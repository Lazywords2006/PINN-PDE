from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
import torch

from block_kyfan_pinn.metrics import (
    orthogonality_error,
    principal_angle_degrees,
    projector_sine_error,
)
from block_kyfan_pinn.model import BlockKyFanPINN
from block_kyfan_pinn.p4_model import (
    AnchoredGeneralizedTracePINN,
    ROMGeneralizedTracePINN,
)
from block_kyfan_pinn.physics import generalized_trace_energy, periodic_mgs
from scripts.run_p4_diagnostic import (
    P4_FAMILIES,
    P4_METHODS,
    P4_PROMOTION_SEEDS,
    _gram_condition_numbers,
    build_p4_gate,
    build_p4_model,
)
from scripts.run_p4_diagnostic import (
    main as p4_main,
)
from scripts.run_p4_executor import (
    _clear_decision_files,
    _environment,
    interpret_promotion_outputs,
    write_evidence_bundle,
)


def _coordinates(batch: int = 2, points: int = 25) -> torch.Tensor:
    return (torch.rand(batch, points, 2) * (2.0 * math.pi)).requires_grad_()


def test_anchored_trace_returns_raw_trial_basis_and_backpropagates() -> None:
    torch.manual_seed(401)
    model = AnchoredGeneralizedTracePINN(
        width=12,
        hidden_layers=1,
        parameter_dim=4,
        anchor_kind="correct",
        anchor_scale=0.1,
    )
    coordinates = _coordinates()
    parameters = torch.tensor([[0.31, 0.35, 0.50, 0.02], [0.35, 0.31, 0.70, -0.02]])
    raw = model(coordinates, parameters)
    assert raw.shape == (2, 25, 2, 2)
    assert orthogonality_error(periodic_mgs(raw)) < 5e-5
    loss = generalized_trace_energy(raw, coordinates, parameters)
    loss.backward()
    assert torch.isfinite(loss)
    assert any(
        parameter.grad is not None and bool(torch.isfinite(parameter.grad).all())
        for parameter in model.parameters()
    )


@pytest.mark.parametrize("num_charts", [1, 2])
def test_rom_trace_exposes_raw_basis_and_chart_diagnostics(num_charts: int) -> None:
    torch.manual_seed(403 + num_charts)
    model = ROMGeneralizedTracePINN(
        width=12,
        hidden_layers=1,
        parameter_dim=4,
        anchor_scale=0.1,
        anchor_kind="correct",
        num_rom_shells=1,
        rom_hidden_width=12,
        rom_hidden_layers=1,
        num_charts=num_charts,
        chart_temperature=0.25,
        potential_family="harmonic_honeycomb",
        parameter_lower=(0.28, 0.28, 0.20, -0.08),
        parameter_upper=(0.38, 0.38, 0.80, 0.08),
    )
    coordinates = _coordinates()
    parameters = torch.tensor([[0.31, 0.35, 0.50, 0.02], [0.35, 0.31, 0.70, -0.02]])
    raw = model(coordinates, parameters)
    weights = model.chart_weights(parameters)
    disagreement = model.chart_disagreement(coordinates, parameters)
    assert raw.shape == (2, 25, 2, 2)
    assert weights.shape == (2, num_charts)
    assert torch.allclose(weights.sum(-1), torch.ones(2), atol=1e-6)
    assert disagreement.shape == (2,)
    loss = generalized_trace_energy(raw, coordinates, parameters)
    loss.backward()
    assert torch.isfinite(loss)
    assert model.m_weighted is False


def test_p4_builder_freezes_the_five_factorial_methods() -> None:
    assert P4_METHODS == (
        "g0_trace",
        "g1_anchor",
        "g2_static_rom",
        "g3_annealed_rom",
        "k3_p3",
    )
    assert P4_FAMILIES == ("harmonic_honeycomb", "gaussian_honeycomb")
    models = {
        method: build_p4_model(
            method,
            potential_family="harmonic_honeycomb",
            width=12,
            hidden_layers=1,
            device=torch.device("cpu"),
            dtype=torch.float32,
        )
        for method in P4_METHODS
    }
    assert isinstance(models["g1_anchor"], AnchoredGeneralizedTracePINN)
    assert isinstance(models["g2_static_rom"], ROMGeneralizedTracePINN)
    assert isinstance(models["g3_annealed_rom"], ROMGeneralizedTracePINN)
    assert models["g2_static_rom"].num_charts == 1
    assert models["g3_annealed_rom"].num_charts == 1
    assert models["g2_static_rom"].rom_schedule == "constant"
    assert models["g3_annealed_rom"].rom_schedule == "cosine_decay"


def test_g0_and_g1_differ_only_by_the_declared_anchor_term() -> None:
    coordinates = _coordinates(batch=1)
    parameters = torch.tensor([[0.31, 0.35, 0.50, 0.02]])
    torch.manual_seed(409)
    g0 = build_p4_model(
        "g0_trace",
        potential_family="harmonic_honeycomb",
        width=12,
        hidden_layers=1,
        device=torch.device("cpu"),
        dtype=torch.float32,
    )
    torch.manual_seed(409)
    g1 = build_p4_model(
        "g1_anchor",
        potential_family="harmonic_honeycomb",
        width=12,
        hidden_layers=1,
        device=torch.device("cpu"),
        dtype=torch.float32,
    )
    for left, right in zip(g0.parameters(), g1.parameters()):
        assert torch.equal(left, right)
    expected = g0(coordinates, parameters) + 0.1 * BlockKyFanPINN.anchor(
        coordinates, "correct"
    )
    assert torch.allclose(g1(coordinates, parameters), expected)


def test_annealed_rom_uses_the_frozen_warm_decay_refine_schedule() -> None:
    model = ROMGeneralizedTracePINN(
        width=12,
        hidden_layers=1,
        parameter_dim=4,
        num_charts=1,
        rom_schedule="cosine_decay",
        rom_scale=0.1,
    )
    model.set_training_progress(0.25)
    assert float(model.active_rom_scale) == pytest.approx(0.1)
    model.set_training_progress(0.50)
    assert float(model.active_rom_scale) == pytest.approx(0.05)
    model.set_training_progress(0.75)
    assert float(model.active_rom_scale) == pytest.approx(0.0)
    model.set_training_progress(1.0)
    assert float(model.active_rom_scale) == pytest.approx(0.0)


def test_promotion_rejects_a_changed_training_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_p4_diagnostic.py", "--protocol", "promotion", "--points", "128"],
    )
    with pytest.raises(ValueError, match="points are frozen as 256"):
        p4_main()


def _passing_summary() -> dict[str, object]:
    paired = []
    for family in P4_FAMILIES:
        for seed in P4_PROMOTION_SEEDS:
            paired.append(
                {
                    "family": family,
                    "seed": seed,
                    "g0_error": 0.20,
                    "g1_error": 0.15,
                    "improvement_percent": 25.0,
                }
            )
    return {
        "total_runs": 30,
        "completed_runs": 30,
        "failed_runs": 0,
        "maximum_orthogonality_error": 1e-6,
        "maximum_gram_condition": 50.0,
        "g0_trace_near_cluster_projector_mean": 0.20,
        "g1_anchor_near_cluster_projector_mean": 0.15,
        "g2_static_rom_near_cluster_projector_mean": 0.18,
        "g3_annealed_rom_near_cluster_projector_mean": 0.18,
        "k3_p3_near_cluster_projector_mean": 0.40,
        "g1_anchor_harmonic_honeycomb_near_cluster_projector_mean": 0.15,
        "g0_trace_harmonic_honeycomb_near_cluster_projector_mean": 0.20,
        "g1_anchor_gaussian_honeycomb_near_cluster_projector_mean": 0.15,
        "g0_trace_gaussian_honeycomb_near_cluster_projector_mean": 0.20,
        "g3_maximum_final_rom_scale": 0.0,
        "g0_trace_harmonic_honeycomb_num_parameters": 9156,
        "g1_anchor_harmonic_honeycomb_num_parameters": 9156,
        "g0_trace_gaussian_honeycomb_num_parameters": 9284,
        "g1_anchor_gaussian_honeycomb_num_parameters": 9284,
        "paired_seed_improvements": paired,
    }


def test_p4_gate_requires_accuracy_schedule_value_and_seed_consistency() -> None:
    passing = build_p4_gate(_passing_summary())
    assert passing["promotion_go"] is True

    weak_anchor = _passing_summary()
    weak_anchor["g1_anchor_near_cluster_projector_mean"] = 0.18
    assert build_p4_gate(weak_anchor)["promotion_go"] is False

    unfair = _passing_summary()
    unfair["g1_anchor_gaussian_honeycomb_num_parameters"] = 10000
    assert build_p4_gate(unfair)["promotion_go"] is False

    unstable = _passing_summary()
    unstable["paired_seed_improvements"][0]["improvement_percent"] = -1.0  # type: ignore[index]
    assert build_p4_gate(unstable)["promotion_go"] is False

    not_annealed = _passing_summary()
    not_annealed["g3_maximum_final_rom_scale"] = 0.1
    assert build_p4_gate(not_annealed)["promotion_go"] is False


def test_evidence_bundle_contains_manifest_and_matching_sha256(tmp_path: Path) -> None:
    results = tmp_path / "results"
    data = tmp_path / "data"
    benchmarks = tmp_path / "benchmarks"
    results.mkdir()
    data.mkdir()
    benchmarks.mkdir()
    (results / "summary.json").write_text(json.dumps({"status": "STOP"}))
    (data / "cache.sha256").write_text("cache")
    (benchmarks / "suite.json").write_text("{}")
    archive, sidecar, manifest = write_evidence_bundle(
        root=tmp_path,
        include_paths=(results, data / "cache.sha256", benchmarks / "suite.json"),
        output_dir=tmp_path / "artifacts",
        label="unit",
    )
    assert archive.is_file() and sidecar.is_file() and manifest.is_file()
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert sidecar.read_text().split()[0] == digest
    with tarfile.open(archive, "r:gz") as handle:
        names = set(handle.getnames())
    assert "results/summary.json" in names
    assert "results/evidence-manifest.json" in names


def test_executor_never_turns_failed_runs_into_false_promotion_go() -> None:
    false_gate = {"promotion_go": False}
    failed_summary = {"total_runs": 30, "completed_runs": 0, "failed_runs": 30}
    assert interpret_promotion_outputs(0, false_gate, failed_summary) == (
        "ENGINEERING_FAIL",
        1,
    )

    complete_stop = {"total_runs": 30, "completed_runs": 30, "failed_runs": 0}
    assert interpret_promotion_outputs(0, false_gate, complete_stop) == (
        "PROMOTION_STOP",
        2,
    )

    true_gate = {"promotion_go": True}
    assert interpret_promotion_outputs(0, true_gate, complete_stop) == (
        "PROMOTION_GO",
        0,
    )
    assert interpret_promotion_outputs(2, true_gate, complete_stop) == (
        "ENGINEERING_FAIL",
        1,
    )


def test_p4_executor_is_directly_invocable() -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/run_p4_executor.py", "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--smoke-only" in completed.stdout


def test_executor_clears_stale_decision_json(tmp_path: Path) -> None:
    (tmp_path / "summary.json").write_text('{"promotion_go": true}\n')
    (tmp_path / "diagnostic_gate.json").write_text('{"promotion_go": true}\n')
    (tmp_path / "latest.pt").write_bytes(b"resume state")
    _clear_decision_files(tmp_path)
    assert not (tmp_path / "summary.json").exists()
    assert not (tmp_path / "diagnostic_gate.json").exists()
    assert (tmp_path / "latest.pt").read_bytes() == b"resume state"


@pytest.mark.skipif(
    not hasattr(torch.backends, "mps") or not torch.backends.mps.is_available(),
    reason="MPS is unavailable",
)
def test_basis_metrics_move_mps_values_to_cpu_before_float64() -> None:
    torch.manual_seed(419)
    basis = periodic_mgs(torch.randn(1, 25, 2, 2, device="mps"))
    assert projector_sine_error(basis, basis) < 1e-3
    mean_angle, max_angle = principal_angle_degrees(basis, basis)
    assert mean_angle < 0.1
    assert max_angle < 0.1
    condition = _gram_condition_numbers(basis)
    assert condition.device.type == "cpu"
    assert bool(torch.isfinite(condition).all())
    environment = _environment(Path(__file__).resolve().parents[1], "mps")
    assert environment["selected_backend"] == "mps"
    assert environment["accelerator_available"] is True

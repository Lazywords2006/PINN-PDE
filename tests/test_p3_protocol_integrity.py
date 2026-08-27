from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path

import pytest
import torch

from block_kyfan_pinn.experiment import _source_fingerprint
from block_kyfan_pinn.metrics import orthogonality_error
from block_kyfan_pinn.p3_model import P3BlockKyFanPINN
from block_kyfan_pinn.p3_rom import m_weighted_gram_mean, m_weighted_gram_schmidt
from block_kyfan_pinn.physics import generalized_trace_energy, periodic_mgs
from block_kyfan_pinn.reference import (
    ReferenceSolution,
    evaluate_reference_basis,
    plane_wave_hamiltonian,
    solve_reference,
    uniform_grid,
)
from block_kyfan_pinn.suites import load_frozen_suite, write_frozen_suite
from scripts.evaluate_v2_final import _load_promoted_runs
from scripts.generate_v2_assets import (
    build_suite_payload,
    generate_validation_suite,
    reference_gap_metadata,
)
from scripts.run_p3_pilot import (
    PILOT_FAMILIES,
    PILOT_METHODS,
    PilotConfig,
    _config_fingerprint,
    _load_completed_result,
    build_pilot_gate,
    build_pilot_model,
    run_pilot_run,
)


def _p3(*, anchor_kind: str = "correct", m_weighted: bool = False) -> P3BlockKyFanPINN:
    return P3BlockKyFanPINN(
        width=12,
        hidden_layers=1,
        anchor_scale=0.1,
        anchor_kind=anchor_kind,
        parameter_dim=4,
        num_rom_shells=1,
        rom_hidden_width=12,
        rom_hidden_layers=1,
        num_charts=2,
        m_weighted=m_weighted,
        gap_monitor=False,
        fallback_enabled=False,
        parameter_lower=(0.28, 0.28, 0.20, -0.08),
        parameter_upper=(0.38, 0.38, 0.80, 0.08),
    )


def test_p3_anchor_ablation_changes_the_initial_subspace() -> None:
    torch.manual_seed(101)
    correct = _p3(anchor_kind="correct")
    wrong = _p3(anchor_kind="wrong")
    wrong.load_state_dict(correct.state_dict(), strict=False)
    coordinates = (torch.rand(1, 36, 2) * (2.0 * math.pi)).requires_grad_()
    parameters = torch.tensor([[0.31, 0.35, 0.50, 0.02]])
    difference = (correct(coordinates, parameters) - wrong(coordinates, parameters)).abs().max()
    assert float(difference.detach()) > 1e-3


def test_p3_m_weighted_tangent_correction_is_effective_and_l2_orthonormal() -> None:
    torch.manual_seed(103)
    weighted = _p3(m_weighted=True)
    unweighted = _p3(m_weighted=False)
    unweighted.load_state_dict(weighted.state_dict())
    coordinates = (torch.rand(2, 49, 2) * (2.0 * math.pi)).requires_grad_()
    parameters = torch.tensor(
        [[0.29, 0.37, 0.25, -0.06], [0.37, 0.29, 0.78, 0.07]]
    )
    weighted_basis = weighted(coordinates, parameters)
    unweighted_basis = unweighted(coordinates, parameters)
    assert float((weighted_basis - unweighted_basis).abs().max().detach()) > 1e-7
    assert orthogonality_error(weighted_basis) < 5e-5


def test_chart_centers_are_learnable_and_use_normalized_parameters() -> None:
    model = _p3()
    parameters = torch.tensor(
        [[0.28, 0.28, 0.20, -0.08], [0.38, 0.38, 0.80, 0.08]]
    )
    weights = model.chart_weights(parameters)
    assert "chart_centers" in dict(model.named_parameters())
    assert weights.shape == (2, 2)
    assert torch.allclose(weights.sum(-1), torch.ones(2), atol=1e-6)
    assert not torch.allclose(weights[0], weights[1])


def test_m_weighted_gram_schmidt_supports_per_sample_weights() -> None:
    torch.manual_seed(107)
    raw = torch.randn(3, 32, 2, 2)
    weights = torch.rand(3, 32) + 0.1
    basis = m_weighted_gram_schmidt(raw, weights)
    gram_real, gram_imag = m_weighted_gram_mean(basis, weights)
    identity = torch.eye(2).expand(3, -1, -1)
    assert torch.allclose(gram_real, identity, atol=5e-5)
    assert torch.allclose(gram_imag, torch.zeros_like(gram_imag), atol=5e-5)


def test_hexagonal_reference_preserves_the_archived_v2_mode_policy() -> None:
    parameters = torch.tensor([1 / 3, 1 / 3, 0.5, 0.0], dtype=torch.float64)
    square_matrix, square_modes = plane_wave_hamiltonian(parameters, cutoff=1, mode_shape="square")
    hex_matrix, hex_modes = plane_wave_hamiltonian(parameters, cutoff=1, mode_shape="hexagonal")
    assert square_matrix.shape == (9, 9)
    assert hex_matrix.shape == (7, 7)
    assert len(square_modes) == 9
    assert len(hex_modes) == 7
    assert {tuple(int(value) for value in row) for row in hex_modes} == {
        (-1, -1),
        (-1, 0),
        (0, -1),
        (0, 0),
        (0, 1),
        (1, 0),
        (1, 1),
    }
    assert torch.allclose(hex_matrix, hex_matrix.mH, atol=1e-12)


def test_d6_reference_uses_the_positive_cross_metric_closure() -> None:
    parameters = torch.tensor([1 / 3, 1 / 3, 0.5, 0.0], dtype=torch.float64)
    matrix, modes = plane_wave_hamiltonian(
        parameters, cutoff=1, mode_shape="hexagonal_d6"
    )
    assert matrix.shape == (7, 7)
    assert {tuple(int(value) for value in row) for row in modes} == {
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 0),
        (0, 1),
        (1, -1),
        (1, 0),
    }
    assert torch.allclose(matrix, matrix.mH, atol=1e-12)


def test_reference_solver_is_deterministic_at_exact_degeneracy() -> None:
    parameters = torch.tensor([1 / 3, 1 / 3, 0.6, 0.0], dtype=torch.float64)
    first = solve_reference(parameters, cutoff=3, rank=3, mode_shape="hexagonal")
    second = solve_reference(parameters, cutoff=3, rank=3, mode_shape="hexagonal")
    assert torch.equal(first.eigenvalues, second.eigenvalues)
    first_projector = first.eigenvectors[:, :2] @ first.eigenvectors[:, :2].mH
    second_projector = second.eigenvectors[:, :2] @ second.eigenvectors[:, :2].mH
    assert torch.allclose(first_projector, second_projector, atol=1e-12)


def test_reference_evaluation_returns_the_coordinate_dtype_and_device() -> None:
    parameters = torch.tensor([0.31, 0.35, 0.5, 0.02], dtype=torch.float64)
    reference = solve_reference(parameters, cutoff=2, rank=2, mode_shape="hexagonal")
    coordinates = torch.rand(1, 16, 2, dtype=torch.float32)
    values = evaluate_reference_basis(reference, coordinates)
    assert values.device == coordinates.device
    assert values.dtype == coordinates.dtype


@pytest.mark.skipif(
    not hasattr(torch.backends, "mps") or not torch.backends.mps.is_available(),
    reason="MPS is unavailable",
)
def test_reference_evaluation_is_mps_compatible() -> None:
    parameters = torch.tensor([0.31, 0.35, 0.5, 0.02], dtype=torch.float64)
    reference = solve_reference(parameters, cutoff=2, rank=2, mode_shape="hexagonal")
    coordinates = torch.rand(1, 16, 2, device="mps", dtype=torch.float32)
    values = evaluate_reference_basis(reference, coordinates)
    assert values.device.type == "mps"
    assert values.dtype == torch.float32


def test_frozen_suite_has_metadata_and_a_raw_file_sha256(tmp_path: Path) -> None:
    points = generate_validation_suite(seed=20260731)[:4]
    payload = build_suite_payload(
        points,
        suite_id="unit-v2",
        seed=20260731,
        purpose="validation",
    )
    path = tmp_path / "suite.json"
    write_frozen_suite(payload, path)
    loaded, digest = load_frozen_suite(path)
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    declared = path.with_suffix(".sha256").read_text().split()[0]
    assert loaded["suite_id"] == "unit-v2"
    assert loaded["point_count"] == 4
    assert len(loaded["points"]) == 4
    assert digest == expected == declared


def test_committed_v2_assets_are_schema_and_hash_valid() -> None:
    root = Path(__file__).resolve().parents[1]
    validation, _ = load_frozen_suite(root / "benchmarks/v2_validation.json")
    frozen, _ = load_frozen_suite(root / "benchmarks/v2_frozen_test.json")
    convergence = json.loads(
        (root / "benchmarks/v2_reference_convergence.json").read_text()
    )
    assert validation["point_count"] == 64
    assert set(validation["split_counts"]) == {
        "iid_hidden",
        "exact_cluster",
        "near_cluster",
        "strict_ood",
        "gap_scan",
    }
    assert frozen["point_count"] == 640
    assert convergence["all_passed"] is True
    validation_parameters = {
        (point["family"], tuple(point["parameters"]))
        for point in validation["points"]
    }
    frozen_parameters = {
        (point["family"], tuple(point["parameters"]))
        for point in frozen["points"]
    }
    assert validation_parameters.isdisjoint(frozen_parameters)


def test_pilot_uses_four_distinct_models_and_enables_two_p3_charts() -> None:
    assert PILOT_METHODS == ("p1_block", "ordered_residual", "wang_xie_trace", "p3")
    models = {
        method: build_pilot_model(
            method,
            potential_family="harmonic_honeycomb",
            width=12,
            hidden_layers=1,
            device=torch.device("cpu"),
            dtype=torch.float32,
        )
        for method in PILOT_METHODS
    }
    assert len({type(model) for model in models.values()}) == 4
    assert isinstance(models["p3"], P3BlockKyFanPINN)
    assert models["p3"].num_charts == 2


def test_pilot_gate_rejects_a_completed_but_inaccurate_p3() -> None:
    summary = {
        "total_runs": 24,
        "completed_runs": 24,
        "failed_runs": 0,
        "maximum_orthogonality_error": 1e-7,
        "p1_block_projector_mean": 0.20,
        "wang_xie_trace_projector_mean": 0.18,
        "p3_projector_mean": 0.30,
    }
    gate = build_pilot_gate(summary)
    assert gate["all_runs_completed"]
    assert not gate["p3_better_than_best_baseline_15pct"]
    assert not gate["pilot_go"]


def test_pilot_gate_requires_the_improvement_in_each_family() -> None:
    summary = {
        "total_runs": 24,
        "completed_runs": 24,
        "failed_runs": 0,
        "maximum_orthogonality_error": 1e-7,
        "p1_block_near_cluster_projector_mean": 0.20,
        "ordered_residual_near_cluster_projector_mean": 0.22,
        "wang_xie_trace_near_cluster_projector_mean": 0.21,
        "p3_near_cluster_projector_mean": 0.16,
    }
    for family, p3_error in (
        ("harmonic_honeycomb", 0.15),
        ("gaussian_honeycomb", 0.19),
    ):
        summary[f"p1_block_{family}_near_cluster_projector_mean"] = 0.20
        summary[f"ordered_residual_{family}_near_cluster_projector_mean"] = 0.22
        summary[f"wang_xie_trace_{family}_near_cluster_projector_mean"] = 0.21
        summary[f"p3_{family}_near_cluster_projector_mean"] = p3_error
    gate = build_pilot_gate(summary)
    assert gate["p3_better_than_best_baseline_15pct"]
    assert not gate["p3_better_than_best_baseline_15pct_each_family"]
    assert not gate["pilot_go"]


def test_reference_gap_metadata_rejects_a_false_exact_label() -> None:
    point = {
        "id": "false-exact",
        "family": "harmonic_honeycomb",
        "split": "exact_cluster",
        "parameters": [1 / 3, 1 / 3, 0.6, 0.0],
    }
    with pytest.raises(ValueError, match="labelled exact_cluster"):
        reference_gap_metadata(point, torch.tensor([0.0, 0.01, 0.5]))


def test_completed_pilot_result_is_bound_to_checkpoint_bytes(tmp_path: Path) -> None:
    final_path = tmp_path / "final.pt"
    result_path = tmp_path / "result.json"
    final_path.write_bytes(b"checkpoint")
    checkpoint_hash = hashlib.sha256(final_path.read_bytes()).hexdigest()
    result_path.write_text(json.dumps({
        "config_fingerprint": "config",
        "source_fingerprint": "source",
        "suite_sha256": "suite",
        "reference_cache_sha256": "cache",
        "final_checkpoint_sha256": checkpoint_hash,
    }))
    loaded = _load_completed_result(
        result_path,
        final_path,
        config_fingerprint="config",
        source_fingerprint="source",
        suite_hash="suite",
        cache_hash="cache",
    )
    assert loaded is not None
    final_path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checkpoint SHA-256 mismatch"):
        _load_completed_result(
            result_path,
            final_path,
            config_fingerprint="config",
            source_fingerprint="source",
            suite_hash="suite",
            cache_hash="cache",
        )


def test_p3_pilot_smoke_writes_a_real_resumable_checkpoint(tmp_path: Path) -> None:
    point = generate_validation_suite(seed=20260731)[0]
    payload = build_suite_payload(
        [point], suite_id="pilot-smoke", seed=20260731, purpose="validation"
    )
    parameters = torch.tensor(point["parameters"], dtype=torch.float64)
    solution = solve_reference(
        parameters,
        cutoff=2,
        rank=3,
        potential_family=str(point["family"]),
        mode_shape="hexagonal",
    )
    grid = uniform_grid(5).unsqueeze(0)
    rank_two = ReferenceSolution(
        solution.eigenvalues[:2], solution.eigenvectors[:, :2], solution.modes
    )
    reference_basis = periodic_mgs(evaluate_reference_basis(rank_two, grid))[0]
    config = PilotConfig(
        method="p3",
        potential_family=str(point["family"]),
        seed=7,
        device="cpu",
        steps=1,
        points=12,
        parameter_batch=1,
        width=8,
        hidden_layers=1,
        eval_grid_side=5,
        checkpoint_every=1,
    )
    run_dir = tmp_path / "run"
    result = run_pilot_run(
        config,
        run_dir,
        suite_payload=payload,
        suite_hash="suite-hash",
        references={
            str(point["id"]): {
                "basis": reference_basis,
                "eigenvalues": solution.eigenvalues,
            }
        },
        cache_hash="cache-hash",
    )
    final_state = torch.load(run_dir / "final.pt", map_location="cpu", weights_only=False)
    assert result["status"] == "PASS"
    assert final_state["step"] == 1
    assert "model" in final_state and "optimizer" in final_state
    assert (run_dir / "metrics.csv").is_file()


def test_generalized_trace_real_block_matches_complex_solve() -> None:
    torch.manual_seed(109)
    coordinates = (torch.rand(2, 25, 2, dtype=torch.float64) * (2 * math.pi)).requires_grad_()
    from block_kyfan_pinn.model import BlockKyFanPINN

    raw = BlockKyFanPINN.anchor(coordinates, "correct")
    parameters = torch.tensor(
        [[0.31, 0.35, 0.5, 0.02], [0.34, 0.32, 0.6, -0.01]],
        dtype=torch.float64,
    )
    from block_kyfan_pinn.physics import (
        apply_hamiltonian,
        complex_gram_mean,
        ritz_matrix,
    )

    h_basis = apply_hamiltonian(raw, coordinates, parameters)
    b_real, b_imag = complex_gram_mean(raw)
    a_real, a_imag = ritz_matrix(raw, h_basis)
    identity = torch.eye(2, dtype=torch.complex128)
    expected = torch.linalg.solve(
        torch.complex(b_real, b_imag) + 1e-6 * identity,
        torch.complex(a_real, a_imag),
    ).diagonal(dim1=-2, dim2=-1).real.sum(-1).mean()
    actual = generalized_trace_energy(raw, coordinates, parameters)
    assert torch.allclose(actual, expected, atol=1e-10, rtol=1e-10)


def _write_fake_pilot_matrix(pilot_dir: Path, *, p3_error: float) -> None:
    suite_hash = "validation-suite"
    cache_hash = "validation-cache"
    seeds = [42, 137, 251]
    pilot_dir.mkdir()
    (pilot_dir / "summary.json").write_text(json.dumps({
        "suite_sha256": suite_hash,
        "reference_cache_sha256": cache_hash,
        "seeds": seeds,
    }))
    source = _source_fingerprint()
    for method in PILOT_METHODS:
        for family in PILOT_FAMILIES:
            for seed in seeds:
                config = PilotConfig(
                    method=method,
                    potential_family=family,
                    seed=seed,
                    device="cpu",
                )
                run_dir = pilot_dir / f"{method}_{family}_seed{seed}"
                run_dir.mkdir()
                final_path = run_dir / "final.pt"
                final_path.write_bytes(f"{method}-{family}-{seed}".encode())
                result = {
                    "config": asdict(config),
                    "config_fingerprint": _config_fingerprint(
                        config, suite_hash, cache_hash
                    ),
                    "source_fingerprint": source,
                    "suite_sha256": suite_hash,
                    "reference_cache_sha256": cache_hash,
                    "final_checkpoint_sha256": hashlib.sha256(
                        final_path.read_bytes()
                    ).hexdigest(),
                    "mean_projector_sine_error": (
                        p3_error if method == "p3" else 0.20
                    ),
                    "split_projector_mean": {
                        "near_cluster": p3_error if method == "p3" else 0.20
                    },
                    "maximum_orthogonality_error": 1e-7,
                }
                (run_dir / "result.json").write_text(json.dumps(result))


def test_final_evaluator_accepts_only_a_recomputed_go_matrix(tmp_path: Path) -> None:
    pilot_dir = tmp_path / "go"
    _write_fake_pilot_matrix(pilot_dir, p3_error=0.10)
    results, gate = _load_promoted_runs(pilot_dir)
    assert len(results) == 24
    assert gate["pilot_go"]


def test_final_evaluator_refuses_a_recomputed_stop_matrix(tmp_path: Path) -> None:
    pilot_dir = tmp_path / "stop"
    _write_fake_pilot_matrix(pilot_dir, p3_error=0.19)
    with pytest.raises(RuntimeError, match="frozen final suite must remain unopened"):
        _load_promoted_runs(pilot_dir)

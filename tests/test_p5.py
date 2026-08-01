from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import torch

from block_kyfan_pinn.p4_model import (
    AnchoredGeneralizedTracePINN,
    ROMGeneralizedTracePINN,
)
from block_kyfan_pinn.p5_model import (
    P5_HIGH_FREQUENCY_MODES,
    P5_METHODS,
    build_p5_model,
)
from scripts.run_p5_diagnostic import P5_FAMILIES, P5_SEEDS, build_p5_gate


def test_p5_executor_is_directly_invocable() -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/run_p5_executor.py", "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--smoke-only" in completed.stdout


def test_p5_models_freeze_capacity_compute_and_frequency_controls() -> None:
    models = {
        method: build_p5_model(
            method,
            potential_family="harmonic_honeycomb",
            device=torch.device("cpu"),
            dtype=torch.float32,
        )
        for method in P5_METHODS
    }
    assert isinstance(models["p5_anchor"], AnchoredGeneralizedTracePINN)
    assert isinstance(models["p5_wide_anchor"], AnchoredGeneralizedTracePINN)
    assert isinstance(models["p5_long_anchor"], AnchoredGeneralizedTracePINN)
    assert isinstance(models["p5_static_low_rom"], ROMGeneralizedTracePINN)
    assert isinstance(models["p5_unanchored_low_rom"], ROMGeneralizedTracePINN)
    assert isinstance(models["p5_highfreq_rom"], ROMGeneralizedTracePINN)
    assert models["p5_wide_anchor"].network[0].out_features == 72
    assert models["p5_unanchored_low_rom"].base_network.anchor_scale == 0.0
    assert models["p5_highfreq_rom"].rom_modes == list(P5_HIGH_FREQUENCY_MODES)
    assert len(models["p5_highfreq_rom"].rom_modes) == len(
        models["p5_static_low_rom"].rom_modes
    )

    counts = {
        name: sum(parameter.numel() for parameter in model.parameters())
        for name, model in models.items()
    }
    assert (
        abs(counts["p5_wide_anchor"] - counts["p5_static_low_rom"])
        / counts["p5_static_low_rom"]
        < 0.02
    )
    assert counts["p5_highfreq_rom"] == counts["p5_static_low_rom"]
    assert counts["p5_unanchored_low_rom"] == counts["p5_static_low_rom"]


def _passing_summary() -> dict[str, object]:
    summary: dict[str, object] = {
        "total_runs": 36,
        "completed_runs": 36,
        "failed_runs": 0,
        "maximum_orthogonality_error": 1e-6,
        "maximum_gram_condition": 20.0,
    }
    near = {
        "p5_anchor": 0.130,
        "p5_static_low_rom": 0.100,
        "p5_wide_anchor": 0.120,
        "p5_long_anchor": 0.120,
        "p5_unanchored_low_rom": 0.115,
        "p5_highfreq_rom": 0.118,
    }
    gaps = {
        "p5_anchor": 0.140,
        "p5_static_low_rom": 0.139,
        "p5_wide_anchor": 0.141,
        "p5_long_anchor": 0.140,
        "p5_unanchored_low_rom": 0.145,
        "p5_highfreq_rom": 0.143,
    }
    for method in P5_METHODS:
        summary[f"{method}_near_cluster_projector_mean"] = near[method]
        summary[f"{method}_gap_scan_projector_mean"] = gaps[method]
        summary[f"{method}_training_time_mean"] = 40.0 if "rom" in method else 39.0
        for family in P5_FAMILIES:
            summary[f"{method}_{family}_near_cluster_projector_mean"] = near[method]
    for family, rom_count, wide_count in (
        ("harmonic_honeycomb", 11300, 11151),
        ("gaussian_honeycomb", 11397, 11524),
    ):
        summary[f"p5_static_low_rom_{family}_num_parameters"] = rom_count
        summary[f"p5_highfreq_rom_{family}_num_parameters"] = rom_count
        summary[f"p5_unanchored_low_rom_{family}_num_parameters"] = rom_count
        summary[f"p5_wide_anchor_{family}_num_parameters"] = wide_count
        base_count = 9156 if family.startswith("harmonic") else 9220
        summary[f"p5_anchor_{family}_num_parameters"] = base_count
        summary[f"p5_long_anchor_{family}_num_parameters"] = base_count

    pairs = []
    for comparator in (
        "p5_anchor",
        "p5_wide_anchor",
        "p5_long_anchor",
        "p5_unanchored_low_rom",
        "p5_highfreq_rom",
    ):
        for family in P5_FAMILIES:
            for seed in P5_SEEDS:
                pairs.append(
                    {
                        "comparator": comparator,
                        "family": family,
                        "seed": seed,
                        "improvement_percent": 10.0,
                    }
                )
    summary["paired_comparisons"] = pairs
    return summary


def test_p5_gate_requires_structure_not_capacity_or_compute() -> None:
    gate = build_p5_gate(_passing_summary())
    assert gate["mechanism_go"] is True
    assert gate["promotion_go"] is True

    capacity_only = _passing_summary()
    capacity_only["p5_wide_anchor_near_cluster_projector_mean"] = 0.101
    assert build_p5_gate(capacity_only)["mechanism_go"] is False

    compute_only = _passing_summary()
    compute_only["p5_long_anchor_near_cluster_projector_mean"] = 0.101
    assert build_p5_gate(compute_only)["mechanism_go"] is False

    wrong_frequency_wins = _passing_summary()
    wrong_frequency_wins["p5_highfreq_rom_near_cluster_projector_mean"] = 0.099
    assert build_p5_gate(wrong_frequency_wins)["mechanism_go"] is False


def test_p5_gate_separates_mechanism_signal_from_gap_scan_safety() -> None:
    regressing = _passing_summary()
    regressing["p5_static_low_rom_gap_scan_projector_mean"] = 0.150
    gate = build_p5_gate(regressing)
    assert gate["mechanism_go"] is True
    assert gate["gap_scan_non_regression"] is False
    assert gate["promotion_go"] is False


def test_p5_gate_requires_five_of_six_paired_wins_for_each_control() -> None:
    unstable = _passing_summary()
    rows = unstable["paired_comparisons"]
    assert isinstance(rows, list)
    changed = 0
    for row in rows:
        if row["comparator"] == "p5_wide_anchor" and changed < 2:
            row["improvement_percent"] = -1.0
            changed += 1
    assert build_p5_gate(unstable)["mechanism_go"] is False


def test_p5_gate_rejects_parameter_and_time_mismatch() -> None:
    unfair = _passing_summary()
    unfair["p5_wide_anchor_gaussian_honeycomb_num_parameters"] = 9000
    assert build_p5_gate(unfair)["mechanism_go"] is False

    time_mismatch = _passing_summary()
    time_mismatch["p5_long_anchor_training_time_mean"] = 20.0
    assert build_p5_gate(time_mismatch)["mechanism_go"] is False

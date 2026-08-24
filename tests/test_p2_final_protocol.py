"""Frozen-final protocol tests for the P2 paper evaluation."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.evaluate_p2_final import (
    build_final_gate,
    clustered_improvement_bootstrap,
    ensure_final_unused,
)


def _passing_summary() -> dict[str, object]:
    return {
        "engineering_pass": True,
        "p2_shell2_all_near_mean": 0.08,
        "p5_long_anchor_near_mean": 0.10,
        "p2_shell2_all_gap_mean": 0.101,
        "best_neural_gap_mean": 0.10,
        "family_near": {
            "harmonic_honeycomb": {"p2_shell2_all": 0.07, "p5_long_anchor": 0.09},
            "gaussian_honeycomb": {"p2_shell2_all": 0.09, "p5_long_anchor": 0.11},
        },
        "paired_near_wins": 6,
        "paired_near_comparisons": 6,
        "p2_shell2_all_overall_mean": 0.08,
        "p5_long_anchor_overall_mean": 0.10,
        "best_p5_overall_mean": 0.095,
        "fourier_only_rank21_overall_mean": 0.20,
        "maximum_orthogonality_error": 1e-6,
        "overall_improvement_ci_low": 0.10,
        "near_improvement_ci_low": 0.08,
    }


def test_final_gate_accepts_only_complete_success() -> None:
    assert build_final_gate(_passing_summary())["final_go"] is True


def test_final_gate_rejects_nonpositive_near_confidence_bound() -> None:
    summary = _passing_summary()
    summary["near_improvement_ci_low"] = -0.01
    assert build_final_gate(summary)["final_go"] is False


def test_clustered_bootstrap_is_deterministic_and_keeps_point_seeds() -> None:
    rows: list[dict[str, object]] = []
    for point in range(12):
        for seed in (42, 137, 251):
            rows.extend(
                (
                    {
                        "method": "primary",
                        "point_id": f"point-{point}",
                        "seed": seed,
                        "split": "near_cluster",
                        "projector_error": 0.08,
                    },
                    {
                        "method": "baseline",
                        "point_id": f"point-{point}",
                        "seed": seed,
                        "split": "near_cluster",
                        "projector_error": 0.10,
                    },
                )
            )

    first = clustered_improvement_bootstrap(
        rows,
        primary="primary",
        baseline="baseline",
        split="near_cluster",
        samples=200,
        seed=20260824,
    )
    second = clustered_improvement_bootstrap(
        rows,
        primary="primary",
        baseline="baseline",
        split="near_cluster",
        samples=200,
        seed=20260824,
    )

    assert first == second
    assert first["low"] == pytest.approx(0.2)
    assert first["valid_samples"] == 200


def test_one_shot_guard_rejects_existing_final_marker(tmp_path: Path) -> None:
    ensure_final_unused(tmp_path)
    marker = tmp_path / "results/P2_FROZEN_FINAL_STARTED.json"
    marker.parent.mkdir(parents=True)
    marker.write_text("{}\n")

    with pytest.raises(RuntimeError, match="already"):
        ensure_final_unused(tmp_path)

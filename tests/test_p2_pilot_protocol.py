"""Protocol tests for the independent P2 full-shell pilot."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from block_kyfan_pinn.suites import load_frozen_suite
from scripts.generate_p2_validation import (
    P2_COUNTS,
    P2_FAMILIES,
    build_p2_suite_payload,
    generate_p2_validation_suite,
    validate_p2_suite_disjointness,
)
from scripts.run_p2_pilot import build_p2_pilot_gate


def _identity(point: dict[str, object]) -> tuple[str, tuple[float, ...]]:
    return str(point["family"]), tuple(float(value) for value in point["parameters"])


def test_p2_suite_is_deterministic_balanced_and_unique() -> None:
    first = generate_p2_validation_suite()
    second = generate_p2_validation_suite()

    assert first == second
    assert len(first) == 96
    assert len({_identity(point) for point in first}) == 96
    assert Counter(str(point["family"]) for point in first) == {
        family: 48 for family in P2_FAMILIES
    }
    assert Counter(str(point["split"]) for point in first) == {
        split: count * 2 for split, count in P2_COUNTS.items()
    }


def test_p2_suite_is_disjoint_from_every_earlier_suite() -> None:
    root = Path(__file__).resolve().parents[1]
    points = generate_p2_validation_suite()
    validate_p2_suite_disjointness(points, root)

    earlier: set[tuple[str, tuple[float, ...]]] = set()
    for name in (
        "v2_validation.json",
        "v2_frozen_test.json",
        "risk_development_v1.json",
        "p1_validation_v1.json",
    ):
        payload, _ = load_frozen_suite(root / "benchmarks" / name)
        earlier.update(_identity(point) for point in payload["points"])
    assert {_identity(point) for point in points}.isdisjoint(earlier)


def test_p2_payload_freezes_protocol_metadata() -> None:
    payload = build_p2_suite_payload(generate_p2_validation_suite())

    assert payload["suite_id"] == "block-kyfan-p2-validation-v1-20260824"
    assert payload["generation_seed"] == 2026082404
    assert payload["purpose"] == "p2_full_shell_independent_pilot_not_final_test"


def _passing_summary() -> dict[str, object]:
    return {
        "engineering_pass": True,
        "p2_shell2_all_near_mean": 0.09,
        "p5_long_anchor_near_mean": 0.10,
        "p2_shell2_all_gap_mean": 0.101,
        "p5_anchor_gap_mean": 0.10,
        "p5_long_anchor_gap_mean": 0.105,
        "family_near": {
            "harmonic_honeycomb": {"p2_shell2_all": 0.08, "p5_long_anchor": 0.09},
            "gaussian_honeycomb": {"p2_shell2_all": 0.10, "p5_long_anchor": 0.11},
        },
        "paired_near_wins": 5,
        "paired_near_comparisons": 6,
        "p2_shell2_all_overall_mean": 0.09,
        "p5_long_anchor_overall_mean": 0.10,
        "fourier_only_rank21_overall_mean": 0.20,
        "maximum_orthogonality_error": 1e-6,
        "p2_latency_mean_ms": 100.0,
        "p2_latency_p95_ms": 150.0,
        "pwe_latency_mean_ms": 300.0,
    }


def test_p2_pilot_gate_accepts_complete_success() -> None:
    assert build_p2_pilot_gate(_passing_summary())["pilot_go"] is True


def test_p2_pilot_gate_rejects_near_failure() -> None:
    summary = _passing_summary()
    summary["p2_shell2_all_near_mean"] = 0.097
    assert build_p2_pilot_gate(summary)["pilot_go"] is False

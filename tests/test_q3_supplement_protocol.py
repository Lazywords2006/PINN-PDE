"""Protocol tests for the independent SCI-Q3 supplement."""

from __future__ import annotations

import inspect
import json
from collections import Counter
from pathlib import Path

import pytest

from block_kyfan_pinn.suites import load_frozen_suite
from scripts.generate_q3_supplement import (
    Q3_COUNTS,
    Q3_FAMILIES,
    Q3_SUITE_SEED,
    build_q3_suite_payload,
    generate_q3_supplement_suite,
    validate_q3_disjointness,
)
from scripts.run_q3_supplement import (
    Q3_METHODS,
    Q3_SEEDS,
    aggregate_q3_rows,
    build_q3_gate,
    validate_result_identities,
)


def _identity(point: dict[str, object]) -> tuple[str, tuple[float, ...]]:
    return str(point["family"]), tuple(float(value) for value in point["parameters"])


def test_q3_suite_is_deterministic_balanced_unique_and_disjoint() -> None:
    first = generate_q3_supplement_suite()
    second = generate_q3_supplement_suite()

    assert first == second
    assert len(first) == 160
    assert len({_identity(point) for point in first}) == 160
    assert Counter(str(point["family"]) for point in first) == {
        family: 80 for family in Q3_FAMILIES
    }
    assert Counter(str(point["split"]) for point in first) == {
        split: count * len(Q3_FAMILIES) for split, count in Q3_COUNTS.items()
    }
    validate_q3_disjointness(first, Path(__file__).resolve().parents[1])


def test_q3_payload_freezes_protocol_and_committed_bytes() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = build_q3_suite_payload(generate_q3_supplement_suite())

    assert payload["suite_id"] == "block-kyfan-q3-supplement-v1-20260824"
    assert payload["generation_seed"] == Q3_SUITE_SEED
    assert payload["purpose"] == "independent_q3_journal_baseline_supplement_not_final"
    committed, _ = load_frozen_suite(root / "benchmarks/q3_supplement_v1.json")
    assert json.dumps(committed, sort_keys=True) == json.dumps(payload, sort_keys=True)


def test_q3_runner_never_calls_the_frozen_final_evaluator() -> None:
    import scripts.run_q3_supplement as module

    source = inspect.getsource(module)
    assert "evaluate_p2_final.py" not in source
    assert "v2_frozen_test_references" not in source


def test_result_identity_matrix_requires_every_method_seed_and_point() -> None:
    points = [
        {"id": "h", "family": "harmonic_honeycomb"},
        {"id": "g", "family": "gaussian_honeycomb"},
    ]
    rows = [
        {
            "method": method,
            "seed": seed,
            "point_id": point["id"],
            "family": point["family"],
        }
        for method in Q3_METHODS
        for seed in Q3_SEEDS
        for point in points
    ]
    validate_result_identities(rows, points)
    with pytest.raises(ValueError, match="identity matrix"):
        validate_result_identities(rows[:-1], points)


def _passing_summary() -> dict[str, object]:
    return {
        "engineering_pass": True,
        "maximum_orthogonality_error": 1e-7,
        "overall": {
            "p2_full_shell": 0.04,
            "wang_xie_trace_adapted": 0.12,
            "dai_galerkin_adapted": 0.10,
        },
        "splits": {
            "near_cluster": {
                "p2_full_shell": 0.03,
                "wang_xie_trace_adapted": 0.11,
                "dai_galerkin_adapted": 0.09,
            },
            "gap_scan": {
                "p2_full_shell": 0.05,
                "wang_xie_trace_adapted": 0.13,
                "dai_galerkin_adapted": 0.12,
            },
        },
        "paired_family_seed_wins": {
            "wang_xie_trace_adapted": 6,
            "dai_galerkin_adapted": 5,
        },
        "bootstrap_improvement": {
            "wang_xie_trace_adapted": {"low": 0.40, "high": 0.70},
            "dai_galerkin_adapted": {"low": 0.30, "high": 0.60},
        },
    }


def test_q3_gate_accepts_complete_success_and_rejects_near_failure() -> None:
    assert build_q3_gate(_passing_summary())["q3_supplement_go"] is True
    failed = _passing_summary()
    failed["splits"]["near_cluster"]["p2_full_shell"] = 0.095  # type: ignore[index]
    assert build_q3_gate(failed)["q3_supplement_go"] is False


def test_q3_aggregation_preserves_paired_cluster_improvement() -> None:
    points = [
        {"id": "near", "family": "harmonic_honeycomb", "split": "near_cluster"},
        {"id": "gap", "family": "gaussian_honeycomb", "split": "gap_scan"},
    ]
    errors = {
        "p2_full_shell": {"near": 0.05, "gap": 0.06},
        "wang_xie_trace_adapted": {"near": 0.15, "gap": 0.16},
        "dai_galerkin_adapted": {"near": 0.10, "gap": 0.12},
    }
    rows = [
        {
            "method": method,
            "seed": seed,
            "point_id": str(point["id"]),
            "family": str(point["family"]),
            "split": str(point["split"]),
            "projector_error": errors[method][str(point["id"])],
            "orthogonality_error": 1e-7,
            "residual_rms": 0.01,
            "latency_ms": 2.0,
        }
        for method in Q3_METHODS
        for seed in Q3_SEEDS
        for point in points
    ]
    summary = aggregate_q3_rows(rows, points, bootstrap_samples=200)

    assert summary["overall"]["p2_full_shell"] == pytest.approx(0.055)
    assert summary["paired_family_seed_wins"]["wang_xie_trace_adapted"] == 6
    assert summary["paired_family_seed_wins"]["dai_galerkin_adapted"] == 6
    assert summary["bootstrap_improvement"]["wang_xie_trace_adapted"]["low"] > 0
    assert build_q3_gate(summary)["q3_supplement_go"] is True

"""Protocol-integrity tests for the independent P1 pilot."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from block_kyfan_pinn.suites import load_frozen_suite
from scripts.generate_p1_validation import (
    P1_COUNTS,
    P1_FAMILIES,
    build_p1_suite_payload,
    generate_p1_validation_suite,
    validate_p1_suite_disjointness,
)


def _identity(point: dict[str, object]) -> tuple[str, tuple[float, ...]]:
    return str(point["family"]), tuple(float(x) for x in point["parameters"])


def test_p1_suite_is_deterministic_and_has_exact_counts() -> None:
    first = generate_p1_validation_suite()
    second = generate_p1_validation_suite()

    assert first == second
    assert len(first) == 96
    assert len({_identity(point) for point in first}) == 96
    assert Counter(str(point["family"]) for point in first) == {
        family: 48 for family in P1_FAMILIES
    }
    assert Counter(str(point["split"]) for point in first) == {
        split: count * len(P1_FAMILIES) for split, count in P1_COUNTS.items()
    }


def test_p1_payload_freezes_purpose_seed_and_counts() -> None:
    payload = build_p1_suite_payload(generate_p1_validation_suite())

    assert payload["suite_id"] == "block-kyfan-p1-validation-v1-20260824"
    assert payload["purpose"] == "p1_risk_gated_corrector_pilot_not_final_test"
    assert payload["generation_seed"] == 2026082403
    assert payload["family_counts"] == {
        "harmonic_honeycomb": 48,
        "gaussian_honeycomb": 48,
    }


def test_p1_suite_is_disjoint_from_all_earlier_suites() -> None:
    root = Path(__file__).resolve().parents[1]
    points = generate_p1_validation_suite()

    validate_p1_suite_disjointness(points, root)

    earlier: set[tuple[str, tuple[float, ...]]] = set()
    for name in (
        "v2_validation.json",
        "v2_frozen_test.json",
        "risk_development_v1.json",
    ):
        payload, _ = load_frozen_suite(root / "benchmarks" / name)
        earlier.update(_identity(point) for point in payload["points"])
    assert {_identity(point) for point in points}.isdisjoint(earlier)


def test_committed_p1_suite_matches_regeneration_and_sidecar() -> None:
    root = Path(__file__).resolve().parents[1]
    payload, _ = load_frozen_suite(root / "benchmarks/p1_validation_v1.json")
    regenerated = build_p1_suite_payload(generate_p1_validation_suite())

    assert json.dumps(payload, sort_keys=True) == json.dumps(regenerated, sort_keys=True)

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from block_kyfan_pinn.suites import load_frozen_suite
from scripts.generate_risk_development import (
    RISK_AUDIT_SEED,
    RISK_CALIBRATION_SEED,
    build_risk_suite_payload,
    generate_risk_development_suite,
)


def _identity(point: dict[str, object]) -> tuple[str, tuple[float, ...]]:
    return str(point["family"]), tuple(float(v) for v in point["parameters"])


def test_risk_suite_is_deterministic_and_has_exact_counts() -> None:
    first = generate_risk_development_suite()
    second = generate_risk_development_suite()
    assert first == second
    assert len(first) == 160
    assert len({str(point["id"]) for point in first}) == 160
    assert Counter(str(point["role"]) for point in first) == {
        "calibration": 80,
        "audit": 80,
    }
    assert Counter(str(point["family"]) for point in first) == {
        "harmonic_honeycomb": 80,
        "gaussian_honeycomb": 80,
    }
    assert Counter(str(point["split"]) for point in first) == {
        "iid_hidden": 32,
        "exact_cluster": 16,
        "near_cluster": 40,
        "strict_ood": 32,
        "gap_scan": 40,
    }
    assert Counter(
        (str(point["role"]), str(point["family"])) for point in first
    ) == {
        ("calibration", "harmonic_honeycomb"): 40,
        ("calibration", "gaussian_honeycomb"): 40,
        ("audit", "harmonic_honeycomb"): 40,
        ("audit", "gaussian_honeycomb"): 40,
    }


def test_risk_suite_is_disjoint_from_v2_and_between_roles() -> None:
    root = Path(__file__).resolve().parents[1]
    points = generate_risk_development_suite()
    calibration = {
        _identity(point) for point in points if point["role"] == "calibration"
    }
    audit = {_identity(point) for point in points if point["role"] == "audit"}
    validation, _ = load_frozen_suite(root / "benchmarks/v2_validation.json")
    frozen, _ = load_frozen_suite(root / "benchmarks/v2_frozen_test.json")
    committed = {
        _identity(point) for point in validation["points"] + frozen["points"]
    }
    assert calibration.isdisjoint(audit)
    assert calibration.isdisjoint(committed)
    assert audit.isdisjoint(committed)


def test_risk_payload_freezes_roles_and_seeds() -> None:
    payload = build_risk_suite_payload(generate_risk_development_suite())
    assert payload["suite_id"] == "block-kyfan-risk-development-v1-20260824"
    assert payload["purpose"] == "risk_calibration_and_heldout_audit_not_final_test"
    assert payload["point_count"] == 160
    assert payload["role_seeds"] == {
        "calibration": RISK_CALIBRATION_SEED,
        "audit": RISK_AUDIT_SEED,
    }


def test_committed_risk_suite_and_sidecar_are_valid() -> None:
    root = Path(__file__).resolve().parents[1]
    payload, _ = load_frozen_suite(root / "benchmarks/risk_development_v1.json")
    expected = json.loads(
        json.dumps(build_risk_suite_payload(generate_risk_development_suite()))
    )
    assert payload == expected

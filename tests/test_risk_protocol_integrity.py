from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import torch

from block_kyfan_pinn.suites import load_frozen_suite, write_frozen_suite
from scripts.evaluate_risk_features import inventory_p5_checkpoints
from scripts.generate_risk_development import (
    RISK_AUDIT_SEED,
    RISK_CALIBRATION_SEED,
    build_reference_cache,
    build_risk_suite_payload,
    generate_risk_development_suite,
)
from scripts.generate_v2_assets import build_suite_payload


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


def test_reference_cache_binds_suite_and_numerical_policy(tmp_path: Path) -> None:
    points = generate_risk_development_suite()[:2]
    suite = build_suite_payload(
        points,
        suite_id="unit-risk-reference",
        seed=918,
        purpose="unit_test_not_final",
    )
    suite_path = tmp_path / "suite.json"
    write_frozen_suite(suite, suite_path)
    cache_path = tmp_path / "references.pt"
    cache_hash = build_reference_cache(
        suite_path,
        cache_path,
        cutoff=2,
        grid_side=9,
        rank=3,
    )
    payload = torch.load(cache_path, map_location="cpu", weights_only=False)
    assert payload["metadata"]["suite_id"] == "unit-risk-reference"
    assert payload["metadata"]["cutoff"] == 2
    assert payload["metadata"]["grid_side"] == 9
    assert payload["metadata"]["rank"] == 3
    assert payload["metadata"]["point_count"] == 2
    assert len(payload["references"]) == 2
    assert cache_path.with_suffix(".sha256").read_text().split()[0] == cache_hash


def test_p5_inventory_contains_only_twelve_declared_final_checkpoints() -> None:
    root = Path(__file__).resolve().parents[1]
    archive = root / "artifacts/p5-evidence-20260801-092048.tar.gz"
    inventory = inventory_p5_checkpoints(
        archive, archive.with_suffix(archive.suffix + ".sha256")
    )
    assert len(inventory) == 12
    assert {
        (row["method"], row["family"], row["seed"])
        for row in inventory
    } == {
        (method, family, seed)
        for method in ("p5_anchor", "p5_static_low_rom")
        for family in ("harmonic_honeycomb", "gaussian_honeycomb")
        for seed in (42, 137, 251)
    }
    assert all(str(row["checkpoint_member"]).endswith("/final.pt") for row in inventory)
    assert all("latest.pt" not in str(row["checkpoint_member"]) for row in inventory)

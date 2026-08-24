from __future__ import annotations

import json
import hashlib
import math
import tarfile
from collections import Counter
from pathlib import Path

import pytest
import torch

from block_kyfan_pinn.risk import FORBIDDEN_FEATURES
from block_kyfan_pinn.physics import periodic_mgs
from block_kyfan_pinn.suites import load_frozen_suite, write_frozen_suite
from scripts.evaluate_risk_features import (
    PROMOTED_FEATURES,
    _risk_source_fingerprint,
    build_paired_feature_row,
    calibrate_and_audit,
    evaluate_paired_points,
    inventory_p5_checkpoints,
    load_p5_checkpoint,
    package_risk_evidence,
)
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


def test_paired_feature_row_separates_permitted_features_from_oracle_labels() -> None:
    torch.manual_seed(929)
    anchor_basis = periodic_mgs(torch.randn(1, 25, 2, 2))
    candidate_basis = periodic_mgs(torch.randn(1, 25, 2, 2))
    anchor = {
        "residual": 0.10,
        "gram": 2.0,
        "ritz_1": 0.2,
        "ritz_2": 0.5,
        "basis": anchor_basis,
        "projector_error": 0.20,
    }
    candidate = {
        "residual": 0.12,
        "gram": 3.0,
        "ritz_1": 0.25,
        "ritz_2": 0.60,
        "basis": candidate_basis,
        "projector_error": 0.23,
    }
    row = build_paired_feature_row(
        role="audit",
        family="harmonic_honeycomb",
        split="gap_scan",
        point_id="risk-audit-harmonic-gap-000",
        seed=42,
        anchor=anchor,
        candidate=candidate,
        reference_internal_gap=0.01,
        reference_external_gap=0.20,
    )
    assert all(name in row for name in PROMOTED_FEATURES)
    assert set(PROMOTED_FEATURES).isdisjoint(FORBIDDEN_FEATURES)
    assert row["regression"] is True
    assert row["unsafe_regression"] is True
    assert row["delta_error"] == pytest.approx(0.03)
    assert row["projector_disagreement"] > 0.0


def test_actual_p5_checkpoint_pair_extracts_one_finite_feature_row() -> None:
    root = Path(__file__).resolve().parents[1]
    archive = root / "artifacts/p5-evidence-20260801-092048.tar.gz"
    inventory = inventory_p5_checkpoints(
        archive, archive.with_suffix(archive.suffix + ".sha256")
    )
    selected = {
        str(row["method"]): row
        for row in inventory
        if row["family"] == "harmonic_honeycomb" and row["seed"] == 42
    }
    anchor = load_p5_checkpoint(
        archive, selected["p5_anchor"], torch.device("cpu")
    )
    candidate = load_p5_checkpoint(
        archive, selected["p5_static_low_rom"], torch.device("cpu")
    )
    suite, _ = load_frozen_suite(root / "benchmarks/risk_development_v1.json")
    point = next(
        point
        for point in suite["points"]
        if point["family"] == "harmonic_honeycomb"
    )
    cache = torch.load(
        root / "data/risk_development_v1_references.pt",
        map_location="cpu",
        weights_only=False,
    )
    rows = evaluate_paired_points(
        anchor,
        candidate,
        [point],
        cache["references"],
        seed=42,
        device=torch.device("cpu"),
    )
    assert len(rows) == 1
    assert all(math.isfinite(float(rows[0][name])) for name in PROMOTED_FEATURES)
    assert isinstance(rows[0]["regression"], bool)


def _synthetic_risk_rows(*, shuffled_audit: bool = False) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for role, count in (("calibration", 16), ("audit", 40)):
        for index in range(count):
            positive = index % 2 == 1
            if role == "audit" and shuffled_audit:
                positive = index % 4 in {0, 1}
            signal = 2.0 if index % 2 == 1 else -2.0
            if role == "audit":
                signal *= 10.0
            row: dict[str, object] = {
                name: 0.0 for name in PROMOTED_FEATURES
            }
            row.update(
                {
                    "role": role,
                    "family": (
                        "harmonic_honeycomb"
                        if index % 4 in {0, 3}
                        else "gaussian_honeycomb"
                    ),
                    "split": "gap_scan",
                    "point_id": f"{role}-{index:03d}",
                    "seed": 42,
                    "residual_delta": signal,
                    "delta_error": 0.2 if positive else -0.2,
                    "regression": positive,
                    "unsafe_regression": positive,
                    "reference_internal_gap": 0.01,
                    "reference_external_gap": 0.20,
                }
            )
            rows.append(row)
    return rows


def test_calibration_uses_only_calibration_role_and_can_pass_gate() -> None:
    result = calibrate_and_audit(
        _synthetic_risk_rows(), bootstrap_samples=200, bootstrap_seed=947
    )
    residual_index = list(PROMOTED_FEATURES).index("residual_delta")
    assert result["model"]["mean"][residual_index] == pytest.approx(0.0)
    assert result["metrics"]["primary_auroc"] == pytest.approx(1.0)
    assert result["metrics"]["unsafe_auroc"] == pytest.approx(1.0)
    assert result["gate"]["risk_go"] is True
    assert len(result["audit_scores"]) == 40


def test_heldout_shuffled_labels_force_risk_stop() -> None:
    result = calibrate_and_audit(
        _synthetic_risk_rows(shuffled_audit=True),
        bootstrap_samples=200,
        bootstrap_seed=953,
    )
    assert result["metrics"]["primary_auroc"] < 0.70
    assert result["gate"]["risk_go"] is False


def test_risk_evidence_bundle_has_manifest_and_matching_sidecar(
    tmp_path: Path,
) -> None:
    result_dir = tmp_path / "results/risk_development_v1"
    result_dir.mkdir(parents=True)
    metrics = result_dir / "metrics.json"
    metrics.write_text('{"primary_auroc": 0.75}\n')
    archive, sidecar, manifest = package_risk_evidence(
        root=tmp_path,
        include_paths=(result_dir,),
        output_dir=tmp_path / "artifacts",
        label="unit",
    )
    expected = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert sidecar.read_text().split()[0] == expected
    manifest_payload = json.loads(manifest.read_text())
    assert [row["path"] for row in manifest_payload["files"]] == [
        "results/risk_development_v1/metrics.json"
    ]
    with tarfile.open(archive, "r:gz") as handle:
        assert "results/risk_development_v1/metrics.json" in handle.getnames()
        assert "results/risk-development-evidence-manifest.json" in handle.getnames()


def test_risk_source_fingerprint_covers_evaluator_scripts(tmp_path: Path) -> None:
    package = tmp_path / "block_kyfan_pinn"
    scripts = tmp_path / "scripts"
    package.mkdir()
    scripts.mkdir()
    (package / "risk.py").write_text("VALUE = 1\n")
    for name in (
        "generate_risk_development.py",
        "evaluate_risk_features.py",
        "audit_p5_evidence.py",
    ):
        (scripts / name).write_text(f"NAME = {name!r}\n")
    before = _risk_source_fingerprint(tmp_path)
    (scripts / "evaluate_risk_features.py").write_text("NAME = 'changed'\n")
    after = _risk_source_fingerprint(tmp_path)
    assert before != after

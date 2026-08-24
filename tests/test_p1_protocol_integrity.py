"""Protocol-integrity tests for the independent P1 pilot."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from block_kyfan_pinn.suites import load_frozen_suite
from scripts.generate_p1_validation import (
    P1_COUNTS,
    P1_FAMILIES,
    build_p1_suite_payload,
    generate_p1_validation_suite,
    validate_p1_suite_disjointness,
)
from scripts.run_p1_pilot import (
    EXPECTED_P0_ARCHIVE_SHA256,
    frozen_thresholds,
    load_p0_calibration,
    p1_source_fingerprint,
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


def test_p0_calibration_is_loaded_from_the_self_contained_go_evidence() -> None:
    root = Path(__file__).resolve().parents[1]
    archive = root / "artifacts/risk-development-evidence-20260824-092630.tar.gz"
    sidecar = archive.with_suffix(archive.suffix + ".sha256")

    calibration = load_p0_calibration(archive, sidecar)

    assert calibration["archive_sha256"] == EXPECTED_P0_ARCHIVE_SHA256
    assert calibration["gate"]["risk_go"] is True
    assert len(calibration["rows"]) == 240
    assert {row["role"] for row in calibration["rows"]} == {"calibration"}
    assert calibration["model"]["feature_names"] == calibration["feature_schema"]


def test_frozen_thresholds_use_calibration_rows_only() -> None:
    root = Path(__file__).resolve().parents[1]
    archive = root / "artifacts/risk-development-evidence-20260824-092630.tar.gz"
    sidecar = archive.with_suffix(archive.suffix + ".sha256")
    calibration = load_p0_calibration(archive, sidecar)

    first = frozen_thresholds(calibration["model"], calibration["rows"])
    with_fake_audit = list(calibration["rows"]) + [
        {
            **calibration["rows"][0],
            "role": "audit",
            calibration["feature_schema"][0]: 1e9,
        }
    ]
    second = frozen_thresholds(calibration["model"], with_fake_audit)

    assert first == second
    assert first["calibration_rows"] == 240
    assert first["t_low_q60"] < first["t_hard_q80"] < first["t_high_q90"]
    assert first["t_high_q90"] < first["t_pwe_q95"]


def test_p0_evidence_sidecar_mismatch_is_rejected(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    archive = root / "artifacts/risk-development-evidence-20260824-092630.tar.gz"
    bad_sidecar = tmp_path / "evidence.sha256"
    bad_sidecar.write_text("0" * 64 + "  evidence.tar.gz\n")

    with pytest.raises(ValueError, match="sidecar"):
        load_p0_calibration(archive, bad_sidecar)


def test_p1_source_fingerprint_covers_corrector_and_orchestration(tmp_path: Path) -> None:
    package = tmp_path / "block_kyfan_pinn"
    scripts = tmp_path / "scripts"
    package.mkdir()
    scripts.mkdir()
    for path in (
        package / "p1_corrector.py",
        package / "risk.py",
        scripts / "generate_p1_validation.py",
        scripts / "run_p1_pilot.py",
        scripts / "evaluate_risk_features.py",
        scripts / "audit_p5_evidence.py",
    ):
        path.write_text(f"SOURCE = {path.name!r}\n")

    before = p1_source_fingerprint(tmp_path)
    (package / "p1_corrector.py").write_text("SOURCE = 'changed'\n")
    after = p1_source_fingerprint(tmp_path)

    assert len(before) == 64
    assert before != after

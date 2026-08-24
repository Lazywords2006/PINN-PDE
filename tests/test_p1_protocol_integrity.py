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
    build_p1_reference_cache,
    build_p1_suite_payload,
    generate_p1_validation_suite,
    main as generate_p1_main,
    validate_p1_suite_disjointness,
)
from scripts.run_p1_pilot import (
    EXPECTED_P0_ARCHIVE_SHA256,
    P1_METHODS,
    build_inference_features,
    build_p1_bases,
    frozen_thresholds,
    load_p0_calibration,
    p1_source_fingerprint,
)
from block_kyfan_pinn.metrics import orthogonality_error, projector_sine_error
from block_kyfan_pinn.physics import periodic_mgs
from block_kyfan_pinn.suites import write_frozen_suite


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


def test_p1_reference_cache_binds_tiny_suite(tmp_path: Path) -> None:
    points = [
        point
        for point in generate_p1_validation_suite()
        if point["split"] == "iid_hidden"
    ][:2]
    suite_path = tmp_path / "p1_tiny.json"
    cache_path = tmp_path / "p1_tiny.pt"
    write_frozen_suite(build_p1_suite_payload(points), suite_path)

    digest = build_p1_reference_cache(
        suite_path, cache_path, cutoff=2, grid_side=7, rank=3
    )

    payload = __import__("torch").load(cache_path, map_location="cpu", weights_only=False)
    assert len(digest) == 64
    assert payload["metadata"]["suite_id"] == "block-kyfan-p1-validation-v1-20260824"
    assert payload["metadata"]["cutoff"] == 2
    assert set(payload["references"]) == {point["id"] for point in points}
    assert cache_path.with_suffix(".sha256").is_file()


def test_p1_generator_cache_cli_writes_requested_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    points = [
        point
        for point in generate_p1_validation_suite()
        if point["split"] == "iid_hidden"
    ][:2]
    suite_path = tmp_path / "p1_cli.json"
    cache_path = tmp_path / "p1_cli.pt"
    write_frozen_suite(build_p1_suite_payload(points), suite_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "generate_p1_validation.py",
            "--cache-only",
            "--output",
            str(suite_path),
            "--cache-output",
            str(cache_path),
            "--cutoff",
            "2",
            "--grid-side",
            "7",
            "--rank",
            "3",
        ],
    )

    assert generate_p1_main() == 0
    assert cache_path.is_file()


def _synthetic_basis(seed: int) -> object:
    import torch

    generator = torch.Generator().manual_seed(seed)
    return periodic_mgs(torch.randn(2, 29, 2, 2, generator=generator, dtype=torch.float64))


def test_build_inference_features_uses_only_paired_predictions() -> None:
    anchor_basis = _synthetic_basis(1)
    candidate_basis = _synthetic_basis(2)
    anchor = {
        "basis": anchor_basis,
        "residual": 0.2,
        "gram": 2.0,
        "ritz_1": 0.4,
        "ritz_2": 0.45,
    }
    candidate = {
        "basis": candidate_basis,
        "residual": 0.1,
        "gram": 1.5,
        "ritz_1": 0.41,
        "ritz_2": 0.44,
    }

    features = build_inference_features(anchor, candidate)

    assert tuple(features) == tuple(__import__("scripts.evaluate_risk_features", fromlist=["PROMOTED_FEATURES"]).PROMOTED_FEATURES)
    assert all(isinstance(value, float) for value in features.values())
    assert not any("reference" in name or "error" in name for name in features)


def test_build_p1_bases_returns_all_frozen_methods_without_primary_pwe() -> None:
    import torch

    anchor = _synthetic_basis(3)
    candidate = _synthetic_basis(4)
    long_anchor = _synthetic_basis(5)
    reference = _synthetic_basis(6)
    thresholds = {
        "t_low_q60": 0.3,
        "t_hard_q80": 0.5,
        "t_high_q90": 0.7,
        "t_pwe_q95": 0.8,
    }

    outputs = build_p1_bases(
        anchor,
        candidate,
        long_anchor,
        reference,
        score=torch.tensor([0.2, 0.9], dtype=torch.float64),
        thresholds=thresholds,
    )

    assert tuple(outputs) == P1_METHODS
    assert outputs["p1_risk_chordal"]["pwe_mask"].tolist() == [False, False]
    assert outputs["p1_risk_chordal_pwe5"]["pwe_mask"].tolist() == [False, True]
    for method, output in outputs.items():
        basis = output["basis"]
        assert basis.shape == anchor.shape
        assert orthogonality_error(basis) < 1e-5
        if method == "oracle_min_anchor_rom":
            assert output["reference_only"] is True
        else:
            assert output["reference_only"] is False
    assert projector_sine_error(outputs["p5_anchor"]["basis"], anchor) < 1e-6

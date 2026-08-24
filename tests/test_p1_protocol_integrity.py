"""Protocol-integrity tests for the independent P1 pilot."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from block_kyfan_pinn.metrics import orthogonality_error, projector_sine_error
from block_kyfan_pinn.physics import periodic_mgs
from block_kyfan_pinn.suites import load_frozen_suite, write_frozen_suite
from scripts.generate_p1_validation import (
    P1_COUNTS,
    P1_FAMILIES,
    build_p1_reference_cache,
    build_p1_suite_payload,
    generate_p1_validation_suite,
    validate_p1_suite_disjointness,
)
from scripts.generate_p1_validation import (
    main as generate_p1_main,
)
from scripts.run_p1_pilot import (
    EXPECTED_P0_ARCHIVE_SHA256,
    P1_METHODS,
    _load_p1_unit,
    _write_p1_unit,
    accelerator_peak_memory,
    add_reference_p1_variants,
    aggregate_p1_rows,
    audit_p1_evidence,
    benchmark_neural_latency,
    build_inference_features,
    build_neural_p1_bases,
    build_p1_bases,
    build_primary_neural_p1,
    evaluate_p1_point,
    fit_parameter_only_risk,
    frozen_thresholds,
    inventory_p1_checkpoints,
    load_p0_calibration,
    p1_source_fingerprint,
    parameter_only_score,
    prepare_environment,
    validate_p1_runtime_suite,
)
from scripts.run_p1_pilot import (
    build_parser as build_p1_parser,
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
    assert all(isinstance(row["parameters"], list) for row in calibration["rows"])


def test_parameter_only_risk_is_frozen_from_p0_calibration() -> None:
    root = Path(__file__).resolve().parents[1]
    archive = root / "artifacts/risk-development-evidence-20260824-092630.tar.gz"
    calibration = load_p0_calibration(
        archive, archive.with_suffix(archive.suffix + ".sha256")
    )

    first = fit_parameter_only_risk(calibration["rows"])
    second = fit_parameter_only_risk(calibration["rows"])
    scores = parameter_only_score(
        [
            {
                "family": row["family"],
                "parameters": row["parameters"],
            }
            for row in calibration["rows"][:4]
        ],
        first["model"],
    )

    assert first == second
    assert scores.shape == (4,)
    assert first["t_low_q60"] < first["t_high_q90"]
    assert first["model"]["feature_names"][-1] == "parameter_family_gaussian"


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
        scripts / "generate_risk_development.py",
        scripts / "generate_v2_assets.py",
        scripts / "run_p1_pilot.py",
        scripts / "evaluate_risk_features.py",
        scripts / "audit_p5_evidence.py",
        scripts / "run_p3_pilot.py",
        scripts / "run_p4_executor.py",
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


def test_primary_neural_outputs_are_built_without_reference_argument() -> None:
    import torch

    anchor = _synthetic_basis(31)
    candidate = _synthetic_basis(32)
    thresholds = {
        "t_low_q60": 0.3,
        "t_hard_q80": 0.5,
        "t_high_q90": 0.7,
        "t_pwe_q95": 0.8,
        "score_min": 0.1,
        "score_max": 0.9,
    }

    neural = build_neural_p1_bases(
        anchor,
        candidate,
        score=torch.tensor([0.2, 0.95], dtype=torch.float64),
        thresholds=thresholds,
    )

    assert tuple(neural) == (
        "p5_anchor",
        "p5_static_low_rom",
        "p1_hard_select",
        "p1_no_risk_half_blend",
        "p1_parameter_only_chordal",
        "p1_risk_chordal",
    )
    assert neural["p1_risk_chordal"]["pwe_mask"].tolist() == [False, False]
    assert neural["p1_risk_chordal"]["risk_ood_mask"].tolist() == [False, True]
    assert projector_sine_error(
        neural["p1_risk_chordal"]["basis"][1:], anchor[1:]
    ) < 1e-6

    completed = add_reference_p1_variants(
        neural,
        anchor,
        candidate,
        _synthetic_basis(33),
        score=torch.tensor([0.2, 0.95], dtype=torch.float64),
        thresholds=thresholds,
    )
    assert set(completed) == set(P1_METHODS) - {"p5_long_anchor"}


def test_production_primary_matches_primary_row_without_building_ablations() -> None:
    import torch

    anchor = _synthetic_basis(41)
    candidate = _synthetic_basis(42)
    score = torch.tensor([0.2, 0.8], dtype=torch.float64)
    thresholds = {
        "t_low_q60": 0.3,
        "t_hard_q80": 0.5,
        "t_high_q90": 0.7,
        "t_pwe_q95": 0.8,
        "score_min": 0.1,
        "score_max": 0.9,
    }

    primary = build_primary_neural_p1(
        anchor, candidate, score=score, thresholds=thresholds
    )
    all_neural = build_neural_p1_bases(
        anchor, candidate, score=score, thresholds=thresholds
    )

    assert torch.allclose(
        primary["basis"], all_neural["p1_risk_chordal"]["basis"]
    )
    assert set(primary) == {"basis", "weight", "risk_ood_mask"}


def test_runtime_suite_validation_rejects_regeneration_or_overlap_changes() -> None:
    root = Path(__file__).resolve().parents[1]
    payload, _ = load_frozen_suite(root / "benchmarks/p1_validation_v1.json")
    validate_p1_runtime_suite(payload, root)

    changed = json.loads(json.dumps(payload))
    earlier, _ = load_frozen_suite(root / "benchmarks/v2_validation.json")
    changed["points"][0] = earlier["points"][0]
    with pytest.raises(ValueError, match="overlap|regeneration"):
        validate_p1_runtime_suite(changed, root)


def test_p1_checkpoint_inventory_contains_exact_three_methods() -> None:
    root = Path(__file__).resolve().parents[1]
    archive = root / "artifacts/p5-evidence-20260801-092048.tar.gz"
    sidecar = archive.with_suffix(archive.suffix + ".sha256")

    inventory = inventory_p1_checkpoints(archive, sidecar)

    assert len(inventory) == 18
    assert {
        (row["method"], row["family"], row["seed"]) for row in inventory
    } == {
        (method, family, seed)
        for method in ("p5_anchor", "p5_long_anchor", "p5_static_low_rom")
        for family in P1_FAMILIES
        for seed in (42, 137, 251)
    }


def test_p1_aggregation_builds_six_paired_comparisons_and_go_summary() -> None:
    rows: list[dict[str, object]] = []
    for family in P1_FAMILIES:
        for seed_index, seed in enumerate((42, 137, 251)):
            for split in ("near_cluster", "gap_scan"):
                identity = f"{family}-{seed}-{split}"
                anchor_error = (
                    0.08
                    if split == "near_cluster" and seed_index < 1
                    else 0.10
                )
                errors = {
                    "p5_anchor": anchor_error,
                    "p5_long_anchor": 0.10 if split == "near_cluster" else 0.105,
                    "p5_static_low_rom": 0.11 if split == "near_cluster" else 0.10,
                    "p1_hard_select": 0.095 if split == "near_cluster" else 0.10,
                    "p1_no_risk_half_blend": 0.094 if split == "near_cluster" else 0.10,
                    "p1_parameter_only_chordal": 0.092 if split == "near_cluster" else 0.10,
                    "p1_risk_chordal": 0.09 if split == "near_cluster" else 0.099,
                    "p1_risk_chordal_pwe5": 0.08 if split == "near_cluster" else 0.09,
                    "oracle_min_anchor_rom": min(anchor_error, 0.11 if split == "near_cluster" else 0.10),
                }
                for method in P1_METHODS:
                    rows.append(
                        {
                            "method": method,
                            "family": family,
                            "seed": seed,
                            "split": split,
                            "point_id": identity,
                            "projector_error": errors[method],
                            "orthogonality_error": 1e-6,
                            "risk_score": 0.9 if split == "near_cluster" else 0.1,
                            "parameter_risk_score": (
                                0.8
                                if split == "near_cluster" and seed_index != 2
                                else 0.2
                            ),
                            "rom_weight": 0.5,
                            "pwe_used": method == "p1_risk_chordal_pwe5",
                            "risk_ood": False,
                            "reference_only": method == "oracle_min_anchor_rom",
                        }
                    )

    summary = aggregate_p1_rows(
        rows,
        anchor_latency_ms=1.0,
        p1_latency_ms=2.0,
        expected_points_per_method=12,
    )

    assert summary["engineering_pass"] is True
    assert summary["paired_near_comparisons"] == 6
    assert summary["paired_near_wins_vs_long_anchor"] == 6
    assert summary["p1_risk_chordal_pwe_fraction"] == 0.0
    assert summary["p5_static_low_rom_unsafe_rate_vs_anchor"] == pytest.approx(0.5)
    assert summary["p1_risk_chordal_unsafe_rate_vs_anchor"] == pytest.approx(1.0 / 6.0)


def test_tiny_p1_point_evaluation_produces_complete_method_rows() -> None:
    import torch
    from torch import nn

    from block_kyfan_pinn.reference import uniform_grid

    class TinyPeriodicModel(nn.Module):
        def __init__(self, phase: float) -> None:
            super().__init__()
            self.phase = phase

        def forward(self, coordinates: torch.Tensor, parameters: torch.Tensor) -> torch.Tensor:
            x, y = coordinates.unbind(-1)
            phase = self.phase + 0.05 * parameters[:, :1]
            first = torch.stack((torch.cos(x + phase), torch.sin(x + phase)), dim=-1)
            second = torch.stack((torch.cos(y - phase), torch.sin(y - phase)), dim=-1)
            return torch.stack((first, second), dim=2)

    root = Path(__file__).resolve().parents[1]
    p0_archive = root / "artifacts/risk-development-evidence-20260824-092630.tar.gz"
    calibration = load_p0_calibration(
        p0_archive, p0_archive.with_suffix(p0_archive.suffix + ".sha256")
    )
    thresholds = frozen_thresholds(calibration["model"], calibration["rows"])
    grid = uniform_grid(7).unsqueeze(0)
    reference_basis = periodic_mgs(
        TinyPeriodicModel(0.0)(grid, torch.tensor([[0.33, 0.33, 0.5, 0.0]]))
    )[0]
    reference = {"basis": torch.cat((reference_basis, reference_basis[:, :1]), dim=1)}
    point = {
        "id": "tiny-harmonic",
        "family": "harmonic_honeycomb",
        "split": "near_cluster",
        "parameters": [0.33, 0.33, 0.5, 0.0],
    }

    rows, timing = evaluate_p1_point(
        TinyPeriodicModel(0.01),
        TinyPeriodicModel(0.02),
        TinyPeriodicModel(0.015),
        point,
        reference,
        p0_model=calibration["model"],
        thresholds=thresholds,
        seed=42,
        device=torch.device("cpu"),
        grid_side=7,
    )

    assert [row["method"] for row in rows] == list(P1_METHODS)
    assert all(row["point_id"] == "tiny-harmonic" for row in rows)
    assert all(float(row["orthogonality_error"]) < 1e-5 for row in rows)
    assert all(float(row["projector_error"]) >= 0.0 for row in rows)
    assert next(row for row in rows if row["method"] == "p1_risk_chordal")["pwe_used"] is False
    assert timing["anchor_latency_ms"] > 0.0
    assert timing["p1_latency_ms"] > timing["anchor_latency_ms"]


def test_p1_parser_keeps_smoke_and_formal_outputs_separate() -> None:
    parser = build_p1_parser()
    smoke = parser.parse_args(["--device", "cpu", "--smoke-only", "--allow-dirty"])
    formal = parser.parse_args(["--device", "rocm"])

    assert smoke.smoke_only is True
    assert smoke.output_dir.as_posix() == "results/p1_pilot"
    assert formal.smoke_only is False
    assert formal.reference_cache.as_posix() == "data/p1_validation_v1_references.pt"
    assert formal.latency_warmup == 10
    assert formal.latency_repeats == 100


def test_accelerator_peak_memory_is_zero_on_cpu() -> None:
    import torch

    assert accelerator_peak_memory(torch.device("cpu")) == 0


def test_environment_timestamp_is_reused_when_runtime_is_unchanged(
    tmp_path: Path,
) -> None:
    path = tmp_path / "environment.json"
    first = {"timestamp_utc": "first", "torch": "2.11", "hip": "7.2"}
    second = {"timestamp_utc": "second", "torch": "2.11", "hip": "7.2"}

    assert prepare_environment(path, first) == first
    assert prepare_environment(path, second) == first
    assert json.loads(path.read_text())["timestamp_utc"] == "first"


def test_tiny_latency_benchmark_reports_primary_and_anchor_distribution() -> None:
    import torch
    from torch import nn

    class TinyLatencyModel(nn.Module):
        def __init__(self, phase: float) -> None:
            super().__init__()
            self.phase = phase

        def forward(self, coordinates: torch.Tensor, parameters: torch.Tensor) -> torch.Tensor:
            x, y = coordinates.unbind(-1)
            first = torch.stack((torch.cos(x + self.phase), torch.sin(x + self.phase)), -1)
            second = torch.stack((torch.cos(y - self.phase), torch.sin(y - self.phase)), -1)
            return torch.stack((first, second), dim=2)

    root = Path(__file__).resolve().parents[1]
    archive = root / "artifacts/risk-development-evidence-20260824-092630.tar.gz"
    calibration = load_p0_calibration(
        archive, archive.with_suffix(archive.suffix + ".sha256")
    )
    thresholds = frozen_thresholds(calibration["model"], calibration["rows"])
    point = {
        "id": "latency-tiny",
        "family": "harmonic_honeycomb",
        "split": "iid_hidden",
        "parameters": [0.33, 0.34, 0.5, 0.0],
    }

    timing = benchmark_neural_latency(
        TinyLatencyModel(0.01),
        TinyLatencyModel(0.02),
        point,
        p0_model=calibration["model"],
        thresholds=thresholds,
        device=torch.device("cpu"),
        grid_side=7,
        warmup=1,
        repeats=2,
    )

    assert timing["warmup"] == 1
    assert timing["repeats"] == 2
    assert timing["anchor_latency_ms"] > 0.0
    assert timing["p1_latency_ms"] > timing["anchor_latency_ms"]
    assert timing["p1_p95_ms"] >= timing["p1_p50_ms"]
    assert timing["peak_accelerator_memory_bytes"] == 0


def test_p1_unit_resume_requires_hash_provenance_and_complete_methods(
    tmp_path: Path,
) -> None:
    path = tmp_path / "harmonic_seed42.json"
    provenance = {
        "suite_sha256": "a" * 64,
        "reference_sha256": "b" * 64,
        "p0_archive_sha256": "c" * 64,
        "p5_archive_sha256": "d" * 64,
        "source_fingerprint": "e" * 64,
        "threshold_sha256": "f" * 64,
        "checkpoint_sha256": {method: method for method in ("p5_anchor", "p5_long_anchor", "p5_static_low_rom")},
    }
    rows = [
        {
            "method": method,
            "family": "harmonic_honeycomb",
            "seed": 42,
            "split": "near_cluster",
            "point_id": "p1-point-000",
            "projector_error": 0.1,
            "orthogonality_error": 1e-7,
            "risk_score": 0.4,
            "parameter_risk_score": 0.3,
            "rom_weight": 0.5,
            "pwe_used": False,
            "risk_ood": False,
            "reference_only": method == "oracle_min_anchor_rom",
        }
        for method in P1_METHODS
    ]
    timing = {"anchor_latency_ms": 1.0, "p1_latency_ms": 2.0}

    _write_p1_unit(path, provenance, rows, timing)
    loaded = _load_p1_unit(
        path,
        provenance,
        expected_family="harmonic_honeycomb",
        expected_seed=42,
        expected_point_ids={"p1-point-000"},
    )

    assert loaded == {"rows": rows, "timing": timing}
    path.write_text(path.read_text().replace('"projector_error": 0.1', '"projector_error": 0.2', 1))
    with pytest.raises(ValueError, match="SHA-256"):
        _load_p1_unit(
            path,
            provenance,
            expected_family="harmonic_honeycomb",
            expected_seed=42,
            expected_point_ids={"p1-point-000"},
        )


def test_p1_evidence_is_reopened_and_fully_audited(tmp_path: Path) -> None:
    from scripts.run_p4_executor import write_evidence_bundle

    p0 = tmp_path / "artifacts/risk-development-evidence-20260824-092630.tar.gz"
    p5 = tmp_path / "artifacts/p5-evidence-20260801-092048.tar.gz"
    p0_sidecar = p0.with_suffix(p0.suffix + ".sha256")
    p5_sidecar = p5.with_suffix(p5.suffix + ".sha256")
    gate = tmp_path / "results/p1_pilot/gate.json"
    for path, payload in (
        (p0, b"p0"),
        (p5, b"p5"),
        (p0_sidecar, b"p0-sidecar"),
        (p5_sidecar, b"p5-sidecar"),
        (gate, b'{"pilot_go": false}'),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    archive, sidecar, _ = write_evidence_bundle(
        root=tmp_path,
        include_paths=(p0, p0_sidecar, p5, p5_sidecar, gate),
        output_dir=tmp_path / "artifacts",
        label="unit",
        prefix="p1-pilot-evidence",
        manifest_name="p1-pilot-evidence-manifest.json",
    )

    report = audit_p1_evidence(archive, sidecar)

    assert report["audit_pass"] is True
    assert report["member_count"] == 5
    p0.write_bytes(b"changed-after-package")
    assert audit_p1_evidence(archive, sidecar)["audit_pass"] is True

"""Protocol tests for the P2 neural-augmented Galerkin probe."""

from __future__ import annotations

import json

import pytest

from scripts.probe_p2_refinement import (
    audit_p2_evidence,
    build_parser,
    build_probe_gate,
    select_probe_points,
    validate_selection_payload,
)


def test_probe_selection_uses_worst_near_and_largest_gap_advantage() -> None:
    rows: list[dict[str, object]] = []
    for family in ("harmonic_honeycomb", "gaussian_honeycomb"):
        for seed in (42, 137, 251):
            for index, value in enumerate((0.1, 0.2, 0.3)):
                point = f"{family}-near-{index}"
                rows.append(
                    {
                        "method": "p5_long_anchor",
                        "family": family,
                        "seed": seed,
                        "split": "near_cluster",
                        "point_id": point,
                        "projector_error": value,
                    }
                )
            for index, advantage in enumerate((0.01, 0.04, 0.02)):
                point = f"{family}-gap-{index}"
                rows.extend(
                    (
                        {
                            "method": "p5_anchor",
                            "family": family,
                            "seed": seed,
                            "split": "gap_scan",
                            "point_id": point,
                            "projector_error": 0.1,
                        },
                        {
                            "method": "p5_long_anchor",
                            "family": family,
                            "seed": seed,
                            "split": "gap_scan",
                            "point_id": point,
                            "projector_error": 0.1 + advantage,
                        },
                    )
                )

    selected = select_probe_points(rows, per_split=2)

    for family in ("harmonic_honeycomb", "gaussian_honeycomb"):
        assert selected[family]["near_cluster"] == [
            f"{family}-near-2",
            f"{family}-near-1",
        ]
        assert selected[family]["gap_scan"] == [
            f"{family}-gap-1",
            f"{family}-gap-2",
        ]

    validate_selection_payload(selected, rows)
    changed = json.loads(json.dumps(selected))
    changed["harmonic_honeycomb"]["near_cluster"].reverse()
    with pytest.raises(ValueError, match="deterministic"):
        validate_selection_payload(changed, rows)


def _passing_summary() -> dict[str, object]:
    return {
        "engineering_pass": True,
        "p2_shell2_outer_near_mean": 0.095,
        "p5_long_anchor_near_mean": 0.100,
        "p2_shell2_outer_gap_mean": 0.101,
        "p5_anchor_gap_mean": 0.100,
        "family_near": {
            "harmonic_honeycomb": {"p2_shell2_outer": 0.08, "p5_long_anchor": 0.09},
            "gaussian_honeycomb": {"p2_shell2_outer": 0.11, "p5_long_anchor": 0.12},
        },
        "paired_near_wins": 5,
        "paired_near_comparisons": 6,
        "p2_shell2_outer_overall_mean": 0.10,
        "fourier_only_outer2_plus_anchor_overall_mean": 0.13,
        "maximum_orthogonality_error": 1e-6,
        "latency_ratio": 4.0,
    }


def test_probe_gate_requires_every_predeclared_condition() -> None:
    assert build_probe_gate(_passing_summary())["probe_go"] is True


def test_probe_parser_freezes_latency_policy() -> None:
    args = build_parser().parse_args(["--run", "--device", "cuda"])

    assert args.latency_warmup == 10
    assert args.latency_repeats == 100


def test_p2_evidence_audit_reopens_manifest_and_required_inputs(tmp_path) -> None:
    from pathlib import Path

    from scripts.run_p4_executor import write_evidence_bundle

    paths = [
        Path("artifacts/p1-pilot-evidence-20260824-113650.tar.gz"),
        Path("artifacts/p1-pilot-evidence-20260824-113650.tar.gz.sha256"),
        Path("artifacts/p5-evidence-20260801-092048.tar.gz"),
        Path("artifacts/p5-evidence-20260801-092048.tar.gz.sha256"),
        Path("results/p2_refinement_probe/gate.json"),
        Path("results/p2_refinement_probe/selection.json"),
        Path("results/p2_refinement_probe/selection.sha256"),
        Path("data/p1_validation_v1_references.pt"),
        Path("data/p1_validation_v1_references.sha256"),
    ]
    for relative in paths:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.as_posix().encode())
    archive, sidecar, _ = write_evidence_bundle(
        root=tmp_path,
        include_paths=tuple(tmp_path / path for path in paths),
        output_dir=tmp_path / "artifacts",
        label="unit",
        prefix="p2-refinement-probe-evidence",
        manifest_name="p2-refinement-probe-evidence-manifest.json",
    )

    report = audit_p2_evidence(archive, sidecar)

    assert report["audit_pass"] is True
    assert report["member_count"] == len(paths)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("engineering_pass", False),
        ("p2_shell2_outer_near_mean", 0.099),
        ("p2_shell2_outer_gap_mean", 0.103),
        ("paired_near_wins", 4),
        ("p2_shell2_outer_overall_mean", 0.14),
        ("maximum_orthogonality_error", 1e-3),
        ("latency_ratio", 5.1),
    ],
)
def test_each_probe_requirement_forces_stop(key: str, value: object) -> None:
    summary = _passing_summary()
    summary[key] = value
    assert build_probe_gate(summary)["probe_go"] is False

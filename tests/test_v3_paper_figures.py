"""Tests for the V3 formal-result figure pipeline."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from scripts.generate_v3_paper_figures import (
    EXPECTED_FORMAL_EVIDENCE_SHA256,
    METHOD_LABELS,
    paired_point_means,
    read_rows,
    validate_identity_matrix,
    validate_inputs,
)

ROOT = Path(__file__).resolve().parents[1]


def test_formal_rows_have_the_frozen_identity_matrix() -> None:
    rows = read_rows(ROOT / "paper/v3_formal/rows.csv")
    validate_identity_matrix(rows)
    assert len(rows) == 5_280
    assert len({str(row["point_id"]) for row in rows}) == 160
    assert {str(row["method"]) for row in rows} == set(METHOD_LABELS)


def test_identity_validator_rejects_a_missing_row() -> None:
    rows = read_rows(ROOT / "paper/v3_formal/rows.csv")
    with pytest.raises(ValueError, match="5,280"):
        validate_identity_matrix(rows[:-1])


def test_paired_point_means_preserve_all_formal_points() -> None:
    rows = read_rows(ROOT / "paper/v3_formal/rows.csv")
    paired = paired_point_means(
        rows, candidate="sr_routed25", baseline="kinetic_fourier25"
    )
    assert len(paired) == 160
    assert all(row["candidate_error"] >= 0.0 for row in paired)
    assert all(row["baseline_error"] >= 0.0 for row in paired)


def test_evidence_sidecar_is_the_frozen_formal_digest() -> None:
    sidecar = (
        ROOT / "artifacts/v3-symmetry-formal-evidence.tar.gz.sha256"
    ).read_text()
    assert sidecar.split()[0] == EXPECTED_FORMAL_EVIDENCE_SHA256


def test_figure_pipeline_rejects_a_local_result_not_in_the_archive(
    tmp_path: Path,
) -> None:
    result_dir = tmp_path / "formal-results"
    result_dir.mkdir()
    for name in (
        "rows.csv",
        "summary.json",
        "gate.json",
        "provenance.json",
        "evidence-manifest.json",
    ):
        shutil.copy2(ROOT / "paper/v3_formal" / name, result_dir / name)
    with (result_dir / "rows.csv").open("a") as handle:
        handle.write("\n")

    rows = read_rows(result_dir / "rows.csv")
    evidence = ROOT / "artifacts/v3-symmetry-formal-evidence.tar.gz"
    with pytest.raises(ValueError, match="differs from archive: rows.csv"):
        validate_inputs(result_dir, evidence, rows)

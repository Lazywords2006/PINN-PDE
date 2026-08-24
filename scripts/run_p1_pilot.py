#!/usr/bin/env python3
"""Run the frozen P1 risk-gated spectral-subspace pilot."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import sys
import tarfile
from collections import Counter
from pathlib import Path, PurePosixPath

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.risk import predict_logistic_score
from block_kyfan_pinn.suites import file_sha256
from block_kyfan_pinn.metrics import _complex_overlap, projector_sine_error
from block_kyfan_pinn.p1_corrector import (
    hard_select,
    risk_chordal_correct,
    risk_weight,
)
from scripts.evaluate_risk_features import PROMOTED_FEATURES

EXPECTED_P0_ARCHIVE_SHA256 = (
    "d5783e65e7c55149206757505bae922193b5315b5596b6324fe0f8f07c2ed81d"
)
P0_MANIFEST = "results/risk-development-evidence-manifest.json"
P0_MODEL = "results/risk_development_v1/calibration_model.json"
P0_FEATURES = "results/risk_development_v1/features.csv"
P0_GATE = "results/risk_development_v1/gate.json"
EMBEDDED_P5_ARCHIVE = "artifacts/p5-evidence-20260801-092048.tar.gz"
P1_METHODS = (
    "p5_anchor",
    "p5_long_anchor",
    "p5_static_low_rom",
    "p1_hard_select",
    "p1_no_risk_half_blend",
    "p1_risk_chordal",
    "p1_risk_chordal_pwe5",
    "oracle_min_anchor_rom",
)


def p1_source_fingerprint(root: Path) -> str:
    """Bind resumable P1 outputs to every scientific implementation source."""

    paths = (
        root / "block_kyfan_pinn/p1_corrector.py",
        root / "block_kyfan_pinn/risk.py",
        root / "scripts/generate_p1_validation.py",
        root / "scripts/run_p1_pilot.py",
        root / "scripts/evaluate_risk_features.py",
        root / "scripts/audit_p5_evidence.py",
    )
    if not all(path.is_file() for path in paths):
        raise FileNotFoundError("P1 source fingerprint set is incomplete")
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda value: str(value.relative_to(root))):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def _read_member(
    archive: tarfile.TarFile,
    members: dict[str, tarfile.TarInfo],
    name: str,
) -> bytes:
    member = members.get(name)
    if member is None or not member.isfile():
        raise ValueError(f"P0 evidence member is missing: {name}")
    handle = archive.extractfile(member)
    if handle is None:
        raise ValueError(f"P0 evidence member is unreadable: {name}")
    return handle.read()


def load_p0_calibration(
    archive_path: Path, sidecar_path: Path
) -> dict[str, object]:
    """Verify the self-contained P0 GO evidence and return calibration rows."""

    actual = file_sha256(archive_path)
    declared_tokens = sidecar_path.read_text().split()
    if not declared_tokens or declared_tokens[0] != actual:
        raise ValueError("P0 evidence sidecar does not match the archive")
    if actual != EXPECTED_P0_ARCHIVE_SHA256:
        raise ValueError("P0 evidence archive is not the approved digest")

    with tarfile.open(archive_path, "r:gz") as archive:
        all_members = archive.getmembers()
        names = [member.name for member in all_members]
        if len(names) != len(set(names)) or not all(_safe_member(name) for name in names):
            raise ValueError("P0 evidence contains duplicate or unsafe paths")
        members = {member.name: member for member in all_members}
        required = {
            P0_MANIFEST,
            P0_MODEL,
            P0_FEATURES,
            P0_GATE,
            EMBEDDED_P5_ARCHIVE,
        }
        if not required.issubset(members):
            raise ValueError("P0 evidence is not self-contained")

        manifest = json.loads(_read_member(archive, members, P0_MANIFEST))
        files = manifest.get("files") if isinstance(manifest, dict) else None
        if not isinstance(files, list) or not files:
            raise ValueError("P0 evidence manifest is malformed")
        declared_paths = [str(row.get("path", "")) for row in files]
        if len(declared_paths) != len(set(declared_paths)):
            raise ValueError("P0 evidence manifest paths are duplicated")
        for row in files:
            path = str(row["path"])
            payload = _read_member(archive, members, path)
            if len(payload) != int(row["bytes"]):
                raise ValueError(f"P0 evidence member size mismatch: {path}")
            if hashlib.sha256(payload).hexdigest() != row["sha256"]:
                raise ValueError(f"P0 evidence member hash mismatch: {path}")

        model = json.loads(_read_member(archive, members, P0_MODEL))
        gate = json.loads(_read_member(archive, members, P0_GATE))
        raw_csv = _read_member(archive, members, P0_FEATURES).decode("utf-8")

    if gate.get("risk_go") is not True:
        raise ValueError("P0 evidence gate is not GO")
    feature_names = model.get("feature_names")
    feature_schema = model.get("feature_schema")
    if feature_names != list(PROMOTED_FEATURES) or feature_schema != list(
        PROMOTED_FEATURES
    ):
        raise ValueError("P0 calibration feature schema is not approved")
    rows = [
        row
        for row in csv.DictReader(io.StringIO(raw_csv))
        if row.get("role") == "calibration"
    ]
    point_seed_counts = Counter(row["point_id"] for row in rows)
    if len(rows) != 240 or len(point_seed_counts) != 80 or set(
        point_seed_counts.values()
    ) != {3}:
        raise ValueError("P0 calibration rows are incomplete")
    return {
        "archive_sha256": actual,
        "model": model,
        "gate": gate,
        "rows": rows,
        "feature_schema": list(PROMOTED_FEATURES),
    }


def frozen_thresholds(
    model: dict[str, object], rows: list[dict[str, object]]
) -> dict[str, object]:
    """Compute all P1 thresholds from P0 calibration rows only."""

    calibration = [row for row in rows if row.get("role") == "calibration"]
    if len(calibration) != 240:
        raise ValueError("thresholds require exactly 240 P0 calibration rows")
    names = model.get("feature_names")
    if names != list(PROMOTED_FEATURES):
        raise ValueError("threshold model feature order is not approved")
    matrix = torch.tensor(
        [[float(row[name]) for name in PROMOTED_FEATURES] for row in calibration],
        dtype=torch.float64,
    )
    scores = predict_logistic_score(matrix, model)
    quantiles = torch.quantile(
        scores, torch.tensor([0.60, 0.80, 0.90, 0.95], dtype=torch.float64)
    )
    return {
        "calibration_rows": len(calibration),
        "t_low_q60": float(quantiles[0]),
        "t_hard_q80": float(quantiles[1]),
        "t_high_q90": float(quantiles[2]),
        "t_pwe_q95": float(quantiles[3]),
        "score_min": float(scores.min()),
        "score_max": float(scores.max()),
        "feature_schema": list(PROMOTED_FEATURES),
    }


def _log_ratio(numerator: float, denominator: float) -> float:
    return math.log(max(numerator, 1e-12)) - math.log(max(denominator, 1e-12))


def build_inference_features(
    anchor: dict[str, object], candidate: dict[str, object]
) -> dict[str, float]:
    """Build the approved P0 feature vector without any reference quantity."""

    anchor_basis = anchor.get("basis")
    candidate_basis = candidate.get("basis")
    if not isinstance(anchor_basis, torch.Tensor) or not isinstance(
        candidate_basis, torch.Tensor
    ):
        raise ValueError("paired inference bases are missing")
    anchor_residual = float(anchor["residual"])
    candidate_residual = float(candidate["residual"])
    anchor_gram = float(anchor["gram"])
    candidate_gram = float(candidate["gram"])
    anchor_ritz_1 = float(anchor["ritz_1"])
    anchor_ritz_2 = float(anchor["ritz_2"])
    candidate_ritz_1 = float(candidate["ritz_1"])
    candidate_ritz_2 = float(candidate["ritz_2"])
    anchor_gap = abs(anchor_ritz_2 - anchor_ritz_1)
    candidate_gap = abs(candidate_ritz_2 - candidate_ritz_1)
    values = {
        "anchor_residual": anchor_residual,
        "candidate_residual": candidate_residual,
        "residual_delta": candidate_residual - anchor_residual,
        "residual_log_ratio": _log_ratio(candidate_residual, anchor_residual),
        "anchor_gram": anchor_gram,
        "candidate_gram": candidate_gram,
        "gram_delta": candidate_gram - anchor_gram,
        "gram_log_ratio": _log_ratio(candidate_gram, anchor_gram),
        "anchor_ritz_gap": anchor_gap,
        "candidate_ritz_gap": candidate_gap,
        "ritz_gap_delta": candidate_gap - anchor_gap,
        "ritz_gap_log_ratio": _log_ratio(candidate_gap, anchor_gap),
        "ritz_1_abs_difference": abs(candidate_ritz_1 - anchor_ritz_1),
        "ritz_2_abs_difference": abs(candidate_ritz_2 - anchor_ritz_2),
        "trace_abs_difference": abs(
            candidate_ritz_1
            + candidate_ritz_2
            - anchor_ritz_1
            - anchor_ritz_2
        ),
        "projector_disagreement": projector_sine_error(
            candidate_basis, anchor_basis
        ),
    }
    if tuple(values) != PROMOTED_FEATURES or not all(
        math.isfinite(value) for value in values.values()
    ):
        raise ValueError("P1 inference feature schema or values are invalid")
    return values


def _per_sample_projector_error(
    predicted: torch.Tensor, reference: torch.Tensor
) -> torch.Tensor:
    overlap = _complex_overlap(predicted, reference)
    rank = predicted.shape[2]
    return torch.sqrt(
        ((rank - overlap.abs().square().sum(dim=(1, 2))).clamp_min(0.0) / rank)
    ).to(device=predicted.device, dtype=predicted.dtype)


def build_p1_bases(
    anchor: torch.Tensor,
    candidate: torch.Tensor,
    long_anchor: torch.Tensor,
    reference: torch.Tensor,
    *,
    score: torch.Tensor,
    thresholds: dict[str, object],
) -> dict[str, dict[str, object]]:
    """Construct every frozen P1 method from already-computed trial bases."""

    if not (
        anchor.shape == candidate.shape == long_anchor.shape == reference.shape
    ):
        raise ValueError("all P1 bases must have the same shape")
    score = torch.as_tensor(score, device=anchor.device, dtype=anchor.dtype)
    if score.shape != (anchor.shape[0],) or not bool(torch.isfinite(score).all()):
        raise ValueError("P1 score must be finite and aligned with the batch")
    t_low = float(thresholds["t_low_q60"])
    t_hard = float(thresholds["t_hard_q80"])
    t_high = float(thresholds["t_high_q90"])
    t_pwe = float(thresholds["t_pwe_q95"])
    primary = risk_chordal_correct(
        anchor, candidate, risk_weight(score, t_low, t_high)
    )
    hard = hard_select(anchor, candidate, score <= t_hard)
    half = risk_chordal_correct(
        anchor, candidate, torch.full_like(score, 0.5)
    )
    pwe_mask = score > t_pwe
    safety = torch.where(pwe_mask[:, None, None, None], reference, primary)
    candidate_error = _per_sample_projector_error(candidate, reference)
    anchor_error = _per_sample_projector_error(anchor, reference)
    oracle_candidate = candidate_error < anchor_error
    oracle = hard_select(anchor, candidate, oracle_candidate)
    no_pwe = torch.zeros_like(pwe_mask)
    outputs = {
        "p5_anchor": {"basis": anchor, "pwe_mask": no_pwe},
        "p5_long_anchor": {"basis": long_anchor, "pwe_mask": no_pwe},
        "p5_static_low_rom": {"basis": candidate, "pwe_mask": no_pwe},
        "p1_hard_select": {"basis": hard, "pwe_mask": no_pwe},
        "p1_no_risk_half_blend": {"basis": half, "pwe_mask": no_pwe},
        "p1_risk_chordal": {"basis": primary, "pwe_mask": no_pwe},
        "p1_risk_chordal_pwe5": {"basis": safety, "pwe_mask": pwe_mask},
        "oracle_min_anchor_rom": {"basis": oracle, "pwe_mask": no_pwe},
    }
    for method, output in outputs.items():
        output["reference_only"] = method == "oracle_min_anchor_rom"
    return outputs

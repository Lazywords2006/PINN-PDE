#!/usr/bin/env python3
"""Run the frozen P1 risk-gated spectral-subspace pilot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
import tarfile
import time
from collections import Counter
from pathlib import Path, PurePosixPath

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.device import select_device
from block_kyfan_pinn.metrics import (
    _complex_overlap,
    orthogonality_error,
    projector_sine_error,
)
from block_kyfan_pinn.p1_corrector import (
    build_p1_gate,
    hard_select,
    risk_chordal_correct,
    risk_weight,
)
from block_kyfan_pinn.physics import (
    apply_hamiltonian,
    periodic_mgs,
    projected_residual_rms,
)
from block_kyfan_pinn.reference import uniform_grid
from block_kyfan_pinn.risk import (
    binary_auroc,
    fit_logistic_score,
    predict_logistic_score,
)
from block_kyfan_pinn.suites import file_sha256, load_frozen_suite, write_frozen_suite
from scripts.audit_p5_evidence import audit_p5_evidence
from scripts.evaluate_risk_features import (
    EXPECTED_P5_ARCHIVE_SHA256,
    PROMOTED_FEATURES,
    _gram_condition,
    _ritz_values,
    load_p5_checkpoint,
)
from scripts.generate_p1_validation import (
    build_p1_reference_cache,
    build_p1_suite_payload,
    generate_p1_validation_suite,
    validate_p1_suite_disjointness,
)
from scripts.generate_v2_assets import TRAINING_BOUNDS
from scripts.run_p3_pilot import _load_reference_cache
from scripts.run_p4_executor import _environment, write_evidence_bundle

EXPECTED_P0_ARCHIVE_SHA256 = (
    "d5783e65e7c55149206757505bae922193b5315b5596b6324fe0f8f07c2ed81d"
)
P0_MANIFEST = "results/risk-development-evidence-manifest.json"
P0_MODEL = "results/risk_development_v1/calibration_model.json"
P0_FEATURES = "results/risk_development_v1/features.csv"
P0_GATE = "results/risk_development_v1/gate.json"
P0_SUITE = "benchmarks/risk_development_v1.json"
EMBEDDED_P5_ARCHIVE = "artifacts/p5-evidence-20260801-092048.tar.gz"
P1_METHODS = (
    "p5_anchor",
    "p5_long_anchor",
    "p5_static_low_rom",
    "p1_hard_select",
    "p1_no_risk_half_blend",
    "p1_parameter_only_chordal",
    "p1_risk_chordal",
    "p1_risk_chordal_pwe5",
    "oracle_min_anchor_rom",
)
P1_CHECKPOINT_METHODS = (
    "p5_anchor",
    "p5_long_anchor",
    "p5_static_low_rom",
)
P1_FAMILIES = ("harmonic_honeycomb", "gaussian_honeycomb")
P1_SEEDS = (42, 137, 251)


def p1_source_fingerprint(root: Path) -> str:
    """Bind resumable P1 outputs to every scientific implementation source."""

    paths = tuple(sorted((root / "block_kyfan_pinn").rglob("*.py"))) + (
        root / "scripts/audit_p5_evidence.py",
        root / "scripts/evaluate_risk_features.py",
        root / "scripts/generate_p1_validation.py",
        root / "scripts/generate_risk_development.py",
        root / "scripts/generate_v2_assets.py",
        root / "scripts/run_p1_pilot.py",
        root / "scripts/run_p3_pilot.py",
        root / "scripts/run_p4_executor.py",
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


def audit_p1_evidence(
    archive_path: Path, sidecar_path: Path
) -> dict[str, object]:
    """Reopen and independently verify a complete P1 evidence bundle."""

    errors: list[str] = []
    actual = file_sha256(archive_path)
    tokens = sidecar_path.read_text().split() if sidecar_path.is_file() else []
    if not tokens or tokens[0] != actual:
        errors.append("outer sidecar mismatch")
    member_count = 0
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            all_members = archive.getmembers()
            names = [member.name for member in all_members]
            if len(names) != len(set(names)):
                errors.append("duplicate archive members")
            if not all(_safe_member(name) for name in names):
                errors.append("unsafe archive member")
            members = {member.name: member for member in all_members}
            manifest_name = "results/p1-pilot-evidence-manifest.json"
            manifest = json.loads(_read_member(archive, members, manifest_name))
            files = manifest.get("files") if isinstance(manifest, dict) else None
            if not isinstance(files, list) or not files:
                errors.append("manifest is malformed")
                files = []
            member_count = len(files)
            declared_paths = [str(row.get("path", "")) for row in files]
            declared = set(declared_paths)
            if len(declared_paths) != len(declared):
                errors.append("manifest paths are duplicated")
            actual_files = {name for name, member in members.items() if member.isfile()}
            if actual_files != declared | {manifest_name}:
                errors.append("archive contains missing or undeclared files")
            required = {
                "artifacts/risk-development-evidence-20260824-092630.tar.gz",
                "artifacts/risk-development-evidence-20260824-092630.tar.gz.sha256",
                "artifacts/p5-evidence-20260801-092048.tar.gz",
                "artifacts/p5-evidence-20260801-092048.tar.gz.sha256",
                "results/p1_pilot/gate.json",
            }
            if not required.issubset(declared):
                errors.append("required P0/P5/P1 evidence members are missing")
            for row in files:
                path = str(row.get("path", ""))
                payload = _read_member(archive, members, path)
                if len(payload) != int(row.get("bytes", -1)):
                    errors.append(f"member size mismatch: {path}")
                if hashlib.sha256(payload).hexdigest() != row.get("sha256"):
                    errors.append(f"member SHA-256 mismatch: {path}")
    except (OSError, tarfile.TarError, ValueError, KeyError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "audit_pass": not errors,
        "archive_sha256": actual,
        "member_count": member_count,
        "errors": errors,
    }


def inventory_p1_checkpoints(
    archive_path: Path, sidecar_path: Path
) -> list[dict[str, object]]:
    """Return the exact 18 audited P5 final checkpoints permitted by P1."""

    report = audit_p5_evidence(archive_path, sidecar_path)
    if report.get("audit_pass") is not True:
        raise ValueError("P5 evidence audit failed")
    if report.get("archive_sha256") != EXPECTED_P5_ARCHIVE_SHA256:
        raise ValueError("P5 evidence archive is not the approved digest")
    rows: list[dict[str, object]] = []
    with tarfile.open(archive_path, "r:gz") as archive:
        all_members = archive.getmembers()
        names = [member.name for member in all_members]
        if len(names) != len(set(names)) or not all(_safe_member(name) for name in names):
            raise ValueError("P5 evidence contains duplicate or unsafe paths")
        members = {member.name: member for member in all_members}
        result_names = sorted(
            name
            for name, member in members.items()
            if member.isfile()
            and name.startswith("results/p5_promotion/")
            and name.endswith("/result.json")
        )
        for result_name in result_names:
            result = json.loads(_read_member(archive, members, result_name))
            config = result.get("config")
            if not isinstance(config, dict):
                raise TypeError(f"P5 result config is missing: {result_name}")
            method = str(config.get("method"))
            if method not in P1_CHECKPOINT_METHODS:
                continue
            family = str(config.get("potential_family"))
            seed = int(config.get("seed", -1))
            if family not in P1_FAMILIES or seed not in P1_SEEDS:
                raise ValueError("P1 checkpoint identity is unexpected")
            run_root = result_name.rsplit("/", 1)[0]
            checkpoint_name = f"{run_root}/final.pt"
            payload = _read_member(archive, members, checkpoint_name)
            digest = hashlib.sha256(payload).hexdigest()
            if digest != result.get("final_checkpoint_sha256"):
                raise ValueError("P1 checkpoint hash does not match its P5 result")
            if result.get("status") != "PASS":
                raise ValueError("P1 checkpoint source run is incomplete")
            rows.append(
                {
                    "method": method,
                    "family": family,
                    "seed": seed,
                    "checkpoint_member": checkpoint_name,
                    "result_member": result_name,
                    "checkpoint_sha256": digest,
                    "config": config,
                }
            )
    expected = {
        (method, family, seed)
        for method in P1_CHECKPOINT_METHODS
        for family in P1_FAMILIES
        for seed in P1_SEEDS
    }
    actual = {(row["method"], row["family"], row["seed"]) for row in rows}
    if len(rows) != 18 or actual != expected:
        raise ValueError("P1 checkpoint inventory is incomplete")
    return sorted(
        rows,
        key=lambda row: (str(row["method"]), str(row["family"]), int(row["seed"])),
    )


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
            P0_SUITE,
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
        suite = json.loads(_read_member(archive, members, P0_SUITE))
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
    points = {
        str(point["id"]): point
        for point in suite.get("points", [])
        if isinstance(point, dict)
    }
    for row in rows:
        point = points.get(str(row["point_id"]))
        if not isinstance(point, dict) or point.get("family") != row.get("family"):
            raise ValueError("P0 calibration parameter identity is missing")
        row["parameters"] = [float(value) for value in point["parameters"]]
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


PARAMETER_FEATURES = (
    "parameter_kx",
    "parameter_ky",
    "parameter_strength",
    "parameter_shape",
    "parameter_breaking",
    "parameter_family_gaussian",
)


def _parameter_feature_row(point: dict[str, object]) -> list[float]:
    family = str(point["family"])
    parameters = [float(value) for value in point["parameters"]]
    bounds = TRAINING_BOUNDS.get(family)
    if bounds is None or len(parameters) != len(bounds):
        raise ValueError("parameter-only point family or dimension is invalid")
    normalized = [
        (value - lower) / (upper - lower)
        for value, (lower, upper) in zip(parameters, bounds)
    ]
    if family == "harmonic_honeycomb":
        return [normalized[0], normalized[1], normalized[2], 0.0, normalized[3], 0.0]
    return [
        normalized[0],
        normalized[1],
        normalized[2],
        normalized[3],
        normalized[4],
        1.0,
    ]


def parameter_only_score(
    points: list[dict[str, object]], model: dict[str, object]
) -> torch.Tensor:
    """Score parameter locations with the frozen P0 calibration baseline."""

    matrix = torch.tensor(
        [_parameter_feature_row(point) for point in points], dtype=torch.float64
    )
    return predict_logistic_score(matrix, model)


def fit_parameter_only_risk(rows: list[dict[str, object]]) -> dict[str, object]:
    """Fit the preregistered parameter-only baseline on P0 calibration only."""

    calibration = [row for row in rows if row.get("role") == "calibration"]
    if len(calibration) != 240:
        raise ValueError("parameter-only baseline requires 240 calibration rows")
    matrix = torch.tensor(
        [_parameter_feature_row(row) for row in calibration], dtype=torch.float64
    )
    labels = torch.tensor(
        [str(row["regression"]).lower() == "true" for row in calibration],
        dtype=torch.bool,
    )
    model = fit_logistic_score(
        matrix, labels, list(PARAMETER_FEATURES), l2=1e-2
    )
    scores = predict_logistic_score(matrix, model)
    quantiles = torch.quantile(
        scores, torch.tensor([0.60, 0.90], dtype=torch.float64)
    )
    return {
        "model": model,
        "t_low_q60": float(quantiles[0]),
        "t_high_q90": float(quantiles[1]),
        "score_min": float(scores.min()),
        "score_max": float(scores.max()),
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
        raise TypeError("paired inference bases are missing")
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
        (rank - overlap.abs().square().sum(dim=(1, 2))).clamp_min(0.0) / rank
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
    """Construct all neural and reference-only variants for audit convenience."""

    if not (
        anchor.shape == candidate.shape == long_anchor.shape == reference.shape
    ):
        raise ValueError("all P1 bases must have the same shape")
    neural = build_neural_p1_bases(
        anchor, candidate, score=score, thresholds=thresholds
    )
    outputs = add_reference_p1_variants(
        neural,
        anchor,
        candidate,
        reference,
        score=score,
        thresholds=thresholds,
    )
    outputs["p5_long_anchor"] = {
        "basis": long_anchor,
        "pwe_mask": torch.zeros(anchor.shape[0], dtype=torch.bool, device=anchor.device),
        "risk_ood_mask": torch.zeros(
            anchor.shape[0], dtype=torch.bool, device=anchor.device
        ),
        "reference_only": False,
    }
    return {method: outputs[method] for method in P1_METHODS}


def build_neural_p1_bases(
    anchor: torch.Tensor,
    candidate: torch.Tensor,
    *,
    score: torch.Tensor,
    thresholds: dict[str, object],
    parameter_score: torch.Tensor | None = None,
    parameter_thresholds: dict[str, object] | None = None,
) -> dict[str, dict[str, object]]:
    """Build the complete reference-free P1 primary and neural controls."""

    if anchor.shape != candidate.shape:
        raise ValueError("P1 anchor and candidate bases must have the same shape")
    score = torch.as_tensor(score, device=anchor.device, dtype=anchor.dtype)
    if score.shape != (anchor.shape[0],) or not bool(torch.isfinite(score).all()):
        raise ValueError("P1 score must be finite and aligned with the batch")
    production = build_primary_neural_p1(
        anchor, candidate, score=score, thresholds=thresholds
    )
    t_hard = float(thresholds["t_hard_q80"])
    risk_ood = production["risk_ood_mask"]
    primary = production["basis"]
    hard = hard_select(anchor, candidate, (score <= t_hard) & ~risk_ood)
    half = risk_chordal_correct(
        anchor, candidate, torch.full_like(score, 0.5)
    )
    if parameter_score is None:
        parameter_score = score
    parameter_score = torch.as_tensor(
        parameter_score, device=anchor.device, dtype=anchor.dtype
    )
    if parameter_score.shape != score.shape or not bool(
        torch.isfinite(parameter_score).all()
    ):
        raise ValueError("parameter-only score must align with the P1 batch")
    parameter_thresholds = thresholds if parameter_thresholds is None else parameter_thresholds
    parameter_ood = (
        parameter_score < float(parameter_thresholds.get("score_min", 0.0))
    ) | (parameter_score > float(parameter_thresholds.get("score_max", 1.0)))
    parameter_weight = torch.where(
        parameter_ood,
        torch.zeros_like(parameter_score),
        risk_weight(
            parameter_score,
            float(parameter_thresholds["t_low_q60"]),
            float(parameter_thresholds["t_high_q90"]),
        ),
    )
    parameter_output = risk_chordal_correct(
        anchor, candidate, parameter_weight
    )
    no_pwe = torch.zeros_like(risk_ood)
    outputs = {
        "p5_anchor": {"basis": anchor, "pwe_mask": no_pwe},
        "p5_static_low_rom": {"basis": candidate, "pwe_mask": no_pwe},
        "p1_hard_select": {"basis": hard, "pwe_mask": no_pwe},
        "p1_no_risk_half_blend": {"basis": half, "pwe_mask": no_pwe},
        "p1_parameter_only_chordal": {
            "basis": parameter_output,
            "pwe_mask": no_pwe,
        },
        "p1_risk_chordal": {"basis": primary, "pwe_mask": no_pwe},
    }
    for output in outputs.values():
        output["risk_ood_mask"] = risk_ood
        output["reference_only"] = False
    outputs["p1_parameter_only_chordal"]["risk_ood_mask"] = parameter_ood
    return outputs


def build_primary_neural_p1(
    anchor: torch.Tensor,
    candidate: torch.Tensor,
    *,
    score: torch.Tensor,
    thresholds: dict[str, object],
) -> dict[str, torch.Tensor]:
    """Build only the deployable reference-free P1 production output."""

    if anchor.shape != candidate.shape:
        raise ValueError("P1 anchor and candidate bases must have the same shape")
    score = torch.as_tensor(score, device=anchor.device, dtype=anchor.dtype)
    if score.shape != (anchor.shape[0],) or not bool(torch.isfinite(score).all()):
        raise ValueError("P1 score must be finite and aligned with the batch")
    risk_ood = (score < float(thresholds.get("score_min", 0.0))) | (
        score > float(thresholds.get("score_max", 1.0))
    )
    weight = torch.where(
        risk_ood,
        torch.zeros_like(score),
        risk_weight(
            score,
            float(thresholds["t_low_q60"]),
            float(thresholds["t_high_q90"]),
        ),
    )
    return {
        "basis": risk_chordal_correct(anchor, candidate, weight),
        "weight": weight,
        "risk_ood_mask": risk_ood,
    }


def add_reference_p1_variants(
    neural: dict[str, dict[str, object]],
    anchor: torch.Tensor,
    candidate: torch.Tensor,
    reference: torch.Tensor,
    *,
    score: torch.Tensor,
    thresholds: dict[str, object],
) -> dict[str, dict[str, object]]:
    """Add PWE safety and oracle rows after reference-free primary inference."""

    outputs = {name: dict(value) for name, value in neural.items()}
    score = torch.as_tensor(score, device=anchor.device, dtype=anchor.dtype)
    risk_ood = (score < float(thresholds.get("score_min", 0.0))) | (
        score > float(thresholds.get("score_max", 1.0))
    )
    pwe_mask = (score > float(thresholds["t_pwe_q95"])) | risk_ood
    primary = outputs["p1_risk_chordal"]["basis"]
    safety = torch.where(pwe_mask[:, None, None, None], reference, primary)
    candidate_error = _per_sample_projector_error(candidate, reference)
    anchor_error = _per_sample_projector_error(anchor, reference)
    oracle = hard_select(anchor, candidate, candidate_error < anchor_error)
    outputs["p1_risk_chordal_pwe5"] = {
        "basis": safety,
        "pwe_mask": pwe_mask,
    }
    outputs["oracle_min_anchor_rom"] = {
        "basis": oracle,
        "pwe_mask": torch.zeros_like(pwe_mask),
    }
    for method, output in outputs.items():
        output["risk_ood_mask"] = risk_ood
        output["reference_only"] = method == "oracle_min_anchor_rom"
    return outputs


def validate_p1_runtime_suite(payload: dict[str, object], root: Path) -> None:
    """Recheck disjointness and exact preregistered bytes before P1 inference."""

    points = payload.get("points")
    if not isinstance(points, list):
        raise TypeError("P1 runtime suite points are missing")
    validate_p1_suite_disjointness(points, root)
    expected = build_p1_suite_payload(generate_p1_validation_suite())
    if json.dumps(payload, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError("P1 runtime suite does not match deterministic regeneration")


def aggregate_p1_rows(
    rows: list[dict[str, object]],
    *,
    anchor_latency_ms: float,
    p1_latency_ms: float,
    expected_points_per_method: int,
) -> dict[str, object]:
    """Aggregate paired P1 rows into the frozen gate summary schema."""

    by_method = {
        method: [row for row in rows if row.get("method") == method]
        for method in P1_METHODS
    }
    expected_identity: set[tuple[str, int, str]] | None = None
    engineering_pass = True
    for method, selected in by_method.items():
        identities = {
            (str(row["family"]), int(row["seed"]), str(row["point_id"]))
            for row in selected
        }
        if len(selected) != expected_points_per_method or len(identities) != len(
            selected
        ):
            engineering_pass = False
        if expected_identity is None:
            expected_identity = identities
        elif identities != expected_identity:
            engineering_pass = False
        if any(
            not math.isfinite(float(row["projector_error"]))
            or not math.isfinite(float(row["orthogonality_error"]))
            for row in selected
        ):
            engineering_pass = False
        if any(
            bool(row.get("reference_only")) != (method == "oracle_min_anchor_rom")
            for row in selected
        ):
            engineering_pass = False
    if any(row.get("method") not in P1_METHODS for row in rows):
        engineering_pass = False

    def mean_error(method: str, *, split: str | None = None) -> float:
        selected = [
            row
            for row in by_method[method]
            if split is None or row.get("split") == split
        ]
        if not selected:
            return math.inf
        return sum(float(row["projector_error"]) for row in selected) / len(selected)

    summary: dict[str, object] = {
        "engineering_pass": engineering_pass,
        "rows_per_method": {
            method: len(selected) for method, selected in by_method.items()
        },
        "maximum_orthogonality_error": max(
            (float(row["orthogonality_error"]) for row in rows), default=math.inf
        ),
        "p5_anchor_latency_ms": float(anchor_latency_ms),
        "p1_risk_chordal_latency_ms": float(p1_latency_ms),
    }
    for method in P1_METHODS:
        summary[f"{method}_overall_projector_mean"] = mean_error(method)
        for split in ("iid_hidden", "exact_cluster", "near_cluster", "strict_ood", "gap_scan"):
            value = mean_error(method, split=split)
            if math.isfinite(value):
                summary[f"{method}_{split}_projector_mean"] = value

    family_near: dict[str, dict[str, float]] = {}
    for family in P1_FAMILIES:
        family_near[family] = {}
        for method in ("p1_risk_chordal", "p5_long_anchor"):
            selected = [
                row
                for row in by_method[method]
                if row.get("family") == family and row.get("split") == "near_cluster"
            ]
            family_near[family][method] = (
                sum(float(row["projector_error"]) for row in selected) / len(selected)
                if selected
                else math.inf
            )
    summary["family_near_projector_mean"] = family_near

    paired_wins = 0
    paired_comparisons = 0
    for family in P1_FAMILIES:
        for seed in P1_SEEDS:
            primary = [
                row
                for row in by_method["p1_risk_chordal"]
                if row.get("family") == family
                and int(row["seed"]) == seed
                and row.get("split") == "near_cluster"
            ]
            baseline = [
                row
                for row in by_method["p5_long_anchor"]
                if row.get("family") == family
                and int(row["seed"]) == seed
                and row.get("split") == "near_cluster"
            ]
            if primary and baseline and len(primary) == len(baseline):
                paired_comparisons += 1
                primary_mean = sum(float(row["projector_error"]) for row in primary) / len(primary)
                baseline_mean = sum(float(row["projector_error"]) for row in baseline) / len(baseline)
                paired_wins += primary_mean < baseline_mean
    summary["paired_near_wins_vs_long_anchor"] = paired_wins
    summary["paired_near_comparisons"] = paired_comparisons

    anchor_by_identity = {
        (str(row["family"]), int(row["seed"]), str(row["point_id"])): float(
            row["projector_error"]
        )
        for row in by_method["p5_anchor"]
    }
    for method in ("p5_static_low_rom", "p1_risk_chordal"):
        unsafe = [
            float(row["projector_error"])
            > 1.02
            * anchor_by_identity[
                (str(row["family"]), int(row["seed"]), str(row["point_id"]))
            ]
            for row in by_method[method]
        ]
        summary[f"{method}_unsafe_rate_vs_anchor"] = (
            sum(unsafe) / len(unsafe) if unsafe else math.inf
        )
    primary_rows = by_method["p1_risk_chordal"]
    summary["p1_risk_chordal_pwe_fraction"] = (
        sum(bool(row.get("pwe_used")) for row in primary_rows) / len(primary_rows)
        if primary_rows
        else math.inf
    )
    rom_by_identity = {
        (str(row["family"]), int(row["seed"]), str(row["point_id"])): float(
            row["projector_error"]
        )
        for row in by_method["p5_static_low_rom"]
    }
    regression = torch.tensor(
        [
            rom_by_identity[
                (str(row["family"]), int(row["seed"]), str(row["point_id"]))
            ]
            > anchor_by_identity[
                (str(row["family"]), int(row["seed"]), str(row["point_id"]))
            ]
            for row in primary_rows
        ],
        dtype=torch.bool,
    )
    combined_scores = torch.tensor(
        [float(row["risk_score"]) for row in primary_rows], dtype=torch.float64
    )
    parameter_scores = torch.tensor(
        [float(row["parameter_risk_score"]) for row in primary_rows],
        dtype=torch.float64,
    )
    try:
        summary["combined_risk_auroc"] = binary_auroc(
            regression, combined_scores
        )
        summary["parameter_only_risk_auroc"] = binary_auroc(
            regression, parameter_scores
        )
        summary["combined_risk_auroc_by_family"] = {
            family: binary_auroc(
                regression[
                    torch.tensor(
                        [row["family"] == family for row in primary_rows],
                        dtype=torch.bool,
                    )
                ],
                combined_scores[
                    torch.tensor(
                        [row["family"] == family for row in primary_rows],
                        dtype=torch.bool,
                    )
                ],
            )
            for family in P1_FAMILIES
        }
    except ValueError:
        summary["combined_risk_auroc"] = math.nan
        summary["parameter_only_risk_auroc"] = math.nan
        summary["combined_risk_auroc_by_family"] = {
            family: math.nan for family in P1_FAMILIES
        }
    return summary


def _synchronize(device: torch.device) -> None:
    if device.type == "cuda" and torch.cuda.is_available():
        torch.cuda.synchronize(device)
    elif device.type == "mps" and torch.backends.mps.is_available():
        torch.mps.synchronize()


def accelerator_peak_memory(device: torch.device) -> int:
    """Return measured accelerator memory bytes, or zero for CPU."""

    if device.type == "cuda" and torch.cuda.is_available():
        return int(torch.cuda.max_memory_allocated(device))
    if device.type == "mps" and torch.backends.mps.is_available():
        return int(torch.mps.current_allocated_memory())
    return 0


def _model_diagnostics(
    model: torch.nn.Module,
    coordinates: torch.Tensor,
    parameters: torch.Tensor,
    family: str,
) -> dict[str, object]:
    raw = model(coordinates, parameters)
    basis = periodic_mgs(raw)
    h_basis = apply_hamiltonian(basis, coordinates, parameters, family)
    ritz = _ritz_values(basis, h_basis)
    return {
        "basis": basis,
        "residual": float(projected_residual_rms(basis, h_basis).detach().cpu()),
        "gram": _gram_condition(raw),
        "ritz_1": float(ritz[0]),
        "ritz_2": float(ritz[1]),
    }


def benchmark_neural_latency(
    anchor_model: torch.nn.Module,
    candidate_model: torch.nn.Module,
    point: dict[str, object],
    *,
    p0_model: dict[str, object],
    thresholds: dict[str, object],
    device: torch.device,
    grid_side: int,
    warmup: int,
    repeats: int,
) -> dict[str, float | int]:
    """Benchmark complete reference-free anchor and P1 query paths."""

    if warmup < 0 or repeats < 1:
        raise ValueError("latency warmup/repeats are invalid")
    family = str(point["family"])

    def inputs() -> tuple[torch.Tensor, torch.Tensor]:
        coordinates = uniform_grid(grid_side).unsqueeze(0).to(device).requires_grad_()
        parameters = torch.tensor(
            [point["parameters"]], device=device, dtype=torch.float32
        )
        return coordinates, parameters

    def anchor_query() -> None:
        coordinates, parameters = inputs()
        _model_diagnostics(anchor_model, coordinates, parameters, family)

    def p1_query() -> None:
        coordinates, parameters = inputs()
        anchor = _model_diagnostics(anchor_model, coordinates, parameters, family)
        candidate = _model_diagnostics(
            candidate_model, coordinates, parameters, family
        )
        features = build_inference_features(anchor, candidate)
        matrix = torch.tensor(
            [[features[name] for name in PROMOTED_FEATURES]], dtype=torch.float64
        )
        score = predict_logistic_score(matrix, p0_model).to(
            device=device, dtype=parameters.dtype
        )
        build_primary_neural_p1(
            anchor["basis"],
            candidate["basis"],
            score=score,
            thresholds=thresholds,
        )

    for _ in range(warmup):
        anchor_query()
        p1_query()
        _synchronize(device)

    def samples(query: object) -> list[float]:
        values: list[float] = []
        for _ in range(repeats):
            _synchronize(device)
            started = time.perf_counter()
            query()
            _synchronize(device)
            values.append((time.perf_counter() - started) * 1000.0)
        return values

    anchor_samples = samples(anchor_query)
    p1_samples = samples(p1_query)

    def statistics(values: list[float]) -> tuple[float, float, float]:
        tensor = torch.tensor(values, dtype=torch.float64)
        return (
            float(tensor.mean()),
            float(torch.quantile(tensor, 0.50)),
            float(torch.quantile(tensor, 0.95)),
        )

    anchor_mean, anchor_p50, anchor_p95 = statistics(anchor_samples)
    p1_mean, p1_p50, p1_p95 = statistics(p1_samples)
    return {
        "warmup": warmup,
        "repeats": repeats,
        "anchor_latency_ms": anchor_mean,
        "anchor_p50_ms": anchor_p50,
        "anchor_p95_ms": anchor_p95,
        "p1_latency_ms": p1_mean,
        "p1_p50_ms": p1_p50,
        "p1_p95_ms": p1_p95,
        "peak_accelerator_memory_bytes": accelerator_peak_memory(device),
    }


def evaluate_p1_point(
    anchor_model: torch.nn.Module,
    candidate_model: torch.nn.Module,
    long_anchor_model: torch.nn.Module,
    point: dict[str, object],
    reference: dict[str, object],
    *,
    p0_model: dict[str, object],
    thresholds: dict[str, object],
    parameter_model: dict[str, object] | None = None,
    parameter_thresholds: dict[str, object] | None = None,
    seed: int,
    device: torch.device,
    grid_side: int = 33,
) -> tuple[list[dict[str, object]], dict[str, float]]:
    """Evaluate all P1 methods for one point without reference feature leakage."""

    coordinates = uniform_grid(grid_side).unsqueeze(0).to(device).requires_grad_()
    parameters = torch.tensor(
        [point["parameters"]], device=device, dtype=torch.float32
    )
    family = str(point["family"])

    _synchronize(device)
    p1_started = time.perf_counter()
    anchor_started = p1_started
    anchor = _model_diagnostics(anchor_model, coordinates, parameters, family)
    _synchronize(device)
    anchor_elapsed = (time.perf_counter() - anchor_started) * 1000.0
    candidate = _model_diagnostics(candidate_model, coordinates, parameters, family)
    features = build_inference_features(anchor, candidate)
    feature_matrix = torch.tensor(
        [[features[name] for name in PROMOTED_FEATURES]], dtype=torch.float64
    )
    score = predict_logistic_score(feature_matrix, p0_model).to(
        device=device, dtype=parameters.dtype
    )
    parameter_score = (
        parameter_only_score([point], parameter_model).to(
            device=device, dtype=parameters.dtype
        )
        if parameter_model is not None
        else score
    )
    neural_outputs = build_neural_p1_bases(
        anchor["basis"],
        candidate["basis"],
        score=score,
        thresholds=thresholds,
        parameter_score=parameter_score,
        parameter_thresholds=parameter_thresholds,
    )
    _synchronize(device)
    p1_elapsed = (time.perf_counter() - p1_started) * 1000.0

    long_anchor = _model_diagnostics(
        long_anchor_model, coordinates, parameters, family
    )
    reference_basis = reference.get("basis")
    if not isinstance(reference_basis, torch.Tensor):
        raise TypeError(f"P1 reference basis is missing: {point['id']}")
    reference_basis = periodic_mgs(
        reference_basis[..., :2, :]
        .unsqueeze(0)
        .to(device=device, dtype=parameters.dtype)
    )
    outputs = add_reference_p1_variants(
        neural_outputs,
        anchor["basis"],
        candidate["basis"],
        reference_basis,
        score=score,
        thresholds=thresholds,
    )
    outputs["p5_long_anchor"] = {
        "basis": long_anchor["basis"],
        "pwe_mask": torch.zeros_like(score, dtype=torch.bool),
        "risk_ood_mask": torch.zeros_like(score, dtype=torch.bool),
        "reference_only": False,
    }
    outputs = {method: outputs[method] for method in P1_METHODS}
    risk_ood = neural_outputs["p1_risk_chordal"]["risk_ood_mask"]
    primary_weight = torch.where(
        risk_ood,
        torch.zeros_like(score),
        risk_weight(
            score,
            float(thresholds["t_low_q60"]),
            float(thresholds["t_high_q90"]),
        ),
    )
    rows: list[dict[str, object]] = []
    for method in P1_METHODS:
        output = outputs[method]
        basis = output["basis"]
        if not isinstance(basis, torch.Tensor):
            raise TypeError(f"P1 method basis is missing: {method}")
        rows.append(
            {
                "method": method,
                "family": family,
                "seed": seed,
                "split": str(point["split"]),
                "point_id": str(point["id"]),
                "projector_error": projector_sine_error(basis, reference_basis),
                "orthogonality_error": orthogonality_error(basis),
                "risk_score": float(score[0].detach().cpu()),
                "parameter_risk_score": float(
                    parameter_score[0].detach().cpu()
                ),
                "rom_weight": float(primary_weight[0].detach().cpu()),
                "pwe_used": bool(output["pwe_mask"][0].detach().cpu()),
                "risk_ood": bool(output["risk_ood_mask"][0].detach().cpu()),
                "reference_only": bool(output["reference_only"]),
            }
        )
    return rows, {
        "anchor_latency_ms": anchor_elapsed,
        "p1_latency_ms": p1_elapsed,
    }


def _atomic_json(payload: object, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def prepare_environment(
    path: Path, current: dict[str, object]
) -> dict[str, object]:
    """Reuse the original timestamp when all scientific runtime fields match."""

    if path.is_file():
        previous = json.loads(path.read_text())
        if isinstance(previous, dict):
            previous_stable = {
                key: value
                for key, value in previous.items()
                if key != "timestamp_utc"
            }
            current_stable = {
                key: value
                for key, value in current.items()
                if key != "timestamp_utc"
            }
            if previous_stable == current_stable:
                return previous
    _atomic_json(current, path)
    return current


def _write_p1_unit(
    path: Path,
    provenance: dict[str, object],
    rows: list[dict[str, object]],
    timing: dict[str, float],
) -> None:
    """Atomically persist one resumable family-seed P1 unit."""

    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_json(
        {"provenance": provenance, "rows": rows, "timing": timing}, path
    )
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{file_sha256(path)}  {path.name}\n"
    )


def _load_p1_unit(
    path: Path,
    expected_provenance: dict[str, object],
    *,
    expected_family: str,
    expected_seed: int,
    expected_point_ids: set[str],
) -> dict[str, object] | None:
    """Load a completed unit only when bytes, sources, and identities match."""

    sidecar = path.with_suffix(path.suffix + ".sha256")
    if not path.is_file() and not sidecar.is_file():
        return None
    if not path.is_file() or not sidecar.is_file():
        raise ValueError("P1 unit JSON and SHA-256 sidecar must coexist")
    tokens = sidecar.read_text().split()
    if not tokens or tokens[0] != file_sha256(path):
        raise ValueError("P1 unit SHA-256 mismatch")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict) or payload.get("provenance") != expected_provenance:
        raise ValueError("P1 unit provenance mismatch")
    rows = payload.get("rows")
    timing = payload.get("timing")
    if not isinstance(rows, list) or len(rows) != len(expected_point_ids) * len(
        P1_METHODS
    ):
        raise ValueError("P1 unit row count is incomplete")
    identities: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("P1 unit row is not an object")
        point_id = str(row.get("point_id", ""))
        method = str(row.get("method", ""))
        identity = point_id, method
        if (
            point_id not in expected_point_ids
            or method not in P1_METHODS
            or identity in identities
        ):
            raise ValueError("P1 unit row identity is invalid")
        identities.add(identity)
        if row.get("family") != expected_family or row.get("seed") != expected_seed:
            raise ValueError("P1 unit family or seed is invalid")
        if not all(
            math.isfinite(float(row[name]))
            for name in (
                "projector_error",
                "orthogonality_error",
                "risk_score",
                "parameter_risk_score",
                "rom_weight",
            )
        ):
            raise ValueError("P1 unit contains non-finite metrics")
        if (
            not isinstance(row.get("pwe_used"), bool)
            or not isinstance(row.get("risk_ood"), bool)
            or not isinstance(row.get("reference_only"), bool)
        ):
            raise TypeError("P1 unit Boolean fields are malformed")
        if bool(row["reference_only"]) != (method == "oracle_min_anchor_rom"):
            raise ValueError("P1 unit oracle marker is invalid")
    expected_identities = {
        (point_id, method)
        for point_id in expected_point_ids
        for method in P1_METHODS
    }
    if identities != expected_identities:
        raise ValueError("P1 unit methods are incomplete")
    if not isinstance(timing, dict) or not all(
        name in timing and math.isfinite(float(timing[name])) and float(timing[name]) > 0
        for name in ("anchor_latency_ms", "p1_latency_ms")
    ):
        raise ValueError("P1 unit timing is invalid")
    return {"rows": rows, "timing": timing}


def _write_rows(rows: list[dict[str, object]], path: Path) -> None:
    fields = (
        "method",
        "family",
        "seed",
        "split",
        "point_id",
        "projector_error",
        "orthogonality_error",
        "risk_score",
        "parameter_risk_score",
        "rom_weight",
        "pwe_used",
        "risk_ood",
        "reference_only",
    )
    temporary = path.with_suffix(".csv.tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _report(status: str, summary: dict[str, object], gate: dict[str, object]) -> str:
    lines = [
        "# P1 Risk-Gated Corrector Report",
        "",
        "> Development pilot only. Frozen final was not read or evaluated.",
        "",
        f"- Status: `{status}`",
        f"- Engineering pass: `{summary['engineering_pass']}`",
    ]
    if "p1_risk_chordal_near_cluster_projector_mean" in summary:
        lines.extend(
            (
                f"- P1 near error: `{summary['p1_risk_chordal_near_cluster_projector_mean']:.6f}`",
                f"- long-anchor near error: `{summary['p5_long_anchor_near_cluster_projector_mean']:.6f}`",
                f"- P1 gap-scan error: `{summary['p1_risk_chordal_gap_scan_projector_mean']:.6f}`",
                f"- P1/anchor latency ratio: `{gate.get('latency_ratio', math.nan):.6f}`",
            )
        )
    lines.extend(
        (
            "",
            "A smoke PASS is engineering evidence only. P1_PILOT_STOP keeps promotion and frozen final closed.",
            "",
        )
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--device", default="auto", choices=("auto", "cpu", "mps", "cuda", "rocm")
    )
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--latency-warmup", type=int, default=10)
    parser.add_argument("--latency-repeats", type=int, default=100)
    parser.add_argument(
        "--suite", type=Path, default=Path("benchmarks/p1_validation_v1.json")
    )
    parser.add_argument(
        "--reference-cache",
        type=Path,
        default=Path("data/p1_validation_v1_references.pt"),
    )
    parser.add_argument(
        "--p0-archive",
        type=Path,
        default=Path("artifacts/risk-development-evidence-20260824-092630.tar.gz"),
    )
    parser.add_argument(
        "--p0-sidecar",
        type=Path,
        default=Path("artifacts/risk-development-evidence-20260824-092630.tar.gz.sha256"),
    )
    parser.add_argument(
        "--p5-archive",
        type=Path,
        default=Path("artifacts/p5-evidence-20260801-092048.tar.gz"),
    )
    parser.add_argument(
        "--p5-sidecar",
        type=Path,
        default=Path("artifacts/p5-evidence-20260801-092048.tar.gz.sha256"),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("results/p1_pilot")
    )
    return parser


def _root_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def run_p1_pilot(args: argparse.Namespace) -> tuple[str, int]:
    root = Path(__file__).resolve().parents[1]
    output_dir = (
        root / "results/p1_smoke"
        if args.smoke_only
        else _root_path(root, args.output_dir)
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ("summary.json", "gate.json", "rows.csv"):
        (output_dir / name).unlink(missing_ok=True)

    current_environment = _environment(root, args.device)
    if current_environment["git_status_porcelain"] and not args.allow_dirty:
        raise RuntimeError("formal P1 execution requires a clean Git checkout")
    prepare_environment(output_dir / "environment.json", current_environment)
    device = select_device(args.device)
    if device.type == "cuda" and torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats(device)

    p0_archive = _root_path(root, args.p0_archive)
    p0_sidecar = _root_path(root, args.p0_sidecar)
    calibration = load_p0_calibration(p0_archive, p0_sidecar)
    thresholds = frozen_thresholds(calibration["model"], calibration["rows"])
    parameter_baseline = fit_parameter_only_risk(calibration["rows"])
    threshold_payload = {
        **thresholds,
        "parameter_only": parameter_baseline,
        "p0_archive_sha256": calibration["archive_sha256"],
        "source_fingerprint": p1_source_fingerprint(root),
    }
    _atomic_json(threshold_payload, output_dir / "thresholds.json")
    threshold_sha256 = file_sha256(output_dir / "thresholds.json")

    formal_suite_path = _root_path(root, args.suite)
    formal_suite, _ = load_frozen_suite(formal_suite_path)
    if formal_suite.get("suite_id") != "block-kyfan-p1-validation-v1-20260824":
        raise ValueError("unexpected P1 validation suite")
    validate_p1_runtime_suite(formal_suite, root)
    grid_side = 7 if args.smoke_only else 33
    cutoff = 2 if args.smoke_only else 24
    seeds = (42,) if args.smoke_only else P1_SEEDS
    if args.smoke_only:
        points = []
        for family in P1_FAMILIES:
            points.append(
                next(
                    point
                    for point in formal_suite["points"]
                    if point["family"] == family and point["split"] == "iid_hidden"
                )
            )
        suite_path = output_dir / "p1_smoke_suite.json"
        write_frozen_suite(build_p1_suite_payload(points), suite_path)
        reference_path = output_dir / "p1_smoke_references.pt"
        build_p1_reference_cache(
            suite_path, reference_path, cutoff=cutoff, grid_side=grid_side, rank=3
        )
    else:
        points = list(formal_suite["points"])
        suite_path = formal_suite_path
        reference_path = _root_path(root, args.reference_cache)
    suite, suite_hash = load_frozen_suite(suite_path)
    references, reference_hash = _load_reference_cache(
        reference_path,
        suite_id=str(suite["suite_id"]),
        suite_hash=suite_hash,
        point_ids={str(point["id"]) for point in points},
        grid_side=grid_side,
        cutoff=cutoff,
    )
    reference_payload = torch.load(reference_path, map_location="cpu", weights_only=False)
    if reference_payload.get("metadata", {}).get("rank") != 3:
        raise ValueError("P1 reference cache rank must be three")

    p5_archive = _root_path(root, args.p5_archive)
    p5_sidecar = _root_path(root, args.p5_sidecar)
    inventory = inventory_p1_checkpoints(p5_archive, p5_sidecar)
    _atomic_json(inventory, output_dir / "checkpoint_inventory.json")
    inventory_map = {
        (str(row["method"]), str(row["family"]), int(row["seed"])): row
        for row in inventory
    }
    all_rows: list[dict[str, object]] = []
    anchor_latencies: list[float] = []
    p1_latencies: list[float] = []
    latency_units: list[dict[str, object]] = []
    unit_dir = output_dir / "units"
    unit_dir.mkdir(exist_ok=True)
    source_fingerprint = p1_source_fingerprint(root)
    p5_archive_sha256 = file_sha256(p5_archive)
    for family in P1_FAMILIES:
        family_points = [point for point in points if point["family"] == family]
        for seed in seeds:
            checkpoint_sha256 = {
                method: str(inventory_map[(method, family, seed)]["checkpoint_sha256"])
                for method in P1_CHECKPOINT_METHODS
            }
            unit_provenance = {
                "suite_sha256": suite_hash,
                "reference_sha256": reference_hash,
                "p0_archive_sha256": calibration["archive_sha256"],
                "p5_archive_sha256": p5_archive_sha256,
                "source_fingerprint": source_fingerprint,
                "requirements_sha256": file_sha256(root / "requirements.txt"),
                "environment_sha256": file_sha256(
                    output_dir / "environment.json"
                ),
                "torch_version": torch.__version__,
                "hip_version": torch.version.hip,
                "latency_warmup": (
                    1 if args.smoke_only else args.latency_warmup
                ),
                "latency_repeats": (
                    2 if args.smoke_only else args.latency_repeats
                ),
                "threshold_sha256": threshold_sha256,
                "checkpoint_sha256": checkpoint_sha256,
            }
            unit_path = unit_dir / f"{family}_seed{seed}.json"
            try:
                completed = _load_p1_unit(
                    unit_path,
                    unit_provenance,
                    expected_family=family,
                    expected_seed=seed,
                    expected_point_ids={str(point["id"]) for point in family_points},
                )
            except ValueError:
                if not args.smoke_only:
                    raise
                unit_path.unlink(missing_ok=True)
                unit_path.with_suffix(unit_path.suffix + ".sha256").unlink(
                    missing_ok=True
                )
                completed = None
            if completed is not None:
                all_rows.extend(completed["rows"])
                timing = completed["timing"]
                anchor_latencies.append(float(timing["anchor_latency_ms"]))
                p1_latencies.append(float(timing["p1_latency_ms"]))
                latency_units.append({"family": family, "seed": seed, **timing})
                print(f"P1_UNIT_RESUMED={family}:seed{seed}", flush=True)
                continue
            anchor_model = load_p5_checkpoint(
                p5_archive, inventory_map[("p5_anchor", family, seed)], device
            )
            candidate_model = load_p5_checkpoint(
                p5_archive,
                inventory_map[("p5_static_low_rom", family, seed)],
                device,
            )
            long_anchor_model = load_p5_checkpoint(
                p5_archive,
                inventory_map[("p5_long_anchor", family, seed)],
                device,
            )
            unit_timing = benchmark_neural_latency(
                anchor_model,
                candidate_model,
                family_points[0],
                p0_model=calibration["model"],
                thresholds=thresholds,
                device=device,
                grid_side=grid_side,
                warmup=1 if args.smoke_only else args.latency_warmup,
                repeats=2 if args.smoke_only else args.latency_repeats,
            )
            unit_rows: list[dict[str, object]] = []
            for point in family_points:
                rows, _ = evaluate_p1_point(
                    anchor_model,
                    candidate_model,
                    long_anchor_model,
                    point,
                    references[str(point["id"])],
                    p0_model=calibration["model"],
                    thresholds=thresholds,
                    parameter_model=parameter_baseline["model"],
                    parameter_thresholds=parameter_baseline,
                    seed=seed,
                    device=device,
                    grid_side=grid_side,
                )
                unit_rows.extend(rows)
            _write_p1_unit(unit_path, unit_provenance, unit_rows, unit_timing)
            all_rows.extend(unit_rows)
            anchor_latencies.append(float(unit_timing["anchor_latency_ms"]))
            p1_latencies.append(float(unit_timing["p1_latency_ms"]))
            latency_units.append({"family": family, "seed": seed, **unit_timing})
            print(f"P1_UNIT_COMPLETE={family}:seed{seed}", flush=True)

    expected_points_per_method = len(points) * len(seeds)
    summary = aggregate_p1_rows(
        all_rows,
        anchor_latency_ms=sum(anchor_latencies) / len(anchor_latencies),
        p1_latency_ms=sum(p1_latencies) / len(p1_latencies),
        expected_points_per_method=expected_points_per_method,
    )
    summary["latency_units"] = latency_units
    summary["peak_accelerator_memory_bytes"] = max(
        (
            int(unit.get("peak_accelerator_memory_bytes", 0))
            for unit in latency_units
        ),
        default=accelerator_peak_memory(device),
    )
    provenance = {
        "suite_sha256": suite_hash,
        "reference_sha256": reference_hash,
        "p0_archive_sha256": calibration["archive_sha256"],
        "p5_archive_sha256": p5_archive_sha256,
        "source_fingerprint": source_fingerprint,
        "seeds": list(seeds),
        "grid_side": grid_side,
        "cutoff": cutoff,
    }
    summary.update(provenance)
    _atomic_json(provenance, output_dir / "provenance.json")
    _write_rows(all_rows, output_dir / "rows.csv")
    _atomic_json(summary, output_dir / "summary.json")

    if args.smoke_only:
        smoke_pass = bool(summary["engineering_pass"]) and len(all_rows) == len(
            P1_METHODS
        ) * expected_points_per_method
        status = "P1_ENGINEERING_SMOKE_PASS" if smoke_pass else "P1_ENGINEERING_SMOKE_FAIL"
        gate = {"engineering_pass": smoke_pass, "pilot_go": False, **provenance}
        exit_code = 0 if smoke_pass else 1
    else:
        gate = {**build_p1_gate(summary), **provenance}
        status = "P1_PILOT_GO" if gate["pilot_go"] else "P1_PILOT_STOP"
        exit_code = 0 if gate["pilot_go"] else 2
    _atomic_json(gate, output_dir / "gate.json")
    (output_dir / "report.md").write_text(_report(status, summary, gate))

    if not args.smoke_only:
        label = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        archive, sidecar, manifest = write_evidence_bundle(
            root=root,
            include_paths=(
                output_dir,
                suite_path,
                suite_path.with_suffix(".sha256"),
                reference_path,
                reference_path.with_suffix(".sha256"),
                p0_archive,
                p0_sidecar,
                p5_archive,
                p5_sidecar,
                root / "block_kyfan_pinn/p1_corrector.py",
                root / "scripts/generate_p1_validation.py",
                root / "scripts/run_p1_pilot.py",
                root / "tests/test_p1_corrector.py",
                root / "tests/test_p1_protocol_integrity.py",
                root / "requirements.txt",
            ),
            output_dir=root / "artifacts",
            label=label,
            prefix="p1-pilot-evidence",
            manifest_name="p1-pilot-evidence-manifest.json",
        )
        evidence_audit = audit_p1_evidence(archive, sidecar)
        _atomic_json(evidence_audit, output_dir / "evidence-audit.json")
        if evidence_audit["audit_pass"] is not True:
            raise RuntimeError(
                f"P1 evidence audit failed: {evidence_audit['errors']}"
            )
        print(f"P1_EVIDENCE_BUNDLE={archive}")
        print(f"P1_EVIDENCE_SHA256={sidecar}")
        print(f"P1_EVIDENCE_MANIFEST={manifest}")
    print(f"P1_STATUS={status}")
    return status, exit_code


def main() -> int:
    args = build_parser().parse_args()
    _, exit_code = run_p1_pilot(args)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

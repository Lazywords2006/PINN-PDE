#!/usr/bin/env python3
"""Evaluate held-out label-free risk features from audited P5 checkpoints."""

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
from torch import nn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.metrics import projector_sine_error
from block_kyfan_pinn.device import select_device
from block_kyfan_pinn.p5_model import build_p5_model
from block_kyfan_pinn.physics import (
    apply_hamiltonian,
    complex_gram_mean,
    periodic_mgs,
    projected_residual_rms,
    ritz_matrix,
)
from block_kyfan_pinn.reference import uniform_grid
from block_kyfan_pinn.risk import (
    average_precision,
    binary_auroc,
    build_risk_gate,
    clustered_bootstrap_auc,
    fit_logistic_score,
    predict_logistic_score,
    risk_coverage,
    safe_log_ratio,
)
from block_kyfan_pinn.suites import file_sha256, load_frozen_suite
from scripts.audit_p5_evidence import audit_p5_evidence
from scripts.run_p3_pilot import _load_reference_cache
from scripts.run_p4_executor import _environment, write_evidence_bundle

EXPECTED_P5_ARCHIVE_SHA256 = (
    "56891c5740eb94c62299b72869d790a1cbdee6abda3fae2903ed822f5e405101"
)
RISK_METHODS = ("p5_anchor", "p5_static_low_rom")
RISK_FAMILIES = ("harmonic_honeycomb", "gaussian_honeycomb")
RISK_SEEDS = (42, 137, 251)
PROMOTED_FEATURES = (
    "anchor_residual",
    "candidate_residual",
    "residual_delta",
    "residual_log_ratio",
    "anchor_gram",
    "candidate_gram",
    "gram_delta",
    "gram_log_ratio",
    "anchor_ritz_gap",
    "candidate_ritz_gap",
    "ritz_gap_delta",
    "ritz_gap_log_ratio",
    "ritz_1_abs_difference",
    "ritz_2_abs_difference",
    "trace_abs_difference",
    "projector_disagreement",
)


def _risk_source_fingerprint(root: Path) -> str:
    """Bind paired units to both the library and P0 orchestration sources."""

    root = root.resolve()
    files = sorted((root / "block_kyfan_pinn").rglob("*.py"))
    files.extend(
        root / "scripts" / name
        for name in (
            "generate_risk_development.py",
            "evaluate_risk_features.py",
            "audit_p5_evidence.py",
        )
    )
    if not files or not all(path.is_file() for path in files):
        raise FileNotFoundError("risk fingerprint source set is incomplete")
    digest = hashlib.sha256()
    for path in sorted(set(files), key=lambda value: str(value.relative_to(root))):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _member_is_safe(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def _read_member(
    archive: tarfile.TarFile,
    members: dict[str, tarfile.TarInfo],
    name: str,
) -> bytes:
    member = members.get(name)
    if member is None or not member.isfile():
        raise ValueError(f"missing evidence member: {name}")
    handle = archive.extractfile(member)
    if handle is None:
        raise ValueError(f"unreadable evidence member: {name}")
    return handle.read()


def inventory_p5_checkpoints(
    archive_path: Path, sidecar_path: Path
) -> list[dict[str, object]]:
    """Return only the 12 paired final checkpoints after full P5 audit."""

    report = audit_p5_evidence(archive_path, sidecar_path)
    if report.get("audit_pass") is not True:
        raise ValueError("P5 evidence audit failed")
    if report.get("archive_sha256") != EXPECTED_P5_ARCHIVE_SHA256:
        raise ValueError("P5 evidence archive SHA-256 is not the approved digest")

    rows: list[dict[str, object]] = []
    with tarfile.open(archive_path, "r:gz") as archive:
        all_members = archive.getmembers()
        names = [member.name for member in all_members]
        duplicates = [name for name, count in Counter(names).items() if count > 1]
        unsafe = [name for name in names if not _member_is_safe(name)]
        if duplicates or unsafe:
            raise ValueError("P5 archive contains duplicate or unsafe paths")
        members = {member.name: member for member in all_members}
        result_names = sorted(
            name
            for name, member in members.items()
            if member.isfile()
            and name.startswith("results/p5_promotion/")
            and name.endswith("/result.json")
        )
        for result_member in result_names:
            result = json.loads(
                _read_member(archive, members, result_member).decode("utf-8")
            )
            config = result.get("config")
            if not isinstance(config, dict):
                raise ValueError(f"missing P5 config: {result_member}")
            method = str(config.get("method"))
            if method not in RISK_METHODS:
                continue
            family = str(config.get("potential_family"))
            seed = int(config.get("seed", -1))
            if family not in RISK_FAMILIES or seed not in RISK_SEEDS:
                raise ValueError(f"unexpected risk checkpoint identity: {config}")
            run_root = result_member.rsplit("/", 1)[0]
            checkpoint_member = f"{run_root}/final.pt"
            checkpoint_bytes = _read_member(
                archive, members, checkpoint_member
            )
            checkpoint_hash = hashlib.sha256(checkpoint_bytes).hexdigest()
            if checkpoint_hash != result.get("final_checkpoint_sha256"):
                raise ValueError(
                    f"final checkpoint hash mismatch: {checkpoint_member}"
                )
            if result.get("status") != "PASS":
                raise ValueError(f"P5 run is not complete: {run_root}")
            rows.append(
                {
                    "method": method,
                    "family": family,
                    "seed": seed,
                    "checkpoint_member": checkpoint_member,
                    "result_member": result_member,
                    "checkpoint_sha256": checkpoint_hash,
                    "config": config,
                }
            )

    expected = {
        (method, family, seed)
        for method in RISK_METHODS
        for family in RISK_FAMILIES
        for seed in RISK_SEEDS
    }
    actual = {
        (row["method"], row["family"], row["seed"]) for row in rows
    }
    if len(rows) != 12 or actual != expected:
        raise ValueError("P5 risk checkpoint inventory is incomplete")
    return sorted(
        rows,
        key=lambda row: (str(row["method"]), str(row["family"]), int(row["seed"])),
    )


def load_p5_checkpoint(
    archive_path: Path,
    inventory_row: dict[str, object],
    device: torch.device,
) -> nn.Module:
    """Reconstruct one exact P5 model from its declared final checkpoint."""

    member_name = str(inventory_row["checkpoint_member"])
    with tarfile.open(archive_path, "r:gz") as archive:
        member = archive.getmember(member_name)
        if not member.isfile() or not _member_is_safe(member.name):
            raise ValueError("P5 checkpoint member is unsafe or not a file")
        handle = archive.extractfile(member)
        if handle is None:
            raise ValueError("P5 checkpoint member is unreadable")
        checkpoint_bytes = handle.read()
    actual_hash = hashlib.sha256(checkpoint_bytes).hexdigest()
    if actual_hash != inventory_row["checkpoint_sha256"]:
        raise ValueError("P5 checkpoint bytes do not match inventory SHA-256")
    checkpoint = torch.load(
        io.BytesIO(checkpoint_bytes),
        map_location=device,
        weights_only=False,
    )
    if not isinstance(checkpoint, dict):
        raise ValueError("P5 checkpoint payload must be an object")
    config = checkpoint.get("config")
    expected_config = inventory_row.get("config")
    if not isinstance(config, dict) or config != expected_config:
        raise ValueError("P5 checkpoint config does not match result inventory")
    if (
        config.get("method") != inventory_row["method"]
        or config.get("potential_family") != inventory_row["family"]
        or config.get("seed") != inventory_row["seed"]
    ):
        raise ValueError("P5 checkpoint identity mismatch")
    state = checkpoint.get("model")
    if not isinstance(state, dict):
        raise ValueError("P5 checkpoint model state is missing")
    model = build_p5_model(
        str(inventory_row["method"]),
        potential_family=str(inventory_row["family"]),
        device=device,
        dtype=torch.float32,
    )
    model.load_state_dict(state, strict=True)
    model.eval()
    return model


def _gram_condition(raw_basis: torch.Tensor) -> float:
    real, imag = complex_gram_mean(raw_basis)
    gram = torch.complex(real.detach().cpu(), imag.detach().cpu())
    eigenvalues = torch.linalg.eigvalsh(gram).real.clamp_min(1e-12)
    return float((eigenvalues.amax(-1) / eigenvalues.amin(-1)).amax())


def _ritz_values(
    basis: torch.Tensor, h_basis: torch.Tensor
) -> torch.Tensor:
    real, imag = ritz_matrix(basis, h_basis)
    matrix = torch.complex(real.detach().cpu(), imag.detach().cpu())
    return torch.linalg.eigvalsh(matrix)[0].real


def _evaluate_one_model(
    model: nn.Module,
    point: dict[str, object],
    reference: dict[str, object],
    device: torch.device,
) -> dict[str, object]:
    coordinates = uniform_grid(33).unsqueeze(0).to(device).requires_grad_()
    parameters = torch.tensor(
        [point["parameters"]], device=device, dtype=torch.float32
    )
    raw_basis = model(coordinates, parameters)
    basis = periodic_mgs(raw_basis)
    h_basis = apply_hamiltonian(
        basis, coordinates, parameters, str(point["family"])
    )
    ritz = _ritz_values(basis, h_basis)
    reference_basis = reference.get("basis")
    if not isinstance(reference_basis, torch.Tensor):
        raise ValueError(f"reference basis is missing for {point['id']}")
    reference_basis = (
        reference_basis[..., :2, :]
        .unsqueeze(0)
        .to(device=device, dtype=basis.dtype)
    )
    return {
        "residual": float(projected_residual_rms(basis, h_basis).detach().cpu()),
        "gram": _gram_condition(raw_basis),
        "ritz_1": float(ritz[0]),
        "ritz_2": float(ritz[1]),
        "basis": basis.detach(),
        "projector_error": projector_sine_error(basis, reference_basis),
    }


def _scalar_log_ratio(numerator: float, denominator: float) -> float:
    values = safe_log_ratio(
        torch.tensor([numerator]), torch.tensor([denominator])
    )
    return float(values[0])


def build_paired_feature_row(
    *,
    role: str,
    family: str,
    split: str,
    point_id: str,
    seed: int,
    anchor: dict[str, object],
    candidate: dict[str, object],
    reference_internal_gap: float,
    reference_external_gap: float,
) -> dict[str, object]:
    """Join paired predictor diagnostics and keep oracle fields separate."""

    anchor_basis = anchor.get("basis")
    candidate_basis = candidate.get("basis")
    if not isinstance(anchor_basis, torch.Tensor) or not isinstance(
        candidate_basis, torch.Tensor
    ):
        raise ValueError("paired basis tensors are missing")
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
    anchor_error = float(anchor["projector_error"])
    candidate_error = float(candidate["projector_error"])
    return {
        "role": role,
        "family": family,
        "split": split,
        "point_id": point_id,
        "seed": seed,
        "anchor_residual": anchor_residual,
        "candidate_residual": candidate_residual,
        "residual_delta": candidate_residual - anchor_residual,
        "residual_log_ratio": _scalar_log_ratio(
            candidate_residual, anchor_residual
        ),
        "anchor_gram": anchor_gram,
        "candidate_gram": candidate_gram,
        "gram_delta": candidate_gram - anchor_gram,
        "gram_log_ratio": _scalar_log_ratio(candidate_gram, anchor_gram),
        "anchor_ritz_gap": anchor_gap,
        "candidate_ritz_gap": candidate_gap,
        "ritz_gap_delta": candidate_gap - anchor_gap,
        "ritz_gap_log_ratio": _scalar_log_ratio(candidate_gap, anchor_gap),
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
        "anchor_projector_error": anchor_error,
        "candidate_projector_error": candidate_error,
        "delta_error": candidate_error - anchor_error,
        "regression": candidate_error > anchor_error,
        "unsafe_regression": candidate_error > 1.02 * anchor_error,
        "reference_internal_gap": float(reference_internal_gap),
        "reference_external_gap": float(reference_external_gap),
    }


def evaluate_paired_points(
    anchor_model: nn.Module,
    candidate_model: nn.Module,
    points: list[dict[str, object]],
    references: dict[str, dict[str, object]],
    *,
    seed: int,
    device: torch.device,
) -> list[dict[str, object]]:
    """Evaluate one paired family/seed unit on shared parameter points."""

    rows: list[dict[str, object]] = []
    for point in points:
        point_id = str(point["id"])
        reference = references.get(point_id)
        if not isinstance(reference, dict):
            raise ValueError(f"reference is missing for {point_id}")
        anchor = _evaluate_one_model(
            anchor_model, point, reference, device
        )
        candidate = _evaluate_one_model(
            candidate_model, point, reference, device
        )
        rows.append(
            build_paired_feature_row(
                role=str(point["role"]),
                family=str(point["family"]),
                split=str(point["split"]),
                point_id=point_id,
                seed=seed,
                anchor=anchor,
                candidate=candidate,
                reference_internal_gap=float(reference["internal_gap"]),
                reference_external_gap=float(reference["external_gap"]),
            )
        )
    return rows


def _feature_matrix(rows: list[dict[str, object]]) -> torch.Tensor:
    matrix = torch.tensor(
        [
            [float(row[name]) for name in PROMOTED_FEATURES]
            for row in rows
        ],
        dtype=torch.float64,
    )
    if not bool(torch.isfinite(matrix).all()):
        raise ValueError("risk feature matrix contains non-finite values")
    return matrix


def calibrate_and_audit(
    rows: list[dict[str, object]],
    *,
    bootstrap_samples: int = 1000,
    bootstrap_seed: int = 20260824,
    expected_rows: int | None = None,
) -> dict[str, object]:
    """Fit on calibration rows and evaluate the audit role exactly once."""

    if expected_rows is not None and len(rows) != expected_rows:
        raise ValueError(
            f"expected {expected_rows} paired rows, received {len(rows)}"
        )
    identities = [
        (str(row.get("role")), str(row.get("point_id")), int(row.get("seed", -1)))
        for row in rows
    ]
    if len(identities) != len(set(identities)):
        raise ValueError("risk point/seed identities are duplicated")
    calibration = [row for row in rows if row.get("role") == "calibration"]
    audit = [row for row in rows if row.get("role") == "audit"]
    if not calibration or not audit or len(calibration) + len(audit) != len(rows):
        raise ValueError("risk rows must have non-empty calibration and audit roles")
    calibration_ids = {str(row["point_id"]) for row in calibration}
    audit_ids = {str(row["point_id"]) for row in audit}
    if not calibration_ids.isdisjoint(audit_ids):
        raise ValueError("risk calibration and audit point IDs overlap")
    if expected_rows == 480:
        for role_rows in (calibration, audit):
            role_point_ids = {str(row["point_id"]) for row in role_rows}
            if len(role_point_ids) != 80:
                raise ValueError("formal risk role must contain 80 unique points")
            for point_id in role_point_ids:
                seeds = {
                    int(row["seed"])
                    for row in role_rows
                    if row["point_id"] == point_id
                }
                if seeds != set(RISK_SEEDS):
                    raise ValueError(
                        f"formal risk point has incomplete seeds: {point_id}"
                    )

    calibration_matrix = _feature_matrix(calibration)
    audit_matrix = _feature_matrix(audit)
    calibration_labels = torch.tensor(
        [bool(row["regression"]) for row in calibration], dtype=torch.bool
    )
    primary_labels = torch.tensor(
        [bool(row["regression"]) for row in audit], dtype=torch.bool
    )
    unsafe_labels = torch.tensor(
        [bool(row["unsafe_regression"]) for row in audit], dtype=torch.bool
    )
    severity = torch.tensor(
        [float(row["delta_error"]) for row in audit], dtype=torch.float64
    )
    model = fit_logistic_score(
        calibration_matrix,
        calibration_labels,
        list(PROMOTED_FEATURES),
        l2=1e-2,
    )
    scores = predict_logistic_score(audit_matrix, model)
    primary_auroc = binary_auroc(primary_labels, scores)
    unsafe_auroc = binary_auroc(unsafe_labels, scores)
    primary_auprc = average_precision(primary_labels, scores)
    prevalence = float(primary_labels.double().mean())
    unsafe_rate = float(unsafe_labels.double().mean())
    family_auroc: dict[str, float] = {}
    for family in RISK_FAMILIES:
        mask = torch.tensor(
            [row["family"] == family for row in audit], dtype=torch.bool
        )
        family_auroc[family] = binary_auroc(
            primary_labels[mask], scores[mask]
        )
    top_count = max(1, math.ceil(0.20 * len(audit)))
    top_indices = torch.argsort(scores, descending=True, stable=True)[:top_count]
    top20_precision = float(primary_labels[top_indices].double().mean())
    primary_curve = risk_coverage(
        primary_labels, severity, scores, coverages=(0.5, 0.8, 1.0)
    )
    unsafe_curve = risk_coverage(
        unsafe_labels, severity, scores, coverages=(0.5, 0.8, 1.0)
    )
    unsafe_80 = next(
        float(row["failure_rate"])
        for row in unsafe_curve
        if row["coverage"] == 0.8
    )
    bootstrap = clustered_bootstrap_auc(
        [str(row["point_id"]) for row in audit],
        primary_labels,
        scores,
        samples=bootstrap_samples,
        seed=bootstrap_seed,
    )
    metrics: dict[str, object] = {
        "engineering_pass": True,
        "calibration_rows": len(calibration),
        "audit_rows": len(audit),
        "primary_auroc": primary_auroc,
        "unsafe_auroc": unsafe_auroc,
        "primary_auroc_ci_low": bootstrap["low"],
        "primary_auroc_ci_high": bootstrap["high"],
        "primary_auprc": primary_auprc,
        "primary_prevalence": prevalence,
        "unsafe_rate": unsafe_rate,
        "unsafe_rate_at_80pct_coverage": unsafe_80,
        "family_auroc": family_auroc,
        "top20_precision": top20_precision,
        "primary_risk_coverage": primary_curve,
        "unsafe_risk_coverage": unsafe_curve,
        "bootstrap_valid_samples": bootstrap["valid_samples"],
        "bootstrap_seed": bootstrap_seed,
    }
    gate = build_risk_gate(metrics)
    return {
        "model": model,
        "metrics": metrics,
        "gate": gate,
        "audit_scores": scores.tolist(),
    }


def package_risk_evidence(
    *,
    root: Path,
    include_paths: tuple[Path, ...],
    output_dir: Path,
    label: str,
) -> tuple[Path, Path, Path]:
    """Package P0 outputs using the repository's manifest convention."""

    return write_evidence_bundle(
        root=root,
        include_paths=include_paths,
        output_dir=output_dir,
        label=label,
        prefix="risk-development-evidence",
        manifest_name="risk-development-evidence-manifest.json",
    )


def _risk_evidence_inputs(
    *,
    root: Path,
    output_dir: Path,
    suite_path: Path,
    reference_path: Path,
    p5_archive_path: Path,
    p5_sidecar_path: Path,
) -> tuple[Path, ...]:
    """Return the self-contained P0 evidence input set."""

    return (
        output_dir,
        suite_path,
        suite_path.with_suffix(".sha256"),
        reference_path,
        reference_path.with_suffix(".sha256"),
        p5_archive_path,
        p5_sidecar_path,
        root / "block_kyfan_pinn/risk.py",
        root / "scripts/generate_risk_development.py",
        root / "scripts/evaluate_risk_features.py",
        root / "scripts/audit_p5_evidence.py",
        root / "tests/test_risk.py",
        root / "tests/test_risk_protocol_integrity.py",
        root / "requirements.txt",
    )


def _atomic_json(payload: object, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def _unit_provenance(
    *,
    suite_sha256: str,
    reference_sha256: str,
    archive_sha256: str,
    source_fingerprint: str,
    anchor_inventory: dict[str, object],
    candidate_inventory: dict[str, object],
) -> dict[str, object]:
    return {
        "suite_sha256": suite_sha256,
        "reference_sha256": reference_sha256,
        "archive_sha256": archive_sha256,
        "source_fingerprint": source_fingerprint,
        "anchor_checkpoint_sha256": anchor_inventory["checkpoint_sha256"],
        "candidate_checkpoint_sha256": candidate_inventory["checkpoint_sha256"],
        "feature_schema": list(PROMOTED_FEATURES),
    }


def _load_completed_unit(
    path: Path,
    expected_provenance: dict[str, object],
    *,
    expected_family: str,
    expected_seed: int,
    expected_points: dict[str, tuple[str, str]],
) -> list[dict[str, object]] | None:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if not path.is_file() and not sidecar.is_file():
        return None
    if not path.is_file() or not sidecar.is_file():
        raise ValueError(f"risk unit JSON and SHA-256 must coexist: {path}")
    tokens = sidecar.read_text().split()
    if not tokens or tokens[0] != file_sha256(path):
        raise ValueError(f"risk unit SHA-256 mismatch: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict) or payload.get("provenance") != expected_provenance:
        raise ValueError(f"risk unit provenance mismatch: {path}")
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != len(expected_points):
        raise ValueError(f"risk unit is incomplete: {path}")
    identities: set[str] = set()
    finite_fields = (
        *PROMOTED_FEATURES,
        "anchor_projector_error",
        "candidate_projector_error",
        "delta_error",
        "reference_internal_gap",
        "reference_external_gap",
    )
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"risk unit row is not an object: {path}")
        point_id = str(row.get("point_id", ""))
        expected_role_split = expected_points.get(point_id)
        if expected_role_split is None or point_id in identities:
            raise ValueError(f"risk unit point identity is invalid: {point_id}")
        identities.add(point_id)
        if row.get("family") != expected_family:
            raise ValueError(f"risk unit row has wrong family: {point_id}")
        if row.get("seed") != expected_seed:
            raise ValueError(f"risk unit row has wrong seed: {point_id}")
        if (row.get("role"), row.get("split")) != expected_role_split:
            raise ValueError(f"risk unit row role/split mismatch: {point_id}")
        if not all(
            field in row and math.isfinite(float(row[field]))
            for field in finite_fields
        ):
            raise ValueError(f"risk unit row has missing/non-finite fields: {point_id}")
        if not isinstance(row.get("regression"), bool) or not isinstance(
            row.get("unsafe_regression"), bool
        ):
            raise ValueError(f"risk unit row labels are not booleans: {point_id}")
    if identities != set(expected_points):
        raise ValueError(f"risk unit point set is incomplete: {path}")
    return rows


def _write_completed_unit(
    path: Path,
    provenance: dict[str, object],
    rows: list[dict[str, object]],
) -> None:
    _atomic_json({"provenance": provenance, "rows": rows}, path)
    digest = file_sha256(path)
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{digest}  {path.name}\n"
    )


def _write_features_csv(rows: list[dict[str, object]], path: Path) -> None:
    fieldnames = (
        "role",
        "family",
        "split",
        "point_id",
        "seed",
        *PROMOTED_FEATURES,
        "anchor_projector_error",
        "candidate_projector_error",
        "delta_error",
        "regression",
        "unsafe_regression",
        "reference_internal_gap",
        "reference_external_gap",
    )
    temporary = path.with_suffix(".csv.tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _report_markdown(
    result: dict[str, object], provenance: dict[str, object]
) -> str:
    metrics = result["metrics"]
    gate = result["gate"]
    status = (
        "RISK_DEVELOPMENT_GO" if gate["risk_go"] else "RISK_DEVELOPMENT_STOP"
    )
    return "\n".join(
        (
            "# P0 Risk-Development Report",
            "",
            "> Development evidence only. Frozen final was not read or evaluated.",
            "",
            f"- Status: `{status}`",
            f"- Primary audit AUROC: `{metrics['primary_auroc']:.6f}`",
            f"- Unsafe audit AUROC: `{metrics['unsafe_auroc']:.6f}`",
            f"- Primary audit AUPRC: `{metrics['primary_auprc']:.6f}`",
            f"- Primary prevalence: `{metrics['primary_prevalence']:.6f}`",
            f"- Suite SHA-256: `{provenance['suite_sha256']}`",
            f"- P5 archive SHA-256: `{provenance['archive_sha256']}`",
            "",
            "A STOP result forbids conditional-corrector implementation and P6 GPU execution.",
            "A GO result authorizes a separate conditional-corrector design, not frozen final.",
            "",
        )
    )


def run_risk_evaluation(args: argparse.Namespace) -> tuple[str, int]:
    """Run all six paired units and persist a deterministic P0 decision."""

    root = Path(__file__).resolve().parents[1]
    output_dir = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ("gate.json", "metrics.json", "calibration_model.json"):
        (output_dir / name).unlink(missing_ok=True)

    environment = _environment(root, args.device)
    if environment["git_status_porcelain"] and not args.allow_dirty:
        raise RuntimeError("risk evaluation requires a clean Git checkout")
    _atomic_json(environment, output_dir / "environment.json")
    device = select_device(args.device)

    suite_path = args.suite if args.suite.is_absolute() else root / args.suite
    suite, suite_hash = load_frozen_suite(suite_path)
    if suite.get("suite_id") != "block-kyfan-risk-development-v1-20260824":
        raise ValueError("unexpected risk-development suite")
    points = suite["points"]
    reference_path = (
        args.reference_cache
        if args.reference_cache.is_absolute()
        else root / args.reference_cache
    )
    references, reference_hash = _load_reference_cache(
        reference_path,
        suite_id=str(suite["suite_id"]),
        suite_hash=suite_hash,
        point_ids={str(point["id"]) for point in points},
        grid_side=33,
        cutoff=24,
    )
    reference_payload = torch.load(
        reference_path, map_location="cpu", weights_only=False
    )
    if reference_payload.get("metadata", {}).get("rank") != 3:
        raise ValueError("risk reference cache rank must be three")

    archive_path = args.archive if args.archive.is_absolute() else root / args.archive
    sidecar_path = args.sidecar if args.sidecar.is_absolute() else root / args.sidecar
    archive_hash = file_sha256(archive_path)
    risk_source_fingerprint = _risk_source_fingerprint(root)
    inventory = inventory_p5_checkpoints(archive_path, sidecar_path)
    _atomic_json(inventory, output_dir / "checkpoint_inventory.json")
    inventory_map = {
        (str(row["method"]), str(row["family"]), int(row["seed"])): row
        for row in inventory
    }

    unit_dir = output_dir / "units"
    unit_dir.mkdir(exist_ok=True)
    all_rows: list[dict[str, object]] = []
    for family in RISK_FAMILIES:
        family_points = [point for point in points if point["family"] == family]
        if len(family_points) != 80:
            raise ValueError(f"risk suite family count is not 80: {family}")
        for seed in RISK_SEEDS:
            anchor_row = inventory_map[("p5_anchor", family, seed)]
            candidate_row = inventory_map[("p5_static_low_rom", family, seed)]
            provenance = _unit_provenance(
                suite_sha256=suite_hash,
                reference_sha256=reference_hash,
                archive_sha256=archive_hash,
                source_fingerprint=risk_source_fingerprint,
                anchor_inventory=anchor_row,
                candidate_inventory=candidate_row,
            )
            unit_path = unit_dir / f"{family}_seed{seed}.json"
            expected_points = {
                str(point["id"]): (str(point["role"]), str(point["split"]))
                for point in family_points
            }
            completed = _load_completed_unit(
                unit_path,
                provenance,
                expected_family=family,
                expected_seed=seed,
                expected_points=expected_points,
            )
            if completed is not None:
                all_rows.extend(completed)
                continue
            anchor_model = load_p5_checkpoint(archive_path, anchor_row, device)
            candidate_model = load_p5_checkpoint(archive_path, candidate_row, device)
            rows = evaluate_paired_points(
                anchor_model,
                candidate_model,
                family_points,
                references,
                seed=seed,
                device=device,
            )
            _write_completed_unit(unit_path, provenance, rows)
            all_rows.extend(rows)
            print(f"RISK_UNIT_COMPLETE={family}:seed{seed}", flush=True)
    if len(all_rows) != 480:
        raise ValueError("risk evaluation did not produce 480 paired rows")
    identities = {
        (row["point_id"], row["seed"]) for row in all_rows
    }
    if len(identities) != 480:
        raise ValueError("risk paired row identities are duplicated")
    _write_features_csv(all_rows, output_dir / "features.csv")
    result = calibrate_and_audit(
        all_rows,
        bootstrap_samples=args.bootstrap_samples,
        bootstrap_seed=args.bootstrap_seed,
        expected_rows=480,
    )
    provenance = {
        "suite_sha256": suite_hash,
        "reference_sha256": reference_hash,
        "archive_sha256": archive_hash,
        "source_fingerprint": risk_source_fingerprint,
        "feature_schema": list(PROMOTED_FEATURES),
    }
    model_payload = {**result["model"], **provenance}
    metrics_payload = {**result["metrics"], **provenance}
    gate_payload = {**result["gate"], **provenance}
    _atomic_json(model_payload, output_dir / "calibration_model.json")
    _atomic_json(metrics_payload, output_dir / "metrics.json")
    _atomic_json(gate_payload, output_dir / "gate.json")
    (output_dir / "report.md").write_text(
        _report_markdown(result, provenance)
    )

    label = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    archive, sidecar, manifest = package_risk_evidence(
        root=root,
        include_paths=_risk_evidence_inputs(
            root=root,
            output_dir=output_dir,
            suite_path=suite_path,
            reference_path=reference_path,
            p5_archive_path=archive_path,
            p5_sidecar_path=sidecar_path,
        ),
        output_dir=root / "artifacts",
        label=label,
    )
    status = (
        "RISK_DEVELOPMENT_GO"
        if result["gate"]["risk_go"]
        else "RISK_DEVELOPMENT_STOP"
    )
    print(f"RISK_DEVELOPMENT_STATUS={status}")
    print(f"RISK_EVIDENCE_BUNDLE={archive}")
    print(f"RISK_EVIDENCE_SHA256={sidecar}")
    print(f"RISK_EVIDENCE_MANIFEST={manifest}")
    return status, 0 if status == "RISK_DEVELOPMENT_GO" else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--device", default="auto", choices=("auto", "cpu", "mps", "cuda", "rocm")
    )
    parser.add_argument(
        "--suite", type=Path, default=Path("benchmarks/risk_development_v1.json")
    )
    parser.add_argument(
        "--reference-cache",
        type=Path,
        default=Path("data/risk_development_v1_references.pt"),
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=Path("artifacts/p5-evidence-20260801-092048.tar.gz"),
    )
    parser.add_argument(
        "--sidecar",
        type=Path,
        default=Path("artifacts/p5-evidence-20260801-092048.tar.gz.sha256"),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("results/risk_development_v1")
    )
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260824)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    _, exit_code = run_risk_evaluation(args)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

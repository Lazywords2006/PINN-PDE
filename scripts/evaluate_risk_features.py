#!/usr/bin/env python3
"""Evaluate held-out label-free risk features from audited P5 checkpoints."""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tarfile
from collections import Counter
from pathlib import Path, PurePosixPath

import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.metrics import projector_sine_error
from block_kyfan_pinn.p5_model import build_p5_model
from block_kyfan_pinn.physics import (
    apply_hamiltonian,
    complex_gram_mean,
    periodic_mgs,
    projected_residual_rms,
    ritz_matrix,
)
from block_kyfan_pinn.reference import uniform_grid
from block_kyfan_pinn.risk import safe_log_ratio
from scripts.audit_p5_evidence import audit_p5_evidence

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

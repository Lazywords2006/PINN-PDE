"""Basis-invariant risk-gated correction for rank-two spectral subspaces."""

from __future__ import annotations

import math

import torch
from torch import Tensor

from .metrics import _complex_overlap
from .physics import periodic_mgs


def _validate_pair(anchor: Tensor, candidate: Tensor) -> None:
    if anchor.shape != candidate.shape:
        raise ValueError("anchor and candidate must have the same shape")
    if anchor.ndim != 4 or anchor.shape[-2:] != (2, 2):
        raise ValueError("bases must have shape [batch, points, 2, 2]")
    if not bool(torch.isfinite(anchor).all()) or not bool(
        torch.isfinite(candidate).all()
    ):
        raise ValueError("bases must be finite")


def _right_complex_multiply(basis: Tensor, matrix: Tensor) -> Tensor:
    matrix = matrix.to(device=basis.device)
    real = matrix.real.to(dtype=basis.dtype)
    imag = matrix.imag.to(dtype=basis.dtype)
    basis_real, basis_imag = basis[..., 0], basis[..., 1]
    output_real = torch.einsum("bni,bij->bnj", basis_real, real) - torch.einsum(
        "bni,bij->bnj", basis_imag, imag
    )
    output_imag = torch.einsum("bni,bij->bnj", basis_real, imag) + torch.einsum(
        "bni,bij->bnj", basis_imag, real
    )
    return torch.stack((output_real, output_imag), dim=-1)


def complex_procrustes_align(anchor: Tensor, candidate: Tensor) -> Tensor:
    """Align candidate columns to anchor without changing its projector."""

    _validate_pair(anchor, candidate)
    overlap = _complex_overlap(anchor, candidate)
    left, _, right_adjoint = torch.linalg.svd(overlap, full_matrices=False)
    rotation = right_adjoint.mH @ left.mH
    return _right_complex_multiply(candidate, rotation)


def risk_weight(score: Tensor, t_low: float, t_high: float) -> Tensor:
    """Map a failure-risk score to a monotone ROM correction weight."""

    if not t_low < t_high:
        raise ValueError("t_low must be strictly below t_high")
    score = torch.as_tensor(score)
    if score.ndim != 1 or not bool(torch.isfinite(score).all()):
        raise ValueError("score must be a finite one-dimensional tensor")
    return ((t_high - score) / (t_high - t_low)).clamp(0.0, 1.0)


def risk_chordal_correct(
    anchor: Tensor, candidate: Tensor, weight: Tensor
) -> Tensor:
    """Retract a Procrustes-aligned risk-controlled chordal correction."""

    _validate_pair(anchor, candidate)
    weight = torch.as_tensor(weight, device=anchor.device, dtype=anchor.dtype)
    if weight.shape != (anchor.shape[0],) or not bool(torch.isfinite(weight).all()):
        raise ValueError("weight must be one finite value per batch element")
    if bool(((weight < 0.0) | (weight > 1.0)).any()):
        raise ValueError("weight must lie in [0, 1]")
    aligned = complex_procrustes_align(anchor, candidate)
    raw = anchor + weight[:, None, None, None] * (aligned - anchor)
    return periodic_mgs(raw)


def hard_select(
    anchor: Tensor, candidate: Tensor, use_candidate: Tensor
) -> Tensor:
    """Select anchor or aligned candidate for each batch element."""

    _validate_pair(anchor, candidate)
    mask = torch.as_tensor(use_candidate, device=anchor.device)
    if mask.dtype is not torch.bool or mask.shape != (anchor.shape[0],):
        raise ValueError("use_candidate must be a Boolean batch mask")
    aligned = complex_procrustes_align(anchor, candidate)
    return torch.where(mask[:, None, None, None], aligned, anchor)


def build_p1_gate(summary: dict[str, object]) -> dict[str, object]:
    """Apply the frozen neural-only P1 pilot promotion requirements."""

    primary_near = float(summary["p1_risk_chordal_near_cluster_projector_mean"])
    long_near = float(summary["p5_long_anchor_near_cluster_projector_mean"])
    primary_gap = float(summary["p1_risk_chordal_gap_scan_projector_mean"])
    best_safe_gap = min(
        float(summary["p5_anchor_gap_scan_projector_mean"]),
        float(summary["p5_long_anchor_gap_scan_projector_mean"]),
    )
    primary_overall = float(summary["p1_risk_chordal_overall_projector_mean"])
    anchor_overall = float(summary["p5_anchor_overall_projector_mean"])
    rom_overall = float(summary["p5_static_low_rom_overall_projector_mean"])
    primary_unsafe = float(summary["p1_risk_chordal_unsafe_rate_vs_anchor"])
    rom_unsafe = float(summary["p5_static_low_rom_unsafe_rate_vs_anchor"])
    primary_latency = float(summary["p1_risk_chordal_latency_ms"])
    anchor_latency = float(summary["p5_anchor_latency_ms"])
    families = summary["family_near_projector_mean"]
    if not isinstance(families, dict) or set(families) != {
        "harmonic_honeycomb",
        "gaussian_honeycomb",
    }:
        raise ValueError("P1 summary must contain both potential families")
    family_pass = all(
        float(values["p1_risk_chordal"])
        < float(values["p5_long_anchor"])
        for values in families.values()
        if isinstance(values, dict)
    ) and all(isinstance(values, dict) for values in families.values())
    finite = (
        primary_near,
        long_near,
        primary_gap,
        best_safe_gap,
        primary_overall,
        anchor_overall,
        rom_overall,
        primary_unsafe,
        rom_unsafe,
        primary_latency,
        anchor_latency,
        float(summary["maximum_orthogonality_error"]),
        float(summary["p1_risk_chordal_pwe_fraction"]),
    )
    near_improvement = (
        (long_near - primary_near) / long_near if long_near > 0.0 else -math.inf
    )
    latency_ratio = (
        primary_latency / anchor_latency if anchor_latency > 0.0 else math.inf
    )
    checks = {
        "engineering_pass": bool(summary["engineering_pass"])
        and all(math.isfinite(value) for value in finite),
        "orthogonality_pass": float(summary["maximum_orthogonality_error"])
        < 1e-4,
        "near_improvement_pass": near_improvement >= 0.05,
        "gap_safety_pass": primary_gap <= 1.02 * best_safe_gap,
        "both_families_pass": family_pass,
        "paired_wins_pass": int(summary["paired_near_comparisons"]) == 6
        and int(summary["paired_near_wins_vs_long_anchor"]) >= 5,
        "overall_error_pass": primary_overall < anchor_overall
        and primary_overall < rom_overall,
        "unsafe_reduction_pass": rom_unsafe > 0.0
        and primary_unsafe <= 0.75 * rom_unsafe,
        "primary_zero_pwe_pass": float(summary["p1_risk_chordal_pwe_fraction"])
        == 0.0,
        "latency_pass": latency_ratio <= 2.5,
    }
    return {
        **checks,
        "near_improvement_fraction": near_improvement,
        "best_safe_gap": best_safe_gap,
        "latency_ratio": latency_ratio,
        "pilot_go": all(checks.values()),
    }

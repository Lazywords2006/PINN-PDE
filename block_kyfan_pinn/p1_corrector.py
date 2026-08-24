"""Basis-invariant risk-gated correction for rank-two spectral subspaces."""

from __future__ import annotations

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


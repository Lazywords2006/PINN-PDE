"""Basis-invariant spectral-cluster metrics."""

import math

import torch
from torch import Tensor


def _complex_overlap(left: Tensor, right: Tensor) -> Tensor:
    target_device = left.device if left.device.type == "cuda" else torch.device("cpu")
    left = left.detach().to(device=target_device, dtype=torch.float64)
    right = right.detach().to(device=target_device, dtype=torch.float64)
    left_real, left_imag = left[..., 0], left[..., 1]
    right_real, right_imag = right[..., 0], right[..., 1]
    real = torch.einsum("bni,bnj->bij", left_real, right_real) + torch.einsum(
        "bni,bnj->bij", left_imag, right_imag
    )
    imag = torch.einsum("bni,bnj->bij", left_real, right_imag) - torch.einsum(
        "bni,bnj->bij", left_imag, right_real
    )
    return torch.complex(real, imag) / left.shape[1]


def projector_sine_error(predicted: Tensor, reference: Tensor) -> float:
    if predicted.shape != reference.shape:
        raise ValueError("predicted and reference bases must have equal shape")
    cross = _complex_overlap(predicted, reference)
    overlap = cross.abs().square().sum(dim=(1, 2))
    rank = predicted.shape[2]
    error = torch.sqrt(((rank - overlap).clamp_min(0.0) / rank))
    return float(error.mean())


def principal_angle_degrees(predicted: Tensor, reference: Tensor) -> tuple[float, float]:
    """Return mean and maximum principal angle in degrees."""

    if predicted.shape != reference.shape:
        raise ValueError("predicted and reference bases must have equal shape")
    singular_values = torch.linalg.svdvals(_complex_overlap(predicted, reference)).clamp(0.0, 1.0)
    singular_values = torch.where(singular_values > 1.0 - 1e-7, torch.ones_like(singular_values), singular_values)
    angles = torch.acos(singular_values) * (180.0 / math.pi)
    return float(angles.mean().cpu()), float(angles.max().cpu())


def orthogonality_error(basis: Tensor) -> float:
    """Maximum absolute entry of Q*Q-I under cell-average quadrature."""

    overlap = _complex_overlap(basis, basis)
    identity = torch.eye(
        overlap.shape[-1], dtype=overlap.dtype, device=overlap.device
    ).expand_as(overlap)
    return float((overlap - identity).abs().max().cpu())

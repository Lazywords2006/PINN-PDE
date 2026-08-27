"""Reduced-order Fourier charts and basis-invariant routing utilities for P3."""

from __future__ import annotations

from collections.abc import Sequence

import torch
from torch import Tensor, nn

from .symmetry import legacy_hexagonal_shell_modes


def _k_point_modes(num_shells: int) -> list[tuple[int, int]]:
    """Return the reciprocal modes in ``num_shells`` hexagonal shells."""

    return legacy_hexagonal_shell_modes(num_shells)


def _build_rom_basis(coordinates: Tensor, modes: Sequence[tuple[int, int]]) -> Tensor:
    """Evaluate ``exp(i m·x)`` as real/imaginary pairs ``[B,P,M,2]``."""

    mode_tensor = coordinates.new_tensor(modes)
    phases = torch.einsum("bpd,md->bpm", coordinates, mode_tensor)
    return torch.stack((torch.cos(phases), torch.sin(phases)), dim=-1)


class ROMCoefficientNetwork(nn.Module):
    """Map PDE parameters to complex Fourier coefficients for each rank column."""

    def __init__(
        self,
        *,
        parameter_dim: int = 4,
        num_modes: int = 3,
        rank: int = 2,
        hidden_width: int = 64,
        hidden_layers: int = 2,
    ) -> None:
        super().__init__()
        if num_modes < 1 or rank < 1:
            raise ValueError("num_modes and rank must be positive")
        layers: list[nn.Module] = []
        in_features = parameter_dim
        for _ in range(hidden_layers):
            layers.extend((nn.Linear(in_features, hidden_width), nn.SiLU()))
            in_features = hidden_width
        output = nn.Linear(in_features, rank * num_modes * 2)
        nn.init.normal_(output.weight, std=1e-3)
        nn.init.zeros_(output.bias)
        layers.append(output)
        self.network = nn.Sequential(*layers)
        self.num_modes = num_modes
        self.rank = rank

    def forward(self, parameters: Tensor) -> Tensor:
        """Return coefficients shaped ``[B,rank,num_modes,real_imag]``."""

        raw = self.network(parameters)
        return raw.reshape(parameters.shape[0], self.rank, self.num_modes, 2)


def parametric_rom_anchor(
    coordinates: Tensor,
    parameters: Tensor,
    coefficient_network: ROMCoefficientNetwork,
    *,
    modes: list[tuple[int, int]],
    anchor_scale: float = 1.0,
) -> Tensor:
    """Evaluate a parameter-dependent complex Fourier correction ``[B,P,R,2]``."""

    if parameters.shape[0] != coordinates.shape[0]:
        raise ValueError("batch sizes of coordinates and parameters must match")
    if len(modes) != coefficient_network.num_modes:
        raise ValueError("mode count does not match coefficient network")
    waves = _build_rom_basis(coordinates, modes)
    coefficients = coefficient_network(parameters)
    wave_real, wave_imag = waves[..., 0], waves[..., 1]
    coefficient_real = coefficients[..., 0]
    coefficient_imag = coefficients[..., 1]
    real = torch.einsum("bpm,brm->bpr", wave_real, coefficient_real) - torch.einsum(
        "bpm,brm->bpr", wave_imag, coefficient_imag
    )
    imag = torch.einsum("bpm,brm->bpr", wave_real, coefficient_imag) + torch.einsum(
        "bpm,brm->bpr", wave_imag, coefficient_real
    )
    return anchor_scale * torch.stack((real, imag), dim=-1)


def _normalized_weights(raw: Tensor, m_weights: Tensor | None) -> Tensor:
    batch, points = raw.shape[:2]
    if m_weights is None:
        weights = raw.new_ones(batch, points)
    elif m_weights.ndim == 1 and m_weights.shape[0] == points:
        weights = m_weights.to(device=raw.device, dtype=raw.dtype).expand(batch, -1)
    elif m_weights.shape == (batch, points):
        weights = m_weights.to(device=raw.device, dtype=raw.dtype)
    else:
        raise ValueError("m_weights must have shape [points] or [batch, points]")
    if bool((weights < 0).any().detach().cpu()):
        raise ValueError("m_weights must be non-negative")
    return weights / weights.sum(dim=1, keepdim=True).clamp_min(1e-14)


def m_weighted_gram_mean(
    basis: Tensor, m_weights: Tensor | None = None
) -> tuple[Tensor, Tensor]:
    """Return the per-sample complex Gram matrix under positive weights."""

    if basis.ndim != 4 or basis.shape[-1] != 2:
        raise ValueError("basis must have shape [batch, points, rank, 2]")
    weights = _normalized_weights(basis, m_weights)
    real, imag = basis[..., 0], basis[..., 1]
    real_gram = torch.einsum("bp,bpi,bpj->bij", weights, real, real) + torch.einsum(
        "bp,bpi,bpj->bij", weights, imag, imag
    )
    imag_gram = torch.einsum("bp,bpi,bpj->bij", weights, real, imag) - torch.einsum(
        "bp,bpi,bpj->bij", weights, imag, real
    )
    return real_gram, imag_gram


def m_weighted_gram_schmidt(
    raw: Tensor, m_weights: Tensor | None = None, eps: float = 1e-7
) -> Tensor:
    """Weighted complex modified Gram–Schmidt with per-sample weights."""

    if raw.ndim != 4 or raw.shape[-1] != 2:
        raise ValueError("raw must have shape [batch, points, rank, 2]")
    weights = _normalized_weights(raw, m_weights)
    columns: list[Tensor] = []
    for index in range(raw.shape[2]):
        vector = raw[:, :, index]
        for q in columns:
            coefficient_real = torch.einsum(
                "bp,bp->b",
                weights,
                q[..., 0] * vector[..., 0] + q[..., 1] * vector[..., 1],
            ).detach()
            coefficient_imag = torch.einsum(
                "bp,bp->b",
                weights,
                q[..., 0] * vector[..., 1] - q[..., 1] * vector[..., 0],
            ).detach()
            projection = torch.stack(
                (
                    q[..., 0] * coefficient_real[:, None]
                    - q[..., 1] * coefficient_imag[:, None],
                    q[..., 0] * coefficient_imag[:, None]
                    + q[..., 1] * coefficient_real[:, None],
                ),
                dim=-1,
            )
            vector = vector - projection
        norm = torch.sqrt(
            torch.einsum("bp,bp->b", weights, vector.square().sum(-1)).clamp_min(eps * eps)
        )
        if bool((norm.detach() <= eps).any().cpu()):
            raise ValueError("rank-deficient complex basis under weighted norm")
        columns.append(vector / norm.detach()[:, None, None])
    return torch.stack(columns, dim=2)


def chart_partition(
    normalized_parameters: Tensor,
    chart_centers: Tensor | Sequence[tuple[float, ...]],
    temperature: float = 0.5,
) -> Tensor:
    """Return a smooth partition of unity in normalized parameter space."""

    if temperature <= 0:
        raise ValueError("temperature must be positive")
    centers = torch.as_tensor(
        chart_centers,
        device=normalized_parameters.device,
        dtype=normalized_parameters.dtype,
    )
    if centers.ndim != 2 or centers.shape[1] != normalized_parameters.shape[1]:
        raise ValueError("chart centers must have shape [charts, parameter_dim]")
    distances = (normalized_parameters[:, None, :] - centers[None, :, :]).square().sum(-1)
    return torch.softmax(-distances / temperature, dim=-1)


def chart_disagreement_risk(basis_a: Tensor, basis_b: Tensor) -> Tensor:
    """Return one basis-invariant principal-angle disagreement per sample."""

    from .metrics import _complex_overlap

    singular_values = torch.linalg.svdvals(_complex_overlap(basis_a, basis_b)).clamp(0.0, 1.0)
    return 1.0 - singular_values.square().mean(dim=-1)


def should_fallback(
    residual_risk: Tensor,
    chart_risk: Tensor | float,
    *,
    residual_threshold: float = 0.5,
    chart_threshold: float = 0.3,
) -> Tensor:
    """Return a per-sample fallback mask from label-free risk signals."""

    chart_tensor = torch.as_tensor(
        chart_risk, device=residual_risk.device, dtype=residual_risk.dtype
    )
    return (residual_risk > residual_threshold) | (chart_tensor > chart_threshold)

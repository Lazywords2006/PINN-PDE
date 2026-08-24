"""Basis-invariant neural-augmented Rayleigh--Ritz refinement."""

from __future__ import annotations

from collections.abc import Sequence

import torch
from torch import Tensor

from .p3_rom import _build_rom_basis
from .physics import galerkin_rank_basis, periodic_mgs


def hex_shell_modes(num_shells: int) -> list[tuple[int, int]]:
    """Return every reciprocal mode through a closed hexagonal shell."""

    if num_shells < 0:
        raise ValueError("num_shells must be non-negative")
    return sorted(
        (m1, m2)
        for m1 in range(-num_shells, num_shells + 1)
        for m2 in range(-num_shells, num_shells + 1)
        if max(abs(m1), abs(m2), abs(m1 - m2)) <= num_shells
    )


def outer_shell_modes(shell: int) -> list[tuple[int, int]]:
    """Return only reciprocal modes on one positive hexagonal shell."""

    if shell < 1:
        raise ValueError("shell must be positive")
    return [
        mode
        for mode in hex_shell_modes(shell)
        if max(abs(mode[0]), abs(mode[1]), abs(mode[0] - mode[1])) == shell
    ]


def _remove_projection(vector: Tensor, column: Tensor) -> Tensor:
    coefficient_real = (
        column[..., 0] * vector[..., 0]
        + column[..., 1] * vector[..., 1]
    ).mean(1)
    coefficient_imag = (
        column[..., 0] * vector[..., 1]
        - column[..., 1] * vector[..., 0]
    ).mean(1)
    projection_real = (
        column[..., 0] * coefficient_real[:, None]
        - column[..., 1] * coefficient_imag[:, None]
    )
    projection_imag = (
        column[..., 0] * coefficient_imag[:, None]
        + column[..., 1] * coefficient_real[:, None]
    )
    return vector - torch.stack((projection_real, projection_imag), dim=-1)


def orthogonal_analytic_augmentation(
    neural_basis: Tensor,
    coordinates: Tensor,
    modes: Sequence[tuple[int, int]],
    *,
    tolerance: float = 1e-5,
) -> tuple[Tensor, list[tuple[int, int]]]:
    """Append analytic modes not already represented by the neural subspace."""

    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    if neural_basis.ndim != 4 or neural_basis.shape[-1] != 2:
        raise ValueError("neural_basis must have shape [batch, points, rank, 2]")
    if coordinates.shape[:2] != neural_basis.shape[:2]:
        raise ValueError("coordinates and neural_basis must share batch and points")
    selected_modes = list(modes)
    if not selected_modes or len(set(selected_modes)) != len(selected_modes):
        raise ValueError("modes must be non-empty and unique")

    neural = periodic_mgs(neural_basis)
    columns = [neural[:, :, index] for index in range(neural.shape[2])]
    waves = _build_rom_basis(coordinates, selected_modes)
    accepted: list[tuple[int, int]] = []
    for mode_index, mode in enumerate(selected_modes):
        vector = waves[:, :, mode_index]
        for column in columns:
            vector = _remove_projection(vector, column)
        norm = torch.sqrt(vector.square().sum(-1).mean(1).clamp_min(0.0))
        if not bool((norm > tolerance).all().detach().cpu()):
            continue
        normalized = vector / norm[:, None, None]
        columns.append(normalized)
        accepted.append(mode)
    trial = torch.stack(columns, dim=2)
    return periodic_mgs(trial), accepted


def neural_augmented_ritz(
    neural_basis: Tensor,
    coordinates: Tensor,
    parameters: Tensor,
    potential_family: str,
    modes: Sequence[tuple[int, int]],
    *,
    tolerance: float = 1e-5,
) -> tuple[Tensor, dict[str, object]]:
    """Extract the lowest rank-two Ritz space from neural plus analytic modes."""

    trial, accepted = orthogonal_analytic_augmentation(
        neural_basis, coordinates, modes, tolerance=tolerance
    )
    if trial.shape[2] < 2:
        raise ValueError("augmented trial space has insufficient rank")
    basis = galerkin_rank_basis(
        trial,
        coordinates,
        parameters,
        potential_family,
        target_rank=2,
    )
    return basis, {
        "trial_rank": trial.shape[2],
        "accepted_mode_count": len(accepted),
        "accepted_modes": accepted,
    }


def fourier_only_ritz(
    coordinates: Tensor,
    parameters: Tensor,
    potential_family: str,
    modes: Sequence[tuple[int, int]],
) -> Tensor:
    """Return a same-dictionary Fourier-only Rayleigh--Ritz control."""

    selected_modes = list(modes)
    if len(selected_modes) < 2 or len(set(selected_modes)) != len(selected_modes):
        raise ValueError("Fourier control requires at least two unique modes")
    trial = periodic_mgs(_build_rom_basis(coordinates, selected_modes))
    return galerkin_rank_basis(
        trial,
        coordinates,
        parameters,
        potential_family,
        target_rank=2,
    )


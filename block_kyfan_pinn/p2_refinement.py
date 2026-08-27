"""Basis-invariant neural-augmented Rayleigh--Ritz refinement."""

from __future__ import annotations

import math
from collections.abc import Sequence

import torch
from torch import Tensor

from .p3_rom import _build_rom_basis
from .physics import (
    apply_hamiltonian,
    galerkin_rank_basis,
    hermitian_ritz_matrix,
    periodic_mgs,
    periodic_potential,
)
from .symmetry import (
    hexagonal_shell_index,
    hexagonal_shell_modes,
    legacy_hexagonal_shell_index,
    legacy_hexagonal_shell_modes,
)


def hex_shell_modes(num_shells: int) -> list[tuple[int, int]]:
    """Return the archived V2 dictionary without changing old evidence."""

    return legacy_hexagonal_shell_modes(num_shells)


def d6_hex_shell_modes(num_shells: int) -> list[tuple[int, int]]:
    """Return the D6 closure consistent with the positive-cross metric."""

    return hexagonal_shell_modes(num_shells)


def outer_shell_modes(shell: int) -> list[tuple[int, int]]:
    """Return only reciprocal modes on one positive hexagonal shell."""

    if shell < 1:
        raise ValueError("shell must be positive")
    return [
        mode
        for mode in hex_shell_modes(shell)
        if legacy_hexagonal_shell_index(mode) == shell
    ]


def d6_outer_shell_modes(shell: int) -> list[tuple[int, int]]:
    if shell < 1:
        raise ValueError("shell must be positive")
    return [
        mode
        for mode in d6_hex_shell_modes(shell)
        if hexagonal_shell_index(mode) == shell
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
    # Cell quadrature coefficients are global constants for spatial
    # differentiation, matching the repository's periodic MGS convention.
    coefficient_real = coefficient_real.detach()
    coefficient_imag = coefficient_imag.detach()
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
        norm = norm.detach()
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


def analytic_fourier_hamiltonian(
    coordinates: Tensor,
    parameters: Tensor,
    potential_family: str,
    modes: Sequence[tuple[int, int]],
) -> Tensor:
    """Apply the Bloch Hamiltonian analytically to periodic plane waves."""

    selected_modes = list(modes)
    waves = _build_rom_basis(coordinates, selected_modes)
    mode_tensor = coordinates.new_tensor(selected_modes)
    shifted = mode_tensor[None] + parameters[:, None, :2]
    first, second = shifted.unbind(-1)
    kinetic = 0.5 * (first.square() + second.square() + first * second)
    potential = periodic_potential(
        coordinates, parameters, potential_family
    )
    multiplier = potential[:, :, None] + kinetic[:, None, :]
    return waves * multiplier[..., None]


def _subtract_complex_multiple(
    vector: Tensor, column: Tensor, coefficient_real: Tensor, coefficient_imag: Tensor
) -> Tensor:
    real = (
        column[..., 0] * coefficient_real[:, None]
        - column[..., 1] * coefficient_imag[:, None]
    )
    imag = (
        column[..., 0] * coefficient_imag[:, None]
        + column[..., 1] * coefficient_real[:, None]
    )
    return vector - torch.stack((real, imag), dim=-1)


def _paired_append(
    vector: Tensor,
    h_vector: Tensor,
    columns: list[Tensor],
    h_columns: list[Tensor],
    *,
    tolerance: float,
) -> bool:
    for column, h_column in zip(columns, h_columns, strict=True):
        coefficient_real = (
            column[..., 0] * vector[..., 0]
            + column[..., 1] * vector[..., 1]
        ).mean(1)
        coefficient_imag = (
            column[..., 0] * vector[..., 1]
            - column[..., 1] * vector[..., 0]
        ).mean(1)
        coefficient_real = coefficient_real.detach()
        coefficient_imag = coefficient_imag.detach()
        vector = _subtract_complex_multiple(
            vector, column, coefficient_real, coefficient_imag
        )
        h_vector = _subtract_complex_multiple(
            h_vector, h_column, coefficient_real, coefficient_imag
        )
    norm = torch.sqrt(vector.square().sum(-1).mean(1).clamp_min(0.0))
    if not bool((norm > tolerance).all().detach().cpu()):
        return False
    # Equal-weight quadrature coefficients are constants for spatial
    # differentiation. Detaching the normalization preserves H(cw)=cH(w)
    # for the paired analytic action and avoids nonlocal grid derivatives.
    norm = norm.detach()
    columns.append(vector / norm[:, None, None])
    h_columns.append(h_vector / norm[:, None, None])
    return True


def _select_low_ritz(trial: Tensor, h_trial: Tensor) -> Tensor:
    matrix = hermitian_ritz_matrix(trial, h_trial)
    target_device = trial.device
    if target_device.type == "mps":
        matrix = matrix.cpu()
    _, eigenvectors = torch.linalg.eigh(matrix)
    coefficients = eigenvectors[..., :2].detach()
    real = coefficients.real.to(device=target_device, dtype=trial.dtype)
    imag = coefficients.imag.to(device=target_device, dtype=trial.dtype)
    trial_real, trial_imag = trial[..., 0], trial[..., 1]
    selected_real = torch.einsum(
        "bnm,bmr->bnr", trial_real, real
    ) - torch.einsum("bnm,bmr->bnr", trial_imag, imag)
    selected_imag = torch.einsum(
        "bnm,bmr->bnr", trial_real, imag
    ) + torch.einsum("bnm,bmr->bnr", trial_imag, real)
    return periodic_mgs(torch.stack((selected_real, selected_imag), dim=-1))


def neural_augmented_ritz_fast(
    neural_basis: Tensor,
    coordinates: Tensor,
    parameters: Tensor,
    potential_family: str,
    modes: Sequence[tuple[int, int]],
    *,
    tolerance: float = 1e-5,
) -> tuple[Tensor, dict[str, object]]:
    """Refine with analytic Fourier Hamiltonians and paired orthogonalization."""

    neural = periodic_mgs(neural_basis)
    h_neural = apply_hamiltonian(
        neural, coordinates, parameters, potential_family
    )
    columns = [neural[:, :, index] for index in range(neural.shape[2])]
    h_columns = [h_neural[:, :, index] for index in range(h_neural.shape[2])]
    selected_modes = list(modes)
    waves = _build_rom_basis(coordinates, selected_modes)
    h_waves = analytic_fourier_hamiltonian(
        coordinates, parameters, potential_family, selected_modes
    )
    accepted: list[tuple[int, int]] = []
    for index, mode in enumerate(selected_modes):
        if _paired_append(
            waves[:, :, index],
            h_waves[:, :, index],
            columns,
            h_columns,
            tolerance=tolerance,
        ):
            accepted.append(mode)
    trial = torch.stack(columns, dim=2)
    h_trial = torch.stack(h_columns, dim=2)
    return _select_low_ritz(trial, h_trial), {
        "trial_rank": trial.shape[2],
        "accepted_mode_count": len(accepted),
        "accepted_modes": accepted,
    }


def fourier_only_ritz_fast(
    coordinates: Tensor,
    parameters: Tensor,
    potential_family: str,
    modes: Sequence[tuple[int, int]],
    *,
    tolerance: float = 1e-5,
) -> Tensor:
    """Evaluate the Fourier-only control without per-column autodiff."""

    selected_modes = list(modes)
    waves = _build_rom_basis(coordinates, selected_modes)
    h_waves = analytic_fourier_hamiltonian(
        coordinates, parameters, potential_family, selected_modes
    )
    columns: list[Tensor] = []
    h_columns: list[Tensor] = []
    for index in range(len(selected_modes)):
        _paired_append(
            waves[:, :, index],
            h_waves[:, :, index],
            columns,
            h_columns,
            tolerance=tolerance,
        )
    if len(columns) < 2:
        raise ValueError("Fourier-only analytic trial space has insufficient rank")
    return _select_low_ritz(
        torch.stack(columns, dim=2), torch.stack(h_columns, dim=2)
    )


def _basis_ritz_trace(
    basis: Tensor,
    coordinates: Tensor,
    parameters: Tensor,
    potential_family: str,
) -> Tensor:
    h_basis = apply_hamiltonian(
        basis, coordinates, parameters, potential_family
    )
    matrix = hermitian_ritz_matrix(basis, h_basis)
    output_device = matrix.device
    if output_device.type == "mps":
        matrix = matrix.cpu()
    values = torch.linalg.eigvalsh(matrix).real[..., :2].sum(-1)
    return values.to(output_device)


def guarded_neural_fourier_ritz(
    neural_basis: Tensor,
    coordinates: Tensor,
    parameters: Tensor,
    potential_family: str,
    *,
    hybrid_modes: Sequence[tuple[int, int]],
    pure_modes: Sequence[tuple[int, int]],
    tolerance: float = 1e-5,
) -> tuple[Tensor, dict[str, object]]:
    """Select a hybrid or pure-Fourier Ritz space by label-free trace."""

    hybrid, hybrid_details = neural_augmented_ritz_fast(
        neural_basis,
        coordinates,
        parameters,
        potential_family,
        hybrid_modes,
        tolerance=tolerance,
    )
    pure = fourier_only_ritz_fast(
        coordinates,
        parameters,
        potential_family,
        pure_modes,
        tolerance=tolerance,
    )
    hybrid_trace = _basis_ritz_trace(
        hybrid, coordinates, parameters, potential_family
    )
    pure_trace = _basis_ritz_trace(
        pure, coordinates, parameters, potential_family
    )
    choose_hybrid = (hybrid_trace <= pure_trace).detach()
    mask = choose_hybrid.to(neural_basis.device)[:, None, None, None]
    selected = torch.where(mask, hybrid, pure)
    selected_trace = torch.where(choose_hybrid, hybrid_trace, pure_trace)
    return selected, {
        "choose_hybrid": choose_hybrid.cpu().tolist(),
        "hybrid_trace": hybrid_trace.detach().cpu().tolist(),
        "pure_trace": pure_trace.detach().cpu().tolist(),
        "selected_trace": selected_trace.detach().cpu().tolist(),
        "hybrid_trial_rank": int(hybrid_details["trial_rank"]),
        "pure_trial_rank": len(pure_modes),
    }


def potential_spectral_tail_ratio(
    coordinates: Tensor,
    parameters: Tensor,
    potential_family: str,
    *,
    resolved_shell: int = 1,
) -> Tensor:
    """Measure potential Fourier energy outside a resolved D6 shell."""

    side = math.isqrt(coordinates.shape[1])
    if side * side != coordinates.shape[1]:
        raise ValueError("spectral routing requires a square periodic grid")
    values = periodic_potential(
        coordinates, parameters, potential_family
    ).reshape(coordinates.shape[0], side, side)
    coefficients = torch.fft.fft2(values, norm="forward")
    mask = torch.zeros((side, side), dtype=torch.bool, device=coordinates.device)
    for first_index in range(side):
        first = first_index if first_index <= side // 2 else first_index - side
        for second_index in range(side):
            second = (
                second_index
                if second_index <= side // 2
                else second_index - side
            )
            if hexagonal_shell_index((first, second)) > resolved_shell:
                mask[first_index, second_index] = True
    energy = coefficients.abs().square()
    total = energy.sum(dim=(-2, -1)).clamp_min(1e-20)
    return energy[:, mask].sum(-1) / total


def spectral_routed_neural_fourier_ritz(
    neural_basis: Tensor,
    coordinates: Tensor,
    parameters: Tensor,
    potential_family: str,
    *,
    hybrid_modes: Sequence[tuple[int, int]],
    pure_modes: Sequence[tuple[int, int]],
    threshold: float = 0.1,
    tolerance: float = 1e-5,
) -> tuple[Tensor, dict[str, object]]:
    """Route spectrally rich potentials to neural augmentation without labels."""

    if neural_basis.shape[0] != 1:
        raise ValueError("route batches by spectral class before calling this function")
    tail_ratio = potential_spectral_tail_ratio(
        coordinates, parameters, potential_family
    )
    if float(tail_ratio.detach().cpu()[0]) > threshold:
        basis, details = neural_augmented_ritz_fast(
            neural_basis,
            coordinates,
            parameters,
            potential_family,
            hybrid_modes,
            tolerance=tolerance,
        )
        return basis, {
            "route": "hybrid",
            "tail_ratio": float(tail_ratio.detach().cpu()[0]),
            "trial_rank": int(details["trial_rank"]),
        }
    basis = fourier_only_ritz_fast(
        coordinates,
        parameters,
        potential_family,
        pure_modes,
        tolerance=tolerance,
    )
    return basis, {
        "route": "fourier",
        "tail_ratio": float(tail_ratio.detach().cpu()[0]),
        "trial_rank": len(pure_modes),
    }

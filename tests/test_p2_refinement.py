"""Unit tests for P2 neural-augmented Galerkin refinement."""

from __future__ import annotations

import torch

from block_kyfan_pinn.metrics import orthogonality_error, projector_sine_error
from block_kyfan_pinn.model import BlockKyFanPINN
from block_kyfan_pinn.p2_refinement import (
    fourier_only_ritz,
    hex_shell_modes,
    neural_augmented_ritz,
    orthogonal_analytic_augmentation,
    outer_shell_modes,
)
from block_kyfan_pinn.p3_rom import _build_rom_basis
from block_kyfan_pinn.physics import periodic_mgs
from block_kyfan_pinn.reference import uniform_grid


def _complex_rotate(basis: torch.Tensor) -> torch.Tensor:
    raw = torch.tensor(
        [[1.0 + 0.3j, -0.2 + 0.8j], [0.4 - 0.6j, 0.9 + 0.1j]],
        dtype=torch.complex64,
    )
    unitary, _ = torch.linalg.qr(raw)
    values = torch.complex(basis[..., 0], basis[..., 1])
    rotated = torch.einsum("bni,ij->bnj", values, unitary)
    return torch.stack((rotated.real, rotated.imag), dim=-1)


def test_hexagonal_mode_counts_are_exact() -> None:
    assert len(hex_shell_modes(0)) == 1
    assert len(hex_shell_modes(1)) == 7
    assert len(hex_shell_modes(2)) == 19
    assert len(outer_shell_modes(1)) == 6
    assert len(outer_shell_modes(2)) == 12


def test_duplicate_analytic_modes_are_rejected() -> None:
    coordinates = uniform_grid(9).unsqueeze(0).requires_grad_()
    duplicate_modes = [(0, 0), (1, 0)]
    neural = periodic_mgs(_build_rom_basis(coordinates, duplicate_modes))

    trial, accepted = orthogonal_analytic_augmentation(
        neural, coordinates, duplicate_modes, tolerance=1e-5
    )

    assert trial.shape[2] == 2
    assert accepted == []
    assert orthogonality_error(trial) < 1e-6


def test_neural_augmented_ritz_is_u2_invariant_and_orthonormal() -> None:
    coordinates = uniform_grid(9).unsqueeze(0).requires_grad_()
    parameters = torch.tensor([[1 / 3, 1 / 3, 0.5, 0.0]])
    neural = periodic_mgs(BlockKyFanPINN.anchor(coordinates, "correct"))
    rotated = _complex_rotate(neural)
    modes = outer_shell_modes(2)

    first, first_info = neural_augmented_ritz(
        neural, coordinates, parameters, "harmonic_honeycomb", modes
    )
    second, second_info = neural_augmented_ritz(
        rotated, coordinates, parameters, "harmonic_honeycomb", modes
    )

    assert first.shape == neural.shape
    assert first_info["accepted_mode_count"] == len(modes)
    assert second_info["accepted_modes"] == first_info["accepted_modes"]
    assert orthogonality_error(first) < 1e-5
    assert projector_sine_error(first, second) < 1e-5


def test_fourier_only_ritz_returns_rank_two_projector() -> None:
    coordinates = uniform_grid(9).unsqueeze(0).requires_grad_()
    parameters = torch.tensor([[1 / 3, 1 / 3, 0.5, 0.0]])

    basis = fourier_only_ritz(
        coordinates,
        parameters,
        "harmonic_honeycomb",
        hex_shell_modes(2),
    )

    assert basis.shape == (1, 81, 2, 2)
    assert orthogonality_error(basis) < 1e-5


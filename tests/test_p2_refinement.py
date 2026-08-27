"""Unit tests for P2 neural-augmented Galerkin refinement."""

from __future__ import annotations

import torch

from block_kyfan_pinn.metrics import orthogonality_error, projector_sine_error
from block_kyfan_pinn.model import BlockKyFanPINN
from block_kyfan_pinn.p2_refinement import (
    analytic_fourier_hamiltonian,
    d6_hex_shell_modes,
    fourier_only_ritz,
    fourier_only_ritz_fast,
    guarded_neural_fourier_ritz,
    hex_shell_modes,
    neural_augmented_ritz,
    neural_augmented_ritz_fast,
    orthogonal_analytic_augmentation,
    outer_shell_modes,
    potential_spectral_tail_ratio,
    spectral_routed_neural_fourier_ritz,
)
from block_kyfan_pinn.p3_rom import _build_rom_basis
from block_kyfan_pinn.physics import (
    apply_hamiltonian,
    hermitian_ritz_matrix,
    periodic_mgs,
    ritz_matrix,
)
from block_kyfan_pinn.reference import uniform_grid
from block_kyfan_pinn.symmetry import lowest_kinetic_modes


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


def test_hexagonal_modes_match_the_positive_cross_metric() -> None:
    first_shell = set(d6_hex_shell_modes(1))
    assert first_shell == {
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 0),
        (0, 1),
        (1, -1),
        (1, 0),
    }

    second_shell = set(d6_hex_shell_modes(2))

    def rotate(mode: tuple[int, int]) -> tuple[int, int]:
        first, second = mode
        return -second, first + second

    assert {rotate(mode) for mode in second_shell} == second_shell
    assert {(second, first) for first, second in second_shell} == second_shell
    assert all(
        first * first + second * second + first * second <= 4
        for first, second in second_shell
    )


def test_lowest_kinetic_control_closes_boundary_ties_at_k() -> None:
    modes = lowest_kinetic_modes((1 / 3, 1 / 3), rank=25, candidate_shell=4)
    assert len(modes) == 27

    def energy(mode: tuple[int, int]) -> float:
        first = mode[0] + 1 / 3
        second = mode[1] + 1 / 3
        return 0.5 * (first * first + second * second + first * second)

    selected_max = max(energy(mode) for mode in modes)
    candidates = d6_hex_shell_modes(4)
    assert all(
        mode in modes for mode in candidates if abs(energy(mode) - selected_max) < 1e-12
    )
    rounded_k = torch.tensor([1 / 3, 1 / 3], dtype=torch.float32).tolist()
    assert len(lowest_kinetic_modes(rounded_k, rank=25, candidate_shell=4)) == 27


def test_hermitian_ritz_matrix_removes_collocation_skew_part() -> None:
    torch.manual_seed(1201)
    basis = torch.randn(2, 17, 3, 2)
    h_basis = torch.randn(2, 17, 3, 2)
    matrix = hermitian_ritz_matrix(basis, h_basis)
    assert torch.allclose(matrix, matrix.mH, atol=1e-7)


def test_duplicate_analytic_modes_are_rejected() -> None:
    coordinates = uniform_grid(17).unsqueeze(0).requires_grad_()
    duplicate_modes = [(0, 0), (1, 0)]
    neural = periodic_mgs(_build_rom_basis(coordinates, duplicate_modes))

    trial, accepted = orthogonal_analytic_augmentation(
        neural, coordinates, duplicate_modes, tolerance=1e-5
    )

    assert trial.shape[2] == 2
    assert accepted == []
    assert orthogonality_error(trial) < 1e-6


def test_neural_augmented_ritz_is_u2_invariant_and_orthonormal() -> None:
    coordinates = uniform_grid(17).unsqueeze(0).requires_grad_()
    parameters = torch.tensor([[1 / 3, 1 / 3, 0.5, 0.0]])
    neural = periodic_mgs(BlockKyFanPINN.anchor(coordinates, "correct"))
    rotated = _complex_rotate(neural)
    modes = outer_shell_modes(2)

    first, first_info = neural_augmented_ritz_fast(
        neural, coordinates, parameters, "harmonic_honeycomb", modes
    )
    second, second_info = neural_augmented_ritz_fast(
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


def test_analytic_fourier_hamiltonian_matches_autodiff_refinement() -> None:
    coordinates = uniform_grid(9).unsqueeze(0).requires_grad_()
    parameters = torch.tensor([[0.34, 0.32, 0.5, 0.01]])
    neural = periodic_mgs(BlockKyFanPINN.anchor(coordinates, "correct"))
    modes = outer_shell_modes(2)

    analytic_h = analytic_fourier_hamiltonian(
        coordinates, parameters, "harmonic_honeycomb", modes
    )
    slow, _ = neural_augmented_ritz(
        neural, coordinates, parameters, "harmonic_honeycomb", modes
    )
    fast, fast_info = neural_augmented_ritz_fast(
        neural, coordinates, parameters, "harmonic_honeycomb", modes
    )

    assert analytic_h.shape == (1, 81, len(modes), 2)
    assert fast_info["accepted_mode_count"] == len(modes)
    assert projector_sine_error(slow, fast) < 1e-4


def test_fast_fourier_only_matches_autodiff_control() -> None:
    coordinates = uniform_grid(9).unsqueeze(0).requires_grad_()
    parameters = torch.tensor([[0.34, 0.32, 0.5, 0.01]])
    modes = d6_hex_shell_modes(2)

    slow = fourier_only_ritz(
        coordinates, parameters, "harmonic_honeycomb", modes
    )
    fast = fourier_only_ritz_fast(
        coordinates, parameters, "harmonic_honeycomb", modes
    )

    assert projector_sine_error(slow, fast) < 1e-4
    assert orthogonality_error(fast) < 1e-5


def test_anchor_augmented_closed_shell_preserves_self_adjoint_action() -> None:
    coordinates = uniform_grid(17).unsqueeze(0).requires_grad_()
    parameters = torch.tensor([[0.34, 0.32, 2.4, 0.29, 0.03]])
    modes = d6_hex_shell_modes(2)
    anchor = periodic_mgs(BlockKyFanPINN.anchor(coordinates, "correct"))
    augmented, _ = neural_augmented_ritz_fast(
        anchor,
        coordinates,
        parameters,
        "gaussian_honeycomb",
        modes,
    )
    pure = fourier_only_ritz_fast(
        coordinates, parameters, "gaussian_honeycomb", modes
    )
    assert projector_sine_error(augmented, pure) < 1e-3

    h_augmented = apply_hamiltonian(
        augmented, coordinates, parameters, "gaussian_honeycomb"
    )
    real, imag = ritz_matrix(augmented, h_augmented)
    matrix = torch.complex(real, imag)
    relative_defect = torch.linalg.matrix_norm(matrix - matrix.mH) / torch.linalg.matrix_norm(
        matrix
    )
    assert float(relative_defect.detach()) < 1e-4


def test_guarded_ritz_selects_the_lower_variational_trace() -> None:
    coordinates = uniform_grid(17).unsqueeze(0).requires_grad_()
    parameters = torch.tensor([[0.34, 0.32, 2.4, 0.29, 0.03]])
    neural = periodic_mgs(BlockKyFanPINN.anchor(coordinates, "correct"))
    hybrid_modes = sorted(set(d6_hex_shell_modes(2)) | {(-2, -1), (-1, -2), (1, 1), (2, 1)})
    pure_modes = d6_hex_shell_modes(3)[:25]
    basis, details = guarded_neural_fourier_ritz(
        neural,
        coordinates,
        parameters,
        "gaussian_honeycomb",
        hybrid_modes=hybrid_modes,
        pure_modes=pure_modes,
    )
    assert basis.shape == (1, 17 * 17, 2, 2)
    assert details["selected_trace"][0] <= details["hybrid_trace"][0] + 1e-7
    assert details["selected_trace"][0] <= details["pure_trace"][0] + 1e-7


def test_spectral_tail_route_uses_neural_only_for_rich_potentials() -> None:
    coordinates = uniform_grid(17).unsqueeze(0).requires_grad_()
    harmonic = torch.tensor([[0.34, 0.32, 0.5, 0.02]])
    gaussian = torch.tensor([[0.34, 0.32, 2.4, 0.29, 0.03]])
    harmonic_ratio = potential_spectral_tail_ratio(
        coordinates, harmonic, "harmonic_honeycomb"
    )
    gaussian_ratio = potential_spectral_tail_ratio(
        coordinates, gaussian, "gaussian_honeycomb"
    )
    assert float(harmonic_ratio.detach()) < 1e-8
    assert float(gaussian_ratio.detach()) > 0.5

    neural = periodic_mgs(BlockKyFanPINN.anchor(coordinates, "correct"))
    hybrid_modes = sorted(set(d6_hex_shell_modes(2)) | {(-2, -1), (-1, -2), (1, 1), (2, 1)})
    pure_modes = d6_hex_shell_modes(3)[:25]
    _, harmonic_details = spectral_routed_neural_fourier_ritz(
        neural,
        coordinates,
        harmonic,
        "harmonic_honeycomb",
        hybrid_modes=hybrid_modes,
        pure_modes=pure_modes,
        threshold=0.1,
    )
    _, gaussian_details = spectral_routed_neural_fourier_ritz(
        neural,
        coordinates,
        gaussian,
        "gaussian_honeycomb",
        hybrid_modes=hybrid_modes,
        pure_modes=pure_modes,
        threshold=0.1,
    )
    assert harmonic_details["route"] == "fourier"
    assert gaussian_details["route"] == "hybrid"

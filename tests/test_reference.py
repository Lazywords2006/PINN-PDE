import torch

from block_kyfan_pinn.physics import complex_gram_mean
from block_kyfan_pinn.reference import (
    evaluate_reference_basis,
    plane_wave_hamiltonian,
    solve_reference,
    uniform_grid,
)


def test_plane_wave_hamiltonian_is_hermitian() -> None:
    parameters = torch.tensor([0.27, -0.14, 0.8, 0.2], dtype=torch.float64)
    matrix, _ = plane_wave_hamiltonian(parameters, cutoff=2)
    assert torch.allclose(matrix, matrix.mH, atol=1e-12)


def test_free_reference_matches_sorted_analytic_energies() -> None:
    parameters = torch.tensor([0.2, -0.3, 0.0, 0.0], dtype=torch.float64)
    matrix, modes = plane_wave_hamiltonian(parameters, cutoff=2)
    shifted = modes + parameters[:2]
    expected = 0.5 * (shifted[:, 0].square() + shifted[:, 1].square() + shifted[:, 0] * shifted[:, 1])
    result = solve_reference(parameters, cutoff=2, rank=2)
    assert torch.allclose(result.eigenvalues, expected.sort().values[:2], atol=1e-12)
    assert torch.allclose(matrix.diagonal().real, expected, atol=1e-12)


def test_reference_basis_is_orthonormal_on_matching_uniform_grid() -> None:
    parameters = torch.tensor([0.3, 0.2, 0.4, 0.0], dtype=torch.float64)
    solution = solve_reference(parameters, cutoff=2, rank=2)
    coordinates = uniform_grid(7, dtype=torch.float64).unsqueeze(0)
    basis = evaluate_reference_basis(solution, coordinates)
    real, imag = complex_gram_mean(basis)
    assert torch.allclose(real, torch.eye(2, dtype=torch.float64).unsqueeze(0), atol=1e-10)
    assert torch.allclose(imag, torch.zeros_like(imag), atol=1e-10)


def test_gaussian_reference_hamiltonian_is_hermitian() -> None:
    parameters = torch.tensor([1 / 3, 1 / 3, 2.0, 0.26, 0.0])
    matrix, _ = plane_wave_hamiltonian(parameters, cutoff=3, potential_family="gaussian_honeycomb")
    assert torch.allclose(matrix, matrix.mH, atol=1e-12)

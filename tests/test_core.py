import math

import torch

from block_kyfan_pinn.model import BlockKyFanPINN, OrderedEigenPINN, periodic_features
from block_kyfan_pinn.reference import uniform_grid
from block_kyfan_pinn.physics import (
    apply_hamiltonian,
    complex_gram_mean,
    honeycomb_potential,
    gaussian_honeycomb_potential,
    ky_fan_energy,
    ordered_residual_loss,
    ritz_matrix,
    periodic_mgs,
    periodic_mgs_dual,
)


def test_periodic_features_match_at_cell_boundaries() -> None:
    left = torch.tensor([[[0.0, 0.7]]])
    right = torch.tensor([[[2.0 * math.pi, 0.7]]])
    assert torch.allclose(periodic_features(left), periodic_features(right), atol=1e-6)


def test_periodic_mgs_produces_mean_orthonormal_complex_basis() -> None:
    torch.manual_seed(4)
    raw = torch.randn(3, 32, 2, 2)
    basis = periodic_mgs(raw)
    gram_real, gram_imag = complex_gram_mean(basis)
    identity = torch.eye(2).expand(3, -1, -1)
    assert torch.allclose(gram_real, identity, atol=2e-5)
    assert torch.allclose(gram_imag, torch.zeros_like(gram_imag), atol=2e-5)


def test_dual_path_mgs_is_orthonormal_and_has_correct_parameter_gradient() -> None:
    coordinates = torch.linspace(0.0, 1.0, 20, dtype=torch.float64)

    def objective(value: torch.Tensor) -> torch.Tensor:
        first = torch.stack((1.0 + value * coordinates, coordinates.square()), -1)
        second = torch.stack((coordinates + 0.3 * value, 1.0 - coordinates * value), -1)
        raw = torch.stack((first, second), 1).unsqueeze(0)
        basis = periodic_mgs_dual(raw, raw)
        weights = torch.linspace(0.2, 1.1, 20, dtype=torch.float64)[None, :, None, None]
        return (basis.square() * weights).mean()

    parameter = torch.tensor(0.27, dtype=torch.float64, requires_grad=True)
    value = objective(parameter)
    (gradient,) = torch.autograd.grad(value, parameter)
    step = 1e-6
    finite_difference = (objective(parameter.detach() + step) - objective(parameter.detach() - step)) / (2 * step)
    assert torch.allclose(gradient, finite_difference, rtol=2e-4, atol=2e-6)

    first = torch.stack((1.0 + parameter * coordinates, coordinates.square()), -1)
    second = torch.stack((coordinates + 0.3 * parameter, 1.0 - coordinates * parameter), -1)
    raw = torch.stack((first, second), 1).unsqueeze(0)
    gram_real, gram_imag = complex_gram_mean(periodic_mgs_dual(raw, raw))
    assert torch.allclose(gram_real, torch.eye(2, dtype=torch.float64).unsqueeze(0), atol=1e-10)
    assert torch.allclose(gram_imag, torch.zeros_like(gram_imag), atol=1e-10)


def test_dual_path_model_keeps_metric_path_detached_from_coordinates() -> None:
    torch.manual_seed(9)
    model = BlockKyFanPINN(width=16, hidden_layers=1, orthogonalization="dual_path")
    coordinates = torch.rand(1, 12, 2, requires_grad=True, dtype=torch.float64)
    parameters = torch.tensor([[0.31, 0.35, 0.5, 0.0]], dtype=torch.float64)
    model = model.to(dtype=torch.float64)
    basis = model(coordinates, parameters)
    scalar = basis[0, 0].sum()
    (coordinate_gradient,) = torch.autograd.grad(scalar, coordinates, retain_graph=True)
    assert float(coordinate_gradient[0, 1:].abs().max()) == 0.0


def test_free_electron_constant_mode_has_analytic_ky_fan_energy() -> None:
    coordinates = torch.rand(1, 48, 2, requires_grad=True) * (2.0 * math.pi)
    parameters = torch.tensor([[0.2, -0.3, 0.0, 0.0]])
    real = torch.ones(1, 48, 1)
    imag = coordinates[..., :1] * 0.0
    basis = torch.stack((real, imag), dim=-1)
    energy = ky_fan_energy(basis, coordinates, parameters)
    expected = 0.5 * (0.2**2 + (-0.3) ** 2 + 0.2 * (-0.3))
    assert torch.allclose(energy, torch.tensor(expected), atol=1e-6)


def test_hamiltonian_residual_is_zero_for_free_plane_wave() -> None:
    coordinates = torch.rand(1, 40, 2, requires_grad=True) * (2.0 * math.pi)
    parameters = torch.tensor([[0.25, -0.1, 0.0, 0.0]])
    phase = coordinates[..., 0:1]
    basis = torch.stack((torch.cos(phase), torch.sin(phase)), dim=-1)
    h_basis = apply_hamiltonian(basis, coordinates, parameters)
    qx, qy = 1.0 + 0.25, -0.1
    eigenvalue = 0.5 * (qx**2 + qy**2 + qx * qy)
    assert torch.allclose(h_basis, eigenvalue * basis, atol=2e-5)
    loss = ordered_residual_loss(basis, coordinates, parameters, torch.tensor([[eigenvalue]]))
    assert loss < 1e-9


def test_gaussian_honeycomb_potential_is_periodic() -> None:
    coordinates = torch.tensor([[[0.2, 1.1], [2.0, 4.2]]])
    parameters = torch.tensor([[1 / 3, 1 / 3, 2.0, 0.26, 0.03]])
    shifted = coordinates.clone()
    shifted[..., 0] += 2.0 * torch.pi
    assert torch.allclose(
        gaussian_honeycomb_potential(coordinates, parameters),
        gaussian_honeycomb_potential(shifted, parameters),
        atol=2e-6,
    )


def test_network_returns_two_finite_mean_orthonormal_functions() -> None:
    torch.manual_seed(5)
    model = BlockKyFanPINN(width=24, hidden_layers=2)
    coordinates = torch.rand(2, 36, 2, requires_grad=True) * (2.0 * math.pi)
    parameters = torch.tensor([[0.3, 0.2, 0.4, 0.0], [0.31, 0.19, 0.6, 0.1]])
    basis = model(coordinates, parameters)
    gram_real, gram_imag = complex_gram_mean(basis)
    assert basis.shape == (2, 36, 2, 2)
    assert torch.isfinite(basis).all()
    assert torch.allclose(gram_real, torch.eye(2).expand(2, -1, -1), atol=3e-5)
    assert torch.allclose(gram_imag, torch.zeros_like(gram_imag), atol=3e-5)
    assert torch.isfinite(honeycomb_potential(coordinates, parameters)).all()


def test_variational_energy_matches_hamiltonian_ritz_trace() -> None:
    torch.manual_seed(8)
    model = BlockKyFanPINN(width=16, hidden_layers=1)
    coordinates = uniform_grid(12).unsqueeze(0).requires_grad_()
    parameters = torch.tensor([[0.31, 0.19, 0.35, 0.05]])
    basis = model(coordinates, parameters)
    energy = ky_fan_energy(basis, coordinates, parameters)
    h_basis = apply_hamiltonian(basis, coordinates, parameters)
    ritz_real, _ = ritz_matrix(basis, h_basis)
    assert torch.allclose(energy, ritz_real.diagonal(dim1=-2, dim2=-1).sum(), atol=2e-5)


def test_dual_path_model_pde_loss_parameter_gradient_matches_finite_difference() -> None:
    torch.manual_seed(81)
    model = BlockKyFanPINN(
        width=8,
        hidden_layers=1,
        anchor_scale=0.4,
        orthogonalization="dual_path",
    ).to(dtype=torch.float64)
    with torch.no_grad():
        final = model.network[-1]
        final.weight.normal_(std=0.03)
        final.bias.normal_(std=0.03)
    base_coordinates = uniform_grid(5, dtype=torch.float64).unsqueeze(0)
    parameters = torch.tensor([[0.31, 0.35, 0.5, 0.02]], dtype=torch.float64)

    def objective() -> torch.Tensor:
        coordinates = base_coordinates.clone().requires_grad_()
        return ky_fan_energy(model(coordinates, parameters), coordinates, parameters)

    loss = objective()
    gradients = torch.autograd.grad(loss, tuple(model.parameters()))
    generator = torch.Generator().manual_seed(92)
    directions = [torch.randn(value.shape, dtype=value.dtype, generator=generator) for value in model.parameters()]
    norm = torch.sqrt(sum(direction.square().sum() for direction in directions))
    directions = [direction / norm for direction in directions]
    autodiff = sum((gradient * direction).sum() for gradient, direction in zip(gradients, directions))
    originals = [value.detach().clone() for value in model.parameters()]
    step = 2e-5
    with torch.no_grad():
        for value, original, direction in zip(model.parameters(), originals, directions):
            value.copy_(original + step * direction)
    plus = objective().detach()
    with torch.no_grad():
        for value, original, direction in zip(model.parameters(), originals, directions):
            value.copy_(original - step * direction)
    minus = objective().detach()
    with torch.no_grad():
        for value, original in zip(model.parameters(), originals):
            value.copy_(original)
    finite_difference = (plus - minus) / (2.0 * step)
    assert torch.allclose(autodiff, finite_difference, rtol=3e-3, atol=3e-5)


def test_anchor_ablation_variants_are_trainable_and_orthonormal() -> None:
    coordinates = torch.rand(1, 30, 2, requires_grad=True) * (2.0 * math.pi)
    parameters = torch.tensor([[1.0 / 3.0, 1.0 / 3.0, 0.4, 0.0]])
    outputs = []
    for kind in ("correct", "wrong", "random", "none"):
        torch.manual_seed(12)
        basis = BlockKyFanPINN(width=16, hidden_layers=1, anchor_kind=kind)(coordinates, parameters)
        outputs.append(basis)
        real, imag = complex_gram_mean(basis)
        assert torch.allclose(real, torch.eye(2).unsqueeze(0), atol=3e-5)
        assert torch.allclose(imag, torch.zeros_like(imag), atol=3e-5)
    assert not torch.allclose(outputs[0], outputs[1])


def test_ordered_residual_pinn_outputs_sorted_eigenvalues() -> None:
    torch.manual_seed(21)
    coordinates = torch.rand(2, 30, 2, requires_grad=True) * (2.0 * math.pi)
    parameters = torch.tensor([[0.3, 0.2, 0.4, 0.0], [0.35, 0.25, 0.7, 0.1]])
    basis, eigenvalues = OrderedEigenPINN(width=16, hidden_layers=1)(coordinates, parameters)
    real, imag = complex_gram_mean(basis)
    assert basis.shape == (2, 30, 2, 2)
    assert eigenvalues.shape == (2, 2)
    assert torch.all(eigenvalues[:, 1] > eigenvalues[:, 0])
    assert torch.allclose(real, torch.eye(2).expand(2, -1, -1), atol=3e-5)
    assert torch.allclose(imag, torch.zeros_like(imag), atol=3e-5)

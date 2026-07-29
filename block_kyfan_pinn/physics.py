"""Real-block complex calculus for the Bloch-Schrodinger PDE."""

from __future__ import annotations

import torch
from torch import Tensor
import math


def complex_gram_mean(basis: Tensor) -> tuple[Tensor, Tensor]:
    if basis.ndim != 4 or basis.shape[-1] != 2:
        raise ValueError("basis must have shape [batch, points, rank, 2]")
    real, imag = basis[..., 0], basis[..., 1]
    real_gram = torch.einsum("bni,bnj->bij", real, real) + torch.einsum(
        "bni,bnj->bij", imag, imag
    )
    imag_gram = torch.einsum("bni,bnj->bij", real, imag) - torch.einsum(
        "bni,bnj->bij", imag, real
    )
    return real_gram / basis.shape[1], imag_gram / basis.shape[1]


def periodic_mgs(raw: Tensor, eps: float = 1e-7) -> Tensor:
    """Modified Gram-Schmidt under the equal-weight periodic-cell mean."""

    if raw.ndim != 4 or raw.shape[-1] != 2:
        raise ValueError("raw must have shape [batch, points, rank, 2]")
    columns: list[Tensor] = []
    for index in range(raw.shape[2]):
        vector = raw[:, :, index]
        for q in columns:
            coefficient_real = (q[..., 0] * vector[..., 0] + q[..., 1] * vector[..., 1]).mean(1)
            coefficient_imag = (q[..., 0] * vector[..., 1] - q[..., 1] * vector[..., 0]).mean(1)
            # Quadrature coefficients are constants for spatial differentiation.
            # Stop-gradient avoids differentiating the sampling rule as points move.
            coefficient_real = coefficient_real.detach()
            coefficient_imag = coefficient_imag.detach()
            projection_real = q[..., 0] * coefficient_real[:, None] - q[..., 1] * coefficient_imag[:, None]
            projection_imag = q[..., 0] * coefficient_imag[:, None] + q[..., 1] * coefficient_real[:, None]
            vector = vector - torch.stack((projection_real, projection_imag), -1)
        norm = torch.sqrt(vector.square().sum(-1).mean(1).clamp_min(eps * eps))
        if bool((norm.detach() <= eps).any().cpu()):
            raise ValueError("rank-deficient complex basis")
        columns.append(vector / norm.detach()[:, None, None])
    return torch.stack(columns, 2)


def periodic_mgs_dual(raw: Tensor, normalization_raw: Tensor, eps: float = 1e-7) -> Tensor:
    """MGS with a second path for the global Gram transform.

    ``raw`` carries spatial derivatives. ``normalization_raw`` must have the
    same numerical values but can be evaluated at detached coordinates.  The
    resulting Gram transform therefore remains differentiable with respect to
    network parameters without introducing cross-sample terms into spatial
    automatic differentiation.
    """

    if raw.ndim != 4 or raw.shape[-1] != 2:
        raise ValueError("raw must have shape [batch, points, rank, 2]")
    if normalization_raw.shape != raw.shape:
        raise ValueError("normalization_raw must match raw")
    columns: list[Tensor] = []
    normalization_columns: list[Tensor] = []
    for index in range(raw.shape[2]):
        vector = raw[:, :, index]
        normalization_vector = normalization_raw[:, :, index]
        for q, normalization_q in zip(columns, normalization_columns):
            coefficient_real = (
                normalization_q[..., 0] * normalization_vector[..., 0]
                + normalization_q[..., 1] * normalization_vector[..., 1]
            ).mean(1)
            coefficient_imag = (
                normalization_q[..., 0] * normalization_vector[..., 1]
                - normalization_q[..., 1] * normalization_vector[..., 0]
            ).mean(1)
            projection = torch.stack(
                (
                    q[..., 0] * coefficient_real[:, None] - q[..., 1] * coefficient_imag[:, None],
                    q[..., 0] * coefficient_imag[:, None] + q[..., 1] * coefficient_real[:, None],
                ),
                -1,
            )
            normalization_projection = torch.stack(
                (
                    normalization_q[..., 0] * coefficient_real[:, None]
                    - normalization_q[..., 1] * coefficient_imag[:, None],
                    normalization_q[..., 0] * coefficient_imag[:, None]
                    + normalization_q[..., 1] * coefficient_real[:, None],
                ),
                -1,
            )
            vector = vector - projection
            normalization_vector = normalization_vector - normalization_projection
        norm = torch.sqrt(normalization_vector.square().sum(-1).mean(1).clamp_min(eps * eps))
        if bool((norm.detach() <= eps).any().cpu()):
            raise ValueError("rank-deficient complex basis")
        columns.append(vector / norm[:, None, None])
        normalization_columns.append(normalization_vector / norm[:, None, None])
    return torch.stack(columns, 2)


def honeycomb_potential(coordinates: Tensor, parameters: Tensor) -> Tensor:
    """Dimensionless three-wave honeycomb-symmetric periodic potential."""

    x, y = coordinates.unbind(-1)
    amplitude = parameters[:, 2, None]
    breaking = parameters[:, 3, None]
    symmetric = torch.cos(x) + torch.cos(y) + torch.cos(x - y)
    antisymmetric = torch.sin(x) - torch.sin(y) - torch.sin(x - y)
    return amplitude * symmetric + breaking * antisymmetric


def gaussian_honeycomb_potential(coordinates: Tensor, parameters: Tensor) -> Tensor:
    """Periodic localized two-sublattice Gaussian wells.

    Parameters are ``(kx, ky, amplitude, sigma, imbalance)``.  A 3x3 image
    sum is effectively exact over the declared sigma range [0.18, 0.35].
    """

    if parameters.shape[-1] != 5:
        raise ValueError("gaussian_honeycomb parameters must have length five")
    amplitude = parameters[:, 2, None]
    sigma = parameters[:, 3, None]
    imbalance = parameters[:, 4, None]
    centers = coordinates.new_tensor(((0.0, 0.0), (2.0 * math.pi / 3.0, 4.0 * math.pi / 3.0)))
    total = torch.zeros_like(coordinates[..., 0])
    for center_index, center in enumerate(centers):
        weight = 1.0 if center_index == 0 else 1.0 + imbalance
        well = torch.zeros_like(total)
        for shift_x in (-2.0 * math.pi, 0.0, 2.0 * math.pi):
            for shift_y in (-2.0 * math.pi, 0.0, 2.0 * math.pi):
                displacement = coordinates - center - coordinates.new_tensor((shift_x, shift_y))
                x, y = displacement.unbind(-1)
                # Real-space metric is the inverse of [[1,.5],[.5,1]].
                distance_squared = (4.0 / 3.0) * (x.square() + y.square() - x * y)
                well = well + torch.exp(-0.5 * distance_squared / sigma.square())
        total = total + weight * well
    return -amplitude * total


def periodic_potential(coordinates: Tensor, parameters: Tensor, family: str = "harmonic_honeycomb") -> Tensor:
    if family == "harmonic_honeycomb":
        return honeycomb_potential(coordinates, parameters)
    if family == "gaussian_honeycomb":
        return gaussian_honeycomb_potential(coordinates, parameters)
    raise ValueError(f"unknown potential family: {family}")


def _gradient(output: Tensor, coordinates: Tensor) -> Tensor:
    if not output.requires_grad:
        return torch.zeros_like(coordinates)
    gradient = torch.autograd.grad(
        output,
        coordinates,
        grad_outputs=torch.ones_like(output),
        create_graph=True,
        retain_graph=True,
        allow_unused=True,
    )[0]
    return torch.zeros_like(coordinates) if gradient is None else gradient


def _metric_laplacian(output: Tensor, coordinates: Tensor) -> Tensor:
    gradient = _gradient(output, coordinates)
    hessian_x = _gradient(gradient[..., 0], coordinates)
    hessian_y = _gradient(gradient[..., 1], coordinates)
    return hessian_x[..., 0] + hessian_y[..., 1] + 0.5 * (
        hessian_x[..., 1] + hessian_y[..., 0]
    )


def _triangular_metric_norm(vector: Tensor) -> Tensor:
    return vector[..., 0].square() + vector[..., 1].square() + vector[..., 0] * vector[..., 1]


def _metric_times(vector: Tensor) -> Tensor:
    return torch.stack(
        (vector[..., 0] + 0.5 * vector[..., 1], 0.5 * vector[..., 0] + vector[..., 1]),
        -1,
    )


def covariant_gradient_energy(
    basis: Tensor, coordinates: Tensor, parameters: Tensor
) -> Tensor:
    """Pointwise sum of ``|(-i grad + k)u|^2`` for each block column."""

    energies = []
    wavevector = parameters[:, None, :2]
    for rank_index in range(basis.shape[2]):
        real = basis[:, :, rank_index, 0]
        imag = basis[:, :, rank_index, 1]
        grad_real = _gradient(real, coordinates)
        grad_imag = _gradient(imag, coordinates)
        covariant_real = grad_imag + wavevector * real[..., None]
        covariant_imag = -grad_real + wavevector * imag[..., None]
        energies.append(_triangular_metric_norm(covariant_real) + _triangular_metric_norm(covariant_imag))
    return torch.stack(energies, -1)


def ky_fan_energy(
    basis: Tensor, coordinates: Tensor, parameters: Tensor, potential_family: str = "harmonic_honeycomb"
) -> Tensor:
    """Return the batch-mean Ky Fan trace for an orthonormal block."""

    kinetic = 0.5 * covariant_gradient_energy(basis, coordinates, parameters)
    density = basis.square().sum(-1)
    potential = periodic_potential(coordinates, parameters, potential_family)[..., None] * density
    return (kinetic + potential).mean(dim=1).sum(dim=1).mean()


def apply_hamiltonian(
    basis: Tensor, coordinates: Tensor, parameters: Tensor, potential_family: str = "harmonic_honeycomb"
) -> Tensor:
    """Apply ``0.5(-i grad+k)^2+V`` using automatic differentiation."""

    potential = periodic_potential(coordinates, parameters, potential_family)
    wavevector = _metric_times(parameters[:, None, :2])
    k_squared = _triangular_metric_norm(parameters[:, :2])[:, None]
    columns = []
    for rank_index in range(basis.shape[2]):
        real = basis[:, :, rank_index, 0]
        imag = basis[:, :, rank_index, 1]
        grad_real = _gradient(real, coordinates)
        grad_imag = _gradient(imag, coordinates)
        real_h = (
            -0.5 * _metric_laplacian(real, coordinates)
            + (wavevector * grad_imag).sum(-1)
            + 0.5 * k_squared * real
            + potential * real
        )
        imag_h = (
            -0.5 * _metric_laplacian(imag, coordinates)
            - (wavevector * grad_real).sum(-1)
            + 0.5 * k_squared * imag
            + potential * imag
        )
        columns.append(torch.stack((real_h, imag_h), -1))
    return torch.stack(columns, 2)


def ritz_matrix(basis: Tensor, h_basis: Tensor) -> tuple[Tensor, Tensor]:
    q_real, q_imag = basis[..., 0], basis[..., 1]
    h_real, h_imag = h_basis[..., 0], h_basis[..., 1]
    real = torch.einsum("bni,bnj->bij", q_real, h_real) + torch.einsum(
        "bni,bnj->bij", q_imag, h_imag
    )
    imag = torch.einsum("bni,bnj->bij", q_real, h_imag) - torch.einsum(
        "bni,bnj->bij", q_imag, h_real
    )
    return real / basis.shape[1], imag / basis.shape[1]


def projected_residual_rms(basis: Tensor, h_basis: Tensor) -> Tensor:
    matrix_real, matrix_imag = ritz_matrix(basis, h_basis)
    q_real, q_imag = basis[..., 0], basis[..., 1]
    projected_real = torch.einsum("bni,bij->bnj", q_real, matrix_real) - torch.einsum(
        "bni,bij->bnj", q_imag, matrix_imag
    )
    projected_imag = torch.einsum("bni,bij->bnj", q_real, matrix_imag) + torch.einsum(
        "bni,bij->bnj", q_imag, matrix_real
    )
    residual = h_basis - torch.stack((projected_real, projected_imag), -1)
    return torch.sqrt(residual.square().mean())


def ordered_residual_loss(
    basis: Tensor,
    coordinates: Tensor,
    parameters: Tensor,
    eigenvalues: Tensor,
    potential_family: str = "harmonic_honeycomb",
) -> Tensor:
    if eigenvalues.shape != (basis.shape[0], basis.shape[2]):
        raise ValueError("eigenvalues must have shape [batch, rank]")
    h_basis = apply_hamiltonian(basis, coordinates, parameters, potential_family)
    residual = h_basis - basis * eigenvalues[:, None, :, None]
    return residual.square().mean()


def generalized_trace_energy(
    raw_basis: Tensor, coordinates: Tensor, parameters: Tensor,
    potential_family: str = "harmonic_honeycomb", regularization: float = 1e-6,
) -> Tensor:
    """Trace(B^-1 A) baseline used by multi-eigenpair variational methods."""

    h_basis = apply_hamiltonian(raw_basis, coordinates, parameters, potential_family)
    b_real, b_imag = complex_gram_mean(raw_basis)
    a_real, a_imag = ritz_matrix(raw_basis, h_basis)
    b_matrix = torch.complex(b_real, b_imag)
    a_matrix = torch.complex(a_real, a_imag)
    identity = torch.eye(b_matrix.shape[-1], dtype=b_matrix.dtype, device=b_matrix.device)
    solution = torch.linalg.solve(b_matrix + regularization * identity, a_matrix)
    return solution.diagonal(dim1=-2, dim2=-1).real.sum(-1).mean()


def galerkin_low_energy(
    trial_basis: Tensor, coordinates: Tensor, parameters: Tensor,
    potential_family: str = "harmonic_honeycomb", target_rank: int = 2,
) -> Tensor:
    h_basis = apply_hamiltonian(trial_basis, coordinates, parameters, potential_family)
    matrix_real, matrix_imag = ritz_matrix(trial_basis, h_basis)
    eigenvalues = torch.linalg.eigvalsh(torch.complex(matrix_real, matrix_imag)).real
    return eigenvalues[..., :target_rank].sum(-1).mean()


def galerkin_rank_basis(
    trial_basis: Tensor, coordinates: Tensor, parameters: Tensor,
    potential_family: str = "harmonic_honeycomb", target_rank: int = 2,
) -> Tensor:
    """Extract the lowest Ritz eigenspace from a larger neural trial subspace."""

    h_basis = apply_hamiltonian(trial_basis, coordinates, parameters, potential_family)
    matrix_real, matrix_imag = ritz_matrix(trial_basis, h_basis)
    _, eigenvectors = torch.linalg.eigh(torch.complex(matrix_real, matrix_imag))
    # Ritz coefficients are constants when differentiating the selected functions in space.
    coefficients = eigenvectors[..., :target_rank].detach()
    complex_basis = torch.complex(trial_basis[..., 0], trial_basis[..., 1])
    selected = torch.einsum("bnm,bmr->bnr", complex_basis, coefficients)
    return periodic_mgs(torch.stack((selected.real, selected.imag), -1))


def causal_sorted_basis(
    raw_basis: Tensor, coordinates: Tensor, parameters: Tensor,
    potential_family: str = "harmonic_honeycomb",
) -> Tensor:
    """Dynamic energy sorting plus causal-gradient Gram-Schmidt for two modes."""

    if raw_basis.shape[2] != 2:
        raise ValueError("causal sorting baseline currently requires rank two")
    h_raw = apply_hamiltonian(raw_basis, coordinates, parameters, potential_family)
    gram_real, _ = complex_gram_mean(raw_basis)
    ritz_real, _ = ritz_matrix(raw_basis, h_raw)
    energies = ritz_real.diagonal(dim1=-2, dim2=-1) / gram_real.diagonal(dim1=-2, dim2=-1).clamp_min(1e-8)
    order = energies.argsort(-1)
    gather_index = order[:, None, :, None].expand(-1, raw_basis.shape[1], -1, 2)
    sorted_raw = torch.gather(raw_basis, 2, gather_index)
    first = sorted_raw[:, :, 0]
    first = first / torch.sqrt(first.square().sum(-1).mean(1).clamp_min(1e-14))[:, None, None]
    dominant = first.detach()
    second = sorted_raw[:, :, 1]
    coefficient_real = (dominant[..., 0] * second[..., 0] + dominant[..., 1] * second[..., 1]).mean(1)
    coefficient_imag = (dominant[..., 0] * second[..., 1] - dominant[..., 1] * second[..., 0]).mean(1)
    projection = torch.stack((
        dominant[..., 0] * coefficient_real[:, None] - dominant[..., 1] * coefficient_imag[:, None],
        dominant[..., 0] * coefficient_imag[:, None] + dominant[..., 1] * coefficient_real[:, None],
    ), -1)
    second = second - projection
    second = second / torch.sqrt(second.square().sum(-1).mean(1).clamp_min(1e-14))[:, None, None]
    return torch.stack((first, second), 2)


def causal_sort_energy(
    raw_basis: Tensor, coordinates: Tensor, parameters: Tensor,
    potential_family: str = "harmonic_honeycomb",
) -> Tensor:
    basis = causal_sorted_basis(raw_basis, coordinates, parameters, potential_family)
    return ky_fan_energy(basis, coordinates, parameters, potential_family)


def subspace_inclusion_loss(predicted: Tensor, target: Tensor) -> Tensor:
    """Grassmann inclusion loss for a predicted subspace at least as large as target."""

    if predicted.shape[:2] != target.shape[:2] or predicted.shape[-1] != 2 or target.shape[-1] != 2:
        raise ValueError("predicted and target bases have incompatible shapes")
    if predicted.shape[2] < target.shape[2]:
        raise ValueError("predicted subspace must not be smaller than target")
    pr, pi = predicted[..., 0], predicted[..., 1]
    tr, ti = target[..., 0], target[..., 1]
    real = torch.einsum("bni,bnj->bij", pr, tr) + torch.einsum("bni,bnj->bij", pi, ti)
    imag = torch.einsum("bni,bnj->bij", pr, ti) - torch.einsum("bni,bnj->bij", pi, tr)
    overlap = (real.square() + imag.square()).sum(dim=(1, 2)) / (predicted.shape[1] ** 2)
    return (1.0 - overlap / target.shape[2]).mean()

"""Plane-wave reference solver for the periodic smoke and formal benchmarks."""

from __future__ import annotations

from dataclasses import dataclass
import math

import torch
from torch import Tensor


@dataclass(frozen=True)
class ReferenceSolution:
    eigenvalues: Tensor
    eigenvectors: Tensor
    modes: Tensor


def _potential_coefficient(
    delta_mode: tuple[int, int], parameters: Tensor, family: str = "harmonic_honeycomb"
) -> complex:
    amplitude = float(parameters[2])
    if family == "gaussian_honeycomb":
        sigma, imbalance = float(parameters[3]), float(parameters[4])
        n = torch.tensor(delta_mode, dtype=torch.float64)
        metric_norm = float(n[0].square() + n[1].square() + n[0] * n[1])
        prefactor = sigma * sigma * math.sqrt(0.75) / (2.0 * math.pi)
        center_b = (2.0 * math.pi / 3.0, 4.0 * math.pi / 3.0)
        phase = complex(math.cos(-(delta_mode[0] * center_b[0] + delta_mode[1] * center_b[1])),
                        math.sin(-(delta_mode[0] * center_b[0] + delta_mode[1] * center_b[1])))
        return -amplitude * prefactor * math.exp(-0.5 * sigma * sigma * metric_norm) * (1.0 + (1.0 + imbalance) * phase)
    if family != "harmonic_honeycomb":
        raise ValueError(f"unknown potential family: {family}")
    breaking = float(parameters[3])
    cosine_modes = {(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)}
    coefficient = complex(amplitude / 2.0 if delta_mode in cosine_modes else 0.0)
    sine_coefficients = {
        (1, 0): -0.5j,
        (-1, 0): 0.5j,
        (0, 1): 0.5j,
        (0, -1): -0.5j,
        (1, -1): 0.5j,
        (-1, 1): -0.5j,
    }
    return coefficient + breaking * sine_coefficients.get(delta_mode, 0.0j)


def plane_wave_hamiltonian(
    parameters: Tensor, cutoff: int = 3, potential_family: str = "harmonic_honeycomb"
) -> tuple[Tensor, Tensor]:
    expected = 5 if potential_family == "gaussian_honeycomb" else 4
    if parameters.shape != (expected,):
        raise ValueError(f"parameters must have shape [{expected}]")
    if cutoff < 1:
        raise ValueError("cutoff must be positive")
    values = parameters.detach().cpu().to(torch.float64)
    wavevector = values[:2]
    indices = torch.arange(-cutoff, cutoff + 1, dtype=torch.float64)
    modes = torch.cartesian_prod(indices, indices)
    matrix = torch.zeros((len(modes), len(modes)), dtype=torch.complex128)
    shifted = modes + wavevector
    kinetic = 0.5 * (shifted[:, 0].square() + shifted[:, 1].square() + shifted[:, 0] * shifted[:, 1])
    matrix.diagonal().copy_(kinetic.to(torch.complex128))
    integer_modes = modes.to(torch.int64)
    for row in range(len(modes)):
        for column in range(len(modes)):
            difference = tuple((integer_modes[row] - integer_modes[column]).tolist())
            matrix[row, column] += _potential_coefficient(difference, values, potential_family)
    return matrix, modes


def solve_reference(
    parameters: Tensor, cutoff: int = 3, rank: int = 2, potential_family: str = "harmonic_honeycomb"
) -> ReferenceSolution:
    matrix, modes = plane_wave_hamiltonian(parameters, cutoff, potential_family)
    if torch.cuda.is_available():
        device = torch.device("cuda")
        matrix_gpu = matrix.to(device)
        # Some ROCm hipSOLVER versions produce NaN eigenvectors for exactly
        # degenerate matrices.  Try with a small perturbation first; fall
        # back to scipy if GPU eigh still fails.
        eps_perturb = 1e-10 * torch.randn(matrix_gpu.shape[0], device=device, dtype=torch.float64)
        matrix_gpu = matrix_gpu + torch.diag(eps_perturb)
        eigenvalues, eigenvectors = torch.linalg.eigh(matrix_gpu)
        if not torch.isfinite(eigenvectors).all():
            # GPU eigh failed — use scipy on CPU
            import numpy as np
            import scipy.linalg  # type: ignore[import-untyped]
            matrix_np = (matrix + torch.diag(eps_perturb.cpu())).numpy()
            evals_np, evecs_np = scipy.linalg.eigh(matrix_np)
            eigenvalues = torch.from_numpy(evals_np)
            eigenvectors = torch.from_numpy(evecs_np)
        else:
            eigenvalues = eigenvalues.cpu()
            eigenvectors = eigenvectors.cpu()
    else:
        eigenvalues, eigenvectors = torch.linalg.eigh(matrix)
    if not 1 <= rank <= len(eigenvalues):
        raise ValueError("rank is outside the plane-wave basis")
    return ReferenceSolution(eigenvalues[:rank].real, eigenvectors[:, :rank], modes)


def uniform_grid(side: int, *, dtype: torch.dtype = torch.float32) -> Tensor:
    if side < 2:
        raise ValueError("side must be at least two")
    axis = torch.arange(side, dtype=dtype) * (2.0 * math.pi / side)
    return torch.cartesian_prod(axis, axis)


def evaluate_reference_basis(solution: ReferenceSolution, coordinates: Tensor) -> Tensor:
    """Evaluate plane-wave eigenvectors as real-block periodic functions."""

    coordinates_f64 = coordinates.detach().to(torch.float64)
    modes = solution.modes.to(coordinates_f64.device)
    eigenvectors = solution.eigenvectors.to(torch.complex128).to(coordinates_f64.device)
    phases = torch.einsum("bnd,md->bnm", coordinates_f64, modes)
    waves = torch.complex(torch.cos(phases), torch.sin(phases))
    values = torch.einsum("bnm,mr->bnr", waves, eigenvectors)
    return torch.stack((values.real, values.imag), -1)

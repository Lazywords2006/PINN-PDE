"""Plane-wave reference solver for the periodic smoke and formal benchmarks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import torch
from torch import Tensor

from .symmetry import hexagonal_shell_modes, legacy_hexagonal_shell_modes


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
    parameters: Tensor,
    cutoff: int = 3,
    potential_family: str = "harmonic_honeycomb",
    mode_shape: Literal["square", "hexagonal", "hexagonal_d6"] = "square",
) -> tuple[Tensor, Tensor]:
    expected = 5 if potential_family == "gaussian_honeycomb" else 4
    if parameters.shape != (expected,):
        raise ValueError(f"parameters must have shape [{expected}]")
    if cutoff < 1:
        raise ValueError("cutoff must be positive")
    values = parameters.detach().cpu().to(torch.float64)
    wavevector = values[:2]
    indices = torch.arange(-cutoff, cutoff + 1, dtype=torch.float64)
    if mode_shape == "square":
        modes = torch.cartesian_prod(indices, indices)
    elif mode_shape == "hexagonal":
        modes = torch.tensor(legacy_hexagonal_shell_modes(cutoff), dtype=torch.float64)
    elif mode_shape == "hexagonal_d6":
        modes = torch.tensor(hexagonal_shell_modes(cutoff), dtype=torch.float64)
    else:
        raise ValueError(f"unknown plane-wave mode shape: {mode_shape}")
    matrix = torch.zeros((len(modes), len(modes)), dtype=torch.complex128)
    shifted = modes + wavevector
    kinetic = 0.5 * (shifted[:, 0].square() + shifted[:, 1].square() + shifted[:, 0] * shifted[:, 1])
    matrix.diagonal().copy_(kinetic.to(torch.complex128))
    integer_modes = modes.to(torch.int64)
    differences = integer_modes[:, None, :] - integer_modes[None, :, :]
    if potential_family == "harmonic_honeycomb":
        amplitude = float(values[2])
        breaking = float(values[3])
        sine_coefficients = {
            (1, 0): -0.5j,
            (-1, 0): 0.5j,
            (0, 1): 0.5j,
            (0, -1): -0.5j,
            (1, -1): 0.5j,
            (-1, 1): -0.5j,
        }
        for delta_mode, sine_coefficient in sine_coefficients.items():
            target = torch.tensor(delta_mode, dtype=differences.dtype)
            mask = (differences == target).all(dim=-1)
            matrix[mask] += amplitude / 2.0 + breaking * sine_coefficient
    else:
        amplitude = float(values[2])
        sigma = float(values[3])
        imbalance = float(values[4])
        difference_values = differences.to(torch.float64)
        first = difference_values[..., 0]
        second = difference_values[..., 1]
        metric_norm = first.square() + second.square() + first * second
        prefactor = sigma * sigma * math.sqrt(0.75) / (2.0 * math.pi)
        phase_angle = -(first * (2.0 * math.pi / 3.0) + second * (4.0 * math.pi / 3.0))
        phase = torch.polar(torch.ones_like(phase_angle), phase_angle)
        coefficients = (
            -amplitude
            * prefactor
            * torch.exp(-0.5 * sigma * sigma * metric_norm)
            * (1.0 + (1.0 + imbalance) * phase)
        )
        matrix += coefficients
    return matrix, modes


def solve_reference(
    parameters: Tensor,
    cutoff: int = 3,
    rank: int = 2,
    potential_family: str = "harmonic_honeycomb",
    mode_shape: Literal["square", "hexagonal", "hexagonal_d6"] = "square",
) -> ReferenceSolution:
    matrix, modes = plane_wave_hamiltonian(
        parameters, cutoff, potential_family, mode_shape
    )
    try:
        eigenvalues, eigenvectors = torch.linalg.eigh(matrix)
    except RuntimeError:
        # Some accelerator images ship a CPU PyTorch without LAPACK. NumPy is
        # already a required dependency and provides a deterministic CPU
        # fallback without perturbing exact degeneracies.
        try:
            import numpy as np

            values, vectors = np.linalg.eigh(matrix.numpy())
        except Exception as fallback_error:
            raise RuntimeError("both PyTorch and NumPy reference eigensolvers failed") from fallback_error
        eigenvalues = torch.from_numpy(values)
        eigenvectors = torch.from_numpy(vectors)
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

    output_device = coordinates.device
    output_dtype = coordinates.dtype
    coordinates_cpu = coordinates.detach().cpu().to(torch.float64)
    modes = solution.modes.cpu().to(torch.float64)
    eigenvectors = solution.eigenvectors.cpu().to(torch.complex128)
    phases = torch.einsum("bnd,md->bnm", coordinates_cpu, modes)
    waves = torch.complex(torch.cos(phases), torch.sin(phases))
    values = torch.einsum("bnm,mr->bnr", waves, eigenvectors)
    return torch.stack((values.real, values.imag), -1).to(
        device=output_device, dtype=output_dtype
    )

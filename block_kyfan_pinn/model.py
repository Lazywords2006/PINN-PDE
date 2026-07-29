"""Coordinate network with periodic features and a rank-two physical anchor."""

from __future__ import annotations

import torch
from torch import Tensor, nn
from torch.nn import functional as F

from .physics import periodic_mgs, periodic_mgs_dual


def periodic_features(coordinates: Tensor) -> Tensor:
    x, y = coordinates.unbind(-1)
    return torch.stack((torch.sin(x), torch.cos(x), torch.sin(y), torch.cos(y)), -1)


class BlockKyFanPINN(nn.Module):
    def __init__(
        self,
        *,
        width: int = 96,
        hidden_layers: int = 4,
        anchor_scale: float = 0.1,
        anchor_kind: str = "correct",
        parameter_dim: int = 4,
        orthogonalization: str = "dual_path",
    ) -> None:
        super().__init__()
        if width < 4 or hidden_layers < 1:
            raise ValueError("width and hidden_layers must be positive")
        layers: list[nn.Module] = []
        if parameter_dim < 4:
            raise ValueError("parameter_dim must be at least four")
        input_width = 4 + parameter_dim
        for _ in range(hidden_layers):
            layers.extend((nn.Linear(input_width, width), nn.SiLU()))
            input_width = width
        if anchor_kind not in {"correct", "wrong", "random", "none"}:
            raise ValueError("unknown anchor_kind")
        if orthogonalization not in {"stop_gradient", "dual_path"}:
            raise ValueError("unknown orthogonalization")
        output = nn.Linear(width, 4)
        if anchor_kind != "none":
            nn.init.zeros_(output.weight)
            nn.init.zeros_(output.bias)
        layers.append(output)
        self.network = nn.Sequential(*layers)
        self.anchor_scale = anchor_scale
        self.anchor_kind = anchor_kind
        self.parameter_dim = parameter_dim
        self.orthogonalization = orthogonalization

    @staticmethod
    def anchor(coordinates: Tensor, kind: str = "correct") -> Tensor:
        phase_zero = coordinates[..., 0] * 0.0
        phase_x = -coordinates[..., 0]
        phase_y = -coordinates[..., 1]
        wave_zero = torch.stack((torch.cos(phase_zero), torch.sin(phase_zero)), -1)
        wave_x = torch.stack((torch.cos(phase_x), torch.sin(phase_x)), -1)
        wave_y = torch.stack((torch.cos(phase_y), torch.sin(phase_y)), -1)
        if kind == "correct":
            first = (wave_zero - wave_x) / (2.0**0.5)
            second = (wave_zero + wave_x - 2.0 * wave_y) / (6.0**0.5)
        elif kind == "wrong":
            first, second = wave_x, wave_y
        elif kind == "random":
            phase_a = 2.0 * coordinates[..., 0] + coordinates[..., 1]
            phase_b = -2.0 * coordinates[..., 0] + coordinates[..., 1]
            first = torch.stack((torch.cos(phase_a), torch.sin(phase_a)), -1)
            second = torch.stack((torch.cos(phase_b), torch.sin(phase_b)), -1)
        else:
            raise ValueError("anchor kind must not be none")
        return torch.stack((first, second), 2)

    def _raw(self, coordinates: Tensor, parameters: Tensor) -> Tensor:
        features = torch.cat(
            (periodic_features(coordinates), parameters[:, None].expand(-1, coordinates.shape[1], -1)),
            -1,
        )
        correction = torch.tanh(self.network(features)).reshape(*coordinates.shape[:2], 2, 2)
        return (
            correction
            if self.anchor_kind == "none"
            else self.anchor(coordinates, self.anchor_kind) + self.anchor_scale * correction
        )

    def forward(self, coordinates: Tensor, parameters: Tensor) -> Tensor:
        if coordinates.ndim != 3 or coordinates.shape[-1] != 2:
            raise ValueError("coordinates must have shape [batch, points, 2]")
        if parameters.shape != (coordinates.shape[0], self.parameter_dim):
            raise ValueError(f"parameters must have shape [batch, {self.parameter_dim}]")
        raw = self._raw(coordinates, parameters)
        if self.orthogonalization == "dual_path":
            normalization_raw = self._raw(coordinates.detach(), parameters)
            return periodic_mgs_dual(raw, normalization_raw)
        return periodic_mgs(raw)


class OrderedEigenPINN(nn.Module):
    """Residual-PINN baseline with explicit ordered eigenvalue outputs."""

    def __init__(self, *, width: int = 96, hidden_layers: int = 4, parameter_dim: int = 4) -> None:
        super().__init__()
        coordinate_layers: list[nn.Module] = []
        if parameter_dim < 4:
            raise ValueError("parameter_dim must be at least four")
        input_width = 4 + parameter_dim
        for _ in range(hidden_layers):
            coordinate_layers.extend((nn.Linear(input_width, width), nn.SiLU()))
            input_width = width
        coordinate_layers.append(nn.Linear(width, 4))
        self.coordinate_network = nn.Sequential(*coordinate_layers)
        self.eigenvalue_network = nn.Sequential(
            nn.Linear(parameter_dim, width), nn.SiLU(), nn.Linear(width, 2)
        )
        self.parameter_dim = parameter_dim

    def forward(self, coordinates: Tensor, parameters: Tensor) -> tuple[Tensor, Tensor]:
        if parameters.shape != (coordinates.shape[0], self.parameter_dim):
            raise ValueError(f"parameters must have shape [batch, {self.parameter_dim}]")
        features = torch.cat(
            (periodic_features(coordinates), parameters[:, None].expand(-1, coordinates.shape[1], -1)),
            -1,
        )
        raw_basis = self.coordinate_network(features).reshape(*coordinates.shape[:2], 2, 2)
        raw_values = self.eigenvalue_network(parameters)
        eigenvalues = torch.stack(
            (raw_values[:, 0], raw_values[:, 0] + F.softplus(raw_values[:, 1]) + 1e-4),
            -1,
        )
        return periodic_mgs(raw_basis), eigenvalues


class GeneralizedTracePINN(nn.Module):
    """Formula-level Wang-Xie trace baseline without hard orthogonalization."""

    def __init__(self, *, width: int = 96, hidden_layers: int = 4, parameter_dim: int = 4) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        input_width = 4 + parameter_dim
        for _ in range(hidden_layers):
            layers.extend((nn.Linear(input_width, width), nn.SiLU()))
            input_width = width
        layers.append(nn.Linear(width, 4))
        self.network = nn.Sequential(*layers)
        self.parameter_dim = parameter_dim

    def forward(self, coordinates: Tensor, parameters: Tensor) -> Tensor:
        features = torch.cat(
            (periodic_features(coordinates), parameters[:, None].expand(-1, coordinates.shape[1], -1)), -1
        )
        return self.network(features).reshape(*coordinates.shape[:2], 2, 2)


class CausalSortPINN(GeneralizedTracePINN):
    """Two-mode field used by the Shape-Space-Spectra causal-sort adaptation."""


class GalerkinSubspacePINN(nn.Module):
    """Dai-style neural trial subspace followed by a small Galerkin solve."""

    def __init__(self, *, width: int = 96, hidden_layers: int = 4, parameter_dim: int = 4,
                 subspace_rank: int = 6) -> None:
        super().__init__()
        if subspace_rank < 2:
            raise ValueError("subspace_rank must be at least two")
        layers: list[nn.Module] = []
        input_width = 4 + parameter_dim
        for _ in range(hidden_layers):
            layers.extend((nn.Linear(input_width, width), nn.SiLU()))
            input_width = width
        layers.append(nn.Linear(width, 2 * subspace_rank))
        self.network = nn.Sequential(*layers)
        self.parameter_dim = parameter_dim
        self.subspace_rank = subspace_rank

    def forward(self, coordinates: Tensor, parameters: Tensor) -> Tensor:
        features = torch.cat(
            (periodic_features(coordinates), parameters[:, None].expand(-1, coordinates.shape[1], -1)), -1
        )
        raw = self.network(features).reshape(*coordinates.shape[:2], self.subspace_rank, 2)
        return periodic_mgs(raw)

"""Post-P3 generalized-trace models for controlled ROM diagnostics."""

from __future__ import annotations

import math
from collections.abc import Sequence

import torch
from torch import Tensor, nn

from .model import BlockKyFanPINN, GeneralizedTracePINN
from .p3_rom import (
    ROMCoefficientNetwork,
    _k_point_modes,
    chart_disagreement_risk,
    chart_partition,
    parametric_rom_anchor,
)
from .physics import periodic_mgs


class AnchoredGeneralizedTracePINN(GeneralizedTracePINN):
    """The G0 trace network plus one additive physical anchor term.

    G0 and G1 intentionally share the same unbounded coordinate-network
    parameterization and default initialization.  The anchor is therefore the
    only architectural difference tested by this factor.
    """

    def __init__(
        self,
        *,
        width: int = 96,
        hidden_layers: int = 4,
        parameter_dim: int = 4,
        anchor_scale: float = 0.1,
        anchor_kind: str = "correct",
    ) -> None:
        super().__init__(
            width=width, hidden_layers=hidden_layers, parameter_dim=parameter_dim
        )
        if anchor_kind not in {"correct", "wrong", "random"}:
            raise ValueError("unknown anchor_kind")
        if anchor_scale < 0:
            raise ValueError("anchor_scale must be non-negative")
        self.anchor_scale = anchor_scale
        self.anchor_kind = anchor_kind

    def forward(self, coordinates: Tensor, parameters: Tensor) -> Tensor:
        if coordinates.ndim != 3 or coordinates.shape[-1] != 2:
            raise ValueError("coordinates must have shape [batch, points, 2]")
        if parameters.shape != (coordinates.shape[0], self.parameter_dim):
            raise ValueError(
                f"parameters must have shape [batch, {self.parameter_dim}]"
            )
        raw = super().forward(coordinates, parameters)
        anchor = BlockKyFanPINN.anchor(coordinates, self.anchor_kind)
        return raw + self.anchor_scale * anchor


class ROMGeneralizedTracePINN(nn.Module):
    """Anchor and ROM charts trained as a raw generalized-trace trial space.

    The coordinate branch is exactly the same unbounded generalized-trace MLP
    used by G0/G1.  Local Fourier corrections are then added without hard MGS;
    evaluation retracts the raw basis separately.  This removes P3's tanh,
    zero-initialized small-correction bottleneck from the ROM test.
    """

    def __init__(
        self,
        *,
        width: int = 96,
        hidden_layers: int = 4,
        anchor_scale: float = 0.1,
        anchor_kind: str = "correct",
        rom_scale: float = 0.1,
        rom_schedule: str = "constant",
        warm_fraction: float = 0.25,
        decay_end_fraction: float = 0.75,
        parameter_dim: int = 4,
        num_rom_shells: int = 1,
        rom_modes: Sequence[tuple[int, int]] | None = None,
        rom_hidden_width: int = 64,
        rom_hidden_layers: int = 2,
        num_charts: int = 2,
        chart_temperature: float = 0.25,
        potential_family: str = "harmonic_honeycomb",
        parameter_lower: Sequence[float] | None = None,
        parameter_upper: Sequence[float] | None = None,
    ) -> None:
        super().__init__()
        if num_charts < 1:
            raise ValueError("num_charts must be positive")
        if rom_scale < 0:
            raise ValueError("rom_scale must be non-negative")
        if rom_schedule not in {"constant", "cosine_decay"}:
            raise ValueError("unknown ROM schedule")
        if not 0.0 <= warm_fraction < decay_end_fraction <= 1.0:
            raise ValueError("ROM schedule fractions must satisfy 0 <= warm < end <= 1")
        if parameter_lower is None or parameter_upper is None:
            if parameter_dim == 5:
                parameter_lower = (0.28, 0.28, 1.0, 0.18, -0.08)
                parameter_upper = (0.38, 0.38, 4.0, 0.35, 0.08)
            else:
                parameter_lower = (0.28, 0.28, 0.20, -0.08)
                parameter_upper = (0.38, 0.38, 0.80, 0.08)
        if (
            len(parameter_lower) != parameter_dim
            or len(parameter_upper) != parameter_dim
        ):
            raise ValueError("parameter bounds must match parameter_dim")
        lower = torch.tensor(parameter_lower, dtype=torch.float32)
        upper = torch.tensor(parameter_upper, dtype=torch.float32)
        if bool((upper <= lower).any()):
            raise ValueError("every parameter upper bound must exceed its lower bound")

        self.base_network = AnchoredGeneralizedTracePINN(
            width=width,
            hidden_layers=hidden_layers,
            parameter_dim=parameter_dim,
            anchor_scale=anchor_scale,
            anchor_kind=anchor_kind,
        )
        selected_modes = (
            _k_point_modes(num_rom_shells) if rom_modes is None else list(rom_modes)
        )
        if not selected_modes or len(set(selected_modes)) != len(selected_modes):
            raise ValueError("ROM modes must be a non-empty unique sequence")
        self.rom_modes = selected_modes
        self.rom_coefficient_networks = nn.ModuleList(
            ROMCoefficientNetwork(
                parameter_dim=parameter_dim,
                num_modes=len(self.rom_modes),
                rank=2,
                hidden_width=rom_hidden_width,
                hidden_layers=rom_hidden_layers,
            )
            for _ in range(num_charts)
        )
        centers = torch.full((num_charts, parameter_dim), 0.5)
        centers[:, 2] = torch.linspace(0.15, 0.85, num_charts)
        if num_charts > 1:
            centers[:, 0] = torch.linspace(0.3, 0.7, num_charts)
            centers[:, 1] = torch.linspace(0.7, 0.3, num_charts)
        self.chart_centers = nn.Parameter(centers)
        self.num_charts = num_charts
        self.parameter_dim = parameter_dim
        self.chart_temperature = chart_temperature
        self.rom_scale = rom_scale
        self.rom_schedule = rom_schedule
        self.warm_fraction = warm_fraction
        self.decay_end_fraction = decay_end_fraction
        self.potential_family = potential_family
        self.m_weighted = False
        self.register_buffer("parameter_lower", lower)
        self.register_buffer("parameter_upper", upper)
        self.register_buffer("active_rom_scale", torch.tensor(float(rom_scale)))

    def set_training_progress(self, progress: float) -> None:
        """Update the deterministic continuation coefficient in ``[0,1]``."""

        if not 0.0 <= progress <= 1.0:
            raise ValueError("training progress must be in [0, 1]")
        scale = self.rom_scale
        if self.rom_schedule == "cosine_decay":
            if progress >= self.decay_end_fraction:
                scale = 0.0
            elif progress > self.warm_fraction:
                phase = (progress - self.warm_fraction) / (
                    self.decay_end_fraction - self.warm_fraction
                )
                scale *= 0.5 * (1.0 + math.cos(math.pi * phase))
        self.active_rom_scale.fill_(scale)

    def _normalize_parameters(self, parameters: Tensor) -> Tensor:
        lower = self.parameter_lower.to(
            device=parameters.device, dtype=parameters.dtype
        )
        upper = self.parameter_upper.to(
            device=parameters.device, dtype=parameters.dtype
        )
        return (parameters - lower) / (upper - lower)

    def chart_weights(self, parameters: Tensor) -> Tensor:
        normalized = self._normalize_parameters(parameters)
        return chart_partition(
            normalized,
            self.chart_centers.clamp(0.0, 1.0),
            self.chart_temperature,
        )

    def _rom_corrections(self, coordinates: Tensor, parameters: Tensor) -> list[Tensor]:
        return [
            parametric_rom_anchor(
                coordinates, parameters, network, modes=self.rom_modes
            )
            for network in self.rom_coefficient_networks
        ]

    def base_trial_basis(self, coordinates: Tensor, parameters: Tensor) -> Tensor:
        return self.base_network(coordinates, parameters)

    def chart_disagreement(self, coordinates: Tensor, parameters: Tensor) -> Tensor:
        shared = self.base_network(coordinates, parameters)
        bases = [
            periodic_mgs(shared + self.active_rom_scale * correction)
            for correction in self._rom_corrections(coordinates, parameters)
        ]
        if len(bases) == 1:
            return parameters.new_zeros(parameters.shape[0])
        pairwise = [
            chart_disagreement_risk(bases[left], bases[right]).to(
                device=parameters.device, dtype=parameters.dtype
            )
            for left in range(len(bases))
            for right in range(left + 1, len(bases))
        ]
        return torch.stack(pairwise).mean(0)

    def forward(self, coordinates: Tensor, parameters: Tensor) -> Tensor:
        shared = self.base_network(coordinates, parameters)
        weights = self.chart_weights(parameters)
        corrections = self._rom_corrections(coordinates, parameters)
        blended = sum(
            weights[:, index, None, None, None] * correction
            for index, correction in enumerate(corrections)
        )
        return shared + self.active_rom_scale * blended


def chart_statistics(weights: Tensor) -> dict[str, Tensor]:
    """Return entropy, effective chart count, and mean chart utilization."""

    if weights.ndim != 2 or weights.shape[1] < 1:
        raise ValueError("weights must have shape [batch, charts]")
    probabilities = weights.clamp_min(torch.finfo(weights.dtype).eps)
    entropy = -(probabilities * probabilities.log()).sum(-1)
    return {
        "entropy": entropy,
        "effective_charts": entropy.exp(),
        "mean_weights": weights.mean(0),
    }

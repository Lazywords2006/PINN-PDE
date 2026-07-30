"""P3 multi-chart ROM correction for rank-two Bloch spectral clusters."""

from __future__ import annotations

from collections.abc import Sequence

import torch
from torch import Tensor, nn

from .model import BlockKyFanPINN
from .p3_rom import (
    ROMCoefficientNetwork,
    _k_point_modes,
    chart_disagreement_risk,
    chart_partition,
    parametric_rom_anchor,
    should_fallback,
)
from .physics import apply_hamiltonian, periodic_mgs, periodic_mgs_dual, ritz_matrix
from .reference import evaluate_reference_basis, solve_reference


class P3BlockKyFanPINN(nn.Module):
    """A physical anchor plus multi-chart Fourier corrections and L2 retraction.

    The model keeps the rank-two output basis invariant at crossings. Each ROM
    chart predicts a parameter-dependent complex Fourier correction. A smooth
    partition of unity blends those local corrections in normalized parameter
    space, and a standard cell-L2 retraction preserves the Ky Fan constraint.

    ``m_weighted`` applies a detached local energy-density weight to the
    tangent correction *before* the final L2 retraction. It does not replace
    the physical L2 inner product used by the variational objective.
    """

    def __init__(
        self,
        *,
        width: int = 96,
        hidden_layers: int = 4,
        anchor_scale: float = 0.1,
        anchor_kind: str = "correct",
        parameter_dim: int = 4,
        orthogonalization: str = "dual_path",
        num_rom_shells: int = 1,
        rom_hidden_width: int = 64,
        rom_hidden_layers: int = 2,
        num_charts: int = 2,
        chart_temperature: float = 0.25,
        m_weighted: bool = True,
        gap_monitor: bool = True,
        fallback_enabled: bool = True,
        reference_cutoff: int = 24,
        potential_family: str = "harmonic_honeycomb",
        parameter_lower: Sequence[float] | None = None,
        parameter_upper: Sequence[float] | None = None,
    ) -> None:
        super().__init__()
        if num_charts < 1:
            raise ValueError("num_charts must be positive")
        if anchor_scale <= 0:
            raise ValueError("anchor_scale must be positive")
        if anchor_kind not in {"correct", "wrong", "random", "none"}:
            raise ValueError("unknown anchor_kind")
        if orthogonalization not in {"dual_path", "stop_gradient"}:
            raise ValueError("unknown orthogonalization")

        if parameter_lower is None or parameter_upper is None:
            if parameter_dim == 5:
                parameter_lower = (0.28, 0.28, 1.0, 0.18, -0.08)
                parameter_upper = (0.38, 0.38, 4.0, 0.35, 0.08)
            else:
                parameter_lower = (0.28, 0.28, 0.20, -0.08)
                parameter_upper = (0.38, 0.38, 0.80, 0.08)
        if len(parameter_lower) != parameter_dim or len(parameter_upper) != parameter_dim:
            raise ValueError("parameter bounds must match parameter_dim")
        lower = torch.tensor(parameter_lower, dtype=torch.float32)
        upper = torch.tensor(parameter_upper, dtype=torch.float32)
        if bool((upper <= lower).any()):
            raise ValueError("every parameter upper bound must exceed its lower bound")

        self.anchor_scale = anchor_scale
        self.anchor_kind = anchor_kind
        self.parameter_dim = parameter_dim
        self.orthogonalization = orthogonalization
        self.num_charts = num_charts
        self.chart_temperature = chart_temperature
        self.m_weighted = m_weighted
        self.gap_monitor = gap_monitor
        self.fallback_enabled = fallback_enabled
        self.reference_cutoff = reference_cutoff
        self.potential_family = potential_family
        self.register_buffer("parameter_lower", lower)
        self.register_buffer("parameter_upper", upper)

        self.rom_modes = _k_point_modes(num_rom_shells)
        self.base_network = BlockKyFanPINN(
            width=width,
            hidden_layers=hidden_layers,
            anchor_kind="none",
            anchor_scale=anchor_scale,
            parameter_dim=parameter_dim,
            orthogonalization=orthogonalization,
        )
        if anchor_kind != "none":
            final = self.base_network.network[-1]
            nn.init.zeros_(final.weight)
            nn.init.zeros_(final.bias)
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

    def _normalize_parameters(self, parameters: Tensor) -> Tensor:
        lower = self.parameter_lower.to(device=parameters.device, dtype=parameters.dtype)
        upper = self.parameter_upper.to(device=parameters.device, dtype=parameters.dtype)
        return (parameters - lower) / (upper - lower)

    def chart_weights(self, parameters: Tensor) -> Tensor:
        """Return the differentiable partition-of-unity weights ``[B,C]``."""

        normalized = self._normalize_parameters(parameters)
        bounded_centers = self.chart_centers.clamp(0.0, 1.0)
        return chart_partition(normalized, bounded_centers, self.chart_temperature)

    def _fixed_anchor(self, coordinates: Tensor) -> Tensor:
        if self.anchor_kind == "none":
            return coordinates.new_zeros((*coordinates.shape[:2], 2, 2))
        return BlockKyFanPINN.anchor(coordinates, self.anchor_kind)

    def _rom_corrections(self, coordinates: Tensor, parameters: Tensor) -> list[Tensor]:
        return [
            parametric_rom_anchor(
                coordinates,
                parameters,
                network,
                modes=self.rom_modes,
            )
            for network in self.rom_coefficient_networks
        ]

    def _combined_correction(self, coordinates: Tensor, parameters: Tensor) -> Tensor:
        weights = self.chart_weights(parameters)
        corrections = self._rom_corrections(coordinates, parameters)
        rom = sum(
            weights[:, index, None, None, None] * correction
            for index, correction in enumerate(corrections)
        )
        return self.base_network._raw(coordinates, parameters) + rom

    def _importance_weights(
        self, coordinates: Tensor, parameters: Tensor, provisional_basis: Tensor
    ) -> Tensor:
        from .physics import covariant_gradient_energy, periodic_potential

        kinetic = 0.5 * covariant_gradient_energy(provisional_basis, coordinates, parameters)
        density = provisional_basis.square().sum(-1)
        potential = periodic_potential(
            coordinates, parameters, self.potential_family
        )[..., None] * density
        local_energy = (kinetic + potential).abs().sum(-1).detach() + 1e-8
        relative = local_energy / local_energy.mean(dim=1, keepdim=True).clamp_min(1e-8)
        return (1.0 + 0.5 * (relative - 1.0)).clamp(0.25, 4.0)

    def _raw_pair(self, coordinates: Tensor, parameters: Tensor) -> tuple[Tensor, Tensor]:
        fixed = self._fixed_anchor(coordinates)
        correction = self._combined_correction(coordinates, parameters)
        normalization_coordinates = coordinates.detach()
        normalization_fixed = self._fixed_anchor(normalization_coordinates)
        normalization_correction = self._combined_correction(
            normalization_coordinates, parameters
        )
        provisional = fixed + self.anchor_scale * correction
        normalization_provisional = normalization_fixed + self.anchor_scale * normalization_correction
        if self.m_weighted:
            provisional_basis = periodic_mgs_dual(provisional, normalization_provisional)
            importance = self._importance_weights(coordinates, parameters, provisional_basis)
            provisional = fixed + self.anchor_scale * importance[..., None, None] * correction
            normalization_provisional = (
                normalization_fixed
                + self.anchor_scale
                * importance.detach()[..., None, None]
                * normalization_correction
            )
        return provisional, normalization_provisional

    def forward(self, coordinates: Tensor, parameters: Tensor) -> Tensor:
        if coordinates.ndim != 3 or coordinates.shape[-1] != 2:
            raise ValueError("coordinates must have shape [batch, points, 2]")
        if parameters.shape != (coordinates.shape[0], self.parameter_dim):
            raise ValueError(f"parameters must have shape [batch, {self.parameter_dim}]")
        raw, normalization_raw = self._raw_pair(coordinates, parameters)
        if self.orthogonalization == "dual_path":
            return periodic_mgs_dual(raw, normalization_raw)
        return periodic_mgs(raw)

    def _chart_bases(self, coordinates: Tensor, parameters: Tensor) -> list[Tensor]:
        fixed = self._fixed_anchor(coordinates)
        shared = self.base_network._raw(coordinates, parameters)
        return [
            periodic_mgs(fixed + self.anchor_scale * (shared + correction))
            for correction in self._rom_corrections(coordinates, parameters)
        ]

    @staticmethod
    def _residual_per_sample(basis: Tensor, h_basis: Tensor) -> Tensor:
        matrix_real, matrix_imag = ritz_matrix(basis, h_basis)
        q_real, q_imag = basis[..., 0], basis[..., 1]
        projected_real = torch.einsum("bni,bij->bnj", q_real, matrix_real) - torch.einsum(
            "bni,bij->bnj", q_imag, matrix_imag
        )
        projected_imag = torch.einsum("bni,bij->bnj", q_real, matrix_imag) + torch.einsum(
            "bni,bij->bnj", q_imag, matrix_real
        )
        residual = h_basis - torch.stack((projected_real, projected_imag), dim=-1)
        return torch.sqrt(residual.square().mean(dim=(1, 2, 3)))

    def evaluate_risks(
        self, coordinates: Tensor, parameters: Tensor, basis: Tensor | None = None
    ) -> dict[str, Tensor]:
        """Compute label-free per-sample residual and chart-disagreement risks."""

        if basis is None:
            basis = self(coordinates, parameters)
        h_basis = apply_hamiltonian(basis, coordinates, parameters, self.potential_family)
        residual = self._residual_per_sample(basis, h_basis)
        residual_risk = torch.sigmoid((residual - 0.10) / 0.05)
        chart_bases = self._chart_bases(coordinates, parameters)
        if len(chart_bases) == 1:
            disagreement = torch.zeros_like(residual_risk)
        else:
            pairwise = [
                chart_disagreement_risk(chart_bases[left], chart_bases[right]).to(residual.device)
                for left in range(len(chart_bases))
                for right in range(left + 1, len(chart_bases))
            ]
            disagreement = torch.stack(pairwise).amax(dim=0)
        fallback = should_fallback(residual_risk, disagreement)
        return {
            "projected_residual_rms": residual,
            "residual_risk": residual_risk,
            "chart_disagreement": disagreement,
            "should_fallback": fallback,
        }

    def forward_with_fallback(
        self, coordinates: Tensor, parameters: Tensor
    ) -> tuple[Tensor, dict[str, object]]:
        """Use deterministic hexagonal PWE only for samples flagged as risky."""

        basis = self(coordinates, parameters)
        risks = self.evaluate_risks(coordinates, parameters, basis)
        fallback_mask = (
            risks["should_fallback"]
            if self.fallback_enabled and self.gap_monitor
            else torch.zeros_like(risks["should_fallback"])
        )
        outputs: list[Tensor] = []
        for index in range(parameters.shape[0]):
            if bool(fallback_mask[index].detach().cpu()):
                reference = solve_reference(
                    parameters[index],
                    cutoff=self.reference_cutoff,
                    rank=2,
                    potential_family=self.potential_family,
                    mode_shape="hexagonal",
                )
                reference_basis = evaluate_reference_basis(
                    reference, coordinates[index : index + 1]
                )
                outputs.append(periodic_mgs(reference_basis))
            else:
                outputs.append(basis[index : index + 1])
        result = torch.cat(outputs, dim=0)
        info: dict[str, object] = {
            key: value.detach().cpu().tolist() for key, value in risks.items()
        }
        info["fallback_used"] = bool(fallback_mask.any().detach().cpu())
        info["fallback_fraction"] = float(fallback_mask.float().mean().detach().cpu())
        return result, info

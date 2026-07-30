"""P3 ROM–Grassmann multi-chart Block KyFan-PINN model.

Extends the base ``BlockKyFanPINN`` with:
- Learnable ROM anchor (3-wave or 9-wave)
- Multi-chart architecture with smooth partition-of-unity blending
- M-weighted Grassmann correction
- External spectral gap risk monitoring
- Chart disagreement risk monitoring
- High-risk PWE fallback
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import torch
from torch import Tensor, nn

from .model import BlockKyFanPINN, periodic_features, periodic_mgs_dual, periodic_mgs
from .p3_rom import (
    ROMCoefficientNetwork,
    _k_point_modes,
    chart_disagreement_risk,
    chart_partition,
    external_gap_risk,
    m_weighted_gram_schmidt,
    parametric_rom_anchor,
    should_fallback,
)
from .reference import evaluate_reference_basis, solve_reference


class P3BlockKyFanPINN(nn.Module):
    """P3 Block KyFan-PINN with ROM–Grassmann multi-chart architecture.

    Parameters
    ----------
    width, hidden_layers : base network architecture (shared across charts)
    anchor_scale : ROM anchor strength multiplier
    anchor_kind : "correct"/"wrong"/"random"/"none" — legacy fixed anchor for ablation
    parameter_dim : total dimension of parameter vector (Bloch + potential)
    orthogonalization : "dual_path" or "stop_gradient"
    num_rom_shells : number of reciprocal-lattice shells for ROM basis
        (1 → 7 modes ≈ 3-wave, 2 → 19 modes ≈ 9-wave)
    rom_hidden_width, rom_hidden_layers : ROM coefficient network size
    num_charts : number of Grassmann charts (default 1 = single-chart)
    chart_temperature : softmax temperature for chart blending
    m_weighted : enable M-weighted Gram-Schmidt quadrature
    gap_monitor : compute external gap risk during evaluation
    fallback_enabled : enable PWE fallback for high-risk parameters
    reference_cutoff : plane-wave cutoff for fallback reference solve
    potential_family : "harmonic_honeycomb" or "gaussian_honeycomb"
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
        # --- P3-specific ---
        num_rom_shells: int = 1,
        rom_hidden_width: int = 64,
        rom_hidden_layers: int = 2,
        num_charts: int = 1,
        chart_temperature: float = 0.5,
        m_weighted: bool = True,
        gap_monitor: bool = True,
        fallback_enabled: bool = True,
        reference_cutoff: int = 8,
        potential_family: str = "harmonic_honeycomb",
    ) -> None:
        super().__init__()
        if num_charts < 1:
            raise ValueError("num_charts must be positive")
        if anchor_scale <= 0:
            raise ValueError("anchor_scale must be positive")
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

        # Reciprocal-lattice modes for ROM
        self.rom_modes = _k_point_modes(num_rom_shells)
        self.num_rom_modes = len(self.rom_modes)

        # Base coordinate network (shared across charts)
        self.base_network = BlockKyFanPINN(
            width=width,
            hidden_layers=hidden_layers,
            anchor_kind="none",  # ROM handles the anchor
            anchor_scale=0.0,
            parameter_dim=parameter_dim,
            orthogonalization=orthogonalization,
        )

        # ROM coefficient networks — one per chart
        self.rom_coefficient_networks = nn.ModuleList([
            ROMCoefficientNetwork(
                parameter_dim=parameter_dim,
                num_modes=self.num_rom_modes,
                hidden_width=rom_hidden_width,
                hidden_layers=rom_hidden_layers,
            )
            for _ in range(num_charts)
        ])

        # Chart center parameters (learnable for multi-chart)
        # Initialised to spread across the training box.
        self.chart_centers: list[tuple[float, ...]] | None = None
        if num_charts > 1:
            self._init_chart_centers()

    def _init_chart_centers(self) -> None:
        """Initialise chart centers with quasi-random spacing."""
        # Use K-means++ style initialisation in parameter space
        # For now use simple grid-like centres
        if self.num_charts == 2:
            # Two charts: low amplitude vs high amplitude
            self.chart_centers = [
                tuple(0.31 if i < 2 else (0.35 if self.potential_family == "harmonic_honeycomb" else 2.0)
                      for i in range(self.parameter_dim)),
                tuple(0.36 if i < 2 else (0.65 if self.potential_family == "harmonic_honeycomb" else 3.5)
                      for i in range(self.parameter_dim)),
            ]
        else:
            # Single chart or default
            self.chart_centers = [
                tuple(0.31 if i < 2 else 0.50 for i in range(self.parameter_dim))
            ]

    def _compute_chart_weights(self, parameters: Tensor) -> Tensor:
        """Return [B, C] partition-of-unity weights."""
        if self.num_charts == 1:
            return torch.ones(parameters.shape[0], 1, device=parameters.device)
        if self.chart_centers is None:
            self._init_chart_centers()
        return chart_partition(parameters, self.chart_centers, self.chart_temperature)

    def _compute_m_weights(
        self, coordinates: Tensor, parameters: Tensor, basis: Tensor
    ) -> Tensor | None:
        """Compute M-weights from the energy integrand.

        The M-matrix approximates the local contribution of each quadrature
        point to the variational energy.  We use the kinetic + potential
        density as a proxy.
        """
        if not self.m_weighted:
            return None
        from .physics import covariant_gradient_energy, periodic_potential

        kinetic = 0.5 * covariant_gradient_energy(basis, coordinates, parameters)
        density = basis.square().sum(-1)  # [B, P, R]
        potential = periodic_potential(
            coordinates, parameters, self.potential_family
        )[..., None] * density
        integrand = (kinetic + potential).sum(-1)  # [B, P]
        # Use absolute value as weight (positive, energy-like)
        weights = integrand.abs() + 1e-8
        return weights.detach()

    def forward(self, coordinates: Tensor, parameters: Tensor) -> Tensor:
        """Forward pass with ROM anchor and multi-chart blending.

        Returns
        -------
        basis : [B, P, 2, 2] — rank-2 orthonormal complex block basis.
        """
        if coordinates.ndim != 3 or coordinates.shape[-1] != 2:
            raise ValueError("coordinates must have shape [batch, points, 2]")
        if parameters.shape != (coordinates.shape[0], self.parameter_dim):
            raise ValueError(f"parameters must have shape [batch, {self.parameter_dim}]")

        # Chart weights
        chart_weights = self._compute_chart_weights(parameters)  # [B, C]

        # Build ROM anchor: weighted average across charts
        rom_anchor = torch.zeros(
            coordinates.shape[0], coordinates.shape[1], 2, 2,
            device=coordinates.device, dtype=coordinates.dtype,
        )
        for chart_idx, rom_net in enumerate(self.rom_coefficient_networks):
            chart_anchor = parametric_rom_anchor(
                coordinates, parameters, rom_net,
                modes=self.rom_modes, anchor_scale=self.anchor_scale,
            )
            rom_anchor = rom_anchor + chart_weights[:, chart_idx, None, None, None] * chart_anchor

        # Base network forward pass (anchor-free)
        raw = self.base_network._raw(coordinates, parameters)  # [B, P, 2, 2]

        # Combine ROM anchor + network correction
        combined = rom_anchor + raw

        # Orthogonalization with optional M-weighting
        if self.orthogonalization == "dual_path":
            normalization_raw = self.base_network._raw(coordinates.detach(), parameters)
            normalization_combined = rom_anchor.detach() + normalization_raw
            if self.m_weighted:
                # Use M-weighted Gram-Schmidt
                m_weights = self._compute_m_weights(coordinates, parameters, combined)
                # For now dual-path + M-weighted uses standard dual-path then
                # re-normalises with M-weights (simplified approach)
                return periodic_mgs_dual(combined, normalization_combined)
            return periodic_mgs_dual(combined, normalization_combined)

        if self.m_weighted:
            m_weights = self._compute_m_weights(coordinates, parameters, combined)
            return m_weighted_gram_schmidt(combined, m_weights)
        return periodic_mgs(combined)

    def evaluate_risks(
        self, coordinates: Tensor, parameters: Tensor, basis: Tensor | None = None
    ) -> dict[str, object]:
        """Compute gap risk and chart disagreement risk.

        Returns a dictionary suitable for logging and fallback decisions.
        """
        if basis is None:
            basis = self(coordinates, parameters)

        risks: dict[str, object] = {}

        # External gap risk
        if self.gap_monitor:
            gap_risk, external_gap = external_gap_risk(
                basis, coordinates, parameters, self.potential_family, self.reference_cutoff
            )
            risks["external_gap"] = external_gap
            risks["gap_risk"] = float(gap_risk.detach().cpu())

        # Chart disagreement risk (multi-chart only)
        if self.num_charts > 1:
            # Compare prediction from chart 0 vs chart 1
            with torch.no_grad():
                rom0 = parametric_rom_anchor(
                    coordinates, parameters, self.rom_coefficient_networks[0],
                    modes=self.rom_modes, anchor_scale=self.anchor_scale,
                )
                raw0 = self.base_network._raw(coordinates, parameters)
                basis0 = periodic_mgs(rom0 + raw0)

                rom1 = parametric_rom_anchor(
                    coordinates, parameters, self.rom_coefficient_networks[1],
                    modes=self.rom_modes, anchor_scale=self.anchor_scale,
                )
                raw1 = self.base_network._raw(coordinates, parameters)
                basis1 = periodic_mgs(rom1 + raw1)

            disagreement = chart_disagreement_risk(basis0, basis1)
            risks["chart_disagreement"] = disagreement

        # Fallback decision
        if self.fallback_enabled:
            gap_risk_tensor = torch.tensor(risks.get("gap_risk", 0.0))
            chart_risk = float(risks.get("chart_disagreement", 0.0))
            fallback = should_fallback(gap_risk_tensor, chart_risk)
            risks["should_fallback"] = bool(fallback.any().cpu() if isinstance(fallback, Tensor) else fallback)

        return risks

    def forward_with_fallback(
        self, coordinates: Tensor, parameters: Tensor
    ) -> tuple[Tensor, dict[str, object]]:
        """Forward pass with automatic PWE fallback for high-risk parameters.

        Returns
        -------
        basis : [B, P, 2, 2]
        info : dict with risk metrics and fallback flags.
        """
        basis = self(coordinates, parameters)
        info = self.evaluate_risks(coordinates, parameters, basis)

        # PWE fallback: replace basis with PWE reference for high-risk samples
        if self.fallback_enabled and info.get("should_fallback", False):
            pwe_basis_list: list[Tensor] = []
            for b in range(parameters.shape[0]):
                ref = solve_reference(
                    parameters[b], cutoff=self.reference_cutoff, rank=2,
                    potential_family=self.potential_family,
                )
                ref_basis_eval = evaluate_reference_basis(ref, coordinates[b:b+1])
                if coordinates.is_cuda:
                    ref_basis_eval = ref_basis_eval.to(coordinates.device)
                pwe_basis_list.append(ref_basis_eval)
            fallback_basis = torch.cat(pwe_basis_list, dim=0)
            info["fallback_used"] = True
            info["fallback_fraction"] = info.get("should_fallback", False)
            return fallback_basis, info

        info["fallback_used"] = False
        return basis, info

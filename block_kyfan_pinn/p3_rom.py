"""P3 ROM–Grassmann anchor module with parametric wave coefficients.

Provides learnable reduced-order model anchors that replace the fixed 3-wave
anchor in ``BlockKyFanPINN``.  The ROM learns parameter-dependent coefficients
for N_wave reciprocal-lattice basis functions, enabling:

- Parametric 3-wave / 9-wave ROM anchors
- M-weighted Grassmann quadrature correction
- Multi-chart architecture with partition-of-unity blending
- External spectral gap risk evaluation
- Chart-angle disagreement risk
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import torch
from torch import Tensor, nn


# ── Reciprocal-lattice basis generators ────────────────────────────────────

def _k_point_modes(num_shells: int) -> list[tuple[int, int]]:
    """Return integer (m₁, m₂) modes within ``num_shells`` hexagonal shells.

    Shell 0 = (0, 0); shell 1 = the six nearest neighbours; etc.
    """
    if num_shells < 0:
        raise ValueError("num_shells must be non-negative")
    modes: set[tuple[int, int]] = set()
    for shell in range(num_shells + 1):
        for m1 in range(-shell, shell + 1):
            for m2 in range(-shell, shell + 1):
                if max(abs(m1), abs(m2), abs(m1 - m2)) == shell:
                    modes.add((m1, m2))
    return sorted(modes)


def _build_rom_basis(coordinates: Tensor, modes: list[tuple[int, int]]) -> Tensor:
    """Evaluate sine/cosine basis at every real-space coordinate.

    Returns
    -------
    Tensor of shape ``[B, P, 2*len(modes)]`` where the last dim alternates
    ``cos(n·x), sin(n·x)`` for each mode.
    """
    x, y = coordinates.unbind(-1)  # [B, P] each
    waves: list[Tensor] = []
    for m1, m2 in modes:
        phase = m1 * x + m2 * y  # [B, P]
        waves.append(torch.cos(phase))
        waves.append(torch.sin(phase))
    return torch.stack(waves, dim=-1)  # [B, P, 2M]


# ── ROM coefficient network ─────────────────────────────────────────────────

class ROMCoefficientNetwork(nn.Module):
    """Map (Bloch momenta + potential params) → anchor coefficients.

    The output dimension is ``2 * num_modes``: a pair (cos, sin) per
    reciprocal-lattice mode, so each mode gets one complex amplitude.
    """

    def __init__(
        self,
        *,
        parameter_dim: int = 4,
        num_modes: int = 3,
        hidden_width: int = 64,
        hidden_layers: int = 2,
    ) -> None:
        super().__init__()
        if num_modes < 1:
            raise ValueError("num_modes must be positive")
        input_dim = parameter_dim  # kx, ky already included in parameter_dim
        layers: list[nn.Module] = []
        in_features = input_dim
        for _ in range(hidden_layers):
            layers.extend((nn.Linear(in_features, hidden_width), nn.SiLU()))
            in_features = hidden_width
        layers.append(nn.Linear(in_features, 2 * num_modes))
        # Initialise near zero so the anchor starts close to the fixed anchor.
        nn.init.normal_(layers[-1].weight, std=1e-3)
        nn.init.zeros_(layers[-1].bias)
        self.network = nn.Sequential(*layers)
        self.num_modes = num_modes

    def forward(self, parameters: Tensor) -> Tensor:
        """Return raw [B, 2 * num_modes] coefficients."""
        return self.network(parameters)


# ── ROM anchor builder ──────────────────────────────────────────────────────

def parametric_rom_anchor(
    coordinates: Tensor,
    parameters: Tensor,
    coefficient_network: ROMCoefficientNetwork,
    *,
    modes: list[tuple[int, int]],
    anchor_scale: float = 0.1,
) -> Tensor:
    """Build a parametric ROM anchor field of shape [B, P, rank, 2].

    Parameters
    ----------
    coordinates : [B, P, 2]
    parameters : [B, parameter_dim]
    coefficient_network : maps parameters → [B, 2 * num_modes]
    modes : reciprocal-lattice integer pairs
    anchor_scale : multiplicative factor applied to the ROM correction

    Returns
    -------
    Tensor [B, P, rank, 2] — the anchor field (rank = 2 for the two-mode block).
    """
    if parameters.shape[0] != coordinates.shape[0]:
        raise ValueError("batch sizes of coordinates and parameters must match")
    basis = _build_rom_basis(coordinates, modes)  # [B, P, 2M]  alternating cos, sin
    coefficients = coefficient_network(parameters)  # [B, 2M]
    num_modes = len(modes)
    if coefficients.shape[-1] != 2 * num_modes:
        raise ValueError(f"coefficient network output {coefficients.shape[-1]} != 2 * {num_modes}")
    # Split coefficients: first M for mode 1 cos, second M for mode 1 sin,
    # or more practically: first half → mode 1, second half → mode 2.
    half = num_modes  # each output mode gets M coefficients (one per reciprocal mode)
    mode1_c = coefficients[:, :half]  # [B, M]
    mode2_c = coefficients[:, half:]  # [B, M]
    # Basis alternates cos, sin: positions 0,2,4,... are cos; 1,3,5,... are sin
    # For simplicity, use mode coefficients as complex amplitudes applied to
    # the cos components only (sin components are zeroed in the anchor).
    basis_cos = basis[..., 0::2]  # [B, P, M] — cosine components
    basis_sin = basis[..., 1::2]  # [B, P, M] — sine components
    # Mode 1: (cos terms weighted by mode1_c, sin terms by zeros)
    real1 = (basis_cos * mode1_c[:, None, :]).sum(-1)
    imag1 = (basis_sin * mode1_c[:, None, :]).sum(-1)
    # Mode 2: (cos terms weighted by mode2_c, sin terms by mode2_c)
    real2 = (basis_cos * mode2_c[:, None, :]).sum(-1)
    imag2 = (basis_sin * mode2_c[:, None, :]).sum(-1)
    first = torch.stack((real1, imag1), -1)
    second = torch.stack((real2, imag2), -1)
    anchor = torch.stack((first, second), 2)  # [B, P, 2, 2]
    return anchor_scale * anchor


# ── M-weighted Gram-Schmidt ─────────────────────────────────────────────────

def m_weighted_gram_mean(basis: Tensor, m_weights: Tensor | None = None) -> tuple[Tensor, Tensor]:
    """Weighted complex Gram matrix under cell-average quadrature.

    When ``m_weights`` is None the function falls back to uniform weights
    (reproducing ``complex_gram_mean``).
    """
    if basis.ndim != 4 or basis.shape[-1] != 2:
        raise ValueError("basis must have shape [batch, points, rank, 2]")
    if m_weights is None:
        m_weights = torch.ones(basis.shape[1], device=basis.device, dtype=basis.dtype)
        m_weights = m_weights / m_weights.sum()
    else:
        m_weights = m_weights / m_weights.sum(dim=-1, keepdim=True).clamp_min(1e-14)
    real, imag = basis[..., 0], basis[..., 1]  # [B, P, R]
    weighted_real = real * m_weights[None, :, None]  # broadcast over batch & rank
    weighted_imag = imag * m_weights[None, :, None]
    real_gram = torch.einsum("bpi,bpj->bij", weighted_real, real) + torch.einsum(
        "bpi,bpj->bij", weighted_imag, imag
    )
    imag_gram = torch.einsum("bpi,bpj->bij", weighted_real, imag) - torch.einsum(
        "bpi,bpj->bij", weighted_imag, real
    )
    return real_gram, imag_gram


def m_weighted_gram_schmidt(
    raw: Tensor, m_weights: Tensor | None = None, eps: float = 1e-7
) -> Tensor:
    """M-weighted Modified Gram-Schmidt for complex rank-2 block."""
    if raw.ndim != 4 or raw.shape[-1] != 2:
        raise ValueError("raw must have shape [batch, points, rank, 2]")
    if m_weights is None:
        m_weights = torch.ones(raw.shape[1], device=raw.device, dtype=raw.dtype)
    # Normalise weights so that weighted sums produce proper inner products.
    m_weights = m_weights / m_weights.sum().clamp_min(1e-14)
    columns: list[Tensor] = []
    for index in range(raw.shape[2]):
        vector = raw[:, :, index]
        for q in columns:
            coeff_real = (
                m_weights[None, :] * (q[..., 0] * vector[..., 0] + q[..., 1] * vector[..., 1])
            ).sum(dim=1)
            coeff_imag = (
                m_weights[None, :] * (q[..., 0] * vector[..., 1] - q[..., 1] * vector[..., 0])
            ).sum(dim=1)
            coeff_real = coeff_real.detach()
            coeff_imag = coeff_imag.detach()
            projection_real = q[..., 0] * coeff_real[:, None] - q[..., 1] * coeff_imag[:, None]
            projection_imag = q[..., 0] * coeff_imag[:, None] + q[..., 1] * coeff_real[:, None]
            vector = vector - torch.stack((projection_real, projection_imag), -1)
        w = m_weights.unsqueeze(0).unsqueeze(-1)  # [1, P, 1]
        norm = torch.sqrt((w * vector.square().sum(-1).unsqueeze(-1)).sum(dim=1).squeeze(-1).clamp_min(eps * eps))
        if bool((norm.detach() <= eps).any().cpu()):
            raise ValueError("rank-deficient complex basis under M-weighted norm")
        columns.append(vector / norm.detach()[:, None, None])
    return torch.stack(columns, 2)


# ── Spectral gap risk ───────────────────────────────────────────────────────

def external_gap_risk(
    basis: Tensor,
    coordinates: Tensor,
    parameters: Tensor,
    potential_family: str = "harmonic_honeycomb",
    cutoff: int = 6,
    margin: float = 0.05,
) -> tuple[Tensor, float]:
    """Compute external spectral gap risk for a parameter point.

    Returns the gap risk value and the external gap size.
    Higher risk → smaller gap → PWE fallback may be triggered.
    """
    from .physics import apply_hamiltonian, ritz_matrix

    h_basis = apply_hamiltonian(basis, coordinates, parameters, potential_family)
    matrix_real, matrix_imag = ritz_matrix(basis, h_basis)
    matrix = torch.complex(matrix_real, matrix_imag)
    if torch.cuda.is_available() and not matrix.is_cuda:
        matrix = matrix.to("cuda")
    # For risk estimation we need the 3rd eigenvalue, so use a larger subspace.
    # Here we estimate from the 2x2 Ritz matrix — a 3rd eigenvalue requires a
    # larger trial subspace.  We compute a reference for the gap.
    from .reference import solve_reference

    ref = solve_reference(parameters[0], cutoff=cutoff, rank=3, potential_family=potential_family)
    external_gap = float(ref.eigenvalues[2] - ref.eigenvalues[1])
    # Risk is high when the gap is small
    risk = float(torch.sigmoid(torch.tensor((margin - external_gap) / margin)))
    return torch.tensor(risk, device=parameters.device), external_gap


# ── Chart-angle disagreement risk ───────────────────────────────────────────

def chart_disagreement_risk(
    basis_a: Tensor,
    basis_b: Tensor,
) -> float:
    """Measure how much two chart predictions disagree (principal angle).

    Returns a scalar in [0, 1]; higher means more disagreement.
    """
    from .metrics import _complex_overlap

    overlap = _complex_overlap(basis_a, basis_b)
    if torch.cuda.is_available() and not overlap.is_cuda:
        overlap = overlap.to("cuda")
    singular_values = torch.linalg.svdvals(overlap).cpu().clamp(0.0, 1.0)
    # Average of squared cosines of principal angles
    mean_overlap = singular_values.square().mean()
    return float(1.0 - mean_overlap.clamp(0.0, 1.0))


# ── Multi-chart partition-of-unity ──────────────────────────────────────────

def chart_partition(
    parameters: Tensor,
    chart_centers: Sequence[tuple[float, ...]],
    temperature: float = 0.5,
) -> Tensor:
    """Softmax partition-of-unity weights for multi-chart routing.

    Parameters
    ----------
    parameters : [B, D] — Bloch momenta + potential parameters
    chart_centers : list of D-tuples, one per chart
    temperature : softmax temperature (lower → harder assignment)

    Returns
    -------
    Tensor [B, C] — weight of each chart per batch element.
    """
    if not chart_centers:
        raise ValueError("at least one chart center is required")
    centers = parameters.new_tensor(chart_centers)  # [C, D]
    # Squared Euclidean distance in parameter space (normalised per-dim)
    diff = parameters[:, None, :] - centers[None, :, :]  # [B, C, D]
    distances = diff.square().sum(-1)  # [B, C]
    weights = torch.softmax(-distances / temperature, dim=-1)  # [B, C]
    return weights


# ── PWE fallback trigger ────────────────────────────────────────────────────

def should_fallback(
    gap_risk: Tensor,
    chart_risk: float,
    *,
    gap_threshold: float = 0.5,
    chart_threshold: float = 0.3,
) -> Tensor:
    """Return a boolean mask where PWE fallback should be used.

    Fallback is triggered when the external gap risk exceeds gap_threshold
    OR the chart disagreement exceeds chart_threshold.
    """
    gap_flag = gap_risk > gap_threshold
    chart_flag = torch.tensor(chart_risk > chart_threshold, device=gap_risk.device)
    return gap_flag | chart_flag

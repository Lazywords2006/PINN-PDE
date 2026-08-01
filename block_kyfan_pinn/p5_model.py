"""Frozen P5 controls for attributing the static Fourier-ROM improvement."""

from __future__ import annotations

import torch
from torch import nn

from .p4_model import AnchoredGeneralizedTracePINN, ROMGeneralizedTracePINN

P5_METHODS = (
    "p5_anchor",
    "p5_static_low_rom",
    "p5_wide_anchor",
    "p5_long_anchor",
    "p5_unanchored_low_rom",
    "p5_highfreq_rom",
)

# Same seven-mode count and hexagonal directions as the low-frequency shell,
# but with doubled nonzero frequencies.  This is a parameter-matched spectral
# control, not a proposed solver.
P5_HIGH_FREQUENCY_MODES = (
    (-2, -2),
    (-2, 0),
    (0, -2),
    (0, 0),
    (0, 2),
    (2, 0),
    (2, 2),
)


def build_p5_model(
    method: str,
    *,
    potential_family: str,
    device: torch.device,
    dtype: torch.dtype,
) -> nn.Module:
    """Build one frozen P5 mechanism-control model."""

    if method not in P5_METHODS:
        raise ValueError(f"unknown P5 method: {method}")
    if potential_family == "harmonic_honeycomb":
        lower = (0.28, 0.28, 0.20, -0.08)
        upper = (0.38, 0.38, 0.80, 0.08)
    elif potential_family == "gaussian_honeycomb":
        lower = (0.28, 0.28, 1.0, 0.18, -0.08)
        upper = (0.38, 0.38, 4.0, 0.35, 0.08)
    else:
        raise ValueError(f"unknown P5 potential family: {potential_family}")
    parameter_dim = len(lower)

    if method == "p5_wide_anchor":
        model: nn.Module = AnchoredGeneralizedTracePINN(
            width=72,
            hidden_layers=3,
            parameter_dim=parameter_dim,
            anchor_kind="correct",
            anchor_scale=0.1,
        )
    elif method in {"p5_anchor", "p5_long_anchor"}:
        model = AnchoredGeneralizedTracePINN(
            width=64,
            hidden_layers=3,
            parameter_dim=parameter_dim,
            anchor_kind="correct",
            anchor_scale=0.1,
        )
    else:
        model = ROMGeneralizedTracePINN(
            width=64,
            hidden_layers=3,
            parameter_dim=parameter_dim,
            anchor_kind="correct",
            anchor_scale=0.0 if method == "p5_unanchored_low_rom" else 0.1,
            num_rom_shells=1,
            rom_modes=(
                P5_HIGH_FREQUENCY_MODES if method == "p5_highfreq_rom" else None
            ),
            rom_hidden_width=32,
            rom_hidden_layers=2,
            num_charts=1,
            chart_temperature=0.25,
            rom_schedule="constant",
            potential_family=potential_family,
            parameter_lower=lower,
            parameter_upper=upper,
        )
    return model.to(device=device, dtype=dtype)

"""Two PINN variants for one angular mode of the unit-disk Wentzell problem (R32 amendment 2).

Layer lifting: F = N + delta * w((1 - s)/2, t; c) * exp(-t / tau), where
    delta = (F_t demanded by the dynamic BC) - (F_t demanded by the bulk equation) at s=1, t=0,
    w solves the half-line model w_t = w_xx, c w_t - w_x = c at x = 0, w(x, 0) = 0 (unit mismatch).
  Near the corner the reduced problem is F_t ~ F_xx with c F_t + b F - F_x = 0 (x = (1 - s)/2), so the
  lifted remainder N is compatible at leading order.  The time factor keeps the correction local in time.
Hard initial condition (baseline): F = f(s) + t * N.
Decay scaling: F = exp(-lambda t) * N with lambda the slowest eigenvalue of the mode; the bulk and
  boundary residuals are multiplied by exp(lambda t), i.e. the loss is the residual of the N-equation.
The base network and the training loop are the frozen vanilla ones.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import torch
from numpy.polynomial import Polynomial
from torch import nn

from pinn_vanilla import MLP, Config, Problem, TrainResult, train

torch.set_default_dtype(torch.float64)


@dataclass(frozen=True)
class Variant:
    layer: bool
    decay: bool
    tau: float = 0.1
    hard_ic: bool = False

    @property
    def name(self) -> str:
        parts = [n for n, on in (("hardic", self.hard_ic), ("layer", self.layer), ("decay", self.decay)) if on]
        return "+".join(parts) if parts else "vanilla"


def layer_profile(x: torch.Tensor, t: torch.Tensor, c: float) -> torch.Tensor:
    """Unit-mismatch half-line solution, written with erfcx so it is stable for small c and large t."""
    rt = torch.sqrt(t.clamp_min(1e-30))
    eta = x / (2.0 * rt)
    gauss = torch.exp(-(eta**2))
    ierfc = gauss / math.sqrt(math.pi) - eta * torch.special.erfc(eta)
    impedance = torch.special.erfc(eta) - gauss * torch.special.erfcx(eta + rt / c)
    return c * (2.0 * rt * ierfc - c * impedance)


def corner_mismatch(p: Problem) -> float:
    f = Polynomial(np.asarray(p.poly, dtype=float))
    f1, fs, fss = f(1.0), f.deriv(1)(1.0), f.deriv(2)(1.0)
    bulk = 4.0 * fss + 4.0 * (p.m + 1) * fs
    boundary = -(p.b * f1 + 2.0 * fs) / p.c
    return float(boundary - bulk)


class LiftedNet(nn.Module):
    def __init__(self, base: nn.Module, p: Problem, variant: Variant, lam: float = 0.0):
        super().__init__()
        self.base = base
        self.variant = variant
        self.problem = p
        self.c = p.c
        self.lam = float(lam)
        self.delta = corner_mismatch(p) if variant.layer else 0.0

    def forward(self, s: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        out = self.base(s, t)
        if self.variant.hard_ic:
            out = self.problem.f0(s) + t * out
        if self.variant.decay:
            out = torch.exp(-self.lam * t) * out
        if self.variant.layer:
            out = out + self.delta * layer_profile(0.5 * (1.0 - s), t, self.c) * torch.exp(-t / self.variant.tau)
        return out

    def time_weight(self, t: torch.Tensor) -> torch.Tensor:
        return torch.exp(self.lam * t) if self.variant.decay else torch.ones_like(t)


def train_variant(p: Problem, cfg: Config, variant: Variant, lam: float) -> TrainResult:
    return train(p, cfg, make_net=lambda: LiftedNet(MLP(cfg.width, cfg.depth), p, variant, lam))

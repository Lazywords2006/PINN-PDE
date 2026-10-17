"""R33 screening PINNs for the 1D dynamic-boundary problems in problems.py (one network, five constructions).

    vanilla       u = N                                   (all soft)
    hardic        u = f + t N                             (hard initial condition)
    rba           u = N, residual-based attention point weights (Anagnostopoulos et al. 2024)
    layer         u = N + delta w(y, t; c') exp(-t/tau)   (R32 initial-layer lifting)
    hardic+layer  u = f + t N + delta w(y, t; c') exp(-t/tau)
with y = (1 - x)/sqrt(D), c' = c/sqrt(D) and w the half-line unit-mismatch solution (same formula as R32).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass

import torch
from torch import nn

from problems import Problem1D

torch.set_default_dtype(torch.float64)
METHODS = ("vanilla", "hardic", "rba", "layer", "hardic+layer")


@dataclass(frozen=True)
class Config:
    width: int = 64
    depth: int = 4
    adam_steps: int = 4000
    lr0: float = 1e-3
    lr1: float = 1e-5
    nf: int = 2048
    nb: int = 128
    n0: int = 256
    lbfgs_iters: int = 500
    lbfgs_chunk: int = 50
    nf_fixed: int = 4096
    nb_fixed: int = 256
    n0_fixed: int = 512
    tau: float = 0.1
    rba_gamma: float = 0.999
    rba_eta: float = 0.01
    seed: int = 0


def layer_profile(y: torch.Tensor, t: torch.Tensor, c: float) -> torch.Tensor:
    """w_t = w_yy (y > 0), c w_t - w_y = c at y = 0, w(y, 0) = 0; copied from R32 pinn_improved.layer_profile."""
    rt = torch.sqrt(t.clamp_min(1e-30))
    eta = y / (2.0 * rt)
    gauss = torch.exp(-(eta**2))
    ierfc = gauss / math.sqrt(math.pi) - eta * torch.special.erfc(eta)
    impedance = torch.special.erfc(eta) - gauss * torch.special.erfcx(eta + rt / c)
    return c * (2.0 * rt * ierfc - c * impedance)


class MLP(nn.Module):
    def __init__(self, width: int, depth: int):
        super().__init__()
        dims = [2] + [width] * depth + [1]
        self.layers = nn.ModuleList(nn.Linear(a, b) for a, b in zip(dims[:-1], dims[1:]))
        for layer in self.layers:
            nn.init.xavier_normal_(layer.weight)
            nn.init.zeros_(layer.bias)

    def forward(self, x: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        h = torch.stack([x, t], dim=-1)
        for layer in self.layers[:-1]:
            h = torch.tanh(layer(h))
        return self.layers[-1](h).squeeze(-1)


class Model(nn.Module):
    def __init__(self, p: Problem1D, method: str, cfg: Config):
        super().__init__()
        self.base = MLP(cfg.width, cfg.depth)
        self.p, self.method, self.tau = p, method, cfg.tau
        self.hard = method.startswith("hardic")
        self.layer = method.endswith("layer")
        self.delta = p.mismatch() if self.layer else 0.0
        self.sqrt_d = math.sqrt(p.D)

    def forward(self, x: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        out = self.base(x, t)
        if self.hard:
            out = self.p.f(x) + t * out
        if self.layer:
            y = (1.0 - x) / self.sqrt_d
            out = out + self.delta * layer_profile(y, t, self.p.c / self.sqrt_d) * torch.exp(-t / self.tau)
        return out


def _d(y, x):
    return torch.autograd.grad(y.sum(), x, create_graph=True)[0]


def residuals(model: Model, pts) -> list[torch.Tensor]:
    p = model.p
    x_f, t_f, t_b0, t_b1, x_0 = pts
    x = x_f.clone().requires_grad_(True)
    t = t_f.clone().requires_grad_(True)
    u = model(x, t)
    u_x = _d(u, x)
    r_pde = _d(u, t) - p.D * _d(u_x, x) - p.R(u)
    x = torch.zeros_like(t_b0).requires_grad_(True)
    r_b0 = _d(model(x, t_b0), x)
    x = torch.ones_like(t_b1).requires_grad_(True)
    t = t_b1.clone().requires_grad_(True)
    u = model(x, t)
    r_b1 = p.c * _d(u, t) + p.D * _d(u, x) + p.G(u)
    out = [r_pde, r_b0, r_b1]
    if not model.hard:
        out.append(model(x_0, torch.zeros_like(x_0)) - p.f(x_0))
    return out


def train(p: Problem1D, method: str, cfg: Config) -> tuple[Model, dict]:
    torch.manual_seed(cfg.seed)
    gen = torch.Generator().manual_seed(1000 + cfg.seed)
    model = Model(p, method, cfg)
    rba = method == "rba"

    def draw(nf, nb, n0):
        return (torch.rand(nf, generator=gen), torch.rand(nf, generator=gen), torch.rand(nb, generator=gen),
                torch.rand(nb, generator=gen), torch.rand(n0, generator=gen))

    fixed_adam = draw(cfg.nf, cfg.nb, cfg.n0) if rba else None
    lam = [torch.ones(n) for n in (cfg.nf, cfg.nb, cfg.nb, cfg.n0)] if rba else None

    def loss_of(res, weights=None):
        if weights is None:
            return sum(r.pow(2).mean() for r in res)
        return sum((w * r).pow(2).mean() for w, r in zip(weights, res))

    hist = {"loss": [], "lbfgs_loss": []}
    start = time.perf_counter()
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr0)
    sched = torch.optim.lr_scheduler.ExponentialLR(opt, (cfg.lr1 / cfg.lr0) ** (1.0 / cfg.adam_steps))
    for step in range(cfg.adam_steps):
        res = residuals(model, fixed_adam if rba else draw(cfg.nf, cfg.nb, cfg.n0))
        loss = loss_of(res, lam)
        opt.zero_grad()
        loss.backward()
        opt.step()
        sched.step()
        if rba:
            with torch.no_grad():
                for i, r in enumerate(res):
                    a = r.detach().abs()
                    lam[i] = cfg.rba_gamma * lam[i] + cfg.rba_eta * a / a.max().clamp_min(1e-300)
        if step % 10 == 0:
            hist["loss"].append(loss.item())
    adam_seconds = time.perf_counter() - start

    pts = fixed_adam if rba else draw(cfg.nf_fixed, cfg.nb_fixed, cfg.n0_fixed)
    lbfgs = torch.optim.LBFGS(model.parameters(), lr=1.0, max_iter=cfg.lbfgs_chunk, history_size=50,
                              line_search_fn="strong_wolfe", tolerance_grad=1e-14, tolerance_change=1e-16)

    def closure():
        lbfgs.zero_grad()
        value = loss_of(residuals(model, pts), lam)
        value.backward()
        return value

    hist["lbfgs_loss"].append(loss_of(residuals(model, pts), lam).item())
    done = 0
    while done < cfg.lbfgs_iters:
        lbfgs.step(closure)
        done += cfg.lbfgs_chunk
        hist["lbfgs_loss"].append(loss_of(residuals(model, pts), lam).item())
        if hist["lbfgs_loss"][-1] >= hist["lbfgs_loss"][-2] * (1.0 - 1e-9):
            break
    hist["wall_seconds"] = time.perf_counter() - start
    hist["adam_seconds"] = adam_seconds
    return model, hist

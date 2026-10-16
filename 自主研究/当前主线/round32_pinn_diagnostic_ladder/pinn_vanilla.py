"""Vanilla PINN for one angular mode of the unit-disk Wentzell problem (frozen R32 configuration).

Soft constraints only: bulk residual, dynamic-boundary residual and initial mismatch, equal weights.
Adam with exponentially decayed learning rate, then L-BFGS on a fixed point set.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import torch
from torch import nn

torch.set_default_dtype(torch.float64)


@dataclass(frozen=True)
class Problem:
    name: str
    m: int
    c: float
    d: float
    kappa: float
    poly: tuple[float, ...]

    @property
    def b(self) -> float:
        return self.d * self.m**2 + self.kappa + self.m

    def f0(self, s: torch.Tensor) -> torch.Tensor:
        return sum(coef * s**i for i, coef in enumerate(self.poly))


@dataclass(frozen=True)
class Config:
    width: int = 64
    depth: int = 4
    adam_steps: int = 20000
    lr0: float = 1e-3
    lr1: float = 1e-5
    nf: int = 4096
    nb: int = 256
    n0: int = 256
    lbfgs_iters: int = 3000
    lbfgs_chunk: int = 50
    nf_fixed: int = 8192
    nb_fixed: int = 512
    n0_fixed: int = 512
    w_pde: float = 1.0
    w_bc: float = 1.0
    w_ic: float = 1.0
    seed: int = 0
    diag_steps: tuple[int, ...] = (0, 1000, 5000, 20000)
    t_power: float = 1.0  # collocation/boundary times drawn as U**t_power (1 = uniform, frozen default)


@dataclass
class TrainResult:
    net: nn.Module
    history: dict[str, list[float]]
    wall_seconds: float
    adam_seconds: float = 0.0
    extra: dict[str, float] = field(default_factory=dict)


class MLP(nn.Module):
    def __init__(self, width: int, depth: int):
        super().__init__()
        dims = [2] + [width] * depth + [1]
        self.layers = nn.ModuleList(nn.Linear(a, b) for a, b in zip(dims[:-1], dims[1:]))
        for layer in self.layers:
            nn.init.xavier_normal_(layer.weight)
            nn.init.zeros_(layer.bias)

    def forward(self, s: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        x = torch.stack([s, t], dim=-1)
        for layer in self.layers[:-1]:
            x = torch.tanh(layer(x))
        return self.layers[-1](x).squeeze(-1)


def _grad(y: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
    if not y.requires_grad:
        return torch.zeros_like(x)
    g = torch.autograd.grad(y.sum(), x, create_graph=True, allow_unused=True)[0]
    return torch.zeros_like(x) if g is None else g


def residual_pde(net: nn.Module, p: Problem, s: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
    s = s.detach().clone().requires_grad_(True)
    t = t.detach().clone().requires_grad_(True)
    big_f = net(s, t)
    f_s = _grad(big_f, s)
    f_t = _grad(big_f, t)
    f_ss = _grad(f_s, s)
    return f_t - 4.0 * s * f_ss - 4.0 * (p.m + 1) * f_s


def residual_bc(net: nn.Module, p: Problem, t: torch.Tensor) -> torch.Tensor:
    s = torch.ones_like(t).requires_grad_(True)
    t = t.detach().clone().requires_grad_(True)
    big_f = net(s, t)
    return p.c * _grad(big_f, t) + p.b * big_f + 2.0 * _grad(big_f, s)


def residual_ic(net: nn.Module, p: Problem, s: torch.Tensor) -> torch.Tensor:
    return net(s, torch.zeros_like(s)) - p.f0(s)


def loss_terms(net, p, s_f, t_f, t_b, s_0) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    r_pde = residual_pde(net, p, s_f, t_f)
    r_bc = residual_bc(net, p, t_b)
    time_weight = getattr(net, "time_weight", None)
    if time_weight is not None:
        r_pde = r_pde * time_weight(t_f)
        r_bc = r_bc * time_weight(t_b)
    return (r_pde.pow(2).mean(), r_bc.pow(2).mean(), residual_ic(net, p, s_0).pow(2).mean())


def _total(cfg: Config, terms) -> torch.Tensor:
    return cfg.w_pde * terms[0] + cfg.w_bc * terms[1] + cfg.w_ic * terms[2]


def _grad_norms(net: nn.Module, terms) -> list[float]:
    params = [q for q in net.parameters()]
    out = []
    for term in terms:
        g = torch.autograd.grad(term, params, retain_graph=True, allow_unused=True)
        out.append(float(torch.sqrt(sum((x**2).sum() for x in g if x is not None))))
    return out


def train(p: Problem, cfg: Config, make_net=None) -> TrainResult:
    """make_net (optional) builds the network after seeding; a `time_weight(t)` method on it scales the residuals."""
    torch.manual_seed(cfg.seed)
    gen = torch.Generator().manual_seed(1000 + cfg.seed)
    net = make_net() if make_net is not None else MLP(cfg.width, cfg.depth)
    hist: dict[str, list[float]] = {k: [] for k in ("loss", "pde", "bc", "ic", "diag_step", "grad_pde", "grad_bc", "grad_ic", "lbfgs_loss", "lbfgs_iter")}
    start = time.perf_counter()

    def draw(nf: int, nb: int, n0: int):
        s_f, t_f = torch.rand(nf, generator=gen), torch.rand(nf, generator=gen)
        t_b, s_0 = torch.rand(nb, generator=gen), torch.rand(n0, generator=gen)
        if cfg.t_power != 1.0:
            t_f, t_b = t_f**cfg.t_power, t_b**cfg.t_power
        return s_f, t_f, t_b, s_0

    opt = torch.optim.Adam(net.parameters(), lr=cfg.lr0)
    gamma = (cfg.lr1 / cfg.lr0) ** (1.0 / max(cfg.adam_steps, 1))
    sched = torch.optim.lr_scheduler.ExponentialLR(opt, gamma)
    for step in range(cfg.adam_steps):
        terms = loss_terms(net, p, *draw(cfg.nf, cfg.nb, cfg.n0))
        loss = _total(cfg, terms)
        if step in cfg.diag_steps:
            g = _grad_norms(net, terms)
            hist["diag_step"].append(step)
            hist["grad_pde"].append(g[0])
            hist["grad_bc"].append(g[1])
            hist["grad_ic"].append(g[2])
        hist["loss"].append(loss.item())
        for key, term in zip(("pde", "bc", "ic"), terms):
            hist[key].append(term.item())
        opt.zero_grad()
        loss.backward()
        opt.step()
        sched.step()
    adam_seconds = time.perf_counter() - start

    if cfg.lbfgs_iters > 0:
        pts = draw(cfg.nf_fixed, cfg.nb_fixed, cfg.n0_fixed)
        lbfgs = torch.optim.LBFGS(net.parameters(), lr=1.0, max_iter=cfg.lbfgs_chunk, history_size=50, line_search_fn="strong_wolfe", tolerance_grad=1e-14, tolerance_change=1e-16)

        def closure():
            lbfgs.zero_grad()
            value = _total(cfg, loss_terms(net, p, *pts))
            value.backward()
            return value

        hist["lbfgs_loss"].append(_total(cfg, loss_terms(net, p, *pts)).item())
        hist["lbfgs_iter"].append(0)
        done = 0
        while done < cfg.lbfgs_iters:
            lbfgs.step(closure)
            done += cfg.lbfgs_chunk
            hist["lbfgs_loss"].append(_total(cfg, loss_terms(net, p, *pts)).item())
            hist["lbfgs_iter"].append(done)
            if hist["lbfgs_loss"][-1] >= hist["lbfgs_loss"][-2] * (1.0 - 1e-9):
                break
    return TrainResult(net=net, history=hist, wall_seconds=time.perf_counter() - start, adam_seconds=adam_seconds)


def net_fn(net: nn.Module):
    """Numpy field function (F, F_s) of a trained network, as the evaluator expects."""

    def fn(s: np.ndarray, t: float) -> tuple[np.ndarray, np.ndarray]:
        s_t = torch.tensor(np.asarray(s, dtype=float), requires_grad=True)
        big_f = net(s_t, torch.full_like(s_t, float(t)))
        f_s = torch.autograd.grad(big_f.sum(), s_t)[0]
        return big_f.detach().numpy(), f_s.detach().numpy()

    return fn

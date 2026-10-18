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
    arch: str = "mlp"  # "mlp" or "pirate" (PirateNet, Wang et al. 2024)
    pirate_blocks: int = 3
    fourier_scale: float = 1.0
    causal_eps: float = 0.0  # > 0: causal weighting (Wang, Sankaran, Perdikaris 2022) with this epsilon
    causal_chunks: int = 32


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


class PirateNet(nn.Module):
    """PirateNet (Wang, Li, Chen, Perdikaris, JMLR 2024): random Fourier embedding, gated residual blocks with
    adaptive skip weights alpha (initialised at 0, so the network starts as a shallow model). The physics-informed
    least-squares initialisation of the last layer is not used."""

    def __init__(self, width: int, blocks: int, scale: float):
        super().__init__()
        self.register_buffer("B", scale * torch.randn(2, width // 2))
        self.u = nn.Linear(width, width)
        self.v = nn.Linear(width, width)
        self.blocks = nn.ModuleList(nn.ModuleList(nn.Linear(width, width) for _ in range(3)) for _ in range(blocks))
        self.alpha = nn.Parameter(torch.zeros(blocks))
        self.out = nn.Linear(width, 1)
        for layer in [self.u, self.v, self.out] + [l for b in self.blocks for l in b]:
            nn.init.xavier_normal_(layer.weight)
            nn.init.zeros_(layer.bias)

    def forward(self, x: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        z = torch.stack([x, t], dim=-1) @ self.B
        h = torch.cat([torch.cos(z), torch.sin(z)], dim=-1)
        u, v = torch.tanh(self.u(h)), torch.tanh(self.v(h))
        for k, (l1, l2, l3) in enumerate(self.blocks):
            f = torch.tanh(l1(h))
            z1 = f * u + (1.0 - f) * v
            g = torch.tanh(l2(z1))
            z2 = g * u + (1.0 - g) * v
            h = self.alpha[k] * torch.tanh(l3(z2)) + (1.0 - self.alpha[k]) * h
        return self.out(h).squeeze(-1)


class Model(nn.Module):
    def __init__(self, p: Problem1D, method: str, cfg: Config):
        super().__init__()
        self.base = MLP(cfg.width, cfg.depth) if cfg.arch == "mlp" else PirateNet(cfg.width, cfg.pirate_blocks, cfg.fourier_scale)
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


def train(p: Problem1D, method: str, cfg: Config, ckpt: str | None = None, ckpt_every: int = 500) -> tuple[Model, dict]:
    """ckpt (optional): file used to save training state every `ckpt_every` Adam steps and after every L-BFGS chunk,
    and to resume from after an interruption. Resuming restores the network, optimiser, scheduler, sampling generator,
    RBA weights and point sets, so the remaining steps see the same samples as an uninterrupted run."""
    import os

    torch.manual_seed(cfg.seed)
    gen = torch.Generator().manual_seed(1000 + cfg.seed)
    model = Model(p, method, cfg)
    rba = method == "rba"

    def draw(nf, nb, n0):
        return (torch.rand(nf, generator=gen), torch.rand(nf, generator=gen), torch.rand(nb, generator=gen),
                torch.rand(nb, generator=gen), torch.rand(n0, generator=gen))

    fixed_adam = draw(cfg.nf, cfg.nb, cfg.n0) if rba else None
    lam = [torch.ones(n) for n in (cfg.nf, cfg.nb, cfg.nb, cfg.n0)] if rba else None

    def causal_mean(r, t):
        """Causal weighting: chunk losses L_k in time, weights exp(-eps * sum_{j<k} L_j) (no gradient)."""
        idx = (t * cfg.causal_chunks).long().clamp(0, cfg.causal_chunks - 1)
        sums = torch.zeros(cfg.causal_chunks).index_add(0, idx, r.pow(2))
        counts = torch.zeros(cfg.causal_chunks).index_add(0, idx, torch.ones_like(r)).clamp_min(1.0)
        chunk = sums / counts
        w = torch.exp(-cfg.causal_eps * (torch.cumsum(chunk, 0) - chunk)).detach()
        return (w * chunk).mean()

    def loss_of(res, weights=None, pts_used=None):
        if cfg.causal_eps > 0.0:
            _, t_f, t_b0, t_b1, _ = pts_used
            out = causal_mean(res[0], t_f) + causal_mean(res[1], t_b0) + causal_mean(res[2], t_b1)
            return out + sum(r.pow(2).mean() for r in res[3:])
        if weights is None:
            return sum(r.pow(2).mean() for r in res)
        return sum((w * r).pow(2).mean() for w, r in zip(weights, res))

    hist = {"loss": [], "lbfgs_loss": [], "resumed_at": []}
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr0)
    sched = torch.optim.lr_scheduler.ExponentialLR(opt, (cfg.lr1 / cfg.lr0) ** (1.0 / cfg.adam_steps))
    state = {"phase": "adam", "step": 0, "elapsed": 0.0, "adam_seconds": 0.0, "done": 0}
    pts = lbfgs_state = None
    if ckpt and os.path.exists(ckpt):
        c = torch.load(ckpt, weights_only=False)
        model.load_state_dict(c["model"])
        opt.load_state_dict(c["opt"])
        sched.load_state_dict(c["sched"])
        gen.set_state(c["gen"])
        fixed_adam, lam, hist, state, pts, lbfgs_state = c["fixed_adam"], c["lam"], c["hist"], c["state"], c["pts"], c["lbfgs"]
        hist["resumed_at"].append(f"{state['phase']}:{state['step'] if state['phase'] == 'adam' else state['done']}")

    def save(lbfgs_opt=None):
        if not ckpt:
            return
        tmp = ckpt + ".tmp"
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "sched": sched.state_dict(),
                    "gen": gen.get_state(), "fixed_adam": fixed_adam, "lam": lam, "hist": hist, "state": state,
                    "pts": pts, "lbfgs": lbfgs_opt.state_dict() if lbfgs_opt is not None else None}, tmp)
        os.replace(tmp, ckpt)

    seg_start = time.perf_counter()
    base_elapsed = state["elapsed"]
    if state["phase"] == "adam":
        for step in range(state["step"], cfg.adam_steps):
            pts_step = fixed_adam if rba else draw(cfg.nf, cfg.nb, cfg.n0)
            res = residuals(model, pts_step)
            loss = loss_of(res, lam, pts_step)
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
            if (step + 1) % ckpt_every == 0 and step + 1 < cfg.adam_steps:
                state.update(step=step + 1, elapsed=base_elapsed + time.perf_counter() - seg_start)
                save()
        state["adam_seconds"] = base_elapsed + time.perf_counter() - seg_start
        pts = fixed_adam if rba else draw(cfg.nf_fixed, cfg.nb_fixed, cfg.n0_fixed)
        state.update(phase="lbfgs", step=cfg.adam_steps, done=0, elapsed=state["adam_seconds"])
        save()

    lbfgs = torch.optim.LBFGS(model.parameters(), lr=1.0, max_iter=cfg.lbfgs_chunk, history_size=50,
                              line_search_fn="strong_wolfe", tolerance_grad=1e-14, tolerance_change=1e-16)
    if lbfgs_state is not None:
        lbfgs.load_state_dict(lbfgs_state)

    def closure():
        lbfgs.zero_grad()
        value = loss_of(residuals(model, pts), lam, pts)
        value.backward()
        return value

    if not hist["lbfgs_loss"]:
        hist["lbfgs_loss"].append(loss_of(residuals(model, pts), lam, pts).item())
    done = state["done"]
    stopped = len(hist["lbfgs_loss"]) >= 2 and hist["lbfgs_loss"][-1] >= hist["lbfgs_loss"][-2] * (1.0 - 1e-9)
    while done < cfg.lbfgs_iters and not stopped:
        lbfgs.step(closure)
        done += cfg.lbfgs_chunk
        hist["lbfgs_loss"].append(loss_of(residuals(model, pts), lam, pts).item())
        stopped = hist["lbfgs_loss"][-1] >= hist["lbfgs_loss"][-2] * (1.0 - 1e-9)
        state.update(done=done, elapsed=base_elapsed + time.perf_counter() - seg_start)
        save(lbfgs)
    hist["wall_seconds"] = base_elapsed + time.perf_counter() - seg_start
    hist["adam_seconds"] = state["adam_seconds"]
    return model, hist

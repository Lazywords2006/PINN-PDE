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
    w_ic: float = 1.0  # weight on the (soft) initial-condition loss; > 1 for the "heavy IC weight" baseline
    t_refine: float = 0.0  # fraction of collocation/boundary times drawn from the first segment [0, 0.01]
    optimizer: str = "adam"  # "adam" or "soap" (own implementation of Vyas et al. 2024)
    soap_freq: int = 10
    soap_beta: float = 0.95


def layer_profile(y: torch.Tensor, t: torch.Tensor, c: float) -> torch.Tensor:
    """w_t = w_yy (y > 0), c w_t - w_y = c at y = 0, w(y, 0) = 0; copied from R32 pinn_improved.layer_profile."""
    rt = torch.sqrt(t.clamp_min(1e-30))
    eta = y / (2.0 * rt)
    gauss = torch.exp(-(eta**2))
    ierfc = gauss / math.sqrt(math.pi) - eta * torch.special.erfc(eta)
    impedance = torch.special.erfc(eta) - gauss * torch.special.erfcx(eta + rt / c)
    return c * (2.0 * rt * ierfc - c * impedance)


def flux_layer(y: torch.Tensor, t: torch.Tensor, d: float, delta_y: float) -> torch.Tensor:
    """E4 flux layer: U_t = D U_yy (y > 0), D U_y(0, t) = delta_y, U(y, 0) = 0, i.e.
    U = -2 delta_y sqrt(t/D) ierfc(y / (2 sqrt(D t)))."""
    rt = torch.sqrt(t.clamp_min(1e-30))
    eta = y / (2.0 * math.sqrt(d) * rt)
    ierfc = torch.exp(-(eta**2)) * (1.0 / math.sqrt(math.pi) - eta * torch.special.erfcx(eta))
    return -2.0 * delta_y * rt / math.sqrt(d) * ierfc


class SurfaceNet(nn.Module):
    """E4 surface variable network v(t): tanh MLP 3 x 32."""

    def __init__(self, width: int = 32, depth: int = 3):
        super().__init__()
        dims = [1] + [width] * depth + [1]
        self.layers = nn.ModuleList(nn.Linear(a, b) for a, b in zip(dims[:-1], dims[1:]))
        for layer in self.layers:
            nn.init.xavier_normal_(layer.weight)
            nn.init.zeros_(layer.bias)

    def forward(self, t: torch.Tensor) -> torch.Tensor:
        h = t.unsqueeze(-1)
        for layer in self.layers[:-1]:
            h = torch.tanh(layer(h))
        return self.layers[-1](h).squeeze(-1)


class SOAP(torch.optim.Optimizer):
    """SOAP (Vyas, Chen, Morwani, Kakade et al. 2024): Adam run in the eigenbasis of the Shampoo preconditioner.
    Own float64 implementation (the `heavyball` package does not support float64). 2-D parameters get the rotated
    Adam update; 1-D parameters (biases, alpha) use plain Adam. The eigenbasis is refreshed every `freq` steps and
    the first moment is re-expressed in the new basis."""

    def __init__(self, params, lr=1e-3, betas=(0.95, 0.95), shampoo_beta=0.95, eps=1e-8, freq=10):
        super().__init__(params, dict(lr=lr, betas=betas, shampoo_beta=shampoo_beta, eps=eps, freq=freq))

    @staticmethod
    def _eigbasis(gg):
        _, q = torch.linalg.eigh(gg + 1e-30 * torch.eye(gg.shape[0], dtype=gg.dtype))
        return q.flip(-1)

    @torch.no_grad()
    def step(self, closure=None):
        loss = None
        if closure is not None:
            with torch.enable_grad():
                loss = closure()
        for group in self.param_groups:
            b1, b2 = group["betas"]
            for p in group["params"]:
                if p.grad is None:
                    continue
                g = p.grad
                st = self.state[p]
                if not st:
                    st["step"] = 0
                    st["m"] = torch.zeros_like(p)
                    st["v"] = torch.zeros_like(p)
                    if p.ndim == 2:
                        st["L"] = torch.zeros(p.shape[0], p.shape[0], dtype=p.dtype)
                        st["R"] = torch.zeros(p.shape[1], p.shape[1], dtype=p.dtype)
                st["step"] += 1
                t = st["step"]
                if p.ndim == 2:
                    sb = group["shampoo_beta"]
                    st["L"].mul_(sb).add_(g @ g.T, alpha=1 - sb)
                    st["R"].mul_(sb).add_(g.T @ g, alpha=1 - sb)
                    if t == 1:
                        st["QL"], st["QR"] = self._eigbasis(st["L"]), self._eigbasis(st["R"])
                    elif t % group["freq"] == 0:
                        m_orig = st["QL"] @ st["m"] @ st["QR"].T
                        st["QL"], st["QR"] = self._eigbasis(st["L"]), self._eigbasis(st["R"])
                        st["m"] = st["QL"].T @ m_orig @ st["QR"]
                    gr = st["QL"].T @ g @ st["QR"]
                else:
                    gr = g
                st["m"].mul_(b1).add_(gr, alpha=1 - b1)
                st["v"].mul_(b2).addcmul_(gr, gr, value=1 - b2)
                mhat = st["m"] / (1 - b1**t)
                vhat = st["v"] / (1 - b2**t)
                upd = mhat / (vhat.sqrt() + group["eps"])
                if p.ndim == 2:
                    upd = st["QL"] @ upd @ st["QR"].T
                p.add_(upd, alpha=-group["lr"])
        return loss


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
        self.bulk_surface = getattr(p, "kind", "") == "bulk_surface"
        if self.bulk_surface:
            self.surf = SurfaceNet()

    def forward(self, x: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        out = self.base(x, t)
        if self.hard:
            out = self.p.f(x) + t * out
        if self.layer:
            if self.bulk_surface:
                out = out + flux_layer(1.0 - x, t, self.p.D, self.delta) * torch.exp(-t / self.tau)
            else:
                y = (1.0 - x) / self.sqrt_d
                out = out + self.delta * layer_profile(y, t, self.p.c / self.sqrt_d) * torch.exp(-t / self.tau)
        return out

    def surface(self, t: torch.Tensor) -> torch.Tensor:
        """E4 surface variable v(t); hard initial condition v = V0 + t N_v."""
        out = self.surf(t)
        return self.p.V0 + t * out if self.hard else out


def _d(y, x):
    return torch.autograd.grad(y.sum(), x, create_graph=True)[0]


def residuals_bulk_surface(model: Model, pts) -> list[torch.Tensor]:
    """E4 residuals: bulk, Neumann at x = 0, exchange flux at x = 1, surface ODE, then (soft IC only) u and v initial."""
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
    v = model.surface(t)
    r_flux = p.D * _d(u, x) - p.kappa * (v - u)
    r_surf = _d(v, t) - p.kappa * (u - v) + p.gamma * v**3
    out = [r_pde, r_b0, r_flux, r_surf]
    if not model.hard:
        out.append(model(x_0, torch.zeros_like(x_0)) - p.f(x_0))
        out.append((model.surface(torch.zeros(1)) - p.V0))
    return out


def residuals(model: Model, pts) -> list[torch.Tensor]:
    if model.bulk_surface:
        return residuals_bulk_surface(model, pts)
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
        pts = (torch.rand(nf, generator=gen), torch.rand(nf, generator=gen), torch.rand(nb, generator=gen),
               torch.rand(nb, generator=gen), torch.rand(n0, generator=gen))
        if cfg.t_refine > 0.0:  # a fraction of the times goes to the first segment [0, 0.01]
            x_f, t_f, t_b0, t_b1, x_0 = pts
            t_f, t_b0, t_b1 = t_f.clone(), t_b0.clone(), t_b1.clone()
            t_f[: int(cfg.t_refine * nf)] *= 0.01
            t_b0[: int(cfg.t_refine * nb)] *= 0.01
            t_b1[: int(cfg.t_refine * nb)] *= 0.01
            pts = (x_f, t_f, t_b0, t_b1, x_0)
        return pts

    fixed_adam = draw(cfg.nf, cfg.nb, cfg.n0) if rba else None
    sizes = (cfg.nf, cfg.nb, cfg.nb, cfg.nb, cfg.n0, 1) if model.bulk_surface else (cfg.nf, cfg.nb, cfg.nb, cfg.n0)
    lam = [torch.ones(n) for n in sizes] if rba else None

    def causal_mean(r, t):
        """Causal weighting: chunk losses L_k in time, weights exp(-eps * sum_{j<k} L_j) (no gradient)."""
        idx = (t * cfg.causal_chunks).long().clamp(0, cfg.causal_chunks - 1)
        sums = torch.zeros(cfg.causal_chunks).index_add(0, idx, r.pow(2))
        counts = torch.zeros(cfg.causal_chunks).index_add(0, idx, torch.ones_like(r)).clamp_min(1.0)
        chunk = sums / counts
        w = torch.exp(-cfg.causal_eps * (torch.cumsum(chunk, 0) - chunk)).detach()
        return (w * chunk).mean()

    def loss_of(res, weights=None, pts_used=None):
        if cfg.w_ic != 1.0 and not model.hard and not model.bulk_surface:
            res = list(res[:-1]) + [res[-1] * math.sqrt(cfg.w_ic)]
        if cfg.causal_eps > 0.0:
            _, t_f, t_b0, t_b1, _ = pts_used
            out = causal_mean(res[0], t_f) + causal_mean(res[1], t_b0) + causal_mean(res[2], t_b1)
            return out + sum(r.pow(2).mean() for r in res[3:])
        if weights is None:
            return sum(r.pow(2).mean() for r in res)
        return sum((w * r).pow(2).mean() for w, r in zip(weights, res))

    hist = {"loss": [], "lbfgs_loss": [], "resumed_at": []}
    if cfg.optimizer == "soap":
        opt = SOAP(model.parameters(), lr=cfg.lr0, betas=(0.95, 0.95), shampoo_beta=cfg.soap_beta, freq=cfg.soap_freq)
    else:
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

"""Failure diagnosis for one trained run: where in (r, t) the error sits, what the residuals look like,
and how the loss terms and their gradients behaved.  Observation only; nothing is retrained.

    python diagnose.py --cell-id m1_lin_c0.3_d0.1_k0.3 --seed 0 [--tag cells]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

from pinn_vanilla import MLP, Problem, residual_bc, residual_pde
from ladder import response_poly
from ref_wentzell import Mode, gauss_legendre_unit

HERE = Path(__file__).resolve().parent
T_GRID = np.logspace(np.log10(2e-3), 0.0, 60)


def load(cell_id: str, seed: int, tag: str):
    path = HERE / "runs" / tag / f"{cell_id}_s{seed}.json"
    rec = json.loads(path.read_text())
    cfg = rec["config"]
    cl = rec["cell"]
    m, poly = response_poly(cl)
    prob = Problem(cl["response"], m, cl["c"], cl["d"], cl["kappa"], tuple(float(x) for x in poly))
    net = MLP(cfg["width"], cfg["depth"])
    vinfo = rec.get("variant", {"name": "vanilla"})
    if vinfo["name"] != "vanilla":
        from pinn_improved import LiftedNet, Variant

        variant = Variant(layer="layer" in vinfo["name"], decay="decay" in vinfo["name"], tau=vinfo["tau"], hard_ic="hardic" in vinfo["name"])
        net = LiftedNet(net, prob, variant, vinfo["lam"])
    net.load_state_dict(torch.load(path.with_suffix(".pt")))
    ref = Mode(m, cl["c"], cl["d"], cl["kappa"], np.asarray(poly), mu_max=300.0)
    return rec, net, prob, ref


def field(net: MLP, s: np.ndarray, t: float) -> np.ndarray:
    with torch.no_grad():
        return net(torch.tensor(s), torch.full((len(s),), float(t))).numpy()


def diagnose(cell_id: str, seed: int, tag: str) -> dict:
    rec, net, prob, ref = load(cell_id, seed, tag)
    m = prob.m
    r, w = gauss_legendre_unit(200)
    s = r**2
    vol, trace, loc_r, early = [], [], [], []
    err_map = np.zeros((len(T_GRID), len(r)))
    for j, t in enumerate(T_GRID):
        ft = r**m * field(net, s, t)
        ft_ref = ref.f(r, t)
        err_map[j] = np.abs(ft - ft_ref)
        den = np.sqrt(np.sum(w * r * ft_ref**2))
        vol.append(float(np.sqrt(np.sum(w * r * (ft - ft_ref) ** 2)) / den))
        tr = float(field(net, np.array([1.0]), t)[0])
        trace.append(abs(tr - ref.trace(t)) / max(abs(ref.trace(t)), 1e-12))
        loc_r.append(float(r[np.argmax(err_map[j])]))
    # residual maps
    t_res = torch.tensor(T_GRID)
    pde_rms = []
    for t in T_GRID:
        sv = torch.tensor(np.linspace(0.0, 1.0, 400))
        pde_rms.append(float(residual_pde(net, prob, sv, torch.full_like(sv, float(t))).pow(2).mean().sqrt()))
    bc = residual_bc(net, prob, t_res).detach().numpy()
    h = rec["history"]
    ic_err = float(np.sqrt(np.mean((field(net, s, 0.0) - np.polynomial.polynomial.polyval(s, np.asarray(prob.poly))) ** 2)))
    out = {
        "cell": cell_id,
        "seed": seed,
        "vol_err_over_t": dict(zip([f"{t:.4g}" for t in T_GRID[::6]], vol[::6])),
        "trace_err_over_t": dict(zip([f"{t:.4g}" for t in T_GRID[::6]], trace[::6])),
        "r_of_max_error_over_t": dict(zip([f"{t:.4g}" for t in T_GRID[::6]], loc_r[::6])),
        "worst_t_vol": float(T_GRID[int(np.argmax(vol))]),
        "worst_t_trace": float(T_GRID[int(np.argmax(trace))]),
        "ic_rms_error": ic_err,
        "bc_residual_rms": float(np.sqrt(np.mean(bc**2))),
        "pde_residual_rms_over_t": dict(zip([f"{t:.4g}" for t in T_GRID[::6]], pde_rms[::6])),
        "final_losses": {k: h[k][-1] for k in ("pde", "bc", "ic") if h[k]},
        "final_adam_loss": rec["final_adam_loss"],
        "final_lbfgs_loss": rec["final_lbfgs_loss"],
        "grad_norms": {"step": h["diag_step"], "pde": h["grad_pde"], "bc": h["grad_bc"], "ic": h["grad_ic"]},
        "wall_seconds": rec["wall_seconds"],
        "metrics_max": {k: max(v) for k, v in rec["metrics"].items()},
    }
    fig, ax = plt.subplots(2, 2, figsize=(11, 8))
    for key in ("pde", "bc", "ic"):
        ax[0, 0].semilogy(np.arange(len(h[key])) * 10, h[key], label=key, lw=0.8)
    ax[0, 0].set_title("Adam loss terms")
    ax[0, 0].legend()
    ax[0, 1].loglog(T_GRID, vol, label="volume rel L2")
    ax[0, 1].loglog(T_GRID, trace, label="trace rel err")
    ax[0, 1].set_title("error vs t")
    ax[0, 1].legend()
    im = ax[1, 0].pcolormesh(r, T_GRID, np.log10(err_map + 1e-16), shading="auto")
    ax[1, 0].set_yscale("log")
    ax[1, 0].set_title("log10 |f - f_ref|  (r, t)")
    fig.colorbar(im, ax=ax[1, 0])
    ax[1, 1].loglog(T_GRID, pde_rms, label="PDE residual rms")
    ax[1, 1].loglog(T_GRID, np.abs(bc) + 1e-16, label="|BC residual|")
    ax[1, 1].set_title("residuals vs t")
    ax[1, 1].legend()
    fig.suptitle(f"{cell_id} seed {seed}")
    fig.tight_layout()
    fig_path = HERE / "runs" / tag / f"{cell_id}_s{seed}_diag.png"
    fig.savefig(fig_path, dpi=110)
    out["figure"] = str(fig_path.relative_to(HERE))
    (HERE / "runs" / tag / f"{cell_id}_s{seed}_diag.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell-id", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tag", default="cells")
    a = ap.parse_args()
    print(json.dumps(diagnose(a.cell_id, a.seed, a.tag), indent=1))

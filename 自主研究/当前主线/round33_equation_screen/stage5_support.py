"""Amendment-5 reference and independent diagnostics; no training or parameter selection."""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq


def eigen_e1_cos(x, t, n_modes=400):
    """Independent spectral expansion for f=0.5*cos(pi*x), including boundary mass c=0.3."""
    c, kappa = 0.3, 0.3
    def equation(mu):
        return (kappa - c * mu**2) * np.cos(mu) - mu * np.sin(mu)
    grid = np.linspace(1e-6, 1300.0, 400000)
    vals = equation(grid)
    roots = np.array([brentq(equation, grid[i], grid[i+1])
                      for i in np.nonzero(np.sign(vals[:-1]) != np.sign(vals[1:]))[0]][:n_modes])
    if len(roots) != n_modes:
        raise ValueError("insufficient eigenmodes")
    # Analytic integrals, independent of Chebyshev MOL and its interpolation.
    integral = 0.5 * (np.sinc((roots - np.pi) / np.pi) + np.sinc((roots + np.pi) / np.pi))
    num = 0.5 * integral - 0.5 * c * np.cos(roots)
    den = 0.5 + np.sin(2 * roots) / (4 * roots) + c * np.cos(roots)**2
    return ((num / den * np.exp(-roots**2 * t))[:, None]
            * np.cos(roots[:, None] * np.asarray(x)[None, :])).sum(axis=0)


def check_new_references():
    from problems import IC_CASES, OUT_TIMES, get_reference
    x = np.linspace(0, 1, 401)
    rows = []
    for name, p in IC_CASES.items():
        lo, hi = get_reference(p, 48), get_reference(p, 96)
        err = max(float(np.max(np.abs(lo(x, t) - hi(x, t)))) for t in OUT_TIMES)
        eigen_err = (max(float(np.max(np.abs(hi(x, t) - eigen_e1_cos(x, t)))) for t in OUT_TIMES)
                     if name == "E1_heat_cos" else None)
        rows.append({"eq": name, "delta": p.mismatch(), "N48_N96_max_abs": err,
                     "independent_eigen_max_abs": eigen_err,
                     "passed": err <= 1e-8 and (eigen_err is None or eigen_err <= 1e-8)})
    return rows


def heldout_residuals(model):
    """Fixed independent diagnostics, evaluated in chunks without optimizer updates."""
    import torch
    from pinn1d import residuals
    rng = np.random.default_rng(330500)
    pts = (rng.uniform(0, 1, 8192), rng.uniform(1e-4, 1, 8192),
           rng.uniform(1e-4, 1, 1024), rng.uniform(1e-4, 1, 1024), rng.uniform(0, 1, 1024))
    collected = [[], [], []]
    # Each call uses slices of the same registered points; no resampling across models.
    for start in range(0, 8192, 1024):
        inputs = tuple(torch.tensor(a[start:start+1024] if i < 2 else a) for i, a in enumerate(pts))
        out = residuals(model, inputs)
        collected[0].append(out[0].detach().numpy())
        if start == 0:
            collected[1].append(out[1].detach().numpy())
            collected[2].append(out[2].detach().numpy())
        del out
    with torch.no_grad():
        x0 = torch.tensor(pts[4])
        initial = (model(x0, torch.zeros_like(x0)) - model.p.f(x0)).numpy()
    arrays = [np.concatenate(a) for a in collected] + [initial]
    names = ("pde", "left_neumann", "right_dynamic", "initial")
    result = {name: {"rms": float(np.sqrt(np.mean(a**2))), "max_abs": float(np.max(np.abs(a))), "n": len(a)}
              for name, a in zip(names, arrays)}
    if not all(np.isfinite(v) for row in result.values() for v in row.values()):
        raise ValueError("non-finite held-out diagnostic")
    return result

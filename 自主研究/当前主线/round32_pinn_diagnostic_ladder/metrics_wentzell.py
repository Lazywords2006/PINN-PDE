"""Independent evaluator: errors against the Bessel reference and ladder-defined budget defects.

`fn(s, t)` returns (F, F_s) as numpy arrays for a numpy array s and a scalar t.
All quantities drop the common angular factor.  The budget defects are self-consistency
measures of the candidate solution, not the frozen normalization of the old contract.
"""
from __future__ import annotations

from typing import Callable

import numpy as np

from ref_wentzell import Mode, gauss_legendre_unit

OUT_TIMES = np.array([0.05, 0.1, 0.25, 0.5, 1.0])
FIELD_FLOOR = 1e-12

FieldFn = Callable[[np.ndarray, float], tuple[np.ndarray, np.ndarray]]


def _rel(num: float, den: float) -> float:
    return abs(num) / max(abs(den), FIELD_FLOOR)


def evaluate(
    fn: FieldFn,
    ref: Mode,
    times: np.ndarray = OUT_TIMES,
    nr: int = 128,
    nt: int = 64,
    t_start: float = 0.0,
) -> dict[str, list[float]]:
    m, c, kappa = ref.m, ref.c, ref.kappa
    q = ref.d * m * m + kappa
    r, w = gauss_legendre_unit(nr)
    s = r**2
    xi, wxi = gauss_legendre_unit(nt)
    one = np.array([1.0])

    def state(t: float) -> tuple[np.ndarray, np.ndarray, float]:
        big_f, big_fs = fn(s, t)
        ft = r**m * big_f
        ftr = m * r ** (m - 1) * big_f + 2.0 * r ** (m + 1) * big_fs
        tr = float(fn(one, t)[0][0])
        return ft, ftr, tr

    def energy(t: float) -> float:
        ft, _, tr = state(t)
        return 0.5 * (np.sum(w * r * ft**2) + c * tr**2)

    def dissipation(t: float) -> float:
        ft, ftr, tr = state(t)
        return float(np.sum(w * r * (ftr**2 + m * m * ft**2 / r**2)) + q * tr**2)

    def mass(t: float) -> float:
        ft, _, tr = state(t)
        return float(np.sum(w * r * ft) + c * tr)

    e0 = energy(t_start)
    m0 = mass(t_start) if m == 0 else 0.0
    out: dict[str, list[float]] = {k: [] for k in ("vol", "trace", "flux", "energy_defect", "mass_defect")}
    for t_end in times:
        ft, _, tr = state(t_end)
        ft_ref = ref.f(r, t_end)
        out["vol"].append(float(np.sqrt(np.sum(w * r * (ft - ft_ref) ** 2) / np.sum(w * r * ft_ref**2))))
        out["trace"].append(_rel(tr - ref.trace(t_end), ref.trace(t_end)))
        big_f1, big_fs1 = fn(one, t_end)
        out["flux"].append(_rel(m * big_f1[0] + 2.0 * big_fs1[0] - ref.flux(t_end), ref.flux(t_end)))
        span = t_end - t_start
        tau = t_start + span * xi**2
        weight = wxi * 2.0 * span * xi
        diss = sum(wk * dissipation(tk) for tk, wk in zip(tau, weight))
        out["energy_defect"].append(_rel(energy(t_end) - e0 + diss, e0))
        if m == 0:
            flow = sum(wk * state(tk)[2] for tk, wk in zip(tau, weight))
            out["mass_defect"].append(_rel(mass(t_end) - m0 + kappa * flow, m0))
        else:
            out["mass_defect"].append(0.0)
    return out

"""R33 screening problems and their reference solutions.

All problems: u_t = D u_xx + R(u) on (0,1); u_x = 0 at x = 0; dynamic boundary c u_t + D u_x + G(u) = 0 at x = 1;
u(x, 0) = f(x).  The reference is Chebyshev collocation in x (method of lines) integrated with scipy Radau.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.integrate import solve_ivp

OUT_TIMES = (0.05, 0.1, 0.25, 0.5, 1.0)


def _cos(x):
    """cos for floats, numpy arrays and torch tensors."""
    if isinstance(x, (float, int, np.ndarray)):
        return np.cos(x)
    import torch

    return torch.cos(x)


@dataclass(frozen=True)
class Problem1D:
    name: str
    D: float
    c: float
    R: Callable  # works on numpy arrays and torch tensors
    G: Callable
    f: Callable
    f_x: Callable
    f_xx: Callable

    def mismatch(self) -> float:
        """delta = u_t demanded by the dynamic boundary minus u_t demanded by the bulk, at x = 1, t = 0."""
        f1, fx1, fxx1 = self.f(1.0), self.f_x(1.0), self.f_xx(1.0)
        bulk = self.D * fxx1 + self.R(f1)
        boundary = -(self.D * fx1 + self.G(f1)) / self.c
        return float(boundary - bulk)


PROBLEMS = {
    "E1_heat": Problem1D(
        "E1_heat", D=1.0, c=0.3,
        R=lambda u: 0.0 * u, G=lambda u: 0.3 * u,
        f=lambda x: x**2 - 0.5, f_x=lambda x: 2.0 * x, f_xx=lambda x: 2.0 + 0.0 * x,
    ),
    "E2_allen_cahn": Problem1D(
        "E2_allen_cahn", D=0.01, c=0.3,
        R=lambda u: u - u**3, G=lambda u: 1.0 * u,
        f=lambda x: 0.5 * _cos(np.pi * x),
        f_x=lambda x: -0.5 * np.pi * np.sin(np.pi * x),
        f_xx=lambda x: -0.5 * np.pi**2 * np.cos(np.pi * x),
    ),
    "E3_fisher": Problem1D(
        "E3_fisher", D=0.1, c=0.3,
        R=lambda u: u * (1.0 - u), G=lambda u: 1.0 * (u - 1.0),
        f=lambda x: 0.1 * (1.0 - x**2), f_x=lambda x: -0.2 * x, f_xx=lambda x: -0.2 + 0.0 * x,
    ),
}



def _e1(c: float) -> Problem1D:
    return Problem1D(f"E1_c{c:g}", D=1.0, c=c, R=lambda u: 0.0 * u, G=lambda u: 0.3 * u,
                     f=lambda x: x**2 - 0.5, f_x=lambda x: 2.0 * x, f_xx=lambda x: 2.0 + 0.0 * x)


def _e3(kappa: float) -> Problem1D:
    return Problem1D(f"E3_k{kappa:g}", D=0.1, c=0.3, R=lambda u: u * (1.0 - u), G=lambda u: kappa * (u - 1.0),
                     f=lambda x: 0.1 * (1.0 - x**2), f_x=lambda x: -0.2 * x, f_xx=lambda x: -0.2 + 0.0 * x)


# parameter axes (amendment 2): E1 with other boundary capacities c, E3 with other reservoir strengths kappa
AXES = {p.name: p for p in [_e1(c) for c in (0.03, 0.1, 1.0, 3.0)] + [_e3(k) for k in (0.1, 3.0)]}


def get_problem(name: str) -> Problem1D:
    return PROBLEMS[name] if name in PROBLEMS else AXES[name]


def cheb(n: int) -> tuple[np.ndarray, np.ndarray]:
    """Chebyshev points on [0,1] ordered x_0 = 0 ... x_n = 1 and the first-derivative matrix."""
    j = np.arange(n + 1)
    z = -np.cos(np.pi * j / n)  # -1 .. 1
    cw = np.ones(n + 1)
    cw[0] = cw[-1] = 2.0
    cw = cw * (-1.0) ** j
    dz = z[:, None] - z[None, :]
    dmat = (cw[:, None] / cw[None, :]) / (dz + np.eye(n + 1))
    dmat -= np.diag(dmat.sum(axis=1))
    return (z + 1.0) / 2.0, 2.0 * dmat


class Reference:
    def __init__(self, p: Problem1D, n: int = 48, rtol: float = 1e-12, atol: float = 1e-13):
        self.p, self.n = p, n
        x, d1 = cheb(n)
        d2 = d1 @ d1
        self.x = x
        # Neumann at x = 0: row 0 of d1 u = 0 gives u_0 as a linear map of u_1..u_n
        self.u0_map = -d1[0, 1:] / d1[0, 0]

        def full(v):
            return np.concatenate([[self.u0_map @ v], v])

        def rhs(_t, v):
            u = full(v)
            du = np.empty_like(v)
            du[:-1] = p.D * (d2[1:-1] @ u) + p.R(u[1:-1])
            du[-1] = -(p.D * (d1[-1] @ u) + p.G(u[-1])) / p.c
            return du

        v0 = p.f(x[1:])
        sol = solve_ivp(rhs, (0.0, max(OUT_TIMES)), v0, method="Radau", rtol=rtol, atol=atol, dense_output=True)
        if not sol.success:
            raise RuntimeError(sol.message)
        self._sol, self._full = sol, full

    def values(self, t: float) -> np.ndarray:
        return self._full(self._sol.sol(t))

    def __call__(self, xq: np.ndarray, t: float) -> np.ndarray:
        coef = np.polynomial.chebyshev.chebfit(2.0 * self.x - 1.0, self.values(t), self.n)
        return np.polynomial.chebyshev.chebval(2.0 * np.asarray(xq) - 1.0, coef)


def self_check(name: str, n_lo: int = 48, n_hi: int = 96) -> float:
    p = get_problem(name)
    lo, hi = Reference(p, n_lo), Reference(p, n_hi)
    xq = np.linspace(0.0, 1.0, 401)
    return max(float(np.max(np.abs(lo(xq, t) - hi(xq, t)))) for t in OUT_TIMES)


if __name__ == "__main__":
    for name, p in {**PROBLEMS, **AXES}.items():
        print(f"{name}: delta = {p.mismatch():+.4f}, c' = {p.c / np.sqrt(p.D):.3f}, ref self-check = {self_check(name):.2e}")

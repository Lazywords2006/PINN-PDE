"""Reference solutions for one angular mode of the unit-disk Wentzell problem.

Problem (bulk diffusion 1, zero forcing, outward normal):
    u_t = Lap u                      in the disk
    c u_t - d Lap_G u + du/dnu + kappa u = 0   on the circle
Single mode u = r^m F(r^2, t) cos(m theta) = f(r, t) cos(m theta).  With s = r^2:
    F_t = 4 s F_ss + 4 (m + 1) F_s
    c F_t + (d m^2 + kappa + m) F + 2 F_s = 0   at s = 1
Two independent solvers:
    Mode      Bessel eigen-expansion in the weighted space <f,g> = int f g r dr + c f(1) g(1)
    cheb_mol  Chebyshev collocation in s with the boundary node following the dynamic BC
"""
from __future__ import annotations

import numpy as np
from numpy.polynomial.legendre import leggauss
from numpy.polynomial.polynomial import polyval
from scipy.linalg import expm
from scipy.optimize import brentq
from scipy.special import gamma, gammaln, jv, jvp

RESPONSES: dict[str, tuple[int, np.ndarray]] = {
    "m0_const": (0, np.array([1.0])),
    "m0_lin": (0, np.array([-0.5, 1.0])),
    "m1_const": (1, np.array([1.0])),
    "m1_lin": (1, np.array([-0.6, 1.0])),
    "m2_const": (2, np.array([1.0])),
}


def gauss_legendre_unit(n: int) -> tuple[np.ndarray, np.ndarray]:
    """Gauss-Legendre nodes and weights on [0, 1]."""
    x, w = leggauss(n)
    return 0.5 * (x + 1.0), 0.5 * w


class Mode:
    """Eigen-expansion reference for f(r, t) = sum_k a_k exp(-lam_k t) J_m(mu_k r)."""

    def __init__(self, m: int, c: float, d: float, kappa: float, poly: np.ndarray, mu_max: float = 80.0):
        self.m = int(m)
        self.c = float(c)
        self.d = float(d)
        self.kappa = float(kappa)
        self.poly = np.asarray(poly, dtype=float)
        self.q = self.d * self.m**2 + self.kappa
        self.has_zero_mode = self.m == 0 and self.kappa == 0.0
        roots = self._roots(mu_max)
        self.mu = np.concatenate([[0.0], roots]) if self.has_zero_mode else roots
        self.lam = self.mu**2
        self.norm = self._norms()
        self.a = self._coefficients(max(300, int(4 * mu_max)))

    # ---- spectrum -------------------------------------------------------
    def _g(self, mu: np.ndarray) -> np.ndarray:
        return (self.q - self.c * mu**2) * jv(self.m, mu) + mu * jvp(self.m, mu)

    def _roots(self, mu_max: float) -> np.ndarray:
        grid = np.arange(1e-6, mu_max, 0.01)
        g = self._g(grid)
        idx = np.nonzero(np.sign(g[:-1]) * np.sign(g[1:]) < 0)[0]
        return np.array([brentq(self._g, grid[i], grid[i + 1], xtol=1e-14, rtol=1e-15) for i in idx])

    def _norms(self) -> np.ndarray:
        mu = self.mu
        out = np.empty_like(mu)
        for k, x in enumerate(mu):
            if x == 0.0:
                out[k] = 0.5 + self.c
            else:
                j = jv(self.m, x)
                bulk = 0.5 * (jvp(self.m, x) ** 2 + (1.0 - self.m**2 / x**2) * j**2)
                out[k] = bulk + self.c * j**2
        return out

    def _phi(self, r: np.ndarray) -> np.ndarray:
        """Eigenfunctions J_m(mu_k r), shape (K, len(r)); the zero mode is the constant 1."""
        out = jv(self.m, np.outer(self.mu, r))
        if self.has_zero_mode:
            out[0] = 1.0
        return out

    def _coefficients(self, nq: int) -> np.ndarray:
        r, w = gauss_legendre_unit(nq)
        f0 = r**self.m * polyval(r**2, self.poly)
        f0_1 = polyval(1.0, self.poly)
        phi = self._phi(r)
        num = phi @ (w * r * f0) + self.c * f0_1 * self._trace_modes()
        return num / self.norm

    def _trace_modes(self) -> np.ndarray:
        tr = jv(self.m, self.mu)
        if self.has_zero_mode:
            tr[0] = 1.0
        return tr

    # ---- fields ---------------------------------------------------------
    def _decay(self, t: float) -> np.ndarray:
        return self.a * np.exp(-self.lam * t)

    def f(self, r: np.ndarray, t: float) -> np.ndarray:
        """Radial profile f(r, t) = r^m F(r^2, t)."""
        return self._decay(t) @ self._phi(np.asarray(r, dtype=float))

    def f_r(self, r: np.ndarray, t: float) -> np.ndarray:
        r = np.asarray(r, dtype=float)
        dphi = self.mu[:, None] * jvp(self.m, np.outer(self.mu, r))
        if self.has_zero_mode:
            dphi[0] = 0.0
        return self._decay(t) @ dphi

    def F(self, s: np.ndarray, t: float) -> np.ndarray:
        """F(s, t) = f / r^m with the exact limit at s = 0."""
        s = np.asarray(s, dtype=float)
        r = np.sqrt(s)
        out = np.empty_like(s)
        pos = r > 0
        if np.any(pos):
            out[pos] = self.f(r[pos], t) / r[pos] ** self.m
        if np.any(~pos):
            lim = (self.mu / 2.0) ** self.m / gamma(self.m + 1)
            if self.has_zero_mode:
                lim[0] = 1.0
            out[~pos] = self._decay(t) @ lim
        return out

    def F_s(self, s: np.ndarray, t: float) -> np.ndarray:
        """dF/ds for s > 0: (f_r - m f / r) / (2 r^(m+1))."""
        r = np.sqrt(np.asarray(s, dtype=float))
        return (self.f_r(r, t) - self.m * self.f(r, t) / r) / (2.0 * r ** (self.m + 1))

    def trace(self, t: float) -> float:
        return float(self._decay(t) @ self._trace_modes())

    def flux(self, t: float) -> float:
        """Normal derivative at r = 1: m F + 2 F_s at s = 1."""
        dphi = self.mu * jvp(self.m, self.mu)
        if self.has_zero_mode:
            dphi[0] = 0.0
        return float(self._decay(t) @ dphi)

    # ---- budgets (angular factor dropped consistently) -------------------
    def energy(self, t: float) -> float:
        return float(0.5 * np.sum(self.a**2 * self.norm * np.exp(-2.0 * self.lam * t)))

    def dE_dt(self, t: float) -> float:
        return float(-np.sum(self.lam * self.a**2 * self.norm * np.exp(-2.0 * self.lam * t)))

    def mass(self, t: float) -> float:
        """int f r dr + c f(1), meaningful for m = 0 only."""
        if self.m != 0:
            raise ValueError("mass is defined for m = 0")
        mu = self.mu
        bulk = np.where(mu > 0, jv(1, mu) / np.where(mu > 0, mu, 1.0), 0.5)
        tr = self._trace_modes()
        return float(self._decay(t) @ (bulk + self.c * tr))


def eigen_poly(m: int, mu: float, nterms: int = 40) -> np.ndarray:
    """Taylor coefficients in s of J_m(mu sqrt(s)) / s^(m/2), normalized to value 1 at s = 0."""
    k = np.arange(nterms)
    log_mag = k * np.log(mu * mu / 4.0) + gammaln(m + 1) - gammaln(k + 1) - gammaln(k + m + 1)
    return (-1.0) ** k * np.exp(log_mag)


def compatible_poly(m: int, c: float, d: float, kappa: float, modes: tuple[int, ...]) -> np.ndarray:
    """Equal-weight sum of the listed eigenfunctions (1-based) as polynomial initial data."""
    roots = Mode(m, c, d, kappa, np.array([1.0])).mu
    return sum(eigen_poly(m, roots[k - 1]) for k in modes)


# ---- Chebyshev collocation ----------------------------------------------
def _cheb_matrix(n: int) -> tuple[np.ndarray, np.ndarray]:
    x = np.cos(np.pi * np.arange(n + 1) / n)
    cw = np.ones(n + 1)
    cw[0] = cw[-1] = 2.0
    cw *= (-1.0) ** np.arange(n + 1)
    dx = x[:, None] - x[None, :]
    mat = (cw[:, None] / cw[None, :]) / (dx + np.eye(n + 1))
    mat -= np.diag(mat.sum(axis=1))
    return x, mat


def cheb_operator(m: int, c: float, d: float, kappa: float, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Nodes s_j (ascending, s_0 = 0, s_n = 1) and the matrix A with F_t = A F."""
    x, dx = _cheb_matrix(n)
    s = 0.5 * (1.0 - x)
    ds = -2.0 * dx
    dss = ds @ ds
    b = d * m * m + kappa + m
    a = 4.0 * s[:, None] * dss + 4.0 * (m + 1) * ds
    a[-1, :] = -(2.0 * ds[-1, :])
    a[-1, -1] -= b
    a[-1, :] /= c
    return s, a


def cheb_mol(m: int, c: float, d: float, kappa: float, poly: np.ndarray, n: int, times: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """F at the Chebyshev nodes for each requested time (matrix exponential)."""
    s, a = cheb_operator(m, c, d, kappa, n)
    f0 = polyval(s, np.asarray(poly, dtype=float))
    return s, np.array([expm(a * t) @ f0 for t in times])

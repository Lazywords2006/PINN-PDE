"""Tests for the single-angular-mode Wentzell reference solver (written before the code)."""
import numpy as np
import pytest

from ref_wentzell import RESPONSES, Mode, cheb_operator, cheb_mol, gauss_legendre_unit

OUT_TIMES = np.array([0.05, 0.1, 0.25, 0.5, 1.0])
CENTER = (0.3, 0.1, 0.3)
CORNERS = [(c, d, k) for c in (0.01, 10.0) for d in (0.01, 1.0) for k in (0.1, 1.0)]
POINTS = [CENTER] + CORNERS
ALL_RESPONSES = list(RESPONSES)


def make(name, point, **kw):
    m, poly = RESPONSES[name]
    c, d, k = point
    return Mode(m, c, d, k, poly, **kw)


@pytest.mark.parametrize("point", POINTS)
@pytest.mark.parametrize("m", [0, 1, 2])
def test_eigenvalues_match_collocation(point, m):
    """Bessel roots must coincide with the lowest eigenvalues of the Chebyshev operator,
    which also shows that no root was skipped."""
    c, d, k = point
    mode = Mode(m, c, d, k, np.array([1.0]))
    _, A = cheb_operator(m, c, d, k, 80)
    ev = np.sort(-np.linalg.eigvals(A).real)
    n = 8
    got = np.sort(mode.lam)[:n]
    ref = ev[: len(got)]
    assert np.allclose(got, ref, rtol=1e-7, atol=1e-9), (got, ref)


@pytest.mark.parametrize("point", POINTS)
@pytest.mark.parametrize("name", ALL_RESPONSES)
def test_matches_collocation_solution(point, name):
    """Two independent methods agree at the output times."""
    m, poly = RESPONSES[name]
    c, d, k = point
    if m == 0 and k == 0:
        pytest.skip("trivial")
    mode = Mode(m, c, d, k, poly)
    s, F = cheb_mol(m, c, d, k, poly, 80, OUT_TIMES)
    for j, t in enumerate(OUT_TIMES):
        ref = mode.F(s, t)
        err = np.max(np.abs(ref - F[j]))
        assert err < 1e-7 * max(1.0, np.max(np.abs(ref))), (t, err)


@pytest.mark.parametrize("point", [CENTER, (0.01, 1.0, 1.0), (10.0, 0.01, 0.1)])
@pytest.mark.parametrize("name", ["m0_lin", "m1_lin", "m2_const"])
def test_energy_identity(point, name):
    """dE/dt = -(bulk dissipation + (d m^2 + kappa) trace^2): fixes the sign convention of the BC."""
    m, poly = RESPONSES[name]
    c, d, k = point
    mode = Mode(m, c, d, k, poly)
    r, w = gauss_legendre_unit(400)
    for t in (0.05, 0.3, 1.0):
        fr = mode.f_r(r, t)
        f = mode.f(r, t)
        bulk = np.sum(w * r * (fr**2 + (m * m) * f**2 / r**2))
        tr = mode.trace(t)
        diss = bulk + (d * m * m + k) * tr**2
        assert np.isclose(mode.dE_dt(t), -diss, rtol=1e-7), (t, mode.dE_dt(t), -diss)
        # energy from the quadrature equals the energy from the series
        e_quad = 0.5 * (np.sum(w * r * f**2) + c * tr**2)
        assert np.isclose(mode.energy(t), e_quad, rtol=1e-9)


@pytest.mark.parametrize("point", [CENTER, (0.01, 1.0, 1.0), (10.0, 0.01, 0.1)])
def test_mass_budget(point):
    c, d, k = point
    m, poly = RESPONSES["m0_lin"]
    mode = Mode(m, c, d, k, poly)
    r, w = gauss_legendre_unit(400)
    h = 1e-5
    t = 0.2
    dM = (mode.mass(t + h) - mode.mass(t - h)) / (2 * h)
    assert np.isclose(dM, -k * mode.trace(t), rtol=1e-5, atol=1e-8)
    # bulk part of the mass from quadrature
    m_quad = np.sum(w * r * mode.f(r, t)) + c * mode.trace(t)
    assert np.isclose(mode.mass(t), m_quad, rtol=1e-9)


def test_kappa_zero_conserves_mass_and_constant_is_steady():
    m, poly = RESPONSES["m0_lin"]
    mode = Mode(m, 0.3, 0.1, 0.0, poly)
    m0 = mode.mass(0.0)
    for t in OUT_TIMES:
        assert np.isclose(mode.mass(t), m0, rtol=1e-6, atol=1e-9)
    const = Mode(0, 0.3, 0.1, 0.0, np.array([1.0]))
    s = np.linspace(0, 1, 11)
    for t in OUT_TIMES:
        assert np.allclose(const.F(s, t), 1.0, atol=1e-12)


@pytest.mark.parametrize("point", [CENTER, (0.01, 1.0, 1.0), (10.0, 0.01, 0.1)])
@pytest.mark.parametrize("name", ["m0_lin", "m1_lin", "m2_const"])
def test_pde_and_bc_residual_of_reference(point, name):
    """The reference satisfies the reduced PDE and the dynamic BC (finite differences)."""
    m, poly = RESPONSES[name]
    c, d, k = point
    mode = Mode(m, c, d, k, poly)
    b = d * m * m + k + m
    t = 0.2
    h = 1e-4
    s = np.array([0.1, 0.3, 0.5, 0.7, 0.9])
    F = mode.F(s, t)
    Fs = (mode.F(s + h, t) - mode.F(s - h, t)) / (2 * h)
    Fss = (mode.F(s + h, t) - 2 * F + mode.F(s - h, t)) / h**2
    Ft = (mode.F(s, t + h) - mode.F(s, t - h)) / (2 * h)
    scale = np.abs(Ft) + np.abs(4 * s * Fss) + np.abs(4 * (m + 1) * Fs) + 1e-12
    res = Ft - 4 * s * Fss - 4 * (m + 1) * Fs
    assert np.max(np.abs(res) / scale) < 1e-5
    s1 = np.array([1.0])
    F1 = mode.F(s1, t)
    Fs1 = (mode.F(s1, t + 0) - mode.F(s1 - h, t)) / h  # one-sided, refined below
    Fs1 = (3 * mode.F(s1, t) - 4 * mode.F(s1 - h, t) + mode.F(s1 - 2 * h, t)) / (2 * h)
    Ft1 = (mode.F(s1, t + h) - mode.F(s1, t - h)) / (2 * h)
    bc = c * Ft1 + b * F1 + 2 * Fs1
    sc = np.abs(c * Ft1) + np.abs(b * F1) + np.abs(2 * Fs1)
    assert np.max(np.abs(bc) / sc) < 1e-5
    # analytic normal flux equals m F + 2 F_s at s=1
    assert np.isclose(mode.flux(t), m * F1[0] + 2 * Fs1[0], rtol=1e-5)


@pytest.mark.parametrize("name", ALL_RESPONSES)
def test_initial_data_recovered_in_weighted_norm(name):
    """Series at t -> 0+ reproduces the data in the weighted L2 norm (completeness of the roots)."""
    m, poly = RESPONSES[name]
    mode = Mode(m, 0.3, 0.1, 0.3, poly, mu_max=400.0)
    r, w = gauss_legendre_unit(2000)
    f0 = np.polyval(poly[::-1], r**2) * r**m
    ft = mode.f(r, 1e-7)
    num = np.sum(w * r * (ft - f0) ** 2) + mode.c * (mode.trace(1e-7) - np.polyval(poly[::-1], 1.0)) ** 2
    den = np.sum(w * r * f0**2) + mode.c * np.polyval(poly[::-1], 1.0) ** 2
    assert np.sqrt(num / den) < 2e-2


def test_cheb_converges():
    m, poly = RESPONSES["m1_lin"]
    _, F1 = cheb_mol(m, 0.3, 0.1, 0.3, poly, 48, OUT_TIMES)
    s2, F2 = cheb_mol(m, 0.3, 0.1, 0.3, poly, 96, OUT_TIMES)
    mode = Mode(m, 0.3, 0.1, 0.3, poly)
    err2 = max(np.max(np.abs(mode.F(s2, t) - F2[j])) for j, t in enumerate(OUT_TIMES))
    assert err2 < 1e-8


@pytest.mark.parametrize("name", ["m0_lin", "m1_lin", "m2_const"])
def test_F_s_matches_finite_difference(name):
    m, poly = RESPONSES[name]
    mode = Mode(m, 0.3, 0.1, 0.3, poly)
    s = np.array([0.05, 0.3, 0.6, 0.95])
    h = 1e-5
    fd = (mode.F(s + h, 0.2) - mode.F(s - h, 0.2)) / (2 * h)
    assert np.allclose(mode.F_s(s, 0.2), fd, rtol=1e-6, atol=1e-8)


@pytest.mark.parametrize("m", [0, 1, 2])
def test_compatible_initial_data_is_a_pure_decaying_mode(m):
    from ref_wentzell import compatible_poly

    poly = compatible_poly(m, 0.3, 0.1, 0.3, (1,))
    mode = Mode(m, 0.3, 0.1, 0.3, poly)
    lam1 = mode.lam[0]
    s = np.linspace(0.0, 1.0, 21)
    f0 = np.polynomial.polynomial.polyval(s, poly)
    for t in (0.05, 0.5, 1.0):
        assert np.allclose(mode.F(s, t), np.exp(-lam1 * t) * f0, rtol=1e-8, atol=1e-10)
    # the two-mode datum decays with two rates
    two = Mode(m, 0.3, 0.1, 0.3, compatible_poly(m, 0.3, 0.1, 0.3, (1, 3)))
    big = np.argsort(-np.abs(two.a))[:2]
    assert sorted(big.tolist()) == [0, 2]
    assert np.max(np.abs(np.delete(two.a, [0, 2]))) < 1e-8

"""Tests for the two PINN variants: corner-layer lifting and exp(-lambda t) decay scaling (written before the code)."""
import math

import numpy as np
import pytest
import torch

from pinn_improved import LiftedNet, Variant, corner_mismatch, layer_profile, train_variant
from pinn_vanilla import Config, Problem, residual_bc, residual_pde
from ref_wentzell import RESPONSES, compatible_poly

torch.set_default_dtype(torch.float64)


def derivs(c, x, t):
    x = x.clone().requires_grad_(True)
    t = t.clone().requires_grad_(True)
    w = layer_profile(x, t, c)
    w_x = torch.autograd.grad(w.sum(), x, create_graph=True)[0]
    w_t = torch.autograd.grad(w.sum(), t, create_graph=True)[0]
    w_xx = torch.autograd.grad(w_x.sum(), x)[0]
    return w.detach(), w_x.detach(), w_t.detach(), w_xx


@pytest.mark.parametrize("c", [0.01, 0.3, 10.0])
def test_layer_profile_solves_the_half_line_model(c):
    """w_t = w_xx in x > 0, c w_t - w_x = c at x = 0, w(x, 0+) = 0."""
    x = torch.tensor([0.0, 0.01, 0.05, 0.2, 0.5])
    for tv in (1e-3, 0.05, 0.5):
        t = torch.full_like(x, tv)
        w, w_x, w_t, w_xx = derivs(c, x, t)
        assert torch.allclose(w_t[1:], w_xx[1:], rtol=1e-7, atol=1e-9)
        assert abs(float(c * w_t[0] - w_x[0]) - c) < 1e-8 * max(1.0, c)
    tiny = layer_profile(x, torch.full_like(x, 1e-12), c)
    assert torch.all(tiny.abs() < 1e-10)


def test_layer_trace_follows_the_dynamic_rate_at_short_times():
    c = 0.3
    t = torch.tensor([1e-6, 1e-5])
    w0 = layer_profile(torch.zeros(2), t, c)
    assert torch.allclose(w0, t, rtol=2e-2)


def test_layer_profile_is_finite_at_t_zero_and_for_small_c():
    x = torch.linspace(0, 0.5, 11)
    for c in (0.01, 0.3, 10.0):
        w = layer_profile(x, torch.zeros_like(x), c)
        assert torch.all(torch.isfinite(w)) and torch.all(w.abs() < 1e-10)
        w1 = layer_profile(x, torch.ones_like(x), c)
        assert torch.all(torch.isfinite(w1))


def problem(name="m0_lin", c=0.3, d=0.1, kappa=0.3):
    m, poly = RESPONSES[name]
    return Problem(name, m, c, d, kappa, tuple(float(x) for x in poly))


def test_corner_mismatch_values():
    # m0_lin at P0: bulk F_t = 4, boundary F_t = -(0.3*0.5 + 2)/0.3
    assert math.isclose(corner_mismatch(problem("m0_lin")), -(0.15 + 2.0) / 0.3 - 4.0, rel_tol=1e-12)
    poly = compatible_poly(1, 0.3, 0.1, 0.3, (1,))
    p = Problem("m1_eig1", 1, 0.3, 0.1, 0.3, tuple(poly))
    assert abs(corner_mismatch(p)) < 1e-8


class Regular(torch.nn.Module):
    """N = f(s) + t * (bulk operator applied to f): the smooth short-time expansion."""

    def __init__(self, p):
        super().__init__()
        self.p = p
        f = np.polynomial.polynomial.Polynomial(p.poly)
        bulk = 4 * np.polynomial.polynomial.Polynomial([0, 1]) * f.deriv(2) + 4 * (p.m + 1) * f.deriv(1)
        self.f = tuple(f.coef)
        self.g = tuple(bulk.coef)

    def forward(self, s, t):
        ev = lambda co: sum(a * s**i for i, a in enumerate(co))
        return ev(self.f) + t * ev(self.g)


@pytest.mark.parametrize("name", ["m0_lin", "m1_lin", "m2_const"])
def test_lifting_removes_the_corner_conflict(name):
    """With the regular expansion as N, the BC residual at t -> 0 is -c*delta without lifting and ~0 with it."""
    p = problem(name)
    delta = corner_mismatch(p)
    t = torch.tensor([1e-8])
    plain = LiftedNet(Regular(p), p, Variant(layer=False, decay=False))
    lifted = LiftedNet(Regular(p), p, Variant(layer=True, decay=False))
    r_plain = float(residual_bc(plain, p, t))
    r_lift = float(residual_bc(lifted, p, t))
    assert math.isclose(r_plain, -p.c * delta, rel_tol=1e-6)
    assert abs(r_lift) < 1e-3 * abs(p.c * delta)
    # lifting leaves the initial condition unchanged
    s = torch.linspace(0, 1, 11)
    assert torch.allclose(lifted(s, torch.zeros_like(s)), plain(s, torch.zeros_like(s)), atol=1e-12)


def test_decay_variant_scales_output_and_weights():
    p = problem("m2_const")
    base = Regular(p)
    v = Variant(layer=False, decay=True)
    net = LiftedNet(base, p, v, lam=5.5)
    s = torch.rand(7)
    t = torch.rand(7)
    assert torch.allclose(net(s, t), torch.exp(-5.5 * t) * base(s, t))
    assert torch.allclose(net.time_weight(t), torch.exp(5.5 * t))
    plain = LiftedNet(base, p, Variant(layer=False, decay=False))
    assert torch.allclose(plain.time_weight(t), torch.ones_like(t))


def test_variant_training_runs_and_is_deterministic():
    p = problem("m0_lin")
    cfg = Config(width=16, depth=2, adam_steps=60, lbfgs_iters=0, nf=128, nb=32, n0=32, seed=0)
    for v in (Variant(True, False), Variant(False, True), Variant(True, True)):
        r1 = train_variant(p, cfg, v, lam=0.36)
        r2 = train_variant(p, cfg, v, lam=0.36)
        assert np.isfinite(r1.history["loss"][-1])
        assert r1.history["loss"][-1] == r2.history["loss"][-1]


def test_vanilla_path_unchanged_by_variant_machinery():
    """Variant(False, False) must reproduce plain vanilla training bit for bit."""
    from pinn_vanilla import train

    p = problem("m1_const")
    cfg = Config(width=16, depth=2, adam_steps=50, lbfgs_iters=0, nf=128, nb=32, n0=32, seed=0)
    a = train(p, cfg)
    b = train_variant(p, cfg, Variant(False, False), lam=0.0)
    assert a.history["loss"] == b.history["loss"]


def test_hard_ic_variant_matches_initial_data_exactly():
    p = problem("m0_lin")
    torch.manual_seed(0)
    from pinn_vanilla import MLP, residual_ic

    net = LiftedNet(MLP(8, 2), p, Variant(layer=False, decay=False, hard_ic=True))
    s = torch.rand(20)
    assert torch.allclose(residual_ic(net, p, s), torch.zeros(20), atol=1e-14)
    assert Variant(False, False, hard_ic=True).name == "hardic"


def test_early_time_sampling_power():
    from pinn_vanilla import Config, train

    p = problem("m1_const")
    base = dict(width=16, depth=2, adam_steps=30, lbfgs_iters=0, nf=128, nb=32, n0=32, seed=0)
    a = train(p, Config(**base))
    b = train(p, Config(**base, t_power=1.0))
    assert a.history["loss"] == b.history["loss"]
    c = train(p, Config(**base, t_power=2.0))
    assert c.history["loss"] != a.history["loss"]

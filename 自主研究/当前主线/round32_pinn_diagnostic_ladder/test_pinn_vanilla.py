"""Tests for the vanilla PINN and the independent evaluator (written before the code)."""
import numpy as np
import pytest
import torch

from metrics_wentzell import OUT_TIMES, evaluate
from pinn_vanilla import Config, Problem, residual_bc, residual_ic, residual_pde, train
from ref_wentzell import RESPONSES, Mode

torch.set_default_dtype(torch.float64)


class Poly(torch.nn.Module):
    """F = s + 4 (m + 1) t solves the reduced bulk equation exactly."""

    def __init__(self, m: int):
        super().__init__()
        self.m = m

    def forward(self, s, t):
        return s + 4.0 * (self.m + 1) * t


def problem(name="m1_lin", c=0.3, d=0.1, kappa=0.3):
    m, poly = RESPONSES[name]
    return Problem(name, m, c, d, kappa, tuple(poly))


@pytest.mark.parametrize("name", ["m0_lin", "m1_lin", "m2_const"])
def test_residual_operators_on_polynomial(name):
    p = problem(name)
    net = Poly(p.m)
    s = torch.rand(50)
    t = torch.rand(50)
    assert torch.allclose(residual_pde(net, p, s, t), torch.zeros(50), atol=1e-12)
    b = p.d * p.m**2 + p.kappa + p.m
    tb = torch.rand(20)
    expect = p.c * 4.0 * (p.m + 1) + b * (1.0 + 4.0 * (p.m + 1) * tb) + 2.0
    assert torch.allclose(residual_bc(net, p, tb), expect, atol=1e-12)


def test_ic_residual_uses_the_response_polynomial():
    p = problem("m1_lin")

    class Init(torch.nn.Module):
        def forward(self, s, t):
            return s - 0.6 + 0.0 * t

    s = torch.rand(30)
    assert torch.allclose(residual_ic(Init(), p, s), torch.zeros(30), atol=1e-14)


def tiny_config(**kw):
    base = dict(width=16, depth=2, adam_steps=150, lbfgs_iters=0, nf=128, nb=32, n0=32, seed=0)
    base.update(kw)
    return Config(**base)


def test_training_reduces_loss_and_is_deterministic():
    p = problem("m1_const")
    r1 = train(p, tiny_config())
    r2 = train(p, tiny_config())
    assert r1.history["loss"][-1] < r1.history["loss"][0]
    assert r1.history["loss"][-1] == r2.history["loss"][-1]


def test_lbfgs_phase_runs_and_does_not_increase_loss():
    p = problem("m0_lin")
    r = train(p, tiny_config(adam_steps=100, lbfgs_iters=40, nf_fixed=256, nb_fixed=64, n0_fixed=64))
    assert r.history["lbfgs_loss"][-1] <= r.history["lbfgs_loss"][0] + 1e-12


def reference_fn(mode):
    def fn(s, t):
        return mode.F(s, t), mode.F_s(s, t)

    return fn


@pytest.mark.parametrize("name", ["m0_lin", "m1_lin", "m2_const"])
def test_evaluator_gives_zero_error_for_reference(name):
    m, poly = RESPONSES[name]
    mode = Mode(m, 0.3, 0.1, 0.3, poly)
    out = evaluate(reference_fn(mode), mode, t_start=0.02)
    assert max(out["vol"]) < 1e-12
    assert max(out["trace"]) < 1e-12
    assert max(out["flux"]) < 1e-9
    # quadrature floor of the budget defects for the exact solution
    assert max(out["energy_defect"]) < 1e-6
    if m == 0:
        assert max(out["mass_defect"]) < 1e-6


def test_evaluator_detects_a_scaled_solution():
    m, poly = RESPONSES["m1_lin"]
    mode = Mode(m, 0.3, 0.1, 0.3, poly)
    base = reference_fn(mode)

    def scaled(s, t):
        f, fs = base(s, t)
        return 1.01 * f, 1.01 * fs

    out = evaluate(scaled, mode)
    assert np.allclose(out["vol"], 0.01, rtol=1e-6)
    assert np.allclose(out["trace"], 0.01, rtol=1e-6)
    assert np.allclose(out["flux"], 0.01, rtol=1e-6)


def test_budget_defect_detects_wrong_time_scale():
    m, poly = RESPONSES["m0_lin"]
    mode = Mode(m, 0.3, 0.1, 0.3, poly)
    base = reference_fn(mode)

    def stretched(s, t):
        return base(s, 1.2 * t)

    out = evaluate(stretched, mode, t_start=0.02)
    assert max(out["energy_defect"]) > 1e-3
    assert max(out["mass_defect"]) > 1e-3


def test_output_times_follow_the_contract():
    assert list(OUT_TIMES) == [0.05, 0.1, 0.25, 0.5, 1.0]

import numpy as np
import pytest
import torch
from scipy.optimize import brentq

from pinn1d import Config, Model, residuals
from problems import AXES, OUT_TIMES, PROBLEMS, Reference


def eigen_reference_e1(x, t, n_modes=400, c=0.3):
    """Independent E1 reference: u_t = u_xx, u_x(0) = 0, c u_t + u_x + kappa u = 0 at x = 1.
    Modes cos(mu x) with (kappa - c mu^2) cos mu - mu sin mu = 0, weighted inner product <f,g> = int f g + c f(1) g(1)."""
    kappa = 0.3
    g = lambda mu: (kappa - c * mu**2) * np.cos(mu) - mu * np.sin(mu)
    grid = np.linspace(1e-6, 1300.0, 400000)
    vals = g(grid)
    roots = [brentq(g, grid[i], grid[i + 1]) for i in np.nonzero(np.sign(vals[:-1]) != np.sign(vals[1:]))[0]][:n_modes]
    xg, wg = np.polynomial.legendre.leggauss(400)
    xg, wg = 0.5 * (xg + 1), 0.5 * wg
    f = lambda z: z**2 - 0.5
    out = np.zeros_like(x)
    for mu in roots:
        phi = lambda z: np.cos(mu * z)
        num = np.sum(wg * f(xg) * phi(xg)) + c * f(1.0) * phi(1.0)
        den = np.sum(wg * phi(xg) ** 2) + c * phi(1.0) ** 2
        out += num / den * np.exp(-(mu**2) * t) * phi(x)
    return out


@pytest.mark.parametrize("t", OUT_TIMES)
def test_e1_reference_matches_eigen_expansion(t):
    x = np.linspace(0, 1, 101)
    ref = Reference(PROBLEMS["E1_heat"], 48)
    assert np.max(np.abs(ref(x, t) - eigen_reference_e1(x, t))) < 1e-8


@pytest.mark.parametrize("eq", list(PROBLEMS))
def test_hard_ic_exact(eq):
    p = PROBLEMS[eq]
    for method in ("hardic", "hardic+layer"):
        m = Model(p, method, Config())
        x = torch.linspace(0, 1, 50)
        assert torch.max(torch.abs(m(x, torch.zeros_like(x)) - p.f(x))) < 1e-14


@pytest.mark.parametrize("eq", list(PROBLEMS))
def test_layer_shifts_boundary_residual_by_c_delta(eq):
    """With N == 0 the lifted model's boundary residual at t -> 0+ differs from the unlifted one by c * delta."""
    p = PROBLEMS[eq]
    t = torch.tensor([1e-10])
    vals = {}
    for method in ("hardic", "hardic+layer"):
        m = Model(p, method, Config())
        for prm in m.base.parameters():
            torch.nn.init.zeros_(prm)
        z = torch.zeros(1)
        vals[method] = residuals(m, (torch.rand(4), torch.rand(4), z, t, torch.rand(4)))[2]
    assert float(vals["hardic+layer"] - vals["hardic"]) == pytest.approx(p.c * p.mismatch(), rel=1e-3)


@pytest.mark.parametrize("eq", list(PROBLEMS))
def test_reference_self_consistency(eq):
    p = PROBLEMS[eq]
    x = np.linspace(0, 1, 201)
    lo, hi = Reference(p, 48), Reference(p, 96)
    assert max(np.max(np.abs(lo(x, t) - hi(x, t))) for t in OUT_TIMES) < 1e-8


@pytest.mark.parametrize("c", [0.03, 0.1, 1.0, 3.0])
def test_e1_axis_reference_matches_eigen_expansion(c):
    x = np.linspace(0, 1, 101)
    ref = Reference(AXES[f"E1_c{c:g}"], 48)
    for t in OUT_TIMES:
        assert np.max(np.abs(ref(x, t) - eigen_reference_e1(x, t, c=c))) < 1e-8


@pytest.mark.parametrize("name", list(AXES))
def test_axis_reference_self_consistency(name):
    p = AXES[name]
    x = np.linspace(0, 1, 201)
    lo, hi = Reference(p, 48), Reference(p, 96)
    assert max(np.max(np.abs(lo(x, t) - hi(x, t))) for t in OUT_TIMES) < 1e-8


def test_pirate_and_causal_train_smoke():
    from dataclasses import replace

    from pinn1d import train

    p = PROBLEMS["E3_fisher"]
    for cfg in (replace(Config(), arch="pirate", adam_steps=3, lbfgs_iters=0),
                replace(Config(), causal_eps=1.0, adam_steps=3, lbfgs_iters=0)):
        model, hist = train(p, "hardic+layer", cfg)
        x = torch.linspace(0, 1, 7)
        assert torch.isfinite(model(x, 0.5 + 0 * x)).all()
        assert torch.max(torch.abs(model(x, 0 * x) - p.f(x))) < 1e-14
        assert np.isfinite(hist["loss"][-1])


@pytest.mark.parametrize("method,interrupt_after", [("hardic+layer", 25), ("rba", 25), ("hardic", 60)])
def test_checkpoint_resume_matches_uninterrupted(tmp_path, monkeypatch, method, interrupt_after):
    """Interrupt training (in the Adam phase, or in L-BFGS for 60 calls) and resume from the checkpoint:
    the final network must equal the uninterrupted one."""
    from dataclasses import replace

    import pinn1d

    p = PROBLEMS["E3_fisher"]
    cfg = replace(Config(), adam_steps=40, nf=64, nb=16, n0=16, lbfgs_iters=100, lbfgs_chunk=10,
                  nf_fixed=64, nb_fixed=16, n0_fixed=16)
    ref_model, ref_hist = pinn1d.train(p, method, cfg)
    ckpt = str(tmp_path / "run.ckpt")
    real = pinn1d.residuals
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] > interrupt_after:
            raise KeyboardInterrupt
        return real(*a, **k)

    monkeypatch.setattr(pinn1d, "residuals", flaky)
    with pytest.raises(KeyboardInterrupt):
        pinn1d.train(p, method, cfg, ckpt=ckpt, ckpt_every=10)
    monkeypatch.setattr(pinn1d, "residuals", real)
    model, hist = pinn1d.train(p, method, cfg, ckpt=ckpt, ckpt_every=10)
    assert hist["resumed_at"]
    for a, b in zip(ref_model.state_dict().values(), model.state_dict().values()):
        assert torch.equal(a, b)
    assert hist["lbfgs_loss"] == ref_hist["lbfgs_loss"]

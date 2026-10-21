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


# ---- E4 (bulk-surface, flux-jump corner layer) ----

def test_e4_reference_self_consistency():
    from problems import BULK_SURFACE, ReferenceBS

    p = BULK_SURFACE["E4_bulk_surface"]
    x = np.linspace(0, 1, 201)
    lo, hi = ReferenceBS(p, 48), ReferenceBS(p, 96)
    assert max(np.max(np.abs(lo(x, t) - hi(x, t))) for t in OUT_TIMES) < 1e-8
    assert max(abs(lo.v(t) - hi.v(t)) for t in OUT_TIMES) < 1e-8


def test_e4_reference_second_integrator():
    from problems import BULK_SURFACE, ReferenceBS

    p = BULK_SURFACE["E4_bulk_surface"]
    x = np.linspace(0, 1, 201)
    a, b = ReferenceBS(p, 96), ReferenceBS(p, 96, rtol=1e-11, atol=1e-13, method="BDF")
    assert max(np.max(np.abs(a(x, t) - b(x, t))) for t in OUT_TIMES) < 1e-7


def test_e4_reference_satisfies_exchange_condition():
    from problems import BULK_SURFACE, ReferenceBS

    p = BULK_SURFACE["E4_bulk_surface"]
    ref = ReferenceBS(p, 96)
    h = 1e-5
    for t in OUT_TIMES:
        ux = (ref(np.array([1.0]), t) - ref(np.array([1.0 - h]), t)) / h
        assert abs(p.D * ux[0] - p.kappa * (ref.v(t) - ref(np.array([1.0]), t)[0])) < 5e-4


def test_e4_sqrt_t_coefficient_matches_flux_layer():
    """u(1,t) - f(1) ~ -2 Delta_y sqrt(t/(pi D)) as t -> 0 (reference vs analytic flux layer), within 5% at t = 1e-5."""
    from problems import BULK_SURFACE, ReferenceBS

    p = BULK_SURFACE["E4_bulk_surface"]
    ref = ReferenceBS(p, 160)
    t = 1e-5
    got = (ref.values(t)[-1] - p.f(1.0)) / np.sqrt(t)
    want = -2.0 * p.mismatch() / np.sqrt(np.pi * p.D)
    assert abs(got - want) / abs(want) < 0.05


def test_e4_flux_layer_solves_heat_equation_and_flux():
    from pinn1d import flux_layer

    p = PROBLEMS and __import__("problems").BULK_SURFACE["E4_bulk_surface"]
    d, dy = p.D, p.mismatch()
    y = torch.linspace(0.02, 0.6, 7).requires_grad_(True)
    t = torch.full_like(y, 0.07).requires_grad_(True)
    u = flux_layer(y, t, d, dy)
    ut = torch.autograd.grad(u.sum(), t, create_graph=True)[0]
    uy = torch.autograd.grad(u.sum(), y, create_graph=True)[0]
    uyy = torch.autograd.grad(uy.sum(), y)[0]
    assert torch.max(torch.abs(ut - d * uyy)) < 1e-9
    y0 = torch.zeros(3, requires_grad=True)
    t0 = torch.tensor([0.01, 0.07, 0.3])
    uy0 = torch.autograd.grad(flux_layer(y0, t0, d, dy).sum(), y0)[0]
    assert torch.max(torch.abs(d * uy0 - dy)) < 1e-9


def test_e4_hard_ic_exact_and_layer_vanishes_at_t0():
    from problems import BULK_SURFACE

    p = BULK_SURFACE["E4_bulk_surface"]
    x = torch.linspace(0, 1, 40)
    for method in ("hardic", "hardic+layer"):
        m = Model(p, method, Config())
        assert torch.max(torch.abs(m(x, torch.zeros_like(x)) - p.f(x))) < 1e-14
        assert abs(float(m.surface(torch.zeros(1))[0]) - p.V0) < 1e-14


def test_e4_layer_shifts_flux_residual_by_delta():
    """With the networks zeroed, the unlifted exchange-flux residual at t -> 0+ equals Delta_y and the lift removes it."""
    from pinn1d import residuals
    from problems import BULK_SURFACE

    p = BULK_SURFACE["E4_bulk_surface"]
    t = torch.tensor([1e-10])
    vals = {}
    for method in ("hardic", "hardic+layer"):
        m = Model(p, method, Config())
        for prm in list(m.base.parameters()) + list(m.surf.parameters()):
            torch.nn.init.zeros_(prm)
        vals[method] = residuals(m, (torch.rand(4), torch.rand(4), t, t, torch.rand(4)))[2]
    assert float(vals["hardic"]) == pytest.approx(p.mismatch(), rel=1e-3)
    assert abs(float(vals["hardic+layer"])) < 2e-3


@pytest.mark.parametrize("method", ["vanilla", "rba", "hardic+layer"])
def test_e4_train_smoke_and_resume(tmp_path, monkeypatch, method):
    from dataclasses import replace

    import pinn1d
    from problems import BULK_SURFACE

    p = BULK_SURFACE["E4_bulk_surface"]
    cfg = replace(Config(), adam_steps=20, nf=32, nb=8, n0=8, lbfgs_iters=20, lbfgs_chunk=10,
                  nf_fixed=32, nb_fixed=8, n0_fixed=8)
    ref_model, ref_hist = pinn1d.train(p, method, cfg)
    x = torch.linspace(0, 1, 5)
    assert torch.isfinite(ref_model(x, 0.5 + 0 * x)).all() and torch.isfinite(ref_model.surface(torch.tensor([0.5]))).all()
    ckpt = str(tmp_path / "e4.ckpt")
    real = pinn1d.residuals
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] > 12:
            raise KeyboardInterrupt
        return real(*a, **k)

    monkeypatch.setattr(pinn1d, "residuals", flaky)
    with pytest.raises(KeyboardInterrupt):
        pinn1d.train(p, method, cfg, ckpt=ckpt, ckpt_every=5)
    monkeypatch.setattr(pinn1d, "residuals", real)
    model, hist = pinn1d.train(p, method, cfg, ckpt=ckpt, ckpt_every=5)
    assert hist["resumed_at"]
    for a, b in zip(ref_model.state_dict().values(), model.state_dict().values()):
        assert torch.equal(a, b)


def test_e4_evaluate_reports_surface_error():
    from dataclasses import replace

    import pinn1d
    from problems import BULK_SURFACE, get_reference
    from screen import evaluate

    p = BULK_SURFACE["E4_bulk_surface"]
    cfg = replace(Config(), adam_steps=2, lbfgs_iters=0, nf=16, nb=4, n0=4)
    model, _ = pinn1d.train(p, "hardic+layer", cfg)
    out = evaluate(model, get_reference(p, 64))
    assert len(out["vol"]) == 5 and len(out["surface_abs"]) == 5 and all(np.isfinite(out["vol"]))


# ---- baselines of amendment 3: SOAP, heavy IC weight, first-segment refinement ----

def test_soap_minimises_quadratic_and_resumes_identically():
    from pinn1d import SOAP

    torch.manual_seed(0)
    a = torch.randn(6, 6)
    a = a @ a.T + 0.1 * torch.eye(6)
    target = torch.randn(6, 4)

    def run(steps, state=None, w0=None):
        w = (w0 if w0 is not None else torch.zeros(6, 4)).clone().requires_grad_(True)
        opt = SOAP([w], lr=0.05, freq=5)
        if state is not None:
            opt.load_state_dict(state)
        for _ in range(steps):
            loss = 0.5 * ((w - target) * (a @ (w - target))).sum()
            opt.zero_grad(); loss.backward(); opt.step()
        return w.detach(), opt.state_dict(), loss.item()

    w, _, loss = run(400)
    assert loss < 1e-4
    w_full, _, _ = run(40)
    w_half, state, _ = run(20)
    import copy
    w_res, _, _ = run(20, state=copy.deepcopy(state), w0=w_half)
    assert torch.allclose(w_full, w_res, atol=1e-12)


def test_ic_weight_and_refinement_change_loss_and_points():
    from dataclasses import replace

    import pinn1d

    p = PROBLEMS["E3_fisher"]
    cfg0 = replace(Config(), adam_steps=3, lbfgs_iters=0, nf=64, nb=16, n0=16)
    base, h0 = pinn1d.train(p, "vanilla", cfg0)
    heavy, h1 = pinn1d.train(p, "vanilla", replace(cfg0, w_ic=1000.0))
    assert h1["loss"][0] > 10 * h0["loss"][0]
    ref, _ = pinn1d.train(p, "vanilla", replace(cfg0, t_refine=0.3))
    assert all(torch.isfinite(q).all() for q in ref.state_dict().values())


@pytest.mark.parametrize("method", ["vanilla", "hardic+layer"])
def test_soap_train_smoke_and_resume(tmp_path, monkeypatch, method):
    from dataclasses import replace

    import pinn1d

    p = PROBLEMS["E3_fisher"]
    cfg = replace(Config(), optimizer="soap", adam_steps=20, nf=32, nb=8, n0=8, lbfgs_iters=20, lbfgs_chunk=10,
                  nf_fixed=32, nb_fixed=8, n0_fixed=8)
    ref_model, _ = pinn1d.train(p, method, cfg)
    ckpt = str(tmp_path / "s.ckpt")
    real = pinn1d.residuals
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] > 12:
            raise KeyboardInterrupt
        return real(*a, **k)

    monkeypatch.setattr(pinn1d, "residuals", flaky)
    with pytest.raises(KeyboardInterrupt):
        pinn1d.train(p, method, cfg, ckpt=ckpt, ckpt_every=5)
    monkeypatch.setattr(pinn1d, "residuals", real)
    model, hist = pinn1d.train(p, method, cfg, ckpt=ckpt, ckpt_every=5)
    assert hist["resumed_at"]
    for x, y in zip(ref_model.state_dict().values(), model.state_dict().values()):
        assert torch.equal(x, y)

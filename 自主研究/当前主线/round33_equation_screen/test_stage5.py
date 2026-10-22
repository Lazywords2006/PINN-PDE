"""Independent checks for the two opt-in initial conditions and training counters."""
from dataclasses import replace

import numpy as np
import pytest
import torch

from pinn1d import Config, Model, train
from problems import IC_CASES, PROBLEMS, get_problem
from run_artifacts import load_result, save_outputs
from stage5_support import check_new_references, heldout_residuals


@pytest.mark.parametrize("name,delta", [
    ("E1_heat_cos", 0.5 - 0.5 * np.pi**2),
    ("E3_fisher_cos", 1 / 0.3 - 0.005 * np.pi**2),
])
def test_new_initial_data_derivatives_and_mismatch(name, delta):
    p = get_problem(name)
    x = torch.linspace(0, 1, 101, requires_grad=True)
    fx = torch.autograd.grad(p.f(x).sum(), x, create_graph=True)[0]
    fxx = torch.autograd.grad(fx.sum(), x)[0]
    torch.testing.assert_close(fx, p.f_x(x), rtol=1e-13, atol=1e-14)
    torch.testing.assert_close(fxx, p.f_xx(x), rtol=1e-13, atol=1e-14)
    for func in (p.f, p.f_x, p.f_xx):
        np.testing.assert_allclose(func(x).detach().numpy(), func(x.detach().numpy()), rtol=1e-13, atol=1e-14)
    assert abs(p.f_x(0.0)) < 1e-14
    assert p.mismatch() == pytest.approx(delta, abs=1e-13)


def test_new_cases_do_not_expand_default_equation_selection():
    assert list(PROBLEMS) == ["E1_heat", "E2_allen_cahn", "E3_fisher"]
    assert not set(IC_CASES).intersection(PROBLEMS)
    assert PROBLEMS["E1_heat"].f(1.0) == 0.5
    assert PROBLEMS["E3_fisher"].f(1.0) == 0.0


def test_new_reference_convergence_and_independent_e1_expansion():
    rows = check_new_references()
    assert len(rows) == 2 and all(r["passed"] for r in rows), rows


@pytest.mark.parametrize("name", list(IC_CASES))
def test_new_hard_initial_data_and_complete_roundtrip(tmp_path, name):
    from test_integrity import record_for
    cfg = replace(Config(), width=8, depth=1)
    x = torch.linspace(0, 1, 101)
    for method in ("hardic", "hardic+layer"):
        model = Model(get_problem(name), method, cfg)
        assert torch.max(torch.abs(model(x, 0 * x) - model.p.f(x))) < 1e-14
        path = tmp_path / f"{method}.json"
        save_outputs(path, record_for(model, cfg), model)
        restored, _, status = load_result(path, expected_config=cfg)
        assert status == "complete"
        assert all(torch.equal(value, restored.state_dict()[key]) for key, value in model.state_dict().items())


def test_lbfgs_counts_match_actual_closure_invocations(monkeypatch):
    original_step = torch.optim.LBFGS.step
    calls = [0]
    def measured_step(optimizer, closure):
        def counted():
            calls[0] += 1
            return closure()
        return original_step(optimizer, counted)
    monkeypatch.setattr(torch.optim.LBFGS, "step", measured_step)
    cfg = replace(Config(), width=8, depth=1, adam_steps=2, nf=16, nb=4, n0=4,
                  nf_fixed=16, nb_fixed=4, n0_fixed=4, lbfgs_iters=10, lbfgs_chunk=5)
    _, hist = train(get_problem("E1_heat_cos"), "hardic", cfg)
    assert hist["adam_gradient_calls"] == 2
    assert hist["lbfgs_func_evals"] == calls[0] > 0
    assert 0 < hist["lbfgs_n_iter"] <= hist["lbfgs_func_evals"]
    assert hist["lbfgs_budget_used"] in (5, 10)
    assert hist["lbfgs_stop_reason"] in ("budget_exhausted", "loss_stagnation")


def test_heldout_diagnostic_zero_solution_has_only_initial_error():
    model = Model(get_problem("E1_heat_cos"), "vanilla", replace(Config(), width=4, depth=1))
    for parameter in model.parameters():
        torch.nn.init.zeros_(parameter)
    values = heldout_residuals(model)
    assert values["pde"]["n"] == 8192
    for name in ("pde", "left_neumann", "right_dynamic"):
        assert values[name]["rms"] == 0 and values[name]["max_abs"] == 0
    assert values["initial"]["n"] == 1024
    assert 0.3 < values["initial"]["rms"] < 0.4
    assert 0.49 < values["initial"]["max_abs"] <= 0.5

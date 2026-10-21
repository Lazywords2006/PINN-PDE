"""Meaningful preflight checks for the corrected baseline and result persistence."""
import copy
import json
from dataclasses import asdict, replace

import numpy as np
import pytest
import torch

from pinn1d import Config, Model, train
from problems import OUT_TIMES, get_problem
from run_artifacts import load_result, save_outputs, validate_checkpoint, validate_config
from soap_baseline import SOAPOfficial64
from third_party.soap_official import SOAP as UpstreamSOAP


def test_soap_float32_matches_pinned_upstream_through_qr_updates():
    original_dtype = torch.get_default_dtype()
    try:
        torch.set_default_dtype(torch.float32)
        gen = torch.Generator().manual_seed(55)
        a = torch.randn(5, 3, generator=gen).requires_grad_()
        b = a.detach().clone().requires_grad_()
        kwargs = dict(lr=0.003, betas=(0.95, 0.95), shampoo_beta=0.95, weight_decay=0, precondition_frequency=3)
        local, official = SOAPOfficial64([a], **kwargs), UpstreamSOAP([b], **kwargs)
        for step in range(25):
            grad = torch.randn(a.shape, generator=gen)
            a.grad, b.grad = grad.clone(), grad.clone()
            local.step()
            official.step()
            if step == 0:
                assert torch.equal(a, b)
                assert local.state[a]['step'] == official.state[b]['step'] == 0
            torch.testing.assert_close(a, b, rtol=1e-6, atol=1e-7)
            torch.testing.assert_close(local.state[a]['exp_avg_sq'], official.state[b]['exp_avg_sq'], rtol=1e-6, atol=1e-7)
    finally:
        torch.set_default_dtype(original_dtype)


def test_soap_float64_decompositions_do_not_downcast(monkeypatch):
    seen = []
    for name in ('eigh', 'qr'):
        real = getattr(torch.linalg, name)
        def checked(x, *args, _real=real, _name=name, **kwargs):
            seen.append((_name, x.dtype))
            return _real(x, *args, **kwargs)
        monkeypatch.setattr(torch.linalg, name, checked)
    x = torch.arange(12, dtype=torch.float64).reshape(4, 3).requires_grad_()
    opt = SOAPOfficial64([x], lr=0.001, weight_decay=0, precondition_frequency=2)
    original = x.detach().clone()
    for step in range(8):
        x.grad = torch.sin(original + step) + 0.1
        opt.step()
        if step == 0:
            assert torch.equal(x, original)
    assert {name for name, _ in seen} == {'eigh', 'qr'}
    assert all(dtype == torch.float64 for _, dtype in seen)
    assert torch.isfinite(x).all()


@pytest.mark.parametrize('method', ['vanilla', 'hardic+layer'])
def test_official64_training_resume_is_bitwise_identical(tmp_path, monkeypatch, method):
    import pinn1d
    p = get_problem('E3_fisher')
    cfg = replace(Config(), optimizer='soap_official64', adam_steps=20, nf=32, nb=8, n0=8,
                  nf_fixed=32, nb_fixed=8, n0_fixed=8, lbfgs_iters=20, lbfgs_chunk=10)
    full, full_hist = train(p, method, cfg)
    ckpt = str(tmp_path/'resume.ckpt')
    real = pinn1d.residuals
    calls = [0]
    def interrupt(*args, **kwargs):
        calls[0] += 1
        if calls[0] > 12:
            raise KeyboardInterrupt
        return real(*args, **kwargs)
    monkeypatch.setattr(pinn1d, 'residuals', interrupt)
    with pytest.raises(KeyboardInterrupt):
        train(p, method, cfg, ckpt=ckpt, ckpt_every=5)
    monkeypatch.setattr(pinn1d, 'residuals', real)
    validate_checkpoint(ckpt, p, method, cfg)
    resumed, resumed_hist = train(p, method, cfg, ckpt=ckpt, ckpt_every=5)
    assert resumed_hist['resumed_at'] == ['adam:10']
    assert full_hist['lbfgs_loss'] == resumed_hist['lbfgs_loss']
    assert all(torch.equal(v, resumed.state_dict()[k]) for k, v in full.state_dict().items())
    with pytest.raises(ValueError, match='match|configuration'):
        train(p, method, replace(cfg, lr0=0.002), ckpt=ckpt)


def record_for(model, cfg):
    return {'eq': model.p.name, 'method': model.method, 'seed': cfg.seed, 'tag': 'unit', 'config': asdict(cfg),
            'metrics': {'times': list(OUT_TIMES), 'vol': [0.1]*5, 'trace': [0.2]*5},
            'max_vol': 0.1, 'max_trace': 0.2, 'env': {'torch': str(torch.__version__)}}


@pytest.mark.parametrize('eq', ['E1_heat', 'E4_bulk_surface'])
def test_complete_model_roundtrip_preserves_all_branches(tmp_path, eq):
    cfg = replace(Config(), width=8, depth=1)
    model = Model(get_problem(eq), 'hardic+layer', cfg)
    path = tmp_path/'result.json'
    save_outputs(path, record_for(model, cfg), model)
    recovered, _, status = load_result(path, expected_config=cfg)
    assert status == 'complete'
    assert all(torch.equal(v, recovered.state_dict()[k]) for k, v in model.state_dict().items())
    if model.bulk_surface:
        t = torch.tensor([0.01, 0.05, 0.5])
        assert torch.equal(model.surface(t), recovered.surface(t))


@pytest.mark.parametrize('corruption', ['missing_base', 'corrupt_full', 'changed_metadata'])
def test_existing_outputs_reject_corruption(tmp_path, corruption):
    cfg = replace(Config(), width=8, depth=1)
    model = Model(get_problem('E1_heat'), 'hardic', cfg)
    path = tmp_path/'result.json'
    save_outputs(path, record_for(model, cfg), model)
    if corruption == 'missing_base':
        path.with_suffix('.pt').unlink()
    elif corruption == 'corrupt_full':
        path.with_suffix('.model.pt').write_bytes(b'incomplete')
    else:
        rec = json.loads(path.read_text())
        rec['seed'] = 7
        path.write_text(json.dumps(rec))
    with pytest.raises(ValueError):
        load_result(path)


def test_publish_failure_never_leaves_a_completed_json(tmp_path, monkeypatch):
    cfg = replace(Config(), width=8, depth=1)
    model = Model(get_problem('E1_heat'), 'hardic', cfg)
    path = tmp_path/'result.json'
    real = torch.save
    def fail(content, target):
        if str(target).endswith('.model.pt.tmp'):
            raise OSError('simulated disk write interruption')
        return real(content, target)
    monkeypatch.setattr(torch, 'save', fail)
    with pytest.raises(OSError, match='interruption'):
        save_outputs(path, record_for(model, cfg), model)
    assert not path.exists()
    monkeypatch.setattr(torch, 'save', real)
    save_outputs(path, record_for(model, cfg), model)
    assert load_result(path)[2] == 'complete'


def test_historical_e4_missing_surface_is_never_silently_reconstructed(tmp_path):
    cfg = replace(Config(), width=8, depth=1)
    model = Model(get_problem('E4_bulk_surface'), 'hardic', cfg)
    path = tmp_path/'legacy.json'
    path.write_text(json.dumps(record_for(model, cfg)))
    torch.save(model.base.state_dict(), path.with_suffix('.pt'))
    with pytest.raises(ValueError, match='lacks surface'):
        load_result(path)
    assert load_result(path, require_complete=False)[2] == 'legacy_bulk_only'


@pytest.mark.parametrize('eq', ['E1_heat', 'E4_bulk_surface'])
def test_run_one_saves_complete_outputs_and_checks_before_skip(tmp_path, monkeypatch, eq):
    import pinn1d
    import screen
    calls = []
    def train_stub(p, method, cfg, **kwargs):
        calls.append(1)
        return Model(p, method, cfg), {'wall_seconds': 0.0, 'adam_seconds': 0.0, 'loss': [1.0], 'lbfgs_loss': [0.5]}
    monkeypatch.setattr(pinn1d, 'train', train_stub)
    monkeypatch.setattr(screen, 'HERE', tmp_path)
    monkeypatch.setenv('R33_CKPT_DIR', str(tmp_path/'ckpt'))
    job = (eq, 'hardic+layer', 100, {'width': 8, 'depth': 1}, 'unit')
    assert screen.run_one(job).startswith('done ')
    path = screen.out_path('unit', eq, 'hardic+layer', 100)
    assert load_result(path)[2] == 'complete'
    with pytest.raises(ValueError, match='another job'):
        load_result(path, expected_job=(eq, 'vanilla', 100, 'unit'))
    assert screen.run_one(job).startswith('skip verified')
    assert len(calls) == 1
    path.with_suffix('.pt').unlink()
    with pytest.raises(ValueError, match='artifact'):
        screen.run_one(job)
    assert len(calls) == 1


@pytest.mark.parametrize('overrides', [{'optimizer': 'not_an_optimizer'}, {'lr0': float('nan')}, {'t_refine': 1.1}, {'arch': 'pirate', 'width': 63}])
def test_invalid_config_is_rejected_before_training(overrides):
    with pytest.raises(ValueError):
        validate_config(replace(Config(), **overrides), 'hardic')

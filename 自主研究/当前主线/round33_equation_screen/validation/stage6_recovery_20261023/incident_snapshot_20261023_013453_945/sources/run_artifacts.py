"""Complete, hashed result bundles; JSON is published last as the commit marker."""
from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import asdict
from pathlib import Path

import torch


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('result contains a non-finite number')
    if isinstance(value, dict):
        for item in value.values():
            _finite(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _finite(item)


def save_outputs(path, record, model):
    """Retain the historical base-only .pt and add a complete .model.pt bundle."""
    path = Path(path)
    _finite(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    base = path.with_suffix('.pt')
    full = path.with_suffix('.model.pt')
    metadata = json.loads(json.dumps({k: record[k] for k in ('eq', 'method', 'seed', 'tag', 'config', 'env')}))
    payload = {'format': 'r33_complete_model_v1', 'metadata': metadata, 'state_dict': model.state_dict()}
    for target, content in ((base, model.base.state_dict()), (full, payload)):
        temporary = target.with_name(target.name + '.tmp')
        torch.save(content, temporary)
        os.replace(temporary, target)
    record = dict(record)
    record['artifacts'] = {'version': 1, 'base': {'file': base.name, 'sha256': sha256(base)},
                           'model': {'file': full.name, 'sha256': sha256(full)}}
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(record, allow_nan=False), encoding='utf-8')
    os.replace(temporary, path)
    return record


def load_result(path, expected_config=None, require_complete=True, expected_job=None):
    """Fail on corrupt/config-mismatched results; never fill missing E4 weights."""
    from pinn1d import Config, Model
    from problems import OUT_TIMES, get_problem

    path = Path(path)
    rec = json.loads(path.read_text(encoding='utf-8'))
    _finite(rec)
    cfg = Config(**rec['config'])
    if expected_job is not None and (rec['eq'], rec['method'], rec['seed'], rec['tag']) != tuple(expected_job):
        raise ValueError('existing result belongs to another job')
    if cfg.seed != rec['seed']:
        raise ValueError('result seed disagrees with its configuration')
    if expected_config is not None and asdict(cfg) != asdict(expected_config):
        raise ValueError('existing result uses a different configuration; choose a new tag')
    if list(rec['metrics']['times']) != list(OUT_TIMES):
        raise ValueError('result output times disagree with the protocol')
    if any(len(rec['metrics'][key]) != len(OUT_TIMES) for key in ('vol', 'trace')):
        raise ValueError('incomplete error sequence')
    if rec['max_vol'] != max(rec['metrics']['vol']) or rec['max_trace'] != max(rec['metrics']['trace']):
        raise ValueError('result summary disagrees with its error sequence')
    model = Model(get_problem(rec['eq']), rec['method'], cfg)
    artifacts = rec.get('artifacts')
    if artifacts:
        if artifacts.get('version') != 1:
            raise ValueError('unsupported artifact manifest version')
        for key in ('base', 'model'):
            entry = artifacts[key]
            if Path(entry['file']).name != entry['file']:
                raise ValueError('artifact must be a file in the result directory')
            candidate = path.parent / entry['file']
            if not candidate.is_file() or sha256(candidate) != entry['sha256']:
                raise ValueError(f'missing or corrupted {key} artifact')
        payload = torch.load(path.parent / artifacts['model']['file'], weights_only=True, map_location='cpu')
        metadata = {k: rec[k] for k in ('eq', 'method', 'seed', 'tag', 'config', 'env')}
        if payload.get('format') != 'r33_complete_model_v1' or payload['metadata'] != metadata:
            raise ValueError('full model metadata disagrees with its result JSON')
        model.load_state_dict(payload['state_dict'], strict=True)
        status = 'complete'
    else:
        base = path.with_suffix('.pt')
        if not base.is_file():
            raise ValueError('result JSON exists without saved weights')
        model.base.load_state_dict(torch.load(base, weights_only=True, map_location='cpu'), strict=True)
        status = 'legacy_bulk_only' if model.bulk_surface else 'legacy_complete'
        if model.bulk_surface and require_complete:
            raise ValueError('historical E4 result lacks surface weights; keep it unreverified, do not overwrite it')
    if not all(torch.isfinite(t).all() for t in model.state_dict().values()):
        raise ValueError('saved model contains non-finite parameters')
    model.eval()
    return model, rec, status


def validate_checkpoint(path, problem, method, cfg):
    """CLI resume requires a bound identity; imported historical copies get one after inspection."""
    path = Path(path)
    if not path.exists():
        return
    state = torch.load(path, weights_only=False, map_location='cpu')
    expected = {'problem': problem.name, 'method': method, 'config': asdict(cfg)}
    if state.get('identity') != expected:
        raise ValueError('unbound or mismatched checkpoint; inspect/import it before resuming')
    saved_version = state.get('environment', {}).get('torch', '').split('+')[0]
    if saved_version and saved_version != str(torch.__version__).split('+')[0]:
        raise ValueError('checkpoint PyTorch version mismatch; use the pinned runtime')


def validate_config(cfg, method):
    from pinn1d import METHODS

    if method not in METHODS or cfg.arch not in ('mlp', 'pirate') or cfg.optimizer not in ('adam', 'soap', 'soap_official64'):
        raise ValueError('unknown method, architecture, or optimizer')
    for field in ('width', 'depth', 'adam_steps', 'nf', 'nb', 'n0', 'nf_fixed', 'nb_fixed', 'n0_fixed', 'lbfgs_chunk', 'soap_freq', 'causal_chunks', 'pirate_blocks'):
        value = getattr(cfg, field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f'{field} must be a positive integer')
    if cfg.lbfgs_iters < 0 or cfg.lbfgs_iters % cfg.lbfgs_chunk:
        raise ValueError('lbfgs_iters must be a nonnegative multiple of lbfgs_chunk')
    if cfg.arch == 'pirate' and (cfg.width % 2 or cfg.pirate_blocks <= 0):
        raise ValueError('PirateNet needs an even width and positive block count')
    if not 0 <= cfg.t_refine <= 1 or not 0 < cfg.rba_gamma < 1 or not 0 < cfg.soap_beta < 1:
        raise ValueError('invalid sampling fraction or averaging coefficient')
    if not math.isfinite(cfg.causal_eps) or cfg.causal_eps < 0:
        raise ValueError('causal_eps must be finite and nonnegative')
    for field in ('lr0', 'lr1', 'tau', 'w_ic', 'rba_eta', 'fourier_scale'):
        if not math.isfinite(getattr(cfg, field)) or getattr(cfg, field) <= 0:
            raise ValueError(f'{field} must be finite and positive')

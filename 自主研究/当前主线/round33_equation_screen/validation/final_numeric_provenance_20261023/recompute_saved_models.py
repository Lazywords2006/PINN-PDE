"""2026-10-23 read-only numerical production evidence. Never reconstruct training logs.

prepare freezes source/input identities; run launches independently logged processes;
worker reloads actual saved weights or freshly solves the registered reference.
The inference/reference implementation is frozen project code, NOT an independent
PDE solver. Quadrature, saved-weight loading, comparison and provenance are new.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import traceback
import warnings
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNTIME = Path("D:/CodexRuntime/runs/r33_final_numeric_provenance_20261023")
SOURCES = ("pinn1d.py", "problems.py", "run_artifacts.py", "screen.py",
           "stage5_support.py", "SCREEN_PROTOCOL.md")
TIMES = [0.05, 0.1, 0.25, 0.5, 1.0]
RTOL, ATOL, REF_TOL = 1e-5, 1e-9, 1e-8
sys.dont_write_bytecode = True


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for data in iter(lambda: handle.read(1048576), b""):
            h.update(data)
    return h.hexdigest()


def dump(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite_json(value):
    if isinstance(value, float):
        require(math.isfinite(value), "nonfinite input JSON")
    elif isinstance(value, dict):
        for item in value.values():
            finite_json(item)
    elif isinstance(value, list):
        for item in value:
            finite_json(item)


def raw_files():
    return sorted(p for p in (ROOT / "runs").rglob("*")
                  if p.is_file() and p.suffix in (".json", ".pt"))


def hashes(paths, root):
    return {p.relative_to(root).as_posix(): digest(p) for p in paths}


def verify_hashes(items, root):
    return {name: {"expected": expected,
                   "actual": digest(root / name) if (root / name).is_file() else None}
            for name, expected in items.items()
            if not (root / name).is_file() or digest(root / name) != expected}


def local_environment():
    return {"python": sys.version, "executable": sys.executable,
            "executable_sha256": digest(sys.executable), "platform": platform.platform(),
            "machine": platform.machine(), "processor": platform.processor(),
            "cwd": str(Path.cwd()), "pid": os.getpid(),
            "thread_and_cache_environment": {k: os.environ.get(k) for k in (
                "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                "TEMP", "TMP", "XDG_CACHE_HOME", "PIP_CACHE_DIR", "UV_CACHE_DIR", "PYTHONDONTWRITEBYTECODE")}}


def numerical_environment():
    import numpy as np
    import scipy
    import torch
    return {**local_environment(), "numpy": np.__version__, "scipy": scipy.__version__,
            "torch": str(torch.__version__), "torch_default_dtype": str(torch.get_default_dtype()),
            "torch_threads": torch.get_num_threads(), "torch_interop_threads": torch.get_num_interop_threads(),
            "torch_build": torch.__config__.show(),
            "distributions": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}}


def imported_files():
    rows = {}
    for name, mod in sorted(sys.modules.copy().items()):
        filename = getattr(mod, "__file__", None)
        if filename and Path(filename).is_file():
            p = Path(filename).resolve()
            rows.setdefault(str(p), {"sha256": digest(p), "bytes": p.stat().st_size, "modules": []})["modules"].append(name)
    return rows


def prepare():
    require(not (HERE / "plan.json").exists(), "frozen plan already exists; do not overwrite")
    paths = sorted((ROOT / "runs").rglob("*.json"))
    require(len(paths) == 206, f"expected all 206 results, found {len(paths)}")
    snapshot = hashes(raw_files(), ROOT)
    old_path = ROOT / "validation/feasibility_review_20261021/existing_data_review.json"
    old = read(old_path)["SHA256清单"]
    require(len(old) == 260 and not verify_hashes(old, ROOT), "historical 260-file identity failed")
    source_dir = HERE / "frozen_source"
    source_dir.mkdir(exist_ok=False)
    for name in SOURCES:
        shutil.copy2(ROOT / name, source_dir / name)
    code = {"recompute_saved_models.py": digest(__file__),
            **{f"frozen_source/{name}": digest(source_dir / name) for name in SOURCES}}
    jobs = []
    for i, path in enumerate(paths):
        rec = read(path)
        finite_json(rec)
        rel = path.relative_to(ROOT).as_posix()
        files = [rel, path.with_suffix(".pt").relative_to(ROOT).as_posix()]
        if rec.get("artifacts"):
            files += [(path.parent / rec["artifacts"]["model"]["file"]).relative_to(ROOT).as_posix()]
        require(all(x in snapshot for x in files), f"missing saved input for {rel}")
        jobs.append({"key": f"job_{i:03d}", "path": rel, "eq": rec["eq"], "method": rec["method"],
                     "seed": rec["seed"], "tag": rec["tag"], "config": rec["config"],
                     "input_hashes": {x: snapshot[x] for x in files},
                     "format": "complete" if rec.get("artifacts") else "legacy"})
    require(len({(j['eq'], j['method'], j['seed'], j['tag']) for j in jobs}) == len(jobs), "duplicate identity")
    # Exercise every forward construction, both architectures, full/legacy payloads,
    # missing E4 surface, and the historically resumed PirateNet configuration.
    specifications = [("screen", "E1_heat", "vanilla", 0),
                      ("screen", "E1_heat", "hardic", 0),
                      ("screen", "E2_allen_cahn", "rba", 0),
                      ("screen", "E3_fisher", "layer", 0),
                      ("e4screen", "E4_bulk_surface", "hardic+layer", 0),
                      ("pirate", "E1_heat", "hardic", 2),
                      ("pirate", "E1_heat", "hardic+layer", 0),
                      ("final_soap64_v1", "E3_fisher", "hardic+layer", 0)]
    probe = []
    for spec in specifications:
        matches = [j for j in jobs if (j['tag'], j['eq'], j['method'], j['seed']) == spec]
        require(len(matches) == 1, f"probe identity absent: {spec}")
        probe.append(matches[0]['key'])
    plan = {"created_utc": utc(), "scope": "2026-10-23 current saved-weight body/trace numerical recomputation only",
            "training_execution_history_reconstructed": False, "training_or_tuning_calls": 0,
            "independence": "new process/weight loading/quadrature/provenance; frozen project forward and reference implementations reused",
            "excluded": ["legacy E4 v(t) prediction", "legacy E4 surface/exchange residuals", "old training exits/warnings/trajectory"],
            "tolerances": {"rtol": RTOL, "atol": ATOL, "reference_selfcheck_max_abs": REF_TOL},
            "times": TIMES, "n64_gl200": True, "n96_gl400": True,
            "source_sha256": code, "raw_input_sha256": snapshot,
            "historical_manifest": {"path": str(old_path), "sha256": digest(old_path), "count": len(old)},
            "jobs": jobs, "probe_keys": probe}
    dump(HERE / "plan.json", plan)
    print(json.dumps({"result_count": len(jobs), "input_files": len(snapshot), "equations": sorted({j['eq'] for j in jobs}),
                      "probe_keys": probe, "checker_sha256": code['recompute_saved_models.py']}, ensure_ascii=False), flush=True)


def configure_runtime():
    dirs = {"TEMP": "D:/CodexRuntime/temp", "TMP": "D:/CodexRuntime/temp",
            "XDG_CACHE_HOME": "D:/CodexRuntime/cache/xdg", "PIP_CACHE_DIR": "D:/CodexRuntime/cache/pip",
            "UV_CACHE_DIR": "D:/CodexRuntime/cache/uv"}
    for key, value in dirs.items():
        Path(value).mkdir(parents=True, exist_ok=True)
        os.environ[key] = value
    for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[key] = "1"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["PYTHONUTF8"] = "1"


def freeze_check(plan):
    require(not verify_hashes(plan['source_sha256'], HERE), "checker or frozen dependency changed")
    for name in SOURCES:
        require(digest(ROOT / name) == plan['source_sha256'][f'frozen_source/{name}'], f"live source changed: {name}")


def initialize_numerics():
    sys.path.insert(0, str(HERE / "frozen_source"))
    import torch
    import pinn1d
    import problems
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    require(list(problems.OUT_TIMES) == TIMES, "evaluation times changed")
    require(str(torch.__version__).split('+')[0] == '2.14.1', "unexpected Torch version")
    require(torch.get_default_dtype() == torch.float64, "expected float64")
    # An explicit guard: accidental use of this imported training function fails.
    def forbidden_training(*args, **kwargs):
        raise RuntimeError("training is prohibited in this saved-weight audit")
    pinn1d.train = forbidden_training


def reference_job(eq, dest):
    import numpy as np
    from problems import get_problem, get_reference
    p = get_problem(eq)
    refs = {n: get_reference(p, n) for n in (48, 64, 96)}
    xcheck = np.linspace(0, 1, 401)
    arrays = {'times': np.array(TIMES), 'xcheck': xcheck}
    for n in (48, 96):
        arrays[f'selfcheck_n{n}'] = np.array([refs[n](xcheck, t) for t in TIMES])
    selfcheck = float(np.max(np.abs(arrays['selfcheck_n48'] - arrays['selfcheck_n96'])))
    for n, points in ((64, 200), (96, 400)):
        x, w = np.polynomial.legendre.leggauss(points)
        x, w = (x + 1.0) * 0.5, w * 0.5
        arrays[f'x{points}'], arrays[f'w{points}'] = x, w
        arrays[f'bulk_n{n}'] = np.array([refs[n](x, t) for t in TIMES])
        arrays[f'trace_n{n}'] = np.array([refs[n](np.array([1.0]), t)[0] for t in TIMES])
    require(all(np.isfinite(a).all() for a in arrays.values()), "nonfinite reference array")
    np.savez_compressed(dest / 'arrays.npz', **arrays)
    result = {"eq": eq, "selfcheck_max_abs": selfcheck, "reference_pass": selfcheck <= REF_TOL,
              "arrays_sha256": digest(dest / 'arrays.npz'), "n": [48, 64, 96],
              "selfcheck_grid_points": 401, "surface_reference_evaluated": False}
    dump(dest / 'result.json', result)
    require(result['reference_pass'], f"reference selfcheck exceeds {REF_TOL}: {selfcheck}")
    return result


def reload_saved(job):
    import torch
    from pinn1d import Config, Model
    from problems import get_problem
    require(not verify_hashes(job['input_hashes'], ROOT), "input identity changed before reload")
    path = ROOT / job['path']
    rec = read(path)
    finite_json(rec)
    require((rec['eq'], rec['method'], rec['seed'], rec['tag'], rec['config']) ==
            (job['eq'], job['method'], job['seed'], job['tag'], job['config']), "job metadata differs")
    require(rec['metrics']['times'] == TIMES and len(rec['metrics']['vol']) == 5 and len(rec['metrics']['trace']) == 5,
            "unexpected metric sequence")
    require(rec['max_vol'] == max(rec['metrics']['vol']) and rec['max_trace'] == max(rec['metrics']['trace']),
            "original scalar summary mismatch")
    cfg = Config(**rec['config'])
    require(cfg.seed == rec['seed'], "seed mismatch")
    # Meta construction has no numeric random parameters. All evaluated parameters
    # must be assigned from a persisted state dict before any forward call.
    with torch.device('meta'):
        model = Model(get_problem(rec['eq']), rec['method'], cfg)
    base = torch.load(path.with_suffix('.pt'), map_location='cpu', weights_only=True)
    art = rec.get('artifacts')
    if art:
        require(art['version'] == 1, "unrecognized complete artifact format")
        for key in ('base', 'model'):
            entry = art[key]
            require(Path(entry['file']).name == entry['file'], "artifact path escapes result directory")
            require(digest(path.parent / entry['file']) == entry['sha256'], "artifact's recorded SHA256 mismatch")
        require(art['base']['file'] == path.with_suffix('.pt').name, "unexpected base artifact name")
        payload = torch.load(path.parent / art['model']['file'], map_location='cpu', weights_only=True)
        require(payload['format'] == 'r33_complete_model_v1', "unrecognized model format")
        require(payload['metadata'] == {k: rec[k] for k in ('eq', 'method', 'seed', 'tag', 'config', 'env')},
                "full model metadata mismatch")
        model.load_state_dict(payload['state_dict'], strict=True, assign=True)
        full_base = model.base.state_dict()
        require(full_base.keys() == base.keys() and all(torch.equal(base[k], full_base[k]) for k in base),
                "full model and legacy base artifact disagree")
        status = 'complete'
    else:
        if model.bulk_surface:
            del model.surf  # absent historical surface weights remain absent
        model.base.load_state_dict(base, strict=True, assign=True)
        status = 'legacy_bulk_only' if model.bulk_surface else 'legacy_complete'
    require(all(not t.is_meta and torch.isfinite(t).all() for t in model.state_dict().values()), "unloaded/nonfinite parameter")
    require(all(t.dtype == torch.float64 for t in model.state_dict().values()), "saved model dtype is not float64")
    model.eval()
    return model, rec, status


def state_identity(model):
    return {k: hashlib.sha256(v.detach().numpy().tobytes()).hexdigest() for k, v in model.state_dict().items()}


def compare(actual, recorded):
    import numpy as np
    actual, recorded = np.asarray(actual), np.asarray(recorded)
    diff = np.abs(actual - recorded)
    limits = ATOL + RTOL * np.abs(recorded)
    return {'passed': bool(np.all(diff <= limits)), 'actual': actual.tolist(), 'recorded': recorded.tolist(),
            'absolute_difference': diff.tolist(), 'tolerance_per_value': limits.tolist(),
            'max_abs_difference': float(np.max(diff)), 'max_fraction_of_tolerance': float(np.max(diff / limits))}


def model_job(job, batch, dest):
    import numpy as np
    import torch
    ref_dir = batch / 'references' / job['eq']
    ref_result = read(ref_dir / 'result.json')
    require(ref_result['reference_pass'] and digest(ref_dir / 'arrays.npz') == ref_result['arrays_sha256'],
            "reference not passed or altered")
    model, rec, status = reload_saved(job)
    before = state_identity(model)
    arrays, comparisons = {}, {}
    with np.load(ref_dir / 'arrays.npz', allow_pickle=False) as refs:
        for n, points in ((64, 200), (96, 400)):
            x, w = refs[f'x{points}'], refs[f'w{points}']
            with torch.inference_mode():
                pred = np.array([model(torch.from_numpy(x), torch.full((points,), t, dtype=torch.float64)).numpy() for t in TIMES])
                trace = np.array([float(model(torch.ones(1, dtype=torch.float64), torch.tensor([t], dtype=torch.float64))[0]) for t in TIMES])
            target, target_trace = refs[f'bulk_n{n}'], refs[f'trace_n{n}']
            # New vectorized implementation of the registered relative L2/trace definitions.
            denominator = np.sum(w[None, :] * target**2, axis=1)
            require(np.all(denominator > 0), "zero body normalization")
            vol = np.sqrt(np.sum(w[None, :] * (pred - target)**2, axis=1) / denominator)
            tr = np.abs(trace - target_trace) / np.maximum(np.abs(target_trace), 1e-12)
            arrays.update({f'pred_n{n}': pred, f'trace_pred_n{n}': trace, f'vol_n{n}': vol, f'trace_n{n}': tr})
            comparisons[f'n{n}_gl{points}'] = {k: compare(v, rec['metrics'][k]) for k, v in (('vol', vol), ('trace', tr))}
    require(all(np.isfinite(a).all() for a in arrays.values()), "nonfinite model output")
    np.savez_compressed(dest / 'arrays.npz', times=np.array(TIMES), **arrays)
    state_unchanged = before == state_identity(model)
    input_unchanged = not verify_hashes(job['input_hashes'], ROOT)
    result = {"key": job['key'], "path": job['path'], "eq": rec['eq'], "method": rec['method'],
              "tag": rec['tag'], "seed": rec['seed'], "config": rec['config'], "restore_status": status,
              "architecture": rec['config'].get('arch', 'mlp'), "input_sha256": job['input_hashes'],
              "reference_arrays_sha256": ref_result['arrays_sha256'], "reference_result_sha256": digest(ref_dir/'result.json'),
              "arrays_sha256": digest(dest/'arrays.npz'), "comparisons": comparisons,
              "all_comparisons_pass": all(c['passed'] for level in comparisons.values() for c in level.values()),
              "input_unchanged": input_unchanged, "model_state_unchanged": state_unchanged,
              "evaluated_state_sha256": before, "surface_evaluated": False,
              "missing_surface_branch": status == 'legacy_bulk_only',
              "excluded": ['v(t)', 'surface/exchange residuals'] if status == 'legacy_bulk_only' else [],
              "training_calls": 0, "historical_training_exit_or_warnings_recovered": False}
    dump(dest / 'result.json', result)
    require(state_unchanged and input_unchanged, "model/input changed during inference")
    require(result['all_comparisons_pass'], "registered numerical tolerance exceeded; retain this failure")
    return result


def worker(args):
    batch = Path(args.batch_dir)
    dest = batch / ('references' if args.kind == 'reference' else 'models') / args.key
    dest.mkdir(parents=True, exist_ok=True)
    captured = []
    original_show = warnings.showwarning
    def record_warning(message, category, filename, lineno, file=None, line=None):
        captured.append({'message': str(message), 'category': category.__name__, 'filename': filename, 'lineno': lineno})
        original_show(message, category, filename, lineno, file=file, line=line)
    warnings.showwarning = record_warning
    warnings.simplefilter('always')
    started, tick, exitcode = utc(), time.perf_counter(), 0
    status = {'kind': args.kind, 'key': args.key, 'started_utc': started,
              'argv': sys.argv, 'plan_sha256': digest(HERE/'plan.json')}
    print(json.dumps({'event': 'worker_start', **status}, ensure_ascii=False), flush=True)
    try:
        plan = read(HERE / 'plan.json')
        freeze_check(plan)
        initialize_numerics()
        status['environment'] = numerical_environment()
        if args.kind == 'reference':
            reference_job(args.key, dest)
        else:
            job = next(j for j in plan['jobs'] if j['key'] == args.key)
            model_job(job, batch, dest)
        freeze_check(plan)
        status['outcome'] = 'completed'
    except BaseException as error:
        exitcode = 1
        status.update(outcome='failed', exception_type=type(error).__name__, exception=str(error))
        traceback.print_exc()
    finally:
        modules = imported_files()
        dump(dest / 'imported_files.json', modules)
        status.update(finished_utc=utc(), elapsed_seconds=time.perf_counter()-tick,
                      warnings=captured, warning_count=len(captured),
                      imported_files_sha256=digest(dest/'imported_files.json'),
                      intended_exit_code=exitcode)
        dump(dest/'worker_status.json', status)
        print(json.dumps({'event': 'worker_end', 'kind': args.kind, 'key': args.key,
                          'outcome': status['outcome'], 'warning_count': len(captured),
                          'elapsed_seconds': status['elapsed_seconds']}, ensure_ascii=False), flush=True)
    return exitcode


def launch(kind, key, batch):
    dest = batch / ('references' if kind == 'reference' else 'models') / key
    dest.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, '-B', str(Path(__file__).resolve()), 'worker', '--kind', kind,
               '--key', key, '--batch-dir', str(batch)]
    invocation = {'command_argv': command, 'command_windows': subprocess.list2cmdline(command),
                  'cwd': str(HERE), 'started_utc': utc(), 'kind': kind, 'key': key}
    dump(dest/'invocation.json', invocation)
    tick = time.perf_counter()
    with (dest/'stdout.log').open('wb') as out, (dest/'stderr.log').open('wb') as err:
        completed = subprocess.run(command, cwd=str(HERE), env=os.environ.copy(), stdout=out, stderr=err,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    execution = {**invocation, 'finished_utc': utc(), 'actual_returncode': completed.returncode,
                 'elapsed_seconds': time.perf_counter()-tick,
                 'stdout_sha256': digest(dest/'stdout.log'), 'stderr_sha256': digest(dest/'stderr.log'),
                 'outputs_sha256': hashes(sorted(p for p in dest.iterdir() if p.is_file()), dest)}
    dump(dest/'execution.json', execution)
    print(json.dumps({'kind': kind, 'key': key, 'actual_returncode': completed.returncode,
                      'elapsed_seconds': execution['elapsed_seconds']}, ensure_ascii=False), flush=True)
    return execution


def run_batch(args):
    require(1 <= args.workers <= 8, 'workers must be between 1 and 8')
    plan = read(HERE/'plan.json')
    freeze_check(plan)
    require(not verify_hashes(plan['raw_input_sha256'], ROOT), 'input snapshot mismatch before batch')
    batch = RUNTIME / args.batch
    batch.mkdir(parents=True, exist_ok=False)
    jobs = plan['jobs'] if args.batch == 'full' else [j for j in plan['jobs'] if j['key'] in plan['probe_keys']]
    equations = sorted({j['eq'] for j in jobs})
    started, tick = utc(), time.perf_counter()
    dump(batch/'input_manifest_before.json', hashes(raw_files(), ROOT))
    dump(batch/'batch_invocation.json', {'argv': sys.argv, 'command_windows': subprocess.list2cmdline([sys.executable, *sys.argv]),
        'started_utc': started, 'environment': local_environment(), 'workers': args.workers,
        'plan_sha256': digest(HERE/'plan.json'), 'source_sha256': plan['source_sha256'],
        'scope': plan['scope'], 'job_keys': [j['key'] for j in jobs]})
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        refs = list(pool.map(lambda eq: launch('reference', eq, batch), equations))
    # A failed reference is preserved and prohibits dependent numerical claims.
    reference_ok = all(x['actual_returncode'] == 0 for x in refs)
    runs = []
    if reference_ok:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            runs = list(pool.map(lambda j: launch('model', j['key'], batch), jobs))
    after = hashes(raw_files(), ROOT)
    dump(batch/'input_manifest_after.json', after)
    unchanged = after == read(batch/'input_manifest_before.json') == plan['raw_input_sha256']
    rows = [read(batch/'models'/r['key']/'result.json') for r in runs if (batch/'models'/r['key']/'result.json').exists()]
    statuses = [read(batch/('references' if x['kind']=='reference' else 'models')/x['key']/'worker_status.json')
                for x in refs+runs if (batch/('references' if x['kind']=='reference' else 'models')/x['key']/'worker_status.json').exists()]
    result = {'scope': plan['scope'], 'batch': args.batch, 'started_utc': started, 'finished_utc': utc(),
              'elapsed_seconds': time.perf_counter()-tick, 'expected_results': len(jobs), 'attempted_models': len(runs),
              'reference_count': len(refs), 'reference_executions': refs, 'model_executions': runs,
              'input_file_count': len(after), 'inputs_unchanged': unchanged,
              'all_actual_returncodes_zero': all(x['actual_returncode'] == 0 for x in refs+runs),
              'warning_count': sum(s['warning_count'] for s in statuses), 'warnings': [w for s in statuses for w in s['warnings']],
              'all_model_comparisons_pass': len(rows)==len(jobs) and all(r['all_comparisons_pass'] for r in rows),
              'legacy_e4_surface_excluded': sum(r['missing_surface_branch'] for r in rows),
              'max_abs_differences': {level: {metric: max((r['comparisons'][level][metric]['max_abs_difference'] for r in rows), default=None)
                                             for metric in ('vol','trace')} for level in ('n64_gl200','n96_gl400')},
              'rows': rows, 'training_calls': 0, 'historical_training_history_reconstructed': False}
    result['current_numerical_recomputation_pass'] = (reference_ok and len(runs)==len(jobs) and unchanged
        and result['all_actual_returncodes_zero'] and result['all_model_comparisons_pass'])
    dump(batch/'summary.json', result)
    dump(batch/'evidence_sha256.json', hashes(sorted(p for p in batch.rglob('*') if p.is_file()), batch))
    destination = HERE/'evidence'/args.batch
    require(not destination.exists(), 'project evidence destination already exists')
    shutil.copytree(batch, destination)
    copied = hashes(sorted(p for p in destination.rglob('*') if p.is_file() and p.name!='evidence_sha256.json'), destination)
    require(copied == read(batch/'evidence_sha256.json'), 'evidence copy identity failure')
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','reference_executions','model_executions')}, ensure_ascii=False), flush=True)
    return 0 if result['current_numerical_recomputation_pass'] else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='command', required=True)
    sub.add_parser('prepare')
    run = sub.add_parser('run')
    run.add_argument('--batch', choices=('probe','full'), required=True)
    run.add_argument('--workers', type=int, default=8)
    worker_parser = sub.add_parser('worker')
    worker_parser.add_argument('--kind', choices=('reference','model'), required=True)
    worker_parser.add_argument('--key', required=True)
    worker_parser.add_argument('--batch-dir', required=True)
    args = ap.parse_args()
    configure_runtime()
    if args.command == 'prepare':
        prepare()
        return 0
    return worker(args) if args.command == 'worker' else run_batch(args)


if __name__ == '__main__':
    raise SystemExit(main())

"""Supplementary saved-weight production evidence for 52 existing heldout records.

No training, no new scientific experiment, no changed diagnostics or thresholds.
The body/trace checker and its plan remain unchanged. Forward equations are from
frozen source; this script independently evaluates autograd residual formulas,
the original fixed point sequence, and RMS/max_abs summaries.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import warnings

import recompute_saved_models as base

HERE, ROOT = base.HERE, base.ROOT
PLAN = HERE/'heldout_plan.json'
REPORTS = (
    'validation/stage5_20261022/pirate_validation.json',
    'validation/stage5_20261022/ic_validation.json',
    'validation/stage6_20261022/completion_archive_20261023/results_validation.json',
)
COMPONENTS = ('pde', 'left_neumann', 'right_dynamic', 'initial')
sys.dont_write_bytecode = True


def prepare():
    base.require(not PLAN.exists(), 'heldout plan already exists')
    parent = base.read(HERE/'plan.json')
    base.freeze_check(parent)
    lookup = {(j['tag'],j['eq'],j['method'],j['seed']):j for j in parent['jobs']}
    frozen = HERE/'heldout_source_records'
    frozen.mkdir(exist_ok=False)
    jobs = []
    counts = []
    for relative, count in zip(REPORTS, (4,18,30)):
        path = ROOT/relative
        report = base.read(path)
        rows = report['results']
        base.require(len(rows) == count, 'unexpected recorded diagnostic count')
        destination = frozen/path.name
        shutil.copy2(path, destination)
        counts.append({'path':relative,'count':len(rows),'with_heldout':sum('heldout' in x for x in rows)})
        for row in rows:
            original = lookup[tuple(row['job'])]
            base.require(row['json_sha256'] == original['input_hashes'][original['path']], 'record to input JSON identity mismatch')
            base.require(set(row['heldout']) == set(COMPONENTS), 'heldout component missing')
            base.require(original['eq'] != 'E4_bulk_surface', 'E4 has no authorized complete heldout state')
            for component in COMPONENTS:
                entry = row['heldout'][component]
                base.finite_json(entry)
                base.require(set(entry) == {'rms','max_abs','n'}, 'unexpected heldout fields')
                base.require(entry['n'] == (8192 if component=='pde' else 1024), 'point count mismatch')
            jobs.append({**original, 'recorded_heldout':row['heldout'], 'record_source':relative,
                         'record_source_sha256':base.digest(path)})
    base.require(len(jobs)==52 and len({j['key'] for j in jobs})==52, 'expected 52 distinct heldout records')
    plan = {'created_utc':base.utc(), 'scope':'2026-10-23 saved-weight recomputation of existing 52 heldout diagnostics only',
            'parent_plan_sha256':base.digest(HERE/'plan.json'),
            'source_sha256':{'recompute_heldout.py':base.digest(__file__),
                             'recompute_saved_models.py':base.digest(HERE/'recompute_saved_models.py'),
                             **{f'heldout_source_records/{Path(r).name}':base.digest(ROOT/r) for r in REPORTS}},
            'original_report_sha256':{r:base.digest(ROOT/r) for r in REPORTS},
            'definition_sources':['frozen_source/stage5_support.py:42','frozen_source/pinn1d.py:258',
                                  'frozen_source/SCREEN_PROTOCOL.md amendments 5-6'],
            'points':{'numpy_generator':'default_rng','seed':330500,'ordered_draws':[
                ['x_bulk','uniform',0,1,8192],['t_bulk','uniform',1e-4,1,8192],
                ['t_left','uniform',1e-4,1,1024],['t_right','uniform',1e-4,1,1024],
                ['x_initial','uniform',0,1,1024]],'body_chunk_size':1024},
            'formulas':{'pde':'u_t - D*u_xx - R(u)','left_neumann':'u_x(0,t)',
                        'right_dynamic':'c*u_t(1,t) + D*u_x(1,t) + G(u(1,t))','initial':'u(x,0)-f(x)'},
            'aggregation':{'rms':'sqrt(mean(residual**2))','max_abs':'max(abs(residual))'},
            'comparison_tolerance':{'rtol':base.RTOL,'atol':base.ATOL},
            'counts':counts, 'jobs':jobs, 'training_calls':0,
            'excluded':['training losses/trajectory','legacy E4 surface weights/predictions/residuals']}
    base.dump(PLAN,plan)
    print({'jobs':len(jobs),'counts':counts,'checker_sha256':plan['source_sha256']['recompute_heldout.py']},flush=True)


def check_frozen(plan):
    base.require(base.digest(HERE/'plan.json')==plan['parent_plan_sha256'],'body/trace plan changed')
    base.freeze_check(base.read(HERE/'plan.json'))
    base.require(not base.verify_hashes(plan['source_sha256'],HERE),'heldout checker or frozen records changed')
    base.require(not base.verify_hashes(plan['original_report_sha256'],ROOT),'existing heldout report changed')


def compute(job,dest):
    import numpy as np
    import torch
    model, rec, status = base.reload_saved(job)
    base.require(not model.bulk_surface,'surface diagnostics prohibited')
    before = base.state_identity(model)
    rng = np.random.default_rng(330500)
    xf,tf,tl,tr,x0 = (rng.uniform(0,1,8192),rng.uniform(1e-4,1,8192),
                     rng.uniform(1e-4,1,1024),rng.uniform(1e-4,1,1024),rng.uniform(0,1,1024))
    def tensor(a,grad=False):
        return torch.tensor(a,dtype=torch.float64,requires_grad=grad)
    def derivative(y,x):
        return torch.autograd.grad(y,x,grad_outputs=torch.ones_like(y),create_graph=True)[0]
    pde=[]
    for start in range(0,8192,1024):
        x,t=tensor(xf[start:start+1024],True),tensor(tf[start:start+1024],True)
        u=model(x,t)
        ux=derivative(u,x)
        residual=derivative(u,t)-model.p.D*derivative(ux,x)-model.p.R(u)
        pde.append(residual.detach().numpy())
        del x,t,u,ux,residual
    x=tensor(np.zeros(1024),True)
    left=derivative(model(x,tensor(tl)),x).detach().numpy()
    x,t=tensor(np.ones(1024),True),tensor(tr,True)
    u=model(x,t)
    right=(model.p.c*derivative(u,t)+model.p.D*derivative(u,x)+model.p.G(u)).detach().numpy()
    with torch.no_grad():
        x=tensor(x0)
        initial=(model(x,torch.zeros_like(x))-model.p.f(x)).numpy()
    values=dict(zip(COMPONENTS,(np.concatenate(pde),left,right,initial)))
    base.require(all(np.isfinite(a).all() for a in values.values()),'nonfinite heldout residual')
    np.savez_compressed(dest/'arrays.npz',x_bulk=xf,t_bulk=tf,t_left=tl,t_right=tr,x_initial=x0,**values)
    aggregates={component:{'rms':float(np.sqrt(np.mean(a**2))),'max_abs':float(np.max(np.abs(a))),'n':len(a)}
                for component,a in values.items()}
    comparisons={component:{field:base.compare([entry[field]],[job['recorded_heldout'][component][field]])
                            for field in ('rms','max_abs')} for component,entry in aggregates.items()}
    unchanged=before==base.state_identity(model) and not base.verify_hashes(job['input_hashes'],ROOT)
    gradients_absent=all(p.grad is None for p in model.parameters())
    output={'key':job['key'],'job':[job['tag'],job['eq'],job['method'],job['seed']],
            'path':job['path'],'input_sha256':job['input_hashes'],'config':job['config'],
            'restore_status':status,'record_source':job['record_source'],
            'record_source_sha256':job['record_source_sha256'],'original':job['recorded_heldout'],
            'recomputed':aggregates,'comparisons':comparisons,'arrays_sha256':base.digest(dest/'arrays.npz'),
            'all_comparisons_pass':all(c['passed'] for entry in comparisons.values() for c in entry.values()),
            'model_and_input_unchanged':unchanged,'parameter_gradients_not_accumulated':gradients_absent,
            'point_counts_match':all(aggregates[c]['n']==job['recorded_heldout'][c]['n'] for c in COMPONENTS),
            'training_calls':0,'historical_training_history_reconstructed':False}
    base.dump(dest/'result.json',output)
    base.require(output['all_comparisons_pass'] and unchanged and gradients_absent and output['point_counts_match'],
                 'heldout numerical comparison or read-only check failed; retain failure')


def worker(args):
    batch=Path(args.batch_dir)
    dest=batch/'models'/args.key
    captured=[]
    original=warnings.showwarning
    def warning(message,category,filename,lineno,file=None,line=None):
        captured.append({'message':str(message),'category':category.__name__,'filename':filename,'lineno':lineno})
        original(message,category,filename,lineno,file=file,line=line)
    warnings.showwarning=warning
    warnings.simplefilter('always')
    tick=time.perf_counter()
    status={'started_utc':base.utc(),'argv':sys.argv,'key':args.key,'heldout_plan_sha256':base.digest(PLAN)}
    print({'event':'worker_start',**status},flush=True)
    code=0
    try:
        plan=base.read(PLAN)
        check_frozen(plan)
        base.initialize_numerics()
        status['environment']=base.numerical_environment()
        compute(next(j for j in plan['jobs'] if j['key']==args.key),dest)
        check_frozen(plan)
        status['outcome']='completed'
    except BaseException as exc:
        code=1
        status.update(outcome='failed',exception_type=type(exc).__name__,exception=str(exc))
        traceback.print_exc()
    finally:
        base.dump(dest/'imported_files.json',base.imported_files())
        status.update(finished_utc=base.utc(),elapsed_seconds=time.perf_counter()-tick,
                      warning_count=len(captured),warnings=captured,intended_exit_code=code,
                      imported_files_sha256=base.digest(dest/'imported_files.json'))
        base.dump(dest/'worker_status.json',status)
        print({'event':'worker_end','key':args.key,'outcome':status['outcome'],
               'warning_count':len(captured),'elapsed_seconds':status['elapsed_seconds']},flush=True)
    return code


def launch(job,batch):
    dest=batch/'models'/job['key']
    dest.mkdir(parents=True,exist_ok=False)
    command=[sys.executable,'-B',str(Path(__file__).resolve()),'worker','--key',job['key'],'--batch-dir',str(batch)]
    invocation={'command_argv':command,'command_windows':subprocess.list2cmdline(command),
                'cwd':str(HERE),'started_utc':base.utc(),'key':job['key']}
    base.dump(dest/'invocation.json',invocation)
    tick=time.perf_counter()
    with (dest/'stdout.log').open('wb') as out,(dest/'stderr.log').open('wb') as err:
        process=subprocess.run(command,cwd=str(HERE),env=os.environ.copy(),stdout=out,stderr=err,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    execution={**invocation,'actual_returncode':process.returncode,'finished_utc':base.utc(),
               'elapsed_seconds':time.perf_counter()-tick,
               'stdout_sha256':base.digest(dest/'stdout.log'),'stderr_sha256':base.digest(dest/'stderr.log'),
               'outputs_sha256':base.hashes(sorted(p for p in dest.iterdir() if p.is_file()),dest)}
    base.dump(dest/'execution.json',execution)
    print({'key':job['key'],'actual_returncode':process.returncode,'elapsed_seconds':execution['elapsed_seconds']},flush=True)
    return execution


def run(args):
    base.require(1<=args.workers<=8,'workers must be 1..8')
    plan=base.read(PLAN)
    check_frozen(plan)
    parent=base.read(HERE/'plan.json')
    base.require(not base.verify_hashes(parent['raw_input_sha256'],ROOT),'raw input snapshot mismatch')
    batch=base.RUNTIME/'heldout'
    batch.mkdir(parents=True,exist_ok=False)
    tick=time.perf_counter()
    invocation={'argv':sys.argv,'command_windows':subprocess.list2cmdline([sys.executable,*sys.argv]),
                'started_utc':base.utc(),'environment':base.local_environment(),'workers':args.workers,
                'heldout_plan_sha256':base.digest(PLAN),'source_sha256':plan['source_sha256']}
    base.dump(batch/'batch_invocation.json',invocation)
    base.dump(batch/'input_manifest_before.json',base.hashes(base.raw_files(),ROOT))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        executions=list(pool.map(lambda job:launch(job,batch),plan['jobs']))
    rows=[base.read(batch/'models'/j['key']/'result.json') for j in plan['jobs']
          if (batch/'models'/j['key']/'result.json').exists()]
    statuses=[base.read(batch/'models'/j['key']/'worker_status.json') for j in plan['jobs']
              if (batch/'models'/j['key']/'worker_status.json').exists()]
    after=base.hashes(base.raw_files(),ROOT)
    base.dump(batch/'input_manifest_after.json',after)
    unchanged=after==parent['raw_input_sha256']==base.read(batch/'input_manifest_before.json')
    check_frozen(plan)
    summary={'scope':plan['scope'],'started_utc':invocation['started_utc'],'finished_utc':base.utc(),
             'elapsed_seconds':time.perf_counter()-tick,'expected_count':52,'result_count':len(rows),
             'execution_count':len(executions),'all_actual_returncodes_zero':all(x['actual_returncode']==0 for x in executions),
             'all_comparisons_pass':len(rows)==52 and all(r['all_comparisons_pass'] for r in rows),
             'inputs_unchanged':unchanged,'warning_count':sum(s['warning_count'] for s in statuses),
             'warnings':[w for s in statuses for w in s['warnings']],
             'max_abs_differences':{c:{f:max((r['comparisons'][c][f]['max_abs_difference'] for r in rows),default=None)
                                       for f in ('rms','max_abs')} for c in COMPONENTS},
             'executions':executions,'rows':rows,'training_calls':0,'historical_training_history_reconstructed':False}
    summary['current_heldout_recomputation_pass']=(summary['all_actual_returncodes_zero'] and
                                                 summary['all_comparisons_pass'] and unchanged)
    base.dump(batch/'summary.json',summary)
    base.dump(batch/'evidence_sha256.json',base.hashes(sorted(p for p in batch.rglob('*') if p.is_file()),batch))
    destination=HERE/'evidence'/'heldout'
    base.require(not destination.exists(),'heldout evidence destination already exists')
    shutil.copytree(batch,destination)
    base.require(base.hashes(sorted(p for p in destination.rglob('*') if p.is_file() and p.name!='evidence_sha256.json'),destination)
                 ==base.read(batch/'evidence_sha256.json'),'evidence copy identity failed')
    print({k:v for k,v in summary.items() if k not in ('rows','executions')},flush=True)
    return 0 if summary['current_heldout_recomputation_pass'] else 1


def main():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest='command',required=True)
    sub.add_parser('prepare')
    runner=sub.add_parser('run')
    runner.add_argument('--workers',type=int,default=8)
    child=sub.add_parser('worker')
    child.add_argument('--key',required=True)
    child.add_argument('--batch-dir',required=True)
    args=ap.parse_args()
    base.configure_runtime()
    if args.command=='prepare':
        prepare()
        return 0
    return worker(args) if args.command=='worker' else run(args)


if __name__=='__main__':
    raise SystemExit(main())

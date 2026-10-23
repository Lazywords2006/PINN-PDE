import json, hashlib, datetime, collections, sys
from pathlib import Path
import numpy as np

ROOT=Path('E:/PINN-PDE/自主研究/当前主线/round33_equation_screen')
P=ROOT/'validation/final_numeric_provenance_20261023'
O=ROOT/'manuscript/integrity/final_numeric_completion_20261023'
FIRST=ROOT/'manuscript/integrity/final_revised1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]; deps={}; maxima={}; details={'auditor_environment':{'executable':sys.executable,'numpy':np.__version__,'python':sys.version}}
def check(label,ok,detail=None):
    checks.append({'label':label,'passed':bool(ok),'detail':detail})
def same(a,b):return np.allclose(a,b,rtol=1e-13,atol=1e-15)
plan=read(P/'plan.json'); hplan=read(P/'heldout_plan.json')
check('first_audit_preserved',sha(FIRST/'FINAL_INTEGRITY_REVIEW_CN.md')=='9a292e11206f5ed790917de94d5be1bfd06bcf332afd1bbd7dae75f5cb4893f8')
check('first_audit_manifest_preserved',sha(FIRST/'REVIEW_MANIFEST.json')=='aad83fa52d65076be608f8aa42ef2990d6aaf4d5154464b4a26de70ca68599ce')
check('body_checker_reviewed_bytes',sha(P/'recompute_saved_models.py')=='7cbe64b660606ca66bf63af28f6fc71c4072106a687c8a85a56b3fb7c37b9611')
check('heldout_checker_reviewed_bytes',sha(P/'recompute_heldout.py')=='0f95d05c484dddb3be20d8d8de512f0759934234eee278bd0d00505eff7b0433')
check('body_plan_reviewed_bytes',sha(P/'plan.json')=='c3ab15b47313c62f5b50aafff2df1e698e4aff5c8a905bc7654485dabbaf8d5b')
check('heldout_plan_reviewed_bytes',sha(P/'heldout_plan.json')=='032c8890ad5c49a57f30c265bfe46fa649ccafb1b1afa14b5a90f744f793756c')
for p,h in {**plan['source_sha256'],**hplan['source_sha256']}.items():check('source:'+p,sha(P/p)==h)
for p,h in plan['raw_input_sha256'].items():check('raw_input:'+p,sha(ROOT/p)==h)
for p,h in hplan['original_report_sha256'].items():check('old_heldout_report:'+p,sha(ROOT/p)==h)
check('all206_unique_inputs',len(plan['jobs'])==206 and len({j['path'] for j in plan['jobs']})==206)
check('all52_unique_heldout',len(hplan['jobs'])==52 and len({j['path'] for j in hplan['jobs']})==52)
jobmap={x['key']:x for x in plan['jobs']}; heldmap={x['key']:x for x in hplan['jobs']}
times=np.array([.05,.1,.25,.5,1.])

def inspect_execution(batch,kind,key):
    d=batch/kind/key;e=read(d/'execution.json');w=read(d/'worker_status.json');iv=read(d/'invocation.json')
    label=batch.name+':'+kind+':'+key
    check(label+':actual_OS_returncode',e['actual_returncode']==0 and w['outcome']=='completed' and w['intended_exit_code']==0)
    check(label+':actual_logs_warnings',w['warning_count']==0 and w['warnings']==[] and (d/'stderr.log').stat().st_size==0)
    check(label+':stdout_completion','worker_end' in (d/'stdout.log').read_text(encoding='utf-8') and 'completed' in (d/'stdout.log').read_text(encoding='utf-8'))
    check(label+':log_hashes',sha(d/'stdout.log')==e['stdout_sha256'] and sha(d/'stderr.log')==e['stderr_sha256'])
    check(label+':output_hashes',all(sha(d/f)==h for f,h in e['outputs_sha256'].items()))
    check(label+':imports_manifest',sha(d/'imported_files.json')==w['imported_files_sha256'])
    check(label+':actual_single_thread_float64',w['environment']['torch_threads']==1 and w['environment']['torch_interop_threads']==1 and w['environment']['torch_default_dtype']=='torch.float64')
    env=w['environment'];check(label+':interpreter',sha(Path(env['executable']))==env['executable_sha256'])
    check(label+':runtime_on_D',all(str(env['thread_and_cache_environment'][k]).lower().replace('\\','/').startswith('d:/codexruntime/') for k in ['TEMP','TMP','XDG_CACHE_HOME','PIP_CACHE_DIR','UV_CACHE_DIR']))
    imp=read(d/'imported_files.json'); conflict=[]
    for p,v in imp.items():
        if p in deps and deps[p]!=v['sha256']:conflict.append(p)
        deps[p]=v['sha256']
    check(label+':import_hash_consistency',not conflict,conflict)
    return read(d/'result.json')

def inspect_batch(bname):
    b=P/'evidence'/bname;s=read(b/'summary.json');iv=read(b/'batch_invocation.json')
    sup=P/'supervisors'/bname;se=read(sup/'execution.json')
    check(bname+':supervisor_exit_and_stderr',se['actual_returncode']==0 and (sup/'stderr.log').stat().st_size==0)
    check(bname+':supervisor_bound_logs_source',sha(sup/'stdout.log')==se['stdout_sha256'] and sha(sup/'stderr.log')==se['stderr_sha256'] and sha(P/'launch_logged.ps1')==se['launcher_sha256'] and sha(P/('recompute_saved_models.py' if bname=='full' else 'recompute_heldout.py'))==se['script_sha256'])
    check(bname+':snapshot488',read(b/'input_manifest_before.json')==read(b/'input_manifest_after.json')==plan['raw_input_sha256'])
    check(bname+':archived_files',all(sha(b/p)==h for p,h in read(b/'evidence_sha256.json').items()))
    check(bname+':concurrency',1<=iv['workers']<=8)
    check(bname+':no_training',s['training_calls']==0 and s.get('historical_training_history_reconstructed') is False)
    check(bname+':summarywarnings',s['warning_count']==0 and s['warnings']==[])
    return b,s

b,s=inspect_batch('full')
check('full:complete206',len(s['rows'])==s['expected_results']==s['attempted_models']==206 and len(s['model_executions'])==206)
check('full:exact_job_set',set(r['key'] for r in s['rows'])==set(jobmap))
check('full:reference_equation_set',set(e['key'] for e in s['reference_executions'])==set(j['eq'] for j in plan['jobs']))
for z in s['reference_executions']:
    r=inspect_execution(b,'references',z['key']);d=b/'references'/z['key']
    with np.load(d/'arrays.npz',allow_pickle=False) as a:
        check('reference:'+z['key']+':finite',all(np.isfinite(a[k]).all() for k in a))
        check('reference:'+z['key']+':grid',np.array_equal(a['times'],times) and np.array_equal(a['xcheck'],np.linspace(0,1,401)))
        diff=float(np.max(np.abs(a['selfcheck_n48']-a['selfcheck_n96'])))
        check('reference:'+z['key']+':N48_N96',diff<=1e-8 and diff==r['selfcheck_max_abs'],diff)
        for n in [200,400]:
            x,w=np.polynomial.legendre.leggauss(n)
            check('reference:'+z['key']+':GL'+str(n),same(a['x'+str(n)],(x+1)/2) and same(a['w'+str(n)],w/2))
    check('reference:'+z['key']+':NPZhash',sha(d/'arrays.npz')==r['arrays_sha256'])
    maxima['reference_'+z['key']]=diff

legacy=0; maxima.update({f'n{n}_{m}':0. for n in [64,96] for m in ['vol','trace']})
for row in s['rows']:
    key=row['key'];r=inspect_execution(b,'models',key);j=jobmap[key];d=b/'models'/key;rd=b/'references'/j['eq'];raw=read(ROOT/j['path'])
    check(key+':exact_summary_result',r==row)
    check(key+':id_config_inputs',all(r[k]==j[k] for k in ['path','eq','method','seed','tag','config']) and r['input_sha256']==j['input_hashes'])
    check(key+':reference_binding',sha(rd/'arrays.npz')==r['reference_arrays_sha256'] and sha(rd/'result.json')==r['reference_result_sha256'] and sha(d/'arrays.npz')==r['arrays_sha256'])
    with np.load(d/'arrays.npz',allow_pickle=False) as a,np.load(rd/'arrays.npz',allow_pickle=False) as ref:
        check(key+':times_finite',np.array_equal(a['times'],times) and all(np.isfinite(a[k]).all() for k in a))
        for n,k in [(64,200),(96,400)]:
            target=ref[f'bulk_n{n}'];w=ref[f'w{k}'];pred=a[f'pred_n{n}']
            actual={'vol':np.sqrt(np.sum((pred-target)**2*w,axis=1)/np.sum(target**2*w,axis=1)), 'trace':np.abs(a[f'trace_pred_n{n}']-ref[f'trace_n{n}'])/np.maximum(np.abs(ref[f'trace_n{n}']),1e-12)}
            for m,v in actual.items():
                old=np.asarray(raw['metrics'][m]);limit=1e-9+1e-5*np.abs(old);diff=np.abs(v-old);c=r['comparisons'][f'n{n}_gl{k}'][m]
                check(f'{key}:npz_n{n}_{m}',same(v,a[f'{m}_n{n}']) and same(v,c['actual']) and np.array_equal(old,c['recorded']) and np.all(diff<=limit),{'max_abs_difference':float(diff.max()),'max_tolerance_fraction':float(np.max(diff/limit))})
                maxima[f'n{n}_{m}']=max(maxima[f'n{n}_{m}'],float(diff.max()))
    check(key+':no_mutation_no_surface',r['model_state_unchanged'] and r['input_unchanged'] and not r['surface_evaluated'] and r['training_calls']==0)
    if r['restore_status']=='legacy_bulk_only':
        legacy+=1;check(key+':E4_explicit_exclusion',r['eq']=='E4_bulk_surface' and r['missing_surface_branch'] and set(r['excluded'])=={'v(t)','surface/exchange residuals'})
check('full:legacy_E4_count',legacy==20,legacy)
details['full']={k:s[k] for k in ['expected_results','reference_count','elapsed_seconds','warning_count','max_abs_differences']}

if '--body-only' in sys.argv:
    for p,h in deps.items():check('live_dependency:'+p,sha(Path(p))==h)
    details['unique_dependency_files']=len(deps)
    details['independent_max_body_trace_difference']=maxima
    out={'created':datetime.datetime.now().astimezone().isoformat(),'scope':'Completed 206 body/trace plus 12 reference execution records; heldout and candidate2 not yet included.','checks':checks,'check_count':len(checks),'failure_count':sum(not x['passed'] for x in checks),'failures':[x for x in checks if not x['passed']],'details':details}
    (O/'FULL206_INDEPENDENT_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:out[k] for k in ['check_count','failure_count','failures','details']},ensure_ascii=False))
    sys.exit(0)

b,s=inspect_batch('heldout')
check('heldout:complete52',len(s['rows'])==s['result_count']==s['execution_count']==s['expected_count']==52)
check('heldout:exact_job_set',set(r['key'] for r in s['rows'])==set(heldmap))
rng=np.random.default_rng(330500)
points=dict(zip(['x_bulk','t_bulk','t_left','t_right','x_initial'],[rng.uniform(0,1,8192),rng.uniform(1e-4,1,8192),rng.uniform(1e-4,1,1024),rng.uniform(1e-4,1,1024),rng.uniform(0,1,1024)]))
heldmax={}
for row in s['rows']:
    key=row['key'];r=inspect_execution(b,'models',key);j=heldmap[key];d=b/'models'/key
    check('heldout:'+key+':summary_record_identity',r==row and r['path']==j['path'] and r['input_sha256']==j['input_hashes'] and r['config']==j['config'] and r['original']==j['recorded_heldout'])
    check('heldout:'+key+':source_hash',sha(ROOT/r['record_source'])==r['record_source_sha256']==j['record_source_sha256'])
    check('heldout:'+key+':NPZhash',sha(d/'arrays.npz')==r['arrays_sha256'])
    with np.load(d/'arrays.npz',allow_pickle=False) as a:
        check('heldout:'+key+':points_exact',all(np.array_equal(a[k],v) for k,v in points.items()))
        check('heldout:'+key+':finite',all(np.isfinite(a[k]).all() for k in a))
        for component,old in j['recorded_heldout'].items():
            arr=a[component];v={'rms':float(np.sqrt(np.mean(arr**2))),'max_abs':float(np.max(np.abs(arr))),'n':len(arr)}
            check('heldout:'+key+':count:'+component,len(arr)==old['n']==r['recomputed'][component]['n'])
            for field in ['rms','max_abs']:
                diff=abs(v[field]-old[field]);limit=1e-9+1e-5*abs(old[field])
                check('heldout:'+key+':aggregate:'+component+':'+field,same(v[field],r['recomputed'][component][field]) and diff<=limit,{'absolute_difference':diff,'tolerance':limit})
                heldmax[component+'_'+field]=max(heldmax.get(component+'_'+field,0),diff)
    check('heldout:'+key+':read_only',r['model_and_input_unchanged'] and r['parameter_gradients_not_accumulated'] and r['training_calls']==0 and j['eq']!='E4_bulk_surface')
details['heldout']={k:s[k] for k in ['result_count','elapsed_seconds','warning_count','max_abs_differences']}
for p,h in deps.items():check('live_dependency:'+p,sha(Path(p))==h)
details['unique_dependency_files']=len(deps)
details['independent_max_body_trace_difference']=maxima
details['independent_max_heldout_difference']=heldmax
out={'created':datetime.datetime.now().astimezone().isoformat(),'method':'Read-only independent audit of actual execution records, all produced arrays, all input/source/dependency hashes; no training, no solver rerun, no altered thresholds. Frozen source reviewed separately before actual runs.','first_failure_preserved':True,'checks':checks,'check_count':len(checks),'failure_count':sum(not x['passed'] for x in checks),'failures':[x for x in checks if not x['passed']],'details':details,'source_bindings':{str(p.relative_to(ROOT)):sha(p) for p in [P/'plan.json',P/'heldout_plan.json',P/'evidence/full/summary.json',P/'evidence/heldout/summary.json']}}
(O/'ACTUAL_RUN_INDEPENDENT_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:out[k] for k in ['check_count','failure_count','failures','details']},ensure_ascii=False))

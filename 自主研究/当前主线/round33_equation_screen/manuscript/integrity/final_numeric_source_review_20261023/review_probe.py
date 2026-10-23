import json,hashlib,datetime
from pathlib import Path
import numpy as np
R=Path('E:/PINN-PDE/自主研究/当前主线/round33_equation_screen');P=R/'validation/final_numeric_provenance_20261023';B=P/'evidence/probe';O=R/'manuscript/integrity/final_numeric_source_review_20261023'
def j(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
plan=j(P/'plan.json');s=j(B/'summary.json');checks=[]
def ck(label,okay,detail=None):checks.append(dict(label=label,passed=bool(okay),detail=detail))
ck('reviewed_checker_hash',sha(P/'recompute_saved_models.py')=='7cbe64b660606ca66bf63af28f6fc71c4072106a687c8a85a56b3fb7c37b9611')
for p,h in plan['source_sha256'].items():ck('frozen_source:'+p,sha(P/p)==h)
for p,h in plan['raw_input_sha256'].items():ck('raw_input:'+p,sha(R/p)==h)
for p,h in j(B/'evidence_sha256.json').items():ck('probe_file:'+p,sha(B/p)==h)
ck('manifest_unchanged',j(B/'input_manifest_before.json')==j(B/'input_manifest_after.json')==plan['raw_input_sha256'])
for z in s['reference_executions']+s['model_executions']:
 d=B/('references' if z['kind']=='reference' else 'models')/z['key'];e=j(d/'execution.json');w=j(d/'worker_status.json');txt=(d/'stdout.log').read_text(encoding='utf-8')
 ck('real_returncode:'+z['key'],e['actual_returncode']==0 and w['outcome']=='completed')
 ck('warnings:'+z['key'],w['warning_count']==0 and not w['warnings'] and (d/'stderr.log').stat().st_size==0)
 ck('worker_completed_stdout:'+z['key'],'worker_end' in txt and 'completed' in txt)
 ck('module_import_hash:'+z['key'],sha(d/'imported_files.json')==w['imported_files_sha256'])
for row in s['rows']:
 d=B/'models'/row['key'];rd=B/'references'/row['eq'];raw=j(R/row['path'])
 with np.load(d/'arrays.npz',allow_pickle=False) as a,np.load(rd/'arrays.npz',allow_pickle=False) as refs:
  for n,k in [(64,200),(96,400)]:
   target=refs[f'bulk_n{n}'];w=refs[f'w{k}'];pred=a[f'pred_n{n}']
   actual=np.sqrt(np.sum((pred-target)**2*w,axis=1)/np.sum(target**2*w,axis=1));trace=np.abs(a[f'trace_pred_n{n}']-refs[f'trace_n{n}'])/np.maximum(np.abs(refs[f'trace_n{n}']),1e-12)
   for metric,v in [('vol',actual),('trace',trace)]:
    old=np.asarray(raw['metrics'][metric]);lim=1e-9+1e-5*np.abs(old)
    ck(f'npz_metric:{row["key"]}:n{n}:{metric}',np.allclose(v,a[f'{metric}_n{n}'],rtol=1e-14,atol=1e-15) and np.all(np.abs(v-old)<=lim),dict(max_abs_difference=float(np.max(np.abs(v-old)))))
 ck('unchanged_model:'+row['key'],row['model_state_unchanged'] and row['input_unchanged'] and not row['surface_evaluated'])
out=dict(created=datetime.datetime.now().astimezone().isoformat(),checker_sha256=sha(P/'recompute_saved_models.py'),plan_sha256=sha(P/'plan.json'),probe_summary_sha256=sha(B/'summary.json'),checks=checks,failures=[x for x in checks if not x['passed']],method_review='read full checker and frozen forward/reference implementations; independent recomputation of saved NPZ weighted relative errors; no training or model run by this reviewer',scope='release to run body/trace audit only, not final integrity PASS')
(O/'PROBE_INDEPENDENT_CHECK.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(checks=len(checks),failures=out['failures']),ensure_ascii=False))

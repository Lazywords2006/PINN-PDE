import json, csv, re, hashlib, statistics, datetime, math
from pathlib import Path
R=Path('E:/PINN-PDE/自主研究/当前主线/round33_equation_screen')
O=R/'manuscript/integrity/final_revised1'
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def j(p): return read(R/p)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def path(job):
 tag,eq,m,s=job
 return R/'runs'/tag/eq/(m.replace('+','_')+'_s'+str(s)+'.json')
def close(a,b): return abs(a-b)<=1e-9+1e-5*abs(b)
checks=[]
def check(kind,src,actual,expected,ok=None):
 checks.append(dict(kind=kind,source=src,actual=actual,expected=expected,passed=actual==expected if ok is None else bool(ok)))
h=j('validation/feasibility_review_20261021/existing_data_review.json')
for p,v in h['SHA256清单'].items():check('legacy_sha256',p,sha(R/p),v)
for x in h['逐结果复核']:
 p=x['文件'];raw=j(p)
 check('legacy_raw_max',p,max(raw['metrics']['vol']),x['原体误差'])
 check('legacy_saved_recompute',p,x['重算体误差'],x['原体误差'],close(x['重算体误差'],x['原体误差']))
 check('legacy_saved_dense_recompute',p,x['加密重算体误差'],x['原体误差'],close(x['加密重算体误差'],x['原体误差']))
 check('legacy_saved_component_deltas',p,max(x['体误差序列最大差'],x['迹误差序列最大差']),1e-9,max(x['体误差序列最大差'],x['迹误差序列最大差'])<1e-9)
p=j('validation/resolution_20261022/preflight_review.json')
for x in p['逐结果']:
 raw=j(x['文件']);check('preflight_json_hash',x['文件'],sha(R/x['文件']),x['JSON_SHA256'])
 check('preflight_vol',x['文件'],raw['metrics']['vol'],x['体误差序列'])
 check('preflight_trace',x['文件'],raw['metrics']['trace'],x['迹误差序列'])
 check('preflight_saved_deltas',x['文件'],max(x['体误差重算最大差'],x['迹误差重算最大差']),1e-9,max(x['体误差重算最大差'],x['迹误差重算最大差'])<1e-9)
 for kind in ['base','model']:
  z=x['产物'][kind];check('preflight_weight_hash',str((R/x['文件']).with_name(z['file'])),sha((R/x['文件']).with_name(z['file'])),z['sha256'])
saved={}
for f in ['validation/stage5_20261022/ic_validation.json','validation/stage5_20261022/pirate_validation.json','validation/stage6_20261022/completion_archive_20261023/results_validation.json']:
 for x in j(f)['results']:
  rp=path(x['job']);raw=read(rp);saved[tuple(x['job'])]=x
  check('saved_raw_hash',str(rp),sha(rp),x['json_sha256'])
  for name in ['metrics','recomputed_N64_GL200','dense_metrics','dense_metrics_N96_GL400']:
   if name in x:
    for metric in ['vol','trace']:
     check('saved_sequence_tolerance',str(rp)+'#'+name+'.'+metric,x[name][metric],raw['metrics'][metric],all(close(a,b) for a,b in zip(x[name][metric],raw['metrics'][metric])))
  for c,v in x.get('history_counters',{}).items():
   if c in raw['history']:check('history_counters',str(rp)+'#'+c,raw['history'][c],v)
a=j('validation/stage6_analysis_20261022/complete_v2/analysis_evidence.json')
s=j('validation/stage6_20261022/completion_archive_20261023/final_runtime_status.json')
status={tuple(x['job']):x for x in s['tasks']}
csvsets={}
for filename in ['all_new_runs.csv','default_six_arms.csv','tau_sensitivity.csv']:
 rows=list(csv.DictReader((R/'validation/stage6_analysis_20261022/complete_v2'/filename).open(encoding='utf-8-sig')))
 csvsets[filename]=[x['source'] for x in rows]
 for x in rows:
  raw=j(x['source']);src=filename+'#'+x['source'];job=(x['tag'],x['eq'],x['method'],int(x['seed']))
  check('csv_sha256',src,sha(R/x['source']),x['source_sha256'])
  for m in ['max_vol','max_trace']:check('csv_metric',src+'#'+m,float(x[m]),raw[m])
  for m in ['vol','trace']:
   for t,v in zip(raw['metrics']['times'],raw['metrics'][m]):check('csv_metric',src+'#'+m+str(t),float(x[f'{m}_t{t:g}']),v)
  for m,v in raw['env'].items():
   if m in x:check('csv_env',src+'#'+m,x[m],v)
  for k in ['adam_gradient_calls','lbfgs_budget_used','lbfgs_func_evals','lbfgs_n_iter']:
   check('csv_counter',src+'#'+k,None if x[k]=='' else int(x[k]),raw['history'].get(k))
  if job in saved:
   for comp,vs in saved[job]['heldout'].items():
    for stat in ['rms','max_abs']:check('csv_heldout',src+'#'+comp+'.'+stat,float(x['heldout_'+comp+'_'+stat]),vs[stat])
  if job in status:
   check('csv_attempt_cost',src,float(x['attempt_wall_seconds_sum']),sum(z['wall_seconds'] for z in status[job]['attempts']))
check('csv_unique_records','union',len(set(csvsets['default_six_arms.csv']+csvsets['tau_sensitivity.csv'])),48)
check('csv_shared_records','intersection',len(set(csvsets['default_six_arms.csv'])&set(csvsets['tau_sensitivity.csv'])),6)
newraw=[read(path(x['job'])) for x in s['tasks']]
check('trajectory_cost','raw30',sum(x['wall_seconds'] for x in newraw),a['costs']['new_local_30']['trajectory_seconds_sum'],abs(sum(x['wall_seconds'] for x in newraw)-a['costs']['new_local_30']['trajectory_seconds_sum'])<1e-6)
check('attempt_cost','status30',sum(y['wall_seconds'] for x in s['tasks'] for y in x['attempts']),a['costs']['local_attempt_wall_seconds_sum'])
check('runner_cost','status',s['session_wall_seconds']+s['prior_runner_wall_seconds'],a['costs']['local_runner_elapsed_seconds'])
check('batch_cost','status',s['batch_elapsed_seconds'],a['costs']['local_batch_elapsed_seconds'])
for x in s['tasks']:
 check('attempt_count',x['id'],len(x['attempts']),1)
 for z in x['attempts']:check('attempt_exit',x['id'],z['exit_code'],0)
for f,v in a['evidence']['source_hashes'].items():check('current_source_hash',f,sha(R/f),v)
for f,v in a['output_sha256'].items():check('analysis_output_hash',f,sha(R/'validation/stage6_analysis_20261022/complete_v2'/f),v)
for f,v in a['analysis_code_sha256'].items():check('analysis_code_hash',f,sha(R/'validation/stage6_analysis_20261022'/f),v)
for x in csv.DictReader((R/'manuscript/figures/analytic_layer_data.csv').open(encoding='utf-8-sig')):
 c,y,t=float(x['C']),float(x['y']),float(x['t']);v=math.exp(y/c+t/c**2)*math.erfc(y/(2*math.sqrt(t))+math.sqrt(t)/c)
 check('analytic_figure_data',f"panel{x['panel']}#y={y},t={t}",float(x['Q']),v,abs(float(x['Q'])-v)<1e-14)
for x in csv.DictReader((R/'manuscript/figures/history_v2/historical_comparison_data.csv').open(encoding='utf-8-sig')):
 check('history_figure_raw_hash',x['source'],sha(R/x['source']),x['sha256'])
 check('history_figure_raw_value',x['source'],float(x['max_vol']),max(j(x['source'])['metrics']['vol']))
for key,expected in [('lbfgs_n_iter',[1880,3000]),('lbfgs_func_evals',[3211,3771])]:
 vals=[x['history'][key] for x in newraw];check('stage6_counter_range',key,[min(vals),max(vals)],expected)
first5=[x for k,x in saved.items() if k[0] in ['final_ic_v1','pirate']]
for key,expected in [('lbfgs_n_iter',[1951,3000]),('lbfgs_func_evals',[3196,3751])]:
 vals=[x['history_counters'][key] for x in first5];check('stage5_counter_range',key,[min(vals),max(vals)],expected)
times=[read(path(x['job']))['wall_seconds']/60 for x in first5 if x['job'][0]=='final_ic_v1']
check('stage5_cost_minutes','ic18',[round(min(times),1),round(statistics.median(times),1),round(max(times),1)],[38.2,90.4,103.5])
logs=[]
for x in s['tasks']:
 for z in x['attempts']:
  p=Path(z['log']);txt=p.read_text(encoding='utf-8',errors='replace');flags=[t for t in txt.splitlines() if re.search(r'(?i)warning|traceback|exception|nan|inf\b',t)]
  logs.append(dict(job=x['job'],file=str(p),sha256=sha(p),flag_lines=flags,exit=z['exit_code']))
summary=dict(created=datetime.datetime.now().astimezone().isoformat(),scope='read-only saved-artifact verification; no training, model reload, or new reference integration',checks=checks,failures=[x for x in checks if not x['passed']],legacy= dict(rows=130,hashes=260,saved_warnings='historical full production warning/exit evidence unavailable; disclosed'),preflight_rows=24,saved_stage5_stage6_rows=len(saved),stage6_logs=logs,source_lineage_counts=[len(x['jobs']) for x in s['source_lineage']],csv_source_sets=csvsets)
(O/'SUPPLEMENT_AUDIT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(checks=len(checks),failures=summary['failures'],logs_with_flags=[x['file'] for x in logs if x['flag_lines']],source_lineage_counts=summary['source_lineage_counts']),ensure_ascii=False))

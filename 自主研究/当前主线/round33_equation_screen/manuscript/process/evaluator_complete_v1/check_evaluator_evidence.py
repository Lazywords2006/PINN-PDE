"""Read-only scientific/data checks for frozen evaluator Phase 6b, round 1.
No project code imports, model loading, training, or ODE integration.
Only outputs to this evaluator directory.
"""
from pathlib import Path
import hashlib, json, re, statistics, math
from collections import defaultdict

ROOT = Path(r'E:\PINN-PDE\自主研究\当前主线\round33_equation_screen')
OUT = Path(__file__).resolve().parent
def read_json(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
draft_path = ROOT/'manuscript/drafts/complete_v1.md'
draft = draft_path.read_text(encoding='utf-8-sig')
packet = (OUT/'input_packet.md').read_text(encoding='utf-8-sig')
stage6 = read_json(ROOT/'validation/stage6_analysis_20261022/complete_v2/analysis_evidence.json')
old = read_json(ROOT/'manuscript/process/writer_data_evidence.json')
manifest = stage6['evidence']['raw_sha256']
hash_checks=[]
raw={}
for rel, expected in manifest.items():
    path = ROOT/rel
    actual = sha(path)
    hash_checks.append({'path':rel,'expected':expected,'actual':actual,'match':expected==actual})
    if path.suffix=='.json':
        j=read_json(path)
        raw[(j['tag'],j['eq'],j['method'],int(j['seed']))]=j
assert len(raw)==206

max_checks=[]
groups=defaultdict(list)
for key,j in sorted(raw.items()):
    assert j['metrics']['times']==[.05,.1,.25,.5,1.0]
    v=max(j['metrics']['vol']); t=max(j['metrics']['trace'])
    max_checks.append({'job':list(key),'vol_match':v==j['max_vol'],'trace_match':t==j['max_trace'],'all_finite':all(math.isfinite(x) for x in j['metrics']['vol']+j['metrics']['trace'])})
    groups[key[:3]].append((key[3],v,t))
def group(tag,eq,method):
    a=sorted(groups[(tag,eq,method)])
    assert a
    return {'seeds':[x[0] for x in a],'vol':[x[1] for x in a],'trace':[x[2] for x in a],
            'vol_median':statistics.median(x[1] for x in a),'trace_median':statistics.median(x[2] for x in a),
            'threshold_count':sum(x[1]<=.01 for x in a)}
def ratio(tag,eq,baseline='hardic',candidate='hardic+layer'):
    return group(tag,eq,baseline)['vol_median']/group(tag,eq,candidate)['vol_median']

table_checks=[]
def near(display,value):
    d=float(display)
    if 'e' in display.lower():
        mantissa,exponent=display.lower().split('e')
        places=len(mantissa.split('.')[1]) if '.' in mantissa else 0
        tol=.5001*10**(int(exponent)-places)
    else:
        places=len(display.split('.')[1]) if '.' in display else 0
        tol=.5001*10**(-places)
    return abs(d-value)<=tol
def check(table,line,field,display,value):
    table_checks.append({'table':table,'line':line,'field':field,'display':display,'expected':value,'match':near(display,value)})
table=None
for line,s in enumerate(draft.splitlines(),1):
    if s.startswith('表') and '\u3000' in s:
        table=s.split('\u3000')[0]
    if not s.startswith('|'): continue
    cells=[x.strip() for x in s.strip('|').split('|')]
    if not cells[0].startswith('E'): continue
    eq=cells[0]
    if table in ['表2','表3','表4','表7']:
        if table=='表7':
            tag='confirm' if cells[1].startswith('Adam') else 'final_soap64_v1'
            method=cells[2]; offset=3
        else:
            tag={'表2':'confirm','表3':'final_ic_v1','表4':'pirate'}[table]
            method=cells[1]; offset=2
        if method=='RBA本地变体': method='rba'
        g=group(tag,eq,method)
        for n,val in enumerate(g['vol']): check(table,line,'seed'+str(n),cells[offset+n],val)
        check(table,line,'vol_median',cells[offset+3],g['vol_median'])
        check(table,line,'trace_median',cells[offset+4],g['trace_median'])
        table_checks.append({'table':table,'line':line,'field':'threshold_count','match':cells[offset+5]==str(g['threshold_count'])+'/3'})
    elif table=='表5':
        tag='confirm' if eq in ['E1_heat','E3_fisher'] else 'axis'
        h=group(tag,eq,'hardic'); c=group(tag,eq,'hardic+layer')
        for k,idx,val in [('delta',1,raw[(tag,eq,'hardic+layer',0)]['delta']),('hardic_median',2,h['vol_median']),('candidate_median',3,c['vol_median']),('ratio',4,h['vol_median']/c['vol_median'])]: check(table,line,k,cells[idx],val)
    elif table=='表6':
        tau=cells[1]; tag={'0.03':'sensitivity_tau003_v1','0.1':'confirm','0.3':'sensitivity_tau03_v1'}[tau]
        g=group(tag,eq,'hardic+layer')
        for n,val in enumerate(g['vol']): check(table,line,'seed'+str(n),cells[3+n],val)
        check(table,line,'vol_median',cells[6],g['vol_median'])
        check(table,line,'ratio',cells[8],g['vol_median']/group('confirm',eq,'hardic+layer')['vol_median'])
    elif table=='表B1':
        method='rba' if cells[1]=='RBA本地变体' else cells[1]
        g=group('screen',eq,method)
        for k,idx,val in [('vol_s0',2,g['vol'][0]),('vol_s1',3,g['vol'][1]),('vol_median',4,g['vol_median']),('trace_s0',5,g['trace'][0]),('trace_s1',6,g['trace'][1]),('trace_median',7,g['trace_median'])]: check(table,line,k,cells[idx],val)
    elif table=='表B2':
        bg=min(group('screen',eq,m)['vol_median'] for m in ['hardic','rba'])
        cg=min(group('screen',eq,m)['vol_median'] for m in ['layer','hardic+layer'])
        check(table,line,'vanilla_median',cells[2],group('screen',eq,'vanilla')['vol_median'])
        check(table,line,'ratio',cells[5],bg/cg)

cfg=read_json(ROOT/'manuscript/PAPER_CONFIGURATION.json')
counts={}; current=None; in_math=False
for s in draft.splitlines():
    if s.startswith('## '):
        title=s[3:]
        current=title if title in cfg['section_targets'] else None
        if current: counts[current]=0
    if current is None: continue
    if s.strip()=='\\[': in_math=True; continue
    if s.strip()=='\\]': in_math=False; continue
    if in_math or s.startswith('|') or s.startswith('![') or re.match(r'^图\d',s): continue
    counts[current]+=len(re.findall(r'[\u4e00-\u9fff]',s))

validator=read_json(ROOT/'validation/stage6_20261022/results_validation.json')
validation=[]
for row in validator['results']:
    k=tuple(row['job']); j=raw[k]
    checks=[]
    for kind in ['recomputed_N64_GL200','dense_metrics_N96_GL400']:
        for field in ['vol','trace']:
            for a,b in zip(j['metrics'][field],row[kind][field]): checks.append(abs(a-b)<=1e-9+1e-5*abs(b))
    validation.append({'job':list(k),'saved_recomputation_complete':row['complete_and_recomputed'],'saved_series_tolerance':all(checks),'json_hash_match':row['json_sha256']==manifest['runs/'+k[0]+'/'+k[1]+'/'+k[2].replace('+','_')+'_s'+str(k[3])+'.json']})

ratios={}
for tag,eq in [('confirm','E1_heat'),('confirm','E3_fisher'),('final_ic_v1','E1_heat_cos'),('final_ic_v1','E3_fisher_cos'),('pirate','E1_heat'),('pirate','E3_fisher'),('final_soap64_v1','E1_heat'),('final_soap64_v1','E3_fisher'),('axis','E3_k0.1'),('e4confirm','E4_bulk_surface')]:
    ratios[tag+'/'+eq]=ratio(tag,eq)
ratios['E4_vanilla_over_candidate']=ratio('e4confirm','E4_bulk_surface','vanilla')
ratios['new_E3_seed0_increase_percent']=(raw[('final_ic_v1','E3_fisher_cos','hardic+layer',0)]['max_vol']/raw[('final_ic_v1','E3_fisher_cos','hardic',0)]['max_vol']-1)*100
for eq in ['E1_heat','E3_fisher']:
    ms=[group(t,eq,'hardic+layer')['vol_median'] for t in ['sensitivity_tau003_v1','confirm','sensitivity_tau03_v1']]
    ratios[eq+'/tau_max_min']=max(ms)/min(ms)

ic_path=ROOT/'validation/stage5_20261022/ic_validation.json'
stage5=read_json(ROOT/'validation/stage5_analysis_20261022/analysis_evidence.json')
ic=read_json(ic_path)
heldout=defaultdict(list)
for row in ic['results']:
    key=tuple(row['job']); j=raw[key]
    assert row['json_sha256']==manifest['runs/'+key[0]+'/'+key[1]+'/'+key[2].replace('+','_')+'_s'+str(key[3])+'.json']
    for field in ['vol','trace']:
        assert all(abs(a-b)<=1e-9+1e-5*abs(b) for a,b in zip(j['metrics'][field],row['dense_metrics'][field]))
    heldout[key[1:3]].append(row)
table=None
for line,s in enumerate(draft.splitlines(),1):
    if s.startswith('表') and '\u3000' in s: table=s.split('\u3000')[0]
    if table!='表8' or not s.startswith('| E'):continue
    cells=[x.strip() for x in s.strip('|').split('|')]
    if tuple(cells[:2]) not in heldout:continue
    rows=heldout[tuple(cells[:2])]
    for n,field in enumerate(['pde','left_neumann','right_dynamic','initial'],2):
        check('表8',line,field+'_rms_median',cells[n],statistics.median(r['heldout'][field]['rms'] for r in rows))
summary=read_json(ROOT/'validation/stage6_20261022/summary.json')
new_rows=[j for k,j in raw.items() if k[0] in ['sensitivity_tau003_v1','sensitivity_tau03_v1','final_soap64_v1']]
cost_checks={
 'trajectory_seconds_sum':sum(j['wall_seconds'] for j in new_rows),
 'recorded_batch_elapsed_seconds':summary['batch_elapsed_seconds'],
 'recorded_runner_wall_seconds':summary['total_runner_wall_seconds'],
 'lbfgs_iter_range':[min(j['history']['lbfgs_n_iter'] for j in new_rows),max(j['history']['lbfgs_n_iter'] for j in new_rows)],
 'lbfgs_func_evals_range':[min(j['history']['lbfgs_func_evals'] for j in new_rows),max(j['history']['lbfgs_func_evals'] for j in new_rows)],
 'first_stage_config_calls':sorted(set(j['history']['adam_gradient_calls'] for j in new_rows)),
}
assert cost_checks['lbfgs_iter_range']==[1880,3000]
assert cost_checks['lbfgs_func_evals_range']==[3211,3771]
assert abs(cost_checks['trajectory_seconds_sum']-371817.95)<.005
paragraphs=read_json(ROOT/'manuscript/process/complete_v1/paragraph_audit.json')
paragraph_check={'all_segment_text_present':all(p['text'] in draft for p in paragraphs['paragraphs']),
                 'total_segments':len(paragraphs['paragraphs']),
                 'assessed_writer_count':paragraphs['assessed_paragraphs'],
                 'writer_complete_teel_count':paragraphs['full_teel_writer_judgments'],
                 'assessment_note':'Each supplied paragraph was read in the frozen draft; arithmetic/segmentation checked separately from semantic reviewer judgment.'}

refs=read_json(ROOT/'manuscript/process/complete_v1/citation_contexts.json')['references']
source_hashes=[]
for r in refs:
    le=r.get('local_evidence')
    if le and le.get('path') and le.get('sha256'):
        source_hashes.append({'citation':r['citation_number'],'path':le['path'],'sha256':sha(le['path']),'match':sha(le['path'])==le['sha256']})

evidence={
 'review_round':1,
 'packet_sha256':sha(OUT/'input_packet.md'),'draft_sha256':sha(draft_path),
 'draft_embedded_in_packet':draft.strip() in packet,
 'operations':{'training_runs':0,'model_loads':0,'reference_integrations':0,'other_reviewer_reports_read':0},
 'raw_files_checked':len(hash_checks),'raw_json_count':len(raw),'raw_hash_checks':hash_checks,
 'raw_metric_max_checks':max_checks,'table_numeric_checks':table_checks,
 'word_count_method':'Count U+4E00-U+9FFF in six sections, include titles/table captions/notes; exclude Markdown table rows, image lines, figure captions and display equations.',
 'section_counts':counts,'body_count':sum(counts.values()),'section_targets':cfg['section_targets'],
 'saved_recomputation_evidence':validation,
 'new_ic_saved_recomputation':{'count':len(ic['results']),'source_sha256':sha(ic_path),'hash_matches_stage5_analysis':sha(ic_path)==stage5['validation_sha256']['ic_validation.json']},
 'cost_checks':cost_checks,'writer_paragraph_segmentation_check':paragraph_check,
 'key_ratios':ratios,'original_source_hash_checks':source_hashes,
 'source_files':{str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'SCREEN_PROTOCOL.md',ROOT/'pinn1d.py',ROOT/'problems.py',ROOT/'soap_baseline.py',ROOT/'validation/stage6_20261022/results_validation.json',ROOT/'validation/stage6_analysis_20261022/complete_v2/analysis_evidence.json',ROOT/'manuscript/PAPER_CONFIGURATION.json']},
}
(OUT/'evaluator_evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'raw_files':len(hash_checks),'raw_json':len(raw),'hash_mismatches':[x for x in hash_checks if not x['match']],'metric_mismatches':[x for x in max_checks if not(x['vol_match'] and x['trace_match'] and x['all_finite'])],'table_cells':len(table_checks),'table_mismatches':[x for x in table_checks if not x['match']],'counts':counts,'body_count':sum(counts.values()),'validation_rows':len(validation),'validation_mismatches':[x for x in validation if not(x['saved_recomputation_complete'] and x['saved_series_tolerance'] and x['json_hash_match'])],'ratios':ratios,'source_hashes_match':all(x['match'] for x in source_hashes)},ensure_ascii=False,indent=2))

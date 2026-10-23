from pathlib import Path
import json,hashlib,statistics,re,decimal,collections,datetime,csv
R=Path('E:/PINN-PDE/自主研究/当前主线/round33_equation_screen');O=R/'manuscript/integrity/final_revised1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
raw=read(O/'RAW_JSON_INDEPENDENT.json')
groups=collections.defaultdict(list)
for r in raw:
 d=r['data'];d['source']=str(Path(r['path']).relative_to(R)).replace('\\','/');d['sha256']=sha(Path(r['path']))
 assert d['sha256']==r['sha256']
 assert d['metrics']['times']==[.05,.1,.25,.5,1]
 assert max(d['metrics']['vol'])==d['max_vol']
 assert max(d['metrics']['trace'])==d['max_trace']
 groups[d['tag'],d['eq'],d['method']].append(d)
for g in groups.values():g.sort(key=lambda d:d['seed'])
def group(tag,eq,m):
 g=groups[tag,eq,m];return dict(sources=[{'path':d['source'],'sha256':d['sha256']} for d in g],v=[d['max_vol'] for d in g],tr=[d['max_trace'] for d in g],mv=statistics.median(d['max_vol'] for d in g),mt=statistics.median(d['max_trace'] for d in g),success=sum(d['max_vol']<=.01 for d in g),delta=g[0]['delta'],n=len(g))
def ratio(tag,eq,m='hardic',cand='hardic+layer'):return group(tag,eq,m)['mv']/group(tag,eq,cand)['mv']
lines=(R/'manuscript/drafts/delivery_candidate.md').read_text(encoding='utf-8-sig').splitlines();checks=[]
def cells(n):return [s.strip() for s in lines[n-1].strip('|').split('|')]
def check(n,col,actual,sources,display=None):
 shown=cells(n)[col] if display is None else display
 if isinstance(actual,str): ok=shown==actual;tol=None
 else:
  dv=decimal.Decimal(shown);tol=float(decimal.Decimal(10)**dv.as_tuple().exponent/2);ok=abs(float(shown)-actual)<=tol+abs(actual)*1e-14
 checks.append(dict(line=n,column=col,shown=shown,actual=actual,tolerance=tol,passed=ok,sources=sources))
def regular(a,b,tag,eqcolumn=0,mcolumn=1,offset=2,e4=False):
 for n in range(a,b+1):
  c=cells(n);eq='E4_bulk_surface' if e4 else c[eqcolumn];m=c[mcolumn].replace('RBA本地变体','rba');g=group(tag,eq,m)
  for j,v in enumerate(g['v']+[g['mv'],g['mt']]):check(n,offset+j,v,g['sources'])
  check(n,offset+5,f"{g['success']}/3",g['sources'])
regular(284,291,'confirm');regular(305,310,'final_ic_v1');regular(328,331,'pirate')
regular(668,671,'e4confirm',mcolumn=0,offset=1,e4=True)
for n in range(389,401):
 regular(n,n,'confirm' if 'Adam/' in lines[n-1] else 'final_soap64_v1',mcolumn=2,offset=3)
for n in range(345,353):
 eq=cells(n)[0];tag='confirm' if eq in ['E1_heat','E3_fisher'] else 'axis';h=group(tag,eq,'hardic');g=group(tag,eq,'hardic+layer');ss=h['sources']+g['sources']
 for col,val in [(1,g['delta']),(2,h['mv']),(3,g['mv']),(4,h['mv']/g['mv'])]:check(n,col,val,ss)
 check(n,5,f"{g['success']}/3",ss);check(n,6,'满足' if h['mv']/g['mv']>=3 and g['success']>=2 else '不满足',ss)
for n in range(366,372):
 c=cells(n);tag={'.03':'sensitivity_tau003_v1','.1':'confirm','.3':'sensitivity_tau03_v1'}[c[1][1:]];g=group(tag,c[0],'hardic+layer');g0=group('confirm',c[0],'hardic+layer')
 for j,v in enumerate(g['v']+[g['mv']]):check(n,3+j,v,g['sources'])
 ranges=c[7].split('–')
 for shown,val in zip(ranges,[min(g['v']),max(g['v'])]):check(n,7,val,g['sources'],shown)
 check(n,8,g['mv']/g0['mv'],g['sources']+g0['sources'])
for n in range(578,593):
 c=cells(n);g=group('screen',c[0],c[1].replace('RBA本地变体','rba'))
 for j,v in enumerate(g['v']+[g['mv']]+g['tr']+[g['mt']]):check(n,2+j,v,g['sources'])
hist=read(R/'validation/feasibility_review_20261021/existing_data_review.json')
for n in range(600,603):
 eq=cells(n)[0];rr=next(x for x in hist['参考解核验'] if x['方程']==eq);g=group('screen',eq,'vanilla');ss=g['sources'];h=group('screen',eq,'hardic');hh=group('screen',eq,'rba');l=group('screen',eq,'layer');ll=group('screen',eq,'hardic+layer')
 check(n,1,rr['N48与N96最大体差'],['validation/feasibility_review_20261021/existing_data_review.json']);check(n,2,g['mv'],ss);check(n,3,'hardic' if h['mv']<hh['mv'] else 'RBA本地变体',ss);check(n,4,'layer' if l['mv']<ll['mv'] else 'hardic+layer',ss)
 ra=min(h['mv'],hh['mv'])/min(l['mv'],ll['mv']);check(n,5,ra,ss);check(n,6,'是' if ra>=3 and g['mv']>.01 and rr['N48与N96最大体差']<=1e-8 else '否',ss)
v5=read(R/'validation/stage5_20261022/ic_validation.json')['results']
for n in range(416,422):
 c=cells(n);rr=[x for x in v5 if x['job'][1:3]==c[:2]]
 for j,key in enumerate(['pde','left_neumann','right_dynamic','initial']):check(n,2+j,statistics.median(x['heldout'][key]['rms'] for x in rr),['validation/stage5_20261022/ic_validation.json'])
derived={}
for tag,eqs in [('confirm',['E1_heat','E3_fisher']),('final_ic_v1',['E1_heat_cos','E3_fisher_cos']),('pirate',['E1_heat','E3_fisher']),('final_soap64_v1',['E1_heat','E3_fisher'])]:
 for eq in eqs:
  derived[tag+'/'+eq]={'hardic_ratio':ratio(tag,eq),'paired_improved':sum(a>b for a,b in zip(group(tag,eq,'hardic')['v'],group(tag,eq,'hardic+layer')['v']))}
  if (tag,eq,'vanilla') in groups:derived[tag+'/'+eq]['vanilla_ratio']=ratio(tag,eq,'vanilla')
for eq in ['E1_heat','E3_fisher']:
 med=[group(t,eq,'hardic+layer')['mv'] for t in ['sensitivity_tau003_v1','confirm','sensitivity_tau03_v1']]
 derived['tau/'+eq]=dict(max_min_ratio=max(med)/min(med))
 derived['A1/'+eq]=min(group(t,eq,'hardic')['mv'] for t in ['causal1','causal10','pirate'])/group('confirm',eq,'hardic+layer')['mv']
derived['new_E3_seed0_increase_percent']=(group('final_ic_v1','E3_fisher_cos','hardic+layer')['v'][0]/group('final_ic_v1','E3_fisher_cos','hardic')['v'][0]-1)*100
derived['weak_increase_percent']=(1/ratio('axis','E3_k0.1')-1)*100
derived['e4_vanilla_ratio']=ratio('e4confirm','E4_bulk_surface','vanilla')
r0={x['job'][2]:x for x in v5 if x['job'][1]=='E1_heat_cos' and x['job'][3]==0}
derived['new_E1_seed0_right_increase_percent']=(r0['hardic+layer']['heldout']['right_dynamic']['rms']/r0['hardic']['heldout']['right_dynamic']['rms']-1)*100
manifest=read(R/'validation/stage6_analysis_20261022/complete_v2/analysis_evidence.json')['evidence']['raw_sha256']
hashes=[dict(path=p,expected=h,actual=sha(R/p)) for p,h in manifest.items()]
for x in hashes:x['passed']=x['actual']==x['expected']
v6=read(R/'validation/stage6_20261022/completion_archive_20261023/results_validation.json')['results']
recompute=[]
for x in v5+read(R/'validation/stage5_20261022/pirate_validation.json')['results']+v6:
 job=tuple(x['job']);d=next(d for d in groups[job[:3]] if d['seed']==job[3]);z=dict(job=job,json_hash_matches=x.get('json_sha256',x.get('raw_sha256'))==d['sha256'])
 for field in ['metrics','recomputed_N64_GL200','dense_metrics','dense_metrics_N96_GL400']:
  if field in x:
   z[field+'_max_abs_delta']=max(abs(a-b) for typ in ['vol','trace'] for a,b in zip(x[field][typ],d['metrics'][typ]))
 recompute.append(z)
write('NUMERICAL_AUDIT.json',dict(created=datetime.datetime.now().astimezone().isoformat(),draft_sha256=sha(R/'manuscript/drafts/delivery_candidate.md'),method='read-only aggregation; no model evaluation or experiment rerun',raw_count=len(raw),raw_metric_identity_pass=True,cell_checks=checks,failures=[c for c in checks if not c['passed']],derived=derived,recomputed_saved_records=recompute,hashes=hashes,hash_failures=[h for h in hashes if not h['passed']]))
print(json.dumps(dict(cells=len(checks),failures=[c for c in checks if not c['passed']],hash_files=len(hashes),hash_failures=sum(not h['passed'] for h in hashes),derived=derived,recompute_records=len(recompute),recompute_hash_mismatch=[x for x in recompute if not x['json_hash_matches']]),ensure_ascii=False,indent=2))


"""Read-only verification of frozen revision 1a. Writes only beside this script.

No training, model load, reference integration, or edits to author/review inputs.
"""
from pathlib import Path
import collections
import datetime
import difflib
import hashlib
import json
import math
import re
import statistics
import subprocess

OUT = Path(__file__).resolve().parent
MAN = OUT.parents[2]
ROOT = MAN.parent
def read(p):
    return Path(p).read_text(encoding="utf-8-sig")
def js(p):
    return json.loads(read(p))
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name, obj):
    (OUT/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

oldp = MAN/'drafts/complete_v1.md'
newp = MAN/'drafts/complete_revised1a.md'
old, new = read(oldp), read(newp)
assert sha(newp) == '398c2a44f2f9fd959b62564ddc599b123a3dd5de168ad0257a8572e188bf92e8'
tracker = js(MAN/'reviews/revision1/REVIEW_ITEMS.json')
response = js(MAN/'process/complete_revised1a/RESPONSE_TO_REVIEWS.json')
frozen = js(MAN/'process/complete_revised1a/FROZEN_LAYOUT_MANIFEST.json')
checks = []
for group, mapping in [
    ('revision1a_frozen', frozen['files']),
    ('revision1a_protected', js(MAN/'process/complete_revised1a/protected_before.json')),
    ('revision1_protected', js(MAN/'process/complete_revised1/protected_before.json')),
    ('original_review_inputs', {r['文件']: r['SHA256'] for r in tracker['输入清单']}),
    ('author_source_bindings', js(MAN/'process/complete_revised1/source_evidence.json')['sources'])]:
    for name, expected in mapping.items():
        got = sha(name)
        checks.append(dict(group=group, path=name, expected=expected, actual=got, matches=(got==expected)))
assert all(x['matches'] for x in checks)
assert response['draft_sha256'] == sha(newp)
assert response['tracker_sha256'] == sha(MAN/'reviews/revision1/REVIEW_ITEMS.json')
assert [x['编号'] for x in response['responses']] == [x['编号'] for x in tracker['修订条目']]
location_checks=[]
for r in response['responses']:
    locs=r['实际修订位置']
    if isinstance(locs,dict): locs=[locs]
    for loc in locs:
        if loc.get('line') is not None:
            p=Path(loc['file']); line=read(p).splitlines()[loc['line']-1]
            location_checks.append(dict(id=r['编号'],file=str(p),line=loc['line'],anchor=loc['exact_anchor'],matches=loc['exact_anchor'] in line,sha_matches=sha(p)==loc['sha256']))
assert all(x['matches'] and x['sha_matches'] for x in location_checks)

# Independently enumerate the raw-result folders; do not take author aggregate values.
raw=[]
for tag, equations in [('e4screen',['E4_bulk_surface']),('e4confirm',['E4_bulk_surface']),('pirate',['E1_heat','E3_fisher'])]:
    for eq in equations:
        for p in sorted((ROOT/'runs'/tag/eq).glob('*.json')):
            j=js(p)
            if tag=='pirate' and j['method'] not in ['hardic','hardic+layer']: continue
            m=j['metrics']
            assert m['times']==[0.05,0.1,0.25,0.5,1.0]
            assert len(m['vol'])==len(m['trace'])==5
            assert all(math.isfinite(x) for x in m['vol']+m['trace'])
            assert max(m['vol'])==j['max_vol'] and max(m['trace'])==j['max_trace']
            raw.append(dict(source=p.relative_to(ROOT).as_posix(),sha256=sha(p),tag=tag,eq=eq,method=j['method'],seed=j['seed'],metrics={k:m[k] for k in ['times','vol','trace']},max_vol=max(m['vol']),max_trace=max(m['trace']),config=j['config'],env=j.get('env'),resumed_at=j.get('history',{}).get('resumed_at',[]),delta=j['delta']))
assert len(raw)==32 and collections.Counter(r['tag'] for r in raw)=={'e4screen':8,'e4confirm':12,'pirate':12}
author_raw={r['source']:r for r in js(MAN/'process/complete_revised1/source_evidence.json')['targeted_raw_records']}
raw_matches=[]
for r in raw:
    ar=author_raw[r['source']]
    same=all(r[k]==ar[k] for k in ['sha256','tag','eq','method','seed','metrics','max_vol','max_trace','config','env','resumed_at','delta'])
    raw_matches.append(dict(source=r['source'],matches=same))
assert all(r['matches'] for r in raw_matches)
groups=[]
for key in sorted({(r['tag'],r['eq'],r['method']) for r in raw}):
    rows=sorted([r for r in raw if (r['tag'],r['eq'],r['method'])==key],key=lambda r:r['seed'])
    groups.append(dict(tag=key[0],eq=key[1],method=key[2],seeds=[r['seed'] for r in rows],body=[r['max_vol'] for r in rows],trace=[r['max_trace'] for r in rows],median_body=statistics.median(r['max_vol'] for r in rows),median_trace=statistics.median(r['max_trace'] for r in rows),under_1e2=sum(r['max_vol']<=0.01 for r in rows),sources=[r['source'] for r in rows]))
def grp(tag,eq,method): return next(g for g in groups if (g['tag'],g['eq'],g['method'])==(tag,eq,method))
e4ratio=grp('e4confirm','E4_bulk_surface','vanilla')['median_body']/grp('e4confirm','E4_bulk_surface','hardic+layer')['median_body']
e4screenratio=min(grp('e4screen','E4_bulk_surface',m)['median_body'] for m in ['hardic','rba'])/grp('e4screen','E4_bulk_surface','hardic+layer')['median_body']
e4explore=min(grp('e4confirm','E4_bulk_surface',m)['median_body'] for m in ['hardic','rba'])/grp('e4confirm','E4_bulk_surface','hardic+layer')['median_body']
pirateratios={eq:grp('pirate',eq,'hardic')['median_body']/grp('pirate',eq,'hardic+layer')['median_body'] for eq in ['E1_heat','E3_fisher']}
table_checks=[]
for g in groups:
    if g['tag']!='e4confirm':continue
    label='RBA本地变体' if g['method']=='rba' else g['method']
    expected='| '+label+' | '+' | '.join(f'{v:.5e}' for v in g['body']+[g['median_body'],g['median_trace']])+f" | {g['under_1e2']}/3 |"
    table_checks.append(dict(method=g['method'],expected_line=expected,present=expected in new))
assert all(r['present'] for r in table_checks)
assert f'{e4ratio:.12f}' in new
assert all(f'{r:.2f}' in new for r in pirateratios.values())

# Rebuild the published count from text, distinguishing captions from prose beginning with a table number.
configp=MAN/'PAPER_CONFIGURATION.json'
config=js(configp)
def count(text, variant):
    data={k:0 for k in config['section_targets']}; current=None; display=False
    exclusions=[]
    for n,line in enumerate(text.splitlines(),1):
        s=line.strip()
        if s.startswith('## '):
            name=s[3:]
            current=name if name in data else None
        if current is None: continue
        if s==r'\[': display=True
        in_display=display
        if s==r'\]': display=False
        reason=None
        if in_display: reason='display_math'
        elif s.startswith('|'): reason='table_data'
        elif s.startswith('!['): reason='image'
        elif re.match(r'^图\d+[\s\u3000]',s): reason='figure_caption'
        elif variant=='without_table_captions_notes' and re.match(r'^表\d+(?:[\s\u3000]|注[:：])',s): reason='table_caption_or_note'
        elif variant=='all_table_prefix_and_chapter_titles' and (re.match(r'^表\d+',s) or s.startswith('## ')): reason='all_table_prefix_or_chapter_title'
        if reason:
            exclusions.append(dict(line=n,reason=reason,cjk=len(re.findall('[\u4e00-\u9fff]',line))))
            continue
        data[current]+=len(re.findall('[\u4e00-\u9fff]',line))
    return dict(total=sum(data.values()),sections=data,exclusions=exclusions)
counts={name:{mode:count(text,mode) for mode in ['published','without_table_captions_notes','all_table_prefix_and_chapter_titles']} for name,text in [('complete_v1',old),('complete_revised1a',new)]}
published=counts['complete_revised1a']['published']
assert published['total']==11487
assert published['sections']=={k:v['actual_cjk'] for k,v in js(MAN/'process/complete_revised1a/word_counts.json')['sections'].items()}
quotas={k:dict(actual=published['sections'][k],target=v,relative_deviation=published['sections'][k]/v-1,within_tolerance=abs(published['sections'][k]/v-1)<=config['section_tolerance']) for k,v in config['section_targets'].items()}
assert all(x['within_tolerance'] for x in quotas.values())
assert abs(published['total']/config['target_body_cjk_characters']-1)<=config['total_tolerance']
gitpath=configp.relative_to(Path('E:/PINN-PDE')).as_posix()
commit='46855c4b80ab4e7e9620c916b327cde9af9b5191'
prior_config=subprocess.run(['git','show',f'{commit}:{gitpath}'],cwd='E:/PINN-PDE',capture_output=True,check=True).stdout
assert json.loads(prior_config)==config

oldlines,newlines=old.splitlines(),new.splitlines()
hunks=[]
for i,(tag,a0,a1,b0,b1) in enumerate(difflib.SequenceMatcher(None,oldlines,newlines).get_opcodes()):
    if tag=='equal':continue
    hunks.append(dict(id=f'H{i}',kind=tag,old_lines=[a0+1,a1],new_lines=[b0+1,b1],old_text='\n'.join(oldlines[a0:a1]),new_text='\n'.join(newlines[b0:b1])))
save('change_hunks.json',hunks)
assert len(hunks)==22
assert re.findall(r'!\[[^\]]*\]\([^\n]+\)',old)==re.findall(r'!\[[^\]]*\]\([^\n]+\)',new)
oldrefs=old.split('## 参考文献')[1].split('题录与阅读版本')[0]
newrefs=new.split('## 参考文献')[1].split('题录与阅读版本')[0]
assert oldrefs==newrefs
oldrows=[s for s in old.splitlines() if s.startswith('|') and not s.startswith(('| E09 |','| E14 |'))]
newrows=new.splitlines()
assert all(s in newrows for s in oldrows)
assert 'N04' not in new
figure_checks=[]
for item in js(MAN/'process/complete_revised1a/figure_retention_checks.json')['figures']:
    figure_checks.append(dict(path=item['path'],sha256=sha(item['path']),matches=sha(item['path'])==item['sha256']))
assert all(r['matches'] for r in figure_checks)
save('raw32_reaggregation.json',dict(records=raw,groups=groups,author_record_matches=raw_matches,e4_vanilla_over_corrected=e4ratio,e4_screen_hardic_rba_over_corrected=e4screenratio,e4_confirm_hardic_rba_over_corrected=e4explore,pirate_hardic_over_corrected=pirateratios,e4_table_checks=table_checks))
save('independent_counts.json',dict(config_sha256=sha(configp),prior_git_commit=commit,prior_git_config_semantically_identical=True,counts=counts,quotas=quotas,total_deviation=published['total']/11000-1))
save('input_integrity.json',dict(checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),draft=str(newp),draft_sha256=sha(newp),original_sha256=sha(oldp),tracker_sha256=sha(MAN/'reviews/revision1/REVIEW_ITEMS.json'),response_sha256=sha(MAN/'process/complete_revised1a/RESPONSE_TO_REVIEWS.json'),freeze_manifest_sha256=sha(MAN/'process/complete_revised1a/FROZEN_LAYOUT_MANIFEST.json'),bindings=checks,author_locations=location_checks,figures=figure_checks,original_table_rows_preserved=len(oldrows),references_unchanged=True,change_hunks=len(hunks),new_or_replaced_lines=sum(h['new_lines'][1]-h['new_lines'][0]+1 for h in hunks),operations=dict(training=0,model_load=0,reference_integration=0,torch_import=0,git_mutation=0)))
print(json.dumps(dict(binding_checks=len(checks),all_bindings_match=True,author_locations=len(location_checks),raw_records=len(raw),e4_ratio=e4ratio,e4_screen_ratio=e4screenratio,e4_exploratory_ratio=e4explore,pirate_ratios=pirateratios,counts={k:{m:v['total'] for m,v in d.items()} for k,d in counts.items()},quotas=quotas,hunks=len(hunks),new_or_replaced_lines=sum(h['new_lines'][1]-h['new_lines'][0]+1 for h in hunks)),ensure_ascii=False,indent=2))

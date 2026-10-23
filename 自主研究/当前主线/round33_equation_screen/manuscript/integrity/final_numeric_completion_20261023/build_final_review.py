from pathlib import Path
import json,hashlib,datetime,difflib,re,collections,sys

R=Path('E:/PINN-PDE/自主研究/当前主线/round33_equation_screen')
O=R/'manuscript/integrity/final_numeric_completion_20261023'
F=R/'manuscript/integrity/final_revised1'
P=R/'validation/final_numeric_provenance_20261023'
D=Path(sys.argv[1])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
now=datetime.datetime.now().astimezone().isoformat()
oldp=R/'manuscript/drafts/delivery_candidate.md'; c2=R/'manuscript/drafts/delivery_candidate2.md'
oldlines=oldp.read_text(encoding='utf-8-sig').splitlines();lines=D.read_text(encoding='utf-8-sig').splitlines()
assert sha(oldp)=='aef0c10a1bf19e8703a8066e1f0aaef75600b886777424b9f6545677ccc77eb0'
assert sha(c2)=='59d1db8fd5c8c468783e98ba6db1bcde0e49e7f923e82afa6e2d9e6dbf383cd4'
assert '12个方程、参数或初值配置的参考解均新计算N48、N64与N96' in '\n'.join(lines)
assert '12种方程的参考解' not in '\n'.join(lines)
ops=list(difflib.SequenceMatcher(a=oldlines,b=lines,autojunk=False).get_opcodes())
oldmap={i+n+1:k+n+1 for t,i,j,k,l in ops if t=='equal' for n in range(j-i)}
newmap={v:k for k,v in oldmap.items()}
changes=[dict(tag=t,old_start=i+1,old_end=j,new_start=k+1,new_end=l,old_lines=oldlines[i:j],new_lines=lines[k:l]) for t,i,j,k,l in ops if t!='equal']
changed=[{'id':f'D{z+1:02}','line':n,'text':t} for z,(n,t) in enumerate((n,t) for c in changes for n,t in enumerate(c['new_lines'],c['new_start']) if t.strip())]
assert len(changed)==11
write('FINAL_CANDIDATE_BINDING.json',dict(created=now,old_sha256=sha(oldp),candidate2_sha256=sha(c2),final_path=str(D),final_sha256=sha(D),old_lines=len(oldlines),final_lines=len(lines),changes=changes))
(O/'FINAL_CANDIDATE_INDEPENDENT_DIFF.patch').write_text('\n'.join(difflib.unified_diff(oldlines,lines,fromfile=oldp.name,tofile=D.name,lineterm=''))+'\n',encoding='utf-8')
write('RESOLVED_SCOPE_WORDING.json',dict(issue='12种方程 may imply 12 distinct PDE types; actual twelve keys include parameter and initial-condition variants',found_in=str(c2),found_sha256=sha(c2),found_line=630,actual_reference_keys=sorted(set(j['eq'] for j in read(P/'plan.json')['jobs'])),correction='12个方程、参数或初值配置',resolved_in=str(D),resolved_sha256=sha(D),status='RESOLVED'))

# All changed prose, including mapping/link-only changes outside the prose denominator,
# was queried. Search pools are not misrepresented as independently ranked per query.
queryplan=read(O/'D1_INCREMENT_QUERY_PLAN.json');raw=read(O/'D1_INCREMENT_SEARCH_RAW.json');refined=read(O/'D1_INCREMENT_REFINED_RAW.json')
orig_records=[]
for p in queryplan:
    batch=next(b['value'] for b in raw if p['id'] in b['value']['paragraphs'])
    blocks=[z.strip() for z in batch['response'].split('--------------------------------------------------------------------------------') if z.strip()][:10]
    comp=[]
    for z in blocks:
        m=difflib.SequenceMatcher(a=p['fragment'],b=z,autojunk=False).find_longest_match()
        u=re.search(r'\((https?://[^\s)]+)\)',z)
        comp.append(dict(title_and_url=z.splitlines()[0],url=u.group(1) if u else None,longest_literal_overlap=p['fragment'][m.a:m.a+m.size],overlap_length=m.size))
    rq=[q for q in refined['queries'] if q['id']==p['id']]
    extra=[]
    if rq:
        for z in [z.strip() for z in refined['response'].split('--------------------------------------------------------------------------------') if z.strip()][:10]:
            m=difflib.SequenceMatcher(a=p['fragment'],b=z,autojunk=False).find_longest_match();u=re.search(r'\((https?://[^\s)]+)\)',z)
            extra.append(dict(title_and_url=z.splitlines()[0],url=u.group(1) if u else None,longest_literal_overlap=p['fragment'][m.a:m.a+m.size],overlap_length=m.size))
    orig_records.append(dict(id=p['id'],line=p['line'],text=next(c['text'] for c in changed if c['id']==p['id']),fragment=p['fragment'],queries=[q for q in batch['queries'] if q['id']==p['id']],query_time=batch['timestamp'],pool_scope='top up to 10 returned blocks from a two-paragraph/four-query pool; not per-query ranking',comparisons=comp,refined_queries=rq,refined_comparisons=extra,exact_fragment_found=p['fragment'] in batch['response'],verdict='PARAPHRASE_WITH_ATTRIBUTION' if p['id']=='D02' else 'NO_UNATTRIBUTED_CLOSE_MATCH_FOUND',manual_assessment='Own run-specific scope, numbers and chronology; returned shared terms are generic technical/numeric tokens or unrelated matches. D02 is an attributed reference/version description, unchanged except internal path. Public search is heuristic, not proof of absence.'))
base_inventory=read(F/'INVENTORY.json');selected={p['text'] for p in base_inventory['paragraphs'] if p['selected_originality']};v1=(R/'manuscript/drafts/complete_v1.md').read_text(encoding='utf-8-sig')
paras=[];section='';inmath=False
for n,s in enumerate(lines,1):
    if s.startswith('#'):section=s.lstrip('# ').strip();continue
    if s=='\\[':inmath=True;continue
    if s=='\\]':inmath=False;continue
    if not s.strip() or inmath or s.startswith(('|','![')) or re.match(r'^\[\d+\]',s) or section.startswith(('参考文献','数据与论据')) or n in (3,5,11,17) or s.startswith(('关键词','Keywords')) or len(s)<21:continue
    paras.append(dict(line=n,text=s,section=section,changed_from_complete_v1=s not in v1,changed_in_supplement=n not in newmap,checked=s in selected or n not in newmap))
assert all(p['checked'] for p in paras if p['changed_from_complete_v1'])
write('ORIGINALITY_SUPPLEMENT.json',dict(created=now,draft_sha256=sha(D),body_paragraphs=len(paras),checked=sum(p['checked'] for p in paras),checked_percent=100*sum(p['checked'] for p in paras)/len(paras),changed_from_complete_v1=sum(p['changed_from_complete_v1'] for p in paras),changed_checked=sum(p['checked'] and p['changed_from_complete_v1'] for p in paras),new_or_modified_prose_in_denominator=sum(p['changed_in_supplement'] for p in paras),all_changed_units_including_maps_and_links=len(changed),increment_queries=sum(len(b['value']['queries']) for b in raw)+len(refined['queries']),total_session_queries=154+sum(len(b['value']['queries']) for b in raw)+len(refined['queries']),records=orig_records,paragraphs=paras,limitations=['Public web search is heuristic and has Chinese/cross-language and unindexed/paywall blind spots.','No Turnitin/iThenticate certificate.','D2 author self-overlap check remains NOT_RUN because author identity has not been supplied.','Several generic queries returned off-topic results; four scoped supplementary queries were actually executed and retained.']))

manual={
'D01':('Current 206/52 scope and chronology: full fresh reload followed prior JSON-only aggregation; historical 176=130+24+22 and 398+90=488 remain verified. Current scripts do not rerun training or supply E4 surface weights.',['ACTUAL_RUN_INDEPENDENT_AUDIT.json','../final_revised1/SUPPLEMENT_AUDIT.json']),
'D02':('Only the local citation-context link changes; 13 external references and 18 citation occurrences remain byte-identical and retain their fresh source/context audit. New linked file must match the frozen package.',['../final_revised1/REFERENCE_AND_CONTEXT_AUDIT.json','PROCESS_AND_LINK_CHECK.json']),
'D03':('Temporal wording correctly attributes the 398-file hash-only historical check to its earlier review, not the new reloading run.',['../working_20261023/historical_execution_scope.json','../final_revised1/SUPPLEMENT_AUDIT.json']),
'D04':('E18 links the actual 206 body/trace plus 52 heldout execution archive and its verified 2300-file manifest; no old training logs reconstructed.',['FINAL_NUMERIC_MANIFEST_CHECK.json','ACTUAL_RUN_INDEPENDENT_AUDIT.json']),
'D05':('206 raw JSON hashes match; first aggregation and subsequent numerical reloading are separately archived and neither is training. Original reports, evidence and tables preserved.',['FIRST_AUDIT_PRESERVATION.json','ACTUAL_RUN_INDEPENDENT_AUDIT.json','FINAL_CANDIDATE_BINDING.json']),
'D06':('Earlier 130+24+22/398 records, missing historical exits, two 63/71 test logs with one warning each, old source hash differences and 20 missing E4 surface branches remain factual and explicitly limited.',['../final_revised1/SUPPLEMENT_AUDIT.json','../final_revised1/SOURCE_VERSION_AUDIT.json','ACTUAL_RUN_INDEPENDENT_AUDIT.json']),
'D07':('Only chronology changes: previous stage6 analysis aggregated saved reports; new reloading is E18. Three CSVs, 30 new/36 default/18 tau rows with six shared defaults and 48 unique analysis records remain hash-bound and independently checked.',['../final_revised1/SUPPLEMENT_AUDIT.json','FIRST_AUDIT_PRESERVATION.json']),
'D08':('Independent recalculation from all model/reference NPZ arrays verifies 206*2*5*2=4120 comparisons at unchanged rtol1e-5/atol1e-9. Maxima round correctly. Twelve keys are problem/parameter/initial-condition configurations, not twelve distinct PDE classes; 12*401*5 reference self-checks meet1e-8.',['ACTUAL_RUN_INDEPENDENT_AUDIT.json','RESOLVED_SCOPE_WORDING.json']),
'D09':('Original reports define 4+18+30=52 unique heldout models and 52*4*2=416 scalar aggregates; independently reconstructed RNG arrays exactly match saved evaluation points; all RMS/max_abs differences are zero. 270 child and two supervisor actual exits0, warnings0, empty stderr; all488 original files and reviewed code unchanged. Times351.9388094/89.8463016 round as shown and refer to validation batch computation.',['ACTUAL_RUN_INDEPENDENT_AUDIT.json','../../../validation/final_numeric_provenance_20261023/heldout_plan.json']),
'D10':('Actual strict reload statuses count110 legacy complete,20 legacy bulk-only,76 complete; E4 missing surf is deleted and excluded,52 heldout models contain no E4. Frozen model/reference code is reused with independently reviewed new checking/aggregation, not a separate solver. No historical training process evidence is reconstructed.',['ACTUAL_RUN_INDEPENDENT_AUDIT.json','RELOAD_STATUS_COUNTS.json','../final_numeric_source_review_20261023/SOURCE_REVIEW_CN.md','../final_numeric_source_review_20261023/HELDOUT_SOURCE_REVIEW_CN.md']),
'D11':('Original E4 failure criterion and adverse vanilla ratio remain unchanged; fresh E18 loads the20 saved bulk branches only and does not validate absent v(t) or early-time full-solution asymptotics.',['ACTUAL_RUN_INDEPENDENT_AUDIT.json','../final_revised1/NUMERICAL_AUDIT.json','FINAL_CANDIDATE_BINDING.json'])}
write('CHANGED_CLAIMS_AUDIT.json',dict(created=now,draft_sha256=sha(D),records=[{**c,'verdict':'VERIFIED','detail':manual[c['id']][0],'verification_sources':manual[c['id']][1]} for c in changed]))

# Preserve every unchanged claim and update every changed line, including non-prose table/mapping material.
base=read(F/'CLAIM_REGISTRY.json');registry=[]
for q in base['registry']:
    if all(n in oldmap for n in range(q['line'],q['end_line']+1)):
        nq=dict(q);nq['line']=oldmap[q['line']];nq['end_line']=oldmap[q['end_line']]
        nq['reused_from']='../final_revised1/CLAIM_REGISTRY.json#'+q['id'];nq['original_verification_sources']=q['verification_sources'];nq['verification_sources']=[nq['reused_from'],'FIRST_AUDIT_PRESERVATION.json'];registry.append(nq)
for c in changed:
    text=c['text'];isrow=text.startswith('|');clean=re.sub(r'\[(?:E\d+(?:,E\d+)*|\d+(?:[,–—-]\d+)*)\]','',text)
    sentences=[text] if isrow else [s.strip() for s in re.split(r'(?<=[。！？])',clean) if s.strip()]
    section=next((s.lstrip('# ').strip() for s in reversed(lines[:c['line']]) if s.startswith('#')),'')
    for sentence in sentences:
        registry.append(dict(id='',line=c['line'],end_line=c['line'],section=section,type='table_row' if isrow else 'prose_sentence',claim=sentence,cited_external_refs=[],cited_evidence=sorted(set(re.findall(r'E\d+',text))),verification_sources=manual[c['id']][1],verdict='VERIFIED',detail=manual[c['id']][0],evidence_level='source_and_actual_execution_checked',increment_id=c['id']))
registry.sort(key=lambda q:q['line'])
for i,q in enumerate(registry,1):q['id']=f'F{i:04}'
cover=[];oldcoverage={c['line']:c for c in base['line_coverage']}
for n,t in enumerate(lines,1):
    ids=[q['id'] for q in registry if q['line']<=n<=q['end_line']]
    if ids:cover.append(dict(line=n,classification='claim',claim_ids=ids))
    elif n in newmap:
        cc=dict(oldcoverage[newmap[n]]);cc['line']=n;cc.pop('claim_ids',None);cover.append(cc)
    elif not t.strip():cover.append(dict(line=n,classification='blank'))
    elif t.startswith('#'):cover.append(dict(line=n,classification='heading'))
    else:raise AssertionError(('unclassified',n,t))
counts=dict(collections.Counter(q['verdict'] for q in registry))
write('FINAL_CLAIM_REGISTRY.json',dict(created=now,draft_sha256=sha(D),coverage_method='All final lines and each unchanged prior claim carried by exact line mapping; every changed prose sentence and evidence table row independently checked; references, numeric cells and formula blocks retain their hash-stable independent audits.',counts=counts,registry=registry,line_coverage=cover,claim_count=len(registry),line_count=len(lines)))
(O/'FINAL_CLAIM_REGISTRY.md').write_text('# 最终候选稿全量声明映射\n\n全部'+str(len(lines))+'行已分类，'+str(len(registry))+'登记单元；未变声明逐字映射首轮独立证据，新增及修改声明见专项检查。\n\n| ID | 行 | 状态 | 声明 | 来源与边界 |\n|---|---:|---|---|---|\n'+'\n'.join('| '+q['id']+' | '+str(q['line'])+' | '+q['verdict']+' | '+q['claim'].replace('|','\\|').replace('\n',' ')+' | '+q['detail'].replace('|','\\|').replace('\n',' ')+' |' for q in registry)+'\n',encoding='utf-8')
print(json.dumps(dict(final_sha256=sha(D),final_lines=len(lines),claim_count=len(registry),claim_counts=counts,originality_checked=sum(p['checked'] for p in paras),paragraphs=len(paras),changed_from_v1=sum(p['changed_from_complete_v1'] for p in paras)),ensure_ascii=False))

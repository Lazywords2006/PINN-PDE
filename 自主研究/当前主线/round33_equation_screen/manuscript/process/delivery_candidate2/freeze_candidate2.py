from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib,json
OUT=Path(__file__).resolve().parent
MAN=OUT.parents[1]
DRAFT=MAN/'drafts/delivery_candidate2.md'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
readj=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def save(n,o):(OUT/n).write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not (OUT/'FROZEN_CANDIDATE2_MANIFEST.json').exists()
h=sha(DRAFT)
assert h=='59d1db8fd5c8c468783e98ba6db1bcde0e49e7f923e82afa6e2d9e6dbf383cd4'
bound=['change_map.json','word_counts.json','citation_contexts.json','figure_retention_checks.json',
       'numeric_evidence_checks.json','prior_25_items_location_bridge.json','RESPONSES_TO_FINAL_PROVENANCE.json','source_checks.json','candidate2_checks.json']
for n in bound:assert readj(OUT/n)['draft_sha256']==h,n
for p,v in readj(OUT/'protected_before.json').items():assert sha(Path(p))==v,p
for p,v in readj(OUT/'source_checks.json')['source_sha256'].items():assert sha(Path(p))==v,p
for group in readj(OUT/'prior_25_items_location_bridge.json')['items']:
    for loc in group['current_locations']:
        p=Path(loc['file']);assert sha(p)==loc['sha256']
        if 'exact_anchor' in loc:assert loc['exact_anchor'] in p.read_text(encoding='utf-8').splitlines()[loc['line']-1]
for item in readj(OUT/'RESPONSES_TO_FINAL_PROVENANCE.json')['items']:
    for loc in item['locations']:assert loc['exact_anchor'] in DRAFT.read_text(encoding='utf-8').splitlines()[loc['line']-1]
c=readj(OUT/'candidate2_checks.json');c['final_frozen']=True;save('candidate2_checks.json',c)
save('final_binding_checks.json',{'draft_sha256':h,'bound_json_files':bound,'all_binding_checks_pass':True,
    'body_cjk':11510,'protected_old_files':58,'final_integrity_not_preclaimed':True,
    'freeze_scope':'冻结本候选与作者过程证据，最终独立增量核验和排版另行记录。'})
files={str(DRAFT):sha(DRAFT)}
files.update({str(p):sha(p) for p in sorted(OUT.iterdir()) if p.is_file()})
save('FROZEN_CANDIDATE2_MANIFEST.json',{'created_local':datetime.now(timezone(timedelta(hours=8))).isoformat(),
    'draft_sha256':h,'file_count':len(files),'files':files,'manifest_excludes_itself':True,
    'final_integrity_status':'PENDING_INDEPENDENT_INCREMENTAL_REVIEW',
    'read_only_future_policy':'后续修订必须另存，不覆盖此候选或过程清单。'})
assert all(sha(Path(p))==v for p,v in files.items())
print(json.dumps({'draft_sha256':h,'manifest_sha256':sha(OUT/'FROZEN_CANDIDATE2_MANIFEST.json'),'file_count':len(files)}))

"""复用候选稿2仍有效的检查，绑定唯一术语修订及附件链接后冻结。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import copy,hashlib,json,re
OUT=Path(__file__).resolve().parent
MAN=OUT.parents[1]
OLD=MAN/'process/delivery_candidate2'
BASE=MAN/'drafts/delivery_candidate2.md'
DRAFT=MAN/'drafts/delivery_candidate2a.md'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
readj=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def save(n,o):(OUT/n).write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not (OUT/'FROZEN_CANDIDATE2A_MANIFEST.json').exists()
h=sha(DRAFT);bh=sha(BASE)
assert h=='741b88925f6248050c9de3f5fa590f2abf8a8496f4194dd6c35990038a3343ce'
assert bh=='59d1db8fd5c8c468783e98ba6db1bcde0e49e7f923e82afa6e2d9e6dbf383cd4'
b,t=[p.read_text(encoding='utf-8') for p in (BASE,DRAFT)]
changes=readj(OUT/'change_map.json')['changes']
back=t
for x in reversed(changes):back=back.replace(x['new'],x['old'])
assert back==b
body=lambda s:s.split('## 1 引言与相关工作',1)[1].split('## 参考文献',1)[0]
assert body(b)==body(t)
tables=lambda s:re.findall(r'(?:^\|.*\n)+',s,re.M)
assert tables(b)==tables(t) and len(tables(t))==14
formula=lambda s:re.findall(r'\\\[.*?\\\]',s,re.S)
assert formula(b)==formula(t)
assert re.findall(r'^\[\d+\].+$',b,re.M)==re.findall(r'^\[\d+\].+$',t,re.M)
assert len(t.splitlines())==len(b.splitlines())

def inherit(name):
    obj=readj(OLD/name)
    assert obj['draft_sha256']==bh
    obj['candidate2_parent_sha256']=bh
    obj['draft_sha256']=h
    return obj
counts=inherit('word_counts.json')
counts['prior_count_base_sha256']=counts['base_sha256'];counts['base_sha256']=bh
counts['base_sections']=copy.deepcopy(counts['sections'])
counts['derivation_note']='候选稿2a六章正文逐字相同，原11,510及逐章计数直接复用；唯一术语改动在附录D。'
assert counts['actual_body_cjk']==11510
save('word_counts.json',counts)
word=(OLD/'WORD_COUNTS_CN.md').read_text(encoding='utf-8').replace('候选稿2','候选稿2a').replace(bh,h)
word += '\n候选稿2a与候选稿2的六章正文逐字相同。上表父候选计数仍保留最初delivery_candidate.md的比较；本次2→2a正文差值为0，附录术语与附件链接不计正文。\n'
(OUT/'WORD_COUNTS_CN.md').write_text(word,encoding='utf-8')

c=inherit('citation_contexts.json');c['parent_sha256']=bh
for row in c['contexts']:assert row['paragraph']==t.splitlines()[row['line']-1]
for row in c['data_evidence_contexts']:
    old=row['paragraph'];new=old
    for x in changes:new=new.replace(x['old'],x['new'])
    assert new==t.splitlines()[row['line']-1]
    row['paragraph']=new
c['derivation_note']='原18处外部引用不变；E18附录D配置计数术语同步更新。'
save('citation_contexts.json',c)
cm=(OLD/'citation_contexts.md').read_text(encoding='utf-8').replace('候选稿2引用上下文','候选稿2a引用上下文').replace(bh,h)
for x in changes:cm=cm.replace(x['old'],x['new'])
(OUT/'citation_contexts.md').write_text(cm,encoding='utf-8')
fig=inherit('figure_retention_checks.json');fig['parent_sha256']=bh
for row in fig['figures']:assert sha(Path(row['path']))==row['sha256']
save('figure_retention_checks.json',fig)

num=inherit('numeric_evidence_checks.json')
num['derivation_note']='候选稿2的4536项只读比较、270子进程及2父进程核对结果直接复用；本版数值、图表和公式逐字未变。'
num['all_fourteen_table_blocks_unchanged_from_candidate2']=True
num['only_changed_table_block_from_candidate2']=None
save('numeric_evidence_checks.json',num)

def rebind_locations(locations):
    for loc in locations:
        if Path(loc['file'])==BASE:
            loc['file']=str(DRAFT);loc['sha256']=h
            assert loc['exact_anchor'] in t.splitlines()[loc['line']-1]
        else:assert sha(Path(loc['file']))==loc['sha256']
bridges=inherit('prior_25_items_location_bridge.json')
for item in bridges['items']:rebind_locations(item['current_locations'])
save('prior_25_items_location_bridge.json',bridges)
resp=inherit('RESPONSES_TO_FINAL_PROVENANCE.json')
resp['base_sha256']=bh
for item in resp['items']:rebind_locations(item['locations'])
resp['terminology_response']={
    'id':'TERMINOLOGY-01','instruction_source':'父代理转达独立最终核验者的唯一正文修项；其余新增段落未要求修改。',
    'old_text':changes[0]['old'],'new_text':changes[0]['new'],
    'reason':'12对应方程、参数或初值配置，避免读作12类不同方程。',
    'line':630,'draft_sha256':h,
    'binding_link_update':{'line':503,'reason':'仅同步本稿引用附件路径。'},
    'status':'AUTHOR_ADDRESSED_AWAITING_INDEPENDENT_FINAL_RECHECK'}
save('RESPONSES_TO_FINAL_PROVENANCE.json',resp)
rm=(OLD/'RESPONSES_TO_FINAL_PROVENANCE_CN.md').read_text(encoding='utf-8')
rm=rm.replace(DRAFT.with_name('delivery_candidate2.md').as_posix(),DRAFT.as_posix()).replace(bh,h)
rm=rm.replace('[delivery_candidate2.md]','[delivery_candidate2a.md]').replace('候选稿2','候选稿2a')
rm += f'''\n## 独立最终核验的唯一术语修项

第630行已将“{changes[0]['old']}”改为“{changes[0]['new']}”，精确表示12个参考问题配置，不改变N值、误差或任何科学判据。第503行仅同步引用附件链接。父候选稿2及其21文件冻结清单完整保留，父稿SHA256为`{bh}`。将两处替换逆向恢复后，全文与父稿一致；六章正文、14个表块、所有显示公式、13条题录及4幅图均原样保留。本稿最终核验结论仍由独立核验者给出。
'''
(OUT/'RESPONSES_TO_FINAL_PROVENANCE_CN.md').write_text(rm,encoding='utf-8')

source=inherit('source_checks.json')
for p,v in source['source_sha256'].items():assert sha(Path(p))==v
source['candidate2_frozen_manifest']={'file':str(OLD/'FROZEN_CANDIDATE2_MANIFEST.json'),'sha256':sha(OLD/'FROZEN_CANDIDATE2_MANIFEST.json')}
source['derivation_note']='本轮未重跑前轮统计核对；逐字同一的科学内容复用已冻检查，只核来源当前身份及派生绑定。'
save('source_checks.json',source)
protected=readj(OUT/'protected_before.json')
assert all(sha(Path(p))==v for p,v in protected.items())
historical=readj(OLD/'protected_before.json')
assert all(sha(Path(p))==v for p,v in historical.items())
save('protected_after.json',protected)
save('candidate2a_checks.json',{'draft_sha256':h,'base_sha256':bh,
    'only_terminology_and_attachment_link_changed':True,'changed_lines':[503,630],
    'reverse_replacements_equal_parent':True,'six_body_sections_byte_identical':True,
    'body_cjk':11510,'section_cjk':[1695,2190,2210,2755,1897,763],
    'all_14_table_blocks_byte_identical':True,'all_display_formula_blocks_byte_identical':True,
    'external_reference_text_and_contexts_unchanged':True,'four_figures_unchanged':True,
    'original_25_item_locations_rebound':84,
    'parent_candidate_and_frozen_files_unchanged':len(protected),
    'earlier_historical_protected_files_unchanged':len(historical),
    'writer_model_or_reference_execution':False,'writer_training_calls':0,'rendered_by_writer':False,
    'final_integrity_status':'PENDING_INDEPENDENT_FINAL_RECHECK','final_frozen':True})
bound=['change_map.json','word_counts.json','citation_contexts.json','figure_retention_checks.json',
       'numeric_evidence_checks.json','prior_25_items_location_bridge.json','RESPONSES_TO_FINAL_PROVENANCE.json','source_checks.json','candidate2a_checks.json']
for n in bound:assert readj(OUT/n)['draft_sha256']==h
save('final_binding_checks.json',{'draft_sha256':h,'all_binding_checks_pass':True,'bound_json_files':bound,
    'parent_candidate_sha256':bh,'manuscript_link_points_to_current_citation_attachment':True,
    'author_self_check_is_not_final_review_decision':True})
files={str(DRAFT):sha(DRAFT)}
files.update({str(p):sha(p) for p in sorted(OUT.iterdir()) if p.is_file()})
save('FROZEN_CANDIDATE2A_MANIFEST.json',{'created_local':datetime.now(timezone(timedelta(hours=8))).isoformat(),
    'draft_sha256':h,'file_count':len(files),'files':files,'manifest_excludes_itself':True,
    'final_integrity_status':'PENDING_INDEPENDENT_FINAL_RECHECK',
    'read_only_future_policy':'本候选与附件已冻结。后续状态另行记录，不覆盖已冻文件。'})
assert all(sha(Path(p))==v for p,v in files.items())
print(json.dumps({'draft_sha256':h,'manifest_sha256':sha(OUT/'FROZEN_CANDIDATE2A_MANIFEST.json'),
    'file_count':len(files),'body_cjk':11510,'protected_parent_files':len(protected)},ensure_ascii=False))

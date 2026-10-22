"""仅绑定冻结v2展示版，复用既有206份JSON核查；不重扫原始结果或加载模型。"""
from pathlib import Path
import hashlib
import json
import re

OUT=Path(__file__).resolve().parent
MAN=OUT.parents[1]
ROOT=MAN.parent
DRAFT=MAN/'drafts/complete_v1.md'
V1=ROOT/'validation/stage6_analysis_20261022/complete_v1'
V2=ROOT/'validation/stage6_analysis_20261022/complete_v2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
readj=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

assert not (OUT/'v2_binding_checks.json').exists(),'展示版已绑定；请勿重复覆盖证据。'
state=readj(OUT/'draft_state.json')
old_sha=sha(DRAFT)
assert old_sha==state['draft_sha256']
sources=readj(OUT/'source_checks.json')
numbers=readj(OUT/'numeric_checks.json')
counts=readj(OUT/'word_counts.json')
assert sources['draft_sha256']==numbers['draft_sha256']==counts['draft_sha256']==old_sha
assert numbers['raw_json_count']==206 and numbers['all_raw_json_hashes_match_formal488_manifest'] is True
assert sha(V1/'analysis_evidence.json')==numbers['analysis_sha256']
a=readj(V1/'analysis_evidence.json'); b=readj(V2/'analysis_evidence.json')
assert set(a)==set(b)
changed=[k for k in a if a[k]!=b[k]]
assert set(changed)=={'generated_local','figure_metadata','analysis_code_sha256','output_sha256'},changed
scientific_keys=[k for k in a if k not in changed]
assert all(a[k]==b[k] for k in scientific_keys)
assert len(b['output_sha256'])==8
assert all(sha(V2/name)==digest for name,digest in b['output_sha256'].items())
csvs=('all_new_runs.csv','default_six_arms.csv','tau_sensitivity.csv')
assert all(sha(V1/name)==sha(V2/name) for name in csvs)
final_files={str(V2/'analysis_evidence.json'):sha(V2/'analysis_evidence.json')}
final_files.update({str(V2/name):sha(V2/name) for name in b['output_sha256']})
assert len(final_files)==9

t=DRAFT.read_text(encoding='utf-8')
old='stage6_analysis_20261022/complete_v1/'
new='stage6_analysis_20261022/complete_v2/'
assert t.count(old)==6,t.count(old)
t=t.replace(old,new)
old_scope='正式分析绑定旧398与新90文件；本作者另核206份JSON及新增汇总，不重新加载模型'
new_scope='正式分析绑定旧398与新90文件；v2仅修订展示，三CSV及科学字段与v1完全一致；作者既有206份JSON及分组核查继续有效'
assert t.count(old_scope)==1
t=t.replace(old_scope,new_scope)
config=readj(MAN/'PAPER_CONFIGURATION.json')
for title,target in config['section_targets'].items():
    block=t.split('## '+title+'\n',1)[1].split('\n## ',1)[0]
    block=re.sub(r'\\\[.*?\\\]','',block,flags=re.S)
    block=re.sub(r'<!--.*?-->','',block,flags=re.S)
    lines=[line for line in block.splitlines() if not line.startswith(('|','图','!['))]
    cjk=len(re.findall(r'[\u4e00-\u9fff]',title+'\n'+'\n'.join(lines)))
    assert cjk==counts['sections'][title]['actual_cjk']
DRAFT.write_text(t,encoding='utf-8')
new_sha=sha(DRAFT)
for name,obj in [('word_counts.json',counts),('numeric_checks.json',numbers),('source_checks.json',sources),('draft_state.json',state)]:
    obj['draft_sha256']=new_sha
    if name=='numeric_checks.json':
        obj['display_analysis_sha256']=sha(V2/'analysis_evidence.json')
        obj['display_analysis_scientific_fields_identical_to_validated_v1']=True
        obj['original_numeric_verification_reused']=True
    elif name=='source_checks.json':
        obj['sources'].update(final_files)
        obj['stage6_display_version']='complete_v2'
        obj['stage6_display_output_hashes_match']=True
        obj['v1_v2_all_scientific_fields_and_csv_identical']=True
        obj['v2_targeted_review_pending']=True
    elif name=='draft_state.json':
        obj['stage6_display_version']='complete_v2'
        obj['phase4b_pending']=True
    save(name,obj)
save('v2_binding_checks.json',{'draft_before_sha256':old_sha,'draft_sha256':new_sha,
    'stage6_v1_analysis_sha256':sha(V1/'analysis_evidence.json'),
    'stage6_v2_analysis_sha256':sha(V2/'analysis_evidence.json'),
    'changed_top_level_fields':changed,'scientific_keys_unchanged':scientific_keys,
    'all_three_csv_byte_identical':{name:sha(V2/name) for name in csvs},
    'frozen_nine_file_sha256':final_files,'all_output_hashes_match':True,
    'old_numeric_evidence_reused':True,'body_counts_unchanged':True,
    'scope':'只读比较两版正式JSON/CSV及九个展示输出；不重扫206份原JSON、不重新加载模型、不运行训练/ODE/排版。',
    'independent_v2_review_pending':True})
print(json.dumps({'draft_sha256':new_sha,'body_cjk':counts['actual_body_cjk'],'replaced_paths':6,
    'v2_files':len(final_files),'scientific_fields_identical':True,'independent_review_pending':True},ensure_ascii=False,indent=2))

"""作者交付的最终回读和哈希清单；只检查本稿与本过程目录。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import ast
import hashlib
import json
import re

OUT=Path(__file__).resolve().parent
MAN=OUT.parents[1]
DRAFT=MAN/'drafts/complete_v1.md'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
readj=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not (OUT/'FROZEN_DELIVERY_MANIFEST.json').exists(),'已存在冻结清单，拒绝覆盖。'
t=DRAFT.read_text(encoding='utf-8'); digest=sha(DRAFT)
phase=(OUT/'writer_phase4b.md').read_text(encoding='utf-8')
assert phase.split('## Draft Body\n\n',1)[1].split('\n\n## Dimension Scores',1)[0]==t.rstrip()
assert 'MATERIAL GAP' not in t and 'stage6_analysis_20261022/complete_v1/' not in t
bound=[]
for p in sorted(OUT.glob('*.json')):
    obj=readj(p)
    if isinstance(obj,dict) and 'draft_sha256' in obj:
        assert obj['draft_sha256']==digest,p
        bound.append(p.name)
for p in OUT.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
counts=readj(OUT/'word_counts.json')
structure=readj(OUT/'final_structure_checks.json')
scores=readj(OUT/'phase4b_checks.json')
source=readj(OUT/'source_checks.json')
binding=readj(OUT/'v2_binding_checks.json')
numeric=readj(OUT/'numeric_checks.json')
assert scores['phase4b_sha256']==sha(OUT/'writer_phase4b.md')
assert scores['full_draft_embedded_exactly'] and scores['writer_decision']=='accept'
assert all(v['score']=='pass' for v in scores['scores'].values())
assert source['v2_targeted_review_pending'] is False and binding['independent_v2_review_pending'] is False
assert source['v2_targeted_review']['full_manuscript_verdict'] is False
assert structure['main_sections']==6 and structure['main_tables']==8 and structure['references']==13
assert structure['all_markdown_tables']==13 and len(structure['images'])==4
assert structure['protected_files_unchanged']==53
assert counts['within_10_percent'] and all(v['within_15_percent'] for v in counts['sections'].values())
assert numeric['raw_json_count']==206 and len(numeric['prose_numeric_claims'])==26
assert len(numeric['stage6_main_table_groups'])==18
save('delivery_readback.json',{'draft_sha256':digest,'phase4b_sha256':sha(OUT/'writer_phase4b.md'),
    'full_draft_in_phase4b_exact':True,'bound_json_artifacts':bound,
    'script_AST_parse_passed':True,'body_cjk':counts['actual_body_cjk'],'all_six_section_quotas_met':True,
    'main_sections':6,'main_tables':8,'all_markdown_tables':13,'references':13,'figures':4,
    'independently_reaggregated_raw_JSON':206,'new_group_mappings':18,'prose_numeric_checks':26,
    'old_protected_files_unchanged_reused_finalizer_check':53,
    'targeted_stage6_v2_findings_closed':['S6-F01','S6-F02','S6-F03'],
    'whole_manuscript_independent_review_passed':False,'final_render_by_writer':False,
    'scope':'最终回读仅检查本稿/本过程目录；既有原始数据检查及图版限定复核保留原范围，不重复全库扫描。'})
files=[DRAFT]+[p for p in OUT.iterdir() if p.is_file() and p.name!='FROZEN_DELIVERY_MANIFEST.json']
save('FROZEN_DELIVERY_MANIFEST.json',{'frozen_local':datetime.now(timezone(timedelta(hours=8))).isoformat(),
    'draft_sha256':digest,'phase4b_sha256':sha(OUT/'writer_phase4b.md'),
    'draft_body_cjk':counts['actual_body_cjk'],'writer_decision':'accept',
    'scope':'作者完整初稿交付冻结；不是独立全文审查或投稿通过。后续改稿另存版本，不覆盖本稿和本清单。',
    'files':{str(p):sha(p) for p in sorted(files)}})
print(json.dumps({'draft_sha256':digest,'phase4b_sha256':sha(OUT/'writer_phase4b.md'),
    'manifest_sha256':sha(OUT/'FROZEN_DELIVERY_MANIFEST.json'),'frozen_files':len(files),
    'body_cjk':counts['actual_body_cjk']},ensure_ascii=False,indent=2))

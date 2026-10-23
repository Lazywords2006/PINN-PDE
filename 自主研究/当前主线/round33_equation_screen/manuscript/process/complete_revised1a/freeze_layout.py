"""冻结排版派生稿及响应；不把静态检查宣称为重新渲染通过。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json

OUT = Path(__file__).resolve().parent
MAN = OUT.parents[1]
DRAFT = MAN / 'drafts/complete_revised1a.md'
PARENT = MAN / 'drafts/complete_revised1.md'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
readj = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

assert not (OUT / 'FROZEN_LAYOUT_MANIFEST.json').exists()
checks = readj(OUT / 'layout_revision_checks.json')
digest = sha(DRAFT)
assert checks['draft_sha256'] == digest == '398c2a44f2f9fd959b62564ddc599b123a3dd5de168ad0257a8572e188bf92e8'
responses = readj(OUT / 'RESPONSE_TO_REVIEWS.json')
assert responses['draft_sha256'] == digest and len(responses['responses']) == 25
checked = {}
for item in responses['responses']:
    for obj in item['实际修订位置'] + item['作者证据']:
        p = Path(obj['file'])
        if str(p) not in checked:
            checked[str(p)] = sha(p)
        assert checked[str(p)] == obj['sha256']
    assert item['独立核验状态'] == 'PENDING'
protected = readj(OUT / 'protected_before.json')
assert readj(OUT / 'protected_after.json') == protected
assert all(sha(Path(p)) == expected for p, expected in protected.items())
renderer = MAN / 'render_manuscript_v2.py'
format_line = next(line for line in renderer.read_text(encoding='utf-8').splitlines() if line.startswith('FORMAT = '))
assert 'tex_math_single_backslash' in format_line
checks['final_frozen'] = True
save('layout_revision_checks.json', checks)
save('source_checks.json', {
    'draft_sha256': digest, 'parent_sha256': sha(PARENT), 'parent_frozen_files_and_manifest_unchanged': len(protected),
    'protection_hashes': protected, 'scientific_response_count': 25, 'unique_response_evidence_files_current': len(checked),
    'scientific_results_evidence': '沿用complete_revised1的有效来源与数字核查；本次未重扫原始训练文件。',
    'renderer_read_only_check': {'path': str(renderer), 'sha256': sha(renderer), 'format_line': format_line,
                                 'supports_inline_single_backslash_math': True, 'renderer_edited': False, 'renderer_run': False},
    'layout_rerender_status': 'PENDING_PARENT_COORDINATION',
    'independent_scientific_review_status': 'PENDING',
    'body_cjk': 11487, 'fourteen_tables_identical': True, 'four_figure_hashes_retained': True,
    'references_identical': 13, 'citation_contexts_identical': 18
})
files = [DRAFT] + sorted(p for p in OUT.iterdir() if p.is_file() and p.name != 'FROZEN_LAYOUT_MANIFEST.json')
manifest = {
    'status': 'FROZEN_LAYOUT_FIX_OF_FIRST_REVISION', 'draft_sha256': digest, 'parent_sha256': sha(PARENT),
    'frozen_local': datetime.now(timezone(timedelta(hours=8))).isoformat(), 'file_count': len(files),
    'files': {str(p): sha(p) for p in files}, 'scientific_revision_round': 1, 'new_scientific_revision': False,
    'fixed_issues': ['Unicode数学下标导致的六条缺字风险', '引用上下文文件长路径的行宽溢出'],
    'remaining_checks': ['独立HTML/PDF复检', '25项独立修订核验', '最终完整性检查及人类作者确认'],
    'original_review_panel': 'ABORT; usable=2, panel_size=5; no full-panel editorial decision'
}
save('FROZEN_LAYOUT_MANIFEST.json', manifest)
assert all(sha(Path(p)) == expected for p, expected in manifest['files'].items())
print(json.dumps({'draft_sha256': digest, 'manifest_sha256': sha(OUT / 'FROZEN_LAYOUT_MANIFEST.json'),
                  'files': len(files), 'parent_protected': len(protected), 'responses': 25}, ensure_ascii=False, indent=2))

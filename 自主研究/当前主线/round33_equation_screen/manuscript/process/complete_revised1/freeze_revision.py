"""一次性冻结已完成的作者修订，逐条核对回应定位与证据；不修改任何研究数据。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
MAN = OUT.parents[1]
DRAFT = MAN / 'drafts/complete_revised1.md'
BASE = MAN / 'drafts/complete_v1.md'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
readj = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

assert not (OUT / 'FROZEN_REVISION_MANIFEST.json').exists(), '冻结清单已存在，停止覆盖。'
t, b = DRAFT.read_text(encoding='utf-8'), BASE.read_text(encoding='utf-8')
digest = sha(DRAFT)
state = readj(OUT / 'revision_state.json')
assert state['draft_sha256'] == digest and state['author_revision_complete']
response = readj(OUT / 'RESPONSE_TO_REVIEWS.json')
assert response['draft_sha256'] == digest and len(response['responses']) == 25
checked_files = {}
def exact_file(path, expected):
    path = Path(path)
    if str(path) not in checked_files:
        checked_files[str(path)] = sha(path)
    assert checked_files[str(path)] == expected, str(path)

locations = 0
for item in response['responses']:
    assert item['作者答复'] and item['实际修订位置'] and item['作者证据']
    assert item['独立核验状态'] == 'PENDING' and item['独立核验结果'] is None
    for location in item['实际修订位置']:
        exact_file(location['file'], location['sha256'])
        if 'line' in location:
            lines = Path(location['file']).read_text(encoding='utf-8').splitlines()
            assert location['exact_anchor'] in lines[location['line'] - 1]
        locations += 1
    for evidence in item['作者证据']:
        exact_file(evidence['file'], evidence['sha256'])
    exact_file(item['原报告位置']['文件'], item['原报告位置']['SHA256'])
exact_file(MAN / 'reviews/revision1/REVIEW_ITEMS.json', response['tracker_sha256'])
assert {i['编号'] for i in response['responses']} == {i['编号'] for i in readj(MAN / 'reviews/revision1/REVIEW_ITEMS.json')['修订条目']}
mapped = set(re.findall(r'^\| (E\d{2}) \|', t, re.M))
used = set()
for group in re.findall(r'\[(E\d{2}(?:,E\d{2})*)\]', t):
    used.update(group.split(','))
assert used <= mapped

def tables(text):
    out, buf = [], []
    for line in text.splitlines() + ['']:
        if line.startswith('|'):
            buf.append(line)
        elif buf:
            out.append('\n'.join(buf))
            buf = []
    return out

all_tables = tables(t)
assert len(all_tables) == 14
assert all(len({line.count('|') for line in table.splitlines()}) == 1 for table in all_tables)
old_main_tables = tables(b.split('## 3 实验设计与复现方法', 1)[1].split('## 5 讨论与局限', 1)[0])
assert len(old_main_tables) == 8 and all(table in t for table in old_main_tables)
assert re.findall(r'^\[\d+\].+$', t, re.M) == re.findall(r'^\[\d+\].+$', b, re.M)
assert t.count('\\[') == t.count('\\]')
counts = readj(OUT / 'word_counts.json')
assert counts['draft_sha256'] == digest and counts['actual_body_cjk'] == 11487
assert counts['within_10_percent'] and all(x['within_15_percent'] for x in counts['sections'].values())
diff = (OUT / 'complete_v1_to_revised1.diff').read_text(encoding='utf-8')
assert diff.startswith('--- drafts/complete_v1.md\n+++ drafts/complete_revised1.md\n')
state['final_frozen'] = True
state['frozen_local'] = datetime.now(timezone(timedelta(hours=8))).isoformat()
save('revision_state.json', state)
checks = readj(OUT / 'revision_checks.json')
checks['final_frozen'] = True
checks['response_location_checks'] = locations
checks['all_evidence_codes_mapped'] = True
save('revision_checks.json', checks)
save('final_binding_checks.json', {
    'draft_sha256': digest, 'response_count': 25, 'mandatory_count': 14, 'optional_count': 11,
    'response_location_checks': locations, 'unique_response_and_source_files_hash_checked': len(checked_files),
    'all_original_issue_ids_preserved': True, 'all_independent_statuses_pending': True,
    'eight_main_table_blocks_unchanged': True, 'all_markdown_tables_valid': 14,
    'all_referenced_data_codes_mapped': sorted(used), 'display_math_pairs': t.count('\\['),
    'references_preserved': 13, 'body_cjk': 11487,
    'check_scope': '最终只核小型作者响应、引用文件及定位，复用此前原始JSON和图形检查；不重扫数据、不运行训练或渲染。'
})
files = [DRAFT] + sorted(p for p in OUT.iterdir() if p.is_file() and p.name != 'FROZEN_REVISION_MANIFEST.json')
manifest = {
    'status': 'FROZEN_AUTHOR_REVISION_AWAITING_INDEPENDENT_VERIFICATION',
    'draft_sha256': digest, 'base_sha256': sha(BASE), 'frozen_local': state['frozen_local'],
    'file_count': len(files), 'files': {str(p): sha(p) for p in files},
    'counts': {'body_cjk': 11487, 'mandatory_response_count': 14, 'optional_response_count': 11, 'independent_closed_count': 0},
    'pending': ['25项独立修订核验', '最终全稿完整性与渲染核验', '人类作者最终确认及身份/基金/利益冲突/贡献信息'],
    'old_full_review_status': 'ABORT; usable=2, panel_size=5; no full-panel editorial decision',
    'preservation_scope': '原完整v1、Phase4a/Phase4b、审稿契约与报告、统一问题清单、科研代码和原始产物保持。后续修改必须新建版本。'
}
save('FROZEN_REVISION_MANIFEST.json', manifest)
assert all(sha(Path(p)) == value for p, value in manifest['files'].items())
print(json.dumps({'draft_sha256': digest, 'manifest_sha256': sha(OUT / 'FROZEN_REVISION_MANIFEST.json'),
                  'file_count': len(files), 'response_locations': locations, 'body_cjk': 11487,
                  'independent_closed': 0}, ensure_ascii=False, indent=2))

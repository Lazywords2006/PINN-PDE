"""第一修订稿的两项排版修复；另存派生稿，不改已冻结版本。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import copy
import difflib
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
MAN = OUT.parents[1]
OLD = MAN / 'process/complete_revised1'
BASE = MAN / 'drafts/complete_revised1.md'
DRAFT = MAN / 'drafts/complete_revised1a.md'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
readj = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat()
def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

assert not DRAFT.exists(), '排版派生稿已存在，拒绝覆盖。'
assert sha(BASE) == '5eb4cf00f663aa18face96dc503c7e3d35420e2d809489e0cad5f176f8bdd68a'
old_manifest = readj(OLD / 'FROZEN_REVISION_MANIFEST.json')
protected = dict(old_manifest['files'])
protected[str(OLD / 'FROZEN_REVISION_MANIFEST.json')] = '687273429dd3532bb7a3a79cca84c6975443ba7dedbc4e029acdeb25e2b6467c'
assert all(sha(Path(p)) == h for p, h in protected.items())
save('protected_before.json', protected)
base = BASE.read_text(encoding='utf-8')
t = base
replacements = [
    {'issue': 'LAYOUT-02', 'description': '长代码路径改为简短可读链接，完整目标保留在链接中',
     'old': '`../process/complete_revised1/citation_contexts.md`',
     'new': '[本稿引用上下文表](../process/complete_revised1a/citation_contexts.md)'},
    {'issue': 'LAYOUT-01', 'description': '通量错配的y下标使用TeX数学模式',
     'old': 'Δᵧ=κ[f(1)−V₀]+Df′(1)=−1.02',
     'new': r"\(\Delta_y=\kappa[f(1)-V_0]+Df'(1)=-1.02\)"},
    {'issue': 'LAYOUT-01', 'description': '热方程时间及二阶空间下标使用TeX数学模式',
     'old': 'Uₜ=DUᵧᵧ', 'new': r'\(U_t=DU_{yy}\)'},
    {'issue': 'LAYOUT-01', 'description': '常通量条件的一阶空间下标使用TeX数学模式',
     'old': 'DUᵧ(0,t)=Δᵧ', 'new': r'\(D U_y(0,t)=\Delta_y\)'}
]
assert {c: base.count(c) for c in ('ᵧ', 'ₜ')} == {'ᵧ': 5, 'ₜ': 1}
for entry in replacements:
    assert t.count(entry['old']) == 1
    entry['base_line'] = t[:t.index(entry['old'])].count('\n') + 1
    t = t.replace(entry['old'], entry['new'])
    entry['derived_line'] = t[:t.index(entry['new'])].count('\n') + 1
assert not any(c in t for c in ('ᵧ', 'ₜ'))
restored = t
for entry in reversed(replacements):
    assert restored.count(entry['new']) == 1
    restored = restored.replace(entry['new'], entry['old'])
assert restored == base, '出现授权替换之外的变更。'
assert len(t.splitlines()) == len(base.splitlines())
assert t.split('## 1 引言与相关工作', 1)[1].split('## 参考文献', 1)[0] == base.split('## 1 引言与相关工作', 1)[1].split('## 参考文献', 1)[0]
DRAFT.write_text(t, encoding='utf-8')
digest = sha(DRAFT)
(OUT / 'complete_revised1_to_revised1a.diff').write_text(''.join(difflib.unified_diff(
    base.splitlines(keepends=True), t.splitlines(keepends=True),
    fromfile='drafts/complete_revised1.md', tofile='drafts/complete_revised1a.md')), encoding='utf-8')
fixes = {'base_sha256': sha(BASE), 'draft_sha256': digest, 'generated_local': now(),
    'revision_kind': '第一轮科学修订后的排版修复，不是第二轮科学修订',
    'reported_precheck_findings': {'source': '父代理转达的独立排版预检',
      'missing_glyph_warnings': {'ᵧ': 5, 'ₜ': 1}, 'overfull_hbox_pt': 1.53183,
      'location': '附录E约p25与生成TeX763–764行；这是原预检定位，不是本代理复渲染结果。'},
    'replacements': replacements, 'only_authorized_replacements': True,
    'same_line_count': True, 'six_body_sections_byte_identical': True,
    'missing_codepoints_after': {'ᵧ': t.count('ᵧ'), 'ₜ': t.count('ₜ')},
    'rerender_verification': 'PENDING_PARENT_COORDINATED_LAYOUT_CHECK',
    'operations': {'training': 0, 'model_load': 0, 'reference_integration': 0, 'render': 0, 'renderer_edit': 0, 'git_mutation': 0}}
save('LAYOUT_FIXES.json', fixes)

# 保留原统计，只将与新稿绑定的辅助文件另存；基础数据核对不重做。
counts = readj(OLD / 'word_counts.json')
counts['layout_parent_draft_sha256'] = counts['draft_sha256']
counts['draft_sha256'] = digest
counts['derivation_note'] = '六章正文逐字一致；仅正文外的路径显示和附录数学表示改变，原计数及配额判断继续有效。'
save('word_counts.json', counts)
count_report = (OLD / 'COUNT_DEFINITION_COMPARISON_CN.md').read_text(encoding='utf-8')
count_report = count_report.replace(sha(BASE), digest)
count_report = count_report.replace('本轮修订稿SHA256：', '本轮排版派生稿SHA256：')
count_report += f'\n本版为第一修订稿的排版派生稿；父稿SHA256 `{sha(BASE)}`。六章正文逐字相同，上述字数与配额沿用有效核验，不将此排版修改计为第二轮科学修订。\n'
(OUT / 'COUNT_DEFINITION_COMPARISON_CN.md').write_text(count_report, encoding='utf-8')
comparison = readj(OLD / 'count_definition_comparison.json')
comparison['layout_parent_draft_sha256'] = comparison['draft_sha256']
comparison['draft_sha256'] = digest
save('count_definition_comparison.json', comparison)
citation = readj(OLD / 'citation_contexts.json')
citation['layout_parent_draft_sha256'] = citation['draft_sha256']
citation['draft_sha256'] = digest
for context in citation['contexts']:
    line = t.splitlines()[context['line'] - 1]
    assert line == context['paragraph']
for context in citation['data_evidence_contexts']:
    line = t.splitlines()[context['line'] - 1]
    assert line == context['paragraph']
citation['layout_note'] = '18处外部引用上下文及数据引用段落未变；简短链接指向本文件同目录的引用说明。'
save('citation_contexts.json', citation)
citation_md = (OLD / 'citation_contexts.md').read_text(encoding='utf-8').replace(sha(BASE), digest)
citation_md += f'\n排版派生来源：`complete_revised1.md`，SHA256 `{sha(BASE)}`。原18处引用的正文、编号、行位及阅读证据保持一致。\n'
(OUT / 'citation_contexts.md').write_text(citation_md, encoding='utf-8')
figure = readj(OLD / 'figure_retention_checks.json')
figure['layout_parent_draft_sha256'] = figure['draft_sha256']
figure['draft_sha256'] = digest
for row in figure['figures']:
    assert sha(Path(row['path'])) == row['sha256']
save('figure_retention_checks.json', figure)

# 25项响应的科学答复及处置保持；每个稿件定位重新绑定新SHA和当前行位。
responses = readj(OLD / 'RESPONSE_TO_REVIEWS.json')
responses['layout_parent_draft_sha256'] = responses['draft_sha256']
responses['draft_sha256'] = digest
responses['generated_local'] = now()
responses['revision_kind'] = fixes['revision_kind']
responses['layout_fix_evidence'] = {'file': str(OUT / 'LAYOUT_FIXES.json'), 'sha256': sha(OUT / 'LAYOUT_FIXES.json')}
derived_files = {'word_counts.json', 'citation_contexts.json', 'figure_retention_checks.json',
                 'count_definition_comparison.json', 'COUNT_DEFINITION_COMPARISON_CN.md'}
rebound_locations = 0
for item in responses['responses']:
    assert item['独立核验状态'] == 'PENDING'
    for loc in item['实际修订位置']:
        p = Path(loc['file'])
        if p == BASE:
            loc['file'] = str(DRAFT)
            loc['sha256'] = digest
            needle = loc['exact_anchor']
            assert t.count(needle) == 1
            loc['line'] = t[:t.index(needle)].count('\n') + 1
            rebound_locations += 1
        elif p.parent == OLD and p.name in derived_files:
            loc['file'] = str(OUT / p.name)
            loc['sha256'] = sha(OUT / p.name)
    for ev in item['作者证据']:
        p = Path(ev['file'])
        if p.parent == OLD and p.name in derived_files:
            ev['file'] = str(OUT / p.name)
            ev['sha256'] = sha(OUT / p.name)
save('RESPONSE_TO_REVIEWS.json', responses)
md = ['# 第一修订稿排版修复后的完整逐项响应', '',
      f'新稿：[{DRAFT.name}](<{DRAFT.as_posix()}>), SHA256 `{digest}`。冻结父稿SHA256 `{sha(BASE)}`。', '',
      '这份派生稿只修复独立预检指出的两项排版问题，不是第二轮科学修订。25项答复的内容、处置和待独立核验状态均保持；稿件位置已重新绑定新稿及其行位。原full_v1保持ABORT、2/5可用、无全轮编辑裁决。', '',
      '14项必修与11项建议全部回应：21项采纳、1项部分采纳、3项可选文献不采纳。RESOLVED和DELIBERATE_LIMITATION仅是作者处置，独立核验关闭仍为0。两项排版修复的再次渲染结果由父代理协调记录，本文件不预判通过。', '']
for item in responses['responses']:
    md += [f"## {item['编号']}：{item['问题摘要']}", '',
           f"来源：{item['审稿角色']}，{item['类别']}。作者处置：{item['作者处置']}；状态：{item['作者修订状态']}（独立核验PENDING）。", '',
           item['作者答复'], '', '修订位置：', '']
    for loc in item['实际修订位置']:
        label = loc.get('label', loc.get('detail', Path(loc['file']).name))
        line = f":{loc['line']}" if 'line' in loc else ''
        md.append(f"- [{label}](<{Path(loc['file']).as_posix()}{line}>)")
    md += ['', '证据：', '']
    for ev in item['作者证据']:
        md.append(f"- [{Path(ev['file']).name}](<{Path(ev['file']).as_posix()}>): {ev['detail']}")
    if item['未采纳部分及理由']:
        md += ['', '未采纳部分与理由：' + item['未采纳部分及理由']]
    md += ['', '原验收条件完整保留在JSON；本项尚未由独立复核者认定关闭。', '']
md += ['## 核验边界', '',
       '科学内容、负面结果、预算、判据及人类作者待确认信息全部沿用冻结父稿。正文11,487汉字、六章配额不变。独立修订核验、最终完整性和排版检查仍由后续流程确认；旧稿及冻结清单保持。', '']
(OUT / 'RESPONSE_TO_REVIEWS_CN.md').write_text('\n'.join(md), encoding='utf-8')

assert len(responses['responses']) == 25
old_responses = readj(OLD / 'RESPONSE_TO_REVIEWS.json')['responses']
for old_item, new_item in zip(old_responses, responses['responses']):
    for key in ('编号', '原审稿编号', '审稿角色', '类别', '原验收条件', '作者答复', '作者处置', '作者修订状态', '未采纳部分及理由', '独立核验状态'):
        assert old_item[key] == new_item[key]
    for loc in new_item['实际修订位置']:
        assert sha(Path(loc['file'])) == loc['sha256']
        if 'line' in loc:
            assert loc['exact_anchor'] in Path(loc['file']).read_text(encoding='utf-8').splitlines()[loc['line'] - 1]
    for ev in new_item['作者证据']:
        assert sha(Path(ev['file'])) == ev['sha256']
def tables(s):
    return re.findall(r'(?:^\|.*\n)+', s, re.M)
assert tables(t) == tables(base) and len(tables(t)) == 14
assert re.findall(r'^\[\d+\].+$', t, re.M) == re.findall(r'^\[\d+\].+$', base, re.M)
assert re.findall(r'!\[[^\]]*\]\(([^)]+)\)', t) == re.findall(r'!\[[^\]]*\]\(([^)]+)\)', base)
assert t.count('\\(') == t.count('\\)')
assert t.count('\\[') == t.count('\\]')
assert all(sha(Path(p)) == h for p, h in protected.items())
save('protected_after.json', protected)
save('layout_revision_checks.json', {'draft_sha256': digest, 'parent_sha256': sha(BASE),
    'only_two_reported_issues_changed': True, 'replacements': 4, 'changed_source_lines': [503, 645, 654],
    'six_body_sections_byte_identical': True, 'body_cjk': 11487,
    'all_fourteen_table_blocks_unchanged': True, 'eight_main_tables_unchanged': True,
    'thirteen_references_unchanged': True, 'eighteen_external_contexts_unchanged': True,
    'four_figure_paths_and_hashes_unchanged': True, 'twenty_five_scientific_responses_unchanged': True,
    'draft_locations_rebound': rebound_locations, 'old_frozen_files_unchanged_including_manifest': len(protected),
    'render_check': 'PENDING_PARENT_COORDINATION', 'final_frozen': False})
fix_md = f'''# 第一修订稿的两项排版修复

父稿SHA256：`{sha(BASE)}`。派生稿SHA256：`{digest}`。本次只修复父代理转达的独立排版预检问题，不属于第二轮科学修订。旧稿及包含其26份文件的冻结清单全部保留，合计27个旧文件在修复前后哈希一致。

| 项目 | 原表现 | 修复 | 稿件行位 |
|---|---|---|---|
| LAYOUT-01 | 附录E有ᵧ五次、ₜ一次，原预检报告六条缺字 | 改为TeX数学模式的Delta_y、U_t、U_{{yy}}和U_y，公式含义不变 | 645、654 |
| LAYOUT-02 | citation_contexts.md长代码路径，原预检报告Overfull 1.53183pt | 显示简短的“本稿引用上下文表”，完整文件目标保留在Markdown链接中 | 503 |

`LAYOUT_FIXES.json`保存四处字符串替换的精确前后内容；差异文件显示只改三行。将四处替换逆向恢复后与父稿全文完全一致。六章正文逐字相同，全部14个Markdown表块（含原8张主表）、13条题录、18处外部引用上下文及4张图保持；未改科学参数、结果、判据、审阅记录、协议或渲染器。

完整25项响应另存，作者答复与采纳状态保持，稿件定位重新绑定新SHA。内部数据来源继续指向有效的冻结父稿证据，不重新扫描科研数据或重跑模型。

本代理仅验证源文本已消除相应Unicode字符、链接显示已缩短及证据绑定一致；没有执行渲染，不能据此声称PDF警告已清零。再次HTML/PDF核查通过父代理协调。稿件独立修订核验、最终完整性及人类作者确认仍待完成。
'''
(OUT / 'LAYOUT_FIXES_CN.md').write_text(fix_md, encoding='utf-8')
print(json.dumps({'draft_sha256': digest, 'changed_lines': [503,645,654], 'responses': 25,
                  'draft_locations_rebound': rebound_locations, 'protected_old_files': len(protected), 'body_cjk': 11487}, ensure_ascii=False, indent=2))

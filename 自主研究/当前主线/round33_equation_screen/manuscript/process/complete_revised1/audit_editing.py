"""本轮编辑检查；只读既有稿件，输出仅限当前修订过程目录。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
MAN = OUT.parents[1]
ROOT = MAN.parent
BASE = MAN / 'drafts/complete_v1.md'
DRAFT = MAN / 'drafts/complete_revised1.md'
readj = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
cjk = lambda s: len(re.findall(r'[\u4e00-\u9fff]', s))
assert not (OUT / 'FROZEN_REVISION_MANIFEST.json').exists(), '本轮已冻结；请新建后续检查版本。'

def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

assert sha(BASE) == '8c5a83cff08732ce8e548cd873faa4e55cede075c3340fe9799e9deae37d4fd3'
assert sha(DRAFT) == readj(OUT / 'revision_state.json')['draft_sha256']
base, revised = [p.read_text(encoding='utf-8') for p in (BASE, DRAFT)]
config = readj(MAN / 'PAPER_CONFIGURATION.json')

def table_line_kind(s):
    if re.match(r'^表\d+注', s):
        return 'table_note'
    if re.match(r'^表\d+\s', s):
        return 'table_caption'
    if re.match(r'^表\d+', s):
        return 'body_prose'
    return None

def count_policies(text):
    result = {}
    removed = []
    for title in config['section_targets']:
        start = text.index('## ' + title + '\n')
        end = text.find('\n## ', start + 4)
        block = text[start:end if end != -1 else None]
        # 保留换行以便输出原稿位置。
        block = re.sub(r'\\\[.*?\\\]', lambda m: '\n' * m.group(0).count('\n'), block, flags=re.S)
        block = re.sub(r'<!--.*?-->', lambda m: '\n' * m.group(0).count('\n'), block, flags=re.S)
        values = {k: 0 for k in ('original', 'method_prefix', 'domain_da_prefix', 'eic_caption_note', 'perspective_no_headings')}
        for offset, line in enumerate(block.splitlines()):
            if line.startswith(('|', '图', '![')):
                continue
            n = cjk(line)
            kind = table_line_kind(line)
            values['original'] += n
            if not line.startswith('## ') and kind is None:
                values['method_prefix'] += n
            if kind is None and not (title.startswith('1 ') and line.startswith('## ')):
                values['domain_da_prefix'] += n
            if kind not in ('table_caption', 'table_note'):
                values['eic_caption_note'] += n
                if not re.match(r'^#+\s', line):
                    values['perspective_no_headings'] += n
            if kind or re.match(r'^#+\s', line):
                removed.append({'section': title, 'line': text[:start].count('\n') + offset + 1,
                                'kind': kind or 'heading', 'cjk': n, 'text': line})
        result[title] = values
    return {'sections': result, 'totals': {key: sum(row[key] for row in result.values()) for key in next(iter(result.values()))},
            'classified_lines': removed}

policy_base, policy_new = [count_policies(s) for s in (base, revised)]
assert policy_base['totals'] == {'original': 11434, 'method_prefix': 10213, 'domain_da_prefix': 10243,
                                 'eic_caption_note': 11056, 'perspective_no_headings': 10833}, policy_base['totals']
assert policy_new['totals']['original'] == readj(OUT / 'word_counts.json')['actual_body_cjk']
comparison = {
    'base_sha256': sha(BASE), 'draft_sha256': sha(DRAFT), 'configuration_sha256': sha(MAN / 'PAPER_CONFIGURATION.json'),
    'definition': config['count_definition'], 'original_configuration_preserved': True,
    'interpretation': '各审阅报告的计数均可由不同过滤规则复现；不能将计数差异解释为稿件版本删除。原写作协议口径不追改。',
    'policies': {
        'original': '含章/节标题、表题、表注与所有正文；排除表格行、图题、图片、显示公式、附录等非六章内容。',
        'method_prefix': '在原口径上排除章标题及所有以表号开头的整行，包括若干结果论述段。',
        'domain_da_prefix': '领域审阅源码从第一章标题后截取正文；排除所有以表号开头的整行，保留其后章标题。对抗审阅报告同一近似总数，未据此推断其内部算法。',
        'eic_caption_note': '在原口径上仅排除实际表题与表注，保留以表号开头的论述段。',
        'perspective_no_headings': '在上一口径上排除全部章/节标题。'
    }, 'base': policy_base, 'revised': policy_new,
    'scope': '这是编辑计数字段的口径解释，不改变六章配额，不替代审阅判断或科学核查。'
}
save('count_definition_comparison.json', comparison)
rows = []
for title, target in config['section_targets'].items():
    a, b = policy_base['sections'][title]['original'], policy_new['sections'][title]['original']
    rows.append(f'| {title} | {target} | {a} | {b} | {100*(b/target-1):+.2f}% | 是 |')
baseline_table = '\n'.join(f"| {comparison['policies'][key]} | {policy_base['totals'][key]} | {policy_new['totals'][key]} |"
                           for key in comparison['policies'])
caption_note = sum(x['cjk'] for x in policy_base['classified_lines'] if x['kind'] in ('table_caption', 'table_note'))
body_removed = sum(x['cjk'] for x in policy_base['classified_lines'] if x['kind'] == 'body_prose')
assert (caption_note, body_removed) == (378, 806), (caption_note, body_removed)
report = f'''# 正文字数口径与章节配额说明

原完整稿SHA256：`{sha(BASE)}`。本轮修订稿SHA256：`{sha(DRAFT)}`。原`PAPER_CONFIGURATION.json`未修改；沿用汉字U+4E00—U+9FFF计数，只统计六个编号正文章节。

| 章节 | 既定目标 | 完整v1 | 修订稿 | 修订稿偏差 | 在±15%内 |
|---|---:|---:|---:|---:|---|
{chr(10).join(rows)}

修订稿合计{policy_new['totals']['original']}，相对11000目标为{100*(policy_new['totals']['original']/11000-1):+.2f}%，在±10%内。表格数据行、图片路径、图题、显示公式、摘要、参考文献及附录不计入；章/节标题、表题和表注沿用原计入规则。新增附录E/F没有被用于填充正文配额。

| 可复现的计数规则 | 完整v1 | 修订稿 |
|---|---:|---:|
{baseline_table}

完整v1的表题与表注共{caption_note}汉字；另有{body_removed}汉字的普通结果论述以“表2列出”“表3给出”等表号开头。把全部`^表数字`行过滤，会将这些论述一并删除。方法审阅所列10213、领域审阅所列10243、主编所列11056、跨学科审阅所列10833均可按上表规则复现，并非源稿SHA不同或文字遗失。领域审阅的10243具体对应`domain_evidence.py`第78—85行：总数从第一章标题后开始截取，保留第二章及以后的标题；对抗审阅报告同一近似总数，这里没有推断其未公开的内部计数算法。

本说明将口径差异显式化，不追改原配额、审阅合同或审阅人的评分。逐行分类、原行号和各规则的六章计数见`count_definition_comparison.json`。最终排版仍需按原口径核查，不把附录长度当作正文字数。
'''
(OUT / 'COUNT_DEFINITION_COMPARISON_CN.md').write_text(report, encoding='utf-8')

old_citations = readj(MAN / 'process/complete_v1/citation_contexts.json')
reference_lines = re.findall(r'^\[\d+\].+$', revised, re.M)
assert reference_lines == re.findall(r'^\[\d+\].+$', base, re.M)
assert len(reference_lines) == 13
contexts, evidence_contexts = [], []
section = ''
for no, line in enumerate(revised.splitlines(), 1):
    if line.startswith('## '):
        section = line[3:]
    if re.match(r'^\[\d+\]', line):
        continue
    for match in re.finditer(r'\[(\d+(?:,\d+)*)\]', line):
        numbers = [int(x) for x in match.group(1).split(',')]
        if not all(1 <= x <= 13 for x in numbers):
            # 例如新采样说明中的区间[0,1]，并非外部文献。
            continue
        contexts.append({'numbers': numbers, 'section': section, 'line': no, 'paragraph': line})
    codes = sorted(set(re.findall(r'E\d{2}', ''.join(re.findall(r'\[E[^\]]*\]', line)))))
    if codes:
        assert all(1 <= int(x[1:]) <= 17 for x in codes)
        evidence_contexts.append({'codes': codes, 'section': section, 'line': no, 'paragraph': line})
body_contexts = [x for x in contexts if re.match(r'^[1-6] ', x['section'])]
assert len(contexts) == len(old_citations['contexts']) == 18
assert len(body_contexts) == old_citations['body_citation_occurrences'] == 17
assert [(n, c['paragraph']) for c in contexts for n in c['numbers']] == [(c['number'], c['paragraph']) for c in old_citations['contexts']]
for new, old in zip(contexts, old_citations['contexts']):
    for key in ('key', 'source_scope', 'source_limits', 'verification_basis'):
        new[key] = old[key]
save('citation_contexts.json', {'draft_sha256': sha(DRAFT), 'references': old_citations['references'], 'contexts': contexts,
    'body_citation_occurrences': len(body_contexts), 'all_nonbibliography_occurrences': len(contexts), 'unique_references': 13,
    'data_evidence_contexts': evidence_contexts,
    'status': '13条题录、18处外部引用上下文均保持，继承已保存的阅读范围与题录证据；本轮新增E17内部证据映射。不是新一轮外部文献阅读全文或独立审查通过。'})
citation_md = ['# 本轮引用与证据上下文核对', '', f'绑定修订稿SHA256：`{sha(DRAFT)}`。', '',
    '13条题录逐字保留；六章内17处、全稿非题录18处外部引用均与完整v1对应。本轮没有新增外部文献，不用未读桥接文献装饰讨论。原阅读版本、摘要可用范围及不支持事项见JSON的references字段。', '']
for ctx in contexts:
    citation_md += [f"- 第{ctx['line']}行，{ctx['section']}，文献{','.join(map(str, ctx['numbers']))}：{ctx['paragraph']}"]
citation_md += ['', '内部数据证据扩展至E17；每一处的行号、完整上下文和映射另见JSON。引用上下文核对不能替代独立科学审查。', '']
(OUT / 'citation_contexts.md').write_text('\n'.join(citation_md), encoding='utf-8')

old_sources = readj(MAN / 'process/complete_v1/source_checks.json')['sources']
visual = readj(MAN / 'figures/analytic_layer_visual_check.json')
figure_checks = []
for path in re.findall(r'!\[[^\]]*\]\(([^)]+)\)', revised):
    p = Path(path)
    assert p.is_absolute() and p.exists()
    digest = sha(p)
    expected = old_sources.get(str(p))
    if expected is None and p.name == 'analytic_layer.png':
        expected = '32c820a18d9bfbd59024a495426c33fd648b19a080b19478e4fe17875caeee1f'
        assert expected in json.dumps(visual)
    assert digest == expected, (str(p), digest, expected)
    figure_checks.append({'path': str(p), 'sha256': digest, 'matches_frozen_figure_evidence': True})
assert len(figure_checks) == 4
save('figure_retention_checks.json', {'draft_sha256': sha(DRAFT), 'figures': figure_checks,
    'scope': '仅核四个已用PNG的文件与既有冻结证据一致；本轮未改图、未重新渲染或宣称视觉复审。'})
source = readj(OUT / 'source_evidence.json')
source.setdefault('initial_collection_status', source['status'])
source['status'] = '五份审阅均已读取；定向来源核查完成。修订回应待统一清单绑定，最终独立核验待执行。'
source['reviews_read'] = readj(OUT / 'revision_checks.json')['reviews_read']
save('source_evidence.json', source)
save('editing_audit.json', {'draft_sha256': sha(DRAFT), 'checked_local': datetime.now(timezone(timedelta(hours=8))).isoformat(),
    'five_counting_policies_reproduced': True, 'current_body_cjk': policy_new['totals']['original'],
    'reference_lines_unchanged': 13, 'all_external_citation_contexts': len(contexts), 'main_external_citation_contexts': len(body_contexts),
    'figure_hashes_retained': len(figure_checks), 'source_status_refreshed_without_rechecking_raw_files': True,
    'operations': {'training': 0, 'model_load': 0, 'reference_integration': 0, 'render': 0, 'git_mutation': 0}})
print(json.dumps({'body_cjk': policy_new['totals']['original'], 'policies_base': policy_base['totals'],
                  'contexts': len(contexts), 'figure_hashes': len(figure_checks)}, ensure_ascii=False, indent=2))

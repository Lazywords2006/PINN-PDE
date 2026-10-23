"""候选稿2的只读编辑与证据绑定；不导入科学计算运行库。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter
import copy
import hashlib
import json
import math
import re

OUT = Path(__file__).resolve().parent
MAN = OUT.parents[1]
ROOT = MAN.parent
EVID = ROOT / 'validation/final_numeric_provenance_20261023'
OLD = MAN / 'process/complete_revised1a'
BASE = MAN / 'drafts/delivery_candidate.md'
DRAFT = MAN / 'drafts/delivery_candidate2.md'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
readj = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat()
def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert not (OUT / 'FROZEN_CANDIDATE2_MANIFEST.json').exists()
digest = sha(DRAFT)
assert digest == '59d1db8fd5c8c468783e98ba6db1bcde0e49e7f923e82afa6e2d9e6dbf383cd4'
base, revised = [p.read_text(encoding='utf-8') for p in (BASE,DRAFT)]
changes = readj(OUT / 'change_map.json')['changes']
restored = revised
for c in reversed(changes): restored = restored.replace(c['new'], c['old'])
assert restored == base
config = readj(MAN / 'PAPER_CONFIGURATION.json')

# 原统计口径不变；本轮正文仅§3.4一个段落更新。
def count_sections(text):
    sections = {}
    for title, target in config['section_targets'].items():
        start = text.index('## ' + title + '\n')
        end = text.find('\n## ', start+4)
        block = text[start:end if end != -1 else None]
        block = re.sub(r'\\\[.*?\\\]', '', block, flags=re.S)
        block = re.sub(r'<!--.*?-->', '', block, flags=re.S)
        lines = [s for s in block.splitlines() if not s.startswith(('|','图','!['))]
        n = len(re.findall(r'[\u4e00-\u9fff]', '\n'.join(lines)))
        sections[title] = {'target_cjk':target, 'actual_cjk':n,
            'deviation_percent':round(100*(n/target-1),2), 'within_15_percent': abs(n/target-1)<=.15}
    return sections
oldcounts = count_sections(base)
sections = count_sections(revised)
assert sum(x['actual_cjk'] for x in oldcounts.values()) == 11487
total = sum(x['actual_cjk'] for x in sections.values())
counts = {'base_sha256':sha(BASE), 'draft_sha256':digest,
    'configuration_sha256':sha(MAN/'PAPER_CONFIGURATION.json'),
    'definition':config['count_definition'],
    'implementation_notes':'含章/节标题、表题及表注；排除表格数据行、图题、图片、显示公式、非六章内容。U+4E00—U+9FFF。',
    'actual_body_cjk':total, 'target_body_cjk':11000,
    'deviation_percent':round(100*(total/11000-1),2), 'within_10_percent':abs(total/11000-1)<=.1,
    'sections':sections, 'base_sections':oldcounts,
    'appendices_used_to_fill_quota':False}
assert counts['within_10_percent'] and all(x['within_15_percent'] for x in sections.values())
save('word_counts.json',counts)
md = ['# 候选稿2字数与原配额', '', f'稿件SHA256：`{digest}`。原配置与既定统计口径不变；附录D新增核验记录不计正文。', '',
    '| 章节 | 原目标 | 父候选 | 候选稿2 | 偏差 | ±15% |', '|---|---:|---:|---:|---:|---|']
for title,row in sections.items():
    md.append(f"| {title} | {row['target_cjk']} | {oldcounts[title]['actual_cjk']} | {row['actual_cjk']} | {row['deviation_percent']:+.2f}% | 满足 |")
md += ['', f'合计{total}汉字，较原11000目标为{counts["deviation_percent"]:+.2f}%，在±10%内。原候选11487汉字；差值仅来自§3.4核验阶段说明。', '',
    '计数包含章/节标题、表题和表注，排除表格数据行、图片路径、图题、显示公式、摘要、参考文献、声明与附录。此前不同审阅计数口径的解释仍见已冻结complete_revised1/COUNT_DEFINITION_COMPARISON_CN.md；本版不追改该报告。', '']
(OUT/'WORD_COUNTS_CN.md').write_text('\n'.join(md),encoding='utf-8')

# 13条参考文献和18段外部引用不变；新增E18不属于新增外部文献。
old_citations = readj(OLD/'citation_contexts.json')
assert re.findall(r'^\[\d+\].+$',revised,re.M) == re.findall(r'^\[\d+\].+$',base,re.M)
contexts, data_contexts = [], []
section=''
for no,line in enumerate(revised.splitlines(),1):
    if line.startswith('## '): section=line[3:]
    if re.match(r'^\[\d+\]',line): continue
    for match in re.finditer(r'\[(\d+(?:,\d+)*)\]',line):
        numbers=[int(n) for n in match.group(1).split(',')]
        if all(1<=n<=13 for n in numbers):
            contexts.append({'numbers':numbers,'section':section,'line':no,'paragraph':line})
    codes=sorted(set(re.findall(r'E\d{2}', ''.join(re.findall(r'\[E[^\]]*\]',line)))))
    if codes: data_contexts.append({'codes':codes,'section':section,'line':no,'paragraph':line})
assert len(contexts)==len(old_citations['contexts'])==18
for new,old in zip(contexts,old_citations['contexts']):
    assert (new['numbers'],new['paragraph'])==(old['numbers'],old['paragraph'])
    for key in ('key','source_scope','source_limits','verification_basis'):new[key]=old[key]
mapped=set(re.findall(r'^\| (E\d{2}) \|',revised,re.M))
used={code for c in data_contexts for code in c['codes']}
assert used <= mapped and 'E18' in used
citation={'draft_sha256':digest,'parent_sha256':sha(BASE),'references':old_citations['references'],
    'contexts':contexts,'data_evidence_contexts':data_contexts,
    'body_citation_occurrences':sum(bool(re.match(r'^[1-6] ',c['section'])) for c in contexts),
    'all_nonbibliography_occurrences':len(contexts),'unique_references':13,
    'external_reference_text_and_contexts_unchanged':True,'mapped_evidence_codes':sorted(mapped),'used_evidence_codes':sorted(used),
    'verification_scope':'沿用已核原文和题录，本轮逐字对照上下文并更新行位；未重新通读原文。E18为本地实际执行来源。'}
save('citation_contexts.json',citation)
md=['# 候选稿2引用上下文', '', f'稿件SHA256：`{digest}`。13条题录与18处外部引用上下文逐字不变，正文17处。原阅读版本及支持边界继承已冻结证据；本轮新增E18只对应本地执行记录。', '']
for c in contexts:
    md += [f"## 文献{','.join(map(str,c['numbers']))}，第{c['line']}行",'',c['paragraph'],'',
        '支持范围：'+'；'.join(c['source_scope']), '', '边界：'+'；'.join(c['source_limits']),'']
md += ['## E18的新增上下文', '']
for c in data_contexts:
    if 'E18' in c['codes']:md += [f"第{c['line']}行，{c['section']}：",'',c['paragraph'],'']
(OUT/'citation_contexts.md').write_text('\n'.join(md),encoding='utf-8')

# 原数值表、公式、图和主结论全保留；只允许证据映射表新增E18和更正E12时点。
tables=lambda s:re.findall(r'(?:^\|.*\n)+',s,re.M)
bt,nt=tables(base),tables(revised)
assert len(bt)==len(nt)==14
table_changes=[i+1 for i,(a,b) in enumerate(zip(bt,nt)) if a!=b]
assert len(table_changes)==1 and '| E18 |' in nt[table_changes[0]-1]
assert tables(base[:base.index('## 参考文献')])==tables(revised[:revised.index('## 参考文献')])
assert len(tables(revised[:revised.index('## 参考文献')]))==8
for a in nt:
    widths={len(line.split('|')) for line in a.splitlines()}
    assert len(widths)==1
formula=lambda s:re.findall(r'\\\[.*?\\\]',s,re.S)
assert formula(base)==formula(revised)
assert revised.count('\\[')==revised.count('\\]')
assert revised.count('\\(')==revised.count('\\)')
assert not any(x in revised for x in ('ᵧ','ₜ'))
figure_paths=lambda s:re.findall(r'!\[[^\]]*\]\(([^)]+)\)',s)
assert figure_paths(base)==figure_paths(revised)
fig=readj(OLD/'figure_retention_checks.json')
fig['parent_sha256']=sha(BASE)
fig['draft_sha256']=digest
for x in fig['figures']: assert sha(Path(x['path']))==x['sha256']
save('figure_retention_checks.json',fig)

# 只读实际复算摘要，逐条验证比较、退出和计数，不加载权重或重做参考积分。
report=readj(EVID/'FINAL_NUMERIC_REPORT.json')
full=readj(EVID/'evidence/full/summary.json')
held=readj(EVID/'evidence/heldout/summary.json')
empty_sha=hashlib.sha256(b'').hexdigest()
executions=full['reference_executions']+full['model_executions']+held['executions']
assert len(executions)==270
assert all(x['actual_returncode']==0 and x['stderr_sha256']==empty_sha for x in executions)
assert len(full['rows'])==206 and len(held['rows'])==52
assert Counter(x['restore_status'] for x in full['rows'])==report['restore_status_counts']
def verify_comparisons(rows):
    n=0
    for row in rows:
        assert row['all_comparisons_pass'] and row['training_calls']==0
        for group in row['comparisons'].values():
            for comparison in group.values():
                assert comparison['passed']
                assert len(comparison['actual'])==len(comparison['recorded'])==len(comparison['tolerance_per_value'])
                for a,b,d,tol in zip(comparison['actual'],comparison['recorded'],comparison['absolute_difference'],comparison['tolerance_per_value']):
                    assert math.isfinite(a) and math.isfinite(b)
                    assert abs(a-b)==d and d<=tol
                    assert math.isclose(tol,1e-9+1e-5*abs(b),rel_tol=1e-14,abs_tol=1e-30)
                    n+=1
    return n
assert verify_comparisons(full['rows'])==4120
assert verify_comparisons(held['rows'])==416
assert all(x['model_and_input_unchanged'] and x['parameter_gradients_not_accumulated'] and x['point_counts_match'] for x in held['rows'])
assert all(x['input_unchanged'] and x['model_state_unchanged'] for x in full['rows'])
assert not any(x['job'][1].startswith('E4') for x in held['rows'])
assert Counter(x['job'][0] for x in held['rows'])=={'pirate':4,'final_ic_v1':18,'sensitivity_tau003_v1':6,'sensitivity_tau03_v1':6,'final_soap64_v1':18}
assert all(x['training_calls']==0 for x in (full,held))
assert all(x['warning_count']==0 and not x['warnings'] and not x['historical_training_history_reconstructed'] for x in (full,held))
rounded={
    'N64体':(report['body_trace_max_abs_differences']['n64_gl200']['vol'],'1.732e-12'),
    'N64迹':(report['body_trace_max_abs_differences']['n64_gl200']['trace'],'2.828e-12'),
    'N96体':(report['body_trace_max_abs_differences']['n96_gl400']['vol'],'1.846e-11'),
    'N96迹':(report['body_trace_max_abs_differences']['n96_gl400']['trace'],'4.749e-11'),
    '参考自检':(report['reference_N48_N96_worst_max_abs'],'3.292e-10')}
assert all(format(v,'.3e')==s for v,s in rounded.values())
assert [format(report['elapsed_seconds'][k],'.3f') for k in ('full','heldout')]==['351.939','89.846']
supervisors={k:readj(EVID/f'supervisors/{k}/execution.json') for k in ('full','heldout')}
assert all(x['actual_returncode']==0 and x['stderr_sha256']==empty_sha for x in supervisors.values())
manifest=readj(EVID/'FINAL_DELIVERY_SHA256.json')
source_names=['FINAL_NUMERIC_REPORT.md','FINAL_NUMERIC_REPORT.json','README.md','plan.json','heldout_plan.json',
    'recompute_saved_models.py','recompute_heldout.py','launch_logged.ps1',
    'evidence/full/summary.json','evidence/heldout/summary.json',
    'supervisors/full/execution.json','supervisors/heldout/execution.json']
selected={str(EVID/p):sha(EVID/p) for p in source_names}
assert all(selected[str(EVID/p)]==manifest['sha256'][p] for p in source_names)
selected[str(EVID/'FINAL_DELIVERY_SHA256.json')]=sha(EVID/'FINAL_DELIVERY_SHA256.json')
numeric={'draft_sha256':digest,'scope':'本作者只读解析本次真实执行报告，未自行执行模型或参考解。',
    'body_trace_records':206,'body_trace_scalars_checked':4120,'heldout_records':52,'heldout_scalars_checked':416,
    'actual_child_exits_checked':270,'all_zero_exit':True,'all_child_stderr_empty':True,'supervisor_exit_checks':{k:x['actual_returncode'] for k,x in supervisors.items()},
    'training_calls_in_execution_reports':0,'writer_training_calls':0,
    'rounded_values':rounded,'new_report_hashes':selected,
    'table_blocks_total':14,'unchanged_table_blocks':13,'only_changed_table_block':table_changes[0],
    'eight_main_tables_unchanged':True,'all_display_math_unchanged':True,
    'historical_training_history_reconstructed':False,'final_mode1_decision':'RESERVED_TO_INDEPENDENT_FINAL_REVIEWER'}
save('numeric_evidence_checks.json',numeric)

# 普通re-review判定保留在其原稿；为25项只建立新稿定位，不把旧Accept扩写为本次最终门通过。
prior_dir=MAN/'reviews/revision1/independent_verification'
prior=readj(prior_dir/'VERIFICATION_RESULTS.json')
bridges=[]
for item in prior['items']:
    locations=[]
    for loc in item['author_revision_locations']:
        p=Path(loc['file'])
        copied=copy.deepcopy(loc)
        if p.name=='complete_revised1a.md':
            anchor=loc['exact_anchor']
            if anchor not in revised:
                for c in changes:anchor=anchor.replace(c['old'],c['new'])
            assert revised.count(anchor)==1,(item['id'],anchor)
            copied.update(file=str(DRAFT),line=revised[:revised.index(anchor)].count('\n')+1,sha256=digest,exact_anchor=anchor)
        else:
            assert sha(p)==loc['sha256']
        locations.append(copied)
    bridges.append({'id':item['id'],'priority':item['priority'],
        'prior_independent_status':item['independent_status'],
        'prior_status_scope':'仅对应complete_revised1a及原普通re-review；不自动等于候选稿2最终门通过。',
        'current_locations':locations,'scientific_response_disposition_changed':False,
        'current_provenance_delta_verification':'PENDING_FINAL_INCREMENTAL_REVIEW'})
assert len(bridges)==25
assert Counter(x['prior_independent_status'] for x in bridges)=={'FULLY_ADDRESSED':21,'PARTIALLY_ADDRESSED':1,'NOT_ADDRESSED':3}
save('prior_25_items_location_bridge.json',{'draft_sha256':digest,'prior_report':str(prior_dir/'VERIFICATION_REPORT_CN.md'),
    'prior_report_sha256':sha(prior_dir/'VERIFICATION_REPORT_CN.md'),'items':bridges})

response_items=[
    {'id':'PROV-1','concern':'当前表格数值缺少本轮可审计重算生产链。','response':'新增E18及附录D真实206项保存权重体/迹复算：两套设置、五时刻、4120比较和原容差；同时载入报告、逐值摘要和完整清单，不新增训练。','anchors':['产物核验保留结果','| E18 |','2026-10-23另行完成保存权重的实际数值复算']},
    {'id':'PROV-2','concern':'已有独立点残差和实际退出/警告仍需执行证据。','response':'补入全部52条已有残差记录、416比较及270子进程和2父进程实际退出0、本次warning为0和stderr为空；只限本次，不追填旧日志。','anchors':['同次补核覆盖全部已有52项独立检验点残差记录']},
    {'id':'PROV-3','concern':'不能将复用实现误称独立PDE算法验证，不能补造E4缺失分支。','response':'明确前向与参考解复用冻结项目实现；新检查器独立重载、求积/残差与比较。保留20项E4仅体/迹范围，52残差排除这些模型，旧v不可重建。','anchors':['本次严格重载覆盖110项旧完整模型','小预算筛选未满足原三倍条件；完整预算是在已见筛选失败后按E4_PROTOCOL']},
    {'id':'PROV-4','concern':'旧“未重载”语句与新事实的时点冲突。','response':'§3.4、证据映射后与附录D/E仅增加明确阶段指代；旧先前复核事实、训练日志缺口及所有原科学表格、公式、结论保持。','anchors':['| E12 |','原始训练结果仍位于研究根目录','历史复算来源分别为130项既有模型审查','第二阶段三个tag分别为']},
    {'id':'PROV-5','concern':'补充数值执行不能由作者宣布完整性终审通过。','response':'首轮最终完整性FAIL与原full_v1 ABORT原件保留；本轮仅提供实际证据。候选稿2最终Mode1/完整性及排版结论由独立核验者另行给出，人类作者声明继续待确认。','anchors':['作者姓名、单位、通讯作者与作者贡献：待作者确认','自动代理之间的独立核查属于内部自动审查']},
]
for item in response_items:
    item['status']='AUTHOR_ADDRESSED_AWAITING_FINAL_INCREMENTAL_REVIEW'
    item['locations']=[]
    for anchor in item.pop('anchors'):
        assert revised.count(anchor)==1
        item['locations'].append({'file':str(DRAFT),'line':revised[:revised.index(anchor)].count('\n')+1,'exact_anchor':anchor,'sha256':digest})
responses={'draft_sha256':digest,'base_sha256':sha(BASE),'generated_local':now(),
    'scope':'限定数值溯源补充，非新科学实验或重新进行五人panel。',
    'first_final_integrity_report_preserved':str(MAN/'integrity/final_revised1/FINAL_INTEGRITY_REVIEW_CN.md'),
    'full_v1_status_preserved':'ABORT; usable 2/5; no full-panel editorial decision',
    'final_integrity_decision':'PENDING_INDEPENDENT_INCREMENTAL_REVIEW',
    'items':response_items,'change_map_file':'change_map.json','prior_25_items_bridge':'prior_25_items_location_bridge.json'}
save('RESPONSES_TO_FINAL_PROVENANCE.json',responses)
md=['# 数值溯源补充的逐项响应', '', f'稿件：[{DRAFT.name}](<{DRAFT.as_posix()}>), SHA256 `{digest}`。父候选SHA256 `{sha(BASE)}`。', '',
    '本次仅纳入真实完成且已冻结的206项体/迹和52项残差复算。没有新增训练、HPO或数值表；首轮最终完整性FAIL及原full_v1的ABORT、2/5可用、无全轮编辑裁决均保留。下列为作者修订回应，最终增量核验尚待独立判断。', '']
for item in response_items:
    md += ['## '+item['id'], '', '问题：'+item['concern'], '', '答复：'+item['response'], '', '位置：','']
    for loc in item['locations']:md.append(f"- [稿件第{loc['line']}行](<{DRAFT.as_posix()}:{loc['line']}>)")
    md += ['','状态：作者已补充，待独立最终增量核验。','']
md += ['## 原25项普通修订的保留', '',
    '已读原独立VERIFICATION_REPORT_CN.md：其Accept只绑定complete_revised1a及其对应范围，14项必修FULLY_ADDRESSED，11项建议均回应（7完整、1部分、3不采纳且理由可接受）。本次逐项为25条原验收位置建立新稿行位和SHA映射，科学答复及采纳处置不变；不把旧Accept转写为候选稿2完整性通过。详见prior_25_items_location_bridge.json。', '',
    f'候选稿2正文{total}汉字，各章均在原±15%内，总数在11000±10%内。13条题录、18处外部引用上下文、8张主表、全部显示公式及4幅图保留；14个表块中仅证据映射表发生文字变化。', '',
    'PREPARATION_206_CN.md保留准备时点的52项待证据状态；随后实际完成的52项及其正式哈希由本文件和E18更新，未覆盖准备记录。', '']
(OUT/'RESPONSES_TO_FINAL_PROVENANCE_CN.md').write_text('\n'.join(md),encoding='utf-8')

protected=readj(OUT/'protected_before.json')
assert all(sha(Path(p))==h for p,h in protected.items())
save('protected_after.json',protected)
sources={**selected, str(MAN/'PAPER_CONFIGURATION.json'):sha(MAN/'PAPER_CONFIGURATION.json'),
    str(prior_dir/'VERIFICATION_REPORT_CN.md'):sha(prior_dir/'VERIFICATION_REPORT_CN.md'),
    str(prior_dir/'VERIFICATION_RESULTS.json'):sha(prior_dir/'VERIFICATION_RESULTS.json')}
source_checks={'draft_sha256':digest,'generated_local':now(),'source_sha256':sources,
    'numeric_archive_manifest_entries':len(manifest['sha256']),
    'numeric_archive_selected_entries_writer_rehashed':len(source_names),
    'archive_scope':'本作者针对12个已用来源复核其当前哈希与冻结2300文件清单；不把清单解析说成自行重哈希全部2300文件。',
    'source_producer_executed_by_writer':False,'old_protected_unchanged':len(protected)}
save('source_checks.json',source_checks)
checks={'draft_sha256':digest,'base_sha256':sha(BASE),'generated_local':now(),
    'whitelisted_replacements':len(changes),'reverse_replacements_equal_base':True,
    'body_cjk':total,'all_section_quotas_pass':True,'eight_main_tables_byte_identical':True,
    'thirteen_other_table_blocks_byte_identical':True,'all_display_formula_blocks_byte_identical':True,
    'thirteen_references_byte_identical':True,'eighteen_external_contexts_byte_identical':True,
    'four_figures_paths_and_hashes_unchanged':True,'prior_review_items_rebound':25,
    'old_protected_files_unchanged':len(protected),'operations':{'training':0,'model_load':0,'reference_solve':0,'render':0,'source_mutation':0,'git_mutation':0},
    'final_integrity_status':'PENDING_INDEPENDENT_INCREMENTAL_REVIEW','render_status':'PENDING_PARENT_COORDINATION','final_frozen':False}
save('candidate2_checks.json',checks)
assert not any(x in __import__('sys').modules for x in ('torch','numpy','scipy'))
print(json.dumps({'sha256':digest,'body_cjk':total,'section_cjk':[x['actual_cjk'] for x in sections.values()],
    'new_evidence_scalars':4120+416,'child_exit_checks':270,'prior_item_locations':sum(len(x['current_locations']) for x in bridges),
    'protected':len(protected)},ensure_ascii=False))

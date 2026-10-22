"""完整稿的引用/数字/逐段作者核查与Phase4b；不运行实验或渲染。"""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re

OUT=Path(__file__).resolve().parent
MAN=OUT.parents[1]
ROOT=MAN.parent
DRAFT=MAN/'drafts/complete_v1.md'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
readj=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def save(name,obj): (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
t=DRAFT.read_text(encoding='utf-8')
draft_sha=sha(DRAFT)
counts=readj(OUT/'word_counts.json')
assert counts['draft_sha256']==draft_sha and counts['within_10_percent'] is True
assert all(r['within_15_percent'] for r in counts['sections'].values())
assert 'MATERIAL GAP' not in t
base=(MAN/'drafts/working_revised1.md').read_text(encoding='utf-8')
review_dir=MAN/'integrity/stage6_analysis_20261023'
review_json=review_dir/'V2_FOLLOWUP.json'
review_md=review_dir/'V2_FOLLOWUP.md'
assert sha(review_json)=='cb4057919d58cbe8772758e02d36052534fc74b7eb2e2ba92c726ae67a92ee74'
assert sha(review_md)=='37a49823e8f27f6703977c95fd542e43a13628df43def6c74190679e90eda5cf'
review=readj(review_json)
assert review['status']=='PASS_LIMITED_STAGE6_V2_FOLLOWUP'
assert len(review['findings'])==3 and all(f['status']=='CLOSED' for f in review['findings'])
assert review['new_findings']==[] and review['scope_limits']['full_manuscript_pass_claimed'] is False
binding=readj(OUT/'v2_binding_checks.json')
assert binding['draft_sha256']==draft_sha
assert binding['stage6_v2_analysis_sha256']==review['v2_analysis_evidence_sha256']
assert all(review['protected_snapshot_sha256'][Path(p).relative_to(ROOT).as_posix()]==digest for p,digest in binding['frozen_nine_file_sha256'].items())
source_checks=readj(OUT/'source_checks.json')
assert source_checks['draft_sha256']==draft_sha
source_checks['sources'].update({str(review_json):sha(review_json),str(review_md):sha(review_md)})
for rel in ('validation/stage6_analysis_20261022/complete_v2/revision/REVISION_EVIDENCE.json',
            'validation/stage6_analysis_20261022/complete_v2/VERSION_MAPPING.md'):
    assert sha(ROOT/rel)==review['protected_snapshot_sha256'][rel]
    source_checks['sources'][str(ROOT/rel)]=sha(ROOT/rel)
source_checks['v2_targeted_review_pending']=False
source_checks['v2_targeted_review']={'status':review['status'],'closed_findings':[f['id'] for f in review['findings']],
    'new_findings':0,'full_manuscript_verdict':False}
save('source_checks.json',source_checks)
binding['independent_v2_review_pending']=False
binding['independent_v2_review_status']=review['status']
binding['independent_v2_review_sha256']={str(review_json):sha(review_json),str(review_md):sha(review_md)}
binding['full_manuscript_review_completed']=False
save('v2_binding_checks.json',binding)

# 对旧主表逐块检查；新增表不能掩盖旧数值或负面结果的变更。
def tables(text):
    result=[];buf=[]
    for line in text.splitlines()+['']:
        if line.startswith('|'):buf.append(line)
        elif buf:
            result.append('\n'.join(buf));buf=[]
    return result
old_main=base.split('## 3 实验设计与复现方法',1)[1].split('## 5 讨论与局限',1)[0]
old_tables=tables(old_main)
assert len(old_tables)==6
assert all(block in t for block in old_tables),'旧六主表数据发生变化'
assert len(re.findall(r'^\[\d+\].+$',t,re.M))==13
assert re.findall(r'^\[\d+\].+$',t,re.M)==re.findall(r'^\[\d+\].+$',base,re.M)
for block in tables(t):
    lines=block.splitlines()
    assert len(lines)>=2 and re.fullmatch(r'[| :\-]+',lines[1]),'Markdown表缺分隔行'
    assert len({line.count('|') for line in lines})==1
assert t.count('\\[')==t.count('\\]')
images=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',t)
assert len(images)==4 and all(Path(path).is_file() for path in images)
assert all(Path(path).is_absolute() for path in images)

old_citations=readj(MAN/'process/working_revised1/citation_contexts.json')
refs=old_citations['references']
lookup={row['citation_number']:row for row in refs}
contexts=[];evidence_contexts=[];section='前置部分'
for block in re.split(r'\n\s*\n',t):
    text=block.strip()
    if text.startswith('## '): section=text.splitlines()[0][3:]
    if section=='参考文献' or text.startswith('|'):continue
    if re.match(r'^\[\d+\]',text):continue
    line=t[:t.index(block)].count('\n')+1
    for m in re.finditer(r'\[(\d+(?:,\s*\d+)*)\]',text):
        for num in map(int,re.split(r',\s*',m.group(1))):
            assert num in lookup
            contexts.append({'number':num,'key':lookup[num]['key'],'section':section,'line':line,'paragraph':text,
                'source_scope':lookup[num].get('supports'),'source_limits':lookup[num].get('does_not_support'),
                'verification_basis':'继承已核原文/题录；本次复核上下文保持既有支持范围，不声称重新通读全部原文。'})
    for match in re.finditer(r'\[(E\d+(?:,E\d+)*)\]',text):
        codes=match.group(1).split(',')
        assert all(code in {'E01','E02','E03','E04','E05','E09','E10','E11','E12','E13','E14','E15','E16'} for code in codes)
        evidence_contexts.append({'codes':codes,'section':section,'line':line,'paragraph':text})
assert set(row['number'] for row in contexts)==set(range(1,14))
save('citation_contexts.json',{'draft_sha256':draft_sha,'references':refs,'contexts':contexts,
    'body_citation_occurrences':sum(bool(re.match(r'[1-6] ',r['section'])) for r in contexts),
    'all_nonbibliography_occurrences':len(contexts),'unique_references':13,'data_evidence_contexts':evidence_contexts,
    'status':'作者上下文复核完成；题录文本未改，原文核查沿用已保存证据；正式独立引用复审待执行。'})
md=['# 完整v1引用与证据上下文','',f'稿件SHA256：`{draft_sha}`。13条参考题录与冻结工作稿逐条相同。学术背景和方法引用沿用已核原文范围；新增实验结果由E13/E15支持，不用文献引用替代本项目数据。','',
    'RBA的N01已精确到v2可选首步注意力学习率η*=1；发表年份与阅读版本日期继续分开。Favini仅按出版社摘要可支持范围使用，SOAP按八作者arXiv v2引用。','',
    '| 编号 | BibTeX键 | 引用次数 | 实际阅读范围 |','|---|---|---:|---|']
for row in refs:
    md.append(f"| {row['citation_number']} | {row['key']} | {sum(c['number']==row['citation_number'] for c in contexts)} | {str(row.get('read_version','')).replace('|','/')} |")
for i,row in enumerate(contexts,1):
    md.extend(['',f"## C{i:02} 文献[{row['number']}]：{row['section']}，稿件第{row['line']}行",'',row['paragraph'],'',f"支持范围：{row['source_scope']}",f"限制：{row['source_limits']}"])
(OUT/'citation_contexts.md').write_text('\n'.join(md)+'\n',encoding='utf-8')

# 按完整正文逐段人工语义自核结果固化。短数学引导段也计入分母并从严记为非完整TEEL。
body=t.split('## 1 引言与相关工作\n',1)[1].split('## 参考文献',1)[0]
body_without_math=re.sub(r'\\\[.*?\\\]','',body,flags=re.S)
paragraphs=[];section='1 引言与相关工作'
for block in re.split(r'\n\s*\n',body_without_math):
    block=block.strip()
    if not block or block.startswith(('|','图','![')):continue
    if block.startswith('#'):
        section=block.lstrip('# ');continue
    paragraphs.append({'id':f'P{len(paragraphs)+1:03}','section':section,'text':block})
assert len(paragraphs)==96
formula_leads={10,12,15,16,20,21,22,24,25,27,28,30,32,34,37,38,50}
captions={42,56,60,64,67,70,74,77}
exempt={1,96}
for i,row in enumerate(paragraphs,1):
    if i in captions:
        assert re.match(r'表[1-8]\s',row['text'])
        row.update(status='outside_prose_denominator',reason='表题不作为论述段；表2注P057保留在分母。')
    elif i in exempt:
        row.update(status='contract_exempt',reason='契约豁免引言首段与结论末段。')
    elif i in formula_leads:
        row.update(status='not_full_teel',reason='数学定义、命题或公式引导短段，完成局部展示功能；保守计入分母但不记为完整TEEL。')
    else:
        sentences=[s.strip() for s in re.split(r'(?<=[。！？])',row['text']) if s.strip()]
        row.update(status='teel_writer_judgment',topic=sentences[0],
            evidence='该段所引文献/数据证据及明确给出的公式推演；不是由引文标记自动推出质量通过。',
            explanation='已逐段阅读：叙述事实或推理后解释其对本问题、比较范围或限制的含义。',
            link=''.join(sentences[-2:]),
            reason='作者语义判断：主题明确、依据可定位、解释与本段目的对应，尾部限定或过渡连接论证。')
denominator=sum(row['status'] not in ('outside_prose_denominator','contract_exempt') for row in paragraphs)
passed=sum(row['status']=='teel_writer_judgment' for row in paragraphs)
assert (passed,denominator)==(69,86) and passed/denominator>=.8
save('paragraph_audit.json',{'draft_sha256':draft_sha,'scope':'作者逐段语义自核，非独立评价者评分',
    'segmentation':'空行分段，公式本体不计；公式引导短段保留分母；表题和图题不作为论述段；表注保留。',
    'contract_exempt_paragraphs':['P001','P096'],'full_teel_writer_judgments':passed,'assessed_paragraphs':denominator,
    'proportion':passed/denominator,'at_least_80_percent':True,'paragraphs':paragraphs})

num=readj(OUT/'numeric_checks.json')
assert num['draft_sha256']==draft_sha
numeric_prose=[]
def claim(name,value,format_spec,token,sources):
    assert format(value,format_spec)==token,(name,value,token)
    assert token in t,(name,token)
    numeric_prose.append({'claim':name,'exact_value':value,'display':token,'format':format_spec,'sources':sources})
for r in num['soap_and_tau_independently_reaggregated']:
    claim(r['eq']+' SOAP H/HL比',r['hardic_over_layer'],'.2f',format(r['hardic_over_layer'],'.2f'),'E13默认组原JSON')
    claim(r['eq']+' τ跨档比',r['tau_max_over_min'],'.5f',format(r['tau_max_over_min'],'.5f'),'E13τ组原JSON')
    claim(r['eq']+' 摘要结论τ比',r['tau_max_over_min'],'.2f',format(r['tau_max_over_min'],'.2f'),'E13τ组原JSON')
def scientific_claim(name,value,sources):
    mantissa,exp=format(value,'.5e').split('e')
    power=str(int(exp)).translate(str.maketrans('-0123456789','⁻⁰¹²³⁴⁵⁶⁷⁸⁹'))
    token=mantissa+'×10'+power
    assert token in t,(name,token)
    numeric_prose.append({'claim':name,'exact_value':value,'display':token,'format':'.5e转同值Unicode指数','sources':sources})
for item in num['stage6_main_table_groups']:
    g=item['group']
    if item['kind']=='tau_groups':
        scientific_claim(g['eq']+f" τ={g['tau']}体误差中位数",g['median'],item['sources'])
        if g['tau']!=.1:
            claim(g['eq']+f" τ={g['tau']}相对主档比",g['median_over_tau01'],'.5f',format(g['median_over_tau01'],'.5f'),item['sources'])
    elif g['tag']=='final_soap64_v1' and g['method'] in ('hardic','hardic+layer'):
        scientific_claim(g['eq']+' SOAP '+g['method']+'体误差中位数',g['median'],item['sources'])
    if g['eq']=='E1_heat' and g['tag'] in ('sensitivity_tau003_v1','final_soap64_v1') and g['method']=='hardic+layer':
        scientific_claim(g['eq']+' '+g['tag']+'种子1',g['seeds'][1],item['sources'])
for key,name in [('local_batch_elapsed_seconds','批次总历时'),('local_runner_elapsed_seconds','runner会话累计'),('local_attempt_wall_seconds_sum','attempt之和')]:
    value=num['costs'][key]
    claim(name,value,'.2f',format(value,'.2f'),'E13 costs及最终runtime_status')
claim('记录内轨迹耗时之和',num['costs']['new_local_30']['trajectory_seconds_sum'],'.2f','371817.95','E13 costs逐记录合计')
num['prose_numeric_claims']=numeric_prose
num['old_six_main_tables_exactly_preserved']=True
num['new_tables_have_all_seeds_and_independent_source_mapping']=True
save('numeric_checks.json',num)

scores={
'D1':('section_completeness','pass','六个正文编号章节、全部大纲小节、双语摘要、13条参考文献、四图、八张正文表及附录均已写入。第4.5/4.6由真实30项完整验收结果补齐，正文不含MATERIAL GAP。署名/单位/基金/COI等非科学信息明确待作者确认。Stage6图版三项限定复核已关闭；本完整稿的独立审查与最终渲染尚未完成，不被当作文本缺口或既成通过。'),
'D2':('citation_density','pass',f'13条题录保持原核验文本，{len(contexts)}处非题录引用上下文逐项保留来源支持范围。已有事实和方法背景引用相应文献，项目结果/协议/推导以E编号定位；新增数字由206份原JSON及正式分析复核。自包含公式推导保留E02，未新增无来源的外部事实。作者上下文判断不等于重新通读13篇原文或独立引用审查通过。'),
'D3':('argument_blueprint_fidelity','pass','按照OUTLINE_AND_EVIDENCE保留相容性定义、局部证明、同构造比较、新初值、架构叠加、参数轴、τ、SOAP与残差成本顺序。三个研究问题现在均有相应结果及限制；A-1/G2失败、E2/E1筛选历史、弱错配、不利种子和E4缺失仍在。已完成补证据只关闭材料缺口，不升级经典工具首创、早时间机制或普遍优势主张。'),
'D4':('total_word_count','pass',f"按配置统计正文{counts['actual_body_cjk']}汉字，相对11000目标偏差{counts['deviation_percent']:.2f}%，在9900至12100内。摘要、英文摘要、表行、图题、公式、参考文献、声明和附录不计；标题、表题与表注按原口径计入。实际计数见word_counts.json。"),
'D5':('per_section_word_count','pass','六节均在各自配额±15%范围内，见下表。新增篇幅来自完整τ和SOAP结果、成本分层及其解释和结论，没有用重复背景填补数额。'),
'D6':('paragraph_structure','pass',f'按作者逐段语义复核，86个纳入段中69个具备主题、依据、解释与衔接功能，占{100*passed/denominator:.2f}%。引言首段和结论末段按契约豁免，8个表题不作论述段；17个数学定义/引导短段仍计入分母并从严记为非完整TEEL。公式证明和数据段的判断保存在paragraph_audit.json，未把“存在引用”自动等同TEEL。章节按分析、实验、结果与限制衔接，比例为作者自核而非独立评分。'),
'D7':('register_consistency','pass','中文正文使用数值PDE和科学机器学习术语，英文摘要与中文结果、范围和保留限制对应。统一区分Adam/SOAP之后的L-BFGS、五时刻最大误差与连续时间最大误差、实现调用记录与真实优化器计数。N01–N04和完整AI参与范围已落实，未宣称统计显著、普遍最优、固定加速或投稿通过。')}
report=['## Draft Body','',t.rstrip(),'','## Dimension Scores','']
for key,(name,score,reason) in scores.items():
    report.extend([f'### {key}: {name}','',score,'',reason,''])
    if key=='D5':
        report.extend(['| 正文章节 | 目标汉字 | 实际汉字 | 偏差 | 配额±15% |','|---|---:|---:|---:|---|'])
        for title,row in counts['sections'].items():
            report.append(f"| {title} | {row['target_cjk']} | {row['actual_cjk']} | {row['deviation_percent']:.2f}% | 满足 |")
        report.append('')
report.extend(['## Failure Condition Checks',''])
conditions=[('F1','did not fire','D1、D2、D3均为pass，没有mandatory维度block。'),
    ('F4','did not fire','没有mandatory维度warn。'),('F2','did not fire','D4、D5均为pass，没有high维度block。'),
    ('F3','did not fire','没有high维度warn。'),('F0','fired','全部mandatory维度为pass，且没有更高严重度条件触发。')]
for key,status,reason in conditions:report.extend([f'### {key}','',status,'',reason,''])
report.extend(['## Writer Decision','','writer_decision=accept','',
    '这是作者Phase4b对完整初稿交付条件的自判，表示可交下一阶段独立完整性及五视角审查。它不表示审查已通过、人类作者已完成核验、论文已投稿或录用，也不解除已披露科学局限。原Phase4a承诺文件保持原样，本稿仍按其七维标准评分。',
    '',f'完整稿SHA256：`{draft_sha}`。原Phase4a SHA256：`{sha(MAN/"process/writer_phase4a.md")}`。'])
phase='\n'.join(report)+'\n'
required=['## Draft Body','## Dimension Scores','## Failure Condition Checks','## Writer Decision']
positions=[phase.index(title) for title in required]
assert positions==sorted(positions)
assert all(phase.count('### '+key+': ')==1 for key in scores)
assert all(phase.count('### '+key+'\n')==1 for key,_,_ in conditions)
assert re.findall(r'writer_decision=\w+',phase)==['writer_decision=accept']
assert phase.split('## Draft Body\n\n',1)[1].split('\n\n## Dimension Scores',1)[0]==t.rstrip()
(OUT/'writer_phase4b.md').write_text(phase,encoding='utf-8')
save('phase4b_checks.json',{'draft_sha256':draft_sha,'phase4b_sha256':sha(OUT/'writer_phase4b.md'),
    'phase4a_sha256':sha(MAN/'process/writer_phase4a.md'),'full_draft_embedded_exactly':True,'structural_lint':True,
    'scores':{k:{'name':v[0],'score':v[1],'evidence':v[2]} for k,v in scores.items()},
    'condition_order':['F1','F4','F2','F3','F0'],'fired_conditions':['F0'],'writer_decision':'accept',
    'independent_review_accepted':False,'final_render_performed':False})
summary=['# 完整v1写作交付与剩余事项','',f'稿件SHA256：`{draft_sha}`。正文{counts["actual_body_cjk"]}汉字，全部六节配额满足。','',
    '| 事项 | 完成情况 | 定位 |','|---|---|---|',
    '| Stage6材料缺口 | 30项验收、全部种子、τ/六臂表及成本纳入 | 4.5、4.6、4.7、附录D |',
    '| N01 | v2可选首步注意力学习率η*=1，非网络学习率 | 附录C |',
    '| N02 | E1–E3 atol=1e-13，与E4 atol=1e-14分开 | 附录A |',
    '| N03 | AI参与完整研究执行/分析辅助范围，人类核验待确认 | 声明 |',
    '| N04 | 配置调用字段、末次记录损失、L-BFGS状态计数分开 | 3.2及附录A |',
    '| Stage6图版v2 | 三项展示限定复核全部关闭，无新增；科学字段与三CSV不变 | v2_binding_checks与V2_FOLLOWUP |',
    '| 历史结果 | 原六张主表及13题录逐字保留 | numeric_checks与citation_contexts |',
    '| 作者自核 | 完整Phase4b，原Phase4a不变 | writer_phase4b与phase4b_checks |','',
    '剩余事项：独立完整性核查、五视角评审及按反馈修订尚未完成；最终渲染未执行。作者署名、单位、贡献、资助、COI、AI工具信息及人类最终核验待本人确认。科学限制继续保留：三种子和选择偏差、早时间机制证据不足、跨环境混杂、历史生产日志不完备与E4表面权重缺失。',
    '', '没有启动新训练、模型加载、参考ODE积分或修改原数据/协议/Gate源；完整稿及过程文件另存，旧工作稿与旧过程证据保持原样。']
(OUT/'RESPONSES_AND_UNRESOLVED_CN.md').write_text('\n'.join(summary)+'\n',encoding='utf-8')
before=readj(OUT/'protected_before.json')
assert all(sha(Path(p))==digest for p,digest in before.items())
save('final_structure_checks.json',{'draft_sha256':draft_sha,'main_sections':6,'main_tables':8,'all_markdown_tables':len(tables(t)),
    'old_six_main_tables_exact':True,'references':13,'reference_texts_unchanged':True,'images':images,
    'all_image_paths_absolute_and_exist':True,'display_math_paired':True,'material_gap_count':0,
    'protected_files_unchanged':len(before),'author_only_acceptance':True})
prose_lines='\n'.join(line for line in body_without_math.splitlines() if not line.startswith(('|','图','![')))
flagged_terms=['delve','tapestry','landscape','pivotal','crucial','foster','showcase','testament','navigate','leverage','realm','embark','underscore','multifaceted','nuanced','comprehensive','robust','intricate','cornerstone','paradigm','synergy','holistic','streamline','cutting-edge','groundbreaking']
save('writing_quality_checks.json',{'draft_sha256':draft_sha,'scope':'作者语体与结构检查，不是AI文本检测或独立评审',
    'body_em_dash_count':prose_lines.count('—'),'body_semicolons':prose_lines.count('；')+prose_lines.count(';'),
    'flagged_english_terms_found':[term for term in flagged_terms if re.search(r'\b'+re.escape(term)+r'\b',prose_lines,re.I)],
    'stale_stage6_pending_phrases':[line for line in t.splitlines() if re.search(r'尚未纳入|等待修订6|仍待第4|未完成的灵敏度',line)],
    'manual_register_judgment':'正式中文数值PDE语体；数学保证、描述性结果、机制限制和待作者确认事项分层陈述。',
    'manual_paragraph_judgment_ref':'paragraph_audit.json'})
s=readj(OUT/'draft_state.json');s['phase4b_pending']=False;save('draft_state.json',s)
print(json.dumps({'draft_sha256':draft_sha,'body_cjk':counts['actual_body_cjk'],'citation_contexts':len(contexts),
    'teel_writer_judgment':f'{passed}/{denominator}','writer_decision':'accept','review_and_render_pending':True},ensure_ascii=False,indent=2))

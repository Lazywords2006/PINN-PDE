"""Record the partial Phase 4b honestly, with the draft embedded verbatim."""
from pathlib import Path
import hashlib
import json
import re

P=Path(__file__).resolve().parent
draft_path=P.parent/'drafts/initial_working.md'
draft=draft_path.read_text(encoding='utf-8')
counts=json.loads((P/'writer_word_counts.json').read_text(encoding='utf-8'))
cit=json.loads((P/'writer_citation_map.json').read_text(encoding='utf-8'))
data=json.loads((P/'writer_data_evidence.json').read_text(encoding='utf-8'))
contract=json.loads((P/'writer_contract.json').read_text(encoding='utf-8-sig'))
assert counts['draft_sha256']==hashlib.sha256(draft_path.read_bytes()).hexdigest()
assert len(counts['material_gaps'])==2
assert '<!-- TABLE:' not in draft and '<!-- REFERENCES:' not in draft
assert len(cit['references'])==13
assert {r['citation_number'] for r in cit['references']}==set(range(1,14))
assert {x['number'] for x in cit['contexts']}==set(range(1,14))
assert data['read_json_count']==176 and data['all_hashes_match_snapshot']

word_table=['| 正文章节 | 目标汉字 | 实际汉字 | 偏差 | ±15% |',
            '|---|---:|---:|---:|---|']
for title,c in counts['sections'].items():
    word_table.append(f"| {title} | {c['target_cjk']} | {c['actual_cjk']} | {c['deviation_percent']:+.2f}% | {'满足' if c['within_15_percent'] else '未满足'} |")

scores={
 'D1':('block','六个正文章节和中英文工作摘要已写入，但第4.5节的12次衰减参数训练、第4.6节的18次固定SOAP64训练尚缺完整结果及数值复核。两个MATERIAL GAP仍明确保留，结论与摘要也需随完整证据更新。当前只作为工作稿交接，未满足无研究材料占位符的完整稿要求。'),
 'D2':('pass',f"已有外部科学事实按核验材料使用{len(cit['references'])}条顺序编号文献，现有{len(cit['contexts'])}处正文引用在writer_citation_map.json逐段对应BibTeX键、阅读版本与允许支持范围。Favini文献限定为摘要背景，SOAP明确为arXiv v2。原创数学推导、实际配置与结果分别回指E02、协议和数据映射。176份原始JSON重新聚合并核对哈希、误差序列最大值。该通过仅评价当前已写内容的可追溯性，不证明待完成实验。"),
 'D3':('warn','现有正文沿用批准大纲的研究问题和论证顺序：相容性定义与局部推导、原初值主表、新初值、架构叠加、参数范围、残差和限制。保留A-1/G2失败、弱错配、E4及种子退化，并明确五个观测时刻不证明t趋零机制。两项新结果尚未取得，相关主张—证据—解释链暂时只能记录事前设计，不能完成全部结果论证。'),
 'D4':('block',f"按配置口径，当前正文为{counts['actual_body_cjk']}汉字，相对11000目标偏差{counts['deviation_percent']:+.2f}%，未进入9900至12100的允许区间。计数排除摘要、所有表格行、显示公式、图题、参考文献、声明、附录和材料缺口说明，并记录在writer_word_counts.json。篇幅未以重复句或把小数改写成中文数词补齐。"),
 'D5':('block','第1、2、3、5节在各自配额±15%内，第4节和第6节未达配额下界。前者等待两项完整结果、相应图表及解释，后者等待完整证据汇总后形成最终结论。具体数字列于下表，暂不通过加长无关背景弥补缺口。'),
 'D6':('warn','已写论述段采用主题、证据、解释及论证衔接，并把公式命题与证明单独组织，章节间具有逻辑连接。当前未对补齐后的最终正文逐段确认80% TEEL比例，且缺失结果使相应衔接不能终审，因此只记录待完善，不自报已经通过最终段落比例验收。'),
 'D7':('pass','正文保持科学机器学习与数值PDE所需的正式中文语体，中英文摘要均使用限定于已测配置的表述。数学恒等式、有限点数值交叉检查及训练结果分别陈述，避免新颖性、显著性、普遍优势和固定加速等无证据用语。全文统一使用普通科学数值记法与可区分的体误差、迹误差及残差术语。')}

sections=['## Draft Body\n\n'+draft.rstrip(),'## Dimension Scores']
for d in contract['acceptance_dimensions']:
    score,evidence=scores[d['id']]
    sections.append(f"### {d['id']}: {d['name']}\n\n{score}\n\n{evidence}")
    if d['id']=='D5': sections.append('\n'.join(word_table))

checks={
 'F1':('fired','D1为mandatory维度且评分为block。研究结果仍缺失，完整稿要求未满足。'),
 'F4':('fired','D3为mandatory维度且评分为warn。待完成结果对应的论证链尚未展开。'),
 'F2':('fired','D4与D5为high维度且评分为block，总字数及两节分配尚未达到容差要求。'),
 'F3':('did not fire','没有high维度被评为warn。当前两项high维度均为block，已由F2记录。'),
 'F0':('did not fire','D1为block、D3为warn，不满足所有mandatory维度均为pass的条件。')}
sections.append('## Failure Condition Checks')
for condition in contract['failure_conditions']:
    cid=condition['condition_id'];status,evidence=checks[cid]
    sections.append(f'### {cid}\n\n{status}\n\n{evidence}')
sections.append('## Writer Decision\n\nwriter_decision=escalate_to_evaluator\n\n最高严重度触发条件为F1。本标识仅记录契约判定，不把工作稿冻结为完整稿，也不启动正式完整稿评审。按编排要求，先由父代理接收材料缺口，待修订6全部数据及复核交付后在Phase4b补齐、重算字数并更新自评。作者身份、单位、资助和利益冲突仍待作者确认，属于非研究事实信息，不代为推断。')
report='\n\n'.join(sections)+'\n'
(P/'writer_phase4b.md').write_text(report,encoding='utf-8')

assert re.findall(r'^## (.*)$',report,re.M)[0]=='Draft Body'
assert re.findall(r'^### (D[1-7]):',report,re.M)==['D1','D2','D3','D4','D5','D6','D7']
assert re.findall(r'^### (F\d)',report,re.M)==['F1','F4','F2','F3','F0']
assert report.count('writer_decision=')==1
report_body=report.split('## Draft Body\n\n',1)[1].split('\n\n## Dimension Scores',1)[0]
assert report_body==draft.rstrip()
out={'working_draft_not_complete':True,'draft_body_matches_file_verbatim':True,
 'contract_id':contract['contract_id'],'D6_from_contract':'paragraph_structure',
 'phase4b_sections_in_order':True,'dimension_count':7,'failure_checks_order':['F1','F4','F2','F3','F0'],
 'actual_body_cjk':counts['actual_body_cjk'],'total_target':11000,
 'material_gap_count':2,'references':13,'citation_occurrences':len(cit['contexts']),
 'original_json_count':176,'original_json_hashes_match_snapshot':True,
 'remaining_scientific_inputs':['修订6全部12次tau灵敏度结果和复核','修订6全部18次SOAP64结果和复核'],
 'remaining_work':['补齐4.5及4.6结果和论证','更新摘要、讨论和结论','完成稿件图表与引用终审','按最终全文核算字数和TEEL比例','冻结完整v1后交独立evaluator'],
 'draft_sha256':hashlib.sha256(draft_path.read_bytes()).hexdigest(),
 'phase4b_sha256':hashlib.sha256((P/'writer_phase4b.md').read_bytes()).hexdigest(),
 'scores':{k:v[0] for k,v in scores.items()},'decision':'escalate_to_evaluator'}
(P/'writer_checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))

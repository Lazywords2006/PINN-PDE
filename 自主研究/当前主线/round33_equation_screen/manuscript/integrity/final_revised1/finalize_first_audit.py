import json,hashlib,datetime,collections
from pathlib import Path
R=Path('E:/PINN-PDE/自主研究/当前主线/round33_equation_screen');O=R/'manuscript/integrity/final_revised1'
def j(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def out(n,d):(O/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n' if not isinstance(d,str) else d,encoding='utf-8')
now=datetime.datetime.now().astimezone().isoformat();draft=R/'manuscript/drafts/delivery_candidate.md';num=j(O/'NUMERICAL_AUDIT.json');supp=j(O/'SUPPLEMENT_AUDIT.json');reg=j(O/'CLAIM_REGISTRY.json');orig=j(O/'ORIGINALITY_AUDIT.json')
assert sha(draft)=='aef0c10a1bf19e8703a8066e1f0aaef75600b886777424b9f6545677ccc77eb0'
modes=[
dict(mode=1,name='实现错误通过自审',status='INSUFFICIENT_EVIDENCE',gate='BLOCK',evidence=['NUMERICAL_AUDIT.json','SUPPLEMENT_AUDIT.json','SOURCE_VERSION_AUDIT.json'],finding='当前数学、控制流与数值一致性没有发现新硬错误；较早保存模型复算的逐进程实际exit和完整warning/执行时依赖链尚不能完整独立证明。较早生产训练日志亦不完整。',current_passage='附录D621及627、3.4第272行已明确披露；这不是当前正文虚称全历史零警告，而是严格核验门本身证据未足。',minimum_resolution='为当前论文模型输出数字提供真正重新加载权重、原定义参考/误差/残差计算、输入/源码/依赖冻结、实际进程退出、stdout/stderr与警告的完整生产证据。新证据必须标当前复算，不得声称恢复旧训练史。'),
dict(mode=2,name='引用幻觉',status='CLEAR',gate='none',evidence=['REFERENCE_AND_CONTEXT_AUDIT.json','PRIMARY_PDF_FRESH.json','A0_SEMANTIC_SCHOLAR.json','WEB_CONTEXT_FRESH_LATEST.json'],finding='13题录、18引用出现语境全量新核；期刊与作者稿版本正确区分，0幽灵引用、0未引参考文献。'),
dict(mode=3,name='实验结果幻觉',status='CLEAR',gate='none',evidence=['NUMERICAL_AUDIT.json','SUPPLEMENT_AUDIT.json'],finding='206原JSON、488原始产物哈希一致；426数表单元通过独立聚合及舍入检查；全部种子/负面结果保留。此CLEAR限保存数据对应性，Mode1执行证据另列。'),
dict(mode=4,name='捷径依赖或混杂被写成机制',status='INSUFFICIENT_EVIDENCE',gate='warning_for_unclaimed_stronger_mechanism',evidence=['MATHEMATICAL_METHOD_AUDIT.md','CLAIM_REGISTRY.json'],finding='现有数据不能排除优化路径改变、环境混杂等机制解释；未做任意t趋零因果识别。稿件反复明确不提出唯一机制、跨优化器纯因果、未见初值泛化等强主张。有限配置内描述性改善可核，不把这些强主张改成CLEAR。'),
dict(mode=5,name='缺陷包装成新洞见',status='CLEAR',gate='none',evidence=['NUMERICAL_AUDIT.json','CLAIM_REGISTRY.json'],finding='E4、弱错配、个别种子、A1/G2失败及surf缺失按不利/证据限制陈述，未改写为新机制发现；解析精确性和训练收益分开。'),
dict(mode=6,name='方法流程编造',status='CLEAR',gate='none',evidence=['SOURCE_VERSION_AUDIT.json','MATHEMATICAL_METHOD_AUDIT.md','SUPPLEMENT_AUDIT.json'],finding='已读当前及旧哈希对应源码，固定预算/点数/RBA例外/因果32箱/Pirate差异/SOAP计数与配置相符；当前措辞限定源代码语义、保存记录和本机恢复，不假称全历史当前源码执行或人类全面核验。'),
dict(mode=7,name='早期框架固化',status='CLEAR',gate='none',evidence=['SCREEN_PROTOCOL.md','NUMERICAL_AUDIT.json','CLAIM_REGISTRY.json'],finding='保留原筛选E1未入选、E2未确认、A1/G2失败；新增协议不改旧门槛；主τ和主优化路线未倒选，结论主动收窄。')]
prior=R/'manuscript/integrity/complete_v1_pre/INDEPENDENT_PRE_REVIEW.md'
comparison=dict(read_order='Read only after fresh A/B/C/D/E evidence work; did not use old PASS as support for current checks.',file=str(prior),sha256=sha(prior),old_status='PASS_WITH_NOTES for pre-review only; Mode1 and stronger-mechanism Mode4 insufficient',current_status='FAIL strict final gate, Mode1 still insufficient; all current factual content remains source-scoped',resolved_textual_scope=['AppendixE specifies E4 PDE/ODE/flux layer and full12run body/trace data.','AppendixF explicitly defines A1/A2/G2; RBA versions and execution semantics remain disclosed.','Time clamp vs analytic limit, independent residual point order and environment confounding clarified.'],unresolved=['Historical run exits/warnings not reconstructed.','Author identity/self-publication search and human final accountability pending.','Stronger unique-mechanism or universal-generalization claims unsupported and not made.'],review_contract_note='Original five-report panel remains ABORT because only2/5 usable under its contract. Later independent re-review must stand as a separate process, not retroactively convert the old panel.')
out('PRECHECK_COMPARISON.json',comparison)
report=dict(created=now,scope='academic-pipeline Stage4.5 Mode2 first independent final audit before any new numerical production evidence',draft=str(draft),draft_sha256=sha(draft),original_revised1a_binding=j(O/'DELIVERY_BINDING.json'),overall_verdict='FAIL',blocking_issue_ids=['FM1-HISTORICAL-NUMERIC-EXECUTION-EVIDENCE'],stage5_finalization_allowed=False,body_content=dict(substantive_false_or_distorted_claims_found=0,major_distortion=0,unverifiable_asserted_facts=0,important_distinction='Content scoped verification is not a blanket pipeline PASS. Mode1 remaining evidence gap blocks strict finalization independently.'),coverage=dict(A_references='13/13 fresh primary verification',B_citation_occurrences='18/18',C_table_numeric_cells=426,C_table_numeric_failed=0,C_raw_json=206,C_raw_artifact_hashes=488,C_supplement_checks=len(supp['checks']),C_supplement_failed=len(supp['failures']),D_body_paragraphs=123,D_checked=77,D_percent=77/123*100,D_changed=26,D_changed_checked=26,D_actual_queries=154,D2_self_plagiarism='NOT_EXECUTED: author names unavailable',E_registered_units=len(reg['registry']),E_verdict_counts=reg['counts'],E_all_draft_lines_accounted=689),failure_modes=modes,prior_comparison=comparison,originality=dict(grade_counts=orig['grade_counts'],close_match=0,verbatim=0,limitations=orig['limitations']),ethics_transparency=dict(research_type='primary computational research',human_subjects='no collected human-subject data described',authorship='pending author confirmation',funding='pending, not presumed none',conflicts='pending, not presumed none',AI_disclosure='substantive execution/analysis/writing/review assistance disclosed; no false human-final-check assertion',public_release='repository/license/DOI pending',publication_acceptance='not asserted'),follow_up=dict(new_audit_must_be_append_only=True,proposed_target='manuscript/integrity/final_numeric_completion_20261023/',future_evidence_not_used_in_this_verdict=True,repair_scope='read-only recomputation and minimal manuscript provenance wording; no new training/tuning; preserve historical limitations and negative results'),limitations=['No training, saved-model reload, or new reference integration performed within this first audit. Arithmetic, source reading, hash checks, external searches and source-data/PNG verification only.','Four local PNG figures visually inspected; no full rendered HTML/PDF acceptance claimed by this integrity review.','Originality uses public-web heuristic screening, not professional full-corpus plagiarism certification.','The final gate is not a publication/peer-review acceptance decision.'])
out('FINAL_INTEGRITY_REVIEW.json',report)
md=f'''# 修订稿首轮最终完整性独立核验

结论：**严格 Stage 4.5 门为 FAIL，暂不准进入依赖该门的最终定稿。** 当前正文未发现实质性数字错误、重大引用失真或未披露的负面结果删除；阻断项是 Mode1 的数值执行证据不足。当前内容能够被保存产物支持，与全历史执行链已经完整，是两个不同判断。

对象：[delivery_candidate.md](../../drafts/delivery_candidate.md)，689行，SHA256 `{sha(draft)}`。与原 `complete_revised1a.md` 仅第5行状态说明不同，其他字节一致，独立比对见 `DELIVERY_BINDING.json`。本报告保留失败时点；之后新复算和候选稿修改必须在新目录加审，不能覆盖此报告为PASS。

## 已完成的独立范围

| 阶段 | 本次实际覆盖 | 结果 |
|---|---|---|
| A 文献存在性/题录 | 13/13，每项本次访问原始入口 | 标题、全部列出作者、年或版本、刊物卷页/文号及DOI核对；0幽灵引用 |
| B 引用上下文 | 18/18出现位置 | 全部逐段比对；未把版本或边界条件混为一谈 |
| C 数值与图表 | 426个数表单元；206JSON；488原始产物哈希；另6721项补充检查 | 全部通过原定义、舍入/原容差和哈希检查；四张PNG已看图并核源数据 |
| D 原创性筛查 | 77/123段，62.60%；修改段26/26；154次实际查询，39批 | 58段未找到近似表达、7段有引文的改述、12段公共知识/数学表达；0未署名密切匹配、0逐字匹配 |
| E 全量声明 | 680登记单元，689/689行归类 | 653条在声明范围内核实；19条公式引介/结构语；8条明确待作者确认；没有以短句长度漏掉事实声明 |

E的单元包括每个句子、显示公式块、表格行和图像；参考文献另由A登记，数表另有426单元级检验。`CLAIM_REGISTRY.json/.md`保留原文、行号、类别、来源与边界。这里的“核实”是对当前有限句义的核实，不是将Mode1证据不足隐去。

## 阻断项及最小解决范围

`ai_research_failure_modes.md` Mode1要求核查每项数值是否有产生该数值的保存日志、notebook或script run，并核实际退出码和警告；没有日志须标记。最终核验不能凭正文缩限或用户授权把不存在的执行证据写成存在。

本次已独立验证旧130项复算记录、24项小预算记录、第一阶段22项和第二阶段30项的原始数字对应性；原设置与加密误差均在既定容差。第二阶段30个实际attempt的exit=0，日志无warning/traceback/非有限数值标记，源和产物绑定可核。但较早保存模型复算及生产训练的逐进程真实退出、完整警告与部分执行时依赖链，仍不能由现存资料完整建立。两个历史测试日志分别63/71通过且各1条张量转标量测试断言警告，不能写成全历史零警告。

稿件第272、621、627行已经诚实披露该范围，故没有一条“全历史零警告”的虚假正文需要删除。最小补证是为**当前论文实际使用的模型输出数字**提供真正重新生产这些数字的保存计算：逐权重加载、原定义参考/求积/残差、完整五时刻序列、原容差、输入/代码/依赖哈希及真实stdout/stderr、warning和OS退出码。新日志必须标“本次数值复算”，不能声称追回旧训练过程。旧训练损失、迭代、调用和成本可以按保存记录字段陈述，其历史执行边界仍保留。旧E4的20个surf缺失继续排除v和相关不可重建残差，不能补随机权重。后续真实结果未纳入本报告。

## 数学、实现与数值要点

独立重新检查了变换尺度、Laplace表达式、核表示、0≤Q≤1及0≤w≤t、初始连续延拓、边界恒等式、小时间展开、两个时间导数迭代极限、衰减余项，以及E4常通量层的−1.02符号。命题只对应未截断解析表达式，代码 `t.clamp_min(1e−30)` 的分支差异已明确；没有把硬初值写成完整PDE相容性已经被学习。见 `MATHEMATICAL_METHOD_AUDIT.md`。

全部表格从原JSON按每seed先五时刻max、再取seed median独立重聚合。原硬初值/修正比34.83和5.92，新初值2.69和7.34，Pirate变体22.61和5.52，同批SOAP64为300.07和30.83。τ最大/最小中位数比1.715812和1.43027。新E3seed0退化3.569807%、弱κ点退化38.346149%、新E1seed0右残差增加2.731157%、E4 vanilla/修正比0.838398555111均保留。A1约12.51/1.47、G2联合不通过、E1筛选未过原三倍线没有被追改。

CSV的30、36、18行及共享6行独立核对，合计48独立分析记录。第5阶段L-BFGS内部迭代1951–3000、closure3196–3751及18任务38.2/90.4/103.5分钟范围/中位数相符；第6阶段1880–3000、3211–3771和四层成本22891.57、9286.10、372236.02、371817.95秒各按其原定义计算。训练轨迹时间之和没有冒充并行批次历时。

旧源码哈希准确定位到git `c1f60bd`。到 `ea12d0e` 的差异仅新增SOAP64分支、身份/元数据/计数和两个新初值定义；旧层、RBA、因果和架构控制流未变。当前方法参数因此有源代码支持，但该发现不是历史进程来源链的替代品。RBA初权重1、网络先更新、四分量各自加权且复用固定点；因果32箱；Pirate省略最小二乘初始化；SOAP首次仅初始化及字段回填语义均准确披露。

四张图核对了对数坐标、真实seed、median/最小最大范围、3.57%不利seed标注及历史/本机环境标签。解析图的2728个Q值按公式重新算得一致，未作为训练性能证据。此次未声称完成全稿HTML/PDF视觉验收。

## 文献与原创性

本次Semantic Scholar第一次请求429；重试200，空条目或聚合版本不当未被当作不存在/已确认。最终13项均以本次出版社、作者稿、JMLR、NIST或Crossref原始记录核对。缺失的skill附属S2协议文件已记录，没有虚构读过该文件。

Favini仅支持出版社摘要可见的经典背景；Li一维周期与二维动态边界分开；Chen是Dirichlet角点时间积分；SL-PINN只陈述所读空间层和v2特定相容时变例。RBA期刊2024、2023v1及2026-08-22v2分别核对，v1式9/v2式12及Algorithm1支持本地差异；未谎称逐字读过出版PDF。SOAP使用八作者arXiv v2，不混合会议终稿。

公开搜索仅为启发式筛查，不能证明全文绝无抄袭，不是Turnitin/iThenticate。多查询工具返回的结果池按批保存，没有伪称每个query各自独立排名；每段核查前最多10条返回块并保留比较。中文跨语种、未索引和付费全文存在漏检。作者姓名未提供，D2自我重复发表检索**未执行**；未伪填“无自我抄袭”。AI文字风格只作信息性观察，不推断作者身份。

## 七类失败模式

| 模式 | 状态 | 实际边界 |
|---|---|---|
| 1 实现错误通过自审 | **INSUFFICIENT EVIDENCE，阻断** | 当前保存数字与实现可核；早期数值执行链仍未完整建立 |
| 2 引用幻觉 | CLEAR | 本次13文献、18语境全核 |
| 3 实验结果幻觉 | CLEAR（保存记录对应范围） | 206JSON、488哈希、426单元和全部seed对应；不替代Mode1 |
| 4 捷径/混杂当机制 | INSUFFICIENT EVIDENCE（更强机制） | 独一机制、纯优化器/τ因果和未知初值泛化仍未证实，当前稿未作这些强主张 |
| 5 缺陷包装成洞见 | CLEAR | 负面、surf缺失、变体差异保留，未包装成功 |
| 6 方法流程编造 | CLEAR（当前陈述范围） | 代码、配置与保存字段支持，旧执行历史及人类最终核验没有冒称完成 |
| 7 早期框架固化 | CLEAR | 失败门槛不追改，主参数不倒选，范围按证据收窄 |

## 与旧预审及作者声明的关系

上述独立核验完成后才读取 `complete_v1_pre/INDEPENDENT_PRE_REVIEW.md` 比较。其PASS WITH NOTES仅允许有限初稿进入评审，明确没有解除最终门；本轮没有把旧PASS复用为新PASS。Mode1缺口和更强机制Mode4边界保持。原五报告组依其contract仍为ABORT（2/5可用），后续另行独立复审不能追认旧panel。

作者姓名、贡献、单位、基金、利益冲突、公开仓库/许可/永久标识及人类最终核验仍明确待确认。研究为原始数学计算研究，不是系统综述；AI参与实质执行/分析/写作/内部审查已经披露。内部AI审查不是外部同行评审或录用。

后续补证及最小文字更新须另存并独立核查。只在真实新证据满足规则后判断当前数字范围的最终门；不改变本首轮FAIL，不补造历史训练链或表面模型。

机器入口：`FINAL_INTEGRITY_REVIEW.json`；完整依据为 `REFERENCE_AND_CONTEXT_AUDIT.json`、`NUMERICAL_AUDIT.json`、`SUPPLEMENT_AUDIT.json`、`ORIGINALITY_AUDIT.json`、`CLAIM_REGISTRY.json/.md`、`MATHEMATICAL_METHOD_AUDIT.md`、`SOURCE_VERSION_AUDIT.json`、`PRECHECK_COMPARISON.json`。原始网络查询、接口失败、输入和输出哈希均保留。
'''
out('FINAL_INTEGRITY_REVIEW_CN.md',md)
inputs=j(O/'FILE_BINDINGS.json')['files']
for p in [R/'validation/feasibility_review_20261021/existing_data_review.json',R/'validation/resolution_20261022/preflight_review.json',R/'validation/stage5_20261022/ic_validation.json',R/'validation/stage5_20261022/pirate_validation.json',R/'validation/stage6_20261022/completion_archive_20261023/results_validation.json',R/'validation/stage6_20261022/completion_archive_20261023/final_runtime_status.json',R/'validation/stage6_analysis_20261022/complete_v2/analysis_evidence.json',prior]:inputs.append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size))
out('INPUT_MANIFEST.json',dict(created=now,draft_sha256=sha(draft),inputs=inputs,raw_artifacts=num['hashes'],note='External sources bound by retained actual-query/HTTP records and downloaded primary-PDF SHA256; no memory-derived source used.'))
manifest={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(O.iterdir()) if p.is_file() and p.name!='REVIEW_MANIFEST.json'}
out('REVIEW_MANIFEST.json',dict(created=now,immutable_round='first final audit, before new numerical evidence; preserve FAIL',files=manifest))
print(json.dumps(dict(verdict=report['overall_verdict'],report_sha256=sha(O/'FINAL_INTEGRITY_REVIEW_CN.md'),manifest_sha256=sha(O/'REVIEW_MANIFEST.json'),files=len(manifest)),ensure_ascii=False))

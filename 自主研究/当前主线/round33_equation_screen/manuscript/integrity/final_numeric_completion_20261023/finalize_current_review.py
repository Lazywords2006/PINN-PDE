from pathlib import Path
import json,hashlib,datetime
R=Path('E:/PINN-PDE/自主研究/当前主线/round33_equation_screen')
O=R/'manuscript/integrity/final_numeric_completion_20261023'
F=R/'manuscript/integrity/final_revised1'
D=R/'manuscript/drafts/delivery_candidate2a.md'
N=R/'validation/final_numeric_provenance_20261023'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,d):(O/n).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
now=datetime.datetime.now().astimezone().isoformat()
actual=read(O/'ACTUAL_RUN_INDEPENDENT_AUDIT.json');process=read(O/'PROCESS_AND_LINK_CHECK.json');nm=read(O/'FINAL_NUMERIC_MANIFEST_CHECK.json');first=read(O/'FIRST_AUDIT_PRESERVATION.json');cr=read(O/'FINAL_CLAIM_REGISTRY.json');orig=read(O/'ORIGINALITY_SUPPLEMENT.json');bind=read(O/'FINAL_CANDIDATE_BINDING.json')
assert actual['failure_count']==0 and not process['failures'] and nm['passed'] and first['all_unchanged']
assert sha(D)==cr['draft_sha256']==orig['draft_sha256']==bind['final_sha256']=='741b88925f6248050c9de3f5fa590f2abf8a8496f4194dd6c35990038a3343ce'
assert read(O/'CANDIDATE2_TO_2A_BINDING.json')['only_requested_edits'] and read(O/'RELOAD_STATUS_COUNTS.json')['exact']
assert cr['counts']=={'PENDING_AUTHOR_DECLARATION':8,'VERIFIED':666,'NON_ASSERTIVE_CONNECTOR':19}
modes=[
 {'mode':1,'name':'Implementation bug passing self-review','status':'CLEAR_FOR_CURRENT_CLAIMS','evidence':['ACTUAL_RUN_INDEPENDENT_AUDIT.json','FINAL_NUMERIC_MANIFEST_CHECK.json','../final_numeric_source_review_20261023/SOURCE_REVIEW_CN.md','../final_numeric_source_review_20261023/HELDOUT_SOURCE_REVIEW_CN.md'],'finding':'The actual saved-weight numerical production chain now covers all206 body/trace results and all52 existing heldout residual records at original definitions/tolerances,270 child+2 supervisor actual exits0,zero warnings,empty stderr. New checker source and all arrays independently checked.','outside_scope':'Historical training exits, warnings, missing dependency provenance and full trajectories were not recovered; record-field statements are not promoted to independent history reconstruction. Twenty legacy E4 surface branches remain absent.'},
 {'mode':2,'name':'Hallucinated citation','status':'CLEAR_FOR_CURRENT_CLAIMS','evidence':['../final_revised1/REFERENCE_AND_CONTEXT_AUDIT.json','PROCESS_AND_LINK_CHECK.json'],'finding':'13 freshly verified references and18 contexts retained unchanged; versions and accessible source boundaries remain explicit. No new external references in the numerical supplement.'},
 {'mode':3,'name':'Hallucinated experimental result','status':'CLEAR_FOR_CURRENT_CLAIMS','evidence':['../final_revised1/NUMERICAL_AUDIT.json','ACTUAL_RUN_INDEPENDENT_AUDIT.json','CHANGED_CLAIMS_AUDIT.json'],'finding':'426 original numeric table cells,206 JSONs and488 original artifacts checked;4120 current body/trace values and416 heldout aggregate values reproduce within unchanged tolerance; no seeds/results removed or invented.'},
 {'mode':4,'name':'Shortcut or confounding mistaken for mechanism','status':'CLEAR_FOR_CURRENT_DESCRIPTIVE_SCOPE','evidence':['../final_revised1/MATHEMATICAL_METHOD_AUDIT.md','FINAL_CLAIM_REGISTRY.json'],'finding':'Current paper states fixed-configuration numerical comparisons and auxiliary half-line mathematics, while disclosing variants, failure cases and unmatched compute/optimization limits. It does not assert that a unique mechanism, full-PDE compatibility, optimizer superiority or unseen-IC generalization has been established.','stronger_mechanism_status':'INSUFFICIENT_EVIDENCE; not claimed or newly authorized by this PASS'},
 {'mode':5,'name':'Implementation defect reframed as discovery','status':'CLEAR_FOR_CURRENT_CLAIMS','evidence':['../final_revised1/NUMERICAL_AUDIT.json','ACTUAL_RUN_INDEPENDENT_AUDIT.json','FINAL_CANDIDATE_BINDING.json'],'finding':'Adverse seeds,weak-kappa failure,E4 vanilla ratio,original screening failures and missing surf weights remain explicit. Fresh reproduction does not turn them into successful mechanisms.'},
 {'mode':6,'name':'Methodology fabrication','status':'CLEAR_FOR_CURRENT_CLAIMS','evidence':['../final_revised1/SOURCE_VERSION_AUDIT.json','CHANGED_CLAIMS_AUDIT.json','ACTUAL_RUN_INDEPENDENT_AUDIT.json'],'finding':'Configurations,source semantics,residual sampling and saved fields match. Newly executed reloading is distinguished from prior aggregation and from unrecovered training history. Frozen project forward/reference implementations are reused,not represented as a second independent PDE solver.'},
 {'mode':7,'name':'Premature framing lock-in','status':'CLEAR_FOR_CURRENT_CLAIMS','evidence':['../final_revised1/NUMERICAL_AUDIT.json','RESOLVED_SCOPE_WORDING.json','FINAL_CANDIDATE_BINDING.json'],'finding':'Original scientific thresholds,failed historical criteria,negative cases and main parameter are preserved. One newly detected taxonomy wording issue was corrected in a separately saved candidate2a;candidate2 and first FAIL remain intact.'}
]
limitations=[
 'PASS applies to the frozen current complete initial draft and its actually claimed mathematics,methods,recorded-field facts and current saved-weight numerical output chain; it is not full historical training provenance certification.',
 'Historical missing training exits,warnings,dependency chains and full trajectories remain unverified. Historical tests63/71 each retain their one tensor-to-scalar assertion warning; only new numerical runs have zero warnings.',
 'The20 legacy E4 surface networks are missing. v(t),surface/exchange residuals and their reproducibility remain excluded;no random weights were substituted.',
 'Stronger unique-causal-mechanism claims,unseen-initial-condition generalization,cross-hardware speed ratios and full-PDE early-time regularity are not established by these fixed-configuration experiments.',
 'Author identity,affiliations,contributions,funding,COI,public repository/license/identifier and human final verification remain explicitly pending declarations. D2 self-overlap search was not run because no author name was provided.',
 'Originality checking is a heuristic public-web screen,not proof of absence or a Turnitin/iThenticate report;Chinese,cross-language,unindexed and paywall blind spots remain.',
 'This is an internal independent AI integrity review,not external peer review,acceptance or publication approval. Whole-manuscript PDF/HTML rendering acceptance belongs to subsequent layout verification.'
]
report=dict(created=now,review_type='supplementary final-check after actual numerical provenance completion',draft=str(D),draft_sha256=sha(D),overall_verdict='PASS',stage5_finalization_allowed=True,scope='Frozen complete initial draft only; current saved-weight numerical chain and explicitly scoped statements,with historical and stronger-mechanism limitations retained.',unresolved_blocking_issues=[],resolved_issues=[{'id':'FIRST_FINAL_MODE1','resolution':'Actual new numerical production records,not historical fabrication','prior_report':'../final_revised1/FINAL_INTEGRITY_REVIEW_CN.md','prior_verdict_preserved':'FAIL'},{'id':'SUPPLEMENT_SCOPE_12','resolution':'12 kinds of equations corrected to12 equation/parameter/initial-condition configurations','evidence':'RESOLVED_SCOPE_WORDING.json'}],coverage={'references':13,'citation_occurrences':18,'original_numeric_table_cells':426,'all_raw_json':206,'raw_artifacts':488,'current_body_trace_scalar_comparisons':4120,'current_heldout_scalar_comparisons':416,'actual_child_processes':270,'actual_supervisor_processes':2,'independent_actual_run_checks':8368,'independent_process_link_checks':289,'numerical_archive_files_hashed':2300,'imported_dependency_files_hashed':2256,'final_draft_lines':696,'claim_registry_units':693,'verified_claims':666,'nonassertive_units':19,'explicit_pending_author_declarations':8,'originality_paragraphs_checked':81,'originality_paragraphs_total':126,'originality_percent':81/126*100,'all_changed_since_complete_v1_checked':31,'increment_changed_units_checked':11,'actual_originality_queries_session':180},failure_modes=modes,limitations=limitations,first_failure_preservation={'all35_files_unchanged':True,'review_manifest_sha256':sha(F/'REVIEW_MANIFEST.json'),'first_report_sha256':sha(F/'FINAL_INTEGRITY_REVIEW_CN.md')},current_bindings={'numerical_manifest_sha256':sha(N/'FINAL_DELIVERY_SHA256.json'),'candidate2a_process_index_sha256':sha(R/'manuscript/process/delivery_candidate2a/DELIVERY_BINDING_INDEX.json')},auditor_environment_diagnostic={'preserved_file':'FULL206_PRELIM_NUMPY_MISMATCH.json','finding':'Initial independent audit used NumPy2.2.6;itsGL400 weights differed from production NumPy2.5.3 by1.7897264074397123e-15. Re-running only the read-only audit under the recorded production interpreter made allchecks pass. No scientific tolerance,source,weights,training or numerical production output changed.'})
write('FINAL_INTEGRITY_REVIEW.json',report)
md=f'''# 补充最终完整性独立核验

结论：**PASS。允许冻结候选稿进入最终排版和完整初稿交付。** 适用对象是当前稿件所陈述的有限数学、方法、保存记录字段及保存权重的数值输出链；本结论不追认全历史训练过程，也不赋予稿件未提出的更强机制结论。

对象：[delivery_candidate2a.md](../../drafts/delivery_candidate2a.md)，696行，SHA256 `{sha(D)}`。首轮 `final_revised1` 的严格 **FAIL** 和35个冻结文件全部保留、逐个哈希相同。新证据只在本补充目录裁定，未把旧失败改成通过。

## 阻断项如何解除

首轮阻断的是“当前论文模型输出数字缺少完整可检查的实际生产记录”。本次先独立阅读两套新检查器，再核查真实运行归档，最后从保存数组独立计算误差与残差聚合。并未用工程报告中的PASS布尔值代替检查。

全部206个保存模型在N64/GL200与N96/GL400、五个原定时刻产生4120个体/迹误差值；全部已有52条heldout记录产生416个RMS/max_abs值。原容差保持 `rtol=1e-5, atol=1e-9`。12个方程、参数或初值配置新求N48、N64、N96参考解，N48/N96在401点、五时刻的最大绝对差为3.2916874781463434e-10，小于原1e-8。

| 项目 | 独立核验结果 |
|---|---|
| 真实执行 | 206体/迹＋12参考＋52残差，共270子进程；另2个主管进程，实际OS退出码均0 |
| 警告/错误流 | 全部新子进程warnings为0，stderr空；两主管stderr空 |
| 原件和来源 | 488原始JSON/PT不变；已审源码不变；2256个导入依赖文件哈希核对 |
| 归档 | 2300个文件逐字节重哈希，清单无增删/差异 |
| N64/GL200最大绝对差 | 体1.7316981182347035e-12；迹2.8278490660227362e-12 |
| N96/GL400最大绝对差 | 体1.845973374159371e-11；迹4.7492676458205096e-11 |
| 52条heldout | RNG330500实际点集逐数组相同；四分量RMS与max_abs的416个差均0 |
| 只读约束 | 无训练；逐张量状态与输入身份保持；20个旧E4缺失surf明确移除 |
| 独立检查 | `ACTUAL_RUN_INDEPENDENT_AUDIT.json` 的8368项全部通过 |

重载状态实际为110个旧完整模型、20个旧E4体分支、76个完整产物。52个残差模型不含旧E4。新检查器调用冻结项目模型前向与参考解；独立编写和审查的是重载、求积、残差自动微分聚合、对照及证据链。因此，这不是第二套独立PDE求解器的交叉证明。

这些真实新记录足以支持当前保存权重的误差/残差结论。它们不能追回旧训练的退出码、警告、依赖和完整轨迹；稿件第622、628、634及682行仍明确保留范围。旧损失、调用、迭代和训练成本只按已保存字段解释，没有被改写成逐步观测或独立历史重建。两个旧测试日志的63/71通过及各1条测试断言警告也原样保留。因而本次解除的是当前数值生产链的Mode1阻断，不是豁免或制造历史证据。

## 稿件全量核验及改动

首轮13/13题录和18/18引用语境均已在本次独立任务中访问原始来源核查，当前逐字不变，按准确哈希和行映射复用。首轮426个数表单元、数学推导、全部206JSON/488原件、四图数据及原始负例的独立检查继续有效；当前四张PNG与首轮核看的版本哈希一致。没有用普通复审或作者自核替代这些检查。

新增及修改的11个文字/映射单元全部逐句核查。唯一发现是候选稿2第630行“12种方程”会混淆12个配置与不同方程类型，已在另存的2a中改为“12个方程、参数或初值配置”。2a相对2仅该词句和第503行附件路径变化；2原稿未覆盖。所有原科学数字、公式和图表保持。

最终登记覆盖**696/696行、693个单元**：666条在当前句义范围内核实，19条非断言衔接，8条明确待作者填写的声明。没有将待填声明当作已核实事实，也没有因短句、公式或表格而漏掉硬声明。完整原文、行号、来源和边界在 `FINAL_CLAIM_REGISTRY.json/.md`；11处增量在 `CHANGED_CLAIMS_AUDIT.json`。

作者附件21项绑定、引用上下文、全部本地链接和旧25项修订的84处定位均独立核对（83个文本锚点＋1个文件哈希定位）；六章汉字数独立算得1695、2190、2210、2755、1897、763，共11510。`PROCESS_AND_LINK_CHECK.json` 的289项全部通过。旧25项普通复审状态仅属于其原复审，未被冒称为本次最终门结论。

## 原创性与透明度

按同一段落口径，最终筛查覆盖**81/126段＝64.29%**，相对complete_v1的31个修改段全部覆盖。此次11个新增/修改单元（含表格映射及内部链接变更）执行22次实际查询，并对4处低相关返回追加限定查询，共26次；连同首轮154次，保存180次实际查询。没有找到未署名密切或逐字匹配。检索返回共享的专业词、数字或有引文的版本说明不当作抄袭证据；每批真实结果池和比较记录均保留。

公开网络检索是启发式筛查，不是绝无抄袭证明或专业查重证书。中文、跨语言、未索引及付费全文仍有盲区。作者姓名尚未提供，D2自我重复发表检索未执行；没有伪填“无自我抄袭”。8条作者、单位、贡献、基金、利益冲突、公开仓库/许可/标识及人类最终核验待确认声明仍为待填。对完整初稿而言，它们是已显示的待作者事项，而非被隐去的已完成事实。

## 七类失败模式

| 模式 | 当前稿件范围内裁定 | 保留的边界 |
|---|---|---|
| 1 实现错误通过自审 | CLEAR | 新数值链有源码、数组、真实退出/警告；旧训练全链仍未恢复 |
| 2 引用幻觉 | CLEAR | 13文献/18语境独立核查，版本和访问边界保持 |
| 3 结果幻觉 | CLEAR | 原表和原始记录对应；4120＋416值真实复算，无删除种子或虚构输出 |
| 4 捷径/混杂当机制 | CLEAR，仅限当前描述性范围 | 更强的独一机制、优化器因果及未知初值泛化仍为INSUFFICIENT EVIDENCE，当前稿未作此强断言 |
| 5 缺陷包装成洞见 | CLEAR | 不利种子、弱κ退化、E4 vanilla比值及历史失败判据均保留 |
| 6 方法流程编造 | CLEAR | 配置、原抽样、代码和保存字段相符；新复算与旧聚合/训练历史严格分开 |
| 7 早期框架固化 | CLEAR | 原门槛、主参数、失败和负面结果未被追改，范围随证据精确化 |

此处CLEAR只判断稿件实际提出的主张。对尚无充分实验支持的更强机制，没有因审查完成而转为已证实；对缺失的旧E4 v(t)、表面/交换残差，也没有给予定量认证。

## 核验过程说明与交付边界

一次审计器环境差异完整保留在 `FULL206_PRELIM_NUMPY_MISMATCH.json`：审计初跑使用NumPy2.2.6，其GL400求积权重与生产NumPy2.5.3最大差1.7897264074397123e-15，触发审计的严格节点复核。随后仅用已记录的生产解释器重跑只读审计，原检查阈值未改即全部通过；模型、训练、实际复算输出和科学容差没有改变。这个审计环境问题没有被删除或改称模型失败。

首轮FAIL是它当时证据范围下的真实判断；本补充PASS来自新增真实执行记录、已修正文字和全量映射。原五报告组依其原contract仍为ABORT，后续普通复审和本报告均不追认旧panel。本报告属于内部独立AI核验，不是外部同行评审、接收或投稿合规认可。最终排版还需核对导出/渲染；本报告不宣称已看过尚未形成的全稿PDF/HTML。

机器入口为 `FINAL_INTEGRITY_REVIEW.json`；输出冻结清单为 `REVIEW_MANIFEST.json`。首轮数学、原数字和13条文献的完整证据保留在 `../final_revised1/`，新执行原件见E18。若冻结稿、源码、原结果或上述绑定改变，需按实际改动补核。
'''
(O/'FINAL_INTEGRITY_REVIEW_CN.md').write_text(md,encoding='utf-8')
external=[D,F/'REVIEW_MANIFEST.json',F/'FINAL_INTEGRITY_REVIEW_CN.md',N/'FINAL_DELIVERY_SHA256.json',N/'evidence/full/summary.json',N/'evidence/heldout/summary.json',R/'manuscript/process/delivery_candidate2a/DELIVERY_BINDING_INDEX.json',R/'manuscript/integrity/final_numeric_source_review_20261023/SOURCE_REVIEW_CN.md',R/'manuscript/integrity/final_numeric_source_review_20261023/HELDOUT_SOURCE_REVIEW_CN.md']
manifest=dict(created=now,scope='Frozen supplementary final integrity PASS for candidate2a; first strict FAIL preserved',draft_sha256=sha(D),files={str(p.relative_to(O)).replace('\\','/'):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(O.rglob('*')) if p.is_file() and p.name!='REVIEW_MANIFEST.json'},external_bindings={str(p):sha(p) for p in external})
manifest['file_count']=len(manifest['files']);write('REVIEW_MANIFEST.json',manifest)
print(json.dumps(dict(verdict='PASS',draft_sha256=sha(D),report_sha256=sha(O/'FINAL_INTEGRITY_REVIEW_CN.md'),json_sha256=sha(O/'FINAL_INTEGRITY_REVIEW.json'),manifest_sha256=sha(O/'REVIEW_MANIFEST.json'),files=manifest['file_count']),ensure_ascii=False))

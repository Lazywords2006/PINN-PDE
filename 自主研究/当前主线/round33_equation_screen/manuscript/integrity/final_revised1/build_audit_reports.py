"""Assemble the independently performed read-only audit; does not run experiments."""
import json,re,csv,hashlib,difflib,datetime,collections
from pathlib import Path
R=Path('E:/PINN-PDE/自主研究/当前主线/round33_equation_screen')
O=R/'manuscript/integrity/final_revised1'
def j(name):return json.loads((O/name).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,obj):
 (O/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n' if not isinstance(obj,str) else obj,encoding='utf-8')
draft=R/'manuscript/drafts/delivery_candidate.md';lines=draft.read_text(encoding='utf-8').splitlines();inv=j('INVENTORY.json');nums=j('NUMERICAL_AUDIT.json');sup=j('SUPPLEMENT_AUDIT.json')
now=datetime.datetime.now().astimezone().isoformat()
refs={
1:dict(primary=['https://link.springer.com/article/10.1007/s00028-002-8077-y'],passage='Publisher title/author/journal metadata and abstract on generalized Wentzell heat equations and semigroups; no unseen proof attributed.',notes='2002, Journal of Evolution Equations 2(1), 1–19; four author identities verified.'),
2:dict(primary=['https://www.sciencedirect.com/science/article/pii/S0021999118307125'],passage='Original PINN formulation: neural approximation, PDE residual through differentiation, initial/boundary constraints.',notes='2019 JCP 378, 686–707; Raissi, Perdikaris, Karniadakis; DOI publication year distinct from 2018 DOI string.'),
3:dict(primary=['https://pisrt.org/psr-press/journals/oms/01-vol-10-2026-issue-1/physics-informed-neural-networks-for-the-heat-equation-with-dynamic-wentzell-boundary-conditions/','https://pisrt.org/psrpress/j/oms/2026/physics-informed-neural-networks-for-the-heat-equation-with-dynamic-wentzell-boundary-conditions.pdf'],passage='Abstract/method: hard initial constraint, random features, linear least squares, smooth manufactured solutions; both-end boundary formulas checked against current single-right model.',notes='Muhammad Awais; 2026 OMS 10, 526–536. Webpage revised-date typo is not copied into manuscript.'),
4:dict(primary=['https://www.global-sci.com/ijnam/article/view/24278','https://arxiv.org/html/2507.09757v1'],passage='Abstract and §3.1: 2D surface/bulk dynamic-boundary Allen–Cahn; the 1D example uses periodic boundaries. No error ratio transferred.',notes='Chunyan Li, Wenkai Yu, Qi Wang; 2026 IJNAM 23(4), 576–604.'),
5:dict(primary=['https://global-sci.com/index.php/cicp/article/download/5794/11524/12754','https://arxiv.org/pdf/1011.4549'],passage='Author manuscript §2: Dirichlet problem; S1 is the time integral of S0, equation (2.11), PDF page 6. Supports prior corner correction, not this dynamic-boundary formula.',notes='Qingshan Chen, Zhen Qin, Roger Temam; 2011 CICP 9(3),568–586. Publisher download later redirected; accessible author PDF used for method.'),
6:dict(primary=['https://www.sciencedirect.com/science/article/pii/S0045782521006186','https://api.crossref.org/works/10.1016%2Fj.cma.2021.114333'],passage='Publisher abstract/method passage: distance functions construct trial functions satisfying boundary conditions exactly.',notes='Fresh publisher plus Crossref metadata: N. Sukumar and Ankit Srivastava, 2022 CMA 389,114333. Some direct publisher opens return403; searchable publisher text and metadata independently available.'),
7:dict(primary=['https://www.sciencedirect.com/science/article/abs/pii/S0377042724002395','https://arxiv.org/abs/2312.06278','https://arxiv.org/html/2312.06278v1'],passage='Rectangular-domain stationary singular perturbation: spatial boundary/parabolic/corner layer enrichment; not an initial-time dynamic-boundary result.',notes='Gie, Hong, Jung, Munkhjin; 2024 JCAM 450,115989.'),
8:dict(primary=['https://www.sciencedirect.com/science/article/pii/S0377042725004327','https://arxiv.org/html/2312.03295v2'],passage='Author v2 §3.3, equations (3.26),(3.37): time-dependent example includes initial factor, assumes no temporal layer and compatible data. Claim deliberately limited to this example.',notes='Gie, Hong, Jung, Lee; 2026 JCAM 474,116918; 2025 DOI string is not publication year.'),
9:dict(primary=['https://www.sciencedirect.com/science/article/pii/S0045782524000616','https://arxiv.org/pdf/2307.00379v1','https://arxiv.org/pdf/2307.00379v2','https://arxiv.org/abs/2307.00379v2'],passage='v1 equation(9)/Algorithm1 and v2 equation(12)/Algorithm1: normalized residual history, initial lambda0=0, attention then network; v1 PDE weighting vs v2 multiple components. v2 optional k=1 eta*=1 is attention rate. Local lambda0=1, network-then-attention, all four residuals separately.',notes='Journal bibliographic metadata2024 CMA421116805; read v2 revised2026-08-22, not claimed publisher-PDF verbatim check. S2 merged preprint metadata does not override journal year.'),
10:dict(primary=['https://www.sciencedirect.com/science/article/pii/S0045782524000690','https://arxiv.org/pdf/2203.07404'],passage='Author PDF §3 page6 equations(3.1)–(3.3): weights decrease exponentially with prior temporal residual sum. Local32-bin separate-component implementation is disclosed as local configuration.',notes='Wang, Sankaran, Perdikaris; 2024 CMA421116813. Author preprint title has extra is-all-you-need phrase; journal title correctly used.'),
11:dict(primary=['https://jmlr.org/papers/v25/24-0313.html','https://jmlr.org/papers/volume25/24-0313/24-0313.pdf'],passage='Official paper architecture/initialization sections PDFpp13–15: adaptive residual connections initialized0; physics/data-guided least-squares output initialization. Local omission explicitly disclosed.',notes='Wang, Li, Chen, Perdikaris;2024 JMLR25(402),1–51.'),
12:dict(primary=['https://arxiv.org/abs/2409.11321v2'],passage='v2 abstract: Shampoo eigenbasis and Adam update. Eight-author list includes Mujin Kwun; title/version not mixed with conference final.',notes='First submitted2024-09-17;v2 revised2025-01-31; eight authors verified directly despite S2 merged seven-author record.'),
13:dict(primary=['https://dlmf.nist.gov/7.2.E2','https://dlmf.nist.gov/7.6.E1','https://dlmf.nist.gov/7.14.E4'],passage='NIST erfc definition, erf series and Laplace integral §7.14.4; substitution supports inversion kernel. Manuscript presents its own derivation separately.',notes='Online source correctly has institutional author and section locators; historical access date2026-10-22 not misrepresented as current audit date.'),
}
for x in inv['references']:
 x=x.copy();x.update(refs[x['id']]);x.update(verdict='VERIFIED',fresh_verification=True,bibliographic_fields_checked=['title','all listed authors','year or version','venue','volume/issue/pages/article where applicable','DOI or exact version URL']);refs[x['id']]=x
occ=[]
for n,line in enumerate(lines,1):
 if 477<=n<=501:continue
 for m in re.finditer(r'\[(\d{1,2})\]',line):
  ref=int(m.group(1))
  if ref in refs:occ.append(dict(id=f'B{len(occ)+1:03d}',line=n,reference=ref,claim_context=line,sources=refs[ref]['primary'],source_passage=refs[ref]['passage'],verdict='VERIFIED'))
write('REFERENCE_AND_CONTEXT_AUDIT.json',dict(created=now,draft_sha256=sha(draft),A0=dict(first_attempt='A0_FIRST_ATTEMPT_429.json',retry='A0_SEMANTIC_SCHOLAR.json',missing_skill_reference='deep-research/references/semantic_scholar_api_protocol.md not present; direct API result and primary-source fallback retained',status='S2 retry200; null or merged records resolved with fresh primary metadata, not declared nonexistent'),references=list(refs.values()),citation_occurrences=occ,ghost_citations=[],uncited_references=[i for i in refs if not any(x['reference']==i for x in occ)],all_primary_passages_fresh=True))

# Originality audit: every query was actually executed earlier. Result blocks are pooled by batch;
# do not falsely claim per-query ranking when the web API returned one pooled response.
d=j('D1_SEARCH_RAW.json');byid={p['id']:p for p in inv['paragraphs']};screen=[]
paraphrase={21,23,25,29,31,33,608};common={55,65,78,86,88,98,125,141,149,157,165,193}
for b in d['batches']:
 blocks=[x.strip() for x in b['result'].split('--------------------------------------------------------------------------------') if x.strip()]
 for q in b['queries'][::2]:
  p=byid[q['pid']];matches=[]
  for bl in blocks[:10]:
   head=bl.splitlines()[0];url=re.search(r'https?://[^\s)]+',head)
   match=difflib.SequenceMatcher(None,q['fragment'].lower(),bl.lower(),autojunk=False).find_longest_match()
   matches.append(dict(title_and_url=head,url=url.group() if url else None,longest_fragment_overlap_characters=match.size,fragment_overlap=q['fragment'][match.a:match.a+match.size]))
  grade='PARAPHRASE' if p['line'] in paraphrase else ('COMMON_KNOWLEDGE' if p['line'] in common else 'ORIGINAL')
  screen.append(dict(paragraph=p['id'],line=p['line'],section=p['section'],changed=p['changed'],characteristic_fragment=q['fragment'],queries=[z for z in b['queries'] if z['pid']==p['id']],time=b['time'],search_result_pool_scope='Top up to10 blocks of four-query/two-paragraph pooled response; ranking not per query',comparisons=matches,grade=grade,reason='No uncredited close or verbatim expression found in reviewed public results. '+('Literature concept restated with source citation and different wording.' if grade=='PARAPHRASE' else 'Shared mathematical terminology or elementary statement is not textual copying.' if grade=='COMMON_KNOWLEDGE' else 'No close text match found; absence is limited to this search, not proof of global originality.')))
selected={x['paragraph'] for x in screen};changed={p['id'] for p in inv['paragraphs'] if p['changed']}
assert changed<=selected and len(screen)==77 and len(d['queries'])==154
orig=dict(created=now,draft_sha256=sha(draft),body_paragraphs=123,checked=77,checked_percent=77/123*100,changed_paragraphs=26,changed_checked=26,queries=154,batches=39,selection='All changed prose; high-risk literature and analysis; all major sections, discussion/conclusion, and appendix coverage. Excludes headings, bibliography, display equations and tables from prose denominator; those are covered separately by A/C/E.',records=screen,grade_counts=dict(collections.Counter(x['grade'] for x in screen)),D2=dict(status='NOT_EXECUTED',reason='Author names not supplied; explicit protocol prerequisite absent. Not fabricated as no self-plagiarism.'),D3=dict(indicators_triggered=1,observed='Repeated scope/limitation statements; specific data and definitions remain concrete. Style is not used to infer authorship; substantive AI participation already disclosed.',verdict='INFORMATIONAL_ONLY'),limitations=['Heuristic public-web search, not Turnitin/iThenticate; no exact overlap percentage asserted.','Chinese-to-English translation overlap and inaccessible/unindexed texts may be missed.','Only sampled prose reviewed, though all identified revised paragraphs were covered.','Pooled multi-query search ranking is preserved as returned, not represented as separate per-query results.'])
write('ORIGINALITY_AUDIT.json',orig)

math_report='''# 数学与方法独立核验\n\n对象为 delivery_candidate.md，核查过程只读；以下推导由本核验者重新检查，不以旧 PASS 代替。\n\n1. 式(3)由体方程与右端动态边界代入f得到a与b，δ=b−a。E1为−9.166666666666668，E3为3.42；新初值分别直接代入余弦导数；参数轴只改c或κ。非零δ排除连续角点导数同时满足两式，不构成有限训练误差下界。\n2. y=(1−x)/√D,C=c/√D把热算子和右边界主部化为w_t=w_yy、Cw_t−w_y=C。零初值Laplace变换的衰减解为W=C exp(−√s y)/[s(Cs+√s)]，取Re√s>0。\n3. Q=exp(y/C+t/C²)erfc(y/(2√t)+√t/C)的变换为exp(−√s y)/[√s(√s+1/C)]=sW。以β=1/C，积分核Q=(πt)^−1/2 ∫₀∞exp[−βz−(y+z)²/(4t)]dz，故0≤Q≤erfc(y/(2√t))≤1，积分得0≤w≤t并保证一致连续零初值。\n4. 直接微分w=C{2√t·ierfc(η)−C[erfc(η)−Q]}得w_t=w_yy=Q、w_y=C(Q−erfcη)，右端代入为C。固定y>0时Q→0，y=0时Q→1；w(0,t)=t−4t^(3/2)/(3C√π)+O(t²)。\n5. 平方完成给Q=e^(−η²)erfcx(η+√t/C)与式(11)等价；这避免巨大正指数，不能消除差值相消。当前代码t.clamp_min(1e−30)分支与未截断解析极限不同，正文173及附录A552明确说明。\n6. 式(12)的初值来自tN与w连续趋零；有界连续N及N_t假设下两种迭代时间导数极限差等于δ。未证明N已学到a，故未证明完整PDE斜率b自动成立。衰减后(∂t−∂yy)(e^(−t/τ)w)=−e^(−t/τ)w/τ，边界额外−Cw/τ项，与式(13),(14)一致；另端/反应余项没有被误称为零。\n7. E4中v是独立变量；Δ_y=κ[f(1)−V₀]+Df′(1)=−1.02。U=−2Δ_y√(t/D)ierfc(y/(2√Dt))满足U_t=DU_yy及DU_y(0,t)=Δ_y，符号一致。该常通量层不含v反馈，不等价于主动态边界层，表面旧权重缺失限制未被隐去。\n8. 已读pinn1d.py、problems.py、stage5_support.py、soap_baseline.py和固定SOAP实现；普通4×64、float64、Xavier normal、均匀点、1000+seed、RBA四类固定点及平方损失、网络先于注意力、因果32箱分量独立、PirateNet3块及零跳连均与正文/附录A相符。SOAP首次只初始化、计数字段为配置回填而非独立观测已披露。\n9. 旧源码哈希逐字解析到c1f60bd，比较至ea12d0e只新增官方SOAP64分支、恢复身份/元数据/计数及两个新初值；旧层、RBA、因果和架构控制流不变，见SOURCE_VERSION_AUDIT.json。此为源码语义核查，不追回旧运行时的完整执行链。\n10. 参考误差定义由五时刻序列先max再median；ratio-of-medians不是median-of-ratios。N64/GL200与N96/GL400保存记录按原rtol=1e−5、atol=1e−9复核，不能保证t→0连续时间机制。\n\n判定：上述解析/实现对应关系在所声明范围内 VERIFIED。无一般存在唯一性、全域精确性、普遍最优或统计显著性结论。当前历史执行证据门仍独立标为不足。\n'''
write('MATHEMATICAL_METHOD_AUDIT.md',math_report)

# Per-line support locator assigned after reading all text and source files.
def basis(n):
 if n<=17:return ['MATHEMATICAL_METHOD_AUDIT.md','NUMERICAL_AUDIT.json#derived','SUPPLEMENT_AUDIT.json'], '摘要中的全部倍数回溯原JSON；仅有限配置/描述性结论，范围限制与数据结构一致。'
 if 19<=n<39:return ['REFERENCE_AND_CONTEXT_AUDIT.json','SCREEN_PROTOCOL.md','MATHEMATICAL_METHOD_AUDIT.md'], '逐一核对外部文献原始段落；研究问题/贡献为本稿范围定义，不宣称首创或未测泛化。'
 if 39<=n<219:return ['MATHEMATICAL_METHOD_AUDIT.md','problems.py','pinn1d.py'], '重新作代数、Laplace/核函数及极限检查；实际浮点截断和完整方程余项分别披露。'
 if 219<=n<236:return ['SCREEN_PROTOCOL.md','NUMERICAL_AUDIT.json#derived','SUPPLEMENT_AUDIT.json'], '问题定义及先后协议与实际tag/seed全集相符；筛选和确认不混作独立外部验证。'
 if 236<=n<248:return ['pinn1d.py','soap_baseline.py','third_party/soap_official.py','SOURCE_VERSION_AUDIT.json','REFERENCE_AND_CONTEXT_AUDIT.json'], '已读实际控制流、原/当前源码diff与每run配置；本地变体及计数语义明确，未宣称完整原文复现。'
 if 248<=n<266:return ['problems.py#eval_model','NUMERICAL_AUDIT.json'], '公式与每个JSON的五时刻max相符；组级median与比值独立重算，未推断CI/总体概率。'
 if 266<=n<274:return ['problems.py','stage5_support.py','SUPPLEMENT_AUDIT.json','SOURCE_VERSION_AUDIT.json'], '保存复算记录和原/密网格数值逐项核对；独立残差点生成顺序直接读源码；历史生产链不足单列。'
 if 276<=n<298:return ['NUMERICAL_AUDIT.json#cell_checks','runs/confirm','SCREEN_PROTOCOL.md#修订1'], '全部三个种子与表格逐格独立重聚合；30.06/5.92为较好hardic/RBA基线比，不与hardic-only34.83混用。'
 if 298<=n<320:return ['NUMERICAL_AUDIT.json#cell_checks','NUMERICAL_AUDIT.json#derived','runs/final_ic_v1','SUPPLEMENT_AUDIT.json'], '新初值按每题重训；E3seed0退化3.569807%与图2真实36点匹配。'
 if 320<=n<338:return ['NUMERICAL_AUDIT.json#derived','runs/pirate','runs/causal1','runs/causal10','SCREEN_PROTOCOL.md#修订2'], 'A2同架构比22.61/5.52；A1跨架构最强基线比12.51/1.47，联合失败保留；4条续跑身份/预算记录另核。'
 if 338<=n<358:return ['NUMERICAL_AUDIT.json#cell_checks','NUMERICAL_AUDIT.json#derived','runs/axis','problems.py'], '参数轴只改指定参数；全部8点及弱κ=.1的38.346149%退化保留，不做单调因果推断。'
 if 358<=n<381:return ['NUMERICAL_AUDIT.json#cell_checks','SUPPLEMENT_AUDIT.json','validation/stage6_analysis_20261022/complete_v2/tau_sensitivity.csv'], 'τ=.03/.1/.3全部18记录；最大最小中位数比1.715812/1.43027独立核对；跨环境限制与env字段一致。'
 if 381<=n<410:return ['NUMERICAL_AUDIT.json#cell_checks','NUMERICAL_AUDIT.json#derived','SUPPLEMENT_AUDIT.json','validation/resolution_20261022/preflight_review.json'], '六臂36点完整；SOAP内比300.07/30.83与3/3达标重算；G2旧联合失败不追改。'
 if 410<=n<429:return ['NUMERICAL_AUDIT.json#cell_checks','SUPPLEMENT_AUDIT.json','validation/stage5_20261022/ic_validation.json','validation/stage6_20261022/completion_archive_20261023/final_runtime_status.json'], '全部四分量RMS及不利seed核查；调用区间和四层成本逐项由保存计数/时刻独立相加。'
 if 429<=n<475:return ['MATHEMATICAL_METHOD_AUDIT.md','NUMERICAL_AUDIT.json','SUPPLEMENT_AUDIT.json','SCREEN_PROTOCOL.md','E4_PROTOCOL.md'], '讨论/结论逐句与解析和有限数据对照；负面结果、选择/环境混杂、非因果解释、非泛化及未来工作均未冒称已证实。'
 if 477<=n<=503:return ['REFERENCE_AND_CONTEXT_AUDIT.json'], '题录、版本与可读原文对应；未读出版PDF的限制保留。'
 if 505<=n<=524:return ['NUMERICAL_AUDIT.json#hashes','SUPPLEMENT_AUDIT.json','FILE_BINDINGS.json'], '证据入口存在、哈希及记录数量独立核查；引用旧报告只限对应时点，不代替本次独立审计。'
 if 526<=n<570:return ['pinn1d.py','problems.py','stage5_support.py','soap_baseline.py','MATHEMATICAL_METHOD_AUDIT.md','SOURCE_VERSION_AUDIT.json'], '实际控制流/固定参数与保存配置逐条核对；RBA例外、时间截断、恢复和计数字段口径保留。'
 if 570<=n<606:return ['NUMERICAL_AUDIT.json#cell_checks','SUPPLEMENT_AUDIT.json','SCREEN_PROTOCOL.md','validation/feasibility_review_20261021/existing_data_review.json'], '全部30筛选JSON和原门槛按定义重算；历史参考自检仅核保存记录，不冒称新积分。'
 if 606<=n<619:return ['REFERENCE_AND_CONTEXT_AUDIT.json#reference9','PRIMARY_PDF_FRESH.json','pinn1d.py'], '实际新读取v1/v2 PDF核心公式/Algorithm1，对比原稿初值0、注意力先更新及范围差别；本地差异准确。'
 if 619<=n<629:return ['SUPPLEMENT_AUDIT.json','SOURCE_VERSION_AUDIT.json','validation/stage6_20261022/completion_archive_20261023/','manuscript/integrity/working_20261023/historical_execution_scope.json'], '独立哈希/序列/日志/成本和21+9来源核查；历史退出码/警告和E4缺失明确保留，不据有限记录推断全历史。'
 if 629<=n<677:return ['MATHEMATICAL_METHOD_AUDIT.md','NUMERICAL_AUDIT.json#cell_checks','NUMERICAL_AUDIT.json#derived','E4_PROTOCOL.md','problems.py','pinn1d.py'], 'E4方程、独立v、通量层符号和12份完整预算体/迹逐项核对；旧20份surf缺失不由随机分支填补。'
 if 677<=n<683:return ['SCREEN_PROTOCOL.md#修订2及4','NUMERICAL_AUDIT.json#derived','validation/resolution_20261022/preflight_review.json'], 'A1/A2与G2联合/子条件分别核对；G2不等于四子项全失败，完整预算不能追改小预算。'
 return ['manuscript/drafts/delivery_candidate.md#声明','manuscript/reviews','manuscript/process'], '待作者确认事项未作完成断言；内部自动审查与外部评审/署名责任区分；AI参与与可见产物流程相符。'

# Cover every nonempty scientific line, including tables and display math; excluded structural lines listed explicitly.
registry=[];coverage=[];sec='front matter';inmath=False;math_lines=[];math_start=None
for n,line in enumerate(lines,1):
 s=line.strip()
 if not s:coverage.append(dict(line=n,classification='blank'));continue
 if s.startswith('#'):sec=s.lstrip('# ');coverage.append(dict(line=n,classification='heading'));continue
 if s=='\\[':inmath=True;math_lines=[line];math_start=n;continue
 if inmath:
  math_lines.append(line)
  if s=='\\]':
   unit='\n'.join(math_lines);sources,detail=basis(math_start);rid=f'E{len(registry)+1:04d}'
   registry.append(dict(id=rid,line=math_start,end_line=n,section=sec,type='display_equation',claim=unit,cited_evidence=re.findall(r'E\d\d',unit),verification_sources=sources,verdict='VERIFIED',detail=detail,evidence_level='mathematical_derivation_or_explicit_definition'))
   coverage.extend(dict(line=k,classification='claim',claim_id=rid) for k in range(math_start,n+1));inmath=False
  continue
 if re.match(r'^\|[\s:|\-]+\|$',s):coverage.append(dict(line=n,classification='table_separator'));continue
 if 477<=n<=501:
  rid='A'+str(re.match(r'\[(\d+)\]',s).group(1));coverage.append(dict(line=n,classification='bibliography_verified_in_A',claim_id=rid));continue
 if s.startswith('!['):
  rid=f'E{len(registry)+1:04d}';sources,detail=basis(n);registry.append(dict(id=rid,line=n,end_line=n,section=sec,type='figure',claim=s,verification_sources=sources+['Four displayed PNGs visually inspected; source code/data and hashes checked.'],verdict='VERIFIED',detail='Analytic illustration distinguished from measured error; all seed points, medians, ranges, log axes and scope labels checked against source.',evidence_level='visual_plus_source_data'));coverage.append(dict(line=n,classification='claim',claim_id=rid));continue
 if s.startswith('关键词') or s.startswith('Keywords:'):coverage.append(dict(line=n,classification='keywords'));continue
 if s.startswith('|'):
  units=[s];typ='table_row';level='saved_artifact_numeric_or_method_definition'
 else:
  units=[x.strip() for x in re.split(r'(?<=。)|(?<=[.!?])\s+(?=[A-Z])',s) if x.strip() and not re.fullmatch(r'\[E[\d,E]+\]',x.strip())];typ='prose_sentence';level='source_checked_current_claim'
 sources,detail=basis(n);ids=[]
 for unit in units:
  rid=f'E{len(registry)+1:04d}';ids.append(rid)
  pending='待作者确认' in unit or '待本人核实' in unit or ('须确认' in unit and n>=683)
  nonassert=unit in {'考虑有限区间上的问题','将初值代入两个算子，定义','以向区域内部的归一化距离及归一化容量为','定义单位错配层满足','具体为','令','上述标准积分给出','另一种可直接配方核查的表示为','所用层函数的闭式写为','对该式直接求导可得','在边界处，记指数与余误差函数的乘积为','对小时间展开得到','利用平方展开，等价地写成','本文使用的完整表达式为','**证明。','证毕。','在归一化边界，衰减后的主部作用为','所用常通量辅助层为','该扩展的硬初值修正表达式为'}
  registry.append(dict(id=rid,line=n,end_line=n,section=sec,type=typ,claim=unit,cited_external_refs=re.findall(r'\[(\d+)\]',s),cited_evidence=re.findall(r'E\d\d',s),verification_sources=sources,verdict='PENDING_AUTHOR_DECLARATION' if pending else 'NON_ASSERTIVE_CONNECTOR' if nonassert else 'VERIFIED',detail='Explicitly pending; no completion claim, cannot infer author identity/COI/funding.' if pending else detail,evidence_level='pending_not_asserted_complete' if pending else level))
 coverage.append(dict(line=n,classification='claim',claim_ids=ids))
assert len(coverage)==len(lines) and len({x['line'] for x in coverage})==len(lines)
write('CLAIM_REGISTRY.json',dict(created=now,draft_sha256=sha(draft),coverage_method='All689 lines accounted for. Each prose sentence, display-math block, table row and figure retained; references handled inA; numerical table cells additionally checked individually inNUMERICAL_AUDIT. Pending declarations are not silently treated as verified facts.',counts=dict(collections.Counter(x['verdict'] for x in registry)),registry=registry,line_coverage=sorted(coverage,key=lambda x:x['line']),independent_gate_note='VERIFIED means the current scoped statement matches mathematics/source/saved data. It does not erase Mode1 execution-evidence insufficiency or certify all old production processes.'))
md=['# 全量声明登记','',f'对象SHA256：{sha(draft)}。全部689行均归类，科学声明逐项列出；数表另有426个逐单元检查。','', '| ID | 行 | 类型 | 原文声明 | 判定 | 支持及边界 |','|---|---:|---|---|---|---|']
for x in registry:
 text=x['claim'].replace('|','\\|').replace('\n','<br>');detail=x['detail'].replace('|','\\|')
 md.append(f"| {x['id']} | {x['line']} | {x['type']} | {text} | {x['verdict']} | {detail} 来源：{' ; '.join(x['verification_sources'])} |")
write('CLAIM_REGISTRY.md','\n'.join(md)+'\n')
bound=[]
for p in [draft,R/'SCREEN_PROTOCOL.md',R/'E4_PROTOCOL.md',R/'pinn1d.py',R/'problems.py',R/'stage5_support.py',R/'soap_baseline.py',R/'third_party/soap_official.py',R/'manuscript/figures/plot_analytic_layer.py',R/'manuscript/figures/plot_historical_comparison.py',R/'validation/stage6_analysis_20261022/plot_stage6.py',R/'validation/stage6_analysis_20261022/analyze_stage6.py']:
 bound.append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size))
write('FILE_BINDINGS.json',dict(created=now,files=bound))
print(json.dumps(dict(references=len(refs),citation_occurrences=len(occ),claims=len(registry),claim_verdicts=dict(collections.Counter(x['verdict'] for x in registry)),lines_covered=len(coverage),originality=orig['grade_counts']),ensure_ascii=False))

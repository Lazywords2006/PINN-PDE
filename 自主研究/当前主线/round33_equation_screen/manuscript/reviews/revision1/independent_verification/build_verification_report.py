"""Serialize the EIC's completed manual re-review and independent evidence."""
from pathlib import Path
import datetime
import hashlib
import json

OUT=Path(__file__).resolve().parent
MAN=OUT.parents[2]
ROOT=MAN.parent
def js(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def link(label,p,line=None):return f'[{label}](<{Path(p).as_posix()}{":"+str(line) if line else ""}>)'
draft=MAN/'drafts/complete_revised1a.md'
tracker=js(MAN/'reviews/revision1/REVIEW_ITEMS.json')
responses={x['编号']:x for x in js(MAN/'process/complete_revised1a/RESPONSE_TO_REVIEWS.json')['responses']}
integrity=js(OUT/'input_integrity.json')
assert sha(draft)==integrity['draft_sha256']

# Each finding was reached after reading the original comment, author's claim,
# manuscript revision, and the independent sources named below.
findings={
'M1':('FULLY_ADDRESSED','pinn1d.py:58、69直接给出1e-30；stage5_support.py:46—64给出default_rng(330500)、五次数组抽样顺序及8192/1024/1024/1024分量计数。稿件L173、270、543均准确抄录，端点不再含混。源码哈希与作者冻结绑定一致，本复核未修改采样或训练。',['pinn1d.py:58','stage5_support.py:46','input_integrity.json']),
'M2':('FULLY_ADDRESSED','problems.py:95—106直接定义E1仅变c，G=0.3u；E3以G=κ(u−1)变κ，D=0.1、c=0.3及反应/初值固定。运行名E3_k由同一κ格式化。L223、354对应，表5数据行均原样保留。',['problems.py:95','SCREEN_PROTOCOL.md:85','input_integrity.json']),
'M3':('FULLY_ADDRESSED','全文已无N04；L550直接引出原有调用和损失字段说明。对照原稿，该段除引导短语外保持一致，保留配置调用数、末次记录损失与真实L-BFGS状态的边界。',['change_hunks.json:H37','input_integrity.json']),
'DR1':('FULLY_ADDRESSED','L354给出两条参数轴、所有固定量与k标签。逐项比对problems.py:95—106和SCREEN_PROTOCOL修订2第B组一致，没有改表5结果或把κ写成容量c。',['problems.py:95','SCREEN_PROTOCOL.md:85','change_hunks.json:H15']),
'DR2':('FULLY_ADDRESSED','附录E的PDE、交换通量、独立v方程、初值、D=0.1及κ=γ=V0=1与problems.py、pinn1d.py和E4_PROTOCOL一致。独立求导得U_y=Δ_y/D·erfc(y/(2√Dt))，U_t=D U_yy，且Δ_y=-1.02；该辅助层不同于式12。直接重聚合12份e4confirm原JSON，四行体/迹中位数、逐种子值和达标数全部匹配表E1；0.004675169889310211/0.005576309573543175=0.8383985551109958。缺失20份表面分支权重、探索性质及不提供可复现v数据均保留。',['problems.py:110','pinn1d.py:66','pinn1d.py:199','pinn1d.py:234','E4_PROTOCOL.md:9','raw32_reaggregation.json']),
'DR3':('FULLY_ADDRESSED','N04已删除。L335首次写跨架构强基线判据A-1并指附录F；L408首次写小预算效果判据G2及其两类对象。L514的E09直接到附录E表E1、协议具体节与原JSON，L673给实际分子/分母及精确记录映射，已不只指目录。',['change_hunks.json:H13','change_hunks.json:H19','change_hunks.json:H29','change_hunks.json:H43']),
'DA-m1':('FULLY_ADDRESSED','E3轴由源码支持；E4定义、初值、两分支及常通量层在附录E集中补齐。L654明确不含表面反馈，衰减后不强制交换条件或表面ODE；并未将其写成式12原样推广。负面比值保留且由原JSON复得。',['problems.py:100','pinn1d.py:66','pinn1d.py:212','raw32_reaggregation.json']),
'DA-m2':('FULLY_ADDRESSED','直接读取12份PirateNet原JSON：E1两方法seed0/1为Python3.12.6、Torch2.14.1+cpu，并保留16000/16500等续跑位置；E1 seed2及E3六条为历史Python3.13.16、Torch2.14.1+cu130。结合SCREEN_PROTOCOL修订4—5的四个历史检查点本机续跑记录，表4逐种子来源披露相符。复得22.6078141960和5.5175385428，所有逐种子表行未变。L333明确混合来源中位数不是统一环境随机重复分布估计，也未推断已证明不公平配对。',['raw32_reaggregation.json','SCREEN_PROTOCOL.md:122','SCREEN_PROTOCOL.md:137','input_integrity.json']),
'DA-m3':('FULLY_ADDRESSED','代码t.clamp_min(1e-30)与稿件精确一致。对0≤t<1e-30，层中rt时间依赖被固定，而exp(-t/τ)和f+tN依然含时间，故截断AD极限并非未截断解析命题的证据。L173、185、543、552对此分开说明，浮点初值误差限定保留。',['pinn1d.py:56','pinn1d.py:212','change_hunks.json:H3','change_hunks.json:H5','change_hunks.json:H37']),
'EIC-M1':('FULLY_ADDRESSED','附录F与SCREEN_PROTOCOL:82—83、123—126逐项一致：A-1是MLP修正对两档因果及PirateNet硬初值的最佳者；G2固定Adam修正对四基线，另判SOAP叠加，两方程分别要求3倍且两个候选种子≤0.01。种子100/101、4000+500和联合升级条件正确。明确联合未满足不等于四子判断全失败；旧A-1/G2与full_v1文件哈希均未改。',['SCREEN_PROTOCOL.md:82','SCREEN_PROTOCOL.md:123','input_integrity.json','change_hunks.json:H43']),
'EIC-M2':('FULLY_ADDRESSED','L223与L354以Gκ(u)=κ(u−1)明确算子，κ=0.1/1/3、固定c=0.3，并说明k就是κ；与problems.py:100—106直接匹配。',['problems.py:100','change_hunks.json:H7','change_hunks.json:H15']),
'R3-1':('FULLY_ADDRESSED','E3参数轴和固定量可从表5注直接恢复；精确下界在正文及附录出现。命题1加“未截断解析表达式”，附录说明截断AD和浮点非逐位零，满足两方面的原验收条件。',['problems.py:100','pinn1d.py:58','change_hunks.json:H3','change_hunks.json:H15','change_hunks.json:H37']),
'R3-2':('FULLY_ADDRESSED','附录E式E1—E4及表E1完整，明确v与u(1,t)不同；原JSON五时刻最大值再三种子中位数逐格复算匹配。0.838负面比值、筛选失败、追加探索及20份表面权重缺失原边界均保持。',['raw32_reaggregation.json','E4_PROTOCOL.md:9','change_hunks.json:H43']),
'R3-3':('FULLY_ADDRESSED','恢复和历史执行范围集中到附录D，§3.4和§4.7保留影响解释的证据及成本摘要。独立计数复得六章1695/2190/2187/2755/1897/763，合计11487；相对原1800/2200/2000/2500/1700/800各在±15%，相对11000为+4.43%。原配置SHA与保护清单匹配，且与事前git提交46855c4中的配置语义一致。原稿11434、排除表题/注11056、误滤所有表号开头正文10213等口径可独立复现，未用新增附录充数或事后改目标。',['independent_counts.json','input_integrity.json','change_hunks.json:H9','change_hunks.json:H21','change_hunks.json:H39','change_hunks.json:H41']),
'M-建议1':('FULLY_ADDRESSED','共用附录E已提供短模型、参数、分支和实际层公式；§5.2和E09可定位表E1。与DR2共用核验，未增设实验门槛。',['raw32_reaggregation.json','change_hunks.json:H43']),
'M-建议2':('FULLY_ADDRESSED','对照全部删除和新增区块，恢复细节确已集中，§4.3及τ段落压缩；直接影响各比较的环境、非置信区间及负面结果限定保留。表数据和图引用均未删，作者说明保留的不同作用充分。',['change_hunks.json','input_integrity.json']),
'DR-建议1':('FULLY_ADDRESSED','由problems.py中f(1)=0、f′(1)=f″(1)=-0.2、D=0.1、c=0.3独立代入δ=boundary−bulk，得到(0.02+κ)/0.3+0.02。κ=0.1/1/3对应0.42/3.42/10.0866666667，与表5舍入一致；未推出收益单调性。',['problems.py:46','problems.py:100','change_hunks.json:H15']),
'EIC-建议1':('FULLY_ADDRESSED','历史执行长段从附录A移至D，恢复细节在正文压缩而保留完整入口。比较旁环境边界与讨论中的解释范围各有不同作用，未以压缩为由丢弃负面结果或旧证据缺口。',['change_hunks.json:H9','change_hunks.json:H21','change_hunks.json:H39','change_hunks.json:H41']),
'EIC-建议2':('FULLY_ADDRESSED','附录A新增层函数截断行，与pinn1d.py:58、69准确对应；表后解释理想极限与截断AD差异，无需重复添加科学段落。',['pinn1d.py:58','pinn1d.py:69','change_hunks.json:H35','change_hunks.json:H37']),
'R3-建议1':('FULLY_ADDRESSED','L457明确可靠f′(1)、f″(1)和算子参数是输入要求，并将带噪或插值导数的不确定性标为未验证。与δ计算依赖相符，没有新增带噪实验或保证。',['problems.py:46','change_hunks.json:H25']),
'R3-建议2':('FULLY_ADDRESSED','L457将主目标量限制到本文体相对误差与独立迹误差，指出边界储存及交换通量需由应用选定。没有将现有排序外推到未计算物理量。',['change_hunks.json:H25']),
'R3-建议3':('PARTIALLY_ADDRESSED','未另加一个环境总表，作者已说明不重复预算表及混合续跑难以用单标签概括的原因。现有附录A预算表、表4逐种子来源、附录D具名CSV及§5.3混杂边界可定位，未声称等时间收益或固定开销；部分采纳及理由符合原可选验收。',['raw32_reaggregation.json','change_hunks.json:H13','change_hunks.json:H41']),
'R3-建议4':('NOT_ADDRESSED','未新增Melenk与Babuška文献。作者理由是与本轮局部披露修订及有限主张关系较弱，扩展相关工作需额外原文核查。该项本为可选；原13条题录逐字不变，没有挪用未读来源作PINN保证，理由可接受。',['input_integrity.json']),
'R3-建议5':('NOT_ADDRESSED','未新增Oberkampf与Trucano文献。作者以已有代码/数值复算与历史执行范围披露回应概念分层意图，不扩展成验证框架综述；原建议允许不采纳且不要求物理实验。范围在§3.4、§5.1和附录D可确认，理由可接受。',['change_hunks.json:H9','change_hunks.json:H41','input_integrity.json']),
'R3-建议6':('NOT_ADDRESSED','未新增Morris文献。作者说明未来设计尚未展开，维持三档有限灵敏度而不借名称提升结论；§4.5、§5.3—5.4与此一致。该项是可选未来方向，理由可接受，不应为了引用数强制补文献。',['change_hunks.json:H17','input_integrity.json']),
}
assert len(findings)==25
rows=[]
for item in tracker['修订条目']:
    key=item['编号'];author=responses[key];status,finding,evidence=findings[key]
    rows.append(dict(id=key,priority=item['优先级'],original_comment=item['原报告位置']['原文'],original_source=item['原报告位置'],acceptance_conditions=item['验收条件'],author_claim=author['作者答复'],author_disposition=author['作者处置'],author_reason=author['未采纳部分及理由'],author_revision_locations=author['实际修订位置'],independent_status=status,claim_and_location_verified=True,independent_verification=finding,independent_evidence=evidence,verifier='EIC ordinary re-review; /root/r33_full_eic',author_self_status_not_used_as_evidence=True))
coverage_descriptions={
'H1':'状态改为五份自动审阅意见后的修订初稿，不表示原full_v1合议成功；待核验、未投稿及人类确认均保留。',
'H3':'截断常数、理想解析式与浮点区别；逐行对照pinn1d.py。',
'H5':'命题范围改为未截断解析表达式；没有新增数学保证。',
'H7':'参数轴进入边界函数的位置及新初值范围；对照problems.py。',
'H9':'抽样顺序和分量数对照stage5_support；删除的恢复细节仍在附录D。',
'H11':'PirateNet收益叙述压缩，22.61/5.52与六配对结论保留。',
'H13':'逐种子来源直接核12份JSON；A-1名称和附录入口对照原协议。',
'H15':'E1/E3固定量与κ公式对照源码并独立算δ。',
'H17':'τ说明压缩，跨环境混杂、三种子局限和未搜索均保留。',
'H19':'G2比较对象、种子及附录入口对照协议，旧失败未改。',
'H21':'四层成本数字未变；移出的轮询/恢复定义仍在附录D。',
'H23':'E4正文入口、比较方向与0.838由原JSON核验，负面范围保留。',
'H25':'f导数及目标量条件与实际δ/指标依赖一致，噪声及其他物理量不作已验证主张。',
'H27':'只改引用上下文入口；13条参考文献逐字一致，路径实际存在。',
'H29':'E09精确指表E1、E4协议节及原JSON；体/迹与表面缺口区分。',
'H31':'E14保留v1数据核查及修订自核入口，并明示不能代替独立审查。',
'H33':'E17绑定32份原JSON及源码，独立按文件夹枚举和重聚合核验全部32条。',
'H35':'实现表精确截断行对照两类层函数。',
'H37':'N04删除；新增截断AD解释与实际计算图一致，原字段解释未改。',
'H39':'旧历史执行长段改为附录D入口。',
'H41':'附录D新增段与旧稿附录A对应段逐字相同，未重写原日志或表面权重边界。',
'H43':'完整阅读新增54行附录E/F：逐方程/公式对照源码和协议、独立微分U、复算表E1全部数据，逐门槛对照A-1/A-2/G2，探索与历史缺口完整保留。',
}
hunks=js(OUT/'change_hunks.json')
assert {h['id'] for h in hunks}==set(coverage_descriptions)
coverage=[dict(id=h['id'],kind=h['kind'],old_lines=h['old_lines'],new_lines=h['new_lines'],all_new_and_removed_text_read=True,assessment=coverage_descriptions[h['id']],new_blocking_issue=False) for h in hunks]
save('new_content_coverage.json',dict(base_sha256=sha(MAN/'drafts/complete_v1.md'),draft_sha256=sha(draft),changed_hunks=len(coverage),reviewed_hunks=len(coverage),coverage_percent=100,new_or_replaced_lines=84,coverage=coverage,new_references=0,new_blocking_issues=[]))
summary=dict(decision='Accept',decision_scope='Independent ordinary re-review of 25 revision items for complete_revised1a; not a full_v1 panel decision, journal acceptance, PDF/layout verdict or final publication-readiness declaration',draft_sha256=sha(draft),mandatory_total=14,mandatory_fully_addressed=14,suggested_total=11,suggested_responses=11,suggested_response_percent=100,suggested_fully_addressed=7,suggested_partially_addressed=1,suggested_not_addressed_with_reason=3,new_blocking_issues=0,new_content_hunks_reviewed=22,new_content_hunks_total=22,new_content_coverage_percent=100,original_full_v1_status='ABORT; usable=2, panel_size=5; no whole-panel editorial decision',original_contract_or_scores_changed=False)
assert sum(r['priority']=='P1' and r['independent_status']=='FULLY_ADDRESSED' for r in rows)==14
assert sum(r['priority']=='P2' for r in rows)==11
save('VERIFICATION_RESULTS.json',dict(generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),summary=summary,protocol='C:/Users/LazyM/.codex/skills/academic-paper-reviewer/references/re_review_mode_protocol.md',inputs=integrity,items=rows,new_content_coverage_file='new_content_coverage.json',remaining_limitations=['Historical E4 surface-branch weights absent; no reproducible surface-variable quantitative conclusion added.','Mixed execution sources and three seeds do not support unified-environment distributions or statistical-significance claims.','No new training, model loading, reference integration, or PDF/layout examination in this review.','Independent layout/final integrity and human authorship/funding/conflict confirmation remain separate.']))

lines=['# 第一修订稿独立核验报告（普通 re-review）','','## Decision','','**Accept——仅就本次25项普通修订核验。** 14/14必修项为FULLY_ADDRESSED；11/11建议有明确答复，其中7项完整采纳、1项部分采纳、3项不采纳并给出可接受理由。全部22个变更区块、84行新增或替换文本及对应删除内容已检查；未发现新增阻断问题。','','本判定绑定'+link('complete_revised1a.md',draft)+'，SHA256：`'+sha(draft)+'`。这是首次科学修订的排版派生稿。', '', '**原 full_v1 继续保留 ABORT / usable=2, panel_size=5 / 无全轮编辑裁决。** 本次按专用'+link('re-review协议','C:/Users/LazyM/.codex/skills/academic-paper-reviewer/references/re_review_mode_protocol.md',18)+'独立核验作者修订；没有回填、重跑或修改旧契约、旧报告、评分与lint。本判定不代表期刊录用，也不替代另行进行的HTML/PDF检查、最终完整性或人类作者确认。','','## 核验输入与方法','','先读五份原报告、统一25项清单和全部作者答复，再逐项到实际修改位置核对；作者RESOLVED/PENDING等自报状态不作为独立通过证据。直接读取源码与事前协议，按原始结果文件夹独立枚举并重聚合32份JSON；没有训练、载入模型、积分参考解、导入Torch或修改作者输入。','','最终冻结清单18项及其他输入绑定共89项哈希比对均匹配；83次作者定位锚点及所绑稿件SHA检查均匹配（这些是检查次数，包含共享位置）。原五份报告、contract、lint、metadata和原稿均保留原字节。四幅PNG哈希及原图引用未变；原表数据行未删，13条题录逐字一致。详见'+link('input_integrity.json',OUT/'input_integrity.json')+'。','','## Priority 1 — 必修修订','','表中“作者主张”摘取实际答复；完整原文、验收条件、原报告行号/哈希、作者全部定位与独立证据保存在'+link('VERIFICATION_RESULTS.json',OUT/'VERIFICATION_RESULTS.json')+'。','','| 编号 | 原问题 | 作者主张 | 独立状态 | 实际修订位置 | 核验与质量判断 |','|---|---|---|---|---|---|']
def esc(s):return str(s).replace('|','\\|').replace('\n',' ')
for row in rows:
    if row['priority']!='P1':continue
    item=next(i for i in tracker['修订条目'] if i['编号']==row['id'])
    locs=row['author_revision_locations'];locs=[locs] if isinstance(locs,dict) else locs
    locations='；'.join(link(f"L{x['line']}",x['file'],x['line']) for x in locs if x.get('line'))
    lines.append('| '+' | '.join([esc(row['id']),esc(item['问题摘要']),esc(row['author_claim']),row['independent_status'],locations,'✅ 已核验。'+esc(row['independent_verification'])])+' |')
lines+=['','## Priority 2 — 建议修订','','| 编号 | 状态 | 实际处理、独立核验及理由 |','|---|---|---|']
for row in rows:
    if row['priority']!='P2':continue
    lines.append('| '+row['id']+' | '+row['independent_status']+' | '+esc(row['independent_verification'])+' |')
lines+=['','建议答复率为11/11=100%，超过专用协议要求的80%。NOT_ADDRESSED准确表示未加入三篇可选文献，不能把有理由不采纳改写成已加引用，也不能将可选引用变成新硬门槛。Priority 3未在原清单设项。','','## 独立数据与计数证据','','直接重聚合E4筛选8份、完整预算12份和PirateNet12份原JSON。每条均核五个规定时刻、有限体/迹序列及所存max字段，结果与作者映射一致；全部来源SHA和原序列已另存'+link('raw32_reaggregation.json',OUT/'raw32_reaggregation.json')+'。','','| 核对量 | 本次独立结果 | 含义 |','|---|---:|---|','| E4筛选：hardic/RBA较好者 ÷ 修正中位数 | 1.385954885516 | 小于3，原失败保持 |','| E4探索：hardic/RBA较好者 ÷ 修正中位数 | 8.798415864995 | 满足原追加探索比较；不回写筛选 |','| E4 vanilla ÷ 修正体中位数 | 0.838398555111 | 表E1分子、分母及方向一致，负面额外收益结论保持 |','| PirateNet E1 hardic ÷ 修正 | 22.607814196013 | 四舍五入22.61；混合执行来源、描述性 |','| PirateNet E3 hardic ÷ 修正 | 5.517538542773 | 四舍五入5.52；三种子描述性 |','','E4公式还独立核得：`U_y=(Δ_y/D)erfc(y/(2√(Dt)))`，`U_t=D U_yy=−Δ_y exp(−y²/(4Dt))/√(πDt)`，因而边界常通量为Δ_y。代入初值及参数为−1.02。该辅助问题没有表面反馈，乘衰减后的完整表达式不因此自动满足原交换条件，与稿件限定相符。','','计数直接从原稿和修订稿提取六个编号章节，按既有规则排除图题、表格数据、显示公式及附录；包含章/节标题、表题和表注。原配置哈希为`fc04c1df49f7eebda29ab5cb1d993587a2cb2c68283367b68380ce3d532b62aa`，与事前git提交`46855c4b80ab4e7e9620c916b327cde9af9b5191`中配置语义一致。','','| 章 | 原目标 | 本次独立计数 | 偏差 | 原±15% |','|---|---:|---:|---:|---|']
counts=js(OUT/'independent_counts.json')
for name,row in counts['quotas'].items():lines.append(f"| {name} | {row['target']} | {row['actual']} | {row['relative_deviation']*100:+.2f}% | 满足 |")
lines+=['','合计11487，相对11000为+4.43%，满足原±10%。原稿按同一规则为11434；仅再排除表题/注得到11056，误滤所有“表数字”开头论述并排除章标题得到10213。口径差异已能独立复现，不是稿件内容丢失，也未改变原目标；新增附录未充作正文。逐行分类见'+link('independent_counts.json',OUT/'independent_counts.json')+'。','','## 新增内容100%覆盖与新问题检查','','本次对原稿到1a的diff逐区块检查全部新旧文本，覆盖22/22区块、84行新增或替换文本。没有新增参考文献；原13条题录逐字未变，改变的引用上下文链接实际存在。细分覆盖与判断见'+link('new_content_coverage.json',OUT/'new_content_coverage.json')+'；完整新旧文本见'+link('change_hunks.json',OUT/'change_hunks.json')+'。','','| 区块 | 新稿行 | 核验重点 | 新阻断项 |','|---|---|---|---|']
for c in coverage:lines.append(f"| {c['id']} | {c['new_lines'][0]}—{c['new_lines'][1]} | {c['assessment']} | 无 |")
lines+=['','## 判定理由与保留范围','','全部14项必修披露缺口均有明确作者答复、实际修改与独立来源支持；原实验数值、旧失败和证据边界没有因修订被抹除。11项建议均回应，有理由保留文字或不增加可选文献符合原验收弹性。因此本轮普通re-review判为Accept，无遗留必修修订。','','仍保留研究自身局限：E4旧表面分支权重缺失；三种子与混合执行环境不支撑统计显著或统一环境分布推断；五个时刻误差不证明全早时间渐近余项结构；A-1/G2失败及E4额外收益负面结果继续有效。这些已经披露的研究边界不被本次文本修订虚构为解决。','','本次没有作PDF/HTML视觉裁决，也没有宣称补回历史生产链或表面权重。最终发布前的人类署名、单位、基金、利益冲突及最终核验继续保留待确认。','','核验脚本：'+link('verify_revision1.py',OUT/'verify_revision1.py')+'。脚本仅读取输入并将证据写入本独立核验目录；本报告的逐项质量判断由EIC逐项阅读后给出。','']
(OUT/'VERIFICATION_REPORT_CN.md').write_text('\n'.join(lines),encoding='utf-8')
save('REVIEW_DELIVERY_MANIFEST.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),decision=summary,files={str(p):sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='REVIEW_DELIVERY_MANIFEST.json'}))
print(json.dumps(summary,ensure_ascii=False,indent=2))

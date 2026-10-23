# 第一修订稿独立核验报告（普通 re-review）

## Decision

**Accept——仅就本次25项普通修订核验。** 14/14必修项为FULLY_ADDRESSED；11/11建议有明确答复，其中7项完整采纳、1项部分采纳、3项不采纳并给出可接受理由。全部22个变更区块、84行新增或替换文本及对应删除内容已检查；未发现新增阻断问题。

本判定绑定[complete_revised1a.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md>)，SHA256：`398c2a44f2f9fd959b62564ddc599b123a3dd5de168ad0257a8572e188bf92e8`。这是首次科学修订的排版派生稿。

**原 full_v1 继续保留 ABORT / usable=2, panel_size=5 / 无全轮编辑裁决。** 本次按专用[re-review协议](<C:/Users/LazyM/.codex/skills/academic-paper-reviewer/references/re_review_mode_protocol.md:18>)独立核验作者修订；没有回填、重跑或修改旧契约、旧报告、评分与lint。本判定不代表期刊录用，也不替代另行进行的HTML/PDF检查、最终完整性或人类作者确认。

## 核验输入与方法

先读五份原报告、统一25项清单和全部作者答复，再逐项到实际修改位置核对；作者RESOLVED/PENDING等自报状态不作为独立通过证据。直接读取源码与事前协议，按原始结果文件夹独立枚举并重聚合32份JSON；没有训练、载入模型、积分参考解、导入Torch或修改作者输入。

最终冻结清单18项及其他输入绑定共89项哈希比对均匹配；83次作者定位锚点及所绑稿件SHA检查均匹配（这些是检查次数，包含共享位置）。原五份报告、contract、lint、metadata和原稿均保留原字节。四幅PNG哈希及原图引用未变；原表数据行未删，13条题录逐字一致。详见[input_integrity.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/revision1/independent_verification/input_integrity.json>)。

## Priority 1 — 必修修订

表中“作者主张”摘取实际答复；完整原文、验收条件、原报告行号/哈希、作者全部定位与独立证据保存在[VERIFICATION_RESULTS.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/revision1/independent_verification/VERIFICATION_RESULTS.json>)。

| 编号 | 原问题 | 作者主张 | 独立状态 | 实际修订位置 | 核验与质量判断 |
|---|---|---|---|---|---|
| M1 | 补全时间截断、残差点随机数及抽样顺序 | §2.3和附录A均补出t.clamp_min(1e-30)；§3.4列明default_rng(330500)及体x、体t、左端t、右端t、初值x的抽样顺序，数组8192/8192/1024/1024/1024，四残差分量8192/1024/1024/1024。说明两端时间独立，点集未用于训练或选择。只抄录现有实现，没有改代码或重训。 | FULLY_ADDRESSED | [L173](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:173>)；[L270](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:270>)；[L543](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:543>) | ✅ 已核验。pinn1d.py:58、69直接给出1e-30；stage5_support.py:46—64给出default_rng(330500)、五次数组抽样顺序及8192/1024/1024/1024分量计数。稿件L173、270、543均准确抄录，端点不再含混。源码哈希与作者冻结绑定一致，本复核未修改采样或训练。 |
| M2 | 在表5附近定义两条参数轴 | 在§3.1指出κ进入边界函数；表5注给出E1只改c且D=1、R=0、G(u)=0.3u和初值不变，E3为Gκ(u)=κ(u−1)、κ∈{0.1,1,3}，D=0.1、c=0.3、R=u(1−u)和初值不变。明确运行名k就是κ；保留表5全部结果，另给错配公式校验。 | FULLY_ADDRESSED | [L223](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:223>)；[L354](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:354>) | ✅ 已核验。problems.py:95—106直接定义E1仅变c，G=0.3u；E3以G=κ(u−1)变κ，D=0.1、c=0.3及反应/初值固定。运行名E3_k由同一κ格式化。L223、354对应，表5数据行均原样保留。 |
| M3 | 消除附录A的N04悬空引用 | 删除未定义的内部编号N04，直接引入调用与损失字段口径；保留完成循环后写入配置计数、末次记录损失不等于终点重评、实际L-BFGS状态计数的既有说明。全文检索确认无N04残留。 | FULLY_ADDRESSED | [L550](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:550>) | ✅ 已核验。全文已无N04；L550直接引出原有调用和损失字段说明。对照原稿，该段除引导短语外保持一致，保留配置调用数、末次记录损失与真实L-BFGS状态的边界。 |
| DR1 | 补足参数化边界、取值与固定条件 | 在§3.1指出κ进入边界函数；表5注给出E1只改c且D=1、R=0、G(u)=0.3u和初值不变，E3为Gκ(u)=κ(u−1)、κ∈{0.1,1,3}，D=0.1、c=0.3、R=u(1−u)和初值不变。明确运行名k就是κ；保留表5全部结果，另给错配公式校验。 | FULLY_ADDRESSED | [L223](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:223>)；[L354](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:354>) | ✅ 已核验。L354给出两条参数轴、所有固定量与k标签。逐项比对problems.py:95—106和SCREEN_PROTOCOL修订2第B组一致，没有改表5结果或把κ写成容量c。 |
| DR2 | 为E4负面结果补最小可复核科学定义 | 新增附录E式E1—E4：体PDE、左右端条件、独立表面ODE、初值、D=0.1及κ=γ=V0=1、常通量层U与两分支表达式。明确v不等于u(1,t)，常通量辅助层不含表面反馈，与式12的动态层不同。表E1列完整12次运行的三种子体/迹指标；0.838按vanilla体中位数除以修正组体中位数，先每种子五时刻最大、再三种子中位数。保留20份表面权重缺失与追加探索性质，仅重聚合已有JSON，未补权重或表面定量证据。 | FULLY_ADDRESSED | [L441](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:441>)；[L629](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:629>)；[L645](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:645>)；[L664](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:664>)；[L673](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:673>)；[L675](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:675>) | ✅ 已核验。附录E的PDE、交换通量、独立v方程、初值、D=0.1及κ=γ=V0=1与problems.py、pinn1d.py和E4_PROTOCOL一致。独立求导得U_y=Δ_y/D·erfc(y/(2√Dt))，U_t=D U_yy，且Δ_y=-1.02；该辅助层不同于式12。直接重聚合12份e4confirm原JSON，四行体/迹中位数、逐种子值和达标数全部匹配表E1；0.004675169889310211/0.005576309573543175=0.8383985551109958。缺失20份表面分支权重、探索性质及不提供可复现v数据均保留。 |
| DR3 | 解释N04、A-1、G2并精确化证据入口 | 附录A直接说明字段并删除N04；§4.3与§4.6首次提及A-1和G2时给中文名称、比较对象及附录F定位。附录F详细列出两者的原门槛、对象和预算，保留联合不满足。E09改指附录E表E1与E4_PROTOCOL具体节，0.838可直接由表后分子/分母核查。 | FULLY_ADDRESSED | [L550](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:550>)；[L335](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:335>)；[L408](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:408>)；[L679](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:679>)；[L681](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:681>)；[L514](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:514>)；[L673](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:673>) | ✅ 已核验。N04已删除。L335首次写跨架构强基线判据A-1并指附录F；L408首次写小预算效果判据G2及其两类对象。L514的E09直接到附录E表E1、协议具体节与原JSON，L673给实际分子/分母及精确记录映射，已不只指目录。 |
| DA-m1 | 补参数轴与E4方程及替换层项 | 表5注补全Gκ与固定量；新增附录E给E4体方程、初值、交换边界、独立v方程及实际U层和硬初值分支。式E3是常通量辅助层，文字明确其不含表面反馈，未称为式12原样推广。§5.2定量结论指向表E1，旧负面结果保留；未新增训练。 | FULLY_ADDRESSED | [L354](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:354>)；[L441](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:441>)；[L629](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:629>)；[L645](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:645>)；[L664](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:664>) | ✅ 已核验。E3轴由源码支持；E4定义、初值、两分支及常通量层在附录E集中补齐。L654明确不含表面反馈，衰减后不强制交换条件或表面ODE；并未将其写成式12原样推广。负面比值保留且由原JSON复得。 |
| DA-m2 | 在表4逐种子披露PirateNet执行来源 | 表4旁逐种子说明：E1两方法seed0/1从历史检查点在本机续完，seed2与E3全部为历史云端结果。同种子来源类别对应，但混合来源的三种子中位数不是统一环境随机重复分布估计。表4全部数值、22.61/5.52及逐种子比较均原样保留；没有删种子或认定已证明不公平配对。 | FULLY_ADDRESSED | [L333](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:333>)；[L322](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:322>) | ✅ 已核验。直接读取12份PirateNet原JSON：E1两方法seed0/1为Python3.12.6、Torch2.14.1+cpu，并保留16000/16500等续跑位置；E1 seed2及E3六条为历史Python3.13.16、Torch2.14.1+cu130。结合SCREEN_PROTOCOL修订4—5的四个历史检查点本机续跑记录，表4逐种子来源披露相符。复得22.6078141960和5.5175385428，所有逐种子表行未变。L333明确混合来源中位数不是统一环境随机重复分布估计，也未推断已证明不公平配对。 |
| DA-m3 | 区分解析连续延拓与截断实现的极限 | 在命题1中明确讨论未截断的解析表达式；§2.3和附录A列精确下界。附录A解释t<1e-30时通过开方变量的时间依赖被固定，外部衰减与背景项仍有导数，不能用该分支的AD极限验证解析迭代极限。原浮点初值误差边界保留，不声称逐位零。 | FULLY_ADDRESSED | [L185](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:185>)；[L173](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:173>)；[L543](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:543>)；[L552](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:552>) | ✅ 已核验。代码t.clamp_min(1e-30)与稿件精确一致。对0≤t<1e-30，层中rt时间依赖被固定，而exp(-t/τ)和f+tN依然含时间，故截断AD极限并非未截断解析命题的证据。L173、185、543、552对此分开说明，浮点初值误差限定保留。 |
| EIC-M1 | 清理内部引用并完整解释既有判据 | 删除N04并直接列字段说明。A-1首次出现处给跨架构强基线名称与附录F入口；G2首次出现处说明主候选对强基线和SOAP内叠加两个目标。附录F列两个方程、种子100/101、4000+500预算、三倍和2/2绝对阈值，明确G2未满足指两方程两项的联合条件，不是四个子判断全失败；完整SOAP对照不追改旧判定。 | FULLY_ADDRESSED | [L550](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:550>)；[L335](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:335>)；[L408](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:408>)；[L679](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:679>)；[L681](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:681>) | ✅ 已核验。附录F与SCREEN_PROTOCOL:82—83、123—126逐项一致：A-1是MLP修正对两档因果及PirateNet硬初值的最佳者；G2固定Adam修正对四基线，另判SOAP叠加，两方程分别要求3倍且两个候选种子≤0.01。种子100/101、4000+500和联合升级条件正确。明确联合未满足不等于四子判断全失败；旧A-1/G2与full_v1文件哈希均未改。 |
| EIC-M2 | 给出Gκ定义并解释k运行标签 | 在§3.1指出κ进入边界函数；表5注给出E1只改c且D=1、R=0、G(u)=0.3u和初值不变，E3为Gκ(u)=κ(u−1)、κ∈{0.1,1,3}，D=0.1、c=0.3、R=u(1−u)和初值不变。明确运行名k就是κ；保留表5全部结果，另给错配公式校验。 | FULLY_ADDRESSED | [L223](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:223>)；[L354](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:354>) | ✅ 已核验。L223与L354以Gκ(u)=κ(u−1)明确算子，κ=0.1/1/3、固定c=0.3，并说明k就是κ；与problems.py:100—106直接匹配。 |
| R3-1 | 使参数轴和时间求值规则可从稿件恢复 | 表5注完整列κ边界函数、三个取值、固定D/c/反应/初值及k标签；§2.3、命题1与附录A给1e-30下界及未截断解析连续延拓的范围。读者可从稿件恢复参数轴和实际求值规则，不需根据δ或文件名猜测。 | FULLY_ADDRESSED | [L354](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:354>)；[L173](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:173>)；[L185](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:185>)；[L543](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:543>)；[L552](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:552>) | ✅ 已核验。E3参数轴和固定量可从表5注直接恢复；精确下界在正文及附录出现。命题1加“未截断解析表达式”，附录说明截断AD和浮点非逐位零，满足两方面的原验收条件。 |
| R3-2 | 让E4比较对象和机制变化可直接核查 | 新增附录E式E1—E4：体PDE、左右端条件、独立表面ODE、初值、D=0.1及κ=γ=V0=1、常通量层U与两分支表达式。明确v不等于u(1,t)，常通量辅助层不含表面反馈，与式12的动态层不同。表E1列完整12次运行的三种子体/迹指标；0.838按vanilla体中位数除以修正组体中位数，先每种子五时刻最大、再三种子中位数。保留20份表面权重缺失与追加探索性质，仅重聚合已有JSON，未补权重或表面定量证据。 | FULLY_ADDRESSED | [L441](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:441>)；[L629](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:629>)；[L645](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:645>)；[L664](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:664>)；[L673](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:673>)；[L675](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:675>) | ✅ 已核验。附录E式E1—E4及表E1完整，明确v与u(1,t)不同；原JSON五时刻最大值再三种子中位数逐格复算匹配。0.838负面比值、筛选失败、追加探索及20份表面权重缺失原边界均保持。 |
| R3-3 | 整理工程过程并给分节配额可核对依据 | §3.4与§4.7缩短具体恢复过程，历史130+24+22来源、原21/后9和四层计时边界集中到附录D。主文保留预算、环境混杂及解释所必需的区别。核验附件给原PAPER_CONFIGURATION的六章基数、逐章实际值、±15%和总11000±10%，并复现审阅中的不同计数口径；没有修改目标、旧报告或用附录补正文配额。 | FULLY_ADDRESSED | [L272](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:272>)；[L410](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:410>)；[L619](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:619>)；[L627](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md:627>) | ✅ 已核验。恢复和历史执行范围集中到附录D，§3.4和§4.7保留影响解释的证据及成本摘要。独立计数复得六章1695/2190/2187/2755/1897/763，合计11487；相对原1800/2200/2000/2500/1700/800各在±15%，相对11000为+4.43%。原配置SHA与保护清单匹配，且与事前git提交46855c4中的配置语义一致。原稿11434、排除表题/注11056、误滤所有表号开头正文10213等口径可独立复现，未用新增附录充数或事后改目标。 |

## Priority 2 — 建议修订

| 编号 | 状态 | 实际处理、独立核验及理由 |
|---|---|---|
| M-建议1 | FULLY_ADDRESSED | 共用附录E已提供短模型、参数、分支和实际层公式；§5.2和E09可定位表E1。与DR2共用核验，未增设实验门槛。 |
| M-建议2 | FULLY_ADDRESSED | 对照全部删除和新增区块，恢复细节确已集中，§4.3及τ段落压缩；直接影响各比较的环境、非置信区间及负面结果限定保留。表数据和图引用均未删，作者说明保留的不同作用充分。 |
| DR-建议1 | FULLY_ADDRESSED | 由problems.py中f(1)=0、f′(1)=f″(1)=-0.2、D=0.1、c=0.3独立代入δ=boundary−bulk，得到(0.02+κ)/0.3+0.02。κ=0.1/1/3对应0.42/3.42/10.0866666667，与表5舍入一致；未推出收益单调性。 |
| EIC-建议1 | FULLY_ADDRESSED | 历史执行长段从附录A移至D，恢复细节在正文压缩而保留完整入口。比较旁环境边界与讨论中的解释范围各有不同作用，未以压缩为由丢弃负面结果或旧证据缺口。 |
| EIC-建议2 | FULLY_ADDRESSED | 附录A新增层函数截断行，与pinn1d.py:58、69准确对应；表后解释理想极限与截断AD差异，无需重复添加科学段落。 |
| R3-建议1 | FULLY_ADDRESSED | L457明确可靠f′(1)、f″(1)和算子参数是输入要求，并将带噪或插值导数的不确定性标为未验证。与δ计算依赖相符，没有新增带噪实验或保证。 |
| R3-建议2 | FULLY_ADDRESSED | L457将主目标量限制到本文体相对误差与独立迹误差，指出边界储存及交换通量需由应用选定。没有将现有排序外推到未计算物理量。 |
| R3-建议3 | PARTIALLY_ADDRESSED | 未另加一个环境总表，作者已说明不重复预算表及混合续跑难以用单标签概括的原因。现有附录A预算表、表4逐种子来源、附录D具名CSV及§5.3混杂边界可定位，未声称等时间收益或固定开销；部分采纳及理由符合原可选验收。 |
| R3-建议4 | NOT_ADDRESSED | 未新增Melenk与Babuška文献。作者理由是与本轮局部披露修订及有限主张关系较弱，扩展相关工作需额外原文核查。该项本为可选；原13条题录逐字不变，没有挪用未读来源作PINN保证，理由可接受。 |
| R3-建议5 | NOT_ADDRESSED | 未新增Oberkampf与Trucano文献。作者以已有代码/数值复算与历史执行范围披露回应概念分层意图，不扩展成验证框架综述；原建议允许不采纳且不要求物理实验。范围在§3.4、§5.1和附录D可确认，理由可接受。 |
| R3-建议6 | NOT_ADDRESSED | 未新增Morris文献。作者说明未来设计尚未展开，维持三档有限灵敏度而不借名称提升结论；§4.5、§5.3—5.4与此一致。该项是可选未来方向，理由可接受，不应为了引用数强制补文献。 |

建议答复率为11/11=100%，超过专用协议要求的80%。NOT_ADDRESSED准确表示未加入三篇可选文献，不能把有理由不采纳改写成已加引用，也不能将可选引用变成新硬门槛。Priority 3未在原清单设项。

## 独立数据与计数证据

直接重聚合E4筛选8份、完整预算12份和PirateNet12份原JSON。每条均核五个规定时刻、有限体/迹序列及所存max字段，结果与作者映射一致；全部来源SHA和原序列已另存[raw32_reaggregation.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/revision1/independent_verification/raw32_reaggregation.json>)。

| 核对量 | 本次独立结果 | 含义 |
|---|---:|---|
| E4筛选：hardic/RBA较好者 ÷ 修正中位数 | 1.385954885516 | 小于3，原失败保持 |
| E4探索：hardic/RBA较好者 ÷ 修正中位数 | 8.798415864995 | 满足原追加探索比较；不回写筛选 |
| E4 vanilla ÷ 修正体中位数 | 0.838398555111 | 表E1分子、分母及方向一致，负面额外收益结论保持 |
| PirateNet E1 hardic ÷ 修正 | 22.607814196013 | 四舍五入22.61；混合执行来源、描述性 |
| PirateNet E3 hardic ÷ 修正 | 5.517538542773 | 四舍五入5.52；三种子描述性 |

E4公式还独立核得：`U_y=(Δ_y/D)erfc(y/(2√(Dt)))`，`U_t=D U_yy=−Δ_y exp(−y²/(4Dt))/√(πDt)`，因而边界常通量为Δ_y。代入初值及参数为−1.02。该辅助问题没有表面反馈，乘衰减后的完整表达式不因此自动满足原交换条件，与稿件限定相符。

计数直接从原稿和修订稿提取六个编号章节，按既有规则排除图题、表格数据、显示公式及附录；包含章/节标题、表题和表注。原配置哈希为`fc04c1df49f7eebda29ab5cb1d993587a2cb2c68283367b68380ce3d532b62aa`，与事前git提交`46855c4b80ab4e7e9620c916b327cde9af9b5191`中配置语义一致。

| 章 | 原目标 | 本次独立计数 | 偏差 | 原±15% |
|---|---:|---:|---:|---|
| 1 引言与相关工作 | 1800 | 1695 | -5.83% | 满足 |
| 2 方程、相容性与修正构造 | 2200 | 2190 | -0.45% | 满足 |
| 3 实验设计与复现方法 | 2000 | 2187 | +9.35% | 满足 |
| 4 数值结果 | 2500 | 2755 | +10.20% | 满足 |
| 5 讨论与局限 | 1700 | 1897 | +11.59% | 满足 |
| 6 结论 | 800 | 763 | -4.63% | 满足 |

合计11487，相对11000为+4.43%，满足原±10%。原稿按同一规则为11434；仅再排除表题/注得到11056，误滤所有“表数字”开头论述并排除章标题得到10213。口径差异已能独立复现，不是稿件内容丢失，也未改变原目标；新增附录未充作正文。逐行分类见[independent_counts.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/revision1/independent_verification/independent_counts.json>)。

## 新增内容100%覆盖与新问题检查

本次对原稿到1a的diff逐区块检查全部新旧文本，覆盖22/22区块、84行新增或替换文本。没有新增参考文献；原13条题录逐字未变，改变的引用上下文链接实际存在。细分覆盖与判断见[new_content_coverage.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/revision1/independent_verification/new_content_coverage.json>)；完整新旧文本见[change_hunks.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/revision1/independent_verification/change_hunks.json>)。

| 区块 | 新稿行 | 核验重点 | 新阻断项 |
|---|---|---|---|
| H1 | 5—5 | 状态改为五份自动审阅意见后的修订初稿，不表示原full_v1合议成功；待核验、未投稿及人类确认均保留。 | 无 |
| H3 | 173—173 | 截断常数、理想解析式与浮点区别；逐行对照pinn1d.py。 | 无 |
| H5 | 185—185 | 命题范围改为未截断解析表达式；没有新增数学保证。 | 无 |
| H7 | 223—223 | 参数轴进入边界函数的位置及新初值范围；对照problems.py。 | 无 |
| H9 | 270—272 | 抽样顺序和分量数对照stage5_support；删除的恢复细节仍在附录D。 | 无 |
| H11 | 322—322 | PirateNet收益叙述压缩，22.61/5.52与六配对结论保留。 | 无 |
| H13 | 333—335 | 逐种子来源直接核12份JSON；A-1名称和附录入口对照原协议。 | 无 |
| H15 | 354—355 | E1/E3固定量与κ公式对照源码并独立算δ。 | 无 |
| H17 | 379—379 | τ说明压缩，跨环境混杂、三种子局限和未搜索均保留。 | 无 |
| H19 | 408—408 | G2比较对象、种子及附录入口对照协议，旧失败未改。 | 无 |
| H21 | 427—427 | 四层成本数字未变；移出的轮询/恢复定义仍在附录D。 | 无 |
| H23 | 441—441 | E4正文入口、比较方向与0.838由原JSON核验，负面范围保留。 | 无 |
| H25 | 457—458 | f导数及目标量条件与实际δ/指标依赖一致，噪声及其他物理量不作已验证主张。 | 无 |
| H27 | 503—503 | 只改引用上下文入口；13条参考文献逐字一致，路径实际存在。 | 无 |
| H29 | 514—514 | E09精确指表E1、E4协议节及原JSON；体/迹与表面缺口区分。 | 无 |
| H31 | 519—519 | E14保留v1数据核查及修订自核入口，并明示不能代替独立审查。 | 无 |
| H33 | 522—522 | E17绑定32份原JSON及源码，独立按文件夹枚举和重聚合核验全部32条。 | 无 |
| H35 | 543—543 | 实现表精确截断行对照两类层函数。 | 无 |
| H37 | 550—552 | N04删除；新增截断AD解释与实际计算图一致，原字段解释未改。 | 无 |
| H39 | 568—568 | 旧历史执行长段改为附录D入口。 | 无 |
| H41 | 621—622 | 附录D新增段与旧稿附录A对应段逐字相同，未重写原日志或表面权重边界。 | 无 |
| H43 | 629—682 | 完整阅读新增54行附录E/F：逐方程/公式对照源码和协议、独立微分U、复算表E1全部数据，逐门槛对照A-1/A-2/G2，探索与历史缺口完整保留。 | 无 |

## 判定理由与保留范围

全部14项必修披露缺口均有明确作者答复、实际修改与独立来源支持；原实验数值、旧失败和证据边界没有因修订被抹除。11项建议均回应，有理由保留文字或不增加可选文献符合原验收弹性。因此本轮普通re-review判为Accept，无遗留必修修订。

仍保留研究自身局限：E4旧表面分支权重缺失；三种子与混合执行环境不支撑统计显著或统一环境分布推断；五个时刻误差不证明全早时间渐近余项结构；A-1/G2失败及E4额外收益负面结果继续有效。这些已经披露的研究边界不被本次文本修订虚构为解决。

本次没有作PDF/HTML视觉裁决，也没有宣称补回历史生产链或表面权重。最终发布前的人类署名、单位、基金、利益冲突及最终核验继续保留待确认。

核验脚本：[verify_revision1.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/revision1/independent_verification/verify_revision1.py>)。脚本仅读取输入并将证据写入本独立核验目录；本报告的逐项质量判断由EIC逐项阅读后给出。

## 交付候选的限定字节桥接

复核后另收到交付候选`delivery_candidate.md`，SHA256为`aef0c10a1bf19e8703a8066e1f0aaef75600b886777424b9f6545677ccc77eb0`。本次独立按原始字节比较：仅第5行将待核验的版本状态句改为中性的“完整中文论文初稿、未投稿、实际审查范围见交付说明、不等同于外部同行评审或录用”；其余所有字节与本报告绑定的1a一致。因此候选稿的科学正文、公式、数据表、图引用、参考文献、附录及全部25项修订内容均与已核验版本相同。

这只是限定的版本对应确认，普通re-review仍绑定原1a；不对正在另行进行的final gate、HTML/PDF或最终交付状态提前背书。报告完成时再次核对原89项输入绑定，全部保持一致。详见[delivery_candidate_bridge.json](delivery_candidate_bridge.json)。

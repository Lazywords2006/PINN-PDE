# R33 作者修订与独立复核路线图

本清单来自五份已完成的原始审稿报告，共 **14个原编号必修项、11个建议追踪项**，映射为7组可共用的修订动作。原冻结契约全轮保持 **ABORT、2/5可用、无编辑裁决**；此文件不承担面板综合功能。详细原因见 [PROTOCOL_EXCEPTION_CN.md](PROTOCOL_EXCEPTION_CN.md)。

所有条目当前均为**待核验**，作者答复和实际修订位置留空；本次未读取新稿，不能据此认定任何问题已关闭。完整原文、逐项来源哈希及机器可读字段见 [REVIEW_ITEMS.json](REVIEW_ITEMS.json)。

## 1. 执行顺序与覆盖

建议先完成定义及可复现细节（A1—A3），再整理判据和来源（A4—A5），随后整理正文及形式核验附件（A6），最后逐条回应可选建议（A7）。共同修改可覆盖多个报告，但答复必须逐个保留原编号。

| 动作组 | 作者工作 | 覆盖编号 |
|---|---|---|
| A1 | 数值实现与解析/浮点边界 | M1、DA-m3、R3-1、EIC-建议2 |
| A2 | 参数轴公式、取值与固定量 | M2、DR1、DA-m1、EIC-M2、R3-1、DR-建议1 |
| A3 | E4科学定义、机制差别与负面结果入口 | DR2、DR3、DA-m1、R3-2、M-建议1 |
| A4 | N04、A-1、G2及内部引用清理 | M3、DR3、EIC-M1 |
| A5 | 表4逐种子来源披露 | DA-m2 |
| A6 | 工程说明集中与形式核验附件 | R3-3、M-建议2、EIC-建议1、R3-建议3 |
| A7 | 可选使用假设、评价目标与文献连接 | R3-建议1、R3-建议2、R3-建议4、R3-建议5、R3-建议6 |

必修是本次作者反馈处理优先级，不是冻结契约的mandatory维度，也不表示Major裁决。原报告中的可选措辞不因重复出现自动变为新实验门槛。

## 2. 逐项必修验收输入

### M1：补全时间截断、残差点随机数及抽样顺序

来源：[方法报告第109行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/method_phase2.md:109>)。拟修位置：§2.3、§3.4、附录A。状态：待核验。

- 明确开方前时间截断为1e−30，并能定位到稳定求值说明。
- 明确独立残差点使用NumPy default_rng(330500)，按体x、体t、左端t、右端t、初值x依次抽样。
- 分别列体8192、左端1024、右端1024、初值1024点，消除两个端点合计1024的歧义。
- 答复定位至已有实现或协议的相应来源；不改采样代码、不重新训练。

### M2：在表5附近定义两条参数轴

来源：[方法报告第110行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/method_phase2.md:110>)。拟修位置：§3.1、§4.4表5及表注。状态：待核验。

- 写明热方程轴仅改变容量c，G(u)=0.3u保持不变。
- 写明反应扩散轴Gκ(u)=κ(u−1)，κ取0.1、1、3，c=0.3且其余设置沿用E3。
- 表中运行标签与κ对应；读者无需由文件名或错配值反推所改算子。

### M3：消除附录A的N04悬空引用

来源：[方法报告第111行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/method_phase2.md:111>)。拟修位置：附录A。状态：待核验。

- 删除N04或替换为有定义、可跳转的具名附录条目。
- 必要的调用及损失字段解释直接列出或精确定位，不以内部编号代替说明。

### DR1：补足参数化边界、取值与固定条件

来源：[领域报告第93行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/domain_phase2.md:93>)。拟修位置：§3.1、表5前文或表注。状态：待核验。

- 明确Gκ(u)=κ(u−1)，κ=0.1、1、3，其他条件沿用E3基准。
- 明确E1容量轴保持G(u)=0.3u。
- 参数和表5已有结果相容；如采纳错配公式校验，另按DR-建议1核验，不把可选写法变为新增硬门槛。

### DR2：为E4负面结果补最小可复核科学定义

来源：[领域报告第94行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/domain_phase2.md:94>)。拟修位置：§5.2、科学附录或明确命名的随稿补充材料。状态：待核验。

- 明列u_t=Du_xx+R(u)、D u_x(1,t)=κ(v−u(1,t))、v′=κ(u(1,t)−v)−γv³，以及左端条件、初值、实际参数，并绑定既有记录来源。
- 区分独立表面变量v与体解迹，给出实际常通量层公式，并说明与式（12）动态边界层的区别。
- 为0.838提供比较对象、分子分母、体误差指标、先取五时刻最大值再取三种子中位数的口径及精确表/行入口。
- 保留表面权重缺失和历史使用范围；不补造表面定量证据、不生成权重补历史缺口、不重训。

### DR3：解释N04、A-1、G2并精确化证据入口

来源：[领域报告第95行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/domain_phase2.md:95>)。拟修位置：附录A、A-1/G2首次出现处、E4证据入口。状态：待核验。

- N04删除或替换成已定义的附录条目/补充表。
- A-1和G2首次使用处给出中文含义及相关段落定位。
- E4入口指向明确科学说明和具体结果行，不能仅指一个目录。

### DA-m1：补参数轴与E4方程及替换层项

来源：[反方报告第105行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/da_phase2.md:105>)。拟修位置：§3.1、表5、§5.2或具名科学补充材料。状态：待核验。

- 写出Gκ(u)=κ(u−1)及其余固定量。
- 给E4方程、初值、边界交换与实际修正表达式定义块；或将该定量比较移入包含定义的补充材料并明确链接。
- 不把不同E4层表述为式（12）原样推广；不要求新增训练。

### DA-m2：在表4逐种子披露PirateNet执行来源

来源：[反方报告第106行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/da_phase2.md:106>)。拟修位置：§3.2、表4表注。状态：待核验。

- 注明E1两方法seed0、1由历史检查点在本机续跑，seed2保留历史云端结果；E3为历史结果。
- 保留逐种子数据及22.61、5.52描述性比值，并说明不是统一环境随机重复的分布估计。
- 不删除种子、不重选中位数，不把混合来源直接改判为已证明的不公平配对。

### DA-m3：区分解析连续延拓与截断实现的极限

来源：[反方报告第107行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/da_phase2.md:107>)。拟修位置：§2.3、命题1、附录A。状态：待核验。

- 实现表给出开方前t.clamp_min(1e-30)。
- 明确命题1对应连续延拓的解析公式，不以截断实现t趋零的自动微分极限核验命题。
- 保留浮点初值误差说明，不宣称t=0逐位精确或截断实现与解析公式有完全相同的导数极限。

### EIC-M1：清理内部引用并完整解释既有判据

来源：[主编角色报告第107行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/eic_phase2.md:107>)。拟修位置：附录A、A-1/G2首次进入正文处、相应结论。状态：待核验。

- 删除悬空N04，直接引出已有调用和损失字段口径。
- A-1、G2各给中文名称、判定对象和正文/随稿补充位置。
- 保留G2失败时，说明其主候选对强基线及SOAP叠加两项判断与适用方程范围；不修改既有阈值或历史判定。

### EIC-M2：给出Gκ定义并解释k运行标签

来源：[主编角色报告第108行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/eic_phase2.md:108>)。拟修位置：§3.1或表5表注。状态：待核验。

- 明确Gκ(u)=κ(u−1)，κ取0.1、1、3，其余参数与原E3相同。
- 明确表中k是κ的运行标记，无需新实验。

### R3-1：使参数轴和时间求值规则可从稿件恢复

来源：[相邻视角报告第109行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/perspective_phase2.md:109>)。拟修位置：表5注、§2.3、附录A。状态：待核验。

- 列Gκ(u)=κ(u−1)、κ∈{0.1,1,3}及其余参数、初值保持不变。
- 列时间截断10⁻³⁰，保留解析连续延拓与浮点实现的区别。
- 读者无需猜标签或错配值即可确定参数轴及实际求值规则。

### R3-2：让E4比较对象和机制变化可直接核查

来源：[相邻视角报告第110行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/perspective_phase2.md:110>)。拟修位置：§5.2、短科学附录。状态：待核验。

- 写体方程、交换通量、独立v(t)方程与初值、实际常通量层表达式。
- 说明其区别于式（12）动态边界层，并列已有体误差三种子表或精确可定位原始记录入口。
- 保留0.838负面结论与表面权重缺失限制，不补造表面证据。

### R3-3：整理工程过程并给分节配额可核对依据

来源：[相邻视角报告第111行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/perspective_phase2.md:111>)。拟修位置：§3.4、§4.7、附录D或具名补充材料、作者答复中的形式核验附件。状态：待核验。

- 恢复细节集中到附录D或一个具名补充入口，主文保留影响比较解释的环境、预算、成本口径。
- 提供原先六节目标基数及其既有配置来源、统一计数口径、实际逐节数值与±15%核对；总量按已有11000±10%核对。
- 不以事后修改目标基数或混用计数口径得到通过；若既有基数仍不能取得，明确标为无法核验而非假填合格。
- 正文沿问题、构造、比较和限制组织；配额表、脚本及计数证据可放作者答复或随稿核验附件，不要求进入科研正文。

补充说明：EIC报告称查到PAPER_CONFIGURATION并核验通过，其他报告记录未见分节基数；本清单未读取该配置或新稿，不替任何一方预设最终计数。此处要求可复核证据，而不是新增科学内容。

## 3. 建议项及允许的证据答复

以下原报告未编号的建议使用本清单追踪编号；不表示新增问题。均允许“采纳、部分采纳、不采纳”的具体答复。未采纳须说明理由与证据；回应率不等于采纳率。为避免遗漏，作者应对11项全部回应；re-review的P2原规则是至少80%有回应，即本清单至少9/11。涉及正文篇幅的改进可以由科学附录或核验附件承载，不强迫将管理流程写入科研论述。

### M-建议1：给E4负面结果最短方程与配置入口

来源：[方法报告第112行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/method_phase2.md:112>)。

- 若采纳，可共用DR2、DA-m1、R3-2的定义块和精确配置入口。
- 答复说明共用位置；该建议本身不额外增加实验或通过门槛。

### M-建议2：合并重复的工程与解释边界

来源：[方法报告第112行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/method_phase2.md:112>)。

- 保留首次及直接影响主张解释处的限定，减少重复叙述。
- 如不压缩，说明具体保留理由；不能为缩字删去负面结果、非置信区间含义或混杂边界。

### DR-建议1：用错配公式核对参数轴数值

来源：[领域报告第93行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/domain_phase2.md:93>)。

- 若采纳，列δ=(0.02+κ)/0.3+0.02，并与0.42、3.42、10.086667相互校验。
- 可在作者核验附件给计算并在答复定位；不把该可选呈现方式升为正文必需公式。

### EIC-建议1：集中重复的工程来源说明

来源：[主编角色报告第110行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/eic_phase2.md:110>)。

- 适度合并重复记录，保留一个完整可定位补充入口。
- 若保留多处说明，指出各处对科学解释的不同作用；不得据此制造新的失败条件。

### EIC-建议2：在附录A列时间截断常数

来源：[主编角色报告第110行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/eic_phase2.md:110>)。

- 列1e−30并能对应现有求值实现。
- 可通过M1、DA-m3、R3-1的共用修改答复，无需重复加段。

### R3-建议1：说明可靠初值导数与边界参数的输入条件

来源：[相邻视角报告第117行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/perspective_phase2.md:117>)。

- 若采纳，指出构造需可靠获得f′(1)、f″(1)及边界算子参数。
- 说明本研究解析初值满足条件，带噪观测/离散插值导数不确定性尚未验证；不增设带噪实验。

### R3-建议2：说明按使用目的选择误差目标量

来源：[相邻视角报告第119行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/perspective_phase2.md:119>)。

- 若采纳，说明体相对误差为本研究主目标量，而非所有物理目标上的唯一标准。
- 可提示边界储存、交换通量或组合误差需按应用确定；不把现有体误差排名扩张为其他目标量排名。

### R3-建议3：把资源披露整理为紧凑环境和预算表

来源：[相邻视角报告第121行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/perspective_phase2.md:121>)。

- 若采纳，环境、预算和成本定义集中可读且来源可定位。
- 不据现有记录声称等时间收益或固定额外开销；未采纳可用已有披露位置与保持文字呈现的理由答复。

### R3-建议4：可选连接解析富集与单位分解有限元

来源：[相邻视角报告第127行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/perspective_phase2.md:127>)。

- 如加入Melenk与Babuška（1996），核对原文并仅用于已知局部结构纳入近似空间的概念桥接。
- 不把其逼近或稳定性理论转成PINN训练保证；不采纳可说明与主线或篇幅的关系。

### R3-建议5：可选用计算核验框架组织证据层次

来源：[相邻视角报告第128行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/perspective_phase2.md:128>)。

- 如加入Oberkampf与Trucano（2002），核对原文并区分代码核验、数值解核验与模型验证。
- 引用不增加物理实验要求；不采纳可说明现有证据分层已如何满足原意。

### R3-建议6：可选引用后续参数研究设计视角

来源：[相邻视角报告第129行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/perspective_phase2.md:129>)。

- 如加入Morris（1991），核对原文并限定为未来控制因素与随机变化的实验设计参考。
- 不能把当前三档跨环境数据认定为Morris敏感性分析；不采纳可说明与当前有限主张的距离。

## 4. 分节字数与过程记录的处理

R3-3要求的是可核验的原配额与计数依据。EIC原报告称已读取PAPER_CONFIGURATION并完成核对，其他报告记录所见输入未给六节基数；本清单未读取该配置或任何新稿，不把两种输入可得性结论强行合成“已通过”。各报告的独立计数口径也不同：方法10213、领域及DA约10243、EIC11056、相邻视角10833。它们均不是本次整理者执行的新计数。

作者应在答复或随稿核验附件提供既有配置的准确定位、六节目标基数、统一计数规则和实际数值；后续复核者核验来源是否事前存在，并按原总量11000±10%、分节±15%判断。正文只保留对科学解释必要的环境、预算与成本说明。配额表、计数脚本、runner恢复与会话细节均可集中放附件；不得事后修改配额或把未取到基数记成合格。

## 5. 已有边界与未来研究，不增列本轮补实验

- **更早时间参考解与角点机制**：原报告列为未来强化主张的研究，不是当前必修实验。保留最早观测时刻及五时刻指标的限制。 来源：[method_phase2.md L112](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/method_phase2.md:112>), [domain_phase2.md L97](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/domain_phase2.md:97>), [da_phase2.md L114](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/da_phase2.md:114>), [eic_phase2.md L110](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/eic_phase2.md:110>)。
- **更多独立种子、问题代表性及稳健性**：原报告不要求为了有限描述性结论添加新种子、显著性或事后功效。若未来强化总体保证，需另行设计。 来源：[method_phase2.md L114](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/method_phase2.md:114>), [domain_phase2.md L97](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/domain_phase2.md:97>), [da_phase2.md L115](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/da_phase2.md:115>), [eic_phase2.md L110](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/eic_phase2.md:110>)。
- **同环境τ、优化器及成本比较**：保留混杂与非等时间收益边界；同环境对照是未来更强因果/效率主张的设计，不作为本轮重训任务。 来源：[method_phase2.md L112](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/method_phase2.md:112>), [domain_phase2.md L97](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/domain_phase2.md:97>), [da_phase2.md L99](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/da_phase2.md:99>), [eic_phase2.md L110](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/eic_phase2.md:110>), [perspective_phase2.md L121](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/perspective_phase2.md:121>)。
- **替代解释与机制识别**：角点结构、一般固定偏置和目标平移之间尚未识别；现有报告未证明替代解释胜出。未来可设计解析层、平滑替代项和幅度/符号控制，本轮不新增训练。 来源：[da_phase2.md L89](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/da_phase2.md:89>), [da_phase2.md L113](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/da_phase2.md:113>), [domain_phase2.md L97](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/domain_phase2.md:97>)。
- **既有负面结果与证据边界**：保留不利种子、弱交换退化、A-1/G2未满足、E4无额外收益、表面权重缺失、来源混杂；不将当前有限主张扩为外部评审通过或全历史独立重现。 来源：[method_phase2.md L98](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/method_phase2.md:98>), [domain_phase2.md L94](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/domain_phase2.md:94>), [da_phase2.md L119](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/da_phase2.md:119>), [eic_phase2.md L100](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/eic_phase2.md:100>), [perspective_phase2.md L99](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/perspective_phase2.md:99>)。

五份报告的正面观察已在机器清单中单列保留，主要涉及局部解析性质与经验用途的区分、有限数字核对、真实种子与反例展示。这些肯定无需新增修订条目，也不等于本次整理者重新训练、重放模型或核验全部历史产物。

## 6. 后续独立复核的输入与逐项记录

作者完成修订后提供修订稿、随稿补充材料及逐条答复，答复必须覆盖14个原编号和11个建议追踪编号。每个编号填：具体做了什么、确切文件/章节/公式/表/行、证据来源、未采纳部分及理由。只写“已按建议修改”不能核验。

复核者须亲自进入所述位置，逐项判断为FULLY_ADDRESSED、PARTIALLY_ADDRESSED、NOT_ADDRESSED或MADE_WORSE；缺少明确答复或定位时另标“无法核验”。同一修订可以复用证据，但不能用“同上”跳过某个编号的原始验收条件。建议未采纳但理由充分时应如实记录，不为凑采纳率迫使加入无关正文。

本路线图不作修订后编辑判断。按re-review原规则，全部P1须经实际独立核验为FULLY_ADDRESSED，才具备该模式下进一步考虑接受的必要条件；单纯作者声称已处理不满足该要求。后续只将真实修订新引入的问题另列证据，不借复核追加与原意见无关的实验门槛。即使新的独立核验得到结论，也必须保持原full_v1全轮ABORT与无裁决事实。

# 七篇相关论文的写法分析与 R33 定位

日期：2026-10-22，UTC+8。问题：**一篇围绕特定困难改进 PINN 的论文，怎样界定贡献、设计比较和组织论证？** 本轮不启动训练，不改旧预注册门槛。

## 一、先纠正 R33 的判断尺度

把“通过所有强基线三倍判据”与“论文能否成立”绑定得过紧，需要纠正。前者是 R33 自设的实验投入门槛；后者应看**明确的问题、可辨认的增量、支撑该增量的比较、可复核证据和适用边界**。本轮选读展示了数种可行论证路线，不能据此推出任何稿件必然录用。

R33 可以围绕“动态边界与初值的时间导数错配，使普通硬初值构造在被测问题上拟合困难；经典角点层修正带来可复核改善”组织论文。它不必承担一般 PDE 求解器排名的任务。A-1/G2 失败仍按原协议报告，但不能独自否定这个更窄的贡献。

## 二、选了哪些论文、读到什么程度

这是**目的性叙述选读**，不是系统综述或新颖性穷尽检索。来源包括 OpenAlex、SciSpace 的发现检索，arXiv/期刊原文，以及 Crossref 书目信息核对。以“同类方程、解析修正、硬约束、模块化改进、机制诊断”为纳入理由；综述、只有二手摘要和与论点无关的论文不计入七篇。阅读的是下列版本的引言、相关方法、关键实验/图表及结论，未声称逐页核完所有证明和附录。

| 编号 | 正式论文与发表信息 | 本轮阅读版本/定位 |
|---|---|---|
| P1 | Muhammad Awais，*Physics-informed neural networks for the heat equation with dynamic (Wentzell) boundary conditions*，Open Journal of Mathematical Sciences **10**，526–536，2026。[DOI](https://doi.org/10.30538/oms2026.0303) | [出版社全文](https://pisrt.org/psrpress/j/oms/2026/physics-informed-neural-networks-for-the-heat-equation-with-dynamic-wentzell-boundary-conditions.pdf)，§1、§3–4、§7–9，表 1–4 |
| P2 | Gie、Hong、Jung、Munkhjin，*Semi-analytic PINN methods for boundary layer problems in a rectangular domain*，JCAM **450**，115989，2024。[DOI](https://doi.org/10.1016/j.cam.2024.115989) | [arXiv 2312.06278v1](https://arxiv.org/html/2312.06278v1)，§1–4，表 1–2、图 3.1–3.6；预印本作者列表与正式版本有差异，书目按正式版本，不冒称逐页核过最终版 |
| P3 | Gie、Hong、Jung、Lee，*Singular layer physics-informed neural network method for convection-dominated boundary layer problems in two dimensions*，JCAM **474**，116918，2026。[DOI](https://doi.org/10.1016/j.cam.2025.116918) | [arXiv 2312.03295v2](https://arxiv.org/html/2312.03295v2)，§1–5，表 1、图 4.3–4.4；正式版信息另核出版社 |
| P4 | Sukumar、Srivastava，*Exact imposition of boundary conditions with distance functions in physics-informed deep neural networks*，CMAME **389**，114333，2022。[DOI](https://doi.org/10.1016/j.cma.2021.114333) | [arXiv 2104.08426v2](https://arxiv.org/pdf/2104.08426v2)，§1、约束构造相关节、§9–12，图 16–17；此为标注待刊的作者稿 |
| P5 | Anagnostopoulos、Toscano、Stergiopulos、Karniadakis，*Residual-based attention in physics-informed neural networks*，CMAME **421**，116805，2024。[DOI](https://doi.org/10.1016/j.cma.2024.116805) | [arXiv 2307.00379v2](https://arxiv.org/pdf/2307.00379v2)，§1–4，表 1–6、附录成本表；2026 年更新稿首页注明已与发表版本对齐 |
| P6 | Wang、Sankaran、Perdikaris，*Respecting causality for training physics-informed neural networks*，CMAME **421**，116813，2024。[DOI](https://doi.org/10.1016/j.cma.2024.116813) | [arXiv 2203.07404v1](https://arxiv.org/html/2203.07404v1)，§1–6，表 1、附录超参数/成本；预印本标题包含“is all you need”，正式标题不同。OSTI 托管文件也是该预印本，不当作最终排版版 |
| P7 | Li、Yu、Wang，*Energy Dissipation Rate Guided Adaptive Sampling for Physics-Informed Neural Networks: Resolving Surface-Bulk Dynamics in Allen-Cahn Systems*，IJNAM **23**(4)，576–604，2026。[DOI](https://doi.org/10.4208/ijnam2026-1025) | [期刊最终全文](https://www.math.ualberta.ca/ijnam/Volume-23-2026/No-4-26/2026-04-06.pdf)，§1–4，表 1–3、采样概率比较及附录 |

JCAM = Journal of Computational and Applied Mathematics；CMAME = Computer Methods in Applied Mechanics and Engineering；IJNAM = International Journal of Numerical Analysis and Modeling。七篇的期刊、年份、卷页和 DOI 均有正式记录；版本差异按上表保留。P1 的 PDF 与 Crossref 具体出版日不一致，此处只用一致的年份，不替它们裁定日日期。书目及本地全文 SHA256 见 `validation/literature_writing_20261022/`。

## 三、逐篇看：它们怎样把论文写成立

### P1：Wentzell 热方程——把贡献写成验证基准

**原文写法。** 引言先指出两类验证漏洞：算例可能把边界通量项意外消掉；小体残差可能掩盖边界错误。随后用一个退化测试和一个通量真正激活的测试回应。实验给五个随机特征种子、独立误差/边界残差、有限差分核对及针对性消融。讨论明确限定为光滑一维人造解的验证工作，也说明输入缩放并非该例必要条件，没有把所有组件包装成必要改进。定位见 §1、§7.3、§8–9。[原文](https://pisrt.org/psrpress/j/oms/2026/physics-informed-neural-networks-for-the-heat-equation-with-dynamic-wentzell-boundary-conditions.pdf)

**R33 可学。** 明确每个算例要验证什么：E1 做机制清晰的主例，E3 检验非线性下是否有同类增益，E4 划出通量错配的适用边界。主张可以很具体，但每个检验必须真实触发所声称的困难。该文是验证基准路线，不能仅凭其发表就认定 R33 的方法新颖性已经足够。

### P2：矩形域 SL-PINN——分析先于算法，算例围绕层的类型展开

**原文写法。** 先讲奇异摄动产生的薄层，再做边界层分解，得到 corrector，最后把它嵌进网络或联合训练。数值节按非特征/特征边界、相容/不相容数据组织，并给参数与配点变化。结论回到矩形域对流主导问题中的稳定近似。理论分析的是连续问题的层结构；不能转读为所有 PINN 训练误差的下界。定位见 §2–4。[原文](https://arxiv.org/html/2312.06278v1)

**R33 可学。** 按“错配 δ → 半直线局部模型 → 层函数 w → 保持初值的网络构造 → 数值验证”写。经典分析是构造依据，贡献落到动态边界的具体适配和可核验效果，不需要把经典工具重新命名为全新原理。

### P3：多几何 SL-PINN——用同一机制的不同变体组织推广

**原文写法。** 章节按通道、圆域和椭圆域展开，每一部分连接层分析与数值测试。表 1 明确比较标准五层 PINN、采用 L²/L¹ 训练的 SL-PINN，并列不同扩散参数和问题类型。L¹ 并非表中所有情形都最好；结论仍围绕所研究的对流主导边界层问题。定位见 §2–5、表 1。[原文](https://arxiv.org/html/2312.03295v2)

**R33 可学。** 实验不用机械凑很多互不相关 PDE。E1/E3 和参数轴可以围绕同一时间错配机制展开；哪些配置收益小、哪类错配失效，也是结果结构的一部分。该文多几何证据支撑它自己的范围，不等于一维论文一律必须补二维。

### P4：距离函数硬约束——明确承认经典来源，证明构造性质

**原文写法。** 引言列出贡献时交代 Kantorovich、R-functions 等经典来源，把增量放在几何感知神经试函数及约束适配。先说明约束为何满足，再用标准 PINN/不同距离构造检验解误差。图 16–17 还展示两种方法随网络、点数和训练增加都能变好；结论强调低训练损失与高解精度不是同一件事。定位见 §1、§9.1.1、§10–12。[作者稿](https://arxiv.org/pdf/2104.08426v2)

**R33 可学。** 可以清楚地写“基于经典角点层分析的修正”，然后证明初值保持、解释剩余 PDE/边界残差。承认来源不取消具体适配的研究价值。把“结构保证”和“实验观察”分开，避免从几组训练结果推导不可消除的误差下限。

### P5：RBA——把模块本身和模块组合分开交代

**原文写法。** 引言比较已有权重方法的额外训练/梯度开销，导出残差移动平均的简单模块。实验既比较 plain RBA、plain SA、vanilla，也报告叠加 Fourier、modified MLP、硬边界等组件后的结果，并用逐项消融与成本表拆贡献。主比较给五种子；部分消融用最好种子，不能把两者当作相同证据层级。定位见 §3.1–3.4、表 1–6、附录。[与发表版对齐的作者稿](https://arxiv.org/pdf/2307.00379v2)

**R33 可学。** 两条主线都能写：同一 MLP 中 hardic 与 hardic+layer 的增益；同一 PirateNet 中加/不加校正的增益。MLP+校正不需要先胜过所有其他架构，才能研究一个可组合组件。保留 R33 的全部种子，不照搬最好种子消融的选法。

### P6：因果训练——先把失败现象讲清楚，再给最小修改

**原文写法。** 先用 Allen–Cahn 显示普通训练的时间误差/残差问题，再用 NTK 解释训练偏置，导出时间权重与停止准则，最后扩展到混沌系统。表 1 同列普通 MLP 和 modified MLP 的因果训练结果，展示结构与训练策略的组合；讨论也承认前向 PINN 求解比传统求解器耗时。定位见 §2–6、表 1。[预印本](https://arxiv.org/html/2203.07404v1)；[正式发表记录](https://www.sciencedirect.com/science/article/pii/S0045782524000690)。

**R33 可学。** 引言后的第一张关键图应帮助读者理解硬初值为何仍有困难，然后才展示校正收益。R33 的局部分析可解释设计动机，但当前五个评价时刻不能独自证明 t→0 的误差传播因果链；早期机制证据须可靠核验后再加入。

### P7：EDRAS——算法改进与领域物理问题共同支撑贡献

**原文写法。** 先从热力学结构导出采样指标，再比较 EDRAS、RAR 及组合；另用 RAR/RAD/EDRAS 的概率分析解释采样差异。随后讨论二维静态/动态边界对体相演化的影响。表 3 如实呈现采样密度阈值与误差的非单调关系。表 1 的一维误差属于周期边界，不能挪给二维动态边界。定位见 §2–4、表 1–3、附录。[最终版](https://www.math.ualberta.ca/ijnam/Volume-23-2026/No-4-26/2026-04-06.pdf)

**R33 可学。** 除误差下降，还可讨论不同错配机制的作用边界；E4 的负面比较能回答“这类首阶校正什么时候不够”。但 R33 没有直接复现 EDRAS，多网络分段推进不能与当前 `ic1000` 启发式混同。旧笔记“只有 RAR 基线”不概括本次核对的最终版。

## 四、综合：可借鉴的是论证结构

| 写作环节 | 七篇提供的可借鉴路径 | R33 的对应安排 |
|---|---|---|
| 题目/摘要 | 指明问题类、困难和方法；贡献可以是具体适配、模块或验证基准 | 写一维动态边界抛物问题和时间错配修正，避免一般 PDE 优势 |
| 引言 | 从可展示的困难收束到一个可回答问题 | 硬初值保持函数值，但不能自动处理初始时间导数错配 |
| 方法 | 经典工具的来源、采用它的原因、构造实际保证什么 | δ、半直线层推导、初值保持；剩余误差仍由训练处理 |
| 主实验 | 比较对象服务于主张，而非单纯扩张方法名单 | vanilla/hardic/RBA；同架构加/不加校正是核心；现代基线用于评估范围与组合 |
| 消融/图表 | 把模块增益、组合增益、机制诊断和成本分开 | 现有 confirm、参数轴、E3 PirateNet；小预算只作可行性证据 |
| 讨论 | 成功范围、无效组件、未覆盖问题都写清 | E2 未入选、弱错配收益有限、E4 未优于 vanilla、E1 叠加缺种子 |

由此得到的判断是：**R33 需要支撑一条明确、有限的贡献链，不需要把原 A-1 变成所有论文成立的前提。** 同时，选读到的论文发表只是写作和证据组织的实例；它们使用某种较窄比较，不等于 R33 可以削弱比较公平性，也不构成统一录用标准。

## 五、把 R33 改成怎样的一篇论文

建议题目：**《一维动态边界抛物问题的初始相容性分析与 PINN 角点层修正》**。它明确研究范围，也容纳改进与负面结果。

建议只突出三项贡献：

1. 从体方程与动态边界的初始时间导数要求出发，解释被测硬初值 PINN 的困难，并给出可检查的 δ。
2. 基于经典半直线热方程层分析构造修正，说明初值保持及其适用条件；具体组合由本项目完成，不把解析富集思想称首次。
3. 在明确的一维配置、训练预算和指定时刻上，报告对普通 PINN/硬初值/RBA 的改善、E3 的架构内叠加收益，以及参数轴/E4 揭示的边界。

现有完整预算中，E1/E3 对 vanilla 的中位数改善约 45.47/81.60 倍，对 hardic/RBA 最好者约 30.06/5.92 倍；这些是实质性局部效果证据。E3 PirateNet 架构内叠加约 5.52 倍，可作独立的模块证据。它们足以支持**开始组织这条窄主张的论文初稿**，不必先跑完 42 或 322 次；也不自动等于现稿已可投。

正文建议：问题与错配 → 修正推导 → 固定配置的公平比较 → 逐种子和参数轴 → 架构内叠加 → 失败例及局限。主表保留默认对默认；若以后调参，按用户既定规则另表。两个新小预算 tag 仍只作投入判断，不混入正式主表。

补证据按论点选择：若正文主张两个方程上均可叠加，就需补 E1 四个 checkpoint；若只主张 E3 的已测叠加效果，就明确范围。τ 灵敏度和独立初值是比无目的扩张架构名单更直接的补强，具体预算另行预注册。若强调 t→0 机制，先解决对应时刻参考解收敛；若不作该强机制主张，删去越界因果句即可。E4 缺失的旧表面权重仍不能冒充恢复。

## 六、引用与本轮限制

本轮未训练、未追加调参、未改旧数据或 G2 停止规则。论文定位与试验升级判据分开处理。来源链接、实际阅读版本、书目核验及检索范围记录在 `validation/literature_writing_20261022/`；原文图表未复制，以上均为概括与明确标出的 R33 写作建议。没有完成全领域新颖性核查，也没有借他人的发表结果保证 R33 录用。

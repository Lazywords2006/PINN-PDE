# R32 文献新颖性检查：层校正项（想法 A）与指数衰减输出变换（想法 B）（2026-10-16）

只做文献检索，没有跑任何实验。**一次有限检索不能证明新颖性**，只能说明“在这些检索词下没找到”。检索方式、能读到什么、读不到什么，见第 1 节。

## 结论

| 想法 | 判定 | 依据 |
|---|---|---|
| **A**：把 erfc 型初始/角点层剖面做成带可学习幅值的显式校正项嵌入 PINN | **设计模式已有先例；针对“初-边值不相容的时间角点层”未检出先例** | “解析层剖面 + 网络光滑余项”这一结构已被 Gie–Hong–Jung 的 sl-PINN 系列、Hu–Jin–Zhou 的 SEPINN 采用，但都是定常问题（空间边界层或椭圆角点奇异），剖面是 e^{−x/ε} 型而非 erfc 型。时间相关的校正项嵌入只见到 Burgers 移动内层。没有找到任何 PINN 文献处理 t=0 处初值与边界条件不相容（Dirichlet/Robin/Neumann 热方程，或 Wentzell 动态边界）。 |
| **B**：u = exp(−λt)·N(x,t)，λ 取自最低特征值 | **部分已做** | 用已知的时间包络对解做时间相关归一化以保持相对精度，Zong–He–Tartakovsky（CMAME 2023）已做，包络是幂律 t^{−d/2}，不是指数。取最低特征值为指数的 e^{−λ₁t} 未检出已发表先例，但它是这一做法加硬约束输出变换（Lagaris 型）的特例，单独作贡献的空间很小。 |

另外三点：

1. **动态（Wentzell）边界的 PINN 文献很少，且都不讨论初-边值相容性。** 见到的有 2026 年一维热方程基准（Awais）、Cahn–Hilliard 动态边界的 MCL-PINN、Allen–Cahn 表面-体动力学的 EDRAS（arXiv 2507.09757）。
2. **没有找到量化“初边不相容 → t→0 边界处误差”的 PINN 论文。** 只有综述一般性提到相邻边/角点的冲突边界条件难学，以及大量数值分析文献（Flyer–Fornberg、Chen–Qin–Temam 等）。R32 已有的诊断（误差起于边界、随错配增大、相容初值可到 1e-4）本身可能比校正项更有新意，但这一点同样只是“没找到”。
3. 想法 A 的最近邻是“经典角点校正函数（数值分析）+ semi-analytic PINN（嵌入方式）”的组合。审稿人可能把它看作两者的移植，需要诊断部分和定量提升来撑。

## 1. 检索范围与局限

- **检索词**（中英）：singular layer PINN、semi-analytic PINN、corrector enrichment、compatibility condition、corner singularity PINN、initial layer neural network、incompatible initial boundary data、dynamic boundary condition PINN、Wentzell / Ventcel neural network、bulk-surface PINN、similarity variable / erfc PINN、exponential scaling / decaying solution PINN、hard-constraint time factor、integrating factor PINN、物理信息神经网络 抛物 初边值不相容 初始层。
- **来源**：网络搜索加 arXiv、出版社页面抓取，没有直接用 Google Scholar。ScienceDirect 页面（Gracia–O'Riordan 两篇、Zong 的期刊页）返回 403，只能读检索摘要，书目信息用 Crossref 补。检索工具附带的概述性文字有一部分是模型自己的推断，下面只采用了能在页面上对上的内容。
- **核实等级**：【全文】读了正文相关章节；【摘要页】只读 arXiv/出版社摘要页；【检索摘要】只见检索结果中的摘要，未打开原文；【记忆】凭记忆给出的经典文献，没有重新核对。
- **没做**：CNKI/万方等中文库只用一条中文检索；没有检索动态边界条件抛物问题相容性条件的 PDE 理论文献；没有逐篇追引用链；没有查 Carslaw–Jaeger 型半直线动态边界解。

## 2. 想法 A：显式层校正项

### 2.1 直接与最近先例

**(a) 同一设计模式：解析层剖面嵌入 PINN（定常）**

| 文献 | 内容 | 与 A 的接近程度 |
|---|---|---|
| Gie, Hong, Jung. *Semi-analytic PINN methods for singularly perturbed boundary value problems*. Applicable Analysis 103(14):2554–2571 (2024)；[arXiv 2208.09145](https://arxiv.org/abs/2208.09145)【全文】 | 一维定常 BVP（第 2.1 节对流扩散、2.2 节反应扩散、3.1 节非线性、3.2 节 Burgers）。校正项 φ = −u⁰(0)e^{−x/ε}（式 2.5），反应扩散为 e^{−x/√ε}（式 2.14）。网络输出 ũ = (x−1)(û(x) − û(0)e^{−x/ε})（式 2.7），即**形状固定的显式校正项，幅值取自网络自己的边界值 û(0)**，没有另设可学习系数；Burgers 见式 3.19。 | **最近的设计模式。** “幅值可学习”在这里是隐式的（由网络边界值给出）。问题类型不同：定常、指数剖面、空间边界层。 |
| Chang, Gie, Hong, Jung. *Singular layer PINN method for plane parallel flows*. Comput. Math. Appl. 166:91–105 (2024)；[arXiv 2311.15304](https://arxiv.org/abs/2311.15304)【全文，读至约 93%】 | 定常 Navier–Stokes 平行流（式 1.2）。给出“显式”（式 3.3–3.5，幅值取网络边界值）与“隐式”（式 3.7–3.9，另设可训练的 φ̂，参数 θ_{2,s,L}、θ_{2,s,R}）两种嵌入。无时间变量，未讨论初始层。 | 给出“显式 vs 可学习”的现成对照模板。定常。 |
| Gie, Hong, Jung, Munkhjin. *Semi-analytic PINN methods for boundary layer problems in a rectangular domain*；[arXiv 2312.06278](https://arxiv.org/abs/2312.06278)（J. Comput. Appl. Math.，卷期未核）【检索摘要】 | 二维矩形域，非特征与特征边界，边界层分析后修改 PINN。 | 含矩形域，但椭圆型；角点处的层未见时间方向的讨论。 |
| Gie, Hong, Jung, Lee. *Singular layer PINN method for convection-dominated boundary layer problems in two dimensions*；[arXiv 2312.03295](https://arxiv.org/abs/2312.03295)【摘要页】。Jung, Kim, Ngon. *Singular layer PINN methods for steep reaction–diffusion equations in a smooth convex domain*, Eng. Anal. Bound. Elem. (2025)【检索摘要】 | 二维定常奇异摄动问题。 | 同一家族，定常。 |
| Hu, Jin, Zhou. *Solving Poisson problems in polygonal domains with singularity enriched PINNs*. SIAM J. Sci. Comput. 46(4):C369–C398 (2024)；[arXiv 2308.16429](https://arxiv.org/abs/2308.16429)【摘要页】 | Poisson 方程多边形角点/混合边界/边奇异：把已知奇异函数显式放进 ansatz，并给出收敛分析。 | **“角点奇异 + 解析奇异函数嵌入”的最近先例**，但是椭圆问题的空间角点。奇异函数系数是否可学习，该页未说明。 |

**(b) 时间相关问题上的“校正项/渐近展开 + 网络”**

| 文献 | 内容 | 接近程度 |
|---|---|---|
| Chang, Gie, Hong, Jung. *Singular layer PINN methods for Burgers' equation*；[arXiv 2410.09723](https://arxiv.org/abs/2410.09723)【摘要页】 | 一维 Burgers，小粘性，校正项嵌入，覆盖定常与**移动内层**。 | 最近的“时间相关 + 校正项嵌入”。但是内层，摘要未提初始层或初-边相容性。 |
| Zhu, Chaikovskii, Jin, Zhang. *Deep asymptotic expansion method for singularly perturbed time-dependent reaction-advection-diffusion equations*；[arXiv 2505.23002](https://arxiv.org/abs/2505.23002)【摘要页】 | 移动内部过渡层；用网络逼近展开的光滑部分，层方程另用 PINN 求解。 | 时间相关，但不是解析校正项嵌入，也不是初始层。 |
| Cao, Gao, Yuan, Liu. *Multistep asymptotic pre-training strategy based on PINNs for solving steep boundary singular perturbation problems*. CMAME 431:117222 (2024)【检索摘要】 | 奇异摄动抛物问题，时空陡梯度；在时间和摄动参数两个方向做渐近预训练，摘要称改善对初值的学习。 | 针对抛物问题的陡变，但靠训练策略，不是解析校正项。 |

**(c) 动态（Wentzell）边界条件的 PINN**

| 文献 | 内容 | 接近程度 |
|---|---|---|
| Awais. *Physics-informed neural networks for the heat equation with dynamic (Wentzell) boundary conditions*. Open J. Math. Sci. 10(1):526–536 (2026)；[doi 10.30538/oms2026.0303](https://doi.org/10.30538/oms2026.0303)【摘要页，读了方法描述】 | 一维 (0,1)×(0,0.5]，两端动态边界 u_t + ku ± βu_x = g，k=π²，β=1。求解器是**随机特征最小二乘**（只解输出权重，250 个特征），**硬初值** u = u₀(x) + t·Σ c_m φ_m。两个构造解；基准 A 取 k = απ² 使边界强迫齐次。相对 L² 约 8.65e-6（A）和 9.45e-8（B）。**未讨论角点相容性**，作者说明这是验证基准，不主张方法更优。 | 问题类型最近（动态边界热方程），但数据相容、一维、非梯度训练 PINN。它的硬初值形式 u₀ + t·N 是想法 A 论文里应当比较的基线。相容数据下误差很低，与 R32“相容初值可达约 1e-4”不矛盾，但两者方法与几何不同，不能当作独立佐证。 |
| Chen, Zhang, Zhang, Luo. *A phase-field neural solver for moving contact line problems with dynamic boundary conditions* (MCL-PINN)；[arXiv 2607.19690](https://arxiv.org/abs/2607.19690)（2026-07）【摘要页】 | Cahn–Hilliard + 动态边界；多网络时间步进、自适应损失权重与采样；自称首个此类 PINN。 | 摘要未提相容性、校正项或时间衰减缩放。 |
| Li, Yu, Wang. *Energy dissipation rate guided adaptive sampling for PINNs: resolving surface-bulk dynamics in Allen–Cahn systems*；[arXiv 2507.09757](https://arxiv.org/abs/2507.09757)【摘要页】 | 圆盘、椭圆上的静态与动态边界 Allen–Cahn，自适应采样。检索工具称已刊于 IJNAM 2026，未核实。 | 摘要未说明动态边界如何施加，也未提相容性。 |
| Martínez-Esteban 等 *PINNs with dynamical boundary constraints*（Commun. Nonlinear Sci. Numer. Simul.）【检索摘要】 | 名字相近，但是一种按先前训练约束损失的训练算法，不是动态边界条件。 | **注意区分，不是先例。** |

**(d) 数值分析里的祖先：角点校正函数**

| 文献 | 内容 |
|---|---|
| Flyer, Fornberg. *Accurate numerical resolution of transients in initial-boundary value problems for the heat equation*. J. Comput. Phys. 184(2):526–539 (2003)【检索摘要】 | 初边数据不满足无穷多个相容条件时，t=0 角点产生奇异；一维热方程中它短命，但会严重损害瞬态精度；给出代价很小的补救。 |
| Chen, Qin, Temam. *Numerical resolution near t=0 of nonlinear evolution equations in the presence of corner singularities in space dimension 1*. Commun. Comput. Phys. 9(3):568–586 (2011)；[arXiv 1011.4549](https://arxiv.org/abs/1011.4549)【摘要页】 | 一维 Burgers 与非线性反应扩散；两种补救程序（检索摘要称其一是加入角点校正函数）。 |
| Gracia, O'Riordan. *A singularly perturbed convection-diffusion parabolic problem with incompatible boundary/initial data*. Appl. Numer. Math. 190 (2023)，doi 10.1016/j.apnum.2023.04.011；同作者 *…reaction–diffusion problems with discontinuities in the initial and/or the boundary data*. J. Comput. Appl. Math. 370:112638 (2020)【检索摘要，书目来自 Crossref】 | 初边不相容在小参数下产生强内层；做法是把解分解为已知奇异分量加余项，再用 Shishkin 网格。 |
| Carslaw, Jaeger. *Conduction of Heat in Solids*（半直线热方程的 erfc 型解，含 Robin 边界的 erfc 加指数乘 erfc 形式）【记忆】 | 想法 A 的剖面本身是经典结果。 |

这一组说明：**“解 = 角点校正函数 + 光滑余项”在数值分析里是老办法**；想法 A 新的只可能是把它放进 PINN。

**(e) 其他相关但不构成先例**

- 综述 *Stiff-PDEs and Physics-Informed Neural Networks*（Arch. Comput. Methods Eng. 2023，[doi 10.1007/s11831-023-09890-4](https://doi.org/10.1007/s11831-023-09890-4)，作者未核）【检索摘要】：提到相邻边/角点冲突的边界条件会产生间断，连续激活的网络难学。是空间角点，不是初-边角点，也没有校正方案。
- Zong, He, Tartakovsky（见第 3 节）：抛物问题、初值尖锐扰动，但是靠归一化与采样，不是校正项。
- Wang, Qian, Wang. *Learning heat-based equations in self-similar variables*（ICLR 2026 AI&PDE workshop，[arXiv 2602.00872](https://arxiv.org/abs/2602.00872)）【摘要页】：把自相似坐标当输入变换，用于 Navier–Stokes 与 Burgers 的外推；不嵌入解析剖面，不讨论相容性。
- 用 x/√t 或 erfc 作为 PINN 输入特征、Stokes 第一问题（impulsively started plate）的 PINN：检索未找到。

### 2.2 仍可能是新的部分

1. **时间方向的角点层（初始层）校正项嵌入 PINN**：在 Dirichlet/Robin/Neumann 热方程和 Wentzell 问题上都没检出。
2. **Wentzell 边界下的层剖面及其嵌入**：层内切向项 Δ_Γ 和 c u_t 对剖面的修正，没有检索到文献。（这一点我没有查动态边界抛物问题的相容性条件与半直线解析解的 PDE 文献，可能已有经典结果。）
3. **诊断本身**：初边错配 → 误差起于边界、t→0；log(误差) 对 log(错配) 斜率约 0.78（单参数点、五个格点，只是相关）。没有找到 PINN 论文给出这类量化。
4. **幅值参数化的变体**：sl-PINN 显式型的幅值取自网络边界值，隐式型另设可训练部分；“独立可学习幅值的 erfc 校正项”只是这两者之间的变体，本身新意有限。

### 2.3 判定

- **设计模式**：已有先例（sl-PINN、SEPINN）。
- **针对初-边值不相容的时间角点层（含 Wentzell）**：未检出先例。
- 我的判断（非检索结论）：作为“把经典角点校正与 semi-analytic PINN 结合”有一定新意，但属于增量；如果配上 R32 的诊断和相容/不相容对照（1e-2 → 1e-4 量级的改善），论证会更有力。需要与 u₀ + t·N 型硬初值、加密 t≈0 采样等标准做法比较，否则审稿人会问为什么不用这些。

## 3. 想法 B：指数衰减输出变换

### 3.1 直接与最近先例

| 文献 | 内容 | 接近程度 |
|---|---|---|
| Zong, He, Tartakovsky. *Improved training of physics-informed neural networks for parabolic differential equations with sharply perturbed initial conditions*. CMAME 414:116125 (2023)，[doi 10.1016/j.cma.2023.116125](https://doi.org/10.1016/j.cma.2023.116125)；预印本 [arXiv 2208.08635](https://arxiv.org/abs/2208.08635)（标题略有不同）【全文，读了前 100000/135942 字符】 | 平流-弥散方程、高斯点源初值，解的峰值随时间幂律衰减（摘要给出 t^{−d/2}；第 2.5 节另有一句称峰值“指数下降”，与其公式不一致）。第 3.1 节“Normalized PINN”：ũ = u/g(t)，g(t) 取均场解的最大值（式 23–24，二维 g = M/[2π√(ε²+2D_x t)√(ε²+2D_y t)]），归一化方程（式 25）多出一项 −(ũ/g)(dg/dt)。相对 L² 误差按时刻定义（式 22），再取时间平均（式 45）。 | **机制相同**：用已知的解析时间包络相除，使网络学的量不衰减，从而保住相对精度。差别只在包络形式（幂律 vs 指数）和来源（均场解 vs 最低特征值）。若取 g = e^{−λt}，式 25 的额外项变成 +λũ，即 u = e^{−λt}ũ。 |
| Lagaris, Likas, Fotiadis. IEEE Trans. Neural Netw. 9(5):987–1000 (1998)；Lu 等 *PINNs with hard constraints for inverse design*, SIAM J. Sci. Comput. 43(6):B1105 (2021)；Sukumar, Srivastava, CMAME 389:114333 (2022)【记忆，未重新核对】 | 硬约束输出变换（含时间因子，如 t·N、1−e^{−t}）。 | 说明“在网络输出上乘已知因子”是标准做法，但目的是施加初边条件，不是保相对精度。Awais（2026）用的 u₀ + t·N 属此类。 |

**邻近但不是先例**：Guan–Elman（[arXiv 2409.07671](https://arxiv.org/abs/2409.07671)，对流扩散的输入变换，摘要不涉及时间衰减）【摘要页】；Mathematics 14(17):3208（2026，对流扩散 PINN 的晚期误差谱滤波，事后处理，不是输出变换）【检索摘要】；Huseynov 等 [arXiv 2606.12050](https://arxiv.org/abs/2606.12050)（ODE 的后验误差界，摘要未提积分因子）【摘要页】。另有若干检索结果在谈“以指数为基的单层网络”（钚-241 衰变幻灯片）等，来源不足，未采用。

### 3.2 仍可能是新的部分

- 把 λ 取自谱问题（本项目里 λ₁ 依赖 m，m=0、1、2 分别为 0.36、2.4、5.5），并以“相对误差随时间增长”为动机：未检出。
- 但它在数学上是 Zong 式时间相关归一化的特例，加上积分因子（u = e^{−λt}ũ 把谱整体平移 λ）这一初等变换，**很难单独构成论文贡献**。更适合作为实现细节或消融项。
- 适用范围的提醒（非检索结论）：e^{−λ₁t} 对单模初值最合适；混合模态时，更高模态在 ũ 中以 e^{−(λ_k−λ₁)t} 衰减，不会放大，但 λ 取错会引入 e^{(λ−λ_true)t} 的偏差。

### 3.3 判定

**部分已做**：时间相关包络归一化有先例（Zong 2023，幂律）；指数/特征值版本未检出已发表先例，但属于其特例。

## 4. 对 R32 的含义（仅供参考，决定权在你）

- 因素 1（不相容角点层）对应主要失效台阶 m0_lin，与想法 A 对口；因素 2（m=2 的相对误差放大）与想法 B 对口。A 值得继续，B 基本是已知技术。
- 写作时应引用：sl-PINN 系列与 SEPINN（设计模式）、Flyer–Fornberg 与 Chen–Qin–Temam（角点校正的数值分析来源）、Zong 2023（时间包络归一化），并把 Awais 2026 作为动态边界 PINN 的现有基准提到。
- 若要加强新颖性主张，需要补查：动态边界抛物问题的相容性条件与半直线解（PDE 理论文献）、是否有关于“初边不相容 PINN 误差”的会议论文或学位论文、中文库。

## 5. 未核实项汇总

- ScienceDirect 页面（Zong 期刊页、Gracia–O'Riordan、Jung–Kim–Ngon、PATPINN）未能打开，书目信息来自 Crossref 或检索结果。
- Flyer–Fornberg、Cao 等、Martínez-Esteban 等、Jung–Kim–Ngon、综述 Stiff-PDEs 只见检索摘要。
- Lagaris、Lu 等、Sukumar–Srivastava、Carslaw–Jaeger 为记忆引用。
- EDRAS 的期刊发表信息、2312.06278 的期刊卷期未核。
- 所有“未检出”均指在上述检索词和来源下未检出。

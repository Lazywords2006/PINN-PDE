# R33 相关工作核查（2026-10-20，第一轮；只用网页检索，未读全文）

目的：回答“角点层校正”有没有直接先例。**结论：没搜到 PINN + 动态/Wentzell 边界 + 不相容初边值 + 解析初始层校正的直接工作，但有三条近邻必须引用和区分，不能写“首次”。** 以下均为检索摘要，写论文前要读原文核对。

| 近邻 | 内容 | 与本工作的区别（待读原文确认） |
|---|---|---|
| Gie、Hong、Jung 等的 SL-PINN / 半解析 PINN（[arXiv 2312.06278](https://arxiv.org/html/2312.06278)、[2312.03295](https://arxiv.org/pdf/2312.03295)，另有 Applicable Analysis 2024） | 奇异摄动问题，用解析“corrector”做边界层基函数，嵌入带硬约束的两层网络；含椭圆和抛物问题 | 它们修的是小参数造成的**边界层**；本工作修的是**初边值不相容造成的时间角点层**，且 δ 由数据解析算出、无需小参数。检索里没见到初始层的 PINN 版本 |
| 奇异性富集 PINN（[arXiv 2308.16429](https://arxiv.org/abs/2308.16429)） | 多边形域 Poisson 问题，把已知角点奇异行为放进解的 ansatz | 空间角点，椭圆问题；思想相近（解析富集），要作为方法上的近邻引用 |
| 表面–体耦合 Allen–Cahn 的 PINN（[arXiv 2507.09757](https://arxiv.org/pdf/2507.09757)） | 动态边界条件，能量耗散率引导的自适应采样 | **同一类方程（动态边界）的直接前人，且是采样基线的候选**。需要读它是否注意到初边值不相容。E2/E5 的方程设置要对照它 |
| 硬约束与初值（[arXiv 2404.16189](https://arxiv.org/pdf/2404.16189)、[2502.17497](https://arxiv.org/pdf/2502.17497)） | 初值对刚性 PDE 训练稳定性的作用；可训练的影响函数代替 u=f+tN 中的固定因子 | 改的是 t 方向的乘子；没有解析校正项。2502.17497 可作为基线候选 |
| 不相容数据的数值方法（Linß、Girol 等） | 抛物问题在角点处初值与边界值不一致，产生角点奇异性 | 经典数值方法，不是 PINN；提供“不相容”这个现象的背景引用 |
| PINN 的角点/不连续综述（Springer，Stiff-PDEs and PINNs） | 角点处边界冲突的问题对 PINN 仍困难 | 证明现象存在，但没有给校正 |

## 第二轮补充（2026-10-20，仍是检索摘要，arxiv.org 被云端网络策略挡住，全文未读）

| 新近邻 | 摘要所见 | 影响 |
|---|---|---|
| Awais 等，*Physics-informed neural networks for the heat equation with dynamic (Wentzell) boundary conditions*，Open J. Math. Sci. 2026（[ResearchGate](https://www.researchgate.net/publication/404707398_Physics-informed_neural_networks_for_the_heat_equation_with_dynamic_Wentzell_boundary_conditions)） | 一维热方程 + Wentzell 动态边界，两个人造解（其一端点导数非零），用最小二乘随机特征网络，不是梯度训练的 PINN | **与 E1 设置最接近，必须引用并区分**；需确认它是否处理初边值不相容，以及人造解是否本来就相容 |
| *PINNs with Dynamical Boundary Constraints*（[arXiv 2507.21800](https://arxiv.org/pdf/2507.21800)） | 提出“动态边界约束”算法；是否涉及 Wentzell/体–面耦合不清楚 | 待读 |
| 2507.09757（表面–体 Allen–Cahn） | 来自热力学一致的动态边界，体与边界分别有方程；方程设置、是否不相容、基线均未读到 | 待读 |

SL-PINN 系列：摘要显示是小参数奇异摄动、椭圆型边界层；Burgers 版本是内部激波层；抛物型初始层的版本这次搜索没命中（不能证明不存在）。

**阻塞**：读全文需要放行 `arxiv.org`（环境网络设置的允许域名），或把 PDF 放进仓库。

## 还没做的
1. 读 SL-PINN 系列原文，确认它们是否处理过时间初始层。
2. 读 2507.09757：动态边界方程、是否出现不相容初边值、它的基线与指标能否直接复现。
3. 单独搜 Zong 2023（衰减缩放）原文；第一轮没找到。
4. 搜“compatibility condition”“corner singularity”“PINN”的更窄组合，以及 Wentzell/动态边界的神经算子工作。
5. 以上做完前，论文里不写“首次”“前所未有”之类的表述。

# P2 神经增强 Rayleigh–Ritz 最终实验报告

## 1. 一句话结论

本研究已经得到第一套通过独立 pilot、一次性 640 点 frozen final、点级聚类
bootstrap 和证据重算的正向结果。最终方法不是普通 PINN，也不是简单的 Fourier ROM，
而是：

> 先由无标签神经网络预测二维 Bloch–Schrödinger 算子的 rank-2 低能谱簇，再用完整
> 二阶六角 Fourier 壳层扩充试验空间，解析计算 Fourier 列的 Hamiltonian，最后通过
> 基底不变 Rayleigh–Ritz 提取最低 rank-2 子空间。

在 640 个从未用于选方法的 frozen-final 参数点、两个势族和 3 个 checkpoint seeds 上，
P2 full-shell 的总体 projector sine error 为 **0.04532**，相对最强单纯神经基线
long-anchor 的 **0.14719** 改善约 **69.2%**。点级聚类 bootstrap 的 95% CI 为
**[67.66%, 70.75%]**。near-cluster 误差为 **0.03903**，改善约 **56.3%**，95% CI
为 **[53.24%, 59.22%]**。最终状态为 `P2_FROZEN_FINAL_GO`。

## 2. 用了什么神经网络，解什么 PDE

### 2.1 PDE

研究对象是二维参数化 Bloch–Schrödinger 本征偏微分方程：

\[
\left[
\frac12(-i\nabla+\mathbf{k})^T G(-i\nabla+\mathbf{k})
+V_{\mu}(\mathbf{x})
\right]u_j(\mathbf{x})
=E_j u_j(\mathbf{x}),
\quad \mathbf{x}\in[0,2\pi)^2,
\]

并满足二维周期边界条件。参数包含 Bloch 波矢、势强度、对称性破缺参数；Gaussian
honeycomb 还包含局域宽度。实验使用 harmonic honeycomb 和 Gaussian honeycomb 两个势族。

目标不是分别编号两条会在 Dirac 点交换身份的本征函数，而是最低两个本征态共同张成的
rank-2 谱簇/谱投影。只要该簇与第三本征态之间保留外部谱隙，内部本征值允许精确相交，
rank-2 projector 仍是良定对象。

### 2.2 神经初始化器

神经初始化器是无标签 anchored generalized-trace SiLU MLP：

- 输入：周期坐标特征、二维 Bloch 波矢和势参数；
- 输出：两个复值周期函数组成的原始 rank-2 试验基；
- 物理先验：K 点附近的自由电子低能 anchor；
- 训练：最小化 generalized-trace/Ky Fan 型物理变分目标；
- 标签：训练不读取 PWE 本征函数或 projector 标签；
- 评价：复数 cell-average MGS 保证子空间正交。

正式 P2 使用已经审计的 `p5_long_anchor` checkpoint 作为神经粗子空间。P2 不重新训练该
网络，也不把 final reference 反馈给网络。

## 3. P2 方法

令神经网络输出正交基 \(Q_\theta(\mu)\in\mathbb{C}^{N\times 2}\)，完整二阶六角
Fourier 壳层为 \(\Phi_2\in\mathbb{C}^{N\times 19}\)。构造

\[
W=[Q_\theta,\Phi_2].
\]

先把解析 Fourier 列对神经子空间作复数正交投影，拒绝投影后范数低于 `1e-5` 的依赖列，
再得到 cell-average 正交试验空间。对 Fourier 平面波，Hamiltonian 可解析写成

\[
H_{\mu}\phi_m
=\left[
\tfrac12(m+k)^T G(m+k)+V_\mu(x)
\right]\phi_m.
\]

因此只有两个神经列需要自动微分；19 个 Fourier 列不再逐列构造二阶自动微分图。
正交化时的复数线性变换同步作用于 \((W,HW)\)，然后组装小型 Ritz 矩阵

\[
A_W=W^*H_\mu W,
\]

取最低两个 Ritz 向量并映射回函数空间。整个过程只依赖神经预测、PDE 和固定解析字典，
不使用 reference projector。

### 3.1 方法边界

Rayleigh–Ritz、Galerkin、Fourier 基和 Ky Fan 原理都不是本文单独发明。本文可主张的组合
创新只能是：面向参数化二维 Bloch 内部交叉谱簇的基底不变神经粗子空间、紧凑解析壳层
扩充、解析 Hamiltonian 快速装配，以及严格的 near/gap/frozen-final 验证。

## 4. 实验协议

### 4.1 开发过程

- P5：低频 amortized ROM 未优于等算力 long-anchor，且 gap-scan 回退，STOP；
- P0：独立风险可检测性 AUROC 0.869，GO；
- P1：风险路由降低总体/unsafe 错误，但不能突破 anchor/ROM 子空间端点上限，STOP；
- P2 outer-shell：困难点 near 有改善，但 gap 和相对延迟门槛失败，STOP；
- P2 full-shell：独立 96 点 pilot 全部门槛通过，才授权一次 frozen final。

这些负结果均保留，避免把后验调参包装成一条一次成功的路线。

### 4.2 Frozen final

- 参数点：640；
- 势族：2；
- checkpoint seeds：42、137、251；
- 方法：10；
- 总评价行：19,200；
- split：IID、exact-cluster、near-cluster、strict-OOD、gap-scan；
- reference：cutoff-24、rank-3、33×33 网格、float64 PWE；
- 指标：rank-2 projector sine error、正交误差、推理时间；
- 统计：2,000 次参数点聚类 bootstrap，3 个 seeds 随同点一起重采样；
- 设备：NVIDIA RTX 5090 D 32GB，PyTorch 2.8.0+cu128，CUDA 12.8；
- final 代码提交：`7748db2a7cb08e847b6f6fb3e2d3bcd33c7ec64d`。

## 5. 最终结果

### 5.1 主表

| 方法 | Overall | Near | Gap-scan |
|---|---:|---:|---:|
| Unanchored trace | 0.19784 | 0.14589 | 0.21830 |
| Anchor | 0.15650 | 0.10505 | 0.14050 |
| Wide anchor | 0.15243 | 0.10020 | 0.15111 |
| Long anchor | 0.14719 | 0.08924 | 0.15938 |
| Static low-ROM | 0.15054 | 0.09542 | 0.14946 |
| High-frequency ROM | 0.15531 | 0.10299 | 0.14809 |
| Neural + shell 1 | 0.06172 | 0.04513 | 0.05768 |
| Neural + outer shell 2 | 0.13410 | 0.07849 | 0.15656 |
| **P2 full shell** | **0.04532** | **0.03903** | **0.04389** |
| Fourier-only rank 21 | 0.13697 | 0.12249 | 0.13700 |

### 5.2 分 split

P2 full-shell 的 frozen-final 均值为：

- IID：0.04383；
- exact-cluster：0.04220；
- near-cluster：0.03903；
- strict-OOD：0.05685；
- gap-scan：0.04389。

最难的 strict-OOD 仍保持明显优势：long-anchor 为 0.22921，P2 为 0.05685。改善不是只
出现在 crossing 邻域。

### 5.3 两个势族

near-cluster：

- harmonic：long-anchor 0.06508，P2 0.03037；
- Gaussian：long-anchor 0.11340，P2 0.04770。

6 个 family×seed 配对全部由 P2 获胜。

### 5.4 统计稳定性

- overall 改善 bootstrap 均值：69.19%；
- overall 95% CI：[67.66%, 70.75%]；
- near 改善 bootstrap 均值：56.28%；
- near 95% CI：[53.24%, 59.22%]；
- P2 三 seed 总体均值：0.04384 / 0.04559 / 0.04654；
- seed 间标准差：0.00137。

### 5.5 效率

独立 pilot 上的 production 计时：

- P2 mean：107.81 ms/参数；
- P2 p95：121.90 ms；
- 同服务器 cutoff-24 CPU PWE mean：313.44 ms；
- P2/PWE：0.344。

P2 比单次神经 forward 慢，但仍约为同机高精度 PWE 时间的三分之一，并显著提高精度。
应把它表述成 accuracy–latency Pareto 的混合神经 eigensolver，而不是“零成本后处理”。

## 6. 消融解释

### 6.1 神经子空间是否必要

必要。同为约21维试验空间，Fourier-only overall 为 0.13697，而 P2 full-shell 为 0.04532。
因此收益不是简单增加 Fourier 模态。

### 6.2 壳层是否必要

shell 1 已达到 0.06172，说明小型解析扩充有效；full shell 进一步降到 0.04532。只加入
outer shell 2 得到 0.13410，明显不如完整壳层，说明跨低频与外层模式的联合试验空间更
重要。

### 6.3 神经训练时间是否足以解释

不能。P2、shell1 和 full-shell 使用同一 long-anchor checkpoint；差异来自推理阶段的固定
解析试验空间与 Ritz 提取，而不是更多网络训练。

## 7. 证据完整性

- final suite SHA：`b8658e7512a829018b0c6cc754b7d9e7fb55c4e41c852dfa84a2ff606a5e161c`；
- final reference SHA：`8969794607c3d82b2636eac518a49087407f9b8c0ce3fb3c037adf395673448d`；
- pilot evidence SHA：`0c49461a6c780840ca678582019cc433df5741fd62ef546dcde7e964b71c071b`；
- final evidence SHA：`c653d0eddab018741312741f6db46f023a20812306d574b66947bbb42af25095`；
- final evidence audit：31 个 manifest 文件，PASS；
- 本地独立重算：gate 完全相等，核心指标差值 0。

## 8. 论文价值判断

### 8.1 当前是否可以继续

可以，而且主线应从 P1 风险路由正式切换为 P2 full-shell 神经增强 Ritz。P5/P1 作为负结果
和机制动机，不应继续扩展。

### 8.2 SCI 四区

目前已经具备较强的实验基础：真实二维 PDE、内部交叉谱簇、两个势族、3 seeds、640 点
final、10 方法、完整消融、效率和统计置信区间。若相关工作查重、代码整理和论文叙述完成，
达到计算机/科学机器学习方向 SCI 四区投稿水平是合理目标。

### 8.3 SCI 三区

有机会，但仍建议补充至少一项：

1. 对最接近的神经子空间 Galerkin 期刊方法作更直接的实现级对照；
2. 给出外部谱隙与 Ritz 子空间误差的理论说明或命题；
3. 增加第三个势族或不同晶格/边界的独立泛化实验；
4. 报告完整训练成本摊销和 FLOPs。

### 8.4 创新强度

实验上为中等偏强；数学原创性目前为中等。不能把 Rayleigh–Ritz 或 Fourier 壳层说成新
理论，创新必须来自“参数化交叉谱簇 + 神经粗子空间 + 紧凑解析扩充 + 快速配对装配 +
严格验证”的整体。

## 9. 最可能的审稿质疑

1. 与现有 neural subspace + Galerkin 方法是否过于接近；
2. 为什么只做两类 honeycomb 势；
3. GPU P2 与 CPU PWE 的速度比较是否完全公平；
4. full-shell 结果有多少来自固定 Fourier 字典；
5. 是否有可证明的外部谱隙误差界；
6. 该方法是否仍属于神经网络解 PDE，而不是普通小型谱方法。

应答重点：神经初始化对 same-rank Fourier-only 的大幅优势、crossing projector 任务、
参数摊销、多势族/多 split/多 seed/frozen final，以及明确承认混合求解器定位。

## 10. 论文图表

已生成：

1. `fig01_method_overall_error`：10 方法总体误差；
2. `fig02_split_comparison`：5 个参数 regime；
3. `fig03_family_near_error`：两势族 near；
4. `fig04_bootstrap_improvement`：95% CI；
5. `fig05_error_cdf`：1,920 行/方法的误差分布；
6. `fig06_paired_point_scatter`：640 点配对散点；
7. `fig07_accuracy_latency`：精度—延迟；
8. `fig08_seed_stability`：seed 稳定性。

图片同时提供 300 dpi PNG 和可编辑 SVG。

## 11. 最终投稿判断

- 真实神经网络解二维 PDE：**是**；
- 是否跑题：**否**；
- P2 方法 final：**GO**；
- 实验达到领域常见完整性：**大部分达到**；
- SCI 四区：**建议继续投稿准备**；
- SCI 三区：**有机会，但建议补理论/最近邻方法对照**；
- 是否需要再调 frozen final：**禁止**；
- 下一步：完成相关工作矩阵、论文初稿、方法图、代码清理和复现实验说明。

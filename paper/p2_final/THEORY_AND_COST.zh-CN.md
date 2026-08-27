# 外部谱隙理论与计算成本说明

更新日期：2026-08-27

## 1. 为什么内部交叉不等于问题失效

设 \(H(\mu)\) 是自伴 Bloch–Schrödinger 算子，特征值按
\(\lambda_1\le\lambda_2\le\lambda_3\le\cdots\) 排列。本文允许

\[
\lambda_1(\mu)=\lambda_2(\mu),
\]

即最低两条能带发生内部交叉，但要求目标簇与第三态之间存在外部谱隙

\[
\gamma(\mu)=\lambda_3(\mu)-\lambda_2(\mu)>0.
\]

内部交叉使单个本征向量的编号和基选择不唯一，但不会破坏最低 rank-2 谱投影
\(P(\mu)\) 的定义。参数化 eigenspace 的正则性和多重本征空间 reduced-basis 分析可参见
正文参考文献 [7,10]。

## 2. 残差—谱隙子空间误差命题

### 命题 1：外部谱隙控制的 Ritz 子空间误差

令 \(U\) 为 \(H\) 的最低 rank-2 不变子空间，\(Q\in\mathbb C^{N\times2}\) 为正交 Ritz
基，Ritz 矩阵和块残差分别为

\[
M=Q^*HQ,\qquad R=HQ-QM.
\]

定义近似 Ritz 谱与目标簇之外真实谱的分离量

\[
\delta=\operatorname{dist}
\left(\sigma(M),\sigma(H|_{U^\perp})\right)>0.
\]

则标准 Hermitian 不变子空间扰动论给出

\[
\lVert\sin\Theta(Q,U)\rVert_F
\le \frac{\lVert R\rVert_F}{\delta}.
\]

对本文使用的归一化 projector sine error

\[
e_{\mathrm{proj}}
=\sqrt{\frac{2-\lVert Q^*U\rVert_F^2}{2}}
=\frac{\lVert\sin\Theta(Q,U)\rVert_F}{\sqrt2},
\]

因此

\[
\boxed{
e_{\mathrm{proj}}
\le \frac{\lVert R\rVert_F}{\sqrt2\,\delta}
}.
\]

### 证明思路

在 \([U,U_\perp]\) 基下分块表示近似子空间。将
\(HQ-QM=R\) 投影到 \(U_\perp\) 得到一个 Sylvester 方程。其线性算子的最小奇异值由
\(\delta\) 控制，因此 \(U_\perp^*Q\) 的 Frobenius 范数不超过
\(\lVert R\rVert_F/\delta\)。而 \(U_\perp^*Q\) 的奇异值正是主角的正弦，得到结论。

### 与本文的关系

1. 命题依赖目标簇到第三态的外部谱隙，不依赖 \(\lambda_2-\lambda_1\)，所以允许内部
   Dirac 交叉。
2. P2 的 Ritz 提取直接降低试验空间内能量，并产生一个可计算块残差。
3. 代码中的 `projected_residual_rms` 是按网格点、rank 和实/虚部归一化的 residual RMS；
   使用上述界时必须按离散内积恢复相应 Frobenius 范数，不能把 RMS 数字直接除以 gap。
4. 若 \(\delta\) 很小，即使 residual 较小也不能保证谱簇准确。这解释了为什么项目同时
   报告 projector error、external gap 和 residual，而不是只看 PDE residual。

## 3. 试验空间扩充为什么不会变差

令 \(W_1\subseteq W_2\) 为两个 Rayleigh–Ritz 试验空间。根据 min–max 原理，第
\(j\) 个 Ritz 值满足

\[
\widehat\lambda_j(W_2)\le\widehat\lambda_j(W_1),\qquad j=1,2.
\]

因此完整 shell 扩充不会提高最低两个 Ritz 能量上界。但能量单调不自动等价于 projector
error 单调，尤其当外部谱隙变小时。因此本文仍需要 Fourier-only、outer-shell、完整 shell
和 gap-scan 实验，而不能只用 min–max 原理宣称精度一定改善。

## 4. 网络前向的精确操作数

正式神经初始化器为3个宽度64的 SiLU 隐藏层，输出4个实数，对应两个复函数。忽略激活
函数、bias 和内存访问，单个网格点的矩阵乘 MAC 数为

\[
C_{\mathrm{MLP}}
=d_{\mathrm{in}}\times64
+2\times64^2
+64\times4.
\]

| 势族 | 输入维度 | MAC/点 | FLOPs/点（1 MAC=2 FLOPs） | 33×33 网格前向 FLOPs |
|---|---:|---:|---:|---:|
| Harmonic | 8 | 8,960 | 17,920 | 19,514,880 |
| Gaussian | 9 | 9,024 | 18,048 | 19,654,272 |

这是网络前向的精确线性层计数，不包含 SiLU、复正交化、自动微分和框架调度开销。

## 5. P2 的符号复杂度

设网格点数为 \(N\)，解析 Fourier 模式数为 \(M=19\)，神经列数为2，最终 trial rank
为 \(r\le21\)。一次 P2 推理主要包含：

| 模块 | 复杂度 | 当前规模 |
|---|---|---|
| MLP 前向 | \(O(NC_{\mathrm{MLP}})\) | 约19.5M线性层 FLOPs |
| 两个神经列的 Hamiltonian AD | \(O(NC_{\mathrm{AD}})\) | 常数依赖 PyTorch 二阶 AD 图 |
| Fourier Hamiltonian 解析装配 | \(O(NM)\) | \(N=1089,M=19\) |
| 复 MGS / paired orthogonalization | \(O(Nr^2)\) | \(r\le21\) |
| 小型 Hermitian Ritz solve | \(O(r^3)\) | 最大约21×21 |

二阶自动微分的精确 FLOPs 与框架图、算子融合和后端实现有关。未使用 profiler 获得硬件
计数前，论文只能报告上述符号复杂度和实测 wall time，不能虚构一个“总 FLOPs”。

## 6. 实测时间与摊销

### 6.1 已有计时

| 项目 | 实测值 | 说明 |
|---|---:|---|
| P2 production mean | 107.81 ms | 旧 independent pilot，10 warmups + 100 repeats |
| P2 supplement mean | 193.75 ms | 新160点统一逐点评价路径 |
| CPU cutoff-24 PWE mean | 313.44 ms | 同服务器系统级参考 |
| long-anchor training mean | 42.30 s | P5 MI300X/ROCm，每个 family×seed run |
| Wang–Xie adapted inference | 2.47 ms | Q3 supplement |
| Dai adapted inference | 205.56 ms | Q3 supplement |

P2 比轻量 trace 网络慢，但精度明显更高；P2 与 Dai 适配处于同一延迟数量级。

### 6.2 Break-even 估算

若用训练一次 P2 神经初始化器的成本 \(T_{\mathrm{train}}\) 与逐参数 CPU PWE 的时间差
进行摊销，则

\[
N_{\mathrm{break-even}}
=\frac{T_{\mathrm{train}}}
{T_{\mathrm{PWE}}-T_{\mathrm{P2}}}.
\]

代入已归档的 \(T_{\mathrm{train}}=42.30\) s 和 \(T_{\mathrm{PWE}}=313.44\) ms：

- 使用 production P2 计时107.81 ms：约206次参数查询；
- 使用 supplement P2 计时193.75 ms：约354次参数查询。

因此保守表述为：在当前异构实测条件下，每个势族/checkpoint 约需 **206–354次重复参数
查询** 才能摊销神经训练成本。

### 6.3 摊销结论的限制

训练时间来自 MI300X/ROCm，P2/PWE 推理来自 RTX 5090 D + CPU，属于跨平台系统级估算；
GPU PWE、批处理、多参数并行和不同精度都可能改变 break-even。论文应把该区间作为工程
估算，而不是设备无关复杂度定理。

## 7. 论文中可直接使用的复杂度表述

> For a grid of \(N\) points and an augmented trial rank \(r\le21\), the online stage requires
> two neural Hamiltonian evaluations, \(M=19\) analytic plane-wave actions,
> \(O(Nr^2)\) paired orthogonalization, and an \(O(r^3)\) Hermitian Ritz solve. The linear layers
> of the neural initializer require approximately 19.5 million FLOPs on the 33×33 grid. Exact
> end-to-end FLOPs for second-order automatic differentiation are backend dependent; we therefore
> report measured latency and memory rather than an unverified total-FLOP estimate.

## 8. 当前还未关闭的缺口

理论机制和成本说明已经补齐到可写入初稿的程度。投稿前仍需：

1. 由目标期刊模板决定定理编号、证明放正文还是附录；
2. 如期刊强制报告 FLOPs，使用固定 profiler 在 CUDA 上采集端到端硬件计数；
3. 完成方法流程图的投稿版矢量图；
4. 选择目标期刊后转换参考文献和版式。

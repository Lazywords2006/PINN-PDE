# 当前方法与架构说明

## 一句话版本

A-GTROMNet 用一个轻量神经网络无标签求解二维参数化 Bloch–Schrödinger PDE 的最低
rank-2 本征子空间，不分别追踪在 Dirac 点交换身份的两条能带。

## 求解对象

\[
\mathcal H_{\mathbf k,\mu}u=
\left[\tfrac12(-i\nabla+\mathbf k)^TG(-i\nabla+\mathbf k)
+V_\mu(\mathbf x)\right]u=Eu,
\qquad \mathbf x\in[0,2\pi)^2.
\]

未知对象是两个周期复函数张成的子空间。网络输出形状为
`[batch, points, rank=2, real/imag]`，因此项目求解的是真实二维 PDE 本征问题。

## 当前候选的数据流

1. 将二维坐标变换为 `sin/cos` 周期特征，并拼接 Bloch 波矢与势参数。
2. 三层、宽度 64 的 SiLU MLP 产生共享复值试探函数。
3. K 点附近的两个低能平面波组合提供固定物理 anchor。
4. 一个小型参数网络把 PDE 参数映射到七个低频 Fourier 模态的复系数。
5. 共享分支、anchor 和 ROM 修正共同组成未正交的 rank-2 试探空间。
6. 训练最小化 generalized trace `Tr(B⁻¹A)`；`A` 是 Hamiltonian Ritz 矩阵，`B`
   是 Gram 矩阵。空间导数由 PyTorch 自动微分计算。
7. 评价时使用复 modified Gram–Schmidt，并以投影误差、主角度、PDE residual、正交
   误差和 Gram 条件数评价。

PWE 参考解只在评价阶段使用，不是训练标签。

## P4 到 P5 的逻辑

- G0：只有 generalized-trace MLP。
- G1：G0 + 物理 anchor；不增加可训练参数。
- G2：G1 + 静态低频 Fourier ROM；当前最优但参数和计算更多。
- G3：G2 的 ROM 在训练后半程退火到零；表现不如 G2。
- P5：用宽网络、长训练、去 anchor ROM 和高频 ROM 四类控制，判断 G2 的收益究竟
  是否来自正确低频物理结构。

## 为什么学习谱簇

内部简并处的单个本征向量不唯一，可以交换编号或在目标簇内旋转。只要第二与第三
本征值之间仍有外部谱隙，整个 rank-2 投影仍是良定目标。因此损失和指标都必须对簇内
基变换不敏感。

## 不应过度声称

Ky Fan、generalized trace、PWE、Fourier ROM、谱投影、anchor 和 MGS 都有既有数学或
计算工作。本项目能够主张的创新只能是经过 P5 和 final 证明的**特定协同机制**，不能
把任何单个零件写成首创。当前 P5 正式实验尚未运行，因此方法名和创新表述仍是候选。

# 方法与架构说明

## 一句话版本

P3 Block KyFan-PINN 用一个轻量神经网络学习二维 Bloch–Schrödinger PDE 的最低
rank-2 本征子空间，而不是分别追踪两条会在简并点交换身份的能带。

## 求解对象

未知对象是两个周期复函数张成的子空间：

\[
\mathcal H_{\mathbf k,\mu}u=
\left[\tfrac12(-i\nabla+\mathbf k)^TG(-i\nabla+\mathbf k)
+V_\mu(\mathbf x)\right]u=Eu.
\]

参数包含 Bloch 波矢 \((k_x,k_y)\) 和势函数参数。网络输出
`[batch, points, rank=2, real/imag]`。因此项目是真实的二维 PDE 本征求解，不是一维
ODE，也不是只拟合预先生成标签的代理模型。

## 网络数据流

1. 周期坐标 MLP 接收 \((x,y,\mathbf k,\mu)\)，产生共享修正。
2. 一个物理 anchor 提供接近 K 点低能平面波的起点。
3. 两个局部 ROM 网络把 PDE 参数映射为复 Fourier 系数。
4. 在归一化参数空间中，可学习图中心生成平滑 partition-of-unity 权重。
5. 各图修正被平滑组合；可选能量密度权重突出局部困难区域。
6. dual-path 复 modified Gram–Schmidt 把输出收回标准 cell-L2 正交约束。
7. 训练最小化 Ky Fan trace，即两个低能态的总能量，不使用参考本征函数标签。

## P3 相对 P1 的实质差异

- P1：单一坐标 MLP + 固定物理 anchor + Ky Fan trace。
- P3：在 P1 上增加参数化多图 ROM 修正、可学习图中心、能量密度调制，以及由残差与
  图间分歧构成的无标签风险信号。

代码测试会分别验证 anchor 类型、M 加权和多图确实改变输出，避免“配置开关存在但
计算完全相同”的假实现。

## 为什么学习谱簇

在内部简并处，单个本征向量可以任意旋转或交换编号；逐带标签不连续。只要目标
rank-2 簇与第三条能带之间仍有外部谱隙，整个投影子空间仍是良定对象。项目以投影
误差、主角度和 Ky Fan 能量评价该对象，不以两列输出的具体顺序评价。

## 参考解与公平性

参考解使用 hexagonal-shell plane-wave expansion。2026-07-30 的代表点审计比较
cutoff 20 与 24：六点全部满足 rank-2 投影差 `<1e-3` 且低本征值最大差 `<1e-5`。
正式缓存统一使用 cutoff 24。

训练不读取 PWE 标签。validation 缓存只用于 pilot 评价；冻结 final suite 只有重新
计算的 promotion gate 为 GO 后才能打开。

## 不应过度声称

Ky Fan 原理、PWE、谱投影、ROM、多图思想和 MGS 都不是本文单独发明。可检验的论文
主张应限定为：这些机制是否形成一个对内部简并更稳定、可摊销且消费级单卡可复现的
参数化神经谱簇求解器。该主张必须由尚待运行的 GPU 对照、消融和统计实验支持。

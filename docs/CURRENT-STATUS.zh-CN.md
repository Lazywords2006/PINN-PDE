# 当前研究状态

更新日期：2026-08-28

## 一句话结论

当前课题使用 **SR-SC-NARR 条件神经增强 Rayleigh–Ritz 求解器**，求解二维参数化
Bloch–Schrödinger 本征 PDE 的最低 rank-2 谱投影。修正 D6 对称性后的唯一一次160点 CUDA
正式确认已完成，17项 formal/convergence gate 全部通过，状态为
**`V3_FORMAL_PROMOTION_GO`**。证据足以进入 SCI 四区投稿准备；SCI 三区具有现实机会，
但路由阈值附近的外部泛化仍是主要短板。

## 到底用了什么网络、解什么方程

- 网络：3层、每层64单元、SiLU 激活的 family-specific 参数条件 MLP；
- 训练：不使用 PWE 波函数标签，最小化 generalized-trace 变分目标；
- PDE：二维周期 Bloch–Schrödinger 本征方程；
- 输出：不是给两条会交换身份的能带强行编号，而是最低两态共同张成的 rank-2 谱空间；
- 推理：势谱尾能量决定使用 tie-closed Fourier 空间还是 neural–Fourier 混合空间，再做
  紧凑 Hermitian Rayleigh–Ritz 求解。

因此，它属于真实的“神经网络求解 PDE 本征问题”，但不是普通 residual PINN。

## 正式结果

正式矩阵：160个物理点 × 3 seeds × 11方法 = 5,280行。

| 方法 | Overall projector error | Eigenvalue MAE | CUDA 延迟 |
|---|---:|---:|---:|
| **SR-SC-NARR** | **0.030929** | **0.009837** | 176.64 ms |
| Kinetic Fourier ≥25 | 0.043425 | 0.015996 | 105.55 ms |
| Fixed neural–Fourier 25 | 0.031784 | 0.009890 | 134.81 ms |
| D6 shell 3, rank 37 | 0.030799 | 0.011275 | 220.37 ms |
| Long-anchor neural | 0.139905 | 0.022595 | 1.27 ms |
| Wang–Xie adapted | 0.132717 | 0.018248 | 1.10 ms |
| Dai adapted | 0.432885 | 0.110026 | 130.33 ms |

- 相对 Fourier-25，均值 projector error 改善28.76%；
- family×split 分层 point bootstrap 95%区间：[28.08%, 29.44%]；
- p95 / maximum：0.10568 / 0.16686；
- proposed-method 最大 raw Hermiticity defect：`7.13e-6`；
- 最大正交误差：`2.47e-7`；
- 最小 external gap：0.01917；
- trial rank：25–27；rank-37 Fourier control 为37；
- 峰值 allocated/reserved CUDA 显存：1.24/1.26GB。

## 必须诚实说明的条件性

正式数据中，80个 harmonic 点全部进入 Fourier 分支，与 Fourier-25 数值完全一致；80个
Gaussian 点全部进入 hybrid 分支，projector error 从0.07873降到0.05374，降低31.75%。
因此，整体提升全部来自 Gaussian 势族。

安全说法是：

> 对谱尾复杂的局域 Gaussian 势，两个无标签神经方向能够稳定改善紧凑 Fourier 空间；
> 对光滑 harmonic 势，路由安全回退至 Fourier，避免精度回退。

禁止写成：

- “神经方法在所有势族上都优于 Fourier”；
- “SR-SC-NARR projector accuracy 最优”；
- “路由已经跨势族泛化”；
- “路由提高了当前实现的速度”；
- “优于 Wang–Xie/Dai 原作者官方方法”。

## 与 rank-37 强对照的关系

SR-SC-NARR 的 mean projector error 比 rank-37 shell-3 高0.42%，但 eigenvalue MAE 低
12.75%、延迟低19.84%、rank低10–12维；Gaussian family 的 projector error 还低7.71%。
因此应写成 Pareto trade-off，不写无条件支配。

## 数值审计

| 检查 | 结果 | 门槛 |
|---|---:|---:|
| cutoff 24→28 reference projector | `1.51e-6` | `<1e-3` |
| cutoff 24→28 eigenvalue | `6.95e-10` | `<1e-5` |
| grid 65→97 solver projector | `2.10e-4` | `<1e-3` |
| grid 65→97 solver eigenvalue | `4.77e-7` | `<1e-4` |
| proposed raw Hermiticity defect | `7.13e-6` | `<1e-4` |

5,280行身份无缺失、无重复，必需数值全部 finite，result manifest 与完整 evidence archive
逐文件哈希一致。

## 投稿判断

- SCI 四区：**达到正式写稿和投稿准备标准**；
- SCI 三区：**可以尝试，但不是稳妥档**；
- 创新强度：组合与机制创新中等，数值证据强，通用路由外部有效性中等偏弱；
- 最可能质疑：route 与 family 完全混淆、阈值0.1附近无样本、router 当前增加延迟、
  bootstrap 条件于3个 checkpoints、外部基线为公式级适配。

冲击更稳健 Q3 的最有效补充是：固定现有0.1阈值，预注册连续 roughness sweep 或第三个中等
谱复杂度势族，并加入 tail-ratio/AD/Fourier/orthogonalization/Ritz 的 latency breakdown。
这些补充不得重新调节已经冻结的路由。

## 当前文件入口

- 英文新稿：`paper/v3_manuscript/MANUSCRIPT.en.md`；
- 中文新稿：`paper/v3_manuscript/MANUSCRIPT.zh-CN.md`；
- 正式数据与审计：`paper/v3_formal/`；
- 正式论文图：`figures/v3_formal/`；
- 完整 evidence：`artifacts/v3-symmetry-formal-evidence.tar.gz`；
- 方法协议：`docs/V3-SYMMETRY-CORRECTION-PROTOCOL.zh-CN.md`；
- 复现实验：`docs/RUNBOOK.md`。

正式 evidence SHA-256：
`108a4b042549ead58f7b13f42b6ace4685e93a4e8a54e9563b044c03c29ad78c`。

## 旧内容状态

旧 P2/Q3 论文、图表和数字全部是 `SUPERSEDED_V2_HISTORICAL_ONLY`，禁止投稿或与 V3
数值混合。旧证据只为解释审计历史而保留。

# 当前研究状态

更新日期：2026-08-25

## 一句话结论

当前课题是用无标签神经网络求解二维参数化 Bloch–Schrödinger 本征 PDE 的最低 rank-2
谱簇。最终 P2 full-shell 基底不变神经增强 Rayleigh–Ritz 已通过独立 pilot 和唯一一次
640 点 frozen final，状态为 **`P2_FROZEN_FINAL_GO`**。新的160点期刊基线 supplement
也已完成，状态为 **`Q3_SUPPLEMENT_GO`**。两套证据均已回传本地并独立审计，远端 GPU
已经关机。当前不需要继续租 GPU，也不得重跑 final 或修改 supplement 门槛。

## 方法

1. 3 层、宽度 64 的 SiLU MLP 以周期坐标、Bloch 波矢和势参数为输入；
2. 通过 physical anchor 与 generalized-trace 目标，无标签预测 rank-2 神经粗子空间；
3. 推理时加入完整二阶六角 Fourier shell 的 19 个解析模式；
4. 只对两个神经列使用自动微分，Fourier Hamiltonian 解析装配；
5. 同步正交化 `(W, HW)`，在约 21 维空间内提取最低两个 Ritz 向量。

该方法是混合 neural eigensolver。它属于神经网络求解二维 PDE 本征问题，但不是普通
residual PINN，也不是纯 Fourier 谱方法。

## 阶段进展

| 阶段 | 状态 | 结论 |
|---|---|---|
| P5 low-frequency ROM | STOP | 不敌等成本 long-anchor，gap-scan 回退 |
| P0 risk detectability | GO | 失效风险可检测，但不是最终求解器 |
| P1 risk routing | STOP | 无法突破两个端点子空间的精度上限 |
| P2 outer-shell probe | STOP | near 有效，gap/效率门槛失败 |
| P2 full-shell independent pilot | GO | 96 点 × 2 势族 × 3 seeds，全门槛通过 |
| P2 frozen final | **GO** | 640 点、10 方法、3 seeds、19,200 行、审计通过 |
| 中英文论文初稿 | **完成 v0.1** | 进入引用、理论和最近邻补强 |
| SCI-Q3 supplement | **GO** | 160点、2势族、3 seeds、3方法、1440行、双重审计 |

## 最终主结果

| 方法 | Overall | Near | Gap-scan |
|---|---:|---:|---:|
| Long anchor | 0.14719 | 0.08924 | 0.15938 |
| Neural + shell 1 | 0.06172 | 0.04513 | 0.05768 |
| **P2 full shell** | **0.04532** | **0.03903** | **0.04389** |
| Fourier-only rank 21 | 0.13697 | 0.12249 | 0.13700 |

- overall 改善 69.19%，95% CI `[67.66%, 70.75%]`；
- near 改善 56.28%，95% CI `[53.24%, 59.22%]`；
- harmonic/Gaussian 两势族均改善，family×seed 为 6/6 获胜；
- 三 seed 标准差 0.00137；最大正交误差 `3.12e-7`；
- P2 mean/p95 为 107.81/121.90 ms，同服务器 CPU PWE 为 313.44 ms。

完整数值与证据见 [CORE_RESULTS.zh-CN.md](../paper/p2_final/CORE_RESULTS.zh-CN.md)。

## 独立 Q3 supplement

| 方法 | Overall | Near | Gap-scan | Strict-OOD |
|---|---:|---:|---:|---:|
| **P2 full-shell** | **0.04728** | **0.03804** | **0.06727** | **0.05796** |
| Wang–Xie trace adapted | 0.13114 | 0.09056 | 0.15110 | 0.21776 |
| Dai Galerkin adapted | 0.43367 | 0.42376 | 0.47148 | 0.43758 |

- P2 对 Wang–Xie 适配改善63.78%，95% CI `[59.58%, 67.88%]`；
- P2 对 Dai 适配改善89.08%，95% CI `[88.10%, 90.01%]`；
- 对两个基线均为6/6 family×seed获胜；
- 最大正交误差 `2.95e-7`；
- 证据 SHA-256：`282cdd418eaa11a68498ee7fbc0198dfc1f362a535385756a7cc38275806afe0`。

两个基线是统一 Bloch 框架中的公式级适配，不是作者官方代码结果。Dai 适配收敛较差，
不能由此推断 Dai 原论文方法无效。详细见
[Q3_SUPPLEMENT_REPORT.zh-CN.md](../paper/p2_final/Q3_SUPPLEMENT_REPORT.zh-CN.md)。

## 投稿判断

- SCI 四区：实验基础已经充分，进入论文定稿；
- SCI 三区：实验竞争力明显增强，当前重点转为 external-gap/Ritz 理论说明、FLOPs、
  成本摊销和谨慎表述适配基线；
- 创新强度：实验组合创新中等偏强，纯数学原创性中等；
- 现阶段不能写“已优于所有期刊方法”；
- Frozen final 永久关闭。

## 当前文件入口

- 中文初稿：`paper/p2_final/MANUSCRIPT.zh-CN.md`；
- 英文初稿：`paper/p2_final/MANUSCRIPT.en.md`；
- 核心数据：`paper/p2_final/CORE_RESULTS.zh-CN.md`；
- Q3 supplement：`paper/p2_final/Q3_SUPPLEMENT_REPORT.zh-CN.md`；
- 投稿缺口：`docs/KNOWN_GAPS.zh-CN.md`；
- 运行手册：`docs/RUNBOOK.md`；
- 论文图表：`figures/p2_final/`。

# P2 核心数据与证据索引

更新日期：2026-08-25
状态：`P2_FROZEN_FINAL_GO`
用途：论文写作、表格复核、图表生成与后续 AI 交接的唯一数值摘要。

## 1. 研究对象

本文使用无标签 anchored generalized-trace SiLU MLP 预测二维参数化
Bloch–Schrödinger 本征 PDE 的最低 rank-2 神经粗子空间，再加入完整二阶六角
Fourier shell，通过基底不变的 Rayleigh–Ritz 提取最低谱簇。

网络输入为周期坐标特征、Bloch 波矢与势参数，输出为两个复值周期函数。正式网络为
3 个隐藏层、每层 64 个神经元的 SiLU MLP。harmonic/Gaussian 两个势族的可训练参数量
分别为 9,156 和 9,220。P2 推理阶段不增加可训练参数。

## 2. Frozen-final 协议

| 项目 | 固定值 |
|---|---|
| 参数点 | 640 |
| 势族 | harmonic honeycomb、Gaussian honeycomb |
| checkpoint seeds | 42、137、251 |
| 方法数 | 10 |
| 总评价行 | 19,200 |
| split | IID、exact-cluster、near-cluster、strict-OOD、gap-scan |
| 参考解 | cutoff-24、rank-3、33×33 网格、float64 PWE |
| 主指标 | rank-2 projector sine error，越低越好 |
| 统计 | 2,000 次参数点聚类 bootstrap |
| 设备 | NVIDIA RTX 5090 D 32 GB |
| 软件 | Python 3.12.3、PyTorch 2.8.0+cu128、CUDA 12.8 |
| final 代码提交 | `7748db2a7cb08e847b6f6fb3e2d3bcd33c7ec64d` |

## 3. 主结果

| 方法 | Overall | IID | Exact | Near | Strict-OOD | Gap-scan |
|---|---:|---:|---:|---:|---:|---:|
| Unanchored trace | 0.197840 | 0.184430 | 0.160144 | 0.145890 | 0.268291 | 0.218302 |
| Anchor | 0.156499 | 0.151346 | 0.116099 | 0.105050 | 0.251878 | 0.140497 |
| Wide anchor | 0.152430 | 0.145830 | 0.112747 | 0.100202 | 0.235720 | 0.151109 |
| Long anchor | 0.147194 | 0.138047 | 0.102156 | 0.089237 | 0.229212 | 0.159375 |
| Static low-ROM | 0.150536 | 0.142716 | 0.108925 | 0.095420 | 0.239263 | 0.149463 |
| High-frequency ROM | 0.155313 | 0.148600 | 0.113976 | 0.102992 | 0.245599 | 0.148088 |
| Neural + shell 1 | 0.061720 | 0.059602 | 0.048432 | 0.045129 | 0.092170 | 0.057684 |
| Neural + outer shell 2 | 0.134104 | 0.124099 | 0.087430 | 0.078490 | 0.205610 | 0.156557 |
| **P2 full shell** | **0.045324** | **0.043825** | **0.042204** | **0.039034** | **0.056853** | **0.043892** |
| Fourier-only rank 21 | 0.136965 | 0.133674 | 0.132877 | 0.122489 | 0.158386 | 0.136998 |

## 4. 稳定性、统计与效率

- P2 相对 long-anchor 的 overall 改善：69.1885%，95% CI `[67.6623%, 70.7539%]`；
- near 改善：56.2755%，95% CI `[53.2356%, 59.2233%]`；
- 三 seed overall：`0.0438389 / 0.0455909 / 0.0465407`；
- seed 标准差：`0.0013706`；
- harmonic near：P2 `0.0303657`，long-anchor `0.0650760`；
- Gaussian near：P2 `0.0477020`，long-anchor `0.1133979`；
- family×seed 配对：P2 赢 `6/6`；
- 最大正交误差：`3.123731762e-7`；
- P2 production mean/p95：`107.8147 / 121.9050 ms`；
- 同服务器 cutoff-24 CPU PWE mean：`313.4410 ms`；
- P2/PWE 时间比：`0.344`。

效率数据来自独立 pilot 的 10 次 warmup + 100 次重复计时。GPU P2 与 CPU PWE 是系统级
对照，不应写成同硬件内核的纯算法加速比。

## 5. 消融能支持的结论

1. P2 的收益不能由“更多 Fourier 模态”单独解释：同为约 21 维，Fourier-only overall
   为 `0.136965`，P2 为 `0.045324`。
2. 完整壳层比只用外二阶壳层更有效：`0.045324` 对 `0.134104`。
3. P2、shell 1 与 full shell 复用同一 long-anchor checkpoint，提升不是更多训练步数造成。
4. 低频 ROM 已由 P5 判定为 STOP，不能作为论文主创新。

## 6. 权威证据

| 证据 | SHA-256 / 状态 |
|---|---|
| P5 evidence | `56891c5740eb94c62299b72869d790a1cbdee6abda3fae2903ed822f5e405101` |
| P0 evidence | `d5783e65e7c55149206757505bae922193b5315b5596b6324fe0f8f07c2ed81d` |
| P2 pilot evidence | `0c49461a6c780840ca678582019cc433df5741fd62ef546dcde7e964b71c071b` |
| final suite | `b8658e7512a829018b0c6cc754b7d9e7fb55c4e41c852dfa84a2ff606a5e161c` |
| final reference | `8969794607c3d82b2636eac518a49087407f9b8c0ce3fb3c037adf395673448d` |
| final evidence | `c653d0eddab018741312741f6db46f023a20812306d574b66947bbb42af25095` |
| final audit | 31 个 manifest 文件全部通过；本地重算差值 0 |

原始结果入口：

- `results/remote_5090_p2_final_go/results/p2_final/rows.csv`；
- `results/remote_5090_p2_final_go/results/p2_final/summary.json`；
- `results/remote_5090_p2_final_go/results/p2_final/gate.json`；
- `paper/p2_final/tables/method_summary.csv`；
- `paper/p2_final/tables/split_summary.csv`。

## 7. 写作边界

- 可以写：该方法在当前冻结 benchmark 上显著优于本文实现的九个控制/基线。
- 可以写：在新的160点独立 supplement 上，P2 稳定优于统一 Bloch 框架中的
  Wang–Xie trace 与 Dai Galerkin 公式级适配。
- 不可以写：P2 已优于作者官方实现或所有期刊方法；两者不是作者代码直接运行结果。
- 可以写：P2 比同服务器 CPU cutoff-24 PWE 更快。
- 不可以写：P2 比 PWE 更准确；PWE 是参考解。
- 可以写：这是神经网络求解二维 PDE 本征谱簇的混合求解器。
- 不可以写：Rayleigh–Ritz、Galerkin、Fourier shell 或 Ky Fan 是本文首次提出。
- frozen final 永久关闭，不再筛 checkpoint、改门槛或调参数。

## 8. SCI-Q3 独立 supplement

### 8.1 主结果

| 方法 | Overall | IID | Exact | Near | Strict-OOD | Gap-scan |
|---|---:|---:|---:|---:|---:|---:|
| **P2 full-shell** | **0.04728** | **0.04533** | **0.04239** | **0.03804** | **0.05796** | **0.06727** |
| Wang–Xie adapted | 0.13114 | 0.13243 | 0.09410 | 0.09056 | 0.21776 | 0.15110 |
| Dai adapted | 0.43367 | 0.43112 | 0.42827 | 0.42376 | 0.43758 | 0.47148 |

- 160点、两个势族、3 seeds、3方法、1440行；
- P2 vs Wang–Xie：改善63.78%，95% CI `[59.58%, 67.88%]`；
- P2 vs Dai：改善89.08%，95% CI `[88.10%, 90.01%]`；
- 对两个基线均为6/6 family×seed获胜；
- 最大正交误差 `2.95e-7`；
- evidence SHA-256：`282cdd418eaa11a68498ee7fbc0198dfc1f362a535385756a7cc38275806afe0`；
- 远端与本地 audit 均 PASS。

### 8.2 效率

| 方法 | 参数量 harmonic / Gaussian | mean latency | p95 |
|---|---:|---:|---:|
| P2 | 9,156 / 9,220 | 193.75 ms | 209.01 ms |
| Wang–Xie adapted | 9,156 / 9,220 | 2.47 ms | 2.68 ms |
| Dai adapted | 9,676 / 9,740 | 205.56 ms | 230.18 ms |

Wang–Xie 适配速度最快但精度较低。P2 与 Dai 适配延迟接近，P2 精度更高。Dai 适配训练
收敛不佳，应作为透明负结果而不是对 Dai 原论文的否定。

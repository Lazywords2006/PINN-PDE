# 当前研究状态（2026-08-24）

## 一句话结论

课题是“神经网络求解二维 Bloch–Schrödinger 本征 PDE 的 rank-2 谱簇”，没有跑题。
经过 P5、P0、P1 和 P2 多轮机制筛选，当前主方法已经切换为 **P2 full-shell
基底不变神经增强 Rayleigh–Ritz 求解器**。独立 pilot 和唯一一次 640 点 frozen final
均为 GO，最终证据已回传本地并独立重算。

## 阶段状态

| 阶段 | 状态 | 含义 |
|---|---|---|
| P5 low-ROM | `P5_PROMOTION_STOP` | 不敌 long-anchor，gap 回退 |
| P0 risk detectability | `RISK_DEVELOPMENT_GO` | 风险可检测，但不是最终方法 |
| P1 risk routing | `P1_PILOT_STOP` | 总体更安全，但无法突破端点子空间上限 |
| P2 outer-shell probe | `STOP` | near 改善，gap/效率未过冻结门槛 |
| P2 full-shell independent pilot | **GO** | 96 点 × 3 seeds，全门槛通过 |
| P2 640-point frozen final | **GO** | 10 方法、19,200 行、bootstrap 与审计通过 |
| 当前投稿 | **进入论文准备** | 禁止再调 final；补写作、最近邻对照和理论说明 |

## 当前网络与 PDE

### PDE

\[
\left[
\tfrac12(-i\nabla+\mathbf{k})^T G(-i\nabla+\mathbf{k})
+V_\mu(\mathbf{x})
\right]u_j=E_j u_j,
\quad \mathbf{x}\in[0,2\pi)^2,
\]

周期边界，harmonic/Gaussian honeycomb 两个势族。目标是最低 rank-2 谱投影，而不是给
交叉处的两条本征函数强行编号。

### 神经网络与最终求解器

1. anchored generalized-trace SiLU MLP 无标签预测 rank-2 神经粗子空间；
2. 加入完整二阶六角 Fourier shell（19 个解析模式）；
3. 只对2个神经列使用自动微分，Fourier Hamiltonian 解析装配；
4. 对 \((W,HW)\) 同步正交化并做21维小型 Rayleigh–Ritz；
5. 输出最低 rank-2 谱簇。

P2 是混合神经数值 eigensolver，不应写成普通 residual PINN，也不能把 Rayleigh–Ritz、
Galerkin 或 Fourier 基本身写成发明。

## Frozen-final 主结果

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

P2 full-shell 相对 long-anchor：

- overall 改善 69.19%，点级 bootstrap 95% CI `[67.66%, 70.75%]`；
- near 改善 56.28%，95% CI `[53.24%, 59.22%]`；
- harmonic/Gaussian near 均改善；
- 6/6 family×seed 配对获胜；
- 最大正交误差 `3.12e-7`；
- 三 seed 总体均值 `0.04384 / 0.04559 / 0.04654`，标准差 `0.00137`。

## 分区结果

P2 full-shell：

- IID：0.04383；
- exact-cluster：0.04220；
- near-cluster：0.03903；
- strict-OOD：0.05685；
- gap-scan：0.04389。

优势不是只来自 crossing 点。Fourier-only rank 21 为 0.13697，证明神经粗子空间是关键，
不是简单增加21个 Fourier 模态。

## 效率

RTX 5090 D、10 warmups + 100 repeats：

- P2 mean 107.81 ms；
- P2 p95 121.90 ms；
- 同服务器 cutoff-24 CPU PWE mean 313.44 ms；
- P2/PWE 0.344。

单神经 forward 仍更快，因此应报告 accuracy–latency Pareto，不应声称 P2 是零成本校正。

## 证据与复现

- P5 evidence：`56891c5740eb94c62299b72869d790a1cbdee6abda3fae2903ed822f5e405101`；
- P0 evidence：`d5783e65e7c55149206757505bae922193b5315b5596b6324fe0f8f07c2ed81d`；
- P2 pilot evidence：`0c49461a6c780840ca678582019cc433df5741fd62ef546dcde7e964b71c071b`；
- frozen-final suite：`b8658e7512a829018b0c6cc754b7d9e7fb55c4e41c852dfa84a2ff606a5e161c`；
- frozen-final reference：`8969794607c3d82b2636eac518a49087407f9b8c0ce3fb3c037adf395673448d`；
- frozen-final evidence：`c653d0eddab018741312741f6db46f023a20812306d574b66947bbb42af25095`；
- final commit：`7748db2a7cb08e847b6f6fb3e2d3bcd33c7ec64d`；
- final evidence audit：31 文件 PASS；
- 本地独立重算：所有 gate 相等，核心指标差值 0。

完整报告见
[paper/p2_final/P2_FINAL_EXPERIMENT_REPORT.zh-CN.md](../paper/p2_final/P2_FINAL_EXPERIMENT_REPORT.zh-CN.md)。

## 投稿判断

- 神经网络解真实二维 PDE：是；
- 当前方法 final：GO；
- SCI 四区：已经具备合理投稿基础；
- SCI 三区：有机会，但建议补最近邻 neural-subspace Galerkin 直接对照或理论误差说明；
- 创新强度：组合创新中等偏强，数学理论原创性中等；
- 是否继续跑 frozen final：禁止；
- 当前下一步：相关工作查重、方法图、论文初稿、代码复现说明和投稿选择。

## 仍需补充但不允许使用 final 调参的内容

1. 与最接近期刊 neural-subspace + Galerkin 方法作实现级对照；
2. 参数量、FLOPs、训练摊销与 break-even 表；
3. 外部谱隙和 Ritz 子空间误差的理论命题/讨论；
4. 可选第三势族或不同晶格的非 final 泛化实验；
5. 公开代码、配置、环境和小型复现缓存。

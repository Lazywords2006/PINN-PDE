# 当前研究状态、P4 深度审计与 P5 决策（2026-08-01）

## 先说人话

本课题没有跑题：它确实用神经网络求解二维 Bloch–Schrödinger 本征 PDE。当前最重要
的发现是，原先准备作为主创新的“物理 anchor”有效，但一个加入低频 Fourier ROM 的
版本更好。因此论文不能按原方案直接投稿，需要先证明 ROM 的优势来自物理结构，而
不是来自多了参数或训练更久。

结论分为三层：

1. **工程层：通过。** 代码、缓存、断点、指标、证据包和 MPS/ROCm 兼容路径可运行。
2. **研究层：可以继续。** P4 给出了稳定正向信号，并指出了更有潜力的候选机制。
3. **投稿层：暂时不通过。** 还缺 P5 归因、独立 final、近期外部基线和论文图表。

## 网络与方程

### 方程

\[
\mathcal H_{\mathbf k,\mu}u_j =
\left[\frac12(-i\nabla+\mathbf k)^T G(-i\nabla+\mathbf k)
+V_\mu(\mathbf x)\right]u_j=E_j u_j,
\quad \mathbf x\in[0,2\pi)^2.
\]

边界为二维周期边界。参数包含 Bloch 波矢与势函数的振幅、宽度或对称性破缺参数。
当前有 harmonic honeycomb 和 Gaussian honeycomb 两个势族。

### 网络

当前候选名为 **A-GTROMNet**：周期坐标 SiLU MLP + 物理低能 anchor + 七模态低频
Fourier ROM。网络一次输出两个复值周期函数，代表 rank-2 谱簇。训练最小化无标签
generalized-trace 目标 `Tr(B⁻¹A)`，PWE 参考解不进入训练。

### 为什么它属于神经网络解 PDE

神经网络直接表示 PDE 的两个未知函数；Hamiltonian 中的一阶和二阶空间导数由自动
微分计算；势能和 Bloch 协变导数进入训练损失。它不是监督式代理模型。因为目标是
算子的本征子空间，它属于 neural PDE eigensolver，而不是普通时变初边值 PINN。

## P4 证据审计

### 真实性

- 权威包：`artifacts/p4-evidence-20260801-080059.tar.gz`。
- 30/30 个 run 完成，0 failure。
- manifest 共列出 231 个文件；文件存在性、字节数和 SHA-256 全部匹配。
- 训练发生在 AMD MI300X / ROCm；冻结 validation，3 个 seed，2 个势族。
- frozen final 没有运行。

### 原始结果重算

| 方法 | near-cluster 投影误差 | 相对 G1 | 参数量（harmonic/Gaussian） | 平均训练时间 |
|---|---:|---:|---:|---:|
| G0 无 anchor | 0.16870 | — | 9,156 / 9,220 | 约 31 秒量级 |
| G1 anchor | 0.12323 | 基准 | 9,156 / 9,220 | 31.25 秒 |
| G2 静态低频 ROM | **0.11018** | **改善 10.58%** | 11,300 / 11,397 | 41.54 秒 |
| G3 退火 ROM | 0.13012 | 退化 | 与 G2 同级 | — |
| 历史 P3 | 0.49444 | 明显更差 | — | — |

G1 对 G0 的总体改善为 26.95%，两个势族分别改善 25.12% 和 28.05%，6/6 个
seed×势族配对都为正向。G2 对 G1 在 5/6 个配对中更好。

### 为什么 P4 必须 STOP

冻结门槛要求 G1 与最佳 ROM 扩展相差不超过 2%，但 G2 比 G1 好 10.58%。因此只有
“G1 单独做主方法”的路线被停止。这个 STOP 是有效的科学结论，不能改门槛或挑 best
checkpoint 把它改成 GO。

### G2 还不能直接写成创新

G2 比 G1 多约 23–24% 参数、慢约 33%。在 exact、near-cluster、IID 和 strict OOD
上更好，但在 `gap_scan` 上平均退化约 6.47%；逐点只在 117/192 个点更好。因此目前
无法区分三种解释：

- 低频 Fourier 结构真的更适合该 PDE；
- 只是参数更多；
- 只是训练计算更多或某些 seed 偶然更好。

这就是 P5 必须存在的原因。

## 已修复的证据门控风险

首个 P4 包 `p4-evidence-20260801-043302.tar.gz` 中，30/30 次运行都因远端 PyTorch
缺少 CPU LAPACK 而失败，但 ROCm 构建又把进程退出码错误地变成 0，旧 executor 因此
一度误报 GO。

现在 executor 同时检查：

- `summary.json` 的期望 run 数、完成数和失败数；
- `diagnostic_gate.json` 的真实布尔门槛；
- 参考缓存 SHA-256；
- 证据 manifest 中的源代码、结果和哈希。

Gram 条件数计算也按后端分流：ROCm/CUDA 留在 GPU，MPS 转到 CPU。P5 本地 MPS
烟测已经 12/12 通过，防止同一缺陷再次出现。

## 冻结的 P5 创新归因实验

### 实验矩阵

共 6 方法 × 2 势族 × 3 seeds = 36 次 validation 训练：

| 方法 | 要排除的解释 |
|---|---|
| `p5_anchor` | 原始 G1 基线 |
| `p5_static_low_rom` | 候选机制 |
| `p5_wide_anchor` | 同参数量但无 ROM，排除容量效应 |
| `p5_long_anchor` | 延长训练，排除计算预算效应 |
| `p5_unanchored_low_rom` | 去掉 anchor，检验二者是否协同 |
| `p5_highfreq_rom` | 相同参数和模态数但使用高频模式，排除“任意 ROM 都有效” |

### 冻结成功线

候选方法必须：

- 36/36 完成，正交误差 `<1e-4`，Gram 条件数 `<1e8`；
- 相对每个控制总体至少改善 5%；
- 对每个控制在两个势族都更好；
- 对每个控制至少 5/6 个 seed×势族配对获胜；
- 与宽网络参数量差不超过 2%，与长训练时间差不超过 15%；
- 相对基础 anchor 参数增幅不超过 30%、时间增幅不超过 50%；
- `gap_scan` 误差不得超过最佳无 ROM 控制的 102%。

`mechanism_go=true` 只代表低频结构归因成立；最终必须同时
`gap_scan_non_regression=true` 才能得到 `promotion_go=true`。

### 已完成的小范围验证

2026-08-01 在 Apple MPS 上执行 12 个 5-step 工程烟测：

- 12/12 完成；
- orthogonality pass；
- Gram condition pass；
- `P5_EXECUTION_STATUS=SMOKE_PASS`。

这只证明代码可运行，不代表方法精度有效。正式 36-run 结果仍为**未运行**。

## P5 后三种可能结论

### A. `P5_PROMOTION_GO`

低频结构归因和 gap 安全同时通过。下一步才允许设计一次性 frozen-final 评估，补外部
期刊基线、效率表、误差图、消融图和统计检验。此时 SCI 四区有条件可行，三区仍需
更强理论或跨 PDE 证据。

### B. `mechanism_go=true` 但 `promotion_go=false`

说明 ROM 机制有效，但谱隙附近风险仍不安全。下一步应设计不读取真实标签的谱隙风险
守门或局部校正，继续只用 validation；不能打开 final。

### C. `mechanism_go=false`

说明提升可以被容量、计算或错误频率控制解释，不能把 ROM 写成创新。应停止该主张，
回到更明确的守恒、谱隙感知或子空间几何机制，而不是继续堆模块。

## 当前投稿判断

| 问题 | 当前答案 |
|---|---|
| 是否可以继续 | 可以，P4 提供了稳定信号和明确下一步 |
| 是否可以现在投稿 | 不可以 |
| SCI 四区 | P5 GO + final + 外部基线后有条件可行 |
| SCI 三区 | 当前证据不足 |
| 创新强度 | 当前为中等候选，未完成归因 |
| 最大审稿风险 | ROM 是容量效应；只做一个 PDE 家族；gap-scan 退化；缺外部近期基线 |
| 是否需要多卡 | 不需要，单卡足够 |

## 远端执行资源

- 推荐：单张 RTX 4090/5090 或 MI300X。
- 最低可复现：单张 RTX 4060 8 GB；模型小但运行更慢。
- CPU：12 核已经足够做数据调度；不是瓶颈。
- 内存：32 GB 足够；显存 8 GB 足够，24–32 GB 更宽松。
- 预计 P5 正式矩阵：强卡约 20–40 分钟，4060 约 1–3 小时；以真实日志为准。

## 下一步唯一动作

在干净的 Git `main` 上运行：

```bash
python scripts/run_p5_executor.py --device auto
```

然后回传：

- `artifacts/p5-evidence-*.tar.gz`；
- 对应 `.sha256`；
- 完整终端日志；
- 最后打印的 `P5_EXECUTION_STATUS`。

不要运行 `evaluate_v2_final.py`，不要改 seed、步数、门槛或输出目录。

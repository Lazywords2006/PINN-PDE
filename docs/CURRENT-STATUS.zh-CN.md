# 当前研究状态、P5 报告与证据门禁（2026-08-01）

## 最先看这一段

本课题没有跑题：它使用神经网络求解二维参数化 Bloch–Schrödinger 本征 PDE 的
rank-2 谱簇。但当前方法还不能投稿。

远端执行机已经报告 P5 36-run 完成且判定 `P5_PROMOTION_STOP`。报告中的数字在逻辑和
算术上自洽，但权威证据包 `p5-evidence-20260801-092048.tar.gz`、sidecar、36 个
`result.json` 和原始 CSV 没有随 GitHub 提交上传。主控因此不能按要求独立重算。

当前状态必须分开写：

- **P4：独立核验完成，结论可信。**
- **P5：远端报告完成，主控审计 BLOCKED。**
- **frozen final：未打开。**
- **论文：不可投稿。**
- **下一动作：上传既有 P5 证据，不重跑、不设计 P6。**

## 到底用了什么网络、解了什么方程

求解对象为

\[
\left[\frac12(-i\nabla+\mathbf k)^TG(-i\nabla+\mathbf k)
+V_\mu(\mathbf x)\right]u_j=E_j u_j,
\qquad \mathbf x\in[0,2\pi)^2,
\]

并满足二维周期边界条件。网络接收二维坐标、Bloch 波矢和势参数，输出两个复值周期
函数所张成的 rank-2 子空间。空间导数由自动微分计算，训练不读取 PWE 本征函数标签。
因此它属于无标签变分式 neural PDE eigensolver，不是监督代理模型。

P5 检验的 A-GTROMNet 为周期特征 SiLU MLP + 物理低能 anchor + 七个低频 Fourier ROM
模态，损失为 generalized trace `Tr(B⁻¹A)`。注意：这是“被检验的候选”，不是已获
支持的最终方法。

## 已独立核验的 P4

权威包 `artifacts/p4-evidence-20260801-080059.tar.gz` 已完成外层 SHA、231 个 manifest
文件和 30 个 run 的独立重算：

| 方法 | near-cluster 投影误差 | 结论 |
|---|---:|---|
| G0 generalized trace | 0.16870 | 无 anchor 基线 |
| G1 anchor | 0.12323 | 相对 G0 改善 26.95%，6/6 配对正向 |
| G2 static low ROM | **0.11018** | 比 G1 再好 10.58%，但参数和计算更多 |
| G3 annealed ROM | 0.13012 | 不如静态 ROM |
| 历史 P3 | 0.49444 | 明显落后 |

P4 的 STOP 只否定“G1 已经足够成为主方法”，并指出必须用 P5 排除容量和计算预算效应。

## P5 远端报告：目前能说什么

以下来自 commit `38af315` 的执行报告，**尚未由主控从原始 run 重算**：

| 方法 | 报告 near-cluster | 报告 gap-scan |
|---|---:|---:|
| `p5_static_low_rom` | 0.11018 | 0.14920 |
| `p5_anchor` | 0.12323 | **0.14013** |
| `p5_wide_anchor` | 0.11910 | 0.15098 |
| `p5_long_anchor` | **0.10616** | 0.15930 |
| `p5_unanchored_low_rom` | 0.17171 | 0.21828 |
| `p5_highfreq_rom` | 0.12110 | 0.14783 |

报告同时声称：36/36 完成、0 失败、最大正交误差约 `3.4e-7`、最大 Gram 条件数约
11.0、`mechanism_go=false`、`gap_scan_non_regression=false`、
`promotion_go=false`。

### 报告在算术上是否自洽

是：

- ROM 候选 0.11018 没有优于长训练 anchor 的 0.10616，更不可能“比所有控制至少好
  5%”；
- ROM 候选 gap-scan 0.14920 大于 `1.02 × 0.14013 = 0.14293`；
- 因此两个关键门槛都应为 false，最终 STOP 与表中数字一致。

但“自洽”不等于“独立核验”。没有原始包就无法检查是否漏 run、抄错 summary、选错
checkpoint、CSV 与 JSON 是否一致或 manifest 是否被改动。

## 为什么现在不能把 `p5_long_anchor` 升为新方法

不能，理由有三条：

1. 它只是同一个 anchor 网络训练 665 步，不是新网络或新机制；增加训练预算不能作为
   期刊论文核心创新。
2. 虽然报告的 near-cluster 误差为全场最低 0.10616，但 gap-scan 为 0.15930，比基础
   anchor 的 0.14013 高约 13.7%。它不是整体最优方法。
3. 它最重要的作用是成为强计算预算基线，并证明静态 ROM 的 near-cluster 提升不能与
   “训练更久”区分。

因此 long anchor 应保留为后续论文的强基线，不应改名包装成新方法。

## ROM 是否继续作为主创新

如果原始证据重算后仍得到同样门槛，应放弃“低频 ROM 是主创新”的论文主张：

- 机制归因没有通过；
- gap-scan 安全没有通过；
- 参数和训练时间均增加；
- 高风险区域不存在稳定优势。

ROM 仍可作为负结果、消融或后续局部模块保留，但不能主导标题、摘要和贡献列表。

## 是否马上设计 P6

暂时不设计。P6 的选择依赖 36 个 run 的逐点数据：需要先检查退化集中在哪个势族、
seed、参数区域以及是否与参考外部谱隙、PDE residual 或 Gram 条件数相关。现在只有六个
聚合均值，无法判断应该做谱隙风险守门、课程学习、动态计算分配还是彻底换路线。

在证据通过后，下一阶段应按以下顺序：

1. 画出每个方法的逐点 near/gap 误差与配对差；
2. 检查误差与参考外部谱隙、参数位置、势族和 seed 的相关性；
3. 确认是否存在可由**无标签量**检测的失败区域；
4. 先检索相近的谱隙感知/风险守门期刊方法，再冻结一个新机制；
5. 用新的 validation 协议验证，仍不打开 frozen final。

## 新增的独立证据审计器

仓库新增 `scripts/audit_p5_evidence.py`。收到包后执行：

```bash
python scripts/audit_p5_evidence.py \
  artifacts/p5-evidence-20260801-092048.tar.gz \
  --sidecar artifacts/p5-evidence-20260801-092048.tar.gz.sha256
```

它会：

- 核对外层 SHA-256 sidecar；
- 拒绝重复或不安全的 tar 路径；
- 对 manifest 中每个文件重算字节数和 SHA-256；
- 验证 6 方法 × 2 势族 × 3 seeds 的 36-run 身份矩阵；
- 逐 run 核对 `final.pt` 哈希以及 `metrics.csv` 的行数、分组均值和稳定性指标；
- 从每个 `result.json` 重算两类误差、训练时间、参数量、配对胜率和完整 gate；
- 将重算结果与原 summary、gate 和 execution status 对照；
- 只有全部一致才输出 `audit_pass=true`。

## 投稿判断

| 问题 | 当前答案 |
|---|---|
| 是否属于神经网络解 PDE | 是，且为真实二维本征 PDE |
| 是否可以继续 | 可以，但先补证据完整性 |
| 是否可以现在投稿 | 不可以 |
| P5 是否已独立核验 | 没有，证据包缺失 |
| `p5_long_anchor` 是否为创新 | 不是，只是更强训练预算基线 |
| ROM 是否可做主创新 | 若报告经核验成立，则不可以 |
| SCI 四区 | 目前仍未达到 |
| SCI 三区 | 当前明显不足 |
| frozen final | 保持关闭 |

## 下一步唯一动作

让原远端执行机上传现有的：

- `artifacts/p5-evidence-20260801-092048.tar.gz`；
- `artifacts/p5-evidence-20260801-092048.tar.gz.sha256`。

不要重跑 P5，不要启动 P6，不要运行 `evaluate_v2_final.py`。上传后由主控运行审计器，
再决定下一实验。

# 当前研究状态与投稿判断（2026-08-01，P5 独立审计后）

## 一句话结论

课题没有跑题：本项目确实使用神经网络求解二维参数化 Bloch–Schrödinger 本征 PDE
的 rank-2 谱簇。P5 权威原始证据已经回传并通过独立审计，但科学结论是
**`P5_PROMOTION_STOP`**。当前“低频 ROM 是主创新”的路线应停止；整个神经 PDE 课题
仍可继续，但需要先验证新的失效感知或条件校正机制。目前不能投稿，也不能打开 frozen
final。

## 网络与 PDE

求解对象为

\[
\left[\frac12(-i\nabla+\mathbf k)^TG(-i\nabla+\mathbf k)
+V_\mu(\mathbf x)\right]u_j=E_j u_j,
\qquad \mathbf x\in[0,2\pi)^2,
\]

并满足二维周期边界条件。网络接收二维坐标、Bloch 波矢和势参数，输出两个复值周期
函数张成的 rank-2 子空间。空间导数由自动微分计算，训练不读取 PWE 本征函数标签。
因此它是无标签变分式 neural PDE eigensolver，不是监督代理模型。

P5 检验的 A-GTROMNet 为周期特征 SiLU MLP + 物理低能 anchor + 七个低频 Fourier ROM
模态，损失为 generalized trace `Tr(B⁻¹A)`。P5 已证明它不能作为当前最终方法。

## 当前阶段状态

- **P4：**30-run 权威证据独立核验完成，结论 `PROMOTION_STOP`。
- **P5：**36-run 权威证据独立核验完成，`audit_pass=true`，结论
  `P5_PROMOTION_STOP`。
- **工程：**36/36 完成、0 失败，指标有限，正交与 Gram 稳定性通过。
- **frozen final：**未打开；STOP 状态下禁止运行。
- **论文：**当前方法不可投稿，课题可继续改进。

## P5 权威结果

证据包为 `artifacts/p5-evidence-20260801-092048.tar.gz`，SHA-256：
`56891c5740eb94c62299b72869d790a1cbdee6abda3fae2903ed822f5e405101`。

| 方法 | near-cluster 投影误差 | gap-scan 投影误差 | 作用 |
|---|---:|---:|---|
| `p5_static_low_rom` | 0.11018 | 0.14920 | 被检验候选 |
| `p5_anchor` | 0.12323 | **0.14013** | 基础 anchor |
| `p5_wide_anchor` | 0.11910 | 0.15098 | 参数量控制 |
| `p5_long_anchor` | **0.10616** | 0.15930 | 等算力控制 |
| `p5_unanchored_low_rom` | 0.17171 | 0.21828 | anchor 交互控制 |
| `p5_highfreq_rom` | 0.12110 | 0.14783 | 频率结构控制 |

冻结门槛重算结果：

- `candidate_at_least_5pct_better_than_each_control=false`；
- `candidate_better_in_each_family=false`；
- `at_least_5_of_6_pairs_win_each_control=false`；
- `gap_scan_non_regression=false`；
- `mechanism_go=false`；
- `promotion_go=false`。

## 结果到底说明什么

低频 ROM 相对普通 anchor 的 near-cluster 平均误差改善 10.58%，这个局部收益真实存在。
但是：

1. 等算力 long-anchor 的 near-cluster 误差 0.10616，优于候选的 0.11018；
2. 候选只在 3/6 个势族×seed 组合上胜过 long-anchor；
3. 候选 gap-scan 比最佳非 ROM anchor 差约 6.47%，超过 2% 安全容限；
4. 去掉 anchor 后误差大幅增至 0.17171，说明收益高度依赖 anchor；
5. 候选参数量增加约 23.6%，训练时间增加约 32.4%。

所以不能声称“低频 ROM 的物理结构带来了稳定、可归因的优势”。`p5_long_anchor` 也不能
升级为创新，因为它只是同一网络训练更久，并且 gap-scan 更差。

## 逐点分析发现了什么

每个 run 有 32 个 validation 点。候选与基础 anchor 严格配对后，在 192 个逐点比较中
胜 117 个（60.9%）；但 gap-scan 只胜 9/36，平均误差增加 0.00907。失败主要体现为
gap-scan 安全性，而不是程序整体失效。

候选与 anchor 的误差差对参考 external gap 的简单线性相关约 0.045，对 internal gap
约 −0.017。仅用真值谱隙的单阈值都不一定足够，更不能在推理时依赖不可获得的真值。
下一步必须构造可由网络输出和 PDE 本身计算的无标签风险量，并先验证 risk–coverage。

完整检查见 [P5 独立审计报告](P5-INDEPENDENT-AUDIT.zh-CN.md)。

## 下一步改进方向

最小可行的新方向是**失效感知的条件谱簇校正器**，不是继续无条件叠加 ROM：

1. 基础 anchor 网络生成主预测；
2. 计算无标签风险特征：PDE residual、Gram condition、预测 Ritz 外部间隔、chart 角度、
   多视图不一致；
3. 低风险点直接输出 anchor，候选高收益区域才启用局部校正；
4. 无法可靠判断或风险很高时回退到 PWE；
5. 用 risk–coverage、选择性误差、回退率和 many-query break-even 量化价值。

这个方向只有在小范围验测中证明“风险分数确实能优先找到失败点”后才值得写代码。若
风险排序接近随机，就停止条件路由，重新筛选方法，不直接进入 P6 大矩阵。

## 下一轮小范围验测成功线

- 两个势族、3 seeds、与当前 validation 隔离的新机制开发集；
- anchor、long-anchor、static-low-ROM 与新方法统一参数和 wall-clock 预算；
- near-cluster 相对 long-anchor 至少改善 5%；
- gap-scan 不超过最佳非 ROM 基线 2%；
- 每个势族均改善，至少 5/6 势族×seed 配对获胜；
- 风险排序 AUROC/AUPRC、risk–coverage 明显好于随机；
- 正交误差、Gram 条件数与有限性门槛继续通过；
- 只在上述条件同时满足时才允许冻结下一 promotion。

## 投稿判断

| 问题 | 当前答案 |
|---|---|
| 是否属于神经网络解 PDE | 是，真实二维本征 PDE |
| 当前结果是否可信 | 是，P4/P5 原始证据均独立审计 |
| 当前低频 ROM 能否投稿 | 不能，机制归因和安全门槛失败 |
| 整个课题是否继续 | 可以，但要更换主创新并先小测 |
| SCI 四区 | 当前未达到；新机制与完整实验通过后再评估 |
| SCI 三区 | 当前明显不足，需要更强机制、理论与物理用途 |
| 是否运行 frozen final | 不运行，保持关闭 |
| 是否需要再租多卡 | 不需要；单张 4060/4090/5090 足够开发与验证 |

## 当前允许与禁止的动作

允许：分析原始 validation、设计新开发集、做小型风险可检测性验测、补文献与理论。

禁止：修改旧门槛重跑 P5、挑 best checkpoint、把 validation 当 final、把 long-anchor
包装成创新、在 STOP 状态下运行 `evaluate_v2_final.py`。

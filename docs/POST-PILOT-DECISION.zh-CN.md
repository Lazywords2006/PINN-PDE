# 当前结果、A-GTNet 方案与投稿决策

更新时间：2026-07-30。

## 一句话先说清楚

本文使用一个**无标签、变分式的参数化神经网络 A-GTNet**，求解二维周期
Bloch–Schrödinger 偏微分方程的最低 rank-2 本征谱簇：

\[
\left[\tfrac12(-i\nabla+\mathbf{k})^T G(-i\nabla+\mathbf{k})
+V_{\mu}(\mathbf{x})\right]u_j=E_j u_j,
\qquad \mathbf{x}\in[0,2\pi)^2.
\]

网络不使用 PWE 本征函数作为训练标签，也不在 Dirac 简并点强行区分“第 1 条带”和
“第 2 条带”，而是直接学习两条带共同张成的二维谱子空间。因此这是真正的神经网络
PDE 本征求解，而不是普通监督回归，也不是把一维常微分方程包装成 PDE。

## 当前结果到底说明了什么

### 已经能确定的事实

- P3 multi-chart KyFan-PINN 的代码和验证协议能够运行；
- AMD 执行报告称 P3 的 24-run validation pilot 为 STOP，near-cluster 误差约为最佳
  generalized-trace 基线的 3.08 倍；
- 该次 AMD 原始 CSV、checkpoint 和证据压缩包未回收到仓库，所以具体数值只能称
  “执行者报告”，不能放进论文正式结果表；
- final 从未打开，避免了利用测试集继续调参，这是正确的实验纪律。

### 本地探索性诊断

在 Apple MPS 上用同一网络宽度、同一训练点、同一优化预算做过一次 200 步、seed 42
的开发探针。`near_cluster` 平均投影误差为：

| 方法 | 误差 | 解释 |
|---|---:|---|
| G0：纯 generalized trace | 0.126527 | 公平底座基线 |
| G1：G0 + 物理 anchor | **0.108527** | 相对 G0 改善约 14.2% |
| G2：G1 + 静态单图 ROM | 0.117777 | ROM 没有超过简单 anchor |
| G3：G1 + 退火单图 ROM | 0.113169 | 好于 G2，但仍没有超过 G1 |
| K3：历史 P3 | 0.401505 | 再次显示 hard MGS 路线优化困难 |

这只是**一个 seed 的开发探针**，不能作为论文实验，也没有达到预先设定的 15% 门槛。
它只支持一个下一步假设：应把最简单的 G1 作为候选主方法，而不是继续堆叠 ROM。

另一个 basis-invariant 自蒸馏探针使误差恶化到约 0.326，已经判为 STOP 并从正式实现
中删除。负结果保留在决策记录中，不再让执行机尝试。

## 当时未达预期的问题现在还存在吗

结论是：**工程和实验设计问题大部分已经处理，但核心精度问题尚未被正式实验解决。**
P3 的负结论不会因为换了方法而自动消失；A-GTNet 必须通过新的 30-run promotion，
才能证明它确实改善了原问题。

| 当时远端发现的问题 | 当前处理 | 当前是否仍存在 |
|---|---|---|
| P3 near-cluster 误差 0.4874，最佳 trace 基线 0.1582，差约 3.08 倍 | 停止 P3 主线，K3 只作为历史负对照 | **存在于 P3，未被推翻** |
| Ky Fan + hard MGS 可能造成不良梯度路径 | A-GTNet 改用 raw trial basis 上的 generalized trace，训练时不做 hard MGS | **设计上已处理，效果待 GPU 验证** |
| anchor、ROM、多图和目标函数同时变化，无法归因 | 拆成 G0/G1/G2/G3/K3 五方法矩阵 | **已处理** |
| P3 参数量比最佳基线更多，比较不完全公平 | G0 与 G1 在每个势族内使用完全相同的可训练参数与初始化 | **已处理，并由 gate 自动核验** |
| harmonic 与 Gaussian 两个势族都没有达到 15% 改善 | 新 G1 本地单 seed 仅改善约 14.2% | **仍存在；目前仍未达正式门槛** |
| 原结果包没有回收，提交号与运行源码来源链不完整 | 新 executor 记录源码、suite、cache、配置、checkpoint、环境和逐文件 SHA-256 | **新实验已处理；旧 P3 证据仍不可恢复** |
| 旧报告有一次正交误差 1.19e-4，超过旧门槛 1e-4 | 新 MPS smoke 实测约 1.99e-7 | **工程 smoke 已正常；正式 GPU 仍需报告实际值** |
| frozen final 没有运行 | 按协议继续保持关闭 | **有意保留，不是缺陷** |

这里必须特别说明：历史 P3 gate 的正交阈值是 `1e-4`，当前 A-GTNet promotion 代码
使用 `<2e-4`。两次 gate 因而不能只用“PASS/FAIL”直接比较。虽然当前 smoke 的实际
正交误差远低于两个阈值，正式论文仍必须报告原始最大正交误差，并额外核对它是否也
低于旧的 `1e-4`；不得用放宽阈值掩盖数值问题。

因此，当前只能说：

- A-GTNet 已经消除了 P3 中目标函数、硬正交化、参数量和模块混杂等明显设计问题；
- 本地机制探针从“明显失败”推进到了“单 seed 接近门槛”；
- 14.2% 仍小于 15%，且单 seed 没有统计效力；
- 在新的 30-run 结果返回前，论文状态仍是“可继续验证，但不能投稿”。

正式结果回来后，至少检查 `g1_vs_g0_improvement_percent`、两个
`family_improvement_percent`、6 个 `paired_seed_improvements`、实际最大正交误差、
Gram 条件数和 `promotion_go`。不能只看最后一行状态。

## 为什么把最终候选改成 A-GTNet

A-GTNet 是 **Anchored Generalized-Trace Network**。其输出是两个未正交的复值周期
试探函数组成的矩阵 \(Y_\theta\)，训练目标为

\[
\mathcal L_{GT}=\operatorname{tr}\!\left[
(Y_\theta^*Y_\theta)^{-1}(Y_\theta^*H Y_\theta)
\right].
\]

候选 G1 只在纯 G0 网络输出上增加一个不含可训练参数的低能 Bloch 物理锚点：

\[
Y_{A\text{-}GTNet}=Y_{\theta}+\alpha Y_{\mathrm{anchor}}.
\]

它的研究价值不应写成“我们发明了 generalized trace”或“我们发明了物理 anchor”。
更稳妥的主张是：

> 对带内部简并的参数化二维 Bloch PDE 谱簇，使用固定秩、基底不变的 generalized-
> trace 训练，并用不增加可训练参数的低能 Bloch 子空间作为坐标先验，能否改善无标签
> 摊销式神经求解器在简并邻域的优化稳定性和泛化？

这比 P3 更适合写论文，原因是：G0 与 G1 的网络参数、目标、采样和预算完全相同，唯一
变量就是物理 anchor。ROM 作为 G2/G3 消融保留，用来证明复杂模块并非提升来源。

## 冻结的五方法对照

| 代号 | 训练目标 | 物理 anchor | ROM | 论文角色 |
|---|---|---:|---:|---|
| G0 `g0_trace` | generalized trace | 否 | 否 | 最关键公平基线 |
| G1 `g1_anchor` | generalized trace | 是 | 否 | **A-GTNet 主候选** |
| G2 `g2_static_rom` | generalized trace | 是 | 静态单图 | 复杂度消融 |
| G3 `g3_annealed_rom` | generalized trace | 是 | 退火单图 | 延续训练消融 |
| K3 `k3_p3` | Ky Fan + hard MGS | 是 | 历史双图 | 失败机制负对照 |

五种方法在 harmonic honeycomb 和 Gaussian honeycomb 两个势族上运行，固定 seeds
`42/137/251`、每次 500 步，共 30 次。执行机不得改变方法、seed、步数或门槛。

## 远端 promotion 的硬门槛

只有同时满足下列条件，A-GTNet 才进入下一阶段：

1. 30/30 运行完成，无 NaN；
2. 最大正交误差 `<2e-4`，最大 Gram 条件数 `<1e8`；
3. G1 相对 G0 的 near-cluster 平均投影误差整体至少改善 15%；
4. harmonic 与 Gaussian 两个势族分别都至少改善 15%；
5. 6 个“势族 × seed”配对全部为正改善；
6. G0 与 G1 在**每个势族内**可训练参数量完全相等；
7. G1 优于历史 P3；
8. G1 不得比最佳 ROM 扩展差超过 2%，否则主候选选择不成立；
9. G3 的 ROM 系数在训练结束时确实退火为 0，保证消融协议被执行。

`PROMOTION_GO` 只表示可以由本地继续设计论文实验，不代表已经达到投稿标准，也不授权
远端执行 frozen final。任一条件失败都是 `PROMOTION_STOP`，不得挑 seed 或改门槛。

## 远端机器的唯一职责

远端不是研究助理，也不负责选择算法。它只需要从干净的 `main` 执行：

```bash
python scripts/run_p4_executor.py --device auto 2>&1 | tee p4-executor.log
```

程序自动生成 validation 参考缓存、先做 10-run 工程 smoke、再做冻结的 30-run
promotion，并输出带 manifest 与 SHA-256 的证据包。远端只回传：

- `artifacts/p4-evidence-*.tar.gz`；
- 对应 `.sha256`；
- `p4-executor.log`。

所有解释、统计、下一阶段选择和论文文字都在本地完成。详细操作见
[执行机唯一指令](P4-EXECUTOR.zh-CN.md)。如果交给另一个 AI 或操作员，直接复制
[执行机交接提示词](EXECUTOR-PROMPT.zh-CN.md)，不要让对方自行扩展实验。

## GO 以后才运行什么

若 promotion GO，仍需先由本地冻结 final 方案，再让执行机运行：

1. 一次且仅一次 frozen final；
2. 至少 5 个新 seed，或根据 pilot 方差完成统计功效分析；
3. anchor 类型/尺度、错误 anchor、静态/退火 ROM 的消融；
4. exact degeneracy、near degeneracy、IID、strict OOD、gap scan；
5. 参数量匹配、时间匹配、采样匹配和峰值显存；
6. Dai/Galerkin、监督 Grassmann 上界、逐带神经本征求解器等期刊级基线；
7. 至少一个不同周期势族或另一种二维周期几何。

若 promotion STOP，则不开 final。应根据失败项决定：若改善稳定但不足 15%，可把 anchor
作为优化技巧而非主创新，另找更强研究问题；若跨 seed/势族不稳定，则停止 A-GTNet
精度主张，转向“简并处的基底不变表示与失败机制分析”或更换 PDE 场景。

## 论文应准备的图

| 图 | 必须展示的内容 | 审稿问题 |
|---|---|---|
| Fig. 1 | PDE → 周期神经试探基 → anchor → generalized trace → rank-2 谱簇 | 是否真在解 PDE |
| Fig. 2 | 参考/预测能带和 Dirac 点局部放大 | 简并处是否物理正确 |
| Fig. 3 | `k_x-k_y` 平面的 G0/G1 误差热图 | 改善是否覆盖区域 |
| Fig. 4 | exact/near/IID/OOD 的配对 seed 分布与 95% CI | 是否稳定泛化 |
| Fig. 5 | G0/G1/G2/G3/K3 消融 | anchor 是否是真正来源 |
| Fig. 6 | 训练 loss、投影误差、梯度范数、Gram 条件数 | 为什么优化改善 |
| Fig. 7 | 错误/random/correct anchor 与 anchor scale 敏感性 | 是否只是幸运初始化 |
| Fig. 8 | 误差—训练时间、误差—参数量 Pareto | 是否值得计算成本 |
| Fig. 9 | 第二势/第二几何上的主结果 | 外部有效性 |

主指标必须是 basis-invariant 投影误差和主角度；本征值误差、PDE residual、正交误差、
训练/推理时间和显存作为补充。不能用单个最好 seed 的曲线代替统计图。

## 现在能不能发表

- **现在直接投稿：不能。** P3 是负结果，A-GTNet 只有一个本地探索 seed。
- **是否值得继续：值得。** 下一次 30-run 实验规模小、问题清楚且有硬停止条件。
- **SCI 四区：有条件可能。** 需要 promotion GO、一次 frozen final、完整消融、公平
  期刊级基线和第二外部场景。
- **SCI 三区：当前不足。** 还需要更强外部有效性，以及对 physical anchor 改善
  generalized-trace 优化条件的理论或数值解释。
- **当前创新强度：中等偏弱、待证。** 若两个势族和全部 seed 都达到 15% 以上，且错误
  anchor 消融支持机制，可提升到中等；若只有约 10% 单场景提升，不足以当期刊主创新。

当前最理性的下一步不是写满整篇结果，也不是租多卡，而是让一张 GPU 严格执行这次
冻结 promotion。结果决定是否继续，不由期待决定。

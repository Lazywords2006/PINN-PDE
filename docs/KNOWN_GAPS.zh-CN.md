# 当前缺口与投稿判断

更新时间：2026-07-30。

## 当前能否继续

课题可以继续，但 **P3 不能按原方案继续进入 final**。AMD 交接报告称 24-run pilot
已经完成且 gate 为 STOP；P3 的 near-cluster 投影误差约为最佳 generalized-trace
基线的 3.08 倍。由于原始结果包没有进入仓库，这些数字尚未独立复核，但无论是重现
STOP，还是找回原结果，当前都没有证据支持“P3 优于基线”。现阶段属于**PDE 课题和
工程可行，P3 主创新被 pilot 否证，后继机制有待重新验证**。

## 仍缺什么

| 优先级 | 缺口 | 完成判据 |
|---|---|---|
| P0 | 找回或重跑 P3 pilot 证据 | 有 24 个 result/metrics/training/checkpoint、环境记录、总 manifest 和可通过的 SHA-256；否则只称“外部报告” |
| P0 | A-GTNet promotion | 固定 generalized trace，以同参数量 G0 对照 G1 physical anchor；两势族、3 seeds、30 runs，禁止读取 final |
| P0 | 冻结 final 测试 | 仅当一个预先冻结的后继方法通过新 promotion gate 后运行；P3 当前禁止运行 |
| P0 | 核心消融 | 在同一目标函数下隔离 anchor、静态 ROM、退火 ROM 与历史 hard-MGS P3；错误/random anchor 在 GO 后测试 |
| P0 | 公平基线 | 补 Dai/Galerkin、监督 Grassmann 上界；说明公式适配与官方复现的区别 |
| P1 | 统计分析 | 以 seed 为独立重复，报告均值、标准差、95% CI、配对效应量和 Holm 校正 |
| P1 | 泛化与效率 | IID、exact、near、strict OOD、gap scan；参数量、训练/推理时间、峰值显存 |
| P1 | 图表 | 能带与谱隙、投影误差热图、逐 split 箱线图、消融、误差-时间 Pareto、回退分布 |
| P1 | 外部有效性 | 至少增加一个不同 PDE/几何或解释为何两个势族足以支持主张 |
| P2 | 理论与论文 | 固定秩谱簇良定性、损失/复杂度分析、局限、完整初稿和可复现包 |

## 何时应停止或改方向

- P3 已被报告为未比最佳 pilot 基线改善 15%：保持 final 关闭，停止把 P3 当作主创新。
- 若 A-GTNet/G1 在两个势族均不能稳定优于纯 generalized trace/G0：放弃把 physical
  anchor 当作精度主创新，不得通过增加训练量或选择单个 seed 包装提升。
- 提升只出现在一个势族或一个 seed：创新证据不足。
- 消融已经提示 ROM 没有稳定超过简单 anchor：因此 ROM 只保留为对照，不能堆叠包装。
- final 提升明显低于 validation：报告泛化失败，不能调 final 后再测试。

## 投稿强度判断

- SCI 四区：只有在 GO、完整 final、至少三项有效消融、近期/期刊级基线和完整效率
  报告后，才是“有条件可行”。
- SCI 三区：还需要更强外部有效性、统计证据、理论解释或第二类 PDE；当前尚不够。
- 当前创新强度：P3 机制候选已经得到负向 pilot；后继 A-GTNet 只是待证假设，尚不能作为
  投稿创新。详细决策和实验矩阵见
  [当前结果、A-GTNet 方案与投稿决策](POST-PILOT-DECISION.zh-CN.md)。

## 需要的硬件

单张 RTX 5090 32 GB、RTX 4090 24 GB 或单张 AMD 192 GB 均足够；不需要多卡。模型
显存不是瓶颈，参考解主要吃 CPU 和内存。目标机器建议至少 12 CPU 核、32 GB RAM；
25 核、90 GB 或 8 核、200 GB 均可运行。正式结论应固定一种 GPU 后端，避免把不同
后端结果混进同一统计组。

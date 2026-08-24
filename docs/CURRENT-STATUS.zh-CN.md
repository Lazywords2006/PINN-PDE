# 当前研究状态（2026-08-24）

## 一句话结论

课题仍是“神经网络求解二维 Bloch–Schrödinger 本征 PDE 的 rank-2 谱簇”，没有跑题。
P5 继续是有效 `P5_PROMOTION_STOP`：低频 ROM 不能作为主创新。P0 在独立参数集上证明
退化风险可检测，状态 `RISK_DEVELOPMENT_GO`。P1 基底不变风险门控校正器已经完成设计、
实现和本地 MPS 工程烟测，状态 `P1_ENGINEERING_SMOKE_PASS`；现在只授权 AMD 上的 P1
pilot，不授权 P6 promotion 或 frozen final。

## 阶段状态

| 阶段 | 状态 | 含义 |
|---|---|---|
| P4 | `PROMOTION_STOP` | anchor 有效，但 ROM 收益需要控制 |
| P5 | `P5_PROMOTION_STOP` | ROM 不敌等算力 long-anchor，gap-scan 回退 |
| P5 独立审计 | PASS | 36/36、CSV/checkpoint/manifest/gate 可重算 |
| P0 risk-development | **GO** | 独立 held-out 风险可检测性通过 |
| P1 条件校正器 | **工程烟测 PASS** | 已设计/实现；正式 96 点 x 3 seed 未运行 |
| P1 AMD pilot | 待运行 | 当前下一步；cutoff-24 reference + ROCm 评价 |
| P6 promotion | 未授权 | 只有 P1_PILOT_GO 才能设计 |
| frozen final | 关闭 | 禁止读取与运行 |
| 当前投稿 | NO | 尚无通过 P1/P6/final 的论文方法 |

## P5 结论不变

| 方法 | near-cluster | gap-scan |
|---|---:|---:|
| static-low-ROM | 0.11018 | 0.14920 |
| anchor | 0.12323 | **0.14013** |
| long-anchor | **0.10616** | 0.15930 |

低频 ROM 相对 anchor 的 near 改善真实，但无法区别于更长训练预算，并在 gap-scan 回退
6.47%。因此不能进入标题、摘要或贡献列表。

## P0 独立风险开发

### 数据与隔离

- 160 个新参数点；calibration/audit 各 80；
- harmonic / Gaussian 各 80；
- 每个角色和势族包含 IID、exact、near、strict-OOD、gap-scan；
- 与 `v2_validation.json`、`v2_frozen_test.json` 参数零重叠；
- 12 个已审计 P5 final checkpoint；
- 480 个 point×seed 配对行；
- PWE cutoff 24、rank 3、33×33 grid、CPU float64；
- 推理 MPS float32；
- 真值 projector、误差和参考 gap 不进入拟合特征。

### Held-out audit

| 指标 | 实测 |
|---|---:|
| regression AUROC | **0.869154** |
| unsafe AUROC | **0.843848** |
| clustered 95% CI | **[0.818069, 0.912911]** |
| AUPRC | **0.858756** |
| harmonic AUROC | **0.968532** |
| Gaussian AUROC | **0.716611** |
| top-20% precision | **0.916667** |
| unsafe rate：全量 → 80% coverage | **0.425000 → 0.307292** |

所有冻结门槛通过。结果由 `features.csv` 在单独进程重新拟合、重算并与存储 gate 对照，
主要数值在 `1e-12` 容差内一致。证据 manifest 的 24 个文件均通过字节数与 SHA 审计。

### 诚实限制

- parameter-only 风险基线 AUROC 为 0.707734；
- 组合特征 AUROC 高约 0.161，但风险明显带有参数区域结构；
- Gaussian 单族 0.7166 刚超过门槛，弱于 harmonic；
- P0 检测的是 static-ROM 相对 anchor 的退化，不证明条件路由能改善解；
- P0 仍是开发证据，不是 frozen-final 或论文主实验。

## P1 基底不变风险校正器

主方法同时运行已审计的 anchor 和 static-ROM 神经网络，用 P0 冻结风险决定 ROM 校正
权重。两个 rank-2 复基先做 Procrustes 对齐，再在 Grassmann/谱投影意义下平滑混合并
重新正交。这样不会在能带交叉处因为两列基的任意旋转而错误相加。

已冻结 96 个 P1 新点，与 P0、V2 validation、V2 frozen final 均零重叠。P0-only
Q60/Q80/Q90/Q95 阈值分别为 `0.374721 / 0.483113 / 0.645512 / 0.760633`。

2026-08-24 本机 MPS 烟测实测：191 项测试通过；两势族各 1 点、9 方法完整；最大正交
误差 `1.51e-7`；完整 P1 风险路径约为 anchor 的 `3.01x`（仅 warm-up 1、重复 2）；
第二次执行成功 SHA-bound 恢复。正式门槛为 2.5x，因此效率是明确风险。
这是 cutoff-2、7x7 工程证据，不是精度主实验。

P1 当前是冻结 anchor/ROM 神经 PDE 求解器的推理期基底不变后处理器，不是新训练的校正
网络。正式方法表述必须保持这一边界；parameter-only 路由已加入强基线。

## 当前下一步

必须在 ModelScope AMD ROCm 环境运行冻结 P1 pilot：

1. 先通过 ROCm 预检和 181 项测试；
2. 为 96 点生成 cutoff-24、rank-3、33x33 参考缓存；
3. 运行 anchor、long-anchor、static-ROM、4 个 P1 变体、PWE 安全变体和 oracle；
4. 主方法不允许 PWE 回退，PWE 变体只能单独报告；
5. 完整保存 6 个 SHA-bound unit、CSV、gate、证据包和环境；
6. near 相对 long-anchor至少改善 5%；
7. gap-scan 不超过最佳非 ROM 2%；
8. 两势族均改善、至少 5/6 family×seed 配对获胜；
9. 报告回退率、推理成本和 many-query break-even。

只有 `P1_PILOT_GO` 后，才允许设计 P6 promotion。完整命令见
[P1-RUNBOOK.zh-CN.md](P1-RUNBOOK.zh-CN.md)。

## 证据

- P5 archive SHA：
  `56891c5740eb94c62299b72869d790a1cbdee6abda3fae2903ed822f5e405101`；
- risk suite SHA：
  `292d590fbeee105c827556558a274300454bd937bb125ca0825ee75dca84496b`；
- risk reference SHA：
  `9511548da16aae0f6f4873423bce14b55d7016e6e161e68a00d1675789ff8905`；
- P0 evidence SHA：
  `d5783e65e7c55149206757505bae922193b5315b5596b6324fe0f8f07c2ed81d`。
- P1 suite SHA：
  `0806773a4f4e50ef017d2c0e8487bfb3b489e82a1b0269005d41b5d08613fadd`。

完整命令、指标和限制见 [RISK-DEVELOPMENT-RUNBOOK.zh-CN.md](RISK-DEVELOPMENT-RUNBOOK.zh-CN.md)。

## 投稿判断

- 神经网络解 PDE：是；
- 方向是否继续：是；
- 低频 ROM 是否继续：否；
- P0 是否通过：是；
- 条件校正器工程是否通过：是；
- 条件校正器科学效果是否验证：否；
- 是否可用 AMD 运行 P1 pilot：是；
- SCI 四区：当前未达到；
- SCI 三区：当前明显不足；
- frozen final：保持关闭。

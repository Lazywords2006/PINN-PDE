# 当前研究状态（2026-08-24）

## 一句话结论

课题仍是“神经网络求解二维 Bloch–Schrödinger 本征 PDE 的 rank-2 谱簇”，没有跑题。
P5 继续是有效 `P5_PROMOTION_STOP`：低频 ROM 不能作为主创新。新增 P0 在独立参数集上
证明退化风险可检测，状态 `RISK_DEVELOPMENT_GO`；它只授权设计条件校正器，不授权大规模
GPU 实验或 frozen final。

## 阶段状态

| 阶段 | 状态 | 含义 |
|---|---|---|
| P4 | `PROMOTION_STOP` | anchor 有效，但 ROM 收益需要控制 |
| P5 | `P5_PROMOTION_STOP` | ROM 不敌等算力 long-anchor，gap-scan 回退 |
| P5 独立审计 | PASS | 36/36、CSV/checkpoint/manifest/gate 可重算 |
| P0 risk-development | **GO** | 独立 held-out 风险可检测性通过 |
| P1 条件校正器 | 未设计/未实现 | 当前下一步 |
| P6 GPU pilot | 未授权 | P1 小测 GO 后才生成执行提示词 |
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

## 当前下一步

必须先单独设计 P1 条件校正器：

1. anchor 作为默认稳定预测；
2. parameter-only、单特征和组合风险作为三类风险基线；
3. 只在开发证据支持的区域启用局部校正；
4. 高风险区域回退 PWE；
5. 与 anchor、long-anchor、static-ROM 使用相同参数/时间预算；
6. near 相对 long-anchor至少改善 5%；
7. gap-scan 不超过最佳非 ROM 2%；
8. 两势族均改善、至少 5/6 family×seed 配对获胜；
9. 报告回退率、推理成本和 many-query break-even。

P1 工程与小测通过后，才允许生成无占位符的
`docs/P6-GPU-EXECUTOR-PROMPT.zh-CN.md`。当前该提示词不存在是正确状态。

## 证据

- P5 archive SHA：
  `56891c5740eb94c62299b72869d790a1cbdee6abda3fae2903ed822f5e405101`；
- risk suite SHA：
  `292d590fbeee105c827556558a274300454bd937bb125ca0825ee75dca84496b`；
- risk reference SHA：
  `9511548da16aae0f6f4873423bce14b55d7016e6e161e68a00d1675789ff8905`；
- P0 evidence SHA：
  `50ed6a74b145f360187793ca63c1cd596b95c95f12dd3eb79ecdd9235099d7b6`。

完整命令、指标和限制见 [RISK-DEVELOPMENT-RUNBOOK.zh-CN.md](RISK-DEVELOPMENT-RUNBOOK.zh-CN.md)。

## 投稿判断

- 神经网络解 PDE：是；
- 方向是否继续：是；
- 低频 ROM 是否继续：否；
- P0 是否通过：是；
- 条件校正器是否已验证：否；
- 是否立即租 GPU：否；
- SCI 四区：当前未达到；
- SCI 三区：当前明显不足；
- frozen final：保持关闭。

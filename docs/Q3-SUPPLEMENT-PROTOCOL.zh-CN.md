# SCI 三区独立补充实验协议

冻结日期：2026-08-24

## 目的

在不读取 frozen-final 指标进行模型选择、不重跑 640 点 final 的前提下，直接比较当前
P2 full-shell 求解器与两个最接近期刊方法的可审计 Bloch 适配：Wang–Xie trace 多本征对
和 Dai neural-subspace Galerkin。

## 方法

| 方法 | 训练 | 说明 |
|---|---|---|
| `p2_full_shell` | 不重新训练 | 复用 P5 long-anchor seeds 42/137/251，加入完整 shell 2 |
| `wang_xie_trace_adapted` | 1500 steps | generalized trace，无 anchor，3层×64宽度 SiLU MLP |
| `dai_galerkin_adapted` | 1500 steps | rank-6 神经试验基 + Galerkin，3层×64宽度 SiLU MLP |

两个适配基线使用 Adam、学习率 `1e-3`、每步4个参数实例、每实例256点、seeds
42/137/251。它们获得多于 P2 long-anchor 的训练步数，避免弱基线。

## 独立 suite

- 160 个参数点，harmonic/Gaussian 各80点；
- 每势族：IID 16、exact 16、near 24、strict-OOD 16、gap-scan 8；
- 与 V2 validation、640点 final、P0、P1、P2 independent pilot 全部逐参数去重；
- reference：float64 PWE cutoff-24、rank-3、33×33 网格；
- exact/near 的 internal gap 与 external gap 必须通过参考谱验证；
- suite 和 reference cache 均绑定 SHA-256。

## 指标和成功线

主指标为 rank-2 projector sine error。报告 overall、五个 split、两个势族、三个 seeds、
参数量、训练时间、推理时间、峰值显存和正交误差。

`Q3_SUPPLEMENT_GO` 需要：

1. 3种方法 × 2势族 × 3seeds × 80点的身份矩阵完整；
2. P2 overall 同时低于两个适配基线；
3. P2 对两个基线的参数点聚类 bootstrap 改善95% CI下界均大于0；
4. P2 near 与 gap-scan 均低于两个适配基线；
5. P2 对每个基线至少赢5/6个 family×seed overall 配对；
6. 最大正交误差小于 `1e-4`；
7. 证据包、manifest、源码、suite、cache、checkpoint 与环境哈希全部通过。

如任一项失败，状态为 `Q3_SUPPLEMENT_STOP`，仍保存和报告全部数据。不得移动门槛重跑。

## 论文表述边界

本实验是根据论文公式进行的统一 Bloch 适配，不是作者官方代码结果。最终论文必须说明
适配差异、参数量和训练预算。无论 GO 或 STOP，640点 frozen final 都保持关闭。

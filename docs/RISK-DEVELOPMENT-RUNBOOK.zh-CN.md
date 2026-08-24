# P0 独立风险开发：运行手册与实测结论

更新：2026-08-24。

## 最终状态

`RISK_DEVELOPMENT_GO`。

这个 GO 只说明：在独立 calibration/audit 参数集上，推理时可获得的组合特征能够识别
低频 ROM 相对 anchor 的退化风险。它授权下一步设计条件校正器，不授权运行 P6 大矩阵，
更不授权打开 frozen final。

## 实际运行环境

- Apple MacBook Air M4，16 GB；
- PyTorch 2.8.0；
- PWE 参考：CPU float64、hexagonal cutoff 24、rank 3、33×33 网格；
- checkpoint 推理：MPS float32；
- P5 来源：已独立审计的 12 个 anchor/ROM final checkpoint。

## 冻结资产

| 资产 | SHA-256 / 数量 |
|---|---|
| risk suite | `292d590fbeee105c827556558a274300454bd937bb125ca0825ee75dca84496b` |
| PWE reference cache | `9511548da16aae0f6f4873423bce14b55d7016e6e161e68a00d1675789ff8905` |
| P5 evidence archive | `56891c5740eb94c62299b72869d790a1cbdee6abda3fae2903ed822f5e405101` |
| P0 self-contained evidence archive | `d5783e65e7c55149206757505bae922193b5315b5596b6324fe0f8f07c2ed81d` |
| suite points | 160：calibration 80、audit 80 |
| paired rows | 480：160 点 × 3 seeds |
| checkpoint inventory | 12：2 方法 × 2 势族 × 3 seeds |

PWE 参考生成实际耗时 12 分 44 秒；六个 MPS 配对推理单元耗时约 56 秒。

## Held-out audit 实测

| 指标 | 结果 | 冻结门槛 |
|---|---:|---:|
| regression AUROC | **0.869154** | ≥ 0.70 |
| unsafe-regression AUROC | **0.843848** | ≥ 0.70 |
| clustered 95% CI | **[0.818069, 0.912911]** | 下界 > 0.50 |
| primary AUPRC | **0.858756** | ≥ prevalence + 0.10 |
| regression prevalence | 0.512500 | — |
| harmonic AUROC | **0.968532** | ≥ 0.65 |
| Gaussian AUROC | **0.716611** | ≥ 0.65 |
| top-20% precision | **0.916667** | ≥ prevalence + 0.15 |
| unsafe rate | 0.425000 | — |
| unsafe rate at 80% coverage | **0.307292** | ≤ 0.75 × 0.425 |

按 split 的 held-out AUROC：exact 0.889、gap-scan 0.809、IID 0.829、near 0.900、
strict-OOD 0.804。

最强单特征为 residual log-ratio（AUROC 0.762），其次为 Ritz-gap log-ratio（0.736）和
Ritz-gap difference（0.732）。组合模型的 0.869 明显高于任一单特征。

## 必须保留的限制

参数坐标本身的非门控诊断基线在 audit 上达到 AUROC 0.707734。组合无标签特征高出约
0.161，但这说明退化存在显著参数区域结构。下一阶段必须：

1. 把 parameter-only 模型列为强风险基线；
2. 报告组合特征相对 parameter-only 的增量；
3. 保留跨势族与 gap-scan 分层指标；
4. 不能声称风险完全来自“物理残差”或与参数位置无关；
5. 不能把 P0 GO 写成条件校正器已经有效。

## 复现命令

```bash
uv run --python 3.12 --with-requirements requirements.txt python -m pytest -q

uv run --python 3.12 --with-requirements requirements.txt \
  python scripts/generate_risk_development.py --suite-only

uv run --python 3.12 --with-requirements requirements.txt \
  python scripts/generate_risk_development.py --device cpu --cache-only

uv run --python 3.12 --with-requirements requirements.txt \
  python scripts/evaluate_risk_features.py --device mps
```

科学 STOP 会使用进程退出码 2。判定应读取
`results/risk_development_v1/gate.json`，不能只根据信号进程返回值判断工程失败。

## 输出

- `results/risk_development_v1/features.csv`；
- `results/risk_development_v1/calibration_model.json`；
- `results/risk_development_v1/metrics.json`；
- `results/risk_development_v1/gate.json`；
- `results/risk_development_v1/checkpoint_inventory.json`；
- `results/risk_development_v1/units/*.json`；
- `artifacts/risk-development-evidence-20260824-092630.tar.gz` 及 sidecar；包内含实际 P5
  archive、P5 sidecar、参考缓存、6 个 unit JSON 及其 sidecar、源码与结果，可独立复核。

## 独立复核

已经从 `features.csv` 在另一个进程重新拟合 calibration、计算 audit 指标和 gate；主要
数值与存储 JSON 在 `1e-12` 容差内一致。证据包外层 SHA、tar 路径、重复成员、manifest
字节数和 32 个文件 SHA 全部通过；6 个 resume unit 的内部行身份与 sidecar 也全部通过。

## 下一步

下一步是 P1 条件校正器设计，不是直接大规模训练。设计必须比较：

- parameter-only risk；
- 单特征 risk；
- 当前组合 risk；
- anchor-only；
- long-anchor；
- static-low-ROM；
- 条件路由与 PWE fallback。

P1 的 near、gap、两势族、5/6 配对、成本和回退率门槛全部通过后，才能生成没有占位符的
`P6-GPU-EXECUTOR-PROMPT.zh-CN.md`。当前禁止生成或执行该大规模提示词。

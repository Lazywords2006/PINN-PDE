# AMD ROCm P3 Promotion Pilot — 交接报告

> **本地复核状态（2026-07-30）**：本文件和三份 benchmark SHA 可在仓库中核验，
> 但下文列出的 `results/p3_v2_pilot/`、参考缓存、环境记录与 80 MB 压缩包没有提交到
> GitHub，也未在本地工作区找回。因此，下列训练数字应标记为**远端执行者报告、尚未
> 独立复核**，不能直接复制进论文结果表。即使暂不采信具体数值，报告给出的 gate
> 结论仍要求保持 frozen final 关闭，直至原始证据找回或在固定提交上重新运行。

**日期**: 2026-07-30  
**机器**: AMD gfx942 (Instinct MI300X), 192 GB VRAM, Intel Xeon 23C, 200 GB RAM  
**执行人**: Claude (deepseek-v4-pro), 监督下自动执行  
**提交**: `4e7c8e1a01a358a16538b574e880d2cafd69e4fa` (main)

---

## 执行摘要

按照 `docs/HANDOFF.zh-CN.md` 完整执行了 V2 实验流水线。P3 promotion gate 为 **STOP**——P3 在所有指标上劣于 wang_xie_trace 基线，未达到 15% 改善阈值。

---

## 流水线结果

| 阶段 | 状态 | 详情 |
|---|---|---|
| 1. 代码核验 | ✅ PASS | HEAD = `4e7c8e1a` |
| 2. ROCm 环境 | ⚠️ PASS* | `ROCM_ENGINEERING_VALIDATION=PASS`, smoke OK, 15 测试因 CPU LAPACK 缺失失败 |
| 3. V2 资产生成 | ✅ PASS | 704 点 PWE 参考缓存, SHA-256 三组 OK, 收敛审计 6/6 |
| 4. 24-run pilot | ✅ 完成 | 24/24 runs PASS, 0 NaN, 0 failures |
| 5. Pilot gate | 🛑 STOP | `pilot_go=false` |
| 6. Frozen final | ⏭️ 跳过 | Gate STOP, 按协议不运行 |

\* CPU LAPACK 缺失不影响 GPU 训练；GPU 端使用 hipSOLVER。

---

## Pilot Gate 详情

```json
{
  "all_runs_completed": true,
  "finite_metrics": true,
  "orthogonality_pass": false,
  "best_baseline_projector_mean": 0.1582,
  "p3_vs_best_baseline_improvement_percent": -208.1,
  "pilot_go": false
}
```

**正交性**: max = 1.19e-4 (阈值 1e-4)，仅 `ordered_residual_gaussian_honeycomb_seed42` 超限 0.19×。即使放宽此阈值，核心科学 gate（15% 改善）依然远未达标。

---

## 各方法 near_cluster 投影误差

| 方法 | Overall | Harmonic | Gaussian |
|---|---|---|---|
| **wang_xie_trace** | **0.1582** 🥇 | **0.1270** | **0.1893** |
| p1_block | 0.4964 | 0.2584 | 0.7344 |
| P3 | 0.4874 | 0.3342 | 0.6406 |
| ordered_residual | 0.7764 | 0.7683 | 0.7844 |

### P3 vs 最佳基线改善

- Overall: **-208.1%** (P3 差 3.08×)
- Harmonic: **-163.1%** (P3 差 2.63×)
- Gaussian: **-238.4%** (P3 差 3.38×)

两个势族均远未达到 15% 改善阈值。

---

## Bug 修复

`scripts/run_p3_pilot.py:255` — 参考基有 6 个本征向量 `[1089, 6, 2]`，模型输出 rank-2 `[1, 1089, 2, 2]`。添加 `[..., :2, :]` 切片使形状匹配。`evaluate_v2_final.py` 通过导入自动继承此修复。

---

## 关键发现

1. **wang_xie_trace (GeneralizedTracePINN) 是最佳方法**，且在 harmonic 和 gaussian 上均一致领先
2. **P3 在 gaussian 上略优于 p1_block** (0.641 vs 0.734)，但在 harmonic 上劣于 p1_block (0.334 vs 0.258)
3. **ordered_residual 在两种势族上均表现最差**
4. **所有方法在 harmonic 上的表现均优于 gaussian**（约 2-3× 差距）

---

## 当前创新判定

**P3 未通过 promotion gate。不建议将 P3 作为主创新推进**，理由：

- P3 在两个势族上均未达标（详见 `docs/KNOWN_GAPS.zh-CN.md` 停止判据）
- 提升只在一个势族的一个 baseline（gaussian vs p1_block）上出现，且幅度不足以证明 ROM-Grassmann 机制有效
- Generalized trace 目标函数可能是更适合此 PDE 类别的变分形式

### 后续建议

1. 分析为何 wang_xie_trace 的 trace(B⁻¹A) 目标在此问题上显著优于 Ky Fan trace
2. 检查 P3 ROM 图划分是否在训练预算内充分收敛
3. 考虑将 ROM 修正集成到 generalized trace 框架而非 Ky Fan 框架
4. 若重新设计后仍无改善，按 `KNOWN_GAPS` 停止判据放弃 P3 路线

---

## 资产清单

以下是远端执行者报告的资产位置，并不表示这些文件当前存在于 Git 仓库：

| 文件 | 说明 |
|---|---|
| `results/p3_v2_pilot/` | 24-run pilot 完整输出（result.json x24, final.pt x24, metrics.csv x24, training.csv x24） |
| `data/v2_frozen_test_references.pt` | 640 点 PWE cutoff=24 参考缓存 |
| `data/v2_validation_references.pt` | 64 点 validation 参考缓存 |
| `benchmarks/v2_validation.json` | 64 点 validation suite |
| `benchmarks/v2_frozen_test.json` | 640 点 frozen test suite |
| `benchmarks/v2_reference_convergence.json` | cutoff 16/20/24 收敛审计 |
| `results/environment/` | pip freeze, torch 环境, rocminfo |
| `/tmp/pinn-pde-results.tar.gz` | 完整打包 (80 MB) |
| `/tmp/pinn-pde-results.sha256` | SHA-256: `309f8c4815cf0c76e63d3fe30c5b2faafe70e19804e21f595ad44878619a96dd` |

---

## 环境备注

- **已知限制**: 容器内 ROCm PyTorch 2.10.0 缺少 CPU LAPACK，导致 `torch.linalg.solve` 在 CPU tensor 上失败。GPU 端 hipSOLVER 正常。
- **GPU 名称获取失败**: `torch.cuda.get_device_name(0)` 返回空字符串，ROCm 已知问题，不影响计算。
- **结果包下载验证**: `shasum -a 256 -c pinn-pde-results.sha256`

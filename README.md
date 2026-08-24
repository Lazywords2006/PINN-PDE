# 二维 Bloch–Schrödinger PDE 神经谱簇求解器

本项目使用一个轻量神经网络求解**二维参数化 Bloch–Schrödinger 本征偏微分方程**。
输入为二维坐标、Bloch 波矢和周期势参数；输出为最低两个本征态共同张成的 rank-2
谱簇。训练不读取参考本征函数标签，PWE 高精度解只用于评价。

> 当前判断（2026-08-24）：低频 ROM 和风险路由分别经 P5/P1 判为 STOP，但新的
> **P2 full-shell 基底不变神经增强 Rayleigh–Ritz 求解器**已经通过独立 pilot 和唯一一次
> 640 点 frozen final。最终 overall projector error 为 **0.04532**，long-anchor 为
> 0.14719；点级 bootstrap 改善 69.2%，95% CI `[67.7%, 70.8%]`。最终状态
> **`P2_FROZEN_FINAL_GO`**，证据 audit PASS，本地独立重算完全一致。禁止再次运行或调节
> frozen final，当前进入论文与复现材料准备。

权威状态、结果解释和下一步见
[当前研究状态与 P5 方案](docs/CURRENT-STATUS.zh-CN.md)。本次 P5 执行完整报告见
[P5-EXECUTION-REPORT.zh-CN.md](docs/P5-EXECUTION-REPORT.zh-CN.md)，主控交接见
[HANDOFF-P5-20260801.zh-CN.md](docs/HANDOFF-P5-20260801.zh-CN.md)。独立复核过程、哈希与
逐点失败分析见 [P5 独立审计报告](docs/P5-INDEPENDENT-AUDIT.zh-CN.md)。
P0 设计、命令、实测、证据和限制见
[风险开发运行手册](docs/RISK-DEVELOPMENT-RUNBOOK.zh-CN.md)。
P1 方法、门槛、AMD 命令和回传要求见 [P1 运行手册](docs/P1-RUNBOOK.zh-CN.md)。
P1 是冻结神经求解器上的推理期基底不变后处理器；不能写成“新训练的校正网络”。
P2 的完整方法、final 表格、统计、效率和投稿判断见
[P2 最终实验报告](paper/p2_final/P2_FINAL_EXPERIMENT_REPORT.zh-CN.md)。

## 到底用了什么网络，解了什么 PDE

求解方程为

\[
\left[\tfrac12(-i\nabla+\mathbf{k})^T G(-i\nabla+\mathbf{k})
+V_{\mu}(\mathbf{x})\right]u_j=E_j u_j,
\qquad \mathbf{x}\in[0,2\pi)^2,
\]

其中函数值和一阶导数满足二维周期边界条件。当前验证两个周期势族：harmonic
honeycomb 与 Gaussian honeycomb。

P5 被检验的候选 **A-GTROMNet** 包含：

- 以周期坐标特征、Bloch 波矢和势参数为输入的 SiLU MLP；
- K 点附近的物理低能 anchor；
- 一个由 PDE 参数生成七个低频 Fourier 系数的轻量 ROM 分支；
- 无标签 generalized-trace 变分损失 `Tr(B⁻¹A)`；
- 评价时的复数 modified Gram–Schmidt，保证 rank-2 子空间正交。

这是真实的二维 PDE 本征求解，不是一维 ODE，也不是拿 PWE 标签做监督拟合。它不是
传统“逐点 residual PINN”；更准确的名称是**无标签变分式神经谱簇求解器**。

## 为什么学习谱簇

两条能带在 Dirac 点相交时，单个本征函数可以交换编号或在簇内任意旋转。逐带学习的
目标会不连续。只要目标簇与第三条能带仍有外部谱隙，rank-2 投影子空间仍然良定。
因此本项目评价投影误差和主角度，不评价两列输出的具体顺序。

## 最终 P2 方法与结果

P2 先用 long-anchor 神经网络给出 rank-2 粗子空间，再加入完整二阶六角 Fourier shell
（19 个解析模式），只对两个神经列使用自动微分，对 Fourier 列解析装配 Hamiltonian，
最后在 21 维紧凑空间中提取最低两个 Ritz 向量。方法不使用 reference projector 构造
输出，也不增加新的学习参数。

Frozen-final：640 参数点 × 2 势族 × 3 seeds × 10 方法，共 19,200 行。

| 方法 | Overall | Near | Gap-scan |
|---|---:|---:|---:|
| Long anchor | 0.14719 | 0.08924 | 0.15938 |
| Neural + shell 1 | 0.06172 | 0.04513 | 0.05768 |
| **P2 full shell** | **0.04532** | **0.03903** | **0.04389** |
| Fourier-only rank 21 | 0.13697 | 0.12249 | 0.13700 |

P2 平均推理 107.8 ms、p95 121.9 ms；同服务器 cutoff-24 CPU PWE 为 313.4 ms。
所有 family-seed 配对获胜，最大正交误差 `3.12e-7`。

## 已核验的 P4 结果

权威证据包为 `artifacts/p4-evidence-20260801-080059.tar.gz`，SHA-256 sidecar 已核验。
30/30 个 run 完成，所有 manifest 文件的字节数和 SHA-256 均匹配。

| 方法 | near-cluster 投影误差均值 | 解释 |
|---|---:|---|
| G0 generalized trace | 0.16870 | 无 anchor 的同架构基线 |
| G1 anchor | 0.12323 | 比 G0 改善 26.95%，6/6 seed×势族均为正向 |
| G2 static low-frequency ROM | **0.11018** | 比 G1 再改善 10.58%，但参数约多 23–24%、训练约慢 33% |
| G3 annealed ROM | 0.13012 | 不如静态 ROM |
| 历史 P3 | 0.49444 | 明显落后 |

P4 唯一失败门槛是 G1 没有保持在最优 ROM 扩展的 2% 以内。因此停止的是“只把 G1
作为论文主方法”，不是停止整个课题。G2 在 `gap_scan` 上又比 G1 差约 6.47%，所以也
不能直接把 G2 包装为成功创新。

## P5 要回答的唯一问题

P5 不调 final，不改 P4，也不为了刷指标增加训练预算。它用 36 次 validation 运行判断
G2 的提升究竟来自低频物理结构，还是仅来自更多参数、更多训练时间或任意 Fourier
分支：

| P5 方法 | 控制变量 |
|---|---|
| `p5_anchor` | G1 基线 |
| `p5_static_low_rom` | 候选低频 ROM |
| `p5_wide_anchor` | 参数量匹配 |
| `p5_long_anchor` | 训练时间匹配 |
| `p5_unanchored_low_rom` | 检验 anchor 与 ROM 的交互 |
| `p5_highfreq_rom` | 同参数量、不同频率的结构对照 |

独立重算表明，`p5_long_anchor` 的 near-cluster 误差 0.10616 优于 ROM 候选的
0.11018，而 ROM 候选的 gap-scan 误差 0.14920 又劣于基础 anchor 的 0.14013。因此
`mechanism_go=false`、`gap_scan_non_regression=false` 和 `promotion_go=false` 均已
独立确认。低频 ROM 可以保留为负结果或消融，但不能作为论文标题、摘要或主要贡献。

## P0 风险可检测性结果

P0 使用 160 个与 P5 validation、frozen final 均不重叠的新参数点，calibration/audit
各 80 点，并在 12 个已审计 P5 final checkpoint 上产生 480 个严格配对行。风险分数只用
推理时可获得的 residual、Gram、rank-2 Ritz 与 anchor–ROM projector disagreement；
真值误差和参考 gap 只用于事后标签与审计。

Held-out audit 结果：

- regression AUROC `0.869154`，clustered 95% CI `[0.818069, 0.912911]`；
- unsafe-regression AUROC `0.843848`；
- harmonic / Gaussian AUROC `0.968532 / 0.716611`；
- top-20% precision `0.916667`；
- 80% coverage 时 unsafe rate 从 `0.425000` 降至 `0.307292`；
- 全部预注册门槛通过，状态 `RISK_DEVELOPMENT_GO`。

限制：parameter-only 诊断基线 AUROC 为 `0.707734`，表明风险存在参数区域结构。组合特征
仍高约 0.161，但后续必须把 parameter-only 纳入强基线。P0 没有实现条件校正器，不能
写成新方法已优于基线。

## 环境与验证

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -q
```

设备脚本：

```bash
bash scripts/setup_cuda.sh      # NVIDIA CUDA
bash scripts/setup_rtx5090.sh   # RTX 5090 / CUDA 12.8
bash scripts/setup_rocm.sh      # AMD ROCm，保留镜像自带 PyTorch
```

P5 本地工程烟测：

```bash
python scripts/run_p5_executor.py --device auto --skip-cache --smoke-only
```

P0 风险开发：

```bash
python scripts/generate_risk_development.py --suite-only
python scripts/generate_risk_development.py --device cpu --cache-only
python scripts/evaluate_risk_features.py --device mps
```

P1 本地工程烟测与 AMD 正式入口：

```bash
python scripts/run_p1_pilot.py --device mps --smoke-only --allow-dirty
python scripts/generate_p1_validation.py --device cpu --cache-only
python scripts/run_p1_pilot.py --device rocm
```

第一条不是论文结果；第二、三条必须在干净提交和正式 ROCm 环境中运行。

复现独立审计：

```bash
python scripts/audit_p5_evidence.py \
  artifacts/p5-evidence-20260801-092048.tar.gz \
  --sidecar artifacts/p5-evidence-20260801-092048.tar.gz.sha256
```

审计器会核验外层 SHA-256、包内 manifest、36-run 身份矩阵，直接读取每个
`result.json` 重算 near-cluster/gap-scan 均值和全部门槛，并拒绝旧 summary、缺失 run
或被篡改文件。本仓库证据已得到 `audit_pass=true`；审计不改变冻结科学门槛，所以
最终仍是 STOP。

## 算力

- 本地 Apple MPS/CPU：适合单元测试和 12-run、5-step 烟测，不作为论文正式结果。
- 单张 RTX 4060 8 GB：模型和显存足够，可复现；完整矩阵会更慢。
- 单张 RTX 4090/5090 或 MI300X：足以运行完整机制矩阵。
- 不需要多卡、H100 集群或大规模预训练。

## 目录

```text
block_kyfan_pinn/  网络、PDE、参考解、指标和协议
benchmarks/        冻结 validation/final 套件与 SHA-256
scripts/           资产生成、诊断、门控和证据打包
tests/             单元测试与小型集成测试
docs/              当前决策、架构、运行手册和历史交接
artifacts/         已封存并独立核验 P4、P5 权威证据
```

## 研究纪律

- P5 数值现在可作为 validation 机制筛选的负结果引用，但不能写成 final 测试结论。
- 当前结果只支持 validation 上的机制筛选，不支持论文精度主张。
- P0 GO 只支持“风险可检测”；P1 smoke 只支持“工程可运行”，两者都不支持论文精度主张。
- frozen final 只有新协议明确 GO 后才能运行一次。
- Ky Fan、generalized trace、Fourier ROM、PWE、谱投影和 MGS 都不是本文单独发明。
- P5 审计已经确认：低频 ROM 不能继续作为论文主创新，长训练 anchor 也只能作为
  强基线，不能把增加训练预算写成方法创新。
- 任何无法通过参数量、训练时间、错误频率和多随机种子对照的提升，都不能写成创新。

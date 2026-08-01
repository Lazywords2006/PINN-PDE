# 二维 Bloch–Schrödinger PDE 神经谱簇求解器

本项目使用一个轻量神经网络求解**二维参数化 Bloch–Schrödinger 本征偏微分方程**。
输入为二维坐标、Bloch 波矢和周期势参数；输出为最低两个本征态共同张成的 rank-2
谱簇。训练不读取参考本征函数标签，PWE 高精度解只用于评价。

> 当前判断（2026-08-01）：研究方向可以继续，但还不能投稿。P4 的 30 次正式
> validation 已由主控独立核验为有效 `STOP`。远端执行机报告 P5 的 36-run promotion
> 为 `P5_PROMOTION_STOP`，但 GitHub 当前只有执行报告，尚缺权威 P5 证据包、sidecar
> 和原始 run 文件，故主控独立复核状态为 **BLOCKED**。冻结 final 仍未打开。

权威状态、结果解释和下一步见
[当前研究状态与 P5 方案](docs/CURRENT-STATUS.zh-CN.md)。本次 P5 执行完整报告见
[P5-EXECUTION-REPORT.zh-CN.md](docs/P5-EXECUTION-REPORT.zh-CN.md)，主控交接见
[HANDOFF-P5-20260801.zh-CN.md](docs/HANDOFF-P5-20260801.zh-CN.md)。当前执行机只需使用
[P5 证据上传提示词](docs/P5-EVIDENCE-UPLOAD-PROMPT.zh-CN.md)，不要重跑实验。

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

远端报告表明，`p5_long_anchor` 的 near-cluster 误差 0.10616 优于 ROM 候选的
0.11018，而 ROM 候选的 gap-scan 误差 0.14920 又劣于基础 anchor 的 0.14013。因此
报告中的 `mechanism_go=false`、`gap_scan_non_regression=false` 和
`promotion_go=false` 在算术上自洽。原始证据未进仓库前，这些数值必须标记为
**远端报告、待独立复核**。

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

收到权威证据包后执行独立审计：

```bash
python scripts/audit_p5_evidence.py \
  artifacts/p5-evidence-20260801-092048.tar.gz \
  --sidecar artifacts/p5-evidence-20260801-092048.tar.gz.sha256
```

审计器会核验外层 SHA-256、包内 manifest、36-run 身份矩阵，直接读取每个
`result.json` 重算 near-cluster/gap-scan 均值和全部门槛，并拒绝旧 summary、缺失 run
或被篡改文件。只有 `audit_pass=true` 才能把 P5 数值升级为独立核验结果。

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
artifacts/         已封存 P4 证据；权威 P5 包仍待上传
```

## 研究纪律

- P5 报告数值在原始证据包到达前不得写入论文结果表。
- 当前结果只支持 validation 上的机制筛选，不支持论文精度主张。
- frozen final 只有新协议明确 GO 后才能运行一次。
- Ky Fan、generalized trace、Fourier ROM、PWE、谱投影和 MGS 都不是本文单独发明。
- P5 报告若经审计成立，低频 ROM 不能继续作为论文主创新，长训练 anchor 也只能作为
  强基线，不能把增加训练预算写成方法创新。
- 任何无法通过参数量、训练时间、错误频率和多随机种子对照的提升，都不能写成创新。

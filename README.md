# A-GTNet：二维 Bloch–Schrödinger PDE 神经谱簇求解器

一个用神经网络求解**二维参数化 Bloch–Schrödinger 本征偏微分方程**的研究原型。

网络输入二维坐标、Bloch 波矢和势函数参数，输出两个复值周期函数。它不在能带交叉处
强行给两条能带编号，而是直接学习最低两个本征态共同张成的 rank-2 谱簇。训练使用
无标签 Ky Fan 变分目标；PWE 高精度解只用于参考解和评估，不作为训练标签。

截至 2026-08-01，P4 promotion 协议已在本机（AMD MI300X / ROCm）实际运行：为绕过
该 torch 构建的两个环境缺陷（CPU 端无 LAPACK、导入 torch 的进程强制退出码 0），
对 3 个脚本做了纯工程层修复（Gram 检查改在 GPU 上执行、退出改用 `os._exit`），
30/30 个 run 全部成功完成，executor 门控判定 **PROMOTION_STOP**（exit 2）：
A-GTNet（g1）相对 generalized-trace（g0）的 near-cluster 投影误差改善 **+26.95%**
（两族 25.1%/28.0%，均 ≥15%）、相对历史 P3 改善 **+75.1%**、参数量完全一致，
但**未保持在最优 ROM 扩展的 2% 以内**（`g1_within_2pct_of_best_rom_extension=false`），
因此冻结 gate 为 **STOP**，冻结 final 没有运行。原始 checkpoint/CSV/manifest 已打包进
`artifacts/p4-evidence-20260801-080059.tar.gz` 并进入本仓库，可独立复核。
主候选为 **A-GTNet**：在 retraction-free generalized-trace 网络上加入不增加可训练
参数的低能 Bloch 子空间锚点；ROM 仅保留为消融，不再包装为主创新。
完整交接见 [docs/HANDOFF-20260801.zh-CN.md](docs/HANDOFF-20260801.zh-CN.md)。

## 解什么方程、用什么网络

方程为

\[
\left[\tfrac12(-i\nabla+\mathbf{k})^T G(-i\nabla+\mathbf{k})
+V_{\mu}(\mathbf{x})\right]u_j=E_j u_j,
\qquad \mathbf{x}\in[0,2\pi)^2,
\]

并满足二维周期边界条件。当前包含 harmonic honeycomb 与 Gaussian honeycomb 两个势族。

P3 网络由以下部分组成：周期坐标 MLP、物理低能 anchor、两个可学习参数图、每图一个
轻量 Fourier ROM 修正、能量密度加权的局部修正，以及保持 rank-2 子空间正交的
dual-path 复 MGS。风险判断只使用预测残差和图间分歧，不读取真实谱隙；高风险样本可
回退到确定性的 hexagonal PWE。

这属于“神经网络求解 PDE 本征问题”，但不是普通点态 residual PINN。完整计算结构见
[架构说明](docs/ARCHITECTURE.md)。

## 目录

```text
block_kyfan_pinn/  网络、PDE、参考解、指标和协议
benchmarks/        V1 历史套件与 V2 冻结套件、收敛证据、SHA-256
configs/           旧 V1 复现配置与当前工程 smoke 配置
scripts/           资产生成、pilot、冻结测试、统计和审计工具
tests/             单元与小型集成测试
docs/              架构、运行手册、缺口和机器交接文档
baselines/         外部官方实现的固定版本索引
```

## 环境与工程验证

CPU 或 Apple MPS：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -q
python run_smoke.py --device cpu --steps 5 --points 64
```

NVIDIA CUDA：

```bash
bash scripts/setup_cuda.sh
```

RTX 5090 + CUDA 12.8 可使用 `bash scripts/setup_rtx5090.sh`。AMD ROCm 镜像必须保留
镜像预装的 ROCm PyTorch，使用：

```bash
bash scripts/setup_rocm.sh
```

这些 setup 脚本只做环境、完整测试和最小 smoke，不会擅自运行论文实验。

## V2 实验入口

> 当前 P3 gate 已被报告为 STOP。以下命令保留用于复现和证据审计；不要绕过 gate 打开
> frozen final。下一阶段的算法诊断与停止条件见
> [当前结果、A-GTNet 方案与投稿决策](docs/POST-PILOT-DECISION.zh-CN.md)。

A-GTNet 的五方法因子诊断、自动 gate、断点续训和证据打包已提供独立入口。目标
机器不负责选择方案，只执行：

```bash
python scripts/run_p4_executor.py --device auto
```

该命令先做工程 smoke，通过后自动运行冻结的 30-run validation promotion；无论 GO
或 STOP 都会生成带 SHA-256 manifest 的结果包。详细机器操作见
[A-GTNet 执行机指令](docs/P4-EXECUTOR.zh-CN.md)。
需要交给另一台机器或另一个 AI 时，使用可直接复制的
[执行机交接提示词](docs/EXECUTOR-PROMPT.zh-CN.md)。

正式 promotion 前生成/核验套件、收敛证据和两套参考缓存。生成 final 缓存只验证物理
协议，不会用模型查看 final 表现：

```bash
python scripts/generate_v2_assets.py --device auto --reference-scope all
```

再运行 2 势族 × 4 方法 × 3 随机种子的 24-run pilot：

```bash
python scripts/run_p3_pilot.py \
  --device auto --method all --family all --seed 42 137 251 --steps 500
```

相同命令可以从 `latest.pt` 继续。只有 `results/p3_v2_pilot/pilot_gate.json` 中
`pilot_go=true`，才允许模型运行一次冻结测试：

```bash
python scripts/evaluate_v2_final.py --device auto
```

详细命令、失败处理和结果回收见 [运行手册](docs/RUNBOOK.md) 与
[目标机器交接文档](docs/HANDOFF.zh-CN.md)。

## 当前结论边界

- 已证明：代码路径可运行；P3 各机制不是空开关；V2 文件可验证；cutoff=24 的代表点
  收敛审计通过；真实 checkpoint 与代码/配置/数据哈希绑定。
- 已报告但未独立复核：AMD MI300X 上 24/24 pilot 完成、P3 gate STOP、最佳方法为
  `wang_xie_trace`。仓库缺少该次运行的 CSV、JSON、checkpoint 和结果包。
- 尚未证明：P3 或后继方法稳定优于基线、论文主张有统计显著性、达到 SCI 三区或
  四区标准。
- 当前决定：停止把 P3 当作可投稿主方法，保持 frozen final 未打开；以同参数量的
  generalized-trace 无锚网络 G0 为公平基线，验证 A-GTNet/G1 的物理 anchor 是否在
  两个势族和全部 seed 上稳定有效；静态/退火 ROM 仅作为消融。

仍需补齐的论文内容见 [已知缺口](docs/KNOWN_GAPS.zh-CN.md)。第三方基线的官方仓库、
许可证和固定提交见 [外部基线索引](baselines/external/README.md)。

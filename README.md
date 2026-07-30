# P3 Block KyFan-PINN

一个用神经网络求解**二维参数化 Bloch–Schrödinger 本征偏微分方程**的研究原型。

网络输入二维坐标、Bloch 波矢和势函数参数，输出两个复值周期函数。它不在能带交叉处
强行给两条能带编号，而是直接学习最低两个本征态共同张成的 rank-2 谱簇。训练使用
无标签 Ky Fan 变分目标；PWE 高精度解只用于参考解和评估，不作为训练标签。

截至 2026-07-30，P3 multi-chart ROM 原型、V2 validation/final 套件、原始字节
SHA-256、真实 checkpoint、断点续训、参考解收敛审计、24-run promotion gate 和冻结
测试入口均已实现并有自动测试。**GPU 正式结果尚未运行，因此当前不能声称论文方法
已经优于基线，也不能据此直接投稿。**

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
- 尚未证明：P3 在目标 GPU 上稳定优于基线、论文主张有统计显著性、达到 SCI 三区或
  四区标准。
- 必须先看 24-run pilot。若 P3 相对最佳基线的 validation 投影误差改善不足 15%，
  gate 会 STOP，禁止用 final test 包装结果。

仍需补齐的论文内容见 [已知缺口](docs/KNOWN_GAPS.zh-CN.md)。第三方基线的官方仓库、
许可证和固定提交见 [外部基线索引](baselines/external/README.md)。

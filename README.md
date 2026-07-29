# Block KyFan-PINN

一个面向二维参数化 Bloch–Schrödinger 本征 PDE 的无标签坐标神经变分求解器。模型不在能带交叉处强行追踪两条带的编号，而是学习最低两个本征态共同张成的 rank-2 谱簇。

当前仓库是可运行的研究原型：`45/45` 自动测试通过；dual-path 复 MGS、true Ky Fan trace、checkpoint/RNG/provenance 绑定和 V2 可证伪烟测已实现。现有结果只授权新的小规模 CUDA pilot，不代表论文正式实验已经完成。

## 目录

```text
block_kyfan_pinn/  核心模型、PDE、训练、参考解与指标
benchmarks/        冻结参数套件及 SHA-256
configs/           CPU/MPS/CUDA 实验配置
scripts/           评估、数据生成、统计与审计工具
tests/             单元与集成测试
baselines/         外部官方实现的固定版本索引
run_smoke.py       最小工程烟测入口
run_experiment.py  显式 JSON 配置入口
```

虚拟环境、训练结果、checkpoint、文献 PDF、第三方仓库副本和旧实验压缩包不会进入 Git。它们都可由依赖清单、固定配置或上游提交重新获得。

## 环境

- Python 3.11 或 3.12
- PyTorch 2.8
- NumPy 1.26–2.x

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

RTX 5090 + CUDA 12.8 可使用：

```bash
bash scripts/setup_rtx5090.sh
```

## 验证与运行

先执行完整测试：

```bash
python -m pytest -q
```

再运行一个不用于论文结论的最小烟测：

```bash
python run_smoke.py --device cpu --steps 5 --points 64
```

使用显式配置运行工程完整性实验：

```bash
python run_experiment.py configs/code_integrity_trace_smoke_cpu_v4.json
```

输出默认写入 `results/`，该目录不会提交。`run_all.py` 和 `run_sci3.py` 中的旧 V1 pilot/formal 路径已主动封禁；在新的 V2 正式套件、对称闭合 PWE 参考和两势族 CUDA pilot 完成前，不要绕过门禁启动旧长实验。

## 外部基线

第三方实现不直接复制进仓库。官方地址、许可证和固定提交见 [baselines/external/README.md](baselines/external/README.md)。项目内的 Wang–Xie、Dai 和 causal-sort 方法是统一 Bloch 参数网络上的公式级适配，不应描述为作者官方代码的原样复现。

## 研究边界

- 主方法是周期坐标 MLP + 物理 anchor + dual-path 正交化 + Ky Fan trace，不是 Fourier–Galerkin 主求解器；
- PWE 用于低阶 anchor、传统参考解与基线；
- `benchmarks/falsification_smoke_v2.json` 是 smoke-only 套件，不是最终论文测试集；
- 当前代码尚未实现计划中的 ROM–Grassmann multi-chart、gap-aware routing 和 PWE fallback。

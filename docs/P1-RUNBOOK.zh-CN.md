# P1 风险门控谱簇校正器运行手册

## 1. 当前结论

P1 已完成设计、数学实现、协议测试和 Apple MPS 工程烟测。烟测状态为
`P1_ENGINEERING_SMOKE_PASS`，只证明代码链路、两势族、9 条方法、P0/P5 证据读取、
正交化和断点恢复能够工作；它不是论文结果，也不打开 frozen final。当前 P1 是冻结
神经 PDE 求解器之上的推理期谱簇后处理器，不是“新训练了一个校正网络”。

P1 主方法是：

1. 独立 anchor 与 static-ROM 神经网络各预测一个 rank-2 谱簇；
2. 用冻结 P0 模型计算推理风险；
3. 对两个复基做 Procrustes 对齐，消除簇内任意旋转；
4. 低风险保留 ROM 校正，高风险平滑回到 anchor；
5. 主方法完全不使用 PWE 回退；PWE 5% 尾部回退只单独报告，不能挽救主方法 STOP。

## 2. 冻结资产

| 资产 | SHA-256 |
|---|---|
| P1 96 点套件 | `0806773a4f4e50ef017d2c0e8487bfb3b489e82a1b0269005d41b5d08613fadd` |
| P0 自包含证据 | `d5783e65e7c55149206757505bae922193b5315b5596b6324fe0f8f07c2ed81d` |
| P5 权威证据 | `56891c5740eb94c62299b72869d790a1cbdee6abda3fae2903ed822f5e405101` |

P1 套件包含 harmonic/Gaussian 各 48 点；每族为 IID 8、exact 8、near 16、
strict-OOD 8、gap-scan 8。它与 P0、V2 validation、V2 frozen final 参数零重叠。

P0-only 风险阈值：

| 用途 | 阈值 |
|---|---:|
| 平滑校正开始 Q60 | `0.374721142669` |
| 硬路由 Q80 | `0.483112944647` |
| 平滑校正结束 Q90 | `0.645511703956` |
| PWE 安全变体 Q95 | `0.760633250548` |

## 3. 本地验证

```bash
uv run --python 3.12 --with-requirements requirements.txt python -m pytest -q
uv run --python 3.12 --with-requirements requirements.txt \
  python scripts/run_p1_pilot.py --device mps --smoke-only --allow-dirty
```

2026-08-24 实测：

- 193 项测试全部通过；
- harmonic/Gaussian 各 1 点、seed 42；
- 9 条方法每条 2 行，全部完整；
- 最大正交误差 `1.5124290808632423e-7`；
- 完整计时包含 residual/Ritz、风险、Procrustes 和 MGS；烟测 warm-up 1 次、重复 2 次；
- anchor 路径 `48.680 ms`；
- P1 风险路径 `136.086 ms`，约 `2.80x` anchor；
- MPS 当前分配显存 `154112` bytes；
- 第二次运行成功从 SHA/来源绑定 unit 恢复；
- 状态 `P1_ENGINEERING_SMOKE_PASS`。

烟测使用 cutoff 2、7x7 网格，不能与正式 cutoff 24、33x33 结果混写。

## 4. ModelScope AMD 环境

固定使用：

```text
方式三 GPU 环境
8 CPU 核 / 200 GB 内存 / 192 GB 显存
ubuntu22.04-rocm7.2.3-py312-torch2.11.0-1.39.0
```

不要重新安装 PyTorch，不要切换 CUDA 镜像。进入 Terminal 后：

```bash
cd /mnt/workspace
git clone https://github.com/Lazywords2006/PINN-PDE.git
cd PINN-PDE
git checkout <本次合并后的精确提交>

python - <<'PY'
import torch
print(torch.__version__)
print(torch.version.hip)
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NO_ACCELERATOR")
PY

python scripts/preflight_accelerator.py --backend rocm
python -m pytest -q
```

预检必须显示 HIP/ROCm 可用并通过全部测试；否则不要生成参考缓存。

## 5. 正式 P1 pilot

先生成参考缓存。该步骤是 cutoff-24 PWE，主要消耗 CPU 和内存，可断点续跑：

```bash
python scripts/generate_p1_validation.py --device cpu --cache-only
(cd data && shasum -a 256 -c p1_validation_v1_references.sha256)
```

然后运行固定 2 势族 x 3 seeds 的 P1 pilot：

```bash
python scripts/run_p1_pilot.py --device rocm
```

允许的最终状态只有：

- `P1_PILOT_GO`：主方法全部冻结门槛通过；
- `P1_PILOT_STOP`：保留证据并停止升级；
- 工程异常：没有科学结论，先修复后从 SHA-bound unit 恢复。

正式运行使用 96 点、3 seeds、9 方法，共 2592 个评价行。6 个 family-seed unit
各自保存 JSON 和 SHA sidecar；套件、参考、P0/P5 证据、阈值、源码或 checkpoint 任一
变化都会拒绝旧 unit。

## 6. P1 成功线

神经主方法 `p1_risk_chordal` 必须同时满足：

- near 相对 long-anchor 至少改善 5%；
- gap-scan 不超过最佳 anchor/long-anchor 的 2%；
- 两个势族的 near 都优于 long-anchor；
- 6 个 family-seed 配对至少赢 5 个；
- overall 同时优于 anchor 和 static-ROM；
- unsafe rate 相对 static-ROM 至少下降 25%；
- 组合风险 AUROC 至少 0.70、每个势族至少 0.65，并比 parameter-only 至少高 0.05；
- 主方法 PWE 比例严格为 0；
- 最大正交误差 `<1e-4`；
- 实测推理延迟不超过 anchor 的 2.5 倍。

最新 7x7 小烟测的 production 主路径约为 `2.80x`，高于正式 `2.5x` 门槛；样本数太少，不能据此
宣布 STOP，但正式 AMD 计时若仍超过 2.5x，P1 必须因效率门槛停止或改为共享 trunk。

oracle 和 PWE 安全变体只作上界/安全分析，不能改变主方法 STOP。

## 7. 回传和关机

正式运行结束后必须回传：

```text
results/p1_pilot/
artifacts/p1-pilot-evidence-*.tar.gz
artifacts/p1-pilot-evidence-*.tar.gz.sha256
data/p1_validation_v1_references.pt
data/p1_validation_v1_references.sha256
```

先在本地核验 sidecar 和包内 manifest，再停止 ModelScope 实例。无论 GO 或 STOP 都必须
保存；不要只回传截图或 summary。

## 8. 禁止事项

- 禁止运行 `scripts/evaluate_v2_final.py`；
- 禁止读取 frozen-final reference/results；
- 禁止用 P1 96 点调整 P0 权重或阈值；
- 禁止把 smoke 当论文结果；
- 禁止用 PWE 安全变体掩盖神经主方法失败；
- 禁止因为 AMD 显存大而增加模型、种子或方法矩阵。

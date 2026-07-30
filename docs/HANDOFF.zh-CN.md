# 目标计算机器交接文档

> P3 的 AMD pilot 已被报告为 STOP，且原始结果包尚未在仓库中独立复核。本文档中的
> P3 命令现在只用于证据重现，不得继续到 frozen final。重新设计的判断依据和下一步
> 实验矩阵见 [当前结果、A-GTNet 方案与投稿决策](POST-PILOT-DECISION.zh-CN.md)。

当前新的正式交接入口是 [A-GTNet 执行机指令](P4-EXECUTOR.zh-CN.md)。下面的 P3 内容仅为
历史复现说明。

交接日期：2026-07-30。

## 你要完成的事情

先验证机器，再生成 validation 参考缓存并跑 24-run pilot。只有 gate 为 GO，才生成
640 点 final 缓存并运行冻结测试。单张 GPU 即可，不要开多卡。

## 1. 获取固定主分支

```bash
git clone https://github.com/Lazywords2006/PINN-PDE.git
cd PINN-PDE
git switch main
git pull --ff-only origin main
git rev-parse HEAD
```

把最后一行提交号保存下来。不要在服务器上临时改源码后继续训练。

## 2. 安装环境

NVIDIA 5090 / 4090：

```bash
bash scripts/setup_cuda.sh
source .venv/bin/activate
```

AMD ROCm 镜像：

```bash
bash scripts/setup_rocm.sh
source .venv-rocm/bin/activate
```

ROCm 不要执行 `pip install -r requirements.txt`，否则可能覆盖镜像原有 PyTorch。

## 3. 生成 pilot 所需资产

```bash
mkdir -p results
python scripts/generate_v2_assets.py --device auto --reference-scope all \
  2>&1 | tee results/generate-v2-assets.log
```

该命令使用 CPU double/complex128 PWE；GPU 类型对这一步影响不大。它在训练前验证
validation 与 final 的谱隙标签，但不会加载模型或查看模型 final 表现。中断后重复命令
会从每 25 点保存的 partial cache 继续。

## 4. 跑完整 promotion pilot

```bash
python scripts/run_p3_pilot.py \
  --device auto --method all --family all --seed 42 137 251 --steps 500 \
  2>&1 | tee results/p3-v2-pilot.log
```

相同命令可以恢复。不要删除 `latest.pt`。完成后：

```bash
jq . results/p3_v2_pilot/pilot_gate.json
```

- `pilot_go=false`：停止，不运行 final；把全部结果带回本地分析。
- `pilot_go=true`：继续第 5 步。

## 5. GO 后运行冻结测试

```bash
python scripts/evaluate_v2_final.py --device auto \
  2>&1 | tee results/p3-v2-final.log
```

final evaluator 会自行重新核验 24-run gate；不能靠手改 JSON 绕过。

## 6. 四小时机器的时间策略

1. 前 10 分钟：clone、setup、测试和 smoke。
2. 接着生成全部 V2 参考 cache；向量化 PWE 与 partial checkpoint 已启用。
3. 立即跑 24-run pilot；脚本按 run 保存，租期到点可在下一台同环境机器继续。
4. 若资产阶段未完成，不启动正式 pilot；先打包 partial cache，下一次继续。

不要为了赶时间降低 seeds、reference cutoff 或绕过 gate。少跑的结果只能标记“未完成”。

## 7. 离开服务器前回收

```bash
git rev-parse HEAD > results/GIT_COMMIT.txt
python -m pip freeze > results/pip-freeze.txt
tar -czf /tmp/pinn-pde-results.tar.gz results data
shasum -a 256 /tmp/pinn-pde-results.tar.gz | tee /tmp/pinn-pde-results.sha256
```

下载以下两个文件：

- `/tmp/pinn-pde-results.tar.gz`
- `/tmp/pinn-pde-results.sha256`

下载后在本地运行 `shasum -a 256 -c pinn-pde-results.sha256`。确认通过后再释放服务器。

# V2 运行手册

## 1. 工程门禁

在仓库根目录执行与设备对应的脚本：

```bash
bash scripts/setup_cuda.sh   # NVIDIA
bash scripts/setup_rocm.sh   # AMD ROCm
```

看到 `*_ENGINEERING_VALIDATION=PASS` 只表示环境和小烟测通过，不代表论文实验通过。

## 2. 冻结并验证全部 V2 资产

```bash
python scripts/generate_v2_assets.py --device auto --reference-scope all
```

该命令会重新生成确定性的 64 点 split-balanced validation、640 点 frozen final 套件，运行六点
cutoff 16/20/24 收敛审计，并预计算 validation 与 frozen final 参考缓存。此时不加载
任何训练模型，只验证 final 参数点的谱隙标签和参考解。缓存每 25 点保存
一次 `.partial.pt`；中断后运行同一命令会继续。若 partial 的套件哈希不一致，程序会
拒绝混用。

核验：

```bash
(cd benchmarks && shasum -a 256 -c v2_validation.sha256)
(cd benchmarks && shasum -a 256 -c v2_frozen_test.sha256)
(cd benchmarks && shasum -a 256 -c v2_reference_convergence.sha256)
```

## 3. 运行 promotion pilot

```bash
python scripts/run_p3_pilot.py \
  --device auto \
  --method all \
  --family all \
  --seed 42 137 251 \
  --steps 500
```

矩阵为 4 方法 × 2 势族 × 3 seeds，共 24 次。每次保存模型、优化器、CPU/加速器 RNG、
采样 RNG、源码指纹、配置指纹、suite/cache 哈希和训练 CSV。服务器中断后执行同一命令
即可恢复；若源码、配置或资产变化，恢复会被拒绝。

程序返回码为 0 才表示 gate GO。核心门槛：

- 24/24 完成且指标有限；
- 最大正交误差 `<1e-4`；
- 以 `near_cluster` 为主终点，P3 validation 投影误差相对最佳基线整体改善至少
  15%，且两个势族分别都达到至少 15%。

查看：

```bash
jq . results/p3_v2_pilot/pilot_gate.json
jq '{completed_runs,failed_runs,gate}' results/p3_v2_pilot/summary.json
```

## 4. 只在 GO 后打开 frozen final

```bash
python scripts/evaluate_v2_final.py --device auto
```

final evaluator 会先从 24 个 checkpoint/result 文件重新计算 promotion gate，并校验
checkpoint、源码、validation suite 和缓存绑定。若不是 GO，它会在读取 final suite 前
终止。成功输出：

- `results/p3_v2_final/per_parameter.csv`
- `results/p3_v2_final/summary.json`

## 5. 常见故障

- `source fingerprint mismatch`：运行期间源码改变；不要强行续训，固定提交后重跑。
- `cache SHA-256 ... invalid`：缓存或 sidecar 不完整；从匹配的 partial 继续或重新生成。
- `labelled exact/near_cluster`：实际谱隙不满足冻结标签，必须修协议后重新冻结，不能
  放宽标签掩盖问题。
- pilot 返回 1 且无异常：这是科学 gate STOP，不是程序故障。
- ROCm 环境丢失：不要安装 `requirements.txt` 覆盖镜像 PyTorch，重新执行
  `scripts/setup_rocm.sh` 并使用新 venv。

## 6. 结果回收

停止租用机器前保存提交号和压缩包：

```bash
git rev-parse HEAD > results/GIT_COMMIT.txt
python -m pip freeze > results/pip-freeze.txt
tar -czf pinn-pde-results-$(date +%Y%m%d-%H%M%S).tar.gz results data/*.sha256
shasum -a 256 pinn-pde-results-*.tar.gz
```

将压缩包和对应 SHA-256 下载到本地。不要只复制截图；CSV、JSON、日志、checkpoint 和
环境记录都必须保留。

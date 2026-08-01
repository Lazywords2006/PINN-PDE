# 当前运行手册（P5）

## 1. 纪律

P5 是 validation 上的机制归因，不是 frozen-final 实验。禁止修改方法、seed、步数、
门槛、套件或输出目录。P4 结果不可覆盖，P5 STOP 时禁止运行 final。

## 2. 同步与环境

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git status --porcelain
```

正式执行要求最后一条没有输出。选择一个环境脚本：

```bash
bash scripts/setup_cuda.sh      # NVIDIA
bash scripts/setup_rtx5090.sh   # RTX 5090
bash scripts/setup_rocm.sh      # AMD ROCm
```

AMD 镜像不要用 pip 安装 CUDA 版 torch 覆盖预装 ROCm 版本。

## 3. 本地烟测

有已核验 validation 缓存时：

```bash
python scripts/run_p5_executor.py \
  --device auto --skip-cache --smoke-only
```

合法成功状态为 `P5_EXECUTION_STATUS=SMOKE_PASS`。烟测为 6 方法 × 2 势族 × 1 seed，
每个只训练 5 步，只证明工程可运行。

## 4. 正式 P5

```bash
python scripts/run_p5_executor.py --device auto 2>&1 | tee p5-executor.log
```

程序会：

1. 核验或生成 validation PWE 缓存；
2. 跑 12-run smoke；
3. smoke 通过后跑 36-run promotion；
4. 解析 JSON 和 run 数，不只依赖退出码；
5. 生成带 manifest 的证据包和 SHA-256 sidecar。

断电后运行相同命令会从 `latest.pt` 继续。源码、配置、suite 或缓存哈希不一致时会拒绝
续训。

## 5. 结果解释

```bash
jq . results/p5_execution/execution-summary.json
jq . results/p5_promotion/diagnostic_gate.json
jq '{total_runs,completed_runs,failed_runs,gate}' results/p5_promotion/summary.json
```

- `P5_PROMOTION_GO`：低频结构归因和 gap 安全都通过；先回收证据，仍不要直接开 final。
- `P5_PROMOTION_STOP`：科学门槛未过；保留结果，不改门槛重跑。
- `SMOKE_FAIL`、`CACHE_FAIL`、`ENGINEERING_FAIL`：工程失败；保留 traceback 和失败包。

## 6. 证据核验与回收

```bash
latest=$(ls -t artifacts/p5-evidence-*.tar.gz | head -1)
sha256sum -c "${latest}.sha256" || shasum -a 256 -c "${latest}.sha256"
git rev-parse HEAD > results/P5_GIT_COMMIT.txt
python -m pip freeze > results/p5-pip-freeze.txt
```

下载 `latest`、对应 `.sha256`、`p5-executor.log` 和 Git commit。不要只保存截图。

## 7. 常见故障

- `formal P5 execution requires a clean Git checkout`：先备份结果，恢复干净工作树。
- `source fingerprint mismatch`：运行期间源码变化；固定提交后重新开始，不强行续训。
- `cache SHA-256 ... invalid`：缓存不完整；重新生成 validation 缓存。
- MPS eigvalsh 错误：应使用当前已提交的后端分流版本；不要把 Gram 一律移到 MPS。
- ROCm CPU LAPACK 错误：Gram 应保留在 ROCm GPU；不要恢复旧 `.cpu()` 实现。
- 子进程退出码为 0 但 JSON 有 failure：以 summary/gate 为准，当前 executor 会自动拦截。

完整判断见 [CURRENT-STATUS.zh-CN.md](CURRENT-STATUS.zh-CN.md)。

# A-GTNet 目标机器唯一执行指令

这台机器只负责计算。不要在远端设计方法、改代码、改超参数或解释结果。

如果需要把任务交给另一名操作员或另一个 AI，直接复制
[执行机交接提示词](EXECUTOR-PROMPT.zh-CN.md)。

## 1. 获取冻结代码

```bash
git clone https://github.com/Lazywords2006/PINN-PDE.git
cd PINN-PDE
git switch main
git pull --ff-only origin main
git status --porcelain
git rev-parse HEAD
```

`git status --porcelain` 必须没有输出。若已有仓库，只执行 `git pull --ff-only`，不要
merge 临时分支，也不要在服务器上修改 Python 文件。

## 2. 安装环境

NVIDIA RTX 4090/5090：

```bash
bash scripts/setup_cuda.sh
source .venv/bin/activate
```

AMD ROCm：

```bash
bash scripts/setup_rocm.sh
source .venv-rocm/bin/activate
```

AMD 镜像不要另装 CUDA 版 PyTorch。安装脚本失败就保存日志并停止，不自行换依赖版本。

## 3. 只运行这一条

```bash
python scripts/run_p4_executor.py --device auto 2>&1 | tee p4-executor.log
```

程序会自动：

1. 核验 cutoff 收敛文件与 SHA-256；
2. 只生成 V2 validation 的 PWE 参考缓存，不读取 frozen final；
3. 运行 G0/G1/G2/G3/K3 × 两势族 × seed 42 的 5 步 smoke；
4. smoke 通过后运行 5 方法 × 2 势族 × 3 seeds × 500 步，共 30 次；
5. 以 G1 A-GTNet 为主候选，检查 15% 整体/逐势族改善、6 个配对 seed、逐势族参数量
   相等、正交误差、Gram 条件数、ROM 消融和历史 P3 对照；
6. 无论 GO 或 STOP，都生成环境记录、原始结果、checkpoint 索引、manifest 和证据包。

中断后重新运行同一条命令即可。恢复逻辑会核对源码、suite、cache、配置和 checkpoint
指纹；不要删除 `latest.pt`。

## 4. 只回传三个文件

终端结束时会打印：

```text
P4_EXECUTION_STATUS=...
EVIDENCE_BUNDLE=.../artifacts/p4-evidence-YYYYMMDD-HHMMSS.tar.gz
EVIDENCE_SHA256=...tar.gz.sha256
EVIDENCE_MANIFEST=.../results/evidence-manifest.json
```

下载：

- `artifacts/p4-evidence-*.tar.gz`
- `artifacts/p4-evidence-*.tar.gz.sha256`
- `p4-executor.log`

本地核验：

```bash
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum -c p4-evidence-*.tar.gz.sha256
else
  shasum -a 256 -c p4-evidence-*.tar.gz.sha256
fi
```

## 5. 状态含义

- `PROMOTION_GO`：A-GTNet 通过 validation 门槛；只回传，不运行 final。
- `PROMOTION_STOP`：实验完成但科学门槛失败；同样回传全部证据。
- `SMOKE_FAIL` / `CACHE_FAIL` / `ENGINEERING_FAIL`：工程失败；回传日志，由本地修复。

## 禁止事项

- 不运行 `scripts/evaluate_v2_final.py`；
- 不查看或绘制 frozen final 的模型结果；
- 不改变 seed、步数、宽度、采样点、门槛或输出目录；
- 不删 STOP、不挑最好 seed、不把 smoke 当论文结果；
- 不自行继续更多实验；
- 不只发截图，必须回传原始证据包、SHA-256 和日志。

## 与旧远端结果的关系

旧 P3 的核心精度失败仍然有效，不能因新代码 smoke 通过而宣布解决。新 A-GTNet 只是
针对 generalized trace、hard MGS、参数量公平性和证据链进行了重新设计；它的本地
单 seed 探针改善约 14.2%，仍低于 15% promotion 门槛。只有本次 30-run 返回并通过
全部 gate 后，才能说新方向获得了正式 validation 支持。

此外，旧 P3 的正交门槛为 `1e-4`，新 gate 为 `2e-4`。回传后本地必须比较实际最大
正交误差，而不能只比较 PASS/FAIL 状态。

# 可直接复制的 A-GTNet 执行机交接提示词

把下面整段原样发送给远端机器上的 AI、运维人员或自动执行代理。方括号中的机器信息
可以补充，但不得改实验参数。

---

你不是研究方案设计者，也不是论文分析者。你只是一台受控实验执行器。

你的任务是在当前单张 GPU 机器上，从 GitHub `main` 的干净提交运行已经冻结的
A-GTNet validation promotion，保存全部原始证据并回传。不得选择方法、修改模型、
调整超参数、降低门槛、查看 frozen final、删除失败结果或自行追加实验。

机器信息（仅记录，不据此改协议）：

- GPU：[填写，例如 RTX 5090 32 GB / AMD MI300X 192 GB]
- 系统：[填写]
- 可用时间：[填写]

严格按以下顺序执行。

## 1. 获取干净的主分支

如果目录不存在：

```bash
git clone https://github.com/Lazywords2006/PINN-PDE.git
cd PINN-PDE
```

如果已经存在仓库，先进入仓库，然后执行：

```bash
git switch main
git pull --ff-only origin main
git status --porcelain
git rev-parse HEAD
```

必须记录 `HEAD`。`git status --porcelain` 必须没有输出；如果有输出，停止并报告，不要
提交、stash、reset 或删除文件，也不要在脏工作树继续正式实验。

## 2. 安装环境

如果是 NVIDIA RTX 4090/5090：

```bash
bash scripts/setup_cuda.sh 2>&1 | tee setup.log
source .venv/bin/activate
```

如果是 AMD ROCm：

```bash
bash scripts/setup_rocm.sh 2>&1 | tee setup.log
source .venv-rocm/bin/activate
```

不得在 AMD 环境安装 CUDA PyTorch，不得自行替换 PyTorch、CUDA、ROCm 或依赖版本。
安装失败时保存 `setup.log` 并停止，不能通过跳过测试继续训练。

## 3. 运行唯一正式入口

```bash
python scripts/run_p4_executor.py --device auto 2>&1 | tee p4-executor.log
```

该程序应自动完成 validation 参考缓存、10-run 工程 smoke 和冻结的 30-run promotion。
如果会话中断，重新运行同一条命令恢复；不要删除 `latest.pt`，不要更换 seed 或步数。

## 4. 不要擅自解释或继续实验

结束状态可能是：

- `PROMOTION_GO`：只表示 validation gate 通过；禁止继续 frozen final；
- `PROMOTION_STOP`：这是有效科学负结果，必须完整回传；
- `SMOKE_FAIL`、`CACHE_FAIL`、`ENGINEERING_FAIL`：这是工程故障，保存日志后停止。

无论哪一种状态，都不得修改 JSON、挑选最好 seed、删除 STOP、只发截图或把 smoke
写成论文结果。

## 5. 回传并校验证据

从程序结尾找到：

```text
P4_EXECUTION_STATUS=...
EVIDENCE_BUNDLE=.../artifacts/p4-evidence-YYYYMMDD-HHMMSS.tar.gz
EVIDENCE_SHA256=...tar.gz.sha256
EVIDENCE_MANIFEST=.../results/evidence-manifest.json
```

在服务器上先执行：

```bash
cd artifacts
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum -c p4-evidence-*.tar.gz.sha256
else
  shasum -a 256 -c p4-evidence-*.tar.gz.sha256
fi
cd ..
```

必须回传以下文件，缺一不可：

1. `artifacts/p4-evidence-*.tar.gz`
2. 对应的 `artifacts/p4-evidence-*.tar.gz.sha256`
3. `p4-executor.log`
4. 如果环境安装有异常，再附上 `setup.log`

最终只报告：Git commit、GPU/环境、开始和结束时间、程序状态、三个文件的完整路径、
SHA-256 校验是否通过。不要给出论文结论；本地研究端会读取原始 CSV、JSON 和
checkpoint 后统一判断。

如果租用时间快结束，优先保留并下载已有 `results/`、`data/`、`artifacts/` 和日志，
不要为了赶时间减少训练次数或跳过 gate。

---

本提示词对应的完整协议在 [A-GTNet 目标机器唯一执行指令](P4-EXECUTOR.zh-CN.md)。

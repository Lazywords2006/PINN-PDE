# P5 执行报告 — 远端 ROCm 机 36-run promotion（2026-08-01）

> **证据级别：执行机自报告，主控独立审计尚未完成。** GitHub 当前没有
> `p5-evidence-20260801-092048.tar.gz` 及 sidecar，以下数值不得直接进入论文结果表。
> 报告在算术上支持 STOP，但真实性和完整性仍需原始包重算。

> 执行机最终状态：**`P5_PROMOTION_STOP`**（有效负结果，非程序故障）。冻结 final
> 未打开，未运行 `evaluate_v2_final.py`。证据包 SHA-256 已核验。

## 一句话结论

冻结的 P5 机制归因矩阵在本机（AMD MI300X / ROCm）完整执行：cache + 12-run 工程烟测
全部通过，36/36 正式 run 全部完成、0 失败、指标全部有限。但**候选机制
`p5_static_low_rom` 未通过机制归因与 gap-scan 安全两道门槛**：近簇精度不敌
`p5_long_anchor` 控制组，且 gap-scan 误差相对最优非 ROM 回退，因此 executor 如实判定
**STOP**。这是一个有信息量的负结果：加低频 ROM 的收益更可能来自"训练更久/参数更多"，
而非 ROM 的物理结构本身。

## 机器环境

| 项 | 值 |
|---|---|
| GPU | AMD Instinct MI300X（gfx942），~192 GiB VRAM（rocm-smi 报 205.8 GB） |
| ROCm | kernel 6.10.5 / HIP 7.2.5（镜像自带，未用 pip 覆盖） |
| torch | `2.10.0+git8514f05`（镜像预装，`cuda=None`, `hip=7.2.53211`） |
| Python | 3.12.13 |
| CPU/内存 | Intel Xeon 23 vCPU，200 GiB RAM |
| git | HEAD `c04c43396a17d0dafe03cb74cf17c96fc5789ef9`，工作树干净 |

## 执行流水线

1. **备份**：旧 `artifacts/*.tar.gz`、`*.sha256`、`results/`、`*.log` → 本机
   `/mnt/workspace/backup-PINN-PDE-20260801-164457`（55 MB，含 P4 全部证据，未删除）。
2. **同步**：`git fetch` → `git switch main` → `git reset --hard origin/main` →
   `git clean -fd`。HEAD 精确 = 目标 commit，`git status --porcelain` 空。
3. **环境**：`scripts/setup_rocm.sh`：设备预检 4/4 PASS、设备 smoke PASS、
   `ROCM_ENGINEERING_VALIDATION=PASS`。
4. **测试**：`python -m pytest`。见下节。
5. **正式 P5**：`python scripts/run_p5_executor.py --device auto`（GPU/rocm）。
6. **判定**：只读 JSON（退出码在本机不可信），见"结果"节。
7. **证据核验**：`sha256sum -c` 证据包 sidecar = OK；`P5_GIT_COMMIT.txt`、
   `p5-pip-freeze.txt` 已保存。

## pytest 结果与 CPU-LAPACK 修复

**114 项收集：112 passed / 2 skipped（MPS 不可用）/ 0 failed。**

初始运行有 18 项失败，根因唯一：本镜像 ROCm torch **编译时关闭了 CPU LAPACK**
（`torch._C.has_lapack == False`），CPU 张量上的 `eigh/eigvalsh/svdvals/solve/qr/
lu_factor` 一律抛 `RuntimeError: ... requires compiling PyTorch with LAPACK`。GPU
（rocSOLVER）路径全部正常（preflight/smoke 即证明）。系统存在 `liblapack.so.3`，但这是
编译期开关，无法以 pip/apt 补救。

在用户授权"先修测试再跑"后，加入**纯测试层跨后端兼容垫片** `tests/conftest.py`：
检测到 CPU LAPACK 缺失且有加速器时，把这些 CPU 张量的 linalg 调用透明搬到 GPU 计算、
结果移回 CPU。未修改任何测试源码、科学逻辑、门槛、seed、步数或 benchmark。修复后
112/114 通过（2 个 skip 为 MPS 专属测试，预存在）。

## 正式 P5 结果

### 工程层（全过）

| 阶段 | 结果 |
|---|---|
| validation 参考缓存 | 通过（64 参考，63.5s，SHA-256 sidecar 匹配） |
| 12-run 工程烟测 | 12/12 完成、0 失败；`engineering_pass=true` |
| 36-run promotion | **36/36 完成、0 失败**；`finite_metrics=true`、`orthogonality_pass=true`（max 3.4e-7）、`gram_condition_pass=true`（max 11.0） |

### 候选机制 `p5_static_low_rom`（近簇投影误差均值，越低越好）

| 方法 | 近簇误差 | gap-scan 误差 | 相对候选改进 |
|---|---:|---:|---:|
| **p5_static_low_rom（候选）** | **0.11018** | **0.14920** | — |
| p5_anchor（最优非 ROM 控制） | 0.12323 | 0.14013 | 候选 +10.6% |
| p5_wide_anchor | 0.11910 | 0.15098 | 候选 +7.5% |
| **p5_long_anchor** | **0.10616** | 0.15930 | **候选 −3.8%（控制组更优）** |
| p5_unanchored_low_rom | 0.17171 | 0.21828 | 候选 +35.8% |
| p5_highfreq_rom | 0.12110 | 0.14783 | 候选 +9.0% |

### 门槛逐项

| 门槛 | 判定 | 值 |
|---|---|---|
| `candidate_at_least_5pct_better_than_each_control` | **false** | p5_long_anchor 反超 3.8% |
| `candidate_better_in_each_family` | **false** | — |
| `at_least_5_of_6_pairs_win_each_control` | **false** | 对每个 control 未达 5/6 配对比胜 |
| `gap_scan_non_regression` | **false** | 候选 0.1492 > 1.02×最优非 ROM 0.1401 |
| `rom_control_parameter_counts_match` | true | 候选/两个 ROM 控制参数量一致 |
| `candidate_parameter_overhead_at_most_30pct` | true | 1.236 |
| `candidate_time_overhead_at_most_50pct` | true | 1.324 |
| `long_compute_match_within_15pct` | true | 1.005 |
| `mechanism_go` | **false** | — |
| `promotion_go` | **false** | — |

### 最终状态

`P5_PROMOTION_STOP`（execution-summary.json 的 `status` 字段；本机退出码失真，不信）。

## 证据与产物

| 项 | 路径 |
|---|---|
| 权威证据包 | `artifacts/p5-evidence-20260801-092048.tar.gz`（19,904,767 B，275 文件） |
| 证据包 SHA-256 | `56891c5740eb94c62299b72869d790a1cbdee6abda3fae2903ed822f5e405101` — **核验 OK** |
| 执行日志 | `p5-executor.log`（13514 B） |
| 测试日志 | `pytest.log`（112 passed, 2 skipped） |
| 执行汇总 JSON | `results/p5_execution/execution-summary.json` |
| 烟测门控 | `results/p5_smoke/diagnostic_gate.json`（engineering_pass=true） |
| promotion 门控 | `results/p5_promotion/diagnostic_gate.json` |
| promotion 汇总 | `results/p5_promotion/summary.json`（total=36, completed=36, failed=0） |
| 环境信息 | `results/env-report.txt`、`results/P5_GIT_COMMIT.txt`、`results/p5-pip-freeze.txt` |

证据包内含：p5_smoke/p5_execution/p5_promotion 全部 `final.pt`、`latest.pt`、
`result.json`、metrics/training CSV、manifest、validation 参考缓存及 SHA-256、冻结源码、
requirements.txt。

## 纪律（未做的事）

- 未修改科学参数：seed（42/137/251）、训练预算、配点、batch、门槛、validation suite、方法/势族集合。
- 未运行 `evaluate_v2_final.py`；STOP 状态下 frozen final 保持关闭。
- 未删除任何 `latest.pt`；未更换 torch/ROCm 依赖版本。
- 唯一新增源码为测试层垫片 `tests/conftest.py`（跨后端兼容，见上）。
- 已安装本机缺失工具：`jq` 1.6（apt）。

# R32 接续说明（2026-10-16 本地暂停，迁移到云端）

> **2026-10-17 更新**：下文“接续步骤”已在云端执行完毕。第 8 节 36 个探针和修订 2/2b 的 48 个对照 run 全部完成，结果见 [STAGE2_REPORT.md](STAGE2_REPORT.md)（汇总表由 `compare_summary.py` 生成）。下一步待用户决定；下表是 10-16 暂停时的状态，保留未改。

本地电脑负载过高，用户 2026-10-16 要求停止本地运行并迁移到云端。停止时所有训练进程已退出；已完成的 run 都在 `runs/` 里，脚本会跳过已有结果，被中断的 run 没有留下 JSON，会重跑。

## 已完成

| 内容 | 状态 | 文件 |
|---|---|---|
| 协议（含修订 1、2、2b） | 冻结 | [PROTOCOL.md](PROTOCOL.md) |
| 参考解 / vanilla PINN / 评价器 / 两个改进及两个基线的实现 | 132 项测试通过 | `ref_wentzell.py`、`pinn_vanilla.py`、`metrics_wentzell.py`、`pinn_improved.py`、`test_*.py`；[VALIDATION.md](VALIDATION.md) |
| 第一阶段 R0、R1、RC（33 个 run） | 完成，首个失效台阶 = R0 | `runs/cells/`、[STAGE1_REPORT.md](STAGE1_REPORT.md) |
| 近邻检查 | 完成 | [NOVELTY_CHECK.md](NOVELTY_CHECK.md) |
| 第 8 节探针（36 个 run） | **完成 9 个**：adam5k、budget120、lr3e-3、nolbfgs、w32、wbc0.1、wbc10、wic10、wic100 的 seed 0 | `runs/probe_*/` |
| 修订 2/2b 的改进对照（48 个 run） | **未开始** | `run_compare.sh` |

seed 0 的探针结果（只有 1 个种子，不能下格点结论）：w_ic=10、100 体误差约 6e-3，达 U 级；其余为 2.2e-2–9.8e-2，未达 U 级。

## 接续步骤（在本目录执行）

```bash
pip install -r requirements.txt
python3 -m pytest -q -p no:cacheprovider          # 应为 132 passed
P=$(nproc) bash run_probes.sh                       # 剩余 27 个探针；结束时打印 PROBES_DONE，表格在 runs/probes_report.txt
P=$(nproc) bash run_compare.sh                      # 修订 2/2b 的 48 个 run；结束时打印 COMPARE_DONE
```

- `PY` 环境变量指定 Python（默认 `python3`），`P` 指定并行数（默认 9）。每个 run 单线程（`torch.set_num_threads(1)`）。
- 查看结果：`python3 ladder.py report --cell-id m0_lin_c0.3_d0.1_k0.3 --tag <tag>`；改进方法的 tag 为 `var_layer`、`var_decay`、`var_layer+decay`、`var_hardic`，基线为 `cells`（冻结 vanilla）、`probe_wic10`、`base_tpow2`。
- 诊断单个 run：`python3 diagnose.py --cell-id <cell> --seed <s> --tag <tag>`（输出 `_diag.png/json`）。
- 单个默认 run 在本机单线程约 21 CPU 分钟（Adam 2 万步约 450 s，L-BFGS 3000 次约 160 s）；60k 步、宽 128、Nf=16384 三种探针约慢 2–3 倍。

## 接续时必须遵守

1. 不改第 4 节冻结配置、判据和已写入的修订；新的改动只能以新修订追加，并写在看到相应结果之前。
2. 第 8 节判定：超参鲁棒性探针（宽度、lr、步数、关 L-BFGS、Nf）中任一配置使 m0_lin 达 U 级（≥2/3 种子），结论写“失败来自配置/预算”，不写“结构性失败”。损失权重探针是探索性的。
3. 修订 2b 判定：layer 须在 m0_lin 与 m1_lin 上比冻结 vanilla 低至少 3 倍、低于全部三个基线（w_ic=10、hardic、t_power=2），且达 U 级；decay 须在 m2_eig1 与 m2_const 上低至少 3 倍。达不到如实写，不追加调参。
4. 云端与本机的墙钟不能混在一起比较；本机的 budget120 探针按步数定义（Adam 4500 + L-BFGS 200），不是按云端秒数。
5. 旧资格合同、旧 formal、云端 A/B/C 三路与 heartbeat 仍保持暂停，不恢复。
6. 结果写入新的 `STAGE2_REPORT.md`（探针 + 对照），并同步更新 `总览/00_当前研究总档案.md` 的 R32 小节。

# 配置索引

所有配置均通过 `python run_experiment.py <config.json>` 读取，但它们的科学用途不同：

- `code_integrity_trace_smoke_cpu_v4.json`：当前源码下的 CPU 工程完整性烟测；
- `smoke_mgs_dual_path_mps.json` 与 `smoke_mgs_stop_gradient_mps.json`：2026-07-29 dual-path A/B 机制烟测；
- `sci3_*`：曾为 SCI-Q3 矩阵准备的配置，其中 V1 正式协议已经退役；只有新的 V2 套件和 promotion gate 完成后才能重新授权长实验；
- `formal_*`、`pilot_*`、`ablation_*`、`sensitivity_*`：旧 V1 CUDA 结果的复现配置，只作历史证据，不应继续写入旧输出目录。

`run_all.py` 与 `run_sci3.py` 会主动阻断退役的 pilot/formal 路径。不要通过直接调用 `run_experiment.py` 绕过科学协议门禁。

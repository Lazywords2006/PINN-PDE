# 配置索引

- `code_integrity_trace_smoke_cpu_v4.json`：当前工程完整性 smoke；
- `smoke_mgs_*`：MPS dual-path/stop-gradient 机制 smoke；
- `sci3_*`、`formal_*`、`pilot_*`、`ablation_*`、`sensitivity_*`：退役 V1 的历史复现
  配置，不得作为 V2 入口或写入旧结果目录。

V2 P3 使用显式、可恢复的 Python 入口，不读取这些旧 JSON：

```bash
python scripts/run_p3_pilot.py --help
python scripts/evaluate_v2_final.py --help
```

`run_all.py` 与 `run_sci3.py` 会阻断退役长实验。不要绕过门禁运行旧 V1 正式矩阵。

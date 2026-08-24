# 配置索引

- `code_integrity_trace_smoke_cpu_v4.json`：当前工程完整性 smoke；
- `smoke_mgs_*`：MPS dual-path/stop-gradient 机制 smoke；
- `sci3_*`、`formal_*`、`pilot_*`、`ablation_*`、`sensitivity_*`：P2 final 之前生成的历史
  配置，不得直接作为当前 SCI-Q3 supplement 的正式入口。

当前 P2 结果使用显式、可恢复、SHA 绑定的 Python 入口，不读取这些旧 JSON：

```bash
python scripts/run_p2_pilot.py --help
python scripts/evaluate_p2_final.py --help
```

`evaluate_p2_final.py` 已经执行一次，当前只允许查看帮助或审计源码，禁止再次运行。
新的 supplement 配置必须先重新审查方法、公平预算、suite 和成功线，再写入独立目录。

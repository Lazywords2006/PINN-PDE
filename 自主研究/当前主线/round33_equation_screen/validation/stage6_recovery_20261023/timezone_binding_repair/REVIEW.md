# 恢复证据时区等价比较修复

原 Gate attempt 1 失败于 `inventory['tasks'] != prior['tasks']`。修前 runner、测试源和失败 Gate 日志先保全到 `before/`，哈希见 `before_manifest.json`；原日志、manifest、事故快照和全部早期证据均未覆盖。

`task_binding_differences.json` 对两份实际证据做递归比较（含类型和列表顺序）。30 个任务之间只有 42 处差异，均为 21 个原活动任务及其 attempt 的 started_utc。例如原状态 `2026-10-22T16:08:04.387960+00:00`，inventory 是 `2026-10-23T00:08:04.38796+08:00`，两者表示同一时刻。未发现 PID、配置、命令或其他字段差异。

新增 `same_recovery_inventory_tasks` 只允许下列两个结构位置使用带时区的同一绝对时刻比较：

- `tasks[i].started_utc`
- `tasks[i].attempts[j].started_utc`

时间必须是带 `Z` 或 `±HH:MM` 的完整 ISO 日期时间；缺时区、无效日期、非法 offset、非字符串均拒绝。整秒使用时区转换，小数秒单独保留所有位并仅移除尾部零，避免 datetime 的微秒截断使 100ns 改动被误认为相同。没有时间误差容限。

其他位置按 JSON 值、类型、字典键集合、列表长度及顺序精确比较；同名 started_utc 出现在 config 等其他位置时不作时间等价处理。恢复 manifest 和各文件 SHA-256 的验证维持原样，原始证据不重写、不标准化落盘。

完整当前源码 Torch 回归 **110 passed / 0 failed / 0 error / 0 skipped，4.79 秒**，日志和 XML 为本目录 `pytest_attempt1.log/.xml`。新增 29 项覆盖等价时区和小数零、两个允许位置的无时区/无效/移动时间、100ns 改动、相同但无效的时间、PID/配置/命令/字段/类型改变，以及 recovery_lineage 的正负控集成。

随后只读调用实际 `recovery_lineage`，使用原封不动的恢复 manifest，SHA-256 为 `237609b2ffb7c31f77ac53c1d281bc6e5e03ade97367505e07116835c205c508`。正控通过：21 原活动任务、21 个配对、42 个实测 exit 0；manifest 及 7 个绑定 artifact 的前后 hash 相同。完整结果与调用脚本见 `real_manifest_lineage.json`、`real_manifest_probe_attempt1.log`、`probe_real_manifest.py`。

该正控验证恢复来源、身份与退出证据，没有调用 Gate、Run、完整结果数值复算或训练。新 Gate 仍由根代理在独立审查后执行。此次仅修改 runner 的证据比较和对应测试；训练源码、协议、真实结果和原证据未改，未提交。

历史 hash 复核另发现一项已存在的差异：v1 报告记录的 RECOVERY_ROUTE.md hash 为 `9d18db...`，当前为 `a3197b...`；当前文件逐字节等于本任务开始前 HEAD `352af9c` 中已提交的版本。本次保留该文档与旧报告，在新证据中明确记录既有差异，不将它写为“全部历史 hash 一致”。其他 v1/v2/测试隔离证据均匹配其记录。

# 恢复证据时区绑定：独立限定审查

日期：2026-10-23（UTC+8）。
结论：**接受同瞬间格式比较修复，限定范围内未发现身份绑定放宽。可以由根节点重试既定新Gate流程；当前审查不等于Gate、完整产物验收或恢复派发通过。**

## 范围及差异

本次只审查runner/test的时区增量、对应测试、真实不可变manifest和指定历史证据。未重复整个v2、文献或旧398文件审查；未调用Gate/Run、训练、终止进程或读取checkpoint内容。

独立AST比较确认：runner仅新增 `same_recovery_inventory_tasks`，并在 `recovery_lineage` 的原task清单比较处调用它；其他既有生产函数不变。旧测试函数全部不变，新增一个fixture和5个测试函数，参数化后共29项。

| 当前源码 | SHA256 |
|---|---|
| stage6_runner.py | a2fd8483ed9faa72b25ec6977441522d7897bc6a06b52321a698db4801952e18 |
| test_stage6_runner.py | 5294632eb59732564d22407369a7a9a9402a40a0d2292159a4a4602f002a3ed7 |

12个门禁源和16个本次工程证据文件哈希均独立核对一致；科学训练源、方程、协议、供应商及launcher未改变。

## 时间比较边界

只在传入task列表的以下位置允许时间格式差异：

- `tasks[i].started_utc`
- `tasks[i].attempts[j].started_utc`

时间必须是字符串、完整日期时间并带Z或±HH:MM；无时区、非法日期、非法offset或非字符串均拒绝，两个相同但无效的时间字符串也不会通过。

实现将整秒转换为UTC，小数秒保留原始所有数字，仅去掉尾部零。没有float比较、微秒截断或容差窗口；100ns及更小的真实变化仍不相等。其余JSON值先检查类型，再检查字典键集合、列表长度和顺序及递归值。其他位置的同名started_utc、finished_utc等字段不会获得时间等价豁免。PID、命令、配置、创建FILETIME、原门和证据哈希守卫均未删除或改松。

例如 `2026-10-22T16:08:04.387960+00:00` 与 `2026-10-23T00:08:04.38796+08:00` 可匹配；增加末位100ns则拒绝。它解决序列化显示差异，不忽略真实时间差。

## 独立执行证据

实际执行低负载AST/原生测试：**31 passed，0.36秒**，未导入Torch。

- 从实际测试源抽取29个新增正负控，覆盖等价时区/尾零、允许位置的无时区/无效/移动时间、100ns偏移、相同无效字符串、PID/config/command/字段/type变化及recovery_lineage集成。
- 独立增加高精度测试：超过微秒精度的小数表示可按尾零规则匹配，1e-20秒真实差异拒绝；非允许finished_utc格式差异及attempt PID的int→float均拒绝。
- 独立执行实际冻结manifest的只读生产lineage正控。生产源码通过AST提取执行，配置dataclass、METHODS与validate_config均取自实际代码；没有运行Torch模型、Gate、Run或结果数值验证。

独立运行目录：`D:/CodexRuntime/runs/r33_stage6_20261022/independent_timezone_review_20261023_0450/`。

| 文件 | SHA256 |
|---|---|
| pytest.log | 8d0b1a8193b0404dcf95b5d2f6e75e3b67a5b2a489ac08f7230abba95df65c2c |
| pytest.xml | d6e0e059f869c755780edbebcc31178a33d0dbc6e7183f4094a0883e2afcf8ce |
| independent_timezone_checks.py | a162f335581c0d8e3218e5283b7a6b1b2163a7c75371341666a8fbe8366eb7c8 |
| real_manifest_probe.json | 6cc8aa8035ea2abe8c72a2b2f4237ed9ef85e157a8c98c6662cb840cd9b04b55 |

工程代理执行的完整Torch回归为 **110 tests / 0 failures / 0 errors / 0 skipped，4.79秒**。本审查没有重跑整套，已独立核对日志、XML和绑定哈希：

- `pytest_attempt1.log`：396407eb91da3ce9132b99068ba46c1314330b426b16fdb8497d5222d4f7db04
- `pytest_attempt1.xml`：863294524a575e442038c0d2b7446d45d3d95bca6e1a431586e4c7ff17b578c6

## 实际manifest与原始证据

manifest固定SHA256为 `237609b2ffb7c31f77ac53c1d281bc6e5e03ade97367505e07116835c205c508`。

独立只读正控通过：原21任务、21个launcher/worker配对、42个实测零退出。manifest及7个artifact的前后哈希完全一致：

| artifact | SHA256 |
|---|---|
| observer_events | 1b735175683fa1fc399bd2c6da55e49da82d54502c6383bd7201913c6466654a |
| observer_source | cd8da5fc954aa99019efab13eae4b77086b462f16672db9a4ce92edf571c7957 |
| runner_stderr | b077c0c10f64e120c52cc3fc91c48315deddc426b448681bb68cd2119c7afeea |
| process_inventory | 8e3606ac01cdf6868dc5cd5a97e7094af69678c03ac663f4d1a65159913659d7 |
| prior_status | 834ae2f4123a1298a25b02f906b4df69f1b1723e74b0491dc4a2db0128b6dc89 |
| incident_manifest | d9bcc4ca6cdd8dc03ec940486a5d70c1e3f4d88a22d614847c36fb098cd738b4 |
| prior_gate | bb7250d65bfee8b44858c2ae734e540eee0bf7d26e2d5a68bbc2b7d40ff6e898 |

对真实inventory与prior task列表独立递归比较，恰有42处原始字符串差异，全部落在上述两个允许位置；没有其他字段或类型/结构差异。原始列表直接比较仍不等，修后的同瞬间比较通过。原始证据没有重写或规范化落盘。

该lineage检查会验证绑定来源和退出身份，并检查原任务JSON存在；它没有调用完整ResultValidator，不证明base/model权重、预算计数或参考解数值重算已经验收。

## 历史保留与已知指南差异

独立核对11项指定旧记录均保持原哈希：v1/v2/测试隔离独立报告、79通过/2失败原件、81通过原件及首次新Gate失败日志。修前runner、测试源和Gate失败日志的before快照也保持清单哈希。首次Gate失败仍作为失败历史保留，不改写成当时已通过。

**RECOVERY_ROUTE.md是明确的历史差异**：v1证据记录9d18db30417753a3442e4f35856114a262862f077d68b160db123156362c89ff，当前为a3197bb6fdb6dd60fbd421d713b689d06d26c18360dd39d1a34f94657a39d02e。独立读取Git确认当前文档逐字节等于本次修复前已提交的352af9c版本；该提交更新操作状态说明。它不在manifest的7个硬绑定artifact中。本报告不把可变指南误当原始证据，也不宣称全部历史文件现值都与旧报告一致。

## 可操作结论

- 同瞬间格式误拒绝已在静态、独立31项测试及实际不可变manifest只读正控范围闭环；没有发现新的阻断项。
- 根节点可以重试既定新Gate，必须绑定当前runner/test指纹及完整110项测试证据，原manifest和7artifact继续原样使用。
- 新Gate和原21完整bundle/预算/参考重算仍须按既定机制完成；通过后才可派发剩余9项。此审查不启动这些操作，也不把42个零退出等同于21项数值验收或30/30完成。
- 科学效果、τ/S6-SOAP判据不在本次审查范围，未评为通过。

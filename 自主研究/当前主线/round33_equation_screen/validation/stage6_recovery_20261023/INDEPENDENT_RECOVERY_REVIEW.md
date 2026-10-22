# Stage6 独立恢复工程审查

审查版本：v1 冻结补丁；日期：2026-10-23（UTC+8）。
结论：**BLOCKED：发现可使旧任务静默重训的静态缺陷；完整回归及真实恢复同时保持 PENDING。** 本报告不是论文审查，不修改科学协议。

## 证据范围

- 原 runner 42100 在 01:08:49 左右因 status 临时文件原子替换 WinError 5 退出，异常处理二次保存再次失败。只确认替换拒绝，未确定具体占用者。
- 故障持久状态是 21 running、9 queued、0 completed；状态时间为 01:08:47，不能把它当成当前进程进度。
- 独立重算 incident 清单 20/20 快照哈希一致；原 398 文件全量重算无不符，清单 SHA256 为 `9953f34410cfba34efa1927311a819b0cb82460d6ec30d3c92f9a538c29fea28`。
- 旧 21 项源码身份由原工程门、12 项冻结源码、派发 attempt 和创建时间/完整命令行对应关系保全。这里是来源链证据，不是对进程内存中代码的测量。
- 监督器 90488 的 42 个已核验 HANDLE 覆盖 21 launcher 和 21 实际 worker、21 个唯一 job。冻结证据尚无 process_exited 或 observer_completed。附着成功不代表训练成功。
- v1 runner SHA256：`468423c2e2fc6453c8a1d71eed2d12f0553b980c551a5fb4be133e3215be9b0f`；测试源：`fa43f9290fb1fa952732bd2af45889f52b473caf1c7eacde4423bf46ee3525bc`。
- 已检查实际实现、相关测试、`runner_fix_review.diff`、`engineering_repair_evidence.json`、`RECOVERY_ROUTE.md`、`git_blob_integrity.json`。11 项工程证据文件哈希独立重算吻合。Git 30 个 blob 逐字节保全的结果来自已绑定的工程证据；独立审查另已核验 20 个 incident 快照。
- 只读工程检查和轻量 AST 仿真；未导入 Torch 启动训练，未启动或结束任何真实训练进程，未改代码或科学文件。

## v1 阻断发现

### REC-P1-001：Gate 后旧产物缺失会被重新排队

位置：v1 `stage6_runner.py` 的 `run` 预验证循环（约 932–936 行），关联 `new_state`、`existing_identity_checks`、`recovery_lineage`。

`recovery_lineage` 仅在 Gate 时要求原活动任务存在 JSON；Run 只重新核验恢复证据文件哈希。随后 `new_state` 把原任务重置为 queued，预验证循环仅在 `out_path.exists()` 为真时调用 ResultValidator。若 Gate 后某个旧任务的全部产物被移走，或只剩一个合法 checkpoint，身份扫描可以放过；该原 exit=0 任务便仍是 queued，可被 execute_queue 重新训练。相同模式也可能影响已完成任务在后续重启时的产物缺失。

独立复现使用 AST 提取的真实 `run/new_state/require_reviewed_previous_attempts`，其余依赖替身化，不导入 Torch、不调用 Popen、不训练。设一个原 exit=0 任务、一个新任务且旧产物缺失，实际得到：

```json
{"source_sha256":"468423c2e2fc6453c8a1d71eed2d12f0553b980c551a5fb4be133e3215be9b0f","validator_calls":[],"queued_task_ids_at_execute_queue":["old","new"],"original_exit_zero_task_wrongly_queued":true}
```

这证明运行前核验的控制流缺口，不是实际重复训练事件。

必须修复：每次 Run 在任何派发前，对 recovery lineage 的 original_active_jobs 以及此前已完成的任务强制要求完整 bundle 并调用 ResultValidator；缺失必须抛错停审，不能通过 exists 分支跳过。新增 Gate 后删除 JSON/整体 bundle、合法 checkpoint 仍在、此前 completed 缺失等负控，证明未调用 Popen。问题已反馈根节点；待 v2 定向复审。

## 已确认的实现改进与验证边界

| 项目 | v1 静态判断 | 已执行证据 |
|---|---|---|
| 原子 JSON 替换 | 最多 10 次/4.75 秒退避；不先删目标；每目标每 PID 一个失败 tmp | 原生/合成测试已覆盖 |
| 永久状态写失败 | 停派发、30 秒节流重试、持续 poll/drain；应急文件及 stderr 回退 | 相关测试存在；完整当前源回归 PENDING |
| validation 写失败/最终状态失败 | 停派发、保留真实退出，不把失败的最终保存称 completed | 相关仿真测试存在；完整当前源回归 PENDING |
| running checkpoint 监测 | 仅 stat 的 mtime/size，禁止打开/反序列化；未解析时明确说明 | 原生/合成目标测试覆盖 |
| 非 running checkpoint 解析 | 持有同任务锁后读快照，关闭句柄再反序列化 | 原生/合成目标测试覆盖 |
| 旧退出来源 | 对 launcher/worker 成对核验，绑定 argv、创建 FILETIME、父子、路径与 observer 源/日志 | 静态逻辑及合成测试存在；真实退出尚无 |
| 原/新源码谱系 | 原 21 绑定原 gate，后续 attempts 绑定新 gate；不回填旧进程为新源码 | 静态逻辑具备，真实恢复待执行 |
| 完整产物预验证 | Gate 时有检查，但 Run 仍可绕过缺失旧产物 | **REC-P1-001 阻断** |

首次完整测试是 **70 passed / 1 failed（71 项）**，对应首次补丁源码，不是当前冻结源码的完整通过。失败证实 FILE_SHARE_DELETE 不能保证打开目标总能被 os.replace 覆盖；已保留原日志/XML和当时源码哈希。日志另有 Torch 导入 WMI `0x8007000e` 栈，测试继续完成；不能据此断言真实 worker OOM，也不能宣称零 warning。

修正边界后的 **9/9** 是从生产代码 AST 提取 I/O 函数和选定测试体的轻量原生/合成检查，未导入 Torch。独立读取其 JUnit 确认 9 tests、0 failures/errors/skipped；这不是完整 runner 回归、21 worker 退出证明或科学接受测试。

根节点 02:22 提供的资源读数为 free physical 4.50 GiB、free commit 2.21 GiB、commit 95.27%。完整当前源回归保持 `PENDING_RESOURCE_HEADROOM`；本审查没有为了补测试而再导入 Torch 增加内存压力。该读数由根节点提供，非本审查重新测量。

## 恢复必须满足的精确门

1. **不接管活动训练**：等待原 42 HANDLE 全部 signaled 后记录 GetExitCodeProcess。PID 消失、259/STILL_ACTIVE、日志 START、checkpoint 或结果存在均不能代替实际退出；每 job 必须唯一 launcher+worker 配对，不能少项或重复。
2. **失败和未知停审**：缺退出、身份不符、observer_error、非零退出均不得走本次自动恢复路线。不能换种子或静默重新训练。后续任何已知失败的同配置恢复须单独记录明确处置。
3. **旧 21 强制完整预验证**：exit=0 仍须 JSON/base PT/model PT、任务/冻结配置/finite 检查、预算计数、原 N64/GL200 与 N96/GL400 重算和独立残差门；全部完成后方可新派发。旧产物缺失必须停审，不能从 checkpoint 自动补跑。
4. **剩 9 新门禁**：新 Gate 绑定修复后源码、完整当前源测试、冻结 Python 3.12.6/Torch 2.14.1+cpu/NumPy 2.5.3、旧 398 与复算证据；Gate 与 Run 均绑定同一 recovery manifest 及全部证据哈希。未知修改不得覆盖原状态/历史。
5. **保留源身份**：原门 SHA256 `bb7250d65bfee8b44858c2ae734e540eee0bf7d26e2d5a68bbc2b7d40ff6e898`、incident 原 status/tmp/日志和旧源码均不改。原21沿用旧谱系，后9绑定新门；真实退出和 attempt 时间如实补录，不把孤儿训练时间冒充 runner 活跃时间。
6. **任务与科学协议不变**：仍为 τ 灵敏度12 + 固定官方 SOAP64 对照18，共30 tuples，原问题、种子0/1/2、网络、配点、20000梯度调用/L-BFGS≤3000不变。SOAP初始化调用不赠步，19999参数更新。τ结果只描述，不替换主τ=0.1或倒选优化器。S6-SOAP原判据不变，不替换B-1/B-2/G2或当成发表门槛。
7. **资源与期限不改**：统一队列最多24单线程；物理可用<4 GiB或commit>90%停新派发；保留原48h deadline，只有明确资源复盘记录后才可开启新窗口，不以恢复悄悄重置。
8. **失败状态可追溯**：保留 attempts、退出码、failure_history、source_lineage、原398文件及哈希。任何持久化/验证故障停止新派发并 drain，不能丢活动进程或把部分完成称30/30通过。

## 当前裁定及后续复审

- v1 静态恢复路线：**BLOCKED_BY_REC-P1-001**。
- 本机原生 I/O 目标检查：**PASS，限9项范围**。
- 当前源完整 runner 回归：**PENDING_RESOURCE_HEADROOM**。
- 真实 HANDLE 退出/旧21完整产物复算/新Gate/后9派发/最终30项：**PENDING，未通过**。
- 科学效果与 S6-SOAP/τ 结论：**NOT_EVALUATED**。

修复 v2 后追加定向复审记录并保留 v1 缺陷与冻结指纹；不得把本报告覆盖成没有历史问题的整体 PASS。

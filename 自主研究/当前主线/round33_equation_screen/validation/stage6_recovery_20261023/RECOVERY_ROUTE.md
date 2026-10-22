# Stage6 编排故障修复与恢复路线

状态：修复代码可供独立静态审查；**完整修复后回归仍为 PENDING，恢复派发被阻断**。本轮没有重启 runner、派发训练、终止原 worker、修改科学协议/训练源码/系统页文件。

## 事实与当前保护

原 runner 42100 的日志确认 `status.json.42100.tmp -> status.json` 在 `os.replace` 出现 WinError 5；异常处理再次保存同一状态失败后退出。日志没有识别造成替换拒绝的具体占用者，不归因于某个 reader、杀毒软件或内存不足。

原 gate、12 个冻结源、状态/失败临时状态、门禁测试与故障日志共 20 文件保全于 `incident_snapshot_20261023_013453_945/`，清单含逐文件 SHA-256。该快照的原 gate SHA-256 为 `bb7250d65bfee8b44858c2ae734e540eee0bf7d26e2d5a68bbc2b7d40ff6e898`。

隐藏监督器实际 PID 90488，launcher 84736；42/42 句柄附着及身份核验成功，覆盖 21 原 launcher 和 21 实际 worker。只持有 `SYNCHRONIZE|PROCESS_QUERY_LIMITED_INFORMATION`；以创建 FILETIME、完整 argv、命令行、可执行路径、父子关系绑定原 status。仅在 HANDLE signaled 后记录 GetExitCodeProcess，不从 PID 消失、结果文件存在或 STILL_ACTIVE 推断退出。运行证据目录：`D:/CodexRuntime/runs/r33_stage6_20261022/orphan_observer_20261023_0138/`。

## 修复范围

- JSON 原子替换最多 10 次，退避总计 4.75 秒；永久失败保留原目标，最多每目标每 PID 一个失败临时文件，不先删除目标。单次重试耗时之外的调度延迟不受此上界约束。
- status 持久化最终失败立即停止新派发，继续 poll/drain 已有进程；重试主状态保存节流为 30 秒，退出事件和最终状态另写唯一应急文件，必要时退回已打开 stderr。后续主状态写恢复不会自动恢复派发。
- validation 报告写失败同样停止派发并 drain；外层异常中二次状态保存失败不会覆盖原异常。未知退出不自动重跑，已知失败须逐项明确 `--retry-failed-job`。
- Windows JSON 读使用共享删除。**本机原生测试证明即使 FILE_SHARE_DELETE，保持打开的目标仍可能拒绝 os.replace。** 因此 running checkpoint 仅 stat mtime/size，标记 `progress_unavailable_reason`，绝不打开内容。非 running 分支须先取得并持有任务锁才能解析；读句柄关闭后再 BytesIO 反序列化。冻结 `pinn1d.py` 不改。
- 恢复 gate 通过可选 `--recovery-manifest` 绑定原来源和全部退出证据；原训练/协议/供应商 hash 必须不变。缺失、重复、身份不符、未完成、未知或非零退出一律拒绝这条自动接续路线；exit 0 缺 JSON 也拒绝，不从 checkpoint 重新训练。
- 原 21 项随后仍必须通过现有 ResultValidator 的完整 bundle、预算、N64/N96 与既定残差复算，全部预验证结束才允许派发余下项。原 attempt 补记实测退出及观测墙钟，原/新 gate 来源分别保存；48h deadline、全部 30 tuples/config/预算和旧 398 绑定不变。

## 验证边界

首次完整测试：70 passed / 1 failed，保留 `pytest_attempt1.log/.xml` 与当时源码 hash。失败的是“共享删除保证打开目标可直接覆盖”的过强假设；未将它报为通过。日志另含 Torch 导入时 WMI 的 `0x8007000e` 异常栈，测试继续跑完；它只归本次测试进程，不据此判定任何训练 worker OOM，也不宣称零 warning。

修正边界后的轻量原生/合成检查：`native_io_checks.py` 从实际 runner 与测试文件 AST 提取 I/O 函数及测试体，不导入 Torch，9 项通过（`native_io.log/.xml`）。涵盖真实 Windows 句柄锁释放后重试成功、共享删除允许重命名、有限重试/失败临时文件有界、活动 checkpoint 从不打开、持锁 checkpoint 不解析、状态按 running/failed 分流。它不能代替完整 runner 回归。

后续轻量 GlobalMemoryStatusEx 读到 free physical 4.07 GiB、commit 96.00%、free commit 1.872 GiB，按根节点决定暂缓再次启动完整 Torch/pytest。待余量回升后必须补跑完整相关测试；下述 Gate 内部也会强制重跑完整测试，任何失败阻止 Gate/Run。

## 根节点协调的具体步骤

1. 保持原 21 worker 自然运行，监督器留存 42 个实测退出。`events.jsonl` 必须最终以 `observer_completed` 且 `all_handles_signaled=true` 结束，全部附着成功、身份已验证、42 个退出均为 0。若非零/未知，保留 checkpoint 与真实退出证据，先做同配置工程恢复评审；禁止从本批结果挑选任务。
2. 确认全部任务锁释放；新 Gate/Run 自带此检查，不绕过锁，不凭 PID 缺失代替。对剩余并发上限依据当时资源重新决定，本文件中的 8 是保守示例，不是峰值安全保证。
3. 在固定项目目录，完成以下**证据准备命令**。它只归档/绑定证据，不启动训练。首次创建目录/manifest；若已存在先审查，不覆盖旧版本。

```powershell
Set-Location -LiteralPath 'E:/PINN-PDE/自主研究/当前主线/round33_equation_screen'
$r33Recovery=Join-Path (Get-Location).Path 'validation/stage6_recovery_20261023'
$r33Incident=Join-Path $r33Recovery 'incident_snapshot_20261023_013453_945'
$r33Observer='D:/CodexRuntime/runs/r33_stage6_20261022/orphan_observer_20261023_0138'
$r33Closed=Join-Path $r33Recovery 'completed_exit_observation'
New-Item -ItemType Directory -Path $r33Closed -ErrorAction Stop | Out-Null
Copy-Item -LiteralPath (Join-Path $r33Observer 'events.jsonl'),(Join-Path $r33Observer 'attached.json') -Destination $r33Closed -ErrorAction Stop
$r33Paths=@{
 prior_gate=(Join-Path $r33Incident 'engineering_gate.json')
 prior_status=(Join-Path $r33Incident 'status.json')
 process_inventory=(Join-Path $r33Incident 'process_inventory.json')
 observer_events=(Join-Path $r33Closed 'events.jsonl')
 observer_source=(Join-Path $r33Recovery 'observe_orphan_exits.py')
 runner_stderr=(Join-Path $r33Incident 'runner_20261023_000801_094.stderr.log')
 incident_manifest=(Join-Path $r33Incident 'snapshot_manifest.json')
}
$r33Bindings=@{}
foreach($r33Key in $r33Paths.Keys){$r33Bindings[$r33Key]=@{path=$r33Paths[$r33Key];sha256=(Get-FileHash -LiteralPath $r33Paths[$r33Key] -Algorithm SHA256).Hash.ToLowerInvariant()}}
$r33Manifest=Join-Path $r33Recovery 'recovery_manifest.json'
if(Test-Path -LiteralPath $r33Manifest){throw '恢复manifest已存在，禁止覆盖。'}
@{schema='r33_stage6_recovery_manifest_v1';incident_id='status_replace_winerror5_20261023';artifacts=$r33Bindings} | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $r33Manifest -Encoding UTF8
```

4. 先完成独立代码审查；资源允许时补齐当前完整回归，保留新日志/XML，不覆盖首次失败证据。以下命令**仅测试，不训练**：

```powershell
$env:TEMP='D:/CodexRuntime/temp'; $env:TMP=$env:TEMP
$env:PYTHONPYCACHEPREFIX='D:/CodexRuntime/cache/pycache'
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:OMP_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'; $env:NUMEXPR_NUM_THREADS='1'
& 'D:/CodexRuntime/venvs/r33-torch214/Scripts/python.exe' -m pytest test_stage6_runner.py -q --basetemp 'D:/CodexRuntime/temp/r33-stage6-recovery-final' --junitxml 'validation/stage6_recovery_20261023/pytest_final.xml'
```

5. 仅在上述证据完备、原 worker 全部结束后，由根节点创建新 Gate；此操作会重新验证旧 398、原结果身份、固定环境和全部 runner 测试，但不训练。新 Gate 会覆盖当前标准工程门，原门已逐字节保全并通过 recovery lineage 绑定：

```powershell
& 'D:/CodexRuntime/venvs/r33-torch214/Scripts/python.exe' stage6_runner.py --gate --runtime 'D:/CodexRuntime/runs/r33_stage6_20261022' --recovery-manifest 'validation/stage6_recovery_20261023/recovery_manifest.json'
```

6. **只有新 Gate 成功后，根节点才执行恢复派发命令**。固定任务集合没有按误差筛选；预验证过的原 21 跳过，正常情况下只派剩余 9 项：

```powershell
./run_stage6.ps1 -Action Run -Workers 8
```

任何失败/未知退出、bundle 缺失、重算不通过、证据变化或 48h 复盘门到期均停止此路线。不得自动改 manifest、丢弃历史或另起重复训练来绕过。

## 最终分析兼容性与时间口径

最终 completion_gate 仍读标准 status / results_validation / summary / engineering_gate；字段、30/30 数量、原始 90 文件、旧 398 文件及科学判据不变。新工程门 current source_hashes 绑定修复代码，原 21 来源保存在 recovery lineage 与 runtime/status.source_lineage；分析现有完整 runtime_status 元数据会保留这条链。两份最终报告 results 仍同源一致。

原 runner 故障后的孤儿训练时间不冒充 runner 活跃墙钟。原 attempt 的 wall_seconds 按 HANDLE 退出观测减原派发时刻补记，含观察轮询延迟；新增 batch_elapsed_seconds 反映首次开始到当前时刻的总历时，runner_wall_timing_note 解释口径。最终 30/30 分析尚未运行，不能把接口兼容或工程测试写成科研结果通过。

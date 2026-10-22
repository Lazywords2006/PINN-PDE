# R33 第二阶段运行器工程交付

完成时间：2026-10-23 00:00（UTC+8；目录日期沿用本批立项日 20261022）。本材料只说明工程门，不宣称新研究结果已经完成。

## 已完成的检查

- 修订 6 预注册提交固定为 `bfe89e3a07f1bb3bcc8e049d8d3d7ff95b4a647a`；Gate 检查该提交是当前 HEAD 的祖先，并逐字核对当前协议与该提交内容。
- 冻结 Python 3.12.6 / Torch 2.14.1+cpu / NumPy 2.5.3。原 71 项测试的日志 hash 与 6 个对应训练/方程/产物/残差源 hash 均匹配，复用已有通过证据；没有把本轮检查写成重新运行 71 项。
- 新运行器专项测试 **41 passed**，无失败、错误、跳过。覆盖统一队列并发上限、失败后停止派发且排空活动任务、48 小时门、内存暂停后恢复、同身份重试、成功任务不重复派发、锁与孤儿 worker 防重、CLI 配置完整传递、checkpoint 进度缓存、旧数据保护和重算/预算检查。使用模拟调度与合成验证数据，未执行研究训练。
- 旧 176 个结果对应 **398 个原始文件**逐一 SHA256 相同；原清单来自 `validation/stage5_analysis_20261022/analysis_evidence.json`。
- E1 / E3 的 N64 与 N96 参考解在五个输出时刻、401 空间点的最大绝对差分别为 **6.8473e-13 / 3.6768e-13**，通过 1e-8 门。
- PowerShell 启动器通过语法解析。运行器没有修改 `pinn1d.py`、`problems.py`、旧 tag、旧协议判据或既有默认值。

## SOAP 来源补核

原 71 项工程门未单列供应商源码，因此本轮通过 GitHub 插件 `fetch_blob` 重新取回固定上游 blob `a6362cc9ed2f50ed299204eb3bf07715e7280757`，原内容与出处保存在 `soap_upstream_blob.json`。对内容重新计算 Git blob SHA，完全匹配。

上游内容 19180 字节，本地 `third_party/soap_official.py` 为 19181 字节；差异严格限于本地原有文件最后追加的一个 LF，其他代码与空白字节完全相同。本地文件 SHA256 为 `6b2328e53fb3cb58cf18b21e706f6f17e7f7dcac83c8abb1053fa74d6e0ca592`，本轮未改供应商文件。Gate 显式核此差异并冻结本地 hash，不笼统称字节完全等同。

## 调度和停止行为

30 项任务固定为两档 τ 各 6 项及 SOAP64 18 项。单一父进程维护队列，每项只起一个独立 Python worker；worker 直接调用现有 `screen.run_one`，不会嵌套 `screen.py` 的进程池。所有 Config 字段均通过 `--set` 显式传递，worker 在训练前与冻结矩阵逐项比较。

并发上限 24、每进程单线程、Normal 优先级、后台隐藏窗口。5 秒错峰派发以观测内存爬升；物理可用 <4 GiB 或系统提交 >90% 时只暂停派发，恢复后继续。达到上限不是保证同时开满 24；资源门可以限制实际并发。

状态每 2 秒刷新；checkpoint 按路径、mtime_ns、文件大小缓存，只有变化时读取，不反复载入同一大文件。首个 500 步 checkpoint 出现前显示“尚无首个 checkpoint”，不编造中间步数。

工程失败或 48 小时门均停止新派发，已启动任务继续到完整保存或自身报错；运行器不强杀 checkpoint 写入者。此时结束时间可晚于 48 小时。重启保留先前 48 小时截止，避免通过反复重启自动续期；完成一次资源复盘后可显式使用 `--resource-review-note '复盘结论'` 记录新窗口。该开关不改变任何训练配置或科学任务预算。

父进程锁和逐任务 OS 锁防止重复写入；父进程意外退出后仍存活的 worker 会保留任务锁，再启队列先检查锁并拒绝重复。正常工程失败后只允许原任务、原种子、原配置从 checkpoint 恢复。完成结果重新核身份/完整性/指标，绝不覆盖；尝试记录与失败历史保留。

## 使用方法

在 `E:\PINN-PDE\自主研究\当前主线\round33_equation_screen` 下：

```powershell
.\run_stage6.ps1 -Action Plan
.\run_stage6.ps1 -Action Gate
.\run_stage6.ps1 -Action Run -Workers 24
.\run_stage6.ps1 -Action Status
```

本次 **Gate 已成功执行，未启动 Run**，由父代理审阅/提交后启动。源文件若再改，先重新 Gate。裸运行 PS1 默认 Status，Python 裸入口拒绝启动，防止意外开训练。

日志、锁、状态和 checkpoint：`D:\CodexRuntime\runs\r33_stage6_20261022`。`status.json` 包含 queued/running/completed/failed、PID、命令、尝试记录、可读 checkpoint 位置、开始时间和累计运行器墙钟。各尝试日志独立保存，后台启动日志带时间戳，不截断此前日志。

每个成功任务都会从完整 bundle 重载，重算原 N64/GL200 与 N96/GL400 序列，并按 rtol=1e-5、atol=1e-9 对照记录；随后计算与上一阶段一致的独立 heldout 残差。损失、初值残差、体/迹序列、完整配置、实际 L-BFGS closure/内部迭代和轨迹墙钟统一保存到 `results_validation.json`，批次结束写 `summary.json`，包含全部预注册任务状态和失败历史。SOAP 记录 20000 梯度调用，以及按冻结算法语义推得的 19999 次参数更新；明确更新数是语义推得，不能冒称新增了训练内计数器。

## 文件范围与证据边界

本次仅新增 `stage6_runner.py`、`run_stage6.ps1`、`test_stage6_runner.py` 及本目录材料。`engineering_gate.json`、`pytest.log`、`pytest.xml` 为本轮检查证据。工程门说明可以开始已注册训练，尚不证明完整训练成功、任何方法效果或论文结论。

## 启动前兼容性修复记录（2026-10-23）

父代理提交运行器后，首次使用系统 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File run_stage6.ps1 -Action Run -Workers 24` 调用时，Windows PowerShell 5 把 UTF-8 无 BOM 的中文字符串按旧编码读取，出现 `ParserError`；这次失败发生在 Python 运行器启动前，未派发任何训练任务。此前仅在当前 PowerShell 宿主解析通过，验证范围未覆盖系统 PowerShell 5。

修复仅将 `run_stage6.ps1` 保存为带 BOM 的 UTF-8，脚本内容和调度行为不变。新增专项测试调用真实 `powershell.exe`，通过其 `Parser.ParseFile` 只读解析启动器并确认版本为 5；该测试不执行启动器、不启动训练。随后重新 Gate，更新启动器和测试源 hash；本次专项测试为 **42 passed**，原 71 项测试继续按源 hash 复用。此前 41 项记录作为首次工程门历史保留。

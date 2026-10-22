# Stage6 完成态复现补充（complete_v1）

本补充核对截至 2026-10-23 06:29:36（UTC+8）的 Stage6 完成态，绑定正式完成归档和分析版本 `complete_v1`。本轮独立只读检查的 **613 个断言通过、0 个失败**；该结论限于下述运行证据、产物身份、已保存数值验收和复现材料的绑定，不是论文录用判断，也不增加科学效果结论。机器记录见 [completion_checks.json](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/reproducibility_complete_20261023/completion_checks.json)，逐文件 SHA-256 见 [input_hashes.json](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/reproducibility_complete_20261023/input_hashes.json)。

本轮没有导入 Torch、训练、启动 Gate/Run、重跑工程测试、重载模型、积分参考 ODE、读取活动 checkpoint 内容或重聚合数据/图表。新增 90 个已完成结果文件逐字节哈希；旧 398 个产物沿用正式门的逐字节检查，本轮重新核对其冻结清单哈希、488 映射中的保留关系及目录计数，未重读全部旧权重。

本地提交对象已确认 `7d3857ea93d28c620af51dbc3fdf88e581adae0d` 为 Stage6 全部 30 项与 complete_v1 归档提交。本补充不覆盖 [原复现说明](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/reproducibility/REPRODUCIBILITY_CN.md)或 [恢复时点说明](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/reproducibility_recovery_20261023/RECOVERY_REPRODUCIBILITY_CN.md)；两者所记“在途/待完成”仍是各自时点的真实历史。本文件更新的是完成字段。

## 1. 已完成字段与证据层级

| 层级 | 完成态核对值 | 证据与解释 |
|---|---|---|
| 精确任务 | 30 个元组，无缺项、重复项或额外项 | 状态、计划、Gate、validation、summary 六处身份集合一致；见逐项表 |
| 调度状态 | `phase=completed`；completed=30，running=queued=failed=0；任务 PID 全为空 | 冻结状态快照，不读取可变运行目录推断进度 |
| 逐项执行 | 每项恰好 1 个 attempt，exit_code=0；resume_checkpoint_present 全为 false | 原21与后9的退出证据来源分开，见第2节；不把状态字串单独当作真实退出 |
| 原21退出 | 21 worker＋21 launcher，共42个 HANDLE 均身份核验、exit 0 | 事件日志末行为 `observer_completed/all_handles_signaled=true`；已关闭日志的归档哈希一致 |
| 最终 runner 退出 | PID91632，HANDLE signaled、exit 0 | 保存的原生 HANDLE 观察转录，退出时刻 `2026-10-22T22:29:36.327882+00:00`；本轮没有重新观察已退出进程 |
| 产物保存验收 | validation 与 summary 均 complete=true、required=validated=30；逐结果内容一致 | 状态内逐项 validation 与两报告一致，全部 complete_and_recomputed=true |
| 数值验收记录 | 五时刻体/迹原记录、N64/GL200复算、N96/GL400稠密复算序列相容 | 本轮只对已保存数组以 rtol=1e-5、atol=1e-9复核相容性；不冒充一次新的模型重载或参考求解 |
| 独立残差记录 | PDE 8192；左Neumann、动态右端、初值各1024；RMS/max_abs有限且非负 | 这是保存的四分量残差记录完整性，不另设残差“成功阈值” |
| 三文件束 | 每项 JSON、base PT、完整 model PT 各一份；共90文件 | 三处 digest 绑定一致：逐项 bundle、完成归档、complete_v1原始输入映射；本轮重算新90哈希全部匹配 |
| 历史保留 | 旧398映射未增删或改写，最终 raw_sha256=旧398＋新90=488 | 正式Gate和summary的旧文件检查一致；本轮未重新执行旧398字节扫描 |
| 原期限 | 从首次开始起的原48小时期限未改；本批在期限内完成 | 首次开始为10月23日00:08:04.374697，原截止为10月25日00:08:04.374697，均UTC+8 |
| 预注册 | `bfe89e3a07f1bb3bcc8e049d8d3d7ff95b4a647a` | 计划、Gate、状态、validation、summary、归档和分析记录一致；未改科学判据 |
| 工程回归 | 新Gate绑定110项测试，failures/errors/skipped均0 | 只读取实际日志/JUnit及其哈希，没有再次运行；110项回归不证明科学改进 |
| 研究总量 | 14 tag，206份JSON/206份base PT/76份完整model PT，共488文件 | 目录元数据与488清单逐路径一致；文件计数本身不替代保存验收 |

完成态核心入口为 [completion_archive_20261023](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_20261022/completion_archive_20261023/archive_manifest.json)：归档恰好39文件，其中37个核心/日志文件由 `archived_files` 绑定，runner退出观察另有哈希绑定，加归档manifest本身。其余为30份worker捕获日志、2份恢复后runner日志，以及状态、验收、summary、Gate和计划。归档时间为10月23日06:32:14（UTC+8）。

完整逐任务记录见 [task_inventory.csv](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/reproducibility_complete_20261023/task_inventory.csv)。冻结 [task_plan.json](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_20261022/completion_archive_20261023/task_plan.json) 保存每项完整 worker argv 与配置；这些命令只作来源记录，本轮没有执行。

## 2. 原21与后9的源码和退出谱系

任务键为 `(tag, eq, method, seed)`。文件名 `hardic_layer` 对应方法值 `hardic+layer`。

| 批次 | 精确组成 | 派发/退出来源 |
|---|---|---|
| 原21 | 两个τ tag 的全部12项；SOAP seed0 的E1/E3×3构造共6项；SOAP seed1的E1×3构造共3项 | 原工程门、原worker源码；runner退出后训练继续；42个真实句柄退出由独立监督器补证 |
| 后9 | SOAP seed1的E3×3构造；SOAP seed2的E1/E3×3构造 | 原42全部退出、验收及新Gate后派发；新编排源码；原生Popen退出码记录为0 |

τ矩阵是 `sensitivity_tau003_v1`、`sensitivity_tau03_v1` × E1_heat/E3_fisher × hardic+layer × seeds0/1/2，共12项；SOAP矩阵是 `final_soap64_v1` × E1_heat/E3_fisher × vanilla/hardic/hardic+layer × seeds0/1/2，共18项。没有按结果筛选、漏掉失败种子或追加任务。

原21门SHA-256为 `bb7250d65bfee8b44858c2ae734e540eee0bf7d26e2d5a68bbc2b7d40ff6e898`，后9门为 `4572088adf9eb3010c4d483b6ae71a82087dd5bd41b35dcb38e0687f5666d6e3`。原21 runner哈希为 `7a2f55cd271cfd9d4355998d35b66a095a656aa46e260fc8c1dfeb83db2e870b`，后9为 `a2fd8483ed9faa72b25ec6977441522d7897bc6a06b52321a698db4801952e18`。两门12个源码/协议证据中只有 `stage6_runner.py` 和 `test_stage6_runner.py` 不同；训练、方程、SOAP供应商、launcher、协议等其余10项一致。后9当前12个源哈希仍与其门逐字节一致；原21的旧源身份从旧门/事故快照保留，没有倒填成修复后源码。

恢复manifest SHA-256为 `237609b2ffb7c31f77ac53c1d281bc6e5e03ade97367505e07116835c205c508`，其7个硬绑定artifact本轮全部哈希相符。42退出事件与Gate中21组worker/launcher记录逐项对应；监督器于04:40:32.177297结束，新Gate于04:54:34.833749形成，后9均晚于该门启动。原21保留 `supervision_interrupted=true`、worker和launcher退出码、旧门及恢复manifest；后9仅报告实际Popen退出码，没有捏造独立worker HANDLE字段。

全部30项 `resumed_at=[]`，没有从checkpoint续接梯度轨迹；本次“恢复”指恢复调度监督和保存验收，原21并未重新训练。原21的日志worker PID与独立句柄记录一致，全部30项的日志命令与冻结计划/attempt命令一致。后9日志中的worker PID保留原文，不混同为可能存在的venv launcher PID。

`RECOVERY_ROUTE.md` 是可更新操作指南，曾随 `352af9c1c8666ae6fca00d682eeb8e440f7d6997` 更新为当时81测试通过/等待退出；它当前哈希为 `20db4da69346024f4796465481570abff608aae572fcea348b5cd7366960d842`。该可追溯历史差异不属于本次时区修改，也不在manifest的7个硬绑定artifact中；不能声称所有历史材料的现值均与v1相同。本次未修改指南、manifest、事故快照或旧失败报告。

## 3. 预算和时间的完成口径

30项均为MLP 4×64，Adam/SOAP梯度调用名义预算20000，学习率0.001→0.00001；Adam/SOAP阶段体4096、每端边界256、初值256点；L-BFGS名义预算3000、块50，固定体8192、每端512、初值512。τ两档分别0.03/0.3使用Adam；SOAP组固定τ=0.1、optimizer=soap_official64、freq10、beta0.95。其余全部配置/argv逐项与计划精确一致。

保存的30项 `adam_gradient_calls=20000`、`lbfgs_budget_used=3000`、停止原因均为 `budget_exhausted`。实际L-BFGS内部迭代范围1880–3000、closure求值范围3211–3771；不能将3000名义块预算称为各项实际计算完全相同。12项Adam按冻结实现推得20000次更新，18项SOAP首次调用只初始化，推得19999次参数更新，不额外补一步。

沿用N04口径：`adam_gradient_calls` 是成功完成时按冻结循环配置写入的计数，不是另设的独立逐步观测器；SOAP更新数也是实现语义推断。`final_adam_loss` 是最后一次采样记录的更新前损失（完整预算为零基step19990），不是末步后重新评价；原字段名不改。L-BFGS内部迭代与closure计数来自保存的优化器状态，另列于逐项表。

| 时间量 | 保存值（秒） | 可解释范围 |
|---|---:|---|
| 从批次首次开始到完成的总历时 | 22891.57350254059 | 约6小时21分31.57秒，包含孤儿训练与恢复间隔 |
| runner会话累计墙钟 | 9286.097283363342 | 约2小时34分46.10秒，不包含runner退出后的孤儿间隔 |
| 30个attempt墙钟之和 | 372236.024538517 | 并行任务和；原21使用HANDLE退出观察，含轮询延迟 |
| 30条训练轨迹记录时间之和 | 371817.9532373999 | 逐轨迹训练计时之和，不是并行批次墙钟 |

上述时间来自已冻结 `complete_v1.costs`，不计算跨云端/本机速度倍数。现有五个正时间点、保存误差及均匀残差也不能扩展为t趋于0角点机制验证。

## 4. 生产日志与失败历史

本轮完整读取归档30份worker合并stdout/stderr日志，均有一条冻结命令、一条实际worker START和一条done行；其输出主要是启动和完成信息，并非逐优化步的详细日志。对这30份和恢复后2份runner日志扫描 `warning/traceback/exception/runtimeerror/out of memory/oom/nan/inf/error:`，无匹配；恢复后runner的stdout/stderr归档各为0字节。该发现只覆盖这些捕获文件，不能证明所有环境、历史进程或未记录步骤从未产生警告。

原runner42100的状态替换 `PermissionError [WinError 5]` 事故日志仍在manifest中，最终status/summary仍保留 `failure_history`。因此，30个训练attempt均exit0不等于整个调度过程从未失败。

旧工程失败证据没有用最终成功覆盖：

| 已保存回归记录 | 实际结果 | 边界 |
|---|---|---|
| recovery/pytest_attempt1 | 70通过、1失败 | 读句柄仍打开时原子替换失败；日志另有Torch导入期间WMI 0x8007000e栈，不能据此断言生产worker OOM或“零warning” |
| recovery/pytest_final | 79通过、2失败 | 两个测试扫描真实runs导致隔离失败，原历史保留 |
| recovery/pytest_final_attempt2 | 81通过、0失败 | 两行fixture隔离修复后的实际回归；不覆写上一条 |
| timezone_binding_repair/pytest_attempt1 | 110通过、0失败 | 带时区同瞬间绑定修复后的实际回归 |
| 最终Gate绑定的stage6/pytest.xml | 110通过、0失败 | JUnit哈希与Gate相符；仅工程证据 |

以上XML和对应实际日志哈希进入输入清单；本轮未重跑测试或重新判定旧工程审查。

**历史130条运行的完整生产worker日志仍缺失。** 旧JSON、权重和保存复算可提供相应结果证据，却不能补造原进程完整退出/警告记录；新30份全程捕获日志不能弥补这130条历史空缺。20个历史E4模型缺表面分支、历史源码/运行环境不同等既有限制继续保留。

## 5. 完成后的tag计数与分析版本

下表按14个已登记tag读取目录元数据，与正式488路径映射精确比较；未把其他目录、日志、checkpoint或派生图表算入原始产物。

| tag | JSON运行记录 | base PT | 完整model PT | 原始文件 |
|---|---:|---:|---:|---:|
| screen | 30 | 30 | 0 | 60 |
| confirm | 24 | 24 | 0 | 48 |
| causal1 | 6 | 6 | 0 | 12 |
| causal10 | 6 | 6 | 0 | 12 |
| pirate | 12 | 12 | 4 | 28 |
| axis | 36 | 36 | 0 | 72 |
| e4screen | 8 | 8 | 0 | 16 |
| e4confirm | 12 | 12 | 0 | 24 |
| final_ic_v1 | 18 | 18 | 18 | 54 |
| preflight4_adam | 12 | 12 | 12 | 36 |
| preflight4_soap64 | 12 | 12 | 12 | 36 |
| 历史11tag小计 | **176** | **176** | **46** | **398** |
| sensitivity_tau003_v1 | 6 | 6 | 6 | 18 |
| sensitivity_tau03_v1 | 6 | 6 | 6 | 18 |
| final_soap64_v1 | 18 | 18 | 18 | 54 |
| Stage6新增小计 | **30** | **30** | **30** | **90** |
| 合计 | **206** | **206** | **76** | **488** |

机器表为 [tag_counts.csv](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/reproducibility_complete_20261023/tag_counts.csv)。176条历史记录包括小预算/探索数据，206不是“206条统一主实验”，亦不等于206次从头训练（如Pirate中已有4项历史续接）。

complete_v1于06:30:35（UTC+8）生成：新增30项，默认六臂表36行，τ表18行；两表共享6条默认记录，所以共有48条独立分析记录，54个展示行不代表54次新增训练。本轮只核对该规模和输入/输出哈希，不重新聚合效果、重画图或代替另一独立数据审查。

本轮确认complete_v1的5份输入哈希与完成归档逐一对应；对应关系见机器报告的 `analysis_input_archive_binding`。即使D盘status或工作目录报告以后改变，复现入口应读取这些冻结归档。complete_v1的8个派生输出哈希也一致；当时 `analyze_stage6.py/plot_stage6.py` 的哈希保留在输入记录中，未要求未来可变绘图源仍等于v1。

图表展示层的 `complete_v2` 尚待独立刷新；计划只处理已确认的层次、Adam/SOAP→L-BFGS标签和五时刻max标签问题，数值、配置和判据不变。本补充只认可v1的输入绑定，**不对v1图形展示质量给出通过结论，也不提前认可v2**。后续应另记v2输出及绘图源哈希，不能将版本化展示变化误报为科学原始数据漂移。协议中的B-1/B-2原名称保留；S6-SOAP不替代它们，更不是普适发表门槛。

## 6. 只读复核入口与仍待完成的人工字段

随附 [check_completion.py](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/reproducibility_complete_20261023/check_completion.py) 仅用Python标准库。默认只打印检查摘要；它读取冻结完成态、已完成新90产物与明确证据，不调用任何训练/参考求解/测试入口。可在PowerShell执行：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
& 'C:\Users\LazyM\AppData\Local\Programs\Python\Python312\python.exe' 'E:\PINN-PDE\自主研究\当前主线\round33_equation_screen\manuscript\process\reproducibility_complete_20261023\check_completion.py'
```

本次实际结果为 `PASS, checks=613, failures=[], records=206, files=488`。脚本加 `--write` 仅更新本新目录的机器核对/输入哈希/CSV，不能更新原始数据、manifest、科学报告或旧复现材料。报告中的PASS限于脚本逐条列出的证据层；保存的科学验收不能扩展为本轮独立数值复算。

本轮不改变既有负面结果、环境混杂或论文表述。历史默认Adam与本机SOAP、历史τ=0.1与本机τ=0.03/0.3仍存在运行环境差异；不将跨组差全部归因于优化器/τ，不据最终工程通过推定修正必然优于强基线。主科学结论由冻结分析及另行独立数据核查支持，不能由本复现补充代签。

原 [N03 AI使用说明](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/reproducibility/AI_USE_STATEMENT_N03_CN.md) 的实质性AI执行/分析/写作/审查参与保持披露。内部AI独立审查不是外部人类同行评议。**真实作者身份、贡献、资金/利益冲突、最终工具/日期披露与人类责任签署仍pending**；本轮没有核验或编造任何人类署名。完整稿、原审查材料和旧复现目录均未修改。

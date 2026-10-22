# R33 第二阶段运行资源只读审查

审查范围：正在运行的 30 项预注册队列、既有训练/运行器源码，以及分析工具的完成门接口。资源快照采集于 **2026-10-23 01:02:18 +08:00**，其中 status 写入时间为 01:01:59；源码 hash 复核于 01:09:33。数据是有时间差的单次快照。

本次只写本报告及同目录 `runtime_readonly_review.json`。未启动训练、未加载模型重算、未修改源代码/协议、未操作训练进程、未重跑此前 21 项分析测试或 42 项运行器测试，未生成正式研究结果。

## 结论

**存在后续并发进入 L-BFGS 的内存余量风险，目前没有 L-BFGS 峰值实测，也没有由本次快照证实的 OOM。** 运行器正在按既有门槛暂停新派发；这一门槛只控制新任务，不限制已运行任务的阶段内存增长。当前证据不足以保证 21 个、或上限 24 个并发任务能安全完成全部阶段。

分析工具 `completion_gate` 与运行器的状态、验证、汇总、旧 398 文件绑定字段静态核对一致，未发现接口不匹配。两份最终报告尚不存在，因此这不是整批完成或端到端最终分析通过的证明。

## 当前资源证据

| 项目 | 采集值 |
| --- | ---: |
| 队列状态 | 21 running / 9 queued / 0 completed / 0 failed |
| 新派发因内存暂停 | true |
| 已有训练检查点 | 19 个 Adam，已保存 5000–6500 步 |
| 尚无首个检查点 | 2 个，分别在 00:59:13 与 00:59:54 派发 |
| 系统 committed / commit limit | 45,840,633,856 / 50,230,845,440 bytes |
| 系统 commit 使用率 / 剩余 | 91.26% / 4.09 GiB |
| 系统 AvailableMBytes | 6006 MiB |
| 运行器自身 private | 238.67 MiB |
| 21 个实际训练 worker private 合计 | 7.843 GiB |
| 单 worker private 范围 | 298.46–410.27 MiB |
| 整棵训练进程树 private 合计 | 8.117 GiB |

status 中的前一刻资源读数为 free physical 5.972 GiB、commit 使用 91.07%、free commit 4.179 GiB；与随后 CIM 读数的差异不作为异常。进程树共 64 个进程：运行器 1 个，另有 21 组虚拟环境 Python 启动器、conhost、实际 Python worker。不能把 42 个子 Python 名称当作 42 个重型训练任务。20 个实际 worker 当时有 1 个线程，1 个刚启动的 worker 有 3 个线程；此瞬时数不等于数值运算线程设置被改变。

整树 working set 求和为 8.267 GiB，但共享页可能重复计数，不能解释成独占物理内存。进程 private 合计也不能与全系统 commit 简单等同。CIM 单点 pages/sec=63、page reads/sec=3、page writes/sec=0，仅记录当时计数，不证明持续换页压力或稳定性；本次未做完整 OOM 日志审计。

## L-BFGS 的风险来源

冻结配置为 MLP 4×64、float64。Adam 阶段 PDE 点数 4096、边界/初值各 256；L-BFGS 使用固定 PDE 8192、边界/初值各 512（`stage6_runner.py:43`）。`pinn1d.py:234` 起的导数通过 create_graph 构建；PDE 含二阶导数。因此训练图及其临时张量可能显著增长。

单个 64 宽层的一个 float64 激活矩阵，从 4096 点的 2 MiB 变为 8192 点的 4 MiB。这只是一块张量：多个层、导数中间结果、保存供反向传播的张量、分配器保留块及方法修正都未包括，不能由这个数字给出进程总峰值或精确倍数。前一阶段的 Adam/SOAP 优化器仍被局部变量及 checkpoint 保存函数引用，不会仅因进入 L-BFGS 而全部释放。

这两个方程的模型只有基础 MLP 可训练参数，共 12,737 个，float64 参数为 101,896 bytes。读取当前已安装 Torch 的 `torch/optim/lbfgs.py:381` 起实现可见，最多保存 50 对 old_dirs/old_stps；这两组满历史向量约 9.72 MiB/worker，此外还有梯度、方向、参数克隆等工作向量。历史向量本身不足以解释数 GiB 级增量，主要未测部分是更大点集的自动微分工作集。strong-Wolfe 会重复 closure，但源码并未并行保留所有 closure 的完整反向图，不能把 closure 次数直接乘进峰值。

按当时系统余量，21 个 worker 若**平均额外增加约 199.37 MiB**，就会用完 4.09 GiB commit 余量。这是透明的容量情景，不是预测每个 worker 必然增加这一数值，也不是已发生 OOM。前 19 个任务检查点接近，未来可能阶段重叠，但先后次序、其他应用内存变化、页文件/commit 上限变化均未固定。运行器还会串行重载已完成结果并计算既定验证诊断，其自身工作集也可能增长。

`resources_allow_dispatch` 要求 free physical ≥4 GiB 且 commit ≤90%（`stage6_runner.py:201`）；快照中暂停符合该规则。它既不预留各任务的 L-BFGS 峰值，也不对活动 worker 做阶段切换限流。现阶段保留原运行，不据推测中断任务；如果后续取得真实内存不足证据，按下述恢复路径处理。

## 检查点与最小恢复路径

`pinn1d.py:340`–361 恢复/保存模型、Adam 或 SOAP 优化器、学习率调度器、采样生成器、固定点、history、phase/step/done、L-BFGS 状态及任务配置身份。保存先写 `.tmp` 再 `os.replace`。这保护正常文件替换时的旧检查点，不等于断电级耐久保证；不得把遗留 `.tmp` 自动当作完整检查点。

Adam 按既有 500 步间隔保存。20000 次梯度调用结束后，先抽取固定点并保存 `phase=lbfgs, step=20000, done=0`，再执行首个 L-BFGS closure（`pinn1d.py:384`–387）。因此若这个转换检查点已完整保存，恢复无需重做 Adam。L-BFGS 每个 50 名义迭代预算块结束保存；strong-Wolfe 的真实函数调用次数可能更多，不能把一个块说成固定 50 个 closure。

若发生真实分配失败/worker 非零退出，既有运行器会记录退出码、attempt 日志路径与耗时，将任务标为 failed，停止新派发，等待其余活动任务退出，并以 review_required 结束（`stage6_runner.py:529`–596）。这依赖运行器仍能继续运行；整机或运行器自身崩溃不保证走完该记录路径。

最小处置是保留原结果、检查点和全部 attempt/失败历史，先确认失败日志及系统资源证据；在机器仍可工作时让既有健康任务自然结束。确认 runner/worker 全部退出、锁已释放后，使用原固定环境、原任务集合/种子/科学配置，从原检查点恢复。仅按当时可用内存降低运行并发，例如先选 8–10 个 worker，再由原派发门约束；这个范围是保守处置示例，未经峰值测试，不构成安全保证。本次没有执行任何这些操作。

已完整落盘的成功任务由原运行器重新验证后跳过。没有首个检查点的任务从原种子开始；其他任务重做最后一次成功保存后的未保存工作，最坏是一个 Adam 保存间隔或当前 L-BFGS 块。恢复轨迹保存的训练耗时不包含丢失的未保存区间，因此必须保留 attempt 墙钟与失败记录；若是系统级突发中断，原 attempt 可能没有 finished/exit_code，后续说明中应明确记录中断和缺失耗时，不能补造为正常结束。恢复不是增加科学预算或另开一批重复训练。

## 完成门字段复核

| 分析端要求 | 运行器/产物对应 | 结论 |
| --- | --- | --- |
| status.phase=completed；精确 30 项全部 completed；每行 pid=null | 子进程退出时清空 row.pid；重启已有结果的初始 pid=None；仅所有行 completed 才写 completed | 一致 |
| results_validation 与 summary 均 complete=true、required_count=validated_count=30 | 最后调用 validation_report(validated, complete)，再对同一个 report 字典增加汇总外层字段 | 一致；两者 results 应完全相等 |
| 两份报告与工程门 prereg_commit 固定 | 统一 PREREG bfe89e3a07f1bb3bcc8e049d8d3d7ff95b4a647a | 一致 |
| gate.source_hashes、任务计划、精确任务集合 | 工程门/计划使用同一 ALL_JOBS 与配置构造 | 一致 |
| 旧 398 文件及 manifest 绑定 | 分析逐文件检查旧 manifest，并核对 gate.old_results.manifest_sha256；运行器结束前 check_old_results，summary.old_results.unchanged=true | 一致 |
| 新 30 项完整 bundle 共 90 文件 | validator 返回 JSON、基础模型、完整模型三个文件 hash；分析逐文件及 artifacts 元信息绑定 | 一致 |
| N64/GL200 与 N96/GL400 的五时刻误差 | runner 的两个字段名与 rtol=1e-5、atol=1e-9 对应分析读取 | 一致 |
| history_counters 与 heldout 名称/点数 | pde、left_neumann、right_dynamic、initial；8192 / 1024 / 1024 / 1024 | 一致 |
| attempts、失败/恢复历史及总墙钟 | 分析从 runtime/status 读取；summary.task_status 无 pid 不影响该检查 | 一致 |

`completion_gate` 位于 `analyze_stage6.py:121`；对应运行器生成路径位于 `stage6_runner.py:409`–463、466–504、529–635。队列可能先将 status 写为 completed，再写最终验证/汇总；这个短窗口下分析仍会因两份完整报告未就绪而拒绝发布，符合完整性要求。

此次 hash 对照确认工程门列出的 **12 个冻结文件全部匹配**，分析准备证据列出的 **3 个脚本全部匹配**。这里只核对接口和这些源文件 hash；没有重复运行旧 398 文件扫描、模型验证或完整完成门。最终产物须等真实 30/30 全部结束，再由既有验证与完成门逐项通过后生成。

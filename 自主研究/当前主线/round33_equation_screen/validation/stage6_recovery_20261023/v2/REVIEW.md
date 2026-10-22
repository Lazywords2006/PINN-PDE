# Stage6 编排修复 v2：防止旧结果丢失后静默重训

状态：**轻量检查通过，完整 Torch 回归仍 PENDING_RESOURCE_HEADROOM；禁止恢复派发。** 本版没有运行新 Gate、真实训练或终止原 worker。

独立审查发现 v1 的实际缺口：恢复 Gate 要求原活动任务 JSON 存在，但 Gate 后若产物丢失，run 的 `if JSON.exists()` 可以跳过旧任务验证；`new_state` 又把任务重置为 queued，导致旧任务被当作新任务训练。只有合法 checkpoint 或整个 bundle 消失时，原身份检查也不足以阻止这条路径。

v2 在 run 的所有派发之前调用 `prevalidate_results_before_dispatch`，对 `gate.recovery_lineage.original_active_jobs` 无条件执行现有完整 `ResultValidator`。历史状态为 completed 的任务同样必须完整验证。任一验证异常即进入现有异常退出路径，不进入 execute_queue。

每个必验任务带 `required_complete_result`，从 previous completed 或此前已保存的标记继承；原恢复任务在预检开始时全部标记。这样，即使第一次预检失败后状态写成 review_required/queued，第二次运行仍必须验证同一完整结果。标记只有验证通过后才对应 completed，不用 checkpoint、exit 0 或文件缺失代替完整结果。

新负控是 recovery / previous completed 两种来源分别搭配：Gate 后 JSON 消失、整组 bundle 消失、整组 bundle 消失且仅保留合法身份 checkpoint。每种场景连续运行两次，均要求验证失败且 popen 调用为 0。正控覆盖所有必验任务先标 completed、剩余任务仍 queued，以及旧结果验证完成后才允许模拟派发。

本版 `lightweight.log/.xml` 为 18 项通过：原 9 项原生 I/O 检查，加 9 项预检/恢复检查。`preflight_checks.py` 从实际源码和测试 AST 提取原函数体，不导入 Torch；文件系统、Windows 锁、run/queue 逻辑真实执行，checkpoint 序列化用 JSON 替身，科学数值验证为显式 sentinel。因此它证明的是本地编排负控行为，不能替代完整 runner/Torch 回归或科学验收。完整测试保留在 `test_stage6_runner.py`，等资源余量回升后由根节点运行。

上级目录的 v1 diff、报告、日志、原字节 Git 校验证据不覆盖；`../v1_frozen_sources/` 保存 v1 runner/test 实际源，hash 与原 v1 报告吻合。v2 全量 diff、相对 v1 的增量 diff、源码快照、hash 和 Git blob 校验保存在本目录。事故原 gate、20 项原始快照、监督器源码不变。

根节点后续仍须遵循 `../RECOVERY_ROUTE.md` 的退出证据、锁、完整回归与新 Gate 步骤。该文档的 v1 结论须结合本补丁阅读，当前恢复启动门保持关闭。

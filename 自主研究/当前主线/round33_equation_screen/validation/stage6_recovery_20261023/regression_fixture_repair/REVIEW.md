# 完整回归中的测试目录隔离修复

根代理完整 Torch 回归结果为 **79 passed / 2 failed**。失败日志、XML 和修前测试源已先复制到 `before/`，`before_manifest.json` 保存原路径、复制路径和 SHA-256；没有覆盖原 `pytest_final.log/.xml` 或任何 v1/v2 证据。

两处测试只替换了 ALL_JOBS 和 out_path，却未替换 HERE。`existing_identity_checks` 扫描 HERE/runs 时读到了正在自然完成的真实任务，按缩小后的测试任务集合将其误判为未注册结果。它们分别是 `test_existing_result_is_revalidated_and_never_dispatched` 与 `test_partial_bundle_without_checkpoint_rejected`。

本次产品代码改动为零；`test_stage6_runner.py` 仅增加两行，分别在上述测试中执行 `monkeypatch.setattr(s, "HERE", tmp_path)`，使目录扫描也落到该测试的临时目录。

同类路径已核查：恢复产物丢失测试（2 来源 × 3 场景）已显式隔离 HERE；外层异常测试与旧结果验证/新派发测试已显式替换 existing_identity_checks，不会进入真实目录扫描。其他缩小 ALL_JOBS 的 helper 测试只直接调用预验证函数，不扫描 HERE/runs。没有发现第三个需要补丁的 fixture。

定向检查 `fixture_checks.py` 从当前测试文件抽取这两个实际测试体，并复用 v2 的无 Torch AST 环境执行实际 existing_identity_checks。额外守卫每次 Path.rglob：路径必须位于当前 tmp_path 内，并断言每个测试恰好扫描一次。结果 2 passed / 0 failed，耗时 0.28 秒。它只证明测试隔离与预期分支；不等价于完整 Torch 回归。

根代理随后执行完整 Torch 复测，`../pytest_final_attempt2.log/.xml` 为 **81 passed，6.10 秒，exit 0**。本证据包记录第二次日志/XML 的 hash 并核对 XML 的 81 项、0 failure、0 error、0 skipped；原失败历史继续保留。该通过仅是 runner 工程回归，不替代原 worker 的完整退出、恢复 Gate 或科研验收。

本次没有启动训练、新 Gate、停止进程、写入真实结果或修改 runner/科学源码/协议；没有提交。

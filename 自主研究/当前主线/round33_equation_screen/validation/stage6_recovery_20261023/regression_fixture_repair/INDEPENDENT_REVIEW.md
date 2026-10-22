# Stage6 测试隔离最小修复：独立审查

日期：2026-10-23（UTC+8），核对至04:36。
结论：**接受这两行测试隔离修复；没有削弱生产身份检查。当前不授权恢复派发，原21项运行验收仍待完成。**

## 改动与来源核对

修复仅在以下两个测试中各增加一行 `monkeypatch.setattr(s, "HERE", tmp_path)`：

- `test_existing_result_is_revalidated_and_never_dispatched`
- `test_partial_bundle_without_checkpoint_rejected`

原因明确：这两个测试已缩小ALL_JOBS并替换out_path，但生产函数仍从HERE/runs扫描同tag目录；真实Stage6结果自然落盘后，测试的缩小任务集合会将其他真实任务误判为未注册结果。生产检查按其输入正确拒绝，错误在测试没有完整隔离扫描根目录。

独立AST比较：去掉上述两处预期HERE补丁后，整个测试文件AST与修前完全一致，原断言、预期配置、完整bundle分支和不完整产物拒绝断言均保留。对照v2冻结清单，除测试源外的11个门禁源哈希全部不变，包含runner、训练/方程、供应商、launcher及协议。本次未重新审查整个v2、文献或旧398结果。

| 指纹 | SHA256 |
|---|---|
| 修前测试源 | 16844c7d45cbbd4b357e51140433b64b1ee13b7aa76e0f07d1117496b32b9c63 |
| 修后测试源 | 6fcd2d482d5cd0fad8abdacdbe10fbfa8b632f941f9ecbc5b55f860760a894a6 |
| 未变化的runner | fba758ebe71f1c6dead8acc7cd062c15284a7f908e0ad51038aed6755da8600b |

## 独立针对性验证

实际执行低负载AST/原生检查：**5 passed，0.28秒**，未导入Torch，未运行完整回归或真实训练。

1. 从修后源码提取两个实际测试体，执行生产existing_identity_checks；每次Path.rglob均由额外守卫确认位于该测试tmp_path内，且每例恰好扫描一次。两个原断言均通过。
2. 在临时目录放入未注册JSON，实际生产函数仍抛出“未注册结果”，证明拒绝机制没有被绕过或删除。
3. 从修前快照提取两个旧测试体，仅用D盘临时文件模拟外部同tag结果；分别重现未注册结果异常和预期正则不匹配。预期失败由负控捕获，不读取真实runs目录。

同类隔离审查：直接调用existing_identity_checks的三个测试函数均显式隔离HERE（包括2来源×3情景的恢复产物丢失测试）；调用run的外层异常测试及旧结果/新派发测试已替换扫描函数；其余缩小ALL_JOBS的预验证测试不扫描HERE/runs。未发现第三处相同隔离缺口。

独立运行目录：
`D:/CodexRuntime/runs/r33_stage6_20261022/independent_fixture_review_20261023_0435/`

| 文件 | SHA256 |
|---|---|
| pytest.log | 08893cd61d53e5b060bff2eaec1aa46e86dfba154115e993453edcfe09ff571d |
| pytest.xml | 30cc686510ac542dde204cac36a1e5d8aaa680dd308275f1af683e99a0d56e0b |
| independent_fixture_checks.py | 984cf821cb84f5ac75799105801b072e8a2cf8538e781fa76830e80a3ab7bfd6 |

这些测试证明隔离、预期分支和生产未知结果拒绝行为，不是科学数值验收。

## 完整回归与失败历史

首次完整Torch回归实际为 **79 passed / 2 failed（81项）**。独立读取原XML确认两项失败正是上述测试；原始文件及before快照哈希均与before_manifest一致，未被覆盖：

- `../pytest_final.log`：3347dc704abc66c00def1dcfad5e2207885cc735362a45726bd4bee081b850ef
- `../pytest_final.xml`：71bee10bd4f7b645d9facaa004f55949964feffca37df60d1abd33e9eaa9602d

根代理对修后源码另行实跑的完整回归为 **81 passed in 6.10s，exit0**。本审查未重复运行完整Torch套件，已独立核对新日志/XML：81 tests、0 failures/errors/skipped，两项修复测试均无failure/error。

- `../pytest_final_attempt2.log`：f7dcc47583199ff2d6e4439452c410e4b8a8dbe21e66dc4e50b22b1086cc6a76
- `../pytest_final_attempt2.xml`：6cf52fc66bcd116d1c0aad9efb8d3f79ebd2ad9347eda5749ed42c2e9a47ecce

因此，首次79/2继续作为失败历史保留；新81/0仅作为修后完整runner测试证据。不能把两次记录合并成从未失败，也不能据测试通过判定原21训练通过。

## 根节点的可操作结论

- 可以接受两行补丁及当前测试源指纹；不需修改runner或科学协议。
- 后续新Gate须绑定当前测试源6fcd2d48…及当前源码，不能复用旧v2测试源16844c7d…的身份；Gate内部按现有机制重新验证测试与冻结证据。
- 原21仍须全部launcher/worker HANDLE实测退出并完整结束监督、核对退出码、锁释放和完整bundle/预算/参考重算；再以恢复manifest及新Gate进入仅派余9的既定路线。
- 根代理04:33通报34个零退出、4个原worker仍在；这是部分监督进展，非原21全部验收。当前journal未关闭，本审查没有复制、归档或固定其整文件哈希。
- 尚未执行新Gate、恢复派发、原21最终验收或30/30接受。上述事项均为PENDING；科学效果不在本次审查范围。

本审查未改项目源、原始结果或协议，未启动/结束真实训练，未打开活动checkpoint内容。仅写本报告与JSON，轻量测试运行文件保存在D:/CodexRuntime。

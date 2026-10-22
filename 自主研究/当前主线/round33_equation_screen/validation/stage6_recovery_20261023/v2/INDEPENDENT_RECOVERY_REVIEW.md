# Stage6 独立恢复工程复审 v2

日期：2026-10-23（UTC+8）；独立监测核对时间：02:39:44。
结论：**REC-P1-001 已在静态与独立轻量测试范围内闭环；真实恢复仍 PENDING，当前禁止新派发。** 没有发现 v2 增量引入的新阻断缺陷。此结论不等于完整 Torch 回归、旧21训练完成或最终30项验收通过。

## 冻结身份及历史保留

- v2 runner SHA256：`fba758ebe71f1c6dead8acc7cd062c15284a7f908e0ad51038aed6755da8600b`。
- v2 测试源 SHA256：`16844c7d45cbbd4b357e51140433b64b1ee13b7aa76e0f07d1117496b32b9c63`。
- 独立核验全部12个门禁源与v2冻结证据一致，14个v2工程证据文件哈希一致；旧398文件再次全量重算无不符。
- AST逐定义比较确认：v1→v2仅修改 `new_state`、`run`，新增 `prevalidate_results_before_dispatch`；没有删除函数，其余生产函数未变化。训练、方程、供应商、协议和launcher不变。
- 上级目录v1独立报告保持原样，仍记录 BLOCKED 和实际反例。其Markdown SHA256为 `7e54eef1626ec97101f7d8dd866bb0171bc1d53e51ac27cad4abd6ab16f5c70f`，JSON为 `89d2ce0710cc176e7f79380a8209eb4e73bc2db52b749a51913c857e5d1b043c`。本报告另存，不将v1历史覆盖成通过。

## REC-P1-001 修复复核

v1缺陷：恢复Gate后旧产物丢失时，Run可因JSON不存在跳过校验，再由new_state把旧任务放回queued；独立AST反例已证明此控制流，未发生真实重复训练。

v2修复具有三个必要部分：

1. `new_state` 在重置任务状态前，从 previous completed 或已存在的 `required_complete_result` 继承必验标记。不能只看本次的queued状态。
2. `prevalidate_results_before_dispatch` 在任何逐项验证之前，为恢复门的全部 `original_active_jobs` 设置必验标记；这些任务无条件进入现有ResultValidator，JSON存在性不再决定是否验证。恢复门中不属于精确任务集合的job直接拒绝。
3. `run` 先完成全部预验证，再保存状态和调用execute_queue。异常路径保留必验标记，状态写成review_required；第二次启动仍须验证同一个旧结果。成功任务才置为completed；剩余真正未尝试任务仍可保持queued。

独立重跑六个负控：来源为恢复原活动任务 / previous completed，分别配合仅JSON丢失、整组bundle丢失、仅合法身份checkpoint保留。每种场景连续调用Run两次；均拒绝缺失旧完整产物，Popen调用为0，必验标记持续保留。正控验证必验结果全部先完成，真正剩余任务才可进入模拟派发。这里的checkpoint序列化和科学验证器为明确替身；已执行真实编排与文件/锁控制流，不宣称测试了Torch数值或真实训练。

裁定：**REC-P1-001 = CLOSED_STATIC_AND_LIGHTWEIGHT_TESTED**。若之后改动runner/test或其冻结依赖，须重新检查源码指纹并补相应测试。

## 独立测试与v1安全边界回归

| 独立执行 | 结果 | 范围 |
|---|---|---|
| 原生I/O 9项 + v2预检/恢复9项 | 18 passed，3.81秒 | Windows句柄、有限替换重试、失败tmp有界、running checkpoint只stat、锁阻止内容解析；六类丢失负控、二次运行及正控 |
| 额外AST提取回归 | 21 passed，3.85秒 | 永久status失败drain、写恢复不重新派发、validation写失败、最终保存失败、原异常保留；恢复身份/创建时间/父子/命令/退出码/完整结束/hash负控、恢复证据变化、原status冲突、未知退出与显式失败重试边界 |

两组均由独立审查者实际重跑，未导入Torch，未调用真实训练Popen。源函数及测试体从实际冻结代码AST提取；科学配置验证、数值ResultValidator和Torch checkpoint真实序列化未纳入本次轻量验证。

额外回归首次收集失败：pytest从E盘项目指向D盘临时测试文件时误扫D盘受保护的WpSystem目录，报WinError1337。已保留首次日志/XML；显式限定rootdir/confcutdir并使用importlib导入模式后，同一测试源21项通过。这是独立测试器的收集配置问题，不记为产品测试通过，也不归因为worker故障。

v1的真实Windows发现继续有效：FILE_SHARE_DELETE并不能保证打开目标可被原子覆盖。v2没有回退到“运行中打开checkpoint”方案；running分支仅stat，非running解析仍须持任务锁。v1的有限重试、失败停止新派发、持续poll/drain、应急退出证据、恢复manifest和源码谱系逻辑均未被v2改动。独立原生/AST回归在所列范围未发现这些保护退化。

## 独立测试证据

目录：`D:/CodexRuntime/runs/r33_stage6_20261022/independent_v2_review_20261023_0234/`。

| 文件 | SHA256 |
|---|---|
| pytest.log | b6b05389e130a5a4bc866c5295984c2b516f4261f61f249d520c182fcfb46d72 |
| pytest.xml | 08db48005deaf0cf9cfe352784e0fef97208f14601c5c0c26784c5c0b52e52a8 |
| pytest_extra.log | 414de4f1baa22b04b378286112fd1d045155cc93112b3fb5408609726c4e0741 |
| pytest_extra.xml | 49650859b9de201ff6bb56632c40b77ea712ed23d55145c23402d05450c026f6 |
| pytest_extra.log.attempt1 | 7e6fa1b6e2c6de3d19ece891177cdfade7cf655b11fb1dbb2cb2aea5225095ee |
| pytest_extra.xml.attempt1 | cb0ebcf1dbf74194dddd07634a98330f2189a9c065d4ab23c28a95374caacc46 |
| independent_extra_checks.py | ccdcaf175e1e7ecdc9d8114e4c85abf529ffe8c5aa3011c09e9da6dec3facbf5 |

## 真实监测与尚未开放的门

02:39:44独立读取监督器事件：42 attached、1 attachment_complete、0 process_exited、无observer_completed。持久status哈希仍为事故时的 `834ae2f4123a1298a25b02f906b4df69f1b1723e74b0491dc4a2db0128b6dc89`，其running/queued及训练步数是过期快照，不能充当当前进度。

这些记录只证明既有附着证据尚未形成完整退出证据；不把未报告退出的训练计为PASS。完整当前源Torch回归仍为 `PENDING_RESOURCE_HEADROOM`，原首次70 passed/1 failed的日志和WMI 0x8007000e诊断继续保留，不提升成当前完整回归通过。

根节点下一步按顺序执行：

1. 等待原42 HANDLE全部实际signaled，唯一launcher/worker配对完整，退出码全部为0，观察器完整结束；任何缺失、未知或非零都停审，不自动重训。
2. 确认任务锁释放，资源余量足够后补跑当前冻结源的完整Torch runner回归，失败仍阻止Gate/Run。轻量18+21不能替代这一步。
3. 固定已关闭的退出日志及相关证据，创建不可覆盖的recovery manifest；运行新Gate，绑定旧21的原源码谱系、新代码、原状态、398旧文件、固定环境、完整测试与参考解门。
4. Run必须再次无条件验证原21的完整JSON/basePT/modelPT、预算与N64/N96指标等，不论此前Gate是否已检查。全部旧结果完成预验证后，才允许派发剩余9项。
5. 沿用原30任务、种子/配置/预算、48h资源复盘期限和科学判据；不调整τ主配置或倒选优化器。原21退出证据、额外耗时和新9源码谱系分别留档。

## 最终范围裁定

- v1缺陷历史：**保留BLOCKED**。
- v2修复的静态/独立轻量闭环：**通过所列范围，无新阻断发现**。
- 完整Torch回归：**PENDING**。
- 原21真实退出与完整产物验收、新Gate、剩9真实派发和最终30/30：**PENDING，当前不开放恢复派发**。
- 科学效果、S6-SOAP与τ结论：**NOT_EVALUATED**。

本审查没有修改项目代码、科学协议或原始结果，没有启动或终止真实训练。只写独立报告，测试运行文件与缓存位于D:/CodexRuntime。

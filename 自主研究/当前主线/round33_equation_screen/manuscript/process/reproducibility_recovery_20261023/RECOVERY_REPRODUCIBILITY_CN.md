# R33 恢复阶段复现补充

本补充记录原21项完成验收及后9项恢复派发的来源链，供完整稿后续整合。静态核对时间：`2026-10-23T05:37:21.092244+08:00`（UTC+8）。本轮依据已归档证据，不查询实时进程、不读取活动checkpoint、不加载模型、不运行训练、Gate、数值复算或最终汇总。**最后9项及Stage6最终30/30验收仍待完成，不提前形成τ敏感性或SOAP科学结论。**

旧[复现说明](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/reproducibility/REPRODUCIBILITY_CN.md)、[数据字典](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/reproducibility/DATA_DICTIONARY_CN.md)及其02:57快照原样保留。旧文中的“完整回归及恢复待完成”属于当时时点；以下新证据补充进展，不覆盖旧记录。冻结稿`working_revised1.md`保持SHA256 `7ca430d7911dda4507469099e493dc2563ef48dff0157b4df862e4ab8f3b3635`。

## 1. 恢复事件与证据层级

原runner 42100因status原子替换WinError 5退出；日志没有确定具体占用者。原21项worker继续执行，监督器以已验证身份的HANDLE记录21组launcher/worker共42个零退出。恢复清单绑定原Gate、原status、进程清单、监督记录、源码和故障日志。`exit_code=0`首先证明进程结束；原21项随后由恢复Run走完整bundle、预算、N64/GL200及N96/GL400误差复算、独立heldout残差验证，才进入已完成状态。

| 事件/证据 | 已保存的事实 | 可支持的结论 |
|---|---|---|
| 修复提交`352af9c` | 两处测试增加HERE临时目录隔离；原生产检查与科学代码未变 | 测试不再扫描真实实验结果；独立5项检查及修后81项回归有各自证据 |
| 修复提交`2a42ded` | 仅允许指定started_utc路径按同一精确瞬间比较时区格式；身份、配置、PID和真实时间差继续严格检查 | 独立31项限定检查及完整110项工程回归支持该修复；不等于科研判据通过 |
| 新Gate，2026-10-23 04:54:34（UTC+8） | `passed=true`；110 tests、0 failures、0 errors、0 skipped；12门禁源和旧398清单绑定 | 支持恢复编排进入既定验证和派发流程；110是工程测试数量 |
| 04:57:14状态观察、04:58:30派发观察 | 原21已completed且`complete_and_recomputed=true`；原queued9已running；所有30任务均只有attempt1，后9未从checkpoint恢复 | 支持该观察时点的21/9分层；不能据此声称当前9项已完成或运行正常 |
| 原21归档提交`0ccc65a` | 21任务、每任务JSON/base PT/model PT共63文件；已保存Git索引字节与验收SHA的63/63一致检查 | 原21验收产物已归档；本补充只重核元数据映射及提交文件集合，不再次重载模型或复算数值 |

恢复实际runner为91632，launcher为25644；进程创建记录为2026-10-23 04:55:29（UTC+8），`--workers 9`。这些PID描述派发证据，不是本轮实时存活证明。原48小时复盘期限保持为`2026-10-25T00:08:04.374697+08:00`（UTC+8），没有因工程恢复重置。当前[恢复路线](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_recovery_20261023/RECOVERY_ROUTE.md)保留历史命令和当时状态，应以顶部的实际恢复记录理解，不能重复执行历史派发示例。

## 2. 原21与后9的源码来源

原21不是在新runner下重新训练。它们在原Gate/原runner下自然完成，之后由修复版runner核验退出证据并重载已有完整结果验收。后9是原计划中尚未派发的任务，在新Gate/修复版runner下开始各自第一次attempt。两组共有的训练函数、方程、参数、供应商SOAP实现、协议及任务集合没有因恢复变化；本次静态比较12个门禁源，变化项仅runner和runner测试。

| 来源层 | 任务范围 | Gate SHA256 | runner SHA256 |
|---|---|---|---|
| 原21训练来源 | τ=0.03/0.3共12项；SOAP的E1/E3种子0全部6项，加E1种子1三方法共3项 | `bb7250d65bfee8b44858c2ae734e540eee0bf7d26e2d5a68bbc2b7d40ff6e898` | `7a2f55cd271cfd9d4355998d35b66a095a656aa46e260fc8c1dfeb83db2e870b` |
| 后9训练及当前编排来源 | SOAP的E3种子1三方法，加E1/E3种子2六项 | `4572088adf9eb3010c4d483b6ae71a82087dd5bd41b35dcb38e0687f5666d6e3` | `a2fd8483ed9faa72b25ec6977441522d7897bc6a06b52321a698db4801952e18` |

新测试源SHA256为`5294632eb59732564d22407369a7a9a9402a40a0d2292159a4a4602f002a3ed7`。逐任务归属、attempt编号、配置哈希、所属Gate及验收状态见同目录`source_lineage.json`。它只提取归档状态，不包含任何本轮新计算的误差结论。`source_lineage`、attempt的`source_gate_sha256`以及Gate的`recovery_lineage.prior_source_hashes`应在最终分析中共同保存，不能用当前源码哈希覆盖原21的训练身份。

主要来源为[恢复清单](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_recovery_20261023/recovery_manifest.json)、[新Gate归档](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_recovery_20261023/recovery_gate_success/engineering_gate.json)、[派发证据](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_recovery_20261023/recovery_dispatch/dispatch_evidence.json)、[状态观察](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_recovery_20261023/recovery_dispatch/status_observation_20261023_045714.json)、[原21归档清单](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_recovery_20261023/original21_archive.json)及[63文件字节核对记录](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_recovery_20261023/original21_git_blob_checks.json)。这些证据的原始字节哈希与当前source/route/analysis哈希统一写在`recovery_static_evidence.json`。

## 3. 计数、时间与分析解释

21完成加9运行仍不是30/30；63已归档文件也不是新增90文件齐全。历史176项及398文件保持独立证据层。所有30项最终验收后才可确认总计206个独立运行记录、90个新增文件及488个原始文件绑定。默认比较36行与τ表18行共用6个历史默认记录，因此展示行数54不等于54次新训练；最终分析记录集合应为48个独立记录。

本轮绑定当前分析源`validation/stage6_analysis_20261022/analyze_stage6.py`，SHA256为`5eee1bd327426cbba355e76f60d87d24d1d822eb4c76347302cdde9b57b19dc1`。这里只做AST语法和接口声明静态核对，不执行`--partial`、`--final`或任何训练函数。最终分析仍须从完整status、results_validation、summary、新Gate及任务计划绑定输入；本补充不代替该完成门。

时间必须分别报告：`batch_elapsed_seconds`是首次开始至观察时刻的整批历时；`total_runner_wall_seconds`是保存的runner会话累计时间，不补造原runner退出后的孤儿区间；各attempt的`wall_seconds`可以求和，但并行之和不是批次墙钟。原21的attempt时间以HANDLE退出观测减原派发时刻补记，包含观察轮询延迟。记录内训练轨迹耗时又是另一层字段，不能拿来填补调度器缺口。

N04继续适用：`history.adam_gradient_calls`由成功完成后的`cfg.adam_steps`写入，依赖冻结循环及完成证据，不是独立逐步观测计数器；SOAP19999次更新由冻结算法语义推得。L-BFGS内部迭代与closure来自优化器保存状态。`final_adam_loss`应称“Adam/SOAP末次记录损失”，是零基step19990（小预算为3990）更新前计算、当步更新后记录的抽样值，不是终点重新评估。

跨环境限制继续保留：τ=0.1历史云端结果与τ=0.03/0.3本机结果不能作纯τ因果归因；历史Adam与本机SOAP之间的精度和成本差异也混有环境、软件因素。S6-SOAP主判据限定在本机同批固定SOAP实现的hardic与hardic+layer比较内。原A-1、G2失败、E4缺表面分支及原负面结果不会因工程恢复而消失。

AI参与范围沿用[N03声明](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/reproducibility/AI_USE_STATEMENT_N03_CN.md)。本次补充包含工程证据整理、静态来源核对及复现文字撰写；作者身份、贡献、具体AI工具版本与人类最终核验仍须作者确认，不能预先签署。

## 4. 30/30后的更新入口

完整验收后按同目录[最终字段刷新清单](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/reproducibility_recovery_20261023/FINAL_REFRESH_FIELDS_CN.md)逐项刷新，另存完成时点版本。当前材料、旧复现目录、原Gate及失败/修复证据继续保留。完整稿在结果和最终来源链可核对后再补4.5/4.6及结论；当前两处MATERIAL GAP保持原样。

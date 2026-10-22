# Stage6最终30/30后需刷新的字段

本清单是未来核对要求，不是这些字段已经满足的声明。当前证据止于原21已验收归档、后9已派发。执行者须在后9结束后读取真实最终输出，任何缺失或不一致继续保留待核状态，不用计划值填充。

| 层级 | 最终需读取/核对的字段 | 应满足的范围与解释 |
|---|---|---|
| 运行完成 | `status.phase/tasks/counts/updated_utc`；每任务`state/pid/attempts` | 精确30元组，全部completed、任务PID均空；保留全部attempt、真实退出、失败历史及是否续接，不强行预设最终仍全为attempt1 |
| 科学验收 | `results_validation.json`及`summary.json`的`complete/validated_count/required_count/prereg_commit/results` | 两报告均complete，30/30，预注册提交一致，逐任务results同源一致；“110工程测试通过”不替代这些字段 |
| 逐结果身份 | `job/config/json_sha256/bundle_sha256/complete_and_recomputed`与原JSON/artifacts | 30配置与冻结计划一致；每项JSON、base PT、model PT三文件恰好齐全，90个新增哈希；不漏项、不加项、不按误差筛选 |
| 数值复核 | 五时刻vol/trace、`recomputed_N64_GL200`、`dense_metrics_N96_GL400`、`tolerance` | 读真实保存复算；按现门rtol=1e−5、atol=1e−9逐序列核对；不得将5个正时刻结果外推成t→0机制实证 |
| 残差与预算 | `heldout`四分量及n/rms/max_abs、`history_counters`、`optimizer_accounting` | PDE8192、左端/动态右端/初值各1024；如实保留L-BFGS停止原因、内部n_iter和closure，N04计数与末次记录损失口径继续适用 |
| 源码与恢复来源 | 当前Gate `source_hashes/recovery_lineage`，status `source_lineage/recovery_incidents/applied_recoveries/failure_history`，attempt `source_gate_sha256` | 原21归旧Gate、后9归新Gate；保留原manifest、42零退出绑定及两修复提交；任何新恢复另追加来源，不覆盖既有层 |
| 固定协议与截止 | `task_plan`、`prereg_commit`、`review_deadline_unix`、预算及参数 | 保持原30任务和原48小时期限；若出现延期/失败，记录事实与授权，不以恢复成功推定延期 |
| 完整来源清单 | analysis `evidence.raw_sha256/input_sha256/source_hashes/runtime_status` | 原398与新90合计488；5份最终输入逐字节绑定；原21归档63文件与最终验收仍可追踪。此处是预期数量，当前不填“已完成” |
| 分析规模 | `new_task_count/default_comparison_records/tau_records/records` | 预期30、36、18及48独立分析记录；全部研究运行记录最终206；区分展示行数、独立记录数及训练次数 |
| 科学结论 | `default_groups/tau_groups/tau_summary/S6_SOAP` | 按预注册固定判据读取逐方程及联合结果；无结果前保持待定，不因工程通过宣告SOAP获益或τ稳健性 |
| 时间与成本 | `costs.local_batch_elapsed_seconds/local_runner_elapsed_seconds/local_attempt_wall_seconds_sum/runner_wall_timing_note`及逐记录trajectory时间 | 各层分别报告；孤儿间隔不算runner活跃墙钟；原21观测补记含轮询延迟；不算跨环境速度倍数 |
| 最终派生物 | analysis `generated_local/output_sha256`、CSV/图表/报告来源、完整稿SHA和字数、渲染/独立审查记录 | 在新输出目录生成并绑定，不覆盖旧时点证据；稿件保留负面结果、环境混杂、E4缺失及N03人类核验待确认 |

完成门目前在`analyze_stage6.py:completion_gate`中；本补充已静态读取其要求，没有调用它。完整稿使用当时实际分析源码及输出哈希；若源码在本补充之后改变，另记变更来源并按所改范围验证。旧`reproducibility/`与本`reproducibility_recovery_20261023/`仍是历史时点证据，后续完成材料应另存。

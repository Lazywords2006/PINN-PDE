# Stage6 complete_v1 → complete_v2 版本映射

complete_v2 仅处理独立审查的 S6-F01、S6-F02、S6-F03。修订来源为 `../../../manuscript/integrity/stage6_analysis_20261023/INDEPENDENT_STAGE6_ANALYSIS_REVIEW.md`，SHA-256 为 `10139292faa6450a680c47ad7965f38afe82f969ee362e8a026af64be0ebbbef`。complete_v1 对应归档提交 `7d3857ea93d28c620af51dbc3fdf88e581adae0d`，原目录九份文件全部保留，未覆盖。

| complete_v1 原文件 | complete_v2 对应文件 | 变化范围 |
| --- | --- | --- |
| all_new_runs.csv | all_new_runs.csv | 逐字节相同，30 行 |
| default_six_arms.csv | default_six_arms.csv | 逐字节相同，36 行 |
| tau_sensitivity.csv | tau_sensitivity.csv | 逐字节相同，18 行 |
| default_six_arms.png | default_six_arms.png | 三项展示修订，原数值及点位不变 |
| default_six_arms.pdf | default_six_arms.pdf | 与 PNG 同一图，矢量导出 |
| tau_sensitivity.png | tau_sensitivity.png | 三项展示修订，原数值及点位不变 |
| tau_sensitivity.pdf | tau_sensitivity.pdf | 与 PNG 同一图，矢量导出 |
| STAGE6_ANALYSIS_20261022.md | STAGE6_ANALYSIS_20261022.md | 时间及主指标/训练路线定义、相邻图注；全部数值表格不变 |
| analysis_evidence.json | analysis_evidence.json | 生成时间、绘图元信息、分析源哈希、输出哈希更新；其余字段严格相同 |

S6-F01：中位数线 zorder 从 5 改为 3，种子点仍为 4、范围线仍为 2，避免中位数线覆盖真实种子标记。真实数据的全部 18 个显示组逐一检查种子值、中位数值和图层顺序。

S6-F02：默认图明确 Adam→L-BFGS / SOAP64→L-BFGS，τ 图明确 Adam→L-BFGS；保留历史云端/本机来源与 τ=0.1 主配置。报告相邻图注同步说明完整训练路线及跨环境比较限制。

S6-F03：纵轴写明“五时刻最大体相对 L² 误差”，两图图注列出 t={0.05, 0.1, 0.25, 0.5, 1}，明确只是五个固定时刻的最大值，非连续时间上确界。

48 条唯一记录、12 个默认分组、6 个 τ 分组、全部比值/判据/耗时及 488 个原始文件的来源绑定与 v1 相同。保留协议中的 B-1/B-2/G2 原名和旧负面结论，没有修改原始数据、科学计算、训练、工程门或门绑定的 12 个源文件。analyze_stage6.py 除 report 函数外 AST 相同；绘图验证逻辑和数据选取保持原样。

现有 26 项分析测试通过。作者已查看两张原尺寸 PNG 与两份实际 PDF 的 Poppler 渲染；字形、标签、图注与种子可读，无裁切。PDF 渲染检查图保存在 `revision/visual_checks/`；文本提取、测试日志、修改前后源、源差异、逐字节与实际 Git blob 核验保存在 `revision/`。这不替代后续独立定向复核，也不构成新的模型计算验证。

完整前后 SHA-256、等价字段和检查证据见 `revision/REVISION_EVIDENCE.json`；可用分析环境运行 `revision/verify_revision.py` 复核。正式九份产物由 `analysis_evidence.json` 与修订证据共同绑定，后续新增审查文件不更改这些正式产物。

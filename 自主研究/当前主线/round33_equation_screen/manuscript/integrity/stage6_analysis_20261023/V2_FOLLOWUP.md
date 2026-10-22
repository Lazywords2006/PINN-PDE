# Stage6 complete_v2 限定独立复核

结论：**限定复核通过；S6-F01、S6-F02、S6-F03 三项全部关闭，无新增发现。** 本次只审展示修订和两版数据/判据一致性，不是完整稿审前检查，也不是最终稿PASS。

## 三项关闭依据

| 原问题 | 状态 | 独立核验 |
|---|---|---|
| S6-F01 中位数线覆盖种子 | 关闭 | 源中median=3、scatter=4、range=2；两PNG和两PDF渲染均看到完整圆/三角/方形轮廓，黑线不再穿过点中心。 |
| S6-F02 完整训练路线不明 | 关闭 | 默认图两组明确Adam→L-BFGS及SOAP64→L-BFGS；τ图标题明确Adam→L-BFGS；报告相邻图注同步说明。 |
| S6-F03 最大值时刻范围不明 | 关闭 | 两图纵轴均写“五时刻最大”；页脚和相邻图注明列t={0.05,0.1,0.25,0.5,1}，明确非连续时间上确界。 |

已实际查看两张原PNG及两份PDF的Poppler渲染。新标签、页脚、图注和种子形状可读，没有发现缺字、裁切或新遮挡；历史云端/本机来源、非CI范围、1e-2参考线以及τ=0.1主配置继续保留。

## 数字和来源保持一致

三份CSV与complete_v1逐字节相同；48条records、12组default_groups、6组tau_groups，以及全部比值、S6-SOAP判据、耗时、488项原始哈希清单、验证输入和运行状态等科学/来源字段完全相同。evidence仅`generated_local`、`figure_metadata`、`analysis_code_sha256`、`output_sha256`四个顶层字段变化。全部Markdown表格行逐字相同。

S6-SOAP的E1/E3 H/HL中位数比仍为300.0703499915824、30.828062990965837，均3/3≤1e-2；τ跨档最大/最小中位数比仍为1.7158122472919974、1.4302686790148533。它们沿用v1已完成的独立数据核查，不构成新的模型结果。

| CSV | 两版共同SHA-256 |
|---|---|
| all_new_runs.csv | `7b4784091953a3f62307e9ee6a8e41bc11b4dc3e652355ef6403e8c808e44fb5` |
| default_six_arms.csv | `cc3f3803811a9f5f0b3d99af0c2023b9f8aaf4c4d57b679f2ee7fed5ffcd51e2` |
| tau_sensitivity.csv | `509d29b90d56f2fca00c1377df44d7fd8818b67f1fcfc13d2da83a643e02ea16` |

从冻结提交`7d3857ea93d28c620af51dbc3fdf88e581adae0d`直接读取旧源与文件：v1九份正式产物均匹配先前审查快照和Git blob，两份v1独立审查报告保持原hash。分析源除`report`函数外AST完全相同，绘图输入验证函数AST也相同；当前两份源hash与v2 evidence一致。

## 冻结标识与范围

v2正式`analysis_evidence.json` SHA-256：`28753d87bf7cbc2af53d24eedd01927a50907abcfd42dfbaf50173005e8fea38`。作者修订清单SHA-256：`fe8a476155bf4a5c899d85495eaabd9ec9b6c5906849509a9311b2c4e8c8f737`。本轮24个相关文件前后哈希一致，v1审查报告未覆盖；只新增本文件及`V2_FOLLOWUP.json`。

本次未重复488个旧/新原始文件的全量哈希扫描、未重跑核心测试、未导入Torch、未加载模型或训练，也未读取仍在变动的完整稿。先前跨环境因果、三种子、固定时间点及历史执行证据的科学范围限制继续有效。完整稿完整性核验需另以明确冻结版本为对象。

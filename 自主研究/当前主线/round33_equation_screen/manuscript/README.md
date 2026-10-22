# R33 论文材料

当前是有明确缺口的工作稿，尚未交付完整初稿、未投稿。30次修订6实验于2026-10-23 00:08（UTC+8）启动。01:08调度器写入状态时退出，21个训练进程仍在运行，恢复状态见上级`PAPER_AUTOPILOT.md`及`validation/stage6_recovery_20261023/`。`D:\CodexRuntime\runs\r33_stage6_20261022\status.json`必须结合更新时间、实际进程身份和独立监督记录阅读；旧状态文件不能证明调度器仍活着，不能据此重复启动。

## 阅读顺序

1. `drafts/working_revised1.md`：当前修订正文，原始/新初值、架构叠加和负面结果已经写入，新增完整筛选表、实际实现配置及解析示意图；第4.5、4.6节等待τ灵敏度和SOAP64完整数据。正文10129汉字，冻结SHA256见独立复核报告。`drafts/initial_working.md`保留原版。作者身份、单位、基金和利益冲突尚待作者提供，不替作者声明。
2. `research/MATH_SOURCE_AUDIT.md`：局部层推导、缩放、渐近、初始导数迭代极限及保证范围。
3. `research/CITATION_CONTEXT.md`、`REFERENCES_VERIFIED.json`、`references.bib`：13条正文文献及1条备选、实际阅读版本、上下文和题录更正。
4. `process/writer_data_evidence.json`、`working_tables.md`：176个历史结果的独立重聚合与逐文件哈希；不包含正在运行的30项预测结果。
5. `integrity/working_20261023/REVISED1_FOLLOWUP_CN.md`：F01–F05关闭复核，六旧表、完整筛选及解析图核对正确；历史全生产链与机制因果证据仍有限制。工作稿预审与完整稿最终审查分开存放，不能相互替代。

`PAPER_CONFIGURATION.json` 与 `OUTLINE_AND_EVIDENCE.md` 固定文章范围及正文计数口径。`process/writer_phase4a.md` 和 `evaluator_phase6a.md` 是在对应稿件可见之前形成的标准承诺；当前 writer Phase4b 自评明确记录数据及篇幅未完整，不能当作审查通过。

## 数据与实验

正式结果仍在上级 `runs/`；原始数据不复制成另一个可随意编辑的主表。第一阶段来源为 `../validation/stage5_analysis_20261022/`。第二阶段分析入口是 `../validation/stage6_analysis_20261022/README.md`，其正式模式要求30/30结果与复核完成。

现阶段主配置仍是固定τ=0.1的Adam修正模型，调参次数为0；新τ只做灵敏度描述，不倒选主配置。默认比较、不同初值、架构与优化器内叠加、失效点分别报告。旧RBA、因果训练、PirateNet变体的实现和预算差异必须披露；云端与本机墙钟不能合为速度排名。

## 排版与复现

训练环境固定在 `D:\CodexRuntime\venvs\r33-torch214`，排版与绘图使用独立的 `D:\CodexRuntime\venvs\r33-analysis`。后者现有 matplotlib 3.11.2、pypandoc_binary 1.17、PyMuPDF 1.26.7；不修改训练依赖。

`render_manuscript.py` 可生成离线MathML HTML和XeLaTeX PDF。编译器只读取现有安装，关闭自动安装包与shell执行；中间TeX、日志和逐页预览均放在 `D:\CodexRuntime\runs\r33_paper_render`。PDF生成后仍要目视检查，自动几何检查不能代替排版验收。当前工作稿排版只作预检。

## 交付前仍需完成

- 全部30项完成、重载、N96/GL400复算、独立残差与原始文件哈希核验。
- 补齐正文、摘要、结论、逐种子图及完整表；更新计数、引用和数据映射。
- writer/evaluator契约检查、完整性核验、五个独立视角审查、逐项修订与复核。
- 最终数字/引用/主张检查，以及HTML/PDF图文布局检查。

保留所有负面结果。完成初稿和内部审查并不等同于通过真实期刊同行评审。

# R33 论文材料

2026-10-23 06:29（UTC+8），修订6的30项实验全部完成并通过数值验收，调度器真实退出码为0。完整分析已生成于`../validation/stage6_analysis_20261022/complete_v1/`；完成态运行记录与30个生产日志保存在`../validation/stage6_20261022/completion_archive_20261023/`。此前01:08发生的状态写入故障、原21项自然退出及后9项恢复派发的完整历史保留，见上级`PAPER_AUTOPILOT.md`与恢复目录。当前没有活动训练队列，不要再次启动实验。

完整初稿v1已冻结，正文11434汉字，六章、四图、13个含附录表格及13条参考文献。独立写作评估已接受；完整性预审为PASS WITH NOTES，允许进入五视角正式评审，不代表最终完整性通过或期刊录用。五视角原盲承诺保持，当前分批独立阅读全稿；后续修订另存版本。S6-SOAP满足固定配置内叠加判据，旧A-1/G2/E4负面结论保留。

## 当前阅读顺序

1. [完整初稿v1](drafts/complete_v1.md)：全部正文、摘要、结论、附录和声明；冻结SHA256为`8c5a83cff08732ce8e548cd873faa4e55cede075c3340fe9799e9deae37d4fd3`。作者身份、单位、基金、利益冲突及人类最终确认仍待作者提供。
2. [数学来源核查](research/MATH_SOURCE_AUDIT.md)、[引用语境](research/CITATION_CONTEXT.md)及`research/references.bib`：经典数学基础、推导边界、真实题录和阅读版本。
3. [完整稿生成记录](process/complete_v1/FROZEN_DELIVERY_MANIFEST.json)、[独立写作评估](process/evaluator_complete_v1/evaluator_phase6b.md)、[独立完整性预审](integrity/complete_v1_pre/INDEPENDENT_PRE_REVIEW.md)：作者自核和独立核验分开；历史执行链与更强机制主张仍有证据限制。
4. `reviews/full_v1/`：原始契约、五位独立审稿人的内容盲Phase1、冻结全稿输入包和实际派发记录。正式Phase2及编辑综合完成后另行存放，不把旧研究准备度报告当作全稿评审。
5. `../validation/stage6_analysis_20261022/complete_v2/`、`figures/history_v2/`及`figures/`内解析图：当前四幅图及逐点数据。展示v2已独立复核，科学CSV与v1逐字节一致，原版本保留。
6. `process/reproducibility_complete_20261023/`：30/30完成态复现检查（613项断言），连到原始生产记录与90个新产物；`process/reproducibility/`和恢复补充保存其历史时点，不冒充全部历史生产链完整。
7. `process/render_complete_v1/`：25页PDF实际渲染、字体/几何/图文检查和预览证据；HTML内容与嵌入资源已静态核对，本地浏览器预览被安全策略拒绝，因此没有HTML浏览器目视验收。

`PAPER_CONFIGURATION.json`与`OUTLINE_AND_EVIDENCE.md`固定文章范围和正文计数口径。`drafts/initial_working.md`、`working_revised1.md`以及各历史报告均保持原时点语境。当前完整稿的真实Phase4b在`process/complete_v1/writer_phase4b.md`，独立Phase6b在`process/evaluator_complete_v1/`；两者不能与旧工作稿记录混用。

## 数据与实验

正式结果仍在上级 `runs/`；原始数据不复制成另一个可随意编辑的主表。第一阶段来源为 `../validation/stage5_analysis_20261022/`。第二阶段分析入口是 `../validation/stage6_analysis_20261022/README.md`，其正式模式要求30/30结果与复核完成。

现阶段主配置仍是固定τ=0.1的Adam修正模型，调参次数为0；新τ只做灵敏度描述，不倒选主配置。默认比较、不同初值、架构与优化器内叠加、失效点分别报告。旧RBA、因果训练、PirateNet变体的实现和预算差异必须披露；云端与本机墙钟不能合为速度排名。

## 排版与复现

训练环境固定在 `D:\CodexRuntime\venvs\r33-torch214`，排版与绘图使用独立的 `D:\CodexRuntime\venvs\r33-analysis`。后者现有 matplotlib 3.11.2、pypandoc_binary 1.17、PyMuPDF 1.26.7；不修改训练依赖。

`render_manuscript_v2.py` 可生成离线MathML HTML和XeLaTeX PDF。编译器只读取现有安装，关闭自动安装包与shell执行；中间TeX、日志和逐页预览均放在 `D:\CodexRuntime\runs\r33_paper_render`。PDF生成后仍要目视检查，自动几何检查不能代替排版验收。当前完整v1排版只作预检，最终交付须待正式审稿、必要修订和最终独立核验。

## 交付前仍需完成

- 五个独立视角的正式审稿、机械编辑综合及必要的逐项修订和复核。
- 对最终稿从头独立核查数字、引用、主张与七类失败模式；保留无法补回的历史证据限制。
- 输出经实际渲染检查的最终论文及过程记录、数据和复现入口。

保留所有负面结果。完成初稿和内部审查并不等同于通过真实期刊同行评审。

# R33 第二阶段只读分析工具

本目录工具聚合已有产物，不训练、不调参、不补算旧模型诊断、不修改旧文件。正式分析只在 30/30 完成并绑定验证后发布；未齐时仅输出标为 `partial` 的运行状态。当前先交付代码模板，不以模拟数字生成论文图。

使用现有独立分析环境 `D:\CodexRuntime\venvs\r33-analysis`。所有依赖缓存/临时构建在 D 盘，训练环境不变。

```powershell
$env:TEMP='D:\CodexRuntime\temp'
$env:TMP=$env:TEMP
$env:PYTHONPYCACHEPREFIX='D:\CodexRuntime\cache\pycache'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:MPLCONFIGDIR='D:\CodexRuntime\cache\matplotlib'
$env:XDG_CACHE_HOME='D:\CodexRuntime\cache\xdg'
& 'D:\CodexRuntime\venvs\r33-analysis\Scripts\python.exe' '自主研究\当前主线\round33_equation_screen\validation\stage6_analysis_20261022\analyze_stage6.py' --partial
# 仅在结果全部完成之后运行：
& 'D:\CodexRuntime\venvs\r33-analysis\Scripts\python.exe' '自主研究\当前主线\round33_equation_screen\validation\stage6_analysis_20261022\analyze_stage6.py' --final
```

`--partial` 和裸入口只打印状态，不生成判据/正式表/图。`--final` 在任一完整门失败时退出码为 2，不生成正式产物。门要求：运行状态所有任务 completed；验证和汇总报告均完整 30/30 且结果一致；新任务集合精确匹配；源码/协议/完整 bundle/已有 398 文件 hash 不变；配置、种子、误差时刻、N64/N96 序列容差、残差点数和调用记录绑定通过。

`--partial`的任务数量仅代表保存的快照，不等于实时进程数量；输出包含快照年龄，超过120秒会标为`stale`，时间缺失或异常单独标记。120秒是运行诊断提示，不是科学判据。即使时间较新，本工具也不验证PID身份或授权重启。2026-10-23发生调度器退出而训练子进程继续的事件，恢复期间必须结合`../stage6_recovery_20261023/`及D盘独立监督记录，不得只看状态JSON派发重复训练。partial输入哈希绑定本次实际读取的字节，避免把两次不同快照混为同一输入。

正式输出：

- `all_new_runs.csv`：全部新 30 项，每种子完整体/迹序列、损失、heldout RMS/max、实际调用、环境和耗时。
- `default_six_arms.csv`：两方程 × Adam/SOAP64 × 三方法 × 三种子，共 36 行。默认 Adam 只读复用历史云端 confirm；不据结果挑优化器。
- `tau_sensitivity.csv`：两方程 × τ=0.03/0.1/0.3 × 三种子，共 18 行。τ=.1 只读复用 confirm；主配置仍为 .1，不选择最优 τ。
- `analysis_evidence.json`：全部分组、S6-SOAP 严格联合判定、τ 每档范围与跨档最大/最小中位数之比、488 个原始文件 hash、运行尝试和失败历史、图表来源与输出 hash。
- `STAGE6_ANALYSIS_20261022.md`：完整中文分析。
- `default_six_arms.png/.pdf`、`tau_sensitivity.png/.pdf`：各组全部真实种子、短横线中位数、最小–最大竖线；不创造 CI。旧 confirm 云端来源与新本机来源在图中注明。

绘图应用 `plot-from-data` 技能 `bar_grouped_hatch` 的分组、颜色、网格和 300 dpi 导出规范；因 n=3 且指标跨数量级，用真实种子散点/中位数/范围代替柱体。中文使用本地微软雅黑或黑体并检查字形，PDF 嵌入字体。无 LaTeX 或网络字体依赖。

旧默认组未保存的 heldout 残差和实际 closure 以空值明确标注，不补算。云端与本机墙钟分别描述，不计算速度倍数；并行进程耗时总和不冒充批次墙钟。S6-SOAP 是本批预注册判据，不是发表标准；原 A-1/G2/E4 负面证据保留。

正式文件不覆盖：已有 `analysis_evidence.json` 时拒绝再次发布。确需重出版本，使用 `--output` 指定本目录内的新子目录。构建先放 `D:\CodexRuntime\runs\r33_stage6_analysis_20261022`，所有输入复查后发布，JSON 最后作为完成标记。

测试使用标准库 unittest 和合成最小输入，只检查门/聚合边界；不会生成模拟论文图。执行：在本目录运行 `D:\CodexRuntime\venvs\r33-analysis\Scripts\python.exe -m unittest test_analysis -v`。完整数据到齐后的 PNG/PDF 尚须实际渲染并目视确认标签与布局，当前仅验证模板、字体与阻断逻辑。

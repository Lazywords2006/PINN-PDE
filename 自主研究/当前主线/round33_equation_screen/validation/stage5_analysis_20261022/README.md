# 第一阶段结果分析附件

本目录只汇总保存的实验产物，不运行训练、不选择配置、不改变协议。

- 阅读主报告：`../../STAGE5_ANALYSIS_20261022.md`。
- HTML 阅读版：`第一阶段分析与论文证据.html`，与两张 PNG 放在同一目录。
- `all_runs.csv`：176 次已保存实验的逐次指标；空值代表未保存/未在该批检验，不代表零。
- `analysis_evidence.json`：分组、配对比值、计时、398 个原始结果文件哈希、工程门及验证来源。
- `completion_status_snapshot.json`：完成时运行状态副本；训练批次已结束。
- PNG 为 300 dpi，PDF 为矢量版本；点对应真实种子，未使用模拟数据或置信区间。

复算命令（仓库根目录）：

```powershell
$env:TEMP='D:\CodexRuntime\temp'
$env:TMP='D:\CodexRuntime\temp'
$env:PYTHONPYCACHEPREFIX='D:\CodexRuntime\cache\pycache'
$env:MPLCONFIGDIR='D:\CodexRuntime\cache\matplotlib'
$env:XDG_CACHE_HOME='D:\CodexRuntime\cache\xdg'
& 'D:\CodexRuntime\venvs\r33-analysis\Scripts\python.exe' '自主研究\当前主线\round33_equation_screen\validation\stage5_analysis_20261022\analyze_stage5.py'
```

分析环境：Python 3.12.6、matplotlib 3.11.2、Markdown 3.11.2、NumPy 2.5.4；独立于训练环境。数值汇总使用 Python 标准库，绘图依赖 `requirements.txt`。脚本优先使用本目录完成状态快照。异机复算须保持工程门要求的训练源/证据字节，并按平台设置缓存目录；若 Git 换行转换导致哈希不同，应核对字节来源，不能关闭检查后声称完整性验证通过。

验证范围：复用已通过的模型重载和数值重算报告，重新核对原始文件 SHA256、22 项验证绑定、176 行聚合、加密误差容差及训练源一致性。两张图已查看并修正标签重叠，HTML 已检查表格/图片引用；没有把 HTML 静态结构检查说成浏览器实测。原 `problems.py`、`pinn1d.py`、`SCREEN_PROTOCOL.md` 未修改，71 项测试结果仍对应当前训练源；本轮未重新运行训练测试。

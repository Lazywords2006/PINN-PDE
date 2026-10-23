# complete_revised1a 排版预检与 renderer v3 回归

本报告仅覆盖下列固定稿件和排版器的预检；不替代修订核验、最终完整性检查、人类作者确认或期刊审稿，也不适用于后续 delivery_candidate。

| 对象 | SHA-256 |
|---|---|
| complete_revised1a.md 与本轮字节快照 | 398c2a44f2f9fd959b62564ddc599b123a3dd5de168ad0257a8572e188bf92e8 |
| render_manuscript_v3.py | f510d09de47d64795256fa749f3ed37420fd4eff00b1462545f8c8f0307014a4 |
| 冻结 render_manuscript_v2.py | fee7a28695faf9c849534e98a49ca5c72e06bf03b3a91604e574bfadceebafa5 |
| complete_revised1a.html | faeb7bbd066c9f299f8972ab2aade515863a75577ae2b01f0cd160e7450c09c8 |
| complete_revised1a.pdf | bb57f015d44c12d15d55b3a6893b2aee29f31aa9fd124d2c57a0a9bbe0a1aad7 |

## 结论与修复范围

实际生成27页PDF，CLI退出0；Missing character为0，Overfull为0，27页文本及图片块均无物理页面越界。旧预检发现的附录E缺字由作者代理在1a源稿中改为数学表达式；长路径由源稿简短链接消除。排版代理未修改该源稿、表格数据、研究协议或训练代码。

v3从冻结v2派生，保留11pt字号、22mm页边距、1.25倍行距、全部正文/表格/图像及四幅图的手写图注。安装的 needspace.sty 位于 `C:/Users/LazyM/AppData/Local/Programs/MiKTeX/tex/latex/needspace/needspace.sty`，由 kpsewhich 实际定位。v3只识别“表编号+分隔空白”且下一块为Pandoc longtable的11处真正表题，预留实际表题高度加7个正文基线；若其前紧邻节标题，则连同节标题预留11个正文基线。本稿只有4.7节符合这一特例。表体仍允许跨页；讨论段和表注不进入该规则。编译缓存目录包含v3源哈希，TEMP/TMP也位于该工作目录的temp子目录。

第一次v3尝试（2f62cced7fc0...）在第15页末留下孤立4.7节标题；该尝试保留于独立目录，仅供失败回归证据。当前f510d09...版本已消除此缺陷：4.7节标题、表8标题与表体同在第16页。旧v2缺字失败报告仍原样保留。

## 实际检查

- 27页全部接触图已实际查看；另查看第6、7、9、10、11、12、13、14、15、16、20、21、22、23、24、25、26、27页120dpi原页图，覆盖全部表格出现页、四幅图、附录E及末页。
- 四幅图仍在第6、11、14、15页；图、坐标、图例及完整图注可读，同页，无裁切或重复自动图题。
- 11处有编号表题与该表的表头及第一数据行同页，页码依次为7、10、10、12、12、13、14、16、23、24、26；视觉检查与PDF提取定位一致。源37个标题中未发现独立留在页末的节标题。
- 第25页附录E的四条显示公式及正文中的 Delta_y、U_t、U_yy、U_y 下标完整。第26页表E1保留4种方法和全部3个种子、体/迹中位数与阈值计数。第27页声明整节排在同页，AI参与与责任边界完整，无截断尾行。
- 14张表的行列及数据保留。表3跨第10—11页，续页有重复表头和最后一条数据行；这属于可读的长表分页，未做尾行整体搬移。第13页表6的最小—最大列仍有科学记数法分行显示；值未丢失，精细出版版可进一步调整列宽。两项均已明确记录，未越过本次仅修复表题keep的授权范围。
- 日志仍有2条Underfull和4条ignored Infinite glue shrinkage，实际对应长表分页未见重叠、截断或越界；并非零诊断消息，原日志保留。

## HTML静态验证及内容回归

未用浏览器、HTTP服务、其他浏览器或CDP加载HTML；既有URL安全拒绝未被绕过。

同稿同label以冻结v2生成的HTML与当前v3 HTML逐字节一致。37个源标题和950个不含数学/图像的段落及表格单元文本片段均在静态HTML中可定位；14表的行列和单元文本逐一相同；29个MathML节点的TeX annotation与源数学节点逐一一致；4幅嵌入PNG与源文件字节及SHA-256一致；script计数0，替代字符U+FFFD计数0。

旧rev1与rev1a的14个Table AST和4个Image AST逐字相同。对真实旧TeX应用v3规则只包装11处实际表题，移除这些布局包装后可精确恢复原TeX（包括节标题），证明这一转换未改表内容。此证据不能扩展为浏览器字体、屏幕布局或交互验收，也不是科学内容终验。

## 实际命令与证据

```powershell
& 'D:/CodexRuntime/venvs/r33-analysis/Scripts/python.exe' 'E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/render_manuscript_v3.py' 'E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md' --output 'D:/CodexRuntime/runs/r33_paper_render/revised1a_pre_20261023_398c2a44f2f9_v3_f510d09de47d' --label '修订初稿排版预检；修订核验及最终完整性检查尚未完成，未投稿' --pdf
```

PDF图像由实际Poppler命令 `pdftoppm.exe -r 120 -png <PDF> <output>/pages/page` 产生。其后运行同目录 `inspect_snapshot.py` 和 `layout_regression.py`。PDF文本比较只归一化空白、减号字形及Unicode上标数字；另行实施视觉检查。

主运行目录：`D:/CodexRuntime/runs/r33_paper_render/revised1a_pre_20261023_398c2a44f2f9_v3_f510d09de47d/`。

编译目录：`D:/CodexRuntime/runs/r33_paper_render/complete_revised1a_398c2a44f2f9_renderer_v3_f510d09de47d/`。

证据包括源快照、v3快照、PDF、HTML、render.json、static_and_pdf_checks.json、layout_regression.json、完整页图、接触图、两份检查脚本及编译日志。render.json中的visual_review=pending是自动renderer的原始输出；本报告记录后续实际视觉检查，不篡改原始记录。

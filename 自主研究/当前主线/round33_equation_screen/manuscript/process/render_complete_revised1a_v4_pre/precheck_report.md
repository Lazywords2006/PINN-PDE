# complete_revised1a 排版预检与 renderer v4 区间回归

本报告仅覆盖固定稿件 complete_revised1a 与派生排版器 v4 的排版预检，不替代修订核验、最终完整性检查、人类作者确认或期刊审稿；不适用于后续 delivery_candidate。实际页眉状态为“修订初稿排版预检；修订核验及最终完整性检查尚未完成，未投稿”。

| 对象 | SHA-256 |
|---|---|
| complete_revised1a.md 与本轮字节快照 | 398c2a44f2f9fd959b62564ddc599b123a3dd5de168ad0257a8572e188bf92e8 |
| render_manuscript_v4.py | 2507932eeb47752c7e245d7c9d7a293dcc5fd4889ce82b0ebcb997ce386bc504 |
| 已冻结 render_manuscript_v3.py | f510d09de47d64795256fa749f3ed37420fd4eff00b1462545f8c8f0307014a4 |
| complete_revised1a.html | faeb7bbd066c9f299f8972ab2aade515863a75577ae2b01f0cd160e7450c09c8 |
| complete_revised1a.pdf | 7e0bebd895e1515e35bb93e4e53814e025819017015c9d562fdb069cea6b000c |

## 结果和授权范围

实际生成27页PDF，CLI退出0；Missing character为0，Overfull为0，27页文本及图片块均无物理页面越界。11处有编号表题与该表的表头及第一数据行同页；未发现孤立留在页末的节标题。旧rev1的缺字、长路径溢出和表2表题脱离表体问题已在1a及v3中解决，并由v4保留。

v4从已冻结的v3派生，只对TeX longtable内明确匹配的科学计数法区间 a--b 包装：每个端点整体置于不可断行盒内，原范围分隔符两侧允许断行。本稿共6组、全部位于表6。端点、指数、分隔符、字符顺序和数值完全保留；移除新增的6组包装后，整个TeX文件与冻结v3逐字节一致。11pt字号、22mm页边距、1.25倍行距、图像与手写图注策略、表题预留策略均未变化。排版代理未修改源Markdown、表数据、研究协议或训练代码。

## 视觉检查与回归

- v4全部27页由Poppler实际生成120dpi页图，并与已完成视觉检查的v3逐页比较原始RGB像素：仅第13页变化，其余26页尺寸和每一个像素完全相同。其余26页复用v3的实际视觉检查，未虚称重新逐页查看。
- 第13页已实际打开查看：表6的6组最小—最大值均保持完整端点，指数不再拆开；可在端点与范围线之间换行，行高保持，表头和全部数据清楚，无裁切、重叠或越界。
- v3已实际查看全部27页接触图，并查看第6、7、9、10、11、12、13、14、15、16、20、21、22、23、24、25、26、27页120dpi原页图，覆盖全部表格出现页、四幅图、附录E及末页。v4中除第13页外这些证据由相同像素关联。
- 四幅图仍在第6、11、14、15页，完整图注同页，无重复自动图题；第16页4.7节标题、表8标题与表体同页；第25页附录E公式下标完整；第26页表E1保留4种方法、3个种子和阈值计数；第27页声明及AI参与责任边界完整。
- 表3仍跨第10—11页，续页有重复表头和最后一条数据行，保持可读；本次未继续调整长表分页。
- 编译日志仍有2条Underfull和4条ignored Infinite glue shrinkage，与v3一致。实际长表页面未见重叠、截断或越界；并非零诊断消息，原日志保留。

## HTML静态与内容完整性

HTML与同稿同label的v2/v3输出逐字节一致。静态检查确认14张表的行列及单元文本、37个标题、950个不含数学/图像的段落及单元文本片段、29个MathML节点的TeX annotation和4幅嵌入PNG均与源内容对应。script计数0，替代字符U+FFFD计数0。旧rev1与1a的14个Table AST及4个Image AST仍相同。

未用浏览器、HTTP服务、其他浏览器或CDP加载HTML；未绕过既有URL安全拒绝。本报告只确认HTML静态源及嵌入资源，未完成浏览器字体、屏幕布局或交互验收。

## 命令及证据

```powershell
& 'D:/CodexRuntime/venvs/r33-analysis/Scripts/python.exe' 'E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/render_manuscript_v4.py' 'E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1a.md' --output 'D:/CodexRuntime/runs/r33_paper_render/revised1a_pre_20261023_398c2a44f2f9_v4_2507932eeb47' --label '修订初稿排版预检；修订核验及最终完整性检查尚未完成，未投稿' --pdf
```

PDF页图由实际Poppler命令 `pdftoppm.exe -r 120 -png <PDF> <output>/pages/page` 产生；随后运行 `inspect_snapshot.py`、`layout_regression.py` 和 `range_regression.py`。PDF文本定位只归一化空白、减号字形及Unicode上标数字；另行实施视觉检查及像素回归。

输出目录：`D:/CodexRuntime/runs/r33_paper_render/revised1a_pre_20261023_398c2a44f2f9_v4_2507932eeb47/`。

编译目录：`D:/CodexRuntime/runs/r33_paper_render/complete_revised1a_398c2a44f2f9_renderer_v4_2507932eeb47/`。

项目内证据：`E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/render_complete_revised1a_v4_pre/`。

证据包括固定源快照、v4快照、PDF、HTML、render.json、static_and_pdf_checks.json、layout_regression.json、range_regression.json、完整页图、接触图、检查脚本及编译日志。render.json中的visual_review=pending是自动renderer原始输出；本报告记录其后的实际视觉检查，不改写原始记录。旧v2失败证据和v3已完成预检证据已分别冻结，均未覆盖。

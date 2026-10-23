# complete_revised1 排版预检：发现阻断项

这是修订初稿的排版预检，不是最终交付、科学审稿或投稿验收。仅适用于下列 SHA-256 的原稿；不得迁移到后续修订稿。

| 对象 | SHA-256 |
|---|---|
| complete_revised1.md（字节快照） | 5eb4cf00f663aa18face96dc503c7e3d35420e2d809489e0cad5f176f8bdd68a |
| render_manuscript_v2.py | fee7a28695faf9c849534e98a49ca5c72e06bf03b3a91604e574bfadceebafa5 |
| complete_revised1.html | 4fbfa17237d48d93933e1bf90f8c158f0de75d0974444adf599d965fe07a6e06 |
| complete_revised1.DIAGNOSTIC-missing-glyphs.pdf | 1d0e333a224f0894502e1b8daaa41cf32fc96cb786f79109bc9fe4ef858a0b96 |

## 实际执行

```powershell
& 'D:/CodexRuntime/venvs/r33-analysis/Scripts/python.exe' 'E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/render_manuscript_v2.py' 'E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md' --output 'D:/CodexRuntime/runs/r33_paper_render/revised1_pre_20261023_5eb4cf00f663' --label '修订初稿排版预检；修订核验及最终完整性检查尚未完成，未投稿' --pdf
```

CLI 退出码为 1。XeLaTeX 两遍已生成 27 页 PDF，renderer 因缺字门禁停止，未生成成功的 render.json。其诊断 PDF 另名保存，不当作可交付 PDF。实际渲染用 Poppler `pdftoppm.exe -r 120 -png <diagnostic.pdf> <output>/pages/page`；检查脚本为同目录 `inspect_snapshot.py`。

运行目录：`D:/CodexRuntime/runs/r33_paper_render/revised1_pre_20261023_5eb4cf00f663/`。冻结 renderer 的编译工作目录为 `D:/CodexRuntime/runs/r33_paper_render/complete_revised1_5eb4cf00f663_renderer_v2_fee7a28695fa/`。renderer 自身固定子进程 TEMP/TMP 为 D:/CodexRuntime/temp；未修改该冻结实现。

## 实际发现

1. **阻断：第25页附录E缺字。** 原稿第645、654行使用 Unicode 下标 `ᵧ` 和 `ₜ`，SimSun 缺少相应字形。paper.log 有6条 Missing character（5个ᵧ、1个ₜ）；页图可见初始通量错配及辅助热方程的下标空缺。展示的四条独立公式E1—E4本身可读，问题位于其相邻正文公式。
2. **排版缺陷：第9页末表2标题与第10页表体分离。** 标题为两行，整张表从下一页才开始；需要将实际表题与表头/首行保持同页。其他已检查表题未见相同分离。
3. **轻微溢出：第19页参考文献后的 citation_contexts.md 长路径。** paper.log 报1条 Overfull hbox，超出正文行宽1.53183pt（生成TeX第763—764行）；未超出物理页面边界，仍须保留该警告。
4. **可读性提示：第13页表6的最小—最大列较窄。** 科学记数法有跨行拆分（如e−/04），未丢失数值，建议最终版留意该列宽。本预检未改动表格。

日志另有2条 Underfull hbox、4条 ignored Infinite glue shrinkage。已核查对应长表分页，未见数据行重叠或页面外溢；这些诊断消息未删除。

## 检查覆盖及边界

- 已查看27页的全部5张接触图；另实际逐页查看第6、7、9、10、11、12、13、14、15、16、19、20、21、22、23、24、25、26、27页120 dpi原页图。检查了所有表格出现页、四幅图及附录E、最后一页。
- 四幅图分别在第6、11、14、15页。坐标、图例与面板可读，无裁切；各自完整手写图注均在同页。不存在重复生成的自动图题。
- 14张表均保留表头和数据列；长表跨页处有重复表头，无肉眼可见行截断/重叠。第26页表E1包含4种方法、seed 0/1/2、体误差中位数、迹误差中位数及阈值计数。
- 第27页是声明续页：首段延续有两行，其后AI参与说明及责任边界完整；末尾无截断、无独立单行尾页。全文接触图未见单行段落孤悬；第4—5页有公式引导语与公式跨页，第22—23页两条RBA显示公式跨页，作为预览可读但未进行精细出版分页。
- 27页PDF文本/图像块几何检查均未越过物理页面边界。几何检查不代替上述视觉检查，也不排除1.53183pt正文行宽溢出。
- HTML只做静态结构与文本核验，未执行浏览器。37个源标题和952个不含数学/图片的段落或表格单元文本片段在HTML中均可定位；14张表行列和单元文本逐一一致；26个数学节点对应26个MathML和逐字一致的TeX annotation；4张嵌入PNG与源图字节及SHA-256一致；无script、无U+FFFD替代字符。
- HTML结果只证明保存内容、MathML和嵌入资源结构；未声明任何浏览器中的字体、换行、屏幕布局或交互验收。此前URL安全拒绝未通过本地HTTP服务、其他浏览器或CDP绕过。
- 原稿、冻结renderer、科学数据、协议、训练代码均未改动。本轮不检查科学结论或数据真实性，不得称最终PASS。

详细机器证据见 `static_and_pdf_checks.json`、`source_ast.json`、`inspection_stdout.txt`、`pages/` 与编译目录 `paper.log`。

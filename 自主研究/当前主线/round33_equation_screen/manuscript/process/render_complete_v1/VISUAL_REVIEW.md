# 完整稿 v1：renderer v2 排版预检

本轮只修复原渲染器的自动英文图号与末页孤行，未改正文、图表、公式或科学结论。原稿 SHA-256 保持 `8c5a83cff08732ce8e548cd873faa4e55cede075c3340fe9799e9deae37d4fd3`，原 `render_manuscript.py` 保留不变。新版另存 `manuscript/render_manuscript_v2.py`。

修复采用 Pandoc `-implicit_figures`，保留原稿四段完整中文图注；四幅图片与各自中文图注使用无自动编号的同页排版块。增加段首/段尾孤行罚值和不拉伸页底设置。正文仍为11pt、22mm页边距、1.25行距，没有缩小字号或改动正文。第一次 v2 生成发现普通图片段继承首行缩进而产生4个溢出告警，第二次用同页排版块消除，初次报告保存在 `attempt1_render.json`，最终结果单独保存。

最终预检 HTML 与 PDF 位于：

- `D:/CodexRuntime/runs/r33_paper_render/complete_v1_renderer_v2_preview_final/complete_v1.html`
- `D:/CodexRuntime/runs/r33_paper_render/complete_v1_renderer_v2_preview_final/complete_v1.pdf`

新版PDF仍为25页。已在工具中查看全部25页的 `contact.png`，并原尺寸查看第6、11、14、15页的四幅图及第25页末页，检查图号、中文图注、可读性、页边界和页码。未见重复“Figure N”标签、图片/图注分离、覆盖或裁切。末页现有22行正文，含成本段及完整声明，不再只有一行。正文、表格和公式的总体版式保持原排版尺度；为保持图片和长图注同页，部分页尾留白是正常排版结果。本轮未展开新的科学审查。

自动内容核对见 `render_checks.json`：HTML可见正文在仅剔除原版4个自动图题后完全相同；生成的TeX正文在仅剔除图环境/同页排版包装后完全相同。22个展示公式、13份表格的TeX逐字相同，4幅嵌入HTML的图片与原文件逐字节相同。HTML含22个离线MathML元素、0脚本、0外部资源依赖，四段原中文图注保留。最终编译为0缺失字形、0 overfull、0页外内容块。

`render_checks.json` 的视觉字段保留自动检查不能替代目视的提示；本文件记录随后实际完成的目视检查。最终输出、渲染器与本目录证据的哈希见 `render_manifest.json`。该结论仅限审稿前排版预检，不是完整稿科学审查、最终交付或投稿通过。

# 历史数据图 v2 限定独立复核

结论：**限定复核通过**。v1 的中位数线遮挡问题 V1 已关闭；v2 的 PNG/PDF 中三种种子标记轮廓完整，标题和图注准确表述为 Adam＋L-BFGS 训练路线。CSV、12 组统计、12 次配对及 36 项输入哈希与 v1 完全一致，没有发现新增问题。

## 版本及改动范围

以已冻结提交 `01bfb621c91ae96b6c8e1473a026060f155654a4` 为 v1 基准，直接读取提交中的原始源文件，并逐字比对当前源。仅发现以下五处已说明修改：模块描述改为 Adam plus L-BFGS；中位数横线 `zorder=5→3`；主标题明确 Adam＋L-BFGS；图注开头明确该训练路线；默认输出目录改为 `history_v2`。没有附加源代码改动，数值算法、位置、种子标记、颜色、轴范围、参考阈值、面板标题和负面案例标注未变。

v1 五项原始产物与两份独立审查报告共 **7/7 文件**与冻结提交逐字节相同；同时匹配 v1 审查保存的 SHA-256。冻结的 v1 原源 SHA-256 为 `2e455bf832eb3857e2b1ed779cb71b67026e338185515e3c9f40dd75c6a3020a`。两版工作稿也匹配 v1 审查快照。

## 数据与证据一致性

- v1/v2 CSV 逐字节相同，SHA-256：`a2987b60e0be5448ea04c3d1bcd902e7d3030ff802402f3344655401e031fb60`。
- `groups` 的 12 组完整对象（含各种子、median/min/max）完全相同；`pairs` 的 12 个完整对象完全相同。
- 两版 `raw_sha256` 的 36 项完全相同；本轮重读这 36 份 JSON 字节，全部匹配两版记录与旧 398 项冻结清单。
- evidence 仅 `generated_utc`、`source_sha256` 和 `outputs` 三个顶层字段发生预期变化；CSV 输出哈希保持不变。
- 原初值改善 **6/6**、新初值改善 **5/6**，新 E3 种子 0 的退步 **3.56980745963111%** 均未变化。
- 图注仅更改开头的训练路线措辞，其余科学范围说明逐字相同。

## PNG/PDF 目视复核

独立查看了 v2 PNG 和通过 Poppler 渲染的 v2 PDF。中位数线图层为 3，散点为 4，同种子连线为 2。圆、三角、方形在中位数附近保持完整轮廓，原问题 **V1：关闭**。中位数线仍然可辨，全部点及新 E3 种子 0 的 `3.57%` 退步标注保留且可读；未见字体缺失、裁切或新遮挡。

标题“默认 Adam＋L-BFGS：原初值与固定新初值”及图注“默认Adam＋L-BFGS训练路线”与 v1 已核对的训练记录一致，避免将最终误差理解为纯 Adam 阶段结果。各面板的历史云端/本机区分，以及分别训练、非置信区间和完整对照须阅读正文的说明继续保留。

## 审查边界与保护核验

本轮只做 v1→v2 视觉/标题修订及数据一致性复核；完整 36 点数据审查沿用被冻结的 v1 报告。没有导入 Torch、读取模型权重、重新计算模型预测、启动训练、安装依赖或修改已有文件。检查前后 **52** 个相关文件的哈希保持一致，仅新增本报告与配套 JSON。

历史完整退出码/警告绑定的限制未被本次排版修订消除；本图仍不覆盖 RBA、因果训练、PirateNet、弱错配与 E4，不能据此推出普遍优势或全稿最终审查结论。

## v2 快照

| v2 文件 | SHA-256 |
|---|---|
| manuscript/figures/plot_historical_comparison.py | `b364d0542afe6fafb73e196d4d8a9291fc723560b114281ecf88ce82b52cb303` |
| manuscript/figures/history_v2/historical_comparison.pdf | `41ee7b649f7a8dfa0c006615bdecc1b926315f7a1b98fee2d1d2672427e4f8c6` |
| manuscript/figures/history_v2/historical_comparison.png | `433b14dfb1f00bec71752f1ce47e2a643e3ce5867cb101171e0a9fcd08fc41bf` |
| manuscript/figures/history_v2/historical_comparison_caption.md | `195adea13aea8b33ceefb10948edb17600203035c66e6ad001ae149091f027f6` |
| manuscript/figures/history_v2/historical_comparison_data.csv | `a2987b60e0be5448ea04c3d1bcd902e7d3030ff802402f3344655401e031fb60` |
| manuscript/figures/history_v2/historical_comparison_evidence.json | `99c264211fd477d6845eadaa0d26ab7e6622f7b72cd15d8324b9ed1d630c4bea` |

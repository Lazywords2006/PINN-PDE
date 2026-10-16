# 参数化 Bloch 谱簇的神经求解研究

研究对象：二维参数化 Bloch–Schrödinger 本征问题的最低两态谱簇。完整状态见[当前研究总档案](总览/00_当前研究总档案.md)。

## 现在在做什么

1. **当前主线（进行中）**：寻找真正新的神经求解机制，同时交付完整数学模型、合格数据，并说明与已有论文的实质区别。最新是 R29"相位相干成对 Fourier 模式激活"，目前只有机制定义，还没有实验。入口：[自主研究](自主研究/README.md)。
2. **投稿论文（冻结）**：SR-SC-NARR《参数化 Bloch 谱簇中神经增强的条件性收益与局限》，已修订完成，等待作者确定署名、投稿目标和是否公开。[中英文 Word/PDF](论文与证据/paper/v3_submission/)。
3. **副线成果**：Eig-PIELM 版本限定技术纠错（R11/R17/R18/R25），独立保存。

## 目录

```
PINN-PDE/
├── 总览/          当前研究总档案（唯一状态入口）；历史/ 存旧版 README、旧总档案
├── 自主研究/      当前主线/（R19 起，含各轮交付 zip）、历史_R01-R18/、状态控制文件
├── 论文与证据/    论文稿（paper/）、docs、figures、data、results、artifacts、logs
├── 独立诊断/      2026-09 对 V3 方法的 P0、P1/P2、AutoStudy 诊断
├── 论文审查/      SR-SC-NARR 的审查报告与修订记录
├── 文献库/        当前主线相关 PDF
└── 代码/          独立 git 仓库（GitHub：PINN-PDE-code），只含代码
```

两个 git 仓库：本目录对应 GitHub [PINN-PDE](https://github.com/Lazywords2006/PINN-PDE)（文档与研究记录）；`代码/` 对应 [PINN-PDE-code](https://github.com/Lazywords2006/PINN-PDE-code)（只含代码），已写入 `.gitignore`。`论文与证据/` 体积大，只在本地保存，不进 git。

## 2026-10-11 整理说明

- 目录去掉了编号前缀，`PINN-PDE-code` 并入为 `代码/`。
- 04、05、06、01 的旧名字保留为 Finder 中隐藏的符号链接：冻结的运行清单和复现命令里仍写着旧路径，靠它们保证能解析。`Paper/PINN&PNE` 和 `Paper/PINN-PDE-main-20260730` 同理。
- 新旧路径对照见 [MOVE_LOG](自主研究/MOVE_LOG_20261011.tsv) 末尾的第二阶段记录。

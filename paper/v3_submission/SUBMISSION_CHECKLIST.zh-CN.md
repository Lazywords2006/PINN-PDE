# V3 投稿检查表

## 已完成

- [x] 二维真实 PDE 本征问题与周期边界；
- [x] 交叉感知 rank-2 projector 定义；
- [x] D6 正确壳层与 kinetic tie closure；
- [x] 160点、3 seeds、11方法、5,280行 formal；
- [x] 强 Fourier-25、fixed hybrid、rank-37 shell-3 对照；
- [x] IID/exact/near/OOD/gap-scan；
- [x] projector、eigenvalue、p95、maximum、residual、延迟、显存；
- [x] cutoff 20/24/28 与 grid 65/97 收敛；
- [x] orthogonality、raw Hermiticity、external gap；
- [x] 2,000次 stratified point bootstrap；
- [x] family-specific 与 routing ablation；
- [x] 12张论文图和数值表；
- [x] 66篇核验文献，50篇正式期刊；
- [x] 中英文 Markdown、DOCX、PDF；
- [x] DOCX逐页渲染与无障碍检查；
- [x] 完整 evidence archive 和 SHA-256；
- [x] GPU 实例关闭。

## 作者必须填写

- [ ] 作者姓名、顺序、单位、地址；
- [ ] 通信作者、邮箱、ORCID；
- [ ] CRediT 分工；
- [ ] 基金项目；
- [ ] 利益冲突最终确认；
- [ ] 数据/代码公开时间和匿名策略；
- [ ] AI assistance 声明是否符合目标期刊政策。

## 投稿当天核查

- [ ] 用学校订阅复核当年 JCR/中科院分区；
- [ ] 复核学校认定与预警名单；
- [ ] 下载并套用最新 author guidelines/template；
- [ ] 检查 word/page/reference/figure 限制；
- [ ] 检查 single-blind/double-blind 要求；
- [ ] 把作者占位符全部替换；
- [ ] 更新 cover letter 的期刊名和通信作者；
- [ ] 检查所有 DOI、卷期、页码与发表状态；
- [ ] 核验 `SHA256SUMS.txt`；
- [ ] 确认没有混入 superseded P2/Q3 数字。

## 禁止事项

- [ ] 不重跑或重开160点 formal；
- [ ] 不移动阈值或使用 formal 调参；
- [ ] 不写“所有势族都获得神经提升”；
- [ ] 不写“projector accuracy 最优”或“比 Fourier-25 更快”；
- [ ] 不写“router 已跨势族泛化”；
- [ ] 不把 Wang–Xie/Dai 适配写成官方复现；
- [ ] 不把 Ky Fan、Ritz、谱投影、Fourier 或神经子空间单独写成首创。

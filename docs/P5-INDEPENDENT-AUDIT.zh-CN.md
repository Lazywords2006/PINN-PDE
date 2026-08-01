# P5 权威证据独立审计与科学判定（2026-08-01）

## 最终结论

权威证据已回传，独立审计 **PASS**；冻结科学判定为 **`P5_PROMOTION_STOP`**。

- 证据包：`artifacts/p5-evidence-20260801-092048.tar.gz`
- SHA-256：`56891c5740eb94c62299b72869d790a1cbdee6abda3fae2903ed822f5e405101`
- 运行矩阵：6 方法 × 2 势族 × 3 seeds = 36/36，0 失败
- 执行源码：commit `c04c43396a17d0dafe03cb74cf17c96fc5789ef9`，工作树干净
- 设备：AMD MI300X / ROCm，PyTorch `2.10.0+git8514f05`，HIP `7.2.53211`
- frozen final：未打开

这里的 `STOP` 是科学门槛未通过，不是文件损坏、程序错误或 GPU 失败。

## 独立检查了什么

`scripts/audit_p5_evidence.py` 没有信任执行机汇总，而是重新检查：

1. 外层 sidecar 与压缩包 SHA-256；
2. tar 路径安全性、重复成员和 manifest 中每个文件的字节数、SHA-256；
3. 36-run 身份矩阵及每个 `result.json` 的完成状态；
4. 每个 `final.pt` 的哈希是否与 `result.json` 一致；
5. 每份 `metrics.csv` 的 32 行数据、split 均值、最大正交误差和 Gram 条件数；
6. 从 36 个 run 重新聚合 summary、paired comparison 与完整 gate；
7. 重算 gate 是否仍得到 `P5_PROMOTION_STOP`。

所有检查均为 true，缺失 run、意外 run、manifest 失败和 run artifact 失败均为 0。

## 核心数值（越低越好）

| 方法 | near-cluster | gap-scan | 科学解释 |
|---|---:|---:|---|
| `p5_static_low_rom` | 0.11018 | 0.14920 | 被检验的低频 ROM 候选 |
| `p5_anchor` | 0.12323 | **0.14013** | 候选 near 改善 10.58%，但 gap 更安全 |
| `p5_wide_anchor` | 0.11910 | 0.15098 | 参数量匹配控制 |
| `p5_long_anchor` | **0.10616** | 0.15930 | 等算力控制在 near 上反超候选 3.79% |
| `p5_unanchored_low_rom` | 0.17171 | 0.21828 | 去掉 anchor 后明显退化 |
| `p5_highfreq_rom` | 0.12110 | 0.14783 | 频率结构控制，候选只改善 9.01% |

候选相对基础 anchor 在 6 个势族×seed 组合中胜 5 个，但相对 long-anchor 只胜 3 个。
候选 gap-scan 比最佳非 ROM anchor 高约 **6.47%**，超过冻结的 2% 非退化容限。

## 逐点失败分析

每个 run 有 32 个 validation 点：8 IID、4 exact-cluster、8 near-cluster、6 strict-OOD、
6 gap-scan。把相同势族、seed 和参数点严格配对后：

| 候选对照 | 逐点胜率 | 平均误差差（候选−对照） |
|---|---:|---:|
| anchor | 117/192 = 60.9% | −0.00844 |
| wide-anchor | 105/192 = 54.7% | −0.00540 |
| long-anchor | 92/192 = 47.9% | +0.00146 |
| unanchored-low-ROM | 179/192 = 93.2% | −0.05085 |
| highfreq-ROM | 120/192 = 62.5% | −0.00703 |

与基础 anchor 比较时，候选在 exact、IID、near 和 strict-OOD 的平均误差较低，但在
gap-scan 仅胜 **9/36** 个逐点配对，平均误差反而增加 `+0.00907`。这说明失败不是
“整体训练崩溃”，而是 ROM 候选在专门的谱隙扫描区域缺乏安全性。

逐点误差差与参考 external gap 的线性相关只有约 `+0.045`，与 internal gap 约
`−0.017`。因此仅用一个简单谱隙阈值未必能可靠检测全部失败；下一机制必须先验证风险
分数是否能在**不读取真值 projector**的条件下区分候选失败点。

## 为什么低频 ROM 不能作为当前论文主创新

1. 相对普通 anchor 的近簇提升真实存在，但等算力 long-anchor 能达到更低 near 误差；
2. 候选没有通过“比每个控制至少好 5%”和“每个势族均改善”；
3. gap-scan 出现 6.47% 回退，违反安全门槛；
4. 去掉 anchor 后 ROM 明显退化，说明已观察优势高度依赖 anchor；
5. 参数量增加约 23.6%，训练时间增加约 32.4%，不能忽略成本解释。

因此不能在标题或摘要中宣称“提出的低频 ROM 机制稳定优于基线”。它适合作为负结果、
消融和方法设计依据。

## 下一步允许做什么

先做一个新的、与 frozen final 隔离的小型 validation 机制验测：

1. 从原始逐点数据构造无标签风险特征：PDE residual、Gram condition、chart 角度、预测
   Ritz 外部间隔和多视图不一致；
2. 只在现有 validation 上评估 risk–coverage：风险分数能否优先覆盖 gap-scan 的退化点；
3. 若风险排序有效，再测试“anchor 主预测 + 局部 ROM 修正 + 高风险回退”的条件路由；
4. 与 anchor、long-anchor 和静态 ROM 使用相同预算、3 seeds、两个势族；
5. 只有 near 改善、gap 非退化和风险校准同时通过，才冻结新的 promotion 协议。

不能直接开启 frozen final，也不能通过修改旧门槛或增加旧方法步数把 STOP 改写成 GO。

## 投稿判断

- 课题属于真实的神经网络求解二维本征 PDE，没有跑题。
- 当前工程和证据链达到可复核研究原型水平。
- 当前低频 ROM 方法不达到 SCI 四区完整投稿线，SCI 三区更不足。
- 研究仍可继续，但下一篇论文的主创新必须从“无条件低频 ROM”转向可验证的失效感知、
  条件校正或其他经过公平控制的新机制。

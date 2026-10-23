# R33 冻结契约覆盖缺口与修订处理说明

本轮五份审稿报告全部完成；原规则仅判定 **2/5 份可用于契约综合**。必须保留 **ABORT / `[PANEL-SHRUNK: usable=2, panel_size=5]`**。`reviewer_full` 全轮**没有编辑裁决**。本文件记录并解释原事实，不修改原契约、旧报告、lint或人数规则。

## 1. 已独立核对的事实

原契约固定 `panel_size=5`；D1—D3为mandatory，D4为high，D5为normal。五份报告的必需章节、五个维度分数及四个本地触发结果齐全。本次直接从报告抽取分数，重算本地条件和可派生动作，并与原lint及其记录的源哈希逐项核对一致。

| 角色 | D1 | D2 | D3 | D4 | D5 | F1/F2/F3 | F0 | 局部动作记录 | 原lint可用 |
|---|---|---|---|---|---|---|---|---|---|
| 方法 | warn | pass | pass | pass | warn | false / false / false | false | 无可派生动作 | 否 |
| 领域 | warn | pass | pass | pass | warn | false / false / false | false | 无可派生动作 | 否 |
| 反方 | pass | pass | pass | warn | warn | false / false / false | true | 局部F0动作accept（仅记录原报告） | 是 |
| 主编角色 | pass | pass | pass | pass | warn | false / false / false | true | 局部F0动作accept（仅记录原报告） | 是 |
| 相邻视角 | warn | pass | pass | pass | warn | false / false / false | false | 无可派生动作 | 否 |

这里的EIC、DA局部accept只是复述其原报告；它们不能代表五人全轮结果。方法、领域、相邻视角报告如实保留了D1警告，没有伪造兜底动作，因此原lint均记录 `decision_not_derivable_from_fired_condition`。详见[原phase2_lint.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/phase2_lint.json:4>)及各报告的 `Editorial Decision`。

## 2. 为什么属于冻结契约覆盖缺口

对于三份 `D1=warn, D2=D3=D4=pass, D5=warn` 的分数：

- F1要求mandatory出现block，实际没有，故false。
- F2要求至少两个mandatory为warn或更差，实际只有D1一个；D5为normal不能补入计数，故false。
- F3要求high出现block，而D4=pass，故false。
- F0要求全部mandatory为pass，而D1=warn，故false。

原契约只有这四个动作入口，没有“单个mandatory警告且无block”的兜底分支。协议§8第3步要求从已经触发的条件中按severity选择动作；空触发集合无法产生动作。这是契约定义对合法分数组合的覆盖不足，不是审稿正文缺席，也不是已经证明的科学方法失效。三份报告均将缺口解释为可由现有资料补齐的披露/呈现问题，同时保留了具体修订项；不能由“无动作”倒推出方法正确性或错误性。

协议§5要求动作可由触发条件派生，§6要求五份有效输出齐备；因此原lint的2/5可用事实必然触发人数不变量失败。即使仅作诊断查看完整五个分数行，F0也只有2/5个本地真值，达不到all；F1/F2/F3也没有触发见证。此说明不是越过lint进行正式合议。协议中N=5的majority阈值为4；本案F2的本地见证数是0，任何阈值争论均不产生动作。

## 3. 原轮次保留边界

1. `full_v1` 的五份原报告、原契约及原lint保持字节不变；不缩成两人面板，不删掉三份真实报告，不调分、不改量词、不添加事后fallback。
2. 不因无多维mandatory警告便输出accept，也不把normal警告计入mandatory以制造major动作。
3. 不重新调用已见稿件的Phase2来获得所需裁决；本案没有multi-dissent例外依据。
4. 原全轮维持ABORT且无裁决。任何后续独立修订核验都使用新的核验记录，不能回填原全轮通过。

规则位置：[sprint_contract_protocol.md §3](<C:/Users/LazyM/.codex/skills/academic-paper-reviewer/references/sprint_contract_protocol.md:34>)（冻结与不可改字段）、[§5](<C:/Users/LazyM/.codex/skills/academic-paper-reviewer/references/sprint_contract_protocol.md:54>)（Phase2动作与不可重试）、[§6](<C:/Users/LazyM/.codex/skills/academic-paper-reviewer/references/sprint_contract_protocol.md:67>)（固定人数）、[§8](<C:/Users/LazyM/.codex/skills/academic-paper-reviewer/references/sprint_contract_protocol.md:85>)（量词和优先级）。

## 4. 为什么可以继续常规作者修订

用户已授权自动持续修订至完整初稿。五份报告包含可独立使用的真实作者反馈，即使其中三份不能进入冻结契约综合，也无需抹除其内容。依revision coach的逐项覆盖原则，将这些原问题整理成14项必修、11项建议，并保留每个原编号、原文、行号、源哈希和验收条件。这里的“必修”是作者处理审稿反馈的标记，不等于契约mandatory，也不构成编辑裁决。

本工作仅整理核验输入，未读取正在编辑的新稿，未把任何条目标为关闭，未改论文、结果或旧报告，未重训或commit。用户的持续执行授权覆盖了revision coach一般流程中的再次等待作者确认步骤，因此直接交付可审阅清单，不另行停止索取许可。

后续采用[re-review协议](<C:/Users/LazyM/.codex/skills/academic-paper-reviewer/references/re_review_mode_protocol.md:18>)的逐项追溯规则：作者答复、实际修改位置、独立核验三者必须对应。该协议末尾明确re-review尚无本版sprint contract模板并沿用既有行为，见[第109行起](<C:/Users/LazyM/.codex/skills/academic-paper-reviewer/references/re_review_mode_protocol.md:109>)。这是随后独立的修订核验，不是原五人契约综合的替代品。本说明不对修订后稿件预设通过或编辑结论。

## 5. 本次核对边界与输入身份

本次只读取五份Phase2、原contract、phase2_lint、metadata及指定revision coach/re-review/sprint协议。没有读取Phase1、论文新稿、原始训练数据或源码，因此本次独立确认限于报告内容与协议事实，不重做审稿人所述科学复算或Phase1触发词语义审计。原报告的正面证据、缺口与未验证边界均按其声明范围保留。

| 输入 | SHA256 |
|---|---|
| [contract.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/contract.json>) | `5c57f4b63df625c2b5ec47f9bb1b7bdff651fef89f3144b4d0ef37094971e406` |
| [phase2_lint.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/phase2_lint.json>) | `5b08f5eb8b890eea4cf0d19f2cfb7cd7735879e6745fc580fc03c0c6661c94cd` |
| [metadata.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/metadata.json>) | `8b469d4c7642c4af585a5792bf54fd00d35dafeec4a428fee1e2687ef23d81ff` |
| [method_phase2.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/method_phase2.md>) | `7456fa16569c64b41705607889f7a2aed2bde05a6c022f1f668428486fc1c000` |
| [domain_phase2.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/domain_phase2.md>) | `93dd5ed660068b6ab54d7c1e2a2043d2617052a04cc88fdd2a37829f79faa5ec` |
| [da_phase2.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/da_phase2.md>) | `7f2c13c9df54cc117b6afa5f3307f3e30bee1dc621bf78d5729b15fe120fa5a7` |
| [eic_phase2.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/eic_phase2.md>) | `fdf6d8bd2f9e27f3f22118ab2050eccbe60b1f15133c6b1300a758955fee6e0e` |
| [perspective_phase2.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/reviews/full_v1/perspective_phase2.md>) | `656afd5be44f0d80df53b3d70cd77a3bae7f5cd7be94a65016b56c1727980abf` |
| [sprint_contract_protocol.md](<C:/Users/LazyM/.codex/skills/academic-paper-reviewer/references/sprint_contract_protocol.md>) | `99784c42692ff6bb809b8c34c64038c493fe244c82bb9dd3f5699792e4e65d0d` |
| [re_review_mode_protocol.md](<C:/Users/LazyM/.codex/skills/academic-paper-reviewer/references/re_review_mode_protocol.md>) | `48e49d0d60ce3f1eeca81a642599d2b7960775188d3c0782592302532b09a4d3` |
| [revision_coach_agent.md](<C:/Users/LazyM/.codex/skills/academic-paper/agents/revision_coach_agent.md>) | `26ef672747cd0fb8e8de3565ec4dbb24c205cb76cbe833eb77dcdc37a6e3d5a2` |

机器可读核验输入见 [REVIEW_ITEMS.json](REVIEW_ITEMS.json)；作者执行路线见 [REVISION_ROADMAP_CN.md](REVISION_ROADMAP_CN.md)。

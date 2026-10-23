# 数值溯源补充的逐项响应

稿件：[delivery_candidate2.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/delivery_candidate2.md>), SHA256 `59d1db8fd5c8c468783e98ba6db1bcde0e49e7f923e82afa6e2d9e6dbf383cd4`。父候选SHA256 `aef0c10a1bf19e8703a8066e1f0aaef75600b886777424b9f6545677ccc77eb0`。

本次仅纳入真实完成且已冻结的206项体/迹和52项残差复算。没有新增训练、HPO或数值表；首轮最终完整性FAIL及原full_v1的ABORT、2/5可用、无全轮编辑裁决均保留。下列为作者修订回应，最终增量核验尚待独立判断。

## PROV-1

问题：当前表格数值缺少本轮可审计重算生产链。

答复：新增E18及附录D真实206项保存权重体/迹复算：两套设置、五时刻、4120比较和原容差；同时载入报告、逐值摘要和完整清单，不新增训练。

位置：

- [稿件第272行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/delivery_candidate2.md:272>)
- [稿件第523行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/delivery_candidate2.md:523>)
- [稿件第630行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/delivery_candidate2.md:630>)

状态：作者已补充，待独立最终增量核验。

## PROV-2

问题：已有独立点残差和实际退出/警告仍需执行证据。

答复：补入全部52条已有残差记录、416比较及270子进程和2父进程实际退出0、本次warning为0和stderr为空；只限本次，不追填旧日志。

位置：

- [稿件第632行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/delivery_candidate2.md:632>)

状态：作者已补充，待独立最终增量核验。

## PROV-3

问题：不能将复用实现误称独立PDE算法验证，不能补造E4缺失分支。

答复：明确前向与参考解复用冻结项目实现；新检查器独立重载、求积/残差与比较。保留20项E4仅体/迹范围，52残差排除这些模型，旧v不可重建。

位置：

- [稿件第634行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/delivery_candidate2.md:634>)
- [稿件第682行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/delivery_candidate2.md:682>)

状态：作者已补充，待独立最终增量核验。

## PROV-4

问题：旧“未重载”语句与新事实的时点冲突。

答复：§3.4、证据映射后与附录D/E仅增加明确阶段指代；旧先前复核事实、训练日志缺口及所有原科学表格、公式、结论保持。

位置：

- [稿件第517行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/delivery_candidate2.md:517>)
- [稿件第525行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/delivery_candidate2.md:525>)
- [稿件第622行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/delivery_candidate2.md:622>)
- [稿件第624行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/delivery_candidate2.md:624>)

状态：作者已补充，待独立最终增量核验。

## PROV-5

问题：补充数值执行不能由作者宣布完整性终审通过。

答复：首轮最终完整性FAIL与原full_v1 ABORT原件保留；本轮仅提供实际证据。候选稿2最终Mode1/完整性及排版结论由独立核验者另行给出，人类作者声明继续待确认。

位置：

- [稿件第692行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/delivery_candidate2.md:692>)
- [稿件第696行](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/delivery_candidate2.md:696>)

状态：作者已补充，待独立最终增量核验。

## 原25项普通修订的保留

已读原独立VERIFICATION_REPORT_CN.md：其Accept只绑定complete_revised1a及其对应范围，14项必修FULLY_ADDRESSED，11项建议均回应（7完整、1部分、3不采纳且理由可接受）。本次逐项为25条原验收位置建立新稿行位和SHA映射，科学答复及采纳处置不变；不把旧Accept转写为候选稿2完整性通过。详见prior_25_items_location_bridge.json。

候选稿2正文11510汉字，各章均在原±15%内，总数在11000±10%内。13条题录、18处外部引用上下文、8张主表、全部显示公式及4幅图保留；14个表块中仅证据映射表发生文字变化。

PREPARATION_206_CN.md保留准备时点的52项待证据状态；随后实际完成的52项及其正式哈希由本文件和E18更新，未覆盖准备记录。

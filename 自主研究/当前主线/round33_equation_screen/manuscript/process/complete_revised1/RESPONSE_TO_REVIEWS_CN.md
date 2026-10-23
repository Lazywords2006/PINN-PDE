# 首轮完整稿修订逐项答复

修订稿：[complete_revised1.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md>), SHA256 `5eb4cf00f663aa18face96dc503c7e3d35420e2d809489e0cad5f176f8bdd68a`。原完整稿SHA256 `8c5a83cff08732ce8e548cd873faa4e55cede075c3340fe9799e9deae37d4fd3`。

本响应逐项覆盖统一清单的14项必修和11项建议。作者已落实21项、部分采纳1项、未采纳3项可选桥接文献；全部25项均有答复。下述RESOLVED和DELIBERATE_LIMITATION仅为作者处置状态，全部独立核验仍为PENDING。原清单保持待核验，没有替复核者填FULLY_ADDRESSED。

原full_v1五份报告完成，但冻结契约全轮保持ABORT、2/5可用、无编辑裁决；两份局部accept不代表五人结论。本轮是常规作者修订，既不改旧评分与契约，也不回填原面板通过。说明见reviews/revision1/PROTOCOL_EXCEPTION_CN.md。

现稿状态为“五份独立自动审阅意见后的修订初稿，待修订核验与最终完整性检查，未投稿”。没有新增训练、模型加载、参考积分、图形重绘或git操作。

## M1：补全时间截断、残差点随机数及抽样顺序

来源：方法，必修。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

§2.3和附录A均补出t.clamp_min(1e-30)；§3.4列明default_rng(330500)及体x、体t、左端t、右端t、初值x的抽样顺序，数组8192/8192/1024/1024/1024，四残差分量8192/1024/1024/1024。说明两端时间独立，点集未用于训练或选择。只抄录现有实现，没有改代码或重训。

修订位置：

- [§2.3：截断与未截断解析式](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:173>)
- [§3.4：独立点抽样顺序与分量数](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:270>)
- [附录A：时间下界精确常数](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:543>)

证据：

- [stage5_support.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/stage5_support.py>): heldout_residuals附近的固定default_rng和抽样顺序；具体值同步保存于source_evidence.json.heldout
- [pinn1d.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/pinn1d.py>): layer_profile/flux_layer的1e-30截断；Model的E4分支与硬初值表达式
- [source_evidence.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/source_evidence.json>): 32份定向JSON核对：E4筛选8+完整12+PirateNet12，含原序列/最大值/中位数/来源SHA

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## M2：在表5附近定义两条参数轴

来源：方法，必修。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

在§3.1指出κ进入边界函数；表5注给出E1只改c且D=1、R=0、G(u)=0.3u和初值不变，E3为Gκ(u)=κ(u−1)、κ∈{0.1,1,3}，D=0.1、c=0.3、R=u(1−u)和初值不变。明确运行名k就是κ；保留表5全部结果，另给错配公式校验。

修订位置：

- [§3.1：参数轴进入边界函数的位置](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:223>)
- [表5注：两参数轴、固定量、运行标签与错配](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:354>)

证据：

- [problems.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/problems.py>): _e1/_e3及BulkSurface的参数、初值和边界函数定义
- [SCREEN_PROTOCOL.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/SCREEN_PROTOCOL.md>): 修订2第A组A-1/A-2；修订4第5项G2；后续修订保持原判定
- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## M3：消除附录A的N04悬空引用

来源：方法，必修。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

删除未定义的内部编号N04，直接引入调用与损失字段口径；保留完成循环后写入配置计数、末次记录损失不等于终点重评、实际L-BFGS状态计数的既有说明。全文检索确认无N04残留。

修订位置：

- [附录A：删除N04后的直接字段解释](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:550>)

证据：

- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## DR1：补足参数化边界、取值与固定条件

来源：领域，必修。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

在§3.1指出κ进入边界函数；表5注给出E1只改c且D=1、R=0、G(u)=0.3u和初值不变，E3为Gκ(u)=κ(u−1)、κ∈{0.1,1,3}，D=0.1、c=0.3、R=u(1−u)和初值不变。明确运行名k就是κ；保留表5全部结果，另给错配公式校验。

修订位置：

- [§3.1：参数轴进入边界函数的位置](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:223>)
- [表5注：两参数轴、固定量、运行标签与错配](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:354>)

证据：

- [problems.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/problems.py>): _e1/_e3及BulkSurface的参数、初值和边界函数定义
- [SCREEN_PROTOCOL.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/SCREEN_PROTOCOL.md>): 修订2第A组A-1/A-2；修订4第5项G2；后续修订保持原判定
- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## DR2：为E4负面结果补最小可复核科学定义

来源：领域，必修。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

新增附录E式E1—E4：体PDE、左右端条件、独立表面ODE、初值、D=0.1及κ=γ=V0=1、常通量层U与两分支表达式。明确v不等于u(1,t)，常通量辅助层不含表面反馈，与式12的动态层不同。表E1列完整12次运行的三种子体/迹指标；0.838按vanilla体中位数除以修正组体中位数，先每种子五时刻最大、再三种子中位数。保留20份表面权重缺失与追加探索性质，仅重聚合已有JSON，未补权重或表面定量证据。

修订位置：

- [§5.2：E4负面结果及附录入口](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:441>)
- [附录E：式E1—E4和实际配置](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:629>)
- [附录E：独立v、通量错配与层定义](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:645>)
- [附录E表E1：完整三种子体/迹表](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:664>)
- [表E1后：0.838的分子、分母与汇总次序](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:673>)
- [附录E：探索性质及20份表面权重缺失](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:675>)

证据：

- [problems.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/problems.py>): _e1/_e3及BulkSurface的参数、初值和边界函数定义
- [pinn1d.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/pinn1d.py>): layer_profile/flux_layer的1e-30截断；Model的E4分支与硬初值表达式
- [E4_PROTOCOL.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/E4_PROTOCOL.md>): 第2—5节、修订1及末尾纠正，原科学模型、追加探索与表面分支缺失
- [source_evidence.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/source_evidence.json>): 32份定向JSON核对：E4筛选8+完整12+PirateNet12，含原序列/最大值/中位数/来源SHA

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## DR3：解释N04、A-1、G2并精确化证据入口

来源：领域，必修。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

附录A直接说明字段并删除N04；§4.3与§4.6首次提及A-1和G2时给中文名称、比较对象及附录F定位。附录F详细列出两者的原门槛、对象和预算，保留联合不满足。E09改指附录E表E1与E4_PROTOCOL具体节，0.838可直接由表后分子/分母核查。

修订位置：

- [附录A：删除N04后的直接字段解释](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:550>)
- [§4.3：A-1首处名称与定位](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:335>)
- [§4.6：G2首处名称与定位](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:408>)
- [附录F：A-1对象与联合门槛](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:679>)
- [附录F：G2两项、两方程与原种子/预算](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:681>)
- [E09：科学附录、表E1和协议具体节](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:514>)
- [表E1后：0.838的分子、分母与汇总次序](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:673>)

证据：

- [SCREEN_PROTOCOL.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/SCREEN_PROTOCOL.md>): 修订2第A组A-1/A-2；修订4第5项G2；后续修订保持原判定
- [E4_PROTOCOL.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/E4_PROTOCOL.md>): 第2—5节、修订1及末尾纠正，原科学模型、追加探索与表面分支缺失
- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## DA-m1：补参数轴与E4方程及替换层项

来源：反方，必修。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

表5注补全Gκ与固定量；新增附录E给E4体方程、初值、交换边界、独立v方程及实际U层和硬初值分支。式E3是常通量辅助层，文字明确其不含表面反馈，未称为式12原样推广。§5.2定量结论指向表E1，旧负面结果保留；未新增训练。

修订位置：

- [表5注：两参数轴、固定量、运行标签与错配](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:354>)
- [§5.2：E4负面结果及附录入口](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:441>)
- [附录E：式E1—E4和实际配置](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:629>)
- [附录E：独立v、通量错配与层定义](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:645>)
- [附录E表E1：完整三种子体/迹表](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:664>)

证据：

- [problems.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/problems.py>): _e1/_e3及BulkSurface的参数、初值和边界函数定义
- [pinn1d.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/pinn1d.py>): layer_profile/flux_layer的1e-30截断；Model的E4分支与硬初值表达式
- [E4_PROTOCOL.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/E4_PROTOCOL.md>): 第2—5节、修订1及末尾纠正，原科学模型、追加探索与表面分支缺失
- [source_evidence.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/source_evidence.json>): 32份定向JSON核对：E4筛选8+完整12+PirateNet12，含原序列/最大值/中位数/来源SHA

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## DA-m2：在表4逐种子披露PirateNet执行来源

来源：反方，必修。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

表4旁逐种子说明：E1两方法seed0/1从历史检查点在本机续完，seed2与E3全部为历史云端结果。同种子来源类别对应，但混合来源的三种子中位数不是统一环境随机重复分布估计。表4全部数值、22.61/5.52及逐种子比较均原样保留；没有删种子或认定已证明不公平配对。

修订位置：

- [表4注：逐种子来源及中位数范围](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:333>)
- [§4.3：保留22.61与5.52的描述性比值](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:322>)

证据：

- [source_evidence.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/source_evidence.json>): 32份定向JSON核对：E4筛选8+完整12+PirateNet12，含原序列/最大值/中位数/来源SHA
- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## DA-m3：区分解析连续延拓与截断实现的极限

来源：反方，必修。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

在命题1中明确讨论未截断的解析表达式；§2.3和附录A列精确下界。附录A解释t<1e-30时通过开方变量的时间依赖被固定，外部衰减与背景项仍有导数，不能用该分支的AD极限验证解析迭代极限。原浮点初值误差边界保留，不声称逐位零。

修订位置：

- [§2.3：命题1的解析对象](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:185>)
- [§2.3：截断与未截断解析式](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:173>)
- [附录A：时间下界精确常数](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:543>)
- [附录A：截断分支自动微分不验证解析极限](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:552>)

证据：

- [pinn1d.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/pinn1d.py>): layer_profile/flux_layer的1e-30截断；Model的E4分支与硬初值表达式
- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## EIC-M1：清理内部引用并完整解释既有判据

来源：主编角色，必修。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

删除N04并直接列字段说明。A-1首次出现处给跨架构强基线名称与附录F入口；G2首次出现处说明主候选对强基线和SOAP内叠加两个目标。附录F列两个方程、种子100/101、4000+500预算、三倍和2/2绝对阈值，明确G2未满足指两方程两项的联合条件，不是四个子判断全失败；完整SOAP对照不追改旧判定。

修订位置：

- [附录A：删除N04后的直接字段解释](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:550>)
- [§4.3：A-1首处名称与定位](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:335>)
- [§4.6：G2首处名称与定位](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:408>)
- [附录F：A-1对象与联合门槛](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:679>)
- [附录F：G2两项、两方程与原种子/预算](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:681>)

证据：

- [SCREEN_PROTOCOL.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/SCREEN_PROTOCOL.md>): 修订2第A组A-1/A-2；修订4第5项G2；后续修订保持原判定
- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## EIC-M2：给出Gκ定义并解释k运行标签

来源：主编角色，必修。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

在§3.1指出κ进入边界函数；表5注给出E1只改c且D=1、R=0、G(u)=0.3u和初值不变，E3为Gκ(u)=κ(u−1)、κ∈{0.1,1,3}，D=0.1、c=0.3、R=u(1−u)和初值不变。明确运行名k就是κ；保留表5全部结果，另给错配公式校验。

修订位置：

- [§3.1：参数轴进入边界函数的位置](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:223>)
- [表5注：两参数轴、固定量、运行标签与错配](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:354>)

证据：

- [problems.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/problems.py>): _e1/_e3及BulkSurface的参数、初值和边界函数定义
- [SCREEN_PROTOCOL.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/SCREEN_PROTOCOL.md>): 修订2第A组A-1/A-2；修订4第5项G2；后续修订保持原判定
- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## R3-1：使参数轴和时间求值规则可从稿件恢复

来源：相邻视角，必修。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

表5注完整列κ边界函数、三个取值、固定D/c/反应/初值及k标签；§2.3、命题1与附录A给1e-30下界及未截断解析连续延拓的范围。读者可从稿件恢复参数轴和实际求值规则，不需根据δ或文件名猜测。

修订位置：

- [表5注：两参数轴、固定量、运行标签与错配](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:354>)
- [§2.3：截断与未截断解析式](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:173>)
- [§2.3：命题1的解析对象](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:185>)
- [附录A：时间下界精确常数](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:543>)
- [附录A：截断分支自动微分不验证解析极限](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:552>)

证据：

- [problems.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/problems.py>): _e1/_e3及BulkSurface的参数、初值和边界函数定义
- [pinn1d.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/pinn1d.py>): layer_profile/flux_layer的1e-30截断；Model的E4分支与硬初值表达式
- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## R3-2：让E4比较对象和机制变化可直接核查

来源：相邻视角，必修。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

新增附录E式E1—E4：体PDE、左右端条件、独立表面ODE、初值、D=0.1及κ=γ=V0=1、常通量层U与两分支表达式。明确v不等于u(1,t)，常通量辅助层不含表面反馈，与式12的动态层不同。表E1列完整12次运行的三种子体/迹指标；0.838按vanilla体中位数除以修正组体中位数，先每种子五时刻最大、再三种子中位数。保留20份表面权重缺失与追加探索性质，仅重聚合已有JSON，未补权重或表面定量证据。

修订位置：

- [§5.2：E4负面结果及附录入口](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:441>)
- [附录E：式E1—E4和实际配置](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:629>)
- [附录E：独立v、通量错配与层定义](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:645>)
- [附录E表E1：完整三种子体/迹表](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:664>)
- [表E1后：0.838的分子、分母与汇总次序](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:673>)
- [附录E：探索性质及20份表面权重缺失](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:675>)

证据：

- [problems.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/problems.py>): _e1/_e3及BulkSurface的参数、初值和边界函数定义
- [pinn1d.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/pinn1d.py>): layer_profile/flux_layer的1e-30截断；Model的E4分支与硬初值表达式
- [E4_PROTOCOL.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/E4_PROTOCOL.md>): 第2—5节、修订1及末尾纠正，原科学模型、追加探索与表面分支缺失
- [source_evidence.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/source_evidence.json>): 32份定向JSON核对：E4筛选8+完整12+PirateNet12，含原序列/最大值/中位数/来源SHA

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## R3-3：整理工程过程并给分节配额可核对依据

来源：相邻视角，必修。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

§3.4与§4.7缩短具体恢复过程，历史130+24+22来源、原21/后9和四层计时边界集中到附录D。主文保留预算、环境混杂及解释所必需的区别。核验附件给原PAPER_CONFIGURATION的六章基数、逐章实际值、±15%和总11000±10%，并复现审阅中的不同计数口径；没有修改目标、旧报告或用附录补正文配额。

修订位置：

- [§3.4：来源核验与历史链范围](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:272>)
- [§4.7：预算与四层成本的科学解释](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:410>)
- [附录D：集中的历史来源、恢复与计时](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:619>)
- [附录D：成本定义与不支持等时间排名](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:627>)
- [原配置、六章目标、实际计数及五种计数口径](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/COUNT_DEFINITION_COMPARISON_CN.md>)

证据：

- [PAPER_CONFIGURATION.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/PAPER_CONFIGURATION.json>): 事前六章目标1800/2200/2000/2500/1700/800，总量与分节容差不变
- [word_counts.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/word_counts.json>): 原配置口径六章逐项及总量结果
- [count_definition_comparison.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/count_definition_comparison.json>): 各审阅计数的算法重现及逐行分类
- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## M-建议1：给E4负面结果最短方程与配置入口

来源：方法，建议。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

采纳为一个短科学附录：E4的方程、独立v、实际参数、常通量层与配置入口均在附录E；§5.2和E09可直接定位表E1与0.838计算。与DR2共用内容，未另增实验门槛。

修订位置：

- [§5.2：E4负面结果及附录入口](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:441>)
- [附录E：式E1—E4和实际配置](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:629>)
- [附录E表E1：完整三种子体/迹表](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:664>)
- [E09：科学附录、表E1和协议具体节](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:514>)

证据：

- [E4_PROTOCOL.md](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/E4_PROTOCOL.md>): 第2—5节、修订1及末尾纠正，原科学模型、追加探索与表面分支缺失
- [problems.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/problems.py>): _e1/_e3及BulkSurface的参数、初值和边界函数定义
- [source_evidence.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/source_evidence.json>): 32份定向JSON核对：E4筛选8+完整12+PirateNet12，含原序列/最大值/中位数/来源SHA

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## M-建议2：合并重复的工程与解释边界

来源：方法，建议。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

压缩§3.4、§4.7、§4.3和τ讨论的重复过程表述，将完整历史执行与恢复范围集中到附录D，附录A仅保留入口。仍在图注、相应比较和局限段保留直接影响解释的环境混杂、非置信区间和负面结果；这些位置各约束不同主张，不合并删除。

修订位置：

- [§3.4：来源核验与历史链范围](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:272>)
- [§4.7：预算与四层成本的科学解释](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:410>)
- [附录D：集中的历史来源、恢复与计时](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:619>)
- [§5.3：跨路线与跨档混杂边界](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:453>)

证据：

- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号
- [figure_retention_checks.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/figure_retention_checks.json>): 四个PNG与既有冻结哈希一致

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## DR-建议1：用错配公式核对参数轴数值

来源：领域，建议。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

采纳δ=(0.02+κ)/0.3+0.02并放在表5注；本轮数值核对得到κ=0.1/1/3时δ=0.42/3.42/10.0866666667，与表5显示值一致。只核算现有定义，不据该式建立收益对错配的单调性。

修订位置：

- [表5注：两参数轴、固定量、运行标签与错配](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:354>)

证据：

- [problems.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/problems.py>): _e1/_e3及BulkSurface的参数、初值和边界函数定义
- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## EIC-建议1：集中重复的工程来源说明

来源：主编角色，建议。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

压缩§3.4、§4.7、§4.3和τ讨论的重复过程表述，将完整历史执行与恢复范围集中到附录D，附录A仅保留入口。仍在图注、相应比较和局限段保留直接影响解释的环境混杂、非置信区间和负面结果；这些位置各约束不同主张，不合并删除。

修订位置：

- [§3.4：来源核验与历史链范围](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:272>)
- [§4.7：预算与四层成本的科学解释](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:410>)
- [附录D：集中的历史来源、恢复与计时](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:619>)
- [§5.3：跨路线与跨档混杂边界](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:453>)

证据：

- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号
- [figure_retention_checks.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/figure_retention_checks.json>): 四个PNG与既有冻结哈希一致

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## EIC-建议2：在附录A列时间截断常数

来源：主编角色，建议。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

附录A实现表新增“层函数的时间截断”一行，给出rt=torch.sqrt(t.clamp_min(1e-30))并说明两类层的使用范围；表后区分截断AD与未截断解析极限。

修订位置：

- [附录A：时间下界精确常数](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:543>)
- [附录A：截断分支自动微分不验证解析极限](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:552>)

证据：

- [pinn1d.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/pinn1d.py>): layer_profile/flux_layer的1e-30截断；Model的E4分支与硬初值表达式
- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## R3-建议1：说明可靠初值导数与边界参数的输入条件

来源：相邻视角，建议。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

§5.4补出可靠f′(1)、f″(1)及算子参数的输入条件；说明只测试解析初值，带噪观测与离散插值造成的导数估计误差对δ的影响尚未验证。未添加带噪实验或把此条件写成新的已验证结论。

修订位置：

- [§5.4：输入可靠性及目标量限制](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:457>)

证据：

- [problems.py](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/problems.py>): _e1/_e3及BulkSurface的参数、初值和边界函数定义
- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## R3-建议2：说明按使用目的选择误差目标量

来源：相邻视角，建议。作者处置：采纳；状态：RESOLVED（独立核验PENDING）。

同一新增段说明应用应先确定目标量；本研究的体相对误差和独立迹误差不能代表边界储存、交换通量等全部物理量的精度次序。保留原主指标，不将现有排序外推到未计算目标量。

修订位置：

- [§5.4：输入可靠性及目标量限制](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:457>)

证据：

- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## R3-建议3：把资源披露整理为紧凑环境和预算表

来源：相邻视角，建议。作者处置：部分采纳；状态：DELIBERATE_LIMITATION（独立核验PENDING）。

部分采纳：预算已有附录A紧凑表，本轮把历史来源、恢复和四层成本集中到附录D，并在表4直接补逐种子来源；完整CSV保存逐运行环境与调用。暂不另加一个跨来源环境总表，避免重复既有预算表，并保留“历史检查点本机续完”等无法用单一批次标签概括的信息。精度和成本混杂仍在§5.3明确，未主张等时间收益或固定额外开销。

修订位置：

- [附录A：紧凑预算与采样表](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:534>)
- [表4注：逐种子来源及中位数范围](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:333>)
- [附录D：含环境、实际调用的完整数据表入口](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:623>)
- [附录D：成本定义与不支持等时间排名](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:627>)
- [§5.3：跨路线与跨档混杂边界](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:453>)

证据：

- [source_evidence.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/source_evidence.json>): 32份定向JSON核对：E4筛选8+完整12+PirateNet12，含原序列/最大值/中位数/来源SHA
- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号

未采纳部分与理由：不另新增重复的总表；已有紧凑预算表、具名补充入口与逐记录来源比单一环境标签更精确。该项原验收允许以现有披露和具体理由回应。

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## R3-建议4：可选连接解析富集与单位分解有限元

来源：相邻视角，建议。作者处置：不采纳；状态：DELIBERATE_LIMITATION（独立核验PENDING）。

本轮不加入可选的Melenk与Babuška文献。现有§1已将经典局部层和解析富集工具与本工作的具体构造分开，命题1与经验结论的范围也已明确。新增单位分解有限元桥接会扩展相关工作分支而不补当前必修披露缺口；没有阅读新来源后再借其理论作PINN保证的必要。保留现有13条已核对题录。

修订位置：

- [§1：已有解析工具与本工作范围](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:37>)
- [§2.3：命题1的解析对象](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:185>)

证据：

- [citation_contexts.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/citation_contexts.json>): 13题录与18处外部上下文保持；现有阅读范围与限制保留
- [PAPER_CONFIGURATION.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/PAPER_CONFIGURATION.json>): 事前六章目标1800/2200/2000/2500/1700/800，总量与分节容差不变

未采纳部分与理由：与本轮局部修订及当前有限主张的直接关系较弱；不新增未核对的文献，不声称其具体内容支持本文。

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## R3-建议5：可选用计算核验框架组织证据层次

来源：相邻视角，建议。作者处置：不采纳；状态：DELIBERATE_LIMITATION（独立核验PENDING）。

本轮不新增Oberkampf与Trucano文献。§3.4、§5.1和附录D已分别限定数值复算、机制解释及历史执行范围，且本文不包含物理观测验证；本轮采用这些具体边界而不扩展为一个新的验证框架综述。没有据此省略已有独立点/参考解检查，也未提出新物理实验要求。

修订位置：

- [§3.4：来源核验与历史链范围](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:272>)
- [§5.1：机制解释边界](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:431>)
- [附录D：集中的历史来源、恢复与计时](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:619>)

证据：

- [citation_contexts.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/citation_contexts.json>): 13题录与18处外部上下文保持；现有阅读范围与限制保留
- [change_map.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/change_map.json>): 逐修改前后原文、原行号与新行号

未采纳部分与理由：原建议为可选概念组织；现有具名证据分层足以回应意图，添加新框架需额外原文核查且不改变当前结论。

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## R3-建议6：可选引用后续参数研究设计视角

来源：相邻视角，建议。作者处置：不采纳；状态：DELIBERATE_LIMITATION（独立核验PENDING）。

本轮不新增Morris文献。§4.5与§5.3已限制三档、三种子及跨环境解释；§5.4把同环境、独立种子和可分离因素设计列为下一步。当前实验没有开展Morris敏感性分析，不借可选引文把三档描述性结果升级为该分析。

修订位置：

- [§5.3：跨路线与跨档混杂边界](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:453>)
- [§5.4：未来同环境、独立种子研究范围](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/drafts/complete_revised1.md:459>)

证据：

- [citation_contexts.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/complete_revised1/citation_contexts.json>): 13题录与18处外部上下文保持；现有阅读范围与限制保留
- [PAPER_CONFIGURATION.json](<E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/PAPER_CONFIGURATION.json>): 事前六章目标1800/2200/2000/2500/1700/800，总量与分节容差不变

未采纳部分与理由：后续研究设计尚未展开；保留具体未来方向，不为本轮有限参数结果增加方法名称或未经核对的新文献。

原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。

## 保留的未验证范围与后续核验

修订核验须亲自检查上述25项对应位置；最终HTML/PDF、版面和全稿完整性由独立流程随后核查。署名、单位、基金、利益冲突、贡献与人类作者最终核验仍待作者确认。

科学边界保留：五个正时刻不能证明早期角点机制；三种子、筛选后选择与环境差异不支持总体成功概率或纯优化器/τ因果排名；历史生产日志不完整，E4表面权重缺失；原A-1/G2不满足、弱错配退化、新初值不利种子及E4对vanilla无额外收益均未删除。

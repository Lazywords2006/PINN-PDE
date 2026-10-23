"""按已核实的首轮审稿意见另存修订稿；只编辑本轮稿件和本轮过程目录。"""
from pathlib import Path
from statistics import median
from datetime import datetime, timezone, timedelta
import difflib
import hashlib
import json
import re

OUT=Path(__file__).resolve().parent
MAN=OUT.parents[1]
ROOT=MAN.parent
BASE=MAN/'drafts/complete_v1.md'
DRAFT=MAN/'drafts/complete_revised1.md'
BASE_SHA='8c5a83cff08732ce8e548cd873faa4e55cede075c3340fe9799e9deae37d4fd3'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
readj=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
assert not (OUT/'FROZEN_REVISION_MANIFEST.json').exists(), '本轮已冻结；请新建下一修订版本。'
def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert sha(BASE)==BASE_SHA
protected=readj(OUT/'protected_before.json')
assert all(sha(Path(p))==digest for p,digest in protected.items())
if DRAFT.exists():
    assert sha(DRAFT)==readj(OUT/'revision_state.json')['draft_sha256'],'外部修订已变化，停止覆盖。'
evidence=readj(OUT/'source_evidence.json')
assert evidence['base_sha256']==BASE_SHA
base=BASE.read_text(encoding='utf-8'); t=base
changes=[]
def replace(key,old,new):
    global t
    assert t.count(old)==1,(key,t.count(old))
    t=t.replace(old,new)
    changes.append({'key':key,'old':old,'new':new})

replace('status',
    '> 写作状态：完整中文论文初稿v1，纳入已完成并复算验收的全部第二阶段30项结果。当前为作者自核后交付独立完整性与同行视角审查的版本，尚未完成该轮审查或投稿。文中的E编号指向文末数据证据映射，不属于外部文献编号。署名、单位、基金、利益冲突及人类作者最终核验待作者确认。',
    '> 写作状态：五份独立自动审阅意见后的修订初稿，待修订核验与最终完整性检查，未投稿。已完成并复算验收的第二阶段30项结果保持原样。文中的E编号指向文末数据证据映射，不属于外部文献编号。署名、单位、基金、利益冲突及人类作者最终核验待作者确认。')
replace('clamp_and_analytic_limit',
    '该改写避免显式形成较大的正指数，与式（8）的数学表达保持一致，但不自动消除闭式中小时间差值的相消。初始值由连续延拓定义，实际实现则在开方前对时间作极小正数截断。浮点初值误差需要检验，不能把解析等于零解释为任意机器上的逐位零。代码层面的稳定求值和数学边界定义共同决定可复现实现。[E02]',
    '该改写避免显式形成较大的正指数，与式（8）等价，但不自动消除小时间差值的相消。解析初值通过连续延拓定义；代码则以`t.clamp_min(1e-30)`替代开方中的时间，并用该截断值计算层形。命题1针对未经截断的解析表达式，不能用截断分支的自动微分极限验证。浮点初值误差仍须检验，解析零不意味着逐位零；实现与极限的区别见附录A。[E02,E17]')
replace('proposition_scope',
    '**命题1（初值与初始导数迭代极限）。** 在上述假设下，式（12）通过连续延拓满足初值，并且',
    '**命题1（初值与初始导数迭代极限）。** 在上述假设下，式（12）的未截断解析表达式通过连续延拓满足初值，并且')
replace('axis_intro',
    '参数轴另改变热方程的边界容量和反应扩散问题的储库强度，其余条件保持各自基准设置。[E01]',
    '参数轴另改变热方程容量c和反应扩散边界函数Gκ(u)=κ(u−1)中的κ，具体取值与固定条件见表5注。[E01,E17]')
replace('heldout_sampling',
    '独立残差检验使用固定随机数种子生成新的体点、两端边界点和初值点，数量分别为8192、1024及1024。时间在10⁻⁴至1之间均匀取样，分别报告体方程、左端、右端动态边界和初值残差的均方根及最大绝对值。检验点不参与训练或配置选择，各分量也没有统一量纲归一化，因此不将它们相加为一个新的方法排名。解误差与残差指标需要并列解释。[E01,E03]',
    '独立残差点由NumPy `default_rng(330500)`按体x、体t、左端t、右端t、初值x依次抽样，数组长度为8192、8192、1024、1024、1024；x在[0,1]、t在[10⁻⁴,1]均匀分布，两端时间独立。体、左端、右端和初值各有8192、1024、1024、1024个检验点，分别报告均方根与最大绝对值。点集不参与训练或配置选择，分量未统一量纲，不能相加用于排名，须与解误差并列解释。[E01,E03,E17]')
replace('pirate_source_note',
    '| E3_fisher | hardic | 5.73940e-04 | 3.41486e-04 | 6.40310e-04 | 5.73940e-04 | 3.44877e-04 | 3/3 |\n\n跨架构强基线比较仍存在不同结论。',
    '| E3_fisher | hardic | 5.73940e-04 | 3.41486e-04 | 6.40310e-04 | 5.73940e-04 | 3.44877e-04 | 3/3 |\n\n表4注：E1两方法的seed 0、1从历史检查点在本机续完；seed 2及E3全部保留历史云端结果。同种子的来源类别对应，但三种子中位数混合执行来源，不是统一环境随机重复的分布估计；记录映射见E17。\n\n跨架构强基线比较仍存在不同结论。')
replace('a1_first_definition',
    '因此，原要求两个问题都至少达到三倍的强基线判据仍未满足。',
    '因此，原跨架构强基线判据A-1要求两个问题均至少达到三倍，仍未满足（完整定义见附录F）。')
replace('axis_note',
    '| E3_k3 | 10.086667 | 3.85368e-03 | 7.69199e-04 | 5.01000 | 3/3 | 满足 |\n\n弱储库强度点的比值',
    '| E3_k3 | 10.086667 | 3.85368e-03 | 7.69199e-04 | 5.01000 | 3/3 | 满足 |\n\n表5注：E1仅改变c∈{0.03,0.1,0.3,1,3}，D=1、R=0、G(u)=0.3u及原初值不变；E3令Gκ(u)=κ(u−1)，κ∈{0.1,1,3}，D=0.1、c=0.3、R(u)=u(1−u)及原初值不变，运行名中的k即κ。由式（3）得E3的δ=(0.02+κ)/0.3+0.02，其余训练条件沿用基准。[E01,E17]\n\n弱储库强度点的比值')
replace('g2_first_definition',
    '小预算G2与本节完整预算使用不同投入规模和种子，回答的实验问题不同。完整S6-SOAP满足条件不会追改G2失败，也不会改变此前跨架构强基线A-1未满足的结论。本文保留默认Adam主路线及两类结果，避免用后得到的正面叠加结果替换原比较。所有新增任务的损失、独立残差及实际调用在附录D所列数据表中完整提供。[E01,E03,E04,E13]',
    '小预算效果判据G2对E1/E3分别检查默认Adam修正组对强基线的优势，以及SOAP内的叠加性；种子100、101及两项门槛见附录F。本节S6-SOAP不会追改G2失败，也不改变第4.3节A-1未满足的结论。主路线仍为默认Adam，全部新增损失、残差及调用记录见附录D。[E01,E03,E04,E13]')
replace('compact_pirate_scope',
    '两个问题均满足原架构叠加判据。该证据说明在本文的具体架构实现和默认训练设置中，解析层项的收益能够保留，不表明所有残差网络或初始化方式均会获得同样结果。[E03,E05]',
    '两个问题均满足原架构叠加判据，收益限于该变体和默认训练设置，不能外推到所有残差网络或初始化方式。[E03,E05]')
replace('compact_tau_limit',
    '本机两档与历史主档的执行环境和软件存在差异，表6不能隔离纯τ效应。即使本机两档共享执行环境，三种子和三个指定取值仍不足以建立连续参数区间内的误差保证。该补证据说明修正并非只在唯一已报告档位产生较小主误差，所支持的范围限于这些配置和保存指标。主参数继续由事前协议决定，未开展超参数搜索。[E04,E13]',
    '本机两档与历史主档的环境及软件不同，表6不能隔离纯τ效应。三种子和三个取值也不能保证连续参数区间内的误差。较小主误差仅在这些配置和保存指标上得到报告；主参数继续由事前协议决定，未开展超参数搜索。[E04,E13]')
replace('e4_result_location',
    '完整预算下，修正相对硬初值及残差注意力的比较满足探索条件，但相对普通网络的中位数比约0.838，未显示额外收益。',
    '附录E给出最短模型及表E1的完整三种子结果。完整预算下，修正对硬初值和残差注意力满足探索条件，但普通网络与修正组的体误差中位数之比约0.838，未显示额外收益。')
replace('n04_remove','调用与损失字段按N04解释：','调用与损失字段口径如下：')
replace('concentrate_recovery_body',
    '工程恢复分别保留原21与后9的源码来源，全部任务各一次attempt、退出码零；恢复和计时范围见附录D。',
    '工程恢复与历史执行范围集中列于附录D。')
replace('concentrate_recovery_cost',
    '原21项由监督器观察退出后补记attempt时间，含轮询延迟，孤儿执行区间不计入runner会话。四种口径分别保存，不能相互填补或当作跨环境速度倍数。[E13,E15]',
    '四种口径分别保存，定义及恢复造成的计时边界见附录D，不能相互填补或当作跨环境速度倍数。[E13,E15]')
history_scope='历史复算来源分别为130项既有模型审查、24项小预算模型复核及22项第一阶段新增模型复核，包含原设置和加密设置的体、迹误差记录。独立补查对398个结果与权重文件核对当前哈希，而未重新运行176个模型。部分历史生产进程的逐次退出码和完整警告信息未留存，两个已保存测试日志分别记录63项与71项测试通过、各有1条张量转标量的测试断言警告，不能改称全历史零警告。旧130项的训练源码哈希与当前源码不同，也不能倒称全部历史运行均由当前代码完成。E4中20项历史模型缺少表面权重，仍只支持体与迹。上述范围和逐结果映射见E12所指补充审查。[E12]'
replace('concentrate_historical_scope',history_scope,'历史执行、权重缺失与日志范围统一见附录D。[E12]')
replace('historical_scope_appendix_d',
    '## 附录D 完整新增数据、恢复与成本口径（不计正文字数）\n\n',
    '## 附录D 完整新增数据、恢复与成本口径（不计正文字数）\n\n'+history_scope+'\n\n')
replace('input_and_target_limits',
    '### 5.4 进一步工作的具体方向\n\n',
    '### 5.4 进一步工作的具体方向\n\n构造需要可靠的f′(1)、f″(1)及算子参数。本文仅测解析初值，未验证带噪观测或离散插值的导数估计误差如何影响δ。迁移时还应先确定目标量；本文的体相对误差及独立迹误差，不代表边界储存、交换通量等所有量的精度次序。[E01,E02]\n\n')
replace('clamp_appendix_row',
    '| 衰减时间τ | 主参数0.1；修订6另外预定0.03、0.3，主参数旧结果只读复用 | 第4.5节报告全部档位，不据结果选择τ；超参数搜索次数为0 |',
    '| 衰减时间τ | 主参数0.1；修订6另外预定0.03、0.3，主参数旧结果只读复用 | 第4.5节报告全部档位，不据结果选择τ；超参数搜索次数为0 |\n| 层函数的时间截断 | `rt=torch.sqrt(t.clamp_min(1e-30))`；动态边界层和E4通量层均使用该下界 | 仅为实际浮点评估定义，不替代命题1的未截断解析极限；开方以下时间分支固定在截断值 |')
replace('clamp_appendix_explanation',
    '对RBA的每一残差分量q及其固定点i，本地实现为',
    '时间截断须与解析延拓区分：当0≤t<10⁻³⁰时，`layer_profile`通过开方变量的时间依赖被固定；式（12）的外部衰减和背景项仍有各自导数。因此，在该分支上对代码作自动微分并令t趋零，不能验证命题1的未截断导数迭代极限。本文保留已有浮点初值误差检验，不声称t=0逐位精确或实现极限与理想极限完全相同。[E02,E17]\n\n对RBA的每一残差分量q及其固定点i，本地实现为')

e4final=[g for g in evidence['e4_groups'] if g['tag']=='e4confirm']
table_e4='\n'.join(['| 方法 | seed 0 | seed 1 | seed 2 | 体误差中位数 | 迹误差中位数 | 体≤0.01 |',
    '|---|---:|---:|---:|---:|---:|---:|']+[
    '| '+' | '.join([('RBA本地变体' if g['method']=='rba' else g['method']),*[f'{v:.5e}' for v in g['max_vol']],
        f"{g['vol_median']:.5e}",f"{g['trace_median']:.5e}",f"{g['under_1e2']}/3"])+' |' for g in e4final])
vm=next(g['vol_median'] for g in e4final if g['method']=='vanilla')
lm=next(g['vol_median'] for g in e4final if g['method']=='hardic+layer')
appendices=r'''## 附录E 体表耦合扩展的模型与完整预算数据（不计正文字数）

E4取0≤x≤1、0≤t≤1，体解u与独立表面变量v满足

\[
u_t=Du_{xx}+u(1-u),\qquad u_x(0,t)=0,
\qquad D u_x(1,t)=\kappa\{v(t)-u(1,t)\},
\tag{E1}
\]

\[
v'(t)=\kappa\{u(1,t)-v(t)\}-\gamma v(t)^3,
\qquad u(x,0)=0.1(1-x^2),\quad v(0)=V_0.
\tag{E2}
\]

实际参数为D=0.1、κ=γ=V₀=1。v(t)是另一个未知量，并不等于体解的边界迹u(1,t)。令y=1−x，则初始通量错配为Δᵧ=κ[f(1)−V₀]+Df′(1)=−1.02；它与正文的时间导数错配δ是不同量。所用常通量辅助层为

\[
U(y,t)=-2\Delta_y\sqrt{t/D}\,\operatorname{ierfc}
\!\left(\frac{y}{2\sqrt{Dt}}\right),
\quad \operatorname{ierfc}(z)=\frac{e^{-z^2}}{\sqrt\pi}-z\operatorname{erfc}(z).
\tag{E3}
\]

它满足辅助热方程Uₜ=DUᵧᵧ、常通量DUᵧ(0,t)=Δᵧ，并在t=0按连续延拓取零。与式（12）的动态边界层不同，这一辅助问题不含表面反馈；乘衰减后也不强制满足完整交换条件或表面ODE。该扩展的硬初值修正表达式为

\[
u_\theta=f(x)+tN_\theta(x,t)+e^{-t/0.1}U(1-x,t),
\qquad v_\phi=V_0+tN_\phi(t).
\tag{E4}
\]

体分支采用4×64 tanh MLP，表面分支为3×32 tanh MLP。vanilla与RBA使用两个直接输出分支并施加软初值；hardic使用式（E4）去掉U项。训练还约束体PDE、左端Neumann、右端通量交换和表面ODE残差。参数、初值、通量层和分支定义可在E4_PROTOCOL第2—4节及当前源码对应函数中相互核对；历史运行身份另由原JSON和既有复算记录限定，不能仅由当前源码倒推全历史执行。[E09,E17]

表E1　E4完整预算探索性结果，tag为e4confirm，seed 0、1、2。每个种子先对五个规定时刻取最大体相对误差，再取三种子中位数；迹列对应u(1,t)，不对应v(t)。

{{TABLE_E4}}

表E1第一行vanilla的体误差中位数为{{VM}}，末行hardic+layer为{{LM}}；分子取前者、分母取后者，比值为{{RATIO}}，按三位小数报告为0.838。该数只比较描述性体误差中位数，不表示逐种子比值中位数或统计等价。四方法的完整12份原JSON路径、逐时刻体/迹序列及SHA256见本轮E17的`source_evidence.json`中`e4_groups`和`targeted_raw_records`。[E09,E17]

小预算筛选未满足原三倍条件；完整预算是在已见筛选失败后按E4_PROTOCOL修订1追加的探索，不追改原判定。完整预算修正组对hardic/RBA较好者满足探索条件，但表E1的vanilla比值低于一，限制其额外收益主张。20份历史E4权重均缺表面分支；表E1仅列已有体与迹证据，本轮只读重聚合JSON，没有重载模型，也未将旧v(t)数字补成可复现表面结果。早时间的实际解渐近结构及余项正则性仍未由这些五时刻误差证明。[E09,E12,E17]

## 附录F 历史判据的定义与定位（不计正文字数）

跨架构强基线判据A-1见SCREEN_PROTOCOL修订2第A组：对E1和E3分别以MLP的hardic+layer为候选，以{hardic+因果ε=1、hardic+因果ε=10、PirateNet+hardic}中体误差中位数最低者为基线，要求两个方程的“基线中位数/候选中位数”均至少为3。第4.3节给出约12.51和1.47，故联合条件未满足。同一PirateNet变体内部的A-2则要求两个方程的hardic/修正组中位数比均至少为3；它与跨架构A-1是不同判断。[E01,E03]

小预算效果判据G2见SCREEN_PROTOCOL修订4第5项，使用E1/E3及种子100、101，两种训练路线均为4000次第一阶段调用加名义上限500的L-BFGS。第一项固定主候选为Adam+hardic+layer，要求其两种子主误差中位数至少比{Adam+vanilla、Adam+hardic、SOAP64+vanilla、SOAP64+hardic}中最好者低3倍，并且两个候选种子均≤10⁻²。第二项另比较SOAP64+hardic+layer与SOAP64+hardic，要求三倍中位数比及两个修正种子均≤10⁻²。两项均按E1和E3分别判断，只有两方程两项全部满足才达到原升级条件；“G2未满足”指该联合条件未成立，不表示四个子判断全部失败。第4.6节的完整预算S6-SOAP使用不同种子和投入，不能追改G2，也不能据其倒选主优化器。[E01,E03,E04]

'''
appendices=appendices.replace('{{TABLE_E4}}',table_e4).replace('{{VM}}',f'{vm:.8e}').replace('{{LM}}',f'{lm:.8e}').replace('{{RATIO}}',f"{evidence['e4_vanilla_over_corrected_median_ratio']:.12f}")
replace('e4_and_criterion_appendices','## 声明（不计正文字数）',appendices+'## 声明（不计正文字数）')
replace('e09_mapping',
    '| E09 | 体表耦合扩展及权重限制 | `../../E4_PROTOCOL.md` 末尾纠正与 `runs/e4confirm` 原始JSON | 体与迹可复核；表面变量定量证据不纳入 |',
    '| E09 | 体表耦合扩展及权重限制 | 附录E表E1；`../../E4_PROTOCOL.md` 第2—5节、修订1及末尾纠正；`../../runs/e4confirm` 原始JSON | 体与迹可复核；表面变量定量证据不纳入 |')
replace('e14_mapping',
    '| E14 | 本完整稿数字与引用自核 | `../process/complete_v1/numeric_checks.json`、`citation_contexts.json`、`source_checks.json`、`word_counts.json` | 作者有限自核，不能作为独立审查通过声明 |',
    '| E14 | 完整v1数字与引用核查及本轮编辑核对 | `../process/complete_v1/numeric_checks.json`；`../process/complete_revised1/revision_checks.json`、`citation_contexts.json`、`word_counts.json` | 沿用有效数据核查；本轮编辑自核不代替独立审查 |')
replace('e17_mapping',
    '| E16 | 原/新初值全部报告种子的历史图v2 | `../figures/history_v2/historical_comparison.png`、对应PDF/CSV/evidence及独立图表核查 | 36个真实记录、12组比较；分别训练、不同批次、非未知初值泛化 |',
    '| E16 | 原/新初值全部报告种子的历史图v2 | `../figures/history_v2/historical_comparison.png`、对应PDF/CSV/evidence及独立图表核查 | 36个真实记录、12组比较；分别训练、不同批次、非未知初值泛化 |\n| E17 | 首轮修订的参数、采样、E4数据和PirateNet来源 | `../process/complete_revised1/source_evidence.json`及逐项响应 | 定向核对32份已有JSON及相关源码/协议；不重训、不补造历史表面分支 |')
t=t.replace('`../process/complete_v1/citation_contexts.md`','`../process/complete_revised1/citation_contexts.md`')

def tables(text):
    out=[];buf=[]
    for line in text.splitlines()+['']:
        if line.startswith('|'):buf.append(line)
        elif buf:out.append('\n'.join(buf));buf=[]
    return out
main_old=base.split('## 3 实验设计与复现方法',1)[1].split('## 5 讨论与局限',1)[0]
assert len(tables(main_old))==8
assert all(block in t for block in tables(main_old))
assert re.findall(r'^\[\d+\].+$',t,re.M)==re.findall(r'^\[\d+\].+$',base,re.M)
assert re.findall(r'!\[[^\]]*\]\(([^)]+)\)',t)==re.findall(r'!\[[^\]]*\]\(([^)]+)\)',base)
assert 'N04' not in t and 'MATERIAL GAP' not in t
assert t.count('\\[')==t.count('\\]')
for tab in tables(t):
    assert len({line.count('|') for line in tab.splitlines()})==1
    assert re.fullmatch(r'[| :\-]+',tab.splitlines()[1])
DRAFT.write_text(t,encoding='utf-8')
digest=sha(DRAFT)
for change in changes:
    assert change['new'] in t
    change['new_line']=t[:t.index(change['new'])].count('\n')+1
    change['old_line']=base[:base.index(change['old'])].count('\n')+1 if change['old'] in base else None
save('change_map.json',{'base_sha256':BASE_SHA,'draft_sha256':digest,'changes':changes})
(OUT/'complete_v1_to_revised1.diff').write_text(''.join(difflib.unified_diff(base.splitlines(keepends=True),t.splitlines(keepends=True),fromfile='drafts/complete_v1.md',tofile='drafts/complete_revised1.md')),encoding='utf-8')
config=readj(MAN/'PAPER_CONFIGURATION.json'); counts={}
for title,target in config['section_targets'].items():
    block=t.split('## '+title+'\n',1)[1].split('\n## ',1)[0]
    block=re.sub(r'\\\[.*?\\\]','',block,flags=re.S)
    block=re.sub(r'<!--.*?-->','',block,flags=re.S)
    lines=[line for line in block.splitlines() if not line.startswith(('|','图','!['))]
    actual=len(re.findall(r'[\u4e00-\u9fff]',title+'\n'+'\n'.join(lines)))
    counts[title]={'target_cjk':target,'actual_cjk':actual,'deviation_percent':round(100*(actual/target-1),2),'within_15_percent':abs(actual/target-1)<=.15}
total=sum(r['actual_cjk'] for r in counts.values())
save('word_counts.json',{'base_sha256':BASE_SHA,'draft_sha256':digest,'definition':config['count_definition'],
    'implementation_notes':'完全沿用完整v1口径：含章/节标题、表题及表注；排除表格行、图题、图片路径、显示公式。',
    'actual_body_cjk':total,'target_body_cjk':11000,'deviation_percent':round(100*(total/11000-1),2),
    'within_10_percent':abs(total/11000-1)<=.1,'sections':counts})
read_reviews={}
for role in ('method','domain','da','eic','perspective'):
    p=MAN/'reviews/full_v1'/f'{role}_phase2.md'
    read_reviews[str(p)]=sha(p)
save('revision_checks.json',{'base_sha256':BASE_SHA,'draft_sha256':digest,'eight_main_tables_unchanged':True,
    'thirteen_references_unchanged':True,'four_figures_paths_unchanged':True,'all_markdown_tables':len(tables(t)),
    'display_math_delimiters_paired':True,'n04_internal_label_removed':True,'e4_table_from_original_json':True,
    'original_defaults_unchanged':{'tau':.1,'first_optimizer':'Adam','hpo_runs':0},
    'reviews_read':read_reviews,'remaining_review':None,'final_frozen':False,
    'original_protected_files_unchanged':len(protected),'operations':{'training':0,'model_load':0,'reference_integration':0,'git_mutation':0,'render':0}})
assert all(sha(Path(p))==v for p,v in protected.items())
save('revision_state.json',{'draft_sha256':digest,'generated_local':datetime.now(timezone(timedelta(hours=8))).isoformat(),
    'body_cjk':total,'read_reviewers':5,'pending_reviewers':[],'final_frozen':False})
print(json.dumps({'draft_sha256':digest,'body_cjk':total,'sections':counts,'changes':len(changes),'all_markdown_tables':len(tables(t)),
    'final_frozen':False,'remaining_review':None},ensure_ascii=False,indent=2))

"""从冻结工作稿生成完整v1及作者证据；仅聚合保存结果，不训练或重载模型。"""
from pathlib import Path
from collections import Counter, defaultdict
from statistics import median
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import json
import math
import re
import sys

OUT=Path(__file__).resolve().parent
MAN=OUT.parents[1]
ROOT=MAN.parent
BASE=MAN/'drafts/working_revised1.md'
DRAFT=MAN/'drafts/complete_v1.md'
ANALYSIS=ROOT/'validation/stage6_analysis_20261022/complete_v1'
FIGURES=ANALYSIS
BASE_SHA='7ca430d7911dda4507469099e493dc2563ef48dff0157b4df862e4ab8f3b3635'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def readj(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def save(name,obj):
    assert (OUT/name).parent==OUT
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def same(a,b): return abs(a-b)<=1e-13*max(1.,abs(a),abs(b))
assert sha(BASE)==BASE_SHA
if DRAFT.exists():
    assert (OUT/'draft_state.json').exists()
    assert sha(DRAFT)==readj(OUT/'draft_state.json')['draft_sha256'],'外部稿件已变化，停止覆盖。'
before_path=OUT/'protected_before.json'
if not before_path.exists():
    protected=[BASE,MAN/'drafts/initial_working.md',MAN/'PAPER_CONFIGURATION.json',MAN/'OUTLINE_AND_EVIDENCE.md']
    protected += [p for p in (MAN/'process').rglob('*') if p.is_file() and OUT not in p.parents]
    protected += [p for p in (MAN/'research').rglob('*') if p.is_file()]
    save('protected_before.json',{str(p):sha(p) for p in protected})
before=readj(before_path)
assert all(sha(Path(p))==v for p,v in before.items())
a=readj(ANALYSIS/'analysis_evidence.json')
assert a['analysis_state']=='complete' and a['new_task_count']==30
assert a['default_comparison_records']==36 and a['tau_records']==18 and len(a['records'])==48
assert a['evidence']['old398_unchanged'] is True and len(a['evidence']['raw_sha256'])==488
assert all(sha(ANALYSIS/name)==digest for name,digest in a['output_sha256'].items())
assert all(sha(Path(name))==digest for name,digest in a['evidence']['input_sha256'].items())
assert all(sha(ROOT/name)==digest for name,digest in a['evidence']['source_hashes'].items())
state=a['evidence']['runtime_status']
assert state['phase']=='completed' and len(state['tasks'])==30
assert all(r['state']=='completed' and r['pid'] is None and len(r['attempts'])==1 and r['attempts'][0]['exit_code']==0 and r['validation']['complete_and_recomputed'] is True for r in state['tasks'])
assert [len(r['jobs']) for r in state['source_lineage']]==[21,9]

# 独立读取206份原JSON；不打开任何PT/checkpoint，不运行神经网络或ODE。
old_manifest=readj(MAN/'process/writer_data_evidence.json')['manifest']
old_paths={row['source'] for row in old_manifest}
assert len(old_paths)==176
paths=old_paths|{r['source'] for r in a['records']}
assert len(paths)==206
raw_records={}
for name in sorted(paths):
    path=ROOT/name
    assert sha(path)==a['evidence']['raw_sha256'][name],name
    raw=readj(path)
    assert all(math.isfinite(v) for key in ('vol','trace') for v in raw['metrics'][key])
    raw_records[name]=raw
for row in a['records']:
    raw=raw_records[row['source']]
    assert raw['metrics']==row['metrics']
    assert max(raw['metrics']['vol'])==row['max_vol']
    assert max(raw['metrics']['trace'])==row['max_trace']
    assert raw['config']==row['config']

def group_rows(g,subset):
    rows=sorted([r for r in subset if r['tag']==g['tag'] and r['eq']==g['eq'] and r['method']==g['method']],key=lambda r:r['seed'])
    assert [r['seed'] for r in rows]==[0,1,2]
    vols=[max(raw_records[r['source']]['metrics']['vol']) for r in rows]
    traces=[max(raw_records[r['source']]['metrics']['trace']) for r in rows]
    assert vols==g['seeds'] and traces==g['trace_seeds']
    assert median(vols)==g['median'] and min(vols)==g['min'] and max(vols)==g['max']
    assert median(traces)==g['trace_median']
    assert sum(v<=.01 for v in vols)==g['under_1e2']
    return rows
group_checks=[]
for kind in ('default_groups','tau_groups'):
    for g in a[kind]:
        rows=group_rows(g,a['records'])
        group_checks.append({'kind':kind,'group':g,'sources':[r['source'] for r in rows],'independent_raw_json_aggregation_matches':True})
soap=[]
for eq in ('E1_heat','E3_fisher'):
    gs={g['method']:g for g in a['default_groups'] if g['tag']=='final_soap64_v1' and g['eq']==eq}
    ratio=gs['hardic']['median']/gs['hardic+layer']['median']
    declared=next(x for x in a['S6_SOAP']['per_equation'] if x['eq']==eq)
    assert ratio==declared['hardic_over_layer'] and declared['passed'] is True
    paired=[h/l for h,l in zip(gs['hardic']['seeds'],gs['hardic+layer']['seeds'])]
    assert all(v>1 for v in paired)
    taugs=[g for g in a['tau_groups'] if g['eq']==eq]
    tauratio=max(g['median'] for g in taugs)/min(g['median'] for g in taugs)
    assert tauratio==next(x['across_tau_max_over_min_median'] for x in a['tau_summary'] if x['eq']==eq)
    soap.append({'eq':eq,'hardic_over_layer':ratio,'paired_hardic_over_layer':paired,'tau_max_over_min':tauratio})
assert a['S6_SOAP']['joint_passed'] is True
newrows=[r for r in a['records'] if r['tag']!='confirm']
calls_range={key:[min(r['calls'][key] for r in newrows),max(r['calls'][key] for r in newrows)] for key in ('lbfgs_n_iter','lbfgs_func_evals')}
costs=a['costs']
assert same(sum(t['attempts'][0]['wall_seconds'] for t in state['tasks']),costs['local_attempt_wall_seconds_sum'])

t=BASE.read_text(encoding='utf-8')
def replace(old,new):
    global t
    assert t.count(old)==1,(old[:100],t.count(old))
    t=t.replace(old,new)
def replace_section(start,end,new):
    global t
    assert t.count(start)==t.count(end)==1
    left=t.index(start); right=t.index(end,left)
    t=t[:left]+new.rstrip()+'\n\n'+t[right:]

replace('作者：待作者填写。单位：待作者填写。','作者：待作者确认。单位：待作者确认。')
start=t.index('> 写作状态：'); stop=t.index('\n\n## 中文摘要',start)
t=t[:start]+'> 写作状态：完整中文论文初稿v1，纳入已完成并复算验收的全部第二阶段30项结果。当前为作者自核后交付独立完整性与同行视角审查的版本，尚未完成该轮审查或投稿。文中的E编号指向文末数据证据映射，不属于外部文献编号。署名、单位、基金、利益冲突及人类作者最终核验待作者确认。'+t[stop:]
replace_section('## 中文摘要（工作版）','关键词：', '''## 中文摘要

初值与动态边界要求的初始时间导数不一致，使一维抛物问题的角点分析区别于仅约束初始函数值的处理。本文由初值和方程算子计算导数错配，在硬初值表达式中加入半直线热方程动态边界层及固定指数衰减因子。Laplace变换与直接微分说明层函数的初始值、局部方程及边界性质，并区分局部模型的精确性与完整有限区间问题的训练余项。两类一维问题采用三个随机种子，以五个预定时刻的最大体相对误差为主指标。在默认Adam加L-BFGS路线下，原初值上硬初值与修正组的误差中位数比分别为34.83和5.92，两个事前固定新初值分别训练后的比值为2.69和7.34。PirateNet本地变体内的比值为22.61和5.52。同批固定SOAP64加L-BFGS对照中，比值为300.07和30.83，两方程修正组均有三个种子达到既定绝对误差阈值，满足该批叠加判据。三个衰减档位的中位数最大最小比为1.72和1.43，主参数保持0.1。研究同时保留个别种子退化、弱错配点及体表耦合扩展的负面结果。数据支持被测配置内的经验改善和有限叠加性，未证明初始角点机制的唯一性、普遍优化器优势或任意初值泛化。历史与新增批次的环境差异也限制跨组精度和成本的因果解释。

''')
replace_section('## English Abstract (working version)','## 1 引言与相关工作', '''## English Abstract

A mismatch between the initial time derivatives required by a parabolic equation and its dynamic boundary condition motivates a targeted correction to hard-initial-condition physics-informed neural networks. For one-dimensional problems, the mismatch is computed from the prescribed initial profile and differential operators. A half-line heat-equation layer with a dynamic boundary condition is added to the hard-initial-condition representation with a fixed exponential decay factor. A Laplace-transform construction and direct differentiation distinguish the exact local layer problem from the residual terms of the full finite-interval problem. Experiments use three seeds and the maximum relative volume error over five prescribed times. Under the default Adam plus L-BFGS route, the ratios of the median errors of the hard-initial-condition baseline to the corrected method are 34.83 and 5.92 for the original profiles, and 2.69 and 7.34 for two prespecified alternative profiles trained separately. Within the local PirateNet variant, the ratios are 22.61 and 5.52. Within the same local batch using fixed SOAP64 plus L-BFGS, the ratios are 300.07 and 30.83; all three corrected runs satisfy the absolute-error threshold for both equations, meeting the preregistered stacking criterion. Across three decay settings, the ratios of the largest to the smallest median errors are 1.72 and 1.43, while the main decay parameter remains 0.1. An adverse seed, a weak-mismatch setting, and a bulk-surface extension delimit the observed benefits. These results support empirical improvement and limited stacking within the tested configurations. They do not establish a unique corner mechanism, universal optimizer superiority, or generalization to arbitrary initial conditions. Environmental differences between historical and new batches also limit causal interpretations of cross-group accuracy and cost.

Keywords: physics-informed neural networks; dynamic boundary conditions; initial compatibility; corner layer; analytic correction

''')
replace('架构叠加使用 PirateNet 变体，优化器叠加及衰减参数敏感性仍待本稿后续补齐。[E01,E03,E04]','架构叠加使用 PirateNet 变体，优化器叠加与衰减参数敏感性则使用修订6全部三十项完整结果；主配置和判断规则均保持事前定义。[E01,E03,E04,E13]')
replace('考察其在五个固定观测时刻的解误差和架构叠加性','考察其在五个固定观测时刻的解误差及所用架构与优化器内的叠加性')
replace('完整预算先进行20000次 Adam 梯度调用','默认完整预算先进行20000次 Adam 梯度调用')
replace('SOAP 首次调用仅初始化状态，故20000次梯度调用对应19999次参数更新，不额外补偿调用。此设计只支持固定实现的比较，不代表优化器家族的全局排名。[E04]',
    'SOAP 首次调用仅初始化，20000次调用对应的19999次更新由冻结实现推得，不额外补偿。调用字段由完成循环后的配置值写入，并非独立逐步观测；损失和L-BFGS计数口径见附录A。两类实验均已完成，不进行超参数搜索或结果倒选。[E04,E13]')
replace('产物核验保留原始结果、权重和配置的对应关系。第一阶段新增二十二个任务已通过重新加载、身份检查以及误差复算。本文对176份结果记录再次只读聚合，文件哈希与既有快照一致，所记录的最大误差均能由逐时刻序列重建。历史体表耦合结果缺失表面网络权重，故其表面变量不纳入正式可复现定量证据。全部176项分别有130＋24＋22份保存模型复算记录，独立补查绑定398个结果与权重文件。该补查核对已有记录及当前哈希，没有重新加载全部模型；历史日志范围见附录A。保存完整产物能够检验已报告结果的一致性，但不扩大方法的适用范围。[E03,E05,E09,E12]',
    '产物核验保留结果、权重与配置的对应关系。历史176项已有130＋24＋22份保存模型复算记录，绑定398文件，部分原始生产日志仍不完备。第二阶段三十项全部通过完整产物、预算、参考加密及残差复算，新增90文件，共206份独立运行记录。本文只读重聚合全部结果JSON，未重复模型加载。工程恢复分别保留原21与后9的源码来源，全部任务各一次attempt、退出码零；恢复和计时范围见附录D。E4缺少历史表面网络权重，表面变量不作为可重建定量证据。当前数值一致性与全历史生产链完整性据此分别判断。[E03,E05,E09,E12,E13,E15]')

history_caption=(MAN/'figures/history_v2/historical_comparison_caption.md').read_text(encoding='utf-8').strip()
history_figure=f'![原初值与固定新初值的全部报告种子]({(MAN/"figures/history_v2/historical_comparison.png").as_posix()})\n\n图2　'+history_caption.removeprefix('图：')+'[E16]\n\n'
replace('### 4.3 PirateNet 变体内的架构叠加',history_figure+'### 4.3 PirateNet 变体内的架构叠加')
def md_table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,row))+' |' for row in rows])
fmt=lambda x:f'{x:.5e}'
tau_table=md_table(['问题','τ','执行环境','seed 0','seed 1','seed 2','体误差中位数','最小–最大','中位数/τ=0.1'],[
    [g['eq'],f"{g['tau']:g}",'历史云端' if g['tag']=='confirm' else '本机',*map(fmt,g['seeds']),fmt(g['median']),fmt(g['min'])+'–'+fmt(g['max']),f"{g['median_over_tau01']:.5f}"] for g in a['tau_groups']])
default_table=md_table(['问题','第一阶段优化器/环境','方法','seed 0','seed 1','seed 2','体误差中位数','迹误差中位数','体≤0.01'],[
    [g['eq'],'Adam/历史云端' if g['tag']=='confirm' else 'SOAP64/本机',g['method'],*map(fmt,g['seeds']),fmt(g['median']),fmt(g['trace_median']),f"{g['under_1e2']}/3"] for g in a['default_groups']])
replace_section('### 4.5 衰减参数灵敏度','### 4.7 独立残差与计算成本',f'''### 4.5 衰减参数灵敏度

表6报告预先固定的三个衰减档位。新增两档共十二次训练全部完成，主档复用既有六次结果。热方程三档体误差中位数依次为1.37334×10⁻³、1.18038×10⁻³和8.00404×10⁻⁴，反应扩散问题为4.85645×10⁻⁴、3.91498×10⁻⁴和3.39548×10⁻⁴。相对于主档，两端档位的中位数比在热方程上为1.16347与0.67809，在反应扩散问题上为1.24048与0.86730。跨档最大最小中位数比分别为1.71581和1.43027，描述的是这三个指定档位间的变化幅度。[E04,E13]

表6　衰减参数灵敏度的全部种子。数值按式（16）计算，主τ=0.1保持不变。[E13]

{tau_table}

三档的修正组均有三个种子达到主误差不超过百分之一，但种子波动与档间变化不应混为一谈。热方程τ为0.03时，种子一的误差为4.51090×10⁻³，高于同档另两个保存值，反映同档不同种子的差异。图3呈现全部种子及范围，避免较低中位数遮蔽个别运行的表现。跨档比未被赋予新的稳健性通过线，也未用于把主τ改为中位数最低的0.3。[E13]

![三个预定衰减档位的全部种子]({(FIGURES/'tau_sensitivity.png').as_posix()})

图3　三个预定τ档位的五时刻最大体相对误差。点表示真实报告种子，短横线为三种子中位数，竖线为最小–最大范围，不是置信区间。τ=0.1来自历史云端，0.03与0.3来自本机，两种来源的环境差异与参数变化并存。蓝色参考线为0.01，不是新增稳健性或发表标准。[E13]

本机两档与历史主档的执行环境和软件存在差异，表6不能隔离纯τ效应。即使本机两档共享执行环境，三种子和三个指定取值仍不足以建立连续参数区间内的误差保证。该补证据说明修正并非只在唯一已报告档位产生较小主误差，所支持的范围限于这些配置和保存指标。主参数继续由事前协议决定，未开展超参数搜索。[E04,E13]

### 4.6 固定SOAP64对照

表7给出两条训练路线的六臂默认配置，均在第一阶段后使用L-BFGS。同批本机SOAP64内，热方程硬初值及修正组中位数分别为4.43049×10⁻²与1.47648×10⁻⁴，比值300.07；反应扩散问题分别为2.49476×10⁻³与8.09251×10⁻⁵，比值30.83。两方程修正组均为三个种子的主误差不超过百分之一，且六个配对种子均改善，因此满足事前S6-SOAP的联合叠加条件。该条件要求两个方程均达到三倍中位数比、修正组至少两个种子达到绝对阈值，其用途不延伸为发表门槛。[E04,E13]

表7　默认六臂对照的全部种子。各路线第二阶段均为L-BFGS；Adam与SOAP64之间存在执行环境差异，跨路线精度并列不构成优化器因果排名。[E13]

{default_table}

![默认六臂完整种子比较]({(FIGURES/'default_six_arms.png').as_posix()})

图4　默认Adam加L-BFGS与固定SOAP64加L-BFGS的全部种子。点、中位数和最小–最大范围分别显示，均不表示置信区间。历史云端Adam与本机SOAP64分组标示；S6-SOAP只在同批本机SOAP64内比较hardic与hardic+layer，不能把跨环境差异全部归因于优化器。[E13]

中位数比需要结合逐种子值理解。SOAP64热方程修正组种子一仍为2.97685×10⁻³，高于该组另两个约10⁻⁴量级的保存值；相应组级比值不表示每个种子都改善三百倍。普通SOAP64网络在热方程上仅一个种子达到绝对阈值，反应扩散问题则没有达到。加入修正后的结果显示特定表达式与固定优化路线能够共同发挥作用，尚不能分离其各自对训练路径的因果贡献。[E13]

小预算G2与本节完整预算使用不同投入规模和种子，回答的实验问题不同。完整S6-SOAP满足条件不会追改G2失败，也不会改变此前跨架构强基线A-1未满足的结论。本文保留默认Adam主路线及两类结果，避免用后得到的正面叠加结果替换原比较。所有新增任务的损失、独立残差及实际调用在附录D所列数据表中完整提供。[E01,E03,E04,E13]

''')
replace('表6　新初值独立检验点','表8　新初值独立检验点')
replace('## 5 讨论与局限',f'''第二阶段三十项的L-BFGS内部迭代范围为{calls_range['lbfgs_n_iter'][0]}至{calls_range['lbfgs_n_iter'][1]}，闭包调用为{calls_range['lbfgs_func_evals'][0]}至{calls_range['lbfgs_func_evals'][1]}。整批历时22891.57秒，runner会话累计9286.10秒，全部attempt墙钟之和372236.02秒，记录内轨迹耗时之和371817.95秒。原21项由监督器观察退出后补记attempt时间，含轮询延迟，孤儿执行区间不计入runner会话。四种口径分别保存，不能相互填补或当作跨环境速度倍数。[E13,E15]

## 5 讨论与局限''')
replace('历史Adam确认与本机SOAP64的执行环境及软件版本不同，因此六臂跨组精度差也不能单独归因于优化器，不能称为同环境的优化器公平排名。修订6的主要叠加判据只比较同批本机SOAP64内的硬初值与硬初值加层，回答该固定实现中的叠加性。名义预算一致与执行环境不同需要同时披露。[E03,E04]',
    '历史Adam确认与本机SOAP64的环境及软件版本不同，六臂跨组精度差不能单独归因于优化器，成本也不能作等墙钟比较。τ主档为历史云端、另两档为本机，同样混合参数与环境变化。S6-SOAP已满足的判据只比较同批本机SOAP64内的硬初值与修正组；它支持该固定实现中的叠加性，未隔离不同优化器的总体贡献。图2上下排的新旧初值还分别训练于不同环境，跨排变化不能归于初值这一单一因素。[E03,E04,E13,E16]')
replace('当前最直接的补证据是完成已登记的衰减参数灵敏度及固定 SOAP64 比较，以判断固定主配置附近的变化和另一优化更新规则下的叠加性。若出现不利结果，应据此收窄论点，而不删去档位或追加种子追逐正面中位数。完成之后仍需保留该研究的一维范围、有限方程数量及初值分别重训的条件。更高维问题只有在相应边界几何、局部层构造和参考解都得到独立验证后，才适合形成新的结论。[E04]',
    '已完成的灵敏度和固定SOAP64对照补足了两个预先安排的经验问题，也留下了新的可检验边界。后续同环境复现实验可把τ和优化器的变化与硬件、软件差异分开，按事前规则增加独立种子，估计收益分布而非继续比较最小误差。更高维推广则需要匹配边界几何的局部层、完整参考解及相应误差评估。当前一维结果尚不足以决定这些设置中的构造形式或预期改善幅度。[E04,E13]')
replace_section('## 6 结论','## 参考文献','''## 6 结论

本文围绕一维动态边界抛物问题的初始相容性，构造了硬初值与局部角点层相结合的神经网络表达式。导数错配由已知初值、体算子和边界算子计算，半直线层的变换表达式、局部方程及边界性质通过直接推导核查。修正项在初始时刻连续为零，使试函数严格保留给定初值，同时允许不同趋近路径具有相应的导数极限。衰减、反应项及有限区间另一端仍留下需要训练的余项，所以解析保证只对应明确写出的局部性质和初值约束。[E02]

默认Adam加L-BFGS路线在两个原初值及两个事前固定新初值上，修正组的三种子体误差中位数均低于相应硬初值基线。PirateNet本地变体内的比较保留了组级改善，完整SOAP64对照则在两个方程上均满足既定叠加判据。这些结果把证据从一种默认表达式扩展到所测架构和优化路线，但仍限于各自固定实现。新初值任务分别重训，不能解释为一个训练后的网络对未知初值直接泛化。[E03,E05,E13]

三个预定衰减档位均保存全部种子，跨档最大最小中位数比为1.72和1.43。其意义是描述有限取值上的误差变化，而不是确定最优衰减常数。主τ保持0.1，默认训练路线保持Adam加L-BFGS，没有根据补充结果倒选参数或优化器。历史云端与本机的差异限制跨档及跨优化器精度的因果归因，也限制成本排名，较小的中位数本身不能消除这些混杂。[E04,E13]

负面结果规定了经验结论的边界。新初值有个别种子退化，弱错配参数点的修正中位数较差，跨架构强基线A-1及小预算G2仍未满足，体表耦合扩展相对普通网络也无额外收益。该扩展缺失历史表面权重的问题另行保留，不以随机重建分支替代原产物。这些限制使本文的结论指向局部构造在特定配置中的适用性，而非所有种子、所有方程或所有优化器上的保证。[E03,E05,E09,E12]

完整产物与来源链使上述比较可以逐项检查，但工程恢复、数值复算和机制解释仍有不同职责。独立残差不总与解误差同序，五个正时刻的结果也不证明趋近初始角点的唯一因果机制。下一步应优先验证更早时间的参考精度，并设计同环境、独立种子和可分离动力学影响的对照，再讨论更广的边界结构。本文由此提供一个可计算、可复核且适用范围明确的修正方案及其经验依据。[E02,E03,E13,E15]

''')
replace('`../process/working_revised1/citation_contexts.md`','`../process/complete_v1/citation_contexts.md`')
t=t.replace('（工作稿附件，不计正文字数）','（不计正文字数）')
replace('| E04 | 灵敏度和固定SOAP64计划 | `../../SCREEN_PROTOCOL.md` 修订6 | 事前规则，不能作为结果证据 |','| E04 | 灵敏度和固定SOAP64事前计划 | `../../SCREEN_PROTOCOL.md` 修订6 | 事前规则，结果另由E13支持 |')
replace('原始训练结果仍位于研究根目录的 `runs`，本工作稿只读使用。每个表格单元可通过对应分组的 `sources` 回指到原始JSON；逐文件SHA256及取最大值检查保存在独立映射文件。内部重聚合没有替代原始模型加载验证，也没有重新训练。',
    '''| E13 | 第二阶段全部30项正式结果、τ及六臂对照、残差和成本 | `../../validation/stage6_analysis_20261022/complete_v1/analysis_evidence.json`及三个CSV、报告和PNG/PDF | 正式分析绑定旧398与新90文件；本作者另核206份JSON及新增汇总，不重新加载模型 |
| E14 | 本完整稿数字与引用自核 | `../process/complete_v1/numeric_checks.json`、`citation_contexts.json`、`source_checks.json`、`word_counts.json` | 作者有限自核，不能作为独立审查通过声明 |
| E15 | 30/30完成及恢复来源链 | `../../validation/stage6_20261022/completion_archive_20261023/`、`../process/reproducibility_recovery_20261023/` | 全部30项退出与复算完成；原21及后9保留不同编排源码来源，科学训练源未改 |
| E16 | 原/新初值全部报告种子的历史图v2 | `../figures/history_v2/historical_comparison.png`、对应PDF/CSV/evidence及独立图表核查 | 36个真实记录、12组比较；分别训练、不同批次、非未知初值泛化 |

原始训练结果仍位于研究根目录的`runs`，本稿只读使用。新旧表格单元可以回指到相应原始JSON，数字映射保存在E14。全部206份JSON的当前哈希与正式清单匹配；本次重聚合不等同于重跑全部模型。既有数学和文献核验、历史工作稿及两版复现时点材料保留原件，完成稿另存。''')
replace('完整预算、筛选预算和待纳入结果的修订6计划分别列明。','完整预算、筛选预算和已完成的修订6实验分别列明。')
replace('| 衰减时间τ | 主参数0.1；修订6另外预定0.03、0.3，主参数旧结果只读复用 | 此表是计划与配置披露，灵敏度完整结果仍待第4.5节 |',
    '| 衰减时间τ | 主参数0.1；修订6另外预定0.03、0.3，主参数旧结果只读复用 | 第4.5节报告全部档位，不据结果选择τ；超参数搜索次数为0 |')
replace("| 参考时间积分 | scipy `solve_ivp(method='Radau', rtol=1e-12, atol=1e-13, dense_output=True)` | `problems.py`；空间Chebyshev，左端Neumann消元、右端动态ODE |",
    "| 参考时间积分 | E1–E3：scipy `solve_ivp(method='Radau', rtol=1e-12, atol=1e-13, dense_output=True)`；E4的体表参考解atol=1e-14 | `problems.py`；E1–E3的一维参考解采用空间Chebyshev、左端Neumann消元、右端动态ODE，不能将该atol统一外推到E4 |")
replace('| 修订6 SOAP64计划 | `soap_official64`；betas=(0.95,0.95)，shampoo_beta=0.95，预条件频率10，weight_decay=0；学习率0.001至0.00001 | 20000次梯度调用、首次仅初始化即19999次参数更新；完整18次结果仍待第4.6节 |',
    '| 修订6 SOAP64实现 | `soap_official64`；betas=(0.95,0.95)，shampoo_beta=0.95，预条件频率10，weight_decay=0；学习率0.001至0.00001 | 完整18次结果见第4.6节；20000次调用含首次仅初始化，19999次更新由冻结实现语义推得 |')
replace('对RBA的每一残差分量q及其固定点i，本地实现为',
    '调用与损失字段按N04解释：`history.adam_gradient_calls=cfg.adam_steps`在第一阶段成功完成后写入，依赖冻结循环与完成证据，不是独立逐步计数器。`final_adam_loss`沿用历史字段名，表示“Adam/SOAP末次记录损失”，在零基step19990（筛选为3990）参数更新前计算、当步更新后记录，不是训练终点重评。`lbfgs_n_iter`与`lbfgs_func_evals`取自优化器保存状态；外部名义预算3000可能在内部迭代少于3000时耗尽，两种计数不可混用。[E13,E14]\n\n对RBA的每一残差分量q及其固定点i，本地实现为')
replace('λ₀=0；正文另说明首步采用η的选择','λ₀=0；正文另有在k=1令注意力学习率η*=1的可选分支，非网络学习率')
replace('## 声明（不计正文字数）','''## 附录D 完整新增数据、恢复与成本口径（不计正文字数）

第二阶段三个tag分别为`sensitivity_tau003_v1`、`sensitivity_tau03_v1`与`final_soap64_v1`，对应6、6与18项。全部三十项完成并通过完整模型重载、预算与身份、N64/GL200和N96/GL400、四类独立残差的既定验收。正式分析仅聚合保存的复算报告，本作者进一步重聚合原始JSON，没有再次重载模型、训练或积分参考解。完整输出为[全部新增30项](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_analysis_20261022/complete_v1/all_new_runs.csv)、[默认六臂36行](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_analysis_20261022/complete_v1/default_six_arms.csv)及[τ三档18行](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_analysis_20261022/complete_v1/tau_sensitivity.csv)。CSV保留五时刻体/迹序列、四分量残差的RMS与max_abs、损失、实际L-BFGS计数、环境、逐次尝试时间及来源哈希。两张比较表共享六个历史默认记录，合计48个独立分析记录，不能按54行推算训练次数。[E13]

原runner的状态替换故障中断了编排，原21项计算继续执行。监督器按绑定身份的HANDLE确认42个launcher/worker零退出后，修复版runner重新验证完整结果并派发原计划剩余9项。两组都保持各一次attempt，没有因工程恢复更改方程、训练函数、协议、任务预算或参数。原21的训练来源归原Gate，后9归新Gate，两层哈希同时保存在`runtime_status.source_lineage`和逐次attempt记录。新Gate的110项通过属于工程回归，不替代三十项科学验收。最终runner 91632在2026-10-23 06:29:36（UTC+8）由HANDLE观测到退出码0，退出证据和最终状态另行归档。[E15]

成本分为整批历时、runner会话累计、attempt墙钟和记录内训练轨迹四层。原21的attempt墙钟按真实退出观测与原派发时刻计算，含轮询延迟；runner缺席区间不能补记成会话活跃时间。上述层次与历史云端18项另列，均不支持跨硬件速度倍数或等时间精度排名。旧398与新90原始文件共488项由正式清单绑定，稿件数值映射另核206份JSON。完整性保证限定于这些记录，历史部分生产日志及E4表面权重缺失仍保留。[E12,E13,E15]

## 声明（不计正文字数）''')
old_declaration=t.split('## 声明（不计正文字数）\n\n',1)[1]
new_declaration='''作者姓名、单位、通讯作者与作者贡献：待作者确认。资金来源与基金编号：待作者确认，不推断无资助。利益冲突：待作者确认，不代作无利益冲突声明。数据可用性：本地原始结果、权重、协议、代码与复算记录已保存；公开仓库、许可与永久标识待作者确认，不声称已经公开发布。研究对象为数学方程与计算实验，不包含本文采集的人类受试者数据，正式投稿声明格式待按目标期刊核对。

本项目属于原始计算研究。依据用户提出的研究方向、约束和授权，自动AI代理参与了实验任务编排、运行器及产物管理代码的检查与工程修复、计算任务的执行与监测、既有及新增数据的聚合和复核、文献题录与相关原文核对、方法推导检查、图表生成、初稿起草以及内部自动审查和逐项修订。AI参与包含实质性的研究执行与分析辅助，并不限于语言润色。协议、源码、日志、原始结果、模型产物和哈希清单分别保存，以区分数学推导、有限数值核查、已执行计算和未证实解释。

自动代理之间的独立核查属于内部自动审查，不等同于人类作者已全面复核、外部同行评审或期刊录用。尚未记录人类作者对全部代码、数据、参考文献、解释和最终文稿完成逐项核验。正式署名作者须确认各自贡献、核实文稿并确认提交责任；AI工具名称、版本和使用日期等信息仍待本人核实，不预先声明这些确认已经完成。本研究不是系统综述，辅助文献核对不被写成系统检索或双人筛选流程。
'''
assert old_declaration.startswith('作者贡献、单位')
t=t[:-len(old_declaration)]+new_declaration
t=t.replace('\n\n| E13 |','\n| E13 |')
assert 'MATERIAL GAP' not in t
assert '工作版' not in t
assert len(re.findall(r'^## [1-6] ',t,re.M))==6
oldrefs=re.findall(r'^\[\d+\].+$',BASE.read_text(encoding='utf-8'),re.M)
assert re.findall(r'^\[\d+\].+$',t,re.M)==oldrefs
DRAFT.write_text(t,encoding='utf-8')
draft_sha=sha(DRAFT)
config=readj(MAN/'PAPER_CONFIGURATION.json')
counts={}
for title,target in config['section_targets'].items():
    block=t.split('## '+title+'\n',1)[1].split('\n## ',1)[0]
    block=re.sub(r'\\\[.*?\\\]','',block,flags=re.S)
    block=re.sub(r'<!--.*?-->','',block,flags=re.S)
    lines=[line for line in block.splitlines() if not line.startswith('|') and not line.startswith('图') and not line.startswith('![')]
    actual=len(re.findall(r'[\u4e00-\u9fff]',title+'\n'+'\n'.join(lines)))
    counts[title]={'actual_cjk':actual,'target_cjk':target,'deviation_percent':round(100*(actual/target-1),2),'within_15_percent':abs(actual/target-1)<=.15}
total=sum(r['actual_cjk'] for r in counts.values())
save('word_counts.json',{'draft_sha256':draft_sha,'definition':config['count_definition'],
    'implementation_notes':'与冻结稿相同：含章/节标题和表题、表注；排除全部Markdown表行、图题、图片路径、显示公式；附录等不计。',
    'sections':counts,'actual_body_cjk':total,'target_body_cjk':11000,'deviation_percent':round(100*(total/11000-1),2),
    'within_10_percent':abs(total/11000-1)<=.1,'material_gap_count':0})
save('numeric_checks.json',{'draft_sha256':draft_sha,'analysis_sha256':sha(ANALYSIS/'analysis_evidence.json'),
    'raw_json_count':len(paths),'all_raw_json_hashes_match_formal488_manifest':True,
    'json_sha256':{name:sha(ROOT/name) for name in sorted(paths)},'old_176_preserved':True,
    'stage6_main_table_groups':group_checks,'soap_and_tau_independently_reaggregated':soap,'lbfgs_actual_ranges':calls_range,
    'costs':costs,'new_table_markdown':{'table6_tau':tau_table,'table7_default':default_table},
    'scope':'只读JSON/保存报告重聚合与输入/输出哈希核对；不重新加载模型、重训或新参考积分。'})
source_files=[ANALYSIS/'analysis_evidence.json',MAN/'OUTLINE_AND_EVIDENCE.md',MAN/'PAPER_CONFIGURATION.json',
    MAN/'process/writer_phase4a.md',MAN/'process/writer_contract.json',BASE,
    ROOT/'SCREEN_PROTOCOL.md',ROOT/'pinn1d.py',ROOT/'problems.py',ROOT/'stage6_runner.py',
    ROOT/'validation/stage6_20261022/completion_archive_20261023/runner_exit_observation.json',
    ROOT/'validation/stage6_20261022/completion_archive_20261023/archive_manifest.json']
source_files += list(ANALYSIS.iterdir())
source_files += [p for p in (MAN/'figures/history_v2').iterdir() if p.is_file()]
source_files += [Path(x) for x in a['evidence']['input_sha256']]
save('source_checks.json',{'draft_sha256':draft_sha,'sources':{str(p):sha(p) for p in dict.fromkeys(source_files) if p.is_file()},
    'phase4a_preserved':True,'all_analysis_inputs_and_output_hashes_match':True,'all_gate_sources_match':True,
    'frozen_working_draft_sha256':BASE_SHA,'runtime_state_completed':True,'tasks_completed_and_recomputed':30,
    'attempts_per_task':1,'all_task_exit_codes_zero':True,'source_lineage_job_counts':[21,9],
    'N01':'附录C：可选首步注意力学习率η*=1，非网络学习率',
    'N02':'附录A：E1–E3 atol=1e-13，E4体表参考解atol=1e-14',
    'N03':'声明：完整AI执行和分析辅助范围；人类作者全面核验未预先签署',
    'N04':'3.2、4.7及附录A：第一阶段配置调用字段、末次记录损失与真实L-BFGS计数分开',
    'unresolved':['独立完整性核查与五视角审查尚未完成','最终渲染尚未执行','署名单位贡献基金COI及AI工具信息待作者确认','人类作者全面核验待确认','历史生产日志不完备与E4表面权重缺失','三种子/选择偏差/早时间机制/跨环境比较限制保留'],
    'operations':{'training_runs':0,'model_loads':0,'reference_integrations':0,'torch_imports':0,'render_runs':0}})
assert all(sha(Path(p))==v for p,v in before.items())
save('protected_after.json',{str(p):sha(Path(p)) for p in before})
save('draft_state.json',{'draft_sha256':draft_sha,'generated_local':datetime.now(timezone(timedelta(hours=8))).isoformat(),
    'body_cjk':total,'counts':counts,'protected_unchanged':len(before),'phase4b_pending':True})
print(json.dumps({'draft':str(DRAFT),'sha256':draft_sha,'body_cjk':total,'sections':counts,
    'protected_unchanged':len(before),'raw_json_verified':206,'lbfgs_ranges':calls_range},ensure_ascii=False,indent=2))

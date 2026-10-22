"""F01-F05 文稿修订：仅读取既有证据，不训练、不改原稿或原过程文件。"""
from pathlib import Path
from collections import defaultdict
import hashlib
import json
import math
import re
import statistics

OUT = Path(__file__).resolve().parent
MAN = OUT.parents[1]
ROOT = MAN.parent
DRAFT = MAN / 'drafts/working_revised1.md'
INITIAL = MAN / 'drafts/initial_working.md'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def readj(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def writej(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

if DRAFT.exists():
    assert (OUT/'checks.json').exists(), '不覆盖未经本脚本绑定的修订稿'
    assert sha(DRAFT) == readj(OUT/'checks.json')['draft_sha256'], '修订稿已有外部修改，不覆盖'
old = readj(MAN/'process/writer_data_evidence.json')
initial_sha = sha(INITIAL)
assert initial_sha == '9783dd11b2756134b5f365e234e1e7ba4590ab6dd11435fc1910c2e85b84e8d9'

# 只锁定本次读取且不应变化的旧文件，不枚举或干预正在运行的 Stage6。
protected = [INITIAL, MAN/'PAPER_CONFIGURATION.json']
protected += [p for p in (MAN/'process').iterdir() if p.is_file()]
protected += [p for p in (MAN/'research').rglob('*') if p.is_file()]
protected += [ROOT/n for n in ['pinn1d.py', 'problems.py', 'screen.py', 'stage5_support.py',
    'soap_baseline.py', 'SCREEN_PROTOCOL.md', 'E4_PROTOCOL.md', 'METHOD_DERIVATION.md']]
protected += [ROOT/'validation/stage5_analysis_20261022/analysis_evidence.json',
    ROOT/'validation/feasibility_review_20261021/existing_data_review.json',
    MAN/'integrity/working_20261023/WORKING_INTEGRITY_REVIEW_CN.md',
    MAN/'integrity/working_20261023/working_integrity_review.json',
    MAN/'integrity/working_20261023/HISTORICAL_EXECUTION_SCOPE.md',
    MAN/'integrity/working_20261023/historical_execution_scope.json']
protected += [ROOT/r['source'] for r in old['manifest']]
protected = sorted(set(protected), key=str)
before = {str(p): sha(p) for p in protected}
writej('protected_before.json', {'说明':'本次修订前的只读文件绑定；不涵盖正在运行的 Stage6 目录。', 'sha256':before})

rows = defaultdict(list)
manifest = []
for item in old['manifest']:
    p = ROOT/item['source']
    actual_sha = sha(p)
    assert actual_sha == item['sha256'], p
    d = readj(p)
    assert len(d['metrics']['vol']) == len(d['metrics']['trace']) == 5
    assert all(math.isfinite(v) for k in ['vol','trace'] for v in d['metrics'][k])
    assert d['max_vol'] == max(d['metrics']['vol'])
    assert d['max_trace'] == max(d['metrics']['trace'])
    entry = {'source':item['source'], 'sha256':actual_sha, 'seed':d['seed'],
        'max_vol':d['max_vol'], 'max_trace':d['max_trace'], 'config':d['config']}
    rows[(d['tag'],d['eq'],d['method'])].append(entry)
    manifest.append({'source':item['source'], 'sha256':actual_sha})
assert len(manifest) == 176
for group in rows.values():
    group.sort(key=lambda x:x['seed'])

equations = ['E1_heat','E2_allen_cahn','E3_fisher']
methods = ['vanilla','hardic','rba','layer','hardic+layer']
screen = []
for eq in equations:
    for method in methods:
        r = rows['screen',eq,method]
        assert [x['seed'] for x in r] == [0,1]
        screen.append({'equation':eq, 'method':method, 'rows':r,
            'median_vol':statistics.median(x['max_vol'] for x in r),
            'median_trace':statistics.median(x['max_trace'] for x in r)})
sg = {(x['equation'],x['method']):x for x in screen}
review_path = ROOT/'validation/feasibility_review_20261021/existing_data_review.json'
reference_review = readj(review_path)
ref_by_eq = {x['方程']:x for x in reference_review['参考解核验']}
gates = []
for eq in equations:
    baseline = min(['hardic','rba'], key=lambda m:sg[eq,m]['median_vol'])
    candidate = min(['layer','hardic+layer'], key=lambda m:sg[eq,m]['median_vol'])
    ratio = sg[eq,baseline]['median_vol']/sg[eq,candidate]['median_vol']
    ref_diff = ref_by_eq[eq]['N48与N96最大体差']
    vanilla = sg[eq,'vanilla']['median_vol']
    gates.append({'equation':eq, 'reference_max_difference':ref_diff,
        'reference_record_reused_not_rerun':True, 'vanilla_median':vanilla,
        'best_baseline':baseline, 'best_candidate':candidate, 'ratio':ratio,
        'reference_gate':ref_diff<=1e-8, 'vanilla_gate':vanilla>1e-2, 'ratio_gate':ratio>=3,
        'screen_selected':ref_diff<=1e-8 and vanilla>1e-2 and ratio>=3})
assert [x['screen_selected'] for x in gates] == [False,False,True]
paired_ratio = rows['confirm','E3_fisher','hardic'][0]['max_vol']/rows['confirm','E3_fisher','hardic+layer'][0]['max_vol']
assert format(paired_ratio,'.2f') == '1.35'

text = INITIAL.read_text(encoding='utf-8')
original = text
def replace_once(a,b):
    global text
    assert text.count(a)==1, ('待替换段应唯一',a[:70],text.count(a))
    text = text.replace(a,b)

replace_once('> 写作状态：材料可见阶段的工作稿，不是冻结完整稿或投稿稿。',
    '> 写作状态：材料可见阶段的工作稿修订1，已回应完整性预审F01–F05，尚待独立复核，不是冻结完整稿或投稿稿。')

replace_once('实验按筛选、确认及有限补证据先后进行。最初筛选同时涉及热方程、Allen–Cahn 方程和 Fisher–KPP 方程，采用两个种子与较小预算。其用途是决定继续投入的对象。热方程与 Fisher–KPP 方程进入完整预算确认，采用三个报告种子。历史筛选与确认复用了相同编号的部分种子，因此后者不能被表述为种子完全独立的外部验证。本文保留这种历史关系，并将筛选表与正式主表分开呈现。[E01,E05]',
    '实验按筛选、确认及有限补证据先后进行。最初筛选同时涉及热方程、Allen–Cahn 方程和 Fisher–KPP 方程，采用两个种子与较小预算。其用途是决定继续投入的对象。附录B列出全部三十次筛选及原门槛：三个方程的较好基线与较好候选之比分别为'+ '、'.join(f"{g['ratio']:.5f}" for g in gates)+'，原筛选只有 Fisher–KPP 方程入选。热方程未达三倍，随后在已看到筛选结果、尚未启动确认训练时，按协议修订1与 Fisher–KPP 方程一起进入完整预算三种子确认。这不改变原筛选判定。Allen–Cahn 的普通网络中位数为0.0139493，但收益比未达三倍，未继续主确认。历史筛选与确认复用了相同编号的部分种子，因此后者不能被表述为种子完全独立的外部验证。两种子筛选统计与正式三种子主表分开呈现。[E01,E05,E10]')

replace_once('完整预算先进行20000次 Adam 梯度调用，学习率从10⁻³指数衰减至10⁻⁵，再使用名义上限3000次的 L-BFGS。Adam 阶段普通方法每步重采样4096个体点、每端256个边界点和256个初值点。L-BFGS 使用固定点集，体点8192个，每端及初值各512个。四类均方残差的权重为一，硬初值类不再加入初值损失。主实验没有针对候选方法或基线搜索网络规模、训练步数或衰减参数。[E01,E05]',
    '完整预算先进行20000次 Adam 梯度调用，学习率从10⁻³指数衰减至10⁻⁵，再使用名义上限3000次的 L-BFGS。普通网络、硬初值及修正方法在 Adam 阶段每步重采样4096个体点、每端256个边界点和256个初值点，L-BFGS 另取固定点集，体点8192个、每端512个、初值512个。未加注意力或因果权重时，各类均方残差的外部系数为一，硬初值类不再加入初值损失。RBA本地变体的有效点集与权重见下段及表2脚注，不能套用上述 L-BFGS 点数。附录A列出固定实现参数与停止规则，均摘自既有源码、配置及协议，不是本轮新增调参。[E01,E05,E10]')

replace_once('残差注意力按归一化残差历史更新逐点权重[9]，本文按协议在固定体点上更新，并在 L-BFGS 阶段冻结权重。该基线的固定体点数为4096，少于普通方法的8192。这项实现差异在比较中保留，不能因名义迭代上限一致就称各方法使用了相同实际计算量。因果权重由先前时段的残差确定[10]，本文将其叠加于硬初值，时间分为32段，使用两档已登记参数，并在原强基线判定中取对基线有利的一档。本文不将这两档比较推广为充分公平调参后的最优排名。[E01]',
    '残差注意力按归一化残差历史更新逐点权重[9]。本文明确使用RBA本地变体：完整预算下，整个 Adam 点集固定为体4096个、每端256个及初值256个，并在 L-BFGS 继续复用。体、左边界、右边界及初值四类残差分别使用逐点权重，L-BFGS 冻结这些权重。权重初始化为一，在每次 Adam 网络参数更新后，使用本次更新前已计算的残差更新权重。此实现不等同于原文全部训练配置，其与所读版本的差异见附录C。因果权重由先前时段的残差确定[10]，本文将其叠加于硬初值，分32个时间箱，固定使用ε为1或10，两档分别训练，体与两端边界三个分量各自计算因果权重，并在原强基线判定中取对基线有利的一档。本文不将有限配置比较推广为充分公平调参后的最优排名。[E01,E10]')

replace_once('其配对收益约1.36倍', '其配对收益约1.35倍')
text = text.replace('| rba |','| RBA本地变体 |')
replace_once('| E3_fisher | vanilla | 3.19455e-02 | 2.44953e-02 | 4.26099e-02 | 3.19455e-02 | 8.16815e-02 | 0/3 |',
    '| E3_fisher | vanilla | 3.19455e-02 | 2.44953e-02 | 4.26099e-02 | 3.19455e-02 | 8.16815e-02 | 0/3 |\n\n表2注：RBA本地变体在两个优化阶段复用同一完整固定点集，体4096个、每端256个、初值256个；其余表中方法的 L-BFGS 点集为8192、每端512及初值512。RBA四类残差均带逐点权重，进入 L-BFGS 后冻结。原JSON仍含通用的 `nf_fixed`、`nb_fixed`、`n0_fixed` 字段，但源码的RBA分支复用 `fixed_adam`，这些通用字段不决定该分支的有效点数。该差异不能用相同名义步数抵消。[E10]')

replace_once('筛选范围包含未进入主确认实验的 Allen–Cahn 问题，这意味着主文的两个问题已经过选择。',
    '筛选范围包含未进入主确认实验的 Allen–Cahn 问题，热方程也未达到原筛选三倍门槛而由后续协议扩展进入确认，这意味着主文的两个问题已经过选择。')
replace_once('残差注意力的固定点集较少',
    'RBA本地变体的体、两端边界及初值固定点集均较少，且权重初始化和更新次序不同于所读原文算法')
replace_once('### 5.4 进一步工作的具体方向',
    '历史Adam确认与本机SOAP64的执行环境及软件版本不同，因此六臂跨组精度差也不能单独归因于优化器，不能称为同环境的优化器公平排名。修订6的主要叠加判据只比较同批本机SOAP64内的硬初值与硬初值加层，回答该固定实现中的叠加性。名义预算一致与执行环境不同需要同时披露。[E03,E04]\n\n### 5.4 进一步工作的具体方向')
replace_once('保存完整产物能够检验已报告结果的一致性，但不扩大方法的适用范围。[E03,E05,E09]',
    '全部176项分别有130＋24＋22份保存模型复算记录，独立补查绑定398个结果与权重文件。该补查核对已有记录及当前哈希，没有重新加载全部模型；历史日志范围见附录A。保存完整产物能够检验已报告结果的一致性，但不扩大方法的适用范围。[E03,E05,E09,E12]')

replace_once('题录与阅读版本的对应关系见引用上下文表。Favini等仅用于其出版社摘要可支持的经典研究背景，不引述未读证明；部分期刊条目的核心方法核验采用可访问作者稿。SOAP明确引用八作者的arXiv第2版，不将其题名和作者与ICLR终稿混合。',
    '题录与阅读版本的对应关系见 `../process/working_revised1/citation_contexts.md`。Favini等仅用于其出版社摘要可支持的经典研究背景，不引述未读证明；部分期刊条目的核心方法核验采用可访问作者稿。RBA期刊题录的发表年为2024，本次所读缓存为arXiv:2307.00379v2，修订日期2026-08-22，并另核对2023年的v1核心公式与Algorithm 1；两版范围差异及本地实现见附录C。SOAP明确引用八作者的arXiv第2版，不将其题名和作者与ICLR终稿混合。')

replace_once('| E09 | 体表耦合扩展及权重限制 | `../../E4_PROTOCOL.md` 末尾纠正与 `runs/e4confirm` 原始JSON | 体与迹可复核；表面变量定量证据不纳入 |',
    '| E09 | 体表耦合扩展及权重限制 | `../../E4_PROTOCOL.md` 末尾纠正与 `runs/e4confirm` 原始JSON | 体与迹可复核；表面变量定量证据不纳入 |\n| E10 | 修订1实现、全筛选及引用版本核查 | `../process/working_revised1/source_checks.json`、`numeric_checks.json`、`citation_contexts.md`、`revise_working.py` | 只读重聚合176份旧JSON，其中筛选30份；参考自检复用历史记录；不含新训练 |\n| E11 | 半直线辅助层时间导数示意 | `../figures/analytic_layer.png`、`analytic_layer.pdf`、`analytic_layer_data.csv`、`analytic_layer_evidence.json`、`plot_analytic_layer.py` | 解析辅助函数作图，C=0.3；不是完整PDE解或实验性能证据 |\n| E12 | 历史保存模型复算与日志边界 | `../integrity/working_20261023/HISTORICAL_EXECUTION_SCOPE.md`及`historical_execution_scope.json` | 130＋24＋22项保存复算及398产物当前哈希绑定；本轮补查未重放176模型，不证明全历史零警告 |')

figure_caption = (MAN/'figures/analytic_layer_caption.md').read_text(encoding='utf-8').strip()
assert figure_caption.startswith('图：')
figure_path = (MAN/'figures/analytic_layer.png').as_posix()
replace_once('### 2.3 稳定表达式与网络组合',
    f'![Q(y,t)]({figure_path})\n\n图1　'+figure_caption[2:]+' 极小尾部可能下溢为浮点零，图上为零不表示正时间的解析函数严格为零。[E11]\n\n### 2.3 稳定表达式与网络组合')

appendix_a = r'''## 附录A 固定实现参数（工作稿附件，不计正文字数）

以下数值描述实际代码路径及已保存配置。完整预算、筛选预算和待纳入结果的修订6计划分别列明。`nb` 均指每一个端点的点数，硬初值方法不计算初值损失。RBA有效点数以控制流为准，不能仅从JSON的通用 `*_fixed` 字段读取。[E01,E04,E10]

| 项目 | 实际取值或规则 | 对应范围与来源 |
|---|---|---|
| 普通MLP | 输入(x,t)；4个隐藏层、每层64、tanh；Xavier normal权重、零偏置；float64 | `pinn1d.py` 的MLP及Model |
| 随机数与采样 | 网络种子为运行seed，采样生成器种子为1000+seed；体空间与时间均匀抽样，边界时间均匀抽样；原比较 `t_refine=0` | `pinn1d.py` 的train/draw；不包含另行计划的早期加密采样 |
| 完整预算 Adam | 20000次梯度调用；学习率0.001至0.00001，逐调用指数调度；体4096、每端256、初值256 | 确认、新初值、参数轴和架构叠加对应配置 |
| 完整预算 L-BFGS | 名义上限3000；普通方法另取固定体8192、每端512、初值512 | RBA例外见下一行；名义上限不同于内部实际迭代 |
| 完整预算 RBA点集 | Adam开始取一次体4096、每端256、初值256；两个阶段持续复用全部点 | 四类残差都使用逐点权重，L-BFGS冻结权重 |
| 原筛选预算 | Adam4000次，体2048、每端128、初值256；L-BFGS名义上限500，普通方法固定体4096、每端256、初值512；seed为0和1 | RBA在两个阶段复用体2048、每端128、初值256的整个Adam固定点集 |
| RBA权重 | 每个分量各自初始化λ=1；γ=0.999、η=0.01；分量内部最大绝对残差的分母下截断为10⁻³⁰⁰ | 每个分量的损失为mean((λr)²)，再对四个分量求和；不是mean(λr²) |
| RBA更新次序 | 用θₖ和λₖ计算损失，反传并更新网络及学习率，再用已计算的r(θₖ)更新λₖ₊₁ | 不在网络更新后重新计算残差；完整规则见下式 |
| 因果训练 | ε固定为1或10，32箱；体、左端、右端分别分箱与加权；权重不参与梯度 | `causal1`、`causal10`；不是原文完整退火流程；初值残差如存在则保持普通均方 |
| PirateNet本地变体 | width64、3残差块；Fourier scale=1.0，B为2×32标准正态矩阵；嵌入为cos(zB)、sin(zB)，不额外乘2π；可学习跳连系数初值0 | 不采用原文物理信息最小二乘输出初始化 |
| 衰减时间τ | 主参数0.1；修订6另外预定0.03、0.3，主参数旧结果只读复用 | 此表是计划与配置披露，灵敏度完整结果仍待第4.5节 |
| L-BFGS内部参数 | lr=1，max_iter=50/块，history_size=50，line_search_fn=strong_wolfe，tolerance_grad=10⁻¹⁴，tolerance_change=10⁻¹⁶ | 外部每次调用将名义计数加50，内部可能提前终止 |
| L-BFGS块间停止 | L_new≥L_prev(1−10⁻⁹)时停止；恢复时也先检查既有相邻块损失；否则到名义预算停止 | `pinn1d.py`；不能用名义预算替代实际迭代/closure计数 |
| 参考时间积分 | scipy `solve_ivp(method='Radau', rtol=1e-12, atol=1e-13, dense_output=True)` | `problems.py`；空间Chebyshev，左端Neumann消元、右端动态ODE |
| 参考分辨率与求积 | 原自检N48/N96、最大差≤10⁻⁸；常规评估N64/200点Gauss–Legendre；新产物加密复算N96/400点 | 仅支持预定五时刻，早期连续时间精度未由此验证 |
| 修订6 SOAP64计划 | `soap_official64`；betas=(0.95,0.95)，shampoo_beta=0.95，预条件频率10，weight_decay=0；学习率0.001至0.00001 | 20000次梯度调用、首次仅初始化即19999次参数更新；完整18次结果仍待第4.6节 |

对RBA的每一残差分量q及其固定点i，本地实现为

\[
L_k=\sum_q\operatorname{mean}_i[(\lambda_{q,i}^{(k)}r_{q,i}(\theta_k))^2],\qquad
\theta_{k+1}=\operatorname{AdamStep}(\theta_k,\nabla_\theta L_k),
\]
\[
\lambda_{q,i}^{(0)}=1,\qquad
\lambda_{q,i}^{(k+1)}=0.999\lambda_{q,i}^{(k)}
+0.01\frac{|r_{q,i}(\theta_k)|}{\max\{\max_j|r_{q,j}(\theta_k)|,10^{-300}\}}.
\]

对于因果训练，时间箱编号为min(floor(32t),31)。每个分量先分别计算箱内均方残差，空箱计数下截断为1，其箱损失为0；第k箱的权重为exp(−ε∑_{j<k}L_j)，以停止梯度的方式乘箱损失后对32箱取平均。三个时变残差分量分别得到上述平均后相加，不能替换成先合并三个分量再计算共同权重。[E10]

历史复算来源分别为130项既有模型审查、24项小预算模型复核及22项第一阶段新增模型复核，包含原设置和加密设置的体、迹误差记录。独立补查对398个结果与权重文件核对当前哈希，而未重新运行176个模型。部分历史生产进程的逐次退出码和完整警告信息未留存，两个已保存测试日志分别记录63项与71项测试通过、各有1条张量转标量的测试断言警告，不能改称全历史零警告。旧130项的训练源码哈希与当前源码不同，也不能倒称全部历史运行均由当前代码完成。E4中20项历史模型缺少表面权重，仍只支持体与迹。上述范围和逐结果映射见E12所指补充审查。[E12]
'''

table_b = ['| 问题 | 方法 | 体seed 0 | 体seed 1 | 体中位数 | 迹seed 0 | 迹seed 1 | 迹中位数 |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
for x in screen:
    r0,r1 = x['rows']
    label = 'RBA本地变体' if x['method']=='rba' else x['method']
    table_b.append('| '+x['equation']+' | '+label+' | '+' | '.join(f'{v:.7e}' for v in [
        r0['max_vol'],r1['max_vol'],x['median_vol'],r0['max_trace'],r1['max_trace'],x['median_trace']])+' |')
gate_b = ['| 问题 | N48/N96历史最大体差 | vanilla体中位数 | 较好基线 | 较好候选 | 基线/候选比 | 原筛选入选 |',
          '|---|---:|---:|---|---|---:|---|']
for x in gates:
    gate_b.append(f"| {x['equation']} | {x['reference_max_difference']:.7e} | {x['vanilla_median']:.7e} | {x['best_baseline']} | {x['best_candidate']} | {x['ratio']:.5f} | {'是' if x['screen_selected'] else '否'} |")
appendix_b = '''## 附录B 原始筛选的全部结果与原门槛（工作稿附件，不计正文字数）

本附录覆盖原3方程×5种构造×2种子，共30次既有运行。E1、E3定义见表1；E2为D=0.01、c=0.3、R(u)=u−u³、G(u)=u、f(x)=0.5cos(πx)，左端条件和时间范围不变。筛选预算见附录A。`layer` 表示普通网络加解析层、初值仍采用软损失；`hardic+layer` 为式（12）。各seed列均先在五个预定时刻取最大值，两个种子时中位数等于两值平均。本表不合并进正式三种子表，也不从两个样本估计总体概率。[E01,E05,E10]

表B1　全部原筛选的逐种子最大误差。原文件方法标记 `rba` 在此写为RBA本地变体。

'''+ '\n'.join(table_b)+'''

原门槛是同时满足三项：参考N48/N96自检最大差≤10⁻⁸；普通网络体误差中位数>0.01；hardic与RBA中的较低体误差中位数，除以layer与hardic+layer中的较低体误差中位数，所得比值≥3。迹误差不参与该入选规则。这里保留原规则，没有根据完整预算结果调整三倍线。[E01,E10]

表B2　逐方程原筛选门槛。参考列复用2026-10-21已有的自检记录，本次未重新积分参考解；训练指标由原30份JSON重新聚合。

'''+ '\n'.join(gate_b)+'''

三个方程的参考自检及普通网络门槛均满足，只有E3的收益比满足三倍线。E1原筛选未入选，随后依照已看过筛选结果、确认训练尚未启动时追加的修订1，检验扩大预算后的表现；该新增实验不追改原入选状态。E2未进入主确认。全部原JSON的路径与SHA256、精确值及门槛布尔值见 `../process/working_revised1/numeric_checks.json`。本次复核仅是文件和统计重聚合，不等同重新训练。[E01,E10]
'''

appendix_c = '''## 附录C RBA题录、阅读版本与本地差异（工作稿附件，不计正文字数）

文献[9]的期刊题录保留2024年。实际阅读缓存为arXiv:2307.00379v2（2026-08-22），其公式（12）和Algorithm 1用于核查按归一化残差历史累积逐点权重的核心表述。另对arXiv v1（2023）的公式（9）与Algorithm 1作版本交叉核对。阅读较新的作者稿不能写成已逐字核对2024年出版PDF。[E10]

| 项目 | arXiv v1（2023） | 所读arXiv v2（2026-08-22） | 本文实际本地变体 |
|---|---|---|---|
| 原文展示的加权范围 | PDE残差逐点加权，边界与初值另外构成损失 | 扩展为多个残差损失项的逐点加权 | 本题体、左边界、右动态边界、初值四类残差分别加权 |
| Algorithm 1的初始权重 | λ₀=0 | λ₀=0；正文另说明首步采用η的选择 | 四类λ₀=1 |
| Algorithm 1的更新顺序 | 先更新注意力，再更新网络 | 先更新注意力，再更新网络 | 先更新网络，再用本步更新前已计算的残差更新注意力 |
| 支持的共同引用命题 | 归一化残差历史形成逐点注意力 | 归一化残差历史形成逐点注意力 | 使用该思想；完整点集、损失平方、初始化及次序按附录A披露 |

以上差异说明本文比较对象是披露配置的RBA本地变体，不构成对原文完整网络、边界处理、权重策略及调参结果的严格复现。版本信息与核心公式交叉核查不修改已有运行，也不改变原报告的误差值。[E10]
'''

replace_once('## 声明（不计正文字数）', appendix_a+'\n'+appendix_b+'\n'+appendix_c+'\n## 声明（不计正文字数）')
# 核对正文中显示的筛选比值不是手工舍入误写。
for gate in gates:
    assert f"{gate['ratio']:.5f}" in text.split('## 参考文献')[0], gate
assert f"{sg['E2_allen_cahn','vanilla']['median_vol']:.7f}" == '0.0139493'

# 原六个主表保留全部单元数值，只修改RBA的显示标签。
original_tables = [s for s in original.split('## 参考文献')[0].splitlines() if s.startswith('|')]
revised_tables = [s.replace('RBA本地变体','rba') for s in text.split('## 参考文献')[0].splitlines() if s.startswith('|')]
assert original_tables == revised_tables
gaps = re.findall(r'\[MATERIAL GAP.*?\]',text,re.S)
assert gaps == re.findall(r'\[MATERIAL GAP.*?\]',original,re.S) and len(gaps)==2
assert text.split('## 参考文献')[1].split('题录与阅读版本')[0] == original.split('## 参考文献')[1].split('题录与阅读版本')[0]
DRAFT.write_text(text,encoding='utf-8')
draft_sha = sha(DRAFT)

config = readj(MAN/'PAPER_CONFIGURATION.json')
counts = {}
for m in re.finditer(r'^## ([1-6] [^\n]+)\n(.*?)(?=^## [1-6] |^## 参考文献|\Z)',text,re.M|re.S):
    title,content = m[1],m[2]
    clean = title+'\n'+content
    clean = re.sub(r'\\\[.*?\\\]','',clean,flags=re.S)
    clean = re.sub(r'<!--.*?-->','',clean,flags=re.S)
    clean = re.sub(r'^\|.*$','',clean,flags=re.M)
    clean = re.sub(r'^!\[.*?\]\(.*?\)\s*$','',clean,flags=re.M)
    clean = re.sub(r'^图\d+.*$','',clean,flags=re.M)
    clean = re.sub(r'\[MATERIAL GAP.*?\]','',clean,flags=re.S)
    actual = len(re.findall(r'[\u3400-\u4dbf\u4e00-\u9fff]',clean))
    target = config['section_targets'][title]
    counts[title] = {'actual_cjk':actual,'target_cjk':target,'deviation_percent':round(100*(actual-target)/target,2),'within_15_percent':abs(actual-target)<=target*.15}
assert len(counts)==6
total = sum(x['actual_cjk'] for x in counts.values())
writej('word_counts.json', {'definition':config['count_definition'],
    'implementation_notes':'与初稿相同：含六节标题、小节标题及表注，排除全部Markdown表格行、显示公式、图题、HTML注释及MATERIAL GAP；新增图片Markdown行的文件路径亦不计入正文。附录不计。',
    'sections':counts, 'actual_body_cjk':total, 'target_body_cjk':11000,
    'deviation_percent':round(100*(total-11000)/11000,2), 'within_10_percent':abs(total-11000)<=1100,
    'material_gaps':gaps,'draft_sha256':draft_sha})

cmap = readj(MAN/'process/writer_citation_map.json')
refs = cmap['references']
for r in refs:
    if r['key']=='Anagnostopoulos2024RBA':
        r['read_version']='arXiv:2307.00379v2（2026-08-22）；另核对v1（2023）公式9与Algorithm 1'
        r['version_notes']=['期刊题录2024；实际阅读缓存v2为2026-08-22，不等同2024出版PDF逐字核对。',
            'v1主要PDE残差加权；v2扩展多个残差项；二版Algorithm 1均初始化λ0=0且先更新注意力再更新网络。',
            '本地四残差加权、λ0=1，先网络更新，再用预先计算的残差更新注意力。']
contexts=[]
without_bib = text.split('## 参考文献')[0]+'\n'+text.split('## 数据与论据证据映射')[1]
section='front_matter'
for para in re.split(r'\n\s*\n',without_bib):
    if para.startswith('## '): section=para.splitlines()[0][3:]
    if para.startswith('### '): section=para.splitlines()[0][4:]
    for m in re.finditer(r'\[(\d+)\]',para):
        n=int(m[1]); assert 1<=n<=13
        contexts.append({'number':n,'key':refs[n-1]['key'],'section':section,'paragraph':para})
writej('citation_contexts.json',{'draft_sha256':draft_sha,'references':refs,'contexts':contexts,
    'body_citation_occurrences':len(re.findall(r'\[(\d+)\]',text.split('## 参考文献')[0])),
    'all_nonbibliography_occurrences':len(contexts),'unique_references':13,
    'status':'继承已核实题录与来源，新增RBA版本说明；本次不声称重新核验全部13篇原文。'})
cite_md=['# 修订1引用上下文与阅读版本','',f'对应稿件SHA256：`{draft_sha}`。',
    '', '13条原题录保持不变。此次针对F05补充RBA版本与本地差异，其他条目承接既有核验，未伪称本轮重新通读全部原文。', '',
    '| 编号 | BibTeX键 | 题录年份 | 实际阅读版本/范围 |','|---|---|---|---|']
for r in refs:
    cite_md.append(f"| {r['citation_number']} | {r['key']} | {r.get('year','在线')} | {r.get('read_version','见原题录核验表')} |")
cite_md += ['','RBA补充核查：v1为2023版本的公式（9）和Algorithm 1；v2缓存修订于2026-08-22，核查公式（12）和Algorithm 1。v1主要PDE加权、v2扩展多个残差损失项；两版算法均λ₀=0且先注意力后网络。本地λ₀=1，先更新网络再使用预先已算残差更新注意力；四残差和固定点集按稿件附录A、C公开。','']
for c in contexts:
    cite_md += [f"## 引文[{c['number']}]：{c['section']}",'',c['paragraph'],'']
(OUT/'citation_contexts.md').write_text('\n'.join(cite_md),encoding='utf-8')

writej('numeric_checks.json', {'draft_sha256':draft_sha,
    '原始JSON复核':{'数量':len(manifest),'哈希与旧快照全部一致':True,'最大值均等于逐时刻序列最大值':True,'全部误差有限':True,'manifest':manifest},
    'F02':{'ratio':paired_ratio,'rounded_2dp':format(paired_ratio,'.2f'),
        'numerator':rows['confirm','E3_fisher','hardic'][0], 'denominator':rows['confirm','E3_fisher','hardic+layer'][0]},
    'F04':{'run_count':30,'table_rows':15,'seed_scope':[0,1],'statistic':'每个种子先取五时刻最大值，再取两种子中位数（等于两值平均）',
        'screen_groups':screen,'gates':gates,'reference_record':str(review_path),'reference_record_sha256':sha(review_path),
        'reference_review_not_rerun':True},
    '旧主表':{'Markdown行数含表头':len(original_tables),'全部六表数值和排列与原稿一致':True,'仅RBA显示标签改变':True},
    '边界':'这是原记录/源码/统计重聚合，不是重训、重新加载176模型或新参考积分。'})

source_checks = {
    'draft_sha256':draft_sha,'scope':'F01–F05作者修订自核，待独立复核',
    'source_sha256':{str(p):sha(p) for p in protected if p.suffix in ['.py','.md'] and p not in [INITIAL]},
    'F01':{'source':'pinn1d.py:291–305,367–385','effective_full_points':[4096,256,256,256],
        'effective_screen_points':[2048,128,128,256],'order':'体、左端、右端、初值','all_four_weighted':True,
        'lbfgs_reuses_entire_fixed_adam':True,'lbfgs_weights_frozen':True},
    'F03':{'source':'pinn1d.py:26–53,303–325,337–378,389–421; problems.py:166; SCREEN_PROTOCOL.md修订2/5/6',
        'rba':{'lambda0':1,'gamma':.999,'eta':.01,'denominator_floor':1e-300,'network_then_weights':True,'residuals_from_pre_update_parameters':True},
        'causal':{'eps':[1,10],'chunks':32,'componentwise':['pde','left','right'],'detached_weights':True},
        'tau':{'main':.1,'planned_extra':[.03,.3],'results_pending':True},'fourier_scale':1.,
        'radau':{'rtol':1e-12,'atol':1e-13},
        'lbfgs':{'lr':1.,'chunk':50,'history_size':50,'line_search_fn':'strong_wolfe','tolerance_grad':1e-14,'tolerance_change':1e-16,'relative_block_improvement_stop':1e-9}},
    'F05':{'publication_year':2024,'v2_revision_date':'2026-08-22',
        'v1_locations':'公式9与Algorithm 1','v2_locations':'公式12与Algorithm 1',
        'v1_pdf_sha256':'a663d21aefbcabac209e8a371b2abb5280f88118466f60554db8de361136645f',
        'v2_pdf_sha256':'d8db5f61fc6b14471afa5043172cf6f3cd884ab7c6566b80a4002177add73855',
        'v1_text':'D:/CodexRuntime/runs/r33_integrity_working_20261023/RBA_v1.txt',
        'v2_text':'D:/CodexRuntime/runs/r33_integrity_working_20261023/Anagnostopoulos2024RBA.txt',
        'check_boundary':'核查既有缓存所列位置；不是出版PDF逐字校勘。'},
    'retained_limitations':['L01机制证据不足','L02三种子和历史选择','L03缺失E4表面权重','L04两处Stage6材料缺口','L05异环境和异负载墙钟不能排名；历史Adam与本机SOAP64跨组精度差不能单独因果归于优化器'],
    'parent_supplied_analytic_figure':{'path':figure_path,'caption_source':'manuscript/figures/analytic_layer_caption.md',
        'caption_sha256':sha(MAN/'figures/analytic_layer_caption.md'),'kind':'analytic_auxiliary_function_illustration',
        'C':.3,'training_runs':0,'not_full_PDE_solution':True,'not_experimental_evidence':True,
        'visual_review':'父任务已完成PNG及PDF目视复查，见manuscript/figures/analytic_layer_visual_check.json；作者修订整合文件与明确限定图注。'},
    'historical_execution_scope':{'source':'manuscript/integrity/working_20261023/HISTORICAL_EXECUTION_SCOPE.md',
        'saved_replay_groups':[130,24,22],'files_hashed_by_independent_supplement':398,
        'not_replayed_by_current_writer':True,'historical_exit_codes_and_warnings_not_complete':True,
        'preserved_test_logs':[{'passed':63,'warnings':1},{'passed':71,'warnings':1}]}}
writej('source_checks.json',source_checks)

after = {str(p):sha(p) for p in protected}
changed = [p for p in before if before[p]!=after[p]]
assert not changed, changed
writej('protected_after.json',{'sha256':after,'compared_count':len(before),'all_unchanged':True,
    'old_writer_phase4b_sha256':sha(MAN/'process/writer_phase4b.md'),'initial_sha256':sha(INITIAL)})
writej('checks.json', {'draft_sha256':draft_sha,'initial_sha256':initial_sha,'protected_files':len(before),
    'protected_all_unchanged':True,'original_table_numbers_unchanged':True,'original_bibliography_unchanged':True,
    'material_gaps_unchanged':True,'material_gap_count':2,'body_cjk':total,
    'scope':'作者对F01–F05的文稿修订及有限自核；独立完整性结论待复核；尚非完整稿。'})

responses = '''# 工作稿修订1逐项响应

修订对象为 `drafts/working_revised1.md`。只新增修订稿和本目录文件，原稿、旧作者过程文件、研究核验材料、源码、协议与原始结果保持不变。未启动训练、重载模型、重算参考解或触碰运行中的Stage6。

| 问题 | 本次处理 | 稿件位置 | 自核与剩余状态 |
|---|---|---|---|
| F01 | RBA改称本地变体，补全四类残差、整个固定点集复用、L-BFGS冻结权重，并解释JSON通用固定点数字段未进入RBA有效分支 | 3.2、表2标签与脚注、5.3、附录A/C | 源码/旧配置对照已做；待独立复核 |
| F02 | E3原初值seed0配对比由1.36改为1.35 | 4.1 | 原两份JSON重算；精确值及路径见numeric_checks.json；待独立复核 |
| F03 | 补λ初值、γ/η、分母下截断、更新时序；因果ε/分箱/分量；τ、Fourier、Radau、L-BFGS参数和块停规则 | 3.2及附录A | 从既有代码/协议提取，没有新增调参；待独立复核 |
| F04 | 补30次原筛选、15行逐种子体/迹表及3行门槛表；明确仅E3原筛选入选，E1是按后续修订1扩展确认，E2未达三倍 | 3.1、5.2、附录B | 176份JSON只读哈希与最大值复核，30份筛选重新聚合；参考自检仅复用已有记录；待独立复核 |
| F05 | 期刊2024年不变，标明实际阅读v2为2026-08-22；补v1公式9/Algorithm1与v2公式12/Algorithm1差异及本地初始化/顺序差异 | 题录说明、附录C、citation_contexts.md/json | 缓存原文位置已核对；非出版PDF逐字校勘，非严格原方法复现；待独立复核 |

## 原科学与证据局限

L01仍保留：五个离散时刻、最早0.05与均匀独立残差不能证明早期角点因果机制。L02仍保留：正式三种子、历史筛选复用部分编号，新初值分别重训。L03仍保留：E4历史表面权重缺失，不能重建表面定量证据。L04仍保留：第4.5和4.6两个MATERIAL GAP原文逐字保留。L05仍保留：不同环境/负载的墙钟不能给公平耗时排名。此次补表还明确E1未通过原筛选，不能追改该历史判定。

## 交付与核验边界

'''
responses += f'- 修订稿SHA256：`{draft_sha}`。\n- 初稿SHA256：`{initial_sha}`，与修订前一致。\n- 正文按原口径计{total}个汉字，相对11000目标偏差{100*(total-11000)/11000:.2f}%；附录、表格数据及占位段不计。\n- 逐节字数、偏差和门槛见word_counts.json；本轮不以填充文字假装未完成的第4节结果或完整结论已补齐。\n- 保护文件{len(before)}份逐项哈希未变；176份旧JSON的哈希、逐时刻最大值与有限性一致；六个旧主表全部数字未变。\n- 13条原参考题录未变；新增引用版本说明。独立完整性复核尚未进行，不能把作者自核记为审稿通过。\n'
responses += '\n另按父任务明确指示纳入其提供的图1与E11映射：C=0.3的半直线辅助层Q=w_t解析示意，不含错配幅度或衰减、不作为完整PDE参考解、PINN预测或机制因果证据。父任务已完成PNG与PDF目视复查，见analytic_layer_visual_check.json；本轮未改图文件。\n\n新增E12引用完整性补充审查，简述130＋24＋22保存模型复算、398文件的独立哈希核对及日志边界；本作者没有重放176模型。保留历史源码版本差异、部分生产退出码/警告留存不完整以及63/71测试各1警告，不宣称全历史零警告。\n'
responses += '\n按父任务补充要求，在5.3明确环境差异也限制Adam与SOAP64跨组精度差的因果归因；主要S6叠加比较只在同批本机SOAP64内进行，不把名义预算一致解释为同环境优化器公平排名。此处未填写待完成结果。\n'
(OUT/'responses.md').write_text(responses,encoding='utf-8')
print(json.dumps({'draft':str(DRAFT),'sha256':draft_sha,'body_cjk':total,'sections':counts,
    'screen_ratios':[x['ratio'] for x in gates],'paired_ratio':paired_ratio,
    'protected_unchanged':len(before),'gaps':2,'citations_nonbibliography':len(contexts)},ensure_ascii=False,indent=2))

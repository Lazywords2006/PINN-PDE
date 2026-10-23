"""绑定25项作者响应与本轮局部核对；不改旧稿、审稿清单或科学产物。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from statistics import median
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
MAN = OUT.parents[1]
ROOT = MAN.parent
DRAFT = MAN / 'drafts/complete_revised1.md'
BASE = MAN / 'drafts/complete_v1.md'
REVIEW = MAN / 'reviews/revision1'
readj = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat()

def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

assert not (OUT / 'FROZEN_REVISION_MANIFEST.json').exists(), '已冻结稿不可重新生成证据。'
assert sha(DRAFT) == readj(OUT / 'revision_state.json')['draft_sha256']
t = DRAFT.read_text(encoding='utf-8')
base = BASE.read_text(encoding='utf-8')
digest = sha(DRAFT)
changes = readj(OUT / 'change_map.json')
sources = readj(OUT / 'source_evidence.json')
sources['status'] = '五份审阅及统一25项清单已绑定作者响应；作者局部核查完成，独立修订核验与最终完整性仍待执行。'
save('source_evidence.json', sources)
counts = readj(OUT / 'word_counts.json')
checks = readj(OUT / 'revision_checks.json')
assert all(x['draft_sha256'] == digest for x in (changes, counts, checks, readj(OUT / 'editing_audit.json')))
tracker_files = {
    'REVIEW_ITEMS.json': '3ff9d4159f28a547dd16bc065403f649defa36570ed4f1a7bdc7842bdf58bd78',
    'REVISION_ROADMAP_CN.md': '213dec21b3ba3ccb2c7e94bb71e5c3fa5b69954a2db887b581291c19c4b41424',
    'PROTOCOL_EXCEPTION_CN.md': 'f49bc0ecb2968ac76d1e366360357ea46f036eb7a7088e9aad3c8d20b6b26a40'
}
assert all(sha(REVIEW / name) == expected for name, expected in tracker_files.items())
tracker = readj(REVIEW / 'REVIEW_ITEMS.json')
items = tracker['修订条目']
assert len(items) == 25 and sum(x['类别'] == '必修' for x in items) == 14
assert all(x['核验状态'] == '待核验' and x['独立核验结果'] is None for x in items)

def anchor(needle, label, file=DRAFT):
    text = t if file == DRAFT else file.read_text(encoding='utf-8')
    assert text.count(needle) == 1, (label, text.count(needle))
    return {'file': str(file), 'line': text[:text.index(needle)].count('\n') + 1, 'label': label,
            'exact_anchor': needle, 'sha256': sha(file)}

def file_evidence(file, detail):
    assert file.is_file()
    return {'file': str(file), 'sha256': sha(file), 'detail': detail}

L = {
    'clamp': anchor('该改写避免显式形成较大的正指数，与式（8）等价', '§2.3：截断与未截断解析式'),
    'prop': anchor('**命题1（初值与初始导数迭代极限）。**', '§2.3：命题1的解析对象'),
    'heldout': anchor('独立残差点由NumPy `default_rng(330500)`', '§3.4：独立点抽样顺序与分量数'),
    'axis_intro': anchor('主实验采用表1的两类方程', '§3.1：参数轴进入边界函数的位置'),
    'axis': anchor('表5注：E1仅改变c∈', '表5注：两参数轴、固定量、运行标签与错配'),
    'a1': anchor('跨架构强基线比较仍存在不同结论。', '§4.3：A-1首处名称与定位'),
    'g2': anchor('小预算效果判据G2对E1/E3分别检查', '§4.6：G2首处名称与定位'),
    'pirate': anchor('表4注：E1两方法的seed 0、1', '表4注：逐种子来源及中位数范围'),
    'pirate_results': anchor('表4在相同 PirateNet 变体内比较', '§4.3：保留22.61与5.52的描述性比值'),
    'e4main': anchor('体表耦合扩展具有不同的边界交换结构', '§5.2：E4负面结果及附录入口'),
    'input_target': anchor('构造需要可靠的f′(1)、f″(1)及算子参数。', '§5.4：输入可靠性及目标量限制'),
    'future': anchor('已完成的灵敏度和固定SOAP64对照补足了两个预先安排的经验问题', '§5.4：未来同环境、独立种子研究范围'),
    'costmain': anchor('### 4.7 独立残差与计算成本', '§4.7：预算与四层成本的科学解释'),
    'environment': anchor('历史Adam确认与本机SOAP64的环境及软件版本不同', '§5.3：跨路线与跨档混杂边界'),
    'artifactscope': anchor('产物核验保留结果、权重与配置的对应关系。', '§3.4：来源核验与历史链范围'),
    'model_scope': anchor('本文的贡献范围是一个自包含的相容性分析', '§1：已有解析工具与本工作范围'),
    'mechanism': anchor('### 5.1 局部分析能够解释的范围', '§5.1：机制解释边界'),
    'budget': anchor('| 完整预算 Adam |', '附录A：紧凑预算与采样表'),
    'clamp_table': anchor('| 层函数的时间截断 |', '附录A：时间下界精确常数'),
    'fields': anchor('调用与损失字段口径如下：', '附录A：删除N04后的直接字段解释'),
    'clamp_detail': anchor('时间截断须与解析延拓区分：', '附录A：截断分支自动微分不验证解析极限'),
    'history': anchor('## 附录D 完整新增数据、恢复与成本口径', '附录D：集中的历史来源、恢复与计时'),
    'csv': anchor('第二阶段三个tag分别为', '附录D：含环境、实际调用的完整数据表入口'),
    'fourcosts': anchor('成本分为整批历时、runner会话累计、attempt墙钟和记录内训练轨迹四层。', '附录D：成本定义与不支持等时间排名'),
    'e4': anchor('## 附录E 体表耦合扩展的模型与完整预算数据', '附录E：式E1—E4和实际配置'),
    'e4dist': anchor('实际参数为D=0.1、κ=γ=V₀=1。', '附录E：独立v、通量错配与层定义'),
    'e4table': anchor('表E1　E4完整预算探索性结果', '附录E表E1：完整三种子体/迹表'),
    'e4ratio': anchor('表E1第一行vanilla的体误差中位数', '表E1后：0.838的分子、分母与汇总次序'),
    'e4limit': anchor('小预算筛选未满足原三倍条件；完整预算是在已见筛选失败后', '附录E：探索性质及20份表面权重缺失'),
    'a1full': anchor('跨架构强基线判据A-1见SCREEN_PROTOCOL', '附录F：A-1对象与联合门槛'),
    'g2full': anchor('小预算效果判据G2见SCREEN_PROTOCOL', '附录F：G2两项、两方程与原种子/预算'),
    'e09': anchor('| E09 | 体表耦合扩展及权重限制 |', 'E09：科学附录、表E1和协议具体节'),
    'quota': file_evidence(OUT / 'COUNT_DEFINITION_COMPARISON_CN.md', '原配置、六章目标、实际计数及五种计数口径'),
}
E = {
    'sampling': file_evidence(ROOT / 'stage5_support.py', 'heldout_residuals附近的固定default_rng和抽样顺序；具体值同步保存于source_evidence.json.heldout'),
    'model': file_evidence(ROOT / 'pinn1d.py', 'layer_profile/flux_layer的1e-30截断；Model的E4分支与硬初值表达式'),
    'problem': file_evidence(ROOT / 'problems.py', '_e1/_e3及BulkSurface的参数、初值和边界函数定义'),
    'protocol': file_evidence(ROOT / 'SCREEN_PROTOCOL.md', '修订2第A组A-1/A-2；修订4第5项G2；后续修订保持原判定'),
    'e4protocol': file_evidence(ROOT / 'E4_PROTOCOL.md', '第2—5节、修订1及末尾纠正，原科学模型、追加探索与表面分支缺失'),
    'raw': file_evidence(OUT / 'source_evidence.json', '32份定向JSON核对：E4筛选8+完整12+PirateNet12，含原序列/最大值/中位数/来源SHA'),
    'fig': file_evidence(OUT / 'figure_retention_checks.json', '四个PNG与既有冻结哈希一致'),
    'counts': file_evidence(OUT / 'word_counts.json', '原配置口径六章逐项及总量结果'),
    'countdiff': file_evidence(OUT / 'count_definition_comparison.json', '各审阅计数的算法重现及逐行分类'),
    'config': file_evidence(MAN / 'PAPER_CONFIGURATION.json', '事前六章目标1800/2200/2000/2500/1700/800，总量与分节容差不变'),
    'change': file_evidence(OUT / 'change_map.json', '逐修改前后原文、原行号与新行号'),
    'cite': file_evidence(OUT / 'citation_contexts.json', '13题录与18处外部上下文保持；现有阅读范围与限制保留')
}

specs = {}
def add(ids, response, locs, evidence, disposition='采纳', state='RESOLVED', reason=None):
    for id_ in ids:
        assert id_ not in specs
        specs[id_] = {'response': response, 'locations': [L[x] for x in locs], 'evidence': [E[x] for x in evidence],
                      'disposition': disposition, 'author_state': state, 'unadopted_reason': reason}

add(['M1'], '§2.3和附录A均补出t.clamp_min(1e-30)；§3.4列明default_rng(330500)及体x、体t、左端t、右端t、初值x的抽样顺序，数组8192/8192/1024/1024/1024，四残差分量8192/1024/1024/1024。说明两端时间独立，点集未用于训练或选择。只抄录现有实现，没有改代码或重训。',
    ['clamp','heldout','clamp_table'], ['sampling','model','raw'])
add(['M2','DR1','EIC-M2'], '在§3.1指出κ进入边界函数；表5注给出E1只改c且D=1、R=0、G(u)=0.3u和初值不变，E3为Gκ(u)=κ(u−1)、κ∈{0.1,1,3}，D=0.1、c=0.3、R=u(1−u)和初值不变。明确运行名k就是κ；保留表5全部结果，另给错配公式校验。',
    ['axis_intro','axis'], ['problem','protocol','change'])
add(['M3'], '删除未定义的内部编号N04，直接引入调用与损失字段口径；保留完成循环后写入配置计数、末次记录损失不等于终点重评、实际L-BFGS状态计数的既有说明。全文检索确认无N04残留。',
    ['fields'], ['change'])
add(['DR2','R3-2'], '新增附录E式E1—E4：体PDE、左右端条件、独立表面ODE、初值、D=0.1及κ=γ=V0=1、常通量层U与两分支表达式。明确v不等于u(1,t)，常通量辅助层不含表面反馈，与式12的动态层不同。表E1列完整12次运行的三种子体/迹指标；0.838按vanilla体中位数除以修正组体中位数，先每种子五时刻最大、再三种子中位数。保留20份表面权重缺失与追加探索性质，仅重聚合已有JSON，未补权重或表面定量证据。',
    ['e4main','e4','e4dist','e4table','e4ratio','e4limit'], ['problem','model','e4protocol','raw'])
add(['DR3'], '附录A直接说明字段并删除N04；§4.3与§4.6首次提及A-1和G2时给中文名称、比较对象及附录F定位。附录F详细列出两者的原门槛、对象和预算，保留联合不满足。E09改指附录E表E1与E4_PROTOCOL具体节，0.838可直接由表后分子/分母核查。',
    ['fields','a1','g2','a1full','g2full','e09','e4ratio'], ['protocol','e4protocol','change'])
add(['DA-m1'], '表5注补全Gκ与固定量；新增附录E给E4体方程、初值、交换边界、独立v方程及实际U层和硬初值分支。式E3是常通量辅助层，文字明确其不含表面反馈，未称为式12原样推广。§5.2定量结论指向表E1，旧负面结果保留；未新增训练。',
    ['axis','e4main','e4','e4dist','e4table'], ['problem','model','e4protocol','raw'])
add(['DA-m2'], '表4旁逐种子说明：E1两方法seed0/1从历史检查点在本机续完，seed2与E3全部为历史云端结果。同种子来源类别对应，但混合来源的三种子中位数不是统一环境随机重复分布估计。表4全部数值、22.61/5.52及逐种子比较均原样保留；没有删种子或认定已证明不公平配对。',
    ['pirate','pirate_results'], ['raw','change'])
add(['DA-m3'], '在命题1中明确讨论未截断的解析表达式；§2.3和附录A列精确下界。附录A解释t<1e-30时通过开方变量的时间依赖被固定，外部衰减与背景项仍有导数，不能用该分支的AD极限验证解析迭代极限。原浮点初值误差边界保留，不声称逐位零。',
    ['prop','clamp','clamp_table','clamp_detail'], ['model','change'])
add(['EIC-M1'], '删除N04并直接列字段说明。A-1首次出现处给跨架构强基线名称与附录F入口；G2首次出现处说明主候选对强基线和SOAP内叠加两个目标。附录F列两个方程、种子100/101、4000+500预算、三倍和2/2绝对阈值，明确G2未满足指两方程两项的联合条件，不是四个子判断全失败；完整SOAP对照不追改旧判定。',
    ['fields','a1','g2','a1full','g2full'], ['protocol','change'])
add(['R3-1'], '表5注完整列κ边界函数、三个取值、固定D/c/反应/初值及k标签；§2.3、命题1与附录A给1e-30下界及未截断解析连续延拓的范围。读者可从稿件恢复参数轴和实际求值规则，不需根据δ或文件名猜测。',
    ['axis','clamp','prop','clamp_table','clamp_detail'], ['problem','model','change'])
add(['R3-3'], '§3.4与§4.7缩短具体恢复过程，历史130+24+22来源、原21/后9和四层计时边界集中到附录D。主文保留预算、环境混杂及解释所必需的区别。核验附件给原PAPER_CONFIGURATION的六章基数、逐章实际值、±15%和总11000±10%，并复现审阅中的不同计数口径；没有修改目标、旧报告或用附录补正文配额。',
    ['artifactscope','costmain','history','fourcosts','quota'], ['config','counts','countdiff','change'])
add(['M-建议1'], '采纳为一个短科学附录：E4的方程、独立v、实际参数、常通量层与配置入口均在附录E；§5.2和E09可直接定位表E1与0.838计算。与DR2共用内容，未另增实验门槛。',
    ['e4main','e4','e4table','e09'], ['e4protocol','problem','raw'])
add(['M-建议2','EIC-建议1'], '压缩§3.4、§4.7、§4.3和τ讨论的重复过程表述，将完整历史执行与恢复范围集中到附录D，附录A仅保留入口。仍在图注、相应比较和局限段保留直接影响解释的环境混杂、非置信区间和负面结果；这些位置各约束不同主张，不合并删除。',
    ['artifactscope','costmain','history','environment'], ['change','fig'])
add(['DR-建议1'], '采纳δ=(0.02+κ)/0.3+0.02并放在表5注；本轮数值核对得到κ=0.1/1/3时δ=0.42/3.42/10.0866666667，与表5显示值一致。只核算现有定义，不据该式建立收益对错配的单调性。',
    ['axis'], ['problem','change'])
add(['EIC-建议2'], '附录A实现表新增“层函数的时间截断”一行，给出rt=torch.sqrt(t.clamp_min(1e-30))并说明两类层的使用范围；表后区分截断AD与未截断解析极限。',
    ['clamp_table','clamp_detail'], ['model','change'])
add(['R3-建议1'], '§5.4补出可靠f′(1)、f″(1)及算子参数的输入条件；说明只测试解析初值，带噪观测与离散插值造成的导数估计误差对δ的影响尚未验证。未添加带噪实验或把此条件写成新的已验证结论。',
    ['input_target'], ['problem','change'])
add(['R3-建议2'], '同一新增段说明应用应先确定目标量；本研究的体相对误差和独立迹误差不能代表边界储存、交换通量等全部物理量的精度次序。保留原主指标，不将现有排序外推到未计算目标量。',
    ['input_target'], ['change'])
add(['R3-建议3'], '部分采纳：预算已有附录A紧凑表，本轮把历史来源、恢复和四层成本集中到附录D，并在表4直接补逐种子来源；完整CSV保存逐运行环境与调用。暂不另加一个跨来源环境总表，避免重复既有预算表，并保留“历史检查点本机续完”等无法用单一批次标签概括的信息。精度和成本混杂仍在§5.3明确，未主张等时间收益或固定额外开销。',
    ['budget','pirate','csv','fourcosts','environment'], ['raw','change'], disposition='部分采纳', state='DELIBERATE_LIMITATION',
    reason='不另新增重复的总表；已有紧凑预算表、具名补充入口与逐记录来源比单一环境标签更精确。该项原验收允许以现有披露和具体理由回应。')
add(['R3-建议4'], '本轮不加入可选的Melenk与Babuška文献。现有§1已将经典局部层和解析富集工具与本工作的具体构造分开，命题1与经验结论的范围也已明确。新增单位分解有限元桥接会扩展相关工作分支而不补当前必修披露缺口；没有阅读新来源后再借其理论作PINN保证的必要。保留现有13条已核对题录。',
    ['model_scope','prop'], ['cite','config'], disposition='不采纳', state='DELIBERATE_LIMITATION',
    reason='与本轮局部修订及当前有限主张的直接关系较弱；不新增未核对的文献，不声称其具体内容支持本文。')
add(['R3-建议5'], '本轮不新增Oberkampf与Trucano文献。§3.4、§5.1和附录D已分别限定数值复算、机制解释及历史执行范围，且本文不包含物理观测验证；本轮采用这些具体边界而不扩展为一个新的验证框架综述。没有据此省略已有独立点/参考解检查，也未提出新物理实验要求。',
    ['artifactscope','mechanism','history'], ['cite','change'], disposition='不采纳', state='DELIBERATE_LIMITATION',
    reason='原建议为可选概念组织；现有具名证据分层足以回应意图，添加新框架需额外原文核查且不改变当前结论。')
add(['R3-建议6'], '本轮不新增Morris文献。§4.5与§5.3已限制三档、三种子及跨环境解释；§5.4把同环境、独立种子和可分离因素设计列为下一步。当前实验没有开展Morris敏感性分析，不借可选引文把三档描述性结果升级为该分析。',
    ['environment','future'], ['cite','config'], disposition='不采纳', state='DELIBERATE_LIMITATION',
    reason='后续研究设计尚未展开；保留具体未来方向，不为本轮有限参数结果增加方法名称或未经核对的新文献。')
assert set(specs) == {x['编号'] for x in items}

# 只重核本轮新增的算术和原始JSON快照汇总，不再遍历206个旧数据文件。
e4_rows = [x for x in sources['e4_groups'] if x['tag'] == 'e4confirm']
for row in e4_rows:
    assert len(row['max_vol']) == 3 and median(row['max_vol']) == row['vol_median']
    assert median(row['max_trace']) == row['trace_median']
    cells = [('RBA本地变体' if row['method'] == 'rba' else row['method']),
             *[f'{v:.5e}' for v in row['max_vol']], f"{row['vol_median']:.5e}", f"{row['trace_median']:.5e}", f"{row['under_1e2']}/3"]
    assert '| ' + ' | '.join(cells) + ' |' in t
by_method = {x['method']: x for x in e4_rows}
ratio = by_method['vanilla']['vol_median'] / by_method['hardic+layer']['vol_median']
assert ratio == sources['e4_vanilla_over_corrected_median_ratio']
assert f'{ratio:.12f}' in t and f'{ratio:.3f}' == '0.838'
delta_checks = [{'kappa': k, 'delta': (.02 + k)/.3 + .02, 'table_precision': f'{(.02+k)/.3+.02:.8g}'} for k in (.1, 1., 3.)]
assert all(x['table_precision'] in t for x in delta_checks)
numeric = {'draft_sha256': digest, 'e4_rows': e4_rows, 'e4_vanilla_over_corrected': ratio,
           'e3_parameter_axis_delta': delta_checks, 'eight_old_main_tables_data_unchanged': True,
           'reuse_scope': '复用本轮source_evidence中32项定向原JSON的已核数据，以及完整v1已通过的206项数值映射；此步不重新加载模型或重复全库哈希。'}
save('numeric_revision_checks.json', numeric)

responses = []
for item in items:
    spec = specs[item['编号']]
    responses.append({
        '编号': item['编号'], '原审稿编号': item['原审稿编号'], '审稿角色': item['审稿角色'],
        '类别': item['类别'], '问题摘要': item['问题摘要'], '原报告位置': item['原报告位置'],
        '原验收条件': item['验收条件'], '合并动作组': item['合并动作组'],
        '作者答复': spec['response'], '作者处置': spec['disposition'], '作者修订状态': spec['author_state'],
        '状态含义': '仅表示作者已经落实编辑或说明取舍；不替代独立核验，不回写原清单。',
        '实际修订位置': spec['locations'], '作者证据': spec['evidence'], '未采纳部分及理由': spec['unadopted_reason'],
        '独立核验状态': 'PENDING', '独立核验结果': None, '核验人': None
    })
response_file = {
    'draft_sha256': digest, 'base_sha256': sha(BASE), 'generated_local': now(),
    'tracker_sha256': tracker_files['REVIEW_ITEMS.json'], 'old_panel_status': 'ABORT / PANEL-SHRUNK: usable=2, panel_size=5; no full-panel editorial decision',
    'counts': {'mandatory_responded': 14, 'mandatory_total': 14, 'optional_responded': 11, 'optional_total': 11,
               'responses': 25, 'adopted': 21, 'partly_adopted': 1, 'not_adopted_optional_references': 3,
               'independently_verified_closed': 0}, 'responses': responses,
    'boundary': '原五份报告、契约、lint与tracker未修改；作者RESOLVED/DELIBERATE_LIMITATION均不等于FULLY_ADDRESSED独立核验。'
}
assert sum(x['作者处置'] == '采纳' for x in responses) == 21
assert all(x['作者修订状态'] == 'RESOLVED' for x in responses if x['类别'] == '必修')
save('RESPONSE_TO_REVIEWS.json', response_file)

md = ['# 首轮完整稿修订逐项答复', '',
      f'修订稿：[{DRAFT.name}](<{DRAFT.as_posix()}>), SHA256 `{digest}`。原完整稿SHA256 `{sha(BASE)}`。', '',
      '本响应逐项覆盖统一清单的14项必修和11项建议。作者已落实21项、部分采纳1项、未采纳3项可选桥接文献；全部25项均有答复。下述RESOLVED和DELIBERATE_LIMITATION仅为作者处置状态，全部独立核验仍为PENDING。原清单保持待核验，没有替复核者填FULLY_ADDRESSED。', '',
      '原full_v1五份报告完成，但冻结契约全轮保持ABORT、2/5可用、无编辑裁决；两份局部accept不代表五人结论。本轮是常规作者修订，既不改旧评分与契约，也不回填原面板通过。说明见reviews/revision1/PROTOCOL_EXCEPTION_CN.md。', '',
      '现稿状态为“五份独立自动审阅意见后的修订初稿，待修订核验与最终完整性检查，未投稿”。没有新增训练、模型加载、参考积分、图形重绘或git操作。', '']
for response in responses:
    md += [f"## {response['编号']}：{response['问题摘要']}", '',
           f"来源：{response['审稿角色']}，{response['类别']}。作者处置：{response['作者处置']}；状态：{response['作者修订状态']}（独立核验PENDING）。", '',
           response['作者答复'], '', '修订位置：', '']
    for loc in response['实际修订位置']:
        line = f":{loc['line']}" if 'line' in loc else ''
        label = loc.get('label', loc.get('detail', Path(loc['file']).name))
        md.append(f"- [{label}](<{Path(loc['file']).as_posix()}{line}>)")
    md += ['', '证据：', '']
    for ev in response['作者证据']:
        md.append(f"- [{Path(ev['file']).name}](<{Path(ev['file']).as_posix()}>): {ev['detail']}")
    if response['未采纳部分及理由']:
        md += ['', '未采纳部分与理由：' + response['未采纳部分及理由']]
    md += ['', '原验收条件逐项保留在JSON中；本条尚未由独立复核者认定关闭。', '']
md += ['## 保留的未验证范围与后续核验', '',
       '修订核验须亲自检查上述25项对应位置；最终HTML/PDF、版面和全稿完整性由独立流程随后核查。署名、单位、基金、利益冲突、贡献与人类作者最终核验仍待作者确认。', '',
       '科学边界保留：五个正时刻不能证明早期角点机制；三种子、筛选后选择与环境差异不支持总体成功概率或纯优化器/τ因果排名；历史生产日志不完整，E4表面权重缺失；原A-1/G2不满足、弱错配退化、新初值不利种子及E4对vanilla无额外收益均未删除。', '']
(OUT / 'RESPONSE_TO_REVIEWS_CN.md').write_text('\n'.join(md), encoding='utf-8')

protected = readj(OUT / 'protected_before.json')
assert len(protected) == 28 and all(sha(Path(p)) == value for p, value in protected.items())
assert all(sha(Path(p)) == value for p, value in sources['sources'].items())
assert all(sha(Path(p)) == value for p, value in checks['reviews_read'].items())
assert all(sha(REVIEW / name) == value for name, value in tracker_files.items())
save('protected_after.json', protected)
source_checks = {'draft_sha256': digest, 'base_sha256': sha(BASE), 'checked_local': now(),
    'old_protected_files_unchanged': len(protected), 'protected_file_hashes': protected,
    'five_source_and_protocol_hashes_current': sources['sources'], 'five_review_files_unchanged': checks['reviews_read'],
    'tracker_files_unchanged': {str(REVIEW / name): value for name, value in tracker_files.items()},
    'domain_counting_source': file_evidence(MAN / 'reviews/full_v1/domain_evidence.py', '仅检查78—85行以解释10243计数，未运行该审稿脚本'),
    'data_checks_reused': {'current_targeted_json_records': 32, 'older_complete_v1_json_records': 206,
                           'raw_files_rehashed_at_finalization': 0, 'scope': '原本轮采集及完整v1核验仍有效；未进行重复全库扫描。'},
    'new_numeric_checks': str(OUT / 'numeric_revision_checks.json'), 'four_figure_hashes_preserved': True,
    'remaining': ['独立逐项修订核验', '最终完整性与渲染核验', '人类作者最终核验及署名、单位、基金、利益冲突、贡献信息'],
    'operations': {'training': 0, 'model_load': 0, 'reference_integration': 0, 'render': 0, 'git_mutation': 0}}
save('source_checks.json', source_checks)
assert counts['within_10_percent'] and all(x['within_15_percent'] for x in counts['sections'].values())
assert 'N04' not in t and 'MATERIAL GAP' not in t
assert t.count('\\[') == t.count('\\]')
assert len(re.findall(r'^\[\d+\].+$', t, re.M)) == 13
assert re.findall(r'!\[[^\]]*\]\(([^)]+)\)', t) == re.findall(r'!\[[^\]]*\]\(([^)]+)\)', base)
for needle in ['五份独立自动审阅意见后的修订初稿，待修订核验与最终完整性检查，未投稿',
               '新初值有个别种子退化', '跨架构强基线A-1及小预算G2仍未满足', '0.838',
               '两种子筛选统计与正式三种子主表分开呈现', '未隔离不同优化器的总体贡献']:
    assert needle in t
checks.update({'review_tracker_sha256': tracker_files['REVIEW_ITEMS.json'], 'mandatory_response_count': 14,
               'optional_response_count': 11, 'independent_closed_count': 0, 'new_e4_numeric_rows_checked': 4,
               'parameter_delta_checks': 3, 'all_external_citation_contexts_unchanged': 18,
               'figure_hashes_unchanged': 4, 'original_panel_status_preserved': 'ABORT; no editorial decision',
               'independent_revision_review_pending': True, 'final_render_pending': True, 'final_frozen': False})
save('revision_checks.json', checks)
selfcheck = f'''# 作者修订自核与交付边界

绑定稿件SHA256：`{digest}`。本文件是作者自核，不是独立审阅或编辑裁决。

- 原14项必修与11项建议全部逐项答复，14必修均有实际修订位置。21项采纳、1项部分采纳、3项可选文献不采纳；理由均明确。独立核验关闭数为0。
- 正文{counts['actual_body_cjk']}汉字，总目标11000±10%；六章1695/2190/2187/2755/1897/763，均在原目标±15%。原配置SHA及计数口径见专门附件；附录不计正文。
- 原8张主表数值逐字保持，13条题录与18处外部引用上下文保持，4张图路径与PNG哈希保持。本轮新增附录E四方法三种子表，逐行与已核的12份E4完整预算JSON汇总一致；0.838398555111及三档δ另核算。
- 32份定向JSON的源哈希、时刻、有限性、最大值与来源已在本轮source_evidence记录；最终步骤复用有效检查，没有再扫描206项全库、载入模型或重新积分。
- 28份既有受保护文件、5份源码/协议、5份审阅报告以及3份统一清单文件均保持原哈希。旧Phase4a/Phase4b、冻结完整v1、原reviewer契约、评分、lint及数据均未改。
- 解析命题明确针对未截断表达式，实际1e-30截断单列。E4常通量层与正文动态层分开；历史表面权重缺失未补造。
- 原主τ=0.1、Adam主路线、0次超参数搜索、全部不利种子/未满足判据与环境混杂边界保留。原五人轮次维持ABORT、2/5可用、无全轮裁决。

本轮逐一阅读并修改了change_map中的全部编辑块，最终附录E的方程、符号、参数和表格也已回读。显示数学分隔符成对，14个Markdown表的列结构一致，稿内已使用的全部E编号均有内部证据映射。没有为本轮重新生成旧写作Phase4b自评分或修改预承诺。

剩余工作：由独立复核者实际核查25项响应；随后完成全稿完整性、最终渲染与版面检查。人类作者最终确认及署名、单位、基金、利益冲突、贡献信息仍待补齐。本文未投稿，自动审阅不等于真实同行录用。
'''
(OUT / 'REVISION_SELF_CHECK_CN.md').write_text(selfcheck, encoding='utf-8')
save('revision_state.json', {'draft_sha256': digest, 'generated_local': now(), 'body_cjk': counts['actual_body_cjk'],
     'read_reviewers': 5, 'pending_reviewers': [], 'tracker_items_responded': 25, 'author_revision_complete': True,
     'independent_revision_review_pending': True, 'final_integrity_and_render_pending': True, 'final_frozen': False})
print(json.dumps({'draft_sha256': digest, 'body_cjk': counts['actual_body_cjk'], 'responses': 25,
                  'mandatory': 14, 'optional': 11, 'independent_closed': 0, 'old_protected_unchanged': len(protected)}, ensure_ascii=False, indent=2))

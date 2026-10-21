"""从已核验数据生成中文静态报告，不训练、不覆盖任何原始结果。"""
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def esc(value):
    return html.escape(str(value))


def num(value):
    return f'{value:.3e}'


def table(headers, rows):
    return '<div class="scroll"><table><thead><tr>' + ''.join(f'<th>{esc(v)}</th>' for v in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{esc(v)}</td>' for v in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def main():
    data = json.loads((HERE / 'preflight_review.json').read_text(encoding='utf-8'))
    timing = json.loads((HERE / 'batch_timing.json').read_text(encoding='utf-8-sig'))
    old = json.loads((HERE.parent / 'feasibility_review_20261021' / 'existing_data_review.json').read_text(encoding='utf-8'))
    lookup = {(r['tag'], r['方程'], r['方法']): r for r in old['分组汇总']}
    def oldmed(tag, eq, method):
        return lookup[tag, eq, method]['体误差中位数']
    passed = data['建议有限完整确认']
    decision = '可以另行预注册有限完整预算确认；不自动启动大批次。' if passed else '停止自动扩大实验。工程已可运行，当前固定配置未通过效果门。'
    old_rows = []
    for eq in ('E1_heat', 'E3_fisher'):
        ours = oldmed('confirm', eq, 'hardic+layer')
        for method in ('vanilla', 'hardic', 'rba'):
            base = oldmed('confirm', eq, method)
            old_rows.append([eq[:2], method, num(base), num(ours), f'{base/ours:.2f}', '原 confirm，3 种子，固定配置'])
        best_causal = min(oldmed(t, eq, 'hardic') for t in ('causal1', 'causal10'))
        old_rows.append([eq[:2], '因果训练较好档', num(best_causal), num(ours), f'{best_causal/ours:.2f}', 'ε 两档中对基线有利者；E3 未达 3'])
    gate_rows = [[r['方程'][:2], num(r['主候选中位数']), r['最好基线'], num(r['最好基线中位数']), f"{r['主比较倍数']:.2f}", '通过' if r['主比较通过'] else '未通过', f"{r['SOAP叠加倍数']:.2f}", '通过' if r['SOAP叠加通过'] else '未通过'] for r in data['效果门逐项']]
    summaries = [[r['方程'][:2], 'Adam' if r['tag'].endswith('adam') else 'SOAP64', r['方法'], num(r['逐种子']['100']), num(r['逐种子']['101']), num(r['体误差中位数']), num(r['迹误差中位数']), f"{r['达1e-2数']}/2", f"{r['耗时中位数秒']/60:.2f}"] for r in data['方法汇总']]
    repairs = [
        ['评估分支误判', '按 bulk_surface 区分 E4，避免把所有模型的 surface 函数当作独立网络', '新增回归测试，原 43 项保留', '已修复'],
        ['旧 SOAP 与官方算法语义不同', '保留历史实现，另增 soap_official64；固定上游源及 MIT 许可证', 'float32 多步与上游一致；float64 分解不降精度；续跑一致', '已修复，不能混名'],
        ['E4 新模型保存不完整', '新结果同时保存 base 与完整 model.state_dict、元数据及 SHA256；JSON 最后原子发布', 'E1/E4 往返加载、损坏/配置错配拒绝测试', '未来产物已修复'],
        ['旧 E4 表面分支未保存', '保留原记录，标注 v 未从权重复核，排除正式表面定量主张', '20 个旧 PT 确认缺 surf；体/迹已复核', '历史权重无法追回'],
        ['checkpoint 身份/环境不明', '固定镜像源、逐文件 Git blob，隔离 runtime，生成绑定任务工作副本', '四个历史源均通过；两次各 2 步状态逐位一致', '可恢复，完整训练待补'],
        ['损坏结果可能被直接 skip', 'skip 前核配置、任务身份、哈希及完整模型；错误即拒绝', '缺文件/损坏/任务错配/发布失败等测试', '已修复'],
        ['论文与文献表述越界', '重写论文计划；追加历史报告纠正；给半直线层自包含推导', '撤回误差下限、所有基线、统计等价与首次等无证据说法', '已修正，稿件仍待完成'],
    ]
    refrows = [[r['方程'], num(r['N48_N96最大差']), '≤1e−8：通过' if r['通过1e-8'] else '失败'] for r in data['参考解复核']]
    perrun = [[r['方程'][:2], r['tag'], r['方法'], r['种子'], num(r['最大体相对L2']), num(r['最大迹相对误差']), num(r['Adam末次记录损失']), num(r['LBFGS最终记录损失']), f"{r['耗时秒']:.1f}", r['Adam或SOAP参数更新数'], r['LBFGS外层预算累计'], '通过' if r['完整模型校验'] and r['原设置重算通过'] and r['加密设置重算通过'] else '失败'] for r in data['逐结果']]
    maxv = max(r['体误差重算最大差'] for r in data['逐结果'])
    maxt = max(r['迹误差重算最大差'] for r in data['逐结果'])
    counts = {}
    for r in old['逐结果复核']:
        counts[r['tag']] = counts.get(r['tag'], 0) + 1
    countrows = [[tag, counts.get(tag, 0), counts.get(tag, 0)] for tag in ('screen','confirm','axis','causal1','causal10','pirate','e4screen','e4confirm','soap1e3','soap3e3','ic1000')]
    text = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>R33 修复结果与论文准备度</title>
<style>:root{--ink:#173047;--muted:#526678;--line:#dce5ec;--bg:#f3f6f9;--teal:#126b5d;--amber:#8b5309}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.75 "Microsoft YaHei","Noto Sans CJK SC",sans-serif}main{max-width:1240px;margin:auto;padding:42px 28px 64px}h1{font-size:32px;line-height:1.35;margin:8px 0 14px}h2{font-size:23px;margin:0 0 14px}h3{font-size:18px}p{margin:10px 0}.kicker,.small{color:var(--muted);font-size:14px}.lead{font-size:19px}.card{background:white;border:1px solid var(--line);border-radius:12px;padding:24px;margin:22px 0}.status{border-left:5px solid var(--amber)}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.stat{background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px}.stat b{display:block;font-size:27px;color:var(--teal)}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:11px 12px;border-bottom:1px solid var(--line);vertical-align:top}th{background:#edf3f7;white-space:nowrap}tbody tr:last-child td{border-bottom:0}a{color:#155e91;text-decoration:underline;text-underline-offset:3px}li{margin:7px 0}details{margin-top:16px}summary{cursor:pointer;font-weight:bold}code{font-size:13px;background:#edf3f7;padding:2px 5px;border-radius:3px}footer{font-size:13px;color:var(--muted)}@media(max-width:750px){main{padding:24px 14px}.card{padding:18px}.grid{grid-template-columns:repeat(2,1fr)}h1{font-size:26px}}</style><main>
<div class="kicker">R33 · 本机核验 · 2026-10-22（UTC+8）</div><h1>修复结果、是否开跑与论文准备度</h1>'''
    text += f'<p class="lead">{esc(decision)}</p><p>原数据中的 E1/E3 改善成立，但尚不能概括为普遍强于现代 PINN。当前没有达到所拟方法论文的投稿准备度。</p>'
    text += '<div class="grid"><div class="stat"><b>63 / 63</b>完整测试通过</div><div class="stat"><b>130 / 130</b>旧体/迹指标复核</div><div class="stat"><b>24 / 24</b>固定小预算运行完成</div><div class="stat"><b>4 / 4</b>历史 checkpoint 可恢复</div></div>'
    text += '<section class="card status"><h2>判定分开看</h2><p><strong>G0 工程准备：</strong>' + ('通过' if data['G0工程准备通过'] else '未通过') + '；<strong>G1 运行可靠性：</strong>' + ('通过' if data['G1运行可靠性通过'] else '未通过') + '；<strong>G2 效果：</strong>' + ('通过' if data['G2两方程两项均通过'] else '未通过') + '。</p><p>工程修复允许可靠地运行和保存结果；是否值得扩大投入取决于效果门。42 个旧完整基线与 322 个新增调参草案都没有启动；本轮没有搜索学习率、τ 或其他超参数。</p></section>'
    text += '<section class="card"><h2>问题如何处理</h2>' + table(['问题','处理','验证证据','当前状态'], repairs) + '<p class="small">完整测试保留原 43 项并新增 20 项，共 63 passed；一个旧测试的 tensor 转标量警告未影响断言。系统 Python 未替换；专用环境、运行缓存和 checkpoint 都在 D:\\CodexRuntime。</p></section>'
    text += '<section class="card"><h2>新小预算对照：按预注册门槛判</h2><p>两方程 × {Adam、官方语义 SOAP float64 适配} × {vanilla、hardic、hardic+layer} × 种子 100/101，共 24 次。MLP 4×64，单线程每进程、workers=8；优化器梯度调用 4000 次，L-BFGS 至多 500，配点 2048/128/256、固定点 4096/256/512；lr 从 1e−3 降至 1e−5，τ=0.1。无逐方法调参。</p><p>主候选事先固定为 Adam+hardic+layer，不能在 Adam 与 SOAP 修正结果中事后挑更好者。主比较与 SOAP 叠加各要求中位数至少改善 3 倍、两个修正种子都 ≤1e−2，且两方程全部通过才建议有限完整确认。</p>'
    text += table(['方程','固定主候选中位数','最好基线','基线中位数','主比较倍数','主比较','SOAP 叠加倍数','叠加判定'], gate_rows)
    text += '<p>' + '；'.join(esc(f"{r['方程'][:2]}：主候选达标 {r['主候选达1e-2数']}/2，SOAP 叠加候选达标 {r['SOAP叠加候选达1e-2数']}/2") for r in data['效果门逐项']) + '。E1 的 SOAP 叠加虽有倍数收益，仍因一个种子超限而未通过；倍数与绝对误差门都必须满足。</p>'
    text += '<h3>全部方法与两种子结果</h3>' + table(['方程','优化器','方法','seed 100','seed 101','体中位数','迹中位数','≤1e−2','耗时中位数/分'], summaries)
    text += '<p class="small">误差为五个指定时刻最大相对误差；两种子的中位数等于均值。数据只用于投入决策，不进论文正式主表。SOAP 首次调用只初始化，所以 4000 次梯度调用对应 3999 次参数更新；未赠送补偿步数。墙钟受同机并发和任务顺序影响，不据此宣称等墙钟效率优势。</p>'
    text += f'<p>按本机批次日志创建/末次写入时间记录，24 次总墙钟约 {timing["batch_seconds"]/60:.1f} 分钟；单次耗时范围 {min(r["耗时秒"] for r in data["逐结果"])/60:.1f}–{max(r["耗时秒"] for r in data["逐结果"])/60:.1f} 分钟。累计进程训练时间不能当批次墙钟。<a href="batch_timing.json">原时间记录</a>。</p>'
    text += '<details><summary>24 次逐种子指标、损失、耗时及复核</summary>' + table(['方程','tag','方法','种子','体误差','迹误差','Adam末次记录损失','LBFGS终值','秒','参数更新数','LBFGS外层预算','复核'], perrun) + '<p class="small">Adam 损失末次记录在零基步索引 3990，非第 4000 次之后重算；L-BFGS 记录的是已执行预算块，不冒充内部实际迭代或 closure 调用次数，后者未保存。</p></details></section>'
    text += '<section class="card"><h2>结果可复核，不等于效果门通过</h2>' + table(['方程','参考解 N48/N96 最大差','原门槛'], refrows)
    text += f'<p>24 个新完整模型的 SHA256、任务身份和配置均已核验，重新加载后复算体/迹误差，并用 N96、GL400 加密核对。原设置重算最大绝对差：体 {maxv:.3e}，迹 {maxt:.3e}。旧 260 个 JSON/PT 哈希保持不变。</p><details><summary>旧 tag 数量与交接表</summary>' + table(['tag','JSON 数','旧 base PT 数'], countrows) + '<p>合计 130/130，与交接表一致；新 tag 分别增加 12 个 JSON、12 个 base PT 和 12 个完整 model PT，不能混计为旧结果。</p></details></section>'
    text += '<section class="card"><h2>是否比基准 PINN 强</h2><p><strong>对当前已测 E1/E3 的 vanilla、hardic、RBA：有明确数值改善。</strong>下表为旧完整预算三种子，基线中位数除以 MLP+hardic+layer 中位数。它不是逐配对种子共同倍数，也不等于统计显著。</p>' + table(['方程','基线','基线误差','修正误差','倍数','范围'], old_rows)
    text += '<p><strong>对现代强变体：广泛优势尚未成立。</strong>E3 的 MLP+修正对 PirateNet+hardic 仅约 1.47 倍，原 A-1 未满足；在 PirateNet 内叠加修正，E3 中位数改善约 5.52 倍，A-2 仅该方程满足。E1 缺种子 0/1 共四个结果。PirateNet 实现省略物理信息最小二乘初始化，须据实命名。E4 相对 vanilla 的比值约 0.838，不能作为第三个成功泛化例，也不能声称两者统计等价。</p></section>'
    text += '<section class="card"><h2>论文准备度与下一步</h2><p>“比 vanilla 好”满足局部效果证据，却不足以单独支撑当前方法论文。三倍是项目投入门槛，期刊没有统一倍数标准；需要可辨认的贡献、可靠复现、公平比较和与论点匹配的覆盖。</p><ol><li>已修正写作越界：不再宣称误差下限、首次、无参数、优于所有基线。方法称“基于经典角点层分析的修正”；公式及其只硬满足初值的边界写进自包含推导。</li><li>仍缺研究证据：E1 PirateNet 三种子补齐、与目标强基线的完整比较、独立初值/配置、τ 灵敏度和完整开销；小预算不补足这些。先依据失败诊断决定是否值得另行注册有限方案，不自动把缺口转换成大批次。</li><li>仍缺稿件闭环：经典层公式出处逐式对照、相关工作的有界系统检索、完整稿件。Awais 的光滑相容人造解和 SL-PINN 的解析 corrector 已有近邻，不能把组合思想称首次。EDRAS 的表 1 是周期边界；本项目 ic1000 只是受其启发，不能声称完整复现。</li></ol><p>若只写一维限定范围的经验方法短文，不自动要求二维；若主张一般动态边界 PDE 优势，则须有更广证据。最终是否发表取决于目标刊物及真实评审，不给保证。</p><p>建议执行顺序：小预算判定与失败分析 → 另立有限诊断或公平调参方案（若继续）→ 有依据后优先续跑四个现有 PirateNet checkpoint → 有限完整基线确认 → 泛化/灵敏度和成稿。当前不启动 42/322。</p></section>'
    text += '<section class="card"><h2>预注册、偏差与证据入口</h2><p>研究性能试验在提交 <code>c31355c</code> 之后开始。四个 checkpoint 的 16 次工程短更新因第一次提交被上游源码空白检查阻断及编排错误，先于成功提交执行；该偏差已在 24 次研究运行前披露。它只作为事后工程核验，不冒称预注册，也未重跑探针增加预算。旧判据未改、未丢弃失败种子。</p><ul><li><a href="preflight_review.json">机器可读完整核验与判定</a> · <a href="validate_preflight.py">复算程序</a> · <a href="pytest_final.log">63 项测试日志</a></li><li><a href="checkpoint_review.json">checkpoint 来源与恢复检查</a> · <a href="preflight4_adam.log">Adam 批次日志</a> · <a href="preflight4_soap64.log">SOAP 批次日志</a></li><li><a href="../../PAPER_PLAN.md">当前论文计划</a> · <a href="../../METHOD_DERIVATION.md">层函数推导与适用边界</a> · <a href="../../SCREEN_PROTOCOL.md">预注册及修订 4</a></li><li><a href="../feasibility_review_20261021/数据可行性核验.html">前次只读复核</a> · <a href="eic_phase2.txt">独立编辑视角意见</a> · <a href="method_phase2.txt">独立方法视角意见</a> · <a href="review_protocol_status.json">模拟评审输出格式审计</a></li></ul><p class="small">两份独立意见面向改写前材料，仅作定性参考。技能要求的逐条件输出结构未满足，正式模拟评审轮次中止，未生成综合接受/拒绝决定。本报告判断依据可核验数据，不冒称双评审通过。</p><p class="small">原始文献：<a href="https://pisrt.org/psrpress/j/oms/2026/physics-informed-neural-networks-for-the-heat-equation-with-dynamic-wentzell-boundary-conditions.pdf">Awais 2026 §2–4</a> · <a href="https://arxiv.org/html/2312.06278">SL-PINN 2312.06278 §3.2.2</a> · <a href="https://arxiv.org/html/2312.03295">2312.03295 §3.3</a> · <a href="https://arxiv.org/html/2507.09757">EDRAS §3.1–3.3</a>。只核对相关章节，不声称已通读所有文献。</p></section>'
    text += '<footer>所有新结果用独立 tag；原始 130 次不覆盖。工程测试、checkpoint 短验证、小预算效果和正式论文结果各自标明证据层级。</footer></main></html>'
    target = HERE / '修复结果与论文准备度.html'
    target.write_text(text, encoding='utf-8')
    print(target)


if __name__ == '__main__':
    main()

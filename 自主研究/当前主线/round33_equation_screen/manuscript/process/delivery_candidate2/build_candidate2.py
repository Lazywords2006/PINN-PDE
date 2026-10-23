"""只将实际完成的保存权重复算证据纳入新候选稿；旧稿只读。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import difflib

OUT = Path(__file__).resolve().parent
MAN = OUT.parents[1]
ROOT = MAN.parent
BASE = MAN / 'drafts/delivery_candidate.md'
DRAFT = MAN / 'drafts/delivery_candidate2.md'
EVID = ROOT / 'validation/final_numeric_provenance_20261023'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
readj = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

assert not DRAFT.exists(), '新稿已存在，拒绝覆盖。'
assert sha(BASE) == 'aef0c10a1bf19e8703a8066e1f0aaef75600b886777424b9f6545677ccc77eb0'
expected = {
    'FINAL_NUMERIC_REPORT.md': '7657cbb16ec272ace2044bc1300291593dee2973357ced286384374eaabe307c',
    'FINAL_NUMERIC_REPORT.json': 'a13bade9cd7ebc72e37e1f07d856f633b9b60508309e73a7c67cdd2fa872be5d',
    'FINAL_DELIVERY_SHA256.json': 'b8c29c42fc8603b5e0ed865d83b625ac158b0bbf394fd98c7c2b3427a0fe2aae',
}
assert all(sha(EVID / p) == h for p, h in expected.items())
report = readj(EVID / 'FINAL_NUMERIC_REPORT.json')
assert (report['body_trace_result_count'], report['body_trace_scalar_comparisons'], report['heldout_result_count'], report['heldout_scalar_comparisons']) == (206, 4120, 52, 416)
assert report['all_child_actual_returncodes_zero'] and set(report['supervisor_actual_returncodes'].values()) == {0}
assert report['warning_count'] == 0 and not report['nonempty_child_stderr'] and not report['nonempty_supervisor_stderr']
assert report['source_hashes_unchanged'] and report['original_488_hashes_unchanged']
assert report['body_trace_recomputation_pass'] and report['heldout_recomputation_pass']
assert report['restore_status_counts'] == {'legacy_complete':110, 'legacy_bulk_only':20, 'complete':76}
assert all(v == 0 for x in report['heldout_max_abs_differences'].values() for v in x.values())
protected = {str(p): sha(p) for p in (MAN / 'drafts').glob('*.md') if p != DRAFT}
for folder, name in [('complete_revised1', 'FROZEN_REVISION_MANIFEST.json'), ('complete_revised1a', 'FROZEN_LAYOUT_MANIFEST.json')]:
    manifest_path = MAN / 'process' / folder / name
    frozen = readj(manifest_path)
    for p, h in frozen['files'].items():
        assert sha(Path(p)) == h
        protected[p] = h
    protected[str(manifest_path)] = sha(manifest_path)
for p in [MAN / 'PAPER_CONFIGURATION.json', MAN / 'integrity/final_revised1/FINAL_INTEGRITY_REVIEW_CN.md']:
    protected[str(p)] = sha(p)
for p in (MAN / 'reviews/revision1').glob('*'):
    if p.is_file(): protected[str(p)] = sha(p)
for p, h in expected.items(): protected[str(EVID / p)] = h
save('protected_before.json', protected)
base = BASE.read_text(encoding='utf-8')
t = base
changes = []
def replace(issue, old, new):
    global t
    assert t.count(old) == 1, (issue, t.count(old))
    changes.append({'id':issue, 'old':old, 'new':new, 'base_line':base[:base.index(old)].count('\n')+1})
    t = t.replace(old, new)

replace('P01',
    '本文只读重聚合全部结果JSON，未重复模型加载。工程恢复与历史执行范围集中列于附录D。',
    '初稿汇总只读重聚合结果JSON；随后另行重载全部206项，完成两套求积及已有52项独立点残差的实际复算。工程恢复、历史执行范围及本次记录见附录D。')
replace('P02',
    '当前数值一致性与全历史生产链完整性据此分别判断。[E03,E05,E09,E12,E13,E15]',
    '当前数值一致性与全历史生产链完整性据此分别判断。[E03,E05,E09,E12,E13,E15,E18]')
replace('P03', '../process/complete_revised1a/citation_contexts.md', '../process/delivery_candidate2/citation_contexts.md')
replace('P04', '本轮补查未重放176模型，不证明全历史零警告', '该次补查未重放176模型，不证明全历史零警告')
e17 = '| E17 | 首轮修订的参数、采样、E4数据和PirateNet来源 | `../process/complete_revised1/source_evidence.json`及逐项响应 | 定向核对32份已有JSON及相关源码/协议；不重训、不补造历史表面分支 |'
e18 = '| E18 | 2026-10-23保存权重的实际数值复算 | [正式报告](../../validation/final_numeric_provenance_20261023/FINAL_NUMERIC_REPORT.md)、[逐值汇总](../../validation/final_numeric_provenance_20261023/FINAL_NUMERIC_REPORT.json)及[完整清单](../../validation/final_numeric_provenance_20261023/FINAL_DELIVERY_SHA256.json) | 206项体/迹、52项已有残差及本次真实命令、环境、源/输入哈希、输出、退出与警告；不恢复旧训练日志，不补缺失表面权重 |'
replace('P05', e17, e17 + '\n' + e18)
replace('P06',
    '全部206份JSON的当前哈希与正式清单匹配；本次重聚合不等同于重跑全部模型。',
    '全部206份JSON的当前哈希与正式清单匹配；初稿的只读重聚合与随后E18所列保存权重复算分别留档，二者均不重做训练。')
replace('P07', '独立补查对398个结果与权重文件核对当前哈希，而未重新运行176个模型。',
    '先前独立补查对398个结果与权重文件核对当时哈希，而未重新运行176个模型。')
replace('P08', '正式分析仅聚合保存的复算报告，本作者进一步重聚合原始JSON，没有再次重载模型、训练或积分参考解。',
    '初稿阶段的正式分析仅聚合保存的复算报告，作者进一步重聚合原始JSON，彼时没有再次重载模型、训练或积分参考解。')
new_evidence = '''2026-10-23另行完成保存权重的实际数值复算：全部206项在N64/GL200与N96/GL400、五个既定时刻共比较4120个体/迹误差值，保持rtol=10⁻⁵、atol=10⁻⁹，全部在容差内。两套设置对原记录的最大绝对差分别为体1.732×10⁻¹²、迹2.828×10⁻¹²及体1.846×10⁻¹¹、迹4.749×10⁻¹¹。12种方程的参考解均新计算N48、N64与N96；N48/N96在401点及五时刻的自检最大绝对差为3.292×10⁻¹⁰，低于原10⁻⁸阈值。[E18]

同次补核覆盖全部已有52项独立检验点残差记录，即第一阶段4项PirateNet、18项新初值及第二阶段30项。按第3.4节原抽样顺序与点数，重新计算体、左端、右动态边界和初值的RMS与max_abs，共416项，与原记录逐值差均为零。12个参考解、206个体/迹及52个残差子进程，以及两批父进程的真实退出码均为0；本次警告数为0，stderr为空。488个原始JSON/PT及已审源文件哈希保持一致，训练更新数为0。两批核验分别耗时351.939秒与89.846秒，仅表示验证成本。[E18]

本次严格重载覆盖110项旧完整模型、20项旧E4体分支及76项完整产物；缺失的旧E4表面分支明确移除，仍不支持v(t)和表面/交换残差，52项残差复核也不含这些模型。模型前向与参考解调用冻结的项目实现，另写检查器执行严格重载、求积、残差自动微分聚合及逐值比较；因此不是另一套独立PDE求解算法的交叉验证。新进程的命令、环境、源/输入身份、数组、实际退出及警告构成本次证据，不能倒填旧训练退出码、警告、完整源依赖与轨迹。原损失、调用、迭代和训练成本仍按保存字段解释，科学判据及原数值表不变。[E18]

'''
replace('P09', '## 附录E 体表耦合扩展的模型与完整预算数据（不计正文字数）', new_evidence + '## 附录E 体表耦合扩展的模型与完整预算数据（不计正文字数）')
replace('P10', '表E1仅列已有体与迹证据，本轮只读重聚合JSON，没有重载模型，也未将旧v(t)数字补成可复现表面结果。',
    '表E1仅列体与迹证据，首轮修订仅重聚合JSON；随后E18已重载其保存体分支，仍未将旧v(t)数字补成可复现表面结果。')
replace('P11', '早时间的实际解渐近结构及余项正则性仍未由这些五时刻误差证明。[E09,E12,E17]',
    '早时间的实际解渐近结构及余项正则性仍未由这些五时刻误差证明。[E09,E12,E17,E18]')
restored = t
for c in reversed(changes):
    assert restored.count(c['new']) == 1
    restored = restored.replace(c['new'], c['old'])
assert restored == base
DRAFT.write_text(t, encoding='utf-8')
digest = sha(DRAFT)
for c in changes:
    c['new_line'] = t[:t.index(c['new'])].count('\n') + 1
save('change_map.json', {'base_sha256':sha(BASE), 'draft_sha256':digest, 'changes':changes,
    'generated_local':datetime.now(timezone(timedelta(hours=8))).isoformat(),
    'only_authorized_provenance_changes':True, 'final_integrity_status':'PENDING_INDEPENDENT_RECHECK'})
(OUT / 'delivery_candidate_to_candidate2.diff').write_text(''.join(difflib.unified_diff(
    base.splitlines(keepends=True), t.splitlines(keepends=True),
    fromfile='drafts/delivery_candidate.md', tofile='drafts/delivery_candidate2.md')), encoding='utf-8')
assert all(sha(Path(p)) == h for p,h in protected.items())
print(json.dumps({'draft':str(DRAFT), 'sha256':digest, 'edits':len(changes), 'protected':len(protected)}, ensure_ascii=False))

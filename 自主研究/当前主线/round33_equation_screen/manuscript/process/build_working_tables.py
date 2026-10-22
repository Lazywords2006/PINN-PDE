"""Read-only aggregation for the Phase 4b working manuscript; no training."""
from pathlib import Path
import hashlib
import json
import statistics

PROCESS = Path(__file__).resolve().parent
ROOT = PROCESS.parents[1]
TAGS = ['screen', 'confirm', 'causal1', 'causal10', 'pirate', 'axis',
        'e4screen', 'e4confirm', 'final_ic_v1', 'preflight4_adam', 'preflight4_soap64']
old = json.loads((ROOT/'validation/stage5_analysis_20261022/analysis_evidence.json').read_text(encoding='utf-8-sig'))
groups = {}
manifest = []
for tag in TAGS:
    for path in sorted((ROOT/'runs'/tag).glob('*/*.json')):
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        rel = path.relative_to(ROOT).as_posix()
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        assert old['raw_sha256'][rel] == sha, rel
        assert abs(max(data['metrics']['vol'])-data['max_vol']) < 1e-15, rel
        assert abs(max(data['metrics']['trace'])-data['max_trace']) < 1e-15, rel
        key = '/'.join((tag, data['eq'], data['method']))
        groups.setdefault(key, []).append({
            'seed': data['seed'], 'max_vol': data['max_vol'], 'max_trace': data['max_trace'],
            'times': data['metrics']['times'], 'vol': data['metrics']['vol'], 'trace': data['metrics']['trace'],
            'delta': data.get('delta'), 'config': data['config'], 'source': rel, 'sha256': sha})
        manifest.append({'source': rel, 'sha256': sha})
for key, rows in groups.items():
    rows.sort(key=lambda r: r['seed'])
    assert len(set(r['seed'] for r in rows)) == len(rows), key

summary = {}
for key, rows in groups.items():
    summary[key] = {'seeds': [r['seed'] for r in rows], 'vols': [r['max_vol'] for r in rows],
       'median_vol': statistics.median(r['max_vol'] for r in rows),
       'median_trace': statistics.median(r['max_trace'] for r in rows),
       'count_le_1e_2': sum(r['max_vol'] <= 1e-2 for r in rows),
       'delta': rows[0]['delta'], 'sources': [r['source'] for r in rows]}

def table(tag, methods=None):
    lines=['| 问题 | 方法 | seed 0 | seed 1 | seed 2 | 体误差中位数 | 迹误差中位数 | 体≤0.01 |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    for k,s in summary.items():
        t,eq,method=k.split('/')
        if t != tag or (methods and method not in methods): continue
        if s['seeds'] != [0,1,2]: continue
        vals=' | '.join(f'{v:.5e}' for v in s['vols'])
        lines.append(f"| {eq} | {method} | {vals} | {s['median_vol']:.5e} | {s['median_trace']:.5e} | {s['count_le_1e_2']}/3 |")
    return '\n'.join(lines)

tables={tag:table(tag) for tag in ['confirm','final_ic_v1','pirate','e4confirm']}
axis=['| 问题 | δ | hardic中位数 | 修正中位数 | 中位数比 | 修正体≤0.01 | 原点判据 |',
      '|---|---:|---:|---:|---:|---:|---|']
for k,s in summary.items():
    tag,eq,method=k.split('/')
    if method != 'hardic+layer' or tag not in ['axis','confirm']: continue
    h=summary['/'.join((tag,eq,'hardic'))]
    ratio=h['median_vol']/s['median_vol']
    passed=ratio>=3 and s['count_le_1e_2']>=2
    axis.append(f"| {eq} | {s['delta']:.8g} | {h['median_vol']:.5e} | {s['median_vol']:.5e} | {ratio:.5f} | {s['count_le_1e_2']}/3 | {'满足' if passed else '不满足'} |")
tables['axis']='\n'.join(axis)

residuals=['| 问题 | 方法 | 体方程RMS | 左端Neumann RMS | 右端动态边界RMS | 初值RMS |',
           '|---|---|---:|---:|---:|---:|']
heldout_sources={}
for k,g in old['groups'].items():
    if not k.startswith('final_ic_v1/'): continue
    vals=g['heldout_medians']
    residuals.append('| '+g['eq']+' | '+g['method']+' | '+
      ' | '.join(f"{vals[name]['rms']:.5e}" for name in ['pde','left_neumann','right_dynamic','initial'])+' |')
    heldout_sources[k]=vals
tables['heldout']='\n'.join(residuals)

out={'snapshot_source': 'validation/stage5_analysis_20261022/analysis_evidence.json',
     'snapshot_sha256':hashlib.sha256((ROOT/'validation/stage5_analysis_20261022/analysis_evidence.json').read_bytes()).hexdigest(),
     'read_json_count':len(manifest), 'all_hashes_match_snapshot':True,
     'all_maxima_match_sequences':True, 'groups':summary,'rows':groups,'manifest':manifest,
     'heldout_summary_source':'validation/stage5_analysis_20261022/analysis_evidence.json#groups',
     'heldout_medians':heldout_sources}
(PROCESS/'writer_data_evidence.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(PROCESS/'working_tables.md').write_text('\n\n'.join('## '+k+'\n\n'+v for k,v in tables.items())+'\n',encoding='utf-8')
print(json.dumps({'read_json_count':len(manifest),'groups':len(groups),'all_hashes_match_snapshot':True},ensure_ascii=False))

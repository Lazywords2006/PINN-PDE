"""只读核验修订4的固定24次对照；不训练、不选配置、不变更判据。"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import numpy as np
import torch

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT))
from pinn1d import Config
from problems import OUT_TIMES, get_problem, get_reference
from run_artifacts import load_result, sha256
from screen import evaluate, out_path

torch.set_num_threads(1)
torch.set_num_interop_threads(1)
SEEDS = (100, 101)
EQS = ('E1_heat', 'E3_fisher')
METHODS = ('vanilla', 'hardic', 'hardic+layer')
TAGS = {'preflight4_adam': 'adam', 'preflight4_soap64': 'soap_official64'}


def main():
    old = json.loads((OUT.parent / 'feasibility_review_20261021' / 'existing_data_review.json').read_text(encoding='utf-8'))
    unchanged = all((ROOT / name).is_file() and sha256(ROOT / name) == h for name, h in old['SHA256清单'].items())
    if not unchanged:
        raise ValueError('历史结果文件改变，停止汇总')
    expected_paths = {out_path(tag, eq, method, seed) for tag in TAGS for eq in EQS for method in METHODS for seed in SEEDS}
    actual_paths = {p for tag in TAGS for p in (ROOT / 'runs' / tag).rglob('*.json')}
    if actual_paths != expected_paths:
        raise ValueError(f'固定24次尚未齐全或有额外结果: missing={sorted(str(p) for p in expected_paths-actual_paths)}, extra={sorted(str(p) for p in actual_paths-expected_paths)}')

    refs, checks = {}, []
    xcheck = np.linspace(0, 1, 401)
    for eq in EQS:
        refs[eq] = {n: get_reference(get_problem(eq), n) for n in (48, 64, 96)}
        err = max(float(np.max(np.abs(refs[eq][48](xcheck, t) - refs[eq][96](xcheck, t)))) for t in OUT_TIMES)
        checks.append({'方程': eq, 'N48_N96最大差': err, '通过1e-8': err <= 1e-8})

    xx, ww = np.polynomial.legendre.leggauss(400)
    xx, ww = 0.5 * (xx + 1), 0.5 * ww
    rows, groups = [], {}
    for tag, optimizer in TAGS.items():
        for eq in EQS:
            for method in METHODS:
                for seed in SEEDS:
                    path = out_path(tag, eq, method, seed)
                    cfg = replace(Config(), seed=seed, optimizer=optimizer, w_ic=1, t_refine=0)
                    model, rec, status = load_result(path, expected_config=cfg, expected_job=(eq, method, seed, tag))
                    recomputed = evaluate(model, refs[eq][64])
                    low_ok = all(np.allclose(recomputed[k], rec['metrics'][k], rtol=1e-5, atol=1e-9) for k in ('vol', 'trace'))
                    hv, ht = [], []
                    with torch.no_grad():
                        for t in OUT_TIMES:
                            u = model(torch.tensor(xx), torch.full((len(xx),), t)).numpy()
                            u1 = float(model(torch.ones(1), torch.tensor([t]))[0])
                            ur = refs[eq][96](xx, t)
                            r1 = float(refs[eq][96](np.array([1.]), t)[0])
                            hv.append(float(np.sqrt(np.sum(ww * (u - ur)**2) / np.sum(ww * ur**2))))
                            ht.append(abs(u1-r1) / max(abs(r1), 1e-12))
                    high_ok = all(np.allclose(values, rec['metrics'][k], rtol=1e-5, atol=1e-9) for k, values in (('vol', hv), ('trace', ht)))
                    row = {'tag': tag, '方程': eq, '方法': method, '种子': seed,
                           '最大体相对L2': rec['max_vol'], '最大迹相对误差': rec['max_trace'],
                           '体误差序列': rec['metrics']['vol'], '迹误差序列': rec['metrics']['trace'],
                           'Adam末次记录损失': rec['final_adam_loss'], 'LBFGS最终记录损失': rec['final_lbfgs_loss'],
                           '耗时秒': rec['wall_seconds'], 'Adam耗时秒': rec['adam_seconds'],
                           '梯度调用数_Adam或SOAP阶段': cfg.adam_steps,
                           'Adam或SOAP参数更新数': cfg.adam_steps - (optimizer == 'soap_official64'),
                           'LBFGS外层预算累计': (len(rec['history']['lbfgs_loss'])-1)*cfg.lbfgs_chunk,
                           'LBFGS实际内部迭代和closure次数': None,
                           '完整模型校验': status == 'complete', '原设置重算通过': low_ok,
                           '加密设置重算通过': high_ok,
                           '体误差重算最大差': float(np.max(np.abs(np.array(recomputed['vol'])-rec['metrics']['vol']))),
                           '迹误差重算最大差': float(np.max(np.abs(np.array(recomputed['trace'])-rec['metrics']['trace']))),
                           '文件': path.relative_to(ROOT).as_posix(), 'JSON_SHA256': sha256(path), '产物': rec['artifacts']}
                    rows.append(row)
                    groups.setdefault((tag, eq, method), []).append(row)

    summary = []
    for (tag, eq, method), rs in groups.items():
        summary.append({'tag': tag, '方程': eq, '方法': method, '体误差中位数': median(r['最大体相对L2'] for r in rs),
                        '迹误差中位数': median(r['最大迹相对误差'] for r in rs), '耗时中位数秒': median(r['耗时秒'] for r in rs),
                        '达1e-2数': sum(r['最大体相对L2'] <= 1e-2 for r in rs),
                        '逐种子': {str(r['种子']): r['最大体相对L2'] for r in rs}})
    lookup = {(r['tag'], r['方程'], r['方法']): r for r in summary}
    decisions = []
    for eq in EQS:
        primary = lookup['preflight4_adam', eq, 'hardic+layer']
        bases = [lookup[tag, eq, method] for tag in TAGS for method in ('vanilla', 'hardic')]
        best = min(bases, key=lambda r: r['体误差中位数'])
        ratio = best['体误差中位数'] / primary['体误差中位数']
        soap_h = lookup['preflight4_soap64', eq, 'hardic']
        soap_hl = lookup['preflight4_soap64', eq, 'hardic+layer']
        stacking_ratio = soap_h['体误差中位数'] / soap_hl['体误差中位数']
        decisions.append({'方程': eq, '固定主候选': 'Adam+hardic+layer',
                          '主候选中位数': primary['体误差中位数'], '最好基线': f"{best['tag']}+{best['方法']}",
                          '最好基线中位数': best['体误差中位数'], '主比较倍数': ratio,
                          '主候选达1e-2数': primary['达1e-2数'], '主比较通过': ratio >= 3 and primary['达1e-2数'] == 2,
                          'SOAP叠加倍数': stacking_ratio, 'SOAP叠加候选达1e-2数': soap_hl['达1e-2数'],
                          'SOAP叠加通过': stacking_ratio >= 3 and soap_hl['达1e-2数'] == 2})
    cp = json.loads((OUT / 'checkpoint_review.json').read_text(encoding='utf-8'))
    cp_ok = len(cp['检查']) == 4 and all(r['原始Git对象核对'] and r['本机短续跑核验']['重复两次模型优化器采样状态逐位相同'] for r in cp['检查'])
    test_log = (OUT / 'pytest_final.log').read_text(encoding='utf-8-sig')
    g0 = '63 passed' in test_log and cp_ok and unchanged
    g1 = len(rows) == 24 and all(r['完整模型校验'] and r['原设置重算通过'] and r['加密设置重算通过'] for r in rows) and all(r['通过1e-8'] for r in checks)
    g2 = all(r['主比较通过'] and r['SOAP叠加通过'] for r in decisions)
    result = {'生成时间UTC': datetime.now(timezone.utc).isoformat(), '范围': '固定24次、两种子、小预算可行性；不进入论文正式主表',
              '预注册研究运行前提交': 'c31355c082fb19864d536e269f8b6367583d3897',
              '工程探针先于成功提交偏差': '4个checkpoint共16次Adam短更新先运行；已于研究运行前披露，不称其预注册',
              '旧260文件哈希未变': unchanged, 'G0工程准备通过': g0, 'G1运行可靠性通过': g1,
              'G2两方程两项均通过': g2, '建议有限完整确认': g0 and g1 and g2,
              '自动扩展为完整42或322次': False, '结果数': len(rows), '参考解复核': checks,
              '效果门逐项': decisions, '方法汇总': summary, '逐结果': rows,
              '累计训练进程秒_不能当批次墙钟': sum(r['耗时秒'] for r in rows),
              '计数注意': 'Adam损失末次记录为第3990个零基索引步，非训练终点重算；LBFGS只记录外层预算块，内部迭代和closure次数未保存，不冒充实测',
              '环境': {'python': platform.python_version(), 'torch': str(torch.__version__), 'numpy': np.__version__}}
    (OUT / 'preflight_review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('逐结果', '方法汇总')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

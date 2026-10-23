"""Read finished numerical evidence and write a scope-limited delivery report."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import json
import recompute_saved_models as base

HERE=Path(__file__).resolve().parent


def main():
    full=base.read(HERE/'evidence/full/summary.json')
    held=base.read(HERE/'evidence/heldout/summary.json')
    plan=base.read(HERE/'plan.json')
    held_plan=base.read(HERE/'heldout_plan.json')
    source_ok=(not base.verify_hashes(plan['source_sha256'],HERE)
               and not base.verify_hashes(held_plan['source_sha256'],HERE)
               and not base.verify_hashes(held_plan['original_report_sha256'],base.ROOT))
    original_ok=not base.verify_hashes(plan['raw_input_sha256'],base.ROOT)
    artifact_mismatches={batch:base.verify_hashes(base.read(HERE/f'evidence/{batch}/evidence_sha256.json'),HERE/f'evidence/{batch}')
                         for batch in ('probe','full','heldout')}
    stderr_files=sorted((HERE/'evidence/full').rglob('stderr.log'))+sorted((HERE/'evidence/heldout').rglob('stderr.log'))
    supervisors={batch:base.read(HERE/f'supervisors/{batch}/execution.json') for batch in ('full','heldout')}
    reference_rows=[base.read(HERE/'evidence/full/references'/execution['key']/'result.json')
                    for execution in full['reference_executions']]
    identities=Counter(row['restore_status'] for row in full['rows'])
    report={'created_utc':base.utc(),'scope':'2026-10-23 independent execution from saved weights; not reconstructed training history',
            'body_trace_result_count':len(full['rows']),'body_trace_scalar_comparisons':len(full['rows'])*2*2*5,
            'heldout_result_count':len(held['rows']),'heldout_scalar_comparisons':len(held['rows'])*4*2,
            'actual_reference_processes':len(full['reference_executions']),
            'actual_model_processes':len(full['model_executions'])+len(held['executions']),
            'all_child_actual_returncodes_zero':full['all_actual_returncodes_zero'] and held['all_actual_returncodes_zero'],
            'supervisor_actual_returncodes':{k:v['actual_returncode'] for k,v in supervisors.items()},
            'warning_count':full['warning_count']+held['warning_count'],
            'nonempty_child_stderr':[p.relative_to(HERE).as_posix() for p in stderr_files if p.stat().st_size],
            'nonempty_supervisor_stderr':[k for k in supervisors if (HERE/f'supervisors/{k}/stderr.log').stat().st_size],
            'source_hashes_unchanged':source_ok,'original_488_hashes_unchanged':original_ok,
            'evidence_manifest_mismatches':artifact_mismatches,'restore_status_counts':dict(identities),
            'body_trace_recomputation_pass':full['current_numerical_recomputation_pass'],
            'heldout_recomputation_pass':held['current_heldout_recomputation_pass'],
            'reference_N48_N96_worst_max_abs':max(r['selfcheck_max_abs'] for r in reference_rows),
            'body_trace_max_abs_differences':full['max_abs_differences'],
            'heldout_max_abs_differences':held['max_abs_differences'],
            'elapsed_seconds':{'full':full['elapsed_seconds'],'heldout':held['elapsed_seconds']},
            'input_manifest_sha256':base.digest(HERE/'plan.json'),
            'heldout_plan_sha256':base.digest(HERE/'heldout_plan.json'),
            'evidence_summaries_sha256':{k:base.digest(HERE/f'evidence/{k}/summary.json') for k in ('probe','full','heldout')},
            'producer_sha256':{k:base.digest(HERE/k) for k in ('recompute_saved_models.py','recompute_heldout.py','launch_logged.ps1')},
            'excluded':['20 legacy E4 surface predictions and surface/exchange residuals',
                        'old training exit codes, warnings, source binding and optimization trajectories',
                        'new training, hyperparameter selection, universal scientific advantage claims'],
            'final_manuscript_integrity_decision':'reserved to independent final reviewer; numerical match is not full Mode1 acceptance'}
    base.dump(HERE/'FINAL_NUMERIC_REPORT.json',report)
    f=full['max_abs_differences']
    lines=['# 保存权重数值复算：2026-10-23 最终执行报告','',
           '本报告记录本日真实独立执行。它验证当前保存权重下的已报告数值，不恢复旧训练日志，也不改变旧科学判据。','',
           f"- 全部体/迹结果：{len(full['rows'])}/206；逐值容差比较 4120 项。",
           f"- 已有 heldout 记录：{len(held['rows'])}/52；四分量 RMS/max_abs 逐值比较 416 项。",
           '- 体/迹保持 N64/GL200 与 N96/GL400、五个注册时刻；所有数值比较保持 rtol=1e-5、atol=1e-9。',
           f"- 参考解 12 种方程在 N48/N96、401 点、五时刻自检，最坏最大绝对差 {report['reference_N48_N96_worst_max_abs']:.16g}（阈值 1e-8）。",'',
           '| 检查 | 实际记录 |','|---|---|',
           f"| 全部子进程真实退出码为 0 | {report['all_child_actual_returncodes_zero']}；12 参考 + 206 体/迹 + 52 heldout |",
           f"| 父进程真实退出码 | full={supervisors['full']['actual_returncode']}，heldout={supervisors['heldout']['actual_returncode']} |",
           f"| warning 总数 / 非空子进程 stderr 数 | {report['warning_count']} / {len(report['nonempty_child_stderr'])} |",
           f"| 488 原始文件哈希仍一致 | {original_ok} |",
           f"| 已审源 SHA256 仍一致 | {source_ok} |",
           f"| 全部归档证据按清单复核 | {not any(artifact_mismatches.values())} |",
           f"| 体/迹数值复算通过 | {report['body_trace_recomputation_pass']} |",
           f"| heldout 数值复算通过 | {report['heldout_recomputation_pass']} |",'',
           '| 误差对原记录的最大绝对差 | 体 | 迹 |','|---|---:|---:|',
           f"| N64/GL200 | {f['n64_gl200']['vol']:.16g} | {f['n64_gl200']['trace']:.16g} |",
           f"| N96/GL400 | {f['n96_gl400']['vol']:.16g} | {f['n96_gl400']['trace']:.16g} |",'',
           '| heldout 对原记录的最大绝对差 | RMS | max_abs |','|---|---:|---:|']
    lines += [f"| {component} | {values['rms']:.16g} | {values['max_abs']:.16g} |"
              for component,values in held['max_abs_differences'].items()]
    lines += ['',f"全206批次耗时 {full['elapsed_seconds']:.3f} 秒；heldout52批次耗时 {held['elapsed_seconds']:.3f} 秒。两批顺序运行，每批最多8个单线程进程；训练更新数为0。",'',
              f"恢复范围：{dict(identities)}。20个旧E4只核体/迹，缺失surf分支明确移除；v(t)与表面/交换残差继续不可核。",'',
              '模型前向与参考解调用已冻结项目实现；新写并独立审查的是严格重载、求积/残差聚合、逐值对照及执行证据链。这不能解释为另一套独立PDE求解器的全方法验证。',
              '旧训练退出码、警告、完整源依赖与轨迹未被追回；本次真实新记录不能填造历史记录。最终稿件完整性/Mode1裁定由独立最终核验者另行给出。','',
              '完整身份见 `plan.json`、`heldout_plan.json`；原始命令/版本/源和输入hash/数组/逐值差异/退出/警告均在 `evidence/full` 与 `evidence/heldout`，父进程记录在 `supervisors`。',
              '所有文件从D盘真实运行目录复制后按SHA256核对；原表、原指标与原JSON/PT没有改写。','']
    (HERE/'FINAL_NUMERIC_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()

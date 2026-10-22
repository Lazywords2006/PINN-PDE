"""只读收集复现说明的来源和CLI证据；只写本目录，不导入Torch、不训练。"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone, timedelta
from importlib.metadata import distributions
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

OUT = Path(__file__).resolve().parent
MAN = OUT.parents[1]
ROOT = MAN.parent
RUNTIME = Path(r'D:\CodexRuntime\runs\r33_stage6_20261022')
ANALYSIS_PYTHON = Path(r'D:\CodexRuntime\venvs\r33-analysis\Scripts\python.exe')
FROZEN_DRAFT = MAN/'drafts/working_revised1.md'
FROZEN_SHA = '7ca430d7911dda4507469099e493dc2563ef48dff0157b4df862e4ab8f3b3635'

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def readj(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def writej(name,obj):
    target=OUT/name
    assert target.parent == OUT
    target.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

assert Path(r'D:\CodexRuntime').is_dir()
assert digest(FROZEN_DRAFT.read_bytes()) == FROZEN_SHA
assert 'torch' not in sys.modules
observed = datetime.now(timezone(timedelta(hours=8)))
source_names = [
 'SCREEN_PROTOCOL.md','pinn1d.py','problems.py','screen.py','run_artifacts.py','soap_baseline.py',
 'stage5_support.py','stage6_runner.py','test_stage6_runner.py','run_stage6.ps1','run_stage5.ps1','run_preflight.ps1',
 'validation/stage5_analysis_20261022/analysis_evidence.json',
 'validation/feasibility_review_20261021/existing_data_review.json',
 'validation/resolution_20261022/preflight_review.json','validation/resolution_20261022/validate_preflight.py',
 'validation/stage5_20261022/pirate_validation.json','validation/stage5_20261022/ic_validation.json',
 'validation/stage5_20261022/completion.json','validation/stage6_20261022/engineering_gate.json',
 'validation/stage6_20261022/task_plan.json','validation/stage6_20261022/soap_upstream_blob.json',
 'validation/stage6_recovery_20261023/RECOVERY_ROUTE.md',
 'validation/stage6_recovery_20261023/INDEPENDENT_RECOVERY_REVIEW.md',
 'validation/stage6_recovery_20261023/v2/engineering_repair_evidence.json',
 'validation/stage6_recovery_20261023/v2/INDEPENDENT_RECOVERY_REVIEW.md',
 'validation/stage6_recovery_20261023/v2/INDEPENDENT_RECOVERY_REVIEW.json',
 'validation/stage6_recovery_20261023/incident_snapshot_20261023_013453_945/snapshot_manifest.json',
 'validation/stage6_analysis_20261022/README.md','validation/stage6_analysis_20261022/analyze_stage6.py',
 'validation/stage6_analysis_20261022/plot_stage6.py','manuscript/render_manuscript.py',
 'manuscript/README.md','manuscript/process/writer_data_evidence.json',
 'manuscript/integrity/working_20261023/HISTORICAL_EXECUTION_SCOPE.md',
 'manuscript/integrity/working_20261023/historical_execution_scope.json',
 'manuscript/integrity/working_20261023/REVISED1_FOLLOWUP_CN.md',
 'manuscript/integrity/working_20261023/revised1_followup.json',
 'manuscript/drafts/working_revised1.md',
]
source_bytes={name:(ROOT/name).read_bytes() for name in source_names}
sources={name:{'absolute_path':str(ROOT/name),'sha256':digest(raw),'bytes':len(raw)} for name,raw in source_bytes.items()}
cli={}
for name in ['stage6_runner.py','screen.py','validation/stage6_analysis_20261022/analyze_stage6.py','manuscript/render_manuscript.py']:
    tree=ast.parse(source_bytes[name].decode('utf-8-sig'))
    declarations=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in ('add_argument','add_parser'):
            names=[a.value for a in node.args if isinstance(a,ast.Constant) and isinstance(a.value,str)]
            if names:
                options={}
                for keyword in node.keywords:
                    try: options[keyword.arg]=ast.literal_eval(keyword.value)
                    except (ValueError,TypeError): options[keyword.arg]=ast.unparse(keyword.value)
                declarations.append({'line':node.lineno,'call':node.func.attr,'names':names,'options':options})
    cli[name]={'source_sha256':sources[name]['sha256'],'declarations':sorted(declarations,key=lambda x:x['line'])}

expected_cli={
 'stage6_runner.py':{'--worker','--runtime','--set','--gate','--run','--plan','--status','--workers','--recovery-manifest','--retry-failed-job','--resource-review-note'},
 'screen.py':{'run','report','--eqs','--methods','--seeds','--workers','--set','--tag'},
 'validation/stage6_analysis_20261022/analyze_stage6.py':{'--partial','--final','--output'},
 'manuscript/render_manuscript.py':{'source','--output','--label','--pdf'},
}
for name,expected in expected_cli.items():
    actual={a for d in cli[name]['declarations'] for a in d['names']}
    assert expected<=actual,(name,expected-actual)

plan=json.loads(source_bytes['validation/stage6_20261022/task_plan.json'].decode('utf-8-sig'))
expected_jobs={(tag,eq,'hardic+layer',seed) for tag in ('sensitivity_tau003_v1','sensitivity_tau03_v1')
               for eq in ('E1_heat','E3_fisher') for seed in (0,1,2)}
expected_jobs|={('final_soap64_v1',eq,method,seed) for eq in ('E1_heat','E3_fisher')
                for method in ('vanilla','hardic','hardic+layer') for seed in (0,1,2)}
assert len(plan['jobs'])==30 and {tuple(r['job']) for r in plan['jobs']}==expected_jobs
plan_checks=[]
for row in plan['jobs']:
    cmd=row['command']
    assert Path(cmd[0])==Path(r'D:\CodexRuntime\venvs\r33-torch214\Scripts\python.exe')
    assert cmd[1]=='-u' and Path(cmd[2])==ROOT/'stage6_runner.py'
    assert cmd[3]=='--worker' and cmd[4:8]==[str(x) for x in row['job']]
    assert cmd[8]=='--runtime' and Path(cmd[9])==RUNTIME
    overrides={}
    tail=cmd[10:]
    assert len(tail)%2==0
    for i in range(0,len(tail),2):
        assert tail[i]=='--set'
        k,v=tail[i+1].split('=',1)
        assert k not in overrides
        overrides[k]=v
    assert set(overrides)==set(row['config'])
    for k,v in row['config'].items():
        raw=overrides[k]
        if isinstance(v,(int,float)) and not isinstance(v,bool): assert float(raw)==v,(k,raw,v)
        else: assert raw==str(v),(k,raw,v)
    plan_checks.append({'job':row['job'],'argv_matches_declared_interface':True,
        'override_fields':len(overrides),'all_serialized_overrides_match_frozen_config':True})

old=json.loads(source_bytes['manuscript/process/writer_data_evidence.json'].decode('utf-8-sig'))
old_main=json.loads(source_bytes['validation/stage5_analysis_20261022/analysis_evidence.json'].decode('utf-8-sig'))
tag_counts=dict(Counter(x['source'].split('/')[1] for x in old['manifest']))
assert sum(tag_counts.values())==176 and len(old_main['raw_sha256'])==398
v2=json.loads(source_bytes['validation/stage6_recovery_20261023/v2/INDEPENDENT_RECOVERY_REVIEW.json'].decode('utf-8-sig'))

# 读取包元数据而非导入包；它与工程门的实际运行环境分别记录。
environments={}
for name in ('r33-torch214','r33-analysis'):
    path=Path(r'D:\CodexRuntime\venvs')/name
    metadata={}
    for dist in distributions(path=[str(path/'Lib/site-packages')]):
        label=dist.metadata['Name']
        if label.lower().replace('-','_') in {'torch','numpy','scipy','matplotlib','pypandoc_binary','pymupdf','pytest','mpmath'}:
            metadata[label]=dist.version
    raw=(path/'pyvenv.cfg').read_bytes()
    environments[name]={'path':str(path),'pyvenv_cfg':raw.decode('utf-8'),'pyvenv_cfg_sha256':digest(raw),
        'installed_distribution_metadata':metadata,'packages_imported_for_version_check':False}

# 此子进程只执行已读源码的 --partial 路线，并记录执行后Torch未进入模块表。
analysis=ROOT/'validation/stage6_analysis_20261022/analyze_stage6.py'
wrapper = r'''
import contextlib,io,json,runpy,sys
source=sys.argv[1]
sys.argv=[source,'--partial']
class Capture(io.StringIO):
    def reconfigure(self, **kwargs):
        assert set(kwargs)<= {'encoding'}
buffer=Capture()
exit_code=0
with contextlib.redirect_stdout(buffer):
    try: runpy.run_path(source,run_name='__main__')
    except SystemExit as exc: exit_code=exc.code or 0
assert 'torch' not in sys.modules, 'partial意外导入Torch'
assert exit_code==0, exit_code
print(json.dumps({'exit_code':exit_code,'torch_in_sys_modules':False,'partial_output':json.loads(buffer.getvalue())},ensure_ascii=False))
'''
env=dict(os.environ,TEMP=r'D:\CodexRuntime\temp',TMP=r'D:\CodexRuntime\temp',
    PYTHONPYCACHEPREFIX=r'D:\CodexRuntime\cache\pycache',PYTHONDONTWRITEBYTECODE='1',
    PYTHONUTF8='1',PYTHONIOENCODING='utf-8',MPLCONFIGDIR=r'D:\CodexRuntime\cache\matplotlib',
    XDG_CACHE_HOME=r'D:\CodexRuntime\cache\xdg')
completed=subprocess.run([str(ANALYSIS_PYTHON),'-c',wrapper,str(analysis)],cwd=ROOT,env=env,
                         capture_output=True,text=True,encoding='utf-8',timeout=40)
assert completed.returncode==0,completed.stderr
partial=json.loads(completed.stdout)
partial['captured_local']=observed.isoformat()
partial['source_sha256']=sources['validation/stage6_analysis_20261022/analyze_stage6.py']['sha256']
partial['execution_note']='runpy以__main__和--partial执行同一CLI路线，捕获stdout并检查Torch未导入；未执行--final。'
partial['stderr']=completed.stderr
writej('read_only_partial_snapshot.json',partial)

missing_outputs={}
for name in ['validation/stage6_20261022/results_validation.json','validation/stage6_20261022/summary.json',
             'validation/stage6_analysis_20261022/analysis_evidence.json','manuscript/drafts/complete_v1.md']:
    path=ROOT/name
    missing_outputs[name]={'exists_at_snapshot':path.exists(),'sha256':digest(path.read_bytes()) if path.is_file() else None}

changes=[name for name in source_names if digest((ROOT/name).read_bytes())!=sources[name]['sha256']]
assert not changes,('读取期间来源变化，重新收集后再发布本说明',changes)
assert digest(FROZEN_DRAFT.read_bytes())==FROZEN_SHA
assert 'torch' not in sys.modules

snapshot_string=observed.strftime('%Y-%m-%d %H:%M:%S')
for name in ['REPRODUCIBILITY_CN.md','DATA_DICTIONARY_CN.md']:
    path=OUT/name
    text=path.read_text(encoding='utf-8').replace('{{SNAPSHOT_LOCAL}}',snapshot_string)
    text=re.sub(r'(?<=编写快照时间为 `)\d{4}-\d\d-\d\d \d\d:\d\d:\d\d',snapshot_string,text)
    text=re.sub(r'(?<=版本快照：`)\d{4}-\d\d-\d\d \d\d:\d\d:\d\d',snapshot_string,text)
    path.write_text(text,encoding='utf-8')

ps_shell=shutil.which('pwsh') or shutil.which('powershell')
assert ps_shell, '找不到已有PowerShell，不安装替代依赖'
ps_result=subprocess.run([ps_shell,'-NoProfile','-NonInteractive','-File',str(OUT/'audit_powershell_cli.ps1'),
                          '-ProjectRoot',str(ROOT)],capture_output=True,text=True,encoding='utf-8',timeout=40)
assert ps_result.returncode==0,ps_result.stderr
ps_audit=json.loads(ps_result.stdout)
writej('powershell_cli_audit.json',ps_audit)

audit={'schema':'r33_reproducibility_source_and_command_snapshot_v1','captured_local':observed.isoformat(),
    'status':'在途复现材料；最终30/30后再次核对并定稿','source_files':sources,'cli_static_audit':cli,
    'powershell_cli_static_audit':ps_audit,
    'plan_cli_audit':{'plan_tasks':30,'exact_expected_job_set':True,'job_checks':plan_checks,
        'worker_commands_executed':False,'source':'validation/stage6_20261022/task_plan.json'},
    'counts':{'existing_result_records':176,'existing_tag_counts':tag_counts,'existing_manifest_files':398,
        'new_planned_records':30,'new_complete_bundle_expected_files':90,'eventual_expected_manifest_files':488,
        'new_counts_are_plan_not_acceptance':True},
    'environment_metadata_only':environments,
    'engineering_gate_runtime_environment':json.loads(source_bytes['validation/stage6_20261022/engineering_gate.json'].decode('utf-8-sig'))['environment'],
    'recovery_v2_snapshot':{'overall':v2['overall'],'full_regression_status':v2['full_regression_status'],
        'recovery_dispatch_allowed':v2['recovery_dispatch_allowed'],'scientific_acceptance':v2['scientific_acceptance']},
    'formal_outputs_observed':missing_outputs,'frozen_working_draft_unchanged':True,'frozen_working_draft_sha256':FROZEN_SHA,
    'operations':{'training_runs':0,'model_loads':0,'reference_integrations':0,'dependency_installs':0,
        'torch_imported':False,'formal_aggregation_runs':0,'render_runs':0,'read_only_partial_runs':1},
    'side_effect_boundaries':{'writes':'仅manuscript/process/reproducibility当前目录','modified_scientific_or_training_sources':False,
        'old_398_rehashed_in_this_document_task':False,'note':'旧398来源由已有独立哈希核验支持；本次核清单计数和来源hash，不重复读取全部权重。'},
    'source_files_changed_during_collection':changes}
writej('source_and_command_audit.json',audit)

checks=[]
for name in ['REPRODUCIBILITY_CN.md','DATA_DICTIONARY_CN.md','AI_USE_STATEMENT_N03_CN.md']:
    path=OUT/name
    text=path.read_text(encoding='utf-8')
    assert '{{SNAPSHOT_LOCAL}}' not in text
    assert text.count('```')%2==0
    links=re.findall(r'\]\((E:/[^\n)]+)\)',text)
    assert all(Path(link).exists() for link in links),(name,[link for link in links if not Path(link).exists()])
    expected_columns=None
    for line in text.splitlines():
        if line.startswith('|'):
            count=line.count('|')
            if expected_columns is None: expected_columns=count
            assert count==expected_columns,(name,line)
        else: expected_columns=None
    checks.append({'file':name,'sha256':digest(path.read_bytes()),'local_links':len(links),
                   'all_local_link_targets_exist':True,'code_fences_paired':True,'table_columns_consistent':True})
writej('reproducibility_checks.json',{'captured_local':observed.isoformat(),'documents':checks,
    'all_30_worker_argv_checked_statically':True,'partial_cli_exit_code':0,'partial_cli_did_not_import_torch':True,
    'powershell_wrappers_parsed':3,'documentation_command_blocks_parsed_not_executed':4,
    'frozen_draft_unchanged':True,'source_snapshot_stable_during_collection':True,
    'state':'文档与有限命令/来源检查完成；非训练或完整研究验收'})
print(json.dumps({'output':str(OUT),'snapshot_local':observed.isoformat(),'documents':[x['file'] for x in checks],
    'sources_bound':len(sources),'frozen_draft_unchanged':True,'worker_commands_checked_not_run':30,
    'partial_exit_code':0,'torch_imported':False,'recovery_v2':v2['overall']},ensure_ascii=False,indent=2))

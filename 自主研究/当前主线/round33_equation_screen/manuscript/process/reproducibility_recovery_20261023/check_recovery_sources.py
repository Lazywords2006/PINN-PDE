"""一次性静态绑定恢复复现材料；仅写本目录，不执行实验/分析/Gate。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter
import ast
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
REPO=ROOT.parents[2]
REC='validation/stage6_recovery_20261023/'
STAGE='validation/stage6_20261022/'
PRIOR='bb7250d65bfee8b44858c2ae734e540eee0bf7d26e2d5a68bbc2b7d40ff6e898'
CURRENT='4572088adf9eb3010c4d483b6ae71a82087dd5bd41b35dcb38e0687f5666d6e3'
FROZEN='7ca430d7911dda4507469099e493dc2563ef48dff0157b4df862e4ab8f3b3635'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
readj=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def save(name,value):
    assert (OUT/name).parent==OUT
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def git(*args):
    return subprocess.run(['git',*args],cwd=REPO,check=True,capture_output=True).stdout

assert not (OUT/'recovery_static_evidence.json').exists(),'既有核对证据不可被重跑覆盖。'
observed=datetime.now(timezone(timedelta(hours=8)))
gate=readj(ROOT/(STAGE+'engineering_gate.json'))
source_names=list(gate['source_hashes'])+[
    STAGE+'engineering_gate.json',STAGE+'task_plan.json',STAGE+'pytest.xml',
    REC+'RECOVERY_ROUTE.md',REC+'recovery_manifest.json',
    REC+'recovery_gate_success/engineering_gate.json',REC+'recovery_gate_success/archive_manifest.json',
    REC+'recovery_gate_success/pytest.xml',
    REC+'recovery_dispatch/dispatch_evidence.json',REC+'recovery_dispatch/status_observation_20261023_045714.json',
    REC+'original21_archive.json',REC+'original21_git_blob_checks.json',
    REC+'regression_fixture_repair/INDEPENDENT_REVIEW.json',REC+'timezone_binding_repair/INDEPENDENT_REVIEW.json',
    'validation/stage6_analysis_20261022/analyze_stage6.py','validation/stage6_analysis_20261022/plot_stage6.py',
    'validation/stage6_analysis_20261022/test_analysis.py','validation/stage6_analysis_20261022/precompletion_20261023_checks.json',
    'manuscript/drafts/working_revised1.md']
source_names += [p.relative_to(ROOT).as_posix() for p in (ROOT/'manuscript/process/reproducibility').iterdir() if p.is_file()]
lineage=gate['recovery_lineage']
source_names += [Path(v['path']).relative_to(ROOT).as_posix() for v in lineage['artifacts'].values()]
source_names=list(dict.fromkeys(source_names))
raw={name:(ROOT/name).read_bytes() for name in source_names}
sources={name:{'absolute_path':str(ROOT/name),'sha256':sha(data),'bytes':len(data)} for name,data in raw.items()}
assert sources[STAGE+'engineering_gate.json']['sha256']==CURRENT
assert sources[REC+'recovery_gate_success/engineering_gate.json']['sha256']==CURRENT
assert gate['passed'] is True and len(gate['tasks'])==30
assert all(sources[name]['sha256']==digest for name,digest in gate['source_hashes'].items())
assert lineage['prior_gate_sha256']==PRIOR and lineage['training_and_protocol_unchanged'] is True
changed=[name for name,digest in gate['source_hashes'].items() if digest!=lineage['prior_source_hashes'][name]]
assert set(changed)=={'stage6_runner.py','test_stage6_runner.py'}
assert all(sha(Path(v['path']).read_bytes())==v['sha256'] for v in lineage['artifacts'].values())
assert sources[REC+'recovery_manifest.json']['sha256']==lineage['manifest']['sha256']
assert len(lineage['reconciled'])==21
assert all(row[role]['exit_code']==0 and row[role]['identity_verified'] is True for row in lineage['reconciled'] for role in ('launcher','worker'))
xml=ET.fromstring(raw[STAGE+'pytest.xml'])
suites=list(xml.iter('testsuite'))
test_counts={key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}
assert test_counts=={'tests':110,'failures':0,'errors':0,'skipped':0}
assert sources[STAGE+'pytest.xml']['sha256']==gate['runner_tests']['junit_sha256']
assert raw[STAGE+'pytest.xml']==raw[REC+'recovery_gate_success/pytest.xml']

observation=readj(ROOT/(REC+'recovery_dispatch/status_observation_20261023_045714.json'))
state=observation['status']
dispatch=readj(ROOT/(REC+'recovery_dispatch/dispatch_evidence.json'))
archive=readj(ROOT/(REC+'original21_archive.json'))
blob_checks=readj(ROOT/(REC+'original21_git_blob_checks.json'))
oldjobs={tuple(j) for j in lineage['original_active_jobs']}
newjobs={tuple(j) for j in gate['tasks']}-oldjobs
assert len(oldjobs)==21 and len(newjobs)==9 and state['counts']=={'queued':0,'running':9,'completed':21,'failed':0}
assert all(observation['checks'].values()) and dispatch['original_completed_and_recomputed']==21
assert dispatch['new_gate_sha256']==CURRENT and state['current_gate_sha256']==CURRENT
assert dispatch['runner_pid']==state['runner_pid']==91632 and dispatch['runner_launcher_pid']==25644
assert dispatch['original_deadline_unix']==state['review_deadline_unix']
prior_state=readj(Path(lineage['artifacts']['prior_status']['path']))
assert prior_state['review_deadline_unix']==state['review_deadline_unix']
# deadline原始float跨恢复逐值相同；ISO首发时间仅微秒精度，此处不以浮点相减的末位舍入宣告期限改变。
duration_from_iso=state['review_deadline_unix']-datetime.fromisoformat(state['first_started_utc']).timestamp()
assert abs(duration_from_iso-172800)<1e-6
assert {tuple(row['job']) for row in state['tasks']}==oldjobs|newjobs
assert {tuple(j) for j in archive['jobs']}==oldjobs
assert len(archive['files'])==63 and len({v['path'] for v in archive['files']})==63
assert archive['status_observation_sha256']==sources[REC+'recovery_dispatch/status_observation_20261023_045714.json']['sha256']
assert dispatch['archived_status_sha256']==archive['status_observation_sha256']
assert blob_checks['files']==blob_checks['matched']==63 and blob_checks['all_match'] is True
assert blob_checks['archive_manifest_sha256']==sources[REC+'original21_archive.json']['sha256']
bundle_map={row['path']:row['sha256'] for row in archive['files']}
task_rows=[]
plan=readj(ROOT/(STAGE+'task_plan.json'))
configs={tuple(row['job']):row['config'] for row in plan['jobs']}
for row in state['tasks']:
    job=tuple(row['job'])
    original=job in oldjobs
    assert len(row['attempts'])==1
    attempt=row['attempts'][0]
    assigned_gate=PRIOR if original else CURRENT
    assert attempt['source_gate_sha256']==assigned_gate
    assert row['config']==configs[job]
    assert attempt['resume_checkpoint_present'] is False
    if original:
        assert row['state']=='completed' and row['validation']['complete_and_recomputed'] is True
        assert attempt['exit_code']==attempt['worker_exit_code']==0
        prefix=f'runs/{job[0]}/{job[1]}/'
        assert all(bundle_map[prefix+name]==digest for name,digest in row['validation']['bundle_sha256'].items())
    else:
        assert row['state']=='running' and 'validation' not in row
    task_rows.append({'job':row['job'],'source_group':'original21' if original else 'remaining9',
        'state_at_archived_observation':row['state'],'attempt_count':1,'source_gate_sha256':assigned_gate,
        'runner_sha256':lineage['prior_source_hashes']['stage6_runner.py'] if original else gate['source_hashes']['stage6_runner.py'],
        'config_sha256_canonical_json':sha(json.dumps(row['config'],sort_keys=True,separators=(',',':')).encode()),
        'complete_and_recomputed_at_observation':True if original else None,
        'resume_checkpoint_present':False})
assert len(state['source_lineage'])==2
for item in state['source_lineage']:
    expected=oldjobs if item['role']=='original_workers' else newjobs
    assert {tuple(j) for j in item['jobs']}==expected

commits={key:git('rev-parse',key).decode().strip() for key in ('352af9c','2a42ded','0ccc65a')}
paths={p.decode('utf-8') for p in git('diff-tree','--no-commit-id','--name-only','-r','-z','0ccc65a').split(b'\0') if p}
assert {r['repository_path'] for r in archive['files']}<=paths
archive_git_path=(ROOT/(REC+'original21_archive.json')).relative_to(REPO).as_posix()
checks_git_path=(ROOT/(REC+'original21_git_blob_checks.json')).relative_to(REPO).as_posix()
assert git('show','0ccc65a:'+archive_git_path)==raw[REC+'original21_archive.json']
assert git('show','0ccc65a:'+checks_git_path)==raw[REC+'original21_git_blob_checks.json']

analysis_name='validation/stage6_analysis_20261022/analyze_stage6.py'
ast_sources=['stage6_runner.py','test_stage6_runner.py',analysis_name]
trees={name:ast.parse(raw[name].decode('utf-8-sig')) for name in ast_sources}
analysis_tree=trees[analysis_name]
cli=[]
for node in ast.walk(analysis_tree):
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='add_argument':
        cli.extend(arg.value for arg in node.args if isinstance(arg,ast.Constant) and isinstance(arg.value,str))
assert set(cli)=={'--partial','--final','--output'}
analysis_text=raw[analysis_name].decode('utf-8-sig')
assert 'Adam/SOAP末次记录损失' in analysis_text and 'history.adam_gradient_calls在第一阶段成功完成后按cfg.adam_steps写入' in analysis_text
assert sources['manuscript/drafts/working_revised1.md']['sha256']==FROZEN
assert 'torch' not in sys.modules

deadline=datetime.fromtimestamp(state['review_deadline_unix'],timezone(timedelta(hours=8))).isoformat()
replacements={'{{CHECKED_LOCAL}}':observed.isoformat(),'{{DEADLINE_LOCAL}}':deadline,'{{ANALYSIS_SHA}}':sources[analysis_name]['sha256']}
documents=[]
for name in ['RECOVERY_REPRODUCIBILITY_CN.md','FINAL_REFRESH_FIELDS_CN.md']:
    p=OUT/name
    text=p.read_text(encoding='utf-8')
    for old,new in replacements.items(): text=text.replace(old,new)
    assert '{{' not in text
    p.write_text(text,encoding='utf-8')
    links=re.findall(r'\]\((E:/[^\n)]+)\)',text)
    assert all(Path(link).exists() for link in links)
    columns=None
    for line in text.splitlines():
        if line.startswith('|'):
            current=line.count('|')
            if columns is None: columns=current
            assert columns==current,(name,line)
        else: columns=None
    documents.append({'file':name,'sha256':sha(p.read_bytes()),'links_exist':True,'table_columns_consistent':True})
assert all(sha((ROOT/name).read_bytes())==entry['sha256'] for name,entry in sources.items())
save('source_lineage.json',{'scope':'已归档04:57:14状态的30任务来源映射；不是实时进度或最终科学验收',
    'observation_utc':observation['observed_utc'],'observation_sha256':sources[REC+'recovery_dispatch/status_observation_20261023_045714.json']['sha256'],
    'current_gate_sha256':CURRENT,'prior_gate_sha256':PRIOR,'tasks':task_rows})
evidence={'schema':'r33_recovery_reproducibility_supplement_v1','checked_local':observed.isoformat(),
    'scope':'一次轻量静态来源/身份/元数据核对；复用已完成验收证据，未作新数值验证',
    'sources':sources,'commits':commits,'checks':{
        'current_gate_sha256':CURRENT,'all_12_gate_sources_match_current_files':True,'only_runner_and_test_differ_from_original_gate':changed,
        'recovery_manifest_and_7_artifact_hashes_match':True,'reconciled_zero_exit_observations':42,
        'gate_pytest_xml_counts':test_counts,'original21_complete_and_recomputed_in_saved_observation':True,
        'original21_archive_files':63,'archive_map_matches_saved_validation_bundles':True,
        'existing_git_blob_check':'已保存63/63检查及其归档清单哈希匹配；本次未重复读取63原始产物字节',
        'archive_commit_contains_all_63_paths':True,'archive_and_check_json_equal_committed_bytes':True,
        'remaining9_source_lineage_and_first_attempts_bound':True,'all_30_configs_match_frozen_plan':True,
        'original_48_hour_deadline_unchanged':True,'deadline_local':deadline,
        'parsed_ast_without_import':ast_sources,'analysis_cli':cli,'old_reproducibility_directory_and_frozen_draft_unchanged':True,
        'all_bound_sources_unchanged_during_check':True},
    'operations':{'training_runs':0,'torch_imports':0,'active_checkpoint_reads':0,'model_loads':0,
        'numerical_recomputations':0,'gate_runs':0,'partial_analysis_runs':0,'final_analysis_runs':0,'runtime_status_reads':0,
        'old398_or_new63_result_files_rehashed':False,'git_operations':'read-only metadata and two committed evidence JSONs'},
    'final_30_acceptance':'PENDING','documents':documents}
save('recovery_static_evidence.json',evidence)
print(json.dumps({'output':str(OUT),'files':[p.name for p in OUT.iterdir() if p.is_file()],
    'source_files_bound':len(sources),'checks':'passed within stated static scope',
    'analysis_sha256':sources[analysis_name]['sha256'],'final_30_acceptance':'PENDING'},ensure_ascii=False,indent=2))

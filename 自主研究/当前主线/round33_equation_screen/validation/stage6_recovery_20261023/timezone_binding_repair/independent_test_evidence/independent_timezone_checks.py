"""Independent time-binding tests and immutable real-manifest probe.
Only AST-extracted production definitions execute; no Torch, Gate, Run or training.
"""
import ast
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import runpy
import sys
import types
import pytest
ROOT=Path(r'E:\PINN-PDE\自主研究\当前主线\round33_equation_screen')
ns=runpy.run_path(str(ROOT/'validation/stage6_recovery_20261023/v2/preflight_checks.py'))
s=ns['s']
recovery_fixture=ns['recovery_fixture']
s.__dict__.update(re=re,math=math)
source=ast.parse((ROOT/'stage6_runner.py').read_text(encoding='utf-8'))
constants={'DEFAULT_RUNTIME','TRAINING_FILES','SOURCE_FILES'}
nodes=[n for n in source.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in constants for t in n.targets)]
assert len(nodes)==3
exec(compile(ast.Module(body=nodes,type_ignores=[]),'production-source-constants','exec'),s.__dict__)
functions=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in {'same_recovery_inventory_tasks','source_hashes'}]
assert len(functions)==2
exec(compile(ast.Module(body=functions,type_ignores=[]),'production-time-and-source','exec'),s.__dict__)
pinn_tree=ast.parse((ROOT/'pinn1d.py').read_text(encoding='utf-8'))
methods=next(n for n in pinn_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='METHODS' for t in n.targets))
minimal_pinn=types.ModuleType('pinn1d')
minimal_pinn.METHODS=ast.literal_eval(methods.value)
sys.modules['pinn1d']=minimal_pinn
artifact_tree=ast.parse((ROOT/'run_artifacts.py').read_text(encoding='utf-8'))
validate=next(n for n in artifact_tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate_config')
exec(compile(ast.Module(body=[validate],type_ignores=[]),'production-config-validation','exec'),s.__dict__)
screen_tree=ast.parse((ROOT/'screen.py').read_text(encoding='utf-8'))
out=next(n for n in screen_tree.body if isinstance(n,ast.FunctionDef) and n.name=='out_path')
exec(compile(ast.Module(body=[out],type_ignores=[]),'production-result-path','exec'),s.__dict__)
names={'timestamp_inventory_fixture','bind_changed_events',
 'test_recovery_inventory_accepts_only_same_instants_at_explicit_time_paths',
 'test_recovery_inventory_rejects_naive_invalid_or_moved_time',
 'test_recovery_inventory_does_not_accept_identical_invalid_timestamps',
 'test_recovery_inventory_requires_exact_non_time_values_and_structure',
 'test_recovery_lineage_binds_timezone_converted_inventory_without_weakening_identity'}
test_tree=ast.parse((ROOT/'test_stage6_runner.py').read_text(encoding='utf-8'))
tests=[n for n in test_tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
assert len(tests)==len(names)
exec(compile(ast.Module(body=tests,type_ignores=[]),'production-time-test-bodies','exec'),globals())


def test_independent_arbitrary_fraction_precision_and_other_fields_remain_exact():
    prior=timestamp_inventory_fixture(); observed=copy.deepcopy(prior)
    prior[0]['started_utc']='2026-10-22T16:08:04.123456789012345678900Z'
    observed[0]['started_utc']='2026-10-23T00:08:04.1234567890123456789+08:00'
    assert s.same_recovery_inventory_tasks(observed,prior)
    observed[0]['started_utc']='2026-10-23T00:08:04.12345678901234567891+08:00'
    assert not s.same_recovery_inventory_tasks(observed,prior)
    observed=copy.deepcopy(prior)
    prior[0]['finished_utc']='2026-10-22T16:08:04+00:00'
    observed[0]['finished_utc']='2026-10-23T00:08:04+08:00'
    assert not s.same_recovery_inventory_tasks(observed,prior)
    observed=copy.deepcopy(prior); observed[0]['attempts'][0]['pid']=101.0
    assert not s.same_recovery_inventory_tasks(observed,prior)


def test_independent_real_frozen_manifest_readonly_lineage():
    path=ROOT/'validation/stage6_recovery_20261023/recovery_manifest.json'
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    expected='237609b2ffb7c31f77ac53c1d281bc6e5e03ade97367505e07116835c205c508'
    assert sha(path)==expected
    manifest=json.loads(path.read_text(encoding='utf-8-sig'))
    before={key:sha(entry['path']) for key,entry in manifest['artifacts'].items()}
    assert all(before[key]==entry['sha256'] for key,entry in manifest['artifacts'].items())
    lineage=s.recovery_lineage(path,s.DEFAULT_RUNTIME)
    assert len(lineage['original_active_jobs'])==len(lineage['reconciled'])==21
    assert sum(row[role]['exit_code']==0 for row in lineage['reconciled'] for role in ('launcher','worker'))==42
    assert sha(path)==expected
    assert before=={key:sha(entry['path']) for key,entry in manifest['artifacts'].items()}
    inventory=json.loads(Path(manifest['artifacts']['process_inventory']['path']).read_text(encoding='utf-8-sig'))
    prior=json.loads(Path(manifest['artifacts']['prior_status']['path']).read_text(encoding='utf-8-sig'))
    assert inventory['tasks']!=prior['tasks']
    assert s.same_recovery_inventory_tasks(inventory['tasks'],prior['tasks'])
    report={'manifest_sha256_before_and_after':expected,'artifact_hashes_before_and_after':before,
      'original_active_jobs':21,'reconciled_jobs':21,'zero_exit_observations':42,
      'raw_task_strings_equal':False,'same_instant_task_binding':True,'torch_imported':'torch' in sys.modules,
      'scope':'AST-extracted production lineage/config/source/identity; no Gate, Run, checkpoint content or result numerical validation'}
    (Path(__file__).parent/'real_manifest_probe.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

assert 'torch' not in sys.modules
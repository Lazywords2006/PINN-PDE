"""Independent isolated AST/native checks; no Torch or real run artifacts."""
import ast
from pathlib import Path
import runpy
import sys
import pytest
ROOT=Path(r'E:\PINN-PDE\自主研究\当前主线\round33_equation_screen')
repair=ROOT/'validation/stage6_recovery_20261023/regression_fixture_repair'
ns=runpy.run_path(str(repair/'fixture_checks.py'))
s=ns['s']
require_every_scan_inside_case_directory=ns['require_every_scan_inside_case_directory']
for name in ('test_existing_result_is_revalidated_and_never_dispatched','test_partial_bundle_without_checkpoint_rejected'):
    globals()[name]=ns[name]


def test_production_rejects_unregistered_json_even_after_fixture_repair(monkeypatch,tmp_path):
    job=s.ALL_JOBS[0]
    monkeypatch.setattr(s,'HERE',tmp_path)
    monkeypatch.setattr(s,'ALL_JOBS',[job])
    monkeypatch.setattr(s,'out_path',lambda *args:tmp_path/'expected.json')
    unexpected=tmp_path/'runs'/job[0]/'unregistered.json'
    unexpected.parent.mkdir(parents=True)
    unexpected.write_text('{}')
    with pytest.raises(ValueError,match='未注册结果'):
        s.existing_identity_checks(tmp_path)


@pytest.mark.parametrize('name',['test_existing_result_is_revalidated_and_never_dispatched','test_partial_bundle_without_checkpoint_rejected'])
def test_before_fixture_reproduces_external_scan_failure_on_synthetic_files_only(monkeypatch,tmp_path,name):
    job=s.ALL_JOBS[0]
    external=tmp_path/'synthetic_external_root'
    unexpected=external/'runs'/job[0]/'unregistered.json'
    unexpected.parent.mkdir(parents=True)
    unexpected.write_text('{}')
    monkeypatch.setattr(s,'HERE',external)
    case=tmp_path/'case';case.mkdir()
    before=ast.parse((repair/'before/test_stage6_runner.py').read_text(encoding='utf-8'))
    node=next(n for n in before.body if isinstance(n,ast.FunctionDef) and n.name==name)
    namespace={'s':s,'pytest':pytest}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'before-fixture','exec'),namespace)
    expected=ValueError if name.startswith('test_existing') else AssertionError
    with pytest.raises(expected,match='未注册结果'):
        namespace[name](monkeypatch,case)
    assert unexpected.read_text()=='{}'

assert 'torch' not in sys.modules
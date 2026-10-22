"""Independent lightweight recheck of unchanged persistence and identity tests.
AST-extracted production/test bodies; no Torch import and no training.
"""
import ast
import importlib.util
from pathlib import Path
import sys
ROOT=Path(r'E:\PINN-PDE\自主研究\当前主线\round33_equation_screen')
spec=importlib.util.spec_from_file_location('independent_v2_base',ROOT/'validation/stage6_recovery_20261023/v2/preflight_checks.py')
base=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=base
spec.loader.exec_module(base)
for key,value in base.__dict__.items():
    if not key.startswith('__') and not key.startswith('test_'):
        globals()[key]=value
names={'queue_fixture','bind_changed_events',
       'test_permanent_status_failure_stops_dispatch_and_drains_every_active',
       'test_write_recovery_does_not_resume_dispatch_after_persistence_failure',
       'test_validation_report_failure_stops_dispatch_and_drains',
       'test_final_status_failure_never_claims_completed',
       'test_outer_exception_preserves_original_when_emergency_status_also_fails',
       'test_recovery_binds_original_sources_exit_observations_and_preserves_deadline',
       'test_recovery_rejects_incomplete_mismatched_failed_or_changed_evidence',
       'test_recovery_manifest_cannot_change_after_gate',
       'test_recovery_refuses_to_overwrite_unreviewed_status',
       'test_unknown_exit_never_retries_and_known_failure_requires_explicit_job'}
tree=ast.parse((ROOT/'test_stage6_runner.py').read_text(encoding='utf-8'))
nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
assert len(nodes)==len(names)
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(ROOT/'test_stage6_runner.py'),'exec'),globals())
assert 'torch' not in sys.modules
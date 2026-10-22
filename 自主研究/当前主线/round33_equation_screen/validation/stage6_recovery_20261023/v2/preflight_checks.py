"""Low-memory orchestration regression; AST extracts actual runner/test bodies.

No Torch import and no model training. Checkpoint serialization is represented
by JSON, while the unchanged validate_checkpoint identity code is executed.
Config's actual frozen dataclass is extracted; scientific config validation and
ResultValidator numerics are outside this targeted test's scope.
"""
import ast
import copy
import ctypes
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import types
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[3]
source = ast.parse((ROOT / "stage6_runner.py").read_text(encoding="utf-8"))
s = types.ModuleType("stage6_preflight_isolated")
sys.modules[s.__name__] = s
s.__dict__.update({key: globals()[key] for key in (
    "copy", "ctypes", "asdict", "dataclass", "replace", "datetime", "timezone", "hashlib", "io", "json",
    "os", "Path", "subprocess", "sys", "time", "traceback", "uuid")})
torch = types.SimpleNamespace(
    __version__="2.14.1+cpu", set_num_threads=lambda *a: None, set_num_interop_threads=lambda *a: None,
    save=lambda value, path: Path(path).write_text(json.dumps(value), encoding="utf-8"),
    load=lambda path, **kwargs: json.loads(Path(path).read_text(encoding="utf-8")))
s.__dict__.update(
    HERE=ROOT, VALIDATION=ROOT / "validation/stage6_20261022", torch=torch,
    validate_config=lambda *a: None, get_problem=lambda eq: types.SimpleNamespace(name=eq),
    out_path=lambda *a: Path("__unused_test_path__"), load_result=lambda *a, **kw: pytest.fail("unexpected scientific load"),
    normal_priority=lambda: None, memory_snapshot=lambda: {}, verify_gate=lambda *a: {},
    source_hashes=lambda: {}, check_old_results=lambda: {}, ResultValidator=lambda: None)
config_tree = ast.parse((ROOT / "pinn1d.py").read_text(encoding="utf-8"))
config_node = next(n for n in config_tree.body if isinstance(n, ast.ClassDef) and n.name == "Config")
exec(compile(ast.Module(body=[config_node], type_ignores=[]), str(ROOT / "pinn1d.py"), "exec"), s.__dict__)
constant_names = {"PREREG", "COMMON", "TAU_JOBS", "SOAP_JOBS", "ALL_JOBS", "MAX_WORKERS", "GIB",
                  "_PROGRESS_CACHE", "_REPLACE_DELAYS", "ORCHESTRATION_FILES"}
constants = [n for n in source.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id in constant_names for t in n.targets)]
assert len(constants) == len(constant_names)
exec(compile(ast.Module(body=constants, type_ignores=[]), str(ROOT / "stage6_runner.py"), "exec"), s.__dict__)
artifact_tree = ast.parse((ROOT / "run_artifacts.py").read_text(encoding="utf-8"))
artifact_nodes = [n for n in artifact_tree.body if isinstance(n, ast.FunctionDef)
                  and n.name in {"sha256", "validate_checkpoint"}]
exec(compile(ast.Module(body=artifact_nodes, type_ignores=[]), str(ROOT / "run_artifacts.py"), "exec"), s.__dict__)
names = {"now", "write_json", "read_json", "open_shared_read", "emergency_state", "task_id", "config",
         "checkpoint", "command_for", "FileLock", "worker_lock", "worker_environment", "resources_allow_dispatch",
         "check_no_live_workers", "recovery_lineage", "verify_recovery_bindings", "reconcile_recovered_attempts",
         "require_reviewed_previous_attempts", "existing_identity_checks", "checkpoint_progress", "new_state",
         "prevalidate_results_before_dispatch", "save_status", "validation_report", "execute_queue", "run"}
nodes = [n for n in source.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
assert len(nodes) == len(names)
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / "stage6_runner.py"), "exec"), s.__dict__)
test_tree = ast.parse((ROOT / "test_stage6_runner.py").read_text(encoding="utf-8"))
selected = {"FakeClock", "recovery_fixture",
            "test_previously_finished_artifact_loss_after_gate_never_dispatches_even_on_second_run",
            "test_prevalidation_marks_all_required_jobs_completed_before_queue",
            "test_recovery_validates_old_result_before_any_new_dispatch_and_binds_new_gate"}
tests = [n for n in test_tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in selected]
assert len(tests) == len(selected)
exec(compile(ast.Module(body=tests, type_ignores=[]), str(ROOT / "test_stage6_runner.py"), "exec"), globals())
assert "torch" not in sys.modules

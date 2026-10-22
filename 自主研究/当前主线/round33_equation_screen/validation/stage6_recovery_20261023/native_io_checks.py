"""Low-memory checks of AST-extracted production I/O functions; never import torch.

This is a targeted native/synthetic check, not the pending full runner regression.
All selected test bodies come unchanged from test_stage6_runner.py.
"""
import ast
import copy
import ctypes
from datetime import datetime, timezone
import errno
import io
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback
import types
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[2]
source = ast.parse((ROOT / "stage6_runner.py").read_text(encoding="utf-8"))
names = {"now", "write_json", "open_shared_read", "read_json", "FileLock", "worker_lock",
         "checkpoint", "task_id", "checkpoint_progress", "save_status"}
s = types.ModuleType("isolated_stage6_io")
s.__dict__.update({key: globals()[key] for key in (
    "ctypes", "datetime", "timezone", "io", "json", "os", "Path", "sys", "time", "traceback", "uuid")})
s.__dict__.update(_PROGRESS_CACHE={}, ALL_JOBS=[("test", "E1_heat", "hardic", 0)],
                  torch=types.SimpleNamespace(load=None), out_path=lambda *a: Path("__absent_test_result__"))
s._REPLACE_DELAYS = ast.literal_eval(next(node.value for node in source.body if isinstance(node, ast.Assign)
                                        and any(isinstance(t, ast.Name) and t.id == "_REPLACE_DELAYS" for t in node.targets)))
nodes = [node for node in source.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
assert len(nodes) == len(names)
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / "stage6_runner.py"), "exec"), s.__dict__)

selected = {
    "test_json_replace_transient_denial_retries_without_truncating_destination",
    "test_json_permanent_denial_is_bounded_and_retains_only_one_complete_temp",
    "test_non_sharing_io_failure_is_not_retried",
    "test_shared_reader_allows_rename_and_preserves_detached_old_bytes",
    "test_native_windows_transient_reader_lock_is_retried",
    "test_checkpoint_load_deserializes_detached_shared_snapshot",
    "test_active_checkpoint_progress_never_opens_or_deserializes_file",
    "test_checkpoint_held_worker_lock_blocks_read_even_when_caller_requests_parse",
}
test_source = ast.parse((ROOT / "test_stage6_runner.py").read_text(encoding="utf-8"))
tests = [node for node in test_source.body if isinstance(node, ast.FunctionDef) and node.name in selected]
assert len(tests) == len(selected)
exec(compile(ast.Module(body=tests, type_ignores=[]), str(ROOT / "test_stage6_runner.py"), "exec"), globals())


def test_active_status_routes_without_opening_checkpoint_contents(monkeypatch, tmp_path):
    started = time.time()
    state = {"first_started_utc": datetime.now(timezone.utc).isoformat(), "session_started_unix": started,
             "prior_runner_wall_seconds": 0, "tasks": [
                 {"job": ["test", "E1_heat", "hardic", 0], "state": "running"},
                 {"job": ["test", "E1_heat", "hardic", 1], "state": "failed"}]}
    calls = []

    def progress(job, runtime, *, metadata_only=False):
        calls.append(metadata_only)
        return {"checkpoint_metadata_only": metadata_only}

    monkeypatch.setattr(s, "checkpoint_progress", progress)
    s.save_status(tmp_path, state)
    assert calls == [True, False]
    assert s.read_json(tmp_path / "status.json")["counts"] == dict(queued=0, running=1, completed=0, failed=1)
    assert "torch" not in sys.modules

"""Run the two actual fixture bodies without Torch, guarding every directory scan.

Uses the already documented AST harness for runner code; this verifies fixture
isolation only. Full Torch regression is owned by the root runner.
"""
import ast
from pathlib import Path
import runpy
import sys

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
namespace = runpy.run_path(str(HERE.parent / "v2/preflight_checks.py"))
s = namespace["s"]
names = {"test_existing_result_is_revalidated_and_never_dispatched",
         "test_partial_bundle_without_checkpoint_rejected"}
tree = ast.parse((ROOT / "test_stage6_runner.py").read_text(encoding="utf-8"))
nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
assert len(nodes) == 2
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / "test_stage6_runner.py"), "exec"), globals())
assert "torch" not in sys.modules


@pytest.fixture(autouse=True)
def require_every_scan_inside_case_directory(monkeypatch, tmp_path):
    original = Path.rglob
    seen = []

    def guarded(path, pattern, *args, **kwargs):
        assert path.resolve().is_relative_to(tmp_path.resolve()), f"external directory scan: {path}"
        seen.append(str(path))
        yield from original(path, pattern, *args, **kwargs)

    monkeypatch.setattr(Path, "rglob", guarded)
    yield
    assert len(seen) == 1

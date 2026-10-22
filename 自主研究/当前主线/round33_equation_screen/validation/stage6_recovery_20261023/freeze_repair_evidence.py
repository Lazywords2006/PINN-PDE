"""Freeze engineering review evidence without importing training code or Torch.

Writes only this evidence directory and content-addressed Git blob objects. Does
not stage files, replace the engineering gate, inspect checkpoint bodies, or
start/stop training. Run only after the targeted native checks are complete.
"""
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SNAPSHOT = HERE / "incident_snapshot_20261023_013453_945"
RUNTIME = Path("D:/CodexRuntime/runs/r33_stage6_20261022")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def git(*args):
    return subprocess.run(["git", *map(str, args)], cwd=ROOT, check=True, capture_output=True).stdout


def xml_counts(path):
    suite = ET.parse(path).getroot().find("testsuite")
    return {key: int(suite.attrib[key]) for key in ("tests", "failures", "errors", "skipped")}


def main():
    stamp = datetime.now(timezone.utc).isoformat()
    git_root = Path(git("rev-parse", "--show-toplevel").decode("utf-8").strip())
    snapshot_manifest = read(SNAPSHOT / "snapshot_manifest.json")
    original_gate = read(SNAPSHOT / "engineering_gate.json")
    original_gate_hash = sha(SNAPSHOT / "engineering_gate.json")
    assert sha(ROOT / "validation/stage6_20261022/engineering_gate.json") == original_gate_hash
    assert len(snapshot_manifest["files"]) == 20
    assert sha(RUNTIME / "status.json") == sha(SNAPSHOT / "status.json")
    assert (HERE / ".gitattributes").read_text().strip() == "** -text"

    snapshots = {str(Path(row["snapshot"]).resolve()): row["sha256"].lower()
                 for row in snapshot_manifest["files"]}
    extra_paths = [SNAPSHOT / "snapshot_manifest.json", SNAPSHOT / "process_inventory.json",
                   HERE / "observe_orphan_exits.py", HERE / "pytest_attempt1.log",
                   HERE / "pytest_attempt1.xml", HERE / "pytest_attempt1_hashes.json",
                   HERE / "native_io_checks.py", HERE / "native_io_freeze.log",
                   HERE / "native_io_freeze.xml", HERE / ".gitattributes"]
    blob_rows = []
    for path in [Path(p) for p in snapshots] + extra_paths:
        relative = path.resolve().relative_to(git_root).as_posix()
        attr_fields = git("-C", git_root, "check-attr", "-z", "text", "--", relative).split(b"\0")
        assert attr_fields[2] == b"unset", (relative, attr_fields)
        blob = git("-C", git_root, "hash-object", "--path", relative, "-w", str(path)).decode("ascii").strip()
        blob_bytes = git("cat-file", "blob", blob)
        workspace_sha256 = sha(path)
        blob_sha256 = hashlib.sha256(blob_bytes).hexdigest()
        expected = snapshots.get(str(path.resolve()), workspace_sha256)
        assert blob_sha256 == workspace_sha256 == expected, relative
        blob_rows.append({"path": relative, "git_blob_oid": blob,
                          "git_blob_sha256": blob_sha256, "workspace_sha256": workspace_sha256,
                          "snapshot_manifest_sha256": snapshots.get(str(path.resolve())),
                          "git_text_attribute": "unset", "byte_identical": True})
    write(HERE / "git_blob_integrity.json", {
        "utc": stamp, "scope": "20 incident snapshots plus 10 evidence inputs",
        "operation": "git hash-object --path -w followed by git cat-file blob; no staging or commit",
        "all_byte_identical": True, "snapshot_count": 20, "checked_count": len(blob_rows),
        "files": blob_rows})

    sources = {name: sha(ROOT / name) for name in original_gate["source_hashes"]}
    allowed_changes = {"stage6_runner.py", "test_stage6_runner.py", "run_stage6.ps1"}
    changed_sources = [name for name, digest in sources.items()
                       if digest != original_gate["source_hashes"][name]]
    assert set(changed_sources) <= allowed_changes
    parsed = []
    for path in (ROOT / "stage6_runner.py", ROOT / "test_stage6_runner.py",
                 HERE / "observe_orphan_exits.py", HERE / "native_io_checks.py", Path(__file__)):
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        parsed.append(str(path.relative_to(ROOT)))
    diff = git("diff", "--no-ext-diff", "--", "stage6_runner.py", "test_stage6_runner.py", "run_stage6.ps1")
    assert diff
    (HERE / "runner_fix_review.diff").write_bytes(diff)
    first_counts = xml_counts(HERE / "pytest_attempt1.xml")
    native_counts = xml_counts(HERE / "native_io_freeze.xml")
    assert first_counts == {"tests": 71, "failures": 1, "errors": 0, "skipped": 0}
    assert native_counts == {"tests": 9, "failures": 0, "errors": 0, "skipped": 0}
    events = [json.loads(line) for line in
              (RUNTIME / "orphan_observer_20261023_0138/events.jsonl").read_text(encoding="utf-8").splitlines()]
    event_counts = dict(Counter(row["event"] for row in events))
    files = ["runner_fix_review.diff", "native_io_checks.py", "native_io_freeze.log", "native_io_freeze.xml",
             "pytest_attempt1.log", "pytest_attempt1.xml", "pytest_attempt1_hashes.json",
             "observe_orphan_exits.py", "git_blob_integrity.json", "RECOVERY_ROUTE.md", ".gitattributes"]
    write(HERE / "engineering_repair_evidence.json", {
        "schema": "r33_stage6_engineering_repair_review_v1", "frozen_utc": stamp,
        "status": "STATIC_REVIEW_READY_FULL_REGRESSION_PENDING",
        "complete_regression_status": "PENDING_RESOURCE_HEADROOM",
        "recovery_dispatch_blocked": True, "new_gate_published": False,
        "training_dispatched_by_repair": False, "training_terminated_by_repair": False,
        "original_gate_sha256": original_gate_hash,
        "runtime_status_unchanged_since_incident_snapshot": True,
        "original_scientific_protocol_vendor_sources_unchanged": True,
        "changed_gate_bound_sources": changed_sources, "frozen_source_hashes": sources,
        "ast_parse": {"passed": True, "files": parsed},
        "first_full_regression": {
            "counts": first_counts, "passed_count": 70, "accepted_as_pass": False,
            "source_hashes_file": "pytest_attempt1_hashes.json",
            "failure": "Open Windows destination replacement was denied despite FILE_SHARE_DELETE; overstrong test assumption corrected",
            "additional_diagnostic": "Log includes Torch import WMI 0x8007000e stack; run continued. This is not a training-worker OOM attribution."},
        "current_native_regression": {
            "counts": native_counts, "passed_count": 9,
            "scope": "AST-extracted production I/O, unchanged selected tests, native Windows handles and synthetic checkpoint stub; no Torch import",
            "full_runner_regression": False,
            "source_hashes": {name: sources[name] for name in ("stage6_runner.py", "test_stage6_runner.py")}},
        "observer_event_counts_at_freeze": event_counts,
        "observer_source_sha256": sha(HERE / "observe_orphan_exits.py"),
        "artifact_sha256": {name: sha(HERE / name) for name in files},
        "recovery_route": "RECOVERY_ROUTE.md",
        "required_before_root_recovery": [
            "Independent review and full current-source regression PASS after resource headroom returns",
            "All 42 original HANDLE exits recorded as zero, exact identities verified, observer completed",
            "All original task locks released and all original exit-zero result JSONs present",
            "Immutable recovery manifest and newly passed gate bound to old source and all evidence",
            "All prior results validated by unchanged scientific acceptance before dispatching remaining tasks"],
        "scientific_acceptance": "NOT_EVALUATED_BY_THIS_REPAIR"})
    print(json.dumps({"snapshot_blobs_byte_identical": 20, "total_blobs_byte_identical": len(blob_rows),
                      "native_passed": 9, "complete_regression_status": "PENDING_RESOURCE_HEADROOM",
                      "changed_sources": changed_sources, "observer_events": event_counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()

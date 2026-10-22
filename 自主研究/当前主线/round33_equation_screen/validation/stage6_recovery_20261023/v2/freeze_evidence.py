"""Freeze v2 evidence, preserving all v1 bytes; stdlib only, no training imports."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE.parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def git(*args, allow_diff=False):
    result = subprocess.run(["git", *map(str, args)], cwd=ROOT, capture_output=True)
    assert result.returncode in ((0, 1) if allow_diff else (0,)), result.stderr.decode("utf-8", errors="replace")
    return result.stdout


def main():
    stamp = datetime.now(timezone.utc).isoformat()
    v1 = read(EVIDENCE / "engineering_repair_evidence.json")
    for name, digest in v1["artifact_sha256"].items():
        assert sha(EVIDENCE / name) == digest, name
    for name in ("stage6_runner.py", "test_stage6_runner.py"):
        assert sha(EVIDENCE / "v1_frozen_sources" / name) == v1["frozen_source_hashes"][name]
    original = read(EVIDENCE / "incident_snapshot_20261023_013453_945/engineering_gate.json")
    manifest = read(EVIDENCE / "incident_snapshot_20261023_013453_945/snapshot_manifest.json")
    for entry in manifest["files"]:
        assert sha(entry["snapshot"]) == entry["sha256"]
    assert sha(ROOT / "validation/stage6_20261022/engineering_gate.json") == v1["original_gate_sha256"]
    source_hashes = {name: sha(ROOT / name) for name in original["source_hashes"]}
    changed = [name for name, digest in source_hashes.items() if original["source_hashes"][name] != digest]
    assert set(changed) == {"stage6_runner.py", "test_stage6_runner.py"}
    source_dir = HERE / "frozen_sources"
    source_dir.mkdir(exist_ok=True)
    for name in changed:
        target = source_dir / name
        if target.exists():
            assert sha(target) == source_hashes[name], "Refusing to overwrite a prior freeze"
        else:
            target.write_bytes((ROOT / name).read_bytes())
    write(source_dir / "source_hashes.json", {name: source_hashes[name] for name in changed})
    (HERE / "runner_fix_review.diff").write_bytes(git("diff", "--no-ext-diff", "--",
                                                     "stage6_runner.py", "test_stage6_runner.py", "run_stage6.ps1"))
    delta = b"".join(git("diff", "--no-index", "--no-ext-diff", EVIDENCE / "v1_frozen_sources" / name,
                         ROOT / name, allow_diff=True) for name in changed)
    (HERE / "v1_to_v2.diff").write_bytes(delta)
    git("diff", "--check", "--", "stage6_runner.py", "test_stage6_runner.py")
    parsed = [ROOT / "stage6_runner.py", ROOT / "test_stage6_runner.py", HERE / "preflight_checks.py", Path(__file__)]
    for path in parsed:
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    suite = ET.parse(HERE / "lightweight.xml").getroot().find("testsuite")
    counts = {key: int(suite.attrib[key]) for key in ("tests", "errors", "failures", "skipped")}
    assert counts == dict(tests=18, errors=0, failures=0, skipped=0)
    git_root = Path(git("rev-parse", "--show-toplevel").decode("utf-8").strip())
    inputs = [*sorted(source_dir.iterdir()),
              *sorted((EVIDENCE / "v1_frozen_sources").iterdir()), HERE / "REVIEW.md", HERE / "preflight_checks.py",
              HERE / "lightweight.log", HERE / "lightweight.xml", HERE / "runner_fix_review.diff",
              HERE / "v1_to_v2.diff", Path(__file__)]
    rows = []
    for path in inputs:
        relative = path.resolve().relative_to(git_root).as_posix()
        fields = git("-C", git_root, "check-attr", "-z", "text", "--", relative).split(b"\0")
        assert fields[2] == b"unset"
        oid = git("-C", git_root, "hash-object", "--path", relative, "-w", path).decode("ascii").strip()
        blob_sha = hashlib.sha256(git("cat-file", "blob", oid)).hexdigest()
        assert blob_sha == sha(path)
        rows.append({"path": relative, "git_blob_oid": oid, "sha256": blob_sha,
                     "git_text_attribute": "unset", "blob_equals_workspace": True})
    write(HERE / "git_blob_integrity.json", {"utc": stamp, "all_byte_identical": True,
                                             "count": len(rows), "files": rows})
    artifacts = [*inputs, HERE / "git_blob_integrity.json"]
    write(HERE / "engineering_repair_evidence.json", {
        "schema": "r33_stage6_engineering_repair_review_v2", "frozen_utc": stamp,
        "status": "STATIC_REVIEW_READY_FULL_REGRESSION_PENDING",
        "complete_regression_status": "PENDING_RESOURCE_HEADROOM", "recovery_dispatch_blocked": True,
        "v1_evidence_sha256": sha(EVIDENCE / "engineering_repair_evidence.json"),
        "v1_artifact_hashes_reverified": True, "all_20_incident_snapshots_unchanged": True,
        "original_gate_sha256": v1["original_gate_sha256"], "original_gate_unchanged": True,
        "source_hashes": source_hashes, "only_changed_gate_bound_sources": changed,
        "scientific_protocol_vendor_sources_unchanged": True,
        "repair": "Mandatory prior-result validation before any dispatch, with durable required_complete_result inherited across failed preflight reruns",
        "negative_controls": {"cases": 6, "run_attempts_per_case": 2, "popen_calls_per_case": 0,
            "origins": ["gate recovery original_active_jobs", "previous completed"],
            "losses": ["JSON removed with valid identity checkpoint", "entire bundle removed", "only valid identity checkpoint remains"]},
        "lightweight_regression": {"counts": counts, "torch_imported": False,
            "scope": "9 native I/O checks and 9 AST-extracted orchestration checks; synthetic checkpoint serialization and scientific-validator sentinel",
            "full_torch_regression": False},
        "ast_parse_passed": True, "git_diff_check_passed": True,
        "artifact_sha256": {str(path.relative_to(EVIDENCE)): sha(path) for path in artifacts},
        "new_gate_published": False, "real_training_started": False, "training_terminated": False,
        "scientific_acceptance": "NOT_EVALUATED_BY_THIS_REPAIR"})
    print(json.dumps({"lightweight_passed": 18, "v1_preserved": True, "incident_snapshots_unchanged": 20,
                      "v2_blob_checks": len(rows), "complete_regression": "PENDING_RESOURCE_HEADROOM"}))


if __name__ == "__main__":
    main()

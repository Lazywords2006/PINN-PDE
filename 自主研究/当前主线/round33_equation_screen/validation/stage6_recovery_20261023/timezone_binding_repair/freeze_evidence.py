"""Freeze timezone repair evidence using stdlib only; never invoke Gate or Run."""
import ast
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def git(*args):
    return subprocess.run(["git", *map(str, args)], cwd=ROOT, capture_output=True, check=True).stdout


def main():
    stamp = datetime.now(timezone.utc).isoformat()
    git_root = Path(git("rev-parse", "--show-toplevel").decode("utf-8").strip())
    baseline_head = git("rev-parse", "HEAD").decode("ascii").strip()
    before = read(HERE / "before_manifest.json")
    for entry in before["files"]:
        assert sha(entry["snapshot"]) == entry["sha256"]
        if Path(entry["source"]).name.endswith(".log"):
            assert sha(entry["source"]) == entry["sha256"]
    assert sha(BASE / "recovery_manifest.json") == before["recovery_manifest_sha256"]
    for entry in before["bound_artifacts"].values():
        assert sha(entry["path"]) == entry["sha256"]
    history_mismatches = []
    for report_path, anchor in ((BASE / "engineering_repair_evidence.json", BASE),
                                (BASE / "v2/engineering_repair_evidence.json", BASE),
                                (BASE / "regression_fixture_repair/repair_evidence.json", BASE / "regression_fixture_repair")):
        for name, digest in read(report_path)["artifact_sha256"].items():
            path = anchor / name
            actual = sha(path)
            if actual != digest:
                assert path == BASE / "RECOVERY_ROUTE.md"
                relative = path.relative_to(git_root).as_posix()
                head_sha = hashlib.sha256(git("show", "HEAD:" + relative)).hexdigest()
                assert actual == head_sha == "a3197bb6fdb6dd60fbd421d713b689d06d26c18360dd39d1a34f94657a39d02e"
                history_mismatches.append({"report": str(report_path.relative_to(BASE)), "path": name,
                                           "recorded_sha256": digest, "current_sha256": actual,
                                           "already_committed_head": baseline_head, "head_blob_sha256": head_sha})
    original = read(BASE / "incident_snapshot_20261023_013453_945/engineering_gate.json")
    current = {name: sha(ROOT / name) for name in original["source_hashes"]}
    changed = [name for name, digest in current.items() if digest != original["source_hashes"][name]]
    assert set(changed) == {"stage6_runner.py", "test_stage6_runner.py"}
    after = HERE / "after"
    after.mkdir(exist_ok=True)
    diff = ""
    for name in changed:
        data = (ROOT / name).read_bytes()
        target = after / name
        if target.exists():
            assert target.read_bytes() == data, "Refusing to overwrite a different freeze"
        else:
            target.write_bytes(data)
        ast.parse(data.decode("utf-8-sig"), filename=name)
        diff += "".join(difflib.unified_diff((HERE / "before" / name).read_text(encoding="utf-8-sig").splitlines(keepends=True),
                                            data.decode("utf-8-sig").splitlines(keepends=True),
                                            fromfile="before/" + name, tofile="after/" + name))
    (HERE / "timezone_binding.diff").write_text(diff, encoding="utf-8")
    git("diff", "--check", "--", *changed)
    suite = ET.parse(HERE / "pytest_attempt1.xml").getroot().find("testsuite")
    counts = {key: int(suite.attrib[key]) for key in ("tests", "failures", "errors", "skipped")}
    assert counts == dict(tests=110, failures=0, errors=0, skipped=0)
    probe = read(HERE / "real_manifest_lineage.json")
    assert probe["passed"] and probe["current_source_hashes"] == current
    assert probe["manifest_sha256_before_and_after"] == before["recovery_manifest_sha256"]
    differences = read(HERE / "task_binding_differences.json")
    assert differences["difference_count"] == 42
    assert all(row["same_utc_instant"] for row in differences["differences"])
    inputs = [p for p in sorted(HERE.rglob("*")) if p.is_file() and p.name not in ("git_blob_integrity.json", "repair_evidence.json")]
    rows = []
    for path in inputs:
        relative = path.relative_to(git_root).as_posix()
        attr = git("-C", git_root, "check-attr", "-z", "text", "--", relative).split(b"\0")[2]
        assert attr == b"unset"
        oid = git("-C", git_root, "hash-object", "--path", relative, "-w", path).decode("ascii").strip()
        blob_sha = hashlib.sha256(git("cat-file", "blob", oid)).hexdigest()
        assert blob_sha == sha(path)
        rows.append({"path": relative, "git_blob_oid": oid, "sha256": blob_sha,
                     "text_attribute": "unset", "blob_equals_workspace": True})
    write(HERE / "git_blob_integrity.json", {"verified_utc": stamp, "count": len(rows),
                                             "all_byte_identical": True, "files": rows})
    inputs.append(HERE / "git_blob_integrity.json")
    write(HERE / "repair_evidence.json", {
        "schema": "r33_stage6_timezone_binding_repair_v1", "verified_utc": stamp,
        "status": "CURRENT_SOURCE_FULL_REGRESSION_AND_READONLY_REAL_MANIFEST_PROBE_PASS",
        "changes": "Only explicit task/attempt started_utc paths compare timezone-equivalent exact instants; all other JSON values/types/structure remain exact",
        "allowed_time_paths": ["tasks[i].started_utc", "tasks[i].attempts[j].started_utc"],
        "fractional_second_precision": "All digits retained, trailing zero normalization only; no time tolerance",
        "actual_task_count": 30, "actual_difference_count": 42, "all_actual_differences_same_instant": True,
        "full_torch_regression": counts, "added_test_cases": 29,
        "real_manifest_probe": {key: probe[key] for key in ("passed", "manifest_sha256_before_and_after",
                                   "all_bound_artifacts_unchanged", "original_active_jobs", "reconciled_jobs", "verified_zero_exit_observations")},
        "source_hashes": current, "changed_original_gate_bound_sources": changed,
        "all_scientific_protocol_vendor_sources_unchanged": True,
        "known_preexisting_history_hash_mismatches": history_mismatches,
        "all_other_v1_v2_fixture_repair_artifacts_match_recorded_hashes": True,
        "original_gate_failure_log_unchanged": True,
        "manifest_and_bound_original_evidence_unchanged": True, "git_diff_check_passed": True,
        "artifact_sha256": {str(path.relative_to(HERE)): sha(path) for path in inputs},
        "gate_invoked": False, "run_invoked": False, "training_started_or_stopped": False,
        "committed": False, "scientific_acceptance": "NOT_EVALUATED_BY_THIS_REPAIR"})
    print(json.dumps({"full_torch_passed": 110, "actual_lineage_passed": True, "git_blob_checks": len(rows),
                      "preexisting_route_hash_mismatches": len(history_mismatches), "all_other_history_hashes_match": True}))


if __name__ == "__main__":
    main()

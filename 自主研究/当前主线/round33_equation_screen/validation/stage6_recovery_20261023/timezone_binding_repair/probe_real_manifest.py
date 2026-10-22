"""Read-only real-manifest recovery_lineage probe. Never invokes Gate or Run."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

import stage6_runner as runner


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path = HERE.parent / "recovery_manifest.json"
    expected = "237609b2ffb7c31f77ac53c1d281bc6e5e03ade97367505e07116835c205c508"
    assert sha(manifest_path) == expected
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    original_hashes = {key: sha(entry["path"]) for key, entry in manifest["artifacts"].items()}
    assert all(original_hashes[key] == entry["sha256"] for key, entry in manifest["artifacts"].items())
    lineage = runner.recovery_lineage(manifest_path, runner.DEFAULT_RUNTIME)
    assert len(lineage["original_active_jobs"]) == len(lineage["reconciled"]) == 21
    assert all(row[role]["exit_code"] == 0 for row in lineage["reconciled"] for role in ("launcher", "worker"))
    assert sha(manifest_path) == expected
    assert original_hashes == {key: sha(entry["path"]) for key, entry in manifest["artifacts"].items()}
    report = {
        "verified_utc": datetime.now(timezone.utc).isoformat(), "passed": True,
        "scope": "Read-only recovery_lineage identity/source/exit-evidence check; not Gate, Run, complete bundle validation, or scientific acceptance",
        "manifest_sha256_before_and_after": expected, "all_bound_artifacts_unchanged": True,
        "original_active_jobs": 21, "reconciled_jobs": 21, "verified_zero_exit_observations": 42,
        "current_source_hashes": runner.source_hashes(), "lineage": lineage}
    (HERE / "real_manifest_lineage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("passed", "original_active_jobs", "reconciled_jobs",
                                                  "verified_zero_exit_observations", "all_bound_artifacts_unchanged")}))


if __name__ == "__main__":
    main()

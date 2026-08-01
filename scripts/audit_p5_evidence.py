#!/usr/bin/env python3
"""Independently verify and recompute a frozen P5 evidence bundle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
import tarfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import BinaryIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_p5_diagnostic import (
    P5_FAMILIES,
    P5_METHODS,
    P5_SEEDS,
    _aggregate,
    build_p5_gate,
)

MANIFEST_PATH = "results/p5-evidence-manifest.json"
EXECUTION_PATH = "results/p5_execution/execution-summary.json"
SMOKE_GATE_PATH = "results/p5_smoke/diagnostic_gate.json"
SMOKE_SUMMARY_PATH = "results/p5_smoke/summary.json"
PROMOTION_GATE_PATH = "results/p5_promotion/diagnostic_gate.json"
PROMOTION_SUMMARY_PATH = "results/p5_promotion/summary.json"


def _sha256_stream(handle: BinaryIO) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return _sha256_stream(handle)


def _member_is_safe(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def _read_member_bytes(
    archive: tarfile.TarFile, members: dict[str, tarfile.TarInfo], name: str
) -> bytes:
    member = members.get(name)
    if member is None or not member.isfile():
        raise ValueError(f"missing evidence member: {name}")
    extracted = archive.extractfile(member)
    if extracted is None:
        raise ValueError(f"cannot read evidence member: {name}")
    return extracted.read()


def _read_json_member(
    archive: tarfile.TarFile, members: dict[str, tarfile.TarInfo], name: str
) -> dict[str, object]:
    value = json.loads(_read_member_bytes(archive, members, name))
    if not isinstance(value, dict):
        raise ValueError(f"evidence JSON must be an object: {name}")
    return value


def _numbers_close(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=1e-10, abs_tol=1e-12)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            _numbers_close(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _numbers_close(a, b) for a, b in zip(left, right)
        )
    return left == right


def _summary_projection(summary: dict[str, object]) -> dict[str, object]:
    keys = {
        "total_runs",
        "completed_runs",
        "failed_runs",
        "methods",
        "families",
        "seeds",
        "steps",
        "maximum_orthogonality_error",
        "maximum_gram_condition",
        "paired_comparisons",
    }
    for method in P5_METHODS:
        keys.update(
            {
                f"{method}_near_cluster_projector_mean",
                f"{method}_gap_scan_projector_mean",
                f"{method}_training_time_mean",
            }
        )
        for family in P5_FAMILIES:
            keys.update(
                {
                    f"{method}_{family}_near_cluster_projector_mean",
                    f"{method}_{family}_num_parameters",
                }
            )
    return {key: summary.get(key) for key in sorted(keys)}


def _verify_manifest(
    archive: tarfile.TarFile,
    members: dict[str, tarfile.TarInfo],
    manifest: dict[str, object],
) -> tuple[bool, list[dict[str, object]]]:
    rows = manifest.get("files")
    if not isinstance(rows, list):
        return False, [{"path": MANIFEST_PATH, "reason": "files is not a list"}]
    failures: list[dict[str, object]] = []
    listed: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            failures.append({"path": None, "reason": "manifest row is not an object"})
            continue
        name = row.get("path")
        if not isinstance(name, str) or not _member_is_safe(name):
            failures.append({"path": name, "reason": "unsafe or invalid path"})
            continue
        if name in listed:
            failures.append({"path": name, "reason": "duplicate manifest path"})
            continue
        listed.add(name)
        member = members.get(name)
        if member is None or not member.isfile():
            failures.append({"path": name, "reason": "missing from archive"})
            continue
        extracted = archive.extractfile(member)
        if extracted is None:
            failures.append({"path": name, "reason": "unreadable"})
            continue
        actual_hash = _sha256_stream(extracted)
        expected_hash = row.get("sha256")
        expected_bytes = row.get("bytes")
        if expected_bytes != member.size:
            failures.append(
                {
                    "path": name,
                    "reason": "byte count mismatch",
                    "expected": expected_bytes,
                    "actual": member.size,
                }
            )
        if expected_hash != actual_hash:
            failures.append(
                {
                    "path": name,
                    "reason": "SHA-256 mismatch",
                    "expected": expected_hash,
                    "actual": actual_hash,
                }
            )
    archive_files = {name for name, member in members.items() if member.isfile()}
    unlisted = sorted(archive_files - listed - {MANIFEST_PATH})
    for name in unlisted:
        failures.append({"path": name, "reason": "archive file is not in manifest"})
    return not failures, failures


def audit_p5_evidence(
    archive_path: Path, sidecar_path: Path | None = None
) -> dict[str, object]:
    """Verify hashes and independently recompute every frozen P5 gate input."""

    archive_path = archive_path.resolve()
    if sidecar_path is None:
        candidate = archive_path.with_suffix(archive_path.suffix + ".sha256")
        sidecar_path = candidate if candidate.is_file() else None
    archive_sha256 = _sha256_file(archive_path)
    sidecar_expected: str | None = None
    if sidecar_path is not None and sidecar_path.is_file():
        tokens = sidecar_path.read_text().split()
        sidecar_expected = tokens[0] if tokens else None
    sidecar_match = sidecar_expected == archive_sha256

    with tarfile.open(archive_path, "r:gz") as archive:
        all_members = archive.getmembers()
        names = [member.name for member in all_members]
        duplicate_members = sorted(
            name for name, count in Counter(names).items() if count > 1
        )
        unsafe_members = sorted(name for name in names if not _member_is_safe(name))
        members = {member.name: member for member in all_members}
        manifest = _read_json_member(archive, members, MANIFEST_PATH)
        manifest_pass, manifest_failures = _verify_manifest(archive, members, manifest)
        execution = _read_json_member(archive, members, EXECUTION_PATH)
        smoke_gate = _read_json_member(archive, members, SMOKE_GATE_PATH)
        smoke_summary = _read_json_member(archive, members, SMOKE_SUMMARY_PATH)
        stored_gate = _read_json_member(archive, members, PROMOTION_GATE_PATH)
        stored_summary = _read_json_member(archive, members, PROMOTION_SUMMARY_PATH)

        result_names = sorted(
            name
            for name, member in members.items()
            if member.isfile()
            and name.startswith("results/p5_promotion/")
            and name.endswith("/result.json")
        )
        results: list[dict[str, object]] = []
        run_artifact_failures: list[dict[str, object]] = []
        for result_name in result_names:
            result = _read_json_member(archive, members, result_name)
            results.append(result)
            run_root = result_name.rsplit("/", 1)[0]
            final_name = f"{run_root}/final.pt"
            metrics_name = f"{run_root}/metrics.csv"
            try:
                final_hash = hashlib.sha256(
                    _read_member_bytes(archive, members, final_name)
                ).hexdigest()
                if final_hash != result.get("final_checkpoint_sha256"):
                    run_artifact_failures.append(
                        {
                            "run": run_root,
                            "reason": "final checkpoint hash mismatch",
                        }
                    )
                metrics_text = _read_member_bytes(
                    archive, members, metrics_name
                ).decode("utf-8")
                metric_rows = list(csv.DictReader(io.StringIO(metrics_text)))
                split_values: dict[str, list[float]] = {}
                for row in metric_rows:
                    split_values.setdefault(row["split"], []).append(
                        float(row["projector_sine_error"])
                    )
                csv_split_means = {
                    split: sum(values) / len(values)
                    for split, values in split_values.items()
                }
                if not _numbers_close(
                    csv_split_means, result.get("split_projector_mean")
                ):
                    run_artifact_failures.append(
                        {
                            "run": run_root,
                            "reason": "metrics.csv split-mean mismatch",
                        }
                    )
                if result.get("point_count") != len(metric_rows):
                    run_artifact_failures.append(
                        {
                            "run": run_root,
                            "reason": "metrics.csv row-count mismatch",
                        }
                    )
                if metric_rows:
                    csv_max_orthogonality = max(
                        float(row["orthogonality_error"]) for row in metric_rows
                    )
                    csv_max_gram = max(
                        float(row["gram_condition"]) for row in metric_rows
                    )
                    if not _numbers_close(
                        csv_max_orthogonality,
                        result.get("maximum_orthogonality_error"),
                    ):
                        run_artifact_failures.append(
                            {
                                "run": run_root,
                                "reason": "CSV orthogonality maximum mismatch",
                            }
                        )
                    if not _numbers_close(
                        csv_max_gram, result.get("maximum_gram_condition")
                    ):
                        run_artifact_failures.append(
                            {
                                "run": run_root,
                                "reason": "CSV Gram-condition maximum mismatch",
                            }
                        )
            except (KeyError, UnicodeDecodeError, ValueError) as error:
                run_artifact_failures.append(
                    {"run": run_root, "reason": f"invalid run artifact: {error}"}
                )

    expected_matrix = {
        (method, family, seed)
        for method in P5_METHODS
        for family in P5_FAMILIES
        for seed in P5_SEEDS
    }
    actual_identities: list[tuple[object, object, object]] = []
    all_results_pass = True
    for result in results:
        config = result.get("config")
        if not isinstance(config, dict):
            all_results_pass = False
            continue
        actual_identities.append(
            (
                config.get("method"),
                config.get("potential_family"),
                config.get("seed"),
            )
        )
        all_results_pass = all_results_pass and result.get("status") == "PASS"
    actual_matrix = set(actual_identities)
    run_matrix_complete = (
        len(results) == 36
        and len(actual_identities) == len(actual_matrix)
        and actual_matrix == expected_matrix
    )

    recomputed_summary = _aggregate(results, [], "promotion")
    recomputed_gate = build_p5_gate(recomputed_summary)
    summary_matches = _numbers_close(
        _summary_projection(stored_summary),
        _summary_projection(recomputed_summary),
    )
    gate_matches = _numbers_close(stored_gate, recomputed_gate)
    expected_status = (
        "P5_PROMOTION_GO"
        if recomputed_gate.get("promotion_go")
        else "P5_PROMOTION_STOP"
    )
    execution_status_matches = execution.get("status") == expected_status
    smoke_pass = (
        smoke_gate.get("engineering_pass") is True
        and smoke_summary.get("total_runs") == 12
        and smoke_summary.get("completed_runs") == 12
        and smoke_summary.get("failed_runs") == 0
    )

    checks = {
        "sidecar_sha256_pass": sidecar_match,
        "safe_archive_paths": not unsafe_members and not duplicate_members,
        "manifest_integrity_pass": manifest_pass,
        "smoke_pass": smoke_pass,
        "run_matrix_complete": run_matrix_complete,
        "all_results_pass": all_results_pass,
        "run_artifacts_match_result_json": not run_artifact_failures,
        "summary_matches_recomputation": summary_matches,
        "gate_matches_recomputation": gate_matches,
        "execution_status_matches_recomputation": execution_status_matches,
    }
    return {
        "schema_version": 1,
        "archive": str(archive_path),
        "archive_sha256": archive_sha256,
        "sidecar": str(sidecar_path) if sidecar_path is not None else None,
        "sidecar_expected_sha256": sidecar_expected,
        "audit_pass": all(checks.values()),
        **checks,
        "duplicate_archive_members": duplicate_members,
        "unsafe_archive_members": unsafe_members,
        "manifest_failures": manifest_failures,
        "run_artifact_failures": run_artifact_failures,
        "result_json_count": len(results),
        "missing_run_identities": [
            list(identity)
            for identity in sorted(expected_matrix - actual_matrix, key=repr)
        ],
        "unexpected_run_identities": [
            list(identity)
            for identity in sorted(actual_matrix - expected_matrix, key=repr)
        ],
        "stored_execution_status": execution.get("status"),
        "recomputed_execution_status": expected_status,
        "stored_gate": stored_gate,
        "recomputed_gate": recomputed_gate,
        "recomputed_summary": _summary_projection(recomputed_summary),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--sidecar", type=Path, default=None)
    parser.add_argument(
        "--output", type=Path, default=Path("results/p5_independent_audit.json")
    )
    args = parser.parse_args()
    try:
        report = audit_p5_evidence(args.archive, args.sidecar)
    except Exception as error:
        report = {
            "schema_version": 1,
            "archive": str(args.archive),
            "audit_pass": False,
            "error_type": type(error).__name__,
            "reason": str(error),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("audit_pass") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())

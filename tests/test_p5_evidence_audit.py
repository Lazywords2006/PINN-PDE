from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

from scripts.audit_p5_evidence import audit_p5_evidence
from scripts.run_p5_diagnostic import (
    P5_FAMILIES,
    P5_METHODS,
    P5_SEEDS,
    _aggregate,
    build_p5_gate,
)


def _result(method: str, family: str, seed: int) -> dict[str, object]:
    near = {
        "p5_anchor": 0.130,
        "p5_static_low_rom": 0.100,
        "p5_wide_anchor": 0.120,
        "p5_long_anchor": 0.120,
        "p5_unanchored_low_rom": 0.115,
        "p5_highfreq_rom": 0.118,
    }[method]
    gap = {
        "p5_anchor": 0.140,
        "p5_static_low_rom": 0.139,
        "p5_wide_anchor": 0.141,
        "p5_long_anchor": 0.140,
        "p5_unanchored_low_rom": 0.145,
        "p5_highfreq_rom": 0.143,
    }[method]
    counts = {
        "harmonic_honeycomb": {
            "p5_anchor": 9156,
            "p5_static_low_rom": 11300,
            "p5_wide_anchor": 11452,
            "p5_long_anchor": 9156,
            "p5_unanchored_low_rom": 11300,
            "p5_highfreq_rom": 11300,
        },
        "gaussian_honeycomb": {
            "p5_anchor": 9220,
            "p5_static_low_rom": 11397,
            "p5_wide_anchor": 11524,
            "p5_long_anchor": 9220,
            "p5_unanchored_low_rom": 11397,
            "p5_highfreq_rom": 11397,
        },
    }
    return {
        "status": "PASS",
        "config": {
            "method": method,
            "potential_family": family,
            "seed": seed,
        },
        "split_projector_mean": {"near_cluster": near, "gap_scan": gap},
        "elapsed_seconds": 40.0 if method != "p5_anchor" else 39.0,
        "num_parameters": counts[family][method],
        "maximum_orthogonality_error": 1e-6,
        "maximum_gram_condition": 20.0,
    }


def _write_bundle(
    tmp_path: Path,
    *,
    missing_run: bool = False,
    falsify_summary: bool = False,
    falsify_metrics: bool = False,
    corrupt_after_manifest: bool = False,
) -> tuple[Path, Path]:
    results = [
        _result(method, family, seed)
        for method in P5_METHODS
        for family in P5_FAMILIES
        for seed in P5_SEEDS
    ]
    if missing_run:
        results.pop()
    summary = _aggregate(results, [], "promotion")
    gate = build_p5_gate(summary)
    summary["gate"] = gate
    if falsify_summary:
        summary["p5_static_low_rom_near_cluster_projector_mean"] = 0.001

    entries: dict[str, bytes] = {
        "results/p5_execution/execution-summary.json": (
            json.dumps(
                {
                    "status": (
                        "P5_PROMOTION_GO"
                        if gate["promotion_go"]
                        else "P5_PROMOTION_STOP"
                    ),
                    "environment": {"git_commit": "test-commit"},
                }
            ).encode()
        ),
        "results/p5_smoke/diagnostic_gate.json": json.dumps(
            {"engineering_pass": True}
        ).encode(),
        "results/p5_smoke/summary.json": json.dumps(
            {"total_runs": 12, "completed_runs": 12, "failed_runs": 0}
        ).encode(),
        "results/p5_promotion/diagnostic_gate.json": json.dumps(gate).encode(),
        "results/p5_promotion/summary.json": json.dumps(summary).encode(),
    }
    for result in results:
        config = result["config"]
        assert isinstance(config, dict)
        run_id = f"{config['method']}_{config['potential_family']}_seed{config['seed']}"
        final_payload = f"checkpoint:{run_id}".encode()
        result["final_checkpoint_sha256"] = hashlib.sha256(final_payload).hexdigest()
        result["point_count"] = 2
        entries[f"results/p5_promotion/{run_id}/result.json"] = json.dumps(
            result
        ).encode()
        entries[f"results/p5_promotion/{run_id}/final.pt"] = final_payload
        split_means = result["split_projector_mean"]
        assert isinstance(split_means, dict)
        near = split_means["near_cluster"]
        gap = split_means["gap_scan"]
        if falsify_metrics and not any(
            name.endswith("/metrics.csv") for name in entries
        ):
            near = float(near) + 0.5
        entries[f"results/p5_promotion/{run_id}/metrics.csv"] = (
            "split,projector_sine_error,orthogonality_error,gram_condition\n"
            f"near_cluster,{near},0.000001,20.0\n"
            f"gap_scan,{gap},0.000001,20.0\n"
        ).encode()

    manifest = {
        "schema_version": 1,
        "files": [
            {
                "path": name,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            for name, payload in sorted(entries.items())
        ],
    }
    entries["results/p5-evidence-manifest.json"] = json.dumps(manifest).encode()
    if corrupt_after_manifest:
        result_name = next(
            name for name in entries if name.endswith("seed42/result.json")
        )
        entries[result_name] += b"\n"

    archive = tmp_path / "p5-evidence-test.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        for name, payload in entries.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            handle.addfile(info, io.BytesIO(payload))
    sidecar = archive.with_suffix(archive.suffix + ".sha256")
    sidecar.write_text(
        f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n"
    )
    return archive, sidecar


def test_valid_p5_bundle_is_recomputed_and_passes(tmp_path: Path) -> None:
    archive, sidecar = _write_bundle(tmp_path)
    report = audit_p5_evidence(archive, sidecar)
    assert report["audit_pass"] is True
    assert report["run_matrix_complete"] is True
    assert report["manifest_integrity_pass"] is True
    assert report["summary_matches_recomputation"] is True
    recomputed = report["recomputed_summary"]
    assert isinstance(recomputed, dict)
    assert recomputed["p5_static_low_rom_near_cluster_projector_mean"] == 0.1


def test_p5_evidence_auditor_is_directly_invocable() -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/audit_p5_evidence.py", "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--sidecar" in completed.stdout


def test_manifest_detects_tampered_result(tmp_path: Path) -> None:
    archive, sidecar = _write_bundle(tmp_path, corrupt_after_manifest=True)
    report = audit_p5_evidence(archive, sidecar)
    assert report["audit_pass"] is False
    assert report["manifest_integrity_pass"] is False


def test_recomputation_detects_falsified_summary(tmp_path: Path) -> None:
    archive, sidecar = _write_bundle(tmp_path, falsify_summary=True)
    report = audit_p5_evidence(archive, sidecar)
    assert report["manifest_integrity_pass"] is True
    assert report["summary_matches_recomputation"] is False
    assert report["audit_pass"] is False


def test_run_csv_must_match_its_result_json(tmp_path: Path) -> None:
    archive, sidecar = _write_bundle(tmp_path, falsify_metrics=True)
    report = audit_p5_evidence(archive, sidecar)
    assert report["manifest_integrity_pass"] is True
    assert report["run_artifacts_match_result_json"] is False
    assert report["audit_pass"] is False


def test_missing_run_fails_the_frozen_matrix(tmp_path: Path) -> None:
    archive, sidecar = _write_bundle(tmp_path, missing_run=True)
    report = audit_p5_evidence(archive, sidecar)
    assert report["run_matrix_complete"] is False
    assert report["audit_pass"] is False

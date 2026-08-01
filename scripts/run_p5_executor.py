#!/usr/bin/env python3
"""Decision-free one-command executor for the frozen P5 control matrix."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_p4_executor import (
    _clear_decision_files,
    _environment,
    _hash_sidecar_matches,
    _interpret_smoke_outputs,
    _read_json,
    _run,
    _write_environment_details,
    interpret_promotion_outputs,
    write_evidence_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--device", choices=("auto", "cpu", "mps", "cuda", "rocm"), default="auto"
    )
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--skip-cache", action="store_true")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="local development only; formal execution requires a clean checkout",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    execution_dir = root / "results/p5_execution"
    execution_dir.mkdir(parents=True, exist_ok=True)
    environment = _environment(root, args.device)
    if environment["git_status_porcelain"] and not args.allow_dirty:
        raise RuntimeError("formal P5 execution requires a clean Git checkout")
    (execution_dir / "environment.json").write_text(
        json.dumps(environment, ensure_ascii=False, indent=2) + "\n"
    )
    _write_environment_details(execution_dir)

    records: list[dict[str, object]] = []
    status = "ENGINEERING_FAIL"
    exit_code = 1
    python = sys.executable
    cache_path = root / "data/v2_validation_references.pt"
    cache_sidecar = root / "data/v2_validation_references.sha256"
    if not args.skip_cache:
        cache_code = _run(
            root,
            [
                python,
                "scripts/generate_v2_assets.py",
                "--device",
                args.device,
                "--cache-only",
                "--reference-scope",
                "validation",
            ],
            records,
        )
        if cache_code != 0 or not _hash_sidecar_matches(cache_path, cache_sidecar):
            status = "CACHE_FAIL"
        else:
            exit_code = 0

    cache_ready = _hash_sidecar_matches(cache_path, cache_sidecar)
    if args.skip_cache and not cache_ready:
        status = "CACHE_MISSING"
    elif (args.skip_cache or exit_code == 0) and cache_ready:
        _clear_decision_files(root / "results/p5_smoke")
        _run(
            root,
            [
                python,
                "scripts/run_p5_diagnostic.py",
                "--protocol",
                "smoke",
                "--device",
                args.device,
            ],
            records,
        )
        smoke_gate = _read_json(root / "results/p5_smoke/diagnostic_gate.json")
        smoke_summary = _read_json(root / "results/p5_smoke/summary.json")
        if not _interpret_smoke_outputs(smoke_gate, smoke_summary):
            status = "SMOKE_FAIL"
            exit_code = 1
        elif args.smoke_only:
            status = "SMOKE_PASS"
            exit_code = 0
        else:
            _clear_decision_files(root / "results/p5_promotion")
            promotion_code = _run(
                root,
                [
                    python,
                    "scripts/run_p5_diagnostic.py",
                    "--protocol",
                    "promotion",
                    "--device",
                    args.device,
                ],
                records,
            )
            promotion_gate = _read_json(
                root / "results/p5_promotion/diagnostic_gate.json"
            )
            promotion_summary = _read_json(root / "results/p5_promotion/summary.json")
            base_status, exit_code = interpret_promotion_outputs(
                promotion_code,
                promotion_gate,
                promotion_summary,
                expected_runs=36,
            )
            status = f"P5_{base_status}"

    execution = {
        "status": status,
        "exit_code": exit_code,
        "environment": environment,
        "commands": records,
        "interpretation": (
            "P5_PROMOTION_GO requires both a structural-ROM mechanism signal and "
            "gap-scan non-regression. P5_PROMOTION_STOP must not open frozen final."
        ),
    }
    (execution_dir / "execution-summary.json").write_text(
        json.dumps(execution, ensure_ascii=False, indent=2) + "\n"
    )
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    include = (
        root / "results/p5_execution",
        root / "results/p5_smoke",
        root / "results/p5_promotion",
        cache_path,
        cache_sidecar,
        root / "benchmarks/v2_validation.json",
        root / "benchmarks/v2_validation.sha256",
        root / "benchmarks/v2_reference_convergence.json",
        root / "benchmarks/v2_reference_convergence.sha256",
        root / "block_kyfan_pinn",
        root / "scripts/generate_v2_assets.py",
        root / "scripts/run_p4_diagnostic.py",
        root / "scripts/run_p4_executor.py",
        root / "scripts/run_p5_diagnostic.py",
        root / "scripts/run_p5_executor.py",
        root / "requirements.txt",
    )
    archive, sidecar, manifest = write_evidence_bundle(
        root=root,
        include_paths=include,
        output_dir=root / "artifacts",
        label=timestamp,
        prefix="p5-evidence",
        manifest_name="p5-evidence-manifest.json",
    )
    print(f"P5_EXECUTION_STATUS={status}")
    print(f"EVIDENCE_BUNDLE={archive}")
    print(f"EVIDENCE_SHA256={sidecar}")
    print(f"EVIDENCE_MANIFEST={manifest}")
    return exit_code


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)

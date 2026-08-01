#!/usr/bin/env python3
"""One-command, decision-free executor for the P4 validation protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import torch


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _included_files(root: Path, include_paths: tuple[Path, ...], manifest: Path) -> list[Path]:
    def eligible(path: Path) -> bool:
        return path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"

    files: set[Path] = set()
    for requested in include_paths:
        path = requested if requested.is_absolute() else root / requested
        if not path.exists():
            continue
        if eligible(path):
            files.add(path.resolve())
        else:
            files.update(candidate.resolve() for candidate in path.rglob("*") if eligible(candidate))
    files.discard(manifest.resolve())
    return sorted(files, key=lambda path: str(path.relative_to(root.resolve())))


def write_evidence_bundle(
    *,
    root: Path,
    include_paths: tuple[Path, ...],
    output_dir: Path,
    label: str,
) -> tuple[Path, Path, Path]:
    """Write a hash manifest, compressed evidence bundle, and SHA sidecar."""

    root = root.resolve()
    output_dir = output_dir if output_dir.is_absolute() else root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    results_root = root / "results"
    results_root.mkdir(parents=True, exist_ok=True)
    manifest = results_root / "evidence-manifest.json"
    files = _included_files(root, include_paths, manifest)
    payload = {
        "schema_version": 1,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": [
            {
                "path": str(path.relative_to(root)),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in files
        ],
    }
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    archive = output_dir / f"p4-evidence-{label}.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        for path in files:
            handle.add(path, arcname=str(path.relative_to(root)), recursive=False)
        handle.add(manifest, arcname=str(manifest.relative_to(root)), recursive=False)
    sidecar = archive.with_suffix(archive.suffix + ".sha256")
    sidecar.write_text(f"{_sha256(archive)}  {archive.name}\n")
    return archive, sidecar, manifest


def _git_value(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ("git", *arguments), cwd=root, check=True, text=True, capture_output=True
    )
    return result.stdout.strip()


def _environment(root: Path, device: str) -> dict[str, object]:
    selected_name: str | None = None
    accelerator_memory: int | None = None
    if torch.cuda.is_available():
        try:
            selected_name = torch.cuda.get_device_name(0)
            accelerator_memory = int(torch.cuda.get_device_properties(0).total_memory)
        except Exception:
            selected_name = None
    return {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": _git_value(root, "rev-parse", "HEAD"),
        "git_branch": _git_value(root, "branch", "--show-current"),
        "git_status_porcelain": _git_value(root, "status", "--porcelain"),
        "requested_device": device,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "hip": getattr(torch.version, "hip", None),
        "accelerator_available": torch.cuda.is_available(),
        "accelerator_name": selected_name,
        "accelerator_total_memory_bytes": accelerator_memory,
        "cpu_count": os.cpu_count(),
    }


def _write_environment_details(execution_dir: Path) -> None:
    freeze = subprocess.run(
        (sys.executable, "-m", "pip", "freeze"),
        check=False,
        text=True,
        capture_output=True,
    )
    (execution_dir / "pip-freeze.txt").write_text(
        freeze.stdout if freeze.returncode == 0 else freeze.stderr
    )
    query = shutil.which("nvidia-smi") or shutil.which("rocminfo")
    if query is not None:
        hardware = subprocess.run(
            (query,), check=False, text=True, capture_output=True
        )
        (execution_dir / "accelerator-query.txt").write_text(
            hardware.stdout + hardware.stderr
        )


def _run(root: Path, command: list[str], records: list[dict[str, object]]) -> int:
    print("EXEC:", " ".join(command), flush=True)
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=root, check=False)
    records.append(
        {
            "command": command,
            "return_code": completed.returncode,
            "elapsed_seconds": time.perf_counter() - started,
        }
    )
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "mps", "cuda", "rocm"))
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--skip-cache", action="store_true")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="local development only; formal remote execution must use a clean checkout",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    execution_dir = root / "results" / "p4_execution"
    execution_dir.mkdir(parents=True, exist_ok=True)
    environment = _environment(root, args.device)
    if environment["git_status_porcelain"] and not args.allow_dirty:
        raise RuntimeError("formal P4 execution requires a clean Git checkout")
    (execution_dir / "environment.json").write_text(
        json.dumps(environment, ensure_ascii=False, indent=2) + "\n"
    )
    _write_environment_details(execution_dir)

    records: list[dict[str, object]] = []
    status = "ENGINEERING_FAIL"
    exit_code = 1
    python = sys.executable
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
        if cache_code != 0:
            status = "CACHE_FAIL"
        else:
            exit_code = 0

    cache_ready = (root / "data/v2_validation_references.pt").is_file()
    if args.skip_cache and not cache_ready:
        status = "CACHE_MISSING"
        exit_code = 1
    elif (args.skip_cache or exit_code == 0) and cache_ready:
        smoke_code = _run(
            root,
            [
                python,
                "scripts/run_p4_diagnostic.py",
                "--protocol",
                "smoke",
                "--device",
                args.device,
                "--method",
                "all",
                "--family",
                "all",
                "--seed",
                "42",
                "--steps",
                "5",
                "--points",
                "64",
                "--parameter-batch",
                "1",
                "--max-points-per-split",
                "1",
            ],
            records,
        )
        if smoke_code != 0:
            status = "SMOKE_FAIL"
            exit_code = smoke_code
        elif args.smoke_only:
            status = "SMOKE_PASS"
            exit_code = 0
        else:
            promotion_code = _run(
                root,
                [
                    python,
                    "scripts/run_p4_diagnostic.py",
                    "--protocol",
                    "promotion",
                    "--device",
                    args.device,
                    "--method",
                    "all",
                    "--family",
                    "all",
                    "--seed",
                    "42",
                    "137",
                    "251",
                    "--steps",
                    "500",
                ],
                records,
            )
            status = "PROMOTION_GO" if promotion_code == 0 else "PROMOTION_STOP"
            exit_code = promotion_code

    execution = {
        "status": status,
        "exit_code": exit_code,
        "environment": environment,
        "commands": records,
        "interpretation": (
            "Only PROMOTION_GO authorizes design of a frozen-final evaluator for P4. "
            "PROMOTION_STOP is a scientific result, not an infrastructure failure."
        ),
    }
    (execution_dir / "execution-summary.json").write_text(
        json.dumps(execution, ensure_ascii=False, indent=2) + "\n"
    )
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    include = (
        root / "results/p4_execution",
        root / "results/p4_smoke",
        root / "results/p4_promotion",
        root / "data/v2_validation_references.pt",
        root / "data/v2_validation_references.sha256",
        root / "benchmarks/v2_validation.json",
        root / "benchmarks/v2_validation.sha256",
        root / "benchmarks/v2_reference_convergence.json",
        root / "benchmarks/v2_reference_convergence.sha256",
        root / "block_kyfan_pinn",
        root / "scripts/run_p4_diagnostic.py",
        root / "scripts/run_p4_executor.py",
        root / "requirements.txt",
    )
    archive, sidecar, manifest = write_evidence_bundle(
        root=root,
        include_paths=include,
        output_dir=root / "artifacts",
        label=timestamp,
    )
    print(f"P4_EXECUTION_STATUS={status}")
    print(f"EVIDENCE_BUNDLE={archive}")
    print(f"EVIDENCE_SHA256={sidecar}")
    print(f"EVIDENCE_MANIFEST={manifest}")
    return exit_code


if __name__ == "__main__":
    # Environment workaround: this ROCm torch build forces exit code 0 on
    # interpreter shutdown, masking failures. os._exit() bypasses that hook.
    # Run main() first so its prints are in the buffer, then flush, then exit.
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)

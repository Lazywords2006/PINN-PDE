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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch

from block_kyfan_pinn.device import select_device


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _included_files(
    root: Path, include_paths: tuple[Path, ...], manifest: Path
) -> list[Path]:
    def eligible(path: Path) -> bool:
        return (
            path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        )

    files: set[Path] = set()
    for requested in include_paths:
        path = requested if requested.is_absolute() else root / requested
        if not path.exists():
            continue
        if eligible(path):
            files.add(path.resolve())
        else:
            files.update(
                candidate.resolve()
                for candidate in path.rglob("*")
                if eligible(candidate)
            )
    files.discard(manifest.resolve())
    return sorted(files, key=lambda path: str(path.relative_to(root.resolve())))


def write_evidence_bundle(
    *,
    root: Path,
    include_paths: tuple[Path, ...],
    output_dir: Path,
    label: str,
    prefix: str = "p4-evidence",
    manifest_name: str = "evidence-manifest.json",
) -> tuple[Path, Path, Path]:
    """Write a hash manifest, compressed evidence bundle, and SHA sidecar."""

    root = root.resolve()
    output_dir = output_dir if output_dir.is_absolute() else root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    results_root = root / "results"
    results_root.mkdir(parents=True, exist_ok=True)
    manifest = results_root / manifest_name
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
    archive = output_dir / f"{prefix}-{label}.tar.gz"
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
    selected_device = select_device(device)
    selected_name: str | None = None
    accelerator_memory: int | None = None
    if selected_device.type == "cuda":
        try:
            selected_name = torch.cuda.get_device_name(0)
            accelerator_memory = int(torch.cuda.get_device_properties(0).total_memory)
        except Exception:
            selected_name = None
    elif selected_device.type == "mps":
        selected_name = "Apple MPS"
    selected_backend = (
        "rocm"
        if selected_device.type == "cuda" and getattr(torch.version, "hip", None)
        else selected_device.type
    )
    return {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": _git_value(root, "rev-parse", "HEAD"),
        "git_branch": _git_value(root, "branch", "--show-current"),
        "git_status_porcelain": _git_value(root, "status", "--porcelain"),
        "requested_device": device,
        "selected_device": str(selected_device),
        "selected_backend": selected_backend,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "hip": getattr(torch.version, "hip", None),
        "accelerator_available": selected_device.type != "cpu",
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
        hardware = subprocess.run((query,), check=False, text=True, capture_output=True)
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


def _read_json(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def interpret_promotion_outputs(
    return_code: int,
    gate: dict[str, object] | None,
    summary: dict[str, object] | None,
    expected_runs: int = 30,
) -> tuple[str, int]:
    """Interpret promotion JSON, never a subprocess code alone.

    Some ROCm torch builds force process exit code zero even after an exception.
    A complete 30-run summary and the serialized gate are therefore mandatory.
    """

    if gate is None or summary is None:
        return "ENGINEERING_FAIL", 1
    complete = (
        int(summary.get("total_runs", 0)) == expected_runs
        and int(summary.get("completed_runs", 0)) == expected_runs
        and int(summary.get("failed_runs", expected_runs)) == 0
    )
    if not complete:
        return "ENGINEERING_FAIL", 1
    if bool(gate.get("promotion_go")):
        return ("PROMOTION_GO", 0) if return_code == 0 else ("ENGINEERING_FAIL", 1)
    return "PROMOTION_STOP", 2


def _interpret_smoke_outputs(
    gate: dict[str, object] | None, summary: dict[str, object] | None
) -> bool:
    if gate is None or summary is None or not bool(gate.get("engineering_pass")):
        return False
    total = int(summary.get("total_runs", 0))
    return (
        total > 0
        and int(summary.get("completed_runs", 0)) == total
        and int(summary.get("failed_runs", total)) == 0
    )


def _hash_sidecar_matches(path: Path, sidecar: Path) -> bool:
    try:
        expected = sidecar.read_text().split()[0]
    except (FileNotFoundError, IndexError, OSError):
        return False
    return path.is_file() and _sha256(path) == expected


def _clear_decision_files(output_dir: Path) -> None:
    """Prevent a crashed subprocess from reusing a stale gate or summary."""

    for name in ("summary.json", "diagnostic_gate.json"):
        (output_dir / name).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--device", default="auto", choices=("auto", "cpu", "mps", "cuda", "rocm")
    )
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--skip-cache", action="store_true")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help=(
            "local development only; formal remote execution requires a clean checkout"
        ),
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
        cache_ready = _hash_sidecar_matches(
            root / "data/v2_validation_references.pt",
            root / "data/v2_validation_references.sha256",
        )
        if cache_code != 0 or not cache_ready:
            status = "CACHE_FAIL"
        else:
            exit_code = 0

    cache_ready = _hash_sidecar_matches(
        root / "data/v2_validation_references.pt",
        root / "data/v2_validation_references.sha256",
    )
    if args.skip_cache and not cache_ready:
        status = "CACHE_MISSING"
        exit_code = 1
    elif (args.skip_cache or exit_code == 0) and cache_ready:
        _clear_decision_files(root / "results/p4_smoke")
        _run(
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
        smoke_gate = _read_json(root / "results/p4_smoke/diagnostic_gate.json")
        smoke_summary = _read_json(root / "results/p4_smoke/summary.json")
        if not _interpret_smoke_outputs(smoke_gate, smoke_summary):
            status = "SMOKE_FAIL"
            exit_code = 1
        elif args.smoke_only:
            status = "SMOKE_PASS"
            exit_code = 0
        else:
            _clear_decision_files(root / "results/p4_promotion")
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
            promotion_gate = _read_json(
                root / "results/p4_promotion/diagnostic_gate.json"
            )
            promotion_summary = _read_json(root / "results/p4_promotion/summary.json")
            status, exit_code = interpret_promotion_outputs(
                promotion_code, promotion_gate, promotion_summary
            )

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
        root / "scripts/generate_v2_assets.py",
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

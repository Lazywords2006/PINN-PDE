from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import torch

from block_kyfan_pinn.accelerator import (
    accelerator_report,
    detect_backend,
    run_numerical_checks,
)
from block_kyfan_pinn.device import select_device


def test_detect_backend_returns_cpu_when_no_accelerator_is_available(monkeypatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    assert detect_backend() == "cpu"


def test_rocm_request_rejects_a_non_rocm_torch_build(monkeypatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.version, "hip", None)
    try:
        select_device("rocm")
    except RuntimeError as error:
        assert "ROCm" in str(error)
    else:
        raise AssertionError("a non-ROCm build must not satisfy a ROCm request")


def test_cpu_numerical_preflight_exercises_required_operations() -> None:
    checks = run_numerical_checks(torch.device("cpu"))
    assert checks["second_derivative_float32"]["status"] == "PASS"
    assert checks["second_derivative_float64"]["status"] == "PASS"
    assert checks["complex64_linalg"]["status"] == "PASS"
    assert checks["complex128_linalg"]["status"] == "PASS"


def test_accelerator_report_is_machine_readable() -> None:
    report = accelerator_report("cpu")
    assert report["status"] == "PASS"
    assert report["requested_backend"] == "cpu"
    assert report["selected_device"] == "cpu"
    assert report["detected_backend"] in {"cpu", "mps", "cuda", "rocm"}
    assert report["checks"]


def test_preflight_script_runs_from_the_repository_root() -> None:
    repository = Path(__file__).resolve().parents[1]
    process = subprocess.run(
        [sys.executable, "scripts/preflight_accelerator.py", "--backend", "cpu"],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert '"status": "PASS"' in process.stdout

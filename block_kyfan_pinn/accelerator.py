"""Runtime inspection and numerical accelerator preflight checks."""

from __future__ import annotations

import platform
from collections.abc import Callable

import torch

from .device import select_device, synchronize


def detect_backend() -> str:
    """Return the accelerator backend exposed by the current PyTorch build."""

    if torch.cuda.is_available():
        return "rocm" if getattr(torch.version, "hip", None) else "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _run_check(operation: Callable[[], float]) -> dict[str, object]:
    try:
        maximum_error = operation()
    except Exception as error:  # The exception text is required preflight evidence.
        return {
            "status": "FAIL",
            "error_type": type(error).__name__,
            "error": str(error),
        }
    return {"status": "PASS", "maximum_error": maximum_error}


def _second_derivative_check(device: torch.device, dtype: torch.dtype) -> float:
    coordinates = torch.linspace(-0.8, 0.8, 32, device=device, dtype=dtype, requires_grad=True)
    values = torch.sin(coordinates).square()
    first = torch.autograd.grad(values.sum(), coordinates, create_graph=True)[0]
    second = torch.autograd.grad(first.sum(), coordinates)[0]
    expected = 2.0 * torch.cos(2.0 * coordinates)
    error = float((second - expected).abs().max().detach().cpu())
    synchronize(device)
    tolerance = 5e-5 if dtype == torch.float32 else 1e-10
    if error > tolerance:
        raise ArithmeticError(
            f"second-derivative error {error:.3e} exceeds tolerance {tolerance:.3e}"
        )
    return error


def _complex_linalg_check(device: torch.device, dtype: torch.dtype) -> float:
    real_dtype = torch.float32 if dtype == torch.complex64 else torch.float64
    diagonal = torch.arange(1, 5, device=device, dtype=real_dtype)
    matrix = torch.diag(diagonal).to(dtype=dtype)
    matrix[0, 1] = 0.25 + 0.125j
    matrix[1, 0] = 0.25 - 0.125j
    matrix[2, 3] = -0.2 + 0.1j
    matrix[3, 2] = -0.2 - 0.1j
    q, _ = torch.linalg.qr(matrix)
    identity = torch.eye(4, device=device, dtype=dtype)
    orthogonality_error = (q.mH @ q - identity).abs().max()
    eigenvalues = torch.linalg.eigvalsh(matrix)
    if not bool(torch.isfinite(eigenvalues).all().detach().cpu()):
        raise FloatingPointError("complex Hermitian eigenvalues are non-finite")
    synchronize(device)
    error = float(orthogonality_error.detach().cpu())
    tolerance = 1e-4 if dtype == torch.complex64 else 1e-10
    if error > tolerance:
        raise ArithmeticError(
            f"complex QR error {error:.3e} exceeds tolerance {tolerance:.3e}"
        )
    return error


def run_numerical_checks(device: torch.device) -> dict[str, dict[str, object]]:
    """Exercise operations required by the neural PDE and PWE workflows."""

    return {
        "second_derivative_float32": _run_check(
            lambda: _second_derivative_check(device, torch.float32)
        ),
        "second_derivative_float64": _run_check(
            lambda: _second_derivative_check(device, torch.float64)
        ),
        "complex64_linalg": _run_check(lambda: _complex_linalg_check(device, torch.complex64)),
        "complex128_linalg": _run_check(lambda: _complex_linalg_check(device, torch.complex128)),
    }


def accelerator_report(requested_backend: str = "auto") -> dict[str, object]:
    """Build a JSON-serializable runtime and numerical capability report."""

    device = select_device(requested_backend)
    detected_backend = detect_backend()
    checks = run_numerical_checks(device)
    device_name = platform.processor() or platform.machine()
    total_memory_bytes = 0
    capability: list[int] | None = None
    if device.type == "cuda":
        properties = torch.cuda.get_device_properties(device)
        device_name = properties.name
        total_memory_bytes = int(properties.total_memory)
        if not getattr(torch.version, "hip", None):
            capability = list(torch.cuda.get_device_capability(device))
    status = "PASS" if all(check["status"] == "PASS" for check in checks.values()) else "FAIL"
    return {
        "status": status,
        "requested_backend": requested_backend,
        "detected_backend": detected_backend,
        "selected_device": str(device),
        "device_name": device_name,
        "total_memory_bytes": total_memory_bytes,
        "compute_capability": capability,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "torch_version": torch.__version__,
        "torch_cuda_version": torch.version.cuda,
        "torch_hip_version": getattr(torch.version, "hip", None),
        "checks": checks,
    }

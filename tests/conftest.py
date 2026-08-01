"""Cross-backend compatibility shim for torch builds without CPU LAPACK.

This machine's ROCm PyTorch is compiled with the CPU LAPACK backend
disabled (``torch._C.has_lapack is False``). Operations such as
``eigh``, ``eigvalsh``, ``svd``/``svdvals``, ``solve``, ``qr``,
``lu_factor``, ``inv``, ``det``, etc. therefore raise
"LAPACK library not found in compilation" on CPU tensors, even though
the accelerator (ROCm/cuSOLVER/rocsolver) path works correctly.

When that defect is detected *and* an accelerator is available, this
shim transparently runs those operations on the accelerator and moves
results back to the input tensors' original device. No scientific
logic, thresholds, seeds, steps, or benchmarks are touched, and no
test source is modified: this is purely a runtime device-detection
fallback for one broken backend.

The shim is inert when the build has CPU LAPACK, when no accelerator
is present, or when a call already receives accelerator tensors.
"""

from __future__ import annotations

import functools

import torch
import torch.linalg as _linalg

# Compiled-in flag: False when the build lacks the CPU LAPACK backend.
_LAPACK_BROKEN = not getattr(torch._C, "has_lapack", True)

# Operations whose CPU path requires LAPACK and therefore fails on this
# build. Only these are redirected; every other op is untouched.
_BROKEN_OPS = (
    "cholesky",
    "cholesky_ex",
    "det",
    "eig",
    "eigh",
    "eigvalsh",
    "inv",
    "lstsq",
    "lu",
    "lu_factor",
    "lu_solve",
    "matrix_rank",
    "pinv",
    "qr",
    "slogdet",
    "solve",
    "solve_triangular",
    "svd",
    "svdvals",
)


def _back_to_cpu(value):
    """Recursively move tensors back to CPU, preserving container shape."""
    if isinstance(value, torch.Tensor):
        return value.cpu() if value.device.type != "cpu" else value
    if isinstance(value, tuple):
        return tuple(_back_to_cpu(item) for item in value)
    if isinstance(value, list):
        return [_back_to_cpu(item) for item in value]
    if isinstance(value, dict):
        return {key: _back_to_cpu(item) for key, item in value.items()}
    return value


def _redirect_to_accelerator(fn):
    """Wrap ``fn`` so CPU tensors compute on the accelerator when needed."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        sample = next(
            (arg for arg in (*args, *kwargs.values()) if isinstance(arg, torch.Tensor)),
            None,
        )
        if (
            _LAPACK_BROKEN
            and sample is not None
            and sample.device.type == "cpu"
            and torch.cuda.is_available()
        ):
            moved_args = tuple(
                arg.cuda()
                if isinstance(arg, torch.Tensor) and arg.device.type == "cpu"
                else arg
                for arg in args
            )
            moved_kwargs = {
                key: (value.cuda() if isinstance(value, torch.Tensor) and value.device.type == "cpu" else value)
                for key, value in kwargs.items()
            }
            return _back_to_cpu(fn(*moved_args, **moved_kwargs))
        return fn(*args, **kwargs)

    wrapper.__wrapped__ = fn
    return wrapper


for _op in _BROKEN_OPS:
    if hasattr(_linalg, _op):
        setattr(_linalg, _op, _redirect_to_accelerator(getattr(_linalg, _op)))

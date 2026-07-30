"""Device selection shared by smoke and formal runs."""

import torch


def select_device(requested: str = "auto") -> torch.device:
    if requested == "cpu":
        return torch.device("cpu")
    if requested == "mps":
        if not (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()):
            raise RuntimeError("MPS was requested but is unavailable")
        return torch.device("mps")
    if requested == "rocm":
        if not torch.cuda.is_available() or not getattr(torch.version, "hip", None):
            raise RuntimeError("ROCm was requested but this is not a usable ROCm PyTorch build")
        # PyTorch intentionally exposes ROCm devices through the torch.cuda API.
        return torch.device("cuda")
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA-compatible acceleration was requested but is unavailable")
        return torch.device("cuda")
    if requested != "auto":
        raise ValueError(f"unknown device request: {requested}")
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elif device.type == "mps":
        torch.mps.synchronize()

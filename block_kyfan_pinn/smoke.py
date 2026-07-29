"""Small deterministic smoke run; not a paper experiment."""

from __future__ import annotations

import json
import platform
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import torch

from .device import select_device, synchronize
from .metrics import projector_sine_error
from .model import BlockKyFanPINN
from .physics import (
    apply_hamiltonian,
    complex_gram_mean,
    ky_fan_energy,
    projected_residual_rms,
    periodic_mgs,
)
from .reference import evaluate_reference_basis, solve_reference


@dataclass(frozen=True)
class SmokeConfig:
    device: str = "auto"
    seed: int = 17
    steps: int = 30
    points: int = 96
    width: int = 32
    hidden_layers: int = 2
    learning_rate: float = 3e-3


def run_smoke(config: SmokeConfig, output_path: Path | None = None) -> dict[str, object]:
    torch.manual_seed(config.seed)
    device = select_device(config.device)
    model = BlockKyFanPINN(width=config.width, hidden_layers=config.hidden_layers).to(device)
    coordinates = (torch.rand(1, config.points, 2, device=device) * (2.0 * torch.pi)).requires_grad_()
    parameters = torch.tensor([[0.31, 0.35, 0.35, 0.05]], device=device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)

    initial = float(ky_fan_energy(model(coordinates, parameters), coordinates, parameters).detach().cpu())
    start = time.perf_counter()
    loss_history: list[float] = []
    for _ in range(config.steps):
        optimizer.zero_grad(set_to_none=True)
        loss = ky_fan_energy(model(coordinates, parameters), coordinates, parameters)
        if not bool(torch.isfinite(loss).detach().cpu()):
            raise FloatingPointError("non-finite Ky Fan energy")
        loss.backward()
        optimizer.step()
        loss_history.append(float(loss.detach().cpu()))
    synchronize(device)
    elapsed = time.perf_counter() - start

    basis = model(coordinates, parameters)
    final = float(ky_fan_energy(basis, coordinates, parameters).detach().cpu())
    gram_real, gram_imag = complex_gram_mean(basis)
    identity = torch.eye(2, device=device).expand_as(gram_real)
    orthogonality_error = float(
        torch.maximum((gram_real - identity).abs().max(), gram_imag.abs().max()).detach().cpu()
    )
    h_basis = apply_hamiltonian(basis, coordinates, parameters)
    residual = float(projected_residual_rms(basis, h_basis).detach().cpu())
    reference = solve_reference(parameters[0], cutoff=2, rank=2)
    reference_basis = periodic_mgs(evaluate_reference_basis(reference, coordinates))
    subspace_error = projector_sine_error(basis, reference_basis)
    passed = final < initial and orthogonality_error < 1e-4 and torch.isfinite(h_basis).all().item()

    peak_memory = 0
    if device.type == "cuda":
        peak_memory = int(torch.cuda.max_memory_allocated(device))
    elif device.type == "mps":
        peak_memory = int(torch.mps.current_allocated_memory())
    result: dict[str, object] = {
        "status": "PASS" if passed else "FAIL",
        "scope": "engineering_smoke_not_paper_result",
        "config": asdict(config),
        "device": str(device),
        "torch_version": torch.__version__,
        "python_version": platform.python_version(),
        "initial_energy": initial,
        "final_energy": final,
        "energy_reduction": initial - final,
        "orthogonality_error": orthogonality_error,
        "residual_rms": residual,
        "projector_sine_error": subspace_error,
        "reference_eigenvalues": reference.eigenvalues.tolist(),
        "elapsed_seconds": elapsed,
        "peak_memory_bytes": peak_memory,
        "loss_history": loss_history,
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result

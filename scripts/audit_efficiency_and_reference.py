"""Audit inference cost and plane-wave reference convergence."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import torch

from block_kyfan_pinn.device import select_device, synchronize
from block_kyfan_pinn.metrics import projector_sine_error
from block_kyfan_pinn.model import BlockKyFanPINN
from block_kyfan_pinn.physics import periodic_mgs
from block_kyfan_pinn.reference import evaluate_reference_basis, solve_reference, uniform_grid


CASES = {
    "interpolation": (0.31, 0.35, 0.35, 0.05),
    "symmetric_cluster": (1.0 / 3.0, 1.0 / 3.0, 0.60, 0.0),
    "extrapolation": (0.42, 0.24, 0.90, 0.16),
}


def _timed_forward(model: BlockKyFanPINN, device: torch.device, repeats: int) -> list[float]:
    coordinates = uniform_grid(33).unsqueeze(0).to(device)
    parameters = torch.tensor([CASES["interpolation"]], device=device)
    with torch.no_grad():
        for _ in range(20):
            model(coordinates, parameters)
        synchronize(device)
        samples = []
        for _ in range(repeats):
            start = time.perf_counter()
            model(coordinates, parameters)
            synchronize(device)
            samples.append(time.perf_counter() - start)
    return samples


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--repeats", type=int, default=200)
    args = parser.parse_args()

    device = select_device(args.device)
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False)
    config = checkpoint["config"]
    model = BlockKyFanPINN(
        width=int(config["width"]),
        hidden_layers=int(config["hidden_layers"]),
        anchor_kind=str(config["anchor_kind"]),
        anchor_scale=float(config["anchor_scale"]),
        parameter_dim=len(config["parameter_lower"]),
        orthogonalization=str(config.get("orthogonalization", "stop_gradient")),
    ).to(device)
    model.load_state_dict(checkpoint["model"])
    model.eval()

    timings = _timed_forward(model, device, args.repeats)
    coordinates = uniform_grid(33).unsqueeze(0)
    convergence = []
    for name, values in CASES.items():
        parameter = torch.tensor(values)
        reference_high = solve_reference(
            parameter, cutoff=24, rank=2, mode_shape="hexagonal"
        )
        basis_high = periodic_mgs(evaluate_reference_basis(reference_high, coordinates))
        for cutoff in (8, 12, 16, 20):
            start = time.perf_counter()
            reference = solve_reference(
                parameter, cutoff=cutoff, rank=2, mode_shape="hexagonal"
            )
            elapsed = time.perf_counter() - start
            basis = periodic_mgs(evaluate_reference_basis(reference, coordinates))
            convergence.append(
                {
                    "case": name,
                    "cutoff": cutoff,
                    "projector_error_vs_cutoff24": projector_sine_error(basis, basis_high),
                    "eigenvalue_1_abs_error": abs(float(reference.eigenvalues[0] - reference_high.eigenvalues[0])),
                    "eigenvalue_2_abs_error": abs(float(reference.eigenvalues[1] - reference_high.eigenvalues[1])),
                    "solve_seconds": elapsed,
                }
            )

    result = {
        "status": "COMPLETE",
        "device": str(device),
        "device_name": torch.cuda.get_device_name(0) if device.type == "cuda" else str(device),
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "inference_grid_points": 33 * 33,
        "inference_repeats": args.repeats,
        "inference_seconds_mean": statistics.mean(timings),
        "inference_seconds_std": statistics.stdev(timings),
        "inference_seconds_p95": sorted(timings)[int(0.95 * (len(timings) - 1))],
        "reference_convergence": convergence,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

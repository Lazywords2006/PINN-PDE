"""Generate basis-invariant spectral-cluster density figures."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch

from block_kyfan_pinn.device import select_device
from block_kyfan_pinn.model import BlockKyFanPINN
from block_kyfan_pinn.physics import periodic_mgs
from block_kyfan_pinn.reference import evaluate_reference_basis, solve_reference, uniform_grid


CASES = {
    "interpolation": (0.31, 0.35, 0.35, 0.05),
    "symmetric_cluster": (1.0 / 3.0, 1.0 / 3.0, 0.60, 0.0),
    "extrapolation": (0.42, 0.24, 0.90, 0.16),
}


def density(basis: torch.Tensor) -> torch.Tensor:
    return basis.square().sum(dim=(-1, -2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--grid-side", type=int, default=65)
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
    args.output_dir.mkdir(parents=True, exist_ok=True)

    coordinates_cpu = uniform_grid(args.grid_side)
    for name, values in CASES.items():
        coordinates = coordinates_cpu.unsqueeze(0).to(device)
        parameters = torch.tensor([values], device=device)
        with torch.no_grad():
            prediction = model(coordinates, parameters).cpu()
        reference = solve_reference(torch.tensor(values), cutoff=8, rank=2)
        reference_basis = periodic_mgs(evaluate_reference_basis(reference, coordinates_cpu.unsqueeze(0)))
        predicted_density = density(prediction)[0].reshape(args.grid_side, args.grid_side).numpy()
        reference_density = density(reference_basis)[0].reshape(args.grid_side, args.grid_side).numpy()
        absolute_error = np.abs(predicted_density - reference_density)
        np.savez_compressed(
            args.output_dir / f"{name}_cluster_density.npz",
            predicted=predicted_density,
            reference=reference_density,
            absolute_error=absolute_error,
        )
        figure, axes = plt.subplots(1, 3, figsize=(12, 3.5), constrained_layout=True)
        for axis, image, title in zip(
            axes,
            (predicted_density, reference_density, absolute_error),
            ("Predicted cluster density", "Reference cluster density", "Absolute density error"),
        ):
            rendered = axis.imshow(image, origin="lower", cmap="viridis")
            axis.set_title(title)
            axis.set_xlabel("s1 grid")
            axis.set_ylabel("s2 grid")
            figure.colorbar(rendered, ax=axis, fraction=0.046)
        figure.suptitle(name.replace("_", " ").title())
        figure.savefig(args.output_dir / f"{name}_cluster_density.png", dpi=180)
        plt.close(figure)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

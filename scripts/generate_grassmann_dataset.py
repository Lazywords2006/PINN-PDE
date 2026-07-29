"""Generate PWE-labelled training data for the supervised Grassmann upper bound."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.physics import periodic_mgs
from block_kyfan_pinn.reference import evaluate_reference_basis, solve_reference, uniform_grid


BOUNDS = {
    "harmonic_honeycomb": [(0.28, 0.38), (0.28, 0.38), (0.20, 0.80), (-0.08, 0.08)],
    "gaussian_honeycomb": [(0.28, 0.38), (0.28, 0.38), (1.0, 4.0), (0.18, 0.35), (-0.08, 0.08)],
}


def _lhs(count: int, bounds: list[tuple[float, float]], seed: int) -> torch.Tensor:
    rng = random.Random(seed)
    columns = []
    for low, high in bounds:
        values = [low + (high - low) * ((index + rng.random()) / count) for index in range(count)]
        rng.shuffle(values); columns.append(values)
    return torch.tensor([[column[index] for column in columns] for index in range(count)], dtype=torch.float32)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("family", choices=tuple(BOUNDS))
    parser.add_argument("output", type=Path)
    parser.add_argument("--count", type=int, default=1024)
    parser.add_argument("--grid-side", type=int, default=33)
    parser.add_argument("--cutoff", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260714)
    args = parser.parse_args()
    parameters = _lhs(args.count, BOUNDS[args.family], args.seed)
    coordinates = uniform_grid(args.grid_side).unsqueeze(0)
    bases = []
    for index, values in enumerate(parameters):
        solution = solve_reference(values, cutoff=args.cutoff, rank=2, potential_family=args.family)
        bases.append(periodic_mgs(evaluate_reference_basis(solution, coordinates))[0].to(torch.float32))
        if (index + 1) % 50 == 0:
            print(f"generated {index + 1}/{args.count}", flush=True)
    payload = {
        "metadata": {"family": args.family, "count": args.count, "grid_side": args.grid_side,
                     "cutoff": args.cutoff, "seed": args.seed, "label_source": "plane_wave_eigh"},
        "parameters": parameters,
        "basis": torch.stack(bases),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, args.output)
    args.output.with_suffix(".json").write_text(json.dumps(payload["metadata"], indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

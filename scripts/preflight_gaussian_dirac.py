"""Cheap PWE preflight for the Gaussian family's K-point rank-two cluster."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from block_kyfan_pinn.reference import solve_reference


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("output", type=Path); args = parser.parse_args()
    rows = []
    for amplitude in (1.0, 2.0, 3.0, 4.0):
        for sigma in (0.18, 0.26, 0.35):
            parameters = torch.tensor([1 / 3, 1 / 3, amplitude, sigma, 0.0], dtype=torch.float64)
            values = solve_reference(parameters, cutoff=8, rank=4,
                                     potential_family="gaussian_honeycomb").eigenvalues
            rows.append({"amplitude": amplitude, "sigma": sigma,
                         "eigenvalues": [float(value) for value in values],
                         "internal_gap": float(values[1] - values[0]),
                         "external_gap": float(values[2] - values[1])})
    result = {"status": "PASS" if max(row["internal_gap"] for row in rows) < 5e-5 and
              min(row["external_gap"] for row in rows) > 1e-2 else "FAIL",
              "cutoff": 8, "max_internal_gap": max(row["internal_gap"] for row in rows),
              "min_external_gap": min(row["external_gap"] for row in rows), "cases": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n"); print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__": raise SystemExit(main())

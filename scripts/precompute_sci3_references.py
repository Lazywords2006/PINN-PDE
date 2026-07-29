"""Precompute frozen-suite PWE references once for reuse by every method/seed."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.physics import periodic_mgs
from block_kyfan_pinn.reference import ReferenceSolution, evaluate_reference_basis, solve_reference, uniform_grid


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--grid-side", type=int, default=33)
    parser.add_argument("--cutoff", type=int, default=8)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    suite_bytes = args.suite.read_bytes(); suite = json.loads(suite_bytes)
    coordinates = uniform_grid(args.grid_side).unsqueeze(0)
    references = {}
    points = suite["points"] if args.limit is None else suite["points"][:args.limit]
    for index, point in enumerate(points):
        parameters = torch.tensor(point["parameters"], dtype=torch.float64)
        solution = solve_reference(parameters, cutoff=args.cutoff, rank=3,
                                   potential_family=point["family"])
        rank_two = ReferenceSolution(solution.eigenvalues[:2], solution.eigenvectors[:, :2], solution.modes)
        basis = periodic_mgs(evaluate_reference_basis(rank_two, coordinates))[0].to(torch.float32)
        references[point["id"]] = {"eigenvalues": solution.eigenvalues.to(torch.float64), "basis": basis}
        if (index + 1) % 25 == 0: print(f"precomputed {index + 1}/{len(points)}", flush=True)
    payload = {"metadata": {"suite_id": suite["suite_id"],
                            "suite_sha256": hashlib.sha256(suite_bytes).hexdigest(),
                            "grid_side": args.grid_side, "cutoff": args.cutoff},
               "references": references}
    args.output.parent.mkdir(parents=True, exist_ok=True); torch.save(payload, args.output)
    args.output.with_suffix(".json").write_text(json.dumps(payload["metadata"], indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

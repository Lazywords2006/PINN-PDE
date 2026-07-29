"""Cutoff convergence and external-gap audit for the frozen SCI-Q3 suite."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.metrics import projector_sine_error
from block_kyfan_pinn.physics import periodic_mgs
from block_kyfan_pinn.reference import ReferenceSolution, evaluate_reference_basis, solve_reference, uniform_grid


def _percentile(values: list[float], q: float) -> float:
    values = sorted(values); index = (len(values) - 1) * q
    low, high = int(index), min(int(index) + 1, len(values) - 1); weight = index - low
    return values[low] * (1 - weight) + values[high] * weight


def _basis(solution: ReferenceSolution, coordinates: torch.Tensor) -> torch.Tensor:
    rank_two = ReferenceSolution(solution.eigenvalues[:2], solution.eigenvectors[:, :2], solution.modes)
    return periodic_mgs(evaluate_reference_basis(rank_two, coordinates))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", type=Path)
    parser.add_argument("family", choices=("harmonic_honeycomb", "gaussian_honeycomb"))
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    suite = json.loads(args.suite.read_text())
    points = [point for point in suite["points"] if point["family"] == args.family]
    if args.limit: points = points[:args.limit]
    coordinates = uniform_grid(33).unsqueeze(0)
    rows = []
    for index, point in enumerate(points):
        parameters = torch.tensor(point["parameters"], dtype=torch.float64)
        solutions = {cutoff: solve_reference(parameters, cutoff=cutoff, rank=3,
                                              potential_family=args.family) for cutoff in (8, 12, 16)}
        reference = solutions[16]
        row = {"id": point["id"], "split": point["split"],
               "internal_gap": float(reference.eigenvalues[1] - reference.eigenvalues[0]),
               "external_gap": float(reference.eigenvalues[2] - reference.eigenvalues[1])}
        for cutoff in (8, 12):
            row[f"projector_cutoff_{cutoff}_vs_16"] = projector_sine_error(
                _basis(solutions[cutoff], coordinates), _basis(reference, coordinates))
            row[f"eigen_relative_cutoff_{cutoff}_vs_16"] = float(
                ((solutions[cutoff].eigenvalues[:2] - reference.eigenvalues[:2]).abs() /
                 reference.eigenvalues[:2].abs().clamp_min(1e-12)).max())
        rows.append(row)
        if (index + 1) % 25 == 0: print(f"audited {index + 1}/{len(points)}", flush=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "per_parameter.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    gaps = [float(row["external_gap"]) for row in rows]
    result = {"status": "COMPLETE", "family": args.family, "n": len(rows),
              "external_gap": {"minimum": min(gaps), "p05": _percentile(gaps, .05),
                               "median": statistics.median(gaps)},
              "cutoff_8_vs_16": {
                  "projector_max": max(float(row["projector_cutoff_8_vs_16"]) for row in rows),
                  "eigen_relative_max": max(float(row["eigen_relative_cutoff_8_vs_16"]) for row in rows),
              }}
    (args.output_dir / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())

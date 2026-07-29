"""Fair many-query timing: neural forward versus CPU assembly + GPU batched eigh."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.device import select_device, synchronize
from block_kyfan_pinn.experiment import ExperimentConfig
from block_kyfan_pinn.model import BlockKyFanPINN
from block_kyfan_pinn.reference import plane_wave_hamiltonian, uniform_grid


def _sample(config: ExperimentConfig, count: int) -> torch.Tensor:
    generator = torch.Generator().manual_seed(20260712)
    lower = torch.tensor(config.parameter_lower)
    upper = torch.tensor(config.parameter_upper)
    return lower + torch.rand((count, len(lower)), generator=generator) * (upper - lower)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("training_summary", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--batches", default="1,8,32,128")
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()
    config = ExperimentConfig.from_json(args.config)
    batches = tuple(int(value) for value in args.batches.split(","))
    max_batch = max(batches)
    device = select_device(config.device)
    model = BlockKyFanPINN(width=config.width, hidden_layers=config.hidden_layers,
                           anchor_kind=config.anchor_kind, anchor_scale=config.anchor_scale,
                           parameter_dim=len(config.parameter_lower),
                           orthogonalization=config.orthogonalization).to(device).eval()
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False)
    if checkpoint.get("config_fingerprint") is None:
        raise ValueError("checkpoint is missing immutable configuration provenance")
    model.load_state_dict(checkpoint["model"])
    parameters_cpu = _sample(config, max_batch)
    coordinates = uniform_grid(config.eval_grid_side).unsqueeze(0).to(device)

    assembly_start = time.perf_counter()
    matrices = torch.stack([
        plane_wave_hamiltonian(values, cutoff=config.reference_cutoff,
                               potential_family=config.potential_family)[0]
        for values in parameters_cpu
    ])
    assembly_total = time.perf_counter() - assembly_start
    rows = []
    with torch.no_grad():
        for batch in batches:
            parameters = parameters_cpu[:batch].to(device)
            coords = coordinates.expand(batch, -1, -1)
            for _ in range(3): model(coords, parameters)
            synchronize(device)
            neural = []
            for _ in range(args.repeats):
                start = time.perf_counter(); model(coords, parameters); synchronize(device)
                neural.append(time.perf_counter() - start)
            matrix_batch = matrices[:batch].to(device)
            for _ in range(2): torch.linalg.eigvalsh(matrix_batch)
            synchronize(device)
            eigh = []
            for _ in range(args.repeats):
                start = time.perf_counter(); torch.linalg.eigvalsh(matrix_batch); synchronize(device)
                eigh.append(time.perf_counter() - start)
            rows.append({
                "batch": batch,
                "neural_seconds": statistics.mean(neural),
                "neural_seconds_per_query": statistics.mean(neural) / batch,
                "gpu_eigh_seconds": statistics.mean(eigh),
                "gpu_eigh_seconds_per_query": statistics.mean(eigh) / batch,
                "cpu_assembly_seconds_per_query": assembly_total / max_batch,
                "classical_total_seconds_per_query": assembly_total / max_batch + statistics.mean(eigh) / batch,
            })
    training = json.loads(args.training_summary.read_text())
    training_seconds = statistics.mean(float(run["elapsed_seconds"]) for run in training["runs"])
    for row in rows:
        saving = float(row["classical_total_seconds_per_query"]) - float(row["neural_seconds_per_query"])
        row["break_even_queries"] = training_seconds / saving if saving > 0 else None
    input_width = 4 + len(config.parameter_lower)
    mlp_flops_per_point = 2 * (input_width * config.width +
                               (config.hidden_layers - 1) * config.width * config.width +
                               config.width * 4)
    result = {"status": "COMPLETE", "device": str(device), "family": config.potential_family,
              "training_seconds_per_seed": training_seconds, "parameter_count": sum(p.numel() for p in model.parameters()),
              "mlp_flops_per_spatial_field_estimate": mlp_flops_per_point * config.eval_grid_side ** 2,
              "timings": rows,
              "fairness_note": "GPU eig timing excludes CPU matrix assembly; classical_total includes measured assembly"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Train the label-using Grassmann subspace-regression performance upper bound."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from dataclasses import asdict
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.device import select_device, synchronize
from block_kyfan_pinn.experiment import ExperimentConfig, _config_fingerprint, _source_fingerprint
from block_kyfan_pinn.model import GalerkinSubspacePINN
from block_kyfan_pinn.physics import subspace_inclusion_loss
from block_kyfan_pinn.reference import uniform_grid


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("dataset", type=Path)
    args = parser.parse_args()
    config = ExperimentConfig.from_json(args.config)
    if config.method != "supervised_grassmann":
        parser.error("config method must be supervised_grassmann")
    if len(config.seeds) != len(set(config.seeds)):
        parser.error("config seeds must be unique")
    data = torch.load(args.dataset, map_location="cpu")
    if data["metadata"]["family"] != config.potential_family:
        parser.error("dataset/config potential family mismatch")
    device = select_device(config.device)
    dtype = torch.float64 if config.dtype == "float64" else torch.float32
    coordinates = uniform_grid(int(data["metadata"]["grid_side"]), dtype=dtype).unsqueeze(0).to(device)
    parameters_all = data["parameters"]
    basis_all = data["basis"]
    root = Path(config.output_dir)
    if root.is_dir() and any(root.iterdir()):
        parser.error(f"refusing to overwrite immutable supervised output: {root}")
    root.mkdir(parents=True, exist_ok=True)
    fingerprint = _config_fingerprint(config)
    source_fingerprint = _source_fingerprint()
    trainer_source_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    dataset_sha256 = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    runs = []
    for seed in config.seeds:
        seed_dir = root / f"seed_{seed}"
        seed_dir.mkdir(parents=True, exist_ok=False)
        torch.manual_seed(seed)
        sample_generator = torch.Generator(device="cpu").manual_seed(seed + 1_000_003)
        model = GalerkinSubspacePINN(width=config.width, hidden_layers=config.hidden_layers,
                                     parameter_dim=parameters_all.shape[1], subspace_rank=config.subspace_rank).to(
                                         device=device, dtype=dtype)
        optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
        rows = []
        start = time.perf_counter()
        for step in range(config.steps):
            indices = torch.randint(
                len(parameters_all), (config.parameter_batch,), generator=sample_generator
            )
            parameters = parameters_all[indices].to(device=device, dtype=dtype)
            target = basis_all[indices].to(device=device, dtype=dtype)
            coords = coordinates.expand(config.parameter_batch, -1, -1)
            optimizer.zero_grad(set_to_none=True)
            predicted = model(coords, parameters)
            loss = subspace_inclusion_loss(predicted, target)
            loss.backward(); optimizer.step()
            if step == 0 or (step + 1) % 100 == 0 or step + 1 == config.steps:
                rows.append({"step": step + 1, "loss": float(loss.detach().cpu())})
        synchronize(device)
        elapsed = time.perf_counter() - start
        checkpoint = {
            "model": model.state_dict(),
            "config": asdict(config),
            "config_fingerprint": fingerprint,
            "source_fingerprint": source_fingerprint,
            "trainer_source_sha256": trainer_source_sha256,
            "seed": seed,
            "sample_rng_state": sample_generator.get_state(),
            "dataset_sha256": dataset_sha256,
        }
        checkpoint_path = seed_dir / "final.pt"
        torch.save(checkpoint, checkpoint_path)
        with (seed_dir / "training.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=("step", "loss")); writer.writeheader(); writer.writerows(rows)
        runs.append({"seed": seed, "elapsed_seconds": elapsed, "final_loss": rows[-1]["loss"],
                     "checkpoint_sha256": hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()})
    summary = {"status": "COMPLETE", "config": asdict(config), "config_fingerprint": fingerprint,
               "source_fingerprint": source_fingerprint, "trainer_source_sha256": trainer_source_sha256,
               "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
               "dataset": str(args.dataset), "dataset_sha256": dataset_sha256, "runs": runs,
               "environment": {"python": platform.python_version(), "torch": torch.__version__, "device": str(device)}}
    (root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

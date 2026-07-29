"""Safe staged entry point; long CUDA runs require an explicit flag."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from block_kyfan_pinn.experiment import ExperimentConfig, pilot_gate, run_experiment
from block_kyfan_pinn.smoke import SmokeConfig, run_smoke


def main() -> int:
    parser = argparse.ArgumentParser()
    stage = parser.add_mutually_exclusive_group(required=True)
    stage.add_argument("--smoke", action="store_true")
    stage.add_argument("--pilot", action="store_true")
    stage.add_argument("--formal", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        result = run_smoke(SmokeConfig(), Path("results/smoke/smoke_result.json"))
        print(f"smoke={result['status']} device={result['device']}")
        return 0 if result["status"] == "PASS" else 1
    if args.pilot:
        parser.error(
            "legacy pilot retired after the V1 protocol audit; use the falsification V2 workflow"
        )
        config_name = "pilot_cuda.json" if torch.cuda.is_available() else "pilot_mps.json"
        config = ExperimentConfig.from_json(Path("configs") / config_name)
        run_experiment(config)
        print(f"pilot=COMPLETE; inspect {config.output_dir}/summary.json")
        return 0
    parser.error(
        "legacy formal matrix retired after the V1 protocol audit; freeze a new V2 suite before CUDA training"
    )
    if not torch.cuda.is_available():
        parser.error("--formal requires CUDA; no formal result was started")
    pilot_path = Path("results/pilot_cuda/summary.json")
    if not pilot_path.is_file():
        parser.error("--formal requires a completed CUDA pilot; run --pilot first")
    passed, reasons = pilot_gate(json.loads(pilot_path.read_text()))
    if not passed:
        parser.error("CUDA pilot did not pass promotion gates: " + "; ".join(reasons))
    for name in (
        "formal_cuda.json",
        "ablation_no_anchor_cuda.json",
        "ablation_wrong_anchor_cuda.json",
        "ablation_random_anchor_cuda.json",
        "ablation_no_residual_cuda.json",
        "baseline_ordered_pinn_cuda.json",
    ):
        run_experiment(ExperimentConfig.from_json(Path("configs") / name))
    print("formal core+anchor ablations COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

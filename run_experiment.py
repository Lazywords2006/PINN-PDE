"""Run a configured Block KyFan-PINN experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from block_kyfan_pinn.experiment import ExperimentConfig, run_experiment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    result = run_experiment(ExperimentConfig.from_json(args.config))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

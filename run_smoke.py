"""Run the basic engineering smoke test and persist its evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from block_kyfan_pinn.smoke import SmokeConfig, run_smoke


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--device", default="auto", choices=("auto", "cpu", "mps", "cuda", "rocm")
    )
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--points", type=int, default=96)
    parser.add_argument("--output", type=Path, default=Path("results/smoke/smoke_result.json"))
    args = parser.parse_args()
    result = run_smoke(
        SmokeConfig(device=args.device, steps=args.steps, points=args.points),
        output_path=args.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verify that a CPU, CUDA, ROCm, or MPS runtime supports required operations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from block_kyfan_pinn.accelerator import accelerator_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--backend", default="auto", choices=("auto", "cpu", "mps", "cuda", "rocm")
    )
    parser.add_argument("--expected-name", help="case-insensitive substring required in device name")
    parser.add_argument("--min-vram-gb", type=float, default=0.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = accelerator_report(args.backend)
    failures: list[str] = []
    if args.expected_name and args.expected_name.lower() not in str(report["device_name"]).lower():
        failures.append(
            f"device name {report['device_name']!r} does not contain {args.expected_name!r}"
        )
    minimum_bytes = int(args.min_vram_gb * 2**30)
    if int(report["total_memory_bytes"]) < minimum_bytes:
        failures.append(
            f"VRAM is below {args.min_vram_gb:.2f} GiB: "
            f"{int(report['total_memory_bytes']) / 2**30:.2f} GiB detected"
        )
    if failures:
        report["status"] = "FAIL"
        report["requirements_failures"] = failures

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

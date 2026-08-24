#!/usr/bin/env python3
"""Generate the disjoint SCI-Q3 journal-baseline supplement and references."""

from __future__ import annotations

import argparse
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.suites import load_frozen_suite, write_frozen_suite
from scripts.generate_risk_development import build_reference_cache
from scripts.generate_v2_assets import (
    TRAINING_BOUNDS,
    _generate_family_points,
    build_suite_payload,
)

Q3_SUITE_SEED = 2026082411
Q3_FAMILIES = ("harmonic_honeycomb", "gaussian_honeycomb")
Q3_COUNTS = {
    "iid_hidden": 16,
    "exact_cluster": 16,
    "near_cluster": 24,
    "strict_ood": 16,
    "gap_scan": 8,
}
EARLIER_SUITES = (
    "v2_validation.json",
    "v2_frozen_test.json",
    "risk_development_v1.json",
    "p1_validation_v1.json",
    "p2_validation_v1.json",
)


def _identity(point: dict[str, object]) -> tuple[str, tuple[float, ...]]:
    return str(point["family"]), tuple(float(value) for value in point["parameters"])


def _retarget(points: list[dict[str, object]], family: str) -> None:
    exact_index = 0
    gap_index = 0
    for point in points:
        parameters = [float(value) for value in point["parameters"]]
        split = str(point["split"])
        if split == "exact_cluster":
            low, high = TRAINING_BOUNDS[family][2]
            parameters[2] = low + (high - low) * (
                (exact_index + 0.37) / (Q3_COUNTS["exact_cluster"] + 0.83)
            )
            if family == "gaussian_honeycomb":
                sigma_low, sigma_high = TRAINING_BOUNDS[family][3]
                parameters[3] = sigma_low + (sigma_high - sigma_low) * (
                    (exact_index + 0.61) / (Q3_COUNTS["exact_cluster"] + 1.17)
                )
            parameters[-1] = 0.0
            exact_index += 1
        elif split == "gap_scan":
            fraction = (gap_index + 0.29) / (Q3_COUNTS["gap_scan"] + 0.58)
            parameters[0] = (1.0 / 3.0) + fraction * (0.5 - 1.0 / 3.0)
            parameters[1] = 1.0 / 3.0
            if family == "harmonic_honeycomb":
                parameters[2] = 0.625
            else:
                parameters[2] = 3.10
                parameters[3] = 0.31
            parameters[-1] = 0.0
            gap_index += 1
        point["parameters"] = parameters


def generate_q3_supplement_suite() -> list[dict[str, object]]:
    rng = random.Random(Q3_SUITE_SEED)
    points: list[dict[str, object]] = []
    for family in Q3_FAMILIES:
        generated = _generate_family_points(
            family,
            rng,
            n_iid=Q3_COUNTS["iid_hidden"],
            n_exact=Q3_COUNTS["exact_cluster"],
            n_near=Q3_COUNTS["near_cluster"],
            n_ood=Q3_COUNTS["strict_ood"],
            n_gap_scan=Q3_COUNTS["gap_scan"],
        )
        _retarget(generated, family)
        counters: Counter[str] = Counter()
        for point in generated:
            split = str(point["split"])
            index = counters[split]
            counters[split] += 1
            point["id"] = f"q3-{family}-{split}-{index:03d}"
            points.append(point)
    return points


def build_q3_suite_payload(points: list[dict[str, object]]) -> dict[str, object]:
    return build_suite_payload(
        points,
        suite_id="block-kyfan-q3-supplement-v1-20260824",
        seed=Q3_SUITE_SEED,
        purpose="independent_q3_journal_baseline_supplement_not_final",
    )


def validate_q3_disjointness(points: list[dict[str, object]], root: Path) -> None:
    identities = {_identity(point) for point in points}
    if len(identities) != len(points):
        raise ValueError("Q3 supplement contains duplicate parameters")
    earlier: set[tuple[str, tuple[float, ...]]] = set()
    for name in EARLIER_SUITES:
        payload, _ = load_frozen_suite(root / "benchmarks" / name)
        earlier.update(_identity(point) for point in payload["points"])
    overlap = identities & earlier
    if overlap:
        raise ValueError(
            f"Q3 supplement overlaps earlier suites at {len(overlap)} points"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--suite-only", action="store_true")
    mode.add_argument("--cache-only", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("benchmarks/q3_supplement_v1.json")
    )
    parser.add_argument(
        "--cache-output", type=Path, default=Path("data/q3_supplement_v1_references.pt")
    )
    parser.add_argument("--cutoff", type=int, default=24)
    parser.add_argument("--grid-side", type=int, default=33)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output = args.output if args.output.is_absolute() else root / args.output
    cache = (
        args.cache_output
        if args.cache_output.is_absolute()
        else root / args.cache_output
    )
    if args.suite_only:
        points = generate_q3_supplement_suite()
        validate_q3_disjointness(points, root)
        digest = write_frozen_suite(build_q3_suite_payload(points), output)
        print(f"Q3_SUITE={output}")
        print(f"Q3_SUITE_POINTS={len(points)}")
        print(f"Q3_SUITE_SHA256={digest}")
        return 0

    suite, _ = load_frozen_suite(output)
    if suite.get("suite_id") != "block-kyfan-q3-supplement-v1-20260824":
        raise ValueError("unexpected Q3 supplement suite id")
    digest = build_reference_cache(
        output, cache, cutoff=args.cutoff, grid_side=args.grid_side, rank=3
    )
    print(f"Q3_REFERENCE_CACHE={cache}")
    print(f"Q3_REFERENCE_CACHE_SHA256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

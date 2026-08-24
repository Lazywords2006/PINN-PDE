#!/usr/bin/env python3
"""Generate the independent P2 full-shell pilot suite and references."""

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

P2_SUITE_SEED = 2026082404
P2_FAMILIES = ("harmonic_honeycomb", "gaussian_honeycomb")
P2_COUNTS = {
    "iid_hidden": 8,
    "exact_cluster": 8,
    "near_cluster": 16,
    "strict_ood": 8,
    "gap_scan": 8,
}


def _identity(point: dict[str, object]) -> tuple[str, tuple[float, ...]]:
    return str(point["family"]), tuple(
        float(value) for value in point["parameters"]
    )


def _retarget(points: list[dict[str, object]], family: str) -> None:
    exact_index = 0
    gap_index = 0
    for point in points:
        parameters = [float(value) for value in point["parameters"]]
        if point["split"] == "exact_cluster":
            low, high = TRAINING_BOUNDS[family][2]
            fraction = (exact_index + 0.19) / 9.31
            parameters[2] = low + fraction * (high - low)
            if family == "gaussian_honeycomb":
                sigma_low, sigma_high = TRAINING_BOUNDS[family][3]
                sigma_fraction = (exact_index + 0.83) / 9.43
                parameters[3] = sigma_low + sigma_fraction * (
                    sigma_high - sigma_low
                )
            parameters[-1] = 0.0
            exact_index += 1
        elif point["split"] == "gap_scan":
            fraction = (gap_index + 0.73) / 9.11
            parameters[0] = (1.0 / 3.0) + fraction * (
                0.5 - 1.0 / 3.0
            )
            parameters[1] = 1.0 / 3.0
            if family == "harmonic_honeycomb":
                parameters[2] = 0.575
            else:
                parameters[2] = 2.75
                parameters[3] = 0.285
            parameters[-1] = 0.0
            gap_index += 1
        point["parameters"] = parameters


def generate_p2_validation_suite() -> list[dict[str, object]]:
    rng = random.Random(P2_SUITE_SEED)
    points: list[dict[str, object]] = []
    for family in P2_FAMILIES:
        generated = _generate_family_points(
            family,
            rng,
            n_iid=P2_COUNTS["iid_hidden"],
            n_exact=P2_COUNTS["exact_cluster"],
            n_near=P2_COUNTS["near_cluster"],
            n_ood=P2_COUNTS["strict_ood"],
            n_gap_scan=P2_COUNTS["gap_scan"],
        )
        _retarget(generated, family)
        counters: Counter[str] = Counter()
        for point in generated:
            split = str(point["split"])
            index = counters[split]
            counters[split] += 1
            point["id"] = f"p2-{family}-{split}-{index:03d}"
            points.append(point)
    return points


def build_p2_suite_payload(
    points: list[dict[str, object]],
) -> dict[str, object]:
    return build_suite_payload(
        points,
        suite_id="block-kyfan-p2-validation-v1-20260824",
        seed=P2_SUITE_SEED,
        purpose="p2_full_shell_independent_pilot_not_final_test",
    )


def validate_p2_suite_disjointness(
    points: list[dict[str, object]], root: Path
) -> None:
    identities = {_identity(point) for point in points}
    if len(identities) != len(points):
        raise ValueError("P2 suite contains duplicate parameters")
    earlier: set[tuple[str, tuple[float, ...]]] = set()
    for name in (
        "v2_validation.json",
        "v2_frozen_test.json",
        "risk_development_v1.json",
        "p1_validation_v1.json",
    ):
        payload, _ = load_frozen_suite(root / "benchmarks" / name)
        earlier.update(_identity(point) for point in payload["points"])
    if not identities.isdisjoint(earlier):
        raise ValueError("P2 suite overlaps an earlier decision suite")


def build_p2_reference_cache(
    suite_path: Path,
    output_path: Path,
    *,
    cutoff: int = 24,
    grid_side: int = 33,
    rank: int = 3,
) -> str:
    suite, _ = load_frozen_suite(suite_path)
    if suite.get("suite_id") != "block-kyfan-p2-validation-v1-20260824":
        raise ValueError("unexpected P2 suite id")
    return build_reference_cache(
        suite_path,
        output_path,
        cutoff=cutoff,
        grid_side=grid_side,
        rank=rank,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite-only", action="store_true")
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--device", default="cpu", choices=("cpu",))
    parser.add_argument("--cutoff", type=int, default=24)
    parser.add_argument("--grid-side", type=int, default=33)
    parser.add_argument("--rank", type=int, default=3)
    parser.add_argument(
        "--output", type=Path, default=Path("benchmarks/p2_validation_v1.json")
    )
    parser.add_argument(
        "--cache-output",
        type=Path,
        default=Path("data/p2_validation_v1_references.pt"),
    )
    args = parser.parse_args()
    if args.suite_only == args.cache_only:
        parser.error("choose exactly one of --suite-only or --cache-only")
    root = Path(__file__).resolve().parents[1]
    output = args.output if args.output.is_absolute() else root / args.output
    if args.cache_only:
        cache = (
            args.cache_output
            if args.cache_output.is_absolute()
            else root / args.cache_output
        )
        digest = build_p2_reference_cache(
            output,
            cache,
            cutoff=args.cutoff,
            grid_side=args.grid_side,
            rank=args.rank,
        )
        print(f"P2_REFERENCE_CACHE={cache}")
        print(f"P2_REFERENCE_CACHE_SHA256={digest}")
        return 0
    points = generate_p2_validation_suite()
    validate_p2_suite_disjointness(points, root)
    digest = write_frozen_suite(build_p2_suite_payload(points), output)
    print(f"P2_SUITE={output}")
    print(f"P2_SUITE_POINTS={len(points)}")
    print(f"P2_SUITE_SHA256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


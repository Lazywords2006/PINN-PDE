#!/usr/bin/env python3
"""Generate the independent P1 risk-gated-corrector pilot suite."""

from __future__ import annotations

import argparse
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.suites import load_frozen_suite, write_frozen_suite
from scripts.generate_v2_assets import (
    TRAINING_BOUNDS,
    _generate_family_points,
    build_suite_payload,
)

P1_SUITE_SEED = 2026082403
P1_FAMILIES = ("harmonic_honeycomb", "gaussian_honeycomb")
P1_COUNTS = {
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


def _retarget_deterministic_points(
    points: list[dict[str, object]], *, family: str
) -> None:
    """Keep cluster semantics while avoiding earlier deterministic grids."""

    exact_index = 0
    gap_index = 0
    for point in points:
        parameters = [float(value) for value in point["parameters"]]
        split = str(point["split"])
        if split == "exact_cluster":
            amplitude_low, amplitude_high = TRAINING_BOUNDS[family][2]
            fraction = (exact_index + 0.37) / 8.73
            parameters[2] = amplitude_low + fraction * (
                amplitude_high - amplitude_low
            )
            if family == "gaussian_honeycomb":
                sigma_low, sigma_high = TRAINING_BOUNDS[family][3]
                sigma_fraction = (exact_index + 0.61) / 9.17
                parameters[3] = sigma_low + sigma_fraction * (
                    sigma_high - sigma_low
                )
            parameters[-1] = 0.0
            exact_index += 1
        elif split == "gap_scan":
            fraction = (gap_index + 0.41) / 8.89
            parameters[0] = (1.0 / 3.0) + fraction * (
                0.5 - 1.0 / 3.0
            )
            parameters[1] = 1.0 / 3.0
            if family == "harmonic_honeycomb":
                parameters[2] = 0.55
            else:
                parameters[2] = 2.6
                parameters[3] = 0.27
            parameters[-1] = 0.0
            gap_index += 1
        point["parameters"] = parameters


def generate_p1_validation_suite() -> list[dict[str, object]]:
    """Return the frozen 96-point P1 pilot parameter suite."""

    rng = random.Random(P1_SUITE_SEED)
    points: list[dict[str, object]] = []
    for family in P1_FAMILIES:
        generated = _generate_family_points(
            family,
            rng,
            n_iid=P1_COUNTS["iid_hidden"],
            n_exact=P1_COUNTS["exact_cluster"],
            n_near=P1_COUNTS["near_cluster"],
            n_ood=P1_COUNTS["strict_ood"],
            n_gap_scan=P1_COUNTS["gap_scan"],
        )
        _retarget_deterministic_points(generated, family=family)
        counters: Counter[str] = Counter()
        for point in generated:
            split = str(point["split"])
            index = counters[split]
            counters[split] += 1
            point["id"] = f"p1-{family}-{split}-{index:03d}"
            points.append(point)
    return points


def build_p1_suite_payload(
    points: list[dict[str, object]],
) -> dict[str, object]:
    """Wrap P1 points in the repository's frozen-suite schema."""

    return build_suite_payload(
        points,
        suite_id="block-kyfan-p1-validation-v1-20260824",
        seed=P1_SUITE_SEED,
        purpose="p1_risk_gated_corrector_pilot_not_final_test",
    )


def validate_p1_suite_disjointness(
    points: list[dict[str, object]], root: Path
) -> None:
    """Reject duplicates and overlap with every earlier decision suite."""

    identities = {_identity(point) for point in points}
    if len(identities) != len(points):
        raise ValueError("P1 suite contains duplicate parameters")
    earlier: set[tuple[str, tuple[float, ...]]] = set()
    for name in (
        "v2_validation.json",
        "v2_frozen_test.json",
        "risk_development_v1.json",
    ):
        payload, _ = load_frozen_suite(root / "benchmarks" / name)
        earlier.update(_identity(point) for point in payload["points"])
    if not identities.isdisjoint(earlier):
        raise ValueError("P1 parameters overlap an earlier decision suite")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite-only", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/p1_validation_v1.json"),
    )
    args = parser.parse_args()
    if not args.suite_only:
        parser.error("--suite-only is required until the cache task is implemented")
    root = Path(__file__).resolve().parents[1]
    output = args.output if args.output.is_absolute() else root / args.output
    points = generate_p1_validation_suite()
    validate_p1_suite_disjointness(points, root)
    digest = write_frozen_suite(build_p1_suite_payload(points), output)
    print(f"P1_SUITE={output}")
    print(f"P1_SUITE_POINTS={len(points)}")
    print(f"P1_SUITE_SHA256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


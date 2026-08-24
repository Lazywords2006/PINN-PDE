#!/usr/bin/env python3
"""Generate the independent P0 risk calibration and held-out audit suite."""

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

RISK_CALIBRATION_SEED = 2026082401
RISK_AUDIT_SEED = 2026082402
RISK_SUITE_SEED = 20260824
RISK_FAMILIES = ("harmonic_honeycomb", "gaussian_honeycomb")
RISK_ROLES = ("calibration", "audit")
RISK_ROLE_COUNTS = {
    "iid_hidden": 8,
    "exact_cluster": 4,
    "near_cluster": 10,
    "strict_ood": 8,
    "gap_scan": 10,
}


def _retarget_deterministic_points(
    points: list[dict[str, object]], *, role: str, family: str
) -> None:
    """Keep exact/gap semantics while making the two roles disjoint."""

    role_offset = 0.25 if role == "calibration" else 0.75
    exact_index = 0
    gap_index = 0
    for point in points:
        parameters = [float(value) for value in point["parameters"]]
        if point["split"] == "exact_cluster":
            amplitude_low, amplitude_high = TRAINING_BOUNDS[family][2]
            fraction = (exact_index + role_offset) / 5.0
            parameters[2] = amplitude_low + fraction * (
                amplitude_high - amplitude_low
            )
            if family == "gaussian_honeycomb":
                sigma_low, sigma_high = TRAINING_BOUNDS[family][3]
                sigma_fraction = (exact_index + 0.5 * role_offset) / 5.0
                parameters[3] = sigma_low + sigma_fraction * (
                    sigma_high - sigma_low
                )
            parameters[-1] = 0.0
            exact_index += 1
        elif point["split"] == "gap_scan":
            fraction = (gap_index + role_offset) / 11.0
            parameters[0] = (1.0 / 3.0) + fraction * (
                0.5 - 1.0 / 3.0
            )
            parameters[1] = 1.0 / 3.0
            if family == "harmonic_honeycomb":
                parameters[2] = 0.45 if role == "calibration" else 0.65
            else:
                parameters[2] = 2.1 if role == "calibration" else 3.1
                parameters[3] = 0.24 if role == "calibration" else 0.30
            parameters[-1] = 0.0
            gap_index += 1
        point["parameters"] = parameters


def generate_risk_development_suite() -> list[dict[str, object]]:
    """Return 160 deterministic, role-labelled, split-balanced points."""

    points: list[dict[str, object]] = []
    role_seeds = {
        "calibration": RISK_CALIBRATION_SEED,
        "audit": RISK_AUDIT_SEED,
    }
    for role in RISK_ROLES:
        rng = random.Random(role_seeds[role])
        for family in RISK_FAMILIES:
            generated = _generate_family_points(
                family,
                rng,
                n_iid=RISK_ROLE_COUNTS["iid_hidden"],
                n_exact=RISK_ROLE_COUNTS["exact_cluster"],
                n_near=RISK_ROLE_COUNTS["near_cluster"],
                n_ood=RISK_ROLE_COUNTS["strict_ood"],
                n_gap_scan=RISK_ROLE_COUNTS["gap_scan"],
            )
            _retarget_deterministic_points(
                generated, role=role, family=family
            )
            counters: Counter[str] = Counter()
            for point in generated:
                split = str(point["split"])
                index = counters[split]
                counters[split] += 1
                point["role"] = role
                point["id"] = (
                    f"risk-{role}-{family}-{split}-{index:03d}"
                )
                points.append(point)
    return points


def build_risk_suite_payload(
    points: list[dict[str, object]],
) -> dict[str, object]:
    """Wrap risk points with immutable role and generation metadata."""

    payload = build_suite_payload(
        points,
        suite_id="block-kyfan-risk-development-v1-20260824",
        seed=RISK_SUITE_SEED,
        purpose="risk_calibration_and_heldout_audit_not_final_test",
    )
    payload["role_seeds"] = {
        "calibration": RISK_CALIBRATION_SEED,
        "audit": RISK_AUDIT_SEED,
    }
    payload["role_counts"] = dict(
        Counter(str(point["role"]) for point in points)
    )
    payload["role_family_counts"] = {
        f"{role}:{family}": sum(
            point["role"] == role and point["family"] == family
            for point in points
        )
        for role in RISK_ROLES
        for family in RISK_FAMILIES
    }
    return payload


def _identity(
    point: dict[str, object],
) -> tuple[str, tuple[float, ...]]:
    return str(point["family"]), tuple(
        float(value) for value in point["parameters"]
    )


def validate_risk_suite_disjointness(
    points: list[dict[str, object]], root: Path
) -> None:
    """Reject role leakage and overlap with validation or frozen final."""

    by_role = {
        role: {
            _identity(point) for point in points if point["role"] == role
        }
        for role in RISK_ROLES
    }
    if not by_role["calibration"].isdisjoint(by_role["audit"]):
        raise ValueError("risk calibration and audit parameters overlap")
    committed: set[tuple[str, tuple[float, ...]]] = set()
    for name in ("v2_validation.json", "v2_frozen_test.json"):
        payload, _ = load_frozen_suite(root / "benchmarks" / name)
        committed.update(_identity(point) for point in payload["points"])
    for role, identities in by_role.items():
        if not identities.isdisjoint(committed):
            raise ValueError(f"risk {role} parameters overlap V2 assets")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite-only", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/risk_development_v1.json"),
    )
    args = parser.parse_args()
    if not args.suite_only:
        parser.error("P0 reference caching is added in the next implementation task")
    root = Path(__file__).resolve().parents[1]
    points = generate_risk_development_suite()
    validate_risk_suite_disjointness(points, root)
    payload = build_risk_suite_payload(points)
    output = args.output if args.output.is_absolute() else root / args.output
    digest = write_frozen_suite(payload, output)
    print(f"RISK_SUITE={output}")
    print(f"RISK_SUITE_POINTS={len(points)}")
    print(f"RISK_SUITE_SHA256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Generate immutable validation/test parameter suites for the SCI-Q3 matrix."""

from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmarks"
SEED = 20260712


def _lhs(count: int, bounds: list[tuple[float, float]], rng: random.Random) -> list[list[float]]:
    columns = []
    for low, high in bounds:
        values = [low + (high - low) * ((index + rng.random()) / count) for index in range(count)]
        rng.shuffle(values)
        columns.append(values)
    return [[column[index] for column in columns] for index in range(count)]


def _point(family: str, split: str, index: int, values: list[float]) -> dict[str, object]:
    return {
        "id": f"{family}-{split}-{index:04d}",
        "family": family,
        "split": split,
        "parameters": [round(value, 12) for value in values],
    }


def _family_points(family: str, rng: random.Random, *, validation: bool) -> list[dict[str, object]]:
    if family == "harmonic_honeycomb":
        physical = [(0.20, 0.80), (-0.08, 0.08)]
        ood_physical = [(0.08, 0.96), (-0.112, 0.112)]
    else:
        physical = [(1.0, 4.0), (0.18, 0.35), (-0.08, 0.08)]
        ood_physical = [(0.4, 4.6), (0.146, 0.384), (-0.112, 0.112)]
    if validation:
        values = _lhs(32, [(0.28, 0.38), (0.28, 0.38), *physical], rng)
        return [_point(family, "validation", i, value) for i, value in enumerate(values)]

    points: list[dict[str, object]] = []
    iid = _lhs(96, [(0.28, 0.38), (0.28, 0.38), *physical], rng)
    points.extend(_point(family, "iid", i, value) for i, value in enumerate(iid))

    exact_physical = _lhs(32, physical[:-1] + [(0.0, 0.0)], rng)
    for i, values in enumerate(exact_physical):
        points.append(_point(family, "exact_dirac", i, [1.0 / 3.0, 1.0 / 3.0, *values]))

    near_physical = _lhs(64, physical, rng)
    for i, values in enumerate(near_physical):
        radius = (0.002, 0.006, 0.015, 0.035)[i % 4]
        angle = 2.0 * math.pi * (i + 0.5) / len(near_physical)
        kx = 1.0 / 3.0 + radius * math.cos(angle)
        ky = 1.0 / 3.0 + radius * math.sin(angle)
        points.append(_point(family, "near_crossing", i, [kx, ky, *values]))

    ood = _lhs(64, [(0.24, 0.42), (0.24, 0.42), *ood_physical], rng)
    points.extend(_point(family, "ood_20pct", i, value) for i, value in enumerate(ood))

    gap = _lhs(64, [(0.27, 0.40), (0.27, 0.40), *physical], rng)
    points.extend(_point(family, "gap_scan", i, value) for i, value in enumerate(gap))
    return points


def _write(name: str, points: list[dict[str, object]], purpose: str) -> None:
    payload = {
        "suite_id": name,
        "seed": SEED,
        "purpose": purpose,
        "frozen_before_formal_training": True,
        "point_count": len(points),
        "points": points,
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path = OUT / f"{name}.json"
    path.write_text(body, encoding="utf-8")
    (OUT / f"{name}.sha256").write_text(f"{hashlib.sha256(body.encode()).hexdigest()}  {path.name}\n")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    validation_rng = random.Random(SEED)
    test_rng = random.Random(SEED + 1)
    families = ("harmonic_honeycomb", "gaussian_honeycomb")
    validation = [point for family in families for point in _family_points(family, validation_rng, validation=True)]
    test = [point for family in families for point in _family_points(family, test_rng, validation=False)]
    _write("sci3_validation_v1", validation, "hyperparameter selection only; never report as final test")
    _write("sci3_frozen_test_v1", test, "single-use final test; do not tune on these points")
    print(f"validation={len(validation)} test={len(test)} output={OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

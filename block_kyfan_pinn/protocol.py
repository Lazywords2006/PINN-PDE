"""Immutable parameter protocols for falsifying spectral-cluster claims.

The V1 benchmark used broad boxes whose nominal OOD subset overlapped the
training box, and it labelled points near K geometrically without checking the
actual spectrum.  This module keeps the replacement protocol small and pure so
that its invariants can be tested before any expensive reference solve.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence

import torch

from .reference import solve_reference


TRAINING_BOUNDS: dict[str, tuple[tuple[float, float], ...]] = {
    "harmonic_honeycomb": (
        (0.28, 0.38),
        (0.28, 0.38),
        (0.20, 0.80),
        (-0.08, 0.08),
    ),
    "gaussian_honeycomb": (
        (0.28, 0.38),
        (0.28, 0.38),
        (1.00, 4.00),
        (0.18, 0.35),
        (-0.08, 0.08),
    ),
}


def is_inside_training_box(parameters: Sequence[float], family: str) -> bool:
    """Return true only when every parameter lies in the declared train box."""

    try:
        bounds = TRAINING_BOUNDS[family]
    except KeyError as error:
        raise ValueError(f"unknown potential family: {family}") from error
    if len(parameters) != len(bounds):
        raise ValueError(f"{family} requires {len(bounds)} parameters")
    return all(low <= float(value) <= high for value, (low, high) in zip(parameters, bounds))


def _lhs(count: int, bounds: Sequence[tuple[float, float]], rng: random.Random) -> list[list[float]]:
    columns: list[list[float]] = []
    for low, high in bounds:
        values = [low + (high - low) * ((index + rng.random()) / count) for index in range(count)]
        rng.shuffle(values)
        columns.append(values)
    return [[float(column[index]) for column in columns] for index in range(count)]


def _row(family: str, split: str, index: int, parameters: Sequence[float]) -> dict[str, object]:
    return {
        "id": f"{family}-{split}-{index:03d}",
        "family": family,
        "split": split,
        "parameters": [float(value) for value in parameters],
    }


def _family_smoke_points(family: str, rng: random.Random) -> list[dict[str, object]]:
    bounds = TRAINING_BOUNDS[family]
    points = [_row(family, "iid_hidden", index, values) for index, values in enumerate(_lhs(3, bounds, rng))]

    if family == "harmonic_honeycomb":
        exact_physical = ((0.30, 0.0), (0.50, 0.0), (0.70, 0.0))
        near_physical = ((0.35, 0.0), (0.50, 0.0), (0.70, 0.0))
        strict_ood = (
            (0.25, 0.33, 0.50, 0.0),
            (0.33, 0.41, 0.50, 0.0),
            (0.33, 0.33, 0.90, 0.10),
        )
    else:
        exact_physical = ((2.0, 0.26, 0.0), (2.5, 0.30, 0.0), (3.0, 0.26, 0.0))
        near_physical = ((2.0, 0.26, 0.0), (2.5, 0.30, 0.0), (3.0, 0.26, 0.0))
        strict_ood = (
            (0.25, 0.33, 2.50, 0.26, 0.0),
            (0.33, 0.41, 2.50, 0.26, 0.0),
            (0.33, 0.33, 4.30, 0.38, 0.10),
        )

    k_point = (1.0 / 3.0, 1.0 / 3.0)
    points.extend(
        _row(family, "exact_cluster", index, (*k_point, *physical))
        for index, physical in enumerate(exact_physical)
    )
    radii = (0.002, 0.006, 0.012)
    angles = (0.0, 2.0 * math.pi / 3.0, 4.0 * math.pi / 3.0)
    for index, (physical, radius, angle) in enumerate(zip(near_physical, radii, angles)):
        kx = k_point[0] + radius * math.cos(angle)
        ky = k_point[1] + radius * math.sin(angle)
        points.append(_row(family, "near_cluster", index, (kx, ky, *physical)))
    points.extend(_row(family, "strict_ood", index, values) for index, values in enumerate(strict_ood))
    return points


def build_falsification_smoke_points(seed: int = 20260729) -> list[dict[str, object]]:
    """Build 24 deterministic points without looking at a trained model."""

    rng = random.Random(seed)
    return [
        point
        for family in ("harmonic_honeycomb", "gaussian_honeycomb")
        for point in _family_smoke_points(family, rng)
    ]


def annotate_spectral_gaps(
    points: Sequence[dict[str, object]], *, cutoff: int = 6
) -> list[dict[str, object]]:
    """Attach the two gaps from an independent plane-wave reference solve."""

    annotated: list[dict[str, object]] = []
    for point in points:
        family = str(point["family"])
        parameters = torch.tensor(point["parameters"], dtype=torch.float64)
        solution = solve_reference(parameters, cutoff=cutoff, rank=3, potential_family=family)
        row = dict(point)
        row["reference_cutoff"] = cutoff
        row["internal_gap"] = float(solution.eigenvalues[1] - solution.eigenvalues[0])
        row["external_gap"] = float(solution.eigenvalues[2] - solution.eigenvalues[1])
        annotated.append(row)
    return annotated


def validate_falsification_points(points: Sequence[dict[str, object]]) -> list[str]:
    """Return protocol violations instead of silently accepting bad labels."""

    errors: list[str] = []
    ids = [str(point.get("id")) for point in points]
    if len(ids) != len(set(ids)):
        errors.append("duplicate point id")
    for point in points:
        identity = str(point.get("id"))
        family = str(point.get("family"))
        split = str(point.get("split"))
        parameters = point.get("parameters")
        if not isinstance(parameters, list):
            errors.append(f"{identity}: parameters must be a list")
            continue
        try:
            inside = is_inside_training_box(parameters, family)
        except ValueError as error:
            errors.append(f"{identity}: {error}")
            continue
        if split == "iid_hidden" and not inside:
            errors.append(f"{identity}: iid_hidden lies outside training box")
        if split == "strict_ood" and inside:
            errors.append(f"{identity}: strict_ood overlaps training box")
        if split in {"exact_cluster", "near_cluster"} and float(parameters[-1]) != 0.0:
            errors.append(f"{identity}: cluster case breaks honeycomb symmetry")
        if split == "exact_cluster" and any(
            abs(float(value) - 1.0 / 3.0) > 1e-14 for value in parameters[:2]
        ):
            errors.append(f"{identity}: exact_cluster is not at K")
        if "internal_gap" not in point or "external_gap" not in point:
            errors.append(f"{identity}: missing spectral gap evidence")
            continue
        internal_gap = float(point["internal_gap"])
        external_gap = float(point["external_gap"])
        if external_gap <= 0.01:
            errors.append(f"{identity}: target rank-two cluster is not externally isolated")
        if split == "exact_cluster":
            tolerance = 1e-8 if family == "harmonic_honeycomb" else 5e-4
            if internal_gap > tolerance:
                errors.append(f"{identity}: exact_cluster internal_gap exceeds {tolerance:g}")
        if split == "near_cluster" and not (0.0 < internal_gap <= 0.02):
            errors.append(f"{identity}: near_cluster internal_gap must be in (0, 0.02]")
    return errors

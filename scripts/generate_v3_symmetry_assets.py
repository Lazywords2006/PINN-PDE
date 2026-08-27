#!/usr/bin/env python3
"""Generate disjoint suites and references for the symmetry-corrected solver."""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections.abc import Mapping
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.physics import periodic_mgs
from block_kyfan_pinn.reference import (
    evaluate_reference_basis,
    solve_reference,
    uniform_grid,
)
from block_kyfan_pinn.suites import file_sha256, write_frozen_suite
from block_kyfan_pinn.v3_protocol import (
    V3_FORMAL_POINT_DIGEST,
    V3_FORMAL_PURPOSE,
    V3_FORMAL_SEED,
    V3_FORMAL_SUITE_ID,
    V3_MODE_POLICY,
    physical_point_digest,
)
from scripts.generate_v2_assets import OOD_BOUNDS, TRAINING_BOUNDS, _lhs_sample

PILOT_COUNTS = {
    "iid_hidden": 2,
    "exact_cluster": 2,
    "near_cluster": 3,
    "strict_ood": 3,
    "gap_scan": 2,
}
TEST_COUNTS = {
    "iid_hidden": 16,
    "exact_cluster": 16,
    "near_cluster": 24,
    "strict_ood": 16,
    "gap_scan": 8,
}
FAMILIES = ("harmonic_honeycomb", "gaussian_honeycomb")


def validate_spectral_point(
    split: str, *, internal_gap: float, external_gap: float
) -> None:
    """Enforce the spectral meaning of every declared benchmark split."""

    if external_gap <= 1e-2:
        raise ValueError(f"external gap is not isolated: {external_gap:.3e}")
    if split == "exact_cluster" and internal_gap >= 1e-3:
        raise ValueError(f"exact-cluster internal gap is too large: {internal_gap:.3e}")
    if split == "near_cluster" and internal_gap >= 2e-2:
        raise ValueError(f"near-cluster internal gap is too large: {internal_gap:.3e}")


def _potential_parameters(
    family: str, *, index: int, count: int, offset: float
) -> list[float]:
    bounds = TRAINING_BOUNDS[family][2:]
    values = []
    for dimension, (lower, upper) in enumerate(bounds):
        fraction = (
            (index + offset + 0.193 * dimension + 0.5) % count
        ) / count
        values.append(lower + fraction * (upper - lower))
    values[-1] = 0.0
    return values


def _family_points(
    family: str,
    *,
    rng: random.Random,
    prefix: str,
    counts: Mapping[str, int],
) -> list[dict[str, object]]:
    bounds = TRAINING_BOUNDS[family]
    points: list[dict[str, object]] = []
    k_point = 1.0 / 3.0

    for index, parameters in enumerate(
        _lhs_sample(counts["iid_hidden"], bounds, rng)
    ):
        points.append(
            {
                "id": f"{prefix}-{family}-iid-{index:03d}",
                "family": family,
                "split": "iid_hidden",
                "parameters": parameters,
            }
        )

    for index in range(counts["exact_cluster"]):
        potential = _potential_parameters(
            family,
            index=index,
            count=counts["exact_cluster"],
            offset=0.371,
        )
        points.append(
            {
                "id": f"{prefix}-{family}-exact-{index:03d}",
                "family": family,
                "split": "exact_cluster",
                "parameters": [k_point, k_point, *potential],
            }
        )

    for index in range(counts["near_cluster"]):
        angle = 2.0 * math.pi * (index + 0.347) / counts["near_cluster"]
        radius = 0.0015 + 0.011 * rng.random()
        potential = [
            lower + rng.random() * (upper - lower)
            for lower, upper in bounds[2:]
        ]
        potential[-1] = 0.0
        points.append(
            {
                "id": f"{prefix}-{family}-near-{index:03d}",
                "family": family,
                "split": "near_cluster",
                "parameters": [
                    k_point + radius * math.cos(angle),
                    k_point + radius * math.sin(angle),
                    *potential,
                ],
            }
        )

    for index, parameters in enumerate(
        _lhs_sample(counts["strict_ood"], OOD_BOUNDS[family], rng)
    ):
        points.append(
            {
                "id": f"{prefix}-{family}-ood-{index:03d}",
                "family": family,
                "split": "strict_ood",
                "parameters": parameters,
            }
        )

    for index in range(counts["gap_scan"]):
        fraction = (index + 0.413) / (counts["gap_scan"] + 0.827)
        potential = _potential_parameters(
            family,
            index=index,
            count=counts["gap_scan"],
            offset=0.619,
        )
        points.append(
            {
                "id": f"{prefix}-{family}-gap-{index:03d}",
                "family": family,
                "split": "gap_scan",
                "parameters": [
                    k_point + fraction * (0.5 - k_point),
                    k_point,
                    *potential,
                ],
            }
        )
    return points


def generate_suite_points(
    *, seed: int, prefix: str, counts: Mapping[str, int]
) -> list[dict[str, object]]:
    """Return one deterministic two-family suite."""

    required = set(PILOT_COUNTS)
    if set(counts) != required or any(int(counts[key]) < 1 for key in required):
        raise ValueError("counts must define five positive split sizes")
    rng = random.Random(seed)
    points = [
        point
        for family in FAMILIES
        for point in _family_points(
            family, rng=rng, prefix=prefix, counts=counts
        )
    ]
    identities = {
        (
            str(point["family"]),
            tuple(round(float(value), 14) for value in point["parameters"]),
        )
        for point in points
    }
    if len(identities) != len(points):
        raise ValueError("generated suite contains duplicate parameter points")
    return points


def _existing_identities(root: Path, excluded: set[Path]) -> set[tuple[object, ...]]:
    identities: set[tuple[object, ...]] = set()
    for path in (root / "benchmarks").glob("*.json"):
        if path.resolve() in excluded:
            continue
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for point in payload.get("points", []):
            if not isinstance(point, dict) or "parameters" not in point:
                continue
            identities.add(
                (
                    str(point.get("family")),
                    tuple(round(float(value), 14) for value in point["parameters"]),
                )
            )
    return identities


def _suite_payload(
    points: list[dict[str, object]], *, suite_id: str, seed: int, purpose: str
) -> dict[str, object]:
    return {
        "suite_id": suite_id,
        "protocol_version": 2,
        "purpose": purpose,
        "generation_seed": seed,
        "point_count": len(points),
        "grid_side": 65,
        "reference_cutoff": 24,
        "mode_policy": V3_MODE_POLICY,
        "training_bounds": TRAINING_BOUNDS,
        "points": points,
    }


def build_reference_cache(suite_path: Path, output: Path) -> str:
    """Build a float64, cutoff-24, grid-65 reference cache."""

    if output.exists() or output.with_suffix(".sha256").exists():
        raise FileExistsError(f"reference target already exists: {output}")
    suite = json.loads(suite_path.read_text())
    suite_hash = file_sha256(suite_path)
    grid = uniform_grid(65, dtype=torch.float64).unsqueeze(0)
    references: dict[str, dict[str, object]] = {}
    for index, point in enumerate(suite["points"], start=1):
        family = str(point["family"])
        parameters = torch.tensor(point["parameters"], dtype=torch.float64)
        solution = solve_reference(
            parameters,
            cutoff=24,
            rank=3,
            potential_family=family,
            mode_shape="hexagonal_d6",
        )
        basis = periodic_mgs(evaluate_reference_basis(solution, grid))[0]
        internal_gap = float(abs(solution.eigenvalues[1] - solution.eigenvalues[0]))
        external_gap = float(abs(solution.eigenvalues[2] - solution.eigenvalues[1]))
        validate_spectral_point(
            str(point["split"]),
            internal_gap=internal_gap,
            external_gap=external_gap,
        )
        references[str(point["id"])] = {
            "basis": basis,
            "eigenvalues": solution.eigenvalues,
            "parameters": [float(value) for value in point["parameters"]],
            "family": family,
            "internal_gap": internal_gap,
            "external_gap": external_gap,
        }
        print(f"REFERENCE={index}/{len(suite['points'])}", flush=True)
    payload = {
        "metadata": {
            "suite_id": suite["suite_id"],
            "suite_sha256": suite_hash,
            "grid_side": 65,
            "cutoff": 24,
            "rank": 3,
            "mode_shape": "hexagonal_d6",
            "point_count": len(references),
        },
        "references": references,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, output)
    digest = file_sha256(output)
    output.with_suffix(".sha256").write_text(f"{digest}  {output.name}\n")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--build-cache", choices=("none", "pilot", "test", "both"), default="none"
    )
    parser.add_argument("--emit-test", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    pilot_path = root / "benchmarks/v3_symmetry_pilot.json"
    test_path = root / "benchmarks/v3_symmetry_test.json"
    excluded = {pilot_path.resolve(), test_path.resolve()}
    existing = _existing_identities(root, excluded)
    configurations = [
        (
            pilot_path,
            generate_suite_points(
                seed=20260827, prefix="v3-pilot", counts=PILOT_COUNTS
            ),
            "block-kyfan-v3-symmetry-pilot-20260827",
            20260827,
            "symmetry_correction_engineering_only",
        )
    ]
    if args.emit_test:
        configurations.append(
            (
                test_path,
                generate_suite_points(
                    seed=V3_FORMAL_SEED,
                    prefix="v3-confirm",
                    counts=TEST_COUNTS,
                ),
                V3_FORMAL_SUITE_ID,
                V3_FORMAL_SEED,
                V3_FORMAL_PURPOSE,
            )
        )
    for path, points, suite_id, seed, purpose in configurations:
        if path.is_file():
            existing_payload = json.loads(path.read_text())
            if path == test_path and args.emit_test:
                raise FileExistsError("frozen confirmation suite already exists")
            if (
                existing_payload.get("suite_id") != suite_id
                or existing_payload.get("generation_seed") != seed
            ):
                raise ValueError(f"existing suite metadata mismatch: {path}")
            existing |= {
                (
                    str(point["family"]),
                    tuple(
                        round(float(value), 14)
                        for value in point["parameters"]
                    ),
                )
                for point in existing_payload["points"]
            }
            print(f"SUITE_REUSED={path}")
            continue
        identities = {
            (
                str(point["family"]),
                tuple(round(float(value), 14) for value in point["parameters"]),
            )
            for point in points
        }
        overlap = identities & existing
        if overlap:
            raise ValueError(f"{path.name} overlaps earlier suites")
        write_frozen_suite(
            _suite_payload(
                points, suite_id=suite_id, seed=seed, purpose=purpose
            ),
            path,
        )
        existing |= identities
        print(f"SUITE={path}")
    if args.build_cache in {"pilot", "both"}:
        digest = build_reference_cache(
            pilot_path, root / "data/v3_symmetry_pilot_references.pt"
        )
        print(f"PILOT_REFERENCE_SHA256={digest}")
    if args.build_cache in {"test", "both"}:
        if not test_path.is_file():
            raise FileNotFoundError("test suite is absent; use --emit-test first")
        reference_path = root / "data/v3_symmetry_test_references.pt"
        digest = build_reference_cache(
            test_path, reference_path
        )
        print(f"TEST_REFERENCE_SHA256={digest}")
        from scripts.run_v3_symmetry_evaluation import _source_fingerprint

        formal_manifest = {
            "suite_sha256": file_sha256(test_path),
            "reference_sha256": digest,
            "source_fingerprint": _source_fingerprint(root),
            "point_count": 160,
            "suite_id": V3_FORMAL_SUITE_ID,
            "generation_seed": V3_FORMAL_SEED,
            "purpose": V3_FORMAL_PURPOSE,
            "mode_policy": V3_MODE_POLICY,
            "physical_point_digest": physical_point_digest(
                json.loads(test_path.read_text())["points"]
            ),
        }
        if formal_manifest["physical_point_digest"] != V3_FORMAL_POINT_DIGEST:
            raise ValueError("generated confirmation point digest is not frozen")
        convergence_path = root / "benchmarks/v3_symmetry_convergence_audit.json"
        if not convergence_path.is_file():
            raise FileNotFoundError("committed convergence evidence is required")
        convergence_sidecar = convergence_path.with_suffix(".sha256")
        declared_convergence = convergence_sidecar.read_text().split()[0]
        actual_convergence = file_sha256(convergence_path)
        if declared_convergence != actual_convergence:
            raise ValueError("convergence evidence sidecar mismatch")
        convergence_payload = json.loads(convergence_path.read_text())
        if not bool(convergence_payload.get("gate", {}).get("convergence_go")):
            raise ValueError("convergence evidence did not pass")
        formal_manifest["convergence_audit_sha256"] = actual_convergence
        manifest_path = test_path.with_suffix(".manifest.json")
        if manifest_path.exists():
            raise FileExistsError("formal manifest already exists")
        manifest_path.write_text(
            json.dumps(formal_manifest, ensure_ascii=False, indent=2) + "\n"
        )
        print(f"FORMAL_MANIFEST={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

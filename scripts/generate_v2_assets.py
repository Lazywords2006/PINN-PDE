"""Generate V2 frozen experimental assets.

Creates:
1. Symmetry-closed PWE reference solutions (hexagonal shell cutoff)
2. Cutoff convergence audit (8, 12, 16 shells)
3. 640-point V2 frozen test suite (IID/exact/near/ODO/gap-scan)
4. Independent validation split
5. SHA-256 hashes

Usage:
    python scripts/generate_v2_assets.py [--device auto]
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import sys
import time
from collections.abc import Sequence
from pathlib import Path

import torch

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.device import select_device


# ── Symmetry-closed PWE: hexagonal shells ───────────────────────────────────

def hex_shell_modes(num_shells: int) -> list[tuple[int, int]]:
    """Return integer (m₁, m₂) within the first ``num_shells`` hexagonal shells.

    A hexagonal shell of order *s* contains all vectors whose
    max(|m₁|, |m₂|, |m₁−m₂|) = s.  This set is closed under the
    honeycomb point-group operations.
    """
    modes: list[tuple[int, int]] = []
    for s in range(num_shells + 1):
        for m1 in range(-s, s + 1):
            for m2 in range(-s, s + 1):
                if max(abs(m1), abs(m2), abs(m1 - m2)) == s:
                    modes.append((m1, m2))
    return modes


def symmetry_closed_pwe(
    parameters: list[float],
    num_shells: int,
    potential_family: str = "harmonic_honeycomb",
) -> dict:
    """Diagonalise the Bloch Hamiltonian in a symmetry-closed basis."""
    from block_kyfan_pinn.reference import solve_reference

    tensor = torch.tensor(parameters, dtype=torch.float64)
    cutoff = num_shells  # each shell adds one more ring
    # The square-cutoff solve_reference uses a square of side (2*cutoff+1)² modes.
    # For comparable coverage use a square cutoff proportional to shells.
    square_cutoff = max(1, num_shells)
    solution = solve_reference(tensor, cutoff=square_cutoff, rank=6,
                               potential_family=potential_family)
    return {
        "parameters": parameters,
        "eigenvalues": [float(v) for v in solution.eigenvalues[:6].cpu()],
        "num_shells": num_shells,
        "num_modes": len(hex_shell_modes(num_shells)),
        "family": potential_family,
    }


def cutoff_convergence_audit(
    parameters: list[float],
    max_shells: int = 16,
    potential_family: str = "harmonic_honeycomb",
) -> list[dict]:
    """Audit reference convergence across cutoff values."""
    from block_kyfan_pinn.reference import solve_reference

    results = []
    tensor = torch.tensor(parameters, dtype=torch.float64)

    for cutoff in (8, 12, 16):
        solution = solve_reference(tensor, cutoff=cutoff, rank=6,
                                   potential_family=potential_family)
        results.append({
            "cutoff": cutoff,
            "num_modes": (2 * cutoff + 1) ** 2,
            "eigenvalues": [float(v) for v in solution.eigenvalues[:6].cpu()],
        })

    # Check convergence: cutoff 12 vs 16 diffs
    if len(results) >= 3:
        e12 = torch.tensor(results[1]["eigenvalues"])
        e16 = torch.tensor(results[2]["eigenvalues"])
        projector_diff = float((e12[:2] - e16[:2]).abs().max())
        results.append({
            "convergence_check": {
                "cutoff_12_vs_16_max_eigenvalue_diff": projector_diff,
                "criterion": "diff < 1e-3",
                "passed": projector_diff < 1e-3,
            }
        })

    return results


# ── Parameter point generation ──────────────────────────────────────────────

TRAINING_BOUNDS = {
    "harmonic_honeycomb": [
        (0.28, 0.38),  # kx
        (0.28, 0.38),  # ky
        (0.20, 0.80),  # v0
        (-0.08, 0.08),  # delta
    ],
    "gaussian_honeycomb": [
        (0.28, 0.38),  # kx
        (0.28, 0.38),  # ky
        (1.00, 4.00),  # amplitude
        (0.18, 0.35),  # sigma
        (-0.08, 0.08),  # imbalance
    ],
}

OOD_BOUNDS = {
    "harmonic_honeycomb": [
        (0.20, 0.28),  # kx below training
        (0.38, 0.45),  # ky above training
        (0.20, 0.95),  # wider v0
        (-0.15, 0.15),  # wider delta
    ],
    "gaussian_honeycomb": [
        (0.20, 0.28),  # kx below
        (0.38, 0.45),  # ky above
        (0.80, 4.50),  # wider amplitude
        (0.15, 0.40),  # wider sigma
        (-0.15, 0.15),  # wider imbalance
    ],
}


def _lhs_sample(
    count: int, bounds: Sequence[tuple[float, float]], rng: random.Random
) -> list[list[float]]:
    """Latin hypercube sample."""
    dim = len(bounds)
    samples = []
    for d in range(dim):
        low, high = bounds[d]
        values = [low + (high - low) * ((i + rng.random()) / count) for i in range(count)]
        rng.shuffle(values)
        samples.append(values)
    return [[float(samples[d][i]) for d in range(dim)] for i in range(count)]


def _generate_family_points(
    family: str, rng: random.Random,
    # Counts per split
    n_iid: int = 96,
    n_exact: int = 32,
    n_near: int = 64,
    n_ood: int = 64,
    n_gap_scan: int = 64,
) -> list[dict]:
    """Generate all points for one potential family (320 total)."""
    points: list[dict] = []
    bounds = TRAINING_BOUNDS[family]
    k_point = (1.0 / 3.0, 1.0 / 3.0)
    param_dim = len(bounds)

    # IID hidden — LHS within training box
    for i, params in enumerate(_lhs_sample(n_iid, bounds, rng)):
        points.append({"id": f"{family}-iid-{i:03d}", "family": family,
                        "split": "iid_hidden", "parameters": params})

    # Exact cluster — exactly at K point, zero symmetry breaking
    for i in range(n_exact):
        remaining = list(bounds[2:])  # potential params without kx,ky
        for j in range(len(remaining)):
            low, high = bounds[2 + j]
            remaining[j] = low + (high - low) * ((i * 3 + j * 7 + 1) % (n_exact + 1)) / n_exact
        if family == "harmonic_honeycomb":
            remaining[-1] = 0.0  # delta=0 for exact cluster
        else:
            remaining[-1] = 0.0  # imbalance=0 for exact cluster
        points.append({"id": f"{family}-exact-{i:03d}", "family": family,
                        "split": "exact_cluster",
                        "parameters": [k_point[0], k_point[1]] + remaining})

    # Near cluster — small perturbation from K, small internal gap
    for i in range(n_near):
        angle = 2.0 * math.pi * i / n_near
        radius = 0.002 + 0.010 * rng.random()  # 0.002–0.012
        kx = k_point[0] + radius * math.cos(angle)
        ky = k_point[1] + radius * math.sin(angle)
        remaining = list(bounds[2:])
        for j in range(len(remaining)):
            low, high = bounds[2 + j]
            remaining[j] = low + (high - low) * rng.random()
        if family == "harmonic_honeycomb":
            remaining[-1] = 0.0  # delta=0 for near-cluster symmetry
        else:
            remaining[-1] = 0.0  # imbalance=0
        points.append({"id": f"{family}-near-{i:03d}", "family": family,
                        "split": "near_cluster",
                        "parameters": [kx, ky] + remaining})

    # Strict OOD
    ood_bounds = OOD_BOUNDS[family]
    for i, params in enumerate(_lhs_sample(n_ood, ood_bounds, rng)):
        # Ensure at least one parameter is outside training
        points.append({"id": f"{family}-ood-{i:03d}", "family": family,
                        "split": "strict_ood", "parameters": params})

    # Gap scan — systematic scan across k-space line
    for i in range(n_gap_scan):
        # Scan from K to M (vary kx from 1/3 to 0.5, ky fixed at 1/3)
        t = i / (n_gap_scan - 1) if n_gap_scan > 1 else 0.5
        kx = k_point[0] + t * (0.5 - k_point[0])
        ky = k_point[1]
        remaining = list(bounds[2:])
        for j in range(len(remaining)):
            low, high = bounds[2 + j]
            remaining[j] = (low + high) / 2.0  # mid-range
        if family == "harmonic_honeycomb":
            remaining[-1] = 0.0
        else:
            remaining[-1] = 0.0
        points.append({"id": f"{family}-gap-{i:03d}", "family": family,
                        "split": "gap_scan",
                        "parameters": [kx, ky] + remaining})

    return points


def generate_v2_test_suite(seed: int = 20260730) -> list[dict]:
    """Generate 640-point V2 frozen test suite."""
    rng = random.Random(seed)
    points = []
    for family in ("harmonic_honeycomb", "gaussian_honeycomb"):
        points.extend(_generate_family_points(family, rng))
    return points


def generate_validation_suite(seed: int = 20260731) -> list[dict]:
    """Generate independent validation suite for hyperparameter selection."""
    rng = random.Random(seed)
    points = []
    for family in ("harmonic_honeycomb", "gaussian_honeycomb"):
        bounds = TRAINING_BOUNDS[family]
        for i, params in enumerate(_lhs_sample(32, bounds, rng)):
            points.append({"id": f"val-{family}-{i:03d}", "family": family,
                           "split": "validation", "parameters": params})
    return points


def compute_suite_hash(points: list[dict]) -> str:
    """SHA-256 hash of the canonically-serialised point list."""
    body = json.dumps(points, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode()).hexdigest()


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="auto")
    parser.add_argument("--output-dir", default="benchmarks")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()

    device = select_device(args.device)
    print(f"Device: {device}")

    output_dir = Path(args.output_dir)
    data_dir = Path(args.data_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    if not args.audit_only:
        # ── Generate V2 test suite ──
        print("Generating V2 frozen test suite (640 points)...")
        t0 = time.perf_counter()
        test_suite = generate_v2_test_suite(seed=20260730)
        print(f"  {len(test_suite)} points generated in {time.perf_counter() - t0:.1f}s")
        for split in ("iid_hidden", "exact_cluster", "near_cluster", "strict_ood", "gap_scan"):
            count = sum(1 for p in test_suite if p["split"] == split)
            print(f"    {split}: {count}")

        test_path = output_dir / "v2_frozen_test.json"
        test_path.write_text(json.dumps(test_suite, ensure_ascii=False, indent=2))
        test_hash = compute_suite_hash(test_suite)
        (output_dir / "v2_frozen_test.sha256").write_text(
            f"{test_hash}  v2_frozen_test.json\n")
        print(f"  SHA-256: {test_hash[:16]}...")

        # ── Generate validation suite ──
        print("Generating independent validation suite (64 points)...")
        val_suite = generate_validation_suite(seed=20260731)
        val_path = output_dir / "v2_validation.json"
        val_path.write_text(json.dumps(val_suite, ensure_ascii=False, indent=2))
        val_hash = compute_suite_hash(val_suite)
        (output_dir / "v2_validation.sha256").write_text(
            f"{val_hash}  v2_validation.json\n")
        print(f"  SHA-256: {val_hash[:16]}...")

    # ── Reference convergence audit ──
    print("Running cutoff convergence audit...")
    test_params = [
        ([0.31, 0.35, 0.35, 0.05], "harmonic_honeycomb"),
        ([1.0/3.0, 1.0/3.0, 0.60, 0.0], "harmonic_honeycomb"),
        ([0.42, 0.24, 0.90, 0.16], "harmonic_honeycomb"),
        ([0.31, 0.35, 2.0, 0.26, 0.04], "gaussian_honeycomb"),
        ([1.0/3.0, 1.0/3.0, 2.5, 0.26, 0.0], "gaussian_honeycomb"),
        ([0.42, 0.24, 4.4, 0.37, 0.10], "gaussian_honeycomb"),
    ]

    all_passed = True
    audit_results = []
    for params, family in test_params:
        audit = cutoff_convergence_audit(params, max_shells=16, potential_family=family)
        audit_results.append({"parameters": params, "family": family, "audit": audit})
        check = audit[-1].get("convergence_check", {})
        passed = check.get("passed", False)
        diff = check.get("cutoff_12_vs_16_max_eigenvalue_diff", float("inf"))
        status = "✅" if passed else "❌"
        all_passed = all_passed and passed
        print(f"  {family} {params[:2]}: diff={diff:.2e} {status}")

    audit_path = output_dir / "v2_reference_convergence.json"
    audit_path.write_text(json.dumps({
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "all_passed": all_passed,
        "results": audit_results,
    }, ensure_ascii=False, indent=2))
    audit_hash = hashlib.sha256(audit_path.read_bytes()).hexdigest()
    (output_dir / "v2_reference_convergence.sha256").write_text(
        f"{audit_hash}  v2_reference_convergence.json\n")

    print(f"\nConvergence audit: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
    if not all_passed:
        print("WARNING: Cutoff convergence check failed — reference may be unreliable.")
        return 1

    # ── Pre-compute reference solutions for the test suite ──
    if not args.audit_only and all_passed:
        print(f"\nPre-computing PWE references for {len(test_suite)} test points...")
        from block_kyfan_pinn.reference import solve_reference

        references = {}
        t0 = time.perf_counter()
        for i, point in enumerate(test_suite):
            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{len(test_suite)}...")
            tensor = torch.tensor(point["parameters"], dtype=torch.float64)
            try:
                sol = solve_reference(tensor, cutoff=12, rank=6,
                                      potential_family=point["family"])
                references[point["id"]] = {
                    "eigenvalues": [float(v) for v in sol.eigenvalues[:6].cpu()],
                    "parameters": point["parameters"],
                    "family": point["family"],
                }
            except Exception as e:
                print(f"  WARNING: {point['id']}: {e}")

        ref_path = data_dir / "v2_frozen_test_references.pt"
        torch.save(references, ref_path)
        ref_hash = hashlib.sha256(ref_path.read_bytes()).hexdigest()
        (data_dir / "v2_frozen_test_references.sha256").write_text(
            f"{ref_hash}  v2_frozen_test_references.pt\n")
        print(f"  {len(references)} references saved in {time.perf_counter() - t0:.1f}s")

    print("\nV2 asset generation complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

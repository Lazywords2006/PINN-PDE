"""Generate V2 frozen experimental assets.

Creates:
1. Symmetry-closed PWE reference solutions (hexagonal shell cutoff)
2. Cutoff convergence audit (8, 12, 16 shells)
3. 640-point V2 frozen test suite (IID/exact/near/ODO/gap-scan)
4. Independent validation split
5. SHA-256 hashes

Usage:
    python scripts/generate_v2_assets.py --device auto --reference-scope validation
"""

from __future__ import annotations

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
from block_kyfan_pinn.metrics import projector_sine_error
from block_kyfan_pinn.physics import periodic_mgs
from block_kyfan_pinn.reference import evaluate_reference_basis, solve_reference, uniform_grid
from block_kyfan_pinn.suites import file_sha256, load_frozen_suite, write_frozen_suite


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
    tensor = torch.tensor(parameters, dtype=torch.float64)
    solution = solve_reference(
        tensor,
        cutoff=max(1, num_shells),
        rank=6,
        potential_family=potential_family,
        mode_shape="hexagonal",
    )
    return {
        "parameters": parameters,
        "eigenvalues": [float(v) for v in solution.eigenvalues[:6].cpu()],
        "num_shells": num_shells,
        "num_modes": len(hex_shell_modes(num_shells)),
        "family": potential_family,
    }


def cutoff_convergence_audit(
    parameters: list[float],
    cutoffs: tuple[int, ...] = (16, 20, 24),
    potential_family: str = "harmonic_honeycomb",
) -> list[dict]:
    """Audit rank-two projector and eigenvalue convergence on hexagonal modes."""

    if len(cutoffs) < 2 or tuple(sorted(set(cutoffs))) != cutoffs:
        raise ValueError("cutoffs must contain at least two increasing unique values")
    results: list[dict] = []
    tensor = torch.tensor(parameters, dtype=torch.float64)
    grid = uniform_grid(33, dtype=torch.float64).unsqueeze(0)
    solutions = []

    for cutoff in cutoffs:
        solution = solve_reference(
            tensor,
            cutoff=cutoff,
            rank=6,
            potential_family=potential_family,
            mode_shape="hexagonal",
        )
        solutions.append(solution)
        results.append({
            "cutoff": cutoff,
            "num_modes": len(solution.modes),
            "eigenvalues": [float(v) for v in solution.eigenvalues[:6].cpu()],
        })

    previous, final = solutions[-2:]
    previous_basis = periodic_mgs(evaluate_reference_basis(previous, grid))
    final_basis = periodic_mgs(evaluate_reference_basis(final, grid))
    projector_error = projector_sine_error(previous_basis, final_basis)
    eigenvalue_error = float(
        (previous.eigenvalues[:2] - final.eigenvalues[:2]).abs().max()
    )
    results.append({
        "convergence_check": {
            "lower_cutoff": cutoffs[-2],
            "upper_cutoff": cutoffs[-1],
            "rank2_projector_sine_error": projector_error,
            "max_low_eigenvalue_difference": eigenvalue_error,
            "criteria": {
                "rank2_projector_sine_error": "< 1e-3",
                "max_low_eigenvalue_difference": "< 1e-5",
            },
            "passed": projector_error < 1e-3 and eigenvalue_error < 1e-5,
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
    """Generate an independent 64-point, split-balanced validation suite."""

    rng = random.Random(seed)
    points: list[dict] = []
    for family in ("harmonic_honeycomb", "gaussian_honeycomb"):
        family_points = _generate_family_points(
            family,
            rng,
            n_iid=8,
            n_exact=4,
            n_near=8,
            n_ood=6,
            n_gap_scan=6,
        )
        exact_index = 0
        gap_index = 0
        for point in family_points:
            parameters = point["parameters"]
            if point["split"] == "exact_cluster":
                amplitude_low, amplitude_high = TRAINING_BOUNDS[family][2]
                parameters[2] = amplitude_low + (amplitude_high - amplitude_low) * (
                    (exact_index + 0.23) / 4.91
                )
                if family == "gaussian_honeycomb":
                    sigma_low, sigma_high = TRAINING_BOUNDS[family][3]
                    parameters[3] = sigma_low + (sigma_high - sigma_low) * (
                        (exact_index + 0.41) / 5.37
                    )
                exact_index += 1
            elif point["split"] == "gap_scan":
                fraction = (gap_index + 0.5) / 6.0
                parameters[0] = (1.0 / 3.0) + fraction * (0.5 - 1.0 / 3.0)
                gap_index += 1
            point["id"] = f"val-{point['id']}"
        points.extend(family_points)
    return points


def build_suite_payload(
    points: list[dict], *, suite_id: str, seed: int, purpose: str
) -> dict[str, object]:
    """Wrap deterministic points in the schema consumed by formal evaluators."""

    split_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    for point in points:
        split = str(point["split"])
        family = str(point["family"])
        split_counts[split] = split_counts.get(split, 0) + 1
        family_counts[family] = family_counts.get(family, 0) + 1
    return {
        "suite_id": suite_id,
        "protocol_version": 2,
        "purpose": purpose,
        "generation_seed": seed,
        "point_count": len(points),
        "split_counts": split_counts,
        "family_counts": family_counts,
        "training_bounds": TRAINING_BOUNDS,
        "points": points,
    }


def reference_gap_metadata(
    point: dict[str, object], eigenvalues: torch.Tensor
) -> dict[str, float]:
    """Validate split semantics against the computed low spectrum."""

    if eigenvalues.numel() < 3:
        raise ValueError("at least three reference eigenvalues are required")
    internal_gap = float((eigenvalues[1] - eigenvalues[0]).abs())
    external_gap = float((eigenvalues[2] - eigenvalues[1]).abs())
    split = str(point["split"])
    if split == "exact_cluster" and internal_gap > 1e-3:
        raise ValueError(
            f"{point['id']} is labelled exact_cluster but its internal gap is "
            f"{internal_gap:.3e}"
        )
    if split == "near_cluster" and internal_gap > 2e-2:
        raise ValueError(
            f"{point['id']} is labelled near_cluster but its internal gap is "
            f"{internal_gap:.3e}"
        )
    if split in {"exact_cluster", "near_cluster"} and external_gap <= 1e-2:
        raise ValueError(
            f"{point['id']} does not isolate the rank-two cluster: external gap "
            f"{external_gap:.3e}"
        )
    if split == "strict_ood":
        family = str(point["family"])
        parameters = [float(value) for value in point["parameters"]]
        if all(
            lower <= value <= upper
            for value, (lower, upper) in zip(parameters, TRAINING_BOUNDS[family])
        ):
            raise ValueError(f"{point['id']} is labelled strict_ood but is in-domain")
    return {"internal_gap": internal_gap, "external_gap": external_gap}


def _atomic_torch_save(payload: object, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    temporary.replace(path)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="auto")
    parser.add_argument("--output-dir", default="benchmarks")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--suites-only", action="store_true")
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="use committed suites to build reference caches without rewriting benchmarks",
    )
    parser.add_argument(
        "--reference-scope",
        choices=("none", "validation", "all"),
        default="validation",
        help="precompute no cache, only the pilot cache, or pilot and frozen-final caches",
    )
    args = parser.parse_args()

    modes = (args.audit_only, args.suites_only, args.cache_only)
    if sum(bool(mode) for mode in modes) > 1:
        parser.error("--audit-only, --suites-only, and --cache-only are mutually exclusive")
    if args.cache_only and args.reference_scope == "none":
        parser.error("--cache-only requires --reference-scope validation or all")

    device = select_device(args.device)
    print(f"Device: {device}")

    output_dir = Path(args.output_dir)
    data_dir = Path(args.data_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    if not args.audit_only and not args.cache_only:
        # ── Generate V2 test suite ──
        print("Generating V2 frozen test suite (640 points)...")
        t0 = time.perf_counter()
        test_suite = generate_v2_test_suite(seed=20260730)
        print(f"  {len(test_suite)} points generated in {time.perf_counter() - t0:.1f}s")
        for split in ("iid_hidden", "exact_cluster", "near_cluster", "strict_ood", "gap_scan"):
            count = sum(1 for p in test_suite if p["split"] == split)
            print(f"    {split}: {count}")

        test_path = output_dir / "v2_frozen_test.json"
        test_payload = build_suite_payload(
            test_suite,
            suite_id="block-kyfan-v2-frozen-test-20260730",
            seed=20260730,
            purpose="final_test_do_not_use_for_model_selection",
        )
        test_hash = write_frozen_suite(test_payload, test_path)
        print(f"  SHA-256: {test_hash[:16]}...")

        # ── Generate validation suite ──
        print("Generating independent validation suite (64 points)...")
        val_suite = generate_validation_suite(seed=20260731)
        val_path = output_dir / "v2_validation.json"
        val_payload = build_suite_payload(
            val_suite,
            suite_id="block-kyfan-v2-validation-20260731",
            seed=20260731,
            purpose="pilot_and_hyperparameter_selection",
        )
        val_hash = write_frozen_suite(val_payload, val_path)
        print(f"  SHA-256: {val_hash[:16]}...")

        if args.suites_only:
            print("\nV2 suite generation complete; convergence and caches were skipped.")
            return 0

    # ── Reference convergence audit ──
    if args.cache_only:
        convergence_path = output_dir / "v2_reference_convergence.json"
        convergence_hash_path = output_dir / "v2_reference_convergence.sha256"
        if not convergence_path.is_file() or not convergence_hash_path.is_file():
            raise FileNotFoundError("committed convergence audit or SHA-256 is missing")
        expected_hash = convergence_hash_path.read_text().split()[0]
        if file_sha256(convergence_path) != expected_hash:
            raise ValueError("committed convergence audit SHA-256 is invalid")
        convergence = json.loads(convergence_path.read_text())
        if convergence.get("all_passed") is not True:
            raise ValueError("committed reference convergence audit did not pass")
        all_passed = True
        print("Using committed, SHA-verified cutoff convergence audit.")
    else:
        print("Running cutoff convergence audit...")
    test_params = [
        ([0.31, 0.35, 0.35, 0.05], "harmonic_honeycomb"),
        ([1.0/3.0, 1.0/3.0, 0.60, 0.0], "harmonic_honeycomb"),
        ([0.42, 0.24, 0.90, 0.16], "harmonic_honeycomb"),
        ([0.31, 0.35, 2.0, 0.26, 0.04], "gaussian_honeycomb"),
        ([1.0/3.0, 1.0/3.0, 2.5, 0.26, 0.0], "gaussian_honeycomb"),
        ([0.42, 0.24, 4.4, 0.37, 0.10], "gaussian_honeycomb"),
    ]

    if not args.cache_only:
        all_passed = True
        audit_results = []
        for params, family in test_params:
            audit = cutoff_convergence_audit(params, potential_family=family)
            audit_results.append({"parameters": params, "family": family, "audit": audit})
            check = audit[-1].get("convergence_check", {})
            passed = check.get("passed", False)
            projector_error = check.get("rank2_projector_sine_error", float("inf"))
            eigenvalue_error = check.get("max_low_eigenvalue_difference", float("inf"))
            status = "✅" if passed else "❌"
            all_passed = all_passed and passed
            print(
                f"  {family} {params[:2]}: projector={projector_error:.2e} "
                f"eigenvalue={eigenvalue_error:.2e} {status}"
            )

        audit_path = output_dir / "v2_reference_convergence.json"
        audit_path.write_text(json.dumps({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "all_passed": all_passed,
            "results": audit_results,
        }, ensure_ascii=False, indent=2))
        audit_hash = file_sha256(audit_path)
        (output_dir / "v2_reference_convergence.sha256").write_text(
            f"{audit_hash}  v2_reference_convergence.json\n")

        print(f"\nConvergence audit: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
        if not all_passed:
            print("WARNING: Cutoff convergence check failed — reference may be unreliable.")
            return 1

    # ── Pre-compute reference solutions for the test suite ──
    if not args.audit_only and all_passed and args.reference_scope != "none":
        suite_paths = [output_dir / "v2_validation.json"]
        if args.reference_scope == "all":
            suite_paths.append(output_dir / "v2_frozen_test.json")
        for suite_path in suite_paths:
            payload, suite_hash = load_frozen_suite(suite_path)
            points = payload["points"]
            print(f"\nPre-computing PWE references for {len(points)} points in {suite_path.name}...")
            references = {}
            grid_side = 33
            reference_cutoff = 24
            grid = uniform_grid(grid_side, dtype=torch.float64).unsqueeze(0)
            t0 = time.perf_counter()
            partial_path = data_dir / f"{suite_path.stem}_references.partial.pt"
            if partial_path.is_file():
                partial = torch.load(partial_path, map_location="cpu", weights_only=False)
                metadata = partial.get("metadata", {})
                expected = {
                    "suite_id": payload["suite_id"],
                    "suite_sha256": suite_hash,
                    "grid_side": grid_side,
                    "cutoff": reference_cutoff,
                    "mode_shape": "hexagonal",
                    "point_count": len(points),
                }
                if any(metadata.get(key) != value for key, value in expected.items()):
                    raise ValueError(f"stale partial reference cache: {partial_path}")
                partial_references = partial.get("references")
                if not isinstance(partial_references, dict):
                    raise ValueError(f"invalid partial reference cache: {partial_path}")
                valid_ids = {str(point["id"]) for point in points}
                if not set(partial_references).issubset(valid_ids):
                    raise ValueError(f"partial cache contains unknown point IDs: {partial_path}")
                references.update(partial_references)
                print(f"  resuming from {len(references)} cached points")
            for i, point in enumerate(points):
                if point["id"] in references:
                    continue
                if (i + 1) % 100 == 0:
                    print(f"  {i + 1}/{len(points)}...")
                tensor = torch.tensor(point["parameters"], dtype=torch.float64)
                solution = solve_reference(
                    tensor,
                    cutoff=reference_cutoff,
                    rank=6,
                    potential_family=point["family"],
                    mode_shape="hexagonal",
                )
                gaps = reference_gap_metadata(point, solution.eigenvalues)
                basis = periodic_mgs(evaluate_reference_basis(solution, grid))[0].cpu()
                references[point["id"]] = {
                    "basis": basis,
                    "eigenvalues": solution.eigenvalues.cpu(),
                    "parameters": point["parameters"],
                    "family": point["family"],
                    **gaps,
                }

                if (i + 1) % 25 == 0:
                    _atomic_torch_save(
                        {
                            "metadata": {
                                "suite_id": payload["suite_id"],
                                "suite_sha256": suite_hash,
                                "grid_side": grid_side,
                                "cutoff": reference_cutoff,
                                "mode_shape": "hexagonal",
                                "point_count": len(points),
                                "completed_point_count": len(references),
                            },
                            "references": references,
                        },
                        partial_path,
                    )

            stem = suite_path.stem
            ref_path = data_dir / f"{stem}_references.pt"
            _atomic_torch_save({
                "metadata": {
                    "suite_id": payload["suite_id"],
                    "suite_sha256": suite_hash,
                    "grid_side": grid_side,
                    "cutoff": reference_cutoff,
                    "mode_shape": "hexagonal",
                    "point_count": len(points),
                },
                "references": references,
            }, ref_path)
            partial_path.unlink(missing_ok=True)
            ref_hash = file_sha256(ref_path)
            ref_path.with_suffix(".sha256").write_text(f"{ref_hash}  {ref_path.name}\n")
            print(f"  {len(references)} references saved in {time.perf_counter() - t0:.1f}s")

        if args.reference_scope == "validation" and not args.cache_only:
            print(
                "NOTE: the frozen-final spectral labels have not yet been reference-validated; "
                "use --reference-scope all before a formal promotion run."
            )

    print("\nV2 asset generation complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

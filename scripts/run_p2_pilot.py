#!/usr/bin/env python3
"""Run the independent P2 full-shell neural-Galerkin pilot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
import tarfile
import time
from pathlib import Path, PurePosixPath

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.device import select_device
from block_kyfan_pinn.metrics import orthogonality_error, projector_sine_error
from block_kyfan_pinn.p2_refinement import (
    fourier_only_ritz_fast,
    hex_shell_modes,
    neural_augmented_ritz_fast,
)
from block_kyfan_pinn.physics import periodic_mgs
from block_kyfan_pinn.reference import solve_reference, uniform_grid
from block_kyfan_pinn.suites import file_sha256, load_frozen_suite
from scripts.evaluate_risk_features import load_p5_checkpoint
from scripts.generate_p2_validation import (
    build_p2_suite_payload,
    generate_p2_validation_suite,
    validate_p2_suite_disjointness,
)
from scripts.probe_p2_refinement import (
    audit_p2_evidence,
    benchmark_refinement_latency,
)
from scripts.run_p1_pilot import P1_FAMILIES, P1_SEEDS, inventory_p1_checkpoints
from scripts.run_p3_pilot import _load_reference_cache
from scripts.run_p4_executor import _environment, write_evidence_bundle

EXPECTED_PROBE_SHA256 = (
    "07c203fa7dcfbfde3fdc1f46e3fec63ede60f8b0bf4dccb3b963ad557791c50d"
)
METHODS = (
    "p5_anchor",
    "p5_long_anchor",
    "p5_static_low_rom",
    "p2_shell1",
    "p2_shell2_all",
    "fourier_only_rank21",
)


def p2_pilot_source_fingerprint(root: Path) -> str:
    files = sorted((root / "block_kyfan_pinn").rglob("*.py"))
    files.extend(
        root / "scripts" / name
        for name in (
            "generate_p2_validation.py",
            "run_p2_pilot.py",
            "probe_p2_refinement.py",
            "evaluate_risk_features.py",
            "run_p1_pilot.py",
            "run_p3_pilot.py",
            "run_p4_executor.py",
        )
    )
    files.append(root / "requirements.txt")
    digest = hashlib.sha256()
    for path in sorted(set(files), key=lambda value: str(value.relative_to(root))):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_p2_pilot_gate(summary: dict[str, object]) -> dict[str, object]:
    p2_near = float(summary["p2_shell2_all_near_mean"])
    long_near = float(summary["p5_long_anchor_near_mean"])
    p2_gap = float(summary["p2_shell2_all_gap_mean"])
    best_gap = min(
        float(summary["p5_anchor_gap_mean"]),
        float(summary["p5_long_anchor_gap_mean"]),
    )
    p2_overall = float(summary["p2_shell2_all_overall_mean"])
    long_overall = float(summary["p5_long_anchor_overall_mean"])
    fourier_overall = float(summary["fourier_only_rank21_overall_mean"])
    family = summary["family_near"]
    if not isinstance(family, dict) or set(family) != set(P1_FAMILIES):
        raise ValueError("P2 pilot requires both potential families")
    finite = (
        p2_near,
        long_near,
        p2_gap,
        best_gap,
        p2_overall,
        long_overall,
        fourier_overall,
        float(summary["maximum_orthogonality_error"]),
        float(summary["p2_latency_mean_ms"]),
        float(summary["p2_latency_p95_ms"]),
        float(summary["pwe_latency_mean_ms"]),
    )
    checks = {
        "engineering_pass": bool(summary["engineering_pass"])
        and all(math.isfinite(value) for value in finite),
        "near_improvement_pass": long_near > 0
        and (long_near - p2_near) / long_near >= 0.05,
        "gap_safety_pass": p2_gap <= 1.02 * best_gap,
        "both_families_pass": all(
            float(values["p2_shell2_all"])
            < float(values["p5_long_anchor"])
            for values in family.values()
            if isinstance(values, dict)
        )
        and all(isinstance(values, dict) for values in family.values()),
        "paired_wins_pass": int(summary["paired_near_comparisons"]) == 6
        and int(summary["paired_near_wins"]) >= 5,
        "overall_improvement_pass": long_overall > 0
        and (long_overall - p2_overall) / long_overall >= 0.05,
        "fourier_control_pass": p2_overall < fourier_overall,
        "orthogonality_pass": float(summary["maximum_orthogonality_error"])
        < 1e-4,
        "absolute_latency_pass": float(summary["p2_latency_mean_ms"]) <= 150.0
        and float(summary["p2_latency_p95_ms"]) <= 200.0,
        "pwe_speed_pass": float(summary["pwe_latency_mean_ms"]) > 0
        and float(summary["p2_latency_mean_ms"])
        <= 0.5 * float(summary["pwe_latency_mean_ms"]),
    }
    return {**checks, "pilot_go": all(checks.values())}


def _atomic_json(payload: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def _synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elif device.type == "mps":
        torch.mps.synchronize()


def _measure_basis(
    basis: torch.Tensor, reference: torch.Tensor
) -> tuple[float, float]:
    return projector_sine_error(basis, reference), orthogonality_error(basis)


def _aggregate(
    rows: list[dict[str, object]],
    latency_units: list[dict[str, object]],
    pwe_times: list[float],
) -> dict[str, object]:
    by_method = {
        method: [row for row in rows if row["method"] == method]
        for method in METHODS
    }
    expected: set[tuple[str, int, str]] | None = None
    engineering = len(rows) == 1728
    for selected in by_method.values():
        identities = {
            (str(row["family"]), int(row["seed"]), str(row["point_id"]))
            for row in selected
        }
        if len(selected) != 288 or len(identities) != 288:
            engineering = False
        if expected is None:
            expected = identities
        elif identities != expected:
            engineering = False
        if any(
            not math.isfinite(float(row[key]))
            for row in selected
            for key in ("projector_error", "orthogonality_error", "latency_ms")
        ):
            engineering = False

    def mean(method: str, split: str | None = None) -> float:
        values = [
            float(row["projector_error"])
            for row in by_method[method]
            if split is None or row["split"] == split
        ]
        return statistics.mean(values)

    summary: dict[str, object] = {
        "engineering_pass": engineering,
        "rows_per_method": {
            method: len(selected) for method, selected in by_method.items()
        },
        "maximum_orthogonality_error": max(
            float(row["orthogonality_error"]) for row in rows
        ),
    }
    for method in METHODS:
        summary[f"{method}_overall_mean"] = mean(method)
        summary[f"{method}_near_mean"] = mean(method, "near_cluster")
        summary[f"{method}_gap_mean"] = mean(method, "gap_scan")
    summary["family_near"] = {
        family: {
            method: statistics.mean(
                float(row["projector_error"])
                for row in by_method[method]
                if row["family"] == family and row["split"] == "near_cluster"
            )
            for method in ("p2_shell2_all", "p5_long_anchor")
        }
        for family in P1_FAMILIES
    }
    wins = 0
    comparisons = 0
    for family in P1_FAMILIES:
        for seed in P1_SEEDS:
            p2 = [
                float(row["projector_error"])
                for row in by_method["p2_shell2_all"]
                if row["family"] == family
                and int(row["seed"]) == seed
                and row["split"] == "near_cluster"
            ]
            baseline = [
                float(row["projector_error"])
                for row in by_method["p5_long_anchor"]
                if row["family"] == family
                and int(row["seed"]) == seed
                and row["split"] == "near_cluster"
            ]
            comparisons += 1
            wins += statistics.mean(p2) < statistics.mean(baseline)
    summary["paired_near_wins"] = wins
    summary["paired_near_comparisons"] = comparisons
    summary["latency_units"] = latency_units
    p2_means = [float(unit["p2_mean_ms"]) for unit in latency_units]
    p2_p95 = [float(unit["p2_p95_ms"]) for unit in latency_units]
    summary["p2_latency_mean_ms"] = statistics.mean(p2_means)
    summary["p2_latency_p95_ms"] = max(p2_p95)
    summary["pwe_latency_mean_ms"] = statistics.mean(pwe_times)
    summary["pwe_latency_samples_ms"] = pwe_times
    return summary


def audit_p2_pilot_evidence(
    archive_path: Path, sidecar_path: Path
) -> dict[str, object]:
    errors: list[str] = []
    actual = file_sha256(archive_path)
    tokens = sidecar_path.read_text().split() if sidecar_path.is_file() else []
    if not tokens or tokens[0] != actual:
        errors.append("outer sidecar mismatch")
    count = 0
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if len(names) != len(set(names)):
                errors.append("duplicate members")
            if any(
                PurePosixPath(name).is_absolute()
                or ".." in PurePosixPath(name).parts
                for name in names
            ):
                errors.append("unsafe member")
            mapping = {member.name: member for member in members}
            manifest_name = "results/p2-pilot-evidence-manifest.json"
            handle = archive.extractfile(mapping[manifest_name])
            if handle is None:
                raise ValueError("unreadable P2 pilot manifest")
            manifest = json.loads(handle.read())
            files = manifest["files"]
            count = len(files)
            declared = [str(row["path"]) for row in files]
            actual_files = {name for name, member in mapping.items() if member.isfile()}
            if len(declared) != len(set(declared)):
                errors.append("duplicate manifest paths")
            if actual_files != set(declared) | {manifest_name}:
                errors.append("missing or undeclared files")
            required = {
                "results/p2_pilot/gate.json",
                "artifacts/p5-evidence-20260801-092048.tar.gz",
                "artifacts/p5-evidence-20260801-092048.tar.gz.sha256",
                "artifacts/p2-refinement-probe-evidence-20260824-123743.tar.gz",
                "artifacts/p2-refinement-probe-evidence-20260824-123743.tar.gz.sha256",
                "data/p2_validation_v1_references.pt",
                "data/p2_validation_v1_references.sha256",
            }
            if not required.issubset(declared):
                errors.append("required P2 inputs missing")
            for row in files:
                member_handle = archive.extractfile(mapping[row["path"]])
                if member_handle is None:
                    errors.append(f"unreadable {row['path']}")
                    continue
                payload = member_handle.read()
                if len(payload) != int(row["bytes"]):
                    errors.append(f"size mismatch {row['path']}")
                if hashlib.sha256(payload).hexdigest() != row["sha256"]:
                    errors.append(f"hash mismatch {row['path']}")
    except (OSError, tarfile.TarError, KeyError, ValueError) as error:
        errors.append(str(error))
    return {"audit_pass": not errors, "archive_sha256": actual, "member_count": count, "errors": errors}


def run_pilot(args: argparse.Namespace) -> tuple[str, int]:
    root = Path(__file__).resolve().parents[1]
    output = root / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    suite_path = root / args.suite
    suite, suite_hash = load_frozen_suite(suite_path)
    if suite != build_p2_suite_payload(generate_p2_validation_suite()):
        raise ValueError("P2 suite does not match deterministic regeneration")
    validate_p2_suite_disjointness(suite["points"], root)
    cache_path = root / args.reference_cache
    references, cache_hash = _load_reference_cache(
        cache_path,
        suite_id=str(suite["suite_id"]),
        suite_hash=suite_hash,
        point_ids={str(point["id"]) for point in suite["points"]},
        grid_side=33,
        cutoff=24,
    )
    probe_archive = root / args.probe_evidence
    probe_sidecar = probe_archive.with_suffix(probe_archive.suffix + ".sha256")
    probe_audit = audit_p2_evidence(probe_archive, probe_sidecar)
    if probe_audit["audit_pass"] is not True or probe_audit["archive_sha256"] != EXPECTED_PROBE_SHA256:
        raise ValueError("P2 pilot requires approved probe evidence")
    p5_archive = root / args.p5_archive
    p5_sidecar = p5_archive.with_suffix(p5_archive.suffix + ".sha256")
    inventory = inventory_p1_checkpoints(p5_archive, p5_sidecar)
    _atomic_json(inventory, output / "checkpoint_inventory.json")
    inventory_map = {
        (str(row["method"]), str(row["family"]), int(row["seed"])): row
        for row in inventory
    }
    device = select_device(args.device)
    grid = uniform_grid(33)
    full_modes = hex_shell_modes(2)
    shell1_modes = hex_shell_modes(1)
    fourier21 = hex_shell_modes(2) + [(-3, -3), (-3, 0)]
    rows: list[dict[str, object]] = []
    latency_units: list[dict[str, object]] = []
    units = output / "units"
    units.mkdir(exist_ok=True)
    for family in P1_FAMILIES:
        family_points = [point for point in suite["points"] if point["family"] == family]
        for seed in P1_SEEDS:
            models = {
                method: load_p5_checkpoint(
                    p5_archive, inventory_map[(method, family, seed)], device
                )
                for method in ("p5_anchor", "p5_long_anchor", "p5_static_low_rom")
            }
            timing = benchmark_refinement_latency(
                models["p5_long_anchor"],
                family_points[0],
                device=device,
                modes=full_modes,
                warmup=args.latency_warmup,
                repeats=args.latency_repeats,
            )
            latency_units.append({"family": family, "seed": seed, **timing})
            unit_rows: list[dict[str, object]] = []
            for point in family_points:
                parameters = torch.tensor([point["parameters"]], device=device, dtype=torch.float32)
                reference = references[str(point["id"])]["basis"][..., :2, :].unsqueeze(0).to(device=device, dtype=torch.float32)
                for method, model in models.items():
                    coordinates = grid.unsqueeze(0).to(device).requires_grad_()
                    _synchronize(device)
                    started = time.perf_counter()
                    basis = periodic_mgs(model(coordinates, parameters))
                    _synchronize(device)
                    elapsed = (time.perf_counter() - started) * 1000.0
                    error, orth = _measure_basis(basis, reference)
                    unit_rows.append({"method": method, "family": family, "seed": seed, "split": point["split"], "point_id": point["id"], "projector_error": error, "orthogonality_error": orth, "latency_ms": elapsed, "trial_rank": 2})
                for method, modes in (("p2_shell1", shell1_modes), ("p2_shell2_all", full_modes)):
                    coordinates = grid.unsqueeze(0).to(device).requires_grad_()
                    _synchronize(device)
                    started = time.perf_counter()
                    neural = periodic_mgs(models["p5_long_anchor"](coordinates, parameters))
                    basis, info = neural_augmented_ritz_fast(neural, coordinates, parameters, family, modes)
                    _synchronize(device)
                    elapsed = (time.perf_counter() - started) * 1000.0
                    error, orth = _measure_basis(basis, reference)
                    unit_rows.append({"method": method, "family": family, "seed": seed, "split": point["split"], "point_id": point["id"], "projector_error": error, "orthogonality_error": orth, "latency_ms": elapsed, "trial_rank": info["trial_rank"]})
                coordinates = grid.unsqueeze(0).to(device).requires_grad_()
                _synchronize(device)
                started = time.perf_counter()
                basis = fourier_only_ritz_fast(coordinates, parameters, family, fourier21)
                _synchronize(device)
                elapsed = (time.perf_counter() - started) * 1000.0
                error, orth = _measure_basis(basis, reference)
                unit_rows.append({"method": "fourier_only_rank21", "family": family, "seed": seed, "split": point["split"], "point_id": point["id"], "projector_error": error, "orthogonality_error": orth, "latency_ms": elapsed, "trial_rank": 21})
            rows.extend(unit_rows)
            unit_path = units / f"{family}_seed{seed}.json"
            _atomic_json(unit_rows, unit_path)
            unit_path.with_suffix(".json.sha256").write_text(f"{file_sha256(unit_path)}  {unit_path.name}\n")
            print(f"P2_PILOT_UNIT_COMPLETE={family}:seed{seed}", flush=True)
    pwe_times: list[float] = []
    for family in P1_FAMILIES:
        point = next(point for point in suite["points"] if point["family"] == family)
        tensor = torch.tensor(point["parameters"], dtype=torch.float64)
        solve_reference(tensor, cutoff=24, rank=3, potential_family=family, mode_shape="hexagonal")
        for _ in range(args.pwe_repeats):
            started = time.perf_counter()
            solve_reference(tensor, cutoff=24, rank=3, potential_family=family, mode_shape="hexagonal")
            pwe_times.append((time.perf_counter() - started) * 1000.0)
    rows_path = output / "rows.csv"
    with rows_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = _aggregate(rows, latency_units, pwe_times)
    provenance = {
        "suite_sha256": suite_hash,
        "reference_sha256": cache_hash,
        "probe_evidence_sha256": probe_audit["archive_sha256"],
        "p5_evidence_sha256": file_sha256(p5_archive),
        "source_fingerprint": p2_pilot_source_fingerprint(root),
        "checkpoint_sha256": {
            f"{row['method']}:{row['family']}:{row['seed']}": row[
                "checkpoint_sha256"
            ]
            for row in inventory
        },
        "latency_warmup": args.latency_warmup,
        "latency_repeats": args.latency_repeats,
        "pwe_repeats": args.pwe_repeats,
        "environment": _environment(root, args.device),
    }
    _atomic_json(provenance, output / "provenance.json")
    summary.update(provenance)
    gate = build_p2_pilot_gate(summary)
    _atomic_json(summary, output / "summary.json")
    _atomic_json(gate, output / "gate.json")
    status = "P2_FULL_SHELL_PILOT_GO" if gate["pilot_go"] else "P2_FULL_SHELL_PILOT_STOP"
    (output / "report.md").write_text(f"# P2 full-shell pilot\n\n- Status: `{status}`\n- near: `{summary['p2_shell2_all_near_mean']:.6f}`\n- gap: `{summary['p2_shell2_all_gap_mean']:.6f}`\n")
    archive, sidecar, manifest = write_evidence_bundle(root=root, include_paths=(output, suite_path, suite_path.with_suffix(".sha256"), cache_path, cache_path.with_suffix(".sha256"), probe_archive, probe_sidecar, p5_archive, p5_sidecar, root / "block_kyfan_pinn/p2_refinement.py", root / "scripts/generate_p2_validation.py", root / "scripts/run_p2_pilot.py", root / "tests/test_p2_pilot_protocol.py", root / "requirements.txt"), output_dir=root / "artifacts", label=time.strftime("%Y%m%d-%H%M%S", time.gmtime()), prefix="p2-pilot-evidence", manifest_name="p2-pilot-evidence-manifest.json")
    evidence_audit = audit_p2_pilot_evidence(archive, sidecar)
    _atomic_json(evidence_audit, output / "evidence-audit.json")
    if evidence_audit["audit_pass"] is not True:
        raise RuntimeError(f"P2 pilot evidence audit failed: {evidence_audit['errors']}")
    print(f"P2_PILOT_EVIDENCE={archive}")
    print(f"P2_PILOT_EVIDENCE_SHA256={sidecar}")
    print(f"P2_PILOT_EVIDENCE_MANIFEST={manifest}")
    print(f"P2_PILOT_STATUS={status}")
    return status, 0 if gate["pilot_go"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--latency-warmup", type=int, default=10)
    parser.add_argument("--latency-repeats", type=int, default=100)
    parser.add_argument("--pwe-repeats", type=int, default=5)
    parser.add_argument("--suite", type=Path, default=Path("benchmarks/p2_validation_v1.json"))
    parser.add_argument("--reference-cache", type=Path, default=Path("data/p2_validation_v1_references.pt"))
    parser.add_argument("--probe-evidence", type=Path, default=Path("artifacts/p2-refinement-probe-evidence-20260824-123743.tar.gz"))
    parser.add_argument("--p5-archive", type=Path, default=Path("artifacts/p5-evidence-20260801-092048.tar.gz"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/p2_pilot"))
    return parser


def main() -> int:
    _, code = run_pilot(build_parser().parse_args())
    return code


if __name__ == "__main__":
    raise SystemExit(main())

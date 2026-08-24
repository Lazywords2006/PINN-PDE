#!/usr/bin/env python3
"""One-shot frozen-final evaluator for the P2 full-shell solver."""

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
from collections import defaultdict
from pathlib import Path, PurePosixPath

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.device import select_device
from block_kyfan_pinn.metrics import orthogonality_error, projector_sine_error
from block_kyfan_pinn.p2_refinement import (
    fourier_only_ritz_fast,
    hex_shell_modes,
    neural_augmented_ritz_fast,
    outer_shell_modes,
)
from block_kyfan_pinn.p5_model import P5_METHODS
from block_kyfan_pinn.physics import periodic_mgs
from block_kyfan_pinn.reference import uniform_grid
from block_kyfan_pinn.suites import file_sha256, load_frozen_suite
from scripts.audit_p5_evidence import audit_p5_evidence
from scripts.evaluate_risk_features import (
    EXPECTED_P5_ARCHIVE_SHA256,
    load_p5_checkpoint,
)
from scripts.generate_risk_development import build_reference_cache
from scripts.run_p1_pilot import P1_FAMILIES, P1_SEEDS
from scripts.run_p2_pilot import audit_p2_pilot_evidence
from scripts.run_p3_pilot import _load_reference_cache
from scripts.run_p4_executor import _environment, write_evidence_bundle

EXPECTED_PILOT_SHA256 = (
    "0c49461a6c780840ca678582019cc433df5741fd62ef546dcde7e964b71c071b"
)
FINAL_METHODS = (
    "p5_unanchored_low_rom",
    "p5_anchor",
    "p5_wide_anchor",
    "p5_long_anchor",
    "p5_static_low_rom",
    "p5_highfreq_rom",
    "p2_shell1",
    "p2_shell2_outer",
    "p2_shell2_all",
    "fourier_only_rank21",
)


def ensure_final_unused(output_dir: Path) -> None:
    forbidden = (
        "FINAL_EVALUATION_STARTED.json",
        "rows.csv",
        "summary.json",
        "gate.json",
    )
    if any((output_dir / name).exists() for name in forbidden):
        raise RuntimeError("frozen final evaluation has already started or completed")


def clustered_improvement_bootstrap(
    rows: list[dict[str, object]],
    *,
    primary: str,
    baseline: str,
    split: str | None,
    samples: int,
    seed: int,
) -> dict[str, float | int]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        if row["method"] not in {primary, baseline}:
            continue
        if split is not None and row["split"] != split:
            continue
        grouped[(str(row["method"]), str(row["point_id"]))].append(
            float(row["projector_error"])
        )
    points = sorted(
        point
        for method, point in grouped
        if method == primary and (baseline, point) in grouped
    )
    if not points or samples < 1:
        raise ValueError("bootstrap has no paired points or samples")
    primary_mean = {
        point: statistics.mean(grouped[(primary, point)]) for point in points
    }
    baseline_mean = {
        point: statistics.mean(grouped[(baseline, point)]) for point in points
    }
    generator = torch.Generator().manual_seed(seed)
    values: list[float] = []
    for _ in range(samples):
        indices = torch.randint(len(points), (len(points),), generator=generator)
        selected = [points[index] for index in indices.tolist()]
        p_mean = statistics.mean(primary_mean[point] for point in selected)
        b_mean = statistics.mean(baseline_mean[point] for point in selected)
        values.append((b_mean - p_mean) / b_mean)
    tensor = torch.tensor(values, dtype=torch.float64)
    return {
        "mean": float(tensor.mean()),
        "low": float(torch.quantile(tensor, 0.025)),
        "high": float(torch.quantile(tensor, 0.975)),
        "valid_samples": samples,
        "point_clusters": len(points),
    }


def build_final_gate(summary: dict[str, object]) -> dict[str, object]:
    p2_near = float(summary["p2_shell2_all_near_mean"])
    long_near = float(summary["p5_long_anchor_near_mean"])
    p2_gap = float(summary["p2_shell2_all_gap_mean"])
    best_gap = float(summary["best_neural_gap_mean"])
    p2_overall = float(summary["p2_shell2_all_overall_mean"])
    long_overall = float(summary["p5_long_anchor_overall_mean"])
    best_p5 = float(summary["best_p5_overall_mean"])
    fourier = float(summary["fourier_only_rank21_overall_mean"])
    family = summary["family_near"]
    checks = {
        "engineering_pass": bool(summary["engineering_pass"]),
        "near_improvement_pass": long_near > 0
        and (long_near - p2_near) / long_near >= 0.05,
        "gap_safety_pass": p2_gap <= 1.02 * best_gap,
        "both_families_pass": isinstance(family, dict)
        and set(family) == set(P1_FAMILIES)
        and all(
            float(values["p2_shell2_all"])
            < float(values["p5_long_anchor"])
            for values in family.values()
        ),
        "paired_wins_pass": int(summary["paired_near_comparisons"]) == 6
        and int(summary["paired_near_wins"]) >= 5,
        "overall_improvement_pass": long_overall > 0
        and (long_overall - p2_overall) / long_overall >= 0.05,
        "all_p5_baselines_pass": p2_overall < best_p5,
        "fourier_control_pass": p2_overall < fourier,
        "orthogonality_pass": float(summary["maximum_orthogonality_error"])
        < 1e-4,
        "overall_ci_pass": float(summary["overall_improvement_ci_low"]) > 0,
        "near_ci_pass": float(summary["near_improvement_ci_low"]) > 0,
    }
    return {**checks, "final_go": all(checks.values())}


def _atomic_json(payload: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def _read_member(
    archive: tarfile.TarFile, members: dict[str, tarfile.TarInfo], name: str
) -> bytes:
    handle = archive.extractfile(members[name])
    if handle is None:
        raise ValueError(f"unreadable evidence member: {name}")
    return handle.read()


def inventory_final_checkpoints(
    archive_path: Path, sidecar_path: Path
) -> list[dict[str, object]]:
    report = audit_p5_evidence(archive_path, sidecar_path)
    if report.get("audit_pass") is not True or report.get(
        "archive_sha256"
    ) != EXPECTED_P5_ARCHIVE_SHA256:
        raise ValueError("final checkpoint source P5 evidence is invalid")
    rows: list[dict[str, object]] = []
    with tarfile.open(archive_path, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        result_names = sorted(
            name
            for name in members
            if name.startswith("results/p5_promotion/") and name.endswith("/result.json")
        )
        for result_name in result_names:
            result = json.loads(_read_member(archive, members, result_name))
            config = result["config"]
            method = str(config["method"])
            family = str(config["potential_family"])
            seed = int(config["seed"])
            if method not in P5_METHODS:
                continue
            checkpoint_name = f"{result_name.rsplit('/', 1)[0]}/final.pt"
            payload = _read_member(archive, members, checkpoint_name)
            digest = hashlib.sha256(payload).hexdigest()
            if digest != result["final_checkpoint_sha256"] or result["status"] != "PASS":
                raise ValueError("invalid final P5 checkpoint")
            rows.append(
                {
                    "method": method,
                    "family": family,
                    "seed": seed,
                    "checkpoint_member": checkpoint_name,
                    "result_member": result_name,
                    "checkpoint_sha256": digest,
                    "config": config,
                }
            )
    expected = {
        (method, family, seed)
        for method in P5_METHODS
        for family in P1_FAMILIES
        for seed in P1_SEEDS
    }
    actual = {(row["method"], row["family"], row["seed"]) for row in rows}
    if len(rows) != 36 or actual != expected:
        raise ValueError("final P5 checkpoint inventory is incomplete")
    return rows


def _verify_pilot_go(archive_path: Path) -> None:
    with tarfile.open(archive_path, "r:gz") as archive:
        member = archive.getmember("results/p2_pilot/gate.json")
        handle = archive.extractfile(member)
        if handle is None:
            raise ValueError("pilot gate is unreadable")
        gate = json.loads(handle.read())
    if gate.get("pilot_go") is not True:
        raise ValueError("approved P2 pilot evidence does not contain GO")


def _source_fingerprint(root: Path) -> str:
    files = sorted((root / "block_kyfan_pinn").rglob("*.py"))
    files.extend(
        root / "scripts" / name
        for name in (
            "evaluate_p2_final.py",
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


def _aggregate(rows: list[dict[str, object]], bootstrap_samples: int) -> dict[str, object]:
    by_method = {
        method: [row for row in rows if row["method"] == method]
        for method in FINAL_METHODS
    }
    expected: set[tuple[str, int, str]] | None = None
    engineering = len(rows) == 19200
    for selected in by_method.values():
        identities = {
            (str(row["family"]), int(row["seed"]), str(row["point_id"]))
            for row in selected
        }
        if len(selected) != 1920 or len(identities) != 1920:
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
    for method in FINAL_METHODS:
        summary[f"{method}_overall_mean"] = mean(method)
        for split in (
            "iid_hidden",
            "exact_cluster",
            "near_cluster",
            "strict_ood",
            "gap_scan",
        ):
            summary[f"{method}_{split}_mean"] = mean(method, split)
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
    for family in P1_FAMILIES:
        for seed in P1_SEEDS:
            p2 = statistics.mean(
                float(row["projector_error"])
                for row in by_method["p2_shell2_all"]
                if row["family"] == family
                and int(row["seed"]) == seed
                and row["split"] == "near_cluster"
            )
            baseline = statistics.mean(
                float(row["projector_error"])
                for row in by_method["p5_long_anchor"]
                if row["family"] == family
                and int(row["seed"]) == seed
                and row["split"] == "near_cluster"
            )
            wins += p2 < baseline
    summary["paired_near_wins"] = wins
    summary["paired_near_comparisons"] = 6
    p5_methods = [method for method in FINAL_METHODS if method.startswith("p5_")]
    summary["best_p5_overall_mean"] = min(mean(method) for method in p5_methods)
    summary["best_neural_gap_mean"] = min(
        mean(method, "gap_scan") for method in p5_methods
    )
    overall_ci = clustered_improvement_bootstrap(
        rows,
        primary="p2_shell2_all",
        baseline="p5_long_anchor",
        split=None,
        samples=bootstrap_samples,
        seed=2026082405,
    )
    near_ci = clustered_improvement_bootstrap(
        rows,
        primary="p2_shell2_all",
        baseline="p5_long_anchor",
        split="near_cluster",
        samples=bootstrap_samples,
        seed=2026082406,
    )
    summary["overall_improvement_bootstrap"] = overall_ci
    summary["near_improvement_bootstrap"] = near_ci
    summary["overall_improvement_ci_low"] = overall_ci["low"]
    summary["near_improvement_ci_low"] = near_ci["low"]
    summary["seed_means"] = {
        method: {
            str(seed): statistics.mean(
                float(row["projector_error"])
                for row in by_method[method]
                if int(row["seed"]) == seed
            )
            for seed in P1_SEEDS
        }
        for method in FINAL_METHODS
    }
    summary["seed_std"] = {
        method: float(
            torch.tensor(
                list(summary["seed_means"][method].values()),
                dtype=torch.float64,
            ).std(unbiased=True)
        )
        for method in FINAL_METHODS
    }
    return summary


def _audit_final_evidence(archive_path: Path, sidecar_path: Path) -> dict[str, object]:
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
            manifest_name = "results/p2-final-evidence-manifest.json"
            manifest = json.loads(_read_member(archive, mapping, manifest_name))
            files = manifest["files"]
            count = len(files)
            declared = [str(row["path"]) for row in files]
            actual_files = {name for name, member in mapping.items() if member.isfile()}
            if len(declared) != len(set(declared)):
                errors.append("duplicate manifest paths")
            if actual_files != set(declared) | {manifest_name}:
                errors.append("missing or undeclared files")
            required = {
                "results/p2_final/gate.json",
                "benchmarks/v2_frozen_test.json",
                "benchmarks/v2_frozen_test.sha256",
                "data/v2_frozen_test_references.pt",
                "data/v2_frozen_test_references.sha256",
                "artifacts/p2-pilot-evidence-20260824-130211.tar.gz",
                "artifacts/p2-pilot-evidence-20260824-130211.tar.gz.sha256",
                "artifacts/p5-evidence-20260801-092048.tar.gz",
                "artifacts/p5-evidence-20260801-092048.tar.gz.sha256",
            }
            if not required.issubset(declared):
                errors.append("required final inputs missing")
            for row in files:
                payload = _read_member(archive, mapping, str(row["path"]))
                if len(payload) != int(row["bytes"]):
                    errors.append(f"size mismatch {row['path']}")
                if hashlib.sha256(payload).hexdigest() != row["sha256"]:
                    errors.append(f"hash mismatch {row['path']}")
    except (OSError, tarfile.TarError, KeyError, ValueError) as error:
        errors.append(str(error))
    return {"audit_pass": not errors, "archive_sha256": actual, "member_count": count, "errors": errors}


def build_final_cache(args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parents[1]
    suite_path = root / args.suite
    suite, _ = load_frozen_suite(suite_path)
    if suite.get("suite_id") != "block-kyfan-v2-frozen-test-20260730":
        raise ValueError("unexpected frozen final suite")
    output = root / args.reference_cache
    digest = build_reference_cache(
        suite_path, output, cutoff=24, grid_side=33, rank=3
    )
    print(f"P2_FINAL_REFERENCE_CACHE={output}")
    print(f"P2_FINAL_REFERENCE_SHA256={digest}")
    return 0


def run_final(args: argparse.Namespace) -> tuple[str, int]:
    root = Path(__file__).resolve().parents[1]
    output = root / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    ensure_final_unused(output)
    environment = _environment(root, args.device)
    if environment["git_status_porcelain"]:
        raise RuntimeError("frozen final requires a clean Git checkout")
    pilot_archive = root / args.pilot_evidence
    pilot_sidecar = pilot_archive.with_suffix(pilot_archive.suffix + ".sha256")
    pilot_audit = audit_p2_pilot_evidence(pilot_archive, pilot_sidecar)
    if pilot_audit["audit_pass"] is not True or pilot_audit[
        "archive_sha256"
    ] != EXPECTED_PILOT_SHA256:
        raise ValueError("approved P2 pilot evidence is invalid")
    _verify_pilot_go(pilot_archive)
    _atomic_json(
        {
            "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "git_commit": environment["git_commit"],
            "pilot_evidence_sha256": pilot_audit["archive_sha256"],
        },
        output / "FINAL_EVALUATION_STARTED.json",
    )
    suite_path = root / args.suite
    suite, suite_hash = load_frozen_suite(suite_path)
    if suite.get("suite_id") != "block-kyfan-v2-frozen-test-20260730":
        raise ValueError("unexpected frozen final suite")
    cache_path = root / args.reference_cache
    references, cache_hash = _load_reference_cache(
        cache_path,
        suite_id=str(suite["suite_id"]),
        suite_hash=suite_hash,
        point_ids={str(point["id"]) for point in suite["points"]},
        grid_side=33,
        cutoff=24,
    )
    p5_archive = root / args.p5_archive
    p5_sidecar = p5_archive.with_suffix(p5_archive.suffix + ".sha256")
    inventory = inventory_final_checkpoints(p5_archive, p5_sidecar)
    _atomic_json(inventory, output / "checkpoint_inventory.json")
    inventory_map = {
        (str(row["method"]), str(row["family"]), int(row["seed"])): row
        for row in inventory
    }
    device = select_device(args.device)
    grid = uniform_grid(33)
    shell1 = hex_shell_modes(1)
    outer2 = outer_shell_modes(2)
    full2 = hex_shell_modes(2)
    fourier21 = full2 + [(-3, -3), (-3, 0)]
    rows: list[dict[str, object]] = []
    units = output / "units"
    units.mkdir(exist_ok=True)
    for family in P1_FAMILIES:
        family_points = [point for point in suite["points"] if point["family"] == family]
        for seed in P1_SEEDS:
            models = {
                method: load_p5_checkpoint(
                    p5_archive, inventory_map[(method, family, seed)], device
                )
                for method in P5_METHODS
            }
            unit_rows: list[dict[str, object]] = []
            for point in family_points:
                parameters = torch.tensor([point["parameters"]], device=device, dtype=torch.float32)
                reference = references[str(point["id"])]["basis"][..., :2, :].unsqueeze(0).to(device=device, dtype=torch.float32)
                for method, model in models.items():
                    coordinates = grid.unsqueeze(0).to(device).requires_grad_()
                    torch.cuda.synchronize(device)
                    started = time.perf_counter()
                    basis = periodic_mgs(model(coordinates, parameters))
                    torch.cuda.synchronize(device)
                    elapsed = (time.perf_counter() - started) * 1000.0
                    unit_rows.append({"method": method, "family": family, "seed": seed, "split": point["split"], "point_id": point["id"], "projector_error": projector_sine_error(basis, reference), "orthogonality_error": orthogonality_error(basis), "latency_ms": elapsed})
                for method, modes in (("p2_shell1", shell1), ("p2_shell2_outer", outer2), ("p2_shell2_all", full2)):
                    coordinates = grid.unsqueeze(0).to(device).requires_grad_()
                    torch.cuda.synchronize(device)
                    started = time.perf_counter()
                    neural = periodic_mgs(models["p5_long_anchor"](coordinates, parameters))
                    basis, _ = neural_augmented_ritz_fast(neural, coordinates, parameters, family, modes)
                    torch.cuda.synchronize(device)
                    elapsed = (time.perf_counter() - started) * 1000.0
                    unit_rows.append({"method": method, "family": family, "seed": seed, "split": point["split"], "point_id": point["id"], "projector_error": projector_sine_error(basis, reference), "orthogonality_error": orthogonality_error(basis), "latency_ms": elapsed})
                coordinates = grid.unsqueeze(0).to(device).requires_grad_()
                torch.cuda.synchronize(device)
                started = time.perf_counter()
                basis = fourier_only_ritz_fast(coordinates, parameters, family, fourier21)
                torch.cuda.synchronize(device)
                elapsed = (time.perf_counter() - started) * 1000.0
                unit_rows.append({"method": "fourier_only_rank21", "family": family, "seed": seed, "split": point["split"], "point_id": point["id"], "projector_error": projector_sine_error(basis, reference), "orthogonality_error": orthogonality_error(basis), "latency_ms": elapsed})
            rows.extend(unit_rows)
            unit_path = units / f"{family}_seed{seed}.json"
            _atomic_json(unit_rows, unit_path)
            unit_path.with_suffix(".json.sha256").write_text(
                f"{file_sha256(unit_path)}  {unit_path.name}\n"
            )
            print(f"P2_FINAL_UNIT_COMPLETE={family}:seed{seed}", flush=True)
    rows_path = output / "rows.csv"
    with rows_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = _aggregate(rows, args.bootstrap_samples)
    provenance = {
        "suite_sha256": suite_hash,
        "reference_sha256": cache_hash,
        "pilot_evidence_sha256": pilot_audit["archive_sha256"],
        "p5_evidence_sha256": file_sha256(p5_archive),
        "source_fingerprint": _source_fingerprint(root),
        "bootstrap_samples": args.bootstrap_samples,
        "environment": environment,
    }
    summary.update(provenance)
    gate = build_final_gate(summary)
    _atomic_json(provenance, output / "provenance.json")
    _atomic_json(summary, output / "summary.json")
    _atomic_json(gate, output / "gate.json")
    status = "P2_FROZEN_FINAL_GO" if gate["final_go"] else "P2_FROZEN_FINAL_STOP"
    (output / "report.md").write_text(
        f"# P2 frozen final\n\n- Status: `{status}`\n"
        f"- overall: `{summary['p2_shell2_all_overall_mean']:.6f}`\n"
        f"- near: `{summary['p2_shell2_all_near_mean']:.6f}`\n"
        f"- gap: `{summary['p2_shell2_all_gap_mean']:.6f}`\n"
    )
    archive, sidecar, manifest = write_evidence_bundle(
        root=root,
        include_paths=(
            output,
            suite_path,
            suite_path.with_suffix(".sha256"),
            cache_path,
            cache_path.with_suffix(".sha256"),
            pilot_archive,
            pilot_sidecar,
            p5_archive,
            p5_sidecar,
            root / "block_kyfan_pinn/p2_refinement.py",
            root / "scripts/evaluate_p2_final.py",
            root / "tests/test_p2_final_protocol.py",
            root / "requirements.txt",
        ),
        output_dir=root / "artifacts",
        label=time.strftime("%Y%m%d-%H%M%S", time.gmtime()),
        prefix="p2-final-evidence",
        manifest_name="p2-final-evidence-manifest.json",
    )
    evidence_audit = _audit_final_evidence(archive, sidecar)
    _atomic_json(evidence_audit, output / "evidence-audit.json")
    if evidence_audit["audit_pass"] is not True:
        raise RuntimeError(f"final evidence audit failed: {evidence_audit['errors']}")
    print(f"P2_FINAL_EVIDENCE={archive}")
    print(f"P2_FINAL_EVIDENCE_SHA256={sidecar}")
    print(f"P2_FINAL_EVIDENCE_MANIFEST={manifest}")
    print(f"P2_FINAL_STATUS={status}")
    return status, 0 if gate["final_go"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--suite", type=Path, default=Path("benchmarks/v2_frozen_test.json"))
    parser.add_argument("--reference-cache", type=Path, default=Path("data/v2_frozen_test_references.pt"))
    parser.add_argument("--pilot-evidence", type=Path, default=Path("artifacts/p2-pilot-evidence-20260824-130211.tar.gz"))
    parser.add_argument("--p5-archive", type=Path, default=Path("artifacts/p5-evidence-20260801-092048.tar.gz"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/p2_final"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.cache_only == args.run:
        raise SystemExit("choose exactly one of --cache-only or --run")
    return build_final_cache(args) if args.cache_only else run_final(args)[1]


if __name__ == "__main__":
    raise SystemExit(main())

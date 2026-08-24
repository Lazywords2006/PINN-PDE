#!/usr/bin/env python3
"""Run the bounded P2 neural-augmented Galerkin mechanism probe."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
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
    fourier_only_ritz,
    hex_shell_modes,
    neural_augmented_ritz,
    outer_shell_modes,
)
from block_kyfan_pinn.physics import periodic_mgs
from block_kyfan_pinn.reference import uniform_grid
from block_kyfan_pinn.suites import file_sha256, load_frozen_suite
from scripts.evaluate_risk_features import load_p5_checkpoint
from scripts.run_p1_pilot import (
    P1_FAMILIES,
    P1_SEEDS,
    audit_p1_evidence,
    inventory_p1_checkpoints,
    validate_p1_runtime_suite,
)
from scripts.run_p3_pilot import _load_reference_cache
from scripts.run_p4_executor import _environment, write_evidence_bundle

EXPECTED_P1_EVIDENCE_SHA256 = (
    "3f4b0064aac3fa6a83c83f318498740fff1a2a4f56d8f5499e46af1a8edb1127"
)
P2_METHODS = (
    "p5_anchor",
    "p5_long_anchor",
    "fourier_only_outer2_plus_anchor",
    "p2_shell1",
    "p2_shell2_outer",
    "p2_shell2_all",
)


def p2_source_fingerprint(root: Path) -> str:
    files = sorted((root / "block_kyfan_pinn").rglob("*.py"))
    files.extend(
        root / "scripts" / name
        for name in (
            "probe_p2_refinement.py",
            "run_p1_pilot.py",
            "run_p3_pilot.py",
            "run_p4_executor.py",
            "evaluate_risk_features.py",
        )
    )
    files.append(root / "requirements.txt")
    if not files or not all(path.is_file() for path in files):
        raise FileNotFoundError("P2 source fingerprint set is incomplete")
    digest = hashlib.sha256()
    for path in sorted(set(files), key=lambda value: str(value.relative_to(root))):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def audit_p2_evidence(
    archive_path: Path, sidecar_path: Path
) -> dict[str, object]:
    """Reopen a P2 probe bundle and verify every manifest-bound input."""

    errors: list[str] = []
    actual = file_sha256(archive_path)
    tokens = sidecar_path.read_text().split() if sidecar_path.is_file() else []
    if not tokens or tokens[0] != actual:
        errors.append("outer sidecar mismatch")
    count = 0
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            all_members = archive.getmembers()
            names = [member.name for member in all_members]
            if len(names) != len(set(names)):
                errors.append("duplicate archive members")
            if any(
                PurePosixPath(name).is_absolute()
                or ".." in PurePosixPath(name).parts
                for name in names
            ):
                errors.append("unsafe archive member")
            members = {member.name: member for member in all_members}
            manifest_name = "results/p2-refinement-probe-evidence-manifest.json"
            manifest_handle = archive.extractfile(members[manifest_name])
            if manifest_handle is None:
                raise ValueError("P2 evidence manifest is unreadable")
            manifest = json.loads(manifest_handle.read())
            files = manifest.get("files") if isinstance(manifest, dict) else None
            if not isinstance(files, list) or not files:
                raise ValueError("P2 evidence manifest is malformed")
            count = len(files)
            declared_paths = [str(row.get("path", "")) for row in files]
            if len(declared_paths) != len(set(declared_paths)):
                errors.append("manifest paths are duplicated")
            actual_files = {name for name, member in members.items() if member.isfile()}
            if actual_files != set(declared_paths) | {manifest_name}:
                errors.append("archive contains missing or undeclared files")
            required = {
                "artifacts/p1-pilot-evidence-20260824-113650.tar.gz",
                "artifacts/p1-pilot-evidence-20260824-113650.tar.gz.sha256",
                "artifacts/p5-evidence-20260801-092048.tar.gz",
                "artifacts/p5-evidence-20260801-092048.tar.gz.sha256",
                "results/p2_refinement_probe/gate.json",
                "results/p2_refinement_probe/selection.json",
                "results/p2_refinement_probe/selection.sha256",
                "data/p1_validation_v1_references.pt",
                "data/p1_validation_v1_references.sha256",
            }
            if not required.issubset(declared_paths):
                errors.append("required P1/P5/P2 inputs are missing")
            for row in files:
                path = str(row["path"])
                handle = archive.extractfile(members[path])
                if handle is None:
                    errors.append(f"unreadable member: {path}")
                    continue
                payload = handle.read()
                if len(payload) != int(row["bytes"]):
                    errors.append(f"member size mismatch: {path}")
                if hashlib.sha256(payload).hexdigest() != row["sha256"]:
                    errors.append(f"member SHA-256 mismatch: {path}")
    except (OSError, tarfile.TarError, KeyError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "audit_pass": not errors,
        "archive_sha256": actual,
        "member_count": count,
        "errors": errors,
    }


def _means_by_point(rows: list[dict[str, object]]) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row["point_id"])].append(float(row["projector_error"]))
    return {point: statistics.mean(values) for point, values in grouped.items()}


def select_probe_points(
    rows: list[dict[str, object]], *, per_split: int = 2
) -> dict[str, dict[str, list[str]]]:
    """Select worst near points and largest anchor-over-long gap advantages."""

    if per_split < 1:
        raise ValueError("per_split must be positive")
    selected: dict[str, dict[str, list[str]]] = {}
    for family in P1_FAMILIES:
        near_rows = [
            row
            for row in rows
            if row.get("method") == "p5_long_anchor"
            and row.get("family") == family
            and row.get("split") == "near_cluster"
        ]
        near_means = _means_by_point(near_rows)
        near = [
            point
            for point, _ in sorted(
                near_means.items(), key=lambda item: (-item[1], item[0])
            )[:per_split]
        ]
        anchor_rows = [
            row
            for row in rows
            if row.get("method") == "p5_anchor"
            and row.get("family") == family
            and row.get("split") == "gap_scan"
        ]
        long_rows = [
            row
            for row in rows
            if row.get("method") == "p5_long_anchor"
            and row.get("family") == family
            and row.get("split") == "gap_scan"
        ]
        anchor_means = _means_by_point(anchor_rows)
        long_means = _means_by_point(long_rows)
        common = set(anchor_means) & set(long_means)
        advantages = {
            point: long_means[point] - anchor_means[point] for point in common
        }
        gap = [
            point
            for point, _ in sorted(
                advantages.items(), key=lambda item: (-item[1], item[0])
            )[:per_split]
        ]
        if len(near) != per_split or len(gap) != per_split:
            raise ValueError(f"insufficient P2 diagnostic points for {family}")
        selected[family] = {"near_cluster": near, "gap_scan": gap}
    return selected


def build_probe_gate(summary: dict[str, object]) -> dict[str, object]:
    """Apply the frozen P2-A mechanism-probe thresholds."""

    p2_near = float(summary["p2_shell2_outer_near_mean"])
    long_near = float(summary["p5_long_anchor_near_mean"])
    p2_gap = float(summary["p2_shell2_outer_gap_mean"])
    anchor_gap = float(summary["p5_anchor_gap_mean"])
    p2_overall = float(summary["p2_shell2_outer_overall_mean"])
    fourier_overall = float(
        summary["fourier_only_outer2_plus_anchor_overall_mean"]
    )
    family = summary["family_near"]
    if not isinstance(family, dict) or set(family) != set(P1_FAMILIES):
        raise ValueError("P2 probe summary must contain both families")
    finite = (
        p2_near,
        long_near,
        p2_gap,
        anchor_gap,
        p2_overall,
        fourier_overall,
        float(summary["maximum_orthogonality_error"]),
        float(summary["latency_ratio"]),
    )
    checks = {
        "engineering_pass": bool(summary["engineering_pass"])
        and all(math.isfinite(value) for value in finite),
        "near_improvement_pass": long_near > 0.0
        and (long_near - p2_near) / long_near >= 0.02,
        "gap_safety_pass": p2_gap <= 1.02 * anchor_gap,
        "both_families_pass": all(
            float(values["p2_shell2_outer"])
            < float(values["p5_long_anchor"])
            for values in family.values()
            if isinstance(values, dict)
        )
        and all(isinstance(values, dict) for values in family.values()),
        "paired_wins_pass": int(summary["paired_near_comparisons"]) == 6
        and int(summary["paired_near_wins"]) >= 5,
        "fourier_control_pass": p2_overall < fourier_overall,
        "orthogonality_pass": float(summary["maximum_orthogonality_error"])
        < 1e-4,
        "latency_pass": float(summary["latency_ratio"]) <= 5.0,
    }
    return {**checks, "probe_go": all(checks.values())}


def _write_json(payload: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _load_rows(path: Path) -> list[dict[str, object]]:
    with path.open() as handle:
        return list(csv.DictReader(handle))


def load_audited_p1_rows(archive_path: Path) -> tuple[list[dict[str, object]], str]:
    """Read P1 rows only from their audited evidence manifest binding."""

    manifest_name = "results/p1-pilot-evidence-manifest.json"
    rows_name = "results/p1_pilot/rows.csv"
    with tarfile.open(archive_path, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        manifest_handle = archive.extractfile(members[manifest_name])
        rows_handle = archive.extractfile(members[rows_name])
        if manifest_handle is None or rows_handle is None:
            raise ValueError("P1 evidence rows or manifest are unreadable")
        manifest = json.loads(manifest_handle.read())
        payload = rows_handle.read()
    entries = {
        str(row["path"]): row
        for row in manifest.get("files", [])
        if isinstance(row, dict) and "path" in row
    }
    entry = entries.get(rows_name)
    if entry is None:
        raise ValueError("P1 rows are absent from the evidence manifest")
    digest = hashlib.sha256(payload).hexdigest()
    if len(payload) != int(entry["bytes"]) or digest != entry["sha256"]:
        raise ValueError("P1 rows do not match the evidence manifest")
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8")))), digest


def _synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elif device.type == "mps":
        torch.mps.synchronize()


def benchmark_refinement_latency(
    long_model: torch.nn.Module,
    point: dict[str, object],
    *,
    device: torch.device,
    modes: list[tuple[int, int]],
    warmup: int,
    repeats: int,
) -> dict[str, float | int]:
    """Benchmark complete long-anchor and production P2 query paths."""

    if warmup < 0 or repeats < 1:
        raise ValueError("invalid P2 latency policy")
    grid = uniform_grid(33)
    family = str(point["family"])
    parameters = torch.tensor(
        [point["parameters"]], device=device, dtype=torch.float32
    )

    def long_query() -> None:
        coordinates = grid.unsqueeze(0).to(device).requires_grad_()
        periodic_mgs(long_model(coordinates, parameters))

    def p2_query() -> None:
        coordinates = grid.unsqueeze(0).to(device).requires_grad_()
        neural = periodic_mgs(long_model(coordinates, parameters))
        neural_augmented_ritz(
            neural, coordinates, parameters, family, modes
        )

    for _ in range(warmup):
        long_query()
        p2_query()
        _synchronize(device)

    def measure(query: object) -> list[float]:
        values: list[float] = []
        for _ in range(repeats):
            _synchronize(device)
            started = time.perf_counter()
            query()
            _synchronize(device)
            values.append((time.perf_counter() - started) * 1000.0)
        return values

    long_values = torch.tensor(measure(long_query), dtype=torch.float64)
    p2_values = torch.tensor(measure(p2_query), dtype=torch.float64)
    return {
        "warmup": warmup,
        "repeats": repeats,
        "long_mean_ms": float(long_values.mean()),
        "long_p50_ms": float(torch.quantile(long_values, 0.50)),
        "long_p95_ms": float(torch.quantile(long_values, 0.95)),
        "p2_mean_ms": float(p2_values.mean()),
        "p2_p50_ms": float(torch.quantile(p2_values, 0.50)),
        "p2_p95_ms": float(torch.quantile(p2_values, 0.95)),
    }


def _evaluate(
    basis: torch.Tensor, reference: torch.Tensor
) -> tuple[float, float]:
    return projector_sine_error(basis, reference), orthogonality_error(basis)


def _aggregate(rows: list[dict[str, object]]) -> dict[str, object]:
    by_method = {
        method: [row for row in rows if row.get("method") == method]
        for method in P2_METHODS
    }
    expected_identities: set[tuple[str, int, str]] | None = None
    engineering_pass = not any(
        row.get("method") not in P2_METHODS for row in rows
    )
    for method, selected in by_method.items():
        identities = {
            (str(row["family"]), int(row["seed"]), str(row["point_id"]))
            for row in selected
        }
        if len(selected) != 24 or len(identities) != 24:
            engineering_pass = False
        if expected_identities is None:
            expected_identities = identities
        elif identities != expected_identities:
            engineering_pass = False
        split_counts = {
            split: sum(row["split"] == split for row in selected)
            for split in ("near_cluster", "gap_scan")
        }
        if split_counts != {"near_cluster": 12, "gap_scan": 12}:
            engineering_pass = False
        if any(
            not all(
                math.isfinite(float(row[name]))
                for name in (
                    "projector_error",
                    "orthogonality_error",
                    "latency_ms",
                    "trial_rank",
                )
            )
            or int(row["trial_rank"]) < 2
            for row in selected
        ):
            engineering_pass = False

    def mean(method: str, split: str | None = None) -> float:
        values = [
            float(row["projector_error"])
            for row in rows
            if row["method"] == method
            and (split is None or row["split"] == split)
        ]
        return statistics.mean(values) if values else math.inf

    summary: dict[str, object] = {
        "engineering_pass": engineering_pass
        and len(rows) == len(P2_METHODS) * 24,
        "rows_per_method": {
            method: len(selected) for method, selected in by_method.items()
        },
        "maximum_orthogonality_error": max(
            float(row["orthogonality_error"]) for row in rows
        ),
    }
    for method in P2_METHODS:
        summary[f"{method}_overall_mean"] = mean(method)
        summary[f"{method}_near_mean"] = mean(method, "near_cluster")
        summary[f"{method}_gap_mean"] = mean(method, "gap_scan")
    family_near: dict[str, dict[str, float]] = {}
    for family in P1_FAMILIES:
        family_near[family] = {}
        for method in ("p2_shell2_outer", "p5_long_anchor"):
            values = [
                float(row["projector_error"])
                for row in rows
                if row["method"] == method
                and row["family"] == family
                and row["split"] == "near_cluster"
            ]
            family_near[family][method] = statistics.mean(values)
    summary["family_near"] = family_near
    wins = 0
    comparisons = 0
    for family in P1_FAMILIES:
        for seed in P1_SEEDS:
            p2 = [
                float(row["projector_error"])
                for row in rows
                if row["method"] == "p2_shell2_outer"
                and row["family"] == family
                and int(row["seed"]) == seed
                and row["split"] == "near_cluster"
            ]
            baseline = [
                float(row["projector_error"])
                for row in rows
                if row["method"] == "p5_long_anchor"
                and row["family"] == family
                and int(row["seed"]) == seed
                and row["split"] == "near_cluster"
            ]
            if p2 and baseline:
                comparisons += 1
                wins += statistics.mean(p2) < statistics.mean(baseline)
    summary["paired_near_wins"] = wins
    summary["paired_near_comparisons"] = comparisons
    p2_times = [
        float(row["latency_ms"])
        for row in rows
        if row["method"] == "p2_shell2_outer"
    ]
    long_times = [
        float(row["latency_ms"])
        for row in rows
        if row["method"] == "p5_long_anchor"
    ]
    summary["latency_ratio"] = statistics.mean(p2_times) / statistics.mean(
        long_times
    )
    return summary


def run_probe(args: argparse.Namespace) -> tuple[str, int]:
    root = Path(__file__).resolve().parents[1]
    output = root / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    p1_archive = root / args.p1_evidence
    p1_sidecar = p1_archive.with_suffix(p1_archive.suffix + ".sha256")
    audit = audit_p1_evidence(p1_archive, p1_sidecar)
    if audit["audit_pass"] is not True or audit["archive_sha256"] != EXPECTED_P1_EVIDENCE_SHA256:
        raise ValueError("P2 probe requires the approved audited P1 evidence")
    p1_rows, p1_rows_hash = load_audited_p1_rows(p1_archive)
    suite_path = root / args.suite
    suite, suite_hash = load_frozen_suite(suite_path)
    validate_p1_runtime_suite(suite, root)
    selection_path = output / "selection.json"
    if args.select_only:
        selection = {
            "protocol": "p2-neural-galerkin-probe-v1-20260824",
            "p1_evidence_sha256": audit["archive_sha256"],
            "p1_rows_sha256": p1_rows_hash,
            "suite_sha256": suite_hash,
            "selected": select_probe_points(p1_rows),
        }
        _write_json(selection, selection_path)
        digest = file_sha256(selection_path)
        selection_path.with_suffix(".sha256").write_text(
            f"{digest}  {selection_path.name}\n"
        )
        print(f"P2_SELECTION={selection_path}")
        print(f"P2_SELECTION_SHA256={digest}")
        return "P2_SELECTION_FROZEN", 0

    selection = json.loads(selection_path.read_text())
    declared = selection_path.with_suffix(".sha256").read_text().split()[0]
    if declared != file_sha256(selection_path):
        raise ValueError("P2 selection SHA-256 mismatch")
    if selection["suite_sha256"] != suite_hash:
        raise ValueError("P2 selection suite mismatch")
    if selection["p1_rows_sha256"] != p1_rows_hash:
        raise ValueError("P2 selection does not match audited P1 rows")
    if selection.get("protocol") != "p2-neural-galerkin-probe-v1-20260824":
        raise ValueError("unexpected P2 selection protocol")
    selected_payload = selection.get("selected")
    if not isinstance(selected_payload, dict) or set(selected_payload) != set(
        P1_FAMILIES
    ):
        raise ValueError("P2 selection family structure is invalid")
    for family, splits in selected_payload.items():
        if not isinstance(splits, dict) or set(splits) != {
            "near_cluster",
            "gap_scan",
        }:
            raise ValueError(f"P2 selection splits are invalid for {family}")
        if any(
            not isinstance(values, list)
            or len(values) != 2
            or len(set(values)) != 2
            for values in splits.values()
        ):
            raise ValueError(f"P2 selection counts are invalid for {family}")
    selected_ids = {
        point
        for family in selected_payload.values()
        for values in family.values()
        for point in values
    }
    points = [point for point in suite["points"] if point["id"] in selected_ids]
    if len(points) != 8:
        raise ValueError("P2 probe must contain eight unique points")

    cache_path = root / args.reference_cache
    references, cache_hash = _load_reference_cache(
        cache_path,
        suite_id=str(suite["suite_id"]),
        suite_hash=suite_hash,
        point_ids=selected_ids,
        grid_side=33,
        cutoff=24,
    )
    p5_archive = root / args.p5_archive
    p5_sidecar = p5_archive.with_suffix(p5_archive.suffix + ".sha256")
    inventory = inventory_p1_checkpoints(p5_archive, p5_sidecar)
    _write_json(inventory, output / "checkpoint_inventory.json")
    inventory_map = {
        (str(row["method"]), str(row["family"]), int(row["seed"])): row
        for row in inventory
    }
    device = select_device(args.device)
    methods_modes = {
        "p2_shell1": hex_shell_modes(1),
        "p2_shell2_outer": outer_shell_modes(2),
        "p2_shell2_all": hex_shell_modes(2),
    }
    control_modes = outer_shell_modes(2) + [(0, 0), (-1, 0)]
    result_rows: list[dict[str, object]] = []
    latency_units: list[dict[str, object]] = []
    grid = uniform_grid(33)
    for family in P1_FAMILIES:
        family_points = [point for point in points if point["family"] == family]
        for seed in P1_SEEDS:
            anchor_model = load_p5_checkpoint(
                p5_archive, inventory_map[("p5_anchor", family, seed)], device
            )
            long_model = load_p5_checkpoint(
                p5_archive, inventory_map[("p5_long_anchor", family, seed)], device
            )
            timing = benchmark_refinement_latency(
                long_model,
                family_points[0],
                device=device,
                modes=outer_shell_modes(2),
                warmup=args.latency_warmup,
                repeats=args.latency_repeats,
            )
            latency_units.append({"family": family, "seed": seed, **timing})
            for point in family_points:
                reference = (
                    references[str(point["id"])]["basis"][..., :2, :]
                    .unsqueeze(0)
                    .to(device=device, dtype=torch.float32)
                )
                parameters = torch.tensor(
                    [point["parameters"]], device=device, dtype=torch.float32
                )
                for method, model in (
                    ("p5_anchor", anchor_model),
                    ("p5_long_anchor", long_model),
                ):
                    coordinates = grid.unsqueeze(0).to(device).requires_grad_()
                    _synchronize(device)
                    started = time.perf_counter()
                    basis = periodic_mgs(model(coordinates, parameters))
                    _synchronize(device)
                    elapsed = (time.perf_counter() - started) * 1000.0
                    error, orth = _evaluate(basis, reference)
                    result_rows.append(
                        {
                            "method": method,
                            "family": family,
                            "seed": seed,
                            "split": point["split"],
                            "point_id": point["id"],
                            "projector_error": error,
                            "orthogonality_error": orth,
                            "latency_ms": elapsed,
                            "trial_rank": 2,
                        }
                    )
                coordinates = grid.unsqueeze(0).to(device).requires_grad_()
                _synchronize(device)
                started = time.perf_counter()
                fourier = fourier_only_ritz(
                    coordinates, parameters, family, control_modes
                )
                _synchronize(device)
                elapsed = (time.perf_counter() - started) * 1000.0
                error, orth = _evaluate(fourier, reference)
                result_rows.append(
                    {
                        "method": "fourier_only_outer2_plus_anchor",
                        "family": family,
                        "seed": seed,
                        "split": point["split"],
                        "point_id": point["id"],
                        "projector_error": error,
                        "orthogonality_error": orth,
                        "latency_ms": elapsed,
                        "trial_rank": len(control_modes),
                    }
                )
                for method, modes in methods_modes.items():
                    coordinates = grid.unsqueeze(0).to(device).requires_grad_()
                    _synchronize(device)
                    started = time.perf_counter()
                    neural = periodic_mgs(long_model(coordinates, parameters))
                    refined, info = neural_augmented_ritz(
                        neural, coordinates, parameters, family, modes
                    )
                    _synchronize(device)
                    elapsed = (time.perf_counter() - started) * 1000.0
                    error, orth = _evaluate(refined, reference)
                    result_rows.append(
                        {
                            "method": method,
                            "family": family,
                            "seed": seed,
                            "split": point["split"],
                            "point_id": point["id"],
                            "projector_error": error,
                            "orthogonality_error": orth,
                            "latency_ms": elapsed,
                            "trial_rank": info["trial_rank"],
                        }
                    )
            print(f"P2_UNIT_COMPLETE={family}:seed{seed}", flush=True)

    rows_file = output / "rows.csv"
    with rows_file.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result_rows[0]))
        writer.writeheader()
        writer.writerows(result_rows)
    summary = _aggregate(result_rows)
    summary["latency_units"] = latency_units
    summary["latency_ratio"] = statistics.mean(
        float(unit["p2_mean_ms"]) for unit in latency_units
    ) / statistics.mean(float(unit["long_mean_ms"]) for unit in latency_units)
    provenance = {
        "suite_sha256": suite_hash,
        "reference_sha256": cache_hash,
        "p1_evidence_sha256": audit["archive_sha256"],
        "p5_evidence_sha256": file_sha256(p5_archive),
        "selection_sha256": file_sha256(selection_path),
        "source_fingerprint": p2_source_fingerprint(root),
        "checkpoint_sha256": {
            f"{row['method']}:{row['family']}:{row['seed']}": row[
                "checkpoint_sha256"
            ]
            for row in inventory
            if row["method"] in {"p5_anchor", "p5_long_anchor"}
        },
        "latency_warmup": args.latency_warmup,
        "latency_repeats": args.latency_repeats,
        "environment": _environment(root, args.device),
    }
    _write_json(provenance, output / "provenance.json")
    summary.update(provenance)
    gate = build_probe_gate(summary)
    _write_json(summary, output / "summary.json")
    _write_json(gate, output / "gate.json")
    status = (
        "P2_REFINEMENT_PROBE_GO" if gate["probe_go"] else "P2_REFINEMENT_PROBE_STOP"
    )
    (output / "report.md").write_text(
        f"# P2 refinement probe\n\n- Status: `{status}`\n"
        f"- P2 near: `{summary['p2_shell2_outer_near_mean']:.6f}`\n"
        f"- long-anchor near: `{summary['p5_long_anchor_near_mean']:.6f}`\n"
        f"- P2 gap: `{summary['p2_shell2_outer_gap_mean']:.6f}`\n"
    )
    archive, sidecar, manifest = write_evidence_bundle(
        root=root,
        include_paths=(
            output,
            selection_path,
            selection_path.with_suffix(".sha256"),
            suite_path,
            suite_path.with_suffix(".sha256"),
            cache_path,
            cache_path.with_suffix(".sha256"),
            p1_archive,
            p1_sidecar,
            p5_archive,
            p5_sidecar,
            root / "block_kyfan_pinn/p2_refinement.py",
            root / "scripts/probe_p2_refinement.py",
            root / "tests/test_p2_refinement.py",
            root / "tests/test_p2_protocol.py",
            root / "requirements.txt",
        ),
        output_dir=root / "artifacts",
        label=time.strftime("%Y%m%d-%H%M%S", time.gmtime()),
        prefix="p2-refinement-probe-evidence",
        manifest_name="p2-refinement-probe-evidence-manifest.json",
    )
    evidence_audit = audit_p2_evidence(archive, sidecar)
    _write_json(evidence_audit, output / "evidence-audit.json")
    if evidence_audit["audit_pass"] is not True:
        raise RuntimeError(f"P2 evidence audit failed: {evidence_audit['errors']}")
    print(f"P2_EVIDENCE_BUNDLE={archive}")
    print(f"P2_EVIDENCE_SHA256={sidecar}")
    print(f"P2_EVIDENCE_MANIFEST={manifest}")
    print(f"P2_STATUS={status}")
    return status, 0 if gate["probe_go"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--select-only", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--latency-warmup", type=int, default=10)
    parser.add_argument("--latency-repeats", type=int, default=100)
    parser.add_argument(
        "--p1-evidence",
        type=Path,
        default=Path("artifacts/p1-pilot-evidence-20260824-113650.tar.gz"),
    )
    parser.add_argument(
        "--suite", type=Path, default=Path("benchmarks/p1_validation_v1.json")
    )
    parser.add_argument(
        "--reference-cache",
        type=Path,
        default=Path("data/p1_validation_v1_references.pt"),
    )
    parser.add_argument(
        "--p5-archive",
        type=Path,
        default=Path("artifacts/p5-evidence-20260801-092048.tar.gz"),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("results/p2_refinement_probe")
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.select_only == args.run:
        raise SystemExit("choose exactly one of --select-only or --run")
    _, code = run_probe(args)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

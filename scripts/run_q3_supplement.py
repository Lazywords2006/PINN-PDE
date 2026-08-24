#!/usr/bin/env python3
"""Run the independent SCI-Q3 journal-baseline supplement."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import statistics
import subprocess
import sys
import tarfile
import time
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path, PurePosixPath

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.device import select_device
from block_kyfan_pinn.experiment import (
    ExperimentConfig,
    _source_fingerprint,
    run_experiment,
)
from block_kyfan_pinn.metrics import orthogonality_error, projector_sine_error
from block_kyfan_pinn.p2_refinement import hex_shell_modes, neural_augmented_ritz_fast
from block_kyfan_pinn.physics import (
    apply_hamiltonian,
    galerkin_rank_basis,
    periodic_mgs,
    projected_residual_rms,
)
from block_kyfan_pinn.suites import file_sha256, load_frozen_suite
from scripts.evaluate_risk_features import load_p5_checkpoint
from scripts.evaluate_sci3_suite import _load_model
from scripts.generate_v2_assets import TRAINING_BOUNDS
from scripts.run_p1_pilot import P1_FAMILIES, inventory_p1_checkpoints
from scripts.run_p4_executor import write_evidence_bundle

Q3_METHODS = (
    "p2_full_shell",
    "wang_xie_trace_adapted",
    "dai_galerkin_adapted",
)
Q3_BASELINES = Q3_METHODS[1:]
Q3_SEEDS = (42, 137, 251)
P5_ARCHIVE_NAME = "p5-evidence-20260801-092048.tar.gz"


def validate_result_identities(
    rows: Sequence[dict[str, object]], points: Sequence[dict[str, object]]
) -> None:
    expected = {
        (method, seed, str(point["id"]), str(point["family"]))
        for method in Q3_METHODS
        for seed in Q3_SEEDS
        for point in points
    }
    actual = {
        (
            str(row["method"]),
            int(row["seed"]),
            str(row["point_id"]),
            str(row["family"]),
        )
        for row in rows
    }
    if len(rows) != len(expected) or actual != expected:
        raise ValueError("Q3 result identity matrix is incomplete or unexpected")


def build_q3_gate(summary: dict[str, object]) -> dict[str, object]:
    overall = summary.get("overall")
    splits = summary.get("splits")
    wins = summary.get("paired_family_seed_wins")
    bootstrap = summary.get("bootstrap_improvement")
    if not all(isinstance(value, dict) for value in (overall, splits, wins, bootstrap)):
        raise ValueError("Q3 summary is missing gate inputs")
    near = splits.get("near_cluster")
    gap = splits.get("gap_scan")
    if not isinstance(near, dict) or not isinstance(gap, dict):
        raise TypeError("Q3 summary is missing near/gap splits")

    finite_values = [float(overall[method]) for method in Q3_METHODS] + [
        float(values[method]) for values in (near, gap) for method in Q3_METHODS
    ]
    checks: dict[str, object] = {
        "engineering_pass": bool(summary.get("engineering_pass"))
        and all(math.isfinite(value) for value in finite_values),
        "overall_better_than_each_baseline": all(
            float(overall["p2_full_shell"]) < float(overall[baseline])
            for baseline in Q3_BASELINES
        ),
        "near_better_than_each_baseline": all(
            float(near["p2_full_shell"]) < float(near[baseline])
            for baseline in Q3_BASELINES
        ),
        "gap_better_than_each_baseline": all(
            float(gap["p2_full_shell"]) < float(gap[baseline])
            for baseline in Q3_BASELINES
        ),
        "at_least_5_of_6_family_seed_wins": all(
            int(wins[baseline]) >= 5 for baseline in Q3_BASELINES
        ),
        "bootstrap_ci_positive": all(
            float(bootstrap[baseline]["low"]) > 0.0 for baseline in Q3_BASELINES
        ),
        "orthogonality_pass": float(
            summary.get("maximum_orthogonality_error", math.inf)
        )
        < 1e-4,
    }
    checks["q3_supplement_go"] = all(bool(value) for value in checks.values())
    return checks


def _percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def _clustered_bootstrap_improvement(
    rows: Sequence[dict[str, object]], baseline: str, samples: int
) -> dict[str, object]:
    if samples < 20:
        raise ValueError("clustered bootstrap requires at least 20 samples")
    point_ids = sorted({str(row["point_id"]) for row in rows})
    lookup = {
        (str(row["method"]), int(row["seed"]), str(row["point_id"])): float(
            row["projector_error"]
        )
        for row in rows
    }
    rng = random.Random(2026082412)
    improvements: list[float] = []
    for _ in range(samples):
        selected = [rng.choice(point_ids) for _ in point_ids]
        primary_values = [
            lookup[("p2_full_shell", seed, identity)]
            for identity in selected
            for seed in Q3_SEEDS
        ]
        baseline_values = [
            lookup[(baseline, seed, identity)]
            for identity in selected
            for seed in Q3_SEEDS
        ]
        primary_mean = statistics.mean(primary_values)
        baseline_mean = statistics.mean(baseline_values)
        improvements.append((baseline_mean - primary_mean) / max(baseline_mean, 1e-12))
    return {
        "mean": statistics.mean(improvements),
        "low": _percentile(improvements, 0.025),
        "high": _percentile(improvements, 0.975),
        "samples": samples,
        "point_clusters": len(point_ids),
    }


def aggregate_q3_rows(
    rows: Sequence[dict[str, object]],
    points: Sequence[dict[str, object]],
    *,
    bootstrap_samples: int = 2000,
) -> dict[str, object]:
    validate_result_identities(rows, points)
    numeric_keys = (
        "projector_error",
        "orthogonality_error",
        "residual_rms",
        "latency_ms",
    )
    engineering = all(
        math.isfinite(float(row[key])) for row in rows for key in numeric_keys
    )

    def mean(
        method: str,
        *,
        key: str = "projector_error",
        split: str | None = None,
        family: str | None = None,
        seed: int | None = None,
    ) -> float:
        values = [
            float(row[key])
            for row in rows
            if row["method"] == method
            and (split is None or row["split"] == split)
            and (family is None or row["family"] == family)
            and (seed is None or int(row["seed"]) == seed)
        ]
        if not values:
            raise ValueError("Q3 aggregate selection is empty")
        return statistics.mean(values)

    split_names = sorted({str(point["split"]) for point in points})
    overall = {method: mean(method) for method in Q3_METHODS}
    splits = {
        split: {method: mean(method, split=split) for method in Q3_METHODS}
        for split in split_names
    }
    families = {
        family: {method: mean(method, family=family) for method in Q3_METHODS}
        for family in P1_FAMILIES
    }
    seed_means = {
        method: {str(seed): mean(method, seed=seed) for seed in Q3_SEEDS}
        for method in Q3_METHODS
    }
    wins = {
        baseline: sum(
            mean("p2_full_shell", family=family, seed=seed)
            < mean(baseline, family=family, seed=seed)
            for family in P1_FAMILIES
            for seed in Q3_SEEDS
        )
        for baseline in Q3_BASELINES
    }
    latency = {}
    for method in Q3_METHODS:
        values = [float(row["latency_ms"]) for row in rows if row["method"] == method]
        latency[method] = {
            "mean_ms": statistics.mean(values),
            "p95_ms": _percentile(values, 0.95),
        }
    summary: dict[str, object] = {
        "engineering_pass": engineering,
        "rows_per_method": {
            method: sum(row["method"] == method for row in rows)
            for method in Q3_METHODS
        },
        "overall": overall,
        "splits": splits,
        "families": families,
        "seed_means": seed_means,
        "paired_family_seed_wins": wins,
        "bootstrap_improvement": {
            baseline: _clustered_bootstrap_improvement(
                rows, baseline, bootstrap_samples
            )
            for baseline in Q3_BASELINES
        },
        "maximum_orthogonality_error": max(
            float(row["orthogonality_error"]) for row in rows
        ),
        "mean_residual_rms": {
            method: mean(method, key="residual_rms") for method in Q3_METHODS
        },
        "latency": latency,
        "bootstrap_samples": bootstrap_samples,
    }
    return summary


def _atomic_json(payload: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def _write_rows(rows: Sequence[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _baseline_config(
    method: str,
    family: str,
    output: Path,
    *,
    formal: bool,
    device: str,
    steps: int,
) -> ExperimentConfig:
    if method not in {"wang_xie_trace", "dai_galerkin"}:
        raise ValueError("unsupported Q3 adapted baseline")
    bounds = TRAINING_BOUNDS[family]
    return ExperimentConfig(
        name=f"q3_{family}_{method}_{'formal' if formal else 'smoke'}",
        method=method,
        device=device,
        seeds=Q3_SEEDS if formal else (42,),
        steps=steps if formal else 5,
        points=256 if formal else 64,
        parameter_batch=4 if formal else 1,
        width=64,
        hidden_layers=3,
        learning_rate=1e-3,
        anchor_kind="none",
        anchor_scale=0.0,
        residual_weight=0.0,
        eval_grid_side=33,
        reference_cutoff=24,
        checkpoint_every=max(1, (steps if formal else 5) // 3),
        resume=True,
        output_dir=str(output / "training" / method / family),
        potential_family=family,
        parameter_lower=tuple(low for low, _ in bounds),
        parameter_upper=tuple(high for _, high in bounds),
        dtype="float32",
        subspace_rank=6,
        sampling_stream="cpu_generator_v2",
    )


def _load_references(
    suite_path: Path, cache_path: Path
) -> tuple[
    dict[str, object], list[dict[str, object]], dict[str, dict[str, object]], str, str
]:
    suite, suite_hash = load_frozen_suite(suite_path)
    if suite.get("suite_id") != "block-kyfan-q3-supplement-v1-20260824":
        raise ValueError("unexpected Q3 supplement suite")
    points = suite["points"]
    cache_hash = file_sha256(cache_path)
    sidecar = cache_path.with_suffix(".sha256")
    tokens = sidecar.read_text().split() if sidecar.is_file() else []
    if not tokens or tokens[0] != cache_hash:
        raise ValueError("Q3 reference cache SHA-256 mismatch")
    payload = torch.load(cache_path, map_location="cpu", weights_only=False)
    metadata = payload.get("metadata")
    references = payload.get("references")
    if not isinstance(metadata, dict) or not isinstance(references, dict):
        raise TypeError("Q3 reference cache is malformed")
    expected = {
        "suite_id": suite["suite_id"],
        "suite_sha256": suite_hash,
        "cutoff": 24,
        "grid_side": 33,
        "rank": 3,
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValueError(f"Q3 reference metadata mismatch for {key}")
    point_ids = {str(point["id"]) for point in points}
    if set(references) != point_ids:
        raise ValueError("Q3 reference cache identity set is incomplete")
    return suite, points, references, suite_hash, cache_hash


def _synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elif device.type == "mps":
        torch.mps.synchronize()


def _evaluate_method(
    method: str,
    model: torch.nn.Module,
    point: dict[str, object],
    reference: dict[str, object],
    device: torch.device,
) -> dict[str, object]:
    from block_kyfan_pinn.reference import uniform_grid

    coordinates = uniform_grid(33).unsqueeze(0).to(device).requires_grad_()
    parameters = torch.tensor([point["parameters"]], device=device, dtype=torch.float32)
    _synchronize(device)
    started = time.perf_counter()
    if method == "p2_full_shell":
        neural = periodic_mgs(model(coordinates, parameters))
        basis, details = neural_augmented_ritz_fast(
            neural,
            coordinates,
            parameters,
            str(point["family"]),
            hex_shell_modes(2),
        )
        trial_rank = int(details["trial_rank"])
    elif method == "wang_xie_trace_adapted":
        basis = periodic_mgs(model(coordinates, parameters))
        trial_rank = 2
    elif method == "dai_galerkin_adapted":
        raw = model(coordinates, parameters)
        basis = galerkin_rank_basis(
            raw,
            coordinates,
            parameters,
            str(point["family"]),
            target_rank=2,
        )
        trial_rank = int(raw.shape[2])
    else:
        raise ValueError(f"unknown Q3 method: {method}")
    _synchronize(device)
    latency_ms = (time.perf_counter() - started) * 1000.0
    h_basis = apply_hamiltonian(basis, coordinates, parameters, str(point["family"]))
    reference_basis = reference.get("basis")
    if not isinstance(reference_basis, torch.Tensor):
        raise TypeError("Q3 reference basis is missing")
    reference_basis = (
        reference_basis[..., :2, :].unsqueeze(0).to(device=device, dtype=basis.dtype)
    )
    return {
        "method": method,
        "seed": int(point["_seed"]),
        "point_id": str(point["id"]),
        "family": str(point["family"]),
        "split": str(point["split"]),
        "projector_error": projector_sine_error(basis, reference_basis),
        "orthogonality_error": orthogonality_error(basis),
        "residual_rms": float(projected_residual_rms(basis, h_basis).detach().cpu()),
        "latency_ms": latency_ms,
        "trial_rank": trial_rank,
    }


def _environment(root: Path, requested_device: str) -> dict[str, object]:
    device = select_device(requested_device)
    commit_file = root / "SOURCE_GIT_COMMIT.txt"
    if commit_file.is_file():
        commit = commit_file.read_text().strip()
        branch = "archive-deployment"
    else:
        commit = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=root,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        branch = subprocess.run(
            ("git", "branch", "--show-current"),
            cwd=root,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
    return {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_commit": commit,
        "branch": branch,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "device": str(device),
        "accelerator_name": torch.cuda.get_device_name(0)
        if device.type == "cuda"
        else str(device),
        "accelerator_total_memory_bytes": int(
            torch.cuda.get_device_properties(0).total_memory
        )
        if device.type == "cuda"
        else None,
    }


def _read_member(
    archive: tarfile.TarFile, members: dict[str, tarfile.TarInfo], name: str
) -> bytes:
    member = members.get(name)
    if member is None or not member.isfile():
        raise ValueError(f"missing evidence member: {name}")
    handle = archive.extractfile(member)
    if handle is None:
        raise ValueError(f"unreadable evidence member: {name}")
    return handle.read()


def audit_q3_evidence(archive_path: Path, sidecar_path: Path) -> dict[str, object]:
    errors: list[str] = []
    actual = file_sha256(archive_path)
    tokens = sidecar_path.read_text().split() if sidecar_path.is_file() else []
    if not tokens or tokens[0] != actual:
        errors.append("outer sidecar mismatch")
    manifest_count = 0
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members_list = archive.getmembers()
            names = [member.name for member in members_list]
            if len(names) != len(set(names)):
                errors.append("duplicate archive members")
            if any(
                PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
                for name in names
            ):
                errors.append("unsafe archive member")
            members = {member.name: member for member in members_list}
            manifest_name = "results/q3-supplement-evidence-manifest.json"
            manifest = json.loads(_read_member(archive, members, manifest_name))
            files = manifest.get("files")
            if not isinstance(files, list):
                raise TypeError("invalid Q3 evidence manifest")
            manifest_count = len(files)
            for row in files:
                payload = _read_member(archive, members, str(row["path"]))
                if len(payload) != int(row["bytes"]):
                    errors.append(f"size mismatch {row['path']}")
                if hashlib.sha256(payload).hexdigest() != row["sha256"]:
                    errors.append(f"hash mismatch {row['path']}")
            required = {
                "results/q3_supplement_formal/rows.csv",
                "results/q3_supplement_formal/summary.json",
                "results/q3_supplement_formal/gate.json",
                "results/q3_supplement_formal/provenance.json",
                "benchmarks/q3_supplement_v1.json",
                "benchmarks/q3_supplement_v1.sha256",
                "data/q3_supplement_v1_references.pt",
                "data/q3_supplement_v1_references.sha256",
                "scripts/generate_q3_supplement.py",
                "scripts/run_q3_supplement.py",
            }
            declared = {str(row["path"]) for row in files}
            if not required.issubset(declared):
                errors.append("required Q3 evidence files are missing")
            rows_bytes = _read_member(
                archive, members, "results/q3_supplement_formal/rows.csv"
            ).decode()
            rows = list(csv.DictReader(rows_bytes.splitlines()))
            suite = json.loads(
                _read_member(archive, members, "benchmarks/q3_supplement_v1.json")
            )
            stored_summary = json.loads(
                _read_member(
                    archive, members, "results/q3_supplement_formal/summary.json"
                )
            )
            stored_gate = json.loads(
                _read_member(archive, members, "results/q3_supplement_formal/gate.json")
            )
            recomputed = aggregate_q3_rows(
                rows,
                suite["points"],
                bootstrap_samples=int(stored_summary["bootstrap_samples"]),
            )
            recomputed_gate = build_q3_gate(recomputed)
            if recomputed_gate != stored_gate:
                errors.append("Q3 gate recomputation mismatch")
            for method in Q3_METHODS:
                if not math.isclose(
                    float(recomputed["overall"][method]),
                    float(stored_summary["overall"][method]),
                    rel_tol=0.0,
                    abs_tol=1e-12,
                ):
                    errors.append(f"Q3 overall recomputation mismatch for {method}")
    except (OSError, tarfile.TarError, KeyError, TypeError, ValueError) as error:
        errors.append(str(error))
    return {
        "audit_pass": not errors,
        "archive_sha256": actual,
        "manifest_file_count": manifest_count,
        "errors": errors,
    }


def _run_training(
    output: Path, *, formal: bool, device: str, baseline_steps: int
) -> tuple[dict[str, ExperimentConfig], dict[str, object]]:
    configs: dict[str, ExperimentConfig] = {}
    summaries: dict[str, object] = {}
    for family in P1_FAMILIES:
        for raw_method, label in (
            ("wang_xie_trace", "wang_xie_trace_adapted"),
            ("dai_galerkin", "dai_galerkin_adapted"),
        ):
            config = _baseline_config(
                raw_method,
                family,
                output,
                formal=formal,
                device=device,
                steps=baseline_steps,
            )
            key = f"{label}:{family}"
            configs[key] = config
            summaries[key] = run_experiment(config)
            _atomic_json(asdict(config), output / "configs" / f"{label}_{family}.json")
    return configs, summaries


def _select_points(
    points: Sequence[dict[str, object]], *, formal: bool
) -> list[dict[str, object]]:
    if formal:
        return list(points)
    selected: list[dict[str, object]] = []
    for family in P1_FAMILIES:
        selected.extend([point for point in points if point["family"] == family][:2])
    return selected


def _run_evaluation(
    root: Path,
    output: Path,
    points: Sequence[dict[str, object]],
    references: dict[str, dict[str, object]],
    configs: dict[str, ExperimentConfig],
    *,
    formal: bool,
    device_name: str,
    p5_archive: Path,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    device = select_device(device_name)
    p5_sidecar = p5_archive.with_suffix(p5_archive.suffix + ".sha256")
    inventory = inventory_p1_checkpoints(p5_archive, p5_sidecar)
    inventory_map = {
        (str(row["method"]), str(row["family"]), int(row["seed"])): row
        for row in inventory
    }
    seeds = Q3_SEEDS if formal else (42,)
    rows: list[dict[str, object]] = []
    parameter_counts: dict[str, dict[str, int]] = {method: {} for method in Q3_METHODS}
    for family in P1_FAMILIES:
        family_points = [point for point in points if point["family"] == family]
        for seed in seeds:
            p2_model = load_p5_checkpoint(
                p5_archive,
                inventory_map[("p5_long_anchor", family, seed)],
                device,
            )
            parameter_counts["p2_full_shell"][family] = sum(
                parameter.numel() for parameter in p2_model.parameters()
            )
            baseline_models: dict[str, torch.nn.Module] = {}
            for label in Q3_BASELINES:
                config = configs[f"{label}:{family}"]
                checkpoint = Path(config.output_dir) / f"seed_{seed}" / "final.pt"
                model, _ = _load_model(config, checkpoint, device)
                baseline_models[label] = model
                parameter_counts[label][family] = sum(
                    parameter.numel() for parameter in model.parameters()
                )
            method_models = {"p2_full_shell": p2_model, **baseline_models}
            for method, model in method_models.items():
                for original in family_points:
                    point = {**original, "_seed": seed}
                    rows.append(
                        _evaluate_method(
                            method,
                            model,
                            point,
                            references[str(point["id"])],
                            device,
                        )
                    )
            print(f"Q3_UNIT_COMPLETE={family}:seed{seed}", flush=True)
    return rows, parameter_counts


def _write_report(output: Path, status: str, summary: dict[str, object]) -> None:
    overall = summary["overall"]
    bootstrap = summary["bootstrap_improvement"]
    (output / "report.md").write_text(
        "# SCI-Q3 independent supplement\n\n"
        f"- Status: `{status}`\n"
        f"- P2 overall: `{overall['p2_full_shell']:.6f}`\n"
        f"- Wang-Xie adapted overall: `{overall['wang_xie_trace_adapted']:.6f}`\n"
        f"- Dai adapted overall: `{overall['dai_galerkin_adapted']:.6f}`\n"
        f"- P2 vs Wang-Xie improvement CI: `[{bootstrap['wang_xie_trace_adapted']['low']:.4f}, "
        f"{bootstrap['wang_xie_trace_adapted']['high']:.4f}]`\n"
        f"- P2 vs Dai improvement CI: `[{bootstrap['dai_galerkin_adapted']['low']:.4f}, "
        f"{bootstrap['dai_galerkin_adapted']['high']:.4f}]`\n"
    )


def run(args: argparse.Namespace) -> tuple[str, int]:
    root = Path(__file__).resolve().parents[1]
    formal = bool(args.formal)
    output = root / (
        "results/q3_supplement_formal" if formal else "results/q3_supplement_smoke"
    )
    output.mkdir(parents=True, exist_ok=True)
    suite_path = root / args.suite
    cache_path = root / args.reference_cache
    _, all_points, references, suite_hash, cache_hash = _load_references(
        suite_path, cache_path
    )
    points = _select_points(all_points, formal=formal)
    if formal:
        smoke_gate_path = root / "results/q3_supplement_smoke/gate.json"
        if (
            not smoke_gate_path.is_file()
            or json.loads(smoke_gate_path.read_text()).get("engineering_pass")
            is not True
        ):
            raise RuntimeError("formal Q3 supplement requires a passing smoke gate")
    configs, training = _run_training(
        output,
        formal=formal,
        device=args.device,
        baseline_steps=args.baseline_steps,
    )
    p5_archive = root / args.p5_archive
    rows, parameter_counts = _run_evaluation(
        root,
        output,
        points,
        references,
        configs,
        formal=formal,
        device_name=args.device,
        p5_archive=p5_archive,
    )
    _write_rows(rows, output / "rows.csv")
    environment = _environment(root, args.device)
    if not formal:
        finite = all(
            math.isfinite(float(row[key]))
            for row in rows
            for key in (
                "projector_error",
                "orthogonality_error",
                "residual_rms",
                "latency_ms",
            )
        )
        gate = {
            "row_count": len(rows),
            "expected_row_count": len(Q3_METHODS) * 4,
            "finite_metrics": finite,
            "orthogonality_pass": max(float(row["orthogonality_error"]) for row in rows)
            < 1e-3,
        }
        gate["engineering_pass"] = (
            gate["row_count"] == gate["expected_row_count"]
            and gate["finite_metrics"]
            and gate["orthogonality_pass"]
        )
        _atomic_json(gate, output / "gate.json")
        _atomic_json(
            {"training": training, "environment": environment}, output / "summary.json"
        )
        status = (
            "Q3_SUPPLEMENT_SMOKE_PASS"
            if gate["engineering_pass"]
            else "Q3_SUPPLEMENT_SMOKE_FAIL"
        )
        print(f"Q3_SUPPLEMENT_STATUS={status}")
        return status, 0 if gate["engineering_pass"] else 2

    summary = aggregate_q3_rows(
        rows, all_points, bootstrap_samples=args.bootstrap_samples
    )
    training_cost = {
        key: {
            "elapsed_seconds": sum(
                float(run["elapsed_seconds"]) for run in value["runs"]
            ),
            "peak_memory_bytes": max(
                (
                    int(run["peak_memory_bytes"])
                    for run in value["runs"]
                    if run["peak_memory_bytes"] is not None
                ),
                default=None,
            ),
            "steps": int(value["config"]["steps"]),
        }
        for key, value in training.items()
    }
    summary["parameter_counts"] = parameter_counts
    summary["training_cost"] = training_cost
    gate = build_q3_gate(summary)
    provenance = {
        "suite_sha256": suite_hash,
        "reference_sha256": cache_hash,
        "p5_evidence_sha256": file_sha256(p5_archive),
        "source_fingerprint": _source_fingerprint(),
        "runner_sha256": file_sha256(Path(__file__)),
        "generator_sha256": file_sha256(root / "scripts/generate_q3_supplement.py"),
        "environment": environment,
    }
    _atomic_json(summary, output / "summary.json")
    _atomic_json(gate, output / "gate.json")
    _atomic_json(provenance, output / "provenance.json")
    status = "Q3_SUPPLEMENT_GO" if gate["q3_supplement_go"] else "Q3_SUPPLEMENT_STOP"
    _write_report(output, status, summary)
    archive, sidecar, manifest = write_evidence_bundle(
        root=root,
        include_paths=(
            output,
            suite_path,
            suite_path.with_suffix(".sha256"),
            cache_path,
            cache_path.with_suffix(".sha256"),
            p5_archive,
            p5_archive.with_suffix(p5_archive.suffix + ".sha256"),
            root / "scripts/generate_q3_supplement.py",
            root / "scripts/run_q3_supplement.py",
            root / "tests/test_q3_supplement_protocol.py",
            root / "docs/Q3-SUPPLEMENT-PROTOCOL.zh-CN.md",
            root / "requirements.txt",
            root / "SOURCE_GIT_COMMIT.txt",
        ),
        output_dir=root / "artifacts",
        label=time.strftime("%Y%m%d-%H%M%S", time.gmtime()),
        prefix="q3-supplement-evidence",
        manifest_name="q3-supplement-evidence-manifest.json",
    )
    audit = audit_q3_evidence(archive, sidecar)
    _atomic_json(audit, output / "evidence-audit.json")
    if audit["audit_pass"] is not True:
        raise RuntimeError(f"Q3 evidence audit failed: {audit['errors']}")
    print(f"Q3_SUPPLEMENT_EVIDENCE={archive}")
    print(f"Q3_SUPPLEMENT_EVIDENCE_SHA256={sidecar}")
    print(f"Q3_SUPPLEMENT_MANIFEST={manifest}")
    print(f"Q3_SUPPLEMENT_STATUS={status}")
    return status, 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke-only", action="store_true")
    mode.add_argument("--formal", action="store_true")
    mode.add_argument("--audit-evidence", type=Path)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--suite", default="benchmarks/q3_supplement_v1.json")
    parser.add_argument(
        "--reference-cache", default="data/q3_supplement_v1_references.pt"
    )
    parser.add_argument("--p5-archive", default=f"artifacts/{P5_ARCHIVE_NAME}")
    parser.add_argument("--baseline-steps", type=int, default=1500)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    args = parser.parse_args()
    if args.audit_evidence is not None:
        archive = args.audit_evidence
        sidecar = archive.with_suffix(archive.suffix + ".sha256")
        report = audit_q3_evidence(archive, sidecar)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["audit_pass"] else 2
    _, code = run(args)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run the frozen V2 validation pilot: 2 families × 4 methods × 3 seeds."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.device import select_device, synchronize
from block_kyfan_pinn.experiment import (
    _capture_rng_state,
    _restore_rng_state,
    _sample_coordinates,
    _sample_parameters,
    _source_fingerprint,
)
from block_kyfan_pinn.metrics import (
    orthogonality_error,
    principal_angle_degrees,
    projector_sine_error,
)
from block_kyfan_pinn.model import BlockKyFanPINN, GeneralizedTracePINN, OrderedEigenPINN
from block_kyfan_pinn.p3_model import P3BlockKyFanPINN
from block_kyfan_pinn.physics import (
    apply_hamiltonian,
    generalized_trace_energy,
    ky_fan_energy,
    ordered_residual_loss,
    periodic_mgs,
    projected_residual_rms,
    ritz_matrix,
)
from block_kyfan_pinn.reference import uniform_grid
from block_kyfan_pinn.suites import file_sha256, load_frozen_suite


PILOT_METHODS = ("p1_block", "ordered_residual", "wang_xie_trace", "p3")
PILOT_FAMILIES = ("harmonic_honeycomb", "gaussian_honeycomb")
FAMILY_BOUNDS: dict[str, tuple[tuple[float, ...], tuple[float, ...]]] = {
    "harmonic_honeycomb": (
        (0.28, 0.28, 0.20, -0.08),
        (0.38, 0.38, 0.80, 0.08),
    ),
    "gaussian_honeycomb": (
        (0.28, 0.28, 1.00, 0.18, -0.08),
        (0.38, 0.38, 4.00, 0.35, 0.08),
    ),
}


@dataclass(frozen=True)
class PilotConfig:
    method: str
    potential_family: str
    seed: int
    device: str = "auto"
    steps: int = 500
    points: int = 256
    parameter_batch: int = 4
    width: int = 64
    hidden_layers: int = 3
    learning_rate: float = 1e-3
    eval_grid_side: int = 33
    reference_cutoff: int = 24
    checkpoint_every: int = 100


def build_pilot_model(
    method: str,
    *,
    potential_family: str,
    width: int,
    hidden_layers: int,
    device: torch.device,
    dtype: torch.dtype,
) -> nn.Module:
    """Build one of four intentionally distinct pilot methods."""

    lower, upper = FAMILY_BOUNDS[potential_family]
    parameter_dim = len(lower)
    if method == "p1_block":
        model: nn.Module = BlockKyFanPINN(
            width=width,
            hidden_layers=hidden_layers,
            anchor_kind="correct",
            anchor_scale=0.1,
            parameter_dim=parameter_dim,
            orthogonalization="dual_path",
        )
    elif method == "ordered_residual":
        model = OrderedEigenPINN(
            width=width, hidden_layers=hidden_layers, parameter_dim=parameter_dim
        )
    elif method == "wang_xie_trace":
        model = GeneralizedTracePINN(
            width=width, hidden_layers=hidden_layers, parameter_dim=parameter_dim
        )
    elif method == "p3":
        model = P3BlockKyFanPINN(
            width=width,
            hidden_layers=hidden_layers,
            anchor_scale=0.1,
            anchor_kind="correct",
            parameter_dim=parameter_dim,
            orthogonalization="dual_path",
            num_rom_shells=1,
            rom_hidden_width=32,
            rom_hidden_layers=2,
            num_charts=2,
            chart_temperature=0.25,
            m_weighted=True,
            gap_monitor=True,
            fallback_enabled=False,
            reference_cutoff=24,
            potential_family=potential_family,
            parameter_lower=lower,
            parameter_upper=upper,
        )
    else:
        raise ValueError(f"unknown pilot method: {method}")
    return model.to(device=device, dtype=dtype)


def _config_fingerprint(config: PilotConfig, suite_hash: str, cache_hash: str) -> str:
    body = json.dumps(
        {"config": asdict(config), "suite_sha256": suite_hash, "cache_sha256": cache_hash},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode()).hexdigest()


def _load_completed_result(
    result_path: Path,
    final_path: Path,
    *,
    config_fingerprint: str,
    source_fingerprint: str,
    suite_hash: str,
    cache_hash: str,
) -> dict[str, object] | None:
    """Return a completed run only when every provenance binding still matches."""

    if not result_path.is_file() and not final_path.is_file():
        return None
    if not result_path.is_file() or not final_path.is_file():
        raise ValueError("pilot run is incomplete: result.json and final.pt must coexist")
    result = json.loads(result_path.read_text())
    expected = {
        "config_fingerprint": config_fingerprint,
        "source_fingerprint": source_fingerprint,
        "suite_sha256": suite_hash,
        "reference_cache_sha256": cache_hash,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise ValueError(f"completed pilot provenance mismatch for {key}")
    checkpoint_hash = file_sha256(final_path)
    if result.get("final_checkpoint_sha256") != checkpoint_hash:
        raise ValueError("completed pilot checkpoint SHA-256 mismatch")
    return result


def _load_reference_cache(
    path: Path,
    *,
    suite_id: str,
    suite_hash: str,
    point_ids: set[str],
    grid_side: int,
    cutoff: int,
) -> tuple[dict[str, dict[str, object]], str]:
    if not path.is_file():
        raise FileNotFoundError(
            f"reference cache is missing: {path}; run scripts/generate_v2_assets.py first"
        )
    cache_hash = file_sha256(path)
    sidecar = path.with_suffix(".sha256")
    if not sidecar.is_file() or sidecar.read_text().strip().split()[0] != cache_hash:
        raise ValueError("reference cache SHA-256 sidecar is missing or invalid")
    payload = torch.load(path, map_location="cpu", weights_only=False)
    metadata = payload.get("metadata", {})
    expected = {
        "suite_id": suite_id,
        "suite_sha256": suite_hash,
        "grid_side": grid_side,
        "cutoff": cutoff,
        "mode_shape": "hexagonal",
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValueError(
                f"reference cache metadata mismatch for {key}: expected {value!r}, "
                f"got {metadata.get(key)!r}"
            )
    references = payload.get("references")
    if not isinstance(references, dict) or not point_ids.issubset(references):
        raise ValueError("reference cache does not cover every selected suite point")
    return references, cache_hash


def _training_loss(
    method: str,
    output: object,
    coordinates: torch.Tensor,
    parameters: torch.Tensor,
    potential_family: str,
) -> torch.Tensor:
    if method == "ordered_residual":
        basis, eigenvalues = output
        return ordered_residual_loss(
            basis, coordinates, parameters, eigenvalues, potential_family
        ) + 1e-3 * eigenvalues.mean()
    if method == "wang_xie_trace":
        return generalized_trace_energy(output, coordinates, parameters, potential_family)
    return ky_fan_energy(output, coordinates, parameters, potential_family)


def _evaluation_basis(method: str, output: object) -> torch.Tensor:
    if method == "ordered_residual":
        return output[0]
    if method == "wang_xie_trace":
        return periodic_mgs(output)
    return output


def _evaluate_suite(
    model: nn.Module,
    config: PilotConfig,
    device: torch.device,
    points: list[dict[str, object]],
    references: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    grid = uniform_grid(config.eval_grid_side).unsqueeze(0)
    rows: list[dict[str, object]] = []
    for point in points:
        coordinates = grid.to(device).requires_grad_()
        parameters = torch.tensor([point["parameters"]], device=device)
        output = model(coordinates, parameters)
        basis = _evaluation_basis(config.method, output)
        reference_basis = references[str(point["id"])]["basis"]
        reference_basis = reference_basis.unsqueeze(0).to(
            device=device, dtype=basis.dtype
        )
        h_basis = apply_hamiltonian(
            basis, coordinates, parameters, config.potential_family
        )
        matrix_real, matrix_imag = ritz_matrix(basis, h_basis)
        if device.type == "mps":
            matrix_real = matrix_real.cpu()
            matrix_imag = matrix_imag.cpu()
        ritz_values = torch.linalg.eigvalsh(
            torch.complex(matrix_real, matrix_imag)[0].detach()
        ).real.cpu()
        reference_values = references[str(point["id"])]["eigenvalues"]
        if not isinstance(reference_values, torch.Tensor) or reference_values.numel() < 3:
            raise ValueError(f"reference eigenvalues are missing for {point['id']}")
        angle_mean, angle_max = principal_angle_degrees(basis, reference_basis)
        row: dict[str, object] = {
            "id": point["id"],
            "family": point["family"],
            "split": point["split"],
            "projector_sine_error": projector_sine_error(basis, reference_basis),
            "principal_angle_mean_deg": angle_mean,
            "principal_angle_max_deg": angle_max,
            "ritz_eigenvalue_abs_max": float(
                (ritz_values - reference_values[:2]).abs().max()
            ),
            "trace_abs_error": float(
                (ritz_values.sum() - reference_values[:2].sum()).abs()
            ),
            "residual_rms": float(projected_residual_rms(basis, h_basis).detach().cpu()),
            "orthogonality_error": orthogonality_error(basis),
            "internal_gap": float(reference_values[1] - reference_values[0]),
            "external_gap": float(reference_values[2] - reference_values[1]),
        }
        if config.method == "p3":
            risks = model.evaluate_risks(coordinates, parameters, basis)
            row["chart_disagreement"] = float(
                risks["chart_disagreement"][0].detach().cpu()
            )
            row["residual_risk"] = float(risks["residual_risk"][0].detach().cpu())
        rows.append(row)
    return rows


def run_pilot_run(
    config: PilotConfig,
    output_dir: Path,
    *,
    suite_payload: dict[str, object],
    suite_hash: str,
    references: dict[str, dict[str, object]],
    cache_hash: str,
) -> dict[str, object]:
    """Train, resume, evaluate, and persist one immutable pilot run."""

    if config.steps < 1:
        raise ValueError("steps must be positive")
    torch.manual_seed(config.seed)
    device = select_device(config.device)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    dtype = torch.float32
    model = build_pilot_model(
        config.method,
        potential_family=config.potential_family,
        width=config.width,
        hidden_layers=config.hidden_layers,
        device=device,
        dtype=dtype,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    lower, upper = FAMILY_BOUNDS[config.potential_family]
    sample_generator = torch.Generator(device="cpu")
    sample_generator.manual_seed(config.seed + 1_000_003)

    output_dir.mkdir(parents=True, exist_ok=True)
    latest_path = output_dir / "latest.pt"
    final_path = output_dir / "final.pt"
    result_path = output_dir / "result.json"
    fingerprint = _config_fingerprint(config, suite_hash, cache_hash)
    source_fingerprint = _source_fingerprint()
    start_step = 0
    elapsed_before = 0.0
    training_rows: list[dict[str, object]] = []
    completed = _load_completed_result(
        result_path,
        final_path,
        config_fingerprint=fingerprint,
        source_fingerprint=source_fingerprint,
        suite_hash=suite_hash,
        cache_hash=cache_hash,
    )
    if completed is not None:
        return completed
    if latest_path.is_file():
        state = torch.load(latest_path, map_location=device, weights_only=False)
        if state.get("config_fingerprint") != fingerprint:
            raise ValueError("pilot resume configuration fingerprint mismatch")
        if state.get("source_fingerprint") != source_fingerprint:
            raise ValueError("pilot resume source fingerprint mismatch")
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        _restore_rng_state(state["rng_state"], device)
        sample_generator.set_state(state["sample_rng_state"])
        start_step = int(state["step"])
        elapsed_before = float(state.get("elapsed_seconds", 0.0))
        training_rows = list(state.get("training_rows", []))

    start = time.perf_counter()
    for step in range(start_step, config.steps):
        coordinates = _sample_coordinates(
            config.parameter_batch, config.points, device, dtype, sample_generator
        )
        parameters = _sample_parameters(
            config.parameter_batch, device, lower, upper, dtype, sample_generator
        )
        optimizer.zero_grad(set_to_none=True)
        output = model(coordinates, parameters)
        loss = _training_loss(
            config.method, output, coordinates, parameters, config.potential_family
        )
        if not bool(torch.isfinite(loss).detach().cpu()):
            raise FloatingPointError(f"non-finite loss at step {step}")
        loss.backward()
        optimizer.step()
        if step == start_step or (step + 1) % 50 == 0 or step + 1 == config.steps:
            training_rows.append({"step": step + 1, "loss": float(loss.detach().cpu())})
        if config.checkpoint_every > 0 and (step + 1) % config.checkpoint_every == 0:
            torch.save(
                {
                    "model": model.state_dict(),
                    "optimizer": optimizer.state_dict(),
                    "step": step + 1,
                    "config": asdict(config),
                    "config_fingerprint": fingerprint,
                    "source_fingerprint": source_fingerprint,
                    "suite_sha256": suite_hash,
                    "reference_cache_sha256": cache_hash,
                    "rng_state": _capture_rng_state(device),
                    "sample_rng_state": sample_generator.get_state(),
                    "elapsed_seconds": elapsed_before + time.perf_counter() - start,
                    "training_rows": training_rows,
                },
                latest_path,
            )
    synchronize(device)
    elapsed = elapsed_before + time.perf_counter() - start

    family_points = [
        point
        for point in suite_payload["points"]
        if point["family"] == config.potential_family
    ]
    evaluation = _evaluate_suite(model, config, device, family_points, references)
    projector_values = [float(row["projector_sine_error"]) for row in evaluation]
    residual_values = [float(row["residual_rms"]) for row in evaluation]
    orthogonality_values = [float(row["orthogonality_error"]) for row in evaluation]
    final_state = {
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "step": config.steps,
        "config": asdict(config),
        "config_fingerprint": fingerprint,
        "source_fingerprint": source_fingerprint,
        "suite_sha256": suite_hash,
        "reference_cache_sha256": cache_hash,
        "rng_state": _capture_rng_state(device),
        "sample_rng_state": sample_generator.get_state(),
        "elapsed_seconds": elapsed,
        "training_rows": training_rows,
    }
    torch.save(final_state, final_path)
    torch.save(final_state, latest_path)
    with (output_dir / "metrics.csv").open("w", newline="") as handle:
        fieldnames = sorted({key for row in evaluation for key in row})
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(evaluation)
    with (output_dir / "training.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("step", "loss"))
        writer.writeheader()
        writer.writerows(training_rows)
    result: dict[str, object] = {
        "status": "PASS",
        "config": asdict(config),
        "config_fingerprint": fingerprint,
        "source_fingerprint": source_fingerprint,
        "suite_id": suite_payload["suite_id"],
        "suite_sha256": suite_hash,
        "reference_cache_sha256": cache_hash,
        "device": str(device),
        "num_parameters": sum(parameter.numel() for parameter in model.parameters()),
        "initial_loss": float(training_rows[0]["loss"]),
        "final_loss": float(training_rows[-1]["loss"]),
        "elapsed_seconds": elapsed,
        "peak_memory_bytes": (
            int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else None
        ),
        "mean_projector_sine_error": statistics.mean(projector_values),
        "split_projector_mean": {
            split: statistics.mean(
                float(row["projector_sine_error"])
                for row in evaluation
                if row["split"] == split
            )
            for split in sorted({str(row["split"]) for row in evaluation})
        },
        "std_projector_sine_error": (
            statistics.stdev(projector_values) if len(projector_values) > 1 else 0.0
        ),
        "mean_residual_rms": statistics.mean(residual_values),
        "maximum_orthogonality_error": max(orthogonality_values),
        "final_checkpoint_sha256": file_sha256(final_path),
        "point_count": len(evaluation),
    }
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def build_pilot_gate(summary: dict[str, object]) -> dict[str, object]:
    """Apply the frozen promotion rule; accuracy improvements are mandatory."""

    total = int(summary.get("total_runs", 0))
    completed = int(summary.get("completed_runs", 0))
    failed = int(summary.get("failed_runs", total))
    primary_split = "near_cluster"
    p3_error = float(
        summary.get(f"p3_{primary_split}_projector_mean", math.inf)
    )
    baseline_errors = [
        float(
            summary.get(f"{method}_{primary_split}_projector_mean", math.inf)
        )
        for method in PILOT_METHODS
        if method != "p3"
    ]
    best_baseline = min(baseline_errors)
    improvement = (
        100.0 * (best_baseline - p3_error) / best_baseline
        if math.isfinite(best_baseline) and best_baseline > 0
        else -math.inf
    )
    family_improvements: dict[str, float] = {}
    for family in PILOT_FAMILIES:
        family_p3 = float(
            summary.get(
                f"p3_{family}_{primary_split}_projector_mean", math.inf
            )
        )
        family_baselines = [
            float(
                summary.get(
                    f"{method}_{family}_{primary_split}_projector_mean",
                    math.inf,
                )
            )
            for method in PILOT_METHODS
            if method != "p3"
        ]
        family_best = min(family_baselines)
        family_improvements[family] = (
            100.0 * (family_best - family_p3) / family_best
            if math.isfinite(family_best) and family_best > 0
            else -math.inf
        )
    gate: dict[str, object] = {
        "primary_split": primary_split,
        "all_runs_completed": total == 24 and completed == total and failed == 0,
        "finite_metrics": math.isfinite(p3_error) and all(math.isfinite(v) for v in baseline_errors),
        "orthogonality_pass": float(
            summary.get("maximum_orthogonality_error", math.inf)
        ) < 1e-4,
        "best_baseline_projector_mean": best_baseline,
        "p3_vs_best_baseline_improvement_percent": improvement,
        "p3_better_than_best_baseline_15pct": improvement >= 15.0,
        "family_improvement_percent": family_improvements,
        "p3_better_than_best_baseline_15pct_each_family": all(
            value >= 15.0 for value in family_improvements.values()
        ),
    }
    gate["pilot_go"] = all(
        bool(gate[key])
        for key in (
            "all_runs_completed",
            "finite_metrics",
            "orthogonality_pass",
            "p3_better_than_best_baseline_15pct",
            "p3_better_than_best_baseline_15pct_each_family",
        )
    )
    return gate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="auto", choices=("auto", "cuda", "rocm"))
    parser.add_argument("--method", choices=(*PILOT_METHODS, "all"), default="all")
    parser.add_argument("--family", choices=(*PILOT_FAMILIES, "all"), default="all")
    parser.add_argument("--seed", type=int, nargs="+", default=[42, 137, 251])
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--suite", type=Path, default=Path("benchmarks/v2_validation.json"))
    parser.add_argument(
        "--reference-cache", type=Path, default=Path("data/v2_validation_references.pt")
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results/p3_v2_pilot"))
    args = parser.parse_args()

    suite_payload, suite_hash = load_frozen_suite(args.suite)
    if suite_payload.get("purpose") != "pilot_and_hyperparameter_selection":
        raise ValueError("pilot must use the validation suite, not the frozen final test suite")
    point_ids = {str(point["id"]) for point in suite_payload["points"]}
    references, cache_hash = _load_reference_cache(
        args.reference_cache,
        suite_id=str(suite_payload["suite_id"]),
        suite_hash=suite_hash,
        point_ids=point_ids,
        grid_side=33,
        cutoff=24,
    )
    methods = PILOT_METHODS if args.method == "all" else (args.method,)
    families = PILOT_FAMILIES if args.family == "all" else (args.family,)
    total = len(methods) * len(families) * len(args.seed)
    if args.method == "all" and args.family == "all" and len(args.seed) != 3:
        raise ValueError("the promotion pilot requires exactly three seeds")

    results: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for method in methods:
        for family in families:
            for seed in args.seed:
                run_id = f"{method}_{family}_seed{seed}"
                run_dir = args.output_dir / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                config = PilotConfig(
                    method=method,
                    potential_family=family,
                    seed=seed,
                    device=args.device,
                    steps=args.steps,
                )
                print(f"[{len(results) + len(failures) + 1}/{total}] {run_id}", flush=True)
                try:
                    result = run_pilot_run(
                        config,
                        run_dir,
                        suite_payload=suite_payload,
                        suite_hash=suite_hash,
                        references=references,
                        cache_hash=cache_hash,
                    )
                    results.append(result)
                except Exception as error:
                    failure = {
                        "status": "FAIL",
                        "run_id": run_id,
                        "error_type": type(error).__name__,
                        "reason": str(error),
                    }
                    (run_dir / "failure.json").write_text(
                        json.dumps(failure, ensure_ascii=False, indent=2) + "\n"
                    )
                    failures.append(failure)

    summary: dict[str, object] = {
        "scope": "v2_validation_promotion_pilot_not_final_test",
        "total_runs": total,
        "completed_runs": len(results),
        "failed_runs": len(failures),
        "suite_id": suite_payload["suite_id"],
        "suite_sha256": suite_hash,
        "reference_cache_sha256": cache_hash,
        "methods": list(methods),
        "families": list(families),
        "seeds": args.seed,
        "steps": args.steps,
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "hip": getattr(torch.version, "hip", None),
        },
        "maximum_orthogonality_error": max(
            (float(result["maximum_orthogonality_error"]) for result in results),
            default=math.inf,
        ),
        "failures": failures,
    }
    for method in methods:
        values = [
            float(result["mean_projector_sine_error"])
            for result in results
            if result["config"]["method"] == method
        ]
        summary[f"{method}_projector_mean"] = (
            statistics.mean(values) if values else math.inf
        )
        summary[f"{method}_projector_std"] = (
            statistics.stdev(values) if len(values) > 1 else 0.0
        )
        primary_values = [
            float(result["split_projector_mean"]["near_cluster"])
            for result in results
            if result["config"]["method"] == method
            and "near_cluster" in result["split_projector_mean"]
        ]
        summary[f"{method}_near_cluster_projector_mean"] = (
            statistics.mean(primary_values) if primary_values else math.inf
        )
        for family in families:
            family_values = [
                float(result["mean_projector_sine_error"])
                for result in results
                if result["config"]["method"] == method
                and result["config"]["potential_family"] == family
            ]
            summary[f"{method}_{family}_projector_mean"] = (
                statistics.mean(family_values) if family_values else math.inf
            )
            family_primary_values = [
                float(result["split_projector_mean"]["near_cluster"])
                for result in results
                if result["config"]["method"] == method
                and result["config"]["potential_family"] == family
                and "near_cluster" in result["split_projector_mean"]
            ]
            summary[f"{method}_{family}_near_cluster_projector_mean"] = (
                statistics.mean(family_primary_values)
                if family_primary_values
                else math.inf
            )
    gate = build_pilot_gate(summary)
    summary["gate"] = gate
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    (args.output_dir / "pilot_gate.json").write_text(
        json.dumps(gate, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(gate, ensure_ascii=False, indent=2))
    return 0 if bool(gate["pilot_go"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())

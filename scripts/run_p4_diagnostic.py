#!/usr/bin/env python3
"""Run the controlled P4 generalized-trace/ROM diagnostic matrix."""

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
import traceback
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
)
from block_kyfan_pinn.metrics import (
    orthogonality_error,
    principal_angle_degrees,
    projector_sine_error,
)
from block_kyfan_pinn.model import GeneralizedTracePINN
from block_kyfan_pinn.p3_model import P3BlockKyFanPINN
from block_kyfan_pinn.p4_model import (
    AnchoredGeneralizedTracePINN,
    ROMGeneralizedTracePINN,
    chart_statistics,
)
from block_kyfan_pinn.physics import (
    apply_hamiltonian,
    complex_gram_mean,
    generalized_trace_energy,
    ky_fan_energy,
    periodic_mgs,
    projected_residual_rms,
    ritz_matrix,
)
from block_kyfan_pinn.reference import uniform_grid
from block_kyfan_pinn.suites import file_sha256, load_frozen_suite
from scripts.run_p3_pilot import (
    FAMILY_BOUNDS,
    _config_fingerprint,
    _load_completed_result,
    _load_reference_cache,
)


P4_METHODS = (
    "g0_trace",
    "g1_anchor",
    "g2_static_rom",
    "g3_annealed_rom",
    "k3_p3",
)
P4_FAMILIES = ("harmonic_honeycomb", "gaussian_honeycomb")
P4_PROMOTION_SEEDS = (42, 137, 251)
P4_PROMOTION_STEPS = 500
P4_PROMOTION_POINTS = 256
P4_PROMOTION_PARAMETER_BATCH = 4
P4_PROMOTION_CHECKPOINT_EVERY = 100
P4_PROMOTION_MONITOR_EVERY = 50
RAW_TRACE_METHODS = frozenset(P4_METHODS[:4])


@dataclass(frozen=True)
class P4Config:
    method: str
    potential_family: str
    seed: int
    protocol: str = "smoke"
    device: str = "auto"
    steps: int = 5
    points: int = 64
    parameter_batch: int = 1
    width: int = 64
    hidden_layers: int = 3
    learning_rate: float = 1e-3
    eval_grid_side: int = 33
    reference_cutoff: int = 24
    checkpoint_every: int = 100
    monitor_every: int = 50


def _validate_method_family(method: str, potential_family: str) -> None:
    if method not in P4_METHODS:
        raise ValueError(f"unknown P4 method: {method}")
    if potential_family not in P4_FAMILIES:
        raise ValueError(f"unknown P4 potential family: {potential_family}")


def build_p4_model(
    method: str,
    *,
    potential_family: str,
    width: int,
    hidden_layers: int,
    device: torch.device,
    dtype: torch.dtype,
) -> nn.Module:
    """Build the frozen G0/G1/G2/G3/K3 factorial comparison."""

    _validate_method_family(method, potential_family)
    lower, upper = FAMILY_BOUNDS[potential_family]
    parameter_dim = len(lower)
    common = {
        "width": width,
        "hidden_layers": hidden_layers,
        "parameter_dim": parameter_dim,
    }
    if method == "g0_trace":
        model: nn.Module = GeneralizedTracePINN(**common)
    elif method == "g1_anchor":
        model = AnchoredGeneralizedTracePINN(
            **common, anchor_kind="correct", anchor_scale=0.1
        )
    elif method in {"g2_static_rom", "g3_annealed_rom"}:
        model = ROMGeneralizedTracePINN(
            **common,
            anchor_kind="correct",
            anchor_scale=0.1,
            num_rom_shells=1,
            rom_hidden_width=32,
            rom_hidden_layers=2,
            num_charts=1,
            chart_temperature=0.25,
            rom_schedule=(
                "cosine_decay" if method == "g3_annealed_rom" else "constant"
            ),
            potential_family=potential_family,
            parameter_lower=lower,
            parameter_upper=upper,
        )
    else:
        model = P3BlockKyFanPINN(
            **common,
            anchor_kind="correct",
            anchor_scale=0.1,
            orthogonalization="dual_path",
            num_rom_shells=1,
            rom_hidden_width=32,
            rom_hidden_layers=2,
            num_charts=2,
            chart_temperature=0.25,
            m_weighted=True,
            gap_monitor=False,
            fallback_enabled=False,
            reference_cutoff=24,
            potential_family=potential_family,
            parameter_lower=lower,
            parameter_upper=upper,
        )
    return model.to(device=device, dtype=dtype)


def _p4_source_fingerprint() -> str:
    """Bind checkpoints to both the library and this exact runner."""

    root = Path(__file__).resolve().parents[1]
    files = sorted((root / "block_kyfan_pinn").rglob("*.py")) + [Path(__file__).resolve()]
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _training_loss(
    method: str,
    output: torch.Tensor,
    coordinates: torch.Tensor,
    parameters: torch.Tensor,
    potential_family: str,
) -> tuple[torch.Tensor, dict[str, float]]:
    if method in RAW_TRACE_METHODS:
        energy = generalized_trace_energy(
            output, coordinates, parameters, potential_family
        )
        return energy, {
            "energy_loss": float(energy.detach().cpu()),
        }
    energy = ky_fan_energy(output, coordinates, parameters, potential_family)
    return energy, {
        "energy_loss": float(energy.detach().cpu()),
    }


def _evaluation_basis(method: str, output: torch.Tensor) -> torch.Tensor:
    return periodic_mgs(output) if method in RAW_TRACE_METHODS else output


def _gradient_norm(model: nn.Module) -> float:
    squared = sum(
        float(parameter.grad.detach().square().sum().cpu())
        for parameter in model.parameters()
        if parameter.grad is not None
    )
    return math.sqrt(squared)


def _gram_condition_numbers(raw_basis: torch.Tensor) -> torch.Tensor:
    real, imag = complex_gram_mean(raw_basis)
    gram = torch.complex(real, imag).detach().cpu()
    eigenvalues = torch.linalg.eigvalsh(gram).real.clamp_min(1e-12)
    return eigenvalues.amax(-1) / eigenvalues.amin(-1)


def _chart_values(
    model: nn.Module, coordinates: torch.Tensor, parameters: torch.Tensor
) -> dict[str, object]:
    if not isinstance(model, ROMGeneralizedTracePINN):
        return {}
    values = chart_statistics(model.chart_weights(parameters))
    return {
        "chart_entropy": float(values["entropy"].mean().detach().cpu()),
        "effective_charts": float(values["effective_charts"].mean().detach().cpu()),
        "chart_disagreement": float(
            model.chart_disagreement(coordinates, parameters).mean().detach().cpu()
        ),
        "mean_chart_weights": [
            float(value) for value in values["mean_weights"].detach().cpu()
        ],
    }


def _set_training_progress(model: nn.Module, progress: float) -> None:
    if isinstance(model, ROMGeneralizedTracePINN):
        model.set_training_progress(progress)


def _evaluate_suite(
    model: nn.Module,
    config: P4Config,
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
        reference_basis = reference_basis[..., :2, :].unsqueeze(0).to(
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
            "gram_condition": float(_gram_condition_numbers(output).amax()),
            "internal_gap": float(reference_values[1] - reference_values[0]),
            "external_gap": float(reference_values[2] - reference_values[1]),
        }
        row.update(_chart_values(model, coordinates, parameters))
        rows.append(row)
    return rows


def _monitor_points(points: list[dict[str, object]]) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for split in sorted({str(point["split"]) for point in points}):
        selected.append(next(point for point in points if point["split"] == split))
    return selected


def run_p4_run(
    config: P4Config,
    output_dir: Path,
    *,
    suite_payload: dict[str, object],
    suite_hash: str,
    references: dict[str, dict[str, object]],
    cache_hash: str,
) -> dict[str, object]:
    """Train, resume, evaluate, and persist one P4 diagnostic run."""

    _validate_method_family(config.method, config.potential_family)
    if config.steps < 1:
        raise ValueError("steps must be positive")
    torch.manual_seed(config.seed)
    device = select_device(config.device)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    dtype = torch.float32
    model = build_p4_model(
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
    sample_generator.manual_seed(config.seed + 2_000_003)

    output_dir.mkdir(parents=True, exist_ok=True)
    latest_path = output_dir / "latest.pt"
    final_path = output_dir / "final.pt"
    result_path = output_dir / "result.json"
    fingerprint = _config_fingerprint(config, suite_hash, cache_hash)
    source_fingerprint = _p4_source_fingerprint()
    completed = _load_completed_result(
        result_path,
        final_path,
        config_fingerprint=fingerprint,
        source_fingerprint=source_fingerprint,
        suite_hash=suite_hash,
        cache_hash=cache_hash,
    )
    if completed is not None:
        (output_dir / "failure.json").unlink(missing_ok=True)
        return completed

    family_points = [
        point
        for point in suite_payload["points"]
        if point["family"] == config.potential_family
    ]
    monitored = _monitor_points(family_points)
    start_step = 0
    elapsed_before = 0.0
    training_rows: list[dict[str, object]] = []
    if latest_path.is_file():
        state = torch.load(latest_path, map_location=device, weights_only=False)
        if state.get("config_fingerprint") != fingerprint:
            raise ValueError("P4 resume configuration fingerprint mismatch")
        if state.get("source_fingerprint") != source_fingerprint:
            raise ValueError("P4 resume source fingerprint mismatch")
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        _restore_rng_state(state["rng_state"], device)
        sample_generator.set_state(state["sample_rng_state"])
        start_step = int(state["step"])
        elapsed_before = float(state.get("elapsed_seconds", 0.0))
        training_rows = list(state.get("training_rows", []))

    start = time.perf_counter()
    for step in range(start_step, config.steps):
        _set_training_progress(model, step / max(config.steps - 1, 1))
        coordinates = _sample_coordinates(
            config.parameter_batch, config.points, device, dtype, sample_generator
        )
        parameters = _sample_parameters(
            config.parameter_batch, device, lower, upper, dtype, sample_generator
        )
        optimizer.zero_grad(set_to_none=True)
        output = model(coordinates, parameters)
        loss, loss_parts = _training_loss(
            config.method,
            output,
            coordinates,
            parameters,
            config.potential_family,
        )
        if not bool(torch.isfinite(loss).detach().cpu()):
            raise FloatingPointError(f"non-finite P4 loss at step {step}")
        loss.backward()
        gradient_norm = _gradient_norm(model)
        optimizer.step()

        should_log = (
            step == start_step
            or (step + 1) % config.monitor_every == 0
            or step + 1 == config.steps
        )
        if should_log:
            chart = _chart_values(model, coordinates, parameters)
            monitor_rows = _evaluate_suite(
                model, config, device, monitored, references
            )
            training_rows.append(
                {
                    "step": step + 1,
                    "loss": float(loss.detach().cpu()),
                    **loss_parts,
                    "gradient_norm": gradient_norm,
                    "gram_condition_mean": float(
                        _gram_condition_numbers(output).mean()
                    ),
                    "monitor_projector_mean": statistics.mean(
                        float(row["projector_sine_error"]) for row in monitor_rows
                    ),
                    "chart_entropy": chart.get("chart_entropy"),
                    "effective_charts": chart.get("effective_charts"),
                    "chart_disagreement": chart.get("chart_disagreement"),
                    "active_rom_scale": (
                        float(model.active_rom_scale.detach().cpu())
                        if isinstance(model, ROMGeneralizedTracePINN)
                        else None
                    ),
                }
            )
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
    evaluation = _evaluate_suite(model, config, device, family_points, references)
    projector_values = [float(row["projector_sine_error"]) for row in evaluation]
    residual_values = [float(row["residual_rms"]) for row in evaluation]
    orthogonality_values = [float(row["orthogonality_error"]) for row in evaluation]
    gram_conditions = [float(row["gram_condition"]) for row in evaluation]
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
        fieldnames = sorted({key for row in training_rows for key in row})
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
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
        "std_projector_sine_error": (
            statistics.stdev(projector_values) if len(projector_values) > 1 else 0.0
        ),
        "split_projector_mean": {
            split: statistics.mean(
                float(row["projector_sine_error"])
                for row in evaluation
                if row["split"] == split
            )
            for split in sorted({str(row["split"]) for row in evaluation})
        },
        "mean_residual_rms": statistics.mean(residual_values),
        "maximum_orthogonality_error": max(orthogonality_values),
        "maximum_gram_condition": max(gram_conditions),
        "final_checkpoint_sha256": file_sha256(final_path),
        "point_count": len(evaluation),
    }
    if isinstance(model, ROMGeneralizedTracePINN):
        result["final_rom_scale"] = float(model.active_rom_scale.detach().cpu())
        result["rom_schedule"] = model.rom_schedule
    chart_rows = [row for row in evaluation if "effective_charts" in row]
    if chart_rows:
        result["mean_chart_entropy"] = statistics.mean(
            float(row["chart_entropy"]) for row in chart_rows
        )
        result["mean_effective_charts"] = statistics.mean(
            float(row["effective_charts"]) for row in chart_rows
        )
        result["mean_chart_disagreement"] = statistics.mean(
            float(row["chart_disagreement"]) for row in chart_rows
        )
        chart_count = len(chart_rows[0]["mean_chart_weights"])
        result["mean_chart_weights"] = [
            statistics.mean(float(row["mean_chart_weights"][index]) for row in chart_rows)
            for index in range(chart_count)
        ]
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (output_dir / "failure.json").unlink(missing_ok=True)
    return result


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _improvement(baseline: float, candidate: float) -> float:
    if not math.isfinite(baseline) or baseline <= 0 or not math.isfinite(candidate):
        return -math.inf
    return 100.0 * (baseline - candidate) / baseline


def build_p4_gate(summary: dict[str, object]) -> dict[str, object]:
    """Apply the frozen scientific promotion rule to the 30-run matrix."""

    g0 = float(summary.get("g0_trace_near_cluster_projector_mean", math.inf))
    g1 = float(summary.get("g1_anchor_near_cluster_projector_mean", math.inf))
    g2 = float(summary.get("g2_static_rom_near_cluster_projector_mean", math.inf))
    g3 = float(summary.get("g3_annealed_rom_near_cluster_projector_mean", math.inf))
    k3 = float(summary.get("k3_p3_near_cluster_projector_mean", math.inf))
    overall = _improvement(g0, g1)
    historical_gain = _improvement(k3, g1)
    family_improvements = {
        family: _improvement(
            float(
                summary.get(
                    f"g0_trace_{family}_near_cluster_projector_mean", math.inf
                )
            ),
            float(
                summary.get(
                    f"g1_anchor_{family}_near_cluster_projector_mean", math.inf
                )
            ),
        )
        for family in P4_FAMILIES
    }
    paired = summary.get("paired_seed_improvements", [])
    paired_values = [
        float(row.get("improvement_percent", -math.inf))
        for row in paired
        if isinstance(row, dict)
    ]
    parameter_count_pairs = {
        family: (
            int(summary.get(f"g0_trace_{family}_num_parameters", -1)),
            int(summary.get(f"g1_anchor_{family}_num_parameters", -2)),
        )
        for family in P4_FAMILIES
    }
    finite_metrics = all(
        _finite_number(value)
        for value in (
            g0,
            g1,
            g2,
            g3,
            k3,
            summary.get("maximum_orthogonality_error", math.inf),
            summary.get("maximum_gram_condition", math.inf),
            summary.get("g3_maximum_final_rom_scale", math.inf),
        )
    ) and all(math.isfinite(value) for value in paired_values)
    gate: dict[str, object] = {
        "all_runs_completed": int(summary.get("total_runs", 0)) == 30
        and int(summary.get("completed_runs", 0)) == 30
        and int(summary.get("failed_runs", 30)) == 0,
        "finite_metrics": finite_metrics,
        "orthogonality_pass": float(
            summary.get("maximum_orthogonality_error", math.inf)
        )
        < 2e-4,
        "gram_condition_pass": float(summary.get("maximum_gram_condition", math.inf))
        < 1e8,
        "g1_vs_g0_improvement_percent": overall,
        "g1_vs_g0_at_least_15pct": overall >= 15.0,
        "family_improvement_percent": family_improvements,
        "g1_vs_g0_at_least_15pct_each_family": all(
            value >= 15.0 for value in family_improvements.values()
        ),
        "g1_vs_historical_p3_improvement_percent": historical_gain,
        "g1_better_than_historical_p3": historical_gain > 0.0,
        "parameter_count_pairs": parameter_count_pairs,
        "g1_matches_g0_parameter_count_each_family": all(
            baseline_count >= 0 and baseline_count == candidate_count
            for baseline_count, candidate_count in parameter_count_pairs.values()
        ),
        "g1_within_2pct_of_best_rom_extension": g1
        <= 1.02 * min(g2, g3),
        "paired_seed_improvements": paired,
        "all_family_seed_pairs_improve": len(paired_values) == 6
        and all(value > 0.0 for value in paired_values),
        "rom_fully_annealed": float(
            summary.get("g3_maximum_final_rom_scale", math.inf)
        )
        <= 1e-8,
    }
    gate["promotion_go"] = all(
        bool(gate[key])
        for key in (
            "all_runs_completed",
            "finite_metrics",
            "orthogonality_pass",
            "gram_condition_pass",
            "g1_vs_g0_at_least_15pct",
            "g1_vs_g0_at_least_15pct_each_family",
            "g1_better_than_historical_p3",
            "g1_matches_g0_parameter_count_each_family",
            "g1_within_2pct_of_best_rom_extension",
            "all_family_seed_pairs_improve",
            "rom_fully_annealed",
        )
    )
    return gate


def build_smoke_gate(summary: dict[str, object]) -> dict[str, object]:
    total = int(summary.get("total_runs", 0))
    gate: dict[str, object] = {
        "all_runs_completed": total > 0
        and int(summary.get("completed_runs", 0)) == total
        and int(summary.get("failed_runs", total)) == 0,
        "finite_metrics": _finite_number(
            summary.get("maximum_orthogonality_error", math.inf)
        )
        and _finite_number(summary.get("maximum_gram_condition", math.inf)),
        "orthogonality_pass": float(
            summary.get("maximum_orthogonality_error", math.inf)
        )
        < 5e-4,
        "gram_condition_pass": float(summary.get("maximum_gram_condition", math.inf))
        < 1e8,
    }
    gate["engineering_pass"] = all(bool(value) for value in gate.values())
    return gate


def _selected_points(
    suite_payload: dict[str, object], max_points_per_split: int
) -> list[dict[str, object]]:
    points = list(suite_payload["points"])
    if max_points_per_split <= 0:
        return points
    selected: list[dict[str, object]] = []
    counts: dict[tuple[str, str], int] = {}
    for point in points:
        key = (str(point["family"]), str(point["split"]))
        if counts.get(key, 0) < max_points_per_split:
            selected.append(point)
            counts[key] = counts.get(key, 0) + 1
    return selected


def _aggregate_summary(
    *,
    protocol: str,
    results: list[dict[str, object]],
    failures: list[dict[str, object]],
    methods: tuple[str, ...],
    families: tuple[str, ...],
    seeds: tuple[int, ...],
    suite_payload: dict[str, object],
    suite_hash: str,
    cache_hash: str,
    steps: int,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "scope": "v2_validation_p4_objective_diagnostic_not_final_test",
        "protocol": protocol,
        "total_runs": len(methods) * len(families) * len(seeds),
        "completed_runs": len(results),
        "failed_runs": len(failures),
        "suite_id": suite_payload["suite_id"],
        "suite_sha256": suite_hash,
        "reference_cache_sha256": cache_hash,
        "source_fingerprint": _p4_source_fingerprint(),
        "methods": list(methods),
        "families": list(families),
        "seeds": list(seeds),
        "steps": steps,
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
        "maximum_gram_condition": max(
            (float(result["maximum_gram_condition"]) for result in results),
            default=math.inf,
        ),
        "failures": failures,
    }
    for method in methods:
        method_results = [
            result for result in results if result["config"]["method"] == method
        ]
        values = [float(result["mean_projector_sine_error"]) for result in method_results]
        summary[f"{method}_projector_mean"] = (
            statistics.mean(values) if values else math.inf
        )
        near = [
            float(result["split_projector_mean"]["near_cluster"])
            for result in method_results
            if "near_cluster" in result["split_projector_mean"]
        ]
        summary[f"{method}_near_cluster_projector_mean"] = (
            statistics.mean(near) if near else math.inf
        )
        parameter_counts = {int(result["num_parameters"]) for result in method_results}
        summary[f"{method}_num_parameters"] = (
            parameter_counts.pop() if len(parameter_counts) == 1 else -1
        )
        for family in families:
            family_results = [
                result
                for result in method_results
                if result["config"]["potential_family"] == family
            ]
            family_near = [
                float(result["split_projector_mean"]["near_cluster"])
                for result in family_results
                if "near_cluster" in result["split_projector_mean"]
            ]
            summary[f"{method}_{family}_near_cluster_projector_mean"] = (
                statistics.mean(family_near) if family_near else math.inf
            )
            family_parameter_counts = {
                int(result["num_parameters"]) for result in family_results
            }
            summary[f"{method}_{family}_num_parameters"] = (
                family_parameter_counts.pop()
                if len(family_parameter_counts) == 1
                else -1
            )

    g3_results = [
        result for result in results if result["config"]["method"] == "g3_annealed_rom"
    ]
    summary["g3_mean_effective_charts"] = (
        statistics.mean(float(result["mean_effective_charts"]) for result in g3_results)
        if g3_results
        else -math.inf
    )
    summary["g3_mean_chart_disagreement"] = (
        statistics.mean(
            float(result["mean_chart_disagreement"]) for result in g3_results
        )
        if g3_results
        else -math.inf
    )
    summary["g3_maximum_final_rom_scale"] = max(
        (float(result.get("final_rom_scale", math.inf)) for result in g3_results),
        default=math.inf,
    )
    if g3_results and all("mean_chart_weights" in result for result in g3_results):
        chart_count = len(g3_results[0]["mean_chart_weights"])
        mean_weights = [
            statistics.mean(
                float(result["mean_chart_weights"][index]) for result in g3_results
            )
            for index in range(chart_count)
        ]
        summary["g3_mean_chart_weights"] = mean_weights
        summary["g3_minimum_mean_chart_weight"] = min(mean_weights)
    else:
        summary["g3_mean_chart_weights"] = []
        summary["g3_minimum_mean_chart_weight"] = -math.inf

    paired: list[dict[str, object]] = []
    for family in families:
        for seed in seeds:
            indexed = {
                str(result["config"]["method"]): result
                for result in results
                if result["config"]["potential_family"] == family
                and int(result["config"]["seed"]) == seed
            }
            if "g0_trace" not in indexed or "g1_anchor" not in indexed:
                continue
            g0 = float(indexed["g0_trace"]["split_projector_mean"]["near_cluster"])
            candidate = float(
                indexed["g1_anchor"]["split_projector_mean"]["near_cluster"]
            )
            paired.append(
                {
                    "family": family,
                    "seed": seed,
                    "g0_error": g0,
                    "g1_error": candidate,
                    "improvement_percent": _improvement(g0, candidate),
                }
            )
    summary["paired_seed_improvements"] = paired
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", choices=("smoke", "promotion"), default="smoke")
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "mps", "cuda", "rocm"))
    parser.add_argument("--method", choices=(*P4_METHODS, "all"), default="all")
    parser.add_argument("--family", choices=(*P4_FAMILIES, "all"), default="all")
    parser.add_argument("--seed", type=int, nargs="+", default=None)
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--points", type=int, default=None)
    parser.add_argument("--parameter-batch", type=int, default=None)
    parser.add_argument("--checkpoint-every", type=int, default=None)
    parser.add_argument("--monitor-every", type=int, default=None)
    parser.add_argument("--max-points-per-split", type=int, default=None)
    parser.add_argument("--suite", type=Path, default=Path("benchmarks/v2_validation.json"))
    parser.add_argument(
        "--reference-cache", type=Path, default=Path("data/v2_validation_references.pt")
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    if args.protocol == "promotion":
        seeds = tuple(args.seed or P4_PROMOTION_SEEDS)
        steps = args.steps or P4_PROMOTION_STEPS
        points = args.points or P4_PROMOTION_POINTS
        parameter_batch = args.parameter_batch or P4_PROMOTION_PARAMETER_BATCH
        checkpoint_every = (
            args.checkpoint_every or P4_PROMOTION_CHECKPOINT_EVERY
        )
        monitor_every = args.monitor_every or P4_PROMOTION_MONITOR_EVERY
        max_points_per_split = args.max_points_per_split or 0
        if args.method != "all" or args.family != "all":
            raise ValueError("P4 promotion requires all five methods and both families")
        if seeds != P4_PROMOTION_SEEDS:
            raise ValueError(f"P4 promotion seeds are frozen as {P4_PROMOTION_SEEDS}")
        if steps != P4_PROMOTION_STEPS:
            raise ValueError(f"P4 promotion steps are frozen as {P4_PROMOTION_STEPS}")
        if points != P4_PROMOTION_POINTS:
            raise ValueError(f"P4 promotion points are frozen as {P4_PROMOTION_POINTS}")
        if parameter_batch != P4_PROMOTION_PARAMETER_BATCH:
            raise ValueError(
                "P4 promotion parameter batch is frozen as "
                f"{P4_PROMOTION_PARAMETER_BATCH}"
            )
        if checkpoint_every != P4_PROMOTION_CHECKPOINT_EVERY:
            raise ValueError(
                "P4 promotion checkpoint interval is frozen as "
                f"{P4_PROMOTION_CHECKPOINT_EVERY}"
            )
        if monitor_every != P4_PROMOTION_MONITOR_EVERY:
            raise ValueError(
                "P4 promotion monitor interval is frozen as "
                f"{P4_PROMOTION_MONITOR_EVERY}"
            )
        if max_points_per_split != 0:
            raise ValueError("P4 promotion must evaluate the complete validation suite")
        output_dir = args.output_dir or Path("results/p4_promotion")
    else:
        seeds = tuple(args.seed or (42,))
        steps = args.steps or 5
        points = args.points or 64
        parameter_batch = args.parameter_batch or 1
        checkpoint_every = args.checkpoint_every or max(1, steps)
        monitor_every = args.monitor_every or max(1, steps)
        max_points_per_split = (
            1 if args.max_points_per_split is None else args.max_points_per_split
        )
        output_dir = args.output_dir or Path("results/p4_smoke")

    suite_payload, suite_hash = load_frozen_suite(args.suite)
    if suite_payload.get("purpose") != "pilot_and_hyperparameter_selection":
        raise ValueError("P4 diagnostics may use validation only, never frozen final")
    selected = _selected_points(suite_payload, max_points_per_split)
    selected_payload = dict(suite_payload)
    selected_payload["points"] = selected
    point_ids = {str(point["id"]) for point in selected}
    references, cache_hash = _load_reference_cache(
        args.reference_cache,
        suite_id=str(suite_payload["suite_id"]),
        suite_hash=suite_hash,
        point_ids=point_ids,
        grid_side=33,
        cutoff=24,
    )
    methods = P4_METHODS if args.method == "all" else (args.method,)
    families = P4_FAMILIES if args.family == "all" else (args.family,)
    total = len(methods) * len(families) * len(seeds)
    results: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for method in methods:
        for family in families:
            for seed in seeds:
                run_id = f"{method}_{family}_seed{seed}"
                print(f"[{len(results) + len(failures) + 1}/{total}] {run_id}", flush=True)
                config = P4Config(
                    method=method,
                    potential_family=family,
                    seed=seed,
                    protocol=args.protocol,
                    device=args.device,
                    steps=steps,
                    points=points,
                    parameter_batch=parameter_batch,
                    checkpoint_every=checkpoint_every,
                    monitor_every=monitor_every,
                )
                try:
                    results.append(
                        run_p4_run(
                            config,
                            output_dir / run_id,
                            suite_payload=selected_payload,
                            suite_hash=suite_hash,
                            references=references,
                            cache_hash=cache_hash,
                        )
                    )
                except Exception as error:
                    failure = {
                        "status": "FAIL",
                        "run_id": run_id,
                        "error_type": type(error).__name__,
                        "reason": str(error),
                        "traceback": traceback.format_exc(),
                    }
                    run_dir = output_dir / run_id
                    run_dir.mkdir(parents=True, exist_ok=True)
                    (run_dir / "failure.json").write_text(
                        json.dumps(failure, ensure_ascii=False, indent=2) + "\n"
                    )
                    failures.append(failure)

    summary = _aggregate_summary(
        protocol=args.protocol,
        results=results,
        failures=failures,
        methods=methods,
        families=families,
        seeds=seeds,
        suite_payload=suite_payload,
        suite_hash=suite_hash,
        cache_hash=cache_hash,
        steps=steps,
    )
    gate = build_p4_gate(summary) if args.protocol == "promotion" else build_smoke_gate(summary)
    summary["gate"] = gate
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    (output_dir / "diagnostic_gate.json").write_text(
        json.dumps(gate, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(gate, ensure_ascii=False, indent=2))
    passed = bool(
        gate["promotion_go"] if args.protocol == "promotion" else gate["engineering_pass"]
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

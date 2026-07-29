"""Evaluate one trained checkpoint on a frozen SCI-Q3 parameter suite."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import statistics
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.experiment import ExperimentConfig, _source_fingerprint
from block_kyfan_pinn.device import select_device
from block_kyfan_pinn.metrics import orthogonality_error, principal_angle_degrees, projector_sine_error
from block_kyfan_pinn.model import (BlockKyFanPINN, CausalSortPINN, GalerkinSubspacePINN,
                                   GeneralizedTracePINN, OrderedEigenPINN)
from block_kyfan_pinn.physics import (apply_hamiltonian, causal_sorted_basis, galerkin_rank_basis, periodic_mgs,
                                     projected_residual_rms, ritz_matrix)
from block_kyfan_pinn.reference import ReferenceSolution, evaluate_reference_basis, solve_reference, uniform_grid


_CHECKPOINT_CONFIG_DEFAULTS = {
    "orthogonalization": "stop_gradient",
    "sampling_stream": "legacy_global_v1",
}
_CHECKPOINT_CONFIG_KEYS = (
    "method",
    "width",
    "hidden_layers",
    "anchor_kind",
    "anchor_scale",
    "potential_family",
    "parameter_lower",
    "parameter_upper",
    "dtype",
    "subspace_rank",
    "orthogonalization",
    "sampling_stream",
)


def _normalized_config_value(value: object) -> object:
    return tuple(value) if isinstance(value, (list, tuple)) else value


def _validate_checkpoint_config(config: ExperimentConfig, checkpoint_config: dict[str, object]) -> None:
    """Reject semantic mismatches that do not change state-dict tensor shapes."""

    for key in _CHECKPOINT_CONFIG_KEYS:
        expected = _normalized_config_value(getattr(config, key))
        actual = _normalized_config_value(
            checkpoint_config.get(key, _CHECKPOINT_CONFIG_DEFAULTS.get(key))
        )
        if actual != expected:
            raise ValueError(f"checkpoint config mismatch for {key}: expected {expected!r}, got {actual!r}")


def _validate_checkpoint_source(config: ExperimentConfig, state: dict[str, object]) -> None:
    """Bind current-protocol evaluations to the exact training-library sources."""

    recorded = state.get("source_fingerprint")
    if config.sampling_stream == "cpu_generator_v2" and recorded != _source_fingerprint():
        raise ValueError("checkpoint source fingerprint does not match current training library")


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def _summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output = []
    for split in sorted({str(row["split"]) for row in rows}):
        selected = [row for row in rows if row["split"] == split]
        errors = [float(row["projector_sine_error"]) for row in selected]
        output.append({
            "split": split,
            "n": len(errors),
            "mean": statistics.mean(errors),
            "std": statistics.stdev(errors) if len(errors) > 1 else 0.0,
            "median": statistics.median(errors),
            "p95": _percentile(errors, 0.95),
            "maximum": max(errors),
            "cluster_failure_rate": sum(error > 0.5 for error in errors) / len(errors),
        })
    return output


def _validate_suite_payload(suite: dict[str, object]) -> list[dict[str, object]]:
    """Validate identity and numeric integrity before selecting a family."""

    raw_points = suite.get("points")
    if not isinstance(raw_points, list) or not raw_points:
        raise ValueError("suite points must be a non-empty list")
    if int(suite.get("point_count", -1)) != len(raw_points):
        raise ValueError("suite point_count does not match points")
    points: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in raw_points:
        if not isinstance(raw, dict):
            raise ValueError("each suite point must be an object")
        identity = str(raw.get("id", ""))
        if not identity or identity in seen:
            raise ValueError(f"suite point id is empty or duplicated: {identity!r}")
        seen.add(identity)
        if not str(raw.get("family", "")) or not str(raw.get("split", "")):
            raise ValueError(f"suite point {identity} is missing family or split")
        parameters = raw.get("parameters")
        if not isinstance(parameters, list) or not parameters:
            raise ValueError(f"suite point {identity} has invalid parameters")
        if not all(math.isfinite(float(value)) for value in parameters):
            raise ValueError(f"suite point {identity} has non-finite parameters")
        points.append(raw)
    return points


def _validate_reference_cache(
    payload: dict[str, object], config: ExperimentConfig, suite: dict[str, object],
    suite_hash: str, expected_ids: set[str],
) -> tuple[dict[str, dict[str, torch.Tensor]], dict[str, object]]:
    metadata = payload.get("metadata")
    references = payload.get("references")
    if not isinstance(metadata, dict) or not isinstance(references, dict):
        raise ValueError("reference cache must contain metadata and references")
    expected_metadata = {
        "suite_id": suite.get("suite_id"),
        "suite_sha256": suite_hash,
        "grid_side": config.eval_grid_side,
        "cutoff": config.reference_cutoff,
    }
    for key, expected in expected_metadata.items():
        if metadata.get(key) != expected:
            raise ValueError(
                f"reference cache metadata mismatch for {key}: expected {expected!r}, got {metadata.get(key)!r}"
            )
    missing = expected_ids - set(references)
    if missing:
        raise ValueError(f"reference cache is missing {len(missing)} selected point ids")
    expected_points = config.eval_grid_side ** 2
    for identity in expected_ids:
        entry = references[identity]
        if not isinstance(entry, dict) or "basis" not in entry or "eigenvalues" not in entry:
            raise ValueError(f"invalid reference cache entry for {identity}")
        basis = entry["basis"]
        eigenvalues = entry["eigenvalues"]
        if not isinstance(basis, torch.Tensor) or not isinstance(eigenvalues, torch.Tensor):
            raise ValueError(f"reference cache tensors are invalid for {identity}")
        if tuple(basis.shape) != (expected_points, 2, 2):
            raise ValueError(f"reference cache tensor shape mismatch for {identity}")
        if eigenvalues.ndim != 1 or eigenvalues.numel() < 3:
            raise ValueError(f"reference cache tensor shape mismatch for {identity}")
        if not bool(torch.isfinite(basis).all()) or not bool(torch.isfinite(eigenvalues).all()):
            raise ValueError(f"reference cache contains non-finite values for {identity}")
    return references, metadata


def _load_model(config: ExperimentConfig, checkpoint: Path, device: torch.device):
    parameter_dim = len(config.parameter_lower)
    if config.method == "block_kyfan":
        model = BlockKyFanPINN(width=config.width, hidden_layers=config.hidden_layers,
                               anchor_kind=config.anchor_kind, anchor_scale=config.anchor_scale,
                               parameter_dim=parameter_dim,
                               orthogonalization=config.orthogonalization)
    elif config.method == "ordered_residual":
        model = OrderedEigenPINN(width=config.width, hidden_layers=config.hidden_layers,
                                 parameter_dim=parameter_dim)
    elif config.method == "wang_xie_trace":
        model = GeneralizedTracePINN(width=config.width, hidden_layers=config.hidden_layers,
                                     parameter_dim=parameter_dim)
    elif config.method == "dai_galerkin":
        model = GalerkinSubspacePINN(width=config.width, hidden_layers=config.hidden_layers,
                                     parameter_dim=parameter_dim, subspace_rank=config.subspace_rank)
    elif config.method == "supervised_grassmann":
        model = GalerkinSubspacePINN(width=config.width, hidden_layers=config.hidden_layers,
                                     parameter_dim=parameter_dim, subspace_rank=config.subspace_rank)
    elif config.method == "causal_sort":
        model = CausalSortPINN(width=config.width, hidden_layers=config.hidden_layers,
                               parameter_dim=parameter_dim)
    else:
        raise ValueError(f"unsupported method: {config.method}")
    state = torch.load(checkpoint, map_location=device, weights_only=False)
    checkpoint_config = state.get("config")
    if not isinstance(checkpoint_config, dict):
        raise ValueError("checkpoint has no embedded experiment config")
    _validate_checkpoint_config(config, checkpoint_config)
    embedded_fingerprint = hashlib.sha256(
        json.dumps(checkpoint_config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    recorded_fingerprint = state.get("config_fingerprint")
    if recorded_fingerprint != embedded_fingerprint:
        raise ValueError("checkpoint config fingerprint is missing or invalid")
    _validate_checkpoint_source(config, state)
    model.load_state_dict(state["model"])
    dtype = torch.float64 if config.dtype == "float64" else torch.float32
    return model.to(device=device, dtype=dtype).eval(), state


def _evaluate_point(model, config: ExperimentConfig, point: dict[str, object], coordinates_cpu: torch.Tensor,
                    device: torch.device, cached_reference: dict[str, torch.Tensor] | None = None) -> dict[str, object]:
    values = [float(value) for value in point["parameters"]]  # type: ignore[index]
    coordinates = coordinates_cpu.unsqueeze(0).to(device).requires_grad_()
    parameters = torch.tensor([values], dtype=coordinates.dtype, device=device)
    output = model(coordinates, parameters)
    if isinstance(output, tuple):
        basis = output[0]
    elif config.method == "wang_xie_trace":
        basis = periodic_mgs(output)
    elif config.method in {"dai_galerkin", "supervised_grassmann"}:
        basis = galerkin_rank_basis(output, coordinates, parameters, config.potential_family)
    elif config.method == "causal_sort":
        basis = causal_sorted_basis(output, coordinates, parameters, config.potential_family)
    else:
        basis = output
    h_basis = apply_hamiltonian(basis, coordinates, parameters, config.potential_family)
    residual = float(projected_residual_rms(basis, h_basis).detach().cpu())
    ritz_real, ritz_imag = ritz_matrix(basis, h_basis)
    ritz = torch.linalg.eigvalsh(torch.complex(ritz_real, ritz_imag)[0].detach().cpu()).real

    if cached_reference is None:
        reference3 = solve_reference(parameters[0], cutoff=config.reference_cutoff, rank=3,
                                     potential_family=config.potential_family)
        reference2 = ReferenceSolution(reference3.eigenvalues[:2], reference3.eigenvectors[:, :2], reference3.modes)
        reference_basis = periodic_mgs(evaluate_reference_basis(reference2, coordinates))
        reference_values = reference3.eigenvalues
    else:
        reference_basis = cached_reference["basis"].unsqueeze(0).to(device=device, dtype=coordinates.dtype)
        reference_values = cached_reference["eigenvalues"]
    angle_mean, angle_max = principal_angle_degrees(basis, reference_basis)
    eigen_relative = float(((ritz - reference_values[:2]).abs() / reference_values[:2].abs().clamp_min(1e-12)).max())
    trace_relative = float((ritz.sum() - reference_values[:2].sum()).abs() /
                           reference_values[:2].abs().sum().clamp_min(1e-12))
    external_gap = float(reference_values[2] - reference_values[1])
    normalized_gap = external_gap / max(float(reference_values[2].abs()), 1.0)

    with torch.no_grad():
        shifted_x = coordinates.detach().clone(); shifted_x[..., 0] += 2.0 * math.pi
        shifted_y = coordinates.detach().clone(); shifted_y[..., 1] += 2.0 * math.pi
        base = model(coordinates.detach(), parameters); base = base[0] if isinstance(base, tuple) else base
        px = model(shifted_x, parameters); px = px[0] if isinstance(px, tuple) else px
        py = model(shifted_y, parameters); py = py[0] if isinstance(py, tuple) else py
        periodic_error = float(torch.maximum((base - px).abs().max(), (base - py).abs().max()).cpu())

    return {
        "id": point["id"], "family": point["family"], "split": point["split"],
        **{f"parameter_{index}": value for index, value in enumerate(values)},
        "projector_sine_error": projector_sine_error(basis, reference_basis),
        "principal_angle_mean_deg": angle_mean, "principal_angle_max_deg": angle_max,
        "eigenvalue_relative_max": eigen_relative, "trace_relative_error": trace_relative,
        "ritz_residual_rms": residual, "orthogonality_error": orthogonality_error(basis),
        "periodic_boundary_error": periodic_error, "external_gap": external_gap,
        "normalized_external_gap": normalized_gap,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("suite", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--reference-cache", type=Path)
    args = parser.parse_args()
    config = ExperimentConfig.from_json(args.config)
    suite_bytes = args.suite.read_bytes()
    suite = json.loads(suite_bytes)
    points = [point for point in _validate_suite_payload(suite) if point["family"] == config.potential_family]
    if args.limit is not None:
        points = points[:args.limit]
    if not points:
        raise ValueError("suite contains no points for this potential family")
    expected_parameter_dim = len(config.parameter_lower)
    if any(len(point["parameters"]) != expected_parameter_dim for point in points):
        raise ValueError("suite parameter dimension does not match experiment config")
    device = select_device(config.device)
    model, checkpoint_state = _load_model(config, args.checkpoint, device)
    dtype = torch.float64 if config.dtype == "float64" else torch.float32
    coordinates = uniform_grid(config.eval_grid_side, dtype=dtype)
    cache = None
    cache_metadata: dict[str, object] | None = None
    suite_hash = hashlib.sha256(suite_bytes).hexdigest()
    if args.reference_cache:
        cache_payload = torch.load(args.reference_cache, map_location="cpu")
        cache, cache_metadata = _validate_reference_cache(
            cache_payload, config, suite, suite_hash, {str(point["id"]) for point in points}
        )
    rows = [_evaluate_point(model, config, point, coordinates, device,
                            None if cache is None else cache[point["id"]]) for point in points]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "per_parameter.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    result = {
        "status": "COMPLETE", "suite_id": suite["suite_id"], "suite_sha256": suite_hash,
        "suite": str(args.suite),
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        "checkpoint_seed": checkpoint_state.get("seed"),
        "checkpoint_config_fingerprint": checkpoint_state.get("config_fingerprint"),
        "checkpoint_source_fingerprint": checkpoint_state.get("source_fingerprint"),
        "config": str(args.config),
        "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "reference": {
            "mode": "cache" if args.reference_cache else "on_demand",
            "cache": str(args.reference_cache) if args.reference_cache else None,
            "cache_sha256": hashlib.sha256(args.reference_cache.read_bytes()).hexdigest()
            if args.reference_cache else None,
            "metadata": cache_metadata,
            "actual_grid_side": config.eval_grid_side,
            "actual_cutoff": config.reference_cutoff,
        },
        "potential_family": config.potential_family,
        "point_count": len(rows), "environment": {"python": platform.python_version(), "torch": torch.__version__,
        "device": str(device)}, "aggregate": _summary(rows),
    }
    (args.output_dir / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

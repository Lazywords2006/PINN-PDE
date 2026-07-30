"""Reproducible multi-parameter training and reference evaluation."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import torch

from .device import select_device, synchronize
from .metrics import projector_sine_error
from .model import BlockKyFanPINN, CausalSortPINN, GalerkinSubspacePINN, GeneralizedTracePINN, OrderedEigenPINN
from .physics import (
    apply_hamiltonian,
    causal_sort_energy,
    causal_sorted_basis,
    galerkin_low_energy,
    galerkin_rank_basis,
    generalized_trace_energy,
    ky_fan_energy,
    ordered_residual_loss,
    periodic_mgs,
    projected_residual_rms,
    ritz_matrix,
)
from .reference import evaluate_reference_basis, solve_reference, uniform_grid


@dataclass(frozen=True)
class ExperimentConfig:
    name: str
    method: str = "block_kyfan"
    device: str = "auto"
    seeds: tuple[int, ...] = (11, 22, 33)
    steps: int = 5000
    points: int = 1024
    parameter_batch: int = 8
    width: int = 96
    hidden_layers: int = 4
    learning_rate: float = 1e-3
    anchor_kind: str = "correct"
    anchor_scale: float = 0.1
    residual_weight: float = 0.0
    residual_start_fraction: float = 0.8
    eval_grid_side: int = 33
    reference_cutoff: int = 8
    checkpoint_every: int = 500
    resume: bool = True
    output_dir: str = "results/formal/main"
    potential_family: str = "harmonic_honeycomb"
    parameter_lower: tuple[float, ...] = (0.28, 0.28, 0.20, -0.08)
    parameter_upper: tuple[float, ...] = (0.38, 0.38, 0.80, 0.08)
    dtype: str = "float32"
    subspace_rank: int = 6
    # dual_path preserves parameter gradients through the Gram transform while
    # preventing cross-point coordinate derivatives.  The historical
    # stop_gradient path is retained only as an explicit ablation.
    orthogonalization: str = "dual_path"
    sampling_stream: str = "cpu_generator_v2"

    @classmethod
    def from_json(cls, path: Path) -> "ExperimentConfig":
        values = json.loads(path.read_text())
        values["seeds"] = tuple(values["seeds"])
        for key in ("parameter_lower", "parameter_upper"):
            if key in values:
                values[key] = tuple(values[key])
        return cls(**values)


def _config_fingerprint(config: ExperimentConfig) -> str:
    body = json.dumps(asdict(config), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def _source_fingerprint() -> str:
    """Hash training-library sources so resume cannot cross code revisions."""

    root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _capture_rng_state(device: torch.device) -> dict[str, object]:
    state: dict[str, object] = {"cpu": torch.get_rng_state()}
    if device.type == "cuda":
        state["cuda"] = torch.cuda.get_rng_state_all()
    elif device.type == "mps":
        state["mps"] = torch.mps.get_rng_state()
    return state


def _restore_rng_state(state: dict[str, object], device: torch.device) -> None:
    torch.set_rng_state(state["cpu"])  # type: ignore[arg-type]
    if device.type == "cuda" and "cuda" in state:
        torch.cuda.set_rng_state_all(state["cuda"])  # type: ignore[arg-type]
    elif device.type == "mps" and "mps" in state:
        torch.mps.set_rng_state(state["mps"])  # type: ignore[arg-type]


def pilot_gate(summary: dict[str, object]) -> tuple[bool, list[str]]:
    """Return whether a CUDA pilot is safe to promote to the formal matrix."""

    reasons: list[str] = []
    mean_error = float(summary.get("mean_projector_sine_error", float("inf")))
    std_error = float(summary.get("std_projector_sine_error", float("inf")))
    if mean_error >= 0.34:
        reasons.append(f"mean projector error {mean_error:.4f} >= 0.34")
    if std_error >= 0.02:
        reasons.append(f"projector std {std_error:.4f} >= 0.02")
    case_limits = {"interpolation": 0.27, "symmetric_cluster": 0.35}
    aggregate = {str(row["case"]): row for row in summary.get("aggregate", [])}  # type: ignore[union-attr]
    for case, limit in case_limits.items():
        value = float(aggregate.get(case, {}).get("projector_mean", float("inf")))
        if value >= limit:
            reasons.append(f"{case} projector error {value:.4f} >= {limit:.2f}")
    return not reasons, reasons


def _sample_parameters(
    batch: int, device: torch.device, lower_values: tuple[float, ...], upper_values: tuple[float, ...],
    dtype: torch.dtype = torch.float32, generator: torch.Generator | None = None,
) -> torch.Tensor:
    if len(lower_values) != len(upper_values) or len(lower_values) < 4:
        raise ValueError("parameter bounds must have equal length of at least four")
    # Sampling on a dedicated CPU generator makes the parameter stream
    # independent of model initialization, architecture, and accelerator.
    unit = torch.rand(batch, len(lower_values), dtype=dtype, generator=generator).to(device)
    lower = torch.tensor(lower_values, device=device, dtype=dtype)
    upper = torch.tensor(upper_values, device=device, dtype=dtype)
    return lower + unit * (upper - lower)


def _sample_coordinates(
    batch: int, minimum_points: int, device: torch.device, dtype: torch.dtype = torch.float32,
    generator: torch.Generator | None = None,
) -> torch.Tensor:
    side = math.ceil(math.sqrt(minimum_points))
    base = uniform_grid(side, dtype=dtype).to(device)
    shifts = (
        torch.rand(batch, 1, 2, dtype=dtype, generator=generator)
        * (2.0 * math.pi / side)
    ).to(device)
    return torch.remainder(base.unsqueeze(0) + shifts, 2.0 * math.pi).to(device).requires_grad_()


def _evaluation_cases(potential_family: str) -> tuple[tuple[str, tuple[float, ...]], ...]:
    if potential_family == "gaussian_honeycomb":
        return (
            ("interpolation", (0.31, 0.35, 2.0, 0.26, 0.04)),
            ("symmetric_cluster", (1.0 / 3.0, 1.0 / 3.0, 2.5, 0.26, 0.0)),
            ("extrapolation", (0.42, 0.24, 4.4, 0.37, 0.10)),
        )
    return (
        ("interpolation", (0.31, 0.35, 0.35, 0.05)),
        ("symmetric_cluster", (1.0 / 3.0, 1.0 / 3.0, 0.60, 0.0)),
        ("extrapolation", (0.42, 0.24, 0.90, 0.16)),
    )


def _evaluate(
    model: BlockKyFanPINN | OrderedEigenPINN | GeneralizedTracePINN | GalerkinSubspacePINN | CausalSortPINN,
    config: ExperimentConfig,
    device: torch.device,
) -> list[dict[str, object]]:
    dtype = torch.float64 if config.dtype == "float64" else torch.float32
    coordinates_cpu = uniform_grid(config.eval_grid_side, dtype=dtype)
    rows: list[dict[str, object]] = []
    for case, values in _evaluation_cases(config.potential_family):
        coordinates = coordinates_cpu.unsqueeze(0).to(device).requires_grad_()
        parameters = torch.tensor([values], device=device)
        output = model(coordinates, parameters)
        if isinstance(output, tuple):
            basis = output[0]
        elif config.method == "wang_xie_trace":
            basis = periodic_mgs(output)
        elif config.method == "dai_galerkin":
            basis = galerkin_rank_basis(output, coordinates, parameters, config.potential_family)
        elif config.method == "causal_sort":
            basis = causal_sorted_basis(output, coordinates, parameters, config.potential_family)
        else:
            basis = output
        h_basis = apply_hamiltonian(basis, coordinates, parameters, config.potential_family)
        residual = float(projected_residual_rms(basis, h_basis).detach().cpu())
        matrix_real, matrix_imag = ritz_matrix(basis, h_basis)
        if device.type == "mps":
            matrix_real = matrix_real.cpu()
            matrix_imag = matrix_imag.cpu()
        matrix = torch.complex(matrix_real.detach(), matrix_imag.detach())
        ritz_values = torch.linalg.eigvalsh(matrix[0]).real.cpu()
        reference = solve_reference(
            parameters[0], cutoff=config.reference_cutoff, rank=2, potential_family=config.potential_family
        )
        reference_basis = periodic_mgs(evaluate_reference_basis(reference, coordinates))
        parameter_fields = (
            {"kx": values[0], "ky": values[1], "amplitude": values[2], "sigma": values[3],
             "imbalance": values[4]}
            if config.potential_family == "gaussian_honeycomb"
            else {"kx": values[0], "ky": values[1], "v0": values[2], "delta": values[3]}
        )
        rows.append(
            {
                "case": case,
                **parameter_fields,
                "projector_sine_error": projector_sine_error(basis, reference_basis),
                "residual_rms": residual,
                "ritz_1": float(ritz_values[0]),
                "ritz_2": float(ritz_values[1]),
                "reference_1": float(reference.eigenvalues[0]),
                "reference_2": float(reference.eigenvalues[1]),
            }
        )
    return rows


def _run_seed(config: ExperimentConfig, seed: int, root: Path) -> dict[str, object]:
    torch.manual_seed(seed)
    device = select_device(config.device)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    if config.dtype not in {"float32", "float64"}:
        raise ValueError("dtype must be float32 or float64")
    if config.sampling_stream != "cpu_generator_v2":
        raise ValueError("unknown sampling_stream")
    sample_generator = torch.Generator(device="cpu")
    sample_generator.manual_seed(seed + 1_000_003)
    dtype = torch.float64 if config.dtype == "float64" else torch.float32
    parameter_dim = len(config.parameter_lower)
    if parameter_dim != len(config.parameter_upper):
        raise ValueError("parameter_lower and parameter_upper must have equal length")
    if config.method == "block_kyfan":
        model: BlockKyFanPINN | OrderedEigenPINN | GeneralizedTracePINN | GalerkinSubspacePINN | CausalSortPINN = BlockKyFanPINN(
            width=config.width,
            hidden_layers=config.hidden_layers,
            anchor_kind=config.anchor_kind,
            anchor_scale=config.anchor_scale,
            parameter_dim=parameter_dim,
            orthogonalization=config.orthogonalization,
        ).to(device=device, dtype=dtype)
    elif config.method == "ordered_residual":
        model = OrderedEigenPINN(
            width=config.width, hidden_layers=config.hidden_layers, parameter_dim=parameter_dim
        ).to(device=device, dtype=dtype)
    elif config.method == "wang_xie_trace":
        model = GeneralizedTracePINN(
            width=config.width, hidden_layers=config.hidden_layers, parameter_dim=parameter_dim
        ).to(device=device, dtype=dtype)
    elif config.method == "dai_galerkin":
        model = GalerkinSubspacePINN(
            width=config.width, hidden_layers=config.hidden_layers, parameter_dim=parameter_dim,
            subspace_rank=config.subspace_rank,
        ).to(device=device, dtype=dtype)
    elif config.method == "causal_sort":
        model = CausalSortPINN(
            width=config.width, hidden_layers=config.hidden_layers, parameter_dim=parameter_dim
        ).to(device=device, dtype=dtype)
    else:
        raise ValueError(f"unknown method: {config.method}")
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    seed_dir = root / f"seed_{seed}"
    latest_path = seed_dir / "latest.pt"
    final_path = seed_dir / "final.pt"
    run_summary_path = seed_dir / "run_summary.json"
    if seed_dir.is_dir() and any(seed_dir.iterdir()):
        if not config.resume:
            raise FileExistsError(f"refusing to overwrite non-empty immutable run directory: {seed_dir}")
        if not latest_path.is_file():
            raise FileExistsError(f"non-empty run directory has no resumable checkpoint: {seed_dir}")
    seed_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = _config_fingerprint(config)
    source_fingerprint = _source_fingerprint()
    start_step = 0
    elapsed_before = 0.0
    finalize_only = False
    checkpoint_training_rows: list[dict[str, object]] = []
    if config.resume and latest_path.is_file():
        checkpoint = torch.load(latest_path, map_location=device, weights_only=False)
        if checkpoint.get("config_fingerprint") != fingerprint:
            raise ValueError("resume configuration fingerprint does not match checkpoint")
        if int(checkpoint.get("seed", -1)) != seed:
            raise ValueError("resume seed does not match checkpoint")
        if checkpoint.get("source_fingerprint") != source_fingerprint:
            raise ValueError("resume source fingerprint does not match current training code")
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        start_step = int(checkpoint["step"])
        elapsed_before = float(checkpoint.get("elapsed_seconds", 0.0))
        if "rng_state" not in checkpoint:
            raise ValueError("resume checkpoint has no RNG state")
        _restore_rng_state(checkpoint["rng_state"], device)
        if "sample_rng_state" not in checkpoint:
            raise ValueError("resume checkpoint has no sampling RNG state")
        sample_generator.set_state(checkpoint["sample_rng_state"])
        checkpoint_training_rows = list(checkpoint.get("training_rows", []))
        if start_step >= config.steps:
            if run_summary_path.is_file():
                return json.loads(run_summary_path.read_text())
            finalize_only = True
    start = time.perf_counter()
    initial_loss = math.nan
    final_loss = math.nan
    training_path = seed_dir / "training.csv"
    training_rows: list[dict[str, object]] = checkpoint_training_rows
    if training_rows:
        initial_loss = float(training_rows[0]["loss"])
        final_loss = float(training_rows[-1]["loss"])
    if config.resume and training_path.is_file() and not training_rows:
        with training_path.open() as handle:
            training_rows.extend(csv.DictReader(handle))
        if training_rows:
            initial_loss = float(training_rows[0]["loss"])
            final_loss = float(training_rows[-1]["loss"])
    for step in range(start_step, config.steps):
        coordinates = _sample_coordinates(
            config.parameter_batch, config.points, device, dtype, sample_generator
        )
        parameters = _sample_parameters(
            config.parameter_batch, device, config.parameter_lower, config.parameter_upper, dtype,
            sample_generator,
        )
        optimizer.zero_grad(set_to_none=True)
        output = model(coordinates, parameters)
        if isinstance(output, tuple):
            basis, eigenvalues = output
            loss = ordered_residual_loss(
                basis, coordinates, parameters, eigenvalues, config.potential_family
            ) + 1e-3 * eigenvalues.mean()
        elif config.method == "wang_xie_trace":
            loss = generalized_trace_energy(output, coordinates, parameters, config.potential_family)
        elif config.method == "dai_galerkin":
            loss = galerkin_low_energy(output, coordinates, parameters, config.potential_family)
        elif config.method == "causal_sort":
            loss = causal_sort_energy(output, coordinates, parameters, config.potential_family)
        else:
            loss = ky_fan_energy(output, coordinates, parameters, config.potential_family)
            if config.residual_weight > 0.0 and step >= int(config.steps * config.residual_start_fraction):
                h_output = apply_hamiltonian(
                    output, coordinates, parameters, config.potential_family
                )
                loss = loss + config.residual_weight * projected_residual_rms(output, h_output).square()
        if not bool(torch.isfinite(loss).detach().cpu()):
            raise FloatingPointError(f"non-finite loss at step {step}")
        loss.backward()
        optimizer.step()
        value = float(loss.detach().cpu())
        if step == start_step and math.isnan(initial_loss):
            initial_loss = value
        final_loss = value
        if step == start_step or (step + 1) % 100 == 0 or step + 1 == config.steps:
            training_rows.append({"step": step + 1, "loss": value})
        if config.checkpoint_every > 0 and (step + 1) % config.checkpoint_every == 0:
            torch.save(
                {
                    "model": model.state_dict(),
                    "optimizer": optimizer.state_dict(),
                    "step": step + 1,
                    "seed": seed,
                    "config": asdict(config),
                    "config_fingerprint": fingerprint,
                    "source_fingerprint": source_fingerprint,
                    "rng_state": _capture_rng_state(device),
                    "sample_rng_state": sample_generator.get_state(),
                    "elapsed_seconds": elapsed_before + time.perf_counter() - start,
                    "training_rows": training_rows,
                },
                latest_path,
            )
    synchronize(device)
    elapsed = elapsed_before if finalize_only else elapsed_before + time.perf_counter() - start
    if math.isnan(initial_loss):
        initial_loss = final_loss = 0.0
    completed_state = {
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "step": config.steps,
        "seed": seed,
        "config": asdict(config),
        "config_fingerprint": fingerprint,
        "source_fingerprint": source_fingerprint,
        "rng_state": _capture_rng_state(device),
        "sample_rng_state": sample_generator.get_state(),
        "elapsed_seconds": elapsed,
        "training_rows": training_rows,
    }
    if not finalize_only:
        torch.save(completed_state, final_path)
        torch.save(completed_state, latest_path)
    elif not final_path.is_file():
        # A crash may occur after the step-N periodic checkpoint but before the
        # final artifact and summary are written.  The completed latest.pt is
        # sufficient to recreate the immutable evaluation checkpoint.
        torch.save(completed_state, final_path)
    with training_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("step", "loss"))
        writer.writeheader()
        writer.writerows(training_rows)
    evaluation_start = time.perf_counter()
    rows = _evaluate(model, config, device)
    synchronize(device)
    evaluation_seconds = time.perf_counter() - evaluation_start
    with (seed_dir / "metrics.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    peak_memory: int | None = None
    current_memory: int | None = None
    if device.type == "cuda":
        peak_memory = int(torch.cuda.max_memory_allocated(device))
    elif device.type == "mps":
        current_memory = int(torch.mps.current_allocated_memory())
    run = {
        "seed": seed,
        "device": str(device),
        "initial_loss": initial_loss,
        "final_loss": final_loss,
        "elapsed_seconds": elapsed,
        "peak_memory_bytes": peak_memory,
        "current_memory_bytes": current_memory,
        "mean_projector_sine_error": sum(float(row["projector_sine_error"]) for row in rows) / len(rows),
        "objective": "ky_fan_trace" if config.method == "block_kyfan" else config.method,
        "orthogonalization": config.orthogonalization if config.method == "block_kyfan" else "not_applicable",
        "source_fingerprint": source_fingerprint,
        "final_checkpoint_sha256": hashlib.sha256(final_path.read_bytes()).hexdigest(),
        "evaluation_seconds": evaluation_seconds,
        "finalized_from_completed_checkpoint": finalize_only,
    }
    temporary_summary = run_summary_path.with_suffix(".json.tmp")
    temporary_summary.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n")
    temporary_summary.replace(run_summary_path)
    completed_state["finalized"] = True
    torch.save(completed_state, latest_path)
    return run


def run_experiment(config: ExperimentConfig) -> dict[str, object]:
    if config.steps < 1 or config.points < 4 or not config.seeds:
        raise ValueError("steps, points, and seeds must be non-empty positive values")
    if len(config.seeds) != len(set(config.seeds)):
        raise ValueError("experiment seeds must be unique")
    root = Path(config.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    runs = [_run_seed(config, seed, root) for seed in config.seeds]
    grouped: dict[str, dict[str, list[float]]] = {}
    for seed in config.seeds:
        with (root / f"seed_{seed}" / "metrics.csv").open() as handle:
            for row in csv.DictReader(handle):
                values = grouped.setdefault(row["case"], {"projector": [], "residual": []})
                values["projector"].append(float(row["projector_sine_error"]))
                values["residual"].append(float(row["residual_rms"]))
    aggregate = []
    for case, values in grouped.items():
        aggregate.append(
            {
                "case": case,
                "projector_mean": statistics.mean(values["projector"]),
                "projector_std": statistics.stdev(values["projector"]) if len(values["projector"]) > 1 else 0.0,
                "residual_mean": statistics.mean(values["residual"]),
                "residual_std": statistics.stdev(values["residual"]) if len(values["residual"]) > 1 else 0.0,
            }
        )
    with (root / "aggregate.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(aggregate[0]))
        writer.writeheader()
        writer.writerows(aggregate)
    run_errors = [float(run["mean_projector_sine_error"]) for run in runs]
    summary: dict[str, object] = {
        "status": "COMPLETE",
        "scope": "experiment_output_requires_scientific_gate_review",
        "objective_reduction": "batch_mean_of_rank_trace",
        "config_fingerprint": _config_fingerprint(config),
        "source_fingerprint": _source_fingerprint(),
        "config": asdict(config),
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else str(select_device(config.device)),
        },
        "runs": runs,
        "aggregate": aggregate,
        "mean_projector_sine_error": statistics.mean(run_errors),
        "std_projector_sine_error": statistics.stdev(run_errors) if len(run_errors) > 1 else 0.0,
    }
    (root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary

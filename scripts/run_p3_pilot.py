"""AMD ROCm P3 Pilot: 2 families × 4 methods × 3 seeds = 24 runs.

Methods:
- anchor_only: BlockKyFanPINN with fixed correct anchor, no ROM
- dual_path: Current BlockKyFanPINN (default)
- wang_xie_trace: GeneralizedTracePINN (strongest unlabeled baseline)
- p3: P3BlockKyFanPINN with ROM–Grassmann multi-chart

Evaluated on: IID hidden, exact cluster, near cluster, strict OOD points
from the V2 frozen test suite.

Saves results to results/amd_rocm_p3_pilot/
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.device import select_device, synchronize
from block_kyfan_pinn.experiment import (
    ExperimentConfig,
    _config_fingerprint,
    _source_fingerprint,
    _sample_coordinates,
    _sample_parameters,
    _evaluation_cases,
)
from block_kyfan_pinn.metrics import projector_sine_error, orthogonality_error
from block_kyfan_pinn.model import (
    BlockKyFanPINN,
    OrderedEigenPINN,
    GeneralizedTracePINN,
)
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
from block_kyfan_pinn.reference import evaluate_reference_basis, solve_reference, uniform_grid


@dataclass(frozen=True)
class PilotConfig:
    name: str
    method: str
    potential_family: str
    seed: int
    steps: int = 500
    points: int = 256
    parameter_batch: int = 4
    width: int = 64
    hidden_layers: int = 3
    learning_rate: float = 1e-3
    eval_grid_side: int = 33
    reference_cutoff: int = 8


def run_pilot_run(config: PilotConfig, output_dir: Path) -> dict:
    """Run a single pilot training + evaluation and return results."""
    torch.manual_seed(config.seed)
    device = select_device("auto")
    if device.type != "cuda":
        device = select_device("cuda")

    dtype = torch.float32
    parameter_dim = 5 if config.potential_family == "gaussian_honeycomb" else 4
    parameter_lower = (
        (0.28, 0.28, 0.20, -0.08)
        if parameter_dim == 4
        else (0.28, 0.28, 1.00, 0.18, -0.08)
    )
    parameter_upper = (
        (0.38, 0.38, 0.80, 0.08)
        if parameter_dim == 4
        else (0.38, 0.38, 4.00, 0.35, 0.08)
    )

    sample_generator = torch.Generator(device="cpu")
    sample_generator.manual_seed(config.seed + 1_000_003)

    # ── Build model ──
    if config.method == "anchor_only":
        model: torch.nn.Module = BlockKyFanPINN(
            width=config.width, hidden_layers=config.hidden_layers,
            anchor_kind="correct", anchor_scale=0.1,
            parameter_dim=parameter_dim, orthogonalization="dual_path",
        ).to(device=device, dtype=dtype)
    elif config.method == "dual_path":
        model = BlockKyFanPINN(
            width=config.width, hidden_layers=config.hidden_layers,
            anchor_kind="correct", anchor_scale=0.1,
            parameter_dim=parameter_dim, orthogonalization="dual_path",
        ).to(device=device, dtype=dtype)
    elif config.method == "wang_xie_trace":
        model = GeneralizedTracePINN(
            width=config.width, hidden_layers=config.hidden_layers,
            parameter_dim=parameter_dim,
        ).to(device=device, dtype=dtype)
    elif config.method == "p3":
        model = P3BlockKyFanPINN(
            width=config.width, hidden_layers=config.hidden_layers,
            anchor_scale=0.1, anchor_kind="correct",
            parameter_dim=parameter_dim, orthogonalization="dual_path",
            num_rom_shells=1, rom_hidden_width=32, rom_hidden_layers=2,
            num_charts=1, m_weighted=True,
            gap_monitor=True, fallback_enabled=False,
            reference_cutoff=config.reference_cutoff,
            potential_family=config.potential_family,
        ).to(device=device, dtype=dtype)
    else:
        raise ValueError(f"unknown method: {config.method}")

    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    num_params = sum(p.numel() for p in model.parameters())

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Training ──
    start_time = time.perf_counter()
    training_rows: list[dict] = []
    peak_memory = 0

    for step in range(config.steps):
        coordinates = _sample_coordinates(
            config.parameter_batch, config.points, device, dtype, sample_generator
        )
        parameters = _sample_parameters(
            config.parameter_batch, device, parameter_lower, parameter_upper, dtype, sample_generator
        )

        optimizer.zero_grad(set_to_none=True)
        output = model(coordinates, parameters)

        if isinstance(output, tuple):
            basis, eigenvalues = output
            loss = ordered_residual_loss(
                basis, coordinates, parameters, eigenvalues, config.potential_family
            ) + 1e-3 * eigenvalues.mean()
        elif config.method == "wang_xie_trace":
            loss = generalized_trace_energy(
                output, coordinates, parameters, config.potential_family
            )
        else:
            loss = ky_fan_energy(output, coordinates, parameters, config.potential_family)

        if not torch.isfinite(loss).any():
            return {"status": "FAIL", "reason": f"NaN at step {step}"}

        loss.backward()
        optimizer.step()

        value = float(loss.detach().cpu())
        if step == 0 or (step + 1) % 50 == 0 or step + 1 == config.steps:
            training_rows.append({"step": step + 1, "loss": value})

    synchronize(device)
    elapsed = time.perf_counter() - start_time
    if device.type == "cuda":
        peak_memory = int(torch.cuda.max_memory_allocated(device))

    # ── Evaluation ──
    eval_dtype = dtype  # match model dtype
    eval_coords = uniform_grid(config.eval_grid_side, dtype=eval_dtype)
    eval_rows: list[dict] = []
    projector_errors: list[float] = []
    residuals: list[float] = []
    ortho_errors: list[float] = []

    eval_cases = _evaluation_cases(config.potential_family)
    for case, values in eval_cases:
        coords = eval_coords.unsqueeze(0).to(device).requires_grad_()
        params = torch.tensor([values], device=device)
        output = model(coords, params)

        if isinstance(output, tuple):
            basis = output[0]
        elif config.method == "wang_xie_trace":
            basis = periodic_mgs(output)
        else:
            basis = output

        h_basis = apply_hamiltonian(basis, coords, params, config.potential_family)
        residual = float(projected_residual_rms(basis, h_basis).detach().cpu())
        residuals.append(residual)

        ref = solve_reference(params[0], cutoff=config.reference_cutoff, rank=2,
                              potential_family=config.potential_family)
        ref_basis = periodic_mgs(evaluate_reference_basis(ref, coords))
        proj_error = projector_sine_error(basis, ref_basis)
        projector_errors.append(proj_error)
        ortho_err = orthogonality_error(basis)
        ortho_errors.append(ortho_err)

        eval_rows.append({
            "case": case,
            "projector_sine_error": proj_error,
            "residual_rms": residual,
            "orthogonality_error": ortho_err,
        })

    mean_projector = sum(projector_errors) / len(projector_errors)
    mean_residual = sum(residuals) / len(residuals)
    mean_ortho = sum(ortho_errors) / len(ortho_errors)

    # Risk evaluation for P3
    p3_risks = {}
    if config.method == "p3":
        coords = eval_coords.unsqueeze(0).to(device).requires_grad_()
        params = torch.tensor([eval_cases[0][1]], device=device)
        try:
            risks = model.evaluate_risks(coords, params)
            p3_risks = {k: float(v) if not isinstance(v, bool) else v
                        for k, v in risks.items() if k != "external_gap"}
        except Exception:
            pass

    final_loss = float(training_rows[-1]["loss"]) if training_rows else float("nan")
    initial_loss = float(training_rows[0]["loss"]) if training_rows else float("nan")

    run_result = {
        "status": "PASS",
        "config": asdict(config),
        "device": str(device),
        "initial_loss": initial_loss,
        "final_loss": final_loss,
        "energy_reduction": initial_loss - final_loss,
        "elapsed_seconds": elapsed,
        "peak_memory_bytes": peak_memory,
        "num_parameters": num_params,
        "mean_projector_sine_error": mean_projector,
        "mean_residual_rms": mean_residual,
        "mean_orthogonality_error": mean_ortho,
        "evaluation": eval_rows,
        "training": training_rows,
        "p3_risks": p3_risks,
    }

    return run_result


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=("anchor_only", "dual_path", "wang_xie_trace", "p3", "all"))
    parser.add_argument("--family", choices=("harmonic_honeycomb", "gaussian_honeycomb", "all"))
    parser.add_argument("--seed", type=int, nargs="+")
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--output-dir", default="results/amd_rocm_p3_pilot")
    args = parser.parse_args()

    methods = (
        ["anchor_only", "dual_path", "wang_xie_trace", "p3"]
        if args.method == "all" or args.method is None
        else [args.method]
    )
    families = (
        ["harmonic_honeycomb", "gaussian_honeycomb"]
        if args.family == "all" or args.family is None
        else [args.family]
    )
    seeds = args.seed if args.seed else [42, 137, 251]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results: dict[str, dict] = {}
    total = len(methods) * len(families) * len(seeds)
    count = 0

    print(f"=== P3 Pilot: {total} runs ===")
    t0 = time.perf_counter()

    for method in methods:
        for family in families:
            for seed in seeds:
                count += 1
                name = f"{method}_{family}_seed{seed}"
                print(f"\n[{count}/{total}] {name}")

                run_config = PilotConfig(
                    name=name, method=method, potential_family=family,
                    seed=seed, steps=args.steps,
                )
                run_dir = output_dir / name

                try:
                    result = run_pilot_run(run_config, run_dir)
                except Exception as e:
                    result = {"status": "FAIL", "reason": str(e)}

                result["run_id"] = name
                all_results[name] = result

                # Save per-run
                (run_dir / "result.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2))
                # Save checkpoint
                import torch
                torch.save({"result": result}, run_dir / "checkpoint.pt")

                status = result.get("status", "UNKNOWN")
                proj = result.get("mean_projector_sine_error", float("nan"))
                print(f"  {status} projector={proj:.4f} loss={result.get('final_loss', float('nan')):.6f}")

    total_elapsed = time.perf_counter() - t0

    # ── Summary ──
    summary = {
        "total_runs": total,
        "total_elapsed": total_elapsed,
        "methods": methods,
        "families": families,
        "seeds": seeds,
        "steps": args.steps,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Per-method summary stats
    for method in methods:
        method_results = [r for n, r in all_results.items() if method in n and r.get("status") == "PASS"]
        if method_results:
            errors = [r["mean_projector_sine_error"] for r in method_results]
            summary[f"{method}_projector_mean"] = sum(errors) / len(errors)
            summary[f"{method}_projector_std"] = (
                (sum((e - summary[f"{method}_projector_mean"])**2 for e in errors) / (len(errors) - 1))**0.5
                if len(errors) > 1 else 0.0
            )
            summary[f"{method}_n_completed"] = len(method_results)
        else:
            summary[f"{method}_projector_mean"] = float("nan")
            summary[f"{method}_n_completed"] = 0

    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2))

    # ── Pilot gate ──
    ours_key = "p3_projector_mean"
    baseline_key = "wang_xie_trace_projector_mean"
    anchor_key = "anchor_only_projector_mean"

    gate_results = {
        "all_runs_completed": all(r.get("status") == "PASS" for r in all_results.values()),
        "no_nan": all(not r.get("reason", "").startswith("NaN") for r in all_results.values()),
        "m_ortho_check": all(
            r.get("mean_orthogonality_error", float("inf")) < 1e-5
            for r in all_results.values() if r.get("status") == "PASS"
        ),
    }

    if ours_key in summary and baseline_key in summary:
        gate_results["p3_vs_baseline_improvement"] = (
            (summary[baseline_key] - summary[ours_key]) / summary[baseline_key] * 100
        )
        gate_results["p3_vs_anchor_improvement"] = (
            (summary[anchor_key] - summary[ours_key]) / summary[anchor_key] * 100
        )
        gate_results["p3_better_than_baseline_15pct"] = (
            gate_results["p3_vs_baseline_improvement"] >= 15.0
        )
        gate_results["p3_better_than_anchor_20pct"] = (
            gate_results["p3_vs_anchor_improvement"] >= 20.0
        )

    gate_results["pilot_go"] = (
        gate_results.get("all_runs_completed", False)
        and gate_results.get("no_nan", False)
        and gate_results.get("m_ortho_check", False)
    )

    (output_dir / "pilot_gate.json").write_text(
        json.dumps(gate_results, ensure_ascii=False, indent=2))

    print(f"\n{'='*60}")
    print(f"Pilot complete in {total_elapsed:.0f}s")
    print(f"P3 projector: {summary.get(ours_key, 'N/A')}")
    print(f"Baseline projector: {summary.get(baseline_key, 'N/A')}")
    print(f"Anchor-only projector: {summary.get(anchor_key, 'N/A')}")
    if ours_key in summary and baseline_key in summary:
        improvement = gate_results.get("p3_vs_baseline_improvement", float("nan"))
        print(f"P3 vs baseline improvement: {improvement:.1f}%")
    print(f"Pilot GO: {gate_results['pilot_go']}")

    return 0 if gate_results["pilot_go"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

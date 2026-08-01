#!/usr/bin/env python3
"""Run the frozen P5 mechanism-attribution matrix on validation only."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import traceback
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.p5_model import P5_METHODS
from block_kyfan_pinn.suites import load_frozen_suite
from scripts.run_p3_pilot import _load_reference_cache
from scripts.run_p4_diagnostic import (
    P4_FAMILIES,
    P4Config,
    _selected_points,
    run_p4_run,
)

P5_FAMILIES = P4_FAMILIES
P5_SEEDS = (42, 137, 251)
P5_STANDARD_STEPS = 500
P5_LONG_STEPS = 665
P5_POINTS = 256
P5_PARAMETER_BATCH = 4
P5_CHECKPOINT_EVERY = 100
P5_MONITOR_EVERY = 50
P5_CANDIDATE = "p5_static_low_rom"
P5_COMPARATORS = (
    "p5_anchor",
    "p5_wide_anchor",
    "p5_long_anchor",
    "p5_unanchored_low_rom",
    "p5_highfreq_rom",
)


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _improvement(baseline: float, candidate: float) -> float:
    if not math.isfinite(baseline) or baseline <= 0 or not math.isfinite(candidate):
        return -math.inf
    return 100.0 * (baseline - candidate) / baseline


def _paired_wins(rows: object, comparator: str) -> tuple[int, list[dict[str, object]]]:
    selected = (
        [
            row
            for row in rows
            if isinstance(row, dict) and row.get("comparator") == comparator
        ]
        if isinstance(rows, list)
        else []
    )
    return sum(
        float(row.get("improvement_percent", -math.inf)) > 0 for row in selected
    ), selected


def build_p5_gate(summary: dict[str, object]) -> dict[str, object]:
    """Freeze the structural-ROM mechanism and safety decision."""

    candidate = float(
        summary.get(f"{P5_CANDIDATE}_near_cluster_projector_mean", math.inf)
    )
    overall = {
        comparator: _improvement(
            float(summary.get(f"{comparator}_near_cluster_projector_mean", math.inf)),
            candidate,
        )
        for comparator in P5_COMPARATORS
    }
    family = {
        comparator: {
            name: _improvement(
                float(
                    summary.get(
                        f"{comparator}_{name}_near_cluster_projector_mean", math.inf
                    )
                ),
                float(
                    summary.get(
                        f"{P5_CANDIDATE}_{name}_near_cluster_projector_mean",
                        math.inf,
                    )
                ),
            )
            for name in P5_FAMILIES
        }
        for comparator in P5_COMPARATORS
    }
    pair_counts: dict[str, int] = {}
    pair_rows: dict[str, list[dict[str, object]]] = {}
    for comparator in P5_COMPARATORS:
        pair_counts[comparator], pair_rows[comparator] = _paired_wins(
            summary.get("paired_comparisons", []), comparator
        )

    parameter_ratios: dict[str, float] = {}
    rom_control_counts_match = True
    for name in P5_FAMILIES:
        low = int(summary.get(f"{P5_CANDIDATE}_{name}_num_parameters", -1))
        wide = int(summary.get(f"p5_wide_anchor_{name}_num_parameters", -2))
        parameter_ratios[name] = abs(wide - low) / low if low > 0 else math.inf
        for control in ("p5_unanchored_low_rom", "p5_highfreq_rom"):
            rom_control_counts_match = (
                rom_control_counts_match
                and int(summary.get(f"{control}_{name}_num_parameters", -2)) == low
            )

    low_time = float(summary.get(f"{P5_CANDIDATE}_training_time_mean", math.inf))
    long_time = float(summary.get("p5_long_anchor_training_time_mean", math.inf))
    anchor_time = float(summary.get("p5_anchor_training_time_mean", math.inf))
    time_match_ratio = long_time / low_time if low_time > 0 else math.inf
    parameter_overhead_values: list[float] = []
    for name in P5_FAMILIES:
        candidate_count = int(summary.get(f"{P5_CANDIDATE}_{name}_num_parameters", -1))
        anchor_count = int(summary.get(f"p5_anchor_{name}_num_parameters", 0))
        parameter_overhead_values.append(
            candidate_count / anchor_count
            if candidate_count > 0 and anchor_count > 0
            else math.inf
        )
    parameter_overhead = max(parameter_overhead_values, default=math.inf)
    time_overhead = low_time / anchor_time if anchor_time > 0 else math.inf
    best_safe_gap = min(
        float(summary.get(f"{method}_gap_scan_projector_mean", math.inf))
        for method in ("p5_anchor", "p5_wide_anchor", "p5_long_anchor")
    )
    candidate_gap = float(
        summary.get(f"{P5_CANDIDATE}_gap_scan_projector_mean", math.inf)
    )

    finite_values = [
        candidate,
        candidate_gap,
        best_safe_gap,
        low_time,
        long_time,
        anchor_time,
        *overall.values(),
        *(value for values in family.values() for value in values.values()),
    ]
    gate: dict[str, object] = {
        "all_runs_completed": int(summary.get("total_runs", 0)) == 36
        and int(summary.get("completed_runs", 0)) == 36
        and int(summary.get("failed_runs", 36)) == 0,
        "finite_metrics": all(_finite(value) for value in finite_values),
        "orthogonality_pass": float(
            summary.get("maximum_orthogonality_error", math.inf)
        )
        < 1e-4,
        "gram_condition_pass": float(summary.get("maximum_gram_condition", math.inf))
        < 1e8,
        "candidate_improvement_percent": overall,
        "candidate_at_least_5pct_better_than_each_control": all(
            value >= 5.0 for value in overall.values()
        ),
        "family_improvement_percent": family,
        "candidate_better_in_each_family": all(
            value > 0.0 for values in family.values() for value in values.values()
        ),
        "paired_positive_counts": pair_counts,
        "paired_comparisons": pair_rows,
        "at_least_5_of_6_pairs_win_each_control": all(
            len(pair_rows[name]) == 6 and pair_counts[name] >= 5
            for name in P5_COMPARATORS
        ),
        "wide_parameter_mismatch_ratio": parameter_ratios,
        "wide_parameter_match_within_2pct": all(
            value <= 0.02 for value in parameter_ratios.values()
        ),
        "rom_control_parameter_counts_match": rom_control_counts_match,
        "long_to_rom_time_ratio": time_match_ratio,
        "long_compute_match_within_15pct": 0.85 <= time_match_ratio <= 1.15,
        "candidate_parameter_overhead_ratio": parameter_overhead,
        "candidate_parameter_overhead_at_most_30pct": parameter_overhead <= 1.30,
        "candidate_time_overhead_ratio": time_overhead,
        "candidate_time_overhead_at_most_50pct": time_overhead <= 1.50,
        "candidate_gap_scan_error": candidate_gap,
        "best_non_rom_gap_scan_error": best_safe_gap,
        "gap_scan_non_regression": candidate_gap <= 1.02 * best_safe_gap,
    }
    mechanism_keys = (
        "all_runs_completed",
        "finite_metrics",
        "orthogonality_pass",
        "gram_condition_pass",
        "candidate_at_least_5pct_better_than_each_control",
        "candidate_better_in_each_family",
        "at_least_5_of_6_pairs_win_each_control",
        "wide_parameter_match_within_2pct",
        "rom_control_parameter_counts_match",
        "long_compute_match_within_15pct",
        "candidate_parameter_overhead_at_most_30pct",
        "candidate_time_overhead_at_most_50pct",
    )
    gate["mechanism_go"] = all(bool(gate[key]) for key in mechanism_keys)
    gate["promotion_go"] = bool(gate["mechanism_go"]) and bool(
        gate["gap_scan_non_regression"]
    )
    return gate


def build_p5_smoke_gate(summary: dict[str, object]) -> dict[str, object]:
    total = int(summary.get("total_runs", 0))
    gate = {
        "all_runs_completed": total == 12
        and int(summary.get("completed_runs", 0)) == total
        and int(summary.get("failed_runs", total)) == 0,
        "orthogonality_pass": float(
            summary.get("maximum_orthogonality_error", math.inf)
        )
        < 5e-4,
        "gram_condition_pass": float(summary.get("maximum_gram_condition", math.inf))
        < 1e8,
    }
    gate["engineering_pass"] = all(gate.values())
    return gate


def _aggregate(
    results: list[dict[str, object]], failures: list[dict[str, object]], protocol: str
) -> dict[str, object]:
    summary: dict[str, object] = {
        "scope": "v2_validation_p5_mechanism_attribution_not_final_test",
        "protocol": protocol,
        "total_runs": len(P5_METHODS)
        * len(P5_FAMILIES)
        * (len(P5_SEEDS) if protocol == "promotion" else 1),
        "completed_runs": len(results),
        "failed_runs": len(failures),
        "methods": list(P5_METHODS),
        "families": list(P5_FAMILIES),
        "seeds": list(P5_SEEDS if protocol == "promotion" else (42,)),
        "steps": {
            method: (
                5
                if protocol == "smoke"
                else P5_LONG_STEPS
                if method == "p5_long_anchor"
                else P5_STANDARD_STEPS
            )
            for method in P5_METHODS
        },
        "maximum_orthogonality_error": max(
            (float(row["maximum_orthogonality_error"]) for row in results),
            default=math.inf,
        ),
        "maximum_gram_condition": max(
            (float(row["maximum_gram_condition"]) for row in results),
            default=math.inf,
        ),
        "failures": failures,
    }
    for method in P5_METHODS:
        method_rows = [row for row in results if row["config"]["method"] == method]
        for split in ("near_cluster", "gap_scan"):
            values = [
                float(row["split_projector_mean"][split])
                for row in method_rows
                if split in row["split_projector_mean"]
            ]
            summary[f"{method}_{split}_projector_mean"] = (
                statistics.mean(values) if values else math.inf
            )
        summary[f"{method}_training_time_mean"] = (
            statistics.mean(float(row["elapsed_seconds"]) for row in method_rows)
            if method_rows
            else math.inf
        )
        for family in P5_FAMILIES:
            family_rows = [
                row
                for row in method_rows
                if row["config"]["potential_family"] == family
            ]
            near = [
                float(row["split_projector_mean"]["near_cluster"])
                for row in family_rows
                if "near_cluster" in row["split_projector_mean"]
            ]
            summary[f"{method}_{family}_near_cluster_projector_mean"] = (
                statistics.mean(near) if near else math.inf
            )
            counts = {int(row["num_parameters"]) for row in family_rows}
            summary[f"{method}_{family}_num_parameters"] = (
                counts.pop() if len(counts) == 1 else -1
            )

    pairs: list[dict[str, object]] = []
    seeds = P5_SEEDS if protocol == "promotion" else (42,)
    for comparator in P5_COMPARATORS:
        for family in P5_FAMILIES:
            for seed in seeds:
                indexed = {
                    str(row["config"]["method"]): row
                    for row in results
                    if row["config"]["potential_family"] == family
                    and int(row["config"]["seed"]) == seed
                }
                if P5_CANDIDATE not in indexed or comparator not in indexed:
                    continue
                baseline = float(
                    indexed[comparator]["split_projector_mean"]["near_cluster"]
                )
                candidate = float(
                    indexed[P5_CANDIDATE]["split_projector_mean"]["near_cluster"]
                )
                pairs.append(
                    {
                        "comparator": comparator,
                        "family": family,
                        "seed": seed,
                        "baseline_error": baseline,
                        "candidate_error": candidate,
                        "improvement_percent": _improvement(baseline, candidate),
                    }
                )
    summary["paired_comparisons"] = pairs
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", choices=("smoke", "promotion"), default="smoke")
    parser.add_argument(
        "--device", choices=("auto", "cpu", "mps", "cuda", "rocm"), default="auto"
    )
    parser.add_argument(
        "--suite", type=Path, default=Path("benchmarks/v2_validation.json")
    )
    parser.add_argument(
        "--reference-cache", type=Path, default=Path("data/v2_validation_references.pt")
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    suite, suite_hash = load_frozen_suite(args.suite)
    if suite.get("purpose") != "pilot_and_hyperparameter_selection":
        raise ValueError("P5 may use validation only, never frozen final")
    max_points = 1 if args.protocol == "smoke" else 0
    selected = _selected_points(suite, max_points)
    selected_suite = dict(suite)
    selected_suite["points"] = selected
    point_ids = {str(point["id"]) for point in selected}
    references, cache_hash = _load_reference_cache(
        args.reference_cache,
        suite_id=str(suite["suite_id"]),
        suite_hash=suite_hash,
        point_ids=point_ids,
        grid_side=33,
        cutoff=24,
    )
    output_dir = args.output_dir or Path(
        "results/p5_smoke" if args.protocol == "smoke" else "results/p5_promotion"
    )
    seeds = (42,) if args.protocol == "smoke" else P5_SEEDS
    results: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    total = len(P5_METHODS) * len(P5_FAMILIES) * len(seeds)
    for method in P5_METHODS:
        for family in P5_FAMILIES:
            for seed in seeds:
                run_id = f"{method}_{family}_seed{seed}"
                print(
                    f"[{len(results) + len(failures) + 1}/{total}] {run_id}", flush=True
                )
                config = P4Config(
                    method=method,
                    potential_family=family,
                    seed=seed,
                    protocol=f"p5_{args.protocol}",
                    device=args.device,
                    steps=(
                        5
                        if args.protocol == "smoke"
                        else P5_LONG_STEPS
                        if method == "p5_long_anchor"
                        else P5_STANDARD_STEPS
                    ),
                    points=64 if args.protocol == "smoke" else P5_POINTS,
                    parameter_batch=1
                    if args.protocol == "smoke"
                    else P5_PARAMETER_BATCH,
                    checkpoint_every=5
                    if args.protocol == "smoke"
                    else P5_CHECKPOINT_EVERY,
                    monitor_every=5 if args.protocol == "smoke" else P5_MONITOR_EVERY,
                )
                try:
                    results.append(
                        run_p4_run(
                            config,
                            output_dir / run_id,
                            suite_payload=selected_suite,
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
                        "config": asdict(config),
                    }
                    run_dir = output_dir / run_id
                    run_dir.mkdir(parents=True, exist_ok=True)
                    (run_dir / "failure.json").write_text(
                        json.dumps(failure, ensure_ascii=False, indent=2) + "\n"
                    )
                    failures.append(failure)

    summary = _aggregate(results, failures, args.protocol)
    gate = (
        build_p5_gate(summary)
        if args.protocol == "promotion"
        else build_p5_smoke_gate(summary)
    )
    summary["gate"] = gate
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    (output_dir / "diagnostic_gate.json").write_text(
        json.dumps(gate, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(gate, ensure_ascii=False, indent=2))
    passed = (
        gate["promotion_go"]
        if args.protocol == "promotion"
        else gate["engineering_pass"]
    )
    return 0 if bool(passed) else 2


if __name__ == "__main__":
    raise SystemExit(main())

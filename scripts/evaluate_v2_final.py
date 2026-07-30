#!/usr/bin/env python3
"""Evaluate all promoted pilot checkpoints once on the frozen V2 final suite."""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import statistics
import sys
from dataclasses import replace
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.device import select_device
from block_kyfan_pinn.experiment import _source_fingerprint
from block_kyfan_pinn.suites import load_frozen_suite
from scripts.run_p3_pilot import (
    PILOT_FAMILIES,
    PILOT_METHODS,
    PilotConfig,
    _config_fingerprint,
    _evaluate_suite,
    _load_completed_result,
    _load_reference_cache,
    build_pilot_gate,
    build_pilot_model,
)


def _load_promoted_runs(pilot_dir: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Recompute the promotion decision without reading the final-test suite."""

    summary_path = pilot_dir / "summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError(f"pilot summary is missing: {summary_path}")
    recorded_summary = json.loads(summary_path.read_text())
    validation_suite_hash = str(recorded_summary.get("suite_sha256", ""))
    validation_cache_hash = str(recorded_summary.get("reference_cache_sha256", ""))
    seeds = recorded_summary.get("seeds")
    if not isinstance(seeds, list) or len(seeds) != 3:
        raise ValueError("promotion requires exactly three recorded pilot seeds")

    current_source = _source_fingerprint()
    results: list[dict[str, object]] = []
    for method in PILOT_METHODS:
        for family in PILOT_FAMILIES:
            for raw_seed in seeds:
                seed = int(raw_seed)
                run_dir = pilot_dir / f"{method}_{family}_seed{seed}"
                result_path = run_dir / "result.json"
                final_path = run_dir / "final.pt"
                if not result_path.is_file():
                    raise FileNotFoundError(f"pilot result is missing: {result_path}")
                raw_result = json.loads(result_path.read_text())
                config_values = raw_result.get("config")
                if not isinstance(config_values, dict):
                    raise ValueError(f"pilot result has no config: {result_path}")
                config = PilotConfig(**config_values)
                if (config.method, config.potential_family, config.seed) != (
                    method,
                    family,
                    seed,
                ):
                    raise ValueError(f"pilot run identity mismatch: {run_dir}")
                fingerprint = _config_fingerprint(
                    config, validation_suite_hash, validation_cache_hash
                )
                result = _load_completed_result(
                    result_path,
                    final_path,
                    config_fingerprint=fingerprint,
                    source_fingerprint=current_source,
                    suite_hash=validation_suite_hash,
                    cache_hash=validation_cache_hash,
                )
                if result is None:
                    raise ValueError(f"pilot run is incomplete: {run_dir}")
                results.append(result)

    recomputed: dict[str, object] = {
        "total_runs": 24,
        "completed_runs": len(results),
        "failed_runs": 0,
        "maximum_orthogonality_error": max(
            float(result["maximum_orthogonality_error"]) for result in results
        ),
    }
    for method in PILOT_METHODS:
        values = [
            float(result["mean_projector_sine_error"])
            for result in results
            if result["config"]["method"] == method
        ]
        recomputed[f"{method}_projector_mean"] = statistics.mean(values)
        primary_values = [
            float(result["split_projector_mean"]["near_cluster"])
            for result in results
            if result["config"]["method"] == method
            and "near_cluster" in result["split_projector_mean"]
        ]
        recomputed[f"{method}_near_cluster_projector_mean"] = statistics.mean(
            primary_values
        )
        for family in PILOT_FAMILIES:
            family_values = [
                float(result["mean_projector_sine_error"])
                for result in results
                if result["config"]["method"] == method
                and result["config"]["potential_family"] == family
            ]
            recomputed[f"{method}_{family}_projector_mean"] = statistics.mean(
                family_values
            )
            family_primary_values = [
                float(result["split_projector_mean"]["near_cluster"])
                for result in results
                if result["config"]["method"] == method
                and result["config"]["potential_family"] == family
                and "near_cluster" in result["split_projector_mean"]
            ]
            recomputed[
                f"{method}_{family}_near_cluster_projector_mean"
            ] = statistics.mean(family_primary_values)
    gate = build_pilot_gate(recomputed)
    if not bool(gate["pilot_go"]):
        raise RuntimeError(
            "pilot promotion gate is STOP; the frozen final suite must remain unopened"
        )
    return results, gate


def _aggregate(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    keys = sorted(
        {
            (str(row["method"]), str(row["family"]), str(row["split"]))
            for row in rows
        }
    )
    for method, family, split in keys:
        selected = [
            row
            for row in rows
            if (row["method"], row["family"], row["split"])
            == (method, family, split)
        ]
        seed_means = []
        for seed in sorted({int(row["seed"]) for row in selected}):
            values = [
                float(row["projector_sine_error"])
                for row in selected
                if int(row["seed"]) == seed
            ]
            seed_means.append(statistics.mean(values))
        output.append(
            {
                "method": method,
                "family": family,
                "split": split,
                "point_rows": len(selected),
                "seed_count": len(seed_means),
                "projector_error_seed_mean": statistics.mean(seed_means),
                "projector_error_seed_std": (
                    statistics.stdev(seed_means) if len(seed_means) > 1 else 0.0
                ),
                "projector_error_maximum": max(
                    float(row["projector_sine_error"]) for row in selected
                ),
            }
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-dir", type=Path, default=Path("results/p3_v2_pilot"))
    parser.add_argument("--suite", type=Path, default=Path("benchmarks/v2_frozen_test.json"))
    parser.add_argument(
        "--reference-cache",
        type=Path,
        default=Path("data/v2_frozen_test_references.pt"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results/p3_v2_final"))
    parser.add_argument("--device", default="auto", choices=("auto", "cuda", "rocm"))
    args = parser.parse_args()

    pilot_results, gate = _load_promoted_runs(args.pilot_dir)
    suite_payload, suite_hash = load_frozen_suite(args.suite)
    if suite_payload.get("purpose") != "final_test_do_not_use_for_model_selection":
        raise ValueError("final evaluator requires the frozen final-test suite")
    point_ids = {str(point["id"]) for point in suite_payload["points"]}
    references, cache_hash = _load_reference_cache(
        args.reference_cache,
        suite_id=str(suite_payload["suite_id"]),
        suite_hash=suite_hash,
        point_ids=point_ids,
        grid_side=33,
        cutoff=24,
    )
    device = select_device(args.device)
    all_rows: list[dict[str, object]] = []
    checkpoints: list[dict[str, object]] = []

    for index, result in enumerate(pilot_results, start=1):
        config_values = result["config"]
        config = PilotConfig(**config_values)
        evaluation_config = replace(config, device=args.device)
        run_id = f"{config.method}_{config.potential_family}_seed{config.seed}"
        final_path = args.pilot_dir / run_id / "final.pt"
        state = torch.load(final_path, map_location=device, weights_only=False)
        if state.get("config_fingerprint") != result.get("config_fingerprint"):
            raise ValueError(f"checkpoint config binding mismatch: {final_path}")
        if state.get("source_fingerprint") != _source_fingerprint():
            raise ValueError(f"checkpoint source binding mismatch: {final_path}")
        model = build_pilot_model(
            config.method,
            potential_family=config.potential_family,
            width=config.width,
            hidden_layers=config.hidden_layers,
            device=device,
            dtype=torch.float32,
        )
        model.load_state_dict(state["model"])
        model.eval()
        family_points = [
            point
            for point in suite_payload["points"]
            if point["family"] == config.potential_family
        ]
        print(f"[{index}/24] evaluating {run_id}", flush=True)
        rows = _evaluate_suite(
            model, evaluation_config, device, family_points, references
        )
        for row in rows:
            row.update({"run_id": run_id, "method": config.method, "seed": config.seed})
        all_rows.extend(rows)
        checkpoints.append(
            {
                "run_id": run_id,
                "checkpoint_sha256": result["final_checkpoint_sha256"],
                "config_fingerprint": result["config_fingerprint"],
            }
        )

    if not all_rows or not all(math.isfinite(float(row["projector_sine_error"])) for row in all_rows):
        raise RuntimeError("final evaluation produced no finite result rows")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "per_parameter.csv"
    with csv_path.open("w", newline="") as handle:
        fieldnames = sorted({key for row in all_rows for key in row})
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    summary = {
        "status": "COMPLETE",
        "scope": "v2_frozen_final_test_opened_after_recomputed_pilot_go",
        "pilot_gate": gate,
        "suite_id": suite_payload["suite_id"],
        "suite_sha256": suite_hash,
        "reference_cache_sha256": cache_hash,
        "checkpoint_count": len(checkpoints),
        "row_count": len(all_rows),
        "checkpoints": checkpoints,
        "aggregate": _aggregate(all_rows),
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "device": str(device),
            "cuda": torch.version.cuda,
            "hip": getattr(torch.version, "hip", None),
        },
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({key: summary[key] for key in ("status", "row_count", "aggregate")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

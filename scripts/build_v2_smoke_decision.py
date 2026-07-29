"""Deterministically rebuild the V2 dual-path versus stop-gradient smoke gate.

The gate is intentionally a post-hoc, reproducible mechanism screen, not a
publication endpoint or a preregistered statistical test.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path


THRESHOLDS = {
    "maximum_dual_projector_mean": 0.18,
    "minimum_relative_reduction": 0.20,
    "minimum_seed_point_win_rate": 0.80,
    "maximum_training_time_multiplier": 1.60,
    "maximum_orthogonality_error": 1e-5,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_rows(
    root: Path, seeds: list[int], suite_hash: str, suite_id: str,
    family: str, expected_ids: set[str],
    expected_config_fingerprint: str | None = None,
    expected_source_fingerprint: str | None = None,
    expected_checkpoint_hashes: dict[int, str] | None = None,
) -> tuple[dict[tuple[int, str], float], float, list[Path], set[str]]:
    values: dict[tuple[int, str], float] = {}
    maximum_orthogonality = 0.0
    inputs: list[Path] = []
    checkpoint_hashes: set[str] = set()
    for seed in seeds:
        seed_dir = root / f"seed_{seed}"
        summary_path = seed_dir / "summary.json"
        rows_path = seed_dir / "per_parameter.csv"
        summary = json.loads(summary_path.read_text())
        if summary.get("suite_sha256") != suite_hash or summary.get("suite_id") != suite_id:
            raise ValueError(f"suite hash mismatch in {summary_path}")
        if summary.get("potential_family") != family:
            raise ValueError(f"potential family mismatch in {summary_path}")
        if int(summary.get("checkpoint_seed", -1)) != seed:
            raise ValueError(f"checkpoint seed mismatch in {summary_path}")
        if (
            expected_config_fingerprint is not None
            and summary.get("checkpoint_config_fingerprint") != expected_config_fingerprint
        ):
            raise ValueError(f"checkpoint config fingerprint mismatch in {summary_path}")
        if (
            expected_source_fingerprint is not None
            and summary.get("checkpoint_source_fingerprint") != expected_source_fingerprint
        ):
            raise ValueError(f"checkpoint source fingerprint mismatch in {summary_path}")
        checkpoint_hash = str(summary.get("checkpoint_sha256", ""))
        if len(checkpoint_hash) != 64 or checkpoint_hash in checkpoint_hashes:
            raise ValueError(f"missing or duplicate checkpoint SHA-256 in {summary_path}")
        if expected_checkpoint_hashes is not None and checkpoint_hash != expected_checkpoint_hashes.get(seed):
            raise ValueError(f"evaluation checkpoint is not the training final checkpoint in {summary_path}")
        checkpoint_hashes.add(checkpoint_hash)
        if int(summary.get("point_count", -1)) != len(expected_ids):
            raise ValueError(f"incomplete point_count in {summary_path}")
        with rows_path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        identities = [str(row["id"]) for row in rows]
        if len(identities) != len(set(identities)):
            raise ValueError(f"duplicate point identity in {rows_path}")
        current_ids = set(identities)
        if len(rows) != len(expected_ids) or current_ids != expected_ids:
            raise ValueError(f"point identity set is incomplete or selected in {rows_path}")
        for row in rows:
            error = float(row["projector_sine_error"])
            orthogonality = float(row["orthogonality_error"])
            if not math.isfinite(error) or not math.isfinite(orthogonality):
                raise ValueError(f"non-finite metric in {rows_path}")
            values[(seed, str(row["id"]))] = error
            maximum_orthogonality = max(maximum_orthogonality, orthogonality)
        inputs.extend((summary_path, rows_path))
    return values, maximum_orthogonality, inputs, checkpoint_hashes


def _validate_ab_configs(dual: dict[str, object], stop: dict[str, object]) -> str:
    dual_config = dual.get("config")
    stop_config = stop.get("config")
    if not isinstance(dual_config, dict) or not isinstance(stop_config, dict):
        raise ValueError("training summaries must embed complete configs")
    if dual_config.get("orthogonalization") != "dual_path":
        raise ValueError("dual arm is not dual_path")
    if stop_config.get("orthogonalization") != "stop_gradient":
        raise ValueError("stop arm is not stop_gradient")
    allowed = {"name", "output_dir", "orthogonalization"}
    for key in set(dual_config) | set(stop_config):
        if key not in allowed and dual_config.get(key) != stop_config.get(key):
            raise ValueError(f"A/B training config mismatch outside treatment for {key}")
    family = str(dual_config.get("potential_family", ""))
    if not family:
        raise ValueError("training config has no potential_family")
    return family


def _training_seed_set(training: dict[str, object], label: str) -> list[int]:
    config = training.get("config")
    runs = training.get("runs")
    if not isinstance(config, dict) or not isinstance(runs, list):
        raise ValueError(f"{label} training summary must embed config and runs")
    config_seeds = [int(seed) for seed in config.get("seeds", [])]
    run_seeds = [int(run["seed"]) for run in runs if isinstance(run, dict) and "seed" in run]
    if (
        not config_seeds
        or len(config_seeds) != len(set(config_seeds))
        or len(run_seeds) != len(runs)
        or len(run_seeds) != len(set(run_seeds))
        or set(run_seeds) != set(config_seeds)
    ):
        raise ValueError(f"{label} training runs must exactly match config.seeds")
    return sorted(config_seeds)


def _training_config_fingerprint(training: dict[str, object], label: str) -> str:
    config = training.get("config")
    if not isinstance(config, dict):
        raise ValueError(f"{label} training summary has no embedded config")
    computed = hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    recorded = training.get("config_fingerprint")
    if recorded is not None and recorded != computed:
        raise ValueError(f"{label} training config fingerprint is invalid")
    return computed


def _training_checkpoint_hashes(
    training: dict[str, object], label: str, allow_legacy_unbound: bool,
) -> dict[int, str] | None:
    runs = training.get("runs")
    if not isinstance(runs, list):
        raise ValueError(f"{label} training summary has no runs")
    hashes: dict[int, str] = {}
    missing = False
    for run in runs:
        if not isinstance(run, dict) or "seed" not in run:
            raise ValueError(f"{label} training run is malformed")
        value = run.get("final_checkpoint_sha256")
        if value is None:
            missing = True
            continue
        digest = str(value)
        if len(digest) != 64 or digest in hashes.values():
            raise ValueError(f"{label} training final checkpoint SHA-256 is invalid or duplicated")
        hashes[int(run["seed"])] = digest
    if missing:
        if hashes:
            raise ValueError(f"{label} training summary mixes bound and unbound checkpoints")
        if not allow_legacy_unbound:
            raise ValueError(
                f"{label} training summary has no final checkpoint hashes; "
                "use the explicit legacy-unbound flag only for archived evidence"
            )
        return None
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--dual-training", type=Path, required=True)
    parser.add_argument("--stop-training", type=Path, required=True)
    parser.add_argument("--dual-eval", type=Path, required=True)
    parser.add_argument("--stop-eval", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-legacy-unbound-checkpoints", action="store_true",
        help="allow archived summaries without per-seed final checkpoint SHA; never use for new pilots",
    )
    args = parser.parse_args()

    suite_hash = _sha256(args.suite)
    suite = json.loads(args.suite.read_text())
    dual_training = json.loads(args.dual_training.read_text())
    stop_training = json.loads(args.stop_training.read_text())
    family = _validate_ab_configs(dual_training, stop_training)
    dual_seeds = _training_seed_set(dual_training, "dual")
    stop_seeds = _training_seed_set(stop_training, "stop-gradient")
    if dual_seeds != stop_seeds:
        raise ValueError("training summaries must contain the same unique seed set")
    seeds = dual_seeds
    dual_config_fingerprint = _training_config_fingerprint(dual_training, "dual")
    stop_config_fingerprint = _training_config_fingerprint(stop_training, "stop-gradient")
    dual_checkpoint_hashes = _training_checkpoint_hashes(
        dual_training, "dual", args.allow_legacy_unbound_checkpoints
    )
    stop_checkpoint_hashes = _training_checkpoint_hashes(
        stop_training, "stop-gradient", args.allow_legacy_unbound_checkpoints
    )
    if (dual_checkpoint_hashes is None) != (stop_checkpoint_hashes is None):
        raise ValueError("A/B arms must use the same checkpoint-binding mode")
    dual_source_fingerprint = dual_training.get("source_fingerprint")
    stop_source_fingerprint = stop_training.get("source_fingerprint")
    expected_ids = {
        str(point["id"]) for point in suite["points"] if point.get("family") == family
    }
    if not expected_ids:
        raise ValueError(f"suite has no points for {family}")

    suite_id = str(suite.get("suite_id", ""))
    dual, dual_orth, dual_inputs, dual_checkpoints = _load_rows(
        args.dual_eval, seeds, suite_hash, suite_id, family, expected_ids,
        dual_config_fingerprint,
        str(dual_source_fingerprint) if dual_source_fingerprint is not None else None,
        dual_checkpoint_hashes,
    )
    stop, stop_orth, stop_inputs, stop_checkpoints = _load_rows(
        args.stop_eval, seeds, suite_hash, suite_id, family, expected_ids,
        stop_config_fingerprint,
        str(stop_source_fingerprint) if stop_source_fingerprint is not None else None,
        stop_checkpoint_hashes,
    )
    if dual_checkpoints & stop_checkpoints:
        raise ValueError("the same checkpoint was reused across A/B arms")
    if set(dual) != set(stop):
        raise ValueError("dual and stop-gradient evaluations are not exactly paired")
    dual_values = [dual[key] for key in sorted(dual)]
    stop_values = [stop[key] for key in sorted(stop)]
    dual_mean = statistics.mean(dual_values)
    stop_mean = statistics.mean(stop_values)
    relative_reduction = (stop_mean - dual_mean) / max(abs(stop_mean), 1e-12)
    wins = sum(dual[key] < stop[key] for key in dual)
    win_rate = wins / len(dual)
    dual_seconds = sum(float(run["elapsed_seconds"]) for run in dual_training["runs"])
    stop_seconds = sum(float(run["elapsed_seconds"]) for run in stop_training["runs"])
    time_multiplier = dual_seconds / stop_seconds
    maximum_orthogonality = max(dual_orth, stop_orth)

    checks = {
        "dual_mean": dual_mean <= THRESHOLDS["maximum_dual_projector_mean"],
        "relative_reduction": relative_reduction >= THRESHOLDS["minimum_relative_reduction"],
        "paired_win_rate": win_rate >= THRESHOLDS["minimum_seed_point_win_rate"],
        "training_time_multiplier": time_multiplier <= THRESHOLDS["maximum_training_time_multiplier"],
        "orthogonality": maximum_orthogonality <= THRESHOLDS["maximum_orthogonality_error"],
    }
    inputs = [args.suite, args.dual_training, args.stop_training, *dual_inputs, *stop_inputs]
    result = {
        "status": "SMOKE_GATE_PASS_NOT_PAPER_RESULT" if all(checks.values()) else "SMOKE_GATE_STOP",
        "scope": "mechanism_falsification_only",
        "suite_id": suite.get("suite_id"),
        "suite_sha256": suite_hash,
        "seeds": seeds,
        "paired_comparisons": len(dual),
        "checkpoint_binding": (
            "legacy_unbound_explicit" if dual_checkpoint_hashes is None else "exact_final_sha256_per_seed"
        ),
        "thresholds_locked_for_reproducible_rebuild": THRESHOLDS,
        "threshold_timing": (
            "Locked after the original smoke results were observed; this is a reproducible "
            "post-hoc engineering gate, not a preregistered statistical endpoint."
        ),
        "checks": checks,
        "metrics": {
            "dual_projector_mean": dual_mean,
            "stop_gradient_projector_mean": stop_mean,
            "relative_reduction": relative_reduction,
            "wins": wins,
            "win_rate": win_rate,
            "dual_training_seconds_total": dual_seconds,
            "stop_gradient_training_seconds_total": stop_seconds,
            "training_time_multiplier": time_multiplier,
            "maximum_orthogonality_error": maximum_orthogonality,
        },
        "objective_note": (
            "The archived 2026-07-29 smoke used rank-normalized Ky Fan trace. "
            "For fixed rank two this has the same minimizer as the true trace; "
            "current code reports and optimizes the true rank sum."
        ),
        "limitations": [
            "Apple MPS only",
            "three seeds and one trained potential family",
            "not a preregistered final test",
            "cannot support a journal claim without the CUDA two-family matrix",
            *(
                ["archived training summaries lack per-seed final checkpoint SHA binding"]
                if dual_checkpoint_hashes is None else []
            ),
        ],
        "input_sha256": {str(path): _sha256(path) for path in inputs},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())

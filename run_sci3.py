"""Staged SCI-Q3 experiment entry point with explicit promotion gates."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from block_kyfan_pinn.experiment import ExperimentConfig, pilot_gate, run_experiment


CONFIGS = Path("configs")
SUITE = Path("benchmarks/sci3_frozen_test_v1.json")
VALIDATION_SUITE = Path("benchmarks/sci3_validation_v1.json")
REFERENCE_CACHE = Path("data/sci3_frozen_test_references.pt")
LEGACY_PROTOCOL_WARNING = (
    "SCI-Q3 V1 has been retired: its OOD split overlaps training, its near-crossing "
    "cases do not enforce a small internal gap, and its square plane-wave cutoff can "
    "create pseudo-splitting. Use the falsification V2 smoke gate and generate a new "
    "frozen formal V2 suite before starting publication experiments."
)
PILOTS = (
    "sci3_gaussian_pilot_ours_3seed.json",
    "sci3_gaussian_pilot_no_anchor_3seed.json",
    "sci3_gaussian_pilot_ordered_3seed.json",
)
FORMAL = tuple(
    f"sci3_{family}_{method}_10seed.json"
    for family in ("harmonic", "gaussian")
    for method in ("ours", "no_anchor", "ordered", "wang_xie", "dai_galerkin", "causal_sort")
)
SUPERVISED = (
    "sci3_harmonic_supervised_grassmann_10seed.json",
    "sci3_gaussian_supervised_grassmann_10seed.json",
)
ANCHOR_VALIDATION = tuple(f"sci3_anchor_validation_{value}.json" for value in ("040", "060", "080", "100"))
ABLATIONS = tuple(
    f"sci3_{family}_{suffix}.json"
    for family in ("harmonic", "gaussian")
    for suffix in (
        "wrong_anchor_5seed", "random_anchor_5seed", "budget_half_3seed",
        "budget_double_3seed", "float64_3seed",
    )
)


def _run_configs(names: tuple[str, ...]) -> None:
    for name in names:
        print(f"\n=== {name} ===", flush=True)
        run_experiment(ExperimentConfig.from_json(CONFIGS / name))


def _gaussian_gate() -> tuple[bool, str]:
    summaries = {}
    ours_summary: dict[str, object] | None = None
    for name in PILOTS:
        config = ExperimentConfig.from_json(CONFIGS / name)
        path = Path(config.output_dir) / "summary.json"
        if not path.is_file():
            return False, f"missing pilot summary: {path}"
        summary = json.loads(path.read_text())
        summaries[name] = float(summary["mean_projector_sine_error"])
        if name == PILOTS[0]:
            ours_summary = summary
    assert ours_summary is not None
    absolute_passed, absolute_reasons = pilot_gate(ours_summary)
    ours = summaries[PILOTS[0]]
    strongest = min(summaries[PILOTS[1]], summaries[PILOTS[2]])
    relative_passed = ours < strongest
    reasons = [f"ours={ours:.6f}, strongest pilot baseline={strongest:.6f}"]
    reasons.extend(absolute_reasons)
    return absolute_passed and relative_passed, "; ".join(reasons)


def _evaluate() -> None:
    if not SUITE.is_file():
        raise FileNotFoundError("run scripts/generate_sci3_parameter_suites.py first")
    if not REFERENCE_CACHE.is_file():
        raise FileNotFoundError("run run_sci3.py --reference-data first")
    for name in FORMAL + SUPERVISED + ABLATIONS:
        config_path = CONFIGS / name
        config = ExperimentConfig.from_json(config_path)
        for seed in config.seeds:
            checkpoint = Path(config.output_dir) / f"seed_{seed}" / "final.pt"
            if not checkpoint.is_file():
                raise FileNotFoundError(checkpoint)
            output = Path(config.output_dir) / "frozen_test" / f"seed_{seed}"
            subprocess.run(
                [sys.executable, "scripts/evaluate_sci3_suite.py", str(config_path), str(checkpoint),
                 str(SUITE), str(output), "--reference-cache", str(REFERENCE_CACHE)], check=True
            )


def _anchor_validation() -> None:
    _run_configs(ANCHOR_VALIDATION)
    scores = {}
    for name in ANCHOR_VALIDATION:
        config_path = CONFIGS / name
        config = ExperimentConfig.from_json(config_path)
        values = []
        for seed in config.seeds:
            output = Path(config.output_dir) / "validation" / f"seed_{seed}"
            subprocess.run([sys.executable, "scripts/evaluate_sci3_suite.py", str(config_path),
                            str(Path(config.output_dir) / f"seed_{seed}" / "final.pt"),
                            str(VALIDATION_SUITE), str(output)], check=True, stdout=subprocess.DEVNULL)
            summary = json.loads((output / "summary.json").read_text())
            values.append(float(summary["aggregate"][0]["mean"]))
        scores[str(config.anchor_scale)] = sum(values) / len(values)
    selected = min(scores, key=scores.get)
    result = {"selection_data": "validation_only", "scores": scores, "selected_anchor_scale": float(selected)}
    path = Path("results/sci3/anchor_validation/selection.json"); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    stage = parser.add_mutually_exclusive_group(required=True)
    stage.add_argument("--prepare", action="store_true")
    stage.add_argument("--gaussian-pilot", action="store_true")
    stage.add_argument("--anchor-validation", action="store_true")
    stage.add_argument("--formal-core", action="store_true")
    stage.add_argument("--supervised-data", action="store_true")
    stage.add_argument("--reference-data", action="store_true")
    stage.add_argument("--supervised-train", action="store_true")
    stage.add_argument("--ablations", action="store_true")
    stage.add_argument("--evaluate", action="store_true")
    args = parser.parse_args()
    parser.error(LEGACY_PROTOCOL_WARNING)
    if args.prepare:
        subprocess.run([sys.executable, "scripts/generate_sci3_parameter_suites.py"], check=True)
        subprocess.run([sys.executable, "-m", "pytest", "-q"], check=True)
    elif args.gaussian_pilot:
        _run_configs(PILOTS)
        passed, reason = _gaussian_gate()
        print(f"gaussian_pilot_gate={'GO' if passed else 'STOP'}: {reason}")
        return 0 if passed else 2
    elif args.anchor_validation:
        _anchor_validation()
    elif args.formal_core:
        selection_path = Path("results/sci3/anchor_validation/selection.json")
        if not selection_path.is_file():
            parser.error("run --anchor-validation before --formal-core")
        selected_scale = float(json.loads(selection_path.read_text())["selected_anchor_scale"])
        if selected_scale != 0.4:
            parser.error(
                f"validation selected anchor_scale={selected_scale}; update all ours configs before formal test"
            )
        passed, reason = _gaussian_gate()
        if not passed:
            parser.error(f"formal core blocked by Gaussian pilot gate: {reason}")
        _run_configs(FORMAL)
    elif args.supervised_data:
        for family in ("harmonic_honeycomb", "gaussian_honeycomb"):
            subprocess.run([sys.executable, "scripts/generate_grassmann_dataset.py", family,
                            f"data/sci3_{family}_grassmann.pt"], check=True)
    elif args.reference_data:
        subprocess.run([sys.executable, "scripts/precompute_sci3_references.py", str(SUITE),
                        str(REFERENCE_CACHE)], check=True)
    elif args.supervised_train:
        for name in SUPERVISED:
            config = ExperimentConfig.from_json(CONFIGS / name)
            dataset = f"data/sci3_{config.potential_family}_grassmann.pt"
            subprocess.run([sys.executable, "scripts/train_supervised_grassmann.py",
                            str(CONFIGS / name), dataset], check=True)
    elif args.ablations:
        _run_configs(ABLATIONS)
    else:
        _evaluate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

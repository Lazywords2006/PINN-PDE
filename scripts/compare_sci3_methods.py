"""Paired statistics planned for the frozen-before-formal V2 endpoint."""

from __future__ import annotations

import argparse
import csv
import glob
import itertools
import json
import math
import random
import re
import statistics
from pathlib import Path


def _seed(path: str) -> int:
    match = re.search(r"seed_(\d+)", path)
    if not match:
        raise ValueError(f"path does not contain seed_<n>: {path}")
    return int(match.group(1))


def _load(pattern: str, split: str) -> dict[int, dict[str, float]]:
    output: dict[int, dict[str, float]] = {}
    for path in sorted(glob.glob(pattern)):
        seed = _seed(path)
        if seed in output:
            raise ValueError(f"duplicate result file for seed {seed}")
        with open(path, newline="") as handle:
            rows = [row for row in csv.DictReader(handle) if row["split"] == split]
        if not rows:
            raise ValueError(f"no {split} rows in {path}")
        identities = [str(row["id"]) for row in rows]
        if len(identities) != len(set(identities)):
            raise ValueError(f"duplicate point id in {path}")
        values = {str(row["id"]): float(row["projector_sine_error"]) for row in rows}
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError(f"non-finite projector error in {path}")
        output[seed] = values
    return output


def _permutation_p(differences: list[float]) -> float:
    observed = abs(statistics.mean(differences))
    count = 0
    total = 0
    for signs in itertools.product((-1.0, 1.0), repeat=len(differences)):
        total += 1
        if abs(statistics.mean(value * sign for value, sign in zip(differences, signs))) >= observed - 1e-15:
            count += 1
    return count / total


def _nested_bootstrap_ci(
    ours: dict[int, dict[str, float]], baseline: dict[int, dict[str, float]], samples: int = 10000
) -> tuple[float, float]:
    """Paired bootstrap: resample seeds, then point identities within each seed."""

    rng = random.Random(20260712)
    seeds = sorted(ours)
    means = []
    for _ in range(samples):
        sampled_seed_means = []
        for _ in seeds:
            seed = rng.choice(seeds)
            identities = sorted(ours[seed])
            point_differences = [
                baseline[seed][identity] - ours[seed][identity]
                for identity in (rng.choice(identities) for _ in identities)
            ]
            sampled_seed_means.append(statistics.mean(point_differences))
        means.append(statistics.mean(sampled_seed_means))
    means.sort()
    return means[int(0.025 * samples)], means[int(0.975 * samples)]


def _matched_pairs_rank_biserial(differences: list[float]) -> float:
    """Wilcoxon matched-pairs rank-biserial effect size with average tie ranks."""

    nonzero = [value for value in differences if abs(value) > 1e-15]
    if not nonzero:
        return 0.0
    order = sorted(range(len(nonzero)), key=lambda index: abs(nonzero[index]))
    ranks = [0.0] * len(nonzero)
    start = 0
    while start < len(order):
        end = start + 1
        magnitude = abs(nonzero[order[start]])
        while end < len(order) and math.isclose(
            abs(nonzero[order[end]]), magnitude, rel_tol=1e-12, abs_tol=1e-15
        ):
            end += 1
        average_rank = ((start + 1) + end) / 2.0
        for position in range(start, end):
            ranks[order[position]] = average_rank
        start = end
    positive = sum(rank for rank, value in zip(ranks, nonzero) if value > 0)
    negative = sum(rank for rank, value in zip(ranks, nonzero) if value < 0)
    return (positive - negative) / (positive + negative)


def _seed_means(paired: dict[int, dict[str, float]]) -> dict[int, float]:
    return {seed: statistics.mean(values.values()) for seed, values in paired.items()}


def _compare(ours: dict[int, dict[str, float]], baseline: dict[int, dict[str, float]]) -> dict[str, object]:
    if set(ours) != set(baseline):
        raise ValueError("ours and baseline must contain exactly the same seed set")
    seeds = sorted(ours)
    if len(seeds) < 10:
        raise ValueError(f"paired SCI-Q3 comparison requires at least 10 seeds; got {len(seeds)}")
    for seed in seeds:
        if set(ours[seed]) != set(baseline[seed]):
            raise ValueError(f"point id mismatch for seed {seed}")
    ours_mean = _seed_means(ours)
    baseline_mean = _seed_means(baseline)
    differences = [baseline_mean[seed] - ours_mean[seed] for seed in seeds]
    relative = [
        (baseline_mean[seed] - ours_mean[seed]) / max(abs(baseline_mean[seed]), 1e-12)
        for seed in seeds
    ]
    ci_low, ci_high = _nested_bootstrap_ci(ours, baseline)
    positives = sum(value > 0 for value in differences)
    negatives = sum(value < 0 for value in differences)
    return {
        "seeds": seeds,
        "points_per_seed": len(ours[seeds[0]]),
        "ours_mean": statistics.mean(ours_mean.values()),
        "baseline_mean": statistics.mean(baseline_mean.values()),
        "paired_improvement_mean": statistics.mean(differences),
        "paired_improvement_ci95": [ci_low, ci_high],
        "relative_improvement_median": statistics.median(relative),
        "seeds_improved": positives,
        "paired_permutation_p": _permutation_p(differences),
        "matched_pairs_rank_biserial": _matched_pairs_rank_biserial(differences),
    }


def _apply_holm(comparisons: dict[str, dict[str, object]], alpha: float = 0.05) -> None:
    """Apply Holm's step-down rule, stopping rejection after the first failure."""

    ordered = sorted(comparisons, key=lambda name: float(comparisons[name]["paired_permutation_p"]))
    still_rejecting = True
    for index, name in enumerate(ordered):
        raw = float(comparisons[name]["paired_permutation_p"])
        threshold = alpha / (len(ordered) - index)
        passed = still_rejecting and raw <= threshold
        comparisons[name]["holm_threshold"] = threshold
        comparisons[name]["holm_pass"] = passed
        if not passed:
            still_rejecting = False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ours", required=True, help="glob for ours per_parameter.csv files")
    parser.add_argument("--baseline", action="append", required=True, help="name=glob; repeatable")
    parser.add_argument("--split", default="near_cluster")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    ours = _load(args.ours, args.split)
    comparisons = {}
    for value in args.baseline:
        name, pattern = value.split("=", 1)
        comparisons[name] = _compare(ours, _load(pattern, args.split))
    _apply_holm(comparisons)
    result = {"primary_endpoint": args.split, "comparisons": comparisons}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

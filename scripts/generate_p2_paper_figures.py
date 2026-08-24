#!/usr/bin/env python3
"""Generate publication figures and tables from audited P2 final rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tarfile
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

METHOD_LABELS = {
    "p5_unanchored_low_rom": "Unanchored trace",
    "p5_anchor": "Anchor",
    "p5_wide_anchor": "Wide anchor",
    "p5_long_anchor": "Long anchor",
    "p5_static_low_rom": "Static low-ROM",
    "p5_highfreq_rom": "High-frequency ROM",
    "p2_shell1": "Neural + shell 1",
    "p2_shell2_outer": "Neural + outer shell 2",
    "p2_shell2_all": "P2 full shell",
    "fourier_only_rank21": "Fourier-only (rank 21)",
}
SPLIT_LABELS = {
    "iid_hidden": "IID",
    "exact_cluster": "Exact",
    "near_cluster": "Near",
    "strict_ood": "Strict OOD",
    "gap_scan": "Gap scan",
}
COLORS = {
    "primary": "#D8892B",
    "blue": "#2F5D8A",
    "teal": "#3B7F6D",
    "purple": "#7B5EA7",
    "gray": "#8A8F98",
    "light_gray": "#D6D9DE",
    "ink": "#20252B",
}
EXPECTED_FINAL_EVIDENCE_SHA256 = (
    "c653d0eddab018741312741f6db46f023a20812306d574b66947bbb42af25095"
)
EXPECTED_FINAL_SUITE_SHA256 = (
    "b8658e7512a829018b0c6cc754b7d9e7fb55c4e41c852dfa84a2ff606a5e161c"
)
EXPECTED_FINAL_REFERENCE_SHA256 = (
    "8969794607c3d82b2636eac518a49087407f9b8c0ce3fb3c037adf395673448d"
)
EXPECTED_PILOT_EVIDENCE_SHA256 = (
    "0c49461a6c780840ca678582019cc433df5741fd62ef546dcde7e964b71c071b"
)


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "axes.edgecolor": "#7C828A",
            "axes.linewidth": 0.8,
            "xtick.color": COLORS["ink"],
            "ytick.color": COLORS["ink"],
            "text.color": COLORS["ink"],
            "axes.labelcolor": COLORS["ink"],
            "axes.titlecolor": COLORS["ink"],
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "svg.fonttype": "none",
        }
    )


def _save(fig: plt.Figure, output: Path, name: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output / f"{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(output / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)


def _read_rows(path: Path) -> list[dict[str, object]]:
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["seed"] = int(row["seed"])
        row["projector_error"] = float(row["projector_error"])
        row["latency_ms"] = float(row["latency_ms"])
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_final_inputs(
    final_dir: Path,
    evidence: Path,
    pilot_evidence: Path,
    rows: list[dict[str, object]],
    summary: dict[str, object],
) -> None:
    sidecar = evidence.with_suffix(evidence.suffix + ".sha256")
    declared = sidecar.read_text().split()[0] if sidecar.is_file() else ""
    actual = _sha256(evidence)
    if actual != declared or actual != EXPECTED_FINAL_EVIDENCE_SHA256:
        raise ValueError("final evidence SHA-256 is not approved")
    with tarfile.open(evidence, "r:gz") as archive:
        manifest_handle = archive.extractfile(
            archive.getmember("results/p2-final-evidence-manifest.json")
        )
        if manifest_handle is None:
            raise ValueError("final evidence manifest is unreadable")
        manifest = json.loads(manifest_handle.read())
    entries = {row["path"]: row for row in manifest["files"]}
    rows_entry = entries.get("results/p2_final/rows.csv")
    rows_path = final_dir / "rows.csv"
    if (
        rows_entry is None
        or rows_path.stat().st_size != int(rows_entry["bytes"])
        or _sha256(rows_path) != rows_entry["sha256"]
    ):
        raise ValueError("final rows do not match evidence manifest")
    pilot_sidecar = pilot_evidence.with_suffix(pilot_evidence.suffix + ".sha256")
    pilot_actual = _sha256(pilot_evidence)
    pilot_declared = (
        pilot_sidecar.read_text().split()[0] if pilot_sidecar.is_file() else ""
    )
    if (
        pilot_actual != pilot_declared
        or pilot_actual != EXPECTED_PILOT_EVIDENCE_SHA256
        or summary.get("pilot_evidence_sha256") != EXPECTED_PILOT_EVIDENCE_SHA256
    ):
        raise ValueError("pilot evidence SHA-256 is not approved")
    gate = json.loads((final_dir / "gate.json").read_text())
    if gate.get("final_go") is not True:
        raise ValueError("paper figures require P2_FROZEN_FINAL_GO")
    if summary.get("suite_sha256") != EXPECTED_FINAL_SUITE_SHA256:
        raise ValueError("final suite SHA-256 mismatch")
    if summary.get("reference_sha256") != EXPECTED_FINAL_REFERENCE_SHA256:
        raise ValueError("final reference SHA-256 mismatch")
    if len(rows) != 19_200:
        raise ValueError("final rows must contain exactly 19,200 records")
    method_counts = {
        method: sum(row["method"] == method for row in rows)
        for method in METHOD_LABELS
    }
    if {row["method"] for row in rows} != set(METHOD_LABELS) or set(
        method_counts.values()
    ) != {1_920}:
        raise ValueError("final method identities or row counts are invalid")
    for method in METHOD_LABELS:
        recomputed = _group_mean(rows, method)
        stored = float(summary[f"{method}_overall_mean"])
        if abs(recomputed - stored) > 1e-12:
            raise ValueError(f"final summary does not match rows for {method}")
        for split in SPLIT_LABELS:
            recomputed_split = _group_mean(rows, method, split)
            stored_split = float(summary[f"{method}_{split}_mean"])
            if abs(recomputed_split - stored_split) > 1e-12:
                raise ValueError(
                    f"final split summary does not match rows for {method}:{split}"
                )
        for seed in (42, 137, 251):
            seed_mean = float(
                np.mean(
                    [
                        row["projector_error"]
                        for row in rows
                        if row["method"] == method and row["seed"] == seed
                    ]
                )
            )
            if abs(seed_mean - float(summary["seed_means"][method][str(seed)])) > 1e-12:
                raise ValueError(
                    f"final seed summary does not match rows for {method}:{seed}"
                )
    for family, stored_values in summary["family_near"].items():
        for method, stored in stored_values.items():
            recomputed = float(
                np.mean(
                    [
                        row["projector_error"]
                        for row in rows
                        if row["family"] == family
                        and row["method"] == method
                        and row["split"] == "near_cluster"
                    ]
                )
            )
            if abs(recomputed - float(stored)) > 1e-12:
                raise ValueError(
                    f"final family summary does not match rows for {family}:{method}"
                )


def _group_mean(
    rows: list[dict[str, object]], method: str, split: str | None = None
) -> float:
    values = [
        float(row["projector_error"])
        for row in rows
        if row["method"] == method and (split is None or row["split"] == split)
    ]
    return float(np.mean(values))


def _method_table(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    table: list[dict[str, object]] = []
    for method, label in METHOD_LABELS.items():
        selected = [row for row in rows if row["method"] == method]
        table.append(
            {
                "method": method,
                "label": label,
                "overall_error": float(
                    np.mean([row["projector_error"] for row in selected])
                ),
                "latency_ms": float(np.mean([row["latency_ms"] for row in selected])),
                **{
                    f"{split}_error": _group_mean(rows, method, split)
                    for split in SPLIT_LABELS
                },
            }
        )
    return table


def _write_tables(
    rows: list[dict[str, object]], table_dir: Path
) -> list[dict[str, object]]:
    table_dir.mkdir(parents=True, exist_ok=True)
    method_table = _method_table(rows)
    with (table_dir / "method_summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(method_table[0]))
        writer.writeheader()
        writer.writerows(method_table)
    split_rows = [
        {
            "method": method,
            "split": split,
            "mean_projector_error": _group_mean(rows, method, split),
        }
        for method in METHOD_LABELS
        for split in SPLIT_LABELS
    ]
    with (table_dir / "split_summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(split_rows[0]))
        writer.writeheader()
        writer.writerows(split_rows)
    return method_table


def figure_method_ranking(table: list[dict[str, object]], output: Path) -> None:
    ordered = sorted(table, key=lambda row: float(row["overall_error"]), reverse=True)
    labels = [str(row["label"]) for row in ordered]
    values = [float(row["overall_error"]) for row in ordered]
    colors = [
        COLORS["primary"] if row["method"] == "p2_shell2_all" else COLORS["blue"]
        if str(row["method"]).startswith("p2_")
        else COLORS["gray"]
        for row in ordered
    ]
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    bars = ax.barh(labels, values, color=colors, edgecolor=COLORS["ink"], linewidth=0.35)
    ax.set_xlabel("Mean rank-2 projector sine error (lower is better)")
    ax.set_title("Frozen-final overall error by method\n640 parameter points × 3 checkpoint seeds")
    ax.grid(axis="x", color="#E6E8EB", linewidth=0.7)
    ax.set_axisbelow(True)
    for bar, value in zip(bars, values, strict=True):
        ax.text(value + 0.002, bar.get_y() + bar.get_height() / 2, f"{value:.3f}", va="center", fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, output, "fig01_method_overall_error")


def figure_split_comparison(rows: list[dict[str, object]], output: Path) -> None:
    methods = (
        "p5_anchor",
        "p5_long_anchor",
        "p2_shell1",
        "p2_shell2_all",
        "fourier_only_rank21",
    )
    colors = [COLORS["gray"], COLORS["purple"], COLORS["teal"], COLORS["primary"], COLORS["blue"]]
    x = np.arange(len(SPLIT_LABELS))
    width = 0.15
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    for index, (method, color) in enumerate(zip(methods, colors, strict=True)):
        values = [_group_mean(rows, method, split) for split in SPLIT_LABELS]
        ax.bar(
            x + (index - 2) * width,
            values,
            width,
            label=METHOD_LABELS[method],
            color=color,
            edgecolor=COLORS["ink"],
            linewidth=0.3,
        )
    ax.set_xticks(x, SPLIT_LABELS.values())
    ax.set_ylabel("Mean projector sine error")
    ax.set_title("Frozen-final error across parameter regimes\nIdentical split definitions and reference cutoff for all methods")
    ax.grid(axis="y", color="#E6E8EB", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.legend(ncol=3, frameon=False, fontsize=8, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, output, "fig02_split_comparison")


def figure_family_near(rows: list[dict[str, object]], output: Path) -> None:
    families = ("harmonic_honeycomb", "gaussian_honeycomb")
    labels = ("Harmonic honeycomb", "Gaussian honeycomb")
    methods = ("p5_long_anchor", "p2_shell1", "p2_shell2_all")
    colors = (COLORS["purple"], COLORS["teal"], COLORS["primary"])
    x = np.arange(2)
    width = 0.23
    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    for index, (method, color) in enumerate(zip(methods, colors, strict=True)):
        values = [
            float(
                np.mean(
                    [
                        row["projector_error"]
                        for row in rows
                        if row["method"] == method
                        and row["family"] == family
                        and row["split"] == "near_cluster"
                    ]
                )
            )
            for family in families
        ]
        ax.bar(x + (index - 1) * width, values, width, label=METHOD_LABELS[method], color=color, edgecolor=COLORS["ink"], linewidth=0.35)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Near-cluster projector error")
    ax.set_title("Near-cluster error by potential family\n128 final points × 3 checkpoint seeds")
    ax.grid(axis="y", color="#E6E8EB", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, output, "fig03_family_near_error")


def figure_bootstrap(summary: dict[str, object], output: Path) -> None:
    names = ("Overall", "Near-cluster")
    blocks = (
        summary["overall_improvement_bootstrap"],
        summary["near_improvement_bootstrap"],
    )
    means = np.array([block["mean"] for block in blocks]) * 100
    lows = np.array([block["low"] for block in blocks]) * 100
    highs = np.array([block["high"] for block in blocks]) * 100
    y = np.arange(2)
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    ax.errorbar(means, y, xerr=np.vstack((means - lows, highs - means)), fmt="o", color=COLORS["primary"], ecolor=COLORS["blue"], capsize=4, linewidth=2)
    ax.axvline(0, color=COLORS["ink"], linewidth=0.8)
    ax.set_yticks(y, names)
    ax.set_xlabel("Improvement over long-anchor (%)")
    ax.set_title("Point-clustered bootstrap improvement\n2,000 resamples; 95% confidence intervals")
    ax.grid(axis="x", color="#E6E8EB", linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    for index, (mean, low, high) in enumerate(zip(means, lows, highs, strict=True)):
        ax.text(high + 1.0, index, f"{mean:.1f}% [{low:.1f}, {high:.1f}]", va="center", fontsize=8)
    _save(fig, output, "fig04_bootstrap_improvement")


def figure_error_cdf(rows: list[dict[str, object]], output: Path) -> None:
    methods = ("p5_anchor", "p5_long_anchor", "p2_shell1", "p2_shell2_all", "fourier_only_rank21")
    colors = (COLORS["gray"], COLORS["purple"], COLORS["teal"], COLORS["primary"], COLORS["blue"])
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    for method, color in zip(methods, colors, strict=True):
        values = np.sort([row["projector_error"] for row in rows if row["method"] == method])
        cdf = np.arange(1, len(values) + 1) / len(values)
        ax.plot(values, cdf, label=METHOD_LABELS[method], color=color, linewidth=1.8)
    ax.set_xlabel("Rank-2 projector sine error")
    ax.set_ylabel("Empirical cumulative probability")
    ax.set_title("Frozen-final error distribution\n1,920 paired rows per method")
    ax.grid(color="#E6E8EB", linewidth=0.7)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, output, "fig05_error_cdf")


def figure_paired_scatter(rows: list[dict[str, object]], output: Path) -> None:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    family_by_point: dict[str, str] = {}
    for row in rows:
        if row["method"] in {"p5_long_anchor", "p2_shell2_all"}:
            grouped[(str(row["method"]), str(row["point_id"]))].append(float(row["projector_error"]))
            family_by_point[str(row["point_id"])] = str(row["family"])
    points = sorted(point for method, point in grouped if method == "p2_shell2_all")
    x = np.array([np.mean(grouped[("p5_long_anchor", point)]) for point in points])
    y = np.array([np.mean(grouped[("p2_shell2_all", point)]) for point in points])
    colors = [COLORS["blue"] if family_by_point[point] == "harmonic_honeycomb" else COLORS["primary"] for point in points]
    fig, ax = plt.subplots(figsize=(5.3, 5.0))
    ax.scatter(x, y, c=colors, s=15, alpha=0.65, linewidths=0)
    limit = max(float(x.max()), float(y.max())) * 1.04
    ax.plot([0, limit], [0, limit], color=COLORS["ink"], linestyle="--", linewidth=1, label="Equal error")
    ax.set_xlim(0, limit)
    ax.set_ylim(0, limit)
    ax.set_xlabel("Long-anchor point-mean error")
    ax.set_ylabel("P2 full-shell point-mean error")
    ax.set_title("Paired final error by parameter point\n640 point clusters; colors denote potential family")
    ax.grid(color="#E6E8EB", linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, output, "fig06_paired_point_scatter")


def figure_efficiency(
    table: list[dict[str, object]], pilot_summary: dict[str, object], output: Path
) -> None:
    selected = [
        row
        for row in table
        if row["method"]
        in {
            "p5_anchor",
            "p5_long_anchor",
            "p5_static_low_rom",
            "p2_shell1",
            "p2_shell2_all",
            "fourier_only_rank21",
        }
    ]
    fig, ax = plt.subplots(figsize=(6.4, 4.3))
    label_offsets = {
        "p5_anchor": (7, 8),
        "p5_long_anchor": (7, 9),
        "p5_static_low_rom": (7, -13),
        "p2_shell1": (7, 5),
        "p2_shell2_all": (7, 5),
        "fourier_only_rank21": (7, 5),
    }
    for row in selected:
        method = str(row["method"])
        color = COLORS["primary"] if method == "p2_shell2_all" else COLORS["teal"] if method.startswith("p2_") else COLORS["gray"]
        latency = (
            float(pilot_summary["p2_latency_mean_ms"])
            if method == "p2_shell2_all"
            else float(row["latency_ms"])
        )
        ax.scatter(latency, float(row["overall_error"]), s=45, color=color, edgecolor=COLORS["ink"], linewidth=0.4)
        ax.annotate(
            METHOD_LABELS[method],
            (latency, float(row["overall_error"])),
            xytext=label_offsets[method],
            textcoords="offset points",
            fontsize=7,
        )
    pwe_latency = float(pilot_summary["pwe_latency_mean_ms"])
    ax.scatter(pwe_latency, 0.0, marker="D", s=50, color=COLORS["blue"], edgecolor=COLORS["ink"], linewidth=0.4)
    ax.annotate("Cutoff-24 PWE reference", (pwe_latency, 0.0), xytext=(-5, 9), ha="right", textcoords="offset points", fontsize=7)
    ax.set_xscale("log")
    ax.set_xlabel("Mean inference time per parameter (ms, log scale)")
    ax.set_ylabel("Frozen-final mean projector error")
    ax.set_title("Accuracy–latency comparison\nP2/PWE: production benchmark; other methods: final per-point timing")
    ax.grid(color="#E6E8EB", linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, output, "fig07_accuracy_latency")


def figure_seed_stability(summary: dict[str, object], output: Path) -> None:
    methods = ("p5_anchor", "p5_long_anchor", "p2_shell1", "p2_shell2_all")
    seeds = ("42", "137", "251")
    x = np.arange(3)
    fig, ax = plt.subplots(figsize=(6.7, 3.8))
    colors = (COLORS["gray"], COLORS["purple"], COLORS["teal"], COLORS["primary"])
    for method, color in zip(methods, colors, strict=True):
        values = [summary["seed_means"][method][seed] for seed in seeds]
        ax.plot(x, values, marker="o", label=METHOD_LABELS[method], color=color, linewidth=1.8)
    ax.set_xticks(x, [f"Seed {seed}" for seed in seeds])
    ax.set_ylabel("Mean frozen-final projector error")
    ax.set_title("Checkpoint-seed stability\nEach seed aggregates 640 parameter points")
    ax.grid(axis="y", color="#E6E8EB", linewidth=0.7)
    ax.legend(frameon=False, fontsize=8, ncol=2)
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, output, "fig08_seed_stability")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--final-dir", type=Path, required=True)
    parser.add_argument("--final-evidence", type=Path, required=True)
    parser.add_argument("--pilot-evidence", type=Path, required=True)
    parser.add_argument("--pilot-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("figures/p2_final"))
    parser.add_argument("--table-dir", type=Path, default=Path("paper/p2_final/tables"))
    args = parser.parse_args()
    _style()
    rows = _read_rows(args.final_dir / "rows.csv")
    summary = json.loads((args.final_dir / "summary.json").read_text())
    pilot_summary = json.loads(args.pilot_summary.read_text())
    _validate_final_inputs(
        args.final_dir,
        args.final_evidence,
        args.pilot_evidence,
        rows,
        summary,
    )
    table = _write_tables(rows, args.table_dir)
    figure_method_ranking(table, args.output_dir)
    figure_split_comparison(rows, args.output_dir)
    figure_family_near(rows, args.output_dir)
    figure_bootstrap(summary, args.output_dir)
    figure_error_cdf(rows, args.output_dir)
    figure_paired_scatter(rows, args.output_dir)
    figure_efficiency(table, pilot_summary, args.output_dir)
    figure_seed_stability(summary, args.output_dir)
    print(f"P2_FIGURES={args.output_dir}")
    print(f"P2_TABLES={args.table_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

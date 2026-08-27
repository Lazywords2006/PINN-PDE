#!/usr/bin/env python3
"""Generate publication figures and tables from frozen V3 formal evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

EXPECTED_FORMAL_EVIDENCE_SHA256 = (
    "108a4b042549ead58f7b13f42b6ace4685e93a4e8a54e9563b044c03c29ad78c"
)
EXPECTED_SOURCE_FINGERPRINT = (
    "27b8d487a8ff81a89d27d49856b3559e51188d0424a143ad7133d9d572f2dbbb"
)
EXPECTED_ROWS = 5_280
EXPECTED_POINTS = 160
EXPECTED_SEEDS = {42, 137, 251}

METHOD_LABELS = {
    "long_anchor": "Long-anchor neural",
    "sc_narr_shell1": "Neural + D6 shell 1",
    "sc_narr": "Neural + D6 shell 2",
    "sc_hybrid25": "Fixed neural–Fourier 25",
    "sr_routed25": "SR-SC-NARR",
    "fourier_shell2": "D6 shell 2 (rank 19)",
    "kinetic_fourier21": "Kinetic Fourier ≥21",
    "kinetic_fourier25": "Kinetic Fourier ≥25",
    "fourier_shell3": "D6 shell 3 (rank 37)",
    "wang_xie_adapted": "Wang–Xie adapted",
    "dai_adapted": "Dai adapted",
}
SPLIT_LABELS = {
    "iid_hidden": "IID",
    "exact_cluster": "Exact",
    "near_cluster": "Near",
    "strict_ood": "Strict OOD",
    "gap_scan": "Gap scan",
}
COLORS = {
    "primary": "#C96A2B",
    "blue": "#325D88",
    "teal": "#2F7D6A",
    "purple": "#7656A3",
    "gray": "#8B929B",
    "dark": "#252A30",
    "grid": "#E4E7EB",
}
NUMERIC_FIELDS = (
    "projector_error",
    "e1_abs_error",
    "e2_abs_error",
    "trace_abs_error",
    "residual_rms",
    "orthogonality_error",
    "hermiticity_defect_raw",
    "internal_gap",
    "external_gap",
    "trial_rank",
    "tail_ratio",
    "latency_ms",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(path: Path) -> list[dict[str, object]]:
    """Read formal rows and convert declared numerical fields."""

    with path.open(newline="") as handle:
        rows: list[dict[str, object]] = list(csv.DictReader(handle))
    for row in rows:
        row["seed"] = int(str(row["seed"]))
        for field in NUMERIC_FIELDS:
            row[field] = float(str(row[field]))
    return rows


def validate_identity_matrix(rows: list[dict[str, object]]) -> None:
    """Reject incomplete, duplicated, or non-finite formal matrices."""

    if len(rows) != EXPECTED_ROWS:
        raise ValueError("formal rows must contain exactly 5,280 records")
    methods = Counter(str(row["method"]) for row in rows)
    if set(methods) != set(METHOD_LABELS) or set(methods.values()) != {480}:
        raise ValueError("formal method identities or counts are invalid")
    identities = {
        (str(row["method"]), int(row["seed"]), str(row["point_id"]))
        for row in rows
    }
    if len(identities) != EXPECTED_ROWS:
        raise ValueError("formal method–seed–point identities are duplicated")
    if len({str(row["point_id"]) for row in rows}) != EXPECTED_POINTS:
        raise ValueError("formal physical-point count is invalid")
    if {int(row["seed"]) for row in rows} != EXPECTED_SEEDS:
        raise ValueError("formal checkpoint-seed set is invalid")
    required = tuple(field for field in NUMERIC_FIELDS if field != "tail_ratio")
    if not all(
        math.isfinite(float(row[field])) for row in rows for field in required
    ):
        raise ValueError("formal rows contain non-finite required metrics")
    routed = [row for row in rows if row["method"] == "sr_routed25"]
    if not all(math.isfinite(float(row["tail_ratio"])) for row in routed):
        raise ValueError("routed rows contain non-finite tail ratios")
    if Counter(str(row["route"]) for row in routed) != {
        "fourier": 240,
        "hybrid": 240,
    }:
        raise ValueError("formal routed-method branch counts are invalid")


def _mean(
    rows: list[dict[str, object]],
    method: str,
    field: str,
    *,
    split: str | None = None,
    family: str | None = None,
    seed: int | None = None,
) -> float:
    values = [
        float(row[field])
        for row in rows
        if row["method"] == method
        and (split is None or row["split"] == split)
        and (family is None or row["family"] == family)
        and (seed is None or row["seed"] == seed)
    ]
    if not values:
        raise ValueError(f"empty aggregate for {method}:{field}")
    return statistics.mean(values)


def validate_inputs(
    result_dir: Path, evidence_path: Path, rows: list[dict[str, object]]
) -> tuple[dict[str, object], dict[str, object]]:
    """Bind figures to the frozen archive, result manifest, and gate."""

    sidecar = evidence_path.with_suffix(evidence_path.suffix + ".sha256")
    declared = sidecar.read_text().split()[0]
    actual = file_sha256(evidence_path)
    if actual != declared or actual != EXPECTED_FORMAL_EVIDENCE_SHA256:
        raise ValueError("formal evidence SHA-256 is not approved")
    gate = json.loads((result_dir / "gate.json").read_text())
    if gate.get("promotion_go") is not True or not all(gate.values()):
        raise ValueError("paper figures require V3_FORMAL_PROMOTION_GO")
    provenance = json.loads((result_dir / "provenance.json").read_text())
    if (
        provenance.get("formal") is not True
        or provenance.get("source_fingerprint") != EXPECTED_SOURCE_FINGERPRINT
        or provenance.get("git_status_before_open") != "clean"
        or provenance.get("device") != "cuda"
    ):
        raise ValueError("formal provenance is not publication-approved")
    archive_payloads: dict[str, bytes] = {}
    with tarfile.open(evidence_path, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        for name in (
            "rows.csv",
            "summary.json",
            "gate.json",
            "provenance.json",
            "evidence-manifest.json",
        ):
            member = members.get(f"results/{name}")
            if member is None:
                raise ValueError(f"approved evidence archive is missing {name}")
            handle = archive.extractfile(member)
            if handle is None:
                raise ValueError(f"approved evidence member is unreadable: {name}")
            archive_payloads[name] = handle.read()
            if (result_dir / name).read_bytes() != archive_payloads[name]:
                raise ValueError(f"local formal result differs from archive: {name}")
    manifest = json.loads(archive_payloads["evidence-manifest.json"])
    result_entries = {
        str(item["path"]): item
        for item in manifest["files"]
        if item["kind"] == "result"
    }
    for name in ("rows.csv", "summary.json", "gate.json", "provenance.json"):
        path = result_dir / name
        entry = result_entries.get(name)
        if (
            entry is None
            or path.stat().st_size != int(entry["bytes"])
            or file_sha256(path) != entry["sha256"]
        ):
            raise ValueError(f"formal result does not match manifest: {name}")
    validate_identity_matrix(rows)
    summary = json.loads((result_dir / "summary.json").read_text())
    for method in METHOD_LABELS:
        recomputed = _mean(rows, method, "projector_error")
        if abs(recomputed - float(summary["methods"][method]["overall"])) > 1e-12:
            raise ValueError(f"formal mean does not match rows: {method}")
    return summary, provenance


def validate_convergence(
    path: Path,
    *,
    provenance: dict[str, object],
    evidence_path: Path,
) -> dict[str, object]:
    """Bind the convergence table to sidecar, provenance, and formal archive."""

    actual = file_sha256(path)
    sidecar = path.with_suffix(".sha256")
    declared = sidecar.read_text().split()[0]
    if actual != declared:
        raise ValueError("convergence audit sidecar mismatch")
    if actual != provenance.get("convergence_audit_sha256"):
        raise ValueError("convergence audit is not bound by formal provenance")
    with tarfile.open(evidence_path, "r:gz") as archive:
        members = [
            member
            for member in archive.getmembers()
            if member.name.endswith("_v3_symmetry_convergence_audit.json")
        ]
        if len(members) != 1:
            raise ValueError("formal archive convergence member is ambiguous")
        handle = archive.extractfile(members[0])
        if handle is None or handle.read() != path.read_bytes():
            raise ValueError("convergence audit differs from formal archive")
    payload = json.loads(path.read_text())
    if payload.get("gate", {}).get("convergence_go") is not True:
        raise ValueError("paper tables require V3_CONVERGENCE_GO")
    return payload


def paired_point_means(
    rows: list[dict[str, object]], *, candidate: str, baseline: str
) -> list[dict[str, object]]:
    """Return one seed-averaged paired record per physical point."""

    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if row["method"] in {candidate, baseline}:
            grouped[(str(row["method"]), str(row["point_id"]))].append(row)
    points = sorted(
        point for method, point in grouped if method == candidate
    )
    result: list[dict[str, object]] = []
    for point in points:
        candidate_rows = grouped[(candidate, point)]
        baseline_rows = grouped[(baseline, point)]
        if len(candidate_rows) != 3 or len(baseline_rows) != 3:
            raise ValueError(f"paired point lacks three seeds: {point}")
        first = candidate_rows[0]
        result.append(
            {
                "point_id": point,
                "family": first["family"],
                "split": first["split"],
                "candidate_error": statistics.mean(
                    float(row["projector_error"]) for row in candidate_rows
                ),
                "baseline_error": statistics.mean(
                    float(row["projector_error"]) for row in baseline_rows
                ),
                "internal_gap": statistics.mean(
                    float(row["internal_gap"]) for row in candidate_rows
                ),
                "tail_ratio": statistics.mean(
                    float(row["tail_ratio"]) for row in candidate_rows
                ),
                "route": first["route"],
            }
        )
    if len(result) != EXPECTED_POINTS:
        raise ValueError("paired point table is incomplete")
    return result


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "axes.edgecolor": "#7B8189",
            "axes.linewidth": 0.8,
            "text.color": COLORS["dark"],
            "axes.labelcolor": COLORS["dark"],
            "axes.titlecolor": COLORS["dark"],
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


def _clean_axis(axis: plt.Axes) -> None:
    axis.grid(color=COLORS["grid"], linewidth=0.7)
    axis.set_axisbelow(True)
    axis.spines[["top", "right"]].set_visible(False)


def write_tables(
    rows: list[dict[str, object]],
    summary: dict[str, object],
    table_dir: Path,
    convergence: dict[str, object],
) -> None:
    table_dir.mkdir(parents=True, exist_ok=True)
    fields = [
        "method",
        "label",
        "overall",
        *SPLIT_LABELS,
        "eigenvalue_mae",
        "residual_rms",
        "p95",
        "maximum",
        "latency_ms",
    ]
    method_rows = []
    for method, label in METHOD_LABELS.items():
        stored = summary["methods"][method]
        method_rows.append(
            {
                "method": method,
                "label": label,
                **{field: stored[field] for field in fields[2:]},
            }
        )
    with (table_dir / "method_summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(method_rows)
    family_seed_rows = []
    for family in ("harmonic_honeycomb", "gaussian_honeycomb"):
        for seed in sorted(EXPECTED_SEEDS):
            candidate = _mean(
                rows,
                "sr_routed25",
                "projector_error",
                family=family,
                seed=seed,
            )
            baseline = _mean(
                rows,
                "kinetic_fourier25",
                "projector_error",
                family=family,
                seed=seed,
            )
            family_seed_rows.append(
                {
                    "family": family,
                    "seed": seed,
                    "candidate_error": candidate,
                    "baseline_error": baseline,
                    "relative_improvement": (baseline - candidate) / baseline,
                }
            )
    with (table_dir / "family_seed_pairs.csv").open(
        "w", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(family_seed_rows[0])
        )
        writer.writeheader()
        writer.writerows(family_seed_rows)
    family_rows = []
    for family in ("harmonic_honeycomb", "gaussian_honeycomb"):
        for method in (
            "sr_routed25",
            "kinetic_fourier25",
            "fourier_shell3",
            "sc_hybrid25",
        ):
            family_rows.append(
                {
                    "family": family,
                    "method": method,
                    "projector_error": _mean(
                        rows,
                        method,
                        "projector_error",
                        family=family,
                    ),
                    "eigenvalue_mae": statistics.mean(
                        0.5
                        * (
                            float(row["e1_abs_error"])
                            + float(row["e2_abs_error"])
                        )
                        for row in rows
                        if row["method"] == method and row["family"] == family
                    ),
                    "latency_ms": _mean(
                        rows, method, "latency_ms", family=family
                    ),
                }
            )
    with (table_dir / "family_summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(family_rows[0]))
        writer.writeheader()
        writer.writerows(family_rows)
    routing_methods = (
        "kinetic_fourier25",
        "sc_hybrid25",
        "sr_routed25",
    )
    routing_rows = [
        {
            "method": method,
            "projector_error": summary["methods"][method]["overall"],
            "eigenvalue_mae": summary["methods"][method]["eigenvalue_mae"],
            "latency_ms": summary["methods"][method]["latency_ms"],
            "p95": summary["methods"][method]["p95"],
        }
        for method in routing_methods
    ]
    with (table_dir / "routing_ablation.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(routing_rows[0]))
        writer.writeheader()
        writer.writerows(routing_rows)
    convergence_summary = convergence["summary"]
    integrity_rows = [
        {
            "metric": "reference_projector_cutoff_24_28",
            "value": convergence_summary["max_reference_projector_24_28"],
            "threshold": "<1e-3",
        },
        {
            "metric": "reference_eigenvalue_cutoff_24_28",
            "value": convergence_summary["max_reference_eigenvalue_24_28"],
            "threshold": "<1e-5",
        },
        {
            "metric": "solver_projector_grid_65_97",
            "value": convergence_summary[
                "max_solver_projector_grid_difference"
            ],
            "threshold": "<1e-3",
        },
        {
            "metric": "solver_eigenvalue_grid_65_97",
            "value": convergence_summary[
                "max_solver_eigenvalue_grid_difference"
            ],
            "threshold": "<1e-4",
        },
        {
            "metric": "proposed_raw_hermiticity_defect",
            "value": summary["methods"]["sr_routed25"][
                "max_raw_hermiticity_defect"
            ],
            "threshold": "<1e-4",
        },
        {
            "metric": "maximum_orthogonality_error",
            "value": summary["maximum_orthogonality_error"],
            "threshold": "<1e-4",
        },
        {
            "metric": "minimum_external_gap",
            "value": summary["minimum_external_gap"],
            "threshold": ">1e-2",
        },
    ]
    with (table_dir / "numerical_integrity.csv").open(
        "w", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(integrity_rows[0]))
        writer.writeheader()
        writer.writerows(integrity_rows)


def figure_overall(summary: dict[str, object], output: Path) -> None:
    ordered = sorted(
        METHOD_LABELS,
        key=lambda method: float(summary["methods"][method]["overall"]),
        reverse=True,
    )
    values = [float(summary["methods"][method]["overall"]) for method in ordered]
    colors = [
        COLORS["primary"] if method == "sr_routed25" else COLORS["blue"]
        if method in {"kinetic_fourier25", "fourier_shell3"}
        else COLORS["gray"]
        for method in ordered
    ]
    fig, axis = plt.subplots(figsize=(7.5, 4.8))
    bars = axis.barh(
        [METHOD_LABELS[method] for method in ordered],
        values,
        color=colors,
        edgecolor=COLORS["dark"],
        linewidth=0.3,
    )
    for bar, value in zip(bars, values, strict=True):
        axis.text(
            value + 0.004,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.3f}",
            va="center",
            fontsize=8,
        )
    axis.set_xlabel("Mean rank-2 projector sine error (lower is better)")
    axis.set_title("Frozen V3 confirmation: overall projector error\n160 points × 3 seeds")
    _clean_axis(axis)
    _save(fig, output, "fig01_overall_error")


def figure_splits(summary: dict[str, object], output: Path) -> None:
    methods = (
        "sr_routed25",
        "kinetic_fourier25",
        "fourier_shell3",
        "long_anchor",
        "wang_xie_adapted",
    )
    colors = (
        COLORS["primary"],
        COLORS["blue"],
        COLORS["teal"],
        COLORS["gray"],
        COLORS["purple"],
    )
    x = np.arange(len(SPLIT_LABELS))
    width = 0.16
    fig, axis = plt.subplots(figsize=(8.4, 4.4))
    for index, (method, color) in enumerate(zip(methods, colors, strict=True)):
        values = [float(summary["methods"][method][split]) for split in SPLIT_LABELS]
        axis.bar(
            x + (index - 2) * width,
            values,
            width,
            label=METHOD_LABELS[method],
            color=color,
            edgecolor=COLORS["dark"],
            linewidth=0.25,
        )
    axis.set_xticks(x, SPLIT_LABELS.values())
    axis.set_ylabel("Mean projector sine error")
    axis.set_title("Generalization across frozen parameter regimes")
    axis.legend(frameon=False, fontsize=8, ncol=3)
    _clean_axis(axis)
    _save(fig, output, "fig02_split_comparison")


def figure_cdf(rows: list[dict[str, object]], output: Path) -> None:
    methods = (
        "sr_routed25",
        "kinetic_fourier25",
        "fourier_shell3",
        "long_anchor",
    )
    colors = (
        COLORS["primary"],
        COLORS["blue"],
        COLORS["teal"],
        COLORS["gray"],
    )
    fig, axis = plt.subplots(figsize=(6.6, 4.2))
    for method, color in zip(methods, colors, strict=True):
        values = np.sort(
            [float(row["projector_error"]) for row in rows if row["method"] == method]
        )
        axis.plot(
            values,
            np.arange(1, len(values) + 1) / len(values),
            label=METHOD_LABELS[method],
            color=color,
            linewidth=1.8,
        )
    axis.set_xlabel("Rank-2 projector sine error")
    axis.set_ylabel("Empirical cumulative probability")
    axis.set_title("Formal error distributions (480 paired rows per method)")
    axis.legend(frameon=False, fontsize=8, loc="lower right")
    _clean_axis(axis)
    _save(fig, output, "fig03_error_cdf")


def figure_paired(rows: list[dict[str, object]], output: Path) -> None:
    paired = paired_point_means(
        rows, candidate="sr_routed25", baseline="kinetic_fourier25"
    )
    x = np.array([float(row["baseline_error"]) for row in paired])
    y = np.array([float(row["candidate_error"]) for row in paired])
    limit = max(float(x.max()), float(y.max())) * 1.04
    fig, axis = plt.subplots(figsize=(5.2, 5.0))
    for family, label, color in (
        ("harmonic_honeycomb", "Harmonic", COLORS["blue"]),
        ("gaussian_honeycomb", "Gaussian", COLORS["primary"]),
    ):
        selected = [row for row in paired if row["family"] == family]
        axis.scatter(
            [float(row["baseline_error"]) for row in selected],
            [float(row["candidate_error"]) for row in selected],
            label=label,
            color=color,
            s=18,
            alpha=0.7,
            linewidths=0,
        )
    axis.plot([0, limit], [0, limit], "--", color=COLORS["dark"], linewidth=1)
    axis.set_xlim(0, limit)
    axis.set_ylim(0, limit)
    axis.set_xlabel("Kinetic Fourier ≥25 point-mean error")
    axis.set_ylabel("SR-SC-NARR point-mean error")
    axis.set_title("Paired error over 160 physical parameter points")
    axis.legend(frameon=False, fontsize=8)
    _clean_axis(axis)
    _save(fig, output, "fig04_paired_point_error")


def figure_pareto(summary: dict[str, object], output: Path) -> None:
    methods = (
        "sr_routed25",
        "kinetic_fourier25",
        "fourier_shell3",
        "fourier_shell2",
        "sc_hybrid25",
        "long_anchor",
        "wang_xie_adapted",
        "dai_adapted",
    )
    label_specs = {
        "sr_routed25": ((7, -10), "left"),
        "kinetic_fourier25": ((-5, 13), "right"),
        "fourier_shell3": ((-5, 13), "right"),
        "fourier_shell2": (5, 5),
        "sc_hybrid25": ((0, 15), "center"),
        "long_anchor": (5, 10),
        "wang_xie_adapted": (5, -13),
        "dai_adapted": (5, 5),
    }
    method_colors = {
        "sr_routed25": COLORS["primary"],
        "kinetic_fourier25": COLORS["blue"],
        "fourier_shell3": COLORS["teal"],
        "fourier_shell2": COLORS["purple"],
        "sc_hybrid25": "#D29B36",
        "long_anchor": COLORS["gray"],
        "wang_xie_adapted": "#A07A46",
        "dai_adapted": "#5B6570",
    }
    fig, axis = plt.subplots(figsize=(6.8, 4.6))
    for method in methods:
        stored = summary["methods"][method]
        color = method_colors[method]
        axis.scatter(
            float(stored["latency_ms"]),
            float(stored["overall"]),
            s=55 if method == "sr_routed25" else 38,
            color=color,
            edgecolor=COLORS["dark"],
            linewidth=0.35,
        )
        specification = label_specs[method]
        offset = specification[0] if isinstance(specification[0], tuple) else specification
        alignment = specification[1] if isinstance(specification[0], tuple) else "left"
        axis.annotate(
            METHOD_LABELS[method],
            (float(stored["latency_ms"]), float(stored["overall"])),
            xytext=offset,
            textcoords="offset points",
            fontsize=7,
            ha=alignment,
        )
    axis.set_xscale("log")
    axis.set_xlabel("Mean CUDA latency per method–point evaluation (ms, log scale)")
    axis.set_ylabel("Mean projector sine error")
    axis.set_title("Formal accuracy–latency context on one NVIDIA A10")
    axis.set_ylim(-0.005, 0.46)
    _clean_axis(axis)
    _save(fig, output, "fig05_accuracy_latency")


def figure_family_seed(rows: list[dict[str, object]], output: Path) -> None:
    families = ("harmonic_honeycomb", "gaussian_honeycomb")
    seeds = tuple(sorted(EXPECTED_SEEDS))
    matrix = np.zeros((2, 3))
    for family_index, family in enumerate(families):
        for seed_index, seed in enumerate(seeds):
            candidate = _mean(
                rows,
                "sr_routed25",
                "projector_error",
                family=family,
                seed=seed,
            )
            baseline = _mean(
                rows,
                "kinetic_fourier25",
                "projector_error",
                family=family,
                seed=seed,
            )
            matrix[family_index, seed_index] = 100 * (baseline - candidate) / baseline
    fig, axis = plt.subplots(figsize=(5.8, 2.8))
    rendered = axis.imshow(matrix, cmap="RdYlGn", vmin=-5, vmax=60, aspect="auto")
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            axis.text(
                column,
                row,
                f"{matrix[row, column]:.1f}%",
                ha="center",
                va="center",
                color=COLORS["dark"],
                fontsize=9,
            )
    axis.set_xticks(range(3), [f"Seed {seed}" for seed in seeds])
    axis.set_yticks(range(2), ["Harmonic", "Gaussian"])
    axis.set_title("Relative improvement over kinetic Fourier ≥25")
    fig.colorbar(rendered, ax=axis, label="Improvement (%)", fraction=0.05)
    _save(fig, output, "fig06_family_seed_improvement")


def figure_route(rows: list[dict[str, object]], output: Path) -> None:
    paired = paired_point_means(
        rows, candidate="sr_routed25", baseline="kinetic_fourier25"
    )
    fig, axis = plt.subplots(figsize=(6.5, 4.2))
    for family, route, label, color in (
        (
            "harmonic_honeycomb",
            "fourier",
            "Harmonic → Fourier route (80)",
            COLORS["blue"],
        ),
        (
            "gaussian_honeycomb",
            "hybrid",
            "Gaussian → hybrid route (80)",
            COLORS["primary"],
        ),
    ):
        selected = [
            row
            for row in paired
            if row["route"] == route and row["family"] == family
        ]
        axis.scatter(
            [float(row["tail_ratio"]) for row in selected],
            [float(row["candidate_error"]) for row in selected],
            label=label,
            color=color,
            s=22,
            alpha=0.72,
            linewidths=0,
        )
    axis.axvline(0.1, linestyle="--", color=COLORS["dark"], linewidth=1)
    axis.set_xlabel("Potential Fourier tail-energy ratio beyond D6 shell 1")
    axis.set_ylabel("SR-SC-NARR point-mean projector error")
    axis.set_title("Frozen routing separates two spectral-complexity endpoints")
    axis.legend(frameon=False, fontsize=8)
    _clean_axis(axis)
    _save(fig, output, "fig07_route_tail_ratio")


def figure_gap(rows: list[dict[str, object]], output: Path) -> None:
    paired = paired_point_means(
        rows, candidate="sr_routed25", baseline="kinetic_fourier25"
    )
    paired = [
        row
        for row in paired
        if row["split"] in {"exact_cluster", "near_cluster"}
    ]
    fig, axis = plt.subplots(figsize=(6.5, 4.2))
    gap = np.array([max(float(row["internal_gap"]), 1e-12) for row in paired])
    axis.scatter(
        gap,
        [float(row["candidate_error"]) for row in paired],
        label="SR-SC-NARR",
        color=COLORS["primary"],
        s=19,
        alpha=0.62,
        linewidths=0,
    )
    axis.scatter(
        gap,
        [float(row["baseline_error"]) for row in paired],
        label="Kinetic Fourier ≥25",
        color=COLORS["blue"],
        s=17,
        alpha=0.42,
        linewidths=0,
    )
    axis.set_xscale("log")
    axis.set_xlabel("Internal rank-2 cluster gap (log scale)")
    axis.set_ylabel("Point-mean projector error")
    axis.set_title("Error near exact and near-degenerate crossings")
    axis.legend(frameon=False, fontsize=8)
    _clean_axis(axis)
    _save(fig, output, "fig08_error_vs_internal_gap")


def figure_bootstrap(summary: dict[str, object], output: Path) -> None:
    block = summary["bootstrap_vs_kinetic"]
    mean = 100 * float(block["mean"])
    low = 100 * float(block["low"])
    high = 100 * float(block["high"])
    fig, axis = plt.subplots(figsize=(6.2, 2.2))
    axis.errorbar(
        [mean],
        [0],
        xerr=[[mean - low], [high - mean]],
        fmt="o",
        color=COLORS["primary"],
        ecolor=COLORS["blue"],
        capsize=5,
        linewidth=2,
    )
    axis.axvline(10, color=COLORS["dark"], linestyle="--", linewidth=1)
    axis.set_yticks([0], ["SR-SC-NARR vs Fourier ≥25"])
    axis.set_xlabel("Relative projector-error improvement (%)")
    axis.set_title("Stratified point bootstrap: 2,000 resamples, 95% interval")
    axis.text(high + 0.3, 0, f"{mean:.2f}% [{low:.2f}, {high:.2f}]", va="center")
    _clean_axis(axis)
    _save(fig, output, "fig09_bootstrap_improvement")


def figure_routing_ablation(summary: dict[str, object], output: Path) -> None:
    methods = ("kinetic_fourier25", "sc_hybrid25", "sr_routed25")
    labels = [METHOD_LABELS[method] for method in methods]
    error = [float(summary["methods"][method]["overall"]) for method in methods]
    latency = [float(summary["methods"][method]["latency_ms"]) for method in methods]
    colors = (COLORS["blue"], "#D29B36", COLORS["primary"])
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.5), constrained_layout=True)
    axes[0].bar(labels, error, color=colors, edgecolor=COLORS["dark"], linewidth=0.3)
    axes[0].set_ylabel("Mean projector error")
    axes[0].set_title("Accuracy")
    axes[1].bar(
        labels,
        latency,
        color=colors,
        edgecolor=COLORS["dark"],
        linewidth=0.3,
    )
    axes[1].set_ylabel("Mean CUDA latency (ms)")
    axes[1].set_title("Online cost")
    for axis in axes:
        axis.tick_params(axis="x", rotation=15)
        _clean_axis(axis)
    fig.suptitle("Routing ablation: conditional selection is not a speedup")
    _save(fig, output, "fig10_routing_ablation")


def figure_family_summary(rows: list[dict[str, object]], output: Path) -> None:
    families = ("harmonic_honeycomb", "gaussian_honeycomb")
    methods = (
        "sr_routed25",
        "kinetic_fourier25",
        "fourier_shell3",
        "sc_hybrid25",
    )
    colors = (
        COLORS["primary"],
        COLORS["blue"],
        COLORS["teal"],
        "#D29B36",
    )
    x = np.arange(2)
    width = 0.19
    fig, axis = plt.subplots(figsize=(6.8, 4.0))
    for index, (method, color) in enumerate(zip(methods, colors, strict=True)):
        values = [
            _mean(rows, method, "projector_error", family=family)
            for family in families
        ]
        axis.bar(
            x + (index - 1.5) * width,
            values,
            width,
            label=METHOD_LABELS[method],
            color=color,
            edgecolor=COLORS["dark"],
            linewidth=0.25,
        )
    axis.set_xticks(x, ["Harmonic", "Gaussian"])
    axis.set_ylabel("Mean projector sine error")
    axis.set_title("Family-specific formal results reveal conditional neural gain")
    axis.legend(frameon=False, fontsize=8, ncol=2)
    _clean_axis(axis)
    _save(fig, output, "fig11_family_specific_results")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, default=Path("paper/v3_formal"))
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("artifacts/v3-symmetry-formal-evidence.tar.gz"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("figures/v3_formal"))
    parser.add_argument("--table-dir", type=Path, default=Path("paper/v3_formal/tables"))
    parser.add_argument(
        "--convergence",
        type=Path,
        default=Path("benchmarks/v3_symmetry_convergence_audit.json"),
    )
    args = parser.parse_args()
    _style()
    rows = read_rows(args.result_dir / "rows.csv")
    summary, provenance = validate_inputs(args.result_dir, args.evidence, rows)
    convergence = validate_convergence(
        args.convergence,
        provenance=provenance,
        evidence_path=args.evidence,
    )
    write_tables(rows, summary, args.table_dir, convergence)
    figure_overall(summary, args.output_dir)
    figure_splits(summary, args.output_dir)
    figure_cdf(rows, args.output_dir)
    figure_paired(rows, args.output_dir)
    figure_pareto(summary, args.output_dir)
    figure_family_seed(rows, args.output_dir)
    figure_route(rows, args.output_dir)
    figure_gap(rows, args.output_dir)
    figure_bootstrap(summary, args.output_dir)
    figure_routing_ablation(summary, args.output_dir)
    figure_family_summary(rows, args.output_dir)
    print(f"V3_FIGURES={args.output_dir}")
    print(f"V3_TABLES={args.table_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

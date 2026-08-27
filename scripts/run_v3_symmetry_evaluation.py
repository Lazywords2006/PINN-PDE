#!/usr/bin/env python3
"""Evaluate the symmetry-corrected neural-augmented Ritz solver."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import statistics
import subprocess
import sys
import tarfile
import time
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.device import select_device
from block_kyfan_pinn.experiment import ExperimentConfig
from block_kyfan_pinn.metrics import orthogonality_error, projector_sine_error
from block_kyfan_pinn.model import GalerkinSubspacePINN, GeneralizedTracePINN
from block_kyfan_pinn.p2_refinement import (
    d6_hex_shell_modes,
    fourier_only_ritz_fast,
    neural_augmented_ritz_fast,
    potential_spectral_tail_ratio,
)
from block_kyfan_pinn.physics import (
    apply_hamiltonian,
    galerkin_rank_basis,
    hermitian_ritz_matrix,
    periodic_mgs,
    projected_residual_rms,
    ritz_matrix,
)
from block_kyfan_pinn.reference import uniform_grid
from block_kyfan_pinn.suites import file_sha256, load_frozen_suite
from block_kyfan_pinn.symmetry import lowest_kinetic_modes
from block_kyfan_pinn.v3_protocol import (
    V3_FORMAL_POINT_DIGEST,
    V3_FORMAL_PURPOSE,
    V3_FORMAL_SEED,
    V3_FORMAL_SPLIT_COUNTS,
    V3_FORMAL_SUITE_ID,
    V3_GLOBAL_OPENING_MARKER,
    V3_MODE_POLICY,
    physical_point_digest,
)
from scripts.evaluate_risk_features import load_p5_checkpoint

METHODS = (
    "long_anchor",
    "sc_narr_shell1",
    "sc_narr",
    "sc_hybrid25",
    "sr_routed25",
    "fourier_shell2",
    "kinetic_fourier21",
    "kinetic_fourier25",
    "fourier_shell3",
    "wang_xie_adapted",
    "dai_adapted",
)
SEEDS = (42, 137, 251)
EXPECTED_P5_ARCHIVE_SHA256 = (
    "56891c5740eb94c62299b72869d790a1cbdee6abda3fae2903ed822f5e405101"
)
EXPECTED_Q3_ARCHIVE_SHA256 = (
    "282cdd418eaa11a68498ee7fbc0198dfc1f362a535385756a7cc38275806afe0"
)


def _percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
    index = max(0, min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def build_gate(summary: dict[str, object]) -> dict[str, object]:
    """Apply the preregistered corrected-method success criteria."""

    methods = summary["methods"]
    if not isinstance(methods, dict):
        raise TypeError("summary methods must be a mapping")
    sc = methods["sr_routed25"]
    controls = [
        methods["long_anchor"],
        methods["fourier_shell2"],
        methods["kinetic_fourier25"],
        methods["wang_xie_adapted"],
    ]
    checks = {
        "identity_complete": bool(summary["identity_complete"]),
        "finite_metrics": bool(summary["finite_metrics"]),
        "orthogonality_pass": float(summary["maximum_orthogonality_error"])
        < 1e-4,
        "raw_hermiticity_pass": float(sc["max_raw_hermiticity_defect"])
        < 1e-4,
        "external_isolation_pass": float(summary["minimum_external_gap"]) > 1e-2,
        "absolute_projector_pass": float(sc["overall"]) < 0.06,
        "absolute_eigenvalue_pass": float(sc["eigenvalue_mae"]) < 0.02,
        "all_strong_controls_pass": all(
            float(sc["overall"]) < float(control["overall"])
            for control in controls
        ),
        "near_controls_pass": all(float(sc["near_cluster"]) < float(control["near_cluster"]) for control in controls),
        "tail_pass": float(sc["p95"]) < 0.15 and float(sc["maximum"]) < 0.25,
        "kinetic_control_margin_pass": (
            float(methods["kinetic_fourier25"]["overall"])
            - float(sc["overall"])
        )
        / float(methods["kinetic_fourier25"]["overall"])
        >= 0.10,
        "all_split_kinetic_control_pass": bool(
            summary["all_split_kinetic_control_pass"]
        ),
        "family_seed_wins_pass": int(summary["family_seed_wins_vs_kinetic"]) >= 3
        and int(summary["family_seed_nonregressions_vs_kinetic"]) == 6,
        "bootstrap_margin_pass": float(summary["bootstrap_vs_kinetic"]["low"])
        >= 0.10,
        "higher_rank_pareto_context_pass": float(sc["overall"])
        <= 1.25 * float(methods["fourier_shell3"]["overall"])
        and float(sc["eigenvalue_mae"])
        <= float(methods["fourier_shell3"]["eigenvalue_mae"])
        and float(sc["latency_ms"])
        <= 0.90 * float(methods["fourier_shell3"]["latency_ms"]),
    }
    return {**checks, "promotion_go": all(checks.values())}


def _load_references(
    suite_path: Path, cache_path: Path
) -> tuple[dict[str, object], list[dict[str, object]], dict[str, object]]:
    suite, suite_hash = load_frozen_suite(suite_path)
    cache_hash = file_sha256(cache_path)
    tokens = cache_path.with_suffix(".sha256").read_text().split()
    if not tokens or tokens[0] != cache_hash:
        raise ValueError("reference cache sidecar mismatch")
    payload = torch.load(cache_path, map_location="cpu", weights_only=True)
    if not isinstance(payload, dict):
        raise TypeError("reference cache root must be a mapping")
    metadata = payload.get("metadata")
    references = payload.get("references")
    if not isinstance(metadata, dict) or not isinstance(references, dict):
        raise TypeError("reference cache is malformed")
    expected = {
        "suite_id": suite["suite_id"],
        "suite_sha256": suite_hash,
        "grid_side": 65,
        "cutoff": 24,
        "rank": 3,
        "point_count": len(suite["points"]),
        "mode_shape": "hexagonal_d6",
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValueError(f"reference metadata mismatch for {key}")
    if set(references) != {str(point["id"]) for point in suite["points"]}:
        raise ValueError("reference identity set is incomplete")
    points = list(suite["points"])
    parameter_identities = {
        (
            str(point["family"]),
            tuple(round(float(value), 14) for value in point["parameters"]),
        )
        for point in points
    }
    if len(parameter_identities) != len(points):
        raise ValueError("suite contains duplicate physical parameter points")
    return suite, points, references


def _validate_formal_suite(suite: dict[str, object], points: Sequence[dict[str, object]]) -> None:
    if suite.get("purpose") != V3_FORMAL_PURPOSE:
        raise ValueError("formal run received a non-confirmation suite")
    if suite.get("suite_id") != V3_FORMAL_SUITE_ID:
        raise ValueError("formal confirmation suite ID is incorrect")
    if suite.get("generation_seed") != V3_FORMAL_SEED:
        raise ValueError("formal confirmation generation seed is incorrect")
    if suite.get("mode_policy") != V3_MODE_POLICY:
        raise ValueError("formal confirmation mode policy is incorrect")
    if suite.get("protocol_version") != 2:
        raise ValueError("formal confirmation protocol version is incorrect")
    if physical_point_digest(points) != V3_FORMAL_POINT_DIGEST:
        raise ValueError("formal confirmation physical point digest is incorrect")
    if len(points) != 160:
        raise ValueError("formal confirmation must contain 160 points")
    split_counts = {
        split: sum(point["split"] == split for point in points)
        for split in sorted(V3_FORMAL_SPLIT_COUNTS)
    }
    if split_counts != V3_FORMAL_SPLIT_COUNTS:
        raise ValueError("formal confirmation split matrix is incorrect")
    family_counts = {
        family: sum(point["family"] == family for point in points)
        for family in ("gaussian_honeycomb", "harmonic_honeycomb")
    }
    if family_counts != {
        "gaussian_honeycomb": 80,
        "harmonic_honeycomb": 80,
    }:
        raise ValueError("formal confirmation family matrix is incorrect")
    expected_cells = {
        (family, split): count // 2
        for family in ("gaussian_honeycomb", "harmonic_honeycomb")
        for split, count in V3_FORMAL_SPLIT_COUNTS.items()
    }
    actual_cells = {
        (family, split): sum(
            point["family"] == family and point["split"] == split
            for point in points
        )
        for family, split in expected_cells
    }
    if actual_cells != expected_cells:
        raise ValueError("formal confirmation family-by-split matrix is incorrect")


def _synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elif device.type == "mps":
        torch.mps.synchronize()


def _basis_for_method(
    method: str,
    model: torch.nn.Module,
    coordinates: torch.Tensor,
    parameters: torch.Tensor,
    family: str,
) -> tuple[torch.Tensor, int]:
    if method == "fourier_shell2":
        return (
            fourier_only_ritz_fast(
                coordinates, parameters, family, d6_hex_shell_modes(2)
            ),
            19,
        )
    if method in {"kinetic_fourier21", "kinetic_fourier25"}:
        minimum_rank = 21 if method == "kinetic_fourier21" else 25
        modes = lowest_kinetic_modes(
            parameters[0, :2].detach().cpu().tolist(),
            rank=minimum_rank,
            candidate_shell=4,
        )
        return fourier_only_ritz_fast(
            coordinates, parameters, family, modes
        ), len(modes)
    if method == "fourier_shell3":
        modes = d6_hex_shell_modes(3)
        return fourier_only_ritz_fast(
            coordinates, parameters, family, modes
        ), len(modes)
    if method == "sr_routed25":
        pure_modes = lowest_kinetic_modes(
            parameters[0, :2].detach().cpu().tolist(),
            rank=25,
            candidate_shell=4,
        )
        tail_ratio = potential_spectral_tail_ratio(
            coordinates, parameters, family
        )
        if float(tail_ratio.detach().cpu()[0]) <= 0.1:
            return fourier_only_ritz_fast(
                coordinates, parameters, family, pure_modes
            ), len(pure_modes)

    raw_output = model(coordinates, parameters)
    if method == "dai_adapted":
        return (
            galerkin_rank_basis(
                raw_output,
                coordinates,
                parameters,
                family,
                target_rank=2,
            ),
            int(raw_output.shape[2]),
        )
    neural = periodic_mgs(raw_output)
    if method == "wang_xie_adapted":
        return neural, 2
    if method == "long_anchor":
        return neural, 2
    if method == "sc_narr_shell1":
        basis, details = neural_augmented_ritz_fast(
            neural, coordinates, parameters, family, d6_hex_shell_modes(1)
        )
        return basis, int(details["trial_rank"])
    if method == "sc_narr":
        basis, details = neural_augmented_ritz_fast(
            neural, coordinates, parameters, family, d6_hex_shell_modes(2)
        )
        return basis, int(details["trial_rank"])
    if method in {"sc_hybrid25", "sr_routed25"}:
        hybrid_modes = sorted(
            set(d6_hex_shell_modes(2))
            | set(
                lowest_kinetic_modes(
                    parameters[0, :2].detach().cpu().tolist(),
                    rank=21,
                    candidate_shell=4,
                )
            )
        )
        if method == "sc_hybrid25":
            basis, details = neural_augmented_ritz_fast(
                neural, coordinates, parameters, family, hybrid_modes
            )
            return basis, int(details["trial_rank"])
        basis, details = neural_augmented_ritz_fast(
            neural, coordinates, parameters, family, hybrid_modes
        )
        return basis, int(details["trial_rank"])
    raise ValueError(f"unknown method: {method}")


def _evaluate(
    method: str,
    model: torch.nn.Module,
    point: dict[str, object],
    reference: dict[str, object],
    *,
    seed: int,
    device: torch.device,
) -> dict[str, object]:
    coordinates = uniform_grid(65).unsqueeze(0).to(device).requires_grad_()
    parameters = torch.tensor(
        [point["parameters"]], device=device, dtype=torch.float32
    )
    family = str(point["family"])
    _synchronize(device)
    started = time.perf_counter()
    basis, trial_rank = _basis_for_method(
        method, model, coordinates, parameters, family
    )
    _synchronize(device)
    latency_ms = 1000.0 * (time.perf_counter() - started)
    h_basis = apply_hamiltonian(basis, coordinates, parameters, family)
    raw_real, raw_imag = ritz_matrix(basis, h_basis)
    raw_matrix = torch.complex(raw_real, raw_imag)
    raw_for_norm = raw_matrix.cpu() if raw_matrix.device.type == "mps" else raw_matrix
    denominator = torch.linalg.matrix_norm(raw_for_norm).clamp_min(1e-12)
    hermiticity_defect = float(
        (torch.linalg.matrix_norm(raw_for_norm - raw_for_norm.mH) / denominator)
        .detach()
        .cpu()
    )
    matrix = hermitian_ritz_matrix(basis, h_basis)
    if matrix.device.type == "mps":
        matrix = matrix.cpu()
    ritz_values = torch.linalg.eigvalsh(matrix).real[0, :2]
    reference_basis = reference["basis"]
    reference_values = reference["eigenvalues"]
    if not isinstance(reference_basis, torch.Tensor) or not isinstance(
        reference_values, torch.Tensor
    ):
        raise TypeError("reference tensors are missing")
    target = reference_basis[..., :2, :].unsqueeze(0).to(
        device=device, dtype=basis.dtype
    )
    exact_values = reference_values[:2].to(
        device=ritz_values.device, dtype=ritz_values.dtype
    )
    errors = (ritz_values - exact_values).abs()
    tail_ratio = (
        float(
            potential_spectral_tail_ratio(
                coordinates, parameters, family
            ).detach().cpu()[0]
        )
        if method == "sr_routed25"
        else math.nan
    )
    return {
        "method": method,
        "family": family,
        "seed": seed,
        "split": str(point["split"]),
        "point_id": str(point["id"]),
        "projector_error": projector_sine_error(basis, target),
        "e1_abs_error": float(errors[0].detach().cpu()),
        "e2_abs_error": float(errors[1].detach().cpu()),
        "trace_abs_error": float(errors.sum().detach().cpu()),
        "residual_rms": float(projected_residual_rms(basis, h_basis).detach().cpu()),
        "orthogonality_error": orthogonality_error(basis),
        "hermiticity_defect_raw": hermiticity_defect,
        "internal_gap": float(reference["internal_gap"]),
        "external_gap": float(reference["external_gap"]),
        "trial_rank": trial_rank,
        "route": (
            "hybrid"
            if method == "sr_routed25" and tail_ratio > 0.1
            else "fourier"
            if method == "sr_routed25"
            else "not_applicable"
        ),
        "tail_ratio": tail_ratio,
        "latency_ms": latency_ms,
    }


def _stratified_bootstrap(
    rows: Sequence[dict[str, object]],
    *,
    baseline: str,
    samples: int = 2000,
) -> dict[str, float | int]:
    by_method_point: dict[tuple[str, str], list[float]] = defaultdict(list)
    strata: dict[tuple[str, str], list[str]] = defaultdict(list)
    point_metadata: dict[str, tuple[str, str]] = {}
    for row in rows:
        point = str(row["point_id"])
        method = str(row["method"])
        by_method_point[(method, point)].append(float(row["projector_error"]))
        point_metadata[point] = (str(row["family"]), str(row["split"]))
    for point, stratum in point_metadata.items():
        strata[stratum].append(point)
    point_means = {
        key: statistics.mean(values) for key, values in by_method_point.items()
    }
    rng = random.Random(20260827)
    improvements = []
    for _ in range(samples):
        selected = [
            rng.choice(points)
            for points in strata.values()
            for _ in range(len(points))
        ]
        candidate = statistics.mean(
            point_means[("sr_routed25", point)] for point in selected
        )
        comparison = statistics.mean(point_means[(baseline, point)] for point in selected)
        if comparison > 0.0:
            improvements.append((comparison - candidate) / comparison)
    return {
        "mean": statistics.mean(improvements),
        "low": _percentile(improvements, 0.025),
        "high": _percentile(improvements, 0.975),
        "samples": len(improvements),
        "strata": len(strata),
    }


def summarize(
    rows: Sequence[dict[str, object]], points: Sequence[dict[str, object]]
) -> dict[str, object]:
    expected = {
        (method, seed, str(point["id"]))
        for method in METHODS
        for seed in SEEDS
        for point in points
    }
    actual = {
        (str(row["method"]), int(row["seed"]), str(row["point_id"]))
        for row in rows
    }
    by_method: dict[str, dict[str, float]] = {}
    for method in METHODS:
        selected = [row for row in rows if row["method"] == method]
        errors = [float(row["projector_error"]) for row in selected]
        eigen_errors = [
            value
            for row in selected
            for value in (float(row["e1_abs_error"]), float(row["e2_abs_error"]))
        ]
        record = {
            "overall": statistics.mean(errors),
            "median": statistics.median(errors),
            "p95": _percentile(errors, 0.95),
            "maximum": max(errors),
            "eigenvalue_mae": statistics.mean(eigen_errors),
            "residual_rms": statistics.mean(
                float(row["residual_rms"]) for row in selected
            ),
            "latency_ms": statistics.mean(
                float(row["latency_ms"]) for row in selected
            ),
            "max_raw_hermiticity_defect": max(
                float(row["hermiticity_defect_raw"]) for row in selected
            ),
            "minimum_trial_rank": min(int(row["trial_rank"]) for row in selected),
            "maximum_trial_rank": max(int(row["trial_rank"]) for row in selected),
        }
        for split in sorted({str(point["split"]) for point in points}):
            record[split] = statistics.mean(
                float(row["projector_error"])
                for row in selected
                if row["split"] == split
            )
        by_method[method] = record
        if method == "sr_routed25":
            record["hybrid_route_count"] = sum(
                row["route"] == "hybrid" for row in selected
            )
            record["fourier_route_count"] = sum(
                row["route"] == "fourier" for row in selected
            )
    numeric_keys = (
        "projector_error",
        "e1_abs_error",
        "e2_abs_error",
        "residual_rms",
        "orthogonality_error",
        "hermiticity_defect_raw",
        "external_gap",
    )
    summary: dict[str, object] = {
        "identity_complete": actual == expected
        and len(rows) == len(expected)
        and len(actual) == len(rows),
        "row_count": len(rows),
        "finite_metrics": all(
            math.isfinite(float(row[key])) for row in rows for key in numeric_keys
        ),
        "maximum_orthogonality_error": max(
            float(row["orthogonality_error"]) for row in rows
        ),
        "maximum_raw_hermiticity_defect": max(
            float(row["hermiticity_defect_raw"]) for row in rows
        ),
        "minimum_external_gap": min(float(row["external_gap"]) for row in rows),
        "methods": by_method,
    }
    splits = sorted({str(point["split"]) for point in points})
    summary["all_split_kinetic_control_pass"] = all(
        by_method["sr_routed25"][split]
        <= by_method["kinetic_fourier25"][split] + 1e-6
        for split in splits
    )
    wins = 0
    nonregressions = 0
    for family in sorted({str(point["family"]) for point in points}):
        for seed in SEEDS:
            candidate = statistics.mean(
                float(row["projector_error"])
                for row in rows
                if row["method"] == "sr_routed25"
                and row["family"] == family
                and int(row["seed"]) == seed
            )
            baseline = statistics.mean(
                float(row["projector_error"])
                for row in rows
                if row["method"] == "kinetic_fourier25"
                and row["family"] == family
                and int(row["seed"]) == seed
            )
            wins += candidate < baseline - 1e-6
            nonregressions += candidate <= baseline + 1e-6
    summary["family_seed_wins_vs_kinetic"] = wins
    summary["family_seed_nonregressions_vs_kinetic"] = nonregressions
    summary["bootstrap_vs_kinetic"] = _stratified_bootstrap(
        rows, baseline="kinetic_fourier25"
    )
    return summary


def _write_rows(rows: Sequence[dict[str, object]], path: Path) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _source_fingerprint(root: Path) -> str:
    paths = sorted((root / "block_kyfan_pinn").glob("*.py"))
    paths.extend(
        root / "scripts" / name
        for name in (
            "generate_v3_symmetry_assets.py",
            "run_v3_symmetry_evaluation.py",
            "audit_v3_convergence.py",
            "evaluate_risk_features.py",
        )
    )
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda value: str(value.relative_to(root))):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _load_adapted_baselines(
    training_root: Path, device: torch.device
) -> dict[tuple[str, str, int], torch.nn.Module]:
    configurations = training_root.parent / "configs"
    models: dict[tuple[str, str, int], torch.nn.Module] = {}
    for method, config_prefix in (
        ("wang_xie_adapted", "wang_xie_trace_adapted"),
        ("dai_adapted", "dai_galerkin_adapted"),
    ):
        training_name = "wang_xie_trace" if method == "wang_xie_adapted" else "dai_galerkin"
        for family in ("harmonic_honeycomb", "gaussian_honeycomb"):
            config = ExperimentConfig.from_json(
                configurations / f"{config_prefix}_{family}.json"
            )
            for seed in SEEDS:
                checkpoint = training_root / training_name / family / f"seed_{seed}" / "final.pt"
                state = torch.load(
                    checkpoint, map_location=device, weights_only=True
                )
                embedded = state.get("config")
                if not isinstance(embedded, dict):
                    raise TypeError("adapted checkpoint has no embedded config")
                for key in (
                    "method",
                    "potential_family",
                    "width",
                    "hidden_layers",
                    "subspace_rank",
                ):
                    if embedded.get(key) != getattr(config, key):
                        raise ValueError(f"adapted checkpoint mismatch for {key}")
                recorded = state.get("config_fingerprint")
                computed = hashlib.sha256(
                    json.dumps(
                        embedded, sort_keys=True, separators=(",", ":")
                    ).encode()
                ).hexdigest()
                if recorded != computed:
                    raise ValueError("adapted checkpoint config fingerprint mismatch")
                parameter_dim = len(config.parameter_lower)
                if method == "wang_xie_adapted":
                    model = GeneralizedTracePINN(
                        width=config.width,
                        hidden_layers=config.hidden_layers,
                        parameter_dim=parameter_dim,
                    )
                else:
                    model = GalerkinSubspacePINN(
                        width=config.width,
                        hidden_layers=config.hidden_layers,
                        parameter_dim=parameter_dim,
                        subspace_rank=config.subspace_rank,
                    )
                model.load_state_dict(state["model"])
                model = model.to(device=device, dtype=torch.float32).eval()
                models[(method, family, seed)] = model
    return models


def _verify_q3_training_root(training_root: Path, archive_path: Path) -> None:
    if file_sha256(archive_path) != EXPECTED_Q3_ARCHIVE_SHA256:
        raise ValueError("unexpected Q3 evidence archive")
    with tarfile.open(archive_path, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        for local in sorted(training_root.rglob("final.pt")):
            relative = local.relative_to(training_root)
            member_name = f"results/q3_supplement_formal/training/{relative}"
            member = members.get(member_name)
            if member is None:
                raise ValueError(f"Q3 archive is missing {member_name}")
            handle = archive.extractfile(member)
            if handle is None:
                raise ValueError(f"Q3 archive member is unreadable: {member_name}")
            if hashlib.sha256(handle.read()).hexdigest() != file_sha256(local):
                raise ValueError(f"Q3 checkpoint mismatch: {relative}")


def _prepare_formal_opening(
    *, root: Path, suite_path: Path, cache_path: Path, output: Path
) -> Path:
    status = subprocess.run(
        ("git", "status", "--porcelain"),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if status:
        raise RuntimeError("formal confirmation requires a clean Git checkout")
    if output.exists():
        raise FileExistsError("formal output directory already exists")
    archive_path = output.parent / f"{output.name}-evidence.tar.gz"
    archive_sidecar = archive_path.with_suffix(archive_path.suffix + ".sha256")
    if archive_path.exists() or archive_sidecar.exists():
        raise FileExistsError("formal evidence bundle target already exists")
    marker = root / "benchmarks" / V3_GLOBAL_OPENING_MARKER
    if marker.exists():
        raise RuntimeError("formal confirmation suite has already been opened")
    commit = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    marker.write_text(
        json.dumps(
            {
                "status": "OPENED_FOR_SINGLE_CONFIRMATION",
                "git_commit": commit,
                "suite_sha256": file_sha256(suite_path),
                "reference_sha256": file_sha256(cache_path),
                "source_fingerprint": _source_fingerprint(root),
                "opened_unix_time": time.time(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    return marker


def _cuda_static_provenance(device: torch.device) -> dict[str, object]:
    if device.type != "cuda":
        return {}
    index = device.index if device.index is not None else torch.cuda.current_device()
    properties = torch.cuda.get_device_properties(index)
    driver = subprocess.run(
        (
            "nvidia-smi",
            "--query-gpu=driver_version",
            "--format=csv,noheader",
            f"--id={index}",
        ),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {
        "cuda_runtime": torch.version.cuda,
        "driver": driver,
        "device_index": index,
        "device_name": properties.name,
        "compute_capability": list(torch.cuda.get_device_capability(index)),
        "total_memory_bytes": properties.total_memory,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--reference-cache", type=Path, required=True)
    parser.add_argument("--p5-archive", type=Path, required=True)
    parser.add_argument("--checkpoint-inventory", type=Path, required=True)
    parser.add_argument("--q3-training-root", type=Path, required=True)
    parser.add_argument("--q3-evidence", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--device", choices=("auto", "cpu", "mps", "cuda", "rocm"), default="auto"
    )
    parser.add_argument("--formal", action="store_true")
    parser.add_argument("--formal-manifest", type=Path)
    parser.add_argument("--convergence-audit", type=Path)
    args = parser.parse_args()
    suite, points, references = _load_references(
        args.suite.resolve(), args.reference_cache.resolve()
    )
    if args.formal:
        _validate_formal_suite(suite, points)
        if args.formal_manifest is None or args.convergence_audit is None:
            parser.error(
                "--formal requires --formal-manifest and --convergence-audit"
            )
        manifest = json.loads(args.formal_manifest.read_text())
        expected_manifest = {
            "suite_sha256": file_sha256(args.suite.resolve()),
            "reference_sha256": file_sha256(args.reference_cache.resolve()),
            "source_fingerprint": _source_fingerprint(
                Path(__file__).resolve().parents[1]
            ),
            "point_count": 160,
            "suite_id": V3_FORMAL_SUITE_ID,
            "generation_seed": V3_FORMAL_SEED,
            "purpose": V3_FORMAL_PURPOSE,
            "mode_policy": V3_MODE_POLICY,
            "physical_point_digest": V3_FORMAL_POINT_DIGEST,
        }
        for key, value in expected_manifest.items():
            if manifest.get(key) != value:
                raise ValueError(f"formal manifest mismatch for {key}")
        convergence_path = args.convergence_audit.resolve()
        convergence_hash = file_sha256(convergence_path)
        declared_convergence = convergence_path.with_suffix(".sha256").read_text().split()[0]
        if convergence_hash != declared_convergence:
            raise ValueError("convergence audit sidecar mismatch")
        if manifest.get("convergence_audit_sha256") != convergence_hash:
            raise ValueError("formal manifest does not bind convergence evidence")
        convergence_payload = json.loads(convergence_path.read_text())
        if not bool(convergence_payload.get("gate", {}).get("convergence_go")):
            raise ValueError("required convergence audit did not pass")
        if (
            convergence_payload.get("provenance", {}).get("source_fingerprint")
            != expected_manifest["source_fingerprint"]
        ):
            raise ValueError("convergence source fingerprint mismatch")
    inventory = json.loads(args.checkpoint_inventory.read_text())
    p5_sidecar = args.p5_archive.with_suffix(args.p5_archive.suffix + ".sha256")
    declared_p5 = p5_sidecar.read_text().split()[0]
    actual_p5 = file_sha256(args.p5_archive.resolve())
    if declared_p5 != actual_p5:
        raise ValueError("P5 archive sidecar mismatch")
    if args.formal and actual_p5 != EXPECTED_P5_ARCHIVE_SHA256:
        raise ValueError("unexpected P5 evidence archive")
    device = select_device(args.device)
    if args.formal and device.type != "cuda":
        raise RuntimeError("formal confirmation requires CUDA")
    models = {
        (str(row["family"]), int(row["seed"])): load_p5_checkpoint(
            args.p5_archive.resolve(), row, device
        )
        for row in inventory
        if row.get("method") == "p5_long_anchor"
    }
    adapted_models = _load_adapted_baselines(
        args.q3_training_root.resolve(), device
    )
    if args.formal:
        if args.q3_evidence is None:
            parser.error("--formal requires --q3-evidence")
        _verify_q3_training_root(
            args.q3_training_root.resolve(), args.q3_evidence.resolve()
        )
    output = args.output_dir.resolve()
    cuda_static = _cuda_static_provenance(device)
    if args.formal:
        _prepare_formal_opening(
            root=Path(__file__).resolve().parents[1],
            suite_path=args.suite.resolve(),
            cache_path=args.reference_cache.resolve(),
            output=output,
        )
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    rows: list[dict[str, object]] = []
    for family in ("harmonic_honeycomb", "gaussian_honeycomb"):
        family_points = [point for point in points if point["family"] == family]
        for seed in SEEDS:
            model = models[(family, seed)]
            for point in family_points:
                offset = (
                    seed + sum(str(point["id"]).encode("utf-8"))
                ) % len(METHODS)
                method_order = METHODS[offset:] + METHODS[:offset]
                for method in method_order:
                    selected_model = (
                        adapted_models[(method, family, seed)]
                        if method in {"wang_xie_adapted", "dai_adapted"}
                        else model
                    )
                    rows.append(
                        _evaluate(
                            method,
                            selected_model,
                            point,
                            references[str(point["id"])],
                            seed=seed,
                            device=device,
                        )
                    )
            print(f"EVALUATED={family}:seed{seed}", flush=True)
    summary = summarize(rows, points)
    raw_gate = build_gate(summary)
    if args.formal:
        raw_gate["convergence_pass"] = True
        raw_gate["promotion_go"] = bool(raw_gate["promotion_go"])
    gate = (
        raw_gate
        if args.formal
        else {
            **raw_gate,
            "pilot_go": bool(raw_gate["promotion_go"]),
            "promotion_go": False,
        }
    )
    output.mkdir(parents=True, exist_ok=True)
    _write_rows(rows, output / "rows.csv")
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    (output / "gate.json").write_text(
        json.dumps(gate, ensure_ascii=False, indent=2) + "\n"
    )
    commit = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    checkpoint_hashes = {
        str(path.relative_to(args.q3_training_root.resolve())): file_sha256(path)
        for path in sorted(args.q3_training_root.resolve().rglob("final.pt"))
    }
    cuda_provenance = dict(cuda_static)
    if device.type == "cuda":
        cuda_provenance.update(
            {
                "peak_allocated_bytes": torch.cuda.max_memory_allocated(device),
                "peak_reserved_bytes": torch.cuda.max_memory_reserved(device),
            }
        )
    provenance = {
        "formal": args.formal,
        "git_commit": commit,
        "git_status_before_open": "clean" if args.formal else "not_required",
        "source_fingerprint": _source_fingerprint(
            Path(__file__).resolve().parents[1]
        ),
        "suite_sha256": file_sha256(args.suite.resolve()),
        "reference_sha256": file_sha256(args.reference_cache.resolve()),
        "p5_archive_sha256": file_sha256(args.p5_archive.resolve()),
        "checkpoint_inventory_sha256": file_sha256(
            args.checkpoint_inventory.resolve()
        ),
        "adapted_checkpoint_sha256": checkpoint_hashes,
        "formal_manifest_sha256": (
            file_sha256(args.formal_manifest.resolve())
            if args.formal_manifest is not None
            else None
        ),
        "convergence_audit_sha256": (
            file_sha256(args.convergence_audit.resolve())
            if args.convergence_audit is not None
            else None
        ),
        "device": str(device),
        "torch": torch.__version__,
        "platform": platform.platform(),
        "cuda": cuda_provenance,
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n"
    )
    evidence_files = [
        output / name
        for name in ("rows.csv", "summary.json", "gate.json", "provenance.json")
    ]
    bound_inputs = [
        args.suite.resolve(),
        args.suite.resolve().with_suffix(".sha256"),
        args.reference_cache.resolve(),
        args.reference_cache.resolve().with_suffix(".sha256"),
    ]
    if args.formal:
        if args.formal_manifest is None or args.convergence_audit is None:
            raise RuntimeError("formal evidence inputs disappeared")
        bound_inputs.extend(
            (
                args.formal_manifest.resolve(),
                args.convergence_audit.resolve(),
                args.convergence_audit.resolve().with_suffix(".sha256"),
                Path(__file__).resolve().parents[1]
                / "benchmarks"
                / V3_GLOBAL_OPENING_MARKER,
            )
        )
    evidence_manifest = {
        "files": [
            {
                "kind": "result",
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in evidence_files
        ]
        + [
            {
                "kind": "bound_input",
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in bound_inputs
        ],
    }
    manifest_path = output / "evidence-manifest.json"
    manifest_path.write_text(
        json.dumps(evidence_manifest, ensure_ascii=False, indent=2) + "\n"
    )
    archive_path = output.parent / f"{output.name}-evidence.tar.gz"
    archive_sidecar = archive_path.with_suffix(archive_path.suffix + ".sha256")
    if archive_path.exists() or archive_sidecar.exists():
        raise FileExistsError("evidence bundle target already exists")
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in [*evidence_files, manifest_path]:
            archive.add(path, arcname=f"results/{path.name}")
        for index, path in enumerate(bound_inputs):
            archive.add(path, arcname=f"inputs/{index:02d}_{path.name}")
    archive_hash = file_sha256(archive_path)
    archive_sidecar.write_text(f"{archive_hash}  {archive_path.name}\n")
    decision_name = "PROMOTION_GO" if args.formal else "PILOT_GO"
    decision = gate["promotion_go"] if args.formal else gate["pilot_go"]
    print(f"{decision_name}={decision}")
    print(f"OUTPUT={output}")
    print(f"EVIDENCE_BUNDLE={archive_path}")
    print(f"EVIDENCE_SHA256={archive_hash}")
    return 0 if decision else 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Reference-cutoff and grid-convergence audit for the corrected solver."""

from __future__ import annotations

import argparse
import json
import sys
import tarfile
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.metrics import projector_sine_error
from block_kyfan_pinn.p2_refinement import (
    d6_hex_shell_modes,
    spectral_routed_neural_fourier_ritz,
)
from block_kyfan_pinn.physics import (
    apply_hamiltonian,
    hermitian_ritz_matrix,
    periodic_mgs,
    ritz_matrix,
)
from block_kyfan_pinn.reference import (
    evaluate_reference_basis,
    solve_reference,
    uniform_grid,
)
from block_kyfan_pinn.suites import file_sha256, load_frozen_suite
from block_kyfan_pinn.symmetry import lowest_kinetic_modes
from scripts.evaluate_risk_features import load_p5_checkpoint

EXPECTED_P5_ARCHIVE_SHA256 = (
    "56891c5740eb94c62299b72869d790a1cbdee6abda3fae2903ed822f5e405101"
)


def build_convergence_gate(summary: dict[str, object]) -> dict[str, object]:
    checks = {
        "reference_projector_pass": float(
            summary["max_reference_projector_24_28"]
        )
        < 1e-3,
        "reference_eigenvalue_pass": float(
            summary["max_reference_eigenvalue_24_28"]
        )
        < 1e-5,
        "solver_projector_grid_pass": float(
            summary["max_solver_projector_grid_difference"]
        )
        < 1e-3,
        "solver_eigenvalue_grid_pass": float(
            summary["max_solver_eigenvalue_grid_difference"]
        )
        < 1e-4,
        "raw_hermiticity_pass": float(summary["max_raw_hermiticity_defect"])
        < 1e-4,
    }
    return {**checks, "convergence_go": all(checks.values())}


def _reference_basis(solution: object, side: int) -> torch.Tensor:
    grid = uniform_grid(side, dtype=torch.float64).unsqueeze(0)
    return periodic_mgs(evaluate_reference_basis(solution, grid))[:, :, :2]


def _periodic_resample_basis(
    basis: torch.Tensor, *, source_side: int, target_side: int
) -> torch.Tensor:
    if target_side < source_side or (target_side - source_side) % 2:
        raise ValueError("target grid must provide symmetric odd-grid padding")
    values = torch.complex(basis[0, ..., 0], basis[0, ..., 1]).reshape(
        source_side, source_side, basis.shape[2]
    )
    coefficients = torch.fft.fftshift(
        torch.fft.fft2(values, dim=(0, 1), norm="forward"), dim=(0, 1)
    )
    padded = torch.zeros(
        (target_side, target_side, basis.shape[2]), dtype=coefficients.dtype
    )
    start = (target_side - source_side) // 2
    padded[start : start + source_side, start : start + source_side] = coefficients
    resampled = torch.fft.ifft2(
        torch.fft.ifftshift(padded, dim=(0, 1)), dim=(0, 1), norm="forward"
    ).reshape(1, target_side * target_side, basis.shape[2])
    return periodic_mgs(torch.stack((resampled.real, resampled.imag), dim=-1))


def _candidate(
    model: torch.nn.Module,
    point: dict[str, object],
    reference_solution: object,
    *,
    side: int,
) -> tuple[dict[str, object], torch.Tensor]:
    family = str(point["family"])
    parameters = torch.tensor([point["parameters"]], dtype=torch.float32)
    coordinates = uniform_grid(side).unsqueeze(0).requires_grad_()
    neural = periodic_mgs(model(coordinates, parameters))
    hybrid_modes = sorted(
        set(d6_hex_shell_modes(2))
        | set(
            lowest_kinetic_modes(
                point["parameters"][:2], rank=21, candidate_shell=4
            )
        )
    )
    pure_modes = lowest_kinetic_modes(
        point["parameters"][:2], rank=25, candidate_shell=4
    )
    basis, details = spectral_routed_neural_fourier_ritz(
        neural,
        coordinates,
        parameters,
        family,
        hybrid_modes=hybrid_modes,
        pure_modes=pure_modes,
        threshold=0.1,
    )
    h_basis = apply_hamiltonian(basis, coordinates, parameters, family)
    raw_real, raw_imag = ritz_matrix(basis, h_basis)
    raw = torch.complex(raw_real, raw_imag)
    defect = float(
        (
            torch.linalg.matrix_norm(raw - raw.mH)
            / torch.linalg.matrix_norm(raw).clamp_min(1e-12)
        )
        .detach()
        .cpu()
    )
    values = torch.linalg.eigvalsh(hermitian_ritz_matrix(basis, h_basis))[0, :2]
    target = _reference_basis(reference_solution, side)
    return {
        "side": side,
        "projector_error": projector_sine_error(basis, target),
        "eigenvalues": [float(value.detach()) for value in values],
        "hermiticity_defect": defect,
        "route": details["route"],
    }, basis.detach().cpu()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--p5-archive", type=Path, required=True)
    parser.add_argument("--checkpoint-inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    suite, suite_hash = load_frozen_suite(args.suite)
    if file_sha256(args.p5_archive) != EXPECTED_P5_ARCHIVE_SHA256:
        raise ValueError("unexpected P5 evidence archive")
    physical_identities = {
        (
            str(point["family"]),
            tuple(round(float(value), 14) for value in point["parameters"]),
        )
        for point in suite["points"]
    }
    if len(physical_identities) != len(suite["points"]):
        raise ValueError("convergence suite has duplicate physical points")
    selected = [
        point
        for point in suite["points"]
        if any(
            token in str(point["id"])
            for token in (
                "-iid-000",
                "-exact-000",
                "-near-000",
                "-ood-000",
                "-gap-000",
            )
        )
    ]
    if len(selected) != 10:
        raise ValueError("convergence audit requires ten deterministic points")
    expected_cells = {
        (family, split)
        for family in ("gaussian_honeycomb", "harmonic_honeycomb")
        for split in (
            "iid_hidden",
            "exact_cluster",
            "near_cluster",
            "strict_ood",
            "gap_scan",
        )
    }
    actual_cells = {
        (str(point["family"]), str(point["split"])) for point in selected
    }
    if actual_cells != expected_cells or len({point["id"] for point in selected}) != 10:
        raise ValueError("convergence audit is not family-by-split balanced")
    inventory = json.loads(args.checkpoint_inventory.read_text())
    models = {
        (str(row["family"]), int(row["seed"])): load_p5_checkpoint(
            args.p5_archive, row, torch.device("cpu")
        )
        for row in inventory
        if row.get("method") == "p5_long_anchor"
    }
    reference_rows = []
    solver_rows = []
    solver_bases: dict[tuple[str, int, int], torch.Tensor] = {}
    for point in selected:
        family = str(point["family"])
        parameters = torch.tensor(point["parameters"], dtype=torch.float64)
        solutions = {
            cutoff: solve_reference(
                parameters,
                cutoff=cutoff,
                rank=3,
                potential_family=family,
                mode_shape="hexagonal_d6",
            )
            for cutoff in (20, 24, 28)
        }
        bases = {
            cutoff: _reference_basis(solution, 97)
            for cutoff, solution in solutions.items()
        }
        reference_rows.append(
            {
                "point_id": point["id"],
                "family": family,
                "projector_20_24": projector_sine_error(bases[20], bases[24]),
                "projector_24_28": projector_sine_error(bases[24], bases[28]),
                "eigenvalue_20_24": float(
                    (solutions[20].eigenvalues[:2] - solutions[24].eigenvalues[:2])
                    .abs()
                    .max()
                ),
                "eigenvalue_24_28": float(
                    (solutions[24].eigenvalues[:2] - solutions[28].eigenvalues[:2])
                    .abs()
                    .max()
                ),
            }
        )
        for seed in (42, 137, 251):
            model = models[(family, seed)]
            for side in (65, 97):
                record, basis = _candidate(
                    model, point, solutions[28], side=side
                )
                solver_rows.append(
                    {
                        "point_id": point["id"],
                        "family": family,
                        "seed": seed,
                        **record,
                    }
                )
                solver_bases[(str(point["id"]), seed, side)] = basis
        print(f"CONVERGENCE_POINT={point['id']}", flush=True)
    indexed = {
        (str(row["point_id"]), int(row["seed"]), int(row["side"])): row
        for row in solver_rows
    }
    projector_differences = []
    eigenvalue_differences = []
    for point in selected:
        for seed in (42, 137, 251):
            lower = indexed[(str(point["id"]), seed, 65)]
            upper = indexed[(str(point["id"]), seed, 97)]
            lower_basis = _periodic_resample_basis(
                solver_bases[(str(point["id"]), seed, 65)],
                source_side=65,
                target_side=97,
            )
            upper_basis = solver_bases[(str(point["id"]), seed, 97)]
            projector_differences.append(
                projector_sine_error(lower_basis, upper_basis)
            )
            eigenvalue_differences.append(
                max(
                    abs(float(first) - float(second))
                    for first, second in zip(
                        lower["eigenvalues"], upper["eigenvalues"], strict=True
                    )
                )
            )
    summary: dict[str, object] = {
        "points": len(selected),
        "max_reference_projector_20_24": max(
            float(row["projector_20_24"]) for row in reference_rows
        ),
        "max_reference_projector_24_28": max(
            float(row["projector_24_28"]) for row in reference_rows
        ),
        "max_reference_eigenvalue_20_24": max(
            float(row["eigenvalue_20_24"]) for row in reference_rows
        ),
        "max_reference_eigenvalue_24_28": max(
            float(row["eigenvalue_24_28"]) for row in reference_rows
        ),
        "max_solver_projector_grid_difference": max(projector_differences),
        "max_solver_eigenvalue_grid_difference": max(eigenvalue_differences),
        "max_raw_hermiticity_defect": max(
            float(row["hermiticity_defect"]) for row in solver_rows
        ),
        "reference_rows": reference_rows,
        "solver_rows": solver_rows,
    }
    gate = build_convergence_gate(summary)
    output = args.output.resolve()
    if output.exists() or output.with_suffix(".sha256").exists():
        raise FileExistsError("convergence evidence target already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    from scripts.run_v3_symmetry_evaluation import _source_fingerprint

    provenance = {
        "suite_id": suite["suite_id"],
        "suite_sha256": suite_hash,
        "p5_archive_sha256": file_sha256(args.p5_archive),
        "checkpoint_inventory_sha256": file_sha256(args.checkpoint_inventory),
        "source_fingerprint": _source_fingerprint(
            Path(__file__).resolve().parents[1]
        ),
        "cutoffs": [20, 24, 28],
        "solver_grids": [65, 97],
        "reference_grid": 97,
        "selected_point_ids": [str(point["id"]) for point in selected],
    }
    output.write_text(
        json.dumps(
            {"summary": summary, "gate": gate, "provenance": provenance},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    digest = file_sha256(output)
    output_sidecar = output.with_suffix(".sha256")
    output_sidecar.write_text(f"{digest}  {output.name}\n")
    archive_path = output.parent / f"{output.stem}-evidence.tar.gz"
    archive_sidecar = archive_path.with_suffix(archive_path.suffix + ".sha256")
    if archive_path.exists() or archive_sidecar.exists():
        raise FileExistsError("convergence bundle target already exists")
    bound_inputs = [
        args.suite.resolve(),
        args.suite.resolve().with_suffix(".sha256"),
        args.p5_archive.resolve().with_suffix(
            args.p5_archive.resolve().suffix + ".sha256"
        ),
        args.checkpoint_inventory.resolve(),
    ]
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(output, arcname=f"results/{output.name}")
        archive.add(output_sidecar, arcname=f"results/{output_sidecar.name}")
        for index, path in enumerate(bound_inputs):
            archive.add(path, arcname=f"inputs/{index:02d}_{path.name}")
    archive_hash = file_sha256(archive_path)
    archive_sidecar.write_text(f"{archive_hash}  {archive_path.name}\n")
    print(f"CONVERGENCE_GO={gate['convergence_go']}")
    print(f"CONVERGENCE_SHA256={digest}")
    print(f"CONVERGENCE_BUNDLE={archive_path}")
    print(f"CONVERGENCE_BUNDLE_SHA256={archive_hash}")
    return 0 if gate["convergence_go"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

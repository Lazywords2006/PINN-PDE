#!/usr/bin/env python3
"""Local PWE feasibility probe for rank-two projector quantum geometry.

This script is deliberately not a formal reference validator.  It uses the
project's current square Cartesian Fourier cutoff, records that limitation in
every row, and writes enough provenance to reproduce the local probe.  A
symmetry-closed shell implementation is still required before publication.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import platform
import sys
from typing import Final

import torch
from torch import Tensor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.reference import plane_wave_hamiltonian


MODE_POLICY: Final = "square_cartesian_not_symmetry_closed"
K_POINT: Final = (1.0 / 3.0, 1.0 / 3.0)
PROJECT_ROOT: Final = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT: Final = (
    PROJECT_ROOT
    / "results"
    / "projector_quantum_geometry"
    / "11_projector量子几何参考探针.csv"
)


@dataclass(frozen=True)
class ProbeCase:
    family: str
    physical_parameters: tuple[float, ...]


CASES: Final = {
    "harmonic_honeycomb": ProbeCase("harmonic_honeycomb", (0.5, 0.0)),
    "gaussian_honeycomb": ProbeCase("gaussian_honeycomb", (2.5, 0.26, 0.0)),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _projector(
    case: ProbeCase, kx: float, ky: float, cutoff: int
) -> tuple[Tensor, Tensor]:
    parameters = torch.tensor(
        (kx, ky, *case.physical_parameters), dtype=torch.float64
    )
    hamiltonian, _ = plane_wave_hamiltonian(
        parameters, cutoff=cutoff, potential_family=case.family
    )
    eigenvalues, eigenvectors = torch.linalg.eigh(hamiltonian)
    frame = eigenvectors[:, :2]
    return frame @ frame.conj().T, eigenvalues.real


def probe_point(case: ProbeCase, cutoff: int, delta_k: float) -> dict[str, object]:
    """Evaluate a central-difference quantum-geometry diagnostic at K."""

    if cutoff < 1:
        raise ValueError("cutoff must be positive")
    if delta_k <= 0.0:
        raise ValueError("delta_k must be positive")

    kx, ky = K_POINT
    projector, eigenvalues = _projector(case, kx, ky, cutoff)
    projector_x_plus, _ = _projector(case, kx + delta_k, ky, cutoff)
    projector_x_minus, _ = _projector(case, kx - delta_k, ky, cutoff)
    projector_y_plus, _ = _projector(case, kx, ky + delta_k, cutoff)
    projector_y_minus, _ = _projector(case, kx, ky - delta_k, cutoff)

    derivative_x = (projector_x_plus - projector_x_minus) / (2.0 * delta_k)
    derivative_y = (projector_y_plus - projector_y_minus) / (2.0 * delta_k)
    g_xx = 0.5 * torch.trace(derivative_x @ derivative_x).real
    g_yy = 0.5 * torch.trace(derivative_y @ derivative_y).real
    g_xy = 0.5 * torch.trace(derivative_x @ derivative_y).real
    commutator = derivative_x @ derivative_y - derivative_y @ derivative_x
    curvature_trace = -1j * torch.trace(projector @ commutator)

    return {
        "family": case.family,
        "cutoff": cutoff,
        "delta_k": delta_k,
        "internal_gap": float(eigenvalues[1] - eigenvalues[0]),
        "external_gap": float(eigenvalues[2] - eigenvalues[1]),
        "g_xx": float(g_xx),
        "g_yy": float(g_yy),
        "g_xy": float(g_xy),
        "trace_F_xy_real": float(curvature_trace.real),
        "trace_F_xy_imag": float(curvature_trace.imag),
        "projector_idempotency_fro": float(
            torch.linalg.matrix_norm(projector @ projector - projector)
        ),
        "projector_hermiticity_fro": float(
            torch.linalg.matrix_norm(projector - projector.conj().T)
        ),
        "mode_policy": MODE_POLICY,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--families",
        nargs="+",
        choices=tuple(CASES),
        default=list(CASES),
    )
    parser.add_argument("--cutoffs", nargs="+", type=int, default=[4, 6, 8, 10])
    parser.add_argument(
        "--delta-k", nargs="+", type=float, default=[0.02, 0.01, 0.005]
    )
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument("--metadata", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    torch.set_num_threads(args.threads)
    rows = [
        probe_point(CASES[family], cutoff, delta_k)
        for family in args.families
        for cutoff in args.cutoffs
        for delta_k in args.delta_k
    ]

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    script_path = Path(__file__).resolve()
    reference_path = (
        script_path.parent.parent / "block_kyfan_pinn" / "reference.py"
    ).resolve()
    configuration = {
        "families": [asdict(CASES[family]) for family in args.families],
        "cutoffs": args.cutoffs,
        "delta_k": args.delta_k,
        "threads": args.threads,
        "k_point_reciprocal_coordinates": K_POINT,
        "target_rank": 2,
        "dtype": "torch.complex128 / torch.float64",
        "mode_policy": MODE_POLICY,
        "formal_reference_validation": False,
    }
    canonical_configuration = json.dumps(
        configuration, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    metadata = {
        "purpose": "local feasibility probe only",
        "limitations": [
            "square Cartesian cutoff is not symmetry-closed at honeycomb K",
            "finite-difference projector derivatives are not a final convergence proof",
            "no neural-network prediction is evaluated",
        ],
        "configuration": configuration,
        "configuration_sha256": hashlib.sha256(canonical_configuration).hexdigest(),
        "script_sha256": _sha256(script_path),
        "reference_solver_sha256": _sha256(reference_path),
        "output_csv": str(output),
        "output_sha256": _sha256(output),
        "python": platform.python_version(),
        "pytorch": torch.__version__,
        "platform": platform.platform(),
    }
    metadata_path = (
        args.metadata.resolve()
        if args.metadata is not None
        else output.with_suffix(".metadata.json")
    )
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    print(f"wrote {len(rows)} rows to {output}")
    print(f"wrote metadata to {metadata_path}")


if __name__ == "__main__":
    main()

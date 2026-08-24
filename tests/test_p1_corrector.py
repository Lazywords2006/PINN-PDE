"""Unit tests for the P1 risk-gated spectral-subspace corrector."""

from __future__ import annotations

import pytest
import torch

from block_kyfan_pinn.metrics import orthogonality_error, projector_sine_error
from block_kyfan_pinn.p1_corrector import (
    build_p1_gate,
    complex_procrustes_align,
    hard_select,
    risk_chordal_correct,
    risk_weight,
)
from block_kyfan_pinn.physics import periodic_mgs


def _basis(batch: int = 2, points: int = 31) -> torch.Tensor:
    generator = torch.Generator().manual_seed(20260824)
    raw = torch.randn(
        batch, points, 2, 2, generator=generator, dtype=torch.float64
    )
    return periodic_mgs(raw)


def _real_rotate(basis: torch.Tensor, angle: float) -> torch.Tensor:
    rotation = basis.new_tensor(
        [
            [torch.cos(torch.tensor(angle)), -torch.sin(torch.tensor(angle))],
            [torch.sin(torch.tensor(angle)), torch.cos(torch.tensor(angle))],
        ]
    )
    return torch.einsum("bnir,ij->bnjr", basis, rotation)


def _complex_rotate(basis: torch.Tensor, matrix: torch.Tensor) -> torch.Tensor:
    basis_complex = torch.complex(basis[..., 0], basis[..., 1])
    rotated = torch.einsum("bni,ij->bnj", basis_complex, matrix)
    return torch.stack((rotated.real, rotated.imag), dim=-1)


def test_complex_procrustes_removes_rank_two_basis_rotation() -> None:
    anchor = _basis()
    rotated = _real_rotate(anchor, 0.73)

    aligned = complex_procrustes_align(anchor, rotated)

    assert projector_sine_error(aligned, anchor) < 1e-6
    assert torch.allclose(aligned, anchor, atol=2e-5, rtol=2e-5)


def test_complex_procrustes_rejects_mismatched_shapes() -> None:
    anchor = _basis()
    with pytest.raises(ValueError, match="same shape"):
        complex_procrustes_align(anchor, anchor[:, :-1])


def test_complex_procrustes_handles_general_u2_rotation_and_column_phases() -> None:
    anchor = _basis()
    raw = torch.tensor(
        [[1.0 + 0.4j, -0.2 + 0.7j], [0.3 - 0.5j, 0.9 + 0.1j]],
        dtype=torch.complex128,
    )
    unitary, _ = torch.linalg.qr(raw)
    candidate = _complex_rotate(anchor, unitary)

    aligned = complex_procrustes_align(anchor, candidate)

    assert torch.allclose(aligned, anchor, atol=2e-10, rtol=2e-10)
    assert orthogonality_error(aligned) < 1e-10


@pytest.mark.skipif(
    not torch.backends.mps.is_available(), reason="MPS accelerator is unavailable"
)
def test_complex_procrustes_moves_real_rotation_to_mps_safely() -> None:
    anchor = _basis().float().to("mps")
    candidate = _real_rotate(anchor, 0.41)

    aligned = complex_procrustes_align(anchor, candidate)

    assert aligned.device.type == "mps"
    assert torch.isfinite(aligned).all()


def test_risk_weight_has_frozen_endpoints_and_is_monotone() -> None:
    scores = torch.tensor([0.1, 0.2, 0.3, 0.4])

    weights = risk_weight(scores, t_low=0.2, t_high=0.3)

    assert weights.tolist() == pytest.approx([1.0, 1.0, 0.0, 0.0])
    assert bool((weights[:-1] >= weights[1:]).all())


def test_risk_weight_rejects_invalid_threshold_order() -> None:
    with pytest.raises(ValueError, match="t_low"):
        risk_weight(torch.tensor([0.5]), t_low=0.7, t_high=0.7)


def test_risk_chordal_endpoints_match_anchor_and_candidate_projectors() -> None:
    anchor = _basis()
    candidate = periodic_mgs(anchor + 0.15 * _basis())

    anchor_output = risk_chordal_correct(
        anchor, candidate, torch.zeros(anchor.shape[0])
    )
    candidate_output = risk_chordal_correct(
        anchor, candidate, torch.ones(anchor.shape[0])
    )

    assert projector_sine_error(anchor_output, anchor) < 1e-6
    assert projector_sine_error(candidate_output, candidate) < 1e-5
    assert orthogonality_error(anchor_output) < 1e-5
    assert orthogonality_error(candidate_output) < 1e-5


def test_hard_select_returns_only_requested_projector() -> None:
    anchor = _basis()
    candidate = periodic_mgs(anchor + 0.25 * _basis())
    selected = hard_select(
        anchor, candidate, torch.tensor([True, False], dtype=torch.bool)
    )

    assert projector_sine_error(selected[:1], candidate[:1]) < 1e-5
    assert projector_sine_error(selected[1:], anchor[1:]) < 1e-6


def _passing_summary() -> dict[str, object]:
    return {
        "engineering_pass": True,
        "maximum_orthogonality_error": 1e-6,
        "p1_risk_chordal_near_cluster_projector_mean": 0.090,
        "p5_long_anchor_near_cluster_projector_mean": 0.100,
        "p1_risk_chordal_gap_scan_projector_mean": 0.101,
        "p5_anchor_gap_scan_projector_mean": 0.100,
        "p5_long_anchor_gap_scan_projector_mean": 0.105,
        "family_near_projector_mean": {
            "harmonic_honeycomb": {"p1_risk_chordal": 0.08, "p5_long_anchor": 0.09},
            "gaussian_honeycomb": {"p1_risk_chordal": 0.10, "p5_long_anchor": 0.11},
        },
        "paired_near_wins_vs_long_anchor": 5,
        "paired_near_comparisons": 6,
        "p1_risk_chordal_overall_projector_mean": 0.10,
        "p5_anchor_overall_projector_mean": 0.12,
        "p5_static_low_rom_overall_projector_mean": 0.11,
        "p1_risk_chordal_unsafe_rate_vs_anchor": 0.15,
        "p5_static_low_rom_unsafe_rate_vs_anchor": 0.25,
        "p1_risk_chordal_pwe_fraction": 0.0,
        "combined_risk_auroc": 0.82,
        "parameter_only_risk_auroc": 0.72,
        "combined_risk_auroc_by_family": {
            "harmonic_honeycomb": 0.85,
            "gaussian_honeycomb": 0.75,
        },
        "p1_risk_chordal_latency_ms": 2.4,
        "p5_anchor_latency_ms": 1.0,
    }


def test_p1_gate_accepts_only_complete_neural_primary_success() -> None:
    gate = build_p1_gate(_passing_summary())

    assert gate["pilot_go"] is True
    assert all(value is True for key, value in gate.items() if key.endswith("_pass"))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("engineering_pass",), False),
        (("maximum_orthogonality_error",), 1e-3),
        (("p1_risk_chordal_near_cluster_projector_mean",), 0.097),
        (("p1_risk_chordal_gap_scan_projector_mean",), 0.103),
        (("family_near_projector_mean", "gaussian_honeycomb", "p1_risk_chordal"), 0.12),
        (("paired_near_wins_vs_long_anchor",), 4),
        (("p1_risk_chordal_overall_projector_mean",), 0.115),
        (("p1_risk_chordal_unsafe_rate_vs_anchor",), 0.20),
        (("p1_risk_chordal_pwe_fraction",), 0.01),
        (("combined_risk_auroc",), 0.69),
        (("combined_risk_auroc",), 0.76),
        (("combined_risk_auroc_by_family", "gaussian_honeycomb"), 0.64),
        (("p1_risk_chordal_latency_ms",), 2.6),
    ],
)
def test_each_frozen_p1_requirement_forces_stop(
    path: tuple[str, ...], value: object
) -> None:
    summary = _passing_summary()
    target = summary
    for key in path[:-1]:
        target = target[key]  # type: ignore[index,assignment]
    target[path[-1]] = value  # type: ignore[index]

    assert build_p1_gate(summary)["pilot_go"] is False

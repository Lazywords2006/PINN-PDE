"""Unit tests for the P1 risk-gated spectral-subspace corrector."""

from __future__ import annotations

import pytest
import torch

from block_kyfan_pinn.metrics import orthogonality_error, projector_sine_error
from block_kyfan_pinn.p1_corrector import (
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

"""Unit tests for P3 ROM–Grassmann multi-chart module."""

import math

import pytest
import torch

from block_kyfan_pinn.model import periodic_features
from block_kyfan_pinn.physics import complex_gram_mean, periodic_mgs
from block_kyfan_pinn.p3_model import P3BlockKyFanPINN
from block_kyfan_pinn.p3_rom import (
    ROMCoefficientNetwork,
    _k_point_modes,
    chart_disagreement_risk,
    chart_partition,
    m_weighted_gram_mean,
    m_weighted_gram_schmidt,
    parametric_rom_anchor,
    should_fallback,
)


# ── Reciprocal-lattice modes ────────────────────────────────────────────────

def test_k_point_modes_shell_0_returns_origin_only() -> None:
    modes = _k_point_modes(0)
    assert modes == [(0, 0)]


def test_k_point_modes_shell_1_returns_7_modes() -> None:
    modes = _k_point_modes(1)
    assert len(modes) == 7  # origin + 6 hex neighbours
    assert (0, 0) in modes


def test_k_point_modes_shell_2_returns_19_modes() -> None:
    modes = _k_point_modes(2)
    assert len(modes) == 19  # approximated hexagonal 2-shell


# ── ROM coefficient network ─────────────────────────────────────────────────

def test_rom_coefficient_network_output_shape() -> None:
    net = ROMCoefficientNetwork(parameter_dim=4, num_modes=7, hidden_width=16, hidden_layers=1)
    params = torch.randn(3, 4)
    output = net(params)
    assert output.shape == (3, 2, 7, 2)  # batch, rank, modes, real/imaginary


def test_rom_coefficient_network_differentiable() -> None:
    net = ROMCoefficientNetwork(parameter_dim=5, num_modes=3, hidden_width=16, hidden_layers=1)
    params = torch.randn(2, 5, requires_grad=True)
    output = net(params)
    loss = output.square().sum()
    loss.backward()
    assert params.grad is not None
    assert torch.isfinite(params.grad).all()


# ── Parametric ROM anchor ───────────────────────────────────────────────────

def test_parametric_rom_anchor_shape() -> None:
    net = ROMCoefficientNetwork(parameter_dim=4, num_modes=7, hidden_width=16, hidden_layers=1)
    modes = _k_point_modes(1)  # 7 modes
    coordinates = torch.rand(2, 64, 2) * (2.0 * math.pi)
    parameters = torch.randn(2, 4)
    anchor = parametric_rom_anchor(coordinates, parameters, net, modes=modes, anchor_scale=0.1)
    assert anchor.shape == (2, 64, 2, 2)
    assert torch.isfinite(anchor).all()


def test_parametric_rom_anchor_differentiable() -> None:
    net = ROMCoefficientNetwork(parameter_dim=4, num_modes=3, hidden_width=16, hidden_layers=1)
    modes = [(0, 0), (1, 0), (0, 1)]
    coordinates = torch.rand(1, 16, 2) * (2.0 * math.pi)
    coordinates.requires_grad_(True)
    parameters = torch.randn(1, 4)
    anchor = parametric_rom_anchor(coordinates, parameters, net, modes=modes, anchor_scale=0.1)
    loss = anchor.square().sum()
    loss.backward()
    assert torch.isfinite(coordinates.grad).all()


# ── M-weighted Gram-Schmidt ─────────────────────────────────────────────────

def test_m_weighted_gram_mean_reproduces_unweighted_when_uniform() -> None:
    torch.manual_seed(3)
    basis = periodic_mgs(torch.randn(2, 32, 2, 2))
    uniform_w = torch.ones(32) / 32.0
    m_real, m_imag = m_weighted_gram_mean(basis, uniform_w)
    std_real, std_imag = complex_gram_mean(basis)
    assert torch.allclose(m_real, std_real, atol=1e-5)
    assert torch.allclose(m_imag, std_imag, atol=1e-5)


def test_m_weighted_gram_schmidt_produces_orthonormal_basis() -> None:
    torch.manual_seed(7)
    raw = torch.randn(2, 48, 2, 2)
    weights = torch.linspace(0.5, 1.5, 48)  # non-uniform
    basis = m_weighted_gram_schmidt(raw, weights)
    gram_real, gram_imag = m_weighted_gram_mean(basis, weights)
    identity = torch.eye(2).unsqueeze(0)
    assert torch.allclose(gram_real, identity, atol=1e-4)
    assert torch.allclose(gram_imag, torch.zeros_like(gram_imag), atol=1e-4)


def test_m_weighted_gram_schmidt_produces_finite_output() -> None:
    torch.manual_seed(11)
    raw = torch.randn(1, 64, 2, 2)
    basis = m_weighted_gram_schmidt(raw)
    assert torch.isfinite(basis).all()


# ── Chart partition ─────────────────────────────────────────────────────────

def test_chart_partition_single_chart_returns_one() -> None:
    params = torch.randn(4, 4)
    weights = chart_partition(params, [(0.31, 0.35, 0.50, 0.0)])
    assert weights.shape == (4, 1)
    assert torch.allclose(weights.sum(-1), torch.ones(4), atol=1e-6)


def test_chart_partition_soft_assignment() -> None:
    params = torch.tensor([[0.30, 0.30, 0.50, 0.0], [0.40, 0.40, 0.70, 0.1]])
    centers = [(0.30, 0.30, 0.50, 0.0), (0.40, 0.40, 0.70, 0.1)]
    weights = chart_partition(params, centers, temperature=0.1)
    # Point 0 should be assigned mainly to chart 0
    assert weights[0, 0] > weights[0, 1]
    # Point 1 should be assigned mainly to chart 1
    assert weights[1, 1] > weights[1, 0]


# ── Chart disagreement risk ─────────────────────────────────────────────────

def test_chart_disagreement_identical_basis_returns_zero() -> None:
    torch.manual_seed(13)
    basis = periodic_mgs(torch.randn(1, 40, 2, 2))
    risk = chart_disagreement_risk(basis, basis)
    assert risk < 1e-5


def test_chart_disagreement_different_basis_positive() -> None:
    torch.manual_seed(17)
    basis_a = periodic_mgs(torch.randn(1, 40, 2, 2))
    basis_b = periodic_mgs(torch.randn(1, 40, 2, 2))
    risk = chart_disagreement_risk(basis_a, basis_b)
    assert 0.0 < risk <= 1.0


# ── Fallback trigger ────────────────────────────────────────────────────────

def test_should_fallback_below_thresholds_returns_false() -> None:
    residual_risk = torch.tensor([0.1])
    chart_risk = 0.1
    result = should_fallback(
        residual_risk, chart_risk, residual_threshold=0.5, chart_threshold=0.3
    )
    assert not bool(result.any().cpu())


def test_should_fallback_above_residual_threshold_returns_true() -> None:
    residual_risk = torch.tensor([0.8])
    chart_risk = 0.1
    result = should_fallback(
        residual_risk, chart_risk, residual_threshold=0.5, chart_threshold=0.3
    )
    assert bool(result.any().cpu())


def test_should_fallback_above_chart_threshold_returns_true() -> None:
    residual_risk = torch.tensor([0.1])
    chart_risk = 0.5
    result = should_fallback(
        residual_risk, chart_risk, residual_threshold=0.5, chart_threshold=0.3
    )
    assert bool(result.any().cpu())


# ── P3 model ────────────────────────────────────────────────────────────────

def test_p3_model_forward_shape() -> None:
    torch.manual_seed(19)
    model = P3BlockKyFanPINN(
        width=24, hidden_layers=2,
        anchor_scale=0.1, anchor_kind="correct",
        parameter_dim=4,
        num_rom_shells=1, rom_hidden_width=32, rom_hidden_layers=1,
        num_charts=1, m_weighted=False, gap_monitor=False,
        fallback_enabled=False,
    )
    coordinates = torch.rand(2, 36, 2, requires_grad=True) * (2.0 * math.pi)
    parameters = torch.tensor([[0.31, 0.35, 0.35, 0.05], [0.33, 0.33, 0.60, 0.0]])
    basis = model(coordinates, parameters)
    assert basis.shape == (2, 36, 2, 2)
    assert torch.isfinite(basis).all()


def test_p3_model_output_is_orthonormal() -> None:
    torch.manual_seed(23)
    model = P3BlockKyFanPINN(
        width=24, hidden_layers=2,
        anchor_scale=0.1, anchor_kind="correct",
        parameter_dim=4,
        num_rom_shells=1, rom_hidden_width=32, rom_hidden_layers=1,
        num_charts=1, m_weighted=False, gap_monitor=False,
        fallback_enabled=False,
    )
    coordinates = torch.rand(1, 49, 2, requires_grad=True) * (2.0 * math.pi)
    parameters = torch.tensor([[0.31, 0.35, 0.35, 0.05]])
    basis = model(coordinates, parameters)
    gram_real, gram_imag = complex_gram_mean(basis)
    assert torch.allclose(gram_real, torch.eye(2).unsqueeze(0), atol=3e-5)
    assert torch.allclose(gram_imag, torch.zeros_like(gram_imag), atol=3e-5)


def test_p3_model_multi_chart_forward_shape() -> None:
    torch.manual_seed(29)
    model = P3BlockKyFanPINN(
        width=16, hidden_layers=1,
        anchor_scale=0.1, anchor_kind="correct",
        parameter_dim=4,
        num_rom_shells=1, rom_hidden_width=16, rom_hidden_layers=1,
        num_charts=2, chart_temperature=0.5,
        m_weighted=False, gap_monitor=False,
        fallback_enabled=False,
    )
    coordinates = torch.rand(1, 25, 2, requires_grad=True) * (2.0 * math.pi)
    parameters = torch.tensor([[0.31, 0.35, 0.35, 0.05]])
    basis = model(coordinates, parameters)
    assert basis.shape == (1, 25, 2, 2)


def test_p3_model_differentiable() -> None:
    torch.manual_seed(31)
    model = P3BlockKyFanPINN(
        width=16, hidden_layers=1,
        anchor_scale=0.1, anchor_kind="correct",
        parameter_dim=4,
        num_rom_shells=1, rom_hidden_width=16, rom_hidden_layers=1,
        num_charts=1, m_weighted=False, gap_monitor=False,
        fallback_enabled=False,
    )
    coordinates = torch.rand(1, 16, 2, requires_grad=True) * (2.0 * math.pi)
    parameters = torch.tensor([[0.31, 0.35, 0.35, 0.05]])
    from block_kyfan_pinn.physics import ky_fan_energy

    basis = model(coordinates, parameters)
    loss = ky_fan_energy(basis, coordinates, parameters)
    loss.backward()
    # Check that at least some parameters have gradients
    grad_count = sum(
        1 for p in model.parameters() if p.grad is not None and torch.isfinite(p.grad).all()
    )
    assert grad_count > 0


def test_p3_model_9_wave_rom() -> None:
    """9-wave ROM with 2 shells (19 modes total)."""
    torch.manual_seed(37)
    model = P3BlockKyFanPINN(
        width=16, hidden_layers=1,
        anchor_scale=0.1, anchor_kind="correct",
        parameter_dim=5,
        num_rom_shells=2,  # 19 modes ≈ 9-wave
        rom_hidden_width=32, rom_hidden_layers=1,
        num_charts=1, m_weighted=False, gap_monitor=False,
        fallback_enabled=False, potential_family="gaussian_honeycomb",
    )
    coordinates = torch.rand(1, 25, 2, requires_grad=True) * (2.0 * math.pi)
    parameters = torch.tensor([[0.31, 0.35, 2.0, 0.26, 0.04]])
    basis = model(coordinates, parameters)
    assert basis.shape == (1, 25, 2, 2)
    assert torch.isfinite(basis).all()


def test_p3_model_risk_evaluation_single_chart() -> None:
    torch.manual_seed(41)
    model = P3BlockKyFanPINN(
        width=16, hidden_layers=1,
        anchor_scale=0.1, anchor_kind="correct",
        parameter_dim=4,
        num_rom_shells=1, rom_hidden_width=16, rom_hidden_layers=1,
        num_charts=1, m_weighted=False,
        gap_monitor=True, fallback_enabled=False,
    )
    coordinates = torch.rand(1, 25, 2, requires_grad=True) * (2.0 * math.pi)
    parameters = torch.tensor([[0.31, 0.35, 0.35, 0.05]])
    basis = model(coordinates, parameters)
    risks = model.evaluate_risks(coordinates, parameters, basis)
    assert "projected_residual_rms" in risks
    assert "residual_risk" in risks
    assert "chart_disagreement" in risks
    assert "should_fallback" in risks
    assert risks["projected_residual_rms"].shape == (1,)
    assert bool((risks["residual_risk"] >= 0.0).all())
    assert bool((risks["residual_risk"] <= 1.0).all())


def test_p3_model_forward_with_fallback() -> None:
    torch.manual_seed(43)
    model = P3BlockKyFanPINN(
        width=16, hidden_layers=1,
        anchor_scale=0.1, anchor_kind="correct",
        parameter_dim=4,
        num_rom_shells=1, rom_hidden_width=16, rom_hidden_layers=1,
        num_charts=1, m_weighted=False,
        gap_monitor=True, fallback_enabled=True,
        reference_cutoff=4,
    )
    coordinates = torch.rand(1, 25, 2, requires_grad=True) * (2.0 * math.pi)
    parameters = torch.tensor([[0.31, 0.35, 0.35, 0.05]])
    basis, info = model.forward_with_fallback(coordinates, parameters)
    assert basis.shape == (1, 25, 2, 2)
    assert torch.isfinite(basis).all()
    assert "fallback_used" in info
    assert isinstance(info["fallback_used"], bool)


def test_p3_model_m_weighted_is_orthonormal() -> None:
    torch.manual_seed(47)
    model = P3BlockKyFanPINN(
        width=16, hidden_layers=1,
        anchor_scale=0.1, anchor_kind="correct",
        parameter_dim=4,
        num_rom_shells=1, rom_hidden_width=16, rom_hidden_layers=1,
        num_charts=1, m_weighted=True, gap_monitor=False,
        fallback_enabled=False,
    )
    coordinates = torch.rand(1, 36, 2, requires_grad=True) * (2.0 * math.pi)
    parameters = torch.tensor([[0.31, 0.35, 0.35, 0.05]])
    basis = model(coordinates, parameters)
    gram_real, gram_imag = complex_gram_mean(basis)
    assert torch.allclose(gram_real, torch.eye(2).unsqueeze(0), atol=3e-5)
    assert torch.allclose(gram_imag, torch.zeros_like(gram_imag), atol=3e-5)

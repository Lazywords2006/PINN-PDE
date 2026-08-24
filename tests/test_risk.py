from __future__ import annotations

import math

import pytest
import torch

from block_kyfan_pinn.risk import (
    average_precision,
    binary_auroc,
    build_risk_gate,
    clustered_bootstrap_auc,
    fit_logistic_score,
    predict_logistic_score,
    regression_labels,
    risk_coverage,
    safe_log_ratio,
)


def test_regression_labels_use_strict_and_two_percent_boundaries() -> None:
    candidate = torch.tensor([1.0, 1.01, 1.02, 1.03], dtype=torch.float64)
    anchor = torch.ones(4, dtype=torch.float64)
    regression, unsafe = regression_labels(candidate, anchor)
    assert regression.tolist() == [False, True, True, True]
    assert unsafe.tolist() == [False, False, False, True]


def test_safe_log_ratio_is_finite_for_zero_inputs() -> None:
    result = safe_log_ratio(
        torch.tensor([0.0, 2.0]), torch.tensor([0.0, 1.0])
    )
    assert torch.isfinite(result).all()
    assert result[1] == pytest.approx(math.log(2.0))


def test_binary_ranking_metrics_match_perfect_ordering() -> None:
    labels = torch.tensor([0, 0, 1, 1], dtype=torch.bool)
    scores = torch.tensor([0.1, 0.2, 0.8, 0.9])
    assert binary_auroc(labels, scores) == pytest.approx(1.0)
    assert average_precision(labels, scores) == pytest.approx(1.0)


def test_binary_auroc_rejects_single_class() -> None:
    with pytest.raises(ValueError, match="both classes"):
        binary_auroc(torch.zeros(4, dtype=torch.bool), torch.arange(4.0))


def test_fit_logistic_score_rejects_reference_features() -> None:
    features = torch.randn(8, 2)
    labels = torch.tensor([0, 1] * 4, dtype=torch.bool)
    with pytest.raises(ValueError, match="forbidden"):
        fit_logistic_score(features, labels, ["residual", "external_gap"])


def test_logistic_score_is_deterministic_and_orders_separable_data() -> None:
    features = torch.tensor([[-2.0], [-1.0], [1.0], [2.0]])
    labels = torch.tensor([0, 0, 1, 1], dtype=torch.bool)
    first = fit_logistic_score(features, labels, ["residual_delta"])
    second = fit_logistic_score(features, labels, ["residual_delta"])
    scores = predict_logistic_score(features, first)
    assert first == second
    assert binary_auroc(labels, scores) == pytest.approx(1.0)


def test_logistic_score_rejects_single_class_calibration() -> None:
    with pytest.raises(ValueError, match="both classes"):
        fit_logistic_score(
            torch.arange(4.0).unsqueeze(-1),
            torch.zeros(4, dtype=torch.bool),
            ["residual_delta"],
        )


def test_risk_coverage_removes_high_risk_failures_first() -> None:
    failure = torch.tensor([0, 0, 1, 1], dtype=torch.bool)
    severity = torch.tensor([-0.1, -0.2, 0.3, 0.4])
    scores = torch.tensor([0.1, 0.2, 0.8, 0.9])
    curve = risk_coverage(
        failure, severity, scores, coverages=(0.5, 0.8, 1.0)
    )
    assert curve[0]["failure_rate"] == 0.0
    assert curve[-1]["failure_rate"] == pytest.approx(0.5)


def test_clustered_bootstrap_auc_is_deterministic_by_point() -> None:
    point_ids = ["a", "a", "b", "b", "c", "c", "d", "d"]
    labels = torch.tensor([0, 0, 0, 0, 1, 1, 1, 1], dtype=torch.bool)
    scores = torch.tensor([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9])
    first = clustered_bootstrap_auc(
        point_ids, labels, scores, samples=200, seed=73
    )
    second = clustered_bootstrap_auc(
        point_ids, labels, scores, samples=200, seed=73
    )
    assert first == second
    assert first["low"] == pytest.approx(1.0)
    assert first["high"] == pytest.approx(1.0)


def test_risk_gate_requires_every_scientific_threshold() -> None:
    metrics: dict[str, object] = {
        "engineering_pass": True,
        "primary_auroc": 0.72,
        "unsafe_auroc": 0.73,
        "primary_auroc_ci_low": 0.55,
        "family_auroc": {
            "harmonic_honeycomb": 0.68,
            "gaussian_honeycomb": 0.69,
        },
        "primary_auprc": 0.62,
        "primary_prevalence": 0.40,
        "top20_precision": 0.60,
        "unsafe_rate": 0.40,
        "unsafe_rate_at_80pct_coverage": 0.28,
    }
    gate = build_risk_gate(metrics)
    assert gate["risk_go"] is True
    metrics["primary_auroc"] = 0.69
    assert build_risk_gate(metrics)["risk_go"] is False

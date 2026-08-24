from __future__ import annotations

import math

import pytest
import torch

from block_kyfan_pinn.risk import (
    average_precision,
    binary_auroc,
    regression_labels,
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

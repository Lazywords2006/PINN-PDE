"""Label-free failure-risk analysis for paired neural spectral-cluster solvers."""

from __future__ import annotations

import torch
from torch import Tensor


def _one_dimensional(values: Tensor, name: str) -> Tensor:
    values = torch.as_tensor(values, dtype=torch.float64).flatten()
    if values.numel() == 0 or not bool(torch.isfinite(values).all()):
        raise ValueError(f"{name} must be a non-empty finite vector")
    return values


def regression_labels(candidate: Tensor, anchor: Tensor) -> tuple[Tensor, Tensor]:
    """Return strict-regression and greater-than-two-percent labels."""

    candidate = _one_dimensional(candidate, "candidate")
    anchor = _one_dimensional(anchor, "anchor")
    if candidate.shape != anchor.shape:
        raise ValueError("candidate and anchor must have the same shape")
    return candidate > anchor, candidate > 1.02 * anchor


def safe_log_ratio(
    numerator: Tensor, denominator: Tensor, eps: float = 1e-12
) -> Tensor:
    """Return a finite log-ratio with a common positive floor."""

    if eps <= 0:
        raise ValueError("eps must be positive")
    numerator = torch.as_tensor(numerator, dtype=torch.float64)
    denominator = torch.as_tensor(denominator, dtype=torch.float64)
    if numerator.shape != denominator.shape:
        raise ValueError("ratio operands must have the same shape")
    return torch.log(numerator.clamp_min(eps)) - torch.log(
        denominator.clamp_min(eps)
    )


def binary_auroc(labels: Tensor, scores: Tensor) -> float:
    """Compute tie-aware binary AUROC without an external statistics package."""

    labels = torch.as_tensor(labels, dtype=torch.bool).flatten()
    scores = _one_dimensional(scores, "scores")
    if labels.shape != scores.shape:
        raise ValueError("labels and scores must have the same shape")
    positive = scores[labels]
    negative = scores[~labels]
    if positive.numel() == 0 or negative.numel() == 0:
        raise ValueError("AUROC requires both classes")
    comparisons = positive[:, None] - negative[None, :]
    return float(
        (
            (comparisons > 0).double()
            + 0.5 * (comparisons == 0).double()
        ).mean()
    )


def average_precision(labels: Tensor, scores: Tensor) -> float:
    """Compute average precision from a deterministic stable ranking."""

    labels = torch.as_tensor(labels, dtype=torch.bool).flatten()
    scores = _one_dimensional(scores, "scores")
    if labels.shape != scores.shape:
        raise ValueError("labels and scores must have the same shape")
    if not bool(labels.any()):
        raise ValueError("average precision requires positives")
    order = torch.argsort(scores, descending=True, stable=True)
    ordered = labels[order].double()
    precision = ordered.cumsum(0) / torch.arange(
        1, ordered.numel() + 1, dtype=torch.float64
    )
    return float((precision * ordered).sum() / ordered.sum())

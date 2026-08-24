"""Label-free failure-risk analysis for paired neural spectral-cluster solvers."""

from __future__ import annotations

import math

import torch
from torch import Tensor


FORBIDDEN_FEATURES = frozenset(
    {
        "split",
        "role",
        "projector_error",
        "anchor_projector_error",
        "candidate_projector_error",
        "delta_error",
        "regression",
        "unsafe_regression",
        "internal_gap",
        "external_gap",
        "reference_internal_gap",
        "reference_external_gap",
        "reference_eigenvalues",
    }
)


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


def validate_feature_names(names: list[str]) -> None:
    """Reject duplicated or oracle-derived fitted features."""

    forbidden = sorted(set(names) & FORBIDDEN_FEATURES)
    if forbidden:
        raise ValueError(f"forbidden fitted features: {forbidden}")
    if not names or len(names) != len(set(names)):
        raise ValueError("feature names must be non-empty and unique")


def fit_logistic_score(
    features: Tensor,
    labels: Tensor,
    names: list[str],
    l2: float = 1e-2,
) -> dict[str, object]:
    """Fit one deterministic, standardized L2-logistic risk score."""

    validate_feature_names(names)
    if l2 < 0:
        raise ValueError("l2 must be non-negative")
    matrix = torch.as_tensor(features, dtype=torch.float64)
    targets = torch.as_tensor(labels, dtype=torch.float64).flatten()
    if (
        matrix.ndim != 2
        or matrix.shape != (targets.numel(), len(names))
        or not bool(torch.isfinite(matrix).all())
    ):
        raise ValueError("features must be a finite [rows, features] matrix")
    if targets.numel() == 0 or bool(targets.min() == targets.max()):
        raise ValueError("logistic fitting requires both classes")
    mean = matrix.mean(0)
    scale = matrix.std(0, unbiased=False).clamp_min(1e-12)
    standardized = (matrix - mean) / scale
    design = torch.cat(
        (standardized, torch.ones((standardized.shape[0], 1), dtype=torch.float64)),
        dim=1,
    )
    coefficients = torch.zeros(design.shape[1], dtype=torch.float64)
    penalty = torch.full((design.shape[1],), 2.0 * l2, dtype=torch.float64)
    penalty[-1] = 0.0
    identity = torch.eye(design.shape[1], dtype=torch.float64)
    for _ in range(100):
        probability = torch.sigmoid(design @ coefficients)
        gradient = design.T @ (probability - targets) / targets.numel()
        gradient = gradient + penalty * coefficients
        curvature = probability * (1.0 - probability)
        hessian = design.T @ (design * curvature[:, None]) / targets.numel()
        hessian = hessian + torch.diag(penalty) + 1e-10 * identity
        step = torch.linalg.solve(hessian, gradient)
        coefficients = coefficients - step
        if float(step.abs().max()) < 1e-10:
            break
    weight = coefficients[:-1]
    intercept = coefficients[-1]
    return {
        "feature_names": list(names),
        "mean": mean.tolist(),
        "scale": scale.tolist(),
        "weight": weight.tolist(),
        "intercept": float(intercept),
        "l2": float(l2),
    }


def predict_logistic_score(
    features: Tensor, model: dict[str, object]
) -> Tensor:
    """Apply a score returned by :func:`fit_logistic_score`."""

    matrix = torch.as_tensor(features, dtype=torch.float64)
    mean = torch.tensor(model["mean"], dtype=torch.float64)
    scale = torch.tensor(model["scale"], dtype=torch.float64)
    weight = torch.tensor(model["weight"], dtype=torch.float64)
    if matrix.ndim != 2 or matrix.shape[1] != weight.numel():
        raise ValueError("prediction features do not match the fitted model")
    if mean.shape != weight.shape or scale.shape != weight.shape:
        raise ValueError("fitted model vectors are inconsistent")
    intercept = float(model["intercept"])
    return torch.sigmoid(((matrix - mean) / scale) @ weight + intercept)


def risk_coverage(
    failure: Tensor,
    severity: Tensor,
    scores: Tensor,
    *,
    coverages: tuple[float, ...] = (0.5, 0.8, 1.0),
) -> list[dict[str, float | int]]:
    """Measure retained-set errors after rejecting the highest-risk rows."""

    failure = torch.as_tensor(failure, dtype=torch.bool).flatten()
    severity = _one_dimensional(severity, "severity")
    scores = _one_dimensional(scores, "scores")
    if failure.shape != severity.shape or failure.shape != scores.shape:
        raise ValueError("coverage inputs must have the same shape")
    order = torch.argsort(scores, descending=False, stable=True)
    rows: list[dict[str, float | int]] = []
    for coverage in coverages:
        if not 0.0 < coverage <= 1.0:
            raise ValueError("coverage must be in (0, 1]")
        count = max(1, math.ceil(coverage * failure.numel()))
        selected = order[:count]
        rows.append(
            {
                "coverage": float(coverage),
                "count": count,
                "failure_rate": float(failure[selected].double().mean()),
                "mean_positive_severity": float(
                    severity[selected].clamp_min(0).mean()
                ),
            }
        )
    return rows


def clustered_bootstrap_auc(
    point_ids: list[str],
    labels: Tensor,
    scores: Tensor,
    *,
    samples: int = 1000,
    seed: int = 20260824,
) -> dict[str, float | int]:
    """Bootstrap AUROC while keeping all seed rows of a point together."""

    labels = torch.as_tensor(labels, dtype=torch.bool).flatten()
    scores = _one_dimensional(scores, "scores")
    if len(point_ids) != labels.numel() or labels.shape != scores.shape:
        raise ValueError("bootstrap rows must align")
    if samples <= 0:
        raise ValueError("samples must be positive")
    unique = sorted(set(point_ids))
    if not unique:
        raise ValueError("point_ids must be non-empty")
    by_point = {
        point: [index for index, value in enumerate(point_ids) if value == point]
        for point in unique
    }
    generator = torch.Generator().manual_seed(seed)
    values: list[float] = []
    for _ in range(samples):
        draws = torch.randint(
            len(unique), (len(unique),), generator=generator
        )
        indices = [
            row
            for draw in draws.tolist()
            for row in by_point[unique[draw]]
        ]
        selected_labels = labels[indices]
        if bool(selected_labels.any()) and bool((~selected_labels).any()):
            values.append(binary_auroc(selected_labels, scores[indices]))
    if len(values) < max(100, samples // 2):
        raise ValueError("too few valid clustered bootstrap samples")
    tensor = torch.tensor(values, dtype=torch.float64)
    return {
        "mean": float(tensor.mean()),
        "low": float(torch.quantile(tensor, 0.025)),
        "high": float(torch.quantile(tensor, 0.975)),
        "valid_samples": len(values),
    }


def build_risk_gate(metrics: dict[str, object]) -> dict[str, object]:
    """Apply the predeclared held-out P0 risk-detectability thresholds."""

    raw_family = metrics.get("family_auroc")
    if not isinstance(raw_family, dict) or set(raw_family) != {
        "harmonic_honeycomb",
        "gaussian_honeycomb",
    }:
        raise ValueError("family_auroc must contain exactly the two P5 families")
    unsafe_rate = float(metrics["unsafe_rate"])
    checks = {
        "engineering_pass": bool(metrics["engineering_pass"]),
        "primary_auroc_pass": float(metrics["primary_auroc"]) >= 0.70,
        "unsafe_auroc_pass": float(metrics["unsafe_auroc"]) >= 0.70,
        "primary_ci_pass": float(metrics["primary_auroc_ci_low"]) > 0.50,
        "family_auroc_pass": all(
            float(value) >= 0.65 for value in raw_family.values()
        ),
        "primary_auprc_pass": float(metrics["primary_auprc"])
        >= float(metrics["primary_prevalence"]) + 0.10,
        "top20_precision_pass": float(metrics["top20_precision"])
        >= float(metrics["primary_prevalence"]) + 0.15,
        "coverage_safety_pass": unsafe_rate > 0
        and float(metrics["unsafe_rate_at_80pct_coverage"])
        <= 0.75 * unsafe_rate,
    }
    return {**checks, "risk_go": all(checks.values())}

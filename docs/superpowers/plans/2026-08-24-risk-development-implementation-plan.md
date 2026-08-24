# Independent Risk-Development Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and locally run an independently split, evidence-bound P0 pipeline that tests whether label-free inference quantities can detect P5 ROM regressions without touching frozen final.

**Architecture:** Add one pure risk-analysis module, one deterministic suite generator, and one evidence-driven evaluator. The generator freezes calibration/audit points and references; the evaluator verifies the P5 archive, loads only paired anchor/ROM final checkpoints, writes features, fits on calibration only, evaluates audit once, and emits a frozen GO/STOP gate.

**Tech Stack:** Python 3.12, PyTorch 2.8, NumPy through PyTorch only, pytest, JSON/CSV, tarfile, existing PWE and evidence utilities.

---

## File Map

- Create `block_kyfan_pinn/risk.py` — labels, feature validation, ranking metrics, logistic score, grouped bootstrap, gate.
- Create `scripts/generate_risk_development.py` — deterministic suite, disjointness checks, reference cache.
- Create `scripts/evaluate_risk_features.py` — evidence verification, checkpoint loading, paired inference, outputs, evidence bundle.
- Create `tests/test_risk.py` — pure risk-analysis tests.
- Create `tests/test_risk_protocol_integrity.py` — suite/archive/provenance/end-to-end tests.
- Create `benchmarks/risk_development_v1.json` and `.sha256` — frozen 160-point suite.
- Create `docs/RISK-DEVELOPMENT-RUNBOOK.zh-CN.md` — commands and interpretation.
- Modify `README.md` — add P0 entry without changing P5/final status.

## Task 1: Labels, Safe Features, and Ranking Metrics

**Files:**
- Create: `tests/test_risk.py`
- Create: `block_kyfan_pinn/risk.py`

- [ ] **Step 1: Write failing label and transform tests**

```python
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
    candidate = torch.tensor([1.0, 1.01, 1.02, 1.03])
    anchor = torch.ones(4)
    regression, unsafe = regression_labels(candidate, anchor)
    assert regression.tolist() == [False, True, True, True]
    assert unsafe.tolist() == [False, False, False, True]


def test_safe_log_ratio_is_finite_for_zero_inputs() -> None:
    result = safe_log_ratio(torch.tensor([0.0, 2.0]), torch.tensor([0.0, 1.0]))
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
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
uv run --python 3.12 --with-requirements requirements.txt \
  python -m pytest tests/test_risk.py -q
```

Expected: collection error `ModuleNotFoundError: No module named 'block_kyfan_pinn.risk'`.

- [ ] **Step 3: Implement the minimal pure functions**

Create `block_kyfan_pinn/risk.py` with:

```python
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
    candidate = _one_dimensional(candidate, "candidate")
    anchor = _one_dimensional(anchor, "anchor")
    if candidate.shape != anchor.shape:
        raise ValueError("candidate and anchor must have the same shape")
    return candidate > anchor, candidate > 1.02 * anchor


def safe_log_ratio(numerator: Tensor, denominator: Tensor, eps: float = 1e-12) -> Tensor:
    if eps <= 0:
        raise ValueError("eps must be positive")
    numerator = torch.as_tensor(numerator, dtype=torch.float64)
    denominator = torch.as_tensor(denominator, dtype=torch.float64)
    if numerator.shape != denominator.shape:
        raise ValueError("ratio operands must have the same shape")
    return torch.log(numerator.clamp_min(eps)) - torch.log(denominator.clamp_min(eps))


def binary_auroc(labels: Tensor, scores: Tensor) -> float:
    labels = torch.as_tensor(labels, dtype=torch.bool).flatten()
    scores = _one_dimensional(scores, "scores")
    if labels.shape != scores.shape:
        raise ValueError("labels and scores must have the same shape")
    positive = scores[labels]
    negative = scores[~labels]
    if positive.numel() == 0 or negative.numel() == 0:
        raise ValueError("AUROC requires both classes")
    comparisons = positive[:, None] - negative[None, :]
    return float(((comparisons > 0).double() + 0.5 * (comparisons == 0).double()).mean())


def average_precision(labels: Tensor, scores: Tensor) -> float:
    labels = torch.as_tensor(labels, dtype=torch.bool).flatten()
    scores = _one_dimensional(scores, "scores")
    if labels.shape != scores.shape or labels.sum() == 0:
        raise ValueError("average precision requires aligned labels and positives")
    order = torch.argsort(scores, descending=True, stable=True)
    ordered = labels[order].double()
    precision = ordered.cumsum(0) / torch.arange(1, ordered.numel() + 1, dtype=torch.float64)
    return float((precision * ordered).sum() / ordered.sum())
```

- [ ] **Step 4: Run tests and verify GREEN**

Run the Task 1 command. Expected: `4 passed`.

- [ ] **Step 5: Commit Task 1**

```bash
git add block_kyfan_pinn/risk.py tests/test_risk.py
git commit -m "feat: add deterministic risk labels and ranking metrics"
```

## Task 2: Coverage, Logistic Score, Bootstrap, and Gate

**Files:**
- Modify: `tests/test_risk.py`
- Modify: `block_kyfan_pinn/risk.py`

- [ ] **Step 1: Add failing tests for forbidden features, calibration-only fitting, coverage, and gates**

Append tests that import `FORBIDDEN_FEATURES`, `fit_logistic_score`, `predict_logistic_score`,
`risk_coverage`, `clustered_bootstrap_auc`, and `build_risk_gate` and assert:

```python
def test_fit_logistic_score_rejects_reference_features() -> None:
    features = torch.randn(8, 2)
    labels = torch.tensor([0, 1] * 4, dtype=torch.bool)
    with pytest.raises(ValueError, match="forbidden"):
        fit_logistic_score(features, labels, ["residual", "external_gap"])


def test_logistic_score_is_deterministic_and_orders_separable_data() -> None:
    x = torch.tensor([[-2.0], [-1.0], [1.0], [2.0]])
    y = torch.tensor([0, 0, 1, 1], dtype=torch.bool)
    first = fit_logistic_score(x, y, ["residual_delta"])
    second = fit_logistic_score(x, y, ["residual_delta"])
    scores = predict_logistic_score(x, first)
    assert first == second
    assert binary_auroc(y, scores) == pytest.approx(1.0)


def test_risk_coverage_removes_high_risk_failures_first() -> None:
    failure = torch.tensor([0, 0, 1, 1], dtype=torch.bool)
    severity = torch.tensor([-0.1, -0.2, 0.3, 0.4])
    scores = torch.tensor([0.1, 0.2, 0.8, 0.9])
    curve = risk_coverage(failure, severity, scores, coverages=(0.5, 0.8, 1.0))
    assert curve[0]["failure_rate"] == 0.0
    assert curve[-1]["failure_rate"] == pytest.approx(0.5)


def test_risk_gate_requires_every_scientific_threshold() -> None:
    metrics = {
        "engineering_pass": True,
        "primary_auroc": 0.72,
        "unsafe_auroc": 0.73,
        "primary_auroc_ci_low": 0.55,
        "family_auroc": {"harmonic_honeycomb": 0.68, "gaussian_honeycomb": 0.69},
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
```

- [ ] **Step 2: Run the focused tests and verify RED**

Expected: import errors for the missing APIs.

- [ ] **Step 3: Implement deterministic analysis APIs**

Add to `risk.py`:

```python
FORBIDDEN_FEATURES = frozenset({
    "split", "role", "projector_error", "delta_error", "regression",
    "unsafe_regression", "internal_gap", "external_gap", "reference_eigenvalues",
})


def validate_feature_names(names: list[str]) -> None:
    forbidden = sorted(set(names) & FORBIDDEN_FEATURES)
    if forbidden:
        raise ValueError(f"forbidden fitted features: {forbidden}")
    if len(names) != len(set(names)) or not names:
        raise ValueError("feature names must be non-empty and unique")


def fit_logistic_score(features: Tensor, labels: Tensor, names: list[str], l2: float = 1e-2) -> dict[str, object]:
    validate_feature_names(names)
    x = torch.as_tensor(features, dtype=torch.float64)
    y = torch.as_tensor(labels, dtype=torch.float64).flatten()
    if x.ndim != 2 or x.shape != (y.numel(), len(names)) or not bool(torch.isfinite(x).all()):
        raise ValueError("features must be a finite [rows, features] matrix")
    if y.min() == y.max():
        raise ValueError("logistic fitting requires both classes")
    mean = x.mean(0)
    scale = x.std(0, unbiased=False).clamp_min(1e-12)
    z = (x - mean) / scale
    weight = torch.zeros(z.shape[1], dtype=torch.float64, requires_grad=True)
    intercept = torch.zeros((), dtype=torch.float64, requires_grad=True)
    optimizer = torch.optim.LBFGS([weight, intercept], max_iter=100, tolerance_grad=1e-10)
    def closure() -> Tensor:
        optimizer.zero_grad()
        logits = z @ weight + intercept
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, y) + l2 * weight.square().sum()
        loss.backward()
        return loss
    optimizer.step(closure)
    return {
        "feature_names": names,
        "mean": mean.tolist(), "scale": scale.tolist(),
        "weight": weight.detach().tolist(), "intercept": float(intercept.detach()),
        "l2": l2,
    }


def predict_logistic_score(features: Tensor, model: dict[str, object]) -> Tensor:
    x = torch.as_tensor(features, dtype=torch.float64)
    mean = torch.tensor(model["mean"], dtype=torch.float64)
    scale = torch.tensor(model["scale"], dtype=torch.float64)
    weight = torch.tensor(model["weight"], dtype=torch.float64)
    intercept = float(model["intercept"])
    return torch.sigmoid(((x - mean) / scale) @ weight + intercept)


def risk_coverage(
    failure: Tensor,
    severity: Tensor,
    scores: Tensor,
    *,
    coverages: tuple[float, ...] = (0.5, 0.8, 1.0),
) -> list[dict[str, float]]:
    failure = torch.as_tensor(failure, dtype=torch.bool).flatten()
    severity = _one_dimensional(severity, "severity")
    scores = _one_dimensional(scores, "scores")
    if failure.shape != severity.shape or failure.shape != scores.shape:
        raise ValueError("coverage inputs must have the same shape")
    order = torch.argsort(scores, descending=False, stable=True)
    rows: list[dict[str, float]] = []
    for coverage in coverages:
        if not 0.0 < coverage <= 1.0:
            raise ValueError("coverage must be in (0, 1]")
        count = max(1, math.ceil(coverage * failure.numel()))
        selected = order[:count]
        rows.append({
            "coverage": coverage,
            "count": float(count),
            "failure_rate": float(failure[selected].double().mean()),
            "mean_positive_severity": float(severity[selected].clamp_min(0).mean()),
        })
    return rows


def clustered_bootstrap_auc(
    point_ids: list[str],
    labels: Tensor,
    scores: Tensor,
    *,
    samples: int = 1000,
    seed: int = 20260824,
) -> dict[str, float]:
    labels = torch.as_tensor(labels, dtype=torch.bool).flatten()
    scores = _one_dimensional(scores, "scores")
    if len(point_ids) != labels.numel() or labels.shape != scores.shape:
        raise ValueError("bootstrap rows must align")
    unique = sorted(set(point_ids))
    by_point = {point: [i for i, value in enumerate(point_ids) if value == point] for point in unique}
    generator = torch.Generator().manual_seed(seed)
    values: list[float] = []
    for _ in range(samples):
        draws = torch.randint(len(unique), (len(unique),), generator=generator)
        indices = [row for draw in draws.tolist() for row in by_point[unique[draw]]]
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
        "valid_samples": float(len(values)),
    }


def build_risk_gate(metrics: dict[str, object]) -> dict[str, object]:
    family = metrics["family_auroc"]
    checks = {
        "engineering_pass": bool(metrics["engineering_pass"]),
        "primary_auroc_pass": float(metrics["primary_auroc"]) >= 0.70,
        "unsafe_auroc_pass": float(metrics["unsafe_auroc"]) >= 0.70,
        "primary_ci_pass": float(metrics["primary_auroc_ci_low"]) > 0.50,
        "family_auroc_pass": all(float(value) >= 0.65 for value in family.values()),
        "primary_auprc_pass": float(metrics["primary_auprc"]) >= float(metrics["primary_prevalence"]) + 0.10,
        "top20_precision_pass": float(metrics["top20_precision"]) >= float(metrics["primary_prevalence"]) + 0.15,
        "coverage_safety_pass": float(metrics["unsafe_rate_at_80pct_coverage"]) <= 0.75 * float(metrics["unsafe_rate"]),
    }
    return {**checks, "risk_go": all(checks.values())}
```

Add `import math` to the module. Keep all returned counts JSON-serializable; the evaluator may cast
the count fields to integers when writing the final report.

- [ ] **Step 4: Run tests and verify GREEN**

Expected: all `tests/test_risk.py` tests pass.

- [ ] **Step 5: Run the full test suite**

```bash
uv run --python 3.12 --with-requirements requirements.txt python -m pytest -q
```

Expected: existing 120 tests plus the new risk tests pass.

- [ ] **Step 6: Commit Task 2**

```bash
git add block_kyfan_pinn/risk.py tests/test_risk.py
git commit -m "feat: add calibrated risk score and frozen gate"
```

## Task 3: Frozen Risk-Development Suite

**Files:**
- Create: `tests/test_risk_protocol_integrity.py`
- Create: `scripts/generate_risk_development.py`
- Create: `benchmarks/risk_development_v1.json`
- Create: `benchmarks/risk_development_v1.sha256`

- [ ] **Step 1: Write failing suite-integrity tests**

Tests import `generate_risk_development_suite` and assert exact 160-point counts, role/family/split
counts, deterministic bytes, and no parameter overlap with `v2_validation.json` or
`v2_frozen_test.json`. Add a committed-asset test that calls `load_frozen_suite`, checks the suite
ID/purpose, and verifies all exact/near reference semantics after the cache is generated.

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run --python 3.12 --with-requirements requirements.txt \
  python -m pytest tests/test_risk_protocol_integrity.py -q
```

Expected: import error for `scripts.generate_risk_development`.

- [ ] **Step 3: Implement deterministic point generation**

`generate_risk_development_suite()` calls the existing `_generate_family_points` twice per family:

```python
ROLE_COUNTS = {"iid_hidden": 8, "exact_cluster": 4, "near_cluster": 10,
               "strict_ood": 8, "gap_scan": 10}
ROLE_SEEDS = {"calibration": 2026082401, "audit": 2026082402}

def generate_risk_development_suite() -> list[dict[str, object]]:
    points = []
    for role, seed in ROLE_SEEDS.items():
        rng = random.Random(seed)
        for family in ("harmonic_honeycomb", "gaussian_honeycomb"):
            generated = _generate_family_points(
                family, rng, n_iid=8, n_exact=4, n_near=10, n_ood=8, n_gap_scan=10
            )
            counters: dict[str, int] = {}
            for point in generated:
                split = str(point["split"])
                index = counters.get(split, 0)
                counters[split] = index + 1
                point["role"] = role
                point["id"] = f"risk-{role}-{family}-{split}-{index:03d}"
                points.append(point)
    return points
```

Before writing, compare exact `(family, tuple(parameters))` identities against both committed V2
suites and between roles. Build the payload with purpose
`risk_calibration_and_heldout_audit_not_final_test`, add `role_counts`, and call
`write_frozen_suite`.

- [ ] **Step 4: Run suite tests and verify GREEN**

- [ ] **Step 5: Generate and inspect committed suite**

```bash
uv run --python 3.12 --with-requirements requirements.txt \
  python scripts/generate_risk_development.py --suite-only
shasum -a 256 -c benchmarks/risk_development_v1.sha256
```

Expected: 160 points, 80 per role, 80 per family, 32 IID, 16 exact, 40 near, 32 OOD,
40 gap-scan, and hash `OK`.

- [ ] **Step 6: Commit Task 3**

```bash
git add scripts/generate_risk_development.py tests/test_risk_protocol_integrity.py \
  benchmarks/risk_development_v1.json benchmarks/risk_development_v1.sha256
git commit -m "feat: freeze independent risk-development suite"
```

## Task 4: Reference Cache and P5 Archive Inventory

**Files:**
- Modify: `scripts/generate_risk_development.py`
- Create: `scripts/evaluate_risk_features.py`
- Modify: `tests/test_risk_protocol_integrity.py`

- [ ] **Step 1: Add failing tests for reference provenance and archive inventory**

Tests require:

- reference metadata with suite SHA, cutoff 24, grid side 33, rank 3;
- exact/near gap validation through `reference_gap_metadata`;
- archive SHA and manifest verification before checkpoint listing;
- exactly 12 allowed `final.pt` members for two methods × two families × three seeds;
- rejection of `latest.pt`, best checkpoints, unsafe paths, duplicate members, and unexpected methods.

- [ ] **Step 2: Verify RED**

Expected: missing `build_reference_cache` and `inventory_p5_checkpoints` APIs.

- [ ] **Step 3: Implement resumable reference caching**

Use `load_frozen_suite`, `solve_reference(... cutoff=24, rank=3, mode_shape="hexagonal")`,
`uniform_grid(33, dtype=torch.float64)`, `evaluate_reference_basis`, and
`reference_gap_metadata`. A partial cache is reusable only when suite SHA, cutoff, grid, rank,
and source fingerprint match. Save the completed cache atomically and write its exact-byte SHA.

- [ ] **Step 4: Implement verified checkpoint inventory**

In `evaluate_risk_features.py`, reuse `audit_p5_evidence` as the first gate. Abort unless
`audit_pass` is true and archive SHA equals the approved digest. Open the tar with safe member
checks and return inventory rows:

```python
{"method": method, "family": family, "seed": seed,
 "checkpoint_member": final_member, "result_member": result_member,
 "checkpoint_sha256": declared_final_sha}
```

Only `p5_anchor` and `p5_static_low_rom` are accepted.

- [ ] **Step 5: Run focused tests and verify GREEN**

- [ ] **Step 6: Generate local references**

```bash
uv run --python 3.12 --with-requirements requirements.txt \
  python scripts/generate_risk_development.py --device cpu --cache-only
```

Expected: 160 references, semantic gap checks pass, cache and SHA sidecar written under `data/`.

- [ ] **Step 7: Commit Task 4**

Commit source and tests only; the ignored cache is preserved locally and later bundled as evidence.

## Task 5: Paired Feature Extraction

**Files:**
- Modify: `scripts/evaluate_risk_features.py`
- Modify: `tests/test_risk_protocol_integrity.py`

- [ ] **Step 1: Add failing feature-extraction tests**

Create tiny anchor/ROM models and a two-point reference cache. Assert each output row contains:

```text
role,family,split,point_id,seed,
anchor_residual,candidate_residual,residual_delta,residual_log_ratio,
anchor_gram,candidate_gram,gram_delta,gram_log_ratio,
anchor_ritz_gap,candidate_ritz_gap,ritz_gap_delta,ritz_gap_log_ratio,
ritz_1_abs_difference,ritz_2_abs_difference,trace_abs_difference,
projector_disagreement,
anchor_projector_error,candidate_projector_error,delta_error,
regression,unsafe_regression,reference_internal_gap,reference_external_gap
```

Assert the fitted feature list includes only columns through `projector_disagreement` and excludes
role/family/split/labels/reference columns.

- [ ] **Step 2: Verify RED**

- [ ] **Step 3: Implement model reconstruction and paired evaluation**

For each inventory row, call `build_p5_model`, load the checkpoint payload from tar bytes with
`torch.load(io.BytesIO(...), map_location=device, weights_only=False)`, verify the declared
checkpoint hash and `checkpoint["config"]`, then call
`model.load_state_dict(checkpoint["model"])`. Use the existing P4 evaluation basis, Hamiltonian,
Ritz, Gram, residual, and projector utilities. Pair rows by
`(role, family, split, point_id, seed)` and calculate features with safe log ratios.

- [ ] **Step 4: Add resume protection**

One completed unit is `(method, family, seed)`. Reuse it only if suite SHA, evidence SHA,
checkpoint SHA, source fingerprint, device type, and feature schema match. Remove any previous
`gate.json` before a run starts.

- [ ] **Step 5: Run focused and full tests**

- [ ] **Step 6: Commit Task 5**

```bash
git add scripts/evaluate_risk_features.py tests/test_risk_protocol_integrity.py
git commit -m "feat: extract paired label-free risk features"
```

## Task 6: Calibration, Audit, Gate, and Evidence Bundle

**Files:**
- Modify: `scripts/evaluate_risk_features.py`
- Modify: `tests/test_risk_protocol_integrity.py`

- [ ] **Step 1: Add failing end-to-end gate tests**

Use synthetic paired rows with known separable scores to assert GO and shuffled scores to assert
STOP. Verify calibration statistics and coefficients never use audit rows, audit is evaluated once,
point IDs remain grouped, and outputs contain all provenance fields.

- [ ] **Step 2: Verify RED**

- [ ] **Step 3: Implement calibration and held-out audit**

Use the exact promoted feature order:

```python
PROMOTED_FEATURES = [
    "anchor_residual", "candidate_residual", "residual_delta", "residual_log_ratio",
    "anchor_gram", "candidate_gram", "gram_delta", "gram_log_ratio",
    "anchor_ritz_gap", "candidate_ritz_gap", "ritz_gap_delta", "ritz_gap_log_ratio",
    "ritz_1_abs_difference", "ritz_2_abs_difference", "trace_abs_difference",
    "projector_disagreement",
]
```

Fit only rows whose point role is calibration. Freeze `calibration_model.json`, then score audit
rows. Compute primary/unsafe metrics, family metrics, top-20%, coverage, and clustered-bootstrap
CI. Call `build_risk_gate` and write `RISK_DEVELOPMENT_GO` or `RISK_DEVELOPMENT_STOP`.

- [ ] **Step 4: Implement evidence packaging**

Bundle suite/sidecar, reference cache/sidecar, P5 archive SHA reference, source files,
checkpoint inventory, features CSV, calibration model, metrics, gate, environment, and report.
Manifest every file's bytes and SHA; write outer sidecar. Do not include or read frozen-final
references.

- [ ] **Step 5: Run focused and full tests**

- [ ] **Step 6: Commit Task 6**

```bash
git add scripts/evaluate_risk_features.py tests/test_risk_protocol_integrity.py
git commit -m "feat: add held-out risk decision and evidence bundle"
```

## Task 7: Runbook, README, and Local P0 Execution

**Files:**
- Create: `docs/RISK-DEVELOPMENT-RUNBOOK.zh-CN.md`
- Modify: `README.md`

- [ ] **Step 1: Write the runbook**

Document exactly:

```bash
uv run --python 3.12 --with-requirements requirements.txt python -m pytest -q
uv run --python 3.12 --with-requirements requirements.txt \
  python scripts/generate_risk_development.py --suite-only
uv run --python 3.12 --with-requirements requirements.txt \
  python scripts/generate_risk_development.py --device cpu --cache-only
uv run --python 3.12 --with-requirements requirements.txt \
  python scripts/evaluate_risk_features.py --device mps
```

Include expected files, evidence hash verification, GO/STOP interpretation, resume rules, and the
explicit ban on frozen final and P6 prompt creation after STOP.

- [ ] **Step 2: Update README status**

Add a P0 section that points to the runbook and states that P5 remains STOP until a separately
audited risk GO; do not replace or soften the P5 result.

- [ ] **Step 3: Run the full local P0 pipeline**

Run tests, suite generation, CPU reference cache, and MPS feature evaluation. Record actual wall
time and environment. If MPS encounters an unsupported operation, rerun inference on CPU and record
the fallback; do not change feature definitions or gates.

- [ ] **Step 4: Independently verify outputs**

Check suite SHA, evidence archive SHA, exact point/run counts, no validation/final overlap, no
prohibited features, and recompute the gate from `features.csv` in a separate process.

- [ ] **Step 5: Update the canonical workspace record**

Only after verified execution, update
`/Users/lazywords/Paper/PINN&PNE/00_项目总览/00_当前研究总档案.md` with the actual P0
result and distinguish GO, STOP, unrun, and expected states.

- [ ] **Step 6: Commit Task 7**

```bash
git add README.md docs/RISK-DEVELOPMENT-RUNBOOK.zh-CN.md
git commit -m "docs: add risk-development runbook and status"
```

## Completion Gate

Before declaring P0 complete:

```bash
git status --short
uv run --python 3.12 --with-requirements requirements.txt python -m pytest -q
shasum -a 256 -c benchmarks/risk_development_v1.sha256
```

Required evidence:

- clean source commit and recorded source fingerprint;
- complete 160-point suite and 480 paired rows;
- verified P5 archive and exactly 12 final checkpoints;
- independent calibration/audit roles;
- risk gate recomputation equality;
- evidence archive/manifest/sidecar integrity;
- no access to `v2_frozen_test` references or `evaluate_v2_final.py`;
- no P6 GPU prompt unless a separately reviewed `RISK_DEVELOPMENT_GO` is independently verified.

# Independent Risk-Development Design

## 1. Decision

Implement a new **P0 risk-detectability stage** before any conditional corrector or new GPU
training. P0 reuses the independently audited P5 `p5_anchor` and `p5_static_low_rom` final
checkpoints, evaluates them on a new parameter suite, and asks whether inference-time,
label-free quantities can rank the points where the ROM candidate regresses relative to the
anchor.

P0 is a scientific falsification stage, not a method-promotion stage. It may read only the
parameter coordinates in `benchmarks/v2_frozen_test.json` for mechanical overlap rejection. It
must not read frozen-final references, labels, checkpoints or results; run
`scripts/evaluate_v2_final.py`; retrain P5; or change the frozen P5 gate.

## 2. Alternatives Considered

### A. Reanalyse P5 validation only

This is cheap and useful for diagnostics, but every threshold would be selected and evaluated
on the same 64 validation points. It cannot support a new method claim. The existing exploratory
analysis remains historical context only.

### B. Independent suite plus fixed P5 checkpoints — selected

Generate a disjoint risk-development suite, precompute high-accuracy PWE references, evaluate
fixed audited checkpoints, calibrate a small deterministic risk score on one half, and evaluate
it once on the held-out half. This isolates the risk hypothesis while remaining feasible on an
Apple M4 or one consumer GPU.

### C. Train an end-to-end neural router immediately

This has higher capacity but introduces a second learned model before risk detectability has
been established. It increases overfitting, compute, and reviewer skepticism. It is explicitly
deferred until P0 passes.

## 3. Scientific Question and Targets

For a parameter point `x`, potential family `f`, and paired seed `s`, define:

- `e_rom(x,f,s)`: rank-2 projector sine error of `p5_static_low_rom`;
- `e_anchor(x,f,s)`: rank-2 projector sine error of `p5_anchor`;
- `delta_error = e_rom - e_anchor`;
- `regression = 1[delta_error > 0]`;
- `unsafe_regression = 1[e_rom > 1.02 * e_anchor]`.

`delta_error`, `regression`, and `unsafe_regression` are evaluation labels. They are computed
from PWE reference projectors after inference and must never be inputs to a risk score.

The primary question is whether a score constructed only from quantities available at inference
can rank `regression`. The safety question repeats the analysis for `unsafe_regression`. The
continuous `delta_error` is used for risk–coverage and severity plots, not for fitting a hidden
oracle feature.

## 4. Independent Suite

Create `benchmarks/risk_development_v1.json` and its SHA-256 sidecar with these frozen properties:

- suite id: `block-kyfan-risk-development-v1-20260824`;
- purpose: `risk_calibration_and_heldout_audit_not_final_test`;
- total points: 160;
- potential families: harmonic honeycomb and Gaussian honeycomb;
- roles: 80 `calibration`, 80 `audit`;
- for each role and family: 8 IID, 4 exact-cluster, 10 near-cluster, 8 strict-OOD,
  and 10 gap-scan points;
- calibration seed: `2026082401`;
- audit seed: `2026082402`;
- point IDs include role, family, split, and a zero-padded index;
- exact and near points satisfy the existing internal/external gap semantics;
- strict-OOD points are outside the corresponding training box;
- no `(family, parameters)` tuple overlaps `v2_validation.json` or `v2_frozen_test.json`;
- no calibration tuple overlaps an audit tuple.

The final-suite JSON is used only as a set of parameter identities in this overlap check. No
frozen-final reference cache or evaluation output is opened.

References use the existing symmetry-closed hexagonal PWE solver with cutoff 24, rank 3,
float64 assembly, and the existing 33×33 evaluation grid. The reference cache records suite
SHA, cutoff, grid, eigenvalues, rank-2 basis, internal gap, and external gap. Reference gaps are
allowed only as post-inference audit metadata and stratification variables, never in score inputs.

## 5. Checkpoint Scope and Pairing

Read only the authoritative archive
`artifacts/p5-evidence-20260801-092048.tar.gz`, whose expected SHA-256 is
`56891c5740eb94c62299b72869d790a1cbdee6abda3fae2903ed822f5e405101`.

Evaluate exactly:

- `p5_anchor` × 2 families × seeds 42, 137, 251;
- `p5_static_low_rom` × 2 families × seeds 42, 137, 251.

The archive reader verifies the outer sidecar and internal manifest before loading any
checkpoint. Every ROM row must have one anchor row with identical family, seed, and point ID.
No best-checkpoint selection is permitted; only each run's declared `final.pt` is loaded.

The unit of data splitting is the parameter point, not the seed-point row. All three seeds for a
point stay in the same role. Statistical confidence intervals resample points as clusters so the
three seeds are not treated as independent parameter samples.

## 6. Permitted Risk Features

P0 v1 uses only features already obtainable from the two fixed rank-2 predictors:

1. candidate and anchor projected residual RMS;
2. residual difference and log-ratio;
3. candidate and anchor raw-basis Gram condition number;
4. Gram difference and log-ratio;
5. candidate and anchor predicted internal Ritz gap `|ritz_2 - ritz_1|`;
6. internal Ritz-gap difference and log-ratio;
7. absolute differences of the two predicted Ritz values and their trace;
8. basis-invariant projector disagreement between candidate and anchor.

Normalized PDE parameters may be evaluated as a **parameter-only leakage baseline**, but they
are excluded from the promoted risk score. Split names, reference eigenvalues, reference gaps,
reference projectors, projector errors, and failure labels are forbidden score inputs.

P0 v1 does not claim a predicted external eigengap: both P5 models expose only a rank-2 trial
space, so a third Ritz direction is unavailable. Adding a third trial direction would change the
model and requires a separate approved design.

Single-feature rankings and simple hand-written scores are reported as diagnostics. The selected
composite score is an L2-regularized logistic regression implemented with PyTorch on standardized
features. It uses fixed regularization `1e-2`, fits calibration rows only, and is evaluated once
on audit rows. No audit-driven feature selection, threshold tuning, or regularization search is
allowed.

## 7. Outputs

P0 writes under `results/risk_development_v1/`:

- `environment.json`;
- `checkpoint_inventory.json`;
- `features.csv`: one paired seed-point row with permitted features and audit labels;
- `calibration_model.json`: feature order, calibration means/scales, coefficients, intercept,
  fixed regularization, and calibration suite SHA;
- `metrics.json`: calibration and audit AUROC, AUPRC, prevalence, top-20% precision/recall,
  risk–coverage, selective error, and clustered-bootstrap intervals;
- `gate.json`;
- `report.md` clearly marked as development evidence, not final test;
- an evidence tarball with manifest and SHA-256 sidecar.

Figures are generated only from `features.csv` and `metrics.json`: ROC/PR, risk–coverage,
calibration, split/family failure rate, and risk versus `delta_error`.

## 8. Gate

Engineering gates:

- suite and sidecar hashes match;
- 160 unique points, correct role/family/split counts, and zero overlap with validation/final;
- evidence archive integrity passes before checkpoint loading;
- all 12 checkpoint runs load and every paired row is present;
- 480 paired rows are finite;
- prohibited inputs are absent from the fitted feature list;
- all outputs record source commit, suite SHA, archive SHA, device, PyTorch version, and seed.

Scientific `risk_go` requires all of:

- held-out audit AUROC for `regression` ≥ 0.70;
- held-out audit AUROC for `unsafe_regression` ≥ 0.70;
- point-clustered 95% CI lower bound for primary AUROC > 0.50;
- each potential family's primary AUROC ≥ 0.65;
- primary audit AUPRC ≥ audit prevalence + 0.10;
- top-20% primary precision ≥ audit prevalence + 0.15;
- at 80% coverage, the retained rows' unsafe-regression rate is at least 25% lower than the
  unfiltered audit rate;
- all engineering gates pass.

If any condition fails, the status is `RISK_DEVELOPMENT_STOP`. No conditional corrector, P6 GPU
matrix, or GPU executor prompt is created.

If every condition passes, the status is `RISK_DEVELOPMENT_GO`. This authorizes design of a
conditional corrector; it does not authorize frozen final.

## 9. Components and File Boundaries

- `block_kyfan_pinn/risk.py`: pure feature transforms, binary-label helpers, deterministic
  standardization/logistic fitting, ranking metrics, grouped bootstrap, and gate construction;
- `scripts/generate_risk_development.py`: deterministic suite generation, overlap rejection,
  sidecar writing, and optional reference-cache creation;
- `scripts/evaluate_risk_features.py`: verified archive loading, checkpoint reconstruction,
  paired inference, raw CSV writing, calibration-only fit, audit evaluation, and evidence bundle;
- `tests/test_risk.py`: unit tests for labels, forbidden-feature enforcement, metrics,
  deterministic fitting, coverage, and gates;
- `tests/test_risk_protocol_integrity.py`: suite counts/disjointness, archive/checkpoint pairing,
  no-final access, provenance, and small end-to-end smoke tests;
- `benchmarks/risk_development_v1.json` and `.sha256`: committed frozen development suite;
- `data/risk_development_v1_references.pt` and `.sha256`: reproducible local cache, both ignored
  by Git and included in the P0 evidence bundle;
- `docs/RISK-DEVELOPMENT-RUNBOOK.zh-CN.md`: commands, expected outputs, interpretation, and
  recovery rules.

The existing P3 fallback functions are not modified during P0. They are scientifically
insufficient until the new risk gate passes.

## 10. Data Flow

1. Generate the deterministic suite and reject all overlap.
2. Compute or load SHA-bound PWE references.
3. Verify the P5 evidence archive and enumerate the 12 allowed final checkpoints.
4. Reconstruct the exact model/config for each checkpoint.
5. Evaluate candidate and anchor on each point and seed.
6. Join paired outputs by role, family, seed, and point ID.
7. Compute permitted label-free features.
8. Compute reference-only labels in a separate audit namespace.
9. Fit standardization and logistic coefficients on calibration points only.
10. Freeze the fitted model JSON.
11. Evaluate the audit role once, bootstrap by point, and build the gate.
12. Package every input/output hash and emit GO or STOP.

## 11. Error Handling

The run stops without partial promotion if it encounters a hash mismatch, unsafe tar path,
duplicate archive member, missing checkpoint, mismatched final checkpoint hash, duplicate point,
suite overlap, missing paired row, non-finite feature, prohibited fitted feature, calibration/audit
role leakage, reference-gap semantic violation, or output provenance mismatch.

Interrupted reference generation may resume only from a partial cache whose suite SHA, cutoff,
grid, and source fingerprint match. Interrupted feature evaluation may resume only completed
seed/family/checkpoint units with matching checkpoint and suite hashes. Gate files from a prior
run are deleted before a new evaluation begins.

## 12. Testing Strategy

Implementation follows test-first development. Tests must first fail because the new APIs/files do
not exist, then pass after minimal implementation.

Required coverage includes:

- exact label boundary at equality and the 2% unsafe threshold;
- zero/negative values in safe log-ratio transforms;
- AUROC/AUPRC on known rankings and single-class rejection;
- risk–coverage ordering and clustered bootstrap determinism;
- calibration-only standardization and fitting;
- forbidden feature names rejected;
- suite determinism, exact counts, sidecar validity, and disjointness from validation/final;
- archive integrity and exactly 12 allowed final checkpoints;
- point-grouped role separation;
- tiny CPU/MPS feature smoke without frozen-final reads;
- STOP and GO gate fixtures;
- full existing test-suite regression.

## 13. Large-Experiment Prompt Policy

No large-experiment prompt is written during P0 design or implementation. After an independently
verified `RISK_DEVELOPMENT_GO`, create a separately reviewed
`docs/P6-GPU-EXECUTOR-PROMPT.zh-CN.md` containing:

- the exact clean Git commit and branch;
- one RTX 4090/5090 requirement, software image, disk, and expected duration;
- cache, engineering smoke, two-family × three-seed pilot, and STOP/GO commands;
- fixed seeds, budgets, baselines, metrics, and gates;
- explicit prohibition on frozen-final execution;
- checkpoint/log/CSV/environment/manifest/SHA return requirements;
- automatic stop on engineering failure, risk regression, gap regression, or evidence mismatch;
- shutdown and local-backup instructions.

The prompt must contain no placeholders and must be generated from the promoted protocol, not from
theoretical expectations.

## 14. Scope Exclusions

P0 does not implement a learned neural router, conditional correction, third Ritz state, new ROM,
new PDE, quantum geometry, full baseline matrix, promotion matrix, or frozen-final evaluation.
Those require a new design after `RISK_DEVELOPMENT_GO`.

# P1 Risk-Gated Spectral-Subspace Corrector Design

## 1. Decision

Build P1 as a **basis-invariant, risk-gated corrector for rank-two Bloch spectral
subspaces**.  It reuses the independently audited P5 `p5_anchor`,
`p5_static_low_rom`, and `p5_long_anchor` final checkpoints.  At inference it
computes the anchor and ROM trial subspaces, evaluates the frozen P0 risk score,
aligns the ROM basis to the anchor by complex orthogonal Procrustes, and retracts
a risk-controlled chordal correction back to the Grassmann manifold.

P1 is a development pilot.  It does not retrain P5, read the frozen V2 final
references, run `scripts/evaluate_v2_final.py`, or change the P0/P5 decisions.

## 2. Research Object

The underlying PDE remains the two-dimensional periodic Bloch--Schrodinger
eigenproblem

\[
\left[\tfrac12(-i\nabla+k)^T G(-i\nabla+k)+V_\mu(x)\right]u_j
=E_j u_j,
\qquad x\in[0,2\pi)^2,
\]

with periodic boundary conditions.  The neural output is the rank-two spectral
projector associated with the lowest internally crossing eigenvalue cluster,
not two individually labelled eigenfunctions.  Harmonic and localized Gaussian
honeycomb potentials are both retained.

## 3. Alternatives Considered

### A. Twin-network risk-gated correction -- selected

Use the audited anchor and ROM networks as independent predictions.  This is the
only option directly supported by P0, because P0 calibrated risk from paired
anchor/ROM inference quantities.  Its weakness is roughly two neural forward
passes per query; the pilot therefore reports end-to-end latency and many-query
break-even rather than hiding the cost.

### B. Single-ROM internal-base gate -- efficiency ablation

Treat the `p5_static_low_rom` model's own base branch as the anchor and gate its
ROM correction.  It needs only one shared trunk evaluation, but P0 did not audit
this pair and the jointly trained base branch may be weaker than the independent
anchor.  It is an ablation, not the promoted P1 method.

### C. New shared-trunk dual-head network -- deferred

Train a new shared anchor/correction network and a learned router end to end.
This may reduce inference cost, but it adds a new training mechanism before the
fixed-checkpoint routing hypothesis is falsified.  It is authorized only if P1
passes and the twin-network cost is the remaining publication blocker.

## 4. Basis-Invariant Corrector

Let `Q_a` and `Q_r` be cell-L2 orthonormal anchor and ROM bases.  Form the complex
overlap `C = Q_a^* Q_r` and compute `C = U S V^*`.  The unitary Procrustes factor
is `R = V U^*`; the aligned ROM basis is `Q_r R`.  This removes arbitrary
rank-two basis rotations at exact and near degeneracies.

For frozen risk score `s`, define two thresholds from P0 calibration rows only:

- `t_low`: the 60th percentile of calibration scores;
- `t_high`: the 90th percentile of calibration scores.

The ROM weight is

\[
\alpha(s)=\operatorname{clamp}
\left(\frac{t_{high}-s}{t_{high}-t_{low}},0,1\right).
\]

The main neural output is

\[
Q_{P1}=\operatorname{MGS}\bigl(Q_a+
\alpha(s)(Q_rR-Q_a)\bigr).
\]

The score and thresholds are detached inference controls; no reference solution,
reference gap, projector error, split name, or failure label is available to the
router at inference.

Two controls are required:

- `hard_select`: ROM below the P0 calibration 80th percentile, otherwise anchor;
- `no_risk_half_blend`: fixed `alpha=0.5` after Procrustes alignment.

The primary gate is evaluated first without PWE.  A separate safety variant may
replace only the top 5% P0-calibration risk tail with cutoff-24 PWE.  PWE results
must be reported separately and cannot rescue a failed neural-only primary gate.

## 5. Independent P1 Pilot Suite

Create `benchmarks/p1_validation_v1.json` and its SHA-256 sidecar with 96 new
points, disjoint from V2 validation, V2 frozen final, and P0 risk development:

- 48 harmonic and 48 Gaussian points;
- per family: 8 IID, 8 exact-cluster, 16 near-cluster, 8 strict-OOD, 8 gap-scan;
- deterministic seed `2026082403`;
- suite id `block-kyfan-p1-validation-v1-20260824`;
- purpose `p1_risk_gated_corrector_pilot_not_final_test`;
- PWE cutoff 24, rank 3, 33x33 grid, float64 reference assembly.

The suite is evaluated once after the P0 calibration model, feature schema,
threshold quantiles, methods, and P1 gate have been frozen in code and tests.

## 6. Methods and Fairness

Evaluate two families and seeds 42, 137, and 251 for:

1. `p5_anchor`;
2. `p5_long_anchor`;
3. `p5_static_low_rom`;
4. `p1_hard_select`;
5. `p1_no_risk_half_blend`;
6. `p1_risk_chordal` (primary);
7. `p1_risk_chordal_pwe5` (reported safety variant, not primary rescue);
8. `oracle_min_anchor_rom` (reference-only upper bound, never deployable).

All neural methods use the exact audited final checkpoints.  No best checkpoint,
extra optimization step, hidden parameter point, or audit-selected threshold is
allowed.  Timing uses warm-up plus at least 100 repeated queries per method on
the same device.  PWE time is included in the safety variant.

## 7. Frozen P1 Gate

Engineering requirements:

- suite/sidecar, P0 evidence/sidecar, P5 evidence/sidecar, and reference cache
  hashes all match;
- exactly 96 points and 288 family-seed rows per method;
- every output is finite;
- maximum orthogonality error is below `1e-4`;
- the fitted feature order exactly equals P0 `PROMOTED_FEATURES`;
- P0 calibration thresholds are recorded before P1 references are evaluated;
- provenance records Git commit, device, PyTorch/ROCm version, all source hashes,
  checkpoint hashes, and seeds.

`P1_PILOT_GO` requires the neural-only `p1_risk_chordal` to satisfy all of:

- near-cluster projector error is at least 5% lower than `p5_long_anchor`;
- gap-scan projector error is at most 2% above the best of `p5_anchor` and
  `p5_long_anchor`;
- near-cluster error is lower than `p5_long_anchor` in both potential families;
- at least 5 of 6 family-by-seed near-cluster comparisons beat long-anchor;
- overall error is lower than both `p5_anchor` and `p5_static_low_rom`;
- unsafe regression relative to anchor is at least 25% lower than static ROM;
- numerical PWE fallback fraction is exactly zero for the primary method;
- measured neural inference latency is no more than 2.5 times anchor latency.

If any primary requirement fails, status is `P1_PILOT_STOP`.  The PWE safety
variant, oracle, or a favourable single family cannot override STOP.

## 8. Outputs

Write under `results/p1_pilot/`:

- `environment.json`, `provenance.json`, and `checkpoint_inventory.json`;
- `thresholds.json` containing P0-only quantiles;
- one SHA-bound unit JSON per family and seed;
- `rows.csv`, `summary.json`, `gate.json`, and `report.md`;
- figures for method-by-split error, near/gap paired wins, risk versus selected
  weight, risk--coverage, error maps, latency, fallback rate, and oracle gap;
- a self-contained `artifacts/p1-pilot-evidence-*.tar.gz` plus sidecar and
  internal manifest.

## 9. File Boundaries

- `block_kyfan_pinn/p1_corrector.py`: complex Procrustes alignment, score-to-weight
  mapping, chordal retraction, hard selector, and P1 gate helpers;
- `scripts/generate_p1_validation.py`: suite generation, overlap rejection, and
  reference cache;
- `scripts/run_p1_pilot.py`: evidence verification, fixed-checkpoint inference,
  timing, aggregation, gate, and evidence packaging;
- `tests/test_p1_corrector.py`: pure mathematical and gate tests;
- `tests/test_p1_protocol_integrity.py`: suite, evidence, provenance, and tiny
  end-to-end tests;
- `docs/P1-RUNBOOK.zh-CN.md`: exact local and ROCm commands and interpretation.

## 10. Error Handling and Resume

Abort without promotion on hash mismatch, unsafe archive member, source mismatch,
duplicate point, suite overlap, incomplete checkpoint pairing, prohibited P0
feature, non-finite score, rank-deficient blend, incomplete unit, or stale unit
provenance.  Resume accepts a unit only when its JSON sidecar and every suite,
reference, source, model, and threshold hash match.

## 11. Scope Boundary

P1 does not open frozen final, claim publication readiness, train a new router,
replace the P5 STOP decision, or generate paper results from smoke tests.  A P1
GO authorizes an independent AMD/CUDA promotion matrix and a reviewed executor
prompt.  Publication remains NO until promotion, final, baselines, ablations,
statistics, efficiency, and figures are complete.

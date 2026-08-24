# P1 Risk-Gated Spectral-Subspace Corrector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a hash-bound P1 pilot that tests whether P0 risk can safely gate a basis-invariant correction between audited anchor and ROM neural spectral-subspace solvers.

**Architecture:** Add a pure Grassmann correction module, a deterministic P1 suite generator, and a fixed-checkpoint pilot executor.  Thresholds come only from the P0 calibration model/evidence; the P1 suite is evaluated once, the neural-only method owns the promotion gate, and the optional PWE safety variant is reported separately.

**Tech Stack:** Python 3.12, PyTorch 2.11/2.8, ROCm 7.2.3 or Apple MPS/CPU, pytest, JSON/CSV/tarfile, existing PWE and evidence utilities.

---

## File Map

- Create `block_kyfan_pinn/p1_corrector.py` -- alignment, routing, correction, metrics, gate.
- Create `tests/test_p1_corrector.py` -- pure complex-geometry, routing, and gate tests.
- Create `scripts/generate_p1_validation.py` -- frozen suite and reference cache.
- Create `benchmarks/p1_validation_v1.json` and `.sha256` -- 96-point P1 pilot suite.
- Create `tests/test_p1_protocol_integrity.py` -- disjointness, evidence, resume, and smoke tests.
- Create `scripts/run_p1_pilot.py` -- verified checkpoint evaluation and evidence bundle.
- Create `docs/P1-RUNBOOK.zh-CN.md` -- local/ROCm commands and scientific interpretation.
- Modify `docs/CURRENT-STATUS.zh-CN.md` and `README.md` only after the actual pilot result exists.

## Task 1: Complex Procrustes Alignment and Risk Routing

**Files:**
- Create: `tests/test_p1_corrector.py`
- Create: `block_kyfan_pinn/p1_corrector.py`

- [ ] **Step 1: Write failing tests**

Add tests that construct two periodic orthonormal complex bases, rotate one by a
known `2x2` unitary, and require `complex_procrustes_align` to recover projector-
equivalent columns.  Add tests for exact `t_low/t_high` endpoint weights, monotone
weights, a rank-two orthonormal `risk_chordal_correct`, and a hard selector that
returns only anchor or aligned ROM.

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run --python 3.12 --with-requirements requirements.txt \
  python -m pytest tests/test_p1_corrector.py -q
```

Expected: collection fails because `block_kyfan_pinn.p1_corrector` does not exist.

- [ ] **Step 3: Implement the minimal APIs**

Implement these exact public functions:

```python
def complex_procrustes_align(anchor: Tensor, candidate: Tensor) -> Tensor: ...
def risk_weight(score: Tensor, t_low: float, t_high: float) -> Tensor: ...
def risk_chordal_correct(anchor: Tensor, candidate: Tensor, weight: Tensor) -> Tensor: ...
def hard_select(anchor: Tensor, candidate: Tensor, use_candidate: Tensor) -> Tensor: ...
def build_p1_gate(summary: dict[str, object]) -> dict[str, object]: ...
```

Use `metrics._complex_overlap`, complex `torch.linalg.svd`, explicit real/imaginary
matrix multiplication, and `physics.periodic_mgs`.  Reject unequal shapes,
non-finite values, invalid thresholds, and wrong mask/weight batch shapes.

- [ ] **Step 4: Verify GREEN and regression safety**

Run the focused test and then:

```bash
uv run --python 3.12 --with-requirements requirements.txt python -m pytest -q
```

Expected: all existing 146 tests plus the new P1 tests pass.

- [ ] **Step 5: Commit**

```bash
git add block_kyfan_pinn/p1_corrector.py tests/test_p1_corrector.py
git commit -m "feat: add basis-invariant risk-gated corrector"
```

## Task 2: Frozen P1 Pilot Suite

**Files:**
- Create: `scripts/generate_p1_validation.py`
- Create: `tests/test_p1_protocol_integrity.py`
- Create: `benchmarks/p1_validation_v1.json`
- Create: `benchmarks/p1_validation_v1.sha256`

- [ ] **Step 1: Write deterministic-suite tests**

Require 96 unique points, the exact family/split counts from the design, byte-
identical regeneration, correct suite id/purpose/seed, valid sidecar, and zero
parameter overlap with `v2_validation.json`, `v2_frozen_test.json`, and
`risk_development_v1.json`.

- [ ] **Step 2: Verify RED**

```bash
uv run --python 3.12 --with-requirements requirements.txt \
  python -m pytest tests/test_p1_protocol_integrity.py -q
```

Expected: import failure for `scripts.generate_p1_validation`.

- [ ] **Step 3: Implement suite generation**

Reuse the deterministic family point generator from
`scripts/generate_risk_development.py`, but use seed `2026082403`, counts
`8/8/16/8/8`, P1-specific IDs, and explicit overlap rejection against all three
earlier suites.  Write canonical JSON plus a standard SHA-256 sidecar.

- [ ] **Step 4: Freeze and verify the suite**

```bash
uv run --python 3.12 --with-requirements requirements.txt \
  python scripts/generate_p1_validation.py --suite-only
shasum -a 256 -c benchmarks/p1_validation_v1.sha256
```

Expected: 96 points and `OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_p1_validation.py tests/test_p1_protocol_integrity.py \
  benchmarks/p1_validation_v1.json benchmarks/p1_validation_v1.sha256
git commit -m "feat: freeze independent P1 pilot suite"
```

## Task 3: P0 Calibration Extraction and Frozen Thresholds

**Files:**
- Modify: `scripts/run_p1_pilot.py`
- Modify: `tests/test_p1_protocol_integrity.py`

- [ ] **Step 1: Test evidence verification**

Require the P0 archive digest
`d5783e65e7c55149206757505bae922193b5315b5596b6324fe0f8f07c2ed81d`,
its sidecar, safe unique tar members, the embedded P5 archive, P0
`calibration_model.json`, and P0 `features.csv`.  Reject any schema other than
`PROMOTED_FEATURES` and any archive whose stored P0 gate is not GO.

- [ ] **Step 2: Test calibration-only thresholds**

Build scores from rows whose role is exactly `calibration`; require the 60th,
80th, 90th, and 95th quantiles to be deterministic and prove that changing audit
rows cannot change thresholds.

- [ ] **Step 3: Implement extraction**

Create `scripts/run_p1_pilot.py` with pure helpers
`load_p0_calibration`, `frozen_thresholds`, and `p1_source_fingerprint`.  Record
the P0 archive, model, feature schema, row count, and threshold hashes in
`results/p1_pilot/thresholds.json` before loading P1 references.

- [ ] **Step 4: Run focused tests and commit**

```bash
uv run --python 3.12 --with-requirements requirements.txt \
  python -m pytest tests/test_p1_protocol_integrity.py -q
git add scripts/run_p1_pilot.py tests/test_p1_protocol_integrity.py
git commit -m "feat: bind P1 routing to P0 calibration evidence"
```

## Task 4: Reference Cache and Fixed-Checkpoint Inference

**Files:**
- Modify: `scripts/generate_p1_validation.py`
- Modify: `scripts/run_p1_pilot.py`
- Modify: `tests/test_p1_protocol_integrity.py`

- [ ] **Step 1: Add tiny-cache and paired-inference tests**

Use a two-point temporary suite and cutoff 2 for the cache test.  Use small
synthetic anchor/candidate modules for the inference test and require all seven
deployable method rows, finite residual/projector/orthogonality metrics, detached
risk score/weight, and zero PWE use in the primary method.

- [ ] **Step 2: Implement cache generation**

Reuse `build_reference_cache` with cutoff 24, rank 3, 33x33 grid, float64 CPU
assembly, atomic writes, source fingerprint, suite SHA, and sidecar validation.

- [ ] **Step 3: Implement one-point evaluation**

Load the exact audited P5 anchor, long-anchor, and static-ROM final checkpoints
for the same family/seed.  Reuse `build_paired_feature_row` to preserve the P0
feature schema, compute the frozen score, form hard/fixed/risk chordal outputs,
and evaluate the reference projector only after all inference features and
weights are frozen.

- [ ] **Step 4: Verify and commit**

```bash
uv run --python 3.12 --with-requirements requirements.txt \
  python -m pytest tests/test_p1_protocol_integrity.py -q
git add scripts/generate_p1_validation.py scripts/run_p1_pilot.py \
  tests/test_p1_protocol_integrity.py
git commit -m "feat: evaluate fixed P1 correction methods"
```

## Task 5: Aggregation, Gate, Timing, Resume, and Evidence

**Files:**
- Modify: `block_kyfan_pinn/p1_corrector.py`
- Modify: `scripts/run_p1_pilot.py`
- Modify: `tests/test_p1_corrector.py`
- Modify: `tests/test_p1_protocol_integrity.py`

- [ ] **Step 1: Add GO/STOP gate fixtures**

The GO fixture must satisfy every exact threshold in the design.  Independently
flip near improvement, gap safety, one family, paired wins, overall error,
unsafe reduction, orthogonality, primary PWE fraction, and latency to prove each
condition forces STOP.

- [ ] **Step 2: Add resume-integrity tests**

Each family-seed unit must have a SHA sidecar and bind suite, reference, P0/P5
archive, thresholds, source fingerprint, checkpoint hashes, family, seed,
method schema, and exact point IDs.  Mutating any field must reject resume.

- [ ] **Step 3: Implement aggregation and timing**

Write 288 rows per method, family/split/seed means, six paired near comparisons,
unsafe rates, PWE fractions, orthogonality maxima, and warm-up plus 100-query
latency.  The oracle row is marked `reference_only=true` and excluded from every
gate.  Write `P1_PILOT_GO` or `P1_PILOT_STOP` without reading frozen final.

- [ ] **Step 4: Package self-contained evidence**

Include P1 outputs, suite/cache and sidecars, actual P0/P5 evidence archives and
sidecars, source files, tests, requirements, environment, and an internal
manifest.  Re-open the tarball and verify every member size and SHA before
printing the status.

- [ ] **Step 5: Verify and commit**

```bash
uv run --python 3.12 --with-requirements requirements.txt python -m pytest -q
git add block_kyfan_pinn/p1_corrector.py scripts/run_p1_pilot.py \
  tests/test_p1_corrector.py tests/test_p1_protocol_integrity.py
git commit -m "feat: add frozen P1 pilot decision and evidence"
```

## Task 6: Local Smoke, AMD Preflight, and Pilot Execution

**Files:**
- Create: `docs/P1-RUNBOOK.zh-CN.md`
- Modify after measured result: `docs/CURRENT-STATUS.zh-CN.md`, `README.md`

- [ ] **Step 1: Run local engineering smoke**

```bash
uv run --python 3.12 --with-requirements requirements.txt python -m pytest -q
uv run --python 3.12 --with-requirements requirements.txt \
  python scripts/generate_p1_validation.py --suite-only
uv run --python 3.12 --with-requirements requirements.txt \
  python scripts/generate_p1_validation.py --device cpu --smoke-cache
uv run --python 3.12 --with-requirements requirements.txt \
  python scripts/run_p1_pilot.py --device mps --smoke-only --allow-dirty
```

Expected: tests pass, suite hash passes, tiny cache passes, and status is
`P1_ENGINEERING_SMOKE_PASS`.  This is not a scientific result.

- [ ] **Step 2: Run ModelScope AMD preflight**

Use image `ubuntu22.04-rocm7.2.3-py312-torch2.11.0-1.39.0`, clone the exact clean
commit, do not reinstall PyTorch, and run:

```bash
python scripts/preflight_accelerator.py --backend rocm
python -m pytest -q
```

Expected: HIP available, accelerator memory recorded, and all tests pass.

- [ ] **Step 3: Generate the formal reference cache**

```bash
python scripts/generate_p1_validation.py --device cpu --cache-only
shasum -a 256 -c data/p1_validation_v1_references.sha256
```

Expected: cutoff-24, rank-3, 33x33 cache and `OK`.

- [ ] **Step 4: Run the formal P1 pilot once**

```bash
python scripts/run_p1_pilot.py --device rocm
```

Expected: one explicit `P1_PILOT_GO` or `P1_PILOT_STOP`, never a theoretical
expectation.  Preserve all results and evidence regardless of STOP.

- [ ] **Step 5: Back up and update status**

Copy the evidence archive and sidecar back locally before stopping the instance.
Update status/README only with the actual gate, exact metrics, hashes, device,
and limitations.  Commit with:

```bash
git add docs/P1-RUNBOOK.zh-CN.md docs/CURRENT-STATUS.zh-CN.md README.md
git commit -m "docs: record measured P1 pilot decision"
```

## Task 7: Promotion Boundary

- [ ] **Step 1: If P1 STOP, stop scientific escalation**

Do not create a frozen-final command.  Use failure attribution to choose exactly
one next design: hard selection if blending fails, internal-base routing if cost
alone fails, or abandon risk gating if near/gap gates fail.

- [ ] **Step 2: If P1 GO, write the separate promotion executor**

Only after GO, freeze a two-family, at least five-seed AMD/CUDA promotion matrix,
full baselines, ablations, robustness, latency, three repeats, figures, and the
independent final gate.  The final evaluator remains closed until that promotion
also passes.

## Plan Self-Review

- Spec coverage: PDE, basis invariance, P0-only calibration, independent suite,
  fairness, PWE boundary, gate, timing, evidence, AMD, and final-test closure all
  map to an implementation task.
- Placeholder scan: no `TBD`, `TODO`, or unassigned implementation decision is
  present.
- Type consistency: public corrector APIs, suite IDs, archive digests, method
  names, thresholds, and result paths are identical across tasks.

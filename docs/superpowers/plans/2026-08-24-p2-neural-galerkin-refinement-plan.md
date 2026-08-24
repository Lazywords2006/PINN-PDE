# P2 Neural-Augmented Galerkin Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Falsify or promote a compact basis-invariant neural-plus-Fourier Rayleigh--Ritz refinement after the audited P1 routing STOP.

**Architecture:** Add one pure trial-space refinement module and one diagnostic probe that reuses audited long-anchor checkpoints and the already-open P1 validation evidence.  The probe compares three frozen Fourier dictionaries against long-anchor, anchor, and a same-size Fourier-only Galerkin control; it emits a strict GO/STOP without touching frozen final.

**Tech Stack:** Python 3.12, PyTorch 2.8 CUDA 12.8, existing Bloch Hamiltonian/autodiff, pytest, CSV/JSON/tar SHA evidence.

---

## Task 1: Trial Dictionary and Stable Augmentation

**Files:**
- Create `block_kyfan_pinn/p2_refinement.py`
- Create `tests/test_p2_refinement.py`

- [ ] Write failing tests for exact hex-shell counts, projection of duplicate
  modes, accepted-column tolerance, rank-two output, U(2) invariance of the
  neural initializer, and orthogonality below `1e-5`.
- [ ] Run the focused tests and confirm import failure.
- [ ] Implement `hex_shell_modes`, `outer_shell_modes`,
  `orthogonal_analytic_augmentation`, `neural_augmented_ritz`, and
  `fourier_only_ritz` using existing `_build_rom_basis`, `periodic_mgs`, and
  `galerkin_rank_basis`.
- [ ] Run focused and full tests.
- [ ] Commit `feat: add neural-augmented Galerkin refinement`.

## Task 2: Audited P1 Probe Loader

**Files:**
- Create `scripts/probe_p2_refinement.py`
- Create `tests/test_p2_protocol.py`

- [ ] Write failing tests that require the approved P1 evidence digest,
  `audit_pass=true`, exact 18 P5 checkpoint identities, cutoff-24 cache hash,
  deterministic diagnostic point selection, and no frozen-final path access.
- [ ] Implement verified evidence/cache/checkpoint loading by reusing P1/P5
  auditors and exact final checkpoints.
- [ ] Freeze the point-selection JSON and SHA sidecar before evaluation.
- [ ] Commit `feat: bind P2 probe to audited P1 evidence`.

## Task 3: Probe Evaluation and Gate

**Files:**
- Modify `scripts/probe_p2_refinement.py`
- Modify `tests/test_p2_protocol.py`

- [ ] Add synthetic GO/STOP fixtures for near, gap, both families, 5/6 paired
  wins, Fourier-only control, orthogonality, finite metrics, and latency.
- [ ] Evaluate anchor, long-anchor, Fourier-only, shell1, shell2-outer, and
  shell2-all on the frozen diagnostic subset.
- [ ] Measure 10 warmups and 100 repeats for long-anchor and primary P2.
- [ ] Write rows, summary, gate, environment, provenance, units, report, and a
  self-contained evidence tarball; reopen and audit it before status output.
- [ ] Run on RTX 5090 D.  Preserve either `P2_REFINEMENT_PROBE_GO` or
  `P2_REFINEMENT_PROBE_STOP`.

## Task 4: Conditional Escalation

- [ ] If probe GO, freeze a new disjoint P2 suite and a separate implementation
  plan before formal execution.
- [ ] If probe STOP for expressivity only, design one bounded local variational
  correction probe; do not silently change P2-A thresholds.
- [ ] If probe STOP for gap safety, numerical rank, or Fourier-only dominance,
  stop this direction and retain all evidence.

## Verification

Run before any GPU probe:

```bash
python -m pytest -q
python scripts/preflight_accelerator.py --backend cuda
git status --short --branch
```

Expected: all tests pass, CUDA preflight PASS, and a clean exact commit.

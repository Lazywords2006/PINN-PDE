# SCI-Q3 Supplement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run an auditable, disjoint 160-point comparison between fixed P2 full-shell and Wang–Xie/Dai journal-method adaptations.

**Architecture:** A deterministic generator freezes the suite and cutoff-24 cache. A staged runner trains two strong adaptations, loads the exact audited P2 long-anchor checkpoints, evaluates a shared identity matrix, computes clustered statistics and gates, then packages a self-contained evidence archive.

**Tech Stack:** Python 3.12, PyTorch 2.8, CUDA 12.8, RTX 5090 D, pytest, CSV/JSON/tar SHA-256 evidence.

---

### Task 1: Freeze protocol tests

**Files:**
- Create: `tests/test_q3_supplement_protocol.py`

- [ ] Write failing tests for deterministic 160-point generation, split/family counts, uniqueness, disjointness, method identity completeness, clustered gate GO/STOP, and the ban on final evaluation paths.
- [ ] Run `python -m pytest tests/test_q3_supplement_protocol.py -q` and verify failure because the new modules do not exist.

### Task 2: Implement deterministic suite and reference cache

**Files:**
- Create: `scripts/generate_q3_supplement.py`
- Create: `benchmarks/q3_supplement_v1.json`
- Create: `benchmarks/q3_supplement_v1.sha256`

- [ ] Implement `generate_q3_supplement_suite`, `validate_q3_disjointness`, and the frozen payload.
- [ ] Reuse cutoff-24 `build_reference_cache` so exact/near and external-gap semantics are checked.
- [ ] Run focused tests until green and regenerate the suite twice to confirm byte equality.

### Task 3: Implement staged training and evaluation

**Files:**
- Create: `scripts/run_q3_supplement.py`
- Modify: `tests/test_q3_supplement_protocol.py`

- [ ] Add synthetic failing tests for result identity matrices and gate thresholds.
- [ ] Implement `--smoke-only`, `--formal`, and `--audit-evidence` modes.
- [ ] Train 1500-step Wang–Xie and Dai adaptations for two families and three seeds.
- [ ] Load exact P5 long-anchor checkpoints and evaluate fixed P2 full-shell.
- [ ] Write `rows.csv`, `summary.json`, `gate.json`, `provenance.json`, environment and timing tables.

### Task 4: Evidence packaging and verification

**Files:**
- Modify: `scripts/run_q3_supplement.py`
- Modify: `tests/test_q3_supplement_protocol.py`

- [ ] Package suite/cache, baseline checkpoints, source, rows, summaries, gate, environment and manifest.
- [ ] Reopen the tarball, validate safe unique paths, bytes and SHA-256, and recompute the gate from rows.
- [ ] Run focused tests, full pytest, Ruff, and CUDA preflight.

### Task 5: Remote execution and shutdown

- [ ] Transfer the committed source snapshot to the RTX 5090 D machine and verify its archive SHA.
- [ ] Run smoke. If engineering checks pass, run formal once.
- [ ] Audit the evidence on the remote machine and download archive + sidecar + concise report locally.
- [ ] Verify the downloaded SHA and audit locally.
- [ ] Update the local status/HTML with actual GO or STOP values.
- [ ] Only after local verification, execute `shutdown -h now` and confirm SSH closes.

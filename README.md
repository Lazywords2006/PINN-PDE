# Basis-Invariant Neural Solver for 2D Bloch Spectral Clusters

This repository solves a genuine two-dimensional parametric Bloch–Schrödinger eigen-PDE with a
label-free neural network. The target is the lowest rank-two spectral projector, not two globally
ordered eigenfunctions at an internal band crossing.

Current scientific status: **`V3_SYMMETRY_PILOT_GO` + `V3_CONVERGENCE_GO`**. An external audit
found that the archived P2/Q3 shell convention was inconsistent with the positive-cross kinetic
metric. Those immutable results are retained as superseded historical evidence and must not be
submitted. The corrected D6 shell, paired-normalization derivative fix, Hermitian Ritz assembly,
strong Fourier controls, spectral-roughness routing, grid-65 references, and cutoff/grid convergence
audit now pass on a disjoint 24-point pilot. A procedurally frozen 160-point CUDA confirmation is
the remaining blocking experiment; no publication claim uses it until that run is complete.

## Method in one paragraph

A three-layer width-64 SiLU MLP receives periodic coordinates, a Bloch wavevector, and potential
parameters. An anchored generalized-trace objective trains it without plane-wave eigenfunction
labels to predict a rank-two neural coarse space. V3 first measures the potential energy outside the
first D6 Fourier shell. Spectrally simple cases use a tie-closed, minimum-rank-25 kinetic Fourier
space directly; spectrally rich cases use a rank-25 neural–Fourier trial space. The actual pure-space
rank can rise to27 when a kinetic-energy multiplet crosses the rank boundary. Fourier Hamiltonian
actions are analytic, neural actions use automatic differentiation, and a Hermitian compact Ritz
solve extracts the cluster. The method is a routed hybrid eigensolver, not a standard residual PINN.

## Superseded historical result

The table below is the **superseded V2 result** and is retained only for provenance. It does not
describe the current V3 method.

| Method | Overall projector error | Near crossing | Gap scan |
|---|---:|---:|---:|
| Long-anchor neural baseline | 0.14719 | 0.08924 | 0.15938 |
| Fourier-only rank 21 | 0.13697 | 0.12249 | 0.13700 |
| **Neural + complete shell 2** | **0.04532** | **0.03903** | **0.04389** |

Overall improvement over long-anchor is 69.19%, with a point-clustered 95% bootstrap interval of
[67.66%, 70.75%]. Evidence audit passed, and local recomputation reproduced all core values exactly.

The superseded Q3 supplement obtained overall errors of 0.04728 for P2, 0.13114 for a
Wang–Xie trace adaptation, and 0.43367 for a Dai neural-subspace Galerkin adaptation. P2 improves
over Wang–Xie by 63.78%, with a 95% point-clustered interval of [59.58%, 67.88%], and wins all six
family-by-seed comparisons. These are transparent Bloch adaptations, not official author-code runs.

## Start here

- [Current status](docs/CURRENT-STATUS.zh-CN.md)
- [V3 correction and confirmation protocol](docs/V3-SYMMETRY-CORRECTION-PROTOCOL.zh-CN.md)
- [V3 pilot evidence](paper/v3_pilot/README.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Reproduction and supplement runbook](docs/RUNBOOK.md)
- [Historical V2 data index — superseded](paper/p2_final/CORE_RESULTS.zh-CN.md)
- [Chinese manuscript draft](paper/p2_final/MANUSCRIPT.zh-CN.md)
- [English manuscript draft](paper/p2_final/MANUSCRIPT.en.md)
- [Detailed final experiment report](paper/p2_final/P2_FINAL_EXPERIMENT_REPORT.zh-CN.md)
- [SCI-Q3 supplement report](paper/p2_final/Q3_SUPPLEMENT_REPORT.zh-CN.md)
- [External-gap theory and cost analysis](paper/p2_final/THEORY_AND_COST.zh-CN.md)
- [Citation audit](paper/p2_final/CITATION_AUDIT.zh-CN.md)
- [Target journal and rationale](paper/submission_nmpde/JOURNAL_TARGET.zh-CN.md)
- The v0.3 DOCX/PDF package is superseded and must not be submitted. A new package will be built
  only after the V3 CUDA confirmation passes.

## Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -q
```

CUDA, RTX 5090, and ROCm setup helpers are in `scripts/setup_cuda.sh`,
`scripts/setup_rtx5090.sh`, and `scripts/setup_rocm.sh`.

## Repository map

```text
block_kyfan_pinn/   neural models, Bloch physics, reference solver, P2 refinement
benchmarks/         frozen suites and SHA-256 sidecars
scripts/            training, evaluation, audit, figure and supplement tools
tests/              unit and protocol-integrity tests
paper/p2_final/     core data, bilingual drafts, tables, theory and final report
paper/submission_nmpde/ editable submission files, journal note and checklist
figures/p2_final/   nine publication figures in PNG and SVG
docs/               current status, architecture, runbook and frozen protocol
results/            ignored/local evidence and returned remote results
```

## Non-negotiable research rules

- Never rerun, tune on, or select checkpoints using `benchmarks/v2_frozen_test.json`.
- Do not alter the final suite, reference cache, thresholds, or one-shot marker.
- Do not present smoke tests as paper results or formula-level baseline adaptations as official
  author-code reproductions.
- Do not claim Rayleigh–Ritz, Galerkin, Fourier bases, Ky Fan trace, or spectral projectors as new.
- Preserve P5, P1, and outer-shell STOP evidence.
- The completed `q3_supplement_v1` suite is evidence, not a new tuning set; do not rerun it after
  changing methods or gates.

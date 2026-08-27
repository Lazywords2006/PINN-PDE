# Basis-Invariant Neural Solver for 2D Bloch Spectral Clusters

This repository solves a genuine two-dimensional parametric Bloch–Schrödinger eigen-PDE with a
label-free neural network. The target is the lowest rank-two spectral projector, not two globally
ordered eigenfunctions at an internal band crossing.

Current scientific status: **`V3_FORMAL_PROMOTION_GO`**. An external audit
found that the archived P2/Q3 shell convention was inconsistent with the positive-cross kinetic
metric. Those immutable results are retained as superseded historical evidence and must not be
submitted. The corrected D6 shell, paired-normalization derivative fix, Hermitian Ritz assembly,
strong Fourier controls, spectral-roughness routing, grid-65 references, and cutoff/grid convergence
audit passed on a disjoint 24-point pilot. The 160-point CUDA confirmation has now been opened once
and completed: all formal and convergence gates pass, with 5,280 unique rows and a hash-bound
evidence archive. The suite is permanently closed. The paper claim is conditional neural
augmentation, because harmonic cases fall back to Fourier and all measured gain comes from the
spectrally rich Gaussian family.

## Method in one paragraph

A three-layer width-64 SiLU MLP receives periodic coordinates, a Bloch wavevector, and potential
parameters. An anchored generalized-trace objective trains it without plane-wave eigenfunction
labels to predict a rank-two neural coarse space. V3 first measures the potential energy outside the
first D6 Fourier shell. Spectrally simple cases use a tie-closed, minimum-rank-25 kinetic Fourier
space directly; spectrally rich cases use a rank-25 neural–Fourier trial space. The actual pure-space
rank can rise to27 when a kinetic-energy multiplet crosses the rank boundary. Fourier Hamiltonian
actions are analytic, neural actions use automatic differentiation, and a Hermitian compact Ritz
solve extracts the cluster. The method is a routed hybrid eigensolver, not a standard residual PINN.

## V3 formal result

| Method | Overall projector error | Eigenvalue MAE | A10 latency |
|---|---:|---:|---:|
| **SR-SC-NARR** | **0.030929** | **0.009837** | 176.64 ms |
| Kinetic Fourier ≥25 | 0.043425 | 0.015996 | 105.55 ms |
| Fixed neural–Fourier 25 | 0.031784 | 0.009890 | 134.81 ms |
| D6 shell 3, rank 37 | 0.030799 | 0.011275 | 220.37 ms |

The 28.76% aggregate improvement over Fourier-25 comes entirely from the Gaussian family; harmonic
cases route to Fourier and match the control. Relative to shell-3, SR-SC-NARR is a lower-rank,
lower-eigenvalue-error, lower-latency Pareto point with 0.42% higher mean projector error.

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
- [V3 formal evidence and results](paper/v3_formal/README.md)
- [English V3 manuscript](paper/v3_manuscript/MANUSCRIPT.en.md)
- [Chinese V3 manuscript](paper/v3_manuscript/MANUSCRIPT.zh-CN.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Reproduction and supplement runbook](docs/RUNBOOK.md)
- [Historical V2 data index — superseded](paper/p2_final/CORE_RESULTS.zh-CN.md)
- [Verified 66-paper literature matrix](paper/v3_formal/LITERATURE_MATRIX.md)
- [Verified BibTeX](paper/v3_formal/REFERENCES_VERIFIED.bib)
- [Bilingual DOCX/PDF package](paper/v3_submission/)
- [Target journal and rationale](paper/submission_nmpde/JOURNAL_TARGET.zh-CN.md)
- The old v0.3 P2 package is superseded. Only `paper/v3_submission/` may be used for the current draft.

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
paper/v3_formal/    formal rows, summaries, tables, literature matrix and evidence metadata
paper/v3_manuscript/ bilingual source manuscripts
paper/v3_submission/ visually verified bilingual DOCX/PDF files
figures/v3_formal/  publication figures in PNG and SVG
docs/               current status, architecture, runbook and frozen protocol
results/            ignored/local evidence and returned remote results
```

## Non-negotiable research rules

- Never rerun, tune on, or select checkpoints using `benchmarks/v2_frozen_test.json`.
- Do not alter or rerun the final suite, reference cache, thresholds, or one-shot marker.
- Do not present smoke tests as paper results or formula-level baseline adaptations as official
  author-code reproductions.
- Do not claim Rayleigh–Ritz, Galerkin, Fourier bases, Ky Fan trace, or spectral projectors as new.
- Preserve P5, P1, and outer-shell STOP evidence.
- The completed `q3_supplement_v1` suite is evidence, not a new tuning set; do not rerun it after
  changing methods or gates.

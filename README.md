# Basis-Invariant Neural Solver for 2D Bloch Spectral Clusters

This repository solves a genuine two-dimensional parametric Bloch–Schrödinger eigen-PDE with a
label-free neural network. The target is the lowest rank-two spectral projector, not two globally
ordered eigenfunctions at an internal band crossing.

Current scientific status: **`P2_FROZEN_FINAL_GO` + `Q3_SUPPLEMENT_GO`**. The one-shot final
evaluation is complete and permanently closed. A separate 160-point journal-baseline supplement
has also completed on an RTX 5090 D and passed its preregistered gate.

## Method in one paragraph

A three-layer width-64 SiLU MLP receives periodic coordinates, a Bloch wavevector, and potential
parameters. An anchored generalized-trace objective trains it without plane-wave eigenfunction
labels to predict a rank-two neural coarse space. At inference, the solver adds all 19 modes in the
complete second hexagonal Fourier shell, evaluates the Hamiltonian analytically on Fourier columns,
uses automatic differentiation only on the two neural columns, and solves a compact approximately
21-dimensional Rayleigh–Ritz problem. The method is a hybrid neural numerical eigensolver, not a
standard residual PINN and not a pure Fourier method.

## Frozen-final result

The final benchmark contains 640 parameter points, two honeycomb potential families, three
checkpoint seeds, ten methods, and 19,200 paired rows.

| Method | Overall projector error | Near crossing | Gap scan |
|---|---:|---:|---:|
| Long-anchor neural baseline | 0.14719 | 0.08924 | 0.15938 |
| Fourier-only rank 21 | 0.13697 | 0.12249 | 0.13700 |
| **Neural + complete shell 2** | **0.04532** | **0.03903** | **0.04389** |

Overall improvement over long-anchor is 69.19%, with a point-clustered 95% bootstrap interval of
[67.66%, 70.75%]. Evidence audit passed, and local recomputation reproduced all core values exactly.

The independent Q3 supplement obtains overall errors of 0.04728 for P2, 0.13114 for a
Wang–Xie trace adaptation, and 0.43367 for a Dai neural-subspace Galerkin adaptation. P2 improves
over Wang–Xie by 63.78%, with a 95% point-clustered interval of [59.58%, 67.88%], and wins all six
family-by-seed comparisons. These are transparent Bloch adaptations, not official author-code runs.

## Start here

- [Current status](docs/CURRENT-STATUS.zh-CN.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Reproduction and supplement runbook](docs/RUNBOOK.md)
- [Known publication gaps](docs/KNOWN_GAPS.zh-CN.md)
- [Core data index](paper/p2_final/CORE_RESULTS.zh-CN.md)
- [Chinese manuscript draft](paper/p2_final/MANUSCRIPT.zh-CN.md)
- [English manuscript draft](paper/p2_final/MANUSCRIPT.en.md)
- [Detailed final experiment report](paper/p2_final/P2_FINAL_EXPERIMENT_REPORT.zh-CN.md)
- [SCI-Q3 supplement report](paper/p2_final/Q3_SUPPLEMENT_REPORT.zh-CN.md)
- [Historical P5 negative-result audit](docs/P5-INDEPENDENT-AUDIT.zh-CN.md)

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
paper/p2_final/     core data, bilingual drafts, tables and final report
figures/p2_final/   eight publication figures in PNG and SVG
docs/               current status, architecture, runbook, gaps, retained audit
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

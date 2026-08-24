# P2 Full-Shell Independent Pilot Design

## Decision

The frozen `shell2_outer` probe returned STOP, but the preregistered
`shell2_all` diagnostic produced a strong, basis-invariant mechanism signal on
the selected difficult points: near error `0.08551` versus long-anchor
`0.19988`, gap error `0.05104` versus anchor `0.17821`, 6/6 near wins, and
Fourier-only error `0.64876`.  Its measured RTX 5090 D latency was about 104 ms.
These selected-point results are exploratory and cannot support a paper claim.

Freeze `shell2_all` as a new candidate and evaluate it once on an independent
96-point suite.  The completed outer-shell STOP remains unchanged.

## Methods

Evaluate harmonic and Gaussian honeycomb potentials, seeds 42/137/251, with:

1. audited `p5_anchor`;
2. audited `p5_long_anchor`;
3. audited `p5_static_low_rom`;
4. `p2_shell1` neural-augmented Ritz ablation;
5. `p2_shell2_all` primary, with two neural columns plus all 19 modes through
   shell two;
6. `fourier_only_rank21`, using 21 analytic modes and no neural columns.

All Hamiltonian images of Fourier modes are analytic.  Only the two neural
columns use automatic differentiation.  No reference projector enters any
method construction.

## Independent Suite

- id `block-kyfan-p2-validation-v1-20260824`;
- generation seed `2026082404`;
- 96 points: per family IID 8, exact 8, near 16, OOD 8, gap-scan 8;
- disjoint from V2 validation/final, P0 risk, P1 validation, and therefore every
  selected P2 probe point;
- cutoff-24, rank-3, 33x33 float64 PWE references;
- suite and cache SHA sidecars frozen before evaluation.

## Gate

`P2_FULL_SHELL_PILOT_GO` requires all:

- primary near error at least 5% below long-anchor;
- primary gap error no more than 2% above the best of anchor and long-anchor;
- both potential families improve on near and at least 5/6 family-seed pairs win;
- primary overall error at least 5% below long-anchor;
- primary overall error below the 21-mode Fourier-only control;
- maximum orthogonality error below `1e-4` and every metric finite;
- production mean latency below 150 ms and p95 below 200 ms on RTX 5090 D;
- production mean latency below 50% of a cutoff-24 direct PWE solve measured on
  the same server;
- 1728 rows, exact identities, clean commit, source/checkpoint/environment
  provenance, SHA-bound units, and evidence audit pass.

P2 GO authorizes a broader promotion matrix; P2 STOP stops full-shell escalation.
Neither result opens frozen final.

## Publication Boundary

The method is a neural-initialized hybrid eigensolver, not a pure one-forward
PINN and not a new Galerkin theorem.  A defensible claim requires accuracy-cost
Pareto results against direct PWE, same-rank Fourier-only Galerkin, long-anchor,
static ROM, and journal neural-subspace Galerkin work.  The independent pilot is
development evidence, not a final paper table.

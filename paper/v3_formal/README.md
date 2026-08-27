# V3 Formal Confirmation Results

Date: 2026-08-28

Status: **`V3_FORMAL_PROMOTION_GO`**

Method: **SR-SC-NARR**

Task: lowest rank-two spectral projector of a parameterized two-dimensional periodic
Bloch–Schrödinger eigenvalue PDE.

## Protocol

- one procedurally frozen CUDA confirmation;
- 160 physical parameter points, two honeycomb potential families, five splits;
- three archived checkpoint seeds and 11 methods/ablations;
- 5,280 unique evaluation rows;
- corrected D6 Fourier geometry and cutoff-24, float64, grid-65 PWE references;
- all method, routing, benchmark, bootstrap, and success thresholds frozen before opening;
- independent cutoff 20/24/28 and grid 65/97 convergence audit;
- NVIDIA A10 24GB, PyTorch 2.10.0+cu128, CUDA 12.8.

## Main results

Projector error, eigenvalue MAE, and latency are lower-is-better.

| Method | Overall | Near | Strict OOD | Gap scan | Eigenvalue MAE | p95 | CUDA latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| **SR-SC-NARR** | **0.030929** | **0.029007** | **0.035618** | **0.030391** | **0.009837** | **0.105683** | 176.64 ms |
| Kinetic Fourier, minimum rank 25 | 0.043425 | 0.041291 | 0.050231 | 0.043054 | 0.015996 | 0.146571 | 105.55 ms |
| Full D6 shell 3, rank 37 | 0.030799 | 0.028538 | 0.034598 | 0.030762 | 0.011275 | 0.110973 | 220.37 ms |
| Fourier shell 2, rank 19 | 0.073476 | 0.067746 | 0.083663 | 0.074778 | 0.023261 | 0.212103 | 61.24 ms |
| Long-anchor neural solver | 0.139905 | 0.089580 | 0.228525 | 0.183825 | 0.022595 | 0.325521 | 1.27 ms |
| Wang–Xie formula-level adaptation | 0.132717 | 0.088125 | 0.211824 | 0.182409 | 0.018248 | 0.304959 | 1.10 ms |
| Dai formula-level adaptation | 0.432885 | 0.422582 | 0.440783 | 0.471568 | 0.110026 | 0.654799 | 130.33 ms |

SR-SC-NARR reduces mean projector error relative to kinetic Fourier-25 by 28.76%; the
family-by-split stratified point bootstrap 95% interval is [28.08%, 29.44%]. It wins three of six
family-by-seed cells strictly and does not regress in any of the six. It is 0.42% less accurate in
mean projector error than rank-37 shell 3, but has 12.75% lower eigenvalue MAE and 19.84% lower
latency. This supports a Pareto claim, not an unconditional accuracy or speed dominance claim.

## Numerical integrity

- all 17 formal/convergence gate fields are `true`;
- 5,280/5,280 method–seed–point identities are present and unique;
- all required numerical fields are finite;
- maximum orthogonality error: `2.47e-7`;
- proposed-method maximum raw Hermiticity defect: `7.13e-6`;
- minimum sampled external gap: `0.01917`;
- SR-SC-NARR route counts: 240 Fourier and 240 hybrid;
- SR-SC-NARR trial ranks: 25, 26, and 27; shell-3 control rank: 37;
- peak allocated/reserved CUDA memory: 1.24/1.26 GB.

## Evidence

- source fingerprint:
  `27b8d487a8ff81a89d27d49856b3559e51188d0424a143ad7133d9d572f2dbbb`;
- suite SHA-256:
  `cf834352157fbe298bb511cb7ab8e325471473fde0a0f2824f2c31e35b4f7571`;
- reference SHA-256:
  `19ef0364cdb0b0407ef2fa3c6880268690ddaf7d46b82b43d50b0a6bce51b36e`;
- convergence audit SHA-256:
  `b2a104f7dde8e506b9446634af6d716c00c8317adb2d6fa5c8f1484e4cf0e0f2`;
- formal evidence archive SHA-256:
  `108a4b042549ead58f7b13f42b6ace4685e93a4e8a54e9563b044c03c29ad78c`.

The evidence archive, marker, raw CSV, summary, gate, provenance, and manifest are preserved. The
formal suite is permanently closed; no rerun or threshold change is permitted.

# V3 Pilot Evidence

Status: `V3_SYMMETRY_PILOT_GO`  
Role: engineering/mechanism evidence only; not the formal paper test.

## What was tested

- 24 previously unused parameter points;
- harmonic and Gaussian honeycomb potentials;
- IID, exact crossing, near crossing, strict OOD, and gap-scan splits;
- three archived checkpoint seeds: 42, 137, and 251;
- 11 methods and ablations on the same points;
- corrected D6 Fourier shells, tie-closed kinetic dictionaries, detached paired normalization,
  explicit Hermitian Ritz assembly, eigenvalue error, residual, latency, and raw Hermiticity defect.

## Main result

| Method | Projector error | Eigenvalue MAE | CPU latency |
|---|---:|---:|---:|
| **SR-SC-NARR** | **0.029784** | **0.008074** | 52.51 ms |
| Kinetic Fourier, minimum rank 25 | 0.041718 | 0.012762 | 29.56 ms |
| Full D6 shell 3, rank 37 | 0.029605 | 0.009185 | 61.76 ms |
| Long-anchor neural solver | 0.151579 | 0.020266 | 0.94 ms |
| Wang–Xie formula-level adaptation | 0.147858 | 0.017458 | 0.83 ms |
| Dai formula-level adaptation | 0.433862 | 0.100872 | 110.84 ms |

The stratified point bootstrap estimates a 28.50% improvement over the kinetic-Fourier control,
with a 95% interval of [25.94%, 30.32%]. The maximum proposed-method raw Hermiticity defect is
`2.63e-6`; maximum orthogonality error across the experiment is `2.56e-7`.

## Integrity

- source fingerprint:
  `27b8d487a8ff81a89d27d49856b3559e51188d0424a143ad7133d9d572f2dbbb`;
- pilot suite SHA-256:
  `ada77c55dec17a6b912b1b7347182a0f60135a1f3771ca9387e1bd5b8161ed7d`;
- reference cache SHA-256:
  `e586cdf8c9c72c90bc9a224b5c9e83b6e384a4991987dca09f238552feade4a1`;
- evidence bundle SHA-256:
  `e9f3047ebb0aaf8bd89202de95544d1b8b6a0a6b62fe8a2427ac80d78fffa5b4`.

`gate.json` deliberately records `pilot_go=true` and `promotion_go=false`. Only the future frozen
160-point CUDA confirmation may promote the method to a paper result.

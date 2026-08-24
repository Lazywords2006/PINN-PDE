# P2 Neural-Augmented Galerkin Refinement Design

## 1. Decision Trigger

The audited CUDA P1 pilot returned `P1_PILOT_STOP`.  Risk detection was strong
(`AUROC=0.86984`, parameter-only `0.74103`), overall error and unsafe regression
improved, orthogonality and latency passed, but the primary method was 4.02%
worse than long-anchor on near-cluster and 4.03% worse than the best anchor on
gap-scan.  Even the reference-only pointwise minimum of anchor and static-ROM
had near error `0.10423`, above long-anchor `0.10118`.  Therefore no router or
blend restricted to those two endpoint subspaces can meet the frozen P1 near
gate.  Threshold tuning is scientifically closed.

P2 tests a new mechanism: **basis-invariant neural-augmented Rayleigh--Ritz
refinement**.  A neural spectral-cluster prediction supplies a high-quality
rank-two coarse subspace.  A small analytic Fourier dictionary augments the
trial space, and a physics-based Ritz solve extracts the lowest rank-two
subspace without reference labels or per-instance gradient training.

## 2. PDE and Neural Component

The PDE remains the two-dimensional periodic Bloch--Schrodinger eigenproblem

\[
\left[\tfrac12(-i\nabla+k)^T G(-i\nabla+k)+V_\mu(x)\right]u_j=E_j u_j,
\qquad x\in[0,2\pi)^2.
\]

The neural initializer is the audited `p5_long_anchor` rank-two predictor.  P2
does not retrain it during the mechanism probe.  The output target remains the
rank-two spectral projector, so exact internal degeneracy and basis rotations
are allowed.

## 3. Candidate Methods

### A. Neural-Augmented Rayleigh--Ritz (selected first)

For neural basis `Q_theta(mu)` and analytic plane waves `Phi_S`, form

\[
W=[Q_\theta,\Phi_S].
\]

Remove components already represented by `Q_theta`, reject numerically dependent
columns, orthonormalize the remaining complex trial basis under cell-average
quadrature, assemble `W^* H_mu W`, and select its two lowest Ritz vectors.  The
operation depends only on the PDE, neural prediction, and fixed dictionary.

Probe dictionaries:

- `shell1`: the seven first-shell hexagonal modes;
- `shell2_outer`: only the twelve modes on the second hexagonal shell;
- `shell2_all`: all nineteen modes through shell two.

`shell2_outer` is the primary probe because it avoids duplicating the free-
electron anchor modes while adding missing high-frequency directions.

### B. Risk-triggered test-time variational Fourier correction (deferred)

Freeze long-anchor, initialize a point-specific tangent Fourier correction at
zero, and optimize only 28--76 correction coefficients with generalized-trace
physics loss for a small number of steps.  This is more expensive and easier to
overfit collocation points.  It is attempted only once if candidate A fails for
expressivity rather than numerical instability.

### C. More routing or larger static ROM (rejected)

P1 and P5 already falsified these mechanisms.  The endpoint oracle and long-
anchor control show that more threshold tuning or another amortized low-ROM
branch cannot answer the failure.

## 4. Basis-Invariance and Numerical Safety

P2 never assigns labels to individual eigenfunctions.  All operations act on
trial spaces and Ritz projectors.  Analytic modes are projected against the
neural subspace, then accepted only if their post-projection norm exceeds a
frozen tolerance `1e-5`.  The resulting basis must satisfy maximum
orthogonality error below `1e-4`.

The primary implementation uses complex modified Gram--Schmidt on accepted
columns.  Any rank deficiency, non-finite Hamiltonian, insufficient accepted
rank, or complex eigensolver failure is an engineering STOP, not a silent
fallback to reference PWE.

For efficiency, automatic differentiation applies the Hamiltonian only to the
two neural columns.  Plane-wave Hamiltonians are assembled analytically, and
the same detached orthogonalization transform is applied to both each trial
column and its Hamiltonian image.  Unit tests require this fast assembly to
match the direct per-column autodiff Rayleigh--Ritz projector.  The abandoned
naive implementation is retained as a negative efficiency result.

## 5. Development Probe

The first probe may reuse P1 validation points because P1 has already exposed
them and they are used only for mechanism selection, never for a P2 final claim.
Select, per potential family:

- two worst long-anchor near-cluster points;
- two representative gap-scan points where anchor beats long-anchor.

Evaluate seeds 42, 137, and 251 for long-anchor, anchor, pure Fourier Galerkin
with the same dictionary, and the three neural-augmented dictionaries.

The probe is GO only if `shell2_outer` satisfies all:

- mean near projector error at least 2% below long-anchor;
- gap-scan error no more than 2% above anchor;
- both potential families improve on near-cluster;
- at least 5 of 6 family-seed near comparisons improve;
- neural-augmented error is below the same-size pure Fourier Galerkin control;
- maximum orthogonality error below `1e-4`;
- no NaN/Inf and no reference quantity used in construction;
- latency below 5x long-anchor on the probe.

If the probe fails, no independent P2 suite or large matrix is run.  Failure
attributable to missing local flexibility authorizes candidate B once; a
numerical or physics non-regression failure stops P2 entirely.

## 6. Independent P2 Pilot Boundary

Only after probe GO, generate a new 96-point suite with seed `2026082404`,
disjoint from V2 validation/final, P0, P1, and all probe identities.  Freeze
cutoff-24 rank-3 references, two families, seeds 42/137/251, method list,
latency budget, and SHA-bound evidence before reading its projector errors.

P2 pilot GO requires:

- near error at least 5% below long-anchor;
- gap-scan at most 2% above the best non-reference neural baseline;
- both families improve and at least 5/6 family-seed pairs win;
- overall error at least 5% below long-anchor;
- same-size pure Fourier Galerkin is worse than neural-augmented P2;
- orthogonality, finite metrics, provenance, latency, and evidence audit pass.

P2 pilot GO still does not open frozen final.  It authorizes a promotion matrix
with traditional PWE timing, standard PINN/eigen-PINN baselines, Dai-style
neural-subspace Galerkin, ablations, confidence intervals, and figures.

## 7. Novelty Boundary

Rayleigh--Ritz, Fourier bases, Galerkin projection, and neural subspace methods
are prior art.  P2 must not claim them as inventions.  The defensible combined
contribution is restricted to:

- parameterized Bloch PDE spectral clusters with exact internal crossings;
- a basis-invariant neural coarse subspace;
- a compact analytic augmentation designed around the crossing modes;
- explicit same-dictionary Fourier-only controls;
- consumer-GPU reproducibility and strict near/gap safety gates.

The closest journal comparison remains neural-subspace-plus-Galerkin work such
as Dai et al.; P2 is publishable only if the parameterized crossing setting,
same-size controls, accuracy/cost results, and basis-invariant analysis create a
clear difference.

## 8. Scope Exclusions

The P2 probe does not tune on frozen final, change P1 results, train from PWE
labels, hide direct PWE cost, claim a new neural network, or produce paper
results.  Every negative result is retained.

# Spectral-Complexity-Gated Neural Augmentation for Parametric Bloch Spectral Clusters with Band Crossings

> Manuscript draft v1.0, 28 August 2026. Numerical statements in this draft are generated only
> from the frozen V3 formal evidence. Author names, affiliations, ORCID identifiers, funding,
> CRediT roles, and the target journal style remain for the authors to supply.

## Abstract

Repeated solution of parameterized partial-differential eigenproblems is expensive, while internal
eigenvalue crossings make individually ordered eigenfunctions an unstable learning target. We
consider the lowest rank-two spectral projector of a two-dimensional periodic
Bloch–Schrödinger operator with harmonic and localized Gaussian honeycomb potentials. We propose
SR-SC-NARR, a spectral-roughness-routed, symmetry-consistent neural-augmented Rayleigh–Ritz
solver. A lightweight SiLU network is trained without plane-wave labels by a generalized-trace
variational objective and supplies two parameter-dependent complex trial directions. At inference,
a potential-only Fourier tail-energy diagnostic chooses between a tie-closed kinetic Fourier space
and a symmetry-consistent neural–Fourier space. The reciprocal dictionaries obey the D6 closure
associated with the implemented positive-cross kinetic metric; Fourier Hamiltonian actions are
analytic, neural actions use automatic differentiation, paired orthogonalization preserves
Hamiltonian consistency, and the reduced matrix is explicitly Hermitian.

The method is evaluated once on a procedurally frozen CUDA confirmation set containing 160
physical parameter points, two potential families, five parameter regimes, three archived network
seeds, 11 methods and ablations, and 5,280 paired evaluations. SR-SC-NARR attains a mean rank-two
projector sine error of 0.03093, a p95 of 0.10568, and a two-eigenvalue mean absolute error of
0.00984. Relative to a tie-closed kinetic Fourier control of minimum rank 25, mean projector error
decreases by 28.76%; a family-by-split stratified point bootstrap gives a conditional 95% interval
of [28.08%, 29.44%]. The gain is deliberately reported as conditional: all harmonic cases select
the Fourier branch and match the control, whereas all Gaussian cases select the hybrid branch and
reduce error by 31.75%. Relative to a complete rank-37 D6 shell, the proposed solver has 0.42%
higher projector error but 12.75% lower eigenvalue error, 19.84% lower latency, and trial rank
25–27. These results support a conditional neural-augmentation and Pareto claim, not universal
neural superiority or routing generalization between the two observed spectral endpoints.

**Keywords:** neural PDE eigensolver; Bloch–Schrödinger equation; spectral projector; eigenvalue
crossing; Rayleigh–Ritz; Fourier spectral method; scientific machine learning

## 1. Introduction

Neural PDE solvers aim to amortize repeated differential-equation solves by learning a function or
operator family rather than solving each parameter instance from scratch. Variational neural
solvers such as Deep Ritz [16] and neural operators [17] provide complementary examples of this
shift from a single discretized solution to a learned function-space approximation. Physics-informed neural
networks (PINNs) introduced a widely used residual-based realization of this idea [1], and
conditional PINNs extended it to parameterized classes of problems [2]. Differential
eigenproblems are harder than ordinary initial-boundary-value problems: the eigenvalues are
unknown, the homogeneous residual admits the zero function, multiple states require normalization
and orthogonality, and eigenvectors cease to be unique at multiplicities.

The last issue is central for Bloch band structures. Two-dimensional honeycomb operators may
possess conical Dirac crossings at Brillouin-zone vertices [11]. Around an internal crossing, a
globally ordered “band 1 eigenfunction” and “band 2 eigenfunction” may swap or rotate. Penalizing
the difference between individually labeled eigenvectors then confuses a basis convention with a
physical error. If the two-dimensional low-energy cluster remains separated from the third state,
however, its spectral projector is still well-defined. Parameter-dependent eigenspace theory
therefore motivates learning the cluster rather than its individual columns [7,15].

Several neighboring works supply important ingredients. Trace and Ky Fan objectives enable joint
computation of multiple eigenpairs [3]. Rayleigh-quotient neural eigensolvers can combine energy
minimization and Gram–Schmidt orthogonalization [4]. Neural trial subspaces can be followed by a
Galerkin solve [5]. Shape Space Spectra treats multiplicity through dynamic mode reordering [6],
and supervised Grassmann regression learns parameter-to-subspace maps [8]. Classical reduced-basis
methods address repeated band-structure and multiple-eigenspace calculations [9,10,12]. These
works establish that trace minimization, neural subspaces, Fourier bases, and Rayleigh–Ritz are
not individually new.

The open practical question addressed here is narrower. A label-free neural coarse space may help
when a compact analytic Fourier dictionary under-resolves a spectrally rich potential, but neural
automatic differentiation is unnecessary when a small Fourier space is already adequate. We ask:

1. Can a basis-invariant neural coarse space improve a symmetry-consistent low-rank Fourier Ritz
   solver at internal Bloch crossings?
2. Can a diagnostic computed only from the potential decide when to invoke neural augmentation
   without reading reference projectors or test errors?
3. Does the resulting solver remain competitive with a stronger, higher-rank Fourier control under
   a one-shot, hash-bound evaluation protocol?

The contributions are:

1. **Crossing-aware PDE target.** Training and evaluation target the lowest rank-two subspace and
   projector, making the formulation invariant to phases, permutations, and internal unitary
   rotations.
2. **Symmetry-consistent trial spaces.** Reciprocal dictionaries use the D6 closure consistent with
   the kinetic quadratic form (m_1^2+m_2^2+m_1m_2). Kinetic-energy boundary ties are retained,
   preventing arbitrary truncation of degenerate multiplets.
3. **Label-free conditional neural augmentation.** A potential Fourier tail-energy ratio routes
   each query to a pure Fourier or neural–Fourier trial space. The diagnostic uses no eigensolution
   labels.
4. **Operator-consistent compact solve.** Analytic Fourier Hamiltonian actions, automatic
   differentiation of only two neural directions, detached cell-quadrature normalization, paired
   transformations of ((W,HW)), and an explicitly Hermitian Ritz matrix produce the final cluster.
5. **Audited evidence.** A disjoint pilot, an independent cutoff/grid convergence audit, and a
   single procedurally frozen 160-point CUDA confirmation preserve suite, reference, checkpoint,
   source, row, and evidence hashes.

The main empirical conclusion is intentionally conditional. The formal set contains two separated
spectral-complexity endpoints: the harmonic family always routes to Fourier and the Gaussian family
always routes to the hybrid. The experiment validates safe endpoint selection and a stable neural
gain on the rich endpoint; it does not establish interpolation around the threshold or universal
routing across unseen potential families.

## 2. Related Work

### 2.1 Neural PDE and eigenvalue solvers

Standard PINNs minimize differential residuals, boundary conditions, initial conditions, and
optional observations [1]. Eigenvalue versions must additionally avoid trivial solutions and
represent normalization, orthogonality, and eigenvalue order. Jin et al. used physics-informed
networks to discover multiple quantum eigenstates without supervised wavefunction labels [14].
Kovacs et al. showed that a conditional physics-informed network can represent a parameterized
class of eigenproblems [2]. These methods establish label-free neural eigenanalysis but do not by
themselves remove the discontinuity of individually ordered states at an internal crossing.

Wang and Xie compute several eigenpairs jointly with tensor neural networks and a trace objective
[3]. Rowan et al. combine Rayleigh quotients and Gram–Schmidt for engineering eigenproblems [4].
Their principles motivate our generalized-trace initializer and orthogonality treatment. Our
primary claim is not superiority to the original implementations: the formal Wang–Xie result in
this study is a transparent formula-level Bloch adaptation, not an official author-code
reproduction.

### 2.2 Neural trial spaces and parameterized eigenspaces

Dai, Fan, and Sheng construct neural trial functions and solve a Galerkin eigenproblem inside the
learned subspace [5]. This is the closest journal-level structural neighbor to our hybrid compact
solve. The present method differs through a single parameter-conditioned coarse network, an
internally crossing Bloch projector target, an analytic D6 Fourier dictionary, a potential-only
route, and paired Hamiltonian assembly. The Dai-style adaptation used here converges poorly and is
reported for transparency; it is not the central evidence for the proposed method.

Chang et al. learn spectra over parameterized shape families and dynamically reorder modes at
multiplicities [6]. Fanaskov et al. directly regress parameterized subspaces on a Grassmannian but
use precomputed subspace labels [8]. We instead train from the operator and evaluate the projector.
Grubišić et al. analyze parameter-dependent eigenspaces under external isolation [7], supporting
the use of a cluster target even when the internal gap closes. Recent subspace-approximation theory
provides an additional numerical-analysis perspective [18], while Dölz and Ebert treat uncertainty
in eigenspaces of higher multiplicity [21]. Deep Eigenspace Network is a particularly close recent
preprint because it learns parameter-to-eigenspace maps and uses Ritz postprocessing, but it relies
on precomputed supervision and studies a different non-self-adjoint setting [22].

### 2.3 Bloch model reduction and periodic quantum networks

Reduced bases have long been used for repeated band-structure calculations [9]. Horger et al.
develop simultaneous reduced-basis approximation for parameterized multiple eigenvalues [10].
Haasdonk et al. combine full-order, reduced-order, and machine-learning components with
certification [12], illustrating why a hybrid solver should be assessed through accuracy, cost,
and reliability rather than neural forward time alone. Hsu et al. demonstrated equation-driven
neural band-structure learning in two-dimensional periodic quantum systems [13]. Fefferman and
Weinstein provide the mathematical setting for honeycomb potentials and Dirac points [11].
Data-driven reduced-order modeling has also been applied directly to parameterized PDE eigenvalue
problems [20], and neural networks have accelerated classical iterations for nonlinear
Schrödinger eigenproblems [19]. These works reinforce the need to state exactly which part of a
hybrid online solve is learned and which part remains numerical.

The novelty boundary is consequently specific: we claim a corrected, basis-invariant,
spectral-complexity-gated combination and its controlled evidence. We do not claim the invention of
Ky Fan principles, projectors, Fourier spectral discretization, Gram–Schmidt, Galerkin projection,
or Rayleigh–Ritz.

## 3. Problem Formulation

### 3.1 Two-dimensional Bloch eigenproblem

Let the periodic cell be $\Omega=[0,2\pi)^2$. For Bloch wavevector
$\mathbf k=(k_1,k_2)$ and potential parameters $\mu$, consider

\[
\mathcal H_{\mathbf k,\mu}u_j=
\left[\frac12(-i\nabla+\mathbf k)^T
G(-i\nabla+\mathbf k)+V_\mu(\mathbf x)\right]u_j
=E_j u_j,
\qquad
G=\begin{bmatrix}1&1/2\\1/2&1\end{bmatrix},
\]

with periodic function and first-derivative boundary conditions. A reciprocal mode
$\mathbf m=(m_1,m_2)\in\mathbb Z^2$ has kinetic energy

\[
T(\mathbf m,\mathbf k)=\frac12\left[(m_1+k_1)^2+(m_2+k_2)^2
+(m_1+k_1)(m_2+k_2)\right].
\]

The harmonic honeycomb family is

\[
V_{a,\delta}^{\mathrm H}(x,y)=
a[\cos x+\cos y+\cos(x-y)]
+\delta[\sin x-\sin y-\sin(x-y)].
\]

The training ranges are $a\in[0.20,0.80]$,
$\delta\in[-0.08,0.08]$, and $k_1,k_2\in[0.28,0.38]$.

The localized family consists of two periodically repeated Gaussian sublattices. With centers
$c_1=(0,0)$, $c_2=(2\pi/3,4\pi/3)$, weights
$w_1=1$, $w_2=1+\delta$, and periodic images $n\in\{-1,0,1\}^2$,

\[
V_{a,\sigma,\delta}^{\mathrm G}(x)
=-a\sum_{\ell=1}^2 w_\ell
\sum_n
\exp\!\left[-\frac{2}{3\sigma^2}
\left(d_1^2+d_2^2-d_1d_2\right)\right],
\quad d=x-c_\ell-2\pi n.
\]

Its training ranges are $a\in[1,4]$, $\sigma\in[0.18,0.35]$,
$\delta\in[-0.08,0.08]$, with the same Bloch box. Strict-OOD evaluation extends the Bloch
coordinates to $k_1\in[0.20,0.28]$, $k_2\in[0.38,0.45]$ and widens the potential ranges.

### 3.2 Spectral-cluster target

Let $U_2(\mathbf k,\mu)$ denote the span of the two lowest eigenstates and let
$P_2$ be its orthogonal projector. The internal gap $E_2-E_1$ may vanish. We require external
isolation from the unwanted spectrum through $E_3-E_2>0$. If $Q$ and $Q_\star$ are
orthonormal predicted and reference bases, the primary metric is

\[
e_{\mathrm{proj}}(Q,Q_\star)=
\sqrt{\frac{2-\lVert Q^*Q_\star\rVert_F^2}{2}}.
\]

It is the root-mean-square sine of the two principal angles and is invariant to all unitary changes
of basis inside either rank-two space. We also report the mean absolute error of the lowest two Ritz
eigenvalues, residual RMS, p95 and maximum projector error, orthogonality, raw Ritz Hermiticity
defect, trial rank, latency, and peak memory.

## 4. SR-SC-NARR

### 4.1 Label-free neural coarse space

Separate family-specific networks receive periodic features

\[
[\sin x,\cos x,\sin y,\cos y,\mathbf k,\mu]
\]

and output real and imaginary parts of two complex periodic functions. The MLP has three hidden
layers of width 64 with SiLU activations. A fixed low-energy anchor near the K point is added with
scale 0.1. For raw columns $Z_\theta$, define

\[
B_\theta=Z_\theta^*Z_\theta,\qquad
A_\theta=Z_\theta^*\mathcal H Z_\theta.
\]

The training loss is the regularized generalized trace

\[
\mathcal L_{\mathrm{trace}}
=\operatorname{Tr}\!\left[(B_\theta+10^{-6}I)^{-1}A_\theta\right].
\]

No PWE eigenvector, projector, or ordered band label enters training. Adam uses learning rate
(10^{-3}), four parameter instances and 256 shifted periodic points per step, for 665 steps.
Three archived checkpoints use seeds 42, 137, and 251. At evaluation, complex modified
Gram–Schmidt retracts the raw output to a rank-two neural basis $Q_\theta$.

### 4.2 D6-consistent Fourier spaces and tie closure

For the positive-cross kinetic metric, the complete D6 shell of radius $s$ is

\[
\mathcal S_s=\{(m_1,m_2)\in\mathbb Z^2:
\max(|m_1|,|m_2|,|m_1+m_2|)\le s\}.
\]

It contains 7, 19, and 37 modes for (s=1,2,3). The plus sign is essential: it is the shell
closure compatible with $m_1^2+m_2^2+m_1m_2$.

For a nominal kinetic rank $r$, modes from $\mathcal S_4$ are sorted by
$T(m,k)$. If the boundary energy is $T_r$, every mode satisfying

\[
T(m,k)\le T_r+10^{-7}\max(1,|T_r|)
\]

is retained. This tie closure avoids cutting an exact kinetic multiplet. The nominal rank-25
dictionary therefore has actual rank 25 or 27 on the formal set.

### 4.3 Potential-only spectral routing

On the 65 by 65 periodic grid, let $\widehat V_m$ be the discrete Fourier coefficients of the
potential. The routing statistic is

\[
\rho(V)=
\frac{\sum_{m\notin\mathcal S_1}|\widehat V_m|^2}
{\sum_m|\widehat V_m|^2}.
\]

The threshold is frozen at 0.1. If $\rho\le0.1$, the solver uses the tie-closed minimum-rank-25
kinetic Fourier dictionary. If $\rho>0.1$, it forms a hybrid dictionary from
$\mathcal S_2\cup\mathcal K_{21}(k)$ and appends the two neural directions. Redundant Fourier
columns are rejected during orthogonalization, yielding formal trial ranks 25–27. The route reads
only the input potential; it does not evaluate either candidate against a reference solution.

### 4.4 Analytic and automatic-differentiation Hamiltonian actions

For a plane wave $\phi_m(x)=e^{im\cdot x}$,

\[
\mathcal H\phi_m=[T(m,k)+V_\mu(x)]\phi_m,
\]

so the Fourier Hamiltonian columns are analytic. Automatic differentiation is used only for the two
neural columns. During modified Gram–Schmidt, the equal-weight cell-quadrature projection
coefficients and normalization are treated as constants with respect to spatial coordinates. Every
linear operation applied to a trial column $w$ is simultaneously applied to its Hamiltonian
column $Hw$. This paired construction preserves $H(cw)=cHw$ numerically and avoids nonlocal
cross-grid derivative terms.

Let the accepted paired columns be ((W,HW)). The reduced matrix is explicitly Hermitianized,

\[
A_W=\frac12[W^*(HW)+(W^*(HW))^*].
\]

Its two lowest eigenvectors are mapped back through $W$ and retracted to obtain the final basis.

### 4.5 Algorithm

```text
Input: (k, μ), family-specific archived network, grid X
1. Evaluate Vμ(X) and the tail ratio ρ(Vμ).
2. If ρ ≤ 0.1:
      construct tie-closed kinetic Fourier dictionary K25(k);
      assemble (W, HW) analytically.
   Else:
      evaluate and orthonormalize the two neural directions Qθ;
      construct S2 ∪ K21(k);
      append analytic Fourier pairs to (Qθ, HQθ).
3. Apply paired modified Gram–Schmidt with detached cell-quadrature scalars.
4. Form the explicitly Hermitian compact Ritz matrix.
5. Return its lowest rank-two Ritz subspace and Ritz eigenvalues.
```

The online cost is $O(Nr^2+r^3)$ after the column actions, where $N=65^2$ and
$r\in[25,27]$. Neural second derivatives are paid only on the hybrid route. The formal timing also
includes the current FFT-based routing diagnostic.

## 5. Experimental Protocol

### 5.1 Separation of development and confirmation

An external audit found that a superseded V2 implementation combined the positive-cross kinetic
metric with a negative-cross reciprocal-shell convention. V3 corrected the D6 closure, detached
paired normalization, explicitly Hermitianized the reduced matrix, replaced an asymmetric
rank-21 Fourier control by tie-closed kinetic controls, and created a new disjoint evaluation. Old
V2/Q3 numbers are retained only as historical provenance and are not combined with the results in
this paper.

A 24-point V3 engineering pilot was used to finalize code, route, controls, and gates. The code and
pilot were committed before the formal suite was generated. The 160-point suite, reference cache,
physical-point digest, source fingerprint, and convergence evidence were then committed separately.
The formal set was opened once in a clean CUDA checkout. A global marker prevents a second formal
opening.

### 5.2 Confirmation set

Each potential family contributes 80 points: 16 IID-hidden, 16 exact-cluster, 24 near-cluster,
16 strict-OOD, and 8 gap-scan points. Exact points have internal gap below $10^{-3}$, near points
below $2\times10^{-2}$, and every point has external gap above $10^{-2}$. Three checkpoint seeds
and 11 methods are evaluated at every point, producing
$160\times3\times11=5{,}280$ unique rows.

References use a float64 D6 plane-wave expansion with cutoff 24 and rank 3, evaluated on a
65 by 65 grid. An independent audit compares cutoffs 20, 24, and 28 and directly resamples solver
projectors between grid sizes 65 and 97.

### 5.3 Comparisons and ablations

The matrix contains:

- the archived long-anchor neural solver;
- neural augmentation with D6 shell 1 and shell 2;
- fixed neural–Fourier rank-about-25 and routed SR-SC-NARR;
- D6 shell-2 rank 19;
- tie-closed kinetic Fourier controls of nominal rank 21 and 25;
- complete D6 shell-3 rank 37;
- formula-level Bloch adaptations of Wang–Xie trace [3] and Dai Galerkin [5].

The strongest evidence for the neural claim is the comparison with kinetic Fourier-25, fixed
hybrid, and shell-3. The two literature adaptations provide context but are not official
reproductions.

### 5.4 Statistical and hardware protocol

The primary interval is a 2,000-sample bootstrap stratified over the ten family-by-split cells.
Within each point, errors are first averaged over the three archived seeds; physical points are then
resampled with replacement inside each stratum. The resulting interval is conditional on those
three checkpoints and does not estimate uncertainty over arbitrary retraining seeds.

Formal evaluation used one NVIDIA A10 with 23.82 GB reported memory, PyTorch 2.10.0+cu128, CUDA
12.8, and driver 550.54.15. Method order was deterministically rotated by point and seed to reduce
timing-order bias. Peak allocated and reserved memory were 1.24 and 1.26 GB.

The protocol follows recent calls for broad PDE benchmarks [23], strong classical baselines and
honest runtime claims [24], and explicit protection against test leakage in machine-learning-based
science [25].

## 6. Results

### 6.1 Overall and split performance

**Table 1. Formal projector and eigenvalue results.** Lower is better.

| Method | Overall | Near | Strict OOD | Gap scan | Eigenvalue MAE | p95 | Latency (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| **SR-SC-NARR** | **0.030929** | **0.029007** | **0.035618** | **0.030391** | **0.009837** | **0.105683** | 176.64 |
| Kinetic Fourier ≥25 | 0.043425 | 0.041291 | 0.050231 | 0.043054 | 0.015996 | 0.146571 | 105.55 |
| D6 shell 3, rank 37 | 0.030799 | 0.028538 | 0.034598 | 0.030762 | 0.011275 | 0.110973 | 220.37 |
| Fixed neural–Fourier 25 | 0.031784 | — | — | — | 0.009890 | 0.105683 | 134.81 |
| D6 shell 2, rank 19 | 0.073476 | 0.067746 | 0.083663 | 0.074778 | 0.023261 | 0.212103 | 61.24 |
| Long-anchor neural | 0.139905 | 0.089580 | 0.228525 | 0.183825 | 0.022595 | 0.325521 | 1.27 |
| Wang–Xie adapted | 0.132717 | 0.088125 | 0.211824 | 0.182409 | 0.018248 | 0.304959 | 1.10 |
| Dai adapted | 0.432885 | 0.422582 | 0.440783 | 0.471568 | 0.110026 | 0.654799 | 130.33 |

SR-SC-NARR lowers mean projector error relative to kinetic Fourier-25 by 28.76%. The stratified
point-bootstrap interval is [28.08%, 29.44%]. All five splits are non-regressive relative to the
control. The proposed p95 and maximum are 0.10568 and 0.16686.

![Figure 1. Overall formal projector error for 11 methods and ablations.](../../figures/v3_formal/fig01_overall_error.png)

![Figure 2. Error across IID, exact, near, strict-OOD, and gap-scan regimes.](../../figures/v3_formal/fig02_split_comparison.png)

### 6.2 The gain is conditional on potential spectral complexity

**Table 2. Family-specific mean results.**

| Family | Method | Projector error | Eigenvalue MAE | Latency (ms) |
|---|---|---:|---:|---:|
| Harmonic | SR-SC-NARR | 0.008120 | 0.000345 | 159.76 |
| Harmonic | Kinetic Fourier ≥25 | 0.008120 | 0.000345 | 104.72 |
| Harmonic | D6 shell 3 | 0.003370 | 0.000080 | 220.46 |
| Harmonic | Fixed hybrid | 0.009831 | 0.000451 | 132.42 |
| Gaussian | SR-SC-NARR | 0.053737 | 0.019329 | 193.53 |
| Gaussian | Kinetic Fourier ≥25 | 0.078729 | 0.031646 | 106.39 |
| Gaussian | D6 shell 3 | 0.058228 | 0.022470 | 220.27 |
| Gaussian | Fixed hybrid | 0.053737 | 0.019329 | 137.20 |

All 80 harmonic points have $\rho\ll0.1$, take the Fourier route, and exactly match the kinetic
Fourier control. All 80 Gaussian points have $\rho\in[0.807,0.964]$, take the hybrid route, and
reduce error by 31.75%. The Gaussian improvements for seeds 42, 137, and 251 are 30.5%, 32.6%, and
32.1%. Thus three of six family-by-seed cells are strict wins and all six are non-regressions.

![Figure 3. Family-specific formal results; the aggregate gain comes from the spectrally rich Gaussian endpoint.](../../figures/v3_formal/fig11_family_specific_results.png)

![Figure 4. The formal set contains two separated tail-ratio endpoints and no samples near the frozen 0.1 threshold.](../../figures/v3_formal/fig07_route_tail_ratio.png)

### 6.3 Routing ablation and cost

Pure kinetic Fourier-25 attains 0.04342 at 105.55 ms. Always using the hybrid improves error to
0.03178 but costs 134.81 ms. Routing improves aggregate error by a further 2.69% to 0.03093 because
it avoids the inferior hybrid on harmonic cases, but current tail-ratio computation increases
latency to 176.64 ms. The router is therefore a non-regressive conditional selector, not a speedup
in the present implementation.

![Figure 5. Routing ablation: conditional selection improves aggregate accuracy but adds online diagnostic cost.](../../figures/v3_formal/fig10_routing_ablation.png)

### 6.4 Higher-rank Fourier context

Complete D6 shell-3 has slightly lower projector error than SR-SC-NARR: 0.030799 versus 0.030929,
a 0.42% difference. The proposed method nevertheless has 12.75% lower eigenvalue MAE, 19.84% lower
latency, and trial rank 25–27 rather than 37. On Gaussian cases, it also has 7.71% lower projector
error than shell-3. This is a Pareto trade-off, not unconditional dominance in projector accuracy
or execution time.

![Figure 6. Accuracy-latency context on the formal A10 system.](../../figures/v3_formal/fig05_accuracy_latency.png)

### 6.5 Crossings and internal-gap behavior

The minimum external gap over the formal set is 0.01917. Exact-cluster gaps are numerically near
zero, while near-cluster gaps remain below the preregistered bound. The projector metric remains
defined throughout. Figure 7 plots error against the internal gap without assigning identities to
the individual bands.

![Figure 7. Point-mean projector error across exact and near-degenerate cases.](../../figures/v3_formal/fig08_error_vs_internal_gap.png)

### 6.6 Numerical integrity

**Table 3. Independent numerical checks.**

| Check | Observed | Frozen threshold |
|---|---:|---:|
| Reference projector, cutoff 24→28 | $1.51\times10^{-6}$ | $<10^{-3}$ |
| Reference eigenvalue, cutoff 24→28 | $6.95\times10^{-10}$ | $<10^{-5}$ |
| Solver projector, grid 65→97 | $2.10\times10^{-4}$ | $<10^{-3}$ |
| Solver eigenvalue, grid 65→97 | $4.77\times10^{-7}$ | $<10^{-4}$ |
| Proposed maximum raw Hermiticity defect | $7.13\times10^{-6}$ | $<10^{-4}$ |
| Maximum orthogonality error | $2.47\times10^{-7}$ | $<10^{-4}$ |
| Minimum external gap | 0.01917 | $>10^{-2}$ |

The all-method maximum Hermiticity defect is larger because the poorly converged Dai adaptation
reaches 0.00259. The formal gate correctly applies the Hermiticity threshold to the proposed
method, not to unrelated baseline failure.

## 7. Discussion

### 7.1 Why a projector target is appropriate

At a crossing, individually ordered eigenvectors are not a continuous physical observable. A
rank-two projector removes arbitrary phase, ordering, and internal rotation. External spectral
isolation, rather than a positive internal gap, is the relevant stability condition. The network
only needs to supply useful directions near the low-energy invariant space; the compact Ritz solve
then uses the operator to select the final cluster.

### 7.2 Division of labor

The formal results reveal a clear division. Smooth harmonic potentials are already represented
well by the tie-closed kinetic dictionary, so neural augmentation should be avoided. Localized
Gaussian wells contain substantial Fourier energy outside the first shell; two learned
parameter-dependent directions improve a compact analytic space. This mechanism is more precise
than saying that a neural network “solves the PDE better” in every regime.

### 7.3 What the router has and has not established

The route is label-free and successfully avoids regression at the two observed endpoints. It has
not been validated on potentials with $\rho$ close to 0.1, and route and family are perfectly
confounded in the formal set. A continuous roughness sweep or a third intermediate-complexity
family is therefore the most important external validation for future work. The frozen threshold
must not be retuned on such a supplement.

### 7.4 Relation to neighboring methods

Wang–Xie [3] establishes joint trace-based neural eigenanalysis; Dai et al. [5] establish neural
trial subspaces followed by Galerkin extraction; Chang et al. [6] address multiplicity over
parameterized shape families; Fanaskov et al. [8] regress parameterized subspaces with labels; and
Pau [9] applies reduced bases to repeated band calculations. SR-SC-NARR differs through the joint
use of a label-free parameter network, a fixed-rank projector target at internal crossings, D6 and
tie-closed analytic dictionaries, potential-only conditional augmentation, paired operator
assembly, and a one-shot confirmation with a strong rank-37 Fourier context.

## 8. Limitations and Threats to Validity

The formal benchmark contains two potential families but only two well-separated spectral-tail
regimes. It does not prove interpolation around the routing threshold or transfer to an unseen
family. The method addresses only the lowest rank-two cluster on a two-dimensional periodic cell;
higher clusters, three-dimensional crystals, and nonperiodic boundaries remain open.

The routing diagnostic adds approximately 42 ms relative to fixed hybrid and 71 ms relative to
Fourier-25 on the formal system. A fused or precomputed diagnostic is needed before claiming a
routing speed advantage. Formal latency is the mean of the randomized one-pass evaluation matrix;
a dedicated repeated microbenchmark and component-level profiler would strengthen hardware claims.

The bootstrap interval resamples physical points and is conditional on three archived checkpoint
seeds. It is not a population interval over arbitrary retraining randomness. Wang–Xie and Dai
results are formula-level adaptations, not official author-code reproductions. The Dai adaptation
converges poorly, so it is contextual rather than decisive evidence.

The formal experiment used PyTorch 2.10.0 although the development requirement originally pinned
the 2.8 series. Full tests passed on the formal environment and source/checkpoint/reference hashes
were unchanged, but the exact software version must be reported for reproducibility.

Internal-validity safeguards include a disjoint pilot, method and gate freezing before test
generation, a clean CUDA opening, a single-use marker, complete identity and finite-value audits,
independent cutoff/grid convergence, and an evidence archive binding source, suite, reference,
manifest, marker, rows, summary, gate, and provenance.

## 9. Conclusion

We introduced SR-SC-NARR, a conditional neural-augmented Rayleigh–Ritz solver for the lowest
spectral cluster of a parameterized two-dimensional Bloch–Schrödinger PDE. The method combines a
label-free generalized-trace network with D6-consistent, tie-closed Fourier trial spaces and a
potential-only spectral-tail diagnostic. It predicts a rank-two projector rather than separately
ordered bands and remains meaningful at internal crossings.

On a single procedurally frozen 160-point CUDA confirmation, the solver reduces mean projector
error by 28.76% relative to minimum-rank-25 kinetic Fourier, with a conditional 95% interval of
[28.08%, 29.44%]. The gain comes entirely from the spectrally rich Gaussian family; the harmonic
family safely falls back to Fourier. Relative to rank-37 shell-3, the proposed method is a lower-rank,
lower-eigenvalue-error, lower-latency Pareto alternative with nearly identical mean projector
accuracy. The evidence supports journal submission under a conditional neural-augmentation claim.
The clearest route toward a stronger general algorithm claim is a preregistered, fixed-threshold
roughness sweep spanning the empty interval between the two formal spectral endpoints.

## Reproducibility and Data Availability

Code, frozen suites, the reference cache, raw rows, summaries, gates, provenance, figures, and
evidence archives are maintained at `https://github.com/Lazywords2006/PINN-PDE`. The formal evidence
SHA-256 is
`108a4b042549ead58f7b13f42b6ace4685e93a4e8a54e9563b044c03c29ad78c`.
The formal suite is permanently closed and must not be rerun or used for threshold tuning.

## Ethics, Conflict of Interest, Funding, and AI Disclosure

This work involves no human participants, animals, personal data, or clinical decisions. The
authors declare no known conflict of interest, subject to confirmation by the final author list.
Funding information has not yet been supplied. Generative AI assisted with code review, document
organization, and language editing; the authors remain responsible for the mathematics,
citations, software, experiments, numerical values, and final manuscript.

## References

[1] M. Raissi, P. Perdikaris, and G. E. Karniadakis, “Physics-informed neural networks:
A deep learning framework for solving forward and inverse problems involving nonlinear partial
differential equations,” *Journal of Computational Physics*, 378, 686–707, 2019.
https://doi.org/10.1016/j.jcp.2018.10.045

[2] A. Kovacs et al., “Conditional physics informed neural networks,” *Communications in
Nonlinear Science and Numerical Simulation*, 104, 106041, 2022.
https://doi.org/10.1016/j.cnsns.2021.106041

[3] Y. Wang and H. Xie, “Computing multi-eigenpairs of high-dimensional eigenvalue problems
using tensor neural networks,” *Journal of Computational Physics*, 506, 112928, 2024.
https://doi.org/10.1016/j.jcp.2024.112928

[4] C. Rowan, J. Evans, K. Maute, and A. Doostan, “Solving engineering eigenvalue problems
with neural networks using the Rayleigh quotient,” *International Journal for Numerical Methods
in Engineering*, 126, e70209, 2025. https://doi.org/10.1002/nme.70209

[5] X. Dai, Y. Fan, and Z. Sheng, “Subspace method based on neural networks for solving
eigenvalue problems,” *Communications in Nonlinear Science and Numerical Simulation*, 161,
110060, 2026. https://doi.org/10.1016/j.cnsns.2026.110060

[6] Y. Chang et al., “Shape Space Spectra,” *ACM Transactions on Graphics*, 44(4), 1–16,
2025. https://doi.org/10.1145/3731148

[7] L. Grubišić, M. Saarikangas, and H. Hakula, “Stochastic collocation method for computing
eigenspaces of parameter-dependent operators,” *Numerische Mathematik*, 153, 85–110, 2023.
https://doi.org/10.1007/s00211-022-01339-3

[8] V. Fanaskov et al., “Deep Learning for Subspace Regression,” *International Conference on
Learning Representations*, 2026. https://openreview.net/forum?id=HF60Lu1Maj

[9] G. S. H. Pau, “Reduced-basis method for band structure calculations,” *Physical Review E*,
76, 046704, 2007. https://doi.org/10.1103/PhysRevE.76.046704

[10] T. Horger, B. Wohlmuth, and T. Dickopf, “Simultaneous reduced basis approximation of
parameterized elliptic eigenvalue problems,” *ESAIM: M2AN*, 51(2), 443–465, 2017.
https://doi.org/10.1051/m2an/2016025

[11] C. L. Fefferman and M. I. Weinstein, “Honeycomb lattice potentials and Dirac points,”
*Journal of the American Mathematical Society*, 25(4), 1169–1220, 2012.
https://doi.org/10.1090/S0894-0347-2012-00745-0

[12] B. Haasdonk et al., “A new certified hierarchical and adaptive RB-ML-ROM surrogate model
for parametrized PDEs,” *SIAM Journal on Scientific Computing*, 45(3), A1039–A1065, 2023.
https://doi.org/10.1137/22M1493318

[13] C. Hsu et al., “Equation-driven neural networks for periodic quantum systems,” NeurIPS
Workshop on Machine Learning and the Physical Sciences, 2024.
https://neurips.cc/virtual/2024/99978

[14] H. Jin, M. Mattheakis, and P. Protopapas, “Physics-Informed Neural Networks for Quantum
Eigenvalue Problems,” *International Joint Conference on Neural Networks*, 2022.
https://doi.org/10.1109/IJCNN55064.2022.9891944

[15] C. Davis and W. M. Kahan, “The rotation of eigenvectors by a perturbation. III,”
*SIAM Journal on Numerical Analysis*, 7(1), 1–46, 1970.
https://doi.org/10.1137/0707001

[16] W. E and B. Yu, “The Deep Ritz Method: A Deep Learning-Based Numerical Algorithm for
Solving Variational Problems,” *Communications in Mathematics and Statistics*, 6(1), 1–12,
2018. https://doi.org/10.1007/s40304-018-0127-z

[17] N. Kovachki et al., “Neural Operator: Learning Maps Between Function Spaces With
Applications to PDEs,” *Journal of Machine Learning Research*, 24(89), 1–97, 2023.
https://jmlr.org/papers/v24/21-1524.html

[18] S. W. Cheung, Y. Choi, S. W. Chung, J.-L. Fattebert, C. Kendrick, and D. Osei-Kuffuor,
“Theory and numerics of subspace approximation of eigenvalue problems,” *Applied Mathematics and
Computation*, 511, 129722, 2026. https://doi.org/10.1016/j.amc.2025.129722

[19] D. Peterseim, J.-F. Pietschmann, J. Püschel, and K. Rueß, “Neural network acceleration of
iterative methods for nonlinear Schrödinger eigenvalue problems,” *Journal of Computational and
Applied Mathematics*, 485, 117414, 2026. https://doi.org/10.1016/j.cam.2026.117414

[20] F. Bertrand, D. Boffi, and A. Halim, “Data-driven reduced order modeling for parametric
PDE eigenvalue problems using Gaussian process regression,” *Journal of Computational Physics*,
495, 112503, 2023. https://doi.org/10.1016/j.jcp.2023.112503

[21] J. Dölz and D. Ebert, “On Uncertainty Quantification of Eigenvalues and Eigenspaces with
Higher Multiplicity,” *SIAM Journal on Numerical Analysis*, 62(1), 422–451, 2024.
https://doi.org/10.1137/22M1529324

[22] H. Li, J. Sun, and Z. Zhang, “Deep Eigenspace Network for Parametric Non-Self-Adjoint
Eigenvalue Problems,” arXiv:2512.20058, 2026. https://arxiv.org/abs/2512.20058

[23] Z. Hao et al., “PINNacle: A Comprehensive Benchmark of Physics-Informed Neural Networks
for Solving PDEs,” *Advances in Neural Information Processing Systems 37*, 76721–76774, 2024.
https://doi.org/10.52202/079017-2442

[24] N. McGreivy and A. Hakim, “Weak baselines and reporting biases lead to overoptimism in
machine learning for fluid-related partial differential equations,” *Nature Machine Intelligence*,
6(10), 1256–1269, 2024. https://doi.org/10.1038/s42256-024-00897-5

[25] S. Kapoor and A. Narayanan, “Leakage and the reproducibility crisis in
machine-learning-based science,” *Patterns*, 4(9), 100804, 2023.
https://doi.org/10.1016/j.patter.2023.100804

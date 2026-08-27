# A Basis-Invariant Neural-Augmented Rayleigh–Ritz Solver for Parametric Bloch Spectral Clusters with Eigenvalue Crossings

> **SUPERSEDED — DO NOT SUBMIT.** A 27 August 2026 audit found an inconsistent reciprocal-shell
> convention in this version. Its P2/Q3 numbers remain immutable historical evidence, but the
> current method is the V3 symmetry-corrected SR-SC-NARR protocol. This manuscript will be replaced
> after the new CUDA confirmation; none of the results below are current publication claims.
>
> English manuscript v0.3, 27 August 2026. Every numerical value below comes from an archived
> experiment. The NMPDE-oriented editable DOCX and PDF preview are complete. Author names,
> affiliations, ORCID, CRediT roles, funding, and final journal-system metadata remain for the
> authors to supply.

## Abstract

Parameterized Bloch eigenproblems require repeated PDE solves, while internal band crossings make
individually ordered eigenfunctions discontinuous. We propose a basis-invariant neural-augmented
Rayleigh–Ritz solver for the lowest rank-two spectral cluster of a two-dimensional periodic
Bloch–Schrödinger equation. A lightweight SiLU multilayer perceptron learns a label-free neural
coarse space through a generalized-trace objective. At inference, this space is augmented by the
complete second hexagonal Fourier shell. Automatic differentiation is used only for the two neural
columns; Hamiltonian actions on 19 plane waves are assembled analytically, and paired
orthogonalization produces a compact Ritz problem. A one-shot frozen test contains 640 parameter
points, two honeycomb potential families, three checkpoint seeds, ten methods, and 19,200 paired
evaluations. The proposed solver attains an overall projector error of 0.04532, compared with
0.14719 for a compute-matched long-anchor network and 0.13697 for a same-rank Fourier-only
control. Its improvement over long-anchor is 69.19%, with a point-clustered 95% interval of
[67.66%, 70.75%]. On a separate 160-point journal-baseline supplement, P2 attains 0.04728 versus
0.13114 for a Wang–Xie trace adaptation, an improvement of 63.78% with a 95% interval of
[59.58%, 67.88%], and wins all six family-by-seed comparisons. The results support a reproducible
accuracy-cost trade-off at internal crossings. The method is a hybrid neural numerical
eigensolver rather than a conventional residual PINN or a purely Fourier solver.

**Keywords:** neural PDE solver; parametric eigenproblem; Bloch–Schrödinger equation; spectral
cluster; Rayleigh–Ritz; basis invariance; scientific machine learning

## 1. Introduction

Physics-informed neural networks incorporate differential equations, boundary conditions, or
variational principles into network training, enabling approximation with few or no solution
labels [1]. Their appeal is especially strong for parameterized problems: one trained model can
serve many operator instances. Conditional PINNs have demonstrated this idea for classes of
eigenvalue problems [2]. Differential eigenproblems, however, introduce complications absent from
standard initial-boundary-value problems. A solver must avoid the trivial zero function, identify
multiple eigenstates, enforce normalization and orthogonality, and remain meaningful at
multiplicities and crossings.

Bloch–Schrödinger operators with two-dimensional honeycomb potentials can exhibit conical Dirac
crossings at vertices of the Brillouin zone [11]. At such a crossing, separate labels for the first
and second bands do not define a globally continuous target. Their eigenvectors may also undergo
arbitrary unitary rotations within the degenerate eigenspace. Regressing ordered eigenfunctions or
minimizing separate residuals can therefore mistake a representational choice for a physical
solution. In contrast, if the lowest two states remain separated from the third state by an
external spectral gap, their rank-two eigenspace and spectral projector remain well-defined [7].

Several existing lines of work supply components of a solution. Wang and Xie used tensor neural
networks and a trace objective to compute multiple eigenpairs jointly [3]. Rowan et al. combined
Rayleigh quotients with Gram–Schmidt orthogonalization for engineering eigenproblems [4]. Dai et
al. constructed neural trial subspaces and solved a projected Galerkin eigenproblem [5].
Parameterized neural eigenanalysis has also been studied through dynamic mode reordering in Shape
Space Spectra [6], supervised Grassmannian subspace regression [8], and equation-driven networks
for periodic quantum systems [13]. Classical reduced-basis methods have long addressed Bloch band
structures [9] and parameter-dependent multiple eigenspaces [10]. Consequently, this work does not
claim Ky Fan principles, trace objectives, Fourier bases, Galerkin projection, or Rayleigh–Ritz as
standalone inventions.

We address a narrower question: can a lightweight, label-free parameter network supply an
amortized coarse space for an internally crossing Bloch cluster, and can a fixed analytic Fourier
shell correct that space without turning inference into a full high-cutoff plane-wave solve? The
contributions are as follows.

**Contribution 1 — Crossing-aware target.** The lowest two Bloch states are formulated as a rank-two projector-learning problem. Training,
   refinement, and evaluation are insensitive to column permutations, phases, and unitary rotations
   within the target cluster.
**Contribution 2 — Neural-analytic trial space.** A compact trial space combines a label-free neural coarse basis with the complete second
   hexagonal Fourier shell. A same-rank Fourier-only control isolates the contribution of the neural
   component.
**Contribution 3 — Paired fast assembly.** Hamiltonian assembly is split by column type. Only the two neural columns use automatic
   differentiation. The 19 Fourier columns use an analytic action. The same orthogonalization transform
   is applied to each pair \((w,Hw)\).
**Contribution 4 — Frozen evidence protocol.** Evaluation uses an independent pilot, a one-shot frozen test, and a disjoint journal-baseline
   supplement, with clustered bootstrap intervals, timing, and hash-bound evidence auditing.

The claims in this draft are limited to this combined mechanism and the archived benchmarks. The
supplement contains formula-level Bloch adaptations of Dai et al. and Wang and Xie; they are not
represented as official reproductions of the authors' software.

## 2. Related Work

### 2.1 Neural PDE and eigenvalue solvers

Conventional PINNs minimize pointwise differential residuals together with boundary, initial, and
optional data terms [1]. Eigenproblems complicate this construction because eigenvalues are unknown,
the zero function satisfies a homogeneous residual, and multiple states require normalization and
orthogonality. Jin et al. introduced unsupervised neural quantum eigensolvers with normalization and
orthogonality losses [14]. Kovacs et al. extended conditional PINNs so that one network covered a
class of eigenproblems [2]. These studies establish the feasibility of label-free neural
eigenanalysis, but individually represented states may still be discontinuous at crossings.

Wang and Xie optimized multiple eigenpairs together using tensor neural networks and a trace
objective [3], showing that joint subspace-style optimization can avoid some limitations of serial
deflation. Rowan et al. demonstrated that Rayleigh quotient minimization and Gram–Schmidt provide a
simple, reliable combination for continuous engineering eigenproblems [4]. These works motivate
our variational coarse network. They do not, however, evaluate a single parameter network that
predicts a fixed-rank low-energy projector through internal Bloch crossings.

### 2.2 Neural subspaces, Galerkin projection, and parametric eigenspaces

Dai, Fan, and Sheng train neural basis functions and project an eigenproblem onto their span [5].
This is the closest journal method to the present solver and must be treated as a direct baseline.
Our setting differs in its parameterized Bloch cluster, physical anchor, closed reciprocal shell,
analytic Fourier Hamiltonian, and paired orthogonalization. Whether these differences produce a
consistent advantage has been examined with an independent formula-level Bloch adaptation. The
remaining gap to an official author implementation is acknowledged as a limitation.

Shape Space Spectra uses a neural field across continuously parameterized shape families and
dynamically reorders individual eigenfunctions at multiplicities [6]. We avoid assigning an
identity within the cluster and directly evaluate the rank-two projector. Fanaskov et al. formulate
parameter-to-subspace prediction as supervised Grassmann regression [8], whereas our training loss
does not access plane-wave projector labels. Grubišić et al. show that an externally isolated
parametric eigenspace can retain regular parameter dependence in the presence of internal
crossings [7], supporting the cluster rather than bandwise formulation used here.

### 2.3 Bloch reduced bases and periodic quantum networks

Pau applied reduced bases to repeated band-structure calculations [9]. Horger et al. developed
simultaneous reduced-basis approximation for parameterized elliptic eigenproblems and emphasized
parameter-dependent multiplicity and error estimation [10]. Hsu et al. trained equation-driven
networks for band structures and wavefunctions in two-dimensional periodic quantum systems [13].
Haasdonk et al. built a hierarchical full-order, reduced-order, and machine-learning chain with
a posteriori certification [12], reinforcing the need to report accuracy, cost, and reliability for
hybrid neural numerical solvers rather than neural forward time alone.
Together these papers place the present study at the intersection of neural PDE solvers,
amortized eigenspaces, and band-structure model reduction. They also narrow the novelty claim: the
contribution must be the complete crossing-aware neural-plus-analytic mechanism and its controlled
validation, not the use of a honeycomb potential or Fourier basis alone.

## 3. Problem Formulation

### 3.1 Bloch–Schrödinger eigenproblem

On the periodic cell \(\Omega=[0,2\pi)^2\), we consider

\[
\mathcal H_{\mathbf k,\mu}u_j=
\left[\frac12(-i\nabla+\mathbf k)^T G(-i\nabla+\mathbf k)
+V_\mu(\mathbf x)\right]u_j
=E_j u_j,
\]

with periodic function and first-derivative boundary conditions. For reciprocal mode
\(\mathbf m=(m_1,m_2)\), the implemented kinetic energy is

\[
T(\mathbf m,\mathbf k)=\frac12\left[(m_1+k_1)^2+(m_2+k_2)^2
+(m_1+k_1)(m_2+k_2)\right].
\]

The harmonic honeycomb family is

\[
V_{a,\delta}(x,y)=a[\cos x+\cos y+\cos(x-y)]
+\delta[\sin x-\sin y-\sin(x-y)],
\]

where \(a\in[0.2,0.8]\) and \(\delta\in[-0.08,0.08]\). The Gaussian honeycomb
family contains two periodically repeated Gaussian sublattices and is parameterized by amplitude
\(a\in[1,4]\), width \(\sigma\in[0.18,0.35]\), and imbalance
\(\delta\in[-0.08,0.08]\). For both families, the training box uses
\(k_x,k_y\in[0.28,0.38]\).

### 3.2 Cluster target and error metric

Let \(U_2(\mathbf k,\mu)\) denote the span of the two lowest eigenstates and let \(P_2\)
be its orthogonal projector. The internal gap \(E_2-E_1\) may vanish, but the external gap
\(E_3-E_2\) should remain positive. Given predicted and reference bases \(Q\) and
\(Q_\star\), the primary metric is the root-mean-square sine of their principal angles,

\[
e_{\mathrm{proj}}=
\sqrt{\frac{2-\lVert Q^*Q_\star\rVert_F^2}{2}}.
\]

This is equivalently a normalized Frobenius discrepancy between the rank-two projectors. It is
invariant to column order, complex phase, and unitary rotation within either basis.

Reference solutions are generated by a float64 plane-wave expansion (PWE) with cutoff 24 and rank
3, then evaluated on a 33 by 33 periodic grid. PWE eigenvectors and projectors are used only for
testing and audit, never as labels for the variational neural training.

## 4. Method

### 4.1 Label-free neural coarse space

The network input is

\[
[\sin x,\cos x,\sin y,\cos y,\mathbf k,\mu].
\]

Three width-64 SiLU hidden layers output real and imaginary components of two complex periodic
functions. The harmonic and Gaussian networks contain 9,156 and 9,220 trainable parameters,
respectively. A fixed combination of low-energy plane waves near the K point supplies a physical
anchor, and the MLP learns an additive correction. Training uses Adam with learning rate
\(10^{-3}\), four parameter instances per batch, and 256 shifted periodic grid points per
instance. The final long-anchor checkpoints were trained for 665 steps with seeds 42, 137, and 251.

For a raw trial matrix \(Z_\theta\), define

\[
B_\theta=Z_\theta^*Z_\theta,\qquad
A_\theta=Z_\theta^*\mathcal H Z_\theta.
\]

The label-free objective is the generalized trace

\[
\mathcal L_{\mathrm{trace}}=\operatorname{Tr}(B_\theta^{-1}A_\theta).
\]

No reference eigenvector, projector, or band label enters the loss. Complex modified
Gram–Schmidt under equal-weight cell quadrature produces the neural coarse basis
\(Q_\theta\) for evaluation and refinement.

### 4.2 Complete second-shell augmentation

Define the closed hexagonal reciprocal dictionary

\[
\mathcal M_2=\{(m_1,m_2)\in\mathbb Z^2:
\max(|m_1|,|m_2|,|m_1-m_2|)\le2\}.
\]

It contains 19 plane waves \(\phi_m(\mathbf x)=e^{i m\cdot x}\). The augmented trial
matrix is

\[
W=[Q_\theta,\{\phi_m:m\in\mathcal M_2\}].
\]

Each analytic column is projected against previously accepted columns. Directions with projected
norm below \(10^{-5}\) are rejected. The complete configuration normally yields a 21-dimensional
space. Because augmentation operates on the span, any unitary rotation of the two neural columns
leaves the final trial space unchanged.

### 4.3 Analytic Hamiltonian action and paired orthogonalization

PyTorch automatic differentiation is used to calculate \(\mathcal H Q_\theta\) for the two
neural columns. For a plane wave,

\[
\mathcal H\phi_m=
\left[T(\mathbf m,\mathbf k)+V_\mu(\mathbf x)\right]\phi_m,
\]

so all 19 analytic columns avoid second-order autograd graphs. During orthogonalization, every
complex linear transformation applied to a trial vector \(w\) is also applied to \(Hw\). This
produces a paired basis \((\widehat W,H\widehat W)\), preserves the linear Hamiltonian relation,
and removes the need to differentiate the augmented basis again.

### 4.4 Compact Ritz extraction

The reduced Hermitian matrix is

\[
A_W=\widehat W^*H\widehat W.
\]

Its two lowest Ritz vectors are mapped back to the function grid to obtain the final rank-two
basis. P2 adds no learned parameters and never reads the reference projector at inference. The
pipeline is

\[
(\mathbf x,\mathbf k,\mu)
\xrightarrow{\text{label-free SiLU MLP}}Q_\theta
\xrightarrow{+\mathcal M_2}\widehat W
\xrightarrow{\text{paired }(W,HW)}A_W
\xrightarrow{\text{Ritz}}\widehat U_2.
\]

![P2 method pipeline](../../figures/p2_final/fig09_method_pipeline.png)

**Figure 1.** Basis-invariant neural-augmented Rayleigh–Ritz pipeline.

### 4.5 External-gap stability

Let \(U\) be the exact lowest rank-two invariant subspace, \(Q\) an orthonormal Ritz basis,
\(M=Q^*HQ\), and \(R=HQ-QM\). If the approximate Ritz spectrum is separated from the
unwanted spectrum by

\[
\delta=\operatorname{dist}(\sigma(M),\sigma(H|_{U^\perp}))>0,
\]

then the Hermitian invariant-subspace residual bound [15] gives

\[
e_{\mathrm{proj}}
\le\frac{\lVert R\rVert_F}{\sqrt2\,\delta}.
\]

The separation concerns the target cluster and the third state; it does not require a positive
internal gap between the first two eigenvalues. The bound therefore remains meaningful at an
internal Dirac crossing. The reported residual RMS is normalized over grid points, rank, and
real/imaginary components and must be rescaled before insertion into this Frobenius-norm bound.

### 4.6 Complexity and amortization

For \(N\) grid points, \(M=19\) analytic modes, and trial rank \(r\le21\), the online stage
contains two neural Hamiltonian evaluations, \(O(NM)\) analytic Fourier actions,
\(O(Nr^2)\) paired orthogonalization, and an \(O(r^3)\) Ritz solve. The MLP linear layers require
approximately 19.5 million FLOPs on the 33 by 33 grid. End-to-end FLOPs for second-order automatic
differentiation depend on the backend, so measured wall time is reported instead of an unverified
total. Archived timings give an approximate system-level training break-even of 206–354 repeated
parameter queries.

## 5. Experimental Design

### 5.1 Development and freezing protocol

The low-frequency ROM studied in P5 was stopped because a compute-matched long-anchor network
performed better near crossings and the ROM regressed on gap scans. P0 showed that failures were
detectable, but P1 risk routing could not exceed the accuracy of its two endpoint subspaces and was
also stopped. An initial outer-shell P2 probe improved near-crossing points but failed frozen gap
and efficiency criteria. Only after the complete-shell method passed every preregistered gate on a
new 96-point pilot, with two families and three seeds, was the 640-point frozen test opened once.
It is now permanently closed.

### 5.2 Splits and comparisons

The frozen test contains 192 IID points, 64 exact-cluster points, 128 near-cluster points,
128 strict-OOD points, and 128 gap-scan points. Each family contributes 320 points. Ten methods
are evaluated for three checkpoint seeds at every point, yielding 19,200 rows.

The comparison matrix contains unanchored trace, anchor, wide anchor, long anchor, static
low-frequency ROM, high-frequency ROM, neural plus shell 1, neural plus outer shell 2, the proposed
complete-shell method, and a Fourier-only rank-21 control. This is a controlled internal matrix.
A second, disjoint suite evaluates explicit Bloch adaptations of Wang–Xie [3] and Dai [5].

### 5.3 Statistics and hardware

The primary confidence intervals use 2,000 bootstrap samples clustered by the 640 physical
parameter points. All checkpoint seeds associated with a point are resampled together. Formal
evaluation ran on an NVIDIA RTX 5090 D with 32 GB memory, PyTorch 2.8.0+cu128, and CUDA 12.8.
Latency uses ten warmups followed by 100 repetitions. The PWE reference was timed on the CPU of the
same server. This comparison represents system-level wall time, not a device-matched kernel
benchmark.

### 5.4 Journal-baseline supplement

The supplementary suite contains 160 parameter points disjoint from all earlier decision sets,
with 80 points per potential family and coverage of IID, exact-cluster, near-cluster, strict-OOD,
and gap-scan regimes. Wang–Xie trace and rank-six Dai-style neural-subspace Galerkin adaptations
are trained for 1,500 steps with three seeds under the same sampling and collocation budget. This
budget exceeds the 665 steps used by the P2 neural initializer. All methods use the same cutoff-24
reference. The matrix contains 1,440 rows and uses 2,000 point-clustered bootstrap samples.

## 6. Results

### 6.1 Main comparison

**Table 1.** Frozen-final rank-two projector sine error (lower is better).

| Method | Overall | Near | Gap scan |
|---|---:|---:|---:|
| Unanchored trace | 0.19784 | 0.14589 | 0.21830 |
| Anchor | 0.15650 | 0.10505 | 0.14050 |
| Wide anchor | 0.15243 | 0.10020 | 0.15111 |
| Long anchor | 0.14719 | 0.08924 | 0.15938 |
| Static low-ROM | 0.15054 | 0.09542 | 0.14946 |
| High-frequency ROM | 0.15531 | 0.10299 | 0.14809 |
| Neural + shell 1 | 0.06172 | 0.04513 | 0.05768 |
| Neural + outer shell 2 | 0.13410 | 0.07849 | 0.15656 |
| **Neural + complete shell 2** | **0.04532** | **0.03903** | **0.04389** |
| Fourier-only rank 21 | 0.13697 | 0.12249 | 0.13700 |

The complete-shell solver gives the lowest error overall, near crossings, and on gap scans. Its
overall improvement over long-anchor is 69.19%, with a point-clustered 95% interval of
[67.66%, 70.75%]. The near-crossing improvement is 56.28%, with a 95% interval of
[53.24%, 59.22%]. Both intervals remain far from zero.

![Frozen-final overall method comparison](../../figures/p2_final/fig01_method_overall_error.png)

**Figure 2.** Overall projector error for the ten frozen-final methods. Lower is better.

### 6.2 Parameter regimes and potential families

Errors on IID, exact-cluster, near-cluster, strict-OOD, and gap-scan points are 0.04383, 0.04220,
0.03903, 0.05685, and 0.04389. Long-anchor reaches 0.22921 on strict OOD, indicating that the
gain is not confined to points selected around the crossing.

![Projector error across five parameter regimes](../../figures/p2_final/fig02_split_comparison.png)

**Figure 3.** Projector error across IID, exact-cluster, near-cluster, strict-OOD, and gap-scan
regimes.

For harmonic near-cluster points, error decreases from 0.06508 to 0.03037. For the Gaussian
family, it decreases from 0.11340 to 0.04770. The proposed solver wins all six
family-by-checkpoint-seed comparisons. Overall errors across the three seeds are 0.04384, 0.04559,
and 0.04654, with a standard deviation of 0.00137. Maximum orthogonality error is
\(3.12\times10^{-7}\).

![Point-clustered bootstrap intervals](../../figures/p2_final/fig04_bootstrap_improvement.png)

**Figure 4.** Point-clustered bootstrap intervals for improvement over the long-anchor baseline.

### 6.3 Ablation evidence

The Fourier-only rank-21 control has overall error 0.13697, compared with 0.04532 for the proposed
method. A fixed dictionary of equal nominal rank therefore does not explain the improvement. The
parameter-dependent neural directions are essential. Shell 1 reaches 0.06172, and completing shell
2 reduces error to 0.04532. Adding only the outer second shell yields 0.13410, showing that the
closed low-to-second-order reciprocal space is substantially more effective than an isolated outer
ring.

All three shell variants reuse the same long-anchor checkpoints. Their differences arise from the
inference-time trial space and Ritz extraction, not additional network training, learned
parameters, or post-final tuning.

### 6.4 Efficiency

Mean inference time is 107.81 ms per parameter and the 95th percentile is 121.90 ms. The
same-server cutoff-24 CPU PWE solve takes 313.44 ms on average, giving a ratio of 0.344. A neural
forward pass alone remains close to 1 ms, so the proposed solver is not a cost-free correction. It
occupies an intermediate accuracy-latency point between a fast neural surrogate and a high-accuracy
direct eigensolve.

![Accuracy-latency comparison](../../figures/p2_final/fig07_accuracy_latency.png)

**Figure 5.** Accuracy-latency comparison. P2 lies between a single neural forward pass and the
cutoff-24 reference solve.

### 6.5 Independent journal-baseline supplement

**Table 2.** Independent supplement results on 160 parameter points (lower is better).

| Method | Overall | Near | Gap scan | Strict OOD |
|---|---:|---:|---:|---:|
| **P2 full shell** | **0.04728** | **0.03804** | **0.06727** | **0.05796** |
| Wang–Xie trace adapted | 0.13114 | 0.09056 | 0.15110 | 0.21776 |
| Dai Galerkin adapted | 0.43367 | 0.42376 | 0.47148 | 0.43758 |

P2 improves over the Wang–Xie adaptation by 63.78%, with a 95% interval of
[59.58%, 67.88%], and over the Dai adaptation by 89.08%, with an interval of
[88.10%, 90.01%]. It wins all six family-by-seed comparisons against both baselines. Mean
latencies for P2, Wang–Xie, and Dai are 193.75, 2.47, and 205.56 ms, respectively. The
Wang–Xie adaptation is therefore substantially faster but less accurate, whereas P2 and the Dai
adaptation occupy a similar latency range.

The Dai adaptation converges poorly in the present parameterized Bloch setting. This result does
not establish that the method of Dai et al. is ineffective. The strongest nearest-neighbor evidence
is the stable P2 advantage over the parameter-matched Wang–Xie trace adaptation despite its larger
training budget.

## 7. Discussion

### 7.1 Why the cluster formulation helps

Bandwise prediction turns a physically nonunique basis choice into a learning target. At a Dirac
crossing, that choice can swap or rotate abruptly. Projector-based training and evaluation remove
this artificial discontinuity. External spectral isolation keeps the target subspace meaningful,
while the network only needs to place a compact trial space near it. Rayleigh–Ritz then selects the
lowest-energy directions using the operator itself.

### 7.2 Division of labor between neural and numerical components

The neural network learns parameter-dependent low-energy directions that a small fixed Fourier
dictionary does not capture uniformly. The analytic shell supplies structured correction
directions, and the reduced Ritz solve restores operator consistency. This division explains why
both pure neural and pure rank-21 Fourier controls underperform their combination. The scientific
claim is therefore a controlled hybrid mechanism, not the replacement of classical numerical
analysis by a neural network.

### 7.3 Relation to the closest literature

Wang and Xie [3] established trace-based neural computation of multiple eigenpairs. Dai et al. [5]
established a neural-subspace-plus-Galerkin eigensolver. Chang et al. [6] addressed multiplicity and
mode switching over parameterized families. Pau [9] applied reduced bases to band structures. The
present method differs through the simultaneous use of a label-free Bloch parameter network, a
rank-two projector target at internal crossings, an orthogonal-complement closed hexagonal shell,
paired \((W,HW)\) transformations, and a frozen near/gap/OOD evaluation with a same-rank control.

The independent supplement shows a stable P2 advantage over a Wang–Xie trace adaptation in the
same Bloch framework. Formula-level adaptations are not official author implementations, and the
poor convergence of the Dai adaptation cannot support a claim of universal superiority to Dai et
al. [5].

## 8. Limitations and Threats to Validity

The study covers two honeycomb potential families and only the lowest rank-two cluster. The results
do not directly extend to higher-rank clusters, three-dimensional crystals, or nonperiodic boundary
conditions. The supplement contains formula-level Bloch adaptations rather than official
author-code reproductions, and the convergence of the Dai adaptation limits its comparative
strength. The P2-to-PWE timing
uses a GPU method and CPU reference and must be interpreted as a system configuration rather than
a hardware-independent speedup. The manuscript provides symbolic complexity, neural-forward FLOPs,
a break-even estimate, and an external-gap residual bound, but it does not yet contain profiler-based
end-to-end hardware FLOPs for second-order automatic differentiation. Three formal training seeds are supported by
clustered bootstrap statistics and six of six family-seed wins, but additional seeds may still be
useful in supplementary experiments. The frozen test itself must not be rerun.

Internal-validity safeguards include a single final opening after an independent pilot, SHA-256
bindings for suites, references, checkpoints, source, and evidence packages, complete identity
audits of 19,200 final rows and 1,440 supplementary rows, and independent local aggregation. The
supplement verifies 89 manifest files in both remote and local audits.

## 9. Conclusion

We developed a basis-invariant neural-augmented Rayleigh–Ritz solver for an internally crossing
spectral cluster of a two-dimensional parametric Bloch–Schrödinger PDE. A label-free SiLU network
provides a parameter-dependent rank-two coarse space. A complete second hexagonal Fourier shell,
analytic Hamiltonian actions, and a compact Ritz problem refine that space without accessing test
projectors. Frozen evaluation reduces overall projector error from 0.14719 for the strongest pure
neural baseline to 0.04532, with consistent gains across both potential families, all five parameter
regimes, and every family-seed pairing.

The evidence supports the classification of this work as a genuine neural PDE eigensolver and is
sufficient for journal submission preparation. It provides a strong Q4 foundation, while the
independent journal-baseline supplement creates a realistic but not guaranteed Q3 opportunity.
The target-journal package and publication-ready method diagram are complete. Optional CUDA
profiler counts should be added only if requested; the frozen test and supplement remain closed.

## Data Availability

Source code, frozen benchmarks, CSV/JSON outputs, evidence hashes, and figure-generation scripts
are intended for public release before publication. The development repository is
`https://github.com/Lazywords2006/PINN-PDE`. The frozen-final evidence SHA-256 is
`c653d0eddab018741312741f6db46f023a20812306d574b66947bbb42af25095`.

## Ethics Declaration

This work did not involve human participants, animals, or personal data.

## Author Contributions (CRediT; pending author confirmation)

Conceptualization, methodology, software, validation, data curation, visualization, writing, and
project-administration roles will be assigned after the author list is finalized.

## Conflict of Interest

The authors declare no known conflict of interest. This statement must be reconfirmed by every
author before submission.

## Funding

No funding information has been provided. The final manuscript will list the actual grants or state
that the work received no specific external funding.

## AI-Assistance Disclosure

Generative AI assisted with document organization, language editing, and construction of the code
evidence index. The authors remain responsible for verifying all mathematics, citations,
experimental values, statistical claims, and final prose. The disclosure will be adapted to the
policy of the selected journal.

## References

[1] M. Raissi, P. Perdikaris, and G. E. Karniadakis, “Physics-informed neural
networks: A deep learning framework for solving forward and inverse problems involving
nonlinear partial differential equations,” *Journal of Computational Physics*, vol. 378,
pp. 686–707, 2019. https://doi.org/10.1016/j.jcp.2018.10.045

[2] A. Kovacs et al., “Conditional physics informed neural networks,” *Communications in
Nonlinear Science and Numerical Simulation*, vol. 104, 106041, 2022.
https://doi.org/10.1016/j.cnsns.2021.106041

[3] Y. Wang and H. Xie, “Computing multi-eigenpairs of high-dimensional eigenvalue
problems using tensor neural networks,” *Journal of Computational Physics*, vol. 506,
112928, 2024. https://doi.org/10.1016/j.jcp.2024.112928

[4] C. Rowan, J. Evans, K. Maute, and A. Doostan, “Solving engineering eigenvalue
problems with neural networks using the Rayleigh quotient,” *International Journal for
Numerical Methods in Engineering*, vol. 126, no. 24, e70209, 2025.
https://doi.org/10.1002/nme.70209

[5] X. Dai, Y. Fan, and Z. Sheng, “Subspace method based on neural networks for solving
eigenvalue problems,” *Communications in Nonlinear Science and Numerical Simulation*,
vol. 161, 110060, 2026. https://doi.org/10.1016/j.cnsns.2026.110060

[6] Y. Chang, O. Benchekroun, M. M. Chiaramonte, P. Y. Chen, and E. Grinspun,
“Shape Space Spectra,” *ACM Transactions on Graphics*, vol. 44, no. 4, pp. 1–16,
2025. https://doi.org/10.1145/3731148

[7] L. Grubišić, M. Saarikangas, and H. Hakula, “Stochastic collocation method for
computing eigenspaces of parameter-dependent operators,” *Numerische Mathematik*,
vol. 153, pp. 85–110, 2023. https://doi.org/10.1007/s00211-022-01339-3

[8] V. Fanaskov, V. Trifonov, A. Rudikov, E. Muravleva, and I. Oseledets, “Deep
Learning for Subspace Regression,” in *International Conference on Learning
Representations (ICLR)*, 2026. https://openreview.net/forum?id=HF60Lu1Maj

[9] G. S. H. Pau, “Reduced-basis method for band structure calculations,” *Physical
Review E*, vol. 76, 046704, 2007. https://doi.org/10.1103/PhysRevE.76.046704

[10] T. Horger, B. Wohlmuth, and T. Dickopf, “Simultaneous reduced basis approximation
of parameterized elliptic eigenvalue problems,” *ESAIM: Mathematical Modelling and
Numerical Analysis*, vol. 51, no. 2, pp. 443–465, 2017.
https://doi.org/10.1051/m2an/2016025

[11] C. L. Fefferman and M. I. Weinstein, “Honeycomb lattice potentials and Dirac
points,” *Journal of the American Mathematical Society*, vol. 25, no. 4,
pp. 1169–1220, 2012. https://doi.org/10.1090/S0894-0347-2012-00745-0

[12] B. Haasdonk, H. Kleikamp, M. Ohlberger, F. Schindler, and T. Wenzel, “A new
certified hierarchical and adaptive RB-ML-ROM surrogate model for parametrized PDEs,”
*SIAM Journal on Scientific Computing*, vol. 45, no. 3, pp. A1039–A1065, 2023.
https://doi.org/10.1137/22M1493318

[13] C. Hsu, M. Mattheakis, G. R. Schleder, and D. T. Larson, “Equation-driven neural
networks for periodic quantum systems,” NeurIPS 2024 Workshop on Machine Learning and
the Physical Sciences, 2024. https://neurips.cc/virtual/2024/99978

[14] H. Jin, M. Mattheakis, and P. Protopapas, “Physics-Informed Neural Networks for
Quantum Eigenvalue Problems,” in *2022 International Joint Conference on Neural
Networks (IJCNN)*, 2022. https://doi.org/10.1109/IJCNN55064.2022.9891944

[15] C. Davis and W. M. Kahan, “The rotation of eigenvectors by a perturbation. III,”
*SIAM Journal on Numerical Analysis*, vol. 7, no. 1, pp. 1–46, 1970.
https://doi.org/10.1137/0707001

# Method and Results Draft

## Problem setting

We consider parameterized two-dimensional Bloch eigenproblems of the form

\[
\left[\frac12(-i\nabla+\mathbf{k})^T G(-i\nabla+\mathbf{k})
+V_{\mu}(\mathbf{x})\right]u_j=E_j u_j,
\qquad \mathbf{x}\in[0,2\pi)^2,
\]

with periodic boundary conditions. Rather than assigning persistent labels to
individual eigenfunctions across an internal eigenvalue crossing, the target is
the rank-two spectral projector associated with the lowest isolated cluster.

## Neural-augmented trial space

An anchored generalized-trace neural network provides a label-free coarse basis
\(Q_\theta(\mu)\in\mathbb{C}^{N\times 2}\). The network receives periodic
coordinate features, the Bloch wavevector, and potential parameters, and is
trained without plane-wave eigenfunction labels. At inference, we augment the
neural basis with all 19 reciprocal modes in the second closed hexagonal shell,

\[
W(\mu)=[Q_\theta(\mu),\Phi_2].
\]

Analytic columns are projected against the neural subspace and numerically
dependent directions are rejected. All retained columns are orthonormalized
under equal-weight periodic-cell quadrature. The procedure operates on subspaces
and is invariant to unitary rotations within the two neural columns.

## Fast Hamiltonian assembly and Ritz extraction

Automatic differentiation is used only for the two neural columns. For a
periodic plane wave \(\phi_m(x)=\exp(i m\cdot x)\), the Hamiltonian image is
assembled analytically as

\[
H_\mu\phi_m=
\left[\frac12(m+k)^T G(m+k)+V_\mu(x)\right]\phi_m.
\]

The complex orthogonalization transform is applied to each pair \((w,Hw)\),
which preserves linearity without differentiating every augmented column. We
then solve the compact Ritz problem in the resulting trial space and map its two
lowest eigenvectors back to the function grid. The method introduces no new
learned parameters and does not access the reference projector at inference.

## Frozen-final results

The one-shot frozen-final evaluation contains 640 parameter points, two
honeycomb potential families, three independently trained checkpoint seeds, ten
methods, and 19,200 paired rows. The proposed full-shell method attains an
overall rank-two projector sine error of 0.04532, compared with 0.14719 for the
time-matched long-anchor network and 0.13697 for a 21-mode Fourier-only control.
The corresponding overall improvement over long-anchor is 69.2%, with a
point-clustered 95% bootstrap interval of [67.7%, 70.8%].

Near the internal crossing, the error decreases from 0.08924 to 0.03903, an
improvement of 56.3% with a 95% interval of [53.2%, 59.2%]. The method wins all
six potential-family-by-checkpoint-seed comparisons. It also remains effective
on exact clusters (0.04220), strict out-of-distribution points (0.05685), and
gap scans (0.04389). The maximum orthogonality error is
\(3.12\times10^{-7}\).

On an RTX 5090 D, the production implementation requires 107.8 ms per parameter
on average (121.9 ms at the 95th percentile), whereas the same-server cutoff-24
CPU plane-wave reference solve requires 313.4 ms on average. These timings place
the method between a one-forward neural surrogate and a high-accuracy direct
eigensolver: it is a hybrid neural numerical solver rather than a cost-free
postprocessor.

## Limitations

The present study is restricted to two periodic honeycomb potentials and a
rank-two low-energy cluster. Rayleigh--Ritz and Fourier trial spaces are prior
numerical tools; the contribution lies in their basis-invariant combination
with a parameterized neural spectral-cluster initializer and in the paired fast
Hamiltonian assembly. A direct reproduction of the closest published neural
subspace Galerkin baseline and an external-gap-based error analysis would
strengthen the theoretical and comparative claims.

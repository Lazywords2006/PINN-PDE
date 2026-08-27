# V3 Method Architecture

## PDE target

The solver approximates the lowest rank-two spectral cluster of

\[
\left[\tfrac12(-i\nabla+\mathbf k)^TG(-i\nabla+\mathbf k)+V_\mu(\mathbf x)\right]u=Eu,
\qquad \mathbf x\in[0,2\pi)^2,
\]

with periodic boundary conditions. Harmonic and Gaussian honeycomb potential families are tested.

## Data flow

```text
periodic coordinates + Bloch vector + potential parameters
                         │
                         ▼
       archived label-free generalized-trace SiLU MLP
       3 hidden layers × width 64, rank-two complex output
                         │
                         ▼
                neural coarse subspace Qθ
                         │
       potential Fourier tail energy outside D6 shell 1
                 ┌───────┴────────┐
          tail ratio ≤ 0.1   tail ratio > 0.1
          tie-closed kinetic  D6 shell 2 ∪ kinetic modes
          Fourier rank ≥ 25   ∪ two neural directions
                 └───────┬────────┘
                         ▼
       paired orthogonalization with detached quadrature norms
       neural H columns: autodiff; Fourier H columns: analytic
                         │
                         ▼
          explicit Hermitian compact Ritz problem
                         │
                         ▼
             lowest rank-two spectral projector
```

## Invariances

- Periodic coordinate encoding enforces coordinate periodicity.
- The scientific target is a subspace, not an ordered pair of eigenfunctions.
- Complex MGS and projector metrics are invariant to column phases and permutations.
- The augmented span is unchanged by a unitary rotation of the rank-two neural basis.
- The same complex transform is applied to each trial/Hamiltonian pair.
- Fourier dictionaries are closed at kinetic-energy ties, so exact D6 multiplets are not cut at an
  arbitrary rank boundary.

## Train and inference separation

Training minimizes `Tr(B^-1 A)` without reference eigenvector labels. V3 reuses audited long-anchor
checkpoints and adds no trainable parameters. Reference PWE projectors are used only for evaluation.
The pilot was used to freeze the route and gate. The formal confirmation suite is procedurally
separate and may never be used for training, tuning, checkpoint selection, or threshold changes.

## Complexity interpretation

For grid size \(N=65^2\), the simple route solves a tie-closed Fourier Ritz problem with rank at
least 25. The rich route evaluates two autodiff neural columns plus a symmetry-consistent analytic
Fourier dictionary and solves a compact rank-about-25 Hermitian problem. A full D6 shell-3 rank-37
solver is the stronger accuracy/cost control. The formal CUDA run reports latency and peak memory;
the current CPU pilot timing is context, not a publication speed claim.

## Scientific novelty boundary

Rayleigh–Ritz, Galerkin projection, Fourier bases, Ky Fan trace, spectral projectors, and
Gram–Schmidt are established tools. The candidate contribution is the label-free parametric neural
coarse space combined with a D6-consistent, tie-closed dictionary and a label-free spectral-tail
router for internally crossing Bloch clusters. Publication claims remain conditional on the frozen
CUDA confirmation and must not call any established component a new invention.

# Current Method Architecture

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
       anchored generalized-trace SiLU MLP
       3 hidden layers × width 64, rank-two complex output
                         │
                         ▼
                neural coarse subspace Qθ
                         │
            + 19 complete shell-2 plane waves
                         │
                         ▼
           paired orthogonalization of (W, HW)
       neural H columns: autodiff; Fourier H columns: analytic
                         │
                         ▼
             compact ≈21D Hermitian Ritz problem
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

## Train and inference separation

Training minimizes `Tr(B^-1 A)` without reference eigenvector labels. The final P2 method reuses
audited long-anchor checkpoints and adds no trainable parameters. Reference PWE projectors are used
only for evaluation. The frozen final may never be used for training or model selection.

## Complexity interpretation

For trial rank \(r\approx21\) and grid size \(N=33^2\), P2 evaluates two autodiff Hamiltonian
columns, 19 analytic columns, orthogonalizes the trial space, and solves an \(r\times r\) Hermitian
problem. The compact solve is negligible compared with high-cutoff PWE, while the neural/Fourier
assembly is more expensive than a single network forward pass.

## Scientific novelty boundary

Rayleigh–Ritz, Galerkin projection, Fourier bases, Ky Fan trace, spectral projectors, and
Gram–Schmidt are established tools. The paper contribution is their basis-invariant combination for
a parameterized internally crossing Bloch cluster, the analytic paired assembly, and the controlled
frozen evaluation.

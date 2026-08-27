# Draft Cover Letter

Dear Editor,

Please consider our manuscript, **“Spectral-Complexity-Gated Neural Augmentation for Parametric
Bloch Spectral Clusters with Band Crossings,”** for publication in *Numerical Methods for Partial
Differential Equations*.

The manuscript studies repeated solution of a two-dimensional parameterized periodic
Bloch–Schrödinger eigenvalue PDE. Internal band crossings make individually ordered eigenfunctions
an unstable learning target, so the method predicts the lowest rank-two spectral projector. Our
SR-SC-NARR solver combines a label-free generalized-trace neural coarse space with
symmetry-consistent, tie-closed Fourier trial spaces and a potential-only spectral-tail diagnostic.
The final cluster is extracted by an explicitly Hermitian compact Rayleigh–Ritz solve.

The evidence is based on a single procedurally frozen CUDA confirmation containing 160 physical
parameter points, two potential families, five parameter regimes, three archived checkpoint seeds,
11 methods and ablations, and 5,280 paired evaluations. Relative to a minimum-rank-25 kinetic
Fourier control, mean projector error decreases by 28.76%, with a family-by-split stratified
point-bootstrap 95% interval of [28.08%, 29.44%]. The gain is reported conditionally: harmonic
cases fall back to Fourier, while localized Gaussian cases obtain the neural improvement. Relative
to a complete rank-37 D6 shell, the method provides a lower-rank Pareto trade-off rather than an
unconditional accuracy claim. Independent cutoff and grid convergence checks, raw Hermiticity,
external-gap, orthogonality, latency, peak-memory, and complete provenance are reported.

We believe the manuscript fits the journal because it develops and evaluates a learning-augmented
numerical method for a parameterized PDE eigenproblem, with explicit attention to variational
structure, spectral approximation, stability, convergence, and reproducibility. The manuscript is
original, is not under consideration elsewhere, and uses no human participants, animals, personal
data, or clinical information. Formula-level adaptations of neighboring methods are clearly
identified as adaptations rather than official author-code reproductions.

The code, frozen benchmarks, raw data, figure scripts, and SHA-256-bound evidence are prepared for
release. Author names, affiliations, funding, conflicts of interest, and the corresponding-author
details will be entered after final confirmation by all authors.

Thank you for your consideration.

Sincerely,

**[Corresponding Author]**
**[Affiliation]**
**[Email]**

# Cover Letter

27 August 2026

Editor-in-Chief  
*Numerical Methods for Partial Differential Equations*

Dear Editor,

Please consider our original research manuscript, “A Basis-Invariant Neural-Augmented
Rayleigh–Ritz Solver for Parametric Bloch Spectral Clusters with Eigenvalue Crossings,” for
publication in *Numerical Methods for Partial Differential Equations*.

The manuscript develops a label-free neural numerical method for a family of two-dimensional
periodic Bloch–Schrödinger eigenproblems. Instead of tracking individually ordered eigenfunctions
through internal crossings, the method predicts a rank-two neural coarse space, augments it with a
closed hexagonal Fourier shell, applies paired orthogonalization to trial functions and their
Hamiltonian images, and extracts the target cluster through a compact Rayleigh–Ritz solve.

The study fits the journal’s scope in parameterized PDEs and learning algorithms for numerical PDE
solutions. It also provides an external-gap residual bound, a complexity and amortization analysis,
and controlled comparisons against neural, Fourier-only, and journal-method adaptations.

The one-shot frozen evaluation contains 640 parameter points, two potential families, three
checkpoint seeds, ten methods, and 19,200 paired rows. The proposed solver reduces overall
projector error from 0.14719 for the strongest pure-neural baseline to 0.04532. A separate
160-point journal-baseline supplement confirms a 63.78% improvement over a parameter-matched
Wang–Xie trace adaptation, with a point-clustered 95% confidence interval of
[59.58%, 67.88%]. All frozen evidence packages were independently verified using SHA-256
manifests and local recomputation.

This manuscript is original, has not been published, and is not under consideration elsewhere.
All authors will approve the submitted version. The study involves no human participants, animals,
or personal data. Code, frozen benchmarks, result tables, and evidence hashes will be made
available through the project repository.

Thank you for considering this work.

Sincerely,

[Corresponding Author Name]  
[Department and Institution]  
[Postal Address]  
[Email]  
[ORCID]

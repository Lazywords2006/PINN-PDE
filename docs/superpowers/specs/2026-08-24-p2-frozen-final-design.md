# P2 Frozen Final Evaluation Design

## Authorization

The independent P2 full-shell pilot passed every frozen gate and was independently
recomputed byte-for-byte from its evidence archive.  Its approved evidence SHA is
`0c49461a6c780840ca678582019cc433df5741fd62ef546dcde7e964b71c071b`.
This authorizes one evaluation of the pre-existing 640-point V2 frozen final
suite.  Final parameters or references remain forbidden for any tuning.

## Suite and Methods

Use `benchmarks/v2_frozen_test.json` and its existing SHA sidecar.  The suite has
two potential families and IID, exact-cluster, near-cluster, strict-OOD, and
gap-scan splits.  Evaluate seeds 42, 137, and 251 for:

1. unanchored generalized-trace neural solver;
2. anchor neural solver;
3. width-matched anchor;
4. time-matched long-anchor;
5. static low-ROM;
6. high-frequency ROM control;
7. P2 shell-one neural-Galerkin ablation;
8. P2 outer-shell-two ablation;
9. P2 full-shell-two primary;
10. equal-rank Fourier-only Galerkin control.

Direct cutoff-24 PWE is the reference and numerical timing comparator.

## Frozen Claims

Final support for the primary method requires:

- near error at least 5% below long-anchor;
- gap error no more than 2% above the best non-reference neural baseline;
- both potential families improve and at least 5/6 family-seed pairs win;
- overall error at least 5% below long-anchor;
- primary error below Fourier-only and every P5 neural baseline;
- maximum orthogonality error below `1e-4`;
- all 19,200 rows present, finite, unique, and identically paired;
- point-clustered 95% bootstrap confidence interval for overall and near
  improvement has a lower bound above zero;
- source, checkpoints, suite, cache, pilot evidence, environment, units, and
  evidence manifest pass independent audit.

No threshold is changed after final output.  A final STOP is preserved and ends
the current paper claim.  A final GO authorizes paper tables and figures, not
additional final tuning.

## Statistics and Figures

Bootstrap parameter points as clusters, keeping all three checkpoint seeds for
each sampled point.  Use 2,000 deterministic bootstrap samples.  Report mean,
standard deviation across seeds, improvement percentage, CI, split/family
tables, absolute-error CDF, near/gap paired plots, error heat maps, latency,
memory, and direct-PWE break-even.

## Safety

The evaluator must verify the approved pilot archive and stored `pilot_go=true`,
require a clean exact commit, create a one-shot marker before reading final
references, and refuse rerun if final rows or gate already exist.  It must not
write optimizer state, train a model, or expose final errors to any other script.

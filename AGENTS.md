# Repository guardrails

This is a scientific-computing repository with a completed one-shot final evaluation.

- Canonical status: `docs/CURRENT-STATUS.zh-CN.md`.
- Canonical numeric summary: `paper/p2_final/CORE_RESULTS.zh-CN.md`.
- Current method: basis-invariant neural-augmented Rayleigh–Ritz with the complete second
  hexagonal shell.
- Final status: `P2_FROZEN_FINAL_GO`.
- Supplement status: `Q3_SUPPLEMENT_GO`; evidence SHA-256
  `282cdd418eaa11a68498ee7fbc0198dfc1f362a535385756a7cc38275806afe0`.
- `benchmarks/v2_frozen_test.json` and its references are permanently closed to training,
  tuning, checkpoint selection, and reruns.
- `benchmarks/q3_supplement_v1.json` has already been used for one formal comparison and is now
  closed to tuning or method changes.
- Formula-level `wang_xie_trace` and `dai_galerkin` supplement results are not official
  author-code reproductions.
- Keep smoke, validation, frozen final, and planned experiments clearly separated.
- Preserve source, suite, cache, checkpoint, RNG, manifest, and SHA-256 provenance.
- Generated data, checkpoints, and large results belong in ignored `data/` or `results/` paths.
- Run `python -m pytest -q` before committing Python changes.
- Documentation cleanup may remove completed execution prompts, but must not remove archived
  negative-result evidence.

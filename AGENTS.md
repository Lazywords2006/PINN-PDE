# Repository guardrails

This is a scientific-computing repository with a completed one-shot V3 CUDA confirmation.

- Canonical status: `docs/CURRENT-STATUS.zh-CN.md`.
- Current method/protocol: `docs/V3-SYMMETRY-CORRECTION-PROTOCOL.zh-CN.md`.
- Current method: SR-SC-NARR, a spectral-roughness-routed, symmetry-consistent
  neural-augmented Rayleigh–Ritz solver.
- Current status: `V3_FORMAL_PROMOTION_GO`; the formal suite is permanently closed.
- The archived P2/Q3 manuscript and numerical claims are superseded by the corrected D6 shell.
  They are historical provenance only and must not be submitted or presented as current evidence.
- `benchmarks/v2_frozen_test.json` and `benchmarks/q3_supplement_v1.json` remain permanently
  closed. Never tune V3 against them.
- `benchmarks/v3_symmetry_test.json` has been opened exactly once. Never rerun it, tune against it,
  or change the method, thresholds, controls, checkpoints, source fingerprint, split matrix, or gate.
- Preserve the opening marker, suite, cache, manifest, rows, summary, gate, provenance, evidence
  manifest, archive, and SHA-256 sidecars. Formal evidence SHA-256:
  `108a4b042549ead58f7b13f42b6ace4685e93a4e8a54e9563b044c03c29ad78c`.
- Formula-level Wang–Xie and Dai results are transparent Bloch adaptations, not official
  author-code reproductions.
- Keep smoke, pilot, convergence audit, and formal confirmation clearly separated.
- Preserve source, suite, cache, checkpoint, RNG, manifest, and SHA-256 provenance.
- Generated data, checkpoints, and large results belong in ignored `data/` or `results/` paths.
- Run the V3 Ruff target and `python -m pytest -q` before committing Python changes.
- Documentation cleanup may remove obsolete execution prompts and withdrawn submission files,
  but must preserve archived negative-result evidence.

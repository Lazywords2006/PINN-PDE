# Repository guardrails

This is a scientific-computing repository. Preserve the distinction between
engineering smoke tests, the V2 validation pilot, and the frozen V2 final test.

- Do not use `benchmarks/v2_frozen_test.json` for training, tuning, or pilot decisions.
- Do not run `scripts/evaluate_v2_final.py` unless the recomputed 24-run pilot gate is GO.
- Do not describe smoke or unrun GPU experiments as paper results.
- Do not edit frozen suite JSON or SHA-256 files by hand; regenerate them with
  `scripts/generate_v2_assets.py --suites-only`.
- Keep reference cutoff 24 unless a new, stricter convergence audit justifies a change.
- Preserve checkpoint, source, suite, cache, and RNG provenance bindings.
- Use `python -m pytest -q` before committing Python changes.
- Generated data, checkpoints, and results belong in ignored `data/` and `results/`.

Operational instructions are in `docs/RUNBOOK.md`; unresolved scientific work is
tracked in `docs/KNOWN_GAPS.zh-CN.md`.

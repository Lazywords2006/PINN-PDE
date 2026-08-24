# Reproduction and SCI-Q3 Supplement Runbook

## 1. Current rule

The P2 frozen final and Q3 supplement are complete and permanently closed. Do not run
`scripts/evaluate_p2_final.py` or rerun `q3_supplement_v1` after changing methods or gates. The
commands below are for code verification, evidence auditing, and figure regeneration.

## 2. Local verification

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -q
```

Device preflight:

```bash
python scripts/preflight_accelerator.py --backend cuda
```

Use `mps` or `rocm` only when that backend is actually available. MPS smoke tests are engineering
checks and cannot replace the archived CUDA paper results.

## 3. Verify returned final evidence without rerunning it

```bash
shasum -a 256 -c \
  results/remote_5090_p2_final_go/p2-final-evidence-20260824-133520.tar.gz.sha256

jq . results/remote_5090_p2_final_go/results/p2_final/gate.json
jq . results/remote_5090_p2_final_go/results/p2_final/summary.json
```

Expected final evidence SHA-256:

```text
c653d0eddab018741312741f6db46f023a20812306d574b66947bbb42af25095
```

## 4. Regenerate publication figures

```bash
python scripts/generate_p2_paper_figures.py
```

The generator validates the final evidence digest, GO gate, 19,200-row identity matrix, method
counts, suite/reference/pilot hashes, and numeric aggregates before plotting. Do not bypass these
checks to produce a prettier figure.

## 5. Completed SCI-Q3 supplement

The supplement ran on 2026-08-25 and returned `Q3_SUPPLEMENT_GO`. Protocol and results:

- `docs/Q3-SUPPLEMENT-PROTOCOL.zh-CN.md`;
- `paper/p2_final/Q3_SUPPLEMENT_REPORT.zh-CN.md`;
- `benchmarks/q3_supplement_v1.json`;
- local evidence: `results/remote_5090_q3_supplement_go/`.

The executed sequence was:

1. write a new protocol and success criteria;
2. generate a disjoint supplementary parameter suite and SHA-256 sidecar;
3. implement and document a faithful Dai-style neural-subspace Galerkin baseline;
4. implement and document a Wang–Xie trace baseline, including every Bloch-specific adaptation;
5. run a small smoke, then a 3-seed pilot;
6. compare parameter counts, training budget, wall time, peak memory, and identical test points;
7. package rows, summaries, environment, source fingerprint, manifest, and outer SHA-256;
8. report the positive result without changing the frozen main table.

The legacy `sci3_*` configs remain retired. The completed supplement uses
`scripts/generate_q3_supplement.py` and `scripts/run_q3_supplement.py`.

Audit a returned archive without running experiments:

```bash
python scripts/run_q3_supplement.py \
  --audit-evidence results/remote_5090_q3_supplement_go/q3-supplement-evidence-20260824-170904.tar.gz
```

## 6. Hardware

- Documentation, theory, audit, and plotting: local CPU/Mac, no rented GPU.
- Completed nearest-neighbor supplement: one RTX 5090 D 32 GB; wall time about 64 minutes.
- A third potential family or same-device PWE timing may add 6–12 hours.
- Multi-GPU training is unnecessary.

## 7. Failure handling

- Non-finite loss or rank deficiency: preserve traceback and exact config; stop that run.
- Suite/cache/source hash mismatch: do not resume across revisions.
- Nearest journal baseline wins: retain the result and narrow the paper claim.
- Supplement does not pass its preregistered gate: do not modify the main frozen evidence.
- CUDA results disagree with archived values: investigate environment and evidence bindings; never
  overwrite the archive.

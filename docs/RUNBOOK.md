# V3 Verification and Formal-Confirmation Runbook

## 1. Current rule

P2 and Q3 are superseded historical evidence. Do not run `scripts/evaluate_p2_final.py`, reopen
`v2_frozen_test`, or rerun `q3_supplement_v1`. V3 pilot and convergence evidence have passed. The
only remaining main experiment is one procedurally frozen 160-point CUDA confirmation. Generate the
formal suite only after the V3 freeze commit has been pushed.

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

Use `mps` or `rocm` only for engineering checks. They cannot replace the V3 CUDA confirmation.

## 3. Verify the current V3 pilot and convergence evidence

```bash
shasum -a 256 -c benchmarks/v3_symmetry_pilot.sha256
shasum -a 256 -c benchmarks/v3_symmetry_convergence_audit.sha256
shasum -a 256 -c benchmarks/v3_symmetry_convergence_audit-evidence.tar.gz.sha256
jq .gate benchmarks/v3_symmetry_convergence_audit.json
jq . paper/v3_pilot/gate.json
```

Current evidence SHA-256:

```text
pilot bundle: e9f3047ebb0aaf8bd89202de95544d1b8b6a0a6b62fe8a2427ac80d78fffa5b4
convergence JSON: b2a104f7dde8e506b9446634af6d716c00c8317adb2d6fa5c8f1484e4cf0e0f2
convergence bundle: 1df60548ddf9a6cb124d7f50285f51560ee00bf811721ffac870102398a47616
```

## 4. Generate the formal suite after the freeze commit

```bash
python scripts/generate_v3_symmetry_assets.py --emit-test --build-cache test
```

Commit and push `benchmarks/v3_symmetry_test.json`, its sidecar, the formal manifest, the reference
cache, and its sidecar without changing source code. The generator binds the suite, 160-point digest,
source fingerprint, reference cache, and convergence audit.

Frozen formal-input hashes:

```text
suite:     cf834352157fbe298bb511cb7ab8e325471473fde0a0f2824f2c31e35b4f7571
reference: 19ef0364cdb0b0407ef2fa3c6880268690ddaf7d46b82b43d50b0a6bce51b36e
point set: 96ed54c912780fd3c23ee35b7ab622367692ccc799d2182a5fb38f4eda540e3e
```

## 5. Run the single formal CUDA confirmation

```bash
python scripts/run_v3_symmetry_evaluation.py \
  --suite benchmarks/v3_symmetry_test.json \
  --reference-cache data/v3_symmetry_test_references.pt \
  --p5-archive artifacts/p5-evidence-20260801-092048.tar.gz \
  --checkpoint-inventory results/p1_smoke/checkpoint_inventory.json \
  --q3-training-root results/remote_5090_q3_supplement_go/q3_supplement_formal/training \
  --q3-evidence results/remote_5090_q3_supplement_go/q3-supplement-evidence-20260824-170904.tar.gz \
  --output-dir results/v3_symmetry_formal \
  --formal \
  --formal-manifest benchmarks/v3_symmetry_test.manifest.json \
  --convergence-audit benchmarks/v3_symmetry_convergence_audit.json \
  --device cuda
```

The command refuses a dirty checkout, non-CUDA device, wrong source fingerprint, wrong suite digest,
wrong P5/Q3 evidence, stale convergence audit, an existing output, or a second formal opening.

## 6. Hardware

- Local CPU/Mac: tests, pilot, convergence audit, reference generation, writing, and plotting.
- Formal run: one NVIDIA CUDA GPU. RTX 4060 is feasible; RTX 4090/5090 shortens the wall time.
- Recommended rental: one RTX 5090/5090 D with at least 32 GB system disk and 50 GB data disk.
- Multi-GPU training is unnecessary; the protocol is single-GPU by design.

## 7. Failure handling

- Non-finite loss or rank deficiency: preserve traceback and exact config; stop that run.
- Suite/cache/source hash mismatch: do not resume across revisions.
- Nearest journal baseline or Fourier-25 wins: retain the result and narrow or stop the neural claim.
- Formal gate fails: do not change thresholds or reopen the confirmation suite.
- CUDA results disagree with the pilot: preserve both and diagnose; never overwrite either archive.
- A crash after the global opening marker is an audited failed opening, not permission to silently
  rerun the test.

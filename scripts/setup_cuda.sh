#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
TORCH_VERSION="${TORCH_VERSION:-2.8.0}"
TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu128}"
MIN_VRAM_GB="${MIN_VRAM_GB:-8}"
SMOKE_STEPS="${SMOKE_STEPS:-5}"
SMOKE_POINTS="${SMOKE_POINTS:-64}"

"$PYTHON_BIN" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install "torch==$TORCH_VERSION" --index-url "$TORCH_INDEX_URL"
python -m pip install -r requirements-core.txt

PREFLIGHT_ARGS=(
  --backend cuda
  --min-vram-gb "$MIN_VRAM_GB"
  --output results/preflight/cuda.json
)
if [[ -n "${EXPECTED_GPU_NAME:-}" ]]; then
  PREFLIGHT_ARGS+=(--expected-name "$EXPECTED_GPU_NAME")
fi
python scripts/preflight_accelerator.py "${PREFLIGHT_ARGS[@]}"
python -m pytest -q
python run_smoke.py \
  --device cuda \
  --steps "$SMOKE_STEPS" \
  --points "$SMOKE_POINTS" \
  --output results/smoke/cuda_smoke.json

echo "CUDA_ENGINEERING_VALIDATION=PASS"
echo "Formal V2 paper experiments were not started by this setup script."

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv-rocm}"
MIN_VRAM_GB="${MIN_VRAM_GB:-8}"
SMOKE_STEPS="${SMOKE_STEPS:-5}"
SMOKE_POINTS="${SMOKE_POINTS:-64}"

# ROCm wheels are tied to the host driver/image. Reuse the image's tested
# PyTorch build instead of allowing PyPI to replace it with a CUDA/CPU wheel.
"$PYTHON_BIN" - <<'PY'
import torch

assert torch.cuda.is_available(), "the image's ROCm accelerator is unavailable"
assert getattr(torch.version, "hip", None), "the image does not contain a ROCm PyTorch build"
print(f"BASE_TORCH={torch.__version__}")
print(f"BASE_ROCM={torch.version.hip}")
print(f"BASE_GPU={torch.cuda.get_device_name(0)}")
PY

if [[ ! -e "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv --system-site-packages "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r requirements-core.txt

python - <<'PY'
import torch

assert torch.cuda.is_available(), "ROCm became unavailable inside the virtual environment"
assert getattr(torch.version, "hip", None), (
    "the virtual environment is not using the image's ROCm PyTorch; "
    "choose a new VENV_DIR and rerun"
)
PY

PREFLIGHT_ARGS=(
  --backend rocm
  --min-vram-gb "$MIN_VRAM_GB"
  --output results/preflight/rocm.json
)
if [[ -n "${EXPECTED_GPU_NAME:-}" ]]; then
  PREFLIGHT_ARGS+=(--expected-name "$EXPECTED_GPU_NAME")
fi
python scripts/preflight_accelerator.py "${PREFLIGHT_ARGS[@]}"
python -m pytest -q
python run_smoke.py \
  --device rocm \
  --steps "$SMOKE_STEPS" \
  --points "$SMOKE_POINTS" \
  --output results/smoke/rocm_smoke.json

echo "ROCM_ENGINEERING_VALIDATION=PASS"
echo "Formal V2 paper experiments were not started by this setup script."

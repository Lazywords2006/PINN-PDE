#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r requirements.txt

python - <<'PY'
import torch

assert torch.cuda.is_available(), "CUDA is unavailable"
name = torch.cuda.get_device_name(0)
memory_gb = torch.cuda.get_device_properties(0).total_memory / 2**30
capability = torch.cuda.get_device_capability(0)
print(f"GPU={name}")
print(f"VRAM_GB={memory_gb:.2f}")
print(f"CUDA={torch.version.cuda}")
print(f"CAPABILITY={capability}")
assert "5090" in name, f"expected RTX 5090, got {name}"
assert memory_gb >= 30.0, f"expected at least 30GB VRAM, got {memory_gb:.2f}"
x = torch.randn(256, 256, device="cuda", requires_grad=True)
(x.square().mean()).backward()
torch.cuda.synchronize()
print("RTX5090_PREFLIGHT=PASS")
PY

python -m pytest -q
python run_all.py --smoke

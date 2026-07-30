#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_GPU_NAME="5090" MIN_VRAM_GB="30" bash "$ROOT_DIR/scripts/setup_cuda.sh"

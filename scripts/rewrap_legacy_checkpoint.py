"""Create an explicit provenance wrapper for pre-fingerprint checkpoints.

The source checkpoint is never modified.  The wrapper records its SHA-256 and
marks the missing original fingerprint instead of pretending that the legacy
run used the current checkpoint protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    state = torch.load(args.source, map_location="cpu", weights_only=False)
    if "model" not in state or not isinstance(state.get("config"), dict) or "seed" not in state:
        raise ValueError("legacy checkpoint is missing model, config, or seed")
    if state.get("config_fingerprint") is not None:
        raise ValueError("source already has a config fingerprint; no wrapper is needed")
    config_fingerprint = hashlib.sha256(
        json.dumps(state["config"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    wrapped = {
        **state,
        "config_fingerprint": config_fingerprint,
        "source_fingerprint": None,
        "legacy_provenance": {
            "status": "LEGACY_REWRAPPED_NO_ORIGINAL_CONFIG_OR_SOURCE_FINGERPRINT",
            "source_checkpoint": str(args.source),
            "source_checkpoint_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(wrapped, args.output)
    print(json.dumps({"output": str(args.output), "config_fingerprint": config_fingerprint}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

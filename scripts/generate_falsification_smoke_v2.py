"""Generate the small V2 falsification suite used before new GPU training.

This suite is intentionally not the final test set.  It exists to decide
whether the corrected scientific direction deserves a full formal matrix.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from block_kyfan_pinn.protocol import (
    annotate_spectral_gaps,
    build_falsification_smoke_points,
    validate_falsification_points,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "benchmarks" / "falsification_smoke_v2.json",
    )
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument("--reference-cutoff", type=int, default=6)
    args = parser.parse_args()

    points = annotate_spectral_gaps(
        build_falsification_smoke_points(seed=args.seed), cutoff=args.reference_cutoff
    )
    errors = validate_falsification_points(points)
    if errors:
        raise ValueError("invalid V2 falsification suite:\n" + "\n".join(errors))
    payload = {
        "suite_id": "block_kyfan_falsification_smoke_v2",
        "status": "SMOKE_ONLY_NOT_FINAL_TEST",
        "seed": args.seed,
        "reference_cutoff_for_gap_screen": args.reference_cutoff,
        "v1_replacement_reason": (
            "V1 OOD overlapped the training box and V1 near-crossing labels were geometric rather "
            "than spectrum-screened."
        ),
        "point_count": len(points),
        "points": points,
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    digest = hashlib.sha256(body.encode()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(body, encoding="utf-8")
    args.output.with_suffix(".sha256").write_text(f"{digest}  {args.output.name}\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS",
                "suite": str(args.output),
                "sha256": digest,
                "point_count": len(points),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

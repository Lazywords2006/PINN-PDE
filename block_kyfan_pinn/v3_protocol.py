"""Frozen identifiers for the V3 symmetry-corrected confirmation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

V3_FORMAL_SEED = 20260917
V3_FORMAL_SUITE_ID = f"block-kyfan-v3-symmetry-confirm-{V3_FORMAL_SEED}"
V3_FORMAL_PURPOSE = "post_correction_procedurally_frozen_confirmation"
V3_MODE_POLICY = "positive_cross_metric_d6_closure"
V3_GLOBAL_OPENING_MARKER = "V3_CONFIRMATION_OPENED.json"
V3_FORMAL_POINT_DIGEST = (
    "96ed54c912780fd3c23ee35b7ab622367692ccc799d2182a5fb38f4eda540e3e"
)
V3_FORMAL_SPLIT_COUNTS = {
    "iid_hidden": 32,
    "exact_cluster": 32,
    "near_cluster": 48,
    "strict_ood": 32,
    "gap_scan": 16,
}


def physical_point_digest(points: Sequence[dict[str, object]]) -> str:
    """Hash sorted family/split/parameter identities independently of point IDs."""

    identities = sorted(
        (
            str(point["family"]),
            str(point["split"]),
            [format(float(value), ".17g") for value in point["parameters"]],
        )
        for point in points
    )
    payload = json.dumps(
        identities, ensure_ascii=False, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()

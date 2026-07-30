"""Frozen-suite serialization, validation, and SHA-256 binding."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def validate_suite_payload(
    payload: dict[str, object], *, protocol_version: int | None = 2
) -> list[dict[str, object]]:
    """Validate metadata, identities, and numeric integrity of a frozen suite."""

    raw_points = payload.get("points")
    if not isinstance(raw_points, list) or not raw_points:
        raise ValueError("suite points must be a non-empty list")
    if int(payload.get("point_count", -1)) != len(raw_points):
        raise ValueError("suite point_count does not match points")

    points: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in raw_points:
        if not isinstance(raw, dict):
            raise ValueError("each suite point must be an object")
        identity = str(raw.get("id", ""))
        if not identity or identity in seen:
            raise ValueError(f"suite point id is empty or duplicated: {identity!r}")
        seen.add(identity)
        if not str(raw.get("family", "")) or not str(raw.get("split", "")):
            raise ValueError(f"suite point {identity} is missing family or split")
        parameters = raw.get("parameters")
        if not isinstance(parameters, list) or not parameters:
            raise ValueError(f"suite point {identity} has invalid parameters")
        if not all(math.isfinite(float(value)) for value in parameters):
            raise ValueError(f"suite point {identity} has non-finite parameters")
        points.append(raw)

    # Validate identities before metadata so a malformed or duplicated point
    # cannot be hidden behind an unrelated wrapper error.
    suite_id = payload.get("suite_id")
    if not isinstance(suite_id, str) or not suite_id:
        raise ValueError("suite_id must be a non-empty string")
    if (
        protocol_version is not None
        and int(payload.get("protocol_version", -1)) != protocol_version
    ):
        raise ValueError(f"protocol_version must be {protocol_version}")
    return points


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of the exact bytes stored at ``path``."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_frozen_suite(payload: dict[str, object], path: Path) -> str:
    """Write one validated suite and a conventional raw-file SHA-256 sidecar."""

    validate_suite_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    digest = file_sha256(path)
    path.with_suffix(".sha256").write_text(f"{digest}  {path.name}\n")
    return digest


def load_frozen_suite(
    path: Path, *, verify_sha256: bool = True
) -> tuple[dict[str, object], str]:
    """Load a suite, validate its schema, and optionally verify its sidecar."""

    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("frozen suite root must be an object")
    validate_suite_payload(payload)
    digest = file_sha256(path)
    if verify_sha256:
        sidecar = path.with_suffix(".sha256")
        if not sidecar.is_file():
            raise FileNotFoundError(f"missing suite SHA-256 sidecar: {sidecar}")
        declared = sidecar.read_text().strip().split()[0]
        if declared != digest:
            raise ValueError(
                f"suite SHA-256 mismatch: declared {declared}, computed {digest}"
            )
    return payload, digest

#!/usr/bin/env python3
"""Evaluate held-out label-free risk features from audited P5 checkpoints."""

from __future__ import annotations

import hashlib
import json
import sys
import tarfile
from collections import Counter
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.audit_p5_evidence import audit_p5_evidence

EXPECTED_P5_ARCHIVE_SHA256 = (
    "56891c5740eb94c62299b72869d790a1cbdee6abda3fae2903ed822f5e405101"
)
RISK_METHODS = ("p5_anchor", "p5_static_low_rom")
RISK_FAMILIES = ("harmonic_honeycomb", "gaussian_honeycomb")
RISK_SEEDS = (42, 137, 251)


def _member_is_safe(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def _read_member(
    archive: tarfile.TarFile,
    members: dict[str, tarfile.TarInfo],
    name: str,
) -> bytes:
    member = members.get(name)
    if member is None or not member.isfile():
        raise ValueError(f"missing evidence member: {name}")
    handle = archive.extractfile(member)
    if handle is None:
        raise ValueError(f"unreadable evidence member: {name}")
    return handle.read()


def inventory_p5_checkpoints(
    archive_path: Path, sidecar_path: Path
) -> list[dict[str, object]]:
    """Return only the 12 paired final checkpoints after full P5 audit."""

    report = audit_p5_evidence(archive_path, sidecar_path)
    if report.get("audit_pass") is not True:
        raise ValueError("P5 evidence audit failed")
    if report.get("archive_sha256") != EXPECTED_P5_ARCHIVE_SHA256:
        raise ValueError("P5 evidence archive SHA-256 is not the approved digest")

    rows: list[dict[str, object]] = []
    with tarfile.open(archive_path, "r:gz") as archive:
        all_members = archive.getmembers()
        names = [member.name for member in all_members]
        duplicates = [name for name, count in Counter(names).items() if count > 1]
        unsafe = [name for name in names if not _member_is_safe(name)]
        if duplicates or unsafe:
            raise ValueError("P5 archive contains duplicate or unsafe paths")
        members = {member.name: member for member in all_members}
        result_names = sorted(
            name
            for name, member in members.items()
            if member.isfile()
            and name.startswith("results/p5_promotion/")
            and name.endswith("/result.json")
        )
        for result_member in result_names:
            result = json.loads(
                _read_member(archive, members, result_member).decode("utf-8")
            )
            config = result.get("config")
            if not isinstance(config, dict):
                raise ValueError(f"missing P5 config: {result_member}")
            method = str(config.get("method"))
            if method not in RISK_METHODS:
                continue
            family = str(config.get("potential_family"))
            seed = int(config.get("seed", -1))
            if family not in RISK_FAMILIES or seed not in RISK_SEEDS:
                raise ValueError(f"unexpected risk checkpoint identity: {config}")
            run_root = result_member.rsplit("/", 1)[0]
            checkpoint_member = f"{run_root}/final.pt"
            checkpoint_bytes = _read_member(
                archive, members, checkpoint_member
            )
            checkpoint_hash = hashlib.sha256(checkpoint_bytes).hexdigest()
            if checkpoint_hash != result.get("final_checkpoint_sha256"):
                raise ValueError(
                    f"final checkpoint hash mismatch: {checkpoint_member}"
                )
            if result.get("status") != "PASS":
                raise ValueError(f"P5 run is not complete: {run_root}")
            rows.append(
                {
                    "method": method,
                    "family": family,
                    "seed": seed,
                    "checkpoint_member": checkpoint_member,
                    "result_member": result_member,
                    "checkpoint_sha256": checkpoint_hash,
                    "config": config,
                }
            )

    expected = {
        (method, family, seed)
        for method in RISK_METHODS
        for family in RISK_FAMILIES
        for seed in RISK_SEEDS
    }
    actual = {
        (row["method"], row["family"], row["seed"]) for row in rows
    }
    if len(rows) != 12 or actual != expected:
        raise ValueError("P5 risk checkpoint inventory is incomplete")
    return sorted(
        rows,
        key=lambda row: (str(row["method"]), str(row["family"]), int(row["seed"])),
    )

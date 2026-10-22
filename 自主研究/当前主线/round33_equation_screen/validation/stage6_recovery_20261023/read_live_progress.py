"""Lightweight orphan progress: identity queries and checkpoint stat only.

This does not validate scientific results or authorize recovery. The original
observer's closed journal remains the authoritative exit evidence for the gate.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import msvcrt
import os
from pathlib import Path
import time

from observe_orphan_exits import WindowsQuery


def read_shared(path):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(path), 0x80000000, 7, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    with os.fdopen(fd, "rb") as stream:
        return stream.read()


def memory_snapshot():
    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in
            ("total_physical", "free_physical", "total_commit", "free_commit",
             "total_virtual", "free_virtual", "free_extended")]
    status = Memory()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError()
    return {"available_physical_gib": status.free_physical / 2**30,
            "available_commit_gib": status.free_commit / 2**30,
            "commit_used_fraction": 1 - status.free_commit / status.total_commit}


def snapshot(runtime):
    observer = runtime / "orphan_observer_20261023_0138"
    attached = json.loads(read_shared(observer / "attached.json").decode("utf-8-sig"))
    raw = read_shared(observer / "events.jsonl")
    # A trailing partial append is not treated as a complete event.
    lines = raw.split(b"\n")
    events = [json.loads(line) for line in lines[:-1] if line.strip()]
    exits = [item for item in events if item["event"] == "process_exited"]
    api = WindowsQuery()
    rows = []
    for expected in attached["processes"]:
        if expected["role"] != "worker":
            continue
        row = {"job": expected["job"], "pid": expected["pid"]}
        handle = None
        try:
            handle = api.open(expected["pid"])
            times = [wintypes.FILETIME() for _ in range(4)]
            if not api.kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                raise ctypes.WinError(ctypes.get_last_error())
            ticks = [(t.dwHighDateTime << 32) | t.dwLowDateTime for t in times]
            row["creation_matches_attached"] = ticks[0] == expected["creation_filetime_utc"]
            row["handle_wait_status"] = api.kernel.WaitForSingleObject(handle, 0)
            row["running_identity_verified"] = (row["creation_matches_attached"] and
                                                  row["handle_wait_status"] == 258)
            row["cumulative_cpu_seconds"] = (ticks[2] + ticks[3]) / 1e7
        except OSError as exc:
            row["query_error"] = repr(exc)
            row["running_identity_verified"] = False
        finally:
            if handle is not None:
                api.kernel.CloseHandle(handle)
        tag, eq, method, seed = expected["job"]
        path = runtime / "checkpoints" / f"{tag}__{eq}__{method.replace('+', '_')}_s{seed}.ckpt"
        try:
            stat = path.stat()  # Never open or deserialize a live checkpoint.
            row.update(checkpoint_mtime=stat.st_mtime, checkpoint_size=stat.st_size,
                       checkpoint_age_seconds=max(0, time.time() - stat.st_mtime))
        except FileNotFoundError:
            row["checkpoint_missing"] = True
        rows.append(row)
    ages = [r["checkpoint_age_seconds"] for r in rows if "checkpoint_age_seconds" in r]
    return {"observed_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "live_identity_and_metadata_only_not_scientific_acceptance_or_dispatch_authority",
            "observer_completed_recorded": any(e["event"] == "observer_completed" for e in events),
            "observer_pid": attached["observer_pid"], "attached_handles": attached["attached_count"],
            "journal_exit_records": len(exits),
            "journal_nonzero_exits": [e for e in exits if e["exit_code"] != 0],
            "journal_errors": [e for e in events if e["event"] in
                               ("attach_failed", "identity_failed", "observer_error")],
            "journal_incomplete_last_line": bool(lines[-1]),
            "running_workers_verified": sum(r["running_identity_verified"] for r in rows),
            "checkpoint_count": len(ages), "checkpoint_oldest_age_seconds": max(ages, default=None),
            "checkpoint_newest_age_seconds": min(ages, default=None),
            "checkpoint_content_read": False, "memory": memory_snapshot(), "workers": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=Path(r"D:\CodexRuntime\runs\r33_stage6_20261022"))
    parser.add_argument("--output", type=Path, help="Optional new snapshot file; existing files are never overwritten")
    args = parser.parse_args()
    result = snapshot(args.runtime)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "workers"}, ensure_ascii=False, allow_nan=False))

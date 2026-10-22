"""Revision 6: one bounded queue, immutable task identities, and audited completion.

This module adds orchestration only. The worker invokes screen.run_one unchanged;
every config field is serialized through --set, including default-valued fields.
"""
from __future__ import annotations

import argparse
import copy
import ctypes
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
import uuid
import xml.etree.ElementTree as ET

import numpy as np
import torch

from pinn1d import Config
from problems import OUT_TIMES, get_problem, get_reference
from run_artifacts import load_result, sha256, validate_checkpoint, validate_config
from screen import evaluate, out_path, parse_overrides, run_one
from stage5_support import heldout_residuals

HERE = Path(__file__).resolve().parent
VALIDATION = HERE / "validation/stage6_20261022"
DEFAULT_RUNTIME = Path(r"D:\CodexRuntime\runs\r33_stage6_20261022")
PREREG = "bfe89e3a07f1bb3bcc8e049d8d3d7ff95b4a647a"
OLD_MANIFEST = HERE / "validation/stage5_analysis_20261022/analysis_evidence.json"
OLD_GATE = HERE / "validation/stage5_20261022/engineering_gate.json"
TRAINING_FILES = ("pinn1d.py", "problems.py", "screen.py", "run_artifacts.py",
                  "soap_baseline.py", "stage5_support.py")
SOURCE_FILES = TRAINING_FILES + ("third_party/soap_official.py", "stage6_runner.py",
                               "run_stage6.ps1", "test_stage6_runner.py", "SCREEN_PROTOCOL.md",
                               "validation/stage6_20261022/soap_upstream_blob.json")
COMMON = dict(width=64, depth=4, adam_steps=20000, lr0=0.001, lr1=1e-5,
              nf=4096, nb=256, n0=256, lbfgs_iters=3000, lbfgs_chunk=50,
              nf_fixed=8192, nb_fixed=512, n0_fixed=512, tau=0.1, w_ic=1,
              t_refine=0, optimizer="adam", arch="mlp")
TAU_JOBS = [(tag, eq, "hardic+layer", seed)
            for tag in ("sensitivity_tau003_v1", "sensitivity_tau03_v1")
            for seed in (0, 1, 2) for eq in ("E1_heat", "E3_fisher")]
SOAP_JOBS = [("final_soap64_v1", eq, method, seed) for seed in (0, 1, 2)
             for eq in ("E1_heat", "E3_fisher") for method in ("vanilla", "hardic", "hardic+layer")]
ALL_JOBS = TAU_JOBS + SOAP_JOBS
MAX_WORKERS = 24
GIB = 1024 ** 3
_PROGRESS_CACHE = {}
_REPLACE_DELAYS = (0.05, 0.1, 0.2, 0.4, 0.8, 0.8, 0.8, 0.8, 0.8)
ORCHESTRATION_FILES = {"stage6_runner.py", "run_stage6.ps1", "test_stage6_runner.py"}


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # One writer per process/path under the runner lock. Reuse its failed temp
    # so permanent denial cannot leave a new full status file on every poll.
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    # Windows can temporarily deny replacement. Never delete the old
    # destination or truncate it as a fallback; retain the complete temp on failure.
    for attempt in range(len(_REPLACE_DELAYS) + 1):
        try:
            os.replace(tmp, path)
            return
        except OSError as exc:
            transient = isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in (5, 32, 33)
            if not transient or attempt == len(_REPLACE_DELAYS):
                raise
            time.sleep(_REPLACE_DELAYS[attempt])


def open_shared_read(path):
    """Use delete-sharing for short Windows reads; replacement may still need retry."""
    if os.name != "nt":
        return Path(path).open("rb")
    import msvcrt
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    # GENERIC_READ; FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE.
    handle = kernel.CreateFileW(str(Path(path)), 0x80000000, 7, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    return os.fdopen(fd, "rb")


def read_json(path):
    with open_shared_read(path) as handle:
        return json.loads(handle.read().decode("utf-8-sig"))


def emergency_state(runtime, state, where, error):
    """Independent evidence on a unique path; reporting failure never orphans workers."""
    payload = {"utc": now(), "where": where, "error": str(error), "state": state}
    path = Path(runtime) / "emergency" / f"{os.getpid()}_{time.time_ns()}_{uuid.uuid4().hex}.json"
    try:
        write_json(path, payload)
        print(f"EMERGENCY_STATE {path}: {where}: {error}", file=sys.stderr, flush=True)
    except Exception as exc:
        # A full disk/permission error may affect both locations. The launcher's
        # stderr is a separate already-open stream; retain exit observations there.
        try:
            print("EMERGENCY_STATE_FALLBACK " + json.dumps(dict(payload, evidence_write_error=repr(exc)),
                  ensure_ascii=False, allow_nan=False), file=sys.stderr, flush=True)
        except Exception:
            pass


def task_id(job):
    tag, eq, method, seed = job
    return f"{tag}__{eq}__{method.replace('+', '_')}_s{seed}"


def config(job):
    if tuple(job) not in ALL_JOBS:
        raise ValueError(f"任务不属于已预注册的 30 项：{job}")
    cfg = dict(COMMON, seed=job[3])
    if job[0] == "sensitivity_tau003_v1":
        cfg["tau"] = 0.03
    elif job[0] == "sensitivity_tau03_v1":
        cfg["tau"] = 0.3
    else:
        cfg["optimizer"] = "soap_official64"
    result = replace(Config(), **cfg)
    validate_config(result, job[2])
    return result


def checkpoint(job, runtime):
    return Path(runtime) / "checkpoints" / (task_id(job) + ".ckpt")


def command_for(job, runtime):
    command = [sys.executable, "-u", str(HERE / "stage6_runner.py"), "--worker",
               job[0], job[1], job[2], str(job[3]), "--runtime", str(runtime)]
    for key, value in asdict(config(job)).items():
        command.extend(["--set", f"{key}={value}"])
    return command


def worker_config(job, arguments):
    keys = [arg.split("=", 1)[0] for arg in arguments]
    if len(keys) != len(set(keys)):
        raise ValueError("--set 不允许重复覆盖")
    supplied = parse_overrides(arguments)
    expected = asdict(config(job))
    if supplied != expected:
        raise ValueError("worker 的 --set 必须逐项匹配冻结配置，禁止更换参数或种子")
    supplied.pop("seed")  # screen.run_one supplies the seed from the task tuple.
    return supplied


class FileLock:
    """OS lock survives stale lock files and prevents duplicate live writers."""

    def __init__(self, path):
        self.path = Path(path)
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        if self.path.stat().st_size == 0:
            self.handle.write(b"0")
            self.handle.flush()
        self.handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.handle.close()
            self.handle = None
            raise RuntimeError(f"已有进程持有锁：{self.path}") from exc
        return self

    def __exit__(self, *_):
        if self.handle is not None:
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None


def worker_lock(job, runtime):
    return FileLock(Path(runtime) / "locks" / (task_id(job) + ".lock"))


def worker_environment(runtime):
    return dict(os.environ, R33_CKPT_DIR=str(Path(runtime) / "checkpoints"),
                OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                NUMEXPR_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1",
                TEMP=r"D:\CodexRuntime\temp", TMP=r"D:\CodexRuntime\temp",
                PYTHONPYCACHEPREFIX=r"D:\CodexRuntime\cache\pycache",
                PYTHONUTF8="1", PYTHONIOENCODING="utf-8")


def normal_priority():
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        if not kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x20):
            raise ctypes.WinError(ctypes.get_last_error())


def memory_snapshot():
    if os.name != "nt":
        raise RuntimeError("本轮资源门针对 Windows；不在未知平台静默禁用资源检查")

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in (
                "total_physical", "available_physical", "total_commit", "available_commit",
                "total_virtual", "available_virtual", "available_extended_virtual")]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    if not kernel.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError(ctypes.get_last_error())
    return {"available_physical_gib": status.available_physical / GIB,
            "total_physical_gib": status.total_physical / GIB,
            "commit_used_fraction": 1 - status.available_commit / status.total_commit,
            "available_commit_gib": status.available_commit / GIB}


def resources_allow_dispatch(snapshot):
    return snapshot["available_physical_gib"] >= 4 and snapshot["commit_used_fraction"] <= 0.90


def source_hashes():
    return {name: sha256(HERE / name) for name in SOURCE_FILES}


def check_preregistration():
    subprocess.run(["git", "merge-base", "--is-ancestor", PREREG, "HEAD"], cwd=HERE, check=True)
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=HERE,
                                       encoding="utf-8").strip())
    rel = (HERE / "SCREEN_PROTOCOL.md").relative_to(root).as_posix()
    committed = subprocess.check_output(["git", "show", f"{PREREG}:{rel}"], cwd=HERE)
    if committed.replace(b"\r\n", b"\n") != (HERE / "SCREEN_PROTOCOL.md").read_bytes().replace(b"\r\n", b"\n"):
        raise ValueError("协议与修订 6 的预注册提交不同；须审核新修订后更新门")


def check_old_results():
    manifest = read_json(OLD_MANIFEST)["raw_sha256"]
    if len(manifest) != 398:
        raise ValueError(f"旧结果清单应为 398 个文件，实际 {len(manifest)}")
    for name, digest in manifest.items():
        if sha256(HERE / name) != digest:
            raise ValueError(f"旧结果文件已变化：{name}")
    return {"files": len(manifest), "unchanged": True, "manifest_sha256": sha256(OLD_MANIFEST)}


def check_reused_tests():
    evidence = read_json(OLD_GATE)
    log = OLD_GATE.parent / "pytest.log"
    if evidence.get("tests") != 71 or not evidence.get("passed"):
        raise ValueError("缺少上一阶段 71 项测试通过证据")
    if sha256(log) != evidence["pytest_log_sha256"]:
        raise ValueError("原测试日志 hash 不匹配")
    if not re.search(r"\b71 passed\b", log.read_text(encoding="utf-8-sig")):
        raise ValueError("原日志未记录 71 passed")
    for name in TRAINING_FILES:
        if sha256(HERE / name) != evidence["source_hashes"][name]:
            raise ValueError(f"训练源发生变化，不能复用原 71 项测试：{name}")
    return {"tests": 71, "reused": True, "training_source_hashes": {
        name: evidence["source_hashes"][name] for name in TRAINING_FILES},
        "pytest_log_sha256": sha256(log),
        "protocol_hash_excluded_from_old_gate": "修订 6 已单独检查预注册提交"}


def check_vendor_source():
    evidence = read_json(VALIDATION / "soap_upstream_blob.json")
    upstream = evidence["content"].encode("utf-8")
    blob_sha = hashlib.sha1(b"blob " + str(len(upstream)).encode() + b"\0" + upstream).hexdigest()
    if blob_sha != "a6362cc9ed2f50ed299204eb3bf07715e7280757" or evidence["blob_sha"] != blob_sha:
        raise ValueError("保存的 SOAP 上游源码不是固定 Git blob")
    local = (HERE / "third_party/soap_official.py").read_bytes()
    # The original vendoring commit adds exactly one final LF. Do not normalize
    # any other whitespace or code when checking the pinned source.
    if local != upstream + b"\n":
        raise ValueError("SOAP 供应商源码与固定 blob 不符（仅允许已记录的末尾 LF）")
    return {"repository": "nikhilvyas/SOAP", "upstream_blob_sha1": blob_sha,
            "upstream_bytes": len(upstream), "local_bytes": len(local),
            "local_sha256": sha256(HERE / "third_party/soap_official.py"),
            "difference": "本地原有文件仅在上游末尾添加一个 LF；其余字节完全相同。",
            "passed": True}


def check_no_live_workers(runtime):
    # If the queue process died, an orphan worker retains its task lock. Do not
    # start a second writer or count PID reuse as proof of a live old worker.
    for job in ALL_JOBS:
        with worker_lock(job, runtime):
            pass


def same_recovery_inventory_tasks(observed, expected):
    """Only task/attempt started_utc may differ by timezone rendering.

    Retain every fractional digit: datetime.fromisoformat alone would truncate
    sub-microsecond changes. All other JSON values and types must match exactly.
    """
    def instant(value):
        if not isinstance(value, str):
            raise ValueError("timestamp must be text")
        match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})", value)
        if not match:
            raise ValueError("timestamp must have an explicit timezone")
        seconds, fraction, offset = match.groups()
        if offset != "Z" and (int(offset[1:3]) > 23 or int(offset[4:6]) > 59):
            raise ValueError("invalid timezone offset")
        utc = datetime.fromisoformat(seconds + offset).astimezone(timezone.utc)
        return utc, (fraction or "").rstrip("0")

    def same(left, right, path=()):
        timestamp = ((len(path) == 2 and isinstance(path[0], int) and path[1] == "started_utc") or
                     (len(path) == 4 and isinstance(path[0], int) and path[1] == "attempts" and
                      isinstance(path[2], int) and path[3] == "started_utc"))
        if timestamp:
            try:
                return instant(left) == instant(right)
            except (ValueError, OverflowError):
                return False
        if type(left) is not type(right):
            return False
        if isinstance(left, dict):
            return left.keys() == right.keys() and all(same(left[k], right[k], path + (k,)) for k in left)
        if isinstance(left, list):
            return len(left) == len(right) and all(same(a, b, path + (i,)) for i, (a, b) in enumerate(zip(left, right)))
        return left == right

    return same(observed, expected)


def recovery_lineage(manifest_path, runtime):
    """Bind a completed HANDLE observation to the original 21 task attempts.

    This does not adopt live workers or infer success from a missing PID. Failed
    or unknown exits require a separate explicit decision, never an automatic retry.
    """
    manifest_path = Path(manifest_path).resolve()
    manifest = read_json(manifest_path)
    if manifest.get("schema") != "r33_stage6_recovery_manifest_v1" or not manifest.get("incident_id"):
        raise ValueError("恢复 manifest 类型或 incident_id 错误")
    required = {"prior_gate", "prior_status", "process_inventory", "observer_events",
                "observer_source", "runner_stderr", "incident_manifest"}
    if set(manifest.get("artifacts", {})) != required:
        raise ValueError("恢复 manifest 必须完整绑定原门/状态/进程身份/观察日志/源码/故障日志/快照清单")
    artifacts = copy.deepcopy(manifest["artifacts"])
    for entry in artifacts.values():
        path = Path(entry["path"]).resolve()
        if sha256(path) != entry["sha256"]:
            raise ValueError(f"恢复证据 hash 不匹配：{path}")
        entry["path"] = str(path)
    prior_gate = read_json(artifacts["prior_gate"]["path"])
    prior = read_json(artifacts["prior_status"]["path"])
    inventory = read_json(artifacts["process_inventory"]["path"])
    frozen = read_json(artifacts["incident_manifest"]["path"])
    for entry in frozen["files"]:
        if sha256(entry["snapshot"]) != entry["sha256"]:
            raise ValueError(f"事故原始快照发生变化：{entry['snapshot']}")
    current_hashes = source_hashes()
    original_hashes = prior_gate["source_hashes"]
    if set(current_hashes) != set(original_hashes) or any(
            current_hashes[name] != value for name, value in original_hashes.items() if name not in ORCHESTRATION_FILES):
        raise ValueError("恢复仅允许编排源变化；训练/协议/供应商源码必须与原门完全相同")
    if (prior_gate.get("passed") is not True or prior_gate.get("prereg_commit") != PREREG or
            prior.get("prereg_commit") != PREREG or prior_gate["tasks"] != [list(j) for j in ALL_JOBS] or
            Path(prior_gate["runtime"]).resolve() != Path(runtime).resolve()):
        raise ValueError("恢复原门的协议、任务集合或运行目录不符")
    tasks = {tuple(row["job"]): row for row in prior["tasks"]}
    if len(prior["tasks"]) != len(tasks) or set(tasks) != set(ALL_JOBS):
        raise ValueError("恢复原状态必须包含精确的全部预注册任务")
    for job, row in tasks.items():
        if row["id"] != task_id(job) or row["config"] != asdict(config(job)):
            raise ValueError("恢复原任务身份/完整配置不符")
    if (not same_recovery_inventory_tasks(inventory["tasks"], prior["tasks"]) or
            inventory["original_gate_sha256"] != artifacts["prior_gate"]["sha256"] or
            inventory["original_runner_pid"] != prior["runner_pid"]):
        raise ValueError("进程身份清单没有绑定原运行状态和原门")
    with open_shared_read(artifacts["observer_events"]["path"]) as handle:
        events = [json.loads(line) for line in handle.read().decode("utf-8").splitlines() if line.strip()]
    starts = [e for e in events if e["event"] == "observer_started"]
    if (len(starts) != 1 or starts[0]["snapshot_sha256"] != artifacts["process_inventory"]["sha256"] or
            starts[0]["observer_source_sha256"] != artifacts["observer_source"]["sha256"] or
            starts[0]["original_gate_sha256"] != artifacts["prior_gate"]["sha256"] or
            not events or events[-1].get("event") != "observer_completed" or
            events[-1].get("all_handles_signaled") is not True or
            any(e["event"] in ("attach_failed", "identity_failed", "observer_error") for e in events)):
        raise ValueError("HANDLE 观察未完整成功结束或证据绑定不符；禁止推断未知退出")
    active = {job: row for job, row in tasks.items() if row["state"] == "running"}
    if not active or any(row["state"] != "queued" for job, row in tasks.items() if job not in active):
        raise ValueError("此事故恢复要求原状态仅包含 running/queued，其他状态须单独审查")
    processes = {row["pid"]: row for row in inventory["workers"]}
    attached_rows = [e for e in events if e["event"] == "attached"]
    exits_rows = [e for e in events if e["event"] == "process_exited"]
    attached = {e["pid"]: e for e in attached_rows}
    exits = {e["pid"]: e for e in exits_rows}
    if (len(processes) != len(inventory["workers"]) or len(processes) != 2 * len(active) or
            len(attached_rows) != len(attached) or len(exits_rows) != len(exits) or
            set(processes) != set(attached) or set(processes) != set(exits)):
        raise ValueError("每个原任务必须有唯一 launcher/worker 身份与 HANDLE 退出记录")
    reconciled = []
    for job, row in active.items():
        pair = [a for a in attached_rows if tuple(a["job"]) == job]
        if len(pair) != 2 or {a["role"] for a in pair} != {"launcher", "worker"}:
            raise ValueError("原任务 launcher/worker 配对不完整")
        observations = {}
        for identity in pair:
            pid, role = identity["pid"], identity["role"]
            sampled, observed = processes[pid], exits[pid]
            if ((role == "launcher" and pid != row["pid"]) or
                    (role == "worker" and identity["ppid"] != row["pid"]) or
                    identity["ppid"] != sampled["ppid"] or
                    abs(identity["creation_filetime_utc"] - sampled["creation_filetime_utc"]) > 10 or
                    identity["command_line"] != sampled["command_line"] or
                    os.path.normcase(identity["executable_path"]) != os.path.normcase(sampled["executable_path"]) or
                    identity["argv"][1:] != row["attempts"][-1]["command"][1:] or
                    observed.get("identity_verified") is not True or observed.get("job") != list(job) or
                    observed.get("role") != role or
                    observed.get("creation_filetime_utc") != identity["creation_filetime_utc"]):
                raise ValueError("恢复进程的完整参数/创建时间/父子关系/退出身份不符")
            if observed["exit_code"] != 0:
                raise ValueError(f"原任务真实退出非零，须单独明确处置，禁止静默重跑：{job} {role} {observed['exit_code']}")
            observations[role] = observed
        if not out_path(*job).is_file():
            raise ValueError(f"原任务退出后没有完整结果 JSON；不得自动重跑：{job}")
        finished = datetime.fromisoformat(observations["launcher"]["utc"]).timestamp()
        wall = finished - row["attempts"][-1]["started_unix"]
        if wall < 0:
            raise ValueError("退出观测时间早于原任务派发")
        reconciled.append({"job": list(job), "launcher": observations["launcher"],
                           "worker": observations["worker"], "observed_wall_seconds": wall})
    return {"schema": "r33_stage6_recovery_lineage_v1", "incident_id": manifest["incident_id"],
            "manifest": {"path": str(manifest_path), "sha256": sha256(manifest_path)},
            "artifacts": artifacts, "prior_gate_sha256": artifacts["prior_gate"]["sha256"],
            "prior_source_hashes": original_hashes, "prior_status_sha256": artifacts["prior_status"]["sha256"],
            "original_active_jobs": [list(j) for j in active], "reconciled": reconciled,
            "training_and_protocol_unchanged": True,
            "scope": "原进程退出身份与编排来源；exit 0 不替代完整 bundle、预算与误差重算。"}


def verify_recovery_bindings(lineage):
    for entry in [lineage["manifest"], *lineage["artifacts"].values()]:
        if sha256(entry["path"]) != entry["sha256"]:
            raise ValueError(f"冻结恢复证据变化：{entry['path']}")


def reconcile_recovered_attempts(previous, lineage, current_status_sha256):
    if not lineage or lineage["manifest"]["sha256"] in previous.get("applied_recoveries", []):
        return previous
    if current_status_sha256 != lineage["prior_status_sha256"]:
        raise ValueError("恢复前 status 与已保全事故状态不同；禁止覆盖未经审查的新历史")
    previous = copy.deepcopy(previous)
    rows = {tuple(row["job"]): row for row in previous["tasks"]}
    for observation in lineage["reconciled"]:
        row = rows[tuple(observation["job"])]
        attempt = row["attempts"][-1]
        attempt.update(finished_utc=observation["launcher"]["utc"], exit_code=observation["launcher"]["exit_code"],
                       worker_exit_code=observation["worker"]["exit_code"],
                       wall_seconds=observation["observed_wall_seconds"],
                       wall_seconds_basis="HANDLE signaled exit observed by recovery monitor minus original dispatch time",
                       source_gate_sha256=lineage["prior_gate_sha256"],
                       supervision_interrupted=True, recovery_manifest_sha256=lineage["manifest"]["sha256"],
                       observed_worker_pid=observation["worker"]["pid"])
    incident = {"utc": now(), "reason": "runner_permission_error_orphaned_workers",
                "incident_id": lineage["incident_id"], "recovered_exit_observations": len(lineage["reconciled"]),
                "manifest": lineage["manifest"], "runner_stderr": lineage["artifacts"]["runner_stderr"]}
    previous.setdefault("failure_history", []).append(incident)
    previous.setdefault("recovery_incidents", []).append(incident)
    previous.setdefault("applied_recoveries", []).append(lineage["manifest"]["sha256"])
    previous.setdefault("source_lineage", []).append({"gate_sha256": lineage["prior_gate_sha256"],
        "source_hashes": lineage["prior_source_hashes"], "jobs": lineage["original_active_jobs"],
        "role": "original_workers", "recovery_manifest": lineage["manifest"]})
    previous["runner_wall_timing_note"] = ("原 runner 退出后的孤儿训练区间不计入 runner 活跃墙钟；"
                                           "各原 attempt 的墙钟按 HANDLE 退出观测补记，含轮询延迟；批次总历时单列。")
    return previous


def require_reviewed_previous_attempts(previous, retry_failed_jobs=()):
    """No orphan/failed attempt becomes a fresh training run by resetting state."""
    retry = set(retry_failed_jobs)
    if previous is None:
        if retry:
            raise ValueError("没有原任务历史，不能指定失败重试")
        return
    failed = set()
    for row in previous.get("tasks", []):
        for attempt in row.get("attempts", []):
            if attempt.get("pid") is not None and "exit_code" not in attempt and "launch_error" not in attempt:
                raise ValueError(f"原 attempt 缺少实测退出；须先恢复监督证据，禁止重复训练：{row['id']}")
        last = row.get("attempts", [{}])[-1] if row.get("attempts") else {}
        if (row.get("state") == "failed" or last.get("exit_code", 0) != 0 or
                last.get("worker_exit_code", 0) != 0 or "launch_error" in last):
            failed.add(row["id"])
    if retry - failed:
        raise ValueError("失败重试参数包含没有失败证据的任务")
    if failed - retry:
        raise ValueError("已失败任务须逐项明确 --retry-failed-job 后才能恢复：" + ", ".join(sorted(failed - retry)))


def existing_identity_checks(runtime):
    expected_paths = {out_path(*job).resolve() for job in ALL_JOBS}
    for tag in {job[0] for job in ALL_JOBS}:
        for path in (HERE / "runs" / tag).rglob("*.json"):
            if path.resolve() not in expected_paths:
                raise ValueError(f"新 tag 出现未注册结果：{path}")
    rows = []
    for job in ALL_JOBS:
        path, ckpt = out_path(*job), checkpoint(job, runtime)
        if path.exists():
            _, _, artifact = load_result(path, expected_config=config(job),
                                         expected_job=(job[1], job[2], job[3], job[0]))
            if artifact != "complete":
                raise ValueError(f"新结果必须具备完整 bundle：{path}")
            rows.append({"job": list(job), "existing_result": str(path), "sha256": sha256(path)})
        elif ckpt.exists():
            validate_checkpoint(ckpt, get_problem(job[1]), job[2], config(job))
            rows.append({"job": list(job), "checkpoint": str(ckpt), "sha256": sha256(ckpt)})
        elif path.with_suffix(".pt").exists() or path.with_suffix(".model.pt").exists():
            raise ValueError(f"发现没有 JSON 和 checkpoint 的不完整结果：{path}")
    return rows


def verify_gate(runtime):
    check_preregistration()
    evidence = read_json(VALIDATION / "engineering_gate.json")
    if not evidence.get("passed") or evidence["prereg_commit"] != PREREG:
        raise ValueError("修订 6 工程门尚未通过")
    if evidence["source_hashes"] != source_hashes():
        raise ValueError("工程门后源文件发生改变；须重新跑 Gate")
    if evidence["runtime"] != str(Path(runtime).resolve()):
        raise ValueError("运行目录与工程门不同")
    check_runtime()
    if sha256(OLD_MANIFEST) != evidence["old_results"]["manifest_sha256"]:
        raise ValueError("旧 398 文件证据清单变化")
    if sha256(VALIDATION / "pytest.xml") != evidence["runner_tests"]["junit_sha256"]:
        raise ValueError("新 runner 测试证据变化")
    if evidence.get("recovery_lineage"):
        verify_recovery_bindings(evidence["recovery_lineage"])
    check_old_results()
    return evidence


def check_runtime():
    actual = {"python": sys.version.split()[0], "torch": str(torch.__version__), "numpy": np.__version__}
    expected = {"python": "3.12.6", "torch": "2.14.1+cpu", "numpy": "2.5.3"}
    if actual != expected:
        raise ValueError(f"必须使用冻结环境：实际 {actual}；要求 {expected}")
    return actual


def reference_checks():
    rows = []
    x = np.linspace(0, 1, 401)
    for eq in ("E1_heat", "E3_fisher"):
        p = get_problem(eq)
        r64, r96 = get_reference(p, 64), get_reference(p, 96)
        difference = max(float(np.max(np.abs(r64(x, t) - r96(x, t)))) for t in OUT_TIMES)
        if not np.isfinite(difference) or difference > 1e-8:
            raise ValueError(f"参考解自检失败：{eq}，N64/N96 最大绝对差 {difference}")
        rows.append({"eq": eq, "N64_N96_max_abs": difference, "points": 401,
                     "times": list(OUT_TIMES), "tolerance": 1e-8, "passed": True})
    return rows


def gate(runtime, recovery_manifest=None):
    runtime = Path(runtime).resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    check_preregistration()
    versions = check_runtime()
    check_no_live_workers(runtime)
    lineage = recovery_lineage(recovery_manifest, runtime) if recovery_manifest else None
    old_gate_path = VALIDATION / "engineering_gate.json"
    if old_gate_path.exists() and (runtime / "status.json").exists() and lineage is None:
        prior = read_json(runtime / "status.json")
        if any(row.get("state") == "running" for row in prior.get("tasks", [])):
            raise ValueError("原状态仍有失去监督的 running 任务；须绑定恢复证据，不得直接覆盖原门")
    reused, old, vendor = check_reused_tests(), check_old_results(), check_vendor_source()
    references = reference_checks()
    identities = existing_identity_checks(runtime)
    VALIDATION.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "pytest", "test_stage6_runner.py", "-q",
               "--basetemp", r"D:\CodexRuntime\temp\r33-stage6-pytest",
               "--junitxml", str(VALIDATION / "pytest.xml")]
    with (VALIDATION / "pytest.log").open("w", encoding="utf-8") as log:
        completed = subprocess.run(command, cwd=HERE, env=worker_environment(runtime),
                                   stdout=log, stderr=subprocess.STDOUT, check=False)
    if completed.returncode:
        raise ValueError("stage6 runner 专用测试失败，检查 validation/stage6_20261022/pytest.log")
    suites = ET.parse(VALIDATION / "pytest.xml").getroot()
    leaves = [suites] if suites.tag == "testsuite" else list(suites)
    counts = {name: sum(int(s.attrib.get(name, 0)) for s in leaves)
              for name in ("tests", "failures", "errors", "skipped")}
    if counts["tests"] < 12 or any(counts[k] for k in ("failures", "errors", "skipped")):
        raise ValueError(f"runner 测试未完整通过：{counts}")
    report = {"time_utc": now(), "passed": True, "prereg_commit": PREREG,
              "runtime": str(runtime), "environment": versions, "references": references,
              "source_hashes": source_hashes(), "reused_tests": reused, "old_results": old,
              "vendor_source": vendor,
              "runner_tests": dict(counts, command=command, junit_sha256=sha256(VALIDATION / "pytest.xml")),
              "existing_identities": identities, "tasks": [list(j) for j in ALL_JOBS],
              "new_training_started_by_gate": False}
    if lineage:
        report["recovery_lineage"] = lineage
    write_json(VALIDATION / "engineering_gate.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return report


def worker(job, arguments, runtime):
    overrides = worker_config(job, arguments)
    verify_gate(runtime)
    normal_priority()
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    os.environ.update(worker_environment(runtime))
    with worker_lock(job, runtime):
        print(f"START {now()} PID={os.getpid()} JOB={job!r}", flush=True)
        print(run_one((job[1], job[2], job[3], overrides, job[0])), flush=True)


def checkpoint_progress(job, runtime, *, metadata_only=False):
    path = checkpoint(job, runtime)
    key = str(path.resolve())
    try:
        stat = path.stat()
    except FileNotFoundError:
        _PROGRESS_CACHE.pop(key, None)
        return {"checkpoint": str(path), "position": "结果已落盘" if out_path(*job).exists() else "尚无首个 checkpoint"}
    metadata = {"checkpoint": str(path), "checkpoint_modified_unix": stat.st_mtime,
                "checkpoint_size_bytes": stat.st_size, "checkpoint_metadata_only": True}
    if metadata_only:
        return dict(metadata, progress_unavailable_reason="活动任务仅查看 mtime/size；不打开检查点，保护冻结训练写端。")
    signature = (stat.st_mtime_ns, stat.st_size)
    try:
        # Never read a live writer's checkpoint. Hold its task lock through the
        # snapshot/deserialization, so even a late-starting duplicate cannot race.
        with worker_lock(job, runtime):
            stat = path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
            cached = _PROGRESS_CACHE.get(key)
            if cached and cached[0] == signature:
                return dict(cached[1])
            with open_shared_read(path) as handle:
                snapshot = handle.read()
            raw = torch.load(io.BytesIO(snapshot), weights_only=False, map_location="cpu")
        state = raw["state"]
        progress = {"checkpoint": str(path), "phase": state["phase"], "adam_step": state["step"],
                    "lbfgs_budget_used": state["done"], "saved_elapsed_seconds": state.get("elapsed"),
                    "checkpoint_modified_unix": stat.st_mtime,
                    "resumed_at": raw["hist"].get("resumed_at", [])}
        _PROGRESS_CACHE[key] = (signature, progress)
        return dict(progress)
    except (OSError, EOFError, KeyError, RuntimeError) as exc:
        return dict(metadata, progress_read_error=str(exc),
                    progress_unavailable_reason="检查点未解析：任务锁占用或读取失败；不推断训练位置。")


class ResultValidator:
    def __init__(self):
        self.references = {}
        xx, ww = np.polynomial.legendre.leggauss(400)
        self.xx, self.ww = 0.5 * (xx + 1), 0.5 * ww

    def __call__(self, job):
        tag, eq, method, seed = job
        refs = self.references.setdefault(eq, {})
        for n in (64, 96):
            if n not in refs:
                refs[n] = get_reference(get_problem(eq), n)
        path = out_path(*job)
        model, rec, artifact = load_result(path, expected_config=config(job), expected_job=(eq, method, seed, tag))
        recomputed = evaluate(model, refs[64])
        dense = {"vol": [], "trace": []}
        with torch.no_grad():
            for t in OUT_TIMES:
                u = model(torch.tensor(self.xx), torch.full((len(self.xx),), t)).numpy()
                ur = refs[96](self.xx, t)
                dense["vol"].append(float(np.sqrt(np.sum(self.ww * (u - ur) ** 2) / np.sum(self.ww * ur ** 2))))
                u1 = float(model(torch.ones(1), torch.tensor([t]))[0])
                r1 = float(refs[96](np.array([1.]), t)[0])
                dense["trace"].append(abs(u1 - r1) / max(abs(r1), 1e-12))
        if artifact != "complete" or not all(
                np.allclose(values[k], rec["metrics"][k], rtol=1e-5, atol=1e-9)
                for values in (recomputed, dense) for k in ("vol", "trace")):
            raise ValueError(f"完整模型/参考解重算检查未通过：{path}")
        history = rec["history"]
        if history.get("adam_gradient_calls") != 20000:
            raise ValueError(f"未完成 20000 次梯度调用：{path}")
        if history.get("lbfgs_stop_reason") not in ("budget_exhausted", "loss_stagnation"):
            raise ValueError(f"L-BFGS 未记录合法终止原因：{path}")
        if not 0 < history.get("lbfgs_budget_used", 0) <= 3000:
            raise ValueError(f"L-BFGS 预算记录错误：{path}")
        counters = {k: history.get(k) for k in (
            "adam_gradient_calls", "lbfgs_budget_used", "lbfgs_func_evals", "lbfgs_n_iter",
            "lbfgs_loss_stagnation", "lbfgs_stop_reason", "resumed_at")}
        is_soap = config(job).optimizer == "soap_official64"
        return {"job": list(job), "validated_utc": now(), "json_sha256": sha256(path),
                "bundle_sha256": {p.name: sha256(p) for p in
                                  (path, path.with_suffix(".pt"), path.with_suffix(".model.pt"))},
                "complete_and_recomputed": True, "max_vol": rec["max_vol"], "max_trace": rec["max_trace"],
                "metrics": rec["metrics"], "recomputed_N64_GL200": recomputed,
                "dense_metrics_N96_GL400": dense, "tolerance": {"rtol": 1e-5, "atol": 1e-9},
                "heldout": heldout_residuals(model), "history_counters": counters,
                "config": rec["config"], "delta": rec["delta"],
                "final_adam_loss": rec["final_adam_loss"], "final_lbfgs_loss": rec["final_lbfgs_loss"],
                "adam_seconds": rec["adam_seconds"],
                "optimizer_accounting": {"optimizer": config(job).optimizer,
                    "gradient_calls_recorded": history["adam_gradient_calls"],
                    "first_call_initializes_only": is_soap,
                    "parameter_updates_inferred_from_frozen_optimizer_semantics": 19999 if is_soap else 20000,
                    "note": "更新次数按冻结实现推得；真实 L-BFGS closure 次数见 history_counters。"},
                "trajectory_wall_seconds_including_saved_history": rec["wall_seconds"]}


def new_state(previous=None):
    previous = previous or {}
    prior_rows = {tuple(r["job"]): r for r in previous.get("tasks", [])}
    rows = []
    for job in ALL_JOBS:
        prior = prior_rows.get(job, {})
        rows.append({"job": list(job), "id": task_id(job), "state": "queued", "pid": None,
                     "config": asdict(config(job)), "attempts": prior.get("attempts", []),
                     "required_complete_result": (prior.get("required_complete_result", False) or
                                                  prior.get("state") == "completed"),
                     "last_error": prior.get("last_error")})
    start = time.time()
    return {"phase": "checking", "prereg_commit": PREREG, "runner_pid": os.getpid(),
            "first_started_utc": previous.get("first_started_utc", now()),
            "session_started_utc": now(), "session_started_unix": start,
            "prior_runner_wall_seconds": previous.get("total_runner_wall_seconds", 0),
            "review_deadline_unix": previous.get("review_deadline_unix", start + 48 * 3600), "tasks": rows,
            "failure_history": previous.get("failure_history", []), "resources": None,
            "resource_reviews": previous.get("resource_reviews", []),
            "source_lineage": previous.get("source_lineage", []),
            "recovery_incidents": previous.get("recovery_incidents", []),
            "applied_recoveries": previous.get("applied_recoveries", []),
            "runner_wall_timing_note": previous.get("runner_wall_timing_note"),
            "stop_dispatch_reason": None, "preregistered_tasks": 30}


def prevalidate_results_before_dispatch(state, gate_evidence, validator):
    """A previously completed/original recovered job can never become queued.

    Persist the requirement even when validation fails, so a second run cannot
    erase this protection by reading the failed preflight's reset task states.
    File existence is only a discovery rule for genuinely unattempted jobs.
    """
    required = {tuple(job) for job in gate_evidence.get("recovery_lineage", {}).get("original_active_jobs", [])}
    rows = {tuple(row["job"]): row for row in state["tasks"]}
    if required - rows.keys():
        raise ValueError("恢复门的原活动任务不在当前精确任务集合中")
    for job in required:
        rows[job]["required_complete_result"] = True
    for row in state["tasks"]:
        job = tuple(row["job"])
        if row.get("required_complete_result") or out_path(*job).exists():
            row["validation"] = validator(job)
            row["state"] = "completed"
            row["required_complete_result"] = True


def save_status(runtime, state):
    state["updated_utc"] = now()
    state["session_wall_seconds"] = time.time() - state["session_started_unix"]
    state["total_runner_wall_seconds"] = state["prior_runner_wall_seconds"] + state["session_wall_seconds"]
    state["batch_elapsed_seconds"] = time.time() - datetime.fromisoformat(state["first_started_utc"]).timestamp()
    state["counts"] = {key: sum(r["state"] == key for r in state["tasks"])
                       for key in ("queued", "running", "completed", "failed")}
    for row in state["tasks"]:
        if row["state"] in ("running", "failed"):
            row["progress"] = checkpoint_progress(tuple(row["job"]), runtime,
                                                  metadata_only=row["state"] == "running")
    write_json(Path(runtime) / "status.json", state)


def validation_report(rows, complete=False):
    report = {"updated_utc": now(), "prereg_commit": PREREG, "complete": complete,
              "required_count": 30, "validated_count": len(rows),
              "results": [rows[task_id(j)] for j in ALL_JOBS if task_id(j) in rows],
              "selection": "所有预注册任务全部报告；不按误差或损失筛除。"}
    write_json(VALIDATION / "results_validation.json", report)
    return report


def execute_queue(runtime, state, workers, validator, *, popen=subprocess.Popen,
                  memory=memory_snapshot, sleep=time.sleep, clock=time.time,
                  persist=save_status, dispatch_interval=5.0):
    """All failure/deadline paths drain active workers; never kill a checkpoint writer."""
    if not 1 <= workers <= MAX_WORKERS:
        raise ValueError("workers 必须为 1..24")
    active, validated = {}, {}
    state["max_workers"] = workers
    state["dispatch_interval_seconds"] = dispatch_interval
    state["phase"] = "running"
    for row in state["tasks"]:
        if row["state"] == "completed":
            validated[row["id"]] = row["validation"]
    last_dispatch = -float("inf")
    next_persist_retry = -float("inf")

    def stop(reason, error=None):
        if state["stop_dispatch_reason"] is None:
            state["stop_dispatch_reason"] = reason
            state["phase"] = "draining"
            if error:
                state["failure_history"].append({"utc": now(), "reason": reason, "error": error})

    def persist_safely(where):
        nonlocal next_persist_retry
        if where == "queue_poll" and clock() < next_persist_retry:
            return False
        try:
            persist(runtime, state)
            next_persist_retry = -float("inf")
            return True
        except Exception:
            detail = traceback.format_exc()
            stop("status_persistence_failure", detail)
            state["status_persistence_failures"] = state.get("status_persistence_failures", 0) + 1
            state["last_status_persistence_error"] = detail
            next_persist_retry = clock() + 30
            if state["status_persistence_failures"] == 1 or where == "queue_final":
                emergency_state(runtime, state, where, detail)
            return False

    while True:
        for identifier, item in list(active.items()):
            child, log, row = item
            try:
                returncode = child.poll()
            except Exception:
                detail = traceback.format_exc()
                stop("process_poll_failure", detail)
                row["poll_error_count"] = row.get("poll_error_count", 0) + 1
                row["last_poll_error"] = detail
                if row["poll_error_count"] == 1:
                    emergency_state(runtime, state, "process_poll_failure", detail)
                continue
            if returncode is None:
                continue
            try:
                log.close()
            except Exception:
                detail = traceback.format_exc()
                stop("worker_log_close_failure", detail)
                emergency_state(runtime, state, "worker_log_close_failure", detail)
            del active[identifier]
            row["pid"] = None
            row["finished_utc"] = now()
            attempt = row["attempts"][-1]
            attempt.update(finished_utc=now(), exit_code=returncode,
                           wall_seconds=clock() - attempt["started_unix"])
            if state.get("status_persistence_failures"):
                emergency_state(runtime, state, "worker_exit_during_drain",
                                f"{identifier}: exit_code={returncode}")
            try:
                if returncode:
                    raise RuntimeError(f"worker 退出码 {returncode}；查看 {attempt['log']}")
                row["validation"] = validator(tuple(row["job"]))
                row["state"] = "completed"
                validated[identifier] = row["validation"]
                validation_report(validated)
            except Exception as exc:
                row["state"] = "failed"
                row["last_error"] = str(exc)
                stop("engineering_failure", f"{identifier}: {exc}")
        queued = [r for r in state["tasks"] if r["state"] == "queued"]
        if clock() >= state["review_deadline_unix"] and queued:
            stop("48h_resource_review")
        if not active and (not queued or state["stop_dispatch_reason"]):
            break
        if not state["stop_dispatch_reason"]:
            try:
                snapshot = memory()
                state["resources"] = snapshot
                allowed = resources_allow_dispatch(snapshot)
                state["dispatch_paused_for_memory"] = not allowed
                if queued and len(active) < workers and allowed and clock() - last_dispatch >= dispatch_interval:
                    row = queued[0]
                    job = tuple(row["job"])
                    command = command_for(job, runtime)
                    logpath = Path(runtime) / "logs" / f"{row['id']}__attempt{len(row['attempts']) + 1}.log"
                    logpath.parent.mkdir(parents=True, exist_ok=True)
                    log = logpath.open("a", encoding="utf-8")
                    log.write(f"START {now()}\nCOMMAND {json.dumps(command, ensure_ascii=False)}\n")
                    log.flush()
                    flags = (subprocess.CREATE_NO_WINDOW | subprocess.NORMAL_PRIORITY_CLASS) if os.name == "nt" else 0
                    attempt = {"started_utc": now(), "started_unix": clock(), "pid": None,
                               "command": command, "log": str(logpath),
                               "source_gate_sha256": state.get("current_gate_sha256"),
                               "resume_checkpoint_present": checkpoint(job, runtime).exists()}
                    row["attempts"].append(attempt)
                    for lineage in state.get("source_lineage", []):
                        if lineage["gate_sha256"] == state.get("current_gate_sha256"):
                            jobs = lineage.setdefault("jobs", [])
                            if list(job) not in jobs:
                                jobs.append(list(job))
                    try:
                        child = popen(command, cwd=HERE, env=worker_environment(runtime), stdout=log,
                                      stderr=subprocess.STDOUT, creationflags=flags)
                    except Exception as exc:
                        log.close()
                        row.update(state="failed", last_error=str(exc))
                        attempt.update(finished_utc=now(), launch_error=str(exc),
                                       wall_seconds=clock() - attempt["started_unix"])
                        raise
                    attempt["pid"] = child.pid
                    row.update(state="running", pid=child.pid, started_utc=attempt["started_utc"], command=command)
                    active[row["id"]] = (child, log, row)
                    last_dispatch = clock()
            except Exception as exc:
                stop("engineering_failure", traceback.format_exc())
        persist_safely("queue_poll")
        sleep(2)
    state["phase"] = ("completed" if not state["stop_dispatch_reason"] and
                      all(r["state"] == "completed" for r in state["tasks"]) else "review_required")
    if not persist_safely("queue_final"):
        state["phase"] = "review_required"
        emergency_state(runtime, state, "queue_final_unpersisted", state["last_status_persistence_error"])
    return validated


def run(runtime, workers, resource_review_note=None, retry_failed_jobs=()):
    runtime = Path(runtime).resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    normal_priority()
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    with FileLock(runtime / "runner.lock"):
        gate_evidence = verify_gate(runtime)
        check_no_live_workers(runtime)
        existing_identity_checks(runtime)
        previous = read_json(runtime / "status.json") if (runtime / "status.json").exists() else None
        if gate_evidence.get("recovery_lineage"):
            if previous is None:
                raise ValueError("恢复运行缺少已绑定原状态")
            previous = reconcile_recovered_attempts(previous, gate_evidence["recovery_lineage"],
                                                   sha256(runtime / "status.json"))
        require_reviewed_previous_attempts(previous, retry_failed_jobs)
        state = new_state(previous)
        if retry_failed_jobs:
            state["failure_history"].append({"utc": now(), "reason": "explicit_failed_job_retry",
                                             "task_ids": sorted(set(retry_failed_jobs))})
        gate_sha = sha256(VALIDATION / "engineering_gate.json")
        state["current_gate_sha256"] = gate_sha
        if not any(entry["gate_sha256"] == gate_sha for entry in state["source_lineage"]):
            state["source_lineage"].append({"gate_sha256": gate_sha, "source_hashes": gate_evidence["source_hashes"],
                                            "role": "current_orchestration", "jobs": []})
        if resource_review_note:
            if not previous or previous.get("stop_dispatch_reason") != "48h_resource_review":
                raise ValueError("仅在已达到 48 小时复盘门后使用 --resource-review-note")
            state["resource_reviews"].append({"utc": now(), "note": resource_review_note,
                                             "previous_deadline_unix": state["review_deadline_unix"]})
            state["review_deadline_unix"] = time.time() + 48 * 3600
        validator = ResultValidator()
        try:
            prevalidate_results_before_dispatch(state, gate_evidence, validator)
            save_status(runtime, state)
            validated = execute_queue(runtime, state, workers, validator)
            old = check_old_results()
            complete = state["phase"] == "completed" and len(validated) == 30
            report = validation_report(validated, complete)
            report.update(old_results=old, phase=state["phase"],
                          total_runner_wall_seconds=state["total_runner_wall_seconds"],
                          batch_elapsed_seconds=state["batch_elapsed_seconds"],
                          source_lineage=state["source_lineage"], recovery_incidents=state["recovery_incidents"],
                          failure_history=state["failure_history"], resources=state["resources"],
                          task_status=[{k: row[k] for k in ("id", "job", "state", "attempts", "last_error")}
                                       for row in state["tasks"]])
            write_json(VALIDATION / "summary.json", report)
            return 0 if complete else 2
        except Exception:
            original_error = traceback.format_exc()
            state["phase"] = "review_required"
            state["failure_history"].append({"utc": now(), "error": original_error})
            try:
                save_status(runtime, state)
            except Exception:
                emergency_state(runtime, state, "run_exception_status_failed",
                                dict(original=original_error, status_error=traceback.format_exc()))
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--gate", action="store_true")
    action.add_argument("--run", action="store_true")
    action.add_argument("--plan", action="store_true")
    action.add_argument("--status", action="store_true")
    action.add_argument("--worker", nargs=4, metavar=("TAG", "EQ", "METHOD", "SEED"))
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--resource-review-note", help="达到 48 小时门后，记录资源复盘结论并开启下一检查窗口")
    parser.add_argument("--recovery-manifest", type=Path,
                        help="仅用于 --gate；绑定原门/状态与已结束的孤儿进程 HANDLE 观察，不启动训练")
    parser.add_argument("--retry-failed-job", action="append", default=[],
                        help="仅用于 --run；明确允许重试具有已知失败证据的指定 task id，未知退出仍拒绝")
    parser.add_argument("--set", dest="overrides", action="append", default=[])
    args = parser.parse_args()
    if args.recovery_manifest and not args.gate:
        parser.error("--recovery-manifest 只能与 --gate 使用")
    if args.retry_failed_job and not args.run:
        parser.error("--retry-failed-job 只能与 --run 使用")
    if args.worker:
        tag, eq, method, seed = args.worker
        worker((tag, eq, method, int(seed)), args.overrides, args.runtime)
    elif args.gate:
        with FileLock(args.runtime / "runner.lock"):
            gate(args.runtime, args.recovery_manifest)
    elif args.plan:
        print(json.dumps({"prereg_commit": PREREG, "max_workers": 24, "required_tasks": 30,
                          "jobs": [{"job": list(j), "config": asdict(config(j)),
                                    "command": command_for(j, args.runtime)} for j in ALL_JOBS]},
                         ensure_ascii=False, indent=2))
    elif args.status:
        print(json.dumps(read_json(args.runtime / "status.json") if (args.runtime / "status.json").exists()
                         else {"phase": "not_started", "required_tasks": 30}, ensure_ascii=False, indent=2))
    elif args.run:
        return run(args.runtime, args.workers, args.resource_review_note, args.retry_failed_job)
    else:
        parser.error("请选择 --plan、--gate、--run 或 --status；默认不自动训练")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

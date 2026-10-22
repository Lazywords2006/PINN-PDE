"""Runner-only tests: no research training, no mutation of prior artifacts."""
from dataclasses import asdict
from pathlib import Path
import base64
import copy
import errno
import json
import os
import subprocess
import threading

import numpy as np
import pytest
import torch

import stage6_runner as s


def test_windows_powershell5_reads_bom_and_parses_launcher_without_execution():
    launcher = s.HERE / "run_stage6.ps1"
    assert launcher.read_bytes().startswith(b"\xef\xbb\xbf"), "Windows PowerShell 5 中文脚本须保留 UTF-8 BOM"
    escaped = str(launcher).replace("'", "''")
    script = ("[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false); "
              "$tokens=$null; $parseErrors=$null; "
              f"[System.Management.Automation.Language.Parser]::ParseFile('{escaped}', "
              "[ref]$tokens, [ref]$parseErrors) | Out-Null; "
              "if ($parseErrors.Count -ne 0) { $parseErrors | ForEach-Object { $_.Message }; exit 1 }; "
              "Write-Output ('PARSE_OK_PS' + $PSVersionTable.PSVersion.Major)")
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                             "-EncodedCommand", encoded], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            encoding="utf-8", errors="replace", check=False, timeout=30)
    assert result.returncode == 0, result.stdout
    assert "PARSE_OK_PS5" in result.stdout, result.stdout


def override_args(job):
    return [f"{k}={v}" for k, v in asdict(s.config(job)).items()]


def test_frozen_matrix_budget_and_seed_separation():
    assert len(s.ALL_JOBS) == len(set(s.ALL_JOBS)) == 30
    assert len(s.TAU_JOBS) == 12 and len(s.SOAP_JOBS) == 18
    assert {j[3] for j in s.ALL_JOBS} == {0, 1, 2}
    for job in s.ALL_JOBS:
        cfg = s.config(job)
        assert (cfg.adam_steps, cfg.lbfgs_iters, cfg.nf, cfg.nb, cfg.n0) == (20000, 3000, 4096, 256, 256)
        assert (cfg.nf_fixed, cfg.nb_fixed, cfg.n0_fixed, cfg.width, cfg.depth) == (8192, 512, 512, 64, 4)
        assert cfg.arch == "mlp" and cfg.lr0 == 0.001 and cfg.lr1 == 1e-5
        assert cfg.tau == {"sensitivity_tau003_v1": .03, "sensitivity_tau03_v1": .3,
                           "final_soap64_v1": .1}[job[0]]
        assert cfg.optimizer == ("soap_official64" if job in s.SOAP_JOBS else "adam")


@pytest.mark.parametrize("job", [s.TAU_JOBS[0], s.TAU_JOBS[-1], s.SOAP_JOBS[0], s.SOAP_JOBS[-1]])
def test_worker_cli_roundtrip_all_fields_no_nested_pool(job, tmp_path):
    command = s.command_for(job, tmp_path)
    assert "--worker" in command and "--workers" not in command
    overrides = [command[i + 1] for i, arg in enumerate(command) if arg == "--set"]
    parsed = s.worker_config(job, overrides)
    assert parsed == {k: v for k, v in asdict(s.config(job)).items() if k != "seed"}
    assert s.checkpoint(job, tmp_path).name == s.task_id(job) + ".ckpt"


@pytest.mark.parametrize("bad_job", [
    ("final_soap64_v1", "E1_heat", "vanilla", 100),
    ("soap1e3", "E1_heat", "vanilla", 0),
    ("sensitivity_tau003_v1", "E1_heat", "vanilla", 0),
    ("final_soap64_v1", "E1_heat_cos", "hardic", 0)])
def test_unregistered_tasks_rejected(bad_job):
    with pytest.raises(ValueError):
        s.config(bad_job)


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "steps", "seed", "unknown"])
def test_worker_refuses_configuration_drift(mutation):
    job = s.ALL_JOBS[0]
    args = override_args(job)
    if mutation == "duplicate":
        args.append("tau=0.03")
    elif mutation == "missing":
        args.remove("tau=0.03")
    elif mutation == "steps":
        args[args.index("adam_steps=20000")] = "adam_steps=19999"
    elif mutation == "seed":
        args[args.index("seed=0")] = "seed=100"
    else:
        args.append("unspecified=5")
    with pytest.raises(ValueError):
        s.worker_config(job, args)


def test_lock_rejects_duplicate_writer_and_allows_stale_file(tmp_path):
    path = tmp_path / "task.lock"
    with s.FileLock(path):
        with pytest.raises(RuntimeError):
            with s.FileLock(path):
                pytest.fail("duplicate lock acquired")
    with s.FileLock(path):
        assert path.exists()


def test_orphan_worker_lock_blocks_queue_restart(tmp_path):
    with s.worker_lock(s.ALL_JOBS[7], tmp_path):
        with pytest.raises(RuntimeError):
            s.check_no_live_workers(tmp_path)


@pytest.mark.parametrize("physical,commit,allowed", [(4, .90, True), (3.99, .1, False),
                                                   (20, .901, False), (20, .89, True)])
def test_memory_dispatch_boundary(physical, commit, allowed):
    assert s.resources_allow_dispatch({"available_physical_gib": physical,
                                       "commit_used_fraction": commit}) is allowed


def test_worker_runtime_environment_single_thread_and_d_drive(tmp_path):
    env = s.worker_environment(tmp_path)
    for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        assert env[key] == "1"
    for key in ("TEMP", "TMP", "PYTHONPYCACHEPREFIX"):
        assert env[key].startswith("D:\\CodexRuntime\\")
    assert env["R33_CKPT_DIR"] == str(tmp_path / "checkpoints")


class FakeClock:
    def __init__(self):
        self.value = 0.

    def __call__(self):
        return self.value

    def sleep(self, amount):
        self.value += amount


def queue_fixture(monkeypatch, tmp_path, durations, exits=None, workers=2,
                  deadline=100, memory=None, validation_error=False, launch_error=False,
                  persist_error_after=None, persist_recovers_at=None, report_error=False):
    clock, children, persisted = FakeClock(), [], []
    state = s.new_state()
    state["tasks"] = state["tasks"][:len(durations)]
    state["review_deadline_unix"] = deadline
    exits = exits or [0] * len(durations)

    class Child:
        def __init__(self, index):
            self.pid = 100 + index
            self.index = index
            self.ends = clock() + durations[index]

        def poll(self):
            return exits[self.index] if clock() >= self.ends else None

    def popen(command, **kwargs):
        if launch_error:
            raise OSError("simulated launch failure")
        assert "--worker" in command and "--workers" not in command
        assert kwargs["env"]["OMP_NUM_THREADS"] == "1"
        child = Child(len(children))
        children.append(child)
        return child

    def validate(job):
        if validation_error:
            raise ValueError("simulated corrupt bundle")
        return {"job": list(job), "complete_and_recomputed": True}

    def persist(runtime, current):
        persisted.append(copy.deepcopy(current))
        if (persist_error_after is not None and len(persisted) >= persist_error_after and
                (persist_recovers_at is None or len(persisted) < persist_recovers_at)):
            raise PermissionError("simulated permanent status replacement denial")

    def report(*args, **kwargs):
        if report_error:
            raise PermissionError("simulated validation report replacement denial")

    monkeypatch.setattr(s, "validation_report", report)
    result = s.execute_queue(tmp_path, state, workers, validate, popen=popen,
                             memory=memory or (lambda: {"available_physical_gib": 20,
                                                       "commit_used_fraction": .4}),
                             sleep=clock.sleep, clock=clock, persist=persist, dispatch_interval=0)
    return state, children, result, persisted, clock()


def test_queue_obeys_bound_and_completes_every_task(monkeypatch, tmp_path):
    state, children, rows, snapshots, _ = queue_fixture(monkeypatch, tmp_path, [8, 8, 8, 8, 8])
    assert len(children) == len(rows) == 5 and state["phase"] == "completed"
    assert max(sum(r["state"] == "running" for r in snap["tasks"]) for snap in snapshots) == 2
    assert all(row["attempts"][0]["exit_code"] == 0 for row in state["tasks"])


def test_worker_failure_stops_dispatch_and_drains_active(monkeypatch, tmp_path):
    state, children, rows, _, elapsed = queue_fixture(monkeypatch, tmp_path, [6, 10, 10], exits=[1, 0, 0])
    assert len(children) == 2 and len(rows) == 1 and elapsed >= 12
    assert [r["state"] for r in state["tasks"]] == ["failed", "completed", "queued"]
    assert state["stop_dispatch_reason"] == "engineering_failure"
    assert state["tasks"][0]["attempts"][0]["exit_code"] == 1


def test_validation_failure_is_recorded_not_filtered(monkeypatch, tmp_path):
    state, children, rows, _, _ = queue_fixture(monkeypatch, tmp_path, [2, 20], validation_error=True)
    assert len(children) == 1 and not rows
    assert state["tasks"][0]["state"] == "failed"
    assert "corrupt bundle" in state["tasks"][0]["last_error"]


def test_launch_failure_records_attempt_and_stops(monkeypatch, tmp_path):
    state, children, _, _, _ = queue_fixture(monkeypatch, tmp_path, [8, 8], launch_error=True)
    assert not children and state["tasks"][0]["state"] == "failed"
    assert "launch_error" in state["tasks"][0]["attempts"][0]
    assert state["tasks"][1]["state"] == "queued"


def test_48h_stops_new_dispatch_without_terminating_children(monkeypatch, tmp_path):
    state, children, rows, _, elapsed = queue_fixture(monkeypatch, tmp_path, [8, 8, 8], deadline=3)
    assert len(children) == len(rows) == 2 and elapsed >= 10
    assert state["stop_dispatch_reason"] == "48h_resource_review"
    assert state["tasks"][-1]["state"] == "queued"
    assert state["phase"] == "review_required"


def test_memory_pause_resumes_without_changing_configs(monkeypatch, tmp_path):
    calls = []

    def memory():
        calls.append(None)
        return {"available_physical_gib": 2 if len(calls) < 4 else 20,
                "commit_used_fraction": .4}

    state, children, rows, _, _ = queue_fixture(monkeypatch, tmp_path, [4, 4], memory=memory)
    assert len(children) == len(rows) == 2
    assert state["tasks"][0]["attempts"][0]["started_unix"] >= 6
    assert all(r["config"]["adam_steps"] == 20000 for r in state["tasks"])


@pytest.mark.parametrize("workers", [0, 25])
def test_worker_cap_rejects_invalid_values(workers, tmp_path):
    with pytest.raises(ValueError):
        s.execute_queue(tmp_path, s.new_state(), workers, None)


def test_resume_preserves_identity_attempts_and_failure_history():
    prior = s.new_state()
    prior["tasks"][0]["state"] = "failed"
    prior["tasks"][0]["attempts"] = [{"exit_code": 1, "wall_seconds": 100}]
    prior["failure_history"] = [{"error": "recorded"}]
    prior["total_runner_wall_seconds"] = 100
    resumed = s.new_state(prior)
    assert resumed["tasks"][0]["job"] == prior["tasks"][0]["job"]
    assert resumed["tasks"][0]["config"] == prior["tasks"][0]["config"]
    assert resumed["tasks"][0]["attempts"] == prior["tasks"][0]["attempts"]
    assert resumed["tasks"][0]["state"] == "queued"
    assert resumed["failure_history"] == prior["failure_history"]
    assert resumed["prior_runner_wall_seconds"] == 100
    assert resumed["review_deadline_unix"] == prior["review_deadline_unix"]


def test_existing_result_is_revalidated_and_never_dispatched(monkeypatch, tmp_path):
    job = s.ALL_JOBS[0]
    path = tmp_path / "result.json"
    path.write_text("{}")
    monkeypatch.setattr(s, "HERE", tmp_path)
    monkeypatch.setattr(s, "ALL_JOBS", [job])
    monkeypatch.setattr(s, "out_path", lambda *args: path)
    called = []

    def load(path, **kwargs):
        called.append(kwargs)
        return None, {}, "complete"

    monkeypatch.setattr(s, "load_result", load)
    rows = s.existing_identity_checks(tmp_path)
    assert len(rows) == 1 and called[0]["expected_job"] == (job[1], job[2], job[3], job[0])
    assert called[0]["expected_config"] == s.config(job)


def test_partial_bundle_without_checkpoint_rejected(monkeypatch, tmp_path):
    job = s.ALL_JOBS[0]
    path = tmp_path / "result.json"
    path.with_suffix(".pt").write_bytes(b"partial")
    monkeypatch.setattr(s, "HERE", tmp_path)
    monkeypatch.setattr(s, "ALL_JOBS", [job])
    monkeypatch.setattr(s, "out_path", lambda *args: path)
    with pytest.raises(ValueError, match="不完整结果"):
        s.existing_identity_checks(tmp_path)


def test_complete_task_not_redispatched_by_queue(monkeypatch, tmp_path):
    state = s.new_state()
    state["tasks"] = state["tasks"][:1]
    row = state["tasks"][0]
    row.update(state="completed", validation={"job": row["job"]})
    result = s.execute_queue(tmp_path, state, 24, lambda j: pytest.fail("revalidation already done"),
                             popen=lambda *a, **k: pytest.fail("must not launch completed task"),
                             persist=lambda *a: None)
    assert len(result) == 1 and state["phase"] == "completed"


def test_frozen_original_test_sources_and_398_data_current():
    assert s.check_reused_tests()["tests"] == 71
    assert s.check_old_results()["files"] == 398
    s.check_preregistration()
    assert s.check_vendor_source()["passed"]


def test_checkpoint_progress_uses_stat_cache(monkeypatch, tmp_path):
    job = s.ALL_JOBS[0]
    path = s.checkpoint(job, tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"1")
    calls = []

    def load(*a, **k):
        calls.append(None)
        return {"state": {"phase": "adam", "step": 500 * len(calls), "done": 0, "elapsed": 20},
                "hist": {"resumed_at": []}}

    monkeypatch.setattr(s.torch, "load", load)
    assert s.checkpoint_progress(job, tmp_path)["adam_step"] == 500
    assert s.checkpoint_progress(job, tmp_path)["adam_step"] == 500
    assert len(calls) == 1
    path.write_bytes(b"22")
    assert s.checkpoint_progress(job, tmp_path)["adam_step"] == 1000
    assert len(calls) == 2
    path.unlink()
    assert "phase" not in s.checkpoint_progress(job, tmp_path)


def test_worker_calls_existing_api_without_seed_collision(monkeypatch, tmp_path):
    job = s.SOAP_JOBS[-1]
    monkeypatch.setattr(s, "verify_gate", lambda *a: None)
    monkeypatch.setattr(s, "normal_priority", lambda: None)
    monkeypatch.setattr(s.torch, "set_num_threads", lambda *a: None)
    monkeypatch.setattr(s.torch, "set_num_interop_threads", lambda *a: None)
    calls = []
    monkeypatch.setattr(s, "run_one", lambda value: calls.append(value))
    s.worker(job, override_args(job), tmp_path)
    assert len(calls) == 1
    eq, method, seed, overrides, tag = calls[0]
    assert (tag, eq, method, seed) == job
    assert "seed" not in overrides and overrides["optimizer"] == "soap_official64"


@pytest.mark.parametrize("mode", ["valid_soap", "wrong_calls", "bad_stop", "bad_dense", "legacy"])
def test_result_validation_checks_budget_dense_grid_and_soap_accounting(monkeypatch, mode):
    job = s.SOAP_JOBS[0]
    record = {"metrics": {"vol": [0.] * 5, "trace": [0.] * 5}, "max_vol": 0., "max_trace": 0.,
              "config": asdict(s.config(job)), "delta": -1., "final_adam_loss": 1e-3,
              "final_lbfgs_loss": 1e-5, "adam_seconds": 100,
              "wall_seconds": 120, "history": {"adam_gradient_calls": 20000,
              "lbfgs_budget_used": 3000, "lbfgs_stop_reason": "budget_exhausted",
              "lbfgs_func_evals": 3200, "lbfgs_n_iter": 3000}}
    if mode == "wrong_calls":
        record["history"]["adam_gradient_calls"] = 19999
    elif mode == "bad_stop":
        record["history"]["lbfgs_stop_reason"] = "interrupted"

    class Model:
        def __call__(self, x, t):
            return torch.ones_like(x)

    monkeypatch.setattr(s, "load_result", lambda *a, **k: (Model(), record, "legacy" if mode == "legacy" else "complete"))
    monkeypatch.setattr(s, "get_reference", lambda *a: (lambda x, t: np.ones_like(x) * (2 if mode == "bad_dense" else 1)))
    monkeypatch.setattr(s, "evaluate", lambda *a: record["metrics"])
    monkeypatch.setattr(s, "heldout_residuals", lambda *a: {"pde": {"rms": 0.}})
    monkeypatch.setattr(s, "sha256", lambda *a: "synthetic-hash")
    validator = s.ResultValidator()
    if mode == "valid_soap":
        row = validator(job)
        assert row["optimizer_accounting"]["first_call_initializes_only"]
        assert row["optimizer_accounting"]["parameter_updates_inferred_from_frozen_optimizer_semantics"] == 19999
        assert row["history_counters"]["lbfgs_func_evals"] == 3200
    else:
        with pytest.raises(ValueError):
            validator(job)


def test_json_replace_transient_denial_retries_without_truncating_destination(monkeypatch, tmp_path):
    path = tmp_path / "status.json"
    path.write_text('{"old": true}', encoding="utf-8")
    original, calls, delays = s.os.replace, [], []

    def blocked_then_replace(source, target):
        calls.append(None)
        if len(calls) < 3:
            assert json.loads(path.read_text()) == {"old": True}
            raise PermissionError("transient sharing denial")
        return original(source, target)

    monkeypatch.setattr(s.os, "replace", blocked_then_replace)
    monkeypatch.setattr(s.time, "sleep", delays.append)
    s.write_json(path, {"new": True})
    assert s.read_json(path) == {"new": True}
    assert len(calls) == 3 and delays == [.05, .1]
    assert not list(tmp_path.glob("*.tmp"))


def test_json_permanent_denial_is_bounded_and_retains_only_one_complete_temp(monkeypatch, tmp_path):
    path = tmp_path / "status.json"
    path.write_text('{"old": true}', encoding="utf-8")
    calls, delays = [], []

    def denied(*args):
        calls.append(None)
        raise PermissionError("permanent denial")

    monkeypatch.setattr(s.os, "replace", denied)
    monkeypatch.setattr(s.time, "sleep", delays.append)
    for value in (1, 2, 3):
        with pytest.raises(PermissionError):
            s.write_json(path, {"new": value})
    assert len(calls) == 3 * (len(s._REPLACE_DELAYS) + 1)
    assert len(delays) == 3 * len(s._REPLACE_DELAYS)
    assert s.read_json(path) == {"old": True}
    temps = list(tmp_path.glob("*.tmp"))
    assert len(temps) == 1 and s.read_json(temps[0]) == {"new": 3}


def test_non_sharing_io_failure_is_not_retried(monkeypatch, tmp_path):
    def no_space(*args):
        raise OSError(errno.ENOSPC, "full disk")

    monkeypatch.setattr(s.os, "replace", no_space)
    monkeypatch.setattr(s.time, "sleep", lambda *a: pytest.fail("must not retry unrelated error"))
    with pytest.raises(OSError) as exc:
        s.write_json(tmp_path / "status.json", {})
    assert exc.value.errno == errno.ENOSPC


def test_shared_reader_allows_rename_and_preserves_detached_old_bytes(tmp_path):
    path = tmp_path / "status.json"
    s.write_json(path, {"version": "old"})
    with s.open_shared_read(path) as reader:
        # FILE_SHARE_DELETE enables rename. It does not guarantee MoveFileEx
        # can replace an existing open destination on this Windows machine.
        os.rename(path, tmp_path / "detached.json")
        s.write_json(path, {"version": "new"})
        assert json.loads(reader.read()) == {"version": "old"}
    assert s.read_json(path) == {"version": "new"}


def test_native_windows_transient_reader_lock_is_retried(tmp_path):
    from ctypes import wintypes
    kernel = s.ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  s.ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    path = tmp_path / "status.json"
    s.write_json(path, {"old": True})
    handle = kernel.CreateFileW(str(path), 0x80000000, 3, None, 3, 0x80, None)
    assert handle != s.ctypes.c_void_p(-1).value
    release = threading.Timer(.25, lambda: kernel.CloseHandle(handle))
    release.start()
    try:
        s.write_json(path, {"new": True})
    finally:
        release.join()
    assert s.read_json(path) == {"new": True}


def test_checkpoint_load_deserializes_detached_shared_snapshot(monkeypatch, tmp_path):
    job = s.ALL_JOBS[0]
    path = s.checkpoint(job, tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"old checkpoint")

    def load(stream, **kwargs):
        assert isinstance(stream, s.io.BytesIO) and stream.getvalue() == b"old checkpoint"
        replacement = path.with_suffix(".replacement")
        replacement.write_bytes(b"new checkpoint")
        os.replace(replacement, path)
        return {"state": {"phase": "adam", "step": 500, "done": 0}, "hist": {}}

    monkeypatch.setattr(s.torch, "load", load)
    assert s.checkpoint_progress(job, tmp_path)["adam_step"] == 500
    assert path.read_bytes() == b"new checkpoint"


def test_active_checkpoint_progress_never_opens_or_deserializes_file(monkeypatch, tmp_path):
    job = s.ALL_JOBS[0]
    path = s.checkpoint(job, tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"active writer snapshot")
    monkeypatch.setattr(s, "open_shared_read", lambda *a: pytest.fail("must not open active checkpoint"))
    monkeypatch.setattr(s.torch, "load", lambda *a, **k: pytest.fail("must not deserialize active checkpoint"))
    row = s.checkpoint_progress(job, tmp_path, metadata_only=True)
    assert row["checkpoint_metadata_only"] and row["checkpoint_size_bytes"] == path.stat().st_size
    assert "phase" not in row and "progress_unavailable_reason" in row


def test_checkpoint_held_worker_lock_blocks_read_even_when_caller_requests_parse(monkeypatch, tmp_path):
    job = s.ALL_JOBS[0]
    path = s.checkpoint(job, tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"still active")
    monkeypatch.setattr(s, "open_shared_read", lambda *a: pytest.fail("must not open locked checkpoint"))
    with s.worker_lock(job, tmp_path):
        row = s.checkpoint_progress(job, tmp_path)
    assert row["checkpoint_metadata_only"] and "phase" not in row
    assert "持有锁" in row["progress_read_error"]


def test_save_status_requests_metadata_only_for_every_running_task(monkeypatch, tmp_path):
    state = s.new_state()
    state["tasks"] = state["tasks"][:2]
    state["tasks"][0]["state"] = "running"
    state["tasks"][1]["state"] = "failed"
    calls = []

    def progress(job, runtime, *, metadata_only=False):
        calls.append((job, metadata_only))
        return {"checkpoint_metadata_only": metadata_only}

    monkeypatch.setattr(s, "checkpoint_progress", progress)
    s.save_status(tmp_path, state)
    assert calls == [(tuple(state["tasks"][0]["job"]), True), (tuple(state["tasks"][1]["job"]), False)]


def test_permanent_status_failure_stops_dispatch_and_drains_every_active(monkeypatch, tmp_path):
    state, children, rows, _, elapsed = queue_fixture(monkeypatch, tmp_path, [8, 12, 20],
                                                      persist_error_after=2)
    assert len(children) == len(rows) == 2 and elapsed >= 14
    assert state["phase"] == "review_required"
    assert state["stop_dispatch_reason"] == "status_persistence_failure"
    assert [row["state"] for row in state["tasks"]] == ["completed", "completed", "queued"]
    assert all(row["pid"] is None and row["attempts"][-1]["exit_code"] == 0 for row in state["tasks"][:2])
    snapshots = [s.read_json(path) for path in (tmp_path / "emergency").glob("*.json")]
    assert sum(x["where"] == "worker_exit_during_drain" for x in snapshots) == 2
    assert any(x["where"] == "queue_final_unpersisted" for x in snapshots)
    assert state["status_persistence_failures"] <= 3  # retry throttled while polling continues


def test_write_recovery_does_not_resume_dispatch_after_persistence_failure(monkeypatch, tmp_path):
    state, children, _, snapshots, _ = queue_fixture(monkeypatch, tmp_path, [8, 12, 20],
        persist_error_after=2, persist_recovers_at=3)
    assert len(children) == 2 and state["phase"] == "review_required"
    assert snapshots[-1]["stop_dispatch_reason"] == "status_persistence_failure"


def test_validation_report_failure_stops_dispatch_and_drains(monkeypatch, tmp_path):
    state, children, _, _, elapsed = queue_fixture(monkeypatch, tmp_path, [8, 12, 20], report_error=True)
    assert len(children) == 2 and elapsed >= 14
    assert state["phase"] == "review_required"
    assert state["stop_dispatch_reason"] == "engineering_failure"
    assert state["tasks"][-1]["state"] == "queued"
    assert all(row["pid"] is None and row["attempts"][-1]["exit_code"] == 0 for row in state["tasks"][:2])


def test_final_status_failure_never_claims_completed(monkeypatch, tmp_path):
    state = s.new_state()
    state["tasks"] = state["tasks"][:1]
    state["tasks"][0].update(state="completed", validation={"job": state["tasks"][0]["job"]})

    def denied(*args):
        raise PermissionError("final denied")

    s.execute_queue(tmp_path, state, 1, None, persist=denied)
    assert state["phase"] == "review_required"
    assert state["stop_dispatch_reason"] == "status_persistence_failure"


def test_outer_exception_preserves_original_when_emergency_status_also_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(s, "verify_gate", lambda *a: {"source_hashes": {}})
    monkeypatch.setattr(s, "check_no_live_workers", lambda *a: None)
    monkeypatch.setattr(s, "existing_identity_checks", lambda *a: None)
    monkeypatch.setattr(s, "normal_priority", lambda: None)
    monkeypatch.setattr(s.torch, "set_num_threads", lambda *a: None)
    monkeypatch.setattr(s.torch, "set_num_interop_threads", lambda *a: None)
    monkeypatch.setattr(s, "sha256", lambda *a: "test-gate")
    monkeypatch.setattr(s, "out_path", lambda *a: tmp_path / "no-result.json")
    calls = []

    def denied(*args):
        calls.append(None)
        if len(calls) == 1:
            raise ValueError("original persistence error")
        raise PermissionError("secondary persistence error")

    monkeypatch.setattr(s, "save_status", denied)
    with pytest.raises(ValueError, match="original persistence error"):
        s.run(tmp_path, 1)
    assert len(calls) == 2
    snapshots = list((tmp_path / "emergency").glob("*.json"))
    assert len(snapshots) == 1 and "secondary persistence error" in snapshots[0].read_text()


def recovery_fixture(monkeypatch, tmp_path):
    """Synthetic identity/exit evidence only; no process or research model runs."""
    jobs = s.ALL_JOBS[:2]
    monkeypatch.setattr(s, "ALL_JOBS", jobs)
    current = {"pinn1d.py": "training", "SCREEN_PROTOCOL.md": "protocol", "stage6_runner.py": "patched"}
    original = dict(current, **{"stage6_runner.py": "original"})
    monkeypatch.setattr(s, "source_hashes", lambda: current)
    results = tmp_path / "results"
    results.mkdir()
    monkeypatch.setattr(s, "out_path", lambda *job: results / (s.task_id(job) + ".json"))
    s.out_path(*jobs[0]).write_text("{}", encoding="utf-8")
    prior = s.new_state()
    row = prior["tasks"][0]
    command = s.command_for(jobs[0], tmp_path)
    row.update(state="running", pid=101, command=command,
               attempts=[{"pid": 101, "command": command, "started_unix": 100.}])
    prior_gate = {"passed": True, "prereg_commit": s.PREREG, "runtime": str(tmp_path.resolve()),
                  "source_hashes": original, "tasks": [list(j) for j in jobs]}
    prior_gate_path, prior_status_path = tmp_path / "prior_gate.json", tmp_path / "prior_status.json"
    s.write_json(prior_gate_path, prior_gate)
    s.write_json(prior_status_path, prior)
    processes, attached, exits = [], [], []
    for pid, ppid, role in ((101, prior["runner_pid"], "launcher"), (102, 101, "worker")):
        sampled = {"pid": pid, "ppid": ppid, "creation_filetime_utc": 100000 + pid,
                   "executable_path": "C:\\synthetic\\python.exe", "command_line": json.dumps(command)}
        processes.append(sampled)
        attached.append(dict(sampled, event="attached", utc="1970-01-01T00:02:00+00:00",
                             argv=command, role=role, job=list(jobs[0])))
        exits.append({"event": "process_exited", "utc": "1970-01-01T00:03:20+00:00",
                      "pid": pid, "exit_code": 0, "identity_verified": True, "role": role,
                      "job": list(jobs[0]), "creation_filetime_utc": sampled["creation_filetime_utc"]})
    inventory = {"tasks": prior["tasks"], "original_gate_sha256": s.sha256(prior_gate_path),
                 "original_runner_pid": prior["runner_pid"], "workers": processes}
    inventory_path = tmp_path / "process_inventory.json"
    s.write_json(inventory_path, inventory)
    observer_path = tmp_path / "synthetic_observer.py"
    observer_path.write_text("# synthetic test source, never executed\n", encoding="utf-8")
    events = [{"event": "observer_started", "snapshot_sha256": s.sha256(inventory_path),
               "observer_source_sha256": s.sha256(observer_path),
               "original_gate_sha256": s.sha256(prior_gate_path)}, *attached, *exits,
              {"event": "observer_completed", "all_handles_signaled": True}]
    events_path = tmp_path / "events.jsonl"
    events_path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    error_path = tmp_path / "runner.stderr.log"
    error_path.write_text("synthetic WinError 5 fixture\n", encoding="utf-8")
    incident_path = tmp_path / "snapshot_manifest.json"
    s.write_json(incident_path, {"files": [{"snapshot": str(prior_gate_path), "sha256": s.sha256(prior_gate_path)}]})
    paths = dict(prior_gate=prior_gate_path, prior_status=prior_status_path, process_inventory=inventory_path,
                 observer_events=events_path, observer_source=observer_path, runner_stderr=error_path,
                 incident_manifest=incident_path)
    manifest = {"schema": "r33_stage6_recovery_manifest_v1", "incident_id": "synthetic-incident",
                "artifacts": {key: {"path": str(path), "sha256": s.sha256(path)} for key, path in paths.items()}}
    manifest_path = tmp_path / "recovery_manifest.json"
    s.write_json(manifest_path, manifest)
    return dict(jobs=jobs, current=current, original=original, prior=prior, paths=paths,
                events=events, manifest=manifest, manifest_path=manifest_path)


def bind_changed_events(fixture):
    path = fixture["paths"]["observer_events"]
    path.write_text("".join(json.dumps(e) + "\n" for e in fixture["events"]), encoding="utf-8")
    fixture["manifest"]["artifacts"]["observer_events"]["sha256"] = s.sha256(path)
    s.write_json(fixture["manifest_path"], fixture["manifest"])


def timestamp_inventory_fixture():
    stamp = "2026-10-22T16:08:04.387960+00:00"
    return [{"pid": 101, "started_utc": stamp, "config": {"width": 64},
             "attempts": [{"pid": 101, "started_utc": stamp, "command": ["python", "--worker"]}]}]


@pytest.mark.parametrize("converted", ["2026-10-23T00:08:04.38796+08:00",
                                       "2026-10-22T16:08:04.3879600Z",
                                       "2026-10-22T10:38:04.387960-05:30"])
def test_recovery_inventory_accepts_only_same_instants_at_explicit_time_paths(converted):
    prior = timestamp_inventory_fixture()
    observed = copy.deepcopy(prior)
    observed[0]["started_utc"] = converted
    observed[0]["attempts"][0]["started_utc"] = converted
    assert s.same_recovery_inventory_tasks(observed, prior)
    assert s.same_recovery_inventory_tasks(prior, observed)


@pytest.mark.parametrize("location", ["task", "attempt"])
@pytest.mark.parametrize("invalid", ["2026-10-22T16:08:04.387960", "2026-02-30T16:08:04.387960+00:00",
                                     "2026-10-22T16:08:05.387960+00:00", "2026-10-22T16:08:04.3879601+00:00",
                                     "2026-10-23T00:08:04.387960+08:99", None])
def test_recovery_inventory_rejects_naive_invalid_or_moved_time(location, invalid):
    prior = timestamp_inventory_fixture()
    observed = copy.deepcopy(prior)
    row = observed[0] if location == "task" else observed[0]["attempts"][0]
    row["started_utc"] = invalid
    assert not s.same_recovery_inventory_tasks(observed, prior)


@pytest.mark.parametrize("invalid", ["2026-10-22T16:08:04", "2026-02-30T16:08:04+00:00", "invalid"])
def test_recovery_inventory_does_not_accept_identical_invalid_timestamps(invalid):
    prior = timestamp_inventory_fixture()
    prior[0]["started_utc"] = invalid
    assert not s.same_recovery_inventory_tasks(copy.deepcopy(prior), prior)


@pytest.mark.parametrize("mutation", ["pid", "config", "command", "missing", "extra", "type", "other_time_field"])
def test_recovery_inventory_requires_exact_non_time_values_and_structure(mutation):
    prior = timestamp_inventory_fixture()
    observed = copy.deepcopy(prior)
    if mutation == "pid":
        observed[0]["pid"] += 1
    elif mutation == "config":
        observed[0]["config"]["width"] += 1
    elif mutation == "command":
        observed[0]["attempts"][0]["command"][-1] = "--different"
    elif mutation == "missing":
        observed[0].pop("started_utc")
    elif mutation == "extra":
        observed[0]["ignored"] = "must not be ignored"
    elif mutation == "type":
        observed[0]["pid"] = 101.0
    else:
        prior[0]["config"]["started_utc"] = "2026-10-22T16:08:04.387960+00:00"
        observed[0]["config"]["started_utc"] = "2026-10-23T00:08:04.38796+08:00"
    assert not s.same_recovery_inventory_tasks(observed, prior)


@pytest.mark.parametrize("mutation", ["equivalent", "moved_time", "pid", "config"])
def test_recovery_lineage_binds_timezone_converted_inventory_without_weakening_identity(monkeypatch, tmp_path,
                                                                                      mutation):
    fixture = recovery_fixture(monkeypatch, tmp_path)
    prior = fixture["prior"]
    stamp = "1970-01-01T00:01:40.000000+00:00"
    prior["tasks"][0]["started_utc"] = stamp
    prior["tasks"][0]["attempts"][0]["started_utc"] = stamp
    s.write_json(fixture["paths"]["prior_status"], prior)
    inventory = s.read_json(fixture["paths"]["process_inventory"])
    inventory["tasks"] = copy.deepcopy(prior["tasks"])
    row = inventory["tasks"][0]
    row["started_utc"] = row["attempts"][0]["started_utc"] = "1970-01-01T08:01:40+08:00"
    if mutation == "moved_time":
        row["attempts"][0]["started_utc"] = "1970-01-01T08:01:40.0000001+08:00"
    elif mutation == "pid":
        row["pid"] += 1
    elif mutation == "config":
        row["config"]["width"] += 1
    s.write_json(fixture["paths"]["process_inventory"], inventory)
    for key in ("prior_status", "process_inventory"):
        fixture["manifest"]["artifacts"][key]["sha256"] = s.sha256(fixture["paths"][key])
    fixture["events"][0]["snapshot_sha256"] = s.sha256(fixture["paths"]["process_inventory"])
    bind_changed_events(fixture)
    if mutation == "equivalent":
        lineage = s.recovery_lineage(fixture["manifest_path"], tmp_path)
        assert lineage["original_active_jobs"] == [list(fixture["jobs"][0])]
        assert len(lineage["reconciled"]) == 1
    else:
        with pytest.raises(ValueError, match="进程身份清单"):
            s.recovery_lineage(fixture["manifest_path"], tmp_path)


def test_recovery_binds_original_sources_exit_observations_and_preserves_deadline(monkeypatch, tmp_path):
    fixture = recovery_fixture(monkeypatch, tmp_path)
    lineage = s.recovery_lineage(fixture["manifest_path"], tmp_path)
    recovered = s.reconcile_recovered_attempts(fixture["prior"], lineage,
                                              s.sha256(fixture["paths"]["prior_status"]))
    attempt = recovered["tasks"][0]["attempts"][0]
    assert attempt["exit_code"] == attempt["worker_exit_code"] == 0
    assert attempt["source_gate_sha256"] == lineage["prior_gate_sha256"]
    assert attempt["wall_seconds"] == 100 and attempt["supervision_interrupted"]
    assert "exit_code" not in fixture["prior"]["tasks"][0]["attempts"][0]
    assert recovered["source_lineage"][0]["source_hashes"] == fixture["original"]
    resumed = s.new_state(recovered)
    assert resumed["review_deadline_unix"] == fixture["prior"]["review_deadline_unix"]
    assert resumed["failure_history"][0]["reason"] == "runner_permission_error_orphaned_workers"
    assert resumed["applied_recoveries"] == [lineage["manifest"]["sha256"]]
    s.require_reviewed_previous_attempts(recovered)
    assert s.reconcile_recovered_attempts(recovered, lineage, "new-status-hash") is recovered


@pytest.mark.parametrize("mutation", ["missing_exit", "duplicate_exit", "command", "creation", "parent",
                                      "nonzero_exit", "unverified_exit", "missing_complete", "false_complete",
                                      "missing_result", "scientific_source", "hash_changed"])
def test_recovery_rejects_incomplete_mismatched_failed_or_changed_evidence(monkeypatch, tmp_path, mutation):
    fixture = recovery_fixture(monkeypatch, tmp_path)
    events = fixture["events"]
    if mutation == "missing_exit":
        events.pop(-2)
    elif mutation == "duplicate_exit":
        events.insert(-1, copy.deepcopy(events[-2]))
    elif mutation == "command":
        events[2]["argv"] = ["python", "different args"]
    elif mutation == "creation":
        events[2]["creation_filetime_utc"] += 100
    elif mutation == "parent":
        events[2]["ppid"] = 999
    elif mutation == "nonzero_exit":
        events[-2]["exit_code"] = 259
    elif mutation == "unverified_exit":
        events[-2]["identity_verified"] = False
    elif mutation == "missing_complete":
        events.pop()
    elif mutation == "false_complete":
        events[-1]["all_handles_signaled"] = False
    elif mutation == "missing_result":
        s.out_path(*fixture["jobs"][0]).unlink()
    elif mutation == "scientific_source":
        fixture["current"]["pinn1d.py"] = "unauthorized change"
    elif mutation == "hash_changed":
        fixture["paths"]["observer_source"].write_text("changed", encoding="utf-8")
    bind_changed_events(fixture)
    with pytest.raises(ValueError):
        s.recovery_lineage(fixture["manifest_path"], tmp_path)


def test_recovery_manifest_cannot_change_after_gate(monkeypatch, tmp_path):
    fixture = recovery_fixture(monkeypatch, tmp_path)
    lineage = s.recovery_lineage(fixture["manifest_path"], tmp_path)
    s.verify_recovery_bindings(lineage)
    fixture["manifest_path"].write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="冻结恢复证据变化"):
        s.verify_recovery_bindings(lineage)


def test_recovery_refuses_to_overwrite_unreviewed_status(monkeypatch, tmp_path):
    fixture = recovery_fixture(monkeypatch, tmp_path)
    lineage = s.recovery_lineage(fixture["manifest_path"], tmp_path)
    with pytest.raises(ValueError, match="status"):
        s.reconcile_recovered_attempts(fixture["prior"], lineage, "different-status")


def test_unknown_exit_never_retries_and_known_failure_requires_explicit_job():
    prior = s.new_state()
    row = prior["tasks"][0]
    row.update(state="running", attempts=[{"pid": 100}])
    with pytest.raises(ValueError, match="实测退出"):
        s.require_reviewed_previous_attempts(prior, [row["id"]])
    row.update(state="failed", attempts=[{"pid": 100, "exit_code": 1}])
    with pytest.raises(ValueError, match="逐项明确"):
        s.require_reviewed_previous_attempts(prior)
    s.require_reviewed_previous_attempts(prior, [row["id"]])
    with pytest.raises(ValueError, match="没有失败证据"):
        s.require_reviewed_previous_attempts(prior, [row["id"], "unknown-job"])


@pytest.mark.parametrize("invalid_original_bundle", [False, True])
def test_recovery_validates_old_result_before_any_new_dispatch_and_binds_new_gate(monkeypatch, tmp_path,
                                                                               invalid_original_bundle):
    fixture = recovery_fixture(monkeypatch, tmp_path)
    lineage = s.recovery_lineage(fixture["manifest_path"], tmp_path)
    (tmp_path / "status.json").write_bytes(fixture["paths"]["prior_status"].read_bytes())
    validation = tmp_path / "validation"
    validation.mkdir()
    monkeypatch.setattr(s, "VALIDATION", validation)
    gate = {"source_hashes": fixture["current"], "recovery_lineage": lineage}
    s.write_json(validation / "engineering_gate.json", gate)
    monkeypatch.setattr(s, "verify_gate", lambda *a: gate)
    monkeypatch.setattr(s, "existing_identity_checks", lambda *a: None)
    monkeypatch.setattr(s, "normal_priority", lambda: None)
    monkeypatch.setattr(s.torch, "set_num_threads", lambda *a: None)
    monkeypatch.setattr(s.torch, "set_num_interop_threads", lambda *a: None)
    monkeypatch.setattr(s, "check_old_results", lambda: {"files": 398, "unchanged": True})
    validated, launched = [], []

    def validate(job):
        validated.append(job)
        if invalid_original_bundle:
            raise ValueError("synthetic original complete-bundle/budget validation failure")
        return {"job": list(job)}

    monkeypatch.setattr(s, "ResultValidator", lambda: validate)

    class Child:
        pid = 123

        def poll(self):
            return 0

    def popen(command, **kwargs):
        assert validated == [fixture["jobs"][0]]
        launched.append(command)
        return Child()

    execute = s.execute_queue
    clock = FakeClock()
    monkeypatch.setattr(s, "execute_queue", lambda runtime, state, workers, validator:
                        execute(runtime, state, workers, validator, popen=popen, sleep=clock.sleep, clock=clock,
                                memory=lambda: {"available_physical_gib": 20, "commit_used_fraction": .4}))
    if invalid_original_bundle:
        with pytest.raises(ValueError, match="original complete-bundle"):
            s.run(tmp_path, 1)
        assert not launched
    else:
        assert s.run(tmp_path, 1) == 2  # 2-task fixture cannot claim real 30/30 completion.
        assert len(launched) == 1 and validated == fixture["jobs"]
        state = s.read_json(tmp_path / "status.json")
        assert state["tasks"][0]["attempts"][0]["source_gate_sha256"] == lineage["prior_gate_sha256"]
        assert state["tasks"][1]["attempts"][0]["source_gate_sha256"] == s.sha256(validation / "engineering_gate.json")
        assert len(state["source_lineage"]) == 2
        assert state["source_lineage"][1]["jobs"] == [list(fixture["jobs"][1])]


@pytest.mark.parametrize("prior_kind", ["recovery", "completed"])
@pytest.mark.parametrize("removed", ["json", "bundle", "bundle_with_checkpoint"])
def test_previously_finished_artifact_loss_after_gate_never_dispatches_even_on_second_run(
        monkeypatch, tmp_path, prior_kind, removed):
    """Gate is valid first, then files disappear; a checkpoint is not a result.

    The real identity/checkpoint path runs against a minimally valid identity
    checkpoint. The scientific validator is a complete-bundle sentinel here;
    its numerical correctness is covered by the existing validator tests.
    """
    fixture = recovery_fixture(monkeypatch, tmp_path)
    job = fixture["jobs"][0]
    lineage = s.recovery_lineage(fixture["manifest_path"], tmp_path)
    previous = fixture["prior"]
    gate = {"source_hashes": fixture["current"]}
    if prior_kind == "recovery":
        gate["recovery_lineage"] = lineage
    else:
        previous = s.reconcile_recovered_attempts(previous, lineage,
                                                  s.sha256(fixture["paths"]["prior_status"]))
        previous["tasks"][0]["state"] = "completed"
    s.write_json(tmp_path / "status.json", previous)
    validation = tmp_path / "validation"
    validation.mkdir()
    monkeypatch.setattr(s, "VALIDATION", validation)
    s.write_json(validation / "engineering_gate.json", gate)
    monkeypatch.setattr(s, "verify_gate", lambda *a: gate)
    monkeypatch.setattr(s, "normal_priority", lambda: None)
    monkeypatch.setattr(s.torch, "set_num_threads", lambda *a: None)
    monkeypatch.setattr(s.torch, "set_num_interop_threads", lambda *a: None)
    monkeypatch.setattr(s, "check_old_results", lambda: {"files": 398, "unchanged": True})
    monkeypatch.setattr(s, "HERE", tmp_path)

    result = s.out_path(*job)
    parts = (result, result.with_suffix(".pt"), result.with_suffix(".model.pt"))
    for path in parts[1:]:
        path.write_bytes(b"synthetic complete-bundle sentinel")
    if removed != "bundle":
        ckpt = s.checkpoint(job, tmp_path)
        ckpt.parent.mkdir(parents=True)
        # This passes the actual unchanged checkpoint identity validator, but
        # cannot substitute for a result that was required to remain complete.
        torch.save({"identity": {"problem": s.get_problem(job[1]).name,
                                 "method": job[2], "config": asdict(s.config(job))}}, ckpt)
        s.validate_checkpoint(ckpt, s.get_problem(job[1]), job[2], s.config(job))
    for path in (parts[:1] if removed == "json" else parts):
        path.unlink()
    assert s.existing_identity_checks(tmp_path) == ([] if removed == "bundle" else [
        {"job": list(job), "checkpoint": str(s.checkpoint(job, tmp_path)),
         "sha256": s.sha256(s.checkpoint(job, tmp_path))}])
    validated, launched = [], []

    def validate(candidate):
        validated.append(candidate)
        if candidate == job and not all(path.is_file() for path in parts):
            raise ValueError("required prior complete bundle is missing")
        return {"job": list(candidate)}

    monkeypatch.setattr(s, "ResultValidator", lambda: validate)

    class Child:
        pid = 123

        def poll(self):
            return 0

    def popen(command, **kwargs):
        launched.append(command)
        return Child()

    execute = s.execute_queue
    clock = FakeClock()
    monkeypatch.setattr(s, "execute_queue", lambda runtime, state, workers, validator:
                        execute(runtime, state, workers, validator, popen=popen, sleep=clock.sleep, clock=clock,
                                memory=lambda: {"available_physical_gib": 20, "commit_used_fraction": .4}))
    for _ in range(2):
        with pytest.raises(ValueError, match="required prior complete bundle"):
            s.run(tmp_path, 1)
        assert launched == []
        persisted = s.read_json(tmp_path / "status.json")
        assert persisted["tasks"][0]["required_complete_result"] is True
        assert persisted["phase"] == "review_required"
    assert validated == [job, job]


def test_prevalidation_marks_all_required_jobs_completed_before_queue(monkeypatch, tmp_path):
    jobs = s.ALL_JOBS[:3]
    monkeypatch.setattr(s, "ALL_JOBS", jobs)
    monkeypatch.setattr(s, "out_path", lambda *job: tmp_path / (s.task_id(job) + ".json"))
    previous = s.new_state()
    previous["tasks"][0]["state"] = "completed"
    state = s.new_state(previous)
    seen = []

    def validate(job):
        seen.append(job)
        return {"job": list(job), "complete_and_recomputed": True}

    gate = {"recovery_lineage": {"original_active_jobs": [list(jobs[1])]}}
    s.prevalidate_results_before_dispatch(state, gate, validate)
    assert seen == jobs[:2]
    assert [r["state"] for r in state["tasks"]] == ["completed", "completed", "queued"]
    assert [r["required_complete_result"] for r in state["tasks"]] == [True, True, False]

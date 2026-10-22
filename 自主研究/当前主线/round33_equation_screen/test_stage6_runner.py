"""Runner-only tests: no research training, no mutation of prior artifacts."""
from dataclasses import asdict
from pathlib import Path
import base64
import copy
import subprocess

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
                  deadline=100, memory=None, validation_error=False, launch_error=False):
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

    monkeypatch.setattr(s, "validation_report", lambda *a, **k: None)
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

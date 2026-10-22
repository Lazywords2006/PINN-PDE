"""Run only the authorized 4-resume + 18-IC stage, with gates and durable status."""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import traceback

import numpy as np
import torch

from pinn1d import Config
from problems import OUT_TIMES, get_problem, get_reference
from run_artifacts import load_result, sha256, validate_checkpoint
from screen import evaluate, out_path
from stage5_support import check_new_references, heldout_residuals

HERE = Path(__file__).resolve().parent
VALIDATION = HERE / "validation/stage5_20261022"
DEFAULT_RUNTIME = Path(r"D:\CodexRuntime\runs\r33_stage5_20261022")
PIRATE_CKPTS = Path(r"D:\CodexRuntime\runs\r33_resolution_20261021\checkpoint_restore\checkpoints")
PREREG = "2b67dcb"
COMMON = dict(width=64, depth=4, adam_steps=20000, lr0=0.001, lr1=1e-5,
              nf=4096, nb=256, n0=256, lbfgs_iters=3000, lbfgs_chunk=50,
              nf_fixed=8192, nb_fixed=512, n0_fixed=512, tau=0.1, w_ic=1, t_refine=0, optimizer="adam")
SOURCE_FILES = ("problems.py", "pinn1d.py", "screen.py", "run_artifacts.py", "soap_baseline.py",
                "stage5_support.py", "stage5_runner.py", "run_stage5.ps1", "test_stage5.py", "SCREEN_PROTOCOL.md")
PIRATE_JOBS = [("pirate", "E1_heat", method, seed) for seed in (0, 1) for method in ("hardic", "hardic+layer")]
IC_JOBS = [("final_ic_v1", eq, method, seed) for seed in (0, 1, 2)
           for eq in ("E1_heat_cos", "E3_fisher_cos") for method in ("vanilla", "hardic", "hardic+layer")]
ALL_JOBS = PIRATE_JOBS + IC_JOBS


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def config(job):
    tag, _, _, seed = job
    return replace(Config(), **COMMON, arch="pirate" if tag == "pirate" else "mlp", seed=seed)


def checkpoint(job, runtime):
    tag, eq, method, seed = job
    folder = PIRATE_CKPTS if tag == "pirate" else runtime / "ic_checkpoints"
    return folder / f"{tag}__{eq}__{method.replace('+', '_')}_s{seed}.ckpt"


def source_hashes():
    return {name: sha256(HERE / name) for name in SOURCE_FILES}


def old_hashes_ok():
    report = json.loads((HERE / "validation/feasibility_review_20261021/existing_data_review.json").read_text(encoding="utf-8"))
    return all(sha256(HERE / name) == expected for name, expected in report["SHA256清单"].items())


def gate(runtime):
    subprocess.run(["git", "merge-base", "--is-ancestor", PREREG, "HEAD"], cwd=HERE, check=True)
    if str(torch.__version__) != "2.14.1+cpu":
        raise ValueError("use the pinned torch 2.14.1+cpu runtime")
    log = runtime / "pytest.log"
    text = log.read_text(encoding="utf-8-sig")
    if not re.search(r"\b71 passed\b", text) or re.search(r"\b[1-9]\d* failed\b", text):
        raise ValueError("full 71-test suite has not passed")
    refs = check_new_references()
    if not all(row["passed"] for row in refs) or not old_hashes_ok():
        raise ValueError("reference or old-file integrity gate failed")
    rows = []
    for job in PIRATE_JOBS:
        tag, eq, method, seed = job
        path = checkpoint(job, runtime)
        validate_checkpoint(path, get_problem(eq), method, config(job))
        if not path.is_file():
            raise ValueError("required imported checkpoint is missing; never start PirateNet from scratch")
        payload = torch.load(path, weights_only=False, map_location="cpu")
        expected = 16500 if method == "hardic" else 16000
        if payload["state"]["phase"] != "adam" or payload["state"]["step"] != expected:
            raise ValueError("unexpected initial recovery position")
        rows.append({"job": list(job), "checkpoint": str(path), "sha256": sha256(path),
                     "phase": "adam", "step": expected})
    VALIDATION.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(log, VALIDATION / "pytest.log")
    report = {"time_utc": now(), "passed": True, "prereg_commit": PREREG,
              "tests": 71, "pytest_log_sha256": sha256(log), "references": refs,
              "old260_unchanged": True, "checkpoint_checks_readonly": rows,
              "source_hashes": source_hashes(), "new_training_started": False}
    write_json(VALIDATION / "engineering_gate.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


def progress(runtime):
    rows = []
    for job in ALL_JOBS:
        tag, eq, method, seed = job
        row = {"job": list(job)}
        result = out_path(tag, eq, method, seed)
        path = checkpoint(job, runtime)
        if result.exists():
            row["state"] = "result_written_pending_or_completed_validation"
        elif path.exists():
            try:
                raw = torch.load(path, weights_only=False, map_location="cpu")
                row.update(state=raw["state"]["phase"], adam_step=raw["state"]["step"],
                           lbfgs_budget_used=raw["state"]["done"], resumed_at=raw["hist"].get("resumed_at", []),
                           checkpoint_modified=path.stat().st_mtime)
            except (OSError, EOFError):
                row["state"] = "checkpoint_temporarily_unavailable"
        else:
            row["state"] = "pending_or_before_first_checkpoint"
        rows.append(row)
    return rows


def status(runtime, state, **updates):
    state.update(updates, updated_utc=now(), runner_pid=os.getpid(), progress=progress(runtime))
    state["results_written"] = sum(out_path(*job).exists() for job in ALL_JOBS)
    write_json(runtime / "status.json", state)


def run_batch(runtime, state, jobs, workers, logname):
    first = jobs[0]
    tag = first[0]
    cfg = config(first)
    command = [sys.executable, "-u", str(HERE / "screen.py"), "run", "--eqs",
               ",".join(dict.fromkeys(j[1] for j in jobs)), "--methods",
               ",".join(dict.fromkeys(j[2] for j in jobs)), "--seeds",
               ",".join(str(s) for s in dict.fromkeys(j[3] for j in jobs)),
               "--workers", str(workers), "--tag", tag]
    overrides = dict(COMMON, arch=cfg.arch)
    for key, value in overrides.items():
        command.extend(["--set", f"{key}={value}"])
    env = dict(os.environ, R33_CKPT_DIR=str(PIRATE_CKPTS if tag == "pirate" else runtime / "ic_checkpoints"))
    with (runtime / logname).open("a", encoding="utf-8") as log:
        log.write(f"\nSTART {now()} {command!r}\n")
        log.flush()
        child = subprocess.Popen(command, cwd=HERE, env=env, stdout=log, stderr=subprocess.STDOUT,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        status(runtime, state, phase=tag, batch_pid=child.pid, batch_command=command)
        while child.poll() is None:
            if time.time() > state["review_deadline_unix"]:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], stdout=log, stderr=log, check=False)
                else:
                    child.terminate()
                raise TimeoutError("48-hour review: preserved latest atomic checkpoints; no further dispatch")
            time.sleep(15)
            status(runtime, state)
        if child.returncode:
            raise RuntimeError(f"{tag} batch failed with exit {child.returncode}; inspect {logname}; no next batch")
    status(runtime, state, phase=f"validating_{tag}", batch_pid=None)


def validate_batch(jobs, filename):
    refs = {eq: {n: get_reference(get_problem(eq), n) for n in (64, 96)} for eq in dict.fromkeys(j[1] for j in jobs)}
    xx, ww = np.polynomial.legendre.leggauss(400)
    xx, ww = 0.5 * (xx + 1), 0.5 * ww
    rows = []
    for job in jobs:
        tag, eq, method, seed = job
        path = out_path(*job)
        model, rec, artifact = load_result(path, expected_config=config(job), expected_job=(eq, method, seed, tag))
        recomputed = evaluate(model, refs[eq][64])
        dense = {"vol": [], "trace": []}
        with torch.no_grad():
            for t in OUT_TIMES:
                u = model(torch.tensor(xx), torch.full((len(xx),), t)).numpy()
                ur = refs[eq][96](xx, t)
                dense["vol"].append(float(np.sqrt(np.sum(ww * (u - ur)**2) / np.sum(ww * ur**2))))
                u1 = float(model(torch.ones(1), torch.tensor([t]))[0])
                r1 = float(refs[eq][96](np.array([1.]), t)[0])
                dense["trace"].append(abs(u1 - r1) / max(abs(r1), 1e-12))
        passed = artifact == "complete" and all(
            np.allclose(values[k], rec["metrics"][k], rtol=1e-5, atol=1e-9)
            for values in (recomputed, dense) for k in ("vol", "trace"))
        if not passed:
            raise ValueError(f"result recomputation gate failed: {path}")
        rows.append({"job": list(job), "json_sha256": sha256(path), "max_vol": rec["max_vol"],
                     "max_trace": rec["max_trace"], "metrics": rec["metrics"], "dense_metrics": dense,
                     "complete_and_recomputed": passed, "heldout": heldout_residuals(model),
                     "history_counters": {k: rec["history"].get(k) for k in (
                         "adam_gradient_calls", "lbfgs_budget_used", "lbfgs_func_evals", "lbfgs_n_iter",
                         "lbfgs_loss_stagnation", "lbfgs_stop_reason", "resumed_at")},
                     "trajectory_wall_seconds_including_saved_history": rec["wall_seconds"]})
    write_json(VALIDATION / filename, {"time_utc": now(), "passed": True, "count": len(rows), "results": rows})
    return rows


def final_report(pirate, ic, state):
    from statistics import median
    groups = {}
    for eq in ("E1_heat", "E3_fisher"):
        vals = {}
        for method in ("hardic", "hardic+layer"):
            vals[method] = [json.loads(out_path("pirate", eq, method, seed).read_text(encoding="utf-8"))["max_vol"]
                            for seed in (0, 1, 2)]
        ratio = median(vals["hardic"]) / median(vals["hardic+layer"])
        groups[eq] = {"per_seed": vals, "ratio": ratio, "A2_passed": ratio >= 3}
    summary = {"completed_utc": now(), "authorized_tasks": 22, "validated_new_results": len(pirate) + len(ic),
               "A2": groups, "A2_joint": all(g["A2_passed"] for g in groups.values()),
               "old260_unchanged": old_hashes_ok(), "phase2_started": False,
               "new_IC": [{"eq": eq, "ratios_hardic_over_layer": median(r["max_vol"] for r in ic if r["job"][1:3] == [eq, "hardic"]) /
                          median(r["max_vol"] for r in ic if r["job"][1:3] == [eq, "hardic+layer"])}
                          for eq in ("E1_heat_cos", "E3_fisher_cos")]}
    if not summary["old260_unchanged"]:
        raise ValueError("old files changed during training")
    write_json(VALIDATION / "completion.json", summary)
    lines = ["# 第一阶段 22 个任务完成记录", "", f"完成时间 UTC：{summary['completed_utc']}", "",
             "22 个新增/续跑结果已完成完整产物、原设置及加密误差重算，独立检验点残差另存；第二阶段未启动。", "",
             "| 方程 | PirateNet hardic / hardic+layer 中位数比 | 原 A-2 |", "|---|---:|---|"]
    for eq, group in groups.items():
        lines.append(f"| {eq} | {group['ratio']:.6g} | {'满足' if group['A2_passed'] else '不满足'} |")
    lines += ["", "| 新初值 | hardic / hardic+layer 中位数比 |", "|---|---:|"]
    for row in summary["new_IC"]:
        lines.append(f"| {row['eq']} | {row['ratios_hardic_over_layer']:.6g} |")
    lines += ["", "逐种子、vanilla 对照、误差序列和残差详见本目录 JSON。全部失败与不利结果保留。",
              "旧 G2 失败、A-1 失败及 E4 负面结果不因本批结果改判；三种子不声称统计显著。", ""]
    (VALIDATION / "第一阶段完成记录.md").write_text("\n".join(lines), encoding="utf-8")


def run(runtime):
    runtime.mkdir(parents=True, exist_ok=True)
    # An OS lock is released even if the runner dies; never dispatch duplicate batches.
    lock = (runtime / "runner.lock").open("a+b")
    if os.name == "nt":
        import msvcrt
        lock.seek(0)
        if lock.read(1) == b"":
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    engineering = json.loads((VALIDATION / "engineering_gate.json").read_text(encoding="utf-8"))
    if not engineering["passed"] or source_hashes() != engineering["source_hashes"]:
        raise ValueError("engineering gate is missing, failed, or stale")
    state = {"started_utc": now(), "review_deadline_unix": time.time() + 48 * 3600,
             "authorized_tasks": 22, "phase2_authorized": False, "prereg_commit": PREREG,
             "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE, text=True).strip()}
    previous = runtime / "status.json"
    if previous.exists():
        old = json.loads(previous.read_text(encoding="utf-8"))
        state["started_utc"] = old["started_utc"]
        state["review_deadline_unix"] = old["review_deadline_unix"]
    status(runtime, state, phase="starting")
    try:
        run_batch(runtime, state, PIRATE_JOBS, 4, "pirate.log")
        pirate = validate_batch(PIRATE_JOBS, "pirate_validation.json")
        if source_hashes() != engineering["source_hashes"]:
            raise ValueError("source changed after PirateNet batch; stop before new IC dispatch")
        run_batch(runtime, state, IC_JOBS, 8, "final_ic_v1.log")
        ic = validate_batch(IC_JOBS, "ic_validation.json")
        final_report(pirate, ic, state)
        status(runtime, state, phase="completed", batch_pid=None)
    except BaseException as exc:
        status(runtime, state, phase="review_required" if isinstance(exc, TimeoutError) else "failed",
               error=repr(exc), traceback=traceback.format_exc())
        raise
    finally:
        lock.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--gate", action="store_true", help="read-only engineering gate; no training")
    parser.add_argument("--status", action="store_true", help="print existing status; no training")
    parser.add_argument("--plan", action="store_true", help="print 22 registered tasks; no training")
    args = parser.parse_args()
    torch.set_num_threads(1)
    if args.status:
        print((args.runtime / "status.json").read_text(encoding="utf-8"))
    elif args.plan:
        print(json.dumps({"tasks": [list(job) for job in ALL_JOBS], "count": len(ALL_JOBS),
                          "common": COMMON, "phase2": False}, ensure_ascii=False, indent=2))
    elif args.gate:
        gate(args.runtime)
    else:
        run(args.runtime)


if __name__ == "__main__":
    main()

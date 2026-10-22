"""R33 stage 6: aggregate saved, validated results; never run training or diagnostics.

The default/--partial route produces status only. --final requires all 30
preregistered tasks and binds their complete validation to current raw hashes.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
from statistics import median
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
STAGE = ROOT / "validation/stage6_20261022"
RUNTIME = Path(r"D:\CodexRuntime\runs\r33_stage6_20261022")
BUILD = Path(r"D:\CodexRuntime\runs\r33_stage6_analysis_20261022")
PREREG = "bfe89e3a07f1bb3bcc8e049d8d3d7ff95b4a647a"
TIMES = [0.05, 0.1, 0.25, 0.5, 1.0]
METHODS = ("vanilla", "hardic", "hardic+layer")
EQUATIONS = ("E1_heat", "E3_fisher")
TAU_TAGS = {0.03: "sensitivity_tau003_v1", 0.1: "confirm", 0.3: "sensitivity_tau03_v1"}
JOBS = [(tag, eq, "hardic+layer", seed) for tag in (TAU_TAGS[.03], TAU_TAGS[.3])
        for seed in (0, 1, 2) for eq in EQUATIONS] + [
    ("final_soap64_v1", eq, method, seed) for seed in (0, 1, 2) for eq in EQUATIONS for method in METHODS]
OLD_JOBS = [("confirm", eq, method, seed) for eq in EQUATIONS for method in METHODS for seed in (0, 1, 2)]
TZ = timezone(timedelta(hours=8))
COMPONENTS = ("pde", "left_neumann", "right_dynamic", "initial")
COUNTERS = ("adam_gradient_calls", "lbfgs_budget_used", "lbfgs_func_evals", "lbfgs_n_iter", "lbfgs_stop_reason")


def now():
    return datetime.now(TZ).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def result_path(job, root=ROOT):
    tag, eq, method, seed = job
    return Path(root) / "runs" / tag / eq / f"{method.replace('+', '_')}_s{seed}.json"


def finite(value, location="record"):
    if isinstance(value, float):
        require(math.isfinite(value), f"非有限数据：{location}")
    elif isinstance(value, dict):
        for key, item in value.items():
            finite(item, location + "." + key)
    elif isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            finite(item, location + f"[{i}]")


def exact_jobs(rows, expected, label):
    identities = [tuple(r["job"]) for r in rows]
    require(len(identities) == len(set(identities)) == len(expected), f"{label}：任务缺失或重复")
    require(set(identities) == set(expected), f"{label}：任务身份与预注册不一致")
    return {tuple(row["job"]): row for row in rows}


def close_sequence(actual, expected, label):
    require(len(actual) == len(expected) == 5, f"{label}：不是五个时刻")
    require(all(abs(x - y) <= 1e-9 + 1e-5 * abs(y) for x, y in zip(actual, expected)),
            f"{label}：超出 rtol=1e-5 / atol=1e-9")


def old_integrity(root=ROOT):
    path = Path(root) / "validation/stage5_analysis_20261022/analysis_evidence.json"
    manifest = read(path)["raw_sha256"]
    require(len(manifest) == 398, "原始文件清单不是 398 项")
    for name, digest in manifest.items():
        require(sha(Path(root) / name) == digest, f"旧文件 hash 不符：{name}")
    return manifest, sha(path)


def snapshot_freshness(state, observed=None):
    """Describe a saved snapshot; freshness never proves process identity."""
    observed = observed or datetime.now(timezone.utc)
    updated = state.get("updated_utc")
    age = None
    try:
        stamp = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("timestamp has no timezone")
        age = (observed - stamp).total_seconds()
    except (AttributeError, TypeError, ValueError):
        status = "unknown_timestamp"
    else:
        status = "clock_inconsistent" if age < -5 else "stale" if age > 120 else "recent_snapshot"
    return {"timestamp_status": status, "age_seconds": age,
            "stale_warning_after_seconds": 120, "runner_identity_verified": False,
            "notice": "这里只检查保存时间；即使快照较新，也不能据此确认PID身份、进程存活或批准重启。"}


def partial_status(root=ROOT, stage=STAGE, runtime=RUNTIME):
    state_path = Path(runtime) / "status.json"
    state_raw = state_path.read_bytes() if state_path.exists() else None
    state = json.loads(state_raw.decode("utf-8-sig")) if state_raw is not None else {"phase": "not_started", "tasks": []}
    validation_path = Path(stage) / "results_validation.json"
    validation_raw = validation_path.read_bytes() if validation_path.exists() else None
    validation = json.loads(validation_raw.decode("utf-8-sig")) if validation_raw is not None else {"results": [], "complete": False}
    rows = state.get("tasks", [])
    counts = {key: sum(r.get("state") == key for r in rows) for key in ("queued", "running", "completed", "failed")}
    return {"analysis_state": "partial", "generated_local": now(), "prereg_commit": PREREG,
            "required_tasks": 30, "runner_phase": state["phase"], "counts": counts,
            "saved_json_count": sum(result_path(j, root).exists() for j in JOBS),
            "validator_reported_count": len(validation.get("results", [])),
            "validator_reported_complete": validation.get("complete", False),
            "runner_pid": state.get("runner_pid"), "runner_updated_utc": state.get("updated_utc"),
            "count_scope": "persisted_status_snapshot_not_live_process_count",
            "snapshot_freshness": snapshot_freshness(state),
            "resources": state.get("resources"), "stop_dispatch_reason": state.get("stop_dispatch_reason"),
            "final_criteria_evaluated": False,
            "notice": "PARTIAL：任务数量是保存的状态快照，不是实时进程统计。必须核对更新时间、进程身份及恢复监督记录；不能据此重启队列。不计算最终效果判据，不生成正式分析图。",
            "input_sha256": {str(p): hashlib.sha256(raw).hexdigest() for p, raw in
                             ((state_path, state_raw), (validation_path, validation_raw)) if raw is not None}}


def completion_gate(root=ROOT, stage=STAGE, runtime=RUNTIME):
    root, stage, runtime = Path(root), Path(stage), Path(runtime)
    state = read(runtime / "status.json")
    require(state.get("phase") == "completed", "30 项队列尚未 completed；仅允许 --partial")
    statuses = exact_jobs(state.get("tasks", []), JOBS, "运行状态")
    require(all(row["state"] == "completed" for row in statuses.values()), "仍有未完成或失败任务")
    require(all(row.get("pid") is None for row in statuses.values()), "完成状态仍含活动任务 PID")
    validation = read(stage / "results_validation.json")
    summary = read(stage / "summary.json")
    for name, report in (("验证报告", validation), ("汇总报告", summary)):
        require(report.get("complete") is True and report.get("validated_count") == report.get("required_count") == 30,
                f"{name}未确认 30/30；仅允许 --partial")
        require(report.get("prereg_commit") == PREREG, f"{name}预注册提交不匹配")
    diagnostic = exact_jobs(validation["results"], JOBS, "验证报告")
    summary_rows = exact_jobs(summary["results"], JOBS, "汇总报告")
    require(summary_rows == diagnostic, "两份完成报告结果不同")
    gate = read(stage / "engineering_gate.json")
    require(gate.get("passed") is True and gate.get("prereg_commit") == PREREG, "工程门未通过/提交不符")
    require({tuple(j) for j in gate["tasks"]} == set(JOBS), "工程门任务集合不同")
    for name, digest in gate["source_hashes"].items():
        require(sha(root / name) == digest, f"冻结源 hash 不匹配：{name}")
    old_hashes, manifest_sha = old_integrity(root)
    require(gate["old_results"]["manifest_sha256"] == manifest_sha, "398 文件证据清单与工程门不同")
    require(summary.get("old_results", {}).get("unchanged") is True, "完成报告未确认旧文件不变")
    plan = exact_jobs(read(stage / "task_plan.json")["jobs"], JOBS, "任务配置计划")
    records, new_hashes = {}, {}
    expected_jsons = {result_path(j, root).resolve() for j in JOBS}
    actual_jsons = {p.resolve() for tag in {j[0] for j in JOBS} for p in (root / "runs" / tag).rglob("*.json")}
    require(actual_jsons == expected_jsons, "新 tag 存在额外或缺失 JSON，不能隐式筛除")
    for job in JOBS:
        path = result_path(job, root)
        rec, val = read(path), diagnostic[job]
        validate_record(rec, job)
        require(rec["config"] == plan[job]["config"] == val["config"], f"配置身份不符：{job}")
        require(val["complete_and_recomputed"] is True and sha(path) == val["json_sha256"], f"结果未绑定验证：{job}")
        require(val["metrics"] == rec["metrics"], f"验证与原始指标不一致：{job}")
        for section in ("recomputed_N64_GL200", "dense_metrics_N96_GL400"):
            for metric in ("vol", "trace"):
                close_sequence(val[section][metric], rec["metrics"][metric], f"{job} {section}/{metric}")
        require(rec.get("artifacts", {}).get("version") == 1, f"新结果缺少完整产物清单：{job}")
        expected_files = {path.name, path.with_suffix(".pt").name, path.with_suffix(".model.pt").name}
        require(set(val["bundle_sha256"]) == expected_files, f"验证 bundle 清单异常：{job}")
        for name, digest in val["bundle_sha256"].items():
            candidate = path.parent / name
            require(sha(candidate) == digest, f"完整 bundle hash 不符：{candidate}")
            new_hashes[candidate.relative_to(root).as_posix()] = digest
        for key in ("base", "model"):
            entry = rec["artifacts"][key]
            require(Path(entry["file"]).name == entry["file"] and
                    val["bundle_sha256"].get(entry["file"]) == entry["sha256"], f"原始产物清单不符：{job}")
        require(rec["history"].get("adam_gradient_calls") == 20000, f"梯度预算不符：{job}")
        for key in COUNTERS:
            require(val["history_counters"].get(key) == rec["history"].get(key), f"调用计数不符：{job}/{key}")
        require(set(val["heldout"]) == set(COMPONENTS), f"heldout 分量缺失：{job}")
        for component, values in val["heldout"].items():
            require(values["n"] == (8192 if component == "pde" else 1024), f"heldout 点数不符：{job}")
            require(values["rms"] >= 0 and values["max_abs"] >= 0, f"heldout 残差非法：{job}")
        finite(val)
        records[job] = normalize(rec, path, root, val, statuses[job])
    require(len(new_hashes) == 90, "30 项任务应提供 90 个新原始文件")
    for job in OLD_JOBS:
        path = result_path(job, root)
        rec = read(path)
        validate_record(rec, job)
        require(path.relative_to(root).as_posix() in old_hashes, f"旧默认结果不在已冻结清单：{job}")
        require(rec["config"]["tau"] == .1 and rec["config"]["adam_steps"] == 20000, "旧默认配置异常")
        records[job] = normalize(rec, path, root)
    inputs = [runtime / "status.json", stage / "results_validation.json", stage / "summary.json",
              stage / "engineering_gate.json", stage / "task_plan.json"]
    metadata = {"old398_unchanged": True, "old_manifest_sha256": manifest_sha,
                "raw_sha256": dict(old_hashes, **new_hashes), "new_raw_files": 90,
                "input_sha256": {str(p): sha(p) for p in inputs},
                "source_hashes": gate["source_hashes"], "runtime_status": state,
                "validation_source": "复用并逐文件绑定已完成的完整模型重载、加密重算与 heldout 报告；本分析不再运行神经网络。"}
    return records, metadata


def validate_record(rec, job):
    require((rec["tag"], rec["eq"], rec["method"], rec["seed"]) == job, f"JSON 任务身份不符：{job}")
    require(rec["config"]["seed"] == job[3], "配置种子与任务不符")
    require(rec["metrics"]["times"] == TIMES, "评价时刻不符")
    for key in ("vol", "trace"):
        seq = rec["metrics"][key]
        require(len(seq) == 5 and all(x >= 0 for x in seq), "误差序列不完整或为负")
        require(rec["max_" + key] == max(seq), "最大误差与时序不一致")
    finite(rec)


def normalize(rec, path, root, diagnostic=None, state=None):
    is_new = rec["tag"] != "confirm"
    hist = rec.get("history", {})
    return {"job": [rec[k] for k in ("tag", "eq", "method", "seed")],
            "tag": rec["tag"], "eq": rec["eq"], "method": rec["method"], "seed": rec["seed"],
            "optimizer": rec["config"].get("optimizer", "adam"), "tau": rec["config"]["tau"],
            "source": path.relative_to(root).as_posix(), "source_sha256": sha(path),
            "training_location": "本机 stage6" if is_new else "历史云端 confirm",
            "environment": rec["env"], "config": rec["config"], "delta": rec["delta"],
            "metrics": rec["metrics"], "max_vol": rec["max_vol"], "max_trace": rec["max_trace"],
            "final_adam_loss": rec["final_adam_loss"], "final_lbfgs_loss": rec["final_lbfgs_loss"],
            "recorded_wall_seconds": rec["wall_seconds"], "recorded_adam_seconds": rec["adam_seconds"],
            "calls": {key: hist.get(key) for key in COUNTERS}, "resumed_at": hist.get("resumed_at", []),
            "heldout": diagnostic["heldout"] if diagnostic else None,
            "optimizer_accounting": diagnostic.get("optimizer_accounting") if diagnostic else None,
            "attempts": state.get("attempts", []) if state else None,
            "missing_diagnostics_note": None if diagnostic else "旧默认组未保存本轮独立残差；旧未记录的实际调用留空，不补算/填造。"}


def group(records, tag, eq, method):
    rows = [records[(tag, eq, method, seed)] for seed in (0, 1, 2)]
    values = [r["max_vol"] for r in rows]
    return {"tag": tag, "eq": eq, "method": method, "tau": rows[0]["tau"],
            "optimizer": rows[0]["optimizer"], "training_location": rows[0]["training_location"],
            "seeds": values, "median": median(values), "min": min(values), "max": max(values),
            "under_1e2": sum(x <= 1e-2 for x in values),
            "trace_seeds": [r["max_trace"] for r in rows], "trace_median": median(r["max_trace"] for r in rows)}


def ratio(numerator, denominator):
    if denominator == 0:
        return None
    return numerator / denominator


def soap_judgment(hardic, layer):
    value = ratio(hardic["median"], layer["median"])
    # The multiplication form also handles an exactly zero layer error without
    # inventing finite ratios or serializing Infinity into JSON.
    ratio_pass = hardic["median"] > 0 and hardic["median"] >= 3 * layer["median"]
    return {"hardic_median": hardic["median"], "layer_median": layer["median"],
            "hardic_over_layer": value, "ratio_undefined_zero_denominator": value is None,
            "ratio_ge3": ratio_pass, "layer_under_1e2": layer["under_1e2"],
            "at_least_two_of_three": layer["under_1e2"] >= 2,
            "passed": ratio_pass and layer["under_1e2"] >= 2}


def summarize(records, metadata):
    defaults = [group(records, tag, eq, method) for eq in EQUATIONS
                for tag in ("confirm", "final_soap64_v1") for method in METHODS]
    taus = [group(records, tag, eq, "hardic+layer") for eq in EQUATIONS for tau, tag in TAU_TAGS.items()]
    tau_summary = []
    soap = []
    for eq in EQUATIONS:
        rows = [row for row in taus if row["eq"] == eq]
        base = next(row for row in rows if row["tau"] == .1)["median"]
        for row in rows:
            row["median_over_tau01"] = ratio(row["median"], base)
        medians = [row["median"] for row in rows]
        tau_summary.append({"eq": eq, "across_tau_max_over_min_median": ratio(max(medians), min(medians)),
                            "main_tau_unchanged": .1, "tau_selected_from_results": False})
        h = group(records, "final_soap64_v1", eq, "hardic")
        l = group(records, "final_soap64_v1", eq, "hardic+layer")
        soap.append(dict(eq=eq, **soap_judgment(h, l)))
    soap_passes = sum(row["passed"] for row in soap)
    state = metadata["runtime_status"]
    new_rows = [records[j] for j in JOBS]
    old_rows = [records[j] for j in OLD_JOBS]
    costs = {}
    for label, rows in (("new_local_30", new_rows), ("historical_cloud_18", old_rows)):
        values = [r["recorded_wall_seconds"] for r in rows]
        costs[label] = {"count": len(rows), "trajectory_seconds_sum": sum(values),
                        "trajectory_seconds_min": min(values), "trajectory_seconds_median": median(values),
                        "trajectory_seconds_max": max(values)}
    costs["local_runner_elapsed_seconds"] = state["total_runner_wall_seconds"]
    costs["local_batch_elapsed_seconds"] = state.get("batch_elapsed_seconds")
    costs["runner_wall_timing_note"] = state.get("runner_wall_timing_note")
    costs["local_attempt_wall_seconds_sum"] = sum(a.get("wall_seconds", 0) for r in new_rows for a in r["attempts"])
    costs["interpretation"] = "云端与本机分开描述；进程轨迹耗时总和不是并行批次墙钟。整批历时与状态记录的运行器会话累计时间分别报告，调度器退出后至恢复的间隔不计入后者；未保存的整批历时留空，不用进程时间之和补造。不计算跨环境速度倍数。"
    return {"analysis_state": "complete", "generated_local": now(), "prereg_commit": PREREG,
            "new_task_count": 30, "default_comparison_records": 36, "tau_records": 18,
            "records": [records[j] for j in OLD_JOBS + JOBS], "default_groups": defaults,
            "tau_groups": taus, "tau_summary": tau_summary,
            "S6_SOAP": {"per_equation": soap, "joint_passed": soap_passes == 2,
                        "conclusion": "满足本批叠加判据" if soap_passes == 2 else "部分满足" if soap_passes else "不满足",
                        "rule": "两个方程均需 hardic 中位数至少为修正组 3 倍，且修正组至少 2/3 主误差≤1e-2。",
                        "not_a_publication_threshold": True},
            "costs": costs, "evidence": metadata,
            "scope": "事后描述性汇总；无选参、无新阈值、无统计显著性/CI声明。主配置 τ=0.1 不变。",
            "preserved_negative_findings": "原 A-1、G2 失败及 E4 负面结果不因本批改变。"}


def flat(row):
    fields = {key: row[key] for key in ("tag", "eq", "method", "seed", "optimizer", "tau", "training_location",
              "max_vol", "max_trace", "final_adam_loss", "final_lbfgs_loss", "recorded_wall_seconds",
              "recorded_adam_seconds", "source", "source_sha256", "missing_diagnostics_note")}
    fields.update(row["calls"])
    fields["resumed_at"] = ";".join(row["resumed_at"])
    for i, t in enumerate(TIMES):
        for metric in ("vol", "trace"):
            fields[f"{metric}_t{t:g}"] = row["metrics"][metric][i]
    for component in COMPONENTS:
        for measure in ("rms", "max_abs"):
            fields[f"heldout_{component}_{measure}"] = (row["heldout"] or {}).get(component, {}).get(measure)
    fields["optimizer_parameter_updates_semantics"] = (row["optimizer_accounting"] or {}).get(
        "parameter_updates_inferred_from_frozen_optimizer_semantics")
    fields["python"] = row["environment"].get("python")
    fields["torch"] = row["environment"].get("torch")
    fields["numpy"] = row["environment"].get("numpy")
    fields["attempt_wall_seconds_sum"] = sum(a.get("wall_seconds", 0) for a in row["attempts"]) if row["attempts"] is not None else None
    return fields


def csv_write(path, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def number(value):
    return "未保存/不适用" if value is None else f"{value:.5g}"


def table(headers, rows):
    cell = lambda v: str(v).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(map(cell, headers)) + " |",
                       "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(map(cell, row)) + " |" for row in rows])


def report(audit):
    lines = ["# R33 第二阶段完整结果分析", "", f"生成时间：{audit['generated_local']}。状态：**30/30 已完成并绑定复核证据**。", "",
             f"S6-SOAP：**{audit['S6_SOAP']['conclusion']}**。该判据只描述本批固定配置，不是论文发表门槛。", "",
             "所有新任务、所有种子和所有 τ 档均报告；主配置保持 τ=0.1，没有倒选 τ 或优化器。原 A-1、G2 失败和 E4 负面结果保留。", "",
             "## 数据核验与范围", "", "旧 398 个文件逐一 hash 不变；新增 30 项共 90 个原始文件均与完整模型验证报告绑定。原 N64/GL200 与加密 N96/GL400 的序列容差为 rtol=1e-5、atol=1e-9。独立残差沿用固定检验点；本分析只聚合既有报告，不追加模型诊断。", "",
             "主指标为 t={0.05, 0.1, 0.25, 0.5, 1} 五个固定评价时刻的体相对 L² 误差最大值，不是连续时间上的上确界。", "",
             "默认 Adam 来自历史云端 confirm，固定 SOAP64 来自本机本批；误差按已固定指标并列，但这不是隔离运行环境差异的优化器因果比较。不能把全部精度差异归因于优化器，也不能混为等墙钟或速度收益。同一本机环境内的 SOAP 三臂叠加判据另行判断。旧残差和未保存的实际调用留空。", "",
             "## 默认配置六臂对照", "", "每个方程给出 Adam→L-BFGS / SOAP64→L-BFGS × 普通 PINN/硬初值/硬初值加校正的三个真实报告种子。没有调参后主表。", "",
             table(["方程", "tag", "方法", "来源", "seed0", "seed1", "seed2", "中位数", "最小–最大", "≤1e-2"],
                   [[r["eq"], r["tag"], r["method"], r["training_location"], *map(number, r["seeds"]),
                     number(r["median"]), f"{number(r['min'])}–{number(r['max'])}", f"{r['under_1e2']}/3"]
                    for r in audit["default_groups"]]), "", "![默认六臂全部种子和中位数](default_six_arms.png)", "",
             "图注：最终误差对应 Adam→L-BFGS 或 SOAP64→L-BFGS 完整训练路线。纵轴为 t={0.05, 0.1, 0.25, 0.5, 1} 五个固定评价时刻的最大体相对 L² 误差，非连续时间上确界。历史云端与本机来源分别标示。", "",
             "## τ 灵敏度（不选参）", "", "τ=0.03/0.3 为本机新增，τ=0.1 只读复用历史云端 confirm。各档保持完整预算与种子集合；与τ=0.1的差异同时包含运行环境差异，不能视为完全隔离环境后的τ因果效应。跨档 max/min 是中位数之比，不是置信区间或稳健性达标线。", "",
             table(["方程", "τ", "来源", "seed0", "seed1", "seed2", "中位数", "范围", "中位数/τ=0.1"],
                   [[r["eq"], r["tau"], r["training_location"], *map(number, r["seeds"]), number(r["median"]),
                     f"{number(r['min'])}–{number(r['max'])}", number(r["median_over_tau01"])] for r in audit["tau_groups"]]), "",
             table(["方程", "跨 τ 最大/最小中位数", "主 τ"],
                   [[r["eq"], number(r["across_tau_max_over_min_median"]), r["main_tau_unchanged"]] for r in audit["tau_summary"]]),
             "", "![τ三档全部种子和中位数](tau_sensitivity.png)", "",
             "图注：全部 τ 档采用 Adam→L-BFGS，主配置仍为 τ=0.1。纵轴为 t={0.05, 0.1, 0.25, 0.5, 1} 五个固定评价时刻的最大体相对 L² 误差，非连续时间上确界。τ=0.1 与其余两档的运行环境不同，图中差异不作隔离环境后的因果解释。", "",
             "## S6-SOAP 预注册判定", "",
             audit["S6_SOAP"]["rule"], "",
             table(["方程", "hardic中位数", "修正中位数", "比值", "修正≤1e-2", "判定"],
                   [[r["eq"], number(r["hardic_median"]), number(r["layer_median"]), number(r["hardic_over_layer"]),
                     f"{r['layer_under_1e2']}/3", "满足" if r["passed"] else "不满足"] for r in audit["S6_SOAP"]["per_equation"]]), "",
             "## 全部新增任务的损失、独立残差和实际调用", "",
             "训练损失受参数化与目标项影响，不能直接当成相同物理误差。final_adam_loss沿用原始字段名，指第一阶段末次抽样记录的损失：本批为零基step19990更新前计算的值，在该步更新后写入，并非第20000次调用结束后的重评损失。独立检验点残差未参与训练或配置选择。下表以 PDE、动态右端和初值 RMS 展示；左端及全部 max_abs、五个时刻体/迹序列均在 CSV 中完整保留。", "",
             table(["tag/方程/方法/seed", "Adam/SOAP末次记录损失", "L-BFGS末损失", "PDE RMS", "动态边界RMS", "初值RMS", "closure", "内部迭代", "停止原因"],
                   [["/".join(map(str, r["job"])), number(r["final_adam_loss"]), number(r["final_lbfgs_loss"]),
                     number(r["heldout"]["pde"]["rms"]), number(r["heldout"]["right_dynamic"]["rms"]),
                     number(r["heldout"]["initial"]["rms"]), number(r["calls"]["lbfgs_func_evals"]),
                     number(r["calls"]["lbfgs_n_iter"]), r["calls"]["lbfgs_stop_reason"]]
                    for r in audit["records"] if tuple(r["job"]) in JOBS]), "",
             "history.adam_gradient_calls在第一阶段成功完成后按cfg.adam_steps写入，依赖冻结循环及完成证据，属于实现记录而非逐步独立观测计数器。SOAP64 的 20000 次梯度调用包含首次仅初始化，19999 次参数更新由冻结算法语义推得，未冒充新增实测计数器。L-BFGS内部迭代和closure来自优化器保存状态。", "",
             "## 墙钟与恢复记录", "", audit["costs"]["interpretation"], "",
             table(["来源", "任务数", "轨迹秒数合计", "最小", "中位数", "最大"],
                   [[name, value["count"], number(value["trajectory_seconds_sum"]), number(value["trajectory_seconds_min"]),
                     number(value["trajectory_seconds_median"]), number(value["trajectory_seconds_max"])]
                    for name, value in audit["costs"].items() if isinstance(value, dict)]), "",
             f"本机整批历时：{number(audit['costs']['local_batch_elapsed_seconds'])} 秒；按状态记录的运行器会话累计时间：{number(audit['costs']['local_runner_elapsed_seconds'])} 秒；本机所有尝试墙钟之和：{number(audit['costs']['local_attempt_wall_seconds_sum'])} 秒。三者口径不同，未相互替代。恢复计时原注：{audit['costs']['runner_wall_timing_note'] or '未保存/不适用'}。失败历史、每次命令、PID、恢复标记保存在 analysis_evidence.json。", "",
             "## 文件与限制", "", "all_new_runs.csv 含 30 行；default_six_arms.csv 含 36 行；tau_sensitivity.csv 含 18 行。PNG 为 300 dpi，PDF 为矢量；所有点对应真实种子，短横线为中位数，竖线为种子最小–最大范围，均不是 CI。τ=.1 与默认 Adam 的来源差异在图中明确标示。", "",
             "三种子样本不足以支持统计显著性或普遍优势。固定五个输出时刻和均匀检验时间点不能证明 t→0 的机制。S6-SOAP 无论正负均保留，不替代原 B-1/B-2/G2；没有构造新的发表达标线。"]
    return "\n".join(lines) + "\n"


def final_analysis(output=OUT):
    output = Path(output).resolve()
    require(output.is_relative_to(OUT.resolve()), "正式输出只能在 stage6_analysis_20261022 目录或其子目录")
    require(not (output / "analysis_evidence.json").exists(), "已有正式分析，不覆盖；请使用 --output 指定本目录下新版本")
    records, metadata = completion_gate()
    audit = summarize(records, metadata)
    work = BUILD / datetime.now().strftime("build_%Y%m%d_%H%M%S_%f")
    work.mkdir(parents=True, exist_ok=False)
    csv_write(work / "all_new_runs.csv", [flat(records[j]) for j in JOBS])
    default_jobs = [(tag, eq, method, seed) for eq in EQUATIONS for tag in ("confirm", "final_soap64_v1")
                    for method in METHODS for seed in (0, 1, 2)]
    tau_jobs = [(tag, eq, "hardic+layer", seed) for eq in EQUATIONS for tag in TAU_TAGS.values() for seed in (0, 1, 2)]
    csv_write(work / "default_six_arms.csv", [flat(records[j]) for j in default_jobs])
    csv_write(work / "tau_sensitivity.csv", [flat(records[j]) for j in tau_jobs])
    from plot_stage6 import render
    audit["figure_metadata"] = render(audit, work)
    audit["analysis_code_sha256"] = {p.name: sha(p) for p in (OUT / "analyze_stage6.py", OUT / "plot_stage6.py")}
    (work / "STAGE6_ANALYSIS_20261022.md").write_text(report(audit), encoding="utf-8")
    audit["output_sha256"] = {p.name: sha(p) for p in work.iterdir() if p.is_file()}
    # Recheck all source evidence after plotting before publishing a formal result.
    for name, digest in metadata["raw_sha256"].items():
        require(sha(ROOT / name) == digest, f"生成报告期间原始数据发生变化：{name}")
    for name, digest in metadata["input_sha256"].items():
        require(sha(name) == digest, f"生成报告期间验证证据发生变化：{name}")
    write(work / "analysis_evidence.json", audit)
    output.mkdir(parents=True, exist_ok=True)
    for path in work.iterdir():
        require(not (output / path.name).exists(), f"不覆盖已有正式文件：{path.name}")
    # JSON is copied last as this analysis package's completion marker.
    for path in sorted(work.iterdir(), key=lambda p: p.name == "analysis_evidence.json"):
        shutil.copy2(path, output / path.name)
    return {"analysis_state": "complete", "output": str(output), "new_task_count": 30,
            "S6_SOAP": audit["S6_SOAP"]["conclusion"], "artifacts": list(audit["output_sha256"])}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--partial", action="store_true")
    action.add_argument("--final", action="store_true")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    if args.final:
        try:
            result = final_analysis(args.output)
        except (ValueError, FileNotFoundError) as exc:
            print(json.dumps({"analysis_state": "blocked", "formal_report_created": False,
                              "error": str(exc)}, ensure_ascii=False))
            return 2
    else:
        result = partial_status()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

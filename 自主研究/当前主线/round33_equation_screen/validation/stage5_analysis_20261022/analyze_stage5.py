"""Read-only analysis of saved R33 results; never trains or chooses a configuration.

Run with an analysis-only Python environment containing matplotlib and Markdown.
All reported aggregates are calculated from JSON; historical results stay untouched.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
from statistics import median

os.environ.setdefault("MPLCONFIGDIR", r"D:\CodexRuntime\cache\matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", r"D:\CodexRuntime\cache\xdg")
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
STAGE = ROOT / "validation/stage5_20261022"
RUNTIME = Path(r"D:\CodexRuntime\runs\r33_stage5_20261022")
METHODS = ("vanilla", "hardic", "hardic+layer")
NAMES = {"vanilla": "普通 PINN", "hardic": "硬初值", "hardic+layer": "硬初值＋校正", "rba": "RBA"}
TIMES = [0.05, 0.1, 0.25, 0.5, 1.0]
TZ = timezone(timedelta(hours=8))


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def table(headers, rows):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(map(cell, headers)) + " |",
                      "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(map(cell, row)) + " |" for row in rows])


def f(value):
    return "未保存" if value is None else f"{value:.4e}"


def local(value):
    return datetime.fromisoformat(value).astimezone(TZ).strftime("%Y-%m-%d %H:%M:%S UTC+8")


def main():
    records = {}
    raw_hashes = {}
    inventory = {}
    for path in sorted((ROOT / "runs").glob("*/*/*.json")):
        rec = read(path)
        key = (rec["tag"], rec["eq"], rec["method"], rec["seed"])
        assert key not in records, key
        assert math.isclose(rec["max_vol"], max(rec["metrics"]["vol"]), rel_tol=1e-12)
        assert math.isclose(rec["max_trace"], max(rec["metrics"]["trace"]), rel_tol=1e-12)
        assert all(math.isfinite(v) for k in ("vol", "trace") for v in rec["metrics"][k])
        rec = dict(rec, source=path.relative_to(ROOT).as_posix())
        records[key] = rec
        raw_hashes[rec["source"]] = sha(path)
        base = path.with_suffix(".pt")
        assert base.exists(), base
        raw_hashes[base.relative_to(ROOT).as_posix()] = sha(base)
        for entry in rec.get("artifacts", {}).values():
            if not isinstance(entry, dict) or "file" not in entry:
                continue
            artifact = path.parent / entry["file"]
            assert sha(artifact) == entry["sha256"], artifact
            raw_hashes[artifact.relative_to(ROOT).as_posix()] = sha(artifact)
        tag = key[0]
        inv = inventory.setdefault(tag, {"json": 0, "base_pt": 0, "model_pt": 0})
        inv["json"] += 1
        inv["base_pt"] += 1
        inv["model_pt"] += int(path.with_suffix(".model.pt").exists())
    for tag in ("soap1e3", "soap3e3", "ic1000"):
        inventory.setdefault(tag, {"json": 0, "base_pt": 0, "model_pt": 0})

    old_manifest = read(ROOT / "validation/feasibility_review_20261021/existing_data_review.json")["SHA256清单"]
    assert len(old_manifest) == 260
    assert all(sha(ROOT / p) == expected for p, expected in old_manifest.items())
    gate = read(STAGE / "engineering_gate.json")
    assert all(sha(ROOT / p) == expected for p, expected in gate["source_hashes"].items())
    diagnostics = {}
    for name, count in (("pirate_validation.json", 4), ("ic_validation.json", 18)):
        v = read(STAGE / name)
        assert v["passed"] and v["count"] == len(v["results"]) == count
        for row in v["results"]:
            key = tuple(row["job"])
            rec = records[key]
            assert row["complete_and_recomputed"]
            assert raw_hashes[rec["source"]] == row["json_sha256"]
            for metric in ("vol", "trace"):
                assert row["metrics"][metric] == rec["metrics"][metric]
                assert all(abs(x-y) <= 1e-9 + 1e-5*abs(y)
                           for x, y in zip(row["dense_metrics"][metric], rec["metrics"][metric]))
            assert all(math.isfinite(value) for item in row["heldout"].values() for value in item.values())
            diagnostics[key] = row
    assert len(diagnostics) == 22
    completion = read(STAGE / "completion.json")
    assert completion["validated_new_results"] == 22 and completion["old260_unchanged"]
    snapshot = OUT / "completion_status_snapshot.json"
    state = read(snapshot if snapshot.exists() else RUNTIME / "status.json")
    assert state["phase"] == "completed" and state["results_written"] == 22
    if not snapshot.exists():
        dump(snapshot, state)

    def group(tag, eq, method):
        rows = [records[(tag, eq, method, seed)] for seed in (0, 1, 2)]
        result = {"tag": tag, "eq": eq, "method": method,
                  "seeds": [r["max_vol"] for r in rows],
                  "median": median(r["max_vol"] for r in rows),
                  "min": min(r["max_vol"] for r in rows),
                  "max": max(r["max_vol"] for r in rows),
                  "trace_median": median(r["max_trace"] for r in rows),
                  "under_1e2": sum(r["max_vol"] <= 1e-2 for r in rows),
                  "time_medians": [median(r["metrics"]["vol"][i] for r in rows) for i in range(5)],
                  "trace_time_medians": [median(r["metrics"]["trace"][i] for r in rows) for i in range(5)],
                  "wall_median_seconds": median(r["wall_seconds"] for r in rows),
                  "wall_seconds": [r["wall_seconds"] for r in rows]}
        if all((tag, eq, method, s) in diagnostics for s in (0, 1, 2)):
            result["heldout_medians"] = {
                component: {measure: median(diagnostics[(tag, eq, method, s)]["heldout"][component][measure]
                                            for s in (0, 1, 2)) for measure in ("rms", "max_abs")}
                for component in ("pde", "left_neumann", "right_dynamic", "initial")}
        return result

    groups = {}
    def g(tag, eq, method):
        key = f"{tag}/{eq}/{method}"
        if key not in groups:
            groups[key] = group(tag, eq, method)
        return groups[key]

    pairs = []
    for tag, eq in [("confirm", "E1_heat"), ("confirm", "E3_fisher"),
                    ("pirate", "E1_heat"), ("pirate", "E3_fisher"),
                    ("final_ic_v1", "E1_heat_cos"), ("final_ic_v1", "E3_fisher_cos")]:
        h, l = g(tag, eq, "hardic"), g(tag, eq, "hardic+layer")
        pair = {"tag": tag, "eq": eq, "hardic_over_layer": h["median"]/l["median"],
                "paired_ratios": [x/y for x, y in zip(h["seeds"], l["seeds"])],
                "paired_wins": sum(x>y for x,y in zip(h["seeds"], l["seeds"])),
                "trace_ratio": h["trace_median"]/l["trace_median"]}
        if tag != "pirate":
            pair["vanilla_over_layer"] = g(tag, eq, "vanilla")["median"]/l["median"]
        pairs.append(pair)
    a1 = []
    for eq in ("E1_heat", "E3_fisher"):
        choices = {tag: g(tag, eq, "hardic")["median"] for tag in ("causal1", "causal10", "pirate")}
        best = min(choices, key=choices.get)
        ratio = choices[best]/g("confirm", eq, "hardic+layer")["median"]
        a1.append({"eq": eq, "baselines": choices, "best": best, "ratio": ratio, "passed": ratio>=3})
    assert not all(row["passed"] for row in a1)
    for pair in pairs:
        if pair["tag"] == "pirate":
            assert math.isclose(pair["hardic_over_layer"], completion["A2"][pair["eq"]]["ratio"], rel_tol=1e-12)
            assert pair["hardic_over_layer"] >= 3

    new_records = [records[key] for key in diagnostics]
    assert all(math.isfinite(r[k]) for r in new_records for k in ("final_adam_loss", "final_lbfgs_loss"))
    flat_rows = []
    for key, rec in records.items():
        hist = rec.get("history", {})
        row = {k: rec.get(k) for k in ("tag", "eq", "method", "seed", "delta", "max_vol", "max_trace",
                                         "wall_seconds", "adam_seconds", "final_adam_loss", "final_lbfgs_loss", "source")}
        row["artifact_schema"] = rec.get("artifacts", {}).get("version", "legacy_base_only")
        row.update({k: hist.get(k) for k in ("adam_gradient_calls", "lbfgs_budget_used", "lbfgs_func_evals", "lbfgs_n_iter", "lbfgs_stop_reason")})
        row["resumed_at"] = ";".join(hist.get("resumed_at", []))
        for i, t in enumerate(TIMES):
            row[f"vol_t{t:g}"] = rec["metrics"]["vol"][i]
            row[f"trace_t{t:g}"] = rec["metrics"]["trace"][i]
        for component in ("pde", "left_neumann", "right_dynamic", "initial"):
            for measure in ("rms", "max_abs"):
                row[f"heldout_{component}_{measure}"] = diagnostics.get(key, {}).get("heldout", {}).get(component, {}).get(measure)
        flat_rows.append(row)
    with (OUT / "all_runs.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat_rows[0]))
        writer.writeheader()
        writer.writerows(flat_rows)

    # Durations are observed local batch times, not sums of parallel process times.
    start = datetime.fromisoformat(state["started_utc"])
    end = datetime.fromisoformat(completion["completed_utc"])
    pirate_done = datetime.fromisoformat(read(STAGE / "pirate_validation.json")["time_utc"])
    ic_rows = [r for r in new_records if r["tag"] == "final_ic_v1"]
    costs = {"local_total_hours": (end-start).total_seconds()/3600,
             "pirate_batch_including_validation_hours": (pirate_done-start).total_seconds()/3600,
             "ic_batch_including_validation_hours": (end-pirate_done).total_seconds()/3600,
             "ic_process_hours_sum": sum(r["wall_seconds"] for r in ic_rows)/3600,
             "ic_process_minutes_min": min(r["wall_seconds"] for r in ic_rows)/60,
             "ic_process_minutes_median": median(r["wall_seconds"] for r in ic_rows)/60,
             "ic_process_minutes_max": max(r["wall_seconds"] for r in ic_rows)/60,
             "lbfgs_actual_iterations_min": min(r["history"]["lbfgs_n_iter"] for r in new_records),
             "lbfgs_actual_iterations_max": max(r["history"]["lbfgs_n_iter"] for r in new_records),
             "lbfgs_closures_min": min(r["history"]["lbfgs_func_evals"] for r in new_records),
             "lbfgs_closures_max": max(r["history"]["lbfgs_func_evals"] for r in new_records)}
    dense_max = {metric: max(abs(x-y) for row in diagnostics.values()
                            for x,y in zip(row["dense_metrics"][metric], row["metrics"][metric])) for metric in ("vol", "trace")}
    audit = {"generated_local": datetime.now(TZ).isoformat(), "inventory": inventory,
             "result_count": len(records), "old260_hash_match": True,
             "raw_result_file_count": len(raw_hashes), "new22_validation_hash_match": True,
             "training_sources_match_engineering_gate": True, "dense_metric_max_absolute_difference": dense_max,
             "gate_references": gate["references"], "pairs": pairs, "groups": groups, "A1": a1,
             "A2_joint": True, "costs": costs, "raw_sha256": raw_hashes,
             "validation_sha256": {p.name: sha(p) for p in STAGE.glob("*.json")},
             "analysis_type": "事后描述性汇总；没有训练、选参、改判或新的性能阈值", "phase2_started": False}

    lines = ["# R33 第一阶段结果分析与论文证据整理", "",
             f"整理时间：{audit['generated_local']}。本报告由保存结果自动汇总，新增分析为事后描述性分析。", "",
             "**判断：值得继续完成一篇范围明确的方法论文初稿，并优先补 τ 灵敏度；当前不建议启动大规模调参。** 第一阶段回答了 E1 PirateNet 是否可叠加、换初值后是否仍有收益两项问题，但没有证明任意初值、任意优化器或所有种子上都更好。A-1、G2 和 E4 的负面结论保持原样。", "",
             "## 1. 完成状态与数据可信度", "",
             f"第一阶段于 {local(state['started_utc'])} 启动、{local(completion['completed_utc'])} 完成，实测 {costs['local_total_hours']:.2f} 小时。四个 PirateNet 按原 checkpoint 续跑、18 个新初值任务完整训练；22/22 完整产物身份/哈希及原设置与 N96/GL400 误差复算均通过。", "",
             f"本次重新核对全部 {len(records)} 个结果 JSON 与对应权重，共 {len(raw_hashes)} 个原始结果文件；旧 260 文件 SHA256 未变。新增 22 份 JSON 与验证时哈希一致，训练源代码仍匹配开跑工程门。这里复用已通过的模型加载与数值重算，并独立检查哈希、聚合及加密误差容差；没有重复训练。", "",
             f"新结果原/加密误差序列最大绝对差：体 {dense_max['vol']:.3e}、迹 {dense_max['trace']:.3e}。新初值参考解 N48/N96 差分别为 {gate['references'][0]['N48_N96_max_abs']:.3e}、{gate['references'][1]['N48_N96_max_abs']:.3e}，E1 独立本征展开差为 {gate['references'][0]['independent_eigen_max_abs']:.3e}。这些参考核验覆盖五个既定时刻，不扩展到 t→0。", "",
             table(["tag", "JSON", "base PT", "完整 model PT"], [[tag, *[r[k] for k in ("json", "base_pt", "model_pt")]] for tag,r in inventory.items()]), "",
             "其中 preflight4 的 24 次为独立种子 100/101 的小预算投入检查，不进入正式主表；旧 E4 的 20 个 PT 缺表面分支，表面 v(t) 不列为可复现定量证据。旧三个零结果 tag 仍为空；本轮没有调参结果，也没有可以填写的‘调参后对调参后’表。", "",
             "## 2. 主指标、统计口径与全种子对照", "",
             "主指标是每个种子在 t={0.05,0.1,0.25,0.5,1} 五个时刻上的最大体相对 L²，再对种子 0/1/2 取中位数。改善倍数为两方法中位数之比，**不是配对比值的中位数，也不是连续时间最大误差**。小样本仅作描述性比较；不使用显著性措辞或把 3/3 当成总体成功概率。", "",
             table(["问题 / 架构", "vanilla ÷ 校正", "hardic ÷ 校正", "配对改善种子", "配对比（s0/s1/s2）"],
                   [[f"{p['eq']} / {'PirateNet 变体' if p['tag']=='pirate' else 'MLP'}",
                     f"{p['vanilla_over_layer']:.2f}" if 'vanilla_over_layer' in p else "未在本架构比较",
                     f"{p['hardic_over_layer']:.2f}", f"{p['paired_wins']}/3",
                     " / ".join(f"{v:.3f}" for v in p['paired_ratios'])] for p in pairs]), "",
             "四个 MLP 配置（原/新初值 × E1/E3）的三种子中位数均改善；12 个配对种子中 11 个改善。原初值的两个 PirateNet 配置共 6 个配对种子均改善。这些计数仅描述当前样本，不把相关配置合并成新的统计检验。", "",
             "![逐种子误差与中位数](validation/stage5_analysis_20261022/逐种子误差.png)", "",
             "图中点为全部种子，短横线为中位数，连线只对应相同种子；纵轴为对数。1e−2 线仅为原协议报告阈值，不是发表标准。", "",
             "### 2.1 新初值的完整对照", "",
             table(["问题", "方法", "seed 0", "seed 1", "seed 2", "体误差中位数", "迹误差中位数", "体≤1e−2"],
                   [[eq,NAMES[m],*[f(x) for x in g('final_ic_v1',eq,m)['seeds']],f(g('final_ic_v1',eq,m)['median']),
                     f(g('final_ic_v1',eq,m)['trace_median']),f"{g('final_ic_v1',eq,m)['under_1e2']}/3"]
                    for eq in ("E1_heat_cos","E3_fisher_cos") for m in METHODS]), "",
             "E1 新初值：hardic+layer 三个种子均优于 hardic，中位数收益 2.69 倍，低于原初值的 34.83 倍。新初值没有预注册三倍通过门，因此不能把这一结果重新包装成‘达标’或‘失败’；它说明收益随问题配置变化。", "",
             "E3 新初值：中位数收益 7.34 倍，但 seed 0 的体误差由 5.2185e−4 变为 5.4048e−4，增加约 3.57%；同种子的迹误差仍下降。seed 1/2 的体误差明显降低。该组收益主要体现为较差种子误差减轻；不能声称逐种子一致改善或已证明训练稳定性的总体提升。", "",
             "### 2.2 PirateNet 补齐与原判据", "",
             table(["问题", "方法", "seed 0", "seed 1", "seed 2", "中位数"],
                   [[eq,NAMES[m],*[f(x) for x in g('pirate',eq,m)['seeds']],f(g('pirate',eq,m)['median'])]
                    for eq in ("E1_heat","E3_fisher") for m in ("hardic","hardic+layer")]), "",
             "A-2 按原规则更新为 E1/E3 均满足：22.61/5.52 倍。只完成了此前缺失的 E1 判定，没有改门槛。PirateNet 名称须注明实际使用的是省略物理信息最小二乘初始化的变体；本机续跑保持原任务身份，不声称跨机器训练轨迹逐位一致。", "",
             table(["A-1 问题", "较好因果中位数", "PirateNet hardic 中位数", "最好基线", "最好基线 ÷ MLP校正", "≥3"],
                   [[r['eq'],f(min(r['baselines']['causal1'],r['baselines']['causal10'])),f(r['baselines']['pirate']),
                     r['best'],f"{r['ratio']:.3f}","是" if r['passed'] else "否"] for r in a1]), "",
             "A-1 仍整体不满足，E3 为 1.47 倍；修订 4 的 G2 仍未通过。E4 对 vanilla 的中位数比约 0.838，修正没有显示优势；E3 κ=0.1 的修正误差约高 38%。这些反例必须保留。", "",
             "## 3. 时间分布与独立残差", "",
             "下表是各时刻体误差的三种子中位数，与‘各种子先取最大值再取中位数’的主指标不同。", "",
             table(["新初值", "方法", *[f"t={t:g}" for t in TIMES]],
                   [[eq,NAMES[m],*[f(x) for x in g('final_ic_v1',eq,m)['time_medians']]]
                    for eq in ("E1_heat_cos","E3_fisher_cos") for m in METHODS]), "",
             "![新初值各时刻误差](validation/stage5_analysis_20261022/逐时刻误差.png)", "",
             "独立检验点沿用修订 5：固定 RNG 330500，体 8192 点、各边界 1024 点、初值 1024 点；时间均匀分布在 [1e−4,1]。下表是各分量 RMS 的种子中位数，点未参与训练或选参。不同分量没有统一归一化，不直接混成一个排名。", "",
             table(["新初值", "方法", "PDE RMS", "左 Neumann RMS", "右动态边界 RMS", "初值 RMS"],
                   [[eq,NAMES[m],*[f(g('final_ic_v1',eq,m)['heldout_medians'][k]['rms'])
                                    for k in ("pde","left_neumann","right_dynamic","initial")]]
                    for eq in ("E1_heat_cos","E3_fisher_cos") for m in METHODS]), "",
             "PDE 残差与解误差并不总同序：E1 新初值的 vanilla 的 PDE RMS 中位数低于修正方法，但其体误差更高且初值不精确。这表明单看 PDE 残差会遗漏初值/边界误差影响，不能把较小训练损失或某个单项残差直接当成更准确的解。当前没有据残差或参考解重新选配置。", "",
             "相对 hardic，修正的 PDE RMS 中位数在两个新初值上都降低；右边界也有中位数改善，但 E1 seed 0 的右动态边界 RMS 由 7.8475e−4 升到 8.0618e−4（约 +2.73%）。修正仅精确满足初值，不保证全域 PDE/边界残差处处改善或为零。", "",
             "本次五个评价时刻从 0.05 开始；独立残差采用均匀时间点。它们不足以刻画非常薄的 t→0 角点层，也没有证明 δ 为收益的唯一原因。若论文强化机制解释，应先核早期参考解分辨率，再对已保存模型作独立的早期时空诊断。", "",
             "## 4. 实际计算量与墙钟解释", "",
             f"本机批次墙钟：PirateNet 四次续跑及复核约 {costs['pirate_batch_including_validation_hours']:.2f} 小时；18 次新初值及复核约 {costs['ic_batch_including_validation_hours']:.2f} 小时。新初值累加进程耗时 {costs['ic_process_hours_sum']:.2f} 小时，单次 {costs['ic_process_minutes_min']:.1f}–{costs['ic_process_minutes_max']:.1f} 分钟、中位数 {costs['ic_process_minutes_median']:.1f} 分钟；并行进程耗时之和不等于整机完成时间或 CPU 核时。", "",
             "18:54 因用户报告卡顿，八个训练进程从 Normal 降为 BelowNormal，模型/训练配置未改。末尾两个任务开始时并发负载较低，其耗时明显短于早期任务。不能由这批异负载墙钟推出固定百分比额外开销、同时间优势或硬件无关速度排名。PirateNet JSON 的 wall_seconds 包含此前云端保存的训练历史，也不能当作本机续跑时长。", "",
             f"22 个新完成任务均沿用 Adam 20000 调用的总轨迹和 L-BFGS 3000 的名义预算；恢复任务只补剩余 Adam。实际 L-BFGS 内部迭代为 {costs['lbfgs_actual_iterations_min']}–{costs['lbfgs_actual_iterations_max']}，closure 为 {costs['lbfgs_closures_min']}–{costs['lbfgs_closures_max']}。下面保留实际计数。名义预算用满不意味着内部 n_iter 恰好等于 3000，也不证明达到全局最优或充分收敛。", "",
             table(["任务", "seed", "Adam恢复点", "L-BFGS 内部迭代", "closure", "停止原因", "轨迹墙钟/分钟"],
                   [[f"{r['eq']} / {r['method']}",r['seed'],"; ".join(r['history'].get('resumed_at',[])) or "从头",
                     r['history']['lbfgs_n_iter'],r['history']['lbfgs_func_evals'],r['history']['lbfgs_stop_reason'],f"{r['wall_seconds']/60:.1f}"]
                    for r in new_records]), "",
             "新初值的共享架构、种子集合、采样规则、优化调用上限均一致，τ=0.1，零调参。损失中初值的处理是方法差别：vanilla 为软损失，hardic 类为解析约束。旧 RBA 的 L-BFGS 固定体点 4096，普通方法 8192，应披露，不能据同一上限声称相同实际计算量。所有损失、逐时刻指标、计数、残差及来源路径见 all_runs.csv；未保存项留空，未补造旧计数。", "",
             "## 5. 论文可写内容与证据缺口", "",
             table(["拟写论点", "当前判断", "证据/边界"], [
                 ["在被测一维动态边界问题上改善普通 PINN 和硬初值", "支持经验性表述", "四个 MLP 问题/初值配置中位数均改善；逐种子有一个体误差反例"],
                 ["可叠加到所用 PirateNet 变体", "支持限定表述", "原 E1/E3 均按 A-2 达到三倍，完整三种子"],
                 ["换初值仍有效", "支持两个预先固定新初值", "训练分别重做；不是一个网络泛化到未训练初值，也不是任意初值保证"],
                 ["基于经典角点层分析的修正", "可写构造与消融", "完整经典来源逐式对照仍需完成；不称首次或全新数学原理"],
                 ["对 τ 鲁棒或无参数", "证据不足", "目前 τ 固定 0.1；没有灵敏度结果"],
                 ["优化器无关或普遍强于现代 PINN", "不支持", "A-1/G2 失败；正式完整 SOAP64 尚未做"],
                 ["更省计算/稳定性有统计保证", "不支持", "异负载墙钟、实际调用不同；各配置只有三个种子"],
                 ["已具备正式投稿完成度", "尚未", "需来源、稿件、图表、复现包及目标期刊要求闭合；没有录用保证"]]), "",
             "建议结果章节顺序：原初值主表 → 新初值及同架构消融 → PirateNet 叠加 → 参数范围与失败例 → 残差及计算成本。主文保留负面结果入口，附录给全部种子；不把各方程/初值/架构拼成一项胜率或总体统计显著结论。文献定位沿用已整理的七篇原文选读，本轮不声称新增文献核验。", "",
             "可直接用于初稿的结果表述：在固定训练预算下，基于经典角点层分析的修正在所测 E1/E3 的原初值和预先指定的新初值中降低了三种子体误差中位数；新初值相对硬初值的比值为 2.69 和 7.34。该修正可叠加到本文采用的 PirateNet 变体，在原 E1/E3 上的比值为 22.61 和 5.52。收益依赖问题和种子，E3 新初值的一个种子体误差略升，弱错配参数点及 E4 存在负面结果。", "",
             "## 6. 后续投入建议（草案，未启动）", "",
             "第一优先：整理方法推导出处、主表/附录与明确范围的初稿，同时补 12 次 τ 灵敏度。这一问题直接决定‘固定 τ=0.1 的效果是否过于偶然’，比大规模调参更贴近当前论文缺口。原 E1/E3，hardic+layer，τ∈{0.03,0.3}，种子 0/1/2，完整共享预算；与旧 τ=0.1 全部并列。保持主配置 0.1，不按误差选最佳 τ；因此是敏感性描述，不是专门给候选方法挑配置。若据此换主配置，必须改走所有方法同预算的独立种子调参流程。", "",
             "第二优先：只有决定在正文增加优化器叠加论点时，再做 18 次固定 SOAP 官方语义 float64 对照：原 E1/E3 × vanilla/hardic/hardic+layer × 种子 0/1/2，lr0=0.001，其余共享完整预算，零搜索。须用新 tag，不能冒充旧 soap1e3/soap3e3；小预算 G2 失败仍保留。", "",
             "τ 批次按本次单任务范围估算，八进程预留约 3–5 小时；SOAP64 尚无本机完整预算实测，保留 4–8 小时规划区间。两者是宽松资源预算，不是性能预测或承诺；若为前台流畅降低并发，时间可能增加。执行前另行追加并提交协议，不能用本分析充当预注册。当前第二阶段未获授权，未运行任何新训练。", "",
             "不建议恢复 42 个旧基线或 322 次调参草案；无需为了满足旧强排名主张增加搜索。τ 若高度敏感，先如实写范围；SOAP 若没有叠加收益，也只收窄优化器论点，不删结果、不改原判据。", "",
             "## 7. 数据与复现入口", "",
             "- 汇总代码：validation/stage5_analysis_20261022/analyze_stage5.py（只读原始结果）。",
             "- 完整行表：validation/stage5_analysis_20261022/all_runs.csv；覆盖所有 tag，按 tag 区分筛选、正式比较及小预算检查。",
             "- 计算与哈希证据：validation/stage5_analysis_20261022/analysis_evidence.json；结束状态归档为 completion_status_snapshot.json，可脱离本机运行目录复算。",
             "- 原始本轮复核：validation/stage5_20261022/{pirate_validation,ic_validation,completion}.json。",
             "- 图：同目录 300 dpi PNG 及矢量 PDF；图上显示全部种子，没有置信区间或模拟数据。",
             "- 操作系统优先级调整：validation/stage5_20261022/priority_change_20261022.json。",
             "- 历史协议、数据和判据保留；本报告仅更新完成状态及已注册 A-2 的最终判定。", ""]
    md = "\n".join(lines)
    (ROOT / "STAGE5_ANALYSIS_20261022.md").write_text(md, encoding="utf-8")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
                         "axes.unicode_minus": False, "font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "pdf.fonttype": 42, "savefig.dpi": 300})
    colors = {"vanilla": "#777777", "hardic": "#0072B2", "hardic+layer": "#D55E00"}
    fig, axes = plt.subplots(2, 3, figsize=(13.2, 7.4), sharey=True, layout="constrained")
    panels = [("confirm", "E1_heat", "E1 原初值 · MLP"), ("final_ic_v1", "E1_heat_cos", "E1 新初值 · MLP"),
              ("pirate", "E1_heat", "E1 原初值 · PirateNet 变体"), ("confirm", "E3_fisher", "E3 原初值 · MLP"),
              ("final_ic_v1", "E3_fisher_cos", "E3 新初值 · MLP"), ("pirate", "E3_fisher", "E3 原初值 · PirateNet 变体")]
    markers = ("o", "s", "^")
    for ax, (tag, eq, title) in zip(axes.flat, panels):
        methods = METHODS if tag != "pirate" else METHODS[1:]
        for seed, offset in enumerate((-0.07, 0, 0.07)):
            ax.plot([i+offset for i in range(len(methods))], [g(tag,eq,m)['seeds'][seed] for m in methods],
                    color="#b9bec5", lw=0.7, alpha=0.8, zorder=1)
            for i,m in enumerate(methods):
                ax.scatter(i+offset,g(tag,eq,m)['seeds'][seed],marker=markers[seed],s=35,color=colors[m],zorder=3)
        for i,m in enumerate(methods):
            ax.plot([i-0.18,i+0.18],[g(tag,eq,m)['median']]*2,color=colors[m],lw=2.6,zorder=4)
        ax.set(yscale="log",ylim=(5e-5,1.4e-1),title=title,xticks=range(len(methods)),
               xticklabels=[NAMES[m] for m in methods])
        ax.axhline(1e-2,color="#a0a0a0",ls="--",lw=0.8)
        ax.grid(axis="y",which="major",ls=":",color="#dddddd")
    axes[0,0].set_ylabel("五个时刻最大体相对 L²")
    axes[1,0].set_ylabel("五个时刻最大体相对 L²")
    fig.legend(handles=[Line2D([],[],ls="",marker=markers[s],color="#444444",label=f"种子 {s}") for s in range(3)] +
                       [Line2D([],[],lw=2.6,color="#444444",label="中位数")],loc="outside lower center",ncol=4,frameon=False)
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"逐种子误差.{ext}")
    plt.close(fig)
    fig, axes = plt.subplots(1,2,figsize=(11.4,4.2),layout="constrained")
    for ax,eq in zip(axes,("E1_heat_cos","E3_fisher_cos")):
        for m in METHODS:
            for s in range(3):
                rec = records[("final_ic_v1",eq,m,s)]
                ax.plot(TIMES,rec['metrics']['vol'],color=colors[m],alpha=.25,lw=.75)
            ax.plot(TIMES,g('final_ic_v1',eq,m)['time_medians'],color=colors[m],marker="o",lw=2,label=NAMES[m])
        ax.set(yscale="log",xlabel="时间 t",ylabel="体相对 L²",title=eq,xticks=TIMES,
               xticklabels=[f"{t:g}" for t in TIMES])
        ax.tick_params(axis="x", labelrotation=35)
        ax.grid(axis="y",ls=":",color="#dddddd")
        ax.legend(frameon=False)
    fig.suptitle("新初值：浅线为各个种子，粗线为逐时刻中位数",fontsize=11)
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"逐时刻误差.{ext}")
    plt.close(fig)

    import markdown
    body = markdown.markdown(md.replace("validation/stage5_analysis_20261022/", ""), extensions=["tables", "toc"])
    doc = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>R33 第一阶段结果分析</title><style>
    body{margin:0;background:#f4f6f8;color:#1f2937;font:16px/1.8 'Microsoft YaHei',sans-serif}
    main{max-width:1160px;margin:28px auto;background:white;padding:30px 42px;border-radius:12px}
    h1{font-size:29px}h2{font-size:23px;margin-top:38px;border-bottom:2px solid #dbe4ed;padding-bottom:8px}
    h3{font-size:19px}p,li{max-width:100%}table{border-collapse:collapse;width:100%;font-size:13px;margin:20px 0;display:block;overflow-x:auto}
    th,td{padding:9px 11px;border-bottom:1px solid #dbe4ed;white-space:normal}th{background:#eaf1f8;text-align:left}
    tr:nth-child(even){background:#f8fafc}img{max-width:100%;height:auto}a{color:#1d4ed8}strong{color:#153d63}
    @media(max-width:700px){main{margin:0;padding:18px}h1{font-size:24px}}@media print{main{margin:0;padding:0}body{background:white}table{display:table;font-size:10px}}
    </style><main>""" + body + "</main></html>"
    (OUT / "第一阶段分析与论文证据.html").write_text(doc,encoding="utf-8")
    assert all(sha(ROOT/p)==expected for p,expected in raw_hashes.items())
    audit["raw_files_unchanged_after_analysis"] = True
    audit["analysis_script_sha256"] = sha(__file__)
    dump(OUT / "analysis_evidence.json",audit)
    print(json.dumps({k:audit[k] for k in ("result_count","raw_result_file_count","pairs","A1","costs","dense_metric_max_absolute_difference")},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()

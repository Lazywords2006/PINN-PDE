"""Plot all 36 original/new-IC default Adam runs; never trains or selects seeds.

Adapted from plot-from-data/bar_grouped_hatch: grouped methods, neutral/red
colors, light horizontal grid, open axes and 300 dpi. Actual seed points and
paired thin lines replace bars because n=3 and the error spans orders of magnitude.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
from statistics import median

os.environ.setdefault("MPLCONFIGDIR", r"D:\CodexRuntime\cache\matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", r"D:\CodexRuntime\cache\xdg")

ROOT = Path(__file__).resolve().parents[2]
FIGURES = Path(__file__).resolve().parent
MANIFEST = ROOT / "validation/stage5_analysis_20261022/analysis_evidence.json"
TIMES = [.05, .1, .25, .5, 1.]
METHODS = ("vanilla", "hardic", "hardic+layer")
LABELS = ("普通 PINN", "硬初值", "硬初值＋校正")
COLORS = ("#8A8A8A", "#5687A8", "#D00000")
MARKERS = ("o", "^", "s")
PANELS = (("a", "confirm", "E1_heat", "E1 · 原初值（历史云端）"),
          ("b", "confirm", "E3_fisher", "E3 · 原初值（历史云端）"),
          ("c", "final_ic_v1", "E1_heat_cos", "E1 · 新初值（本机）"),
          ("d", "final_ic_v1", "E3_fisher_cos", "E3 · 新初值（本机）"))


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def load_data():
    raw_manifest = MANIFEST.read_bytes()
    frozen = json.loads(raw_manifest)["raw_sha256"]
    if len(frozen) != 398:
        raise ValueError("历史冻结清单不是398个文件")
    rows = []
    for panel, tag, eq, _ in PANELS:
        for method in METHODS:
            for seed in (0, 1, 2):
                relative = f"runs/{tag}/{eq}/{method.replace('+', '_')}_s{seed}.json"
                raw = (ROOT / relative).read_bytes()
                digest = sha_bytes(raw)
                if frozen.get(relative) != digest:
                    raise ValueError(f"图表来源未绑定历史冻结清单：{relative}")
                rec = json.loads(raw)
                if (rec["tag"], rec["eq"], rec["method"], rec["seed"]) != (tag, eq, method, seed):
                    raise ValueError(f"任务身份不一致：{relative}")
                if rec["metrics"]["times"] != TIMES or rec["max_vol"] != max(rec["metrics"]["vol"]):
                    raise ValueError(f"主指标或评价时刻不一致：{relative}")
                value = rec["max_vol"]
                if not math.isfinite(value) or value <= 0:
                    raise ValueError("对数图要求当前数据为有限正值，不以epsilon替换零")
                rows.append({"panel": panel, "tag": tag, "equation": eq, "method": method,
                             "seed": seed, "max_vol": value, "source": relative, "sha256": digest})
    assert len(rows) == 36 and len({r["source"] for r in rows}) == 36
    return rows, sha_bytes(raw_manifest)


def main(output):
    if output.exists():
        raise FileExistsError("目标目录已存在；不覆盖历史图表，请用--output指定新的版本目录")
    rows, manifest_hash = load_data()
    by_id = {(r["panel"], r["method"], r["seed"]): r for r in rows}
    build = Path(r"D:\CodexRuntime\runs\r33_paper_figures") / datetime.now().strftime("history_%Y%m%d_%H%M%S_%f")
    build.mkdir(parents=True, exist_ok=False)
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager, ft2font
    from matplotlib.lines import Line2D
    import matplotlib.pyplot as plt
    font = Path(r"C:\Windows\Fonts\msyh.ttc")
    font_manager.fontManager.addfont(str(font))
    font_name = font_manager.FontProperties(fname=str(font)).get_name()
    required = "普通硬初值校正原新历史云端本机最大体相对误差种子中位数同细线连接并非置信区间全部结果越低越好每个单独训练高于参考线"
    glyphs = ft2font.FT2Font(str(font)).get_charmap()
    if any(ord(ch) not in glyphs for ch in required):
        raise ValueError("绘图字体缺字")
    matplotlib.rcParams.update({"text.usetex": False, "font.family": "sans-serif",
        "font.sans-serif": [font_name, "DejaVu Sans"], "axes.unicode_minus": False,
        "font.size": 10, "axes.titlesize": 11.5, "axes.labelsize": 10.5,
        "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": .9,
        "pdf.fonttype": 42})
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8.2), sharey=True)
    groups, pairs = [], []
    for ax, (panel, tag, eq, title) in zip(axes.flat, PANELS):
        for seed, marker, offset in zip((0, 1, 2), MARKERS, (-.12, 0, .12)):
            values = [by_id[(panel, method, seed)]["max_vol"] for method in METHODS]
            ax.plot([i + offset for i in range(3)], values, color="#BBBBBB", lw=.7, alpha=.8, zorder=2)
            for i, value in enumerate(values):
                ax.scatter([i + offset], [value], marker=marker, s=46, color=COLORS[i],
                           edgecolors="white", linewidths=.55, zorder=4)
            pairs.append({"panel": panel, "tag": tag, "equation": eq, "seed": seed,
                          "hardic": values[1], "layer": values[2],
                          "hardic_over_layer": values[1] / values[2],
                          "layer_lower_than_hardic": values[2] < values[1]})
        for i, method in enumerate(METHODS):
            values = [by_id[(panel, method, seed)]["max_vol"] for seed in (0, 1, 2)]
            ax.hlines(median(values), i - .24, i + .24, color="#202020", lw=2, zorder=5)
            groups.append({"panel": panel, "tag": tag, "equation": eq, "method": method,
                           "seeds": values, "median": median(values), "min": min(values), "max": max(values)})
        ax.axhline(1e-2, color="#4063A1", ls="--", lw=.9, zorder=1)
        ax.set(yscale="log", ylim=(1e-4, .1), xlim=(-.4, 2.65), title=f"({panel}) {title}")
        ax.set_xticks([0, 1, 2], LABELS)
        ax.set_ylabel("五时刻最大体相对 L² 误差")
        ax.yaxis.grid(True, which="major", color="#EBEBEB", ls="--", lw=.7)
        ax.tick_params(direction="out", length=3, width=.8)
        ax.set_axisbelow(True)
    exception = next(r for r in pairs if r["panel"] == "d" and r["seed"] == 0)
    percent = 100 * (exception["layer"] / exception["hardic"] - 1)
    axes[1, 1].annotate(f"种子0：校正后高 {percent:.2f}%", xy=(1.88, exception["layer"]),
                        xytext=(1.1, 1.3e-4), fontsize=9, color="#8B2424",
                        arrowprops={"arrowstyle": "->", "color": "#8B2424", "lw": .8},
                        ha="left", va="bottom")
    handles = [Line2D([], [], marker=marker, color="#555555", ls="None", markersize=6,
                      label=f"种子 {seed}") for seed, marker in enumerate(MARKERS)]
    handles += [Line2D([], [], color="#202020", lw=2, label="中位数"),
                Line2D([], [], color="#BBBBBB", lw=.8, label="同种子连接"),
                Line2D([], [], color="#4063A1", lw=.9, ls="--", label="1e−2 参考线")]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.5, .955), ncol=6,
               frameon=False, fontsize=9, columnspacing=1.4)
    fig.suptitle("默认 Adam：原初值与固定新初值的全部种子", y=.995, fontsize=14)
    fig.text(.5, .035, "每个初值单独训练；纵轴越低越好；短横线为中位数，非置信区间", ha="center", fontsize=10)
    fig.subplots_adjust(left=.09, right=.985, bottom=.11, top=.86, wspace=.24, hspace=.39)
    for extension in ("png", "pdf"):
        fig.savefig(build / f"historical_comparison.{extension}", dpi=300, facecolor="white")
    plt.close(fig)
    with (build / "historical_comparison_data.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    counts = {tag: sum(r["layer_lower_than_hardic"] for r in pairs if r["tag"] == tag)
              for tag in ("confirm", "final_ic_v1")}
    caption = ("图：默认Adam下普通PINN、硬初值及硬初值加校正的全部报告种子。每个点为t={0.05,0.1,0.25,0.5,1}五个时刻中的最大体相对L²误差，纵轴为对数尺度；圆、三角、方形对应种子0、1、2，细线仅连接相同种子，短横线为三种子中位数，均不表示置信区间。蓝色虚线为1e−2参考线，不是发表标准。上排原初值来自历史云端confirm，下排固定新初值来自本机final_ic_v1；各问题分别训练，不能据上下排差异隔离初值和运行环境的因果效应，也不代表模型直接泛化到新初值。相同初值内，校正对硬初值的逐种子比较原初值为"
               f"{counts['confirm']}/6改善、新初值为{counts['final_ic_v1']}/6改善；新E3种子0校正误差高{percent:.2f}%，保留图示。该图未覆盖RBA、因果训练、PirateNet、弱错配和E4；对应完整对照及负面结果须结合正文表格阅读。")
    (build / "historical_comparison_caption.md").write_text(caption + "\n", encoding="utf-8")
    for row in rows:
        if sha_bytes((ROOT / row["source"]).read_bytes()) != row["sha256"]:
            raise ValueError("绘图期间输入发生变化，未发布")
    evidence = {"generated_utc": datetime.now(timezone.utc).isoformat(), "kind": "historical_real_data_figure",
                "training_runs_started": 0, "rows": 36, "groups": groups, "pairs": pairs,
                "paired_improvement_counts": counts, "confidence_intervals": False,
                "statistical_significance_claimed": False, "new_ic_seed0_E3_worsening_percent": percent,
                "manifest_source": str(MANIFEST.relative_to(ROOT)), "manifest_sha256": manifest_hash,
                "source_sha256": sha_bytes(Path(__file__).read_bytes()), "matplotlib": matplotlib.__version__,
                "font": str(font), "font_sha256": sha_bytes(font.read_bytes()), "png_dpi": 300,
                "pdf_vector": True, "raw_sha256": {r["source"]: r["sha256"] for r in rows},
                "visual_review": "pending", "outputs": {p.name: sha_bytes(p.read_bytes()) for p in build.iterdir()}}
    (build / "historical_comparison_evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copytree(build, output)
    print(json.dumps({"output": str(output), "rows": len(rows), "paired_counts": counts,
                      "new_ic_E3_seed0_worsening_percent": percent}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=FIGURES / "history_v1")
    main(parser.parse_args().output.resolve())

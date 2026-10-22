"""Real-data-only stage 6 figures. No demo data, inferred seeds, or confidence intervals.

Visual parameters adapted from plot-from-data/bar_grouped_hatch: grouped method
layout, neutral/red palette, light horizontal grid, open axes, 300-dpi exports.
With three seeds, actual scatter points plus median/range replace filled bars.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", r"D:\CodexRuntime\cache\matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", r"D:\CodexRuntime\cache\xdg")

METHODS = ("vanilla", "hardic", "hardic+layer")
NAMES = {"vanilla": "普通 PINN", "hardic": "硬初值", "hardic+layer": "硬初值＋校正"}
COLORS = {"vanilla": "#8A8A8A", "hardic": "#5687A8", "hardic+layer": "#D00000"}
SEED_MARKERS = ("o", "^", "s")
EQUATIONS = ("E1_heat", "E3_fisher")


def font_setup():
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager, ft2font
    candidates = [Path(r"C:\Windows\Fonts\msyh.ttc"), Path(r"C:\Windows\Fonts\simhei.ttf")]
    selected = next((p for p in candidates if p.is_file()), None)
    if selected is None:
        raise RuntimeError("没有找到本地微软雅黑/黑体；请指定经核验的中文字体后再正式绘图")
    font_manager.fontManager.addfont(str(selected))
    name = font_manager.FontProperties(fname=str(selected)).get_name()
    glyphs = ft2font.FT2Font(str(selected)).get_charmap()
    required = "最大体相对误差普通硬初值校正历史云端本机种子中位数范围默认配置灵敏度三档不选参五个固定评价时刻连续时间上确界路线→"
    missing = [ch for ch in set(required) if ord(ch) not in glyphs]
    if missing:
        raise RuntimeError(f"中文字体缺字：{missing}")
    matplotlib.rcParams.update({"text.usetex": False, "font.family": "sans-serif",
        "font.sans-serif": [name, "DejaVu Sans"], "axes.unicode_minus": False,
        "font.size": 10, "axes.labelsize": 11, "axes.titlesize": 12,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": .9, "pdf.fonttype": 42, "savefig.dpi": 300})
    return {"font_name": name, "font_file": str(selected),
            "font_sha256": hashlib.sha256(selected.read_bytes()).hexdigest(), "chinese_glyph_check": True}


def validate_plot_input(audit):
    if audit.get("analysis_state") != "complete" or audit.get("new_task_count") != 30:
        raise ValueError("图表只接受完整 30/30 分析，不接受 partial 或模拟占位")
    defaults, taus = audit["default_groups"], audit["tau_groups"]
    default_ids = {(r["eq"], r["tag"], r["method"]) for r in defaults}
    expected_default = {(eq, tag, method) for eq in EQUATIONS
                        for tag in ("confirm", "final_soap64_v1") for method in METHODS}
    if len(defaults) != 12 or default_ids != expected_default:
        raise ValueError("默认六臂缺失或重复")
    tau_ids = {(r["eq"], r["tau"]) for r in taus}
    if len(taus) != 6 or tau_ids != {(eq, tau) for eq in EQUATIONS for tau in (.03, .1, .3)}:
        raise ValueError("τ 档位缺失或重复")
    if any(len(row["seeds"]) != 3 for row in defaults + taus):
        raise ValueError("每组必须展示真实的 0/1/2 三个种子")
    evidence = audit.get("evidence", {})
    if evidence.get("old398_unchanged") is not True or evidence.get("new_raw_files") != 90 or len(evidence.get("raw_sha256", {})) != 488:
        raise ValueError("缺少旧 398 + 新 90 个原始文件的完整性绑定")
    records = {tuple(row["job"]): row for row in audit.get("records", [])}
    for row in defaults + taus:
        expected = [records[(row["tag"], row["eq"], row["method"], seed)]["max_vol"] for seed in (0, 1, 2)]
        if row["seeds"] != expected:
            raise ValueError("图中种子与已核原始记录不一致")


def draw_group(ax, x, row, color):
    values = row["seeds"]
    ax.vlines(x, min(values), max(values), color="#777777", lw=1., zorder=2)
    for offset, marker, value in zip((-.13, 0, .13), SEED_MARKERS, values):
        ax.scatter([x + offset], [value], marker=marker, s=43, color=color,
                   edgecolors="white", linewidths=.5, zorder=4)
    ax.hlines(row["median"], x - .24, x + .24, color="#202020", lw=2.0, zorder=3)


def finish_axes(ax, rows):
    values = [value for row in rows for value in row["seeds"]]
    if all(value > 0 for value in values):
        ax.set_yscale("log")
        scale = "log"
    else:
        positives = [value for value in values if value > 0]
        threshold = min(positives) / 10 if positives else 1e-12
        ax.set_yscale("symlog", linthresh=threshold)
        scale = "symlog (preserves actual zeros)"
    ax.axhline(1e-2, color="#4063A1", lw=1., ls="--", alpha=.8, zorder=1)
    ax.yaxis.grid(True, color="#EBEBEB", linewidth=.7, linestyle="--", zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(direction="out", length=3, width=.8)
    ax.set_ylabel("五时刻最大体相对 L² 误差")
    ax.margins(y=.25)
    return scale


def legend(fig):
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], marker=marker, color="#444444", linestyle="None", markersize=6,
                      label=f"种子 {seed}") for seed, marker in enumerate(SEED_MARKERS)]
    handles += [Line2D([], [], color="#202020", lw=2, label="中位数"),
                Line2D([], [], color="#777777", lw=1, marker="|", label="最小–最大范围（非 CI）"),
                Line2D([], [], color="#4063A1", lw=1, ls="--", label="1e-2 参考线")]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.5, .92), ncol=6,
               fontsize=9, frameon=False, handlelength=1.7, columnspacing=1.25)


def save(fig, output, name):
    import matplotlib.pyplot as plt
    paths = []
    for extension in ("png", "pdf"):
        path = Path(output) / (name + "." + extension)
        fig.savefig(path, dpi=300, facecolor="white", bbox_inches="tight")
        paths.append(path.name)
    plt.close(fig)
    return paths


def render(audit, output):
    validate_plot_input(audit)
    font = font_setup()
    import matplotlib
    import matplotlib.pyplot as plt
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    metadata = {"font": font, "matplotlib": matplotlib.__version__, "png_dpi": 300,
                "pdf_vector": True, "confidence_intervals": False, "synthetic_data": False,
                "reference_line": 1e-2, "reference_line_is_publication_threshold": False,
                "evaluation_times": [.05, .1, .25, .5, 1.],
                "maximum_scope": "五个固定评价时刻的最大值，非连续时间上确界",
                "zorder": {"range": 2, "median": 3, "seed_points": 4},
                "training_routes": {"default_confirm": "Adam→L-BFGS",
                                    "default_stage6": "SOAP64→L-BFGS", "tau": "Adam→L-BFGS"},
                "template": "plot-from-data/bar_grouped_hatch：保留分组、配色、网格与导出参数；改为种子散点+中位数/范围。",
                "figures": []}
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.6))
    fig.subplots_adjust(left=.08, right=.985, bottom=.25, top=.76, wspace=.26)
    fig.suptitle("默认配置六臂：全部种子与中位数", y=.98, fontsize=14)
    legend(fig)
    scales = []
    for ax, eq in zip(axes, EQUATIONS):
        rows = [r for r in audit["default_groups"] if r["eq"] == eq]
        for tag, base in (("confirm", 0), ("final_soap64_v1", 4)):
            for i, method in enumerate(METHODS):
                row = next(r for r in rows if r["tag"] == tag and r["method"] == method)
                draw_group(ax, base + i, row, COLORS[method])
        ax.axvspan(-.5, 2.5, color="#F0F0F0", zorder=0)
        ax.axvspan(3.5, 6.5, color="#FFF5ED", zorder=0)
        ax.set_xticks([0, 1, 2, 4, 5, 6], [NAMES[m] for m in METHODS] * 2, fontsize=9)
        ax.set_xlim(-.6, 6.6)
        ax.text(1, -.20, "Adam→L-BFGS\n（历史云端 confirm）", transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=10)
        ax.text(5, -.20, "SOAP64→L-BFGS\n（本机 stage6）", transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=10)
        ax.set_title(eq)
        scales.append(finish_axes(ax, rows))
    fig.text(.5, .025, "评价时刻 t={0.05, 0.1, 0.25, 0.5, 1}；最大值仅针对这五个固定时刻（非连续时间上确界）。",
             ha="center", fontsize=9)
    metadata["figures"].append({"files": save(fig, output, "default_six_arms"), "seed_points": 36,
                                "medians": 12, "y_scales": scales, "training_location_labels": True})
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.5))
    fig.subplots_adjust(left=.085, right=.98, bottom=.22, top=.76, wspace=.28)
    fig.suptitle("τ 灵敏度：Adam→L-BFGS；三档全部报告，主配置保持 0.1", y=.98, fontsize=14)
    legend(fig)
    scales = []
    for ax, eq in zip(axes, EQUATIONS):
        rows = [r for r in audit["tau_groups"] if r["eq"] == eq]
        for i, tau in enumerate((.03, .1, .3)):
            row = next(r for r in rows if r["tau"] == tau)
            draw_group(ax, i, row, COLORS["hardic+layer"])
        ax.axvspan(.55, 1.45, color="#F0F0F0", zorder=0)
        ax.set_xticks([0, 1, 2], ["τ=0.03\n本机 stage6", "τ=0.1（主配置）\n历史云端 confirm", "τ=0.3\n本机 stage6"])
        ax.set_xlim(-.5, 2.5)
        ax.set_title(eq)
        scales.append(finish_axes(ax, rows))
    fig.text(.5, .025, "评价时刻 t={0.05, 0.1, 0.25, 0.5, 1}；最大值仅针对这五个固定时刻（非连续时间上确界）。",
             ha="center", fontsize=9)
    metadata["figures"].append({"files": save(fig, output, "tau_sensitivity"), "seed_points": 18,
                                "medians": 6, "y_scales": scales, "training_location_labels": True})
    return metadata

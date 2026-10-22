"""Illustrate the known auxiliary function Q=w_t, not a trained PDE solution.

Visual style: plot-from-data/line_training_curve (sans-serif, four spines,
outward ticks, no grid, 300 dpi). All example training data are replaced by
direct evaluation of manuscript equations (7) and (11); no random numbers.
"""
import csv
import hashlib
import json
import math
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", r"D:\CodexRuntime\cache\matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", r"D:\CodexRuntime\cache\xdg")
import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager, ft2font
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent
C = 0.3  # E1 default c/sqrt(D); illustration choice, not a fitted parameter.
TIMES = (1e-4, 1e-3, 1e-2, 1e-1)
POSITIONS = (0.0, 0.01, 0.05, 0.1)
COLORS = ("#5B0DAD", "#3D78C2", "#399B91", "#D05A35")
STYLES = ("-", "--", "-.", ":")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def q(y, t):
    # On this fixed plotting domain, y/C+t/C^2 <= 2.445. The direct
    # exponential is bounded; erfc underflow represents a negligible tail.
    return math.exp(y / C + t / C ** 2) * math.erfc(y / (2 * math.sqrt(t)) + math.sqrt(t) / C)


def main():
    font = Path(r"C:\Windows\Fonts\msyh.ttc")
    if not font.exists():
        raise RuntimeError("本机微软雅黑字体缺失，未自动替换或下载字体")
    font_manager.fontManager.addfont(str(font))
    font_name = font_manager.FontProperties(fname=str(font)).get_name()
    labels = "固定时刻的空间剖面位置早期时间响应归一化内向距离单位层时间导数辅助模型曲线由解析公式计算边界"
    glyphs = ft2font.FT2Font(str(font)).get_charmap()
    assert all(ord(ch) in glyphs for ch in labels)
    matplotlib.rcParams.update({"font.family": "sans-serif", "font.sans-serif": [font_name, "DejaVu Sans"],
        "text.usetex": False, "font.size": 10, "axes.unicode_minus": False, "pdf.fonttype": 42})
    ygrid = np.linspace(0, 0.4, 401)
    tgrid = np.logspace(-8, -1, 281)
    rows = []
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.5))
    for t, color, style in zip(TIMES, COLORS, STYLES):
        values = [q(float(y), t) for y in ygrid]
        axes[0].plot(ygrid, values, color=color, ls=style, lw=1.7, label=rf"$t=10^{{{int(round(math.log10(t)))}}}$")
        rows.extend({"panel": "a", "C": C, "y": float(y), "t": t, "Q": value} for y, value in zip(ygrid, values))
    for y, color, style in zip(POSITIONS, COLORS, STYLES):
        values = [q(y, float(t)) for t in tgrid]
        axes[1].semilogx(tgrid, values, color=color, ls=style, lw=1.7, label=rf"$y={y:g}$" + ("（边界）" if y == 0 else ""))
        rows.extend({"panel": "b", "C": C, "y": y, "t": float(t), "Q": value} for t, value in zip(tgrid, values))
    assert all(math.isfinite(row["Q"]) and 0 <= row["Q"] <= 1 for row in rows)
    axes[0].set(xlim=(0, .4), xlabel=r"归一化内向距离 $y=(1-x)/\sqrt{D}$", title="(a) 固定时刻的空间剖面")
    axes[1].set(xlim=(1e-8, 1e-1), xlabel=r"时间 $t$", title="(b) 固定位置的早期时间响应")
    for ax in axes:
        ax.set_ylim(-.025, 1.025)
        ax.set_ylabel(r"单位层时间导数 $Q=w_t$")
        ax.tick_params(direction="out", length=4, width=.8)
        ax.grid(False)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(.9)
        ax.legend(loc="upper right" if ax is axes[0] else "center left", fontsize=9,
                  frameon=True, facecolor="white", edgecolor="#AAAAAA", framealpha=1)
    fig.subplots_adjust(left=.07, right=.985, bottom=.20, top=.88, wspace=.25)
    fig.text(.5, .035, r"辅助模型 $Q=w_t$；$C=0.3$；曲线由解析公式计算", ha="center", fontsize=10)
    for extension in ("png", "pdf"):
        fig.savefig(OUT / f"analytic_layer.{extension}", dpi=300, facecolor="white")
    plt.close(fig)
    with (OUT / "analytic_layer_data.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("panel", "C", "y", "t", "Q"))
        writer.writeheader()
        writer.writerows(rows)
    caption = "图：半直线辅助层的时间导数 Q=w_t。由式（7）直接计算，取 C=c/√D=0.3（原 E1 设置）。左图给出四个固定时刻的空间剖面；右图给出边界及三个固定内部位置的时间响应。边界处 Q 随 t↓0 趋于1，每个固定 y>0 处则趋于0；极限结论由正文推导证明。此图只展示单位辅助层，不包含幅度δ或衰减因子，不是PINN预测、原有限区间问题的参考解或实验性能证据。"
    (OUT / "analytic_layer_caption.md").write_text(caption + "\n", encoding="utf-8")
    report = {"kind": "analytic_auxiliary_function_illustration", "formula": "exp(y/C+t/C^2)*erfc(y/(2sqrt(t))+sqrt(t)/C)",
        "C": C, "times": TIMES, "positions": POSITIONS, "rows": len(rows), "training_runs": 0,
        "random_numbers_used": False, "not_full_PDE_solution": True, "not_experimental_evidence": True,
        "floating_tail_note": "极小erfc尾部可能下溢为浮点零，图示零不宣称解析函数在正时间严格为零。",
        "all_values_finite_and_in_unit_interval": True, "font": str(font), "font_sha256": sha(font),
        "source_sha256": sha(Path(__file__)), "visual_review": "pending",
        "files": {name: sha(OUT / name) for name in ("analytic_layer.png", "analytic_layer.pdf", "analytic_layer_data.csv", "analytic_layer_caption.md")}}
    (OUT / "analytic_layer_evidence.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "rows": len(rows), "training_runs": 0, "kind": report["kind"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Summary table for R32 amendments 2/2b: per cell and method, the median over seeds of the all-time max
volume relative L2 (primary metric), with trace/flux medians and U/C counts, plus the pre-registered verdicts.

    python compare_summary.py            # prints markdown tables
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
P0 = "c0.3_d0.1_k0.3"
# method label -> run tag
METHODS = {
    "vanilla": "cells",
    "w_ic=10": "probe_wic10",
    "hardic": "var_hardic",
    "t_power=2": "base_tpow2",
    "layer": "var_layer",
    "decay": "var_decay",
    "layer+decay": "var_layer+decay",
}
CELLS = ("m0_lin", "m1_lin", "m2_const", "m2_eig1")


def runs(tag: str, cell: str) -> list[dict]:
    out = []
    for p in sorted((HERE / "runs" / tag).glob(f"{cell}_{P0}_s*.json")):
        if p.stem.rsplit("_s", 1)[1].isdigit():
            out.append(json.loads(p.read_text()))
    return out


def stats(rs: list[dict]) -> dict | None:
    if not rs:
        return None
    mx = lambda r, k: max(r["metrics"][k])
    return {
        "n": len(rs),
        "vol": median(mx(r, "vol") for r in rs),
        "vols": [mx(r, "vol") for r in sorted(rs, key=lambda r: r["seed"])],
        "trace": median(mx(r, "trace") for r in rs),
        "flux": median(mx(r, "flux") for r in rs),
        "edef": median(mx(r, "energy_defect") for r in rs),
        "u": sum(r["u_pass"] for r in rs),
        "c": sum(r["c_pass"] for r in rs),
        "wall": median(r["wall_seconds"] for r in rs),
    }


def table() -> dict:
    return {cell: {m: stats(runs(tag, cell)) for m, tag in METHODS.items()} for cell in CELLS}


def verdicts(t: dict) -> list[str]:
    lines = []

    def get(cell, m):
        s = t[cell][m]
        return s if s and s["n"] == 3 else None

    # layer (amendment 2b): both primary cells, >=3x below frozen vanilla, below all three baselines, cell U-pass
    for meth in ("layer", "layer+decay"):
        ok_all = True
        for cell in ("m0_lin", "m1_lin"):
            s, v = get(cell, meth), get(cell, "vanilla")
            base = [get(cell, b) for b in ("w_ic=10", "hardic", "t_power=2")]
            if s is None or v is None or any(b is None for b in base):
                lines.append(f"{meth} @ {cell}: incomplete")
                ok_all = False
                continue
            ratio = v["vol"] / s["vol"]
            below = all(s["vol"] < b["vol"] for b in base)
            upass = s["u"] >= 2
            ok = ratio >= 3 and below and upass
            ok_all &= ok
            lines.append(f"{meth} @ {cell}: vanilla/method = {ratio:.2f} (need >=3), below all baselines = {below}, U {s['u']}/3 -> {'meets' if ok else 'fails'}")
        lines.append(f"  => {meth} vs amendment-2b layer criterion (binding only for 'layer'): {'MET' if ok_all else 'NOT MET'}")
    # decay (amendment 2): m2_eig1 and m2_const, >=3x below frozen vanilla
    ok_all = True
    for cell in ("m2_eig1", "m2_const"):
        s, v = get(cell, "decay"), get(cell, "vanilla")
        if s is None or v is None:
            lines.append(f"decay @ {cell}: incomplete")
            ok_all = False
            continue
        ratio = v["vol"] / s["vol"]
        ok_all &= ratio >= 3
        lines.append(f"decay @ {cell}: vanilla/decay = {ratio:.2f} (need >=3)")
    lines.append(f"  => decay criterion: {'MET' if ok_all else 'NOT MET'}")
    return lines


def main() -> None:
    t = table()
    for cell in CELLS:
        print(f"\n### {cell}@P0\n")
        print("| method | runs | max-vol median | per seed (0,1,2) | trace median | flux median | E-def median | U | C | wall median (s) |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for m, s in t[cell].items():
            if s is None:
                continue
            seeds = ", ".join(f"{x:.1e}" for x in s["vols"])
            print(f"| {m} | {s['n']} | {s['vol']:.2e} | {seeds} | {s['trace']:.2e} | {s['flux']:.2e} | {s['edef']:.1e} | {s['u']}/{s['n']} | {s['c']}/{s['n']} | {s['wall']:.0f} |")
    print("\n### pre-registered verdicts\n")
    for line in verdicts(t):
        print(line)


if __name__ == "__main__":
    main()

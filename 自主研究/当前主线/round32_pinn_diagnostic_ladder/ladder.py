"""R32 ladder: cell definitions, pass criteria, single-run driver, parallel runner and report.

    python ladder.py run --rung R0 --seeds 0,1,2 --workers 8
    python ladder.py run --cell-id m1_lin_c0.3_d0.1_k0.3 --seeds 0,1,2 --set width=128 --tag probe_w128
    python ladder.py report --rung R0
Every run writes one JSON (and the network weights) under runs/<tag>/ and is skipped if it exists.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import platform
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
P0 = {"c": 0.3, "d": 0.1, "kappa": 0.3}
AXIS_C = (0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0)
AXIS_D = (0.01, 0.03, 0.1, 0.3, 1.0)
AXIS_K = (0.0, 0.1, 0.3, 1.0)
ALL = ("m0_const", "m0_lin", "m1_const", "m1_lin", "m2_const")
ANGULAR = ("m1_const", "m1_lin", "m2_const")
COMPATIBLE = {f"m{m}_{tag}": (m, modes) for m in (0, 1, 2) for tag, modes in (("eig1", (1,)), ("eig13", (1, 3)))}

U_LIMITS = {"vol": 1e-2, "trace": 1e-2, "flux": 1e-1}
C_LIMITS = {"vol": 1e-3, "trace": 1e-3, "flux": 1e-2, "energy_defect": 1e-4, "mass_defect": 1e-4}


def cell(resp: str, c: float, d: float, kappa: float) -> dict:
    return {"id": f"{resp}_c{c:g}_d{d:g}_k{kappa:g}", "response": resp, "c": c, "d": d, "kappa": kappa}


def rung_cells(rung: str) -> list[dict]:
    c0, d0, k0 = P0["c"], P0["d"], P0["kappa"]
    if rung == "R0":
        return [cell(r, c0, d0, k0) for r in ("m0_lin", "m0_const")]
    if rung == "R1":
        return [cell(r, c0, d0, k0) for r in ANGULAR]
    if rung == "R2":
        return [cell(r, c, d0, k0) for c in AXIS_C for r in ALL]
    if rung == "R3":
        return [cell(r, c0, d, k0) for d in AXIS_D for r in ANGULAR]
    if rung == "R4":
        return [cell(r, c0, d0, k) for k in AXIS_K for r in ALL if not (k == 0.0 and r == "m0_const")]
    if rung == "RC":
        return [cell(r, c0, d0, k0) for r in COMPATIBLE]
    if rung == "R5":
        return [cell(r, c, d, k) for c in (0.01, 10.0) for d in (0.01, 1.0) for k in (0.1, 1.0) for r in ("m1_lin", "m2_const")]
    raise ValueError(f"unknown rung {rung}")


def find_cell(cell_id: str) -> dict:
    for rung in ("R0", "R1", "RC", "R2", "R3", "R4", "R5"):
        for c in rung_cells(rung):
            if c["id"] == cell_id:
                return c
    raise KeyError(cell_id)


def response_poly(cl: dict) -> tuple[int, np.ndarray]:
    from ref_wentzell import RESPONSES, compatible_poly

    if cl["response"] in COMPATIBLE:
        m, modes = COMPATIBLE[cl["response"]]
        return m, compatible_poly(m, cl["c"], cl["d"], cl["kappa"], modes)
    return RESPONSES[cl["response"]]


def u_pass(metrics: dict) -> bool:
    return all(max(metrics[k]) <= lim for k, lim in U_LIMITS.items())


def c_pass(metrics: dict) -> bool:
    return all(max(metrics[k]) <= lim for k, lim in C_LIMITS.items())


def out_path(tag: str, cell_id: str, seed: int) -> Path:
    return HERE / "runs" / tag / f"{cell_id}_s{seed}.json"


def run_one(job: tuple) -> str:
    import torch

    from metrics_wentzell import evaluate
    from pinn_vanilla import Config, Problem, net_fn, train
    from ref_wentzell import Mode

    torch.set_num_threads(1)
    cl, seed, overrides, tag, variant_name = job
    path = out_path(tag, cl["id"], seed)
    if path.exists():
        return f"skip {path.name}"
    m, poly = response_poly(cl)
    prob = Problem(cl["response"], m, cl["c"], cl["d"], cl["kappa"], tuple(float(x) for x in poly))
    cfg = replace(Config(), seed=seed, **overrides)
    variant_info = {"name": variant_name}
    if variant_name == "vanilla":
        res = train(prob, cfg)
    else:
        from pinn_improved import Variant, corner_mismatch, train_variant

        variant = Variant(layer="layer" in variant_name, decay="decay" in variant_name, hard_ic="hardic" in variant_name)
        lam = float(Mode(m, cl["c"], cl["d"], cl["kappa"], np.array([1.0])).lam[0])
        res = train_variant(prob, cfg, variant, lam)
        variant_info.update({"lam": lam, "delta": corner_mismatch(prob), "tau": variant.tau})
    ref = Mode(m, cl["c"], cl["d"], cl["kappa"], np.asarray(poly))
    t0 = time.perf_counter()
    metrics = evaluate(net_fn(res.net), ref)
    h = res.history
    record = {
        "cell": cl,
        "seed": seed,
        "config": asdict(cfg),
        "tag": tag,
        "variant": variant_info,
        "wall_seconds": res.wall_seconds,
        "adam_seconds": res.adam_seconds,
        "eval_seconds": time.perf_counter() - t0,
        "final_adam_loss": h["loss"][-1] if h["loss"] else None,
        "final_lbfgs_loss": h["lbfgs_loss"][-1] if h["lbfgs_loss"] else None,
        "metrics": metrics,
        "u_pass": u_pass(metrics),
        "c_pass": c_pass(metrics),
        "history": {k: (v[::10] if k in ("loss", "pde", "bc", "ic") else v) for k, v in h.items()},
        "env": {"python": platform.python_version(), "torch": torch.__version__, "numpy": np.__version__},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(res.net.state_dict(), path.with_suffix(".pt"))
    path.write_text(json.dumps(record))
    return f"done {path.name} wall={res.wall_seconds:.0f}s U={record['u_pass']} C={record['c_pass']}"


def parse_overrides(items: list[str]) -> dict:
    out = {}
    for it in items or []:
        key, val = it.split("=")
        out[key] = float(val) if "." in val or "e" in val.lower() else int(val)
    return out


def cmd_run(args) -> None:
    cells = rung_cells(args.rung) if args.rung else [find_cell(args.cell_id)]
    seeds = [int(x) for x in args.seeds.split(",")]
    overrides = parse_overrides(args.set)
    variant = args.variant
    tag = args.tag or ("cells" if variant == "vanilla" else f"var_{variant}")
    jobs = [(cl, sd, overrides, tag, variant) for cl in cells for sd in seeds]
    print(f"{len(jobs)} jobs, tag={tag}, overrides={overrides}", flush=True)
    ctx = mp.get_context("spawn")
    with ctx.Pool(args.workers) as pool:
        for msg in pool.imap_unordered(run_one, jobs):
            print(msg, flush=True)


def load_runs(tag: str, cells: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for cl in cells:
        runs = []
        for p in sorted((HERE / "runs" / tag).glob(f"{cl['id']}_s*.json")):
            if p.stem.rsplit("_s", 1)[1].isdigit():
                runs.append(json.loads(p.read_text()))
        out[cl["id"]] = runs
    return out


def cmd_report(args) -> None:
    cells = rung_cells(args.rung) if args.rung else [find_cell(args.cell_id)]
    runs = load_runs(args.tag or "cells", cells)
    print(f"{'cell':<34}{'seed':>4}{'vol':>10}{'trace':>10}{'flux':>10}{'E-def':>10}{'M-def':>10}{'U':>3}{'C':>3}{'wall':>7}")
    verdicts = {}
    for cl in cells:
        rs = runs[cl["id"]]
        for r in rs:
            mt = r["metrics"]
            print(f"{cl['id']:<34}{r['seed']:>4}{max(mt['vol']):>10.2e}{max(mt['trace']):>10.2e}{max(mt['flux']):>10.2e}{max(mt['energy_defect']):>10.2e}{max(mt['mass_defect']):>10.2e}{int(r['u_pass']):>3}{int(r['c_pass']):>3}{r['wall_seconds']:>7.0f}")
        n_u = sum(r["u_pass"] for r in rs)
        n_c = sum(r["c_pass"] for r in rs)
        verdicts[cl["id"]] = (len(rs), n_u, n_c)
    print("\ncell verdicts (runs, U-pass runs, C-pass runs; cell U-pass needs >=2 of 3):")
    for cid, (n, nu, nc) in verdicts.items():
        status = "U-PASS" if nu >= 2 else ("incomplete" if n < 3 else "U-FAIL")
        print(f"  {cid:<34} runs={n} U={nu} C={nc}  {status}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "report"):
        sp = sub.add_parser(name)
        grp = sp.add_mutually_exclusive_group(required=True)
        grp.add_argument("--rung")
        grp.add_argument("--cell-id")
        sp.add_argument("--tag")
        if name == "run":
            sp.add_argument("--seeds", default="0,1,2")
            sp.add_argument("--workers", type=int, default=4)
            sp.add_argument("--set", action="append")
            sp.add_argument("--variant", default="vanilla", choices=["vanilla", "layer", "decay", "layer+decay", "hardic"])
    args = ap.parse_args(argv)
    {"run": cmd_run, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main(sys.argv[1:])

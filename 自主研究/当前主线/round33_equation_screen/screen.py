"""R33 screening driver: run (equation, method, seed) jobs in parallel and print the screening table.

    python screen.py run [--eqs E1_heat,E2_allen_cahn] [--methods ...] [--seeds 0,1] [--workers 4] [--set adam_steps=200]
    python screen.py report
Each run writes runs/<tag>/<eq>/<method>_s<seed>.json (tag defaults to "screen"); existing results are skipped.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import platform
from dataclasses import asdict, replace
from pathlib import Path
from statistics import median

import numpy as np

HERE = Path(__file__).resolve().parent


def out_path(tag, eq, method, seed) -> Path:
    return HERE / "runs" / tag / eq / f"{method.replace('+', '_')}_s{seed}.json"


def evaluate(model, ref) -> dict:
    import torch

    from problems import OUT_TIMES

    xg, wg = np.polynomial.legendre.leggauss(200)
    xg, wg = 0.5 * (xg + 1.0), 0.5 * wg
    vol, trace = [], []
    for t in OUT_TIMES:
        with torch.no_grad():
            u = model(torch.tensor(xg), torch.full((len(xg),), t)).numpy()
            u1 = float(model(torch.tensor([1.0]), torch.tensor([t]))[0])
        ur = ref(xg, t)
        vol.append(float(np.sqrt(np.sum(wg * (u - ur) ** 2) / np.sum(wg * ur**2))))
        r1 = float(ref(np.array([1.0]), t)[0])
        trace.append(abs(u1 - r1) / max(abs(r1), 1e-12))
    out = {"times": list(OUT_TIMES), "vol": vol, "trace": trace}
    if hasattr(model, "surface"):  # E4: surface variable v(t), absolute error
        with torch.no_grad():
            out["surface_abs"] = [abs(float(model.surface(torch.tensor([t]))[0]) - ref.v(t)) for t in OUT_TIMES]
    return out


def run_one(job) -> str:
    import torch

    from pinn1d import Config, train
    from problems import get_problem, get_reference

    torch.set_num_threads(1)
    eq, method, seed, overrides, tag = job
    path = out_path(tag, eq, method, seed)
    if path.exists():
        return f"skip {path.relative_to(HERE)}"
    p = get_problem(eq)
    cfg = replace(Config(), seed=seed, **overrides)
    # R33_CKPT_DIR: put checkpoints outside the repository (ignored files in the checkout may not survive a container restart)
    ckpt_dir = os.environ.get("R33_CKPT_DIR")
    ckpt = str(Path(ckpt_dir) / f"{tag}__{eq}__{path.stem}.ckpt") if ckpt_dir else str(path.with_suffix('.ckpt'))
    if ckpt_dir:
        Path(ckpt_dir).mkdir(parents=True, exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    model, hist = train(p, method, cfg, ckpt=ckpt)
    metrics = evaluate(model, get_reference(p, 64))
    rec = {"eq": eq, "method": method, "seed": seed, "tag": tag, "config": asdict(cfg), "delta": p.mismatch(),
           "metrics": metrics, "max_vol": max(metrics["vol"]), "max_trace": max(metrics["trace"]),
           "wall_seconds": hist["wall_seconds"], "adam_seconds": hist["adam_seconds"],
           "final_adam_loss": hist["loss"][-1], "final_lbfgs_loss": hist["lbfgs_loss"][-1], "history": hist,
           "env": {"python": platform.python_version(), "torch": torch.__version__, "numpy": np.__version__}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec))
    torch.save(model.base.state_dict(), path.with_suffix(".pt"))
    Path(ckpt).unlink(missing_ok=True)
    return f"done {path.relative_to(HERE)} vol={rec['max_vol']:.2e} wall={rec['wall_seconds']:.0f}s"


def parse_overrides(items):
    out = {}
    for it in items or []:
        k, v = it.split("=")
        for cast in (int, float, str):
            try:
                out[k] = cast(v)
                break
            except ValueError:
                pass
    return out


def cmd_run(a):
    from pinn1d import METHODS
    from problems import PROBLEMS

    eqs = a.eqs.split(",") if a.eqs else list(PROBLEMS)
    methods = a.methods.split(",") if a.methods else list(METHODS)
    seeds = [int(s) for s in a.seeds.split(",")]
    ov = parse_overrides(a.set)
    jobs = [(e, m, s, ov, a.tag) for s in seeds for e in eqs for m in methods]
    print(f"{len(jobs)} jobs tag={a.tag} overrides={ov}", flush=True)
    with mp.get_context("spawn").Pool(a.workers) as pool:
        for msg in pool.imap_unordered(run_one, jobs):
            print(msg, flush=True)


def cmd_report(a):
    from pinn1d import METHODS
    from problems import PROBLEMS

    root = HERE / "runs" / a.tag
    from problems import BULK_SURFACE

    for eq, prob in {**PROBLEMS, **BULK_SURFACE}.items():
        if not (root / eq).exists():
            continue
        print(f"\n### {eq}  (delta = {prob.mismatch():+.3f})\n")
        print("| method | runs | max-vol per seed | median | max-trace median | wall median (s) |")
        print("|---|---|---|---|---|---|")
        med = {}
        for m in METHODS:
            rs = [json.loads(p.read_text()) for p in sorted((root / eq).glob(f"{m.replace('+', '_')}_s*.json"))]
            if not rs:
                continue
            v = [r["max_vol"] for r in rs]
            med[m] = median(v)
            print(f"| {m} | {len(rs)} | {', '.join(f'{x:.1e}' for x in v)} | {med[m]:.2e} | {median(r['max_trace'] for r in rs):.2e} | {median(r['wall_seconds'] for r in rs):.0f} |")
        if all(k in med for k in METHODS):
            best_ours = min(med["layer"], med["hardic+layer"])
            best_base = min(med["hardic"], med["rba"])
            c2 = med["vanilla"] > 1e-2
            c3 = best_base / best_ours >= 3.0
            print(f"\ncriterion 2 (vanilla > 1e-2): {c2}; criterion 3 (best of ours {best_ours:.2e} vs best of hardic/rba {best_base:.2e}, ratio {best_base / best_ours:.2f} >= 3): {c3}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--eqs")
    r.add_argument("--methods")
    r.add_argument("--seeds", default="0,1")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--set", action="append")
    r.add_argument("--tag", default="screen")
    rp = sub.add_parser("report")
    rp.add_argument("--tag", default="screen")
    a = ap.parse_args()
    {"run": cmd_run, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()

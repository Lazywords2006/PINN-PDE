#!/bin/bash
# Protocol section 8 probes on the first failing cell (m0_lin at P0), one change at a time, 3 seeds.
# budget120: Adam 4500 + L-BFGS 200, about 120 s single-thread uncontended on this host (22 ms/step, 19 it/s).
cd "$(dirname "$0")" || exit 1
PY=${PY:-python3}   # local Mac: PY=/Users/lazywords/Paper/PINN-PDE/.venv-r31/bin/python
CELL=m0_lin_c0.3_d0.1_k0.3
JOBS=$(mktemp)
for seed in 0 1 2; do
  cat >> "$JOBS" <<EOF
probe_adam60k adam_steps=60000 $seed
probe_w128 width=128 $seed
probe_nf16k nf=16384 $seed
probe_lr3e-3 lr0=3e-3 $seed
probe_w32 width=32 $seed
probe_adam5k adam_steps=5000 $seed
probe_nolbfgs lbfgs_iters=0 $seed
probe_budget120 adam_steps=4500,lbfgs_iters=200 $seed
probe_wbc0.1 w_bc=0.1 $seed
probe_wbc10 w_bc=10.0 $seed
probe_wic10 w_ic=10.0 $seed
probe_wic100 w_ic=100.0 $seed
EOF
done
run_job() {
  tag=$1; sets=$2; seed=$3
  args=""
  IFS=',' read -ra kv <<< "$sets"
  for x in "${kv[@]}"; do args="$args --set $x"; done
  $PY ladder.py run --cell-id $CELL --seeds $seed --workers 1 --tag $tag $args 2>&1 | tail -1
}
export -f run_job
export PY CELL
xargs -P ${P:-9} -L 1 bash -c 'run_job "$0" "$1" "$2"' < "$JOBS" > runs/probes.log 2>&1
for tag in probe_adam60k probe_w128 probe_nf16k probe_lr3e-3 probe_w32 probe_adam5k probe_nolbfgs probe_budget120 probe_wbc0.1 probe_wbc10 probe_wic10 probe_wic100; do
  echo "=== $tag"; $PY ladder.py report --cell-id $CELL --tag $tag | tail -2
done > runs/probes_report.txt 2>&1
grep -h "Traceback\|Error" runs/probes.log
echo PROBES_DONE

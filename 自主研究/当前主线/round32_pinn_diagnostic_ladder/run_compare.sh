#!/bin/bash
# R32 amendments 2 and 2b: layer lifting / decay scaling against vanilla and three stronger baselines.
# Job line: cell variant overrides tag seed   ("-" = none / default tag)
cd "$(dirname "$0")" || exit 1
PY=${PY:-python3}   # local Mac: PY=/Users/lazywords/Paper/PINN-PDE/.venv-r31/bin/python
P0=c0.3_d0.1_k0.3
JOBS=$(mktemp)
for seed in 0 1 2; do
  for cell in m0_lin m1_lin m2_const; do
    for v in layer decay layer+decay; do echo "$cell $v - - $seed" >> "$JOBS"; done
  done
  echo "m2_eig1 decay - - $seed" >> "$JOBS"
  echo "m1_lin vanilla w_ic=10.0 probe_wic10 $seed" >> "$JOBS"
  echo "m2_const vanilla w_ic=10.0 probe_wic10 $seed" >> "$JOBS"
  for cell in m0_lin m1_lin; do
    echo "$cell hardic - - $seed" >> "$JOBS"
    echo "$cell vanilla t_power=2.0 base_tpow2 $seed" >> "$JOBS"
  done
done
run_job() {
  cell=$1; v=$2; sets=$3; tag=$4; seed=$5
  args="--cell-id ${cell}_$P0 --seeds $seed --workers 1 --variant $v"
  [ "$sets" != "-" ] && args="$args --set $sets"
  [ "$tag" != "-" ] && args="$args --tag $tag"
  $PY ladder.py run $args 2>&1 | tail -1
}
export -f run_job
export PY P0
xargs -P ${P:-9} -L 1 bash -c 'run_job "$0" "$1" "$2" "$3" "$4"' < "$JOBS" > runs/compare.log 2>&1
grep -h "Traceback\|Error" runs/compare.log
echo COMPARE_DONE

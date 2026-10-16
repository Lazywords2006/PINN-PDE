#!/bin/bash
# Stage 1 of the R32 ladder: R0 (remaining seeds), R1 and RC with the frozen vanilla configuration.
cd "$(dirname "$0")" || exit 1
PY=${PY:-python3}   # local Mac: PY=/Users/lazywords/Paper/PINN-PDE/.venv-r31/bin/python
$PY ladder.py run --rung R0 --seeds 1,2 --workers 2 > runs/stage1_R0.log 2>&1 &
$PY ladder.py run --rung R1 --seeds 0,1,2 --workers 3 > runs/stage1_R1.log 2>&1 &
$PY ladder.py run --rung RC --seeds 0,1,2 --workers 3 > runs/stage1_RC.log 2>&1 &
wait
for r in R0 R1 RC; do $PY ladder.py report --rung $r > runs/stage1_report_$r.txt 2>&1; done
grep -h "Traceback\|Error" runs/stage1_*.log runs/R0_seed0.log
echo STAGE1_DONE

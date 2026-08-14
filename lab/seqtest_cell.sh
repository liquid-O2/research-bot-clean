#!/usr/bin/env bash
# ITERATION 2, ONE CHANGE: rank in the SCHEDULE'S OWN SELECTION UNIT.
# The deployable policy is top-1 per (asset, PHASE) CELL, so the group the
# ranker orders must be that cell.  Everything else is held fixed.
set -u
P=/usr/bin/python3; E=/workspace/engine/port_m2/seqtest
run(){ echo "### $*" >&2; "$@" || echo "### FAILED: $*" >&2; }
run $P $E/st_lmart.py --run --unit cell --tag LMART_CELL
run $P $E/st_lmart.py --run --unit day  --tag LMART_DAY
run $P $E/st_rank.py  --run --trunk NONE --mode ctx   --unit cell --tag RANK_CELL_CTX
run $P $E/st_rank.py  --run --trunk PRE_V_shared_MULTI --mode fused --unit cell --tag RANK_CELL_FUSED
run $P $E/st_sched.py --tags LMART_CELL,LMART_DAY,RANK_CELL_CTX,RANK_CELL_FUSED
for t in LMART_CELL RANK_CELL_CTX RANK_CELL_FUSED; do
  run $P $E/st_deficit.py --tag "$t" --name "CELL1_$t" --use primary
done
run $P $E/st_report.py
echo "iteration 2 complete"

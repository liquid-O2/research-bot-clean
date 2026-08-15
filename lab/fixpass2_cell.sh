#!/usr/bin/env bash
# FIXPASS2, RE-POINTED (coordinator correction 2026-08-15): the toggles applied
# ON TOP OF THE ACTUAL CHAMPION — cell-grouped LambdaMART, full prior history.
set -eu
P=/usr/bin/python3
E=/workspace/engine/port_m2/seqtest
# the champion reproduced inside this pass's own harness (identity check)
$P $E/st_rank2.py --lmart --group cell --from-era PRE_E1 --tag LMART2_CELL_ALLDATA
# F6/B1 and F5(a) on top of it, and both
$P $E/st_rank2.py --lmart --group cell --from-era PRE_E1 --daymem --tag LMART2_CELL_ALLDATA_MEM
$P $E/st_rank2.py --lmart --group cell --from-era PRE_E1 --creator --tag LMART2_CELL_ALLDATA_CRE26
$P $E/st_rank2.py --lmart --group cell --from-era PRE_E1 --daymem --creator --tag LMART2_CELL_ALLDATA_MEM_CRE26
# the two mis-specified grouping controls on identical data (F3's own ablation)
$P $E/st_rank2.py --lmart --group day   --from-era PRE_E1 --tag LMART2_DAY_ALLDATA
$P $E/st_rank2.py --lmart --group class --from-era PRE_E1 --tag LMART2_CLASS_ALLDATA
echo "fixpass2 cell/alldata grid complete"

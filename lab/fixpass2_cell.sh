#!/usr/bin/env bash
# FIXPASS2, RE-POINTED (coordinator correction 2026-08-15): the toggles are now
# applied ON TOP OF THE ACTUAL CHAMPION — cell-grouped LambdaMART with the full
# prior training history — instead of the retired session/3 GBT.
#   F5(a) the 26 creator columns   F6/B1 the causal day memory   both
# plus the GBT family re-run on the same full-history training block so the
# F5 statement is made on matched data.
set -eu
P=/usr/bin/python3
E=/workspace/engine/port_m2/seqtest
$P $E/st_rank2.py --lmart --group cell --from-era PRE_E1 --daymem \
   --tag LMART2_CELL_ALLDATA_MEM
$P $E/st_rank2.py --lmart --group cell --from-era PRE_E1 --creator \
   --tag LMART2_CELL_ALLDATA_CRE26
$P $E/st_rank2.py --lmart --group cell --from-era PRE_E1 --daymem --creator \
   --tag LMART2_CELL_ALLDATA_MEM_CRE26
$P $E/st_champ.py --one --from-era PRE_E1
$P $E/st_champ.py --one --from-era PRE_E1 --creator
$P $E/st_champ.py --one --from-era PRE_E1 --label maecap
$P $E/st_champ.py --one --from-era PRE_E1 --creator --label maecap
echo "fixpass2 cell/alldata grid complete"

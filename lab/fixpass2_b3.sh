#!/usr/bin/env bash
set -eu
P=/usr/bin/python3
E=/workspace/engine/port_m2/seqtest
$P $E/st_rank2.py --lmart --group cell --from-era PRE_E1 --hardneg 1 --tag LMART2_CELL_ALLDATA_HN1
$P $E/st_rank2.py --lmart --group cell --from-era PRE_E1 --hardneg 3 --tag LMART2_CELL_ALLDATA_HN3
echo "b3 on the champion complete"

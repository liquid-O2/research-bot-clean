#!/usr/bin/env bash
# FIXPASS2 F3(b) + F6: the LambdaMART grid — deploy-matched DAY groups against
# the first pass's (asset,day,class) groups, with the B1 day-memory and the
# 26 creator columns as toggles.  CPU only.
set -eu
P=/usr/bin/python3
E=/workspace/engine/port_m2/seqtest
$P $E/st_rank2.py --lmart --group day
$P $E/st_rank2.py --lmart --group class
$P $E/st_rank2.py --lmart --group day --daymem
$P $E/st_rank2.py --lmart --group day --creator
$P $E/st_rank2.py --lmart --group day --daymem --creator
$P $E/st_rank2.py --lmart --group class --daymem --creator
echo "lmart2 grid complete"

#!/usr/bin/env bash
# FIXPASS2 — the deficit-ledger decomposition of the pass's leading arms.
set -eu
P=/usr/bin/python3
E=/workspace/engine/port_m2/seqtest
$P $E/st_deficit.py --tag GBT_CRE26      --name FIX2_GBT_CRE26_PRIMARY --use primary
$P $E/st_deficit.py --tag GBT_MAECAP     --name FIX2_GBT_MAECAP_COMPOSED --use composed
$P $E/st_deficit.py --tag LMART2_DAY_MEM_CRE26 --name FIX2_LMART_DAY --use primary
echo "deficit decompositions complete"

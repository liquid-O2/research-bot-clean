#!/usr/bin/env bash
# FIXPASS2 — ledger decompositions of the pass's leading arms, on the CORRECT
# cell/1 policy (st_deficit.POLICY was corrected to cell/1 by the seqtest lane).
set -eu
P=/usr/bin/python3
E=/workspace/engine/port_m2/seqtest
$P $E/st_deficit.py --tag FT2_TOP4_ATTN                 --name CELL1_FIX2_FT2_TOP4_ATTN --use primary
$P $E/st_deficit.py --tag FT2_RANDOM_TOP4_ATTN          --name CELL1_FIX2_FT2_RANDOM    --use primary
$P $E/st_deficit.py --tag LMART2_CELL_ALLDATA_MEM_CRE26 --name CELL1_FIX2_LMART_MEM_CRE26 --use primary
$P $E/st_deficit.py --tag PROBE2_PRE_V2_shared_MULTI_CPC0_FUSED --name CELL1_FIX2_PROBE2_V2 --use primary
echo "fixpass2 deficit decompositions complete"

#!/usr/bin/env bash
set -u
P=/usr/bin/python3; E=/workspace/engine/port_m2/seqtest
run(){ echo "### $*" >&2; "$@" || echo "### FAILED: $*" >&2; }
for t in REF_FORESIGHT GBT_M3FEATURES PROBE_PRE_V_shared_MULTI_CTX PROBE_PRE_V_shared_MULTI_FUSED RANK_CTXONLY LADDER_trf_1M_L256; do
  run $P $E/st_deficit.py --tag "$t" --name "CELL1_$t" --use primary
done

#!/usr/bin/env bash
# lab/seqtest_final.sh — the full evaluation of this pass, run once, end to end.
# ITERATION LAW: no fixes mid-evaluation; everything below is measurement.
set -u
P=/usr/bin/python3
E=/workspace/engine/port_m2/seqtest
run() { echo "### $*" >&2; "$@" || echo "### FAILED: $*" >&2; }

# ---- frozen-trunk representations -----------------------------------------
for t in PRE_V_shared_MULTI PRE_V_shared_NEXT RANDOM PRE_V_si_MULTI; do
  run $P $E/st_pretrain.py --embed --trunk "$t"
done

# ---- AMENDMENT 2 fusion ablation on the chosen trunk ----------------------
run $P $E/st_pretrain.py --probe --trunk PRE_V_shared_MULTI --mode seq,ctx,fused

# ---- AMENDMENT 3: the timescale ablation, next-only vs +multi-horizon -----
run $P $E/st_pretrain.py --probe --trunk PRE_V_shared_NEXT --mode fused \
    --tag PROBE_NEXTONLY_FUSED
run $P $E/st_pretrain.py --probe --trunk RANDOM --mode fused \
    --tag PROBE_RANDOM_FUSED

# ---- AMENDMENT 1: the shared-vs-SI-only decision, taken ON SI -------------
run $P $E/st_pretrain.py --probe --trunk PRE_V_shared_MULTI --mode fused \
    --assets SI --tag PROBE_SHARED_FUSED_SI
run $P $E/st_pretrain.py --probe --trunk PRE_V_si_MULTI --mode fused \
    --assets SI --tag PROBE_SIONLY_FUSED_SI
run $P $E/st_pretrain.py --probe --trunk PRE_V_shared_MULTI --mode fused \
    --assets HG --tag PROBE_SHARED_FUSED_HG
run $P $E/st_pretrain.py --probe --trunk PRE_V_shared_MULTI --mode fused \
    --assets NKD --tag PROBE_SHARED_FUSED_NKD

# ---- THE REDIRECT: the listwise member ranker -----------------------------
run $P $E/st_rank.py --run --trunk NONE               --mode ctx   --tag RANK_CTXONLY
run $P $E/st_rank.py --run --trunk PRE_V_shared_MULTI --mode seq   --tag RANK_SEQONLY
run $P $E/st_rank.py --run --trunk PRE_V_shared_MULTI --mode fused --tag RANK_FUSED_MULTI
run $P $E/st_rank.py --run --trunk PRE_V_shared_NEXT  --mode fused --tag RANK_FUSED_NEXT

# ---- the 'learned properly' certificate ----------------------------------
run $P $E/st_probes.py --all --trunk PRE_V_shared_MULTI

# ---- the ledger decomposition of every score, one command each -----------
for t in RANK_CTXONLY RANK_SEQONLY RANK_FUSED_MULTI RANK_FUSED_NEXT; do
  run $P $E/st_deficit.py --tag "$t" --name "$t" --use primary
done
run $P $E/st_deficit.py --tag PROBE_PRE_V_shared_MULTI_FUSED \
    --name PROBE_FUSED_MULTI

# ---- the frontier lane's plane + the TSVs --------------------------------
run $P $E/st_run.py --stage export --tag RANK_FUSED_MULTI
run $P $E/st_report.py
echo "seqtest final evaluation complete"

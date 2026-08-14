#!/usr/bin/env bash
# lab/seqtest_rank.sh — the member-ranking stage (program redirect 2026-08-16).
#
# GROUPS = (asset, day, class).  Listwise loss.  The number to move is the
# deficit ledger's SEL_WRONG_MEMBER.  EXITS ARE PARKED: the contract stays
# phase-close + the $900 wall throughout.
set -eu
P=/usr/bin/python3
E=/workspace/engine/port_m2/seqtest

# the three ablation rows of AMENDMENT 2, now as RANKERS
$P $E/st_rank.py --run --trunk NONE          --mode ctx   --tag RANK_CTXONLY
$P $E/st_rank.py --run --trunk PRE_A_shared  --mode seq   --tag RANK_SEQONLY
$P $E/st_rank.py --run --trunk PRE_A_shared  --mode fused --tag RANK_FUSED

# every score this lane produced, through the standing deficit ledger
for t in RANK_CTXONLY RANK_SEQONLY RANK_FUSED; do
  $P $E/st_deficit.py --tag "$t" --name "$t" --use primary
done

# the frontier lane's plane gets the fused ranker's column, keyed by cid
$P $E/st_run.py --stage export --tag RANK_FUSED
$P $E/st_report.py
echo "seqtest rank stage complete"

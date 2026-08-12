#!/bin/bash
# stream_eras_v4.sh — SHEET-V4 REGENERATION of the whole 7-era corpus (D-042).
#
# Same fourteen blocks, the SAME rosters (copied from the v3 tree by
# sheet4.roster_path, never rebuilt — "rosters unchanged, richer sheets"), the
# same per-block discipline stream_eras.sh and stream_eras_v2.sh used:
#
#     roster -> run1 (14 shards) -> run2 (14 shards) -> sha both -> audit -> receipt
#
# and the same READ-ORDER LAW for the dual last-20 blocks: read a study block's
# sessions BEFORE its last 20, then the BLIND sheets of those 20 with calls
# committed in writing, and only then the same 20 inside the study variant.
# The blind index is named INDEX_SEALED_DO_NOT_READ_UNTIL_CALLS_COMMITTED.tsv by
# the generator for that reason.
#
# The v3 tree at sheets/ is NOT touched: v4 writes sheets_v4/ beside it.
set -u
V3=/workspace/artifacts/cache/campaign/diagnostics/d020_v3
cd "$V3" || exit 1
RECEIPT="$V3/sheets_v4/STREAM_RECEIPT.tsv"
mkdir -p "$V3/sheets_v4"
python3 sheet4.py manifest || exit 1
[ -f "$RECEIPT" ] || echo -e "block\trange\tsheets\tsha_run1\tsha_run2\tidentical\tcheck" > "$RECEIPT"

run_block () {
  local block=$1 low=$2 high=$3
  grep -q "^${block}	" "$RECEIPT" && { echo "=== $block already receipted, skipping"; return 0; }
  echo "=== $block $low..$high"
  python3 sheet4.py roster --block "$block" || return 1
  for run in run1 run2; do
    for i in $(seq 0 13); do
      python3 sheet4.py render --run $run --block "$block" --shard $i/14 \
        > "_cache/v4_${run}_${block}_$i.log" 2>&1 &
    done
    wait
    python3 sheet4.py index --run $run --block "$block"
  done
  local n s1 s2 same check
  n=$(ls "$V3/sheets_v4/run1/$block" | wc -l)
  s1=$(python3 sheet4.py sha --run run1 | cut -f2)
  s2=$(python3 sheet4.py sha --run run2 | cut -f2)
  same=$([ "$s1" = "$s2" ] && echo yes || echo NO)
  check=$(python3 sheets4_check.py run1 "$block" | tail -1)
  echo -e "$block\t$low..$high\t$n\t$s1\t$s2\t$same\t$check" >> "$RECEIPT"
  echo "--- $block done: $n sheets, identical=$same, $check"
}

run_block study_e1  125 179
run_block study_e1b 180 229
run_block study_e2  230 330
run_block study_e3  331 397
run_block study_e3b 398 427
run_block blind_e3  428 447
run_block study_e4  448 497
run_block blind_e4  478 497
run_block study_e5  498 623
run_block blind_e5  604 623
run_block study_e6  624 735
run_block blind_e6  716 735
run_block study_e7  736 917
run_block blind_e7  898 917
echo "SHEET-V4 STREAM COMPLETE"

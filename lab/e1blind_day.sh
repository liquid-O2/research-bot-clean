#!/usr/bin/env bash
# e1blind_day.sh N DATE8 [NEXT_DATE8] — prepare one E1 BLIND day for the reader.
#   builds the triage index + the as-of driver, runs the reader policy, prints
#   the per-cell as-of brief and the take table, and (optionally) launches the
#   NEXT day's on-demand render in the background so the stepper never waits.
# Never opens an S14 appendix; triage_index.py refuses to.
#
# THE D-001 FIX PASS changed three things (M2_CONSOLIDATED_REVIEW R09/R28/R29):
#
#   R09  THE STEPPER WAS 6x COARSER THAN THE STUDY ROUNDS IT INHERITED.
#        `--drive-step 1800` gave 47 cuts per blind day against 275-277 at 300s
#        in E1D6/E1D8.  A prefix emits every row with `sec <= cut`, so each of
#        those 47 files carried up to 1,799 seconds of LATER rows whose `mid` is
#        the post-decision price path — the D14 SCAN-EXPOSED leak CC-M2-12.1
#        made blocking BEFORE any blind round, made six times worse in the round
#        the teacher gate scores.  The drive is now `--drive-per-row`: exactly
#        one prefix per DISTINCT DECISION SECOND, the `--next` semantics
#        e1d4_asof.py already implements.
#
#   R28  THE D30 GUARD COULD BE SKIPPED ENTIRELY.  The background render launch
#        was wrapped in `|| true`, and the guard below only ran `if [ -f .pid ]`
#        — so a failed launch left no pid file, the guard was skipped, and the
#        index was built on whatever had partially rendered.  That is exactly
#        how blind day 7 sealed 1,109 of 1,117 rows.  The `|| true` is gone, and
#        the count-of-record check now lives in triage_index itself, which
#        compares the day's sheet count against assemble.roster(asset) and
#        REFUSES on a mismatch.  Two independent guards, neither skippable.
#
#   R29  CONSUMERS WERE ROUTED AROUND THE AS-OF MASKING.  The drive was built
#        and then the policy, the cell brief and the take table were all run
#        against `E1BLIND_D${N}_TRIAGE_INDEX.tsv`, the DAY-COMPLETE table —
#        i.e. the mechanic CC-M2-12.1(a) made mandatory was routed around in
#        the driver script itself.  Every consumer below now reads the DRIVE's
#        final prefix, which carries the same rows with the D15 end-of-session
#        columns still masked, and never the day-complete table.
#        REMAINING HALF, not fixable here: e1blind_cellbrief computes its
#        per-cell class histogram over every row of whatever table it is handed
#        (R10), so passing it a prefix bounds the fields but not the
#        cross-row aggregate.  That fix lives in e1blind_cellbrief.py.
set -eu
N="$1"; D="$2"; NEXT="${3:-}"
T=/workspace/artifacts/cache/port/m2/triage
cd /workspace
if [ -n "$NEXT" ]; then
  # R28: NO `|| true`.  A render launch that fails must stop this script, not
  # silently remove the guard that depends on its pid file.
  lab/run.sh "e1blind_render_d$((N+1))" -- /usr/bin/python3 \
    engine/port_m2/era_build.py --era E1 --block BLIND --sessions "$NEXT" \
    --workers 12 >/dev/null 2>&1
fi
# D30 GUARD: never index a day whose on-demand render has not finished.
R=/workspace/artifacts/workflow_memory/runs/e1blind_render_d${N}.rc
if [ -f "/workspace/artifacts/workflow_memory/runs/e1blind_render_d${N}.pid" ]; then
  for _ in $(seq 1 120); do [ -f "$R" ] && break; sleep 10; done
  [ -f "$R" ] && [ "$(cat "$R")" = "0" ] || { echo "D30 GUARD: render d$N not complete (rc=$(cat "$R" 2>/dev/null))" >&2; exit 3; }
fi
# The roster-count guard inside triage_index is the one that cannot be skipped:
# it refuses the whole index when the sheet count for a session disagrees with
# the generation-v3 union roster.
/usr/bin/python3 engine/port_m2/triage_index.py --era E1 --block BLIND \
  --sessions "SI:$D,HG:$D,NKD:$D" --out "$T/E1BLIND_D${N}_TRIAGE_INDEX.tsv" \
  --drive-per-row --drive-out "$T/E1BLIND_D${N}_DRIVE" 2>&1 | tail -1
# R29: every consumer reads the DRIVE, never the day-complete table.  The final
# prefix carries every row of the day with the as-of mask still applied (the
# D15 observed-close block stays masked because the tape has not stopped).
LAST="$(ls "$T/E1BLIND_D${N}_DRIVE"/ASOF_*.tsv | tail -1)"
echo "AS-OF SOURCE: $LAST"
/usr/bin/python3 engine/port_m2/e1blind_policy.py \
  --index "$LAST" --day "$N" \
  --out "$T/E1BLIND_D${N}_POLICY.tsv"
echo "=== AS-OF CELL BRIEF ==="
/usr/bin/python3 engine/port_m2/e1blind_cellbrief.py \
  --drive "$T/E1BLIND_D${N}_DRIVE" --full "$LAST" \
  | grep -v "^  ASSET SO FAR\|classes so far\|as-of prefix"
echo "=== TAKES ==="
/usr/bin/python3 - "$N" "$LAST" <<'PY'
import csv, sys
N, LAST = sys.argv[1], sys.argv[2]
T = "/workspace/artifacts/cache/port/m2/triage/E1BLIND_D%s" % N
pol = list(csv.DictReader(open(T + "_POLICY.tsv"), delimiter="\t"))
idx = {r["cid"]: r for r in csv.DictReader(
    [l for l in open(LAST) if not l.startswith("#")],
    delimiter="\t")}
for c in pol:
    if c["call"] != "TAKE":
        continue
    r = idx[c["cid"]]
    print(" %-28s %s %-5s %-14s %-6s %s rv=%s q50=%s runw=%s age=%s "
          "f5m=%s/%s f60=%s/%s fph=%s trap=%s/%s/%s thru=%s/%s/%s dPOC=%s "
          "inVA=%s" % (c["cid"], c["clock"], c["side"], c["cls"],
                       c["phase_dec"], c["conf"], r["rv1800"], r["q50"],
                       r["runway_phase"], r["extreme_age_trade_side"],
                       r["f5m_sflow"], r["f5m_vol"], r["f60_sflow"],
                       r["f60_vol"], r["fph_vol"], r["trapped_above"],
                       r["trapped_below"], r["phase_total"], r["thru_n"],
                       r["thru_bid"], r["thru_ask"], r["d_POC"], r["in_VA"]))
PY

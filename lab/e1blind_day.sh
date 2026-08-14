#!/usr/bin/env bash
# e1blind_day.sh N DATE8 [NEXT_DATE8] — prepare one E1 BLIND day for the reader.
#   builds the triage index + the as-of driver, runs the reader policy, prints
#   the per-cell as-of brief and the take table, and (optionally) launches the
#   NEXT day's on-demand render in the background so the stepper never waits.
# Never opens an S14 appendix; triage_index.py refuses to.
set -eu
N="$1"; D="$2"; NEXT="${3:-}"
T=/workspace/artifacts/cache/port/m2/triage
cd /workspace
if [ -n "$NEXT" ]; then
  lab/run.sh "e1blind_render_d$((N+1))" -- /usr/bin/python3 \
    engine/port_m2/era_build.py --era E1 --block BLIND --sessions "$NEXT" \
    --workers 12 >/dev/null 2>&1 || true
fi
/usr/bin/python3 engine/port_m2/triage_index.py --era E1 --block BLIND \
  --sessions "SI:$D,HG:$D,NKD:$D" --out "$T/E1BLIND_D${N}_TRIAGE_INDEX.tsv" \
  --drive-step 1800 --drive-out "$T/E1BLIND_D${N}_DRIVE" 2>&1 | tail -1
/usr/bin/python3 engine/port_m2/e1blind_policy.py \
  --index "$T/E1BLIND_D${N}_TRIAGE_INDEX.tsv" --day "$N" \
  --out "$T/E1BLIND_D${N}_POLICY.tsv"
echo "=== AS-OF CELL BRIEF ==="
/usr/bin/python3 engine/port_m2/e1blind_cellbrief.py \
  --drive "$T/E1BLIND_D${N}_DRIVE" --full "$T/E1BLIND_D${N}_TRIAGE_INDEX.tsv" \
  | grep -v "^  ASSET SO FAR\|classes so far\|as-of prefix"
echo "=== TAKES ==="
/usr/bin/python3 - "$N" <<'PY'
import csv, sys
N = sys.argv[1]
T = "/workspace/artifacts/cache/port/m2/triage/E1BLIND_D%s" % N
pol = list(csv.DictReader(open(T + "_POLICY.tsv"), delimiter="\t"))
idx = {r["cid"]: r for r in csv.DictReader(
    [l for l in open(T + "_TRIAGE_INDEX.tsv") if not l.startswith("#")],
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

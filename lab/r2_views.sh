#!/usr/bin/env bash
# r2_views.sh — the round-2 VIEW STACK verification pass, as one command.
#
# Registered through lab/run.sh:
#     lab/run.sh port-r2-views -- lab/r2_views.sh
#
# It runs, in order and failing loudly:
#   1. the R2 red-first fixture (R2-1/2/5/6/7/8 + audit gaps G-2/G-3/G-4/G-12)
#   2. every other M2 fix-lane suite, because R2 touched sections.py (S11) and
#      episode_round.py (the access schema) which those suites also cover
#   3. the R2-2 trajectory differential on an E6 study day
#   4. the ribbon's live-decode-vs-cache differential on three sessions
#   5. the three sample chart panels + the determinism verify
#   6. the view-cost census (D-092.3 measured fidelity, D-086 budget)
#   7. the audit's four spot checks: S11 populated, chart-only take refused,
#      brief read recorded, journal writable
set -uo pipefail

PY=/usr/bin/python3
M2=/workspace/engine/port_m2
RC=0

step() { echo; echo "=== $*"; }
fail() { echo "FAIL: $*" >&2; RC=1; }

step "1/7 R2 red-first fixture"
$PY "$M2/test_r2views_fixlane.py" || fail "test_r2views_fixlane"

step "2/7 the other M2 fix-lane suites"
for t in test_builds_fixlane test_fixlane test_index_fixlane \
         test_reader_fixlane test_avail_fixlane test_gate_fixlane \
         test_pcensus_fixlane; do
  $PY "$M2/$t.py" >/dev/null 2>&1 || fail "$t"
done
echo "  all seven suites run"

step "3/7 R2-2 trajectory differential (E6 study day)"
$PY "$M2/e6_round.py" --day 20240118 --traj-check || fail "traj-check"

step "4/7 ribbon differential: official live decode vs the event cache"
for cid in SI-20240118-003151-L HG-20240320-007080-S NKD-20240416-004029-L; do
  $PY "$M2/ribbon.py" --cid "$cid" --from T-600 --to T --grain action \
      --diff-cache || fail "diff-cache $cid"
done

step "5/7 sample chart panels + determinism"
$PY "$M2/chart_panel.py" --day 20240118 \
    --episodes SI-20240118-L-E03,HG-20240118-S-E12,NKD-20240118-S-E32 \
    --round port-r2-views --caller lab_r2_views || fail "chart render"
$PY "$M2/chart_panel.py" --day 20240118 --episodes SI-20240118-L-E03 \
    --verify || fail "chart determinism"

step "6/7 view-cost census (D-092.3 / D-086)"
$PY "$M2/r2_view_cost.py" --day 20240118 || fail "view cost"

step "7/7 audit spot checks"
$PY - <<'EOF' || RC=1
import os, sys, tempfile
sys.path.insert(0, "/workspace/engine/port_m2")
import m2_common as MC, assemble as A, sections as SEC
import episode_round as ER, e6_round as E6, decision_journal as DJ

ok = True

class P(object):
    def __call__(self, *a, **k): pass
    def refuse(self, *a, **k): pass

# (a) S11 populated
case = A.Case("SI-20240118-003151-L", want_events=False)
body = [l for l in SEC.s11_cross(case, P())[2:] if l.strip()]
bad = [l for l in body if "not strictly prior" in l]
print("  S11 rows=%d refusals=%d" % (len(body), len(bad)))
ok = ok and body and not bad

# (b) a chart-only TAKE is refused
eps = [{"episode_id": "X-20240118-L-E01", "era": "E6", "asset": "SI",
        "date8": 20240118, "rep_cid": "c1", "members": "c1"}]
rank = {"ranked": ["X-20240118-L-E01"], "takes": ["X-20240118-L-E01"]}
with tempfile.TemporaryDirectory() as t:
    e = os.path.join(t, "e.tsv")
    MC.write_tsv(e, "x", "y", list(ER.ACCESS_COLUMNS),
                 [["0", "X-20240118-L-E01", "E6", "SI", "20240118", "c1", "1",
                   "BLIND", "render", "-", "0", "0", "9", "1", "0", "R", "-"]])
    r = ER.take_protocol(eps, rank, round_name="R", ledger=e,
                         ribbon_ledger=os.path.join(t, "nil"),
                         chart_receipt=os.path.join(t, "nil"),
                         brief_ledger=os.path.join(t, "nil"))
print("  chart-only take -> %s" % r["rows"][0]["protocol"])
ok = ok and r["rows"][0]["protocol"] == ER.PROTOCOL_INVALID

# (c) brief read recorded
n = len(E6._read_brief_ledger())
print("  BRIEF_ACCESS rows=%d" % n)
ok = ok and n > 0

# (d) journal writable + blind-fenced
with tempfile.TemporaryDirectory() as t:
    p, i = os.path.join(t, "j.md"), os.path.join(t, "j.tsv")
    DJ.write("SPOT", 20240419, "SI-20240419-L-E01", "SKIP", 0.1,
             reasoning="queue rebuilt twice", path=p, index=i)
    try:
        DJ.write("SPOT", 20240419, "SI-20240419-L-E02", "TAKE", 0.3,
                 reasoning="the oracle seated it", path=p, index=i)
        fenced = False
    except DJ.JournalRefusal:
        fenced = True
    print("  journal written=%d blind_fence=%d" % (os.path.exists(p), fenced))
    ok = ok and os.path.exists(p)
ok = ok and fenced

print("SPOT CHECKS: %s" % ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)
EOF

echo
echo "r2_views.sh rc=$RC"
exit $RC

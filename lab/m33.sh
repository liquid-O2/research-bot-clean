#!/usr/bin/env bash
# M-33 FAILED AUCTION — detector + census + marginal ceiling.  NO BUILD.
# Unaffected by the seating respecification: its verdict is a DP ceiling over the
# CANDIDATE POOL, which is a bound and not a policy.
set -u
cd /workspace
export PYTHONPATH=/workspace/engine/port_m2:/workspace/engine/port_m2/seqtest:/workspace/engine/port_m0:/workspace/engine/port_m1:/workspace/engine/port_m3:/workspace/artifacts/cache/pylibs
say() { echo "[m33 $(date -u +%H:%M:%S)] $*" >&2; }
say "DRIVER UP — M-33 failed auction (detect -> table -> commit)"
say "stage 1/2: detector over the whole corpus (pre-registered constants, unswept)"
python3 engine/port_m2/m33.py --detect --workers 6
rc=$?; say "stage 1/2 rc=$rc"
[ $rc -ne 0 ] && { say "REFUSED at detect — stopping loudly"; exit $rc; }
say "stage 2/2: census + marginal ceiling vs the existing roster"
python3 engine/port_m2/m33.py --table
rc=$?; say "stage 2/2 rc=$rc"
[ $rc -ne 0 ] && { say "table REFUSED — stopping loudly"; exit $rc; }
git add engine/port_m2/m33.py lab/m33.sh provenance/port_m2/M33_FAILED_AUCTION.tsv \
        artifacts/cache/port/m2/m33/events.receipt.json 2>/dev/null
git commit -q -m "M-33 failed auction: detector + census + MARGINAL ceiling against the existing roster (generation-side, unaffected by the seating defect)" || say "nothing to commit"
git push -q 2>/dev/null || say "push deferred"
say "M33 DONE"

#!/usr/bin/env bash
# S1 — THE HORIZON-ALIGNMENT PASS.  ONE CONTINUOUS INLINE DRIVER.
#   no cross-driver rc waits anywhere (a deadlock killed a night once);
#   DRIVER UP is the first heartbeat line so "blocked" can never read as "dead";
#   every stage writes its own artifact and the table is committed as it lands.
set -u
cd /workspace
export PYTHONPATH=/workspace/engine/port_m2:/workspace/engine/port_m2/seqtest:/workspace/engine/port_m0:/workspace/engine/port_m1:/workspace/engine/port_m3:/workspace/artifacts/cache/pylibs
say() { echo "[s1 $(date -u +%H:%M:%S)] $*" >&2; }

say "DRIVER UP — S1 horizon alignment (build -> verify -> table -> commit)"

say "stage 1/3: the three-horizon certificate tensor (all 1,399,374 candidates)"
python3 engine/port_m2/horizon.py --paths --workers 8
rc=$?; say "stage 1/3 rc=$rc"
[ $rc -ne 0 ] && { say "REFUSED at build — stopping loudly"; exit $rc; }

say "stage 2/3: RED FIRST — PHASE must reproduce the committed roster"
python3 engine/port_m2/horizon.py --verify
rc=$?; say "stage 2/3 rc=$rc"
[ $rc -ne 0 ] && { say "RED-FIRST FAILED — nothing downstream may be believed"; exit $rc; }

say "stage 3/3: HORIZON_ALIGNMENT.tsv"
python3 engine/port_m2/horizon.py --table
rc=$?; say "stage 3/3 rc=$rc"
[ $rc -ne 0 ] && { say "table REFUSED — stopping loudly"; exit $rc; }

say "committing"
git add engine/port_m2/horizon.py lab/horizon_s1.sh \
        provenance/port_m2/HORIZON_ALIGNMENT.tsv \
        artifacts/cache/port/m2/horizon/horizons.receipt.json \
        artifacts/cache/port/m2/horizon/verify.receipt.json 2>/dev/null
git commit -q -m "S1 horizon alignment: {phase, next-phase, session}-close priced on ceiling AND realized, wall live, red-first PHASE reproduction" || say "nothing to commit"
git push -q 2>/dev/null || say "push deferred"
say "S1 DONE"

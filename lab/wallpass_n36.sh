#!/usr/bin/env bash
# N3/N6 — THE SESSION-LOAD PASS AT THE WALL SECOND.  ONE CONTINUOUS INLINE DRIVER.
# Deliberately low worker count: the S2 label screen owns the CPU budget and
# this rides beside it without oversubscribing the ~13.6 vCPU quota.
set -u
cd /workspace
export PYTHONPATH=/workspace/engine/port_m2:/workspace/engine/port_m2/seqtest:/workspace/engine/port_m0:/workspace/engine/port_m1:/workspace/engine/port_m3:/workspace/artifacts/cache/pylibs
say() { echo "[n36 $(date -u +%H:%M:%S)] $*" >&2; }

say "DRIVER UP — N3/N6 wall-second second leg (pass -> table -> commit)"

say "stage 1/2: the wall-second tensor (reversal + re-entry legs, wall live)"
python3 engine/port_m2/wallpass.py --pass --workers 2
rc=$?; say "stage 1/2 rc=$rc"
[ $rc -ne 0 ] && { say "REFUSED at wall pass — stopping loudly"; exit $rc; }

say "stage 2/2: WALL_SECOND_LEG.tsv (red-first: the NONE/stop arm must equal apply_stop)"
python3 engine/port_m2/wallpass.py --table
rc=$?; say "stage 2/2 rc=$rc"
[ $rc -ne 0 ] && { say "table REFUSED — stopping loudly"; exit $rc; }

say "committing"
git add engine/port_m2/wallpass.py lab/wallpass_n36.sh \
        provenance/port_m2/WALL_SECOND_LEG.tsv \
        artifacts/cache/port/m2/wallpass/wall.receipt.json 2>/dev/null
git commit -q -m "N3/N6 priced at the wall second: stop-and-reverse and re-entry, both with and against the adopted first-wall stop" || say "nothing to commit"
git push -q 2>/dev/null || say "push deferred"
say "N3/N6 DONE"

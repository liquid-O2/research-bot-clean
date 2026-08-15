#!/usr/bin/env bash
# S2 — THE LABEL RE-SCREEN AT THE ALIGNED HORIZON.  ONE CONTINUOUS INLINE DRIVER.
#   binding eras first (their own table lands early), then the context eras
#   re-emit the full table off the SAME fit cache — nothing is ever refitted.
set -u
cd /workspace
export PYTHONPATH=/workspace/engine/port_m2:/workspace/engine/port_m2/seqtest:/workspace/engine/port_m0:/workspace/engine/port_m1:/workspace/engine/port_m3:/workspace/artifacts/cache/pylibs
say() { echo "[s2 $(date -u +%H:%M:%S)] $*" >&2; }

say "DRIVER UP — S2 label re-screen (binding -> full -> commit)"

say "stage 1/2: BINDING ERAS E5/E6/E7 — 10 arms x 5 seeds + shuffled luck bar x 3 seeds"
python3 engine/port_m2/labelscreen.py --screen --workers 6 --eras E5 E6 E7
rc=$?; say "stage 1/2 rc=$rc"
if [ $rc -ne 0 ]; then say "BINDING SCREEN REFUSED — stopping loudly"; exit $rc; fi
git add provenance/port_m2/LABEL_RESCREEN.tsv engine/port_m2/labelscreen.py lab/labelscreen_s2.sh \
        artifacts/cache/port/m2/labelscreen/targets.receipt.json 2>/dev/null
git commit -q -m "S2 binding-era label re-screen: 8 targets + N4 seat-region + flow/geometry, search-adjusted null + PBO" || say "nothing to commit"
git push -q 2>/dev/null || say "push deferred"
say "BINDING TABLE COMMITTED"

say "stage 2/2: + context eras E3/E4 (reuses the fit cache)"
python3 engine/port_m2/labelscreen.py --screen --workers 6
rc=$?; say "stage 2/2 rc=$rc"
if [ $rc -ne 0 ]; then say "FULL SCREEN REFUSED — the binding table stands"; exit $rc; fi
git add provenance/port_m2/LABEL_RESCREEN.tsv 2>/dev/null
git commit -q -m "S2 label re-screen: all five eras" || say "nothing to commit"
git push -q 2>/dev/null || say "push deferred"
say "S2 DONE"

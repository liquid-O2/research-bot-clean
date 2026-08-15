#!/usr/bin/env bash
# THE ARRIVAL-TIME POLICY — STEP 1: the zoo re-read as arrival scores.
# ONE CONTINUOUS INLINE DRIVER.  Binding eras first, then the context eras.
set -u
cd /workspace
export PYTHONPATH=/workspace/engine/port_m2:/workspace/engine/port_m2/seqtest:/workspace/engine/port_m0:/workspace/engine/port_m1:/workspace/engine/port_m3:/workspace/artifacts/cache/pylibs
say() { echo "[zoo $(date -u +%H:%M:%S)] $*" >&2; }

say "DRIVER UP — arrival-policy zoo (binding -> full -> commit)"

say "stage 1/2: BINDING ERAS E5/E6/E7 — score zoo x causal policy family + shuffled luck bar"
python3 engine/port_m2/arrival.py --zoo --eras E5 E6 E7
rc=$?; say "stage 1/2 rc=$rc"
if [ $rc -ne 0 ]; then say "ZOO REFUSED on binding eras — stopping loudly"; exit $rc; fi
git add provenance/port_m2/ARRIVAL_ZOO.tsv engine/port_m2/arrival.py lab/arrival_zoo.sh 2>/dev/null
git commit -q -m "arrival policy step 1: the score zoo re-read as ARRIVAL scores under a causal policy family (binding eras), with the search-adjusted luck bar" || say "nothing to commit"
git push -q 2>/dev/null || say "push deferred"
say "BINDING ZOO COMMITTED"

say "stage 2/2: all five eras"
python3 engine/port_m2/arrival.py --zoo
rc=$?; say "stage 2/2 rc=$rc"
if [ $rc -ne 0 ]; then say "full ZOO REFUSED — the binding table stands"; exit $rc; fi
git add provenance/port_m2/ARRIVAL_ZOO.tsv 2>/dev/null
git commit -q -m "arrival policy step 1: all five eras" || say "nothing to commit"
git push -q 2>/dev/null || say "push deferred"
say "ZOO DONE"

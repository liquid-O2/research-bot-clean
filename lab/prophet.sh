#!/usr/bin/env bash
# THE CAUSAL PROPHET BOUND — splits the arrival deficit into PREDICTION vs STRUCTURE.
set -u
cd /workspace
export PYTHONPATH=/workspace/engine/port_m2:/workspace/engine/port_m2/seqtest:/workspace/engine/port_m0:/workspace/engine/port_m1:/workspace/engine/port_m3:/workspace/artifacts/cache/pylibs
say() { echo "[prophet $(date -u +%H:%M:%S)] $*" >&2; }
say "DRIVER UP — causal prophet bound (binding eras)"
python3 engine/port_m2/prophet.py --run --eras E5 E6 E7
rc=$?; say "rc=$rc"
[ $rc -ne 0 ] && { say "REFUSED — stopping loudly"; exit $rc; }
git add engine/port_m2/prophet.py lab/prophet.sh provenance/port_m2/ARRIVAL_PROPHET.tsv 2>/dev/null
git commit -q -m "the causal prophet bound: the ceiling of ANY arrival-time model, splitting the deficit into prediction gap vs structure gap" || say "nothing to commit"
git push -q 2>/dev/null || say "push deferred"
say "PROPHET DONE"

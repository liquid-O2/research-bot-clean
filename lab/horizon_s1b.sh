#!/usr/bin/env bash
# S1b — THE SHORT SIDE OF THE HORIZON GRADIENT.  ONE CONTINUOUS INLINE DRIVER.
set -u
cd /workspace
export PYTHONPATH=/workspace/engine/port_m2:/workspace/engine/port_m2/seqtest:/workspace/engine/port_m0:/workspace/engine/port_m1:/workspace/engine/port_m3:/workspace/artifacts/cache/pylibs
say() { echo "[s1b $(date -u +%H:%M:%S)] $*" >&2; }

say "DRIVER UP — S1b short-horizon + re-seating (build -> table -> commit)"

say "stage 1/2: the short-horizon certificate tensor, H in {300,600,900,1800,3600,7200,14400}s"
python3 engine/port_m2/horizon.py --short --workers 8
rc=$?; say "stage 1/2 rc=$rc"
[ $rc -ne 0 ] && { say "REFUSED at short build — stopping loudly"; exit $rc; }

say "stage 2/2: HORIZON_SHORT.tsv"
python3 engine/port_m2/horizon.py --short-table
rc=$?; say "stage 2/2 rc=$rc"
[ $rc -ne 0 ] && { say "table REFUSED — stopping loudly"; exit $rc; }

say "committing"
git add engine/port_m2/horizon.py lab/horizon_s1b.sh \
        provenance/port_m2/HORIZON_SHORT.tsv \
        artifacts/cache/port/m2/horizon/short.receipt.json 2>/dev/null
git commit -q -m "S1b: short exit horizons WITH re-seating priced (ceiling + schedule-free DP + folded arm realized)" || say "nothing to commit"
git push -q 2>/dev/null || say "push deferred"
say "S1b DONE"

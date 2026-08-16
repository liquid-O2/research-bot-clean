#!/usr/bin/env bash
# The SECRETARY grid extended upward — 0.5 won at the TOP of the old grid on both
# E6 and E7, so the optimum was truncated rather than located.
set -u
cd /workspace
export PYTHONPATH=/workspace/engine/port_m2:/workspace/engine/port_m2/seqtest:/workspace/engine/port_m0:/workspace/engine/port_m1:/workspace/engine/port_m3:/workspace/artifacts/cache/pylibs
say() { echo "[secext $(date -u +%H:%M:%S)] $*" >&2; }
say "DRIVER UP — SECRETARY observe-fraction extended to {0.6,0.7,0.8}, all three targets"
python3 engine/port_m2/arrival_fit.py --policy --eras E5 E6 E7
rc=$?; say "rc=$rc"
[ $rc -ne 0 ] && { say "REFUSED — stopping loudly"; exit $rc; }
git add engine/port_m2/arrival.py lab/secretary_extend.sh provenance/port_m2/ARRIVAL_FITTED.tsv 2>/dev/null
git commit -q -m "SECRETARY grid extended upward (0.6/0.7/0.8): the winner sat at the old grid's boundary on two eras, so the optimum was truncated not located" || say "nothing to commit"
git push -q 2>/dev/null || say "push deferred"
say "SECRETARY EXTENSION DONE"

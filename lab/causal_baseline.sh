#!/usr/bin/env bash
set -u
cd /workspace
export PYTHONPATH=/workspace/engine/port_m2:/workspace/engine/port_m2/seqtest:/workspace/engine/port_m0:/workspace/engine/port_m1:/workspace/engine/port_m3:/workspace/artifacts/cache/pylibs
say() { echo "[baseline $(date -u +%H:%M:%S)] $*" >&2; }
say "DRIVER UP — the honest causal baseline (replaces the VOID freeze table)"
python3 engine/port_m2/causal_baseline.py --run --eras E5 E6 E7
rc=$?; say "rc=$rc"
[ $rc -ne 0 ] && { say "REFUSED — stopping loudly"; exit $rc; }
git add engine/port_m2/causal_baseline.py lab/causal_baseline.sh provenance/port_m2/CAUSAL_BASELINE.tsv 2>/dev/null
git commit -q -m "CAUSAL_BASELINE.tsv: the honest arrival-time table, rule selected on the PREVIOUS era and applied blind; replaces the VOID freeze table" || say "nothing to commit"
git push -q 2>/dev/null || say "push deferred"
say "CAUSAL BASELINE DONE"

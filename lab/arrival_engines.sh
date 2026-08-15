#!/usr/bin/env bash
# THE FAIR-ENGINE ROUND, folded onto the ARRIVAL EXPECTANCY (not the voided
# within-cell ranking objective).  Diagnostic = TAIL DOLLARS, never AUC.
set -u
cd /workspace
export PYTHONPATH=/workspace/engine/port_m2:/workspace/engine/port_m2/seqtest:/workspace/engine/port_m0:/workspace/engine/port_m1:/workspace/engine/port_m3:/workspace/artifacts/cache/pylibs
say() { echo "[engines $(date -u +%H:%M:%S)] $*" >&2; }
say "DRIVER UP — fair-engine round on A_EV (LightGBM, LightGBM-dart, CatBoost-ordered vs the xgb incumbent)"
python3 engine/port_m2/arrival_engines.py --fit --workers 4 --eras E5 E6 E7
rc=$?; say "rc=$rc"
[ $rc -ne 0 ] && { say "REFUSED — stopping loudly"; exit $rc; }
git add engine/port_m2/arrival_engines.py lab/arrival_engines.sh provenance/port_m2/ARRIVAL_ENGINES.tsv 2>/dev/null
git commit -q -m "fair-engine round on the arrival expectancy: LightGBM / LightGBM-dart / CatBoost-ordered vs xgb, judged on TAIL DOLLARS and seed stability" || say "nothing to commit"
git push -q 2>/dev/null || say "push deferred"
say "ENGINES DONE"

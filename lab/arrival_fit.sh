#!/usr/bin/env bash
# THE ARRIVAL-TIME POLICY — STEP 2: train + calibrate FOR the arrival decision,
# then re-run the causal policy family on those models.
# ONE CONTINUOUS INLINE DRIVER.  5 workers x 2 threads, sized to ride beside
# the zoo lane inside the ~13.6 vCPU quota.
set -u
cd /workspace
export PYTHONPATH=/workspace/engine/port_m2:/workspace/engine/port_m2/seqtest:/workspace/engine/port_m0:/workspace/engine/port_m1:/workspace/engine/port_m3:/workspace/artifacts/cache/pylibs
say() { echo "[arrfit $(date -u +%H:%M:%S)] $*" >&2; }

say "DRIVER UP — arrival step 2 (fit+calibrate -> policy -> commit)"

say "stage 1/2: A_PWIN + A_PBAR, binary:logistic on the fold structure, isotonic on the inner block (binding eras)"
python3 engine/port_m2/arrival_fit.py --fit --workers 5 --eras E5 E6 E7
rc=$?; say "stage 1/2 rc=$rc"
[ $rc -ne 0 ] && { say "FIT REFUSED — stopping loudly"; exit $rc; }
git add provenance/port_m2/ARRIVAL_TARGETS.tsv engine/port_m2/arrival_fit.py lab/arrival_fit.sh 2>/dev/null
git commit -q -m "arrival step 2: calibrated global arrival targets fitted (A_PWIN, A_PBAR) with isotonic calibration on inner blocks" || say "nothing to commit"
git push -q 2>/dev/null || say "push deferred"

say "stage 2/2: the causal policy family on the calibrated targets"
python3 engine/port_m2/arrival_fit.py --policy --eras E5 E6 E7
rc=$?; say "stage 2/2 rc=$rc"
[ $rc -ne 0 ] && { say "POLICY REFUSED — stopping loudly"; exit $rc; }
git add provenance/port_m2/ARRIVAL_FITTED.tsv 2>/dev/null
git commit -q -m "arrival step 2: causal policy family on the calibrated arrival targets, with the search-adjusted luck bar" || say "nothing to commit"
git push -q 2>/dev/null || say "push deferred"
say "ARRIVAL STEP 2 DONE"

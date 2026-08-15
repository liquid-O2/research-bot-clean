#!/usr/bin/env bash
# THE REAL TEST — the causal policy family on A_EV (plus A_PWIN and A_PBAR as
# the measured counter-examples), with the search-adjusted luck bar.
set -u
cd /workspace
export PYTHONPATH=/workspace/engine/port_m2:/workspace/engine/port_m2/seqtest:/workspace/engine/port_m0:/workspace/engine/port_m1:/workspace/engine/port_m3:/workspace/artifacts/cache/pylibs
say() { echo "[evpol $(date -u +%H:%M:%S)] $*" >&2; }
say "DRIVER UP — causal policy family on the three arrival targets (A_EV is the test)"
python3 engine/port_m2/arrival_fit.py --policy --eras E5 E6 E7
rc=$?; say "rc=$rc"
[ $rc -ne 0 ] && { say "REFUSED — stopping loudly"; exit $rc; }
git add provenance/port_m2/ARRIVAL_FITTED.tsv lab/arrival_ev_policy.sh 2>/dev/null
git commit -q -m "ARRIVAL_FITTED: the causal policy family on A_EV (absolute expectancy), A_PWIN and A_PBAR, with the search-adjusted luck bar" || say "nothing to commit"
git push -q 2>/dev/null || say "push deferred"
say "EV POLICY DONE"

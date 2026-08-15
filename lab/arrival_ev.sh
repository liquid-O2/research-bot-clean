#!/usr/bin/env bash
# A_EV — the ABSOLUTE per-arrival expectancy, the audit's own prescription and
# the only target of the three in the units the stopping comparison is made in.
set -u
cd /workspace
export PYTHONPATH=/workspace/engine/port_m2:/workspace/engine/port_m2/seqtest:/workspace/engine/port_m0:/workspace/engine/port_m1:/workspace/engine/port_m3:/workspace/artifacts/cache/pylibs
say() { echo "[aev $(date -u +%H:%M:%S)] $*" >&2; }
say "DRIVER UP — A_EV absolute expectancy (cached targets are skipped)"
python3 engine/port_m2/arrival_fit.py --fit --workers 5 --eras E5 E6 E7
rc=$?; say "fit rc=$rc"
[ $rc -ne 0 ] && { say "REFUSED — stopping loudly"; exit $rc; }
git add engine/port_m2/arrival_fit.py lab/arrival_ev.sh provenance/port_m2/ARRIVAL_TARGETS.tsv 2>/dev/null
git commit -q -m "A_EV fitted: absolute per-arrival expectancy in dollars, beside A_PWIN (absolute indicator) and A_PBAR (day-relative counter-example)" || say "nothing to commit"
git push -q 2>/dev/null || say "push deferred"
say "A_EV DONE"

#!/usr/bin/env bash
# THE CURRICULUM ROUND, chained end-to-end.  No inter-treatment pauses: each
# stage writes incrementally and the next starts the moment the previous exits.
set -u
R=/workspace/artifacts/workflow_memory/runs
PY=/usr/bin/python3
cd /workspace

# treatment 1 (weighting) is already adjudicated; wait for its run if still live
while [ ! -f "$R/port-m2-curriculum.rc" ]; do sleep 20; done
echo "[curr] weighting rc=$(cat $R/port-m2-curriculum.rc)"

echo "[curr] 1b PER-ERA WEIGHTING SELECTION (inner-block lawful)"
$PY engine/port_m2/curriculum.py --select --eras E3,E4,E5,E6,E7
echo "[curr] select rc=$?"

echo "[curr] 3 DECORRELATED (feature-bagged) ENSEMBLE on the selected weighting"
$PY engine/port_m2/curriculum.py --bagged --eras E3,E4,E5,E6,E7
echo "[curr] bagged rc=$?"

echo "[curr] DONE"

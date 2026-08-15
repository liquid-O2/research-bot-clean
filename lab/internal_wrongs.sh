#!/usr/bin/env bash
# INTERNAL-WRONGS QUEUE — fixing what WE got wrong.
# Sequenced so the regime-router NEVER runs on a legacy forecaster: the router
# was stopped before it started for exactly that reason, and it is placed after
# the forecaster refresh here.
set -u
PY=/usr/bin/python3
cd /workspace
say(){ echo "[iw $(date -u +%H:%M:%S)] $*" >&2; }

while [ ! -f /workspace/artifacts/workflow_memory/runs/port-m2-cellrel.rc ]; do
  sleep 20
done
say "cellrel rc=$(cat /workspace/artifacts/workflow_memory/runs/port-m2-cellrel.rc)"

say "IW-2  SEAT-POLICY REVALIDATION under the 5-seed law (replay only)"
$PY engine/port_m2/policy_reval.py --run
say "IW-2 rc=$?"

say "IW-3  REGIME-ROUTER on the refreshed engine"
$PY engine/port_m2/regime_router.py --run
say "IW-3 rc=$?"

say "INTERNAL-WRONGS BLOCK DONE"

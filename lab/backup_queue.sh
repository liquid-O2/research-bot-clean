#!/usr/bin/env bash
set -u
PY=/usr/bin/python3; cd /workspace
say(){ echo "[bq $(date -u +%H:%M:%S)] $*" >&2; }
while [ ! -f /workspace/artifacts/workflow_memory/runs/port-m2-cellrel.rc ]; do sleep 20; done
say "cellrel rc=$(cat /workspace/artifacts/workflow_memory/runs/port-m2-cellrel.rc)"
say "FLAGSHIP: regime-router specialists (IWM struck from this queue)"
$PY engine/port_m2/regime_router.py --run; say "router rc=$?"
say "BACKUP QUEUE DONE"

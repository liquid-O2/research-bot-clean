#!/usr/bin/env bash
set -u
PY=/usr/bin/python3; cd /workspace
say(){ echo "[rider $(date -u +%H:%M:%S)] $*" >&2; }
while [ ! -f /workspace/artifacts/workflow_memory/runs/port-m2-backup-queue.rc ]; do sleep 20; done
say "backup queue rc=$(cat /workspace/artifacts/workflow_memory/runs/port-m2-backup-queue.rc)"
say "RIDER (a) constrained-HP re-search"
$PY engine/port_m2/riders.py --run; say "rider-a rc=$?"
say "RIDERS DONE"

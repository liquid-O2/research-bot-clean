#!/usr/bin/env bash
# CONSTRAINTS x DISTILLATION COMBINED — queued behind the running gap-closers.
set -u
PY=/usr/bin/python3
cd /workspace
say(){ echo "[cd $(date -u +%H:%M:%S)] $*" >&2; }
while [ ! -f /workspace/artifacts/workflow_memory/runs/port-m2-gapclosers.rc ]; do sleep 15; done
say "gapclosers rc=$(cat /workspace/artifacts/workflow_memory/runs/port-m2-gapclosers.rc)"
say "CD1/2  constrained student under an unconstrained train-window-only teacher"
$PY engine/port_m2/curriculum.py --condistill --eras E3,E4,E5,E6,E7
say "CD1 rc=$?"
say "CD2/2  refreshed stacked final + risk panel + D-030"
$PY engine/port_m2/curriculum.py --stacked --eras E3,E4,E5,E6,E7
say "CD2 rc=$?"
say "CONSTRAINTS x DISTILLATION DONE"

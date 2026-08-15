#!/usr/bin/env bash
# THE TWO GAP-CLOSERS — one continuous process, runs until all of it is done.
set -u
PY=/usr/bin/python3
cd /workspace
say(){ echo "[gap $(date -u +%H:%M:%S)] $*" >&2; }
while [ ! -f /workspace/artifacts/workflow_memory/runs/port-m2-weapons.rc ]; do sleep 15; done
say "weapons rc=$(cat /workspace/artifacts/workflow_memory/runs/port-m2-weapons.rc)"
say "G1/3  CONSTRAINTS TO FULL DEPTH (5 strictness/interaction variants x 5 eras x 5 seeds)"
$PY engine/port_m2/curriculum.py --condepth ALL,CENSUS6,TOP50,CONFLICT_CENSUS,ALL_INTERACT --eras E3,E4,E5,E6,E7
say "G1 rc=$?"
say "G2/3  DISTILLATION with a TRAIN-WINDOW-ONLY teacher (3 variants)"
$PY engine/port_m2/curriculum.py --distill --eras E3,E4,E5,E6,E7
say "G2 rc=$?"
say "G3/3  refreshed stacked final + risk panel + D-030"
$PY engine/port_m2/curriculum.py --stacked --eras E3,E4,E5,E6,E7
say "G3 rc=$?"
say "GAP-CLOSER ROUND DONE"

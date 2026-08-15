#!/usr/bin/env bash
# THE THREE TRAINING WEAPONS — one continuous process, live hb throughout.
set -u
PY=/usr/bin/python3
cd /workspace
say(){ echo "[weap $(date -u +%H:%M:%S)] $*" >&2; }
while [ ! -f /workspace/artifacts/workflow_memory/runs/port-m2-curr-final.rc ]; do sleep 15; done
say "prior driver rc=$(cat /workspace/artifacts/workflow_memory/runs/port-m2-curr-final.rc)"
say "W0/4  building the monotone constraint artifact for all eras"
$PY engine/port_m2/monotone.py --build
say "W0 rc=$?"
say "W1/4  MONOTONE + NOISE arms on the W_VOLMATCH base (5-seed each)"
$PY engine/port_m2/curriculum.py --weapons MONOTONE,NOISE --eras E3,E4,E5,E6,E7
say "W1 rc=$?"
say "W2/4  WEIGHTING-DIVERSE ensemble (volmatch+erabal+flat pooled)"
$PY engine/port_m2/curriculum.py --wdiverse --eras E3,E4,E5,E6,E7
say "W2 rc=$?"
say "W3/4  stacked final refresh + risk panel + D-030"
$PY engine/port_m2/curriculum.py --stacked --eras E3,E4,E5,E6,E7
say "W3 rc=$?"
say "WEAPONS ROUND DONE"

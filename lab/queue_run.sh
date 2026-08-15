#!/usr/bin/env bash
set -u; PY=/usr/bin/python3; cd /workspace
say(){ echo "[Q $(date -u +%H:%M:%S)] $*" >&2; }
say "DRIVER UP — inline, no cross-driver waits, 7 stages"
say "Q1/7  HP re-search (defect fixed: best_score needs early stopping)"
$PY engine/port_m2/riders.py --run; say "Q1 rc=$?"
say "Q2/7  LABEL RE-SCREEN under the current schedule + N4 seat-region row"
$PY engine/port_m2/label_rescreen.py --run; say "Q2 rc=$?"
say "Q3/7  FEATURE ABLATION on the folded config"
$PY engine/port_m2/sufficiency.py --ablation --eras E5,E6,E7; say "Q3 rc=$?"
say "Q4/7  RESERVE CEILINGS N1/N2/N3 then N6 (DP/replay arithmetic)"
$PY engine/port_m2/reserve_ceilings.py --run; say "Q4 rc=$?"
say "QUEUE BLOCK DONE"

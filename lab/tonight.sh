#!/usr/bin/env bash
# TONIGHT'S QUEUE — one registered driver, full width, live hb.
# Distillation is CLOSED NEGATIVE; constraints x distillation is skipped as moot.
set -u
PY=/usr/bin/python3
cd /workspace
say(){ echo "[tonight $(date -u +%H:%M:%S)] $*" >&2; }
say "T1/5  RISK-ADJUSTED RE-RANK (the autopsy mandate, top priority)"
$PY engine/port_m2/confidence.py --riskadj --eras E3,E4,E5,E6,E7; say "T1 rc=$?"
say "T2/5  ISOTONIC calibration"
$PY engine/port_m2/confidence.py --isotonic --eras E3,E4,E5,E6,E7; say "T2 rc=$?"
say "T3/5  THE COMBINED CONFIDENCE-SELECTIVE ARM (agree 0.7-0.9 x risk-adj)"
$PY engine/port_m2/confidence.py --combined --eras E3,E4,E5,E6,E7; say "T3 rc=$?"
say "T4/5  CONSTRAINT DEEPENING (strictness 30/40/50/65/80)"
$PY engine/port_m2/curriculum.py --condepth ALL,TOP50,CENSUS6 --eras E3,E4,E5,E6,E7; say "T4 rc=$?"
say "T5/5  refreshed STACKED FINAL + capture columns"
$PY engine/port_m2/stacked_final.py --run; say "T5 rc=$?"
say "TONIGHT QUEUE DONE"

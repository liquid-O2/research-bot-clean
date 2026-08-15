#!/usr/bin/env bash
# RERUN both distillation stages after the integer-relevance fix, then the
# refreshed stacked final WITH the TOP50 constrained members folded in.
set -u
PY=/usr/bin/python3
cd /workspace
say(){ echo "[dis $(date -u +%H:%M:%S)] $*" >&2; }
say "D1/3  DISTILLATION (teacher train-window-only; integer relevance fixed)"
$PY engine/port_m2/curriculum.py --distill --eras E3,E4,E5,E6,E7
say "D1 rc=$?"
say "D2/3  CONSTRAINTS x DISTILLATION (TOP50-constrained student)"
$PY engine/port_m2/curriculum.py --condistill --eras E3,E4,E5,E6,E7
say "D2 rc=$?"
say "D3/3  STACKED FINAL incl. TOP50 constrained members + risk panel + D-030"
$PY engine/port_m2/curriculum.py --stacked --eras E3,E4,E5,E6,E7
say "D3 rc=$?"
say "DISTILL RERUN DONE"

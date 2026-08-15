#!/usr/bin/env bash
# CONSOLIDATED FREEZE RUN — NO cross-driver waits.
# The previous chain deadlocked: riders waited on backup-queue.rc, which never
# existed because I killed that driver before it could write one, so freeze
# waited on riders forever.  Every stage now runs inline, in order.
set -u
PY=/usr/bin/python3
cd /workspace
say(){ echo "[freeze $(date -u +%H:%M:%S)] $*" >&2; }
say "DRIVER UP — stage 1 of 6 starting immediately (no wait loops)"
say "F1/6  FOLD per-era strictness winners + REBASE CELLREL"
$PY engine/port_m2/fold_stack.py --run; say "F1 rc=$?"
say "F2/6  FINE STRICTNESS k={55..80} per-era AND per-asset, INNER-SELECTED"
$PY engine/port_m2/strictness_fine.py --run; say "F2 rc=$?"
say "F3/6  CONSTRAINED-HP RE-SEARCH on the folded base"
$PY engine/port_m2/riders.py --run; say "F3 rc=$?"
say "F4/6  big-N ensemble on the folded base"
$PY engine/port_m2/stacked_final.py --run; say "F4 rc=$?"
say "F5/6  stop overlay + participation curve"
$PY engine/port_m2/stacked_final.py --stop; say "F5 rc=$?"
say "F6/6  THE FREEZE TABLE (armored primary, per-asset, capture columns)"
$PY engine/port_m2/capture_config.py --run; say "F6 rc=$?"
say "FREEZE RUN DONE"

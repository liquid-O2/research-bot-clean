#!/usr/bin/env bash
# THE CURRICULUM ROUND — ALL REMAINING STAGES IN ONE PROCESS.
# No runner exits between stages: the hb stays live from launch to the stacked
# final.  Every stage writes its TSV before the next begins.
set -u
PY=/usr/bin/python3
cd /workspace

say() { echo "[curr $(date -u +%H:%M:%S)] $*" >&2; }

say "STAGE A/4  bagged ensemble on the W_VOLMATCH base, colsample 0.40"
$PY engine/port_m2/curriculum.py --bagged --base W_VOLMATCH --colsample 0.40 \
    --eras E3,E4,E5,E6,E7
say "STAGE A rc=$?"

say "STAGE B/4  regularization sweep on the W_VOLMATCH base"
$PY engine/port_m2/curriculum.py --reg --eras E3,E4,E5,E6,E7
say "STAGE B rc=$?"

say "STAGE C/4  the stacked final + risk panel + D-030 rates"
$PY engine/port_m2/curriculum.py --stacked --eras E3,E4,E5,E6,E7
say "STAGE C rc=$?"

say "CURRICULUM ROUND DONE"

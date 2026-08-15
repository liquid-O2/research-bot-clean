#!/usr/bin/env bash
set -u; PY=/usr/bin/python3; cd /workspace
say(){ echo "[R $(date -u +%H:%M:%S)] $*" >&2; }
say "DRIVER UP — inline, 2 stages"
say "R1/2  FOLD the HP promotes (E6 depth3/eta0.1 +\$488 dm-sd +160; E4 marginal)"
$PY engine/port_m2/fold_stack.py --run; say "R1 rc=$?"
say "R2/2  RESERVE CEILINGS N1 flexible-allocation + N2 asymmetric-phase (DP/replay)"
$PY engine/port_m2/reserve_ceilings.py --run; say "R2 rc=$?"
say "RESERVE BLOCK DONE"

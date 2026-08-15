#!/usr/bin/env bash
# The remaining chain after confirm landed: blind read -> sufficiency -> ablation.
# Confirm is DONE (rc=0, tables written 13:47); it is not repeated.
set -u
PY=/usr/bin/python3
cd /workspace

echo "[rest] blind read"
$PY engine/port_m2/rank_atlas.py --blind
echo "[rest] blind rc=$?"

echo "[rest] sufficiency split"
$PY engine/port_m2/sufficiency.py --split
echo "[rest] split rc=$?"

echo "[rest] grouped ablation"
$PY engine/port_m2/sufficiency.py --ablation
echo "[rest] ablation rc=$?"

echo "[rest] DONE"

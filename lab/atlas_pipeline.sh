#!/usr/bin/env bash
# RANKING ATLAS pipeline: wait for the screen, then confirm -> blind read, then
# the sufficiency instrument.  One launcher so the stages run back-to-back.
set -u
R=/workspace/artifacts/workflow_memory/runs
PY=/usr/bin/python3
cd /workspace

echo "[pipeline] waiting for the screen"
while [ ! -f "$R/port-m2-atlas-screen.rc" ]; do sleep 30; done
echo "[pipeline] screen rc=$(cat $R/port-m2-atlas-screen.rc)"

echo "[pipeline] STAGE B confirm"
$PY engine/port_m2/rank_atlas.py --confirm --top-n 15
echo "[pipeline] confirm rc=$?"

echo "[pipeline] blind read"
$PY engine/port_m2/rank_atlas.py --blind
echo "[pipeline] blind rc=$?"

echo "[pipeline] sufficiency split"
$PY engine/port_m2/sufficiency.py --split
echo "[pipeline] split rc=$?"

echo "[pipeline] grouped ablation"
$PY engine/port_m2/sufficiency.py --ablation
echo "[pipeline] ablation rc=$?"

echo "[pipeline] DONE"

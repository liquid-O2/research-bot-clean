#!/usr/bin/env bash
# FIXPASS2 — the GPU queue, run AFTER the re-pretraining grid lands.
#
#   1. embed every V2 trunk + the RANDOM_V2 control over the candidate windows
#   2. the FROZEN probe at the repaired vocabulary (isolates F1 alone, at the
#      first pass's exact mechanism)
#   3. F3 + F6: the deploy-matched neural rankers, day groups, +/- hard
#      negatives, +/- day memory
#   4. F2: the partial fine-tune / LoRA arms that retire the frozen probe
#   5. the shuffled-label control at the winning new configuration
set -eu
P=/usr/bin/python3
E=/workspace/engine/port_m2/seqtest
RUNS=/workspace/artifacts/workflow_memory/runs

# --- wait for the pretraining grid -----------------------------------------
while [ ! -f "$RUNS/port-m2-fixpass2-pretrain.rc" ]; do sleep 20; done
echo "pretrain grid rc=$(cat $RUNS/port-m2-fixpass2-pretrain.rc)"

T_NEXT=PRE_V2_shared_NEXT
T_CPC3=PRE_V2_shared_MULTI_CPC0.6
T_CPC0=PRE_V2_shared_MULTI_CPC0

# --- 1. embeddings ---------------------------------------------------------
for T in "$T_NEXT" "$T_CPC3" "$T_CPC0" RANDOM_V2; do
  $P $E/st_pretrain.py --embed --trunk "$T" --tokver v2
done

# --- 2. the frozen probe at the repaired vocabulary ------------------------
for T in "$T_NEXT" "$T_CPC3" "$T_CPC0" RANDOM_V2; do
  $P $E/st_pretrain.py --probe --trunk "$T" --mode fused --tokver v2 \
     --tag "PROBE2_${T}_FUSED"
done
$P $E/st_pretrain.py --probe --trunk "$T_NEXT" --mode seq --tokver v2 \
   --tag "PROBE2_${T_NEXT}_SEQ"
$P $E/st_pretrain.py --probe --trunk "$T_NEXT" --mode ctx --tokver v2 \
   --tag PROBE2_CTXONLY

echo "fixpass2 gpu stage 1-2 complete"

# --- 3. F3 + F6: the deploy-matched neural rankers --------------------------
$P $E/st_fix_drive.py --stage rank

# --- 4. F2: the partial fine-tunes -----------------------------------------
$P $E/st_fix_drive.py --stage ft --steps 800

# --- 5. the red-first controls at the pass's own winning configuration ------
$P $E/st_fix_drive.py --stage control

echo "fixpass2 gpu queue complete"

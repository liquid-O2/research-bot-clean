#!/usr/bin/env bash
# The MATCHED, VAL-GATED pretraining pair (quality-gate amendment 2026-08-16).
set -eu
P=/usr/bin/python3
E=/workspace/engine/port_m2/seqtest
$P $E/st_pretrain.py --pretrain --corpus A --scope shared --budget 1700 --epochs 1
$P $E/st_pretrain.py --pretrain --corpus A --scope shared --budget 1700 --epochs 1 --multi
$P $E/st_pretrain.py --pretrain --corpus A --scope si --budget 900 --epochs 1 --multi
echo "gated pretrain pair complete"

#!/usr/bin/env bash
# lab/seqtest_pretrain.sh — the pretraining stage of port-m2-seqtest, in order.
#
# Implements design/SEQ_PRETRAIN_DESIGN.md + AMENDMENT 1 (shared-vs-SI-only
# ablation, single pass) + AMENDMENT 2 (fusion mandatory, three-row ablation).
# Launched under lab/run.sh as ONE long job so the GPU is never contended.
set -eu
P=/usr/bin/python3
E=/workspace/engine/port_m2/seqtest

# 1. the mandatory throughput smoke, written into the receipt before any run
$P $E/st_pretrain.py --smoke --corpus A --scope shared

# 2. the two trunks (A1.1).  Single pass each; the truncation rule inside
#    st_pretrain holds the wall ceiling rather than overrunning it.
$P $E/st_pretrain.py --pretrain --corpus A --scope shared --budget 4200 --epochs 1
$P $E/st_pretrain.py --pretrain --corpus A --scope si     --budget 2400 --epochs 1

# 3. cache the frozen-trunk representations (one forward pass each)
$P $E/st_pretrain.py --embed --trunk PRE_A_shared
$P $E/st_pretrain.py --embed --trunk PRE_A_si
$P $E/st_pretrain.py --embed --trunk RANDOM

# 4. THE DECLARED ABLATION: seq-only / ctx-only / fused, on identical folds
$P $E/st_pretrain.py --probe --trunk PRE_A_shared --mode seq,ctx,fused
$P $E/st_pretrain.py --probe --trunk RANDOM       --mode seq,fused

# 5. THE SHARED-VS-PER-ASSET DECISION, taken ON SI
$P $E/st_pretrain.py --probe --trunk PRE_A_shared --mode fused --assets SI \
    --tag PROBE_SHARED_FUSED_SI
$P $E/st_pretrain.py --probe --trunk PRE_A_si     --mode fused --assets SI \
    --tag PROBE_SIONLY_FUSED_SI

# 6. the shared trunk's transfer to the thinner books, reported either way
$P $E/st_pretrain.py --probe --trunk PRE_A_shared --mode fused --assets HG \
    --tag PROBE_SHARED_FUSED_HG
$P $E/st_pretrain.py --probe --trunk PRE_A_shared --mode fused --assets NKD \
    --tag PROBE_SHARED_FUSED_NKD

echo "seqtest pretrain stage complete"

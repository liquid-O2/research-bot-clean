# SEQ STACK — IMPROVEMENT BACKLOG (queued 2026-08-17; apply per deficit-ledger results, never mid-run)
B1 DAY-MEMORY TOKENS: prepend compact summaries of the day's prior episodes+resolutions to the input
   (within-day autocorrelation; cell_rank_so_far was a top feature; targets MEMBER-RANKING).
B2 DEEP-ENSEMBLE DISAGREEMENT ABSTENTION: 3-5 seeds; disagreement replaces softmax confidence
   (fixes the measured top-tier inversion; upgrades every frontier tier).
B3 HARD-NEGATIVE RANKING CURRICULUM: wall-pairs weighted into the listwise loss as hard negatives.
B4 MULTI-TASK LABEL HEADS: joint atlas-family targets (retention/walled/fp-race) as regularization.
B5 SEED ENSEMBLES: averaged final scores (variance reduction on NDCG/SEL_WRONG_MEMBER).
Selection rule: after the first stack report + ledger decomposition, apply the backlog item aimed at the
largest surviving deficit; one change per iteration; controls unchanged.

## REPAIR MATRIX (failure signature -> treatment; one change per iteration)
R1 VAL LOSS PLATEAUS HIGH (underfit): ladder up capacity; extend steps (single-pass is a floor not a cap);
   retune LR/warmup; RE-BUCKET the tokenization (too-coarse price-delta/size bins destroy information —
   check tail buckets' occupancy); lengthen context.
R2 TRAIN-VAL GAP GROWS (overfit): weight decay/dropout up; smaller rung; earlier stop; augment (jitter
   sizes/gaps); never train multi-epoch on the same shard order.
R3 LOSS GOOD, PROBES WEAK (representation inaccessible): raise multi-horizon/CPC loss weights (slow
   features starved by the AR head); add SUPERVISED AUXILIARY PROBE HEADS (imbalance/vol-regime/capacity
   as aux losses — shape the representation directly); deepen the projection head so AR stops hogging the trunk.
R4 PROBES GOOD, RANKING FLAT (transfer failure): unfreeze more layers with layer-wise LR decay; attention
   pooling over the window instead of last-token; longer fine-tune; add B1 day-memory tokens.
R5 PER-ASSET VAL SKEWED: stronger balancing; per-asset norm/embedding scales; the per-asset arm wins.
R6 SURPRISE PROFILE FLAT: tokenization losing tail information (re-bucket) or context too short (raise L).
R7 VAL IMPROVES, BENCHMARKS DEGRADE (objective-task misalignment): reweight toward horizon heads; add the
   ranking loss as a semi-supervised auxiliary on the labeled subset during pretraining.

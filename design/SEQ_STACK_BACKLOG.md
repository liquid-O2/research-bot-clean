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

# 16: Combination + causal keep-rule

**What to build:** one probe. Location combination is **OR**, not AND.
A name is eligible if it sits at family A or B or C (TRAIN-chosen).
Then a causal keep-rule that does not see y reduces that pool toward
the high-value names. Shrink-ceiling of the OR-set is the cap: if that
is below the rung on TRAIN, no keep-rule inside it can print the rung.

Finished OR is already measured (ticket 12 union): HG $1878 ret 0.64,
NKD $1172 ret 0.58, SI $1736 ret 0.67. HG shrink is already under
$2000, so OR of those finished families is dead as a HG gate. The OR
set has to include whatever the leftover winners sit on (live HVN,
G1, path identity), or the keep-rule never sees them.

Bars: TRAIN shrink ≥ rung and median names ≤ 16. FORWARD unused as a
knob. 2021 cannot promote.

**Taken encoding (orchestrator, 2026-08-22 novel pass):**

Textbook union ∩ first-third is dead on TRAIN (HG ret 0.47, NKD 0.36).
Do not build it.

Measure, in order:

1. Path-dedup. Cluster names in a cell by aligned dollars / θ. Hindsight
   max-per-cluster vs causal first-per-cluster.
2. Anti-location. Keep names at zero finished families (the leftover
   set that holds 83/73/52% of oracle picks). Second mark: HVN chase or
   G1 at own price, not PDH.
3. Surviving running-max. Current most-extended only after K later
   births failed to beat it. K from TRAIN. Phase-scale, not 300 s.

**Rejected encoding:** confluence k≥2 of finished levels, and
first-third ∩ finished union. Both are the set the winners are not in.

**Blocked by:** tickets 12 and 13 receipts. Fable Turn 2 landed
2026-08-22 and does not amend the taken encoding.

**Fable Turn 2 encoding, rejected.** Turn 2 in
`design/entry_reset/FABLE5_MAX_GOAL_DISCUSSION.md` takes a
location-ok AND first-third-clock funnel, then confluence-count keep,
as `tools/probe_combination_funnel.py`. That is the textbook AND
already dead on TRAIN (HG ret 0.47, NKD 0.36; `NOVEL_FILTERS_20260822.md`).
The human said combination is OR, not AND. Finished OR alone already
leaves HG TRAIN shrink at $1878, under $2000. Do not build that
funnel. Phase IB as the location leg is live until 3600 s and is not
S0. First-third is the time-remaining confound as a gate.

**Status:** path-dedup slice landed. Anti-location and surviving
running-max not built.

- [x] path-dedup `--selftest` (winner-first pick_rate > 0.99;
      winner-last retained < 1; hindsight tautological; NaN y refused)
- [x] Real run
      `artifacts/entry_v2/tabular_recovery/diagnostics/path_dedup_20260822.json`
      schema `QRE2PATHDEDUP1` sha256
      `74de5cd6fb0d3d4e69dda03b63ec4e59570af47520a2773ceb9856d9cf1b4f49`

**Verify (path-dedup slice):**

1. [selftest] → `python3 tools/probe_path_dedup.py --selftest`
2. [real] → `OMP_NUM_THREADS=1 python3 tools/probe_path_dedup.py --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix --out artifacts/entry_v2/tabular_recovery/diagnostics/path_dedup_20260822.json`

**What path-dedup printed (TRAIN tight, 2021). Cannot promote.**

Causal-first of VWAP-aligned/θ buckets: HG ret 0.99 ncell 22
(typed fat-net > 16, shrink $2900, letter
`no majority-and-cut filter`); NKD ret 0.95 ncell 15 shrink $1929
letter `causal_first`; SI ret 0.96 ncell 15 shrink $2486 letter
`causal_first`. Occupancy of causal-first on the cell-max is
outside the shuffle band on all three. Leftover-only stays a fat
net (53/43/26 names). Hindsight max-per-bucket ret 1.00 is
tautological.

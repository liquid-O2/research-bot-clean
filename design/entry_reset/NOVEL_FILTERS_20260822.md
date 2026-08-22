# Novel filters (not PDH confluence, not first-third)

2026-08-22. Human: combination, keep the high-value names, think of
ideas not everyone knows. Textbook union AND first-third already
measured dead on TRAIN (HG ret 0.47, NKD 0.36).

y is unknown at the decision. Argmax y is the shrink-ceiling
diagnostic, never the selector.

## What the receipts say that the books do not

83% HG / 73% NKD / 52% SI of cell-oracle picks sit at *none* of the
finished families (PDH/PDL, prior VAH/VAL, prior LVN, session IB).
Their nearest extra column is live session HVN. Combining finished
levels is stacking the set the winners are not in.

## Constructions to measure (causal)

**1. Path-dedup.** The cell is 50-160 names on a handful of price
paths. Cluster by formation-aligned dollars / θ. Keep one name per
cluster. Hindsight max-per-cluster is the shrink of unique paths.
Causal keep is the first name of each cluster. If hindsight unique-path
shrink is still at the rung and causal-first is not, the path is right
and the representative is wrong.

**2. Anti-location.** Keep names that sit at zero finished families.
That is the leftover set. Then a second causal mark so the pool is not
the whole leftover: developing HVN walked toward this price after
formation, or G1 unpaid volume is at this price. Occupancy of leftovers
on oracle picks is already 0.83/0.73/0.52. Shrink of leftover-only is
the kill test.

**3. HVN chase.** Live session HVN is where leftovers sit. Causal
feature: HVN tick at snapshot minus HVN tick at formation. Keep if the
node moved toward the candidate. The candidate became the day's
business instead of tagging yesterday.

**4. Surviving running-max.** Causal most-extended failed because the
first extreme is premature. Enter the current running-max only after K
later candidates have formed and none beat its extension, with K and a
minimum wait from TRAIN. Phase-scale, not a 300 s clock. Patience
inside 300 s already failed; this waits on *births*, not seconds.

**5. Residual vs phase remaining.** First-third keeps SI because the
label dies at phase close. Keep names whose extension is large after
regressing out phase_remaining_sec on TRAIN. Drop early-only names
with no other mark. Opposite of first-third.

Location combination is OR. AND of union with first-third is not the
construction (human, 2026-08-22). Finished OR alone already leaves HG
TRAIN shrink at $1878, under $2000, so a keep-rule among those remaining
names cannot print the HG rung. The OR set must include the leftover
winners or the gate deletes them before the keep-rule runs.

Banned as the next build: first-third AND finished union, confluence
k≥2 of finished levels. Finished OR without a leftover family is dead
on HG TRAIN.

Receipted 2026-08-22 (`path_dedup_20260822.json` sha 74de5cd6,
formation = phase_elapsed − age):

Leftover-only (not at finished): HG ret 0.98 ncell 53, NKD 0.95 / 43,
SI 0.87 / 26. Keeps the oracle because it barely cuts. Fat net.

Path-dedup causal-first: HG ret 0.99 ncell 22 typed fat-net, NKD 0.95 /
15 letter `causal_first`, SI 0.96 / 15 letter `causal_first`.
Hindsight max-per-cluster ret 1.00 is tautological. Causal-first
occupancy on the cell-max is outside the shuffle band. Names in the
same VWAP bucket have similar y. The object is which path, not which
duplicate on the path.

Location-as-watch on existing G1 names
(`location_watch_20260822.json` sha 469156df): IB V ret 0.28/0.20/0.45
occupancy chance; continuation through IB empty; formed-after-break
fat. The book's S0 order is not a keep-filter on this generator.

Live path-dedup (ticket 18, sha 4beb0045): formation VWAP / 2θ,
keep first. HG 15 names $2781 ret 0.95. Time-NMS does not cut.
The bucket is the swing high or low at birth, not a 60 s clock.

## Next probe

Keep-rule among the ~9-15 live paths. Ticket 16 leftover second-mark
and surviving running-max still open. HVN chase needs HVN at formation
and at snapshot (C++ if the matrix only has snapshot HVN). Running-max
is a walk over formation order inside the cell, still a sum of
precomputed y if flat-by-phase-close holds. Residual vs phase remaining
is a TRAIN residual, FORWARD check.

# What is going wrong, and the path that can actually reach the rung

2026-08-22. Planning skills in the prescribed order. Fable 5 high opinion in
`artifacts/cache/review/fable5_high_opinion_20260822.txt`. This file is the
diagnosis. It amends `overview.md`; it does not replace the ρ ruler or D-110.

Status: plan on disk. Nothing runs except the Fable opinion job already launched.

---

## Verdict

The program has been answering the wrong question. It tries to rank 50–160
near-duplicate reversal series inside one phase, three to ten minutes after
each forms, with a confirmation score that reaches winner-vs-loser AUC about
0.60. The ρ ruler says the dollar rung needs AUC about 0.78–0.89 on that same
within-cell ranking (ρ 0.50–0.71). AUC 0.60 is worth about $200–650 per
asset-day. That is why every model, every fit, and every 300 s rule came back
empty. It is not because Fable cannot write C++. It is not because CatBoost is
the wrong library. It is because 75% of a hindsight cell-max, on a pool that
loses money if entered blindly, is an oracle-grade within-cell ranking, and
the confirmation object does not produce that ranking.

The fix is to stop forcing that ranking, measure where the ceiling actually
lives, and put the selector on that dimension. Entries only. One mini. Frozen
generator. If a block's exact delayed-candidate ceiling cannot support $2,000
per asset-day, that asset's rung on that block is $1,500 (user ruling this
turn). NKD at Δ = 180 s on 2021 already sits there: ceiling $1,934 all /
$1,826 forward.

---

## The three failures, stacked

1. **Code bug (E1R).** Regret label + joint head + argmin never ENTER. $0
   instead of about $500/asset-day. Real, attributed, not the goal. Do not
   relitigate it as the live problem.

2. **Wrong sample.** Every 2026-08-20..22 closure is 67 days of summer 2021,
   forecast context typed-absent, 11–21 days per block. Closed AT that sample
   (CURRENT.md). Scaling the same object to 2022–2025 without changing the
   object will tighten the CI around ρ ≈ 0.15. It will not move ρ to 0.65.

3. **Wrong object (the live failure).** Two honest readings, both receipted,
   now on the table:

   - **Location vs confirmation (this orchestrator).** Anatomy: winners form
     early (tercile winner share about 0.30 / 0.20 / 0.07); the extreme is set
     mid-phase and holds; last-formed is never best. Confirmation answers "is
     this local extreme still defending." The ceiling lives in "is this the
     phase's value extreme." Those are different questions. Five causal shapes
     inside 300 s failed on held blocks. The composite's accrual is real and
     too weak.

   - **Dimension (Fable 5 high, this turn).** The ruler models scoring every
     live series once at Δ = 180 s and taking the top one. Median cell has ~64
     series on one price path. Within-cell series-rank is where ρ dies.
     Nobody has split the ceiling into (a) which phases to trade at all,
     (b) which second on the winning path, (c) which series given the second.
     If (a) or (b) carries the money, the within-cell ρ bar the ruler quotes
     is the wrong bar.

   Both readings ban the same cop-outs: exits, extra minis, size, neural,
   unsealing 2025H2, changing the generator. Both say do not spend the
   one-hour corpus build on the current 4-row-per-series object until the
   ceiling split is known. That sequencing correction is taken.

---

## Goal clauses (this turn + D-110)

| Clause | Law |
|---|---|
| Per-asset rung | $2,000/asset-day if that block's exact delayed-candidate ceiling at the operating Δ is ≥ $2,000; else $1,500. User: if the oracle does not support $2,000, settle for $1,500. |
| 80% of ceiling | Reported diagnostic, not a gate (D-110). |
| Trades | ≤ 12 per portfolio-day. One position per asset. MDD < $1,000. |
| Evidence | Exact replay dollars. 5 real + 5 shuffle. Weakest real > strongest shuffle. Knobs from prior blocks only. |
| Scope | Entries. Generator frozen. Neural dead. 2025H2 sealed. Exits, size, extra minis never a path. |
| Speed | A 12-hour item is inefficient code (user this turn, D-109). Corpus ≈ 1 box-hour once the object is known (D-110). |

2021 NKD at Δ = 180 s: ceiling $1,934 (all) / $1,826 (forward). Rung = $1,500
on that sample. HG and SI ceilings at 180 s are $2,685 and $2,607 (all);
rung stays $2,000 until a later block's ceiling says otherwise.

---

## What we will not do

- Rank the 1,764-column plane with trees. Already lost to unit-weight Dawes.
- Another 300 s threshold rule (extension, patience, re-test-as-price-geometry).
  Failed on threshold and forward. Does not close second-defense (S6): that
  probe never required the level was defended.
- Exits, holds, extra minis, size, neural, generator edits, 2025H2.
- A 10–12 h Python walk as a verdict loop. One-entry-per-phase is a sum of
  precomputed values (0 of 1,473,724 rows still open at phase close).
- Building the 2022–2025 corpus for the current 4-snapshot-per-series object
  before the ceiling split says that is the object.

---

## Design tree (this round)

- Root: reach the per-asset rung from entry selection.
  - Is within-cell series-rank at +180 s the right dimension? **Unknown.**
    Next fact: ticket 07 (marginal dollars on top of the measured picker)
    in parallel with ticket 10 (S6 occupancy) and ticket 09 (scale).
    - If between-cell oracle-skip on top of the measured picker clears the
      rung: cell-quality + θ-skip. Forecast context exists from 2022-02/03.
      Do not close this branch from equal-split arithmetic (3 cells/day);
      cell maxima are unequal (`frac_winner_ge_600` ≈ 0.14).
    - If stored-grid timing on the picked series clears it: the selector is
      when to enter a chosen path, still an entry, not an exit. That is
      timing-within-stored-grid. Continuous timing is unmeasured. Corpus
      must keep a state stream only if 07 prints that letter *and* the
      stored-grid bound is exceeded, which would be an implementation
      defect on this matrix.
    - If series-rank carries it, or if no single dimension on top of the
      measured picker clears the rung: ticket 10 then 08 are the attempt
      to move ρ_series. Write the boundary in the verdict whenever 08's
      THRESHOLD+FORWARD dollars sit below the rung minus the D-106 noise
      floor, whatever letter 07 printed. Do not ask a model for magic.
  - Wire the native builder? **E:** yes, as infrastructure, without freezing
    the snapshot schedule until 07 reports (ticket 02 split: call-site adopt
    now, Δ-grid after 07).
  - Rung when ceiling < $2,000? **G, answered:** $1,500.

---

## Architecture (two sketches; 07 chooses)

**Candidate A (current overview).** Fixed-Δ cell ranker on every live series.
Caller: `cell_selector_verdict(slices, asset, delta_sec, fold, seeds)`.
Deep if the money is in series-rank. Shallow if the money is in which cell.

**Candidate B (Fable; parked until 07).** Cell-quality score + optional
within-cell timing. Caller: `verdict = cell_then_when(corpus, asset, fold)`
returning skip/take per cell and, if take, the second. Deeper if (a) or (b)
dominates: one function hides the split.

**Taken until 07 reports:** do not implement A or B. Implement the split
probe, which is a ruler extension of `probe_rho_ruler.py`, same copula, same
planted/shuffle controls. Minutes. No fit. No walk. No corpus.

---

## Confirmation sequence (PDF re-read, 2026-08-22)

The discretionary PDFs do not score 54 tells. They walk one zone through an
order: finished extreme and memory (S0) → unpaid effort (S1) → reload with
prints, not a spoof (S2) → attacker decays (S3) → opposite aggression (S4)
→ small immediate reward (S5) → **the same side defends a second time (S6,
the entry)**. Waiting is the method. Entry arrows sit on the retest, never
on the first print. Detail and figure notes:
`design/entry_reset/DISCRETIONARY_REREAD_PLAN.md` and
`design/book_confirmations/reread_notes/`.

How we failed it, verified in code: `tools/probe_confirmation_accrual.py:169`
averages DEFENSE/REPLENISH/EXHAUST/LIFTOFF at the same second. The matrix
already emits `disc_state_*_seen` and `_age_sec` and we never asked them
for order. The refill paper's own flow-at-touch grader is AUC 0.54; memory
plus location carry 0.63. Their causal mechanical *entry*, peeks stripped,
is negative (`origin-of-the-move` p18). Do not copy a hand-thresholded OFM.
Do not build G1 until 07 says the money is in timing or series.

Prior for ticket 07, written before the run: the book predicts piles (a)
and (b), not (c). Within-cell series-rank at a fixed Δ is their
flow-at-the-touch, which they measured as a coin flip.

Opus 5 high (`design/book_confirmations/opus5_discretionary_opinion.md`):
vision pass blocked, code audit agrees. First-hand correction on 18k:
licensed Trade 3 is ~4–5 min of clock after the NY open tag, not the
digest's "ten minutes". Fable 5 xhigh and Opus 5 xhigh (same day, second
pass) found that ticket 08's eligibility snippet was a tautology over
mid-price geometry (`retest_seen` implies the other latches;
`discretionary_features.py` 1999–2012) and that 07's sum-to-ceiling clause
cannot fail. Tickets 07 / 09 / 10 are the frontier. Ticket 08 is blocked
by 10. Opinions:
`design/entry_reset/FABLE5_XHIGH_PLAN_CRITIQUE.md`,
`design/entry_reset/OPUS5_XHIGH_MISSING.md`.

---

## The next slice (riskiest unknown first)

**Tickets 07, 09, 10, 11 landed.** Ticket 08 stays closed. Confirmation as
a ranker on the unreduced cell is not the selector. Location families
were scored one at a time (ticket 11). Yesterday PDH/PDL is dead on 2021.
Ranking-by-shrink picked session LVN, a fat net. Phase IB looks like a
selector only on HG TRAIN and is still moving until 3600 s.

**Frontier: C++ for the typed gaps.** Session IB (exploratory) already
missed the shrink-ceiling. Gaps: PWH/PWL, PMH/PML, multi-day untouched
PDH/PDL, VWAP 2-sigma and 2.5-sigma. Do not stack. Do not promote phase
IB (live until 3600 s). Do not fit CatBoost on 1764 columns. Do not call
a null of location because PDH/PDL or session IB missed.

**Ticket 07 — marginal dollars on top of the measured picker.**

What to build: a single-file tool that, per asset and block, publishes P0
(the ρ ≈ 0.15 picker at Δ = 180 s), then P_a / P_b / P_c as the dollars
that picker banks when one dimension at a time is made perfect. No
sum-to-ceiling clause. P_b is timing-within-stored-grid; preregistered
upper bound is `ceiling_series_best − ceiling_180` ($199 HG / $176 NKD /
$207 SI on `all`). Continuous timing is unmeasured. Also publish the
ceiling path's MDD (the $1,000 clause).

1. [Write the probe with red-first selftest] → verify: `python3 tools/probe_ceiling_split.py --selftest`
2. [Run on the frozen 2021 matrix] → verify: exit 0, receipt
   `artifacts/entry_v2/tabular_recovery/diagnostics/ceiling_split_20260822.json`,
   P0 within ±$5 of the ruler's `usd_at_reference_auc['0.60']`, planted arm
   to the cent, shuffle ≈ $0.
3. [Read-out] → verify: which single-dimension oracle on top of the
   measured picker clears the rung, or `no single dimension`. Ticket 08
   does not depend on that letter.

**Ticket 10 — S6 occupancy with a defense join.** Kill-test for the
grammar. `retest_seen` alone is geometry. See `tickets/10-s6-occupancy.md`.

**Ticket 09 — scale, including the engine's own tick constants.** See
`tickets/09-scale-calibration.md`.

Box: minutes on the existing matrix. Abort any one probe if wall > 20 min
(10 min for ticket 10).

---

## Acceptance scenarios

- **SC-DIAG-1** Given a planted matrix where all ceiling dollars sit in 20%
  of cells and within-cell y is noise, When the split probe runs, Then pile
  (a) ≥ 80% of ceiling and piles (b),(c) ≤ 20%. Rejects: a matrix with a
  non-finite y (typed count).
- **SC-DIAG-2** Given the frozen 2021 matrix (7e9e2588…), When the split
  probe runs, Then (a)+(b)+(c) equals the ρ-ruler ceiling@180 per
  asset/block ± $1, and the shuffle arm on each pile is inside ±$50/asset-day.
  Rejects: overlapping definitions that double-count a dollar.
- **SC-RESET-2** (amended) Native builder adopt at the call site may proceed
  in parallel. The 4-offset Δ-grid is not frozen until SC-DIAG-2 is read.
  Rejects: a corpus launch whose snapshot schedule predates the split
  read-out.

---

## How to prompt so this does not regress

Fable's required output shape is adopted for every planning or opinion turn
on every model (verbatim in the Fable file, section 3). Fence: naming exits,
size, extra minis, neural, or 2025H2 as a fallback **fails the turn**.
"exhausted, here is the measurement" is a passing answer. One frozen
question per turn. Paste `entry-v2-goal` and this fence, do not just name
the skill.

---

## Out of scope

Exits, holds, extra minis, size, generator, neural, 2025H2. Relitigating E1R
as the live problem. Another confirmation-threshold rule on the 2021
300 s window. A 12-hour walk. Flattening the PDF stages into a Dawes
average and calling that the confirmation object.

## Applicable skills

keeping-continuity, entry-v2-goal, preregistering-results, running-evals,
encoding-goals-in-gates, verifying-with-receipts, driving-tests-first,
implementing-work, clean-code-for-agents, blast-radius.

## Phases now

1. ρ ruler — landed.
2. Ceiling split (this file, ticket 07) — frontier, starts now when
   implementation is authorized.
3. Native builder at the call site (ticket 02a) — parallel, does not freeze
   snapshots.
4. Snapshot schedule + 2022-03 pilot (ticket 02b) — blocked by 07 read-out.
5. Corpus half-years — blocked by 02b one-hour arithmetic.
6. Selector measurement at scale — blocked by 05, object chosen by 07.
7. Replay + ladder verdict — then the document.

wayfinder skipped for a second map: the destination is unchanged; this file
graduates fog that was already on `ENTRY_RESET_MAP.md`.

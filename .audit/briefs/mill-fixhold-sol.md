# Sol design pass on the fixed-duration exit proposal. 2026-08-28 overnight.

You are a subagent. Don't run memo.
Fresh child, never resume-chain. File pointers, not inlined dumps.

USER standing law: you review every design decision before the parent
judges results. This unit was dispatched in parallel for speed; your page
must be reconciled before any verdict is accepted. Blunt over kind, and
your independent judgment outranks agreement.

## What changed since your closure page

Your sweep-14 page (`.audit/briefs/mill-sweep14-sol-out.md`) ranked the
exit law as the single control most likely to reopen the conclusion,
because sweep 13's ordinal-2 mechanism (postX beat the lateness-matched
control at adjusted p 0.030 on both deciding assets, absolute postX
0.274/0.292) is a timing effect the wall-or-phase-close payoff cannot
monetize.

Independently, and BEFORE your page arrived, the USER proposed the same
lever unprompted, in this form: stop making the policy predict phase
close; hold for a fixed duration, the next hour or two, whichever
horizon the profit lives at, so the model does not have to predict
phase close at all.

USER RULING, mid-dispatch (2026-08-28): the exit law is flexible when
the fixed exit exists to make the model learn proper ENTRIES. Fixed
exits as a learning label are authorized now. Final exits stay tunable
later (ATR-scaled or other shapes) toward the end goal. The thing the
USER will not compromise is that the object being learned is the entry.
The USER framing to test you against: "the fixed exits are there to
make the model learn to take entries, not to take exits." The USER also
ordered full autonomy (no waiting for go-aheads) and asked directly for
ways to fix the noise issue if noise is the main problem.

SWEEP 15 LANDED mid-dispatch (`.audit/mill-sweep15.json`, F12-NOISECEIL,
17 log rows, both reproduction gates exact). Three facts you must
absorb before answering.

1. The order-statistic premium story is dead in reverse. The real
   per-cell-max oracle sits BELOW the p5 of cross-cell within-stratum
   shuffles on every asset at both grains (percentile 0.0 of 200
   draws; fine excess -1555/-3300/-3666, coarse -436/-651/-472 usd/day
   HG/NKD/SI). Big outcomes cluster inside the same cells, and
   re-scattering the identical pooled outcomes raises the per-cell-max
   sum. The pre-registered table did not enumerate the below-p5 case;
   PARTIAL fired by elimination and the parent judged the rows KILL.
2. The decisive finding. On the to-close label the 16-feature state
   predicts SIZE, not DIRECTION. |Y| out-of-fold R2 +0.119/+0.127/
   +0.096; signed Y and sign(Y) are NEGATIVE out-of-fold on all three
   assets. E[Y] per occurrence is negative everywhere (-24/-59/-55).
   This explains every side-calling kill of the night in one line.
3. The coarse post-reset grain (9.0-9.6 occurrences per cell against
   110-136) keeps 93.7/92.1/93.9 percent of the oracle ceiling. A 14x
   smaller selection pool costs 6 to 8 percent of ceiling.

Sweep 16 (below) was dispatched before these numbers existed. The
parent reconciles your page, sweep 15, and sweep 16 into one position
and will not judge sweep 16 first.

## The unit under review. Sweep 16, family F13-FIXHOLD.

Exploratory tier, EXPLORE only, seed 20260827, selftest plus red
mutant, budget 35 minutes. `tools/mill/sweep16.py` (may still be being
written when you read; audit the file if present, else this spec).

Label plane: for every occurrence k in the sweep-14 deduped stream
(47,402 rows, 138/132/132 certifiable cells) and horizon h in {1800,
3600, 5400, 7200} seconds, Y_h(k) = cert of entering at k's stamp on
its fade side and exiting at the FIRST of (the -900 wall crossing,
entry+h, phase close). Frozen entry quote and cost law, cost charged
once at entry, exits at mid, same as the frozen law's wall and close
exits. Y_close kept beside as baseline.

Measurements, per asset, per horizon:
M1 out-of-fold R2 of Y_h on the 16-feature plane under sweep-14's exact
fold law, plus sign and magnitude channels separately, against the
Y_close baseline.
M2 the ordinal mechanism's cash value. Reproduce sweep-13's FIRST and
SECOND entry sets exactly and price both under each Y_h. Paired
asset-day block CIs, 10,000 sign flips, max-stat across horizons and
assets.
M3 the noise-ceiling decomposition applied to Y_h. Real per-cell-max
oracle against cross-cell within-stratum shuffled ceilings, 200 draws,
fine grain and coarse (post-reset first occurrence) grain.
M4 rung arithmetic under sequential capacity. Fixed holds free the
one-position seat, so capacity = feasible sequential entries per
asset-day at each h (entries spaced by h plus the observed median
candidate wait), capped at 12 portfolio-wide. Required per-trade at
rung / (capacity x coverage {0.4, 0.6}) printed beside the out-of-fold
top-decile mean Y_h as the honest edge estimate.
M5 MDD shape of the M2 SECOND line at each h, day-ordered, against the
to-close line.

Pre-registered letters. HORIZON-VIABLE if at some h on a deciding
asset, (out-of-fold R2 >= 0.02 OR the M2 SECOND minus FIRST dollar
delta is positive at max-adjusted p <= 0.05) AND M3 shows structure
excess above the shuffle p95 at either grain AND M4's required
per-trade at 0.6 coverage is within 2x of the observed top-decile mean
Y_h. LABEL-ONLY if predictability appears but the arithmetic falls
short. DEAD if no horizon moves R2, the mechanism cash, or the
structure excess.

## The questions

A. **Design errors.** Leaks or law errors in the label plane (per-entry
   close at min(entry+h, phase_close), wall kept active inside the
   window)? Does keeping the -900 wall inside the window confound the
   horizon contrast with wall-censoring differences across h, and
   should a no-wall diagnostic variant run beside it? Is {30, 60, 90,
   120 min} the right grid given the 1800-second mechanism? Is the
   multiplicity discipline (max-stat across 4 horizons x 3 assets)
   sound, and what exact adjustment law should the parent hold the
   receipt to? Sweep 15 found the real max BELOW the shuffle p5 at the
   to-close law; rule how sweep 16's M3 letter must be read if Y_h
   shows the same clustering direction, so no letter fires by
   elimination again.
B. **The capacity model.** M4 spaces entries by h plus the median
   candidate wait. Does candidate clustering early in phases overstate
   capacity? What coverage assumption is honest for the rung
   arithmetic?
C. **What a positive result authorizes, now that the USER has ruled.**
   The USER authorized fixed-exit learning labels. Given 467 adaptive
   EXPLORE rows, does EXPLORE remain usable to develop an entry model
   on a NEW payoff plane, or does the policy need fresh discipline?
   Write the exact ladder you would hold the parent to (develop where,
   freeze what, the 2021 kill-only screen, the HOLD read), consistent
   with your section E, and restate the promotion bar under a
   fixed-hold line (rungs, MDD both orderings, stress, adjusted nulls).
D. **MDD accounting under sequential entries.** Multiple sequential
   positions per asset-day change the day-sum distribution. Pre-decide
   how MDD must be computed for a fixed-hold line so nothing is argued
   after the numbers exist.
E. **The entries-not-exits framing, judged.** Do you agree with the
   USER's framing that fixed exits are a legitimate scaffold for
   learning entries, with exit engineering deferred? State where the
   framing is sound and where it hides risk (a policy whose entries
   only pay under one h; horizon shopping; the deferred exit tuning
   becoming a fitted lottery). Given the authorization, define the
   final-exit design space worth holding in reserve (fixed h,
   ATR-scaled duration, ATR stops, trailing at horizon) and the
   discipline that keeps later exit tuning honest.
F. **The noise fix, faced directly.** The USER asks for ways to fix the
   noise issue. The fixed-horizon label is a mean-type target rather
   than a per-cell max, and sweep 15 measured the coarse grain at ~93
   percent of ceiling with a 14x smaller pool. Rank the toolbox on
   this record: the coarse post-reset grain, cell-level aggregation of
   decisions, pooled or hierarchical shrinkage across cells,
   ambiguity-band label censoring, anything you add. Which combination
   becomes the successor unit if sweep 16 posts HORIZON-VIABLE, and
   which if it posts DEAD?
G. **The magnitude route, judged with priority.** The one quantity
   verified out-of-fold all night is predicted move SIZE. Direction is
   not predictable from this plane. The USER's exit flexibility makes
   the canonical monetization lawful to design: entries selected by
   predicted |move|, direction made irrelevant by exit asymmetry (a
   stop S well below the predicted favorable excursion, exit at
   horizon otherwise; ATR-scaled S is the USER's own named shape).
   Judge it. State the exact measuring unit you would run first
   (favorable and adverse excursion curves at horizons on
   magnitude-selected states, priced under the frozen entry cost law,
   both sides accounted under the one-position law, coin-side
   expectation), its failure modes (gap through the stop, spread cost
   at stop scale, chop where both sides stop out, capacity,
   regime-dependence of the magnitude signal), whether it survives the
   no-microstructure law at 1-minute inputs, and rank it against the
   ordinal-cash route. If you endorse it, write its pre-registered
   decision letters and thresholds yourself.
H. **Blunt priors.** Probability each route (fixed-hold ordinal cash,
   magnitude-plus-asymmetry) reaches NKD 1500 and SI 1500 causally.
   Name the exact result pattern that would justify the parent
   proceeding straight into entry-model development, versus closing
   the proposal DEAD with a receipt.

Context files: `.audit/briefs/mill-side-resolution.md` (charter, newest
rulings above the sweep-14 closure section), `.audit/mill-sweep13.json`,
`.audit/mill-sweep14.json`, `.audit/mill-sweep15.json`,
`tools/mill/sweep13.py`, `tools/mill/sweep14.py`,
`tools/mill/sweep15.py`, your own pages.

Deliver to `.audit/briefs/mill-fixhold-sol-out.md`. Read-only
otherwise; about 30 minutes. The parent will not judge sweep 16 before
reconciling your page.

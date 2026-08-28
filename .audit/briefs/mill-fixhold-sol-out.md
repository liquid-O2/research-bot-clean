# Sol design judgment on F13 fixed hold

Date 2026-08-28. Scope is the design pass requested in
`.audit/briefs/mill-fixhold-sol.md`.

## Judgment

F13 is **DEAD as a signed ordinal-cash route**. Its M3 result is separately
**CLUSTERED**, not null. The two findings must remain separate. The result does
not close fixed-duration labels as a scaffold for learning entries. It closes
this fade side, 16-feature plane, wall-capped label family, and ordinal contrast
as a route to signed cash.

HOLD stays shut. The next useful unit is one EXPLORE-only magnitude and exit-
asymmetry measurement. It is not another signed ranker and it is not entry-model
development.

The current receipt makes the call easy.

| Asset | Best signed R2 | Best magnitude R2 | Best SECOND minus FIRST | Adjusted p | Minimum M5 day MDD |
|---|---:|---:|---:|---:|---:|
| HG | -0.0300 at 1800 s | -0.0048 at 1800 s | -$77.10/day at 7200 s | 1.000 | $9,482.50 |
| NKD | -0.0318 at 1800 s | +0.0940 at 3600 s | -$80.41/day at 5400 s | 1.000 | $7,057.50 |
| SI | -0.0347 at 1800 s | +0.0406 at 1800 s | +$3.87/day at 1800 s | 1.000 | $8,392.50 |

Every absolute SECOND line is negative at every fixed horizon. Twenty-one of
24 M3 asset, horizon, and grain lines are below p5. The other three are within
band. None is above p95. These facts are in `.audit/mill-sweep16.json`.

The brief's count of 467 adaptive rows is stale. The current hypothesis log has
485 trial rows plus its header. F13 appended 19 of them. EXPLORE remains useful
for development because it was created for adaptive work, but no statistic from
it can promote.

## A. Label plane and inference law

### What is correct

The implementation matches the stated frozen mechanics. It takes the entry
quote strictly before the event, charges the frozen cost once, uses the first
raw mid at the wall or the last raw mid at the close boundary, and never reads a
feature after entry. The scalar hand checks have zero discrepancy. The normal
selftest and the post-exit feature mutant establish the causal seam.

I found no feature leak or sign error that could reverse the receipt. The code
hash recorded in `.audit/mill-sweep16.json` matches `tools/mill/sweep16.py`.

### What is not a clean fixed-duration label

The source rows require only 1800 seconds of scheduled phase time remaining.
The 3600, 5400, and 7200 second labels therefore mix full-horizon exits with
phase-close exits. The frozen generation boundary can truncate a label again.
The receipt does not report either censoring rate. Those labels answer an
executable question, but they do not isolate duration.

Future fixed-duration work must report four exclusive exit causes for every
asset and horizon. They are HORIZON, PHASE_CLOSE, WALL, and GENERATION_END. The
primary horizon contrast uses the common cohort with at least 7200 scheduled
seconds remaining and no generation truncation. A deployable per-horizon table
may use rows with at least h seconds remaining. The existing close-censored
cohort stays beside these as an actual-policy sensitivity.

The -900 wall is a real executable risk rule, but it also censors longer
horizons more often. A longer-horizon contrast can therefore measure extra wall
exposure instead of extra entry information. Run the no-wall terminal return
and excursion path beside the wall-capped label. If no-wall numbers can select
a horizon or fire a letter, they join the registered multiplicity family. If
they are diagnostic only, say so before the outcomes are read. Any final policy
that retains the wall still needs the wall-capped replay.

The 1800, 3600, 5400, and 7200 second grid is defensible for one exploratory
pass. The sweep-13 mechanism makes 1800 seconds primary. The other three are
predeclared sensitivity points. Do not add intermediate horizons after seeing
these results.

### What M2 actually tests

SECOND minus FIRST is not the sweep-13 timing mechanism. It mixes ordinal
position with later entry time. The clean mechanism contrast is POSTX minus its
lateness-matched TIME-MATCH control. Absolute SECOND cash must remain beside
that contrast. The current absolute SECOND cash is negative, so fixing the
control cannot turn F13 into an executable winner.

### Exact multiplicity law

The idea of one max test over the frozen horizon family is right. The current
implementation is not the test described in the brief. It includes `close`, so
it tests 15 lines. It generates independent signs for each line, which destroys
cross-line dependence. It also maximizes unstudentized dollar means across
assets with different scales.

The binding M2 law for a future positive claim is as follows.

1. The eligible family is NKD and SI crossed with the four horizons, giving
   eight tests. HG is report-only. If HG is made decision-eligible before the
   run, the family becomes 12. The close baseline is never in this family.
2. Define one paired difference for every EXPLORE calendar date and line.
   Dates with no difference contribute zero. Use the registered mechanism
   contrast, preferably POSTX minus TIME-MATCH.
3. Studentize each observed mean with its asset-day standard error.
4. For each of 10,000 draws, draw one Rademacher sign per calendar date. Apply
   that same date sign to every asset and horizon, then recompute every
   studentized statistic.
5. Take the maximum positive statistic in each draw. For line j, use
   `p_j = (1 + count(maxT_draw >= T_j)) / 10001`.
6. A cash mechanism claim requires a positive difference and adjusted p at or
   below 0.05. The absolute policy line must also be positive. A relative win
   against a worse control is insufficient.

R2 at 0.02 is an exploratory effect-size screen, not a familywise significance
test. It may not trigger model development alone. A positive prediction claim
requires synchronized asset-day label permutations, a full refit of every
fold, and a maximum R2 null over the same eligible asset and horizon family.

M3 also needs honest family handling if it remains a positive gate. Use one
synchronized within-stratum permutation per draw and take the maximum
studentized excess over the eligible horizons and both grains. The simpler
choice is to keep M3 diagnostic and require the cash test to carry inference.

### Exact M3 reading

M3 has three outcomes.

- ABOVE-P95 means excess per-cell-max structure.
- WITHIN-BAND means unresolved against this null.
- BELOW-P5 means large outcomes cluster inside cells. Call it CLUSTERED.

BELOW-P5 cannot satisfy the pre-registered above-p95 gate, and it cannot fire a
positive letter by elimination. If signed prediction or cash were positive
while M3 was below p5, the correct receipt would be LABEL-ONLY / CLUSTERED and
would route the next model to cell-balanced decisions. Here the registered
signed letter is DEAD and the separate M3 finding is CLUSTERED.

Future M3 comparisons must use the same scoring cohort as M1. Sweep 16 uses all
rows for M3 while M1 scores only rows admitted by its fold law. Also, a
per-cell-max shuffle is not a necessary condition for causal mean
predictability. Do not make it a universal model gate.

## B. Capacity and coverage

M4 is not a capacity estimate. The median wait is 60 seconds because the source
lives on a one-minute lattice and repeats are clustered. Dividing total phase
span by `h + 60` assumes candidates arrive uniformly after each exit. Many
phases instead spend their candidates early, leaving no later seat. The forced
four-entry cap per asset also replaces the actual dynamic portfolio cap with an
equal allocation that the law does not contain.

Capacity must come from a chronological replay over observed eligible
timestamps.

1. Sort all selected candidates by event timestamp. Use a frozen deterministic
   tie break over asset, cell, row, and side.
2. Seat a candidate only when that asset is flat. Process exits before entries
   at an equal timestamp.
3. Price the exact registered exit and keep the asset occupied through its
   actual exit timestamp.
4. Enforce at most 12 seated entries across the portfolio date. Do not reserve
   four for each asset.
5. Carry every split date, including zero-entry dates, into daily cash and
   uncertainty.
6. Report the distribution of seated entries per asset-day, the zero-entry
   fraction, phase and year breakdowns, rejected-for-occupancy counts, and
   rejected-for-cap counts.

There is no honest fixed coverage assumption after this replay exists. Use the
empirical seated entries per day and exact replay cash. For planning only, 0.4
is a conservative sensitivity and 0.6 is optimistic. Neither can fire a letter.
If a planning denominator is unavoidable, use the lower 95 percent asset-day
block bound on mean seated entries. Do not use four times an asserted coverage.

## C. Development and confirmation ladder

The new payoff plane does not reset adaptive reuse. EXPLORE can still develop a
policy because that is its assigned purpose. Its 485 logged trials make its
estimates search-biased and incapable of confirmation.

The exact ladder is below.

1. Develop only on EXPLORE. Use causal rolling or nested folds. Learn score
   cutoffs from each training fold, never from the pooled OOF score
   distribution. Log every tried label, horizon, grain, feature set, model,
   threshold, side law, and exit.
2. Before any external screen, freeze one executable object in writing. Freeze
   the universe and dedup law, input columns and preprocessing, folds, model and
   hyperparameters, learning label, horizon, score cutoff, direction, stop and
   fill law, costs, occupancy, portfolio cap, denominators, null, stress, MDD
   ledgers, decision letters, and all artifact hashes.
3. If fixed h is only a training scaffold and the final exit remains tunable,
   finish the finite exit comparison on EXPLORE before confirmation. A HOLD
   pass under fixed h does not confirm a later ATR or trailing exit. Any exit
   change after HOLD requires a new untouched confirmation era.
4. Replay the frozen object on 2021 once as a kill-only screen, but only if the
   exact causal representation can be reconstructed. A miss kills. A pass only
   licenses the HOLD read. Missing inputs or labels produce STOP, not a proxy
   substitution.
5. Open HOLD once for the frozen object. Do not amend, retune, or read a second
   policy from the miss.

The EXPLORE qualification and the HOLD promotion bar are the standing bar.
NKD must clear $1,500 per asset-day and SI must clear $1,500 with zero-entry
days included. The point estimate and `mean - 2 * asset-day SE` must both clear.
HG may remain report-only for this two-asset milestone. Any HG claim must clear
$2,000. Replay one contract, one position per asset, at most 12 entries per
portfolio date. Every binding MDD ledger must stay below $1,000. The standing
2 percent adversarial replay must still clear the cash and MDD bars. The
registered max-stat cash null must be at or below 0.05. If the legacy -900 wall
is retained, its standing wall-rate bar also remains binding. A HOLD miss kills
the frozen object.

## D. Sequential MDD law

M5 is diagnostic only. It sums one SECOND outcome per cell without enforcing
occupancy or the portfolio cap, and it omits zero-entry dates. Its minimum MDD
is already more than seven times the bar.

Pre-register these ledgers from the accepted chronological replay.

1. Per-asset trade MDD uses seated trades sorted by entry timestamp, then exit
   timestamp, cell, row, and side.
2. Per-asset day MDD sums every sequential trade on each fixed evaluation date
   and includes dates with zero cash.
3. Portfolio trade and portfolio day MDD use the same replay and include all
   assets. The cap is a portfolio law, so a per-asset-only drawdown is
   incomplete.
4. Event-time portfolio equity charges cost at entry and marks every open
   position at the causal raw mid until exit. It captures simultaneous open
   losses that realized ledgers can hide.

For each ledger, start cumulative cash at zero and define MDD as the largest
prior peak minus later equity. The maximum across all binding ledgers must be
strictly below $1,000 on the base replay and the registered stress replay.

## E. Entries first, with the condition stated

I agree with the user's framing. A fixed horizon gives the learner a bounded,
causal question about the state at entry. It removes the need to predict a
distant phase close and is a legitimate training scaffold.

The condition matters. There is no exit-neutral good entry. The learned object
is expected payoff conditional on an exit law. A state can rank well at 30
minutes and lose at 120. Searching horizons can manufacture the appearance of
entry skill, and later exit tuning can become a second fitted lottery. A model
trained on one exit does not inherit validity under another.

Keep only a small final-exit family in reserve.

- Fixed h is the baseline and remains executable as written.
- A volatility-scaled duration uses only strictly prior ATR and strictly prior
  intraday range rate to choose a duration before entry.
- An ATR stop combines a frozen duration with a stop distance fixed in
  `ATR14_prev` units.
- A trailing exit arms only at a predeclared horizon or favorable-excursion
  threshold. Its step, distance, and maximum duration are frozen.

Compare this finite family with nested EXPLORE folds. Retrain the entry model
for each materially different exit, include every exit and parameter in the
same multiplicity family, require stability at neighboring settings, and freeze
the final executable pair before 2021 and HOLD. No exit choice may use HOLD.

## F. Noise treatment

Noise is real, but it is not the whole signed problem. Signed and sign R2 are
negative on all assets. Denoising cannot create conditional direction where
the current state plane has none.

The toolbox ranks as follows.

1. Use the coarse post-reset grain first. It removes about 14 times the rows
   while retaining 92 to 94 percent of the measured ceiling.
2. Balance the loss and the decision at the cell or asset-day level. Repeated
   occurrences from one cell must not dominate a fit or its standard error.
3. Use partial pooling across phase, year, and asset with strictly prior
   training. Asset intercepts and a small number of shrinkage slopes are enough.
4. Prefer robust mean and distribution targets. Huber means, conditional
   quantiles, and joint MFE and MAE targets are better aligned than a per-cell
   maximum.
5. Use ambiguity-band censoring last. Outcome-based censoring can make a
   selected-label problem. It is acceptable as a training sensitivity only if
   the live abstention rule has a causal proxy fixed at entry.

Had F13 been HORIZON-VIABLE, the successor would have been one coarse,
cell-balanced, partially pooled entry model on the registered fixed-h label,
followed by exact sequential OOF replay. Because F13 is DEAD, do not fit another
signed ranker. Move to the magnitude and asymmetry measurement below.

## G. Magnitude and exit asymmetry

This route ranks above ordinal cash. NKD and SI retain real OOF magnitude R2,
while every signed channel and nearly every ordinal cash contrast fail. That is
enough to measure asymmetry. It is not evidence of alpha yet.

Magnitude plus a stop does not make direction mathematically irrelevant. Under
a martingale, a bounded symmetric stopping rule has zero expectation before
costs and negative expectation after costs. The route needs conditional path
continuation or another measured asymmetry. The first unit must test that fact,
not assume it.

### F14-MAGASYM measuring unit

1. Use EXPLORE only and the sweep-15 coarse post-reset universe. Deduplicate an
   identical asset and entry timestamp by the lowest stable cell and row key.
   Keep one-minute causal inputs. No raw suffix value becomes a feature.
2. On the existing chronological folds, fit the 16-feature model to no-wall
   absolute terminal dollar move at h for the same four horizons. Balance cells
   in the loss. Learn the top-decile score cutoff inside each training fold.
   Report OOF R2 and a synchronized max-R2 day-block permutation null.
3. For every selected timestamp, use the frozen entry quote and cost law. Price
   both long and short on raw suffixes through the first of h or phase close.
   Record terminal return, MFE, MAE, first-passage order, and gap size.
4. Test stop distance `q * ATR14_prev` for q in 0.25, 0.50, 0.75, and 1.00.
   Exit at the first actual raw mid through the adverse stop, never at a clipped
   synthetic stop price. Otherwise exit at h or phase close. Report overshoot,
   entry cost divided by stop distance, and the fraction where both hypothetical
   sides stop within h. Keep the legacy wall out of this measurement.
5. The analytic mechanism outcome is half of long PnL plus short PnL at the
   same timestamp. It is a coin-side expectation, not two simultaneous trades.
   The executable sensitivity chooses one side with a frozen hash of asset,
   date, entry timestamp, and seed, then runs the chronological one-position
   replay with the dynamic 12-entry portfolio cap.
6. Build the matched control by permuting OOF magnitude scores among coarse
   states in the same asset, date, and phase cell. Use the same permutation
   across every horizon and stop. Compare selected minus control by asset-day.
   Apply the shared-sign, studentized maxT law across NKD, SI, all horizons, and
   all stops. HG remains report-only.
7. Report year and phase stability, seated capacity, gap-through-stop loss, one
   additional exit-spread stress, and the standing 2 percent adversarial replay.
   For this route, make the 2 percent worst selected entries take the worse of
   their two side outcomes.

This unit respects the no-microstructure law. Inputs stay on the causal
one-minute plane. Raw ticks price outcomes and first stop crossings, just as
the frozen mill already prices walls. Minute OHLC may not infer intraminute
crossing order.

The pre-registered letters are below.

- **ASYM-SURVIVES-EXPLORE** requires NKD and SI each to have a registered
  horizon and stop with magnitude R2 at least 0.02, max-R2 adjusted p at or
  below 0.05, positive selected-minus-control coin expectation at maxT adjusted
  p at or below 0.05, and an exact hash-side replay whose `mean - 2 * SE`
  clears the asset rung. Every MDD ledger and both stresses must clear. The
  nearest inward horizon and stop neighbors must retain positive after-cost
  cash and no MDD breach.
- **MAGNITUDE-ONLY** requires magnitude R2 at least 0.02 with adjusted p at or
  below 0.05 on both deciding assets, plus selected excursion separation, but
  fails the coin expectation or executable rung and risk bar. It confirms a
  measurement signal only. It does not authorize entry-model development or
  HOLD, and it closes this simple ATR-stop monetization shape.
- **ASYM-KILL** fires for the joint route if either deciding asset has no
  magnitude line clearing the adjusted predictive gate, or if every registered
  horizon and stop has a simultaneous 95 percent upper bound at or below zero
  for selected-minus-control coin cash, or below its rung for executable cash.
- **UNRESOLVED** covers every other pattern. It cannot spend HOLD.

The main failure modes are stop gaps, spread cost large relative to the stop,
chop that stops both hypothetical sides, too few later seats, and decay of the
magnitude signal by phase or year. The unit names and measures each one.

## H. Priors and next decision

My joint causal priors for reaching both NKD $1,500 and SI $1,500 are blunt.

- Fixed-hold ordinal cash has a **1 percent** chance.
- Magnitude plus measured exit asymmetry has a **15 percent** chance.

The ordinal prior is near zero because all signed R2 values are negative,
absolute SECOND cash is negative at every horizon, and MDD is many times the
bar. The magnitude prior is higher because NKD and SI retain OOF size signal.
It remains low because size has not produced direction, fair-coin expectancy,
or risk-adjusted cash.

Proceed straight into entry-model development only on
ASYM-SURVIVES-EXPLORE. Positive magnitude R2 alone, a favorable excursion plot,
or one unadjusted stop cell is not enough.

F13 already closes fixed-hold ordinal cash. Close the broader fixed-exit
proposal DEAD if the registered no-wall signed diagnostic also remains
negative and F14 returns ASYM-KILL on either deciding asset. That receipt closes
this proposal, not the user's goal and not the generator. HOLD, 2021, and
2025H2 remain untouched until a frozen survivor exists.

## Verification receipt

The audited result is `.audit/mill-sweep16.json`. Its recorded code SHA is
`fe291e9f8b1d723e7cdfe6230bc0561cc762404745d87c58bfedaaede2f625d4`, which
matches `tools/mill/sweep16.py`. Its spec SHA is
`2db819667c0b43c63239c206828a389b8e9a1a2a1d48a374163d744ddc36c688`.
The sweep-13 reproduction and sweep-15 crosscheck both pass.

`python3 tools/mill/sweep16.py --selftest` passes 22 of 22 checks. With
`QRE2_MILL_S16_MUTANT=horizon_reads_past_exit`, the same command exits 1 and
fails the three intended causal checks. No HOLD, 2021, teacher, late-label, or
2025 byte was opened in this walk.

Primary context pointers are `.audit/briefs/mill-side-resolution.md`,
`.audit/briefs/mill-sweep14-sol-out.md`, `.audit/mill-sweep13.json`,
`.audit/mill-sweep14.json`, `.audit/mill-sweep15.json`,
`.audit/mill-sweep16.json`, and `tools/mill/sweep13.py` through
`tools/mill/sweep16.py`.

Throughput checkpoint is not applicable to this read-only investigation.

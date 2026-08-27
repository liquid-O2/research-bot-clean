# Sol independent ideation on rejection versus rest

The direct caller has a brutal gap. The best causal side reads sit near 0.41 to
0.46, while the drawdown charter tolerates roughly 0.02 wrong fades. The NKD
and SI candidate-grain ceilings require about 0.485 and 0.427 gross capture
before timing loss. Another static feature pile is unlikely to bridge both
gaps.

My first choice is a held-retest join that lets the market resolve the side.
The frozen flow and level-memory test stays second because it adds information
that the failed callers did not have and its remaining cost is nearly zero.
Cross-phase zone memory is third because it targets the phase that causes most
of the damage.

Every screen below is cash-blind. It may use the rejection-side, terminality,
delay, and candidate-availability labels. It may not use teacher cash, a wall,
MFE, MAE, or any return-derived selector. An EXPLORE result can kill an attack.
It cannot promote one or authorize a HOLD read.

## Structurally distinct attacks

### 1. Held-retest resolution join

**Mechanism.** Arm both ATR-scaled extreme zones after they quiet. A zone
resolves only after price retests it, fails to extend the extreme, and then
leaves the zone toward the cell interior. Entering would wait for the next
eligible fade-side candidate. If neither zone holds a retest, the policy does
nothing.

**Why it may beat a coin.** The policy does not predict which quiet extreme
will reject. It waits for a causal state change that defines a defended zone.
This is different from a pullback entry chosen because it looks attractive.
The retest and hold establish the side first. The real risk is that strong
rejections never return, so candidate availability is the first gate.

**Data.** Bar mids, existing ATR-scaled zone episodes, the candidate stream,
and phase boundaries are enough. Flow is not needed.

**Cheapest no-cash screen.** Count unique held retests, the next-candidate
rate, rejection-side error, post-trigger new-extreme rate, and recognition
delay on all 600 cells. Report the no-retest, no-departure, and no-candidate
branches separately. This directly measures whether waiting destroys the
0.40 NKD and 0.35 SI coverage floors.

### 2. Frozen flow and level-memory pair

**Mechanism.** A defended rejection zone absorbs positive attack flow with
little price yield across repeated touches. A resting extreme shows absence,
exhaustion, or flow that still moves price. The frozen D, M, and R5 arms combine
absorption, delta, finished-auction state, schedule, and level memory against
both registered controls.

**Why it may beat a coin.** Every failed caller mainly saw price path or a
compressed candidate race. This test observes who attacked, how much price
moved per attack, and whether the same zone held again. It also compares the
two extremes inside the cell, which removes much of the common regime state.

**Data.** Per-minute aggressor flow, zone episodes, prior-day levels, ATR,
candidate timing, and the current flow cache.

**Cheapest no-cash screen.** Finish the already frozen paired test without an
amendment. Measure side hit, terminal hit, joint hit, coverage, delay, and the
registered delta against both controls. Break out phase 2 and the balance
versus trend diagnostic. Treat the result as unknown until the receipt lands.

### 3. Cross-phase zone memory

**Mechanism.** Carry a causal registry of zones that held during earlier
phases of the same asset-day. When the next phase presents two quiet extremes,
choose only a unique side whose current zone overlaps a previously defended
zone. Ties and no-match cells abstain.

**Why it may beat a coin.** The losing phase is phase 2. A cell-local caller
throws away the prior Tokyo and London tests that can reveal persistent
inventory. Cross-phase memory adds a different time scale without adding a
new market feed.

**Data.** Bar mids, phase boundaries, ATR zones, prior-phase touch counts, and
candidate timing. Flow can remain outside the first screen.

**Cheapest no-cash screen.** Build the registry in one pass. Compare unique
memory matches with the true rejection side on phase 1 and phase 2 cells.
Shuffle the earlier-phase registry across days within asset and phase for the
null. Report selected coverage, side error, delay, and next-candidate rate.

### 4. Prior-level stop-run and recapture

**Mechanism.** At a prior-day high or low, a stop run should show a short
outward excursion, a fast recapture, and no sustained sequence of new
extremes. A genuine continuation should spend more time beyond the level and
keep producing same-direction candidates. Choose only when one side shows the
flush pattern and the other does not.

**Why it may beat a coin.** The prior level supplies a reason for aggressive
orders to arrive. Generic momentum and range position have no such anchor.
The sweep-3 facts put 51% to 59% of terminal extremes near prior-day levels,
so the possible coverage is large enough to test.

**Data.** Prior-day levels, ATR, bar mids, candidate births, and aggressor flow.

**Cheapest no-cash screen.** Use self-scaled excursion depth, time beyond the
level, recapture time, and post-recapture candidate count. Select thresholds
walk-forward on side error and coverage only. Compare with a distance-matched
non-level control and a within-cell side permutation.

### 5. Paired competing-risk survival

**Mechanism.** Model the next state as one of three causal events. The high
breaks again, the low breaks again, or the phase closes with neither break.
Estimate separate hazards for both sides after they quiet. Emit a side only
when the paired survival odds cross a selective threshold.

**Why it may beat a coin.** The fitted 13-feature caller treated the answer as
a static class. A competing-risk model uses event order, censoring, and the
fact that the two sides cannot be interpreted independently. Its confidence
threshold also makes abstention part of the model instead of a score cutoff
added later.

**Data.** Bar mids, candidate event times, quiet ages, phase time remaining,
and optional zone touches. The first pass should exclude flow so this attack
stays independent of the frozen test.

**Cheapest no-cash screen.** Fit cause-specific empirical hazards by prior-day
walk-forward folds. Choose the confidence threshold only from rejection-side
error and coverage. Compare with an age, range-position, and clock control,
plus a within-cell side-label permutation.

### 6. Matched natural flow probes

**Mechanism.** Treat naturally occurring aggressor bursts as probes of each
zone. Match a buy burst near the high with a sell burst of similar percentile
size near the low in the same cell. Compare outward price yield and inward
recovery over the next one, three, and five minutes. The side with lower
outward yield and faster recovery is the defended side.

**Why it may beat a coin.** Aggregate delta mixes attack size with market
state. A within-cell matched response approximates a controlled challenge of
both boundaries. It asks how price responded to equal pressure, not which side
had more volume.

**Data.** Per-minute aggressor flow, bar mids, ATR zones, and candidate times.

**Cheapest no-cash screen.** Form nearest-size burst pairs without replacement.
Use the paired response difference as the only score. Report pair coverage,
side error, delay, and a sign-swap randomization null. No cash is needed.

### 7. Candidate-arrival change point

**Mechanism.** Estimate the online renewal rate of new extremes on each side.
A rejected side should show an abrupt end to its arrival process. A resting or
continuing side should retain a shorter interarrival clock or another burst.
Use a change-point likelihood, not a count race.

**Why it may beat a coin.** The earlier candidate-stream race compressed the
sequence into order and speed summaries. A renewal model preserves clustering,
long gaps, and censoring. Those are the actual signatures of a parent order
stopping.

**Data.** Candidate identities, sides, decision times, phase close, and quiet
times.

**Cheapest no-cash screen.** Fit the pre-change interarrival distribution on
earlier days. Update a two-sided likelihood ratio after both extremes quiet.
Measure high-confidence side error, selected coverage, and delay. Permute
interarrival gaps within asset and phase for the null.

### 8. Regime-scoped admission

**Mechanism.** Admit signals only in a causal balance state and either exclude
phase 2 or demand a separate phase-2 confirmation. Define balance from
realized range versus the day forecast and from value migration. Keep the
underlying side rule fixed.

**Why it may beat a coin.** Quiet has opposite meanings in balance and trend.
Pooling both states can force every side score toward chance. This attack
changes where a fixed rule is trusted rather than adding another side feature.

**Data.** Day-level forecast, realized-so-far range, bar mids, phase, and the
chosen side rule's no-cash outputs.

**Cheapest no-cash screen.** Freeze one walk-forward balance definition from
forecast error quantiles. Report side error and coverage for balance phase 0
and phase 1, balance phase 2, and trend. Use equal-count regime shuffles as the
control. Kill the gate if the selected subset still has coin-grade side error
or falls below the coverage floors.

### 9. Forecast range-exhaustion budget

**Mechanism.** Compare how much of the forecast day range each extreme has
consumed from the open. Prefer the side that has spent a large share of its
causal range budget while producing less continuation per new extreme.

**Why it may beat a coin.** Raw range position and slow mean failed. The
forecast is ex ante information and supplies a scale that those callers did
not have. It can distinguish an ordinary far extreme from an extreme that is
far relative to the expected day.

**Data.** Day-level range forecast, bar mids, open, ATR, phase, and candidate
counts.

**Cheapest no-cash screen.** Use prior-day walk-forward forecast quantiles and
one paired exhaustion difference. Test rejection-side error and coverage.
Require it to beat both raw range position and clock-matched controls. Run an
entry-price collinearity check before believing any separation.

### 10. Latent parent-order schedule fingerprint

**Mechanism.** Infer a sliced parent order from periodic signed-flow pulses.
A pulse train with falling price impact suggests absorption at a defended
zone. The same pulse train with stable impact suggests continuation. Compare
the two sides through their lag spectrum and impact decay.

**Why it may beat a coin.** One-minute aggregation removes order IDs but keeps
the cadence of many execution schedules. Existing totals can miss a repeated
five-minute or fifteen-minute child-order pattern.

**Data.** Per-minute aggressor flow and bar mids. No order IDs are required.

**Cheapest no-cash screen.** Compute signed-flow autocorrelation at lags 1
through 15 and pair it with the change in price yield across pulses. Use a
max-statistic side-permutation null so searching lags does not manufacture a
winner. Report selected coverage, side error, and delay.

### 11. Sequential both-extremes cadence

**Mechanism.** Enter the first qualified side, then consider the opposite side
only after the first frozen-law position exits and another legal candidate is
available. This removes the initial side choice in cells where both entries
can actually seat.

**Why it may beat a coin.** The given S0 fact says even the wrong side's
hindsight best-price fade has positive mean cash. In principle, taking both
could turn side uncertainty into an opportunity-order problem.

**Data.** Candidate times, frozen position intervals, phase close, and the cap
state. The first screen needs no prices.

**Cheapest no-cash screen.** Count cells where both sides can seat sequentially
under the real occupancy law. Report which side arrives first and how much of
the second-side opportunity remains. This attack is probably dead. The given
wrong-side best-price MDD is already 1533, above the 1000 charter, before
causal fill loss.

### 12. Matched-history impossibility certificate

**Mechanism.** Match legal decision states that are nearly identical on every
available causal input but end with opposite rejection labels. Measure the
label disagreement among the closest cross-day twins at the required coverage
levels.

**Why it may dissolve the problem.** If opposite outcomes remain common among
tight causal twins, the missing variable is later order flow or an unavailable
feed. More transformations of the same inputs cannot recover it.

**Data.** All allowed no-cash inputs. Build separate views for price and
candidate history, flow and zone history, and their union.

**Cheapest no-cash screen.** Leave one day out, standardize from earlier days,
and compute nearest-neighbor label disagreement by asset and phase. Compare
with flexible selective classifiers. If every method remains above the wrong-
side budget at the coverage floors, close direct rejection-versus-rest calling
on this data. This is an operational certificate, not a proof about markets.

## Ranking by rung probability and cheapness

The probabilities below are judgment priors, not measured results. Cheapness
is a multiplier from 0 to 1 based on remaining runner work. The product orders
tests only. It must not be quoted as evidence.

| Rank | Attack | P of NKD and SI rungs | Cheapness | Product | Reason for position |
|---:|---|---:|---:|---:|---|
| 1 | Held-retest resolution join | 0.18 | 0.85 | 0.153 | Avoids prediction and has a parameter-light availability gate |
| 2 | Frozen flow and level-memory pair | 0.11 | 1.00 | 0.110 | Already running and adds the missing feed |
| 3 | Cross-phase zone memory | 0.12 | 0.80 | 0.096 | Targets phase 2 with causal same-day history |
| 4 | Prior-level stop-run and recapture | 0.10 | 0.80 | 0.080 | Has a real liquidity anchor and enough possible coverage |
| 5 | Paired competing-risk survival | 0.15 | 0.50 | 0.075 | Better model of the question, but needs a fitted selective hazard |
| 6 | Matched natural flow probes | 0.11 | 0.60 | 0.066 | Strong within-cell control, with moderate pairing work |
| 7 | Candidate-arrival change point | 0.08 | 0.75 | 0.060 | Cheap event-time test, but close to a previously weak information source |
| 8 | Regime-scoped admission | 0.07 | 0.80 | 0.056 | Can remove phase-2 damage, but may discard too much ceiling |
| 9 | Forecast range-exhaustion budget | 0.06 | 0.80 | 0.048 | Truly causal scale, but range-position relatives already failed |
| 10 | Latent parent-order schedule fingerprint | 0.09 | 0.45 | 0.041 | Novel intent signal, but one-minute aliasing is a serious risk |
| 11 | Sequential both-extremes cadence | 0.02 | 0.85 | 0.017 | Occupancy and the known MDD fact are likely fatal |
| 12 | Matched-history impossibility certificate | 0.00 | 0.70 | 0.000 | Cannot earn rungs itself, but can stop waste decisively |

## Tomorrow's top three tests

### Test 1. Held-retest resolution join

**Trigger law.** Use the existing ATR-scaled episode zone and the already
chosen quiet rule. After both sides quiet, arm both zones. A side fires when
all of the following events occur in order:

1. Price touches that side's zone again.
2. The touch does not set a new extreme.
3. A complete one-minute bar then lies outside the zone toward the cell
   interior.
4. The next eligible CLEAR candidate on the fade side appears before phase
   close.

If both sides fire in the same minute, abstain. If the opposite side extends
before step 4, cancel and abstain. Do not add a retrace-distance grid. The zone
boundary supplies the only distance.

**Metrics.** Report opportunity coverage, rejection-side error, post-trigger
new-extreme rate, joint failure rate, terminal-to-trigger delay, trigger-to-
candidate delay, and the three miss branches. Exclude opportunities later
than 45 minutes on NKD or 60 minutes on SI, then recompute coverage. Runtime
does not know terminal time. The delay limit is an evaluation bound only.

**Selection discipline.** This trigger has no fitted weight and no cash-based
choice. Compare it with first-quiet, random eligible side, and side-swapped
controls. Report asset and phase results separately. Do not tune after reading
the table.

**Kill bounds.** Kill if eligible coverage is below 0.40 on NKD or 0.35 on SI.
Kill if the empirical rejection-side error or joint failure exceeds 0.02 on
either asset. Report the binomial upper bound because EXPLORE cannot certify a
2% population error from this sample. A no-error survivor earns a written
freeze decision, not a cash read from this page.

### Test 2. Finish the frozen flow and memory pair

**Trigger law.** Keep the registered D, M, and R5 arms unchanged. Accumulate
attack volume and price yield over the ATR-scaled zone episode. Require the
registered finished-auction and schedule conditions. Let R5 add level memory.
Use the two registered controls exactly as frozen.

**Metrics.** Report the registered delta, side hit, terminal hit, joint hit,
coverage, and delay for NKD and SI. Break out all phases, especially phase 2.
Report balance versus trend, CVD-dies-at-level, and shrinkage-pacing only as
diagnostics. They cannot alter the score.

**Selection discipline.** Do not inspect cash and do not add a third
composite. The running result remains unknown. The current score and both
controls are the complete comparison set.

**Kill bounds.** Apply the frozen bounds. Kill below a 0.03 registered delta.
Keep only at 0.05 or better on both NKD and SI against both controls, with the
0.40 and 0.35 coverage floors intact. A result from 0.03 through less than
0.05 is unresolved. It is not permission to amend the score.

### Test 3. Cross-phase zone memory

**Trigger law.** At each phase close, retain every extreme zone that had a
later touch, no extension on that touch, and an interior departure before the
close. During phase 1 or phase 2, assign each current quiet side two causal
counts. Count the distinct earlier phases with an overlapping held zone, then
count held touches in those zones. Compare sides lexicographically. Choose the
unique larger side and abstain on a tie. Entering would use the next eligible
fade-side candidate.

**Metrics.** Report selected coverage over all cells, rejection-side error,
post-trigger new-extreme rate, delay, next-candidate rate, and phase 2 results.
Also report the number of selections created by a phase match and by the touch
count tie-break.

**Selection discipline.** Use the existing zone width. Fit no weights. Shuffle
the earlier-phase registries across asset-days within asset and target phase
for the null. Keep current-cell price and candidate history fixed during the
shuffle. Do not combine this screen with flow.

**Kill bounds.** Kill if total selected coverage is below 0.40 on NKD or 0.35
on SI. Kill if side error or joint failure exceeds 0.02 on either asset. Kill
if the real-minus-null joint-hit margin is below 0.05. A survivor still needs
one frozen rule and a separately authorized read.

## Devil's-advocate case

The strongest negative case is that rejection is defined by order flow that
has not arrived yet. At a legal entry time, both extremes can have the same
quiet age, similar distance, similar candidate history, and similar local
flow. One later parent order then decides which boundary rests and which one
rejects. Order IDs, options positioning, and news are absent. Phase 2 is where
late orders matter most and where the wall rate rises toward 0.57. The observed
coin results may therefore be the Bayes limit of the available state, not a
modeling failure.

The matched-history certificate can make that claim operational. If tight
causal twins keep opposite labels and every selective model misses the 2%
error budget at the required coverage, direct side calling is closed for this
data. A larger classifier does not change the information set.

If that is true, one family remains credible. A join-only policy waits for a
held retest or another causal state transition that makes the side observable,
then takes the next legal candidate. It pays with missed no-pullback moves, so
the no-cash candidate-availability gate must come first. A regime-scoped form
can admit phase 0 and phase 1 resolution events while refusing unresolved
phase 2 cells.

Sequential both-extremes is not a serious fallback under the present laws.
One position per asset and the frozen exit block many second entries. More
important, the wrong side's hindsight best-price line already has MDD 1533.
That violates the charter before causal entry loss. If the join-only family
misses coverage or delay, no remaining policy in this list has earned a cash
read. The honest result would be that the frozen inputs cannot support the
rungs.

## Wild idea. Reconstruct a latent execution schedule

Treat the one-minute signed-flow tape as a lossy order-ID channel. Search for
repeated pulse spacing, stable pulse size rank, and a consistent aggressor
sign within each zone episode. Then compare the price impact of early and late
pulses. A defended rejection should show the same inferred parent order
continuing while its marginal impact collapses. A resting continuation should
retain impact.

The cheap screen uses autocorrelation lags 1 through 15, pulse-size rank, and
the ratio of late to early price yield. Pair the two sides inside each cell.
Use a max-statistic side permutation across every lag and require the selected
tail to meet the same error and coverage gates. Kill it if no lag family beats
the permutation envelope on both NKD and SI. This is worth one screen because
the user framed the market as algo-dominated. I would not build a larger model
around it unless the spectral receipt separates first.

## Evidence boundary

This page used only the authorized sweep-3, sweep-4, flow-audit, and
structure-audit sections of `.audit/briefs/mill-side-resolution.md`, the stage
A and stage B summaries in `.audit/mill-sweep5.json`, O4b and O4c in
`.audit/mill-sweep4.json`, and the S0 wrong-side fact supplied in the task
brief. It also used the required session-memory facts #674, #676, and #681 for
the algo-intent frame, the no-pullback concern, and the frozen flow bounds. The
frozen flow result was treated as unknown.

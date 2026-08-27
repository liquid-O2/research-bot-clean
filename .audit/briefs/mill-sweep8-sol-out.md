# Sweep 8 survival reframe, Sol co-ideation

Independence note. I did not read a Sweep 8 result, implementation, or log row. The hypothesis log had 400 data rows when I read it and ended at `sweep7b-006`. This page treats both Sweep 8 branches as unknown.

## Bottom line

The two 7b amendments are right. Keep the lateness cap deleted, and keep the depth entry as the primary line. The largest design risk is now measurement. A late entry has less exposure to another extreme, and the depth candidate adds a second wait after the gate fires. Raw post-entry `postX` can therefore improve even if the five-evidence gate predicts nothing.

The first Sweep 8 read must separate three objects.

1. Measure fixed-horizon extension for 1,800 seconds from the gate fire.
2. Measure the same fixed horizon from the candidate entry.
3. Report the fire-to-entry wait and the remaining phase time.

If the gate does not beat an E1-only control and a phase-time-matched random control at the fire stamp, any apparent entry-time pass belongs to depth, delay, or censoring. It does not belong to the survival composite.

## A. Critique of the amended design

### The five evidences

E1, E2, and E4 are largely one mechanism. Quiet age, tape die-off, and interarrival stretch all read the same cessation clock at different resolutions. Giving each one an equal vote makes cadence worth three fifths of `G`. E3 can become stale after its one-shot print, and E5 has the least secure monotone direction. A recent opposite extreme can mean reversal, but it can also mean a two-sided volatile phase.

The equal-weight mean is defensible for a zero-fit first pass. It is not five independent confirmations. If I had set the design before the freeze, I would have averaged E1, E2, and E4 into one cadence block. I would then have averaged that block with E3 and E5. I would also reset E3 on every same-side extreme and report its age at fire.

### The 60th-percentile bar

The 60th percentile is calibrated per completed bar, while the policy watches many bars. Repeated looks make eventual crossing much more common than 40 percent. The correct calibration object is the first crossing per armed extreme or per cell, not the distribution of all bar scores.

I would have picked the bar from strictly prior days to target 0.35 episode coverage without reading outcomes. That keeps the same coverage floor and removes the repeated-look mismatch. The frozen 60th-percentile bar must now stand, but its tables need both bar-level crossing frequency and episode-level entry coverage.

### The depth-primary entry

Making the in-zone candidate primary is the strongest amendment. `SOFT-WRONG/IN-BUDGET` causes 67, 84, and 77 percent of gross loss on HG, NKD, and SI. The first candidate anywhere is therefore the wrong control to promote.

Depth can also hide a weak gate. The in-zone candidate often arrives after the fire, so entry-time `postX` mixes survival discrimination with waiting for a better quote. Report the gate result before applying the candidate condition. Then report the incremental change caused by the in-zone wait.

### The deleted lateness cap

Dropping the cap is correct. `RIGHT/LATE` wins 0.86 to 0.92, has wall rates from 0.00 to 0.04, and contributes positive cash on every asset. The old cap removed the cleanest entries.

The replacement needs a fixed exposure metric. The remaining-time floor of 1,800 seconds makes `postX_1800` available for every entry. Use that metric for selection. Keep extension through phase close as a secondary economic diagnostic.

### Read this failure mode first

Read phase 2 and the fixed-horizon fire table first. Sweep 7a put most continuation risk in phase 2. Sweep 8 fails mechanistically if either condition holds.

- `G` does not lower fire-time `postX_1800` by at least 0.05 against both the E1-only and phase-time-matched controls.
- The improvement appears only after the in-zone candidate wait or only in raw through-close `postX`.

That result would mean the composite is a clock with favorable censoring, not a survival detector.

## B. The late-only question

### What can be known at fire time

`LATE` is a hindsight class. It means the entry happened more than 45 minutes after the faded direction's true terminal extreme on NKD, or more than 60 minutes after it on SI. At fire time, the policy knows only that no newer same-side extreme has appeared yet.

A lawful policy can estimate the hazard of another same-side extreme. It cannot observe terminality. The useful causal state is:

- the current quiet spell relative to prior-day interarrival spells;
- the change in quote, volume, and new-extreme arrival rates;
- the retracement distance from the extreme and whether it held for completed bars;
- the ordinal of the distinct in-zone candidate since the latest extreme;
- the competing event on the other side;
- the fixed 1,800-second risk horizon.

Phase elapsed and phase time remaining belong in matching and censoring controls. They should not earn predictive credit. A direct late policy should estimate `P(new same-side extreme in the next 1,800 seconds)` from strictly earlier days and enter only at a legal in-zone candidate. Do not assume that bare quiet age is sufficient. Sweep 4 found strong terminality separation, but its priced quiet lines still lost with shallow entries and a side objective.

### The rung arithmetic

`RIGHT/LATE` is an optimistic upper bound because `RIGHT` uses `sign(Delta*)`. A causal late selector also receives `SOFT-WRONG/LATE` and `HARD-WRONG/LATE` unless another lawful rule separates them. The all-late rows are the honest empirical mix for a side-agnostic selector.

| Asset and line | Trades | Cell coverage | USD per trade | USD per day | Cell coverage needed at the same USD per trade | USD per trade needed at observed coverage |
|---|---:|---:|---:|---:|---:|---:|
| NKD `RIGHT/LATE` upper bound | 28 | 0.141 | 820.45 | 353.42 | 0.600 | 3,482.14 |
| NKD all late buckets | 56 | 0.283 | 383.17 | 330.12 | 1.285 | 1,741.07 |
| SI `RIGHT/LATE` upper bound | 36 | 0.182 | 828.33 | 465.94 | 0.585 | 2,666.67 |
| SI all late buckets | 67 | 0.338 | 393.51 | 411.95 | 1.232 | 1,432.84 |

The optimistic `RIGHT/LATE` line needs 4.24 times its observed NKD coverage and 3.22 times its observed SI coverage. The all-late causal mix cannot clear alone. At one trade in every cell, its same-economics ceiling is $1,167.19 per NKD day and $1,217.41 per SI day.

### Composition with a depth line

Let `D` be the frozen depth line's USD per asset-day. Let `c` be the late line's non-overlapping cell coverage, `m` the cells per asset-day, and `u` its incremental USD per trade. The pre-replay bound is:

`c_required = max(0, (1500 - D) / (m * u))`

NKD has 3.046 cells per day. SI has 3.094. At the observed all-late coverage and economics, the depth line must already post at least $1,169.88 on NKD and $1,088.05 on SI. At 0.35 non-overlapping coverage, the all-late mix adds $408.52 on NKD and $426.09 on SI. The depth line must then post at least $1,091.48 and $1,073.91.

The `RIGHT/LATE` upper bound is only slightly kinder at its observed prevalence. It requires a depth line of at least $1,146.58 on NKD and $1,034.06 on SI. Do not use that bound to dispatch a line. It assumes the hindsight `RIGHT` label.

These sums are bounds, not replay results. Same-cell overlap, one-position occupancy, and the portfolio entry cap can only reduce them. A composition earns a cash read only after its non-overlapping coverage satisfies the formula.

## C. The cheapest attacks on soft-wrong-in-budget

The second distinct in-zone candidate is the cheapest lever worth a cash read. It uses the frozen candidate generator, adds no side model, and asks for one more observable event at the price level. A second completed gate bar is cheaper to code, but it mostly adds 60 seconds to a problem whose profitable tail is measured in hours.

Run these as separate one-knob units. Do not form a grid.

| Priority | One change | No-cash screen | Pre-registered keep bound |
|---|---|---|---|
| 1 | Change candidate ordinal from first to second distinct in-zone candidate. Reset the ordinal after a same-side new extreme. Keep the 15-minute wait limit. | Cell coverage, fixed-horizon `postX_1800`, first-to-second wait, and candidate identity duplication. | Coverage at least 0.35, `postX_1800` at most 0.25 and at least 0.05 below the Sweep 8 depth line, p90 added wait at most 900 seconds, and zero duplicate identities. |
| 2 | Change gate persistence from one completed bar above the 60th-percentile bar to two consecutive completed bars. Keep the entry law unchanged. | Fire-time `postX_1800`, coverage, and added fire-to-entry delay against the same phase-time control. | Coverage at least 0.35, `postX_1800` at most 0.25 and at least 0.05 below the Sweep 8 depth line, with p90 added entry delay at most 180 seconds. |
| 3 | Change the price condition from the full 0.15 ATR zone to its inner half, at most 0.075 ATR from the running extreme. Keep the first candidate. | Paired favorable quote improvement in ATR, coverage, wait, and `postX_1800`. | Coverage at least 0.35, median favorable quote improvement at least 0.05 ATR, `postX_1800` no more than 0.02 above the base, and p90 added wait at most 900 seconds. |

The first two screens attack continuation. The third buys price buffer and need not lower extension. That is why its screen uses paired quote improvement and only a non-inferiority bound on `postX_1800`.

## D. The unsharp band

Use `AMBIGUOUS` as a third reporting label. Ignore it for Sweep 8 selection because `postX` does not need `sign(Delta*)`. Keep every ambiguous entry in coverage, cash, walls, and replay unless a separate causal abstention rule earns a read.

The options have different consequences.

| Choice | Metric effect | Coverage and cash effect | Ruling |
|---|---|---|---|
| Hindsight abstention | Side accuracy rises because the hard cases disappear. The number is not causal. | On the 7b opportunity set, NKD coverage falls from 0.874 to 0.747 and SI coverage falls from 0.747 to 0.657. Keeping the same rung would require 1.169 times the NKD USD per trade and 1.138 times the SI USD per trade if removed trades had average economics. | Do not use. |
| Third label | Report sharp-side agreement, ambiguous rate, and total coverage separately. | Coverage and cash stay unchanged until a causal ambiguity predictor abstains. | Use for diagnostics. |
| Ignore for policy | Side agreement excludes `AMBIGUOUS`, while survival, cash, walls, and coverage include it. | No arithmetic change. | Use for Sweep 8. |

The flip mistake shows why the distinction matters. `1 - side_agreement` awarded the 12 to 14 percent ambiguous band to the flipped side and manufactured the 0.618 lead. A third label makes that complement impossible.

## E. The two branches

### If Sweep 8 is interesting or better

First require the exposure-matched fire table from section A. If it passes, use this order.

1. Run the second-distinct-candidate unit from section C. This is the direct SWIB attack.
2. If continuation remains the miss, run the two-bar persistence unit.
3. If terminality passes but walls still bind, run the inner-half zone unit.
4. Open late composition only when the frozen depth line and measured non-overlapping coverage satisfy the equation in section B.

Each unit changes one knob from the last frozen line. Each unit uses its own no-cash bound before one priced read. Do not stack two unpriced changes. Freeze an asset as soon as it clears its rung, both MDD orderings, stress, replay, and the adjusted null.

For late composition, require `postX_1800 <= 0.15`, overall non-overlapping coverage at least `c_required`, and a reduction of at least 0.05 against a phase-time-matched control. Price one union line only. Use chronological replay rather than adding two cash totals.

### If Sweep 8 kills

The next unit should be the matched-history certificate, updated for survival rather than side. It can also decide whether the pre-existing balance regime deserves one scoped successor. The dispatch below is ready to paste.

```text
You are a subagent. Don't run memo.

Build and run Sweep 9, the matched-history survival certificate. Sweep 8 has KILLed. Read its receipt and judge page first. Reproduce its eligible opportunity counts before doing any measurement.

OBJECTIVE
Decide whether the allowed causal state can identify 1,800-second survival at deployable coverage. This is a no-cash certificate. It can route one regime-scoped successor or close the current survival feature set. It cannot promote a trading line.

DATA LAW
Use EXPLORE days only. Use the existing mill candidate plane, context cache, and flow-zone cache. Keep HOLD, 2021, 2025, teacher labels, late stores, and every sealed R4mem field shut. Use only completed bars and candidate facts available at each decision timestamp. One row is one distinct in-zone CLEAR candidate at its own decision timestamp. Require extreme age at least 300 seconds and phase time remaining at least 1,800 seconds. Deduplicate candidate identity within a cell and side.

LABEL
Set `Y1800 = 1` when no same-side new extreme occurs during the next 1,800 seconds. Set it to zero otherwise. Report through-close terminality only as a secondary column. Never use either label as a feature.

FEATURE VIEWS
Build four frozen views. `CLOCK` contains asset, phase, phase time remaining, and phase elapsed. Use it only for matching and as a control. It is not eligible for a `SURVIVOR` letter. `S8` contains E1 through E5 exactly as Sweep 8 computed them, plus candidate ordinal and ATR-normalized distance from the running extreme. `SEQUENCE` contains extreme age, prior same-side extreme count, the last three same-side interarrival gaps, the last-10-minute quote and volume ratios, the current gap ratio, opposite-side recency, and the in-zone candidate ordinal. `UNION` is the union of `S8` and `SEQUENCE`. Do not add a fitted flow composite.

WALK-FORWARD LAW
Scale every continuous field from strictly earlier EXPLORE days within asset and phase. Match asset and phase exactly. Require phase elapsed and phase time remaining to differ by no more than 300 seconds. Find each row's nearest prior-day twin in the remaining fields of each eligible view. Also run one fixed five-nearest-neighbor risk estimate. Calibrate the selective bar on prior days to target 0.35 cell coverage. Apply Sweep 8's first-fire, cancellation, and one-entry-per-cell laws unchanged. Keep test days blocked. Never match rows from the same asset-day.

REGIME CUT
Use the existing causal ratio of running range to the square root of forecast variance. Fit balance, middle, and trend tercile edges on strictly earlier days. Report pooled results first and the three frozen regimes second. Measure overall cell coverage after regime admission, not coverage within the admitted regime.

CONTROLS AND NULL
Use E1-only and phase-time-matched random timing as controls. Permute `Y1800` by asset-day blocks within asset, phase, and regime for 1,000 draws. Use a max statistic across NKD, SI, the four views, and the three regime cuts. Seed every draw with 20260827.

METRICS
For each asset and view, report selected cell coverage, `postX_1800`, the delta against both controls, a day-block 95 percent confidence interval, adjusted null p, nearest-twin distance, and label disagreement among the closest 35 percent of twins. Report candidate availability and p90 decision delay. HG is report-only.

BOUNDS
Letter `SURVIVOR` on a deciding asset only if coverage is at least 0.35, `postX_1800` is at most 0.25, the improvement against both controls is at least 0.05, both paired confidence lower bounds exceed zero, and adjusted p is at most 0.05.

Letter `REGIME_SURVIVOR` only if the pooled line misses, one frozen regime meets every `SURVIVOR` bound at at least 0.35 overall coverage, and its improvement over the other regimes is at least 0.10 with adjusted p at most 0.05. Route exactly that view and regime to one scoped survival unit.

Letter `CERTIFICATE` only if every view has `postX_1800` above 0.30 at 0.35 coverage, every improvement upper confidence bound is below 0.05, and closest-twin disagreement has a 95 percent lower bound of at least 0.35 on both NKD and SI. This closes transformations of the current causal state. It is not a claim about unavailable feeds or markets.

Letter `UNRESOLVED` for the interval between those bounds. Do not price an unresolved result.

VERIFICATION
Implement `--selftest` with one synthetic plane where a causal feature perfectly identifies survival and one where identical states have opposing labels. Add a mutant that reads the next interarrival gap as a feature. The mutant must turn the selftest red. Target less than ten minutes on the existing caches.

DELIVERABLES
Write `tools/mill/sweep9_twins.py`, `.audit/mill-sweep9-twins.json`, and the matching hypothesis-log rows. Stop at that receipt. Do not write MEMORY.md and do not open cash.
```

## Recommendation

Do not build a direct `RIGHT/LATE` classifier. Build a survival selector and judge it on fixed exposure. If Sweep 8 has real fire-time separation, the second distinct in-zone candidate is the next clean hillclimb. If Sweep 8 has no separation, run the matched-history certificate before another survival score.

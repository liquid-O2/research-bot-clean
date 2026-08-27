# Flow-arbiter route ruling

Date: 2026-08-27

Scope: independent strategic ruling for the NKD and SI milestone. HG is a
diagnostic only because the USER deferred it. The pending composition baseline,
flow cache, PDF playbook, and PDF audits were not read.

## A. Strategic ruling

**Ruling.** Keep the minutes-scale flow arbiter for one zero-fit, no-cash test.
Do not keep it as a research program. The route is a sound cheap falsification
of the one missing variable. It becomes a goose chase as soon as a miss leads
to feature expansion, weight fitting, or a third read.

### The strongest case for the route

The sweep-4 decomposition is unusually clean.

- Candidate anchoring is not the problem. The S0-replica oracle posts 2182,
  3095, and 3514 USD per asset-day for HG, NKD, and SI. All three rungs clear.
- Delay is not yet the problem for the two-asset milestone. With the side and
  terminal extreme known, NKD clears through 45 minutes and SI clears through
  60 minutes. The composition branch keeps the narrower buffered budgets of 20
  minutes for NKD and 45 minutes for SI.
- Terminality is measurable. The non-terminal false-positive rate falls from
  about 0.19 at Q10 to about 0.05 at Q60 while terminal recall remains about
  0.74 to 0.96.
- Side is the measured failure. Side-blind Stage B reaches 0.75 to 0.82
  terminal-hit, but side_hit is only 0.36 to 0.57. Cash remains between -158
  and +38 USD per asset-day.

That leaves a narrow causal question. At a quieted running extreme, can local
flow identify rejection rather than continued control? Absorption, delta-price
divergence, a flush toward the fade side, and persistent counterflow all address
that question directly. The in-flight cache also makes the marginal test cheap.

The CatBoost loss does not answer this exact question. The prior crosswalk
exposed 1,352 atomic `disc_*` columns at early per-name snapshots and asked a
tree model to learn the interaction. The proposed test reads a few oriented
level scores at the later detector state and combines them with fixed equal
weights. It changes the time, the comparison unit, and the model form.

### The strongest case against the route

The prior loss still carries real weight. The crosswalk was not a toy
implementation. It had 1,290 nonconstant discretionary columns, 1,058 columns
that varied within a watch path, explicit absorption and price-yield families,
and causal path controls. A loss across that representation makes the prior
probability of a stable flow edge low.

The mill record is harsher. The hypothesis log has 263 rows including the
header. It records 184 KILL results and 78 unresolved no-cash results. All 34
priced results are KILL. Sweep after sweep found plausible timing or structural
accuracy that did not become money. Flow stories are especially vulnerable to
post-hoc interpretation because the same attack can describe absorption before
a reversal or persistence before continuation.

The weakest proposed input is schedule persistence. A regular parent order can
identify the side that will continue, not the side that will fail. Reload is
weaker still at MBP-1 fidelity and must remain diagnostic. The lack of a third
corpus makes supervised weight or threshold search unacceptable.

### Decision

The route earns one measurement because sweep 4 isolated side selection and the
measurement can be zero-fit. It does not earn another discretionary feature
campaign. A clean miss closes the entire discretionary layer.

Evidence lives in `.audit/briefs/mill-side-resolution.md`,
`.audit/mill-sweep4.json`,
`design/ENTRY_V2_DISCRETIONARY_FEATURE_CROSSWALK.md`, and
`.audit/mill-hypothesis-log.tsv`.

## B. The single cheapest decisive test

Run one paired level-local rejection test on the frozen EXPLORE cells. Use NKD
and SI as the decision assets. Report HG without letting it affect the ruling.

### Freeze the test before labels

1. Use the exact candidate-anchored detector states and Q values from the
   pending composition branch table. Do not search Q, retrace, phase, or
   detector parameters.
2. Make one observation for every detector opportunity. The observation
   contains the quieted running extreme and the opposite running extreme at the
   same timestamp. Use only cache values available at that timestamp.
3. Keep cash and all outcome magnitudes closed. Keep terminal and fade-side
   labels closed until both score definitions and their percentile thresholds
   are frozen.
4. Build empirical percentiles separately by asset, phase, and Q from the
   outcome-blind EXPLORE census. This is distribution calibration, not a
   supervised fit. No walk-forward learner is needed.

For a high extreme, the fade side is short. For a low extreme, the fade side is
long. Orient every component so that a larger value means stronger rejection
toward that fade side. Let `P` denote the empirical percentile in the frozen
asset, phase, and Q stratum.

| Component | Frozen zero-fit definition |
|---|---|
| Absorption `A` | The mean of `P(attack volume into the extreme)` and `1 - P(price extension per unit of attack)` |
| Delta divergence `D` | The mean of `P(abs attacking delta)` and `1 - P(price extension per unit of abs attacking delta)` |
| Flush `F` | The mean of `P(reversal-aligned delta after the last extreme)` and `P(two-sided flow resolving toward the fade side)` |
| Schedule `S` | `P(persistence toward the fade side - persistence toward continuation)` from signed per-minute delta over the available 10 to 30 minute window |

Use the full score `R4 = (A + D + F + S) / 4`. Freeze the fallback score
`R3 = (A + D + F) / 3` at the same time. Reload and iceberg proxies appear only
in the diagnostic table. They never enter either score.

At each detector opportunity, compute
`margin = R(quieted extreme) - R(opposite extreme)`. The flow arm takes the
first opportunity whose margin is positive and at or above the frozen 60th
percentile for its stratum. It abstains if either level lacks a complete score.
The 60th percentile is fixed because it preserves a plausible path to the 0.40
NKD and 0.35 SI coverage floors. Do not sweep it.

### Compare three arms on identical cells

Use the same detector opportunities and deadlines for every arm.

| Arm | Selection law |
|---|---|
| `D` | Detector alone takes its first eligible opportunity |
| `M` | The frozen `vs_mean` arbiter takes its first agreeing detector opportunity |
| `R4` | The flow arm takes its first opportunity that clears the paired margin rule |

Define an entry as a joint hit only when the selected extreme is terminal and
its fade side equals `sign(Delta*)` at entry. Use cell-weighted results. The
primary metric is `J = joint hits / entries`, ranked by its Wilson lower bound.
The requested arm deltas are differences in `J`. Also report
`Y = joint hits / eligible cells`, with a miss or abstention scored as zero.
`Y` prevents abstention from manufacturing accuracy.

The dispatch receipt needs one table per asset with these fields:

- eligible cells, entries, coverage, and missing-pair count;
- joint-hit rate `J` and joint-hit yield `Y`;
- the joint-hit-rate delta against `D` and against `M`;
- the Wilson lower bound for each arm;
- median and p90 delay from the selected extreme to the decision;
- each component's univariate rank separation as a diagnostic;
- the reload diagnostic;
- results by phase, with pooled cell-weighted results as the decision line.

Use a fixed-seed within-cell high-low swap null. Preserve timestamps, detector
states, phase, and coverage. Use 10,000 swaps with seed 20260827. Adjust the
maximum statistic across NKD, SI, `D`, and `M`. Use paired asset-day blocks for
the confidence interval on each delta. Event-weighted results are sensitivity
only.

This one measurement answers the question. If the paired score cannot beat both
controls without cash, no larger feature set deserves a fit.

## C. Pre-registered kill and keep bounds

No pooled win may hide an asset miss. NKD and SI must each pass.

### Full keep after round one

Freeze `R4` for one EXPLORE cash replay only if every condition passes.

1. `R4 - D` joint-hit-rate delta is at least +0.05 on NKD and at least +0.05
   on SI.
2. `R4 - M` joint-hit-rate delta is at least +0.05 on NKD and at least +0.05
   on SI.
3. The pooled paired 95 percent lower confidence bound is above zero for both
   comparisons. The adjusted swap-null p-value is at most 0.05.
4. Coverage is at least 0.40 on NKD and at least 0.35 on SI.
5. The flow calculation adds no more than 60 seconds at p90 after the detector
   fires. Total p90 delay remains at or below 20 minutes for NKD and 45 minutes
   for SI.
6. Joint-hit yield is higher than both controls. Joint-hit rate is the binding
   accuracy line, and yield is the abstention guard.

### Exactly one second iteration

Open the already frozen `R3` fallback result only if all of these conditions
hold for `R4`.

- Every asset-level delta against both controls is at least +0.03.
- At least one delta misses the +0.05 full-keep bar.
- Both pooled deltas have an adjusted p-value at most 0.10.
- Both coverage floors and both delay budgets pass.
- Absorption, delta divergence, and flush each have the correct rank direction
  on both assets. Schedule is the only component allowed to be unstable.

The second iteration only deletes schedule persistence. It keeps the same
detector states, unit weights, paired comparison, and 60th-percentile rule. Do
not change a sign, a window, a threshold, a phase rule, or an asset rule after
the first result.

`R3` must clear the full round-one bounds. Any miss closes the discretionary
layer. There is no third composite and no supervised fit.

### Immediate kill

Kill the discretionary layer after round one if any asset-level delta against
either control is below +0.03, a coverage floor fails, a delay budget fails, or
the adjusted pooled p-value exceeds 0.10. Kill it if the two assets disagree in
direction. A strong HG diagnostic cannot rescue NKD or SI.

### Cash and HOLD bounds

After a no-cash keep, freeze the exact policy before one EXPLORE cash replay.
The rule earns its single HOLD read only if both NKD and SI exceed 1500 USD per
asset-day, both drawdown orderings remain below 1000 USD, the 2 percent adverse
stress still clears both rungs, and the adjusted permutation p-value is at most
0.05. The existing one-position and 12-entry limits remain binding.

Read HOLD once without amendment. A miss on either rung or the drawdown limit
closes the discretionary layer regardless of the EXPLORE margin. Do not use the
HOLD result to change the composite, threshold, Q, or asset scope.

## D. Ranking for the NKD and SI milestone

There is one control override. If the pending `vs_mean` composition already
passes the same no-cash and cash gates, freeze it and stop. A simpler passing
control outranks every new feature.

| Rank | Route | Ruling |
|---:|---|---|
| 1 | One-shot flow arbiter | Run first because it tests the isolated missing variable on an in-flight cache. Its rank reflects low marginal cost, not high prior confidence. |
| 2 | Persistence join | This is the best next family if flow misses. It avoids terminal-extreme side inference and starts from measured late directional accuracy of 0.57 to 0.66. The NKD and SI delay budgets make a late pullback entry plausible. |
| 3 | Hazard-normalized quiet | Keep only as a detector front end for a side-resolving rule. It may repair phase-age distortion, but terminal timing alone has already failed. |
| 4 | Per-phase-only detector parameters | Lowest value. Phase 1 is already near solved by quiet, phase 2 carries the losses, and the per-phase Stage B variant moved NKD only from -44 to -3 USD per asset-day while SI stayed at +38. It did not solve side. |

If the flow test misses, run the persistence-join no-cash test first tomorrow.
Use the established move to set side and the first aligned pullback candidate to
set entry. Do not run another extreme detector, discretionary feature fit, or
pure-Q sweep before that test.

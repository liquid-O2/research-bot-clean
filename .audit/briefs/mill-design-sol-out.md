# Sol design: a selective remaining-opportunity caller with event entry

Independent Sol consultation, 2026-08-27. I did not read
`.audit/briefs/mill-design-fable.md`. This is an EXPLORE-only design. It can
kill a family and cannot promote a policy.

My bet joins a causal selective caller to an adverse-extreme entry. The caller
handles decidability and side. The event handles timing. Keeping those jobs
separate matters because a perfect side bit at a fixed clock still misses HG
and NKD.

## A. Residual gap

The best causal number below is the best individual Stage B line for that
asset. The three rows come from different families, so they are a capability
marker, not a legal mixed policy.

| Asset | Best causal Stage B line | Gap to rung | Perfect-side diagnostic |
| --- | ---: | ---: | --- |
| HG | 141.33/day, MDD 6,660 | 1,858.67/day | At 1,800 s, 1,038.98/day on 118 trades and MDD 160 |
| NKD | 53.42/day, MDD 8,095 | 1,446.58/day | At 3,600 s, 1,195.77/day and MDD 1,097.50 |
| SI | 231.25/day, MDD 5,990 | 1,268.75/day | At 1,800 s, 1,664.65/day and MDD 385 |

HG binds on timing and coverage. At the same 118-trade coverage, HG needs
1,118.64/trade, 1.93 times the fixed-clock oracle value. NKD binds on entry
placement and drawdown. Perfect side at 3,600 s is only 304.23/day short, but
the path is already 97.50 over the MDD cap. SI binds on selective side
precision. Its causal class has enough fixed-clock value, but wrong calls and
bad entry placement destroy it.

The 1,800 s oracle line gives the clean coverage arithmetic.

| Asset | Coverage | Oracle per trade | Per trade needed at that coverage | Timing multiplier still needed |
| --- | ---: | ---: | ---: | ---: |
| HG | 0.578 | 581.12 | 1,118.64 | 1.93x |
| NKD | 0.455 | 706.67 | 1,083.33 | 1.53x |
| SI | 0.480 | 1,121.45 | 1,010.53 | none |

This rules out a side-only policy. HG needs an event-timing gain even under
oracle side. NKD needs a smaller timing gain plus fewer clustered walls. SI
needs the fitted caller to retain an opportunity that is already large enough.

## B. The policy

### Policy law

Call the policy the remaining-opportunity event filter.

1. Sample one-minute completed bars. A bar closing at `t` reads the last
   trusted quote strictly before `t`. A quote stamped at `t` is future.
2. Build the LEGAL sweep-2 target on training rows only. For side `s`,
   `REM(s,t)` is the maximum frozen-law cert over later lattice times that
   already have a formed same-side CLEAR candidate. Set
   `Delta*(t) = REM(+1,t) - REM(-1,t)`. The row is sharp when
   `abs(Delta*(t)) > max(2 * cost(t), 100)`. A row without both LEGAL REM
   values is unavailable. It is not an ambiguous training label.
3. Fit two L2 logistic heads per asset. The decidability head predicts whether
   the row is sharp. The side head predicts LONG versus SHORT on sharp rows.
   Use the exact 13 causal bar inputs from sweep 2, IRLS, lambda 1.0, 100
   iterations, and no tuning. Training rows are all completed bars inside the
   asset's declaration window. Each cell has total training weight one so long
   phases do not dominate. Standardize from training means and standard
   deviations. Map a zero-variance feature to zero, and do not penalize the
   intercept. Fit on strictly earlier EXPLORE days, with at least 20 earlier
   days. Warm-up cells abstain and remain in the denominator.
4. Evaluate both heads at every completed bar inside the asset's declaration
   window. A call requires the decidability posterior at least `q*` and the
   chosen side posterior at least `p*` on two consecutive bars. The first such
   pair arms one side. There is one arm attempt per cell. A drop below either
   threshold before entry cancels the arm and the cell abstains.
5. While armed, wait for the first new adverse extreme on the called side. A
   LONG event is a formed LONG CLEAR candidate whose `entry_mid2` is strictly
   below every earlier formed LONG candidate in the cell. A SHORT event is the
   symmetric new high. Its `decision_ts_ns` must be at or before the completed
   event bar. The event must arrive before arm expiry and while at least 1,800
   seconds remain in the phase.
6. At the event bar, require the same call on that bar and its preceding bar.
   HG and NKD enter at that completed event bar. SI waits one more completed
   bar and applies the exact sweep-2 four-tick confirmation. If that
   confirmation fails, SI abstains.
7. Entry is the last trusted quote strictly before the entry bar, with
   the frozen spread plus fee. Exit is the unchanged first exact 900-dollar
   wall or phase close. Run the resulting arrivals through
   `engine.entry_v2.replay.replay`. One position per asset, one entry per cell,
   and at most 12 portfolio entries per day remain binding.

`Delta*`, certs, walls, and future event paths exist only in the training and
evaluation planes. The live prefix interface exposes bars, CLEAR formations,
candidate sides, and clocks. It exposes no oracle field.

### Frozen per-asset structure

| Asset | Declaration window after phase open | Arm expiry | Entry law | Minimum EXPLORE coverage |
| --- | --- | ---: | --- | ---: |
| HG | 900 through 3,600 s | 1,800 s | EVENT | 0.65 |
| NKD | 1,800 through 5,400 s | 1,800 s | EVENT | 0.60 |
| SI | 1,800 through 3,600 s | 1,200 s | EVENT+1, sweep-2 four-tick rule | 0.45 |

HG starts early and gets the longest useful event window because coverage is
its binding constraint. NKD can wait longer for a cleaner call, but entry must
still occur at an adverse extreme. SI gives up one bar of cash to protect the
MDD path because its 1,800 s oracle line already clears the rung.

At those coverage floors, the value required from each entered trade is:

| Asset | Cells per EXPLORE day | Trades per day at floor | Required mean per entered trade |
| --- | ---: | ---: | ---: |
| HG | 3.091 | 2.009 | 995.48 |
| NKD | 3.046 | 1.828 | 820.71 |
| SI | 3.094 | 1.392 | 1,077.44 |

These are acceptance requirements, not forecasts. Sweep 2's EVENT oracle must
show that the entry law has this value before the fitted line is worth pricing.

### Threshold calibration and selection

The only configuration grid is
`q*, p* in {0.80, 0.90, 0.95, 0.975, 0.99}`. First produce one out-of-fold
prediction stream. Each EXPLORE day uses models fitted only on earlier days.
Then apply every threshold pair to that fixed stream and simulate the whole
first-arm and event-availability law without cash. Select one pair per asset
from those out-of-fold results. A called entry counts as an error when the
LEGAL `Delta*` target at its entry bar is unavailable, ambiguous, or has the
opposite side. The first 20 days stay as zero-entry warm-up days. The coverage
floors include them. Threshold selection on EXPLORE is why this page cannot
promote.

Selection is lexicographic:

1. Entry-time error is at most 1.0 percent and its Wilson 95 percent
   upper bound from `tools/mill/sweep1.py:wilson` is at most 5.0 percent.
2. Event-entry coverage meets the asset floor in the table above.
3. Median entry time is smallest.
4. Ties choose the larger `min(q*, p*)`, then larger `q*`, then larger `p*`.

No cert, wall, PnL, MDD, or rung value enters this selection. If an asset has no
feasible threshold pair, it emits no entries and the family fails before a
dollar read. Sensitivity rows are diagnostics only. They are not priced.

### Wall and MDD accounting

The sweep-1 error grid is imperfect because it used the late crumbs target,
but its path shape is still the right warning. Two percent adversarial flips
produced MDD 963.75, 897.50, and 827.50 on HG, NKD, and SI. Five percent
produced 2,217.50, 1,345.00, and 2,110.00. That is why calibration targets 1
percent observed error. The 5 percent Wilson ceiling keeps that target
measurable on 198 to 204 cells. The separate 2 percent stress is the MDD gate.

After no-cash selection freezes one threshold pair per asset, price exactly
one policy line. Also rerun the sweep-2 adversarial stress on that frozen line.
Flip `round(0.02 * entries)` calls per asset, choosing the legal flips with the
largest cert damage, and rerun the complete opposite-side event law. A flip
with no legal opposite-side event drops. Parameters remain frozen.

The EXPLORE verdict is pre-registered as follows.

- KILL if any asset lacks a feasible threshold pair, misses its coverage
  floor, exceeds 2 percent observed entry-time error, has a Wilson upper bound
  above 5 percent, misses its dollar rung, has policy wall rate above 2 percent,
  reaches MDD 1,000 or more, or reaches MDD 1,000 or more in the 2 percent
  adversarial stress. Any occupancy overlap, more than 12 portfolio entries,
  a non-unit position, or a denominator drift is also a KILL.
- UNRESOLVED if all hard policy constraints hold but any cash margin above its
  rung is less than two asset-day block standard errors, or the shared
  asset-day block-permutation path null has max-adjusted `p > 0.05` for the
  observed MDD.
- SURVIVES_EXPLORE only if every hard condition holds, every rung margin is at
  least two block standard errors, and the path null resolves. This label
  cannot promote and does not authorize a HOLD read.

The block-permutation null cannot test total cash because that null preserves
cash. It tests whether the low-MDD ordering is unusual. The two-standard-error
day spread is the cash resolution check.

### Runner contract

The implementation needs four small boundaries. Their internals may remain
array-oriented.

```text
fit_heads(prior_rows, asset) -> DecidabilityHead, SideHead
calibrate(prior_oof_ledger, AssetPolicyParams) -> Thresholds | INFEASIBLE
first_causal_entry(cell_prefix, heads, thresholds, params) -> EntryIntent | ABSTAIN
evaluate_frozen_line(entry_intents, expected_sessions) -> EntryEvaluation
```

The evaluator receives `EntryIntent` only after the prefix code has committed
to side and timestamp. This keeps outcome arrays physically unavailable to the
caller and makes the no-oracle claim inspectable.

## C. Pending sweep-2 numbers that would change the design

1. Delta* stability changes the decision clock. Keep the bar-by-bar caller if
   at least 70 percent of cells have at most one LEGAL sign flip and 1,800 s
   agreement with the final stable sign is at least 0.75 on every asset. If
   either condition fails for an asset, move that asset's classification point
   to candidate-event bars only. Do not fit a denser clock to an unstable
   target.
2. The two-stage oracle must have room for causal loss. The chosen EVENT class
   needs at least 2,500/day on HG and 1,875/day on NKD and SI, with MDD below
   800. These are 1.25 times the rungs plus 200 dollars of MDD headroom. If any
   asset falls below either bar, do not price this fitted policy. Route to the
   level and forward-vol family in section E.
3. N3 replaces the provisional error budget. If 2 percent adversarial errors
   on the best EVENT oracle line reach MDD 1,000 on any asset, tighten that
   asset to zero observed error with a 5 percent Wilson upper bound. Its entry
   law also becomes EVENT+1. If 2 percent stays below 1,000, retain the 1
   percent calibration target and 2 percent stress above.
4. N4 decides whether any cheap detector is evidence rather than noise. Add
   one detector score to both heads only if one pre-existing family has error
   at most 0.35, Wilson upper below 0.45, and coverage at least 0.50 on every
   asset against `sign(Delta*(T_fire))`. Choose by error, coverage, delay, then
   simplicity, with no cash. If none qualifies, the 13-feature vector stays
   unchanged.
5. Stage F can make this extension unnecessary. If its one selected EVENT line
   clears every rung by two block standard errors, has MDD below 1,000, wall
   rate at most 2 percent, and passes the 2 percent adversarial stress, freeze
   that smaller fixed-tau policy. Do not build the sequential caller merely to
   be more elaborate.

## D. Three unused information sources

### 1. Prior-day level structure

Cache prior high, low, close, overnight gap, and distance to each level with an
as-of timestamp. Add the signed distances and level-touch flags to the two
heads. Validate in one EXPLORE walk-forward pass by holding the 1 percent
calibration target and 2 percent stress fixed. It earns inclusion only if it
adds at least 10 percentage points of event-entry coverage on every asset
without raising the Wilson error ceiling. This is the best next side source
because it gives an external reason for one extreme to reject while the other
continues.

### 2. The forward-vol forecast

Join only forecasts issued before the phase. Add forecast q50 and q90 range,
realized-prefix range divided by q50, and forecast regime. First measure
whether LEGAL remaining-opportunity magnitude and event availability separate
monotonically across forecast terciles. Then require at least a 10 percentage
point coverage lift at the same selective error when the new columns enter the
decidability head. This source should decide whether a cell is worth waiting
for, not call its side.

### 3. Completed cross-phase same-day state

For a later phase, expose only completed earlier-phase return, range, closing
range position, last extreme side, and candidate-count imbalance. Include
phase identity and calendar fields as controls. Validate with an asset-day
block permutation of the earlier-phase state. Require a 10 percent relative
out-of-fold log-loss reduction and at least 5 percentage points more coverage
under the same calibration and stress law in later phases. This is slower than
any lead-lag edge and remains inside the timescale doctrine.

## E. Failure routing

If the remaining-opportunity event filter misses any EXPLORE rung, the next
family is F3 level rejection normalized by the forward-vol forecast. Build the
two as-of caches once. A LONG call requires a new low within
`d in {0.05, 0.10, 0.20}` forecast q50 ranges of the prior low and a rebound of
`r in {2, 4, 8}` `ASSET_RAW_TICK` increments for `k in {1, 2}` completed bars.
SHORT is symmetric
at the prior high. Select one configuration per asset against LEGAL Delta*
error, coverage, and delay in that order. Price only the selected line under
the same frozen EVENT entry and replay law.

That route tests a new information source. It does not amend this policy, add
an exit, or call the goal unreachable. If F3 kills, F4 forecast and phase
gating is next, followed by completed cross-phase state.

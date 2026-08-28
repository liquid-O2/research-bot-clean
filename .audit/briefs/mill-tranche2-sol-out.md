# Sol tranche-two reconciliation and feasibility ruling

## Ruling

The three stamps stand. Sweep 27 remains `LEVELMEMORY-UNRESOLVED U1`,
sweep 28 remains `GENEALOGY-UNRESOLVED U1`, and sweep 29 remains
`SIZESEAT-KILL K2`.

The proposed composition has already run. Sweep 29 S2 is sweep 28's frozen
R_GEN top-four selection on the break-close lane, followed by the registered
q0.5 decline seating law. Repeating it on EXPLORE would be a second look at
the same 80 calendar-date vectors. HOLD is the only independent evaluation
plane, and S2's K2 receipt gives it no HOLD license.

The observed endpoint arithmetic has a feasible corner only under hindsight
terminal timing. That corner fails the binding portfolio event-time ledger at
$5,893.75. No causal executable mill book measured through sweep 29 occupies
the full cash, cap, and drawdown region. This does not prove that the entire
formed break-close universe is infeasible. The next session should answer that
one remaining question with an exact pathwise capacity bound.

## A. Tranche reconciliation

| Unit | Receipt facts | Ruling |
|---|---|---|
| F22, sweep 27 | NKD `+$210.156/date`, adjusted `p=0.2781`; SI `+$149.531/date`, `p=0.4778`; live cash `-$0.31/day` and `-$180.12/day`; binding MDD `$33,970` | `LEVELMEMORY-UNRESOLVED U1` is correct. Both deltas and both simultaneous upper bounds are positive, so neither K1 nor K2 fires. The live bounds fail. |
| F23, sweep 28 | Genealogy increment NKD `+$96.969/date`, `p=0.3934`, upper `$322.334`; SI `+$204.656/date`, `p=0.0660`, upper `$420.322`; R_GEN cash `+$170.42/day` and `-$17.81/day`; binding MDD `$22,046.25` | `GENEALOGY-UNRESOLVED U1` is correct. R_BASE reproduces sweep 27, both incremental and matched-control points are positive, and neither registered kill fires. |
| F24, sweep 29 | S2 cash NKD `+$215.27/day`, SI `+$102.38/day`; S2 minus S1 `+$36.438/date`, `p=0.3551`, and `+$96.156/date`, `p=0.3437`; binding MDD `$11,466.25`; q0.6 flips NKD | `SIZESEAT-KILL K2` is correct. The MDD clause fires exactly as registered. |

Sweep 29's letter order is sound. The order is `LIVE, K1, K2, U1, U0`.
LIVE and K1 are mutually exclusive by construction. LIVE requires a positive
paired point with adjusted `p <= 0.05` on both deciders. K1 requires a
non-positive simultaneous upper bound on at least one decider. A positive
point has `upper = point + c95 * SE > 0`. LIVE and K2 are also mutually
exclusive because they require MDD below and at least $1,000, respectively.
K1 and K2 can overlap, but both produce the same KILL letter. Their precedence
only names the firing clause.

The sweep 29 synthetic partition check passes all 69 checks. It enumerates 384
constructible receipts, finds zero overlap or fall-through defects after
precedence, reaches every clause, and proves that no LIVE receipt also matches
K1 or K2.

The three U0 clauses are legitimate registered residuals.

- Sweep 27 U0 covers a formed ceiling that misses a deciding rung while the
  matched deltas are not both positive and neither authorized kill fires.
- Sweep 28 U0 covers an undefined deciding increment bound or matched delta.
- Sweep 29 U0 covers an undefined deciding paired bound or delta, or a
  non-positive paired point when neither kill fires.

Each U0 parks the receipt as UNRESOLVED. None broadens the kill surface. The
builders registered them before outcomes and proved total partitions in their
self-tests. I accept them without a stamp correction.

Sweep 29 also resolves the mechanism attribution. There were two same-asset
equal-stamp groups covering four events, and magnitude reordered zero groups.
Priority was not identified. The decline clause did the work. It declined 147
arrivals, 60 later obtained a seat, and 87 were mirrors with honest forgone cash
of `-$8,872.50`. The q0.5 rule improved both deciders and cut binding MDD from
`$22,046.25` to `$11,466.25`, but the whole S2 discipline still letters K2.
The CSV quoting drift changes presentation only. The values agree, so it does
not affect any ruling.

## B. Composition ruling

One sequentially gated composition was lawful, and it has already been spent.
The power plan registered F24 before the genealogy outcome. Sweep 28 then
licensed F24 by producing positive matched deltas on both deciders and material
occupancy loss. Sweep 29 froze all of the following before reading its cash.

- Sweep 28 R_GEN fields, lambda, folds, signs, and top-four selections.
- The 461 selected break-close events and their frozen wall-or-close outcomes.
- Chronological S1 as the control.
- Magnitude ordering plus the causal q0.5 decline rule as S2.
- One shared-date sign maxT family over NKD and SI on 80 dates.
- Full chronology, occupancy, cap, seven binding ledgers, two stresses, and
  q0.4 and q0.6 non-letter neighbours.

That is exactly R_GEN plus decline seating on the break-close lane. A new unit
with those ingredients would reproduce the same qualified events and the same
date vectors after all three ingredients had been selected for attention. It
would provide no independent evidence.

The existing two-line result also has little power for its observed effects.
With `c95=1.9267`, standardized effects are `t=0.8302` on NKD and `t=0.8605`
on SI. A fixed-effect normal approximation gives only 13.6 and 14.3 percent
marginal crossing power at 80 dates. Reaching 80 percent would require about
890 independent dates for NKD and 829 for SI at the same effects and
variances. Joint maxT power is lower. Re-reading the same 80 dates does not add
power.

The lawful independent plane is the untouched HOLD split with 131 HG, 129 NKD,
and 127 SI asset-days. It permits one read of a completely frozen joint
EXPLORE survivor. S2 is not a survivor because it misses cash, MDD, stress,
power, and a neighbour. HOLD therefore remains sealed. The 2021 license can
kill only and cannot rescue or promote this composition. The 2025H2 seal
remains absolute.

## C. Feasibility inequality

For asset `j`, define the following quantities over seated trades.

```text
w_j = positive-cert rate
q_j = wall rate
g_j = mean positive cert
a_j = mean magnitude of a non-wall loss
L_j = mean wall loss magnitude, at least about $900 after the frozen costs
t_j = seated trades per asset-day
R_j = $2,000 for HG and $1,500 for NKD or SI
```

The endpoint mean per trade and the cash constraint are

```text
mu_j = w_j*g_j - q_j*L_j - (1 - w_j - q_j)*a_j
t_j*mu_j >= R_j
```

Equivalently, for fixed payoff sizes and wall rate,

```text
w_j >= (R_j/t_j + a_j + q_j*(L_j - a_j)) / (g_j + a_j)
```

The count and portfolio constraints add

```text
t_j >= ceil(R_j / mu_j), when mu_j > 0
sum_j t_j <= 12
```

At a common observed mean-cert scale, the counts are immediate.

| Mean per trade | NKD trades/day | SI trades/day | Both deciders | HG trades/day | Full portfolio need |
|---:|---:|---:|---:|---:|---:|
| $100 | 15 | 15 | 30 | 20 | 50 |
| $200 | 8 | 8 | 16 | 10 | 26 |
| $300 | 5 | 5 | 10 | 7 | 17 |

The two deciders fit under 12 only at the top of that range, and then leave two
seats for HG when HG needs seven. The full goal cannot fit at any common mean
from $100 through $300. A continuous aggregate bound is `$5,000 / 12 =
$416.67` per trade. Integer allocations make the minimum common mean $500.
For example, four HG trades at $500 and three trades on each decider at $500
use ten seats and meet the point rungs.

Sweep 29 S2 is farther away than the rounded table suggests.

| Asset | Total cash | Trades | Mean per trade | Observed trades/day | Trades/day needed at that mean |
|---|---:|---:|---:|---:|---:|
| NKD | $13,992.50 | 79 | $177.12 | 1.215 | 9 |
| SI | $6,552.50 | 57 | $114.96 | 0.891 | 14 |

Those two lines need 23 daily seats before HG receives one. Count cannot rescue
the selected effect under the portfolio law.

The wall constraint is tighter. A wall near `-$900` leaves less than $100 of
room under strict MDD `< $1,000`. Wall frequency alone cannot guarantee MDD.
Ordering, recovery, simultaneous open marks, and peak-to-later-mark giveback
also matter. Zero walls is the only distribution-free wall-rate guarantee.

An optimistic screen can allow one perfectly isolated wall over the whole
40-day book. Under that fiction, the realized wall rate must obey

```text
q_book <= 1 / (40 * sum_j t_j)
```

| Mean per trade | Both-decider trades over 40 days | One-wall rate ceiling | Full-book trades over 40 days | One-wall rate ceiling |
|---:|---:|---:|---:|---:|
| $100 | 1,200 | 0.0833% | 2,000 | 0.0500% |
| $200 | 640 | 0.1563% | 1,040 | 0.0962% |
| $300 | 400 | 0.2500% | 680 | 0.1471% |

At S2's observed per-trade means, the two deciders require 920 trades over 40
days. Their optimistic one-wall ceiling is `1/920 = 0.1087%`. The R_GEN
selected pre-seat event pool records wall rates of 23.49 percent on NKD and
34.84 percent on SI. S2 does not print a seated wall rate, so I do not infer
one. Its exact `$11,466.25` ledger already supplies the binding result.

The four endpoint scalars can look feasible and still fail the actual law.
The existing I4 oracle is the clean counterexample. It uses the true terminal
extreme bar in hindsight, so it is a diagnostic rather than a policy. I
converted its 437 entries to sweep 22's standard priced-entry type and ran the
unchanged `replay`, `replay_cash`, and `mdd_ledgers` functions.

| Asset | Win rate | Wall rate | Mean/trade | Trades/day | Cash/day | Mean minus 2 SE |
|---|---:|---:|---:|---:|---:|---:|
| HG | 98.73% | 0% | $878.31 | 2.394 | $2,102.61 | $1,818.72 |
| NKD | 100% | 0% | $1,141.24 | 2.046 | $2,335.15 | $1,913.52 |
| SI | 97.26% | 0% | $1,345.77 | 2.281 | $3,070.04 | $2,574.71 |

All 437 entries seat, occupancy rejects zero, cap rejects zero, and the
portfolio maximum is nine entries. The trade and day MDDs are at most $73.75.
The binding portfolio event-time MDD is `$5,893.75`. HG also misses its
mean-minus-two-SE rung.

The missing variable is path risk. Let `E(s)` be exact marked portfolio equity
at event time `s`. The complete feasible region also requires

```text
max over s < u of E(s) - E(u) < $1,000
```

That condition is not determined by win rate, endpoint payoff, trade count, or
wall rate. I4 proves the distinction with zero walls.

The measured USER-facing fact is narrow and consequential. At the current
causal selector's $100 to $300 per-trade scale, the cash requirement exceeds
the portfolio count budget. Its wall exposure and exact MDD then miss the risk
budget by orders of magnitude. Hindsight terminal timing reaches the required
cash, win rate, and count region, yet still misses portfolio event-time MDD by
5.89 times. No completed causal mill book satisfies all constraints. The
global pathwise capacity of the 3,497 priced break-close opportunities has not
been optimized, so I do not call the entire formed-universe region empty yet.
This is a measured interaction among the frozen entry, exit, cap, occupancy,
and MDD laws. It is not a recommendation to change any USER-owned law.

## D. Next tranche

The next session should run F25 only. F26 and F27 are contingent gates, not a
queue to dispatch in parallel.

| Order | Unit | Exact completion or kill condition | Prior |
|---:|---|---|---:|
| 1 | `F25-PATHWISE-CAPACITY` | Over all 3,497 executable priced break-close opportunities, solve for the hindsight subset that maximizes the minimum rung ratio under fixed exits, one position per asset, 12 entries per date, and every binding MDD ledger below $1,000. Run both the full three-asset objective and a labelled decider-only diagnostic. `CAPACITY-EMPTY` requires a certified integer upper bound below 1. `CAPACITY-ROOM` requires an integer witness that passes exact replay. `CAPACITY-UNRESOLVED` covers a nonzero solver gap. `CAPACITY-STOP` covers a failed reproduction or fixture. | 10% full ROOM; 20% decider-only ROOM |
| 2 | `F26-CAUSAL-SOURCE-CENSUS` | Run only after F25 ROOM. Read no outcomes. Inventory every one-minute-or-slower field available at the break-close decision, with source timestamp, coverage, and exact vector identity against F22 components, F23 genealogy, F24 magnitude and decline inputs, and the schedule interaction. `SOURCE-EMPTY` fires when no unused lawful source remains. `SOURCE` requires at least one strictly prior, non-equivalent input block. | 5% conditional on F25 ROOM to find a new source |
| 3 | `F27-ONE-SOURCE-COMPOSITE` | Run only after F26 SOURCE. Freeze the named source block without cash, add it once to R_GEN under the same lambda-1 fold law, retain top four, break-close, and q0.5 decline seating, and compare with exact S2. Use one shared-date maxT family over NKD and SI on all 80 dates. K1 fires on a non-positive simultaneous incremental upper bound, K2 on binding MDD at least $1,000, LIVE requires every standing cash, power, replay, stress, and neighbour bound, U1 covers positive underpowered increments, and U0 is the registered undefined or non-positive residual. | 5% conditional on a lawful new source to reach joint EXPLORE LIVE |

F25 should use a sparse binary optimizer with exact replay cuts. Binary `x_i`
selects each priced opportunity. Linear constraints enforce date cap and
half-open occupancy intervals. Cash constraints define `z` as the minimum
rung ratio. Trade and day drawdown constraints use running-peak variables.
After each solve, exact portfolio event-time replay identifies the worst peak
and trough and adds that violated linear cut. The unit ends only with a replayed
witness or a solver-certified upper bound. This is a deterministic capacity
bound, so it has no null, maxT family, or promotion authority.

Its controls are already available. A fixed S2 selection vector must reproduce
214 seated trades, NKD `$215.269/day`, SI `$102.383/day`, and MDD
`$11,466.25`. The I4 fixture must reproduce 437 seated trades, maximum nine per
date, and portfolio event-time MDD `$5,893.75`. A synthetic overlapping-path
fixture must turn red if the event-time cut or half-open occupancy constraint
is removed.

If F25 returns EMPTY, stop the current mill and give the USER the measured
law-interaction result. Do not run F26, invent another selector, open HOLD, or
recommend a law change. If F25 returns ROOM, spend the following unit only on
the cash-free F26 census. If F26 returns SOURCE-EMPTY, report source exhaustion
to the USER. If F27 eventually returns LIVE, freeze the complete rule before
its single HOLD read. HOLD remains the independent plane for confirmation.

I revise the program prior from 25 percent to 15 percent. I revise the prior
within the current one-minute grain, frozen outcome, and frozen break-close
universe from 10 percent to 2 percent. The positive genealogy and decline
increments preserve some weight. Three facts remove most of it. The rank signal
is near zero, the completed composition is K2, and even the zero-wall terminal
oracle fails the event-time ledger. These priors are judgments, not stop rules.

## Evidence boundary

This ruling uses `.audit/mill-sweep27.json`, `.audit/mill-sweep28.json`,
`.audit/mill-sweep29.json`, `.audit/mill-ideascreen.json`, the corresponding
sweep code, and the unchanged sweep 22 replay functions. Sweep 29's fixture
self-test passed 69 of 69 checks. The I4 event-ledger replay used EXPLORE cache
bytes already opened by its exploratory receipt. No HOLD, 2021, 2025H2,
teacher, or late outcome byte was opened. No file other than this page was
written.

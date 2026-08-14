# E1D3 MECHANICAL BASELINES (CC-M2-4.1 + CC-M2-8.2) — 2021-07-05, SI+HG+NKD, n=644

Arms: (a) `engine/port_m2/baseline_replay.py` — EPISODE_CAUSAL grouping with the FROZEN CC-M1-12 v2
parameters -> 355 episodes over 644 candidates (1.81 cand/episode) -> keep the EARLIEST member ->
TAKE iff the S13 D-071 class-census `cond_value$` clears a frozen threshold. (b) CC-M2-8.2's
YESTERDAY-POLICY, now TWO frozen predecessors: `e1d1_policy.py` and `e1d2_policy.py`, each run
unmodified on this day. (c) the reader's OWN committed rule `e1d3_policy.py` run without the
discretionary override, so the override's contribution is isolated.

Scoring seats at PHASE CLOSE per CC-M2-10.3. On this session that matters: the day's entire winner
set exits at the 07:00 TOKYO phase close.

| arm | TAKE | mean take $ | mean skip $ | winner precision | replay $ | capture |
|---|---|---|---|---|---|---|
| EARLIEST, all episodes | 355 | -53.01 | -32.96 | 0.011 | -1,456.25 | -0.292 |
| EARLIEST + cond_value >= 500 | 349 | -56.44 | -29.34 | 0.011 | -1,531.25 | -0.307 |
| EARLIEST + cond_value >= 516 | 18 | -76.94 | -43.08 | 0.000 | -686.25 | -0.138 |
| EARLIEST + cond_value >= 639 | 16 | -110.08 | -42.34 | 0.000 | -686.25 | -0.138 |
| **EARLIEST + cond_value >= 650 (BEST mechanical arm)** | 7 | -65.71 | -43.79 | 0.000 | **-546.25** | -0.110 |
| **YESTERDAY-POLICY e1d1_policy (frozen day 1)** | 6 | +210.63 | -46.42 | 0.000 | **+382.50** | 0.170 |
| YESTERDAY-POLICY e1d2_policy (frozen day 2) | 21 | +100.36 | -48.89 | 0.000 | +85.00 | 0.017 |
| e1d3_policy alone (the reader's committed rule, no override) | **0** | — | -44.02 | — | 0.00 | 0.000 |
| **READER (E1_STUDY_LEDGER, day 3)** | **5** | **+223.75** | **-46.12** | **0.000** | **+382.50** | **0.170** |

* **Reader margin over the best mechanical baseline: +$928.75** (capture +0.280 against it).
  Every mechanical arm is NEGATIVE on this session; the reader is positive.
* **Reader margin over the frozen day-1 policy: $0.00.** e1d1_policy spent the HG seat on the SAME
  candidate the reader did (HG-20210705-055113-S). This is the second time the frozen rule has
  matched the reader exactly on HG (day 1 §1).
* **Reader margin over the frozen day-2 policy: +$297.50.**
* **Reader margin over the reader's own committed rule: +$382.50** — the rule abstained on all 644
  rows and the discretionary override is the whole of the day's realised result.
* Lift is reported NA: mean(skip) = -$46.12 is not positive (the scorer's honest convention). The
  meaningful statistic is the difference, **mean(take) - mean(skip) = +$269.87**.

Per-asset pairing (where the honesty is):

| asset | reader replay $ | best-baseline replay $ | margin | note |
|---|---|---|---|---|
| HG | **+382.50** | -373.75 (cv>=650) | **+756.25** | one seat, five committed takes, four forfeited |
| SI | 0 (abstained) | -80.00 (cv>=650) | **+80.00** | NY 60s median volume 21 contracts |
| NKD | 0 (abstained) | -92.50 (cv>=650) | **+92.50** | third session, 711 candidates, zero winners |

Day-complete DP ceilings: HG $2,247.50, SI $1,522.50, NKD $1,210.00 (total $4,980.00). The reader's
capture is 0.170 against the HG session it traded and **0.077** against the full-day ceiling.

**The result that matters is not the margin.** All 8 D-021 winners of this session (HG TOKYO longs,
03:02:59-03:20:54, $1,001-$1,139) were refused by the reader's rule on five separate terms, and no
arm in this table took one of them. The day was won by abstaining from three losing sessions and
spending one seat on a directionally-correct trade that reached a third of the bar.

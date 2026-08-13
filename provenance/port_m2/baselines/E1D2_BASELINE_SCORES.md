# E1D2 MECHANICAL BASELINES (CC-M2-4.1 + CC-M2-8.2) — 2021-07-02, SI+HG+NKD, n=935

Arms: (a) `engine/port_m2/baseline_replay.py` — EPISODE_CAUSAL grouping with the FROZEN CC-M1-12 v2
parameters -> 423 episodes over 935 candidates (2.21 cand/episode) -> keep the EARLIEST member ->
TAKE iff the S13 D-071 class-census `cond_value$` clears a frozen threshold. (b) CC-M2-8.2's
YESTERDAY-POLICY: the reader's own frozen `engine/port_m2/e1d1_policy.py`, run on this day.

The yesterday-policy is reported on TWO arms because of the CC-M2-9.3 field defect: the frozen code
reads a column named `slope5m` which, under the extractor it was written against, contained the
ONE-MINUTE slope. BEHAVIOURAL replays the frozen code's actual day-1 behaviour (index built with
slope5m := sl_1); LITERAL runs the same frozen code against the corrected extractor, where `slope5m`
is now the true 5-minute slope. Both are reported; the behavioural arm is the honest baseline
(it is what the policy did), and it is also the stronger one, so the reader is compared against it.

| arm | TAKE | mean take $ | mean skip $ | winner precision | replay $ | capture |
|---|---|---|---|---|---|---|
| EARLIEST, all episodes | 423 | -65 | -56 | 0.000 | -3,436 | -0.649 |
| EARLIEST + cond_value >= 500 | 420 | -63 | -58 | 0.000 | -3,436 | -0.649 |
| **EARLIEST + cond_value >= 516 / >= 639 (BEST)** | 21 | -131 | -59 | 0.000 | **+445** | **0.084** |
| EARLIEST + cond_value >= 650 | 10 | -235 | -58 | 0.000 | -2,758 | -0.520 |
| **YESTERDAY-POLICY e1d1_policy (behavioural)** | 2 | -511 | -59 | 0.000 | **-1,023** | -0.224 |
| YESTERDAY-POLICY e1d1_policy (literal, true 5-min slope) | 1 | -930 | -59 | 0.000 | -930 | -0.204 |
| **READER (E1_STUDY_LEDGER, day 2)** | **33** | **-816** | **-32** | **0.000** | **-1,953** | -0.428 |

**Reader margin over the best mechanical baseline: -$2,398 realised (-0.512 capture).**
**Reader margin over the frozen yesterday-policy: -$930 (behavioural) / -$1,023 (literal).**
The reader lost to every arm except EARLIEST-all-episodes and EARLIEST+cv>=650.

Per-asset pairing (where the honesty is):

| asset | reader replay $ | best-baseline replay $ | margin |
|---|---|---|---|
| HG | -93 | +190 | **-283** |
| SI | -1,860 | +715 | **-2,575** |
| NKD | **0** | -460 | **+460** |

Capture denominators: panel_score charges a reader only for sessions it traded, so the reader's
pooled ceiling reads $4,564 (NKD excluded, no takes) against the baselines' $5,299. On the common
full-day ceiling of $5,299 the reader's capture is **-0.369**.

Nobody made money on 2021-07-02 by the class card: all 38 D-021 winners were SI NY LONGS and every
arm above is essentially short or indiscriminate. The one thing that separates the arms is how much
they lost, and the reader lost the most per take because its conjunction concentrated its takes on
the losing side with high confidence (9-term pool: 32 candidates, mean -$861.25, 26 wall-outs, 0
winners).

WITHIN-ROUND TREND (CC-M2-4.6), study days in sequence:

| day | reader replay $ | best mech. baseline $ | margin | yesterday-policy $ | margin |
|---|---|---|---|---|---|
| E1D1 2021-07-01 (WINDOW-TAINTED DIAGNOSTIC) | +3,003 | +623 | **+2,380** | n/a | n/a |
| E1D2 2021-07-02 (CLEAN) | -1,953 | +445 | **-2,398** | -1,023 | **-930** |
| **2-day total** | **+1,050** | **+1,068** | **-18** | | |

Two days, and the reader's cumulative margin over the best mechanical baseline is -$18 — i.e. zero,
with day 1 marked WINDOW-TAINTED by CC-M2-8.1 and day 2 clean. n = 2 days / 6 asset-clusters: no
sandwich/GEE estimate is computable yet; CC-M2-4.1's day-paired cluster-robust test remains a
ROUND-level instrument.

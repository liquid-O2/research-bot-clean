# E1D4 MECHANICAL BASELINES (CC-M2-4.1 + CC-M2-8.2) — 2021-07-06, SI+HG+NKD, n=1,268

Arms: (a) `engine/port_m2/baseline_replay.py` — EPISODE_CAUSAL grouping with the FROZEN CC-M1-12 v2
parameters -> 558 episodes over 1,268 candidates (2.27 cand/episode) -> keep the EARLIEST member ->
TAKE iff the S13 D-071 class-census `cond_value$` clears a frozen threshold. (b) CC-M2-8.2's
YESTERDAY-POLICY, now THREE frozen predecessors: `e1d1_policy.py`, `e1d2_policy.py` and
`e1d3_policy.py`, each run unmodified on this day. (c) the reader's own committed rule
`e1d4_policy.py` (identical to the ledger — there was no discretionary override on this day).

Scoring seats at PHASE CLOSE per CC-M2-10.3.

**DEFECT D16 ON RECORD (it changes how these numbers were produced, so it belongs here).** The
current TRIAGE-INDEX-V2 extractor writes TWO comment lines and renames `day_type`/`pct_range_hat`
to `day_type_so_far`/`range_vs_hat_pct`. `e1d1_policy.py`, `e1d2_policy.py` and `baseline_replay.py`
are FROZEN and parse with `open(index).readlines()[1:]` and the old column names, so run against the
day-4 index they raise (`KeyError: 'cid'`) or silently lose terms. The reader did NOT edit frozen
code: every arm below was run against `artifacts/cache/port/m2/triage/E1D4_TRIAGE_INDEX_COMPAT.tsv`
— one comment line, both column spellings, byte-identical data — and the fix is ordered on the
tooling lane.

| arm | TAKE | mean take $ | mean skip $ | winner precision | replay $ | capture |
|---|---|---|---|---|---|---|
| **EARLIEST, all episodes (BEST mechanical arm)** | 558 | +59.53 | +135.92 | 0.068 | **+5,170.00** | 0.490 |
| EARLIEST + cond_value >= 500 | 554 | +62.44 | +133.23 | 0.069 | +5,170.00 | 0.490 |
| EARLIEST + cond_value >= 516 | 25 | +500.25 | +94.30 | 0.320 | +3,192.50 | 0.303 |
| EARLIEST + cond_value >= 639 | 23 | +551.25 | +94.01 | 0.348 | +3,192.50 | 0.303 |
| EARLIEST + cond_value >= 650 | 11 | +793.30 | +96.25 | 0.455 | +2,723.75 | 0.258 |
| YESTERDAY-POLICY e1d1_policy (frozen day 1) | **0** | — | +102.30 | — | 0.00 | 0.000 |
| YESTERDAY-POLICY e1d2_policy (frozen day 2) | 11 | -722.61 | +109.52 | 0.000 | -5,158.75 | -0.489 |
| **YESTERDAY-POLICY e1d3_policy (frozen day 3)** | **1** | **+1,807.50** | +100.95 | **1.000** | +1,807.50 | 0.424 |
| **READER (E1_STUDY_LEDGER, day 4 = e1d4_policy, no override)** | **44** | **-754.01** | **+133.08** | **0.000** | **-2,953.75** | **-0.346** |

* **Reader margin over the best mechanical baseline: -$8,123.75** (day 1 +$2,380, day 2 -$2,398,
  day 3 +$928.75). Margin over frozen e1d1_policy **-$2,953.75** (it abstained on all 1,268 rows);
  over frozen e1d2_policy **+$2,205.00**; over frozen e1d3_policy **-$4,761.25**.
* Lift is reported NA (mean take is negative). The meaningful statistic is
  mean(take) - mean(skip) = **-$887.09**. 36 of 44 takes walled (0.818).
* Capture is quoted over the sessions each arm traded; against the FULL day ceiling of $10,542.50
  the reader is **-0.280** and the best mechanical arm is +0.490.

Per-asset pairing (where the honesty is):

| asset | reader replay $ | best-baseline replay $ (EARLIEST) | margin | note |
|---|---|---|---|---|
| SI | **-2,170.00** (4 seated of 32 takes) | +3,005.00 | **-5,175.00** | 76 winners on the session, all NY SHORTS; the reader took 32 NY longs |
| HG | **-783.75** (3 seated of 12 takes) | +3,910.00 | **-4,693.75** | 52 winners, all NY SHORTS; the one correctly-sided take is the 03:15:31 TOKYO short (+$182.50 close, +$3,313.75 peak) |
| NKD | 0 (abstained) | -1,745.00 | **+1,745.00** | NKD produced its first 8 D-021 winners of the round and still lost money on average (-$60.89/candidate) |

Day-complete DP ceilings: SI $4,272.50, HG $4,260.00, NKD $2,010.00 (total $10,542.50).

**THE DECOMPOSITION IS THE DELIVERABLE.** The rule that produced this table has seven terms; five
came from days 1-3 and two were fitted on this round's own three-day pool. Re-running the same rule
with the two new terms removed:

| variant | TAKE | mean take $ | winners | replay $ | capture |
|---|---|---|---|---|---|
| as committed (7 terms) | 44 | -754.01 | 0 | -2,953.75 | -0.346 |
| minus T7 (P026 jump fraction) | 55 | -173.41 | 5 | +1,056.25 | 0.124 |
| minus T6 (ext_needed <= $450) | 53 | -443.33 | 3 | -667.50 | -0.078 |
| **minus T6 and T7 (the five inherited terms)** | 80 | +11.17 | 8 | **+4,277.50** | **0.501** |
| with the direction term MIRRORED | 72 | -593.02 | 0 | -4,078.75 | -0.478 |

The two terms the reader added cost **$7,231.25** of replay, and both were selected by the criterion
ERA_NOTES §41 now strikes ("the threshold that makes all three prior days positive"). Mirroring the
direction term does not rescue the day either — the winners of 2021-07-06 are not the sign flip of
the reader's takes, they are a different object (mature-trend continuation shorts, median extreme age
3,320s, median ext_needed $750).

**One term crossed the day untouched:** runway to the binding exit >= 12,000s (P025) passes on
**136 of 136 winners**, after 94 of 94 on the three prior sessions — 230 winners, zero exceptions,
four day-complete sessions.

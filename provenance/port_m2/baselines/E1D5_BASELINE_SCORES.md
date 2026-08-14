# E1D5 MECHANICAL BASELINES (CC-M2-4.1 + CC-M2-8.2) — 2021-07-07, SI+HG+NKD, n=1,185

Arms: (a) `engine/port_m2/baseline_replay.py` — EPISODE_CAUSAL grouping with the FROZEN CC-M1-12 v2
parameters -> 545 episodes over 1,185 candidates (2.17 cand/episode) -> keep the EARLIEST member ->
TAKE iff the S13 D-071 class-census `cond_value$` clears a frozen threshold. (b) CC-M2-8.2's
YESTERDAY-POLICY, now FOUR frozen predecessors: `e1d1_policy.py`, `e1d2_policy.py`,
`e1d3_policy.py`, `e1d4_policy.py`, each run unmodified. (c) the reader's own committed calls
(`e1d5_policy.py` arm CORE+SIDE, then the CC-M2-13.4(b) pre-mortem vetoes of `e1d5_veto.py`).
All frozen arms were run against `E1D5_TRIAGE_INDEX_COMPAT.tsv` (defect D16: one comment line, both
column spellings, byte-identical data); frozen code was not edited.

Scoring seats at PHASE CLOSE per CC-M2-10.3. Day DP ceilings: SI $2,997.50, HG $3,178.75,
NKD $1,922.50 (total **$8,098.75**).

| arm | TAKE | mean take $ | mean skip $ | winner precision | replay $ | capture |
|---|---|---|---|---|---|---|
| **EARLIEST, all episodes (BEST mechanical arm)** | 545 | -40.40 | -44.75 | 0.029 | **+4,412.50** | 0.545 |
| EARLIEST + cond_value >= 500 | 544 | -39.90 | -45.16 | 0.029 | +4,412.50 | 0.545 |
| EARLIEST + cond_value >= 516 | 26 | +5.58 | -43.83 | 0.038 | +3,380.00 | 0.417 |
| EARLIEST + cond_value >= 639 | 24 | -53.96 | -42.52 | 0.042 | +2,685.00 | 0.332 |
| EARLIEST + cond_value >= 650 | 10 | -231.25 | -41.14 | 0.000 | -358.75 | -0.044 |
| YESTERDAY-POLICY e1d1_policy (frozen) | **0** | — | -42.75 | — | 0.00 | 0.000 |
| YESTERDAY-POLICY e1d2_policy (frozen) | 5 | +502.50 | -45.06 | 0.000 | +1,530.00 | 0.189 |
| YESTERDAY-POLICY e1d3_policy (frozen) | 3 | -930.00 | -40.50 | 0.000 | -1,860.00 | -0.230 |
| YESTERDAY-POLICY e1d4_policy (frozen) | 20 | -383.12 | -36.90 | 0.000 | -615.00 | -0.076 |
| **READER (E1_STUDY_LEDGER, committed calls)** | **15** | **+160.83** | **-45.36** | **0.000** | **+115.00** | **0.014** |

* **Reader margin over the best mechanical baseline: -$4,297.50.** Round to date (margin over the
  best mechanical arm, per day): +$2,380 / -$2,398 / +$928.75 / -$8,123.75 / **-$4,297.50**.
* Margin over frozen e1d1_policy **+$115.00** (it abstained on all 1,185 rows); over frozen
  e1d2_policy **-$1,415.00**; over frozen e1d3_policy **+$1,975.00**; over frozen e1d4_policy
  **+$730.00**.
* Lift is reported NA by the scorer's honest convention (the SKIP mean is negative, -$45.36). The
  meaningful statistic is mean(take) - mean(skip) = **+$206.19** — the reader's takes are the better
  half of the population for the first time since day 1, and they still contain **zero D-021
  winners**. 0 of 15 takes walled (day 4: 36 of 44).

Per-asset pairing:

| asset | reader replay $ | best-baseline replay $ (EARLIEST) | margin | note |
|---|---|---|---|---|
| SI | **+320.00** (1 seat of 8 takes) | +2,335.00 | **-2,015.00** | 28 winners: 26 NY SHORTS + 2 LONDON LONGS |
| HG | **-205.00** (1 seat of 7 takes) | +2,685.00 | **-2,890.00** | 14 winners: 11 NY SHORTS + 3 LONDON LONGS |
| NKD | 0 (abstained, 5th session running) | -607.50 | **+607.50** | 4 winners, all TOKYO LONGS at 02:01-02:02 |

## THE THREE ARMS OF THE DECLARED EXPERIMENT (CC-M2-13.4), MEASURED

| arm | TAKE | mean take $ | winners | replay $ | capture |
|---|---|---|---|---|---|
| CORE — the 5 inherited refusal terms, no side gate | 157 | -317.66 | 9 | -278.75 | -0.034 |
| CORE+SIDE — the committed policy BEFORE the vetoes | 112 | -566.89 | 0 | -2,362.50 | -0.292 |
| MIRROR — core + the OPPOSITE side gate | 25 | +796.75 | 9 | **+1,828.75** | 0.226 |
| CORE+SIGNED — T4's struck OPPOSED sign restored | 58 | -410.06 | 1 | -2,607.50 | -0.322 |
| **READER — CORE+SIDE after the pre-mortem vetoes** | **15** | **+160.83** | **0** | **+115.00** | **0.014** |

* **(b) THE VETO DELTA IS +$2,477.50 OF REPLAY AND +$727.72 OF MEAN TAKE, AT A COST OF ZERO
  WINNERS.** The 97 vetoed takes average **-$679.42** with **0 winners and a 0.732 walled
  fraction**; the 15 that stood average **+$160.83** with a 0.000 walled fraction. Both would-be
  seats were -$930 hard stop-outs (HG-20210707-048882-L, SI-20210707-050720-L) and both were
  refused by trigger V1 before the seal.
* **(c) THE SIDE ESTIMATOR PASSES 0 OF THE DAY'S 46 WINNERS.** It called LONG on SI and HG (26 and
  11 NY SHORT winners) and SHORT on NKD (4 TOKYO LONG winners): 0 for 3 on the sign, on a day when
  the mirror arm returned +$1,828.75.
* **(a) THE INHERITED REFUSAL CORE ALONE IS NEGATIVE ON THIS SESSION** (-$278.75 replay, 9 of 46
  winners retained), after +$4,277.50 on day 4. Term retention on the 46 winners: T2 runway
  **46/46**, T1 live book 44/46, T3 freshness 41/46, T4 aggression-at-magnitude 33/46, T5 magnitude
  floor **23/46**.

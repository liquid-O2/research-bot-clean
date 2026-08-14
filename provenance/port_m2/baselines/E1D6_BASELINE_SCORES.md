# E1D6 MECHANICAL BASELINES (CC-M2-4.1 + CC-M2-8.2) — 2021-07-08, SI+HG+NKD, n=1,618

Arms: (a) `engine/port_m2/baseline_replay.py` — EPISODE_CAUSAL grouping with the FROZEN CC-M1-12 v2
parameters -> **675 episodes** over 1,618 candidates (2.40 cand/episode) -> keep the EARLIEST member
-> TAKE iff the S13 D-071 class-census `cond_value$` clears a frozen threshold. (b) CC-M2-8.2's
YESTERDAY-POLICY, now **FIVE** frozen predecessors, each run unmodified against
`E1D6_TRIAGE_INDEX_COMPAT.tsv` (the D16 pinned view). (c) the reader's own committed calls
(`e1d6_policy.py` arm CORE+READER, which already includes the CC-M2-16.2 V2/V3 vetoes).

Scoring seats at PHASE CLOSE per CC-M2-10.3. Day DP ceilings: SI $4,010.00, HG $2,435.00,
NKD $4,410.00 (total **$10,855.00**).

| arm | TAKE | mean take $ | mean skip $ | winner precision | walled | replay $ | capture |
|---|---|---|---|---|---|---|---|
| **EARLIEST, all episodes / cv>=500 (BEST mechanical)** | 675 / 673 | -50.19 | -67.65 | 0.043 | 0.364 | **+1,228.75** | 0.113 |
| EARLIEST + cond_value >= 516 | 30 | -176.67 | -58.17 | 0.033 | 0.433 | -575.00 | -0.053 |
| EARLIEST + cond_value >= 639 | 28 | -170.62 | -58.42 | 0.036 | 0.393 | -187.50 | -0.017 |
| EARLIEST + cond_value >= 650 | 13 | -217.50 | -59.09 | 0.000 | 0.385 | -465.00 | -0.043 |
| YESTERDAY e1d1 (frozen) | **0** | — | -60.37 | — | — | 0.00 | 0.000 |
| YESTERDAY e1d2 (frozen) | 3 | -946.67 | -58.72 | 0.000 | 1.000 | -1,885.00 | -0.224 |
| YESTERDAY e1d3 (frozen) | 4 | +105.94 | -60.78 | 0.000 | 0.250 | -447.50 | -0.069 |
| YESTERDAY e1d4 (frozen) | 31 | -658.23 | -48.69 | 0.000 | 0.677 | -2,195.00 | -0.341 |
| YESTERDAY e1d5 (frozen) | 46 | +35.90 | -63.18 | 0.152 | 0.022 | -527.50 | -0.082 |
| **READER (E1_STUDY_LEDGER, committed calls)** | **79** | **-71.77** | -59.78 | **0.203** | 0.392 | **-988.75** | -0.091 |

* **Reader margin over the best mechanical baseline: -$2,217.50.** Round to date, per day:
  +$2,380 / -$2,398 / +$928.75 / -$8,123.75 / -$4,297.50 / **-$2,217.50**.
* Margins over the five frozen predecessors: e1d1 **-$988.75** (it abstained on all 1,618 rows),
  e1d2 **+$896.25**, e1d3 **-$541.25**, e1d4 **+$1,206.25**, e1d5 **-$461.25** — the reader beat
  two of its five frozen selves.
* **WINNER PRECISION 0.203 is the round's best on a day-complete take set** (16 D-021 winners in 79
  takes against a 5.25% base rate = **3.9x**), and the reader still lost the replay. That gap is the
  day's finding and it is a SEAT-TIMING fact, not a selection fact (§E1D6-F3).
* Lift NA by the scorer's convention (SKIP mean negative). mean(take) - mean(skip) = **-$11.99**.

Per-asset pairing:

| asset | reader replay $ | seats | best-baseline replay $ | margin | day DP ceiling |
|---|---|---|---|---|---|
| HG | **+378.75** | 3 (TOKYO -242.50, LONDON **+1,338.75**, NY -717.50) | — | — | $2,435.00 |
| SI | **-740.00** | 3 (TOKYO -930, LONDON -930, NY **+1,120.00**) | — | — | $4,010.00 |
| NKD | **-627.50** | 3 (TOKYO -955, LONDON **+1,282.50**, NY -955) | — | — | $4,410.00 |
| total | **-988.75** | 9 | +1,228.75 | **-2,217.50** | $10,855.00 |

## THE CELL-SIDE EXPERIMENT (CC-M2-16.1), MEASURED — THE DAY'S HEADLINE

**Nine ex-ante (asset, phase) cell-side calls, each committed before its cell's first candidate row.
Five cells produced D-021 winners and are scorable.**

| # | cell | truth (winner-majority side) | winners | READER | P029 | E1D6-CS |
|---|---|---|---|---|---|---|
| 3 | HG/LONDON | **SHORT** | 17 | **SHORT ✓** | LONG ✗ | NOCALL |
| 4 | SI/LONDON | **LONG** | 14 | SHORT ✗ | **LONG ✓** | SHORT ✗ |
| 5 | NKD/LONDON | **SHORT** | 24 | **SHORT ✓** | LONG ✗ | **SHORT ✓** |
| 6 | NKD/NY | **LONG** (n=1) | 1 | SHORT ✗ | SHORT ✗ | SHORT ✗ |
| 8 | SI/NY | **SHORT** | 29 | **SHORT ✓** | **SHORT ✓** | LONG ✗ |
| 0,1,2 | HG/SI/NKD TOKYO | NONE (0 winners) | 0 | LONG | LONG | LONG |
| 7 | HG/NY | NONE (0 winners) | 0 | SHORT | SHORT | SHORT |

**CELL-SIDE CALL ACCURACY: READER 3/5 = 0.600; P029 PHASE_SIDE_PRIOR 2/5 = 0.400; E1D6-CS composite
1/4 decided = 0.250.** The reader beat both of its own declared mechanical estimators, and every one
of its three correct calls was a DISCRETIONARY OVERRIDE or an agreement it had to defend against one
of them.

**THE VALUE OF THE CELL SIDE, MEASURED AS THE CC-M2-15.2 PROBE MEASURES IT (core + a cell-side gate,
phase-close seating):**

| arm | takes | mean take $ | winner precision | replay $ | capture |
|---|---|---|---|---|---|
| CORE alone (no side gate, no vetoes) | 200 | -215.28 | 0.105 | +148.75 | 0.014 |
| **CORE + the ORACLE cell side** | 50 | **+1,111.87** | **0.540** | **+5,493.75** | **0.506** |
| CORE + the READER's committed cell side | 120 | -122.76 | 0.158 | -988.75 | -0.091 |
| CORE + P029 | 148 | -218.68 | 0.101 | -3,320.00 | -0.306 |
| CORE + the READER's MIRROR | 160 | -341.60 | 0.050 | **+1,295.00** | 0.119 |
| CORE + E1D6-CS | 117 | -613.55 | 0.026 | -4,382.50 | -0.404 |

* **The oracle cell side is worth +$5,345 of replay over CORE on this one session** (capture 0.506
  against 0.014) — the phase-grain restatement of CC-M2-15.2's "$700/session" at day grain, and it
  is far larger at cell grain.
* **AND THE READER'S 0.600-ACCURATE CELL SIDE LOSES TO ITS OWN MIRROR (-$988.75 vs +$1,295.00).**
  Both facts are true at once and their reconciliation is §E1D6-F3: three of the nine cells had no
  winners on EITHER side, the reader spent a seat in all nine, and a cell-side call says which side,
  never whether the cell has a seat.

## THE V2/V3 VETO ARM (CC-M2-16.2), MEASURED

| pool | n | mean close $ | D-021 winners | walled |
|---|---|---|---|---|
| V2 sole-block (whole day) | 99 | -218.83 | 1 | 0.545 |
| V3 sole-block (whole day) | 170 | -104.15 | 10 | 0.382 |
| V2+V3 together | 20 | -226.56 | 2 | 0.350 |
| the 41 VETOED would-be TAKEs | 41 | **-221.01** | 3 | 0.220 |
| the 79 TAKEs that STOOD | 79 | **-71.77** | 16 | 0.392 |

**The vetoes removed a pool $149 worse per row than the pool they left — and moved ZERO seats, so
the replay delta is EXACTLY $0.00** (`E1D6_ARM_READER_NOVETO.tsv` replays to the same -$988.75).
Sixth-session status: V2 stays net-positive; **V3 refused 10 D-021 winners today at a sole-block
mean of -$104.15, its worst session** (five-session record: 27 rows, -$447.36, 1 winner).

## THE CC-M2-16.4 T5 REPAIR, MEASURED

The repaired floor (`v5 >= 200 OR v5 >= 8% of phase volume`) admits **545 rows the day-5 form
refused**, containing **46 of the day's 85 D-021 winners** — the defect ERA_NOTES §55 named is real
and larger than the NKD seat that exposed it. Inside the reader's own take set the repair admits 39
rows (mean -$58.21, 10 winners), and it is what created the NKD/NY seat (`NKD-20210708-048737-S`,
5m vol 26 = 17.4% of a 149-contract phase), which closed **-$955.00**. **Verdict: the repair is
WINNER-RECOVERING and VALUE-NEUTRAL-TO-NEGATIVE on its first outing** — it restores the winners the
absolute floor hid and it also restores their losing neighbours, which is what a magnitude floor
does when it is not also a side.

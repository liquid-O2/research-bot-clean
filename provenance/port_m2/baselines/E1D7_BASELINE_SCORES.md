# E1D7 MECHANICAL BASELINES (CC-M2-4.1 + CC-M2-8.2) — 2021-07-09, SI+HG+NKD, n=1,388

Arms: (a) `engine/port_m2/baseline_replay.py` — EPISODE_CAUSAL grouping with the FROZEN CC-M1-12 v2
parameters -> **616 episodes** over 1,388 candidates (2.25 cand/episode) -> keep the EARLIEST member
-> TAKE iff the S13 D-071 class-census `cond_value$` clears a frozen threshold. (b) CC-M2-8.2's
YESTERDAY-POLICY, now **SIX** frozen predecessors, each run unmodified against
`E1D7_TRIAGE_INDEX_COMPAT.tsv` (the D16 pinned view). (c) the reader's own committed calls
(`e1d7_policy.py` arm CORE+SEAT+SIDE, which includes the CC-M2-16.2 V2/V3 vetoes).

Scoring seats at PHASE CLOSE per CC-M2-10.3. Day DP ceilings: SI $3,010.00, HG $3,066.00,
NKD $5,560.00 (total **$11,636.00**). The day carries **123 D-021 winners and every one is a LONG**.

| arm | TAKE | mean take $ | mean skip $ | winner precision | replay $ | capture |
|---|---|---|---|---|---|---|
| **EARLIEST + cond_value >= 516 / >= 639 (BEST mechanical)** | 26 / 25 | -224 | -13 | 0.000 | **+535.00** | 0.046 |
| EARLIEST, all episodes / cv>=500 | 616 / 612 | -38 | +1 | 0.081 | -712.50 | -0.061 |
| EARLIEST + cond_value >= 650 | 12 | -227 | -15 | 0.000 | -1,577.50 | -0.136 |
| YESTERDAY e1d1 (frozen) | **0** | — | -16 | — | 0.00 | 0.000 |
| YESTERDAY e1d2 (frozen) | 5 | +41 | -17 | 0.000 | -238.75 | -0.021 |
| YESTERDAY e1d3 (frozen) | 4 | -260 | -16 | 0.000 | -430.00 | -0.140 |
| YESTERDAY e1d4 (frozen) | 9 | -524 | -13 | 0.000 | -38.75 | -0.003 |
| YESTERDAY e1d5 (frozen) | 26 | +192 | -20 | 0.077 | **+310.00** | 0.027 |
| YESTERDAY e1d6 (frozen) | 81 | -407 | +8 | 0.000 | **-5,136.25** | -0.441 |
| **READER (E1_STUDY_LEDGER, committed calls)** | **55** | **+282.27** | -29 | 0.109 | **-432.50** | -0.037 |

* **Reader margin over the best mechanical baseline: -$967.50.** Round to date, per day:
  +$2,380 / -$2,398 / +$928.75 / -$8,123.75 / -$4,297.50 / -$2,217.50 / **-$967.50** — the smallest
  loss of the four losing days and the third-best margin of the round.
* Margins over the six frozen predecessors: e1d1 **-$432.50** (it abstained on all 1,388 rows),
  e1d2 **-$193.75**, e1d3 **-$2.50**, e1d4 **-$393.75**, e1d5 **-$742.50**, e1d6 **+$4,703.75**.
  The reader beat ONE of its six frozen selves — and the one it beat by $4,700 is yesterday's, whose
  committed cell-side table pointed the wrong way on a session that inverted.
* **The reader's take set has a POSITIVE mean (+$282.27 vs a -$29 skip pool) for the second session
  running** and still loses the replay: 55 takes, 6 D-021 winners (precision 0.109 against an 8.9%
  base rate = 1.23x — the round's worst precision-vs-base on a day whose base rate was high).
* Lift NA by the scorer's convention (SKIP mean negative). mean(take) - mean(skip) = **+$311**.

Per-asset pairing (this is where the margin lives):

| asset | reader replay $ | seats | best-baseline replay $ | margin | day DP ceiling |
|---|---|---|---|---|---|
| HG | -130.00 | 1 (NY 13:00:18 L) | **+1,423.75** | **-1,553.75** | $3,066.00 |
| SI | **+470.00** | 1 (NY 13:09:22 L) | -415.00 | **+885.00** | $3,010.00 |
| NKD | -772.50 | 2 (LONDON -955.00, NY +182.50) | -472.50 | -300.00 | $5,560.00 |
| total | **-432.50** | 4 | +535.00 | **-967.50** | $11,636.00 |

**The entire margin is HG**, and it is a STAGE-1 loss, not a side loss or an entry loss: the frozen
EARLIEST+cv>=516 arm banked +$1,423.75 out of HG/LONDON, the cell the reader's seat rule refused at
`rv1800 112.7`. On SI the reader beat every baseline (+$885 over the best) with a single seat.

## THE THREE-STAGE DECOMPOSITION, PRICED AGAINST ITS PARTS (CC-M2-17.1's own question)

| arm | takes | mean take $ | winner precision | replay $ | capture |
|---|---|---|---|---|---|
| CORE alone (no gate) | 184 | +33 | 0.109 | -512.50 | -0.044 |
| CORE + STAGE 1 only (reader SEAT calls) | 100 | +189 | 0.100 | **-1,600.00** | -0.138 |
| CORE + STAGE 2 only (reader SIDE calls, all 9 cells = the day-6 arm) | 103 | +60 | 0.136 | **-1,846.25** | -0.159 |
| **CORE + BOTH (the committed calls, pre-veto)** | 70 | +231 | 0.100 | **-432.50** | -0.037 |
| READER = the same after V2/V3 | 55 | +282 | 0.109 | **-432.50** | -0.037 |
| CORE + reader SEAT + reader MIRROR side | 45 | +74 | 0.089 | -236.25 | -0.020 |
| CORE + P029 phase prior (no seat gate) | 94 | +216 | 0.149 | **+851.25** | 0.073 |
| CORE + **ORACLE seat** (which cells hold winners) | 151 | +41 | 0.192 | -268.75 | -0.023 |
| CORE + **ORACLE side** | 175 | +340 | 0.160 | **+2,030.00** | 0.174 |
| CORE + **ORACLE seat + ORACLE side** | 83 | +635 | 0.337 | **+2,687.50** | 0.231 |
| CORE + reader seat + ORACLE side | 103 | +325 | 0.107 | +1,043.75 | 0.090 |
| CORE + ORACLE seat + reader side | 80 | +137 | 0.253 | -1,500.00 | -0.129 |

**READ THIS TABLE IN THREE STATEMENTS.**
1. **THE COMPOSITION IS WORTH MORE THAN EITHER OF ITS PARTS AND THE PARTS ARE BOTH NEGATIVE**:
   stage 1 alone -$1,600, stage 2 alone -$1,846, both together -$432.50 (+$1,168 over stage 1 alone,
   +$1,414 over stage 2 alone, +$80 over no gate at all). Composing two individually value-destroying
   filters produced the least-bad arm of the reader's family. That is a real, if thin, measurement of
   CC-M2-17.1's central claim — and it is measured on a day when BOTH stages were wrong more often
   than right, which is the strongest form of the observation available today.
2. **THE SIDE REMAINS THE BINDING STAGE.** Oracle side alone is worth **+$2,542 over CORE**; oracle
   seat alone is worth **+$244**. With the side known, knowing the seats too adds a further $657;
   with the seats known, the reader's own side destroys $1,500. The CC-M2-15.2/CC-M2-16.1 ordering
   survives another session: **side first, feasibility second.**
3. **THE ORACLE COMPOSITION CAPTURES 0.231 OF THE DAY** — far below day 6's 0.506, on a day with 123
   winners. The reason is that 68 of them sit in NKD/TOKYO with certificates up to $3,845 in a book
   the refusal core mostly cannot trade (T1 passes on only 56 of the day's 123 winners).

## THE VETO FAMILIES (CC-M2-17.4's split, and the third $0.00 in a row)

15 rows carried V2/V3 with the core and BOTH cell gates admitting them. **Vetoed pool mean
+$41.67 with ONE D-021 winner refused (SI-20210709-054305-L, +$1,020.00); standing pool +$282.27
with 6. Replay delta: exactly $0.00 — no veto fired on a seat-spender, for the third consecutive
session.** V3 (P018) alone accounts for 14 of the 15 and its refused pool is **positive**: this is
the second session running in which V3 refuses winners and money (2021-07-08: 170 sole-blocks,
-$104.15, ten winners refused). **V3's retention under CC-M2-16.2 is now the ledger's weakest
standing claim.**

## GRADE CALIBRATION (CC-M2-4.4)

| | A | B | C |
|---|---|---|---|
| TAKE | — (0) | **+$355.57** (42) | +$45.48 (13) |
| SKIP | **-$955.00** (18) | -$427.41 (343) | +$129.03 (972) |

**Monotone inside the TAKEs for the first time in the round (B > C, n=42/13)** — and still inverted
on the SKIP pool, and the A band is empty of winners for a FOURTH consecutive session (all 18 A-grade
rows are -$955 NKD walls). The rebuild direction named in ERA_NOTES §69 stands: the band selects rows
whose runway is long because the phase just opened and whose rv is high because the move already
happened.

# E6 TEACHER ROUND — THE DRAW + COVERAGE TABLE (committed with the draw, D-076.2/D-087)

Spec: `design/PORT_TEACHER_ROUND_SPEC.md` (frozen 2026-08-15, conformance receipt in §2).
Reader: Opus, pinned max effort. Round ids: `E6-STUDY-D1..D3`, `E6-BLIND-D1..D3`.
Instrument: E6 index + on-demand renderer at HEAD; `episode_round.py` (grain), `ribbon.py` (raw tape),
`triage_index.py` V4 (the per-episode delta row), `retrieve.py` (prior studied history only).

## 1. THE DRAW RULE (pinned BEFORE any sheet was opened; deterministic, no outcome input)

STUDY (3 days, stratified-chronological per D-076.1):
- **R1 strata** = month blocks of the E6 STUDY block (2024-01-02 .. 2024-04-18, 77 session dates):
  S1 = January (22), S2 = February+March (41), S3 = April 1-18 (14).
- **R2 regime target per stratum** = LOW / MID / HIGH — one day per trailing-vol tercile of the era, so the
  study set covers the era's whole vol range and its highest-vol day sits directly adjacent to the BLIND
  block. Terciles are cut on **ATR14_usd (trailing, causal)** within E6, per asset; the day's label is the
  modal label across the three assets.
- **R3 release coverage**: at least one drawn day must carry a scheduled high-impact release (the D-077
  ±10min compliance veto has to be exercised in study, not first met in blind). The constraint is discharged
  at S2, the stratum holding the most release days.
- **R4 within-stratum choice**: among days meeting (stratum ∧ regime target ∧ untainted ∧ R3 when it binds),
  take the day whose **3-asset roster total is closest to the MEDIAN of that eligible set** — never the
  largest or the smallest, so volume is not cherry-picked in either direction; ties → earliest date.
- **R5 order** S1 → S2 → S3.

BLIND (3 days): the **first three BLIND-block dates, contiguous and chronological** (D-036/D-058: blind is
the block that follows study, no gap, no selection of any kind). Day-complete, all three assets.

TAINT CHECK: `provenance/port_m2/USED_CASE_LEDGER.tsv` carries **0 E6 rows** — the whole era is virgin;
no warm-up case, no prior study or blind row touches any drawn day. Checked at draw time.

## 2. THE DRAWN DAYS

| round | date | dow | vol regime (ATR14 tercile) | release | SI | HG | NKD | candidates | episodes |
|---|---|---|---|---|---|---|---|---|---|
| E6-STUDY-D1 | 2024-01-18 | Thu | LOW  | — | 368 | 382 | 485 | 1,235 | 584 |
| E6-STUDY-D2 | 2024-03-20 | Wed | MID  | **FOMC decision day** | 694 | 509 | 267 | 1,470 | (built at day open) |
| E6-STUDY-D3 | 2024-04-16 | Tue | HIGH | — | 800 | 777 | 626 | 2,203 | (built at day open) |
| E6-BLIND-D1 | 2024-04-19 | Fri | HIGH | — | 676 | 755 | 809 | 2,240 | (built at day open) |
| E6-BLIND-D2 | 2024-04-22 | Mon | HIGH | — | 555 | 669 | 485 | 1,709 | (built at day open) |
| E6-BLIND-D3 | 2024-04-23 | Tue | HIGH | — | 415 | 512 | 294 | 1,221 | (built at day open) |

Rule trace (audit): S1 eligible = 18 Jan LOW days, median total 1,201 → 1,235 (0118) and 1,167 (0119) tie at
|Δ|=34 → earliest = **0118**. S2 eligible = 14 Feb-Mar MID days, median 1,380; R3 binds, and of the two
release days in the stratum (0308 Employment Situation 1,815; 0320 FOMC 1,470) the closer to median is
**0320**. S3 eligible = 5 April HIGH days, median 2,203 → exactly **0416**. Days-of-week land distinct
(Thu/Wed/Tue) without a constraint being needed.

## 3. COVERAGE TABLE (round days vs the era's own distribution — representativeness measured, D-076.2)

Era E6 = 128 session dates (77 STUDY / 51 BLIND), 169,326 candidates.

| dimension | E6 (all 128 d) | E6 STUDY block (77 d) | the 3 STUDY days | E6 BLIND block (51 d) | the 3 BLIND days |
|---|---|---|---|---|---|
| vol regime LOW / MID / HIGH | 35% / 27% / 38% | 58% / 35% / 6% | **33% / 33% / 33%** | 0% / 14% / 86% | 0% / 0% / 100% |
| months covered | Jan-Jun | Jan-Apr | Jan, Mar, Apr | Apr-Jun | Apr |
| day-of-week | ~20% each | ~20% each | Thu, Wed, Tue | ~20% each | Fri, Mon, Tue |
| scheduled release days | 19/128 = 15% | 12/77 = 16% | **1/3 = 33%** | 7/51 = 14% | 0/3 = 0% |
| median 3-asset roster/day | 1,253 | 1,323 | 1,470 | 1,209 | 1,709 |
| REVERSAL-CONFIRMATION share | 89.6% | — | 85.6-92.2% | — | 91.6-92.4% |
| NEWS-WINDOW share | 3.8% | — | 2.2-8.7% | — | 1.2-2.9% |
| RECLAIM / OPEN-DYNAMICS | 3.8% / 2.2% | — | 2.3-4.1% / 1.0-2.0% | — | 2.3-4.1% / 1.9-3.4% |
| realized 3-asset session range, $ | (blind block not read) | median $7,512 | $6,488 / $8,925 / $10,144 (32nd / 73rd / 81st pctile of the study block) | NOT READ (outcome) | NOT READ |

**NAMED CAVEATS ON THIS DRAW** (they are structure, not selection):

1. **The era's own walk-forward boundary crosses a regime break.** E6's STUDY block is 58% LOW / 6% HIGH
   trailing vol; its BLIND block is 86% HIGH. This is the spring-2024 metals repricing — the D-084 "2024
   trend onset" break — sitting exactly on the 60/40 study/blind split. The round is therefore an
   **adaptation test by construction**: everything taught on the study days is taught in a quieter tape than
   the one it is tested on. R2 exists to soften this (study day 3 is drawn from the HIGH tercile, the last
   week before the boundary), but it cannot remove it. No day-choice inside E6 can: the era has only 5 HIGH
   study days and they are all in the final week.
2. **The three BLIND days are all HIGH-vol April days.** That is what "the three days after the boundary"
   are; it is representative of the BLIND block (86% HIGH) and not of the era as a whole.
3. **Release coverage is 1/3 in study and 0/3 in blind.** Compliance (D-077 ±10min, incl. held-into) is
   exercised on the FOMC study day; per CC-M2-24.4a the blind round will report compliance coverage as
   *zero scheduled releases in the blind block* — the flags still ride as a hard veto, they simply have
   little to bind on (jobless claims at 12:30Z on 2024-04-25 is outside the drawn days).
4. **Realized offer of the study days runs slightly rich** (32nd/73rd/81st percentile of the study block, mean
   pctile 62): the median-volume rule selects on ROSTER SIZE, which correlates with realized range. Named,
   not corrected — correcting it would require selecting days on their outcomes.
5. Stratification used **causal features only** (trailing ATR14, month, day-of-week, release calendar, roster
   volume). No realized-outcome column entered the draw; the realized-range row above is reported for the
   study block *after* the draw was fixed, and was never computed for the blind block.

## 4. WHAT IS SEALED

No S14 appendix, no outcome, no oracle object of any BLIND day is opened by the reader at any point. The
blind days are decided from the same instrument the study days were read with, sealed per day, and scored by
the orchestrator afterwards.

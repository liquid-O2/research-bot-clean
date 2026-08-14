# E1D8 MECHANICAL BASELINES (CC-M2-4.1 + CC-M2-8.2) — 2021-07-12, SI+HG+NKD, n=949

Arms: (a) `engine/port_m2/baseline_replay.py` — EPISODE_CAUSAL grouping with the FROZEN CC-M1-12 v2
parameters -> **485 episodes** over 949 candidates (1.96 cand/episode) -> keep the EARLIEST member ->
TAKE iff the S13 D-071 class-census `cond_value$` clears a frozen threshold. (b) CC-M2-8.2's
YESTERDAY-POLICY, now **SEVEN** frozen predecessors, each run unmodified against
`E1D8_TRIAGE_INDEX_COMPAT.tsv` (the D16 pinned view). (c) the reader's own committed calls
(`e1d8_policy.py` arm CORE+SEAT = the moment core + V2 + the rolling `unspent_bind` state).

Scoring seats at PHASE CLOSE per CC-M2-10.3. Day DP ceilings: SI $3,260.00, HG $2,322.50,
NKD $1,897.50 (total **$7,480.00**). The day carries **47 D-021 winners (4.95%) and 44 of the 47
are LONGS** — SI 36, HG 9, NKD 2.

| arm | TAKE | mean take $ | mean skip $ | winner precision | replay $ | capture |
|---|---|---|---|---|---|---|
| **EARLIEST + cond_value >= 516 (BEST mechanical)** | 26 | +140 | -25 | 0.077 | **+3,458.75** | 0.462 |
| EARLIEST + cond_value >= 639 | 23 | +148 | -24 | 0.087 | +3,363.75 | 0.450 |
| EARLIEST + cond_value >= 650 | 10 | +162 | -22 | 0.100 | +2,910.00 | 0.389 |
| EARLIEST, all episodes / cv >= 500 | 485 / 482 | -39 | -0 | 0.029 | +2,505.00 | 0.335 |
| YESTERDAY e1d1 (frozen) | 1 | -930 | -19 | 0.000 | -930.00 | -0.285 |
| YESTERDAY e1d2 (frozen) | 4 | -661 | -17 | 0.000 | -1,585.00 | -0.284 |
| YESTERDAY e1d3 (frozen) | 0 | — | -20 | — | 0.00 | 0.000 |
| YESTERDAY e1d4 (frozen) | 11 | +123 | -22 | 0.182 | -627.50 | -0.112 |
| YESTERDAY e1d5 (frozen) | 47 | -658 | +13 | 0.000 | -2,836.25 | -0.508 |
| YESTERDAY e1d6 (frozen) | 87 | -595 | +38 | 0.000 | -4,000.00 | -0.535 |
| **YESTERDAY e1d7 (frozen)** | 19 | +994 | -41 | **0.421** | **+1,952.50** | 0.350 |
| **READER (E1_STUDY_LEDGER, committed calls)** | **72** | -295 | +3 | 0.111 | **+422.50** | 0.130* |

(*capture is computed over the asset-sessions the reader actually traded — SI only. Against the
full day ceiling of $7,480 the reader's capture is 0.056.)

* **Reader margin over the best mechanical baseline: -$3,036.25.** Round to date, per day:
  +$2,380 / -$2,398 / +$928.75 / -$8,123.75 / -$4,297.50 / -$2,217.50 / -$967.50 / **-$3,036.25**
  — **two days won of eight, -$17,731.75 cumulative.**
* Margins over the seven frozen predecessors: e1d1 **+$1,352.50**, e1d2 **+$2,007.50**, e1d3
  **+$422.50**, e1d4 **+$1,050.00**, e1d5 **+$3,258.75**, e1d6 **+$4,422.50**, e1d7 **-$1,530.00**.
  **The reader beat SIX of its seven frozen selves** — its best predecessor record of the round —
  and lost only to yesterday's, whose committed cell-side table happened to point LONG into the NY
  cells this session while today's pointed SHORT.
* **The take set is negative-mean (-$295) for the first time in three sessions**, and the reason is
  one seat: SI/TOKYO closed -$542.50 and SI/LONDON -$505.00 against SI/NY's +$1,470.00.

## THE ARM TABLE — WHAT EACH STAGE DID (CC-M2-19.2's ordering, tested)

| arm | takes | winner precision | mean take $ | replay $ | capture |
|---|---|---|---|---|---|
| CORE alone (T1..T5) | 145 | 0.097 | -216 | **+1,172.50** | 0.157 |
| **READER = CORE + V2 + R2b rolling capacity** | 72 | 0.111 | -295 | **+422.50** | 0.130 |
| READER without V2 | 78 | 0.115 | -236 | +422.50 | 0.130 |
| READER + V3 applied (the advisory arm) | 61 | 0.049 | -448 | +422.50 | 0.130 |
| **READER with the four would-abstain cells removed** | 68 | 0.103 | -341 | **+965.00** | 0.296 |
| CORE + the committed SIDE calls | 95 | **0.000** | -596 | **-4,000.00** | -0.535 |
| CORE + SEAT + SIDE | 53 | 0.000 | -651 | -2,062.50 | -0.633 |
| **MIRROR of the committed side calls** | 19 | **0.421** | +698 | **+1,460.00** | 0.448 |
| CORE + R1 `rv1800 >= 250` (pre-registered, NOT traded) | 119 | 0.143 | -171 | **-1,658.75** | -0.222 |
| CORE + INVERTED R1 `rv1800 < 250` (NOT traded) | 35 | 0.000 | -177 | +207.50 | 0.028 |
| CORE + **ORACLE cell side** | 34 | 0.500 | +1,038 | **+2,310.00** | 0.414 |
| READER + **ORACLE cell side** | 12 | **0.667** | +1,355 | +1,965.00 | 0.603 |

**FIVE STATEMENTS FROM THIS TABLE.**

1. **THE PRE-REGISTRATION HELD OUT OF SAMPLE.** `rv1800 >= 250` at the row — which holds 45 of this
   day's 47 winners (95.7%) and 92.8% of the round's 484 — costs **-$2,831.25 against CORE** when
   run as a gate, exactly as the seven-session pre-registration said it would (-$7,562.50 there).
   Three sessions in a row have now produced the same result for the same class of object.
2. **AND THE DISCIPLINE HELD TOO.** The INVERTED form, worth +$8,923.75 over the seven training
   sessions and the best arm on that board, scores **+$207.50** here — *worse than CORE*. It was
   pre-registered as NOT TRADED precisely because an inversion minted on its own sample is the P009
   error. That refusal was worth $965 relative to trading it.
3. **THE SIDE CALLS WENT 0-FOR-4 AND THE MIRROR WENT 4-FOR-4.** Gating on them costs -$5,172.50
   against the mirror and -$5,172.50 against CORE. **The declared override — running no side gate —
   is what saved the day**, and it produced the day's only winning seat on the exact cell
   (SI/NY) where the committed side call was wrong.
4. **R2b, THE TERM THE READER DID TRADE, COST $750.** Its mechanism is falsified on the day's own
   evidence: it refused **all 11 of the day's HG and NKD winners** (HG/NY's nine winners carry
   `unspent_bind` 180.7-224.4 and paid $1,001-$1,120), and the one cell it admitted — SI/NY, 33
   winners — it admitted only because SI's fvol is REFUSED and the term is silent (defect D22).
   The capacity arithmetic is a mean-reversion prior and it is an anti-signal when the range expands
   (ERA_NOTES §21, restated at row grain).
5. **ABSTENTION SCORED POSITIVE FOR THE FIRST TIME.** ERA_NOTES §70.4 registered cell-level
   abstention as a decision the ledger had never scored. Removing the four cells the reader marked
   `would-abstain` at commit time is worth **+$542.50** (+$422.50 -> +$965.00, capture 0.130 ->
   0.296), and the cell it removes is SI/TOKYO — the 0-for-7 cell whose seat walled.

## THE VETO FAMILIES — A FOURTH CONSECUTIVE $0.00

| family | rows on core+seat-admitted candidates | mean $ | winners refused | replay delta |
|---|---|---|---|---|
| V2 (APPLIED) | 6 | **+467.92** | 1 | **$0.00** |
| V3 (ADVISORY, not applied) | 12 | **+431.46** | 5 | **$0.00** |

Both families refused money and winners this session, and neither moved a seat: `replay_inert=1`
for the **fourth consecutive session** (days 6, 7, 8 at $0.00; day 5's +$2,477.50 remains the only
session where a veto ever changed a seat's money). **V3's retention is now indefensible: over its
last three sessions it has refused 10, 5 and 5 winners at a positive mean and moved $0.00 of
replay.** V2's positive sole-block record is now equally hollow at the seat.

## GRADE CALIBRATION (CC-M2-4.4)

| | A | B | C |
|---|---|---|---|
| TAKE | — (0) | -$301.88 (n=56, w=8) | -$271.41 (n=16, w=0) |
| SKIP | — (0) | **+$122.34 (n=219, w=32)** | -$37.42 (n=658, w=7) |

**A FIFTH CONSECUTIVE SESSION WITH AN EMPTY A BAND — and this time the band is empty of ROWS, not
just of winners**: no row of 949 reaches `sigma_to_exit >= $2,500`. Inside the TAKEs the grade is
flat-to-inverted again (B -$302 vs C -$271); on the SKIP pool it is inverted (B > C) with 32 of the
day's 47 winners sitting in the SKIP-B cell. Over five sessions the grade has been monotone inside
the TAKEs exactly once. It remains disqualified as a judge-aux target (CC-M2-10.5) and ERA_NOTES
§79's rebuild direction is now confirmed twice: `rv1800 * sqrt(runway)` is the right FEASIBILITY
product and the wrong CONFIDENCE reading.

## THE THREE SEATS

| cid | clock | side | close $ | peak $ | MAE | walled |
|---|---|---|---|---|---|---|
| SI-20210712-010922-L | 03:02:02 | LONG | **-542.50** | +670.00 | 50.00 | **1** |
| SI-20210712-027269-L | 07:34:29 | LONG | **-505.00** | **+1,295.00** | 775.00 | 0 |
| SI-20210712-046931-L | 13:02:11 | LONG | **+1,470.00** | +1,745.00 | 325.00 | 0 |

**All three pre-mortems named a mechanism and two of the three fired as written.** Seat 1's
pre-mortem named the clock and the $50 of room; it walled with a $50 MAE and a +$670 peak — the
give-back, not the clock. Seat 2's pre-mortem named the trigger "a print below 26.06 says the
absorption failed"; the MAE of $775 is exactly that print, and the trade then rallied to +$1,295
before the LONDON phase close priced it at -$505 — **the give-back channel (§35/§39.5) taking
$1,800 of round-trip on one seat.** Seat 3's pre-mortem named `rv_collapse 7.41` as the wall marker;
it was the day's winner at +$1,470 with a $325 MAE, so the marker was wrong on the one row where it
was tested.

## WINNER ANATOMY (the day's 47)

`T1 45/47 · T2 47/47 · T3 30/47 · T4 34/47 · T5 42/47 · R1 (rv1800>=250) 45/47 · R2b 36/47`
Core-admitted (all five terms): **17 of 47.** Winner `rv1800` min 241.4 / median 406.6 / max 576.2;
minimum winner `runway_phase` 13,258s — **P025's 12,000s floor holds 47/47 again**, one session
after it broke at 361/361.

Winner clusters: **SI/NY 33 LONGS 13:24:50-16:10:51** ($1,020-$1,670, median $1,245);
**HG/NY 9 LONGS 13:32:45-14:15:37** ($1,001-$1,120); **NKD/NY 2 LONGS 13:02-13:04**; **SI/TOKYO 3
SHORTS 03:11:43-03:19:02** ($1,007-$1,057). Every winner of the day is in TOKYO or NY; LONDON is
empty on all three assets, on a session where the reader spent a LONDON seat.

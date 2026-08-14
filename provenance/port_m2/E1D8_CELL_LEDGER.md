# E1 STUDY DAY 8 — THE PER-CELL LEDGER (the FINAL study day of the E1 round)

Reader: opus-discretionary, fresh context (CC-M2-4.2). Draw: the next chronological STUDY session
per asset strictly after 2021-07-09, warm-ups excluded (CC-M2-8.1) — **SI/HG/NKD 2021-07-12**
(Monday), 949 candidates (SI 327, HG 304, NKD 318). `USED_CASE_LEDGER` carries **0** prior hits on
20210712. `short_day=0`, `observed_close=82799`. **No scheduled release falls inside this session**
(`sched_next_in` 91,644-138,582s against `runway_sess` <= 82,781s) — the CC-M2-12.3 leading
separator says a day-1-like regime, and its limit is on record too: it is a fact about WHICH
patterns apply, never a direction compass.

**WHAT THIS FILE IS.** CC-M2-19 corrected the three-stage stack in two ways and this day runs the
corrected forms: **(1) stage 1 is a ROLLING PER-ROW state, not a per-cell call** (day 7's cell-open
anchor inverted: NKD/TOKYO opened at `rv1800` 53.0 and paid 68 winners four to eight hours later);
**(2) the composition order is SIDE > SEAT > MOMENT** — so the SIDE is committed first, cell by
cell, before that cell's first candidate row. Nine SIDE calls with named evidence are below; the
rolling seat state is logged at every row by the policy, not fixed here.

**MECHANIC (as-of stepper end-to-end).** `triage_index.py --drive-step 300 --drive-out E1D8_DRIVE`
(277 verified prefixes) and `engine/port_m2/e1d8_cellbrief.py --cell K`, which emits a panel built
from rows with `sec < cell_open_sec` PLUS the cell's own first-second row (the row being called),
and refuses to build a panel if any foreign row sits at the cut. Cells are consumed IN
CHRONOLOGICAL ORDER and each call is committed before the next panel is requested.
Accepted exposure, declared as on days 6-7: the ORDERED LIST of (asset, phase, first-candidate
second) is generation-side metadata carrying no price and no outcome.

**TAINT.** `CLEAN;AS-OF-PREFIX` on every row. No `forecast_*.tsv` / `truth_*.tsv` was opened at any
point (the D19 exposure class avoided by construction); the three forecaster columns are `.` on all
949 rows, as CC-M2-17.2 ruled they would be for every 2021 session.

---

## PART A — THE PRE-REGISTRATION, ON SEVEN SESSIONS, BEFORE ANY DAY-8 ROW WAS SEEN

Receipts: `engine/port_m2/e1d8_stage12.py --backtest` (pooled row pool + cell pool) and
`engine/port_m2/e1d8_prereg.py` (one-position phase-close replay of whole policies). Every
threshold below was settled on the POOLED POOL and never on a replay (ERA_NOTES §33/§41).

### A1. STAGE 1 IN ITS CORRECTED ROLLING FORM — 8,077 rows, 484 D-021 winners, base 5.99%

| rolling state (evaluated at the candidate's OWN row) | rows | winners | recall | win% | lift | mean $ |
|---|---|---|---|---|---|---|
| R1 `rv1800 >= 250` | 6,092 | 449 | 0.928 | 7.37% | 1.23x | -10.77 |
| R1 + R2 `unspent_sess >= 500` | 3,783 | 290 | 0.599 | 7.67% | 1.28x | -31.29 |
| **R2b `unspent_bind >= 1000` (with R1)** | 2,540 | 222 | 0.459 | **8.74%** | **1.46x** | **+9.17** |
| R1 + R2 + P025 `runway >= 12,000s` | 3,116 | 281 | 0.581 | 9.02% | 1.50x | -28.37 |

`unspent_bind` is the ERA_NOTES §77 field — the BINDING row's unspent expected move (the phase row
when the exit is a phase close, the session row when it is the session close). §77 asked which
coverage row binds and named it as untested. **The pooled answer is the BINDING row at the full
$1,000 D-021 bar**: it is the only arm in the whole sweep with a POSITIVE mean certificate.

### A2. THE FINDING THAT DECIDED THE DAY'S POLICY: A CONCENTRATOR IS NOT A GATE, AND NOW IT IS MEASURED AT THE SEAT

`e1d8_prereg.py`, one-position phase-close replay over the same seven sessions:

| arm | takes | precision | replay $ | capture |
|---|---|---|---|---|
| CORE (T1..T5) | 1,685 | 0.106 | +5,711.25 | 0.096 |
| CORE + R1 `rv1800(row) >= 250` | 1,425 | 0.114 | **-1,851.25** | -0.031 |
| CORE + R1 + R2b | 783 | 0.138 | +883.75 | 0.034 |
| **CORE + R2b ALONE** | 856 | 0.138 | **+8,182.50** | **0.199** |
| CORE + V2 | 1,508 | 0.111 | +6,648.75 | 0.112 |
| **CORE + V2 + R2b** | 766 | 0.142 | **+7,782.50** | **0.190** |
| CORE + V2 + R2b + V3 | 579 | 0.136 | +396.25* | 0.015* |
| CORE + INVERTED R1 (`rv1800 < 250`) — **NOT TRADED** | 260 | 0.065 | +8,923.75 | 0.166 |
| CORE + ORACLE cell side | 402 | 0.445 | +23,883.75 | 0.477 |
| CORE + ANTI-ORACLE side (always wrong) | 709 | 0.000 | -26,170.00 | -0.521 |

(*the V3 row is measured on the R1+R2b base, hence the different level; V3 costs $250 there.)

**R1 — `rv1800 >= 250` at the row, which holds 92.8% of seven sessions' winners and refuses at
0.29x — COSTS $7,562.50 as a gate.** The mechanism is measured directly, and it is the CC-M2-17.4
seat-spender split applied to a concentrator instead of a veto:

> **Of the 64 seats CORE actually spends over seven sessions, 41 have the rolling state CLOSED and
> average +$201.86; the 23 with the state OPEN average -$111.52.**

The concentrator is real over the POOL and INVERTED on the SUB-POPULATION THAT SPENDS THE SEAT,
because `rv1800` is high after a move has happened and the seat-spending row is the earliest
admitted row of a seating window, typically near a phase open where the nowcast still lags. This is
the same diagnosis ERA_NOTES §69/§79 gave the dead A grade (`sigma_to_exit = rv1800 * sqrt(runway)`
selects rows whose rv is high because the move already happened) — now with a receipt at the seat.

**CONSEQUENCE, DECLARED BEFORE THE DAY:** R1 is PRE-REGISTERED AND NOT TRADED. The inverted form is
measured (+$8,923.75, the best arm on the board) and ALSO NOT TRADED — an inversion minted on the
sample that made it look right is the P009 error, and the day-6 own-fuel inversion reversed on day 7
one session later. Both go to the census, not to the policy.

### A3. STAGE 2 — EVERY HAND SIDE INSTRUMENT, MIRROR-LAW TESTED ON 22 WINNER-BEARING CELLS

| estimator | right | wrong | silent | accuracy | mirror | sessions lost |
|---|---|---|---|---|---|---|
| S2c S10 `d_POC`/`in_VA` LITERAL (back to value) >= $250 | 2 | 6 | 14 | **0.250** | 0.750 | 4 |
| S2c literal >= $500 | 2 | 3 | 17 | 0.400 | 0.600 | 3 |
| S2c literal >= $1,000 | 2 | 1 | 19 | 0.667 | 0.333 | 1 |
| S2e the same field at the cell's MEDIAN row >= $250 | 1 | 11 | 10 | **0.083** | 0.917 | 4 |
| X5 S10 CONTINUATION (away from value) >= $250 | 6 | 2 | 14 | 0.750 | 0.250 | 1 |
| X8 `slope15m` at the cell open, CONTINUATION | 12 | 5 | 5 | **0.706** | 0.294 | 1 |
| X7 `fph_sflow` at the cell open, CONTINUATION | 12 | 9 | 1 | 0.571 | 0.429 | 2 |
| X2 session net so far, CONTINUATION | 10 | 8 | 4 | 0.556 | 0.444 | 2 |
| X4 COMPLEX net (other two assets), CONTINUATION | 11 | 10 | 1 | 0.524 | 0.476 | 3 |
| X1 prior-phase net, CONTINUATION | 9 | 10 | 3 | 0.474 | 0.526 | 3 |
| X3 session pos >= 0.7 LONG / <= 0.3 SHORT | 7 | 10 | 5 | 0.412 | 0.588 | 4 |
| **2-of-3 CONSENSUS (X8 + X7 + X2)** | **10** | **7** | **5** | **0.588** | 0.412 | **1** |

**REGISTERED IN FULL, BEFORE THE DAY:**
1. **S10 GEOMETRY — the only hand side-instrument CC-M2-18.3 left standing — IS ANTI-PREDICTIVE IN
   ITS LITERAL FORM** (2 right / 6 wrong at $250; its 2-for-1 record at $1,000 is n=3). The
   ROLLING/median-anchor form is worse still (1/11). The day-7 answer to open question §70.3 was
   0-for-1; the seven-session answer is 2-for-6. **Stage 2 has no validated hand instrument, and
   this is now measured twice over.**
2. **NOTHING PASSES THE MIRROR LAW** (CC-M2-13.1: beat the mirror on EVERY session). X8 and X5, the
   two best, each lose one session. **AND NOTHING SURVIVES MULTIPLICITY**: X8's 12/5 is a one-sided
   binomial p=0.072 uncorrected, on 12 estimators swept — Holm-adjusted, not significant. X5's 6/2
   is p=0.145.
3. **X8's REPLAY GAIN IS ONE SESSION.** CORE+X8 banks +$3,495 over CORE across seven sessions and
   +$3,578.75 of it is 2021-07-02 alone; the remaining six sessions net -$84. That is the exact
   shape of the four corpses this round has already produced (P014, P026, P028, P031), and it is
   named here rather than after the fact.
4. **THE SIDE CALLS ARE STILL BETTER THAN CHANCE AND STILL COST MONEY.** On the CORE+V2+R2b base,
   the consensus side banks +$5,147.50 against its own MIRROR's -$2,431.25 — a $7,578.75 spread, so
   the calls are on the right side of the mirror — and it is $2,635.00 WORSE than not gating on the
   side at all, because refusing rows moves the seat LATER, not better. Tested both repairs:
   "abstain from the cell if its earliest admitted row is on the wrong side" (+$4,186 vs +$6,745 for
   no gate) and "delay to the first matching row" (+$2,988). Both lose. With the ORACLE side, delay
   beats abstain (+$14,770 vs +$10,465) — the asymmetry is entirely in whether the side is right.

### A4. THE DECLARED DAY-8 POLICY, CHOSEN WITH ITS OWN SEVEN-SESSION RECORD ON THE TABLE

> **`READER` = CORE (T1..T5, T5 repaired per CC-M2-16.4) + V2 + R2b (`unspent_bind >= $1,000`
> evaluated at EVERY row — the corrected ROLLING stage-1 state). NO side gate. NO `rv1800` gate.
> V3 is COMPUTED AND LOGGED on every row and NOT APPLIED (CC-M2-19.4 pooled re-grade in flight).**

This is a DECLARED DISCRETIONARY OVERRIDE of the literal instruction to gate on the reader's own
side and vol calls, made lawful and encouraged by CC-M2-12.6 (a declared override with the rule's
backtest on record pre-seal). All gated arms are reported at unblinding so the override is scored
against the thing it overrode. The nine SIDE calls below are committed in full and gate the reported
`READER+SIDE` arm; they are scored for accuracy exactly as on days 6 and 7.

**PROSPECTIVE PATTERN REGISTRATION (CC-M2-4.3):** P004 (T1), P025 (T2, retained only to keep the
moment core identical to its seven frozen predecessors — CC-M2-19.3 BROKE it), P023's de-signed
magnitude floor (T4/T5-repaired), the V2 fuel-overhang family, **P014's complement `unspent_bind >=
$1,000` (R2b — the ledger lists P014 DEAD with n=0/0, i.e. killed in the warm-up without ever being
counted; this is its first count)**, and the stage-2 estimator panel X2/X7/X8/X5/S2c. P029, P009,
P031 are run only as scored REFERENCE estimators. Anything not in this list is post-hoc.

---

## PART B — THE NINE COMMITTED CELL CALLS (each committed before its cell's first candidate row)

### #0 — HG / TOKYO, opens 00:00:18 — **SIDE: LONG** (LOW) · would-abstain: YES
Panel: X8 SILENT (no 15-minute slope exists at second 18), X7 SHORT on `fph_sflow -9` of 146
contracts, X2 SILENT. **CONSENSUS SILENT** (one vote) -> judgment.
* The X7 vote is dismissed on SIZE: -9 of 146 contracts is the "121 contracts is not an overhang, it
  is a rounding error" standard I wrote on day 7 and am applying again here, before any outcome.
* The only substantive evidence is OVERNIGHT CONTINUATION: on 2021-07-09 all three assets closed in
  the top fifth of their own session ranges — SI +$1,000 at pos 0.84, **HG +$1,650 at pos 0.80**,
  NKD +$3,800 at pos 0.96 — and HG gapped **UP $150** into this session.
* AGAINST, named: prior-phase continuation (X1) scores 0.474 at cell grain over seven sessions —
  a coin flip; P029 also says TOKYO -> LONG and gets no weight (dead as a rule); HG/TOKYO is
  1-of-7 winner-bearing over the round.
* **WOULD-ABSTAIN = YES**: no validated evidence exists for a session's first cell. ERA_NOTES §70.4
  registered cell-level abstention as a decision the ledger has never scored; it is scored now.
* Rolling seat at the open: R1 CLOSED (`rv1800 212.4`), **R2b CLOSED (`unspent_bind $807.2`)**.

### #1 — NKD / TOKYO, opens 00:01:05 — **SIDE: LONG** (LOW-MED)
Panel: X8 SILENT, X7 SHORT on -5 of 21 contracts (dismissed on size), X2 SILENT. **CONSENSUS
SILENT** -> judgment.
* **Overnight continuation at maximum strength: NKD closed 2021-07-09 at `pos 0.96` — the session
  high — after +$3,800 on a $5,700 range, with a flat gap.**
* `vol_regime HIGH rv5/rv66 1.218` says the move is LIVE, not exhausted — the counter-fact to any
  mean-reversion read of a 0.96 close.
* `q50 = $1,468` and `unspent_bind = $1,281`: this phase is priced ABOVE the D-021 bar and can pay
  it. **R2b OPEN — the day's first open seat state.** R1 CLOSED (`rv1800 187.1`).
* AGAINST, named: P029 says TOKYO -> LONG (no weight); every trend-continuation object this round
  has minted has died; NKD's round record is 2-of-7 cells but 72 winners, i.e. all-or-nothing;
  `spread 100 / cost_rt 55` is the board's most expensive round trip.

### #2 — SI / TOKYO, opens 00:03:50 — **SIDE: LONG** (LOW) · would-abstain: YES
Panel: X8 SILENT, X7 SHORT on -14 of 100 contracts (14% — the largest of the three TOKYO votes and
still 100 contracts), X2 SILENT. **CONSENSUS SILENT** -> judgment.
* Same overnight-continuation basis as #0/#1 and the weakest instance of it (SI's +$1,000 at pos
  0.84 was the smallest up-day of the three, flat gap).
* **WOULD-ABSTAIN = YES, and this is the strongest structural abstention on the board: SI/TOKYO is
  0-for-7 — it has never held a D-021 winner in any study session of this round.**
* STRUCTURAL FACT LOGGED: **SI's fvol row is REFUSED again — the FIFTH study session (ERA_NOTES
  §16)**. `cov_sess`, `unspent_sess`, `unspent_bind`, `ladder` and `q50` are all `.`, so **today's
  traded stage-1 term cannot speak for SI at all** and SI's rows pass R2b by construction.
* Rolling seat: R1 CLOSED (`rv1800 128.1`, rv60 77.1), R2b SILENT.

### #3 — HG / LONDON, opens 07:19:16 — **SIDE: SHORT** (MED-HIGH)
Panel: X8 SHORT (`slope15m -5`), X7 SHORT (`-43`), X2 SHORT (`net -$700`). **CONSENSUS SHORT.**
* Load-bearing: **X2 — HG is -$700 on the session at `pos 0.12`, sitting at its session low into the
  London open**, after a TOKYO phase that travelled $1,050 and closed at pos 0.12.
* **S10's CONTINUATION form agrees: `d_POC -587.5` with `in_VA 0`** — price is $587 BELOW the
  developing value area. (Its LITERAL back-to-value form says LONG and is pre-registered
  anti-predictive at 2/6, so its disagreement is itself weak evidence for SHORT.)
* Corroboration from a DEAD instrument, named and given no weight: own-asset fuel `0.90 above /
  0.10 below of 11,981` = ~10,783 underwater longs (P009, dead twice over).
* **DEFECT NAMED BEFORE ANY OUTCOME: X7 is structurally noise at a cell's first second.**
  `fph_sflow = -43` is the LONDON phase's cumulative flow at second 0 of that phase. The estimator
  scored 12/9 in the pre-registration WITH this defect, so the number stands, but from here the
  consensus is read as X8 + X2 and X7 is a tie-breaker only. **This rule is stated now and applied
  unchanged at cells #6, #7 and #8.**
* AGAINST: P029 says LONDON -> LONG (13/4 pooled, dead as a rule); HG/LONDON's round split is
  2 LONG / 1 SHORT; the 60s book is bid (`10/14 sflow +4`).
* Rolling seat: R1 CLOSED (`rv1800 91.9` collapsing to `rv60 18.8` — a dead tape into the open),
  **R2b OPEN (`$1,114`)**.

### #4 — SI / LONDON, opens 07:34:29 — **SIDE: SHORT** (MED)
Panel: X8 SHORT (`-5`), X7 SHORT (`-32`), X2 SHORT (`net -$400`, `pos 0.00`). **CONSENSUS SHORT.**
* Load-bearing: SI is printing its session LOW into the London open (`pos 0.00` on a $1,150 TOKYO
  range); S10's continuation form agrees (`d_POC -662.5`, `in_VA 0`).
* **AGAINST, named and serious — this is the day's hardest cell:**
  (i) **SI/LONDON is 3-for-3 LONG across the round's winner-bearing cells.** That is an era-period
  trend of exactly the kind P029 was killed for (CC-M2-17.6), so it is named and NOT followed;
  (ii) **the near book has turned BID at the low** — `60s sflow +26 on 42` (62%), `5m +33 on 297` —
  while only the 30m still sells (`-28 on 610`). This is P022's horizon disagreement, whose compass
  value was falsified at census (CC-M2-11.1), and it is the absorption shape P007/P023 describe —
  whose DIRECTION was falsified on E1D4. Both are named and neither is followed;
  (iii) S10's literal form says LONG.
* **FLIP THRESHOLD (CC-M2-5.8), stated before the outcome: this call flips to LONG if `f5m_sflow`
  holds >= +10% of its own 5-minute volume for the next 15 minutes while the mid stays above the
  TOKYO low.** That is the one measurable fact that would turn the bid-at-the-low into a signal.
* Rolling seat: **R1 OPEN (`rv1800 264.6`)**, R2b SILENT (SI fvol refused). `day_type AT_RANGE` at
  69.5% of `range_hat`.

### #5 — NKD / LONDON, opens 08:42:18 — **SIDE: LONG** (LOW) · would-abstain: YES
Panel: X8 LONG (`+2.5`), X7 SHORT (`-3`), X2 LONG (`net +$100`). **CONSENSUS LONG — and every
magnitude in it is a rounding error** (a $650 session range in 177 rows, `pos 0.54`: a dead,
balanced tape). Recorded as nominal, exactly as at #0/#1.
* S10 SILENT (`in_VA 1`, `d_POC -12.5`). Cross-asset given no weight in either direction (P031 DEAD
  FINAL, CC-M2-18.3), though the metals are dumping (SI -$850 at pos 0.00, HG -$950 at pos 0.11).
* **THE DECISIVE FACT IS STAGE 1, AND IT IS THE DAY-7 PRE-MORTEM MADE EXECUTABLE: `q50 = $567` —
  S3 prices the WHOLE LONDON phase at little more than half the D-021 bar — so `unspent_bind =
  $466.5` and R2b is CLOSED.** On 2021-07-09 my pre-mortem on this same cell wrote "I need $1,000
  out of a phase the forecaster prices at half that" and the term was not encoded; that seat closed
  **-$955.00, walled**. It is encoded now and it refuses the cell's opening rows.
* Also: the book is DEAD at the open (`60s 0/0`, `5m 2/2`) and `cost_rt` is $55.
* R1 CLOSED (`rv1800 182.9`, rv60 37.5). `vol_regime HIGH rv5/rv66 2.179` is a ratio on a collapsing
  base and is named as such.

### #6 — HG / NY, opens 13:01:21 — **SIDE: SHORT** (MED) · **DECLARED OVERRIDE of the literal consensus**
Panel: X8 LONG (`slope15m +8.3`), X7 LONG (`+2`), X2 SHORT (`net -$1,150`). Literal 2-of-3 consensus
= LONG. **I OVERRIDE IT, on the rule I stated at cell #3 before any outcome was known: X7 is
structurally noise at a cell's first second (`+2` on an empty phase window), so the real vote is
X8 LONG vs X2 SHORT = 1-1, no consensus, and the procedure hands the cell to judgment.**
* Judgment names: **HG is -$1,150 on the session at `pos 0.04`**, having sold through TOKYO (pos
  0.12) and LONDON (pos 0.12); **the whole complex is at its session lows** (SI -$1,050 at pos 0.10,
  NKD -$400 at pos 0.06); **HG/NY is 0 LONG / 3 SHORT across the round's winner-bearing cells**;
  and the medium horizons are selling (`5m -18 on 128`, `30m -36 on 553`) while ONLY the 15-minute
  slope points up.
* Corroboration from a DEAD instrument, no weight: ~20,000 trapped longs across two completed phases
  (TOKYO `0.90 above of 11,981`, LONDON `0.87 above of 10,719`).
* AGAINST, named: X8 is the best-scoring cell-grain estimator in the entire sweep (12/5) and it says
  LONG; S10 is SILENT (`in_VA 1`, `d_POC +25`); a fresh 15-minute up-tick at a session low is
  exactly what a short-covering reversal looks like.
* **PRE-MORTEM (auto-logged, CC-M2-5.4): if HG/NY is a LONG cell, the mechanism is that a session at
  `pos 0.04` carrying 20,000 trapped longs and a fresh 15-minute up-slope at the NY open is a
  short-covering reversal — I will have read the trapped longs as SUPPLY when they were FUEL, which
  is P009's exact failure mode and the reason I gave it no weight and then leaned the same way.
  THE TRIGGER, measurable and not yet present: a print above the developing VAH 4.3350 ($1,125 over
  the open) says the buyers are real and the short is on the wrong side.**
* Rolling seat: R1 CLOSED (`rv1800 172.1`), **R2b CLOSED (`unspent_bind $624.4`, `exit_is_sess 1`,
  `cov_sess 71.6%`)** — HG has spent 72% of its expected session range before NY opens.

### #7 — SI / NY, opens 13:02:11 — **SIDE: SHORT** (MED-HIGH)
The round's richest cell: **6-of-7 winner-bearing, 195 winners, split 4 SHORT / 2 LONG.**
Panel: X8 LONG (`+0.8`), X7 LONG (`+2`), X2 SHORT (`net -$1,050`). Literal consensus = LONG.
**Both LONG votes fall below the magnitude standard I applied at #1 and #3** (`slope15m +0.8 $/min`
is a rounding error; `fph_sflow +2` is the empty-phase-window defect), so by the rule stated at #3
the only substantive vote is X2 -> **SHORT**.
* Load-bearing: SI is -$1,050 at `pos 0.10` after TOKYO closed at pos 0.00 and LONDON at pos 0.25 —
  three consecutive phases of one-way selling.
* Corroboration, unweighted: ~11,650 trapped longs (TOKYO `0.99 above of 5,415`, LONDON `0.80 above
  of 7,860`); SI/NY's 4S/2L round record; P029 says NY -> SHORT.
* AGAINST, named: **SI has spent 96.4% of its expected session range (`day_type AT_RANGE`)**, so a
  $1,000 short needs brand-new range — P017's arithmetic, which is 0-for-4 as a refusal and is
  recorded, not traded; the 30m flow is `+28 on 689`, the only horizon buying; and SI's fvol refusal
  means the capacity arithmetic cannot be checked at all today.
* Rolling seat: **R1 OPEN (`rv1800 262.2`)**, R2b SILENT (fvol refused). `runway_phase 35,868s` with
  `exit_is_sess 1` — the longest runway on the board.

### #8 — NKD / NY, opens 13:02:36 — **SIDE: SHORT** (MED) · would-abstain: YES
Panel: X8 LONG (`+5.8`), X7 SILENT (`0`), X2 SHORT (`net -$400`, `pos 0.06`). **NO CONSENSUS (1-1)**
-> judgment.
* **S10's CONTINUATION form fires SHORT: `d_POC -487.5` with `in_VA 0`** — price is $487 below the
  developing POC and outside the value area. That is the form with the 6/2 record; its LITERAL
  back-to-value form (2/6, anti-predictive) says LONG and is named as such.
* NKD reversed from a flat TOKYO (`net +$100`, pos 0.54) into a **-$550 LONDON closing at pos 0.06**;
  the complex is at its lows (SI pos 0.13, HG pos 0.12).
* AGAINST, named: X8 `+5.8` is the sweep's best estimator and says LONG; NKD/NY is 1L/1S over the
  round; and **the book is completely DEAD at the open (`60s 0/0`, `5m 0/0`) with `cost_rt $55`** —
  NKD's phase opens without a counterparty for a sixth session (ERA_NOTES §56), so the seat may
  exist and never become spendable at the MOMENT stage.
* **WOULD-ABSTAIN = YES.** Rolling seat: R1 CLOSED (`rv1800 241.7` — 8 points under the floor),
  **R2b CLOSED (`unspent_bind $903.2`, `q50 $1,028`)**.

---

## SUMMARY OF THE NINE COMMITTED SIDE CALLS

| # | cell | open | SIDE | conf | would-abstain | primary evidence | R1 @open | R2b @open |
|---|---|---|---|---|---|---|---|---|
| 0 | HG/TOKYO | 00:00:18 | LONG | LOW | **YES** | overnight continuation (HG +$1,650 @pos 0.80, gap +$150) | CLOSED 212.4 | CLOSED $807 |
| 1 | NKD/TOKYO | 00:01:05 | LONG | LOW-MED | no | NKD closed 07-09 at pos 0.96 on +$3,800; HIGH vol; q50 $1,468 | CLOSED 187.1 | **OPEN $1,281** |
| 2 | SI/TOKYO | 00:03:50 | LONG | LOW | **YES** | same, weakest instance; SI/TOKYO **0-for-7** | CLOSED 128.1 | silent (fvol) |
| 3 | HG/LONDON | 07:19:16 | **SHORT** | MED-HIGH | no | X2 -$700 @pos 0.12 + X8 -5 + S10 continuation -$587 outside VA | CLOSED 91.9 | OPEN $1,114 |
| 4 | SI/LONDON | 07:34:29 | **SHORT** | MED | no | X2 -$400 @**pos 0.00** + X8 -5 + S10 continuation -$662 | **OPEN 264.6** | silent (fvol) |
| 5 | NKD/LONDON | 08:42:18 | LONG | LOW | **YES** | nominal consensus on a $650 range; **q50 $567 < the bar** | CLOSED 182.9 | **CLOSED $466** |
| 6 | HG/NY | 13:01:21 | **SHORT** | MED | no | override: X2 -$1,150 @pos 0.04, complex at lows, HG/NY 0L/3S | CLOSED 172.1 | **CLOSED $624** |
| 7 | SI/NY | 13:02:11 | **SHORT** | MED-HIGH | no | X2 -$1,050 @pos 0.10, three phases of one-way selling, 4S/2L | **OPEN 262.2** | silent (fvol) |
| 8 | NKD/NY | 13:02:36 | **SHORT** | MED | **YES** | S10 continuation -$487 outside VA + X2 @pos 0.06; dead book | CLOSED 241.7 | **CLOSED $903** |

**FOUR LONG (all three TOKYO cells + NKD/LONDON, all resting on overnight or nominal continuation)
and FIVE SHORT (every LONDON metal and every NY cell, all resting on X2 — the session's own
one-way selling).** The five SHORT calls are ONE BET TAKEN FIVE TIMES: the complex sold from the
Asian open to the NY open on all three assets, and X2 reads that same fact in each cell. Declared as
such. Four cells carry would-abstain.

**The correlation cuts the other way too:** the three TOKYO LONGs rest on ONE fact (Friday's close
near the highs) and by 07:19 that fact was already refuted by the tape — HG -$700, SI -$400. The
day's own evidence overturned the day's own first three calls within seven hours, and the calls
stand as committed (CC-M2-3: never revise the committed thesis — the miss IS the data).

---

## UNBLINDED RESULT (opened only after the seal commit `cf2400a`)

**THE DAY: 47 D-021 winners in 949 candidates (4.95%), and 44 of the 47 are LONGS.** Four of the
nine cells carry winners. Per asset: SI 36 (mean -$4.04, walled 0.407), HG 9 (+$1.72, 0.230),
NKD 2 (-$57.48, 0.236). Day DP ceiling **$7,480.00** (SI 3,260 / HG 2,322.50 / NKD 1,897.50).

| # | cell | truth | winners | SIDE call | right? | would-abstain | seat spent | seat close $ |
|---|---|---|---|---|---|---|---|---|
| 0 | HG/TOKYO | NONE | 0 | LONG | — | YES | — | — |
| 1 | NKD/TOKYO | NONE | 0 | LONG | — | no | — | — |
| 2 | SI/TOKYO | **SHORT** | 3 | LONG | **✗** | **YES** | 03:02:02 L | **-542.50** (walled) |
| 3 | HG/LONDON | NONE | 0 | SHORT | — | no | — | — |
| 4 | SI/LONDON | NONE | 0 | SHORT | — | no | 07:34:29 L | **-505.00** |
| 5 | NKD/LONDON | NONE | 0 | LONG | — | YES | — | — |
| 6 | HG/NY | **LONG** | 9 | SHORT | **✗** | no | — | — |
| 7 | SI/NY | **LONG** | **33** | SHORT | **✗** | no | 13:02:11 L | **+1,470.00** |
| 8 | NKD/NY | **LONG** | 2 | SHORT | **✗** | YES | — | — |

**SIDE-CALL ACCURACY: 0 of 4 = 0.000. The MIRROR of my calls scores 1.000.** Three-session record
of committed cell-side calls: 3/5, 2/5, 0/4 = **5 of 14 (0.357); mirror 9 of 14 (0.643)**.

**THE FOUR WRONG CALLS ARE TWO BETS, AND THE LEDGER SAID SO BEFORE THE OUTCOME.** The summary
paragraph above committed that the five SHORTs "rest on X2 — the session's own one-way selling" and
were "ONE BET TAKEN FIVE TIMES", and that the three TOKYO LONGs "rest on ONE fact (Friday's close
near the highs)" which "was already refuted by the tape" by 07:19. Both bets lost. Writing the
correlation down before the fact is what makes the loss diagnosable instead of merely painful.

**THE SEAT THAT PAID WAS TAKEN AGAINST MY OWN SIDE CALL.** SI/NY was called SHORT at MED-HIGH
confidence — the day's highest — and it held 33 LONG winners paying $1,020-$1,670. The committed
policy runs no side gate (the declared CC-M2-12.6 override, backtested pre-seal), so it took the
cell's earliest admitted row, a LONG, for **+$1,470.00**. Gating on the committed side calls scores
**-$4,000.00**; the mirror of them scores **+$1,460.00**.

**THE STAGE-1 TERM I DID TRADE REFUSED EVERY NON-SI WINNER.** R2b (`unspent_bind >= $1,000`) refused
all 9 HG/NY winners (`unspent_bind` 180.7-224.4, certificates $1,001-$1,120) and both NKD/NY winners
(903.2, $1,008-$1,020) — 11 of the day's 47. And SI/NY, holding 33 more, passed only because SI's
fvol is REFUSED and the field is `.` (defect D22, named in the seal before unblinding). **The one
cell the term let me into, it let me into by accident.**

**THE PRE-REGISTRATION'S TWO PREDICTIONS BOTH LANDED.** R1 (`rv1800 >= 250`) as a gate: predicted to
destroy value, scored **-$1,658.75** against CORE's +$1,172.50 on a day it holds 45 of 47 winners.
Its INVERTED form, the best arm of the seven-session board (+$8,923.75) and pre-registered as NOT
TRADED: scored **+$207.50**, worse than CORE. The discipline was worth $965.

**ABSTENTION SCORED, AND IT IS THE ONLY THING THAT PAID.** Removing the four would-abstain cells:
+$422.50 -> **+$965.00**, capture 0.130 -> 0.296. The cell that mattered is SI/TOKYO — 0-for-7 over
the round — whose seat walled.

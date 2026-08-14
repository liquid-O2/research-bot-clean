# E1 STUDY DAY 6 — THE CELL-SIDE LEDGER (CC-M2-16.1 / CC-M2-15.5, the day's PRIMARY DELIVERABLE)

Reader: opus-discretionary, fresh context (CC-M2-4.2). Draw: the next chronological STUDY session per
asset strictly after 2021-07-07, warm-ups excluded (CC-M2-8.1) — **SI/HG/NKD 2021-07-08**, 1,618
candidates (SI 515, HG 389, NKD 714). USED_CASE_LEDGER carries 0 prior hits on 20210708.

**WHAT THIS FILE IS.** CC-M2-16.1 made the (ASSET, PHASE) CELL the invariant unit and defined M3
model #1 as the PHASE-SIDE CLASSIFIER anchored at each phase open. This ledger is that classifier's
TRAINING-EVIDENCE SEED: for every one of the day's nine cells, an explicit ex-ante SIDE CALL with
NAMED evidence, **committed before that cell's first candidate row**, produced by the as-of stepper
(`engine/port_m2/e1d6_cellbrief.py`) so the call cannot see the tape it is calling.

**MECHANIC.** `e1d6_cellbrief.py --cell K` emits a brief computed only from rows with
`sec < cell_open_sec` (asserted in code). The reader consumes the briefs IN CHRONOLOGICAL ORDER and
commits each call before requesting the next, so no cell's call can be informed by a later cell's
tape. Declared accepted exposure: the ORDERED LIST of (asset, phase, first-candidate second) is
generation-side metadata of the same class as the per-asset candidate counts every prior study day
declared before the day. It carries no price and no outcome.

---

## THE DECLARED ESTIMATORS, PRE-REGISTERED WITH THEIR MIRROR TESTS BEFORE ANY DAY-6 CELL WAS CALLED

Backtest: `engine/port_m2/e1d6_cellside.py --backtest` over **all 45 (asset, phase) cells of the five
unblinded study sessions**, of which **12 carry D-021 winners** and are scorable. Truth = the cell's
winner-majority side from the frozen v3 roster via `panel_score.outcome`.
Receipt: `artifacts/cache/port/m2/triage/E1D6_CELLSIDE_BACKTEST.tsv`.

### (i) E1D6-CS, the six-component composite (the reader's own first design) — **FAILS**

| component | field | right | wrong | silent | acc |
|---|---|---|---|---|---|
| C1 prior-phase close position | triage `mid` path of the prior phase | 4 | 4 | 4 | 0.500 |
| C2 session net so far | `mid`,`mult` (the CC-M2-15.2 probe's best naive term) | 3 | 5 | 4 | 0.375 |
| C3 overnight continuation | prior session's net move | 4 | 5 | 3 | 0.444 |
| C4 fuel overhang | S8 `trapped_above/below`/`phase_total` | 4 | 4 | 4 | 0.500 |
| C5 cross-asset metals coherence | the other metal's session net | 2 | 5 | 5 | 0.286 |
| C6 multi-day level position | S4 NDAY nearest `d$` | 5 | 3 | 4 | 0.625 |
| **COMPOSITE** | sum of votes | **4** | **6** | 2 | **0.400 decided** |
| **its MIRROR** | | 6 | 4 | 2 | **0.600** |

**E1D6-CS loses to its own mirror (0.400 vs 0.600) and is therefore INADMISSIBLE under CC-M2-13.1.**
Registered here, before the day, exactly as day 5 registered P027's failure. It is NOT the day's
side source. It is still computed and logged per cell so the classifier lane gets the component
values with their labels.

### (ii) P029 PHASE_SIDE_PRIOR — the object the backtest actually found

Cell-side truth over five sessions, by phase: **NY SHORT ×7, NY LONG ×1, LONDON LONG ×2, TOKYO LONG
×2.** The estimator is one field, `S1 phase_dec`:

> **TOKYO or LONDON cell -> LONG. NY cell -> SHORT.**

| session | right / wrong |
|---|---|
| 2021-07-01 | 2 / 0 |
| 2021-07-02 | **0 / 1** |
| 2021-07-05 | 1 / 0 |
| 2021-07-06 | 3 / 0 |
| 2021-07-07 | 5 / 0 |
| **pooled** | **11 / 1** |

**MIRROR-LAW STATUS, REGISTERED BEFORE THE DAY: it beats its mirror on 4 of 5 sessions and LOSES ON
2021-07-02 => it FAILS CC-M2-13.1 as a standing term**, exactly as P027 did. It is traded today as
the declared cell-side experiment (the brief's "your own judgment per cell"), with the failure on
the record first so no result below can be re-read as a discovery.

**THE ONE EXCEPTION IS THE ONE SESSION THE CC-M2-12.3 SEPARATOR FLAGS.** 2021-07-02 is the only
study session containing a scheduled release (12:30Z Employment Situation; `event_in_session`=1 on
935/935 rows there and 0 on every row of the other four). Making the NY sign conditional on that
flag would score 12/12 — **and that is exactly the P014/P026/P028 error the round has three corpses
for (fitting the conditional on the single session that breaks the rule, n=1).** THE CONDITIONAL IS
NOT TRADED AND NOT PROMOTED. It is logged as a censusable hypothesis only.

**EX-ANTE REGIME CHECK FOR TODAY:** 2021-07-08 carries `sched_last_age=.` and
`sched_next_in=472,823s` (CPI, 5.5 days out) on all 1,618 rows => **`event_in_session`=0**, i.e. the
day is in the class where P029 went 11-for-11. Named before the calls.

### (iii) WHAT IS NOT AVAILABLE — DEFECT D20, the regime forecaster is VOID in E1

CC-M2-14.2(a) ordered the forecaster's columns into the triage index "so study days 6-8 read them",
and the day-6 brief orders their use. **They do not exist for this era.**
`predicted_day_type_prob`, `range_hat_vs_trailing` and `menu_hat` are `.` on **all 1,618 rows**,
because `forecast_{SI,HG,NKD}.tsv` carry NO predictions for ANY 2021 session (`p_expansion` and
`range_hat_usd` empty on 462/462 SI, 774/774 HG, 777/777 NKD 2021 rows; the first populated
predictions are 2022, and SI's first are 2022 H2). The join in `triage_index.py` is correct; the
forecaster simply has no walk-forward training window inside E1. **CC-M2-14.3's composition
hypothesis (predicted day-type × side estimator × refusal core) is UNTESTABLE ON E1 STUDY AND E1
BLIND.** Reported as the day's headline defect.

### (iv) DEFECT D19 — the forecaster's per-session file carries TRUTH next to the predictions

While diagnosing (iii) the reader opened `artifacts/cache/port/m2/regime_forecast/forecast_SI.tsv`
and the two siblings, and those rows carry `y_day_type`, `y_range_usd`, `y_share_{TOKYO,LONDON,NY}`
and `y_menu` — the REALISED session outcomes — populated for 2021-07-08, beside the empty
predictions. **The reader therefore saw, before the day was called: each asset's realised session
RANGE, realised day-type class, and realised per-phase range SHARE.** Declared in full rather than
buried:
* these are UNSIGNED magnitude/allocation facts and carry **no side and no candidate outcome**, so
  the cell-side calls below (which are pure side calls) are not informed by them;
* they DO bear on magnitude/feasibility, so **every TAKE row of this day carries the taint value
  `FORECAST-TRUTH-EXPOSED`** and the day's take-set economics are quotable only with that stamp;
* the index join is clean (it reads only the three `*_hat` fields), so the defect is in the FILE
  LAYOUT, not the tooling: **truth columns must not live in the file a reader is directed to read.**
  Fix: split `forecast_*.tsv` into `forecast_*.tsv` (predictions) and `truth_*.tsv` (already exists!
  — the `y_*` columns are duplicated from `truth_{SI,HG,NKD}.tsv` and should simply be dropped from
  the forecast file).

---

## THE NINE CELL-SIDE CALLS (committed in chronological order, each before its cell's first row)

Format: `#K  ASSET/PHASE  open  CALL  conf  | named ex-ante evidence | E1D6-CS composite`

### #0 — HG / TOKYO, opens 00:11:21 — **CALL: LONG**, confidence MEDIUM

Prior rows: **none** (the day's first cell). Evidence is PRIOR-SESSION CONTEXT only, as the module
declares for a session's first cell.
* **P029 PHASE_SIDE_PRIOR: TOKYO -> LONG** (11-for-1 over five sessions; TOKYO cells 2/2 LONG).
* **C3 overnight continuation = +1**: HG's 2021-07-07 session net is **+$1,700** (4.2530 -> 4.3210,
  the largest of the three assets), i.e. a clean up-day into this open.
* **C6 multi-day level position = +1**: S4 on `HG-20210708-000681-L` rolls up `NDAY=8/-1863/8` —
  every N-day level is **$1,863 or more BELOW** the mid and all 8 are virgin. Price is at the top of
  its multi-day range; the N-day trend is up.
* **S2 on the same sheet: `vol_regime LOW rv5/rv66=0.530`, `day_type_so_far INSIDE`,
  `range_so_far=$125.0 = 5.8% of range_hat $2,148.8`** — a coiled, unspent open.
* **S12: `next_scheduled CPI ... in 5d 14:18:39`, no `last_scheduled`** => `event_in_session=0`, the
  regime in which P029 is 11-for-11.
* AGAINST, named: HG's first mid today is **4.3093 against yesterday's last 4.3210 — a $293
  overnight GAP DOWN** after an up-day. A gap against the prior trend is the one fact here pointing
  SHORT, and it is what the call is taken over.
* E1D6-CS composite: SUM +2 -> LONG (agrees; C1/C2/C4/C5 silent for want of prior rows).

### #1 — NKD / TOKYO, opens 00:37:59 — **CALL: LONG**, confidence LOW-MEDIUM

* **P029: TOKYO -> LONG.** NKD's own only winner-bearing TOKYO cell in the round (2021-07-07,
  02:01-02:02) was LONG, 4 winners.
* **C6 = +1**: `NDAY=./-1150/.` on `NKD-20210708-002279-*` — the nearest N-day level is **$1,150
  below** the mid; NKD too opens at the top of its multi-day structure.
* **C3 = 0**: NKD's 2021-07-07 net is **-$150** (28,380 -> 28,350), inside the $300 dead zone — no
  overnight vote. Its NY phase yesterday closed at **0.14 of the NY range** (a weak close), which is
  the fact pointing the other way and is named here.
* **Cross-asset at the cut**: HG is **+$200 with its last mid at 0.89 of the session range so far**
  and its TOKYO phase flow **+128 on 419 (30.5% buy-side)** with the fuel map **349 of 419 trapped
  BELOW** the mid — the metals tape is bid in Asia. NKD is not a metal, so C5 abstains by
  construction; this is read as corroboration of a risk-on Asian session only.
* E1D6-CS composite: SUM +1 -> LONG (agrees).

### #2 — SI / TOKYO, opens 00:57:52 — **CALL: LONG**, confidence LOW-MEDIUM

* **P029: TOKYO -> LONG.**
* **C6 = +1**: `NDAY` nearest **-$900** on `SI-20210708-003472-*` — SI too sits above its N-day
  structure.
* **C3 = 0**: SI's 2021-07-07 net is **-$50**, flat; yesterday was a LONDON +$1,300 / NY -$1,350
  round trip that ended mid-range. No overnight vote.
* **C5 = 0 but the sign is informative and named**: HG is **+$200** (below the $300 dead zone) with
  `pos 0.89` and 349 of 419 TOKYO contracts trapped BELOW the mid. The metals complex is bid in
  Asia; SI is HG's twin in this era.
* AGAINST, named: NKD has turned **-$100 with `pos 0.00`** (its last mid is the session low) and its
  fuel map is **22 of 25 trapped ABOVE** — a small risk-off tick that a metals long must ignore.
  Also SI's spot stamp in S12 (`GOLD_SILVER_RATIO ... si=26.154`, as of 2021-07-06) sits **below**
  today's open, so the two-day drift is up.
* E1D6-CS composite: SUM +1 -> LONG (agrees).

### #3 — HG / LONDON, opens 07:00:26 — **CALL: SHORT**, confidence LOW
**DECLARED DISCRETIONARY OVERRIDE of P029 (which says LONG), lawful under CC-M2-12.6 because P029's
full backtest is on the record above, pre-seal. Both calls are scored separately at unblinding.**

The Asian session inverted the premise the LONDON->LONG cells of 2021-07-07 rested on (that day's
metals TOKYO closed **+$650 HG at pos 0.88 / +$50 SI at pos 0.67**; today's closes the opposite way):
* **CROSS-ASSET, at magnitude: SI is -$1,450 on the session with its last mid at `pos 0.03` — the
  session low — and its TOKYO fuel map is `7,424 above / 1,211 below / 8,635 total` = 86% of the
  phase's contracts trapped ABOVE the mid** with phase sflow **-665 on 8,635 (7.7% sell)**. Every
  buyer of Asian silver is underwater into the London open. SI and HG are one trade in this era.
* **NKD confirms the risk tone**: -$850, `pos 0.22`, phase sflow -115/914 (12.6% sell).
* **HG's own price is BELOW its developing value**: S10 `dev POC 4.305 / VAH 4.316 / VAL 4.295`,
  `d_POC = -93.7` with the mid at 4.301 — price is $94 under the volume magnet, `in_VA=1`.
* **HG fuel map `6,825 above / 4,632 below / 11,457`** = 0.60 trapped against a long (below the 0.65
  C4 trigger, so C4 stays silent — recorded, not overstated).
* Corroboration only (never primary — momentum terms are 3-for-3 value-destroying, ERA_NOTES §34):
  S5 `slope15m/5m/1m = -1.3/-20/-25`, falling into the open.
* AGAINST, named and real: **P029 itself (LONDON 2/2 LONG, pooled 11/1)**; **C3 = +1** (HG's
  2021-07-07 net +$1,700); **C6 = +1** (`NDAY` nearest -$1,619, still at multi-day highs); and HG's
  RELATIVE STRENGTH — it is -$200 while SI is -$1,450, which is the fact that would make a
  HG-vs-SI pairs trader long HG.
* **S2/S3 feasibility (not direction): `day_type_so_far INSIDE`, `range_so_far $1,038 = 48.3% of
  range_hat`, `cov_sess 45.1%`, `unspent_sess $1,264`, `runway_sess 57,682s`** — the session has
  spent under half its expected range with 16 hours to run.
* **S12 `sched_next_in=459,083`, `sched_last_age=.`** => `event_in_session=0`, P029's supported class.
* E1D6-CS composite: SUM 0 -> **NOCALL** (C1 0.462 silent, C2 -1, C3 +1, C4 0, C5 -1, C6 +1).

### #4 — SI / LONDON, opens 07:00:34 — **CALL: SHORT**, confidence MEDIUM-HIGH
**DECLARED DISCRETIONARY OVERRIDE of P029 (LONDON -> LONG). The composite agrees with the override
here (SUM -4), which is the only cell where all four live components line up.**

* **C4 = -1, the strongest single reading of the day so far**: SI's TOKYO fuel map is
  `7,424 above / 1,211 below / 8,635 total` — **86% of the phase's contracts are trapped ABOVE the
  mid**, and the phase's cumulative flow is **-665 on 8,635 (7.7% sell-side)**. This is exactly the
  V2 configuration (supply overhang with the adverse stream still running) that is net-positive as a
  refusal on all five sessions (CC-M2-16.2).
* **C1 = -1**: `pos 0.033` — SI's last TOKYO mid is the session low to within 3% of the range.
* **C2 = -1**: session net **-$1,450** on a $1,500 range, i.e. essentially the whole Asian range was
  one-way down.
* **C6 = -1**: `NDAY` nearest **+$650** — unlike HG and NKD, SI has already traded DOWN THROUGH its
  N-day structure and the nearest multi-day level is now overhead.
* **S10: `dev POC 26.04 / VAH 26.12 / VAL 25.95`, `d_POC = -337.5`** — the mid is $338 below the
  volume magnet, the largest price-vs-value gap on the board.
* **S2: `day_type_so_far AT_RANGE`, `range_so_far $1,662 = 68.6% of range_hat`** with `runway_sess
  58,039s` — two thirds of the expected range spent before London opens, so a continuation SHORT
  needs new range and the mean-reversion family (P017/P021, 0-for-3 as a refusal) would refuse it.
  Recorded as the feasibility caveat, not as direction.
* AGAINST, named: **P029 (LONDON 2/2 LONG)**; SI's `fvol` row is REFUSED for this session
  (`cov_sess=.`, `ladder=.`, `q10/q50=.`, ERA_NOTES §16 repeating), so no coverage/ladder arithmetic
  is available; and the 30m flow is **+77 on 466 buy-side**, the one live stream pointing up.
* E1D6-CS composite: SUM **-4** -> SHORT (agrees with the reader).

### #5 — NKD / LONDON, opens 08:38:34 — **CALL: SHORT**, confidence MEDIUM
**DECLARED DISCRETIONARY OVERRIDE of P029 (LONDON -> LONG); the composite agrees (SUM -2).**

* **C2 = -1 / C1 = -1**: NKD is **-$1,000 on a $1,150 session range with `pos 0.09`** — like SI, the
  whole Asian range was one-way down and the tape sits on its low into the London open.
* **C4 = -1**: TOKYO fuel map `956 above / 280 below / 1,312` = **73% trapped ABOVE**, phase sflow
  **-127 on 1,312 (9.7% sell)**.
* **AGAINST, named and strong: C6 = +1** (`NDAY` nearest **-$1,888**, NKD is still far above its
  multi-day structure) and **P029** (TOKYO/LONDON -> LONG, and NKD's only winner cell in the round
  was a TOKYO LONG).
* **FEASIBILITY WARNING, recorded before the phase is traded (this is the A1 arithmetic, not
  direction): `cov_sess 83.3%` with `unspent_sess $257.70` and `day_type_so_far AT_RANGE` at
  `range_vs_hat 80.9%`.** NKD has spent five sixths of its expected session move before London
  opens; a $1,000 certificate from here needs brand-new range on a `vol_regime LOW / rv5-rv66 0.469`
  tape.
* **THE BOOK IS DEAD AT THE CELL OPEN**: S8 `60s 0/0`, `5m 1/1`, `30m 86/209`. P004 refuses this row
  outright and it is the fifth consecutive session in which NKD's phase opens without a counterparty
  (ERA_NOTES §56). The side call stands as EVIDENCE; it does not imply a take.
* **Cross-asset**: HG LONDON is **-$225 at `pos 0.00`** with `2,851 of 3,047` LONDON contracts
  trapped above — the override of #3 is tracking so far; SI LONDON is **+$150 at `pos 0.33`**, a
  shallow bounce inside a 2,408/2,958 overhang.
* E1D6-CS composite: SUM -2 -> SHORT.

### #6 — NKD / NY, opens 13:00:19 — **CALL: SHORT**, confidence MEDIUM
**P029 and the composite AGREE with the reader here (the only cell of the day where all three
coincide before the LONDON/NY boundary).**

* **P029: NY -> SHORT** (7 of 8 NY cells over five sessions).
* **C2 = -1 at magnitude**: NKD is **-$3,550 on the session** (TOKYO -$1,000 then LONDON -$2,400),
  a one-way trend day.
* **C1 = -1**: `pos 0.109` — the last LONDON mid is on the session low.
* **C4 = -1**: LONDON fuel `1,833 above / 219 below / 2,052` = **89% trapped ABOVE**, phase sflow
  **-181 on 2,052 (8.8% sell)** — the adverse stream is still running (the full V2 configuration).
* **AGAINST, named, and it is the strongest counter-case of the day: the session has grossly
  overspent its capacity.** `day_type_so_far EXPANDED`, `range_so_far $3,925 = 246.7% of range_hat`,
  `cov_sess 254%`, `unspent_sess -$2,380`, `S9 surprise 1.822`, `ladder at_or_above_q90`, and
  `S10 d_POC = -$2,588` with `in_VA=0` — the mid is $2,588 below the developing POC and outside the
  value area entirely. Every mean-reversion object in the ledger (P002/P003/P014/P017/P021) points
  LONG here. They are **0-for-3 as refusals and 0-for-5 as direction**, which is why the call goes
  the other way, but the disagreement is on the record and this is the cell to watch.
* Corroboration against: `S5 slope15m/5m/1m = +10/+10/+50` — the tape is ticking up into the NY open.
* **Cross-asset, and the day's structural surprise: THE METALS HAVE DIVERGED.** SI LONDON is
  **+$1,450 at `pos 0.91` with 11,877 of 12,622 contracts trapped BELOW the mid** (94% — a
  short-side overhang, i.e. buy-back fuel) while HG LONDON is **-$1,425 at `pos 0.10` with 20,213 of
  23,057 trapped ABOVE** (88%). C5's premise that SI and HG are one trade is falsified on this
  session, before it was used on any NY cell.
* E1D6-CS composite: SUM -3 -> SHORT.

### #7 — HG / NY, opens 13:00:28 — **CALL: SHORT**, confidence MEDIUM-HIGH
**P029, the composite and the reader all agree.**

* **P029: NY -> SHORT.**
* **C4 = -1 at the day's largest scale**: HG's LONDON fuel map is
  `20,213 above / 2,844 below / 23,057` — **88% of 23,057 contracts trapped ABOVE the mid**, the
  biggest overhang on any cell of the day. The London buyers are all underwater into the NY open.
* **C1 = -1 (`pos 0.104`) and C2 = -1 (`-$1,650` session, `-$1,425` LONDON)**: a clean two-phase
  downtrend closing on its low.
* **S10 `dev POC 4.262 / VAH 4.297 / VAL 4.233`, `d_POC = -$481.3`, `in_VA=1`** — price is $481
  under value but still inside the value area, so the profile has not yet priced an exhaustion.
* **AGAINST, named**: **C3 = +1** (HG's prior session was **+$1,700**, the strongest overnight
  up-vote on the board) and **C6 = 0** (`NDAY` nearest -$269 — HG has now traded back INTO its
  multi-day structure, so the C6 vote that supported the morning longs has gone). Also
  `S5 slope15m/5m/1m = +14.6/+10/+12.5` and `S8 5m sflow +42 on 265` — the last five minutes before
  the NY open are bid.
* **FEASIBILITY (not direction): `day_type_so_far EXPANDED`, `range_so_far $2,288 = 106.5% of
  range_hat`, `cov_sess 99.4%`, `unspent_sess $14.20`, `runway_sess 36,738s`.** HG has spent its
  entire expected session move before NY opens; a $1,000 NY certificate is brand-new range on a
  `vol_regime LOW` tape. This is the same configuration as NKD (#6) and it is the single largest
  reason to expect the day's NY cells to produce SMALL certificates even if the side is right.
* E1D6-CS composite: SUM -2 -> SHORT.

### #8 — SI / NY, opens 13:00:43 — **CALL: SHORT**, confidence MEDIUM
**The reader SIDES WITH P029 AND AGAINST ITS OWN COMPOSITE (which says LONG, SUM +2). This is the
one cell where the two declared estimators disagree, so it is the day's cleanest single test.**

* **P029: NY -> SHORT.**
* **S10 is the decisive named field: `dev POC 25.97 / VAH 26.15 / VAL 25.95`, `d_POC = +$1,362`,
  `in_VA = 0`.** SI's mid at 26.24 is **above the developing VAH and $1,362 above the POC** — the
  session's entire volume was built $1,300 lower and the London rally has left value behind. (P028
  is DEAD as a magnitude veto, ERA_NOTES §52; this is the SIDE reading of the same field, which has
  never been tested — flagged as such.)
* **The last minute turns at the boundary**: `S5 slope1m = -62.5` against `slope15m +35.8 / 5m +20`,
  and `S8 60s sflow -19 on 51 (37% sell)` with 5m -9/234 and 30m -8/999 — the flow at the NY open
  is selling into the top of the London range. Corroboration, not primary (momentum 3-for-3
  value-destroying).
* **C5 = -1**: HG is **-$1,600** and printed its NY open at `pos 0.10`. In a divergence the weaker
  metal usually wins the argument by the NY afternoon; this is a judgement, named as such.
* **AGAINST, named, and the composite is built on it**: **C1 = +1** (`pos 0.906`), **C4 = +1**
  (LONDON fuel `745 above / 11,877 below / 12,622` = **94% trapped BELOW**, i.e. a short-side
  overhang that must buy back), **C6 = +1** (`NDAY` nearest -$725). Three of the four live
  components say LONG. If SI's NY is a LONG cell, C4 is the component that called it and the reader
  is the one that was wrong.
* `S2 day_type_so_far AT_RANGE`, `range_so_far $1,675 = 69.1% of range_hat`, `runway_sess 36,012s`;
  SI's `fvol` row is REFUSED all session (`cov_sess=.`, `ladder=.`), so no ladder arithmetic exists.
* E1D6-CS composite: SUM +2 -> LONG (**DISAGREES**).

---

## SUMMARY OF THE NINE COMMITTED CELL-SIDE CALLS (all committed before their cell's first row)

| # | cell | open | READER | conf | P029 | E1D6-CS | agree? |
|---|---|---|---|---|---|---|---|
| 0 | HG/TOKYO | 00:11:21 | LONG | MED | LONG | LONG | all |
| 1 | NKD/TOKYO | 00:37:59 | LONG | LOW-MED | LONG | LONG | all |
| 2 | SI/TOKYO | 00:57:52 | LONG | LOW-MED | LONG | LONG | all |
| 3 | HG/LONDON | 07:00:26 | **SHORT** | LOW | LONG | NOCALL | reader overrides P029 |
| 4 | SI/LONDON | 07:00:34 | **SHORT** | MED-HIGH | LONG | SHORT | reader+CS vs P029 |
| 5 | NKD/LONDON | 08:38:34 | **SHORT** | MED | LONG | SHORT | reader+CS vs P029 |
| 6 | NKD/NY | 13:00:19 | SHORT | MED | SHORT | SHORT | all |
| 7 | HG/NY | 13:00:28 | SHORT | MED-HIGH | SHORT | SHORT | all |
| 8 | SI/NY | 13:00:43 | SHORT | MED | SHORT | **LONG** | reader+P029 vs CS |

Reader: 3 LONG (all TOKYO) + 6 SHORT. P029: 6 LONG + 3 SHORT. E1D6-CS: 4 LONG + 4 SHORT + 1 NOCALL.
The three estimators are pairwise distinguishable on this day — 4 cells separate reader from P029
and 2 separate reader from the composite, so all three get a real test.

**DECLARED BIAS DISCLOSURE (honesty, not evidence).** The reader carries background knowledge that
silver and copper fell through July 2021. No call above uses it; every call names sheet/index fields
and the calls that follow the metals down were made from the fuel map, the phase close position and
the cross-asset state. It is declared because an undeclared prior is indistinguishable from a leak.

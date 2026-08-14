# E1 STUDY DAY 7 — THE PER-CELL LEDGER (CC-M2-17.1, the day's PRIMARY DELIVERABLE)

Reader: opus-discretionary, fresh context (CC-M2-4.2). Draw: the next chronological STUDY session
per asset strictly after 2021-07-08, warm-ups excluded (CC-M2-8.1) — **SI/HG/NKD 2021-07-09**,
1,388 candidates (SI 315, HG 407, NKD 666). `USED_CASE_LEDGER` carries **0** prior hits on
20210709. 2021-07-09 is a Friday; `short_day=0`, `observed_close=82799`.

**WHAT THIS FILE IS.** CC-M2-17.1 decomposed the decision into three stages and gave each its own
estimand: **(1) SEAT EXISTENCE — does this (asset, phase) cell offer a D-021 seat today? (2) CELL
SIDE — which side? (3) MOMENT — which candidate?** Day 6 answered only (2) and (3): it called the
side at 0.600 accuracy, the best direction object of the round, and still lost the replay because
it spent a seat in all nine cells and **four held no winner on either side**. This ledger commits
BOTH a SEAT call and a SIDE call for every cell of the day, each **before that cell's first
candidate row**, with named ex-ante evidence, and the day's policy takes **only in cells called
seat=YES and only on the called side** — the full three-stage discipline as the declared experiment.

**MECHANIC (D18b, HEAD V3 tooling end-to-end).** `engine/port_m2/e1d7_cellbrief.py --cell K` emits
a brief built from rows with `sec < cell_open_sec` PLUS the cell's own first-second row (the row
being called; `triage_index.prefix_view` admits `sec <= as_of`, and `_assert_prefix` /
`_assert_at_open` refuse anything else). `engine/port_m2/e1d7_stage12.py --cell K` emits the
declared estimator values for the same cut. The reader consumes the cells IN CHRONOLOGICAL ORDER
and commits each cell's SEAT+SIDE call before requesting the next.
Accepted exposure, declared as on day 6: the ORDERED LIST of (asset, phase, first-candidate second)
is generation-side metadata carrying no price and no outcome.

**TAINT.** `CLEAN;AS-OF-PREFIX` on every row. **The day-6 `FORECAST-TRUTH-EXPOSED` class does not
recur: per CC-M2-17.2 the forecaster is VOID in E1 and the D19 fix may not have landed, so no
forecast/truth TSV was opened at any point today. The triage index is the reader's only forecaster
surface, and its three columns are `.` on all 1,388 rows (verified below).**

---

## THE DECLARED ESTIMATORS, PRE-REGISTERED ON 54 CELLS BEFORE ANY DAY-7 CELL WAS CALLED

`engine/port_m2/e1d7_stage12.py --backtest`, over **all 54 (asset, phase) cells of the six
unblinded study sessions** (17 winner-bearing, 361 D-021 winners). Receipt:
`artifacts/cache/port/m2/triage/E1D7_STAGE12_BACKTEST.tsv`.

### STAGE 1 — SEAT EXISTENCE (a feasibility object: no mirror to fail, like P025/P030)

| estimator | cells YES | with >=1 winner | precision | winner recall |
|---|---|---|---|---|
| ALL CELLS (day-6 behaviour) | 54 | 17 | **0.315** (the base rate) | 1.000 |
| S1a P030 rv1800 >= 100 | 41 | 15 | 0.366 | 0.967 |
| S1a P030 rv1800 >= 150 | 28 | 13 | 0.464 | 0.911 |
| S1a P030 rv1800 >= 200 | 15 | 9 | 0.600 | 0.676 |
| S1a P030 rv1800 >= 250 | 9 | 7 | **0.778** | 0.604 |
| S1b prior-cell $range >= 1000 | 32 | 10 | 0.312 | 0.548 |
| S1c unspent_sess >= $500 | 41 | 12 | 0.293 | 0.734 |
| S1d P025 runway_phase >= 12,000s | 54 | 17 | 0.315 | 1.000 |
| **S1\* = rv1800 >= 250 OR (rv1800 >= 150 AND prior-cell $range >= 1000)** | **16** | **11** | **0.688** | **0.884** |

**S1\* IS THE DECLARED SEAT RULE FOR TODAY** — 2.18x the base rate at 0.884 winner recall and
~2.7 seats/session, both thresholds settled on the POOLED CELL POOL and never on a replay
(ERA_NOTES §33/§41 method law). Both numbers are pre-existing: 250 and 150 are P030's own published
band edges (ERA_NOTES §64) and $1,000 is the D-021 bar itself. A cell with NO predecessor (the
session's first cell of an asset) can only be seated by the top vol band — declared, not improvised.
**ITS KNOWN COST, NAMED BEFORE THE DAY:** S1\* refuses 6 winner-bearing cells of the six sessions,
including **E1D6 HG/LONDON (17 winners, the day-6 best seat +$1,338.75) at rv1800 142.5 with a
prior-cell range of $975 — it misses BOTH thresholds by a hair.** ERA_NOTES §64 registered exactly
this risk when it refused to settle the threshold. Per-session seat counts under S1\*: 4/1/1/2/3/5.

### STAGE 2 — CELL SIDE (mirror-law tested, CC-M2-13.1, on the 17 winner-bearing cells)

| estimator | right | wrong | silent | accuracy | mirror | sessions LOST |
|---|---|---|---|---|---|---|
| **S2a P031 cross-asset fuel overhang >= 0.75** | **10** | **2** | 5 | **0.833** | 0.167 | **1** (E1D2) |
| S2a cross-asset fuel >= 0.65 | 11 | 4 | 2 | 0.733 | 0.267 | 2 (E1D2, E1D3) |
| S2a cross-asset fuel >= 0.85 | 8 | 2 | 7 | 0.800 | 0.200 | 1 (E1D2) |
| S2b P009 OWN-asset fuel >= 0.65 (DEAD) | 5 | 7 | 5 | **0.417** | 0.583 | 3 |
| S2c S10 outside-VA, \|d_POC\| >= $500 | 2 | 2 | 13 | 0.500 | 0.500 | 2 |
| S2c S10 outside-VA, \|d_POC\| >= $1000 | 2 | 0 | 15 | 1.000 | 0.000 | 0 (n=2, both E1D6) |
| S2d P029 phase prior (dead as a rule) | 13 | 4 | 0 | 0.765 | 0.235 | 2 (E1D2, E1D6) |

**REGISTERED BEFORE THE DAY, IN FULL:**
1. **S2a P031 is the round's best side object at six-session scale (0.833 decided) AND IT FAILS THE
   MIRROR LAW**, losing on 2021-07-02 — *the same single session that broke P029, and the only study
   session containing a scheduled release.* The conditional that would repair both is NOT TRADED and
   NOT PROMOTED (the P014/P026/P028 error has four corpses). S2a is traded today as the declared
   experiment with its failure on the record first, exactly as day 6 traded P029.
2. **P009's own-asset reading is confirmed ANTI-PREDICTIVE at six-session scale (0.417 vs its
   mirror's 0.583)** — day 6's one-hour sign inversion (§60) reproduces on 54 cells. This is the
   first population-scale support for P031's central claim.
3. **S10's SIDE reading (P028's field, magnitude-dead) does NOT generalise backwards**: 2 right /
   2 wrong at the $500 threshold over six sessions; its 2-for-2 record lives entirely in the session
   that minted it. It is demoted to the TIE-BREAK slot and its weakness is named here.
4. Declared side procedure per cell: **primary S2a (>= 0.75, with an explicit trapped-CONTRACT-count
   tie-break when two cross-assets disagree — the size of the overhang, not just its fraction);
   secondary S2c when S2a is silent; then the reader's own judgement, naming its fields.**
   Every cell gets a side call even when its seat call is NO, so the classifier lane gets labels for
   all nine cells and the side accuracy is measured on every winner-bearing cell.

### WHAT IS STILL NOT AVAILABLE — D20, the regime forecaster is VOID in E1 (CC-M2-17.2)
`predicted_day_type_prob`, `range_hat_vs_trailing`, `menu_hat` are `.` on all 1,388 rows of this
day, as CC-M2-17.2 ruled they would be. **No forecast_*.tsv or truth_*.tsv was opened** (D19
exposure class avoided by construction). The index is the only forecaster surface and it is empty.

---

## THE NINE CELLS (each committed before its own cell's first candidate row)

Format per cell: `#K ASSET/PHASE open | SEAT call + named evidence | SIDE call + named evidence`.

### #0 — HG / TOKYO, opens 00:00:32 — **SEAT: NO** · **SIDE: SHORT** (LOW)

**STAGE 1 — SEAT: NO.** `rv1800 = 144.2` at the at-open row `HG-20210709-000032-L` → **P030 band
100-150: 13 cells of the round, 2 with winners, 5.5% of all winners**. This is the session's FIRST
cell for HG, so there is no prior-cell travel to rescue it and the declared S1\* rule can only seat
it from the top vol band, which it misses by $106 of rv. Corroborating, not deciding: `S2/S3
day_type_so_far=INSIDE`, `range_so_far $200 = 9.3% of range_hat`, `cov_sess 8.7%` — a cold, unspent
open with `vol_regime MID rv5/rv66 0.706`, `ladder below_q10`, and `jump_frac 0.959` (essentially
all of the last half hour's variance is jump variance — P026 is dead so this gates nothing, but it
is what a 144 rv1800 is made of at 00:00:32). Feasibility is fine (`runway_phase 25,168s`,
`unspent_sess $2,107`) — **the refusal is about the tape's vol, not its clock.**

**STAGE 2 — SIDE: SHORT, LOW confidence.** S2a is formally SILENT (no cross-asset rows exist yet at
sec=32), so this is a PRIOR-SESSION-CONTEXT call, the class day 6 declared for a session's first
cell.
* **P031 read across the overnight boundary (declared as an EXTENSION of the object, which was born
  intra-session):** at 2021-07-08's close SI's NY phase carries `0.73 above / 0.27 below` of
  **33,947 contracts = ~24,800 trapped longs, by far the largest overhang on the board**, with phase
  sflow -397; NKD's NY carries `0.30/0.70` of 2,802 = ~1,960 trapped shorts. The two cross-assets
  disagree in sign, and the declared CONTRACT-COUNT tie-break gives it to SI by 12x → **SHORT**.
* AGAINST, named: HG's OWN prior NY phase closed **+$600 at pos 0.94 with sflow +646 and 0.01/0.99
  fuel (99% of 31,537 contracts trapped BELOW — short-covering demand)**, and HG gapped UP $200
  overnight (4.2690 → 4.2770). That is the strongest single fact pointing LONG and it is an
  OWN-ASSET fuel reading, which is exactly what the pre-registration measures at 0.417 (anti-
  predictive). Named, and not followed.
* AGAINST: P029 says TOKYO → LONG (13/4 pooled, dead as a rule, 2 sessions lost).
* Prior-session nets (C3 form): SI **-$1,350**, HG **-$1,000**, NKD **-$3,100** — the whole complex
  sold off on 07-08; the last-phase recoveries are the counter-fact above.

### #1 — NKD / TOKYO, opens 00:02:15 — **SEAT: NO** · **SIDE: SHORT** (LOW)

**STAGE 1 — SEAT: NO, the day's most confident refusal so far.** `rv1800 = 53.0` (rv900 53, rv300
53, rv60 39.5) at `NKD-20210709-000135-L` → **P030's BOTTOM band (<100): 13 cells, 2 with winners,
3.3% of the round's 361 winners.** No prior cell exists, so S1\* cannot seat it. Independently:
**the book is dead at the open — S8 `60s 1/1`, `5m 7/9`** — the P004 configuration that has refused
NKD's opens for six straight sessions (ERA_NOTES §56), and `vol_regime LOW rv5/rv66 0.535`,
`day_type INSIDE` at `5.6% of range_hat`, `spread 50 / cost_rt 55` (NKD's is the round's most
expensive round trip). Feasibility again is not the issue (`runway_phase 30,465s`).

**STAGE 2 — SIDE: SHORT, LOW confidence.**
* **S2a fires at the 0.65 threshold and is SILENT at the declared 0.75**: the only cross-asset tape
  in existence at sec=135 is HG/TOKYO's three rows — `fuel 81 above / 30 below / 121` (0.67) with
  phase sflow +14 on 121 and through-book 11 prints (1 bid / 10 ask). **121 contracts is not an
  overhang, it is a rounding error**, and I record that the fire is nominal.
* The load-bearing evidence is the same prior-session one as #0: **SI's 07-08 NY close carries
  ~24,800 trapped longs (0.73 of 33,947)**, the largest cross-asset overhang available, → SHORT.
* AGAINST, named: NKD's OWN prior NY closed **+$450 at pos 0.65 with 0.30/0.70 fuel** (own-asset
  reading, 0.417 accurate in the pre-registration — named and not followed); P029 says TOKYO → LONG;
  and NKD gapped UP ~$100 (27,740 → 27,760).

### #2 — SI / TOKYO, opens 00:53:22 — **SEAT: NO** · **SIDE: SHORT** (LOW-MED)

**STAGE 1 — SEAT: NO.** `rv1800 = 119.2` at `SI-20210709-003202-S`, and the shorter horizons are
COLLAPSING INTO the open — rv900 88.4, rv300 55.9, **rv60 25.0** — so the 119 is a stale half-hour
number and the tape at the decision second is quieter still. **P030 band 100-150 (5.5% of winners)**;
no prior cell; S1\* = NO. Book at the open: `60s 0/0`, `5m 10/13` — dead, P004. `day_type INSIDE` at
`5.7% of range_hat`. **SI's fvol row is REFUSED again this session** (`cov_sess=.`, `unspent_sess=.`,
`ladder=.`, `q10/q50=.`, `fvol_source=ATR14_RAW_FILL`) — the fourth study session in which SI's
coverage arithmetic does not exist (ERA_NOTES §16), so S1c is structurally silent for SI today and
the seat call rests on P030 alone.

**STAGE 2 — SIDE: SHORT, LOW-MED confidence.**
* **S2a P031 FIRES AND CLEARS EVEN THE 0.85 THRESHOLD: HG/TOKYO's fuel map is `312 above / 5 below /
  317` = 0.98 trapped ABOVE** with phase sflow +2 on 317. The fraction is extreme; the SIZE is not
  (317 contracts), so this is a weak instance of a strong pattern and I say so before the outcome.
* Corroboration from the overnight state: SI's own 07-08 NY overhang (0.73 above of 33,947) is an
  OWN-asset reading here and is therefore NOT used as evidence for SI's own cell (P009, 0.417).
  What is used: **every asset is lower on the session so far — HG -$175 at pos 0.00, NKD -$50 at
  pos 0.00, and both are printing their session lows at the cut.**
* AGAINST, named: P029 (TOKYO → LONG); S10 says `d_POC = -$50`, `in_VA = 1` — price is AT developing
  value, so S2c is silent and has nothing to add; `jump_frac 0.845`.

### #3 — HG / LONDON, opens 07:01:48 — **SEAT: NO** · **SIDE: SHORT** (MED)

**STAGE 1 — SEAT: NO, and this is the day's discipline test, named as such.** `rv1800 = 112.7`
(rv900 93.5, rv300 59.6, rv60 36.4) and the prior cell — HG/TOKYO, 67 rows — travelled a **$975
range**, i.e. **the exact configuration the pre-registration named as S1\*'s known cost: E1D6
HG/LONDON was rv 142.5 with a prior-cell range of $975 and held 17 winners and the day-6 best seat.**
The rule is followed as written: `rv1800 112.7 < 150` fails the top band by 137 and the second clause
by both of its terms, so **SEAT = NO**. FLIP THRESHOLD (CC-M2-5.8), stated before the outcome: this
cell is seated iff `rv1800 >= 250`, or `rv1800 >= 150` AND the prior cell travels $25 more. It misses
on rv by a wide margin, not by a hair — the $975 coincidence is the eye-catching half and the rv is
the deciding half. Supporting state: `day_type INSIDE` at 52.1% of range_hat, `cov_sess 48.8%`,
`unspent_sess $1,182`, `runway_phase 21,492s` — feasible on capacity, cold on volatility.

**STAGE 2 — SIDE: SHORT, MEDIUM confidence — the first cell of the day where the declared primary
instrument fires at real SIZE.**
* **S2a P031: SI/TOKYO's fuel map is `4,971 above / 110 below / 5,081` = 0.978 trapped ABOVE**, with
  SI **-$350 on the session sitting at `pos 0.00` (its session low) and phase sflow +365 on 5,081**
  — every buyer of Asian silver is underwater into the London open, which is precisely the day-6
  configuration that called HG/LONDON and NKD/LONDON correctly (ERA_NOTES §60). Clears the 0.85
  threshold.
* **The cross-asset tie-break is live and declared: NKD/TOKYO is the opposite sign** — `163 above /
  1,826 below / 2,010` (0.91 BELOW, a short-side overhang) with NKD +$150 at `pos 0.82`. **SI's
  4,971 trapped longs outweigh NKD's 1,826 trapped shorts 2.7:1 on the contract count**, so the
  tie-break gives it to SI → SHORT. This is the rule stated at pre-registration, applied.
* **P009 own-asset (DEAD, 0.417) says LONG**: HG's own TOKYO fuel is `1,907 / 11,452 / 13,359` =
  0.86 trapped BELOW. Under the day-6 inversion the own-asset overhang is anti-predictive, which
  points the same way as S2a; I name it as corroboration-by-inversion and give it no weight.
* **S10 leans SHORT below the declared threshold**: `dev POC 4.274 / VAH 4.288 / VAL 4.268`,
  `d_POC = +$412.5`, `in_VA = 0` — price is above the developing value area but by less than the
  $500 S2c needs, so S2c is SILENT. Recorded as a lean, not as evidence.
* AGAINST, named: P029 (LONDON → LONG); HG is **+$275 on the session at `pos 0.79`** and just made
  its session high; `S5 slope15m/5m/1m = -2.5/-10/+18.8` is turning up into the open (momentum terms
  are 3-for-3 value-destroying, so this is noted and not weighted); and the 60s/5m books are bid
  (`60s 16/23 sflow +7`, `5m 43/57 sflow +9`).

### #4 — SI / LONDON, opens 07:02:19 — **SEAT: NO** · **SIDE: LONG** (MED-HIGH)

**STAGE 1 — SEAT: NO, and this is the closest refusal of the day.** `rv1800 = 218.7` (rv900 189.6,
rv300 135.2, rv60 62.5) → **P030 band 150-250: 19 cells, 6 with winners, 30.7% of the round's
winners** — the second-best band. But the prior cell, SI/TOKYO, travelled only **$450 of range in 49
rows**, so S1\*'s second clause (`rv >= 150 AND prior-cell $range >= 1000`) fails on the tape's own
evidence that this asset has not been moving. FLIP THRESHOLD, stated before the outcome: this cell is
seated iff `rv1800 >= 250` (needs +31.3) **or** the prior cell travels $550 more. `unspent_sess` is
`.` (SI's fvol REFUSED all session), so S1c cannot speak; `runway_phase 21,461s` is ample.
**SEAT = NO by 31 points of realized volatility. It is the cell I would most like to trade and the
rule says the tape has not moved enough to pay the bar — recorded now so the post-mortem can score
the refusal honestly either way.**

**STAGE 2 — SIDE: LONG, MED-HIGH confidence — the day's cleanest instrument reading, and a
deliberate counter-trend call.**
* **S2a P031: BOTH cross-assets carry SHORT-SIDE overhangs and they agree, so no tie-break is
  needed.** HG/TOKYO `1,907 above / 11,452 below / 13,359` = **0.86 trapped BELOW**; NKD/TOKYO
  `163 / 1,826 / 2,010` = **0.91 trapped BELOW**. Under P031 the trapped side is the side that MUST
  transact: 13,278 cross-asset contracts are short into a market that has not broken, and their
  buy-back is demand to the assets that follow → **LONG SI**.
* **P009 own-asset (DEAD, 0.417) says SHORT** — SI's own TOKYO is `4,971 / 110 / 5,081` = 0.978
  trapped ABOVE. **This is the exact field, in the exact direction, that produced the round's worst
  call on day 6 (SI/LONDON called SHORT off its own 86% overhang; SI rallied +$1,450 with 14 LONG
  winners, seat -$930, MAE $1,775).** The pre-registration says the own reading is anti-predictive at
  six-session scale; the inversion agrees with S2a here. **Today I take the cross-asset reading and
  invert the own reading — the whole point of P031 — on the same cell that taught the lesson.**
* S10 leans LONG below threshold: `d_POC = -$162.5`, `in_VA = 0` (price under a developing value area
  whose POC is 25.95 against a 25.92 mid). S2c SILENT at the declared $500.
* AGAINST, named and strong: SI is **-$350 on the session at `pos 0.00`, printing its low into the
  London open**; `5m sflow -35 on 153` and `30m -76 on 386` are selling; `S5 slope15m/5m/1m =
  -11.7/-17.5/-12.5`, straight down. Every price/flow stream says SHORT and only the positioning
  says LONG. P029 also says LONG, for a reason (the phase) I give no weight.

### #5 — NKD / LONDON, opens 08:31:39 — **SEAT: YES** · **SIDE: SHORT** (MED-HIGH)  ← the day's first seat

**STAGE 1 — SEAT: YES, on both clauses of S1\* at once.** `rv1800 = 532.8` at
`NKD-20210709-030699-L` → **P030's TOP band (>= 250): 9 cells of the round, 7 with winners, 60.4% of
all 361 winners** — the single most concentrated state the ledger knows. And the prior cell delivers
independently: **NKD/TOKYO travelled a $4,150 range in 433 rows, net +$2,200, closing at `pos 0.94`**
— this tape is unambiguously paying $1,000 certificates. `runway_phase = 16,101s` clears P025's floor
by 4,101s.
**THE COUNTER-CASE, NAMED BEFORE THE CALL AND NOT OBEYED:** `day_type_so_far = EXPANDED`,
`range_so_far $4,250 = 238.1% of range_hat`, `cov_sess 242.4%`, **`unspent_sess = -$2,497`**,
`S9 surprise 2.381` on the prior row, `ladder at_or_above_q90`. **This is the same configuration as
day 6's NKD/NY cell** (EXPANDED 246.7%, cov 254%, unspent -$2,380) which produced exactly ONE winner.
S1c (`unspent_sess >= 500`) is the term that would refuse it — and S1c scored precision 0.293 against
a 0.315 base rate in the pre-registration, i.e. **it is a NON-signal, so it is not in S1\* and it does
not get to veto here.** If this cell turns out empty, S1c's re-instatement is the post-mortem's first
question. Also named: the book at the cell open is thin (`60s 1/3`, `5m 10/18`) — P004 will refuse the
opening rows at the MOMENT stage; that is stage 3's job, not the seat's.

**STAGE 2 — SIDE: SHORT, MED-HIGH confidence — all three instruments agree for the first time today.**
* **S2a P031: HG/LONDON's fuel map is `3,566 above / 737 below / 4,419` = 0.807 trapped ABOVE**, with
  HG **-$200 on its LONDON phase at `pos 0.16`** and 11 through-book prints (10 clearing the ASK).
  Clears the declared 0.75 threshold → SHORT. SI/LONDON is balanced (`2,007/1,645/3,652` = 0.55) and
  therefore silent; no tie-break needed.
* **S2c S10 FIRES, and at the largest magnitude available: `dev POC 27,690 / VAH 27,900 / VAL 27,530`
  with the mid at 28,210 → `d_POC = +$2,600`, `in_VA = 0`.** Price is $2,600 above the developing POC
  and outside the value area entirely — the identical shape to day 6's SI/NY (`d_POC +$1,362`,
  `in_VA=0` → 29 SHORT winners), which is S2c's only support in six sessions. Named as weak-but-firing.
* **P009 own-asset (DEAD) says LONG** (`130 above / 2,566 below / 2,696` = 0.95 trapped BELOW);
  inverted per the six-session 0.417, it agrees with SHORT.
* AGAINST, named and serious: **NKD is +$2,200 on the session and closed TOKYO at `pos 0.94`** — this
  is a strong uptrend and I am calling for it to fail; P029 says LONDON → LONG; `vol_regime HIGH
  rv5/rv66 1.704` says the move is live, not exhausted. **PRE-MORTEM (auto-logged, CC-M2-5.4): if
  this cell is a LONG cell, it is because a 238%-of-range_hat expansion in Asia was the START of a
  trend day and the "price far above value" reading is measuring the trend rather than an
  overextension — the mirror of the day-6 NKD/NY error, which is the reason to fear it.**

### #6 — HG / NY, opens 13:00:18 — **SEAT: YES** · **SIDE: LONG** (MED)  ← the day's cleanest instrument test

**STAGE 1 — SEAT: YES, on S1\*'s second clause.** `rv1800 = 231.0` (band 150-250, 30.7% of the
round's winners) **AND** the prior cell — HG/LONDON, 163 rows — **travelled a $2,125 range for a net
+$1,300**, comfortably above the D-021 bar: this asset is paying $1,000 moves today.
`runway_phase = 35,981s` with `exit_is_sess = 1` (the NY phase close IS the session close), the
longest runway on the board and the P025 configuration that has held 361/361 winners.
Named against, as on #5: `day_type EXPANDED`, `range_vs_hat 119.6%`, `cov_sess 111.9%`,
`unspent_sess = -$274.6`, `ladder at_or_above_q90` on the prior row — HG has already spent its
expected session range before NY opens. S1c would refuse; S1c is a 0.293-precision non-signal and is
not in S1\*.

**STAGE 2 — SIDE: LONG, MEDIUM confidence. THIS IS THE DAY'S CLEANEST SINGLE TEST: the declared
primary and secondary instruments DISAGREE, and the declared procedure gives it to the primary.**
* **S2a P031 (primary, 0.833 pre-registered) says LONG at size and with agreement**: SI/LONDON is
  `1,244 above / 10,455 below / 11,699` = **0.894 trapped BELOW** (10,455 underwater shorts in
  silver after a +$1,000 London rally) and NKD/LONDON is `255 / 1,358 / 1,613` = **0.842 BELOW**.
  Both cross-assets carry short-side overhangs, they agree, no tie-break is needed, and the larger is
  2.6x the size of any overhang read today. Their buy-back is demand to the asset that follows → LONG.
* **S2c S10 (secondary, 0.500 pre-registered) says SHORT and is OVERRULED BY THE DECLARED
  PROCEDURE**: `dev POC 4.279 / VAH 4.318 / VAL 4.257`, `d_POC = +$1,656`, `in_VA = 0` — HG is
  $1,656 above its developing POC and outside value. The procedure committed before the day says
  S2c speaks only when S2a is SILENT. It is not silent. **Recorded here so that if HG/NY is a SHORT
  cell, the post-mortem scores the PROCEDURE, not a free-hand choice.**
* P009 own-asset (DEAD) says LONG (`0.696 BELOW`); inverted it says SHORT. It is 0.417-accurate and
  gets no weight in either direction.
* AGAINST, named and heavy: **every price/flow stream at the boundary is selling** — `60s sflow -55
  on 250`, `5m -104 on 437`, `30m -36 on 2,068`, `S5 slope15m/5m/1m = -9.2/-27.5/-37.5`; HG is
  +$1,625 on the session at `pos 0.86` and rolling over into the open; and **P029 says NY → SHORT
  (13/4 pooled)**. Four independent things say SHORT and the one instrument with a six-session
  0.833 record says LONG.
* **PRE-MORTEM (auto-logged): if this cell is a SHORT cell, the mechanism is that a cross-asset
  short-side overhang is a LAGGING fact — the shorts were trapped by a rally that is now over, and
  the overhang I am reading as fuel is simply the footprint of the move that already happened.
  That is P027's failure mode (confirmation arrives after the move) wearing P031's clothes.**

### #7 — NKD / NY, opens 13:00:45 — **SEAT: YES** · **SIDE: LONG** (MED)

**STAGE 1 — SEAT: YES, on S1\*'s second clause.** `rv1800 = 223.6` (band 150-250) **AND** the prior
cell NKD/LONDON travelled **$1,400 of range for a net +$750** in 142 rows. `runway_phase = 35,954s`,
`exit_is_sess = 1`. Against, and worse than any cell today: `day_type EXPANDED`, `range_so_far
$4,962 = 278.1% of range_hat`, `cov_sess 283%`, **`unspent_sess = -$3,209`**, `vol_regime HIGH`.
Also named before the fact: **the book is dead at the open (`60s 1/1`, `5m 1/1`, `30m 12/25`) and
NKD's `cost_rt` is $55** — six sessions say NKD's phase opens without a counterparty (ERA_NOTES
§56), so the seat may exist and never become spendable at the MOMENT stage. A seat call is not a
take.

**STAGE 2 — SIDE: LONG, MEDIUM confidence.**
* **S2a P031: SI/LONDON `1,244 / 10,455 / 11,699` = 0.894 trapped BELOW (the same 10,455 underwater
  silver shorts read on #6) and HG/LONDON `8,853 / 20,281 / 29,134` = 0.696 BELOW — both
  cross-assets short-side, same sign, 41k contracts between them.** → LONG.
* S2c SILENT: `d_POC = +$137.5`, `in_VA = 1` — NKD is AT developing value, the profile has nothing
  to say.
* P009 own (DEAD) says LONG (0.842 BELOW); inverted, SHORT. No weight.
* AGAINST: P029 (NY → SHORT); the session is 283% of its expected range; `S5 slope5m/1m = -17.5/-25`.
* **CORRELATION DECLARED: #6 and #7 rest on the SAME SI/LONDON overhang, so they are one bet taken
  twice, not two independent confirmations.** If the reading is wrong, both seats lose together —
  which is exactly what the day-6 SI-TOKYO-overhang trio did in the other direction (2 right, 1
  catastrophically wrong).

### #8 — SI / NY, opens 13:04:12 — **SEAT: YES** · **SIDE: LONG** (LOW-MED, a DECLARED OVERRIDE of the primary instrument's literal form)

**STAGE 1 — SEAT: YES, the strongest seat call of the day, on BOTH clauses.** `rv1800 = 290.5` →
**P030's TOP band (>= 250, 60.4% of the round's winners)**, and the prior cell SI/LONDON travelled
**$1,600 of range for a net +$1,000** in 110 rows. `runway_phase = 35,747s` with `exit_is_sess = 1`.
Unlike #5/#6/#7 the capacity objection does NOT apply here: `day_type AT_RANGE` at **69.2% of
range_hat** — SI has spent two thirds of its expected range with the whole NY session to run.
(`cov_sess`/`unspent_sess` are `.`: SI's fvol is REFUSED all session again.)

**STAGE 2 — SIDE: LONG, LOW-MED confidence. THE PRIMARY INSTRUMENT'S LITERAL FORM SAYS SHORT AND I
AM OVERRIDING IT; both readings are recorded and both will be scored (CC-M2-12.6).**
* **S2a AS BACKTESTED (max overhang FRACTION over each other asset's latest phase block; 0.833 over
  six sessions) says SHORT** — but only because HG's NY phase, **two rows and 80 contracts old**,
  reads `73 above / 7 below` = 0.91. **This is the "121 contracts is not an overhang, it is a
  rounding error" objection I wrote at cell #1 this morning, before any outcome was known, now
  deciding a cell.**
* **THE SIZE-AWARE READINGS SAY LONG, and I measured them before calling this cell** (receipt in the
  post-mortem): the same estimator with a 200-contract floor scores **6 right / 1 wrong = 0.857 with
  zero sessions lost** over the six sessions, and it fires here on **NKD/LONDON `255 / 1,358 / 1,613`
  = 0.842 trapped BELOW → LONG**; the contract-count tie-break form (0.750) also says LONG. The
  meaningful overhangs on the board are **HG/LONDON's 20,281 trapped shorts (0.696 BELOW of 29,134)**
  and NKD/LONDON's 1,358 — the complex is short into a London rally, which is the same fact that
  called #6 and #7.
* P009 own-asset (DEAD) says LONG (SI/LONDON `1,244 / 10,455 / 11,699` = 0.894 BELOW); inverted it
  says SHORT. No weight, both directions named.
* S2c SILENT and leaning the other way: `d_POC = +$362.5`, `in_VA = 0` — above value but $137 short
  of the declared $500 threshold. On day 6 this same field at `+$1,362` called SI/NY SHORT into 29
  winners; today it is a third of that size and does not fire. Named because it is the closest
  analogue in the ledger.
* AGAINST, named and heavy: **the boundary flow is selling hard — `60s sflow -46 on 62` (74%),
  `5m -88 on 284`, `30m -72 on 719`** — SI is +$600 on the session at `pos 0.91`, and **P029 says
  NY → SHORT (13/4)**. Three of the day's nine calls now go against a live sell stream.
* **PRE-MORTEM (auto-logged): if SI/NY is a SHORT cell, the override is what lost it — the 80-contract
  HG/NY fire will have been the correct read of "the asset that just opened is already trapped long",
  and the size floor I applied will have thrown away the freshest information on the board in favour
  of a stale London number.**

---

## SUMMARY OF THE NINE COMMITTED CELL CALLS (each committed before its cell's first candidate row)

| # | cell | open | SEAT | rv1800 (P030 band) | prior-cell $rng | SIDE | conf | primary side evidence |
|---|---|---|---|---|---|---|---|---|
| 0 | HG/TOKYO | 00:00:32 | **NO** | 144.2 (100-150) | — | SHORT | LOW | prior-session SI NY overhang 0.73 of 33,947 |
| 1 | NKD/TOKYO | 00:02:15 | **NO** | 53.0 (<100) | — | SHORT | LOW | same; S2a nominal on 121 contracts |
| 2 | SI/TOKYO | 00:53:22 | **NO** | 119.2 (100-150) | — | SHORT | LOW-MED | HG/TOKYO 0.98 above (317) |
| 3 | HG/LONDON | 07:01:48 | **NO** | 112.7 (100-150) | 975 | SHORT | MED | SI/TOKYO 0.978 above (4,971 trapped longs) |
| 4 | SI/LONDON | 07:02:19 | **NO** | 218.7 (150-250) | 450 | LONG | MED-HIGH | HG 0.86 + NKD 0.91 trapped BELOW, agreeing |
| 5 | NKD/LONDON | 08:31:39 | **YES** | 532.8 (**>=250**) | 4,150 | SHORT | MED-HIGH | HG/LONDON 0.807 above + S10 d_POC +$2,600 outside VA |
| 6 | HG/NY | 13:00:18 | **YES** | 231.0 (150-250) | 2,125 | LONG | MED | SI/LONDON 0.894 BELOW (10,455 trapped shorts) |
| 7 | NKD/NY | 13:00:45 | **YES** | 223.6 (150-250) | 1,400 | LONG | MED | same SI/LONDON overhang + HG/LONDON 0.696 BELOW |
| 8 | SI/NY | 13:04:12 | **YES** | 290.5 (**>=250**) | 1,600 | LONG | LOW-MED | HG/LONDON 20,281 + NKD/LONDON 0.842 trapped BELOW (override) |

**FOUR SEATS, FIVE ABSTENTIONS.** Day 6 spent nine seats in nine cells and four were empty; today
the declared stage-1 rule refuses five cells outright — **including HG/LONDON, whose day-6 twin was
the best seat of that session.** Sides: 4 SHORT (0,1,2,3,5) and 4 LONG (4,6,7,8) — the day is not a
single directional bet, and the LONG cluster (#6/#7/#8) rests on ONE fact (the complex is short into
the London rally), declared as one bet taken three times.

**PROSPECTIVE PATTERN REGISTRATION (CC-M2-4.3):** P030 (S1a), the prior-cell-travel term (S1b, new
this day), P025 (S1d + T2), P031 (S2a, primary), P028's field as a SIDE reading (S2c, secondary),
P004 (T1), P023's de-signed magnitude floor (T4/T5-repaired), P018 (V3), the V2 fuel-overhang family.
P029 and P009 are run only as scored REFERENCE estimators. Anything not in this list is post-hoc.

---

## UNBLINDED RESULT (opened only after the seal commit `02304f6` / content `da74ecc`)

**THE DAY: 123 D-021 winners in 1,388 candidates (8.9%), AND ALL 123 ARE LONGS.** Five of the nine
cells carry winners. Per asset: NKD 79 (mean +$9.45, walled 0.578), SI 22 (-$38.33, 0.419), HG 22
(-$41.93, 0.337). Day DP ceiling **$11,636** (SI 3,010 / HG 3,066 / NKD 5,560).

| # | cell | truth | winners | SEAT call | SEAT right? | SIDE call | SIDE right? | seat spent | seat close $ |
|---|---|---|---|---|---|---|---|---|---|
| 0 | HG/TOKYO | **NONE** | 0 | NO | **✓** | SHORT | — | — | — |
| 1 | NKD/TOKYO | **LONG** | **68** | NO | **✗** | SHORT | **✗** | — | — |
| 2 | SI/TOKYO | **NONE** | 0 | NO | **✓** | SHORT | — | — | — |
| 3 | HG/LONDON | **LONG** | 22 | NO | **✗** | SHORT | **✗** | — | — |
| 4 | SI/LONDON | **LONG** | 15 | NO | **✗** | **LONG ✓** | ✓ | — | — |
| 5 | NKD/LONDON | **LONG** | 11 | YES **✓** | ✓ | SHORT | **✗** | 08:53:38 S | **-955.00** (walled) |
| 6 | HG/NY | **NONE** | 0 | YES | **✗** | LONG | — | 13:00:18 L | -130.00 |
| 7 | NKD/NY | **NONE** | 0 | YES | **✗** | LONG | — | 13:51:19 L | +182.50 |
| 8 | SI/NY | **LONG** | 7 | YES **✓** | ✓ | **LONG ✓** | ✓ | 13:09:22 L | **+470.00** |

**SEAT-CALL ACCURACY: 4 of 9 = 0.444, against 0.556 for "seat every cell" (day 6's behaviour).**
Precision of the four YES calls: **0.500** (pre-registered 0.688). **Winner recall: 18 of 123 =
0.146, against a pre-registered 0.884.** The stage-1 rule did not merely underperform — it inverted.
**SIDE-CALL ACCURACY: 2 of 5 = 0.400; the MIRROR of my calls scores 0.600.** Estimator scoreboard on
the same five cells: **P029 4/5 = 0.800** (the object CC-M2-17.6 killed as a rule); **S2a/P031, the
day's declared primary, 1 right / 3 wrong / 1 silent = 0.250**; **P009's OWN-asset reading, DEAD
twice over, 3 right / 1 wrong = 0.750**; S2c 0/1.

**WHAT KILLED STAGE 1, PRECISELY: THE CELL-OPEN ANCHOR GOES STALE.** NKD/TOKYO holds 68 of the day's
123 winners (median certificate **+$3,020**, max +$3,845) and its `rv1800` AT THE CELL OPEN (00:02:15)
was **53.0 — P030's bottom band.** Its winners run 04:09:13-07:55:42, **four to eight hours after
that reading**, and at their own decision seconds `rv1800` is **278-602, the top band.** The TOKYO
phase is 8.5 hours long; a volatility nowcast taken at its first second is not a statement about it.
P030's day-6 measurement worked because five of its six winner cells were LONDON/NY cells whose
winners arrive soon after the open. **The object is right and the ANCHOR is wrong.**

**AND THE PRE-REGISTERED COST CAME DUE, TWICE.** HG/LONDON (22 winners, certificates $1,045-$1,782)
was refused at `rv1800 112.7 / prior-cell $975` — the same configuration, on the same cell, that the
pre-registration named as S1\*'s known cost on 2021-07-08. SI/LONDON (15 winners) was refused at
`rv1800 218.7 / prior-cell $450` — **and its SIDE call was LONG and CORRECT.** The reader called the
side right and refused the seat.

**THE ONE STAGE-1 TERM I DECLARED A NON-SIGNAL AND DROPPED WOULD HAVE BEEN THE BEST OF THEM:**
S1c (`unspent_sess >= $500`, or `.` when SI's fvol is refused) seats 6 cells, 4 with winners
(precision 0.667) at **winner recall 0.911** — it refuses HG/NY and NKD/NY, two of my three empty
seats, and keeps NKD/TOKYO, HG/LONDON and SI/LONDON. Its 0.293 precision over the six prior sessions
was measured on a pool where it almost never fired; today it fired on the exact cells that were
grossly over-extended (`cov_sess` 242-283%, `unspent_sess` -$2,497/-$3,209) and it was right about
all of them.

# THE GOAL-PATH CENSUSES 1–4

`PORT-M2-GOALPATH-V1` · engine/port_m2/goalpath.py · tests engine/port_m2/test_goalpath.py
Eras E2–E6 (2022-01 → 2024-06), 1,929 asset-sessions, SI/HG/NKD.
Every number below is produced by the committed code from the committed matrix and
the SANE mid grid; nothing is restated from prose.

---

## HEADLINE

**All four censuses close negative against the bars, and two of them close
negative against their own hypothesis.**

1. **The ambiguity veto is falsified, with the sign reversed.** Refusing
   two-sided moments does not raise precision — it *lowers* it. One-sided
   moments carry 27.8 % of daily seatable winner dollars, and their winner rate
   is **0.69×** the population's, not above it (E2–E6, n = 816,967).
2. **The day-side call at day grain is null.** Walk-forward accuracy 0.446–0.559
   with day-clustered CIs straddling the majority base in **every** era and both
   causal arms; the shuffled control sits in the same band.
3. **Class-mix seat allocation adds ~$0.** Allocating the 3 seats/day by
   train-block class economics moves $/session/asset by **−$4.3 … +$10.4**
   against the status quo, one −$200 blow-up included.
4. **The confirmation-strength / trend trade class — priced exactly, 153
   entry × stop × exit cells × 5 eras = 765 cell-era rows over 775,530 confirmed
   extremes — never reaches the bars.** Zero of 765 rows clear the D-021 $600/trade
   floor (max $175.68). Zero of 2,334 stacked configurations reach $1,500/session
   (max $308.54). The median cell earns **−0.25 R**.

**The one thing that did work, and by how much.** The user's trend variant with
the delay census's own post-window decidability block used as a gate is
positive, walk-forward, in all four scoreable eras:
`TREND_1800|EXT|TRAIL_1.0R`, keep the top 5 % of gate scores → **+$28.76 / +$20.35
/ +$63.21 / +$157.01 per trade** (E3/E4/E5/E6) against an ungated **−$17.41 /
−$18.77 / −$24.58 / −$8.23**. Stacked with the model's 3-seat schedule the best
configuration found anywhere is

| | |
|---|---|
| configuration | `TREND_3600 · stop = confirmed extreme ±2 ticks · trail 1.0R · gate top-5 % · model top-3/asset/day` |
| $/session/asset | E3 $5.88 · E4 $131.38 · E5 $32.25 · **E6 $308.54** (mean $119.5) |
| day-clustered CI | E3 [−84.8, 100.6] · E4 [8.9, 262.6] · E5 [−70.1, 133.3] · E6 [60.2, 560.3] |
| $/trade | $4.62 / $109.67 / $24.65 / **$254.64** |
| seats/session | 1.20–1.31 · MDD $272–404 (inside D-030) |
| vs D-048 $2,000 | **0.003× / 0.066× / 0.016× / 0.154×** |
| shuffled-gate control | −$3.62 / $21.51 / $21.09 / $16.09 — the gate is doing the work |
| same cell, no gate | −$31.72 / −$10.74 / −$37.02 / −$43.75 — negative in every era |

Against the *like-for-like* status quo (the D-021 contract — confirmation entry,
$900 wall, phase close — under the identical selection model: $35 / $64 / $38 /
$53 per session) the gated trend arm is **≈2.5× better**. Against the goal it is
**16×–300× short**.

---

## INSTRUMENT RECEIPTS

* **D = 0 identity.** `DELAY_0|EXT|PHASE` reproduces the committed roster
  certificate *exactly* on the 34,621 real E6 rows where neither the structural
  stop nor the $900 wall fired: max |diff| < 1e-6 (test `t09`).
* **The tau-tensor identity.** The m1 label tensors
  (`artifacts/cache/port/m1/skel`, 200 rungs × 0.02 ATR, both sides, 2 anchors)
  and this census price the same object: 5,600 / 5,600 first-passage times
  (SI 2022-01, 400 candidates × 7 rungs × up and down) recomputed identically
  from the SANE mid grid (`goalpath.py --tau-proof`, receipt in
  `artifacts/cache/port/m2/goalpath/tau_proof.receipt.json`).
  **Where the tensor grid would have forced rounding, and why it never does
  here:** a tensor rung is `round_half_up(k · 0.02 · ATR14$/mult, tick)`
  (`engine/cpp/qr_skel/src/geom.cpp:34`). A structural stop is *2 ticks beyond a
  swing price* and is not a ladder rung, so census 4 prices on the grid the
  tensors are *built from* (`s.vt`/`s.vm`) rather than on the ladder — exact, no
  rung rounding anywhere.
* **Fixtures.** 16 assertions green in `engine/port_m2/test_goalpath.py`, all
  driving the shipping `_cont_one` through the production `assemble.load_session`
  seam: the phase-close arithmetic, the fill-at-the-stop convention, the trailing
  exit floored at the initial stop, the swing-structure definition, the trend
  gate's prevailing-direction refusal, the displacement control, the
  non-positive-leg refusal, the one-position replay, the day-clustered bootstrap.
* **Red-first controls.** (a) *displaced entry*: every trigger moved +600 s, the
  whole of E6 re-priced; (b) *shuffled label*: the veto, the day-side call and
  the gate each re-run on shuffled labels/scores.
* **Fill convention.** Entry at the trigger second's SANE mid; a structural stop
  fills **at its own level** — the same convention the $900 wall uses
  (`c_c_roster.certificates` returns exactly `−W − cost`); `cost_rt` (session
  median two-sided spread + $5.00) is charged on every trade.

---

## CENSUS 1 — THE AMBIGUITY VETO · **FALSIFIED, SIGN REVERSED**

`GOALPATH_AMBIGUITY.tsv` · `GOALPATH_AMBIGUITY_VETO.tsv` · `GOALPATH_AMBIGUITY_ORACLE.tsv`

Two-sidedness = an opposite-side candidate in the same (asset, day, phase) cell,
within K\* (SI 180 s / HG 120 s / NKD 150 s, `info_ceiling._kstar`) and within
0.5 × ATR14 of the entry mid — the committed wall-pair geometry.

**The one-sided share of daily seatable dollars** (D-021 winners, E2–E6,
45,953 winners / $80.65 M):

| | within K\* | within 2K\* |
|---|---|---|
| one-sided, share of winners | 30.5 % | 15.4 % |
| one-sided, share of winner **dollars** | **27.8 %** | 13.8 % |
| wall-pair-adjacent share of winner dollars | | **86.2 %** |

Per asset (K\*, dollars): SI 19.3 %, HG 41.8 %, NKD 32.6 %.
DP-scheduled **oracle seats** are 30.4 % (SI) / 48.8 % (HG) / 33.9 % (NKD)
one-sided at 2K\*.

**The veto's cost/benefit on the whole population** — the decisive table:

| veto | kept | winner rate | **lift** | wall rate | winner $ kept | winner $ forfeited |
|---|---|---|---|---|---|---|
| none | 100 % | 0.0563 | 1.00 | 0.390 | $80.65 M | $0 |
| one-sided ≤ K\* | 43.9 % | 0.0390 | **0.693** | 0.357 | $22.39 M | **$58.26 M** |
| one-sided ≤ 2K\* | 23.7 % | 0.0366 | **0.650** | 0.340 | $11.14 M | **$69.52 M** |

The veto costs $58 M of winner dollars to keep $22 M **and lowers precision by
31 %**. Two-sided moments are the *rich* ones: a contested level is where the
paying move happens. The hypothesis is refuted in every era and every asset.

**On the teacher's 15 sealed hand takes** (`GOALPATH_TEACHER_TAKES.tsv`,
`GOALPATH_TEACHER_FILTERS.tsv`):

| arm | n | total | $/trade | walls | D-021 winners |
|---|---|---|---|---|---|
| all 15 | 15 | **$4,506.25** | $300.42 | 7 | 4 |
| one-sided ≤ K\* | 8 | $822.50 | $102.81 | 4 (−3) | 2 (−2) |
| one-sided ≤ 2K\* | 3 | $1,760.00 | $586.67 | 1 (−6) | 1 (−3) |

It removes 3 of 7 wrong-side walls but forfeits 2 of 4 winners and two-thirds of
the dollars. (The 2K\* row is n = 3 — noise, not a result.)

> **Two committed-number corrections fall out of this census, both verified from
> the matrix certificate, not from prose.** (1) The pooled teacher record is
> **$4,506.25 / $300.42 per trade**, not the $4,481 / $299 in `STATE.md:10` and
> `JOURNAL.md`; the committed figure multiplied the all-days $546/trade rate by
> the blind take count instead of summing the ledger. The conclusion is
> unaffected. (2) The **r2x per-take dollars, which were never persisted
> anywhere**, are recovered here: SI-20240429 −$930, SI-20240430 −$930,
> HG-20240501 −$917.50, SI-20240502 +$3,082.50, HG-20240503 +$1,057.50
> (sum +$1,362.50, matching the journal's aggregate).

---

## CENSUS 2 — THE DAY-SIDE CALL AT DAY GRAIN · **NULL**

`GOALPATH_DAYSIDE.tsv` · 2,567 (asset, day) rows.

Label: which side's D-021 winners carry more dollars that day. Base rates —
long 32.1 %, short 29.8 %, **undecided 38.1 %** (no winner-dollar differential at
all: a base rate worth carrying forward on its own).

Two strictly causal arms:

* **AT_TOKYO_CLOSE** — 35 features: the session's own Tokyo window (return,
  range, realised vol, position-in-range, 30-min slope, SANE fraction), the other
  two assets' Tokyo blocks (the cross-asset layer at day grain — never measured
  before), strictly-prior-session structure (return/range/TR/close-position/gap,
  all ATR-normalised), clock, and the 13 guarded regime-forecaster fields.
  Label scored over the rest of the day.
* **AT_SESSION_OPEN** — prior session + forecaster + clock only, **no
  current-session tape at all**; label over the whole session (this arm does not
  cede NKD's Tokyo hours).

| arm | E2 | E3 | E4 | E5 | E6 |
|---|---|---|---|---|---|
| AT_TOKYO_CLOSE accuracy | .508 | .534 | .556 | .454 | .518 |
| … day-clustered CI | [.446,.570] | [.472,.598] | [.487,.626] | [.383,.531] | [.452,.583] |
| … majority base | .529 | .514 | .564 | .536 | .539 |
| … shuffled control | .448 | .458 | .551 | .526 | .469 |
| AT_SESSION_OPEN accuracy | .490 | .559 | .500 | .506 | .446 |
| … majority base | .525 | .504 | .552 | .530 | .517 |

**Not one era, arm or asset beats its own majority base with a CI that excludes
it.** The mean predicted probability sits at 0.43–0.54 — the model is calling a
coin.

**Applied as a filter** it is actively harmful: on the teacher's 15 takes it
keeps 6, removes 4 of 7 walls and **all 4 winners**, for −$366/trade. Stacked in
census 4 (`GOALPATH_STACKED.tsv`) the `DAYSIDE` arm is indistinguishable from
`SHUFFLED_DAYSIDE` throughout.

---

## CENSUS 3 — CLASS-MIX SEAT ECONOMICS · **≈ ZERO**

`GOALPATH_CLASSMIX.tsv` · `GOALPATH_CLASSCELLS.tsv` · `GOALPATH_SEAT_ALLOCATION.tsv`

Per-class card (E6, all assets; selection = walk-forward GBT on
`y_retg_rank_phase`, top-3/asset/session):

| class | fires/session | winner rate | winner mean cert | n selected | precision@sel | $/take@sel |
|---|---|---|---|---|---|---|
| SHOCK-RESOLUTION | 0.62 | .1008 | $2,102.81 | 0 | – | – |
| LEVEL-FIRST-TEST | 1.85 | .0802 | $1,864.74 | 1 | 0 | $257.50 |
| US-CLOCK | 16.9 | .0917 | $2,029.68 | 17 | .059 | −$424.12 |
| OPEN-DYNAMICS | 9.8 | .0726 | $1,826.46 | 14 | .143 | $269.11 |
| RECLAIM | 16.7 | .0779 | $1,978.24 | 59 | .136 | $302.94 |
| REVERSAL-CONFIRMATION | **395.0** | .0577 | $1,870.65 | 1,061 | .042 | $57.85 |
| ALL | 441.0 | .0602 | $1,884.54 | 1,152 | .048 | $66.03 |

The rich classes are real (RECLAIM and OPEN-DYNAMICS run 3× the baseline
precision-at-selection and 4–5× the $/take) **and they are 6 % of the roster**.
The seat-allocation table asks the only question that matters — reallocate the 3
seats/day by train-block class economics, same selection skill:

| era | best class policy | $/session | status quo | **delta** |
|---|---|---|---|---|
| E2 | top-3 classes | $160.78 | $150.42 | **+$10.36** |
| E3 | top-1 class | $37.47 | $35.15 | +$2.32 |
| E4 | top-4 classes | $65.93 | $63.61 | +$2.32 |
| E5 | top-1 class | $41.28 | $37.66 | +$3.62 |
| E6 | top-2 classes | $60.40 | $53.39 | +$7.01 |
| E6 | top-1 class (OPEN-DYNAMICS alone) | −$11.24 | $53.39 | **−$64.62** |

Concentrating on the rich classes buys **+$2 … +$10 per session** and one −$65
hole. The reason is throughput, not quality: the rich classes cannot fill the
seats, so the schedule falls back to REVERSAL-CONFIRMATION anyway.

---

## CENSUS 4 — CONFIRMATION-STRENGTH DIRECT ENTRIES AND THE TREND ARM

`GOALPATH_CONT_ECON.tsv` (765 rows) · `GOALPATH_CONT_REPLAY.tsv` ·
`GOALPATH_TREND_GATE.tsv` · `GOALPATH_STACKED.tsv` (2,334 rows)

### What was built

**Universe** — every CONFIRMED extreme, winners *and* losers: all G1/G2
candidates (`fam_G1|G1_FINE|G1_FAST_OPEN|G2_REJECT|G2_RECLAIM`) in E2–E6 with a
causal pivot: **775,530** candidates, 94.9 % of the roster. E6 alone prices
11.9 M trades across the cell grid.

**The confirmed extreme** = `dec_sec − pivot_age_sec`, the committed matrix
feature ("the most recent CAUSAL ZigZag pivot of the faded type",
`pattern_lib.py:123`); its price is the SANE mid at that second.
**The reclaim level** L = the SANE mid at `conf_sec` (the second the ZigZag
retrace threshold was met). A *re-break* is > 2 ticks through L.

**17 direct entries** (market at the trigger second, never a pullback limit):

| family | trigger |
|---|---|
| `HOLD_T`, T ∈ {60,180,300,600} s | the reclaim level HELD T s with no re-break; entry at T-expiry |
| `LEG_R`, R ∈ {0.5,0.75,1.0} × ATR14 | the reversal leg has travelled R from the extreme **and** the reclaim held; entry at the crossing second |
| `DELAY_D`, D ∈ {0,30,60,120,180,300,600} s | the committed delay grid from the roster's decision second |
| `TREND_D`, D ∈ {900,1800,3600} s | t+D after **confirmation**, taken only while the reversal is still prevailing (price on the reversal side of L at t+D); exits at the entry's **own** phase close (the rolled horizon) |

**3 structural stops** (never the $900 wall; cash risk measured per trade):
`EXT` = the confirmed extreme ∓2 ticks · `RECLAIM` = L ∓2 ticks ·
`SWING` = the nearest retracement structure behind the entry ∓2 ticks — the
adverse extreme since the last favourable extreme, which *is* the path
skeleton's own construction (`c_c_roster._emit_candidate` builds the skeleton as
the prefix-maxima of f and of −f). A stop closer than 2 ticks is refused as
unexecutable; a structure already violated at the trigger refuses the trade.

**3 exits**: phase close · trailing 1.0 R · trailing 1.5 R (the trail is floored
at the initial stop, so it never loosens).

### The measured cash risk — the user's prediction held

Median risk per trade, E2→E6, versus the $900 wall it replaces:

| entry | stop = SWING | stop = RECLAIM | stop = EXT |
|---|---|---|---|
| `DELAY_0` | ~$47 | ~$60 | $175–212 |
| `HOLD_300` | ~$62 | ~$95 | $250–300 |
| `TREND_900` | ~$69 | ~$132 | ~$233 |
| `TREND_1800` | **$87–100** | ~$176 | $350–425 |
| `TREND_3600` | ~$93 | ~$215 | $412–512 |

**Structural risk stays small even at D = 3,600 s** — the SWING stop is a 9–10×
reduction on the wall, and its MAE p90 ($137–175) sits comfortably inside D-021's
$300 band. The prediction was correct. It simply does not pay.

### The complete economics — and where it fails

Across all **765** (era × cell) rows:

* **0** rows reach the D-021 $600/trade floor. The maximum anywhere is
  **$175.68** (`LEG_1|RECLAIM|TRAIL_1.0R`, E3, n = 728, on a **median risk of
  $2,062** — i.e. bought by taking 2.3× the wall in risk, which breaks the D-021
  MAE band and the D-030 MDD target).
* **56 / 765** rows have a positive mean R-multiple. The **median cell earns
  −0.2465 R**; the best is +0.43 R (`LEG_1|SWING|PHASE`, E3, n = 151).
* Win rate rises exactly as the delay census predicted — `TREND_3600|EXT` runs
  0.383–0.394 versus `DELAY_0|EXT` at 0.229–0.245 — **and the dollars do not
  follow**: −$11.89 vs −$22.44 per trade in E6. More confirmation buys accuracy
  and pays for it in give-back, one for one.
* Take-everything replays (`GOALPATH_CONT_REPLAY.tsv`) top out at
  **$75.13/session/asset** in E6 with a CI of [−61, +228].

Per-era stability of the flagship cells (mean $/trade, take-everything):

| cell | E2 | E3 | E4 | E5 | E6 | median risk |
|---|---|---|---|---|---|---|
| `DELAY_0\|EXT\|PHASE` | −31.08 | −22.71 | −24.20 | −23.98 | −22.44 | $175–212 |
| `HOLD_300\|EXT\|TRAIL_1.0R` | −29.28 | −28.95 | −27.12 | −25.48 | −23.96 | $250–300 |
| `TREND_1800\|SWING\|TRAIL_1.0R` | −32.67 | −27.46 | −24.04 | −26.84 | −25.27 | $87–100 |
| `TREND_1800\|EXT\|TRAIL_1.0R` | −29.58 | −17.41 | −18.77 | −24.58 | −8.23 | $350–425 |
| `TREND_3600\|EXT\|TRAIL_1.0R` | −31.30 | −15.02 | −19.44 | −28.40 | −11.89 | $412–512 |
| `LEG_1\|RECLAIM\|TRAIL_1.0R` | −149.33 | +175.68 | +75.64 | +131.77 | +85.37 | $1,987–2,209 |

The pattern is uniform: **the only cells that make money per trade are the ones
that risk 4–10× more cash per trade**, and their R-multiples are still ≈ 0.

### The decidability gate — the one positive result

The trend entries were gated on the `[conf, entry]` post-window block computed
with the delay census's own `m2_delay._post_path` arithmetic (14 fields: net,
MFE, MAE, give-back, efficiency, realised vol, up-fraction, 30 s slope, time-to-
extremes, spread, imbalance and its delta, SANE fraction), fitted walk-forward
(train = all prior eras) and applied forward.

$/trade by keep-fraction, `TREND_1800|EXT|TRAIL_1.0R`:

| era | top 5 % | top 10 % | top 30 % | ungated |
|---|---|---|---|---|
| E3 | **+28.76** | +9.80 | −8.05 | −17.41 |
| E4 | **+20.35** | +15.03 | −11.44 | −18.77 |
| E5 | **+63.21** | +18.22 | −9.61 | −24.58 |
| E6 | **+157.01** | +77.71 | +14.20 | −8.23 |

Monotone in the keep-fraction, positive in all four scoreable eras, and the
shuffled-gate control lands at $−4 … $+22/session. This is a real, out-of-era
signal — **and it is the AUC-value identity again**: the gate's job is to spot
the moves already working, and the price of that knowledge is the move already
made. It buys $20–157/trade against a $600 floor.

### Red-first controls

**Displaced entry** (+600 s on every trigger, all of E6):

| cell | as measured | displaced +600 s |
|---|---|---|
| `TREND_1800\|EXT\|TRAIL_1.0R` | −$8.23 | −$4.26 |
| `TREND_3600\|EXT\|TRAIL_1.0R` | −$11.89 | −$11.79 |
| `TREND_900\|SWING\|TRAIL_1.0R` | −$26.49 | −$27.79 |
| `DELAY_120\|EXT\|PHASE` | −$21.97 | −$17.95 |
| `HOLD_300\|EXT\|TRAIL_1.0R` | −$23.96 | −$16.98 |
| `LEG_1\|RECLAIM\|TRAIL_1.0R` | +$85.37 | +$91.46 |

**Displacing every entry by ten minutes changes nothing, and half the time
improves it.** The trigger structure — held level, travelled leg, elapsed
confirmation — carries no entry-timing edge at all; what the cells measure is
the ambient drift-and-vol of the phase, priced through whatever risk the stop
happens to take.

**Shuffled label** — every filter matched against its own shuffled twin on the
identical (era, cell, selection) configuration, $/session/asset:

| filter vs its shuffled twin | pairs | mean delta | median delta | fraction the real filter wins |
|---|---|---|---|---|
| `VETO_K` vs `SHUFFLED_VETO` | 210 | **−$34.51** | −$10.98 | 0.40 |
| `DAYSIDE` vs `SHUFFLED_DAYSIDE` | 210 | **−$15.59** | −$9.42 | 0.44 |
| `GATE_TOP5` vs `SHUFFLED_GATE_TOP5` | 72 | **+$111.00** | +$99.75 | **0.99** |
| `GATE_TOP10` vs `SHUFFLED_GATE_TOP10` | 72 | **+$128.06** | +$128.80 | **0.97** |

The veto and the day-side call each perform *worse than random subsampling of
the same size* — they are not weak signals, they are inverted ones. The
decidability gate beats its shuffled twin on 71 of 72 configurations. That
contrast is the census in one table.

---

## VERDICT — THE BEST STACKED CONFIGURATION

2,334 configurations were replayed one-position-per-asset with day-clustered CIs
(cell × {no filter, veto K\*, veto 2K\*, day-side, veto+day-side, gate top-5/10/30 %,
gate+veto, gate+day-side, and the three shuffled controls} × {all entries,
model top-3/asset/day}).

**Zero reach $1,500/session/asset. Zero reach $600/trade at n ≥ 50. The maximum
$/session/asset found anywhere is $308.54.**

**The best configuration:**

```
entry class   TREND_3600  (direct market entry 3,600 s after confirmation,
                           taken only while the reversal is still prevailing)
side filter   none         (the day-side call is null — census 2)
veto          none         (the ambiguity veto is falsified — census 1)
class alloc   none         (worth +$2…+$10 — census 3)
gate          top 5 % of the [conf, entry] decidability score, walk-forward
stop          the confirmed extreme ∓2 ticks   (structural, per-trade cash risk)
exit          trailing 1.0 × structure
schedule      3 seats/asset/day, one position per asset
```

| era | $/session/asset | day-clustered CI | $/trade | seats/sess | median risk | MDD | vs D-048 | vs $1,500 floor |
|---|---|---|---|---|---|---|---|---|
| E3 | $5.88 | [−84.79, 100.56] | $4.62 | 1.27 | $662 | $289 | 0.003× | 0.004× |
| E4 | $131.38 | [8.88, 262.59] | $109.67 | 1.20 | $825 | $272 | 0.066× | 0.088× |
| E5 | $32.25 | [−70.12, 133.25] | $24.65 | 1.31 | $712 | $278 | 0.016× | 0.022× |
| E6 | **$308.54** | [60.23, 560.29] | $254.64 | 1.21 | $1,506 | $404 | **0.154×** | 0.206× |
| mean | **$119.51** | 2 of 4 eras exclude zero | $98.40 | 1.25 | | | **0.060×** | 0.080× |

**Reference bars.**

| | E2 | E3 | E4 | E5 | E6 |
|---|---|---|---|---|---|
| D-048 target | $2,000 | $2,000 | $2,000 | $2,000 | $2,000 |
| D-043/D-045 thin floor | $1,500 | $1,500 | $1,500 | $1,500 | $1,500 |
| committed M3 walk-forward (best policy) | $340.88 | $441.14 | $277.92 | $325.86 | $296.57 |
| this lane's like-for-like status quo ($900 wall, same selection) | $150.42 | $35.15 | $63.61 | $37.66 | $53.39 |
| **best goal-path configuration** | – | $5.88 | $131.38 | $32.25 | $308.54 |

### What remains between this and the bars

1. **A factor of ~16 on dollars at the seat level**, and the deficit is *not*
   selection skill: at the measured 1.25 seats/session the configuration would
   need ~$1,600/trade. The trade class's own per-trade ceiling — the best of 765
   measured cell-eras — is $175.68, and that one is bought with $2,062 of risk.
2. **The exit contract is now measured too, and it is not the lever.** Trailing
   at 1.0/1.5 × structure beats the phase close by $5–15/trade and never by more;
   the structural stop beats the $900 wall on *risk* (9–10× smaller) and loses on
   *dollars* (−0.3 to −0.5 R). Both asymmetries the delay census pointed at have
   now been priced, and neither moves the number.
3. **Every lever that remained after the delay census has now been measured and
   is spent**: entry timing (displacement control: no effect), confirmation
   strength (win rate rises, dollars do not), structural risk (small, and small
   is worse), ambiguity (backwards), day-side (null), class mix (+$10), and the
   decidability gate (the one positive, worth $20–157/trade and no more).
4. **What is not measured here**: anything requiring information the program does
   not own (MBP-10 was refused on cost, D-047), and any change to the risk
   posture — position sizing, multiple contracts, wall size/type — which is
   user-reserved (D-029). The one arithmetic observation the census forces:
   the only cells with positive per-trade dollars are the high-risk ones, which
   is a *sizing* statement, and sizing is exactly the reserved class.

### Honest limits of this lane

* The selection model here is a single fixed-hyperparameter walk-forward GBT on
  `y_retg_rank_phase`, not the full M3 harness (which searches hyperparameters
  and the topn/unit policy grid). Its status-quo arm scores $35–150/session
  against M3's committed $278–441, so **the stacked numbers should be read
  against this lane's own status-quo row, not against M3's**.
* The best configuration was chosen from 153 cells × 12 filters × 2 selections
  on the same eras it is reported on. Its era-by-era dispersion ($5.88 → $308.54)
  and the two CIs that straddle zero are the honest reading; only the gate's
  per-trade monotonicity replicates cleanly in all four eras.
* `TREND_D` entries exit at the *entry's own* phase close (the rolled horizon);
  `HOLD`/`LEG`/`DELAY` entries are capped at the original phase close, matching
  the committed delay census. This is stated, not hidden: the trend arm is not
  horizon-comparable with the delay arm.
* The reclaim level is defined as the mid at `conf_sec`. The program has no
  per-candidate signed level *price* (only `level_dist_atr`, a distance), so a
  level-object variant of the reclaim rule was not priced.
* Census 2's `AT_TOKYO_CLOSE` arm cedes NKD's Tokyo hours by construction; the
  `AT_SESSION_OPEN` arm exists precisely to cover that, and is also null.

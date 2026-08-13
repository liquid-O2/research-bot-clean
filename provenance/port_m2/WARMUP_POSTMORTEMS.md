# P-M2c WARM-UP POST-MORTEMS — era E1, STUDY, reader=opus-discretionary

Protocol: theses sealed in commit `459f5d7` ("theses sealed"); every S14 appendix below was opened AFTER
that commit. Committed calls are never revised — the misses are the data (READER_BRIEFING §1).

Certificate convention observed on the tape: a WALLED candidate's phase-close certificate is exactly
`-(900 + cost_rt)` — **-955.00 for NKD, -930.00 for SI, -930.00 for HG(SI-cost)**. `walled=1` with a
`t_wall` LATER than the exit second means the wall never bound the certificate.

Scoreboard for the 24 (phase-close certificate = the adoption metric):

| # | cid | call | phase_close $ | peak_exit $ | walled | mae_bef_peak $ | verdict |
|---|---|---|---|---|---|---|---|
| 1 | NKD-20210701-000027-L | SKIP C | -955.00 | 257.50 | 1 | 125.00 | SKIP right |
| 2 | NKD-20210701-007741-L | SKIP C | -367.50 | 320.00 | 0 | 787.50 | SKIP right |
| 3 | SI-20210701-012312-S | SKIP C | -180.00 | 20.00 | 1 | 1225.00 | SKIP right |
| 4 | HG-20210701-019514-L | SKIP C | +20.00 | 1220.00 | 1 | 225.00 | SKIP right (A1) |
| 5 | SI-20210701-025274-L | SKIP C | +332.50 | 995.00 | 1 | 200.00 | SKIP right |
| 6 | HG-20210701-052246-S | SKIP C | **+1320.00** | 1676.25 | 0 | 475.00 | **MISS** |
| 7 | SI-20210701-052332-L | TAKE B | **-930.00** | 907.50 | 1 | 200.00 | **BAD TAKE** |
| 8 | NKD-20210701-052433-L | SKIP C | +232.50 | 507.50 | 0 | 150.00 | SKIP right |
| 9 | HG-20210701-055858-S | TAKE B | **+1682.50** | 2038.75 | 0 | 50.00 | **WINNER** |
| 10 | NKD-20210818-007457-S | SKIP C | -955.00 | 257.50 | 1 | 275.00 | SKIP right |
| 11 | NKD-20210818-010636-S | SKIP C | -955.00 | -17.50 | 1 | 1137.50 | SKIP right |
| 12 | NKD-20210818-027352-L | SKIP C | -167.50 | 107.50 | 1 | 512.50 | SKIP right |
| 13 | NKD-20210818-055996-L | SKIP C | -955.00 | 320.00 | 1 | 0.00 | SKIP right |
| 14 | NKD-20210818-075162-L | SKIP C | -955.00 | 95.00 | 1 | 37.50 | SKIP right |
| 15 | SI-20210831-028796-S | SKIP C | +557.50 | **2007.50** | 0 | 100.00 | thesis right, exit truncated |
| 16 | SI-20210831-050176-L | SKIP C | -930.00 | 95.00 | 1 | 1112.50 | SKIP right |
| 17 | SI-20210831-055292-L | TAKE B | **-930.00** | 870.00 | 1 | 0.00 | **BAD TAKE** |
| 18 | SI-20210831-058078-L | SKIP C | -930.00 | 20.00 | 1 | 212.50 | SKIP right |
| 19 | SI-20210831-062805-L | SKIP C | +120.00 | 632.50 | 0 | 25.00 | SKIP right |
| 20 | HG-20210929-013657-L | SKIP C | +57.50 | 645.00 | 1 | 825.00 | SKIP right (A1) |
| 21 | HG-20210929-034204-L | SKIP C | +232.50 | 907.50 | 1 | 62.50 | SKIP right (A1) |
| 22 | HG-20210929-052330-S | SKIP C | **+1670.00** | 1913.75 | 0 | 218.75 | **MISS (true D-021 winner)** |
| 23 | HG-20210929-058037-S | TAKE B | +732.50 | 976.25 | 0 | 500.00 | TAKE positive, under bar |
| 24 | HG-20210929-066533-S | SKIP C | +595.00 | 838.75 | 0 | 37.50 | SKIP right |

D-021 winners in the draw (cert>=$1,000 AND mae<=$300 AND unwalled): **2** — #9 (caught) and #22 (missed).
Base rate 2/24 = 8.3%; my TAKE precision 1/4 = 25.0%.

---

## THE THREE FINDINGS THAT MATTER

### F1 — THE PATTERN I MISSED TWICE AND CAUGHT ONCE: `PHASE_ROLLOVER_UNDERMOVED`
All three of the draw's $1,300+ phase-close certificates (#6 +1320, #9 +1682.50, #22 +1670) share one
ex-ante configuration, and no other case in the draw has it:

* `S3 COVERAGE_phase` <= ~70% **and** `S9 ladder_position` in {below_q10, at_or_above_q10} — the phase has
  NOT yet made its expected move;
* `S3 runway to_phase_close` >= ~26,900s with `S13 exit_default = session close` — the whole afternoon to run;
* `S3 phase H` (for a SHORT) printed **within the last 90-200 seconds**;
* `S5 mid_slope_$/min` and `accel(1m-5m)` **both** pointing the trade's way.

| case | COVERAGE_phase | ladder_position | runway s | phase-extreme age | slope / accel | cert |
|---|---|---|---|---|---|---|
| #6 HG-20210701-052246-S | 45.9% | below_q10 | 30553 | 200s | -62.5 / -47.5 | +1320 |
| #9 HG-20210701-055858-S | 68.5% | at_or_above_q10 | 26941 | 70s | -87.5 / -92.5 | +1682.50 |
| #22 HG-20210929-052330-S | 57.9% | below_q10 | 30469 | 93s | -50.0 / -50.0 | +1670 |
| #23 (near-miss, took) | 75.6% | at_or_above_q10 | 24762 | low, not high | 0.0 / +33.7 | +732.50 |
| #24 (near-miss, skipped) | 106.3% | at_or_above_q50 | 16266 | low, not high | +75.0 / +75.0 | +595 |

The two near-misses fail the coverage test and the slope test and both land in the $600-750 band. The
discrimination is clean on FIVE named fields, all present in S3/S5/S9 of the blind sheet.
I took #9 for a DIFFERENT reason (level confluence + A2 spent energy) and skipped #6 and #22 because I let
the S8 fuel map veto them. That is one error made twice.

### F2 — FUEL-MAP POLARITY IS OVERTURNED AS A DIRECTIONAL RULE
I invented `FUEL_POLARITY` at case #2 (sign of phase sflow x which side of the phase volume mass the mid
sits on) and used it as primary or interaction evidence in nine cases. Its record:

* right on every small outcome (#2 -367.50, #3 -180, #4 +20, #19 +120, #24 +595) — where nothing was at stake;
* **wrong on both $1,300+ moves it was asked about** (#6: I said "80.3% below mid with sflow=-878 means the
  aggressive sellers are underwater, a fresh short joins the losing side" — the short paid +$1,320; #22 I let
  fuel SYMMETRY veto a +$1,670 winner);
* as the "against" on my two winners-or-near it argued the wrong way (#9 96.6% below-mid said do not short;
  the short made +$1,682.50).

Verdict: the fuel map measures where inventory SITS, not who must transact. It has no demonstrated directional
power at the magnitude that clears the bar. DEMOTED to a context field. Its one surviving use is degenerate-
state detection (phase_total < ~50 contracts at a phase open, case #5).

### F3 — THE $900 WALL BINDS CONSTANTLY ON THIS PORT (B5 OVERTURNED)
B5 states the wall "never binds true A-class winners on IWM (0.0% measured)". On this draw **9 of 24 (37.5%)
candidates are hard stop-outs** — the wall fires before the exit second and the certificate lands exactly at
-(900+cost). Both of my losing TAKEs (#7, #17) are in that group, at -$930 each, and #17 had
`mae_before_peak = $0.00` — i.e. the trade went my way first and the wall still took it, on the give-back.
Per asset: NKD 5/8 walled-out, SI 4/8, HG 0/8. This is not a tail: it is the modal NKD outcome in E1.

---

## PER-CASE POST-MORTEMS

### #1 NKD-20210701-000027-L — SKIP C. Reality: phase_close **-955.00** (walled), peak_exit +257.50.
Thesis vs reality: correct and for the right reason. The session-open long died at the wall 4.5h later.
Deciding ex-ante data: `S13 spread_at_decision=$175.00` (3.5x the NKD median) and `S8 session vol=12` at
second 27. Earliest telltale: the S7 L1 (`bid x1 / ask x4`) — available in the first line of S7.
Briefing: A1's "capacity is wide open" (COVERAGE 9.8%) was TRUE and IRRELEVANT — capacity without
participation is not opportunity. A1 needs a participation conjunct.

### #2 NKD-20210701-007741-L — SKIP C. Reality: **-367.50**, peak_exit +320.00, unwalled, mae_before_peak $787.50.
Correct. But note the mae: a long held from 28735 saw $787.50 against it before its $375 peak — B5's
"entry-moment quality keeps MAE small" is exactly what was missing.
Deciding ex-ante data: `S3 pivot chain lows 28742.5 -> 28747.5 -> 28767.5 -> 28735.0@02:08:58` — a fresh
break of three prior swing lows three seconds before the decision. Earliest telltale: `S5 mid_slope_$/min
= -187.5 with accel = -132.5` at T-5m. My fuel-polarity primary happened to agree; the pivot chain was the
real reason and it is one S3 line.

### #3 SI-20210701-012312-S — SKIP C. Reality: **-180.00** (walled at 14:12:53), peak_exit +20.00.
Correct. The four-family reclaimed-support confluence $25 below the short entry was the right object to name:
price never went down. Note `unwalled mfe=$1150 @18:36:26` — the short DID eventually work, 15 hours later,
after being stopped out. The wall, not the thesis, was decisive.
Sheet defect confirmed: `S9 ladder_position=below_q10` printed with every `move_ladder` quantile `.` — the
field asserts a band it cannot compute when fvol is REFUSED for the asset/date.

### #4 HG-20210701-019514-L — SKIP C. Reality: **+20.00** at phase close; peak_exit +1220.00 (argmax 15:29:48).
The A1 veto was exactly right on the ADOPTION metric: `COVERAGE TOKYO=79.4% unspent=$229.6, runway 5686s,
exit=phase_close@07:00`. The phase close paid $20. The $1,220 lived nine hours later, outside the exit rule.
Confirmed: **A1 must be evaluated against the EXIT SECOND, not the session.** This is A1's strongest form and
the sheet carries every term of it on one S3 line plus one S13 line.

### #5 SI-20210701-025274-L — SKIP C. Reality: **+332.50**, peak_exit +995.00, walled after the exit, mae $200.
Correct call, wrong emphasis. I skipped on "entered at the exact phase high into an above-normal offer".
Reality: the long worked modestly. What I got right and should have weighted more: `S8 60s volume = 18
contracts` — A3's magnitude test. What I got wrong: I treated `G1_FAST_OPEN mean_cert=+$74.97` as a
meaningful prior; it is a population number and the candidate cleared it by $258.
`one_position_DP seated=1` — this candidate IS in the session's DP schedule. A $332 seat is a real seat that
my C-class SKIP correctly valued at <$700.

### #6 HG-20210701-052246-S — SKIP C. Reality: **+1320.00 phase close, +1676.25 peak, UNWALLED.** MY WORST MISS.
Thesis vs reality: I named the fuel map (80.3% below mid, sellers "underwater") as primary and let it
override the structure. The structure was right and the fuel read was meaningless.
**What visible ex-ante data would have decided it:** the F1 quintuple, all on the blind sheet —
`S3 COVERAGE NY=45.9% unspent=$838.2` + `S9 ladder_position=below_q10` (the NY phase had not yet made even
its 10th-percentile move) + `S3 runway=30553s` with `S13 exit_default=session close` + `S3 pivot 90 HIGH
4.3005@14:27:26` 200 seconds before the decision + `S5 mid_slope T-5m=-62.5, accel=-47.5`.
**Earliest telltale:** `S9 ladder_position=below_q10` — one token, and it says "the move has not happened yet".
Briefing: A1 CONFIRMED in its constructive direction (low coverage + long runway = the seat), which I had
only ever used as a veto. C(ii) confirmed: `S8 phase sflow=-878` was a real parent-order footprint and it won.
My "absorption" counter-read (price rose through the selling) was hindsight-shaped narrative on 52 minutes of
data; the seller finished the job.

### #7 SI-20210701-052332-L — TAKE B. Reality: **-930.00 (WALLED at 16:14:52)**, peak_exit +907.50, mae $200.
Thesis vs reality: the V-reversal was real — the trade made +$525 at h30 and peaked at +$937.50 — and then
gave it all back and hit the wall 1h42m later. My A3 evidence (price+flow+book agreeing in the last 60s at a
9-touch level) described the next 30 minutes correctly and the certificate horizon not at all.
**What would have decided it ex ante:** `S2 day_type_so_far=AT_RANGE` with `range_so_far=$1625.0 = 63.6% of
range_hat` — I wrote this down as my "against" and then took anyway. The session had already moved; the
V-bounce was inside a spent range, and the phase-close exit is 8.5h away with a $900 wall in between.
**Earliest telltale:** `S9 rv_nowcast w60=132.9 vs w1800=489.9` — realised vol collapsing while I read the
burst as live. Briefing: **A3 as a TAKE trigger failed here and in #17 (0 for 2).** A3's survivorship on IWM
does not transfer to an 8-hour walled hold. B1's NEWS-WINDOW class card (the best in the era) did not save it.

### #8 NKD-20210701-052433-L — SKIP C. Reality: **+232.50**, unwalled.
Correct. `S8 60s n=0 trades / vol=0` is the cheapest and most reliable veto in the whole round.
Deciding ex-ante data: that one line. A1 (`COVERAGE SESSION=90.5%`) also correct.

### #9 HG-20210701-055858-S — TAKE B. Reality: **+1682.50 phase close, +2038.75 peak, UNWALLED, mae $50.00.**
A D-021 WINNER, and `ORACLE LEGS: 15:29:48 -> 19:29:51 dir=-1 travel=$2181 captured@1k=1
capture_dec_sec=55858` — **my decision second IS the leg's capture second.** `one_position_DP seated=1`.
Thesis vs reality: the level object I named (a first test of PHASE_HL LONDON|lb1/2/3|H = 4.3148 coincident
with FVOL_LADDER OPEN_LONDON|q50|+1 = 4.3149, failed 70s earlier) held for four hours. mae $50 vindicates
the A5 first-test read and B5's "entry-moment quality, not a wider stop".
Confirmed: A5, B2 (fvol ladder + phase-H confluence), A2 (buy-side aggression at magnitude that failed to
hold), A4 (`dBsz/min=-5.00 vs dAsz/min=+3.00`). My "against" — the fuel map's 96.6%-below squeeze read —
was simply wrong, which is F2.
My A1 refinement (a $1,000 target INSIDE the existing range needs no extension) held: 4.2900 was inside.

### #10 NKD-20210818-007457-S — SKIP C. Reality: **-955.00 (walled)**, peak +257.50.
Correct. Deciding ex-ante data: `S13 spread_at_decision=$75.00` (1.5x median) + `S9 vol_of_vol=0.721` — the
maker widened because the flow was toxic and the entrant pays it (C(i) confirmed as a COST signal, which is
its only use I can defend).
Sheet caveat confirmed at #12: the S5 `z` column is unnormalised.

### #11 NKD-20210818-010636-S — PRELIM SKIP C -> FINAL SKIP C. Reality: **-955.00 (walled)**, peak -17.50,
mae_before_peak $1137.50. Correct on both views.
Note: `ORACLE LEGS: 02:23:35 -> 05:16:57 dir=1 travel=$1663 captured@1k=1 capture_dec_sec=8664` — a real
$1,663 leg existed in this window and was captured by a candidate 20 minutes later, on the LONG side. My
SHORT sat inside a leg going the other way. The blind field that said so: `S4` support cluster BELOW the
short (PRIOR_DAY SETTLE 27437.5 + PROFILE NY|VAH/TOKYO|VAL 27445 + SESSION|VAH 27440, all REJECT) — I named
it in the truncated view and it was the right object.
Ablation: truncated and full agreed; the full view added the dead-book veto (`S8 60s n=1`) as a second reason.

### #12 NKD-20210818-027352-L — SKIP C. Reality: **-167.50 (walled at 21:56:47)**, peak +107.50, mae $512.50.
Correct, and the A1 veto was in its strongest form: `COVERAGE TOKYO=132.5% unspent=-$407.3, runway 3248s`.
The 223-contract 4:1 buy burst that moved the mid $2.50 produced $107.50 of peak. My "flow at magnitude with
no price response is absorption" read was exactly right — **that is the pattern worth keeping from this case**
(`ABSORPTION_NO_RESPONSE`: S8 60s |sflow|/vol > 0.4 with |mid(NOW)-mid(T-1m)| <= 1 tick).
Sheet defect confirmed: `S5 trades/min z=+102.76`.

### #13 NKD-20210818-055996-L — PRELIM SKIP C -> FINAL SKIP C. Reality: **-955.00 (walled)**, peak +320.00,
mae_before_peak $0.00. Correct. The trade went +$375 first and still hit the wall: F3 in miniature.
Deciding ex-ante data (already in the truncated view): `S3 COVERAGE SESSION=101.3% unspent=-$21.9` with
`exit_default=session close`. My truncated note — "when exit_default is session close the SESSION reading is
the binding one" — is confirmed and is now a pattern-ledger rule.

### #14 NKD-20210818-075162-L — SKIP C. Reality: **-955.00 (walled)**, peak +95.00.
Correct. `S8 60s n=0` again. Third NKD-NY dead book in the draw, third stop-out.

### #15 SI-20210831-028796-S — SKIP C. Reality: phase_close **+557.50**, **peak_exit +2007.50 with mae only
$100.00**, unwalled, `sess_close=+1575.00`.
Thesis vs reality: my LOCATION read was right — the short below the four-deep `PHASE_HL NY|lb1/2/3/5|H =
24.2525` cluster with `ask_sz z=+3.37` ran $2,007.50 to 17:05:39. My PARTICIPATION veto (`trades/min=2.00
z=-2.46`, `S8 60s n=2 trades`) was the wrong reason to refuse: a 2.5sd-quiet clock cell did NOT prevent the
move, it just meant the move started later.
**What killed the adoption number was the EXIT RULE, not the entry:** `exit_default=phase_close@13:00:00`
truncated a $2,007 excursion to $557.50, and holding to session close would have paid $1,575.
Briefing item overturned in part: B3's cell law ("quality concentrates in the busy cells") does not imply
"a quiet cell cannot produce a big move" — it is a base-rate statement, and I used it as a per-case veto.
This is an ORCHESTRATOR-FACING finding: the LONDON phase-close exit is the binding constraint on
London-initiated metal shorts that resolve in NY.

### #16 SI-20210831-050176-L — PRELIM SKIP C -> FINAL SKIP C. Reality: **-930.00 (walled at 15:08:27)**,
peak +95.00, mae_before_peak $1112.50. Correct on both views, decisively.
`ORACLE LEGS: 08:06:25 -> 15:15:13 dir=-1 travel=$1775 captured@1k=1 capture_dec_sec=29446` — the leg was
DOWN and was captured six hours before my LONG. The balance-node read ("90.3% of the phase volume in one
+/-0.05 ATR band, through_book n=0 in 600s") was the correct description of a coil that broke the other way.
Ablation: identical call from both views; the full view supplied the quantitative form only.

### #17 SI-20210831-055292-L — TAKE B. Reality: **-930.00 (WALLED at 17:05:36)**, peak_exit +870.00,
**mae_before_peak $0.00**, h30 = +525.00.
Thesis vs reality: the fifteen consecutive minutes of positive `S5 sflow/min` were real; the trade went
straight to +$870 without a tick against it and then reversed into the wall. My thesis described the first
half hour perfectly and the 7.6-hour certificate horizon not at all.
**What would have decided it ex ante:** `S3 COVERAGE SESSION=80.4% unspent=$433.0` combined with
`S13 exit_default = session close` and `wall=$900`. My own A1 refinement ("a $1,000 target inside the range
needs no extension") is **wrong when the hold is to session close through a wall**: being inside the range
does not bound the give-back. The refinement survives for #9 (a 4-hour trend leg) and fails here.
**Earliest telltale:** `S9 rv1800=631.2 vs rv60=72.9` — the vol that produced the move had already collapsed
by an order of magnitude at the decision second, so the leg was ending, not beginning.
C(ii) is CONFIRMED as a short-horizon predictor and REFUTED as a phase-close-certificate predictor.

### #18 SI-20210831-058078-L — PRELIM SKIP C -> FINAL SKIP C. Reality: **-930.00 (walled)**, peak +20.00.
Correct on both views. `ORACLE LEGS: 15:39:55 -> 17:05:39 dir=-1 travel=$1813 captured@1k=1
capture_dec_sec=56549` — a $1,813 DOWN leg was live and captured 25 minutes before my LONG candidate.
Ablation, and this is the round's clearest section-value demonstration: the truncated view's ONLY pro-LONG
item was `S5 ask_sz=8 z=-2.02` read as A4 losing-side thinning. The full view shows the offer was thin
because sellers were hitting the bid (`S8 60s buy/sell_vol 40/68`, three most recent through_book prints all
`>B`). **S5's static book snapshot produces a sign-inverted A4 read that only S8 can correct.**

### #19 SI-20210831-062805-L — SKIP C. Reality: **+120.00**, peak +632.50, unwalled, mae $25.00.
Correct. My named discriminator against #17 (overhead-fuel share and distance-to-shelf) picked the right
direction of difference but for a reason that F2 now demotes; the field that actually separated them is
`S3 COVERAGE NY` (66.0% for #17 vs 96.6% here) and `S9 surprise` (0.551 vs 0.807).

### #20 HG-20210929-013657-L — SKIP C. Reality: **+57.50**, peak +645.00, walled after exit, mae $825.00.
Correct, A1 in its veto form again (`COVERAGE TOKYO=81.1% unspent=$216.1, runway 11543s, exit=phase_close`).
`BROKEN-SUPPORT-OVERHEAD` (eleven |L-family levels stacked at 4.2310-4.2335 above a long entry) survives as
a described object: price did not clear it inside the phase. Retained as a HYPOTHESIS, n=1.

### #21 HG-20210929-034204-L — PRELIM SKIP C -> FINAL SKIP C. Reality: **+232.50**, peak +907.50, mae $62.50.
Correct on both views. A1's strict form (a $1,000 target above BOTH the phase and session highs = mandatory
range extension) is confirmed: the bounce peaked $92.50 short of the bar.
Ablation: the truncated view MISSED `through_book_600s thru_ask=10 vs thru_bid=1` entirely — that field lives
only in S8 — and therefore understated the bounce, which did reach +$907.50 on peak-exit. Call unchanged,
evidence balance materially wrong from S1-S5+S13 alone.

### #22 HG-20210929-052330-S — SKIP C. Reality: **+1670.00 phase close, +1913.75 peak, UNWALLED,
mae $218.75 — a TRUE D-021 WINNER I refused.** MY MOST EXPENSIVE MISS.
Thesis vs reality: I named "THE BALANCE TRIPLE" (fuel symmetry to 0.2%, sflow ~0 on every window, a
twelve-level POC/VWAP nest at d$=0) and concluded "there is no aggressor and no trapped side to trade
against". Correct description, wrong inference: **a balance node with unspent phase capacity is a COIL, and
the coil resolves in the direction the session is already leaning.**
**What visible ex-ante data would have decided it:** the F1 quintuple, every term of it on the sheet —
`S3 COVERAGE NY=57.9% unspent=$727.9` + `S9 ladder_position=below_q10` + `S3 runway=30469s` with session-close
exit + `S3 pivot 89 HIGH 4.2490@14:30:37` 93 seconds before the decision + `S5 mid_slope T-5m=-50.0,
accel=-50.0`. I wrote FOUR of those five into my own "against" field and still skipped.
**Earliest telltale:** `S9 ladder_position=below_q10` alongside `S2 day_type_so_far=AT_RANGE` — the SESSION is
at range while the PHASE has not moved. That conjunction appears in #6 and #22, the two misses, and nowhere else.
Briefing overturned: my own balance-triple pattern is DEAD as a veto on its first out-of-sample test.

### #23 HG-20210929-058037-S — PRELIM SKIP C -> **FINAL TAKE B** (the one call the sections changed).
Reality: **+732.50 phase close, +976.25 peak, unwalled, mae $500.00** — positive, below the $1,000 bar, and
the mae exceeds the $300 acceptance.
Thesis vs reality: my primary (98.4% of NY inventory above the entry with a POSITIVE phase sflow = trapped
longs that must transact) produced a positive but sub-bar trade, and the $500 mae is exactly what B5 warns
about. The upgrade from SKIP to TAKE was directionally right and value-neutral.
The ablation verdict is genuinely mixed: S8 changed the call for the better in sign and by +$732.50 of
realised replay (capture 0.236 on that subset) but did not deliver a bar-clearing trade.
**What would have decided it better ex ante:** F1 again — `COVERAGE NY=75.6%` and `mid_slope T-5m=0.0,
accel=+33.7` (slope pointing AGAINST the short) put this case outside the winning configuration. My own
paired-case note said so and I took anyway.

### #24 HG-20210929-066533-S — SKIP C. Reality: **+595.00**, peak +838.75, unwalled, mae $37.50.
Correct, and the paired experiment I designed against #23 resolved as predicted: the higher-coverage,
shorter-runway, rising-slope member of the pair paid less ($595 vs $732.50) and neither cleared the bar.
`COVERAGE NY=106.3%` + `ladder_position=at_or_above_q50` + `surprise=0.817` is a reliable sub-bar signature:
every case in the draw carrying it (#12, #24) landed between -$168 and +$595.

---

## BRIEFING-ITEM VERDICTS (§3 duty to contradict)

| item | verdict on E1 STUDY (n=24) | evidence |
|---|---|---|
| **A1** capacity/runway arithmetic | **CONFIRMED, and it is the best field in the sheet — but I was using only half of it.** As a VETO: 5/5 (#4, #12, #20, #21, #24 all sub-bar). As a SEAT-FINDER (low coverage + long runway + fresh phase extreme): 3/3 at >=$1,320 (#6, #9, #22). Must be evaluated against the EXIT SECOND (#4) and at the SESSION level when exit=session close (#13). | S3 COVERAGE_phase, unspent, runway; S9 ladder_position; S13 exit_default |
| **A2** refail clustering | CONFIRMED once (#9: buy-side size through the offer that failed to hold). n=1. | S8 through_book_600s + S3 pivots |
| **A3** two-stream agreement at magnitude | **SPLIT: 0/2 as a TAKE trigger (#7, #17 both walled at -$930), 3/3 as a SKIP trigger (#5, #12, #21).** A3-positive describes the next 30 minutes, not the phase-close certificate. | S5 sflow/min + S7 dBsz/dAsz + S8 60s |
| **A4** side-resolved book erosion | CONFIRMED from S7 (`dBsz/min` vs `dAsz/min`, #9, #19), **REFUTED from S5's static `bid_sz/ask_sz` snapshot** (#18: sign-inverted). Use the rate fields, never the level fields. | S7 dBsz/min, dAsz/min |
| **A5** early-in-sequence confirmation | CONFIRMED on the draw's only clean winner (#9, tc=1 test_m=1 four-family confluence, mae $50). | S4 tc, test_m |
| **B1** class cards | **DOES NOT TRANSFER TO THE CANDIDATE.** NEWS-WINDOW carried the era's only positive mean_cert (+$26.63, win_frac 0.1187) and both SI NEWS candidates walled out at -$930 (#7, #18); the two winners came from NEWS_WINDOW/MICRO_OPEN on HG where the class cards are worse. | S13 class card vs outcomes |
| **B2** levels | CONFIRMED. Every case where a named multi-family confluence was the entry object resolved as described (#9 win, #3/#11/#15 correct refusals, #15's location right). fvol-ladder + PHASE_HL co-location is the recurring winning object. | S4 family, price, tc, test_m |
| **B3** quality concentrates in cells | **CONFIRMED as a base rate, REFUTED as a per-case veto.** NKD-in-NY was dead 3/3 as predicted (#8, #13, #14). But #15 produced a $2,007.50 peak excursion out of a clock cell at `trades/min z=-2.46`. | S5 trades/min z; S8 60s n |
| **B4** generation recall | CONSISTENT: 4 of 24 sit inside scored oracle legs; #9's decision second IS a leg's capture second. | S14 ORACLE LEGS |
| **B5** winners' MAE / the wall | **OVERTURNED.** 9/24 (37.5%) hard stop-outs at exactly -(900+cost). Both losing TAKEs walled; #17 with `mae_before_peak=$0.00`. The wall is the dominant loss mechanism on this port, not a tail. | S14 walled, t_wall |
| **B6** costs are small | CONFIRMED in aggregate, REFUTED at the extreme: #1's `spread_at_decision=$175.00` + `cost_rt=$55` = 23% of the bar. Spread state is a first-class veto, not a rounding term. | S13 spread_at_decision, cost_rt |
| **C(i)** maker reactions | CONFIRMED as a COST/toxicity signal (#10 spread widening with vol_of_vol=0.721). No demonstrated directional content. | S13 spread, S7 c2f/L1life |
| **C(ii)** execution-algo footprints | **SPLIT: confirmed at the phase horizon (#6's -878 phase sflow won), refuted at the certificate horizon when read from the last 15 minutes (#17).** | S8 phase sflow vs S5 sflow/min |
| **C(iii)** trapped positions must transact | **OVERTURNED as stated.** See F2 — the fuel map has no demonstrated directional power at bar-clearing magnitude. | S8 FUEL MAP |
| **D1** do mid-leg entries pay? | Partial answer: #9 is a mid-leg continuation entry (3 min into a 4h leg) and paid $1,682.50 with mae $50. n=1, favourable. | |
| **D2** which A-survivors transfer to which classes? | A1/A5/B2 transferred to NEWS-WINDOW and OPEN-DYNAMICS (#6, #9, #22). A3/A4-from-S5 did not transfer at all. | |
| **D3** NKD first-tests / post-shocks distinct? | Untested — the draw produced no NKD LEVEL-FIRST-TEST or SHOCK-RESOLUTION case. NKD's E1 signature in this sample is instead: 5/8 walled out, mean phase-close -$635. | |

## ABLATION VERDICT (6 cases, truncated S1-S5+S13 vs full)
Calls: 5 of 6 identical (all SKIP/C on both views); 1 changed (#23 SKIP/C -> TAKE/B).
Mechanical score on the ablation subset: truncated = 0 TAKEs, mean_skip -$468, replay $0, capture NA;
full = 1 TAKE at +$732.50, mean_skip -$708, replay $732.50, capture 0.236.
The full sections were better on every measurable dimension (they added a positive trade and they made the
SKIP pool worse, i.e. more discriminating). But the effect is small and one-sided: **S1-S5+S13 alone already
carried the A1 arithmetic, the level map and the participation-decay read — which is where 3 of my 4 correct
vetoes came from.** The sections that earned their place are S8 (through_book log and the fuel map: #21, #23)
and S8's flow windows (#18, where they inverted a wrong A4 read from S5). S6's raw ribbon and S10-S12 did not
change a single call in 24 cases.

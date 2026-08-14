# ERA NOTES — E1 (2021H2, STUDY block, boundary 20211019)

**Status: ERA-TAGGED HYPOTHESES (D-059.1).** Seeded from the P-M2c warm-up: 24 STUDY cases across 6
session-assets (SI 20210701/20210831, HG 20210701/20210929, NKD 20210701/20210818). n is tiny; nothing here
is a census. Every claim names the sheet fields a detector would read so it can be censused before use
(D-026/D-056). E2 opens with a LIBRARY RE-TEST of every line below (D-059.2).

## 1. THE ERA'S DOMINANT FACT IN THIS SAMPLE: THE EXIT RULE IS ASSET-SHAPED
Phase-close certificates by asset over the 24 drawn candidates:

| asset | n | mean phase-close $ | positive | hard stop-outs at -(900+cost) | replay capture (panel_score) |
|---|---|---|---|---|---|
| HG | 8 | **+788.75** | 8 / 8 | 0 / 8 | +0.382 |
| SI | 8 | -361.25 | 3 / 8 | 4 / 8 | -0.391 |
| NKD | 8 | -635.00 | 1 / 8 | 5 / 8 | 0 (no takes) |

HG's two sampled sessions (20210701, 20210929) were both afternoon trend days and **every** HG candidate in
the draw finished positive at its exit; NKD's 20210818 chopped and walled out five of eight. If this survives
a census it is a portfolio-selection fact (D-M2 s14 port targeting picked SI+NKD; this sample argues HG's
E1 phase-close behaviour deserves re-examination), not a reader fact. **Fields:** S14 phase-close certificate,
`walled`, by (asset, era). RECOMMENDED CENSUS: walled-fraction and mean phase-close certificate per
(asset, era, phase), whole population — this is cheap and it is the highest-value number the round produced.

## 2. THE SEAT THAT EXISTS IN E1: `P001 PHASE_ROLLOVER_UNDERMOVED`
The only three candidates in the draw whose phase-close certificate cleared $1,300 share one ex-ante
configuration and nothing else (all HG, all NY, all SHORT — a co-occurrence the census must break apart):
`COVERAGE_phase <= 70%` + `ladder_position in {below_q10, at_or_above_q10}` + `runway >= 26,000s` with a
session-close exit + a phase extreme printed within 200 seconds + `mid_slope` and `accel` both signed with
the trade. See PATTERN_LEDGER P001. The two near-miss members of the family (`COVERAGE_phase` 75.6% and
106.3%, slope pointing the wrong way) paid $732.50 and $595 — the coverage and slope terms carry the
discrimination, so the census must vary them.

## 3. WHAT KILLS TRADES IN E1: THE WALL, NOT THE THESIS
9 of 24 candidates (37.5%) were hard stop-outs, landing at exactly `-(900 + cost_rt)`. Two of them
(`NKD-20210818-055996-L`, `SI-20210831-055292-L`) had `mae_before_peak = $0.00` — they went straight to their
peak and were stopped on the give-back. Briefing B5's IWM transfer ("the wall never binds true A-class
winners, 0.0% measured") does not hold on this port in this era. Candidate ex-ante marker to census:
`S9 rv_nowcast w1800 / w60` — in both zero-MAE stop-outs the ratio exceeded 8 (the vol that produced the
move had already collapsed at the decision second).

## 4. PHASE-CLOSE VS SESSION-CLOSE IS NOT A FREE CHOICE
`SI-20210831-028796-S`: peak excursion $2,007.50 with mae $100, session-close $1,575 — and phase-close
$557.50, because the LONDON exit at 13:00 truncated a short that resolved in NY. The reverse also occurs
(`HG-20210929-013657-L` +$57.50 at phase close vs -$1,337.50 at session close). No systematic direction in
n=24; flagged for the orchestrator because it is an EXIT-RULE parameter, not a reader decision.
**Fields:** S14 `horizons_$ phase_close` vs `sess_close`, by (asset, phase_dec).

## 5. WHERE THE SHEET'S INFORMATION ACTUALLY IS (section-ablation seed)
Across 24 cases, the sections that changed or would have changed a call:
* **S3 + S9 (capacity/ladder/runway)** — the source of 5 of my 5 correct A1 vetoes and of all 3 P001 seats.
  Highest information density per token in the whole sheet.
* **S4 (level ledger)** — the entry object in every case that resolved as described (P006, P008).
* **S8 (flow windows, through-book log, fuel map)** — the only section that changed a call in the ablation
  (`HG-20210929-058037-S`), and the only section that can correct S5's inverted book read (P012).
* **S5** — carries the participation-decay read (`trades/min` series) and the slope/accel terms of P001, but
  its `bid_sz`/`ask_sz` levels are actively misleading (P012) and its `z` column is unusable as a threshold
  (defect D3 below).
* **S6 (raw ribbon), S10 (profile), S11 (cross-asset), S12 (context)** — **did not change a single call in 24
  cases.** S6 was useful exactly once as colour (`NKD-20210818-010636-S`, a market maker's quote cycle
  repeating for 36 seconds with zero trades) and S7's `c2f`/`rev/s` carried the same fact in two integers.
  This is a real budget finding given S6 is the largest section (CC-M2-1.1 raised it to 3,000 proxy tokens).

## 6. CLASS-CARD BEHAVIOUR IN E1 (qualifies briefing B1)
The class card is a POPULATION statistic and did not transfer to the candidate in this draw. SI's
NEWS-WINDOW card is the era's best (`cond_value $1042.88`, `mean_cert +$26.63`, `win_frac 0.1187`) and both
SI NEWS-WINDOW candidates drawn walled out at -$930. The two winners came from HG NEWS_WINDOW and HG
MICRO_OPEN, whose cards are materially worse. Do not let a class card move a call; use it only to set the
prior on how often to expect a seat in that class.

## 7. VOL-REGIME NOTE
Only 2 of 24 cases were in a HIGH regime (`HG-20210929-013657-L` rv5/rv66=1.135, `HG-20210929-034204-L`
1.778) and both were sub-bar (+$57.50, +$232.50) — both vetoed correctly by P002, i.e. the regime did not
rescue an exhausted phase. The three P001 seats were all in LOW/MID regimes. B3's "HIGH-vol cell" claim is
NOT supported by this sample and must be re-tested on the population before it is used.

## 8. OPEN QUESTIONS CARRIED INTO E2
1. Does P001 survive outside HG/NY/SHORT? The co-occurrence in n=3 is the single biggest risk in this note.
2. Is the per-asset phase-close asymmetry (§1) an era fact, a session-sampling artefact, or a standing
   property of the exit rule?
3. Does the `rv1800/rv60` collapse predict wall stop-outs (§3)? It is one ratio over the whole population.
4. D3 from the briefing (NKD first-tests / post-shocks as signal-pure families) is UNTESTED — the draw
   produced no NKD LEVEL-FIRST-TEST or SHOCK-RESOLUTION case. Route one deliberately in E2.

## 9. SHEET / PROTOCOL DEFECTS FOUND (for the builder)
* **D1 — `S9 ladder_position` asserts a band it cannot compute.** When `fvol` is REFUSED for the asset/date,
  `S3 COVERAGE exp_move_q50` and every `S9 move_ladder` quantile render as `.` while `ladder_position` still
  prints `below_q10`. Seen on SI 20210701 (`SI-20210701-012312-S`, `-025274-L`, `-052332-L`). Since
  `ladder_position` is a term in P001, this is a live correctness risk.
* **D2 — `S7 refill_after_trade` is identically zero.** `n_refilled_5s=0`, `frac=0.000`,
  `median_restore_ms=.` in **all 24 sheets**, across 3 assets and n_trades_300s from 7 to 427. A field that
  never varies is either broken or mis-specified; I nearly used it as C(i) evidence on case #2.
* **D3 — `S5` z column is a raw (x-mean)/sd against a trailing same-half-hour window whose dispersion can be
  ~0.** Produces `trades/min z=+102.76` (`NKD-20210818-027352-L`) and paired `bid_sz z=+5.40 / ask_sz z=+5.40`
  (`NKD-20210818-007457-S`). Usable as an ordinal, never as a threshold. Needs a robust scale or a cap flag.
* **D4 — `S4 OR STATE` mixes today's completed opening ranges with prior-day ranges for phases that have not
  opened yet, with no as-of stamp.** `SI-20210701-012312-S` at 03:25 TOKYO lists `LONDON|OR30` and `NY|OR30`
  rows. Not a leak (they are prior-day values) but unlabelled and easy to misread as forward information.
* **D5 — protocol/spec mismatch:** the round brief specifies splitting the ablation view at a `## S6` marker
  and reading `SESSIONS_E1.tsv`; the rendered sheets use bare line-initial `S6 RAW EVENT RIBBON` headings and
  the file is `SESSIONS_STUDY.tsv`. Handled in `provenance/port_m2/warmup_view.py` / `warmup_draw.py`.

---

# E1 STUDY DAY 1 UPDATE (2021-07-01, day-complete, n=1,039 across SI/HG/NKD)

Source: provenance/port_m2/E1_STUDY_LEDGER.tsv (sealed `9857814`) + E1_POSTMORTEMS.md §D1.
Everything below is a DAY-COMPLETE COUNT on one session per asset, not a draw. n is now large
enough that several §1-§9 claims above are superseded; they are struck, not deleted (D-059.1).

## 10. THE DAY'S DOMINANT FACT: THE SEAT HAS ONE SHAPE
**All 48 D-021 winners in 1,039 candidates are SHORTS, and all 48 are in the NY phase.**
HG 29, SI 19, NKD 0. Zero long winners; zero TOKYO or LONDON winners on any asset.
Base rate 4.62%. **Fields:** S14 winner_close by (side, phase_dec). RECOMMENDED CENSUS: winner
rate by (asset, phase_dec, side) over the whole era — if the side/phase concentration survives,
it is a generation-side fact worth more than any reader feature.

## 11. THE EIGHT-TERM CONJUNCTION (the day's principal product; needs a census)
The reader's committed rule (engine/port_m2/e1d1_policy.py, T1-T8) is monotone in realised
value over all 1,039 candidates: n_terms 6 -> mean -$25.78 / 8.1% winners; 7 -> **+$586.83 /
30.8%**; 8 -> **+$1,528.75 / 70.0%**. Against a 4.62% base rate this is a 15x lift at the top.
**Fields (all strictly causal, all on the blind sheet):** S8 60s n/vol; S13 spread_at_decision;
S3 phase H/L vs entry mid with S13 mult (the range-EXTENSION arithmetic); S3 runway; S8 phase
sflow sign and |sflow|/phase_vol; S5 mid_slope/accel; S3 phase-extreme age; S9 rv1800/rv60.
CENSUS BEFORE USE, one term at a time — §12 shows two terms are subtracting value.

## 12. TWO TERMS ARE VALUE-DESTROYING (sole-blocking ablation, the cleanest the day affords)
* **T6 momentum (S5 mid_slope + accel signed with the trade): DROP IT.** 17 candidates blocked
  by T6 alone averaged **+$1,438.01** with 8 D-021 winners. Proof case HG-20210701-054129-S: the
  NY phase high printed 2 seconds before the decision, so the 5-minute slope necessarily pointed
  UP on a short; it paid +$1,526.25. **T6 and T7 are not independent — at a fresh extreme the
  slope must point the wrong way.** This directly amends warm-up P001, whose slope term was an
  artefact of sampling its three founders 70-200s after their extremes.
* **T7 freshness (extreme <= 900s): TOO TIGHT.** 3 candidates blocked by T7 alone were all
  D-021 winners (mean +$1,426.25); HG-20210701-057109-S at 1,321s paid +$1,545 with mae $43.75.
* Net-positive terms on this day: T5 (blocked pool mean -$229.48), T4 (-$236.25), T1 (the NKD
  abstention), T2. T3 blocked a positive pool (+$1,217.50) but zero winners — it is doing MAE
  work, not value work, which is exactly what it was written for.

## 13. BRIEFING D1 ANSWERED: MID-LEG CONTINUATION ENTRIES PAY
Inside an established NY down-leg with concordant phase flow, entries 20-35 minutes AFTER the
phase extreme paid $1,376-$1,670 with MAEs of $44-$244 (HG-057109-S, -057765-S, -055739-S).
Entry quality did not decay with distance from the extreme on this day. D1 = YES for
continuation shorts in a flow-concordant NY phase; still untested for longs (there were none).

## 14. FLOW CONCORDANCE IS SCOPED, NOT UNIVERSAL (P015, new)
`sign(S8 phase sflow) == side` with `|sflow|/phase_vol >= 5%` is a correct REQUIREMENT for
rollover/continuation entries: the pool it blocked alone averaged -$229.48, and its founding
case HG-20210701-049049-L (P001 geometry perfect, flow opposed) was a **-$930 hard stop-out**.
It is NOT a requirement for a level-first-test rejection: the reader's single discretionary
override (SI-20210701-054339-S, taken on `S4 OR_EXT NY|OR30|k1.0|+1 tc=1 test_m=2` against a
phase high printed 156s earlier on that level) paid **+$1,682.50 with mae $37.50**, and its five
un-overridden siblings paid $1,470-$1,632 each. Mechanism: a first-test seller need not have
been selling all phase — that is what "first test" means.

## 15. ~~§1 STRUCK~~ — the per-asset phase-close asymmetry does NOT survive a day-complete count
Warm-up §1 (n=8/asset) read: HG 8/8 positive and 0/8 walled, NKD worst at 5/8 walled. Day-complete
on 2021-07-01: **HG 47.9% walled, SI 50.9% walled, NKD 15.5% walled** — the ranking inverts.
HG's higher mean (+$81.96 vs SI -$27.06, NKD -$82.10) is a right-tail effect, not a gentler wall.
Open question 2 above is answered "sampling artefact" for the wall and left open for the mean.

## 16. SI's fvol ROW IS REFUSED FOR THE WHOLE 2021-07-01 SESSION
All 391 SI sheets carry `COVERAGE=.` and `ladder_position=.` (REFUSED: no move_q50_usd_per_sigma;
sigma_source=ATR14_RAW_FILL). **P001 and every coverage/ladder term are structurally unevaluable
on 37.6% of the day.** The substitute that worked is the range-EXTENSION arithmetic computed from
S3 phase H/L, S13 entry mid and S13 mult — it needs no fvol at all, and it is the term that
carried the day's best SI call. RECOMMENDED: census how many (asset, date8) sessions in E1 carry
a refused fvol row; if it is common, the extension arithmetic should be the primary A1 form and
the ladder form the secondary.

## 17. NKD ABSTENTION IS A RESULT
Zero takes on 310 NKD candidates, and NKD produced **zero D-021 winners** all session (best
certificate $857.50). `S8 60s n/vol` alone blocked 278 of 310. NKD's walled fraction is the
LOWEST of the three (0.155): on this session NKD did not stop trades out, it had nothing to offer.

## 18. SECTIONS S6/S10/S11/S12 ARE NOW 0-FOR-1,063
Not opened once in 1,039 day-complete calls (11 deep reads), after 0-for-24 in the warm-up. The
88-field triage index built from S1-S5/S7-S9/S13 carried 1,028 of 1,039 calls with no sheet read
at all. This is a sheet-budget finding the builder should act on.

## 19. OPEN QUESTIONS CARRIED TO DAY 2
1. Does the side/phase concentration of §10 (all winners SHORT, all NY) hold on another session?
2. Does the n_terms monotonicity of §11 survive with T6 dropped and T7 widened?
3. The A|B|C value grade was monotone across calls (TAKE $1,543 vs SKIP -$25) and across the
   SKIP pool (B +$147 vs C -$60) but INVERTED within TAKEs (A $1,523 vs B $1,633, n=9/2). The
   grade is not yet calibrated at the top; CC-M2-4.4 needs a round, not a day.
4. The day-1 draw collides with the P-M2c warm-up sessions (POSTMORTEMS §0, defect D7). Day 2
   must draw from sessions the warm-up never touched.

---

# E1 STUDY DAY 2 UPDATE (2021-07-02, day-complete, n=935 across SI/HG/NKD)

Source: provenance/port_m2/E1_STUDY_LEDGER.tsv (sealed `f8bd5b3`) + E1_POSTMORTEMS.md day-2 section.
Taint CLEAN on all 935 rows (CC-M2-8.1 exclusion honoured). The reader LOST to both mechanical
baselines on this day; several §10-§19 claims above are struck, not deleted (D-059.1).

## 20. ~~§10 STRUCK~~ — THE SIDE CONCENTRATION IS A SESSION PROPERTY, THE PHASE ONE IS NOT
Day 1: all 48 D-021 winners SHORT. Day 2: **all 38 D-021 winners LONG** (and all SI). Day-complete
sides on 2021-07-02: LONG n=452 mean **+$292.15** with 38 winners; SHORT n=483 mean **-$389.86** with
**zero**. What survives two independent day-complete counts is the PHASE: **86 of 86 winners over two
sessions are in the NY phase**, none in TOKYO or LONDON. **Fields:** S14 winner_close by
(phase_dec, side). The phase term is now the reader's best-supported claim; the side term is dead as
an era fact and must never be encoded.

## 21. THE DOMINANT NEW FACT: THE CAPACITY ARITHMETIC IS A MEAN-REVERSION PRIOR
P017 RANGE_EXTENSION_ARITHMETIC (and P014, and every COVERAGE/ladder form of A1) measures the bar
against room INSIDE the phase range on the trade's side. A trade entered AT a fresh extreme has zero
such room by construction, so these terms **systematically refuse continuation/breakout entries and
accept only trades pointed back across the range**. On an INSIDE/AT_RANGE day that is an MAE filter
(day 1: sole-blocked pool +$1,217, 0 winners). On an EXPANDED day it is an anti-signal: on 2021-07-02
it appears in the refusal set of **24 of the 38 winners** (SI-051810-L +$1,707.50 at ext_needed
$512.5; SI-052297-L +$1,682.50 at ext $537.5).
**The regime flag is on every sheet and is two fields: S2 `day_type_so_far` {INSIDE, AT_RANGE,
EXPANDED} and `% of range_hat`, corroborated by S9 `surprise`.** RECOMMENDED CENSUS: winner rate and
mean certificate by (ext_needed band x S2 day_type), whole era. If the interaction is real, the A1
term must be regime-conditional and the fix is cheap.

## 22. P015 FLOW CONCORDANCE IS HORIZON-FRAGILE: THE PHASE WINDOW BECOMES A FOSSIL
The NY phase on 2021-07-02 straddled the 12:30Z Employment Situation. Its cumulative sflow stayed
SELL all afternoon (a pre-release accumulation) while the 5m/30m windows and the price ran UP.
P015 read the phase window, so it pointed the reader SHORT into a $2,525 up-move: its sole-blocked
pool was **+$120.81 with 3 winners** (day 1: -$229.48 with 4 winners), and it appears in the refusal
set of **29 of the 38 winners**. Two days, two opposite verdicts: P015 is 1-1 and is now era-status
CONTESTED.
**Fields for the repair, all on the sheet:** S12 `last_scheduled` event age; S8 sflow at 60s/5m/30m
vs phase — the disagreement BETWEEN horizons is the signal, and it is exactly what the reader wrote
down in the think-aloud transcript at 14:35:09 and then used only as a veto.
RECOMMENDED CENSUS: sign agreement between S8 phase sflow and S8 30m sflow, and winner rate
conditional on their DISAGREEMENT, by (era, class); plus the same split by "phase contains a
scheduled release" from S12.

## 23. THE n_terms LADDER OF §11 DOES NOT SURVIVE (P016 falsified out of sample)
2021-07-02: 6 terms -> +$117.19 / 8.4% winners; 7 -> +$8.51 / 5.6%; 8 -> -$317.03 / 4.5%;
**9 -> -$861.25 / 0.0%**. Day 1's monotone ladder inverts. This agrees with the CC-M2-9.1 census
verdict (P016 beta -$95, p=.07, CONCENTRATOR(feature) not an entry rule). A conjunction of vetoes has
no direction of its own: it inherits the direction of whichever term is directional, and adding terms
makes it more confidently wrong when that term is inverted.

## 24. THE TWO NEW VETOES BOTH WORKED, AND VETOES ARE NOT ENOUGH
* **P018 TWO-STREAM OPPOSITION (T9, new)** — refuse when S8 60s sflow opposes at >=10% of 60s volume
  ON >= 20 contracts AND S5 mid_slope(T-1m) opposes. Day 2 sole-blocked 5 candidates, mean -$422.50,
  0 winners. Validated on day 1 before use (blocks 146, mean -$29.27, 0 of the 10 eight-term takes).
  Born on SI-20210702-052509-S; transcript committed.
* **P019 ANTI-CHASE (T6, new)** — refuse when the trade-side phase extreme is STALE (>600s) and the
  1-minute drift runs against the trade by more than one S9 rv_nowcast w60 unit. Day 2 sole-blocked
  1 candidate at -$930; day 1 blocks 101, mean -$45.90, winner rate 4.0% vs a 4.62% base.
* T7 (widened to 3,600s) and T8 sole-blocked 8 each, all at -$930.
All four are correct refusals costing zero winners across the day — and the day still lost $1,953,
because the entry criterion was pointed at the wrong side. **Refusal quality is not the binding
constraint on this program; direction is.**

## 25. THE ONE-POSITION RULE MAKES A SESSION A SINGLE BET (scoring-instrument fact)
Exit_default is session close on every candidate of both study days, so the FIRST take of a session
holds the seat until 22:59:59 and every later take is forfeited. The reader's best call of day 2
(HG-20210702-058378-L, +$620 close, +$1,007.50 peak, unwalled — a deliberate long probe of §10 taken
against the reader's own flow term) earned nothing because the HG seat had been spent 5.6 hours
earlier on a -$92.50 short. Both days' entire margin (+$2,380 / -$2,398) is decided by which single
candidate per session the seat was spent on. Flagged for the orchestrator as an instrument property:
a per-row rule cannot select the best candidate of a session.

## 26. NKD, TWO DAYS: 514 CANDIDATES, ZERO WINNERS
Day 2: 204 NKD candidates, 0 D-021 winners, mean -$66.64, **walled fraction 0.000** (day 1: 0.155).
The reader abstained on both days; the best mechanical baseline lost $460 on NKD today. NKD's
LEVEL-FIRST-TEST family (briefing D3) finally appeared — 5 cases — and **all five arrive in a dead
book** (S8 60s n = 0, 0, 1, 2, 13). D3 gets its first answer: NKD first-tests in E1 may be signal-pure
but they are untradeable at the $1,000 bar. Two sessions is not a census, but this is now the reader's
most reliable positive finding and it bears on the s14 SI+NKD port target.

## 27. PRE-MORTEMS BECAME THE BEST INSTRUMENT ON THE SHEET (and I ignored them)
Five of six committed pre-mortems named the exact mechanism that killed their trade, in writing,
before the seal (the sixth, on the long probe, was wrong and the probe paid). Day 1's eleven all
failed to fire. The asymmetry is the lesson: **a pre-mortem that names a mechanism measurable on the
sheet is a veto the reader has already reasoned to and then declined to encode.** Proposed protocol
strengthening for CC-M2-5.4: a pre-mortem naming a measurable mechanism must either become a term or
the take is abandoned.

## 28. A|B|C IS ANTI-CALIBRATED (CC-M2-4.4)
Day 2 TAKEs: A -$930 (n=10) / B -$759.55 (n=22) / C -$930 (n=1). SKIPs: B -$117.66 (n=348) /
C +$21.00 (n=554). Inverted on both halves. Over two rounds the grade has never been monotone inside
the TAKEs. As computed it counts how many of the reader's own terms are at their strong setting, i.e.
it measures the rule's confidence, not the candidate's value. It disqualifies itself as a judge-aux
target until it is rebuilt on evidence outside the rule.

## 29. SECTIONS: S12 IS PROMOTED, S6/S10/S11 ARE NOW 0-FOR-1,998
S12 (`last_scheduled` event age) is the field that identifies a fossil phase-flow window (§22) and it
changed nothing on day 1. S2 (`day_type_so_far`, `% of range_hat`) is the regime flag §21 needs. Both
are cheap and both are missing from the triage index (defect D9). S6, S10 and S11 have not been opened
in 1,998 day-complete calls.

## 30. OPEN QUESTIONS CARRIED TO DAY 3
1. Is the NY-phase concentration (86/86 over two sessions) real, or is it an artefact of where
   candidates are generated? Census: winner rate by (phase_dec, asset) over the whole era.
2. Does the (ext_needed x S2 day_type) interaction of §21 hold on the era? This is the highest-value
   census the round has produced.
3. Does horizon disagreement (S8 30m vs phase sflow) beat P015's phase reading? §22.
4. Can a reader with only per-row information ever win a one-position/session-close game (§25), or is
   the instrument measuring candidate selection the reader cannot perform?
5. Both new vetoes (P018/P019) need an era census; each has two days of n and zero winners lost.

---

# E1 STUDY DAY 3 UPDATE (2021-07-05, day-complete, n=644 across SI/HG/NKD)

Source: provenance/port_m2/E1_STUDY_LEDGER.tsv (sealed `481b963`) + E1_POSTMORTEMS.md day-3 section.
Taint CLEAN on all 644 rows in the prior-round sense; the 5 TAKE rows carry the new row-level value
SCAN-EXPOSED (§37). The reader BEAT every mechanical baseline and its own day-2 policy, TIED its
frozen day-1 policy, and MISSED the day's only seat entirely. Several §20-§30 claims above are
struck, not deleted (D-059.1).

## 31. THE DAY-1-vs-DAY-2 SEPARATOR (the round's primary object): FOUND, MEASURED, AND NOT A COMPASS
The ex-ante field that separates the two disagreeing days is **S12 `next_scheduled` countdown vs S3
`runway to_sess_close`** (plus `last_scheduled` once it has fired): does a scheduled release fall
INSIDE this session? It separates them perfectly — 0 of 1,039 rows on 2021-07-01, 935 of 935 on
2021-07-02 — and P015 PHASE_FLOW_CONCORDANCE flips sign exactly with it:

| session contains a scheduled release | phase flow WITH the trade | phase flow AGAINST |
|---|---|---|
| NO (2021-07-01) | n=327 mean **+$262** win 8.9% | n=331 mean -$262 win 0.0% |
| YES (2021-07-02) | n=232 mean **-$552** win 0.0% | n=239 mean +$542 win 15.9% |

**But it cannot be used as a compass, and this is the important half.** The natural repair — "on
event days take the direction from the post-event 30m window" — fails: on 2021-07-02 EVERY flow
horizon was anti-predictive (30m WITH the trade: mean -$387, 0 winners), and a rule built on it fires
31 times at -$737 a trade. 2021-07-05 is a NO-release session, so the flag predicted a day-1-like
regime; the day then produced its winners on the day-2 side of every flow term. **The flag is a real
one-bit fact about two sessions and it is perfectly collinear with the session, which is exactly the
shape of §10's side term that §20 struck.** Recorded as a censusable object (P022's parent), never as
a term. **Fields:** S12 next_scheduled countdown, last_scheduled age; S3 runway_to_sess_close.

## 32. ~~§20 STRUCK~~ — THE WINNERS ARE NOT ALWAYS IN NY, AND THE PHASE TERM WAS AN EXIT TERM
86 of 86 winners over two sessions were NY, which I hardened into "take only rows whose exit_default
phase close equals the session close" (0 winners in 863 rows without it). **All 8 winners of
2021-07-05 are HG TOKYO longs (03:02:59-03:20:54) exiting at the 07:00 TOKYO phase close**, certs
$1,001-$1,139. Three-session count: **86 NY / 8 TOKYO of 94.** The surviving statement is weaker and
mechanical: *the bar needs hours of runway to the binding exit, and NY is usually — not always — the
phase that has them.* A 03:03 TOKYO entry has 3h57m. **CC-M2-10.3's phase-close seating is what makes
such a seat exist**; under session-close-only scoring the day's entire winner set is unpriceable.
RECOMMENDED CENSUS (supersedes P020's): winner rate by (phase_dec, asset, **runway-to-binding-exit
band**) over the era — the runway band is the candidate mechanism, the phase is the proxy.

## 33. THE ABSORPTION FAMILY IS REAL, AND BOTH OF MY MAGNITUDE TERMS WERE WRONG
The conjunction that survived days 1 and 2 — 5m aggression OPPOSED at magnitude with S8
`through_book_600s` on the trade's side — was measured at n=23 mean +$621 (day 1) and n=45 mean +$615
(day 2), 56-58% winners against a 4.4% base. On day 3 it fires ZERO times and the day's 8 winners sit
just outside it on two fields:
* **the absolute 5m volume floor (>= 500).** The winners' 5m volumes are 196-544 on a US-holiday tape;
  their `5m vol / phase volume` ratios are **8.1-9.9%**, which a relative floor at 0.08 admits. The
  floor was pre-registered after testing the relative form — and the test was scored on *replay
  dollars from one seat per session* (n=2 sessions) instead of on the pooled candidate pool. **Method
  law for the rest of the round: settle a threshold on the pooled pool statistic, never on the replay.**
* **the through-book side term, whose sign was backwards.** The winners' through-book prints are
  10/4, 11/3, 3/1 through the BID — i.e. sellers clearing levels — while price refused to extend the
  phase low. That is P007 ABSORPTION_NO_RESPONSE exactly as P007 states it; requiring the prints to
  be on MY side contradicts the very term it sits next to. The confirmation absorption needs is a
  **price-failure** test (the aggression does not extend the trade-side extreme), not a side test.

## 34. THE MOMENTUM TERM IS NOW 3-FOR-3 VALUE-DESTROYING, IN THREE DISGUISES
Day 1 killed "slope signed with the trade"; day 2 rebuilt it as ANTI-CHASE; day 3 rebuilt it as
MOMENT OF TURN ("the opposed aggression has stopped AND the price stream has turned"). All three of
day 3's committed minimal pairs were built on that field, all three predicted the pair would pay
less, and **all three are refuted in the same direction**: HG-055036-S +$432.50 vs my +$382.50,
HG-055228-S +$351.25 vs my +$220.00, HG-056201-S +$163.75 vs my +$145.00. Waiting for the turn means
entering worse; inside a correct thesis it is a pure tax. **Fields:** S5 mid_slope_$/min(T-1m) — and
the field that DID order those entries was entry price relative to the level, monotonically.

## 35. THE GIVE-BACK IS THE BINDING CONSTRAINT ON THIS PORT'S EXIT, NOT THE ENTRY
Every one of the day's 5 takes was directionally right, unwalled, and inside the D-021 MAE
acceptance — peaks $538.75-$776.25 — and every one closed at a third to a half of its peak
(+$382.50, +$220, +$207.50, +$163.75, +$145). Two of five pre-mortems fired and both named the
give-back. Across three days the reader's correctly-diagnosed loss mechanism has been: the wall
(day 2), the side (day 2), and now the give-back (day 3) — and **the give-back is not something an
entry rule can fix.** Flagged for the orchestrator alongside §25: on a holiday session whose tape
ends 6 hours before the nominal close, a session-close exit prices the trade at whatever a dying book
last printed.

## 36. THE HOLIDAY SESSION IS INVISIBLE ON THE SHEET (defect D15)
2021-07-05 is the US Independence Day observed holiday: the last candidate is at 18:59 clock (16:59Z)
against a nominal 22:59:59 session close, and every `runway` and `exit_default` field on all 644
sheets is computed to 22:59:59. SI's NY 60-second median volume is 21 contracts against 79/135 on the
two prior days. The reader can infer the session type only from S8/S5 participation. A
`session_expected_close` field (exchange-calendar join) belongs next to `exit_default`.

## 37. NEW TAINT VALUE: SCAN-EXPOSED (a structural hazard, named at row level for the first time)
The triage index is day-complete, so scanning it shows later rows' `mid` — the price path after the
second being called. On a session whose tape ends early the LAST row's mid is effectively the session
close the exit rule uses. The committed policy is a pure function of one row and is mechanically
unexposed; the 5 discretionary TAKEs are not and are marked. Days 1 and 2 shared the exposure and did
not record it. Build item **D14: `triage_index.py --as-of SEC`**.

## 38. THREE DAYS, THREE REGIMES: NO PER-ROW RULE IS YET POSITIVE ON ALL THREE
Day 1 all-short mean-reversion inside the NY range; day 2 all-long release-driven expansion; day 3
all-long TOKYO reversal on a dead holiday tape with an NY give-back. A systematic search over
direction fields (slope 1m/5m/15m, flow at 60s/5m/30m/phase, through-book, fuel-map polarity, phase
price direction) found 94 two-day-positive conjunctions and the best of them (§33) is negative on the
third day. **What is positive on all three days is only this: a live book (S8 60s n>=5, vol>=10) and
a fresh trade-side extreme (S3 phase H/L age minutes, not hours).** Everything else has flipped at
least once. The reader's per-era lift curve (D-059.6) must be read with that in front of it.

## 39. OPEN QUESTIONS CARRIED TO DAY 4
1. Does the runway-to-binding-exit band (§32) beat `phase_dec` as the winner-concentration variable
   over the era? This replaces the P020 census as specified.
2. Does the absorption family with the two day-3 repairs — relative-OR-absolute volume floor, and a
   price-failure confirmation in place of the through-book side term — survive all three days?
   (§33; it is the round's best candidate object and it now has a specified repair.)
3. Is `ext_needed` measuring capacity at all, or is it a proxy for "which side of the session's own
   trend the trade points"? Day 3: new-range LONGS won, new-range SHORTS walled, in-range shorts
   made small money — on the same session (§7 of the post-mortems). P021 is 1-1.
4. Should the reader stop building momentum/confirmation terms entirely (§34, 3-for-3 against)?
5. The give-back (§35): is there an ex-ante field that separates a certificate that holds its peak
   from one that gives back two thirds? This is now the round's largest unexplained loss channel.

---

# E1 STUDY DAY 4 UPDATE (2021-07-06, day-complete, n=1,268 across SI/HG/NKD)

Source: provenance/port_m2/E1_STUDY_LEDGER.tsv (sealed `613fc6f`) + E1_POSTMORTEMS.md day-4 section.
Taint CLEAN on all 1,268 rows; the day-3 SCAN-EXPOSED hazard was closed by tool in-lane
(`engine/port_m2/e1d4_asof.py`, the D14 mechanic), and the TAKE rows carry `CLEAN;AS-OF-PREFIX`.
The reader LOST to the best mechanical baseline by **$8,123.75** — the worst day of the round — and
the loss decomposes cleanly onto two terms it added this round. Several §31-§39 claims are struck.

## 40. THE DAY: 136 WINNERS, ALL NY SHORTS — FOUR SESSIONS, FOUR MORPHOLOGIES
LONG n=650 mean **-$378.87 with ZERO winners**; SHORT n=618 mean +$608.38 with **136** (SI 76,
HG 52, NKD 8). Per asset: SI +$150.06, HG +$162.73, NKD -$60.89. Day DP ceiling $10,542.50.
The four unblinded sessions now read: NY shorts (07-01), NY longs (07-02), TOKYO longs (07-05),
NY shorts (07-06). **The winner morphology has been different every single session:** rollover
shorts inside the range; release-driven expansion longs; reversal longs on a dead holiday tape; and
now mature-trend CONTINUATION shorts entered a median 3,320s after the phase high, needing a median
$750 of brand-new range, with the 5-minute aggression WITH the trade in 105 of 136 cases.

## 41. THE ROUND'S REAL DEFECT IS THE SELECTION CRITERION (this supersedes §38's reading)
§38 said only two terms were positive on all three days. This day says that test is too weak. The
direction term I built the day-4 rule on — 5m aggression OPPOSED at magnitude — is positive on all
four sessions inside its family (+$223 / +$157 / +$251 / +$90) and **beats its own mirror on exactly
one of them** (mirror: +$427 / -$587 / +$232 / +$133). A term can be positive every day and still be
the worse of the two arms on most days, because "positive" is inherited from the day.
**METHOD LAW (adopted for the rest of the round, alongside day 3's pooled-pool law): a direction
term must beat its own MIRROR on every session, not merely be positive on every session; and a
threshold must be settled on the pooled pool, not on the set of days it makes positive.**
Both terms this round's rule added (T6 ext_needed <= $450, T7 jump_frac < 0.45) were chosen by the
weak criterion, and both are what lost the day (§43).

## 42. P026 CONTINUOUS_TAPE: BORN AND KILLED IN ONE DAY, ON A PRE-REGISTERED TEST
S9's bipower jump fraction `(RV-BV)/RV` over 1,800s looked like the round's first ex-ante handle on
the GIVE-BACK (§35/§39.5): over days 1-3, rows with a peak above $600 kept 0.41-0.50 of it below
jump_frac 0.45 and 0.20-0.27 above 0.55, with 87 of 94 winners below 0.45 and **0 of 94 above 0.55
in 1,464 rows**. On 2021-07-06 the relationship is gone: keep is flat at 0.06-0.12 across every band,
46 of 136 winners sit above 0.45, and the *lowest* band (<0.30) is the day's worst pool (-$310).
As a term it sole-blocked 11 rows worth **+$2,148.98 mean with 5 D-021 winners** — the most
expensive refusal any term of this round has made. **P026 is DEAD, in the P014 class (killed in the
round that birthed it), and the give-back question of §39.5 is re-opened unanswered.**

## 43. THE LOSS DECOMPOSES ONTO THE TWO TERMS THE READER ADDED THIS ROUND
Committed rule (7 terms): 44 takes, replay **-$2,953.75**. Same rule minus T7: +$1,056.25. Minus T6:
-$667.50. **Minus both — i.e. the five terms inherited from days 1-3 (live book, runway, freshness,
opposed aggression, magnitude) — 80 takes, 8 winners, replay +$4,277.50, capture 0.501**, second
only to the saturated EARLIEST arm (+$5,170.00) and ahead of every threshold arm. Mirroring the
direction term instead does NOT rescue the day (-$4,078.75): the day's seats are not the sign flip
of the reader's seats, which is the same thing §38 has said for two days.

## 44. P025 RUNWAY_TO_BINDING_EXIT IS 230-FOR-230 AND IS NOW THE ROUND'S BEST-SUPPORTED OBJECT
Runway to the binding (phase-close) exit >= 12,000s passes on **136 of 136 winners today** (minimum
21,903s) after 94 of 94 across days 1-3 (minimum 13,146s). Four day-complete sessions, 230 winners,
zero exceptions, two roster fields, no judgement. Winner retention of the other terms today: live
book 128/136, magnitude 107/136, jump 90/136, freshness 74/136, absorbed aggression 31/136, in-range
bar 21/136. **Fields:** S13 exit_default, S3 runway to it, S1 phase_dec as a CONTROL. The census
ordered in CC-M2-12.4 is the one to run first.

## 45. ~~§26 STRUCK~~ — NKD HAS SEATS; IT IS THIN, NOT EMPTY
Three sessions, 711 candidates, 0 winners; this session, 312 candidates, **8 D-021 winners** (NY
shorts, 15:07:05-15:33:58). NKD's mean candidate still lost $60.89, 263 of 312 rows fail the
live-book floor, and every mechanical arm that traded NKD lost on it, so the reader's fourth
abstention still scored $0 against -$955 to -$1,745. What is struck is the ERA claim ("untradeable
at the $1,000 bar"), not the abstention. **A rule that can only see the 60-second book will keep
missing NKD's seats; NKD is a leading-regime problem, not a book problem.**

## 46. THE EXIT RULE, AGAIN — AND THIS TIME PHASE-CLOSE SEATING SAVED A TRADE
The day's one correctly-sided take (HG TOKYO short, 03:15:31) closed **+$182.50 at its 07:00 phase
close with a peak of +$3,313.75** later in the session, having survived an $843.75 adverse excursion
— **$56.25 under the $900 wall**. Under session-close scoring it is a huge winner; under phase-close
seating it is a small one; under a $56 tighter wall it is a stop-out. Three of the four sessions have
now produced a headline number that is an EXIT-RULE artefact rather than an entry-quality fact
(§4, §25, §35, and this). **The exit rule is the largest single lever on this program's measured
performance and it is not a reader decision** (D12/CC-M2-10.3 fixed the seat; the wall and the
horizon remain orchestrator parameters).

## 47. THE PRE-MORTEM IS NOW THE READER'S BEST-CALIBRATED INSTRUMENT (3 for 3 today)
All three seat pre-mortems named the mechanism that decided the trade, and the two that named a
measurable trigger were correct within minutes (the SI shelf broke exactly as written; the HG
staircase added rungs exactly as written). Four-day record: 0/11, 5/6, 2/5, 3/3. On every day it
has fired it was ignored as a veto. **The day-2 proposal (a pre-mortem naming a measurable mechanism
must become a term or the take is abandoned) would have saved $1,860 today and cost nothing on day
3.** Re-opened for the orchestrator with four days of evidence instead of one.
Related: S10's developing POC/VAH priced BOTH losing seats before they were taken (2-for-2 on the
days S10 has been read) and it is still not in the triage index (defect D17).

## 48. OPEN QUESTIONS CARRIED TO DAY 5
1. The mirror test (§41) applied backwards: which of the round's surviving objects beat their own
   mirror on all four sessions? P025 has no mirror (it is a scheduling fact); P004 does not either.
   Every DIRECTION object in the ledger now fails the test on at least one session.
2. If no per-row direction term survives the mirror test, the honest day-5 experiment is a rule with
   NO direction term at all — take the seat the runway/participation terms admit, on the side the
   *session* is already on — and measure whether trend-following beats fading on the pooled four
   sessions. Four sessions: 2 short-winner days, 2 long-winner days, and on every one of them the
   winners' 5-minute flow was mostly WITH the trade (105/136 today, and the day-2 winners' flow was
   opposed only on the phase horizon).
3. Does the give-back have ANY ex-ante handle now that P026 is dead (§42)? The one field with a
   two-for-two record is S10's developing POC distance, and it needs to be in the index to be tested.
4. Should the reader's rule keep the two terms that survived four sessions (P004 live book, P025
   runway) and let the MODEL supply direction — i.e. is the reader's remaining job to certify
   feasibility rather than to pick sides? CC-M2-11.3 already says the validated objects are all
   concentrators; four sessions of direction failure is the strongest version of that argument.
5. D16: the frozen baselines could not be run against the current extractor's output without a
   compatibility view. Every future day inherits that hazard until the tooling lane fixes it.

---

# E1 STUDY DAY 5 UPDATE (2021-07-07, day-complete, n=1,185 across SI/HG/NKD)

Source: provenance/port_m2/E1_STUDY_LEDGER.tsv (sealed `398f3e7`) + E1_POSTMORTEMS.md day-5 section
+ baselines/E1D5_BASELINE_SCORES.md. Taint CLEAN on all 1,185 rows; the two seat TAKEs carry the new
row value `VETO-TABLE-SCANNED` (§57/D18). The day was the DECLARED EXPERIMENT of CC-M2-13.4, all
three arms fixed before the session was seen. The reader LOST to the best mechanical baseline by
**$4,297.50**, BEAT three of its four frozen predecessors, and produced the round's first
positive-mean take set (+$160.83 vs a -$45.36 skip pool) with **zero D-021 winners in it**.
Several §40-§48 claims are struck.

## 49. ~~§40/CC-M2-13.3 STRUCK~~ — THE SIDE IS A **PHASE** VARIABLE, NOT A SESSION VARIABLE
Four sessions said "winners concentrate on ONE side per session". 2021-07-07 has winners on BOTH
sides of BOTH metals: SI 2 LONDON LONGS (07:04, 07:32) + 26 NY SHORTS (13:03-15:52); HG 3 LONDON
LONGS (07:02-07:13) + 11 NY SHORTS (14:07-14:28); NKD 4 TOKYO LONGS (02:01). **What has never been
split in five day-complete sessions is the (asset, PHASE) cell** — day 1 NY shorts, day 2 NY longs,
day 3 TOKYO longs, day 4 NY shorts, day 5 TOKYO longs + LONDON longs + NY shorts. The session-side
state variable ordered in CC-M2-13.3 is measuring the wrong unit. **Fields:** S14 winner_close by
(asset, phase_dec, side). RECOMMENDED CENSUS: side purity within (asset, phase_dec) cells over the
whole era — if the cell is pure at population scale, the leading-regime forecaster's target is a
PER-PHASE side, not a per-day side.

## 50. THE FIRST-CONFIRMED-OUTCOME-SIGN ESTIMATOR (P027) IS A LAGGING INDICATOR BY CONSTRUCTION
Declared before the day, traded as ordered, and it passed **0 of the day's 46 winners**. Five
sessions, ten asset-sessions with winners: sign 7 right / 3 wrong, and **7 of the 7 correct
confirmations arrived after their asset-session's first winner. Not one confirmation in five
sessions has ever preceded the winner window it was meant to open.** The mechanism is exact: the
first completed $1,000 move IS the move, so its confirmation second is its end. NKD is the clean
proof — the estimator stamped the session SHORT at 02:01:14 and the four winners are LONGS at
02:01:14-02:02:07, i.e. the reversal off the very low that confirmed it.
**Two defects in the estimator's own form, both cheap:** (i) its NKD founder
`NKD-20210707-002147-S` has `f60_n=0, f60_vol=0, f5m_vol=0` — a DEAD-BOOK row P004 refuses; a
candidate that cannot be traded must never set session state; (ii) it is session-scoped and never
expires, so a 09:01 LONDON confirmation governed a 16:19 NY decision. Per §49 it should be
PHASE-scoped. **Mirror-law status: it beats its mirror on 3 of 5 sessions => FAILS CC-M2-13.1**
(pre-registered as failing before the day). See PATTERN_LEDGER P027.

## 51. PRE-MORTEMS AS VETOES: +$2,477.50 ON THE DAY, -$12,592.50 OVER THE ROUND, AND BOTH ARE TRUE
Day 5 obeyed the four-day-old proposal for the first time. On this session: 97 of 112 policy TAKEs
vetoed, vetoed pool mean **-$679.42 with 0 winners and 0.732 walled**, standing pool **+$160.83 with
0.000 walled**, both would-be seats -$930 hard stop-outs, **replay delta +$2,477.50 at a cost of
zero winners**. Applied mechanically to the refusal core on all five sessions the same three
triggers are **-$12,592.50 and cost 91 of 99 winners**, and the damage is entirely V1/P028 (§52);
V2 (fuel-map overhang) and V3 (P018 two-stream opposition) are net-positive refusals on all five.
**THE TRANSFERABLE STATEMENT: a pre-mortem is an excellent detector of what will kill THIS trade and
a bad rule, because promoting it to a standing term inherits every weakness of the object it names.
CC-M2-10.4's original ruling — auto-log as a hypothesis, do not promote without a census — is
vindicated by the round-level number and contradicted by the day-level one, and the honest reading
is that the veto should bind the SEAT decision (where it is a judgement about one book) and never
the population.**

## 52. P028 BAR_OUTSIDE_DEVELOPING_VALUE — MINTED, CENSUSED ON FIVE SESSIONS, DEAD IN ONE DAY
S10's developing value area vs the price a $1,000 certificate requires. Winner-rate lift of "bar
INSIDE the VA" over "bar OUTSIDE": 0.00x / 0.66x / 0.00x / 0.08x / **7.15x** — spectacular on the
session that minted it, anti-predictive on the four before it, pooled **0.80x** with the inside-VA
pool at -$214.77 mean against +$39.08. **DEAD ON BIRTH, in the P014/P026 class**, and the third
magnitude object this round to be minted on the sessions that made it look right. S10's two-for-two
reputation (§47) came from two hand-read cases and does not survive a count.
What survives is the instrument: `e1d5_s10.py` now writes `d_POC/d_VAH/d_VAL/in_VA/bar_px/
bar_outside_va` for every candidate of all five study days (defect D17 answered in-lane).

## 53. P025 RUNWAY_TO_BINDING_EXIT IS 276-FOR-276 AND IS THE ONLY FIVE-SESSION OBJECT IN THE LEDGER
46 of 46 winners today (minimum winner runway 19,653s) after 230 of 230 on days 1-4; **0 winners in
the 304 rows below 12,000s.** Five day-complete sessions, 276 winners, zero exceptions, two roster
fields, no judgement, no mirror to fail. Every other term of the inherited core leaks winners today:
live book 44/46, freshness 41/46, aggression-at-magnitude 33/46, magnitude floor **23/46**.

## 54. THE INHERITED REFUSAL CORE IS NOT A STANDING WINNER EITHER (§43 qualified)
Day 4's "five inherited terms would have made +$4,277.50" becomes -$278.75 on day 5 (157 takes, 9 of
46 winners retained). Over five sessions the core arm is +$6,437.50 in replay — real, but carried by
two sessions. The core is a FEASIBILITY filter, not an edge: it says a seat is possible, never that
it is on the right side, and the two days it lost are the two days the side went against it.

## 55. THE MAGNITUDE FLOOR'S ABSOLUTE CLAUSE IS A LATENT BUG AND IT COST NKD ITS SEAT
NKD's 4 winners carry `terms=11110`: live book, runway, freshness and aggression all pass; T5 fails
on 5-minute volumes of 118-140 contracts against the ABSOLUTE 200 floor — while their RELATIVE
volumes are **41.5%-45.0% of phase volume**, five times the 8% clause. The term is written
`v5 >= 200 AND (v5 >= 500 OR v5 >= 8% phase)`, so the absolute gate fires before the relative clause
can rescue anything. **Repair (one line): `v5 >= 200 OR v5 >= 8% of phase volume`.** This is day 3's
lesson (§33) surviving in the shape of the term after being fixed in its threshold. Two sessions
running, NKD's seats are invisible to this rule for a reason that has nothing to do with NKD.

## 56. ~~§45 CONFIRMED, §26 STAYS STRUCK~~ — NKD IN E1 IS THIN AND REAL
Five sessions, 1,404 NKD candidates, 12 D-021 winners (8 on 07-06 NY shorts, 4 on 07-07 TOKYO
longs), mean candidate -$50 to -$67 every session, and the reader has abstained on all five. The
abstention has never been punished (best mechanical arm on NKD today: -$607.50) and has now missed
two real seats. NKD's winners arrive in tight clusters of 4-8 candidates inside 30 seconds to 30
minutes; a rule that reads only the 60-second book, or an absolute contract floor, will keep missing
them (§55).

## 57. NEW TAINT VALUE: VETO-TABLE-SCANNED (defect D18)
Making the pre-mortem veto measurable across 112 takes rather than 2 required grading the day's take
list against the triggers as a TABLE, which is the SCAN-EXPOSED hazard the as-of view was built to
close. The calls are mechanically unexposed (every trigger is a pure function of one row), but the
choice of which rows to deep-read was not. **The veto walk must be driven by the same as-of stepper
as the index — and `triage_index.py --as-of` (D14) is STILL not at HEAD after three days of the
reader building its own.**

## 58. OPEN QUESTIONS CARRIED TO DAY 6
1. Is the (asset, phase_dec) cell side-pure at population scale (§49)? This replaces the
   session-side probe of CC-M2-13.3 as specified and is the round's highest-value census.
2. Can ANY causal estimator of a cell's side confirm BEFORE the cell's first winner (§50)? Five
   sessions say the outcome-based family cannot, by construction. If nothing leads, the honest
   conclusion is that side selection belongs to the leading-regime forecaster (CC-M2-11.2) and the
   reader's job is feasibility certification (§48.4 answered YES).
3. Should the veto bind the SEAT and never the population (§51)? Day 5 is one session of evidence
   on each side of that line.
4. Does the phase-scoped, live-book-gated version of P027 beat its mirror on all five sessions? It
   is two guarded lines and the ledger already has the data.
5. The give-back (§39.5) is now three objects dead (P026, P028, and P017's in-range form). Is there
   ANY ex-ante field that separates a certificate that holds its peak from one that gives back two
   thirds — or is the give-back an EXIT-RULE artefact (§46) that no entry field can address?

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

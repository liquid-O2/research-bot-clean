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

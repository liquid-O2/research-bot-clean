# E1 BLIND ROUND — SCORING PASS (CC-M2-6 TEACHER-GATE INPUTS)

Computed by the scoring lane, 12 sealed days, 12418 calls. **This file reports arithmetic; the gate VERDICT is the orchestrator's (CC-M2-6 / D-075).**

## 0. SEAL + GIT ORDERING (verified by this pass)

* Scored ledger `provenance/port_m2/E1_BLIND_LEDGER.tsv`, git blob `cc3dbea886c5`, sha256 `0d0fed00dc901a63` — **identical to the blob committed at HEAD**; the on-disk bytes are the sealed bytes.
* The ledger's last modifying commit is `752918d`. **git numstat over its 13 modifying commits: 12422 lines added, 0 deleted (deleted_none=1), ending at 12422 rows.**
* **Outcome-artefact audit over `99ae1d5..HEAD`: 67 commits, 3 carrying an outcome-bearing path (case-insensitive match on blind_score / unblind / s14 / panel_ / truth).** THE RANGE IS NOT CLEAN — the commits carrying such a path are `4fff1bc`, `6310e71`, `cbe713f`, and each is listed with its files in `E1_BLIND_GIT_ORDERING.tsv`. This is a statement of fact, not a verdict: a scoring artefact committed AFTER the last seal does not taint the seals, and the commit ORDER in that table is what decides it.
* Frozen-arm identity check, COMPUTED: `e1_blind_declared_policy.py` re-run as committed was compared with the sealed `DECLARED` column of `E1BLIND_D*_ARMS.tsv` — 12418 rows compared, 12418 agree, 0 disagree (reproduces=1).
* Index provenance: the 12 triage COMPAT indices are UNTRACKED cache files, so they cannot be seal-checked against HEAD; their sha256s are stamped into the receipt (`input_sha256`, 12 entries) instead of the empty dict the previous receipt carried.

**R127 — DEPLOYABLE CALENDAR COVERAGE (computed).** The dated high-impact release universe is `context.high_impact_calendar (R36 impact-classified)`: 714 events, BOJ policy statement/CPI/Employment Situation/FOMC statement/ISM Manufacturing PMI/ISM Services PMI. It touches **5 of the block's 12 days** (coverage 0.417 against the declared minimum 0.50) — **the DEPLOYABLE readings are REFUSED and NOT published: a reading built on this calendar is an NFP/CPI/FOMC reading, not a prop-firm compliance reading, and D-077-UPDATE(3) calls DEPLOYABLE 'the reading that counts for the goal'**.

## 1. THE ROUND

| | |
|---|---|
| calls scored | 12418 |
| days / session-assets | 12 / 36 |
| reader TAKEs | 204 |
| reader replay seats | 49 |
| D-021 winners in the universe | 501 (base rate 0.0403) |
| summed DP ceiling (close) | $99596.25 |
| reader winner precision / base rate | 0.0294 / 0.0403 = 0.73x |

**SEATING RECONCILIATION.** The reader's sealed record claims **40 cell-seats** (one position per (asset,phase) cell, `seat_holder=` in the sealed interaction field). The CC-M2-10.3 scoring replay seats **49** of its TAKEs: all 40 of the reader's own holders plus **9 re-seats** that open when a position is stopped out at the $900 wall before its phase close. The scoring law is therefore MORE generous than the reader's own seating, not less; 22 of the 12,418 rows are walled among the seats.

| seating | n | realised $ |
|---|---|---|
| reader's own cell-seats | 40 | -287.50 |
| CC-M2-10.3 greedy replay (THE LAW, CC-M2-21.4) | 49 | -738.75 |
| DP seat-split (companion diagnostic) | 31 | +23651.25 |
| peak-exit companion reading (CC-M1-8) | 49 | +42980.00 |

Universe sizes by reading: SCIENCE 12418.

## 2. THE THREE CC-M2-6 BARS

| reading | bar | statistic | bar value | statistic − bar |
|---|---|---|---|---|
| SCIENCE | a_margin_vs_BASE_EARLIEST | $10972.50 (sum, BASE_EARLIEST) | 0.000 | +10972.5000 |
| SCIENCE | a_margin_vs_DECLARED | $-927.50 (sum, DECLARED) | 0.000 | -927.5000 |
| SCIENCE | a_margin_vs_E1D1 | $142.50 (sum, E1D1) | 0.000 | +142.5000 |
| SCIENCE | a_margin_vs_E1D2 | $-853.75 (sum, E1D2) | 0.000 | -853.7500 |
| SCIENCE | a_margin_vs_E1D3 | $1785.00 (sum, E1D3) | 0.000 | +1785.0000 |
| SCIENCE | a_margin_vs_E1D4 | $673.75 (sum, E1D4) | 0.000 | +673.7500 |
| SCIENCE | a_margin_vs_E1D5 | $5605.00 (sum, E1D5) | 0.000 | +5605.0000 |
| SCIENCE | a_margin_vs_E1D6 | $-6845.00 (sum, E1D6) | 0.000 | -6845.0000 |
| SCIENCE | a_margin_vs_E1D7 | $9676.25 (sum, E1D7) | 0.000 | +9676.2500 |
| SCIENCE | a_margin_vs_E1D8 | $-7882.50 (sum, E1D8) | 0.000 | -7882.5000 |
| SCIENCE | a_bar_positive_against_ALL_mechanical | $-7882.50 (sum, E1D8) | 0.000 | -7882.5000 |
| SCIENCE | a_margin_over_PREREGISTERED_arm | $10972.50 (sum, BASE_EARLIEST) | 0.000 | +10972.5000 |
| SCIENCE | a_margin_over_MEDIAN_mechanical_arm | $673.75 (sum, E1D4) | 0.000 | +673.7500 |
| SCIENCE | a_margin_over_MAX_arm_IN_SAMPLE_ORDER_STATISTIC | $-7882.50 (sum, E1D8) | — | — |
| SCIENCE | b_lift_close | — | 1.300 | — |
| SCIENCE | b_lift_close_raw_ratio | 2.105 | — | — |
| SCIENCE | b_mean_take_close_usd | -149.179 | — | — |
| SCIENCE | b_mean_skip_close_usd | -70.867 | — | — |
| SCIENCE | b_lift_peak_companion | 0.830 | 1.300 | -0.4695 |
| SCIENCE | c_replay_capture | -0.007 | 0.250 | -0.2574 |
| SCIENCE | c_replay_capture_vs_full_ceiling | -0.007 | 0.250 | -0.2574 |

Bar (a) inference (day-paired, GEE independence + Liang-Zeger sandwich, Cameron-Miller CR1, 12 day clusters):

| reading | best mechanical arm | sum margin | mean/day | se_CR1 | z | p (normal) | p (t,df11) | days + / − | p sign |
|---|---|---|---|---|---|---|---|---|---|
| SCIENCE | BASE_EARLIEST | $+10972.50 | $+914.38 | 960.26 | 0.952 | 0.3410 | 0.3614 | 7 / 5 | 0.7744 |
| SCIENCE | DECLARED | $-927.50 | $-77.29 | 150.28 | -0.514 | 0.6070 | 0.6172 | 1 / 2 | 1.0000 |
| SCIENCE | E1D1 | $+142.50 | $+11.88 | 517.20 | 0.023 | 0.9817 | 0.9821 | 6 / 6 | 1.0000 |
| SCIENCE | E1D2 | $-853.75 | $-71.15 | 540.15 | -0.132 | 0.8952 | 0.8976 | 5 / 7 | 0.7744 |
| SCIENCE | E1D3 | $+1785.00 | $+148.75 | 718.18 | 0.207 | 0.8359 | 0.8397 | 6 / 6 | 1.0000 |
| SCIENCE | E1D4 | $+673.75 | $+56.15 | 885.60 | 0.063 | 0.9494 | 0.9506 | 6 / 6 | 1.0000 |
| SCIENCE | E1D5 | $+5605.00 | $+467.08 | 697.82 | 0.669 | 0.5033 | 0.5171 | 7 / 5 | 0.7744 |
| SCIENCE | E1D6 | $-6845.00 | $-570.42 | 1252.46 | -0.455 | 0.6488 | 0.6577 | 3 / 9 | 0.1460 |
| SCIENCE | E1D7 | $+9676.25 | $+806.35 | 567.03 | 1.422 | 0.1550 | 0.1827 | 8 / 4 | 0.3877 |
| SCIENCE | E1D8 | $-7882.50 | $-656.88 | 726.89 | -0.904 | 0.3662 | 0.3855 | 4 / 8 | 0.3877 |
| SCIENCE | E1D8 | $-7882.50 | $-656.88 | 726.89 | -0.904 | 0.3662 | 0.3855 | 4 / 8 | 0.3877 |
| SCIENCE | BASE_EARLIEST | $+10972.50 | $+914.38 | 960.26 | 0.952 | 0.3410 | 0.3614 | 7 / 5 | 0.7744 |
| SCIENCE | E1D4 | $+673.75 | $+56.15 | 885.60 | 0.063 | 0.9494 | 0.9506 | 6 / 6 | 1.0000 |
| SCIENCE | E1D8 | $-7882.50 | $-656.88 | 726.89 | -0.904 | 0.3662 | 0.3855 | 4 / 8 | 0.3877 |

## 3. ARMS

### SCIENCE (universe 12418)

| arm | mech? | takes | mean TAKE $ | mean SKIP $ | lift close | lift peak | winners | precision | replay $ | capture |
|---|---|---|---|---|---|---|---|---|---|---|
| E1D8 | y | 247 | -73.09 | -72.13 | — | 1.117 | 34 | 0.138 | +7143.75 | 0.072 |
| E1D6 | y | 1033 | +69.17 | -84.98 | — | 1.275 | 96 | 0.093 | +6106.25 | 0.061 |
| DECLARED | y | 216 | -114.90 | -71.40 | — | 0.856 | 12 | 0.056 | +188.75 | 0.002 |
| E1D2 | y | 14 | +28.93 | -72.27 | — | 0.947 | 0 | 0.000 | +115.00 | 0.001 |
| READER |  | 204 | -149.18 | -70.87 | — | 0.830 | 6 | 0.029 | -738.75 | -0.007 |
| E1D1 | y | 6 | -122.71 | -72.13 | — | 0.855 | 0 | 0.000 | -881.25 | -0.009 |
| E1D4 | y | 334 | -106.68 | -71.20 | — | 0.833 | 21 | 0.063 | -1412.50 | -0.014 |
| E1D3 | y | 21 | -142.80 | -72.03 | — | 0.789 | 0 | 0.000 | -2523.75 | -0.025 |
| E1D5 | y | 762 | -119.24 | -69.08 | — | 0.862 | 27 | 0.035 | -6343.75 | -0.064 |
| E1D7 | y | 857 | -217.03 | -61.41 | — | 0.709 | 21 | 0.025 | -10415.00 | -0.105 |
| BASE_EARLIEST | y | 5980 | -59.52 | -83.89 | — | 1.020 | 197 | 0.033 | -11711.25 | -0.118 |

## 4. READER vs THE FROZEN DECLARED ARM (CC-M2-20.2's two arms)

The two arms differ on **12 of 12418 rows** (the reader's single RV2 evolution); the sealed summary claims 12. Every differing row is a NKD OPEN-DYNAMICS row.

| reading | reader replay | declared replay | day-paired margin | se_CR1 | z | p (t,df11) | days + / − | reader mean TAKE $ | declared mean TAKE $ | reader precision | declared precision | reader capture | declared capture |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SCIENCE | -738.75 | +188.75 | $-927.50 | 150.28 | -0.514 | 0.6172 | 1 / 2 | -149.18 | -114.90 | 0.0294 | 0.0556 | -0.007 | 0.002 |

## 5. PER-DAY SEQUENCE (SCIENCE reading, replay $ at phase close)

| day | date | RV | reader | declared | best-mech-of-day | day ceiling | reader capture |
|---|---|---|---|---|---|---|---|
| 1 | 20211020 | RV1 | +3802.50 | +3802.50 | +3802.50 | 9886.25 | 0.385 |
| 2 | 20211021 | RV1 | +1980.00 | +1980.00 | +4548.75 | 11511.25 | 0.172 |
| 3 | 20211022 | RV1 | -2642.50 | -2642.50 | +1720.00 | 10573.75 | -0.250 |
| 4 | 20211025 | RV1 | +588.75 | +588.75 | +841.25 | 7623.75 | 0.077 |
| 5 | 20211026 | RV1 | -1290.00 | -1290.00 | +4128.75 | 7792.50 | -0.166 |
| 6 | 20211027 | RV2 | +143.75 | -818.75 | +1372.50 | 7573.75 | 0.019 |
| 7 | 20211028 | RV2 | -128.75 | +403.75 | +403.75 | 5430.00 | -0.024 |
| 8 | 20211029 | RV2 | -1190.00 | -1190.00 | +4070.00 | 9548.75 | -0.125 |
| 9 | 20211101 | RV2 | -730.00 | +627.50 | +1747.50 | 6448.75 | -0.113 |
| 10 | 20211102 | RV2 | -2807.50 | -2807.50 | +1365.00 | 7030.00 | -0.399 |
| 11 | 20211103 | RV2 | +2028.75 | +2028.75 | +2028.75 | 8547.50 | 0.237 |
| 12 | 20211104 | RV2 | -493.75 | -493.75 | +2090.00 | 7630.00 | -0.065 |

Trend over the 12-day sequence (Spearman, day index vs reader replay $): rho = -0.287, p = 0.366. Days positive 5 of 12; RV1 (days 1-5) $+2438.75 over 5 days, RV2 (days 6-12) $-3177.50 over 7 days.

## 6. D-077 / CC-M2-22 COMPLIANCE — READ FROM THE CENSUS FLAGS

**THE DEPLOYABLE READINGS ARE REFUSED FOR THIS BLOCK (R127) — see §0 for the computed coverage.** The compliance tables below are NOT published: with the dated-release universe this thin, the label would mean something other than prop-firm compliance. The SCIENCE reading and the flag census stand.

## 7. ANCILLARIES

| cut | level | takes | mean cert $ | sum cert $ | winners | win rate | seats | seat value $ |
|---|---|---|---|---|---|---|---|---|
| class | NEWS-WINDOW | 135 | -203.06 | -27412.50 | 5 | 0.037 | 19 | -5270.00 |
| class | OPEN-DYNAMICS | 69 | -43.77 | -3020.00 | 1 | 0.014 | 30 | +4531.25 |
| release_confound | NEWS-WINDOW|near_dated_release | 29 | -237.11 | -6876.25 | 1 | 0.034 | 4 | -201.25 |
| release_confound | NEWS-WINDOW|clear_of_release | 106 | -193.74 | -20536.25 | 4 | 0.038 | 15 | -5068.75 |
| release_confound | OPEN-DYNAMICS|near_dated_release | 13 | +183.94 | +2391.25 | 0 | 0.000 | 8 | +2503.75 |
| release_confound | OPEN-DYNAMICS|clear_of_release | 56 | -96.63 | -5411.25 | 1 | 0.018 | 22 | +2027.50 |
| subperiod | RV1 | 96 | -178.18 | -17105.00 | 2 | 0.021 | 21 | +2438.75 |
| subperiod | RV2 | 108 | -123.40 | -13327.50 | 4 | 0.037 | 28 | -3177.50 |
| grade_TAKE | A | 178 | -179.16 | -31890.00 | 5 | 0.028 | 35 | -2793.75 |
| grade_SKIP | A | 8529 | -81.76 | -697351.25 | 397 | 0.047 | 0 | +0.00 |
| grade_TAKE | B | 26 | +56.06 | +1457.50 | 1 | 0.038 | 14 | +2055.00 |
| grade_SKIP | B | 3685 | -45.65 | -168218.75 | 98 | 0.027 | 0 | +0.00 |
| asset | SI | 119 | -63.82 | -7595.00 | 4 | 0.034 | 24 | +3505.00 |
| asset | HG | 79 | -288.23 | -22770.00 | 2 | 0.025 | 21 | -3973.75 |
| asset | NKD | 6 | -11.25 | -67.50 | 0 | 0.000 | 4 | -270.00 |

Row-grain GEE (TAKE vs SKIP, clustered on session):

| reading | outcome | link | beta | se_CR1 | z | p | n | clusters |
|---|---|---|---|---|---|---|---|---|
| SCIENCE | cert_close_usd | identity | -78.3119 | 82.5282 | -0.949 | 0.3427 | 12418 | 36 |
| SCIENCE | winner_close | logit | -0.3321 | 0.5429 | -0.612 | 0.5407 | 12418 | 36 |

## 8. D-076 NARROWNESS CAVEAT (echoed verbatim in substance)

> D-076.3: *the E1 blind round stands as sealed, with its consecutive-October narrowness a NAMED CAVEAT on the gate verdict (pass = provisional until E2 confirms on a stratified mix; fail = diagnosed for regime-narrowness before iterations burn fresh days).*

The twelve days are consecutive trading days 2021-10-20..2021-11-04, one asset era, one month-and-a-half of tape, one FOMC. Whatever these bars read, they read on that mix.

## 10. DEFECTS + LIMITS RAISED BY THIS PASS

* **D32 — BAR (b) IS NOT COMPUTABLE AS REGISTERED.** CC-M2-6 defines lift as `mean(cert of TAKEs)/mean(cert of SKIPs)` at the phase-close reading, and `panel_score` refuses a ratio against a non-positive denominator (panel_score.py:444 — "a ratio against a non-positive denominator is not a lift"). On the blind universe mean SKIP is $-70.87, so the registered ratio is undefined for EVERY arm. The bar is reported as its two components (mean TAKE $-149.18 vs mean SKIP $-70.87, difference $-78.31), the raw signed ratio, and the peak-exit companion lift 0.830. This is a pre-registration defect, not a scoring choice — the same hole existed on the study block (mean SKIP -$18.76) and was not noticed because the study lift was quoted on positive-mean subsets.
* **D31 CLOSED by CC-M2-22.1/22.4, and its consequence measured.** The family label is a fixed-clock name (US-CLOCK in display, NEWS-WINDOW on the wire — R102), not a release fact; compliance comes from the census flags. On the round's own calls the two rules differ by an order of magnitude: **0 of 204 reader TAKEs carry an ENTRY flag**, against 135 of 204 that carry the family name. The name-based reading is retained only as the NAME-STRUCK-SUPERSEDED universe, for reconciling the sealed summary. (the DEPLOYABLE universes themselves are REFUSED for this block per R127, so no deployable count is quoted here.)
* **D34 (new, to the compliance lane): `NEWS_DISTANCE.tsv` cannot express the hold-crossing case beyond its own reach.** Its population is candidates within ±15min of a dated release, but `held_into_window` is a property of a hold that can begin HOURS earlier — on this block every such row (a seat entered in the morning and held through the 18:00 UTC FOMC) is outside the file. This pass closes the gap with the census's own definition and proves 0 disagreement on the rows the file does carry, but the file alone would under-count held-into exposure. Suggest the census emit held-into rows regardless of entry distance.
* **D33 — the scoring replay re-seats after a wall stop-out.** The reader held one position per (asset,phase) cell for the whole phase; the replay frees the seat at the certificate's exit second, which for a walled candidate is the wall. That gives the reader 9 seats it never claimed. Named because it moves the headline: the law is more generous than the reader's declared posture.
* ARM REGISTER (computed, `E1_BLIND_ARM_REGISTER.tsv`): 9 arm(s) ran AS COMMITTED through their own CLIs on all twelve days (`DECLARED`, `E1D1`, `E1D2`, `E1D3`, `E1D4`, `E1D5`, `E1D6`, `E1D7`, `E1D8`); 1 arm(s) REFUSED (`BASE_EARLIEST_CV*`). A refused arm is named, never dropped.
* R130 VERDICT RECONCILIATION: 6 of 11 numbers/tokens quoted by `provenance/port_m2/E1_TEACHER_GATE_VERDICT.md` do NOT resolve against the tables this pass wrote (`E1_VERDICT_RECONCILIATION.tsv`). This lane does not edit that document; it makes the discrepancy mechanical.

---
Outputs: `artifacts/cache/port/m2/blind_score/` — E1_BLIND_ARM_REGISTER.tsv, E1_BLIND_GIT_ORDERING.tsv, E1_BLIND_MUTANT.tsv, E1_BLIND_NEWS_DISTANCE.tsv, E1_BLIND_SCORE_ANCILLARY.tsv, E1_BLIND_SCORE_ARMS.tsv, E1_BLIND_SCORE_BARS.tsv, E1_BLIND_SCORE_GEE.tsv, E1_BLIND_SCORE_MARGINS.tsv, E1_BLIND_SCORE_PERDAY.tsv, E1_BLIND_SCORE_REPORT.md, E1_VERDICT_RECONCILIATION.tsv, e1blind_score.receipt.json. Pins re-checked at end: HELD.

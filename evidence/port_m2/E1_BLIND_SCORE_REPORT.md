# E1 BLIND ROUND — SCORING PASS (CC-M2-6 TEACHER-GATE INPUTS)

Computed by the scoring lane, 12 sealed days, 12418 calls. **This file reports arithmetic; the gate VERDICT is the orchestrator's (CC-M2-6 / D-075).**

## 0. SEAL + GIT ORDERING (verified by this pass)

* Scored ledger `provenance/port_m2/E1_BLIND_LEDGER.tsv`, git blob `cc3dbea886c5`, sha256 `0d0fed00dc901a63` — **identical to the blob committed at HEAD**; the on-disk bytes are the sealed bytes.
* The ledger's last modifying commit is `752918d` (day-12 seal). Every one of the twelve seal commits ADDED rows and DELETED none (git numstat, day1 948 -> day12 12,418), so no earlier day's call was ever revised.
* **No outcome artefact exists anywhere in `99ae1d5..HEAD`.** Every commit from the prospective registration to HEAD was audited for outcome-bearing paths (blind_score / unblind / S14 / PANEL_ / truth): 21 commits, 0 carrying such a path. The round-seal commit `89382dd` and the D-077 annotation `5afab84` touched no call. **THE SEAL COMMITS PRECEDE ANY OUTCOME ACCESS: the unblinding is this pass, and it is the first event in the repository's history to read a certificate for these twelve days.**
* Frozen-arm identity check: `e1_blind_declared_policy.py` re-run as committed reproduces the sealed `DECLARED` column of `E1BLIND_D*_ARMS.tsv` exactly.

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
| reader's own 40 cell-seats | 40 | -287.50 |
| CC-M2-10.3 greedy replay (THE LAW, CC-M2-21.4) | 49 | -738.75 |
| DP seat-split (companion diagnostic) | 31 | +23651.25 |
| peak-exit companion reading (CC-M1-8) | 49 | +42980.00 |

Universe sizes by reading: SCIENCE 12418, DEPLOYABLE-DATED 11962, DEPLOYABLE-STRICT 11583.

## 2. THE THREE CC-M2-6 BARS

| reading | bar | statistic | bar value | statistic − bar |
|---|---|---|---|---|
| SCIENCE | a_margin_over_best_mechanical | $-11815.00 (sum, BASE_EARLIEST_CV516) | 0.000 | -11815.0000 |
| SCIENCE | b_lift_close | — | 1.300 | — |
| SCIENCE | b_lift_close_raw_ratio | 2.105 | 1.300 | +0.8051 |
| SCIENCE | b_mean_take_close_usd | -149.179 | — | — |
| SCIENCE | b_mean_skip_close_usd | -70.867 | — | — |
| SCIENCE | b_lift_peak_companion | 0.830 | 1.300 | -0.4695 |
| SCIENCE | c_replay_capture | -0.007 | 0.250 | -0.2574 |
| SCIENCE | c_replay_capture_vs_full_ceiling | -0.007 | 0.250 | -0.2574 |
| DEPLOYABLE-DATED | a_margin_over_best_mechanical | $-11451.25 (sum, E1D8) | 0.000 | -11451.2500 |
| DEPLOYABLE-DATED | b_lift_close | — | 1.300 | — |
| DEPLOYABLE-DATED | b_lift_close_raw_ratio | 2.047 | 1.300 | +0.7474 |
| DEPLOYABLE-DATED | b_mean_take_close_usd | -174.869 | — | — |
| DEPLOYABLE-DATED | b_mean_skip_close_usd | -85.411 | — | — |
| DEPLOYABLE-DATED | b_lift_peak_companion | 0.820 | 1.300 | -0.4798 |
| DEPLOYABLE-DATED | c_replay_capture | -0.048 | 0.250 | -0.2976 |
| DEPLOYABLE-DATED | c_replay_capture_vs_full_ceiling | -0.046 | 0.250 | -0.2965 |
| DEPLOYABLE-STRICT | a_margin_over_best_mechanical | $-4670.00 (sum, E1D8) | 0.000 | -4670.0000 |
| DEPLOYABLE-STRICT | b_lift_close | — | 1.300 | — |
| DEPLOYABLE-STRICT | b_lift_close_raw_ratio | 1.163 | 1.300 | -0.1369 |
| DEPLOYABLE-STRICT | b_mean_take_close_usd | -97.537 | — | — |
| DEPLOYABLE-STRICT | b_mean_skip_close_usd | -83.858 | — | — |
| DEPLOYABLE-STRICT | b_lift_peak_companion | 0.919 | 1.300 | -0.3813 |
| DEPLOYABLE-STRICT | c_replay_capture | 0.022 | 0.250 | -0.2278 |
| DEPLOYABLE-STRICT | c_replay_capture_vs_full_ceiling | 0.022 | 0.250 | -0.2284 |

Bar (a) inference (day-paired, GEE independence + Liang-Zeger sandwich, Cameron-Miller CR1, 12 day clusters):

| reading | best mechanical arm | sum margin | mean/day | se_CR1 | z | p (normal) | p (t,df11) | days + / − | p sign |
|---|---|---|---|---|---|---|---|---|---|
| SCIENCE | BASE_EARLIEST_CV516 | $-11815.00 | $-984.58 | 593.38 | -1.659 | 0.0971 | 0.1253 | 4 / 8 | 0.3877 |
| DEPLOYABLE-DATED | E1D8 | $-11451.25 | $-954.27 | 662.27 | -1.441 | 0.1496 | 0.1775 | 3 / 9 | 0.1460 |
| DEPLOYABLE-STRICT | E1D8 | $-4670.00 | $-389.17 | 653.72 | -0.595 | 0.5516 | 0.5637 | 4 / 7 | 0.5488 |

## 3. ARMS

### SCIENCE (universe 12418)

| arm | mech? | takes | mean TAKE $ | mean SKIP $ | lift close | lift peak | winners | precision | replay $ | capture |
|---|---|---|---|---|---|---|---|---|---|---|
| BASE_EARLIEST_CV516 | y | 229 | -36.91 | -72.82 | — | 0.959 | 15 | 0.066 | +11076.25 | 0.111 |
| BASE_EARLIEST_CV639 | y | 222 | -37.74 | -72.78 | — | 0.956 | 15 | 0.068 | +10018.75 | 0.101 |
| E1D8 | y | 247 | -73.09 | -72.13 | — | 1.117 | 34 | 0.138 | +7143.75 | 0.072 |
| E1D6 | y | 1033 | +69.17 | -84.98 | — | 1.275 | 96 | 0.093 | +6106.25 | 0.061 |
| DECLARED |  | 216 | -114.90 | -71.40 | — | 0.856 | 12 | 0.056 | +188.75 | 0.002 |
| READER |  | 204 | -149.18 | -70.87 | — | 0.830 | 6 | 0.029 | -738.75 | -0.007 |
| E1D1 | y | 6 | -122.71 | -72.13 | — | 0.855 | 0 | 0.000 | -881.25 | -0.009 |
| E1D4 | y | 334 | -106.68 | -71.20 | — | 0.833 | 21 | 0.063 | -1412.50 | -0.014 |
| BASE_EARLIEST_CV650 | y | 118 | -83.39 | -72.05 | — | 0.885 | 8 | 0.068 | -1645.00 | -0.017 |
| E1D3 | y | 21 | -142.80 | -72.03 | — | 0.789 | 0 | 0.000 | -2523.75 | -0.025 |
| E1D5 | y | 769 | -113.34 | -69.43 | — | 0.868 | 27 | 0.035 | -5563.75 | -0.056 |
| E1D2 | y | 54 | -140.88 | -71.85 | — | 0.887 | 1 | 0.019 | -5963.75 | -0.060 |
| BASE_EARLIEST_CV500 | y | 5934 | -60.48 | -82.83 | — | 1.019 | 194 | 0.033 | -8600.00 | -0.086 |
| E1D7 | y | 857 | -217.03 | -61.41 | — | 0.709 | 21 | 0.025 | -10415.00 | -0.105 |
| BASE_EARLIEST_CV0 | y | 5980 | -59.52 | -83.89 | — | 1.020 | 197 | 0.033 | -11711.25 | -0.118 |

### DEPLOYABLE-DATED (universe 11962)

| arm | mech? | takes | mean TAKE $ | mean SKIP $ | lift close | lift peak | winners | precision | replay $ | capture |
|---|---|---|---|---|---|---|---|---|---|---|
| E1D8 | y | 241 | -82.52 | -87.00 | — | 1.085 | 34 | 0.141 | +6823.75 | 0.070 |
| BASE_EARLIEST_CV516 | y | 215 | -60.93 | -87.39 | — | 0.937 | 12 | 0.056 | +5680.00 | 0.058 |
| E1D6 | y | 1014 | +62.05 | -100.71 | — | 1.271 | 93 | 0.092 | +5202.50 | 0.053 |
| BASE_EARLIEST_CV639 | y | 208 | -62.63 | -87.34 | — | 0.932 | 12 | 0.058 | +4622.50 | 0.048 |
| E1D1 | y | 6 | -122.71 | -86.90 | — | 0.878 | 0 | 0.000 | -881.25 | -0.009 |
| E1D3 | y | 21 | -142.80 | -86.82 | — | 0.811 | 0 | 0.000 | -2523.75 | -0.026 |
| E1D4 | y | 330 | -132.27 | -85.63 | — | 0.830 | 20 | 0.061 | -3557.50 | -0.037 |
| DECLARED |  | 213 | -138.66 | -85.98 | — | 0.848 | 12 | 0.056 | -3700.00 | -0.038 |
| BASE_EARLIEST_CV650 | y | 107 | -113.82 | -86.67 | — | 0.821 | 6 | 0.056 | -4146.25 | -0.043 |
| READER |  | 201 | -174.87 | -85.41 | — | 0.820 | 6 | 0.030 | -4627.50 | -0.048 |
| E1D2 | y | 54 | -140.88 | -86.67 | — | 0.912 | 1 | 0.019 | -5963.75 | -0.061 |
| E1D5 | y | 768 | -115.24 | -84.97 | — | 0.890 | 27 | 0.035 | -6908.75 | -0.071 |
| BASE_EARLIEST_CV500 | y | 5796 | -70.42 | -102.42 | — | 1.032 | 157 | 0.027 | -11600.00 | -0.119 |
| E1D7 | y | 827 | -295.98 | -71.39 | — | 0.647 | 10 | 0.012 | -12510.00 | -0.129 |
| BASE_EARLIEST_CV0 | y | 5841 | -69.41 | -103.62 | — | 1.033 | 160 | 0.027 | -16941.25 | -0.174 |

### DEPLOYABLE-STRICT (universe 11583)

| arm | mech? | takes | mean TAKE $ | mean SKIP $ | lift close | lift peak | winners | precision | replay $ | capture |
|---|---|---|---|---|---|---|---|---|---|---|
| E1D8 | y | 230 | -57.74 | -84.47 | — | 1.116 | 34 | 0.148 | +6823.75 | 0.070 |
| E1D6 | y | 952 | +62.36 | -97.04 | — | 1.276 | 90 | 0.095 | +4755.00 | 0.049 |
| DECLARED |  | 79 | -11.65 | -84.43 | — | 0.979 | 7 | 0.089 | +3521.25 | 0.036 |
| BASE_EARLIEST_CV516 | y | 108 | -8.53 | -84.65 | — | 1.047 | 6 | 0.056 | +2546.25 | 0.026 |
| READER |  | 67 | -97.54 | -83.86 | — | 0.919 | 1 | 0.015 | +2153.75 | 0.022 |
| BASE_EARLIEST_CV639 | y | 101 | -8.40 | -84.60 | — | 1.044 | 6 | 0.059 | +1618.75 | 0.017 |
| BASE_EARLIEST_CV650 | y | 0 | — | -83.94 | — | — | 0 | — | +0.00 | 0.000 |
| E1D1 | y | 6 | -122.71 | -83.92 | — | 0.873 | 0 | 0.000 | -881.25 | -0.009 |
| E1D3 | y | 21 | -142.80 | -83.83 | — | 0.806 | 0 | 0.000 | -2523.75 | -0.026 |
| E1D4 | y | 301 | -151.66 | -82.13 | — | 0.831 | 18 | 0.060 | -3762.50 | -0.039 |
| E1D2 | y | 49 | -160.36 | -83.61 | — | 0.893 | 1 | 0.020 | -4778.75 | -0.049 |
| E1D5 | y | 706 | -111.61 | -82.14 | — | 0.881 | 24 | 0.034 | -6890.00 | -0.071 |
| BASE_EARLIEST_CV500 | y | 5689 | -69.60 | -97.77 | — | 1.029 | 151 | 0.027 | -11720.00 | -0.121 |
| E1D7 | y | 760 | -275.82 | -70.46 | — | 0.662 | 8 | 0.011 | -12735.00 | -0.131 |
| BASE_EARLIEST_CV0 | y | 5734 | -68.58 | -98.99 | — | 1.030 | 154 | 0.027 | -17061.25 | -0.176 |

## 4. READER vs THE FROZEN DECLARED ARM (CC-M2-20.2's two arms)

The two arms differ on **12 of 12418 rows** (the reader's single RV2 evolution); the sealed summary claims 12. Every differing row is a NKD OPEN-DYNAMICS row.

| reading | reader replay | declared replay | day-paired margin | se_CR1 | z | p (t,df11) | days + / − | reader mean TAKE $ | declared mean TAKE $ | reader precision | declared precision | reader capture | declared capture |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SCIENCE | -738.75 | +188.75 | $-927.50 | 150.28 | -0.514 | 0.6172 | 1 / 2 | -149.18 | -114.90 | 0.0294 | 0.0556 | -0.007 | 0.002 |
| DEPLOYABLE-DATED | -4627.50 | -3700.00 | $-927.50 | 150.28 | -0.514 | 0.6172 | 1 / 2 | -174.87 | -138.66 | 0.0299 | 0.0563 | -0.048 | -0.038 |
| DEPLOYABLE-STRICT | +2153.75 | +3521.25 | $-1367.50 | 121.72 | -0.936 | 0.3692 | 1 / 2 | -97.54 | -11.65 | 0.0149 | 0.0886 | 0.022 | 0.036 |

## 5. PER-DAY SEQUENCE (SCIENCE reading, replay $ at phase close)

| day | date | RV | reader | declared | best-mech-of-day | day ceiling | reader capture |
|---|---|---|---|---|---|---|---|
| 1 | 20211020 | RV1 | +3802.50 | +3802.50 | +3710.00 | 9886.25 | 0.385 |
| 2 | 20211021 | RV1 | +1980.00 | +1980.00 | +5890.00 | 11511.25 | 0.172 |
| 3 | 20211022 | RV1 | -2642.50 | -2642.50 | +1720.00 | 10573.75 | -0.250 |
| 4 | 20211025 | RV1 | +588.75 | +588.75 | +1490.00 | 7623.75 | 0.077 |
| 5 | 20211026 | RV1 | -1290.00 | -1290.00 | +4128.75 | 7792.50 | -0.166 |
| 6 | 20211027 | RV2 | +143.75 | -818.75 | +1372.50 | 7573.75 | 0.019 |
| 7 | 20211028 | RV2 | -128.75 | +403.75 | +591.25 | 5430.00 | -0.024 |
| 8 | 20211029 | RV2 | -1190.00 | -1190.00 | +4290.00 | 9548.75 | -0.125 |
| 9 | 20211101 | RV2 | -730.00 | +627.50 | +1797.50 | 6448.75 | -0.113 |
| 10 | 20211102 | RV2 | -2807.50 | -2807.50 | +2388.75 | 7030.00 | -0.399 |
| 11 | 20211103 | RV2 | +2028.75 | +2028.75 | +2233.75 | 8547.50 | 0.237 |
| 12 | 20211104 | RV2 | -493.75 | -493.75 | +2090.00 | 7630.00 | -0.065 |

Trend over the 12-day sequence (Spearman, day index vs reader replay $): rho = -0.287, p = 0.366. Days positive 5 of 12; RV1 (days 1-5) $+2438.75 over 5 days, RV2 (days 6-12) $-3177.50 over 7 days.

## 6. D-077 READINGS — WHAT THE RULE ACTUALLY STRIKES

* `m2/news_compliance/NEWS_DISTANCE.tsv` **has not landed** (the census lane is unrun); distances are computed here from `pattern_lib.release_calendar()` — the DATED BLS+FOMC calendar, D-057 SCHEDULE_EXEMPT.
* Over 2021-10-20..2021-11-04 that calendar contains **exactly one** dated high-impact release: the FOMC statement, 2021-11-03 18:00 UTC (day 11). Employment Situation 2021-11-05 and CPI 2021-11-10 fall after the block.
* Candidates struck by the literal rule: 162 by entry-in-window, 456 by hold-crossing; reader TAKEs struck 3 of 204; reader replay seats struck 2 of 49.
* **This is defect D31 in the reader's own summary, quantified:** the NEWS-WINDOW family is cut against the FIXED 08:30 / 10:00 ET wall-clock GENERATION anchors (`engine/port_m1/family_discovery.py:104` `NEWS_SLOTS`, consumed by `engine/port_m1/b10_generation_v3.py:143 news_release_offsets`), not against the dated BLS/FOMC calendar the prop rule names. The literal dated rule therefore strikes almost nothing here, which is why DEPLOYABLE-STRICT — the family struck as D-077-UPDATE.2 orders — is carried as the second deployable reading.

### D-077.2 — news-window takes by MINUTES SINCE the generation anchor

| minutes since 08:30/10:00/14:00 ET slot | takes | mean cert $ | winners | replay seats |
|---|---|---|---|---|
| [0,1) | 24 | -187.81 | 0 | 4 |
| [1,2) | 11 | -437.39 | 0 | 5 |
| [2,3) | 18 | +162.01 | 3 | 4 |
| [3,5) | 25 | -351.00 | 1 | 4 |
| [5,8) | 41 | -166.43 | 1 | 2 |
| [8,10) | 14 | -253.66 | 0 | 0 |
| [10,15) | 2 | -930.00 | 0 | 0 |

Of the 135 NEWS-WINDOW takes, 133 are inside the first 10 minutes after a generation anchor — the window D-077-UPDATE forbids outright. The OPEN-DYNAMICS takes' slot ages are not a release fact (their anchors are phase opens), and none of the round's OPEN-DYNAMICS seats sits inside a DATED release window.

### 26-of-40 reconciliation

The summary's 40 seats are the reader's OWN cell-seats; the scoring law's replay seats 49 (D33 below). Both bases are reconciled:

| quantity | summary claim | recomputed (reader's own 40) | recomputed (CC-M2-10.3 replay) |
|---|---|---|---|
| TAKEs NEWS-WINDOW / OPEN-DYNAMICS | 135 / 69 | 135 / 69 | 135 / 69 |
| seats | 40 | 40 | 49 |
| seats NEWS-WINDOW / OPEN-DYNAMICS | 14 / 26 | 14 / 26 | 19 / 30 |
| deployable seats (family struck, D-077-UPDATE.2) | 26 | 26 | 29 |
| deployable seats (literal dated ±10min rule) | — | 39 | 47 |

**The summary's 26-of-40 is confirmed exactly on its own basis.**

## 7. ANCILLARIES

| cut | level | takes | mean cert $ | sum cert $ | winners | win rate | seats | seat value $ |
|---|---|---|---|---|---|---|---|---|
| class | NEWS-WINDOW | 135 | -203.06 | -27412.50 | 5 | 0.037 | 19 | -5270.00 |
| class | OPEN-DYNAMICS | 69 | -43.77 | -3020.00 | 1 | 0.014 | 30 | +4531.25 |
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
| DEPLOYABLE-DATED | cert_close_usd | identity | -89.4585 | 84.1655 | -1.063 | 0.2878 | 11962 | 36 |
| DEPLOYABLE-DATED | winner_close | logit | -0.1399 | 0.5417 | -0.258 | 0.7962 | 11962 | 36 |
| DEPLOYABLE-STRICT | cert_close_usd | identity | -13.6791 | 115.5216 | -0.118 | 0.9057 | 11583 | 36 |
| DEPLOYABLE-STRICT | winner_close | logit | -0.8414 | 1.0455 | -0.805 | 0.4209 | 11583 | 36 |

## 8. D-076 NARROWNESS CAVEAT (echoed verbatim in substance)

> D-076.3: *the E1 blind round stands as sealed, with its consecutive-October narrowness a NAMED CAVEAT on the gate verdict (pass = provisional until E2 confirms on a stratified mix; fail = diagnosed for regime-narrowness before iterations burn fresh days).*

The twelve days are consecutive trading days 2021-10-20..2021-11-04, one asset era, one month-and-a-half of tape, one FOMC. Whatever these bars read, they read on that mix.

## 9. RED-FIRST MUTANT

| check | expected | observed | verdict |
|---|---|---|---|
| ledger blob hash refuses a post-seal flip | REFUSAL | SealRefusal raised (mutant blob 86f7c680496a != sealed cc3dbea886c5) | PASS |
| flipping HG-20211020-046895-L TAKE->SKIP moves the score | score changes | takes 204->203, replay $-738.75->$-4756.25, mean TAKE $-149.18->$-160.54 | PASS |
| sealed ledger blob == committed HEAD blob | cc3dbea886c53f212045372b2c351eaad0d4a2dc | cc3dbea886c53f212045372b2c351eaad0d4a2dc | PASS |

## 10. DEFECTS + LIMITS RAISED BY THIS PASS

* **D32 — BAR (b) IS NOT COMPUTABLE AS REGISTERED.** CC-M2-6 defines lift as `mean(cert of TAKEs)/mean(cert of SKIPs)` at the phase-close reading, and `panel_score` refuses a ratio against a non-positive denominator (panel_score.py:444 — "a ratio against a non-positive denominator is not a lift"). On the blind universe mean SKIP is $-70.87, so the registered ratio is undefined for EVERY arm. The bar is reported as its two components (mean TAKE $-149.18 vs mean SKIP $-70.87, difference $-78.31), the raw signed ratio, and the peak-exit companion lift 0.830. This is a pre-registration defect, not a scoring choice — the same hole existed on the study block (mean SKIP -$18.76) and was not noticed because the study lift was quoted on positive-mean subsets.
* **D31 quantified (the reader's own defect).** The dated BLS+FOMC calendar the prop rule speaks about contains ONE release inside the block; the NEWS-WINDOW family is cut against the fixed 08:30/10:00 ET GENERATION anchors. A literal [-10,+10] dated-calendar veto therefore strikes 3 of 204 reader TAKEs, while the family D-077-UPDATE.2 strikes for deployment is 135 of 204. Both readings are carried; they are not interchangeable.
* **`m2/news_compliance/NEWS_DISTANCE.tsv` does not exist** — the D-077 census lane (`engine/port_m2/news_census.py`) is written but unrun, so this pass computed its own distances from `pattern_lib.release_calendar()`. When the census lands, the DEPLOYABLE readings should be recomputed against it.
* **D33 — the scoring replay re-seats after a wall stop-out.** The reader held one position per (asset,phase) cell for the whole phase; the replay frees the seat at the certificate's exit second, which for a walled candidate is the wall. That gives the reader 9 seats it never claimed. Named because it moves the headline: the law is more generous than the reader's declared posture.
* All eight frozen predecessor policies e1d1..e1d8 ran AS COMMITTED through their own CLIs on all twelve days (no unrunnable arm), as did `e1_blind_declared_policy.py`.

---
Outputs: `artifacts/cache/port/m2/blind_score/` (ARMS, PERDAY, MARGINS, BARS, NEWS_DISTANCE, ANCILLARY, GEE, GIT_ORDERING, MUTANT, receipt). Pins re-checked at end: HELD.

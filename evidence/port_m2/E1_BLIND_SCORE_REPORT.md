# E1 BLIND ROUND — SCORING PASS (CC-M2-6 TEACHER-GATE INPUTS)

Computed by the scoring lane, 12 sealed days, 12418 calls. **This file reports arithmetic; the gate VERDICT is the orchestrator's (CC-M2-6 / D-075).**

## 0. SEAL + GIT ORDERING (verified by this pass)

* Scored ledger `provenance/port_m2/E1_BLIND_LEDGER.tsv`, git blob `cc3dbea886c5`, sha256 `0d0fed00dc901a63` — **identical to the blob committed at HEAD**; the on-disk bytes are the sealed bytes.
* The ledger's last modifying commit is `752918d` (day-12 seal). Every one of the twelve seal commits ADDED rows and DELETED none (git numstat, day1 948 -> day12 12,418), so no earlier day's call was ever revised.
* **No outcome artefact exists anywhere in `99ae1d5..HEAD`.** Every commit from the prospective registration to HEAD was audited for outcome-bearing paths (blind_score / unblind / S14 / PANEL_ / truth): 28 commits, 1 carrying such a path. The round-seal commit `89382dd` and the D-077 annotation `5afab84` touched no call. **THE SEAL COMMITS PRECEDE ANY OUTCOME ACCESS: the unblinding is this pass, and it is the first event in the repository's history to read a certificate for these twelve days.**
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

Universe sizes by reading: SCIENCE 12418, DEPLOYABLE 11796, NAME-STRUCK-SUPERSEDED 11430.

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
| DEPLOYABLE | a_margin_over_best_mechanical | $-10307.50 (sum, BASE_EARLIEST_CV516) | 0.000 | -10307.5000 |
| DEPLOYABLE | b_lift_close | — | 1.300 | — |
| DEPLOYABLE | b_lift_close_raw_ratio | 2.167 | 1.300 | +0.8672 |
| DEPLOYABLE | b_mean_take_close_usd | -159.537 | — | — |
| DEPLOYABLE | b_mean_skip_close_usd | -73.615 | — | — |
| DEPLOYABLE | b_lift_peak_companion | 0.821 | 1.300 | -0.4791 |
| DEPLOYABLE | c_replay_capture | -0.028 | 0.250 | -0.2785 |
| DEPLOYABLE | c_replay_capture_vs_full_ceiling | -0.028 | 0.250 | -0.2778 |
| NAME-STRUCK-SUPERSEDED | a_margin_over_best_mechanical | $-3740.00 (sum, E1D8) | 0.000 | -3740.0000 |
| NAME-STRUCK-SUPERSEDED | b_lift_close | — | 1.300 | — |
| NAME-STRUCK-SUPERSEDED | b_lift_close_raw_ratio | 1.171 | 1.300 | -0.1293 |
| NAME-STRUCK-SUPERSEDED | b_mean_take_close_usd | -84.924 | — | — |
| NAME-STRUCK-SUPERSEDED | b_mean_skip_close_usd | -72.541 | — | — |
| NAME-STRUCK-SUPERSEDED | b_lift_peak_companion | 0.920 | 1.300 | -0.3802 |
| NAME-STRUCK-SUPERSEDED | c_replay_capture | 0.032 | 0.250 | -0.2183 |
| NAME-STRUCK-SUPERSEDED | c_replay_capture_vs_full_ceiling | 0.031 | 0.250 | -0.2190 |

Bar (a) inference (day-paired, GEE independence + Liang-Zeger sandwich, Cameron-Miller CR1, 12 day clusters):

| reading | best mechanical arm | sum margin | mean/day | se_CR1 | z | p (normal) | p (t,df11) | days + / − | p sign |
|---|---|---|---|---|---|---|---|---|---|
| SCIENCE | BASE_EARLIEST_CV516 | $-11815.00 | $-984.58 | 593.38 | -1.659 | 0.0971 | 0.1253 | 4 / 8 | 0.3877 |
| DEPLOYABLE | BASE_EARLIEST_CV516 | $-10307.50 | $-858.96 | 621.03 | -1.383 | 0.1666 | 0.1941 | 5 / 7 | 0.7744 |
| NAME-STRUCK-SUPERSEDED | E1D8 | $-3740.00 | $-311.67 | 662.45 | -0.470 | 0.6380 | 0.6472 | 5 / 7 | 0.7744 |

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

### DEPLOYABLE (universe 11796)

| arm | mech? | takes | mean TAKE $ | mean SKIP $ | lift close | lift peak | winners | precision | replay $ | capture |
|---|---|---|---|---|---|---|---|---|---|---|
| BASE_EARLIEST_CV516 | y | 212 | -48.63 | -75.53 | — | 0.936 | 12 | 0.057 | +7540.00 | 0.078 |
| E1D8 | y | 241 | -82.52 | -74.89 | — | 1.072 | 34 | 0.141 | +6823.75 | 0.070 |
| BASE_EARLIEST_CV639 | y | 205 | -49.94 | -75.49 | — | 0.932 | 12 | 0.059 | +6482.50 | 0.067 |
| E1D6 | y | 1014 | +62.05 | -87.94 | — | 1.254 | 93 | 0.092 | +5202.50 | 0.053 |
| E1D4 | y | 309 | -78.06 | -74.97 | — | 0.892 | 20 | 0.065 | +162.50 | 0.002 |
| E1D1 | y | 6 | -122.71 | -75.03 | — | 0.867 | 0 | 0.000 | -881.25 | -0.009 |
| DECLARED |  | 209 | -123.51 | -74.18 | — | 0.849 | 12 | 0.057 | -1840.00 | -0.019 |
| BASE_EARLIEST_CV650 | y | 105 | -98.27 | -74.84 | — | 0.824 | 6 | 0.057 | -2286.25 | -0.024 |
| E1D3 | y | 21 | -142.80 | -74.93 | — | 0.801 | 0 | 0.000 | -2523.75 | -0.026 |
| READER |  | 197 | -159.54 | -73.61 | — | 0.821 | 6 | 0.030 | -2767.50 | -0.028 |
| E1D2 | y | 52 | -110.53 | -74.89 | — | 0.928 | 1 | 0.019 | -4103.75 | -0.042 |
| E1D5 | y | 730 | -72.83 | -75.20 | — | 0.914 | 27 | 0.037 | -4118.75 | -0.042 |
| BASE_EARLIEST_CV500 | y | 5728 | -60.21 | -89.05 | — | 1.028 | 157 | 0.027 | -5090.00 | -0.052 |
| E1D7 | y | 762 | -241.89 | -63.53 | — | 0.681 | 10 | 0.013 | -6930.00 | -0.071 |
| BASE_EARLIEST_CV0 | y | 5772 | -59.12 | -90.31 | — | 1.030 | 160 | 0.028 | -10431.25 | -0.107 |

### NAME-STRUCK-SUPERSEDED (universe 11430)

| arm | mech? | takes | mean TAKE $ | mean SKIP $ | lift close | lift peak | winners | precision | replay $ | capture |
|---|---|---|---|---|---|---|---|---|---|---|
| E1D8 | y | 230 | -57.74 | -72.92 | — | 1.102 | 34 | 0.148 | +6823.75 | 0.070 |
| E1D6 | y | 952 | +62.36 | -84.88 | — | 1.259 | 90 | 0.095 | +4755.00 | 0.049 |
| DECLARED |  | 78 | +0.13 | -73.11 | — | 0.978 | 7 | 0.090 | +4451.25 | 0.046 |
| BASE_EARLIEST_CV516 | y | 107 | +0.08 | -73.30 | — | 1.043 | 6 | 0.056 | +3476.25 | 0.036 |
| READER |  | 66 | -84.92 | -72.54 | — | 0.920 | 1 | 0.015 | +3083.75 | 0.032 |
| BASE_EARLIEST_CV639 | y | 100 | +0.81 | -73.26 | — | 1.041 | 6 | 0.060 | +2548.75 | 0.026 |
| BASE_EARLIEST_CV650 | y | 0 | — | -72.61 | — | — | 0 | — | +0.00 | 0.000 |
| E1D4 | y | 280 | -93.28 | -72.09 | — | 0.901 | 18 | 0.064 | -42.50 | -0.000 |
| E1D1 | y | 6 | -122.71 | -72.59 | — | 0.863 | 0 | 0.000 | -881.25 | -0.009 |
| E1D3 | y | 21 | -142.80 | -72.48 | — | 0.797 | 0 | 0.000 | -2523.75 | -0.026 |
| E1D2 | y | 47 | -127.61 | -72.39 | — | 0.912 | 1 | 0.021 | -2918.75 | -0.030 |
| E1D5 | y | 671 | -68.93 | -72.84 | — | 0.905 | 24 | 0.036 | -4100.00 | -0.042 |
| BASE_EARLIEST_CV500 | y | 5623 | -59.50 | -85.31 | — | 1.026 | 151 | 0.027 | -5210.00 | -0.054 |
| E1D7 | y | 698 | -217.71 | -63.17 | — | 0.700 | 8 | 0.011 | -7155.00 | -0.074 |
| BASE_EARLIEST_CV0 | y | 5667 | -58.40 | -86.59 | — | 1.027 | 154 | 0.027 | -10551.25 | -0.109 |

## 4. READER vs THE FROZEN DECLARED ARM (CC-M2-20.2's two arms)

The two arms differ on **12 of 12418 rows** (the reader's single RV2 evolution); the sealed summary claims 12. Every differing row is a NKD OPEN-DYNAMICS row.

| reading | reader replay | declared replay | day-paired margin | se_CR1 | z | p (t,df11) | days + / − | reader mean TAKE $ | declared mean TAKE $ | reader precision | declared precision | reader capture | declared capture |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SCIENCE | -738.75 | +188.75 | $-927.50 | 150.28 | -0.514 | 0.6172 | 1 / 2 | -149.18 | -114.90 | 0.0294 | 0.0556 | -0.007 | 0.002 |
| DEPLOYABLE | -2767.50 | -1840.00 | $-927.50 | 150.28 | -0.514 | 0.6172 | 1 / 2 | -159.54 | -123.51 | 0.0305 | 0.0574 | -0.028 | -0.019 |
| NAME-STRUCK-SUPERSEDED | +3083.75 | +4451.25 | $-1367.50 | 121.72 | -0.936 | 0.3692 | 1 / 2 | -84.92 | +0.13 | 0.0152 | 0.0897 | 0.032 | 0.046 |

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

## 6. D-077 / CC-M2-22 COMPLIANCE — READ FROM THE CENSUS FLAGS

**CC-M2-22.4 is binding here and supersedes the name-based reading.** Compliance is taken from the FLAGS in `artifacts/cache/port/m2/news_compliance/NEWS_DISTANCE.tsv` (`inside_default_window`, `pre_release_window`, `held_into_window`); nothing is inferred from a blank `minutes_since_release` (D-N3 — a blank means a release is AHEAD of the row).

* The census file carries **189 of the round's 12418 candidates** (its reach is ±15min of a dated release); **all 189 are on day 11, 2021-11-03** — the block's only dated high-impact release (FOMC statement 18:00 UTC; the CPI-named rows are pre-window rows whose LAST release was October CPI and whose NEXT is that FOMC).
* Flag agreement RED CHECK: this pass's own recomputation of `inside_default_window` and `held_into_window` matches the census file on **every one of the 189 rows** the file carries (0 disagreements), so the hold-crossing clause applied to rows OUTSIDE the file's ±15min reach is the census's own definition (news_census.py:400-408), not a substitute. Without that clause a seat entered hours before the FOMC and held through it would be scored compliant.
* Flag census over the whole round: 162 candidates inside_default_window, 622 whose phase-close hold crosses a restricted window.

### THE FLAG-BASED EXCLUSION (the number that counts)

| basis | takes excluded | seats excluded (reader's own 40) | seats excluded (CC-M2-10.3 replay, 49) |
|---|---|---|---|
| **CC-M2-22.4 FLAGS (binding)** | **7 of 204** | **2 of 40** | **3 of 49** |
| name-based `NEWS-WINDOW` label (SUPERSEDED, D-N1) | 135 of 204 | 14 of 40 | 19 of 49 |

**D-N1 confirmed on the round's own calls.** The sealed ledger's `NEWS-WINDOW` label (CC-M2-22.1 renames it **US_CLOCK**) is a fixed-clock family name, not a release fact: of the reader's 135 US_CLOCK takes only **4 (3.0%)** carry any compliance flag. The summary's **26-of-40 was a name-based guess and is superseded** — on the flags **38 of the reader's 40 cell-seats survive** (2 excluded), and 46 of the scorer's 49 replay seats survive (3 excluded).

### Takes RE-LABELLED BY ACTUAL FLAG STATE (not by family name)

| actual proximity state | takes | mean cert $ | winners | replay seats | seat value $ |
|---|---|---|---|---|---|
| HOLD crosses a restricted window | 7 | +142.32 | 0 | 3 | +2028.75 |
| COMPLIANT (no flag) | 197 | -159.54 | 6 | 46 | -2767.50 |

Flagged share by family label — the D-N1 point in one line: NEWS-WINDOW 4 of 135 flagged, OPEN-DYNAMICS 3 of 69 flagged.

### D-077.2 — US_CLOCK takes by MINUTES SINCE the GENERATION anchor

The family's own anchor is the fixed 08:30 / 10:00 / 14:00 ET slot set (`engine/port_m1/family_discovery.py:104 NEWS_SLOTS`, consumed by `engine/port_m1/b10_generation_v3.py:143 news_release_offsets`). This is a CLOCK profile and — D-N1 — it is NOT the compliance rule.

| minutes since 08:30/10:00/14:00 ET slot | takes | mean cert $ | winners | replay seats | of which flagged |
|---|---|---|---|---|---|
| [0,1) | 24 | -187.81 | 0 | 4 | 0 |
| [1,2) | 11 | -437.39 | 0 | 5 | 1 |
| [2,3) | 18 | +162.01 | 3 | 4 | 1 |
| [3,5) | 25 | -351.00 | 1 | 4 | 1 |
| [5,8) | 41 | -166.43 | 1 | 2 | 1 |
| [8,10) | 14 | -253.66 | 0 | 0 | 0 |
| [10,15) | 2 | -930.00 | 0 | 0 | 0 |

Of the 135 US_CLOCK takes, 133 sit in the first 10 minutes after a generation SLOT, but only 4 carry a compliance flag — the slot was a DATED release on only one day of the twelve. That gap IS D-N1.

### 26-of-40 reconciliation (both numbers, as ordered)

The summary's 40 seats are the reader's OWN cell-seats; the scoring law's replay seats 49 (D33 below). Both bases, both rules:

| quantity | summary claim | reader's own 40 | CC-M2-10.3 replay (49) |
|---|---|---|---|
| TAKEs US_CLOCK / OPEN-DYNAMICS | 135 / 69 | 135 / 69 | 135 / 69 |
| seats | 40 | 40 | 49 |
| seats US_CLOCK / OPEN-DYNAMICS | 14 / 26 | 14 / 26 | 19 / 30 |
| deployable seats — PURE NAME strike (the summary's rule) | 26 | 26 | 30 |
| deployable seats — NAME strike AND flags (NAME-STRUCK-SUPERSEDED universe) | — | 25 | 28 |
| **deployable seats — CC-M2-22.4 FLAGS (binding)** | — | **38** | **46** |

**The summary's 26-of-40 reproduces exactly on its own (pure name-strike) basis — 26 of 40 — and is superseded.** Under the binding flag rule **38 of the 40 stand, 2 excluded** (3 of 49 on the replay basis): the name-based rule threw away 13 seats that carry no compliance flag at all.

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
| DEPLOYABLE | cert_close_usd | identity | -85.9221 | 85.2187 | -1.008 | 0.3133 | 11796 | 36 |
| DEPLOYABLE | winner_close | logit | -0.1336 | 0.5423 | -0.246 | 0.8054 | 11796 | 36 |
| NAME-STRUCK-SUPERSEDED | cert_close_usd | identity | -12.3837 | 117.2010 | -0.106 | 0.9159 | 11430 | 36 |
| NAME-STRUCK-SUPERSEDED | winner_close | logit | -0.8399 | 1.0455 | -0.803 | 0.4218 | 11430 | 36 |

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
* **D31 CLOSED by CC-M2-22.1/22.4, and its consequence measured.** The family label is a fixed-clock name (US_CLOCK), not a release fact; compliance now comes from the census flags. On the round's own calls the two rules differ by an order of magnitude: **7 of 204 reader TAKEs carry a flag**, against 135 of 204 that carry the family name. The name-based reading is retained only as the NAME-STRUCK-SUPERSEDED universe, for reconciling the sealed summary.
* **D34 (new, to the compliance lane): `NEWS_DISTANCE.tsv` cannot express the hold-crossing case beyond its own reach.** Its population is candidates within ±15min of a dated release, but `held_into_window` is a property of a hold that can begin HOURS earlier — on this block every such row (a seat entered in the morning and held through the 18:00 UTC FOMC) is outside the file. This pass closes the gap with the census's own definition and proves 0 disagreement on the rows the file does carry, but the file alone would under-count held-into exposure. Suggest the census emit held-into rows regardless of entry distance.
* **D33 — the scoring replay re-seats after a wall stop-out.** The reader held one position per (asset,phase) cell for the whole phase; the replay frees the seat at the certificate's exit second, which for a walled candidate is the wall. That gives the reader 9 seats it never claimed. Named because it moves the headline: the law is more generous than the reader's declared posture.
* All eight frozen predecessor policies e1d1..e1d8 ran AS COMMITTED through their own CLIs on all twelve days (no unrunnable arm), as did `e1_blind_declared_policy.py`.

---
Outputs: `artifacts/cache/port/m2/blind_score/` (ARMS, PERDAY, MARGINS, BARS, NEWS_DISTANCE, ANCILLARY, GEE, GIT_ORDERING, MUTANT, receipt). Pins re-checked at end: HELD.

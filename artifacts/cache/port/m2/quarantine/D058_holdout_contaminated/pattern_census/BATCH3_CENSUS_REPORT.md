# CENSUS BATCH 3 — P025 / P023 / P024 / P007-as-entry

Ordered by CC-M2-12.4. Population: the frozen v3 roster, 1580360 candidates over 3734 sessions (FIT 2021-2024 + the 2025 GATE echo, eval-only), all three assets. Detectors are strictly causal and read only committed pattern_lib frame fields (V1 + the V2 block this batch added: refail geometry, observed close, level confluence).

MULTIPLICITY: every GEE test of all four patterns and every reading is corrected Holm-Bonferroni as ONE family (372 tests).

NOT CENSUSABLE AT ERA SCALE (named, not hidden): P007's S7 `c2f`, P024's S7 `dBsz/min vs dAsz/min` erosion and P023's S8 through-book side are MBP-1 book-event statistics; the event cache covers 488 of 3734 roster sessions. Those terms are absent from the detectors below and the era-scale extraction is a build item.

## HEADLINE VERDICTS (CC-M2-9.1 vocabulary)

| detector | reading | fires (FIT) | per session | verdict | beta_close | Holm | winner-rate x | cond-value x |
|---|---|---|---|---|---|---|---|---|
| P025 | A_nominal | 901997 | 304.729 | WINNER CONCENTRATOR | 4.9 | HOLM_NOT_SIGNIFICANT | 3.70 | 2.13 |
| P025 | B_observed | 901810 | 304.666 | WINNER CONCENTRATOR | 4.9 | HOLM_NOT_SIGNIFICANT | 3.70 | 2.13 |
| P023 | ABS | 77796 | 26.282 | WINNER CONCENTRATOR | 13.5 | HOLM_NOT_SIGNIFICANT | 1.52 | 1.37 |
| P023 | REL | 80113 | 27.065 | WINNER CONCENTRATOR | 11.7 | HOLM_NOT_SIGNIFICANT | 1.43 | 1.32 |
| P023 | OR | 129237 | 43.661 | WINNER CONCENTRATOR | 8.3 | HOLM_NOT_SIGNIFICANT | 1.46 | 1.31 |
| P024 | A_core | 1823 | 0.616 | WINNER CONCENTRATOR | 0.8 | HOLM_NOT_SIGNIFICANT | 1.35 | 1.27 |
| P024 | B_confluence | 594 | 0.201 | NULL | 54.0 | HOLM_NOT_SIGNIFICANT | 1.00 | 1.14 |
| P007 | A_60s_ledger | 68852 | 23.261 | NULL | -10.2 | HOLM_NOT_SIGNIFICANT | 0.68 | 0.75 |
| P007 | B_phase_day3 | 86685 | 29.285 | NULL | 7.4 | HOLM_NOT_SIGNIFICANT | 1.00 | 1.02 |

## P025 RUNWAY_TO_BINDING_EXIT — the structural candidate

Runway = decision second -> the BINDING exit (the CC-M2-10.3 phase-close seat). Reading A is the nominal roster runway; reading B corrects it with the m0 receipt's observed close (D15). `conc_ratio` = winner share / candidate share, so 1.00 means the band holds winners exactly in proportion to the candidates generated inside it.

### runway bands — A_nominal (ALL assets, FIT)

| band | n | cand share | winners | winner rate | conc_ratio | mean close | cond close | frac >= $1000 | mean peak | NY share |
|---|---|---|---|---|---|---|---|---|---|---|
| b0_lt15m | 16843 | 0.0138 | 7 | 0.00042 | 0.01 | -38.0 | 89.9 | 0.0006 | 829.9 | 0.123 |
| b1_15-30m | 21249 | 0.0174 | 31 | 0.00146 | 0.03 | -34.5 | 166.1 | 0.0033 | 890.0 | 0.091 |
| b2_30-60m | 43841 | 0.0359 | 316 | 0.00721 | 0.13 | -40.4 | 238.3 | 0.0104 | 816.8 | 0.180 |
| b3_1-2h | 103989 | 0.0851 | 1654 | 0.01591 | 0.28 | -30.5 | 336.9 | 0.0237 | 762.7 | 0.296 |
| b4_2-3h | 134349 | 0.1099 | 4095 | 0.03048 | 0.53 | -30.1 | 468.5 | 0.0474 | 837.0 | 0.285 |
| b5_3-4h | 128185 | 0.1049 | 4497 | 0.03508 | 0.62 | -34.2 | 491.8 | 0.0527 | 869.4 | 0.273 |
| b6_4-6h | 260027 | 0.2127 | 14663 | 0.05639 | 0.99 | -32.6 | 629.7 | 0.0861 | 826.6 | 0.440 |
| b7_6-8h | 353458 | 0.2892 | 29046 | 0.08218 | 1.44 | -24.9 | 849.3 | 0.1317 | 805.9 | 0.814 |
| b8_ge8h | 160327 | 0.1312 | 15371 | 0.09587 | 1.68 | -19.0 | 1083.5 | 0.1659 | 920.1 | 0.949 |

### runway bands — B_observed (ALL assets, FIT)

| band | n | cand share | winners | winner rate | conc_ratio | mean close | cond close | frac >= $1000 | mean peak | NY share |
|---|---|---|---|---|---|---|---|---|---|---|
| b0_lt15m | 16846 | 0.0138 | 7 | 0.00042 | 0.01 | -38.0 | 89.9 | 0.0006 | 829.8 | 0.123 |
| b1_15-30m | 21257 | 0.0174 | 31 | 0.00146 | 0.03 | -34.5 | 166.1 | 0.0033 | 889.7 | 0.091 |
| b2_30-60m | 43857 | 0.0359 | 316 | 0.00721 | 0.13 | -40.4 | 238.3 | 0.0104 | 816.5 | 0.181 |
| b3_1-2h | 104049 | 0.0851 | 1654 | 0.01590 | 0.28 | -30.5 | 336.8 | 0.0237 | 762.3 | 0.296 |
| b4_2-3h | 134449 | 0.1100 | 4095 | 0.03046 | 0.53 | -30.1 | 468.3 | 0.0474 | 836.5 | 0.285 |
| b5_3-4h | 128378 | 0.1050 | 4497 | 0.03503 | 0.61 | -34.2 | 491.5 | 0.0526 | 868.5 | 0.274 |
| b6_4-6h | 260491 | 0.2131 | 14690 | 0.05639 | 0.99 | -32.6 | 629.4 | 0.0861 | 826.0 | 0.441 |
| b7_6-8h | 353060 | 0.2889 | 29036 | 0.08224 | 1.44 | -24.9 | 850.2 | 0.1318 | 806.5 | 0.813 |
| b8_ge8h | 159881 | 0.1308 | 15354 | 0.09603 | 1.68 | -18.9 | 1084.9 | 0.1662 | 921.4 | 0.949 |

### DOES PHASE SURVIVE CONDITIONING ON RUNWAY?  (ALL assets, FIT)

`NY_RAW` is P020's claim re-run as a GEE; `NY_ADJ` is the same coefficient with runway_hours in the model. The winner rows use a logit link because the struck claim (86 of 86) was a WINNER claim.

| reading | test | metric | beta | se_cr1 | z | p_cr1 | Holm |
|---|---|---|---|---|---|---|---|
| A_nominal | NY_RAW | cert_close | 8.1644 | 5.8347 | 1.40 | 0.161731 | HOLM_NOT_SIGNIFICANT |
| A_nominal | NY_RAW | winner | 0.6366 | 0.0370 | 17.19 | 0.000000 | HOLM_SIGNIFICANT |
| A_nominal | NY_ADJ | cert_close | 4.3945 | 6.0733 | 0.72 | 0.469327 | HOLM_NOT_SIGNIFICANT |
| A_nominal | NY_ADJ | winner | 0.0022 | 0.0468 | 0.05 | 0.962493 | HOLM_NOT_SIGNIFICANT |
| A_nominal | RW_RAW | cert_close | 1.8270 | 1.1608 | 1.57 | 0.115505 | HOLM_NOT_SIGNIFICANT |
| A_nominal | RW_RAW | winner | 0.2307 | 0.0068 | 33.71 | 0.000000 | HOLM_SIGNIFICANT |
| A_nominal | RW_ADJ | cert_close | 1.3690 | 1.2153 | 1.13 | 0.259969 | HOLM_NOT_SIGNIFICANT |
| A_nominal | RW_ADJ | winner | 0.2304 | 0.0086 | 26.84 | 0.000000 | HOLM_SIGNIFICANT |
| B_observed | NY_RAW | cert_close | 8.1644 | 5.8347 | 1.40 | 0.161731 | HOLM_NOT_SIGNIFICANT |
| B_observed | NY_RAW | winner | 0.6366 | 0.0370 | 17.19 | 0.000000 | HOLM_SIGNIFICANT |
| B_observed | NY_ADJ | cert_close | 4.3705 | 6.0665 | 0.72 | 0.471257 | HOLM_NOT_SIGNIFICANT |
| B_observed | NY_ADJ | winner | 0.0022 | 0.0467 | 0.05 | 0.962731 | HOLM_NOT_SIGNIFICANT |
| B_observed | RW_RAW | cert_close | 1.8355 | 1.1630 | 1.58 | 0.114521 | HOLM_NOT_SIGNIFICANT |
| B_observed | RW_RAW | winner | 0.2311 | 0.0069 | 33.74 | 0.000000 | HOLM_SIGNIFICANT |
| B_observed | RW_ADJ | cert_close | 1.3805 | 1.2169 | 1.13 | 0.256584 | HOLM_NOT_SIGNIFICANT |
| B_observed | RW_ADJ | winner | 0.2309 | 0.0086 | 26.89 | 0.000000 | HOLM_SIGNIFICANT |

### the same question stratified — is_NY INSIDE each runway band (FIT, all assets)

| band | metric | n | n_NY | beta | z | p_cr1 | Holm |
|---|---|---|---|---|---|---|---|
| b0_lt15m_A_nominal | cert_close | 16843 | 2066 | -7.2534 | -1.80 | 0.071147 | HOLM_NOT_SIGNIFICANT |
| b0_lt15m_A_nominal | winner | 16843 | 2066 | -16.5732 | -21.57 | 0.000000 | HOLM_SIGNIFICANT |
| b1_15-30m_A_nominal | cert_close | 21249 | 1925 | -3.2576 | -0.54 | 0.588864 | HOLM_NOT_SIGNIFICANT |
| b1_15-30m_A_nominal | winner | 21249 | 1925 | -1.0958 | -1.05 | 0.293783 | HOLM_NOT_SIGNIFICANT |
| b2_30-60m_A_nominal | cert_close | 43841 | 7911 | -2.2651 | -0.40 | 0.691210 | HOLM_NOT_SIGNIFICANT |
| b2_30-60m_A_nominal | winner | 43841 | 7911 | -0.6393 | -1.08 | 0.281428 | HOLM_NOT_SIGNIFICANT |
| b3_1-2h_A_nominal | cert_close | 103989 | 30733 | -12.5850 | -1.80 | 0.071687 | HOLM_NOT_SIGNIFICANT |
| b3_1-2h_A_nominal | winner | 103989 | 30733 | 0.3738 | 1.96 | 0.050123 | HOLM_NOT_SIGNIFICANT |
| b4_2-3h_A_nominal | cert_close | 134349 | 38278 | 7.4248 | 0.62 | 0.534680 | HOLM_NOT_SIGNIFICANT |
| b4_2-3h_A_nominal | winner | 134349 | 38278 | 0.7577 | 6.22 | 0.000000 | HOLM_SIGNIFICANT |
| b5_3-4h_A_nominal | cert_close | 128185 | 34940 | -1.7047 | -0.24 | 0.814131 | HOLM_NOT_SIGNIFICANT |
| b5_3-4h_A_nominal | winner | 128185 | 34940 | 0.0142 | 0.14 | 0.891867 | HOLM_NOT_SIGNIFICANT |
| b6_4-6h_A_nominal | cert_close | 260027 | 114438 | 10.3455 | 1.28 | 0.201803 | HOLM_NOT_SIGNIFICANT |
| b6_4-6h_A_nominal | winner | 260027 | 114438 | -0.2095 | -3.34 | 0.000827 | HOLM_NOT_SIGNIFICANT |
| b7_6-8h_A_nominal | cert_close | 353458 | 287563 | 2.7730 | 0.20 | 0.842015 | HOLM_NOT_SIGNIFICANT |
| b7_6-8h_A_nominal | winner | 353458 | 287563 | 0.0461 | 0.85 | 0.397738 | HOLM_NOT_SIGNIFICANT |
| b8_ge8h_A_nominal | cert_close | 160327 | 152125 | 14.8453 | 0.48 | 0.628711 | HOLM_NOT_SIGNIFICANT |
| b8_ge8h_A_nominal | winner | 160327 | 152125 | 0.1743 | 1.42 | 0.154691 | HOLM_NOT_SIGNIFICANT |
| b0_lt15m_B_observed | cert_close | 16846 | 2069 | -7.2295 | -1.80 | 0.071803 | HOLM_NOT_SIGNIFICANT |
| b0_lt15m_B_observed | winner | 16846 | 2069 | -16.5732 | -21.57 | 0.000000 | HOLM_SIGNIFICANT |
| b1_15-30m_B_observed | cert_close | 21257 | 1933 | -3.1589 | -0.52 | 0.599703 | HOLM_NOT_SIGNIFICANT |
| b1_15-30m_B_observed | winner | 21257 | 1933 | -1.1000 | -1.05 | 0.291962 | HOLM_NOT_SIGNIFICANT |
| b2_30-60m_B_observed | cert_close | 43857 | 7927 | -2.2239 | -0.39 | 0.696329 | HOLM_NOT_SIGNIFICANT |
| b2_30-60m_B_observed | winner | 43857 | 7927 | -0.6414 | -1.08 | 0.279909 | HOLM_NOT_SIGNIFICANT |
| b3_1-2h_B_observed | cert_close | 104049 | 30793 | -12.6115 | -1.81 | 0.070818 | HOLM_NOT_SIGNIFICANT |
| b3_1-2h_B_observed | winner | 104049 | 30793 | 0.3718 | 1.95 | 0.051371 | HOLM_NOT_SIGNIFICANT |
| b4_2-3h_B_observed | cert_close | 134449 | 38378 | 7.3776 | 0.62 | 0.536391 | HOLM_NOT_SIGNIFICANT |
| b4_2-3h_B_observed | winner | 134449 | 38378 | 0.7550 | 6.20 | 0.000000 | HOLM_SIGNIFICANT |
| b5_3-4h_B_observed | cert_close | 128378 | 35133 | -1.8816 | -0.26 | 0.794787 | HOLM_NOT_SIGNIFICANT |
| b5_3-4h_B_observed | winner | 128378 | 35133 | 0.0085 | 0.08 | 0.935322 | HOLM_NOT_SIGNIFICANT |
| b6_4-6h_B_observed | cert_close | 260491 | 114902 | 10.3343 | 1.28 | 0.201249 | HOLM_NOT_SIGNIFICANT |
| b6_4-6h_B_observed | winner | 260491 | 114902 | -0.2088 | -3.34 | 0.000848 | HOLM_NOT_SIGNIFICANT |
| b7_6-8h_B_observed | cert_close | 353060 | 287165 | 2.7789 | 0.20 | 0.841733 | HOLM_NOT_SIGNIFICANT |
| b7_6-8h_B_observed | winner | 353060 | 287165 | 0.0471 | 0.86 | 0.387052 | HOLM_NOT_SIGNIFICANT |
| b8_ge8h_B_observed | cert_close | 159881 | 151679 | 14.9461 | 0.49 | 0.626490 | HOLM_NOT_SIGNIFICANT |
| b8_ge8h_B_observed | winner | 159881 | 151679 | 0.1763 | 1.44 | 0.150026 | HOLM_NOT_SIGNIFICANT |

### phase within band — the artefact control (ALL assets, FIT, reading B_observed)

| band | phase | n | cand share | winners | winner share | conc_ratio_in_band | winner rate | band rate |
|---|---|---|---|---|---|---|---|---|
| b0_lt15m | TOKYO | 7897 | 0.469 | 5 | 0.714 | 1.52 | 0.00063 | 0.00042 |
| b0_lt15m | LONDON | 6880 | 0.408 | 2 | 0.286 | 0.70 | 0.00029 | 0.00042 |
| b0_lt15m | NY | 2069 | 0.123 | 0 | 0.000 | 0.00 | 0.00000 | 0.00042 |
| b1_15-30m | TOKYO | 11793 | 0.555 | 12 | 0.387 | 0.70 | 0.00102 | 0.00146 |
| b1_15-30m | LONDON | 7531 | 0.354 | 18 | 0.581 | 1.64 | 0.00239 | 0.00146 |
| b1_15-30m | NY | 1933 | 0.091 | 1 | 0.032 | 0.35 | 0.00052 | 0.00146 |
| b2_30-60m | TOKYO | 20041 | 0.457 | 195 | 0.617 | 1.35 | 0.00973 | 0.00721 |
| b2_30-60m | LONDON | 15889 | 0.362 | 88 | 0.278 | 0.77 | 0.00554 | 0.00721 |
| b2_30-60m | NY | 7927 | 0.181 | 33 | 0.104 | 0.58 | 0.00416 | 0.00721 |
| b3_1-2h | TOKYO | 33285 | 0.320 | 580 | 0.351 | 1.10 | 0.01743 | 0.01590 |
| b3_1-2h | LONDON | 39971 | 0.384 | 450 | 0.272 | 0.71 | 0.01126 | 0.01590 |
| b3_1-2h | NY | 30793 | 0.296 | 624 | 0.377 | 1.27 | 0.02026 | 0.01590 |
| b4_2-3h | TOKYO | 36103 | 0.269 | 923 | 0.225 | 0.84 | 0.02557 | 0.03046 |
| b4_2-3h | LONDON | 59968 | 0.446 | 1317 | 0.322 | 0.72 | 0.02196 | 0.03046 |
| b4_2-3h | NY | 38378 | 0.285 | 1855 | 0.453 | 1.59 | 0.04833 | 0.03046 |
| b5_3-4h | TOKYO | 41190 | 0.321 | 1166 | 0.259 | 0.81 | 0.02831 | 0.03503 |
| b5_3-4h | LONDON | 52055 | 0.405 | 2093 | 0.465 | 1.15 | 0.04021 | 0.03503 |
| b5_3-4h | NY | 35133 | 0.274 | 1238 | 0.275 | 1.01 | 0.03524 | 0.03503 |
| b6_4-6h | TOKYO | 113109 | 0.434 | 6966 | 0.474 | 1.09 | 0.06159 | 0.05639 |
| b6_4-6h | LONDON | 32480 | 0.125 | 1948 | 0.133 | 1.06 | 0.05998 | 0.05639 |
| b6_4-6h | NY | 114902 | 0.441 | 5776 | 0.393 | 0.89 | 0.05027 | 0.05639 |
| b7_6-8h | TOKYO | 65893 | 0.187 | 5231 | 0.180 | 0.97 | 0.07939 | 0.08224 |
| b7_6-8h | LONDON | 2 | 0.000 | 0 | 0.000 | 0.00 | 0.00000 | 0.08224 |
| b7_6-8h | NY | 287165 | 0.813 | 23805 | 0.820 | 1.01 | 0.08290 | 0.08224 |
| b8_ge8h | TOKYO | 8202 | 0.051 | 676 | 0.044 | 0.86 | 0.08242 | 0.09603 |
| b8_ge8h | NY | 151679 | 0.949 | 14678 | 0.956 | 1.01 | 0.09677 | 0.09603 |

## P023 ABSORPTION_TWO_STREAM_ENTRY — the repaired entry object

| reading | era | fires | per session | mean close | cond close | mean peak | winners | winner rate | baseline winner rate | beta_close | Holm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ABS | FIT | 77796 | 26.282 | -16.1 | 885.4 | 842.2 | 6522 | 0.08383 | 0.05519 | 13.5 | HOLM_NOT_SIGNIFICANT |
| ABS | GATE_2025 | 19443 | 25.120 | 102.2 | 1930.8 | 1576.4 | 1772 | 0.09114 | 0.06323 | 137.4 | HOLM_NOT_SIGNIFICANT |
| ABS | GATE_2025H1 | 8457 | 22.197 | 98.1 | 1472.7 | 1216.2 | 911 | 0.10772 | 0.06377 | . | . |
| ABS | GATE_2025H2 | 10986 | 27.954 | 105.4 | 2395.4 | 1853.7 | 861 | 0.07837 | 0.06269 | . | . |
| REL | FIT | 80113 | 27.065 | -17.7 | 859.7 | 978.5 | 6367 | 0.07948 | 0.05543 | 11.7 | HOLM_NOT_SIGNIFICANT |
| REL | GATE_2025 | 23787 | 30.733 | 28.2 | 1396.0 | 1418.1 | 1926 | 0.08097 | 0.06359 | 59.9 | HOLM_NOT_SIGNIFICANT |
| REL | GATE_2025H1 | 11730 | 30.787 | -11.7 | 1168.7 | 1256.9 | 1000 | 0.08525 | 0.06450 | . | . |
| REL | GATE_2025H2 | 12057 | 30.679 | 67.0 | 1640.6 | 1575.0 | 926 | 0.07680 | 0.06271 | . | . |
| OR | FIT | 129237 | 43.661 | -21.3 | 840.4 | 890.6 | 10266 | 0.07944 | 0.05436 | 8.3 | HOLM_NOT_SIGNIFICANT |
| OR | GATE_2025 | 35797 | 46.249 | 37.5 | 1535.9 | 1444.9 | 2995 | 0.08367 | 0.06264 | 72.5 | HOLM_NOT_SIGNIFICANT |
| OR | GATE_2025H1 | 16746 | 43.953 | 19.4 | 1232.8 | 1217.4 | 1525 | 0.09107 | 0.06324 | . | . |
| OR | GATE_2025H2 | 19051 | 48.476 | 53.4 | 1856.8 | 1644.9 | 1470 | 0.07716 | 0.06206 | . | . |

TERM MARGINALS (FIT, all assets): what each term does alone, and what the detector does with it dropped.

| reading | term | scope | n | mean close | cond close | winners | winner rate |
|---|---|---|---|---|---|---|---|
| ABS | T1_opposed_5m | TERM_ALONE | 359312 | -32.1 | 676.5 | 21390 | 0.05953 |
| ABS | T1_opposed_5m | DETECTOR_MINUS_TERM | 272889 | -14.5 | 897.4 | 22604 | 0.08283 |
| ABS | T1_opposed_5m | NEAR_MISS_ONLY_THIS_TERM_FAILS | 195093 | -13.9 | 902.2 | 16082 | 0.08243 |
| ABS | T2_vol_abs_500 | TERM_ALONE | 288805 | -14.7 | 906.3 | 24006 | 0.08312 |
| ABS | T2_vol_abs_500 | DETECTOR_MINUS_TERM | 292363 | -30.0 | 687.5 | 17838 | 0.06101 |
| ABS | T2_vol_abs_500 | NEAR_MISS_ONLY_THIS_TERM_FAILS | 214567 | -35.1 | 617.9 | 11316 | 0.05274 |
| ABS | T3_live_book | TERM_ALONE | 1074796 | -26.1 | 683.9 | 63830 | 0.05939 |
| ABS | T3_live_book | DETECTOR_MINUS_TERM | 77798 | -16.1 | 885.4 | 6522 | 0.08383 |
| ABS | T3_live_book | NEAR_MISS_ONLY_THIS_TERM_FAILS | 2 | -155.0 | 420.0 | 0 | 0.00000 |
| ABS | T4_price_failure | TERM_ALONE | 1188230 | -28.5 | 655.8 | 67021 | 0.05640 |
| ABS | T4_price_failure | DETECTOR_MINUS_TERM | 87198 | -15.8 | 905.1 | 7375 | 0.08458 |
| ABS | T4_price_failure | NEAR_MISS_ONLY_THIS_TERM_FAILS | 9402 | -13.7 | 1080.4 | 853 | 0.09073 |
| REL | T1_opposed_5m | TERM_ALONE | 359312 | -32.1 | 676.5 | 21390 | 0.05953 |
| REL | T1_opposed_5m | DETECTOR_MINUS_TERM | 276075 | -25.0 | 868.9 | 21108 | 0.07646 |
| REL | T1_opposed_5m | NEAR_MISS_ONLY_THIS_TERM_FAILS | 195962 | -27.9 | 872.7 | 14741 | 0.07522 |
| REL | T2_vol_rel_8pct | TERM_ALONE | 323310 | -26.8 | 864.3 | 24569 | 0.07599 |
| REL | T2_vol_rel_8pct | DETECTOR_MINUS_TERM | 292363 | -30.0 | 687.5 | 17838 | 0.06101 |
| REL | T2_vol_rel_8pct | NEAR_MISS_ONLY_THIS_TERM_FAILS | 212250 | -34.6 | 623.3 | 11471 | 0.05404 |
| REL | T3_live_book | TERM_ALONE | 1074796 | -26.1 | 683.9 | 63830 | 0.05939 |
| REL | T3_live_book | DETECTOR_MINUS_TERM | 88018 | -19.8 | 845.4 | 6891 | 0.07829 |
| REL | T3_live_book | NEAR_MISS_ONLY_THIS_TERM_FAILS | 7905 | -40.7 | 702.9 | 524 | 0.06629 |
| REL | T4_price_failure | TERM_ALONE | 1188230 | -28.5 | 655.8 | 67021 | 0.05640 |
| REL | T4_price_failure | DETECTOR_MINUS_TERM | 92865 | -20.3 | 875.0 | 7423 | 0.07993 |
| REL | T4_price_failure | NEAR_MISS_ONLY_THIS_TERM_FAILS | 12752 | -36.1 | 977.0 | 1056 | 0.08281 |
| OR | T1_opposed_5m | TERM_ALONE | 359312 | -32.1 | 676.5 | 21390 | 0.05953 |
| OR | T1_opposed_5m | DETECTOR_MINUS_TERM | 450175 | -20.1 | 852.8 | 35181 | 0.07815 |
| OR | T1_opposed_5m | NEAR_MISS_ONLY_THIS_TERM_FAILS | 320938 | -19.6 | 857.8 | 24915 | 0.07763 |
| OR | T2_vol_abs_or_rel | TERM_ALONE | 502440 | -21.7 | 851.6 | 39076 | 0.07777 |
| OR | T2_vol_abs_or_rel | DETECTOR_MINUS_TERM | 292363 | -30.0 | 687.5 | 17838 | 0.06101 |
| OR | T2_vol_abs_or_rel | NEAR_MISS_ONLY_THIS_TERM_FAILS | 163126 | -36.9 | 568.4 | 7572 | 0.04642 |
| OR | T3_live_book | TERM_ALONE | 1074796 | -26.1 | 683.9 | 63830 | 0.05939 |
| OR | T3_live_book | DETECTOR_MINUS_TERM | 137143 | -22.4 | 832.4 | 10790 | 0.07868 |
| OR | T3_live_book | NEAR_MISS_ONLY_THIS_TERM_FAILS | 7906 | -40.6 | 702.8 | 524 | 0.06628 |
| OR | T4_price_failure | TERM_ALONE | 1188230 | -28.5 | 655.8 | 67021 | 0.05640 |
| OR | T4_price_failure | DETECTOR_MINUS_TERM | 144917 | -22.0 | 853.2 | 11591 | 0.07998 |
| OR | T4_price_failure | NEAR_MISS_ONLY_THIS_TERM_FAILS | 15680 | -27.4 | 963.5 | 1325 | 0.08450 |

MECHANISM DESTRUCTION (each term shuffled within its session, 40 replicates): `edge_retention` is the fraction of the intact edge that SURVIVES the destruction — a load-bearing term leaves little behind.

| reading | neutralised term | intact fires | intact edge | destroyed edge | retention | verdict |
|---|---|---|---|---|---|---|
| ABS | T1_opposed_5m | 77796 | 13.5 | 15.2 | 1.12 | TERM_NOT_LOAD_BEARING |
| ABS | T2_vol_abs_500 | 77796 | 13.5 | 23.0 | 1.70 | TERM_NOT_LOAD_BEARING |
| ABS | T3_live_book | 77796 | 13.5 | 13.8 | 1.02 | TERM_NOT_LOAD_BEARING |
| ABS | T4_price_failure | 77796 | 13.5 | 13.3 | 0.98 | TERM_NOT_LOAD_BEARING |
| REL | T1_opposed_5m | 80113 | 11.7 | 5.5 | 0.47 | TERM_LOAD_BEARING |
| REL | T2_vol_rel_8pct | 80113 | 11.7 | 1.9 | 0.16 | TERM_LOAD_BEARING |
| REL | T3_live_book | 80113 | 11.7 | 14.3 | 1.22 | TERM_NOT_LOAD_BEARING |
| REL | T4_price_failure | 80113 | 11.7 | 8.7 | 0.74 | PARTIAL |
| OR | T1_opposed_5m | 129237 | 8.3 | 10.0 | 1.21 | TERM_NOT_LOAD_BEARING |
| OR | T2_vol_abs_or_rel | 129237 | 8.3 | 10.8 | 1.31 | TERM_NOT_LOAD_BEARING |
| OR | T3_live_book | 129237 | 8.3 | 9.9 | 1.20 | TERM_NOT_LOAD_BEARING |
| OR | T4_price_failure | 129237 | 8.3 | 7.0 | 0.85 | TERM_NOT_LOAD_BEARING |

## P024 REFAIL_REVERSION — direction confirmed, magnitude failed

| reading | era | fires | per session | mean close | cond close | mean peak | winners | winner rate | baseline winner rate | beta_close | Holm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A_core | FIT | 1823 | 0.616 | -27.9 | 840.9 | 869.2 | 140 | 0.07680 | 0.05698 | 0.8 | HOLM_NOT_SIGNIFICANT |
| A_core | GATE_2025 | 626 | 0.809 | -118.3 | 1015.9 | 1090.4 | 44 | 0.07029 | 0.06474 | -90.7 | HOLM_NOT_SIGNIFICANT |
| A_core | GATE_2025H1 | 341 | 0.895 | -18.7 | 963.8 | 1196.0 | 23 | 0.06745 | 0.06587 | . | . |
| A_core | GATE_2025H2 | 285 | 0.725 | -237.4 | 1106.4 | 964.1 | 21 | 0.07368 | 0.06363 | . | . |
| B_confluence | FIT | 594 | 0.201 | 25.3 | 757.4 | 831.2 | 34 | 0.05724 | 0.05701 | 54.0 | HOLM_NOT_SIGNIFICANT |
| B_confluence | GATE_2025 | 145 | 0.187 | -196.6 | 727.4 | 920.0 | 10 | 0.06897 | 0.06474 | -168.9 | HOLM_NOT_SIGNIFICANT |
| B_confluence | GATE_2025H1 | 85 | 0.223 | -158.0 | 795.2 | 913.2 | 7 | 0.08235 | 0.06586 | . | . |
| B_confluence | GATE_2025H2 | 60 | 0.153 | -251.1 | 617.6 | 929.6 | 3 | 0.05000 | 0.06365 | . | . |

TERM MARGINALS (FIT, all assets): what each term does alone, and what the detector does with it dropped.

| reading | term | scope | n | mean close | cond close | winners | winner rate |
|---|---|---|---|---|---|---|---|
| A_core | T1_refail | TERM_ALONE | 100765 | -25.4 | 794.9 | 7527 | 0.07470 |
| A_core | T1_refail | DETECTOR_MINUS_TERM | 17466 | -50.1 | 664.5 | 888 | 0.05084 |
| A_core | T1_refail | NEAR_MISS_ONLY_THIS_TERM_FAILS | 15643 | -52.7 | 643.4 | 748 | 0.04782 |
| A_core | T2_expanded | TERM_ALONE | 632063 | -32.1 | 641.1 | 34723 | 0.05494 |
| A_core | T2_expanded | DETECTOR_MINUS_TERM | 3073 | -51.7 | 786.1 | 205 | 0.06671 |
| A_core | T2_expanded | NEAR_MISS_ONLY_THIS_TERM_FAILS | 1250 | -86.5 | 705.7 | 65 | 0.05200 |
| A_core | T3_room | TERM_ALONE | 533783 | -33.1 | 697.7 | 31755 | 0.05949 |
| A_core | T3_room | DETECTOR_MINUS_TERM | 5538 | -34.0 | 760.9 | 384 | 0.06934 |
| A_core | T3_room | NEAR_MISS_ONLY_THIS_TERM_FAILS | 3715 | -36.9 | 721.4 | 244 | 0.06568 |
| A_core | T4_flow_concordant | TERM_ALONE | 154794 | -50.4 | 647.3 | 8289 | 0.05355 |
| A_core | T4_flow_concordant | DETECTOR_MINUS_TERM | 31415 | -28.0 | 816.0 | 2367 | 0.07535 |
| A_core | T4_flow_concordant | NEAR_MISS_ONLY_THIS_TERM_FAILS | 29592 | -28.0 | 814.5 | 2227 | 0.07526 |
| B_confluence | T1_refail | TERM_ALONE | 100765 | -25.4 | 794.9 | 7527 | 0.07470 |
| B_confluence | T1_refail | DETECTOR_MINUS_TERM | 5558 | -50.5 | 563.3 | 245 | 0.04408 |
| B_confluence | T1_refail | NEAR_MISS_ONLY_THIS_TERM_FAILS | 4964 | -59.6 | 537.4 | 211 | 0.04251 |
| B_confluence | T2_expanded | TERM_ALONE | 632063 | -32.1 | 641.1 | 34723 | 0.05494 |
| B_confluence | T2_expanded | DETECTOR_MINUS_TERM | 1149 | -82.0 | 700.4 | 47 | 0.04091 |
| B_confluence | T2_expanded | NEAR_MISS_ONLY_THIS_TERM_FAILS | 555 | -196.7 | 625.0 | 13 | 0.02342 |
| B_confluence | T3_room | TERM_ALONE | 533783 | -33.1 | 697.7 | 31755 | 0.05949 |
| B_confluence | T3_room | DETECTOR_MINUS_TERM | 2007 | 10.3 | 746.9 | 133 | 0.06627 |
| B_confluence | T3_room | NEAR_MISS_ONLY_THIS_TERM_FAILS | 1413 | 4.0 | 742.1 | 99 | 0.07006 |
| B_confluence | T4_flow_concordant | TERM_ALONE | 154794 | -50.4 | 647.3 | 8289 | 0.05355 |
| B_confluence | T4_flow_concordant | DETECTOR_MINUS_TERM | 10293 | -23.0 | 776.5 | 760 | 0.07384 |
| B_confluence | T4_flow_concordant | NEAR_MISS_ONLY_THIS_TERM_FAILS | 9699 | -26.0 | 777.8 | 726 | 0.07485 |
| B_confluence | T5_confluence | TERM_ALONE | 427954 | -25.3 | 661.9 | 24803 | 0.05796 |
| B_confluence | T5_confluence | DETECTOR_MINUS_TERM | 1823 | -27.9 | 840.9 | 140 | 0.07680 |
| B_confluence | T5_confluence | NEAR_MISS_ONLY_THIS_TERM_FAILS | 1229 | -53.6 | 888.4 | 106 | 0.08625 |

MECHANISM DESTRUCTION (each term shuffled within its session, 40 replicates): `edge_retention` is the fraction of the intact edge that SURVIVES the destruction — a load-bearing term leaves little behind.

| reading | neutralised term | intact fires | intact edge | destroyed edge | retention | verdict |
|---|---|---|---|---|---|---|
| A_core | T1_refail | 1823 | 0.8 | 8.5 | 10.90 | TERM_NOT_LOAD_BEARING |
| A_core | T2_expanded | 1823 | 0.8 | -20.2 | -25.81 | TERM_LOAD_BEARING |
| A_core | T3_room | 1823 | 0.8 | -12.8 | -16.43 | TERM_LOAD_BEARING |
| A_core | T4_flow_concordant | 1823 | 0.8 | -4.1 | -5.19 | TERM_LOAD_BEARING |
| B_confluence | T1_refail | 594 | 54.0 | -16.7 | -0.31 | TERM_LOAD_BEARING |
| B_confluence | T2_expanded | 594 | 54.0 | -22.9 | -0.42 | TERM_LOAD_BEARING |
| B_confluence | T3_room | 594 | 54.0 | 44.2 | 0.82 | TERM_NOT_LOAD_BEARING |
| B_confluence | T4_flow_concordant | 594 | 54.0 | 2.8 | 0.05 | TERM_LOAD_BEARING |
| B_confluence | T5_confluence | 594 | 54.0 | 49.4 | 0.91 | TERM_NOT_LOAD_BEARING |

### DIRECTION vs MAGNITUDE (the day-3 verdict, censused)

| reading | era | group | n | posfrac (direction) | cond close | median close | frac >= $1000 | mean peak - mean close | winners |
|---|---|---|---|---|---|---|---|---|---|
| P024_A_core | FIT | FIRE | 1823 | 0.4328 | 840.9 | -142.5 | 0.1262 | 897.1 | 140 |
| P024_A_core | FIT | NOFIRE | 1220445 | 0.4394 | 662.3 | -80.0 | 0.0913 | 862.5 | 69540 |
| P024_A_core | GATE_2025 | FIRE | 626 | 0.3802 | 1015.9 | -673.8 | 0.1086 | 1208.7 | 44 |
| P024_A_core | GATE_2025 | NOFIRE | 357466 | 0.3898 | 1061.3 | -267.5 | 0.1270 | 1232.4 | 23141 |
| P024_B_confluence | FIT | FIRE | 594 | 0.4815 | 757.4 | -39.4 | 0.1094 | 805.9 | 34 |
| P024_B_confluence | FIT | NOFIRE | 1221674 | 0.4394 | 662.5 | -80.0 | 0.0914 | 862.6 | 69646 |
| P024_B_confluence | GATE_2025 | FIRE | 145 | 0.3793 | 727.4 | -330.0 | 0.0828 | 1116.5 | 10 |
| P024_B_confluence | GATE_2025 | NOFIRE | 357947 | 0.3898 | 1061.3 | -267.5 | 0.1270 | 1232.4 | 23175 |

## P007 ABSORPTION_NO_RESPONSE — censused AS AN ENTRY

| reading | era | fires | per session | mean close | cond close | mean peak | winners | winner rate | baseline winner rate | beta_close | Holm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A_60s_ledger | FIT | 68852 | 23.261 | -38.3 | 505.0 | 769.2 | 2718 | 0.03948 | 0.05806 | -10.2 | HOLM_NOT_SIGNIFICANT |
| A_60s_ledger | GATE_2025 | 13707 | 17.709 | -40.4 | 685.0 | 997.4 | 673 | 0.04910 | 0.06537 | -13.1 | HOLM_NOT_SIGNIFICANT |
| A_60s_ledger | GATE_2025H1 | 7380 | 19.370 | -39.7 | 657.2 | 1016.8 | 362 | 0.04905 | 0.06660 | . | . |
| A_60s_ledger | GATE_2025H2 | 6327 | 16.099 | -41.2 | 718.9 | 974.7 | 311 | 0.04915 | 0.06417 | . | . |
| B_phase_day3 | FIT | 86685 | 29.285 | -21.8 | 675.5 | 882.9 | 4925 | 0.05681 | 0.05702 | 7.4 | HOLM_NOT_SIGNIFICANT |
| B_phase_day3 | GATE_2025 | 24212 | 31.282 | -8.1 | 957.9 | 1148.8 | 1630 | 0.06732 | 0.06456 | 21.0 | HOLM_NOT_SIGNIFICANT |
| B_phase_day3 | GATE_2025H1 | 11931 | 31.315 | -72.2 | 825.8 | 1115.2 | 776 | 0.06504 | 0.06593 | . | . |
| B_phase_day3 | GATE_2025H2 | 12281 | 31.249 | 54.1 | 1086.8 | 1181.5 | 854 | 0.06954 | 0.06322 | . | . |

TERM MARGINALS (FIT, all assets): what each term does alone, and what the detector does with it dropped.

| reading | term | scope | n | mean close | cond close | winners | winner rate |
|---|---|---|---|---|---|---|---|
| A_60s_ledger | T1_opposed_60s_0.40 | TERM_ALONE | 174123 | -34.4 | 564.1 | 8048 | 0.04622 |
| A_60s_ledger | T1_opposed_60s_0.40 | DETECTOR_MINUS_TERM | 417503 | -32.4 | 564.8 | 19380 | 0.04642 |
| A_60s_ledger | T1_opposed_60s_0.40 | NEAR_MISS_ONLY_THIS_TERM_FAILS | 348651 | -31.2 | 576.6 | 16662 | 0.04779 |
| A_60s_ledger | T2_no_price_response | TERM_ALONE | 417503 | -32.4 | 564.8 | 19380 | 0.04642 |
| A_60s_ledger | T2_no_price_response | DETECTOR_MINUS_TERM | 174123 | -34.4 | 564.1 | 8048 | 0.04622 |
| A_60s_ledger | T2_no_price_response | NEAR_MISS_ONLY_THIS_TERM_FAILS | 105271 | -31.8 | 602.3 | 5330 | 0.05063 |
| B_phase_day3 | T1_opposed_phase_0.10 | TERM_ALONE | 92814 | -20.7 | 688.4 | 5389 | 0.05806 |
| B_phase_day3 | T1_opposed_phase_0.10 | DETECTOR_MINUS_TERM | 1188230 | -28.5 | 655.8 | 67021 | 0.05640 |
| B_phase_day3 | T1_opposed_phase_0.10 | NEAR_MISS_ONLY_THIS_TERM_FAILS | 1101545 | -29.1 | 654.2 | 62096 | 0.05637 |
| B_phase_day3 | T2_price_failure | TERM_ALONE | 1188230 | -28.5 | 655.8 | 67021 | 0.05640 |
| B_phase_day3 | T2_price_failure | DETECTOR_MINUS_TERM | 92814 | -20.7 | 688.4 | 5389 | 0.05806 |
| B_phase_day3 | T2_price_failure | NEAR_MISS_ONLY_THIS_TERM_FAILS | 6129 | -4.6 | 870.8 | 464 | 0.07571 |

MECHANISM DESTRUCTION (each term shuffled within its session, 40 replicates): `edge_retention` is the fraction of the intact edge that SURVIVES the destruction — a load-bearing term leaves little behind.

| reading | neutralised term | intact fires | intact edge | destroyed edge | retention | verdict |
|---|---|---|---|---|---|---|
| A_60s_ledger | T1_opposed_60s_0.40 | 68852 | -10.2 | -10.0 | 0.98 | VOID_no_intact_edge |
| A_60s_ledger | T2_no_price_response | 68852 | -10.2 | -9.3 | 0.91 | VOID_no_intact_edge |
| B_phase_day3 | T1_opposed_phase_0.10 | 86685 | 7.4 | -9.2 | -1.25 | TERM_LOAD_BEARING |
| B_phase_day3 | T2_price_failure | 86685 | 7.4 | 7.9 | 1.07 | TERM_NOT_LOAD_BEARING |

## THE BIRTH CASES (do the detectors fire on the cases they were born on?)

| cid | what it is | detectors that fire |
|---|---|---|
| HG-20210705-010979-L | P025 birth case (TOKYO long, 3h57m of runway, cert +$1,020) | P025_A_nominal, P025_B_observed, P007_B_phase_day3 |
| HG-20210705-012045-L | P025 birth case (cert +$1,138.75, MAE $0) | P025_A_nominal, P025_B_observed, P023_REL, P023_OR, P007_B_phase_day3 |
| HG-20210705-055113-S | P024 birth case (the day-3 override: +$382.50 on a $1,000 thesis, peak +$776.25) | P025_A_nominal, P025_B_observed, P024_A_core, P024_B_confluence |
| HG-20210705-056096-S | P024 companion (+$145) | P025_A_nominal, P025_B_observed |

## PROVENANCE

* elapsed 237.7s; pins HELD
* D-038/D-058 HOLDOUT, FLAGGED FOR ADJUDICATION: 261 sessions from 2025-09-01 onward are inside the GATE echo. Batches 1-2 pooled the whole GATE year, so the pooled row is kept for comparability and every table also carries GATE_2025H1 / GATE_2025H2 — the H1 row is the holdout-free reading. FIT (the only fitted era) is untouched by this.
* outputs: BATCH3_{CENSUS,TERMS,DESTRUCTION,ROBUST}.tsv, P025_RUNWAY.tsv, P025_PHASE_GIVEN_RUNWAY.tsv, P024_MAGNITUDE.tsv


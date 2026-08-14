# P001 PHASE_ROLLOVER_UNDERMOVED — name->count census

Pattern: `P001 PHASE_ROLLOVER_UNDERMOVED` (provenance/port_m2/PATTERN_LEDGER.tsv). The first pattern through the DISCRETIONARY_METHOD §4.2 codification loop, run on V1.1-correct data per CC-M2-7.2.

Population: the frozen v3 roster, 1580360 candidates over 3734 sessions (FIT 2021-2024 + the 2025 GATE echo), all three assets.

## HEADLINE

* **Reading A** — fires 3.53/session (10455 fires, 2960 sessions). ADOPTION METRIC (walled phase-close): mean $-46.06 for the firing set vs $-28.55 for everything it does not fire on, a session-clustered difference of $-17.50 (CR1 se $21.51, p=0.4159) -> **NO MEAN-VALUE EDGE**. PEAK-EXIT companion: $25.02 (p=0.1858). CONDITIONAL value (mean over the winners it does produce): $1036.98 vs $659.65 = 1.57x. D-021 winner rate 9.63% vs 5.67% = 1.70x.
* **Reading B** — fires 10.65/session (31534 fires, 2960 sessions). ADOPTION METRIC (walled phase-close): mean $-30.10 for the firing set vs $-28.67 for everything it does not fire on, a session-clustered difference of $-1.44 (CR1 se $15.31, p=0.9252) -> **NO MEAN-VALUE EDGE**. PEAK-EXIT companion: $18.31 (p=0.1560). CONDITIONAL value (mean over the winners it does produce): $1015.23 vs $653.85 = 1.55x. D-021 winner rate 9.28% vs 5.61% = 1.65x.
* **Reading P016** — fires 3.65/session (10797 fires, 2960 sessions). ADOPTION METRIC (walled phase-close): mean $-123.21 for the firing set vs $-27.86 for everything it does not fire on, a session-clustered difference of $-95.35 (CR1 se $53.37, p=0.0740) -> **NO MEAN-VALUE EDGE**. PEAK-EXIT companion: $-79.75 (p=0.0600). CONDITIONAL value (mean over the winners it does produce): $905.67 vs $660.72 = 1.37x. D-021 winner rate 8.42% vs 5.68% = 1.48x.

DEFECT D-P001-1 (the T4 ambiguity, found by this census). PATTERN_LEDGER names the age term as `age of S3.phase H (SHORT) or L (LONG) <= 200s`, but that field does NOT reproduce the post-mortem's own table: on HG-20210929-052330-S the phase H is 1,236s old at the decision second while the post-mortem quotes 93s. 93s is the age of the most recent CAUSAL ZigZag HIGH pivot (14:30:37, confirmed 14:31:48, decision 14:32:10). The two readings agree on the other two support cases. Both are censused here: READING A is the ledger literal, READING B the post-mortem literal. The orchestrator rules which one P001 means; the ledger's `sheet_fields` text needs the fix either way.

MULTIPLICITY: 16 GEE tests are run per reading (4 asset groups x 2 eras x 2 certificate readings). Every robust table therefore carries Holm-Bonferroni columns; an uncorrected p<0.05 row that fails Holm is noise, and the tables say which is which.

## ARM A — P001 (PATTERN_LEDGER literal: T4 = phase-extreme age)

| | fires | per session | mean close $ | cond. close $ | mean peak $ | cond. peak $ | winners |
|---|---|---|---|---|---|---|---|
| FIRE | 10455 | 3.532 | -46.06 | 1036.98 | 858.70 | 914.26 | 1007 (9.63%) |
| NOFIRE | 1211813 | 409.396 | -28.55 | 659.65 | 833.68 | 902.23 | 68673 (5.67%) |

Per-year stability (ALL assets, FIRE group):

| year | fires | per session | mean close $ | cond. close $ | mean peak $ |
|---|---|---|---|---|---|
| 2021 | 1739 | 2.730 | -59.61 | 835.07 | 736.46 |
| 2021 baseline | 240188 | 377.061 | -29.75 | 597.94 | 790.27 |
| 2022 | 2575 | 3.327 | -21.10 | 1093.67 | 904.39 |
| 2022 baseline | 331269 | 427.996 | -34.21 | 667.44 | 833.49 |
| 2023 | 3492 | 4.523 | -48.32 | 908.92 | 753.61 |
| 2023 baseline | 310305 | 401.949 | -22.98 | 568.02 | 726.99 |
| 2024 | 2649 | 3.409 | -58.42 | 1325.67 | 1033.07 |
| 2024 baseline | 330051 | 424.776 | -27.25 | 790.81 | 965.76 |
| GATE_2025 (eval-only) | 2840 | 3.669 | -31.93 | 1604.05 | 1174.14 |
| GATE_2025 baseline | 355252 | 458.982 | -27.69 | 1057.43 | 1204.84 |

Co-occurrence break-out (FIT, FIRE group) — the E1 note flagged P001's support set as all-HG / all-NY / all-SHORT, and P016's name carries NY/SHORT too; neither is a term here, so these strata are what breaks the co-occurrence apart:

| stratum | fires | mean close $ | cond. close $ | baseline mean $ |
|---|---|---|---|---|
| ALL / ALL / LONG | 5434 | 2.58 | 1007.77 | -27.41 |
| ALL / ALL / SHORT | 5021 | -98.69 | 1074.33 | -29.71 |
| ALL / NY / ALL | 10455 | -46.06 | 1036.98 | -24.68 |
| HG / ALL / ALL | 3655 | -39.31 | 804.93 | -27.70 |
| HG / ALL / LONG | 1863 | -11.43 | 786.20 | -36.47 |
| HG / ALL / SHORT | 1792 | -68.30 | 825.81 | -18.91 |
| HG / NY / ALL | 3655 | -39.31 | 804.93 | -33.14 |
| NKD / ALL / ALL | 2050 | -22.00 | 922.20 | -46.71 |
| NKD / ALL / LONG | 1096 | 59.14 | 848.69 | -33.16 |
| NKD / ALL / SHORT | 954 | -115.22 | 1040.49 | -60.55 |
| NKD / NY / ALL | 2050 | -22.00 | 922.20 | -48.93 |
| SI / ALL / ALL | 4750 | -61.63 | 1305.72 | -11.42 |
| SI / ALL / LONG | 2475 | -11.93 | 1283.67 | -12.35 |
| SI / ALL / SHORT | 2275 | -115.69 | 1334.28 | -10.49 |
| SI / NY / ALL | 4750 | -61.63 | 1305.72 | -2.77 |

Mechanism destruction (FIT, ALL assets; each term shuffled within its session, 40 replicates). EDGE = mean close of the firing set minus mean close of the non-firing rest; `retention` = destroyed edge / intact edge. High retention means the term was not carrying the value. Intact edge = $-17.50 (close), $25.02 (peak).

| neutralised term | fires (mean) | mean close $ | edge close $ | retention close | retention peak | verdict |
|---|---|---|---|---|---|---|
| T1_coverage | 5241.5 | -42.96 | -14.32 | 0.818 | -1.403 | VOID_no_intact_edge |
| T2_ladder | 5642.8 | -43.60 | -14.96 | 0.855 | -1.361 | VOID_no_intact_edge |
| T3_runway | 4919.3 | -36.11 | -7.44 | 0.425 | 3.900 | VOID_no_intact_edge |
| T4_age | 5638.8 | -10.57 | 18.22 | -1.041 | 1.503 | VOID_no_intact_edge |
| T5_slope | 7466.1 | -23.03 | 5.71 | -0.326 | 2.596 | VOID_no_intact_edge |

Cluster-robust inference (CC-M1-12.4; GEE identity link, Liang-Zeger sandwich clustered on SESSION, CR1 scaling):

| asset | era | metric | beta $ | se naive | se CR1 | z | p | DEFF | n_eff | raw verdict | Holm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | FIT | cert_close | -17.50 | 8.27 | 21.51 | -0.81 | 0.41590 | 10.24 | 119357.4 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| ALL | FIT | cert_peak | 25.02 | 10.17 | 18.91 | 1.32 | 0.18576 | 45.11 | 27092.3 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| ALL | GATE_2025 | cert_close | -4.24 | 25.79 | 46.31 | -0.09 | 0.92710 | 13.87 | 25826.2 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| ALL | GATE_2025 | cert_peak | -30.70 | 38.14 | 51.29 | -0.60 | 0.54942 | 42.21 | 8484.1 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| SI | FIT | cert_close | -50.20 | 14.47 | 39.06 | -1.29 | 0.19874 | 15.64 | 25919.5 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| SI | FIT | cert_peak | 47.15 | 17.17 | 35.25 | 1.34 | 0.18102 | 40.50 | 10012.1 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| SI | GATE_2025 | cert_close | 16.09 | 47.15 | 72.99 | 0.22 | 0.82557 | 14.85 | 9001.4 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| SI | GATE_2025 | cert_peak | -145.80 | 73.91 | 99.00 | -1.47 | 0.14081 | 37.87 | 3530.7 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | FIT | cert_close | -11.61 | 11.03 | 26.93 | -0.43 | 0.66627 | 5.25 | 79420.9 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | FIT | cert_peak | -15.17 | 13.86 | 21.40 | -0.71 | 0.47837 | 45.00 | 9273.3 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | GATE_2025 | cert_close | 14.73 | 34.97 | 87.47 | 0.17 | 0.86629 | 10.18 | 11025.0 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | GATE_2025 | cert_peak | 68.26 | 46.92 | 80.38 | 0.85 | 0.39575 | 39.40 | 2848.5 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | FIT | cert_close | 24.71 | 18.65 | 38.33 | 0.64 | 0.51914 | 6.61 | 60412.8 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | FIT | cert_peak | -45.17 | 23.37 | 30.14 | -1.50 | 0.13394 | 41.24 | 9688.5 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | GATE_2025 | cert_close | -62.32 | 45.50 | 80.52 | -0.77 | 0.43894 | 15.93 | 7040.7 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | GATE_2025 | cert_peak | -93.63 | 59.31 | 57.84 | -1.62 | 0.10551 | 40.35 | 2780.1 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |

Term marginals (FIT, ALL assets):

| term | alone: n / mean close $ | detector without it: n / mean close $ | near-miss (only this fails): n / mean close $ |
|---|---|---|---|
| T1_coverage | 503892 / -28.53 | 11150 / -40.96 | 695 / 35.75 |
| T2_ladder | 561021 / -28.68 | 10522 / -45.01 | 67 / 118.13 |
| T3_runway | 219064 / -24.03 | 25013 / -32.59 | 14558 / -22.92 |
| T4_age | 117273 / -31.62 | 58878 / -33.41 | 48423 / -30.68 |
| T5_slope | 431709 / -27.08 | 20809 / -23.71 | 10354 / -1.15 |

## ARM B — P001 (post-mortem literal: T4 = causal ZigZag pivot age)

| | fires | per session | mean close $ | cond. close $ | mean peak $ | cond. peak $ | winners |
|---|---|---|---|---|---|---|---|
| FIRE | 31534 | 10.653 | -30.10 | 1015.23 | 851.73 | 911.59 | 2925 (9.28%) |
| NOFIRE | 1190734 | 402.275 | -28.67 | 653.85 | 833.42 | 902.09 | 66755 (5.61%) |

Per-year stability (ALL assets, FIRE group):

| year | fires | per session | mean close $ | cond. close $ | mean peak $ |
|---|---|---|---|---|---|
| 2021 | 5170 | 8.116 | -22.08 | 819.63 | 765.70 |
| 2021 baseline | 236757 | 371.675 | -30.14 | 594.63 | 790.41 |
| 2022 | 6899 | 8.913 | -67.20 | 1022.07 | 836.14 |
| 2022 baseline | 326945 | 422.410 | -33.41 | 663.80 | 834.00 |
| 2023 | 11139 | 14.429 | 3.21 | 934.17 | 780.63 |
| 2023 baseline | 302658 | 392.044 | -24.23 | 558.70 | 725.32 |
| 2024 | 8326 | 10.716 | -48.91 | 1288.92 | 1013.20 |
| 2024 baseline | 324374 | 417.470 | -26.95 | 783.46 | 965.09 |
| GATE_2025 (eval-only) | 8179 | 10.567 | 10.97 | 1766.20 | 1246.49 |
| GATE_2025 baseline | 349913 | 452.084 | -28.63 | 1046.94 | 1203.62 |

Co-occurrence break-out (FIT, FIRE group) — the E1 note flagged P001's support set as all-HG / all-NY / all-SHORT, and P016's name carries NY/SHORT too; neither is a term here, so these strata are what breaks the co-occurrence apart:

| stratum | fires | mean close $ | cond. close $ | baseline mean $ |
|---|---|---|---|---|
| ALL / ALL / LONG | 16074 | 5.52 | 1010.13 | -28.02 |
| ALL / ALL / SHORT | 15460 | -67.14 | 1021.08 | -29.31 |
| ALL / NY / ALL | 31534 | -30.10 | 1015.23 | -24.76 |
| HG / ALL / ALL | 11801 | -6.52 | 759.61 | -28.42 |
| HG / ALL / LONG | 5994 | 3.66 | 761.56 | -37.43 |
| HG / ALL / SHORT | 5807 | -17.02 | 757.56 | -19.40 |
| HG / NY / ALL | 11801 | -6.52 | 759.61 | -34.69 |
| NKD / ALL / ALL | 5084 | -70.03 | 882.06 | -46.28 |
| NKD / ALL / LONG | 2625 | 20.20 | 798.65 | -33.35 |
| NKD / ALL / SHORT | 2459 | -166.36 | 1013.09 | -59.49 |
| NKD / NY / ALL | 5084 | -70.03 | 882.06 | -47.93 |
| SI / ALL / ALL | 14649 | -35.24 | 1322.63 | -11.14 |
| SI / ALL / LONG | 7455 | 1.85 | 1346.87 | -12.88 |
| SI / ALL / SHORT | 7194 | -73.68 | 1295.65 | -9.39 |
| SI / NY / ALL | 14649 | -35.24 | 1322.63 | -2.02 |

Mechanism destruction (FIT, ALL assets; each term shuffled within its session, 40 replicates). EDGE = mean close of the firing set minus mean close of the non-firing rest; `retention` = destroyed edge / intact edge. High retention means the term was not carrying the value. Intact edge = $-1.44 (close), $18.31 (peak).

| neutralised term | fires (mean) | mean close $ | edge close $ | retention close | retention peak | verdict |
|---|---|---|---|---|---|---|
| T1_coverage | 16981.7 | -44.25 | -15.76 | 10.973 | -2.789 | VOID_no_intact_edge |
| T2_ladder | 17972.2 | -49.60 | -21.21 | 14.766 | -2.904 | VOID_no_intact_edge |
| T3_runway | 15161.6 | -25.32 | 3.43 | -2.386 | 2.503 | VOID_no_intact_edge |
| T4_age | 21449.0 | -21.98 | 6.84 | -4.761 | 3.343 | VOID_no_intact_edge |
| T5_slope | 22378.0 | -24.74 | 4.04 | -2.812 | 2.428 | VOID_no_intact_edge |

Cluster-robust inference (CC-M1-12.4; GEE identity link, Liang-Zeger sandwich clustered on SESSION, CR1 scaling):

| asset | era | metric | beta $ | se naive | se CR1 | z | p | DEFF | n_eff | raw verdict | Holm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | FIT | cert_close | -1.44 | 4.80 | 15.31 | -0.09 | 0.92524 | 10.24 | 119357.4 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| ALL | FIT | cert_peak | 18.31 | 5.91 | 12.91 | 1.42 | 0.15604 | 45.11 | 27092.3 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| ALL | GATE_2025 | cert_close | 39.60 | 15.31 | 45.98 | 0.86 | 0.38911 | 13.87 | 25826.2 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| ALL | GATE_2025 | cert_peak | 42.87 | 22.64 | 53.35 | 0.80 | 0.42165 | 42.21 | 8484.1 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| SI | FIT | cert_close | -24.10 | 8.35 | 28.47 | -0.85 | 0.39732 | 15.64 | 25919.5 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| SI | FIT | cert_peak | 45.66 | 9.90 | 22.70 | 2.01 | 0.04433 | 40.50 | 10012.1 | SIGNIFICANT_p<0.05 | HOLM_NOT_SIGNIFICANT |
| SI | GATE_2025 | cert_close | 87.06 | 27.59 | 68.17 | 1.28 | 0.20158 | 14.85 | 9001.4 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| SI | GATE_2025 | cert_peak | -109.09 | 43.26 | 95.03 | -1.15 | 0.25098 | 37.87 | 3530.7 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | FIT | cert_close | 21.90 | 6.20 | 16.06 | 1.36 | 0.17277 | 5.25 | 79420.9 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | FIT | cert_peak | -18.94 | 7.79 | 14.21 | -1.33 | 0.18261 | 45.00 | 9273.3 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | GATE_2025 | cert_close | 72.74 | 21.56 | 76.70 | 0.95 | 0.34295 | 10.18 | 11025.0 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | GATE_2025 | cert_peak | 173.16 | 28.93 | 76.57 | 2.26 | 0.02372 | 39.40 | 2848.5 | SIGNIFICANT_p<0.05 | HOLM_NOT_SIGNIFICANT |
| NKD | FIT | cert_close | -23.75 | 11.89 | 25.73 | -0.92 | 0.35592 | 6.61 | 60412.8 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | FIT | cert_peak | -78.95 | 14.90 | 18.81 | -4.20 | 0.00003 | 41.24 | 9688.5 | SIGNIFICANT_p<0.05 | HOLM_SIGNIFICANT |
| NKD | GATE_2025 | cert_close | -77.29 | 26.82 | 95.53 | -0.81 | 0.41851 | 15.93 | 7040.7 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | GATE_2025 | cert_peak | -6.99 | 34.96 | 94.17 | -0.07 | 0.94080 | 40.35 | 2780.1 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |

Term marginals (FIT, ALL assets):

| term | alone: n / mean close $ | detector without it: n / mean close $ | near-miss (only this fails): n / mean close $ |
|---|---|---|---|
| T1_coverage | 503892 / -28.53 | 34396 / -27.89 | 2862 / -3.56 |
| T2_ladder | 561021 / -28.68 | 31788 / -29.26 | 254 / 75.68 |
| T3_runway | 219064 / -24.03 | 80073 / -24.94 | 48539 / -21.59 |
| T4_age | 464952 / -23.34 | 58878 / -33.41 | 27344 / -37.23 |
| T5_slope | 431709 / -27.08 | 62114 / -27.34 | 30580 / -24.48 |

## ARM P016 — P016 NY_SHORT_ROLLOVER_CONCORDANT (P001's successor)

| | fires | per session | mean close $ | cond. close $ | mean peak $ | cond. peak $ | winners |
|---|---|---|---|---|---|---|---|
| FIRE | 10797 | 3.648 | -123.21 | 905.67 | 754.85 | 817.81 | 909 (8.42%) |
| NOFIRE | 1211471 | 409.281 | -27.86 | 660.72 | 834.60 | 903.09 | 68771 (5.68%) |

Per-year stability (ALL assets, FIRE group):

| year | fires | per session | mean close $ | cond. close $ | mean peak $ |
|---|---|---|---|---|---|
| 2021 | 1462 | 2.295 | -131.10 | 716.87 | 677.58 |
| 2021 baseline | 240465 | 377.496 | -29.35 | 598.87 | 790.57 |
| 2022 | 3423 | 4.422 | -143.35 | 1227.98 | 789.33 |
| 2022 baseline | 330421 | 426.901 | -32.97 | 666.27 | 834.50 |
| 2023 | 3257 | 4.219 | -15.70 | 700.41 | 697.79 |
| 2023 baseline | 310540 | 402.254 | -23.34 | 570.13 | 727.59 |
| 2024 | 2655 | 3.417 | -224.80 | 977.71 | 822.94 |
| 2024 baseline | 330045 | 424.768 | -25.91 | 793.26 | 967.45 |
| GATE_2025 (eval-only) | 3968 | 5.127 | 40.91 | 1468.88 | 1225.82 |
| GATE_2025 baseline | 354124 | 457.525 | -28.50 | 1056.63 | 1204.36 |

Co-occurrence break-out (FIT, FIRE group) — the E1 note flagged P001's support set as all-HG / all-NY / all-SHORT, and P016's name carries NY/SHORT too; neither is a term here, so these strata are what breaks the co-occurrence apart:

| stratum | fires | mean close $ | cond. close $ | baseline mean $ |
|---|---|---|---|---|
| ALL / ALL / LONG | 4787 | -40.82 | 941.01 | -27.04 |
| ALL / ALL / SHORT | 6010 | -188.84 | 869.95 | -28.69 |
| ALL / NY / ALL | 10797 | -123.21 | 905.67 | -23.40 |
| HG / ALL / ALL | 4086 | -78.59 | 746.23 | -27.30 |
| HG / ALL / LONG | 1622 | 43.79 | 780.42 | -36.88 |
| HG / ALL / SHORT | 2464 | -159.14 | 714.27 | -17.66 |
| HG / NY / ALL | 4086 | -78.59 | 746.23 | -32.41 |
| NKD / ALL / ALL | 1735 | -32.33 | 1179.81 | -46.65 |
| NKD / ALL / LONG | 1042 | 57.84 | 1327.83 | -33.13 |
| NKD / ALL / SHORT | 693 | -167.90 | 899.45 | -60.44 |
| NKD / NY / ALL | 1735 | -32.33 | 1179.81 | -48.78 |
| SI / ALL / ALL | 4976 | -191.55 | 961.10 | -9.78 |
| SI / ALL / LONG | 2123 | -153.89 | 891.72 | -10.85 |
| SI / ALL / SHORT | 2853 | -219.57 | 1020.25 | -8.70 |
| SI / NY / ALL | 4976 | -191.55 | 961.10 | -0.32 |

Mechanism destruction (FIT, ALL assets; each term shuffled within its session, 40 replicates). EDGE = mean close of the firing set minus mean close of the non-firing rest; `retention` = destroyed edge / intact edge. High retention means the term was not carrying the value. Intact edge = $-95.35 (close), $-79.75 (peak).

| neutralised term | fires (mean) | mean close $ | edge close $ | retention close | retention peak | verdict |
|---|---|---|---|---|---|---|
| X1_extension | 18177.3 | -120.52 | -93.21 | 0.977 | 0.430 | VOID_no_intact_edge |
| X2_runway | 8642.0 | -80.72 | -52.39 | 0.549 | 0.558 | VOID_no_intact_edge |
| X3_book | 9491.9 | -136.15 | -108.29 | 1.136 | 1.089 | VOID_no_intact_edge |
| X4_flow_concord | 19253.6 | -32.94 | -4.31 | 0.045 | 0.971 | VOID_no_intact_edge |
| X5_vol_alive | 10319.9 | -118.62 | -90.68 | 0.951 | 0.936 | VOID_no_intact_edge |

Cluster-robust inference (CC-M1-12.4; GEE identity link, Liang-Zeger sandwich clustered on SESSION, CR1 scaling):

| asset | era | metric | beta $ | se naive | se CR1 | z | p | DEFF | n_eff | raw verdict | Holm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | FIT | cert_close | -95.35 | 8.14 | 53.37 | -1.79 | 0.07401 | 10.24 | 119357.4 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| ALL | FIT | cert_peak | -79.75 | 10.01 | 42.40 | -1.88 | 0.06001 | 45.11 | 27092.3 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| ALL | GATE_2025 | cert_close | 69.40 | 21.85 | 149.04 | 0.47 | 0.64146 | 13.87 | 25826.2 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| ALL | GATE_2025 | cert_peak | 21.45 | 32.32 | 132.33 | 0.16 | 0.87121 | 42.21 | 8484.1 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| SI | FIT | cert_close | -181.77 | 14.14 | 77.38 | -2.35 | 0.01882 | 15.64 | 25919.5 | SIGNIFICANT_p<0.05 | HOLM_NOT_SIGNIFICANT |
| SI | FIT | cert_peak | -170.42 | 16.78 | 63.40 | -2.69 | 0.00719 | 40.50 | 10012.1 | SIGNIFICANT_p<0.05 | HOLM_NOT_SIGNIFICANT |
| SI | GATE_2025 | cert_close | -189.52 | 45.77 | 180.45 | -1.05 | 0.29361 | 14.85 | 9001.4 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| SI | GATE_2025 | cert_peak | -406.85 | 71.76 | 155.26 | -2.62 | 0.00878 | 37.87 | 3530.7 | SIGNIFICANT_p<0.05 | HOLM_NOT_SIGNIFICANT |
| HG | FIT | cert_close | -51.29 | 10.43 | 81.67 | -0.63 | 0.52996 | 5.25 | 79420.9 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | FIT | cert_peak | -78.44 | 13.12 | 62.57 | -1.25 | 0.20998 | 45.00 | 9273.3 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | GATE_2025 | cert_close | 380.70 | 22.89 | 285.23 | 1.33 | 0.18196 | 10.18 | 11025.0 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | GATE_2025 | cert_peak | 445.24 | 30.73 | 243.40 | 1.83 | 0.06736 | 39.40 | 2848.5 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | FIT | cert_close | 14.32 | 20.26 | 150.94 | 0.09 | 0.92442 | 6.61 | 60412.8 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | FIT | cert_peak | 75.27 | 25.39 | 114.65 | 0.66 | 0.51152 | 41.24 | 9688.5 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | GATE_2025 | cert_close | -135.68 | 43.87 | 220.24 | -0.62 | 0.53786 | 15.93 | 7040.7 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | GATE_2025 | cert_peak | 18.12 | 57.18 | 241.49 | 0.08 | 0.94017 | 40.35 | 2780.1 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |

Term marginals (FIT, ALL assets):

| term | alone: n / mean close $ | detector without it: n / mean close $ | near-miss (only this fails): n / mean close $ |
|---|---|---|---|
| X1_extension | 533348 / -33.19 | 42539 / -90.16 | 31742 / -78.92 |
| X2_runway | 387101 / -25.40 | 26860 / -50.66 | 16063 / -1.89 |
| X3_book | 829618 / -23.07 | 13572 / -116.16 | 2775 / -88.70 |
| X4_flow_concord | 205699 / -50.52 | 134867 / -21.35 | 124070 / -12.49 |
| X5_vol_alive | 1079004 / -29.02 | 11712 / -119.94 | 915 / -81.36 |

## REFUSED-FVOL CENSUS (CC-M2-8.4) — the size of the ladder hole

A REFUSED S9 ladder is not a missing number, it is a term that cannot fire: any pattern with a ladder or COVERAGE clause is structurally blind on those candidates. Row grain = fvol forecast rows (session x segment); candidate grain = decisions. Note the two are different questions — the ATR14 FALLBACK is common (a fifth of rows) and mostly still carries quantiles; only the no-move_q* rows refuse.

| asset | era | fvol rows | no move_q* | % | ATR fallback % | sessions with a refused segment % | candidates | ladder REFUSED % | COVERAGE REFUSED % |
|---|---|---|---|---|---|---|---|---|---|
| ALL | 2021 | 2548 | 360 | 14.13 | 100.00 | 14.13 | 241927 | 15.21 | 15.21 |
| ALL | 2022 | 3096 | 0 | 0.00 | 21.96 | 0.00 | 333844 | 0.00 | 0.00 |
| ALL | 2023 | 3088 | 0 | 0.00 | 0.00 | 0.00 | 313797 | 0.00 | 0.00 |
| ALL | 2024 | 3108 | 0 | 0.00 | 0.00 | 0.00 | 332700 | 0.00 | 0.00 |
| ALL | 2025 | 3093 | 0 | 0.00 | 0.00 | 0.00 | 358092 | 0.00 | 0.00 |
| ALL | ALL | 29866 | 720 | 2.41 | 21.62 | 2.41 | 1580360 | 2.33 | 2.33 |
| ALL | FIT | 11840 | 360 | 3.04 | 27.26 | 3.04 | 1222268 | 3.01 | 3.01 |
| ALL | GATE_2025 | 3093 | 0 | 0.00 | 0.00 | 0.00 | 358092 | 0.00 | 0.00 |
| HG | 2021 | 988 | 120 | 12.15 | 100.00 | 12.15 | 93993 | 15.18 | 15.18 |
| HG | 2022 | 1032 | 0 | 0.00 | 8.14 | 0.00 | 110802 | 0.00 | 0.00 |
| HG | 2023 | 1028 | 0 | 0.00 | 0.00 | 0.00 | 105361 | 0.00 | 0.00 |
| HG | 2024 | 1036 | 0 | 0.00 | 0.00 | 0.00 | 107109 | 0.00 | 0.00 |
| HG | 2025 | 1031 | 0 | 0.00 | 0.00 | 0.00 | 112227 | 0.00 | 0.00 |
| HG | ALL | 10230 | 240 | 2.35 | 20.96 | 2.35 | 529492 | 2.70 | 2.70 |
| HG | FIT | 4084 | 120 | 2.94 | 26.25 | 2.94 | 417265 | 3.42 | 3.42 |
| HG | GATE_2025 | 1031 | 0 | 0.00 | 0.00 | 0.00 | 112227 | 0.00 | 0.00 |
| NKD | 2021 | 992 | 120 | 12.10 | 100.00 | 12.10 | 92439 | 10.98 | 10.98 |
| NKD | 2022 | 1032 | 0 | 0.00 | 8.14 | 0.00 | 107609 | 0.00 | 0.00 |
| NKD | 2023 | 1032 | 0 | 0.00 | 0.00 | 0.00 | 93616 | 0.00 | 0.00 |
| NKD | 2024 | 1036 | 0 | 0.00 | 0.00 | 0.00 | 105862 | 0.00 | 0.00 |
| NKD | 2025 | 1031 | 0 | 0.00 | 0.00 | 0.00 | 112168 | 0.00 | 0.00 |
| NKD | ALL | 10246 | 240 | 2.34 | 21.00 | 2.34 | 511694 | 1.98 | 1.98 |
| NKD | FIT | 4092 | 120 | 2.93 | 26.30 | 2.93 | 399526 | 2.54 | 2.54 |
| NKD | GATE_2025 | 1031 | 0 | 0.00 | 0.00 | 0.00 | 112168 | 0.00 | 0.00 |
| SI | 2021 | 568 | 120 | 21.13 | 100.00 | 21.13 | 55495 | 22.32 | 22.32 |
| SI | 2022 | 1032 | 0 | 0.00 | 49.61 | 0.00 | 115433 | 0.00 | 0.00 |
| SI | 2023 | 1028 | 0 | 0.00 | 0.00 | 0.00 | 114820 | 0.00 | 0.00 |
| SI | 2024 | 1036 | 0 | 0.00 | 0.00 | 0.00 | 119729 | 0.00 | 0.00 |
| SI | 2025 | 1031 | 0 | 0.00 | 0.00 | 0.00 | 133697 | 0.00 | 0.00 |
| SI | ALL | 9390 | 240 | 2.56 | 23.00 | 2.56 | 539174 | 2.30 | 2.30 |
| SI | FIT | 3664 | 120 | 3.28 | 29.48 | 3.28 | 405477 | 3.06 | 3.06 |
| SI | GATE_2025 | 1031 | 0 | 0.00 | 0.00 | 0.00 | 133697 | 0.00 | 0.00 |

## Support-set check (the 3 P001 PATTERN_LEDGER cases)

| case | arm A | arm B | arm P016 | cert close $ |
|---|---|---|---|---|
| HG-20210701-052246-S | True | True | True | 1320.00 |
| HG-20210701-055858-S | True | True | True | 1682.50 |
| HG-20210929-052330-S | False | True | False | 1670.00 |

## Provenance

* engine: `engine/port_m2/p001_census.py` + `engine/port_m2/pattern_lib.py`
* red-first mutants: `engine/port_m2/test_pattern.py` (artifacts/cache/port/m2/tests/pattern_red_ledger.tsv)
* runtime 122.1s; pins HELD
* params_hash `f8d2e2eef007828e5d81c51f4c82166ffb88932cf6c0edb03aeefc970874056e`


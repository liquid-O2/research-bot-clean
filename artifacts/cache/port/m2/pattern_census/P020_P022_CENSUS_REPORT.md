# CENSUS BATCH 2 — P020 / P021 / P022 name->count censuses

Ordered by CC-M2-10.2. Population: the frozen v3 roster, 1580360 candidates over 3734 sessions (FIT 2021-2024 + the 2025 GATE echo, eval-only), all three assets. Detectors are strictly causal and read only committed pattern_lib frame fields.

MULTIPLICITY: every GEE test of all three patterns AND both P021 interaction readings is corrected Holm-Bonferroni as ONE family (64 tests). A raw p<0.05 that fails Holm is noise and the tables say which is which.

## HEADLINE VERDICTS (CC-M2-9.1 vocabulary)

* **P020 NY_PHASE_CONCENTRATION** — fires on 669979 of 1222268 FIT candidates (54.81%). ADOPTION METRIC (walled phase-close): mean $-25.01 for the firing set vs $-33.18 for the rest, session-clustered difference $8.16 (CR1 se $5.83, p=0.16173, HOLM_NOT_SIGNIFICANT). PEAK-EXIT companion: $-367.72 (p=0.00000). CONDITIONAL value $771.37 vs $534.65 = 1.44x. D-021 winner rate 7.17% vs 3.92% = 1.83x. **VERDICT: WINNER CONCENTRATOR (feature candidate set only — CC-M2-9.1 disposition)**
* **P021 REGIME_CONDITIONAL_CAPACITY** — fires on 278924 of 1222268 FIT candidates (22.82%). ADOPTION METRIC (walled phase-close): mean $-27.64 for the firing set vs $-29.02 for the rest, session-clustered difference $1.38 (CR1 se $7.51, p=0.85425, HOLM_NOT_SIGNIFICANT). PEAK-EXIT companion: $5.29 (p=0.79192). CONDITIONAL value $637.40 vs $669.92 = 0.95x. D-021 winner rate 5.23% vs 5.84% = 0.90x. **VERDICT: NULL (no adoption edge, no concentration)**
* **P022 FLOW_HORIZON_DISAGREEMENT** — fires on 8564 of 1222268 FIT candidates (0.70%). ADOPTION METRIC (walled phase-close): mean $-61.29 for the firing set vs $-28.47 for the rest, session-clustered difference $-32.81 (CR1 se $30.31, p=0.27890, HOLM_NOT_SIGNIFICANT). PEAK-EXIT companion: $-0.50 (p=0.98416). CONDITIONAL value $1025.26 vs $660.23 = 1.55x. D-021 winner rate 10.08% vs 5.67% = 1.78x. **VERDICT: WINNER CONCENTRATOR (feature candidate set only — CC-M2-9.1 disposition)**

## P020 NY_PHASE_CONCENTRATION — the base-rate census

The ledger's own instruction: 'winner rate by (phase_dec, asset) over the whole era, and check it is not an artefact of where candidates are generated'. `conc_ratio` is that check: winners' share of a phase divided by candidates' share of it. 1.00 = the phase holds winners in exact proportion to the candidates generated inside it.

| asset | era | phase | candidates | cand share | winners | winner share | conc_ratio | winner rate % | mean close $ | cond close $ |
|---|---|---|---|---|---|---|---|---|---|---|
| ALL | FIT | TOKYO | 337513 | 0.2761 | 15754 | 0.2261 | 0.819 | 4.668 | -34.72 | 607.71 |
| ALL | FIT | LONDON | 214776 | 0.1757 | 5916 | 0.0849 | 0.483 | 2.754 | -30.75 | 422.94 |
| ALL | FIT | NY | 669979 | 0.5481 | 48010 | 0.6890 | 1.257 | 7.166 | -25.01 | 771.37 |
| ALL | GATE_2025 | TOKYO | 110168 | 0.3077 | 5925 | 0.2556 | 0.831 | 5.378 | -39.23 | 996.23 |
| ALL | GATE_2025 | LONDON | 54157 | 0.1512 | 1981 | 0.0854 | 0.565 | 3.658 | -39.12 | 632.12 |
| ALL | GATE_2025 | NY | 193767 | 0.5411 | 15279 | 0.6590 | 1.218 | 7.885 | -18.00 | 1240.06 |
| SI | FIT | TOKYO | 64011 | 0.1579 | 2210 | 0.0764 | 0.484 | 3.453 | -32.18 | 581.11 |
| SI | FIT | LONDON | 66992 | 0.1652 | 2119 | 0.0733 | 0.444 | 3.163 | -26.43 | 474.55 |
| SI | FIT | NY | 274474 | 0.6769 | 24583 | 0.8503 | 1.256 | 8.956 | -3.79 | 1013.63 |
| SI | GATE_2025 | TOKYO | 33909 | 0.2536 | 1526 | 0.1679 | 0.662 | 4.500 | -22.01 | 1331.58 |
| SI | GATE_2025 | LONDON | 19911 | 0.1489 | 767 | 0.0844 | 0.567 | 3.852 | -50.50 | 805.57 |
| SI | GATE_2025 | NY | 79877 | 0.5974 | 6798 | 0.7478 | 1.252 | 8.511 | -8.65 | 1690.41 |
| HG | FIT | TOKYO | 101153 | 0.2424 | 3153 | 0.1694 | 0.699 | 3.117 | -25.87 | 443.80 |
| HG | FIT | LONDON | 88009 | 0.2109 | 2510 | 0.1348 | 0.639 | 2.852 | -15.93 | 407.92 |
| HG | FIT | NY | 228103 | 0.5467 | 12951 | 0.6958 | 1.273 | 5.678 | -33.24 | 575.92 |
| HG | GATE_2025 | TOKYO | 28520 | 0.2541 | 1137 | 0.1700 | 0.669 | 3.987 | -33.69 | 629.97 |
| HG | GATE_2025 | LONDON | 21027 | 0.1874 | 657 | 0.0983 | 0.524 | 3.125 | -42.61 | 451.16 |
| HG | GATE_2025 | NY | 62680 | 0.5585 | 4893 | 0.7317 | 1.310 | 7.806 | -16.61 | 867.81 |
| NKD | FIT | TOKYO | 172349 | 0.4314 | 10391 | 0.4690 | 1.087 | 6.029 | -40.87 | 722.55 |
| NKD | FIT | LONDON | 59775 | 0.1496 | 1287 | 0.0581 | 0.388 | 2.153 | -57.41 | 385.14 |
| NKD | FIT | NY | 167402 | 0.4190 | 10476 | 0.4729 | 1.129 | 6.258 | -48.60 | 671.59 |
| NKD | GATE_2025 | TOKYO | 47739 | 0.4256 | 3262 | 0.4404 | 1.035 | 6.833 | -54.78 | 1025.31 |
| NKD | GATE_2025 | LONDON | 13219 | 0.1179 | 557 | 0.0752 | 0.638 | 4.214 | -16.44 | 687.82 |
| NKD | GATE_2025 | NY | 51210 | 0.4565 | 3588 | 0.4844 | 1.061 | 7.006 | -34.29 | 1140.89 |

Per-year stability of the NY concentration ratio (ALL assets):

| year | NY candidates | NY cand share | NY winners | NY winner share | conc_ratio | NY winner rate % |
|---|---|---|---|---|---|---|
| 2021 | 122400 | 0.5059 | 8448 | 0.6462 | 1.277 | 6.902 |
| 2022 | 191433 | 0.5734 | 14808 | 0.7338 | 1.280 | 7.735 |
| 2023 | 176759 | 0.5633 | 11150 | 0.7160 | 1.271 | 6.308 |
| 2024 | 179387 | 0.5392 | 13604 | 0.6523 | 1.210 | 7.584 |
| GATE_2025 (eval-only) | 193767 | 0.5411 | 15279 | 0.6590 | 1.218 | 7.885 |

Side and class break-out (FIT, ALL assets, NY phase) — the E1D2 finding was that the SIDE term is a session property and must never be encoded, while the PHASE term is 86-for-86; these rows are that claim at era scale:

| stratum | candidates | conc_ratio | winner rate % | base rate % | lift | mean close $ |
|---|---|---|---|---|---|---|
| SIDE LONG | 337169 | 1.288 | 7.220 | 5.607 | 1.29 | -14.08 |
| SIDE SHORT | 332810 | 1.227 | 7.111 | 5.795 | 1.23 | -36.09 |
| CLASS LEVEL-FIRST-TEST | 332 | 0.461 | 3.012 | 6.537 | 0.46 | -100.97 |
| CLASS NEWS-WINDOW | 44520 | 1.000 | 9.335 | 9.335 | 1.00 | -9.17 |
| CLASS OPEN-DYNAMICS | 15370 | 1.256 | 9.083 | 7.231 | 1.26 | -25.69 |
| CLASS RECLAIM | 30317 | 1.206 | 7.507 | 6.224 | 1.21 | -42.60 |
| CLASS REVERSAL-CONFIRMATION | 578846 | 1.263 | 6.931 | 5.486 | 1.26 | -25.21 |
| CLASS SHOCK-RESOLUTION | 594 | 1.228 | 8.754 | 7.128 | 1.23 | -58.43 |

## P021 REGIME_CONDITIONAL_CAPACITY — the interaction is the point

THE CLAIM UNDER TEST (E1_POSTMORTEMS §3): on EXPANSION-flagged candidates, BREAKOUT-direction entries outperform REVERSION-direction entries; on non-flagged candidates the ordering reverses. Two readings of direction (A = side equals the range-extension side; B = P017's own ext_needed > $450). The 2x2 is the evidence; the difference in differences is the test.

### direction reading A_extension_side (FIT, ALL assets)

| flag | direction | n | mean close $ | cond close $ | mean peak $ | winners | winner rate % |
|---|---|---|---|---|---|---|---|
| FLAGGED | BREAKOUT | 130804 | -29.46 | 633.14 | 840.23 | 6617 | 5.059 |
| FLAGGED | REVERSION | 148120 | -26.02 | 641.13 | 835.98 | 7969 | 5.380 |
| UNFLAGGED | BREAKOUT | 444514 | -22.15 | 672.96 | 836.25 | 26051 | 5.861 |
| UNFLAGGED | REVERSION | 498732 | -35.10 | 667.18 | 829.54 | 29036 | 5.822 |
| UNFLAGGED | NO_DIRECTION | 98 | -206.02 | 654.07 | 661.65 | 7 | 7.143 |

breakout - reversion, FLAGGED: **$-3.44**; UNFLAGGED: **$12.95**; difference in differences: **$-16.39**.

### direction reading B_ext_needed (FIT, ALL assets)

| flag | direction | n | mean close $ | cond close $ | mean peak $ | winners | winner rate % |
|---|---|---|---|---|---|---|---|
| FLAGGED | BREAKOUT | 85774 | -15.01 | 579.88 | 829.33 | 4031 | 4.700 |
| FLAGGED | REVERSION | 193150 | -33.24 | 663.34 | 841.82 | 10555 | 5.465 |
| UNFLAGGED | BREAKOUT | 602687 | -26.70 | 643.89 | 835.10 | 33894 | 5.624 |
| UNFLAGGED | REVERSION | 340633 | -33.09 | 717.15 | 828.42 | 21200 | 6.224 |
| UNFLAGGED | NO_DIRECTION | 24 | -323.75 | 409.06 | 646.82 | 0 | 0.000 |

breakout - reversion, FLAGGED: **$18.23**; UNFLAGGED: **$6.38**; difference in differences: **$11.85**.

WHEN THE FLAG FIRES (FIT, session clock in seconds from the session open): median decision second of FLAGGED candidates 56120 vs UNFLAGGED 49474; median decision second of all D-021 WINNERS 52780, and of the winners the flag covers 57881. A conditioner that only prints EXPANDED after the day has expanded arrives LATE by construction, which is the mechanism behind the interaction result below.

Difference-in-differences, session-clustered (CR1), FIT only. beta = the INTERACTION coefficient: the extra dollars a breakout-direction entry is worth on an EXPANSION-flagged candidate over an unflagged one.

| test | asset | metric | n | beta $ | se CR1 | z | p | DEFF | n_eff | raw | Holm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P021_DID_A | ALL | cert_close | 1222170 | -16.39 | 32.29 | -0.51 | 0.61174 | 10.24 | 119337.2 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| P021_DID_A | ALL | cert_peak | 1222170 | -2.47 | 33.83 | -0.07 | 0.94190 | 45.11 | 27091.6 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| P021_DID_A | SI | cert_close | 405445 | -10.20 | 69.70 | -0.15 | 0.88364 | 15.64 | 25916.6 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| P021_DID_A | SI | cert_peak | 405445 | -38.53 | 64.71 | -0.60 | 0.55162 | 40.50 | 10011.6 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| P021_DID_A | HG | cert_close | 417243 | -19.17 | 46.79 | -0.41 | 0.68198 | 5.26 | 79384.7 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| P021_DID_A | HG | cert_peak | 417243 | -30.29 | 50.10 | -0.60 | 0.54550 | 44.99 | 9274.3 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| P021_DID_A | NKD | cert_close | 399482 | -20.23 | 48.53 | -0.42 | 0.67678 | 6.61 | 60397.6 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| P021_DID_A | NKD | cert_peak | 399482 | 43.68 | 57.90 | 0.75 | 0.45066 | 41.24 | 9687.8 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| P021_DID_B | ALL | cert_close | 1222244 | 11.85 | 21.96 | 0.54 | 0.58949 | 10.24 | 119349.6 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| P021_DID_B | ALL | cert_peak | 1222244 | -19.16 | 27.61 | -0.69 | 0.48756 | 45.11 | 27092.1 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| P021_DID_B | SI | cert_close | 405469 | 56.55 | 47.97 | 1.18 | 0.23846 | 15.64 | 25918.4 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| P021_DID_B | SI | cert_peak | 405469 | -90.32 | 47.74 | -1.89 | 0.05850 | 40.50 | 10012.0 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| P021_DID_B | HG | cert_close | 417254 | 11.78 | 35.49 | 0.33 | 0.73996 | 5.26 | 79393.0 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| P021_DID_B | HG | cert_peak | 417254 | -13.09 | 42.00 | -0.31 | 0.75530 | 44.99 | 9274.3 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| P021_DID_B | NKD | cert_close | 399521 | -25.36 | 31.01 | -0.82 | 0.41350 | 6.61 | 60412.8 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| P021_DID_B | NKD | cert_peak | 399521 | 19.82 | 49.68 | 0.40 | 0.68990 | 41.24 | 9687.7 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |

## P022 FLOW_HORIZON_DISAGREEMENT — veto or compass?

Among FLAGGED candidates the phase window and the short windows point opposite ways by construction, so every flagged candidate is aligned with exactly one of them. If the short windows are the live market, the LIVE-aligned half beats the FOSSIL-aligned half. The D10 EVENT-ANCHORED window (flow since the release, never across it) is the third reading.

| window | alignment | side | n | mean close $ | cond close $ | mean peak $ | winners | winner rate % |
|---|---|---|---|---|---|---|---|---|
| 5m | ALIGNED | ALL | 4455 | -79.62 | 1028.00 | 837.93 | 426 | 9.562 |
| 5m | ALIGNED | LONG | 2419 | -69.71 | 983.42 | 890.92 | 227 | 9.384 |
| 5m | ALIGNED | SHORT | 2036 | -91.40 | 1087.67 | 774.97 | 199 | 9.774 |
| 5m | OPPOSED | ALL | 4109 | -41.41 | 1022.47 | 828.47 | 437 | 10.635 |
| 5m | OPPOSED | LONG | 1915 | 23.20 | 972.27 | 874.80 | 208 | 10.862 |
| 5m | OPPOSED | SHORT | 2194 | -97.80 | 1075.43 | 788.02 | 229 | 10.438 |
| 30m | ALIGNED | ALL | 4455 | -79.62 | 1028.00 | 837.93 | 426 | 9.562 |
| 30m | ALIGNED | LONG | 2419 | -69.71 | 983.42 | 890.92 | 227 | 9.384 |
| 30m | ALIGNED | SHORT | 2036 | -91.40 | 1087.67 | 774.97 | 199 | 9.774 |
| 30m | OPPOSED | ALL | 4109 | -41.41 | 1022.47 | 828.47 | 437 | 10.635 |
| 30m | OPPOSED | LONG | 1915 | 23.20 | 972.27 | 874.80 | 208 | 10.862 |
| 30m | OPPOSED | SHORT | 2194 | -97.80 | 1075.43 | 788.02 | 229 | 10.438 |
| phase | ALIGNED | ALL | 4109 | -41.41 | 1022.47 | 828.47 | 437 | 10.635 |
| phase | ALIGNED | LONG | 1915 | 23.20 | 972.27 | 874.80 | 208 | 10.862 |
| phase | ALIGNED | SHORT | 2194 | -97.80 | 1075.43 | 788.02 | 229 | 10.438 |
| phase | OPPOSED | ALL | 4455 | -79.62 | 1028.00 | 837.93 | 426 | 9.562 |
| phase | OPPOSED | LONG | 2419 | -69.71 | 983.42 | 890.92 | 227 | 9.384 |
| phase | OPPOSED | SHORT | 2036 | -91.40 | 1087.67 | 774.97 | 199 | 9.774 |
| event_anchored | ALIGNED | ALL | 4193 | -33.77 | 1039.29 | 859.77 | 457 | 10.899 |
| event_anchored | ALIGNED | LONG | 2176 | -15.96 | 977.54 | 904.79 | 238 | 10.938 |
| event_anchored | ALIGNED | SHORT | 2017 | -52.98 | 1111.83 | 811.20 | 219 | 10.858 |
| event_anchored | OPPOSED | ALL | 4337 | -88.75 | 1015.63 | 809.26 | 404 | 9.315 |
| event_anchored | OPPOSED | LONG | 2138 | -43.99 | 981.89 | 863.47 | 195 | 9.121 |
| event_anchored | OPPOSED | SHORT | 2199 | -132.27 | 1056.01 | 756.56 | 209 | 9.504 |

## P020 NY_PHASE_CONCENTRATION — detail

| | fires | per session | mean close $ | cond. close $ | mean peak $ | cond. peak $ | winners |
|---|---|---|---|---|---|---|---|
| FIRE | 669979 | 226.344 | -25.01 | 771.37 | 667.73 | 728.46 | 48010 (7.166%) |
| NOFIRE | 552289 | 186.584 | -33.18 | 534.65 | 1035.46 | 1110.82 | 21670 (3.924%) |

Per-year stability (ALL assets):

| year | fires | mean close $ | cond close $ | winner rate % | baseline mean $ | baseline winner rate % |
|---|---|---|---|---|---|---|
| 2021 | 122400 | -24.60 | 687.52 | 6.902 | -35.45 | 3.870 |
| 2022 | 191433 | -32.59 | 802.28 | 7.735 | -36.14 | 3.771 |
| 2023 | 176759 | -16.37 | 679.30 | 6.308 | -32.14 | 3.228 |
| 2024 | 179387 | -25.72 | 896.71 | 7.584 | -29.58 | 4.729 |
| GATE_2025 (eval-only) | 193767 | -18.00 | 1240.06 | 7.885 | -39.20 | 4.811 |

Per-asset / per-side (FIT):

| stratum | fires | mean close $ | cond close $ | winner rate % | baseline mean $ |
|---|---|---|---|---|---|
| ALL / ALL / LONG | 337169 | -14.08 | 762.29 | 7.220 | -43.03 |
| ALL / ALL / SHORT | 332810 | -36.09 | 781.19 | 7.111 | -23.24 |
| HG / ALL / ALL | 228103 | -33.24 | 575.92 | 5.678 | -21.24 |
| HG / ALL / LONG | 114211 | -31.28 | 572.70 | 5.656 | -42.25 |
| HG / ALL / SHORT | 113892 | -35.20 | 579.21 | 5.699 | -0.21 |
| NKD / ALL / ALL | 167402 | -48.60 | 671.59 | 6.258 | -45.13 |
| NKD / ALL / LONG | 84851 | -18.98 | 649.11 | 6.167 | -42.57 |
| NKD / ALL / SHORT | 82551 | -79.05 | 698.93 | 6.351 | -47.73 |
| SI / ALL / ALL | 274474 | -3.79 | 1013.63 | 8.956 | -29.24 |
| SI / ALL / LONG | 138107 | 3.15 | 1009.22 | 9.160 | -45.00 |
| SI / ALL / SHORT | 136367 | -10.82 | 1018.31 | 8.751 | -13.47 |

Mechanism destruction (FIT, ALL assets; each term shuffled within its session, 40 replicates). EDGE = mean close of the firing set minus the non-firing rest; retention = destroyed edge / intact edge. High retention means the term was not carrying the value.

| neutralised term | fires (mean) | mean close $ | edge close $ | intact edge $ | retention close | retention peak | verdict |
|---|---|---|---|---|---|---|---|
| T1_phase_is_NY | 669979.0 | -24.94 | 8.33 | 8.16 | 1.021 | -0.086 | TERM_NOT_LOAD_BEARING |

Term marginals (FIT, ALL assets):

| term | alone: n / mean close $ | detector without it: n / mean close $ | near-miss (only this fails): n / mean close $ |
|---|---|---|---|
| T1_phase_is_NY | 669979 / -25.01 | 1222268 / -28.70 | 552289 / -33.18 |

Cluster-robust inference (GEE identity link, Liang-Zeger sandwich clustered on SESSION, CR1; Holm over the whole batch):

| asset | era | metric | beta $ | se naive | se CR1 | z | p | DEFF | n_eff | raw verdict | Holm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | FIT | cert_close | 8.16 | 1.53 | 5.83 | 1.40 | 0.16173 | 10.24 | 119357.4 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| ALL | FIT | cert_peak | -367.72 | 1.85 | 9.03 | -40.70 | 0.00000 | 45.11 | 27092.3 | SIGNIFICANT_p<0.05 | HOLM_SIGNIFICANT |
| ALL | GATE_2025 | cert_close | 21.20 | 4.59 | 23.77 | 0.89 | 0.37243 | 13.87 | 25826.2 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| ALL | GATE_2025 | cert_peak | -447.55 | 6.75 | 39.94 | -11.20 | 0.00000 | 42.21 | 8484.1 | SIGNIFICANT_p<0.05 | HOLM_SIGNIFICANT |
| SI | FIT | cert_close | 25.45 | 3.33 | 11.08 | 2.30 | 0.02168 | 15.64 | 25919.5 | SIGNIFICANT_p<0.05 | HOLM_NOT_SIGNIFICANT |
| SI | FIT | cert_peak | -415.32 | 3.90 | 18.46 | -22.50 | 0.00000 | 40.50 | 10012.1 | SIGNIFICANT_p<0.05 | HOLM_SIGNIFICANT |
| SI | GATE_2025 | cert_close | 23.90 | 9.56 | 41.98 | 0.57 | 0.56914 | 14.85 | 9001.4 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| SI | GATE_2025 | cert_peak | -599.62 | 14.90 | 96.63 | -6.21 | 0.00000 | 37.87 | 3530.7 | SIGNIFICANT_p<0.05 | HOLM_SIGNIFICANT |
| HG | FIT | cert_close | -12.00 | 2.06 | 6.00 | -2.00 | 0.04576 | 5.25 | 79420.9 | SIGNIFICANT_p<0.05 | HOLM_NOT_SIGNIFICANT |
| HG | FIT | cert_peak | -394.91 | 2.52 | 10.86 | -36.36 | 0.00000 | 45.00 | 9273.3 | SIGNIFICANT_p<0.05 | HOLM_SIGNIFICANT |
| HG | GATE_2025 | cert_close | 20.87 | 5.67 | 22.54 | 0.93 | 0.35449 | 10.18 | 11025.0 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | GATE_2025 | cert_peak | -409.01 | 7.51 | 41.94 | -9.75 | 0.00000 | 39.40 | 2848.5 | SIGNIFICANT_p<0.05 | HOLM_SIGNIFICANT |
| NKD | FIT | cert_close | -3.48 | 2.70 | 9.14 | -0.38 | 0.70361 | 6.61 | 60412.8 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | FIT | cert_peak | -427.69 | 3.32 | 12.64 | -33.83 | 0.00000 | 41.24 | 9688.5 | SIGNIFICANT_p<0.05 | HOLM_SIGNIFICANT |
| NKD | GATE_2025 | cert_close | 12.18 | 7.55 | 55.16 | 0.22 | 0.82524 | 15.93 | 7040.7 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | GATE_2025 | cert_peak | -413.45 | 9.77 | 55.50 | -7.45 | 0.00000 | 40.35 | 2780.1 | SIGNIFICANT_p<0.05 | HOLM_SIGNIFICANT |

## P021 REGIME_CONDITIONAL_CAPACITY — detail

| | fires | per session | mean close $ | cond. close $ | mean peak $ | cond. peak $ | winners |
|---|---|---|---|---|---|---|---|
| FIRE | 278924 | 94.231 | -27.64 | 637.40 | 837.98 | 917.12 | 14586 (5.229%) |
| NOFIRE | 943344 | 318.697 | -29.02 | 669.92 | 832.68 | 898.02 | 55094 (5.840%) |

Per-year stability (ALL assets):

| year | fires | mean close $ | cond close $ | winner rate % | baseline mean $ | baseline winner rate % |
|---|---|---|---|---|---|---|
| 2021 | 30563 | -27.72 | 630.36 | 5.343 | -30.29 | 5.413 |
| 2022 | 80559 | -40.80 | 585.94 | 5.349 | -31.98 | 6.266 |
| 2023 | 73182 | -18.00 | 501.74 | 4.039 | -24.86 | 5.244 |
| 2024 | 94620 | -23.86 | 798.25 | 6.011 | -28.95 | 6.370 |
| GATE_2025 (eval-only) | 116254 | -26.58 | 1062.44 | 5.869 | -28.28 | 6.766 |

Per-asset / per-side (FIT):

| stratum | fires | mean close $ | cond close $ | winner rate % | baseline mean $ |
|---|---|---|---|---|---|
| ALL / ALL / LONG | 141142 | -15.18 | 626.79 | 5.317 | -30.71 |
| ALL / ALL / SHORT | 137782 | -40.40 | 649.26 | 5.140 | -27.31 |
| ALL / LONDON / ALL | 44597 | -38.68 | 384.41 | 2.141 | -28.67 |
| ALL / NY / ALL | 155529 | -15.88 | 717.12 | 6.748 | -27.77 |
| ALL / TOKYO / ALL | 78798 | -44.60 | 625.80 | 3.980 | -31.72 |
| HG / ALL / ALL | 83567 | -34.31 | 444.01 | 3.611 | -26.17 |
| HG / ALL / LONG | 41984 | -32.50 | 440.23 | 3.466 | -37.20 |
| HG / ALL / SHORT | 41583 | -36.15 | 447.93 | 3.759 | -15.14 |
| HG / LONDON / ALL | 15074 | -14.05 | 346.32 | 2.057 | -16.32 |
| HG / NY / ALL | 48991 | -39.86 | 487.78 | 4.568 | -31.42 |
| HG / TOKYO / ALL | 19502 | -36.04 | 410.97 | 2.410 | -23.44 |
| NKD / ALL / ALL | 102903 | -46.96 | 635.30 | 4.668 | -46.46 |
| NKD / ALL / LONG | 52455 | -36.28 | 603.73 | 4.488 | -31.39 |
| NKD / ALL / SHORT | 50448 | -58.06 | 672.71 | 4.856 | -61.76 |
| NKD / LONDON / ALL | 16829 | -77.54 | 391.41 | 2.080 | -49.53 |
| NKD / NY / ALL | 42813 | -28.70 | 687.01 | 5.746 | -55.44 |
| NKD / TOKYO / ALL | 43261 | -53.13 | 677.86 | 4.609 | -36.76 |
| SI / ALL / ALL | 92454 | -0.10 | 824.72 | 7.316 | -15.53 |
| SI / ALL / LONG | 46703 | 24.10 | 823.34 | 7.912 | -23.19 |
| SI / ALL / SHORT | 45751 | -24.79 | 826.28 | 6.708 | -7.83 |
| SI / LONDON / ALL | 12694 | -16.42 | 421.58 | 2.324 | -28.77 |
| SI / NY / ALL | 63725 | 11.18 | 923.92 | 9.097 | -8.31 |
| SI / TOKYO / ALL | 16035 | -31.97 | 771.40 | 4.191 | -32.25 |

Mechanism destruction (FIT, ALL assets; each term shuffled within its session, 40 replicates). EDGE = mean close of the firing set minus the non-firing rest; retention = destroyed edge / intact edge. High retention means the term was not carrying the value.

| neutralised term | fires (mean) | mean close $ | edge close $ | intact edge $ | retention close | retention peak | verdict |
|---|---|---|---|---|---|---|---|
| T1_day_type_EXPANDED | 199971.1 | -26.30 | 2.88 | 1.38 | 2.084 | 12.464 | TERM_NOT_LOAD_BEARING |
| T2_surprise_ge_0.99 | 199924.9 | -17.13 | 13.84 | 1.38 | 10.027 | 19.584 | TERM_NOT_LOAD_BEARING |

Term marginals (FIT, ALL assets):

| term | alone: n / mean close $ | detector without it: n / mean close $ | near-miss (only this fails): n / mean close $ |
|---|---|---|---|
| T1_day_type_EXPANDED | 632063 / -32.12 | 281845 / -28.44 | 2921 / -104.79 |
| T2_surprise_ge_0.99 | 281845 / -28.44 | 632063 / -32.12 | 353139 / -35.67 |

Cluster-robust inference (GEE identity link, Liang-Zeger sandwich clustered on SESSION, CR1; Holm over the whole batch):

| asset | era | metric | beta $ | se naive | se CR1 | z | p | DEFF | n_eff | raw verdict | Holm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | FIT | cert_close | 1.38 | 1.81 | 7.51 | 0.18 | 0.85425 | 10.24 | 119357.4 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| ALL | FIT | cert_peak | 5.29 | 2.23 | 20.06 | 0.26 | 0.79192 | 45.11 | 27092.3 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| ALL | GATE_2025 | cert_close | 1.69 | 4.89 | 19.87 | 0.09 | 0.93205 | 13.87 | 25826.2 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| ALL | GATE_2025 | cert_peak | 110.64 | 7.22 | 50.01 | 2.21 | 0.02696 | 42.21 | 8484.1 | SIGNIFICANT_p<0.05 | HOLM_NOT_SIGNIFICANT |
| SI | FIT | cert_close | 15.43 | 3.71 | 15.72 | 0.98 | 0.32614 | 15.64 | 25919.5 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| SI | FIT | cert_peak | -21.11 | 4.40 | 28.93 | -0.73 | 0.46554 | 40.50 | 10012.1 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| SI | GATE_2025 | cert_close | -40.44 | 10.23 | 34.93 | -1.16 | 0.24704 | 14.85 | 9001.4 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| SI | GATE_2025 | cert_peak | 236.69 | 16.02 | 110.36 | 2.14 | 0.03197 | 37.87 | 3530.7 | SIGNIFICANT_p<0.05 | HOLM_NOT_SIGNIFICANT |
| HG | FIT | cert_close | -8.15 | 2.57 | 7.99 | -1.02 | 0.30761 | 5.25 | 79420.9 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | FIT | cert_peak | -39.70 | 3.23 | 25.15 | -1.58 | 0.11450 | 45.00 | 9273.3 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | GATE_2025 | cert_close | 18.85 | 6.07 | 26.47 | 0.71 | 0.47644 | 10.18 | 11025.0 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | GATE_2025 | cert_peak | 69.66 | 8.14 | 64.18 | 1.09 | 0.27776 | 39.40 | 2848.5 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | FIT | cert_close | -0.50 | 3.05 | 13.34 | -0.04 | 0.96991 | 6.61 | 60412.8 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | FIT | cert_peak | 54.68 | 3.82 | 42.07 | 1.30 | 0.19374 | 41.24 | 9688.5 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | GATE_2025 | cert_close | 34.91 | 7.81 | 37.19 | 0.94 | 0.34791 | 15.93 | 7040.7 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | GATE_2025 | cert_peak | 48.58 | 10.18 | 43.30 | 1.12 | 0.26190 | 40.35 | 2780.1 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |

## P022 FLOW_HORIZON_DISAGREEMENT — detail

| | fires | per session | mean close $ | cond. close $ | mean peak $ | cond. peak $ | winners |
|---|---|---|---|---|---|---|---|
| FIRE | 8564 | 2.893 | -61.29 | 1025.26 | 833.39 | 912.10 | 863 (10.077%) |
| NOFIRE | 1213704 | 410.035 | -28.47 | 660.23 | 833.89 | 902.27 | 68817 (5.670%) |

Per-year stability (ALL assets):

| year | fires | mean close $ | cond close $ | winner rate % | baseline mean $ | baseline winner rate % |
|---|---|---|---|---|---|---|
| 2021 | 1516 | -8.09 | 877.55 | 9.763 | -30.10 | 5.377 |
| 2022 | 2973 | -89.15 | 1066.73 | 9.317 | -33.61 | 6.015 |
| 2023 | 2056 | -6.32 | 1028.74 | 11.430 | -23.37 | 4.920 |
| 2024 | 2019 | -116.18 | 1092.14 | 10.054 | -26.96 | 6.245 |
| GATE_2025 (eval-only) | 2378 | -52.39 | 1399.74 | 10.050 | -27.56 | 6.451 |

Per-asset / per-side (FIT):

| stratum | fires | mean close $ | cond close $ | winner rate % | baseline mean $ |
|---|---|---|---|---|---|
| ALL / ALL / LONG | 4334 | -28.66 | 978.19 | 10.037 | -27.14 |
| ALL / ALL / SHORT | 4230 | -94.72 | 1081.20 | 10.118 | -29.82 |
| ALL / NY / ALL | 8564 | -61.29 | 1025.26 | 10.077 | -24.54 |
| HG / ALL / ALL | 2874 | -57.11 | 796.81 | 8.316 | -27.60 |
| HG / ALL / LONG | 1475 | -100.72 | 798.50 | 6.441 | -35.79 |
| HG / ALL / SHORT | 1399 | -11.12 | 795.23 | 10.293 | -19.39 |
| HG / NY / ALL | 2874 | -57.11 | 796.81 | 8.316 | -32.93 |
| NKD / ALL / ALL | 2186 | -22.33 | 1084.33 | 10.613 | -46.72 |
| NKD / ALL / LONG | 1119 | 4.67 | 979.56 | 9.026 | -32.87 |
| NKD / ALL / SHORT | 1067 | -50.65 | 1222.74 | 12.277 | -60.87 |
| NKD / NY / ALL | 2186 | -22.33 | 1084.33 | 10.613 | -48.95 |
| SI / ALL / ALL | 3504 | -89.02 | 1202.25 | 11.187 | -11.34 |
| SI / ALL / LONG | 1740 | 11.00 | 1119.45 | 13.736 | -12.54 |
| SI / ALL / SHORT | 1764 | -187.67 | 1317.15 | 8.673 | -10.13 |
| SI / NY / ALL | 3504 | -89.02 | 1202.25 | 11.187 | -2.69 |

Mechanism destruction (FIT, ALL assets; each term shuffled within its session, 40 replicates). EDGE = mean close of the firing set minus the non-firing rest; retention = destroyed edge / intact edge. High retention means the term was not carrying the value.

| neutralised term | fires (mean) | mean close $ | edge close $ | intact edge $ | retention close | retention peak | verdict |
|---|---|---|---|---|---|---|---|
| T1_disagrees_30m | 6388.8 | -27.98 | 0.73 | -32.81 | -0.022 | -87.308 | VOID_no_intact_edge |
| T2_disagrees_5m | 5971.7 | -46.99 | -18.38 | -32.81 | 0.560 | -16.807 | VOID_no_intact_edge |
| T3_release_lt_90min | 9232.3 | -24.39 | 4.35 | -32.81 | -0.132 | -107.281 | VOID_no_intact_edge |

Term marginals (FIT, ALL assets):

| term | alone: n / mean close $ | detector without it: n / mean close $ | near-miss (only this fails): n / mean close $ |
|---|---|---|---|
| T1_disagrees_30m | 365247 / -29.10 | 20386 / -25.51 | 11822 / 0.41 |
| T2_disagrees_5m | 491239 / -25.95 | 13976 / -42.39 | 5412 / -12.49 |
| T3_release_lt_90min | 53203 / -8.32 | 211293 / -26.76 | 202729 / -25.30 |

Cluster-robust inference (GEE identity link, Liang-Zeger sandwich clustered on SESSION, CR1; Holm over the whole batch):

| asset | era | metric | beta $ | se naive | se CR1 | z | p | DEFF | n_eff | raw verdict | Holm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | FIT | cert_close | -32.81 | 9.13 | 30.31 | -1.08 | 0.27890 | 10.24 | 119357.4 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| ALL | FIT | cert_peak | -0.50 | 11.23 | 25.41 | -0.02 | 0.98416 | 45.11 | 27092.3 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| ALL | GATE_2025 | cert_close | -24.83 | 28.16 | 65.77 | -0.38 | 0.70577 | 13.87 | 25826.2 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| ALL | GATE_2025 | cert_peak | -60.34 | 41.65 | 87.79 | -0.69 | 0.49192 | 42.21 | 8484.1 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| SI | FIT | cert_close | -77.68 | 16.83 | 52.14 | -1.49 | 0.13631 | 15.64 | 25919.5 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| SI | FIT | cert_peak | 18.57 | 19.96 | 40.14 | 0.46 | 0.64369 | 40.50 | 10012.1 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| SI | GATE_2025 | cert_close | -29.26 | 52.73 | 106.27 | -0.28 | 0.78305 | 14.85 | 9001.4 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| SI | GATE_2025 | cert_peak | -151.76 | 82.66 | 144.98 | -1.05 | 0.29519 | 37.87 | 3530.7 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | FIT | cert_close | -29.51 | 12.42 | 48.72 | -0.61 | 0.54473 | 5.25 | 79420.9 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | FIT | cert_peak | -30.04 | 15.62 | 35.61 | -0.84 | 0.39892 | 45.00 | 9273.3 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | GATE_2025 | cert_close | 123.05 | 33.82 | 65.32 | 1.88 | 0.05958 | 10.18 | 11025.0 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| HG | GATE_2025 | cert_peak | 38.56 | 45.38 | 134.44 | 0.29 | 0.77425 | 39.40 | 2848.5 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | FIT | cert_close | 24.39 | 18.06 | 51.28 | 0.48 | 0.63439 | 6.61 | 60412.8 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | FIT | cert_peak | -40.45 | 22.64 | 51.78 | -0.78 | 0.43471 | 41.24 | 9688.5 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | GATE_2025 | cert_close | -243.10 | 54.91 | 134.03 | -1.81 | 0.06971 | 15.93 | 7040.7 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |
| NKD | GATE_2025 | cert_peak | -129.68 | 71.57 | 97.95 | -1.32 | 0.18550 | 40.35 | 2780.1 | NOT_SIGNIFICANT | HOLM_NOT_SIGNIFICANT |

## Named-case check (the E1D2 cases these patterns were written from)

| case | note | P020 | P021 | P022 | day_type | surprise | ext_needed $ | release age s | cert close $ |
|---|---|---|---|---|---|---|---|---|---|
| SI-20210702-051810-L | P021 proof case (+$1,707.50; ext_needed $512.5) | YES | no | no | INSIDE | 0.211 | 512.5 | 1362210 | 1707.50 |
| SI-20210702-052297-L | P021 proof case (+$1,682.50; ext_needed $537.5) | YES | no | no | INSIDE | 0.369 | 537.5 | 97 | 1682.50 |
| SI-20210702-057352-L | the seat the reader READ THE REGIME ON (EXPANDED, 112.1% of range_hat, surprise 0.993) | YES | YES | no | EXPANDED | 0.993 | 200.0 | 5152 | 432.50 |
| SI-20210702-052509-S | P022 birth case (-$930; think-aloud committed) | YES | no | no | INSIDE | 0.413 | 0.0 | 309 | -930.00 |
| SI-20210702-054009-S | P022 companion (-$930) | YES | no | no | AT_RANGE | 0.693 | 0.0 | 1809 | -930.00 |

## Provenance

* engine: `engine/port_m2/p020_census.py` (census machinery reused from `p001_census.py`; frame from `pattern_lib.py`)
* red-first mutants: `engine/port_m2/test_pattern.py` (artifacts/cache/port/m2/tests/pattern_red_ledger.tsv)
* runtime 175.0s; pins HELD
* params_hash `00c21776223b82281297cb2b32ca2d3a786d1f1abda99aeb43d935f37bf8819a`


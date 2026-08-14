# ERA PRIMER — E2 (20220101..20220630)

Auto-generated from COMMITTED CENSUSES by engine/port_m2/era_primer.py (spec §3).
Every figure carries its source as `file:line`. sheets_version=PORT-SHEETS-V1.1  spec_sha16=19fedc9231ba9f0e
STUDY/BLIND boundary date (day-complete, D-058/D-036): **20220420** — sessions <= boundary are STUDY.

## 1. THE ERA'S MATERIAL

| asset | sessions | candidates | STUDY sess | STUDY cand | BLIND sess | BLIND cand | source |
|---|---|---|---|---|---|---|---|
| SI | 128 | 59338 | 77 | 37416 | 51 | 21922 | artifacts/cache/port/m2/era/E2/INDEX_SI.tsv n=59338 |
| HG | 128 | 56299 | 77 | 34637 | 51 | 21662 | artifacts/cache/port/m2/era/E2/INDEX_HG.tsv n=56299 |
| NKD | 128 | 59925 | 77 | 36648 | 51 | 23277 | artifacts/cache/port/m2/era/E2/INDEX_NKD.tsv n=59925 |

## 2. COST (m0 census A)

Session round-trip cost is the entry bar's denominator: a $1,000 trade is a $1,000 trade AFTER this.

| asset | cost_rt median $ | spread_med $ | spread_p90 $ | dominance median | source |
|---|---|---|---|---|---|
| SI | 30.00 | 25.00 | 50.00 | 0.9158 | artifacts/cache/port/m0/census_a_cost.tsv:L13152-L13764 n=154 |
| HG | 30.00 | 25.00 | 37.50 | 1.0000 | artifacts/cache/port/m0/census_a_cost.tsv:L1248-L1860 n=154 |
| NKD | 55.00 | 50.00 | 50.00 | 1.0000 | artifacts/cache/port/m0/census_a_cost.tsv:L7456-L8068 n=154 |

## 3. OFFER (m0 census B, SESSION/FULL convention)

| asset | range median $ | best_leg median $ | legs_1k mean/session | sessions | source |
|---|---|---|---|---|---|
| SI | 2725 | 2725 | 2.93 | 154 | artifacts/cache/port/m0/census_b_offer.tsv:L22671-L23436 n=154 |
| HG | 2272 | 2272 | 2.22 | 154 | artifacts/cache/port/m0/census_b_offer.tsv:L1555-L2320 n=154 |
| NKD | 2394 | 2394 | 2.42 | 154 | artifacts/cache/port/m0/census_b_offer.tsv:L12431-L13196 n=154 |

## 4. VOL-REGIME MIX (m1 fvol, SESSION segment)

The regime tag every sheet's S2 shows, counted over the era.

| asset | regime mix (n sessions) | rv5/rv66 median | sigma_hat median $ | source |
|---|---|---|---|---|
| SI | HIGH=39 LOW=55 MID=34 | 0.859 | 2590.8 | artifacts/cache/port/m1/fvol/fvol_forecasts.tsv:L161-L288 n=128 |
| HG | HIGH=47 LOW=51 MID=30 | 0.894 | 1580.1 | artifacts/cache/port/m1/fvol/fvol_forecasts.tsv:L5008-L5135 n=128 |
| NKD | HIGH=43 LOW=33 MID=52 | 0.926 | 1681.2 | artifacts/cache/port/m1/fvol/fvol_forecasts.tsv:L10168-L10295 n=128 |

## 5. PHASE MAP

Where the seated value sits (census C, by calendar year — the census's own era vocabulary) and what each phase costs (census A).

| asset | phase | seated value share | cost_rt median $ | two-sided seconds median | sources |
|---|---|---|---|---|---|
| SI | TOKYO | 2022=0.197 | 30.00 | 25200 | artifacts/cache/port/m0/census_c_phase_value.tsv:L70 ; artifacts/cache/port/m0/census_a_cost.tsv:L13149-L13761 n=154 |
| SI | LONDON | 2022=0.278 | 30.00 | 21600 | artifacts/cache/port/m0/census_c_phase_value.tsv:L54 ; artifacts/cache/port/m0/census_a_cost.tsv:L13150-L13762 n=154 |
| SI | NY | 2022=0.525 | 30.00 | 36000 | artifacts/cache/port/m0/census_c_phase_value.tsv:L62 ; artifacts/cache/port/m0/census_a_cost.tsv:L13151-L13763 n=154 |
| HG | TOKYO | 2022=0.301 | 30.00 | 28800 | artifacts/cache/port/m0/census_c_phase_value.tsv:L22 ; artifacts/cache/port/m0/census_a_cost.tsv:L1245-L1857 n=154 |
| HG | LONDON | 2022=0.263 | 30.00 | 14400 | artifacts/cache/port/m0/census_c_phase_value.tsv:L6 ; artifacts/cache/port/m0/census_a_cost.tsv:L1246-L1858 n=154 |
| HG | NY | 2022=0.437 | 30.00 | 36000 | artifacts/cache/port/m0/census_c_phase_value.tsv:L14 ; artifacts/cache/port/m0/census_a_cost.tsv:L1247-L1859 n=154 |
| NKD | TOKYO | 2022=0.386 | 55.00 | 27000 | artifacts/cache/port/m0/census_c_phase_value.tsv:L46 ; artifacts/cache/port/m0/census_a_cost.tsv:L7453-L8065 n=154 |
| NKD | LONDON | 2022=0.192 | 55.00 | 18000 | artifacts/cache/port/m0/census_c_phase_value.tsv:L30 ; artifacts/cache/port/m0/census_a_cost.tsv:L7454-L8066 n=154 |
| NKD | NY | 2022=0.422 | 55.00 | 36000 | artifacts/cache/port/m0/census_c_phase_value.tsv:L38 ; artifacts/cache/port/m0/census_a_cost.tsv:L7455-L8067 n=154 |

## 6. CANDIDATE-CLASS CARDS (D-071.4)

The class every sheet declares in S1, with its census card FOR THIS ERA.  `fires/sess` is the class's fire rate; `cond_value$` is the CC-M1-7.3 conditional value (mean walled phase-close certificate over positive candidates); `win_frac` is the D-021 winner share (>= $1,000 with MAE <= $300, never walled).

| asset | class | n_cand | fires/sess | cond_value $ | pos_frac | win_frac | cond_peak $ | source |
|---|---|---|---|---|---|---|---|---|
| SI | SHOCK-RESOLUTION | 52 | 0.41 | 1338.06 | 0.3462 | 0.0769 | 1439.02 | artifacts/cache/port/m2/class_census.tsv:L337 |
| SI | NEWS-WINDOW | 2565 | 20.04 | 1219.93 | 0.4125 | 0.1240 | 1060.15 | artifacts/cache/port/m2/class_census.tsv:L265 |
| SI | OPEN-DYNAMICS | 1365 | 10.66 | 1157.52 | 0.4073 | 0.1150 | 1183.23 | artifacts/cache/port/m2/class_census.tsv:L283 |
| SI | REVERSAL-CONFIRMATION | 52978 | 413.89 | 815.53 | 0.4302 | 0.0697 | 1032.90 | artifacts/cache/port/m2/class_census.tsv:L319 |
| SI | RECLAIM | 2378 | 18.58 | 853.68 | 0.4142 | 0.0719 | 1007.17 | artifacts/cache/port/m2/class_census.tsv:L301 |
| SI | ALL_CLASSES | 59338 | 463.58 | 841.70 | 0.4282 | 0.0732 | 1036.85 | artifacts/cache/port/m2/class_census.tsv:L247 |
| HG | SHOCK-RESOLUTION | 24 | 0.19 | 932.50 | 0.1667 | 0.0417 | 1620.00 | artifacts/cache/port/m2/class_census.tsv:L103 |
| HG | NEWS-WINDOW | 1471 | 11.49 | 820.17 | 0.4167 | 0.0802 | 843.44 | artifacts/cache/port/m2/class_census.tsv:L31 |
| HG | OPEN-DYNAMICS | 1224 | 9.56 | 777.18 | 0.4608 | 0.0727 | 1063.16 | artifacts/cache/port/m2/class_census.tsv:L49 |
| HG | REVERSAL-CONFIRMATION | 50927 | 397.87 | 601.11 | 0.4475 | 0.0550 | 917.32 | artifacts/cache/port/m2/class_census.tsv:L85 |
| HG | RECLAIM | 2653 | 20.73 | 606.81 | 0.4489 | 0.0660 | 854.62 | artifacts/cache/port/m2/class_census.tsv:L67 |
| HG | ALL_CLASSES | 56299 | 439.84 | 610.72 | 0.4470 | 0.0566 | 915.87 | artifacts/cache/port/m2/class_census.tsv:L13 |
| NKD | SHOCK-RESOLUTION | 74 | 0.58 | 833.51 | 0.5000 | 0.1081 | 1122.02 | artifacts/cache/port/m2/class_census.tsv:L229 |
| NKD | LEVEL-FIRST-TEST | 725 | 5.66 | 730.27 | 0.4097 | 0.0662 | 1125.22 | artifacts/cache/port/m2/class_census.tsv:L139 |
| NKD | NEWS-WINDOW | 1133 | 8.85 | 953.13 | 0.4342 | 0.1174 | 897.89 | artifacts/cache/port/m2/class_census.tsv:L157 |
| NKD | OPEN-DYNAMICS | 1648 | 12.88 | 788.01 | 0.4254 | 0.0807 | 1021.73 | artifacts/cache/port/m2/class_census.tsv:L175 |
| NKD | REVERSAL-CONFIRMATION | 54202 | 423.45 | 650.03 | 0.4311 | 0.0607 | 895.93 | artifacts/cache/port/m2/class_census.tsv:L211 |
| NKD | RECLAIM | 2143 | 16.74 | 644.85 | 0.4251 | 0.0523 | 839.34 | artifacts/cache/port/m2/class_census.tsv:L193 |
| NKD | ALL_CLASSES | 59925 | 468.16 | 660.56 | 0.4306 | 0.0621 | 900.43 | artifacts/cache/port/m2/class_census.tsv:L121 |

## 7. FAMILY CARDS (m1 generation_v3 census, calendar-year rows)

| asset | family | era | n_cand | cond_value $ | pos_frac | cond_peak $ | source |
|---|---|---|---|---|---|---|---|
| SI | G1 | 2022 | 40946 | 801.21 | 0.4332 | 1024.76 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L9 |
| SI | G1_FINE | 2022 | 46029 | 804.87 | 0.4352 | 1028.01 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L16 |
| SI | G1_FAST_OPEN | 2022 | 999 | 1075.51 | 0.3864 | 1344.84 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L23 |
| SI | G2_REJECT | 2022 | 21709 | 832.40 | 0.4316 | 1001.62 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L30 |
| SI | G2_RECLAIM | 2022 | 4969 | 832.77 | 0.4313 | 973.94 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L37 |
| SI | NEWS_WINDOW | 2022 | 5512 | 1221.30 | 0.4011 | 1029.24 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L44 |
| SI | MICRO_OPEN | 2022 | 1602 | 1149.74 | 0.4151 | 1049.28 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L51 |
| SI | POST_SHOCK | 2022 | 97 | 1307.50 | 0.3505 | 1276.90 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L58 |
| SI | FIRST_TEST | 2022 | 0 | . | . | . | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L65 |
| HG | G1 | 2022 | 38493 | 571.15 | 0.4519 | 873.50 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L79 |
| HG | G1_FINE | 2022 | 46458 | 567.85 | 0.4521 | 867.25 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L86 |
| HG | G1_FAST_OPEN | 2022 | 1491 | 763.75 | 0.4628 | 1096.72 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L93 |
| HG | G2_REJECT | 2022 | 20032 | 607.74 | 0.4442 | 827.78 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L100 |
| HG | G2_RECLAIM | 2022 | 4793 | 618.71 | 0.4488 | 817.72 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L107 |
| HG | NEWS_WINDOW | 2022 | 3307 | 811.67 | 0.4233 | 787.44 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L114 |
| HG | MICRO_OPEN | 2022 | 1074 | 684.59 | 0.4395 | 803.50 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L121 |
| HG | POST_SHOCK | 2022 | 48 | 945.74 | 0.3542 | 1392.53 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L128 |
| HG | FIRST_TEST | 2022 | 0 | . | . | . | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L135 |
| NKD | G1 | 2022 | 39826 | 574.45 | 0.4346 | 822.78 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L149 |
| NKD | G1_FINE | 2022 | 46917 | 573.94 | 0.4357 | 824.93 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L156 |
| NKD | G1_FAST_OPEN | 2022 | 1468 | 660.08 | 0.4251 | 996.74 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L163 |
| NKD | G2_REJECT | 2022 | 17677 | 587.29 | 0.4368 | 786.45 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L170 |
| NKD | G2_RECLAIM | 2022 | 3813 | 602.51 | 0.4330 | 783.95 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L177 |
| NKD | NEWS_WINDOW | 2022 | 2755 | 890.53 | 0.4359 | 786.61 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L184 |
| NKD | MICRO_OPEN | 2022 | 1501 | 721.06 | 0.4390 | 841.14 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L191 |
| NKD | POST_SHOCK | 2022 | 195 | 782.21 | 0.4462 | 1001.63 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L198 |
| NKD | FIRST_TEST | 2022 | 1480 | 620.62 | 0.4345 | 1024.12 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L205 |

## 8. HOW TO READ THIS PAGE

* It is a PRIOR, not a rule (D-068.2 duty to contradict): the tape is the data and overturning a primer item is the most valuable output of a study block.
* Class cards are POPULATION quality, never trade targets — the $1,000+/trade bar (D-021) applies to SELECTED trades (D-062).
* Era-learned patterns are ERA-TAGGED HYPOTHESES (D-059.1); each new era opens with the library re-test before new discovery.


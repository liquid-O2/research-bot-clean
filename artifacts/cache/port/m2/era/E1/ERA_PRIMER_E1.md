# ERA PRIMER — E1 (20210701..20211231)

Auto-generated from COMMITTED CENSUSES by engine/port_m2/era_primer.py (spec §3).
Every figure carries its source as `file:line`. sheets_version=PORT-SHEETS-V1.1  spec_sha16=19fedc9231ba9f0e
STUDY/BLIND boundary date (day-complete, D-058/D-036): **20211019** — sessions <= boundary are STUDY.

## 1. THE ERA'S MATERIAL

| asset | sessions | candidates | STUDY sess | STUDY cand | BLIND sess | BLIND cand | source |
|---|---|---|---|---|---|---|---|
| SI | 131 | 50916 | 79 | 31500 | 52 | 19416 | artifacts/cache/port/m2/era/E1/INDEX_SI.tsv n=50916 |
| HG | 131 | 47647 | 79 | 31376 | 52 | 16271 | artifacts/cache/port/m2/era/E1/INDEX_HG.tsv n=47647 |
| NKD | 131 | 52113 | 79 | 32226 | 52 | 19887 | artifacts/cache/port/m2/era/E1/INDEX_NKD.tsv n=52113 |

## 2. COST (m0 census A)

Session round-trip cost is the entry bar's denominator: a $1,000 trade is a $1,000 trade AFTER this.

| asset | cost_rt median $ | spread_med $ | spread_p90 $ | dominance median | source |
|---|---|---|---|---|---|
| SI | 30.00 | 25.00 | 50.00 | 0.9447 | artifacts/cache/port/m0/census_a_cost.tsv:L12532-L13148 n=155 |
| HG | 30.00 | 25.00 | 25.00 | 1.0000 | artifacts/cache/port/m0/census_a_cost.tsv:L620-L1244 n=157 |
| NKD | 55.00 | 50.00 | 50.00 | 1.0000 | artifacts/cache/port/m0/census_a_cost.tsv:L6828-L7452 n=157 |

## 3. OFFER (m0 census B, SESSION/FULL convention)

| asset | range median $ | best_leg median $ | legs_1k mean/session | sessions | source |
|---|---|---|---|---|---|
| SI | 2338 | 2338 | 1.88 | 155 | artifacts/cache/port/m0/census_b_offer.tsv:L21896-L22666 n=155 |
| HG | 2256 | 2256 | 1.57 | 157 | artifacts/cache/port/m0/census_b_offer.tsv:L770-L1550 n=157 |
| NKD | 1900 | 1900 | 1.59 | 157 | artifacts/cache/port/m0/census_b_offer.tsv:L11646-L12426 n=157 |

## 4. VOL-REGIME MIX (m1 fvol, SESSION segment)

The regime tag every sheet's S2 shows, counted over the era.

| asset | regime mix (n sessions) | rv5/rv66 median | sigma_hat median $ | source |
|---|---|---|---|---|
| SI | HIGH=26 LOW=47 MID=58 | 0.882 | 2402.0 | artifacts/cache/port/m1/fvol/fvol_forecasts.tsv:L30-L160 n=131 |
| HG | HIGH=44 LOW=52 MID=35 | 0.877 | 2192.1 | artifacts/cache/port/m1/fvol/fvol_forecasts.tsv:L4877-L5007 n=131 |
| NKD | HIGH=49 LOW=44 MID=38 | 0.911 | 2019.0 | artifacts/cache/port/m1/fvol/fvol_forecasts.tsv:L10037-L10167 n=131 |

## 5. PHASE MAP

Where the seated value sits (census C, by calendar year — the census's own era vocabulary) and what each phase costs (census A).

| asset | phase | seated value share | cost_rt median $ | two-sided seconds median | sources |
|---|---|---|---|---|---|
| SI | TOKYO | 2021=0.192 | 30.00 | 25200 | artifacts/cache/port/m0/census_c_phase_value.tsv:L69 ; artifacts/cache/port/m0/census_a_cost.tsv:L12529-L13145 n=155 |
| SI | LONDON | 2021=0.255 | 30.00 | 21600 | artifacts/cache/port/m0/census_c_phase_value.tsv:L53 ; artifacts/cache/port/m0/census_a_cost.tsv:L12530-L13146 n=155 |
| SI | NY | 2021=0.553 | 30.00 | 36000 | artifacts/cache/port/m0/census_c_phase_value.tsv:L61 ; artifacts/cache/port/m0/census_a_cost.tsv:L12531-L13147 n=155 |
| HG | TOKYO | 2021=0.254 | 30.00 | 25200 | artifacts/cache/port/m0/census_c_phase_value.tsv:L21 ; artifacts/cache/port/m0/census_a_cost.tsv:L617-L1241 n=157 |
| HG | LONDON | 2021=0.310 | 30.00 | 21600 | artifacts/cache/port/m0/census_c_phase_value.tsv:L5 ; artifacts/cache/port/m0/census_a_cost.tsv:L618-L1242 n=157 |
| HG | NY | 2021=0.436 | 30.00 | 36000 | artifacts/cache/port/m0/census_c_phase_value.tsv:L13 ; artifacts/cache/port/m0/census_a_cost.tsv:L619-L1243 n=157 |
| NKD | TOKYO | 2021=0.487 | 55.00 | 30600 | artifacts/cache/port/m0/census_c_phase_value.tsv:L45 ; artifacts/cache/port/m0/census_a_cost.tsv:L6825-L7449 n=157 |
| NKD | LONDON | 2021=0.164 | 30.00 | 16200 | artifacts/cache/port/m0/census_c_phase_value.tsv:L29 ; artifacts/cache/port/m0/census_a_cost.tsv:L6826-L7450 n=157 |
| NKD | NY | 2021=0.349 | 30.00 | 36000 | artifacts/cache/port/m0/census_c_phase_value.tsv:L37 ; artifacts/cache/port/m0/census_a_cost.tsv:L6827-L7451 n=157 |

## 6. CANDIDATE-CLASS CARDS (D-071.4)

The class every sheet declares in S1, with its census card FOR THIS ERA.  `fires/sess` is the class's fire rate; `cond_value$` is the CC-M1-7.3 conditional value (mean walled phase-close certificate over positive candidates); `win_frac` is the D-021 winner share (>= $1,000 with MAE <= $300, never walled).

| asset | class | n_cand | fires/sess | cond_value $ | pos_frac | win_frac | cond_peak $ | source |
|---|---|---|---|---|---|---|---|---|
| SI | SHOCK-RESOLUTION | 34 | 0.26 | 959.58 | 0.3529 | 0.0000 | 1112.19 | artifacts/cache/port/m2/class_census.tsv:L336 |
| SI | NEWS-WINDOW | 2696 | 20.58 | 1042.88 | 0.4388 | 0.1187 | 962.67 | artifacts/cache/port/m2/class_census.tsv:L264 |
| SI | OPEN-DYNAMICS | 1283 | 9.79 | 848.32 | 0.4575 | 0.0826 | 969.70 | artifacts/cache/port/m2/class_census.tsv:L282 |
| SI | REVERSAL-CONFIRMATION | 44823 | 342.16 | 654.86 | 0.4403 | 0.0590 | 905.47 | artifacts/cache/port/m2/class_census.tsv:L318 |
| SI | RECLAIM | 2080 | 15.88 | 708.54 | 0.4173 | 0.0620 | 827.91 | artifacts/cache/port/m2/class_census.tsv:L300 |
| SI | ALL_CLASSES | 50916 | 388.67 | 682.69 | 0.4396 | 0.0629 | 907.07 | artifacts/cache/port/m2/class_census.tsv:L246 |
| HG | SHOCK-RESOLUTION | 13 | 0.10 | 184.06 | 0.3077 | 0.0000 | 363.23 | artifacts/cache/port/m2/class_census.tsv:L102 |
| HG | NEWS-WINDOW | 1609 | 12.28 | 704.60 | 0.4723 | 0.0653 | 730.05 | artifacts/cache/port/m2/class_census.tsv:L30 |
| HG | OPEN-DYNAMICS | 946 | 7.22 | 650.35 | 0.4683 | 0.0772 | 868.22 | artifacts/cache/port/m2/class_census.tsv:L48 |
| HG | REVERSAL-CONFIRMATION | 43387 | 331.20 | 516.84 | 0.4625 | 0.0463 | 837.00 | artifacts/cache/port/m2/class_census.tsv:L84 |
| HG | RECLAIM | 1692 | 12.92 | 500.14 | 0.4722 | 0.0384 | 724.22 | artifacts/cache/port/m2/class_census.tsv:L66 |
| HG | ALL_CLASSES | 47647 | 363.72 | 525.32 | 0.4633 | 0.0472 | 829.82 | artifacts/cache/port/m2/class_census.tsv:L12 |
| NKD | SHOCK-RESOLUTION | 22 | 0.17 | 938.75 | 0.4545 | 0.0455 | 1049.61 | artifacts/cache/port/m2/class_census.tsv:L228 |
| NKD | LEVEL-FIRST-TEST | 714 | 5.45 | 639.59 | 0.4174 | 0.0490 | 902.18 | artifacts/cache/port/m2/class_census.tsv:L138 |
| NKD | NEWS-WINDOW | 1013 | 7.73 | 719.92 | 0.4482 | 0.0800 | 667.11 | artifacts/cache/port/m2/class_census.tsv:L156 |
| NKD | OPEN-DYNAMICS | 1237 | 9.44 | 728.08 | 0.4204 | 0.0582 | 902.69 | artifacts/cache/port/m2/class_census.tsv:L174 |
| NKD | REVERSAL-CONFIRMATION | 47797 | 364.86 | 587.82 | 0.4290 | 0.0467 | 854.22 | artifacts/cache/port/m2/class_census.tsv:L210 |
| NKD | RECLAIM | 1330 | 10.15 | 592.48 | 0.4286 | 0.0421 | 805.64 | artifacts/cache/port/m2/class_census.tsv:L192 |
| NKD | ALL_CLASSES | 52113 | 397.81 | 594.73 | 0.4290 | 0.0476 | 851.22 | artifacts/cache/port/m2/class_census.tsv:L120 |

## 7. FAMILY CARDS (m1 generation_v3 census, calendar-year rows)

| asset | family | era | n_cand | cond_value $ | pos_frac | cond_peak $ | source |
|---|---|---|---|---|---|---|---|
| SI | G1 | 2021 | 20193 | 690.66 | 0.4406 | 938.21 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L8 |
| SI | G1_FINE | 2021 | 22675 | 670.50 | 0.4451 | 937.88 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L15 |
| SI | G1_FAST_OPEN | 2021 | 400 | 794.58 | 0.5175 | 1167.82 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L22 |
| SI | G2_REJECT | 2021 | 9195 | 693.05 | 0.4250 | 896.75 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L29 |
| SI | G2_RECLAIM | 2021 | 2188 | 699.79 | 0.4150 | 823.70 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L36 |
| SI | NEWS_WINDOW | 2021 | 2925 | 1104.56 | 0.4424 | 1007.38 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L43 |
| SI | MICRO_OPEN | 2021 | 1003 | 896.31 | 0.4297 | 898.31 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L50 |
| SI | POST_SHOCK | 2021 | 37 | 1042.12 | 0.3514 | 1112.50 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L57 |
| SI | FIRST_TEST | 2021 | 0 | . | . | . | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L64 |
| HG | G1 | 2021 | 34660 | 545.76 | 0.4634 | 844.92 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L78 |
| HG | G1_FINE | 2021 | 41767 | 537.45 | 0.4630 | 840.91 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L85 |
| HG | G1_FAST_OPEN | 2021 | 744 | 762.26 | 0.4624 | 1046.00 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L92 |
| HG | G2_REJECT | 2021 | 12971 | 584.44 | 0.4663 | 799.75 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L99 |
| HG | G2_RECLAIM | 2021 | 2958 | 554.40 | 0.4692 | 771.06 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L106 |
| HG | NEWS_WINDOW | 2021 | 2985 | 745.48 | 0.4670 | 730.84 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L113 |
| HG | MICRO_OPEN | 2021 | 1144 | 640.45 | 0.4668 | 741.81 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L120 |
| HG | POST_SHOCK | 2021 | 41 | 772.50 | 0.3659 | 926.25 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L127 |
| HG | FIRST_TEST | 2021 | 0 | . | . | . | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L134 |
| NKD | G1 | 2021 | 36836 | 591.25 | 0.4275 | 865.43 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L148 |
| NKD | G1_FINE | 2021 | 42387 | 569.42 | 0.4323 | 843.90 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L155 |
| NKD | G1_FAST_OPEN | 2021 | 847 | 935.78 | 0.4227 | 1059.36 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L162 |
| NKD | G2_REJECT | 2021 | 10714 | 554.67 | 0.4343 | 787.07 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L169 |
| NKD | G2_RECLAIM | 2021 | 2359 | 592.17 | 0.4239 | 792.02 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L176 |
| NKD | NEWS_WINDOW | 2021 | 1767 | 694.12 | 0.4397 | 654.42 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L183 |
| NKD | MICRO_OPEN | 2021 | 1335 | 634.05 | 0.4300 | 824.13 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L190 |
| NKD | POST_SHOCK | 2021 | 45 | 814.85 | 0.3778 | 1142.58 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L197 |
| NKD | FIRST_TEST | 2021 | 1309 | 643.23 | 0.4324 | 920.22 | artifacts/cache/port/m1/generation_v3/census_family_value.tsv:L204 |

## 8. HOW TO READ THIS PAGE

* It is a PRIOR, not a rule (D-068.2 duty to contradict): the tape is the data and overturning a primer item is the most valuable output of a study block.
* Class cards are POPULATION quality, never trade targets — the $1,000+/trade bar (D-021) applies to SELECTED trades (D-062).
* Era-learned patterns are ERA-TAGGED HYPOTHESES (D-059.1); each new era opens with the library re-test before new discovery.


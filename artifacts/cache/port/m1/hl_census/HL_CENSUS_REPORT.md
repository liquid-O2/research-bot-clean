# HL_CENSUS_REPORT — day-high/low prediction census

Spec: design/PORT_HL_CENSUS_SPEC.md (sha16 ff35394b9f87b891), FROZEN. Census type: EXPLORATORY, non-certifying. FIT era = FIT_2021_2024; GATE_2025 echoed separately; 2026 sealed and never opened.
params_hash=0bfcf7e30aa61b66f82fe08b1f33b845c9bebe172ff2e266362eaca9d5013750

All targets and all mid reads apply the D-054 / CC-M1-4 MID-SANE mask (D-054/CC-M1-4: TWO_SIDED and spread_$ <= min(10 x trailing-phase-median spread_$, $500); trailing median = same-phase per-session medians over the 20 STRICTLY PRIOR sessions (>= 5 observations, else only the cap binds); insane seconds typed-excluded, never interpolated).

## 0. Outcome

| family | assets where the rule is met | verdict |
|---|---|---|
| P1_BASE | none | REJECT |
| P1_BASE_RS | none | REJECT |
| P1_SIDE_POPEN | none | REJECT |
| P1_SIDE_SETTLE | none | REJECT |
| P1_SIDE_SOPEN | none | REJECT |
| P2_LOGIT | none | REJECT |
| P2_OLS | none | REJECT |
| P2_UNCOND | none | REJECT |
| P3_OR30 | NKD REST_OF_WINDOW\|LONDON, SI REST_OF_WINDOW\|LONDON, SI REST_OF_WINDOW\|NY, SI REST_OF_WINDOW\|TOKYO | ADOPT |
| P3_OR60 | SI REST_OF_WINDOW\|LONDON, SI REST_OF_WINDOW\|TOKYO | ADOPT |
| P4_CAMARILLA | none | REJECT |
| P4_FLOOR | none | REJECT |
| P5_D00 | none | REJECT |
| P5_D25 | none | REJECT |
| P5_D50 | none | REJECT |
| P5_D75 | none | REJECT |
| P6_GAPFILL | none | REJECT |

## 1. Pre-registered adoption rule (spec §3)

Rule: lift >= 1.5 AND marginal capture >= +3pp AND per-FIT-year lift sign-stable (>1 in every FIT year). Source: hl_adoption.tsv.

| asset | family | target | capture | null | lift | marginal_pp | year-stable | decision | file:line |
|---|---|---|---|---|---|---|---|---|---|
| HG | P1_BASE | PHASE_HL | 0.638 | 0.193 | 3.300 | 0.000 | 1 | REJECT | hl_adoption.tsv:5 |
| HG | P1_BASE | SESSION_HL | 0.179 | 0.060 | 3.000 | 0.000 | 1 | REJECT | hl_adoption.tsv:6 |
| HG | P1_BASE_RS | PHASE_HL | 0.632 | 0.188 | 3.362 | 0.000 | 1 | REJECT | hl_adoption.tsv:7 |
| HG | P1_BASE_RS | SESSION_HL | 0.167 | 0.058 | 2.904 | 0.000 | 1 | REJECT | hl_adoption.tsv:8 |
| HG | P1_SIDE_POPEN | PHASE_HL | 0.644 | 0.210 | 3.069 | 0.021 | 1 | REJECT | hl_adoption.tsv:9 |
| HG | P1_SIDE_SETTLE | SESSION_HL | 0.182 | 0.076 | 2.391 | 0.006 | 1 | REJECT | hl_adoption.tsv:10 |
| HG | P1_SIDE_SOPEN | SESSION_HL | 0.170 | 0.073 | 2.324 | 0.004 | 1 | REJECT | hl_adoption.tsv:11 |
| HG | P2_LOGIT | SESSION_HL | 0.074 | 0.032 | 2.333 | 0.000 | 1 | REJECT | hl_adoption.tsv:12 |
| HG | P2_OLS | SESSION_HL | 0.080 | 0.031 | 2.574 | 0.000 | 1 | REJECT | hl_adoption.tsv:13 |
| HG | P2_UNCOND | SESSION_HL | 0.080 | 0.031 | 2.630 | 0.001 | 1 | REJECT | hl_adoption.tsv:14 |
| HG | P3_OR30 | REST_OF_WINDOW\|LONDON | 0.419 | 0.047 | 8.917 | 0.028 | 1 | REJECT | hl_adoption.tsv:15 |
| HG | P3_OR30 | REST_OF_WINDOW\|NY | 0.397 | 0.157 | 2.523 | 0.022 | 1 | REJECT | hl_adoption.tsv:16 |
| HG | P3_OR30 | REST_OF_WINDOW\|SESSION | 0.231 | 0.166 | 1.393 | 0.012 | 1 | REJECT | hl_adoption.tsv:17 |
| HG | P3_OR30 | REST_OF_WINDOW\|TOKYO | 0.402 | 0.097 | 4.121 | 0.023 | 1 | REJECT | hl_adoption.tsv:18 |
| HG | P3_OR60 | REST_OF_WINDOW\|LONDON | 0.323 | 0.032 | 9.985 | 0.018 | 1 | REJECT | hl_adoption.tsv:19 |
| HG | P3_OR60 | REST_OF_WINDOW\|NY | 0.404 | 0.128 | 3.157 | 0.021 | 1 | REJECT | hl_adoption.tsv:20 |
| HG | P3_OR60 | REST_OF_WINDOW\|SESSION | 0.263 | 0.169 | 1.557 | 0.014 | 1 | REJECT | hl_adoption.tsv:21 |
| HG | P3_OR60 | REST_OF_WINDOW\|TOKYO | 0.433 | 0.100 | 4.312 | 0.024 | 1 | REJECT | hl_adoption.tsv:22 |
| HG | P4_CAMARILLA | SESSION_HL | 0.173 | 0.090 | 1.929 | 0.007 | 1 | REJECT | hl_adoption.tsv:23 |
| HG | P4_FLOOR | SESSION_HL | 0.167 | 0.149 | 1.122 | 0.005 | 0 | REJECT | hl_adoption.tsv:24 |
| HG | P5_D00 | PHASE_HL | 0.159 | 0.173 | 0.915 | 0.000 | 0 | REJECT | hl_adoption.tsv:25 |
| HG | P5_D00 | SESSION_HL | 0.151 | 0.171 | 0.883 | 0.000 | 0 | REJECT | hl_adoption.tsv:26 |
| HG | P5_D25 | PHASE_HL | 0.159 | 0.179 | 0.893 | 0.007 | 0 | REJECT | hl_adoption.tsv:27 |
| HG | P5_D25 | SESSION_HL | 0.170 | 0.175 | 0.972 | 0.007 | 0 | REJECT | hl_adoption.tsv:28 |
| HG | P5_D50 | PHASE_HL | 0.128 | 0.159 | 0.807 | 0.003 | 0 | REJECT | hl_adoption.tsv:29 |
| HG | P5_D50 | SESSION_HL | 0.150 | 0.170 | 0.882 | 0.003 | 0 | REJECT | hl_adoption.tsv:30 |
| HG | P5_D75 | PHASE_HL | 0.100 | 0.124 | 0.806 | 0.005 | 0 | REJECT | hl_adoption.tsv:31 |
| HG | P5_D75 | SESSION_HL | 0.125 | 0.151 | 0.828 | 0.004 | 0 | REJECT | hl_adoption.tsv:32 |
| HG | P6_GAPFILL | SESSION_HL | 0.045 | 0.045 | 1.000 | 0.000 | 0 | REJECT | hl_adoption.tsv:33 |
| NKD | P1_BASE | PHASE_HL | 0.683 | 0.196 | 3.486 | 0.000 | 1 | REJECT | hl_adoption.tsv:34 |
| NKD | P1_BASE | SESSION_HL | 0.185 | 0.072 | 2.573 | 0.000 | 1 | REJECT | hl_adoption.tsv:35 |
| NKD | P1_BASE_RS | PHASE_HL | 0.677 | 0.191 | 3.539 | 0.000 | 1 | REJECT | hl_adoption.tsv:36 |
| NKD | P1_BASE_RS | SESSION_HL | 0.200 | 0.069 | 2.877 | 0.000 | 1 | REJECT | hl_adoption.tsv:37 |
| NKD | P1_SIDE_POPEN | PHASE_HL | 0.709 | 0.208 | 3.399 | 0.013 | 1 | REJECT | hl_adoption.tsv:38 |
| NKD | P1_SIDE_SETTLE | SESSION_HL | 0.208 | 0.079 | 2.647 | 0.003 | 1 | REJECT | hl_adoption.tsv:39 |
| NKD | P1_SIDE_SOPEN | SESSION_HL | 0.191 | 0.078 | 2.461 | 0.004 | 1 | REJECT | hl_adoption.tsv:40 |
| NKD | P2_LOGIT | SESSION_HL | 0.072 | 0.034 | 2.118 | 0.000 | 1 | REJECT | hl_adoption.tsv:41 |
| NKD | P2_OLS | SESSION_HL | 0.080 | 0.032 | 2.500 | 0.000 | 1 | REJECT | hl_adoption.tsv:42 |
| NKD | P2_UNCOND | SESSION_HL | 0.082 | 0.034 | 2.385 | 0.000 | 1 | REJECT | hl_adoption.tsv:43 |
| NKD | P3_OR30 | REST_OF_WINDOW\|LONDON | 0.585 | 0.023 | 25.447 | 0.032 | 1 | ADOPT | hl_adoption.tsv:44 |
| NKD | P3_OR30 | REST_OF_WINDOW\|NY | 0.431 | 0.117 | 3.675 | 0.028 | 1 | REJECT | hl_adoption.tsv:45 |
| NKD | P3_OR30 | REST_OF_WINDOW\|SESSION | 0.296 | 0.163 | 1.811 | 0.011 | 1 | REJECT | hl_adoption.tsv:46 |
| NKD | P3_OR30 | REST_OF_WINDOW\|TOKYO | 0.383 | 0.119 | 3.209 | 0.019 | 1 | REJECT | hl_adoption.tsv:47 |
| NKD | P3_OR60 | REST_OF_WINDOW\|LONDON | 0.525 | 0.015 | 34.677 | 0.025 | 1 | REJECT | hl_adoption.tsv:48 |
| NKD | P3_OR60 | REST_OF_WINDOW\|NY | 0.449 | 0.111 | 4.031 | 0.024 | 1 | REJECT | hl_adoption.tsv:49 |
| NKD | P3_OR60 | REST_OF_WINDOW\|SESSION | 0.316 | 0.163 | 1.943 | 0.011 | 1 | REJECT | hl_adoption.tsv:50 |
| NKD | P3_OR60 | REST_OF_WINDOW\|TOKYO | 0.384 | 0.110 | 3.493 | 0.017 | 1 | REJECT | hl_adoption.tsv:51 |
| NKD | P4_CAMARILLA | SESSION_HL | 0.180 | 0.081 | 2.236 | 0.004 | 1 | REJECT | hl_adoption.tsv:52 |
| NKD | P4_FLOOR | SESSION_HL | 0.168 | 0.166 | 1.009 | 0.007 | 0 | REJECT | hl_adoption.tsv:53 |
| NKD | P5_D00 | PHASE_HL | 0.164 | 0.162 | 1.014 | 0.000 | 0 | REJECT | hl_adoption.tsv:54 |
| NKD | P5_D00 | SESSION_HL | 0.166 | 0.151 | 1.097 | 0.000 | 0 | REJECT | hl_adoption.tsv:55 |
| NKD | P5_D25 | PHASE_HL | 0.164 | 0.157 | 1.041 | 0.010 | 1 | REJECT | hl_adoption.tsv:56 |
| NKD | P5_D25 | SESSION_HL | 0.188 | 0.147 | 1.279 | 0.007 | 1 | REJECT | hl_adoption.tsv:57 |
| NKD | P5_D50 | PHASE_HL | 0.148 | 0.162 | 0.913 | 0.006 | 0 | REJECT | hl_adoption.tsv:58 |
| NKD | P5_D50 | SESSION_HL | 0.168 | 0.172 | 0.977 | 0.004 | 0 | REJECT | hl_adoption.tsv:59 |
| NKD | P5_D75 | PHASE_HL | 0.103 | 0.144 | 0.715 | 0.004 | 0 | REJECT | hl_adoption.tsv:60 |
| NKD | P5_D75 | SESSION_HL | 0.135 | 0.184 | 0.732 | 0.004 | 0 | REJECT | hl_adoption.tsv:61 |
| NKD | P6_GAPFILL | SESSION_HL | 0.043 | 0.000 | nan | 0.000 | 0 | REJECT | hl_adoption.tsv:62 |
| SI | P1_BASE | PHASE_HL | 0.654 | 0.175 | 3.748 | 0.000 | 1 | REJECT | hl_adoption.tsv:63 |
| SI | P1_BASE | SESSION_HL | 0.177 | 0.062 | 2.881 | 0.000 | 1 | REJECT | hl_adoption.tsv:64 |
| SI | P1_BASE_RS | PHASE_HL | 0.646 | 0.173 | 3.727 | 0.000 | 1 | REJECT | hl_adoption.tsv:65 |
| SI | P1_BASE_RS | SESSION_HL | 0.181 | 0.065 | 2.759 | 0.000 | 1 | REJECT | hl_adoption.tsv:66 |
| SI | P1_SIDE_POPEN | PHASE_HL | 0.670 | 0.188 | 3.568 | 0.028 | 1 | REJECT | hl_adoption.tsv:67 |
| SI | P1_SIDE_SETTLE | SESSION_HL | 0.181 | 0.065 | 2.791 | 0.004 | 1 | REJECT | hl_adoption.tsv:68 |
| SI | P1_SIDE_SOPEN | SESSION_HL | 0.177 | 0.076 | 2.326 | 0.003 | 1 | REJECT | hl_adoption.tsv:69 |
| SI | P2_LOGIT | SESSION_HL | 0.094 | 0.047 | 1.984 | 0.001 | 1 | REJECT | hl_adoption.tsv:70 |
| SI | P2_OLS | SESSION_HL | 0.094 | 0.047 | 2.000 | 0.000 | 0 | REJECT | hl_adoption.tsv:71 |
| SI | P2_UNCOND | SESSION_HL | 0.091 | 0.045 | 2.034 | 0.000 | 1 | REJECT | hl_adoption.tsv:72 |
| SI | P3_OR30 | REST_OF_WINDOW\|LONDON | 0.526 | 0.055 | 9.535 | 0.051 | 1 | ADOPT | hl_adoption.tsv:73 |
| SI | P3_OR30 | REST_OF_WINDOW\|NY | 0.384 | 0.153 | 2.502 | 0.030 | 1 | ADOPT | hl_adoption.tsv:74 |
| SI | P3_OR30 | REST_OF_WINDOW\|SESSION | 0.243 | 0.151 | 1.612 | 0.020 | 1 | REJECT | hl_adoption.tsv:75 |
| SI | P3_OR30 | REST_OF_WINDOW\|TOKYO | 0.460 | 0.066 | 7.017 | 0.063 | 1 | ADOPT | hl_adoption.tsv:76 |
| SI | P3_OR60 | REST_OF_WINDOW\|LONDON | 0.493 | 0.033 | 15.050 | 0.037 | 1 | ADOPT | hl_adoption.tsv:77 |
| SI | P3_OR60 | REST_OF_WINDOW\|NY | 0.385 | 0.150 | 2.564 | 0.026 | 1 | REJECT | hl_adoption.tsv:78 |
| SI | P3_OR60 | REST_OF_WINDOW\|SESSION | 0.268 | 0.158 | 1.693 | 0.019 | 1 | REJECT | hl_adoption.tsv:79 |
| SI | P3_OR60 | REST_OF_WINDOW\|TOKYO | 0.480 | 0.069 | 6.976 | 0.063 | 1 | ADOPT | hl_adoption.tsv:80 |
| SI | P4_CAMARILLA | SESSION_HL | 0.176 | 0.079 | 2.228 | 0.005 | 1 | REJECT | hl_adoption.tsv:81 |
| SI | P4_FLOOR | SESSION_HL | 0.175 | 0.158 | 1.111 | 0.013 | 0 | REJECT | hl_adoption.tsv:82 |
| SI | P5_D00 | PHASE_HL | 0.168 | 0.158 | 1.067 | 0.015 | 0 | REJECT | hl_adoption.tsv:83 |
| SI | P5_D00 | SESSION_HL | 0.154 | 0.149 | 1.033 | 0.009 | 0 | REJECT | hl_adoption.tsv:84 |
| SI | P5_D25 | PHASE_HL | 0.162 | 0.158 | 1.024 | 0.011 | 0 | REJECT | hl_adoption.tsv:85 |
| SI | P5_D25 | SESSION_HL | 0.161 | 0.162 | 0.993 | 0.008 | 0 | REJECT | hl_adoption.tsv:86 |
| SI | P5_D50 | PHASE_HL | 0.134 | 0.178 | 0.753 | 0.008 | 0 | REJECT | hl_adoption.tsv:87 |
| SI | P5_D50 | SESSION_HL | 0.153 | 0.171 | 0.895 | 0.008 | 0 | REJECT | hl_adoption.tsv:88 |
| SI | P5_D75 | PHASE_HL | 0.076 | 0.126 | 0.601 | 0.004 | 0 | REJECT | hl_adoption.tsv:89 |
| SI | P5_D75 | SESSION_HL | 0.105 | 0.135 | 0.781 | 0.007 | 0 | REJECT | hl_adoption.tsv:90 |
| SI | P6_GAPFILL | SESSION_HL | 0.095 | 0.000 | nan | 0.000 | 0 | REJECT | hl_adoption.tsv:91 |

ADOPTED: 6 of 87 (family, target, asset) rows.

## 2. Per-family scores, FIT era (spec §3 a/b/d/f)

| asset | family | target | n_scored | n_extremes | capture | null | lift | med_dist_$ | med_dist_ATR | marginal_pp | kept_cover | file:line |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SI | P1_BASE | PHASE_HL | 5316 | 5496 | 0.654 | 0.175 | 3.748 | 84 | 0.031 | 0.000 | 0.906 | hl_families.tsv:12 |
| SI | P1_BASE | SESSION_HL | 1772 | 1832 | 0.177 | 0.062 | 2.881 | 554 | 0.208 | 0.000 | 0.919 | hl_families.tsv:18 |
| SI | P1_BASE_RS | PHASE_HL | 5316 | 5496 | 0.646 | 0.173 | 3.727 | 84 | 0.031 | 0.000 | 0.906 | hl_families.tsv:24 |
| SI | P1_BASE_RS | SESSION_HL | 1772 | 1832 | 0.181 | 0.065 | 2.759 | 567 | 0.212 | 0.000 | 0.919 | hl_families.tsv:30 |
| SI | P1_SIDE_POPEN | PHASE_HL | 5316 | 5496 | 0.670 | 0.188 | 3.568 | 86 | 0.032 | 0.028 | 0.906 | hl_families.tsv:36 |
| SI | P1_SIDE_SETTLE | SESSION_HL | 1772 | 1832 | 0.181 | 0.065 | 2.791 | 361 | 0.136 | 0.004 | 0.919 | hl_families.tsv:42 |
| SI | P1_SIDE_SOPEN | SESSION_HL | 1772 | 1832 | 0.177 | 0.076 | 2.326 | 357 | 0.134 | 0.003 | 0.919 | hl_families.tsv:48 |
| SI | P2_LOGIT | SESSION_HL | 1292 | 1832 | 0.094 | 0.047 | 1.984 | 791 | 0.292 | 0.001 | 0.919 | hl_families.tsv:53 |
| SI | P2_OLS | SESSION_HL | 1292 | 1832 | 0.094 | 0.047 | 2.000 | 790 | 0.290 | 0.000 | 0.919 | hl_families.tsv:58 |
| SI | P2_UNCOND | SESSION_HL | 1292 | 1832 | 0.091 | 0.045 | 2.034 | 791 | 0.291 | 0.000 | 0.919 | hl_families.tsv:63 |
| SI | P3_OR30 | REST_OF_WINDOW\|LONDON | 1832 | 1832 | 0.526 | 0.055 | 9.535 | 116 | 0.043 | 0.051 | 0.903 | hl_families.tsv:69 |
| SI | P3_OR30 | REST_OF_WINDOW\|NY | 1832 | 1832 | 0.384 | 0.153 | 2.502 | 275 | 0.105 | 0.030 | 0.904 | hl_families.tsv:75 |
| SI | P3_OR30 | REST_OF_WINDOW\|SESSION | 1832 | 1832 | 0.243 | 0.151 | 1.612 | 700 | 0.259 | 0.020 | 0.921 | hl_families.tsv:81 |
| SI | P3_OR30 | REST_OF_WINDOW\|TOKYO | 1832 | 1832 | 0.460 | 0.066 | 7.017 | 162 | 0.061 | 0.063 | 0.906 | hl_families.tsv:87 |
| SI | P3_OR60 | REST_OF_WINDOW\|LONDON | 1832 | 1832 | 0.493 | 0.033 | 15.050 | 138 | 0.052 | 0.037 | 0.903 | hl_families.tsv:93 |
| SI | P3_OR60 | REST_OF_WINDOW\|NY | 1832 | 1832 | 0.385 | 0.150 | 2.564 | 225 | 0.085 | 0.026 | 0.903 | hl_families.tsv:99 |
| SI | P3_OR60 | REST_OF_WINDOW\|SESSION | 1832 | 1832 | 0.268 | 0.158 | 1.693 | 612 | 0.227 | 0.019 | 0.921 | hl_families.tsv:105 |
| SI | P3_OR60 | REST_OF_WINDOW\|TOKYO | 1832 | 1832 | 0.480 | 0.069 | 6.976 | 150 | 0.055 | 0.063 | 0.904 | hl_families.tsv:111 |
| SI | P4_CAMARILLA | SESSION_HL | 1832 | 1832 | 0.176 | 0.079 | 2.228 | 440 | 0.162 | 0.005 | 0.919 | hl_families.tsv:117 |
| SI | P4_FLOOR | SESSION_HL | 1832 | 1832 | 0.175 | 0.158 | 1.111 | 400 | 0.150 | 0.013 | 0.919 | hl_families.tsv:123 |
| SI | P5_D00 | PHASE_HL | 5496 | 5496 | 0.168 | 0.158 | 1.067 | 575 | 0.210 | 0.015 | 0.906 | hl_families.tsv:129 |
| SI | P5_D00 | SESSION_HL | 1832 | 1832 | 0.154 | 0.149 | 1.033 | 650 | 0.243 | 0.009 | 0.919 | hl_families.tsv:135 |
| SI | P5_D25 | PHASE_HL | 5496 | 5496 | 0.162 | 0.158 | 1.024 | 612 | 0.232 | 0.011 | 0.906 | hl_families.tsv:141 |
| SI | P5_D25 | SESSION_HL | 1832 | 1832 | 0.161 | 0.162 | 0.993 | 625 | 0.242 | 0.008 | 0.919 | hl_families.tsv:147 |
| SI | P5_D50 | PHASE_HL | 5496 | 5496 | 0.134 | 0.178 | 0.753 | 800 | 0.299 | 0.008 | 0.906 | hl_families.tsv:153 |
| SI | P5_D50 | SESSION_HL | 1832 | 1832 | 0.153 | 0.171 | 0.895 | 700 | 0.255 | 0.008 | 0.919 | hl_families.tsv:159 |
| SI | P5_D75 | PHASE_HL | 5496 | 5496 | 0.076 | 0.126 | 0.601 | 1369 | 0.506 | 0.004 | 0.906 | hl_families.tsv:165 |
| SI | P5_D75 | SESSION_HL | 1832 | 1832 | 0.105 | 0.135 | 0.781 | 950 | 0.371 | 0.007 | 0.919 | hl_families.tsv:171 |
| SI | P6_GAPFILL | SESSION_HL | 21 | 1832 | 0.095 | 0.000 | nan | 788 | 0.296 | 0.000 | 0.919 | hl_families.tsv:176 |
| HG | P1_BASE | PHASE_HL | 5946 | 6126 | 0.638 | 0.193 | 3.300 | 63 | 0.033 | 0.000 | 0.945 | hl_families.tsv:182 |
| HG | P1_BASE | SESSION_HL | 1982 | 2042 | 0.179 | 0.060 | 3.000 | 464 | 0.241 | 0.000 | 0.945 | hl_families.tsv:188 |
| HG | P1_BASE_RS | PHASE_HL | 5946 | 6126 | 0.632 | 0.188 | 3.362 | 64 | 0.034 | 0.000 | 0.945 | hl_families.tsv:194 |
| HG | P1_BASE_RS | SESSION_HL | 1982 | 2042 | 0.167 | 0.058 | 2.904 | 477 | 0.246 | 0.000 | 0.945 | hl_families.tsv:200 |
| HG | P1_SIDE_POPEN | PHASE_HL | 5946 | 6126 | 0.644 | 0.210 | 3.069 | 64 | 0.034 | 0.021 | 0.945 | hl_families.tsv:206 |
| HG | P1_SIDE_SETTLE | SESSION_HL | 1982 | 2042 | 0.182 | 0.076 | 2.391 | 255 | 0.132 | 0.006 | 0.945 | hl_families.tsv:212 |
| HG | P1_SIDE_SOPEN | SESSION_HL | 1982 | 2042 | 0.170 | 0.073 | 2.324 | 253 | 0.134 | 0.004 | 0.945 | hl_families.tsv:218 |
| HG | P2_LOGIT | SESSION_HL | 1506 | 2042 | 0.074 | 0.032 | 2.333 | 578 | 0.318 | 0.000 | 0.945 | hl_families.tsv:223 |
| HG | P2_OLS | SESSION_HL | 1506 | 2042 | 0.080 | 0.031 | 2.574 | 578 | 0.315 | 0.000 | 0.945 | hl_families.tsv:228 |
| HG | P2_UNCOND | SESSION_HL | 1506 | 2042 | 0.080 | 0.031 | 2.630 | 579 | 0.319 | 0.001 | 0.945 | hl_families.tsv:233 |
| HG | P3_OR30 | REST_OF_WINDOW\|LONDON | 2042 | 2042 | 0.419 | 0.047 | 8.917 | 138 | 0.073 | 0.028 | 0.944 | hl_families.tsv:239 |
| HG | P3_OR30 | REST_OF_WINDOW\|NY | 2042 | 2042 | 0.397 | 0.157 | 2.523 | 164 | 0.088 | 0.022 | 0.939 | hl_families.tsv:245 |
| HG | P3_OR30 | REST_OF_WINDOW\|SESSION | 2042 | 2042 | 0.231 | 0.166 | 1.393 | 481 | 0.259 | 0.012 | 0.944 | hl_families.tsv:251 |
| HG | P3_OR30 | REST_OF_WINDOW\|TOKYO | 2042 | 2042 | 0.402 | 0.097 | 4.121 | 156 | 0.083 | 0.023 | 0.957 | hl_families.tsv:257 |
| HG | P3_OR60 | REST_OF_WINDOW\|LONDON | 2042 | 2042 | 0.323 | 0.032 | 9.985 | 203 | 0.108 | 0.018 | 0.950 | hl_families.tsv:263 |
| HG | P3_OR60 | REST_OF_WINDOW\|NY | 2042 | 2042 | 0.404 | 0.128 | 3.157 | 147 | 0.077 | 0.021 | 0.938 | hl_families.tsv:269 |
| HG | P3_OR60 | REST_OF_WINDOW\|SESSION | 2042 | 2042 | 0.263 | 0.169 | 1.557 | 425 | 0.233 | 0.014 | 0.945 | hl_families.tsv:275 |
| HG | P3_OR60 | REST_OF_WINDOW\|TOKYO | 2042 | 2042 | 0.433 | 0.100 | 4.312 | 142 | 0.072 | 0.024 | 0.958 | hl_families.tsv:281 |
| HG | P4_CAMARILLA | SESSION_HL | 2042 | 2042 | 0.173 | 0.090 | 1.929 | 291 | 0.152 | 0.007 | 0.945 | hl_families.tsv:287 |
| HG | P4_FLOOR | SESSION_HL | 2042 | 2042 | 0.167 | 0.149 | 1.122 | 290 | 0.153 | 0.005 | 0.945 | hl_families.tsv:293 |
| HG | P5_D00 | PHASE_HL | 6126 | 6126 | 0.159 | 0.173 | 0.915 | 425 | 0.218 | 0.000 | 0.945 | hl_families.tsv:299 |
| HG | P5_D00 | SESSION_HL | 2042 | 2042 | 0.151 | 0.171 | 0.883 | 422 | 0.218 | 0.000 | 0.945 | hl_families.tsv:305 |
| HG | P5_D25 | PHASE_HL | 6126 | 6126 | 0.159 | 0.179 | 0.893 | 456 | 0.240 | 0.007 | 0.945 | hl_families.tsv:311 |
| HG | P5_D25 | SESSION_HL | 2042 | 2042 | 0.170 | 0.175 | 0.972 | 419 | 0.220 | 0.007 | 0.945 | hl_families.tsv:317 |
| HG | P5_D50 | PHASE_HL | 6126 | 6126 | 0.128 | 0.159 | 0.807 | 550 | 0.283 | 0.003 | 0.945 | hl_families.tsv:323 |
| HG | P5_D50 | SESSION_HL | 2042 | 2042 | 0.150 | 0.170 | 0.882 | 462 | 0.232 | 0.003 | 0.945 | hl_families.tsv:329 |
| HG | P5_D75 | PHASE_HL | 6126 | 6126 | 0.100 | 0.124 | 0.806 | 862 | 0.453 | 0.005 | 0.945 | hl_families.tsv:335 |
| HG | P5_D75 | SESSION_HL | 2042 | 2042 | 0.125 | 0.151 | 0.828 | 628 | 0.328 | 0.004 | 0.945 | hl_families.tsv:341 |
| HG | P6_GAPFILL | SESSION_HL | 22 | 2042 | 0.045 | 0.045 | 1.000 | 888 | 0.435 | 0.000 | 0.945 | hl_families.tsv:347 |
| NKD | P1_BASE | PHASE_HL | 5958 | 6138 | 0.683 | 0.196 | 3.486 | 66 | 0.029 | 0.000 | 0.951 | hl_families.tsv:353 |
| NKD | P1_BASE | SESSION_HL | 1986 | 2046 | 0.185 | 0.072 | 2.573 | 437 | 0.198 | 0.000 | 0.953 | hl_families.tsv:359 |
| NKD | P1_BASE_RS | PHASE_HL | 5958 | 6138 | 0.677 | 0.191 | 3.539 | 67 | 0.029 | 0.000 | 0.951 | hl_families.tsv:365 |
| NKD | P1_BASE_RS | SESSION_HL | 1986 | 2046 | 0.200 | 0.069 | 2.877 | 447 | 0.201 | 0.000 | 0.953 | hl_families.tsv:371 |
| NKD | P1_SIDE_POPEN | PHASE_HL | 5958 | 6138 | 0.709 | 0.208 | 3.399 | 67 | 0.030 | 0.013 | 0.951 | hl_families.tsv:377 |
| NKD | P1_SIDE_SETTLE | SESSION_HL | 1986 | 2046 | 0.208 | 0.079 | 2.647 | 293 | 0.131 | 0.003 | 0.953 | hl_families.tsv:383 |
| NKD | P1_SIDE_SOPEN | SESSION_HL | 1986 | 2046 | 0.191 | 0.078 | 2.461 | 297 | 0.133 | 0.004 | 0.953 | hl_families.tsv:389 |
| NKD | P2_LOGIT | SESSION_HL | 1508 | 2046 | 0.072 | 0.034 | 2.118 | 687 | 0.293 | 0.000 | 0.953 | hl_families.tsv:394 |
| NKD | P2_OLS | SESSION_HL | 1508 | 2046 | 0.080 | 0.032 | 2.500 | 678 | 0.297 | 0.000 | 0.953 | hl_families.tsv:399 |
| NKD | P2_UNCOND | SESSION_HL | 1508 | 2046 | 0.082 | 0.034 | 2.385 | 674 | 0.292 | 0.000 | 0.953 | hl_families.tsv:404 |
| NKD | P3_OR30 | REST_OF_WINDOW\|LONDON | 2046 | 2046 | 0.585 | 0.023 | 25.447 | 81 | 0.034 | 0.032 | 0.947 | hl_families.tsv:410 |
| NKD | P3_OR30 | REST_OF_WINDOW\|NY | 2046 | 2046 | 0.431 | 0.117 | 3.675 | 175 | 0.075 | 0.028 | 0.941 | hl_families.tsv:416 |
| NKD | P3_OR30 | REST_OF_WINDOW\|SESSION | 2046 | 2046 | 0.296 | 0.163 | 1.811 | 388 | 0.175 | 0.011 | 0.957 | hl_families.tsv:422 |
| NKD | P3_OR30 | REST_OF_WINDOW\|TOKYO | 2046 | 2046 | 0.383 | 0.119 | 3.209 | 212 | 0.094 | 0.019 | 0.963 | hl_families.tsv:428 |
| NKD | P3_OR60 | REST_OF_WINDOW\|LONDON | 2046 | 2046 | 0.525 | 0.015 | 34.677 | 103 | 0.045 | 0.025 | 0.944 | hl_families.tsv:434 |
| NKD | P3_OR60 | REST_OF_WINDOW\|NY | 2046 | 2046 | 0.449 | 0.111 | 4.031 | 144 | 0.062 | 0.024 | 0.943 | hl_families.tsv:440 |
| NKD | P3_OR60 | REST_OF_WINDOW\|SESSION | 2046 | 2046 | 0.316 | 0.163 | 1.943 | 319 | 0.138 | 0.011 | 0.958 | hl_families.tsv:446 |
| NKD | P3_OR60 | REST_OF_WINDOW\|TOKYO | 2046 | 2046 | 0.384 | 0.110 | 3.493 | 200 | 0.088 | 0.017 | 0.965 | hl_families.tsv:452 |
| NKD | P4_CAMARILLA | SESSION_HL | 2046 | 2046 | 0.180 | 0.081 | 2.236 | 337 | 0.148 | 0.004 | 0.953 | hl_families.tsv:458 |
| NKD | P4_FLOOR | SESSION_HL | 2046 | 2046 | 0.168 | 0.166 | 1.009 | 329 | 0.148 | 0.007 | 0.953 | hl_families.tsv:464 |
| NKD | P5_D00 | PHASE_HL | 6138 | 6138 | 0.164 | 0.162 | 1.014 | 525 | 0.230 | 0.000 | 0.951 | hl_families.tsv:470 |
| NKD | P5_D00 | SESSION_HL | 2046 | 2046 | 0.166 | 0.151 | 1.097 | 475 | 0.210 | 0.000 | 0.953 | hl_families.tsv:476 |
| NKD | P5_D25 | PHASE_HL | 6138 | 6138 | 0.164 | 0.157 | 1.041 | 562 | 0.243 | 0.010 | 0.951 | hl_families.tsv:482 |
| NKD | P5_D25 | SESSION_HL | 2046 | 2046 | 0.188 | 0.147 | 1.279 | 475 | 0.200 | 0.007 | 0.953 | hl_families.tsv:488 |
| NKD | P5_D50 | PHASE_HL | 6138 | 6138 | 0.148 | 0.162 | 0.913 | 662 | 0.285 | 0.006 | 0.951 | hl_families.tsv:494 |
| NKD | P5_D50 | SESSION_HL | 2046 | 2046 | 0.168 | 0.172 | 0.977 | 500 | 0.219 | 0.004 | 0.953 | hl_families.tsv:500 |
| NKD | P5_D75 | PHASE_HL | 6138 | 6138 | 0.103 | 0.144 | 0.715 | 1038 | 0.458 | 0.004 | 0.951 | hl_families.tsv:506 |
| NKD | P5_D75 | SESSION_HL | 2046 | 2046 | 0.135 | 0.184 | 0.732 | 750 | 0.322 | 0.004 | 0.953 | hl_families.tsv:512 |
| NKD | P6_GAPFILL | SESSION_HL | 23 | 2046 | 0.043 | 0.000 | nan | 738 | 0.291 | 0.000 | 0.953 | hl_families.tsv:518 |

### 2025 GATE echo (evaluation only, never a selection input)

| asset | family | target | capture | null | lift | file:line |
|---|---|---|---|---|---|---|
| SI | P1_BASE | PHASE_HL | 0.615 | 0.182 | 3.376 | hl_families.tsv:13 |
| SI | P1_BASE | SESSION_HL | 0.157 | 0.091 | 1.723 | hl_families.tsv:19 |
| SI | P1_BASE_RS | PHASE_HL | 0.599 | 0.181 | 3.314 | hl_families.tsv:25 |
| SI | P1_BASE_RS | SESSION_HL | 0.165 | 0.085 | 1.932 | hl_families.tsv:31 |
| SI | P1_SIDE_POPEN | PHASE_HL | 0.636 | 0.191 | 3.324 | hl_families.tsv:37 |
| SI | P1_SIDE_SETTLE | SESSION_HL | 0.169 | 0.064 | 2.636 | hl_families.tsv:43 |
| SI | P1_SIDE_SOPEN | SESSION_HL | 0.155 | 0.072 | 2.162 | hl_families.tsv:49 |
| SI | P2_LOGIT | SESSION_HL | 0.093 | 0.050 | 1.846 | hl_families.tsv:54 |
| SI | P2_OLS | SESSION_HL | 0.091 | 0.045 | 2.043 | hl_families.tsv:59 |
| SI | P2_UNCOND | SESSION_HL | 0.083 | 0.045 | 1.870 | hl_families.tsv:64 |
| SI | P3_OR30 | REST_OF_WINDOW\|LONDON | 0.448 | 0.037 | 12.158 | hl_families.tsv:70 |
| SI | P3_OR30 | REST_OF_WINDOW\|NY | 0.386 | 0.163 | 2.369 | hl_families.tsv:76 |
| SI | P3_OR30 | REST_OF_WINDOW\|SESSION | 0.269 | 0.143 | 1.878 | hl_families.tsv:82 |
| SI | P3_OR30 | REST_OF_WINDOW\|TOKYO | 0.438 | 0.076 | 5.795 | hl_families.tsv:88 |
| SI | P3_OR60 | REST_OF_WINDOW\|LONDON | 0.351 | 0.021 | 16.455 | hl_families.tsv:94 |
| SI | P3_OR60 | REST_OF_WINDOW\|NY | 0.411 | 0.149 | 2.753 | hl_families.tsv:100 |
| SI | P3_OR60 | REST_OF_WINDOW\|SESSION | 0.273 | 0.147 | 1.855 | hl_families.tsv:106 |
| SI | P3_OR60 | REST_OF_WINDOW\|TOKYO | 0.436 | 0.079 | 5.488 | hl_families.tsv:112 |
| SI | P4_CAMARILLA | SESSION_HL | 0.172 | 0.068 | 2.543 | hl_families.tsv:118 |
| SI | P4_FLOOR | SESSION_HL | 0.138 | 0.161 | 0.855 | hl_families.tsv:124 |
| SI | P5_D00 | PHASE_HL | 0.153 | 0.156 | 0.983 | hl_families.tsv:130 |
| SI | P5_D00 | SESSION_HL | 0.124 | 0.153 | 0.810 | hl_families.tsv:136 |
| SI | P5_D25 | PHASE_HL | 0.147 | 0.161 | 0.912 | hl_families.tsv:142 |
| SI | P5_D25 | SESSION_HL | 0.151 | 0.176 | 0.857 | hl_families.tsv:148 |
| SI | P5_D50 | PHASE_HL | 0.127 | 0.165 | 0.770 | hl_families.tsv:154 |
| SI | P5_D50 | SESSION_HL | 0.141 | 0.174 | 0.811 | hl_families.tsv:160 |
| SI | P5_D75 | PHASE_HL | 0.099 | 0.132 | 0.750 | hl_families.tsv:166 |
| SI | P5_D75 | SESSION_HL | 0.097 | 0.157 | 0.617 | hl_families.tsv:172 |
| SI | P6_GAPFILL | SESSION_HL | 0.100 | 0.100 | 1.000 | hl_families.tsv:177 |
| HG | P1_BASE | PHASE_HL | 0.601 | 0.145 | 4.138 | hl_families.tsv:183 |
| HG | P1_BASE | SESSION_HL | 0.171 | 0.060 | 2.839 | hl_families.tsv:189 |
| HG | P1_BASE_RS | PHASE_HL | 0.610 | 0.138 | 4.416 | hl_families.tsv:195 |
| HG | P1_BASE_RS | SESSION_HL | 0.176 | 0.064 | 2.758 | hl_families.tsv:201 |
| HG | P1_SIDE_POPEN | PHASE_HL | 0.627 | 0.155 | 4.046 | hl_families.tsv:207 |
| HG | P1_SIDE_SETTLE | SESSION_HL | 0.190 | 0.079 | 2.390 | hl_families.tsv:213 |
| HG | P1_SIDE_SOPEN | SESSION_HL | 0.211 | 0.066 | 3.206 | hl_families.tsv:219 |
| HG | P2_LOGIT | SESSION_HL | 0.078 | 0.029 | 2.667 | hl_families.tsv:224 |
| HG | P2_OLS | SESSION_HL | 0.072 | 0.029 | 2.467 | hl_families.tsv:229 |
| HG | P2_UNCOND | SESSION_HL | 0.079 | 0.029 | 2.733 | hl_families.tsv:234 |
| HG | P3_OR30 | REST_OF_WINDOW\|LONDON | 0.498 | 0.027 | 18.357 | hl_families.tsv:240 |
| HG | P3_OR30 | REST_OF_WINDOW\|NY | 0.397 | 0.138 | 2.887 | hl_families.tsv:246 |
| HG | P3_OR30 | REST_OF_WINDOW\|SESSION | 0.287 | 0.116 | 2.467 | hl_families.tsv:252 |
| HG | P3_OR30 | REST_OF_WINDOW\|TOKYO | 0.434 | 0.079 | 5.463 | hl_families.tsv:258 |
| HG | P3_OR60 | REST_OF_WINDOW\|LONDON | 0.382 | 0.019 | 19.700 | hl_families.tsv:264 |
| HG | P3_OR60 | REST_OF_WINDOW\|NY | 0.428 | 0.130 | 3.299 | hl_families.tsv:270 |
| HG | P3_OR60 | REST_OF_WINDOW\|SESSION | 0.326 | 0.130 | 2.507 | hl_families.tsv:276 |
| HG | P3_OR60 | REST_OF_WINDOW\|TOKYO | 0.471 | 0.079 | 5.927 | hl_families.tsv:282 |
| HG | P4_CAMARILLA | SESSION_HL | 0.194 | 0.068 | 2.857 | hl_families.tsv:288 |
| HG | P4_FLOOR | SESSION_HL | 0.176 | 0.141 | 1.247 | hl_families.tsv:294 |
| HG | P5_D00 | PHASE_HL | 0.185 | 0.169 | 1.095 | hl_families.tsv:300 |
| HG | P5_D00 | SESSION_HL | 0.200 | 0.192 | 1.040 | hl_families.tsv:306 |
| HG | P5_D25 | PHASE_HL | 0.171 | 0.155 | 1.100 | hl_families.tsv:312 |
| HG | P5_D25 | SESSION_HL | 0.198 | 0.149 | 1.325 | hl_families.tsv:318 |
| HG | P5_D50 | PHASE_HL | 0.146 | 0.152 | 0.962 | hl_families.tsv:324 |
| HG | P5_D50 | SESSION_HL | 0.151 | 0.126 | 1.200 | hl_families.tsv:330 |
| HG | P5_D75 | PHASE_HL | 0.128 | 0.152 | 0.839 | hl_families.tsv:336 |
| HG | P5_D75 | SESSION_HL | 0.151 | 0.159 | 0.951 | hl_families.tsv:342 |
| HG | P6_GAPFILL | SESSION_HL | 0.077 | 0.077 | 1.000 | hl_families.tsv:348 |
| NKD | P1_BASE | PHASE_HL | 0.647 | 0.174 | 3.721 | hl_families.tsv:354 |
| NKD | P1_BASE | SESSION_HL | 0.155 | 0.066 | 2.353 | hl_families.tsv:360 |
| NKD | P1_BASE_RS | PHASE_HL | 0.641 | 0.164 | 3.902 | hl_families.tsv:366 |
| NKD | P1_BASE_RS | SESSION_HL | 0.149 | 0.078 | 1.925 | hl_families.tsv:372 |
| NKD | P1_SIDE_POPEN | PHASE_HL | 0.699 | 0.193 | 3.615 | hl_families.tsv:378 |
| NKD | P1_SIDE_SETTLE | SESSION_HL | 0.149 | 0.089 | 1.674 | hl_families.tsv:384 |
| NKD | P1_SIDE_SOPEN | SESSION_HL | 0.165 | 0.058 | 2.833 | hl_families.tsv:390 |
| NKD | P2_LOGIT | SESSION_HL | 0.074 | 0.047 | 1.583 | hl_families.tsv:395 |
| NKD | P2_OLS | SESSION_HL | 0.076 | 0.047 | 1.625 | hl_families.tsv:400 |
| NKD | P2_UNCOND | SESSION_HL | 0.072 | 0.048 | 1.480 | hl_families.tsv:405 |
| NKD | P3_OR30 | REST_OF_WINDOW\|LONDON | 0.615 | 0.018 | 35.111 | hl_families.tsv:411 |
| NKD | P3_OR30 | REST_OF_WINDOW\|NY | 0.413 | 0.101 | 4.096 | hl_families.tsv:417 |
| NKD | P3_OR30 | REST_OF_WINDOW\|SESSION | 0.266 | 0.145 | 1.827 | hl_families.tsv:423 |
| NKD | P3_OR30 | REST_OF_WINDOW\|TOKYO | 0.353 | 0.140 | 2.528 | hl_families.tsv:429 |
| NKD | P3_OR60 | REST_OF_WINDOW\|LONDON | 0.533 | 0.012 | 45.667 | hl_families.tsv:435 |
| NKD | P3_OR60 | REST_OF_WINDOW\|NY | 0.461 | 0.081 | 5.667 | hl_families.tsv:441 |
| NKD | P3_OR60 | REST_OF_WINDOW\|SESSION | 0.295 | 0.149 | 1.974 | hl_families.tsv:447 |
| NKD | P3_OR60 | REST_OF_WINDOW\|TOKYO | 0.343 | 0.114 | 3.000 | hl_families.tsv:453 |
| NKD | P4_CAMARILLA | SESSION_HL | 0.180 | 0.079 | 2.268 | hl_families.tsv:459 |
| NKD | P4_FLOOR | SESSION_HL | 0.207 | 0.147 | 1.408 | hl_families.tsv:465 |
| NKD | P5_D00 | PHASE_HL | 0.181 | 0.159 | 1.138 | hl_families.tsv:471 |
| NKD | P5_D00 | SESSION_HL | 0.174 | 0.149 | 1.169 | hl_families.tsv:477 |
| NKD | P5_D25 | PHASE_HL | 0.169 | 0.160 | 1.057 | hl_families.tsv:483 |
| NKD | P5_D25 | SESSION_HL | 0.174 | 0.153 | 1.139 | hl_families.tsv:489 |
| NKD | P5_D50 | PHASE_HL | 0.159 | 0.157 | 1.017 | hl_families.tsv:495 |
| NKD | P5_D50 | SESSION_HL | 0.190 | 0.159 | 1.195 | hl_families.tsv:501 |
| NKD | P5_D75 | PHASE_HL | 0.123 | 0.161 | 0.763 | hl_families.tsv:507 |
| NKD | P5_D75 | SESSION_HL | 0.157 | 0.182 | 0.862 | hl_families.tsv:513 |
| NKD | P6_GAPFILL | SESSION_HL | 0.118 | 0.059 | 2.000 | hl_families.tsv:519 |

## 3. Per-FIT-year lift (spec §3e era stability)

| asset | family | target | 2021 | 2022 | 2023 | 2024 | file:line |
|---|---|---|---|---|---|---|---|
| HG | P1_BASE | PHASE_HL | 3.53 | 2.79 | 3.74 | 3.48 | hl_families.tsv:178,179,180,181 |
| HG | P1_BASE | SESSION_HL | 2.96 | 2.92 | 2.62 | 3.73 | hl_families.tsv:184,185,186,187 |
| HG | P1_BASE_RS | PHASE_HL | 3.56 | 2.95 | 3.76 | 3.43 | hl_families.tsv:190,191,192,193 |
| HG | P1_BASE_RS | SESSION_HL | 2.77 | 2.78 | 2.92 | 3.20 | hl_families.tsv:196,197,198,199 |
| HG | P1_SIDE_POPEN | PHASE_HL | 3.32 | 2.74 | 3.22 | 3.16 | hl_families.tsv:202,203,204,205 |
| HG | P1_SIDE_SETTLE | SESSION_HL | 2.86 | 2.49 | 2.00 | 2.35 | hl_families.tsv:208,209,210,211 |
| HG | P1_SIDE_SOPEN | SESSION_HL | 2.89 | 2.33 | 1.83 | 2.47 | hl_families.tsv:214,215,216,217 |
| HG | P2_LOGIT | SESSION_HL | - | 2.43 | 2.80 | 1.89 | hl_families.tsv:220,221,222 |
| HG | P2_OLS | SESSION_HL | - | 3.15 | 2.94 | 1.83 | hl_families.tsv:225,226,227 |
| HG | P2_UNCOND | SESSION_HL | - | 2.43 | 3.62 | 2.11 | hl_families.tsv:230,231,232 |
| HG | P3_OR30 | REST_OF_WINDOW\|LONDON | 4.85 | 9.09 | 23.12 | 12.58 | hl_families.tsv:235,236,237,238 |
| HG | P3_OR30 | REST_OF_WINDOW\|NY | 2.24 | 2.74 | 2.85 | 2.33 | hl_families.tsv:241,242,243,244 |
| HG | P3_OR30 | REST_OF_WINDOW\|SESSION | 1.81 | 1.40 | 1.10 | 1.38 | hl_families.tsv:247,248,249,250 |
| HG | P3_OR30 | REST_OF_WINDOW\|TOKYO | 6.41 | 5.59 | 2.67 | 3.51 | hl_families.tsv:253,254,255,256 |
| HG | P3_OR60 | REST_OF_WINDOW\|LONDON | 5.42 | 12.23 | 21.40 | 16.50 | hl_families.tsv:259,260,261,262 |
| HG | P3_OR60 | REST_OF_WINDOW\|NY | 3.06 | 3.31 | 3.15 | 3.13 | hl_families.tsv:265,266,267,268 |
| HG | P3_OR60 | REST_OF_WINDOW\|SESSION | 2.15 | 1.52 | 1.20 | 1.55 | hl_families.tsv:271,272,273,274 |
| HG | P3_OR60 | REST_OF_WINDOW\|TOKYO | 7.55 | 5.13 | 3.00 | 3.49 | hl_families.tsv:277,278,279,280 |
| HG | P4_CAMARILLA | SESSION_HL | 2.70 | 1.62 | 1.89 | 1.69 | hl_families.tsv:283,284,285,286 |
| HG | P4_FLOOR | SESSION_HL | 1.04 | 1.38 | 1.07 | 0.99 | hl_families.tsv:289,290,291,292 |
| HG | P5_D00 | PHASE_HL | 0.84 | 0.81 | 0.89 | 1.15 | hl_families.tsv:295,296,297,298 |
| HG | P5_D00 | SESSION_HL | 0.76 | 0.71 | 0.95 | 1.12 | hl_families.tsv:301,302,303,304 |
| HG | P5_D25 | PHASE_HL | 0.86 | 0.86 | 0.99 | 0.87 | hl_families.tsv:307,308,309,310 |
| HG | P5_D25 | SESSION_HL | 0.95 | 0.96 | 1.25 | 0.79 | hl_families.tsv:313,314,315,316 |
| HG | P5_D50 | PHASE_HL | 0.79 | 0.86 | 0.86 | 0.73 | hl_families.tsv:319,320,321,322 |
| HG | P5_D50 | SESSION_HL | 0.87 | 1.02 | 0.87 | 0.77 | hl_families.tsv:325,326,327,328 |
| HG | P5_D75 | PHASE_HL | 0.79 | 0.83 | 0.76 | 0.83 | hl_families.tsv:331,332,333,334 |
| HG | P5_D75 | SESSION_HL | 0.87 | 0.83 | 0.85 | 0.78 | hl_families.tsv:337,338,339,340 |
| HG | P6_GAPFILL | SESSION_HL | nan | 1.00 | nan | nan | hl_families.tsv:343,344,345,346 |
| NKD | P1_BASE | PHASE_HL | 3.94 | 3.11 | 3.47 | 3.66 | hl_families.tsv:349,350,351,352 |
| NKD | P1_BASE | SESSION_HL | 2.46 | 2.58 | 2.59 | 2.64 | hl_families.tsv:355,356,357,358 |
| NKD | P1_BASE_RS | PHASE_HL | 3.97 | 3.16 | 3.40 | 3.90 | hl_families.tsv:361,362,363,364 |
| NKD | P1_BASE_RS | SESSION_HL | 3.35 | 2.62 | 2.91 | 2.90 | hl_families.tsv:367,368,369,370 |
| NKD | P1_SIDE_POPEN | PHASE_HL | 3.89 | 3.03 | 3.31 | 3.58 | hl_families.tsv:373,374,375,376 |
| NKD | P1_SIDE_SETTLE | SESSION_HL | 2.96 | 2.80 | 2.75 | 2.17 | hl_families.tsv:379,380,381,382 |
| NKD | P1_SIDE_SOPEN | SESSION_HL | 2.59 | 2.80 | 2.24 | 2.24 | hl_families.tsv:385,386,387,388 |
| NKD | P2_LOGIT | SESSION_HL | - | 2.53 | 1.81 | 2.05 | hl_families.tsv:391,392,393 |
| NKD | P2_OLS | SESSION_HL | - | 4.60 | 2.38 | 1.64 | hl_families.tsv:396,397,398 |
| NKD | P2_UNCOND | SESSION_HL | - | 3.31 | 2.41 | 1.82 | hl_families.tsv:401,402,403 |
| NKD | P3_OR30 | REST_OF_WINDOW\|LONDON | 23.54 | 26.50 | 42.00 | 18.53 | hl_families.tsv:406,407,408,409 |
| NKD | P3_OR30 | REST_OF_WINDOW\|NY | 4.56 | 3.54 | 3.23 | 3.55 | hl_families.tsv:412,413,414,415 |
| NKD | P3_OR30 | REST_OF_WINDOW\|SESSION | 1.75 | 1.85 | 1.77 | 1.87 | hl_families.tsv:418,419,420,421 |
| NKD | P3_OR30 | REST_OF_WINDOW\|TOKYO | 2.63 | 3.70 | 2.69 | 4.30 | hl_families.tsv:424,425,426,427 |
| NKD | P3_OR60 | REST_OF_WINDOW\|LONDON | 40.33 | 28.70 | 26.90 | 55.40 | hl_families.tsv:430,431,432,433 |
| NKD | P3_OR60 | REST_OF_WINDOW\|NY | 5.65 | 3.78 | 3.50 | 3.69 | hl_families.tsv:436,437,438,439 |
| NKD | P3_OR60 | REST_OF_WINDOW\|SESSION | 2.16 | 1.74 | 1.85 | 2.06 | hl_families.tsv:442,443,444,445 |
| NKD | P3_OR60 | REST_OF_WINDOW\|TOKYO | 2.60 | 4.08 | 3.22 | 4.60 | hl_families.tsv:448,449,450,451 |
| NKD | P4_CAMARILLA | SESSION_HL | 2.58 | 1.54 | 3.20 | 2.21 | hl_families.tsv:454,455,456,457 |
| NKD | P4_FLOOR | SESSION_HL | 0.94 | 1.00 | 0.99 | 1.11 | hl_families.tsv:460,461,462,463 |
| NKD | P5_D00 | PHASE_HL | 1.07 | 1.00 | 1.02 | 0.98 | hl_families.tsv:466,467,468,469 |
| NKD | P5_D00 | SESSION_HL | 1.11 | 1.00 | 1.05 | 1.22 | hl_families.tsv:472,473,474,475 |
| NKD | P5_D25 | PHASE_HL | 1.04 | 1.09 | 1.01 | 1.03 | hl_families.tsv:478,479,480,481 |
| NKD | P5_D25 | SESSION_HL | 1.43 | 1.18 | 1.05 | 1.50 | hl_families.tsv:484,485,486,487 |
| NKD | P5_D50 | PHASE_HL | 0.85 | 0.88 | 0.96 | 0.96 | hl_families.tsv:490,491,492,493 |
| NKD | P5_D50 | SESSION_HL | 0.90 | 0.77 | 1.20 | 1.09 | hl_families.tsv:496,497,498,499 |
| NKD | P5_D75 | PHASE_HL | 0.68 | 0.66 | 0.70 | 0.80 | hl_families.tsv:502,503,504,505 |
| NKD | P5_D75 | SESSION_HL | 0.67 | 0.64 | 0.74 | 0.87 | hl_families.tsv:508,509,510,511 |
| NKD | P6_GAPFILL | SESSION_HL | nan | nan | nan | nan | hl_families.tsv:514,515,516,517 |
| SI | P1_BASE | PHASE_HL | 3.91 | 3.22 | 4.10 | 4.05 | hl_families.tsv:8,9,10,11 |
| SI | P1_BASE | SESSION_HL | 3.25 | 2.02 | 4.05 | 3.25 | hl_families.tsv:14,15,16,17 |
| SI | P1_BASE_RS | PHASE_HL | 3.78 | 3.28 | 4.12 | 3.91 | hl_families.tsv:20,21,22,23 |
| SI | P1_BASE_RS | SESSION_HL | 2.54 | 2.08 | 3.91 | 3.14 | hl_families.tsv:26,27,28,29 |
| SI | P1_SIDE_POPEN | PHASE_HL | 3.48 | 2.96 | 4.26 | 3.83 | hl_families.tsv:32,33,34,35 |
| SI | P1_SIDE_SETTLE | SESSION_HL | 3.23 | 2.82 | 3.17 | 2.26 | hl_families.tsv:38,39,40,41 |
| SI | P1_SIDE_SOPEN | SESSION_HL | 3.23 | 2.29 | 2.47 | 1.98 | hl_families.tsv:44,45,46,47 |
| SI | P2_LOGIT | SESSION_HL | - | 1.17 | 2.81 | 1.86 | hl_families.tsv:50,51,52 |
| SI | P2_OLS | SESSION_HL | - | 0.95 | 2.95 | 2.15 | hl_families.tsv:55,56,57 |
| SI | P2_UNCOND | SESSION_HL | - | 1.35 | 3.00 | 1.95 | hl_families.tsv:60,61,62 |
| SI | P3_OR30 | REST_OF_WINDOW\|LONDON | 14.09 | 6.00 | 6.72 | 35.88 | hl_families.tsv:65,66,67,68 |
| SI | P3_OR30 | REST_OF_WINDOW\|NY | 2.22 | 2.75 | 2.66 | 2.28 | hl_families.tsv:71,72,73,74 |
| SI | P3_OR30 | REST_OF_WINDOW\|SESSION | 2.22 | 1.32 | 1.49 | 1.81 | hl_families.tsv:77,78,79,80 |
| SI | P3_OR30 | REST_OF_WINDOW\|TOKYO | 11.31 | 8.28 | 9.15 | 4.17 | hl_families.tsv:83,84,85,86 |
| SI | P3_OR60 | REST_OF_WINDOW\|LONDON | 17.88 | 8.19 | 15.78 | 74.00 | hl_families.tsv:89,90,91,92 |
| SI | P3_OR60 | REST_OF_WINDOW\|NY | 2.14 | 2.87 | 2.23 | 2.99 | hl_families.tsv:95,96,97,98 |
| SI | P3_OR60 | REST_OF_WINDOW\|SESSION | 2.29 | 1.49 | 1.64 | 1.68 | hl_families.tsv:101,102,103,104 |
| SI | P3_OR60 | REST_OF_WINDOW\|TOKYO | 11.00 | 7.90 | 9.41 | 4.25 | hl_families.tsv:107,108,109,110 |
| SI | P4_CAMARILLA | SESSION_HL | 2.75 | 1.84 | 2.20 | 2.48 | hl_families.tsv:113,114,115,116 |
| SI | P4_FLOOR | SESSION_HL | 1.07 | 1.41 | 0.94 | 1.06 | hl_families.tsv:119,120,121,122 |
| SI | P5_D00 | PHASE_HL | 1.32 | 0.90 | 1.11 | 1.09 | hl_families.tsv:125,126,127,128 |
| SI | P5_D00 | SESSION_HL | 1.38 | 0.88 | 0.91 | 1.13 | hl_families.tsv:131,132,133,134 |
| SI | P5_D25 | PHASE_HL | 0.93 | 0.87 | 1.04 | 1.25 | hl_families.tsv:137,138,139,140 |
| SI | P5_D25 | SESSION_HL | 1.31 | 0.88 | 0.79 | 1.21 | hl_families.tsv:143,144,145,146 |
| SI | P5_D50 | PHASE_HL | 0.78 | 0.72 | 0.74 | 0.78 | hl_families.tsv:149,150,151,152 |
| SI | P5_D50 | SESSION_HL | 1.07 | 0.78 | 0.85 | 0.99 | hl_families.tsv:155,156,157,158 |
| SI | P5_D75 | PHASE_HL | 0.51 | 0.74 | 0.45 | 0.68 | hl_families.tsv:161,162,163,164 |
| SI | P5_D75 | SESSION_HL | 0.68 | 0.86 | 0.61 | 0.96 | hl_families.tsv:167,168,169,170 |
| SI | P6_GAPFILL | SESSION_HL | - | nan | nan | nan | hl_families.tsv:173,174,175 |

## 4. Quantile calibration (spec §3c)

| asset | family | target | side | q | era | n | coverage | |err| | file:line |
|---|---|---|---|---|---|---|---|---|---|
| SI | P1_SIDE_SETTLE | SESSION_HL | UP | 0.50 | FIT_2021_2024 | 886 | 0.474 | 0.026 | hl_calibration.tsv:9 |
| SI | P1_SIDE_SETTLE | SESSION_HL | DN | 0.50 | FIT_2021_2024 | 886 | 0.484 | 0.016 | hl_calibration.tsv:16 |
| SI | P1_SIDE_SETTLE | SESSION_HL | UP | 0.75 | FIT_2021_2024 | 886 | 0.714 | 0.036 | hl_calibration.tsv:23 |
| SI | P1_SIDE_SETTLE | SESSION_HL | DN | 0.75 | FIT_2021_2024 | 886 | 0.725 | 0.025 | hl_calibration.tsv:30 |
| SI | P1_SIDE_SETTLE | SESSION_HL | UP | 0.90 | FIT_2021_2024 | 886 | 0.871 | 0.029 | hl_calibration.tsv:37 |
| SI | P1_SIDE_SETTLE | SESSION_HL | DN | 0.90 | FIT_2021_2024 | 886 | 0.885 | 0.015 | hl_calibration.tsv:44 |
| SI | P1_SIDE_SETTLE | SESSION_HL | UP | 0.95 | FIT_2021_2024 | 886 | 0.926 | 0.024 | hl_calibration.tsv:51 |
| SI | P1_SIDE_SETTLE | SESSION_HL | DN | 0.95 | FIT_2021_2024 | 886 | 0.946 | 0.004 | hl_calibration.tsv:58 |
| SI | P1_SIDE_SOPEN | SESSION_HL | UP | 0.50 | FIT_2021_2024 | 886 | 0.472 | 0.028 | hl_calibration.tsv:65 |
| SI | P1_SIDE_SOPEN | SESSION_HL | DN | 0.50 | FIT_2021_2024 | 886 | 0.484 | 0.016 | hl_calibration.tsv:72 |
| SI | P1_SIDE_SOPEN | SESSION_HL | UP | 0.75 | FIT_2021_2024 | 886 | 0.716 | 0.034 | hl_calibration.tsv:79 |
| SI | P1_SIDE_SOPEN | SESSION_HL | DN | 0.75 | FIT_2021_2024 | 886 | 0.722 | 0.028 | hl_calibration.tsv:86 |
| SI | P1_SIDE_SOPEN | SESSION_HL | UP | 0.90 | FIT_2021_2024 | 886 | 0.871 | 0.029 | hl_calibration.tsv:93 |
| SI | P1_SIDE_SOPEN | SESSION_HL | DN | 0.90 | FIT_2021_2024 | 886 | 0.885 | 0.015 | hl_calibration.tsv:100 |
| SI | P1_SIDE_SOPEN | SESSION_HL | UP | 0.95 | FIT_2021_2024 | 886 | 0.929 | 0.021 | hl_calibration.tsv:107 |
| SI | P1_SIDE_SOPEN | SESSION_HL | DN | 0.95 | FIT_2021_2024 | 886 | 0.942 | 0.008 | hl_calibration.tsv:114 |
| SI | P1_SIDE_POPEN | PHASE_HL\|TOKYO | UP | 0.50 | FIT_2021_2024 | 886 | 0.449 | 0.051 | hl_calibration.tsv:121 |
| SI | P1_SIDE_POPEN | PHASE_HL\|TOKYO | DN | 0.50 | FIT_2021_2024 | 886 | 0.407 | 0.093 | hl_calibration.tsv:128 |
| SI | P1_SIDE_POPEN | PHASE_HL\|TOKYO | UP | 0.75 | FIT_2021_2024 | 886 | 0.683 | 0.067 | hl_calibration.tsv:135 |
| SI | P1_SIDE_POPEN | PHASE_HL\|TOKYO | DN | 0.75 | FIT_2021_2024 | 886 | 0.664 | 0.086 | hl_calibration.tsv:142 |
| SI | P1_SIDE_POPEN | PHASE_HL\|TOKYO | UP | 0.90 | FIT_2021_2024 | 886 | 0.852 | 0.048 | hl_calibration.tsv:149 |
| SI | P1_SIDE_POPEN | PHASE_HL\|TOKYO | DN | 0.90 | FIT_2021_2024 | 886 | 0.844 | 0.056 | hl_calibration.tsv:156 |
| SI | P1_SIDE_POPEN | PHASE_HL\|TOKYO | UP | 0.95 | FIT_2021_2024 | 886 | 0.909 | 0.041 | hl_calibration.tsv:163 |
| SI | P1_SIDE_POPEN | PHASE_HL\|TOKYO | DN | 0.95 | FIT_2021_2024 | 886 | 0.911 | 0.039 | hl_calibration.tsv:170 |
| SI | P1_SIDE_POPEN | PHASE_HL\|LONDON | UP | 0.50 | FIT_2021_2024 | 886 | 0.440 | 0.060 | hl_calibration.tsv:177 |
| SI | P1_SIDE_POPEN | PHASE_HL\|LONDON | DN | 0.50 | FIT_2021_2024 | 886 | 0.449 | 0.051 | hl_calibration.tsv:184 |
| SI | P1_SIDE_POPEN | PHASE_HL\|LONDON | UP | 0.75 | FIT_2021_2024 | 886 | 0.690 | 0.060 | hl_calibration.tsv:191 |
| SI | P1_SIDE_POPEN | PHASE_HL\|LONDON | DN | 0.75 | FIT_2021_2024 | 886 | 0.707 | 0.043 | hl_calibration.tsv:198 |
| SI | P1_SIDE_POPEN | PHASE_HL\|LONDON | UP | 0.90 | FIT_2021_2024 | 886 | 0.858 | 0.042 | hl_calibration.tsv:205 |
| SI | P1_SIDE_POPEN | PHASE_HL\|LONDON | DN | 0.90 | FIT_2021_2024 | 886 | 0.850 | 0.050 | hl_calibration.tsv:212 |
| SI | P1_SIDE_POPEN | PHASE_HL\|LONDON | UP | 0.95 | FIT_2021_2024 | 886 | 0.911 | 0.039 | hl_calibration.tsv:219 |
| SI | P1_SIDE_POPEN | PHASE_HL\|LONDON | DN | 0.95 | FIT_2021_2024 | 886 | 0.913 | 0.037 | hl_calibration.tsv:226 |
| SI | P1_SIDE_POPEN | PHASE_HL\|NY | UP | 0.50 | FIT_2021_2024 | 886 | 0.448 | 0.052 | hl_calibration.tsv:233 |
| SI | P1_SIDE_POPEN | PHASE_HL\|NY | DN | 0.50 | FIT_2021_2024 | 886 | 0.462 | 0.038 | hl_calibration.tsv:240 |
| SI | P1_SIDE_POPEN | PHASE_HL\|NY | UP | 0.75 | FIT_2021_2024 | 886 | 0.705 | 0.045 | hl_calibration.tsv:247 |
| SI | P1_SIDE_POPEN | PHASE_HL\|NY | DN | 0.75 | FIT_2021_2024 | 886 | 0.720 | 0.030 | hl_calibration.tsv:254 |
| SI | P1_SIDE_POPEN | PHASE_HL\|NY | UP | 0.90 | FIT_2021_2024 | 886 | 0.859 | 0.041 | hl_calibration.tsv:261 |
| SI | P1_SIDE_POPEN | PHASE_HL\|NY | DN | 0.90 | FIT_2021_2024 | 886 | 0.876 | 0.024 | hl_calibration.tsv:268 |
| SI | P1_SIDE_POPEN | PHASE_HL\|NY | UP | 0.95 | FIT_2021_2024 | 886 | 0.915 | 0.035 | hl_calibration.tsv:275 |
| SI | P1_SIDE_POPEN | PHASE_HL\|NY | DN | 0.95 | FIT_2021_2024 | 886 | 0.928 | 0.022 | hl_calibration.tsv:282 |
| SI | P2_OLS | SESSION_HL | UP | 0.50 | FIT_2021_2024 | 646 | 0.495 | 0.005 | hl_calibration.tsv:288 |
| SI | P2_OLS | SESSION_HL | DN | 0.50 | FIT_2021_2024 | 646 | 0.505 | 0.005 | hl_calibration.tsv:294 |
| SI | P2_LOGIT | SESSION_HL | UP | 0.50 | FIT_2021_2024 | 646 | 0.486 | 0.014 | hl_calibration.tsv:300 |
| SI | P2_LOGIT | SESSION_HL | DN | 0.50 | FIT_2021_2024 | 646 | 0.514 | 0.014 | hl_calibration.tsv:306 |
| SI | P2_UNCOND | SESSION_HL | UP | 0.50 | FIT_2021_2024 | 646 | 0.466 | 0.034 | hl_calibration.tsv:312 |
| SI | P2_UNCOND | SESSION_HL | DN | 0.50 | FIT_2021_2024 | 646 | 0.534 | 0.034 | hl_calibration.tsv:318 |
| HG | P1_SIDE_SETTLE | SESSION_HL | UP | 0.50 | FIT_2021_2024 | 991 | 0.483 | 0.017 | hl_calibration.tsv:325 |
| HG | P1_SIDE_SETTLE | SESSION_HL | DN | 0.50 | FIT_2021_2024 | 991 | 0.480 | 0.020 | hl_calibration.tsv:332 |
| HG | P1_SIDE_SETTLE | SESSION_HL | UP | 0.75 | FIT_2021_2024 | 991 | 0.736 | 0.014 | hl_calibration.tsv:339 |
| HG | P1_SIDE_SETTLE | SESSION_HL | DN | 0.75 | FIT_2021_2024 | 991 | 0.734 | 0.016 | hl_calibration.tsv:346 |
| HG | P1_SIDE_SETTLE | SESSION_HL | UP | 0.90 | FIT_2021_2024 | 991 | 0.889 | 0.011 | hl_calibration.tsv:353 |
| HG | P1_SIDE_SETTLE | SESSION_HL | DN | 0.90 | FIT_2021_2024 | 991 | 0.889 | 0.011 | hl_calibration.tsv:360 |
| HG | P1_SIDE_SETTLE | SESSION_HL | UP | 0.95 | FIT_2021_2024 | 991 | 0.939 | 0.011 | hl_calibration.tsv:367 |
| HG | P1_SIDE_SETTLE | SESSION_HL | DN | 0.95 | FIT_2021_2024 | 991 | 0.937 | 0.013 | hl_calibration.tsv:374 |
| HG | P1_SIDE_SOPEN | SESSION_HL | UP | 0.50 | FIT_2021_2024 | 991 | 0.488 | 0.012 | hl_calibration.tsv:381 |
| HG | P1_SIDE_SOPEN | SESSION_HL | DN | 0.50 | FIT_2021_2024 | 991 | 0.483 | 0.017 | hl_calibration.tsv:388 |
| HG | P1_SIDE_SOPEN | SESSION_HL | UP | 0.75 | FIT_2021_2024 | 991 | 0.728 | 0.022 | hl_calibration.tsv:395 |
| HG | P1_SIDE_SOPEN | SESSION_HL | DN | 0.75 | FIT_2021_2024 | 991 | 0.732 | 0.018 | hl_calibration.tsv:402 |
| HG | P1_SIDE_SOPEN | SESSION_HL | UP | 0.90 | FIT_2021_2024 | 991 | 0.891 | 0.009 | hl_calibration.tsv:409 |
| HG | P1_SIDE_SOPEN | SESSION_HL | DN | 0.90 | FIT_2021_2024 | 991 | 0.890 | 0.010 | hl_calibration.tsv:416 |
| HG | P1_SIDE_SOPEN | SESSION_HL | UP | 0.95 | FIT_2021_2024 | 991 | 0.937 | 0.013 | hl_calibration.tsv:423 |
| HG | P1_SIDE_SOPEN | SESSION_HL | DN | 0.95 | FIT_2021_2024 | 991 | 0.933 | 0.017 | hl_calibration.tsv:430 |
| HG | P1_SIDE_POPEN | PHASE_HL\|TOKYO | UP | 0.50 | FIT_2021_2024 | 991 | 0.471 | 0.029 | hl_calibration.tsv:437 |
| HG | P1_SIDE_POPEN | PHASE_HL\|TOKYO | DN | 0.50 | FIT_2021_2024 | 991 | 0.460 | 0.040 | hl_calibration.tsv:444 |
| HG | P1_SIDE_POPEN | PHASE_HL\|TOKYO | UP | 0.75 | FIT_2021_2024 | 991 | 0.704 | 0.046 | hl_calibration.tsv:451 |
| HG | P1_SIDE_POPEN | PHASE_HL\|TOKYO | DN | 0.75 | FIT_2021_2024 | 991 | 0.697 | 0.053 | hl_calibration.tsv:458 |
| HG | P1_SIDE_POPEN | PHASE_HL\|TOKYO | UP | 0.90 | FIT_2021_2024 | 991 | 0.875 | 0.025 | hl_calibration.tsv:465 |
| HG | P1_SIDE_POPEN | PHASE_HL\|TOKYO | DN | 0.90 | FIT_2021_2024 | 991 | 0.870 | 0.030 | hl_calibration.tsv:472 |
| HG | P1_SIDE_POPEN | PHASE_HL\|TOKYO | UP | 0.95 | FIT_2021_2024 | 991 | 0.932 | 0.018 | hl_calibration.tsv:479 |
| HG | P1_SIDE_POPEN | PHASE_HL\|TOKYO | DN | 0.95 | FIT_2021_2024 | 991 | 0.924 | 0.026 | hl_calibration.tsv:486 |
| HG | P1_SIDE_POPEN | PHASE_HL\|LONDON | UP | 0.50 | FIT_2021_2024 | 991 | 0.461 | 0.039 | hl_calibration.tsv:493 |
| HG | P1_SIDE_POPEN | PHASE_HL\|LONDON | DN | 0.50 | FIT_2021_2024 | 991 | 0.449 | 0.051 | hl_calibration.tsv:500 |
| HG | P1_SIDE_POPEN | PHASE_HL\|LONDON | UP | 0.75 | FIT_2021_2024 | 991 | 0.695 | 0.055 | hl_calibration.tsv:507 |
| HG | P1_SIDE_POPEN | PHASE_HL\|LONDON | DN | 0.75 | FIT_2021_2024 | 991 | 0.710 | 0.040 | hl_calibration.tsv:514 |
| HG | P1_SIDE_POPEN | PHASE_HL\|LONDON | UP | 0.90 | FIT_2021_2024 | 991 | 0.863 | 0.037 | hl_calibration.tsv:521 |
| HG | P1_SIDE_POPEN | PHASE_HL\|LONDON | DN | 0.90 | FIT_2021_2024 | 991 | 0.872 | 0.028 | hl_calibration.tsv:528 |
| HG | P1_SIDE_POPEN | PHASE_HL\|LONDON | UP | 0.95 | FIT_2021_2024 | 991 | 0.921 | 0.029 | hl_calibration.tsv:535 |
| HG | P1_SIDE_POPEN | PHASE_HL\|LONDON | DN | 0.95 | FIT_2021_2024 | 991 | 0.924 | 0.026 | hl_calibration.tsv:542 |
| HG | P1_SIDE_POPEN | PHASE_HL\|NY | UP | 0.50 | FIT_2021_2024 | 991 | 0.476 | 0.024 | hl_calibration.tsv:549 |
| HG | P1_SIDE_POPEN | PHASE_HL\|NY | DN | 0.50 | FIT_2021_2024 | 991 | 0.464 | 0.036 | hl_calibration.tsv:556 |
| HG | P1_SIDE_POPEN | PHASE_HL\|NY | UP | 0.75 | FIT_2021_2024 | 991 | 0.724 | 0.026 | hl_calibration.tsv:563 |
| HG | P1_SIDE_POPEN | PHASE_HL\|NY | DN | 0.75 | FIT_2021_2024 | 991 | 0.710 | 0.040 | hl_calibration.tsv:570 |
| HG | P1_SIDE_POPEN | PHASE_HL\|NY | UP | 0.90 | FIT_2021_2024 | 991 | 0.879 | 0.021 | hl_calibration.tsv:577 |
| HG | P1_SIDE_POPEN | PHASE_HL\|NY | DN | 0.90 | FIT_2021_2024 | 991 | 0.870 | 0.030 | hl_calibration.tsv:584 |
| HG | P1_SIDE_POPEN | PHASE_HL\|NY | UP | 0.95 | FIT_2021_2024 | 991 | 0.932 | 0.018 | hl_calibration.tsv:591 |
| HG | P1_SIDE_POPEN | PHASE_HL\|NY | DN | 0.95 | FIT_2021_2024 | 991 | 0.931 | 0.019 | hl_calibration.tsv:598 |
| HG | P2_OLS | SESSION_HL | UP | 0.50 | FIT_2021_2024 | 753 | 0.491 | 0.009 | hl_calibration.tsv:604 |
| HG | P2_OLS | SESSION_HL | DN | 0.50 | FIT_2021_2024 | 753 | 0.509 | 0.009 | hl_calibration.tsv:610 |
| HG | P2_LOGIT | SESSION_HL | UP | 0.50 | FIT_2021_2024 | 753 | 0.502 | 0.002 | hl_calibration.tsv:616 |
| HG | P2_LOGIT | SESSION_HL | DN | 0.50 | FIT_2021_2024 | 753 | 0.498 | 0.002 | hl_calibration.tsv:622 |
| HG | P2_UNCOND | SESSION_HL | UP | 0.50 | FIT_2021_2024 | 753 | 0.485 | 0.015 | hl_calibration.tsv:628 |
| HG | P2_UNCOND | SESSION_HL | DN | 0.50 | FIT_2021_2024 | 753 | 0.515 | 0.015 | hl_calibration.tsv:634 |
| NKD | P1_SIDE_SETTLE | SESSION_HL | UP | 0.50 | FIT_2021_2024 | 993 | 0.478 | 0.022 | hl_calibration.tsv:641 |
| NKD | P1_SIDE_SETTLE | SESSION_HL | DN | 0.50 | FIT_2021_2024 | 993 | 0.476 | 0.024 | hl_calibration.tsv:648 |
| NKD | P1_SIDE_SETTLE | SESSION_HL | UP | 0.75 | FIT_2021_2024 | 993 | 0.718 | 0.032 | hl_calibration.tsv:655 |
| NKD | P1_SIDE_SETTLE | SESSION_HL | DN | 0.75 | FIT_2021_2024 | 993 | 0.724 | 0.026 | hl_calibration.tsv:662 |
| NKD | P1_SIDE_SETTLE | SESSION_HL | UP | 0.90 | FIT_2021_2024 | 993 | 0.881 | 0.019 | hl_calibration.tsv:669 |
| NKD | P1_SIDE_SETTLE | SESSION_HL | DN | 0.90 | FIT_2021_2024 | 993 | 0.884 | 0.016 | hl_calibration.tsv:676 |
| NKD | P1_SIDE_SETTLE | SESSION_HL | UP | 0.95 | FIT_2021_2024 | 993 | 0.934 | 0.016 | hl_calibration.tsv:683 |
| NKD | P1_SIDE_SETTLE | SESSION_HL | DN | 0.95 | FIT_2021_2024 | 993 | 0.933 | 0.017 | hl_calibration.tsv:690 |
| NKD | P1_SIDE_SOPEN | SESSION_HL | UP | 0.50 | FIT_2021_2024 | 993 | 0.483 | 0.017 | hl_calibration.tsv:697 |
| NKD | P1_SIDE_SOPEN | SESSION_HL | DN | 0.50 | FIT_2021_2024 | 993 | 0.476 | 0.024 | hl_calibration.tsv:704 |
| NKD | P1_SIDE_SOPEN | SESSION_HL | UP | 0.75 | FIT_2021_2024 | 993 | 0.717 | 0.033 | hl_calibration.tsv:711 |
| NKD | P1_SIDE_SOPEN | SESSION_HL | DN | 0.75 | FIT_2021_2024 | 993 | 0.733 | 0.017 | hl_calibration.tsv:718 |
| NKD | P1_SIDE_SOPEN | SESSION_HL | UP | 0.90 | FIT_2021_2024 | 993 | 0.881 | 0.019 | hl_calibration.tsv:725 |
| NKD | P1_SIDE_SOPEN | SESSION_HL | DN | 0.90 | FIT_2021_2024 | 993 | 0.884 | 0.016 | hl_calibration.tsv:732 |
| NKD | P1_SIDE_SOPEN | SESSION_HL | UP | 0.95 | FIT_2021_2024 | 993 | 0.932 | 0.018 | hl_calibration.tsv:739 |
| NKD | P1_SIDE_SOPEN | SESSION_HL | DN | 0.95 | FIT_2021_2024 | 993 | 0.936 | 0.014 | hl_calibration.tsv:746 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|TOKYO | UP | 0.50 | FIT_2021_2024 | 993 | 0.463 | 0.037 | hl_calibration.tsv:753 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|TOKYO | DN | 0.50 | FIT_2021_2024 | 993 | 0.463 | 0.037 | hl_calibration.tsv:760 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|TOKYO | UP | 0.75 | FIT_2021_2024 | 993 | 0.703 | 0.047 | hl_calibration.tsv:767 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|TOKYO | DN | 0.75 | FIT_2021_2024 | 993 | 0.715 | 0.035 | hl_calibration.tsv:774 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|TOKYO | UP | 0.90 | FIT_2021_2024 | 993 | 0.867 | 0.033 | hl_calibration.tsv:781 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|TOKYO | DN | 0.90 | FIT_2021_2024 | 993 | 0.879 | 0.021 | hl_calibration.tsv:788 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|TOKYO | UP | 0.95 | FIT_2021_2024 | 993 | 0.923 | 0.027 | hl_calibration.tsv:795 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|TOKYO | DN | 0.95 | FIT_2021_2024 | 993 | 0.931 | 0.019 | hl_calibration.tsv:802 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|LONDON | UP | 0.50 | FIT_2021_2024 | 993 | 0.436 | 0.064 | hl_calibration.tsv:809 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|LONDON | DN | 0.50 | FIT_2021_2024 | 993 | 0.443 | 0.057 | hl_calibration.tsv:816 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|LONDON | UP | 0.75 | FIT_2021_2024 | 993 | 0.678 | 0.072 | hl_calibration.tsv:823 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|LONDON | DN | 0.75 | FIT_2021_2024 | 993 | 0.679 | 0.071 | hl_calibration.tsv:830 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|LONDON | UP | 0.90 | FIT_2021_2024 | 993 | 0.844 | 0.056 | hl_calibration.tsv:837 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|LONDON | DN | 0.90 | FIT_2021_2024 | 993 | 0.843 | 0.057 | hl_calibration.tsv:844 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|LONDON | UP | 0.95 | FIT_2021_2024 | 993 | 0.919 | 0.031 | hl_calibration.tsv:851 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|LONDON | DN | 0.95 | FIT_2021_2024 | 993 | 0.912 | 0.038 | hl_calibration.tsv:858 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|NY | UP | 0.50 | FIT_2021_2024 | 993 | 0.461 | 0.039 | hl_calibration.tsv:865 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|NY | DN | 0.50 | FIT_2021_2024 | 993 | 0.456 | 0.044 | hl_calibration.tsv:872 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|NY | UP | 0.75 | FIT_2021_2024 | 993 | 0.691 | 0.059 | hl_calibration.tsv:879 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|NY | DN | 0.75 | FIT_2021_2024 | 993 | 0.688 | 0.062 | hl_calibration.tsv:886 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|NY | UP | 0.90 | FIT_2021_2024 | 993 | 0.854 | 0.046 | hl_calibration.tsv:893 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|NY | DN | 0.90 | FIT_2021_2024 | 993 | 0.869 | 0.031 | hl_calibration.tsv:900 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|NY | UP | 0.95 | FIT_2021_2024 | 993 | 0.918 | 0.032 | hl_calibration.tsv:907 |
| NKD | P1_SIDE_POPEN | PHASE_HL\|NY | DN | 0.95 | FIT_2021_2024 | 993 | 0.922 | 0.028 | hl_calibration.tsv:914 |
| NKD | P2_OLS | SESSION_HL | UP | 0.50 | FIT_2021_2024 | 754 | 0.493 | 0.007 | hl_calibration.tsv:920 |
| NKD | P2_OLS | SESSION_HL | DN | 0.50 | FIT_2021_2024 | 754 | 0.507 | 0.007 | hl_calibration.tsv:926 |
| NKD | P2_LOGIT | SESSION_HL | UP | 0.50 | FIT_2021_2024 | 754 | 0.488 | 0.012 | hl_calibration.tsv:932 |
| NKD | P2_LOGIT | SESSION_HL | DN | 0.50 | FIT_2021_2024 | 754 | 0.512 | 0.012 | hl_calibration.tsv:938 |
| NKD | P2_UNCOND | SESSION_HL | UP | 0.50 | FIT_2021_2024 | 754 | 0.495 | 0.005 | hl_calibration.tsv:944 |
| NKD | P2_UNCOND | SESSION_HL | DN | 0.50 | FIT_2021_2024 | 754 | 0.505 | 0.005 | hl_calibration.tsv:950 |

## 5. P2 conditional split vs the unconditional null (spec §2/§3)

Pinball loss at q=0.5 on up_share = (H-open)/(H-L); lower is better. The unconditional null is the trailing median up_share.

| asset | era | model | n | pinball | pinball_uncond | improvement | beats | file:line |
|---|---|---|---|---|---|---|---|---|
| SI | FIT_2021_2024 | OLS | 646 | 0.13445 | 0.13478 | +0.00033 | 1 | hl_p2_pinball.tsv:14 |
| SI | FIT_2021_2024 | LOGIT | 646 | 0.13569 | 0.13478 | -0.00092 | 0 | hl_p2_pinball.tsv:15 |
| SI | GATE_2025 | OLS | 258 | 0.14184 | 0.14269 | +0.00085 | 1 | hl_p2_pinball.tsv:16 |
| SI | GATE_2025 | LOGIT | 258 | 0.14261 | 0.14269 | +0.00009 | 1 | hl_p2_pinball.tsv:17 |
| HG | FIT_2021_2024 | OLS | 753 | 0.13497 | 0.13441 | -0.00056 | 0 | hl_p2_pinball.tsv:26 |
| HG | FIT_2021_2024 | LOGIT | 753 | 0.13641 | 0.13441 | -0.00201 | 0 | hl_p2_pinball.tsv:27 |
| HG | GATE_2025 | OLS | 258 | 0.13823 | 0.13652 | -0.00171 | 0 | hl_p2_pinball.tsv:28 |
| HG | GATE_2025 | LOGIT | 258 | 0.13871 | 0.13652 | -0.00219 | 0 | hl_p2_pinball.tsv:29 |
| NKD | FIT_2021_2024 | OLS | 754 | 0.13829 | 0.13581 | -0.00248 | 0 | hl_p2_pinball.tsv:38 |
| NKD | FIT_2021_2024 | LOGIT | 754 | 0.13978 | 0.13581 | -0.00396 | 0 | hl_p2_pinball.tsv:39 |
| NKD | GATE_2025 | OLS | 258 | 0.13954 | 0.14090 | +0.00136 | 1 | hl_p2_pinball.tsv:40 |
| NKD | GATE_2025 | LOGIT | 258 | 0.13881 | 0.14090 | +0.00209 | 1 | hl_p2_pinball.tsv:41 |

## 6. P7 confluence (spec §2 P7)

| asset | era | top-k | n | capture | null | lift | mean top-zone score | file:line |
|---|---|---|---|---|---|---|---|---|
| SI | FIT_2021_2024 | 1 | 1832 | 0.043 | 0.037 | 1.164 | 13.70 | hl_confluence.tsv:17 |
| SI | FIT_2021_2024 | 3 | 1832 | 0.116 | 0.090 | 1.291 | 13.70 | hl_confluence.tsv:18 |
| SI | FIT_2021_2024 | 5 | 1832 | 0.193 | 0.138 | 1.395 | 13.70 | hl_confluence.tsv:19 |
| SI | GATE_2025 | 1 | 516 | 0.043 | 0.014 | 3.143 | 14.48 | hl_confluence.tsv:20 |
| SI | GATE_2025 | 3 | 516 | 0.103 | 0.072 | 1.432 | 14.48 | hl_confluence.tsv:21 |
| SI | GATE_2025 | 5 | 516 | 0.165 | 0.138 | 1.197 | 14.48 | hl_confluence.tsv:22 |
| HG | FIT_2021_2024 | 1 | 2042 | 0.036 | 0.031 | 1.141 | 14.89 | hl_confluence.tsv:35 |
| HG | FIT_2021_2024 | 3 | 2042 | 0.118 | 0.090 | 1.304 | 14.89 | hl_confluence.tsv:36 |
| HG | FIT_2021_2024 | 5 | 2042 | 0.187 | 0.147 | 1.269 | 14.89 | hl_confluence.tsv:37 |
| HG | GATE_2025 | 1 | 516 | 0.050 | 0.029 | 1.733 | 15.99 | hl_confluence.tsv:38 |
| HG | GATE_2025 | 3 | 516 | 0.126 | 0.089 | 1.413 | 15.99 | hl_confluence.tsv:39 |
| HG | GATE_2025 | 5 | 516 | 0.207 | 0.136 | 1.529 | 15.99 | hl_confluence.tsv:40 |
| NKD | FIT_2021_2024 | 1 | 2046 | 0.053 | 0.033 | 1.612 | 15.18 | hl_confluence.tsv:53 |
| NKD | FIT_2021_2024 | 3 | 2046 | 0.140 | 0.097 | 1.442 | 15.18 | hl_confluence.tsv:54 |
| NKD | FIT_2021_2024 | 5 | 2046 | 0.228 | 0.154 | 1.475 | 15.18 | hl_confluence.tsv:55 |
| NKD | GATE_2025 | 1 | 516 | 0.052 | 0.041 | 1.286 | 15.96 | hl_confluence.tsv:56 |
| NKD | GATE_2025 | 3 | 516 | 0.157 | 0.107 | 1.473 | 15.96 | hl_confluence.tsv:57 |
| NKD | GATE_2025 | 5 | 516 | 0.219 | 0.169 | 1.299 | 15.96 | hl_confluence.tsv:58 |

## 7. P5 overshoot distribution (FIT era, per asset)

| asset | side | n | median_$ | d_p25_$ | d_p50_$ | d_p75_$ | file:line |
|---|---|---|---|---|---|---|---|
| SI | UP | 694 | 738 | 300 | 750 | 1650 | hl_overshoot.tsv:5 |
| SI | DN | 679 | 850 | 350 | 850 | 1725 | hl_overshoot.tsv:6 |
| HG | UP | 775 | 544 | 225 | 538 | 1125 | hl_overshoot.tsv:7 |
| HG | DN | 770 | 562 | 225 | 562 | 1100 | hl_overshoot.tsv:8 |
| NKD | UP | 817 | 625 | 275 | 625 | 1250 | hl_overshoot.tsv:9 |
| NKD | DN | 743 | 612 | 275 | 625 | 1350 | hl_overshoot.tsv:10 |

## 8. D-054 MID-SANE mask accounting

| asset | era | receipts | mean insane frac | median insane frac | zero-sane receipts | degenerate (frozen-quote) receipts | median threshold_$ | file:line |
|---|---|---|---|---|---|---|---|---|
| SI | 2021 | 182 | 0.1052 | 0.0000 | 19 | 28 | 250 | hl_midsane.tsv:5 |
| SI | 2022 | 309 | 0.0845 | 0.0000 | 26 | 51 | 250 | hl_midsane.tsv:6 |
| SI | 2023 | 305 | 0.1148 | 0.0000 | 35 | 48 | 250 | hl_midsane.tsv:7 |
| SI | 2024 | 311 | 0.0648 | 0.0000 | 20 | 52 | 250 | hl_midsane.tsv:8 |
| SI | FIT_2021_2024 | 1107 | 0.0907 | 0.0000 | 100 | 179 | 250 | hl_midsane.tsv:9 |
| SI | GATE_2025 | 310 | 0.0944 | 0.0000 | 29 | 52 | 250 | hl_midsane.tsv:10 |
| HG | 2021 | 310 | 0.0527 | 0.0000 | 16 | 52 | 250 | hl_midsane.tsv:11 |
| HG | 2022 | 310 | 0.0335 | 0.0000 | 10 | 52 | 250 | hl_midsane.tsv:12 |
| HG | 2023 | 310 | 0.0100 | 0.0000 | 3 | 53 | 125 | hl_midsane.tsv:13 |
| HG | 2024 | 311 | 0.0133 | 0.0000 | 4 | 52 | 250 | hl_midsane.tsv:14 |
| HG | FIT_2021_2024 | 1241 | 0.0274 | 0.0000 | 33 | 209 | 250 | hl_midsane.tsv:15 |
| HG | GATE_2025 | 310 | 0.0631 | 0.0000 | 19 | 52 | 250 | hl_midsane.tsv:16 |
| NKD | 2021 | 311 | 0.1710 | 0.0000 | 52 | 52 | 500 | hl_midsane.tsv:17 |
| NKD | 2022 | 310 | 0.1718 | 0.0006 | 52 | 52 | 500 | hl_midsane.tsv:18 |
| NKD | 2023 | 311 | 0.1748 | 0.0002 | 53 | 53 | 250 | hl_midsane.tsv:19 |
| NKD | 2024 | 311 | 0.1713 | 0.0004 | 52 | 52 | 500 | hl_midsane.tsv:20 |
| NKD | FIT_2021_2024 | 1243 | 0.1722 | 0.0002 | 209 | 209 | 500 | hl_midsane.tsv:21 |
| NKD | GATE_2025 | 310 | 0.0799 | 0.0000 | 24 | 52 | 500 | hl_midsane.tsv:22 |

## 8b. Red-first evidence (spec §4)

Every mutant below is a committed broken implementation in engine/port_m1/test_hl.py; the real implementation is green on every case, and a mutant caught by nothing would be a test failure.

| algorithm | mutant | cases broken | file:line |
|---|---|---|---|
| D054_mid_sane | no_500_cap | mask | hl_redfirst.tsv:5 |
| D054_mid_sane | strict_inequality | mask | hl_redfirst.tsv:6 |
| D054_mid_sane | two_sided_dropped | mask | hl_redfirst.tsv:7 |
| P5_delta_fit | no_min_observations | thin | hl_redfirst.tsv:8 |
| P5_delta_fit | no_tick_rounding | quantiles | hl_redfirst.tsv:9 |
| P5_overshoot | nearest_regardless_of_exceedance | samples,era_filter | hl_redfirst.tsv:10 |
| P5_overshoot | noncausal_same_session | samples,era_filter | hl_redfirst.tsv:11 |
| P5_overshoot | unsigned_distance | samples,era_filter | hl_redfirst.tsv:12 |
| P7_confluence | no_family_price_dedupe | dedupe | hl_redfirst.tsv:13 |
| P7_confluence | no_zone_merge | ranking,boundary,dedupe,merge | hl_redfirst.tsv:14 |
| P7_confluence | rank_by_price | ranking | hl_redfirst.tsv:15 |
| P7_confluence | strict_tolerance | ranking,boundary | hl_redfirst.tsv:16 |

## 9. Spec defects and data defects (reported, not improvised around)

**H1 — §2 P1 names per-side quantiles but no per-side calibration target.** The frozen fvol ladder calibrates ONE ratio, realized RANGE / sigma_hat (symmetric about the anchor), while P1 asks for q in {0.5,0.75,0.9,0.95} PER SIDE.  LANE ACTION: the same trailing-250 machinery (b2_fvol.ladder semantics, strictly prior, >= 30 observations) is applied to the ONE-SIDED excursion ratios (H - anchor)/sigma_hat and (anchor - L)/sigma_hat; the existing symmetric ladder is carried unchanged as the P1_BASE / P1_BASE_RS baselines the spec calls for.

**H2 — D-054 does not define the window of 'trailing-phase-median spread'.** LANE ACTION: the median of the same phase's per-session median two-sided spread over the 20 STRICTLY PRIOR sessions, requiring >= 5 observations; with fewer, only the $500 cap binds.  Strictly prior by construction, so a session never licenses its own mask, and the mask is computable live.  Declared in the receipt params.

**H3 — §2 P7 leaves k unspecified in 'top-k confluence zones'.** LANE ACTION: k in {1,3,5} are all reported; no verdict rests on a chosen k.

**H4 — §3 gives no denominator rule for families that do not fire every session.** P6 fires only on gap sessions, P1 only after its calibration warms up, and one-sided families declare nothing for the opposite extreme.  LANE ACTION: capture and its displaced null share a denominator of the extremes where the family DECLARES a compatible-side level (`n_scored`, with `applicable_frac` reported beside it), so the lift is honest; the additivity number (§3f) uses ALL realized extremes of the target (`n_extremes`), which is what generation would actually gain.

**H5 — §2 P2 says 'OLS/logistic' without choosing.** LANE ACTION: both are fitted and reported (P2_OLS, P2_LOGIT), each against the same unconditional-split null.

**H6 — §2 P5 fits the overshoot distribution on FIT and is then tested on FIT.** The spec orders exactly that sequence.  The P5 deltas are therefore IN-SAMPLE on the FIT era; the 2025 echo (deltas frozen from FIT) is the only out-of-sample reading of P5 in this census.

**H7 — §1 asks for phase H/L 'from the frozen phase tables', which carry three phases.** The frozen m0 table partitions the session into TOKYO/LONDON/NY only (m0 SPEC_DEFECTS D5).  LANE ACTION: the phase targets are those three; no fourth phase was invented.

**H8 — DATA DEFECT: frozen-quote receipts (m0 SPEC_DEFECTS D8).** Receipts whose SANE session range is exactly $0 are frozen quotes, not sessions.  LANE ACTION: dropped before any target, anchor or prior-session read - the same exclusion b2_fvol and b3_levels already apply.  Counts per asset and era in hl_midsane.tsv.

**H9 — The KEPT-family list predates the D-053 ledger.** §2 P7 and §3(f) need the KEPT families of the §6b relevance census, which was computed on m1/levels (the superseded VWAP bands), while the level prices are read from the D-053 ledger m1/levels_v2.  LANE ACTION: KEEP/RETIRE decisions taken from generation/level_relevance.tsv (FIT rows), prices from levels_v2.  Only the VWAP family's band set differs between the two, and VWAP is KEPT on HG only.

Generated by engine/port_m1/hl_census.py.

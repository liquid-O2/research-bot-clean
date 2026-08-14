# FVOL D-054 REBUILD — discharging R80 and D-054's closing clause

STATUS: fix-lane output of THE ONE D-001 FIX PASS, availability/tape/fvol sub-lane, 2026-08-14.
FINDING CLOSED: R80 (BLOCKER) — "the fvol layer M2 consumes was built BEFORE D-054 and never rebuilt".
ALSO CLOSED HERE: R89 (the cap-only threshold default is now a refusal).

## 1. WHAT WAS WRONG

`engine/port_m1/b2_fvol.py` contained zero occurrences of `sane` / `b7_sane` / `D-054`.  `_v1_shard:168`
loaded sessions with `X.load_session` and `realized():104` selected seconds with `sel = mask & s.valid`,
where `census_common.load_session:311` sets `s.valid = (s.state == C.ST_TWO_SIDED)` — the RAW two-sided
flag, i.e. exactly the wide-but-two-sided books D-054 exists to delete.  The committed artifact's header
pinned `m1_spec_sha16=ce0a8ca16e342cd7`, two spec revisions before D-054 landed
(`m1_common.py:36-37`: `ce0a8ca16e342cd7 (CC-M1-1) -> 418755209f3d08cb (CC-M1-3) -> ed126c64eee71c41
(CC-M1-4 mid-sanity, D-054)`; the live pin is now `b84832556267e703`).

## 2. WHAT CHANGED

* `engine/port_m1/b2_fvol.py:_v1_shard` installs the D-054 SANE view (`b7_sane.apply_for`) on every
  session BEFORE any estimator reads `s.valid` / `s.vt` / `s.vm` — the same call `assemble.load_session`
  makes at `assemble.py:180-181`.
* `engine/port_m1/b7_sane.py:load_thresholds` no longer back-fills a missing session with
  `[SANE_CAP_USD] * N_PHASES`.  A session without a COMPLETE (all N_PHASES) row set is absent from the
  map and `b7_sane.thresholds_for` raises `SaneThresholdRefusal` (R89): the committed table's SI/HG
  thresholds are $125-$250, so the $500 cap-only default was a mask 2-4x too permissive, fired silently.
  Measured: the committed `sane_thresholds.tsv` holds 4,521 sessions, all with exactly 3 phase rows, so
  the refusal path is armed and does not fire on the current corpus.
* `SECTION` is now `"§3 vol layer V1/V2 + CC-M1-1(A) + D-054 SANE mids"` and the artifacts re-pin to
  `m1_spec_sha16=b84832556267e703`; `params_hash` moves to `9249e6e164e63722...` (a `mid_sanity` PARAMS
  entry), so a stale consumer cannot mistake the two builds.

Rebuild command (D-018 launcher, 8 workers):
`M1_WORKERS=8 lab/run.sh port-m2-fixpass-fvol -- /usr/bin/python3 engine/port_m1/b2_fvol.py` (rc=0).

DETERMINISM: the rebuild was run twice; all six artifacts are byte-identical across runs
(`sha256sum -c` OK on `v1_realized.tsv`, `fvol_forecasts.tsv`, `fvol_walkforward_mae.tsv`,
`fvol_selection.tsv`, `fvol_context.tsv`, `fvol_coefficients.tsv`).

## 3. THE COMPARATOR IS CLEAN

The before/after below is NOT committed-artifact-vs-rebuild — that would confound D-054 with every other
change since `ce0a8ca16e342cd7`.  It is an A/B on the SAME code: the rebuild against a CONTROL run of the
identical HEAD code with `b7_sane.apply_for` neutralised to a no-op.  Verified: the control's
`v1_realized.tsv` data rows are byte-identical to the committed pre-fix artifact (0 of 22,605 rows
differ), so the committed pre-fix build and the unmasked control are the same object and every delta below
is D-054 and nothing else.

## 4. THE POPULATION EFFECT (typed exclusion)

### COVERAGE — the typed exclusion (D-054), SESSION segment

| asset | era | n sessions | finite range before | finite range after | REFUSED by the mask | share |
|---|---|---|---|---|---|---|
| SI | FIT_2021_2024 | 1107 | 1107 | 1007 | 100 | 0.0903 |
| SI | GATE_2025 | 310 | 310 | 281 | 29 | 0.0935 |
| HG | FIT_2021_2024 | 1241 | 1241 | 1208 | 33 | 0.0266 |
| HG | GATE_2025 | 310 | 310 | 292 | 18 | 0.0581 |
| NKD | FIT_2021_2024 | 1243 | 1243 | 1036 | 207 | 0.1665 |
| NKD | GATE_2025 | 310 | 310 | 286 | 24 | 0.0774 |
| ALL | ALL | - | 4521 | 4110 | 411 | 0.0909 |

### V1 REALIZED (the inputs)
CRITICAL QUALIFIER, measured: **all 411 sessions the mask empties were ALREADY degenerate** — every one of
them had `range_usd` exactly $0 before the mask, i.e. the stale-book receipts `b2_fvol.series_for`'s own
docstring names and already dropped from the model population (`_pos(range_usd)`).  Newly excluded from the
model population: **0**.  The forecast key set is IDENTICAL before and after (15,069 rows; 14,933 with a
finite `sigma_hat_usd` in both).  So D-054 does not shrink the fvol population — it changes VALUES.

## 5. BEFORE / AFTER, PER ASSET AND ERA

### V1 REALIZED (the inputs)

| asset | era | segment | metric | n | before | after | delta% | n_pair | med abs delta% | frac rows >5% |
|---|---|---|---|---|---|---|---|---|---|---|
| SI | FIT_2021_2024 | SESSION | n_valid | 1107 | 82800.00 | 82800.00 | +0.00 | 1107 | 0.00 | 0.0930 |
| SI | FIT_2021_2024 | SESSION | range_usd | 1107 | 2625.00 | 2800.00 | +6.67 | 928 | 0.00 | 0.0000 |
| SI | FIT_2021_2024 | SESSION | rv_usd | 1107 | 3361718.75 | 3649218.75 | +8.55 | 928 | 0.00 | 0.0011 |
| SI | FIT_2021_2024 | SESSION | sigma_usd | 1107 | 1833.50 | 1910.29 | +4.19 | 928 | 0.00 | 0.0000 |
| SI | FIT_2021_2024 | SESSION | jump_usd | 1107 | 89814.31 | 120893.83 | +34.60 | 673 | 0.00 | 0.0104 |
| SI | GATE_2025 | SESSION | n_valid | 310 | 82800.00 | 82800.00 | +0.00 | 310 | 0.00 | 0.1000 |
| SI | GATE_2025 | SESSION | range_usd | 310 | 4143.75 | 4362.50 | +5.28 | 258 | 0.00 | 0.0000 |
| SI | GATE_2025 | SESSION | rv_usd | 310 | 7261796.88 | 7831718.75 | +7.85 | 258 | 0.00 | 0.0116 |
| SI | GATE_2025 | SESSION | sigma_usd | 310 | 2694.77 | 2798.52 | +3.85 | 258 | 0.00 | 0.0039 |
| SI | GATE_2025 | SESSION | jump_usd | 310 | 140916.26 | 237775.52 | +68.74 | 174 | 0.00 | 0.0345 |
| HG | FIT_2021_2024 | SESSION | n_valid | 1241 | 82800.00 | 82800.00 | +0.00 | 1241 | 0.00 | 0.0322 |
| HG | FIT_2021_2024 | SESSION | range_usd | 1241 | 1943.75 | 1978.12 | +1.77 | 1032 | 0.00 | 0.0019 |
| HG | FIT_2021_2024 | SESSION | rv_usd | 1241 | 1748046.88 | 1777734.38 | +1.70 | 1032 | 0.00 | 0.0068 |
| HG | FIT_2021_2024 | SESSION | sigma_usd | 1241 | 1322.14 | 1333.32 | +0.85 | 1032 | 0.00 | 0.0048 |
| HG | FIT_2021_2024 | SESSION | jump_usd | 1241 | 53289.09 | 55628.81 | +4.39 | 776 | 0.00 | 0.0116 |
| HG | GATE_2025 | SESSION | n_valid | 310 | 82800.00 | 82800.00 | +0.00 | 310 | 0.00 | 0.0677 |
| HG | GATE_2025 | SESSION | range_usd | 310 | 2384.38 | 2521.88 | +5.77 | 258 | 0.00 | 0.0039 |
| HG | GATE_2025 | SESSION | rv_usd | 310 | 2854121.09 | 3064824.22 | +7.38 | 258 | 0.00 | 0.0155 |
| HG | GATE_2025 | SESSION | sigma_usd | 310 | 1689.41 | 1750.66 | +3.63 | 258 | 0.00 | 0.0116 |
| HG | GATE_2025 | SESSION | jump_usd | 310 | 102293.82 | 119949.88 | +17.26 | 210 | 0.00 | 0.0333 |
| NKD | FIT_2021_2024 | SESSION | n_valid | 1243 | 82800.00 | 82781.00 | -0.02 | 1243 | 0.02 | 0.1834 |
| NKD | FIT_2021_2024 | SESSION | range_usd | 1243 | 2175.00 | 2437.50 | +12.07 | 1034 | 0.00 | 0.0397 |
| NKD | FIT_2021_2024 | SESSION | rv_usd | 1243 | 2153906.25 | 2538671.88 | +17.86 | 1034 | 0.00 | 0.2157 |
| NKD | FIT_2021_2024 | SESSION | sigma_usd | 1243 | 1467.62 | 1593.32 | +8.57 | 1034 | 0.00 | 0.1093 |
| NKD | FIT_2021_2024 | SESSION | jump_usd | 1243 | 68878.03 | 97685.12 | +41.82 | 797 | 0.00 | 0.3588 |
| NKD | GATE_2025 | SESSION | n_valid | 310 | 82800.00 | 82796.00 | -0.00 | 310 | 0.00 | 0.0935 |
| NKD | GATE_2025 | SESSION | range_usd | 310 | 2993.75 | 3262.50 | +8.98 | 258 | 0.00 | 0.0271 |
| NKD | GATE_2025 | SESSION | rv_usd | 310 | 4076484.38 | 4333046.88 | +6.29 | 258 | 0.00 | 0.1512 |
| NKD | GATE_2025 | SESSION | sigma_usd | 310 | 2019.03 | 2081.59 | +3.10 | 258 | 0.00 | 0.0504 |
| NKD | GATE_2025 | SESSION | jump_usd | 310 | 68824.92 | 105949.12 | +53.94 | 172 | 0.00 | 0.3430 |

### V2 FORECASTS (what S3 / S9 / regime_forecast read)

| asset | era | segment | metric | n | before | after | delta% | n_pair | med abs delta% | frac rows >5% |
|---|---|---|---|---|---|---|---|---|---|---|
| SI | FIT_2021_2024 | SESSION | sigma_hat_usd | 928 | 2121.14 | 2121.04 | -0.00 | 916 | 0.01 | 0.0000 |
| SI | FIT_2021_2024 | SESSION | range_hat_usd | 928 | 2527.22 | 2527.22 | +0.00 | 916 | 0.00 | 0.0000 |
| SI | FIT_2021_2024 | SESSION | regime_tag | 928 | - | - | - | 928 | - | 0.2101 |
| SI | FIT_2021_2024 | TOKYO | sigma_hat_usd | 928 | 1227.15 | 1234.49 | +0.60 | 916 | 0.53 | 0.0033 |
| SI | FIT_2021_2024 | TOKYO | range_hat_usd | 928 | 1631.88 | 1626.10 | -0.35 | 916 | 0.49 | 0.0011 |
| SI | FIT_2021_2024 | TOKYO | regime_tag | 928 | - | - | - | 928 | - | 0.0248 |
| SI | FIT_2021_2024 | LONDON | sigma_hat_usd | 928 | 852.41 | 852.47 | +0.01 | 916 | 0.00 | 0.0000 |
| SI | FIT_2021_2024 | LONDON | range_hat_usd | 928 | 1294.11 | 1294.09 | -0.00 | 916 | 0.01 | 0.0000 |
| SI | FIT_2021_2024 | LONDON | regime_tag | 928 | - | - | - | 928 | - | 0.0000 |
| SI | FIT_2021_2024 | NY | sigma_hat_usd | 928 | 1697.01 | 1697.03 | +0.00 | 916 | 0.01 | 0.0000 |
| SI | FIT_2021_2024 | NY | range_hat_usd | 928 | 2527.22 | 2527.22 | +0.00 | 916 | 0.00 | 0.0000 |
| SI | FIT_2021_2024 | NY | regime_tag | 928 | - | - | - | 928 | - | 0.1843 |
| SI | GATE_2025 | SESSION | sigma_hat_usd | 258 | 2665.70 | 2664.41 | -0.05 | 258 | 0.04 | 0.0039 |
| SI | GATE_2025 | SESSION | range_hat_usd | 258 | 3584.77 | 3584.77 | +0.00 | 258 | 0.00 | 0.0000 |
| SI | GATE_2025 | SESSION | regime_tag | 258 | - | - | - | 258 | - | 0.2093 |
| SI | GATE_2025 | TOKYO | sigma_hat_usd | 258 | 1484.07 | 1487.15 | +0.21 | 258 | 0.51 | 0.0233 |
| SI | GATE_2025 | TOKYO | range_hat_usd | 258 | 2064.24 | 2063.65 | -0.03 | 258 | 0.50 | 0.0233 |
| SI | GATE_2025 | TOKYO | regime_tag | 258 | - | - | - | 258 | - | 0.0116 |
| SI | GATE_2025 | LONDON | sigma_hat_usd | 257 | 1032.27 | 1032.18 | -0.01 | 257 | 0.00 | 0.0039 |
| SI | GATE_2025 | LONDON | range_hat_usd | 257 | 1514.71 | 1514.82 | +0.01 | 257 | 0.01 | 0.0000 |
| SI | GATE_2025 | LONDON | regime_tag | 257 | - | - | - | 257 | - | 0.0000 |
| SI | GATE_2025 | NY | sigma_hat_usd | 258 | 2008.80 | 2011.48 | +0.13 | 258 | 0.05 | 0.0039 |
| SI | GATE_2025 | NY | range_hat_usd | 258 | 3584.77 | 3584.77 | +0.00 | 258 | 0.00 | 0.0000 |
| SI | GATE_2025 | NY | regime_tag | 258 | - | - | - | 258 | - | 0.1667 |
| HG | FIT_2021_2024 | SESSION | sigma_hat_usd | 1032 | 1534.86 | 1534.96 | +0.01 | 1021 | 0.11 | 0.0010 |
| HG | FIT_2021_2024 | SESSION | range_hat_usd | 1032 | 2196.74 | 2198.61 | +0.09 | 1021 | 0.10 | 0.0020 |
| HG | FIT_2021_2024 | SESSION | regime_tag | 1032 | - | - | - | 1032 | - | 0.0814 |
| HG | FIT_2021_2024 | TOKYO | sigma_hat_usd | 1032 | 796.05 | 793.58 | -0.31 | 1021 | 0.34 | 0.0020 |
| HG | FIT_2021_2024 | TOKYO | range_hat_usd | 1032 | 1208.65 | 1204.44 | -0.35 | 1021 | 0.35 | 0.0010 |
| HG | FIT_2021_2024 | TOKYO | regime_tag | 1032 | - | - | - | 1032 | - | 0.0155 |
| HG | FIT_2021_2024 | LONDON | sigma_hat_usd | 1032 | 710.15 | 710.66 | +0.07 | 1021 | 0.04 | 0.0000 |
| HG | FIT_2021_2024 | LONDON | range_hat_usd | 1032 | 1135.12 | 1135.02 | -0.01 | 1021 | 0.06 | 0.0000 |
| HG | FIT_2021_2024 | LONDON | regime_tag | 1032 | - | - | - | 1032 | - | 0.0000 |
| HG | FIT_2021_2024 | NY | sigma_hat_usd | 1032 | 1089.93 | 1090.42 | +0.04 | 1021 | 0.15 | 0.0010 |
| HG | FIT_2021_2024 | NY | range_hat_usd | 1032 | 1623.84 | 1626.50 | +0.16 | 1021 | 0.11 | 0.0020 |
| HG | FIT_2021_2024 | NY | regime_tag | 1032 | - | - | - | 1032 | - | 0.0833 |
| HG | GATE_2025 | SESSION | sigma_hat_usd | 258 | 1813.47 | 1807.84 | -0.31 | 258 | 0.14 | 0.0116 |
| HG | GATE_2025 | SESSION | range_hat_usd | 258 | 2777.77 | 2765.01 | -0.46 | 258 | 0.13 | 0.0116 |
| HG | GATE_2025 | SESSION | regime_tag | 258 | - | - | - | 258 | - | 0.1047 |
| HG | GATE_2025 | TOKYO | sigma_hat_usd | 258 | 1076.42 | 1067.89 | -0.79 | 258 | 0.39 | 0.0078 |
| HG | GATE_2025 | TOKYO | range_hat_usd | 258 | 1540.37 | 1527.27 | -0.85 | 258 | 0.54 | 0.0039 |
| HG | GATE_2025 | TOKYO | regime_tag | 258 | - | - | - | 258 | - | 0.0116 |
| HG | GATE_2025 | LONDON | sigma_hat_usd | 257 | 788.01 | 788.53 | +0.07 | 257 | 0.04 | 0.0000 |
| HG | GATE_2025 | LONDON | range_hat_usd | 257 | 1204.13 | 1203.41 | -0.06 | 257 | 0.08 | 0.0000 |
| HG | GATE_2025 | LONDON | regime_tag | 257 | - | - | - | 257 | - | 0.0000 |
| HG | GATE_2025 | NY | sigma_hat_usd | 258 | 1270.41 | 1263.30 | -0.56 | 258 | 0.22 | 0.0194 |
| HG | GATE_2025 | NY | range_hat_usd | 258 | 1916.04 | 1913.32 | -0.14 | 258 | 0.19 | 0.0194 |
| HG | GATE_2025 | NY | regime_tag | 258 | - | - | - | 258 | - | 0.0891 |
| NKD | FIT_2021_2024 | SESSION | sigma_hat_usd | 1034 | 1735.97 | 1739.16 | +0.18 | 1023 | 1.06 | 0.1075 |
| NKD | FIT_2021_2024 | SESSION | range_hat_usd | 1034 | 2319.05 | 2308.61 | -0.45 | 1023 | 0.93 | 0.0860 |
| NKD | FIT_2021_2024 | SESSION | regime_tag | 1034 | - | - | - | 1034 | - | 0.0948 |
| NKD | FIT_2021_2024 | TOKYO | sigma_hat_usd | 1034 | 1253.74 | 1251.39 | -0.19 | 1023 | 1.14 | 0.0948 |
| NKD | FIT_2021_2024 | TOKYO | range_hat_usd | 1034 | 1841.65 | 1828.56 | -0.71 | 1023 | 1.17 | 0.1281 |
| NKD | FIT_2021_2024 | TOKYO | regime_tag | 1034 | - | - | - | 1034 | - | 0.0812 |
| NKD | FIT_2021_2024 | LONDON | sigma_hat_usd | 1034 | 622.88 | 620.89 | -0.32 | 1023 | 0.34 | 0.0176 |
| NKD | FIT_2021_2024 | LONDON | range_hat_usd | 1034 | 936.20 | 941.92 | +0.61 | 1023 | 0.51 | 0.0254 |
| NKD | FIT_2021_2024 | LONDON | regime_tag | 1034 | - | - | - | 1034 | - | 0.0000 |
| NKD | FIT_2021_2024 | NY | sigma_hat_usd | 1034 | 1053.23 | 1043.76 | -0.90 | 1023 | 0.75 | 0.0684 |
| NKD | FIT_2021_2024 | NY | range_hat_usd | 1034 | 1597.69 | 1588.54 | -0.57 | 1023 | 1.11 | 0.0665 |
| NKD | FIT_2021_2024 | NY | regime_tag | 1034 | - | - | - | 1034 | - | 0.0745 |
| NKD | GATE_2025 | SESSION | sigma_hat_usd | 258 | 2112.09 | 2113.99 | +0.09 | 258 | 1.55 | 0.0388 |
| NKD | GATE_2025 | SESSION | range_hat_usd | 258 | 3204.96 | 3197.93 | -0.22 | 258 | 1.22 | 0.0271 |
| NKD | GATE_2025 | SESSION | regime_tag | 258 | - | - | - | 258 | - | 0.0581 |
| NKD | GATE_2025 | TOKYO | sigma_hat_usd | 258 | 1463.73 | 1465.34 | +0.11 | 258 | 1.11 | 0.0504 |
| NKD | GATE_2025 | TOKYO | range_hat_usd | 258 | 2267.09 | 2261.76 | -0.24 | 258 | 1.20 | 0.0504 |
| NKD | GATE_2025 | TOKYO | regime_tag | 258 | - | - | - | 258 | - | 0.0581 |
| NKD | GATE_2025 | LONDON | sigma_hat_usd | 257 | 681.53 | 684.93 | +0.50 | 257 | 0.45 | 0.0117 |
| NKD | GATE_2025 | LONDON | range_hat_usd | 257 | 1035.43 | 1035.08 | -0.03 | 257 | 0.70 | 0.0195 |
| NKD | GATE_2025 | LONDON | regime_tag | 257 | - | - | - | 257 | - | 0.0000 |
| NKD | GATE_2025 | NY | sigma_hat_usd | 258 | 1242.58 | 1275.84 | +2.68 | 258 | 2.09 | 0.1085 |
| NKD | GATE_2025 | NY | range_hat_usd | 258 | 1892.52 | 1931.64 | +2.07 | 258 | 2.09 | 0.1279 |
| NKD | GATE_2025 | NY | regime_tag | 258 | - | - | - | 258 | - | 0.0426 |

### S3 COVERAGE HEADLINE — exp_move_q50 = move_q50_usd_per_sigma x sigma_hat_usd

| asset | era | segment | n_pair | median before $ | median after $ | delta% | med abs delta% | frac rows >5% |
|---|---|---|---|---|---|---|---|---|
| SI | FIT_2021_2024 | SESSION | 886 | 2644.22 | 2644.30 | +0.00 | 0.01 | 0.0000 |
| SI | FIT_2021_2024 | TOKYO | 886 | 1106.73 | 1111.66 | +0.45 | 0.83 | 0.0056 |
| SI | FIT_2021_2024 | LONDON | 886 | 1086.25 | 1086.35 | +0.01 | 0.00 | 0.0000 |
| SI | FIT_2021_2024 | NY | 886 | 2183.42 | 2183.53 | +0.01 | 0.01 | 0.0000 |
| SI | GATE_2025 | SESSION | 258 | 4129.36 | 4129.01 | -0.01 | 0.04 | 0.0039 |
| SI | GATE_2025 | TOKYO | 258 | 2374.05 | 2373.76 | -0.01 | 0.61 | 0.0233 |
| SI | GATE_2025 | LONDON | 257 | 1586.48 | 1586.35 | -0.01 | 0.00 | 0.0039 |
| SI | GATE_2025 | NY | 258 | 3216.10 | 3216.19 | +0.00 | 0.06 | 0.0039 |
| HG | FIT_2021_2024 | SESSION | 991 | 2103.67 | 2101.18 | -0.12 | 0.14 | 0.0010 |
| HG | FIT_2021_2024 | TOKYO | 991 | 1085.59 | 1085.58 | -0.00 | 0.44 | 0.0030 |
| HG | FIT_2021_2024 | LONDON | 991 | 919.87 | 919.78 | -0.01 | 0.05 | 0.0000 |
| HG | FIT_2021_2024 | NY | 991 | 1393.30 | 1392.47 | -0.06 | 0.22 | 0.0020 |
| HG | GATE_2025 | SESSION | 258 | 2643.38 | 2640.25 | -0.12 | 0.21 | 0.0078 |
| HG | GATE_2025 | TOKYO | 258 | 1628.13 | 1628.40 | +0.02 | 0.39 | 0.0078 |
| HG | GATE_2025 | LONDON | 257 | 1154.23 | 1154.21 | -0.00 | 0.04 | 0.0000 |
| HG | GATE_2025 | NY | 258 | 1884.21 | 1882.52 | -0.09 | 0.22 | 0.0194 |
| NKD | FIT_2021_2024 | SESSION | 993 | 2201.08 | 2169.73 | -1.42 | 1.68 | 0.1259 |
| NKD | FIT_2021_2024 | TOKYO | 993 | 1529.21 | 1514.76 | -0.95 | 1.37 | 0.1088 |
| NKD | FIT_2021_2024 | LONDON | 993 | 700.93 | 694.60 | -0.90 | 0.44 | 0.0191 |
| NKD | FIT_2021_2024 | NY | 993 | 1240.06 | 1237.21 | -0.23 | 1.04 | 0.0886 |
| NKD | GATE_2025 | SESSION | 258 | 3321.79 | 3256.58 | -1.96 | 1.50 | 0.0388 |
| NKD | GATE_2025 | TOKYO | 258 | 2312.29 | 2279.99 | -1.40 | 1.48 | 0.0620 |
| NKD | GATE_2025 | LONDON | 257 | 1073.76 | 1075.42 | +0.15 | 0.55 | 0.0117 |
| NKD | GATE_2025 | NY | 258 | 1991.44 | 1967.88 | -1.18 | 1.72 | 0.0349 |

### THE >5% TEST
### POOLED (all assets, eras and segments; paired per (asset, session, segment) row)

| quantity | n | median abs delta | p90 | p99 | max | share of rows moving >5% |
|---|---|---|---|---|---|---|
| sigma_hat_usd | 14,933 | 0.106% | 1.935% | 8.838% | 71.88% | 2.51% |
| range_hat_usd | 14,933 | 0.106% | 2.094% | 8.417% | 72.98% | 2.63% |
| exp_move_q50_usd (S3 COVERAGE) | 14,573 | 0.160% | 2.372% | 8.839% | 71.92% | 2.79% |
| exp_move_q90_usd (S9 ladder top) | 14,573 | 0.210% | 3.062% | 11.813% | 70.98% | 5.19% |
| rv5_over_rv66 (the regime ratio) | 15,057 | 1.307% | 13.636% | 41.483% | 174.82% | 28.30% |
| regime_tag | 15,069 | — | — | — | — | **6.82% of rows RECLASSIFIED** (1,028) |

`ladder_source` changes on 135 rows, `sigma_source` on 21.

### THE §7-B2 GATE AND THE SELECTION RULE ARE UNMOVED

`fvol_selection.tsv`: 0 of 24 `selected_source` values change.
`fvol_walkforward_mae.tsv`: 0 of 72 verdicts change (SI SESSION/NY RANGE stay FAIL; everything else stays
PASS).  The FIT-era walk-forward MAE moves in the model's FAVOUR where the mask bites hardest:

| asset | segment | target | mae_fvol before | after | delta |
|---|---|---|---|---|---|
| NKD | NY | SIGMA | 252.0 | 226.5 | **-10.12%** |
| NKD | SESSION | SIGMA | 328.6 | 308.4 | **-6.15%** |
| NKD | NY | RANGE | 565.3 | 539.5 | -4.58% |
| NKD | SESSION | RANGE | 868.3 | 843.5 | -2.85% |
| NKD | TOKYO | SIGMA | 266.6 | 259.9 | -2.51% |
| HG | TOKYO | SIGMA | 155.5 | 154.5 | -0.62% |
| SI (all 8 rows) | — | — | — | — | within +/-0.19% |

## 6. THE >5% VERDICT (D-054's closing clause)

D-054: *"Impact on all prior census numbers must be QUANTIFIED (before/after) — if M0 verdict numbers move
>5%, a verdict addendum issues."*

**YES — named quantities move more than 5%.  A verdict addendum is owed, scoped as follows.**

MOVES >5% (addendum required):
1. **`regime_tag` — 1,028 of 15,069 rows (6.82%) are reclassified**, up to **21.01%** of rows on
   (SI, FIT_2021_2024, SESSION) and 20.93% on (SI, GATE_2025, SESSION).  Every verdict conditioned on the
   vol-regime tercile — S2's regime block, S9's regime-scaled ladder, `regime_forecast`, and any census
   that groups by `regime_tag` — is computed on a different partition than before.  This is the single
   largest exposure and it is a RE-PARTITION, not a value shift.
2. **`rv5_over_rv66` moves >5% on 28.30% of rows** (median 1.31%, p99 41.48%) — the ratio the terciles are
   cut on, which is why (1) is as large as it is.
3. **`exp_move_q90_usd` moves >5% on 5.19% of rows** — the top rung of the S9 ladder / the MAX-expected-move
   level.
4. **NKD walk-forward SIGMA MAE improves 10.12% (NY) and 6.15% (SESSION)** — a >5% move in a published
   §7-B2 gate number, in the model's favour, with no verdict flip.

DOES NOT MOVE >5% (no addendum owed):
* The headline consumed dollar forecasts at the median: `sigma_hat_usd` and `range_hat_usd` move **0.106%**
  at the median and `exp_move_q50_usd` — the S3 COVERAGE number that drives `unspent`, P002, P003, P014 and
  the whole `unspent_bind` family — moves **0.160%** at the median, with 97.2% of rows inside 5%.  Per
  (asset, era, segment) the median `exp_move_q50_usd` moves at most **-1.96%** (NKD GATE_2025 SESSION).
* The §7-B2 gate verdicts (0 of 72 change) and the §3 benchmark-substitution selections (0 of 24 change).
* The fvol POPULATION: 0 sessions newly excluded from the model.

TAIL WARNING, stated because the medians alone would understate it: the per-row maximum move is ~72% on
`sigma_hat_usd` / `range_hat_usd` / `exp_move_q50_usd`.  A single sheet's COVERAGE number can therefore move
a lot even though the corpus median barely moves; the 2.5-2.8% of rows past 5% are concentrated in NKD
(12.59% of NKD FIT_2021_2024 SESSION rows move >5% on `exp_move_q50_usd`), which is exactly the asset whose
3,220-point open spreads produced D-054 in the first place.

## 7. WHAT THIS DOES NOT COVER

* `regime_forecast.py:228` calls `X.load_session` directly and never applies B7 (R88).  It is owned by
  another lane; its anchor features remain on raw two-sided mids until that lane lands.  Rebuilding fvol
  does not fix it.
* `b10_generation_v3.py:330-331,511-512` still carries the `thr if thr is not None else [SANE_CAP_USD]*N`
  permissive default that R89 struck out of `b7_sane` and `assemble`.  Not this lane's file; flagged.
* Every downstream artifact that READ the pre-fix `fvol_forecasts.tsv` (rendered sheets, the triage indices,
  S3/S9 numbers in committed sheets, `class_census`/`family_census` rows keyed on `regime_tag`) is now stale
  against this build and must be re-rendered by the render lane.

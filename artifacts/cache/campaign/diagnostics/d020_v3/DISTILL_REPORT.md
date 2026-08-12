# DISTILL REPORT — granular-feature winner model (P(cert >= $500))

Config frozen on study CV only: `{'max_depth': 2, 'max_iter': 150, 'learning_rate': 0.05, 'min_samples_leaf': 20, 'l2_regularization': 1.0}` (study grouped-CV AUC 0.632); 109 features, 273 study / 466 blind candidates.
Dropped as degenerate in the study era (17): `Z_zdte_vol_z`, `V_term_ratio`, `V_term_slope30`, `V_term_present`, `R_atr_high`, `X_F_sf60_z__R_atr_high`, `X_F_sf120_z__R_atr_high`, `X_U_urg120_z__R_atr_high`, `X_D_depth60_z__R_atr_high`, `X_Z_zdte_slope__R_atr_high`, `X_V_pv_asym_z__R_atr_high`, `X_V_skew_traded_o__R_atr_high`, `X_V_term_ratio__R_trend_day`, `X_V_term_ratio__R_compress`, `X_V_term_ratio__R_atr_high`, `X_V_term_ratio__R_late`, `X_P_trend_match__R_atr_high`.

## Headline (blind = sessions 428..447, day-complete)
### BLIND (test)
- candidates 466 | winners 115 (24.7%) | AUC **0.652**
- top-3/day exit-free cert: **$1,382/day** ($461/candidate) vs oracle $3,028/day vs random-3 $1,021/day
- one-position replay: hold-to-close **$130/day** | 60m menu $30/day | all three held to close $323/day
- all-candidate cert mean $351
- exit-use split (P quartiles): top-Q cert $437 / close $33 / 60m $19 vs bottom-Q cert $208 / close $-12 / 60m $-9

### STUDY (in-sample reference)
- candidates 273 | winners 59 (21.6%) | AUC **0.994**
- top-3/day exit-free cert: **$2,006/day** ($669/candidate) vs oracle $2,474/day vs random-3 $819/day
- one-position replay: hold-to-close **$469/day** | 60m menu $232/day | all three held to close $1,134/day
- all-candidate cert mean $288
- exit-use split (P quartiles): top-Q cert $759 / close $463 / 60m $228 vs bottom-Q cert $106 / close $-79 / 60m $-71

### STUDY out-of-fold (grouped CV, honest in-era reference)
- OOF AUC 0.601
- top-3/day exit-free cert $1,084/day vs oracle $2,474 vs random $819

## Ablation arms (config re-selected on study CV in every arm)
| arm | features | study CV AUC | blind AUC | top-3 $/day | $/candidate |
|---|---|---|---|---|---|
| full (all features) | 109 | 0.632 | 0.652 | $1,382 | $461 |
| no regime ENCODING (drop R_*, X_*) | 75 | 0.614 | 0.643 | $1,433 | $478 |
| no regime CONTEXT (drop R_*, X_* and runway/trend/range) | 71 | 0.506 | 0.618 | $1,397 | $466 |
| coarse only (playbook_v1 block, P_*) | 10 | 0.617 | 0.630 | $1,297 | $432 |
| granular only (drop P_*) | 99 | 0.573 | 0.657 | $1,351 | $450 |

## L1 logistic twin (interpretable; C=0.05 by study CV, CV AUC 0.630)
- blind AUC 0.687; top-3 $1,285/day; close-replay $62/day
  - `P_runway_s` +0.119
  - `R_runway_min` +0.074
  - `P_trend_size` -0.033
  - `R_late` -0.008

## Reading the importances (caveat, load-bearing)
Permutation importance splits across DUPLICATED information: `P_runway_s` and `R_runway_min` are the same quantity, as are `P_trend_size`/`R_dayrange_atr` and `S_range_atr`.  The tree keeps one copy, so the other copy's family reads ~0.  Family totals therefore UNDERSTATE the R (regime) family; the honest measure of regime value is the 'no regime CONTEXT' ablation arm above, which drops every copy.

## Feature importances (permutation, study, AUC drop)
 1. `P_runway_s` +0.0725 (sd 0.0202)
 2. `P_trend_size` +0.0529 (sd 0.0082)
 3. `Z_share_delta30` +0.0194 (sd 0.0036)
 4. `Z_zdte_slope` +0.0134 (sd 0.0065)
 5. `S_pivot_extreme_o` +0.0126 (sd 0.0036)
 6. `A_abs60` +0.0112 (sd 0.0039)
 7. `D_depth60` +0.0046 (sd 0.0023)
 8. `F_sf600_o` +0.0043 (sd 0.0015)
 9. `F_sf120_o` +0.0034 (sd 0.0012)
10. `Z_charm120_z` +0.0031 (sd 0.0012)
11. `Z_dflow120_z` +0.0031 (sd 0.0011)
12. `P_od5_o` +0.0023 (sd 0.0010)
13. `U_urg_clock_z` +0.0016 (sd 0.0011)
14. `D_imb60_o` +0.0014 (sd 0.0006)
15. `Z_prem120_o` +0.0012 (sd 0.0007)
16. `V_dlog_mid10` +0.0012 (sd 0.0011)
17. `Z_charm120_o` +0.0010 (sd 0.0008)
18. `R_atr_rel` +0.0010 (sd 0.0006)
19. `U_urg120` +0.0010 (sd 0.0005)
20. `V_width_z` +0.0008 (sd 0.0003)

## Feature importances (permutation, BLIND — diagnostic, not used for fitting)
 1. `P_runway_s` +0.1093 (sd 0.0217)
 2. `P_trend_size` +0.0279 (sd 0.0114)
 3. `S_pivot_extreme_o` +0.0146 (sd 0.0068)
 4. `V_dlog_mid10` +0.0077 (sd 0.0046)
 5. `U_urg_clock_z` +0.0061 (sd 0.0038)
 6. `P_trend_match` +0.0043 (sd 0.0015)
 7. `D_depth60` +0.0041 (sd 0.0060)
 8. `R_atr_rel` +0.0035 (sd 0.0010)
 9. `S_pivot_in_range` +0.0030 (sd 0.0013)
10. `A_abs60` +0.0030 (sd 0.0048)
11. `P_od5_o` +0.0029 (sd 0.0029)
12. `V_pv_asym_z` +0.0027 (sd 0.0016)
13. `Z_prem120_o` +0.0021 (sd 0.0020)
14. `F_sf120_o` +0.0018 (sd 0.0024)
15. `F_sf120_z` +0.0016 (sd 0.0018)

## Controls
- label-shuffle control: blind AUC 0.502 (chance expected)
- W2.1 plane-1 (tomorrow expiry) coverage across the 35 sessions: 0.0% of candidates

## Vol-derivative status (coordinator's three additions)
- TRADED-IV ASYMMETRY: **BUILT** from the ribbon's vendor IV per option print (`V_skew_traded`, `_o`, `V_skew_slope`, `_o`; size-weighted call IV minus put IV over the last 15 min and its 15-min slope).
- TERM-MICRO RATIO: **BUILT** (`V_term_ratio`, `V_term_slope30`, `V_term_present`) but DEGENERATE IN THIS ERA — the W2.1 straddle plane 1 is typed-absent for almost every session here, so the columns were dropped by the study-era usability filter.
- SKEW TILT from the W2.1 surface: **SKIPPED-NEEDS-TOOL** (D-017, no approximation). `qr_w21_dump` emits per-bucket rows only for refill / requote / thinning (`mean_refill_bid|ask`, `oriented_refill_difference`) plus per-plane straddle rows; no per-bucket vol or width is exposed, and the straddle collapses call and put by construction, so a put-minus-call surface tilt cannot be formed without a new emission in C++.  The straddle bid/ask asymmetry fallback is already carried as `V_pv_asym` / `V_pv_asym_z` and is NOT a right-side tilt.

## Family totals (sum of positive permutation importance)
- study: P 0.1290 | Z 0.0419 | S 0.0133 | A 0.0113 | F 0.0080 | D 0.0060 | U 0.0039 | V 0.0037 | R 0.0010 | X 0.0000
- blind: P 0.1447 | S 0.0192 | V 0.0112 | U 0.0075 | Z 0.0074 | D 0.0051 | A 0.0035 | F 0.0035 | R 0.0035 | X 0.0000

## Model importance vs the orchestrator's blind-call reliability prior
- prior: FLOW-FLIP / counterflow (80%) -> model family `F` blind importance 0.0035 (rank 8/10)
- prior: REGIME / day-type (80%) -> model family `R` blind importance 0.0035 (rank 9/10)
- prior: 0DTE / crowd composition (80%) -> model family `Z` blind importance 0.0074 (rank 5/10)
- prior: VOL / protection (72%) -> model family `V` blind importance 0.0112 (rank 3/10)
- prior: structure counters (61%) -> model family `S` blind importance 0.0192 (rank 2/10)
- prior: runway (gate only) -> model family `P` blind importance 0.1447 (rank 1/10)
- prior: absorption ratios (47%) -> model family `A` blind importance 0.0035 (rank 7/10)

# MODEL V2 REPORT — SNIPER_V2 features at event grain (P(cert >= $500))

Config frozen on study CV only: `{'max_depth': 2, 'max_iter': 150, 'learning_rate': 0.05, 'min_samples_leaf': 20, 'l2_regularization': 1.0}` (study grouped-CV AUC 0.678); 255 usable features (146 v2 tiers + 109 v1 baseline), 273 study / 466 blind candidates.
Dropped as degenerate in the study era (20): `Z_zdte_vol_z`, `V_term_ratio`, `V_term_slope30`, `V_term_present`, `R_atr_high`, `X_F_sf60_z__R_atr_high`, `X_F_sf120_z__R_atr_high`, `X_U_urg120_z__R_atr_high`, `X_D_depth60_z__R_atr_high`, `X_Z_zdte_slope__R_atr_high`, `X_V_pv_asym_z__R_atr_high`, `X_V_skew_traded_o__R_atr_high`, `X_V_term_ratio__R_trend_day`, `X_V_term_ratio__R_compress`, `X_V_term_ratio__R_atr_high`, `X_V_term_ratio__R_late`, `X_P_trend_match__R_atr_high`, `K_delta120_o`, `K_flip120`, `K_contam_n120`.

Comparison anchors (v1, `DISTILL_REPORT.md`): blind AUC 0.652 GBT / 0.687 L1; top-3/day exit-free cert $1,382; oracle $3,028; random-3 $1,021.

## VERDICT — one target beaten, one not

**Dollars: BEATEN.**  Top-3/day exit-free cert **$1,672/day** against v1's $1,382 (+21%), $557 per candidate against $461.  The v1-features-only arm rerun in this harness reproduces v1's published $1,382 and AUC 0.652 exactly, so the comparison is like-for-like and the gain is the features, not the scaffolding.  RTY-mini equivalent (D-022, blind-era f=0.879): $1,469/day vs v1's $1,214/day.

**Blind AUC: NOT beaten.**  0.641 GBT against v1's 0.652, and 0.674 for the L1 twin against v1's 0.687.  Global ranking quality did not improve; what improved is the TOP of the ranking, which is the part selection uses. Study out-of-fold AUC — the honest in-era reference — rose from v1's 0.601 to 0.658, and the taken-vs-skipped lift at the human operating point rose from 1.45x to 1.57x.  The reading is that the v2 tiers sharpen extreme scores while adding noise in the middle of the distribution, where AUC does most of its counting.

**Honest caveats.**  (1) 255 features on 273 study rows across 15 sessions: study CV resolves arms poorly (the no-capacity arm scores HIGHER on study CV and LOWER on blind), so no arm here should be promoted on CV evidence.  (2) The no-T1.5 arm is marginally BETTER on both AUC and dollars, so the hedge corrector is not paying at this base rate.  (3) The blind one-position hold-to-close replay is $119/day, below v1's $130 — the exit-free selection number improved but the single-position replay did not, and the replay is the shape D-019 actually deploys.

## Headline (blind = sessions 428..447, day-complete, all candidates)
### BLIND (test)
- candidates 466 | winners 115 (24.7%) | AUC **0.641**
- top-3/day exit-free cert: **$1,672/day** ($557/candidate) vs oracle $3,028/day vs random-3 $1,021/day
- one-position replay: hold-to-close **$119/day** | 60m menu $-53/day | all three held to close $505/day
- all-candidate cert mean $351
- exit-use split (P quartiles): top-Q cert $494 / close $70 / 60m $39 vs bottom-Q cert $213 / close $-92 / 60m $-46

### STUDY (in-sample reference)
- candidates 273 | winners 59 (21.6%) | AUC **0.998**
- top-3/day exit-free cert: **$2,054/day** ($685/candidate) vs oracle $2,474/day vs random-3 $819/day
- one-position replay: hold-to-close **$460/day** | 60m menu $289/day | all three held to close $1,096/day
- all-candidate cert mean $288
- exit-use split (P quartiles): top-Q cert $768 / close $474 / 60m $250 vs bottom-Q cert $113 / close $-150 / 60m $-124

### STUDY out-of-fold (grouped CV, honest in-era reference)
- OOF AUC 0.658
- top-3/day exit-free cert $1,364/day vs oracle $2,474 vs random $819

## Operating point comparison (Opus's blind round: 11 takes / 40 = top 27.5%)
| model | takes | take rate | cert/taken | cert/skipped | lift | win-rate taken | win-rate skipped | MAE/taken |
|---|---|---|---|---|---|---|---|---|
| GBT | 128 | 27.5% | $477 | $303 | 1.57x | 33.6% | 21.3% | $123 |
| L1 twin | 128 | 27.5% | $478 | $303 | 1.58x | 36.7% | 20.1% | $123 |

## Selection depth (blind, exit-free cert per day)
| picks/day | v2 GBT | v2 L1 twin |
|---|---|---|
| top-1 | $629 | $576 |
| top-2 | $1,062 | $1,071 |
| top-3 | $1,672 | $1,487 |
| top-5 | $2,569 | $2,425 |

## Ablation arms (config re-selected on study CV in every arm)
| arm | features | study CV AUC | blind AUC | top-3 $/day | $/candidate | lift @27.5% |
|---|---|---|---|---|---|---|
| full v2 (v1 baseline + all SNIPER_V2 tiers) | 255 | 0.678 | 0.641 | $1,672 | $557 | 1.57x |
| no T1.1 CAPACITY (drop C_*) | 227 | 0.718 | 0.618 | $1,699 | $566 | 1.51x |
| no T1.5 HEDGE CORRECTION (corrected flow swapped for the raw J_ twins) | 217 | 0.670 | 0.648 | $1,727 | $576 | 1.57x |
| v1 FEATURES ONLY (the DISTILL_REPORT set, rerun here) | 109 | 0.632 | 0.652 | $1,382 | $461 | 1.45x |
| v2 TIERS ONLY (drop the v1 baseline block) | 146 | 0.677 | 0.633 | $1,641 | $547 | 1.63x |
| TIER 1 only (C,H,G,Q,K + v1 baseline) | 202 | 0.604 | 0.643 | $1,468 | $489 | 1.68x |
| L1-SELECTED (survivors of the study-CV L1 twin, refit as GBT) | 43 | 0.778 | 0.634 | $1,550 | $517 | 1.58x |
| no SESSION-CONSTANT channels | 253 | 0.681 | 0.642 | $1,678 | $559 | 1.59x |

## L1 logistic twin (interpretable; C=0.2 by study CV, CV AUC 0.690)
- blind AUC 0.674; top-3 $1,487/day; close-replay $53/day
  - `B_PS_OVERNIGHT_GAP` -0.595
  - `R_late` -0.454
  - `Q_own_refill_ratio` -0.398
  - `B_PS_D_PRIOR_LOW` -0.363
  - `B_PS_EDGE_DISTANCE_LOW_20D` +0.328
  - `C_erm_sigma_bps` +0.319
  - `P_trend_size` -0.254
  - `A_abs60` -0.188
  - `G_agree_x_early` +0.165
  - `Z_share_delta30` -0.164
  - `P_trend_match` +0.155
  - `H_resid300_o` +0.153
  - `U_urg120` +0.132
  - `X_V_pv_asym_z__R_trend_day` -0.127
  - `G_conflict` +0.119

## Feature importances (permutation, study, AUC drop)
 1. `B_PS_OVERNIGHT_GAP` +0.1073 (sd 0.0204)
 2. `P_runway_s` +0.0071 (sd 0.0033)
 3. `P_od5_o` +0.0026 (sd 0.0009)
 4. `P_trend_size` +0.0026 (sd 0.0010)
 5. `H_beta120` +0.0017 (sd 0.0011)
 6. `Q_own_refill_ratio` +0.0013 (sd 0.0008)
 7. `F_sf120_o` +0.0013 (sd 0.0006)
 8. `A_move60_o` +0.0011 (sd 0.0004)
 9. `B_PS_D_OPEN_ATR` +0.0009 (sd 0.0008)
10. `C_mag_against_bps` +0.0009 (sd 0.0004)
11. `C_giveback_frac` +0.0008 (sd 0.0003)
12. `Z_charm120_z` +0.0007 (sd 0.0004)
13. `Q_qps_accel` +0.0006 (sd 0.0005)
14. `C_objective_bps` +0.0006 (sd 0.0004)
15. `H_resid900_z_o` +0.0006 (sd 0.0005)
16. `Z_share_delta30` +0.0005 (sd 0.0004)
17. `A_abs60` +0.0005 (sd 0.0003)
18. `C_erm_atr_bps` +0.0004 (sd 0.0003)
19. `D_imb_delta_o` +0.0004 (sd 0.0002)
20. `Y_pv_slope30` +0.0004 (sd 0.0003)

## Feature importances (permutation, BLIND — diagnostic, not used for fitting)
 1. `P_runway_s` +0.0443 (sd 0.0108)
 2. `B_PS_OVERNIGHT_GAP` +0.0390 (sd 0.0302)
 3. `C_giveback_frac` +0.0090 (sd 0.0029)
 4. `P_trend_size` +0.0090 (sd 0.0058)
 5. `C_erm_atr_bps` +0.0083 (sd 0.0024)
 6. `C_objective_bps` +0.0066 (sd 0.0029)
 7. `C_erm_sigma_bps` +0.0065 (sd 0.0017)
 8. `B_PS_D_PRIOR_LOW` +0.0054 (sd 0.0043)
 9. `Q_opp_refill_ratio` +0.0053 (sd 0.0023)
10. `B_PS_RANGE_POSITION_20D` +0.0048 (sd 0.0015)
11. `V_dlog_mid10` +0.0047 (sd 0.0025)
12. `G_cell_x_phase` +0.0034 (sd 0.0013)
13. `D_imb_delta_o` +0.0032 (sd 0.0010)
14. `Q_own_refill_ratio` +0.0027 (sd 0.0026)
15. `C_phase` +0.0027 (sd 0.0008)
16. `H_resid900_z_o` +0.0027 (sd 0.0018)
17. `P_od5_o` +0.0027 (sd 0.0048)
18. `Q_qps_accel` +0.0019 (sd 0.0036)
19. `V_pv_asym` +0.0018 (sd 0.0006)
20. `D_depth60` +0.0017 (sd 0.0008)

## Tier totals vs the SNIPER_V2 prediction (sum of positive permutation importance)
| family | tier | study | blind |
|---|---|---|---|
| `P_` | v1 coarse | 0.0122 | 0.0560 |
| `B_` | T2.6 variance-budget | 0.1090 | 0.0533 |
| `C_` | T1.1 capacity | 0.0032 | 0.0355 |
| `Q_` | T1.4 quote-churn | 0.0022 | 0.0105 |
| `V_` | v1 vol | 0.0003 | 0.0065 |
| `D_` | v1 depth | 0.0004 | 0.0049 |
| `G_` | T1.3 cross-stream | 0.0001 | 0.0034 |
| `F_` | v1 flow | 0.0015 | 0.0032 |
| `H_` | T1.2 hidden-supply | 0.0023 | 0.0031 |
| `Z_` | v1 0DTE | 0.0013 | 0.0019 |
| `Y_` | T2.9 vol-surface | 0.0004 | 0.0002 |
| `S_` | v1 structure | 0.0000 | 0.0001 |
| `R_` | v1 regime | 0.0000 | 0.0000 |
| `U_` | v1 urgency | 0.0000 | 0.0000 |
| `A_` | v1 absorption | 0.0016 | 0.0000 |
| `X_` | v1 interactions | 0.0000 | 0.0000 |
| `K_` | T1.5 hedge-corrector | 0.0002 | 0.0000 |
| `N_` | T2.7 swing-chain | 0.0000 | 0.0000 |
| `O_` | T2.8 option-silence | 0.0003 | 0.0000 |
| `W_` | T2.10 0DTE/warehousing | 0.0000 | 0.0000 |

SNIPER_V2 predicted the tier order T1.1 > T1.2 > T1.3 > T1.4 > T1.5, then T2.
Measured on the blind block, with the v1 duplication caveat applied (`P_runway_s` is the same quantity as `C_runway_s`, so the capacity concept owns the `P_` total as well as the `C_` total):
- **T1.1 CAPACITY — CONFIRMED as the top object.** `P_`+`C_` is the largest block by a wide margin, and `C_giveback_frac`, `C_erm_atr_bps`, `C_objective_bps` and `C_erm_sigma_bps` are blind ranks 4-7 on their own. The capacity arithmetic transferred; dropping `C_*` costs blind AUC.
- **T1.4 QUOTE-CHURN — CONFIRMED at about its predicted weight.** The two refill-ratio channels and `Q_qps_accel` all carry blind importance, from a stream v1 never read.
- **T2.6 VARIANCE-BUDGET / W2 block — badly UNDER-predicted.** Ranked 6th in the tier list, measured 2nd. Its weight is concentrated in the SIDE-ORIENTED location channels (`B_PS_OVERNIGHT_GAP`, `B_PS_D_PRIOR_LOW`, `B_PS_RANGE_POSITION_20D`), not in `VB_BUDGET_CONSUMED`.
- **T1.2 HIDDEN-SUPPLY and T1.3 CROSS-STREAM — OVER-predicted.** Both were named the first things to build; both land mid-table. `H_resid900_z_o` and `G_cell_x_phase` do carry blind importance, so the constructs are real, but they are not the decisive objects the introspection rounds claimed.
- **T1.5 HEDGE CORRECTOR — NOT CONFIRMED as a feature family.** The detector fires on roughly 2 seconds per session (about 4% of block seconds), which matches the 2-in-40 rate the readers observed, but at that base rate it cannot move an AUC, and the no-T1.5 arm is not worse. It remains a correctness fix for the rare inverted read, not a source of edge.
- **T2.7 swing-chain, T2.8 option-silence, T2.9 vol-surface, T2.10 warehousing — no measurable blind contribution** at this sample size.

## Controls
- label-shuffle control: blind AUC 0.532 (chance expected)
- walk-forward purity: study = 398..412, blind = 428..447; no blind session is read by any fit, norm or config choice.


## ORIENTED_* sign-convention check (SNIPER_V2 "DEFECT TO CHECK") — DOCUMENTATION GAP

The `DIRECT_RAW` `ORIENTED_*` channels are CASE-ORIENTED and internally consistent:
`sigma_of(side)` returns `+1` for LONG and `-1` for SHORT
(`engine/cpp/qr_carriers/include/qr_carriers/channels.hpp:93-96`) and is applied by
`oriented(value, factor)` (`qr_carriers/src/stream_common.hpp:22`) as a magnitude-preserving
scalar flip AFTER the transform, inside `build_*_token(inputs, side)`; the SHORT shard's
`direct_raw.npy` therefore already carries negated values, and `render.py:705-715` prints
them verbatim with no second flip, so there is no double-flip risk.  Opus's cases 009 and
020 do NOT imply opposite conventions: both are sell-side reads that are correctly positive
for a SHORT.  What made case 009 unreadable is two facts nobody documented, neither of them
orientation.  (1) The 71,000-share ASK block carries trade condition 124, which
`classify_trade_condition` (`qr_carriers/include/qr_carriers/attach.hpp:262-269`) maps to
INELIGIBLE, so `ORIENTED_SIGNED_SIZE` is MASKED for that print
(`qr_carriers/src/stock_print_stream.cpp:169-172`) and it contributes nothing at all —
the visible fingerprint is `W30S_VALID_FRACTION = 0.446`.  (2) The surviving prints are
combined as a print-count mean of `signed_log1p(size)`, never share-weighted, so a
710x size ratio compresses to 2.4x and 38 small sell prints outweigh one huge buy block.
Restricting to condition-0 prints in that window reproduces the emitted sign exactly.
VERDICT: a DOCUMENTATION GAP, not a defect — the C++ is consistent; the pack states neither
the polarity nor the count-weighted/log-compressed/condition-filtered construction, so the
block cannot be reconciled against a share-weighted read of the raw ribbon.  One real
inhomogeneity to document alongside it: within `stock_nbbo`, `OWN_SIGNED_SIZE_CHANGE` and
the OWN/OPPOSITE price channels are NOT sigma-multiplied — they reflect only through the
bid/ask relabelling (`qr_carriers/src/nbbo_stream.cpp:91-92, 103-109`) — so they sit beside
three case-signed columns with nothing marking the difference.  No C++ was edited.


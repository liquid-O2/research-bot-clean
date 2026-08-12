# WALK-FORWARD REPORT — model-v2 features across every lawful era

Frozen estimator for EVERY fit below (v2's config, never re-selected): `{'max_depth': 2, 'max_iter': 150, 'learning_rate': 0.05, 'min_samples_leaf': 20, 'l2_regularization': 1.0}`.  Expanding-window ladder over 6 era blocks, 11941 candidates, 323 sessions 125..447.

## VERDICT

**The edge survives every era, and it is thin everywhere except the last rung.**  All 5 walk-forward segments beat a random-3 draw (lift 1.05x to 1.43x, mean 1.20x), and out-of-era AUC runs 0.554-0.697 — real, but far below the in-era numbers v2 reported.  A single 20-day block was not enough to see this: the spread across eras is wider than the gap between any two feature sets v2 compared.

**More training data helped the RANKING, not the TOP of the ranking.**  Segment e tests the identical `blind_e3` roster v2 tested, with 11475 training candidates instead of 273: AUC 0.646 against v2's 0.641 (+0.005), but top-3/day $1,459 against v2's $1,672 (-$213).  Selection uses the top of the ranking, so on the deployable number the 15-session era-native fit was not improved on by 303 sessions of history.

**Recency-weighting (D-031) is a real but small and inconsistent gain.**  Against pooling, the half-life-one-era weights move AUC by +0.003 on average (2/4 segments better) and top-3/day by +$70 (3/4 better).  Throwing history away entirely (newest era only) moves AUC -0.003 and top-3/day +$88.  Read together: old eras are not poison, and they are not worth much either — consistent with D-031's library claim (patterns persist) and against any simple 'retrain on the last block' rule.

**Pattern decay is NOT mainly a function of era distance.**  In the era-transfer matrix the column you test in explains far more than the row you trained in, and the gap-1 cells are not systematically better than the gap-4/5 cells.  What changes across eras is how much money the day offers: oracle top-3/day runs from $5,165 in `study_e1b` down to $2,257 in `study_e3b` — the OFFER moves, not the truth of the patterns.

**The forecast-vol `fade x hot` corner does NOT survive the walk forward.**  With the contrast's own cut applied verbatim it reproduces exactly on the blocks it was found on (102 candidates, 50% winners), and on the next block forward it collapses to 0% on 9 candidates — at or below the block's base rate.  The whole `M_` block behaves the same way in the model: adding it moves the blind AUC and the blind top-3/day slightly the WRONG way (see the ablation).  The single strongest cell anyone has shown on this roster is an in-sample artifact of `study_e3`, and the stack table shows the same thing at every depth — intersecting it with the model's own top slice does not rescue it.  Treat the forecast-vol channels as ordinary continuous features (`M_sigma_inst_bps` does carry real, small blind importance), not as a gate.


## Era census
| era | sessions | days | candidates | winner rate | mean cert | oracle top-3/day | random-3/day | RTY f (D-022) |
|---|---|---|---|---|---|---|---|---|
| `study_e1` | 125..179 | 55 | 2257 | 29.3% | $400 | $3,817 | $1,153 | 0.922 |
| `study_e1b` | 180..229 | 50 | 2955 | 32.1% | $465 | $5,165 | $1,322 | 0.882 |
| `study_e2` | 230..330 | 101 | 3902 | 29.8% | $403 | $3,945 | $1,136 | 0.907 |
| `study_e3` | 331..397 | 67 | 1861 | 21.5% | $311 | $2,666 | $911 | 0.919 |
| `study_e3b` | 398..427 | 30 | 500 | 21.4% | $281 | $2,257 | $794 | 0.936 |
| `blind_e3` | 428..447 | 20 | 466 | 24.7% | $351 | $3,028 | $1,021 | 0.879 |

## The ladder (expanding window, frozen config, day-complete test blocks)

| seg | train | test | train rows | features | AUC | top-3/day | top-3/day RTY-mini | top-5/day | lift vs random-3 | trades/day @27.5% | cert/taken | op lift |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **a** | study_e1 | `study_e1b` | 2257 | 243 | 0.554 | $1,390 | $1,226 | $2,307 | 1.05x | 16.3 | $493 | 1.09x |
| **b** | study_e1+study_e1b | `study_e2` | 5212 | 267 | 0.569 | $1,307 | $1,185 | $2,090 | 1.15x | 10.6 | $423 | 1.07x |
| **c** | study_e1+study_e1b+study_e2 | `study_e3` | 9114 | 307 | 0.593 | $1,011 | $929 | $1,723 | 1.11x | 7.6 | $335 | 1.11x |
| **d** | study_e1+study_e1b+study_e2+study_e3 | `study_e3b` | 10975 | 307 | 0.697 | $1,006 | $942 | $1,808 | 1.27x | 4.6 | $405 | 1.73x |
| **e** | study_e1+study_e1b+study_e2+study_e3+study_e3b | `blind_e3` | 11475 | 307 | 0.646 | $1,459 | $1,282 | $2,203 | 1.43x | 6.4 | $469 | 1.53x |

Segment **a** has a single training era, so its pooled / regime-weighted / newest-era arms are the same fit by construction.

## POOLED vs REGIME-WEIGHTED vs NEWEST-ERA-ONLY (D-031's question)

Same features, same frozen estimator, same test rows; only the training sample weights differ.  REGIME = 0.5^(eras of age), half-life one era; NEWEST = the immediately preceding era alone.

| seg | test | arm | AUC | top-3/day | top-5/day | lift vs random-3 | cert/taken @27.5% |
|---|---|---|---|---|---|---|---|
| a | `study_e1b` | pooled | 0.554 | $1,390 | $2,307 | 1.05x | $493 |
| a | `study_e1b` | regime-weighted | 0.554 | $1,390 | $2,307 | 1.05x | $493 |
| a | `study_e1b` | newest era only | 0.554 | $1,390 | $2,307 | 1.05x | $493 |
| b | `study_e2` | pooled | 0.569 | $1,307 | $2,090 | 1.15x | $423 |
| b | `study_e2` | regime-weighted | 0.568 | $1,209 | $1,998 | 1.06x | $422 |
| b | `study_e2` | newest era only | 0.578 | $1,355 | $2,055 | 1.19x | $439 |
| c | `study_e3` | pooled | 0.593 | $1,011 | $1,723 | 1.11x | $335 |
| c | `study_e3` | regime-weighted | 0.611 | $1,108 | $1,797 | 1.22x | $366 |
| c | `study_e3` | newest era only | 0.616 | $1,073 | $1,845 | 1.18x | $381 |
| d | `study_e3b` | pooled | 0.697 | $1,006 | $1,808 | 1.27x | $405 |
| d | `study_e3b` | regime-weighted | 0.703 | $1,171 | $1,910 | 1.47x | $437 |
| d | `study_e3b` | newest era only | 0.672 | $1,173 | $1,854 | 1.48x | $389 |
| e | `blind_e3` | pooled | 0.646 | $1,459 | $2,203 | 1.43x | $469 |
| e | `blind_e3` | regime-weighted | 0.636 | $1,575 | $2,156 | 1.54x | $475 |
| e | `blind_e3` | newest era only | 0.628 | $1,535 | $2,309 | 1.50x | $464 |

## Gate STACK — do the gates compound, or do they overlap?

Every row is a SELECTION over the same test block, scored the way the user's acceptance rules score it: a winner needs BOTH legs (cert >= $500 and MAE <= $300), and the dollars come from a ONE-POSITION occupancy replay, not from summing simultaneous picks.  `$/day` divides by EVERY day in the block, including the days the selection never fires; `$/trade` divides by the trades actually taken.  The model score is this lane's own walk-forward prediction for that segment — no refit, no lookahead.

### Segment a — test `study_e1b` (50 days, 2955 candidates)

| family | selection | n | n/day | winner% (cert>=$500 & MAE<=$300) | mean cert | close $/day | close $/trade | days fired | 60m $/day |
|---|---|---|---|---|---|---|---|---|---|
| baseline | all candidates | 2955 | 59.1 | 32.1% | $465 | $-157 | $-157 | 50/50 | $23 |
| baseline | model top-27.5% | 813 | 16.3 | 35.7% | $493 | $-81 | $-81 | 50/50 | $-170 |
| baseline | model top-3/day | 150 | 3.0 | 32.0% | $463 | $6 | $6 | 50/50 | $-5 |
| fvol | fade & hot corner (alone) | 0 | — | — | — | — | — | 0 | — |
| stack | model top ∩ corner | 0 | — | — | — | — | — | 0 | — |
| stack | top-3/day WITHIN the corner | 0 | — | — | — | — | — | 0 | — |
| stack | top-3/day within fade (any vol) | 0 | — | — | — | — | — | 0 | — |

### Segment b — test `study_e2` (101 days, 3902 candidates)

| family | selection | n | n/day | winner% (cert>=$500 & MAE<=$300) | mean cert | close $/day | close $/trade | days fired | 60m $/day |
|---|---|---|---|---|---|---|---|---|---|
| baseline | all candidates | 3902 | 38.6 | 29.8% | $403 | $-47 | $-47 | 101/101 | $-64 |
| baseline | model top-27.5% | 1073 | 10.6 | 32.3% | $423 | $-99 | $-101 | 99/101 | $-146 |
| baseline | model top-3/day | 303 | 3.0 | 35.3% | $436 | $-35 | $-35 | 101/101 | $-11 |
| fvol | fade & hot corner (alone) | 130 | 1.3 | 23.1% | $312 | $-46 | $-230 | 20/101 | $-24 |
| stack | model top ∩ corner | 50 | 0.5 | 26.0% | $372 | $-35 | $-222 | 16/101 | $-12 |
| stack | top-3/day WITHIN the corner | 53 | 0.5 | 20.8% | $279 | $-46 | $-231 | 20/101 | $-33 |
| stack | top-3/day within fade (any vol) | 79 | 0.8 | 22.8% | $295 | $-40 | $-135 | 30/101 | $-8 |

### Segment c — test `study_e3` (67 days, 1861 candidates)

| family | selection | n | n/day | winner% (cert>=$500 & MAE<=$300) | mean cert | close $/day | close $/trade | days fired | 60m $/day |
|---|---|---|---|---|---|---|---|---|---|
| baseline | all candidates | 1861 | 27.8 | 21.5% | $311 | $-14 | $-14 | 67/67 | $-71 |
| baseline | model top-27.5% | 512 | 7.6 | 25.6% | $335 | $-44 | $-44 | 67/67 | $-20 |
| baseline | model top-3/day | 201 | 3.0 | 24.9% | $337 | $-96 | $-96 | 67/67 | $-64 |
| fvol | fade & hot corner (alone) | 132 | 2.0 | 44.7% | $489 | $14 | $41 | 23/67 | $10 |
| stack | model top ∩ corner | 14 | 0.2 | 57.1% | $637 | $8 | $89 | 6/67 | $-3 |
| stack | top-3/day WITHIN the corner | 56 | 0.8 | 48.2% | $500 | $25 | $72 | 23/67 | $30 |
| stack | top-3/day within fade (any vol) | 79 | 1.2 | 41.8% | $459 | $25 | $58 | 29/67 | $41 |

### Segment d — test `study_e3b` (30 days, 500 candidates)

| family | selection | n | n/day | winner% (cert>=$500 & MAE<=$300) | mean cert | close $/day | close $/trade | days fired | 60m $/day |
|---|---|---|---|---|---|---|---|---|---|
| baseline | all candidates | 500 | 16.7 | 21.4% | $281 | $-70 | $-70 | 30/30 | $-89 |
| baseline | model top-27.5% | 138 | 4.6 | 37.0% | $405 | $-88 | $-138 | 19/30 | $-49 |
| baseline | model top-3/day | 90 | 3.0 | 33.3% | $335 | $-117 | $-117 | 30/30 | $-121 |
| fvol | fade & hot corner (alone) | 6 | 0.2 | 33.3% | $420 | $12 | $88 | 4/30 | $18 |
| stack | model top ∩ corner | 4 | 0.1 | 50.0% | $713 | $20 | $199 | 3/30 | $27 |
| stack | top-3/day WITHIN the corner | 6 | 0.2 | 33.3% | $420 | $12 | $88 | 4/30 | $18 |
| stack | top-3/day within fade (any vol) | 15 | 0.5 | 13.3% | $266 | $22 | $73 | 9/30 | $24 |

### Segment e — test `blind_e3` (20 days, 466 candidates)

| family | selection | n | n/day | winner% (cert>=$500 & MAE<=$300) | mean cert | close $/day | close $/trade | days fired | 60m $/day |
|---|---|---|---|---|---|---|---|---|---|
| baseline | all candidates | 466 | 23.3 | 24.7% | $351 | $62 | $62 | 20/20 | $317 |
| baseline | model top-27.5% | 128 | 6.4 | 34.4% | $469 | $46 | $58 | 16/20 | $-34 |
| baseline | model top-3/day | 60 | 3.0 | 35.0% | $486 | $81 | $81 | 20/20 | $67 |
| fvol | fade & hot corner (alone) | 18 | 0.9 | 0.0% | $183 | $-84 | $-279 | 6/20 | $-105 |
| stack | model top ∩ corner | 6 | 0.3 | 0.0% | $173 | $-30 | $-302 | 2/20 | $-45 |
| stack | top-3/day WITHIN the corner | 13 | 0.7 | 0.0% | $175 | $-84 | $-279 | 6/20 | $-88 |
| stack | top-3/day within fade (any vol) | 24 | 1.2 | 12.5% | $246 | $-60 | $-120 | 10/20 | $-52 |

## The forecast-vol / band-state block (`M_`)

34 channels joined from `_cache/fvol` at each candidate's last COMPLETED minute (a row stamped `second` is only read when `second < t`).  The hot/cool cut is the median per-session median `sigma_inst_bps` over the 20 strictly prior covered sessions, never the test block's own median.

| era | candidates | with `M_band_state` | with the ext x vol cell |
|---|---|---|---|
| `study_e1` | 2257 | 0% | 0% |
| `study_e1b` | 2955 | 0% | 0% |
| `study_e2` | 3902 | 80% | 75% |
| `study_e3` | 1861 | 100% | 100% |
| `study_e3b` | 500 | 100% | 100% |
| `blind_e3` | 466 | 100% | 100% |

### Ablation — the same rungs with the `M_` block removed

| seg | test | arm | AUC | top-3/day | top-5/day | lift vs random-3 |
|---|---|---|---|---|---|---|
| c | `study_e3` | with `M_` | 0.593 | $1,011 | $1,723 | 1.11x |
| c | `study_e3` | without `M_` | 0.587 | $1,030 | $1,762 | 1.13x |
| d | `study_e3b` | with `M_` | 0.697 | $1,006 | $1,808 | 1.27x |
| d | `study_e3b` | without `M_` | 0.712 | $992 | $1,822 | 1.25x |
| e | `blind_e3` | with `M_` | 0.646 | $1,459 | $2,203 | 1.43x |
| e | `blind_e3` | without `M_` | 0.651 | $1,511 | $2,188 | 1.48x |

### The landed EXTENSION x VOL cell, re-measured on every era

Rows are the contrast's own cells (`M_extension` = fade at band_state_own <= -2, chase at >= +2; `M_hot` = sigma_inst above the prior-sessions cut).  This is a population measurement, not a fit — no model is involved.

| era | cell | n | win rate | lift vs era base | mean cert |
|---|---|---|---|---|---|
| `study_e2` | fade x hot | 189 | 23.8% | 0.80x | $318 |
| `study_e2` | fade x cool | 60 | 11.7% | 0.39x | $228 |
| `study_e2` | mid x hot | 1834 | 34.5% | 1.16x | $468 |
| `study_e2` | mid x cool | 587 | 19.4% | 0.65x | $268 |
| `study_e2` | chase x hot | 191 | 35.1% | 1.18x | $435 |
| `study_e2` | chase x cool | 58 | 17.2% | 0.58x | $278 |
| `study_e3` | fade x hot | 148 | 43.2% | 2.01x | $482 |
| `study_e3` | fade x cool | 55 | 14.5% | 0.68x | $244 |
| `study_e3` | mid x hot | 1081 | 23.9% | 1.11x | $341 |
| `study_e3` | mid x cool | 380 | 11.3% | 0.53x | $215 |
| `study_e3` | chase x hot | 138 | 18.8% | 0.87x | $276 |
| `study_e3` | chase x cool | 59 | 3.4% | 0.16x | $117 |
| `study_e3b` | fade x hot | 10 | 20.0% | 0.93x | $299 |
| `study_e3b` | fade x cool | 12 | 0.0% | 0.00x | $120 |
| `study_e3b` | mid x hot | 335 | 27.5% | 1.28x | $336 |
| `study_e3b` | mid x cool | 120 | 10.0% | 0.47x | $166 |
| `study_e3b` | chase x hot | 10 | 10.0% | 0.47x | $203 |
| `study_e3b` | chase x cool | 13 | 0.0% | 0.00x | $127 |
| `blind_e3` | fade x hot | 54 | 5.6% | 0.23x | $214 |
| `blind_e3` | fade x cool | 5 | 0.0% | 0.00x | $221 |
| `blind_e3` | mid x hot | 324 | 31.8% | 1.29x | $401 |
| `blind_e3` | mid x cool | 28 | 14.3% | 0.58x | $228 |
| `blind_e3` | chase x hot | 50 | 10.0% | 0.41x | $290 |
| `blind_e3` | chase x cool | 5 | 0.0% | 0.00x | $45 |

### Replication of the landed cell with the contrast's own cut

The landed contrast fixed its hot/cool boundary at `sigma_inst_bps = 121.35` (the median of its own two blocks).  Applying that number verbatim reproduces its cells exactly on the blocks it was measured on, which makes every other row below an honest out-of-sample test of the same rule.

| block | base rate | fade & hot n | win rate | mean cert | chase & cool n | win rate |
|---|---|---|---|---|---|---|
| study_e3+study_e3b (the contrast's own blocks) | 21.5% | 102 | 50.0% | $523 | 127 | 7.1% |
| `study_e2` | 29.8% | 151 | 29.8% | $377 | 117 | 23.9% |
| `study_e3` | 21.5% | 99 | 49.5% | $511 | 107 | 8.4% |
| `study_e3b` | 21.4% | 3 | 66.7% | $901 | 20 | 0.0% |
| `blind_e3` | 24.7% | 9 | 0.0% | $184 | 47 | 8.5% |

### Permutation importance on segment e (test block `blind_e3`, AUC drop)

| rank | feature | AUC drop | sd |
|---|---|---|---|
| 1 | `C_erm_sigma_bps` | +0.0925 | 0.0238 |
| 2 | `V_pv_level` | +0.0072 | 0.0098 |
| 3 | `B_PS_OVERNIGHT_GAP` | +0.0054 | 0.0051 |
| 4 | `Q_opp_refill_ratio` | +0.0040 | 0.0013 |
| 5 | `C_erm_atr_bps` | +0.0033 | 0.0034 |
| 6 | `M_sigma_inst_bps` | +0.0028 | 0.0048 |
| 7 | `B_VB_XTILDE_OPEN` | +0.0022 | 0.0006 |
| 8 | `C_mag_against_bps` | +0.0019 | 0.0022 |
| 9 | `P_runway_s` | +0.0018 | 0.0040 |
| 10 | `X_D_depth60_z__R_atr_high` | +0.0014 | 0.0011 |
| 11 | `C_mag2_bps` | +0.0011 | 0.0009 |
| 12 | `M_traveled_bps` | +0.0011 | 0.0003 |
| 13 | `M_band1_room_bps` | +0.0011 | 0.0008 |
| 14 | `V_pv_asym` | +0.0011 | 0.0004 |
| 15 | `B_PS_D_OPEN_ATR` | +0.0010 | 0.0039 |
| 16 | `M_remaining_move_bps` | +0.0008 | 0.0004 |
| 17 | `M_sigma_inst_rel` | +0.0007 | 0.0014 |
| 18 | `V_dlog_bid10` | +0.0007 | 0.0004 |
| 19 | `F_flip_mag` | +0.0007 | 0.0008 |
| 20 | `P_cumflow_h_o` | +0.0007 | 0.0009 |

Every `M_` channel, wherever it landed:

| rank of 307 | feature | AUC drop |
|---|---|---|
| 6 | `M_sigma_inst_bps` | +0.0028 |
| 12 | `M_traveled_bps` | +0.0011 |
| 13 | `M_band1_room_bps` | +0.0011 |
| 16 | `M_remaining_move_bps` | +0.0008 |
| 17 | `M_sigma_inst_rel` | +0.0007 |
| 33 | `M_sigma_day_bps` | +0.0002 |
| 87 | `M_abs_traveled_bps` | +0.0000 |
| 88 | `M_sigma_now_bps` | +0.0000 |
| 89 | `M_var_fraction_expected` | +0.0000 |
| 90 | `M_rv_sofar_bps` | +0.0000 |
| 91 | `M_band_z` | +0.0000 |
| 92 | `M_band_state_own` | +0.0000 |
| 96 | `M_move_z_own` | +0.0000 |
| 97 | `M_move_z` | +0.0000 |
| 99 | `M_range_so_far_bps` | +0.0000 |
| 100 | `M_move_consumed_fraction` | +0.0000 |
| 114 | `M_range_consumed_fraction` | +0.0000 |
| 135 | `M_hot` | +0.0000 |
| 152 | `M_hot_cut_bps` | +0.0000 |
| 158 | `M_band2_room_bps` | +0.0000 |
| 179 | `M_implied_move_bps` | +0.0000 |
| 180 | `M_clock_third` | +0.0000 |
| 183 | `M_ext_vol_cell` | +0.0000 |
| 184 | `M_ext_x_hot` | +0.0000 |
| 185 | `M_extension` | +0.0000 |
| 186 | `M_sigma_inst_over_now` | +0.0000 |
| 192 | `M_band_state` | +0.0000 |
| 199 | `M_sigma_level_bps` | +0.0000 |
| 282 | `M_band_z_own` | -0.0001 |
| 285 | `M_traveled_bps_own` | -0.0001 |
| 287 | `M_band15_room_bps` | -0.0002 |
| 296 | `M_bso_x_sigma_inst` | -0.0007 |
| 306 | `M_bso_x_sigma_rel` | -0.0100 |

## Era-transfer matrix — the direct measurement of pattern decay

Each cell: ONE era fitted alone (frozen config, 243 columns usable in every era) and scored on another era.  Rows = train era, columns = test era.  The diagonal is left blank (a self-fit is in-sample and not comparable).

### AUC
| train \ test | `study_e1` | `study_e1b` | `study_e2` | `study_e3` | `study_e3b` | `blind_e3` |
|---|---|---|---|---|---|---|
| `study_e1` | — | 0.554 | 0.581 | 0.625 | 0.589 | 0.589 |
| `study_e1b` | 0.544 | — | 0.583 | 0.573 | 0.599 | 0.542 |
| `study_e2` | 0.599 | 0.539 | — | 0.614 | 0.719 | 0.585 |
| `study_e3` | 0.609 | 0.555 | 0.556 | — | 0.664 | 0.601 |
| `study_e3b` | 0.570 | 0.537 | 0.599 | 0.639 | — | 0.591 |
| `blind_e3` | 0.577 | 0.507 | 0.569 | 0.535 | 0.597 | — |

### top-3/day exit-free cert
| train \ test | `study_e1` | `study_e1b` | `study_e2` | `study_e3` | `study_e3b` | `blind_e3` |
|---|---|---|---|---|---|---|
| `study_e1` | — | $1,390 | $1,362 | $1,337 | $826 | $790 |
| `study_e1b` | $1,224 | — | $1,397 | $1,038 | $1,022 | $921 |
| `study_e2` | $1,267 | $1,079 | — | $1,114 | $1,084 | $1,329 |
| `study_e3` | $1,590 | $1,370 | $1,485 | — | $1,250 | $1,115 |
| `study_e3b` | $1,317 | $1,819 | $1,573 | $1,200 | — | $1,361 |
| `blind_e3` | $1,477 | $1,349 | $1,578 | $992 | $1,031 | — |

### lift vs random-3
| train \ test | `study_e1` | `study_e1b` | `study_e2` | `study_e3` | `study_e3b` | `blind_e3` |
|---|---|---|---|---|---|---|
| `study_e1` | — | 1.05x | 1.20x | 1.47x | 1.04x | 0.77x |
| `study_e1b` | 1.06x | — | 1.23x | 1.14x | 1.29x | 0.90x |
| `study_e2` | 1.10x | 0.82x | — | 1.22x | 1.36x | 1.30x |
| `study_e3` | 1.38x | 1.04x | 1.31x | — | 1.57x | 1.09x |
| `study_e3b` | 1.14x | 1.38x | 1.38x | 1.32x | — | 1.33x |
| `blind_e3` | 1.28x | 1.02x | 1.39x | 1.09x | 1.30x | — |

#### Marginals — is the cell driven by WHO TRAINED or WHO IS TESTED?
| era | as TRAIN era: mean AUC | mean top-3/day | as TEST era: mean AUC | mean top-3/day |
|---|---|---|---|---|
| `study_e1` | 0.587 | $1,141 | 0.580 | $1,375 |
| `study_e1b` | 0.568 | $1,120 | 0.538 | $1,401 |
| `study_e2` | 0.611 | $1,175 | 0.577 | $1,479 |
| `study_e3` | 0.597 | $1,362 | 0.597 | $1,136 |
| `study_e3b` | 0.587 | $1,454 | 0.634 | $1,043 |
| `blind_e3` | 0.557 | $1,285 | 0.582 | $1,103 |

Spread of the row means (train era): AUC 0.054, top-3/day $334.  Spread of the column means (test era): AUC 0.095, top-3/day $436.

#### Decay by era distance (mean over cells at each gap)
| gap (eras) | direction | cells | mean AUC | mean top-3/day | mean lift vs random-3 |
|---|---|---|---|---|---|
| 1 | backward | 5 | 0.575 | $1,204 | 1.16x |
| 1 | forward | 5 | 0.601 | $1,302 | 1.28x |
| 2 | backward | 4 | 0.572 | $1,301 | 1.15x |
| 2 | forward | 4 | 0.618 | $1,150 | 1.20x |
| 3 | backward | 3 | 0.572 | $1,662 | 1.38x |
| 3 | forward | 3 | 0.603 | $1,229 | 1.35x |
| 4 | backward | 2 | 0.539 | $1,333 | 1.08x |
| 4 | forward | 2 | 0.565 | $873 | 0.97x |
| 5 | backward | 1 | 0.577 | $1,477 | 1.28x |
| 5 | forward | 1 | 0.589 | $790 | 0.77x |

## Segment e against MODEL_V2 (same test block, more training data)

v2 trained on 398..412 (273 candidates) and tested on the same `blind_e3` roster.  This lane trains on 11475 candidates from 5 eras.

`v2 slice refit` below is the CONTROL: v2's own training rows (398..412, 273 candidates, 288 columns) refitted inside THIS harness with the same frozen config, so any gap between it and the published v2 numbers is harness noise and any gap between it and the pooled arm is training data alone.

| quantity | MODEL_V2 published | v2 slice refit here | walk-forward pooled | walk-forward regime-weighted | delta (pooled - v2 published) |
|---|---|---|---|---|---|
| blind AUC | 0.641 | 0.629 | 0.646 | 0.636 | +0.005 |
| top-3/day exit-free cert | $1,672 | $1,654 | $1,459 | $1,575 | -$213 |
| top-5/day exit-free cert | $2,569 | $2,506 | $2,203 | $2,156 | -$366 |
| cert/taken @27.5% | $477 | $477 | $469 | $475 | -$8 |
| operating-point lift | 1.57x | 1.57x | 1.53x | 1.56x | -0.037 |

RTY-mini overlay (D-022, `blind_e3` mean f=0.879): pooled top-3/day $1,282, regime-weighted $1,384, v2 published $1,469.

## Controls
- LABEL-SHUFFLE control on segment e (train labels permuted, 5 draws): AUC 0.488 +/- 0.043 (real 0.646); top-3/day $940 (real $1,459).
- Walk-forward purity: every rung's test block is strictly LATER than every session in its training window; the estimator config is frozen from v2 and is never re-selected on any block here.
- Session coverage: 323 sessions, no era block excluded, no day excluded (D-038 §3).

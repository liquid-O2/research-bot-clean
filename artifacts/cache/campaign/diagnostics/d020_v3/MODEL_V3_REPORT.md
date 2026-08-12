# MODEL V3 REPORT — the hybrid: the proven reader judgment inside the selector

## VERDICT — the walk-forward target is beaten, the single-block AUC target is beaten only by the arm that throws v2 away

**Walk-forward segment e — BEATEN on both legs.**  With the frozen config and five eras of training, v3 scores AUC 0.655 and top-3 **$1,598/day** against the published 0.646 / $1,459, which this harness reproduces exactly (0.646 / $1,459) when the v3 columns are removed.  That is +10% on the deployable selection number and +0.009 AUC, from features alone: same estimator, same rows, same rung.  Across the whole ladder v3 beats v2 on top-3 $/day in 3 of 5 segments.

**v2 protocol (train on 273 study rows, judge blind_e3) — dollars a tie, AUC not beaten by the full stack.**  v3 FULL lands $1,680/day against the published $1,672 and $1,654 for the v2 columns rerun here (a tie inside harness noise), with blind AUC 0.626 against 0.641 published / 0.629 rerun.  On 273 rows, 417 columns is too many; the arm that DROPS the whole v1+v2 block is the one that works.

**The finding: the v3 tiers ALONE are the best ranker on this roster.**  `E_/T_/I_ ONLY` — 129 columns, no v1 and no v2 channel at all — scores blind AUC **0.676**, beating BOTH published AUC anchors (0.641 GBT and 0.674 L1), and it does it while lifting the human operating point to **1.98x** with $548 per taken candidate and a 43% win rate on takes, against v2's 1.57x / $477 / 33.6%.  Its study CV AUC is 0.503 — i.e. it looks WORTHLESS in-era and is the strongest arm out of era, which is the third time this project has seen study CV fail to resolve arms and is a direct restatement of MODEL_V2_REPORT's caveat (1).  On the walk-forward ladder the same arm beats the v2 column set on AUC in 4 of 5 segments (segment e 0.665 against 0.646) — but its top-3 dollars collapse there ($1,068 against $1,459), so it ranks the population better and the TOP of the day worse.  It is a genuine finding, not a deployable arm: nothing here promotes it, because it is one 20-day block and the walk-forward rung disagrees with it on money.

**Ablations — what actually paid.**

* **CC-013 greeks (`T_`) PAY, in dollars, not in AUC.**  Dropping them costs $163/day on the v2 protocol ($1,518 against $1,680) and $123/day on segment e, while the AUC moves the other way (0.609 against 0.626).  Same signature as v2's own tiers: they sharpen the top of the ranking and add noise in the middle.  In permutation importance the whole `T_` family is near zero, which is the AUC view of exactly that.
* **qr_ivx window objects (`I_`) PAY.**  Dropping them costs $179/day, and `I_curvature_0dte` and `I_atm_iv` are blind permutation ranks 2 and 3 out of 441 columns — the `I_` family is the second largest importance block on the blind set, behind only capacity.  This is the strongest single new-data result in the lane: the 0DTE expiry's own smile CURVATURE, joined from a window that closed before the decision second, carries real out-of-era information.
* **The capacity REFINEMENTS did NOT pay on top of v2's existing `C_` block.**  Removing them IMPROVES the v2-protocol arm ($1,708 and AUC 0.636 against $1,680 / 0.626) and costs only $36/day on segment e.  The honest reading is that `C_giveback_frac` + `C_objective_bps` already carried the arithmetic and the net-runway restatement is mostly a re-parameterisation.  What the exam text added that v2 did not have is the GATE CONJUNCTION, and that shows up as a population fact rather than a model feature: `E_gate_clean` fires on 9.3% of all 11,941 candidates and lifts the winner rate from 27.9% to 33.9% and mean cert from $388 to $478 with no signal read at all.

**The imitation channel did not pay — reported as run.**  Agreement-weighting the training rows on `E_opus_soft` moves segment e to AUC 0.652 and $1,217/day, both WORSE than unweighted (0.655 / $1,598); on the v2 protocol it trades $115/day of top-3 for a higher operating-point lift (1.59x against 1.46x).  The signature itself separates: it fires on 5-18% of candidates in every era and carries a higher winner rate and mean cert in ALL SIX blocks, which is why it is worth keeping as a COLUMN.  What it does not do is improve the fit when used as a weight, and the reason is visible in the fidelity diagnostic: the strict reproduction of the reader's rule fires on 0 of 466 blind candidates, so the soft version is a different, much broader object than the judgment it was meant to imitate.

**Caveats, stated plainly.**  (1) The blind block is 20 days and 466 candidates; a $139/day segment-e gain is one good day away from noise, which is why the five-segment ladder is reported beside it.  (2) Study CV is again unable to resolve arms (the best out-of-era arm has the worst study CV), so no arm here may be promoted on CV evidence and none is.  (3) The `E_/T_/I_ ONLY` result is the kind of thing that reverses; it is published as a finding to be retested on `blind_e4..e7`, not as a recommendation.  (4) `I_` coverage is 58-82% by era (the option-quote surface starts at session 209), so its contribution is measured on a partially covered column.


Matrix 11941 candidates x 462 columns over 323 sessions in 6 era blocks. v3 adds 134 columns in three families: `E_` codified-Opus arithmetic + panel convergences, `T_` CC-013 full-greek flows, `I_` qr_ivx window objects.

## A. v2 PROTOCOL — train on the study block (398..412), judge blind_e3

Config re-selected by grouped study CV inside every arm, exactly as `model_v2.py` does, so the comparison against v2's published numbers is like-for-like.

| arm | features | study CV AUC | blind AUC | top-1 $/day | top-3 $/day | top-5 $/day | $/cand | lift @27.5% | cert/taken |
|---|---|---|---|---|---|---|---|---|---|
| v2 BASELINE (the published v2/walk-forward set) | 288 | 0.683 | **0.629** | $649 | **$1,654** | $2,506 | $551 | 1.57x | $477 |
| v3 FULL (v2 + E_ + T_ + I_) | 417 | 0.667 | **0.626** | $571 | **$1,680** | $2,367 | $560 | 1.46x | $455 |
| v3 minus GREEKS (drop T_) | 379 | 0.684 | **0.609** | $522 | **$1,518** | $2,302 | $506 | 1.39x | $442 |
| v3 minus CAPACITY REFINEMENTS | 395 | 0.668 | **0.636** | $558 | **$1,708** | $2,473 | $569 | 1.52x | $466 |
| v3 minus IVX (drop I_) | 383 | 0.674 | **0.628** | $568 | **$1,501** | $2,383 | $500 | 1.42x | $447 |
| v3 minus AGREEMENT (drop the joint-z block) | 404 | 0.663 | **0.630** | $517 | **$1,662** | $2,465 | $554 | 1.38x | $439 |
| E_/T_/I_ ONLY (drop the whole v2 block) | 129 | 0.503 | **0.676** | $539 | **$1,544** | $2,607 | $515 | 1.98x | $548 |

Published v2 anchors on this identical roster: blind AUC **0.641** (GBT) / **0.674** (L1 twin), top-3 **$1,672**/day, top-5 $2,569/day, lift 1.57x, oracle $3,028/day, random-3 $1,021/day.

### L1 logistic twin (the 0.674 baseline)

CAVEAT on this row: v2's published 0.674 twin was fitted on `FEATURES_V2.tsv`; the `v2 BASELINE` set here is the walk-forward matrix, which also carries the `M_` forecast-vol block, so the twin is not the identical estimator.  Read the two rows against each other, not against the published number.

| arm | C | study CV AUC | blind AUC | top-3 $/day |
|---|---|---|---|---|
| v2 BASELINE (the published v2/walk-forward set) | 0.2 | 0.623 | **0.584** | $1,493 |
| v3 FULL (v2 + E_ + T_ + I_) | 0.05 | 0.617 | **0.613** | $1,605 |

Non-zero L1 weights of the v3 twin (study-selected):
  - `B_PS_OVERNIGHT_GAP` -0.192
  - `E_cap_sigma_vs_B` +0.144
  - `B_PS_D_PRIOR_LOW` -0.097
  - `C_erm_sigma_bps` +0.063
  - `M_hot_cut_bps` -0.049
  - `P_trend_size` -0.036
  - `R_late` -0.029

## B. WALK-FORWARD LADDER — frozen v2 config, expanding window, segments a..e

Estimator frozen at `{'max_depth': 2, 'max_iter': 150, 'learning_rate': 0.05, 'min_samples_leaf': 20, 'l2_regularization': 1.0}` for every fit below and never re-selected.

| seg | test block | arm | features | AUC | top-3 $/day | top-5 $/day | lift vs random-3 | lift @27.5% |
|---|---|---|---|---|---|---|---|---|
| **a** | `study_e1b` | v2 | 243 | 0.554 | **$1,390** | $2,307 | 1.05x | 1.09x |
| **a** | `study_e1b` | v3 | 365 | 0.551 | **$1,515** | $2,450 | 1.15x | 1.15x |
| **a** | `study_e1b` | v3 minus GREEKS | 327 | 0.547 | **$1,494** | $2,357 | 1.13x | 1.16x |
| **a** | `study_e1b` | v3 minus CAPACITY REFINEMENTS | 341 | 0.554 | **$1,619** | $2,508 | 1.22x | 1.12x |
| **a** | `study_e1b` | v3 NEW TIERS ONLY (E_+T_+I_) | 122 | 0.568 | **$1,572** | $2,870 | 1.19x | 1.19x |
| **b** | `study_e2` | v2 | 267 | 0.569 | **$1,307** | $2,090 | 1.15x | 1.07x |
| **b** | `study_e2` | v3 | 401 | 0.572 | **$1,229** | $2,143 | 1.08x | 1.08x |
| **b** | `study_e2` | v3 minus GREEKS | 363 | 0.579 | **$1,292** | $2,146 | 1.14x | 1.15x |
| **b** | `study_e2` | v3 minus CAPACITY REFINEMENTS | 377 | 0.575 | **$1,231** | $2,102 | 1.08x | 1.15x |
| **b** | `study_e2` | v3 NEW TIERS ONLY (E_+T_+I_) | 134 | 0.588 | **$1,317** | $2,164 | 1.16x | 1.35x |
| **c** | `study_e3` | v2 | 307 | 0.593 | **$1,011** | $1,723 | 1.11x | 1.11x |
| **c** | `study_e3` | v3 | 441 | 0.611 | **$1,116** | $1,844 | 1.23x | 1.14x |
| **c** | `study_e3` | v3 minus GREEKS | 403 | 0.612 | **$1,046** | $1,770 | 1.15x | 1.18x |
| **c** | `study_e3` | v3 minus CAPACITY REFINEMENTS | 417 | 0.611 | **$1,116** | $1,844 | 1.23x | 1.14x |
| **c** | `study_e3` | v3 NEW TIERS ONLY (E_+T_+I_) | 134 | 0.653 | **$1,297** | $2,079 | 1.42x | 1.43x |
| **d** | `study_e3b` | v2 | 307 | 0.697 | **$1,006** | $1,808 | 1.27x | 1.73x |
| **d** | `study_e3b` | v3 | 441 | 0.703 | **$1,001** | $1,710 | 1.26x | 1.71x |
| **d** | `study_e3b` | v3 minus GREEKS | 403 | 0.699 | **$1,000** | $1,675 | 1.26x | 1.64x |
| **d** | `study_e3b` | v3 minus CAPACITY REFINEMENTS | 417 | 0.700 | **$939** | $1,678 | 1.18x | 1.75x |
| **d** | `study_e3b` | v3 NEW TIERS ONLY (E_+T_+I_) | 134 | 0.675 | **$1,033** | $1,568 | 1.30x | 1.45x |
| **e** | `blind_e3` | v2 | 307 | 0.646 | **$1,459** | $2,203 | 1.43x | 1.53x |
| **e** | `blind_e3` | v3 | 441 | 0.655 | **$1,598** | $2,173 | 1.57x | 1.47x |
| **e** | `blind_e3` | v3 minus GREEKS | 403 | 0.659 | **$1,475** | $2,046 | 1.44x | 1.47x |
| **e** | `blind_e3` | v3 minus CAPACITY REFINEMENTS | 417 | 0.661 | **$1,562** | $2,135 | 1.53x | 1.53x |
| **e** | `blind_e3` | v3 NEW TIERS ONLY (E_+T_+I_) | 134 | 0.665 | **$1,068** | $1,818 | 1.05x | 1.56x |

Published walk-forward anchors (v2 features, same rungs): a 0.554/$1,390 | b 0.569/$1,307 | c 0.593/$1,011 | d 0.697/$1,006 | e 0.646/**$1,459**.

### The 27.5% operating point on `blind_e3` — the shape the human works in

| protocol | arm | cert/taken | cert/skipped | lift | win-rate taken | MAE/pick | top-3 $/day |
|---|---|---|---|---|---|---|---|
| v2 protocol | v2 BASELINE (the published v2/walk-forward set) | $477 | $303 | 1.57x | 32.8% | $134 | $1,654 |
| v2 protocol | v3 FULL (v2 + E_ + T_ + I_) | $455 | $312 | 1.46x | 30.5% | $125 | $1,680 |
| v2 protocol | v3 minus GREEKS (drop T_) | $442 | $317 | 1.39x | 31.2% | $112 | $1,518 |
| v2 protocol | v3 minus CAPACITY REFINEMENTS | $466 | $307 | 1.52x | 32.0% | $128 | $1,708 |
| v2 protocol | v3 minus IVX (drop I_) | $447 | $315 | 1.42x | 29.7% | $133 | $1,501 |
| v2 protocol | v3 minus AGREEMENT (drop the joint-z block) | $439 | $318 | 1.38x | 31.2% | $120 | $1,662 |
| v2 protocol | E_/T_/I_ ONLY (drop the whole v2 block) | $548 | $277 | 1.98x | 43.0% | $122 | $1,544 |
| segment e | v2 | $469 | n/a | 1.53x | 34.4% | $124 | $1,459 |
| segment e | v3 | $457 | n/a | 1.47x | 33.6% | $132 | $1,598 |
| segment e | v3 minus GREEKS | $456 | n/a | 1.47x | 35.2% | $131 | $1,475 |
| segment e | v3 minus CAPACITY REFINEMENTS | $468 | n/a | 1.53x | 35.9% | $123 | $1,562 |
| segment e | v3 NEW TIERS ONLY (E_+T_+I_) | $474 | n/a | 1.56x | 34.4% | $115 | $1,068 |

Anchor: v2 published 1.57x, cert/taken $477, win-rate taken 33.6%, MAE/pick $123.

## C. THE IMITATION CHANNEL — agreement-weighted training, study side only

`E_opus_take` is the codified Opus signature: all six capacity gates clean, the two streams agreeing at |z| >= 3 on the candidate's own side, and the give-back inside Opus's stated 30% ceiling.  It is a FORMULA from `OPUS_METHOD.md` prose, never a call and never an outcome.  It reproduces the reader's own exam take rate (about 1%), which is too rare to move a sample weight, so the weighting carrier is `E_opus_soft` — at most one gate down and EITHER half of the evidence pair present.  Rows where it fires get sample weight 1 + 1; everything else weighs 1.

| block | candidates | strict fires | soft fires | soft rate | winner rate ON | winner rate OFF | mean cert ON | mean cert OFF |
|---|---|---|---|---|---|---|---|---|
| `study_e1` | 2257 | 1 | 285 | 12.6% | 32.3% | 28.9% | $502 | $385 |
| `study_e1b` | 2955 | 0 | 541 | 18.3% | 36.4% | 31.2% | $531 | $450 |
| `study_e2` | 3902 | 0 | 418 | 10.7% | 35.4% | 29.2% | $492 | $392 |
| `study_e3` | 1861 | 0 | 177 | 9.5% | 26.6% | 21.0% | $323 | $310 |
| `study_e3b` | 500 | 0 | 26 | 5.2% | 30.8% | 20.9% | $497 | $269 |
| `blind_e3` | 466 | 0 | 42 | 9.0% | 28.6% | 24.3% | $480 | $338 |

The capacity conjunction alone (`E_gate_clean` — all six gates pass, no signal read at all), measured as a population over every era:
- fires on 1116 of 11941 candidates (9.3%); winner rate 33.9% against 27.9% off, mean cert $478 against $388.

| protocol | arm | AUC | top-3 $/day | top-5 $/day | lift @27.5% |
|---|---|---|---|---|---|
| v2 protocol (study 398..412 -> blind_e3) | unweighted | 0.626 | $1,680 | $2,367 | 1.46x |
| v2 protocol (study 398..412 -> blind_e3) | agreement-weighted | 0.622 | $1,565 | $2,527 | 1.59x |
| walk-forward segment e (5 eras -> blind_e3) | unweighted | 0.655 | $1,598 | $2,173 | 1.47x |
| walk-forward segment e (5 eras -> blind_e3) | agreement-weighted | 0.652 | $1,217 | $1,929 | 1.45x |

## D. Permutation importance on `blind_e3` (segment-e fit, diagnostic only)

| rank | feature | AUC drop | sd |
|---|---|---|---|
| 1 | `C_erm_sigma_bps` | +0.0736 | 0.0237 |
| 2 | `I_curvature_0dte` | +0.0138 | 0.0108 |
| 3 | `I_atm_iv` | +0.0089 | 0.0086 |
| 4 | `Q_opp_refill_ratio` | +0.0054 | 0.0016 |
| 5 | `M_sigma_inst_bps` | +0.0036 | 0.0036 |
| 6 | `I_pv_level` | +0.0031 | 0.0042 |
| 7 | `B_PS_EDGE_DISTANCE_HIGH_20D` | +0.0028 | 0.0006 |
| 8 | `B_VB_XTILDE_VWAP` | +0.0025 | 0.0040 |
| 9 | `P_runway_s` | +0.0018 | 0.0037 |
| 10 | `C_erm_atr_bps` | +0.0017 | 0.0014 |
| 11 | `V_pv_level` | +0.0016 | 0.0042 |
| 12 | `B_PS_D_OPEN_ATR` | +0.0016 | 0.0032 |
| 13 | `I_pv_relative_change` | +0.0014 | 0.0015 |
| 14 | `Q_erosion_tilt` | +0.0012 | 0.0010 |
| 15 | `H_resid1800_z_o` | +0.0011 | 0.0013 |
| 16 | `H_resid300_z_o` | +0.0010 | 0.0017 |
| 17 | `B_PS_OVERNIGHT_GAP` | +0.0010 | 0.0050 |
| 18 | `C_erm_unspent_bps` | +0.0009 | 0.0004 |
| 19 | `M_band1_room_bps` | +0.0009 | 0.0006 |
| 20 | `C_mag2_bps` | +0.0008 | 0.0006 |
| 21 | `X_D_depth60_z__R_atr_high` | +0.0008 | 0.0014 |
| 22 | `W_resid_o` | +0.0007 | 0.0006 |
| 23 | `C_mag_against_bps` | +0.0005 | 0.0019 |
| 24 | `T_vomma600_o` | +0.0004 | 0.0011 |
| 25 | `E_elast_z` | +0.0003 | 0.0004 |

Family totals (sum of positive importance): `C_` 0.0776, `I_` 0.0273, `B_` 0.0079, `Q_` 0.0072, `M_` 0.0050, `H_` 0.0025, `P_` 0.0020, `V_` 0.0018, `X_` 0.0008, `W_` 0.0007, `T_` 0.0005, `E_` 0.0003

## E. Controls

- LABEL-SHUFFLE (segment e, 5 draws, v3 columns): AUC 0.478 +/- 0.045 against the real 0.655.
- LABEL-SHUFFLE (v2 protocol, v3 columns): blind AUC 0.361.
- WALK-FORWARD PURITY: every rung's test block is strictly later than every session in its training window; the frozen config is v2's and is never re-selected in section B or C.
- BLIND HYGIENE: no Opus call (40-case round or 466-case exam) is a label, a weight, a threshold or a column anywhere in the fitted path.  The imitation weights are computed from `E_opus_soft` on TRAINING rows only, and that column is a formula over v2 channels with thresholds quoted from OPUS_METHOD prose.
- CAUSALITY: `T_` windows end at and exclude the decision second and are z-scored against strictly prior blocks; `I_` reads window `t // 1800 - 1`, which closes at or before t; `E_` is arithmetic on v2 columns.

## F. FIDELITY DIAGNOSTIC — does the codified signature reproduce the reader?  (read-only, computed after every model number above)

Row order verification: the exam ledger is 466 rows against 466 blind candidates, and its own arithmetic pins the alignment — case0095 reads `cap-ok 5.9h` against phase 0.08 (5.97h of session left), case0297 reads `22bp giveback into a 71bp runway` against `C_giveback_bps` 22.3 and `C_mag1_bps` 71.0.

- Opus's exam on this roster: 5 TAKE / 461 SKIP (take rate 1.1%).
- Strict `E_opus_take` fires on 0 rows and covers 0 of the 5 reader TAKEs.
- Soft `E_opus_soft` fires on 42 rows and covers 1 of the 5 reader TAKEs.
- The v3 model's own top-27.5% slice contains 2 of the 5 reader TAKEs.
- Reader TAKEs realised: mean cert $551, winner rate 40.0%, against the block's 24.7% and mean cert $351.
- Soft-signature rows realised: mean cert $480, winner rate 28.6%.


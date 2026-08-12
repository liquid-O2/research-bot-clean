# ERA-RETEST REPORT — the first 2024-2025 validation of the v2 / v3 selectors

Frozen estimator for EVERY fit below (v2's config, never re-selected): `{'max_depth': 2, 'max_iter': 150, 'learning_rate': 0.05, 'min_samples_leaf': 20, 'l2_regularization': 1.0}`.  Expanding-window ladder extended over the four newly opened era blocks, 21,037 candidates, 792 sessions 125..917.  Sealed zone 918+ untouched.


## VERDICT

**1. The `E_/T_/I_ ONLY` finding HELD out of era.  The number 0.676 did not.**  In every one of the four newly opened eras that arm — 134 columns, not one v1 or v2 channel among them — has the highest AUC of all five arms: 0.618 in 2023 Q4, 0.639 in 2024 H1, 0.648 in 2024 H2, 0.639 in 2025, beating the best other arm by +0.014 / +0.004 / +0.018 / +0.011.  Across the four new eras it also carries the best mean top-3 dollars ($1,291/day against v2's $1,226) and the best mean operating-point lift (1.47x against 1.34x), which is the first time this arm has won on money as well as on ranking.  What did NOT survive is the level: 0.676 was one 20-day block's high-water mark, and the honest out-of-era number for this arm is about **0.64**.  On the four 20-day blind sub-blocks it leads on only one (`blind_e4` 0.570); `v3 no-M` leads the other three.  Read plainly: dropping the entire v1+v2 block makes a BETTER ranker in every era we can now see, and the effect size is a third of what the single block advertised.

**2. The era offer in 2024-25 is middling, not rich — and 2025 is the best of it.**  Oracle top-3/day runs $2,841 (2023 Q4), $2,614 (2024 H1), $2,931 (2024 H2), $3,239 (2025).  That is above 2023's thin trough ($2,257-$2,666) and well below the 2022 peak ($3,817-$5,165) — the thin/rich map extends as a middle band, not a new rich era.  Winner rates 24.5-28.6%, mean cert $356-$429.  One number moved a lot and matters for the user's own reporting: the D-022 RTY factor crossed 1.0 (0.895 -> 1.004 -> 1.099 -> 1.073), so from 2024 on, a dollar on our $100k IWM object is worth slightly MORE than a dollar on one RTY mini, where in 2022-23 it was worth less.

**3. NO arm clears $1,500/day at top-3 in any 2024-25 era; every arm clears it at top-5; and neither of those is the deployable number.**  Best top-3/day: $1,391 (2023 Q4, `E/T/I only`), $1,220 (2024 H1, `E/T/I only`), $1,362 (2024 H2, `v2 no-M`), $1,446 (2025, `v3 no-M`) — all short of D-043's floor.  Best top-5/day: $2,134 / $2,015 / $2,195 / $2,225 — all above it.  The honest caveat is that both of those sum the exit-free certified value of k picks a day, while the deployable D-019 shape is ONE position: the earliest of the day's three picks, entered and held to the close, one contract.  That number is **-$90 to +$64/day** in every era and every arm.  The selector ranks candidates better than chance in every era; it does not yet produce a deployable P&L, and D-043's floor is not met on the deployable shape anywhere.

**4. The label-shuffle control is clean on the new data.**  On segment i (2025, the largest new block, 3,972 candidates over 181 days), permuted training labels give AUC 0.495-0.510 +/- 0.017-0.029 across the five arms against the real 0.625-0.639, and top-3 $1,045-$1,129/day against the real $1,320-$1,446.

**5. Two further results worth naming.**  (a) **The edge did not decay with era distance.**  The v2 column set scores mean AUC 0.618 over the four new eras against 0.612 on the published 2022-23 ladder, and 2025 — three years past the oldest training session — scores 0.628.  Whatever changes across eras, it is not that the patterns stop being true.  (b) **The `M_` forecast-vol block still does not pay.**  Dropping it improves top-3 dollars in 3 of 4 new eras on the v2 set (+$94 / +$65 / +$82 / +$9) and in 3 of 4 on v3 (+$46 / -$29 / +$26 / +$125), and never costs more than 0.011 AUC.  The 2024-25 data confirms the published verdict rather than overturning it.

## Era census — the OFFER, extended into 2024-25

| era | sessions | days | candidates | winner rate | mean cert | oracle top-3/day | oracle top-5/day | random-3/day | RTY f | `M_` cov | `I_` cov | `T_` cov | `E_` cov |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `study_e1` | 125..179 | 55 | 2257 | 29.3% | $400 | $3,817 | $5,894 | $1,153 | 0.922 | 0.0% | 58.3% | 100.0% | 99.8% |
| `study_e1b` | 180..229 | 50 | 2955 | 32.1% | $465 | $5,165 | $8,099 | $1,322 | 0.882 | 0.0% | 66.0% | 100.0% | 99.8% |
| `study_e2` | 230..330 | 101 | 3902 | 29.8% | $403 | $3,945 | $6,017 | $1,136 | 0.907 | 79.1% | 81.7% | 100.0% | 99.8% |
| `study_e3` | 331..397 | 67 | 1861 | 21.5% | $311 | $2,666 | $4,041 | $911 | 0.919 | 100.0% | 80.2% | 100.0% | 99.8% |
| `study_e3b` | 398..427 | 30 | 500 | 21.4% | $281 | $2,257 | $3,255 | $794 | 0.936 | 100.0% | 79.9% | 100.0% | 99.7% |
| `blind_e3` | 428..447 | 20 | 466 | 24.7% | $351 | $3,028 | $4,555 | $1,021 | 0.879 | 100.0% | 80.9% | 100.0% | 99.7% |
| `e4` | 448..497 | 50 | 759 | 28.6% | $390 | $2,841 | $4,013 | $1,050 | 0.895 | 100.0% | 80.4% | 100.0% | 99.6% |
| `e5` | 498..623 | 126 | 2248 | 24.5% | $356 | $2,614 | $3,783 | $979 | 1.004 | 100.0% | 85.1% | 100.0% | 99.7% |
| `e6` | 624..735 | 112 | 2117 | 26.9% | $372 | $2,931 | $4,225 | $1,060 | 1.099 | 100.0% | 92.6% | 100.0% | 99.7% |
| `e7` | 736..917 | 181 | 3972 | 28.3% | $429 | $3,239 | $4,673 | $1,083 | 1.073 | 100.0% | 93.9% | 100.0% | 99.7% |

## Reproduction control — the published rung `e`, refitted here

Same rung, same frozen config, on the EXTENDED matrix.  Any drift against the published anchors would mean the extension changed the old rows.

| arm | AUC here | AUC published | top-3 $/day here | top-3 $/day published |
|---|---|---|---|---|
| v2 | 0.646 | 0.646 | $1,459 | $1,459 |
| v2 no-M | 0.651 | 0.651 | $1,511 | $1,511 |
| v3 full | 0.655 | 0.655 | $1,598 | $1,598 |
| v3 no-M | 0.664 | n/a | $1,505 | n/a |
| E/T/I only | 0.665 | 0.665 | $1,068 | $1,068 |

## The extended ladder — segments f..i, four new eras

| seg | test era | window | arm | features | AUC | top-3 $/day | top-3 RTY-mini | top-5 $/day | lift@27.5% | oracle top-3/day | trades/day | lift vs random-3 | cert/taken |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **f** | `e4` (2023 Q4  2023-10-16..12-26) | 125..447 -> e4 | v2 | 307 | 0.595 | **$1,153** | $1,032 | $1,899 | 1.13x | $2,841 | 4.2 | 1.10x | $427 |
| **f** | `e4` (2023 Q4  2023-10-16..12-26) | 125..447 -> e4 | v2 no-M | 274 | 0.584 | **$1,247** | $1,116 | $1,893 | 1.20x | $2,841 | 4.2 | 1.19x | $443 |
| **f** | `e4` (2023 Q4  2023-10-16..12-26) | 125..447 -> e4 | v3 full | 441 | 0.595 | **$1,223** | $1,095 | $1,975 | 1.21x | $2,841 | 4.2 | 1.16x | $445 |
| **f** | `e4` (2023 Q4  2023-10-16..12-26) | 125..447 -> e4 | v3 no-M | 408 | 0.604 | **$1,269** | $1,136 | $2,055 | 1.26x | $2,841 | 4.2 | 1.21x | $459 |
| **f** | `e4` (2023 Q4  2023-10-16..12-26) | 125..447 -> e4 | E/T/I only | 134 | 0.618 | **$1,391** | $1,245 | $2,134 | 1.24x | $2,841 | 4.2 | 1.32x | $454 |
| **g** | `e5` (2024 H1  2023-12-27..2024-06-27) | 125..497 -> e5 | v2 | 307 | 0.633 | **$1,088** | $1,093 | $1,848 | 1.35x | $2,614 | 4.9 | 1.11x | $437 |
| **g** | `e5` (2024 H1  2023-12-27..2024-06-27) | 125..497 -> e5 | v2 no-M | 274 | 0.628 | **$1,153** | $1,158 | $1,863 | 1.29x | $2,614 | 4.9 | 1.18x | $425 |
| **g** | `e5` (2024 H1  2023-12-27..2024-06-27) | 125..497 -> e5 | v3 full | 441 | 0.635 | **$1,150** | $1,155 | $1,801 | 1.40x | $2,614 | 4.9 | 1.17x | $448 |
| **g** | `e5` (2024 H1  2023-12-27..2024-06-27) | 125..497 -> e5 | v3 no-M | 408 | 0.630 | **$1,121** | $1,126 | $1,849 | 1.36x | $2,614 | 4.9 | 1.15x | $440 |
| **g** | `e5` (2024 H1  2023-12-27..2024-06-27) | 125..497 -> e5 | E/T/I only | 134 | 0.639 | **$1,220** | $1,225 | $2,015 | 1.44x | $2,614 | 4.9 | 1.25x | $456 |
| **h** | `e6` (2024 H2  2024-06-28..12-05) | 125..623 -> e6 | v2 | 307 | 0.618 | **$1,281** | $1,407 | $2,061 | 1.28x | $2,931 | 5.2 | 1.21x | $441 |
| **h** | `e6` (2024 H2  2024-06-28..12-05) | 125..623 -> e6 | v2 no-M | 274 | 0.622 | **$1,362** | $1,497 | $2,195 | 1.34x | $2,931 | 5.2 | 1.28x | $455 |
| **h** | `e6` (2024 H2  2024-06-28..12-05) | 125..623 -> e6 | v3 full | 441 | 0.627 | **$1,278** | $1,404 | $1,997 | 1.41x | $2,931 | 5.2 | 1.21x | $470 |
| **h** | `e6` (2024 H2  2024-06-28..12-05) | 125..623 -> e6 | v3 no-M | 408 | 0.630 | **$1,304** | $1,433 | $2,048 | 1.29x | $2,931 | 5.2 | 1.23x | $445 |
| **h** | `e6` (2024 H2  2024-06-28..12-05) | 125..623 -> e6 | E/T/I only | 134 | 0.648 | **$1,231** | $1,353 | $2,018 | 1.52x | $2,931 | 5.2 | 1.16x | $495 |
| **i** | `e7` (2025     2024-12-06..2025-08-29) | 125..735 -> e7 | v2 | 307 | 0.628 | **$1,381** | $1,482 | $2,201 | 1.61x | $3,239 | 6.1 | 1.28x | $591 |
| **i** | `e7` (2025     2024-12-06..2025-08-29) | 125..735 -> e7 | v2 no-M | 274 | 0.625 | **$1,391** | $1,492 | $2,154 | 1.56x | $3,239 | 6.0 | 1.28x | $581 |
| **i** | `e7` (2025     2024-12-06..2025-08-29) | 125..735 -> e7 | v3 full | 441 | 0.628 | **$1,321** | $1,418 | $2,139 | 1.52x | $3,239 | 6.1 | 1.22x | $571 |
| **i** | `e7` (2025     2024-12-06..2025-08-29) | 125..735 -> e7 | v3 no-M | 408 | 0.628 | **$1,446** | $1,552 | $2,225 | 1.52x | $3,239 | 6.0 | 1.34x | $571 |
| **i** | `e7` (2025     2024-12-06..2025-08-29) | 125..735 -> e7 | E/T/I only | 134 | 0.639 | **$1,320** | $1,417 | $2,114 | 1.69x | $3,239 | 6.0 | 1.22x | $608 |

## The blind sub-blocks — `blind_e4..e7`, the last 20 days of each era

The v3 report's caveat (3) asked for the `E_/T_/I_ ONLY` result to be retested on exactly these rosters.  Same fits as above, scored on the sub-block only.

| seg | sub-block | arm | n | days | AUC | top-3 $/day | top-5 $/day | lift@27.5% | oracle top-3/day |
|---|---|---|---|---|---|---|---|---|---|
| f | `blind_e4` | v2 | 351 | 20 | 0.513 | **$1,050** | $1,762 | 0.84x | $3,356 |
| f | `blind_e4` | v2 no-M | 351 | 20 | 0.523 | **$1,131** | $1,907 | 1.07x | $3,356 |
| f | `blind_e4` | v3 full | 351 | 20 | 0.530 | **$1,147** | $2,053 | 1.09x | $3,356 |
| f | `blind_e4` | v3 no-M | 351 | 20 | 0.555 | **$1,385** | $2,215 | 1.21x | $3,356 |
| f | `blind_e4` | E/T/I only | 351 | 20 | 0.570 | **$1,420** | $2,308 | 1.00x | $3,356 |
| g | `blind_e5` | v2 | 326 | 20 | 0.642 | **$1,111** | $1,732 | 1.38x | $2,214 |
| g | `blind_e5` | v2 no-M | 326 | 20 | 0.636 | **$1,151** | $1,783 | 1.49x | $2,214 |
| g | `blind_e5` | v3 full | 326 | 20 | 0.651 | **$1,127** | $1,799 | 1.40x | $2,214 |
| g | `blind_e5` | v3 no-M | 326 | 20 | 0.645 | **$1,154** | $1,828 | 1.45x | $2,214 |
| g | `blind_e5` | E/T/I only | 326 | 20 | 0.645 | **$1,230** | $1,896 | 1.71x | $2,214 |
| h | `blind_e6` | v2 | 270 | 20 | 0.660 | **$1,442** | $2,284 | 1.54x | $2,605 |
| h | `blind_e6` | v2 no-M | 270 | 20 | 0.670 | **$1,333** | $2,395 | 1.70x | $2,605 |
| h | `blind_e6` | v3 full | 270 | 20 | 0.669 | **$1,511** | $2,284 | 1.60x | $2,605 |
| h | `blind_e6` | v3 no-M | 270 | 20 | 0.694 | **$1,650** | $2,247 | 1.65x | $2,605 |
| h | `blind_e6` | E/T/I only | 270 | 20 | 0.682 | **$1,347** | $2,194 | 1.77x | $2,605 |
| i | `blind_e7` | v2 | 298 | 20 | 0.702 | **$1,207** | $2,041 | 2.08x | $2,205 |
| i | `blind_e7` | v2 no-M | 298 | 20 | 0.697 | **$971** | $1,656 | 1.87x | $2,205 |
| i | `blind_e7` | v3 full | 298 | 20 | 0.709 | **$1,239** | $2,068 | 1.95x | $2,205 |
| i | `blind_e7` | v3 no-M | 298 | 20 | 0.747 | **$1,398** | $1,944 | 2.42x | $2,205 |
| i | `blind_e7` | E/T/I only | 298 | 20 | 0.729 | **$1,149** | $1,776 | 2.07x | $2,205 |

## D-043's $1,500/day floor — does ANY arm clear it?

`top-3` / `top-5` sum the exit-free certified value of k picks a day, averaged over EVERY day in the block.  The ONE-POSITION column is the deployable D-019 shape — the earliest of the day's three picks, entered and held to the close, one contract.  The floor is the user's stated minimum for a deployable era.

| test era | best arm @ top-3 | top-3 $/day | clears $1,500? | best arm @ top-5 | top-5 $/day | clears $1,500? | best one-position close $/day | oracle top-3/day |
|---|---|---|---|---|---|---|---|---|
| `e4` (2023 Q4  2023-10-16..12-26) | E/T/I only | **$1,391** | no | E/T/I only | **$2,134** | YES | $22 (E/T/I only) | $2,841 |
| `e5` (2024 H1  2023-12-27..2024-06-27) | E/T/I only | **$1,220** | no | E/T/I only | **$2,015** | YES | $11 (E/T/I only) | $2,614 |
| `e6` (2024 H2  2024-06-28..12-05) | v2 no-M | **$1,362** | no | v2 no-M | **$2,195** | YES | $64 (v2 no-M) | $2,931 |
| `e7` (2025     2024-12-06..2025-08-29) | v3 no-M | **$1,446** | no | v3 no-M | **$2,225** | YES | $38 (v3 no-M) | $3,239 |

## Does `E/T/I only` hold its out-of-era AUC lead?

| test era | `E/T/I only` AUC | best OTHER arm | its AUC | delta | `E/T/I only` top-3 $/day | best other top-3 $/day |
|---|---|---|---|---|---|---|
| `blind_e3` (control) | 0.665 | v3 no-M | 0.664 | +0.001 | $1,068 | $1,598 (v3 full) |
| `e4` (2023 Q4  2023-10-16..12-26) | 0.618 | v3 no-M | 0.604 | +0.014 | $1,391 | $1,269 (v3 no-M) |
| `e5` (2024 H1  2023-12-27..2024-06-27) | 0.639 | v3 full | 0.635 | +0.004 | $1,220 | $1,153 (v2 no-M) |
| `e6` (2024 H2  2024-06-28..12-05) | 0.648 | v3 no-M | 0.630 | +0.018 | $1,231 | $1,362 (v2 no-M) |
| `e7` (2025     2024-12-06..2025-08-29) | 0.639 | v3 full | 0.628 | +0.011 | $1,320 | $1,446 (v3 no-M) |

## Control — label shuffle on segment i

Training labels permuted (5 draws), everything else identical.

| arm | shuffled AUC | shuffled top-3 $/day | real AUC | real top-3 $/day |
|---|---|---|---|---|
| v2 | 0.508 +/- 0.029 | $1,091 +/- $92 | 0.628 | $1,381 |
| v2 no-M | 0.510 +/- 0.029 | $1,107 +/- $58 | 0.625 | $1,391 |
| v3 full | 0.504 +/- 0.026 | $1,129 +/- $111 | 0.628 | $1,321 |
| v3 no-M | 0.502 +/- 0.017 | $1,105 +/- $98 | 0.628 | $1,446 |
| E/T/I only | 0.495 +/- 0.026 | $1,045 +/- $100 | 0.639 | $1,320 |

## Controls and walls

- Sealed zone: `P.SEALED_FROM` = 918; the harness refuses any read at or above it, and the highest session touched here is 917.
- Walk-forward purity: every rung's test block is strictly LATER than every session in its training window (asserted in code).
- No config, column set, threshold or arm is chosen on a test block; usable columns come from each segment's own training window.
- Caches: `build_wf_cache.py` extended `sec2` / `sec3` / `sec4` / `qsec` / `w2cand` from 323 to 793 sessions (125..917) off the `sheets/roster_*.json` glob, and the causal `fvol` hot/cool cut table was regenerated to 917 with every pre-existing entry unchanged (it reads 20 strictly PRIOR sessions).
- `s829` (2025-04-24) is a day-complete roster session with ZERO confirmed extremes; it carries no candidate rows, so the ladder's day counts are candidate-bearing days.
- Typed absence: a family with no coverage in a segment's training window is dropped by `dm.feature_columns` rather than imputed; the census table above reports per-era coverage for `M_`, `I_` and `T_`.

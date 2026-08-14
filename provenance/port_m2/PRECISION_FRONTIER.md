# THE PRECISION FRONTIER

`PORT-M2-PRECISION-FRONTIER-V1` · `engine/port_m2/precision_frontier.py`
(scores, day gate, frontier) · `engine/port_m3/m3_matrix.py` (the teacher
columns) · `engine/port_m3/m3_walk.py --drop-groups` (the D-078 control) ·
`engine/port_m2/teacher_marginal.py` (the clean diff).

Matrix: 1,399,374 candidate rows x 202 features (184 pre-teacher + 18
teacher-evidence), 3,341 asset-sessions, SI/HG/NKD, holdout excluded by the
guarded enumerator.  Every model is walk-forward: model_k is fitted only on
eras strictly before era k and scored on era k.  Reported eras E3, E4, E5, E6
and E8 (the GATE-2025H1 echo); E2 and E7 are fitted so that every reported era
has a previous era's score distribution to calibrate a causal threshold from.

Intervals are CR1 sandwich intervals CLUSTERED BY CALENDAR DAY (D-036/D-073).
`takes/wk`, `$/week` and `$/day` are PORTFOLIO totals across SI+HG+NKD;
`$/session` is the D-048 denominator (realised dollars over EVERY asset-session
of the era, traded or not).

## HEADLINE

**The precision-vs-confidence frontier exists, it is small, and it runs out
before it reaches the throughput the account needs.**

1. **The teacher features change nothing, and the census says exactly why.**
   The D-078 injection is done: 18 columns, `design/TEACHER_FEATURES_V1.md` §2
   PROVEN + §3 SUPPORTED, in the matrix as the `teacher_evidence` group. The
   clean diff — one harness, one matrix, `--drop-groups teacher_evidence` —
   moves $/session by **−$54 / −$51 / −$37 / +$26 / −$43 / −$3** across
   E3–E8 (mean **−$27**, negative in 6 of 8 eras). The control run reproduces
   the committed pre-teacher curve **exactly on 8 of 8 eras**, so this is a
   measurement, not a drift.
   *The mechanism, measured two ways.* The teacher's CAPACITY reading is
   **real and it replicates**: on 1.4M candidates across all eight eras
   `SEAT_LIVE` runs 1.31–1.69× (8/8), `SEAT_DEAD_TIME` 0.05–0.26× (0/8 above
   1), `capacity_big` 1.19–1.81× (8/8), `NAMED_TRIAD` 1.06–1.59× (8/8) — the
   round's headline cues are not E6 artefacts. But those same columns are
   **96–99.9 % reconstructible from the pre-teacher feature block** (median
   R² 0.973): the model already had that information under other names. The
   columns that ARE new — the level ledger's `min_tc_near` (R² −0.36),
   `n_near100` (0.57), `near_d` (0.63) — are the ones the era ladder finds
   **dead**: `LEVEL_VIRGIN` 3/8 eras above 1, `LEVEL_NEAR` 1/8. So the
   teacher round's distilled evidence is either **real and already known**, or
   **new and worthless**. That is the D-078 answer.

2. **The confidence ordering is real to about the top 2 %, then it inverts.**
   Realised winner rate climbs from the era base (0.049–0.065) to
   **0.087–0.171** at the 0.5–2 % tiers — a genuine 1.5–2.5× — and then
   *collapses*: the top 0.1 % of scores returns **0 winners in 152 / 153 /
   163 / 172 candidates** in E3 / E5 / E6 / E8. The most confident tier is not
   the most precise; it is the least. The head is also **2× overconfident in
   its tail** (predicted 0.10–0.28 vs realised 0.09–0.13) while being
   near-perfect in aggregate (predicted 0.057–0.069 vs realised 0.046–0.065).

3. **Precision never gets near what the payoffs need.** The best precision
   found anywhere on the whole (threshold × day-abstention × agreement) plane
   that survives in *every* era is **0.111** — versus a 0.060 base and the
   **0.73** the $1,000/trade bar requires at these payoffs. The teacher's
   measured 40 % is not reached by any model at any confidence level.

4. **THE THROUGHPUT ANSWER, plainly.** At the user's floor of **3–4 portfolio
   takes per week**, the honest reading — pick the operating point on the
   eras BEFORE the one you are trading, then trade it — is
   **−$399 / −$1,819 / −$1,170 / +$23 per week** on E4 / E5 / E6 / E8.
   Three of four negative; mean −$841/week. The per-era argmax table (§6)
   shows $1,750–$2,442 per week, but its winner is a *different* operating
   point in every single era (`1of3_any|top_1%`, `2of3|top_10%`,
   `alone_SEQ|top_10%`, `2of3|top_5%`), which is what selection over 286
   points on 26 weeks of data looks like.

5. **The one thing positive in all five eras is 10× below the floor.**
   `pre-day forecaster gate ≥ q80` + the model's top 1 % of candidates is
   positive in **5/5** eras — $135 / $220 / $228 / $180 / $183 per week,
   precision 0.18, **$512/trade**, $715 per traded day — on **0.38 takes per
   week** (7–13 trades per era; one trade every 2.6 weeks). Loosen it to reach
   the floor (top 5 %, 1.34 takes/week) and $/trade falls to $127 and
   precision to 0.118; open it fully and it is −$48/trade. **Precision and
   throughput trade against each other and they cross far below 3/week.**

6. **The shuffled control is flat, so §2–§5 are measuring the score.**
   A permuted FULL_TF score gives precision **0.049–0.063 at every tier**
   (base 0.060) and −$34…−$80 per trade everywhere. Nothing about the
   selection arithmetic manufactures a frontier.

**What this leaves.** At the original full-value entries, with the trade shape
held fixed, the answer to "what precision and $/day does the top tier actually
deliver, and at what throughput" is: **~11 % precision, ~$30–120 per trade,
~$100–450 per week at 3–7 takes/week — 1–2 % of the D-048 bar — and the
walk-forward-honest version of that number is negative.** The frontier is real
but it is a $500/week frontier, not a $30,000/week one. The one live seam is
the PRE-DAY gate: the only lever in this study that is positive in every era,
and the only one whose weakness is throughput rather than edge.



---

## 1. THE TEACHER-FEATURE INJECTION (D-078) — THE CLEAN DIFF

| era | policy | $/session NO teacher | $/session WITH | Δ $/session | $/trade NO | $/trade WITH | Δ $/trade | capture NO | capture WITH | control == committed? |
|---|---|---|---|---|---|---|---|---|---|---|
| E1 | cell/2 | $136 | $120 | $-16 | $45 | $40 | $-5 | 0.0482 | 0.0425 | YES |
| E2 | cell/1 | $341 | $507 | $167 | $114 | $167 | $53 | 0.1007 | 0.1499 | YES |
| E3 | cell/2 | $441 | $387 | $-54 | $146 | $129 | $-18 | 0.1461 | 0.1281 | YES |
| E4 | cell/1 | $278 | $227 | $-51 | $93 | $76 | $-17 | 0.1008 | 0.0824 | YES |
| E5 | cell/1 | $326 | $289 | $-37 | $109 | $96 | $-12 | 0.1257 | 0.1116 | YES |
| E6 | cell/1 | $297 | $323 | $26 | $99 | $108 | $9 | 0.0877 | 0.0955 | YES |
| E7 | cell/1 | $370 | $327 | $-43 | $123 | $109 | $-14 | 0.0901 | 0.0797 | YES |
| E8 | cell/1 | $344 | $341 | $-3 | $115 | $114 | $-1 | 0.0801 | 0.0794 | YES |

**Where the teacher columns land in the model's own gain ranking** (top-20 only; a group absent from an era's top-20 is absent from this table):

| era | teacher columns in the top-20 | their summed gain share |
|---|---|---|
| E1 | tf_phase_open_frac (#8), tf_phase_open_reset (#17) | 0.0250 |
| E2 | tf_phase_open_frac (#6), tf_range_phase_usd (#7) | 0.0407 |
| E3 | tf_range_phase_usd (#6), tf_phase_open_frac (#11), tf_seat_dead_time (#15) | 0.0510 |
| E4 | tf_phase_open_frac (#6), tf_phase_open_reset (#9), tf_range_phase_usd (#10), tf_seat_dead_time (#13) | 0.0471 |
| E5 | tf_phase_open_frac (#8), tf_seat_live (#17) | 0.0233 |
| E6 | tf_range_phase_usd (#7), tf_phase_open_frac (#8), tf_seat_dead_time (#10), tf_cov_phase_pct (#12) | 0.0726 |
| E7 | tf_phase_open_frac (#9) | 0.0192 |
| E8 | tf_range_phase_usd (#4), tf_phase_open_frac (#8), tf_cov_phase_pct (#10), tf_seat_dead_time (#14) | 0.1257 |


---

## 1b. THE TEACHER'S CUES, RE-MEASURED ON THE WHOLE ERA LADDER

`TEACHER_FEATURES_V1` §7 is explicit that its numbers are six days of one era and that the harness must re-derive every threshold in its own folds before any cue is allowed to carry weight.  This is that re-measurement: 1.4M candidates, eight eras, the same D-021 target, day-clustered intervals (`TEACHER_CUE_ERA_LADDER.tsv`).

| cue | round 1/2 verdict | E1 | E2 | E3 | E4 | E5 | E6 | E7 | E8 | eras above 1x |
|---|---|---|---|---|---|---|---|---|---|---|
| SEAT_LIVE | PROVEN r1 2.62x / DECAYED r2 | 1.54 | 1.36 | 1.36 | 1.50 | 1.69 | 1.55 | 1.40 | 1.31 | 8/8 |
| SEAT_DEAD_TIME | PROVEN r1 0.04x / WEAKENED | 0.13 | 0.06 | 0.08 | 0.05 | 0.08 | 0.13 | 0.21 | 0.26 | 0/8 |
| PHASE_SPENT | PROVEN r1 0.54x / HOLDS_WEAK | 0.79 | 0.87 | 1.00 | 0.80 | 0.78 | 0.95 | 0.90 | 0.89 | 1/8 |
| COV_SWEET_20_60 | PROVEN r1 2.00x / BROKEN | 1.21 | 1.40 | 0.97 | 1.18 | 1.14 | 1.06 | 1.20 | 1.11 | 7/8 |
| capacity_room | PROVEN r1 1.70x | 1.26 | 1.42 | 1.06 | 1.26 | 1.36 | 1.16 | 1.13 | 1.10 | 8/8 |
| capacity_big | PROVEN r1 2.23x / BROKEN r2 | 1.68 | 1.30 | 1.39 | 1.65 | 1.81 | 1.55 | 1.35 | 1.19 | 8/8 |
| LEVEL_VIRGIN | SUPPORTED r1 1.67x / UNSTABLE | 1.14 | 1.04 | 0.81 | 0.99 | 0.94 | 0.97 | 0.99 | 1.03 | 3/8 |
| LEVEL_NEAR | leg, 0.97x alone in r1 | 0.99 | 1.01 | 1.00 | 0.99 | 0.98 | 0.99 | 1.00 | 1.00 | 1/8 |
| PHASE_OPEN_RESET | UNSTABLE r1 1.65x | 1.66 | 1.56 | 1.17 | 1.30 | 1.59 | 1.23 | 1.18 | 1.20 | 8/8 |
| NAMED_TRIAD | SUPPORTED r1 1.77x pooled | 1.59 | 1.49 | 1.06 | 1.13 | 1.34 | 1.12 | 1.07 | 1.24 | 8/8 |
| NAMED_TRIAD_soft | PROVEN r1 1.64x | 1.19 | 1.33 | 1.07 | 1.22 | 1.29 | 1.08 | 1.08 | 1.05 | 8/8 |

## 1c. WAS ANY OF IT NEW INFORMATION?

Out-of-sample R^2 of a model that predicts each TEACHER column from the 184 PRE-TEACHER columns alone.  R^2 near 1 means the column is a re-expression of what the matrix already had (`TEACHER_REDUNDANCY.tsv`).

| teacher column | R^2 from the pre-teacher block | reading |
|---|---|---|
| tf_unspent_phase_usd | 0.9914 | already in the matrix |
| tf_range_phase_usd | 0.9889 | already in the matrix |
| tf_cov_phase_pct | 0.9990 | already in the matrix |
| tf_seat_live | 0.9688 | already in the matrix |
| tf_seat_dead_time | 0.9941 | already in the matrix |
| tf_phase_spent | 0.9972 | already in the matrix |
| tf_cov_sweet_20_60 | 0.9921 | already in the matrix |
| tf_capacity_room | 0.9775 | already in the matrix |
| tf_capacity_big | 0.9580 | already in the matrix |
| tf_near_d_usd | 0.6339 | GENUINELY NEW |
| tf_n_near100 | 0.5705 | GENUINELY NEW |
| tf_min_tc_near | -0.3636 | GENUINELY NEW |
| tf_level_virgin | 0.5016 | GENUINELY NEW |
| tf_level_near | 0.5324 | GENUINELY NEW |
| tf_phase_open_frac | 0.9999 | already in the matrix |
| tf_phase_open_reset | 0.9908 | already in the matrix |
| tf_named_triad | 0.9110 | already in the matrix |
| tf_named_triad_soft | 0.9127 | already in the matrix |

## 1d. THE RAW-EVENT-STREAM CUES ON THE SAME LADDER

`reload_with_side` was the ONE cue in this programme derived from the raw event sequence that survived a census (1.19x on n=1,122, E6R2).  On 1.4M candidates across eight eras it does not replicate.

| cue | E1 | E2 | E3 | E4 | E5 | E6 | E7 | E8 | eras above 1x |
|---|---|---|---|---|---|---|---|---|---|
| reload_with_side>=2 | 1.05 | 1.02 | 1.00 | 0.99 | 1.06 | 1.02 | 1.01 | 1.01 | 6/8 |
| reload_with_side>=1 | 1.03 | 1.01 | 0.98 | 0.97 | 1.04 | 1.00 | 0.99 | 1.01 | 4/8 |
| reload_against<=-1 | 0.98 | 1.00 | 1.04 | 1.04 | 0.98 | 1.02 | 1.02 | 1.00 | 6/8 |
| pull_with_side>=0.25 | 0.73 | 0.77 | 0.65 | 0.65 | 0.73 | 0.71 | 0.72 | 0.83 | 0/8 |
| l1_thin_ahead<=-2 | 1.03 | 1.01 | 1.03 | 1.01 | 0.99 | 0.98 | 0.98 | 0.98 | 4/8 |
| stack_thin_ahead<=-1 | 0.96 | 0.99 | 0.96 | 0.86 | 0.90 | 0.99 | 0.85 | 0.92 | 0/8 |
| trade_frac<=0.05 | 0.99 | 1.00 | 0.95 | 0.99 | 1.07 | 1.10 | 1.03 | 0.92 | 4/8 |
| med_gap<=20ms | 1.01 | 1.00 | 1.02 | 1.03 | 1.02 | 1.00 | 1.00 | 1.01 | 7/8 |


---

## 2. THE THRESHOLD FRONTIER

### 2.1 candidate grain — the best model (FULL_TF)

**E3**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02% | 2 | 0.1 | 0.000 [0.000, 0.000] | 451 [-2328, 3231] | 7 | 451 | 33 | 0 | 0.00 | 2 |
| top_0.05% | 8 | 0.3 | 0.000 [0.000, 0.000] | -127 [-445, 191] | -8 | -145 | -38 | -338 | 0.19 | -3 |
| top_0.1% | 17 | 0.6 | 0.000 [0.000, 0.000] | -165 [-437, 107] | -22 | -216 | -104 | -660 | 0.19 | -7 |
| top_0.2% | 26 | 1.0 | 0.077 [-0.014, 0.168] | 22 [-365, 409] | 4 | 30 | 21 | -1117 | 0.30 | 1 |
| top_0.5% | 42 | 1.6 | 0.119 [0.032, 0.206] | 300 [-13, 614] | 97 | 420 | 467 | -542 | 0.26 | 32 |
| top_1% | 79 | 2.9 | 0.101 [0.032, 0.171] | 144 [-68, 356] | 88 | 219 | 423 | -1182 | 0.33 | 29 |
| top_2% | 149 | 5.5 | 0.067 [0.019, 0.115] | 11 [-161, 183] | 13 | 21 | 62 | -2394 | 0.56 | 4 |
| top_5% | 295 | 10.9 | 0.078 [0.050, 0.106] | -45 [-167, 78] | -101 | -118 | -487 | -4746 | 0.52 | -34 |
| top_10% | 489 | 18.1 | 0.059 [0.037, 0.082] | -115 [-205, -25] | -433 | -437 | -2087 | -7480 | 0.78 | -144 |
| top_20% | 729 | 27.0 | 0.066 [0.049, 0.083] | -66 [-137, 5] | -370 | -370 | -1784 | -8639 | 0.63 | -123 |
| top_100% | 1691 | 62.6 | 0.054 [0.043, 0.066] | -74 [-114, -33] | -957 | -957 | -4606 | -10866 | 0.81 | -319 |

**E4**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02% | 2 | 0.1 | 0.000 [0.000, 0.000] | -642 [-4613, 3328] | -10 | -642 | -49 | 0 | 0.08 | -3 |
| top_0.05% | 8 | 0.3 | 0.125 [-0.216, 0.466] | -160 [-838, 519] | -10 | -213 | -49 | -376 | 0.15 | -3 |
| top_0.1% | 12 | 0.5 | 0.083 [-0.106, 0.272] | -431 [-963, 101] | -40 | -647 | -199 | -942 | 0.23 | -13 |
| top_0.2% | 24 | 0.9 | 0.083 [-0.040, 0.207] | -444 [-789, -99] | -83 | -665 | -409 | -1794 | 0.38 | -28 |
| top_0.5% | 42 | 1.6 | 0.071 [-0.010, 0.153] | -206 [-499, 86] | -67 | -299 | -333 | -2112 | 0.50 | -22 |
| top_1% | 59 | 2.3 | 0.152 [0.065, 0.240] | 41 [-187, 270] | 19 | 66 | 94 | -1395 | 0.46 | 6 |
| top_2% | 98 | 3.8 | 0.102 [0.045, 0.159] | 58 [-175, 290] | 44 | 97 | 217 | -1840 | 0.54 | 15 |
| top_5% | 180 | 6.9 | 0.117 [0.067, 0.166] | 129 [-53, 310] | 179 | 260 | 890 | -2379 | 0.50 | 60 |
| top_10% | 287 | 11.0 | 0.094 [0.059, 0.129] | 41 [-96, 178] | 91 | 108 | 453 | -4548 | 0.46 | 31 |
| top_20% | 465 | 17.9 | 0.082 [0.057, 0.106] | -71 [-166, 23] | -257 | -267 | -1275 | -7540 | 0.58 | -86 |
| top_100% | 1550 | 59.6 | 0.054 [0.043, 0.065] | -31 [-73, 11] | -372 | -372 | -1845 | -9412 | 0.62 | -125 |

**E5**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02% | 3 | 0.1 | 0.000 [0.000, 0.000] | -659 [-1824, 506] | -15 | -659 | -76 | -59 | 0.12 | -5 |
| top_0.05% | 6 | 0.2 | 0.000 [0.000, 0.000] | -505 [-1395, 385] | -23 | -606 | -117 | -524 | 0.15 | -8 |
| top_0.1% | 7 | 0.3 | 0.000 [0.000, 0.000] | -242 [-1160, 675] | -13 | -340 | -65 | -59 | 0.12 | -4 |
| top_0.2% | 14 | 0.5 | 0.000 [0.000, 0.000] | -61 [-562, 439] | -7 | -71 | -33 | -542 | 0.19 | -2 |
| top_0.5% | 33 | 1.3 | 0.091 [-0.012, 0.194] | 142 [-333, 616] | 36 | 195 | 180 | -1354 | 0.23 | 12 |
| top_1% | 55 | 2.1 | 0.091 [0.016, 0.166] | -22 [-335, 290] | -10 | -31 | -48 | -2052 | 0.50 | -3 |
| top_2% | 80 | 3.1 | 0.113 [0.041, 0.184] | -55 [-299, 189] | -34 | -83 | -170 | -2531 | 0.50 | -11 |
| top_5% | 134 | 5.2 | 0.119 [0.066, 0.173] | -36 [-219, 146] | -38 | -64 | -187 | -3255 | 0.50 | -13 |
| top_10% | 240 | 9.2 | 0.083 [0.049, 0.117] | -131 [-275, 13] | -244 | -294 | -1212 | -5182 | 0.65 | -81 |
| top_20% | 431 | 16.6 | 0.090 [0.061, 0.120] | -60 [-168, 48] | -201 | -203 | -997 | -6004 | 0.62 | -67 |
| top_100% | 1517 | 58.3 | 0.056 [0.044, 0.068] | -23 [-63, 17] | -267 | -267 | -1326 | -8251 | 0.54 | -89 |

**E6**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02% | 1 | 0.0 | 0.000 [., .] | 695 [., .] | 5 | 695 | 27 | 0 | 0.00 | 2 |
| top_0.05% | 5 | 0.2 | 0.000 [0.000, 0.000] | -325 [-3087, 2437] | -13 | -542 | -62 | 0 | 0.08 | -4 |
| top_0.1% | 8 | 0.3 | 0.125 [-0.183, 0.433] | -263 [-1285, 760] | -16 | -701 | -81 | 0 | 0.08 | -5 |
| top_0.2% | 11 | 0.4 | 0.182 [0.019, 0.345] | -37 [-1286, 1213] | -3 | -135 | -16 | 0 | 0.08 | -1 |
| top_0.5% | 23 | 0.9 | 0.000 [0.000, 0.000] | 21 [-575, 618] | 4 | 55 | 19 | -930 | 0.12 | 1 |
| top_1% | 46 | 1.8 | 0.043 [-0.026, 0.113] | -320 [-585, -55] | -115 | -818 | -566 | -1827 | 0.35 | -38 |
| top_2% | 71 | 2.7 | 0.113 [0.034, 0.191] | 49 [-295, 394] | 27 | 103 | 135 | -1860 | 0.38 | 9 |
| top_5% | 196 | 7.5 | 0.076 [0.040, 0.113] | -40 [-237, 156] | -61 | -116 | -303 | -3276 | 0.54 | -20 |
| top_10% | 353 | 13.6 | 0.082 [0.051, 0.113] | -73 [-223, 76] | -202 | -249 | -996 | -10740 | 0.46 | -67 |
| top_20% | 662 | 25.5 | 0.088 [0.064, 0.111] | -59 [-162, 44] | -304 | -309 | -1499 | -11030 | 0.58 | -101 |
| top_100% | 1717 | 66.0 | 0.070 [0.057, 0.083] | -8 [-63, 47] | -107 | -107 | -525 | -12908 | 0.46 | -36 |

**E8_GATE_2025H1**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02% | 2 | 0.1 | 0.000 [., .] | -336 [., .] | -5 | -672 | -25 | 0 | 0.04 | -2 |
| top_0.05% | 5 | 0.2 | 0.000 [0.000, 0.000] | -332 [-1457, 792] | -13 | -554 | -62 | 0 | 0.07 | -4 |
| top_0.1% | 5 | 0.2 | 0.000 [0.000, 0.000] | -132 [-991, 726] | -5 | -166 | -25 | 0 | 0.07 | -2 |
| top_0.2% | 12 | 0.4 | 0.000 [0.000, 0.000] | -379 [-906, 148] | -36 | -650 | -168 | -734 | 0.19 | -12 |
| top_0.5% | 30 | 1.1 | 0.100 [-0.005, 0.205] | 241 [-462, 944] | 57 | 402 | 268 | -930 | 0.30 | 19 |
| top_1% | 50 | 1.9 | 0.100 [0.018, 0.182] | 292 [-205, 790] | 115 | 457 | 542 | -1548 | 0.30 | 38 |
| top_2% | 92 | 3.4 | 0.098 [0.032, 0.164] | 87 [-301, 475] | 63 | 170 | 296 | -2626 | 0.48 | 21 |
| top_5% | 170 | 6.3 | 0.082 [0.046, 0.118] | 143 [-164, 450] | 192 | 380 | 902 | -2785 | 0.41 | 64 |
| top_10% | 317 | 11.7 | 0.091 [0.059, 0.123] | -41 [-212, 129] | -104 | -141 | -487 | -4048 | 0.63 | -35 |
| top_20% | 591 | 21.9 | 0.102 [0.079, 0.124] | -38 [-144, 68] | -175 | -195 | -825 | -5401 | 0.56 | -58 |
| top_100% | 2030 | 75.2 | 0.067 [0.055, 0.078] | -60 [-106, -14] | -964 | -964 | -4533 | -16458 | 0.67 | -321 |

### 2.2 episode grain — the best model (FULL_TF)

**E3**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02% | 4 | 0.1 | 0.000 [0.000, 0.000] | 98 [-723, 919] | 3 | 98 | 15 | 0 | 0.07 | 1 |
| top_0.05% | 13 | 0.5 | 0.000 [0.000, 0.000] | -57 [-398, 284] | -6 | -74 | -27 | -342 | 0.19 | -2 |
| top_0.1% | 21 | 0.8 | 0.048 [-0.054, 0.149] | -50 [-395, 295] | -8 | -59 | -39 | -1117 | 0.26 | -3 |
| top_0.2% | 37 | 1.4 | 0.054 [-0.026, 0.134] | 87 [-206, 379] | 25 | 119 | 119 | -542 | 0.22 | 8 |
| top_0.5% | 67 | 2.5 | 0.090 [0.021, 0.158] | 148 [-84, 379] | 76 | 220 | 367 | -1238 | 0.33 | 25 |
| top_1% | 126 | 4.7 | 0.079 [0.034, 0.125] | 62 [-113, 237] | 61 | 111 | 291 | -1844 | 0.37 | 20 |
| top_2% | 192 | 7.1 | 0.078 [0.043, 0.114] | -10 [-177, 157] | -15 | -22 | -74 | -3485 | 0.52 | -5 |
| top_5% | 361 | 13.4 | 0.075 [0.048, 0.101] | -62 [-172, 48] | -173 | -186 | -833 | -4074 | 0.67 | -58 |
| top_10% | 569 | 21.1 | 0.063 [0.042, 0.084] | -104 [-193, -14] | -454 | -458 | -2187 | -8580 | 0.78 | -151 |
| top_20% | 840 | 31.1 | 0.061 [0.044, 0.077] | -97 [-170, -25] | -629 | -629 | -3027 | -10194 | 0.67 | -210 |
| top_100% | 1664 | 61.6 | 0.057 [0.045, 0.069] | -52 [-94, -10] | -666 | -666 | -3207 | -10030 | 0.70 | -222 |

**E4**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02% | 2 | 0.1 | 0.000 [0.000, 0.000] | -580 [-5345, 4185] | -9 | -580 | -45 | 0 | 0.08 | -3 |
| top_0.05% | 6 | 0.2 | 0.167 [-0.321, 0.654] | 239 [-763, 1241] | 11 | 286 | 55 | 0 | 0.08 | 4 |
| top_0.1% | 18 | 0.7 | 0.111 [-0.053, 0.276] | -188 [-683, 307] | -26 | -260 | -130 | -1026 | 0.23 | -9 |
| top_0.2% | 24 | 0.9 | 0.125 [-0.024, 0.274] | -117 [-480, 246] | -22 | -165 | -108 | -1014 | 0.35 | -7 |
| top_0.5% | 48 | 1.8 | 0.083 [0.001, 0.166] | 30 [-270, 329] | 11 | 43 | 55 | -1058 | 0.50 | 4 |
| top_1% | 76 | 2.9 | 0.079 [0.016, 0.142] | 114 [-133, 361] | 67 | 177 | 333 | -1255 | 0.54 | 23 |
| top_2% | 134 | 5.2 | 0.104 [0.054, 0.155] | 118 [-70, 306] | 122 | 202 | 607 | -2030 | 0.46 | 41 |
| top_5% | 250 | 9.6 | 0.096 [0.058, 0.134] | 98 [-45, 241] | 190 | 231 | 941 | -4027 | 0.46 | 64 |
| top_10% | 375 | 14.4 | 0.083 [0.053, 0.113] | -90 [-191, 11] | -261 | -288 | -1295 | -6497 | 0.69 | -87 |
| top_20% | 564 | 21.7 | 0.082 [0.059, 0.104] | -27 [-105, 51] | -117 | -117 | -579 | -6441 | 0.58 | -39 |
| top_100% | 1541 | 59.3 | 0.054 [0.042, 0.067] | -35 [-79, 9] | -423 | -423 | -2099 | -12376 | 0.58 | -142 |

**E5**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02% | 6 | 0.2 | 0.000 [0.000, 0.000] | -170 [-1382, 1043] | -8 | -204 | -39 | -59 | 0.12 | -3 |
| top_0.05% | 8 | 0.3 | 0.000 [0.000, 0.000] | 25 [-854, 903] | 2 | 28 | 8 | -59 | 0.12 | 1 |
| top_0.1% | 14 | 0.5 | 0.000 [0.000, 0.000] | -146 [-691, 399] | -16 | -157 | -79 | -1395 | 0.19 | -5 |
| top_0.2% | 27 | 1.0 | 0.111 [-0.009, 0.231] | 509 [-2, 1021] | 107 | 598 | 529 | -130 | 0.12 | 36 |
| top_0.5% | 47 | 1.8 | 0.106 [0.013, 0.200] | 312 [-138, 763] | 114 | 396 | 564 | -1280 | 0.23 | 38 |
| top_1% | 84 | 3.2 | 0.107 [0.039, 0.176] | -52 [-305, 201] | -34 | -81 | -168 | -2705 | 0.38 | -11 |
| top_2% | 134 | 5.2 | 0.104 [0.053, 0.156] | 14 [-163, 191] | 15 | 25 | 73 | -2220 | 0.50 | 5 |
| top_5% | 253 | 9.7 | 0.083 [0.050, 0.116] | -127 [-266, 12] | -249 | -292 | -1237 | -6304 | 0.54 | -83 |
| top_10% | 412 | 15.8 | 0.104 [0.072, 0.137] | -15 [-124, 94] | -48 | -48 | -237 | -6474 | 0.58 | -16 |
| top_20% | 676 | 26.0 | 0.101 [0.077, 0.124] | -15 [-92, 61] | -81 | -81 | -400 | -8636 | 0.54 | -27 |
| top_100% | 1496 | 57.5 | 0.059 [0.047, 0.072] | -7 [-46, 33] | -77 | -77 | -383 | -8749 | 0.54 | -26 |

**E6**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02% | 1 | 0.0 | 0.000 [., .] | 695 [., .] | 5 | 695 | 27 | 0 | 0.00 | 2 |
| top_0.05% | 7 | 0.3 | 0.000 [0.000, 0.000] | -381 [-2230, 1468] | -21 | -889 | -103 | 0 | 0.08 | -7 |
| top_0.1% | 8 | 0.3 | 0.125 [-0.183, 0.433] | 325 [-1461, 2112] | 20 | 868 | 100 | 0 | 0.04 | 7 |
| top_0.2% | 15 | 0.6 | 0.133 [0.045, 0.222] | 447 [-69, 963] | 52 | 1118 | 258 | 0 | 0.04 | 17 |
| top_0.5% | 35 | 1.3 | 0.086 [-0.004, 0.175] | -181 [-575, 212] | -50 | -423 | -244 | -1204 | 0.19 | -17 |
| top_1% | 62 | 2.4 | 0.081 [0.015, 0.146] | 139 [-211, 489] | 67 | 279 | 332 | -774 | 0.23 | 22 |
| top_2% | 155 | 6.0 | 0.058 [0.022, 0.094] | -93 [-298, 112] | -112 | -257 | -553 | -3290 | 0.42 | -37 |
| top_5% | 329 | 12.7 | 0.064 [0.036, 0.091] | -46 [-185, 93] | -118 | -146 | -583 | -5666 | 0.54 | -39 |
| top_10% | 550 | 21.2 | 0.098 [0.074, 0.122] | -15 [-116, 87] | -63 | -66 | -310 | -4436 | 0.54 | -21 |
| top_20% | 869 | 33.4 | 0.097 [0.076, 0.117] | -26 [-107, 56] | -174 | -174 | -859 | -7749 | 0.54 | -58 |
| top_100% | 1704 | 65.5 | 0.074 [0.061, 0.087] | -3 [-48, 43] | -35 | -35 | -173 | -7816 | 0.54 | -12 |

**E8_GATE_2025H1**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02% | 4 | 0.1 | 0.000 [0.000, 0.000] | -189 [-1804, 1425] | -6 | -252 | -28 | 0 | 0.04 | -2 |
| top_0.05% | 5 | 0.2 | 0.000 [0.000, 0.000] | -30 [-1162, 1102] | -1 | -38 | -6 | 0 | 0.04 | -0 |
| top_0.1% | 8 | 0.3 | 0.125 [-0.167, 0.417] | 331 [-475, 1137] | 21 | 441 | 98 | 0 | 0.07 | 7 |
| top_0.2% | 24 | 0.9 | 0.042 [-0.048, 0.131] | -247 [-764, 271] | -47 | -493 | -219 | -824 | 0.22 | -16 |
| top_0.5% | 53 | 2.0 | 0.075 [0.002, 0.149] | 84 [-345, 513] | 35 | 135 | 165 | -1870 | 0.41 | 12 |
| top_1% | 93 | 3.4 | 0.086 [0.030, 0.142] | -42 [-431, 346] | -31 | -87 | -146 | -3038 | 0.44 | -10 |
| top_2% | 142 | 5.3 | 0.099 [0.049, 0.149] | 28 [-300, 357] | 32 | 68 | 149 | -3869 | 0.59 | 11 |
| top_5% | 289 | 10.7 | 0.086 [0.051, 0.122] | -87 [-278, 104] | -198 | -283 | -932 | -5751 | 0.59 | -66 |
| top_10% | 492 | 18.2 | 0.104 [0.074, 0.133] | -94 [-236, 49] | -363 | -426 | -1706 | -10276 | 0.59 | -121 |
| top_20% | 833 | 30.9 | 0.097 [0.079, 0.116] | -48 [-142, 45] | -316 | -316 | -1485 | -11366 | 0.48 | -105 |
| top_100% | 2005 | 74.3 | 0.071 [0.059, 0.083] | -53 [-101, -6] | -841 | -841 | -3958 | -20601 | 0.63 | -280 |

### 2.3 the SHUFFLED-SCORE control (candidate grain)

A permuted score must produce a FLAT frontier.  If precision and $/trade rise with the tier here, the frontier above is an artefact of the selection arithmetic and not of the score.

**E3 (shuffled)**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02% | 30 | 1.1 | 0.067 [-0.029, 0.163] | 11 [-279, 300] | 2 | 12 | 12 | -910 | 0.37 | 1 |
| top_0.05% | 72 | 2.7 | 0.056 [0.000, 0.111] | -0 [-201, 201] | -0 | -0 | -0 | -1412 | 0.48 | -0 |
| top_0.1% | 142 | 5.3 | 0.049 [0.008, 0.091] | -50 [-187, 88] | -54 | -78 | -261 | -2638 | 0.48 | -18 |
| top_0.2% | 265 | 9.8 | 0.057 [0.028, 0.085] | -37 [-131, 57] | -76 | -85 | -367 | -2560 | 0.63 | -25 |
| top_0.5% | 555 | 20.6 | 0.045 [0.024, 0.066] | -62 [-130, 6] | -265 | -267 | -1274 | -4197 | 0.74 | -88 |
| top_1% | 864 | 32.0 | 0.049 [0.031, 0.066] | -79 [-130, -28] | -522 | -522 | -2514 | -6098 | 0.85 | -174 |
| top_2% | 1212 | 44.9 | 0.045 [0.034, 0.057] | -91 [-132, -51] | -853 | -853 | -4105 | -11014 | 0.74 | -284 |
| top_5% | 1478 | 54.7 | 0.049 [0.038, 0.061] | -67 [-113, -22] | -765 | -765 | -3682 | -15376 | 0.70 | -255 |
| top_10% | 1585 | 58.7 | 0.055 [0.043, 0.067] | -53 [-96, -11] | -652 | -652 | -3140 | -11566 | 0.63 | -217 |
| top_20% | 1638 | 60.7 | 0.057 [0.046, 0.069] | -66 [-111, -22] | -836 | -836 | -4026 | -13085 | 0.74 | -279 |
| top_100% | 1691 | 62.6 | 0.054 [0.043, 0.066] | -74 [-114, -33] | -957 | -957 | -4606 | -10866 | 0.81 | -319 |

**E4 (shuffled)**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02% | 29 | 1.1 | 0.035 [-0.038, 0.107] | -14 [-305, 277] | -3 | -18 | -15 | -759 | 0.38 | -1 |
| top_0.05% | 73 | 2.8 | 0.041 [-0.004, 0.087] | -16 [-191, 159] | -9 | -21 | -45 | -1874 | 0.54 | -3 |
| top_0.1% | 138 | 5.3 | 0.065 [0.025, 0.105] | 74 [-52, 200] | 79 | 115 | 394 | -2176 | 0.35 | 27 |
| top_0.2% | 260 | 10.0 | 0.069 [0.039, 0.100] | 73 [-18, 163] | 147 | 163 | 728 | -2142 | 0.27 | 49 |
| top_0.5% | 532 | 20.5 | 0.060 [0.040, 0.080] | 4 [-64, 73] | 18 | 18 | 87 | -4009 | 0.54 | 6 |
| top_1% | 807 | 31.0 | 0.052 [0.037, 0.067] | -8 [-60, 43] | -52 | -52 | -260 | -4410 | 0.69 | -18 |
| top_2% | 1093 | 42.0 | 0.050 [0.038, 0.062] | -30 [-72, 11] | -258 | -258 | -1279 | -7879 | 0.54 | -86 |
| top_5% | 1388 | 53.4 | 0.048 [0.037, 0.059] | -26 [-65, 12] | -284 | -284 | -1409 | -8364 | 0.65 | -95 |
| top_10% | 1479 | 56.9 | 0.051 [0.040, 0.063] | -19 [-57, 20] | -217 | -217 | -1077 | -7434 | 0.62 | -73 |
| top_20% | 1531 | 58.9 | 0.059 [0.046, 0.071] | -25 [-64, 15] | -291 | -291 | -1445 | -9300 | 0.58 | -98 |
| top_100% | 1550 | 59.6 | 0.054 [0.043, 0.065] | -31 [-73, 11] | -372 | -372 | -1845 | -9412 | 0.62 | -125 |

**E5 (shuffled)**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02% | 31 | 1.2 | 0.032 [-0.034, 0.099] | -139 [-348, 69] | -33 | -154 | -166 | -1061 | 0.50 | -11 |
| top_0.05% | 74 | 2.8 | 0.068 [0.010, 0.125] | -111 [-246, 24] | -64 | -141 | -315 | -1512 | 0.54 | -21 |
| top_0.1% | 144 | 5.5 | 0.049 [0.014, 0.083] | -102 [-208, 3] | -114 | -167 | -565 | -2786 | 0.58 | -38 |
| top_0.2% | 265 | 10.2 | 0.034 [0.012, 0.056] | -93 [-179, -6] | -190 | -215 | -943 | -3738 | 0.58 | -63 |
| top_0.5% | 542 | 20.8 | 0.035 [0.019, 0.051] | -44 [-98, 9] | -187 | -190 | -927 | -5328 | 0.58 | -62 |
| top_1% | 840 | 32.3 | 0.042 [0.026, 0.057] | -46 [-89, -2] | -299 | -299 | -1483 | -5348 | 0.69 | -100 |
| top_2% | 1109 | 42.7 | 0.053 [0.039, 0.068] | -22 [-60, 17] | -186 | -186 | -922 | -6330 | 0.54 | -62 |
| top_5% | 1365 | 52.5 | 0.048 [0.037, 0.060] | -42 [-78, -7] | -449 | -449 | -2229 | -7184 | 0.65 | -150 |
| top_10% | 1458 | 56.1 | 0.049 [0.039, 0.058] | -34 [-73, 6] | -381 | -381 | -1890 | -8432 | 0.69 | -127 |
| top_20% | 1494 | 57.5 | 0.056 [0.044, 0.067] | -42 [-81, -3] | -488 | -488 | -2421 | -8263 | 0.58 | -163 |
| top_100% | 1517 | 58.3 | 0.056 [0.044, 0.068] | -23 [-63, 17] | -267 | -267 | -1326 | -8251 | 0.54 | -89 |

**E6 (shuffled)**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02% | 32 | 1.2 | 0.094 [-0.014, 0.202] | 220 [-170, 609] | 55 | 234 | 270 | -632 | 0.23 | 18 |
| top_0.05% | 77 | 3.0 | 0.052 [0.001, 0.103] | -18 [-241, 205] | -11 | -23 | -53 | -881 | 0.54 | -4 |
| top_0.1% | 148 | 5.7 | 0.047 [0.008, 0.086] | -50 [-210, 110] | -58 | -83 | -285 | -1984 | 0.62 | -19 |
| top_0.2% | 271 | 10.4 | 0.059 [0.029, 0.090] | -52 [-153, 48] | -111 | -126 | -546 | -3970 | 0.62 | -37 |
| top_0.5% | 559 | 21.5 | 0.063 [0.044, 0.082] | -59 [-128, 9] | -259 | -263 | -1276 | -6100 | 0.58 | -86 |
| top_1% | 866 | 33.3 | 0.053 [0.039, 0.067] | -109 [-161, -57] | -738 | -738 | -3634 | -9147 | 0.85 | -246 |
| top_2% | 1214 | 46.7 | 0.053 [0.041, 0.066] | -61 [-108, -14] | -579 | -579 | -2850 | -9554 | 0.69 | -193 |
| top_5% | 1468 | 56.5 | 0.069 [0.055, 0.083] | -33 [-84, 19] | -373 | -373 | -1839 | -9684 | 0.69 | -124 |
| top_10% | 1602 | 61.6 | 0.064 [0.050, 0.077] | -34 [-80, 12] | -427 | -427 | -2100 | -10526 | 0.62 | -142 |
| top_20% | 1670 | 64.2 | 0.065 [0.052, 0.078] | -28 [-80, 25] | -361 | -361 | -1779 | -10208 | 0.58 | -120 |
| top_100% | 1717 | 66.0 | 0.070 [0.057, 0.083] | -8 [-63, 47] | -107 | -107 | -525 | -12908 | 0.46 | -36 |

**E8_GATE_2025H1 (shuffled)**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02% | 34 | 1.3 | 0.088 [-0.016, 0.192] | -245 [-617, 127] | -66 | -298 | -309 | -1828 | 0.37 | -22 |
| top_0.05% | 86 | 3.2 | 0.058 [0.007, 0.110] | -253 [-458, -49] | -171 | -340 | -806 | -1781 | 0.63 | -57 |
| top_0.1% | 167 | 6.2 | 0.048 [0.015, 0.080] | -152 [-336, 31] | -200 | -289 | -942 | -2703 | 0.63 | -67 |
| top_0.2% | 311 | 11.5 | 0.045 [0.022, 0.068] | -201 [-323, -78] | -491 | -557 | -2311 | -5379 | 0.74 | -164 |
| top_0.5% | 627 | 23.2 | 0.043 [0.028, 0.059] | -180 [-282, -78] | -889 | -896 | -4183 | -8257 | 0.70 | -296 |
| top_1% | 963 | 35.7 | 0.055 [0.041, 0.069] | -66 [-144, 13] | -497 | -497 | -2339 | -9340 | 0.70 | -166 |
| top_2% | 1379 | 51.1 | 0.060 [0.047, 0.074] | -102 [-162, -42] | -1106 | -1106 | -5202 | -10184 | 0.93 | -369 |
| top_5% | 1750 | 64.8 | 0.064 [0.052, 0.076] | -93 [-145, -41] | -1283 | -1283 | -6033 | -15154 | 0.74 | -428 |
| top_10% | 1883 | 69.7 | 0.066 [0.056, 0.077] | -75 [-125, -25] | -1110 | -1110 | -5220 | -11026 | 0.81 | -370 |
| top_20% | 1976 | 73.2 | 0.057 [0.046, 0.067] | -101 [-144, -58] | -1571 | -1571 | -7388 | -15348 | 0.78 | -524 |
| top_100% | 2030 | 75.2 | 0.067 [0.055, 0.078] | -60 [-106, -14] | -964 | -964 | -4533 | -16458 | 0.67 | -321 |

### 2.4 the strictly-causal threshold (previous era's cut)

The tiers above cut at a percentile of the EVAL era's own score distribution, which no deployed system knows in advance.  Here the cut is the same percentile of the PREVIOUS era's out-of-sample scores, applied unchanged.

**E3 (previous-era cut)**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02%_prev_cut | 8 | 0.3 | 0.000 [0.000, 0.000] | 27 [-376, 430] | 2 | 31 | 8 | -152 | 0.11 | 1 |
| top_0.05%_prev_cut | 9 | 0.3 | 0.000 [0.000, 0.000] | 14 [-346, 373] | 1 | 18 | 5 | -152 | 0.11 | 0 |
| top_0.1%_prev_cut | 19 | 0.7 | 0.105 [-0.021, 0.232] | 212 [-295, 720] | 31 | 310 | 149 | -660 | 0.19 | 10 |
| top_0.2%_prev_cut | 24 | 0.9 | 0.125 [0.006, 0.244] | 155 [-269, 579] | 29 | 219 | 138 | -930 | 0.26 | 10 |
| top_0.5%_prev_cut | 38 | 1.4 | 0.132 [0.037, 0.226] | 240 [-81, 562] | 70 | 351 | 338 | -296 | 0.19 | 23 |
| top_1%_prev_cut | 65 | 2.4 | 0.108 [0.028, 0.188] | 203 [-40, 446] | 101 | 314 | 488 | -1064 | 0.30 | 34 |
| top_2%_prev_cut | 143 | 5.3 | 0.063 [0.014, 0.112] | 10 [-163, 182] | 11 | 18 | 52 | -2394 | 0.52 | 4 |
| top_5%_prev_cut | 393 | 14.6 | 0.081 [0.051, 0.111] | -63 [-175, 49] | -190 | -201 | -915 | -4340 | 0.74 | -63 |
| top_10%_prev_cut | 743 | 27.5 | 0.063 [0.046, 0.080] | -57 [-129, 14] | -327 | -327 | -1574 | -9515 | 0.56 | -109 |
| top_20%_prev_cut | 1068 | 39.6 | 0.060 [0.045, 0.075] | -104 [-157, -51] | -853 | -853 | -4106 | -10190 | 0.74 | -284 |
| top_100%_prev_cut | 1691 | 62.6 | 0.054 [0.043, 0.066] | -74 [-114, -33] | -957 | -957 | -4606 | -10866 | 0.81 | -319 |

**E4 (previous-era cut)**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02%_prev_cut | 0 | 0.0 | . [., .] | . [., .] | 0 | . | 0 | 0 | 0.00 | 0 |
| top_0.05%_prev_cut | 0 | 0.0 | . [., .] | . [., .] | 0 | . | 0 | 0 | 0.00 | 0 |
| top_0.1%_prev_cut | 0 | 0.0 | . [., .] | . [., .] | 0 | . | 0 | 0 | 0.00 | 0 |
| top_0.2%_prev_cut | 0 | 0.0 | . [., .] | . [., .] | 0 | . | 0 | 0 | 0.00 | 0 |
| top_0.5%_prev_cut | 0 | 0.0 | . [., .] | . [., .] | 0 | . | 0 | 0 | 0.00 | 0 |
| top_1%_prev_cut | 0 | 0.0 | . [., .] | . [., .] | 0 | . | 0 | 0 | 0.00 | 0 |
| top_2%_prev_cut | 0 | 0.0 | . [., .] | . [., .] | 0 | . | 0 | 0 | 0.00 | 0 |
| top_5%_prev_cut | 5 | 0.2 | 0.000 [0.000, 0.000] | -275 [-1239, 689] | -11 | -275 | -53 | -218 | 0.15 | -4 |
| top_10%_prev_cut | 24 | 0.9 | 0.083 [-0.040, 0.207] | -444 [-789, -99] | -83 | -665 | -409 | -1794 | 0.38 | -28 |
| top_20%_prev_cut | 78 | 3.0 | 0.115 [0.048, 0.183] | 97 [-149, 343] | 59 | 165 | 291 | -930 | 0.42 | 20 |
| top_100%_prev_cut | 1550 | 59.6 | 0.054 [0.043, 0.065] | -31 [-73, 11] | -372 | -372 | -1845 | -9412 | 0.62 | -125 |

**E5 (previous-era cut)**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02%_prev_cut | 9 | 0.3 | 0.000 [0.000, 0.000] | -309 [-946, 328] | -22 | -398 | -107 | -542 | 0.19 | -7 |
| top_0.05%_prev_cut | 16 | 0.6 | 0.000 [0.000, 0.000] | -164 [-621, 294] | -20 | -187 | -101 | -1395 | 0.23 | -7 |
| top_0.1%_prev_cut | 30 | 1.2 | 0.067 [-0.033, 0.167] | -149 [-581, 283] | -35 | -212 | -172 | -1860 | 0.31 | -12 |
| top_0.2%_prev_cut | 47 | 1.8 | 0.064 [-0.007, 0.135] | -12 [-371, 347] | -4 | -17 | -22 | -1554 | 0.42 | -1 |
| top_0.5%_prev_cut | 66 | 2.5 | 0.121 [0.040, 0.202] | 46 [-280, 371] | 23 | 67 | 116 | -2354 | 0.46 | 8 |
| top_1%_prev_cut | 100 | 3.8 | 0.130 [0.064, 0.196] | -38 [-269, 193] | -30 | -64 | -147 | -2790 | 0.46 | -10 |
| top_2%_prev_cut | 160 | 6.2 | 0.100 [0.053, 0.147] | -134 [-310, 41] | -167 | -253 | -826 | -4724 | 0.54 | -56 |
| top_5%_prev_cut | 260 | 10.0 | 0.077 [0.045, 0.109] | -147 [-282, -11] | -296 | -347 | -1468 | -5631 | 0.65 | -99 |
| top_10%_prev_cut | 328 | 12.6 | 0.082 [0.053, 0.112] | -138 [-254, -21] | -350 | -367 | -1735 | -6156 | 0.69 | -117 |
| top_20%_prev_cut | 422 | 16.2 | 0.090 [0.060, 0.120] | -26 [-131, 80] | -84 | -84 | -415 | -4954 | 0.54 | -28 |
| top_100%_prev_cut | 1451 | 55.8 | 0.058 [0.046, 0.070] | -24 [-65, 17] | -272 | -272 | -1349 | -8519 | 0.54 | -91 |

**E6 (previous-era cut)**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02%_prev_cut | 37 | 1.4 | 0.054 [-0.028, 0.136] | -175 [-508, 158] | -51 | -432 | -249 | -1793 | 0.27 | -17 |
| top_0.05%_prev_cut | 46 | 1.8 | 0.065 [-0.022, 0.152] | -300 [-577, -23] | -108 | -767 | -531 | -1827 | 0.35 | -36 |
| top_0.1%_prev_cut | 47 | 1.8 | 0.064 [-0.021, 0.148] | -325 [-595, -55] | -119 | -804 | -587 | -1984 | 0.35 | -40 |
| top_0.2%_prev_cut | 97 | 3.7 | 0.093 [0.038, 0.147] | 48 [-229, 326] | 37 | 106 | 180 | -1864 | 0.38 | 12 |
| top_0.5%_prev_cut | 180 | 6.9 | 0.078 [0.040, 0.116] | -80 [-279, 119] | -113 | -234 | -557 | -3807 | 0.54 | -38 |
| top_1%_prev_cut | 215 | 8.3 | 0.070 [0.039, 0.101] | -86 [-263, 91] | -145 | -257 | -712 | -4373 | 0.58 | -48 |
| top_2%_prev_cut | 266 | 10.2 | 0.075 [0.044, 0.106] | -36 [-203, 131] | -75 | -108 | -371 | -8234 | 0.46 | -25 |
| top_5%_prev_cut | 408 | 15.7 | 0.091 [0.061, 0.120] | -103 [-215, 10] | -327 | -388 | -1610 | -8980 | 0.58 | -109 |
| top_10%_prev_cut | 563 | 21.7 | 0.085 [0.061, 0.110] | -89 [-196, 18] | -392 | -415 | -1931 | -12326 | 0.58 | -131 |
| top_20%_prev_cut | 872 | 33.5 | 0.092 [0.072, 0.112] | -60 [-152, 33] | -407 | -407 | -2002 | -14185 | 0.58 | -136 |
| top_100%_prev_cut | 1717 | 66.0 | 0.070 [0.057, 0.083] | -8 [-63, 47] | -107 | -107 | -525 | -12908 | 0.46 | -36 |

**E8_GATE_2025H1 (previous-era cut)**

| tier | n takes | takes/wk | precision [CI] | $/trade [CI] | $/day | $/traded-day | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|---|---|
| top_0.02%_prev_cut | 5 | 0.2 | 0.000 [0.000, 0.000] | -332 [-1457, 792] | -13 | -554 | -62 | 0 | 0.07 | -4 |
| top_0.05%_prev_cut | 4 | 0.1 | 0.000 [0.000, 0.000] | -174 [-1827, 1480] | -5 | -232 | -26 | 0 | 0.04 | -2 |
| top_0.1%_prev_cut | 5 | 0.2 | 0.000 [0.000, 0.000] | 148 [-590, 885] | 6 | 184 | 27 | 0 | 0.04 | 2 |
| top_0.2%_prev_cut | 5 | 0.2 | 0.000 [0.000, 0.000] | -132 [-991, 726] | -5 | -166 | -25 | 0 | 0.07 | -2 |
| top_0.5%_prev_cut | 5 | 0.2 | 0.000 [0.000, 0.000] | -80 [-1000, 840] | -3 | -100 | -15 | 0 | 0.07 | -1 |
| top_1%_prev_cut | 5 | 0.2 | 0.200 [-0.355, 0.755] | 105 [-1188, 1398] | 4 | 105 | 19 | 0 | 0.07 | 1 |
| top_2%_prev_cut | 7 | 0.3 | 0.000 [0.000, 0.000] | -334 [-919, 252] | -18 | -467 | -86 | -372 | 0.11 | -6 |
| top_5%_prev_cut | 17 | 0.6 | 0.000 [0.000, 0.000] | -84 [-674, 505] | -11 | -159 | -53 | -618 | 0.15 | -4 |
| top_10%_prev_cut | 74 | 2.7 | 0.081 [0.019, 0.143] | 145 [-236, 526] | 85 | 276 | 398 | -2079 | 0.30 | 28 |
| top_20%_prev_cut | 378 | 14.0 | 0.098 [0.068, 0.128] | -49 [-183, 84] | -147 | -187 | -692 | -4390 | 0.59 | -49 |
| top_100%_prev_cut | 2030 | 75.2 | 0.067 [0.055, 0.078] | -60 [-106, -14] | -964 | -964 | -4533 | -16458 | 0.67 | -321 |


---

## 3. CALIBRATION — predicted vs realised winner rate

Over CANDIDATES inside each tier (not over seats): this is a statement about the score, not about the schedule.  The head is fitted with squared error on the 0/1 D-021 winner label, so its output is a predicted RATE and the two columns are directly comparable.

**E3**

| tier | n | predicted | realised [CI] | realised − predicted | score range |
|---|---|---|---|---|---|
| top_0.02% | 30 | 0.4447 | 0.0000 [0.0000, 0.0000] | -0.4447 | 0.387 … 0.494 |
| top_0.05% | 76 | 0.3970 | 0.0000 [0.0000, 0.0000] | -0.3970 | 0.343 … 0.494 |
| top_0.1% | 152 | 0.3590 | 0.0000 [0.0000, 0.0000] | -0.3590 | 0.301 … 0.494 |
| top_0.2% | 304 | 0.3202 | 0.0526 [0.0030, 0.1022] | -0.2675 | 0.266 … 0.494 |
| top_0.5% | 759 | 0.2759 | 0.0791 [0.0099, 0.1482] | -0.1968 | 0.226 … 0.494 |
| top_1% | 1518 | 0.2410 | 0.1061 [0.0398, 0.1724] | -0.1350 | 0.193 … 0.494 |
| top_2% | 3036 | 0.2097 | 0.0932 [0.0487, 0.1377] | -0.1165 | 0.169 … 0.494 |
| top_5% | 7591 | 0.1753 | 0.0892 [0.0607, 0.1177] | -0.0861 | 0.141 … 0.494 |
| top_10% | 15182 | 0.1523 | 0.0788 [0.0605, 0.0971] | -0.0736 | 0.120 … 0.494 |
| top_20% | 30364 | 0.1310 | 0.0789 [0.0646, 0.0931] | -0.0521 | 0.101 … 0.494 |
| top_100% | 151822 | 0.0692 | 0.0549 [0.0483, 0.0614] | -0.0143 | 0.009 … 0.494 |

**E4**

| tier | n | predicted | realised [CI] | realised − predicted | score range |
|---|---|---|---|---|---|
| top_0.02% | 30 | 0.1554 | 0.0000 [0.0000, 0.0000] | -0.1554 | 0.150 … 0.159 |
| top_0.05% | 74 | 0.1480 | 0.0541 [-0.1090, 0.2171] | -0.0939 | 0.137 … 0.159 |
| top_0.1% | 148 | 0.1402 | 0.1554 [-0.1240, 0.4348] | 0.0152 | 0.128 … 0.159 |
| top_0.2% | 297 | 0.1316 | 0.0909 [-0.0451, 0.2269] | -0.0407 | 0.120 … 0.159 |
| top_0.5% | 742 | 0.1225 | 0.0984 [0.0250, 0.1718] | -0.0242 | 0.113 … 0.159 |
| top_1% | 1484 | 0.1155 | 0.1388 [0.0701, 0.2076] | 0.0234 | 0.105 … 0.159 |
| top_2% | 2968 | 0.1084 | 0.1193 [0.0622, 0.1764] | 0.0109 | 0.098 … 0.159 |
| top_5% | 7421 | 0.1000 | 0.1070 [0.0769, 0.1371] | 0.0070 | 0.092 … 0.159 |
| top_10% | 14842 | 0.0945 | 0.1023 [0.0812, 0.1233] | 0.0078 | 0.087 … 0.159 |
| top_20% | 29684 | 0.0889 | 0.0972 [0.0837, 0.1107] | 0.0083 | 0.080 … 0.159 |
| top_100% | 148418 | 0.0573 | 0.0493 [0.0441, 0.0544] | -0.0081 | 0.021 … 0.159 |

**E5**

| tier | n | predicted | realised [CI] | realised − predicted | score range |
|---|---|---|---|---|---|
| top_0.02% | 31 | 0.1910 | 0.0000 [0.0000, 0.0000] | -0.1910 | 0.183 … 0.202 |
| top_0.05% | 76 | 0.1811 | 0.0000 [0.0000, 0.0000] | -0.1811 | 0.172 … 0.202 |
| top_0.1% | 153 | 0.1759 | 0.0458 [-0.0590, 0.1505] | -0.1301 | 0.169 … 0.202 |
| top_0.2% | 306 | 0.1631 | 0.0425 [-0.0316, 0.1166] | -0.1206 | 0.139 … 0.202 |
| top_0.5% | 765 | 0.1427 | 0.1059 [0.0086, 0.2032] | -0.0369 | 0.124 … 0.202 |
| top_1% | 1529 | 0.1318 | 0.1714 [0.0919, 0.2509] | 0.0395 | 0.117 … 0.202 |
| top_2% | 3059 | 0.1226 | 0.1281 [0.0705, 0.1858] | 0.0055 | 0.110 … 0.202 |
| top_5% | 7647 | 0.1117 | 0.1211 [0.0841, 0.1581] | 0.0093 | 0.101 … 0.202 |
| top_10% | 15295 | 0.1042 | 0.1113 [0.0862, 0.1364] | 0.0071 | 0.093 … 0.202 |
| top_20% | 30589 | 0.0953 | 0.0974 [0.0801, 0.1146] | 0.0021 | 0.080 … 0.202 |
| top_100% | 152947 | 0.0502 | 0.0457 [0.0394, 0.0519] | -0.0046 | 0.006 … 0.202 |

**E6**

| tier | n | predicted | realised [CI] | realised − predicted | score range |
|---|---|---|---|---|---|
| top_0.02% | 33 | 0.2923 | 0.0000 [., .] | -0.2923 | 0.290 … 0.299 |
| top_0.05% | 82 | 0.2783 | 0.0000 [0.0000, 0.0000] | -0.2783 | 0.264 … 0.299 |
| top_0.1% | 163 | 0.2684 | 0.0123 [-0.0038, 0.0283] | -0.2561 | 0.256 … 0.299 |
| top_0.2% | 326 | 0.2602 | 0.1810 [-0.0798, 0.4418] | -0.0793 | 0.243 … 0.299 |
| top_0.5% | 815 | 0.2388 | 0.1313 [0.0134, 0.2492] | -0.1075 | 0.205 … 0.299 |
| top_1% | 1631 | 0.2128 | 0.1055 [0.0424, 0.1685] | -0.1073 | 0.173 … 0.299 |
| top_2% | 3261 | 0.1852 | 0.0874 [0.0573, 0.1175] | -0.0978 | 0.147 … 0.299 |
| top_5% | 8153 | 0.1521 | 0.1057 [0.0801, 0.1314] | -0.0464 | 0.120 … 0.299 |
| top_10% | 16306 | 0.1312 | 0.1046 [0.0892, 0.1200] | -0.0266 | 0.103 … 0.299 |
| top_20% | 32612 | 0.1135 | 0.1003 [0.0888, 0.1118] | -0.0132 | 0.089 … 0.299 |
| top_100% | 163062 | 0.0590 | 0.0591 [0.0536, 0.0645] | 0.0000 | 0.005 … 0.299 |

**E8_GATE_2025H1**

| tier | n | predicted | realised [CI] | realised − predicted | score range |
|---|---|---|---|---|---|
| top_0.02% | 34 | 0.1695 | 0.0000 [., .] | -0.1695 | 0.163 … 0.179 |
| top_0.05% | 86 | 0.1612 | 0.0000 [0.0000, 0.0000] | -0.1612 | 0.147 … 0.179 |
| top_0.1% | 172 | 0.1529 | 0.0000 [0.0000, 0.0000] | -0.1529 | 0.141 … 0.179 |
| top_0.2% | 345 | 0.1385 | 0.0232 [-0.0308, 0.0771] | -0.1153 | 0.113 … 0.179 |
| top_0.5% | 862 | 0.1201 | 0.0708 [0.0091, 0.1325] | -0.0493 | 0.105 … 0.179 |
| top_1% | 1723 | 0.1121 | 0.0894 [0.0175, 0.1612] | -0.0227 | 0.103 … 0.179 |
| top_2% | 3447 | 0.1068 | 0.0899 [0.0438, 0.1361] | -0.0169 | 0.101 … 0.179 |
| top_5% | 8616 | 0.1022 | 0.0896 [0.0622, 0.1170] | -0.0126 | 0.098 … 0.179 |
| top_10% | 17233 | 0.0989 | 0.0930 [0.0737, 0.1123] | -0.0059 | 0.094 … 0.179 |
| top_20% | 34466 | 0.0949 | 0.0951 [0.0815, 0.1086] | 0.0002 | 0.088 … 0.179 |
| top_100% | 172328 | 0.0635 | 0.0650 [0.0604, 0.0695] | 0.0014 | 0.017 … 0.179 |


---

## 4. THE DAY-ABSTENTION FRONTIER

`causal_top3_running`: an (asset, day) qualifies the instant its RUNNING top-3 mean of already-arrived candidate scores crosses the gate; entries are allowed from that second on.  No day-end quantity is read anywhere.  `preday_forecaster`: the oracle-free variant — a walk-forward day-value model on the forecaster and overnight state as of the day's FIRST candidate second, with no candidate score in it at all.

### 4.1 causal_top3_running

**E3**

| gate pct | sessions qualified | tier | n takes | takes/wk | precision | $/trade | $/traded-day | $/week | frac days traded |
|---|---|---|---|---|---|---|---|---|---|
| q0.0 | 390 | top_0.05% | 8 | 0.3 | 0.000 | -127 | -145 | -38 | 0.054 |
| q0.0 | 390 | top_0.1% | 17 | 0.6 | 0.000 | -165 | -216 | -104 | 0.100 |
| q0.0 | 390 | top_0.2% | 26 | 1.0 | 0.077 | 22 | 30 | 21 | 0.146 |
| q0.0 | 390 | top_0.5% | 42 | 1.6 | 0.119 | 300 | 420 | 467 | 0.231 |
| q0.0 | 390 | top_1% | 76 | 2.8 | 0.092 | 120 | 183 | 339 | 0.385 |
| q0.0 | 390 | top_2% | 146 | 5.4 | 0.062 | 18 | 33 | 98 | 0.608 |
| q0.0 | 390 | top_5% | 293 | 10.9 | 0.079 | -47 | -124 | -508 | 0.854 |
| q0.0 | 390 | top_100% | 1690 | 62.6 | 0.053 | -78 | -1019 | -4905 | 1.000 |
| q50.0 | 390 | top_0.05% | 7 | 0.3 | 0.000 | -69 | -81 | -18 | 0.046 |
| q50.0 | 390 | top_0.1% | 15 | 0.6 | 0.000 | -180 | -225 | -100 | 0.092 |
| q50.0 | 390 | top_0.2% | 25 | 0.9 | 0.080 | 108 | 151 | 100 | 0.139 |
| q50.0 | 390 | top_0.5% | 42 | 1.6 | 0.119 | 304 | 425 | 472 | 0.231 |
| q50.0 | 390 | top_1% | 76 | 2.8 | 0.092 | 113 | 172 | 318 | 0.385 |
| q50.0 | 390 | top_2% | 142 | 5.3 | 0.056 | -9 | -16 | -47 | 0.600 |
| q50.0 | 390 | top_5% | 280 | 10.4 | 0.079 | -34 | -87 | -353 | 0.846 |
| q50.0 | 390 | top_100% | 1564 | 57.9 | 0.051 | -86 | -1029 | -4954 | 1.000 |
| q70.0 | 388 | top_0.05% | 4 | 0.1 | 0.000 | -18 | -18 | -3 | 0.031 |
| q70.0 | 388 | top_0.1% | 12 | 0.4 | 0.000 | -126 | -168 | -56 | 0.069 |
| q70.0 | 388 | top_0.2% | 23 | 0.9 | 0.130 | 170 | 244 | 145 | 0.123 |
| q70.0 | 388 | top_0.5% | 37 | 1.4 | 0.108 | 169 | 251 | 232 | 0.192 |
| q70.0 | 388 | top_1% | 62 | 2.3 | 0.113 | 180 | 279 | 414 | 0.308 |
| q70.0 | 388 | top_2% | 126 | 4.7 | 0.071 | 51 | 91 | 239 | 0.546 |
| q70.0 | 388 | top_5% | 240 | 8.9 | 0.071 | -50 | -114 | -446 | 0.815 |
| q70.0 | 388 | top_100% | 1192 | 44.1 | 0.055 | -105 | -959 | -4617 | 1.000 |
| q80.0 | 360 | top_0.05% | 3 | 0.1 | 0.000 | 87 | 87 | 10 | 0.023 |
| q80.0 | 360 | top_0.1% | 8 | 0.3 | 0.000 | 27 | 31 | 8 | 0.054 |
| q80.0 | 360 | top_0.2% | 20 | 0.7 | 0.150 | 303 | 433 | 225 | 0.108 |
| q80.0 | 360 | top_0.5% | 30 | 1.1 | 0.133 | 229 | 327 | 254 | 0.162 |
| q80.0 | 360 | top_1% | 55 | 2.0 | 0.109 | 258 | 384 | 526 | 0.285 |
| q80.0 | 360 | top_2% | 102 | 3.8 | 0.088 | 79 | 130 | 299 | 0.477 |
| q80.0 | 360 | top_5% | 216 | 8.0 | 0.074 | -23 | -50 | -180 | 0.754 |
| q80.0 | 360 | top_100% | 959 | 35.5 | 0.053 | -86 | -635 | -3057 | 1.000 |
| q90.0 | 271 | top_0.05% | 2 | 0.1 | 0.000 | 451 | 451 | 33 | 0.015 |
| q90.0 | 271 | top_0.1% | 6 | 0.2 | 0.000 | -174 | -208 | -39 | 0.038 |
| q90.0 | 271 | top_0.2% | 14 | 0.5 | 0.000 | -126 | -161 | -66 | 0.085 |
| q90.0 | 271 | top_0.5% | 28 | 1.0 | 0.071 | 51 | 68 | 53 | 0.162 |
| q90.0 | 271 | top_1% | 40 | 1.5 | 0.125 | 260 | 371 | 385 | 0.215 |
| q90.0 | 271 | top_2% | 76 | 2.8 | 0.092 | 105 | 159 | 295 | 0.385 |
| q90.0 | 271 | top_5% | 169 | 6.3 | 0.053 | -28 | -55 | -174 | 0.661 |
| q90.0 | 271 | top_100% | 686 | 25.4 | 0.055 | -65 | -350 | -1646 | 0.977 |
| q95.0 | 184 | top_0.05% | 2 | 0.1 | 0.000 | 292 | 292 | 22 | 0.015 |
| q95.0 | 184 | top_0.1% | 3 | 0.1 | 0.000 | 99 | 99 | 11 | 0.023 |
| q95.0 | 184 | top_0.2% | 7 | 0.3 | 0.000 | -85 | -85 | -22 | 0.054 |
| q95.0 | 184 | top_0.5% | 21 | 0.8 | 0.143 | 222 | 333 | 172 | 0.108 |
| q95.0 | 184 | top_1% | 29 | 1.1 | 0.103 | 121 | 167 | 130 | 0.162 |
| q95.0 | 184 | top_2% | 53 | 2.0 | 0.113 | 283 | 416 | 555 | 0.277 |
| q95.0 | 184 | top_5% | 121 | 4.5 | 0.066 | 40 | 70 | 179 | 0.531 |
| q95.0 | 184 | top_100% | 448 | 16.6 | 0.056 | -89 | -371 | -1484 | 0.831 |
| q97.5 | 121 | top_0.05% | 1 | 0.0 | 0.000 | 645 | 645 | 24 | 0.008 |
| q97.5 | 121 | top_0.1% | 2 | 0.1 | 0.000 | 451 | 451 | 33 | 0.015 |
| q97.5 | 121 | top_0.2% | 4 | 0.1 | 0.000 | -18 | -18 | -3 | 0.031 |
| q97.5 | 121 | top_0.5% | 16 | 0.6 | 0.000 | -183 | -244 | -109 | 0.092 |
| q97.5 | 121 | top_1% | 25 | 0.9 | 0.080 | 108 | 151 | 100 | 0.139 |
| q97.5 | 121 | top_2% | 37 | 1.4 | 0.108 | 171 | 253 | 234 | 0.192 |
| q97.5 | 121 | top_5% | 76 | 2.8 | 0.092 | 112 | 170 | 315 | 0.385 |
| q97.5 | 121 | top_100% | 285 | 10.6 | 0.053 | -52 | -181 | -544 | 0.623 |
| q99.0 | 58 | top_0.05% | 1 | 0.0 | 0.000 | 645 | 645 | 24 | 0.008 |
| q99.0 | 58 | top_0.1% | 1 | 0.0 | 0.000 | 645 | 645 | 24 | 0.008 |
| q99.0 | 58 | top_0.2% | 2 | 0.1 | 0.000 | 292 | 292 | 22 | 0.015 |
| q99.0 | 58 | top_0.5% | 4 | 0.1 | 0.000 | -18 | -18 | -3 | 0.031 |
| q99.0 | 58 | top_1% | 12 | 0.4 | 0.000 | -126 | -168 | -56 | 0.069 |
| q99.0 | 58 | top_2% | 23 | 0.9 | 0.130 | 166 | 239 | 142 | 0.123 |
| q99.0 | 58 | top_5% | 37 | 1.4 | 0.135 | 169 | 250 | 231 | 0.192 |
| q99.0 | 58 | top_100% | 117 | 4.3 | 0.051 | -97 | -246 | -419 | 0.354 |

**E4**

| gate pct | sessions qualified | tier | n takes | takes/wk | precision | $/trade | $/traded-day | $/week | frac days traded |
|---|---|---|---|---|---|---|---|---|---|
| q0.0 | 385 | top_0.05% | 8 | 0.3 | 0.125 | -160 | -213 | -49 | 0.046 |
| q0.0 | 385 | top_0.1% | 12 | 0.5 | 0.083 | -431 | -647 | -199 | 0.062 |
| q0.0 | 385 | top_0.2% | 24 | 0.9 | 0.083 | -444 | -665 | -409 | 0.124 |
| q0.0 | 385 | top_0.5% | 41 | 1.6 | 0.073 | -238 | -336 | -375 | 0.225 |
| q0.0 | 385 | top_1% | 59 | 2.3 | 0.152 | 41 | 66 | 94 | 0.287 |
| q0.0 | 385 | top_2% | 98 | 3.8 | 0.102 | 58 | 97 | 217 | 0.450 |
| q0.0 | 385 | top_5% | 180 | 6.9 | 0.111 | 111 | 224 | 767 | 0.690 |
| q0.0 | 385 | top_100% | 1557 | 59.9 | 0.048 | -44 | -528 | -2619 | 1.000 |
| q50.0 | 385 | top_0.05% | 6 | 0.2 | 0.000 | -282 | -338 | -65 | 0.039 |
| q50.0 | 385 | top_0.1% | 10 | 0.4 | 0.100 | -408 | -582 | -157 | 0.054 |
| q50.0 | 385 | top_0.2% | 23 | 0.9 | 0.087 | -422 | -648 | -374 | 0.116 |
| q50.0 | 385 | top_0.5% | 36 | 1.4 | 0.083 | -198 | -286 | -275 | 0.194 |
| q50.0 | 385 | top_1% | 56 | 2.2 | 0.143 | 23 | 36 | 50 | 0.279 |
| q50.0 | 385 | top_2% | 95 | 3.7 | 0.105 | 73 | 124 | 267 | 0.434 |
| q50.0 | 385 | top_5% | 172 | 6.6 | 0.128 | 130 | 258 | 863 | 0.674 |
| q50.0 | 385 | top_100% | 1337 | 51.4 | 0.053 | -45 | -465 | -2307 | 1.000 |
| q70.0 | 364 | top_0.05% | 4 | 0.2 | 0.000 | -318 | -318 | -49 | 0.031 |
| q70.0 | 364 | top_0.1% | 8 | 0.3 | 0.125 | -160 | -213 | -49 | 0.046 |
| q70.0 | 364 | top_0.2% | 16 | 0.6 | 0.062 | -489 | -870 | -301 | 0.070 |
| q70.0 | 364 | top_0.5% | 26 | 1.0 | 0.115 | -237 | -363 | -237 | 0.132 |
| q70.0 | 364 | top_1% | 45 | 1.7 | 0.067 | -116 | -180 | -201 | 0.225 |
| q70.0 | 364 | top_2% | 66 | 2.5 | 0.121 | -29 | -46 | -75 | 0.326 |
| q70.0 | 364 | top_5% | 141 | 5.4 | 0.106 | 80 | 149 | 436 | 0.589 |
| q70.0 | 364 | top_100% | 727 | 28.0 | 0.066 | -44 | -251 | -1244 | 1.000 |
| q80.0 | 315 | top_0.05% | 3 | 0.1 | 0.000 | -113 | -113 | -13 | 0.023 |
| q80.0 | 315 | top_0.1% | 8 | 0.3 | 0.125 | -160 | -213 | -49 | 0.046 |
| q80.0 | 315 | top_0.2% | 13 | 0.5 | 0.077 | -388 | -630 | -194 | 0.062 |
| q80.0 | 315 | top_0.5% | 23 | 0.9 | 0.130 | -237 | -341 | -210 | 0.124 |
| q80.0 | 315 | top_1% | 43 | 1.7 | 0.070 | -203 | -301 | -336 | 0.225 |
| q80.0 | 315 | top_2% | 60 | 2.3 | 0.150 | 42 | 69 | 98 | 0.287 |
| q80.0 | 315 | top_5% | 120 | 4.6 | 0.125 | 106 | 189 | 488 | 0.519 |
| q80.0 | 315 | top_100% | 610 | 23.5 | 0.067 | -90 | -445 | -2123 | 0.961 |
| q90.0 | 204 | top_0.05% | 2 | 0.1 | 0.000 | -642 | -642 | -49 | 0.015 |
| q90.0 | 204 | top_0.1% | 4 | 0.2 | 0.000 | -318 | -318 | -49 | 0.031 |
| q90.0 | 204 | top_0.2% | 8 | 0.3 | 0.125 | -160 | -213 | -49 | 0.046 |
| q90.0 | 204 | top_0.5% | 21 | 0.8 | 0.095 | -374 | -561 | -302 | 0.108 |
| q90.0 | 204 | top_1% | 26 | 1.0 | 0.115 | -237 | -363 | -237 | 0.132 |
| q90.0 | 204 | top_2% | 45 | 1.7 | 0.067 | -160 | -249 | -278 | 0.225 |
| q90.0 | 204 | top_5% | 80 | 3.1 | 0.113 | 131 | 223 | 403 | 0.364 |
| q90.0 | 204 | top_100% | 372 | 14.3 | 0.081 | 15 | 51 | 212 | 0.845 |
| q95.0 | 143 | top_0.05% | 2 | 0.1 | 0.000 | -642 | -642 | -49 | 0.015 |
| q95.0 | 143 | top_0.1% | 2 | 0.1 | 0.000 | -642 | -642 | -49 | 0.015 |
| q95.0 | 143 | top_0.2% | 5 | 0.2 | 0.000 | -275 | -275 | -53 | 0.039 |
| q95.0 | 143 | top_0.5% | 11 | 0.4 | 0.091 | -386 | -606 | -163 | 0.054 |
| q95.0 | 143 | top_1% | 23 | 0.9 | 0.087 | -422 | -648 | -374 | 0.116 |
| q95.0 | 143 | top_2% | 32 | 1.2 | 0.125 | -174 | -265 | -214 | 0.163 |
| q95.0 | 143 | top_5% | 59 | 2.3 | 0.152 | 56 | 89 | 127 | 0.287 |
| q95.0 | 143 | top_100% | 242 | 9.3 | 0.091 | 51 | 144 | 475 | 0.667 |
| q97.5 | 92 | top_0.05% | 2 | 0.1 | 0.000 | -642 | -642 | -49 | 0.015 |
| q97.5 | 92 | top_0.1% | 2 | 0.1 | 0.000 | -642 | -642 | -49 | 0.015 |
| q97.5 | 92 | top_0.2% | 3 | 0.1 | 0.000 | -113 | -113 | -13 | 0.023 |
| q97.5 | 92 | top_0.5% | 8 | 0.3 | 0.125 | -160 | -213 | -49 | 0.046 |
| q97.5 | 92 | top_1% | 14 | 0.5 | 0.071 | -426 | -746 | -230 | 0.062 |
| q97.5 | 92 | top_2% | 25 | 1.0 | 0.080 | -392 | -613 | -377 | 0.124 |
| q97.5 | 92 | top_5% | 44 | 1.7 | 0.068 | -177 | -268 | -299 | 0.225 |
| q97.5 | 92 | top_100% | 159 | 6.1 | 0.094 | -43 | -107 | -262 | 0.496 |
| q99.0 | 42 | top_0.05% | 2 | 0.1 | 0.000 | -642 | -642 | -49 | 0.015 |
| q99.0 | 42 | top_0.1% | 2 | 0.1 | 0.000 | -642 | -642 | -49 | 0.015 |
| q99.0 | 42 | top_0.2% | 2 | 0.1 | 0.000 | -642 | -642 | -49 | 0.015 |
| q99.0 | 42 | top_0.5% | 4 | 0.2 | 0.000 | -318 | -318 | -49 | 0.031 |
| q99.0 | 42 | top_1% | 8 | 0.3 | 0.125 | -158 | -211 | -49 | 0.046 |
| q99.0 | 42 | top_2% | 15 | 0.6 | 0.067 | -459 | -861 | -265 | 0.062 |
| q99.0 | 42 | top_5% | 25 | 1.0 | 0.120 | -299 | -467 | -288 | 0.124 |
| q99.0 | 42 | top_100% | 71 | 2.7 | 0.141 | -1 | -3 | -4 | 0.256 |

**E5**

| gate pct | sessions qualified | tier | n takes | takes/wk | precision | $/trade | $/traded-day | $/week | frac days traded |
|---|---|---|---|---|---|---|---|---|---|
| q0.0 | 387 | top_0.05% | 6 | 0.2 | 0.000 | -505 | -606 | -117 | 0.039 |
| q0.0 | 387 | top_0.1% | 7 | 0.3 | 0.000 | -242 | -340 | -65 | 0.039 |
| q0.0 | 387 | top_0.2% | 14 | 0.5 | 0.000 | -61 | -71 | -33 | 0.093 |
| q0.0 | 387 | top_0.5% | 33 | 1.3 | 0.091 | 142 | 195 | 180 | 0.186 |
| q0.0 | 387 | top_1% | 55 | 2.1 | 0.091 | -22 | -31 | -48 | 0.310 |
| q0.0 | 387 | top_2% | 80 | 3.1 | 0.113 | -60 | -91 | -186 | 0.411 |
| q0.0 | 387 | top_5% | 133 | 5.1 | 0.128 | -11 | -20 | -58 | 0.589 |
| q0.0 | 387 | top_100% | 1524 | 58.6 | 0.059 | -23 | -270 | -1341 | 1.000 |
| q50.0 | 387 | top_0.05% | 6 | 0.2 | 0.000 | -505 | -606 | -117 | 0.039 |
| q50.0 | 387 | top_0.1% | 7 | 0.3 | 0.000 | -242 | -340 | -65 | 0.039 |
| q50.0 | 387 | top_0.2% | 14 | 0.5 | 0.000 | -61 | -71 | -33 | 0.093 |
| q50.0 | 387 | top_0.5% | 33 | 1.3 | 0.091 | -5 | -7 | -6 | 0.186 |
| q50.0 | 387 | top_1% | 53 | 2.0 | 0.094 | 20 | 27 | 40 | 0.302 |
| q50.0 | 387 | top_2% | 76 | 2.9 | 0.118 | -51 | -76 | -150 | 0.395 |
| q50.0 | 387 | top_5% | 128 | 4.9 | 0.133 | -32 | -55 | -155 | 0.574 |
| q50.0 | 387 | top_100% | 1402 | 53.9 | 0.061 | -40 | -439 | -2179 | 1.000 |
| q70.0 | 352 | top_0.05% | 4 | 0.2 | 0.000 | -727 | -969 | -112 | 0.023 |
| q70.0 | 352 | top_0.1% | 7 | 0.3 | 0.000 | -242 | -340 | -65 | 0.039 |
| q70.0 | 352 | top_0.2% | 11 | 0.4 | 0.000 | -263 | -321 | -111 | 0.070 |
| q70.0 | 352 | top_0.5% | 26 | 1.0 | 0.077 | -29 | -37 | -29 | 0.155 |
| q70.0 | 352 | top_1% | 38 | 1.5 | 0.053 | 84 | 118 | 123 | 0.209 |
| q70.0 | 352 | top_2% | 59 | 2.3 | 0.119 | 90 | 120 | 204 | 0.341 |
| q70.0 | 352 | top_5% | 108 | 4.2 | 0.148 | -34 | -56 | -140 | 0.504 |
| q70.0 | 352 | top_100% | 921 | 35.4 | 0.078 | -51 | -367 | -1823 | 1.000 |
| q80.0 | 257 | top_0.05% | 4 | 0.2 | 0.000 | -727 | -969 | -112 | 0.023 |
| q80.0 | 257 | top_0.1% | 6 | 0.2 | 0.000 | -505 | -606 | -117 | 0.039 |
| q80.0 | 257 | top_0.2% | 7 | 0.3 | 0.000 | -242 | -340 | -65 | 0.039 |
| q80.0 | 257 | top_0.5% | 16 | 0.6 | 0.000 | -164 | -187 | -101 | 0.108 |
| q80.0 | 257 | top_1% | 32 | 1.2 | 0.062 | 29 | 39 | 36 | 0.186 |
| q80.0 | 257 | top_2% | 55 | 2.1 | 0.091 | -22 | -31 | -48 | 0.310 |
| q80.0 | 257 | top_5% | 85 | 3.3 | 0.118 | -78 | -121 | -256 | 0.426 |
| q80.0 | 257 | top_100% | 626 | 24.1 | 0.085 | -47 | -230 | -1132 | 0.992 |
| q90.0 | 156 | top_0.05% | 2 | 0.1 | 0.000 | -424 | -424 | -33 | 0.015 |
| q90.0 | 156 | top_0.1% | 4 | 0.2 | 0.000 | -727 | -969 | -112 | 0.023 |
| q90.0 | 156 | top_0.2% | 6 | 0.2 | 0.000 | -505 | -606 | -117 | 0.039 |
| q90.0 | 156 | top_0.5% | 11 | 0.4 | 0.000 | -263 | -321 | -111 | 0.070 |
| q90.0 | 156 | top_1% | 19 | 0.7 | 0.053 | 4 | 4 | 3 | 0.124 |
| q90.0 | 156 | top_2% | 33 | 1.3 | 0.061 | 157 | 207 | 199 | 0.194 |
| q90.0 | 156 | top_5% | 57 | 2.2 | 0.105 | 129 | 167 | 283 | 0.341 |
| q90.0 | 156 | top_100% | 334 | 12.8 | 0.093 | -59 | -186 | -757 | 0.822 |
| q95.0 | 91 | top_0.05% | 2 | 0.1 | 0.000 | -518 | -518 | -40 | 0.015 |
| q95.0 | 91 | top_0.1% | 2 | 0.1 | 0.000 | -424 | -424 | -33 | 0.015 |
| q95.0 | 91 | top_0.2% | 4 | 0.2 | 0.000 | -727 | -969 | -112 | 0.023 |
| q95.0 | 91 | top_0.5% | 7 | 0.3 | 0.000 | -242 | -340 | -65 | 0.039 |
| q95.0 | 91 | top_1% | 13 | 0.5 | 0.000 | -168 | -198 | -84 | 0.085 |
| q95.0 | 91 | top_2% | 24 | 0.9 | 0.042 | -3 | -4 | -3 | 0.155 |
| q95.0 | 91 | top_5% | 42 | 1.6 | 0.048 | 61 | 86 | 99 | 0.233 |
| q95.0 | 91 | top_100% | 180 | 6.9 | 0.067 | -34 | -80 | -234 | 0.589 |
| q97.5 | 58 | top_0.05% | 2 | 0.1 | 0.000 | -680 | -680 | -52 | 0.015 |
| q97.5 | 58 | top_0.1% | 2 | 0.1 | 0.000 | -518 | -518 | -40 | 0.015 |
| q97.5 | 58 | top_0.2% | 2 | 0.1 | 0.000 | -424 | -424 | -33 | 0.015 |
| q97.5 | 58 | top_0.5% | 6 | 0.2 | 0.000 | -126 | -151 | -29 | 0.039 |
| q97.5 | 58 | top_1% | 7 | 0.3 | 0.000 | -242 | -340 | -65 | 0.039 |
| q97.5 | 58 | top_2% | 14 | 0.5 | 0.000 | -62 | -72 | -33 | 0.093 |
| q97.5 | 58 | top_5% | 32 | 1.2 | 0.094 | 13 | 18 | 16 | 0.186 |
| q97.5 | 58 | top_100% | 115 | 4.4 | 0.078 | -122 | -255 | -540 | 0.426 |
| q99.0 | 39 | top_0.05% | 2 | 0.1 | 0.000 | -680 | -680 | -52 | 0.015 |
| q99.0 | 39 | top_0.1% | 2 | 0.1 | 0.000 | -518 | -518 | -40 | 0.015 |
| q99.0 | 39 | top_0.2% | 2 | 0.1 | 0.000 | -424 | -424 | -33 | 0.015 |
| q99.0 | 39 | top_0.5% | 4 | 0.2 | 0.000 | -727 | -969 | -112 | 0.023 |
| q99.0 | 39 | top_1% | 6 | 0.2 | 0.000 | -505 | -606 | -117 | 0.039 |
| q99.0 | 39 | top_2% | 7 | 0.3 | 0.000 | -242 | -340 | -65 | 0.039 |
| q99.0 | 39 | top_5% | 19 | 0.7 | 0.053 | 5 | 6 | 4 | 0.124 |
| q99.0 | 39 | top_100% | 72 | 2.8 | 0.083 | -23 | -43 | -63 | 0.295 |

**E6**

| gate pct | sessions qualified | tier | n takes | takes/wk | precision | $/trade | $/traded-day | $/week | frac days traded |
|---|---|---|---|---|---|---|---|---|---|
| q0.0 | 384 | top_0.05% | 5 | 0.2 | 0.000 | -325 | -542 | -62 | 0.023 |
| q0.0 | 384 | top_0.1% | 7 | 0.3 | 0.000 | -498 | -1162 | -134 | 0.023 |
| q0.0 | 384 | top_0.2% | 10 | 0.4 | 0.200 | -84 | -279 | -32 | 0.023 |
| q0.0 | 384 | top_0.5% | 23 | 0.9 | 0.000 | 21 | 55 | 19 | 0.070 |
| q0.0 | 384 | top_1% | 45 | 1.7 | 0.044 | -284 | -711 | -492 | 0.141 |
| q0.0 | 384 | top_2% | 70 | 2.7 | 0.100 | 24 | 51 | 64 | 0.258 |
| q0.0 | 384 | top_5% | 196 | 7.5 | 0.076 | -41 | -120 | -313 | 0.531 |
| q0.0 | 384 | top_100% | 1716 | 66.0 | 0.066 | -16 | -220 | -1081 | 1.000 |
| q50.0 | 377 | top_0.05% | 4 | 0.2 | 0.000 | 47 | 62 | 7 | 0.023 |
| q50.0 | 377 | top_0.1% | 7 | 0.3 | 0.000 | -498 | -1162 | -134 | 0.023 |
| q50.0 | 377 | top_0.2% | 9 | 0.3 | 0.222 | -57 | -171 | -20 | 0.023 |
| q50.0 | 377 | top_0.5% | 22 | 0.8 | 0.045 | 32 | 79 | 27 | 0.070 |
| q50.0 | 377 | top_1% | 42 | 1.6 | 0.048 | -277 | -727 | -448 | 0.125 |
| q50.0 | 377 | top_2% | 65 | 2.5 | 0.092 | 45 | 94 | 112 | 0.242 |
| q50.0 | 377 | top_5% | 187 | 7.2 | 0.080 | -82 | -232 | -589 | 0.516 |
| q50.0 | 377 | top_100% | 1516 | 58.3 | 0.073 | -8 | -93 | -459 | 1.000 |
| q70.0 | 340 | top_0.05% | 4 | 0.2 | 0.000 | 47 | 62 | 7 | 0.023 |
| q70.0 | 340 | top_0.1% | 6 | 0.2 | 0.000 | -426 | -852 | -98 | 0.023 |
| q70.0 | 340 | top_0.2% | 8 | 0.3 | 0.125 | -329 | -878 | -101 | 0.023 |
| q70.0 | 340 | top_0.5% | 17 | 0.7 | 0.000 | 209 | 507 | 136 | 0.055 |
| q70.0 | 340 | top_1% | 37 | 1.4 | 0.054 | -149 | -394 | -212 | 0.109 |
| q70.0 | 340 | top_2% | 55 | 2.1 | 0.091 | -56 | -129 | -119 | 0.188 |
| q70.0 | 340 | top_5% | 162 | 6.2 | 0.080 | -19 | -56 | -120 | 0.438 |
| q70.0 | 340 | top_100% | 1212 | 46.6 | 0.075 | -30 | -288 | -1417 | 1.000 |
| q80.0 | 297 | top_0.05% | 3 | 0.1 | 0.000 | 372 | 558 | 43 | 0.016 |
| q80.0 | 297 | top_0.1% | 7 | 0.3 | 0.000 | -498 | -1162 | -134 | 0.023 |
| q80.0 | 297 | top_0.2% | 8 | 0.3 | 0.125 | -263 | -701 | -81 | 0.023 |
| q80.0 | 297 | top_0.5% | 16 | 0.6 | 0.000 | 252 | 672 | 155 | 0.047 |
| q80.0 | 297 | top_1% | 31 | 1.2 | 0.000 | -161 | -500 | -192 | 0.078 |
| q80.0 | 297 | top_2% | 50 | 1.9 | 0.060 | -69 | -165 | -133 | 0.164 |
| q80.0 | 297 | top_5% | 123 | 4.7 | 0.098 | 17 | 43 | 79 | 0.375 |
| q80.0 | 297 | top_100% | 956 | 36.8 | 0.079 | -36 | -273 | -1311 | 0.977 |
| q90.0 | 187 | top_0.05% | 1 | 0.0 | 0.000 | 695 | 695 | 27 | 0.008 |
| q90.0 | 187 | top_0.1% | 4 | 0.2 | 0.000 | 47 | 62 | 7 | 0.023 |
| q90.0 | 187 | top_0.2% | 7 | 0.3 | 0.000 | -498 | -1162 | -134 | 0.023 |
| q90.0 | 187 | top_0.5% | 9 | 0.3 | 0.222 | -57 | -171 | -20 | 0.023 |
| q90.0 | 187 | top_1% | 17 | 0.7 | 0.000 | 194 | 472 | 127 | 0.055 |
| q90.0 | 187 | top_2% | 35 | 1.3 | 0.057 | -142 | -414 | -191 | 0.094 |
| q90.0 | 187 | top_5% | 65 | 2.5 | 0.092 | -26 | -57 | -66 | 0.234 |
| q90.0 | 187 | top_100% | 524 | 20.2 | 0.063 | -105 | -538 | -2111 | 0.797 |
| q95.0 | 111 | top_0.05% | 1 | 0.0 | 0.000 | 695 | 695 | 27 | 0.008 |
| q95.0 | 111 | top_0.1% | 1 | 0.0 | 0.000 | 695 | 695 | 27 | 0.008 |
| q95.0 | 111 | top_0.2% | 4 | 0.2 | 0.000 | 47 | 62 | 7 | 0.023 |
| q95.0 | 111 | top_0.5% | 7 | 0.3 | 0.000 | -498 | -1162 | -134 | 0.023 |
| q95.0 | 111 | top_1% | 10 | 0.4 | 0.200 | -84 | -279 | -32 | 0.023 |
| q95.0 | 111 | top_2% | 19 | 0.7 | 0.000 | 49 | 132 | 36 | 0.055 |
| q95.0 | 111 | top_5% | 45 | 1.7 | 0.067 | -237 | -592 | -410 | 0.141 |
| q95.0 | 111 | top_100% | 285 | 11.0 | 0.084 | -52 | -226 | -573 | 0.516 |
| q97.5 | 61 | top_0.05% | 1 | 0.0 | 0.000 | -155 | -155 | -6 | 0.008 |
| q97.5 | 61 | top_0.1% | 1 | 0.0 | 0.000 | 695 | 695 | 27 | 0.008 |
| q97.5 | 61 | top_0.2% | 1 | 0.0 | 0.000 | 695 | 695 | 27 | 0.008 |
| q97.5 | 61 | top_0.5% | 7 | 0.3 | 0.000 | -498 | -1162 | -134 | 0.023 |
| q97.5 | 61 | top_1% | 8 | 0.3 | 0.125 | -263 | -701 | -81 | 0.023 |
| q97.5 | 61 | top_2% | 12 | 0.5 | 0.167 | 202 | 607 | 93 | 0.031 |
| q97.5 | 61 | top_5% | 28 | 1.1 | 0.000 | -145 | -405 | -156 | 0.078 |
| q97.5 | 61 | top_100% | 179 | 6.9 | 0.078 | -132 | -539 | -912 | 0.344 |
| q99.0 | 27 | top_0.05% | 1 | 0.0 | 0.000 | -930 | -930 | -36 | 0.008 |
| q99.0 | 27 | top_0.1% | 1 | 0.0 | 0.000 | -155 | -155 | -6 | 0.008 |
| q99.0 | 27 | top_0.2% | 1 | 0.0 | 0.000 | -155 | -155 | -6 | 0.008 |
| q99.0 | 27 | top_0.5% | 1 | 0.0 | 0.000 | 695 | 695 | 27 | 0.008 |
| q99.0 | 27 | top_1% | 4 | 0.2 | 0.000 | 47 | 62 | 7 | 0.023 |
| q99.0 | 27 | top_2% | 5 | 0.2 | 0.000 | -42 | -71 | -8 | 0.023 |
| q99.0 | 27 | top_5% | 8 | 0.3 | 0.250 | 229 | 610 | 70 | 0.023 |
| q99.0 | 27 | top_100% | 66 | 2.5 | 0.061 | -251 | -919 | -636 | 0.141 |

**E8_GATE_2025H1**

| gate pct | sessions qualified | tier | n takes | takes/wk | precision | $/trade | $/traded-day | $/week | frac days traded |
|---|---|---|---|---|---|---|---|---|---|
| q0.0 | 381 | top_0.05% | 5 | 0.2 | 0.000 | -332 | -554 | -62 | 0.024 |
| q0.0 | 381 | top_0.1% | 5 | 0.2 | 0.000 | -132 | -166 | -25 | 0.032 |
| q0.0 | 381 | top_0.2% | 12 | 0.4 | 0.000 | -379 | -650 | -168 | 0.055 |
| q0.0 | 381 | top_0.5% | 29 | 1.1 | 0.103 | 234 | 399 | 251 | 0.134 |
| q0.0 | 381 | top_1% | 49 | 1.8 | 0.102 | 276 | 423 | 501 | 0.252 |
| q0.0 | 381 | top_2% | 91 | 3.4 | 0.099 | 98 | 190 | 331 | 0.370 |
| q0.0 | 381 | top_5% | 170 | 6.3 | 0.082 | 153 | 407 | 964 | 0.504 |
| q0.0 | 381 | top_100% | 2030 | 75.2 | 0.074 | -55 | -880 | -4138 | 1.000 |
| q50.0 | 372 | top_0.05% | 4 | 0.1 | 0.000 | -508 | -1016 | -75 | 0.016 |
| q50.0 | 372 | top_0.1% | 4 | 0.1 | 0.000 | -174 | -232 | -26 | 0.024 |
| q50.0 | 372 | top_0.2% | 8 | 0.3 | 0.000 | -175 | -280 | -52 | 0.039 |
| q50.0 | 372 | top_0.5% | 26 | 1.0 | 0.077 | -90 | -167 | -87 | 0.110 |
| q50.0 | 372 | top_1% | 49 | 1.8 | 0.122 | 213 | 336 | 386 | 0.244 |
| q50.0 | 372 | top_2% | 86 | 3.2 | 0.093 | 27 | 54 | 87 | 0.346 |
| q50.0 | 372 | top_5% | 164 | 6.1 | 0.079 | 33 | 85 | 199 | 0.496 |
| q50.0 | 372 | top_100% | 1797 | 66.6 | 0.075 | -77 | -1091 | -5131 | 1.000 |
| q70.0 | 340 | top_0.05% | 3 | 0.1 | 0.000 | -534 | -801 | -59 | 0.016 |
| q70.0 | 340 | top_0.1% | 4 | 0.1 | 0.000 | -174 | -232 | -26 | 0.024 |
| q70.0 | 340 | top_0.2% | 5 | 0.2 | 0.200 | 105 | 105 | 19 | 0.039 |
| q70.0 | 340 | top_0.5% | 21 | 0.8 | 0.000 | -156 | -298 | -121 | 0.087 |
| q70.0 | 340 | top_1% | 40 | 1.5 | 0.100 | 145 | 223 | 215 | 0.205 |
| q70.0 | 340 | top_2% | 71 | 2.6 | 0.085 | 126 | 248 | 331 | 0.283 |
| q70.0 | 340 | top_5% | 144 | 5.3 | 0.076 | -84 | -223 | -446 | 0.425 |
| q70.0 | 340 | top_100% | 1309 | 48.5 | 0.074 | -47 | -481 | -2264 | 1.000 |
| q80.0 | 272 | top_0.05% | 2 | 0.1 | 0.000 | -336 | -672 | -25 | 0.008 |
| q80.0 | 272 | top_0.1% | 4 | 0.1 | 0.000 | -174 | -232 | -26 | 0.024 |
| q80.0 | 272 | top_0.2% | 5 | 0.2 | 0.000 | -75 | -94 | -14 | 0.032 |
| q80.0 | 272 | top_0.5% | 17 | 0.6 | 0.000 | -90 | -169 | -56 | 0.071 |
| q80.0 | 272 | top_1% | 31 | 1.1 | 0.097 | 250 | 408 | 287 | 0.150 |
| q80.0 | 272 | top_2% | 51 | 1.9 | 0.098 | 329 | 508 | 621 | 0.260 |
| q80.0 | 272 | top_5% | 120 | 4.4 | 0.083 | -47 | -108 | -209 | 0.409 |
| q80.0 | 272 | top_100% | 964 | 35.7 | 0.081 | -102 | -870 | -3641 | 0.890 |
| q90.0 | 167 | top_0.05% | 2 | 0.1 | 0.000 | -336 | -672 | -25 | 0.008 |
| q90.0 | 167 | top_0.1% | 2 | 0.1 | 0.000 | -336 | -672 | -25 | 0.008 |
| q90.0 | 167 | top_0.2% | 4 | 0.1 | 0.000 | -174 | -232 | -26 | 0.024 |
| q90.0 | 167 | top_0.5% | 7 | 0.3 | 0.000 | -284 | -397 | -74 | 0.039 |
| q90.0 | 167 | top_1% | 18 | 0.7 | 0.000 | -138 | -275 | -92 | 0.071 |
| q90.0 | 167 | top_2% | 33 | 1.2 | 0.091 | 237 | 372 | 290 | 0.165 |
| q90.0 | 167 | top_5% | 74 | 2.7 | 0.081 | 76 | 141 | 209 | 0.315 |
| q90.0 | 167 | top_100% | 500 | 18.5 | 0.078 | -144 | -784 | -2671 | 0.724 |
| q95.0 | 102 | top_0.05% | 1 | 0.0 | 0.000 | 82 | 82 | 3 | 0.008 |
| q95.0 | 102 | top_0.1% | 2 | 0.1 | 0.000 | -336 | -672 | -25 | 0.008 |
| q95.0 | 102 | top_0.2% | 4 | 0.1 | 0.000 | -508 | -1016 | -75 | 0.016 |
| q95.0 | 102 | top_0.5% | 5 | 0.2 | 0.000 | 148 | 184 | 27 | 0.032 |
| q95.0 | 102 | top_1% | 11 | 0.4 | 0.000 | -328 | -515 | -134 | 0.055 |
| q95.0 | 102 | top_2% | 22 | 0.8 | 0.045 | -129 | -259 | -105 | 0.087 |
| q95.0 | 102 | top_5% | 50 | 1.9 | 0.100 | 238 | 371 | 440 | 0.252 |
| q95.0 | 102 | top_100% | 280 | 10.4 | 0.068 | -48 | -211 | -500 | 0.504 |
| q97.5 | 69 | top_0.05% | 1 | 0.0 | 0.000 | 201 | 201 | 7 | 0.008 |
| q97.5 | 69 | top_0.1% | 2 | 0.1 | 0.000 | -336 | -672 | -25 | 0.008 |
| q97.5 | 69 | top_0.2% | 2 | 0.1 | 0.000 | -336 | -672 | -25 | 0.008 |
| q97.5 | 69 | top_0.5% | 4 | 0.1 | 0.000 | -174 | -232 | -26 | 0.024 |
| q97.5 | 69 | top_1% | 4 | 0.1 | 0.250 | 364 | 364 | 54 | 0.032 |
| q97.5 | 69 | top_2% | 14 | 0.5 | 0.000 | -181 | -317 | -94 | 0.063 |
| q97.5 | 69 | top_5% | 34 | 1.3 | 0.088 | 234 | 379 | 295 | 0.165 |
| q97.5 | 69 | top_100% | 214 | 7.9 | 0.061 | -142 | -597 | -1129 | 0.402 |
| q99.0 | 38 | top_0.05% | 1 | 0.0 | 0.000 | 251 | 251 | 9 | 0.008 |
| q99.0 | 38 | top_0.1% | 1 | 0.0 | 0.000 | 201 | 201 | 7 | 0.008 |
| q99.0 | 38 | top_0.2% | 2 | 0.1 | 0.000 | -336 | -672 | -25 | 0.008 |
| q99.0 | 38 | top_0.5% | 3 | 0.1 | 0.000 | -534 | -801 | -59 | 0.016 |
| q99.0 | 38 | top_1% | 4 | 0.1 | 0.000 | -174 | -232 | -26 | 0.024 |
| q99.0 | 38 | top_2% | 4 | 0.1 | 0.250 | 364 | 364 | 54 | 0.032 |
| q99.0 | 38 | top_5% | 17 | 0.6 | 0.000 | 10 | 21 | 6 | 0.063 |
| q99.0 | 38 | top_100% | 107 | 4.0 | 0.056 | -130 | -435 | -516 | 0.252 |

### 4.2 preday_forecaster

**E3**

| gate pct | sessions qualified | tier | n takes | takes/wk | precision | $/trade | $/traded-day | $/week | frac days traded |
|---|---|---|---|---|---|---|---|---|---|
| q0.0 | 390 | top_0.05% | 8 | 0.3 | 0.000 | -127 | -145 | -38 | 0.054 |
| q0.0 | 390 | top_0.1% | 17 | 0.6 | 0.000 | -165 | -216 | -104 | 0.100 |
| q0.0 | 390 | top_0.2% | 26 | 1.0 | 0.077 | 22 | 30 | 21 | 0.146 |
| q0.0 | 390 | top_0.5% | 42 | 1.6 | 0.119 | 300 | 420 | 467 | 0.231 |
| q0.0 | 390 | top_1% | 79 | 2.9 | 0.101 | 144 | 219 | 423 | 0.400 |
| q0.0 | 390 | top_2% | 149 | 5.5 | 0.067 | 11 | 21 | 62 | 0.615 |
| q0.0 | 390 | top_5% | 295 | 10.9 | 0.078 | -45 | -118 | -487 | 0.854 |
| q0.0 | 390 | top_100% | 1691 | 62.6 | 0.054 | -74 | -957 | -4606 | 1.000 |
| q50.0 | 231 | top_0.05% | 2 | 0.1 | 0.000 | 239 | 239 | 18 | 0.015 |
| q50.0 | 231 | top_0.1% | 6 | 0.2 | 0.000 | -11 | -11 | -2 | 0.046 |
| q50.0 | 231 | top_0.2% | 14 | 0.5 | 0.071 | 142 | 199 | 74 | 0.077 |
| q50.0 | 231 | top_0.5% | 24 | 0.9 | 0.125 | 168 | 224 | 149 | 0.139 |
| q50.0 | 231 | top_1% | 45 | 1.7 | 0.067 | 84 | 111 | 140 | 0.262 |
| q50.0 | 231 | top_2% | 85 | 3.1 | 0.047 | 25 | 40 | 78 | 0.408 |
| q50.0 | 231 | top_5% | 162 | 6.0 | 0.086 | 117 | 248 | 699 | 0.585 |
| q50.0 | 231 | top_100% | 956 | 35.4 | 0.061 | -61 | -524 | -2174 | 0.862 |
| q70.0 | 145 | top_0.05% | 3 | 0.1 | 0.000 | -138 | -138 | -15 | 0.023 |
| q70.0 | 145 | top_0.1% | 6 | 0.2 | 0.000 | -115 | -138 | -26 | 0.038 |
| q70.0 | 145 | top_0.2% | 11 | 0.4 | 0.000 | 55 | 68 | 22 | 0.069 |
| q70.0 | 145 | top_0.5% | 17 | 0.6 | 0.059 | -26 | -31 | -16 | 0.108 |
| q70.0 | 145 | top_1% | 28 | 1.0 | 0.107 | 201 | 256 | 208 | 0.169 |
| q70.0 | 145 | top_2% | 59 | 2.2 | 0.085 | 186 | 296 | 406 | 0.285 |
| q70.0 | 145 | top_5% | 107 | 4.0 | 0.065 | 1 | 1 | 3 | 0.454 |
| q70.0 | 145 | top_100% | 580 | 21.5 | 0.048 | -92 | -533 | -1975 | 0.769 |
| q80.0 | 87 | top_0.05% | 1 | 0.0 | 0.000 | 645 | 645 | 24 | 0.008 |
| q80.0 | 87 | top_0.1% | 2 | 0.1 | 0.000 | 139 | 139 | 10 | 0.015 |
| q80.0 | 87 | top_0.2% | 4 | 0.1 | 0.000 | -18 | -35 | -3 | 0.015 |
| q80.0 | 87 | top_0.5% | 9 | 0.3 | 0.111 | 94 | 140 | 31 | 0.046 |
| q80.0 | 87 | top_1% | 11 | 0.4 | 0.182 | 448 | 617 | 183 | 0.061 |
| q80.0 | 87 | top_2% | 31 | 1.1 | 0.097 | 251 | 338 | 288 | 0.177 |
| q80.0 | 87 | top_5% | 53 | 2.0 | 0.075 | 90 | 129 | 177 | 0.285 |
| q80.0 | 87 | top_100% | 357 | 13.2 | 0.034 | -132 | -684 | -1748 | 0.531 |
| q90.0 | 87 | top_0.05% | 1 | 0.0 | 0.000 | 645 | 645 | 24 | 0.008 |
| q90.0 | 87 | top_0.1% | 2 | 0.1 | 0.000 | 139 | 139 | 10 | 0.015 |
| q90.0 | 87 | top_0.2% | 4 | 0.1 | 0.000 | -18 | -35 | -3 | 0.015 |
| q90.0 | 87 | top_0.5% | 9 | 0.3 | 0.111 | 94 | 140 | 31 | 0.046 |
| q90.0 | 87 | top_1% | 11 | 0.4 | 0.182 | 448 | 617 | 183 | 0.061 |
| q90.0 | 87 | top_2% | 31 | 1.1 | 0.097 | 251 | 338 | 288 | 0.177 |
| q90.0 | 87 | top_5% | 53 | 2.0 | 0.075 | 90 | 129 | 177 | 0.285 |
| q90.0 | 87 | top_100% | 357 | 13.2 | 0.034 | -132 | -684 | -1748 | 0.531 |
| q95.0 | 87 | top_0.05% | 1 | 0.0 | 0.000 | 645 | 645 | 24 | 0.008 |
| q95.0 | 87 | top_0.1% | 2 | 0.1 | 0.000 | 139 | 139 | 10 | 0.015 |
| q95.0 | 87 | top_0.2% | 4 | 0.1 | 0.000 | -18 | -35 | -3 | 0.015 |
| q95.0 | 87 | top_0.5% | 9 | 0.3 | 0.111 | 94 | 140 | 31 | 0.046 |
| q95.0 | 87 | top_1% | 11 | 0.4 | 0.182 | 448 | 617 | 183 | 0.061 |
| q95.0 | 87 | top_2% | 31 | 1.1 | 0.097 | 251 | 338 | 288 | 0.177 |
| q95.0 | 87 | top_5% | 53 | 2.0 | 0.075 | 90 | 129 | 177 | 0.285 |
| q95.0 | 87 | top_100% | 357 | 13.2 | 0.034 | -132 | -684 | -1748 | 0.531 |

**E4**

| gate pct | sessions qualified | tier | n takes | takes/wk | precision | $/trade | $/traded-day | $/week | frac days traded |
|---|---|---|---|---|---|---|---|---|---|
| q0.0 | 385 | top_0.05% | 8 | 0.3 | 0.125 | -160 | -213 | -49 | 0.046 |
| q0.0 | 385 | top_0.1% | 12 | 0.5 | 0.083 | -431 | -647 | -199 | 0.062 |
| q0.0 | 385 | top_0.2% | 24 | 0.9 | 0.083 | -444 | -665 | -409 | 0.124 |
| q0.0 | 385 | top_0.5% | 42 | 1.6 | 0.071 | -206 | -299 | -333 | 0.225 |
| q0.0 | 385 | top_1% | 59 | 2.3 | 0.152 | 41 | 66 | 94 | 0.287 |
| q0.0 | 385 | top_2% | 98 | 3.8 | 0.102 | 58 | 97 | 217 | 0.450 |
| q0.0 | 385 | top_5% | 180 | 6.9 | 0.117 | 129 | 260 | 890 | 0.690 |
| q0.0 | 385 | top_100% | 1550 | 59.6 | 0.054 | -31 | -372 | -1845 | 1.000 |
| q50.0 | 193 | top_0.05% | 2 | 0.1 | 0.000 | -5 | -5 | -0 | 0.015 |
| q50.0 | 193 | top_0.1% | 4 | 0.2 | 0.000 | -936 | -1248 | -144 | 0.023 |
| q50.0 | 193 | top_0.2% | 12 | 0.5 | 0.000 | -810 | -1215 | -374 | 0.062 |
| q50.0 | 193 | top_0.5% | 17 | 0.7 | 0.059 | -276 | -426 | -180 | 0.085 |
| q50.0 | 193 | top_1% | 26 | 1.0 | 0.115 | 18 | 26 | 18 | 0.140 |
| q50.0 | 193 | top_2% | 45 | 1.7 | 0.133 | 222 | 322 | 384 | 0.240 |
| q50.0 | 193 | top_5% | 83 | 3.2 | 0.096 | 135 | 208 | 432 | 0.419 |
| q50.0 | 193 | top_100% | 788 | 30.3 | 0.052 | -56 | -395 | -1687 | 0.861 |
| q70.0 | 116 | top_0.05% | 1 | 0.0 | 0.000 | -955 | -955 | -37 | 0.008 |
| q70.0 | 116 | top_0.1% | 3 | 0.1 | 0.000 | -259 | -389 | -30 | 0.015 |
| q70.0 | 116 | top_0.2% | 5 | 0.2 | 0.000 | -722 | -1204 | -139 | 0.023 |
| q70.0 | 116 | top_0.5% | 9 | 0.3 | 0.111 | -341 | -512 | -118 | 0.046 |
| q70.0 | 116 | top_1% | 18 | 0.7 | 0.056 | -107 | -161 | -74 | 0.093 |
| q70.0 | 116 | top_2% | 24 | 0.9 | 0.083 | 44 | 62 | 40 | 0.132 |
| q70.0 | 116 | top_5% | 44 | 1.7 | 0.136 | 491 | 617 | 831 | 0.271 |
| q70.0 | 116 | top_100% | 468 | 18.0 | 0.049 | -39 | -224 | -697 | 0.628 |
| q80.0 | 77 | top_0.05% | 1 | 0.0 | 0.000 | -955 | -955 | -37 | 0.008 |
| q80.0 | 77 | top_0.1% | 1 | 0.0 | 0.000 | -955 | -955 | -37 | 0.008 |
| q80.0 | 77 | top_0.2% | 4 | 0.2 | 0.000 | -936 | -1872 | -144 | 0.015 |
| q80.0 | 77 | top_0.5% | 4 | 0.2 | 0.250 | 129 | 172 | 20 | 0.023 |
| q80.0 | 77 | top_1% | 8 | 0.3 | 0.125 | 440 | 502 | 135 | 0.054 |
| q80.0 | 77 | top_2% | 11 | 0.4 | 0.091 | 331 | 331 | 140 | 0.085 |
| q80.0 | 77 | top_5% | 29 | 1.1 | 0.069 | 212 | 245 | 236 | 0.194 |
| q80.0 | 77 | top_100% | 300 | 11.5 | 0.053 | -27 | -132 | -315 | 0.481 |
| q90.0 | 39 | top_0.05% | 1 | 0.0 | 0.000 | -955 | -955 | -37 | 0.008 |
| q90.0 | 39 | top_0.1% | 1 | 0.0 | 0.000 | -955 | -955 | -37 | 0.008 |
| q90.0 | 39 | top_0.2% | 1 | 0.0 | 0.000 | -955 | -955 | -37 | 0.008 |
| q90.0 | 39 | top_0.5% | 4 | 0.2 | 0.000 | -21 | -21 | -3 | 0.031 |
| q90.0 | 39 | top_1% | 4 | 0.2 | 0.000 | 436 | 436 | 67 | 0.031 |
| q90.0 | 39 | top_2% | 8 | 0.3 | 0.000 | 124 | 124 | 38 | 0.062 |
| q90.0 | 39 | top_5% | 26 | 1.0 | 0.077 | 309 | 402 | 309 | 0.155 |
| q90.0 | 39 | top_100% | 147 | 5.7 | 0.048 | -7 | -26 | -38 | 0.287 |
| q95.0 | 20 | top_0.05% | 1 | 0.0 | 0.000 | -955 | -955 | -37 | 0.008 |
| q95.0 | 20 | top_0.1% | 1 | 0.0 | 0.000 | -955 | -955 | -37 | 0.008 |
| q95.0 | 20 | top_0.2% | 1 | 0.0 | 0.000 | -955 | -955 | -37 | 0.008 |
| q95.0 | 20 | top_0.5% | 2 | 0.1 | 0.000 | 61 | 61 | 5 | 0.015 |
| q95.0 | 20 | top_1% | 3 | 0.1 | 0.000 | 891 | 891 | 103 | 0.023 |
| q95.0 | 20 | top_2% | 4 | 0.2 | 0.000 | 867 | 867 | 133 | 0.031 |
| q95.0 | 20 | top_5% | 16 | 0.6 | 0.062 | 400 | 533 | 246 | 0.093 |
| q95.0 | 20 | top_100% | 75 | 2.9 | 0.027 | 22 | 91 | 63 | 0.140 |

**E5**

| gate pct | sessions qualified | tier | n takes | takes/wk | precision | $/trade | $/traded-day | $/week | frac days traded |
|---|---|---|---|---|---|---|---|---|---|
| q0.0 | 387 | top_0.05% | 6 | 0.2 | 0.000 | -505 | -606 | -117 | 0.039 |
| q0.0 | 387 | top_0.1% | 7 | 0.3 | 0.000 | -242 | -340 | -65 | 0.039 |
| q0.0 | 387 | top_0.2% | 14 | 0.5 | 0.000 | -61 | -71 | -33 | 0.093 |
| q0.0 | 387 | top_0.5% | 33 | 1.3 | 0.091 | 142 | 195 | 180 | 0.186 |
| q0.0 | 387 | top_1% | 55 | 2.1 | 0.091 | -22 | -31 | -48 | 0.310 |
| q0.0 | 387 | top_2% | 80 | 3.1 | 0.113 | -55 | -83 | -170 | 0.411 |
| q0.0 | 387 | top_5% | 134 | 5.2 | 0.119 | -36 | -64 | -187 | 0.589 |
| q0.0 | 387 | top_100% | 1517 | 58.3 | 0.056 | -23 | -267 | -1326 | 1.000 |
| q50.0 | 194 | top_0.05% | 2 | 0.1 | 0.000 | -930 | -1860 | -72 | 0.008 |
| q50.0 | 194 | top_0.1% | 2 | 0.1 | 0.000 | -930 | -1860 | -72 | 0.008 |
| q50.0 | 194 | top_0.2% | 6 | 0.2 | 0.000 | -378 | -454 | -87 | 0.039 |
| q50.0 | 194 | top_0.5% | 15 | 0.6 | 0.067 | 82 | 103 | 48 | 0.093 |
| q50.0 | 194 | top_1% | 25 | 1.0 | 0.160 | 297 | 338 | 286 | 0.171 |
| q50.0 | 194 | top_2% | 38 | 1.5 | 0.132 | 131 | 185 | 192 | 0.209 |
| q50.0 | 194 | top_5% | 61 | 2.3 | 0.164 | 205 | 271 | 480 | 0.357 |
| q50.0 | 194 | top_100% | 742 | 28.5 | 0.058 | -1 | -6 | -25 | 0.868 |
| q70.0 | 116 | top_0.05% | 2 | 0.1 | 0.000 | -930 | -1860 | -72 | 0.008 |
| q70.0 | 116 | top_0.1% | 2 | 0.1 | 0.000 | -930 | -1860 | -72 | 0.008 |
| q70.0 | 116 | top_0.2% | 4 | 0.2 | 0.000 | -492 | -657 | -76 | 0.023 |
| q70.0 | 116 | top_0.5% | 11 | 0.4 | 0.091 | 12 | 15 | 5 | 0.070 |
| q70.0 | 116 | top_1% | 21 | 0.8 | 0.191 | 244 | 302 | 197 | 0.132 |
| q70.0 | 116 | top_2% | 26 | 1.0 | 0.154 | 245 | 304 | 245 | 0.163 |
| q70.0 | 116 | top_5% | 43 | 1.7 | 0.140 | 35 | 50 | 58 | 0.233 |
| q70.0 | 116 | top_100% | 457 | 17.6 | 0.055 | -2 | -8 | -27 | 0.651 |
| q80.0 | 78 | top_0.05% | 2 | 0.1 | 0.000 | -55 | -55 | -4 | 0.015 |
| q80.0 | 78 | top_0.1% | 3 | 0.1 | 0.000 | -313 | -313 | -36 | 0.023 |
| q80.0 | 78 | top_0.2% | 6 | 0.2 | 0.167 | 470 | 470 | 108 | 0.046 |
| q80.0 | 78 | top_0.5% | 7 | 0.3 | 0.143 | 329 | 329 | 89 | 0.054 |
| q80.0 | 78 | top_1% | 13 | 0.5 | 0.231 | 440 | 572 | 220 | 0.077 |
| q80.0 | 78 | top_2% | 17 | 0.7 | 0.235 | 441 | 499 | 288 | 0.116 |
| q80.0 | 78 | top_5% | 31 | 1.2 | 0.161 | 40 | 56 | 47 | 0.171 |
| q80.0 | 78 | top_100% | 312 | 12.0 | 0.064 | 6 | 29 | 72 | 0.512 |
| q90.0 | 39 | top_0.05% | 2 | 0.1 | 0.000 | -55 | -55 | -4 | 0.015 |
| q90.0 | 39 | top_0.1% | 2 | 0.1 | 0.000 | -55 | -55 | -4 | 0.015 |
| q90.0 | 39 | top_0.2% | 3 | 0.1 | 0.000 | -313 | -313 | -36 | 0.023 |
| q90.0 | 39 | top_0.5% | 5 | 0.2 | 0.000 | -35 | -35 | -7 | 0.039 |
| q90.0 | 39 | top_1% | 7 | 0.3 | 0.000 | -232 | -270 | -62 | 0.046 |
| q90.0 | 39 | top_2% | 14 | 0.5 | 0.214 | 90 | 114 | 48 | 0.085 |
| q90.0 | 39 | top_5% | 18 | 0.7 | 0.167 | 172 | 221 | 119 | 0.108 |
| q90.0 | 39 | top_100% | 167 | 6.4 | 0.060 | -52 | -223 | -335 | 0.302 |
| q95.0 | 20 | top_0.05% | 2 | 0.1 | 0.000 | -55 | -55 | -4 | 0.015 |
| q95.0 | 20 | top_0.1% | 2 | 0.1 | 0.000 | -55 | -55 | -4 | 0.015 |
| q95.0 | 20 | top_0.2% | 2 | 0.1 | 0.000 | -55 | -55 | -4 | 0.015 |
| q95.0 | 20 | top_0.5% | 3 | 0.1 | 0.000 | 212 | 212 | 24 | 0.023 |
| q95.0 | 20 | top_1% | 4 | 0.2 | 0.000 | 29 | 39 | 5 | 0.023 |
| q95.0 | 20 | top_2% | 5 | 0.2 | 0.000 | -200 | -333 | -38 | 0.023 |
| q95.0 | 20 | top_5% | 7 | 0.3 | 0.429 | 1041 | 1458 | 280 | 0.039 |
| q95.0 | 20 | top_100% | 91 | 3.5 | 0.066 | -73 | -331 | -255 | 0.155 |

**E6**

| gate pct | sessions qualified | tier | n takes | takes/wk | precision | $/trade | $/traded-day | $/week | frac days traded |
|---|---|---|---|---|---|---|---|---|---|
| q0.0 | 384 | top_0.05% | 5 | 0.2 | 0.000 | -325 | -542 | -62 | 0.023 |
| q0.0 | 384 | top_0.1% | 8 | 0.3 | 0.125 | -263 | -701 | -81 | 0.023 |
| q0.0 | 384 | top_0.2% | 11 | 0.4 | 0.182 | -37 | -135 | -16 | 0.023 |
| q0.0 | 384 | top_0.5% | 23 | 0.9 | 0.000 | 21 | 55 | 19 | 0.070 |
| q0.0 | 384 | top_1% | 46 | 1.8 | 0.043 | -320 | -818 | -566 | 0.141 |
| q0.0 | 384 | top_2% | 71 | 2.7 | 0.113 | 49 | 103 | 135 | 0.266 |
| q0.0 | 384 | top_5% | 196 | 7.5 | 0.076 | -40 | -116 | -303 | 0.531 |
| q0.0 | 384 | top_100% | 1717 | 66.0 | 0.070 | -8 | -107 | -525 | 1.000 |
| q50.0 | 194 | top_0.05% | 1 | 0.0 | 0.000 | -930 | -930 | -36 | 0.008 |
| q50.0 | 194 | top_0.1% | 4 | 0.2 | 0.250 | -352 | -704 | -54 | 0.016 |
| q50.0 | 194 | top_0.2% | 5 | 0.2 | 0.400 | 162 | 406 | 31 | 0.016 |
| q50.0 | 194 | top_0.5% | 11 | 0.4 | 0.000 | 335 | 738 | 142 | 0.039 |
| q50.0 | 194 | top_1% | 22 | 0.8 | 0.091 | 221 | 443 | 187 | 0.086 |
| q50.0 | 194 | top_2% | 28 | 1.1 | 0.107 | -40 | -80 | -43 | 0.109 |
| q50.0 | 194 | top_5% | 101 | 3.9 | 0.059 | -163 | -366 | -633 | 0.352 |
| q50.0 | 194 | top_100% | 874 | 33.6 | 0.068 | -40 | -303 | -1331 | 0.891 |
| q70.0 | 122 | top_0.05% | 3 | 0.1 | 0.000 | -930 | -2790 | -107 | 0.008 |
| q70.0 | 122 | top_0.1% | 3 | 0.1 | 0.000 | -930 | -1395 | -107 | 0.016 |
| q70.0 | 122 | top_0.2% | 4 | 0.2 | 0.250 | -352 | -704 | -54 | 0.016 |
| q70.0 | 122 | top_0.5% | 9 | 0.3 | 0.000 | 473 | 1418 | 164 | 0.023 |
| q70.0 | 122 | top_1% | 20 | 0.8 | 0.000 | -79 | -198 | -61 | 0.062 |
| q70.0 | 122 | top_2% | 22 | 0.8 | 0.045 | 14 | 28 | 12 | 0.086 |
| q70.0 | 122 | top_5% | 64 | 2.5 | 0.078 | -178 | -422 | -438 | 0.211 |
| q70.0 | 122 | top_100% | 583 | 22.4 | 0.077 | -37 | -248 | -830 | 0.680 |
| q80.0 | 87 | top_0.05% | 1 | 0.0 | 0.000 | -930 | -930 | -36 | 0.008 |
| q80.0 | 87 | top_0.1% | 3 | 0.1 | 0.000 | 32 | 98 | 4 | 0.008 |
| q80.0 | 87 | top_0.2% | 4 | 0.2 | 0.250 | -352 | -704 | -54 | 0.016 |
| q80.0 | 87 | top_0.5% | 5 | 0.2 | 0.400 | 162 | 406 | 31 | 0.016 |
| q80.0 | 87 | top_1% | 11 | 0.4 | 0.091 | 539 | 1186 | 228 | 0.039 |
| q80.0 | 87 | top_2% | 19 | 0.7 | 0.105 | 250 | 527 | 182 | 0.070 |
| q80.0 | 87 | top_5% | 37 | 1.4 | 0.135 | -11 | -26 | -15 | 0.117 |
| q80.0 | 87 | top_100% | 430 | 16.5 | 0.077 | -61 | -391 | -1009 | 0.523 |
| q90.0 | 39 | top_0.05% | 1 | 0.0 | 0.000 | -930 | -930 | -36 | 0.008 |
| q90.0 | 39 | top_0.1% | 2 | 0.1 | 0.500 | 645 | 1290 | 50 | 0.008 |
| q90.0 | 39 | top_0.2% | 3 | 0.1 | 0.333 | 120 | 360 | 14 | 0.008 |
| q90.0 | 39 | top_0.5% | 2 | 0.1 | 0.000 | 1201 | 2402 | 92 | 0.008 |
| q90.0 | 39 | top_1% | 10 | 0.4 | 0.000 | -5 | -12 | -2 | 0.031 |
| q90.0 | 39 | top_2% | 10 | 0.4 | 0.100 | 361 | 602 | 139 | 0.047 |
| q90.0 | 39 | top_5% | 16 | 0.6 | 0.062 | -93 | -187 | -57 | 0.062 |
| q90.0 | 39 | top_100% | 224 | 8.6 | 0.067 | -123 | -837 | -1062 | 0.258 |
| q95.0 | 37 | top_0.05% | 1 | 0.0 | 0.000 | -930 | -930 | -36 | 0.008 |
| q95.0 | 37 | top_0.1% | 2 | 0.1 | 0.500 | 645 | 1290 | 50 | 0.008 |
| q95.0 | 37 | top_0.2% | 3 | 0.1 | 0.333 | 120 | 360 | 14 | 0.008 |
| q95.0 | 37 | top_0.5% | 2 | 0.1 | 0.000 | 1201 | 2402 | 92 | 0.008 |
| q95.0 | 37 | top_1% | 10 | 0.4 | 0.000 | -5 | -12 | -2 | 0.031 |
| q95.0 | 37 | top_2% | 10 | 0.4 | 0.100 | 348 | 579 | 134 | 0.047 |
| q95.0 | 37 | top_5% | 16 | 0.6 | 0.062 | -99 | -198 | -61 | 0.062 |
| q95.0 | 37 | top_100% | 218 | 8.4 | 0.060 | -151 | -1059 | -1262 | 0.242 |

**E8_GATE_2025H1**

| gate pct | sessions qualified | tier | n takes | takes/wk | precision | $/trade | $/traded-day | $/week | frac days traded |
|---|---|---|---|---|---|---|---|---|---|
| q0.0 | 381 | top_0.05% | 5 | 0.2 | 0.000 | -332 | -554 | -62 | 0.024 |
| q0.0 | 381 | top_0.1% | 5 | 0.2 | 0.000 | -132 | -166 | -25 | 0.032 |
| q0.0 | 381 | top_0.2% | 12 | 0.4 | 0.000 | -379 | -650 | -168 | 0.055 |
| q0.0 | 381 | top_0.5% | 30 | 1.1 | 0.100 | 241 | 402 | 268 | 0.142 |
| q0.0 | 381 | top_1% | 50 | 1.9 | 0.100 | 292 | 457 | 542 | 0.252 |
| q0.0 | 381 | top_2% | 92 | 3.4 | 0.098 | 87 | 170 | 296 | 0.370 |
| q0.0 | 381 | top_5% | 170 | 6.3 | 0.082 | 143 | 380 | 902 | 0.504 |
| q0.0 | 381 | top_100% | 2030 | 75.2 | 0.067 | -60 | -964 | -4533 | 1.000 |
| q50.0 | 191 | top_0.05% | 2 | 0.1 | 0.000 | -336 | -672 | -25 | 0.008 |
| q50.0 | 191 | top_0.1% | 1 | 0.0 | 0.000 | 195 | 195 | 7 | 0.008 |
| q50.0 | 191 | top_0.2% | 1 | 0.0 | 0.000 | 195 | 195 | 7 | 0.008 |
| q50.0 | 191 | top_0.5% | 11 | 0.4 | 0.182 | 202 | 247 | 82 | 0.071 |
| q50.0 | 191 | top_1% | 20 | 0.7 | 0.150 | 215 | 269 | 159 | 0.126 |
| q50.0 | 191 | top_2% | 43 | 1.6 | 0.093 | 3 | 4 | 4 | 0.213 |
| q50.0 | 191 | top_5% | 81 | 3.0 | 0.086 | 3 | 6 | 9 | 0.331 |
| q50.0 | 191 | top_100% | 1003 | 37.1 | 0.070 | -68 | -614 | -2525 | 0.874 |
| q70.0 | 115 | top_0.05% | 2 | 0.1 | 0.000 | -336 | -672 | -25 | 0.008 |
| q70.0 | 115 | top_0.1% | 2 | 0.1 | 0.000 | -336 | -672 | -25 | 0.008 |
| q70.0 | 115 | top_0.2% | 1 | 0.0 | 0.000 | 195 | 195 | 7 | 0.008 |
| q70.0 | 115 | top_0.5% | 4 | 0.1 | 0.000 | 23 | 23 | 3 | 0.032 |
| q70.0 | 115 | top_1% | 11 | 0.4 | 0.182 | 429 | 472 | 175 | 0.079 |
| q70.0 | 115 | top_2% | 26 | 1.0 | 0.115 | -20 | -31 | -19 | 0.134 |
| q70.0 | 115 | top_5% | 46 | 1.7 | 0.130 | 254 | 433 | 433 | 0.213 |
| q70.0 | 115 | top_100% | 597 | 22.1 | 0.084 | -24 | -180 | -535 | 0.630 |
| q80.0 | 77 | top_0.05% | 2 | 0.1 | 0.000 | 370 | 370 | 27 | 0.016 |
| q80.0 | 77 | top_0.1% | 3 | 0.1 | 0.333 | 824 | 824 | 92 | 0.024 |
| q80.0 | 77 | top_0.2% | 4 | 0.1 | 0.250 | 732 | 732 | 109 | 0.032 |
| q80.0 | 77 | top_0.5% | 4 | 0.1 | 0.250 | 804 | 804 | 119 | 0.032 |
| q80.0 | 77 | top_1% | 7 | 0.3 | 0.286 | 695 | 695 | 180 | 0.055 |
| q80.0 | 77 | top_2% | 19 | 0.7 | 0.105 | -176 | -304 | -124 | 0.087 |
| q80.0 | 77 | top_5% | 27 | 1.0 | 0.148 | 305 | 457 | 305 | 0.142 |
| q80.0 | 77 | top_100% | 388 | 14.4 | 0.075 | -26 | -185 | -369 | 0.425 |
| q90.0 | 39 | top_0.05% | 2 | 0.1 | 0.000 | -930 | -1860 | -69 | 0.008 |
| q90.0 | 39 | top_0.1% | 3 | 0.1 | 0.333 | -109 | -164 | -12 | 0.016 |
| q90.0 | 39 | top_0.2% | 3 | 0.1 | 0.333 | -109 | -164 | -12 | 0.016 |
| q90.0 | 39 | top_0.5% | 4 | 0.1 | 0.000 | -333 | -444 | -49 | 0.024 |
| q90.0 | 39 | top_1% | 6 | 0.2 | 0.000 | -522 | -782 | -116 | 0.032 |
| q90.0 | 39 | top_2% | 7 | 0.3 | 0.143 | -85 | -100 | -22 | 0.047 |
| q90.0 | 39 | top_5% | 20 | 0.7 | 0.200 | -13 | -24 | -10 | 0.087 |
| q90.0 | 39 | top_100% | 200 | 7.4 | 0.065 | -66 | -428 | -491 | 0.244 |
| q95.0 | 20 | top_0.05% | 1 | 0.0 | 0.000 | 720 | 720 | 27 | 0.008 |
| q95.0 | 20 | top_0.1% | 1 | 0.0 | 0.000 | 720 | 720 | 27 | 0.008 |
| q95.0 | 20 | top_0.2% | 1 | 0.0 | 0.000 | 720 | 720 | 27 | 0.008 |
| q95.0 | 20 | top_0.5% | 1 | 0.0 | 0.000 | 720 | 720 | 27 | 0.008 |
| q95.0 | 20 | top_1% | 2 | 0.1 | 0.000 | -942 | -942 | -70 | 0.016 |
| q95.0 | 20 | top_2% | 4 | 0.1 | 0.250 | 214 | 214 | 32 | 0.032 |
| q95.0 | 20 | top_5% | 12 | 0.4 | 0.167 | 20 | 34 | 9 | 0.055 |
| q95.0 | 20 | top_100% | 99 | 3.7 | 0.020 | -72 | -444 | -263 | 0.126 |


---

## 5. AGREEMENT TIERS — three independent readers of the same second

`FULL_TF` = the full model with teacher features; `TEACHER` = the 18 teacher-evidence columns alone; `SEQ` = the raw event-stream cue block alone.  All three are walk-forward fits of the same D-021 winner head on the same rows.

**E3**

| rule | tier | n takes | takes/wk | precision [CI] | $/trade | $/week | $/session |
|---|---|---|---|---|---|---|---|
| 1of3_any | top_0.05% | 49 | 1.8 | 0.082 [0.007, 0.156] | -96 | -174 | -12 |
| 2of3 | top_0.05% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| 3of3 | top_0.05% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.05% | 8 | 0.3 | 0.000 [0.000, 0.000] | -127 | -38 | -3 |
| alone_TEACHER | top_0.05% | 15 | 0.6 | 0.067 [-0.081, 0.214] | -171 | -95 | -7 |
| alone_SEQ | top_0.05% | 30 | 1.1 | 0.133 [0.012, 0.255] | -40 | -44 | -3 |
| 1of3_any | top_0.1% | 80 | 3.0 | 0.075 [0.019, 0.131] | -110 | -326 | -23 |
| 2of3 | top_0.1% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| 3of3 | top_0.1% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.1% | 17 | 0.6 | 0.000 [0.000, 0.000] | -165 | -104 | -7 |
| alone_TEACHER | top_0.1% | 19 | 0.7 | 0.053 [-0.062, 0.168] | 47 | 33 | 2 |
| alone_SEQ | top_0.1% | 50 | 1.9 | 0.120 [0.031, 0.209] | -75 | -138 | -10 |
| 1of3_any | top_0.2% | 127 | 4.7 | 0.055 [0.017, 0.093] | -101 | -477 | -33 |
| 2of3 | top_0.2% | 3 | 0.1 | 0.333 [-2.490, 3.157] | 589 | 65 | 5 |
| 3of3 | top_0.2% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.2% | 26 | 1.0 | 0.077 [-0.014, 0.168] | 22 | 21 | 1 |
| alone_TEACHER | top_0.2% | 32 | 1.2 | 0.000 [0.000, 0.000] | -190 | -225 | -16 |
| alone_SEQ | top_0.2% | 81 | 3.0 | 0.099 [0.035, 0.163] | 5 | 14 | 1 |
| 1of3_any | top_0.5% | 200 | 7.4 | 0.095 [0.055, 0.135] | 44 | 329 | 23 |
| 2of3 | top_0.5% | 13 | 0.5 | 0.154 [-0.082, 0.390] | 1177 | 567 | 39 |
| 3of3 | top_0.5% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.5% | 42 | 1.6 | 0.119 [0.032, 0.206] | 300 | 467 | 32 |
| alone_TEACHER | top_0.5% | 58 | 2.1 | 0.052 [-0.008, 0.111] | -119 | -255 | -18 |
| alone_SEQ | top_0.5% | 131 | 4.9 | 0.115 [0.056, 0.173] | 41 | 197 | 14 |
| 1of3_any | top_1% | 292 | 10.8 | 0.099 [0.064, 0.135] | 88 | 953 | 66 |
| 2of3 | top_1% | 29 | 1.1 | 0.069 [-0.029, 0.167] | 183 | 197 | 14 |
| 3of3 | top_1% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_1% | 79 | 2.9 | 0.101 [0.032, 0.171] | 144 | 423 | 29 |
| alone_TEACHER | top_1% | 90 | 3.3 | 0.078 [0.023, 0.133] | 46 | 154 | 11 |
| alone_SEQ | top_1% | 183 | 6.8 | 0.104 [0.059, 0.148] | 95 | 641 | 44 |
| 1of3_any | top_2% | 473 | 17.5 | 0.083 [0.059, 0.106] | 43 | 755 | 52 |
| 2of3 | top_2% | 61 | 2.3 | 0.115 [0.036, 0.194] | -121 | -273 | -19 |
| 3of3 | top_2% | 4 | 0.1 | 0.000 [0.000, 0.000] | -930 | -138 | -10 |
| alone_FULL_TF | top_2% | 149 | 5.5 | 0.067 [0.019, 0.115] | 11 | 62 | 4 |
| alone_TEACHER | top_2% | 234 | 8.7 | 0.073 [0.039, 0.106] | 15 | 134 | 9 |
| alone_SEQ | top_2% | 263 | 9.7 | 0.095 [0.058, 0.132] | 62 | 603 | 42 |
| 1of3_any | top_5% | 791 | 29.3 | 0.062 [0.044, 0.080] | -63 | -1854 | -128 |
| 2of3 | top_5% | 211 | 7.8 | 0.109 [0.067, 0.151] | 6 | 50 | 3 |
| 3of3 | top_5% | 31 | 1.1 | 0.097 [-0.043, 0.237] | -242 | -278 | -19 |
| alone_FULL_TF | top_5% | 295 | 10.9 | 0.078 [0.050, 0.106] | -45 | -487 | -34 |
| alone_TEACHER | top_5% | 495 | 18.3 | 0.059 [0.036, 0.081] | -55 | -1003 | -69 |
| alone_SEQ | top_5% | 514 | 19.0 | 0.072 [0.048, 0.096] | -53 | -1002 | -69 |
| 1of3_any | top_10% | 997 | 36.9 | 0.053 [0.040, 0.067] | -92 | -3380 | -234 |
| 2of3 | top_10% | 391 | 14.5 | 0.077 [0.050, 0.103] | -100 | -1454 | -101 |
| 3of3 | top_10% | 96 | 3.6 | 0.083 [0.016, 0.151] | -177 | -631 | -44 |
| alone_FULL_TF | top_10% | 489 | 18.1 | 0.059 [0.037, 0.082] | -115 | -2087 | -144 |
| alone_TEACHER | top_10% | 672 | 24.9 | 0.066 [0.048, 0.083] | -78 | -1948 | -135 |
| alone_SEQ | top_10% | 607 | 22.5 | 0.068 [0.046, 0.089] | -47 | -1055 | -73 |
| 1of3_any | top_20% | 1311 | 48.6 | 0.053 [0.041, 0.065] | -91 | -4409 | -305 |
| 2of3 | top_20% | 655 | 24.3 | 0.064 [0.046, 0.082] | -56 | -1350 | -93 |
| 3of3 | top_20% | 245 | 9.1 | 0.131 [0.090, 0.171] | -31 | -285 | -20 |
| alone_FULL_TF | top_20% | 729 | 27.0 | 0.066 [0.049, 0.083] | -66 | -1784 | -123 |
| alone_TEACHER | top_20% | 965 | 35.7 | 0.055 [0.042, 0.068] | -89 | -3191 | -221 |
| alone_SEQ | top_20% | 800 | 29.6 | 0.080 [0.060, 0.100] | -28 | -815 | -56 |

**E4**

| rule | tier | n takes | takes/wk | precision [CI] | $/trade | $/week | $/session |
|---|---|---|---|---|---|---|---|
| 1of3_any | top_0.05% | 35 | 1.3 | 0.086 [-0.010, 0.182] | -175 | -236 | -16 |
| 2of3 | top_0.05% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| 3of3 | top_0.05% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.05% | 7 | 0.3 | 0.000 [0.000, 0.000] | -375 | -101 | -7 |
| alone_TEACHER | top_0.05% | 2 | 0.1 | 0.000 [0.000, 0.000] | -486 | -37 | -3 |
| alone_SEQ | top_0.05% | 26 | 1.0 | 0.115 [-0.010, 0.241] | -97 | -97 | -7 |
| 1of3_any | top_0.1% | 64 | 2.5 | 0.094 [0.023, 0.165] | -49 | -122 | -8 |
| 2of3 | top_0.1% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| 3of3 | top_0.1% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.1% | 12 | 0.5 | 0.083 [-0.106, 0.272] | -431 | -199 | -13 |
| alone_TEACHER | top_0.1% | 6 | 0.2 | 0.000 [0.000, 0.000] | 216 | 50 | 3 |
| alone_SEQ | top_0.1% | 47 | 1.8 | 0.106 [0.018, 0.195] | -5 | -8 | -1 |
| 1of3_any | top_0.2% | 98 | 3.8 | 0.112 [0.050, 0.175] | 34 | 128 | 9 |
| 2of3 | top_0.2% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| 3of3 | top_0.2% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.2% | 23 | 0.9 | 0.087 [-0.043, 0.217] | -422 | -374 | -25 |
| alone_TEACHER | top_0.2% | 11 | 0.4 | 0.273 [-0.041, 0.587] | 493 | 208 | 14 |
| alone_SEQ | top_0.2% | 66 | 2.5 | 0.106 [0.035, 0.177] | 131 | 332 | 22 |
| 1of3_any | top_0.5% | 150 | 5.8 | 0.100 [0.051, 0.148] | -21 | -123 | -8 |
| 2of3 | top_0.5% | 5 | 0.2 | 0.000 [0.000, 0.000] | -418 | -80 | -5 |
| 3of3 | top_0.5% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.5% | 42 | 1.6 | 0.071 [-0.010, 0.153] | -206 | -333 | -22 |
| alone_TEACHER | top_0.5% | 24 | 0.9 | 0.125 [-0.019, 0.269] | 63 | 58 | 4 |
| alone_SEQ | top_0.5% | 99 | 3.8 | 0.121 [0.057, 0.185] | 88 | 336 | 23 |
| 1of3_any | top_1% | 205 | 7.9 | 0.107 [0.063, 0.151] | -51 | -399 | -27 |
| 2of3 | top_1% | 17 | 0.7 | 0.059 [-0.069, 0.186] | -55 | -36 | -2 |
| 3of3 | top_1% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_1% | 59 | 2.3 | 0.152 [0.065, 0.240] | 41 | 94 | 6 |
| alone_TEACHER | top_1% | 44 | 1.7 | 0.068 [-0.009, 0.145] | -299 | -506 | -34 |
| alone_SEQ | top_1% | 146 | 5.6 | 0.096 [0.043, 0.149] | 25 | 139 | 9 |
| 1of3_any | top_2% | 319 | 12.3 | 0.085 [0.055, 0.114] | -38 | -468 | -32 |
| 2of3 | top_2% | 57 | 2.2 | 0.070 [-0.001, 0.141] | -88 | -193 | -13 |
| 3of3 | top_2% | 6 | 0.2 | 0.333 [-0.209, 0.875] | 624 | 144 | 10 |
| alone_FULL_TF | top_2% | 98 | 3.8 | 0.102 [0.045, 0.159] | 58 | 217 | 15 |
| alone_TEACHER | top_2% | 70 | 2.7 | 0.114 [0.036, 0.192] | -14 | -39 | -3 |
| alone_SEQ | top_2% | 269 | 10.3 | 0.086 [0.053, 0.118] | -70 | -724 | -49 |
| 1of3_any | top_5% | 481 | 18.5 | 0.079 [0.054, 0.104] | -7 | -134 | -9 |
| 2of3 | top_5% | 140 | 5.4 | 0.086 [0.037, 0.135] | 13 | 68 | 5 |
| 3of3 | top_5% | 29 | 1.1 | 0.069 [-0.036, 0.174] | 87 | 97 | 7 |
| alone_FULL_TF | top_5% | 180 | 6.9 | 0.117 [0.067, 0.166] | 129 | 890 | 60 |
| alone_TEACHER | top_5% | 176 | 6.8 | 0.085 [0.045, 0.126] | -93 | -627 | -42 |
| alone_SEQ | top_5% | 407 | 15.7 | 0.093 [0.065, 0.122] | -19 | -290 | -20 |
| 1of3_any | top_10% | 599 | 23.0 | 0.079 [0.058, 0.099] | -39 | -901 | -61 |
| 2of3 | top_10% | 251 | 9.7 | 0.128 [0.089, 0.166] | 181 | 1750 | 118 |
| 3of3 | top_10% | 98 | 3.8 | 0.122 [0.050, 0.195] | -18 | -66 | -4 |
| alone_FULL_TF | top_10% | 287 | 11.0 | 0.094 [0.059, 0.129] | 41 | 453 | 31 |
| alone_TEACHER | top_10% | 340 | 13.1 | 0.082 [0.055, 0.110] | -10 | -124 | -8 |
| alone_SEQ | top_10% | 461 | 17.7 | 0.082 [0.058, 0.107] | -35 | -628 | -42 |
| 1of3_any | top_20% | 891 | 34.3 | 0.061 [0.044, 0.077] | -48 | -1661 | -112 |
| 2of3 | top_20% | 434 | 16.7 | 0.095 [0.068, 0.121] | 8 | 130 | 9 |
| 3of3 | top_20% | 226 | 8.7 | 0.115 [0.072, 0.158] | -82 | -712 | -48 |
| alone_FULL_TF | top_20% | 465 | 17.9 | 0.082 [0.057, 0.106] | -67 | -1199 | -81 |
| alone_TEACHER | top_20% | 674 | 25.9 | 0.079 [0.057, 0.100] | 28 | 735 | 50 |
| alone_SEQ | top_20% | 565 | 21.7 | 0.083 [0.060, 0.106] | -55 | -1198 | -81 |

**E5**

| rule | tier | n takes | takes/wk | precision [CI] | $/trade | $/week | $/session |
|---|---|---|---|---|---|---|---|
| 1of3_any | top_0.05% | 30 | 1.2 | 0.100 [-0.015, 0.215] | -87 | -100 | -7 |
| 2of3 | top_0.05% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| 3of3 | top_0.05% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.05% | 6 | 0.2 | 0.000 [0.000, 0.000] | -126 | -29 | -2 |
| alone_TEACHER | top_0.05% | 9 | 0.3 | 0.000 [0.000, 0.000] | -95 | -33 | -2 |
| alone_SEQ | top_0.05% | 16 | 0.6 | 0.188 [-0.026, 0.401] | -12 | -7 | -0 |
| 1of3_any | top_0.1% | 44 | 1.7 | 0.068 [-0.009, 0.145] | -266 | -450 | -30 |
| 2of3 | top_0.1% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| 3of3 | top_0.1% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.1% | 7 | 0.3 | 0.000 [0.000, 0.000] | -242 | -65 | -4 |
| alone_TEACHER | top_0.1% | 11 | 0.4 | 0.000 [0.000, 0.000] | -253 | -107 | -7 |
| alone_SEQ | top_0.1% | 28 | 1.1 | 0.107 [-0.011, 0.226] | -270 | -290 | -20 |
| 1of3_any | top_0.2% | 84 | 3.2 | 0.059 [0.008, 0.111] | -207 | -669 | -45 |
| 2of3 | top_0.2% | 4 | 0.2 | 0.000 [0.000, 0.000] | -399 | -61 | -4 |
| 3of3 | top_0.2% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.2% | 14 | 0.5 | 0.000 [0.000, 0.000] | -61 | -33 | -2 |
| alone_TEACHER | top_0.2% | 16 | 0.6 | 0.062 [-0.072, 0.197] | -162 | -100 | -7 |
| alone_SEQ | top_0.2% | 69 | 2.7 | 0.058 [0.001, 0.115] | -226 | -600 | -40 |
| 1of3_any | top_0.5% | 155 | 6.0 | 0.065 [0.026, 0.103] | -32 | -189 | -13 |
| 2of3 | top_0.5% | 14 | 0.5 | 0.214 [-0.039, 0.467] | 1 | 1 | 0 |
| 3of3 | top_0.5% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.5% | 33 | 1.3 | 0.091 [-0.012, 0.194] | 142 | 180 | 12 |
| alone_TEACHER | top_0.5% | 27 | 1.0 | 0.037 [-0.039, 0.114] | 57 | 59 | 4 |
| alone_SEQ | top_0.5% | 142 | 5.5 | 0.085 [0.039, 0.130] | -41 | -223 | -15 |
| 1of3_any | top_1% | 230 | 8.8 | 0.074 [0.041, 0.107] | 30 | 264 | 18 |
| 2of3 | top_1% | 34 | 1.3 | 0.088 [-0.010, 0.186] | -205 | -268 | -18 |
| 3of3 | top_1% | 7 | 0.3 | 0.286 [-0.121, 0.692] | 174 | 47 | 3 |
| alone_FULL_TF | top_1% | 55 | 2.1 | 0.091 [0.016, 0.166] | -22 | -48 | -3 |
| alone_TEACHER | top_1% | 71 | 2.7 | 0.085 [0.020, 0.149] | 58 | 159 | 11 |
| alone_SEQ | top_1% | 207 | 8.0 | 0.082 [0.046, 0.119] | 11 | 90 | 6 |
| 1of3_any | top_2% | 340 | 13.1 | 0.071 [0.041, 0.100] | -20 | -257 | -17 |
| 2of3 | top_2% | 67 | 2.6 | 0.134 [0.050, 0.218] | -107 | -276 | -19 |
| 3of3 | top_2% | 16 | 0.6 | 0.125 [-0.050, 0.300] | 117 | 72 | 5 |
| alone_FULL_TF | top_2% | 80 | 3.1 | 0.113 [0.041, 0.184] | -55 | -170 | -11 |
| alone_TEACHER | top_2% | 104 | 4.0 | 0.125 [0.062, 0.188] | 61 | 244 | 16 |
| alone_SEQ | top_2% | 308 | 11.8 | 0.062 [0.036, 0.088] | -50 | -589 | -40 |
| 1of3_any | top_5% | 469 | 18.0 | 0.083 [0.055, 0.111] | -19 | -350 | -24 |
| 2of3 | top_5% | 126 | 4.8 | 0.103 [0.049, 0.158] | -78 | -379 | -25 |
| 3of3 | top_5% | 55 | 2.1 | 0.164 [0.063, 0.265] | 341 | 722 | 48 |
| alone_FULL_TF | top_5% | 134 | 5.2 | 0.119 [0.066, 0.173] | -36 | -187 | -13 |
| alone_TEACHER | top_5% | 177 | 6.8 | 0.096 [0.052, 0.140] | -6 | -42 | -3 |
| alone_SEQ | top_5% | 412 | 15.8 | 0.078 [0.051, 0.105] | -31 | -498 | -33 |
| 1of3_any | top_10% | 610 | 23.5 | 0.074 [0.051, 0.097] | -70 | -1638 | -110 |
| 2of3 | top_10% | 203 | 7.8 | 0.094 [0.053, 0.134] | -91 | -714 | -48 |
| 3of3 | top_10% | 115 | 4.4 | 0.130 [0.065, 0.196] | -52 | -228 | -15 |
| alone_FULL_TF | top_10% | 240 | 9.2 | 0.083 [0.049, 0.117] | -131 | -1212 | -81 |
| alone_TEACHER | top_10% | 278 | 10.7 | 0.083 [0.047, 0.118] | -137 | -1464 | -98 |
| alone_SEQ | top_10% | 487 | 18.7 | 0.080 [0.057, 0.104] | -17 | -312 | -21 |
| 1of3_any | top_20% | 854 | 32.8 | 0.070 [0.053, 0.087] | -30 | -982 | -66 |
| 2of3 | top_20% | 387 | 14.9 | 0.085 [0.055, 0.116] | -45 | -671 | -45 |
| 3of3 | top_20% | 220 | 8.5 | 0.077 [0.043, 0.112] | -81 | -688 | -46 |
| alone_FULL_TF | top_20% | 431 | 16.6 | 0.090 [0.061, 0.120] | -60 | -997 | -67 |
| alone_TEACHER | top_20% | 464 | 17.8 | 0.080 [0.055, 0.104] | -48 | -852 | -57 |
| alone_SEQ | top_20% | 671 | 25.8 | 0.067 [0.048, 0.086] | -11 | -278 | -19 |

**E6**

| rule | tier | n takes | takes/wk | precision [CI] | $/trade | $/week | $/session |
|---|---|---|---|---|---|---|---|
| 1of3_any | top_0.05% | 41 | 1.6 | 0.024 [-0.025, 0.073] | 59 | 94 | 6 |
| 2of3 | top_0.05% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| 3of3 | top_0.05% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.05% | 5 | 0.2 | 0.000 [0.000, 0.000] | -325 | -62 | -4 |
| alone_TEACHER | top_0.05% | 12 | 0.5 | 0.000 [0.000, 0.000] | -7 | -3 | -0 |
| alone_SEQ | top_0.05% | 27 | 1.0 | 0.037 [-0.037, 0.111] | 50 | 52 | 4 |
| 1of3_any | top_0.1% | 78 | 3.0 | 0.013 [-0.013, 0.038] | -255 | -764 | -52 |
| 2of3 | top_0.1% | 2 | 0.1 | 0.000 [0.000, 0.000] | -930 | -72 | -5 |
| 3of3 | top_0.1% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.1% | 7 | 0.3 | 0.000 [0.000, 0.000] | -498 | -134 | -9 |
| alone_TEACHER | top_0.1% | 26 | 1.0 | 0.000 [0.000, 0.000] | -81 | -81 | -5 |
| alone_SEQ | top_0.1% | 54 | 2.1 | 0.018 [-0.018, 0.055] | -347 | -720 | -49 |
| 1of3_any | top_0.2% | 108 | 4.2 | 0.093 [0.033, 0.152] | 19 | 79 | 5 |
| 2of3 | top_0.2% | 6 | 0.2 | 0.167 [-0.428, 0.762] | -476 | -110 | -7 |
| 3of3 | top_0.2% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.2% | 11 | 0.4 | 0.182 [0.019, 0.345] | -37 | -16 | -1 |
| alone_TEACHER | top_0.2% | 36 | 1.4 | 0.111 [0.004, 0.218] | 198 | 274 | 19 |
| alone_SEQ | top_0.2% | 82 | 3.2 | 0.085 [0.015, 0.156] | -40 | -127 | -9 |
| 1of3_any | top_0.5% | 173 | 6.7 | 0.098 [0.049, 0.148] | 27 | 182 | 12 |
| 2of3 | top_0.5% | 16 | 0.6 | 0.062 [-0.074, 0.199] | 492 | 303 | 20 |
| 3of3 | top_0.5% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.5% | 23 | 0.9 | 0.000 [0.000, 0.000] | 21 | 19 | 1 |
| alone_TEACHER | top_0.5% | 53 | 2.0 | 0.132 [0.038, 0.227] | 254 | 519 | 35 |
| alone_SEQ | top_0.5% | 138 | 5.3 | 0.080 [0.031, 0.128] | -76 | -401 | -27 |
| 1of3_any | top_1% | 234 | 9.0 | 0.064 [0.031, 0.098] | -109 | -979 | -66 |
| 2of3 | top_1% | 41 | 1.6 | 0.098 [-0.000, 0.195] | -106 | -168 | -11 |
| 3of3 | top_1% | 2 | 0.1 | 0.000 [0.000, 0.000] | -930 | -72 | -5 |
| alone_FULL_TF | top_1% | 46 | 1.8 | 0.043 [-0.026, 0.113] | -320 | -566 | -38 |
| alone_TEACHER | top_1% | 72 | 2.8 | 0.139 [0.057, 0.221] | 248 | 687 | 47 |
| alone_SEQ | top_1% | 190 | 7.3 | 0.042 [0.010, 0.074] | -160 | -1170 | -79 |
| 1of3_any | top_2% | 307 | 11.8 | 0.101 [0.065, 0.137] | 58 | 685 | 46 |
| 2of3 | top_2% | 70 | 2.7 | 0.100 [0.016, 0.184] | 217 | 584 | 40 |
| 3of3 | top_2% | 14 | 0.5 | 0.000 [0.000, 0.000] | -32 | -17 | -1 |
| alone_FULL_TF | top_2% | 71 | 2.7 | 0.113 [0.034, 0.191] | 49 | 135 | 9 |
| alone_TEACHER | top_2% | 116 | 4.5 | 0.129 [0.071, 0.188] | 307 | 1369 | 93 |
| alone_SEQ | top_2% | 259 | 10.0 | 0.070 [0.035, 0.104] | -41 | -410 | -28 |
| 1of3_any | top_5% | 482 | 18.5 | 0.081 [0.051, 0.111] | -48 | -899 | -61 |
| 2of3 | top_5% | 160 | 6.2 | 0.081 [0.042, 0.121] | 13 | 82 | 6 |
| 3of3 | top_5% | 57 | 2.2 | 0.123 [0.038, 0.208] | 119 | 261 | 18 |
| alone_FULL_TF | top_5% | 196 | 7.5 | 0.076 [0.040, 0.113] | -40 | -303 | -20 |
| alone_TEACHER | top_5% | 218 | 8.4 | 0.078 [0.038, 0.118] | -97 | -812 | -55 |
| alone_SEQ | top_5% | 336 | 12.9 | 0.101 [0.064, 0.139] | 155 | 1997 | 135 |
| 1of3_any | top_10% | 721 | 27.7 | 0.090 [0.069, 0.112] | -17 | -465 | -32 |
| 2of3 | top_10% | 314 | 12.1 | 0.096 [0.061, 0.130] | -37 | -441 | -30 |
| 3of3 | top_10% | 117 | 4.5 | 0.094 [0.041, 0.147] | 70 | 316 | 21 |
| alone_FULL_TF | top_10% | 353 | 13.6 | 0.082 [0.051, 0.113] | -73 | -996 | -67 |
| alone_TEACHER | top_10% | 434 | 16.7 | 0.097 [0.066, 0.128] | -80 | -1329 | -90 |
| alone_SEQ | top_10% | 475 | 18.3 | 0.120 [0.093, 0.146] | 121 | 2219 | 150 |
| 1of3_any | top_20% | 1052 | 40.5 | 0.089 [0.072, 0.106] | 2 | 68 | 5 |
| 2of3 | top_20% | 600 | 23.1 | 0.093 [0.069, 0.118] | -78 | -1799 | -122 |
| 3of3 | top_20% | 273 | 10.5 | 0.095 [0.063, 0.128] | -7 | -71 | -5 |
| alone_FULL_TF | top_20% | 662 | 25.5 | 0.088 [0.064, 0.111] | -59 | -1499 | -101 |
| alone_TEACHER | top_20% | 717 | 27.6 | 0.100 [0.077, 0.123] | -19 | -519 | -35 |
| alone_SEQ | top_20% | 777 | 29.9 | 0.084 [0.064, 0.104] | 13 | 380 | 26 |

**E8_GATE_2025H1**

| rule | tier | n takes | takes/wk | precision [CI] | $/trade | $/week | $/session |
|---|---|---|---|---|---|---|---|
| 1of3_any | top_0.05% | 50 | 1.9 | 0.040 [-0.022, 0.102] | -298 | -551 | -39 |
| 2of3 | top_0.05% | 2 | 0.1 | 0.000 [0.000, 0.000] | -942 | -70 | -5 |
| 3of3 | top_0.05% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.05% | 5 | 0.2 | 0.000 [0.000, 0.000] | -332 | -62 | -4 |
| alone_TEACHER | top_0.05% | 16 | 0.6 | 0.000 [0.000, 0.000] | -481 | -285 | -20 |
| alone_SEQ | top_0.05% | 34 | 1.3 | 0.059 [-0.033, 0.150] | -301 | -379 | -27 |
| 1of3_any | top_0.1% | 85 | 3.1 | 0.047 [-0.004, 0.098] | -256 | -805 | -57 |
| 2of3 | top_0.1% | 2 | 0.1 | 0.000 [0.000, 0.000] | -942 | -70 | -5 |
| 3of3 | top_0.1% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.1% | 5 | 0.2 | 0.000 [0.000, 0.000] | -132 | -25 | -2 |
| alone_TEACHER | top_0.1% | 23 | 0.9 | 0.000 [0.000, 0.000] | -432 | -368 | -26 |
| alone_SEQ | top_0.1% | 61 | 2.3 | 0.066 [-0.005, 0.136] | -244 | -552 | -39 |
| 1of3_any | top_0.2% | 133 | 4.9 | 0.083 [0.027, 0.139] | -241 | -1186 | -84 |
| 2of3 | top_0.2% | 2 | 0.1 | 0.000 [0.000, 0.000] | -942 | -70 | -5 |
| 3of3 | top_0.2% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.2% | 12 | 0.4 | 0.000 [0.000, 0.000] | -379 | -168 | -12 |
| alone_TEACHER | top_0.2% | 43 | 1.6 | 0.070 [-0.012, 0.151] | -321 | -511 | -36 |
| alone_SEQ | top_0.2% | 89 | 3.3 | 0.112 [0.036, 0.189] | -194 | -639 | -45 |
| 1of3_any | top_0.5% | 223 | 8.3 | 0.103 [0.064, 0.142] | -79 | -651 | -46 |
| 2of3 | top_0.5% | 11 | 0.4 | 0.000 [0.000, 0.000] | 482 | 197 | 14 |
| 3of3 | top_0.5% | 0 | 0.0 | . [., .] | . | 0 | 0 |
| alone_FULL_TF | top_0.5% | 30 | 1.1 | 0.100 [-0.005, 0.205] | 241 | 268 | 19 |
| alone_TEACHER | top_0.5% | 58 | 2.1 | 0.121 [0.022, 0.220] | -170 | -365 | -26 |
| alone_SEQ | top_0.5% | 156 | 5.8 | 0.109 [0.062, 0.155] | 25 | 145 | 10 |
| 1of3_any | top_1% | 307 | 11.4 | 0.111 [0.077, 0.145] | -11 | -126 | -9 |
| 2of3 | top_1% | 23 | 0.9 | 0.130 [-0.007, 0.268] | 567 | 483 | 34 |
| 3of3 | top_1% | 1 | 0.0 | 0.000 [., .] | -955 | -35 | -3 |
| alone_FULL_TF | top_1% | 49 | 1.8 | 0.102 [0.019, 0.185] | 276 | 501 | 36 |
| alone_TEACHER | top_1% | 82 | 3.0 | 0.073 [0.013, 0.133] | -227 | -691 | -49 |
| alone_SEQ | top_1% | 232 | 8.6 | 0.116 [0.078, 0.155] | -50 | -429 | -30 |
| 1of3_any | top_2% | 452 | 16.7 | 0.111 [0.084, 0.137] | 54 | 911 | 65 |
| 2of3 | top_2% | 70 | 2.6 | 0.086 [0.020, 0.151] | 30 | 77 | 5 |
| 3of3 | top_2% | 11 | 0.4 | 0.091 [-0.118, 0.299] | 159 | 65 | 5 |
| alone_FULL_TF | top_2% | 91 | 3.4 | 0.099 [0.032, 0.166] | 98 | 331 | 23 |
| alone_TEACHER | top_2% | 143 | 5.3 | 0.091 [0.049, 0.133] | 35 | 188 | 13 |
| alone_SEQ | top_2% | 376 | 13.9 | 0.106 [0.077, 0.136] | -30 | -411 | -29 |
| 1of3_any | top_5% | 637 | 23.6 | 0.099 [0.077, 0.121] | -24 | -561 | -40 |
| 2of3 | top_5% | 177 | 6.6 | 0.119 [0.074, 0.163] | 372 | 2442 | 173 |
| 3of3 | top_5% | 43 | 1.6 | 0.093 [0.003, 0.183] | 145 | 231 | 16 |
| alone_FULL_TF | top_5% | 170 | 6.3 | 0.082 [0.046, 0.118] | 143 | 902 | 64 |
| alone_TEACHER | top_5% | 252 | 9.3 | 0.099 [0.060, 0.138] | -63 | -592 | -42 |
| alone_SEQ | top_5% | 517 | 19.1 | 0.104 [0.081, 0.128] | 66 | 1273 | 90 |
| 1of3_any | top_10% | 833 | 30.9 | 0.094 [0.075, 0.112] | -79 | -2427 | -172 |
| 2of3 | top_10% | 340 | 12.6 | 0.068 [0.039, 0.097] | 18 | 230 | 16 |
| 3of3 | top_10% | 113 | 4.2 | 0.124 [0.068, 0.180] | 226 | 946 | 67 |
| alone_FULL_TF | top_10% | 317 | 11.7 | 0.091 [0.059, 0.123] | -41 | -487 | -35 |
| alone_TEACHER | top_10% | 372 | 13.8 | 0.086 [0.057, 0.115] | -27 | -368 | -26 |
| alone_SEQ | top_10% | 688 | 25.5 | 0.102 [0.081, 0.123] | -41 | -1043 | -74 |
| 1of3_any | top_20% | 1228 | 45.5 | 0.083 [0.067, 0.099] | -101 | -4597 | -326 |
| 2of3 | top_20% | 663 | 24.6 | 0.092 [0.070, 0.114] | -103 | -2520 | -179 |
| 3of3 | top_20% | 307 | 11.4 | 0.098 [0.064, 0.132] | -103 | -1176 | -83 |
| alone_FULL_TF | top_20% | 591 | 21.9 | 0.102 [0.079, 0.124] | -38 | -825 | -58 |
| alone_TEACHER | top_20% | 703 | 26.0 | 0.087 [0.064, 0.109] | -113 | -2931 | -208 |
| alone_SEQ | top_20% | 1063 | 39.4 | 0.085 [0.067, 0.102] | -115 | -4534 | -321 |


---

## 6. THE VERDICT PLANE at the user's weekly throughput floor

Every operating point measured in §2–§5 — threshold x day-abstention x agreement — filtered to a minimum of N portfolio takes per week (all three assets together) and then maximised three ways.

**E3**

| floor takes/wk | criterion | operating point | n takes | takes/wk | precision [CI] | $/trade | $/week | week p10 | losing wks | $/session | vs D-048 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3.0000 | max_usd_per_week | `agreement_1of3_any\|top_1%` | 292 | 10.8 | 0.099 [0.064, 0.135] | 88 | 953 | -2465 | 0.41 | 66 | -1934 |
| 3.0000 | max_precision | `joint_daygate_q80_3of3\|top_20%` | 245 | 9.1 | 0.131 [0.090, 0.171] | -31 | -282 | -5176 | 0.44 | -20 | -2020 |
| 3.0000 | max_usd_per_trade | `threshold_episode_COMPOSED\|top_0.5%` | 90 | 3.3 | 0.089 [0.023, 0.155] | 120 | 399 | -2034 | 0.48 | 28 | -1972 |
| 4.0000 | max_usd_per_week | `agreement_1of3_any\|top_1%` | 292 | 10.8 | 0.099 [0.064, 0.135] | 88 | 953 | -2465 | 0.41 | 66 | -1934 |
| 4.0000 | max_precision | `joint_daygate_q80_3of3\|top_20%` | 245 | 9.1 | 0.131 [0.090, 0.171] | -31 | -282 | -5176 | 0.44 | -20 | -2020 |
| 4.0000 | max_usd_per_trade | `daygate_preday_q50.0\|top_5%` | 162 | 6.0 | 0.086 [0.048, 0.125] | 117 | 699 | -2328 | 0.41 | 48 | -1952 |
| 5.0000 | max_usd_per_week | `agreement_1of3_any\|top_1%` | 292 | 10.8 | 0.099 [0.064, 0.135] | 88 | 953 | -2465 | 0.41 | 66 | -1934 |
| 5.0000 | max_precision | `joint_daygate_q80_3of3\|top_20%` | 245 | 9.1 | 0.131 [0.090, 0.171] | -31 | -282 | -5176 | 0.44 | -20 | -2020 |
| 5.0000 | max_usd_per_trade | `daygate_preday_q50.0\|top_5%` | 162 | 6.0 | 0.086 [0.048, 0.125] | 117 | 699 | -2328 | 0.41 | 48 | -1952 |
| 8.0000 | max_usd_per_week | `agreement_1of3_any\|top_1%` | 292 | 10.8 | 0.099 [0.064, 0.135] | 88 | 953 | -2465 | 0.41 | 66 | -1934 |
| 8.0000 | max_precision | `joint_daygate_q80_3of3\|top_20%` | 245 | 9.1 | 0.131 [0.090, 0.171] | -31 | -282 | -5176 | 0.44 | -20 | -2020 |
| 8.0000 | max_usd_per_trade | `agreement_1of3_any\|top_1%` | 292 | 10.8 | 0.099 [0.064, 0.135] | 88 | 953 | -2465 | 0.41 | 66 | -1934 |

**E4**

| floor takes/wk | criterion | operating point | n takes | takes/wk | precision [CI] | $/trade | $/week | week p10 | losing wks | $/session | vs D-048 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3.0000 | max_usd_per_week | `agreement_2of3\|top_10%` | 251 | 9.7 | 0.128 [0.089, 0.166] | 181 | 1750 | -1564 | 0.31 | 118 | -1882 |
| 3.0000 | max_precision | `threshold_candidate_COMPOSED\|top_0.5%` | 87 | 3.3 | 0.149 [0.071, 0.228] | 140 | 467 | -1862 | 0.38 | 32 | -1968 |
| 3.0000 | max_usd_per_trade | `joint_daygate_q95_2of3\|top_10%` | 134 | 5.2 | 0.104 [0.053, 0.156] | 190 | 980 | -2030 | 0.50 | 66 | -1934 |
| 4.0000 | max_usd_per_week | `agreement_2of3\|top_10%` | 251 | 9.7 | 0.128 [0.089, 0.166] | 181 | 1750 | -1564 | 0.31 | 118 | -1882 |
| 4.0000 | max_precision | `daygate_causal_q50.0\|top_5%` | 172 | 6.6 | 0.128 [0.073, 0.183] | 130 | 863 | -2198 | 0.46 | 58 | -1942 |
| 4.0000 | max_usd_per_trade | `joint_daygate_q95_2of3\|top_10%` | 134 | 5.2 | 0.104 [0.053, 0.156] | 190 | 980 | -2030 | 0.50 | 66 | -1934 |
| 5.0000 | max_usd_per_week | `agreement_2of3\|top_10%` | 251 | 9.7 | 0.128 [0.089, 0.166] | 181 | 1750 | -1564 | 0.31 | 118 | -1882 |
| 5.0000 | max_precision | `daygate_causal_q50.0\|top_5%` | 172 | 6.6 | 0.128 [0.073, 0.183] | 130 | 863 | -2198 | 0.46 | 58 | -1942 |
| 5.0000 | max_usd_per_trade | `joint_daygate_q95_2of3\|top_10%` | 134 | 5.2 | 0.104 [0.053, 0.156] | 190 | 980 | -2030 | 0.50 | 66 | -1934 |
| 8.0000 | max_usd_per_week | `agreement_2of3\|top_10%` | 251 | 9.7 | 0.128 [0.089, 0.166] | 181 | 1750 | -1564 | 0.31 | 118 | -1882 |
| 8.0000 | max_precision | `agreement_2of3\|top_10%` | 251 | 9.7 | 0.128 [0.089, 0.166] | 181 | 1750 | -1564 | 0.31 | 118 | -1882 |
| 8.0000 | max_usd_per_trade | `agreement_2of3\|top_10%` | 251 | 9.7 | 0.128 [0.089, 0.166] | 181 | 1750 | -1564 | 0.31 | 118 | -1882 |

**E5**

| floor takes/wk | criterion | operating point | n takes | takes/wk | precision [CI] | $/trade | $/week | week p10 | losing wks | $/session | vs D-048 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3.0000 | max_usd_per_week | `agreement_1of3_any\|top_1%` | 230 | 8.8 | 0.074 [0.041, 0.107] | 30 | 264 | -3253 | 0.54 | 18 | -1982 |
| 3.0000 | max_precision | `daygate_causal_q70.0\|top_5%` | 108 | 4.2 | 0.148 [0.082, 0.215] | -34 | -140 | -3071 | 0.42 | -9 | -2009 |
| 3.0000 | max_usd_per_trade | `agreement_alone_TEACHER\|top_2%` | 104 | 4.0 | 0.125 [0.062, 0.188] | 61 | 244 | -2134 | 0.42 | 16 | -1984 |
| 4.0000 | max_usd_per_week | `agreement_1of3_any\|top_1%` | 230 | 8.8 | 0.074 [0.041, 0.107] | 30 | 264 | -3253 | 0.54 | 18 | -1982 |
| 4.0000 | max_precision | `daygate_causal_q70.0\|top_5%` | 108 | 4.2 | 0.148 [0.082, 0.215] | -34 | -140 | -3071 | 0.42 | -9 | -2009 |
| 4.0000 | max_usd_per_trade | `agreement_alone_TEACHER\|top_2%` | 104 | 4.0 | 0.125 [0.062, 0.188] | 61 | 244 | -2134 | 0.42 | 16 | -1984 |
| 5.0000 | max_usd_per_week | `agreement_1of3_any\|top_1%` | 230 | 8.8 | 0.074 [0.041, 0.107] | 30 | 264 | -3253 | 0.54 | 18 | -1982 |
| 5.0000 | max_precision | `daygate_causal_q0.0\|top_5%` | 133 | 5.1 | 0.128 [0.072, 0.184] | -11 | -58 | -3255 | 0.50 | -4 | -2004 |
| 5.0000 | max_usd_per_trade | `agreement_1of3_any\|top_1%` | 230 | 8.8 | 0.074 [0.041, 0.107] | 30 | 264 | -3253 | 0.54 | 18 | -1982 |
| 8.0000 | max_usd_per_week | `agreement_1of3_any\|top_1%` | 230 | 8.8 | 0.074 [0.041, 0.107] | 30 | 264 | -3253 | 0.54 | 18 | -1982 |
| 8.0000 | max_precision | `threshold_episode_prevcut\|top_10%` | 379 | 14.6 | 0.108 [0.073, 0.143] | -30 | -435 | -6995 | 0.50 | -29 | -2029 |
| 8.0000 | max_usd_per_trade | `agreement_1of3_any\|top_1%` | 230 | 8.8 | 0.074 [0.041, 0.107] | 30 | 264 | -3253 | 0.54 | 18 | -1982 |

**E6**

| floor takes/wk | criterion | operating point | n takes | takes/wk | precision [CI] | $/trade | $/week | week p10 | losing wks | $/session | vs D-048 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3.0000 | max_usd_per_week | `agreement_alone_SEQ\|top_10%` | 475 | 18.3 | 0.120 [0.093, 0.146] | 121 | 2219 | -4226 | 0.42 | 150 | -1850 |
| 3.0000 | max_precision | `agreement_alone_TEACHER\|top_2%` | 116 | 4.5 | 0.129 [0.071, 0.188] | 307 | 1369 | -1588 | 0.35 | 93 | -1907 |
| 3.0000 | max_usd_per_trade | `agreement_alone_TEACHER\|top_2%` | 116 | 4.5 | 0.129 [0.071, 0.188] | 307 | 1369 | -1588 | 0.35 | 93 | -1907 |
| 4.0000 | max_usd_per_week | `agreement_alone_SEQ\|top_10%` | 475 | 18.3 | 0.120 [0.093, 0.146] | 121 | 2219 | -4226 | 0.42 | 150 | -1850 |
| 4.0000 | max_precision | `agreement_alone_TEACHER\|top_2%` | 116 | 4.5 | 0.129 [0.071, 0.188] | 307 | 1369 | -1588 | 0.35 | 93 | -1907 |
| 4.0000 | max_usd_per_trade | `agreement_alone_TEACHER\|top_2%` | 116 | 4.5 | 0.129 [0.071, 0.188] | 307 | 1369 | -1588 | 0.35 | 93 | -1907 |
| 5.0000 | max_usd_per_week | `agreement_alone_SEQ\|top_10%` | 475 | 18.3 | 0.120 [0.093, 0.146] | 121 | 2219 | -4226 | 0.42 | 150 | -1850 |
| 5.0000 | max_precision | `agreement_alone_SEQ\|top_10%` | 475 | 18.3 | 0.120 [0.093, 0.146] | 121 | 2219 | -4226 | 0.42 | 150 | -1850 |
| 5.0000 | max_usd_per_trade | `agreement_alone_SEQ\|top_5%` | 336 | 12.9 | 0.101 [0.064, 0.139] | 155 | 1997 | -3819 | 0.46 | 135 | -1865 |
| 8.0000 | max_usd_per_week | `agreement_alone_SEQ\|top_10%` | 475 | 18.3 | 0.120 [0.093, 0.146] | 121 | 2219 | -4226 | 0.42 | 150 | -1850 |
| 8.0000 | max_precision | `agreement_alone_SEQ\|top_10%` | 475 | 18.3 | 0.120 [0.093, 0.146] | 121 | 2219 | -4226 | 0.42 | 150 | -1850 |
| 8.0000 | max_usd_per_trade | `agreement_alone_SEQ\|top_5%` | 336 | 12.9 | 0.101 [0.064, 0.139] | 155 | 1997 | -3819 | 0.46 | 135 | -1865 |

**E8_GATE_2025H1**

| floor takes/wk | criterion | operating point | n takes | takes/wk | precision [CI] | $/trade | $/week | week p10 | losing wks | $/session | vs D-048 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3.0000 | max_usd_per_week | `agreement_2of3\|top_5%` | 177 | 6.6 | 0.119 [0.074, 0.163] | 372 | 2442 | -3968 | 0.44 | 173 | -1827 |
| 3.0000 | max_precision | `joint_daygate_q90_2of3\|top_5%` | 126 | 4.7 | 0.127 [0.071, 0.183] | 387 | 1807 | -2884 | 0.41 | 128 | -1872 |
| 3.0000 | max_usd_per_trade | `joint_daygate_q95_3of3\|top_10%` | 82 | 3.0 | 0.098 [0.039, 0.156] | 416 | 1263 | -2040 | 0.44 | 89 | -1911 |
| 4.0000 | max_usd_per_week | `agreement_2of3\|top_5%` | 177 | 6.6 | 0.119 [0.074, 0.163] | 372 | 2442 | -3968 | 0.44 | 173 | -1827 |
| 4.0000 | max_precision | `joint_daygate_q90_2of3\|top_5%` | 126 | 4.7 | 0.127 [0.071, 0.183] | 387 | 1807 | -2884 | 0.41 | 128 | -1872 |
| 4.0000 | max_usd_per_trade | `joint_daygate_q90_2of3\|top_5%` | 126 | 4.7 | 0.127 [0.071, 0.183] | 387 | 1807 | -2884 | 0.41 | 128 | -1872 |
| 5.0000 | max_usd_per_week | `agreement_2of3\|top_5%` | 177 | 6.6 | 0.119 [0.074, 0.163] | 372 | 2442 | -3968 | 0.44 | 173 | -1827 |
| 5.0000 | max_precision | `agreement_2of3\|top_5%` | 177 | 6.6 | 0.119 [0.074, 0.163] | 372 | 2442 | -3968 | 0.44 | 173 | -1827 |
| 5.0000 | max_usd_per_trade | `agreement_2of3\|top_5%` | 177 | 6.6 | 0.119 [0.074, 0.163] | 372 | 2442 | -3968 | 0.44 | 173 | -1827 |
| 8.0000 | max_usd_per_week | `agreement_alone_SEQ\|top_5%` | 517 | 19.1 | 0.104 [0.081, 0.128] | 66 | 1273 | -4794 | 0.52 | 90 | -1910 |
| 8.0000 | max_precision | `agreement_alone_SEQ\|top_1%` | 232 | 8.6 | 0.116 [0.078, 0.155] | -50 | -429 | -3456 | 0.52 | -30 | -2030 |
| 8.0000 | max_usd_per_trade | `threshold_candidate_COMPOSED\|top_2%` | 242 | 9.0 | 0.099 [0.062, 0.136] | 140 | 1259 | -4724 | 0.48 | 89 | -1911 |


---

## 6b. THE PLANE READ HONESTLY

§6 maximises over the plane INSIDE each era, which is selection on the evaluation data.  Two readings that are not:

### 6b.1 operating points that survive every era at the floor

Present in all 5 reported eras AND at or above 3 portfolio takes/week in EVERY one of them, ranked by mean $/week.

| operating point | mean $/week | worst era $/week | eras positive | mean takes/wk | mean precision | E3 $/wk | E4 $/wk | E5 $/wk | E6 $/wk | E8_GATE_2025H1 $/wk |
|---|---|---|---|---|---|---|---|---|---|---|
| `agreement_2of3\|top_5%` | 452 | -379 | 4/5 | 6.2 | 0.100 | 50 | 68 | -379 | 82 | 2442 |
| `joint_daygate_q95_2of3\|top_5%` | 401 | -336 | 4/5 | 4.5 | 0.100 | 192 | 544 | 133 | -336 | 1470 |
| `joint_daygate_q90_2of3\|top_5%` | 361 | -169 | 3/5 | 5.3 | 0.105 | 208 | -77 | 34 | -169 | 1807 |
| `agreement_1of3_any\|top_2%` | 325 | -468 | 3/5 | 14.3 | 0.090 | 755 | -468 | -257 | 685 | 911 |
| `agreement_alone_SEQ\|top_5%` | 296 | -1002 | 2/5 | 16.5 | 0.090 | -1002 | -290 | -498 | 1997 | 1273 |
| `joint_daygate_q80_2of3\|top_5%` | 202 | -345 | 2/5 | 5.9 | 0.095 | -175 | 30 | -345 | -192 | 1692 |
| `joint_daygate_q95_3of3\|top_20%` | 176 | -104 | 3/5 | 4.6 | 0.099 | 50 | -104 | -56 | 965 | 23 |
| `daygate_causal_q0.0\|top_5%` | 171 | -508 | 2/5 | 7.3 | 0.095 | -508 | 767 | -58 | -313 | 964 |
| `threshold_candidate_FULL_TF\|top_5%` | 163 | -487 | 2/5 | 7.4 | 0.095 | -487 | 890 | -187 | -303 | 902 |
| `daygate_preday_q0.0\|top_5%` | 163 | -487 | 2/5 | 7.4 | 0.095 | -487 | 890 | -187 | -303 | 902 |
| `agreement_alone_FULL_TF\|top_5%` | 163 | -487 | 2/5 | 7.4 | 0.095 | -487 | 890 | -187 | -303 | 902 |
| `threshold_candidate_COMPOSED\|top_2%` | 120 | -1015 | 3/5 | 8.4 | 0.092 | 264 | 260 | -1015 | -168 | 1259 |

### 6b.2 the operating point chosen WALK-FORWARD

The point with the best mean $/week on the eras STRICTLY BEFORE era k (subject to >= 3 takes/week there), applied unchanged to era k.  This is the only reading in this document in which nothing about the traded era — not the model, not the threshold, not the rule — was chosen with knowledge of it.

| point chosen on prior eras | traded era | takes/wk | precision | $/trade | $/week | week p10 | losing wks | $/session |
|---|---|---|---|---|---|---|---|---|
| `agreement_1of3_any\|top_1%` | E4 | 7.9 | 0.107 | -51 | -399 | -3475 | 0.65 | -27 |
| `threshold_candidate_COMPOSED\|top_5%` | E5 | 12.8 | 0.072 | -142 | -1819 | -6584 | 0.69 | -122 |
| `agreement_alone_SEQ\|top_1%` | E6 | 7.3 | 0.042 | -160 | -1170 | -5218 | 0.69 | -79 |
| `joint_daygate_q95_3of3\|top_20%` | E8_GATE_2025H1 | 5.4 | 0.090 | 4 | 23 | -4398 | 0.56 | 2 |


---

## 7. INSTRUMENT RECEIPTS

* **The D-078 control reproduces the committed curve.** `m3_walk --drop-groups
  teacher_evidence` over the new 202-column matrix returns, era for era, the
  numbers committed in `provenance/port_m3/ERA_CURVE.tsv` — same `$/session`,
  same `$/trade`, same selected policy.  The teacher group is appended at the
  end of the registry, so the dropped run's feature block is the pre-teacher
  block, column for column.  Column `control_reproduces_committed` in
  `TEACHER_MARGINAL.tsv` carries the check per era.
* **Red-first, shuffled score.**  §2.3 is the receipt: the same pipeline, the
  same replay, the same tiers, with FULL_TF's own scores permuted within the
  era under the pinned seed.
* **Guards.**  The matrix rebuild passed the D-058 holdout guard, the
  forbidden-source NAME guard and the |Spearman| > 0.98 forward-VALUE guard on
  all 202 columns (`artifacts/cache/port/m3/matrix/matrix.receipt.json`);
  `engine/port_m3/test_m3.py --fast` is 13/13 green with the D-078 instrument
  test rewritten for its fired state.
* **Sequence cues.**  1,399,374 / 1,399,374 rows covered, 0 errors, 585 s at 8
  workers, 120 s pre-decision window, `seq_cues.cues_from_window` unchanged
  (`artifacts/cache/port/m2/frontier/seq.receipt.json`).
* **Causality of the day gate.**  `day_qualification` reads only the scores of
  candidates that have ALREADY fired on that asset-day; the qualifying
  candidate is seatable at its own decision second and every later candidate of
  the day is seatable too.  The pre-day gate reads no candidate score at all.
* **What is NOT measured here.**  The trade shape is unchanged throughout
  (confirmation entry, $900 wall, ride to phase close) — the exit contract
  remains the one never-measured variant class (D-029, user-reserved).  The
  teacher columns are E6-derived definitions re-fitted inside every training
  fold (D-034); no threshold from the round is used as a fitted constant.

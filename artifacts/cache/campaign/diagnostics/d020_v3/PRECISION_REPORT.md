# PRECISION — the entered-winner share at the deployment operating point

Two concurrent positions, the $300 wall with gap-through, 576c charged once per trade, `mirror@1.00` and the `cont[lasso,B]@c25` overlay as the frozen exit keepers, `close` as the floor and `oracle` as the ceiling.  Entry geometry, the three quality gates and the class target are the only things that move.  Every cell of the 4,800-row grid is in `precision_segments/precision_grid.tsv`.


## VERDICT

**1. The headline: the entered-winner share IS movable — 32% to 45-54%, in every era, exactly as rung 3 predicted — and it converts to $102/day, not $2,000.**  Threshold geometry is a real instrument: replacing top-k/day with an absolute study-quantile bar lifts the entered-winner share from the program's standing **31.3-32.5%** (top-3 / top-5) to **34.7-38.5%** at the four threshold rungs pooled, and to **43.3% / 45.8% / 53.6% / 42.5% / 54.5%** at each era's best cell with at least 40 trades.  The mean exit-free certificate of the trades actually ENTERED rises with it, from **$388-$464** in the sub-35% cells to **$636-$1,031** in the 40%+ cells, which is the first time in this program that a taken trade's certificate has reached D-021's $1,000 per-trade bar.  And the dollars move too, for the first time in four rungs: a single cell selected with LEAVE-ONE-ERA-OUT discipline — `E/T/I only`, panel-purged columns, the roster's own `cert >= $500` target, no gates, the **P@top-20% bar**, held to the close — realises **-$4 / +$8 / +$119 / +$108 / +$174** per day across `blind_e3` / `e4` / `e5` / `e6` / `e7`, a deployment-era mean of **+$102/day** against rung 1's best two-position rule at **+$14.5/day** and rung 3's at **-$0.9/day**.  That is a 7x improvement on the same corpus with the exit untouched.  It is also 5% of the target.

**2. Verdict (a): NO era reaches the $2,000 target or the $1,500 weak-era floor, and the shortfall is an order of magnitude, not a margin.**  Best cell per era, taken as an in-block MAXIMUM over 960 cells (an upper bound, not a deployable number): **$385** (`blind_e3`, 20 days), **$113** (`e4`), **$119** (`e5`), **$108** (`e6`), **$199** (`e7`).  The honest leave-one-era-out reading is **-$4 / $8 / $119 / $108 / $174**.  Against $2,000 that is 5-10%; against the $1,500 floor, 7-13%.  The arithmetic of the gap is now fully exposed and it is not a mystery: at the LOEO cell the entered book pays **$7 / $82 / $67 / $87 per trade** in `e4`..`e7` on **1.1-2.0 trades/day**, and D-021's floor is $600 per trade.  Precision buys the SIGN of the expectancy, not its size — hold-to-close pays **+$507 per winner and -$297 per dud** at every share level we can reach, so the expectancy is `share x 507 - (1-share) x 297`, it crosses zero at a **37%** share and reaches only **+$88/trade at 45%**.  That formula has a ceiling: even a book of pure winners pays **$507/trade**, so at 1.5 trades/day — where a $2,000 day needs $1,333/trade — **no winner share whatever closes the gap**.  The perfect-exit ceiling on the SAME entered book is $74 / $634 / $959 / $1,070 / $1,703 per day, so the cell realises **10-12% of its own ceiling** in the three largest eras (1% in `e4`), against rung 3's 2-6%; but that ceiling is itself below the $1,449-$1,839 two-position ceiling of the top-5 book, because threshold entry raises the fraction converted and lowers the amount available, and the two effects very nearly cancel.

**3. Verdict (b) and (c): YES, 40%+ is reached in all five eras and 45%+ in three of them — and the cells that do it trade 0.2-3.0 times a day, 0.2-1.2 in the four deployment eras.**  Per era, highest share at >= 40 trades: `blind_e3` **43.3%** (3.0 trades/day, 60 trades), `e4` **45.8%** (1.2/day), `e5` **53.6%** (0.6/day), `e6` **42.5%** (0.7/day), `e7` **54.5%** (0.2/day, entered certificate **$1,260**).  The participation cost is the whole story: the preregistered study-quantile bars do not transfer across eras — a `P@top10` bar admits **0.00 to 2.67 candidates/day** against a roster offering **15.2-23.3/day**, i.e. **0.0% to 12.2%** of the roster rather than the 10% it was calibrated to, because the score surface shifts out of era (it admits nothing at all for `E/T/I only` in `blind_e3`, and 12.2% for `v3 no-M` in `e7`).  That under-participation IS the era-adaptivity the design asked for (thin eras get almost no trades, `e7` gets four times as many as `e4`), but it means the share and the count move in opposite directions and the product barely moves.  On the D-019 shape check the news is good and worth keeping: the family that carries the dollars is **hold-to-close at 106-196 minutes and 0.2-2.0 trades/day**, which is exactly D-019's low-frequency long-duration shape; `mirror@1.00` at these cells holds 5-15 minutes and the `cont[lasso,B]@c25` overlay holds **1.0 minute**, which D-019 rejects on sight.  Stated plainly: **precision is what makes hold-to-close the best exit**, and hold-to-close is the only D-019-legal exit in the program.  The conjunction the brief names — mirror AND the overlay together — is degenerate: the overlay fires at minute one on 87-100% of states, so `mirror+overlay` has a mean hold of **0.95 minutes** in every cell and is simply the overlay.  The overlay remains what rung 3 said it was, a drawdown instrument and nothing else: mean 5-day worst-window **-$422 against hold-to-close's -$2,261**, at a cost of essentially all the money.  D-021's <$1,000 daily-drawdown law is met by NO profitable cell at scale: the LOEO cell's worst 5-day window runs **-$1,970 to -$7,419**, and of 4,800 cells only **12** clear (mdd5 > -$1,000, >$50/day, >= 40 trades), none of them in more than one era.

**4. Verdict (d), and what actually paid.**  The label shuffle is clean and decisive: refitting the class-target model on permuted training labels (3 draws, same columns, same frozen hypers, same out-of-fold threshold machinery, same replay) gives an entered-winner share of **14.3-29.2%** — at or below `e7`'s 28.3% base rate — and an entered certificate of **$256-$433**, against the real refit's **36.5-45.6%** and **$630-$773**.  The precision gain is not a thresholding artifact.  Of the four levers tried, exactly one is large: **the arm**.  `E/T/I only` — 134 columns, no v1 and no v2 channel — enters a **45.2%** winner book at threshold geometry against `v3 no-M`'s **32.2%**, which is a bigger single move than every gate and the class target combined, and it is the fourth independent confirmation of that arm's out-of-era ranking advantage.  The three gates are small or self-defeating: `E_gate_clean` adds **+1.8pt** of share but destroys **92%** of the participation (0.72 -> 0.06 trades/day) and is unusable stacked on a threshold; morning-only adds **+0.7pt** for -17% of the trades; the panel do-not-build purge COSTS 1.6pt of share and yet gains **+$8/day** and appears in the LOEO winner, so it is retained as a wash that simplifies the model by 36 columns.  Experiment 3 — the class-target refit on `cert >= $1,000 & MAE <= $300` — is a **null**: it lifts the strict-class share by 0.7pt and the class AUC by up to +0.06, but it LOWERS the $500 winner share (38.3% -> 35.7%) and the dollars (+$28 -> -$8/day), because the deployment class is 9-12% of the roster and the refit trades away the middle of the distribution to chase it.  What this hands forward: the pre-entry object is real and is worth 7x the exit program's best, but it is worth $102/day, and the binding constraint has moved from the exit to the ROSTER — at 45% precision the offer itself only holds ~1.5 payable candidates a day, so the next order of magnitude has to come from more candidates of that quality, not from a better bar on the ones we have.

**Controls.**  This file's trade table reproduces `exit_segments/stop_replay.tsv` to the dollar on all five segments for `close`, `mirror@1.00` and `cont[lasso,B]@c25` (arm `v3 full`, top-5, two positions), so the exit side is rung 1/3's machinery unchanged and only the entry side moves; the reproduction control on the model side lands segment `e` at the published AUC 0.665 (`E/T/I only`) and 0.664 (`v3 no-M`).  Walk-forward purity asserted in code; usable columns from each segment's own training window; the frozen v2 estimator never re-selected; the threshold grid is the preregistered {5,10,15,20}% quantiles of SESSION-GROUPED OUT-OF-FOLD predictions on the training window and is never read off a test block; the design centre was named before the numbers and the LOEO reading selects only on other eras, with `best-in-block` labelled as an upper bound throughout.  576c charged once per trade on every rule including the oracle; the $300 wall monitored from entry with gap-through; two concurrent positions (D-030).  Sealed zone untouched (highest session read 917; `packlib.SEALED_FROM` 918).  Every one of the 4,800 cells is written to `precision_segments/precision_grid.tsv`, not just the winners.  D-022 overlay: era factors 0.879-1.073, carried in the verdict table's RTY column; no share or percentage moves.


## VERDICT TABLE — the full deployment replay, per era

Design-centre arm/target (`v3 no-M`, target `cert >= $500`, no gates) so that one row per (era, geometry) is readable without a maximum being taken; `winner%` is the ENTERED-winner share (the object), `class%` the strict deployment class, `mdd5` the worst 5-day rolling sum (D-021's drawdown panel).

| era | geometry | rule | $/day | RTY-mini | winner% | class% | trades/day | hold min | worst day | mdd5 | $/trade | entered cert |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `blind_e3` | topk3 | `mirror@1.00` | **$60** | $52 | 38.3% | 25.0% | 3.00 | 14 | -$366 | -$929 | $20 | $502 |
| `blind_e3` | topk3 | `overlay` | **-$18** | -$16 | 38.3% | 25.0% | 3.00 | 1 | -$236 | -$425 | -$6 | $502 |
| `blind_e3` | topk3 | `close` | **$230** | $202 | 38.3% | 27.7% | 2.35 | 183 | -$895 | -$1,917 | $98 | $513 |
| `blind_e3` | topk5 | `mirror@1.00` | **-$24** | -$21 | 33.0% | 18.0% | 5.00 | 13 | -$552 | -$1,714 | -$5 | $440 |
| `blind_e3` | topk5 | `overlay` | **-$41** | -$36 | 33.0% | 18.0% | 5.00 | 1 | -$277 | -$678 | -$8 | $440 |
| `blind_e3` | topk5 | `close` | **$239** | $210 | 36.1% | 21.3% | 3.05 | 167 | -$1,193 | -$1,598 | $78 | $493 |
| `blind_e3` | P@top5 | `mirror@1.00` | **$14** | $12 | 25.0% | 25.0% | 0.20 | 8 | -$163 | -$163 | $70 | $580 |
| `blind_e3` | P@top5 | `overlay` | **-$4** | -$4 | 25.0% | 25.0% | 0.20 | 1 | -$99 | -$99 | -$20 | $580 |
| `blind_e3` | P@top5 | `close` | **$23** | $20 | 25.0% | 25.0% | 0.20 | 144 | -$654 | -$654 | $116 | $580 |
| `blind_e3` | P@top10 | `mirror@1.00` | **$24** | $21 | 33.3% | 33.3% | 0.75 | 9 | -$414 | -$422 | $31 | $593 |
| `blind_e3` | P@top10 | `overlay` | **-$15** | -$13 | 33.3% | 33.3% | 0.75 | 1 | -$277 | -$299 | -$20 | $593 |
| `blind_e3` | P@top10 | `close` | **$182** | $160 | 41.7% | 41.7% | 0.60 | 155 | -$947 | -$776 | $303 | $711 |
| `blind_e3` | P@top15 | `mirror@1.00` | **-$8** | -$7 | 31.8% | 31.8% | 1.10 | 7 | -$654 | -$1,045 | -$7 | $508 |
| `blind_e3` | P@top15 | `overlay` | **-$37** | -$32 | 31.8% | 31.8% | 1.10 | 1 | -$534 | -$734 | -$33 | $508 |
| `blind_e3` | P@top15 | `close` | **$176** | $155 | 37.5% | 37.5% | 0.80 | 142 | -$1,270 | -$898 | $220 | $582 |
| `blind_e3` | P@top20 | `mirror@1.00` | **$56** | $49 | 31.4% | 25.7% | 1.75 | 10 | -$654 | -$1,540 | $32 | $486 |
| `blind_e3` | P@top20 | `overlay` | **-$31** | -$27 | 31.4% | 25.7% | 1.75 | 1 | -$534 | -$852 | -$18 | $486 |
| `blind_e3` | P@top20 | `close` | **$199** | $175 | 39.1% | 30.4% | 1.15 | 156 | -$1,530 | -$1,510 | $173 | $549 |
| `e4` | topk3 | `mirror@1.00` | **$62** | $56 | 34.7% | 10.0% | 3.00 | 20 | -$689 | -$1,308 | $21 | $423 |
| `e4` | topk3 | `overlay` | **$21** | $19 | 34.7% | 10.0% | 3.00 | 1 | -$279 | -$268 | $7 | $423 |
| `e4` | topk3 | `close` | **-$60** | -$54 | 36.3% | 8.9% | 2.48 | 140 | -$937 | -$3,982 | -$24 | $433 |
| `e4` | topk5 | `mirror@1.00` | **$48** | $43 | 32.5% | 10.2% | 4.92 | 21 | -$910 | -$2,315 | $10 | $418 |
| `e4` | topk5 | `overlay` | **$22** | $20 | 32.5% | 10.2% | 4.92 | 1 | -$246 | -$533 | $5 | $418 |
| `e4` | topk5 | `close` | **-$57** | -$51 | 33.8% | 9.6% | 3.14 | 141 | -$1,559 | -$4,162 | -$18 | $420 |
| `e4` | P@top5 | `mirror@1.00` | **$1** | $1 | 0.0% | 0.0% | 0.02 | 21 | $0 | $0 | $43 | $262 |
| `e4` | P@top5 | `overlay` | **$0** | $0 | 0.0% | 0.0% | 0.02 | 1 | $0 | $0 | $19 | $262 |
| `e4` | P@top5 | `close` | **-$6** | -$5 | 0.0% | 0.0% | 0.02 | 100 | -$297 | -$297 | -$297 | $262 |
| `e4` | P@top10 | `mirror@1.00` | **-$2** | -$2 | 33.3% | 0.0% | 0.18 | 15 | -$198 | -$392 | -$14 | $421 |
| `e4` | P@top10 | `overlay` | **$2** | $2 | 33.3% | 0.0% | 0.18 | 1 | -$114 | -$132 | $9 | $421 |
| `e4` | P@top10 | `close` | **-$44** | -$40 | 37.5% | 0.0% | 0.16 | 169 | -$624 | -$1,246 | -$277 | $436 |
| `e4` | P@top15 | `mirror@1.00` | **-$15** | -$14 | 30.4% | 13.0% | 0.46 | 11 | -$280 | -$588 | -$33 | $471 |
| `e4` | P@top15 | `overlay` | **-$3** | -$2 | 30.4% | 13.0% | 0.46 | 1 | -$225 | -$335 | -$6 | $471 |
| `e4` | P@top15 | `close` | **-$36** | -$32 | 30.0% | 10.0% | 0.40 | 131 | -$649 | -$2,156 | -$89 | $464 |
| `e4` | P@top20 | `mirror@1.00` | **-$58** | -$52 | 21.7% | 8.7% | 0.92 | 12 | -$792 | -$2,165 | -$63 | $393 |
| `e4` | P@top20 | `overlay` | **-$6** | -$6 | 21.7% | 8.7% | 0.92 | 1 | -$250 | -$464 | -$7 | $393 |
| `e4` | P@top20 | `close` | **-$48** | -$43 | 24.3% | 8.1% | 0.74 | 119 | -$1,559 | -$4,265 | -$65 | $416 |
| `e5` | topk3 | `mirror@1.00` | **-$20** | -$20 | 28.0% | 8.7% | 3.00 | 18 | -$514 | -$1,536 | -$7 | $374 |
| `e5` | topk3 | `overlay` | **-$7** | -$7 | 28.0% | 8.7% | 3.00 | 1 | -$270 | -$478 | -$2 | $374 |
| `e5` | topk3 | `close` | **-$78** | -$79 | 29.8% | 9.3% | 2.48 | 154 | -$1,092 | -$4,491 | -$32 | $389 |
| `e5` | topk5 | `mirror@1.00` | **-$52** | -$52 | 27.9% | 8.3% | 4.98 | 19 | -$726 | -$2,359 | -$10 | $372 |
| `e5` | topk5 | `overlay` | **-$18** | -$18 | 27.9% | 8.3% | 4.98 | 1 | -$497 | -$703 | -$4 | $372 |
| `e5` | topk5 | `close` | **-$117** | -$117 | 28.8% | 9.2% | 3.12 | 150 | -$1,544 | -$5,389 | -$37 | $379 |
| `e5` | P@top5 | `mirror@1.00` | **-$9** | -$9 | 34.5% | 13.8% | 0.23 | 8 | -$309 | -$487 | -$38 | $424 |
| `e5` | P@top5 | `overlay` | **-$3** | -$3 | 34.5% | 13.8% | 0.23 | 1 | -$497 | -$497 | -$15 | $424 |
| `e5` | P@top5 | `close` | **-$0** | -$0 | 36.0% | 16.0% | 0.20 | 110 | -$654 | -$984 | -$2 | $459 |
| `e5` | P@top10 | `mirror@1.00` | **-$8** | -$8 | 27.5% | 10.8% | 0.95 | 10 | -$586 | -$1,151 | -$9 | $379 |
| `e5` | P@top10 | `overlay` | **-$6** | -$6 | 27.5% | 10.8% | 0.95 | 1 | -$625 | -$625 | -$6 | $379 |
| `e5` | P@top10 | `close` | **-$61** | -$62 | 29.8% | 11.7% | 0.75 | 118 | -$1,847 | -$2,792 | -$82 | $407 |
| `e5` | P@top15 | `mirror@1.00` | **-$23** | -$23 | 30.4% | 13.7% | 1.62 | 11 | -$586 | -$1,214 | -$14 | $411 |
| `e5` | P@top15 | `overlay` | **-$2** | -$2 | 30.4% | 13.7% | 1.62 | 1 | -$836 | -$847 | -$1 | $411 |
| `e5` | P@top15 | `close` | **-$55** | -$55 | 32.9% | 14.7% | 1.13 | 126 | -$2,155 | -$3,653 | -$49 | $443 |
| `e5` | P@top20 | `mirror@1.00` | **-$42** | -$42 | 30.4% | 14.1% | 2.25 | 10 | -$595 | -$1,624 | -$18 | $423 |
| `e5` | P@top20 | `overlay` | **-$4** | -$4 | 30.3% | 14.1% | 2.25 | 1 | -$886 | -$886 | -$2 | $423 |
| `e5` | P@top20 | `close` | **-$71** | -$71 | 30.1% | 14.5% | 1.37 | 129 | -$2,672 | -$4,857 | -$52 | $435 |
| `e6` | topk3 | `mirror@1.00` | **$56** | $61 | 33.3% | 13.1% | 3.00 | 18 | -$652 | -$1,510 | $19 | $435 |
| `e6` | topk3 | `overlay` | **-$17** | -$18 | 33.3% | 13.1% | 3.00 | 1 | -$307 | -$531 | -$6 | $435 |
| `e6` | topk3 | `close` | **$10** | $11 | 34.3% | 13.4% | 2.53 | 145 | -$1,015 | -$4,077 | $4 | $450 |
| `e6` | topk5 | `mirror@1.00` | **$46** | $50 | 32.4% | 11.9% | 4.96 | 17 | -$817 | -$1,872 | $9 | $414 |
| `e6` | topk5 | `overlay` | **-$49** | -$53 | 32.4% | 11.9% | 4.94 | 1 | -$638 | -$960 | -$10 | $414 |
| `e6` | topk5 | `close` | **-$73** | -$80 | 33.0% | 13.3% | 3.22 | 140 | -$1,580 | -$5,737 | -$23 | $431 |
| `e6` | P@top5 | `mirror@1.00` | **-$12** | -$13 | 27.7% | 12.5% | 1.00 | 7 | -$1,199 | -$1,231 | -$12 | $399 |
| `e6` | P@top5 | `overlay` | **-$15** | -$16 | 27.7% | 12.5% | 1.00 | 1 | -$1,122 | -$1,130 | -$15 | $399 |
| `e6` | P@top5 | `close` | **$14** | $15 | 30.3% | 15.8% | 0.68 | 112 | -$2,600 | -$2,600 | $20 | $465 |
| `e6` | P@top10 | `mirror@1.00` | **-$17** | -$19 | 29.8% | 17.0% | 1.95 | 10 | -$992 | -$1,244 | -$9 | $456 |
| `e6` | P@top10 | `overlay` | **-$21** | -$23 | 29.8% | 17.0% | 1.95 | 1 | -$892 | -$982 | -$11 | $456 |
| `e6` | P@top10 | `close` | **$29** | $32 | 31.6% | 18.0% | 1.19 | 118 | -$2,901 | -$3,292 | $25 | $491 |
| `e6` | P@top15 | `mirror@1.00` | **-$26** | -$28 | 30.3% | 15.0% | 2.86 | 10 | -$1,248 | -$1,623 | -$9 | $441 |
| `e6` | P@top15 | `overlay` | **-$20** | -$22 | 30.4% | 15.0% | 2.85 | 1 | -$1,097 | -$1,309 | -$7 | $443 |
| `e6` | P@top15 | `close` | **$11** | $12 | 34.0% | 16.0% | 1.68 | 127 | -$3,210 | -$4,470 | $7 | $483 |
| `e6` | P@top20 | `mirror@1.00` | **-$39** | -$43 | 30.5% | 13.9% | 3.66 | 10 | -$1,775 | -$2,295 | -$11 | $439 |
| `e6` | P@top20 | `overlay` | **-$18** | -$20 | 30.5% | 13.9% | 3.66 | 1 | -$938 | -$1,149 | -$5 | $438 |
| `e6` | P@top20 | `close` | **-$30** | -$33 | 34.8% | 13.9% | 2.18 | 127 | -$4,726 | -$7,567 | -$14 | $476 |
| `e7` | topk3 | `mirror@1.00` | **$30** | $32 | 35.0% | 12.9% | 3.00 | 19 | -$854 | -$1,919 | $10 | $482 |
| `e7` | topk3 | `overlay` | **$11** | $12 | 35.0% | 12.9% | 3.00 | 1 | -$514 | -$1,080 | $4 | $482 |
| `e7` | topk3 | `close` | **$76** | $81 | 34.8% | 13.4% | 2.56 | 146 | -$982 | -$4,132 | $30 | $478 |
| `e7` | topk5 | `mirror@1.00` | **$5** | $6 | 32.1% | 11.6% | 4.96 | 19 | -$1,309 | -$2,399 | $1 | $449 |
| `e7` | topk5 | `overlay` | **-$5** | -$5 | 32.1% | 11.6% | 4.96 | 1 | -$459 | -$903 | -$1 | $449 |
| `e7` | topk5 | `close` | **$54** | $58 | 33.1% | 13.1% | 3.29 | 141 | -$1,642 | -$5,726 | $16 | $463 |
| `e7` | P@top5 | `mirror@1.00` | **$61** | $66 | 41.8% | 25.5% | 0.54 | 5 | -$1,453 | -$1,453 | $113 | $808 |
| `e7` | P@top5 | `overlay` | **$36** | $39 | 41.8% | 25.5% | 0.54 | 1 | -$410 | -$410 | $67 | $808 |
| `e7` | P@top5 | `close` | **-$5** | -$6 | 37.1% | 22.6% | 0.34 | 57 | -$3,123 | -$5,509 | -$16 | $835 |
| `e7` | P@top10 | `mirror@1.00` | **$62** | $67 | 37.3% | 22.4% | 1.11 | 7 | -$1,427 | -$1,209 | $56 | $691 |
| `e7` | P@top10 | `overlay` | **$27** | $29 | 37.3% | 22.4% | 1.11 | 1 | -$764 | -$895 | $24 | $691 |
| `e7` | P@top10 | `close` | **-$5** | -$5 | 33.1% | 19.2% | 0.72 | 62 | -$5,557 | -$5,977 | -$7 | $669 |
| `e7` | P@top15 | `mirror@1.00` | **$85** | $91 | 38.5% | 22.1% | 1.98 | 9 | -$1,262 | -$2,309 | $43 | $671 |
| `e7` | P@top15 | `overlay` | **$38** | $40 | 38.4% | 22.0% | 1.98 | 1 | -$783 | -$823 | $19 | $669 |
| `e7` | P@top15 | `close` | **$24** | $26 | 38.8% | 20.6% | 1.18 | 92 | -$4,950 | -$8,572 | $20 | $640 |
| `e7` | P@top20 | `mirror@1.00` | **$63** | $67 | 38.3% | 20.8% | 2.92 | 9 | -$1,608 | -$2,926 | $22 | $626 |
| `e7` | P@top20 | `overlay` | **$26** | $28 | 38.2% | 20.8% | 2.92 | 1 | -$1,171 | -$1,773 | $9 | $625 |
| `e7` | P@top20 | `close` | **$96** | $103 | 39.5% | 21.0% | 1.58 | 105 | -$3,342 | -$6,124 | $61 | $630 |

## The three readings of each era: design centre, leave-one-era-out, and the in-block maximum

`LOEO` picks the (arm, variant, target, gates, geometry, rule) cell by the mean realised $/day over the other DEPLOYMENT eras (`e4..e7`; the 20-day `blind_e3` control is never a selection basis) and reads it off this one — nothing is selected on the block it is scored on.  `best-in-block` IS a maximum over 960 cells of this era's own test block and is reported as an upper bound, never as a deployable number.

| era | reading | cell | $/day | winner% | class% | trades/day | hold min | worst day | mdd5 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `blind_e3` | design centre | v3 no-M/base/w500/none/P@top10/`mirror@1.00` | **$24** | 33.3% | 33.3% | 0.75 | 9 | -$414 | -$422 |
| `blind_e3` | LOEO | E/T/I only/purge/w500/none/P@top20/`close` | **-$4** | 20.0% | 20.0% | 0.25 | 82 | -$871 | -$1,170 |
| `blind_e3` | best-in-block | v3 no-M/base/wclass/morning/topk5/`close` | **$385** | 37.9% | 20.7% | 2.90 | 180 | -$1,203 | -$2,314 |
| `e4` | design centre | v3 no-M/base/w500/none/P@top10/`mirror@1.00` | **-$2** | 33.3% | 0.0% | 0.18 | 15 | -$198 | -$392 |
| `e4` | LOEO | E/T/I only/purge/w500/none/P@top20/`close` | **$8** | 45.3% | 15.1% | 1.06 | 138 | -$957 | -$2,219 |
| `e4` | best-in-block | E/T/I only/purge/wclass/none/topk3/`mirror@1.00` | **$113** | 40.7% | 13.3% | 3.00 | 18 | -$475 | -$1,352 |
| `e5` | design centre | v3 no-M/base/w500/none/P@top10/`mirror@1.00` | **-$8** | 27.5% | 10.8% | 0.95 | 10 | -$586 | -$1,151 |
| `e5` | LOEO | E/T/I only/purge/w500/none/P@top20/`close` | **$119** | 37.2% | 22.4% | 1.45 | 146 | -$1,224 | -$1,968 |
| `e5` | best-in-block | E/T/I only/purge/w500/none/P@top20/`close` | **$119** | 37.2% | 22.4% | 1.45 | 146 | -$1,224 | -$1,968 |
| `e6` | design centre | v3 no-M/base/w500/none/P@top10/`mirror@1.00` | **-$17** | 29.8% | 17.0% | 1.95 | 10 | -$992 | -$1,244 |
| `e6` | LOEO | E/T/I only/purge/w500/none/P@top20/`close` | **$108** | 39.2% | 17.7% | 1.62 | 134 | -$1,247 | -$2,513 |
| `e6` | best-in-block | E/T/I only/purge/w500/none/P@top20/`close` | **$108** | 39.2% | 17.7% | 1.62 | 134 | -$1,247 | -$2,513 |
| `e7` | design centre | v3 no-M/base/w500/none/P@top10/`mirror@1.00` | **$62** | 37.3% | 22.4% | 1.11 | 7 | -$1,427 | -$1,209 |
| `e7` | LOEO | E/T/I only/purge/w500/none/P@top20/`close` | **$174** | 38.3% | 19.7% | 1.99 | 107 | -$4,049 | -$7,419 |
| `e7` | best-in-block | v3 no-M/base/wclass/none/P@top20/`close` | **$199** | 37.6% | 22.5% | 2.09 | 117 | -$6,373 | -$7,635 |

## EXPERIMENT 1 — threshold geometry: what precision costs and what it buys

Pooled over the five eras, both arms, both targets, both column variants, no gates.  `entered cert` is the mean exit-free certificate of the trades actually taken (D-021's per-trade bar is $1,000).

| geometry | rule | winner% | class% | entered cert | trades/day | hold min | $/trade | $/winner | $/dud | $/day | mdd5 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| topk3 | `close` | 32.4% | 12.9% | $428 | 2.48 | 147 | -$8 | $519 | -$258 | -$20 | -$3,750 |
| topk3 | `mirror@1.00` | 32.3% | 12.6% | $425 | 3.00 | 17 | $5 | $157 | -$69 | $16 | -$1,428 |
| topk3 | `overlay` | 32.3% | 12.6% | $425 | 3.00 | 1 | -$2 | $19 | -$13 | -$7 | -$625 |
| topk3 | `mirror+overlay` | 32.3% | 12.6% | $425 | 3.00 | 1 | -$3 | $18 | -$13 | -$8 | -$589 |
| topk3 | `oracle` | 32.4% | 12.6% | $425 | 2.76 | 81 | $435 | $1,018 | $157 | $1,202 | $2,602 |
| topk5 | `close` | 32.5% | 13.1% | $433 | 3.12 | 146 | -$1 | $524 | -$252 | -$4 | -$4,295 |
| topk5 | `mirror@1.00` | 31.3% | 12.1% | $418 | 4.95 | 17 | -$2 | $142 | -$68 | -$9 | -$2,015 |
| topk5 | `overlay` | 31.3% | 12.1% | $418 | 4.96 | 1 | -$3 | $18 | -$13 | -$16 | -$746 |
| topk5 | `mirror+overlay` | 31.3% | 12.1% | $418 | 4.96 | 1 | -$3 | $17 | -$13 | -$17 | -$740 |
| topk5 | `oracle` | 33.6% | 13.0% | $439 | 3.78 | 84 | $451 | $1,023 | $163 | $1,706 | $4,216 |
| P@top5 | `close` | 35.7% | 15.1% | $477 | 0.28 | 97 | -$26 | $537 | -$279 | $1 | -$2,066 |
| P@top5 | `mirror@1.00` | 35.9% | 15.6% | $481 | 0.42 | 8 | $8 | $200 | -$100 | $7 | -$659 |
| P@top5 | `overlay` | 36.0% | 15.7% | $483 | 0.42 | 1 | -$15 | $75 | -$56 | $3 | -$414 |
| P@top5 | `mirror+overlay` | 36.1% | 15.7% | $483 | 0.42 | 1 | -$8 | $70 | -$46 | $4 | -$348 |
| P@top5 | `oracle` | 35.3% | 15.4% | $472 | 0.33 | 43 | $496 | $1,382 | $97 | $197 | -$102 |
| P@top10 | `close` | 37.3% | 16.8% | $513 | 0.57 | 112 | -$6 | $476 | -$291 | $0 | -$3,243 |
| P@top10 | `mirror@1.00` | 38.2% | 18.5% | $532 | 0.91 | 8 | $10 | $175 | -$93 | $5 | -$1,160 |
| P@top10 | `overlay` | 38.2% | 18.6% | $532 | 0.91 | 1 | -$2 | $54 | -$36 | $1 | -$549 |
| P@top10 | `mirror+overlay` | 38.3% | 18.6% | $533 | 0.91 | 1 | -$1 | $50 | -$32 | $2 | -$519 |
| P@top10 | `oracle` | 37.4% | 17.9% | $518 | 0.67 | 55 | $541 | $1,273 | $126 | $379 | -$105 |
| P@top15 | `close` | 37.3% | 21.6% | $521 | 0.85 | 121 | $46 | $593 | -$286 | $17 | -$3,480 |
| P@top15 | `mirror@1.00` | 38.5% | 23.0% | $538 | 1.46 | 9 | $5 | $169 | -$94 | $2 | -$1,668 |
| P@top15 | `overlay` | 38.5% | 23.0% | $538 | 1.46 | 1 | -$6 | $40 | -$33 | -$1 | -$710 |
| P@top15 | `mirror+overlay` | 38.5% | 23.0% | $538 | 1.46 | 1 | -$6 | $35 | -$31 | -$1 | -$686 |
| P@top15 | `oracle` | 37.5% | 22.5% | $525 | 1.02 | 68 | $558 | $1,286 | $125 | $578 | -$96 |
| P@top20 | `close` | 34.7% | 17.9% | $498 | 1.18 | 120 | $20 | $599 | -$283 | $23 | -$4,348 |
| P@top20 | `mirror@1.00` | 34.9% | 18.7% | $501 | 2.10 | 9 | -$6 | $158 | -$94 | -$6 | -$2,026 |
| P@top20 | `overlay` | 34.9% | 18.7% | $502 | 2.11 | 1 | -$7 | $38 | -$32 | -$5 | -$899 |
| P@top20 | `mirror+overlay` | 34.9% | 18.7% | $502 | 2.11 | 1 | -$8 | $32 | -$31 | -$6 | -$851 |
| P@top20 | `oracle` | 34.8% | 18.6% | $499 | 1.41 | 66 | $525 | $1,273 | $130 | $776 | -$40 |

## How high does the entered-winner share actually go?

The maximum entered-winner share reached in each era over the whole grid, restricted to cells that entered at least 40 trades (a 20-trade cell can print 60% on noise).  This is the object the brief names, and the columns beside it are what that precision costs and pays.

| era | max winner% | cell | trades | trades/day | hold min | entered cert | $/trade | $/day | mdd5 |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `blind_e3` | **40.4%** | v3 no-M/purge/w500/morning/topk3/`close` | 47 | 2.35 | 196 | $552 | $122 | $287 | -$1,357 |
| `blind_e3` | **43.3%** | v3 no-M/purge/w500/morning/topk3/`mirror@1.00` | 60 | 3.00 | 15 | $574 | $29 | $87 | -$1,056 |
| `e4` | **45.3%** | E/T/I only/purge/w500/none/P@top20/`close` | 53 | 1.06 | 138 | $541 | $7 | $8 | -$2,219 |
| `e4` | **45.8%** | v3 no-M/base/wclass/none/P@top20/`mirror@1.00` | 59 | 1.18 | 10 | $560 | $9 | $10 | -$605 |
| `e5` | **53.3%** | v3 no-M/purge/wclass/morning/P@top10/`close` | 45 | 0.36 | 191 | $716 | $229 | $82 | -$1,341 |
| `e5` | **53.6%** | v3 no-M/purge/wclass/morning/P@top10/`mirror@1.00` | 69 | 0.55 | 8 | $714 | $29 | $16 | -$379 |
| `e6` | **41.5%** | E/T/I only/purge/w500/morning/P@top5/`close` | 65 | 0.58 | 150 | $580 | $73 | $42 | -$1,286 |
| `e6` | **42.5%** | E/T/I only/purge/w500/morning/P@top5/`mirror@1.00` | 80 | 0.71 | 9 | $609 | $3 | $2 | -$865 |
| `e7` | **47.3%** | E/T/I only/base/w500/morning/P@top15/`close` | 129 | 0.71 | 115 | $694 | $59 | $42 | -$4,247 |
| `e7` | **54.5%** | E/T/I only/base/wclass/gate_clean/P@top15/`mirror@1.00` | 44 | 0.24 | 9 | $1,260 | $54 | $13 | -$462 |

## THE OBJECT, answered directly — what a percentage point of entered-winner share is worth

Every cell of the grid with at least 40 trades, binned by its own entered-winner share.  `$/trade` is the realised expectancy per trade (D-021's floor is $600, its target $1,000); `$/day` is the era's realised mean.

| winner% bin | rule | cells | trades/day | entered cert | $/trade | $/winner | $/dud | $/day | mdd5 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| <30% | `close` | 120 | 1.19 | $397 | -$60 | $534 | -$265 | -$59 | -$3,122 |
| <30% | `mirror@1.00` | 124 | 1.88 | $389 | -$24 | $121 | -$74 | -$32 | -$1,388 |
| <30% | `overlay` | 124 | 1.90 | $388 | -$9 | $16 | -$18 | -$15 | -$554 |
| 30-35% | `close` | 172 | 1.88 | $464 | -$3 | $528 | -$258 | -$6 | -$4,154 |
| 30-35% | `mirror@1.00` | 191 | 2.66 | $459 | $2 | $169 | -$79 | $3 | -$1,781 |
| 30-35% | `overlay` | 191 | 2.67 | $458 | -$5 | $22 | -$19 | -$10 | -$767 |
| 35-40% | `close` | 117 | 1.63 | $553 | $30 | $539 | -$275 | $43 | -$4,078 |
| 35-40% | `mirror@1.00` | 108 | 2.18 | $574 | $14 | $202 | -$98 | $23 | -$1,971 |
| 35-40% | `overlay` | 107 | 2.15 | $575 | $2 | $61 | -$33 | $7 | -$911 |
| 40-45% | `close` | 32 | 0.91 | $636 | $25 | $461 | -$295 | $14 | -$4,680 |
| 40-45% | `mirror@1.00` | 35 | 1.15 | $664 | $31 | $204 | -$95 | $30 | -$1,054 |
| 40-45% | `overlay` | 37 | 1.15 | $658 | $13 | $72 | -$30 | $12 | -$576 |
| >=45% | `close` | 8 | 0.58 | $693 | $88 | $507 | -$297 | $41 | -$3,213 |
| >=45% | `mirror@1.00` | 23 | 0.49 | $1,011 | $48 | $211 | -$116 | $15 | -$720 |
| >=45% | `overlay` | 22 | 0.46 | $1,031 | $5 | $49 | -$39 | $2 | -$360 |

## EXPERIMENTS 2 and 3 — the gates and the class target

Each factor moved one at a time against the same baseline (pooled over eras, arms and the four threshold geometries; `close` and `mirror@1.00` shown because they are the two exits that carry dollars).

| factor | level | rule | winner% | class% | entered cert | trades/day | $/day | mdd5 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| gates | none | `close` | 38.3% | 17.5% | $555 | 0.72 | $28 | -$2,975 |
| gates | none | `mirror@1.00` | 37.4% | 17.7% | $544 | 1.11 | $5 | -$1,142 |
| gates | gate_clean | `close` | 40.1% | 17.5% | $597 | 0.06 | $4 | -$531 |
| gates | gate_clean | `mirror@1.00` | 40.4% | 17.9% | $613 | 0.06 | -$0 | -$239 |
| gates | morning | `close` | 39.0% | 17.2% | $562 | 0.60 | $20 | -$2,324 |
| gates | morning | `mirror@1.00` | 37.5% | 17.2% | $539 | 0.87 | -$1 | -$1,038 |
| gates | gate_clean+morning | `close` | 40.9% | 18.1% | $615 | 0.06 | $5 | -$498 |
| gates | gate_clean+morning | `mirror@1.00` | 41.2% | 18.4% | $630 | 0.06 | $0 | -$232 |
| column set | base | `close` | 38.3% | 17.5% | $555 | 0.72 | $28 | -$2,975 |
| column set | base | `mirror@1.00` | 37.4% | 17.7% | $544 | 1.11 | $5 | -$1,142 |
| column set | purge | `close` | 36.7% | 18.7% | $534 | 0.86 | $36 | -$3,430 |
| column set | purge | `mirror@1.00` | 35.6% | 18.8% | $528 | 1.38 | $5 | -$1,444 |
| target | w500 | `close` | 38.3% | 17.5% | $555 | 0.72 | $28 | -$2,975 |
| target | w500 | `mirror@1.00` | 37.4% | 17.7% | $544 | 1.11 | $5 | -$1,142 |
| target | wclass | `close` | 35.7% | 18.2% | $468 | 0.66 | -$8 | -$3,417 |
| target | wclass | `mirror@1.00` | 37.9% | 20.0% | $500 | 1.20 | -$1 | -$1,509 |
| arm | E/T/I only | `close` | 45.2% | 17.0% | $591 | 0.58 | $36 | -$2,540 |
| arm | E/T/I only | `mirror@1.00` | 45.3% | 18.5% | $600 | 0.91 | $5 | -$1,030 |
| arm | v3 no-M | `close` | 32.2% | 17.8% | $522 | 0.85 | $20 | -$3,410 |
| arm | v3 no-M | `mirror@1.00` | 30.2% | 17.0% | $494 | 1.32 | $5 | -$1,254 |

## The fits — frozen config, walk-forward, one refit per (arm, column set, target)

`AUC(w500)` scores the fitted model against the roster's own winner label, `AUC(class)` against the deployment class (`cert >= $1,000 & MAE <= $300`).  The reproduction control is segment `e`: `E/T/I only` must land on the published 0.665 and `v3 no-M` on 0.664.

| seg | era | arm | column set | target | features | train pos rate | AUC(w500) | AUC(class) | OOF AUC |
|---|---|---|---|---|---:|---:|---:|---:|---:|
| e | `blind_e3` | E/T/I only | base | w500 | 134 | 28.6% | 0.7 | 0.7 | 0.6 |
| e | `blind_e3` | E/T/I only | base | wclass | 134 | 10.8% | 0.7 | 0.7 | 0.7 |
| e | `blind_e3` | E/T/I only | purge | w500 | 131 | 28.6% | 0.7 | 0.7 | 0.6 |
| e | `blind_e3` | E/T/I only | purge | wclass | 131 | 10.8% | 0.7 | 0.7 | 0.7 |
| e | `blind_e3` | v3 no-M | base | w500 | 408 | 28.6% | 0.7 | 0.7 | 0.6 |
| e | `blind_e3` | v3 no-M | base | wclass | 408 | 10.8% | 0.7 | 0.7 | 0.7 |
| e | `blind_e3` | v3 no-M | purge | w500 | 372 | 28.6% | 0.7 | 0.7 | 0.6 |
| e | `blind_e3` | v3 no-M | purge | wclass | 372 | 10.8% | 0.7 | 0.7 | 0.7 |
| f | `e4` | E/T/I only | base | w500 | 134 | 28.5% | 0.6 | 0.6 | 0.6 |
| f | `e4` | E/T/I only | base | wclass | 134 | 10.8% | 0.6 | 0.6 | 0.7 |
| f | `e4` | E/T/I only | purge | w500 | 131 | 28.5% | 0.6 | 0.6 | 0.6 |
| f | `e4` | E/T/I only | purge | wclass | 131 | 10.8% | 0.6 | 0.6 | 0.7 |
| f | `e4` | v3 no-M | base | w500 | 408 | 28.5% | 0.6 | 0.6 | 0.6 |
| f | `e4` | v3 no-M | base | wclass | 408 | 10.8% | 0.6 | 0.6 | 0.7 |
| f | `e4` | v3 no-M | purge | w500 | 372 | 28.5% | 0.6 | 0.6 | 0.6 |
| f | `e4` | v3 no-M | purge | wclass | 372 | 10.8% | 0.6 | 0.6 | 0.7 |
| g | `e5` | E/T/I only | base | w500 | 134 | 28.5% | 0.6 | 0.7 | 0.6 |
| g | `e5` | E/T/I only | base | wclass | 134 | 10.8% | 0.6 | 0.7 | 0.7 |
| g | `e5` | E/T/I only | purge | w500 | 131 | 28.5% | 0.6 | 0.7 | 0.6 |
| g | `e5` | E/T/I only | purge | wclass | 131 | 10.8% | 0.6 | 0.7 | 0.7 |
| g | `e5` | v3 no-M | base | w500 | 408 | 28.5% | 0.6 | 0.7 | 0.6 |
| g | `e5` | v3 no-M | base | wclass | 408 | 10.8% | 0.6 | 0.7 | 0.7 |
| g | `e5` | v3 no-M | purge | w500 | 372 | 28.5% | 0.6 | 0.7 | 0.6 |
| g | `e5` | v3 no-M | purge | wclass | 372 | 10.8% | 0.6 | 0.7 | 0.7 |
| h | `e6` | E/T/I only | base | w500 | 134 | 27.9% | 0.6 | 0.7 | 0.6 |
| h | `e6` | E/T/I only | base | wclass | 134 | 10.5% | 0.6 | 0.7 | 0.7 |
| h | `e6` | E/T/I only | purge | w500 | 131 | 27.9% | 0.6 | 0.7 | 0.6 |
| h | `e6` | E/T/I only | purge | wclass | 131 | 10.5% | 0.6 | 0.7 | 0.7 |
| h | `e6` | v3 no-M | base | w500 | 408 | 27.9% | 0.6 | 0.7 | 0.6 |
| h | `e6` | v3 no-M | base | wclass | 408 | 10.5% | 0.6 | 0.7 | 0.7 |
| h | `e6` | v3 no-M | purge | w500 | 372 | 27.9% | 0.6 | 0.7 | 0.6 |
| h | `e6` | v3 no-M | purge | wclass | 372 | 10.5% | 0.6 | 0.7 | 0.7 |
| i | `e7` | E/T/I only | base | w500 | 134 | 27.7% | 0.6 | 0.7 | 0.6 |
| i | `e7` | E/T/I only | base | wclass | 134 | 10.4% | 0.6 | 0.7 | 0.7 |
| i | `e7` | E/T/I only | purge | w500 | 131 | 27.7% | 0.6 | 0.7 | 0.6 |
| i | `e7` | E/T/I only | purge | wclass | 131 | 10.4% | 0.6 | 0.7 | 0.7 |
| i | `e7` | v3 no-M | base | w500 | 408 | 27.7% | 0.6 | 0.7 | 0.6 |
| i | `e7` | v3 no-M | base | wclass | 408 | 10.4% | 0.6 | 0.7 | 0.7 |
| i | `e7` | v3 no-M | purge | w500 | 372 | 27.7% | 0.6 | 0.7 | 0.6 |
| i | `e7` | v3 no-M | purge | wclass | 372 | 10.4% | 0.6 | 0.7 | 0.7 |

## The preregistered thresholds — study quantiles, and what they actually admit out of era

The bar is the (1 - q) quantile of SESSION-GROUPED OUT-OF-FOLD predictions on each segment's own training window.  If the score surface were era-stationary, `P@top10` would admit ~10% of the test block's candidates; the admitted column is what it really admits, and it is the era-adaptivity of the design arriving as under-participation.

| era | candidates/day | arm | target | P@top5 | P@top10 | P@top15 | P@top20 | admitted @top10 | @top10 as % of roster |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| `blind_e3` | 23.3 | E/T/I only | w500 | 0.3794 | 0.3668 | 0.3585 | 0.3521 | 0.00/day | 0.0% |
| `blind_e3` | 23.3 | E/T/I only | wclass | 0.2099 | 0.1952 | 0.1837 | 0.1751 | 0.00/day | 0.0% |
| `blind_e3` | 23.3 | v3 no-M | w500 | 0.3992 | 0.3799 | 0.3667 | 0.3573 | 0.75/day | 3.2% |
| `blind_e3` | 23.3 | v3 no-M | wclass | 0.2284 | 0.2016 | 0.1848 | 0.1723 | 0.25/day | 1.1% |
| `e4` | 15.2 | E/T/I only | w500 | 0.3780 | 0.3660 | 0.3590 | 0.3536 | 0.04/day | 0.3% |
| `e4` | 15.2 | E/T/I only | wclass | 0.2090 | 0.1942 | 0.1838 | 0.1747 | 0.14/day | 0.9% |
| `e4` | 15.2 | v3 no-M | w500 | 0.3953 | 0.3776 | 0.3663 | 0.3574 | 0.18/day | 1.2% |
| `e4` | 15.2 | v3 no-M | wclass | 0.2295 | 0.2034 | 0.1862 | 0.1715 | 0.18/day | 1.2% |
| `e5` | 17.8 | E/T/I only | w500 | 0.3672 | 0.3558 | 0.3506 | 0.3460 | 1.16/day | 6.5% |
| `e5` | 17.8 | E/T/I only | wclass | 0.2065 | 0.1909 | 0.1810 | 0.1724 | 0.40/day | 2.3% |
| `e5` | 17.8 | v3 no-M | w500 | 0.3899 | 0.3725 | 0.3624 | 0.3543 | 0.95/day | 5.3% |
| `e5` | 17.8 | v3 no-M | wclass | 0.2208 | 0.1971 | 0.1805 | 0.1677 | 0.79/day | 4.4% |
| `e6` | 18.9 | E/T/I only | w500 | 0.3639 | 0.3547 | 0.3491 | 0.3461 | 0.59/day | 3.1% |
| `e6` | 18.9 | E/T/I only | wclass | 0.2022 | 0.1854 | 0.1758 | 0.1673 | 1.24/day | 6.6% |
| `e6` | 18.9 | v3 no-M | w500 | 0.3801 | 0.3639 | 0.3547 | 0.3473 | 1.95/day | 10.3% |
| `e6` | 18.9 | v3 no-M | wclass | 0.2158 | 0.1932 | 0.1775 | 0.1651 | 1.49/day | 7.9% |
| `e7` | 21.9 | E/T/I only | w500 | 0.3656 | 0.3559 | 0.3506 | 0.3461 | 1.12/day | 5.1% |
| `e7` | 21.9 | E/T/I only | wclass | 0.1990 | 0.1838 | 0.1734 | 0.1658 | 1.88/day | 8.6% |
| `e7` | 21.9 | v3 no-M | w500 | 0.3726 | 0.3602 | 0.3528 | 0.3479 | 1.11/day | 5.1% |
| `e7` | 21.9 | v3 no-M | wclass | 0.2075 | 0.1874 | 0.1734 | 0.1624 | 2.67/day | 12.2% |

## Control — label shuffle on the class-target refit (segment i, `E/T/I only`)

The identical refit on PERMUTED training labels, through the identical OOF threshold machinery and the identical replay.  3 draws.

| draw | geometry | rule | $/day | winner% | class% | trades/day | entered cert |
|---|---|---|---:|---:|---:|---:|---:|
| shuffle0 | P@top5 | `close` | -$43 | 27.2% | 9.9% | 3.03 | $413 |
| shuffle0 | P@top5 | `mirror@1.00` | $25 | 26.8% | 9.9% | 5.25 | $411 |
| shuffle0 | P@top5 | `overlay` | $7 | 26.8% | 9.9% | 5.25 | $412 |
| shuffle0 | P@top10 | `close` | -$11 | 27.8% | 10.5% | 3.52 | $426 |
| shuffle0 | P@top10 | `mirror@1.00` | $48 | 27.1% | 10.5% | 6.94 | $425 |
| shuffle0 | P@top10 | `overlay` | $18 | 27.1% | 10.6% | 6.94 | $426 |
| shuffle0 | P@top15 | `close` | -$45 | 28.1% | 10.7% | 3.76 | $425 |
| shuffle0 | P@top15 | `mirror@1.00` | $11 | 26.8% | 10.4% | 7.80 | $412 |
| shuffle0 | P@top15 | `overlay` | $4 | 26.8% | 10.5% | 7.80 | $413 |
| shuffle0 | P@top20 | `close` | -$38 | 28.4% | 11.2% | 3.85 | $427 |
| shuffle0 | P@top20 | `mirror@1.00` | -$12 | 26.6% | 10.4% | 8.33 | $409 |
| shuffle0 | P@top20 | `overlay` | -$1 | 26.6% | 10.5% | 8.33 | $410 |
| shuffle1 | P@top5 | `close` | -$52 | 14.3% | 5.4% | 0.31 | $256 |
| shuffle1 | P@top5 | `mirror@1.00` | -$8 | 14.3% | 5.4% | 0.31 | $256 |
| shuffle1 | P@top5 | `overlay` | -$5 | 14.3% | 5.4% | 0.31 | $256 |
| shuffle1 | P@top10 | `close` | -$69 | 21.3% | 11.0% | 0.91 | $409 |
| shuffle1 | P@top10 | `mirror@1.00` | -$2 | 21.1% | 11.1% | 0.94 | $408 |
| shuffle1 | P@top10 | `overlay` | -$10 | 21.1% | 11.1% | 0.94 | $408 |
| shuffle1 | P@top15 | `close` | -$116 | 19.3% | 8.7% | 1.83 | $346 |
| shuffle1 | P@top15 | `mirror@1.00` | -$24 | 19.2% | 9.4% | 2.13 | $353 |
| shuffle1 | P@top15 | `overlay` | -$10 | 19.2% | 9.4% | 2.13 | $353 |
| shuffle1 | P@top20 | `close` | -$110 | 23.5% | 10.1% | 2.35 | $377 |
| shuffle1 | P@top20 | `mirror@1.00` | -$31 | 22.3% | 9.8% | 2.94 | $378 |
| shuffle1 | P@top20 | `overlay` | -$6 | 22.3% | 9.8% | 2.94 | $378 |
| shuffle2 | P@top5 | `close` | -$33 | 22.3% | 9.4% | 0.77 | $392 |
| shuffle2 | P@top5 | `mirror@1.00` | -$5 | 22.1% | 9.7% | 0.80 | $382 |
| shuffle2 | P@top5 | `overlay` | $15 | 22.1% | 9.7% | 0.80 | $382 |
| shuffle2 | P@top10 | `close` | -$10 | 29.2% | 13.6% | 1.30 | $433 |
| shuffle2 | P@top10 | `mirror@1.00` | -$1 | 28.5% | 14.1% | 1.53 | $429 |
| shuffle2 | P@top10 | `overlay` | $22 | 28.5% | 14.1% | 1.53 | $429 |
| shuffle2 | P@top15 | `close` | -$3 | 23.4% | 11.2% | 1.67 | $377 |
| shuffle2 | P@top15 | `mirror@1.00` | $3 | 21.7% | 11.1% | 2.14 | $360 |
| shuffle2 | P@top15 | `overlay` | $34 | 21.7% | 11.1% | 2.14 | $360 |
| shuffle2 | P@top20 | `close` | -$3 | 23.4% | 11.2% | 1.67 | $377 |
| shuffle2 | P@top20 | `mirror@1.00` | $3 | 21.7% | 11.1% | 2.14 | $360 |
| shuffle2 | P@top20 | `overlay` | $34 | 21.7% | 11.1% | 2.14 | $360 |
| REAL | P@top5 | `close` | $5 | 45.6% | 25.2% | 0.57 | $753 |
| REAL | P@top5 | `mirror@1.00` | $28 | 42.4% | 26.6% | 0.87 | $773 |
| REAL | P@top5 | `overlay` | $30 | 42.4% | 26.6% | 0.87 | $773 |
| REAL | P@top10 | `close` | -$13 | 41.3% | 23.3% | 0.95 | $695 |
| REAL | P@top10 | `mirror@1.00` | $3 | 37.8% | 23.0% | 1.87 | $668 |
| REAL | P@top10 | `overlay` | $1 | 37.8% | 23.0% | 1.87 | $667 |
| REAL | P@top15 | `close` | -$32 | 42.6% | 22.6% | 1.27 | $692 |
| REAL | P@top15 | `mirror@1.00` | -$14 | 37.5% | 21.6% | 2.99 | $642 |
| REAL | P@top15 | `overlay` | $14 | 37.5% | 21.7% | 3.01 | $641 |
| REAL | P@top20 | `close` | $5 | 39.0% | 22.4% | 1.53 | $664 |
| REAL | P@top20 | `mirror@1.00` | -$30 | 36.5% | 21.1% | 4.13 | $630 |
| REAL | P@top20 | `overlay` | $3 | 36.6% | 21.2% | 4.18 | $634 |

## The panel do-not-build purge, column by column

`PANEL_SYNTHESIS.md` §2, negative convergence, mapped onto the columns this matrix carries.  Three items name channels that were never built here and therefore purge nothing; they are listed so the mapping can be audited.

| panel item | columns dropped |
|---|---|
| traded-IV call-put skew alone | `V_skew_traded`, `V_skew_traded_o`, `V_skew_slope`, `V_skew_slope_o`, `X_V_skew_traded_o__R_trend_day`, `X_V_skew_traded_o__R_compress`, `X_V_skew_traded_o__R_atr_high`, `X_V_skew_traded_o__R_late` |
| urgency / at-touch fraction alone | `U_urg120`, `U_urg120_z`, `U_urg_clock_z`, `E_urg120`, `X_U_urg120_z__R_trend_day`, `X_U_urg120_z__R_compress`, `X_U_urg120_z__R_atr_high`, `X_U_urg120_z__R_late` |
| depth_at_touch alone | `D_depth60`, `D_depth60_z`, `X_D_depth60_z__R_trend_day`, `X_D_depth60_z__R_compress`, `X_D_depth60_z__R_atr_high`, `X_D_depth60_z__R_late` |
| prints/min alone | `U_printrate_z` |
| T-15m/T-30m flow bins alone | _(no such column in this matrix)_ |
| requote latency | _(no such column in this matrix)_ |
| valid_bucket_fraction | _(no such column in this matrix)_ |
| standalone charm / vanna / gamma \|z\| | `Z_gamma120_z`, `Z_vanna120_z`, `Z_charm120_z`, `T_gamma1_z`, `T_vanna1_z` |
| block size after reclaim | `K_blk_frac600`, `K_contam_n600`, `K_contam_n120`, `K_optcontam_n600` |
| PROXY_VOL direction | `Y_pv_slope10`, `Y_pv_slope30`, `Y_expanding`, `Y_slope_x_agree` |

## Laws and controls

- REPRODUCTION: this file's trade table reproduces `exit_segments/stop_replay.tsv` to the dollar on all five segments for `close`, `mirror@1.00` and `cont[lasso,B]@c25` (arm `v3 full`, top-5, two positions), so the exit side is rung 1/3's machinery unchanged and only the entry side moves.
- WALK-FORWARD PURITY: every segment trains only on sessions strictly earlier than its test block (asserted in code); usable columns come from each segment's own training window.
- THE THRESHOLD IS NEVER READ OFF A TEST BLOCK: the grid is the preregistered study quantiles {5,10,15,20}% of session-grouped 5-fold OUT-OF-FOLD predictions on the training window.
- FROZEN ESTIMATOR: `{'max_depth': 2, 'max_iter': 150, 'learning_rate': 0.05, 'min_samples_leaf': 20, 'l2_regularization': 1.0}`, never re-selected; the class-target refit changes the label and nothing else.
- NO CELL IS SELECTED ON ITS OWN BLOCK: the design centre was named before the numbers and the LOEO reading selects on the other four eras; `best-in-block` is labelled as an upper bound.
- COSTS: 576 net cents once per trade; the $300 wall monitored from entry with gap-through; occupancy 2 concurrent positions (D-030).
- SEALED ZONE: `packlib.SEALED_FROM` = 918; the highest session read here is 917.
- D-022 overlay: era RTY-mini factors 0.879 / 0.895 / 1.004 / 1.099 / 1.073; the RTY column of the verdict table carries them and no share or percentage moves.

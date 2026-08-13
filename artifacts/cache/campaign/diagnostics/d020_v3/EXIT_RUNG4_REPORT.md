# EXIT RUNG 4 — MODEL-MIRROR AND CLASS-CONDITIONAL EXITS

ONE position, ONE mini (D-046).  Exit rules that spend the ENTRY model's own intelligence: **A** exits when the model fires the OPPOSITE side above its study bar; **B** lets the entry-time P pick the exit style (top-decile holds to close, the rest gets a time stop); **A+B** gives the hold-class A.  Carried baselines: hold-to-close, `mirror@1.00` (rung 1), `oracle` (ceiling).  Every number is a REALISED dollar on the $100,000 object with the 576c round trip charged once and the $300 wall live.


## VERDICT

**1. Headline: both charter formulations are NULL, and the honest best exit in this rung is still hold-to-close.**  Selecting each cell on the OTHER four eras only (leave-one-era-out — no era picks its own rule), the deployment-era mean realised P&L is **hold-to-close $63/day**, **A (model-mirror) $50/day**, **B (class-conditional) -$4/day**, **A+B -$20/day**, one position, one mini, costs charged, $300 wall live.  Taken instead as an in-block MAXIMUM over the ~184 cells offered per era — an upper bound, not a deployable number — A beats the best prior implementable in 3 of 5 eras, B in 2 of 5 and A+B in 3 of 5, and no formulation wins in all five, with the winning cell changing arm, stream and variant every era.  That is the fourth rung running on which the ranking of exit rules does not transfer.

| era | best prior implementable | best A | best B | best A+B | LOEO best of A/B/A+B | LOEO hold-to-close | one-position oracle ceiling |
|---|---|---|---|---|---|---|---|
| `blind_e3` (control) | $139 | **$223** | $148 | $146 | $9 | $9 | $987 |
| `e4` | **$113** | $82 | $99 | $99 | -$27 | $82 | $1,242 |
| `e5` | $67 | **$107** | $31 | $9 | -$51 | $61 | $1,029 |
| `e6` | $59 | $48 | **$69** | $66 | $24 | $1 | $1,048 |
| `e7` | $107 | $122 | $119 | **$158** | $4 | $107 | $1,201 |
| **deployment mean (e4..e7)** | — | — | — | — | **-$12** | **$63** | **$1,130** |

**2. Verdict (i) — does A and/or B beat all prior implementables per era?  NO.**  Neither does it in every era, and neither survives honest selection in any era.  The single best cell in the whole rung by deployment-era mean is `mmirror@10+prof` on `E/T/I only` at the `P@top20` entry stream, **$66/day** — against plain hold-to-close on the identical arm and identical entry stream at **$63/day**.  The entire measured value of formulation A, on its own best cell, is **$3/day**.  B's best cell (`class[30]`, same arm and stream) is **$50/day**, i.e. it *costs* $13/day against doing nothing.  A+B is worse than either.

**3. WHY A fails, exactly: the opposite-side model fire is a TREND detector, not a reversal detector — it fires on winners more than on duds.**  Pooled over the four deployment eras, occupancy-free, on all 9,096 candidates: `mmirror@25` fires before the close on **34% of winners but only 16% of duds** (`E/T/I only`; 28% vs 15% for `v3 no-M`).  It is more than twice as likely to close a good trade as a bad one, because a big leg is exactly what manufactures a big, high-scoring opposite pivot behind it.  The dollars follow: **-$85 per winner, +$32 per dud**.  At the roster's 27% winner share those cancel to **+$0.4 per trade**.  This is rung 1's symmetric-compression pathology reproduced by our highest-precision detector: swapping the raw ZigZag for the model changed which trades get cut, not the fact that winners and duds get cut at the same net rate.

**4. WHY B fails, exactly: the $300 wall already IS the dud-cutter, and the top-decile bar admits almost nobody out of era.**  Two independent kills.  (a) On the low-P class — the class B is supposed to time-stop — holding to the close beats the 30-minute stop by **+$12 / +$7 / +$12 / +$17 / -$2 / +$4 / -$4 / -$7 / -$4 / -$2** per candidate across all ten (era x arm) cells: a wash, and if anything the wrong sign.  There is no bleed left to stop, because the hard wall fires from entry and caps every dud at about -$300 already; a time stop on top of a hard stop has nothing to cut.  (b) The `P@top10` bar admits **0% to 10%** of the out-of-era roster (0 of 466 candidates in `blind_e3` and 2 of 759 in `e4` for `E/T/I only`; 15 of 466 in `blind_e3` for `v3 no-M`), so B is in practice "time-stop everything", and the hold-class it is built around barely exists.  The one thing the split does show is an ENTRY fact, not an exit fact: where the bar admits a real group, the `E/T/I only` top decile pays **$65 / $110 per candidate held to close against -$12 / -$6 for the rest** (`e5`, `e7`) — the precision lane's finding again, arriving from the exit side.

**5. Verdict (ii) — best one-position realised $/day per era against $2,000 / $1,500: missed by 10-30x, and the ceiling proves the target is not an exit problem.**  In-block maxima: **$223** (`blind_e3`), **$113** (`e4`), **$107** (`e5`), **$69** (`e6`), **$158** (`e7`) — **3-11% of $2,000**, 5-15% of $1,500.  The honest LOEO reading is $9 / $82 / $61 / $1 / $107.  The decisive number is the ceiling beside them: a PERFECT exit on the same one-position book earns **$987 / $1,242 / $1,029 / $1,048 / $1,201 per day**.  With one position at a time, $2,000/session is **unreachable by any exit rule that could ever exist** on this roster — the entered certificate is only $797-$1,027/day because occupancy admits only 1.2-2.5 of the day's picks.  The target has to come from bigger per-trade certificates or more concurrent exposure; the exit lane cannot deliver it, and this rung closes that question rather than leaving it open.

**6. Verdict (iii) — the per-trade distribution: the $900 trade EXISTS, it is just outnumbered 5-to-1.**  At the honest LOEO cell (hold-to-close, `E/T/I only`, `P@top20`, 390 trades over the four deployment eras): mean **$81**, median **-$300**, p90 **+$1,064**, worst -$416; **13% of trades pay $900 or more**, 18% pay $600 or more, and **72% lose**, nearly all of them parked at the wall.  Per era, at each era's own best cell, the mean per trade is $28-$132 and the MEDIAN is negative in every single era (-$27 to -$273).  So D-046's arithmetic resolves cleanly: at ~1-2 trades/day the book needs ~$900-$1,000 per trade, the top decile of the book already delivers that, and the whole shortfall is that the other 87% is a coin-flip against the wall.  Winner SIZE is solved; winner SHARE is not.

**7. Verdict (iv) — the shuffle controls are clean, and they confirm the null.**  Permuting the opposite-fire TIMES within (session, arm, side), preserving the fire count exactly and leaving the entry stream untouched, moves the deployment-era mean by **+$24 / +$17 / -$9 / -$25** per day across the four (arm x stream) design cells — sign-flipping, mean **+$2/day**, i.e. `mmirror@25` is statistically indistinguishable from a random exit clock at the same rate, which is precisely what the +$0.4/trade expectation in §3 predicts.  Permuting entry-P within the session moves B by **-$1 / +$9 / +$2 / -$12** per day; in the cells where the top-decile bar admits nobody the permutation is the identity and the two columns match to the cent, which is itself the §4(b) finding made visible.

**8. The overlay, as instructed, and what it does.**  `cont[lasso,B]@c25` was run ON for every rule of every cell.  It remains what rung 3 and the precision lane measured: it fires at minute one on essentially every state, so every rule's mean hold collapses to **1.0-1.1 minutes** and at the `P@top20` entry stream `close`, `mmirror@25` and `class[30]` all land on the same **$6.6/day, to the cent** — the overlay does not modify the rule, it replaces it.  It buys real drawdown control (worst day -$1,815 to -$1,065 at the best cell) at the cost of essentially all the money, and it violates D-019's long-hold shape on sight.  Every overlay-OFF number above is therefore the like-for-like comparison against rungs 1-3, and both panels are reported in full.

**9. What this hands forward.**  (a) The exit program is now falsified in five distinct ways on the same corpus: a price-symmetric mirror (rung 1), a barrier probability (rung 2), a grid-maximum valuation and an attainable continuation (rung 3), and now the entry model's own opposite-side fire and its entry-time class (rung 4).  The last two mattered because they were the only untried formulations D-046 named; they are now tried.  (b) The binding constraint is arithmetic and pre-entry: one position caps a perfect exit at **~$1,130/day**, so $2,000/session on ONE mini requires a roster whose individual certificates are roughly twice today's, not a better exit.  (c) The one live lever measured anywhere in the program remains rung 1's entry-side giveback of **$156-$228 per trade** — half the leg, spent before the position exists — and the precision lane's winner-share instrument.  Both are pre-entry.  (d) D-019 shape check: the family carrying the dollars here is again hold-to-close at 100-150 minutes and 0.5-0.9 trades/day, which is the compliant shape; A at 47-102 minutes is also compliant; the overlay at 1 minute is not.

**Controls.**  Four reproduction controls, all exact: the replay reproduces `precision_segments/precision_trades.tsv` to **$0.0000 over all 47,810 (candidate, rule) realised P&Ls** for `close`, `mirror@1.00`, `oracle`, `overlay` and `mirror+overlay`, so this rung's arithmetic is rungs 1/3's machinery unchanged; the top-k pick streams reproduce `exit_segments/picks.tsv` on **1,956 of 1,956** (session, arm, k) baskets; the study bars reproduce the published `precision_thresholds.tsv` at **max |delta| 0.00e+00 over 40** (segment, arm, quantile) bars; the overlay predictions cover 9,422 of 9,562 candidates and abstain on the rest.  Strictly prior: an opposite-side candidate's score is a function of features stamped at its OWN decision second under a model fit only on earlier sessions, and the bars are quantiles of session-grouped out-of-fold predictions on each segment's training window, never of a test block.  No test tuning: the bar ladder {10,20,25}%, the class decile, the stops {30,60}, the three A variants, the four entry streams and the two arms were all fixed before any number was computed, all 1,600 cells are written to `rung4_segments/rung4_cells.tsv`, and every headline carries a leave-one-era-out reading beside its in-block maximum.  576c charged once per trade on every rule including the oracle; $300 wall monitored from entry with gap-through; ONE position at a time (D-046).  Sealed zone untouched (highest session replayed 917; `packlib.SEALED_FROM` 918).  D-022 overlay: era RTY-mini factors 0.879-1.073, so every dollar figure is within 12% of its one-mini equivalent and no percentage moves.


## VERDICT TABLE — best implementable cell per era, one position, overlay OFF

`prior` = the best of the rules carried from rungs 1-3 (`close`, `mirror@1.00`, `+patience15`, the `cont[lasso,B]@c25` overlay on hold-to-close) over the SAME streams and arms.  `new` = the best of formulations A / B / A+B.  Both columns are in-block maxima (upper bounds); the LOEO column selects the cell on the OTHER four eras only and reads it out here.

| era | prior best $/day | A/B best $/day | A/B best cell | LOEO A/B $/day | LOEO cell | oracle ceiling $/day | vs $2,000 |
|---|---|---|---|---|---|---|---|
| `blind_e3` | $139 (close, v3 no-M, top3) | **$223** | mmirror@25 / v3 no-M / top5 | $9 | mmirror@10+prof / E/T/I only / thr20 | $987 | 11% |
| `e4` | $113 (mirror@1.00+patience15, E/T/I only, top3) | **$99** | class[60] / E/T/I only / thr20 | -$27 | class[60] / v3 no-M / thr20 | $1,242 | 5% |
| `e5` | $67 (close, E/T/I only, top3) | **$107** | mmirror@25+prof / E/T/I only / top5 | -$51 | class[60]+mmirror@25 / v3 no-M / thr20 | $1,029 | 5% |
| `e6` | $59 (mirror@1.00, v3 no-M, top3) | **$69** | class[30] / v3 no-M / top5 | $24 | mmirror@10+prof / E/T/I only / thr20 | $1,048 | 3% |
| `e7` | $107 (close, E/T/I only, thr20) | **$158** | class[60]+mmirror@25 / v3 no-M / thr20 | $4 | class[30] / E/T/I only / top3 | $1,201 | 8% |

## (i) Does A and/or B beat ALL prior implementables, per era?

| era | best prior | best A | best B | best A+B | A beats prior | B beats prior | A+B beats prior |
|---|---|---|---|---|---|---|---|
| `blind_e3` | $139 | $223 | $148 | $146 | YES | YES | YES |
| `e4` | $113 | $82 | $99 | $99 | no | no | no |
| `e5` | $67 | $107 | $31 | $9 | YES | no | no |
| `e6` | $59 | $48 | $69 | $66 | no | YES | YES |
| `e7` | $107 | $122 | $119 | $158 | YES | YES | YES |

## (ii) Best ONE-POSITION realised $/day per era vs $2,000 / $1,500

| era | best cell $/day | RTY-mini | % of $2,000 | % of $1,500 | picked $/day | entered cert $/day | capture of entered | trades/day | $/trade | mean hold |
|---|---|---|---|---|---|---|---|---|---|---|
| `blind_e3` | **$223** (mmirror@25, v3 no-M, top5) | $196 | 11% | 15% | $2,201 | $914 | 24% | 1.95 | $114 | 144min |
| `e4` | **$113** (mirror@1.00+patience15, E/T/I only, top3) | $101 | 6% | 8% | $1,391 | $983 | 11% | 2.28 | $49 | 27min |
| `e5` | **$107** (mmirror@25+prof, E/T/I only, top5) | $107 | 5% | 7% | $2,015 | $956 | 11% | 2.05 | $52 | 127min |
| `e6` | **$69** (class[30], v3 no-M, top5) | $76 | 3% | 5% | $2,048 | $1,027 | 7% | 2.48 | $28 | 48min |
| `e7` | **$158** (class[60]+mmirror@25, v3 no-M, thr20) | $170 | 8% | 11% | $1,826 | $797 | 20% | 1.20 | $132 | 42min |

## (iii) The per-trade realised distribution at the best cell (the $900+/trade need)

| era | cell | trades | mean | median | p10 | p25 | p75 | p90 | share > $0 | share >= $600 | share >= $900 | worst |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `blind_e3` | mmirror@25 / v3 no-M / top5 | 39 | $114 | -$106 | -$308 | -$302 | $497 | $967 | 46% | 23% | 13% | -$321 |
| `e4` | mirror@1.00+patience15 / E/T/I only / top3 | 114 | $49 | -$27 | -$299 | -$156 | $185 | $545 | 45% | 7% | 4% | -$330 |
| `e5` | mmirror@25+prof / E/T/I only / top5 | 258 | $52 | -$206 | -$310 | -$303 | $249 | $767 | 47% | 15% | 7% | -$334 |
| `e6` | class[30] / v3 no-M / top5 | 278 | $28 | -$86 | -$312 | -$302 | $226 | $507 | 41% | 7% | 4% | -$379 |
| `e7` | class[60]+mmirror@25 / v3 no-M / thr20 | 218 | $132 | -$273 | -$327 | -$307 | $354 | $870 | 41% | 16% | 10% | -$392 |

## (iv) Shuffle controls

A's control permutes the opposite-fire TIMES within (session, arm, side) — the same number of fires per side, random clocks.  B's control permutes the entry-P within (session, arm) — the same class sizes, random membership.  Three draws each; the ENTRY stream is untouched in both, so only the exit-side use of the score is randomised.

| era | arm | stream | real A (`mmirror@25`) | shuffled A (3 draws) | real B (`class[30]`) | shuffled B (3 draws) |
|---|---|---|---|---|---|---|
| `blind_e3` | E/T/I only | top5 | -$4 | -$64 [-$147, -$77, $32] | $9 | $9 [$9, $9, $9] |
| `blind_e3` | E/T/I only | thr20 | $24 | $9 [$9, $9, $9] | -$38 | -$38 [-$38, -$38, -$38] |
| `blind_e3` | v3 no-M | top5 | $223 | $50 [$15, $87, $49] | $44 | $46 [$12, $63, $63] |
| `blind_e3` | v3 no-M | thr20 | $162 | $139 [$153, $133, $129] | $92 | $38 [$1, $44, $69] |
| `e4` | E/T/I only | top5 | $15 | $11 [-$3, $5, $32] | $13 | $5 [$5, $5, $5] |
| `e4` | E/T/I only | thr20 | $55 | $48 [$53, $53, $39] | $84 | $77 [$77, $77, $77] |
| `e4` | v3 no-M | top5 | -$69 | -$94 [-$129, -$75, -$79] | -$77 | -$43 [-$39, -$51, -$39] |
| `e4` | v3 no-M | thr20 | -$68 | -$47 [-$64, -$48, -$30] | -$28 | -$0 [$2, -$4, $2] |
| `e5` | E/T/I only | top5 | $11 | $14 [$21, -$4, $26] | -$12 | $3 [$16, -$18, $12] |
| `e5` | E/T/I only | thr20 | $23 | $6 [$36, -$19, $2] | $7 | $17 [$30, $13, $7] |
| `e5` | v3 no-M | top5 | -$62 | -$54 [-$73, -$29, -$58] | -$64 | -$45 [-$45, -$48, -$42] |
| `e5` | v3 no-M | thr20 | -$77 | -$41 [-$41, -$32, -$49] | -$35 | -$16 [-$18, -$14, -$17] |
| `e6` | E/T/I only | top5 | $6 | -$84 [-$104, -$81, -$68] | -$45 | -$41 [-$46, -$38, -$40] |
| `e6` | E/T/I only | thr20 | $28 | -$9 [$6, -$12, -$21] | -$11 | -$25 [-$32, -$20, -$22] |
| `e6` | v3 no-M | top5 | -$48 | $5 [$8, $3, $2] | $69 | $23 [$1, $13, $56] |
| `e6` | v3 no-M | thr20 | -$61 | -$11 [-$26, $7, -$12] | $18 | -$14 [-$16, -$37, $12] |
| `e7` | E/T/I only | top5 | $32 | $25 [$7, $35, $34] | -$0 | -$6 [-$10, -$8, -$1] |
| `e7` | E/T/I only | thr20 | $50 | $44 [$51, $53, $29] | $119 | $96 [$111, $94, $83] |
| `e7` | v3 no-M | top5 | $19 | $19 [$29, $22, $7] | $0 | -$14 [-$13, -$18, -$12] |
| `e7` | v3 no-M | thr20 | $66 | $58 [$59, $45, $70] | $38 | $72 [$81, $34, $100] |

## WHY — the anatomy, on EVERY candidate (occupancy-free)

These tables do not pass through the one-position filter, so they measure the formulations themselves rather than the book they happen to produce.


**B — does the entry-time P know which trades benefit from being held?**  If it does, the top-decile class must gain from holding and the rest must lose from it.

| era | arm | class | candidates | winner share | hold-to-close $ | 30-min stop $ | 60-min stop $ | close - stop30 | oracle $ |
|---|---|---|---|---|---|---|---|---|---|
| `blind_e3` | E/T/I only | P in top decile | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| `blind_e3` | E/T/I only | the rest | 466 | 25% | $8 | -$4 | $4 | $12 | $361 |
| `blind_e3` | v3 no-M | P in top decile | 15 | 33% | $188 | $14 | $108 | $174 | $597 |
| `blind_e3` | v3 no-M | the rest | 451 | 24% | $2 | -$5 | $1 | $7 | $353 |
| `e4` | E/T/I only | P in top decile | 2 | 100% | $668 | $416 | $431 | $253 | $893 |
| `e4` | E/T/I only | the rest | 757 | 28% | $19 | $7 | $20 | $12 | $401 |
| `e4` | v3 no-M | P in top decile | 9 | 33% | -$279 | $82 | -$11 | -$361 | $425 |
| `e4` | v3 no-M | the rest | 750 | 29% | $25 | $8 | $22 | $17 | $402 |
| `e5` | E/T/I only | P in top decile | 146 | 34% | $65 | $31 | $59 | $35 | $520 |
| `e5` | E/T/I only | the rest | 2102 | 24% | -$12 | -$11 | -$11 | -$2 | $354 |
| `e5` | v3 no-M | P in top decile | 120 | 28% | -$93 | -$37 | -$38 | -$56 | $395 |
| `e5` | v3 no-M | the rest | 2128 | 24% | -$3 | -$6 | -$5 | $4 | $364 |
| `e6` | E/T/I only | P in top decile | 66 | 38% | -$47 | -$21 | $34 | -$26 | $561 |
| `e6` | E/T/I only | the rest | 2051 | 27% | -$9 | -$6 | -$10 | -$4 | $379 |
| `e6` | v3 no-M | P in top decile | 218 | 30% | -$18 | -$34 | -$28 | $16 | $466 |
| `e6` | v3 no-M | the rest | 1899 | 27% | -$10 | -$3 | -$6 | -$7 | $375 |
| `e7` | E/T/I only | P in top decile | 202 | 44% | $110 | $58 | $94 | $52 | $901 |
| `e7` | E/T/I only | the rest | 3770 | 27% | -$6 | -$2 | $5 | -$4 | $430 |
| `e7` | v3 no-M | P in top decile | 201 | 37% | -$8 | -$11 | -$17 | $3 | $724 |
| `e7` | v3 no-M | the rest | 3771 | 28% | $0 | $2 | $11 | -$2 | $440 |

**A — what the opposite-side model fire does when it fires**, split by the TRUTH class of the trade it is closing (read-only; no rule reads it).  A working exit cuts duds harder than winners.

| era | arm | class | candidates | fires before close | mean hold under A | hold-to-close $ | `mmirror@25` $ | A - close |
|---|---|---|---|---|---|---|---|---|
| `blind_e3` | E/T/I only | winners (cert >= $500) | 115 | 15% | 223min | $582 | $516 | -$66 |
| `blind_e3` | E/T/I only | duds | 351 | 5% | 73min | -$180 | -$168 | $13 |
| `blind_e3` | v3 no-M | winners (cert >= $500) | 115 | 22% | 198min | $582 | $526 | -$56 |
| `blind_e3` | v3 no-M | duds | 351 | 13% | 66min | -$180 | -$154 | $26 |
| `e4` | E/T/I only | winners (cert >= $500) | 217 | 18% | 179min | $587 | $523 | -$64 |
| `e4` | E/T/I only | duds | 542 | 11% | 63min | -$206 | -$180 | $25 |
| `e4` | v3 no-M | winners (cert >= $500) | 217 | 17% | 186min | $587 | $522 | -$66 |
| `e4` | v3 no-M | duds | 542 | 13% | 62min | -$206 | -$180 | $26 |
| `e5` | E/T/I only | winners (cert >= $500) | 550 | 37% | 155min | $527 | $405 | -$121 |
| `e5` | E/T/I only | duds | 1698 | 18% | 70min | -$180 | -$145 | $35 |
| `e5` | v3 no-M | winners (cert >= $500) | 550 | 25% | 178min | $527 | $405 | -$122 |
| `e5` | v3 no-M | duds | 1698 | 15% | 73min | -$180 | -$152 | $28 |
| `e6` | E/T/I only | winners (cert >= $500) | 569 | 27% | 178min | $481 | $440 | -$41 |
| `e6` | E/T/I only | duds | 1548 | 11% | 63min | -$191 | -$165 | $26 |
| `e6` | v3 no-M | winners (cert >= $500) | 569 | 37% | 153min | $481 | $338 | -$143 |
| `e6` | v3 no-M | duds | 1548 | 19% | 59min | -$191 | -$155 | $36 |
| `e7` | E/T/I only | winners (cert >= $500) | 1123 | 40% | 129min | $517 | $424 | -$93 |
| `e7` | E/T/I only | duds | 2849 | 17% | 54min | -$204 | -$169 | $35 |
| `e7` | v3 no-M | winners (cert >= $500) | 1123 | 27% | 147min | $517 | $450 | -$67 |
| `e7` | v3 no-M | duds | 2849 | 15% | 55min | -$204 | -$174 | $30 |

## Deployment-era mean (e4..e7), every rule x arm x stream, overlay OFF

| rule | arm | stream | mean $/day | mean $/trade | winner share | capture of entered | trades/day | mean hold | worst day | worst trade |
|---|---|---|---|---|---|---|---|---|---|---|
| oracle | E/T/I only | top5 | **$1,125** | $504 | 39% | 103% | 2.24 | 89min | -$400 | -$379 |
| oracle | v3 no-M | top5 | **$1,069** | $466 | 35% | 104% | 2.29 | 83min | -$309 | -$586 |
| oracle | E/T/I only | top3 | **$900** | $493 | 40% | 103% | 1.83 | 90min | -$310 | -$379 |
| oracle | v3 no-M | top3 | **$841** | $458 | 34% | 103% | 1.84 | 79min | -$291 | -$379 |
| oracle | E/T/I only | thr20 | **$559** | $570 | 39% | 104% | 0.99 | 72min | -$313 | -$571 |
| oracle | v3 no-M | thr20 | **$557** | $447 | 26% | 106% | 1.23 | 54min | -$313 | -$571 |
| oracle | v3 no-M | thr10 | **$269** | $445 | 26% | 104% | 0.60 | 43min | -$313 | -$571 |
| oracle | E/T/I only | thr10 | **$266** | $665 | 51% | 106% | 0.43 | 87min | -$316 | -$571 |
| mmirror@10+prof | E/T/I only | thr20 | **$66** | $89 | 40% | 15% | 0.86 | 114min | -$2,142 | -$416 |
| close | E/T/I only | thr20 | **$63** | $90 | 39% | 15% | 0.76 | 128min | -$1,815 | -$416 |
| mmirror@25+prof | E/T/I only | thr20 | **$56** | $55 | 40% | 10% | 1.17 | 77min | -$2,142 | -$548 |
| mmirror@20+prof | E/T/I only | thr20 | **$53** | $51 | 39% | 9% | 1.09 | 91min | -$2,142 | -$416 |
| mmirror@10 | E/T/I only | thr20 | **$52** | $73 | 39% | 12% | 0.96 | 105min | -$2,142 | -$416 |
| mmirror@10+patience15 | E/T/I only | thr20 | **$51** | $77 | 39% | 13% | 0.89 | 109min | -$2,142 | -$416 |
| class[30] | E/T/I only | thr20 | **$50** | $59 | 39% | 10% | 0.92 | 50min | -$1,821 | -$416 |
| mmirror@10+prof | E/T/I only | thr10 | **$49** | $246 | 55% | 30% | 0.40 | 158min | -$3,086 | -$351 |
| shufB1[30] | E/T/I only | thr20 | **$47** | $50 | 39% | 8% | 1.02 | 29min | -$1,503 | -$416 |
| class[30] | E/T/I only | top3 | **$43** | $23 | 34% | 5% | 1.87 | 40min | -$985 | -$379 |
| mmirror@25+prof | E/T/I only | top5 | **$41** | $20 | 35% | 4% | 2.05 | 120min | -$1,567 | -$548 |
| shufB2[30] | E/T/I only | thr20 | **$41** | $46 | 39% | 8% | 1.02 | 27min | -$1,477 | -$571 |
| mmirror@20+prof | E/T/I only | thr10 | **$40** | $218 | 56% | 26% | 0.45 | 140min | -$3,086 | -$351 |
| shufB1[30] | E/T/I only | top3 | **$40** | $21 | 34% | 5% | 1.92 | 29min | -$985 | -$379 |
| mmirror@25+prof | E/T/I only | thr10 | **$39** | $210 | 56% | 25% | 0.49 | 133min | -$3,086 | -$548 |
| mmirror@25 | E/T/I only | thr20 | **$39** | $37 | 39% | 7% | 1.55 | 61min | -$2,622 | -$548 |
| mmirror@25+patience15 | E/T/I only | thr20 | **$39** | $44 | 38% | 8% | 1.11 | 73min | -$2,622 | -$548 |
| class[30]+mmirror@25 | E/T/I only | thr20 | **$38** | $44 | 39% | 7% | 1.19 | 33min | -$2,020 | -$548 |
| mmirror@20 | E/T/I only | thr20 | **$37** | $33 | 38% | 6% | 1.42 | 76min | -$2,622 | -$416 |
| shufB2[30] | E/T/I only | top3 | **$37** | $19 | 34% | 4% | 1.93 | 27min | -$985 | -$379 |
| shufA1@25 | E/T/I only | thr20 | **$36** | $39 | 40% | 7% | 1.15 | 65min | -$2,238 | -$571 |
| mmirror@20+patience15 | E/T/I only | thr20 | **$36** | $43 | 39% | 7% | 1.07 | 87min | -$2,622 | -$416 |
| shufB3[30] | E/T/I only | thr20 | **$36** | $42 | 38% | 7% | 1.04 | 28min | -$2,309 | -$416 |
| shufB3[30] | E/T/I only | top3 | **$36** | $19 | 34% | 4% | 1.91 | 29min | -$985 | -$379 |
| class[60] | E/T/I only | thr10 | **$34** | $227 | 54% | 27% | 0.34 | 178min | -$3,086 | -$351 |
| class[30] | E/T/I only | thr10 | **$34** | $227 | 54% | 27% | 0.34 | 178min | -$3,086 | -$351 |
| close | E/T/I only | thr10 | **$34** | $227 | 54% | 27% | 0.34 | 178min | -$3,086 | -$351 |
| mirror@1.00 | E/T/I only | top3 | **$33** | $11 | 34% | 3% | 2.94 | 19min | -$856 | -$416 |
| mirror@1.00 | v3 no-M | top3 | **$33** | $11 | 33% | 2% | 2.95 | 19min | -$854 | -$416 |
| mmirror@25+prof | E/T/I only | top3 | **$32** | $20 | 37% | 4% | 1.63 | 129min | -$985 | -$416 |
| mirror@1.00+patience15 | E/T/I only | top3 | **$32** | $14 | 33% | 3% | 2.24 | 24min | -$985 | -$416 |
| class[60] | E/T/I only | thr20 | **$32** | $55 | 39% | 8% | 0.83 | 61min | -$2,251 | -$416 |
| mmirror@10 | E/T/I only | thr10 | **$31** | $216 | 53% | 25% | 0.46 | 149min | -$3,086 | -$351 |
| mmirror@20+prof | E/T/I only | top5 | **$31** | $16 | 34% | 3% | 1.97 | 127min | -$1,567 | -$548 |
| mmirror@10+patience15 | E/T/I only | thr10 | **$29** | $219 | 53% | 25% | 0.40 | 155min | -$3,086 | -$351 |
| class[30]+mmirror@25 | E/T/I only | top3 | **$28** | $14 | 34% | 3% | 1.99 | 31min | -$985 | -$379 |
| shufB3[30] | v3 no-M | thr20 | **$24** | $19 | 31% | 3% | 1.22 | 33min | -$2,830 | -$571 |
| shufA2@25 | E/T/I only | thr10 | **$24** | $195 | 55% | 23% | 0.48 | 128min | -$2,348 | -$548 |
| shufB1[30] | E/T/I only | thr10 | **$24** | $127 | 53% | 15% | 0.42 | 37min | -$1,693 | -$420 |
| shufB3[30] | E/T/I only | thr10 | **$24** | $135 | 53% | 16% | 0.41 | 35min | -$2,204 | -$420 |
| class[60] | v3 no-M | thr20 | **$23** | $13 | 32% | 1% | 1.01 | 63min | -$2,830 | -$435 |
| shufB2[30] | E/T/I only | thr10 | **$23** | $131 | 53% | 15% | 0.41 | 28min | -$1,693 | -$571 |
| shufA3@25 | E/T/I only | thr10 | **$23** | $188 | 55% | 21% | 0.47 | 128min | -$2,416 | -$420 |
| mmirror@20+prof | E/T/I only | top3 | **$22** | $14 | 37% | 3% | 1.58 | 136min | -$985 | -$416 |
| class[60] | E/T/I only | top3 | **$22** | $13 | 35% | 3% | 1.64 | 56min | -$985 | -$379 |
| class[60]+mmirror@25 | E/T/I only | thr20 | **$22** | $45 | 39% | 6% | 1.04 | 45min | -$2,466 | -$548 |
| mmirror@20+patience15 | E/T/I only | thr10 | **$22** | $195 | 53% | 21% | 0.44 | 135min | -$3,086 | -$351 |
| class[60]+mmirror@25 | v3 no-M | thr20 | **$22** | $10 | 31% | -0% | 1.17 | 55min | -$2,830 | -$435 |
| mmirror@20 | E/T/I only | thr10 | **$22** | $190 | 54% | 21% | 0.53 | 129min | -$3,086 | -$351 |
| mirror@1.00 | E/T/I only | thr10 | **$20** | $107 | 54% | 12% | 0.69 | 14min | -$1,160 | -$342 |
| mmirror@25+patience15 | E/T/I only | thr10 | **$20** | $185 | 53% | 20% | 0.47 | 129min | -$3,086 | -$548 |
| shufA2@25 | E/T/I only | thr20 | **$18** | $24 | 39% | 4% | 1.16 | 66min | -$1,404 | -$548 |
| mmirror@25 | E/T/I only | top3 | **$18** | $11 | 36% | 2% | 1.81 | 115min | -$985 | -$416 |
| mmirror@25 | E/T/I only | thr10 | **$18** | $178 | 54% | 19% | 0.58 | 122min | -$3,086 | -$548 |
| class[30]+mmirror@25 | E/T/I only | thr10 | **$18** | $178 | 54% | 19% | 0.58 | 122min | -$3,086 | -$548 |
| class[60]+mmirror@25 | E/T/I only | thr10 | **$18** | $178 | 54% | 19% | 0.58 | 122min | -$3,086 | -$548 |
| close | E/T/I only | top3 | **$18** | $12 | 36% | 3% | 1.47 | 151min | -$985 | -$379 |
| mirror@1.00+patience15 | E/T/I only | thr10 | **$18** | $109 | 53% | 12% | 0.51 | 19min | -$2,360 | -$548 |
| mmirror@10+prof | E/T/I only | top3 | **$18** | $11 | 36% | 2% | 1.51 | 144min | -$985 | -$379 |
| mirror@1.00+patience15 | E/T/I only | thr20 | **$17** | $19 | 38% | 3% | 1.30 | 18min | -$2,904 | -$548 |
| mmirror@25 | E/T/I only | top5 | **$16** | $7 | 34% | 1% | 2.37 | 102min | -$1,567 | -$548 |
| mmirror@25+patience15 | E/T/I only | top5 | **$16** | $7 | 34% | 2% | 2.09 | 112min | -$1,567 | -$548 |
| shufA1@25 | E/T/I only | thr10 | **$16** | $176 | 53% | 19% | 0.50 | 126min | -$3,181 | -$571 |
| shufA3@25 | E/T/I only | top3 | **$14** | $9 | 36% | 2% | 1.60 | 122min | -$985 | -$379 |
| mmirror@20 | E/T/I only | top3 | **$13** | $8 | 35% | 2% | 1.73 | 124min | -$985 | -$416 |
| shufA3@25 | E/T/I only | thr20 | **$12** | $17 | 38% | 3% | 1.18 | 64min | -$1,856 | -$507 |
| shufB1[30] | v3 no-M | thr20 | **$12** | $10 | 31% | 1% | 1.24 | 31min | -$2,830 | -$571 |
| mirror@1.00 | v3 no-M | top5 | **$12** | $3 | 31% | 0% | 4.83 | 20min | -$1,309 | -$531 |
| mmirror@25+patience15 | E/T/I only | top3 | **$12** | $7 | 36% | 1% | 1.67 | 120min | -$985 | -$416 |
| mmirror@20+patience15 | E/T/I only | top3 | **$11** | $7 | 36% | 1% | 1.62 | 128min | -$985 | -$416 |
| class[30] | v3 no-M | top3 | **$8** | $4 | 31% | 1% | 1.90 | 42min | -$959 | -$435 |
| mmirror@20+patience15 | E/T/I only | top5 | **$7** | $3 | 34% | 1% | 2.02 | 118min | -$1,567 | -$548 |
| mmirror@20 | E/T/I only | top5 | **$7** | $3 | 33% | 1% | 2.18 | 114min | -$1,567 | -$548 |
| mirror@1.00 | v3 no-M | thr10 | **$6** | $4 | 32% | -0% | 0.97 | 11min | -$1,250 | -$503 |
| shufA3@25 | E/T/I only | top5 | **$6** | $3 | 34% | 0% | 2.05 | 111min | -$1,567 | -$548 |
| shufB3[30] | v3 no-M | top3 | **$6** | $3 | 31% | 1% | 1.96 | 30min | -$959 | -$392 |
| mmirror@10+patience15 | E/T/I only | top3 | **$6** | $3 | 36% | 1% | 1.54 | 141min | -$985 | -$379 |
| class[30]+mmirror@25 | v3 no-M | top3 | **$5** | $2 | 31% | 0% | 1.96 | 39min | -$944 | -$435 |
| mmirror@10+prof | E/T/I only | top5 | **$5** | $3 | 34% | 0% | 1.82 | 136min | -$1,567 | -$548 |
| mmirror@10 | E/T/I only | top3 | **$4** | $2 | 35% | 0% | 1.56 | 139min | -$985 | -$379 |
| class[60]+mmirror@25 | E/T/I only | top3 | **$4** | $3 | 34% | 1% | 1.75 | 46min | -$985 | -$379 |
| mmirror@20+prof | v3 no-M | thr20 | **$3** | -$10 | 32% | -4% | 1.09 | 104min | -$2,830 | -$489 |
| mirror@1.00+patience15 | E/T/I only | top5 | **$2** | $1 | 30% | 0% | 3.33 | 25min | -$1,567 | -$548 |
| close | v3 no-M | thr20 | **$2** | -$4 | 33% | -3% | 0.88 | 127min | -$2,830 | -$435 |
| shufA2@25 | E/T/I only | top3 | **$1** | $1 | 36% | 0% | 1.62 | 120min | -$985 | -$416 |
| mirror@1.00+patience15 | v3 no-M | thr20 | **$1** | -$5 | 30% | -2% | 1.60 | 18min | -$2,267 | -$623 |
| mirror@1.00 | E/T/I only | thr20 | **-$1** | -$5 | 40% | -1% | 1.99 | 10min | -$1,714 | -$430 |
| class[60] | v3 no-M | top3 | **-$1** | -$0 | 31% | -1% | 1.69 | 58min | -$959 | -$435 |
| mmirror@10 | E/T/I only | top5 | **-$1** | $0 | 33% | -0% | 1.89 | 131min | -$1,567 | -$548 |
| shufB1[30] | v3 no-M | top3 | **-$1** | -$1 | 32% | -0% | 1.99 | 27min | -$959 | -$392 |
| class[30] | v3 no-M | thr20 | **-$2** | -$9 | 32% | -3% | 1.11 | 52min | -$2,830 | -$623 |
| class[30]+mmirror@25 | v3 no-M | thr20 | **-$2** | -$9 | 31% | -3% | 1.31 | 44min | -$2,830 | -$623 |
| mirror@1.00 | E/T/I only | top5 | **-$3** | -$1 | 32% | -0% | 4.80 | 19min | -$1,416 | -$416 |
| class[60]+mmirror@25 | v3 no-M | top3 | **-$4** | -$2 | 31% | -1% | 1.75 | 54min | -$944 | -$435 |
| shufB2[30] | v3 no-M | top3 | **-$4** | -$2 | 32% | -1% | 1.97 | 29min | -$959 | -$392 |
| mirror@1.00+patience15 | v3 no-M | thr10 | **-$4** | -$4 | 30% | -1% | 0.72 | 17min | -$2,003 | -$548 |
| mirror@1.00+patience15 | v3 no-M | top3 | **-$5** | -$2 | 31% | -1% | 2.35 | 24min | -$959 | -$416 |
| mmirror@10+patience15 | v3 no-M | thr20 | **-$5** | -$13 | 32% | -4% | 0.97 | 114min | -$2,830 | -$489 |
| shufB2[30] | v3 no-M | thr20 | **-$5** | -$3 | 31% | -1% | 1.25 | 33min | -$2,830 | -$623 |
| shufA3@25 | v3 no-M | thr20 | **-$5** | -$15 | 32% | -4% | 1.22 | 86min | -$2,741 | -$623 |
| shufB3[30] | E/T/I only | top5 | **-$6** | -$2 | 30% | -1% | 2.68 | 28min | -$1,567 | -$548 |
| class[60] | E/T/I only | top5 | **-$6** | -$4 | 31% | -1% | 2.19 | 50min | -$1,567 | -$548 |
| shufA2@25 | v3 no-M | thr20 | **-$7** | -$20 | 31% | -6% | 1.21 | 85min | -$3,986 | -$507 |
| mmirror@10+patience15 | E/T/I only | top5 | **-$7** | -$4 | 34% | -1% | 1.85 | 132min | -$1,567 | -$548 |
| shufA1@25 | E/T/I only | top3 | **-$7** | -$4 | 35% | -1% | 1.62 | 120min | -$985 | -$416 |
| mmirror@25+prof | v3 no-M | thr20 | **-$8** | -$24 | 32% | -7% | 1.13 | 99min | -$2,518 | -$489 |
| mmirror@20+patience15 | v3 no-M | thr20 | **-$8** | -$12 | 31% | -4% | 1.09 | 100min | -$2,830 | -$623 |
| shufB1[30] | E/T/I only | top5 | **-$8** | -$3 | 30% | -1% | 2.69 | 28min | -$1,567 | -$548 |
| shufB3[30] | v3 no-M | top5 | **-$9** | -$3 | 29% | -1% | 2.80 | 29min | -$1,607 | -$379 |
| mmirror@20+patience15 | v3 no-M | thr10 | **-$10** | -$71 | 32% | -18% | 0.53 | 101min | -$3,298 | -$489 |
| class[30] | v3 no-M | thr10 | **-$10** | -$72 | 32% | -17% | 0.45 | 119min | -$3,298 | -$489 |
| class[60] | v3 no-M | thr10 | **-$10** | -$72 | 32% | -17% | 0.45 | 119min | -$3,298 | -$489 |
| close | v3 no-M | thr10 | **-$10** | -$72 | 32% | -17% | 0.45 | 119min | -$3,298 | -$489 |
| mmirror@25+patience15 | v3 no-M | thr10 | **-$11** | -$63 | 32% | -16% | 0.55 | 96min | -$3,298 | -$489 |
| class[30] | E/T/I only | top5 | **-$11** | -$5 | 30% | -1% | 2.62 | 34min | -$1,567 | -$548 |
| class[60]+mmirror@25 | E/T/I only | top5 | **-$11** | -$5 | 31% | -1% | 2.33 | 44min | -$1,567 | -$548 |
| shufA2@25 | E/T/I only | top5 | **-$11** | -$6 | 34% | -2% | 2.02 | 110min | -$1,567 | -$548 |
| mmirror@10 | v3 no-M | thr20 | **-$12** | -$20 | 32% | -5% | 1.05 | 110min | -$2,830 | -$489 |
| mmirror@20 | v3 no-M | thr10 | **-$12** | -$77 | 33% | -20% | 0.61 | 95min | -$3,298 | -$489 |
| mmirror@10+prof | v3 no-M | thr20 | **-$13** | -$22 | 32% | -6% | 0.99 | 113min | -$2,830 | -$489 |
| shufA3@25 | v3 no-M | thr10 | **-$13** | -$77 | 31% | -19% | 0.60 | 88min | -$3,298 | -$489 |
| shufB3[30] | v3 no-M | thr10 | **-$13** | -$23 | 30% | -4% | 0.58 | 39min | -$3,626 | -$548 |
| mmirror@10+patience15 | v3 no-M | thr10 | **-$13** | -$75 | 32% | -19% | 0.49 | 109min | -$3,298 | -$489 |
| close | E/T/I only | top5 | **-$14** | -$7 | 34% | -2% | 1.77 | 142min | -$1,567 | -$548 |
| mmirror@20+prof | v3 no-M | thr10 | **-$15** | -$79 | 33% | -20% | 0.56 | 101min | -$3,298 | -$489 |
| shufB2[30] | E/T/I only | top5 | **-$15** | -$6 | 30% | -1% | 2.68 | 28min | -$1,567 | -$548 |
| class[30]+mmirror@25 | v3 no-M | thr10 | **-$15** | -$69 | 32% | -18% | 0.64 | 88min | -$3,298 | -$489 |
| class[60]+mmirror@25 | v3 no-M | thr10 | **-$15** | -$69 | 32% | -18% | 0.64 | 88min | -$3,298 | -$489 |
| mmirror@25 | v3 no-M | thr10 | **-$15** | -$69 | 32% | -18% | 0.64 | 88min | -$3,298 | -$489 |
| shufA2@25 | v3 no-M | thr10 | **-$15** | -$80 | 31% | -19% | 0.60 | 87min | -$3,298 | -$489 |
| mmirror@10 | v3 no-M | thr10 | **-$16** | -$82 | 32% | -21% | 0.55 | 103min | -$3,298 | -$489 |
| shufA1@25 | v3 no-M | thr10 | **-$17** | -$80 | 31% | -21% | 0.61 | 87min | -$3,298 | -$489 |
| mirror@1.00 | v3 no-M | thr20 | **-$18** | -$17 | 30% | -5% | 2.27 | 11min | -$1,543 | -$503 |
| shufA1@25 | v3 no-M | thr20 | **-$18** | -$30 | 32% | -8% | 1.25 | 83min | -$3,016 | -$507 |
| class[30] | v3 no-M | top5 | **-$18** | -$6 | 29% | -2% | 2.70 | 38min | -$1,607 | -$435 |
| mmirror@10+prof | v3 no-M | thr10 | **-$18** | -$85 | 32% | -21% | 0.52 | 108min | -$3,298 | -$489 |
| class[30]+mmirror@25 | E/T/I only | top5 | **-$18** | -$7 | 30% | -2% | 2.77 | 29min | -$1,567 | -$548 |
| shufA2@25 | v3 no-M | top5 | **-$20** | -$11 | 32% | -3% | 1.96 | 117min | -$1,559 | -$379 |
| shufA1@25 | E/T/I only | top5 | **-$20** | -$10 | 33% | -3% | 2.07 | 109min | -$1,567 | -$416 |
| mmirror@25+prof | v3 no-M | thr10 | **-$20** | -$84 | 32% | -21% | 0.57 | 98min | -$3,298 | -$489 |
| shufB1[30] | v3 no-M | thr10 | **-$20** | -$30 | 31% | -6% | 0.59 | 35min | -$3,626 | -$548 |
| mmirror@25+patience15 | v3 no-M | thr20 | **-$21** | -$28 | 31% | -7% | 1.12 | 94min | -$2,520 | -$623 |
| class[60] | v3 no-M | top5 | **-$21** | -$9 | 29% | -3% | 2.26 | 54min | -$1,607 | -$435 |
| mirror@1.00+patience15 | v3 no-M | top5 | **-$21** | -$6 | 30% | -2% | 3.46 | 25min | -$1,607 | -$416 |
| class[30]+mmirror@25 | v3 no-M | top5 | **-$22** | -$8 | 29% | -2% | 2.80 | 35min | -$1,456 | -$435 |
| mmirror@25+patience15 | v3 no-M | top3 | **-$22** | -$14 | 33% | -4% | 1.61 | 125min | -$959 | -$435 |
| mmirror@25 | v3 no-M | top3 | **-$23** | -$14 | 32% | -4% | 1.70 | 121min | -$944 | -$435 |
| mmirror@20 | v3 no-M | thr20 | **-$24** | -$29 | 31% | -8% | 1.32 | 86min | -$2,830 | -$489 |
| shufB1[30] | v3 no-M | top5 | **-$24** | -$9 | 29% | -2% | 2.83 | 28min | -$1,607 | -$379 |
| shufB2[30] | v3 no-M | thr10 | **-$25** | -$43 | 31% | -9% | 0.57 | 49min | -$3,626 | -$548 |
| shufA2@25 | v3 no-M | top3 | **-$26** | -$17 | 32% | -4% | 1.58 | 122min | -$944 | -$392 |
| shufB2[30] | v3 no-M | top5 | **-$26** | -$9 | 29% | -2% | 2.82 | 29min | -$1,607 | -$379 |
| mmirror@20+patience15 | v3 no-M | top3 | **-$27** | -$18 | 32% | -5% | 1.58 | 128min | -$959 | -$435 |
| mmirror@25+prof | v3 no-M | top3 | **-$28** | -$19 | 32% | -5% | 1.58 | 130min | -$959 | -$435 |
| mmirror@20+prof | v3 no-M | top3 | **-$29** | -$20 | 32% | -5% | 1.56 | 133min | -$959 | -$435 |
| class[60]+mmirror@25 | v3 no-M | top5 | **-$30** | -$13 | 29% | -4% | 2.33 | 51min | -$1,559 | -$435 |
| shufA3@25 | v3 no-M | top3 | **-$31** | -$21 | 32% | -5% | 1.61 | 120min | -$959 | -$392 |
| shufA3@25 | v3 no-M | top5 | **-$32** | -$17 | 31% | -4% | 2.02 | 113min | -$1,462 | -$392 |
| mmirror@10+patience15 | v3 no-M | top3 | **-$33** | -$22 | 32% | -6% | 1.52 | 135min | -$959 | -$435 |
| close | v3 no-M | top3 | **-$33** | -$23 | 32% | -6% | 1.51 | 138min | -$959 | -$435 |
| shufA1@25 | v3 no-M | top3 | **-$35** | -$23 | 32% | -6% | 1.61 | 120min | -$957 | -$392 |
| mmirror@25 | v3 no-M | thr20 | **-$35** | -$39 | 31% | -10% | 1.40 | 78min | -$2,518 | -$489 |
| mmirror@10+prof | v3 no-M | top3 | **-$36** | -$24 | 32% | -6% | 1.53 | 136min | -$959 | -$435 |
| mmirror@10 | v3 no-M | top3 | **-$36** | -$24 | 32% | -6% | 1.54 | 135min | -$959 | -$435 |
| mmirror@20 | v3 no-M | top3 | **-$38** | -$24 | 32% | -6% | 1.64 | 125min | -$944 | -$435 |
| mmirror@25 | v3 no-M | top5 | **-$40** | -$19 | 31% | -5% | 2.16 | 115min | -$1,559 | -$435 |
| shufA1@25 | v3 no-M | top5 | **-$41** | -$22 | 31% | -6% | 2.02 | 115min | -$1,304 | -$392 |
| close | v3 no-M | top5 | **-$44** | -$24 | 31% | -6% | 1.81 | 138min | -$1,607 | -$435 |
| mmirror@25+patience15 | v3 no-M | top5 | **-$44** | -$22 | 32% | -6% | 2.01 | 120min | -$1,607 | -$435 |
| mmirror@25+prof | v3 no-M | top5 | **-$46** | -$24 | 31% | -6% | 1.94 | 126min | -$1,607 | -$435 |
| mmirror@20+prof | v3 no-M | top5 | **-$47** | -$26 | 31% | -7% | 1.89 | 130min | -$1,607 | -$435 |
| mmirror@10+patience15 | v3 no-M | top5 | **-$51** | -$28 | 31% | -7% | 1.87 | 132min | -$1,607 | -$435 |
| mmirror@20+patience15 | v3 no-M | top5 | **-$54** | -$28 | 31% | -7% | 1.96 | 123min | -$1,607 | -$435 |
| mmirror@10+prof | v3 no-M | top5 | **-$54** | -$30 | 31% | -7% | 1.86 | 134min | -$1,607 | -$435 |
| mmirror@10 | v3 no-M | top5 | **-$61** | -$33 | 30% | -8% | 1.90 | 130min | -$1,559 | -$435 |
| mmirror@20 | v3 no-M | top5 | **-$62** | -$31 | 30% | -8% | 2.05 | 120min | -$1,559 | -$435 |

## The `cont[lasso,B]@c25` overlay ON — the brief's configuration

The overlay is rung 3's drawdown keeper and is run ON for every rule, as specified.  It is also reported OFF above, because every prior rung's implementable numbers are overlay-free and the comparison has to be like-for-like.

| rule | arm | stream | $/day OFF | $/day ON | hold OFF | hold ON | worst day OFF | worst day ON |
|---|---|---|---|---|---|---|---|---|
| oracle | E/T/I only | top5 | $1,125 | $36 | 89min | 1min | -$400 | -$492 |
| oracle | v3 no-M | top5 | $1,069 | $30 | 83min | 1min | -$309 | -$497 |
| oracle | E/T/I only | top3 | $900 | $23 | 90min | 1min | -$310 | -$694 |
| oracle | v3 no-M | top3 | $841 | $29 | 79min | 1min | -$291 | -$384 |
| oracle | E/T/I only | thr20 | $559 | $56 | 72min | 1min | -$313 | -$940 |
| oracle | v3 no-M | thr20 | $557 | $56 | 54min | 1min | -$313 | -$535 |
| oracle | v3 no-M | thr10 | $269 | $28 | 43min | 1min | -$313 | -$345 |
| oracle | E/T/I only | thr10 | $266 | $27 | 87min | 1min | -$316 | -$492 |
| mmirror@10+prof | E/T/I only | thr20 | $66 | $7 | 114min | 1min | -$2,142 | -$1,065 |
| close | E/T/I only | thr20 | $63 | $7 | 128min | 1min | -$1,815 | -$1,065 |
| mmirror@25+prof | E/T/I only | thr20 | $56 | $5 | 77min | 1min | -$2,142 | -$1,065 |
| mmirror@20+prof | E/T/I only | thr20 | $53 | $5 | 91min | 1min | -$2,142 | -$1,065 |
| mmirror@10 | E/T/I only | thr20 | $52 | $6 | 105min | 1min | -$2,142 | -$1,065 |
| mmirror@10+patience15 | E/T/I only | thr20 | $51 | $7 | 109min | 1min | -$2,142 | -$1,065 |
| class[30] | E/T/I only | thr20 | $50 | $7 | 50min | 1min | -$1,821 | -$1,065 |
| mmirror@10+prof | E/T/I only | thr10 | $49 | $8 | 158min | 1min | -$3,086 | -$874 |
| class[30] | E/T/I only | top3 | $43 | -$3 | 40min | 1min | -$985 | -$694 |
| mmirror@25+prof | E/T/I only | top5 | $41 | -$5 | 120min | 1min | -$1,567 | -$874 |
| mmirror@20+prof | E/T/I only | thr10 | $40 | $7 | 140min | 1min | -$3,086 | -$874 |
| mmirror@25+prof | E/T/I only | thr10 | $39 | $7 | 133min | 1min | -$3,086 | -$874 |
| mmirror@25 | E/T/I only | thr20 | $39 | $7 | 61min | 1min | -$2,622 | -$1,101 |
| mmirror@25+patience15 | E/T/I only | thr20 | $39 | $7 | 73min | 1min | -$2,622 | -$1,065 |
| class[30]+mmirror@25 | E/T/I only | thr20 | $38 | $4 | 33min | 1min | -$2,020 | -$1,065 |
| mmirror@20 | E/T/I only | thr20 | $37 | $6 | 76min | 1min | -$2,622 | -$1,101 |
| mmirror@20+patience15 | E/T/I only | thr20 | $36 | $7 | 87min | 1min | -$2,622 | -$1,065 |
| class[60] | E/T/I only | thr10 | $34 | $8 | 178min | 1min | -$3,086 | -$874 |
| class[30] | E/T/I only | thr10 | $34 | $8 | 178min | 1min | -$3,086 | -$874 |
| close | E/T/I only | thr10 | $34 | $8 | 178min | 1min | -$3,086 | -$874 |
| mirror@1.00 | E/T/I only | top3 | $33 | -$4 | 19min | 1min | -$856 | -$518 |
| mirror@1.00 | v3 no-M | top3 | $33 | $1 | 19min | 1min | -$854 | -$474 |
| mmirror@25+prof | E/T/I only | top3 | $32 | -$5 | 129min | 1min | -$985 | -$694 |
| mirror@1.00+patience15 | E/T/I only | top3 | $32 | -$3 | 24min | 1min | -$985 | -$694 |
| class[60] | E/T/I only | thr20 | $32 | $7 | 61min | 1min | -$2,251 | -$1,065 |
| mmirror@10 | E/T/I only | thr10 | $31 | $7 | 149min | 1min | -$3,086 | -$874 |
| mmirror@20+prof | E/T/I only | top5 | $31 | -$5 | 127min | 1min | -$1,567 | -$874 |
| mmirror@10+patience15 | E/T/I only | thr10 | $29 | $8 | 155min | 1min | -$3,086 | -$874 |
| class[30]+mmirror@25 | E/T/I only | top3 | $28 | -$4 | 31min | 1min | -$985 | -$694 |
| class[60] | v3 no-M | thr20 | $23 | -$4 | 63min | 1min | -$2,830 | -$997 |
| mmirror@20+prof | E/T/I only | top3 | $22 | -$5 | 136min | 1min | -$985 | -$694 |
| class[60] | E/T/I only | top3 | $22 | -$4 | 56min | 1min | -$985 | -$694 |
| class[60]+mmirror@25 | E/T/I only | thr20 | $22 | $4 | 45min | 1min | -$2,466 | -$1,065 |
| mmirror@20+patience15 | E/T/I only | thr10 | $22 | $8 | 135min | 1min | -$3,086 | -$874 |
| class[60]+mmirror@25 | v3 no-M | thr20 | $22 | -$2 | 55min | 1min | -$2,830 | -$901 |
| mmirror@20 | E/T/I only | thr10 | $22 | $7 | 129min | 1min | -$3,086 | -$874 |
| mirror@1.00 | E/T/I only | thr10 | $20 | $9 | 14min | 1min | -$1,160 | -$560 |
| mmirror@25+patience15 | E/T/I only | thr10 | $20 | $8 | 129min | 1min | -$3,086 | -$874 |
| mmirror@25 | E/T/I only | top3 | $18 | -$4 | 115min | 1min | -$985 | -$694 |
| mmirror@25 | E/T/I only | thr10 | $18 | $7 | 122min | 1min | -$3,086 | -$874 |
| class[30]+mmirror@25 | E/T/I only | thr10 | $18 | $7 | 122min | 1min | -$3,086 | -$874 |
| class[60]+mmirror@25 | E/T/I only | thr10 | $18 | $7 | 122min | 1min | -$3,086 | -$874 |
| close | E/T/I only | top3 | $18 | -$4 | 151min | 1min | -$985 | -$694 |
| mirror@1.00+patience15 | E/T/I only | thr10 | $18 | $8 | 19min | 1min | -$2,360 | -$874 |
| mmirror@10+prof | E/T/I only | top3 | $18 | -$4 | 144min | 1min | -$985 | -$694 |
| mirror@1.00+patience15 | E/T/I only | thr20 | $17 | $7 | 18min | 1min | -$2,904 | -$1,065 |
| mmirror@25 | E/T/I only | top5 | $16 | -$7 | 102min | 1min | -$1,567 | -$874 |
| mmirror@25+patience15 | E/T/I only | top5 | $16 | -$5 | 112min | 1min | -$1,567 | -$874 |
| mmirror@20 | E/T/I only | top3 | $13 | -$4 | 124min | 1min | -$985 | -$694 |
| mirror@1.00 | v3 no-M | top5 | $12 | -$15 | 20min | 1min | -$1,309 | -$559 |
| mmirror@25+patience15 | E/T/I only | top3 | $12 | -$4 | 120min | 1min | -$985 | -$694 |
| mmirror@20+patience15 | E/T/I only | top3 | $11 | -$4 | 128min | 1min | -$985 | -$694 |
| class[30] | v3 no-M | top3 | $8 | $3 | 42min | 1min | -$959 | -$514 |
| mmirror@20+patience15 | E/T/I only | top5 | $7 | -$5 | 118min | 1min | -$1,567 | -$874 |
| mmirror@20 | E/T/I only | top5 | $7 | -$8 | 114min | 1min | -$1,567 | -$874 |
| mirror@1.00 | v3 no-M | thr10 | $6 | $1 | 11min | 1min | -$1,250 | -$1,236 |
| mmirror@10+patience15 | E/T/I only | top3 | $6 | -$4 | 141min | 1min | -$985 | -$694 |
| class[30]+mmirror@25 | v3 no-M | top3 | $5 | $3 | 39min | 1min | -$944 | -$514 |
| mmirror@10+prof | E/T/I only | top5 | $5 | -$5 | 136min | 1min | -$1,567 | -$874 |
| mmirror@10 | E/T/I only | top3 | $4 | -$4 | 139min | 1min | -$985 | -$694 |
| class[60]+mmirror@25 | E/T/I only | top3 | $4 | -$4 | 46min | 1min | -$985 | -$694 |
| mmirror@20+prof | v3 no-M | thr20 | $3 | -$2 | 104min | 1min | -$2,830 | -$997 |
| mirror@1.00+patience15 | E/T/I only | top5 | $2 | -$4 | 25min | 1min | -$1,567 | -$874 |
| close | v3 no-M | thr20 | $2 | -$4 | 127min | 1min | -$2,830 | -$997 |
| mirror@1.00+patience15 | v3 no-M | thr20 | $1 | -$4 | 18min | 1min | -$2,267 | -$997 |
| mirror@1.00 | E/T/I only | thr20 | -$1 | $2 | 10min | 1min | -$1,714 | -$1,219 |
| class[60] | v3 no-M | top3 | -$1 | $2 | 58min | 1min | -$959 | -$514 |
| mmirror@10 | E/T/I only | top5 | -$1 | -$5 | 131min | 1min | -$1,567 | -$874 |
| class[30] | v3 no-M | thr20 | -$2 | -$4 | 52min | 1min | -$2,830 | -$997 |
| class[30]+mmirror@25 | v3 no-M | thr20 | -$2 | -$2 | 44min | 1min | -$2,830 | -$901 |
| mirror@1.00 | E/T/I only | top5 | -$3 | -$6 | 19min | 1min | -$1,416 | -$560 |
| class[60]+mmirror@25 | v3 no-M | top3 | -$4 | $2 | 54min | 1min | -$944 | -$514 |
| mirror@1.00+patience15 | v3 no-M | thr10 | -$4 | -$0 | 17min | 1min | -$2,003 | -$892 |
| mirror@1.00+patience15 | v3 no-M | top3 | -$5 | $3 | 24min | 1min | -$959 | -$514 |
| mmirror@10+patience15 | v3 no-M | thr20 | -$5 | -$4 | 114min | 1min | -$2,830 | -$997 |
| class[60] | E/T/I only | top5 | -$6 | -$5 | 50min | 1min | -$1,567 | -$874 |
| mmirror@10+patience15 | E/T/I only | top5 | -$7 | -$5 | 132min | 1min | -$1,567 | -$874 |
| mmirror@25+prof | v3 no-M | thr20 | -$8 | -$2 | 99min | 1min | -$2,518 | -$997 |
| mmirror@20+patience15 | v3 no-M | thr20 | -$8 | -$4 | 100min | 1min | -$2,830 | -$997 |
| mmirror@20+patience15 | v3 no-M | thr10 | -$10 | -$0 | 101min | 1min | -$3,298 | -$892 |
| class[30] | v3 no-M | thr10 | -$10 | -$0 | 119min | 1min | -$3,298 | -$892 |
| class[60] | v3 no-M | thr10 | -$10 | -$0 | 119min | 1min | -$3,298 | -$892 |
| close | v3 no-M | thr10 | -$10 | -$0 | 119min | 1min | -$3,298 | -$892 |
| mmirror@25+patience15 | v3 no-M | thr10 | -$11 | -$0 | 96min | 1min | -$3,298 | -$892 |
| class[30] | E/T/I only | top5 | -$11 | -$4 | 34min | 1min | -$1,567 | -$874 |
| class[60]+mmirror@25 | E/T/I only | top5 | -$11 | -$5 | 44min | 1min | -$1,567 | -$874 |
| mmirror@10 | v3 no-M | thr20 | -$12 | -$3 | 110min | 1min | -$2,830 | -$1,059 |
| mmirror@20 | v3 no-M | thr10 | -$12 | $0 | 95min | 1min | -$3,298 | -$764 |
| mmirror@10+prof | v3 no-M | thr20 | -$13 | -$2 | 113min | 1min | -$2,830 | -$997 |
| mmirror@10+patience15 | v3 no-M | thr10 | -$13 | -$0 | 109min | 1min | -$3,298 | -$892 |
| close | E/T/I only | top5 | -$14 | -$5 | 142min | 1min | -$1,567 | -$874 |
| mmirror@20+prof | v3 no-M | thr10 | -$15 | -$1 | 101min | 1min | -$3,298 | -$892 |
| class[30]+mmirror@25 | v3 no-M | thr10 | -$15 | -$0 | 88min | 1min | -$3,298 | -$756 |
| class[60]+mmirror@25 | v3 no-M | thr10 | -$15 | -$0 | 88min | 1min | -$3,298 | -$756 |
| mmirror@25 | v3 no-M | thr10 | -$15 | -$0 | 88min | 1min | -$3,298 | -$756 |
| mmirror@10 | v3 no-M | thr10 | -$16 | $0 | 103min | 1min | -$3,298 | -$892 |
| mirror@1.00 | v3 no-M | thr20 | -$18 | $0 | 11min | 1min | -$1,543 | -$798 |
| class[30] | v3 no-M | top5 | -$18 | -$12 | 38min | 1min | -$1,607 | -$638 |
| mmirror@10+prof | v3 no-M | thr10 | -$18 | -$1 | 108min | 1min | -$3,298 | -$892 |
| class[30]+mmirror@25 | E/T/I only | top5 | -$18 | -$5 | 29min | 1min | -$1,567 | -$874 |
| mmirror@25+prof | v3 no-M | thr10 | -$20 | -$1 | 98min | 1min | -$3,298 | -$892 |
| mmirror@25+patience15 | v3 no-M | thr20 | -$21 | -$4 | 94min | 1min | -$2,520 | -$997 |
| class[60] | v3 no-M | top5 | -$21 | -$13 | 54min | 1min | -$1,607 | -$638 |
| mirror@1.00+patience15 | v3 no-M | top5 | -$21 | -$12 | 25min | 1min | -$1,607 | -$638 |
| class[30]+mmirror@25 | v3 no-M | top5 | -$22 | -$12 | 35min | 1min | -$1,456 | -$638 |
| mmirror@25+patience15 | v3 no-M | top3 | -$22 | $2 | 125min | 1min | -$959 | -$514 |
| mmirror@25 | v3 no-M | top3 | -$23 | $2 | 121min | 1min | -$944 | -$514 |
| mmirror@20 | v3 no-M | thr20 | -$24 | -$2 | 86min | 1min | -$2,830 | -$886 |
| mmirror@20+patience15 | v3 no-M | top3 | -$27 | $2 | 128min | 1min | -$959 | -$514 |
| mmirror@25+prof | v3 no-M | top3 | -$28 | $2 | 130min | 1min | -$959 | -$514 |
| mmirror@20+prof | v3 no-M | top3 | -$29 | $2 | 133min | 1min | -$959 | -$514 |
| class[60]+mmirror@25 | v3 no-M | top5 | -$30 | -$13 | 51min | 1min | -$1,559 | -$638 |
| mmirror@10+patience15 | v3 no-M | top3 | -$33 | $2 | 135min | 1min | -$959 | -$514 |
| close | v3 no-M | top3 | -$33 | $2 | 138min | 1min | -$959 | -$514 |
| mmirror@25 | v3 no-M | thr20 | -$35 | -$2 | 78min | 1min | -$2,518 | -$901 |
| mmirror@10+prof | v3 no-M | top3 | -$36 | $2 | 136min | 1min | -$959 | -$514 |
| mmirror@10 | v3 no-M | top3 | -$36 | $2 | 135min | 1min | -$959 | -$514 |
| mmirror@20 | v3 no-M | top3 | -$38 | $2 | 125min | 1min | -$944 | -$514 |
| mmirror@25 | v3 no-M | top5 | -$40 | -$13 | 115min | 1min | -$1,559 | -$638 |
| close | v3 no-M | top5 | -$44 | -$14 | 138min | 1min | -$1,607 | -$638 |
| mmirror@25+patience15 | v3 no-M | top5 | -$44 | -$14 | 120min | 1min | -$1,607 | -$638 |
| mmirror@25+prof | v3 no-M | top5 | -$46 | -$14 | 126min | 1min | -$1,607 | -$638 |
| mmirror@20+prof | v3 no-M | top5 | -$47 | -$14 | 130min | 1min | -$1,607 | -$638 |
| mmirror@10+patience15 | v3 no-M | top5 | -$51 | -$14 | 132min | 1min | -$1,607 | -$638 |
| mmirror@20+patience15 | v3 no-M | top5 | -$54 | -$14 | 123min | 1min | -$1,607 | -$638 |
| mmirror@10+prof | v3 no-M | top5 | -$54 | -$13 | 134min | 1min | -$1,607 | -$638 |
| mmirror@10 | v3 no-M | top5 | -$61 | -$13 | 130min | 1min | -$1,559 | -$638 |
| mmirror@20 | v3 no-M | top5 | -$62 | -$13 | 120min | 1min | -$1,559 | -$638 |

## Full panel — every (era, arm, stream, rule, overlay) cell

Written in full to `rung4_segments/rung4_cells.tsv`; the overlay-OFF rows are reproduced here.

| era | arm | stream | rule | $/day | $/trade | winner share | entered cert/day | capture entered | trades/day | mean hold | worst day | worst trade | win rate | stop rate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `blind_e3` | E/T/I only | thr10 | class[30] | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | class[30]+mmirror@25 | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | class[60] | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | class[60]+mmirror@25 | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | close | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | mirror@1.00 | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | mirror@1.00+patience15 | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | mmirror@10 | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | mmirror@10+patience15 | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | mmirror@10+prof | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | mmirror@20 | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | mmirror@20+patience15 | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | mmirror@20+prof | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | mmirror@25 | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | mmirror@25+patience15 | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | mmirror@25+prof | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | oracle | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | shufA1@25 | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | shufA2@25 | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | shufA3@25 | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | shufB1[30] | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | shufB2[30] | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr10 | shufB3[30] | **$0** | n/a | n/a% | $0 | n/a% | 0.00 | n/amin | $0 | n/a | n/a% | n/a% |
| `blind_e3` | E/T/I only | thr20 | class[30] | **-$38** | -$190 | 25% | $66 | -57% | 0.20 | 20min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | thr20 | class[30]+mmirror@25 | **-$38** | -$190 | 25% | $66 | -57% | 0.20 | 20min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | thr20 | class[60] | **-$30** | -$152 | 25% | $66 | -46% | 0.20 | 28min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | thr20 | class[60]+mmirror@25 | **-$30** | -$152 | 25% | $66 | -46% | 0.20 | 28min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | thr20 | close | **$9** | $47 | 25% | $66 | 14% | 0.20 | 100min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | thr20 | mirror@1.00 | **-$8** | -$27 | 17% | $75 | -11% | 0.30 | 7min | -$376 | -$182 | 33% | 0% |
| `blind_e3` | E/T/I only | thr20 | mirror@1.00+patience15 | **-$21** | -$103 | 25% | $66 | -31% | 0.20 | 15min | -$541 | -$300 | 25% | 25% |
| `blind_e3` | E/T/I only | thr20 | mmirror@10 | **$9** | $47 | 25% | $66 | 14% | 0.20 | 100min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | thr20 | mmirror@10+patience15 | **$9** | $47 | 25% | $66 | 14% | 0.20 | 100min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | thr20 | mmirror@10+prof | **$9** | $47 | 25% | $66 | 14% | 0.20 | 100min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | thr20 | mmirror@20 | **$9** | $47 | 25% | $66 | 14% | 0.20 | 100min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | thr20 | mmirror@20+patience15 | **$9** | $47 | 25% | $66 | 14% | 0.20 | 100min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | thr20 | mmirror@20+prof | **$9** | $47 | 25% | $66 | 14% | 0.20 | 100min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | thr20 | mmirror@25 | **$24** | $119 | 25% | $66 | 36% | 0.20 | 97min | -$600 | -$300 | 25% | 50% |
| `blind_e3` | E/T/I only | thr20 | mmirror@25+patience15 | **$22** | $112 | 25% | $66 | 34% | 0.20 | 98min | -$600 | -$300 | 25% | 50% |
| `blind_e3` | E/T/I only | thr20 | mmirror@25+prof | **$9** | $47 | 25% | $66 | 14% | 0.20 | 100min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | thr20 | oracle | **$70** | $279 | 20% | $68 | 102% | 0.25 | 63min | -$205 | -$300 | 80% | 20% |
| `blind_e3` | E/T/I only | thr20 | shufA1@25 | **$9** | $47 | 25% | $66 | 14% | 0.20 | 100min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | thr20 | shufA2@25 | **$9** | $47 | 25% | $66 | 14% | 0.20 | 100min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | thr20 | shufA3@25 | **$9** | $47 | 25% | $66 | 14% | 0.20 | 100min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | thr20 | shufB1[30] | **-$38** | -$190 | 25% | $66 | -57% | 0.20 | 20min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | thr20 | shufB2[30] | **-$38** | -$190 | 25% | $66 | -57% | 0.20 | 20min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | thr20 | shufB3[30] | **-$38** | -$190 | 25% | $66 | -57% | 0.20 | 20min | -$600 | -$300 | 25% | 75% |
| `blind_e3` | E/T/I only | top3 | class[30] | **$61** | $35 | 37% | $882 | 7% | 1.75 | 26min | -$630 | -$326 | 46% | 26% |
| `blind_e3` | E/T/I only | top3 | class[30]+mmirror@25 | **$61** | $35 | 37% | $882 | 7% | 1.75 | 26min | -$630 | -$326 | 46% | 26% |
| `blind_e3` | E/T/I only | top3 | class[60] | **-$56** | -$38 | 28% | $597 | -9% | 1.45 | 44min | -$630 | -$326 | 38% | 38% |
| `blind_e3` | E/T/I only | top3 | class[60]+mmirror@25 | **-$56** | -$38 | 28% | $597 | -9% | 1.45 | 44min | -$630 | -$326 | 38% | 38% |
| `blind_e3` | E/T/I only | top3 | close | **-$95** | -$73 | 27% | $541 | -18% | 1.30 | 144min | -$630 | -$326 | 19% | 81% |
| `blind_e3` | E/T/I only | top3 | mirror@1.00 | **$4** | $1 | 24% | $1,057 | 0% | 2.90 | 12min | -$377 | -$307 | 31% | 2% |
| `blind_e3` | E/T/I only | top3 | mirror@1.00+patience15 | **$65** | $32 | 32% | $913 | 7% | 2.05 | 20min | -$542 | -$340 | 51% | 17% |
| `blind_e3` | E/T/I only | top3 | mmirror@10 | **-$95** | -$73 | 27% | $541 | -18% | 1.30 | 144min | -$630 | -$326 | 19% | 81% |
| `blind_e3` | E/T/I only | top3 | mmirror@10+patience15 | **-$95** | -$73 | 27% | $541 | -18% | 1.30 | 144min | -$630 | -$326 | 19% | 81% |
| `blind_e3` | E/T/I only | top3 | mmirror@10+prof | **-$95** | -$73 | 27% | $541 | -18% | 1.30 | 144min | -$630 | -$326 | 19% | 81% |
| `blind_e3` | E/T/I only | top3 | mmirror@20 | **-$177** | -$131 | 26% | $551 | -32% | 1.35 | 128min | -$630 | -$326 | 19% | 81% |
| `blind_e3` | E/T/I only | top3 | mmirror@20+patience15 | **-$177** | -$131 | 26% | $551 | -32% | 1.35 | 128min | -$630 | -$326 | 19% | 81% |
| `blind_e3` | E/T/I only | top3 | mmirror@20+prof | **-$177** | -$131 | 26% | $551 | -32% | 1.35 | 128min | -$630 | -$326 | 19% | 81% |
| `blind_e3` | E/T/I only | top3 | mmirror@25 | **-$110** | -$73 | 30% | $713 | -15% | 1.50 | 124min | -$630 | -$340 | 27% | 70% |
| `blind_e3` | E/T/I only | top3 | mmirror@25+patience15 | **-$106** | -$73 | 31% | $703 | -15% | 1.45 | 128min | -$630 | -$340 | 28% | 72% |
| `blind_e3` | E/T/I only | top3 | mmirror@25+prof | **-$124** | -$83 | 30% | $713 | -17% | 1.50 | 124min | -$630 | -$340 | 27% | 73% |
| `blind_e3` | E/T/I only | top3 | oracle | **$594** | $396 | 27% | $588 | 101% | 1.50 | 63min | -$259 | -$304 | 93% | 7% |
| `blind_e3` | E/T/I only | top3 | shufA1@25 | **-$146** | -$112 | 27% | $541 | -27% | 1.30 | 134min | -$630 | -$326 | 19% | 81% |
| `blind_e3` | E/T/I only | top3 | shufA2@25 | **-$68** | -$51 | 30% | $605 | -11% | 1.35 | 139min | -$630 | -$326 | 26% | 74% |
| `blind_e3` | E/T/I only | top3 | shufA3@25 | **-$2** | -$2 | 30% | $605 | -0% | 1.35 | 140min | -$630 | -$326 | 26% | 74% |
| `blind_e3` | E/T/I only | top3 | shufB1[30] | **$61** | $35 | 37% | $882 | 7% | 1.75 | 26min | -$630 | -$326 | 46% | 26% |
| `blind_e3` | E/T/I only | top3 | shufB2[30] | **$61** | $35 | 37% | $882 | 7% | 1.75 | 26min | -$630 | -$326 | 46% | 26% |
| `blind_e3` | E/T/I only | top3 | shufB3[30] | **$61** | $35 | 37% | $882 | 7% | 1.75 | 26min | -$630 | -$326 | 46% | 26% |
| `blind_e3` | E/T/I only | top5 | class[30] | **$9** | $4 | 25% | $858 | 1% | 2.40 | 26min | -$630 | -$326 | 44% | 27% |
| `blind_e3` | E/T/I only | top5 | class[30]+mmirror@25 | **$9** | $4 | 25% | $858 | 1% | 2.40 | 26min | -$630 | -$326 | 44% | 27% |
| `blind_e3` | E/T/I only | top5 | class[60] | **-$79** | -$39 | 22% | $669 | -12% | 2.05 | 46min | -$924 | -$326 | 39% | 39% |
| `blind_e3` | E/T/I only | top5 | class[60]+mmirror@25 | **-$79** | -$39 | 22% | $669 | -12% | 2.05 | 46min | -$924 | -$326 | 39% | 39% |
| `blind_e3` | E/T/I only | top5 | close | **-$115** | -$70 | 24% | $606 | -19% | 1.65 | 136min | -$924 | -$326 | 24% | 76% |
| `blind_e3` | E/T/I only | top5 | mirror@1.00 | **-$57** | -$12 | 26% | $1,771 | -3% | 4.85 | 12min | -$552 | -$307 | 30% | 1% |
| `blind_e3` | E/T/I only | top5 | mirror@1.00+patience15 | **$49** | $15 | 29% | $1,240 | 4% | 3.15 | 20min | -$676 | -$340 | 51% | 17% |
| `blind_e3` | E/T/I only | top5 | mmirror@10 | **-$115** | -$70 | 24% | $606 | -19% | 1.65 | 136min | -$924 | -$326 | 24% | 76% |
| `blind_e3` | E/T/I only | top5 | mmirror@10+patience15 | **-$115** | -$70 | 24% | $606 | -19% | 1.65 | 136min | -$924 | -$326 | 24% | 76% |
| `blind_e3` | E/T/I only | top5 | mmirror@10+prof | **-$115** | -$70 | 24% | $606 | -19% | 1.65 | 136min | -$924 | -$326 | 24% | 76% |
| `blind_e3` | E/T/I only | top5 | mmirror@20 | **-$104** | -$63 | 27% | $665 | -16% | 1.65 | 133min | -$924 | -$326 | 27% | 70% |
| `blind_e3` | E/T/I only | top5 | mmirror@20+patience15 | **-$197** | -$116 | 24% | $616 | -32% | 1.70 | 124min | -$924 | -$326 | 24% | 76% |
| `blind_e3` | E/T/I only | top5 | mmirror@20+prof | **-$197** | -$116 | 24% | $616 | -32% | 1.70 | 124min | -$924 | -$326 | 24% | 76% |
| `blind_e3` | E/T/I only | top5 | mmirror@25 | **-$4** | -$2 | 32% | $987 | -0% | 2.00 | 123min | -$924 | -$340 | 35% | 57% |
| `blind_e3` | E/T/I only | top5 | mmirror@25+patience15 | **-$109** | -$57 | 26% | $781 | -14% | 1.90 | 117min | -$924 | -$340 | 32% | 68% |
| `blind_e3` | E/T/I only | top5 | mmirror@25+prof | **-$141** | -$74 | 26% | $789 | -18% | 1.90 | 118min | -$924 | -$340 | 32% | 68% |
| `blind_e3` | E/T/I only | top5 | oracle | **$955** | $455 | 36% | $948 | 101% | 2.10 | 92min | -$251 | -$312 | 90% | 10% |
| `blind_e3` | E/T/I only | top5 | shufA1@25 | **-$147** | -$89 | 24% | $606 | -24% | 1.65 | 122min | -$924 | -$326 | 27% | 73% |
| `blind_e3` | E/T/I only | top5 | shufA2@25 | **-$77** | -$45 | 26% | $670 | -11% | 1.70 | 125min | -$924 | -$326 | 32% | 68% |
| `blind_e3` | E/T/I only | top5 | shufA3@25 | **$32** | $20 | 30% | $719 | 5% | 1.65 | 134min | -$924 | -$326 | 33% | 64% |
| `blind_e3` | E/T/I only | top5 | shufB1[30] | **$9** | $4 | 25% | $858 | 1% | 2.40 | 26min | -$630 | -$326 | 44% | 27% |
| `blind_e3` | E/T/I only | top5 | shufB2[30] | **$9** | $4 | 25% | $858 | 1% | 2.40 | 26min | -$630 | -$326 | 44% | 27% |
| `blind_e3` | E/T/I only | top5 | shufB3[30] | **$9** | $4 | 25% | $858 | 1% | 2.40 | 26min | -$630 | -$326 | 44% | 27% |
| `blind_e3` | v3 no-M | thr10 | class[30] | **$82** | $182 | 33% | $262 | 31% | 0.45 | 136min | -$626 | -$321 | 33% | 67% |
| `blind_e3` | v3 no-M | thr10 | class[30]+mmirror@25 | **$125** | $279 | 33% | $262 | 48% | 0.45 | 125min | -$421 | -$321 | 56% | 33% |
| `blind_e3` | v3 no-M | thr10 | class[60] | **$82** | $182 | 33% | $262 | 31% | 0.45 | 136min | -$626 | -$321 | 33% | 67% |
| `blind_e3` | v3 no-M | thr10 | class[60]+mmirror@25 | **$125** | $279 | 33% | $262 | 48% | 0.45 | 125min | -$421 | -$321 | 56% | 33% |
| `blind_e3` | v3 no-M | thr10 | close | **$82** | $182 | 33% | $262 | 31% | 0.45 | 136min | -$626 | -$321 | 33% | 67% |
| `blind_e3` | v3 no-M | thr10 | mirror@1.00 | **$24** | $31 | 33% | $445 | 5% | 0.75 | 9min | -$414 | -$152 | 47% | 0% |
| `blind_e3` | v3 no-M | thr10 | mirror@1.00+patience15 | **$13** | $19 | 31% | $343 | 4% | 0.65 | 16min | -$601 | -$333 | 54% | 15% |
| `blind_e3` | v3 no-M | thr10 | mmirror@10 | **$82** | $182 | 33% | $262 | 31% | 0.45 | 136min | -$626 | -$321 | 33% | 67% |
| `blind_e3` | v3 no-M | thr10 | mmirror@10+patience15 | **$82** | $182 | 33% | $262 | 31% | 0.45 | 136min | -$626 | -$321 | 33% | 67% |
| `blind_e3` | v3 no-M | thr10 | mmirror@10+prof | **$82** | $182 | 33% | $262 | 31% | 0.45 | 136min | -$626 | -$321 | 33% | 67% |
| `blind_e3` | v3 no-M | thr10 | mmirror@20 | **$99** | $221 | 33% | $262 | 38% | 0.45 | 133min | -$626 | -$321 | 44% | 56% |
| `blind_e3` | v3 no-M | thr10 | mmirror@20+patience15 | **$99** | $221 | 33% | $262 | 38% | 0.45 | 133min | -$626 | -$321 | 44% | 56% |
| `blind_e3` | v3 no-M | thr10 | mmirror@20+prof | **$99** | $221 | 33% | $262 | 38% | 0.45 | 133min | -$626 | -$321 | 44% | 56% |
| `blind_e3` | v3 no-M | thr10 | mmirror@25 | **$125** | $279 | 33% | $262 | 48% | 0.45 | 125min | -$421 | -$321 | 56% | 33% |
| `blind_e3` | v3 no-M | thr10 | mmirror@25+patience15 | **$115** | $256 | 33% | $262 | 44% | 0.45 | 127min | -$421 | -$321 | 44% | 33% |
| `blind_e3` | v3 no-M | thr10 | mmirror@25+prof | **$115** | $256 | 33% | $262 | 44% | 0.45 | 131min | -$626 | -$321 | 56% | 44% |
| `blind_e3` | v3 no-M | thr10 | oracle | **$268** | $488 | 27% | $266 | 101% | 0.55 | 61min | $0 | $18 | 100% | 0% |
| `blind_e3` | v3 no-M | thr10 | shufA1@25 | **$126** | $253 | 30% | $278 | 46% | 0.50 | 111min | -$244 | -$310 | 50% | 20% |
| `blind_e3` | v3 no-M | thr10 | shufA2@25 | **$111** | $223 | 30% | $263 | 42% | 0.50 | 111min | -$502 | -$333 | 30% | 30% |
| `blind_e3` | v3 no-M | thr10 | shufA3@25 | **$104** | $208 | 30% | $268 | 39% | 0.50 | 94min | -$485 | -$321 | 40% | 40% |
| `blind_e3` | v3 no-M | thr10 | shufB1[30] | **$44** | $79 | 36% | $341 | 13% | 0.55 | 27min | -$271 | -$310 | 64% | 27% |
| `blind_e3` | v3 no-M | thr10 | shufB2[30] | **$66** | $132 | 40% | $325 | 20% | 0.50 | 54min | -$271 | -$310 | 60% | 30% |
| `blind_e3` | v3 no-M | thr10 | shufB3[30] | **$91** | $182 | 40% | $325 | 28% | 0.50 | 81min | -$271 | -$310 | 60% | 30% |
| `blind_e3` | v3 no-M | thr20 | class[30] | **$92** | $115 | 38% | $426 | 22% | 0.80 | 87min | -$626 | -$321 | 44% | 44% |
| `blind_e3` | v3 no-M | thr20 | class[30]+mmirror@25 | **$93** | $109 | 35% | $428 | 22% | 0.85 | 80min | -$603 | -$321 | 41% | 35% |
| `blind_e3` | v3 no-M | thr20 | class[60] | **$148** | $198 | 40% | $405 | 37% | 0.75 | 100min | -$626 | -$321 | 47% | 47% |
| `blind_e3` | v3 no-M | thr20 | class[60]+mmirror@25 | **$143** | $179 | 38% | $408 | 35% | 0.80 | 93min | -$726 | -$321 | 44% | 44% |
| `blind_e3` | v3 no-M | thr20 | close | **$106** | $152 | 36% | $377 | 28% | 0.70 | 151min | -$901 | -$321 | 36% | 64% |
| `blind_e3` | v3 no-M | thr20 | mirror@1.00 | **$61** | $36 | 32% | $851 | 7% | 1.70 | 10min | -$654 | -$152 | 35% | 0% |
| `blind_e3` | v3 no-M | thr20 | mirror@1.00+patience15 | **$50** | $40 | 32% | $616 | 8% | 1.25 | 18min | -$706 | -$333 | 52% | 16% |
| `blind_e3` | v3 no-M | thr20 | mmirror@10 | **$111** | $139 | 31% | $393 | 28% | 0.80 | 122min | -$878 | -$321 | 44% | 56% |
| `blind_e3` | v3 no-M | thr20 | mmirror@10+patience15 | **$128** | $170 | 33% | $386 | 33% | 0.75 | 130min | -$878 | -$321 | 47% | 53% |
| `blind_e3` | v3 no-M | thr20 | mmirror@10+prof | **$111** | $139 | 31% | $393 | 28% | 0.80 | 122min | -$878 | -$321 | 44% | 56% |
| `blind_e3` | v3 no-M | thr20 | mmirror@20 | **$113** | $133 | 29% | $413 | 27% | 0.85 | 122min | -$831 | -$321 | 47% | 53% |
| `blind_e3` | v3 no-M | thr20 | mmirror@20+patience15 | **$130** | $163 | 31% | $406 | 32% | 0.80 | 129min | -$831 | -$321 | 50% | 50% |
| `blind_e3` | v3 no-M | thr20 | mmirror@20+prof | **$113** | $133 | 29% | $413 | 27% | 0.85 | 122min | -$831 | -$321 | 47% | 53% |
| `blind_e3` | v3 no-M | thr20 | mmirror@25 | **$162** | $162 | 30% | $475 | 34% | 1.00 | 119min | -$831 | -$321 | 50% | 40% |
| `blind_e3` | v3 no-M | thr20 | mmirror@25+patience15 | **$125** | $147 | 29% | $409 | 31% | 0.85 | 121min | -$831 | -$321 | 47% | 47% |
| `blind_e3` | v3 no-M | thr20 | mmirror@25+prof | **$113** | $126 | 28% | $413 | 27% | 0.90 | 114min | -$831 | -$321 | 50% | 50% |
| `blind_e3` | v3 no-M | thr20 | oracle | **$406** | $427 | 26% | $388 | 105% | 0.95 | 66min | -$286 | -$301 | 89% | 11% |
| `blind_e3` | v3 no-M | thr20 | shufA1@25 | **$153** | $192 | 31% | $395 | 39% | 0.80 | 121min | -$411 | -$310 | 44% | 31% |
| `blind_e3` | v3 no-M | thr20 | shufA2@25 | **$133** | $167 | 31% | $380 | 35% | 0.80 | 121min | -$749 | -$333 | 31% | 38% |
| `blind_e3` | v3 no-M | thr20 | shufA3@25 | **$129** | $143 | 28% | $412 | 31% | 0.90 | 112min | -$704 | -$321 | 33% | 33% |
| `blind_e3` | v3 no-M | thr20 | shufB1[30] | **$1** | $1 | 35% | $528 | 0% | 1.00 | 29min | -$563 | -$310 | 45% | 30% |
| `blind_e3` | v3 no-M | thr20 | shufB2[30] | **$44** | $49 | 39% | $492 | 9% | 0.90 | 41min | -$563 | -$310 | 50% | 28% |
| `blind_e3` | v3 no-M | thr20 | shufB3[30] | **$69** | $77 | 39% | $492 | 14% | 0.90 | 56min | -$563 | -$310 | 50% | 28% |
| `blind_e3` | v3 no-M | top3 | class[30] | **$43** | $23 | 39% | $915 | 5% | 1.90 | 50min | -$895 | -$340 | 47% | 37% |
| `blind_e3` | v3 no-M | top3 | class[30]+mmirror@25 | **$61** | $31 | 38% | $915 | 7% | 1.95 | 48min | -$545 | -$340 | 51% | 33% |
| `blind_e3` | v3 no-M | top3 | class[60] | **$129** | $80 | 34% | $747 | 17% | 1.60 | 70min | -$895 | -$340 | 47% | 38% |
| `blind_e3` | v3 no-M | top3 | class[60]+mmirror@25 | **$146** | $89 | 33% | $747 | 20% | 1.65 | 67min | -$545 | -$340 | 52% | 33% |
| `blind_e3` | v3 no-M | top3 | close | **$139** | $99 | 36% | $695 | 20% | 1.40 | 185min | -$895 | -$340 | 43% | 57% |
| `blind_e3` | v3 no-M | top3 | mirror@1.00 | **$63** | $22 | 38% | $1,470 | 4% | 2.90 | 14min | -$366 | -$152 | 40% | 0% |
| `blind_e3` | v3 no-M | top3 | mirror@1.00+patience15 | **$51** | $21 | 35% | $1,116 | 5% | 2.40 | 20min | -$386 | -$340 | 50% | 12% |
| `blind_e3` | v3 no-M | top3 | mmirror@10 | **$139** | $99 | 36% | $695 | 20% | 1.40 | 185min | -$895 | -$340 | 43% | 57% |
| `blind_e3` | v3 no-M | top3 | mmirror@10+patience15 | **$139** | $99 | 36% | $695 | 20% | 1.40 | 185min | -$895 | -$340 | 43% | 57% |
| `blind_e3` | v3 no-M | top3 | mmirror@10+prof | **$139** | $99 | 36% | $695 | 20% | 1.40 | 185min | -$895 | -$340 | 43% | 57% |
| `blind_e3` | v3 no-M | top3 | mmirror@20 | **$156** | $111 | 36% | $695 | 22% | 1.40 | 184min | -$587 | -$340 | 46% | 54% |
| `blind_e3` | v3 no-M | top3 | mmirror@20+patience15 | **$156** | $111 | 36% | $695 | 22% | 1.40 | 184min | -$587 | -$340 | 46% | 54% |
| `blind_e3` | v3 no-M | top3 | mmirror@20+prof | **$156** | $111 | 36% | $695 | 22% | 1.40 | 184min | -$587 | -$340 | 46% | 54% |
| `blind_e3` | v3 no-M | top3 | mmirror@25 | **$209** | $140 | 37% | $754 | 28% | 1.50 | 183min | -$587 | -$340 | 50% | 47% |
| `blind_e3` | v3 no-M | top3 | mmirror@25+patience15 | **$162** | $115 | 36% | $695 | 23% | 1.40 | 184min | -$587 | -$340 | 46% | 50% |
| `blind_e3` | v3 no-M | top3 | mmirror@25+prof | **$156** | $108 | 34% | $695 | 22% | 1.45 | 178min | -$587 | -$340 | 48% | 52% |
| `blind_e3` | v3 no-M | top3 | oracle | **$808** | $505 | 38% | $819 | 99% | 1.60 | 100min | -$176 | -$322 | 88% | 12% |
| `blind_e3` | v3 no-M | top3 | shufA1@25 | **$155** | $103 | 33% | $711 | 22% | 1.50 | 171min | -$587 | -$340 | 47% | 47% |
| `blind_e3` | v3 no-M | top3 | shufA2@25 | **$174** | $116 | 37% | $756 | 23% | 1.50 | 174min | -$720 | -$340 | 43% | 47% |
| `blind_e3` | v3 no-M | top3 | shufA3@25 | **$160** | $110 | 34% | $701 | 23% | 1.45 | 171min | -$587 | -$340 | 45% | 48% |
| `blind_e3` | v3 no-M | top3 | shufB1[30] | **-$14** | -$7 | 41% | $1,040 | -1% | 2.05 | 26min | -$538 | -$340 | 54% | 29% |
| `blind_e3` | v3 no-M | top3 | shufB2[30] | **$36** | $18 | 42% | $1,023 | 4% | 2.00 | 38min | -$538 | -$340 | 52% | 30% |
| `blind_e3` | v3 no-M | top3 | shufB3[30] | **$31** | $16 | 41% | $978 | 3% | 1.95 | 40min | -$538 | -$340 | 51% | 31% |
| `blind_e3` | v3 no-M | top5 | class[30] | **$44** | $17 | 35% | $1,145 | 4% | 2.60 | 39min | -$626 | -$321 | 52% | 27% |
| `blind_e3` | v3 no-M | top5 | class[30]+mmirror@25 | **$54** | $21 | 35% | $1,145 | 5% | 2.60 | 38min | -$563 | -$321 | 52% | 25% |
| `blind_e3` | v3 no-M | top5 | class[60] | **$59** | $29 | 34% | $873 | 7% | 2.05 | 62min | -$659 | -$321 | 44% | 32% |
| `blind_e3` | v3 no-M | top5 | class[60]+mmirror@25 | **$69** | $34 | 34% | $873 | 8% | 2.05 | 61min | -$659 | -$321 | 44% | 29% |
| `blind_e3` | v3 no-M | top5 | close | **-$15** | -$9 | 30% | $698 | -2% | 1.65 | 151min | -$901 | -$321 | 30% | 70% |
| `blind_e3` | v3 no-M | top5 | mirror@1.00 | **$6** | $1 | 34% | $2,159 | 0% | 4.75 | 13min | -$552 | -$182 | 37% | 0% |
| `blind_e3` | v3 no-M | top5 | mirror@1.00+patience15 | **$27** | $8 | 32% | $1,502 | 2% | 3.55 | 20min | -$636 | -$340 | 49% | 13% |
| `blind_e3` | v3 no-M | top5 | mmirror@10 | **$33** | $20 | 30% | $721 | 5% | 1.65 | 149min | -$878 | -$321 | 33% | 64% |
| `blind_e3` | v3 no-M | top5 | mmirror@10+patience15 | **$23** | $14 | 29% | $725 | 3% | 1.70 | 145min | -$878 | -$321 | 35% | 65% |
| `blind_e3` | v3 no-M | top5 | mmirror@10+prof | **$23** | $14 | 29% | $725 | 3% | 1.70 | 145min | -$878 | -$321 | 35% | 65% |
| `blind_e3` | v3 no-M | top5 | mmirror@20 | **$111** | $60 | 30% | $831 | 13% | 1.85 | 144min | -$831 | -$321 | 41% | 54% |
| `blind_e3` | v3 no-M | top5 | mmirror@20+patience15 | **$106** | $59 | 31% | $809 | 13% | 1.80 | 147min | -$831 | -$321 | 42% | 56% |
| `blind_e3` | v3 no-M | top5 | mmirror@20+prof | **$103** | $57 | 31% | $809 | 13% | 1.80 | 147min | -$831 | -$321 | 42% | 58% |
| `blind_e3` | v3 no-M | top5 | mmirror@25 | **$223** | $114 | 33% | $914 | 24% | 1.95 | 144min | -$831 | -$321 | 46% | 44% |
| `blind_e3` | v3 no-M | top5 | mmirror@25+patience15 | **$163** | $91 | 33% | $832 | 20% | 1.80 | 146min | -$831 | -$321 | 44% | 50% |
| `blind_e3` | v3 no-M | top5 | mmirror@25+prof | **$150** | $83 | 33% | $832 | 18% | 1.80 | 148min | -$831 | -$321 | 44% | 56% |
| `blind_e3` | v3 no-M | top5 | oracle | **$987** | $481 | 37% | $980 | 101% | 2.05 | 96min | -$300 | -$312 | 90% | 10% |
| `blind_e3` | v3 no-M | top5 | shufA1@25 | **$15** | $8 | 29% | $714 | 2% | 1.75 | 138min | -$613 | -$318 | 31% | 57% |
| `blind_e3` | v3 no-M | top5 | shufA2@25 | **$87** | $51 | 32% | $773 | 11% | 1.70 | 143min | -$749 | -$333 | 32% | 50% |
| `blind_e3` | v3 no-M | top5 | shufA3@25 | **$49** | $27 | 28% | $748 | 7% | 1.80 | 132min | -$704 | -$321 | 33% | 53% |
| `blind_e3` | v3 no-M | top5 | shufB1[30] | **$12** | $5 | 33% | $1,171 | 1% | 2.70 | 27min | -$563 | -$312 | 56% | 22% |
| `blind_e3` | v3 no-M | top5 | shufB2[30] | **$63** | $24 | 34% | $1,155 | 5% | 2.65 | 36min | -$563 | -$312 | 55% | 23% |
| `blind_e3` | v3 no-M | top5 | shufB3[30] | **$63** | $24 | 34% | $1,155 | 5% | 2.65 | 36min | -$563 | -$312 | 55% | 23% |
| `e4` | E/T/I only | thr10 | class[30] | **$27** | $668 | 100% | $36 | 75% | 0.04 | 354min | $0 | $640 | 100% | 0% |
| `e4` | E/T/I only | thr10 | class[30]+mmirror@25 | **$27** | $668 | 100% | $36 | 75% | 0.04 | 354min | $0 | $640 | 100% | 0% |
| `e4` | E/T/I only | thr10 | class[60] | **$27** | $668 | 100% | $36 | 75% | 0.04 | 354min | $0 | $640 | 100% | 0% |
| `e4` | E/T/I only | thr10 | class[60]+mmirror@25 | **$27** | $668 | 100% | $36 | 75% | 0.04 | 354min | $0 | $640 | 100% | 0% |
| `e4` | E/T/I only | thr10 | close | **$27** | $668 | 100% | $36 | 75% | 0.04 | 354min | $0 | $640 | 100% | 0% |
| `e4` | E/T/I only | thr10 | mirror@1.00 | **$15** | $377 | 100% | $36 | 42% | 0.04 | 26min | $0 | $272 | 100% | 0% |
| `e4` | E/T/I only | thr10 | mirror@1.00+patience15 | **$15** | $377 | 100% | $36 | 42% | 0.04 | 26min | $0 | $272 | 100% | 0% |
| `e4` | E/T/I only | thr10 | mmirror@10 | **$27** | $668 | 100% | $36 | 75% | 0.04 | 354min | $0 | $640 | 100% | 0% |
| `e4` | E/T/I only | thr10 | mmirror@10+patience15 | **$27** | $668 | 100% | $36 | 75% | 0.04 | 354min | $0 | $640 | 100% | 0% |
| `e4` | E/T/I only | thr10 | mmirror@10+prof | **$27** | $668 | 100% | $36 | 75% | 0.04 | 354min | $0 | $640 | 100% | 0% |
| `e4` | E/T/I only | thr10 | mmirror@20 | **$27** | $668 | 100% | $36 | 75% | 0.04 | 354min | $0 | $640 | 100% | 0% |
| `e4` | E/T/I only | thr10 | mmirror@20+patience15 | **$27** | $668 | 100% | $36 | 75% | 0.04 | 354min | $0 | $640 | 100% | 0% |
| `e4` | E/T/I only | thr10 | mmirror@20+prof | **$27** | $668 | 100% | $36 | 75% | 0.04 | 354min | $0 | $640 | 100% | 0% |
| `e4` | E/T/I only | thr10 | mmirror@25 | **$27** | $668 | 100% | $36 | 75% | 0.04 | 354min | $0 | $640 | 100% | 0% |
| `e4` | E/T/I only | thr10 | mmirror@25+patience15 | **$27** | $668 | 100% | $36 | 75% | 0.04 | 354min | $0 | $640 | 100% | 0% |
| `e4` | E/T/I only | thr10 | mmirror@25+prof | **$27** | $668 | 100% | $36 | 75% | 0.04 | 354min | $0 | $640 | 100% | 0% |
| `e4` | E/T/I only | thr10 | oracle | **$36** | $893 | 100% | $36 | 100% | 0.04 | 174min | $0 | $873 | 100% | 0% |
| `e4` | E/T/I only | thr10 | shufA1@25 | **$27** | $668 | 100% | $36 | 75% | 0.04 | 354min | $0 | $640 | 100% | 0% |
| `e4` | E/T/I only | thr10 | shufA2@25 | **$27** | $668 | 100% | $36 | 75% | 0.04 | 354min | $0 | $640 | 100% | 0% |
| `e4` | E/T/I only | thr10 | shufA3@25 | **$27** | $668 | 100% | $36 | 75% | 0.04 | 354min | $0 | $640 | 100% | 0% |
| `e4` | E/T/I only | thr10 | shufB1[30] | **$17** | $416 | 100% | $36 | 46% | 0.04 | 30min | $0 | $331 | 100% | 0% |
| `e4` | E/T/I only | thr10 | shufB2[30] | **$17** | $416 | 100% | $36 | 46% | 0.04 | 30min | $0 | $331 | 100% | 0% |
| `e4` | E/T/I only | thr10 | shufB3[30] | **$17** | $416 | 100% | $36 | 46% | 0.04 | 30min | $0 | $331 | 100% | 0% |
| `e4` | E/T/I only | thr20 | class[30] | **$84** | $145 | 48% | $341 | 25% | 0.58 | 35min | -$328 | -$330 | 55% | 31% |
| `e4` | E/T/I only | thr20 | class[30]+mmirror@25 | **$84** | $145 | 48% | $341 | 25% | 0.58 | 35min | -$328 | -$330 | 55% | 31% |
| `e4` | E/T/I only | thr20 | class[60] | **$99** | $207 | 50% | $299 | 33% | 0.48 | 56min | -$507 | -$334 | 42% | 42% |
| `e4` | E/T/I only | thr20 | class[60]+mmirror@25 | **$99** | $207 | 50% | $299 | 33% | 0.48 | 56min | -$507 | -$334 | 42% | 42% |
| `e4` | E/T/I only | thr20 | close | **$82** | $178 | 52% | $296 | 28% | 0.46 | 150min | -$653 | -$334 | 30% | 70% |
| `e4` | E/T/I only | thr20 | mirror@1.00 | **-$14** | -$20 | 50% | $415 | -3% | 0.68 | 11min | -$538 | -$328 | 21% | 6% |
| `e4` | E/T/I only | thr20 | mirror@1.00+patience15 | **$35** | $60 | 48% | $345 | 10% | 0.58 | 18min | -$549 | -$330 | 48% | 28% |
| `e4` | E/T/I only | thr20 | mmirror@10 | **$82** | $178 | 52% | $296 | 28% | 0.46 | 150min | -$653 | -$334 | 30% | 70% |
| `e4` | E/T/I only | thr20 | mmirror@10+patience15 | **$82** | $178 | 52% | $296 | 28% | 0.46 | 150min | -$653 | -$334 | 30% | 70% |
| `e4` | E/T/I only | thr20 | mmirror@10+prof | **$82** | $178 | 52% | $296 | 28% | 0.46 | 150min | -$653 | -$334 | 30% | 70% |
| `e4` | E/T/I only | thr20 | mmirror@20 | **$35** | $61 | 48% | $334 | 11% | 0.58 | 125min | -$653 | -$334 | 24% | 66% |
| `e4` | E/T/I only | thr20 | mmirror@20+patience15 | **$41** | $80 | 50% | $311 | 13% | 0.52 | 130min | -$653 | -$334 | 27% | 69% |
| `e4` | E/T/I only | thr20 | mmirror@20+prof | **$40** | $77 | 50% | $311 | 13% | 0.52 | 130min | -$653 | -$334 | 27% | 73% |
| `e4` | E/T/I only | thr20 | mmirror@25 | **$55** | $92 | 47% | $337 | 16% | 0.60 | 99min | -$653 | -$334 | 27% | 50% |
| `e4` | E/T/I only | thr20 | mmirror@25+patience15 | **$52** | $95 | 48% | $314 | 16% | 0.54 | 102min | -$653 | -$334 | 30% | 59% |
| `e4` | E/T/I only | thr20 | mmirror@25+prof | **$57** | $105 | 48% | $314 | 18% | 0.54 | 103min | -$653 | -$334 | 33% | 67% |
| `e4` | E/T/I only | thr20 | oracle | **$300** | $625 | 50% | $299 | 100% | 0.48 | 85min | $0 | $6 | 100% | 0% |
| `e4` | E/T/I only | thr20 | shufA1@25 | **$53** | $95 | 50% | $334 | 16% | 0.56 | 80min | -$334 | -$334 | 39% | 32% |
| `e4` | E/T/I only | thr20 | shufA2@25 | **$53** | $91 | 48% | $328 | 16% | 0.58 | 95min | -$653 | -$334 | 38% | 55% |
| `e4` | E/T/I only | thr20 | shufA3@25 | **$39** | $70 | 46% | $323 | 12% | 0.56 | 93min | -$803 | -$334 | 43% | 46% |
| `e4` | E/T/I only | thr20 | shufB1[30] | **$77** | $133 | 48% | $341 | 23% | 0.58 | 23min | -$328 | -$330 | 55% | 31% |
| `e4` | E/T/I only | thr20 | shufB2[30] | **$77** | $133 | 48% | $341 | 23% | 0.58 | 23min | -$328 | -$330 | 55% | 31% |
| `e4` | E/T/I only | thr20 | shufB3[30] | **$77** | $133 | 48% | $341 | 23% | 0.58 | 23min | -$328 | -$330 | 55% | 31% |
| `e4` | E/T/I only | top3 | class[30] | **$79** | $39 | 38% | $895 | 9% | 2.00 | 29min | -$940 | -$330 | 48% | 27% |
| `e4` | E/T/I only | top3 | class[30]+mmirror@25 | **$79** | $39 | 38% | $895 | 9% | 2.00 | 29min | -$940 | -$330 | 48% | 27% |
| `e4` | E/T/I only | top3 | class[60] | **$56** | $33 | 38% | $737 | 8% | 1.68 | 47min | -$940 | -$334 | 44% | 42% |
| `e4` | E/T/I only | top3 | class[60]+mmirror@25 | **$56** | $33 | 38% | $737 | 8% | 1.68 | 47min | -$940 | -$334 | 44% | 42% |
| `e4` | E/T/I only | top3 | close | **-$17** | -$12 | 42% | $689 | -2% | 1.42 | 152min | -$940 | -$346 | 31% | 68% |
| `e4` | E/T/I only | top3 | mirror@1.00 | **$94** | $32 | 38% | $1,376 | 7% | 2.98 | 21min | -$696 | -$328 | 38% | 2% |
| `e4` | E/T/I only | top3 | mirror@1.00+patience15 | **$113** | $49 | 35% | $983 | 11% | 2.28 | 27min | -$940 | -$330 | 45% | 15% |
| `e4` | E/T/I only | top3 | mmirror@10 | **-$17** | -$12 | 42% | $689 | -2% | 1.42 | 152min | -$940 | -$346 | 31% | 68% |
| `e4` | E/T/I only | top3 | mmirror@10+patience15 | **-$17** | -$12 | 42% | $689 | -2% | 1.42 | 152min | -$940 | -$346 | 31% | 68% |
| `e4` | E/T/I only | top3 | mmirror@10+prof | **-$17** | -$12 | 42% | $689 | -2% | 1.42 | 152min | -$940 | -$346 | 31% | 68% |
| `e4` | E/T/I only | top3 | mmirror@20 | **$18** | $11 | 44% | $750 | 2% | 1.56 | 146min | -$940 | -$346 | 33% | 60% |
| `e4` | E/T/I only | top3 | mmirror@20+patience15 | **$3** | $2 | 43% | $699 | 0% | 1.48 | 145min | -$940 | -$346 | 34% | 62% |
| `e4` | E/T/I only | top3 | mmirror@20+prof | **-$7** | -$4 | 43% | $699 | -1% | 1.48 | 147min | -$940 | -$346 | 34% | 65% |
| `e4` | E/T/I only | top3 | mmirror@25 | **$57** | $35 | 45% | $820 | 7% | 1.66 | 134min | -$790 | -$346 | 36% | 52% |
| `e4` | E/T/I only | top3 | mmirror@25+patience15 | **$45** | $29 | 45% | $772 | 6% | 1.56 | 137min | -$940 | -$346 | 37% | 55% |
| `e4` | E/T/I only | top3 | mmirror@25+prof | **$27** | $17 | 44% | $769 | 4% | 1.58 | 135min | -$940 | -$346 | 38% | 61% |
| `e4` | E/T/I only | top3 | oracle | **$1,010** | $537 | 48% | $1,006 | 100% | 1.88 | 91min | -$196 | -$329 | 96% | 4% |
| `e4` | E/T/I only | top3 | shufA1@25 | **-$15** | -$10 | 40% | $699 | -2% | 1.54 | 126min | -$663 | -$346 | 32% | 55% |
| `e4` | E/T/I only | top3 | shufA2@25 | **$13** | $8 | 42% | $698 | 2% | 1.52 | 132min | -$940 | -$346 | 38% | 58% |
| `e4` | E/T/I only | top3 | shufA3@25 | **$10** | $7 | 43% | $734 | 1% | 1.52 | 133min | -$940 | -$346 | 36% | 55% |
| `e4` | E/T/I only | top3 | shufB1[30] | **$71** | $36 | 38% | $895 | 8% | 2.00 | 25min | -$940 | -$330 | 48% | 27% |
| `e4` | E/T/I only | top3 | shufB2[30] | **$71** | $36 | 38% | $895 | 8% | 2.00 | 25min | -$940 | -$330 | 48% | 27% |
| `e4` | E/T/I only | top3 | shufB3[30] | **$71** | $36 | 38% | $895 | 8% | 2.00 | 25min | -$940 | -$330 | 48% | 27% |
| `e4` | E/T/I only | top5 | class[30] | **$13** | $5 | 31% | $1,191 | 1% | 2.74 | 28min | -$931 | -$328 | 47% | 28% |
| `e4` | E/T/I only | top5 | class[30]+mmirror@25 | **$13** | $5 | 31% | $1,191 | 1% | 2.74 | 28min | -$931 | -$328 | 47% | 28% |
| `e4` | E/T/I only | top5 | class[60] | **$20** | $9 | 29% | $913 | 2% | 2.26 | 46min | -$931 | -$334 | 39% | 44% |
| `e4` | E/T/I only | top5 | class[60]+mmirror@25 | **$20** | $9 | 29% | $913 | 2% | 2.26 | 46min | -$931 | -$334 | 39% | 44% |
| `e4` | E/T/I only | top5 | close | **$23** | $14 | 38% | $817 | 3% | 1.68 | 148min | -$931 | -$334 | 31% | 67% |
| `e4` | E/T/I only | top5 | mirror@1.00 | **$23** | $5 | 33% | $2,064 | 1% | 4.80 | 21min | -$1,080 | -$328 | 35% | 1% |
| `e4` | E/T/I only | top5 | mirror@1.00+patience15 | **$63** | $19 | 28% | $1,360 | 5% | 3.38 | 27min | -$783 | -$328 | 40% | 13% |
| `e4` | E/T/I only | top5 | mmirror@10 | **$46** | $27 | 39% | $830 | 5% | 1.68 | 150min | -$931 | -$334 | 32% | 64% |
| `e4` | E/T/I only | top5 | mmirror@10+patience15 | **$23** | $14 | 38% | $817 | 3% | 1.68 | 148min | -$931 | -$334 | 31% | 67% |
| `e4` | E/T/I only | top5 | mmirror@10+prof | **$23** | $14 | 38% | $817 | 3% | 1.68 | 148min | -$931 | -$334 | 31% | 67% |
| `e4` | E/T/I only | top5 | mmirror@20 | **-$13** | -$7 | 39% | $930 | -1% | 1.96 | 132min | -$969 | -$334 | 32% | 58% |
| `e4` | E/T/I only | top5 | mmirror@20+patience15 | **-$12** | -$6 | 38% | $895 | -1% | 1.90 | 131min | -$931 | -$334 | 34% | 61% |
| `e4` | E/T/I only | top5 | mmirror@20+prof | **$37** | $21 | 40% | $878 | 4% | 1.82 | 143min | -$931 | -$334 | 36% | 62% |
| `e4` | E/T/I only | top5 | mmirror@25 | **$15** | $7 | 38% | $1,040 | 1% | 2.22 | 115min | -$1,037 | -$334 | 33% | 49% |
| `e4` | E/T/I only | top5 | mmirror@25+patience15 | **$32** | $16 | 38% | $960 | 3% | 2.00 | 124min | -$931 | -$334 | 36% | 53% |
| `e4` | E/T/I only | top5 | mmirror@25+prof | **$36** | $18 | 40% | $939 | 4% | 1.94 | 133min | -$931 | -$334 | 39% | 59% |
| `e4` | E/T/I only | top5 | oracle | **$1,242** | $570 | 44% | $1,218 | 102% | 2.18 | 92min | -$196 | -$304 | 98% | 2% |
| `e4` | E/T/I only | top5 | shufA1@25 | **-$3** | -$2 | 37% | $907 | -0% | 2.02 | 116min | -$950 | -$334 | 35% | 51% |
| `e4` | E/T/I only | top5 | shufA2@25 | **$5** | $3 | 40% | $890 | 1% | 1.86 | 124min | -$931 | -$334 | 38% | 55% |
| `e4` | E/T/I only | top5 | shufA3@25 | **$32** | $16 | 37% | $935 | 3% | 1.98 | 121min | -$1,016 | -$334 | 37% | 51% |
| `e4` | E/T/I only | top5 | shufB1[30] | **$5** | $2 | 31% | $1,191 | 0% | 2.74 | 26min | -$931 | -$328 | 47% | 28% |
| `e4` | E/T/I only | top5 | shufB2[30] | **$5** | $2 | 31% | $1,191 | 0% | 2.74 | 26min | -$931 | -$328 | 47% | 28% |
| `e4` | E/T/I only | top5 | shufB3[30] | **$5** | $2 | 31% | $1,191 | 0% | 2.74 | 26min | -$931 | -$328 | 47% | 28% |
| `e4` | v3 no-M | thr10 | class[30] | **-$38** | -$272 | 29% | $57 | -67% | 0.14 | 156min | -$324 | -$324 | 0% | 86% |
| `e4` | v3 no-M | thr10 | class[30]+mmirror@25 | **-$32** | -$231 | 29% | $57 | -57% | 0.14 | 145min | -$324 | -$324 | 0% | 71% |
| `e4` | v3 no-M | thr10 | class[60] | **-$38** | -$272 | 29% | $57 | -67% | 0.14 | 156min | -$324 | -$324 | 0% | 86% |
| `e4` | v3 no-M | thr10 | class[60]+mmirror@25 | **-$32** | -$231 | 29% | $57 | -57% | 0.14 | 145min | -$324 | -$324 | 0% | 71% |
| `e4` | v3 no-M | thr10 | close | **-$38** | -$272 | 29% | $57 | -67% | 0.14 | 156min | -$324 | -$324 | 0% | 86% |
| `e4` | v3 no-M | thr10 | mirror@1.00 | **-$2** | -$14 | 33% | $76 | -3% | 0.18 | 15min | -$198 | -$198 | 33% | 0% |
| `e4` | v3 no-M | thr10 | mirror@1.00+patience15 | **$0** | $0 | 25% | $63 | 0% | 0.16 | 18min | -$194 | -$194 | 38% | 0% |
| `e4` | v3 no-M | thr10 | mmirror@10 | **-$38** | -$272 | 29% | $57 | -67% | 0.14 | 156min | -$324 | -$324 | 0% | 86% |
| `e4` | v3 no-M | thr10 | mmirror@10+patience15 | **-$38** | -$272 | 29% | $57 | -67% | 0.14 | 156min | -$324 | -$324 | 0% | 86% |
| `e4` | v3 no-M | thr10 | mmirror@10+prof | **-$38** | -$272 | 29% | $57 | -67% | 0.14 | 156min | -$324 | -$324 | 0% | 86% |
| `e4` | v3 no-M | thr10 | mmirror@20 | **-$38** | -$272 | 29% | $57 | -67% | 0.14 | 156min | -$324 | -$324 | 0% | 86% |
| `e4` | v3 no-M | thr10 | mmirror@20+patience15 | **-$38** | -$272 | 29% | $57 | -67% | 0.14 | 156min | -$324 | -$324 | 0% | 86% |
| `e4` | v3 no-M | thr10 | mmirror@20+prof | **-$38** | -$272 | 29% | $57 | -67% | 0.14 | 156min | -$324 | -$324 | 0% | 86% |
| `e4` | v3 no-M | thr10 | mmirror@25 | **-$32** | -$231 | 29% | $57 | -57% | 0.14 | 145min | -$324 | -$324 | 0% | 71% |
| `e4` | v3 no-M | thr10 | mmirror@25+patience15 | **-$32** | -$231 | 29% | $57 | -57% | 0.14 | 145min | -$324 | -$324 | 0% | 71% |
| `e4` | v3 no-M | thr10 | mmirror@25+prof | **-$38** | -$272 | 29% | $57 | -67% | 0.14 | 156min | -$324 | -$324 | 0% | 86% |
| `e4` | v3 no-M | thr10 | oracle | **$63** | $397 | 25% | $63 | 101% | 0.16 | 41min | $0 | $122 | 100% | 0% |
| `e4` | v3 no-M | thr10 | shufA1@25 | **-$38** | -$272 | 29% | $57 | -67% | 0.14 | 156min | -$324 | -$324 | 0% | 86% |
| `e4` | v3 no-M | thr10 | shufA2@25 | **-$38** | -$272 | 29% | $57 | -67% | 0.14 | 156min | -$324 | -$324 | 0% | 86% |
| `e4` | v3 no-M | thr10 | shufA3@25 | **-$38** | -$272 | 29% | $57 | -67% | 0.14 | 156min | -$324 | -$324 | 0% | 86% |
| `e4` | v3 no-M | thr10 | shufB1[30] | **-$2** | -$10 | 25% | $63 | -3% | 0.16 | 41min | -$324 | -$324 | 38% | 38% |
| `e4` | v3 no-M | thr10 | shufB2[30] | **-$7** | -$45 | 25% | $63 | -12% | 0.16 | 97min | -$324 | -$324 | 38% | 38% |
| `e4` | v3 no-M | thr10 | shufB3[30] | **-$2** | -$10 | 25% | $63 | -3% | 0.16 | 41min | -$324 | -$324 | 38% | 38% |
| `e4` | v3 no-M | thr20 | class[30] | **-$28** | -$45 | 23% | $262 | -11% | 0.62 | 50min | -$1,456 | -$324 | 32% | 48% |
| `e4` | v3 no-M | thr20 | class[30]+mmirror@25 | **-$28** | -$45 | 23% | $262 | -11% | 0.62 | 50min | -$1,456 | -$324 | 32% | 48% |
| `e4` | v3 no-M | thr20 | class[60] | **-$27** | -$47 | 24% | $254 | -11% | 0.58 | 63min | -$1,559 | -$334 | 28% | 62% |
| `e4` | v3 no-M | thr20 | class[60]+mmirror@25 | **-$27** | -$47 | 24% | $254 | -11% | 0.58 | 63min | -$1,559 | -$334 | 28% | 62% |
| `e4` | v3 no-M | thr20 | close | **-$37** | -$68 | 22% | $228 | -16% | 0.54 | 118min | -$1,559 | -$334 | 11% | 81% |
| `e4` | v3 no-M | thr20 | mirror@1.00 | **-$58** | -$63 | 22% | $361 | -16% | 0.92 | 12min | -$792 | -$221 | 17% | 0% |
| `e4` | v3 no-M | thr20 | mirror@1.00+patience15 | **-$27** | -$39 | 21% | $276 | -10% | 0.68 | 20min | -$847 | -$312 | 41% | 21% |
| `e4` | v3 no-M | thr20 | mmirror@10 | **-$28** | -$53 | 23% | $238 | -12% | 0.52 | 124min | -$1,559 | -$334 | 12% | 77% |
| `e4` | v3 no-M | thr20 | mmirror@10+patience15 | **-$37** | -$68 | 22% | $228 | -16% | 0.54 | 118min | -$1,559 | -$334 | 11% | 81% |
| `e4` | v3 no-M | thr20 | mmirror@10+prof | **-$37** | -$68 | 22% | $228 | -16% | 0.54 | 118min | -$1,559 | -$334 | 11% | 81% |
| `e4` | v3 no-M | thr20 | mmirror@20 | **-$47** | -$71 | 21% | $274 | -17% | 0.66 | 97min | -$1,559 | -$334 | 9% | 61% |
| `e4` | v3 no-M | thr20 | mmirror@20+patience15 | **-$27** | -$49 | 21% | $229 | -12% | 0.56 | 113min | -$1,559 | -$334 | 14% | 75% |
| `e4` | v3 no-M | thr20 | mmirror@20+prof | **-$37** | -$68 | 22% | $228 | -16% | 0.54 | 118min | -$1,559 | -$334 | 11% | 81% |
| `e4` | v3 no-M | thr20 | mmirror@25 | **-$68** | -$98 | 20% | $269 | -25% | 0.70 | 88min | -$1,559 | -$334 | 9% | 54% |
| `e4` | v3 no-M | thr20 | mmirror@25+patience15 | **-$48** | -$86 | 21% | $229 | -21% | 0.56 | 110min | -$1,559 | -$334 | 14% | 75% |
| `e4` | v3 no-M | thr20 | mmirror@25+prof | **-$57** | -$106 | 22% | $228 | -25% | 0.54 | 115min | -$1,559 | -$334 | 11% | 81% |
| `e4` | v3 no-M | thr20 | oracle | **$248** | $399 | 19% | $245 | 101% | 0.62 | 53min | $0 | -$304 | 94% | 6% |
| `e4` | v3 no-M | thr20 | shufA1@25 | **-$64** | -$102 | 23% | $254 | -25% | 0.62 | 100min | -$1,299 | -$334 | 10% | 68% |
| `e4` | v3 no-M | thr20 | shufA2@25 | **-$48** | -$83 | 21% | $234 | -21% | 0.58 | 108min | -$1,559 | -$334 | 10% | 69% |
| `e4` | v3 no-M | thr20 | shufA3@25 | **-$30** | -$53 | 25% | $260 | -11% | 0.56 | 110min | -$1,462 | -$334 | 14% | 61% |
| `e4` | v3 no-M | thr20 | shufB1[30] | **$2** | $2 | 22% | $268 | 1% | 0.64 | 27min | -$1,456 | -$324 | 38% | 41% |
| `e4` | v3 no-M | thr20 | shufB2[30] | **-$4** | -$6 | 22% | $268 | -2% | 0.64 | 41min | -$1,456 | -$324 | 38% | 41% |
| `e4` | v3 no-M | thr20 | shufB3[30] | **$2** | $2 | 22% | $268 | 1% | 0.64 | 27min | -$1,456 | -$324 | 38% | 41% |
| `e4` | v3 no-M | top3 | class[30] | **-$34** | -$17 | 31% | $787 | -4% | 2.00 | 30min | -$931 | -$328 | 42% | 37% |
| `e4` | v3 no-M | top3 | class[30]+mmirror@25 | **-$34** | -$17 | 31% | $787 | -4% | 2.00 | 30min | -$931 | -$328 | 42% | 37% |
| `e4` | v3 no-M | top3 | class[60] | **-$54** | -$31 | 31% | $701 | -8% | 1.76 | 46min | -$937 | -$334 | 35% | 53% |
| `e4` | v3 no-M | top3 | class[60]+mmirror@25 | **-$54** | -$31 | 31% | $701 | -8% | 1.76 | 46min | -$937 | -$334 | 35% | 53% |
| `e4` | v3 no-M | top3 | close | **-$90** | -$60 | 32% | $608 | -15% | 1.50 | 120min | -$937 | -$334 | 21% | 77% |
| `e4` | v3 no-M | top3 | mirror@1.00 | **$62** | $21 | 35% | $1,269 | 5% | 3.00 | 20min | -$689 | -$328 | 37% | 1% |
| `e4` | v3 no-M | top3 | mirror@1.00+patience15 | **$15** | $6 | 32% | $953 | 2% | 2.34 | 25min | -$724 | -$328 | 41% | 20% |
| `e4` | v3 no-M | top3 | mmirror@10 | **-$87** | -$58 | 32% | $612 | -14% | 1.50 | 121min | -$937 | -$334 | 21% | 76% |
| `e4` | v3 no-M | top3 | mmirror@10+patience15 | **-$90** | -$60 | 32% | $608 | -15% | 1.50 | 120min | -$937 | -$334 | 21% | 77% |
| `e4` | v3 no-M | top3 | mmirror@10+prof | **-$90** | -$60 | 32% | $608 | -15% | 1.50 | 120min | -$937 | -$334 | 21% | 77% |
| `e4` | v3 no-M | top3 | mmirror@20 | **-$99** | -$63 | 30% | $623 | -16% | 1.58 | 115min | -$937 | -$334 | 20% | 72% |
| `e4` | v3 no-M | top3 | mmirror@20+patience15 | **-$81** | -$53 | 32% | $609 | -13% | 1.52 | 119min | -$937 | -$334 | 22% | 75% |
| `e4` | v3 no-M | top3 | mmirror@20+prof | **-$90** | -$60 | 32% | $608 | -15% | 1.50 | 120min | -$937 | -$334 | 21% | 77% |
| `e4` | v3 no-M | top3 | mmirror@25 | **-$47** | -$28 | 32% | $724 | -6% | 1.68 | 118min | -$937 | -$334 | 25% | 62% |
| `e4` | v3 no-M | top3 | mmirror@25+patience15 | **-$64** | -$41 | 33% | $650 | -10% | 1.56 | 120min | -$937 | -$334 | 24% | 69% |
| `e4` | v3 no-M | top3 | mmirror@25+prof | **-$66** | -$43 | 33% | $662 | -10% | 1.52 | 124min | -$937 | -$334 | 26% | 72% |
| `e4` | v3 no-M | top3 | oracle | **$882** | $469 | 36% | $864 | 102% | 1.88 | 76min | -$196 | -$304 | 97% | 3% |
| `e4` | v3 no-M | top3 | shufA1@25 | **-$119** | -$75 | 32% | $627 | -19% | 1.58 | 113min | -$931 | -$334 | 20% | 72% |
| `e4` | v3 no-M | top3 | shufA2@25 | **-$93** | -$61 | 31% | $631 | -15% | 1.54 | 118min | -$937 | -$334 | 22% | 71% |
| `e4` | v3 no-M | top3 | shufA3@25 | **-$107** | -$68 | 30% | $638 | -17% | 1.58 | 114min | -$931 | -$334 | 22% | 68% |
| `e4` | v3 no-M | top3 | shufB1[30] | **-$4** | -$2 | 31% | $793 | -0% | 2.02 | 26min | -$931 | -$328 | 44% | 35% |
| `e4` | v3 no-M | top3 | shufB2[30] | **-$10** | -$5 | 31% | $793 | -1% | 2.02 | 27min | -$931 | -$328 | 44% | 35% |
| `e4` | v3 no-M | top3 | shufB3[30] | **-$4** | -$2 | 31% | $793 | -0% | 2.02 | 26min | -$931 | -$328 | 44% | 35% |
| `e4` | v3 no-M | top5 | class[30] | **-$77** | -$27 | 27% | $1,028 | -8% | 2.90 | 30min | -$1,456 | -$330 | 42% | 35% |
| `e4` | v3 no-M | top5 | class[30]+mmirror@25 | **-$77** | -$27 | 27% | $1,028 | -8% | 2.90 | 30min | -$1,456 | -$330 | 42% | 35% |
| `e4` | v3 no-M | top5 | class[60] | **-$83** | -$35 | 27% | $841 | -10% | 2.36 | 48min | -$1,559 | -$334 | 36% | 48% |
| `e4` | v3 no-M | top5 | class[60]+mmirror@25 | **-$83** | -$35 | 27% | $841 | -10% | 2.36 | 48min | -$1,559 | -$334 | 36% | 48% |
| `e4` | v3 no-M | top5 | close | **-$98** | -$53 | 30% | $713 | -14% | 1.84 | 128min | -$1,559 | -$334 | 23% | 74% |
| `e4` | v3 no-M | top5 | mirror@1.00 | **$52** | $11 | 33% | $2,052 | 3% | 4.90 | 21min | -$910 | -$328 | 35% | 0% |
| `e4` | v3 no-M | top5 | mirror@1.00+patience15 | **-$34** | -$10 | 26% | $1,264 | -3% | 3.48 | 27min | -$847 | -$330 | 36% | 20% |
| `e4` | v3 no-M | top5 | mmirror@10 | **-$111** | -$61 | 29% | $705 | -16% | 1.84 | 126min | -$1,559 | -$334 | 22% | 74% |
| `e4` | v3 no-M | top5 | mmirror@10+patience15 | **-$98** | -$53 | 30% | $713 | -14% | 1.84 | 128min | -$1,559 | -$334 | 23% | 74% |
| `e4` | v3 no-M | top5 | mmirror@10+prof | **-$98** | -$53 | 30% | $713 | -14% | 1.84 | 128min | -$1,559 | -$334 | 23% | 74% |
| `e4` | v3 no-M | top5 | mmirror@20 | **-$131** | -$66 | 28% | $741 | -18% | 1.98 | 117min | -$1,559 | -$334 | 20% | 69% |
| `e4` | v3 no-M | top5 | mmirror@20+patience15 | **-$106** | -$57 | 30% | $716 | -15% | 1.88 | 123min | -$1,559 | -$334 | 22% | 72% |
| `e4` | v3 no-M | top5 | mmirror@20+prof | **-$98** | -$53 | 30% | $713 | -14% | 1.84 | 128min | -$1,559 | -$334 | 23% | 74% |
| `e4` | v3 no-M | top5 | mmirror@25 | **-$69** | -$33 | 29% | $833 | -8% | 2.12 | 116min | -$1,559 | -$334 | 25% | 59% |
| `e4` | v3 no-M | top5 | mmirror@25+patience15 | **-$90** | -$47 | 31% | $756 | -12% | 1.92 | 124min | -$1,559 | -$334 | 24% | 68% |
| `e4` | v3 no-M | top5 | mmirror@25+prof | **-$84** | -$44 | 29% | $754 | -11% | 1.90 | 126min | -$1,559 | -$334 | 26% | 71% |
| `e4` | v3 no-M | top5 | oracle | **$1,145** | $507 | 39% | $1,075 | 106% | 2.26 | 89min | -$196 | -$304 | 98% | 2% |
| `e4` | v3 no-M | top5 | shufA1@25 | **-$129** | -$65 | 29% | $744 | -17% | 1.98 | 115min | -$1,299 | -$334 | 22% | 67% |
| `e4` | v3 no-M | top5 | shufA2@25 | **-$75** | -$39 | 29% | $756 | -10% | 1.92 | 120min | -$1,559 | -$334 | 26% | 66% |
| `e4` | v3 no-M | top5 | shufA3@25 | **-$79** | -$41 | 28% | $747 | -11% | 1.92 | 119min | -$1,462 | -$334 | 25% | 64% |
| `e4` | v3 no-M | top5 | shufB1[30] | **-$39** | -$13 | 27% | $1,048 | -4% | 2.94 | 25min | -$1,456 | -$330 | 44% | 33% |
| `e4` | v3 no-M | top5 | shufB2[30] | **-$51** | -$17 | 27% | $1,041 | -5% | 2.94 | 28min | -$1,456 | -$330 | 44% | 33% |
| `e4` | v3 no-M | top5 | shufB3[30] | **-$39** | -$13 | 27% | $1,048 | -4% | 2.94 | 25min | -$1,456 | -$330 | 44% | 33% |
| `e5` | E/T/I only | thr10 | class[30] | **$19** | $31 | 38% | $315 | 6% | 0.61 | 149min | -$630 | -$334 | 30% | 66% |
| `e5` | E/T/I only | thr10 | class[30]+mmirror@25 | **$9** | $9 | 33% | $538 | 2% | 1.07 | 52min | -$1,011 | -$334 | 34% | 28% |
| `e5` | E/T/I only | thr10 | class[60] | **$19** | $31 | 38% | $315 | 6% | 0.61 | 149min | -$630 | -$334 | 30% | 66% |
| `e5` | E/T/I only | thr10 | class[60]+mmirror@25 | **$9** | $9 | 33% | $538 | 2% | 1.07 | 52min | -$1,011 | -$334 | 34% | 28% |
| `e5` | E/T/I only | thr10 | close | **$19** | $31 | 38% | $315 | 6% | 0.61 | 149min | -$630 | -$334 | 30% | 66% |
| `e5` | E/T/I only | thr10 | mirror@1.00 | **$22** | $19 | 35% | $576 | 4% | 1.13 | 11min | -$559 | -$298 | 38% | 1% |
| `e5` | E/T/I only | thr10 | mirror@1.00+patience15 | **$14** | $15 | 33% | $452 | 3% | 0.92 | 17min | -$606 | -$334 | 48% | 27% |
| `e5` | E/T/I only | thr10 | mmirror@10 | **$20** | $21 | 34% | $463 | 4% | 0.94 | 89min | -$1,236 | -$334 | 32% | 50% |
| `e5` | E/T/I only | thr10 | mmirror@10+patience15 | **-$4** | -$5 | 33% | $410 | -1% | 0.83 | 92min | -$723 | -$334 | 33% | 57% |
| `e5` | E/T/I only | thr10 | mmirror@10+prof | **$73** | $94 | 39% | $432 | 17% | 0.78 | 110min | -$723 | -$334 | 41% | 57% |
| `e5` | E/T/I only | thr10 | mmirror@20 | **$5** | $5 | 34% | $527 | 1% | 1.04 | 61min | -$1,136 | -$334 | 31% | 36% |
| `e5` | E/T/I only | thr10 | mmirror@20+patience15 | **-$17** | -$19 | 32% | $426 | -4% | 0.87 | 67min | -$740 | -$334 | 35% | 48% |
| `e5` | E/T/I only | thr10 | mmirror@20+prof | **$68** | $84 | 39% | $457 | 15% | 0.81 | 95min | -$723 | -$334 | 46% | 52% |
| `e5` | E/T/I only | thr10 | mmirror@25 | **$9** | $9 | 33% | $538 | 2% | 1.07 | 52min | -$1,011 | -$334 | 34% | 28% |
| `e5` | E/T/I only | thr10 | mmirror@25+patience15 | **-$11** | -$13 | 32% | $435 | -3% | 0.89 | 58min | -$740 | -$334 | 40% | 43% |
| `e5` | E/T/I only | thr10 | mmirror@25+prof | **$71** | $85 | 38% | $459 | 15% | 0.83 | 87min | -$630 | -$334 | 50% | 49% |
| `e5` | E/T/I only | thr10 | oracle | **$405** | $554 | 38% | $401 | 101% | 0.73 | 85min | -$313 | -$334 | 93% | 7% |
| `e5` | E/T/I only | thr10 | shufA1@25 | **$16** | $18 | 34% | $436 | 4% | 0.87 | 58min | -$595 | -$334 | 35% | 31% |
| `e5` | E/T/I only | thr10 | shufA2@25 | **$11** | $13 | 36% | $474 | 2% | 0.87 | 59min | -$631 | -$334 | 39% | 37% |
| `e5` | E/T/I only | thr10 | shufA3@25 | **$24** | $29 | 36% | $439 | 5% | 0.83 | 57min | -$683 | -$334 | 38% | 37% |
| `e5` | E/T/I only | thr10 | shufB1[30] | **$45** | $61 | 35% | $384 | 12% | 0.74 | 43min | -$665 | -$334 | 46% | 33% |
| `e5` | E/T/I only | thr10 | shufB2[30] | **$10** | $13 | 34% | $369 | 3% | 0.74 | 32min | -$606 | -$334 | 45% | 38% |
| `e5` | E/T/I only | thr10 | shufB3[30] | **$17** | $23 | 35% | $382 | 5% | 0.74 | 45min | -$917 | -$407 | 47% | 37% |
| `e5` | E/T/I only | thr20 | class[30] | **$7** | $6 | 35% | $575 | 1% | 1.12 | 80min | -$1,288 | -$346 | 40% | 48% |
| `e5` | E/T/I only | thr20 | class[30]+mmirror@25 | **$1** | $0 | 34% | $740 | 0% | 1.55 | 43min | -$1,288 | -$357 | 41% | 34% |
| `e5` | E/T/I only | thr20 | class[60] | **-$26** | -$25 | 35% | $511 | -5% | 1.03 | 82min | -$1,288 | -$346 | 38% | 57% |
| `e5` | E/T/I only | thr20 | class[60]+mmirror@25 | **-$33** | -$24 | 34% | $656 | -5% | 1.39 | 47min | -$1,288 | -$357 | 37% | 41% |
| `e5` | E/T/I only | thr20 | close | **$61** | $65 | 35% | $454 | 14% | 0.94 | 148min | -$1,288 | -$357 | 32% | 66% |
| `e5` | E/T/I only | thr20 | mirror@1.00 | **-$8** | -$4 | 35% | $1,150 | -1% | 2.37 | 12min | -$974 | -$318 | 35% | 1% |
| `e5` | E/T/I only | thr20 | mirror@1.00+patience15 | **-$22** | -$14 | 31% | $731 | -3% | 1.60 | 18min | -$1,288 | -$357 | 42% | 27% |
| `e5` | E/T/I only | thr20 | mmirror@10 | **$25** | $18 | 35% | $667 | 4% | 1.39 | 92min | -$1,724 | -$357 | 33% | 47% |
| `e5` | E/T/I only | thr20 | mmirror@10+patience15 | **$8** | $6 | 34% | $593 | 1% | 1.25 | 96min | -$1,288 | -$357 | 33% | 55% |
| `e5` | E/T/I only | thr20 | mmirror@10+prof | **$72** | $62 | 37% | $580 | 12% | 1.15 | 115min | -$1,288 | -$357 | 41% | 58% |
| `e5` | E/T/I only | thr20 | mmirror@20 | **$11** | $5 | 34% | $1,032 | 1% | 2.10 | 60min | -$1,613 | -$357 | 33% | 33% |
| `e5` | E/T/I only | thr20 | mmirror@20+patience15 | **-$13** | -$9 | 32% | $699 | -2% | 1.50 | 71min | -$1,288 | -$357 | 34% | 48% |
| `e5` | E/T/I only | thr20 | mmirror@20+prof | **$78** | $54 | 38% | $786 | 10% | 1.46 | 89min | -$1,288 | -$357 | 49% | 49% |
| `e5` | E/T/I only | thr20 | mmirror@25 | **$23** | $10 | 35% | $1,097 | 2% | 2.24 | 52min | -$1,487 | -$357 | 35% | 27% |
| `e5` | E/T/I only | thr20 | mmirror@25+patience15 | **-$3** | -$2 | 32% | $707 | -0% | 1.52 | 66min | -$1,288 | -$357 | 36% | 45% |
| `e5` | E/T/I only | thr20 | mmirror@25+prof | **$88** | $58 | 37% | $805 | 11% | 1.52 | 83min | -$1,288 | -$357 | 51% | 48% |
| `e5` | E/T/I only | thr20 | oracle | **$643** | $591 | 42% | $629 | 102% | 1.09 | 98min | -$313 | -$325 | 94% | 6% |
| `e5` | E/T/I only | thr20 | shufA1@25 | **$36** | $25 | 34% | $669 | 5% | 1.44 | 66min | -$1,149 | -$357 | 41% | 34% |
| `e5` | E/T/I only | thr20 | shufA2@25 | **-$19** | -$13 | 32% | $645 | -3% | 1.44 | 59min | -$1,288 | -$346 | 38% | 40% |
| `e5` | E/T/I only | thr20 | shufA3@25 | **$2** | $2 | 33% | $691 | 0% | 1.44 | 58min | -$1,288 | -$346 | 38% | 37% |
| `e5` | E/T/I only | thr20 | shufB1[30] | **$30** | $24 | 33% | $618 | 5% | 1.29 | 40min | -$1,288 | -$357 | 44% | 36% |
| `e5` | E/T/I only | thr20 | shufB2[30] | **$13** | $10 | 35% | $628 | 2% | 1.26 | 36min | -$1,288 | -$346 | 45% | 38% |
| `e5` | E/T/I only | thr20 | shufB3[30] | **$7** | $5 | 34% | $622 | 1% | 1.30 | 39min | -$1,288 | -$407 | 46% | 37% |
| `e5` | E/T/I only | top3 | class[30] | **$31** | $18 | 33% | $759 | 4% | 1.73 | 60min | -$630 | -$334 | 45% | 33% |
| `e5` | E/T/I only | top3 | class[30]+mmirror@25 | **-$6** | -$3 | 31% | $881 | -1% | 2.05 | 37min | -$683 | -$334 | 45% | 24% |
| `e5` | E/T/I only | top3 | class[60] | **$5** | $3 | 33% | $691 | 1% | 1.56 | 74min | -$686 | -$334 | 43% | 43% |
| `e5` | E/T/I only | top3 | class[60]+mmirror@25 | **-$51** | -$27 | 31% | $804 | -6% | 1.87 | 48min | -$710 | -$334 | 40% | 33% |
| `e5` | E/T/I only | top3 | close | **$67** | $48 | 34% | $632 | 11% | 1.39 | 173min | -$912 | -$334 | 35% | 59% |
| `e5` | E/T/I only | top3 | mirror@1.00 | **-$12** | -$4 | 30% | $1,184 | -1% | 2.96 | 19min | -$541 | -$298 | 38% | 0% |
| `e5` | E/T/I only | top3 | mirror@1.00+patience15 | **-$16** | -$7 | 30% | $902 | -2% | 2.24 | 24min | -$601 | -$334 | 46% | 16% |
| `e5` | E/T/I only | top3 | mmirror@10 | **$11** | $7 | 32% | $717 | 2% | 1.64 | 137min | -$912 | -$334 | 34% | 52% |
| `e5` | E/T/I only | top3 | mmirror@10+patience15 | **$12** | $7 | 33% | $708 | 2% | 1.60 | 140min | -$912 | -$334 | 35% | 54% |
| `e5` | E/T/I only | top3 | mmirror@10+prof | **$59** | $39 | 35% | $703 | 8% | 1.51 | 153min | -$912 | -$334 | 39% | 56% |
| `e5` | E/T/I only | top3 | mmirror@20 | **-$19** | -$10 | 32% | $815 | -2% | 1.89 | 113min | -$912 | -$334 | 33% | 43% |
| `e5` | E/T/I only | top3 | mmirror@20+patience15 | **-$20** | -$11 | 32% | $744 | -3% | 1.72 | 120min | -$912 | -$334 | 35% | 49% |
| `e5` | E/T/I only | top3 | mmirror@20+prof | **$47** | $30 | 35% | $728 | 6% | 1.58 | 143min | -$912 | -$334 | 42% | 54% |
| `e5` | E/T/I only | top3 | mmirror@25 | **-$12** | -$6 | 32% | $874 | -1% | 1.99 | 105min | -$912 | -$334 | 35% | 39% |
| `e5` | E/T/I only | top3 | mmirror@25+patience15 | **-$17** | -$10 | 32% | $758 | -2% | 1.76 | 112min | -$912 | -$334 | 37% | 46% |
| `e5` | E/T/I only | top3 | mmirror@25+prof | **$71** | $44 | 35% | $746 | 10% | 1.62 | 140min | -$912 | -$334 | 45% | 51% |
| `e5` | E/T/I only | top3 | oracle | **$827** | $480 | 38% | $809 | 102% | 1.72 | 99min | -$246 | -$334 | 96% | 4% |
| `e5` | E/T/I only | top3 | shufA1@25 | **-$4** | -$2 | 31% | $692 | -1% | 1.66 | 117min | -$912 | -$334 | 37% | 43% |
| `e5` | E/T/I only | top3 | shufA2@25 | **-$41** | -$24 | 32% | $725 | -6% | 1.71 | 108min | -$912 | -$334 | 37% | 47% |
| `e5` | E/T/I only | top3 | shufA3@25 | **$22** | $14 | 34% | $745 | 3% | 1.61 | 117min | -$912 | -$334 | 38% | 44% |
| `e5` | E/T/I only | top3 | shufB1[30] | **$50** | $27 | 30% | $778 | 6% | 1.87 | 39min | -$615 | -$334 | 48% | 27% |
| `e5` | E/T/I only | top3 | shufB2[30] | **$24** | $13 | 31% | $813 | 3% | 1.90 | 31min | -$615 | -$334 | 49% | 28% |
| `e5` | E/T/I only | top3 | shufB3[30] | **$23** | $13 | 31% | $779 | 3% | 1.83 | 39min | -$630 | -$334 | 48% | 28% |
| `e5` | E/T/I only | top5 | class[30] | **-$12** | -$5 | 29% | $987 | -1% | 2.39 | 48min | -$1,052 | -$334 | 44% | 29% |
| `e5` | E/T/I only | top5 | class[30]+mmirror@25 | **-$32** | -$11 | 28% | $1,172 | -3% | 2.82 | 33min | -$954 | -$334 | 42% | 24% |
| `e5` | E/T/I only | top5 | class[60] | **-$26** | -$13 | 30% | $858 | -3% | 2.02 | 63min | -$1,224 | -$334 | 43% | 41% |
| `e5` | E/T/I only | top5 | class[60]+mmirror@25 | **-$36** | -$15 | 29% | $1,031 | -3% | 2.41 | 46min | -$1,214 | -$334 | 41% | 32% |
| `e5` | E/T/I only | top5 | close | **$15** | $9 | 33% | $729 | 2% | 1.63 | 165min | -$1,229 | -$334 | 34% | 61% |
| `e5` | E/T/I only | top5 | mirror@1.00 | **-$44** | -$9 | 29% | $1,962 | -2% | 4.88 | 19min | -$726 | -$318 | 35% | 0% |
| `e5` | E/T/I only | top5 | mirror@1.00+patience15 | **-$14** | -$4 | 29% | $1,340 | -1% | 3.27 | 26min | -$781 | -$334 | 44% | 14% |
| `e5` | E/T/I only | top5 | mmirror@10 | **$10** | $5 | 31% | $864 | 1% | 1.94 | 128min | -$1,229 | -$334 | 33% | 51% |
| `e5` | E/T/I only | top5 | mmirror@10+patience15 | **$4** | $2 | 32% | $842 | 1% | 1.87 | 133min | -$1,229 | -$334 | 36% | 54% |
| `e5` | E/T/I only | top5 | mmirror@10+prof | **$60** | $34 | 33% | $825 | 7% | 1.79 | 145min | -$1,229 | -$334 | 39% | 57% |
| `e5` | E/T/I only | top5 | mmirror@20 | **$13** | $5 | 31% | $1,069 | 1% | 2.38 | 105min | -$1,261 | -$334 | 34% | 40% |
| `e5` | E/T/I only | top5 | mmirror@20+patience15 | **$11** | $5 | 32% | $928 | 1% | 2.06 | 114min | -$1,229 | -$334 | 38% | 48% |
| `e5` | E/T/I only | top5 | mmirror@20+prof | **$70** | $35 | 34% | $922 | 8% | 1.98 | 131min | -$1,229 | -$334 | 44% | 52% |
| `e5` | E/T/I only | top5 | mmirror@25 | **$11** | $4 | 32% | $1,179 | 1% | 2.60 | 93min | -$1,261 | -$334 | 35% | 34% |
| `e5` | E/T/I only | top5 | mmirror@25+patience15 | **$24** | $11 | 33% | $969 | 2% | 2.14 | 107min | -$1,229 | -$334 | 39% | 44% |
| `e5` | E/T/I only | top5 | mmirror@25+prof | **$107** | $52 | 34% | $956 | 11% | 2.05 | 127min | -$1,229 | -$334 | 47% | 49% |
| `e5` | E/T/I only | top5 | oracle | **$1,029** | $519 | 41% | $1,015 | 101% | 1.98 | 106min | -$81 | -$334 | 97% | 3% |
| `e5` | E/T/I only | top5 | shufA1@25 | **$21** | $10 | 31% | $902 | 2% | 2.06 | 110min | -$1,229 | -$334 | 39% | 40% |
| `e5` | E/T/I only | top5 | shufA2@25 | **-$4** | -$2 | 32% | $956 | -0% | 2.11 | 100min | -$1,229 | -$334 | 39% | 45% |
| `e5` | E/T/I only | top5 | shufA3@25 | **$26** | $13 | 33% | $950 | 3% | 2.06 | 108min | -$1,229 | -$334 | 39% | 42% |
| `e5` | E/T/I only | top5 | shufB1[30] | **$16** | $6 | 29% | $1,055 | 2% | 2.56 | 36min | -$895 | -$334 | 45% | 26% |
| `e5` | E/T/I only | top5 | shufB2[30] | **-$18** | -$7 | 29% | $1,049 | -2% | 2.56 | 34min | -$895 | -$334 | 45% | 28% |
| `e5` | E/T/I only | top5 | shufB3[30] | **$12** | $5 | 28% | $1,055 | 1% | 2.54 | 36min | -$874 | -$407 | 47% | 26% |
| `e5` | v3 no-M | thr10 | class[30] | **-$12** | -$26 | 33% | $223 | -6% | 0.48 | 134min | -$941 | -$435 | 27% | 73% |
| `e5` | v3 no-M | thr10 | class[30]+mmirror@25 | **-$48** | -$84 | 29% | $235 | -20% | 0.57 | 100min | -$1,216 | -$435 | 28% | 62% |
| `e5` | v3 no-M | thr10 | class[60] | **-$12** | -$26 | 33% | $223 | -6% | 0.48 | 134min | -$941 | -$435 | 27% | 73% |
| `e5` | v3 no-M | thr10 | class[60]+mmirror@25 | **-$48** | -$84 | 29% | $235 | -20% | 0.57 | 100min | -$1,216 | -$435 | 28% | 62% |
| `e5` | v3 no-M | thr10 | close | **-$12** | -$26 | 33% | $223 | -6% | 0.48 | 134min | -$941 | -$435 | 27% | 73% |
| `e5` | v3 no-M | thr10 | mirror@1.00 | **-$9** | -$10 | 27% | $334 | -3% | 0.90 | 10min | -$586 | -$318 | 38% | 2% |
| `e5` | v3 no-M | thr10 | mirror@1.00+patience15 | **-$8** | -$11 | 30% | $292 | -3% | 0.72 | 17min | -$720 | -$327 | 51% | 25% |
| `e5` | v3 no-M | thr10 | mmirror@10 | **-$46** | -$86 | 30% | $225 | -20% | 0.53 | 113min | -$1,324 | -$435 | 25% | 72% |
| `e5` | v3 no-M | thr10 | mmirror@10+patience15 | **-$28** | -$55 | 31% | $227 | -12% | 0.51 | 119min | -$941 | -$435 | 28% | 70% |
| `e5` | v3 no-M | thr10 | mmirror@10+prof | **-$44** | -$85 | 31% | $227 | -19% | 0.52 | 121min | -$1,233 | -$435 | 26% | 74% |
| `e5` | v3 no-M | thr10 | mmirror@20 | **-$47** | -$86 | 30% | $233 | -20% | 0.55 | 105min | -$1,216 | -$435 | 26% | 64% |
| `e5` | v3 no-M | thr10 | mmirror@20+patience15 | **-$26** | -$52 | 31% | $227 | -12% | 0.51 | 111min | -$941 | -$435 | 28% | 64% |
| `e5` | v3 no-M | thr10 | mmirror@20+prof | **-$39** | -$73 | 31% | $235 | -17% | 0.53 | 114min | -$941 | -$435 | 30% | 70% |
| `e5` | v3 no-M | thr10 | mmirror@25 | **-$48** | -$84 | 29% | $235 | -20% | 0.57 | 100min | -$1,216 | -$435 | 28% | 62% |
| `e5` | v3 no-M | thr10 | mmirror@25+patience15 | **-$23** | -$45 | 31% | $227 | -10% | 0.51 | 111min | -$941 | -$435 | 30% | 62% |
| `e5` | v3 no-M | thr10 | mmirror@25+prof | **-$40** | -$72 | 30% | $236 | -17% | 0.56 | 108min | -$941 | -$435 | 31% | 69% |
| `e5` | v3 no-M | thr10 | oracle | **$228** | $389 | 27% | $220 | 104% | 0.59 | 53min | -$313 | -$334 | 91% | 9% |
| `e5` | v3 no-M | thr10 | shufA1@25 | **-$43** | -$75 | 27% | $237 | -18% | 0.58 | 85min | -$1,307 | -$344 | 27% | 53% |
| `e5` | v3 no-M | thr10 | shufA2@25 | **-$21** | -$36 | 30% | $246 | -9% | 0.58 | 83min | -$981 | -$326 | 36% | 53% |
| `e5` | v3 no-M | thr10 | shufA3@25 | **-$22** | -$38 | 30% | $248 | -9% | 0.58 | 91min | -$941 | -$362 | 33% | 58% |
| `e5` | v3 no-M | thr10 | shufB1[30] | **-$17** | -$27 | 31% | $268 | -6% | 0.62 | 40min | -$941 | -$344 | 38% | 46% |
| `e5` | v3 no-M | thr10 | shufB2[30] | **-$18** | -$30 | 32% | $263 | -7% | 0.60 | 40min | -$941 | -$344 | 40% | 45% |
| `e5` | v3 no-M | thr10 | shufB3[30] | **-$2** | -$3 | 30% | $264 | -1% | 0.61 | 45min | -$941 | -$344 | 43% | 39% |
| `e5` | v3 no-M | thr20 | class[30] | **-$35** | -$33 | 29% | $465 | -8% | 1.08 | 57min | -$1,992 | -$435 | 35% | 50% |
| `e5` | v3 no-M | thr20 | class[30]+mmirror@25 | **-$51** | -$42 | 28% | $521 | -10% | 1.21 | 48min | -$1,588 | -$435 | 37% | 47% |
| `e5` | v3 no-M | thr20 | class[60] | **-$33** | -$34 | 29% | $437 | -8% | 0.98 | 70min | -$2,051 | -$435 | 33% | 59% |
| `e5` | v3 no-M | thr20 | class[60]+mmirror@25 | **-$51** | -$47 | 28% | $446 | -11% | 1.07 | 60min | -$1,001 | -$435 | 34% | 55% |
| `e5` | v3 no-M | thr20 | close | **-$29** | -$36 | 30% | $376 | -8% | 0.81 | 132min | -$2,051 | -$435 | 24% | 76% |
| `e5` | v3 no-M | thr20 | mirror@1.00 | **-$41** | -$20 | 30% | $869 | -5% | 2.10 | 11min | -$595 | -$344 | 34% | 1% |
| `e5` | v3 no-M | thr20 | mirror@1.00+patience15 | **-$20** | -$13 | 29% | $646 | -3% | 1.56 | 17min | -$892 | -$410 | 48% | 25% |
| `e5` | v3 no-M | thr20 | mmirror@10 | **-$58** | -$61 | 30% | $414 | -14% | 0.94 | 113min | -$1,944 | -$435 | 25% | 74% |
| `e5` | v3 no-M | thr20 | mmirror@10+patience15 | **-$37** | -$41 | 30% | $415 | -9% | 0.91 | 115min | -$1,214 | -$435 | 26% | 73% |
| `e5` | v3 no-M | thr20 | mmirror@10+prof | **-$61** | -$67 | 30% | $409 | -15% | 0.91 | 116min | -$2,051 | -$435 | 24% | 76% |
| `e5` | v3 no-M | thr20 | mmirror@20 | **-$71** | -$64 | 29% | $484 | -15% | 1.10 | 96min | -$1,846 | -$435 | 23% | 63% |
| `e5` | v3 no-M | thr20 | mmirror@20+patience15 | **-$36** | -$37 | 28% | $443 | -8% | 0.98 | 103min | -$1,846 | -$435 | 26% | 65% |
| `e5` | v3 no-M | thr20 | mmirror@20+prof | **-$46** | -$48 | 31% | $437 | -11% | 0.96 | 108min | -$1,355 | -$435 | 28% | 72% |
| `e5` | v3 no-M | thr20 | mmirror@25 | **-$77** | -$68 | 28% | $487 | -16% | 1.13 | 89min | -$1,676 | -$435 | 23% | 55% |
| `e5` | v3 no-M | thr20 | mmirror@25+patience15 | **-$46** | -$45 | 28% | $446 | -10% | 1.01 | 98min | -$1,583 | -$435 | 28% | 63% |
| `e5` | v3 no-M | thr20 | mmirror@25+prof | **-$52** | -$51 | 29% | $443 | -12% | 1.01 | 103min | -$1,668 | -$435 | 29% | 71% |
| `e5` | v3 no-M | thr20 | oracle | **$414** | $395 | 25% | $386 | 107% | 1.05 | 58min | -$313 | -$313 | 95% | 5% |
| `e5` | v3 no-M | thr20 | shufA1@25 | **-$41** | -$39 | 30% | $463 | -9% | 1.06 | 87min | -$1,251 | -$410 | 30% | 51% |
| `e5` | v3 no-M | thr20 | shufA2@25 | **-$32** | -$31 | 29% | $453 | -7% | 1.02 | 87min | -$1,214 | -$386 | 30% | 57% |
| `e5` | v3 no-M | thr20 | shufA3@25 | **-$49** | -$46 | 30% | $474 | -10% | 1.07 | 88min | -$1,214 | -$410 | 31% | 59% |
| `e5` | v3 no-M | thr20 | shufB1[30] | **-$18** | -$15 | 29% | $519 | -4% | 1.22 | 36min | -$1,214 | -$410 | 40% | 41% |
| `e5` | v3 no-M | thr20 | shufB2[30] | **-$14** | -$11 | 30% | $545 | -3% | 1.25 | 32min | -$817 | -$410 | 41% | 37% |
| `e5` | v3 no-M | thr20 | shufB3[30] | **-$17** | -$14 | 28% | $482 | -3% | 1.20 | 36min | -$894 | -$410 | 41% | 36% |
| `e5` | v3 no-M | top3 | class[30] | **-$19** | -$10 | 27% | $717 | -3% | 1.79 | 51min | -$944 | -$435 | 41% | 35% |
| `e5` | v3 no-M | top3 | class[30]+mmirror@25 | **-$27** | -$15 | 28% | $731 | -4% | 1.84 | 47min | -$944 | -$435 | 43% | 31% |
| `e5` | v3 no-M | top3 | class[60] | **-$42** | -$25 | 28% | $662 | -6% | 1.65 | 68min | -$944 | -$435 | 38% | 45% |
| `e5` | v3 no-M | top3 | class[60]+mmirror@25 | **-$51** | -$30 | 28% | $676 | -8% | 1.70 | 63min | -$944 | -$435 | 39% | 42% |
| `e5` | v3 no-M | top3 | close | **-$59** | -$41 | 30% | $595 | -10% | 1.45 | 149min | -$944 | -$435 | 29% | 67% |
| `e5` | v3 no-M | top3 | mirror@1.00 | **-$21** | -$7 | 28% | $1,076 | -2% | 2.93 | 18min | -$514 | -$317 | 37% | 0% |
| `e5` | v3 no-M | top3 | mirror@1.00+patience15 | **-$39** | -$17 | 27% | $886 | -4% | 2.35 | 23min | -$711 | -$326 | 47% | 15% |
| `e5` | v3 no-M | top3 | mmirror@10 | **-$70** | -$47 | 30% | $605 | -12% | 1.48 | 145min | -$944 | -$435 | 30% | 65% |
| `e5` | v3 no-M | top3 | mmirror@10+patience15 | **-$64** | -$44 | 29% | $596 | -11% | 1.46 | 145min | -$944 | -$435 | 30% | 65% |
| `e5` | v3 no-M | top3 | mmirror@10+prof | **-$74** | -$50 | 30% | $605 | -12% | 1.48 | 147min | -$944 | -$435 | 30% | 66% |
| `e5` | v3 no-M | top3 | mmirror@20 | **-$67** | -$43 | 30% | $625 | -11% | 1.55 | 138min | -$944 | -$435 | 30% | 59% |
| `e5` | v3 no-M | top3 | mmirror@20+patience15 | **-$54** | -$36 | 29% | $607 | -9% | 1.49 | 141min | -$944 | -$435 | 31% | 60% |
| `e5` | v3 no-M | top3 | mmirror@20+prof | **-$63** | -$42 | 30% | $610 | -10% | 1.48 | 144min | -$944 | -$435 | 32% | 64% |
| `e5` | v3 no-M | top3 | mmirror@25 | **-$56** | -$35 | 30% | $655 | -9% | 1.60 | 135min | -$944 | -$435 | 30% | 54% |
| `e5` | v3 no-M | top3 | mmirror@25+patience15 | **-$40** | -$27 | 30% | $612 | -7% | 1.50 | 140min | -$944 | -$435 | 33% | 57% |
| `e5` | v3 no-M | top3 | mmirror@25+prof | **-$59** | -$40 | 30% | $610 | -10% | 1.48 | 143min | -$944 | -$435 | 33% | 64% |
| `e5` | v3 no-M | top3 | oracle | **$712** | $408 | 32% | $692 | 103% | 1.75 | 80min | -$129 | -$308 | 98% | 2% |
| `e5` | v3 no-M | top3 | shufA1@25 | **-$67** | -$44 | 29% | $611 | -11% | 1.52 | 130min | -$944 | -$362 | 31% | 56% |
| `e5` | v3 no-M | top3 | shufA2@25 | **-$36** | -$24 | 30% | $607 | -6% | 1.49 | 134min | -$944 | -$362 | 34% | 57% |
| `e5` | v3 no-M | top3 | shufA3@25 | **-$59** | -$39 | 28% | $605 | -10% | 1.51 | 133min | -$944 | -$362 | 32% | 59% |
| `e5` | v3 no-M | top3 | shufB1[30] | **-$3** | -$2 | 28% | $760 | -0% | 1.90 | 32min | -$944 | -$344 | 44% | 27% |
| `e5` | v3 no-M | top3 | shufB2[30] | **-$10** | -$5 | 28% | $758 | -1% | 1.89 | 31min | -$944 | -$344 | 44% | 26% |
| `e5` | v3 no-M | top3 | shufB3[30] | **-$1** | -$0 | 28% | $756 | -0% | 1.90 | 33min | -$944 | -$344 | 44% | 26% |
| `e5` | v3 no-M | top5 | class[30] | **-$64** | -$25 | 26% | $946 | -7% | 2.58 | 40min | -$1,040 | -$435 | 42% | 29% |
| `e5` | v3 no-M | top5 | class[30]+mmirror@25 | **-$87** | -$32 | 25% | $969 | -9% | 2.70 | 37min | -$1,040 | -$435 | 43% | 28% |
| `e5` | v3 no-M | top5 | class[60] | **-$54** | -$25 | 26% | $807 | -7% | 2.13 | 58min | -$924 | -$435 | 40% | 41% |
| `e5` | v3 no-M | top5 | class[60]+mmirror@25 | **-$85** | -$38 | 25% | $819 | -10% | 2.24 | 54min | -$924 | -$435 | 39% | 40% |
| `e5` | v3 no-M | top5 | close | **-$48** | -$28 | 29% | $683 | -7% | 1.71 | 151min | -$1,184 | -$435 | 31% | 66% |
| `e5` | v3 no-M | top5 | mirror@1.00 | **-$57** | -$12 | 28% | $1,778 | -3% | 4.84 | 20min | -$726 | -$318 | 36% | 0% |
| `e5` | v3 no-M | top5 | mirror@1.00+patience15 | **-$55** | -$16 | 28% | $1,288 | -4% | 3.45 | 26min | -$839 | -$327 | 43% | 14% |
| `e5` | v3 no-M | top5 | mmirror@10 | **-$78** | -$42 | 29% | $708 | -11% | 1.83 | 138min | -$1,184 | -$435 | 30% | 64% |
| `e5` | v3 no-M | top5 | mmirror@10+patience15 | **-$60** | -$33 | 29% | $704 | -9% | 1.80 | 141min | -$1,184 | -$435 | 32% | 63% |
| `e5` | v3 no-M | top5 | mmirror@10+prof | **-$71** | -$40 | 29% | $703 | -10% | 1.77 | 145min | -$1,184 | -$435 | 31% | 65% |
| `e5` | v3 no-M | top5 | mmirror@20 | **-$95** | -$49 | 28% | $733 | -13% | 1.94 | 129min | -$1,184 | -$435 | 29% | 59% |
| `e5` | v3 no-M | top5 | mmirror@20+patience15 | **-$77** | -$42 | 28% | $712 | -11% | 1.86 | 132min | -$1,184 | -$435 | 31% | 59% |
| `e5` | v3 no-M | top5 | mmirror@20+prof | **-$79** | -$43 | 29% | $713 | -11% | 1.81 | 139min | -$1,184 | -$435 | 32% | 64% |
| `e5` | v3 no-M | top5 | mmirror@25 | **-$62** | -$31 | 29% | $790 | -8% | 2.02 | 128min | -$1,241 | -$435 | 31% | 52% |
| `e5` | v3 no-M | top5 | mmirror@25+patience15 | **-$39** | -$20 | 29% | $738 | -5% | 1.89 | 132min | -$1,184 | -$435 | 34% | 55% |
| `e5` | v3 no-M | top5 | mmirror@25+prof | **-$64** | -$35 | 30% | $722 | -9% | 1.83 | 139min | -$1,184 | -$435 | 34% | 63% |
| `e5` | v3 no-M | top5 | oracle | **$910** | $426 | 34% | $887 | 103% | 2.13 | 87min | -$255 | -$314 | 97% | 3% |
| `e5` | v3 no-M | top5 | shufA1@25 | **-$73** | -$39 | 28% | $727 | -10% | 1.88 | 128min | -$1,184 | -$344 | 33% | 55% |
| `e5` | v3 no-M | top5 | shufA2@25 | **-$29** | -$16 | 29% | $725 | -4% | 1.83 | 130min | -$1,184 | -$326 | 34% | 53% |
| `e5` | v3 no-M | top5 | shufA3@25 | **-$58** | -$30 | 28% | $764 | -8% | 1.94 | 123min | -$1,184 | -$362 | 32% | 55% |
| `e5` | v3 no-M | top5 | shufB1[30] | **-$45** | -$16 | 26% | $995 | -5% | 2.71 | 33min | -$1,040 | -$344 | 44% | 26% |
| `e5` | v3 no-M | top5 | shufB2[30] | **-$48** | -$18 | 26% | $1,007 | -5% | 2.74 | 30min | -$1,040 | -$344 | 44% | 25% |
| `e5` | v3 no-M | top5 | shufB3[30] | **-$42** | -$16 | 25% | $964 | -4% | 2.67 | 33min | -$1,040 | -$344 | 44% | 25% |
| `e6` | E/T/I only | thr10 | class[30] | **-$7** | -$24 | 32% | $137 | -5% | 0.28 | 108min | -$1,266 | -$334 | 26% | 74% |
| `e6` | E/T/I only | thr10 | class[30]+mmirror@25 | **-$27** | -$55 | 36% | $272 | -10% | 0.49 | 37min | -$861 | -$338 | 38% | 40% |
| `e6` | E/T/I only | thr10 | class[60] | **-$7** | -$24 | 32% | $137 | -5% | 0.28 | 108min | -$1,266 | -$334 | 26% | 74% |
| `e6` | E/T/I only | thr10 | class[60]+mmirror@25 | **-$27** | -$55 | 36% | $272 | -10% | 0.49 | 37min | -$861 | -$338 | 38% | 40% |
| `e6` | E/T/I only | thr10 | close | **-$7** | -$24 | 32% | $137 | -5% | 0.28 | 108min | -$1,266 | -$334 | 26% | 74% |
| `e6` | E/T/I only | thr10 | mirror@1.00 | **-$13** | -$24 | 37% | $295 | -4% | 0.53 | 9min | -$581 | -$321 | 36% | 3% |
| `e6` | E/T/I only | thr10 | mirror@1.00+patience15 | **-$10** | -$27 | 35% | $195 | -5% | 0.36 | 17min | -$914 | -$334 | 40% | 28% |
| `e6` | E/T/I only | thr10 | mmirror@10 | **-$16** | -$38 | 30% | $185 | -9% | 0.42 | 59min | -$1,064 | -$334 | 32% | 55% |
| `e6` | E/T/I only | thr10 | mmirror@10+patience15 | **-$6** | -$20 | 31% | $150 | -4% | 0.31 | 77min | -$1,070 | -$334 | 29% | 63% |
| `e6` | E/T/I only | thr10 | mmirror@10+prof | **-$5** | -$15 | 32% | $172 | -3% | 0.36 | 69min | -$914 | -$334 | 38% | 62% |
| `e6` | E/T/I only | thr10 | mmirror@20 | **-$22** | -$46 | 36% | $257 | -9% | 0.47 | 39min | -$873 | -$338 | 40% | 42% |
| `e6` | E/T/I only | thr10 | mmirror@20+patience15 | **-$17** | -$51 | 34% | $182 | -10% | 0.34 | 54min | -$1,070 | -$334 | 34% | 58% |
| `e6` | E/T/I only | thr10 | mmirror@20+prof | **-$9** | -$21 | 39% | $244 | -3% | 0.41 | 46min | -$914 | -$338 | 48% | 52% |
| `e6` | E/T/I only | thr10 | mmirror@25 | **-$27** | -$55 | 36% | $272 | -10% | 0.49 | 37min | -$861 | -$338 | 38% | 40% |
| `e6` | E/T/I only | thr10 | mmirror@25+patience15 | **-$19** | -$55 | 34% | $182 | -10% | 0.34 | 53min | -$1,070 | -$334 | 34% | 58% |
| `e6` | E/T/I only | thr10 | mmirror@25+prof | **-$4** | -$10 | 38% | $246 | -2% | 0.43 | 43min | -$914 | -$338 | 50% | 50% |
| `e6` | E/T/I only | thr10 | oracle | **$152** | $486 | 31% | $147 | 104% | 0.31 | 54min | $0 | -$271 | 97% | 3% |
| `e6` | E/T/I only | thr10 | shufA1@25 | **-$14** | -$33 | 34% | $206 | -7% | 0.42 | 47min | -$1,009 | -$345 | 36% | 49% |
| `e6` | E/T/I only | thr10 | shufA2@25 | **$5** | $14 | 40% | $237 | 2% | 0.38 | 46min | -$881 | -$336 | 44% | 44% |
| `e6` | E/T/I only | thr10 | shufA3@25 | **-$9** | -$23 | 36% | $214 | -4% | 0.38 | 49min | -$1,110 | -$338 | 38% | 52% |
| `e6` | E/T/I only | thr10 | shufB1[30] | **-$14** | -$47 | 33% | $156 | -9% | 0.29 | 51min | -$944 | -$334 | 39% | 58% |
| `e6` | E/T/I only | thr10 | shufB2[30] | **-$10** | -$35 | 33% | $158 | -7% | 0.29 | 22min | -$944 | -$341 | 42% | 58% |
| `e6` | E/T/I only | thr10 | shufB3[30] | **-$4** | -$14 | 31% | $138 | -3% | 0.29 | 39min | -$944 | -$334 | 41% | 53% |
| `e6` | E/T/I only | thr20 | class[30] | **-$11** | -$14 | 34% | $396 | -3% | 0.79 | 40min | -$1,266 | -$354 | 39% | 55% |
| `e6` | E/T/I only | thr20 | class[30]+mmirror@25 | **-$35** | -$34 | 34% | $516 | -7% | 1.04 | 24min | -$2,020 | -$354 | 40% | 48% |
| `e6` | E/T/I only | thr20 | class[60] | **-$26** | -$36 | 34% | $371 | -7% | 0.73 | 50min | -$1,266 | -$354 | 29% | 61% |
| `e6` | E/T/I only | thr20 | class[60]+mmirror@25 | **-$48** | -$54 | 36% | $466 | -10% | 0.89 | 37min | -$2,452 | -$354 | 31% | 55% |
| `e6` | E/T/I only | thr20 | close | **$1** | $2 | 33% | $351 | 0% | 0.71 | 107min | -$1,266 | -$354 | 24% | 76% |
| `e6` | E/T/I only | thr20 | mirror@1.00 | **-$4** | -$2 | 37% | $887 | -0% | 1.64 | 11min | -$1,104 | -$335 | 36% | 3% |
| `e6` | E/T/I only | thr20 | mirror@1.00+patience15 | **$5** | $5 | 35% | $519 | 1% | 1.04 | 18min | -$1,242 | -$354 | 43% | 25% |
| `e6` | E/T/I only | thr20 | mmirror@10 | **$30** | $33 | 32% | $447 | 7% | 0.92 | 84min | -$944 | -$354 | 31% | 60% |
| `e6` | E/T/I only | thr20 | mmirror@10+patience15 | **$35** | $43 | 33% | $400 | 9% | 0.81 | 93min | -$1,242 | -$354 | 29% | 67% |
| `e6` | E/T/I only | thr20 | mmirror@10+prof | **$24** | $30 | 33% | $402 | 6% | 0.82 | 91min | -$1,242 | -$354 | 32% | 68% |
| `e6` | E/T/I only | thr20 | mmirror@20 | **$48** | $36 | 34% | $698 | 7% | 1.36 | 58min | -$939 | -$354 | 37% | 39% |
| `e6` | E/T/I only | thr20 | mmirror@20+patience15 | **$43** | $45 | 35% | $493 | 9% | 0.96 | 75min | -$1,242 | -$354 | 36% | 51% |
| `e6` | E/T/I only | thr20 | mmirror@20+prof | **$24** | $23 | 34% | $532 | 4% | 1.04 | 70min | -$1,519 | -$354 | 41% | 59% |
| `e6` | E/T/I only | thr20 | mmirror@25 | **$28** | $20 | 36% | $758 | 4% | 1.45 | 48min | -$939 | -$354 | 37% | 36% |
| `e6` | E/T/I only | thr20 | mmirror@25+patience15 | **$25** | $25 | 34% | $495 | 5% | 0.97 | 64min | -$1,242 | -$354 | 37% | 49% |
| `e6` | E/T/I only | thr20 | mmirror@25+prof | **$22** | $20 | 36% | $574 | 4% | 1.09 | 64min | -$1,242 | -$354 | 43% | 57% |
| `e6` | E/T/I only | thr20 | oracle | **$423** | $498 | 33% | $416 | 102% | 0.85 | 62min | -$207 | -$313 | 98% | 2% |
| `e6` | E/T/I only | thr20 | shufA1@25 | **$6** | $5 | 37% | $533 | 1% | 1.02 | 61min | -$1,128 | -$345 | 37% | 46% |
| `e6` | E/T/I only | thr20 | shufA2@25 | **-$12** | -$12 | 35% | $518 | -2% | 1.01 | 58min | -$1,242 | -$354 | 36% | 50% |
| `e6` | E/T/I only | thr20 | shufA3@25 | **-$21** | -$19 | 35% | $589 | -4% | 1.09 | 51min | -$1,242 | -$354 | 34% | 48% |
| `e6` | E/T/I only | thr20 | shufB1[30] | **-$32** | -$38 | 34% | $428 | -7% | 0.84 | 26min | -$1,242 | -$354 | 40% | 52% |
| `e6` | E/T/I only | thr20 | shufB2[30] | **-$20** | -$24 | 34% | $435 | -5% | 0.85 | 23min | -$1,242 | -$354 | 42% | 52% |
| `e6` | E/T/I only | thr20 | shufB3[30] | **-$22** | -$27 | 33% | $410 | -5% | 0.83 | 25min | -$1,242 | -$354 | 41% | 51% |
| `e6` | E/T/I only | top3 | class[30] | **$58** | $32 | 33% | $739 | 8% | 1.79 | 35min | -$925 | -$379 | 49% | 35% |
| `e6` | E/T/I only | top3 | class[30]+mmirror@25 | **$44** | $24 | 33% | $767 | 6% | 1.87 | 29min | -$882 | -$379 | 49% | 32% |
| `e6` | E/T/I only | top3 | class[60] | **$3** | $2 | 34% | $677 | 0% | 1.58 | 51min | -$925 | -$379 | 41% | 45% |
| `e6` | E/T/I only | top3 | class[60]+mmirror@25 | **-$6** | -$3 | 34% | $701 | -1% | 1.64 | 45min | -$882 | -$379 | 41% | 41% |
| `e6` | E/T/I only | top3 | close | **-$22** | -$15 | 35% | $649 | -3% | 1.47 | 142min | -$944 | -$379 | 29% | 67% |
| `e6` | E/T/I only | top3 | mirror@1.00 | **$34** | $12 | 34% | $1,204 | 3% | 2.91 | 17min | -$590 | -$335 | 36% | 2% |
| `e6` | E/T/I only | top3 | mirror@1.00+patience15 | **$58** | $27 | 34% | $885 | 7% | 2.13 | 23min | -$925 | -$379 | 50% | 16% |
| `e6` | E/T/I only | top3 | mmirror@10 | **-$23** | -$15 | 34% | $670 | -3% | 1.54 | 133min | -$944 | -$379 | 30% | 64% |
| `e6` | E/T/I only | top3 | mmirror@10+patience15 | **-$20** | -$13 | 35% | $661 | -3% | 1.51 | 137min | -$944 | -$379 | 30% | 66% |
| `e6` | E/T/I only | top3 | mmirror@10+prof | **-$17** | -$11 | 35% | $665 | -3% | 1.52 | 136min | -$944 | -$379 | 31% | 66% |
| `e6` | E/T/I only | top3 | mmirror@20 | **$24** | $14 | 34% | $760 | 3% | 1.71 | 116min | -$882 | -$379 | 34% | 52% |
| `e6` | E/T/I only | top3 | mmirror@20+patience15 | **$23** | $14 | 35% | $695 | 3% | 1.58 | 122min | -$925 | -$379 | 37% | 58% |
| `e6` | E/T/I only | top3 | mmirror@20+prof | **$2** | $1 | 35% | $696 | 0% | 1.58 | 125min | -$944 | -$379 | 36% | 62% |
| `e6` | E/T/I only | top3 | mmirror@25 | **$10** | $6 | 34% | $793 | 1% | 1.79 | 106min | -$882 | -$348 | 34% | 50% |
| `e6` | E/T/I only | top3 | mmirror@25+patience15 | **-$3** | -$2 | 34% | $697 | -0% | 1.62 | 112min | -$925 | -$379 | 35% | 57% |
| `e6` | E/T/I only | top3 | mmirror@25+prof | **$10** | $6 | 36% | $726 | 1% | 1.62 | 118min | -$944 | -$379 | 39% | 59% |
| `e6` | E/T/I only | top3 | oracle | **$850** | $485 | 39% | $821 | 104% | 1.75 | 86min | -$310 | -$379 | 96% | 4% |
| `e6` | E/T/I only | top3 | shufA1@25 | **-$7** | -$4 | 34% | $694 | -1% | 1.58 | 119min | -$882 | -$379 | 32% | 57% |
| `e6` | E/T/I only | top3 | shufA2@25 | **$5** | $3 | 35% | $692 | 1% | 1.57 | 118min | -$925 | -$379 | 35% | 57% |
| `e6` | E/T/I only | top3 | shufA3@25 | **-$2** | -$1 | 35% | $707 | -0% | 1.57 | 116min | -$925 | -$379 | 35% | 56% |
| `e6` | E/T/I only | top3 | shufB1[30] | **$51** | $28 | 33% | $740 | 7% | 1.80 | 27min | -$925 | -$379 | 50% | 33% |
| `e6` | E/T/I only | top3 | shufB2[30] | **$53** | $29 | 33% | $740 | 7% | 1.80 | 25min | -$925 | -$379 | 51% | 33% |
| `e6` | E/T/I only | top3 | shufB3[30] | **$55** | $31 | 33% | $740 | 7% | 1.80 | 26min | -$925 | -$379 | 51% | 33% |
| `e6` | E/T/I only | top5 | class[30] | **-$45** | -$18 | 31% | $958 | -5% | 2.49 | 29min | -$1,267 | -$379 | 42% | 35% |
| `e6` | E/T/I only | top5 | class[30]+mmirror@25 | **-$34** | -$13 | 31% | $978 | -3% | 2.55 | 27min | -$1,267 | -$379 | 43% | 33% |
| `e6` | E/T/I only | top5 | class[60] | **-$36** | -$17 | 33% | $839 | -4% | 2.09 | 44min | -$1,266 | -$379 | 39% | 47% |
| `e6` | E/T/I only | top5 | class[60]+mmirror@25 | **-$26** | -$12 | 33% | $847 | -3% | 2.13 | 42min | -$1,242 | -$379 | 41% | 45% |
| `e6` | E/T/I only | top5 | close | **-$91** | -$51 | 33% | $712 | -13% | 1.78 | 127min | -$1,266 | -$379 | 27% | 70% |
| `e6` | E/T/I only | top5 | mirror@1.00 | **$17** | $4 | 33% | $1,927 | 1% | 4.72 | 17min | -$853 | -$335 | 36% | 1% |
| `e6` | E/T/I only | top5 | mirror@1.00+patience15 | **-$8** | -$3 | 32% | $1,254 | -1% | 3.17 | 24min | -$1,242 | -$379 | 44% | 16% |
| `e6` | E/T/I only | top5 | mmirror@10 | **-$73** | -$38 | 32% | $773 | -9% | 1.91 | 119min | -$1,217 | -$379 | 29% | 64% |
| `e6` | E/T/I only | top5 | mmirror@10+patience15 | **-$78** | -$43 | 33% | $739 | -11% | 1.84 | 122min | -$1,242 | -$379 | 29% | 67% |
| `e6` | E/T/I only | top5 | mmirror@10+prof | **-$81** | -$44 | 32% | $732 | -11% | 1.83 | 123min | -$1,242 | -$379 | 29% | 68% |
| `e6` | E/T/I only | top5 | mmirror@20 | **-$11** | -$5 | 32% | $926 | -1% | 2.19 | 104min | -$1,217 | -$379 | 33% | 52% |
| `e6` | E/T/I only | top5 | mmirror@20+patience15 | **-$23** | -$11 | 34% | $832 | -3% | 1.99 | 111min | -$1,242 | -$379 | 35% | 57% |
| `e6` | E/T/I only | top5 | mmirror@20+prof | **-$29** | -$15 | 33% | $803 | -4% | 1.96 | 114min | -$1,242 | -$379 | 36% | 62% |
| `e6` | E/T/I only | top5 | mmirror@25 | **$6** | $2 | 33% | $1,021 | 1% | 2.35 | 94min | -$1,217 | -$357 | 34% | 49% |
| `e6` | E/T/I only | top5 | mmirror@25+patience15 | **-$26** | -$13 | 34% | $878 | -3% | 2.06 | 105min | -$1,242 | -$379 | 34% | 55% |
| `e6` | E/T/I only | top5 | mmirror@25+prof | **-$10** | -$5 | 33% | $857 | -1% | 2.05 | 109min | -$1,242 | -$379 | 38% | 60% |
| `e6` | E/T/I only | top5 | oracle | **$1,048** | $459 | 38% | $1,019 | 103% | 2.29 | 78min | -$207 | -$379 | 96% | 4% |
| `e6` | E/T/I only | top5 | shufA1@25 | **-$104** | -$52 | 31% | $788 | -13% | 2.00 | 103min | -$1,212 | -$379 | 29% | 59% |
| `e6` | E/T/I only | top5 | shufA2@25 | **-$81** | -$41 | 31% | $787 | -10% | 1.97 | 103min | -$1,242 | -$379 | 30% | 59% |
| `e6` | E/T/I only | top5 | shufA3@25 | **-$68** | -$34 | 33% | $820 | -8% | 2.00 | 101min | -$1,242 | -$379 | 33% | 57% |
| `e6` | E/T/I only | top5 | shufB1[30] | **-$46** | -$18 | 31% | $978 | -5% | 2.53 | 25min | -$1,267 | -$379 | 43% | 34% |
| `e6` | E/T/I only | top5 | shufB2[30] | **-$38** | -$15 | 32% | $976 | -4% | 2.51 | 25min | -$1,267 | -$379 | 44% | 34% |
| `e6` | E/T/I only | top5 | shufB3[30] | **-$40** | -$16 | 31% | $978 | -4% | 2.53 | 25min | -$1,267 | -$379 | 44% | 34% |
| `e6` | v3 no-M | thr10 | class[30] | **$12** | $16 | 31% | $359 | 3% | 0.71 | 120min | -$1,508 | -$357 | 24% | 75% |
| `e6` | v3 no-M | thr10 | class[30]+mmirror@25 | **-$15** | -$14 | 33% | $548 | -3% | 1.14 | 66min | -$1,891 | -$354 | 30% | 48% |
| `e6` | v3 no-M | thr10 | class[60] | **$12** | $16 | 31% | $359 | 3% | 0.71 | 120min | -$1,508 | -$357 | 24% | 75% |
| `e6` | v3 no-M | thr10 | class[60]+mmirror@25 | **-$15** | -$14 | 33% | $548 | -3% | 1.14 | 66min | -$1,891 | -$354 | 30% | 48% |
| `e6` | v3 no-M | thr10 | close | **$12** | $16 | 31% | $359 | 3% | 0.71 | 120min | -$1,508 | -$357 | 24% | 75% |
| `e6` | v3 no-M | thr10 | mirror@1.00 | **-$11** | -$6 | 30% | $854 | -1% | 1.80 | 10min | -$901 | -$319 | 33% | 2% |
| `e6` | v3 no-M | thr10 | mirror@1.00+patience15 | **-$13** | -$10 | 31% | $606 | -2% | 1.30 | 18min | -$1,588 | -$354 | 46% | 25% |
| `e6` | v3 no-M | thr10 | mmirror@10 | **$6** | $6 | 32% | $443 | 1% | 0.92 | 95min | -$1,722 | -$354 | 27% | 60% |
| `e6` | v3 no-M | thr10 | mmirror@10+patience15 | **-$2** | -$2 | 32% | $397 | -1% | 0.80 | 104min | -$1,456 | -$354 | 26% | 69% |
| `e6` | v3 no-M | thr10 | mmirror@10+prof | **-$3** | -$3 | 32% | $399 | -1% | 0.80 | 105min | -$1,508 | -$357 | 27% | 72% |
| `e6` | v3 no-M | thr10 | mmirror@20 | **$2** | $1 | 34% | $534 | 0% | 1.08 | 77min | -$1,876 | -$354 | 31% | 52% |
| `e6` | v3 no-M | thr10 | mmirror@20+patience15 | **$9** | $9 | 32% | $455 | 2% | 0.93 | 85min | -$1,337 | -$354 | 33% | 61% |
| `e6` | v3 no-M | thr10 | mmirror@20+prof | **-$5** | -$6 | 33% | $455 | -1% | 0.91 | 89min | -$1,828 | -$357 | 32% | 68% |
| `e6` | v3 no-M | thr10 | mmirror@25 | **-$15** | -$14 | 33% | $548 | -3% | 1.14 | 66min | -$1,891 | -$354 | 30% | 48% |
| `e6` | v3 no-M | thr10 | mmirror@25+patience15 | **-$5** | -$5 | 31% | $468 | -1% | 0.98 | 76min | -$1,337 | -$354 | 34% | 57% |
| `e6` | v3 no-M | thr10 | mmirror@25+prof | **-$23** | -$25 | 33% | $472 | -5% | 0.94 | 83min | -$1,828 | -$357 | 33% | 67% |
| `e6` | v3 no-M | thr10 | oracle | **$394** | $388 | 23% | $382 | 103% | 1.02 | 55min | -$308 | -$318 | 94% | 6% |
| `e6` | v3 no-M | thr10 | shufA1@25 | **-$9** | -$9 | 30% | $485 | -2% | 1.00 | 73min | -$2,074 | -$354 | 25% | 54% |
| `e6` | v3 no-M | thr10 | shufA2@25 | **$18** | $18 | 29% | $461 | 4% | 0.99 | 73min | -$1,466 | -$354 | 35% | 50% |
| `e6` | v3 no-M | thr10 | shufA3@25 | **$14** | $14 | 29% | $457 | 3% | 0.99 | 71min | -$1,824 | -$354 | 32% | 53% |
| `e6` | v3 no-M | thr10 | shufB1[30] | **-$29** | -$29 | 32% | $493 | -6% | 0.98 | 41min | -$1,623 | -$354 | 39% | 45% |
| `e6` | v3 no-M | thr10 | shufB2[30] | **-$46** | -$46 | 30% | $474 | -10% | 1.00 | 35min | -$1,889 | -$354 | 38% | 52% |
| `e6` | v3 no-M | thr10 | shufB3[30] | **-$14** | -$14 | 30% | $468 | -3% | 0.97 | 45min | -$1,838 | -$354 | 38% | 51% |
| `e6` | v3 no-M | thr20 | class[30] | **$18** | $12 | 35% | $728 | 2% | 1.47 | 65min | -$2,830 | -$357 | 36% | 55% |
| `e6` | v3 no-M | thr20 | class[30]+mmirror@25 | **-$8** | -$4 | 31% | $877 | -1% | 1.95 | 46min | -$2,830 | -$355 | 35% | 46% |
| `e6` | v3 no-M | thr20 | class[60] | **$38** | $27 | 35% | $688 | 6% | 1.42 | 73min | -$2,830 | -$357 | 33% | 61% |
| `e6` | v3 no-M | thr20 | class[60]+mmirror@25 | **$6** | $3 | 31% | $808 | 1% | 1.81 | 54min | -$2,830 | -$355 | 33% | 51% |
| `e6` | v3 no-M | thr20 | close | **-$23** | -$18 | 35% | $620 | -4% | 1.29 | 134min | -$2,830 | -$357 | 26% | 69% |
| `e6` | v3 no-M | thr20 | mirror@1.00 | **-$34** | -$10 | 31% | $1,527 | -2% | 3.38 | 11min | -$1,543 | -$335 | 33% | 2% |
| `e6` | v3 no-M | thr20 | mirror@1.00+patience15 | **-$8** | -$4 | 33% | $1,111 | -1% | 2.41 | 18min | -$2,267 | -$355 | 43% | 24% |
| `e6` | v3 no-M | thr20 | mmirror@10 | **-$18** | -$12 | 35% | $716 | -2% | 1.51 | 113min | -$2,830 | -$355 | 29% | 59% |
| `e6` | v3 no-M | thr20 | mmirror@10+patience15 | **-$24** | -$17 | 36% | $657 | -4% | 1.38 | 122min | -$2,830 | -$355 | 27% | 65% |
| `e6` | v3 no-M | thr20 | mmirror@10+prof | **-$29** | -$21 | 35% | $660 | -4% | 1.38 | 123min | -$2,830 | -$357 | 28% | 67% |
| `e6` | v3 no-M | thr20 | mmirror@20 | **-$54** | -$28 | 34% | $911 | -6% | 1.96 | 83min | -$2,830 | -$355 | 29% | 50% |
| `e6` | v3 no-M | thr20 | mmirror@20+patience15 | **-$47** | -$29 | 35% | $768 | -6% | 1.62 | 97min | -$2,830 | -$355 | 29% | 60% |
| `e6` | v3 no-M | thr20 | mmirror@20+prof | **-$27** | -$17 | 35% | $734 | -4% | 1.57 | 106min | -$2,830 | -$357 | 32% | 64% |
| `e6` | v3 no-M | thr20 | mmirror@25 | **-$61** | -$29 | 34% | $985 | -6% | 2.08 | 74min | -$2,518 | -$355 | 30% | 46% |
| `e6` | v3 no-M | thr20 | mmirror@25+patience15 | **-$42** | -$24 | 34% | $820 | -5% | 1.71 | 87min | -$2,520 | -$355 | 32% | 56% |
| `e6` | v3 no-M | thr20 | mmirror@25+prof | **-$29** | -$18 | 36% | $795 | -4% | 1.62 | 99min | -$2,518 | -$357 | 35% | 61% |
| `e6` | v3 no-M | thr20 | oracle | **$718** | $385 | 27% | $690 | 104% | 1.87 | 57min | -$307 | -$318 | 94% | 6% |
| `e6` | v3 no-M | thr20 | shufA1@25 | **-$26** | -$15 | 34% | $856 | -3% | 1.78 | 82min | -$3,016 | -$355 | 30% | 51% |
| `e6` | v3 no-M | thr20 | shufA2@25 | **$7** | $4 | 34% | $812 | 1% | 1.71 | 84min | -$2,192 | -$355 | 33% | 49% |
| `e6` | v3 no-M | thr20 | shufA3@25 | **-$12** | -$7 | 31% | $789 | -2% | 1.77 | 82min | -$2,741 | -$355 | 31% | 53% |
| `e6` | v3 no-M | thr20 | shufB1[30] | **-$16** | -$9 | 34% | $889 | -2% | 1.79 | 34min | -$2,830 | -$355 | 42% | 42% |
| `e6` | v3 no-M | thr20 | shufB2[30] | **-$37** | -$21 | 34% | $878 | -4% | 1.80 | 33min | -$2,830 | -$355 | 41% | 47% |
| `e6` | v3 no-M | thr20 | shufB3[30] | **$12** | $7 | 34% | $873 | 1% | 1.80 | 36min | -$2,830 | -$355 | 41% | 47% |
| `e6` | v3 no-M | top3 | class[30] | **$45** | $25 | 30% | $767 | 6% | 1.83 | 53min | -$933 | -$379 | 40% | 40% |
| `e6` | v3 no-M | top3 | class[30]+mmirror@25 | **$38** | $19 | 31% | $857 | 4% | 1.99 | 46min | -$933 | -$379 | 40% | 35% |
| `e6` | v3 no-M | top3 | class[60] | **$18** | $11 | 30% | $701 | 3% | 1.65 | 69min | -$933 | -$379 | 35% | 52% |
| `e6` | v3 no-M | top3 | class[60]+mmirror@25 | **$8** | $5 | 31% | $789 | 1% | 1.79 | 60min | -$933 | -$379 | 35% | 45% |
| `e6` | v3 no-M | top3 | close | **-$37** | -$24 | 32% | $672 | -6% | 1.53 | 141min | -$933 | -$379 | 27% | 69% |
| `e6` | v3 no-M | top3 | mirror@1.00 | **$59** | $20 | 34% | $1,287 | 5% | 2.91 | 18min | -$652 | -$309 | 39% | 1% |
| `e6` | v3 no-M | top3 | mirror@1.00+patience15 | **$17** | $7 | 32% | $1,008 | 2% | 2.36 | 23min | -$778 | -$379 | 46% | 17% |
| `e6` | v3 no-M | top3 | mmirror@10 | **-$36** | -$22 | 31% | $700 | -5% | 1.61 | 132min | -$933 | -$379 | 28% | 66% |
| `e6` | v3 no-M | top3 | mmirror@10+patience15 | **-$34** | -$22 | 32% | $695 | -5% | 1.57 | 135min | -$933 | -$379 | 28% | 67% |
| `e6` | v3 no-M | top3 | mmirror@10+prof | **-$34** | -$21 | 32% | $695 | -5% | 1.58 | 136min | -$933 | -$379 | 28% | 68% |
| `e6` | v3 no-M | top3 | mmirror@20 | **-$36** | -$20 | 32% | $778 | -5% | 1.78 | 115min | -$933 | -$379 | 30% | 60% |
| `e6` | v3 no-M | top3 | mmirror@20+patience15 | **-$24** | -$14 | 33% | $751 | -3% | 1.70 | 119min | -$933 | -$379 | 32% | 61% |
| `e6` | v3 no-M | top3 | mmirror@20+prof | **-$20** | -$12 | 32% | $744 | -3% | 1.68 | 127min | -$933 | -$379 | 32% | 64% |
| `e6` | v3 no-M | top3 | mmirror@25 | **-$32** | -$18 | 32% | $813 | -4% | 1.84 | 108min | -$933 | -$354 | 31% | 54% |
| `e6` | v3 no-M | top3 | mmirror@25+patience15 | **-$24** | -$14 | 32% | $776 | -3% | 1.74 | 111min | -$933 | -$379 | 33% | 58% |
| `e6` | v3 no-M | top3 | mmirror@25+prof | **-$33** | -$19 | 32% | $774 | -4% | 1.74 | 118min | -$933 | -$379 | 34% | 63% |
| `e6` | v3 no-M | top3 | oracle | **$834** | $440 | 32% | $820 | 102% | 1.89 | 75min | -$291 | -$379 | 97% | 3% |
| `e6` | v3 no-M | top3 | shufA1@25 | **$9** | $5 | 32% | $767 | 1% | 1.71 | 115min | -$933 | -$379 | 33% | 55% |
| `e6` | v3 no-M | top3 | shufA2@25 | **$9** | $5 | 33% | $748 | 1% | 1.63 | 117min | -$933 | -$379 | 32% | 56% |
| `e6` | v3 no-M | top3 | shufA3@25 | **$4** | $2 | 31% | $753 | 1% | 1.71 | 112min | -$933 | -$354 | 32% | 57% |
| `e6` | v3 no-M | top3 | shufB1[30] | **-$11** | -$6 | 32% | $870 | -1% | 1.99 | 27min | -$933 | -$379 | 43% | 35% |
| `e6` | v3 no-M | top3 | shufB2[30] | **-$9** | -$4 | 32% | $853 | -1% | 1.96 | 31min | -$933 | -$379 | 43% | 36% |
| `e6` | v3 no-M | top3 | shufB3[30] | **$23** | $12 | 31% | $833 | 3% | 1.93 | 36min | -$933 | -$379 | 43% | 35% |
| `e6` | v3 no-M | top5 | class[30] | **$69** | $28 | 33% | $1,027 | 7% | 2.48 | 48min | -$1,244 | -$379 | 41% | 39% |
| `e6` | v3 no-M | top5 | class[30]+mmirror@25 | **$66** | $24 | 34% | $1,163 | 6% | 2.71 | 40min | -$1,223 | -$379 | 41% | 34% |
| `e6` | v3 no-M | top5 | class[60] | **$42** | $19 | 33% | $902 | 5% | 2.16 | 65min | -$1,244 | -$379 | 38% | 49% |
| `e6` | v3 no-M | top5 | class[60]+mmirror@25 | **$26** | $11 | 34% | $1,031 | 3% | 2.36 | 55min | -$1,223 | -$379 | 38% | 44% |
| `e6` | v3 no-M | top5 | close | **-$28** | -$16 | 34% | $784 | -4% | 1.79 | 143min | -$1,244 | -$379 | 28% | 66% |
| `e6` | v3 no-M | top5 | mirror@1.00 | **$49** | $10 | 33% | $2,005 | 2% | 4.79 | 18min | -$817 | -$309 | 36% | 1% |
| `e6` | v3 no-M | top5 | mirror@1.00+patience15 | **$35** | $10 | 33% | $1,446 | 2% | 3.39 | 24min | -$1,223 | -$379 | 46% | 16% |
| `e6` | v3 no-M | top5 | mmirror@10 | **-$49** | -$25 | 33% | $833 | -6% | 1.95 | 129min | -$1,244 | -$379 | 28% | 63% |
| `e6` | v3 no-M | top5 | mmirror@10+patience15 | **-$53** | -$28 | 33% | $812 | -7% | 1.90 | 130min | -$1,244 | -$379 | 28% | 64% |
| `e6` | v3 no-M | top5 | mmirror@10+prof | **-$50** | -$26 | 33% | $815 | -6% | 1.91 | 130min | -$1,244 | -$379 | 29% | 66% |
| `e6` | v3 no-M | top5 | mmirror@20 | **-$58** | -$26 | 33% | $950 | -6% | 2.21 | 109min | -$1,377 | -$379 | 29% | 56% |
| `e6` | v3 no-M | top5 | mmirror@20+patience15 | **-$56** | -$27 | 33% | $887 | -6% | 2.08 | 112min | -$1,244 | -$379 | 30% | 59% |
| `e6` | v3 no-M | top5 | mmirror@20+prof | **-$30** | -$15 | 34% | $865 | -4% | 1.99 | 122min | -$1,244 | -$379 | 33% | 62% |
| `e6` | v3 no-M | top5 | mmirror@25 | **-$48** | -$21 | 34% | $1,024 | -5% | 2.33 | 102min | -$1,223 | -$354 | 30% | 52% |
| `e6` | v3 no-M | top5 | mmirror@25+patience15 | **-$53** | -$25 | 33% | $936 | -6% | 2.16 | 105min | -$1,223 | -$379 | 31% | 57% |
| `e6` | v3 no-M | top5 | mmirror@25+prof | **-$47** | -$23 | 34% | $915 | -5% | 2.07 | 114min | -$1,244 | -$379 | 33% | 62% |
| `e6` | v3 no-M | top5 | oracle | **$1,020** | $428 | 33% | $993 | 103% | 2.38 | 72min | -$309 | -$379 | 94% | 6% |
| `e6` | v3 no-M | top5 | shufA1@25 | **$8** | $4 | 34% | $938 | 1% | 2.11 | 105min | -$1,244 | -$379 | 32% | 53% |
| `e6` | v3 no-M | top5 | shufA2@25 | **$3** | $1 | 35% | $891 | 0% | 2.01 | 107min | -$1,223 | -$379 | 33% | 56% |
| `e6` | v3 no-M | top5 | shufA3@25 | **$2** | $1 | 33% | $933 | 0% | 2.13 | 99min | -$1,223 | -$354 | 32% | 53% |
| `e6` | v3 no-M | top5 | shufB1[30] | **$1** | $0 | 34% | $1,186 | 0% | 2.77 | 29min | -$1,244 | -$379 | 44% | 35% |
| `e6` | v3 no-M | top5 | shufB2[30] | **$13** | $5 | 33% | $1,155 | 1% | 2.74 | 31min | -$1,244 | -$379 | 43% | 36% |
| `e6` | v3 no-M | top5 | shufB3[30] | **$56** | $20 | 33% | $1,145 | 5% | 2.72 | 33min | -$1,244 | -$379 | 44% | 34% |
| `e7` | E/T/I only | thr10 | class[30] | **$98** | $234 | 47% | $326 | 30% | 0.42 | 102min | -$3,086 | -$351 | 32% | 68% |
| `e7` | E/T/I only | thr10 | class[30]+mmirror@25 | **$62** | $88 | 48% | $627 | 10% | 0.71 | 45min | -$3,086 | -$548 | 32% | 47% |
| `e7` | E/T/I only | thr10 | class[60] | **$98** | $234 | 47% | $326 | 30% | 0.42 | 102min | -$3,086 | -$351 | 32% | 68% |
| `e7` | E/T/I only | thr10 | class[60]+mmirror@25 | **$62** | $88 | 48% | $627 | 10% | 0.71 | 45min | -$3,086 | -$548 | 32% | 47% |
| `e7` | E/T/I only | thr10 | close | **$98** | $234 | 47% | $326 | 30% | 0.42 | 102min | -$3,086 | -$351 | 32% | 68% |
| `e7` | E/T/I only | thr10 | mirror@1.00 | **$57** | $55 | 42% | $775 | 7% | 1.05 | 8min | -$1,160 | -$342 | 41% | 7% |
| `e7` | E/T/I only | thr10 | mirror@1.00+patience15 | **$52** | $73 | 43% | $548 | 9% | 0.71 | 16min | -$2,360 | -$548 | 41% | 45% |
| `e7` | E/T/I only | thr10 | mmirror@10 | **$95** | $211 | 47% | $339 | 28% | 0.45 | 95min | -$3,086 | -$351 | 31% | 64% |
| `e7` | E/T/I only | thr10 | mmirror@10+patience15 | **$99** | $233 | 47% | $326 | 30% | 0.43 | 99min | -$3,086 | -$351 | 32% | 68% |
| `e7` | E/T/I only | thr10 | mmirror@10+prof | **$101** | $236 | 47% | $326 | 31% | 0.43 | 100min | -$3,086 | -$351 | 32% | 68% |
| `e7` | E/T/I only | thr10 | mmirror@20 | **$76** | $132 | 45% | $494 | 15% | 0.57 | 60min | -$3,086 | -$351 | 33% | 51% |
| `e7` | E/T/I only | thr10 | mmirror@20+patience15 | **$94** | $182 | 46% | $428 | 22% | 0.52 | 66min | -$3,086 | -$351 | 36% | 62% |
| `e7` | E/T/I only | thr10 | mmirror@20+prof | **$76** | $142 | 44% | $450 | 17% | 0.54 | 65min | -$3,086 | -$351 | 35% | 65% |
| `e7` | E/T/I only | thr10 | mmirror@25 | **$62** | $88 | 48% | $627 | 10% | 0.71 | 45min | -$3,086 | -$548 | 32% | 47% |
| `e7` | E/T/I only | thr10 | mmirror@25+patience15 | **$84** | $139 | 45% | $491 | 17% | 0.61 | 52min | -$3,086 | -$548 | 35% | 62% |
| `e7` | E/T/I only | thr10 | mmirror@25+prof | **$65** | $97 | 48% | $592 | 11% | 0.66 | 50min | -$3,086 | -$548 | 38% | 62% |
| `e7` | E/T/I only | thr10 | oracle | **$470** | $727 | 36% | $390 | 121% | 0.65 | 35min | -$316 | -$571 | 92% | 8% |
| `e7` | E/T/I only | thr10 | shufA1@25 | **$34** | $51 | 45% | $565 | 6% | 0.66 | 48min | -$3,181 | -$571 | 34% | 57% |
| `e7` | E/T/I only | thr10 | shufA2@25 | **$54** | $86 | 45% | $507 | 11% | 0.62 | 53min | -$2,348 | -$548 | 40% | 50% |
| `e7` | E/T/I only | thr10 | shufA3@25 | **$49** | $78 | 46% | $548 | 9% | 0.63 | 53min | -$2,416 | -$420 | 39% | 52% |
| `e7` | E/T/I only | thr10 | shufB1[30] | **$47** | $78 | 44% | $469 | 10% | 0.61 | 26min | -$1,693 | -$420 | 38% | 55% |
| `e7` | E/T/I only | thr10 | shufB2[30] | **$75** | $131 | 44% | $451 | 17% | 0.57 | 26min | -$1,693 | -$571 | 43% | 49% |
| `e7` | E/T/I only | thr10 | shufB3[30] | **$65** | $114 | 45% | $441 | 15% | 0.57 | 24min | -$2,204 | -$420 | 41% | 50% |
| `e7` | E/T/I only | thr20 | class[30] | **$119** | $98 | 38% | $760 | 16% | 1.20 | 45min | -$1,821 | -$416 | 42% | 47% |
| `e7` | E/T/I only | thr20 | class[30]+mmirror@25 | **$101** | $63 | 40% | $1,025 | 10% | 1.59 | 30min | -$1,981 | -$548 | 41% | 45% |
| `e7` | E/T/I only | thr20 | class[60] | **$81** | $74 | 36% | $668 | 12% | 1.09 | 55min | -$2,251 | -$416 | 34% | 62% |
| `e7` | E/T/I only | thr20 | class[60]+mmirror@25 | **$70** | $50 | 38% | $887 | 8% | 1.39 | 41min | -$2,466 | -$548 | 35% | 57% |
| `e7` | E/T/I only | thr20 | close | **$107** | $114 | 35% | $590 | 18% | 0.94 | 106min | -$1,815 | -$416 | 26% | 74% |
| `e7` | E/T/I only | thr20 | mirror@1.00 | **$23** | $7 | 38% | $2,011 | 1% | 3.26 | 9min | -$1,714 | -$430 | 35% | 8% |
| `e7` | E/T/I only | thr20 | mirror@1.00+patience15 | **$52** | $26 | 39% | $1,233 | 4% | 1.99 | 16min | -$2,904 | -$548 | 42% | 40% |
| `e7` | E/T/I only | thr20 | mmirror@10 | **$68** | $65 | 36% | $635 | 11% | 1.06 | 92min | -$2,142 | -$416 | 26% | 71% |
| `e7` | E/T/I only | thr20 | mmirror@10+patience15 | **$81** | $79 | 37% | $628 | 13% | 1.02 | 97min | -$2,142 | -$416 | 28% | 72% |
| `e7` | E/T/I only | thr20 | mmirror@10+prof | **$85** | $84 | 36% | $621 | 14% | 1.01 | 100min | -$2,142 | -$416 | 27% | 73% |
| `e7` | E/T/I only | thr20 | mmirror@20 | **$53** | $32 | 36% | $1,057 | 5% | 1.66 | 59min | -$2,622 | -$416 | 30% | 50% |
| `e7` | E/T/I only | thr20 | mmirror@20+patience15 | **$73** | $56 | 37% | $811 | 9% | 1.30 | 74min | -$2,622 | -$416 | 34% | 64% |
| `e7` | E/T/I only | thr20 | mmirror@20+prof | **$69** | $52 | 36% | $869 | 8% | 1.34 | 73min | -$2,142 | -$416 | 33% | 67% |
| `e7` | E/T/I only | thr20 | mmirror@25 | **$50** | $26 | 39% | $1,342 | 4% | 1.93 | 47min | -$2,622 | -$548 | 32% | 42% |
| `e7` | E/T/I only | thr20 | mmirror@25+patience15 | **$82** | $58 | 38% | $905 | 9% | 1.41 | 61min | -$2,622 | -$548 | 35% | 59% |
| `e7` | E/T/I only | thr20 | mmirror@25+prof | **$58** | $38 | 39% | $1,071 | 5% | 1.52 | 59min | -$2,142 | -$548 | 37% | 63% |
| `e7` | E/T/I only | thr20 | oracle | **$872** | $566 | 30% | $774 | 113% | 1.54 | 42min | -$263 | -$571 | 92% | 8% |
| `e7` | E/T/I only | thr20 | shufA1@25 | **$51** | $32 | 39% | $1,130 | 5% | 1.60 | 52min | -$2,238 | -$571 | 32% | 54% |
| `e7` | E/T/I only | thr20 | shufA2@25 | **$53** | $33 | 40% | $1,097 | 5% | 1.62 | 53min | -$1,404 | -$548 | 35% | 54% |
| `e7` | E/T/I only | thr20 | shufA3@25 | **$29** | $18 | 38% | $1,122 | 3% | 1.64 | 52min | -$1,856 | -$507 | 33% | 54% |
| `e7` | E/T/I only | thr20 | shufB1[30] | **$111** | $80 | 39% | $946 | 12% | 1.39 | 27min | -$1,503 | -$416 | 43% | 44% |
| `e7` | E/T/I only | thr20 | shufB2[30] | **$94** | $67 | 39% | $924 | 10% | 1.40 | 27min | -$1,477 | -$571 | 44% | 44% |
| `e7` | E/T/I only | thr20 | shufB3[30] | **$83** | $57 | 38% | $934 | 9% | 1.46 | 26min | -$2,309 | -$416 | 41% | 47% |
| `e7` | E/T/I only | top3 | class[30] | **$4** | $2 | 33% | $868 | 1% | 1.97 | 36min | -$985 | -$367 | 45% | 36% |
| `e7` | E/T/I only | top3 | class[30]+mmirror@25 | **-$6** | -$3 | 34% | $924 | -1% | 2.06 | 31min | -$985 | -$367 | 44% | 33% |
| `e7` | E/T/I only | top3 | class[60] | **$25** | $14 | 33% | $774 | 3% | 1.74 | 51min | -$985 | -$367 | 41% | 48% |
| `e7` | E/T/I only | top3 | class[60]+mmirror@25 | **$16** | $9 | 34% | $825 | 2% | 1.82 | 46min | -$985 | -$367 | 41% | 44% |
| `e7` | E/T/I only | top3 | close | **$44** | $27 | 33% | $729 | 6% | 1.60 | 137min | -$985 | -$367 | 31% | 66% |
| `e7` | E/T/I only | top3 | mirror@1.00 | **$17** | $6 | 34% | $1,266 | 1% | 2.92 | 20min | -$856 | -$416 | 37% | 3% |
| `e7` | E/T/I only | top3 | mirror@1.00+patience15 | **-$27** | -$12 | 34% | $1,015 | -3% | 2.31 | 24min | -$985 | -$416 | 42% | 22% |
| `e7` | E/T/I only | top3 | mmirror@10 | **$45** | $28 | 34% | $740 | 6% | 1.63 | 135min | -$985 | -$367 | 31% | 65% |
| `e7` | E/T/I only | top3 | mmirror@10+patience15 | **$48** | $30 | 33% | $735 | 7% | 1.62 | 136min | -$985 | -$367 | 31% | 65% |
| `e7` | E/T/I only | top3 | mmirror@10+prof | **$46** | $29 | 33% | $729 | 6% | 1.61 | 136min | -$985 | -$367 | 31% | 66% |
| `e7` | E/T/I only | top3 | mmirror@20 | **$28** | $16 | 33% | $788 | 4% | 1.76 | 122min | -$985 | -$416 | 32% | 59% |
| `e7` | E/T/I only | top3 | mmirror@20+patience15 | **$37** | $22 | 33% | $764 | 5% | 1.70 | 125min | -$985 | -$416 | 33% | 63% |
| `e7` | E/T/I only | top3 | mmirror@20+prof | **$47** | $28 | 33% | $764 | 6% | 1.69 | 127min | -$985 | -$416 | 34% | 63% |
| `e7` | E/T/I only | top3 | mmirror@25 | **$17** | $10 | 34% | $824 | 2% | 1.80 | 117min | -$985 | -$416 | 32% | 54% |
| `e7` | E/T/I only | top3 | mmirror@25+patience15 | **$21** | $12 | 33% | $779 | 3% | 1.72 | 122min | -$985 | -$416 | 33% | 60% |
| `e7` | E/T/I only | top3 | mmirror@25+prof | **$21** | $13 | 34% | $790 | 3% | 1.71 | 122min | -$985 | -$416 | 34% | 63% |
| `e7` | E/T/I only | top3 | oracle | **$913** | $468 | 34% | $875 | 104% | 1.95 | 82min | -$296 | -$316 | 97% | 3% |
| `e7` | E/T/I only | top3 | shufA1@25 | **-$4** | -$2 | 33% | $774 | -0% | 1.71 | 118min | -$985 | -$416 | 30% | 61% |
| `e7` | E/T/I only | top3 | shufA2@25 | **$29** | $17 | 34% | $764 | 4% | 1.69 | 122min | -$985 | -$416 | 32% | 59% |
| `e7` | E/T/I only | top3 | shufA3@25 | **$26** | $15 | 33% | $752 | 3% | 1.69 | 124min | -$985 | -$367 | 33% | 58% |
| `e7` | E/T/I only | top3 | shufB1[30] | **-$12** | -$6 | 34% | $895 | -1% | 2.02 | 26min | -$985 | -$367 | 46% | 34% |
| `e7` | E/T/I only | top3 | shufB2[30] | **-$2** | -$1 | 34% | $886 | -0% | 2.01 | 26min | -$985 | -$367 | 46% | 34% |
| `e7` | E/T/I only | top3 | shufB3[30] | **-$7** | -$3 | 34% | $895 | -1% | 2.02 | 26min | -$985 | -$367 | 46% | 34% |
| `e7` | E/T/I only | top5 | class[30] | **-$0** | -$0 | 29% | $1,160 | -0% | 2.86 | 32min | -$1,567 | -$548 | 45% | 33% |
| `e7` | E/T/I only | top5 | class[30]+mmirror@25 | **-$19** | -$6 | 30% | $1,270 | -1% | 2.99 | 28min | -$1,567 | -$548 | 45% | 31% |
| `e7` | E/T/I only | top5 | class[60] | **$18** | $8 | 31% | $994 | 2% | 2.39 | 48min | -$1,567 | -$548 | 43% | 46% |
| `e7` | E/T/I only | top5 | class[60]+mmirror@25 | **-$2** | -$1 | 32% | $1,100 | -0% | 2.51 | 43min | -$1,567 | -$548 | 42% | 43% |
| `e7` | E/T/I only | top5 | close | **-$3** | -$2 | 31% | $856 | -0% | 1.98 | 128min | -$1,567 | -$548 | 29% | 67% |
| `e7` | E/T/I only | top5 | mirror@1.00 | **-$10** | -$2 | 32% | $2,025 | -0% | 4.78 | 20min | -$1,416 | -$416 | 35% | 3% |
| `e7` | E/T/I only | top5 | mirror@1.00+patience15 | **-$33** | -$9 | 31% | $1,455 | -2% | 3.52 | 25min | -$1,567 | -$548 | 41% | 20% |
| `e7` | E/T/I only | top5 | mmirror@10 | **$14** | $7 | 31% | $880 | 2% | 2.03 | 125min | -$1,567 | -$548 | 29% | 65% |
| `e7` | E/T/I only | top5 | mmirror@10+patience15 | **$23** | $11 | 31% | $873 | 3% | 2.00 | 126min | -$1,567 | -$548 | 30% | 66% |
| `e7` | E/T/I only | top5 | mmirror@10+prof | **$16** | $8 | 31% | $867 | 2% | 1.99 | 127min | -$1,567 | -$548 | 30% | 66% |
| `e7` | E/T/I only | top5 | mmirror@20 | **$38** | $18 | 32% | $969 | 4% | 2.19 | 115min | -$1,567 | -$548 | 33% | 57% |
| `e7` | E/T/I only | top5 | mmirror@20+patience15 | **$52** | $25 | 31% | $922 | 6% | 2.11 | 117min | -$1,567 | -$548 | 34% | 61% |
| `e7` | E/T/I only | top5 | mmirror@20+prof | **$44** | $21 | 32% | $940 | 5% | 2.10 | 119min | -$1,567 | -$548 | 35% | 62% |
| `e7` | E/T/I only | top5 | mmirror@25 | **$32** | $14 | 33% | $1,058 | 3% | 2.30 | 106min | -$1,567 | -$548 | 33% | 51% |
| `e7` | E/T/I only | top5 | mmirror@25+patience15 | **$33** | $15 | 32% | $948 | 4% | 2.17 | 111min | -$1,567 | -$548 | 34% | 58% |
| `e7` | E/T/I only | top5 | mmirror@25+prof | **$31** | $14 | 33% | $997 | 3% | 2.16 | 111min | -$1,567 | -$548 | 36% | 61% |
| `e7` | E/T/I only | top5 | oracle | **$1,179** | $470 | 33% | $1,108 | 106% | 2.51 | 80min | -$400 | -$330 | 96% | 4% |
| `e7` | E/T/I only | top5 | shufA1@25 | **$7** | $3 | 32% | $984 | 1% | 2.19 | 108min | -$1,567 | -$416 | 32% | 57% |
| `e7` | E/T/I only | top5 | shufA2@25 | **$35** | $16 | 32% | $954 | 4% | 2.14 | 112min | -$1,567 | -$548 | 34% | 56% |
| `e7` | E/T/I only | top5 | shufA3@25 | **$34** | $16 | 32% | $964 | 4% | 2.17 | 112min | -$1,567 | -$548 | 35% | 55% |
| `e7` | E/T/I only | top5 | shufB1[30] | **-$10** | -$3 | 30% | $1,200 | -1% | 2.92 | 26min | -$1,567 | -$548 | 46% | 31% |
| `e7` | E/T/I only | top5 | shufB2[30] | **-$8** | -$3 | 30% | $1,188 | -1% | 2.91 | 27min | -$1,567 | -$548 | 46% | 31% |
| `e7` | E/T/I only | top5 | shufB3[30] | **-$1** | -$0 | 29% | $1,196 | -0% | 2.92 | 26min | -$1,567 | -$548 | 46% | 31% |
| `e7` | v3 no-M | thr10 | class[30] | **-$3** | -$6 | 35% | $310 | -1% | 0.45 | 67min | -$3,298 | -$489 | 20% | 80% |
| `e7` | v3 no-M | thr10 | class[30]+mmirror@25 | **$36** | $51 | 39% | $492 | 7% | 0.70 | 42min | -$3,298 | -$489 | 31% | 51% |
| `e7` | v3 no-M | thr10 | class[60] | **-$3** | -$6 | 35% | $310 | -1% | 0.45 | 67min | -$3,298 | -$489 | 20% | 80% |
| `e7` | v3 no-M | thr10 | class[60]+mmirror@25 | **$36** | $51 | 39% | $492 | 7% | 0.70 | 42min | -$3,298 | -$489 | 31% | 51% |
| `e7` | v3 no-M | thr10 | close | **-$3** | -$6 | 35% | $310 | -1% | 0.45 | 67min | -$3,298 | -$489 | 20% | 80% |
| `e7` | v3 no-M | thr10 | mirror@1.00 | **$48** | $47 | 37% | $700 | 7% | 1.01 | 7min | -$1,250 | -$503 | 36% | 7% |
| `e7` | v3 no-M | thr10 | mirror@1.00+patience15 | **$4** | $5 | 34% | $443 | 1% | 0.70 | 13min | -$2,003 | -$548 | 38% | 50% |
| `e7` | v3 no-M | thr10 | mmirror@10 | **$16** | $25 | 38% | $433 | 4% | 0.62 | 48min | -$3,298 | -$489 | 29% | 68% |
| `e7` | v3 no-M | thr10 | mmirror@10+patience15 | **$14** | $28 | 37% | $356 | 4% | 0.51 | 58min | -$3,298 | -$489 | 24% | 76% |
| `e7` | v3 no-M | thr10 | mmirror@10+prof | **$12** | $20 | 36% | $423 | 3% | 0.61 | 49min | -$3,298 | -$489 | 28% | 72% |
| `e7` | v3 no-M | thr10 | mmirror@20 | **$34** | $49 | 38% | $474 | 7% | 0.69 | 43min | -$3,298 | -$489 | 31% | 57% |
| `e7` | v3 no-M | thr10 | mmirror@20+patience15 | **$16** | $30 | 36% | $366 | 4% | 0.55 | 53min | -$3,298 | -$489 | 24% | 72% |
| `e7` | v3 no-M | thr10 | mmirror@20+prof | **$23** | $35 | 37% | $450 | 5% | 0.65 | 46min | -$3,298 | -$489 | 31% | 69% |
| `e7` | v3 no-M | thr10 | mmirror@25 | **$36** | $51 | 39% | $492 | 7% | 0.70 | 42min | -$3,298 | -$489 | 31% | 51% |
| `e7` | v3 no-M | thr10 | mmirror@25+patience15 | **$17** | $30 | 37% | $370 | 4% | 0.56 | 51min | -$3,298 | -$489 | 24% | 68% |
| `e7` | v3 no-M | thr10 | mmirror@25+prof | **$22** | $33 | 37% | $453 | 5% | 0.65 | 45min | -$3,298 | -$489 | 31% | 68% |
| `e7` | v3 no-M | thr10 | oracle | **$390** | $608 | 29% | $361 | 108% | 0.64 | 24min | $0 | -$571 | 96% | 4% |
| `e7` | v3 no-M | thr10 | shufA1@25 | **$24** | $34 | 38% | $507 | 5% | 0.71 | 35min | -$3,298 | -$489 | 37% | 54% |
| `e7` | v3 no-M | thr10 | shufA2@25 | **-$20** | -$29 | 36% | $448 | -4% | 0.68 | 34min | -$3,298 | -$489 | 31% | 58% |
| `e7` | v3 no-M | thr10 | shufA3@25 | **-$8** | -$11 | 38% | $495 | -2% | 0.69 | 35min | -$3,298 | -$489 | 33% | 53% |
| `e7` | v3 no-M | thr10 | shufB1[30] | **-$33** | -$55 | 35% | $397 | -8% | 0.60 | 19min | -$3,626 | -$548 | 31% | 61% |
| `e7` | v3 no-M | thr10 | shufB2[30] | **-$27** | -$52 | 36% | $362 | -8% | 0.52 | 25min | -$3,626 | -$548 | 32% | 60% |
| `e7` | v3 no-M | thr10 | shufB3[30] | **-$37** | -$63 | 35% | $391 | -9% | 0.58 | 25min | -$3,626 | -$548 | 29% | 66% |
| `e7` | v3 no-M | thr20 | class[30] | **$38** | $31 | 41% | $782 | 5% | 1.25 | 37min | -$1,986 | -$623 | 38% | 53% |
| `e7` | v3 no-M | thr20 | class[30]+mmirror@25 | **$79** | $54 | 41% | $919 | 9% | 1.45 | 31min | -$1,236 | -$623 | 41% | 46% |
| `e7` | v3 no-M | thr20 | class[60] | **$114** | $107 | 41% | $681 | 17% | 1.06 | 48min | -$1,986 | -$434 | 37% | 59% |
| `e7` | v3 no-M | thr20 | class[60]+mmirror@25 | **$158** | $132 | 42% | $797 | 20% | 1.20 | 42min | -$2,089 | -$392 | 41% | 51% |
| `e7` | v3 no-M | thr20 | close | **$96** | $107 | 43% | $606 | 16% | 0.90 | 125min | -$1,986 | -$386 | 30% | 69% |
| `e7` | v3 no-M | thr20 | mirror@1.00 | **$61** | $23 | 39% | $1,690 | 4% | 2.69 | 10min | -$1,380 | -$503 | 35% | 6% |
| `e7` | v3 no-M | thr20 | mirror@1.00+patience15 | **$60** | $34 | 38% | $1,055 | 6% | 1.73 | 17min | -$1,836 | -$623 | 44% | 39% |
| `e7` | v3 no-M | thr20 | mmirror@10 | **$57** | $46 | 40% | $792 | 7% | 1.22 | 88min | -$2,667 | -$489 | 30% | 65% |
| `e7` | v3 no-M | thr20 | mmirror@10+patience15 | **$76** | $72 | 40% | $703 | 11% | 1.06 | 103min | -$1,986 | -$489 | 31% | 67% |
| `e7` | v3 no-M | thr20 | mmirror@10+prof | **$75** | $66 | 40% | $768 | 10% | 1.13 | 96min | -$1,986 | -$489 | 32% | 67% |
| `e7` | v3 no-M | thr20 | mmirror@20 | **$76** | $48 | 39% | $993 | 8% | 1.57 | 69min | -$1,631 | -$489 | 31% | 51% |
| `e7` | v3 no-M | thr20 | mmirror@20+patience15 | **$77** | $65 | 40% | $761 | 10% | 1.18 | 89min | -$1,878 | -$623 | 32% | 63% |
| `e7` | v3 no-M | thr20 | mmirror@20+prof | **$122** | $94 | 41% | $884 | 14% | 1.29 | 84min | -$1,986 | -$489 | 38% | 62% |
| `e7` | v3 no-M | thr20 | mmirror@25 | **$66** | $39 | 40% | $1,063 | 6% | 1.68 | 62min | -$2,063 | -$489 | 32% | 45% |
| `e7` | v3 no-M | thr20 | mmirror@25+patience15 | **$52** | $43 | 40% | $779 | 7% | 1.23 | 81min | -$1,874 | -$623 | 33% | 59% |
| `e7` | v3 no-M | thr20 | mmirror@25+prof | **$106** | $78 | 41% | $908 | 12% | 1.36 | 78min | -$1,986 | -$489 | 39% | 60% |
| `e7` | v3 no-M | thr20 | oracle | **$850** | $611 | 34% | $746 | 114% | 1.39 | 46min | -$309 | -$571 | 94% | 6% |
| `e7` | v3 no-M | thr20 | shufA1@25 | **$59** | $38 | 42% | $1,031 | 6% | 1.55 | 61min | -$1,453 | -$507 | 38% | 47% |
| `e7` | v3 no-M | thr20 | shufA2@25 | **$45** | $30 | 40% | $971 | 5% | 1.52 | 61min | -$3,986 | -$507 | 37% | 48% |
| `e7` | v3 no-M | thr20 | shufA3@25 | **$70** | $47 | 43% | $1,018 | 7% | 1.48 | 64min | -$1,476 | -$623 | 38% | 47% |
| `e7` | v3 no-M | thr20 | shufB1[30] | **$81** | $62 | 40% | $834 | 10% | 1.32 | 27min | -$1,893 | -$571 | 41% | 46% |
| `e7` | v3 no-M | thr20 | shufB2[30] | **$34** | $26 | 39% | $828 | 4% | 1.31 | 26min | -$1,893 | -$623 | 41% | 48% |
| `e7` | v3 no-M | thr20 | shufB3[30] | **$100** | $81 | 40% | $792 | 13% | 1.24 | 33min | -$1,893 | -$571 | 40% | 48% |
| `e7` | v3 no-M | top3 | class[30] | **$37** | $19 | 36% | $939 | 4% | 1.98 | 34min | -$959 | -$392 | 45% | 36% |
| `e7` | v3 no-M | top3 | class[30]+mmirror@25 | **$44** | $22 | 36% | $951 | 5% | 2.00 | 33min | -$853 | -$392 | 45% | 33% |
| `e7` | v3 no-M | top3 | class[60] | **$75** | $44 | 35% | $813 | 9% | 1.71 | 49min | -$959 | -$392 | 42% | 48% |
| `e7` | v3 no-M | top3 | class[60]+mmirror@25 | **$81** | $47 | 35% | $825 | 10% | 1.73 | 48min | -$907 | -$392 | 42% | 45% |
| `e7` | v3 no-M | top3 | close | **$54** | $35 | 36% | $767 | 7% | 1.55 | 143min | -$959 | -$392 | 31% | 66% |
| `e7` | v3 no-M | top3 | mirror@1.00 | **$31** | $11 | 35% | $1,415 | 2% | 2.95 | 19min | -$854 | -$416 | 37% | 3% |
| `e7` | v3 no-M | top3 | mirror@1.00+patience15 | **-$13** | -$5 | 35% | $1,108 | -1% | 2.37 | 23min | -$959 | -$416 | 43% | 22% |
| `e7` | v3 no-M | top3 | mmirror@10 | **$49** | $31 | 35% | $770 | 6% | 1.57 | 139min | -$959 | -$392 | 31% | 65% |
| `e7` | v3 no-M | top3 | mmirror@10+patience15 | **$57** | $37 | 36% | $769 | 7% | 1.55 | 141min | -$959 | -$392 | 31% | 65% |
| `e7` | v3 no-M | top3 | mmirror@10+prof | **$54** | $35 | 36% | $767 | 7% | 1.55 | 143min | -$959 | -$392 | 31% | 66% |
| `e7` | v3 no-M | top3 | mmirror@20 | **$51** | $31 | 35% | $803 | 6% | 1.64 | 132min | -$937 | -$392 | 30% | 59% |
| `e7` | v3 no-M | top3 | mmirror@20+patience15 | **$52** | $33 | 36% | $794 | 7% | 1.61 | 134min | -$959 | -$392 | 31% | 62% |
| `e7` | v3 no-M | top3 | mmirror@20+prof | **$56** | $36 | 36% | $772 | 7% | 1.56 | 142min | -$959 | -$392 | 32% | 65% |
| `e7` | v3 no-M | top3 | mmirror@25 | **$41** | $24 | 35% | $833 | 5% | 1.70 | 124min | -$929 | -$392 | 29% | 55% |
| `e7` | v3 no-M | top3 | mmirror@25+patience15 | **$39** | $24 | 35% | $795 | 5% | 1.63 | 127min | -$959 | -$392 | 31% | 60% |
| `e7` | v3 no-M | top3 | mmirror@25+prof | **$43** | $27 | 35% | $774 | 6% | 1.58 | 137min | -$959 | -$392 | 33% | 65% |
| `e7` | v3 no-M | top3 | oracle | **$935** | $513 | 36% | $896 | 104% | 1.82 | 86min | -$211 | -$316 | 97% | 3% |
| `e7` | v3 no-M | top3 | shufA1@25 | **$37** | $22 | 35% | $811 | 5% | 1.64 | 121min | -$957 | -$392 | 34% | 56% |
| `e7` | v3 no-M | top3 | shufA2@25 | **$17** | $11 | 36% | $822 | 2% | 1.65 | 119min | -$929 | -$392 | 34% | 56% |
| `e7` | v3 no-M | top3 | shufA3@25 | **$36** | $22 | 36% | $864 | 4% | 1.65 | 122min | -$959 | -$392 | 34% | 58% |
| `e7` | v3 no-M | top3 | shufB1[30] | **$14** | $7 | 36% | $979 | 1% | 2.03 | 24min | -$959 | -$392 | 47% | 33% |
| `e7` | v3 no-M | top3 | shufB2[30] | **$12** | $6 | 36% | $977 | 1% | 2.02 | 26min | -$959 | -$392 | 47% | 33% |
| `e7` | v3 no-M | top3 | shufB3[30] | **$5** | $3 | 36% | $970 | 1% | 2.01 | 26min | -$959 | -$392 | 46% | 34% |
| `e7` | v3 no-M | top5 | class[30] | **$0** | $0 | 30% | $1,207 | 0% | 2.83 | 31min | -$1,607 | -$362 | 45% | 33% |
| `e7` | v3 no-M | top5 | class[30]+mmirror@25 | **$12** | $4 | 30% | $1,228 | 1% | 2.87 | 31min | -$1,288 | -$392 | 44% | 30% |
| `e7` | v3 no-M | top5 | class[60] | **$11** | $5 | 31% | $1,022 | 1% | 2.36 | 46min | -$1,607 | -$362 | 42% | 48% |
| `e7` | v3 no-M | top5 | class[60]+mmirror@25 | **$22** | $9 | 31% | $1,031 | 2% | 2.38 | 45min | -$1,288 | -$392 | 41% | 45% |
| `e7` | v3 no-M | top5 | close | **-$0** | -$0 | 32% | $873 | -0% | 1.92 | 131min | -$1,607 | -$362 | 28% | 68% |
| `e7` | v3 no-M | top5 | mirror@1.00 | **$5** | $1 | 32% | $2,125 | 0% | 4.81 | 20min | -$1,309 | -$531 | 37% | 3% |
| `e7` | v3 no-M | top5 | mirror@1.00+patience15 | **-$31** | -$9 | 31% | $1,500 | -2% | 3.52 | 24min | -$1,607 | -$416 | 43% | 20% |
| `e7` | v3 no-M | top5 | mmirror@10 | **-$5** | -$3 | 31% | $882 | -1% | 1.97 | 127min | -$1,440 | -$392 | 28% | 66% |
| `e7` | v3 no-M | top5 | mmirror@10+patience15 | **$6** | $3 | 32% | $882 | 1% | 1.94 | 129min | -$1,607 | -$362 | 28% | 66% |
| `e7` | v3 no-M | top5 | mmirror@10+prof | **$2** | $1 | 32% | $874 | 0% | 1.92 | 131min | -$1,607 | -$392 | 28% | 68% |
| `e7` | v3 no-M | top5 | mmirror@20 | **$37** | $18 | 33% | $961 | 4% | 2.06 | 125min | -$1,288 | -$392 | 29% | 56% |
| `e7` | v3 no-M | top5 | mmirror@20+patience15 | **$24** | $12 | 32% | $924 | 3% | 2.01 | 126min | -$1,607 | -$362 | 29% | 61% |
| `e7` | v3 no-M | top5 | mmirror@20+prof | **$19** | $10 | 32% | $891 | 2% | 1.93 | 130min | -$1,607 | -$392 | 30% | 66% |
| `e7` | v3 no-M | top5 | mmirror@25 | **$19** | $9 | 33% | $1,028 | 2% | 2.18 | 116min | -$1,288 | -$392 | 28% | 50% |
| `e7` | v3 no-M | top5 | mmirror@25+patience15 | **$5** | $3 | 32% | $947 | 1% | 2.07 | 118min | -$1,607 | -$362 | 30% | 59% |
| `e7` | v3 no-M | top5 | mmirror@25+prof | **$10** | $5 | 32% | $907 | 1% | 1.98 | 125min | -$1,607 | -$392 | 31% | 65% |
| `e7` | v3 no-M | top5 | oracle | **$1,201** | $502 | 35% | $1,151 | 104% | 2.39 | 83min | $46 | -$586 | 97% | 3% |
| `e7` | v3 no-M | top5 | shufA1@25 | **$29** | $14 | 33% | $990 | 3% | 2.10 | 112min | -$1,304 | -$392 | 34% | 53% |
| `e7` | v3 no-M | top5 | shufA2@25 | **$22** | $11 | 34% | $1,007 | 2% | 2.08 | 111min | -$1,288 | -$362 | 34% | 53% |
| `e7` | v3 no-M | top5 | shufA3@25 | **$7** | $3 | 33% | $1,014 | 1% | 2.09 | 112min | -$1,440 | -$392 | 32% | 54% |
| `e7` | v3 no-M | top5 | shufB1[30] | **-$13** | -$5 | 30% | $1,254 | -1% | 2.88 | 26min | -$1,607 | -$362 | 46% | 31% |
| `e7` | v3 no-M | top5 | shufB2[30] | **-$18** | -$6 | 30% | $1,252 | -1% | 2.88 | 26min | -$1,607 | -$362 | 46% | 31% |
| `e7` | v3 no-M | top5 | shufB3[30] | **-$12** | -$4 | 30% | $1,252 | -1% | 2.87 | 26min | -$1,607 | -$362 | 46% | 32% |

## The study bars (training-window OOF quantiles)

| segment | era | arm | train rows | features | P@top5 | P@top10 | P@top15 | P@top20 | P@top25 |
|---|---|---|---|---|---|---|---|---|---|
| e | `blind_e3` | E/T/I only | 11475 | 134 | 0.3794 | 0.3668 | 0.3585 | 0.3521 | 0.3468 |
| e | `blind_e3` | v3 no-M | 11475 | 408 | 0.3992 | 0.3799 | 0.3667 | 0.3573 | 0.3493 |
| f | `e4` | E/T/I only | 11941 | 134 | 0.3780 | 0.3660 | 0.3590 | 0.3536 | 0.3487 |
| f | `e4` | v3 no-M | 11941 | 408 | 0.3953 | 0.3776 | 0.3663 | 0.3574 | 0.3502 |
| g | `e5` | E/T/I only | 12700 | 134 | 0.3672 | 0.3558 | 0.3506 | 0.3460 | 0.3428 |
| g | `e5` | v3 no-M | 12700 | 408 | 0.3899 | 0.3725 | 0.3624 | 0.3543 | 0.3477 |
| h | `e6` | E/T/I only | 14948 | 134 | 0.3639 | 0.3547 | 0.3491 | 0.3461 | 0.3426 |
| h | `e6` | v3 no-M | 14948 | 408 | 0.3801 | 0.3639 | 0.3547 | 0.3473 | 0.3416 |
| i | `e7` | E/T/I only | 17065 | 134 | 0.3656 | 0.3559 | 0.3506 | 0.3461 | 0.3426 |
| i | `e7` | v3 no-M | 17065 | 408 | 0.3726 | 0.3602 | 0.3528 | 0.3479 | 0.3432 |

## Laws and controls

- CONTROL — overlay coverage: 9422/9562 candidates carry a `p_lasso_B_c25` prediction set; the rest abstain (the overlay never fires on them)
- CONTROL — replay reproduction vs `precision_trades.tsv`: max |delta| $0.0000 over 47810 (candidate, rule) realised P&Ls across close / mirror@1.00 / oracle / overlay / mirror+overlay
- CONTROL — pick-stream reproduction vs `exit_segments/picks.tsv`: 1956/1956 (session, arm, k) top-k baskets identical
- CONTROL — published bar reproduction: max |delta| 0.00e+00 over 40 (segment, arm, topq) bars of `precision_thresholds.tsv`
- STRICTLY PRIOR: a candidate's model score is a function of features stamped at its OWN decision second and of a model fit on strictly earlier sessions, so an exit stamped at an opposite-side candidate's decision second reads nothing from the future.  The study bars are quantiles of session-grouped OUT-OF-FOLD predictions on each segment's training window.
- NO TEST TUNING: the bar ladder {10,20,25}%, the class decile, the time stops {30,60}, the three A variants, the four streams and the two arms were all fixed before any number was computed, and every cell is reported.  The headline table carries a leave-one-era-out reading beside the in-block maximum.
- ONE POSITION, ONE MINI (D-046): SLOTS=1; the occupancy replay is `exit_engine.replay_day`'s admission test unchanged.
- COSTS: 576 net cents once per trade on every rule including the oracle (`qr_labels/money.hpp`).
- WALL: -30,000 net cents, monitored from entry on marks strictly after the entry mark, filling at the next lawful mark after the crossing; gap-through retained; unchanged from rung 1.
- SEALED ZONE: `packlib.SEALED_FROM` = 918; the highest session replayed here is 917.
- D-022 overlay: era RTY-mini factors `blind_e3` 0.879, `e4` 0.895, `e5` 1.004, `e6` 1.099, `e7` 1.073; every dollar figure is within 12% of its one-mini equivalent and no percentage moves.

# EXIT CENSUS 2 — exit rules priced on the agreement-selected books

_lane_ `port-m2-exits2` · _version_ `PORT-M2-EXITCENSUS2-V1` · develop E3-E7, E8 untouched · adoption of any rule remains the user's (D-029)

## The answer

**No exit rule pays on the agreement books.** 39 rules across five families were priced on the 0.70/0.80/0.85/0.90 agreement books, per era and per asset, against the phase-close baseline on the identical seats. All **156** pooled (book, rule) lines — 39 rules x 4 books — come back KILLED. The least-bad rule on the deployment book (agreement 0.80) is `MHD_STRUCT_0.20ATR` at **$-3.12/session**, which is zero inside the noise, and it fires on 1.7% of trades.

The reason is not that the conditions are blind. They are sharp: *sits below -$600 after 30 minutes* fires on **19.5%** of the trades that eventually lose and on **0.3%** of the trades that eventually win — a precision of **88.9%** against a 12.0% base rate, a **7.429x lift**. The signal is real and the money still is not there, because the $900 wall has already removed the runaway losers and what is left below water at the half-hour mark ends up *less* bad than it looks at the moment the rule would cut it.

## What the exit layer is worth AT MOST

The clairvoyant bounds settle the question for the whole layer, not just for the rules that were tried (agreement-0.80 book, per era, $/session on top of the phase-close baseline):

| clairvoyant exit | era | $/session ADDED |
|---|---|---|
| ORACLE cut every eventual loser at 30 min | E3 | 2.31 |
| ORACLE cut every eventual loser at its best post-30min second | E3 | 20.37 |
| ORACLE take EVERY trade out at its best post-30min second | E3 | 328.01 |
| ORACLE cut every eventual loser at 30 min | E4 | 57.56 |
| ORACLE cut every eventual loser at its best post-30min second | E4 | 108.86 |
| ORACLE take EVERY trade out at its best post-30min second | E4 | 382.46 |
| ORACLE cut every eventual loser at 30 min | E5 | 26.48 |
| ORACLE cut every eventual loser at its best post-30min second | E5 | 62.22 |
| ORACLE take EVERY trade out at its best post-30min second | E5 | 352.62 |
| ORACLE cut every eventual loser at 30 min | E6 | 12.5 |
| ORACLE cut every eventual loser at its best post-30min second | E6 | 74.48 |
| ORACLE take EVERY trade out at its best post-30min second | E6 | 251.04 |
| ORACLE cut every eventual loser at 30 min | E7 | 36.5 |
| ORACLE cut every eventual loser at its best post-30min second | E7 | 80.01 |
| ORACLE take EVERY trade out at its best post-30min second | E7 | 512.92 |

Cutting *every* eventual loser at the perfect second is worth **$20.37-108.86/session**. Taking *every* trade out at its own post-30-minute peak — total clairvoyance over the exit — is worth **$251.04-512.92/session**. The book needs **$750-1,450/session** more to reach the $2,000 floor. **A perfect exit layer does not close the gap, and the achievable fraction of a perfect exit layer is negative.** The gap is an entries/throughput problem.

## The ranked table — agreement 0.80 (the deployment book)

| rule | family | knob | Δ$/session | Δ vs displaced | eras + | worst era | fires on | verdict |
|---|---|---|---|---|---|---|---|---|
| MHD_STRUCT_0.20ATR | 1-MID-HOLD-DISQ | reclaim level lost by 0.20 ATR | -3.12 | 85.29 | 1 | -13.02 | 0.0171 | KILLED |
| MHD_BELOW600_AND_FLOW05 | 1-MID-HOLD-DISQ | -$600 AND flow (later of the two) | -8.44 | 71.98 | 1 | -51.56 | 0.0245 | KILLED |
| MHD_BELOW600 | 1-MID-HOLD-DISQ | sits below -$600 | -8.51 | 84.89 | 1 | -51.56 | 0.0245 | KILLED |
| TIME180_T150 | 4-TIME-DECAY | at entry+180min below +$150 -> exit at market | -18.26 | 64.39 | 1 | -42.12 | 0.1135 | KILLED |
| MHD_BELOW400 | 1-MID-HOLD-DISQ | sits below -$400 | -32.91 | 61.72 | 1 | -78.27 | 0.0583 | KILLED |
| TIME180_T300 | 4-TIME-DECAY | at entry+180min below +$300 -> exit at market | -36.72 | 64.79 | 0 | -56.48 | 0.2277 | KILLED |
| MHD_STRUCT10_AND_FLOW05 | 1-MID-HOLD-DISQ | struct .10 AND flow (later of the two) | -42.24 | 65.37 | 0 | -60.91 | 0.0877 | KILLED |
| MHD_STRUCT_0.10ATR | 1-MID-HOLD-DISQ | reclaim level lost by 0.10 ATR | -43.2 | 53.15 | 0 | -61.94 | 0.0877 | KILLED |

### agreement 0.70

| rule | family | knob | Δ$/session | Δ vs displaced | eras + | worst era | fires on | verdict |
|---|---|---|---|---|---|---|---|---|
| MHD_STRUCT_0.20ATR | 1-MID-HOLD-DISQ | reclaim level lost by 0.20 ATR | -4.35 | 83.59 | 1 | -37.77 | 0.0269 | KILLED |
| MHD_BELOW600_AND_FLOW05 | 1-MID-HOLD-DISQ | -$600 AND flow (later of the two) | -7.52 | 75.45 | 1 | -15.11 | 0.027 | KILLED |
| MHD_BELOW600 | 1-MID-HOLD-DISQ | sits below -$600 | -7.78 | 88.99 | 1 | -15.26 | 0.027 | KILLED |
| TIME180_T150 | 4-TIME-DECAY | at entry+180min below +$150 -> exit at market | -21.11 | 64.34 | 0 | -44.95 | 0.1099 | KILLED |
| MHD_BELOW400 | 1-MID-HOLD-DISQ | sits below -$400 | -33.68 | 67.39 | 0 | -69.46 | 0.0607 | KILLED |
| TIME180_T300 | 4-TIME-DECAY | at entry+180min below +$300 -> exit at market | -39.27 | 54.98 | 0 | -53.19 | 0.2208 | KILLED |
| MHD_STRUCT10_AND_FLOW05 | 1-MID-HOLD-DISQ | struct .10 AND flow (later of the two) | -44.74 | 61.77 | 0 | -55.04 | 0.0933 | KILLED |
| MHD_STRUCT_0.10ATR | 1-MID-HOLD-DISQ | reclaim level lost by 0.10 ATR | -45.68 | 53.51 | 0 | -55.78 | 0.0933 | KILLED |

The *Δ vs displaced* column is the one piece of good news and it is worth reading carefully: almost every rule BEATS its own displaced-time control by $50-90/session. The rules are choosing genuinely worse-than-random moments to leave. Leaving at all is what costs money.

## The autopsy — why sharp conditions still lose

| condition | fires on n | rate on winners | rate on losers | precision | lift | Δ$/session |
|---|---|---|---|---|---|---|
| sits below -$400 after 30 min | 62 | 0.0232 | 0.3333 | 0.6613 | 5.527 | -33.67 |
| sits below -$600 after 30 min | 27 | 0.0033 | 0.1951 | 0.8889 | 7.429 | -7.78 |
| reclaim level lost by 0.10 ATR | 94 | 0.0409 | 0.4634 | 0.6064 | 5.068 | -45.68 |
| reclaim level lost by 0.20 ATR | 26 | 0.0055 | 0.1707 | 0.8077 | 6.75 | -4.35 |
| 15 min of adverse flow, >=0.05 ATR | 961 | 0.9359 | 0.9268 | 0.1186 | 0.991 | -413.69 |
| 15 min of adverse flow, >=0.25 ATR | 118 | 0.1094 | 0.1545 | 0.161 | 1.346 | -61.18 |
| trail armed +$900, 60min extreme | 374 | 0.4 | 0.0976 | 0.0321 | 0.268 | -111.54 |

Three mechanisms, all measured:

1. **The wall already did the cutting.** The $900 wall stops the runaways before any 30-minute rule can look at them, so a -$600 cut can only ever save the last ~$300 of a trade that was going to the wall anyway — on 2-3% of trades.

2. **The survivors mean-revert.** `mean_delta_if_cut_loser` is NEGATIVE in most eras: cutting a trade that ends negative makes it *more* negative, because it is deeper in the hole when the rule fires than where it finishes.

3. **The false positives are expensive.** The rare winner a cut catches costs $600-1,460. At a 0.83-0.93 win rate there is very little loser left to save and a great deal of winner to lose.

The trailing family fails the mirror-image way: it fires on **40.0%** of eventual WINNERS and **9.8%** of eventual losers (lift **0.268** — it is a *winner* detector), so it sells the trades that were still running. Mean give-back on the baseline book is $250-490/trade and none of it is recoverable by a trail, because the give-back is the price of the trades that keep going.

## Combined entries + exits, per era, against the bar

| era | book | sessions | entries only $/ses | + best exit rule | combined $/ses | gap to $2,000 | perfect-exit headroom | entries + perfect exit | capture of ENTRY ceiling | capture of FULL ceiling |
|---|---|---|---|---|---|---|---|---|---|---|
| E3 | 0.70 | 47 | 598.43 | -37.77 | 560.66 | 1439.34 | 421.28 | 1019.71 | 0.1994 | 0.2676 |
| E4 | 0.70 | 186 | 646.94 | -4.57 | 642.37 | 1357.63 | 395.13 | 1042.07 | 0.2369 | 0.3278 |
| E5 | 0.70 | 275 | 728.74 | -3.34 | 725.4 | 1274.6 | 397.07 | 1125.81 | 0.2891 | 0.4235 |
| E6 | 0.70 | 46 | 549.43 | 5.16 | 554.59 | 1445.41 | 337.77 | 887.2 | 0.1525 | 0.1756 |
| E7 | 0.70 | 256 | 1249.91 | -0.85 | 1249.06 | 750.94 | 567.43 | 1817.34 | 0.3189 | 0.3243 |
| E3 | 0.80 | 27 | 554.81 | 0.0 | 554.81 | 1445.19 | 328.01 | 882.82 | 0.1928 | 0.2344 |
| E4 | 0.80 | 134 | 624.84 | -7.46 | 617.38 | 1382.62 | 382.46 | 1007.3 | 0.2282 | 0.3129 |
| E5 | 0.80 | 181 | 702.73 | 1.18 | 703.91 | 1296.09 | 352.62 | 1055.35 | 0.282 | 0.4027 |
| E6 | 0.80 | 24 | 602.81 | -13.02 | 589.79 | 1410.21 | 251.04 | 853.85 | 0.1399 | 0.1408 |
| E7 | 0.80 | 206 | 1174.53 | -3.33 | 1171.2 | 828.8 | 512.92 | 1687.45 | 0.2983 | 0.3103 |

Targets on the face: **floor $2,000/session/asset**, aim $2,500-3,000. No era reaches the floor on any book, with or without exits, and no era reaches it even with a clairvoyant exit. E7 is the closest: $1249.06 combined, $750.94 short.

Capture-of-ceiling reads: the book captures **19-32%** of the ENTRY foresight ceiling (perfect entry selection, same phase-close contract) and **14-42%** of the FULL clairvoyant ceiling (perfect entries AND perfect exits). Exit deltas are the only layer that can push capture-of-ENTRY-ceiling above 1.0, and on this book they push it *down*. One caveat stated rather than hidden: E5/HG reads capture-of-FULL-ceiling **above 1.0** (1.35-1.48) — the anchored oracle-leg family does not dominate every realised trade on that cell, so that denominator is not a true bound there.

## The top rule's full risk panel — agreement 0.80

| arm | era | takes | win | P(≥$1k) | $/trade | $/session | MAE p90 | wall hit | dd p90 | dd max | D-030 breach | weekly p10 | losing weeks |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BASE_PHASE_CLOSE | E3 | 29 | 0.931 | 0.1034 | 516.55 | 554.81 | 440.0 | 0.2069 | 0.0 | 267.5 | 0.0 | 45.0 | 0.1053 |
| MHD_STRUCT_0.20ATR | E3 | 29 | 0.931 | 0.1034 | 516.55 | 554.81 | 440.0 | 0.2069 | 0.0 | 267.5 | 0.0 | 45.0 | 0.1053 |
| BASE_PHASE_CLOSE | E4 | 148 | 0.8176 | 0.223 | 565.73 | 624.84 | 513.13 | 0.2095 | 142.5 | 930.0 | 0.0 | 1194.38 | 0.0 |
| MHD_STRUCT_0.20ATR | E4 | 148 | 0.8108 | 0.223 | 558.98 | 617.38 | 513.13 | 0.2095 | 151.25 | 735.0 | 0.0 | 984.38 | 0.0 |
| BASE_PHASE_CLOSE | E5 | 216 | 0.912 | 0.1898 | 588.87 | 702.73 | 400.0 | 0.1528 | 0.0 | 930.0 | 0.0 | 2475.62 | 0.0 |
| MHD_STRUCT_0.20ATR | E5 | 216 | 0.912 | 0.1898 | 589.85 | 703.91 | 400.0 | 0.1528 | 0.0 | 605.0 | 0.0 | 2475.62 | 0.0 |
| BASE_PHASE_CLOSE | E6 | 24 | 0.8333 | 0.2083 | 602.81 | 602.81 | 592.5 | 0.5 | 135.0 | 355.0 | 0.0 | -161.25 | 0.2143 |
| MHD_STRUCT_0.20ATR | E6 | 24 | 0.8333 | 0.2083 | 589.79 | 589.79 | 592.5 | 0.5 | 135.0 | 492.5 | 0.0 | -283.75 | 0.2143 |
| BASE_PHASE_CLOSE | E7 | 253 | 0.9091 | 0.3597 | 956.34 | 1174.53 | 525.0 | 0.2451 | 30.0 | 505.0 | 0.0 | 4591.75 | 0.0 |
| MHD_STRUCT_0.20ATR | E7 | 253 | 0.9051 | 0.3597 | 953.62 | 1171.2 | 525.0 | 0.2451 | 42.5 | 667.5 | 0.0 | 4591.75 | 0.0 |

The rule changes nothing that matters: D-030 breach rate stays **0.000** everywhere (the agreement filter had already bought that), win rate moves by at most -0.004, and the weekly p10 gets *worse* in E4 and E6. There is no risk-side case for adoption either — there is no risk left to buy.

## The prop law, and the one-contract question

* **No exit before 30 minutes**, enforced in code: `MIN_HOLD_SEC = 1800`, `_check_holds` refuses the whole stage on any breach, and the ranked table re-asserts it against the baseline's own floor. Every rule's minimum hold in the census is >= 1800s except where the PHASE CLOSE itself arrives earlier — those seats show the identical hold on the phase-close baseline, so no rule shortens any hold below the law.

* Median holds under the priced rules run **0.6-5.3 hours** against a baseline of **3.5-5.3 hours**. The 0.6-hour floor belongs to `MHD_FLOW15_LOOSE`, the degenerate form that fires on 99% of trades and is also the census's worst performer; every rule that fires selectively holds for hours. Nothing here is a scalp, and nothing here can become one.

* **The partial-bank family needs at least 2 contracts.** You cannot sell half a contract. Its rows are the two-contract-equivalent and even so they are KILLED (pooled -$56/session at +$1,200, -$82 at +$900). The sizing question does not need to be answered, because the answer does not pay.

## Receipts

* `verify_baseline`: the phase-close contract replayed off these paths reproduces the committed matrix certificate `cert_close_usd` for all 1,028 seats, max |diff| **3.0e-11**.

* The 0.70/0.80 books reproduce `CONFIDENCE_AGREEMENT.tsv` seat-for-seat (E3 51/29, E4 214/148, E5 362/216, E6 49/24, E7 352/253).

* Paths are `m2_delay._leg` imported and called on `assemble.load_session`; seats are `newobj.replay_delayed`; the risk panel is `risk_panel.panel_rows` verbatim.

* The seat set is held FIXED across rules. Earlier exits free occupancy, so re-seating could only ADD trades; not counting them is the conservative choice.

## What would change this answer

1. A **wider wall**. Every finding here is conditional on the $900 wall having already truncated the loss tail. On a wider wall the disqualification family has something to cut.

2. **More than one contract.** Partial banking is the only family whose failure is partly a sizing artefact.

3. **A better entry book.** The exit layer's whole clairvoyant headroom is $250-570/session; entries are $750-1,450 short. The bar is reached from the entry side or not at all.


**Adoption of any rule in this census remains the user's (D-029). The lane's own recommendation is to adopt none: the phase-close + $900-wall contract is already the right exit for this book.**


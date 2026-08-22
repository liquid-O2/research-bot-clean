# Lane Mechanics B digest — big/valid trades vs re-entries and losing starts

Lane: mechanics B (subagent, 2026-08-22). Source PDFs in `/workspace/artifacts/cache/book_pdfs_20260822/`,
every page read visually: `refill-effect (1).pdf` 24/24 · `only-trade-big-trades (1).pdf` 19/19 ·
`stop-re-entering.pdf` 17/17 · `anatomy-of-a-losing-start (1).pdf` 12/12. Page refs = PDF page numbers.

All four are one house (Sires / Ethos Order Flow, NQ/MNQ). The refill paper is the quantitative anchor;
the other three are the discretionary grammar that the paper's feature set formalizes.

---

## R1. GRADED-TOUCH SELECTION (the measured confirmation model)
- **Source**: refill-effect p3, p8-9, p23.
- **SETUP**: a *zone* = price area where a burst of large aggressive market orders traded ("sixty, eighty, a hundred contracts hitting in seconds", p5). Candidate = price returning to the zone later (a *touch*). 41,152 touch events, 235 sessions, 199M ticks, NQ/MNQ Dec 24–Nov 25 (p8).
- **CONFIRMATION SIGNAL**: not a tape event — a pre-touch feature grade. ~20 features in 4 families (p8): **Memory** (held earlier this session; prior-day defence), **Construction** (number & size of aggressive prints; zone width), **Location** (value-area edges, session extremes, distance from open), **Flow & state** (delta into the touch, approach speed, balance vs imbalance). Selection flips the sign: fade-everything −0.285R; model-selected +0.143R OOS (p3, p9).
- **Exact numbers**: base hold rate 42% (p8); graded worst→best decile holds 25%→63% (p9, p23); AUC 0.63 vs scrambled-label placebo 0.51 (only 0.2% of shuffles match, p16); **memory+location families do almost all the work; raw order-flow alone AUC 0.54** (p9). Rotating folds mean R +0.14..+0.22, win 63–67%, AUC 0.61–0.64 per slice (p16).
- **TIMING**: features are all known *before* the touch resolves (p6); grading is at touch arrival, entry rests during the flush (see R2).
- **PASS / NO-TRADE**: low-graded touches (bottom decile holds 25%); Q4-style compressed-volatility regime — "Q4, the most recent slice, lost money at every parameter setting we tried. The edge is regime-dependent: weakest when volatility compressed" (p14).
- **FEATURE MAPPING**: Memory → needs per-level touch-history state; disc_level_z* covers reaction-at-level but a "this zone held earlier this session / prior day" ledger is likely a GAP (named). Construction → disc_evt_* (attack/lift bursts + sizes); per-print size distribution partial at 1s aggregation. Location → disc_auction_*/disc_prior_*/disc_ib_*. Flow & state → w{15..1800}_* signed flow + approach displacement; balance-vs-imbalance state → disc_auction_*.
- **VERBATIM**: "Only 42% of touches hold. Fading every touch ... loses −0.285R per trade after costs." (p8). "Aggression *builds* the level, but it is the level's memory that predicts the next touch." (p9).

## R2. THE REFILL FLUSH (post-touch timing/flush structure — the execution edge)
- **Source**: refill-effect p10-12, p15, p23.
- **SETUP**: a graded zone touch (R1) in progress.
- **CONFIRMATION SIGNAL**: order-book sequence **wall → flush → refill** (p10 figure): (1) resting defender orders stacked in the zone; (2) aggressive orders hit the wall, price *dips inside the zone*; (3) fresh orders replace the filled ones before the aggressors break through; price bounces. The trade is "to be one of those replacing orders" — the entry IS the confirmation-side fill. **The defence does not happen at the front edge of the zone. It happens inside it** (p10).
- **Key measurement**: "around a genuine defended level, the median eventual winner first dips **18 ticks past the touch** before it works" (p10, p23). This is why touch-chasing loses: same signals, same engine, resting-limit-inside entries 68.8% win / PF 1.80 / +$2,112 vs market-order-at-touch 27.2% / 0.81 / −$405 (p11). Resting fills 64 trades vs 312 for market "precisely because it demands the flush that defines the setup" (p11).
- **TIMING**: flush depth median 18 ticks past touch; deployed order rests **12 ticks inside the level** and is **cancelled after 30 minutes** if unfilled (p12) → the whole confirmation window is ≤30 min after touch. Trade horizon: stop 32 ticks, target 96 ticks (3:1), one position at a time (p12); engine line: `rest_min=30 variant=3 entry_in=12 t_minutes=30 sl_ticks=32 tp_ticks=96` (p15).
- **ENTRY TRIGGER + INVALIDATION**: limit 12 ticks inside zone; stop 32 ticks (≈ beyond the zone: idea wrong); target 96; cancel-if-untouched 30 min. OOS record: +0.143R/trade, PF 1.19, +78R over 542 trades / 79 untouched sessions, ~6.8 trades/day, ~30% win with +3R winners, worst DD −16.6R, 11/16 held-out weeks positive (p12-13). Independent engine year: 223 trades, 58.7%, PF 1.45, +$3,803, ≈+0.07R/trade with stricter fills (p14).
- **PASS / NO-TRADE**: compressed-vol regime (Q4); −4R day (stop trading: +14 pts pass rate at every size, p21).
- **FEATURE MAPPING**: flush = short-window adverse displacement past a level → disc_level_z* + w15/w60 displacement; refill = disc_evt_* reloads + disc_quote_* rebuild after depletion; wall-pull fake = disc_evt_* pulls + disc_quote_* depletion. The 18-tick dip is directly computable from our per-second mid path relative to the candidate level.
- **BEYOND-BOOK**: the paper's robustness list (p16) is itself a confirmation-methodology spec: scrambled-label placebo, reverse split, rotating folds, 100-config parameter plateau (rank corr 0.92), "mechanism, not a pattern: ... the profit lives exactly where the mechanism says it must, on the passive side of the level, and dies when you chase."

## R3. FOUR-STAGE ABSORPTION CONFIRMATION (the state machine)
- **Source**: stop-re-entering p10 (stages), p3 (glossary), p12 (thresholds), p14 (checklist).
- **SETUP**: aggression hitting a level at a location where the HTF says the other side should be in control.
- **CONFIRMATION SIGNAL** (ordered stages; "failed absorption and confirmed absorption look identical at the moment most people enter. The difference only exists in time", p10):
  1. **Initial defense** — aggression hits the level, volume above average, price holds. NOT confirmed; "can be temporary liquidity that gets pulled and stops you instantly."
  2. **Replenishment** — the level refreshes as it keeps getting hit, maintained or growing size. **Minimum filter: three ticks of replenishment; one or two is the classic fake-out zone** (p10; glossary p3: "Three ticks or more is the minimum worth trusting").
  3. **Exhaustion** — aggressor volume declining, delta turns against them.
  4. **Lift-off** — the absorber flips passive→aggressive and price accelerates away. "That move is the reward, and it's the confirmation the first three stages were real."
- **Numbers**: "absorption fails roughly **27%** of the time when there's no pacing confirmation behind it ... Wait for replenishment and the failure rate drops sharply" (p10, own-records figure, flagged as such p16).
- **TIMING**: stages resolve over "the next few bars" after the print (p9); entry must sit **within a tick or two of the confirmation, not six to eight ticks late** (p13-14) — "A delayed reward system means probably no reward system" (p13). Reward = **two upticks minimum (two to four)** after buy aggression (p12).
- **ENTRY TRIGGER + INVALIDATION**: enter on the aggression that follows exhaustion — "Passive absorption is the setup; aggression is the trigger" (p12). Stop under the absorption (p12 caption).
- **PASS / NO-TRADE**: stage 1 alone; 1–2 tick replenishment; delta not agreeing; any of the three gates guessed → "the answer is no trade yet. Waiting is also an answer, and it's free" (p11).
- **FEATURE MAPPING**: stage 1 → disc_level_z* (defense) + disc_evt_* attacks + disc_tclock/vclock (above-average pace); stage 2 → disc_evt_* reloads / disc_quote_* rebuild (three-tick replenishment is a countable reload run); stage 3 → declining attack intensity (disc_evt_* rate) + w15/w60 delta sign flip; stage 4 → own-side disc_evt_* lifts + immediate displacement. Full four-stage sequencing = composable from our stream; the *pacing/resiliency* notion (p16: refill speed as "a real, measurable, and variable property") suggests a refill-latency feature — partial GAP.
- **VERBATIM**: "My minimum filter is three ticks of replenishment; one or two is the classic fake-out zone." (p10). "From my own data collection: absorption fails roughly 27% of the time when there's no pacing confirmation behind it." (p10).

## R4. THREE-STEP GATE: LOCATION → REWARD-VS-RESULT → DELTA
- **Source**: stop-re-entering p6-9, p14.
- **SETUP**: any candidate entry or re-entry, DOM/footprint/bubbles alike.
- **CONFIRMATION SIGNAL** (in order, all three): (1) **Location** — where price sits in the HTF auction decides "who you give leniency to"; carries the other two ("Without step one they filter noise", p6). (2) **Reward vs result** — your side acts and the market pays them: upticks after buy aggression / downticks after sell that *stick*. "Effort alone is not the signal. Effort is what the losing side produces on the way to being absorbed" (p7). (3) **Delta filter** — delta agrees with your side; opposite side thickening while the losing side thins: "Doubles and triples where your side acts, singles where the losers used to be. When both happen at your level, the filter is passed. When neither happens, there is no trade" (p9).
- **TIMING**: checked before every entry AND before every re-entry, from zero (p14).
- **PASS / NO-TRADE**: middle of a balance ("neither side has an argument, and every wick looks like absorption because nothing has context", p6); CVD trending against; needing to guess any step.
- **FEATURE MAPPING**: location → disc_auction_*/disc_prior_*/disc_ib_*; reward-vs-result → evt followed by same-direction displacement within seconds (disc_evt_* × w15_* conjunction); delta filter → w{60..300}_* signed flow + CVD-vs-session-median (computable from cumulative signed volume); thicken/thin digit read → per-print size distribution — partial/GAP at 1s aggregation (named).
- **VERBATIM**: "Effort is what the losing side shows. Reward is what the winning side gets. Enter on reward." (p7).

## R5. TRAPPED-DELTA-PRINT REVERSAL
- **Source**: stop-re-entering p9 (figure + caption).
- **SETUP**: outsized delta print(s) at the session/range highs — "a crowd of buyers acted there, and price paid them nothing" — price cannot leave the area. Those buyers are "inventory waiting to be liquidated."
- **CONFIRMATION SIGNAL**: **price breaks below the print zone** (confirming the trap) **with CVD rolling over its median behind it** (figure-only detail: the short triggers on the break of the zone that *contains* the prints, not at the prints).
- **TIMING**: "the next few bars tell you whether they were rewarded or trapped, and that's the only part you trade" (p9).
- **ENTRY TRIGGER + INVALIDATION**: short below the print zone; invalidation = price re-accepting above the prints (they were rewarded after all).
- **PASS / NO-TRADE**: print rewarded (price leaves upward) → no trade.
- **FEATURE MAPPING**: outsized delta print → disc_evt_* large attack/lift cluster; "price can't leave" → small displacement per unit flow (absorption ratio, w60_*); break of zone → disc_level_z* cross; CVD median roll → running signed-volume vs session median. Computable.

## R6. ORIGIN-OF-THE-MOVE DRIVE (the A++ short-gamma trade)
- **Source**: only-trade-big-trades p6-9, p14, p18.
- **SETUP**: a **squeeze** = repeated aggression with no reward: buyers print aggression *inside candle bodies* (the version that normally means being paid) and price goes lower anyway, again and again → "multiple areas where buyers are not willing to price higher"; each failed attempt = trapped longs + untouched resting orders above (p6). The squeeze is fuel/context, NOT the trade (p6-7). HTF (see R7) must agree. Regime gate: **short gamma only** (p14).
- **CONFIRMATION SIGNAL** (ordered): (1) squeeze fails — but "entering on the failure is entering on the moment the previous attempt died" — explicitly NOT the entry (p7); (2) the drive: **price takes out the wicks above** — buyers now willing to pay higher, the thing they refused to do all squeeze; resistance flips to support; resting liquidity above converts and funds the move (p8); (3) below, price stalls at a **refill area** (where sellers previously failed and reload); **buyers absorbing that refill instead of breaking down through it is the confirmation** (p8); (4) entry on the **retest** of the break, not the break: "At the retest, the level you are trading has already been defended once" (p9). Early = "prefiring the trade ... firing on the expectation of confirmation rather than the confirmation" (p9).
- **TIMING**: retest comes after the break or never — "Some of these move without giving one back, and you miss those. He accepts that trade explicitly" (p9). Frequency: A++ "once or twice a week, if that", "maybe even twice a month" — a handful/month at most (p14).
- **ENTRY TRIGGER + INVALIDATION**: long the retest of the flipped level; demonstrated bracket 87.25 pts target vs 18 pts stop, R:R 4.85 (p11, drawn not filled); stop below the defended flip/refill area.
- **PASS / NO-TRADE**: long-gamma/balance regime — "In balance, the squeeze failing is not a precursor to a drive. It is just the top of the range doing what the top of a range does" (p14); CVD sitting against the entry timeframe (p18); no retest → let it go (p18).
- **FEATURE MAPPING**: squeeze = repeated disc_evt_* one-side bursts with non-positive same-direction displacement (effort/reward conjunction over w60..w600); wick take-out → disc_level_z* / rolling-high cross; refill-hold below → R3 stages at the lower level; retest → second approach to flipped level (disc_level_z*). Gamma regime → UNKNOWN (no options-positioning observable in our stream; named gap). "Body vs wick" print location → approximate via price-at-print vs bar range from per-second path — partial.
- **BEYOND-BOOK (figure-only)**: p7-8 figures show the OFM level drawn at the *top* of the squeeze cluster, the green target box starting only above the taken-out wicks, and CVD curling up from below its median *before* the retest entry — CVD turn precedes the retest.
- **VERBATIM**: "People think origin of the move is just you're entering on the failure of the squeeze. No, that's not true." (p7). "When buyers absorb that refill instead of breaking down through it, you have the confirmation." (p8).

## R7. HTF PERMISSION: FAILED AUCTION AT A MINOR VOLUME NODE
- **Source**: only-trade-big-trades p10-11; anatomy p3 (glossary).
- **SETUP**: daily profile read, in order: current auction balancing; price came out of balance; the support in play is a **minor volume node at the extreme of that balance** ("minor volume nodes ... tend to give clean rejections and they tend to start trends", p10); **below the node there is no volume** — "no participation, so there is nothing underneath to hold price if it goes there ... above the node there is structure, below it there is nothing" (p10). Bigger frame: yearly composite as support, balance bulk with VWAP median through it (p10).
- **CONFIRMATION SIGNAL**: price hits the prior node/prior balance and **rejects there instead of accepting into it** — "a really, really clean failed auction long" (p11). Both halves must agree: LTF "buyers just took control off the origin of the move", HTF "rejecting away from a level it should reject from" — "Neither read is doing the work alone" (p11). Alignment grants **leniency**: "you know who to give the benefit of the doubt to when the order flow gets messy ... Without it, every wick is a coin flip" (p11).
- **FEATURE MAPPING**: minor node / value edges / balance state → disc_auction_* + disc_prior_*; thin-volume shelf below → profile-derived — partial (depends on our profile features); yearly composite → UNKNOWN (multi-year composite not in stream; named gap); rejection-vs-acceptance at prior value → disc_level_z* + dwell-time.

## R8. BALANCE-DAY FADE (the trade for the other 80%)
- **Source**: only-trade-big-trades p14-15, p18.
- **SETUP**: long-gamma / balanced regime — "80 percent of the time the market is in balance. 80 percent of the time you are in a long gamma environment" (p14). An extreme where aggression **failed to get paid**: buyers absorbed at the top of the range (p15).
- **CONFIRMATION SIGNAL**: price comes back to that area of absorption and those buyers are **still not being rewarded**; price turns lower. Enter on the trigger at the test back in. Key inversion: "you no longer need your own side to be rewarded ... In balance, sell pressure and sell imbalances get absorbed passively, and passive absorption is exactly what carries price in a balanced market" (p15) — the passive move that is a warning in trend regime (R9) is the mechanism here.
- **TIMING**: on the retest of the failed extreme (second visit); no squeeze prerequisite — "waiting for a squeeze that a balanced market has no reason to produce" is the error (p15).
- **ENTRY TRIGGER + INVALIDATION**: enter test-back-in at the failed extreme; **target back to where the other side last had control**; demonstrated bracket 33 pts target vs 9 pts stop, R:R 3.67 (p15). Rare balance-day bonus: real aggression finally arriving into a balanced session gives a disproportionate leg, ~4–5R chart-read (p16) — same trade held longer "because aggression showed up to justify it."
- **PASS / NO-TRADE**: short-gamma/trend regime (this trade inverts); extreme where aggression WAS paid.
- **FEATURE MAPPING**: failed-extreme memory → level-keyed effort-without-reward history (disc_evt_* + displacement at prior extreme; needs level memory — same GAP as R1 memory family); balance state → disc_auction_*/disc_ib_*; retest → disc_level_z*.
- **VERBATIM**: "An extreme, with the aggression there having failed to get paid. I am entering the test back into that area, targeting where the other side last had control." (p18 checklist).

## R9. PASSIVE-MOVE PASS (winning and still wrong)
- **Source**: only-trade-big-trades p13, p18.
- **SETUP**: in a trade (or candidate) moving your way with **no aggression on your side anywhere in the move** — "No effort on your side at all, just an absence of sellers."
- **SIGNAL/RULE**: entirely passive moves "are normally short term swings rather than the start of anything" (p13). Required sequence, order mattering: "First the opposition's aggression fails, so they are exhausted, trapped or absorbed. Then your side arrives aggressively. Opposition failing on its own is only half of it, and half is what most people trade" (p13).
- **PASS / NO-TRADE**: do not treat a passive drift as trend-start; do not add/size it (p18: "Is my side actually being rewarded, or is this move entirely passive?").
- **FEATURE MAPPING**: displacement with near-zero own-side disc_evt_* intensity over the move window (w60..w600 flow-vs-displacement ratio). Computable — a direct "passivity of the move" feature.

## R10. IMBALANCE × AGGRESSION CONFLUENCE
- **Source**: only-trade-big-trades p5, p18.
- **SETUP**: footprint imbalance (≥350% one-sided at a single price, his threshold) printing at the **same price** as same-side aggression bubbles: "the sellers there were both large and one sided, and ... willing to keep hitting into worse prices to get filled" — size-done-not-price behavior marks the level (p5).
- **CONFIRMATION SIGNAL**: none at print time — mark the level, **wait for price to come back and retest it rather than chasing the print** (p5). Aggression settings behind the bubbles: NQ min 30 / max 60 contracts on a 40-range chart, instrument-specific ("from my data collection", p3).
- **PASS**: an imbalance alone, or a bubble alone — "It tells you something happened, not what happens next" (p5); "An imbalance only interests me where it sits at the same price as aggression" (p18).
- **FEATURE MAPPING**: per-price bid/ask imbalance ratio at print resolution → UNKNOWN at our 1s aggregation unless footprint-grade data exists (named gap); large-print clustering → disc_evt_*.

## R11. RE-ENTRY LAW: PRICE MUST RETURN TO THE LEVEL
- **Source**: anatomy p7; stop-re-entering p14-15.
- **SETUP**: just stopped out of a planned trade at a level.
- **RULE**: "Let us see if we come back down. That is the only time I look for a re-entry" (anatomy p7). "Price has to come back to the level. Not near it, and not on a different level that looks similar. If it does not return, there is no trade, and the loss just stands" (p7). And the checklist version: "If this is a re-entry, it passes every box above from zero, not on the strength of how close it already got" (stop-re-entering p14). Why re-entries fail: break-even effect + realization effect — "the first trade was a read, the second was a hope, and everything after that was the break-even effect picking trades for you" (stop-re-entering p5).
- **RISK FRAME**: daily stop −4R honored mechanically — worth ~**+14 points of evaluation pass rate at every size tested, "the single largest lever in the whole study. Bigger than anything entry-side"** (stop-re-entering p15, citing refill p21); "a trader honoring the daily stop never sees re-entry five" (p15).
- **FEATURE MAPPING**: re-entry eligibility = price back inside the original band (disc_level_z* containment) + full gate recompute (R3/R4 from zero). Computable.

---

## CASES (session walkthroughs / dissected clips)

### C1. Anatomy of a losing start — NQ, 23 Jul 2026, 9 trades (anatomy p1, p5-9, p11)
- Shape: 5 losses −$945, 4 winners +$1,445, net +$500; win rate 44%; worst point −$480 after the first four trades; trades at 10:13/14/15/17/24/25/27/30/31/32 — the whole session ≈20 minutes (p1, p5-6).
- Setup: pre-written thesis with **no direction** — "You will never have a bias in your thesis. You just want areas of reactions" (p4); objective named (prior minor HVN), failure condition named ("overall structure was still lower, so the bullish objective could easily fail", p4).
- Sequence: buyers defending a shelf where they'd held before; entry with **stop just below where they were holding**; spiked out twice in 2 minutes (10:14, 10:15): "I want to see buyers hold. We do have buyers holding. I stop there. I got stopped very fast. I re-enter here, I am in again. Okay, I got stopped twice now" (p6). Third attempt (10:17, +) after price came back into the band; then a 7-minute wait (10:17→10:24) while price was away from the level — "the two stops in a row did not turn into four. The level was not offering anything, so there was nothing to take, and the next trade waited until price came back" (p7).
- Grading of the winners: stop by structure, target by HTF debt, ratio checked not chosen (p9): long 35 ticks stop vs 188 ticks target (5.37:1, p8); short 15 ticks vs 211 (14.07:1, "not the normal case ... happens when the level is unusually precise, which is rare", p9). "The stop is not tight because tight stops are good. It is 35 ticks because that is where the idea is wrong" (p8). "My winners are always much larger than my losses, because I cut them as fast as I can" (p8).
- Session risk frame (p11): one contract; daily objective ~$500 then stop even if the read is still good; max daily loss = half the objective; move to break-even when the reason weakens (not at fixed ticks); trail behind protected highs/lows (swings already defended once).
- Rejections: no trade while price is away from the marked level; no fresh entries after objective.

### C2. Correct entry, dissected (stop-re-entering p12)
Sequence at a low: sellers came in fast, buyers barely printed → no knife-catch (stage 1 only). Then in order: sellers' **double-digit prints thinned to singles** (exhaustion you can see); buyers **answered with triple digits** (conviction you can count); **CVD held** buying pressure; then aggression: **two upticks (minimum, two to four) = reward system** → entry on the aggression, stop under the absorption, reward already paying. "Notice what the entry did not require: prediction, courage, or a feeling about the low."

### C3. Wrong entry, dissected (stop-re-entering p13)
Reversal long in the **middle of a double distribution**, fading a trend (location fail); tape fully red into entry, sell aggression being rewarded (reward fail); buyer at entry printed a single digit; CVD trending against (delta fail); entry **six to eight ticks above the absorption** — "far too delayed. A delayed reward system means probably no reward system." Price retested the old sell aggression above, rejected instantly, stop went. "Every one of those failures was visible before the fill."

### C4. Prefired long into working sellers (only-trade-big-trades p12)
At the premature entry: sell aggression + sell imbalance at the same prices, repeated sellers stacked above, price pushing lower with aggression behind it, **CVD extremely bearish and below its own median** — "across that whole dealing range down, sellers were in control." Avoid specifically: the entry "was pointing into everything that was working at that moment"; the objection is win-rate/variance, not direction (p12).

### C5. Level tested twice, then buyers take control (refill-effect p7 figure; stop-re-entering p7)
Real NQ session: level built early, tested twice (first touch + sharp sell-off back into it); both times "the sellers get nothing: price holds, not breaks. Right after the second test, buyers build a small base (green) just above the level and take control" (p7 caption — figure-only detail: the green base forms *above* the zone, and entry is with the trend resumption, not at the zone edge). Cross-ref: "the level gets tested twice, sellers get nothing both times, and only after the second test do buyers take control. Entering on the first touch is, on the numbers, usually just early. Re-entering after it fails is paying twice for being early" (stop-re-entering p7).

---

## TIMING TABLE (confirmation → typical delay after formation)

| Confirmation | Delay after candidate/setup formation | Source |
|---|---|---|
| Refill flush depth | median winner dips 18 ticks past the touch before working | refill p10, p23 |
| Refill fill window | resting order 12 ticks inside; cancel if unfilled after 30 min | refill p12, p15 |
| Refill trade horizon | 32-tick stop / 96-tick target, ~30% win, +3R winners | refill p12-13 |
| Absorption stage 2 (replenishment) | ≥3 ticks of replenishment while being hit; 1–2 = fake-out | stop-re p10 |
| Absorption stages 2–4 | resolve over "the next few bars" after the print | stop-re p9-10 |
| Reward system | 2 upticks minimum (2–4) after own-side aggression | stop-re p12 |
| Entry proximity to confirmation | within 1–2 ticks of it; 6–8 ticks late = no reward system | stop-re p13-14 |
| Origin-of-move entry | on the retest of the break (after wick take-out + refill hold); retest may never come | otbt p8-9 |
| Second-test pattern | control changes only after the 2nd failed test of the level | refill p7; stop-re p7 |
| Re-entry eligibility | only when price is back inside the level's band; observed gap 2–7 min between attempts | anatomy p6-7 |
| Balance fade | on the test back into the failed extreme (second visit) | otbt p15 |
| A++ frequency | once–twice/week at best; ~handful/month | otbt p14 |

Note: the house states no seconds-denominated delay anywhere; timing is expressed in ticks-past-level, bars, replenishment counts, and returns-to-level. The one hard clock is the 30-minute unfilled-order cancel (refill p12). This is consistent with the ruling's "confirmation may come later than 5 min."

## PASS-RULE LIST
1. Fading every touch loses (−0.285R, 42% hold): no ungraded level trades (refill p8).
2. Bottom-graded touches hold 25% — pass (refill p9).
3. Compressed-volatility regime: edge weakest; Q4 lost at every setting (refill p14).
4. Never chase with market orders at the touch: 27.2% / PF 0.81 (refill p11).
5. Stage-1-only absorption (no replenishment) = 27% failure zone; 1–2 tick replenishment = fake-out (stop-re p10).
6. Any of location / reward / delta guessed → no trade; waiting is free (stop-re p11).
7. Both sides absorbed at range extremes → nobody in control → wait for the break (otbt p4).
8. Imbalance without same-price aggression → information only (otbt p5, p18).
9. Squeeze failure alone is not an entry (otbt p7).
10. No retest → let the trade go (otbt p9, p18).
11. Origin-of-move trade in long-gamma/balance → pass (the ~80% case) (otbt p14).
12. Entirely passive move in your favor → not a trend start; don't size it (otbt p13, p18).
13. Entry >2 ticks late (6–8 ticks past confirmation) → pass (stop-re p13-14).
14. CVD against the entry timeframe → pass (otbt p12, p18).
15. Re-entry unless price returns to the exact level AND the checklist passes from zero → pass (anatomy p7; stop-re p14).
16. Below −4R on the day → no trade, re-entry or otherwise (+14 pts pass rate, largest single lever) (refill p21; stop-re p15).
17. Daily objective reached → stop, even with a good read (anatomy p11).

## NAMED GAPS (observables our stream may lack)
- Per-level touch-history memory (held earlier this session / prior-day defence) — the single most predictive family (refill p9); needs a level-keyed ledger, not a windowed feature.
- Footprint per-price imbalance ratio (350% threshold) at print resolution (otbt p5).
- Per-print size digits (singles/doubles/triples thinning/thickening) if 1s aggregation drops the print-size distribution (stop-re p9, p12).
- Gamma regime / dealer positioning (otbt p14) — not derivable from our tape.
- Yearly composite volume profile (otbt p10) — multi-year history outside our windows.
- Refill pacing/latency ("how fast a level's depth actually refills after getting hit, as a real, measurable, and variable property", stop-re p16) — partially derivable from disc_quote_* rebuild timing.

Terminal state: **success** — all assigned pages read (24 + 19 + 17 + 12 = 72/72), digest complete.

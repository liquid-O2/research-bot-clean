# Lane digest — mechanics A (2026-08-22)

PDFs read visually, every page: `your-mistakes-with-absorption (1).pdf` (14/14), `trapped-buyers-one-retest.pdf` (13/13), `whos-in-control.pdf` (12/12), `reading-delta.pdf` (11/11), `origin-of-the-move (1).pdf` (19/19). 69 pages total.

Sources cited as (pdf-shortname, p N). Shortnames: ABS, TRAP, WIC, DELTA, OFM.

---

## 1. REWARD-SYSTEM-3TICK (ABS p3-4, p13)
- **SETUP**: absorption printed at a level being faded (reversal scenario only). Candidate = the absorption print itself.
- **CONFIRMATION SIGNAL**: price moves in trade direction within 3 ticks of the absorption print ("replenished"). Without it ~27% of absorptions fail (presenter's own estimate, p3, disclaimed p14). Figure p4 (figure-only detail): level drawn as a horizontal red box; green circles at first touch AND at the later retest; T&S/SOT panel shows red prints then green prints flipping; CVD pane below with rising median — entry side and CVD side agree.
- **TIMING**: stated in price distance (3 ticks), not time — effectively the first seconds/bars after the print.
- **ENTRY + INVALIDATION**: do not enter on the print; enter after replenishment confirms (see #5 for the retest entry). Unconfirmed absorption = treated as nothing "whatever it looked like on the print" (p4).
- **PASS**: no 3-tick replenishment; fading side being refreshed on tape (see #2); using absorption to catch continuation.
- **FEATURE MAPPING**: post-candidate displacement sign/magnitude = w15_*/w60_*; replenishment events = disc_evt_* (lifts/attacks after the print). Exact "within 3 ticks" tick-path granularity: partial at per-second resolution.
- **VERBATIM**: "Price needs to move in your direction within three ticks of the absorption for it to count as replenished. Miss that window and the absorption is treated as unconfirmed" (p4). "roughly 27 percent of all absorptions fail without what he calls a reward system, a three tick replenishment in your direction within three ticks of the absorption printing" (p3).

## 2. TS-REFRESH-CHECK (ABS p4, p9, p13)
- **SETUP**: absorption reversal candidate live; direction chosen.
- **CONFIRMATION SIGNAL**: time & sales / speed of tape shows the OPPOSING side is NOT being refreshed. Anti-signal: the side you fade refreshing + defenders stepping in instantly = that side is winning, stand down. At the entry retest: "a decent amount of refresh orders in time and sales, visible on the DOM or the footprint too" on YOUR side (p9).
- **TIMING**: read live across the seconds of the retest.
- **PASS**: opposing side refreshing/defending.
- **FEATURE MAPPING**: disc_evt_reload*/pull*, disc_quote_* depletion/rebuild, disc_tclock/vclock for tape speed.
- **VERBATIM**: "wait for one more retest with a decent amount of refresh orders in time and sales, visible on the DOM or the footprint too, before taking the trade" (p9).

## 3. CVD-MEDIAN-SIDE (ABS p5, p13)
- **SETUP**: any absorption-fade candidate.
- **CONFIRMATION SIGNAL**: price on the correct side of the CVD median for the intended direction. Failure template: uptrend, price above CVD median, falls off and TESTS the median without breaking → uptrend intact → shorts on absorption prints into that test fail (reward system never confirms).
- **TIMING**: state check at decision time.
- **PASS**: fighting the CVD-median side; using absorption for continuation.
- **FEATURE MAPPING**: session-cumulative signed flow vs its median — not a stored feature; approximable by chaining w1800_* flow; UNKNOWN as an exact CVD-median line. Named gap.
- **VERBATIM**: "Remember, absorption, you only use it logically in reversal type of scenarios. You're not using it to try to catch a continuation of a move." (p5).

## 4. LOCATION-GATE (ABS p6-7, p13)
- **SETUP**: pre-condition on every absorption signal.
- **CONFIRMATION SIGNAL**: signal only counts at a real, fixed extreme: shelf, ledge, low volume node, minor volume node, previous-day VAH/VAL. NOT near POC, not inside balance, and current-day VAH/VAL are lagging (they recalculate as the day develops) — treat with caution. Figure p6 (figure-only detail): identical swing-reversal shapes inside value hand-labeled "THIS IS NOT ABS" purely because of location near POC.
- **TIMING**: pre-condition, before the print matters.
- **PASS**: at/near POC = filter out entirely regardless of print quality (ABS p10); inside balance; level still being written.
- **FEATURE MAPPING**: disc_prior_* (prev-day VAH/VAL/POC), disc_auction_* (value edges, balance), disc_ib_*. Shelf/ledge/LVN/MVN detection: UNKNOWN unless a profile-node feature exists — named gap.
- **VERBATIM**: "This absorption is at a real extreme (shelf, ledge, low volume node, minor volume node), not near POC or inside balance." (p13 checklist).

## 5. SPONGE-SEQUENCE (ABS p8-9, p13)
- **SETUP**: the full absorption definition as an ordered sequence at a valid location.
- **CONFIRMATION SIGNAL**, in order: (1) aggressive effort into the level; (2) passive wall soaks it (bubble of aggressive prints at the wall); (3) NO reward — price fails to hold the push; (4) opposite-side aggression arrives (a second energy source, "not just an absence of buyers but active selling"); (5) ENTRY on one more retest of the reward system with refresh orders on your side (see #2). Entry is on the retest, NOT on the wall.
- **TIMING**: multi-step; steps 1-4 over the bars following the push, entry at the subsequent retest — minutes scale.
- **ENTRY + INVALIDATION**: enter at retest; the whole read is void if effort gets rewarded (price holds the push).
- **PASS**: no second-side aggression (absence of one side only); effort rewarded.
- **FEATURE MAPPING**: effort = disc_evt_attack/lift bursts + w15_* flow; wall = disc_quote_* rebuild at level; no-reward = displacement ≈ 0 vs flow (effort/result divergence, w60_*); reversal aggression = signed disc_evt_* flip; retest = disc_level_z*.
- **VERBATIM**: "I can point to the aggressive effort, then the passive wall that absorbed it, in that order... A second, opposite aggression has shown up, not just an absence of the first side... I'm entering on the retest of the reward system, not on the wall itself." (p13 checklist).

## 6. DELTA-SPIKE-CONTROL-FLIP (ABS p10-11, p13)
- **SETUP**: price at a value-area extreme (VAH or VAL).
- **CONFIRMATION SIGNAL**: a high Delta spike of buyers at the extreme = the moment opposition loses control; passively absorbed by the other side → rejection. Same tell both directions: at VAH the buyer spike is absorbed by sellers → rejects lower; at VAL the mirrored spike marks buyers regaining control → rejects up into balance. The wall must trace back to an actual Delta spike where control changed hands. Figure p11 (figure-only detail): delta-profile spikes sit exactly at VAH/VAL rows; both hand-annotated "High delta spike of buyers (Opposition losing control) being abs passively by sellers".
- **TIMING**: fastest of the four checks — "visible at the moment control changes hands, which is earlier in the sequence than the price reaction that eventually follows it" (p11).
- **PASS**: cannot trace the wall to a Delta spike; spike sits at POC.
- **FEATURE MAPPING**: w15_*/w60_* signed-flow extreme + disc_level_z* at disc_auction_* edge. Delta-BY-PRICE profile (spike at a specific price row) is UNKNOWN in our stream — named gap.

## 7. FAILED-AUCTION-ODDS (ABS p12-13)
- **SETUP**: price out of balance below VAL (or above VAH) of a real, previously established balance.
- **CONFIRMATION SIGNAL**: none by itself — it is the permission structure: roughly 72-80% of the time price comes back into balance (presenter's own range, kept as a range because he corrected himself mid-sentence; disclaimed p14). Combine with #6 for the trigger.
- **TIMING**: session scale.
- **PASS**: treating the statistic as the trade signal.
- **FEATURE MAPPING**: disc_auction_* value edges + subsequent w{300..1800}_* displacement back toward value.

## 8. ARRIVAL-SPEED-READ (WIC p3-4, p11)
- **SETUP**: price approaching a balance extreme; first filter before any level/retest logic.
- **CONFIRMATION SIGNAL**: HOW price arrives. Aggressive, fast push in = that side wants it, expect the extreme defended. Slow grind/drift in = no real interest, expect the extreme broken and the opposition to push price back through the whole range. "The extreme by itself decides nothing" (p3).
- **TIMING**: read over the approach (minutes).
- **PASS**: assuming rejection or acceptance from the extreme alone.
- **FEATURE MAPPING**: displacement rate into level = w{60,300,900}_* + disc_tclock/vclock; level proximity = disc_auction_*/disc_level_z*.
- **VERBATIM**: "There really is no way of knowing. Some of the ways I like to understand it is the aggression." (p3). "Reached aggressively, it's a level to expect defended. Reached slowly, it's a level to expect broken." (p4).

## 9. BREAKOUT-RETEST-CONTINUE (WIC p5, p8, p11)
- **SETUP**: a previous (finished) balance; you missed the moment control was decided.
- **CONFIRMATION SIGNAL**: sequence — price breaks the balance low, comes back up for a GENUINE retest, then continues lower. That full sequence confirms sellers in control; the break alone confirms nothing. Symmetric flip: if sellers can't push through on the retest, read flips to buyers (they absorb, drive price back up).
- **TIMING**: break → retest is bars-to-tens-of-minutes on the session charts shown (p8 figure).
- **ENTRY + INVALIDATION**: short valid only after break + held retest; failed retest = flip the read, do not force it.
- **PASS**: trend that fails to break the prior low and comes back = buyers in control, no short.
- **FEATURE MAPPING**: disc_prior_*/disc_auction_* level + disc_level_z* defense/reaction + w-window displacement sign sequence (down, up-to-level, down).
- **VERBATIM**: "A short only becomes valid once price breaks that low, comes back up for a genuine retest, and then continues lower from there, that sequence is what confirms sellers are still in control, not the break by itself." (p5).

## 10. LTF-CONFIRMATION-DROP (WIC p9-11)
- **SETUP**: price at an HTF extreme but the HTF read is mute (no clear buying or selling).
- **CONFIRMATION SIGNAL**: drop to the 15-minute (his default). Confirmation there = (a) price unable to break lower, (b) buyers visibly defending, (c) aggressive selling on Delta with NO reaction lower — sellers pushing and not getting paid, (d) a planned retest where sellers fail to assert control → buyers take over. "The higher timeframe extreme meant nothing on its own until the lower timeframe supplied the confirmation" (p9).
- **TIMING**: 15-minute bars — tens of minutes after reaching the extreme.
- **PASS**: HTF chop where neither side holds a push = explicitly no trade (see CASE-WIC).
- **FEATURE MAPPING**: aggressive-selling-no-result = signed w300_/w900_ flow vs ≈0 displacement (effort/result divergence); defense = disc_level_z*; UNKNOWN: none — this maps well.
- **VERBATIM**: "even when the higher timeframe gives you a reaction, you need to confirm it... whether the lower timeframe is actually showing you that price wants to go the direction the higher timeframe suggested... It's all about alignment." (p10).

## 11. PROTECTED-LOW-PARTIAL (DELTA p3-5, p10) — management confirmation
- **SETUP**: long is on; Delta profile shows clear buy-aggression imbalance at a recent low (sellers there trapped); price forms a small balance and escapes it; the low stops being retested → "protected low". Only confirmed lows / finished auctions (figure p4 carries this handwritten: "ONLY DO THIS METHOD WITH CONFIRMED LOWS / FINISHED AUCTIONS" — figure-only detail).
- **CONFIRMATION SIGNAL**: each new protected low = last point where trapped sellers could still logically defend. Partial below the micro balance, specifically below the sellers who defended it; trail stop behind each successive protected low.
- **TIMING**: as each low confirms (price stops coming back to it).
- **ENTRY TRIGGER + INVALIDATION**: not an entry — a partial/trail rule. Break of the highest-Delta protected low = trade traversing to the stop; accept the drawdown, do not fight; "You can always re-enter" (p5). Never jump straight to breakeven ("probably the worst thing you can do for your EV", p3).
- **FEATURE MAPPING**: swing-low identity + retest cessation = disc_level_z* + candidate bookkeeping; delta imbalance at the low = w-window flow at formation; delta-by-price again UNKNOWN.

## 12. HIGHEST-DELTA-PRINT (DELTA p6-7, p10)
- **SETUP**: buying (or selling) aggression printing on a wick — the textbook absorption fade most beginners take.
- **CONFIRMATION SIGNAL**: check where the HIGHEST point of the session's Delta profile sits, not the most recent print. If the highest print belongs to the side opposite your fade, the read flips: that side defended quickly, was rewarded, and price is more likely to continue their way. "He calls the highest point on the Delta profile a delta print, and treats it as the single most load-bearing piece of information on the chart: whichever side produced it is the side that was rewarded" (p7). On the real ticket (p7 figure, figure-only detail): short entered exactly at the highest sell-aggression print row; stop above it and target below both sit on drawn levels, not fixed distances; trapped buyers show as a "sell bubble" after entry.
- **TIMING**: state check at decision time; the print predates the wick you're reading.
- **PASS**: highest Delta point contradicts the wick you were about to fade → default to the Delta print side (p10 checklist).
- **FEATURE MAPPING**: running max of |signed flow| by price row — delta-by-price profile, UNKNOWN in our stream. Named gap (same gap as #6/#11).

## 13. DELTA-PRINT-AT-VP-EXTREME (DELTA p9-10)
- **SETUP**: dealing range with its own VP; a low volume node or minor volume node extreme drawn from it.
- **CONFIRMATION SIGNAL**: a large Delta print sitting right AT that LVN/MVN extreme → repeatable clean intra-wick reactions: price tags the level and rejects, repeatedly, at both top and bottom of the same micro balance. Check the level has produced MORE than one wick reaction before trusting it (p10 checklist). "By his own account rarely discussed elsewhere" (p9).
- **TIMING**: reactions recur across the life of the zone; entry at a tag of the zone.
- **PASS**: pairing the print with a random price instead of a real VP extreme; only one reaction so far.
- **FEATURE MAPPING**: repeated-defense count at a level = disc_level_z* history; LVN/MVN = named gap (see #4); large print = disc_evt_* size threshold.

## 14. REFILL-CONCEPT (DELTA p8; OFM throughout)
- **SETUP**: a side that had result once at an area.
- **CONFIRMATION SIGNAL**: if the setup repeats, that side tends to have result again; the opposing side gets trapped/exhausted/absorbed; state flips from "buyers have no result" to "sellers do". (The 98% pass-rate figure mentioned p8 belongs to a separate video, explicitly not this document.)
- **FEATURE MAPPING**: level-history features — disc_level_z* defended-before counts. This is the same claim OFM p15 measures: memory + location carry the signal.

## 15. AGGRESSION-BUBBLE-LOCATION (OFM p2, p4)
- **SETUP**: base vocabulary for all OFM reads. Aggression = market order crossing the spread ("accepting a worse price for immediacy"). Filter on NQ NY AM: minimum 30, maximum 60 contracts per print, adjusted with session volume (p4).
- **CONFIRMATION SIGNAL**: WHERE the bubble sits: inside the candle body = pushed price and got result (blatant aggression); on the wick = absorbed, level refused to move. "Same bubble, opposite meaning... nothing more than effort versus result" (p4).
- **FEATURE MAPPING**: disc_evt_* attacks/lifts with size filter; body-vs-wick position ≈ event price vs short-horizon subsequent displacement (w15_*). Exact bar-relative geometry: partial.

## 16. AGGRESSION-TESTING + MEMORY (OFM p4, p15-16)
- **SETUP**: price returning to an old area of aggression.
- **CONFIRMATION SIGNAL**: do those participants act again? If price cuts through and closes beyond it, they have no result and price usually continues to the next aggression area. Measured backbone (companion paper, 199M ticks / 235 sessions / 41,152 zone-touch events): raw order flow into the touch (delta, approach speed, imbalance) alone = AUC 0.54 (coin flip); the signal lives in MEMORY (has this zone been defended before) + LOCATION (real auction edge). Graded touches +0.143R OOS on 79 sessions vs −0.285R fading every touch; only 42% of touches hold unfiltered.
- **TIMING**: at the touch of the old zone.
- **PASS**: "A big print with no history and no location is not a graded setup yet" (p16). First touch of a fresh zone = weakest version; wait for the second test, or memory+construction+location agreeing.
- **FEATURE MAPPING**: disc_level_z* (defended-before, reaction history) + disc_auction_*/disc_prior_* (location). This is the book's strongest empirical endorsement of exactly our level-defense feature family.
- **VERBATIM**: "Aggression builds the level. The level's memory pays the trade." (p15).

## 17. SQUEEZE-REFILL-CLOCK (OFM p5)
- **SETUP**: repeated aggressive orders at the same area getting absorbed over and over — that cluster is the squeeze CATALYST (every failed order waits to reload).
- **CONFIRMATION SIGNAL**: the refill clock — "aggressive with no result becomes aggressive with result": absorbed buyers refill into the next attempt, more aggression joins at worse prices (itself proof of intent), the passive absorbers get eaten, price releases in one fast move. Speed of tape spikes on a real squeeze: "violent and quick, and you will not mistake it for drift" (p5). Figure p5 (figure-only detail): catalyst boxed around 3+ absorbed buy circles; plain-squeeze entry marked at the reload point, annotated "Protected by buyers (covered)"; handwritten "REFILL clock: AGGRESSIVE (NO RESULT) to AGGRESSIVE (WITH RESULT)".
- **TIMING**: release is fast (seconds); watch tape speed at the moment it goes.
- **FEATURE MAPPING**: repeated same-side disc_evt_* absorbed at one area + disc_tclock/vclock spike on release + w15_* displacement burst.

## 18. OFM-MAIN (OFM p3, p6-10)
- **SETUP**: HTF thesis aligned FIRST (mandatory — "I tested this feature set without the thesis behind it and it is basically a coin flip", p3/p18). A squeeze catalyst exists; the first squeeze attempt releases, punches into a wall, and FAILS — price rolls back through the catalyst area. The failure is the setup.
- **CONFIRMATION SIGNAL**: the failed squeeze located the real participation; refill clock still running. Buyers refill below (optional early entry, higher risk), price returns, the sellers get their turn at NO result, and the re-squeeze goes with refilled buyers behind it. Entry on the re-squeeze after price retests the failure area.
- **TIMING**: replay example (p11): rule "No short until price reclaims above the catalyst and fails again. Patience here is the trade." Multi-bar, minutes on the 40-range/scalp charts shown.
- **ENTRY + INVALIDATION**: stop below the aggression that built the entry (above, for shorts) — "below the aggression is the point where the read is simply wrong" (p6). Targets discretionary from the HTF thesis; 1R-3R working zone; trail above/below each new aggression pocket as price goes (p13); for longs, exit when buyers hit a wall and get fully absorbed — "that absorption is the exit" (p9).
- **PASS**: no thesis; inside a balance a squeeze can go either way (p11); first touch of fresh zone (p16); grade the touch first (has it held, was it built by size, where does it sit).
- **FEATURE MAPPING**: catalyst = clustered absorbed disc_evt_*; failure = displacement reversal through the cluster (w60/w300 sign flip); retest = disc_level_z*; re-squeeze = disc_evt_* burst + tclock spike.
- **VERBATIM**: "let the first squeeze fail, then enter on the re-squeeze" (p3). "The squeeze fails often. That is not the problem with the trade. That is the trade." (p3).

## 19. OFM-PASSIVE-VARIANT (OFM p14)
- **SETUP**: same as #18 but the squeeze fails with NO aggressive orders at the failure at all.
- **CONFIRMATION SIGNAL**: the speed of tape just DIES. "The absence of result is itself the signal, and it is the quieter, more common version of this model." Entry above the buyers, stop below the aggression, 1R-3R.
- **TIMING**: read off tape-speed decay at the failure point.
- **FEATURE MAPPING**: disc_tclock/vclock collapse + near-zero disc_evt_* at the level — directly computable. A negative-space confirmation our event features can express as absence.

## 20. STOP-LIMIT-TAG-IN (OFM p12)
- **SETUP**: OFM short entry at the retest area.
- **CONFIRMATION SIGNAL**: mechanical — the entry order is a stop-limit resting below the wick "so only aggressive continuation can tag it in. If sellers don't come with result, there is no fill and no trade. The order type is doing the filtering." Stop above the intermediate wick; stop-out is fine, re-entry sits right below, read unchanged.
- **BEYOND-BOOK**: this converts a tape confirmation into an order-mechanics confirmation — the fill itself is the last gate.
- **FEATURE MAPPING**: equivalent condition = post-retest continuation aggression through the trigger price (disc_evt_* + w15_ displacement).

## 21. 18-TICK-DIP / EXECUTION SIDE (OFM p15-17)
- **SETUP**: any zone-touch trade from #16/#18.
- **CONFIRMATION SIGNAL**: median eventual WINNER dips 18 ticks past the touch before it works — defense happens inside the zone, not at its front edge. Acting the instant price tags the level = "acting at the exact point where the data says the trade has not started yet" (p15). Research config: limit resting 12 ticks inside the zone, 32-tick stop. Identical signals: resting limit PF 1.80 (+$2,112 Q1) vs chasing with market orders PF 0.81 (−$405).
- **TIMING**: spatial delay (18 ticks adverse), not a clock delay — first-class for a formation+delta decision design: confirmation may arrive DURING adverse excursion.
- **FEATURE MAPPING**: computable directly from post-candidate price path; argues candidate evaluation windows must tolerate ~18 ticks MAE before scoring failure.

## 22. OFM honest-numbers boundary (OFM p17-18) — context, not a signal
42% of touches hold unfiltered; touch grading AUC 0.63 OOS (placebo 0.51); worst-to-best decile hold rate 25%→63%; −4R daily stop adds ~14 pts eval pass rate (largest single lever); worst quarter −$647 PF 0.76 disclosed. **"There is no mechanical entry signal in here"**: the entry rebuilt causally with hindsight stripped came back NEGATIVE, −0.16R to −0.54R OOS; what survives is a grading system for touches already found plus the execution rule (which side of the book to stand on). Thesis not optional (coin flip without). All figures historical simulation after modelled costs (p17 footer).

---

## CASES (session walkthroughs)

### CASE-TRAP-ASIA-SHORT (TRAP p3-11) — live Asia session, NQ/MNQ, closed +$501.50
Confirmation sequence in order, all checked BEFORE entry (p11: "every item on it was checked before the entry, not used to justify it afterward"):
1. Balance redrawn until it actually fit price (pre-session; ill-fitting balance = redraw, not force) (p3).
2. Price at the balance's upper extreme; AMT base case = return lower. "Price already approached this upper extreme, and clear AMT tells us we come back lower." (p3).
3. Delta at the highs: HEAVY BUYING read as trapped buyers, not strength — "A wall of buying at a high... can be the exact fuel a move lower needs once it starts" (p4). Figure p4 (figure-only detail): blue (buy) volume bars concentrated exactly at the recent high on the daily VP-with-Delta.
4. Two failed pushes at the SAME level in two separate prior sessions (NY AM and PM, hours apart): "One failed push is noise. Two failed pushes at the same price, in two different sessions, is the market telling you where it isn't willing to trade" (p5).
5. Intraday: price reached for the intraday upper extreme and came up short (p6).
6. Two waits, planned in advance: intraday breakout, THEN the retest of it. "The entry only existed because the market gave him the second wait, not just the first" (p6). If no retest: stand aside, look at the daily extreme instead.
7. Tape into the fill: aggressive selling printing INSIDE candle bodies, bar after bar, not one isolated print (p9) — this gates normal size vs "half-size on a hope".
- ENTRY: short at the retest — "we got that retest right here, we got it, and we shorted all the way down to right here" (p7). Levels marked before they mattered.
- TARGET: deliberately inside Asia's normal range; sessions like this run "almost 150 to 160 points" and he refused to need that; TP taken as soon as it printed, not trailed (p8). Sizing decision, not conviction.
- REJECTED: chasing the breakout without retest; holding for the full daily-range move (needs above-average session to pay).
- TIMING: HTF evidence hours old at entry (two NY sessions); breakout→retest→fill within the session, minutes scale; tape check in the seconds around the entry.
- FEATURE MAPPING: prior-session failed pushes = disc_level_z* + disc_prior_*; breakout-retest = displacement sign sequence + disc_level_z*; body-aggression bar-after-bar = persistent signed disc_evt_*/w60_ flow.

### CASE-WIC-SESSION (WIC p6-10) — HTF trapped buyers, one long stretch of PASS, then the retest short; later a rejected short at the HTF extreme
- HTF: aggressive push up that visibly FADED on Delta ("buyers were a lot stronger going in, then visibly faded. That fade is the tell", p6) → trapped buyers, forced selling fuels the move down, amplified vs a no-trap level → start looking for shorts only.
- PASS stretch: at the old balance neither side could hold a push (retest pushes back up, doesn't maintain, repeats) → "the market explicitly not giving you anything yet"; NO trades through the entire chop (p7).
- Confirmation: sellers aggressively broke the level AND got their retest; earlier trapped-buyers read + fresh confirmation lined up (p7-8). "The strongest trade wasn't the first place price looked tradeable, it was the retest that came after sellers had already proven they could take control once" (p10).
- Rejected short at the HTF upper extreme later: HTF mute → dropped to 15m → buyers defending, aggressive selling with no reaction lower, planned seller retest failed → buyers rampaged higher; no short taken (p9). See #10.

---

## TIMING TABLE

| Confirmation | Typical delay after candidate formation |
|---|---|
| REWARD-SYSTEM-3TICK (#1) | within 3 ticks of the print — first seconds/bars |
| DELTA-SPIKE-CONTROL-FLIP (#6) | at the moment control flips; EARLIER than the price reaction |
| TS-REFRESH-CHECK (#2) | live during the entry retest (seconds) |
| STOP-LIMIT-TAG-IN (#20) | at the fill; only continuation aggression triggers it |
| OFM release / tape spike (#17) | release is seconds ("violent and quick") |
| OFM-PASSIVE tape death (#19) | tape-speed decay at the failure point (seconds-minutes) |
| SPONGE-SEQUENCE entry retest (#5) | one more retest after reversal aggression — minutes |
| BREAKOUT-RETEST (#9, TRAP case) | break then retest — minutes to tens of minutes |
| OFM-MAIN reclaim+fail (#18) | multi-bar; "no short until price reclaims above the catalyst and fails again" |
| 18-TICK-DIP (#21) | spatial not temporal: median winner goes 18 ticks adverse first |
| LTF-CONFIRMATION-DROP (#10) | 15-minute bars — tens of minutes at the HTF extreme |
| PROTECTED-LOW (#11) | as each low confirms (price stops retesting it) |
| Prior-session failed pushes (TRAP #4) | hours old at entry — pre-existing evidence, not a wait |

Direct bearing on the ≥5-minute ruling: the book's confirmations span seconds (tape/Delta at the retest) to tens of minutes (LTF drop, breakout-retest), and one is spatial (18 ticks adverse) rather than temporal. The entry is never at candidate formation; it is at a LATER retest that the market may or may not supply ("two waits, not one").

## PASS-RULE LIST
1. No 3-tick replenishment after the absorption print → unconfirmed, no entry (ABS p4).
2. Fading side being refreshed on T&S / defenders stepping in instantly → stand down (ABS p4).
3. Wrong side of the CVD median for the direction → no entry (ABS p5, p13).
4. Absorption used to catch continuation (not a reversal) → never (ABS p5).
5. Print at/near POC or inside balance → filter out entirely, regardless of print quality (ABS p6, p10).
6. Current-day VAH/VAL as the extreme → caution/lagging; prefer prior-day or fixed nodes (ABS p7).
7. Effort was rewarded (price held the push) → no absorption read (ABS p8).
8. Only absence of one side, no opposite aggression arrived → hope, not a signal (ABS p8-9, p13).
9. Wall cannot be traced to a Delta spike where control changed hands → skip (ABS p13).
10. Extreme reached slowly/grinding → expect it broken; no fade (WIC p4).
11. Breakout without a held retest → nothing confirmed; failed retest → FLIP the read, don't force it (WIC p5, p11).
12. Chop where neither side holds a push → explicitly no trade, wait it out (WIC p7, p11).
13. HTF mute → no trade off HTF alone; require 15m confirmation (WIC p9, p11).
14. Level still forming / unfinished auction → protected-low logic forbidden (DELTA p4).
15. Highest Delta print contradicts the wick fade → default to the print side; no fade (DELTA p6, p10).
16. Delta print not at a real VP extreme, or level has only one wick reaction → skip (DELTA p10).
17. No breakout retest (only the breakout) → stand aside, look higher up (TRAP p6, p12).
18. Tape not showing aggression in your direction → don't size normally (TRAP p9, p12).
19. Target requires above-average session range → wrong target (TRAP p8, p12).
20. No HTF thesis → the whole OFM feature set is a coin flip; do not trade it (OFM p3, p18).
21. First touch of a fresh zone, no memory, no location → not a graded setup yet (OFM p16).
22. Acting the instant price tags the level → data says the trade hasn't started; rest inside the zone instead (OFM p15-16).
23. Squeeze inside a balance → can go either way; wait for the failure (OFM p11).

## BEYOND-BOOK (figures + implications the text does not name)
- Entry arrows in every figure sit at the RETEST after the confirming aggression, never at the wall/level itself (ABS p4, p9; OFM p5-6; TRAP p7). The pattern's text often under-states this; the drawings are unanimous.
- ABS p4 figure pairs three synchronized panes (price + level box, T&S/SOT strip, CVD with median) — the confirmation is a three-stream agreement check, which suggests a computable AND-gate: post-print displacement + tape-side flip + cumulative-flow side.
- OFM p6 schematic marks TWO entries with different risk classes (early refill vs main re-squeeze) — a two-tier confirmation ladder: same candidate, later confirmation = lower risk. Maps naturally to a formation+Delta staged decision.
- Order type as the final confirmation gate (OFM p12): only continuation aggression can fill the resting stop-limit — an entry mechanism that self-enforces confirmation with zero extra signal logic.
- Tape-speed DEATH as a confirmation (OFM p14): absence-of-events is a first-class signal our disc_tclock/vclock can express; the book's quieter, "more common" variant.
- 18-tick median adverse dip (OFM p15) implies confirmation windows must be defined in adverse-excursion space, not only clock space: a 5-minute wait that disqualifies on any adverse tick would discard the median winner.
- The book's own decomposition (OFM p15) says flow-at-the-touch alone is AUC 0.54 while level MEMORY + LOCATION carry the signal — an explicit endorsement of the disc_level_z* + disc_auction_*/disc_prior_* families over instantaneous delta features.
- Recurring named gap across ABS #6, DELTA #11-13: delta-BY-PRICE profile (which price row holds the session's max signed aggression). Our stream has time-window flows but no per-price delta histogram. Second named gap: profile-node structure (shelf/ledge/LVN/MVN) as location gates (ABS #4, DELTA #13).
- TRAP p10 caption warns the audio transcription of the P&L was garbled and the execution panel is the source of truth — a provenance note for anyone re-deriving the case numbers.

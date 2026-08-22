# Lane digest: session walkthroughs + trader autopsy (6 PDFs, 96 pages, all read visually)

PDFs read (pages read / total): ny-am-session (1).pdf 12/12 · 2345-funded-session (1).pdf 11/11 ·
18k-payout-session.pdf 15/15 · 10k-first-month (1).pdf 16/16 · average-unprofitable-trader.pdf 33/33 ·
emotion.pdf 9/9. All page refs below are (pdf, page).

---

## Confirmations / patterns

### REFILL-INTO-BUYERS
- Source: ny-am-session p4-5; refresh mechanics in 18k p11.
- SETUP: bottom of a range; sellers pushed lower and "gotten nothing for it"; buyers already known to be defending the level (HTF objective sits above).
- CONFIRMATION SIGNAL: sellers get absorbed at the low (aggressive selling, no downward result), then price refills straight back into the defending buyers. "That refill is the signal itself, not a guess at direction" (p4). Figure-only detail (p4): two small circles mark the exact prints where buyers stepped in and held; speed-of-tape histogram turns green as the refill starts; stop drawn just below the circles.
- TIMING: refill resolves within a few bars of the failed push (figure: 40-range/minute-scale bars; ~1-3 min after the absorption).
- ENTRY + INVALIDATION: long at/into the refill; stop just below the absorbed buyers; target = pre-marked HTF objective directly above.
- PASS: no HTF objective above = no reward, pass.
- FEATURE MAPPING: disc_evt_attacks (sell aggression) with no displacement (w15/w60 flow-vs-move divergence) + disc_evt_reloads/disc_quote_rebuild at the level + disc_level_z* reaction + disc_tclock uptick on the refill.
- VERBATIM: "sellers are being absorbed at the bottom, stop just below these buyers that are in control, targeting higher timeframe objective." (ny-am p4)

### REFRESH-CONSISTENCY (wall vs bluff)
- Source: 18k p11 (the mechanism chapter).
- SETUP: a resting order at a level of interest is being hit.
- CONFIRMATION SIGNAL: after a hit, the same size reappears at the same price (= one refresh). The read is on the 2nd and 3rd refresh: real level = "hit, replaced, hit, replaced" at roughly steady pace and steady size; bluff = each refresh a little smaller, pacing stretching out, until it stops coming back. Thinning precedes the level giving way.
- TIMING: 2-3 refresh cycles on the tape — seconds to a couple of minutes after the first test.
- ENTRY: with the refreshing side (defense confirmed) or against the thinning side (break imminent).
- PASS: "a single absorption print is never enough to act on by itself" (p11) — no consistency, no trade.
- FEATURE MAPPING: disc_evt_reloads sequence + disc_quote_rebuild/depletion; steadiness = low variance of per-refresh size and inter-refresh interval. Per-refresh size sequence at one price: UNKNOWN if our stream only aggregates reload counts per second (a named gap — the tell is the *trend across refreshes*, not the count).
- VERBATIM: "Sellers common, they're refreshing pretty strongly." / "these buyers are failing, they're refilling again, the refill concept with selling pressure coming in with aggressiveness." (18k p11)

### ORIGIN-OF-THE-MOVE (OFM) SECOND-DEFENSE RETEST
- Source: 18k p7-9; 2345 p5; ny-am (trade 3, "kg one retest trade") p8-9.
- SETUP: the price where control changed hands the first time (sellers absorbed there before / prior trapped side visible), marked "OFM" on the chart in advance.
- CONFIRMATION SIGNAL: price comes back and retests; enter only when the retest happens "with real selling participation behind it, not just a touch," and the defending side *refreshes at the level rather than thinning out*. First two attempts without participation are let go. In 2345 p5 the local flag was the 350%-divergence green box (below) sitting inside this HTF area.
- TIMING: third attempt at the level in the 18k session; figures span ~10+ minutes from first touch to the qualifying retest. Minutes-scale, not seconds.
- ENTRY + INVALIDATION: in on the qualifying retest; stop beyond the level; starting R:R may be <1 (0.69 in both ny-am T3 and 18k T3) and is taken anyway when the level behind is strong.
- PASS: retest without participation = let it go (twice, on camera).
- FEATURE MAPPING: disc_level_z* (repeat defense at level) + disc_evt_attacks direction into level + disc_evt_reloads (refreshing not thinning) + w60/w300 aggression at retest.
- VERBATIM: "A level does not become the trade because price touched it. It becomes the trade when the same side defends it a second time, with more conviction than the first." (18k p7) / "Now we need to go below, we retest it with a decent amount of aggression, I'm in." (18k p7)

### 350%-DIVERGENCE BOX (flag, not signal)
- Source: 2345 p5.
- SETUP: ATH environment, neutral objective; HTF level where the opposing side was already trapped (delta profile shows their aggression getting covered, not reversed).
- CONFIRMATION SIGNAL: a tool prints a green box when a 350 percent divergence between buying and selling aggression fires alongside a small imbalance — "passive absorption on one side and aggressive pressure on the other, at the same price." Explicitly "not a signal on its own." Entry taken as an OFM long "once sellers who had been rewarded at this level earlier failed to hold it a second time." Figure-only: magenta dots mark the trapped-seller prints; the grey box extends the level right; box prints mid-consolidation, entry is later.
- TIMING: flag is instant; the licensing condition (second failure to hold) arrives minutes later.
- FEATURE MAPPING: per-price buy-vs-sell aggression ratio ≈ disc_evt_attacks/lifts ratio in a short window at the level; exact per-price footprint imbalance (350% at one price): UNKNOWN in our per-second families — nearest is w15/w60 signed-flow extremes at a disc_level_z* level.
- VERBATIM: "a 350 percent divergence between buying and selling aggression alongside a small imbalance, printed automatically as a green box when it fires." (2345 p5)

### SESSION-CVD ABSORPTION (level being tested-and-passed)
- Source: 2345 p6 (the $18k-payout level).
- SETUP: a resistance area used and dumped from multiple times ("this level worked before" is where the read starts, not ends).
- CONFIRMATION SIGNAL: across the entire consolidation session, CVD dying while price holds or drifts up = passive limits at the level being consumed and reloaded, not defended free. "Price refusing to drop while the delta record shows no real selling pressure behind the level" = extreme absorption = level currently being tested and passed. Figure-only: annotation on live chart "price rising = high conviction of that session sellers had insane control"; CVD panel grinds down the whole session under flat/rising price.
- TIMING: session-scale (tens of minutes to hours) — the slowest confirmation in the set.
- FEATURE MAPPING: long-window flow-vs-displacement divergence: w900/w1800 signed flow steeply negative while displacement ≥ 0 at a disc_prior_*/disc_auction_* level. Weekly delta profile itself: UNKNOWN (beyond our 30-min max window).
- VERBATIM: "Price rising = high conviction that session sellers had insane control." (2345 p6)

### PROTECTED HIGH/LOW + TRAILING CONVEXITY (exit/hold discipline)
- Source: 18k p8-9, p12; ny-am p8-9; 2345 p7-8; 10k p9.
- SETUP: any running position from the entries above.
- SIGNAL: once price takes out the prior swing with enough aggression to *close* beyond it with real speed of tape, that swing becomes a "protected high/low": the stop moves there and is left alone. Each new qualifying swing creates the next. Mechanism (18k p12): a protected high is defended by *ordinary short covering* by the losing side (participants closing losing positions) — distinct from options dealer hedging, which says nothing about who is winning. Figure-only (18k p8-9): the resting target is also raised as the trail advances (+$775 locked/target $2,300 → +$1,240/target $2,645) — the text never states target-raising.
- TIMING: per-swing, minute-scale increments; R:R 0.69 entries became 1.83 (ny-am) and a 1.6k session (18k).
- PASS: "The stop only ever moves toward protecting what the trade has already made, never further into risk" (2345 p8). Normal breakeven "ruins your EV in a problem environment" (10k p9).
- FEATURE MAPPING: swing structure from price + disc_tclock/vclock at the break (real speed of tape); covering-vs-hedging attribution: UNKNOWN (no participant attribution in our stream).
- VERBATIM: "Once we go below this, it becomes again a protected high, in terms of micro mechanics I can trail further." (18k p8)

### EXHAUSTION-INTO-LEVEL FADE
- Source: ny-am p10-11; 18k p10.
- SETUP: pre-marked resistance; day objective already essentially met (this is a deliberately small last trade).
- CONFIRMATION SIGNAL: the move INTO the level is losing aggression candle by candle, not gaining — "the tell I was waiting on, not just fading a level because it's a level" (ny-am p10). 18k variant: "Buyers are being absorbed. I want these buys to be absorbed. They are, okay, I'm in" (18k p10) — buyers already in control get absorbed rather than defended at the level. Figure-only (ny-am p10): speed-of-tape bars shrink bar-by-bar into the level.
- TIMING: several bars of fading aggression into the level (~minutes).
- ENTRY + INVALIDATION: short at the level, risk deliberately small (~$100), stop above.
- PASS: never fade a level on arrival alone; fade only when the approach is decelerating.
- FEATURE MAPPING: w15..w300 aggression trend into a disc_level_z*/disc_prior_* level + disc_tclock deceleration; sequencing (each bar weaker) is computable.

### ABSORPTION 3-TICK CONFIRMATION RULE
- Source: average-unprofitable-trader p24, p28-29.
- SETUP: an absorption print at a level (aggressive order stopped passively).
- CONFIRMATION SIGNAL: require ≥3 ticks of aggression TOWARD the absorbed side before entering. Author's own collected stat: "absorption fails 27% of the time unless there's a 3-tick aggression toward the absorbed side" (p24). This is the book's only numeric confirmation threshold.
- TIMING: immediately after the absorption print (seconds).
- FEATURE MAPPING: directly computable — disc_evt_* absorption event + signed displacement ≥ 3 ticks in the absorbed side's direction within a short window (w15).
- VERBATIM: "An absorption entry needs 3-tick aggression toward the absorbed side. Without it, it fails 27% of the time." (avg p28 flow map)

### DOM READ: LOCATION → PACING → DIGITS (fixed order, after thesis)
- Source: avg p25-26.
- SETUP: any candidate; thesis already written.
- SIGNAL, in order: (1) Location — at the lower boundary of the volume profile price is at a discount, buyers should step in; "price seeks the POC and value 60 to 80% of the time"; decide who gets benefit of the doubt BEFORE reading the tape. (2) Pacing — effort vs reward: "a huge divergence of buyers over sellers while price stagnates, rotating in the same few ticks, is massive effort with no reward" = warning, whatever the imbalance says. (3) Digits — sellers refreshing from two/three-digit sizes down to singles = thinning; buyers stepping from two/three digits to four/five = building effort. "When the pacing then upticks, effort finally getting its reward, that's the entry" (p26).
- TIMING: pacing/digit sequence plays over seconds at the open ("you can't compute bid-ask maths fast enough, so read digit size").
- PASS: DOM does not confirm (any of the three) → no entry (flow map p28).
- FEATURE MAPPING: Location → disc_auction_*/disc_prior_*/disc_ib_*; Pacing → w15..w300 flow magnitude vs tick-range (effort-no-reward divergence) + disc_tclock uptick as the entry trigger; Digits → disc_quote_depletion/rebuild magnitude trend (exact displayed digit sizes UNKNOWN, but size-decay direction computable).
- VERBATIM: "If you don't understand where we are in the auction, you'll never be truly profitable on the DOM, on the footprint, on any other order-flow entry trigger." (avg p25)

### OPEN-ABOVE-VALUE BREAK-AND-RETEST (worked example, AMT-validated)
- Source: avg p21-22.
- SETUP: current day's TPO opens fully above yesterday's value (A period clear of prior VAH). Wait until ~10:00 for the day type to establish from profile shape.
- CONFIRMATION SIGNAL: value opening/building higher (buyers in control, sellers exhausted) → expect rejection off POC or prior VAH → price breaks the CURRENT day's VAH with aggressive buying imbalances doing the breaking → THE TEST: price comes back to those imbalances; if the buyers who broke the level defend them, that retest is the long. "If they fold, you have your answer, and it cost nothing."
- TIMING: day-type wait ≈ 30 min after open; retest arrives minutes after the break.
- ENTRY + INVALIDATION: long on the defended retest, off the volume profile; stop below the defended imbalances.
- PASS (load-bearing caveats, p21): still subject to time of day; still subject to what the DOM shows at the retest; still needs a decent HTF objective — "a clean break-and-retest into nothing is a clean entry into a losing trade. Thesis first, always. The entry is the last gate, never the first."
- FEATURE MAPPING: disc_prior_* (prior value), disc_ib_*, session clock, w60/w300 aggression at break and retest, disc_level_z* defense at the broken level. Directly computable end-to-end.

### PRE-FILE ENTRY (deliberate pre-confirmation buffer)
- Source: 18k p5-6.
- SETUP: session open at a thesis level, before anything confirms.
- SIGNAL: none — that is the point. A tiny position "to buy a small amount of buffer on the session cheaply, in case the real setup a few minutes later needed the room." Two of these lost (-$100, -$40) and the thesis was unchanged: "you pay the small, known price twice, and you do not change the thesis because of it" (p6).
- TIMING: t≈0 at candidate formation; the REAL entry (OFM retest) came minutes later.
- Relevance to us: the book itself prices unconfirmed entry at a small negative — direct support for a formation+delay decision design rather than entry-at-formation.

### HTF-OVERRIDE (the short he stopped taking)
- Source: 10k p13; also 10k p7-8 (what replaced it).
- SETUP: clean LOCAL order-flow short confirmation at a level.
- RULE: if a key demand level was just tested and sellers were absorbed there, the HTF bias is up and the short is not taken at all "regardless of how clean the local order flow looks." Figure-only (p13): three repeated short attempts fought a level that kept holding; that resistance had sat untouched two weeks; once it broke, everything below it stopped being a place to sell from.
- Replacement trades (p7-8): short off a pre-marked rejection area only when two independent reasons align (his level + a minor HVN); long on second tap with absorption (buyers stepping in and holding); both 1.5R fixed targets, stop above rejection high.
- FEATURE MAPPING: disc_level_z* absorption at HTF level as a *veto* on opposite-side candidates — a sign-conditional pass rule.

---

## CASES (session trades, in sequence)

| Case | Setup | Confirmation observed | Delay after formation | Result |
|---|---|---|---|---|
| ny-am T1 | range low, HTF objective above | sellers absorbed, refill into buyers | ~1-3 min (figure) | +$755 |
| ny-am T2 | level rejected sellers 2x, 3rd retest | none appeared (no buyers 3rd time) — entered anyway small | 3rd touch, tens of min into session | -$100, level held |
| ny-am T3 | kg1 retest, R:R 0.69 | aggressive buying right as level confirms | at level confirm | win, trailed 0.69→1.83 |
| ny-am T4 | pre-marked resistance, objective met | approach losing aggression candle-by-candle | several bars | +~$1,000 day close |
| 2345 T1 | microbalance in ATH push | strength through microbalance | minutes | R:R 5.59 plan, hit target |
| 2345 T2 | lower push, same microbalance read | same, opposite side | minutes | win, target capped by consistency rule |
| 18k T1 | thesis level at open | none (pre-file buffer) | 0 | -$100 |
| 18k T2 | same level | tape looked aggressive; buyers would not give level up | minutes | -$40 |
| 18k T3 | OFM level | 3rd attempt: below + retest with real aggression, sellers refreshing | ~10+ min from 1st touch | session winner (+1.6k running) |
| 18k T4 | buyers-in-control absorbed at level | "I want these buys to be absorbed. They are" | after T3 locked profit | closed day +$2,300/7 accts |
| 10k T1 | pre-marked rejection area + minor HVN | prior rejection at level (confluence of 2) | pre-planned level touch | win 1.5R |
| 10k T2 | second tap of same structure | absorption: buyers stepping in and holding | on the retap | win, ran past 1.5R |

REJECTED on camera: 18k T3's first two retests (no participation); 10k p13's entire short class (HTF veto); avg p21 the fold-at-retest case ("you have your answer, and it cost nothing"); 2345: no PM session the prior day (skipped a whole session, "$500 left on the table" accepted).

---

## TIMING TABLE (confirmation → typical delay after candidate formation)

| Confirmation | Delay |
|---|---|
| Absorption 3-tick aggression rule | seconds (w15-scale) |
| DOM digits/pacing uptick | seconds to ~1 min |
| Refresh consistency (2nd-3rd refresh) | seconds to ~2 min |
| Refill-into-buyers | ~1-3 min |
| Exhaustion-into-level (fading bars) | several bars, ~2-5 min |
| 350% box → second failure-to-hold | flag instant; license minutes later |
| OFM second-defense retest | minutes; 3rd attempt ~10+ min after first touch |
| Open-above-value retest | break minutes after 10:00 day-type wait; retest minutes after break |
| Session-CVD absorption | tens of minutes to whole session |

Direct support for the user ruling: the licensing confirmations here are dominated by the minutes band (retests, refresh cycles, second defenses), with one seconds-band filter (3-tick) and one session-band read. "≥5 minutes" is inside the observed range, and confirmation can indeed come later (OFM 3rd attempt, session CVD).

## PASS-RULE LIST
1. Single absorption print alone: never act (18k p11).
2. Absorption without 3-tick aggression toward absorbed side: 27% failure — require it (avg p24).
3. Retest without real participation ("just a touch"): let it go (18k p7).
4. Break-and-retest with no HTF objective behind it: pass — "clean entry into a losing trade" (avg p21).
5. Trade fights thesis/auction location (e.g. short at lower boundary where buyers should step in): stand down (avg p27, p30).
6. HTF veto: sellers absorbed at key demand ⇒ no shorts regardless of local confirmation (10k p13).
7. Never fade a level on arrival; require decelerating approach (ny-am p10).
8. Effort-no-reward pacing (big imbalance, price rotating few ticks): warning, wait for pacing uptick (avg p26).
9. ATH environment: no predicted target; wait for pullback, trade within the push only (2345 p4).
10. Setup not nameable as feature+regime: outside the box, no trade (avg p27).
11. Doesn't match the written one-sentence A+ setup: not a trade (emotion p7).
12. Session plan complete: done for the day even if setups continue (2345 p9); later trade sized only once an earlier one is no longer at risk (18k p10, p14).
13. Stop only ever moves toward protection, never further into risk (2345 p8); plain breakeven-on-instinct ruins EV (10k p9).

## BEYOND-BOOK (figure-implied / unnamed by the text)
- Resting target is trailed UP alongside the protected-high stop (18k p8-9 figures show target $2,300→$2,645) — a two-sided trail the text never states.
- The refresh-consistency tell is a *trend statistic* (per-refresh size and interval, 2-3 cycles) — suggests a computable "refresh-decay slope" feature; our per-second reload counts may under-resolve it (named gap).
- Speed-of-tape deceleration into a level (ny-am p10 figure) is a confirmation in its own right that the text only gestures at — bar-over-bar disc_tclock slope into disc_level_z*.
- Low starting R:R is treated as *information about the entry, not the trade* (18k p9) — implies confirmation quality and reward math are decoupled: strong-level confirmations license entries a static R:R gate would refuse.
- Pre-file entries price the unconfirmed state at a small known negative — the book's own evidence that formation-time entry is negative-EV and the edge lives in the delayed confirmation.
- Gamma regime / weekly delta print / VIX read (18k p4, emotion p7): UNKNOWN in our stream (no options data, no weekly-scale delta); named gaps.
- Covering-vs-dealer-hedging attribution (18k p12): UNKNOWN — no participant attribution; nearest proxy is passive buying at a level already tested-and-failed-to-break.

Terminal state: SUCCESS — all 6 assigned PDFs read page-by-page with the Read tool (96/96 pages), digest complete.

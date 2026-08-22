# ny-am-session (1).pdf — figure-first notes (12/12 pages)

Source: `/workspace/artifacts/cache/book_pdfs_20260822/ny-am-session (1).pdf`
Ethos Order Flow / Sires, How a Professional Trades the NY AM Open. All 12 pages read as images.

Four live trades, unedited, including the loss. NQ, ~1s / 40-range DeepCharts. Indicators named: CVD and speed of tape. "None of it is prediction. It's a read of what's actually happening at the price, and a reaction to it." (p3)

## Sequence (session grammar, then cases)

1. Location: where price sits in the higher-timeframe auction. Levels are grey horizontal bands marked before the trade, not invented on the print.
2. Absorption: who is defending that location.
3. Refresh and pacing: is that defense thickening or thinning.
4. Only then: entry / wait / pass. The refill (who won the fight for that price) is the signal, not a guess at direction.

Waiting is lawful. Trade 4 waits until the move into a pre-marked resistance loses steam. Trade 2's lesson is that two prior failures still do not force the third.

Exits, dollar P&L, six-account replication, trailing-convexity R:R expansion (p8–9 management half) are out of scope. The *entry* on trade 3 is in scope; the trail that turned 0.69 into 1.83 is not.

## Trade 1 — the refill (pp 4–5)

**Before (p4 figure).** NQ. Grey value/range bands. Price has sold down. At the bottom of the range a small white box; two small circles on it. Cyan arrow: "sellers absorbed at the bottom, no result for the push." Right-hand volume profile. Speed-of-tape histogram (pink then quiet). CVD in the lower pane, sold-off then turning. Green target ticket above, red stop just below the box.

Caption: "Sellers get absorbed at the bottom of the range here, the two small circles marking where buyers stepped in and held. The stop sits just below."

**Sequence:**
1. HTF location already exists (bottom of the range).
2. Sellers push. Absorbed. No result for the push.
3. Price refills straight back into the buyers defending that level.
4. That refill is the signal. Long. Stop just below those buyers. Target the HTF objective sitting directly above.

Verbatim: "sellers are being absorbed at the bottom, stop just below these buyers that are in control, targeting higher timeframe objective." (p4) "That refill is the signal itself, not a guess at direction. It's a read of who's actually winning the fight for that price." (p4)

**After (p5 figure).** Same box, zoomed out. Green arrow: "buyers regain control, the refill runs to $755." CVD now rising. The cleanest trade of the day in his words; three more still came.

Figure-only: entry sits *on* the absorption box after the failed sell push, not on the first sell print of the low. Circles mark the hold, not the probe.

## Trade 2 — the loss (pp 6–7)

**Before (p6 figure).** Cyan arrow: "third retest of the level, still no buyers stepping in." Grey bands. A thin white box at the retest. Speed of tape pink/red. CVD deeply red and falling. Green box left over from an earlier long.

**Sequence he took:**
1. Level had already rejected sellers twice. No buyers either time.
2. Third retest, still nothing.
3. Short, stop just above, "kind of low risk."

**After (p7 figure).** Red arrow: "stopped for -$100, the level held anyway." Price ticks up through the stop before the actual (later) move develops.

**Pass this case encodes:** two failures to get a result do not license the third as a short. "A level failing to hold twice doesn't guarantee it fails a third time." (p7) Absence of buyers on retest 3 looked like confirmation and was not. Waiting through the third test, or requiring a positive sell-side result (effort *and* reward) rather than mere absence, is the stricter form the loss argues for.

Figure-only: the stop is tight just above the white box; CVD is already washed out to the downside *before* the short — the tape is not showing fresh sell control at the level, it is showing an already-spent move. That is visible on the figure and the text does not name it.

## Trade 3 — entry at a confirmed level (pp 8–9)

**Before (p8 figure).** Cyan arrow: "entry goes in here at only R:R 0.69 on paper." Small green target, red stop. White/hollow buy-aggression bubbles at the level. Speed of tape turning green. CVD recovering off a low. Grey band as the location.

Caption: "Aggressive buying lines up right as the level confirms."

**Sequence (entry-side only):**
1. Location already marked (grey band).
2. Aggressive buying prints as the level confirms. Effort and reward on the buy side.
3. Enter there. The paper R:R being 0.69 is not a pass rule in this PDF — he takes it because the confirmation is there.

p9 is trailing convexity (stop walked, same entry now 1.83). Out of scope as a goal path. Keep only the quote that names the setup: "so this was a kg one retest trade with the trailing convexity, that's why I got out there." (p9) — **KG1 retest** is the location class.

Figure-only p9: "OFM" label on a purple horizontal to the left of the later structure. The p8 entry is *below* that OFM line, bouncing off the grey band with buy aggression. Do not collapse this into the OFM-drive sequence from the other PDF; this page names it a KG1 retest.

## Trade 4 — close the day (pp 10–11)

**Before (p10 figure).** Cyan arrow: "sellers exhausted right into the resistance level." Pre-marked grey resistance. Small red box at the stall. Speed of tape had been green, now quieter. CVD flattening / rolling over after a climb. Price stalling into the band, not accelerating through it.

**Sequence:**
1. Resistance marked out ahead of time. Objective for the day already basically in hand — he was "ready above the objective I wanted for today."
2. The move into the level is losing steam candle by candle, not gaining it. That is the tell. Not "fade because it is a level."
3. Sellers exhausted at the resistance. Short.

**After (p11 figure).** Red arrow: "this short closes the day, up a 1k." Small red box, ~$100 risk.

Pass: do not fade a pre-marked resistance on location alone. Require the loss of aggression into it.

## Session-level pass

- No HTF location → no trade. "Location tells you where price sits in the higher timeframe auction." (p3)
- Absorption without a refill (who won) → wait. The refill is the signal (trade 1).
- Third retest of a "failed" level without your side being rewarded → not a forced entry (trade 2).
- Fade-a-level-because-it-is-a-level → pass (trade 4). Need exhaustion / lost steam.
- Loss stays in the record. A clean read that fails is not a reason to skip the sequence next time, and not a reason to invent a new filter from one stop-out.

## Verbatim

- "Location tells you where price sits in the higher timeframe auction. Absorption tells you who's defending it. Refresh and pacing tell you whether that defense is thickening or thinning." (p3)
- "That refill is the signal itself, not a guess at direction." (p4)
- "A level failing to hold twice doesn't guarantee it fails a third time." (p7)
- "Aggressive buying lines up right as the level confirms." (p8)
- "The resistance level here had been marked out in advance, and the move into it was losing steam rather than accelerating, which is the tell I was waiting on, not just fading a level because it's a level." (p10)

## Feature mapping

- Location on HTF bands → `disc_auction_*` / `disc_prior_*`.
- Absorption at the box (trade 1 circles) → `disc_level_z*` defense + `disc_evt_*` failed attacks. Computable.
- Refill as the entry trigger → `disc_quote_*` rebuild / `disc_evt_reloads` after a failed push. **G4** if we need refill *pacing* as a property, not just a count.
- Speed of tape → `disc_tclock` / `disc_vclock`.
- CVD path (trade 2 already-spent, trade 4 roll-over) → **G10** session-cumulative CVD + running median. Named gap as a first-class feature; approximable by chaining long windows.
- KG1 retest (trade 3) → **G9**. External gamma. Named gap.
- Third-retest memory (trade 2) → **G7** level-memory ledger. Named gap. Without it we cannot ask "this level already rejected twice today."

## Pages

1 cover (Tradecopia +$6,050.55 / 4 trades 3W 1L net +$1,000 × 6 accounts — result, not a method), 2 contents, 3 grammar, 4–5 trade 1 refill, 6–7 trade 2 loss, 8–9 trade 3 (entry in; trail out of scope), 10–11 trade 4, 12 closer.

Pages-read 12/12. Terminal: success.

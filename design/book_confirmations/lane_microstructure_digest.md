# Lane digest — microstructure lesson series (Ether/Ethos "Sires" lessons 2-10)

Extraction only, per EXTRACTION_CONTRACT.md. PDFs read with the Read tool, every page seen
as an image: vp-lesson-2 (9/9), tpo-lesson-3 (10/10), vix-lesson-4 (10/10), dom-lesson-5
(8/8), dom-lesson-6 (8/8), dom-lesson-7 (8/8), fp-lesson-8 (8/8), fp-lesson-9 (8/8),
vwap-lesson-10 (9/9). 78 pages total. Page refs are PDF page numbers (printed page
numbers match PDF indices in all nine files).

The series' one-sentence method (vwap-lesson-10 p6): "VWAP gives the location, the
deviation extreme. CVD plus the ladder gives the confirmation. Location plus confirmation
is the whole method in one sentence." Every entry below follows that shape: a level from
profile/TPO/VWAP forms the candidate; DOM/footprint/delta events license the entry.

---

## C1. LADDER-ABSORPTION (DOM fake-break absorption)
- **Source**: dom-lesson-5 p6-7; dom-lesson-6 p3-6.
- **SETUP**: a pre-marked level — shelf, ledge, value edge, old high/low ("Never watch the
  DOM in a vacuum. Come to it with the shelf, the ledge or the value edge already marked",
  dom-5 p7). Retail attacks the level expecting the break.
- **CONFIRMATION SIGNAL**, in order: (1) fast tape arrives at the level — aggression
  committed (dom-5 p6); (2) heavy market orders hit the level but do NOT push price
  through it (dom-6 p3); (3) passive size at the level holds and reloads instead of
  vanishing (dom-6 p6 figure: highlighted bid row refuses to break and reloads while
  aggressive sellers hit it — figure-only detail: the defended row is drawn 2-3x wider
  than neighbors and stays widest across the event); (4) delta agrees: heavy delta INTO
  the level with no price progress = trapped aggressors (dom-6 p6). Then price rejects
  fast the other way (dom-6 p4).
- **TIMING**: the fight is live at the level — seconds while tape is fast; the read is
  made during the attack, not after. dom-6 p4: reset the DOM counts before price arrives
  so the read covers "only the fight at the level, not an hour of noise" — confirmation
  is measured on flow since the approach began.
- **ENTRY + INVALIDATION**: enter on the fast rejection ("If price rejects fast and moves
  your way instead, that was institutions absorbing the retail orders. That is the
  entry", dom-6 p4). DOM gives "tight entries with tiny stops" (dom-5 p7) — stop behind
  the absorbed level. Invalidation: level breaks with speed — "If it breaks, the speed
  carries the continuation" (dom-5 p6).
- **PASS / NO-TRADE**: absorption at a random price means nothing (dom-6 p8); spread
  widens = liquidity pulling, do not lean on the level, do not chase into the gap
  (dom-5 p6); aggression WITH movement is continuation, not absorption (dom-5 p7).
- **FEATURE MAPPING**: disc_evt_* attacks (aggression into level) + reloads (defence);
  disc_quote_* rebuild vs depletion at the touched level; disc_level_z* defense/reaction;
  disc_tclock/vclock for "fast tape"; short w{15..60}_* signed flow vs displacement for
  "heavy delta, no progress". Spread width as its own observable: UNKNOWN in our named
  families (gap). "Reset the counts at approach" maps to formation-anchored windows, not
  session-cumulative delta.
- **BEYOND-BOOK**: absorption "is not always one price. 300 buy orders can get eaten
  across 3 ticks. Watch the zone, not just the single tick" (dom-6 p4) — detection must
  aggregate a 2-3 tick zone around the level, not a single price row.
- **VERBATIM**: "Big market orders hitting your level that do not push price through it.
  The aggression arrives, the level eats it, price reverses. That is absorption, and it
  is one of the highest quality triggers on the ladder." (dom-6 p3). "The middle column
  is the truth, the aggressive prints. Limit orders are intentions, market orders are
  actions." (dom-6 p4).

## C2. ABSORPTION-VS-EXHAUSTION discriminator
- **Source**: dom-lesson-6 p7.
- **SETUP**: price stalls at a level after a push; both look like "no movement".
- **CONFIRMATION SIGNAL**: big volume with no movement = absorption (someone is there;
  reverses harder). Shrinking volume with no movement = exhaustion (nobody left; drifts —
  a pause or fade, not necessarily a hard reversal). Extreme form: stopping volume —
  "a single burst of huge volume that halts a trend dead... it often marks the turn."
- **TIMING**: read over the stall itself (the last push into the level).
- **ENTRY + INVALIDATION**: absorption licenses the reversal trade (C1); exhaustion only
  downgrades continuation — not a licensed reversal entry on its own.
- **PASS / NO-TRADE**: exhaustion is not the absorption trade; expect drift, not snap.
- **FEATURE MAPPING**: volume slope during stall = w{15..120}_* volume/flow decay vs
  disc_evt_* attack intensity; stopping volume = disc_vclock burst + zero displacement.
- **VERBATIM**: "Watch the volume as price stalls. Big volume with no movement is
  absorption, someone is there. Shrinking volume with no movement is exhaustion, nobody
  is left. Absorption reverses harder, exhaustion drifts." (dom-6 p7).

## C3. ICEBERG-RELOAD (hidden size defending a level)
- **Source**: dom-lesson-7 p3-4, p8.
- **SETUP**: a level under heavy attack that "keeps getting hit" so shorts/longs pile in
  expecting the break.
- **CONFIRMATION SIGNAL**, in order: (1) loads of orders hitting the bid or ask, stacking
  constantly, level refuses to give; (2) the reload: "Large volume being held, the
  visible size refreshing instead of dying"; (3) "Then wait for more participants to add
  on within 2 ticks" (dom-7 p4) — new passive joiners within 2 ticks of the defended
  price are part of the confirmation; (4) enter on the iceberg's side.
- **TIMING**: multiple visible-size refresh cycles plus the join — inherently longer than
  one touch; no fixed clock stated. The refresh-vs-prints check is per-event (seconds).
- **ENTRY + INVALIDATION**: "Bid absorbing and price holding confirms the long above the
  level. Offer absorbing and capping price confirms the short below it." (dom-7 p4).
  Invalidation: visible size dies without refreshing (reload stops).
- **PASS / NO-TRADE**: size that vanishes when hit is a spoof, not an iceberg (C4).
- **FEATURE MAPPING**: disc_evt_reloads is this observable directly; disc_quote_* rebuild
  at a fixed price while disc_evt_* attacks continue; disc_level_z* defense score. The
  "add on within 2 ticks" joiner detail: best-effort from disc_quote_* rebuild in
  adjacent price bins — if our quote features are top-of-book only, UNKNOWN (gap).
- **BEYOND-BOOK**: the discriminating filter is refresh rate AGAINST prints: "Real hidden
  size (an iceberg) refreshes as volume trades through it, you see the prints. Fake size
  (spoof, layer, flip) refreshes or vanishes with no prints at all." (dom-7 p7) — a
  computable ratio: refills conditioned on traded volume at that price.
- **VERBATIM**: "One level that keeps reloading while heavy volume trades into it is
  hidden institutional interest." (dom-7 p4). "an iceberg REPLENISHES as it trades, a
  spoof VANISHES before it trades. Reload is real, cancel is fake." (dom-7 p5).

## C4. SPOOF-FILTER (fake size veto)
- **Source**: dom-lesson-7 p5-7.
- **SETUP**: any large visible wall near the candidate level, momentum apparently
  building against or for the trade.
- **SIGNAL (veto, not entry)**: four signs — vanishing walls (disappear the moment market
  trades into them); the flicker ("appear and vanish repeatedly within seconds, without
  ever filling"); odd placement (far from normal resting levels, attention-bait amounts);
  fast cancels (instant cancellation when aggression nears). Variants: layering (ladder
  of fake orders at several prices; tell: "the whole stack pulls together the moment
  price approaches"), flipping (size jumps bid→ask and back "faster than any real order
  manager would work"; tell: no prints, only display flicker) (dom-7 p7).
- **TIMING**: sub-seconds-to-seconds cancel latency is itself the tell.
- **ENTRY**: none. Defensive routine: check the prints not the display; never chase
  spoofed momentum; re-enter consideration "only after genuine absorption appears or the
  fake orders are removed, with confirmation from real prints and sustained liquidity"
  (dom-7 p6).
- **PASS / NO-TRADE**: "If the size keeps changing but the tape is silent, it is a lie.
  Trade the prints, never the picture." (dom-7 p7).
- **FEATURE MAPPING**: disc_evt_pulls (cancel events) at/near the level; disc_quote_*
  depletion without matching disc_evt_* prints; flicker = pull/replace frequency —
  best-effort from evt pulls rate. Order-level cancel latency: UNKNOWN (we have
  per-second aggregates, not order lifecycles) — named gap.

## C5. STACKING-VS-PULLING (passive intent read)
- **Source**: dom-lesson-6 p5; dom-lesson-5 p7.
- **SETUP**: price approaching the level; passive side visible.
- **CONFIRMATION SIGNAL**: stacking (limit orders being added) with agreeing delta =
  intent; pulling (stacked orders removed before price trades there) = fluff, and a
  directional tell in itself: "Bids pulling while bid delta is positive means buyers just
  lost their support, price can drop. Asks pulling while ask delta is negative means
  sellers lost their pressure, price can rise." (dom-6 p5). "Stacked size that stays"
  is real defence; "Stacked size that vanishes as price approaches was never real."
  (dom-6 p6).
- **TIMING**: read on the approach, before price trades at the level.
- **ENTRY + INVALIDATION**: modifier on C1/C3 — stacking supports the hold trade, pulling
  vetoes it (or licenses the break continuation).
- **FEATURE MAPPING**: disc_evt_* reloads/pulls; disc_quote_* rebuild/depletion; sign
  cross with short-window signed flow (w15/w30) for the delta agreement.
- **VERBATIM**: "Stacking shows intent. Pulling shows fluff. Delta confirms who is
  actually aggressive." (dom-6 p5).

## C6. FOOTPRINT-ABSORPTION (candle-vs-delta disagreement)
- **Source**: fp-lesson-9 p3-4, p8.
- **SETUP**: price at a key level where traders get trapped: "old highs and lows, ledges,
  value edges" (fp-9 p4, step 1).
- **CONFIRMATION SIGNAL**: the candle and the delta disagree. "Bullish absorption: the
  candle is bullish but delta is negative, sellers are aggressive yet price still rises.
  Bearish absorption: the candle is bearish but delta is positive, buyers are aggressive
  yet price still falls." (fp-9 p4, step 3). Figure p3 (figure-only detail): 1-minute
  footprint columns, per-candle delta footer printing -496, -550, -674 on candles whose
  bodies hold or rise at the low — three consecutive disagreeing candles before the
  reversal leg; the imbalance highlights cluster at the candle extremes.
- **TIMING**: "The DOM shows absorption as it happens, the footprint proves it after the
  candle closes" (fp-9 p3) — footprint confirmation lands on candle close (1-minute
  chart in the book's figures), i.e. tens of seconds to minutes after the attack starts;
  the p3 figure spans 14:39-14:47 with the reversal ~3-4 candles after the first
  disagreement.
- **ENTRY + INVALIDATION**: "Trade with the institutions, against the trapped." (fp-9
  p4). Entry after the disagreement prints at the level; stop behind the absorbed
  extreme. The p4 figure's arrow (figure-only detail) sits at the close of the
  disagreement candle at the bottom-right of the trapped cluster, not at the level touch.
- **PASS / NO-TRADE**: agreement is not a signal — "The disagreement IS the signal.
  Agreement is just a trend." (fp-9 p8).
- **FEATURE MAPPING**: displacement sign (w-window return) vs signed flow sign
  (w{15..120}_*) crossed at disc_level_z* levels. Per-price bid/ask footprint detail
  inside the candle: best-effort; if our stream has only netted per-second flow, the
  diagonal per-price read is UNKNOWN (gap).

## C7. POC-FLIP (intracandle control change)
- **Source**: fp-lesson-9 p5.
- **SETUP**: at a key level, after/during absorption.
- **CONFIRMATION SIGNAL**: the candle's busiest price (candle POC) jumps from one extreme
  of the candle to the other. "POC low in the candle then flipping high means the
  business moved up with conviction. At a key level, a flip in your direction is
  confirmation the level is being defended." Figure p5 (figure-only detail): two ladders;
  left has the brightest row 2nd from bottom ("POC low, sellers in control"), right has
  it 2nd from top ("POC flips high, buyers take over") — the flip crosses most of the
  candle range, not one tick.
- **TIMING**: within a single candle's life or on the next candle (the figure shows one
  transition between adjacent snapshots).
- **ENTRY + INVALIDATION**: stack element, not standalone (see C9).
- **FEATURE MAPPING**: rolling volume-at-price over the formation window — best-effort
  from per-second price+volume (a windowed mode of traded price); no named disc_* family
  carries intracandle VAP directly (gap if per-second volume is not price-binned).
- **VERBATIM**: "A POC flip is that busiest price jumping to the other side of the
  candle. Control just changed hands." (fp-9 p5).

## C8. DELTA-DIVERGENCE + EXHAUSTION-PRINT
- **Source**: fp-lesson-9 p6; vwap-lesson-10 p6 (CVD version).
- **SETUP**: a trending move into/at the candidate level; fresh high or low being made.
- **CONFIRMATION SIGNAL**: two flavours. Regular divergence: "Price makes a new high or
  low but delta does not. The move has no aggressive fuel behind it... expect a
  reversal." Exhaustion print: "At the extreme, a huge delta bar prints and price refuses
  to extend. The last aggressive push got absorbed." Figure p6 (figure-only detail):
  price line grinding to a fresh high across ~3 swings while the CVD line falls the whole
  time — the divergence builds across multiple swings, not one bar.
- **TIMING**: exhaustion print: "The turn is usually one or two candles away." (fp-9 p6).
  Regular divergence: builds over several swings — minutes; consistent with confirmation
  arriving well after candidate formation.
- **ENTRY + INVALIDATION**: reversal expectation; stack element (C9). "When they
  disagree, believe the delta, the move without conviction is the one that fails."
- **PASS / NO-TRADE**: see C12 CVD breakout grading for the continuation-side veto.
- **FEATURE MAPPING**: new-extreme flag from price path vs signed-flow envelope across
  w{60..1800}_* windows; exhaustion print = disc_vclock burst + max signed-flow bar +
  zero forward displacement.

## C9. FULL-STACK (level → absorption → flip; the book's composite trigger)
- **Source**: fp-lesson-9 p7-8; dom-lesson-5 p7 (ladder version); vp-lesson-2 p7.
- **SETUP**: price reaches a marked level.
- **CONFIRMATION SIGNAL**: in sequence — "Price reaches your level, delta disagrees with
  the candle, then the POC flips your way. That sequence is the full confirmation
  stack." Graded: "One tell is interest, two is a trade. Absorption alone says someone is
  defending. Absorption plus the flip plus divergence says they are winning." (fp-9 p7).
  Ladder equivalent (dom-5 p7): bring level → watch aggression → watch passive
  (hold/reload/stack vs pull) → score with delta → execute small and precise.
- **TIMING**: sequential; each element per its own entry above. Nothing in the series
  binds the stack to a fixed clock — it completes when the third tell prints.
- **ENTRY + INVALIDATION**: execute when DOM and footprint agree: "Lesson 6's ladder
  reads plus this lesson's prints are the same event from two angles. When they agree,
  execute." (fp-9 p7).
- **FEATURE MAPPING**: conjunction of C1/C5 (event families) with C6/C7/C8 (window
  families) at disc_level_z*/disc_auction_*/disc_prior_* levels.

## C10. FOOTPRINT-IMBALANCE and STACKED-IMBALANCE zones
- **Source**: fp-lesson-8 p4-7.
- **SETUP**: any candle at or approaching a level; read is diagonal — "Compare the 56 ask
  to the 5 bid one tick below. Diagonal, not side by side." (fp-8 p4).
- **CONFIRMATION SIGNAL**: one side 3x-4x the diagonal opposite = flagged imbalance
  ("3x to 4x is the standard flag. Below that it is noise", fp-8 p5; figure p5
  highlights asks 220/410/512 against bids one tick lower). Two or three stacked in a
  row at a level = real pressure/zone; "Three or more imbalances in a row build an
  unfinished auction, the market tends to return and finish it." (fp-8 p6). Candle POC
  "behaves like a magnet on the retest" (fp-8 p6).
- **TIMING**: printed per candle; the zone acts on RETEST — a later-revisit magnet, not
  an immediate trigger.
- **ENTRY + INVALIDATION**: stacked buy imbalances = demand zone, "price often revisits
  it and holds"; stacked sell = supply zone, "price revisits it and caps" (fp-8 p6).
  Approach read: "A level hit by exhausted aggression behaves differently to one hit by
  fresh conviction." (fp-8 p7).
- **PASS / NO-TRADE**: single imbalance = noise (fp-8 p7); a number without a location is
  trivia (fp-8 p8).
- **FEATURE MAPPING**: needs per-price bid-vs-ask traded volume at one-tick offset —
  UNKNOWN if our stream lacks price-binned signed volume (named gap); zone-revisit logic
  maps to disc_prior_*/disc_level_z* once zones are marked.

## C11. VWAP-DEVIATION + ABSORPTION (location gate for reversion trades)
- **Source**: vwap-lesson-10 p3-4, p9.
- **SETUP**: price beyond the ±1 VWAP deviation band, ideally at ±2/±2.5 ("Run plus and
  minus 2 and 2.5, you can add 3 but price rarely touches it", vwap-10 p3). VWAP median
  read as "the POC of the session so far". Figure p3 (figure-only detail): hand-drawn
  circles sit on the -2 band touch, the median, and the +2 touch — the trades are drawn
  at band extremes back toward the median.
- **CONFIRMATION SIGNAL**: the two rules — "One: the trades worth taking live beyond the
  1 band and ideally at the 2, deal with at least the 1. Two: only trade VWAP extremes
  WITH absorption, never on the touch alone." (vwap-10 p4). Absorption per C1/C6.
- **TIMING**: the touch forms the candidate; absorption confirmation follows per C1/C6
  timing.
- **ENTRY + INVALIDATION**: reversion toward the median. Falling-knife veto: "If there is
  no confirmation, or the draw beyond the band is clearly still higher or lower, do not
  trade against it. Deviation is probability, not a wall." (vwap-10 p4).
- **PASS / NO-TRADE**: touch alone is not a trade (vwap-10 p9).
- **FEATURE MAPPING**: session VWAP + deviation bands computable from per-second
  price/volume; not a named disc_* family (buildable, but flag as unbuilt). Anchored
  VWAP (from swing or event, vwap-10 p7) needs anchor selection: UNKNOWN as an automated
  observable (gap). Confluence weighting (session+weekly+anchored converging) maps to
  level-stack counting at disc_prior_*.

## C12. CVD-BREAKOUT-GRADE and CVD-ABSORPTION-ZONE
- **Source**: vwap-lesson-10 p5-6.
- **SETUP**: any breakout of a level, or a stall at one.
- **CONFIRMATION SIGNAL**: "Real breakouts print rising CVD. Price breaking out on flat
  or falling CVD is likely a fakeout, low conviction dressed up as momentum." (step 2).
  Absorption zone: "Price stalling while CVD keeps climbing or falling means large
  players are quietly taking the opposite side. That standoff usually resolves
  violently." (step 3).
- **TIMING**: concurrent with the breakout bar(s)/stall; the standoff resolution is
  near-term but unclocked.
- **ENTRY + INVALIDATION**: grade every breakout before joining; fade-side entry from the
  absorption zone per C1/C6 stack.
- **PASS / NO-TRADE**: never chase a breakout whose CVD is flat/falling.
- **FEATURE MAPPING**: cumulative signed flow across w{60..1800}_* windows vs
  displacement; breakout flag from disc_prior_*/disc_ib_* level cross.

## C13. PROFILE-STRUCTURE candidates (shelves, ledges, HVN/LVN)
- **Source**: vp-lesson-2 p3-8.
- **SETUP-DEFINITION entry** (this lesson defines candidates, not confirmations): HVN =
  agreed business, price "gets drawn back to these shelves and slows down inside them";
  LVN = rejection, price "tends to react at these and traverse them quickly" (p3). Shelf
  = body of agreed business between the lines; ledge = the exact price where build-up
  starts/fade-away begins (p4). Ledges "were set by real business and they stay where
  they were set" — structure, not statistics, unlike drifting VAH/VAL/POC (p5). Naked
  POC = untested prior-session POC, "acts like a magnet... a ready made target list";
  composite HVN = heavyweight level (p6).
- **CONFIRMATION**: none from the profile itself — "A ledge on its own is a line. Watch
  the DOM and the footprint at the level: absorption, aggression, the tape picking a
  side. No confirmation, no trade, same rule as every level in this method." (p7).
- **PASS / NO-TRADE**: "Trade the ledge, not the middle of the shelf. Inside the shelf is
  rotation, chop and noise." (p7); lone levels last, stacked (confluent) levels first
  (p8).
- **FEATURE MAPPING**: disc_auction_* (value area), disc_prior_* (prior POC/VAH/VAL,
  naked POCs), disc_level_z* (reaction at marked levels). Ledge extraction from profile
  curvature: best-effort (gradient of volume-at-price); composite profiles across days:
  buildable from prior_* history.
- **VERBATIM**: "Structure first, confirmation second, execution last. The profile tells
  you where the trade lives, the tape tells you when to take it." (p7).

## C14. TPO references: SINGLE-PRINTS, EXCESS, POOR-EXTREMES, IB
- **Source**: tpo-lesson-3 p3-9.
- **SETUP-DEFINITION entry**: letters are 30-minute periods. Single print = one-period
  row, "a sharp one sided move that leaves imbalance behind it. The market tends to come
  back and fill it, like a magnet" — mark fresh singles as targets (p5). Excess = "two or
  more rows of the same letter print at the extreme" then rejection = FINISHED business —
  "Expect those extremes to hold on first test" (p6, p9). Poor high/low = weak rejection,
  "the extreme just stops, it never finishes" = unfinished, tends to be revisited (p7).
  On NQ poor extremes appear as a single TPO tail and are useful; on ES they are less
  reliable (p7, figure-adjacent cards).
- **IB READ** (p8): IB = first hour (A+B periods). Range extension beyond IB = one side
  took control, trending day. "IB holds all day": rotational day — "Fade the IB edges
  back toward the POC." "IB breaks early": "An early, one sided range extension points at
  a trend day. Do not fade it, the auction has already decided."
- **TIMING**: IB verdict available after the first hour; excess needs two 30-min periods
  at the extreme (up to ~60 min to form); singles/poor extremes act on later revisit.
- **CONFIRMATION**: profile is context only — "DOM and footprint decide the entry. The
  profile is context, never the trigger." (p9).
- **FEATURE MAPPING**: disc_ib_* (IB levels/breaks); disc_prior_* (prior POC/VAH/VAL,
  unfinished-business lists); single-print/excess/poor flags from intraday price-path
  history: best-effort, buildable; not present as named families (gap if absent).

## C15. VIX regime gates (session-level PASS layer)
- **Source**: vix-lesson-4 p3-9.
- **SETUP**: pre-open and intraday regime context. Expected daily move = VIX/sqrt(252)
  (p3 figure).
- **RULES**: VIX ~12.5: ES ~30-pt day, scalps only 3-5 pts ("Fishing for 10 point runners
  on a day like this is how the account bleeds", p4). VIX ~16: ~50-pt day, "sweet spot
  for structured R setups". VIX ~22: ~95-pt day, violent swings, no tiny stops, trail
  aggressively. Risk by regime (p5): above 20 widen stops to 3-4 pts; 15-18 "the best
  pocket... the 2 point stop, 10 point target days"; below 14 shrink to scalps or stay
  out; below 13 "Usually not worth fishing. Knowing there is no edge today IS the edge."
  Range completion (p5): once implied range is mostly done, expect mean reversion/chop.
  Intraday direction (p6): ES up+VIX down = continuation; ES up+VIX up = rally may fade;
  ES down+VIX up = don't catch the knife; flat/flat = chop, scalp or stand down. Rising
  VIX intraday = expect expansion away from value; falling = rotation, respect levels.
  Events (p7): pre-event VIX rising — don't over-fade, ignore the implied range; post
  vol-crush — back to fading rotations; the two traps are trading yesterday's regime.
  Curve (p8): backwardation = "cut size hard, widen everything... the auction is broken
  until the curve normalises"; rising VVIX = early warning the range is about to expand.
  Auction link (p9): balance+VIX dropping = fade value edges toward POC; balance+VIX
  rising = prepare for range break, don't lean on the walls; VIX dropping = size
  breakout attempts smaller ("they fail into rotation more often").
- **FEATURE MAPPING**: no VIX/VVIX/term-structure stream in our families — UNKNOWN,
  named gap. fvol (our realized-vol feature) is the nearest in-house proxy; realized
  range-completion vs an implied range needs the implied input we lack.
- **VERBATIM**: "VIX is not a trade signal, it is a context tool... it never tells you
  to click." (p3).

---

## TIMING TABLE (confirmation → typical delay after candidate/setup forms)

| Confirmation | Delay after formation | Source |
|---|---|---|
| Ladder absorption (C1) | live during the attack; seconds at the level, read on flow since approach ("reset the DOM before price arrives") | dom-6 p4 |
| Stacking/pulling read (C5) | on approach, BEFORE price trades at the level | dom-6 p5-6 |
| Spoof veto (C4) | signature is seconds-scale flicker/cancel | dom-7 p6 |
| Iceberg reload (C3) | several refresh cycles + joiners within 2 ticks — multi-touch, unclocked | dom-7 p4 |
| Footprint absorption (C6) | proof on candle close; book figures use 1-min candles, reversal ~3-4 candles after first disagreement | fp-9 p3 |
| POC flip (C7) | within the candle or the next | fp-9 p5 |
| Exhaustion print (C8) | turn "usually one or two candles away" | fp-9 p6 |
| Regular delta divergence (C8) | builds over several swings — minutes, can exceed 5 | fp-9 p6 figure |
| Stacked-imbalance zone (C10) | acts on RETEST — later revisit, not immediate | fp-8 p6 |
| CVD breakout grade (C12) | concurrent with the breakout bar(s) | vwap-10 p6 |
| Excess formation (C14) | needs 2+ same-letter periods = up to ~60 min | tpo-3 p6 |
| IB day-type verdict (C14) | after first hour (A+B) | tpo-3 p8 |
| VIX regime (C15) | pre-open + continuous intraday direction | vix-4 p4-6 |

Direct support for the user ruling that confirmation may come later than 5 minutes:
footprint absorption sequences span multiple 1-minute candles; regular divergence spans
several swings; imbalance zones and TPO references act on revisit, minutes-to-hours
later. The fastest confirmations (ladder absorption, spoof veto) are seconds-scale, so
the window is wide on both ends.

## PASS-RULE LIST

1. No level, no trade: "Absorption at a random price means nothing. At your level it is
   the trigger." (dom-6 p8); "A number without a location is trivia." (fp-8 p8).
2. No confirmation, no trade — at every level type (vp-2 p7; vwap-10 p4; tpo-3 p9).
3. Spread widens: do not lean on the level, do not chase into the gap (dom-5 p6).
4. Aggression WITH movement = continuation — do not fade a breaking level (dom-5 p7).
5. Spoof signs present: never enter with the perceived pressure; wait for real prints
   (dom-7 p6).
6. Size changing while the tape is silent = lie; trade the prints, never the picture
   (dom-7 p7).
7. Inside the shelf middle = rotation, chop, noise — no trade (vp-2 p7).
8. Single footprint imbalance = noise; need 2-3 stacked (fp-8 p7).
9. VWAP band touch alone = no trade; clear draw beyond the band = do not fade (falling
   knife) (vwap-10 p4).
10. Breakout on flat/falling CVD = fakeout; do not chase (vwap-10 p6).
11. Excess (finished business) at an extreme: expect hold on first test — do not chase
    through it (tpo-3 p9).
12. IB breaks early one-sided: do not fade the trend day (tpo-3 p8).
13. VIX below 13: usually not worth trading; below 14: scalps or stand out (vix-4 p5).
14. ES flat + VIX flat: chop — scalp rotations or stand down (vix-4 p6).
15. Implied range mostly completed: fuel spent — do not press continuation (vix-4 p5).
16. Backwardation: auction broken until the curve normalises — cut size, widen, or stand
    aside (vix-4 p8).
17. Poor extremes on ES: less reliable than NQ — downweight (tpo-3 p7).
18. Do not trade yesterday's regime on event days (pre-event fade / post-crush chase are
    the same mistake) (vix-4 p7).

## BEYOND-BOOK (cross-cutting)

- Formation-anchored measurement: the "reset the DOM before price arrives" rule (dom-6
  p4) is the book's own argument for measuring confirmation on flow SINCE candidate
  formation, not on session-cumulative delta — it matches a formation+Delta decision
  design directly.
- Zone, not price: absorption spreads across ~3 ticks (dom-6 p4) and iceberg joiners are
  scored within 2 ticks (dom-7 p4) — every level-conditioned feature should aggregate a
  small tick band, not one price.
- The refill-vs-prints ratio (dom-7 p7) is the series' single most computable novel
  discriminator: passive refills conditioned on traded volume at the same price separates
  real defence (iceberg) from theatre (spoof/layer/flip) with one number.
- Graded stacking: the book counts tells ("One tell is interest, two is a trade", fp-9
  p7) — confirmation is naturally an integer score over {absorption, POC flip,
  divergence, reload, stacking}, not a binary.
- Timing asymmetry the figures imply: DOM tells are seconds-scale, footprint proof is
  candle-scale, profile/TPO references are revisit-scale — a confirmation engine needs at
  least these three clocks running simultaneously.
- The figures repeatedly place the entry at the close of the confirming event (fp-9 p4
  arrow at the disagreement candle's close; vwap-10 p3 circles at band touches), never at
  the level touch itself — entry is after proof, accepting worse price for information.

## Named gaps (observables our stream lacks or may lack)

- Spread width and quote-gap events (C1) — not in the listed families.
- Order-lifecycle cancel latency for spoof flicker (C4) — per-second aggregates cannot
  see sub-second appear/vanish cycles.
- Price-binned bid/ask traded volume for diagonal imbalances and candle POC/flip (C6, C7,
  C10) — UNKNOWN whether our per-second stream is price-binned.
- Depth beyond top-of-book for the 2-tick joiner test (C3) — UNKNOWN.
- VIX / VVIX / term structure (C15) — absent; fvol is a realized-vol stand-in only.
- Anchored-VWAP anchor selection (C11) — needs event/swing anchors we do not mark.

## Terminal state

SUCCESS. Digest written to this file. All assigned pages read visually with the Read
tool: vp-lesson-2 9/9, tpo-lesson-3 10/10, vix-lesson-4 10/10, dom-lesson-5 8/8,
dom-lesson-6 8/8, dom-lesson-7 8/8, fp-lesson-8 8/8, fp-lesson-9 8/8, vwap-lesson-10
9/9 — 78/78 pages. No repo file touched except this digest.

# stop-re-entering.pdf — figure-first notes (17/17 pages)

Source: `/workspace/artifacts/cache/book_pdfs_20260822/stop-re-entering.pdf`
Ethos Order Flow / Education, Sires x Ethos. All 17 pages read as images. Text layer used only to pin quotes; figures carry the grammar.

Entries only. Waiting after formation is lawful. Daily-stop and size material on pp. 14–15 is recorded as a no-trade gate, not as a path.

Hypothesis only. Book numbers (3 ticks, 27%, 2–4 upticks, 18-tick dip, 6–8 ticks late) are this author's NQ/ES parameterization, not law for SI/HG/NKD.

## Sequence (not a score bag)

The book is one ordered machine. A later check is illegal until the earlier one is true. Independent "absorption / delta / replenish" scores are the error this lesson exists to stop.

1. **Location already exists.** Where price sits in the higher-timeframe auction, and which side should be in control. Mid-balance / mid double-distribution / POC magnet = stop. The other checks filter noise (p6, p13, p16).
2. **A candidate level is being hit.** Aggression into that location, volume above average, price holding. This is stage 1 (initial defense). It is the setup, not the entry. Beginners enter here. It is also where the 27% failures live (p10).
3. **Do not take the first touch.** The cited paper: median winner first dipped 18 ticks past the touch. Defense happens inside the level. The live pattern this lesson wants: level tested twice, sellers get nothing both times, buyers take control only after the second test (p7).
4. **Replenishment, countable.** The defended price refreshes as it keeps getting hit, size maintained or growing. Minimum: three ticks of replenishment. One or two is the named fake-out zone (p3, p10, p14).
5. **Exhaustion of the attacker.** Aggressor volume declines. Delta turns against them. Tape digits: doubles/triples shrink to singles on the losing side (p9, p10, p12).
6. **The absorber thickens.** Opposite side comes in with doubles and triples where the losers used to be. Both thin-loser and thick-winner must happen at the level (p9).
7. **Lift-off (the trigger).** Absorber flips passive to aggressive. Price accelerates away. Reward system: own-side aggression followed by upticks (long) or downticks that stick (short). Author's minimum: two upticks, band two to four (p12). "Passive absorption is the setup; aggression is the trigger."
8. **Delta as a filter, not a trigger.** Delta agrees with the side you want. CVD rolling over its median confirms control change on the 40-range examples (p8, p9). A huge delta print at a price is inventory. The next few bars tell you paid vs trapped. You trade that, not the print.
9. **Enter within a tick or two of that confirmation.** Six to eight ticks late means there is probably no reward system (p13, p14).
10. **Re-entry is a new decision from zero.** Same idea after a stop-out is not a continuation. Every box reticks as if the last trade never happened (p5, p14). If any box is open: no trade yet, not a smaller trade. Waiting is free.

Fail-closed at every step. Stage 1 alone is a pass. Guessing any of location / reward / delta is a pass.

---

## Confirmations

### SRE-4STAGE — failed vs confirmed absorption
**NAME:** SRE-4STAGE  
**pdf + page:** stop-re-entering.pdf, pp. 10, 12, 14 (glossary p3; clip p12)

**SETUP.** HTF location already says the absorber's side should be in control. Aggression is hitting that level. Volume above average. Price holding. This is stage 1 only.

**ORDERED CHECKS.**
1. Initial defense (holds, not confirmed).
2. Replenishment: level refreshes while still being hit, size maintained or growing, at least three ticks.
3. Exhaustion: aggressor volume declining, delta turning against them, digits shrinking.
4. Lift-off: absorber flips to aggressive, price leaves.

**WAIT.** Stages 2–4 resolve over the next few bars after the print (p9–10). Replenishment is a tick-count (3), not a clock. Clock time is whatever those bars take on the instrument. 40-range NQ bars are event-time (40 ticks of range), not minutes. ES 1-minute clips on pp. 11–13 show the same machine on clock bars. Waiting through stage 1 is the method.

**TRIGGER / INVALIDATION.** Trigger: own-side aggression after exhaustion, with the reward ticks (see SRE-REWARD-TICKS). Stop sits under the absorption (p12 caption). Invalidation: replenishment fails (1–2 ticks then pull), aggressor digits grow instead of shrink, price accepts through the level, or the lift-off never comes.

**PASS / no-trade.** Stage 1 alone. One or two ticks of replenishment. Entering on the passive defense. Anything past "the next few bars" with no lift-off. Guessing.

**FIGURE-ONLY DETAIL.** None on p10 (text stages). The working picture is p12: yellow `BOT MKT SIM 1` ticket sits on the bounce *after* the low, not on the first hammer. Red bubbles on the way down, then blue bubbles at the turn. Bid ladder showing triple-digit size (100, 117) against ask singles (1–5). That is stage 4 on a ladder, which p10 never draws.

**VERBATIM.**
- "failed absorption and confirmed absorption look identical at the moment most people enter. The difference only exists in time" (p10)
- "My minimum filter is three ticks of replenishment; one or two is the classic fake-out zone." (p10)
- "Passive absorption is the setup; aggression is the trigger." (p12)

**FEATURE MAPPING.**
- Stage 1: `disc_level_z*` defense + `disc_evt_*` attacks + `disc_tclock`/`disc_vclock` above-average pace.
- Stage 2: `disc_evt_*` reloads + `disc_quote_*` rebuild. Three-tick replenishment run is a countable reload sequence.
- Stage 3: `disc_evt_*` attack-rate decay + `w15`/`w60` delta sign flip.
- Stage 4: own-side `disc_evt_*` flip + immediate `w15_*` displacement.
- Digit thinning: **G3** (per-print size distribution). Our 1s aggregates see intensity trend, not singles vs triples on the tape.
- Refill *speed* as resiliency (p16): **G4**, partial via `disc_quote_*` rebuild latency.

### SRE-3STEP-GATE — location, then reward vs result, then delta
**NAME:** SRE-3STEP-GATE  
**pdf + page:** stop-re-entering.pdf, pp. 6–9, 11, 14

**SETUP.** Any candidate, including a re-entry. Applies to DOM, footprint, and bubbles alike "because they're all showing the same information" (p6).

**ORDERED CHECKS.**
1. Location of price in the HTF auction. Who should be in control. Who gets leniency.
2. Reward vs result. Your side acts, the market pays: buy aggression then upticks; sell aggression then downticks that stick. Effort without result is a warning, not an entry.
3. Delta as a filter. Delta agrees. Opposite side thickening, losing side thinning.

**WAIT.** All three *before* any entry and *before* any re-entry. No clock. If a check is not in yet, wait. p11 caption: stage 1 can be obvious while 2–4 have not happened. That freeze-frame is a wait, not a trigger.

**TRIGGER / INVALIDATION.** No standalone trigger. This gate licenses the 4-stage trigger. Invalidation of the gate: location wrong (nothing downstream can save it, p16); own-side effort unpaid; delta against.

**PASS / no-trade.** "the trader is fighting for a reversal in the middle of a balance, where neither side has an argument, and every wick looks like absorption because nothing has context" (p6). "If you need to guess on any of the three, the answer is no trade yet." (p11)

**FIGURE-ONLY DETAIL.** p6 is a nested screenshot of a black lesson slide, handwritten:

`1.) Location of price`  
`2.) Reward vs Result`  
`3.) Delta as a filter`

The caption under the frame says the three checks happen before you even look at DOM / footprint / bubbles. Order is drawn, not implied.

**VERBATIM.**
- "Three checks, in that order, before any entry and before any re-entry." (p6)
- "Effort is what the losing side shows. Reward is what the winning side gets. Enter on reward." (p7)
- "Without step one they filter noise." (p6)

**FEATURE MAPPING.**
- Location: `disc_auction_*` / `disc_prior_*` / `disc_ib_*`. Mid double-distribution / unfinished value: **G8**.
- Reward vs result: `disc_evt_*` followed by same-direction `w15_*` displacement. Effort-no-result = flow vs near-zero move (`w15`..`w300`).
- Delta filter: `w{60..1800}_*` signed flow. Session CVD vs its running median: **G10**.
- Delta *at a price row*: **G1**.

### SRE-TRAPPED-DELTA — unpaid print at the high, short below the zone
**NAME:** SRE-TRAPPED-DELTA  
**pdf + page:** stop-re-entering.pdf, p9 (worked on p8)

**SETUP.** Location already favors sellers (or at least does not favor buyers at the high). An outsized delta print (or cluster) sits at the highs. A crowd of buyers committed at one price.

**ORDERED CHECKS.**
1. Identify the print *at a price*, not "delta is high this minute."
2. Next few bars: did price leave in their favor, or can it not leave.
3. If it cannot leave, those buyers are inventory.
4. Price breaks *below the print zone*.
5. CVD rolls over (p8: over its median; p9 caption: "rolling over behind it").
6. Losing side (buyers) thinning; sellers thickening.

**WAIT.** "The next few bars tell you whether they were rewarded or trapped, and that's the only part you trade." (p9). On the p8 40-range NQ chart, that is several range-bars after the boxed high, not the first pink bubble inside the box.

**TRIGGER / INVALIDATION.** Short when price breaks below the zone that *contains* the prints, with CVD rolling over. Invalidation: price leaves upward (they got paid); CVD holds above its median; buyers thicken instead of thin.

**PASS / no-trade.** Print rewarded. Still inside the box. CVD not rolled. Location does not back a short.

**FIGURE-ONLY DETAIL.** See p8 and p9 notes below. Load-bearing: the short is drawn *under* the boxes, not in them. p8 has a white rectangle around the high cluster with small white circles on specific candles, speed-of-tape green on the rally then pink at the high, CVD climbing then rolling a curved median overlay. p9 has *two* boxed print zones at the highs plus a third box just right of the spike, and three pink circles on *earlier lower wicks* that are not the trap.

**VERBATIM.**
- "Delta is a filter, not a trigger." (p9)
- "The boxed zones hold outsized delta prints at the highs: a crowd of buyers acted there, and price paid them nothing. Those are trapped buyers. The short triggers when price breaks below the print zone, confirming the trap, with the CVD rolling over behind it." (p9 caption)
- "The entry this framework takes is the one where sellers regain control, buyers get absorbed, and the CVD confirms by rolling over its median." (p8)

**FEATURE MAPPING.**
- Outsized print at a price: **G1** (delta-by-price histogram). `disc_evt_*` burst size is a weak proxy; it does not answer "which price row."
- Cannot-leave: `w60_*` flow vs ~0 displacement at `disc_level_z*`.
- Break of zone: `disc_level_z*` cross of the print-zone low.
- CVD vs median: **G10**.
- Tape thicken/thin: **G3**.

### SRE-REWARD-TICKS — two to four upticks after own-side aggression
**NAME:** SRE-REWARD-TICKS  
**pdf + page:** stop-re-entering.pdf, p12 (defined p3, p7; veto p13)

**SETUP.** Stages 1–3 already true. Absorber is about to (or just did) flip aggressive.

**ORDERED CHECKS.**
1. Own-side prints have thickened (triples on p12).
2. Losing-side prints have thinned to singles.
3. CVD holding with the trade.
4. Then the aggression: two upticks minimum, author band two to four.

**WAIT.** Seconds. This is tape, not a 5-minute bar. It is the last check, not a substitute for location or replenishment.

**TRIGGER / INVALIDATION.** Enter on that aggression. Stop under the absorption. Invalidation: the upticks do not stick; tape flips back to the attacker; entry drifts 6–8 ticks away from the confirmation (p13).

**PASS / no-trade.** No upticks. Own-side still printing singles. Tape fully red into a long (p13). "A delayed reward system means probably no reward system." (p13)

**FIGURE-ONLY DETAIL.** p12: after the low, a small base of candles, then a green candle with a blue (buy) bubble. The yellow fill is on that bounce, not the wick extreme. Two-to-four upticks is visible as the first paid green candles *before* the ticket, not a target measured later.

**VERBATIM.**
- "Then the aggression came: two upticks, which is my minimum, two to four, for calling it a reward system." (p12)
- "Buy aggression followed by upticks. Sell aggression followed by downticks that stick." (p7)
- "My entry sits within a tick or two of that confirmation, not six to eight ticks late." (p14)

**FEATURE MAPPING.**
- Consecutive same-direction last-price ticks (run length 2–4): **UNKNOWN** as a first-class count. `w15_*` displacement and `disc_evt_*` lifts approximate "price paid them" but not "two upticks." Named gap, call it **G11** (tick-run length after own-side aggression).
- Proximity 1–2 ticks vs 6–8 ticks late: distance from the lift-off event, computable from the per-second mid path.

### SRE-REENTRY-ZERO — same idea after a stop is a new trade or nothing
**NAME:** SRE-REENTRY-ZERO  
**pdf + page:** stop-re-entering.pdf, pp. 1, 5, 8, 14

**SETUP.** Just stopped out. The urge is to take the same idea again without the read changing (glossary p3).

**ORDERED CHECKS.** Restart SRE-3STEP-GATE and SRE-4STAGE from step 1, from zero. Not "how close it already got."

**WAIT.** Until the whole sequence is true again. If price never returns to a location that earns leniency, there is no trade.

**TRIGGER / INVALIDATION.** Same as the first entry, or pass. Cover geometry: the graded fill is a *new* confirmed low, not a sixth stab at the five X'd longs.

**PASS / no-trade.** Any box still open. Mid-balance reversal fight (p6, p8's three-entry spiral). Daily stop already hit (p14 box; recorded, not a size proposal).

**FIGURE-ONLY DETAIL.** Cover: five red X's labeled 1..5 with 1R..5R on a declining gray path; teal dashed line and circle-dot at the first confirmed candle; rally marked +6R. Footer: "FIVE WRONG ENTRIES. ONE GRADED TRADE. NET +1R." The X's sit on longs into the downtrend. The circle-dot is *after* X5, on the first teal body, not on the low's wick. p15 later says a −4R daily stop would have deleted X5; that is account math, not the entry grammar.

**VERBATIM.**
- "the first trade was a read, the second was a hope, and everything after that was the break-even effect picking trades for you" (p5)
- "If this is a re-entry, it passes every box above from zero, not on the strength of how close it already got." (p14)
- "Waiting is also an answer, and it's free." (p11)

**FEATURE MAPPING.** Recompute the whole stack at the current time. Eligibility: price back in a `disc_level_z*` / `disc_auction_*` band that passes location. No extra feature. The "from zero" rule is a process constraint, not a column.

---

## Page-by-page figure notes

**p1 cover.** Title "Stop Re-Entering / A 3 step plan to always have the best entries." Chart: gray downtrend with five red X's (1R, 2R, 3R, 4R, 5R), then a teal circle-dot on a dashed line labeled CONFIRMED, then a teal uptrend to +6R with an arrow. Footer: "FIVE WRONG ENTRIES. ONE GRADED TRADE. NET +1R." Figure-only: the confirmed marker is a ring-and-dot on the first teal candle after the low, not on the extreme wick, and not on any of the five X's. Net arithmetic is drawn (5 × −1R + 6R = +1R). The failed attempts are visually faded; the graded path is the only fully inked sequence.

**p2 contents.** Text map. Figure-only: large gray logo watermark, no chart. Useful as the book's own order: overtrading reframe → why re-enter → three-step → reward vs result → delta filter → failed vs confirmed absorption → two clips → checklist.

**p3 glossary.** Two-column definitions. Load-bearing for the sequence, no chart. Pink bubbles = sell aggression, white = buy (on *his* chart; MotiveWave clips later use red/blue). Replenishment: "Three ticks or more is the minimum worth trusting." Digit read: "Triple digits is conviction, a single digit where doubles were is weakness." Delta: "A filter, not a signal on its own." CVD: running total of aggression, "which side is winning the session."

**p4.** No chart. Barber and Odean box (turnover, not picks). Reframe: confirmed-entry data, not a two-trade daily cap.

**p5.** Two black cards (break-even effect; realization effect). No market figure. Sequence implication: a stop-out locks the loss; the next decision is new, not a continuation.

**p6.** Nested video-slide screenshot, black board, handwritten 1/2/3 (quoted above). Tiny top-right: "Vital knowledge and implementation must be learned from further trade breakdowns and daily recaps." Figure-only: the three steps are the entire slide. No DOM, no bubbles, no delta histogram. Location is drawn as step one with a period after the number, not as a parallel score.

**p7.** No live chart (the 18-tick / 27.2% vs 68.8% numbers are the refill paper). Sequence implication: first touch is usually early; re-entering after that fail is paying twice for being early. Second-test-then-control is named here and drawn in the refill PDF, not here.

**p8. 40-range walkthrough (NQ).** ATAS-style Deepchart. Header: `NQ-202609`, `100-BT`, `40 Range`. Date axis through `13-07-2026`. Price ~30000–30075. Right-hand daily volume profile, two-tone (buy/sell delta). Three panes: candles, Speed of Tape (18), CVD.

Figure-only:
- White rectangle around the *high* cluster (~30050–30070), not around a low.
- Small white circles on specific candles *inside* that box. Caption: "the circles mark the prints that mattered."
- Green/yellow P&L tags already sitting in the box (`100.00 | 120.00`, a SELL tag). Someone marked a trade *at the high*. The text rejects those: three entries, three stops.
- Speed of tape: tall *green* stack on the rally into the box (~00:52–01:00), then *pink* at the high. Effort on the way up was paid; effort *at* the high was not.
- CVD climbs ~1.26 → ~1.58 into the high, then rolls over a curved white median overlay toward ~1.36, later recovers on the right-hand rally.
- Horizontal line ~30042.75 (POC-looking) cutting the later action.
- After the box: sharp sell-off, failed bounce, later a second rally with a purple circle on a lower wick (right side). The framework's short is the leave-down after CVD rolls, not the first pink bubble in the box.
- Pink bubbles = sell, white = buy, matching p3.

Sequence the text walks: buyers paid on the way up → small-stop long, stopped → flip short into the pullback, stopped → more buy aggression at the wick, re-enter, wick keeps absorbing. None of those asked whether anyone was being rewarded. Lawful entry: sellers regain, buyers absorbed, CVD rolls its median. One entry.

**p9. Trapped buyers, same platform, different day.** Header still NQ 40-range. Crosshair `15-07-2026 03:04:30`. Price ~30000–30070.

Figure-only:
- *Two* white boxes at the highs, plus a third box just to the right of the spike. Left box ~30050 on a prior high (circle inside). Center box on the actual high ~30062–30065 with a small inner rectangle and a + mark. Right box slightly lower after the spike.
- Three *pink* circles on earlier *lower* wicks (~30015–30020). Those are not the trap; they are prior paid sell prints. The trap is the boxed *highs*.
- Speed of tape nearly dead through the middle of the range, then a mixed pink/white burst *after* the high (~03:07–03:21) as the trap confirms. The burst is not the print; it is the liquidation.
- CVD peaked ~1.58, still elevated at the boxed high, then rolls. White median overlay visible.
- A small pink/white bubble cluster sits *in* the high box: the unpaid crowd.
- Short trigger is visually *below* the boxed print zone. Caption states it; the geometry agrees.

**p10.** Four numbered stages, no chart. Black card: absorption fails ~27% with no pacing confirmation; that gap *is* stage 1 vs stage 4; replenishment drops the failure rate. Flagged as own records, not an academic study (again on p16).

**p11. Clip, decision moment.** MotiveWave Console (Sires). `EPZ25` 1-minute. Timestamp `Nov 07 10:23`. Flat: `Pos: 0.00 P/L 0.00`. Three panes: DOM left, time-and-sales center, candle + volume profile right.

Figure-only:
- DOM headers: `Volume | Delta | Vol | Not | Price | Bid | Bid | @Ask | Ask | Ask | O`.
- Current ~6704–6708. A white horizontal line through a *thin* profile shelf (air between two fat nodes ~6710–6716 and ~6694–6700). That is a double-distribution valley, the location veto p13 will name.
- Time-and-sales almost entirely red (sellers hammering the bid). Caption: "Sellers have been hammering into the bid. The question is not whether there's absorption, stage one is obvious. The question is whether anything past stage one has happened yet."
- Bid ladder mixed, including a large `107` several ticks below; some bid cells cyan/red. Not yet the triple-vs-single split of p12.
- Red bubbles on the chart: one left of a bar ~6712, one lower at the current shelf.
- No entry ticket. This is a wait frame.
- Price level (~6706) matches p13's wrong fill, *not* p12's 6622 correct fill, despite the heading "Clip one, the decision moment." Treat p11 as stage-1 freeze-frame in the 6700s EPZ session; treat p12 as a different session's completed stage-4 long.

**p12. Correct entry, dissected.** Same MotiveWave, tab `19th trade`. `EPZ25` 1-minute. Timestamp `Nov 07 10:26`. Long on: `Pos: 1@6622.00 P/L 1237.00 0.25`. Tickets: yellow `BOT MKT SIM 1` at the bounce; `LMT SIM 1 C` at `6851.00`; `STP SIM 1 C` at `6626.00`.

Figure-only:
- Fill is at 6622, ~80 points away from p11/p13. Different clip than the 6700s decision frame, whatever the heading says.
- Visible STP at 6626 is *above* the 6622 fill (4 ticks). Caption says the stop "sits under the absorption." The on-screen STP is a later, managed stop (trade already +1237). Original invalidation is not the number printed on the right.
- Chart: sell-off into ~6618–6622, small base, then green candles. Red bubbles on the way down, blue (buy) bubbles at the turn. Ticket sits on the bounce, not the wick extreme.
- DOM at screenshot time (trend already running): bid column triples (`100`, `117`, `39`, `22`); ask column singles and tiny doubles (`1`–`5`). That is the digit filter passed, drawn, not described.
- T&S now mixed/green, unlike p11/p13.
- Right-hand volume profile has a thick node around the current 6644–6648 area (value building *after* lift-off).
- Time axis 9:37–11:45. The low and fill are near 9:40–9:50. Screenshot is ~10:26, so we are looking at a completed confirmation, not the decision second.

**p13. Wrong entry, dissected.** Tab `4th trade`. Same `EPZ25`, `Nov 07 10:35`. Long: yellow `DOT MKT SIM 1` at `6702.50`. `Pos: 1@6702.50 P/L 37.50 0.25`. `STP SIM 1 C` at `6700.00` (2.5 points / 10 ES ticks under the fill). Yellow STP also highlighted *on the bid ladder*.

Figure-only:
- Same market as p11: bimodal profile, valley at ~6702–6708, fat nodes above and below. Location is the middle of a double distribution, drawn as the right-hand histogram shape, which the text then names.
- T&S fully red into the fill. Cursor on the candle just after the ticket.
- DOM delta column negative (`-1`, `-4`, `-18`, `-14`, `-24`). Sellers still refreshing.
- Leftover at `6715.00`: volume `5715`, delta `333` (orange). Unpaid buy print still sitting at the local high of this range. That is SRE-TRAPPED-DELTA inventory *above* a long. The long is pointing into it.
- Buyer at the entry: single-digit print (text); the ladder agrees, no triple bid wall at 6702.
- Price then tags the old sell-aggression above (~6710), rejects, stop at 6700 is the next event. The rejection is a red bubble on that upper test.
- Caption: "Nothing on the ladder has confirmed a thing: sellers still refreshing, buyers printing singles, and the location argues for the other side entirely."

**p14 checklist.** Nine empty checkboxes, three groups. Figure-only: they are *empty*. The page is a gate, not a score. Caption: "If any one is unticked, the answer is no trade yet, not a smaller trade." Daily-stop box (−4R) and re-entry-from-zero box sit under "RISK, EVERY TIME." Timing box is entry-side: "within a tick or two of that confirmation, not six to eight ticks late."

**p15.** Two black cards (Locke & Mann; refill-paper −4R lever). No chart. Cover is cross-referenced: five −1R re-entries would have been −5R, past the −4R day stop, so a trader honoring that stop never sees X5. Recorded. Not an entry confirmation.

**p16.** Limits and sources. Figure-only: none. Binding for extraction: 27% and digit reads are own collection; paper stats are historical simulation after modelled costs with a losing quarter in the record. Last paragraph: absorption is a process with resiliency that changes second to second; LOB research treats refill speed after a hit as a measurable property. That is G4, and it is why stages exist.

**p17 closer.** No chart. "The checklist stops the re-entry. The thesis makes the first entry worth taking." Location is the lean. Companion: *Origin of the Move* and *The Refill Effect* at kanji.org.uk.

---

## Beyond the text (figures only)

- Cover vs p15: the cover's graded trade is a *new* confirmed low after five failed knife-catches. p15 retells it as "the sixth trade" surviving a day stop. Entry grammar follows the cover: wait until the 4-stage actually completes at a location that earns it. The day stop is a different object.
- p8 tickets inside the high box are the *wrong* fills the lesson is mocking. The lawful short is later, after leave-down + CVD median roll.
- p9's pink circles on lower wicks are distractors. The trap is the boxed highs. A model that fires on "pink bubble near a circle" without asking high vs low will invert this page.
- p11 heading says clip one; the book is the 6700s session that p13 then fills wrong. p12's correct 6622 long is a different clip. Do not stitch p11 → p12 as one timeline.
- p12's on-screen stop (6626) is not the original invalidation. Read the caption for stop placement; read the ladder for digits; read the ticket for *when* they entered (after the bounce, not the wick).
- p13's 5715/333 at 6715 is a G1 object sitting *above* a long. Location and trapped-print both veto before the tape argument.

## What a bag-of-tells would miss

Scoring "some absorption, some delta, some replenish" as parallel features is exactly stage-1 entry. This PDF's decision is ordered: location → unpaid vs paid effort → replenish ≥3 → digits thin/thicken → lift-off ticks → delta/CVD agrees → enter within 1–2 ticks. Without **G1** you cannot ask "print at this price." Without **G3** you cannot ask singles vs triples. Without **G10** you cannot ask CVD vs its median. Without **G11** you cannot count two upticks. Without **G8** you cannot veto the p13 double-distribution mid.

---

## Timing (after formation)

| Check | Delay the book states or the figure implies | Page |
|---|---|---|
| First touch vs working defense | median winner dipped 18 ticks *past* the touch (cited paper) | 7 |
| Second test then control | after the second failed test, not the first | 7 |
| Delta print → paid vs trapped | "the next few bars" | 9 |
| Replenishment | ≥3 ticks while still being hit; 1–2 = fake-out | 10, 14 |
| Stages 1→4 | the gap that contains the 27%; wait through it | 10 |
| Reward ticks | 2 upticks min, band 2–4, seconds on the tape | 12 |
| Entry proximity | within 1–2 ticks of confirmation; 6–8 ticks late = no | 13, 14 |
| 40-range NQ bars (p8–9) | event-time, 40 ticks of range, not clock bars | 8, 9 |
| Re-entry | from zero, no inherited credit | 14 |

---

## Pages

17/17 read as images (cover through closer). Instruments in figures: NQ 40-range (pp. 8–9, 13 Jul 2026 and 15 Jul 2026); EPZ25 1-minute MotiveWave (pp. 11–13, 7 Nov, two different clips).

**Terminal state: success.**

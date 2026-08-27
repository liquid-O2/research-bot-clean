# Diagram-level notes, order-flow half of the discretionary library

Date 2026-08-27. Companion to `CROSSWALK_AUDIT_FLOW_2026-08-27.md`, which
audited the text. This pass looks only at the pictures: what each figure shows
mechanically, what every annotation on it claims, and above all the geometry —
where the marked event sits relative to the extreme, whether one peak or
several are marked, and where confirmation is drawn relative to the pull-away.

Pages read at full resolution: `reading-delta` 2-9 (figures on 4, 7, 9);
`your-mistakes-with-absorption` 4, 6, 9, 11, 13; `refill-effect` 9, 10, 11, 13,
23; `dom-lesson-6` 6, 7; `fp-lesson-9` 5; `trapped-buyers-one-retest` 5, 6, 7,
9. Completeness note at the end.

---

## Consolidated: what the diagrams say about the zone-episode absorption model

The three claims under test are absorption near but not at the extreme,
multiple peaks per episode, and confirmation only after a pull-away. The
diagrams **confirm all three and sharpen each one into a number or an ordering
the text alone did not give**. They also expose one distinction the model
currently collapses.

**Near-not-at is confirmed, and it is two different statements at two
different scales.** The crosswalk treats "location" as one axis; the figures
use it as two, and they veto in opposite directions. At the macro scale the
event must be *at* a structural extreme: `your-mistakes` p6 draws the full
absorption signature at POC and labels it in the author's own hand
**"THIS IS NOT ABS"** — the print is real, the location makes it meaningless —
and p13's checklist makes it a hard gate, "at a real extreme (shelf, ledge, low
volume node, minor volume node), not near POC or inside balance." At the micro
scale the defence is *inside* the zone, not on its front edge:
`refill-effect` p10's three-panel order-book schematic (1. The wall, 2. The
flush, 3. The refill) shows the aggressive sells consuming the top rows of the
resting-bid stack and price dipping *into* the zone before fresh orders appear
below the filled ones, captioned "The defence does not happen at the front edge
of the zone. It happens inside it." `dom-lesson-6` p6's ladder shows the same
thing in miniature: the highlighted defended price is the second row inside the
bid cluster, not its topmost row. So the model should read: the *zone* is
anchored at a structural extreme; the *episode* resolves one layer inside it.

**The depth of "inside" is quantified, and it is 18 ticks, not two.**
`refill-effect` p10 states the median eventual winner first dips 18 ticks past
the touch; p23's stat sheet carries the matching execution triple — limit 12
ticks in, 32-tick stop, 96-tick target. The three numbers are the geometry:
12 < 18 < 32, an entry placed inside the zone shallower than the median adverse
excursion, and a stop placed beyond it. p11 then measures what happens if you
get this wrong — same signals, same quarter, same engine, only the order type
changing: resting inside the zone earns profit factor 1.80, win rate 68.8%,
+$2,112 on 64 fills, while chasing the touch with a market order earns 0.81,
27.2%, -$405 on 312 fills, with the annotation that the limit fills less often
"precisely because it demands the flush that defines the setup." **The adverse
excursion is a constituent of the setup, not a failure of it.** Any rule in the
mill that treats an excursion past the level as invalidation, or that uses a
two-tick lift as the confirmation threshold, is off by roughly an order of
magnitude against the same mechanism.

**Multi-peak is confirmed at three separate timescales, and repetition is
itself the signal.** Within one zone, `reading-delta` p9 marks a wide white box
around a minor-volume-node extreme and states price "tags the level and rejects,
repeatedly, at both the top and bottom of the same micro balance," with "more
than one wick reaction visible along the way once the zone is drawn out
properly." Within one chart, `your-mistakes` p11 marks the *same* mechanic
twice, at VAH and at VAL, with identical annotation text at both callouts — one
rejects a high, the other rejects a low. Across sessions,
`trapped-buyers` p5 shows one level failing twice hours apart in the New York
AM and PM sessions and argues the repetition is the whole content of the read:
"One failed push is noise. Two failed pushes at the same price, in two different
sessions, is the market telling you where it isn't willing to trade... every
hour it held made a break less likely, not more." `reading-delta` p4 generalises
the same shape upward as a ladder of protected lows, each new one replacing the
last. A single-peak episode detector will systematically select the noise case
the author explicitly discards.

**Confirmation after pull-away is confirmed, and it is two gates in a fixed
order, not one.** `your-mistakes` p9 walks the sequence in order: aggressive
effort into the level, a passive wall soaking it, *no reward* for the effort
confirmed by price failing to hold the push, and then — "then, and only then" —
opposite aggression arriving as a second energy source, "not just an absence of
buyers but active selling." The instruction that follows is explicit on where
the entry sits: "enter on the test of the reward system, not on the wall
itself," after "one more retest with a decent amount of refresh orders in time
and sales." `trapped-buyers` p6 states the same rule as a plan formed in
advance — "wait for a breakout of the intraday range, then wait again for price
to come back and retest it. Two waits, not one" — with the stated fallback of
standing aside entirely if the retest never comes. So confirmation = a
displacement away from the level, *plus* a return to it that holds. Gate one is
the pull-away; gate two is the retest. `your-mistakes` p4 sizes gate one
tightly: price must move in your direction **within three ticks** of the
absorption print for it to count as replenished, and past that window the
absorption is treated as unconfirmed regardless of how it looked.

**One correction the model should absorb: the 3-tick and 18-tick numbers are
not in conflict and must not be merged.** Three ticks is the *favourable*
displacement that validates the print, measured immediately and in your
direction. Eighteen ticks is the *adverse* excursion the median winner suffers
before it works, measured past the touch in the opposite direction. They are
different signs, different clocks, and different purposes. A single "confirmation
distance" parameter cannot carry both.

**And one refinement the diagrams force on the fast path.** `your-mistakes` p11
argues the Delta spike is the fastest of the four checks precisely because it
does *not* wait for price: it "is visible at the moment control changes hands,
which is earlier in the sequence than the price reaction that eventually follows
it." `fp-lesson-9` p5 offers the same early read one level down, inside a single
candle — the POC flipping from one extreme of the candle to the other, "control
just changed hands," described as confirmation the level is being defended. So
the sources carry a genuine two-lane structure: a fast lane that reads the
transfer of control directly off delta or the intra-candle POC and does not
require a pull-away, and a slow lane that requires pull-away plus retest. The
zone-episode model currently only implements the slow lane.

**Unresolved conflict, visible in the pictures.** `dom-lesson-6` p7 splits
absorption (heavy volume, no movement, someone is there, reverses hard) from
exhaustion (shrinking volume, no movement, nobody is left, drifts) into two
side-by-side cards and says knowing the difference "is the whole edge, because
they point opposite ways," with stopping volume named as the violent extreme of
the absorption branch. `reading-delta` p8 uses trapped, exhausted and absorbed
as three words for one outcome. The diagrams do not reconcile this; the
distinction should be carried as an explicit fork, not averaged.

---

## reading-delta.pdf

**p4, "The protected low: partial below where sellers could still defend."**
A tldraw annotation over a delta profile (grey volume histogram left, magenta
delta overlay) with a white price path rising left to right. Two red horizontal
lines span the panel — an upper one at the prior high the rally eventually
reaches, and a lower one at the micro balance the move escaped from. The
protected low is drawn as a **band, not a line**: a short congestion of white
zig-zags sitting between the lower red line and a red dashed line just beneath
it. A green curve traces the buyers' defence path from the profile's heavy node
up into that congestion. Annotations: "Sellers have become trapped = Buyers will
protect here" pointing at the band; "SL" hand-lettered at the dashed line
immediately *below* the band; "ENTRY" on a lower dashed line below that; a purple
arrow bottom-left giving the trend direction; and in magenta at top right, the
governing veto — "ONLY DO THIS METHOD WITH CONFIRMED LOWS / FINISHED AUCTIONS."
Geometry: the operative marker is the **bottom edge of the zone**, not the
extreme point. The partial and the trailed stop go below the sellers who
defended, because that is the last price at which the defence is still a defence;
below it the read inverts to "these sellers are refilling and pushing back toward
your entry." Confirmation is marked as an *absence* — the low counts as protected
once price stops coming back to test it.

**p7, "The highest delta print on the profile, against a real short."**
A real order ticket overlaid on a candle chart with the delta profile as a
magenta horizontal histogram on the right edge. Green and magenta Big-Trade
bubbles sit on the candles. Three order-ticket labels are visible at their real
prices: a stop above (`-350.00`), the entry at `-1 QTY` mid-panel, and a limit
target below (`+670.00`). A thick red horizontal bar marks the level being
faded; a white curved arrow runs from the earlier buying cluster across to the
short entry. A purple arrow top-left gives the prevailing direction. The claim
is a discriminator between real and fake delta: the load-bearing quantity is the
**highest point of the delta profile**, not the most recent print, and whichever
side produced that maximum is the side that was rewarded. Geometry: entry sits
at the delta print itself, with stop and target placed at real levels rather
than fixed distances; the "sell bubble" of trapped buyers develops *after* the
print, to its right.

**p6 (text, drives p7) — the divergence example stated cleanly.** Buying
aggression printing on a wick reads, on its own, as buyers being absorbed, the
textbook short. The correction is to look at where the profile's maximum sits.
If the maximum is buyers rather than the sellers who just arrived on the wick,
the read flips to "buyers defended quickly" and price is more likely to push
higher. Same print, opposite conclusion, discriminated purely by the location of
the delta maximum. This is the sharpest real-versus-fake statement in the six
documents.

**p9, "A low volume node extreme, a high delta print, and the wick reaction it
produced."** Two white rectangles are drawn on the chart: an upper thin box at
the prior balance, and a lower wide box marking the dealing range's minor volume
node. A **red circle** marks the high delta print at the upper boundary of the
lower box. Green Big-Trade bubbles (trapped buying delta) cluster above and left
of the circle; magenta bubbles (the sellers who arrive immediately after) sit
below and right. Order tickets at right show the short, its stop above and its
limit target well below. Geometry: the marked event sits **at the edge of a drawn
zone, with the zone drawn first** — the author's stated precondition is that the
LVN/MVN is "drawn out properly" before the print means anything. Multiple wick
reactions are claimed inside the same micro balance, at both its top and its
bottom, which is the clearest single-page statement of multi-peak in the library.

**p8 (text).** Names the refill as control changing hands twice, and treats
trapped / exhausted / absorbed as interchangeable labels for one outcome — the
usage `dom-lesson-6` p7 explicitly rejects.

## your-mistakes-with-absorption (1).pdf

**p4, "The reward system: a confirmed 3-tick move, read against time and sales
and CVD."** Three stacked elements. Top: a white price path oscillating against
a **red horizontal band** (a band, not a line) drawn across the whole panel, with
two green circled touches *at* the band and one red circled failure between them,
before an arrow breaks up and away through it. Middle right: a boxed inset
labelled "T&S or SOT" containing a red-and-green micro candle sequence — the tape
view used to check whether the opposing side is being refreshed. Bottom: a blue
CVD trace, hand-labelled "CVD", rising through the same span with its own arrow.
A white curved arrow connects the price panel to the inset, i.e. read the tape at
that moment. Claims: the entry does not go in on the absorption print; price must
move in your direction **within three ticks** of it to count as replenished, and
missing that window makes the absorption unconfirmed whatever it looked like.
The failure mode named is entering "where the side you are fading is actively
winning" — sellers still being refreshed, buyers instantly defending. Geometry:
the level is a band, the marked touches are multiple, and confirmation is a small
displacement *away* from the band inside a tight tick budget.

**p6, "The absorption signature at POC: right shape, wrong location."** A daily
volume profile with delta profile at right (green above, red below) and VAH, POC
and VAL drawn as horizontal lines across a white price path. Several green
circles mark absorption-shaped events; the highest sits at VAH, and a cluster
sits mid-range near POC. Two hand annotations carry the whole page:
**"THIS IS NOT ABS"** with a curved arrow pointing into the mid-range cluster,
and a magenta arrow labelling POC where price simply chops. An up arrow at the
bottom left marks the eventual resolution — price comes back up, the opposite of
what the signature promised. The page caption is explicit that the print is not
fake; the location makes it meaningless. Geometry: the same signature is a coin
flip at POC and a real signal at a real extreme, which makes location a **veto
applied before the signal is read at all**, not a weight applied to it.

**p9, "The definition, and the sponge: effort up, a passive wall, no reward,
then the reversal."** A sparse panel built around a screenshot of a dictionary
definition of *absorption* ("the process of one thing taking in, soaking up, or
receiving another substance, energy, or attention"), with "soaking up" circled in
red. Two long white curves sweep in from the left — the effort — and a red
scribble with a green vertical stroke on the right marks the wall and the
reversal aggression that follows it. A delta profile fragment sits at the top.
The ordered sequence is the content: effort, wall, **no reward** confirmed by
price failing to hold the push, then opposite aggression as a second energy
source. The stated entry rule is "on the test of the reward system, not on the
wall itself," after one more retest showing refresh orders in time and sales.
Geometry: entry is displaced in time and in price from the absorption event by a
full pull-away-and-return cycle.

**p11, "The same Delta spike mechanic at VAH and at VAL."** The p6 chart
re-annotated. Two yellow-highlighted callouts, one at VAH and one at VAL, carry
**identical text**: "High delta spike of buyers (Opposition losing control) being
abs passively by sellers." A hand note at the top reads "The easiest way to see
this is DELTA:". The "THIS IS NOT ABS" label from p6 is still present on the
mid-range cluster, so the page shows the accept and reject cases side by side on
one chart. Green and red circles mark the individual spikes at both extremes.
Geometry: two marked peaks on one chart, one at each end of value, same mechanic
mirrored; and the explicit claim that the delta spike is visible *earlier* than
the price reaction, which makes it the fast confirmation lane.

**p13, the printable checklist.** Fourteen boxes under four mistakes. The
load-bearing ones for geometry: price has moved in my direction **within 3 ticks**
of the print; time and sales shows the opposing side is *not* being refreshed;
price is on the correct side of the **CVD median**; this is a fade, not a
continuation; the absorption is at a real extreme, **not near POC or inside
balance**; I know whether the VAH/VAL I am using is today's (still moving) or a
previous day's (fixed); I can point to effort *then* wall *in that order*; the
effort was NOT rewarded; **a second, opposite aggression has shown up, not just an
absence of the first side**; I am entering on the retest, not the wall; I have
filtered out any print at POC regardless of how clean it looks; I can trace the
wall back to an actual Delta spike; and for a failed auction the return-to-balance
odds are **roughly 72 to 80 percent**, not a fixed number.

## refill-effect (1).pdf

**p9, "Selection is what changes the sign."** Two panels. Left: average result
per trade, taking every touch (41,152 events) at **-0.285R** in red versus
model-selected touches out-of-sample at **+0.143R** in green, annotated "take
every touch: you lose steadily" and "take only the touches the model grades
highest: the sign flips." Right: grading skill as AUC across three unseen
time-slices (0.61, 0.63, 0.64) plus the full test (0.63), against a red dashed
placebo line at 0.51 annotated "scrambled-label placebo: 0.51. The machine can't
invent an edge from noise," with 0.50 marked as pure guessing. Prose above: the
highest-ranked touches hold 63% of the time, the lowest 25%. The boxed note under
the figure is the decomposition the crosswalk missed: **memory and location
families do almost all the work; raw order-flow features alone reach AUC 0.54**,
with the author's own comment that aggression *builds* the level but the level's
*memory* predicts the next touch.

**p10, the wall / flush / refill schematic — the single most important figure for
the model.** Three side-by-side order-book panels, each a horizontal bar chart of
resting buy size by price with price increasing upward. Panel 1 "The wall":
five teal bars of increasing length downward, annotated "resting buy orders
stacked in the zone, the defenders." Panel 2 "The flush": the top three bars
unchanged but the bottom two rendered **faded/consumed**, with two red arrows
pointing in at them and the annotation "aggressive sells hit the wall, price dips
into the zone." Panel 3 "The refill": the same top three bars plus two **fresh
dark-green replacement bars** at the consumed prices, with a green up-arrow and
the annotation "fresh orders replace the filled ones; sellers are exhausted,
price bounces." Caption: "Each bar is resting buy orders at one price. The wall
gets hit, price dips inside the zone, and if the defenders are real, fresh orders
replace the filled ones before the sellers can break through. **The trade is to be
one of those replacing orders.**" The prose above supplies the number: the median
eventual winner first dips **18 ticks past the touch**, and "the defence does not
happen at the front edge of the zone. It happens inside it." A pull quote closes
the page: "Same signal. Opposite side of the mechanism." Geometry: the marked
absorption event is explicitly *inside* the zone, displaced from the touch by a
median 18 ticks, and the flush is a precondition rather than a veto.

**p11, "Identical signals, opposite outcomes."** Two contrast cards — "Market
order at the touch: you do what the losing aggressors do, pay the spread to push
into a wall, enter before the flush, and eat the full 18-tick dip against a tight
stop. **You pay for the defence**" versus "Resting limit inside the zone: you are
filled by that same flush, at the price where the refill is defending, alongside
the defenders. **You are the refill**, and you collect the premium the impatient
side pays." Below, three paired bar charts under the header "Everything identical:
signals, quarter, engine, costs. Only the ENTRY TYPE changes": profit factor
1.80 versus 0.81 (with a dashed breakeven line at 1.0), win rate 68.8% versus
27.2%, net P&L +$2,112 versus -$405. Caption: 64 resting-limit fills against 312
market-order fills, and "the limit fills less often precisely because it demands
the flush that defines the setup." Prose adds that the effect resists data-mining
because "it is not a chart pattern, it is a **mechanism with a fee attached**, and
the fee changes sign depending on which side of the order book you stand on."

**p13, "The shape of the returns."** Top: a histogram of out-of-sample trade
outcomes in R, with a tall red bar at -1R annotated "losses are capped by the
stop: nothing worse than about -1R", a green bar at +3R annotated "winners run to
the 96-tick target: the +3R cluster", and a teal vertical line at the mean,
"average +0.143 R". Bottom: net R for each of sixteen held-out weeks, eleven
positive, annotated "11 of 16 weeks positive: no single week carries the result."
Geometry relevance: the distribution is bimodal at exactly -1R and +3R, which
means the exit rules are hard and the target is fixed at 96 ticks; there is no
partialling in the measured version of this strategy.

**p23, the one-page stat sheet.** The numbers that matter for geometry, verbatim
from the table: touches that hold **42%** base rate; fade every touch **-0.285R**;
touch-grading **AUC 0.63** out-of-sample against a **0.51** scrambled-label
placebo; hold rate worst-to-best decile **25% → 63%**; dominant features
**memory + location**, with "flow alone: AUC 0.54"; **median winner's dip past the
touch 18 ticks**; resting limit 68.8% / 1.80 / +$2,112 against market order
27.2% / 0.81 / -$405; out-of-sample record 542 trades over 79 untouched sessions
at ~6.8/day with the execution spec **limit 12t in, 32t stop, 96t target**;
+0.143R mean, PF 1.19, 30% win rate; +78R cumulative, 11 of 16 weeks green;
worst quarter -$647 at PF 0.76, disclosed; one leaky feature removed in the
hindsight audit with the edge standing without it; parameter grid train-to-test
rank correlation 0.92 over 100 configs. Data basis: NQ and MNQ, Dec 2024 to Nov
2025, 199M ticks, 235 sessions, 41,152 events, CME tick data, aggressor side.

## dom-lesson-6.pdf

**p6, "The read at the level."** A DOM ladder rendered as a two-sided horizontal
bar chart with a vertical divider. Above the divider, ten **red** bars of varying
length — aggressive sells hitting the bid. Below it, ten **teal** bars, one of
which is **highlighted with a light border and is by far the longest**, extending
past every other bar in the panel. Caption: "Absorption on the ladder: aggressive
sellers hit the bid, the level (highlighted) refuses to break and reloads, price
reverses up." Geometry worth noting: the highlighted defended price is the
**second row inside the teal cluster, not its top row** — the defence sits one
level inside the stack rather than at the boundary where the selling stopped,
the same near-not-at shape `refill-effect` p10 draws at zone scale. Three ticked
checks below: "Aggression into the level, no follow-through — the absorption
tell. Someone bigger is on the other side of the attack." "Stacked size that
stays — real defence. **Stacked size that vanishes as price approaches was never
real.**" "Delta agrees with the read — positive delta with no upward progress
means trapped buyers. That is fuel for the other direction."

**p7, "Absorption vs exhaustion."** Two contrast cards. ABSORPTION (teal): "A
passive giant soaks up aggression at a level and holds it. Heavy volume trades,
price does not move, the aggressive side gets trapped. It signals a reversal,
someone wanted every contract at that price." EXHAUSTION (red): "The aggressive
side simply runs out. Volume dries up, the pushes get smaller, no big passive
player is needed, the move just dies of its own accord. It signals a pause or a
fade, **not necessarily a hard reversal**." Between them: "Stopping volume is the
extreme version: a single burst of huge volume that halts a trend dead. It is
absorption at its most violent, the last aggressive push meeting a wall, and it
often marks the turn." Closing box, "HOW TO TELL THEM APART": "Watch the volume
as price stalls. **Big volume with no movement is absorption**, someone is there.
**Shrinking volume with no movement is exhaustion**, nobody is left. Absorption
reverses harder, exhaustion drifts." The framing sentence at the top calls the
distinction "the whole edge, because they point opposite ways." No price chart on
this page — the discriminator is deliberately volume during the stall, not shape.

## fp-lesson-9.pdf

**p5, "The POC flip."** Two candle-interior volume ladders side by side, each
seven horizontal bars representing volume traded at each price inside a single
candle. Left ladder: the brightest bar is **second from the bottom**, labelled
"POC low, sellers in control." Right ladder: the brightest bar is **second from
the top**, labelled "POC flips high, buyers take over." A diagonal arrow runs from
the left ladder's bright bar up to the right ladder's bright bar. Headline above:
"A POC flip is that busiest price **jumping to the other side of the candle**.
Control just changed hands." Caption: "The heaviest business moves from one
extreme of the candle to the other, buyers and sellers have swapped control."
Closing box, "HOW TO READ IT": "POC low in the candle then flipping high means
the business moved up with conviction. **At a key level, a flip in your direction
is confirmation the level is being defended.**" Geometry: note that neither
marked POC sits at the candle's actual extreme — both are one row in from the
end, so the flip is measured between two interior prices, and the detector is
single-candle, i.e. minute-scale, and needs no pull-away.

## trapped-buyers-one-retest.pdf

**p5, "The level, defended twice across two separate sessions."** A full session
chart with a horizontal volume profile down the right edge and three horizontal
grey bands marking the daily structure. A short **magenta hand-drawn line** marks
the upper extreme where price failed. Two separate rally attempts reach that line
— one in the New York AM session, one in the PM, hours apart — and neither breaks
it. The argument on the page is the multi-peak claim in its strongest form: "One
failed push is noise. Two failed pushes at the same price, in two different
sessions, is the market telling you where it isn't willing to trade... this is not
a level buyers were winning at, and every hour it held made a break less likely,
not more." Geometry: the two marked peaks are at the *same price* but separated
by hours, which puts the repeat-touch clock at session scale, far slower than the
minute-scale detectors elsewhere in the library.

**p6, "Intraday levels marked off the session open and balance."** The same chart
with the intraday structure drawn as horizontal bands built from where the session
opened and balanced, and a vertical divider marking the session boundary. Price
pushes up close to the intraday upper extreme **without fully tagging it**, which
the page reads as another instance of the same story — buyers reaching and coming
up short. The stated plan, formed before the fact: wait for a breakout of the
intraday range, then **wait again** for price to return and retest it. "Two waits,
not one." If the retest does not come, stand aside and look higher up at the daily
extreme instead. Geometry: the marked event is a *near miss* of the extreme rather
than a touch of it, and the entry is gated on a return that may never arrive.

**p7, "The retest and the short entry, marked live."** The same chart with the
retest zone drawn in magenta: two roughly parallel horizontal strokes bounding a
band, a small circled mark where price re-enters it, and a cursor arrow at the
fill. The quoted fill: "we got that retest right here, we got it, and we shorted
all the way down to right here." The page stresses ordering — balance, delta, the
two failed New York pushes and the intraday breakout all lined up **before** price
returned, so the entry was "price arriving at a decision that had already been
made." Geometry: entry sits **inside the magenta band on the return leg**, after
the pull-away, at a level already defended once; the band is drawn wide enough to
be a zone rather than a line.

**p9, "Footprint and DOM, aggressive selling printing inside the body."** A
zoomed footprint chart with a cumulative-delta trace overlaid, a DOM ladder at the
right showing bid and ask stacks with two highlighted resting blocks, and a delta
histogram along the bottom alternating blue and red bars. The claim: aggressive
selling printed **inside the candle bodies** rather than sitting passively on the
offer, and it "kept showing up bar after bar rather than as one isolated print."
The stated reason for the check is that "a level can be correct and the entry can
still be early" — tape aggression in your direction, on top of the level and the
retest, is what turns a half-size hope into a normally sized trade. Geometry: this
is a third confirmation gate, after pull-away and retest, and it is explicitly a
**persistence** test — repeated bars, not one print.

---

## Completeness note

Every figure page in `reading-delta` (4, 7, 9), `your-mistakes-with-absorption`
(4, 6, 9, 11, plus the p13 checklist), `dom-lesson-6` (6, 7) and `fp-lesson-9`
(5) was read at full resolution, along with the surrounding prose on those pages.
`refill-effect` was read at its five load-bearing figure pages (9, 10, 11, 13,
23); its remaining figure pages — roughly 5, 7, 12, 14, 15, 17-21 — were not
opened, and any additional model or feature-importance panels there are
unexamined. `trapped-buyers-one-retest` was read at pages 5, 6, 7 and 9, which
cover the twice-failed level, the intraday levels, the retest entry and the tape
read; pages 4 and 10 carry further screenshots that were not opened. Nothing in
the pages read contradicts the consolidated section above, but the refill-effect
gap is the one worth closing if the model decomposition needs more than the p9
and p23 statements.

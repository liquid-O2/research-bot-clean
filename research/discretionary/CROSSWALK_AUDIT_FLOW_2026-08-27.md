# Crosswalk audit, order-flow half of the discretionary library

Audit date 2026-08-27. Baseline audited against:
`design/ENTRY_V2_DISCRETIONARY_FEATURE_CROSSWALK.md` (status 2026-08-19).
Twelve PDFs read in full text; six diagram pages rendered
(`refill-effect` 9/10/11, `fp-lesson-9` 5, `your-mistakes-with-absorption` 11,
`dom-lesson-6` 6). Report is delta only.

## Headline

The crosswalk is accurate about which *quantities* the sources name and it
built faithful continuous versions of nearly all of them. What it dropped is
almost everything that tells you how to *use* them: the sources' own polarity
rules, ordering requirements, location vetoes, stated thresholds, measured base
rates, and one measured decomposition that contradicts the shape of the v8
build. Three losses are severe.

First, `refill-effect` p9/p23 reports the author's own model decomposition:
memory and location features do nearly all the work and **raw order-flow
features alone reach AUC 0.54**, barely above a coin flip. The crosswalk cites
no base rate, no AUC, and no family decomposition from this paper anywhere,
and v8 then spent the bulk of its 1,352 columns on the sub-second flow families
the paper measured as near-worthless. The source that looks most like our
problem already ran our experiment and published which half loses.

Second, `dom-lesson-6` p7 names the exact distinction the mill's Sweep 4
question turns on, and the crosswalk collapsed it into one ledger row.
Absorption and exhaustion both look like price stalling at a level. The
discriminator is volume during the stall, not price. They "point opposite
ways."

Third, the sources gate absorption reads on location with a hard veto, not a
soft weight, and the crosswalk converted every veto into a learnable feature.

## Decisive for rejection-versus-rest

Flagged first because these bear directly on the Sweep 4 live question.

**Quiet at the extreme is the weak case, by the author's own taxonomy.**
`dom-lesson-6` p7: "Big volume with no movement is absorption, someone is
there. Shrinking volume with no movement is exhaustion, nobody is left.
Absorption reverses harder, exhaustion drifts." A quieted extreme is by
construction the shrinking-volume branch. The author assigns that branch a
pause or a fade, "not necessarily a hard reversal," and reserves the hard
reversal for the opposite signature, heavy volume with no price progress. The
mill detects quiet and then asks for rejection. This source says quiet selects
the drift case. The crosswalk's ledger row 4 lists "DOM speed, aggressive
attack, tape acceleration, exhaustion" as one bundle mapping to `disc_evt_` /
`disc_mhi_`, which erases the opposition. Note also that the sources disagree
with each other here: `reading-delta` p8 explicitly treats trapped, exhausted
and absorbed as interchangeable words for one outcome. `dom-lesson-6` says
knowing the difference "is the whole edge." The crosswalk adopted the
conflating source's usage without recording the conflict.

**A frozen tape is stated as ambiguous, and the disambiguator is the passive
side.** `dom-lesson-5` p6: "A tape that freezes at a level is hesitation, or a
big passive order soaking everything up." The author declines to resolve quiet
from quiet. His resolution comes from the passive channel on p7: "Does resting
size hold, reload and stack, or does it pull?" This corroborates Sweep 4's
side-blind failure from the source side, and it points the arbiter at
quote-side behaviour rather than at trade-side quiet. `disc_quote_` and
`disc_absorption_` already carry the raw material. Nothing in the crosswalk
records that the resolution must come from there.

**Spread widening is an early break-predictor and a veto, not execution
geometry.** `dom-lesson-5` p6: the spread "stays one tick when liquidity is
deep and healthy. It widens the instant liquidity thins out, which is your
earliest warning that a level is about to break." And: "SPREAD WIDENS.
Liquidity is pulling. Do not lean on the level." The crosswalk mentions spread
once, in row 13, as candidate execution geometry. At a quieted extreme the
best-quote width and its stability is a cheap, minute-scale, MBP-1-native
rejection-versus-break discriminator, and it is currently filed as a cost term.

**Absence of the opposing side is explicitly not enough.**
`your-mistakes-with-absorption` p9 and p13: "A second, opposite aggression has
shown up, not just an absence of the first side." Rest is exactly absence of
the first side. The author requires positive opposite aggression before the
reversal is "anything more than a hope." This is the cleanest available
statement of the rejection-versus-rest boundary and it is not in the crosswalk,
whose path 2 reads "attack absorbed at remembered location, poor adverse yield,
opposite control" without the requirement that opposite control be *active*.

**The refill edge is measured weakest exactly in compressed volatility.**
`refill-effect` p14: Q4 "lost money at every parameter setting we tried. The
edge is regime-dependent: weakest when volatility compressed late in the
sample." The mill's candidate regime is a quieted extreme. The author's own
out-of-sample record says this is where his version of the same mechanism
fails. Absent from the crosswalk.

**Adverse excursion past the level is expected, not invalidation.**
`refill-effect` p10: "around a genuine defended level, the median eventual
winner first dips 18 ticks past the touch before it works. The defence does not
happen at the front edge of the zone. It happens inside it." The crosswalk's
ordered state is "adverse test -> reclaim -> two-tick lift -> retest." A
two-tick lift threshold against a median 18-tick adverse dip is a mismatch of
roughly an order of magnitude in the same mechanism. Anything that treats an
adverse excursion at the level as a veto will discard the median winner.

**The POC flip is a named minute-scale control-transfer detector that the
crosswalk does not contain.** `fp-lesson-9` p5, confirmed on the rendered
diagram: every candle has its own point of control, and the flip is that
busiest price jumping from one extreme of the candle to the other. "At a key
level, a flip in your direction is confirmation the level is being defended."
This is computable from MBP-1 trades at bar resolution, it answers "who is in
control" directly, and the string "POC flip" does not occur in the crosswalk.
Row 1 exposes session and phase POC as a coordinate; per-bar POC and its
displacement across consecutive bars is a different object.

**Execution side flips the sign of the same signal.** `refill-effect` p11:
identical signals, same engine, same costs, entry order type the only
difference. Resting limit inside the zone returns profit factor 1.80 and 68.8%
wins; market order at the touch returns 0.81 and 27.2% and loses. The crosswalk
treats the whole problem as feature representation plus a classifier and never
records that the sign depends on which side of the book you take. It also
records the coverage cost: the limit fills on 64 trades against the market
order's 312, "less often precisely because it demands the flush that defines
the setup." That is a roughly 5:1 coverage sacrifice buying the sign flip, and
it should be read next to the mill's coverage floors of 0.70/0.40/0.35.

## Per PDF

### reading-delta.pdf (11 pp)

Missing: the **precedence rule** on p6 and p10. When the most recent print at
the level contradicts the highest point of the delta profile, the highest point
wins, and the read flips. "If the highest Delta point contradicts the wick I
was about to trade against, I default to the Delta print." The crosswalk
exposes max event and max one-second attack as features (row 3) but records no
comparison between recent aggression and the level's maximum, which is the
actual decision.

Missing: **level maturity precondition**, p4. "Only apply this to confirmed
lows and finished auctions, never a level that's still being formed," and on
p10, "price has stopped retesting it, not still forming." No
formation-complete flag exists in the crosswalk.

Missing: **invalidation keyed to the highest-delta protected level**, p5. A
break through the highest-delta protected low on the chart signals the trade is
traversing to the stop. Structural invalidation in row 12 is generic distance,
not delta-ranked.

Missing: **the conjunction in method 3**, p9. A large delta print is used only
when paired with a real VP extreme, specifically a low volume node or minor
volume node, and only when the level has produced more than one wick reaction.
The crosswalk splits these into `disc_footprint_` and `disc_auction_` and never
states that the author requires the conjunction and a repetition count of at
least two.

Terminology conflict worth recording: **"refill" here means control changing
hands twice**, p8. Buyers have result, buyers lose result, sellers gain result
confirmed by their own delta print. The crosswalk's row 6 uses "refill" for
trade-conditioned same-price order replenishment. Both meanings appear in the
library and they are different objects.

Anti-pattern not encoded: the wick trap, p6. Buying aggression printing on a
wick reads as absorption and invites a short; it is wrong when the profile
maximum belongs to the buyers.

Anti-pattern not encoded: jumping straight to breakeven, p3. Stated as
"probably the worst thing you can do for your EV."

### your-mistakes-with-absorption (1).pdf (14 pp)

The densest single source of missed conditions in the library.

Missing thresholds and base rates, all stated flat by the author:
- **27% of absorptions fail without a reward system** (p3).
- **The reward system is a three-tick rule** (p3, p4, p13): price must move in
  your direction within three ticks of the absorption print, otherwise the
  absorption is unconfirmed whatever it looked like. The crosswalk's nearest
  object is a two-tick lift.
- **Failed auction return-to-balance runs roughly 72 to 80 percent** (p12). The
  author refuses to round it and the range is kept deliberately. The crosswalk
  carries path 1 with no prior.

Missing hard vetoes, which the crosswalk converted to soft features:
- **POC and mid-balance kill the signal outright** (p6, p10, p13). "Filter it
  out entirely, regardless of how clean the print looks." The same signature is
  "a coin flip at POC and a real signal at a real extreme." His own chart note
  is "THIS IS NOT ABS," not because the print is fake but because the location
  makes it meaningless.
- **Real extremes are enumerated** (p6, p7, p13): shelf, ledge, low volume node,
  minor volume node. Places "set once and stay put."

Missing reliability asymmetry: **current-day VAH/VAL is a lagging recalculating
value, not a level** (p7). Previous day's VAH/VAL is usable because the day is
closed. The crosswalk exposes developing five-minute VA coordinates (row 1) and
prior-session VA (row 2) with no note that the author treats the first as
unsafe for exactly this read.

Missing scope restriction: **absorption is for reversals only** (p5, p13). "You
only use it logically in reversal type of scenarios. You're not using it to try
to catch a continuation of a move." The crosswalk implements `disc_absorption_`
unconditionally and asks CatBoost to learn the context. The author states the
context as a rule.

Missing regime filter with sign: **the CVD median line** (p5, p13). Plot the
median; price above it means directional aggression is bullish whatever an
individual absorption print suggests. "Price is on the correct side of the CVD
median for the direction I'm about to take." CVD appears once in the crosswalk
as a feature name with no median normalization and no side gate.

Missing ordering, four stages plus an entry condition (p8, p9, p13):
aggressive effort, then a passive wall that absorbs rather than fights, then no
reward confirmed by price failing to hold the push, then opposite aggression as
a second energy source. Entry is "on the test of the reward system, not on the
wall itself," and requires "one more retest with a decent amount of refresh
orders in time and sales." The crosswalk's ordered state family is a different
sequence and omits the entry-on-retest requirement.

Missing origin-tracing rule (p10, p11, p13): trace the passive wall back to the
delta spike where control changed hands. The mirror is stated explicitly, same
mechanic at VAH and VAL with opposite direction. `disc_origin_` counts
pre-formation attack bursts but does not link a wall to its originating spike.

Anti-pattern not encoded (p4): entering while the side you are fading is being
refreshed. "If the time and sales or speed of tape shows sellers refreshing and
buyers stepping in instantly to defend, that is buyers defending, not sellers
in control." Refresh on the faded side is a veto, and the crosswalk's refill
features carry no such polarity.

### refill-effect (1).pdf (24 pp)

Largest delta in the library. This is a measured research paper, not a lesson,
and the crosswalk extracted none of its numbers or its negative results.

Missing measurements:
- Base rate: **only 42% of touches hold**; fading every touch loses **-0.285R**
  after costs (p8, p23). The unconditional version of the concept is a loser.
- Selection: out-of-sample AUC **0.63** against a **0.51** scrambled-label
  placebo, 0.2% of shuffles match; hold rate **25% worst decile to 63% best**,
  monotonic; per-slice AUC 0.61 / 0.63 / 0.64 (p9 rendered, p23).
- **Flow-only AUC 0.54** while memory and location carry the model (p9, p23).
- Median winner **dips 18 ticks past the touch** first (p10, p23).
- Deployed configuration, fully specified (p12): resting limit **12 ticks
  inside** the level, **32-tick stop**, **96-tick target**, **cancel after 30
  minutes**, one position at a time, 1-tick round-trip cost, 1 tick stop
  slippage. Result +0.143R, PF 1.19, 30% win rate, ~6.8 trades/day over 542
  trades on 79 untouched sessions.
- Independent engine gives **+0.07R, about half** the research figure, because
  its fills are stricter (p14). The paper quotes both.
- Zone construction scale: a burst of "sixty, eighty, a hundred contracts
  hitting in seconds" (p5).

Missing feature taxonomy: the author's set is **roughly twenty pre-touch
features in four families**, Memory, Construction, Location, Flow and state
(p8). v8 shipped 1,352 discretion columns. The ratio matters given the
unit-weight direction in the mill brief.

Missing negative results and falsifiers:
- **Q4 lost at every parameter setting**, weakest in compressed volatility
  (p14, p23).
- The **fill-assumption artifact** (p10): the first backtest's edge depended
  entirely on which side of the bracket filled first inside a bar. Optimistic,
  heavily profitable; pessimistic, heavily losing; honest middle, a coin flip.
  They discarded it and rebuilt at tick level.
- The **hindsight audit found one leaky feature** (p16): a stored field that
  predicted outcomes **even at a zone's first touch**, impossible without
  contamination. First-touch uninformativeness is a concrete leak test and it
  is not among the crosswalk's eight cheap-evidence items.
- Robustness battery items the crosswalk's evidence list lacks: reverse split
  (train late, test early), rotating folds, a 100-configuration parameter
  plateau with train-to-test rank correlation 0.92, and the mechanism test,
  "overfit patterns do not care how you execute; a real liquidity mechanism
  does" (p16, p17, p18).
- Limitations stated (p22): 79 sessions is one regime slice; limit fills assume
  a fill when price trades at or through the level, and "real queues are less
  kind"; costs are modelled, not lived.

Missing policy: **the -4R daily stop is worth about fourteen points of pass
rate at every size tested**, the single largest lever found and "nothing to do
with the entry" (p21, p23). Payout is structurally capped near $2,000 per
cycle; scale by account count, not size. The crosswalk's policy row carries
K=1 and <=12/day with no loss-based daily halt.

### trapped-buyers-one-retest.pdf (13 pp)

Missing prerequisite: **the level must fit price or be redrawn** (p3, p12).
"Order flow reads are only as good as the level underneath them," and he
redraws an ill-fitting balance before trading rather than forcing the read. No
level-quality or level-fit gate exists in the crosswalk.

Missing repetition condition with separation (p5, p12): "One failed push is
noise. Two failed pushes at the same price, in two different sessions, hours
apart, is the market telling you where it isn't willing to trade." Minimum
count of two, and the two must sit in different sessions. `disc_test_` counts
candidate-local tests without the cross-session separation requirement. He also
states a monotonic claim in the opposite direction to decay: "every hour it
held made a break less likely, not more."

Missing polarity: **heavy one-sided delta at an extreme is a flag for trapped
positioning, not a directional signal** (p4, p12). Path 7 in the crosswalk
covers effort-versus-reward divergence but not the sign inversion.

Missing undershoot tell (p6): price reaching "close to the intraday upper
extreme without fully tagging it" counts as buyers coming up short. The
crosswalk has overshoot in `disc_fvol_` and no undershoot-of-level feature.

Missing tape conditions at the fill (p9): aggressive selling printing **inside
the candle bodies rather than sitting passively on the offer**, and **bar after
bar rather than one isolated print**. Two conditions, body-versus-extreme
placement of the aggression and persistence across consecutive bars, neither in
the footprint row.

Missing two-wait structure with an abstention branch (p6): breakout, then
retest, and "if the retest didn't come, the plan was to stand aside and look
higher up instead."

Missing sizing rule (p8, p12): the target must not depend on above-average
session movement. He names Asia's typical run at 150 to 160 points and
deliberately targets well inside it. `disc_target_` has room/ATR but no
session-typical-range constraint.

### whos-in-control.pdf (12 pp)

Missing the primary polarity rule of the document (p4): **an aggressive arrival
at the extreme means expect it defended; a slow grinding arrival means expect
it broken.** "The same extreme, reached two different ways, is two different
situations." This is the first filter, applied before any level or retest, and
it is the source's own answer to who is in control at arrival. The crosswalk
has arrival features and no statement of their sign.

Missing side-flip rule (p5, p11): if the retest fails to hold, flip the read to
the other side rather than forcing the original. A failed retest is positive
evidence for the opposite side, not merely a missing confirmation.

Missing abstention as a first-class state (p7, p11): at the old balance
"neither side could push and hold: a retest would push back higher, but not
maintain it, then the same pattern would repeat. That's not indecision to trade
around, it's the market explicitly not giving you anything yet." No trades were
taken through the whole stretch. The crosswalk has twelve confirmation paths
and no no-control state.

Missing level eligibility gate (p10): everywhere else in the range control is
"free game," and only at a level that has already been broken and retested does
the read hold. Control is not readable at an arbitrary price.

Missing amplitude claim (p6): a control transfer from a level with trapped
buyers behind it is "a more amplified move" than the same transfer with no
trapped inventory. That is a target-size consequence, not a direction call, and
the crosswalk carries trapped inventory only as a direction path (path 10).

Missing two-timescale agreement requirement (p9, p10, p11): the higher
timeframe read is a bias, not a trade, until the lower timeframe agrees; his
default drop is to the 15 minute. The crosswalk is single-snapshot with
multi-window clocks and encodes no agreement gate between two scales.

Missing effort-without-result plus failed-retest ordering (p9): aggressive
selling with no reaction lower, then a planned retest to see whether sellers
could still assert control, then the reversal when they could not. Two stages,
and the second is a deliberate test.

### fp-lesson-8.pdf (8 pp)

Missing semantics for stacked imbalances (p6, p7): three or more in a row build
**an unfinished auction, and "the market tends to return and finish it."**
Stacked imbalances and single prints are the footprint's version of poor highs
and lows, "magnets and targets." The crosswalk counts consecutive stacks in
`disc_footprint_` as pressure evidence and builds `disc_target_` from profile
objects only. Unfinished business as a target object is missing entirely.

Missing minimum count (p6, p7, p8): "A single imbalance is noise." "Two or
three flagged imbalances in a row at a level is real pressure, one alone is
noise."

Missing threshold band (p5, p8): the standard imbalance flag is **3x to 4x**
against the diagonal opposite, "below that it is noise." The crosswalk fixed
350% without recording the band or the author's noise floor.

Missing per-bar profile objects (p6): the footprint draws its own value area
and POC inside each candle, and "the candle POC is where the heaviest business
traded, and it behaves like a magnet on the retest." Distinct from session POC.

Missing approach-quality conditional (p7): "A level hit by exhausted aggression
behaves differently to one hit by fresh conviction." Read the diagonals into
the level before reading the level.

Missing pairing requirement (p3, p7): the footprint shows the completed result
and shows no pace; the DOM shows pace and no history. "That is why the two are
read together."

### fp-lesson-9.pdf (8 pp)

Missing the signed disagreement rule (p3, p4): bullish absorption is a
**bullish candle with negative delta**; bearish absorption is a **bearish
candle with positive delta**. "The disagreement IS the signal. Agreement is
just a trend." A two-term sign product at bar scale, cheap and MBP-1-native,
and not named in the crosswalk.

Missing the POC flip (p5), covered above under decisive findings.

Missing the named divergence taxonomy (p6). Regular divergence is a new price
extreme without a new delta extreme, "running on fumes." Exhaustion print is a
huge delta bar where price refuses to extend, and the author gives a timing
estimate: **"the turn is usually one or two candles away."** The crosswalk has
neither name nor the timing.

Missing precedence rule (p6): "When they disagree, believe the delta."

Missing the ordered confirmation stack (p7): level, then absorption, then flip,
in that sequence, and "one tell is interest, two is a trade."

### dom-lesson-5.pdf (8 pp)

The frozen-tape ambiguity and the spread warning are covered above.

Missing the four-channel requirement (p6): depth is what is resting, delta is
who is aggressive, speed is how urgent, spread is how healthy. "Read all four."
The crosswalk carries all four as separate families and never states that the
read requires their conjunction.

Missing the conditional branch on fast tape (p6): fast tape into a level means
committed aggression, and then it forks. "If the level still holds, that is
absorption worth trading. If it breaks, the speed carries the continuation."
Same input, opposite trades depending on the outcome.

Missing the crisp two-way rule (p7): "Aggression with movement is
continuation. Aggression without movement is absorption." The crosswalk has
price yield per attack as an unsigned continuous quantity.

Missing the levels-first ordering (p7, p8): "Never watch the DOM in a vacuum.
Come to it with the shelf, the ledge or the value edge already marked." The DOM
"confirms locations you already marked, it never invents them."

### dom-lesson-6.pdf (8 pp)

The absorption-versus-exhaustion split is covered above and is the single most
important item in this document.

Missing named object: **stopping volume** (p7), "a single burst of huge volume
that halts a trend dead. It is absorption at its most violent, the last
aggressive push meeting a wall, and it often marks the turn."

Missing windowing requirement (p4): "Reset the DOM before price arrives. Clear
the counts so what you are reading is only the fight at the level, not an hour
of noise." The crosswalk's adaptive clocks are trailing windows over the last
N messages, trades or units, which is a different anchor. An arrival-anchored
reset is not the same object as a trailing window and neither is in place.

Missing zone tolerance (p4): "Absorption is not always one price. 300 buy
orders can get eaten across 3 ticks. Watch the zone, not just the single tick."
The crosswalk is built on exact per-price signed executions with a
price-coordinate bijection. A roughly three-tick aggregation band around the
level is required by the source.

Missing entry shape (p4): the fake break. "The DOM shows heavy opposing orders,
it looks like your level is about to break. If price rejects fast and moves
your way instead, that was institutions absorbing." Apparent break then fast
rejection, not a quiet hold.

Missing precedence (p4, p8): "Watch the market orders, not the limits. Limit
orders are intentions, market orders are actions."

Missing signed pull conditions (p5): "Bids pulling while bid delta is positive
means buyers just lost their support." Pull is read jointly with delta sign,
and "delta is the referee."

Missing timing condition on the pull (p6): "Stacked size that vanishes as price
approaches was never real." The vanish must be timed against price approach,
not against the clock.

### dom-lesson-7.pdf (8 pp)

The crosswalk's fill-conditioned cancel-versus-reload proxy (row 6) matches the
author's core tell, "an iceberg REPLENISHES as it trades, a spoof VANISHES
before it trades" (p5). What is missing sits around it.

Missing second confirmation and its threshold (p4): after confirming the
reload, "wait for more participants to add on **within 2 ticks**" before
entering.

Missing spoof signatures beyond cancel-without-fill (p6): the **flicker**,
orders appearing and vanishing repeatedly within seconds without ever filling,
which is a repeat-cycle count at one price rather than a single lifetime; **odd
placement**, size posted far from normal resting levels or at strange
attention-seeking amounts; and **fast cancels** triggered when aggressive
orders hit *near* the level rather than at it.

Missing two named games (p7). **Layering** is a ladder of fake orders across
several prices, and its tell is that "the whole stack pulls together the moment
price approaches." **Flipping** is size jumping bid to ask and back faster than
a real order manager would work, with the tell that "no prints trade, only the
display flickers." Layering is largely unobservable at MBP-1 and belongs in the
fidelity-limits section rather than the feature ledger. Flipping is observable,
since it needs only top-of-book size on both sides plus the trade stream, and
it is not implemented.

Missing the unifying ratio (p7, p8): "the single reliable filter under all of
it is the refresh rate against the prints." Quote churn per traded contract.
"If the size keeps changing but the tape is silent, it is a lie." The crosswalk
has quote churn and trade counts in separate families and never forms the
ratio.

### data-engine.pdf (9 pp)

Mostly process material that the crosswalk's last row legitimately declines to
convert into predictors. Three items are method, not narrative, and were not
converted into the audit discipline either.

Missing determinism criterion (p3): "If two people following your rules would
take different trades, it is not a process yet."

Missing the discovery procedure (p3): "Compare all winners against all losers.
The recurring similarities are the actual edge." Winner-versus-loser contrast
rather than outcome classification.

Missing pre-deployment gates (p8): win rate from a 100-plus-trade sample,
average RR, and **max consecutive losses from a Monte Carlo run**. "If any of
the three is unknown, the model is off limits." The crosswalk's eight
cheap-evidence steps include no consecutive-loss requirement.

Also absent, and probably deliberately out of scope, is the asymmetric
compounding sizing model (p7): risk 1% plus the streak's banked profit, only
after a two-trade winning streak, reset to base after the second win, never
raise the base above 1%.

### code-3-orderflow.pdf (8 pp)

Missing parameter change with a stated reason (p7): **set the value area at 40%
instead of 70% for intraday work.** "The tighter range produces cleaner, more
frequent reactions at the edges." The crosswalk builds developing and prior
value areas with no note that the author uses a different width intraday, which
changes what counts as an extreme.

Missing the three-state map (p6): "Price can only do three things: stay in a
balance, leave a balance, or return to a previous one." The crosswalk's regime
family carries balance fade and expansion continuation, two states, and no
return-to-a-previous-balance destination.

Missing the veto restated (p6): "If your level sits inside a balance, avoid
trading it. Choppy, low edge, the auction has not decided anything there."
Second independent source for the mid-balance veto.

Missing objective definition (p6): single prints from the TPO chart, plus
balances, are "the destinations price trades between," and the fill state
conditions the bias, "rejection from a balance with an unfilled single print
above: bullish bias." Unfilled single prints as targets agrees with
`fp-lesson-8` p6 and appears in neither the target row nor the target family.

Missing bias validity zone (p7): "Treat the thesis like a box. While price
respects the box, the bias lives. The moment price violates it, build a new
bias, do not defend the old one."

Missing exit-family split by account type (p4): funded accounts favour fixed RR
plus one partial because "the drawdown rules punish creativity"; personal
accounts trail and leave runners. The crosswalk's policy row has one exit
policy.

## Consolidated

### Vetoes the ledger turned into features

The sources state four hard filters. The crosswalk turned each into a
continuous input for CatBoost to weigh, which is a real change of meaning
because the author's claim is that the signal has no information at these
locations, not that it has less.

1. Absorption at or near POC, or inside balance, is filtered out entirely
   regardless of print quality (`your-mistakes-with-absorption` p6, p10, p13;
   `code-3-orderflow` p6).
2. Absorption is used for reversals only, never continuation
   (`your-mistakes-with-absorption` p5, p13).
3. Do not lean on a level while the spread is widening (`dom-lesson-5` p6).
4. Do not enter with perceived pressure that smells like a spoof; wait for real
   prints (`dom-lesson-7` p6).

### Stated numbers the ledger genericized

Every one of these is an author-stated constant that v8 replaced with a
continuous family. The crosswalk's line "No author threshold is treated as
truth" is a defensible engineering choice, but it was applied without recording
what the thresholds were, so they cannot be tested as candidate cut points now.

| Quantity | Source value | PDF, page |
|---|---|---|
| Reward-system window | 3 ticks, in your direction, after the print | absorption p3, p4 |
| Crosswalk's analogue | 2-tick lift | crosswalk row 12 |
| Median winner's first adverse dip | 18 ticks past the touch | refill p10 |
| Resting-limit entry depth | 12 ticks inside the level | refill p12 |
| Stop / target | 32 ticks / 96 ticks, cancel at 30 min | refill p12 |
| Absorption zone tolerance | ~3 ticks, not one price | dom-6 p4 |
| Add-on confirmation proximity | within 2 ticks | dom-7 p4 |
| Diagonal imbalance flag | 3x to 4x | fp-8 p5 |
| Stacked imbalance minimum | 2 to 3 in a row; 3+ = unfinished auction | fp-8 p5, p6 |
| Zone construction burst | 60 to 100 contracts in seconds | refill p5 |
| Intraday value area | 40%, not 70% | code-3 p7 |
| Failed-auction return to balance | 72 to 80% | absorption p12 |
| Absorption failure without reward | 27% | absorption p3 |
| Touch hold base rate | 42%; fade-all = -0.285R | refill p8 |
| Flow-only grading skill | AUC 0.54 | refill p9 |
| Repeat-test minimum | 2 failures, different sessions | trapped-buyers p5 |
| Exhaustion-print turn latency | 1 to 2 candles | fp-9 p6 |
| Daily loss halt | -4R, worth +14 pts pass rate | refill p21 |

### Ordering requirements lost

The ledger's state family encodes one canonical order, "adverse test, reclaim,
two-tick lift, retest." The sources specify at least four different orders, and
they are not interchangeable.

- Effort, passive wall, no reward, opposite aggression, retest of the reward
  system (`your-mistakes-with-absorption` p9).
- Level, absorption, POC flip (`fp-lesson-9` p7).
- Wall, flush into the zone, refill by fresh orders (`refill-effect` p10
  diagram).
- Breakout, retest that holds, continuation, with a side flip if the retest
  fails (`whos-in-control` p5).

### Anti-patterns the implementation did not encode

- Entering on the absorption print itself rather than after confirmation
  (absorption p4).
- Entering while the side being faded is actively refreshing (absorption p4).
- Trading the absorption signature at POC (absorption p6, p10).
- Using today's still-moving VAH/VAL as a fixed extreme (absorption p7).
- Reading the recent wick print instead of the profile's maximum delta print
  (reading-delta p6).
- Jumping straight to breakeven (reading-delta p3; code-3 p3 qualifies it,
  "not too early").
- Chasing the touch with a market order, which flips a 1.80 profit factor to
  0.81 (refill p11).
- Trusting a bracket backtest whose result depends on intrabar fill order
  (refill p10).
- Trading a level that does not actually fit price, instead of redrawing it
  (trapped-buyers p3).
- Forcing a read through genuine chop instead of standing aside
  (whos-in-control p7).
- Trading a single imbalance, or a delta print with no VP level under it
  (fp-8 p6; reading-delta p9).
- Trusting displayed size without checking whether prints are trading into it
  (dom-7 p7).

## Ten most consequential missed details

Ranked by expected effect on the rejection-versus-rest arbiter and on whether
the next fit repeats a measured failure.

1. **Raw order flow alone grades at AUC 0.54; memory and location carry the
   model.** `refill-effect (1).pdf` p9 and p23. The library's one quantitative
   paper already decomposed a near-identical problem and found the flow half
   near-worthless, which is the shape v8 built and lost with. Any new
   composite should be weighted toward level memory and location before flow.

2. **Absorption and exhaustion look identical in price and split on volume
   during the stall, and they point opposite ways.** `dom-lesson-6.pdf` p7.
   Big volume with no movement is absorption and reverses hard; shrinking
   volume with no movement is exhaustion and drifts. The mill's quiet detector
   selects the drift branch by construction.

3. **The median winner first dips 18 ticks past the touch; the defence happens
   inside the zone, not at its front edge.** `refill-effect (1).pdf` p10. Any
   invalidation that treats adverse excursion at the level as a veto discards
   the median winner, and a 2-tick lift threshold is off by roughly an order of
   magnitude against this.

4. **Entry order type flips the sign of identical signals: resting limit 1.80
   profit factor versus market order 0.81, at a 5:1 cost in fill count.**
   `refill-effect (1).pdf` p11. Coverage floors and execution side are the same
   decision, and the crosswalk records neither.

5. **Absence of the opposing side is not confirmation; positive opposite
   aggression is required.** `your-mistakes-with-absorption (1).pdf` p9 and p13.
   This is the sharpest available statement of the rejection-versus-rest
   boundary, and rest is exactly the case the author rules out.

6. **Aggressive arrival at an extreme means expect it defended; slow grinding
   arrival means expect it broken.** `whos-in-control.pdf` p4. The source's own
   first-pass side call at a level, stated as a rule, exposed in the crosswalk
   as an unsigned feature.

7. **The three-tick reward system, and 27% of absorptions failing without it.**
   `your-mistakes-with-absorption (1).pdf` p3, p4, p13. A concrete confirmation
   window and a stated failure rate, replaced in v8 by a two-tick lift and no
   base rate.

8. **The POC flip: per-bar point of control jumping from one extreme of the bar
   to the other marks control changing hands.** `fp-lesson-9.pdf` p5. A named,
   minute-scale, MBP-1-computable control-transfer detector that appears
   nowhere in the crosswalk.

9. **Location vetoes are hard, not soft: POC and mid-balance kill the signal
   outright, and real extremes are enumerated as shelves, ledges, low volume
   nodes and minor volume nodes.** `your-mistakes-with-absorption (1).pdf` p6,
   p10, p13, seconded by `code-3-orderflow.pdf` p6. The crosswalk turned all
   four vetoes into learnable weights.

10. **The refill edge is regime-dependent and weakest when volatility
    compresses; Q4 lost at every parameter setting.** `refill-effect (1).pdf`
    p14 and p23. The mill's target regime is a quieted extreme, which is
    precisely where the author's own out-of-sample record fails.

Two near-misses worth naming: the spread-widening break warning
(`dom-lesson-5.pdf` p6), which is a free minute-scale discriminator currently
filed as a cost term; and the leak test from `refill-effect (1).pdf` p16, that
any feature predicting outcomes at a zone's **first** touch is contaminated by
construction.

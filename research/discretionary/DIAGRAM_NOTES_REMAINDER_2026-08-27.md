# Diagram-level notes, the remainder of the discretionary library

Date 2026-08-27. Third and last diagram pass. `DIAGRAM_NOTES_FLOW_2026-08-27.md`
read the order-flow half's core figures; this file reads everything that pass
skipped plus every chart-bearing page in the structure/process half. It is a
companion to both crosswalk audits and does not restate them.

Standing law applies throughout: **absolute tick and dollar figures below are
the source's own, on NQ/MNQ, and are recorded as form only — measure the
equivalent on our assets before using any of them.** Where a rule can be stated
self-scaling (percentile, ATR multiple, spread multiple, fraction of zone
height) it is stated that way and the source's absolute number is kept beside
it as provenance.

Pages read at full resolution in this pass: `refill-effect (1)` 5, 7, 12, 14,
15, 17-21; `trapped-buyers-one-retest` 4, 10; and the chart-bearing pages of
the seventeen structure-half documents listed below. Completeness note at the
end.

---

## Consolidated: the new computable rules these diagrams add

Everything below is *new* against `DIAGRAM_NOTES_FLOW`, `CROSSWALK_AUDIT_FLOW` and
`CROSSWALK_AUDIT_STRUCTURE`. Rules already carried by those three (18-tick adverse
excursion, the 3-tick reward system, limit-versus-market 1.80/0.81, AUC 0.54,
absorption-versus-exhaustion, the hard POC/mid-balance veto, the POC flip) are not
repeated. Ordered by expected effect on the fade.

**1. The trigger is a comparison between defences, not a single defence.**
`18k-payout-session.pdf` p7: "A level does not become the trade because price
touched it. It becomes the trade when the same side defends it a second time, **with
more conviction than the first**." The first two attempts at that exact level "did
not have that participation and were let go." `origin-of-the-move (1).pdf` p10 says
the same from the other side: "No result, twice, from the same participants is as
loud as the tape gets." Computable and self-scaling: require defence strength at
touch *k* to exceed defence strength at touch *k-1*, where strength is
absorbed-volume or refresh-size normalised to the level's own first defence. This
converts multi-peak from a *condition* into the *signal*, and no absolute unit is
involved.

**2. The wall test is a two-slope regression over the refresh sequence, and the
information is in refreshes two and three.** `18k-payout-session.pdf` p11: real size
"refreshes at a roughly steady pace and a roughly steady size... a genuine defender
does not run out of appetite three prints in"; fake size shows "each refresh a
little smaller than the last, **the pacing between them stretching out**, until it
stops coming back at all. That thinning is what precedes the level finally giving
way." Computable: over the refresh sequence at a price, regress replaced-size on
refresh index *and* inter-refresh interval on refresh index; a wall is flat/flat, a
failing level is negative-size *and* positive-interval. Self-scaling by normalising
size to the first refresh and interval to its own median. `dom-lesson-7.pdf` p7 gives
the companion filter as a dimensionless ratio: **book-size churn at a price divided
by traded volume at that price** — "Prints are truth, the display is a story."

**3. The quiet failure is a tape-speed gap, and the author says it is the more
common case.** `origin-of-the-move (1).pdf` p14: "The squeeze fails with **no
aggressive orders at the failure at all: the speed of tape just dies. The absence of
result is itself the signal, and it is the quieter, more common version of this
model.**" The figure shows a dense Speed-of-Tape cluster followed by a visible gap.
Computable and self-scaling: tape-speed (prints or aggressive volume per unit time)
collapsing below a low percentile of its own recent distribution *at the level where
the squeeze should have delivered*. A detector built only on visible absorption
prints misses the majority case by the source's own account.

**4. Delta's sign is conditioned on location — at an extreme it inverts.**
`trapped-buyers-one-retest.pdf` p4: heavy one-sided buy delta concentrated in the
top rows of the profile at a recent high is "**a flag to watch for exactly this, not
a reason to join the buyers**," because those buyers become forced sellers. Against
this, `a-clean-continuation-short.pdf` p4 reads stacking negative delta into a
resistance node as confirming the short. The two reconcile on *whose* delta it is
relative to the level, not on raw sign. And `ny-am-session (1).pdf` p7 supplies the
counter-example that stops this becoming a magnitude rule: strongly negative CVD
(panel scale -500 to -900) into a level **did not** carry the break and the short was
stopped. Computable: use per-price delta from the profile, signed relative to the
level's defending side, never raw bar delta magnitude as a break predictor.

**5. Deceleration into the level is the trigger, not arrival at it.**
`ny-am-session (1).pdf` p10: "**The move up is losing aggression candle by candle,
not gaining it**... which is the tell I was waiting on, not just fading a level
because it's a level." Computable and self-scaling: require a negative slope on
aggressive volume or CVD rate over the approach leg. This is the first-difference
form of `whos-in-control` p4's arrival-mode rule, and `fp-lesson-8.pdf` p7 states the
footprint version — "A level hit by exhausted aggression behaves differently to one
hit by fresh conviction," measured on the diagonals *on approach*.

**6. A hard abstention gate keyed to profile modality, and a permission table keyed
to day type.** `reading-the-volume-profile.pdf` p9 on the trending profile: "when you
see one, **get off. There's nothing to trade**... A trending profile isn't a setup,
it's a signal to stop looking for one," with the named failure being repeated
counter-trend re-entry until the account is gone. `amt-lesson-1.pdf` p10 gives the
table: Trend Day "**continuation only, never fade it**"; Normal Day "**fade the
extremes, target the POC**"; Non-Trend Day "the edge is knowing there is no edge."
`amt-lesson-1.pdf` p11 adds a cheap early classifier — Open Drive vetoes the fade,
Open Auction sanctions it — and `tpo-lesson-3.pdf` p8 adds a third from the initial
balance (first hour; IB holds all day permits the fade, IB breaks early one-sided
forbids it). Three independent classifiers that can be required to agree. All are
computable from bar data; none needs a tick constant.

**7. Excess versus poor extremes inverts the trade, and the marker's reliability is
asset-dependent by the source's own statement.** `tpo-lesson-3.pdf` p6-p7 and p9:
excess is ">=2 rows of the same letter at the extreme", finished business, "**expect
those extremes to hold on first test**"; a poor high or low is flat with no taper,
"unfinished business the market tends to revisit", i.e. a *target*, not a level to
fade from. And the porting law stated by the source: "**On NQ** poor highs and lows
usually appear as a single TPO tail and they are useful... **On ES** the thicker
market structure creates shorter, firmer tails. Poor extremes are less reliable on ES
and rarely used." Form only; measure on our assets — asserted here by the author, not
imposed by us. Note item 3 of the p9 checklist is the **only** sanction in the
library for acting on a first touch, and it applies solely at an excess extreme.

**8. Ledges are stationary; VAH/VAL/POC are not, and that is the actual objection to
using them.** `vp-lesson-2.pdf` p5: "VAH, VAL and POC are useful, but **they
recalculate as price moves. They drift with the session, like a lagging indicator. A
ledge does not move.**" `mastering-amt-vp (1).pdf` p3 states the same as rule three,
"**STOP USING VAH/VAL for levels**." Computable: anchor zones to volume-density
regime changes (the price where build-up starts or fade-away begins — an edge
detection on the volume histogram) with a **fixed birth time**, not to a recomputed
value-area boundary. Any backtest keyed to intrasession VAH/VAL is quietly using a
moving anchor.

**9. Penetration depth does not establish acceptance; failure to sustain from inside
does.** `amt-on-live-markets.pdf` p10: price "**dipped meaningfully into the previous
balance, deep enough that a less patient read might have called it accepted. It still
failed to actually hold and trade lower from inside it**... The rejection was real, it
just took longer to confirm than the textbook version does." This is the
structural-scale twin of the refill paper's 18-tick result, and it generalises the
correction: acceptance is a **dwell-time and rotation-count** measurement, not a
distance one. `amt-on-live-markets.pdf` p6 gives the same test in its cleanest form —
acceptance is "price spending time there and building structure", rejection is "price
enters an area and quickly moves away from it" — which needs no tick constant at all
and is the most portable statement of the rejection-versus-rest boundary in the whole
library.

**10. Level quality is not cacheable; it must be recomputed on each visit.**
`amt-on-live-markets.pdf` p11: a week-long established balance, revisited on a
dump-through basis, is reclassified as an LVN void — "price simply dumped straight
through and is now holding at the lower extreme instead, the low volume node behavior
from earlier in the document." `a-clean-continuation-short.pdf` p7 says the same of
HTF low-volume nodes: price "stalls and tries to build balance there, or, if there's
enough selling pressure, it slices straight through," with the delta print at arrival
naming the branch. Computable: an LVN is bimodal, not a fade target by construction,
and the branch is selected by aggression present at the moment of arrival.

**11. The resting order is itself the filter — stated as design intent, not just as
a statistic.** `origin-of-the-move (1).pdf` p12: "**The order rests below the wick so
only aggressive continuation can tag it in. If sellers don't come with result, there
is no fill and no trade. The order type is doing the filtering.**" Same page: a
stop-out does not invalidate the read — "the re-entry sits right below, and the read
has not changed." Computable: coverage floor and execution side are one decision, and
the fill rate is a *feature of the setup definition*, not a cost to be minimised.

**12. The trail carries a large, measurable share of the realised edge, and it is
event-driven.** `ny-am-session (1).pdf` p8-p9 measures it on a single trade: entry at
**R:R 0.69** on a 58-tick / -$290 fixed initial risk, exit at **R:R 1.83** purely
from trailing — a 2.65x improvement with the entry and initial stop held fixed.
`18k-payout-session.pdf` p8 defines the mechanism: the stop moves to each new
"protected high" that "closed with real speed of tape behind it", walking "one
protected high at a time **rather than by a fixed distance**".
`origin-of-the-move (1).pdf` p13 keys the same trail to "each new aggression pocket".
And `origin-of-the-move (1).pdf` p9 defines the **exit as the mirror of the entry**:
"Trail until buyers hit a wall and get fully absorbed: that absorption is the exit."
Consequence for the mill: an entry-acceptance rule that filters on minimum R:R at
entry would have rejected two of the library's best-documented winners.

**13. Two documented entries deliberately violate 1:1 at entry, and the sources say
so explicitly.** `18k-payout-session.pdf` p8: starting R:R 0.69, "it fails the
arithmetic before it fails the read," taken because the level was strong.
`ny-am-session (1).pdf` p8: R:R 0.69, "Most traders would skip that outright."
Against this, `2345-funded-session (1).pdf` p7 plans **R:R 5.59** and
`a-clean-continuation-short.pdf` p8 plans **6.11** on a re-entry. The method spans
nearly an order of magnitude in entry geometry, so R:R is an output of level quality
plus exit policy, not an input filter.

**14. Re-entry has two different stated gates, and neither is a count.**
`a-clean-continuation-short.pdf` p8: re-enter only once "the same level kept behaving
the same way on repeat — Sellers had control, price went lower. Price came back up to
the level, sellers had control again. It went lower again," i.e. **an additional
completed cycle by the same side at the identical price**, and the re-entry is sized
at a materially wider ratio (6.11) than the first attempt. `origin-of-the-move (1).pdf`
p12: the re-entry level is **pre-placed below the stop** and "the read has not
changed." Against both, `10k-first-month (1).pdf` p13 records the anti-pattern —
three shorts, same level, same 20-tick stop, same ~5.00 R:R, all losing — with the
veto: "a short like this one doesn't get taken at all, **regardless of how clean the
local order flow looks**", because HTF absorption at the opposing level had already
set the bias. Same page adds a level-set invalidation: once a two-weeks-untested level
finally broke, "everything below it stopped being a place to sell from."

**15. Concurrency is gated on the open position's risk state, not on a position cap.**
`18k-payout-session.pdf` p10: "the fourth trade was affordable specifically because
the third one was no longer at risk." Computable: permit a second position once the
first has a stop locked beyond breakeven.

**16. Two session-level governors, both self-scaling, one on each tail.** Left tail:
`refill-effect (1).pdf` p21, "**stop trading for the day once you are down four risk
units**", worth ~14 points of evaluation pass rate, and — the part the earlier passes
did not carry — **the benefit grows with risk size** (+3 at $40/R, +13/+14 at
$120-150/R), so it is a fat-tail truncation whose value scales with exposure. Right
tail: `2345-funded-session (1).pdf` p9, a target "capped by a funded account
consistency rule: a prop firm payout requirement that no single day can represent too
large a share of total profit", plus a session-completion stop independent of
remaining signal quality. `ny-am-session (1).pdf` p11 adds the intraday analogue:
risk cut to ~$100 "deliberately small this late in the day with the objective already
close."

**17. The deployed strategy has a time-stop, and it is a named parameter.**
`refill-effect (1).pdf` p12 and p15: "cancel after 30 minutes, one position at a
time", and the engine's own parameter string reads `Aggression-Memory Tick ·
rest_min=30 variant=3 entry_in=12 t_minutes=30 sl_ticks=32 tp_ticks=96`. Two things
here are new: the **30-minute working-order life** as a first-class parameter (an
unfilled resting order at a zone is withdrawn, not left working), and `variant=3`,
which reveals the zone-construction rule is one of several enumerated variants rather
than a unique definition. Self-scaling restatement of the geometry: entry depth ≈
0.375 × stop, target = 3 × stop, time-stop = 30 minutes.

**18. A reusable robustness acceptance criterion, asset-agnostic.**
`refill-effect (1).pdf` p17-p18: sweep the exit cube (stop × target × entry depth),
plot in-sample against held-out average R per configuration, and require a high **rank
correlation (theirs: 0.92)** plus a contiguous profitable region rather than a single
winning cell — "A curve-fit edge is one bright dot in a sea of noise; this is a
coherent warm region. **The parameters barely matter, the concept does.**" Their
profitable region spans roughly stop 30-55 and target 50-100 ticks. This is a
falsifiable protocol we can run on our own sweeps unchanged.

**19. The achievable object is a calibrated ranking, and its ceiling is modest.**
`origin-of-the-move (1).pdf` p17: touch grading out-of-sample **AUC 0.63** against a
stated placebo of **0.51**, and a hold rate running **25% → 63% monotonically across
deciles**, with the caveat "modest by design". Fading every touch unfiltered is
**-0.285R** after costs on a **42%** base rate. Together these say the deliverable is
a monotone grader, not a classifier, and the honest ceiling is small.

**20. Two named, dimensionless flow thresholds that port without calibration.**
`fp-lesson-8.pdf` p5: an imbalance is flagged when one side is "**3x to 4x larger**
than the diagonal opposite" — and p4 specifies the comparison exactly as ask[p]
versus bid[p-1], one tick down, "**diagonal, not side by side**", which a naive
implementation gets wrong. p6 adds the stacking rule: "**Three or more imbalances in
a row build an unfinished auction, the market tends to return and finish it**" (p7
loosens this to "two or three", so treat the count as a tunable in 2-4).
`2345-funded-session (1).pdf` p5 adds the live trigger: "**a 350 percent divergence
between buying and selling aggression alongside a small imbalance**", explicitly
gated by an HTF context where the opposing side was already weak — "that combination
is what separated this from a random entry on a green box alone."

**21. VWAP deviation bands are the one fully self-scaling location gate in the
library.** `vwap-lesson-10.pdf` p3-p4: the median is "the POC of the session so far";
bands at **1, 2 and 2.5** standard deviations; and the two rules — "the trades worth
taking live **beyond the 1 band and ideally at the 2**", and "**only trade VWAP
extremes WITH absorption, never on the touch alone**", with the warning that
"deviation is probability, not a wall." p6 adds three computable CVD reads: a
price/CVD divergence, a breakout grade (CVD slope during the break; flat or falling
CVD implies fakeout), and an absorption detector (price variance near zero while
|CVD slope| stays high). p7 adds anchored VWAP from a zone's own birth time, which is
literally the trapped-inventory breakeven for everyone who traded since the zone was
built. None of this needs a tick constant.

**22. Two stated conditional probabilities with fully specified antecedents, and one
used as a timing veto.** `mastering-amt-vp (1).pdf` p16: "**If the RTH session opens
inside the previous ETH profile's balance, there is a 73% chance** of the session
going on to hit that ETH profile's MPOC, its mid" — used to hold and trail rather
than take the first target. p15: "**94% chance of price touching either the overnight
high or the overnight low** during the current session" — used as a *timing veto*,
which is the novel application: "the level isn't wrong, the timing is," when a stop
sits between entry and an untagged overnight extreme. Self-scaling form: veto when an
untagged overnight extreme lies within roughly one stop-width beyond entry.
`amt-on-live-markets.pdf` p9 supplies a third with its own live tell: after a failed
auction, 80% full traverse versus 20% range-bound, discriminated by POC behaviour —
repeated failure to break and hold POC selects the range branch, aggressive break plus
held retest selects the traverse. `reading-the-volume-profile.pdf` p5 states the same
POC rule independently.

**23. Overnight inventory gives a complete, entirely pre-open session bias.**
`mastering-amt-vp (1).pdf` p14: the window is 6pm to 9:30am NY; "net long overnight,
the path of least resistance at 9:30 is higher, net short, it's lower"; one clean
distribution means the net environment usually continues, while "**a double
distribution and the low volume node between the two humps becomes the decision
point**", respected or disrespected at the open. All three inputs — overnight net
delta sign, overnight profile modality, and the inter-hump LVN price — are computable
before the session opens.

**24. The failed-auction fade has a fully ordered template and a discrimination test
that flips the trade's sign.** `mastering-amt-vp (1).pdf` p10: "**Balance, break, tag
the prior balance's POC, reject**, and the established balance gets its boundary hit
four times out of five." p11 then tests it on two visually near-identical real charts
and gives the discriminator: chart 2 "fails the definition even though it looks
similar: price does break balance and does retest a grey zone, but **it never tags a
*prior* balance and rejects there** — it simply breaks down, keeps going, and the
retest is a trend continuation entry, not a failed auction. **Same visual grammar,
opposite trade.**" Computable: whether the retested zone is a previously-established
balance, plus time-to-reject. `amt-lesson-1.pdf` p8 gives the fadeable-breakout
signature in three self-scaling parts — breakout-bar volume not elevated versus its own
trailing distribution, elevated wick-to-body ratio, and return inside value within a
few rotations.

**25. The default-and-flip pair, with the flip's own target named.**
`a-clean-continuation-short.pdf` p5: "if price comes back to the top of that balance,
the default expectation is shorts, **unless price closes above it with real, extreme
buying pressure. If that pressure shows up, the read flips to a retest and longs back
toward the session's VWAP instead.**" This is the only place in the library where the
fade's invalidation arrives with its own trade attached, and both the flip condition
and the flip target are computable.

**26. Regime selects the exit, not the entry.** `a-clean-continuation-short.pdf` p6:
gamma-long "raises the odds of chop rather than a clean move all the way to the lower
extreme", so a nearer exit was taken *even though POC would also have worked*;
gamma-negative "lines up with why price dropped and dumped." `code-3-orderflow.pdf`
p4 generalises it to the account: "**FUNDED ACCOUNTS — Favour fixed RR plus one
partial. The drawdown rules punish creativity.**" A mill optimising expectancy alone
picks the wrong exit for a barrier-constrained account.

**27. A second, independent zone constructor, and a display threshold for "large".**
`refill-effect (1).pdf` p5 builds the zone from **clustered large aggressive prints**,
with the paper's own display threshold at **>=40 contracts on MNQ** (form only; on our
assets this must be a per-asset percentile of single-print size).
`fp-lesson-8.pdf` p6 builds an equivalent zone from **>=3 consecutive diagonal
imbalances**. These are different constructors for the same object and should be
compared, not assumed equivalent. `dom-lesson-5.pdf` p3 shows the raw field the
refresh test needs is native: a **signed per-level size-change column** on the ladder.

**28. Two more confirmation windows, all different quantities, none interchangeable.**
Adding to the flow file's correction that 3 ticks (favourable, validating) and 18
ticks (adverse, median winner's excursion) must not be merged: `dom-lesson-7.pdf` p4
adds a **2-tick participation window** — after confirming the reload, "wait for more
participants to add on **within 2 ticks**" before entering. That is a *radius for
additional participants*, not a displacement. Three quantities, three purposes, three
signs. All are form only; on our assets each should be re-derived, and the 2-tick one
is naturally a small multiple of the modal spread.

**29. The value-area percentage is a tunable, not a constant — and the library
disagrees with itself about it.** `reading-the-volume-profile.pdf` p4 says "roughly 68
percent"; `mastering-amt-vp (1).pdf` p5 and `amt-lesson-1.pdf` p5 say roughly 70%
(the latter as an explicit platform setting, "set Value Area Volume to 70");
`amt-on-live-markets.pdf` p4 says only "the majority". And `code-3-orderflow.pdf` p7
proposes changing it outright: "**Set the value area at 40% instead of 70% for
intraday work. The tighter range produces cleaner, more frequent reactions at the
edges.**" That last is a directly testable knob on every value-area rule in the
library, and its stated rationale is exactly the coverage-versus-precision trade the
mill is tuning.

**30. Two unresolved conflicts to carry as forks rather than average away.** First,
**P and B shape polarity**: `mastering-amt-vp (1).pdf` p7 says a P (fat top) "resolves
with price breaking down out of the bottom" and B (fat bottom) resolves higher, while
`reading-the-volume-profile.pdf` p10-p11 and `amt-lesson-1.pdf` p6 read P as
underlying trend higher and B as lower. Same library, opposite signs. Second,
**continuation versus reversal preference**: `reading-the-volume-profile.pdf` p6
states its author "trades continuations, and rarely trades reversals, because
continuations give him a higher win rate. **That's a personal statistic, not a claim
about which read is theoretically correct**" — a well-caveated challenge to a
fade-oriented mill from the structure half's most prolific source. Carry it as a
pre-registered two-sided comparison, alongside `average-unprofitable-trader` p13's
point that a stricter filter can produce a worse account.

**Ordering law, asserted independently by five documents.** `vp-lesson-2.pdf` p7:
"**Structure first, confirmation second, execution last.** The profile tells you where
the trade lives, the tape tells you when to take it." `tpo-lesson-3.pdf` p9: "The
profile is context, **never the trigger**." `dom-lesson-5.pdf` p7: "**Bring a level to
the ladder** — never watch the DOM in a vacuum." `code-3-orderflow.pdf` p6: "**Higher
timeframe narrative first, lower timeframe entries second**", with "if your level sits
inside a balance, avoid trading it" stated as a hard veto. `fp-lesson-8.pdf` p7:
"Bring the level — the footprint is the microscope, the level is the slide." This is
the inverse of a flow-first feature mill: location is a gate, not a weighted feature,
and it is the same conclusion the AUC 0.54 result reaches from the data side.

---

## refill-effect (1).pdf

**p5 — the two outcomes of a touch, plus the raw material.** Two panels side by
side under "The two outcomes of a touch". Both draw the identical prefix: a
horizontal shaded band with a cluster of circles sitting on it, captioned "zone
built earlier by large aggressive orders (circles = big prints)", then a
mountain of price leaving the band and an arrow labelled "the touch" bringing
price back down onto it. The panels differ only in what happens at the touch.
Left, "The level HOLDS: defenders are still there", draws a small green
oscillation *inside* the band and annotates "buyers reload inside the zone,
sellers get absorbed". Right, "The level BREAKS: defenders are gone", draws a
red dashed continuation straight down through the band and annotates "nobody
reloads, price cuts straight through". The caption states the whole paper's
question: "Everything in this paper exists to answer, *before the touch
resolves*, which of these two pictures you are in." Below it is a real chart,
"Aggression bubbles: MNQ, 10 Jan 2025, 9:36-9:44 ET", price y-axis 21080-21160,
minute x-axis, with a two-item legend — green "buy aggressor", red "sell
aggressor" — and bubbles overlaid on the candles sized by print size, footer
"bubble size = contracts in the aggressive print (>=40 shown)". Visible bubble
labels read 201, 132, 137, 172, 165 contracts. Caption: "Red sell-bubbles
hammer a level, green buy-bubbles absorb them, and price turns and trends up.
That absorption is the refill." Computable content: the zone object is defined
constructively as *a cluster of large aggressive prints*, not as a price line
drawn by eye, and the paper's own display threshold for "large" is **>=40
contracts** on MNQ (form only; on our assets this should be a per-asset
percentile of single-print size, not 40). The refill is defined as opposite-side
aggressive prints appearing at the same prices that were being hammered, which
is a directly countable minute-scale event.

**p7 — a live read: the level gets tested twice before buyers take it.** A full
real NQ session on Deepchart, roughly 08:31-09:49 on the x-axis, price
29790-29920, with a volume profile pinned to the right edge and a "Speed of Tape
(10)" histogram panel underneath showing green and red bars in bursts. The chart
is annotated with coloured rectangles: purple and magenta boxes are zones built
by clusters of large aggressive orders, and a single large red rectangle spans
horizontally across most of the session at 29810-29835. Four callouts, in
left-to-right order: "level built here, first test: no result" on the left edge
of the red box; "price returns to the same level: no result again" roughly two
thirds across, at the second test; "buyers regain control here" attached to a
small green box drawn *just above* the top of the red level immediately after
that second test; and "level holds, trend resumes" at the top right. The caption
spells the sequence out: "The level (red) is built early and tested twice, once
on the first touch and again on a sharp sell-off back into it, and both times
the sellers get nothing: price holds, not breaks. Right after the second test,
buyers build a small base (green) just above the level and take control." It
closes with the paper's framing of what it is quantifying: "not the entry
trigger, but whether the defenders are still there when price comes back."
Computable content, and this is the cleanest confirmation-entry geometry in the
document: **two no-result tests of the same level precede the trade, and the
confirmation object is a small consolidation base that forms just above (for a
long) the level, not a touch of the level itself.** The base is above the zone
while the resting entry of p12 is inside it — the two are different objects and
the source uses both. The Speed-of-Tape panel is a second minute-scale channel
running under the price: bursts of tape speed coincide with the tests.

**p12 — the out-of-sample record, and the deployed configuration in one
sentence.** Header text states the deployed configuration explicitly: "at a
model-selected zone, rest a limit order **12 ticks inside the level**, stop 32
ticks, target 96 ticks, cancel after 30 minutes, one position at a time, with a
1-tick round-trip cost and 1 tick of stop slippage charged." Tuning used the
first 156 sessions; "the final **79 sessions were never touched** until the
configuration was frozen." Four stat cards: **+0.143R** per trade after costs,
**1.19** profit factor, **+78R** cumulative over 542 trades, **~6.8** trades per
day. Below, a tick-resolved after-cost equity curve, x-axis trade number 0-542,
y-axis cumulative R 0-80, with pink shaded pools annotated "shaded pools =
drawdown, the give-back from each running peak (worst **-16.6 R**)" and an arrow
to the staircase annotated "each stair-step up = one +3R winner". Caption: "Every
one of the 542 trades across the 79 held-out sessions, in sequence. No parameter
was chosen using any of this data." Computable content: the four-part execution
object (entry depth, stop, target, **time-stop**) is a single joint decision, and
the 30-minute cancel is the piece the earlier passes did not carry — an unfilled
resting order at a zone is *withdrawn* after 30 minutes rather than left working.
Self-scaling restatement: entry depth ~= 0.375 x stop distance, target = 3 x
stop, time-stop = 30 minutes of the same clock the zone was built on; worst
peak-to-trough give-back is ~21% of the cumulative R earned over 542 trades, and
~5.5 stop-widths, which is the drawdown budget any live deployment of this shape
must be able to sit through.

**p14 — an independent engine agrees, and one quarter kills it.** A five-row
table with the signals re-implemented inside Quant Charts' tick-level
backtester, "an engine we did not write, with its own fill logic", run over the
full year at default sizing. Rows: Q1 Dec-Mar, 64 trades, 68.8% win, PF 1.80,
+$2,112; Q2 Apr-Jun, 60, 55.0%, 1.28, +$928; Q3 Jul-Sep, 65, 55.4%, 1.73,
+$1,410; Q4 Oct-Nov, 34, 52.9%, **0.76, -$647**; Year, 223, 58.7%, 1.45, +$3,803.
Footnote: "Per-trade expectancy on this engine ~= +0.07R, about half the research
simulation's +0.14R, because its fills are stricter. We quote both rather than
the friendlier one." A red-bordered box headed NOTE THE LOSING QUARTER: "Q4, the
most recent slice, lost money at **every** parameter setting we tried. The edge
is regime-dependent: weakest when volatility compressed late in the sample. We
flag it and count it in every statistic, because an edge that only appears when
losing periods are trimmed away is not an edge." Computable content: the
half-expectancy-under-stricter-fills result is a calibration fact — the same
signal set loses roughly half its edge purely to fill realism, so any backtest of
this family that does not model queue position is quoting roughly double. And
the regime dependence is stated as a **volatility-compression** conditional,
which is expressible as a realised-volatility percentile gate rather than a
calendar quarter.

**p15 — straight from the engine, with the full parameter string.** Raw
unrestyled Quant Charts output for Q1: an equity curve compounding one contract
from a $100,000 base across 64 trades, peaking near $102,600 with an interior
give-back from ~$101,400 down to ~$100,500 around trades 10-28. Beneath it the
engine's own performance summary panel, whose title line is the complete
parameterisation: `Aggression-Memory Tick · rest_min=30 variant=3 entry_in=12
t_minutes=30 sl_ticks=32 tp_ticks=96`. Panel values: Net P&L +$2112.39, Trades
64, Win Rate 68.8%, Profit Factor 1.80, Sharpe 0.22, Max DD -$1051.98, Avg Trade
+$33.01, Largest Win +$475.01, Largest Loss -$300.62. Computable content: this is
the only page in the library that names the strategy object's own knobs, and two
of them are new. `rest_min=30` and `t_minutes=30` make the 30-minute working-order
life explicit as a parameter rather than a footnote, and `variant=3` shows the
zone-construction rule is one of several enumerated variants rather than a
unique definition. Note also that **largest loss (-$300.62) is close to twice the
nominal 32-tick stop** on the same contract scale that gives largest win +$475.01
against a 96-tick target: the realised loss tail runs past the stop, which is
what the 1-tick slippage charge and gap risk buy you. Sharpe 0.22 on 64 trades is
the honest smallness of the thing.

**p17 — a plateau, not a spike.** A scatter of 100 circles, x-axis "average R,
first half (used for tuning)" from -0.4 to +0.3, y-axis "average R, second half
(untouched)" over the same range, with a grey 45-degree reference line. The cloud
is a tight monotone band along the diagonal. Annotation top left: "if the first
half of the data predicts the second half (**rank correlation 0.92**), the result
is not a fluke." A filled dark marker near (0.19, 0.15) is labelled "the setting
we deployed, on a broad plateau, not a spike". Caption: "Each circle is one exit
configuration (**stop x target x entry depth**), placed by its average R on the
first half of the data (x) and the untouched second half (y). Green circles are
profitable in both halves. If the result were curve-fit, this cloud would be
shapeless." Computable content: a directly reusable **robustness test protocol** —
sweep the exit cube, plot in-sample against held-out average R per configuration,
and require a high rank correlation plus a contiguous profitable region rather
than a single winning cell. That is a falsifiable acceptance criterion for our own
sweeps, and it is asset-agnostic.

**p18 — the whole parameter space, two ways.** Two panels of the same object.
Top, a 3-D surface, "The ridge: expectancy across every stop and target", x-axis
target 20-100 ticks, y-axis stop 25-65 ticks, z and colour "expectancy (R,
untouched half)" running 0.000-0.125, with contour lines projected on the floor
and a red "deployed" label sitting on the ridge crest. Bottom, the same 100
configurations as a dark-background 3-D scatter, "The same space, point by
point", stop 25-65 against target 20-100, coloured by average R on the untouched
half from -0.3 (violet) through 0.0 (green/cyan) to +0.1 (red), with the deployed
point ringed in white near the top. Caption: "Both views show all 100
configurations on the untouched half of the data. A curve-fit edge is one bright
dot in a sea of noise; this is a coherent warm region. **The parameters barely
matter, the concept does.**" Computable content: the profitable region is broad in
both axes — expectancy stays positive across roughly stop 30-55 and target 50-100
— so the geometry that matters is the *ratio*, and the source's own ridge sits
near target ~= 3 x stop with the entry depth held inside the zone.

**p19 — inside a funded-account evaluation.** Framing text first: "A per-trade
edge of +0.14R is modest. What makes it valuable is its **shape**: many small
bounded losses, steady drift, and a fat right tail from the 3-to-1 target," which
is "close to ideal for a prop evaluation, which is a race to +$3,000 before a
$2,000 trailing drawdown, not a race for maximum profit." Method: "We replayed the
held-out daily results 4,000 times through a Topstep-style 50K evaluation, with
the consistency rule enforced and one self-imposed policy: **stop trading any day
that reaches -4R**." Left panel, "400 simulated evaluations at $80 per R": a fan of
grey equity paths from $50,000 over 0-60 trading days, a green dashed "$53,000
pass target", a red dotted "fail line (trailing drawdown)" at ~$48,000, one bold
teal path annotated "the typical account passes around **day 27**", and "each grey
line = one simulated evaluation, built from real held-out trading days". Right
panel, "Smaller risk, higher pass rate": bars at 96.7% ($60 per R), 92.2% ($80),
85.7% ($100). Caption: "Almost every path clears the target; only the unluckiest
sequences of losing days brush the fail line." Computable content: the daily
**-4R hard stop** is a session-level occupancy rule stated in R units, therefore
already self-scaling, and it is the first quantified daily-loss governor in the
library.

**p20 — size sets the trade-off between odds and speed.** A combination chart:
teal bars "chance of passing the evaluation (%)" on the left axis against risk
per R on the x-axis, and an amber line "median trading days to pass" on the right
axis. Paired values, bar then line: $40 -> 99.8% / 60 d; $60 -> 98.3% / 39 d; $80
-> 95.0% / 28 d; $100 -> 90.1% / 21 d; $120 -> 85.4% / 17 d; $150 -> 79.6% / 12 d.
Two summary cards: PATIENT SIZING "$60-80 per R: pass rate in the 90s, but you
must be willing to trade for a month or more without forcing the pace"; FASTER
SIZING "$100-150 per R: a pass in 10-20 days, at 80-86% odds. Right when you have
several attempts queued and want turnover." Body text: "Bet size is the one dial
you fully control... There is no free lunch, only a curve you get to choose a
point on." Computable content: pass probability and time-to-pass are a smooth
monotone trade-off in risk-per-R, and the elasticity is steep in time and shallow
in probability — a ~3.75x increase in risk per trade costs ~20 points of pass rate
but buys a 5x reduction in median days. Stated self-scaling: risk per R here is a
fraction of the trailing-drawdown budget ($40-$150 against a $2,000 buffer, i.e.
2%-7.5% of the buffer per trade).

**p21 — the daily stop, and what a pass is worth.** Body text leads with the
finding: "The single most powerful rule we found has nothing to do with the entry:
**stop trading for the day once you are down four risk units.** A
trailing-drawdown evaluation is asymmetric: one runaway losing day ends the
account, while no single good day is worth the same in reverse. Cutting the tail of
bad days off is worth about fourteen points of pass rate at every size we tested."
Top chart, "One rule: stop at -4R a day, add ~14 points everywhere", paired grey
("trade through bad days") and teal ("stop the day at -4R") bars per risk size,
each pair labelled with the delta: $40 +3, $60 +7, $80 +11, $100 +13, $120 +14,
$150 +13. Second body block: "The payout on a funded account is **structurally
capped** near $2,000 per cycle by the same trailing drawdown, and no edge, however
large, lifts that ceiling. The lever for total income is not size, it is **count**."
Bottom chart, "Scale by accounts, not by size", chance of at least one payout
against funded accounts run in parallel: 1 -> 95.6%, 2 -> 99.8%, 3 -> 100.0%,
4 -> 100.0%, 5 -> 100.0%. Caption: "A single funded account reaches a first payout
~96% of the time at $80 per R; three in parallel make at least one payout a
near-certainty. Many small, capped, high-probability payouts, not one big score."
Computable content: the -4R daily stop's benefit **grows with risk size** (+3 at
the smallest size, +13/+14 at the largest), so the rule is not a constant-value
guard but a fat-tail truncation whose value scales with per-trade exposure; and
capital deployment is a count problem, not a size problem, which is a portfolio
constraint rather than a signal one.

---

## trapped-buyers-one-retest.pdf

**p4 — reading trapped buyers on the Delta.** Section headed "heavy buying into a
high can be the reason price turns, not against it". The figure is captioned
"DAILY VOLUME PROFILE WITH DELTA, HEAVY BUYING MARKED AT THE HIGH": a wide
grey-background chart with two daily volume profiles drawn at their sessions,
each profile's rows coloured blue for buy volume and red for sell volume on the
same price axis as the candles, several horizontal levels extended across the
chart, and a red moving-average-like line. The visible concentration of blue rows
sits at the top of the right-hand profile, right at the recent high. Figure
caption: "Blue bars are buy volume, red is sell, read against price on the same
axis. The concentration of blue sitting right at the recent high is the print in
question." The argument in the body is the annotation's claim: at the highs "the
Delta showed heavy buying, and most traders read that as bullish on sight. His
read is the opposite." Buyers who buy into a high and then watch price turn "are
now in a losing position... the moment price fails to keep going their way, they
become forced sellers: exiting isn't optional, it's how a losing trade gets
closed. A wall of buying at a high, in other words, can be the exact fuel a move
lower needs once it starts, not evidence against it." Closing rule: "He treats a
heavy one sided Delta print at an extreme as **a flag to watch for exactly this,
not as a reason to join the buyers**." Computable content, and this is a genuine
sign inversion: **the sign of a large delta imbalance is conditioned on
location.** Away from an extreme, one-sided buy delta is directional evidence; at
a session/composite extreme it is trapped-inventory evidence and biases the fade
in the *opposite* direction to the delta's sign. The measurable object is
delta-at-price concentrated in the top rows of the profile (per-price delta from a
volume profile, not per-bar delta), and it is explicitly a *flag*, not a trigger —
it arms the watch, and something else has to fire.

**p10 — the result, and what "to the tick" is claiming.** The figure is an
execution-panel screenshot overlaid on the same daily-profile chart, captioned
"REALIZED P&L ON THE FILL: $501.50", showing a Tradovate ticket on MNQ with a
shaded position box spanning entry down to exit and horizontal level lines
crossing the chart at the entry and exit prices. The methodological annotation
under the figure is unusually explicit and worth carrying: "Read directly off the
execution panel rather than off the spoken number, which whisper's transcription
of this clip garbled into something unrelated. The panel is the source of truth
here, not the audio." The body's claims: the fill "on both ends lines up with the
exact levels marked well before either one printed. Nothing about the exit was
improvised." And the trade-shape claim: "This wasn't a trade sized up chasing a
home run figure. It was a normal size, on a level built from **three independent
confirmations**, taken at a target chosen specifically to not depend on an
outsized session. Repeatable trades look like this one." Computable content: both
entry and exit are pre-registered at levels marked before the session resolved —
the exit is a level, not a trailing rule or an R-multiple, in this example — and
the level itself is required to carry **three independent confirmations** before
it is tradeable, which is a confluence-count gate on the zone rather than on the
trigger.

---

## 18k-payout-session.pdf

**p4 — the pre-session thesis, before any trade.** A 5-minute NQ chart with a
footprint/weekly-delta ladder on the right and three horizontal minor-volume-node
lines drawn across a prior dealing range *before any trade fires*. Caption: "the
prior dealing range, three minor volume nodes marked as the levels that had
already produced reactions, and the weekly delta print underneath price." The
weekly delta footprint is read as "sellers trapped at the lows and exhausted on
the way back up, buyers covering into that low" — a delta read of who has already
lost control, done pre-entry. Directional bias is set from a profile asymmetry,
not a guess: the yearly composite carries "a lot of built-up value" above price
and "comparatively little below", so the session objective is set downside. A
callout box, SHORT GAMMA, STATED AT THE OPEN, quotes "we are currently in a short
gamma... environment" with the honest caveat that one gamma model read positive
and price sat "almost exactly on the flip between the two," and the plan did not
change. Computable content: the pre-session object is a *level set* (a dealing
range plus n minor volume nodes that have already produced reactions), the
directional bias is the composite-volume asymmetry above versus below price, and
the regime flag is checked before the chart. All three are computable before the
session opens.

**p5 — the pre-file entry, taken deliberately without confirmation.** NQ on a "40
Range" bar type with Speed-of-Tape and CVD sub-panels; a small white box marks a
pre-file entry near two swing markers inside a red dealing-range box with blue
value bands. Caption: "sold 1 at a 2.00 R:R, a small white box marking the
pre-file entry itself, stopped for -$100 before the level ever confirmed." The
source is explicit that this trade skips the confirmation gate on purpose: "the
point of a pre-file entry is not to be right, it is to buy a small amount of
buffer on the session cheaply, in case the real setup a few minutes later needed
the room." Self-graded "a B plus at best, not a strong setup, entered anyway
because the cost of being wrong on a pre-file entry is small and known in advance."
Failure mode recorded: "Sellers never got absorbed the way the thesis wanted."
Computable content: this is a **second, explicitly lower-conviction order class**
with its own sizing and its own acceptance criterion (cheap optionality on session
buffer), not a degraded version of the main setup — a mill that has one entry
quality bar cannot express it.

**p6 — the second stop, and the confirmation that failed.** Same chart style with
an order-ticket tag reading "1 QTY | -40.00 $" beside a grey consolidation box.
Caption: "A second short order live on the book, -$40 risked, stopped moments
later. Buyers absorbed the sell aggression that was supposed to confirm the
level." The mechanism of failure is named precisely: sellers "pushed in again,
looked aggressive on the tape" but the level did not confirm because the opposing
side soaked the aggression. Running total after two trades is roughly -$140, called
"a scratch rather than a real loss, but a loss all the same," and the thesis is
explicitly left unchanged going into trade three. Computable content: **aggression
arriving is not confirmation; aggression arriving and being absorbed is
disconfirmation of that side.** The same absorption print that confirms a fade in
one direction disconfirms the trade in the other, and the discriminator is simply
which side is doing the absorbing.

**p7 — the entry that worked, and the rule for when a level becomes a trade.** The
level is now labelled "OFM" (Origin of the Move) on the chart itself with a long
horizontal ray, a grey consolidation box, and a small rejection dot below it.
Caption: "sellers absorbed at this exact level before, and the read is that
whoever is in control here proves it by holding the retest." The live quote gives
the sequence: "This would be the origin of the moves set up right here. If you go
below this and retest it... Now we need to go below, we retest it with a decent
amount of aggression, I'm in." Critically, the page states the entry is **not on
the first or second touch**: "The first two attempts at this exact level did not
have that participation and were let go." The confirming tell is sellers
"refreshing at the level rather than thinning out." Pull-quote: "A level does not
become the trade because price touched it. It becomes the trade when the same side
defends it a second time, with more conviction than the first." Computable
content: the trigger is a **comparison between defences, not a single defence** —
defence strength at touch k must exceed defence strength at touch k-1. That is a
directly computable monotonicity test on refresh size and refresh pace, and it is
the sharpest statement in the library of what "multi-peak" is actually for.

**p8 — trailing convexity, defined as a protected-extreme walk.** Continuation of
trade three, with two green order tickets on the ladder reading "+1 STP | 775.00
$" and "+1 LMT | 2300.00 $". Caption: "the stop order has moved to +$775 locked
in, the resting target sits at $2,300. Neither figure is the trade's final result,
both are the position being managed live." The stated starting R:R was **0.69** —
target smaller than stop — and the source is blunt that "it fails the arithmetic
before it fails the read," taken anyway because the level behind it was strong.
The trailing rule is fully mechanical: once price closed below the first swing low
"with enough aggression," the prior high became a "protected high... a point the
stop can move to and leave alone, because giving it back would mean the read was
wrong in the first place"; each new extreme that closed "with real speed of tape
behind it" created the next protected point, so the stop "walked down behind price
one protected high at a time rather than by a fixed distance." Computable content:
an **event-driven trailing stop keyed to structure plus a tape-speed condition**,
not to distance or time — and an entry-acceptance rule that explicitly permits
sub-1R initial geometry when the level quality is high, because the realised R is
produced by the trail rather than by the initial target.

**p9 — what the trail was worth, and the one-variable explanation.** Same trade,
tickets now "+1 STP | 1240.00 $" and "+1 LMT | 2645.00 $". Caption: "stop now at
+$1,240, resting target raised to $2,645. The order ticket, not the account
total." Session running total quoted live as "up 1.6, 1.6k. I took two losses and
then we have this one" — one trade that started at 0.69R turned two losers into a
green day. The page's closing claim is the important one for our purposes: "Every
stop move was a reaction to a level the market had just defended a second time,
read the same way trade one and trade two were read, except this time the market
agreed. **The difference between a losing trade and this one was never the model.
It was whether the level held.**" Computable content: the author asserts the
signal is identical across the winners and the losers and the only differing
variable is the level's realised behaviour — which is a direct argument that the
tradeable edge lives in *level grading*, not in trigger discrimination, and it
agrees with the AUC-0.54 result from the quantitative paper.

**p10 — the fourth trade, and a sequencing rule.** Two side-by-side charts, the
right-hand histogram bars now mint-green rather than the pink of the losing-trade
charts. Left caption: "A fresh short, sized the same as the rest of the day,
entered once buyers already in control were seen absorbed rather than defended."
Right caption: "The same trade later, price having pushed a further leg lower
under the same protected-high trailing." Live quote: "Buyers are being absorbed. I
want these buys to be absorbed. They are, okay, I'm in." Sequencing rule stated
explicitly: "the fourth trade was affordable specifically because the third one was
no longer at risk." Session close: "that is 2.3k across six accounts plus one alpha
account," two losses and two wins with "one of the wins doing almost all of the
work," and an honest note that the $18k headline is seven accounts' payout
accumulated over many prior days, "not something this session's four trades made by
themselves." Computable content: **concurrency is gated on the risk state of the
open position, not on a fixed position cap** — a second position becomes permitted
once the first has a stop locked beyond breakeven. And the "defended versus
absorbed" pair is named as the binary discriminator on the same price action.

**p11 — refresh consistency, the page that defines the wall test.** Text-only, no
chart, but it carries the most directly computable rule in the document. A refresh
is defined as "A resting order gets hit, and a moment later the same size is back
at the same price," and the source states where the information is: "What actually
matters is what happens on the **second and third refresh**, because that is where
the bluff usually shows itself." Real size: "A level backed by real size refreshes
at a roughly steady pace and a roughly steady size: hit, replaced, hit, replaced,
without the replacement visibly shrinking... a genuine defender does not run out of
appetite three prints in." Fake size: "A level that is really just one order
rotating through a queue thins out fast: each refresh a little smaller than the
last, **the pacing between them stretching out**, until it stops coming back at
all. That thinning is what precedes the level finally giving way." Live quotes on
both sides of the book: "Sellers common, they're refreshing pretty strongly," and
"these buyers are failing, they're refilling again." Final rule: "a single
absorption print is never enough to act on by itself... Consistency across several
refreshes is what tells you whether that was a wall or a coincidence." Computable
content: a **two-slope test over a refresh sequence** — regress replaced-size on
refresh index and inter-refresh interval on refresh index; a wall has flat size and
flat interval, a failing level has negative size slope *and* positive interval
slope, and the two must be read together. Both are self-scaling if size is
normalised to the first refresh and interval to its own median.

---

## 10k-first-month (1).pdf

**p5 — what changed, drawn as level density.** A plain chart with several stacked
red horizontal lines above a swing and stacked green lines below, plus a CVD-style
purple line and dotted swing markers. Caption: "multiple prior reaction zones held
against the current leg, not one box guessed at... applied on a real chart rather
than a screenshot from a lesson." The narrative claim is that his earliest theses
were "so many random boxes" with macro commentary "with barely any actual auction
reasoning behind it," and what moved the win rate was "being made to defend a level
in writing before the session, not just after it worked." Computable content: level
construction by **confluence count of prior reaction zones**, and the discipline
device of pre-registering the thesis before the session — the latter is exactly the
pre-registration protocol our own sweeps should be running.

**p7 — the short, with risk above and reward below.** Two panels: a higher-timeframe
5-minute view with price labels 7594.50, 7567.75, 7563.25, 7544.75, and a 2-minute
ES panel showing a dark-red risk box above a dark-green reward box around a short
entry, tagged approximately R:R 1.50. Caption: "The short marked against the
resistance he'd already flagged. Risk above the high in red, the planned reward
below it in green." The confirmation-entry sequence is a two-agreement gate: the
level was pre-marked pre-session as "a key area of resistance" where "price had
rejected from it before," and it was then lined up against "a minor high volume node
sitting close by," with entry taken "because two things agreed, not because price
simply arrived somewhere round." Stop "above the high of the rejection," target
"set at 1.5R," stated explicitly. Computable content: a fixed **1.5R target with a
structural stop at the rejection extreme**, and a hard requirement of two
independent level-construction reasons before the level is tradeable.

**p8 — the long, entered on absorption, and the honest attribution.** Same panel
style; the right panel shows a large green reward zone above a long entry with a
smaller red risk box beneath. Caption: "The long, entered on absorption at the
level. The green zone marks how far the actual move ran past the original plan."
The sequence: a *second, pre-written contingency* thesis ("if price retraced, there
was room for a bigger move higher, a backtest of the same structure from the other
side") that triggered when price returned to the level and printed absorption —
"buyers stepping in and holding" — with entry taken "only... once the level actually
printed the reaction he'd written down beforehand." Same 1.5R target. The move ran
well past it, and the source refuses the credit: "The target was 1.5R. The market
gave him considerably more, which is a different thing from having called it."
Computable content: pre-registered **conditional branches** (if retrace, then the
mirror trade at the same structure) evaluated by whether the written-down reaction
prints, which is a template a session-level state machine can carry directly.

**p12 — thesis construction, stated as an ordered procedure.** A 30-minute ES chart
with a red box marking a live-drawn resistance level, a CVD-style purple line in the
margin, and a replay watermark. Caption: "a level with a prior reaction behind it,
not a line drawn because price happened to be nearby." The page gives the
construction order as a procedure: first read the current auction ("an imbalance had
just printed a large move up, and price was starting to find a new area of
balance"); second, check "whether price has reacted at this level before, looking
left on the chart," to judge real key level versus untested; then set the objective
— "trading back toward balance, targeting a higher timeframe high volume node, the
point of control on the yearly chart." Because the up-move was large, a retrace or
two was predicted *before* the target "and said so before price had done it, which
is the actual test of a thesis, stating the expectation first rather than narrating
it afterward." Computable content: the objective is a **named higher-timeframe HVN
or composite POC**, not an R multiple — the target is a structure, and the path to
it is explicitly allowed to be non-monotonic.

**p13 — three losing shorts, and the veto that would have prevented all three.** A
2-minute ES chart with three stacked short-trade rectangles at successively higher
prices along one up-leg, each showing a repeated 20-tick stop and an R:R near 5.00.
Caption: "repeated short entries fought against a level that kept holding. Same
setup, three attempts, the higher timeframe never agreed with any of them. Zoomed
out, that same resistance area had sat untouched for two weeks before this leg, and
once it finally broke, everything below it stopped being a place to sell from." The
diagnosed error is precise: "a valid looking order flow confirmation was enough on
its own," and "reacting purely off confirmations without the higher timeframe
context meant taking trades against a direction that was already telling on
itself." The corrective rule doubles as the re-entry veto: "seeing a key demand
level get tested and sellers absorbed there tells him the higher timeframe bias, and
a short like this one doesn't get taken at all, regardless of how clean the local
order flow looks." Computable content: this is the library's clearest **anti-pattern
for sequential re-entry** — same level, same stop, same R:R, three times, against a
higher-timeframe context that never agreed. The veto is HTF-directional, evaluated
from absorption at the *opposing* level, and it fires before the local trigger is
consulted. Note also the two-weeks-untouched detail: an old, untested level that
finally breaks invalidates *everything below it* as fade material, which is a
level-set invalidation rule, not a single-level one.

---

## a-clean-continuation-short.pdf

**p4 — the 5-minute thesis: minor volume node plus stacking negative delta.** A
full-width chart with two grey horizontal bands (~29760 and ~29500-29510) and a
DOM/delta ladder on the right, price 29900 down to 29400. Header: "THE 5 MINUTE
THESIS: MINOR VOLUME NODE, NEGATIVE DELTA STACKING." Price "had displaced lower and
value had shifted down with it," and "a minor volume node stood out as the level to
use, a place used previously, multiple times, as resistance," cross-checked against
"negative Delta... stacking and stacking into that level" and "the DOM and heat map,
a clear pattern of sellers pinning the level." Computable content: the conjunction
is **repeat-tested minor volume node + monotonically accumulating same-sign delta
into the level**, which reads as "be lenient on sellers here, expect buyers to be
absorbed and exhausted." Note the delta here is *stacking in the direction of the
eventual trade*, which is the opposite polarity to the trapped-buyers p4 reading;
the two are reconciled by which side the delta belongs to relative to the level, not
by its raw sign.

**p5 — failed auctions at the top, with the flip condition stated.** A dark-red
resistance box near the top of range, a curved arrow annotating a rejection near
~29500, a consolidation box and CVD line. Header: "FAILED AUCTIONS AT THE TOP:
WICKS THAT NEVER CLOSED AND HELD." The conditional rule is stated cleanly and is
directly implementable: "if price comes back to the top of that balance, the default
expectation is shorts, **unless price closes above it with real, extreme buying
pressure. If that pressure shows up, the read flips to a retest and longs back
toward the session's VWAP instead.**" Failed auction is defined as repeated upside
wicks that never "truly closed and held" above the level. An aside notes one of
those wicks worked on a 40-range or 1-minute chart "would have been good for roughly
three to four R on its own," offered as potential, not as a realised trade.
Computable content: a **default-plus-flip pair with a named flip condition and a
named flip target** — the fade is the default at a balance extreme, a close above
with extreme buying pressure inverts the trade, and the inverted target is session
VWAP. That is the only place in the library where the fade's own invalidation comes
with its own trade attached.

**p6 — the exit, chosen by regime rather than by structure.** Text-only. "The exit
on this trade came off a transition in established value, not off POC, even though
POC would also have worked as a valid take profit," and the reason is two
non-order-flow constraints: funded-account consistency rules, and the gamma regime.
"For the prior week and a half, the market had mostly been sitting in a gamma long
environment, which raises the odds of chop rather than a clean move all the way to
the lower extreme," so a "safer, closer exit" was taken. The contrast is given:
"The two sessions immediately before this one had been in a negative gamma
environment instead, which lines up with why price dropped and dumped into this
balance in the first place." Computable content: **regime selects the exit, not the
entry** — gamma-long implies chop implies take the nearer of the valid targets;
gamma-negative implies extension implies the further target is reachable. This is a
target-selection rule conditioned on a variable checked before the chart, and it is
the operational half of the gamma flag the structure crosswalk filed as
non-forcing context.

**p7 — the yearly composite, sliced twice.** A yearly composite chart with a
dark-red box near 30200-30250, a grey band with an inner green band near
29750-29800, a lower grey band near 29500-29550, and a CVD line. Header: "THE
YEARLY COMPOSITE: LOW PARTICIPATION, SLICED THROUGH TWICE." The rule for
higher-timeframe low-volume nodes is a fork: "price stalls and tries to build
balance there, or, if there's enough selling pressure, it slices straight through,"
and delta on the actual slice "showed sellers clearly showing their hand, and price
fully dumped through it." The same balance level "got touched again and used again
as resistance to push price back down, slicing through the same low volume area a
second time." Computable content: an LVN is explicitly **not** a fade level by
itself — it is a bimodal object whose branch is selected by whether aggressive
participation is present at the moment of arrival, and the delta print at arrival is
the named discriminator. This is a direct veto on treating every low-volume node as
a mean-reversion target.

**p8 — the re-entry, with the repetition rule stated.** A detailed execution chart
with an OFM line, many trade markers, two stacked dark-red boxes near the top, a
"SELL 1" R:R tag and a green shaded rectangle spanning the trade. Header carries the
exact figures: "THE RE-ENTRY: SELL 1, **R:R 6.11**, TARGET $1,100 AGAINST A $180
STOP." The first attempt is recorded as a loss: "The read going in was that buyers
who had previously controlled the push higher would offer a passive refill zone for
sellers... Buyers came back in instead, and the trade got stopped, which he's plain
about: that's fine, it happens." The re-entry condition is the page's contribution:
re-enter only once "the same level kept behaving the same way on repeat — Sellers
had control, price went lower. Price came back up to the level, sellers had control
again. It went lower again... a refill zone is: a level where the same side keeps
winning the argument." Computable content: **re-entry requires an additional
completed win-loss-win cycle by the same side at the identical price**, and the
re-entry is sized against a materially wider reward ratio (6.11 here) than the
first attempt — the second attempt is not a repeat of the first, it is a different
trade with a different geometry.

**p9 — the alignment found afterward, and the honesty about it.** Text-only.
Drawing the volume profile for the dealing range actually in play showed "the
resistance used for the refill zone lined up with POC on that leg, on the 1
minute... the refill zone and the dealing range's own fair value were the same
price." The caveat is explicit and should be carried: "this alignment wasn't
something checked in real time during the trade, it's something confirmed
afterward." Trade recap: "a balance rejection. Price came out of balance, used the
level as resistance, pushed all the way back down, and that was a failed auction
with buyers absorbed the whole way down." Computable content: a candidate feature —
refill-zone price coinciding with the in-play leg's 1-minute POC — flagged by the
source itself as **post-hoc, therefore a leak risk** if fitted without care. It
belongs on the hypothesis list, not the feature list, until it is computed causally.

**p10 — the origin-of-the-move entry, and why the first signal was refused.** A
dense chart with many trade markers along a declining path, a long horizontal level
line, red flag markers near two peaks, and pink/mint histogram bars. Header: "THE
ORIGIN OF THE MOVE MARKED (OFM), BIG TRADES SHOWING THE AGGRESSION BEHIND IT." The
sequence, and this is the cleanest refusal-then-entry ordering in the batch: sellers
first showed initiative ("willing to price lower, which is what a genuine origin of
the move entry needs: initiative, not just a guess"), but entering there was
explicitly rejected — "it would have been a high risk entry, since the squeeze lower
hadn't actually confirmed yet." Instead price returned to a "refill zone where
sellers had already shown control, effectively top-ticking there," sellers "came
back in with even more aggression than the first attempt," and on the move back
toward intraday daily value "buyers hit the wall on the way and got absorbed" —
that absorption point is where the stop went ("that's the re-entry point, stop placed
right there"). Target given as two options: "back to where sellers previously had no
control, or more conservatively, the current intraday POC." Computable content: the
initiative print **arms** the level and does not trigger it; the trigger is the
return, with strictly greater aggression than the first attempt; and the stop is
placed at the opposing side's absorption point rather than at a fixed distance.

**p11 — the squeeze variant, entered without a retest.** Text-only. It distinguishes
this third setup from the second: "this one is actually a squeeze, not an origin of
the move, because it never failed the way the second trade's first attempt did.
Sellers showed willingness to price lower and the move happened fast, with real
aggression, **no retest, no false start**." The entry: once "buyers hit that move and
got absorbed, the entry is available with a tight stop right there, opposition
visibly failing on both sides of the read at once." All three of the session's setups
are then tied to "the same underlying model... differing only in labelling (squeeze
versus origin of the move versus earlier entry inside the same idea), not in
mechanism." Computable content: this is the **fast lane of the two-lane structure,
stated in the source's own terms** — when the displacement is fast and carries real
aggression and the opposing side is absorbed immediately, the retest gate is waived
and the stop tightens to the absorption point. The slow lane (initiative, refusal,
return with greater aggression) and the fast lane (immediate absorption of the
counter-attack) are explicitly the same model at different speeds.

---

## mastering-amt-vp (1).pdf

**p3 — the three rules, on the whiteboard.** A photographed whiteboard schematic
titled "Basic rules of AMT:" listing three numbered rules verbatim: "1.)
Understand the Current Auction", "2.) Price 80% of the time stays in fair
value", "3.) Understand real extremes **STOP USING VAH/VAL for levels**." A
green-marker doodle beneath shows a compressing zigzag squeezing into a breakout.
The body text sets the layering: Volume Profile and TPO "are not order flow
either, they are a visualization of AMT", while DOM and footprint are what "tells
you whether to give a level leniency right now." Computable content: rule 2 is a
base rate on *time* (80% inside fair value), and rule 3 is an explicit veto on
the exact levels most implementations use as their fade anchors. The source's own
hierarchy is structure defines where, order flow defines whether — the same
ordering vp-lesson-2 p7 states as "structure first, confirmation second,
execution last."

**p5 — the balance rule schematic, with the failed auction defined.** A hand-drawn
balance box with a jagged price path threading inside it, small red dashed boxes
marking each poke above or below the edges, annotated "20% of the time price comes
out of balance = Failed auction" and "80% of the time in balance". Text supplies
the definitions: POC is "the single price that traded the most", VAH/VAL bound
"roughly 70% of that volume around the POC", and price "spends about 80% of its
time inside it, and the remaining 20% outside is exactly what a failed auction is:
price stepping outside the agreed range and, **four times out of five**, stepping
back in." Caption: "Every red box on this profile is a failed auction, a moment
where price left the balance and the balance won anyway." Computable content: the
failed auction is defined constructively as any excursion beyond VAH/VAL that
re-enters, giving a countable event class, and it carries a stated 80% re-entry
rate once price steps out. This is the base rate our fade is implicitly betting
on, and it is stated as the *source's own*, unvalidated on our assets.

**p7 — P and B days, and the direction trap.** Two side-by-side hand-drawn
schematics of a balance box with a dashed profile bulge and a breakout leg, left
labelled "P day", right "B day". The text is worth quoting exactly because it is
easy to invert: a P day has "its bulk of volume sitting toward the top of the
balance, a fat head with a thin tail hanging below it, and **it resolves with
price breaking down out of the bottom**", and a B day is "the mirror of it, volume
concentrated toward the bottom, resolving higher." Caption: "The letter is where
the volume built before the break; the break is which side actually spent more
time defending it." Note this **contradicts** `reading-the-volume-profile` p10-p11
and `amt-lesson-1` p6, which read P as an up-trend continuation shape and B as a
down-trend continuation shape. The conflict is real and should be carried as a
fork, not averaged: this document says the fat end is the side that *fails*, the
other two say the fat end names the trend that built it.

**p8 — the D day, which forbids both fades.** A compact balance box with a price
path repeatedly testing both edges, red dashed tick-marks at each touch, labelled
"D day". Text: "A D day is neither a P nor a B: the profile stays compact and
centred, price tests both edges of the box and never commits, pure compression
with no resolution at all." The page then denies all three shapes trigger status:
"A P or B day tells you a session has already resolved directionally, which
changes **how much leniency the opposite side deserves** for the rest of it. A D
day tells you the market genuinely has not decided yet." Computable content: shape
sets a *leniency parameter* on the opposing side rather than a direction — a
continuous conditioning variable on the fade's confirmation threshold, not a
binary trade/no-trade gate. That is a better fit for a scoring mill than the flag
the crosswalk recorded.

**p10 — the failed-auction setup, drawn as an ordered sequence.** Mirrored
schematics of a balance rectangle, a breakout leg, red dashed tick-marks, and a
purple dashed horizontal line labelled "Reject Prev balance / POC" where a small
box marks the tag-and-reject point. The caption states the whole sequence in
order: "**Balance, break, tag the prior balance's POC, reject**, and the
established balance gets its boundary hit four times out of five." Computable
content: this is a four-event ordered template with a stated 80% follow-through to
the opposite boundary, and the tagged object is specifically the **prior**
balance's POC — not the current one, and not a generic level. That specificity is
what p11 then tests.

**p11 — the discrimination test, on two real charts.** Two 5-minute NQ charts
(ticker NQ 202609) under "Which image is a failed auction setup? 1? 2?". Chart 1
traces price from the break back up to a green "entry?" box at the top of the grey
zone with a "vah = target" line; chart 2 breaks down through its grey box and
keeps going, with an entry marker on a "VAL target" line. The boxed answer is the
most useful sentence on the page: "**Chart 1 is correct.** Balance, break, a tag
of the prior balance's white box, an instant rejection, and an entry back toward
VAH as target. **Chart 2 fails the definition even though it looks similar:**
price does break balance and does retest a grey zone, but it never tags a *prior*
balance and rejects there, it simply breaks down, keeps going, and the retest is a
trend continuation entry, not a failed auction." Closing: "Same visual grammar,
opposite trade." Computable content: the discriminator between a fade and a
continuation entry at a visually identical retest is **whether the retested zone
is a previously-established balance** and whether rejection is immediate. Both are
computable from the profile history plus a time-to-reject measurement, and getting
this wrong flips the sign of the trade rather than degrading it.

**p12 — three repeatable entries off one composite.** A real composite NQ chart
(DeepChart, 5-minute) with a grey balance box, a volume-profile histogram on the
left, a magenta prior level near the bottom, and a stack of short green tick marks
descending stepwise through the box marking sequential entries. Three entries are
enumerated: "Break out of balance and retest the broken boundary: enter in the
direction of the break, long on a retest of a broken-up level, short on a retest
of a broken-down one. Come back inside the balance and re-accept it: the bias
flips, now you're fading back toward the other side. Traverse straight through the
whole balance without holding: that's one side fully priced in, and every retest
from there trades with that side until proven otherwise." Caption carries the
gate: "Every short in this range only worked **because the higher timeframe had
already broken and re-tested downward**." The toolbar shows "Dly Delta Profile"
and "Wkly Delta Profile" layers, the latter enabled. Computable content: a
three-state machine on the balance (broken-and-retested, re-accepted,
traversed-through) with a different trade in each state and an HTF-agreement
precondition over all three.

**p14 — overnight inventory as the session's opening bias.** A schematic titled
"Schematic for OVN direction:" with hand-lettered "OVN INV", "LVN setup OVN", a
price path marked "NET LONG" at its low running up to a horizontal "SHELF" line
and an "LVN" line with a "POC alignment" callout, against a timeline marked 6:00
PM, 9:30 AM, 4:00 PM/RTH. The note reads: "It's a catalyst to show if RTH (NYAM)
will continue the move from OVN NET LONG/SHORT to be respected or disrespected."
Rules: the overnight window is 6pm to 9:30am NY; "net long overnight, the path of
least resistance at 9:30 is higher, net short, it's lower"; "One clean
distribution and the net environment usually just continues. A double distribution
and the low volume node between the two humps becomes the decision point, the
level that gets 'respected' if the open continues the overnight direction, or
'disrespected' if it doesn't"; and for the shelf, "hold it and price likely stays
inside the overnight range, break it with real aggression and price is more likely
heading back to test the overnight extreme." Computable content: an entirely
pre-open, entirely computable session bias — overnight net delta sign, overnight
profile modality (single versus double distribution), and a named decision level
(the inter-hump LVN) whose respect or disrespect at the open confirms or kills the
bias.

**p15 — the 94% overnight-extreme stat, used as a reason not to trade.** Twin
vertical profiles, "ETH Profile" and "RTH Profile", each labelled High of a
Profile / VAH / Mid of a profile MPOC / POC / VAL / Low of a Profile, with a red
arrow connecting an "OVN HIGH" line to a yellow dashed "OVN LOW" line, captioned
"94% chance of EITHER hitting OVN high or OVN low." The caveat precedes the
number: these landmark stats "are not meant to be the main objective of an edge on
their own, and they only mean anything once you already understand AMT on the
higher timeframe. Used blind, without that context, they're just numbers." The
usage is a **timing veto**, which is the novel part: "if a long level sits a few
points above the overnight low with a tight stop underneath it, and there's a 94%
chance price still trades down to tag that overnight low first, the level isn't
wrong, the timing is." Caption: "94% chance of either, not both. The number says
the level probably gets touched before it gets rewarded." Computable content: a
**stop-placement veto conditioned on proximity to an unswept overnight extreme** —
if our stop sits between the entry and an untagged overnight extreme, the trade is
deferred rather than rejected. Self-scaling form: express the gap as a fraction of
the stop distance, and veto when the untagged extreme lies inside ~1 stop-width
beyond entry.

**p16 — the 73% MPOC rule, with its exact condition.** The same twin-profile
schematic, now with a red oval circling the ETH profile's "Mid of a profile MPOC"
and an arrow to a price path beside the RTH profile, annotated "IF we open inside
the balance of the Previous ETH profile: There is a 73% chance to hit that ETH
profiles MPOC" and "THIS IS WHERE PRICE OPENS AT RTH". Stated rule: "If the RTH
session opens inside the previous ETH profile's balance, there is a 73% chance of
the session going on to hit that ETH profile's MPOC, its mid." Stated usage: "If
you're already long from inside that balance, this is a reason to **hold and
trail** rather than take the first easy target at VAL, because the statistical
pull toward the profile's mid is real and it's not marginal." Computable content:
a conditional target with a fully specified antecedent (RTH open inside prior ETH
value) and a named consequent (prior ETH profile mid, not POC — the *mid of the
profile range*, which is a different object). It is a target-extension rule, not
an entry rule.

---

## amt-on-live-markets.pdf

**p4 — fair value is a range, drawn by hand.** A hand-drawn iPad sketch titled
"AMT" showing a sideways bell curve bracketed top and bottom by two flat lines,
under the header "THE BELL CURVE: VALUE AREA IN THE MIDDLE, THE TAPER AT EACH
END." The correction offered: "fair value is not one exact price point. It's a
range", and on a profile that range is "the value area, the section of the bell
curve containing the majority of a session's traded volume", with VAH the top, VAL
the bottom, and the space between where "price spends most of its time chopping."
Note this document says only "the majority" where `mastering-amt-vp` says roughly
70% and `reading-the-volume-profile` says roughly 68% — three numbers for the same
object across one library, which is itself a reason to treat the value-area
percentage as a tunable rather than a constant.

**p5 — the one question at an extreme.** Text-only. Extremes are "the outer edges
of the auction, the taper in volume at each end of the bell curve", and the rule
is a single test: "When price reaches an extreme, there is exactly one question
worth asking: does the market want to keep accepting prices out here, or does it
want to reject them and return to fair value." The epistemic framing is explicit
and matters for our arbiter: "You are not predicting what price will do at the
extreme. **You are watching what it actually does once it gets there**, and
reading that." Computable content: the trigger is a post-arrival measurement, not
a pre-arrival classification — which is exactly the causal ordering the
origin-of-the-move paper found survives reconstruction while the entry law did
not.

**p6 — acceptance versus rejection, as a time test.** Text-only, stating the
reframe verbatim: instead of "price touched this level, so should I buy or sell",
ask "what did the auction do after reaching this level. Did we accept into the
range, or did we reject." Acceptance is "price spending time there and building
structure, chopping around a level rather than fleeing it"; rejection is "price
enters an area and quickly moves away from it." Worked example: "If fair value was
established lower and price rejects an upper extreme, the read is straightforward:
sellers failed to drive price lower there, buyers absorbed them, and price
rejected back up. The level told you what happened. You didn't have to guess."
Computable content: this is the **cleanest self-scaling statement of the
rejection-versus-rest boundary in the entire library** — the discriminator is
time-at-price and structure-building at the level, measurable as dwell time and
as the count of distinct rotations at the level, and it needs no tick constant at
all.

**p7 — HVN and LVN, with the same test applied.** Text-only. An HVN is "an area
where a lot of volume traded, usually because price spent real time there"; an LVN
is "a stretch with relatively little trading, typically left behind by a fast move
up or down", and structurally "low volume nodes represent a lack of acceptance,
and they tend to exist between two areas of established value." The acceptance test
from p6 is then applied at the LVN: "does price reject immediately on contact, or
does it just keep going, dumping straight through because there was never much
conviction there to begin with." Computable content: LVN is a bimodal object, same
as `a-clean-continuation-short` p7 found, and the branch is chosen by immediacy of
reaction on contact.

**p8 — the failed auction drawn step by step.** A hand-drawn sketch under "THE
FAILED AUCTION, DRAWN STEP BY STEP: DRIVEN LOWER, REJECTED, BACK INTO RANGE" —
chop breaking down out of a mini range and dropping to a lower flat line.
Definition given mechanically: "Price is at fair value, sellers gain control, and
price gets driven lower, back toward a previous area of fair value. If price
reaches that lower area and rejects it, coming all the way back up rather than
accepting into it, that's a failed auction: the market failed to find fair value at
the lower prices it just tried." Closing: "Once price comes back into the original
range, the same acceptance question is waiting again, one level up." Computable
content: a real extreme is defined here as **a previously-established fair-value
area that gets tested and rejected rather than accepted into** — a definition that
requires profile history, not just a price swing high.

**p9 — the second 80/20, with its own tell.** No chart, a promotional callout only,
but the text carries a rule distinct from the p5 80/20 of `mastering-amt-vp`. Once
price is back inside the previous range after a failed auction: "80 percent that
price runs all the way to the far extreme, 20 percent that it simply ranges inside
instead." The tell is stated directly: "Inside that balance there is a POC. If
price keeps coming in and constantly fails to break through it and hold, that's a
clear sign you're most likely getting the 20 percent case, a session that just
chops inside fair value. But if buyers push aggressively through POC, maybe with a
retest that holds, that's the tell you're more likely seeing the 80 percent case
play out." Computable content: a **minute-scale branch discriminator on the POC** —
repeated failure to break and hold POC selects the range-bound branch, aggressive
break plus held retest selects the full-traverse branch. This is the operational
piece that turns the 80% traverse claim into something a mill can condition on
rather than assume.

**p10 — a deep dip that still failed to hold.** Text-only worked narrative. Price
moved extreme-to-extreme inside a balance; after rejecting and continuing lower,
"a small retest confirmed the move, and the target became the previous balance
further down." The nuance is the valuable part: price "didn't just tag that lower
level and bounce. It **dipped meaningfully into the previous balance**, deep enough
that a less patient read might have called it accepted. It still failed to actually
hold and trade lower from inside it", with buyers "slowly" regaining momentum. The
source's own conclusion: "The rejection was real, it just took longer to confirm
than the textbook version does." Computable content: this is the structural-scale
twin of the refill paper's 18-tick result — **penetration depth into a level does
not establish acceptance; only failure to sustain trade from inside it does.** Any
invalidation keyed to depth alone discards this case, and the source flags it as
the common one, not the exception.

**p11 — the same read on the highest timeframe.** A real Bookmap-style chart with
black candles against three clusters of blue and red vertical bars and three
horizontal grey band-lines marking successive balance ranges, spanning about a
week. Price auctioned inside one balance "for around a week, moving from extreme to
extreme to extreme, repeatedly accepting the same range as fair value each time it
returned." After breaking out, "a new fair value formed above the old range", but
price "traded inside it only briefly before showing it no longer wanted to
participate there either", broke out again, retested briefly, then "came all the
way back down to the original fair value, this time not stopping to trade inside
it" — instead "price simply dumped straight through and is now holding at the
lower extreme instead, the low volume node behavior from earlier in the document,
on the highest timeframe in this whole document." Computable content: a
week-long established balance is **reclassified as an LVN void once revisited on a
dump-through basis** — real-versus-lagging status is time-and-acceptance dependent
and must be recomputed on each visit, not fixed by the level's construction
history. This is a direct argument against caching level quality.

**p12 — the synthesis.** Text-only. Every concept in the document "balance, fair
value, extremes, high and low volume nodes, the failed auction, the 80/20 read,
exists to answer a single question: **where is the market finding acceptance, and
where is it rejecting price.** That's the actual foundation of auction market
theory, not a specific setup." Once it becomes the default lens, "the setups in
this document stop being separate tricks to memorize and start looking like the
same read, applied at whatever level price happens to be testing right now."
Computable content: an argument that the many named setups collapse to one
measurement, which for us means one well-specified acceptance metric is worth more
than a catalogue of pattern detectors.

---

## reading-the-volume-profile.pdf

**p4 — the three components, mapped onto price.** A labelled diagram: a sideways
grey volume histogram beside a price chart, with arrows from the histogram to
"VAH", "POC" (in red) and "VAL". VAH is "the highest price within the value area,
the band where roughly **68 percent** of the session's volume traded"; VAL is "the
same idea at the bottom of that band"; POC is "the single price where the most
volume of anywhere in the session traded." Framing: these three "tell you where the
market has already agreed to do business." Note the 68% figure against
`mastering-amt-vp`'s 70% and `amt-lesson-1`'s "Value Area Volume to 70" setting.

**p5 — POC behaviour selects the target.** Text-only. POC is "a magnet within the
balance. Price comes back to it regardless of which direction it approaches from."
The rule is a retest-behaviour test: "If price fails to break above POC, retesting
it again and again without holding above, the more likely outcome is a full trip
back down to value area low. If instead price retests aggressively and then pushes
through POC with real aggression, value area high becomes the more likely target."
Summary: "The behavior around POC, not a guess about direction, is what separates
the two reads." Computable content: a **target-selection rule driven by a repeated
failure count at POC**, which is directly countable at minute scale, and it agrees
exactly with `amt-on-live-markets` p9's branch discriminator.

**p6 — continuation over reversal, stated as a personal statistic.** Text-only.
Continuation is "price breaking out of the range, coming back into it for a
retest, and then continuing in the direction of the original break"; reversal is
"price moving up into the range and simply turning the other way once inside it."
The stated preference is unusually well-caveated: "he trades continuations, and
rarely trades reversals, because continuations give him a higher win rate. **That's
a personal statistic, not a claim about which read is theoretically correct.**"
Nearly every shape covered afterwards "is read the same way, for a break and a
retest, not a turn." Computable content: this is a direct challenge to a
fade-oriented mill — the structure half's most prolific source prefers the
opposite trade class and says so with the caveat attached. Worth carrying as a
pre-registered comparison rather than a contradiction to resolve by argument.

**p7 — the balanced profile, the one that permits the fade.** An infographic card
with a symmetric bell histogram beside a zigzag price path oscillating between two
flat boundary bars. Source's description: "A balanced-shaped profile represents a
market where both buyers and sellers agree on a specific price area, establishing
fair value... neither side maintains sustained control. As a result, volume becomes
concentrated around the center, forming the characteristic bell-shaped
distribution", with "sellers more dominant near the top, buyers more dominant near
the bottom, neither strong enough to break the range outright." The priority claim:
"levels built from a balanced profile are **the strongest and most easily
identifiable in the market**", the ones preferred "to build a plan around."
Computable content: profile modality (symmetry and kurtosis of the volume
distribution) as a **level-quality prior**, computable before the session, and the
balanced case is the one that most permits fading extremes.

**p8 — double distribution, both shelves tradeable.** An infographic card showing
two grey shelves joined by a thin leg, with a price path across the top shelf, a
drop through the leg, and a zigzag at the bottom shelf. Description: "both
participants initially agreed on a certain price area and established fair value.
Later, one side took control and drove price away from that area, eventually
finding acceptance and establishing a new area of fair value." The entry rule is
given for both directions: "if price opens and comes down to retest the lower shelf
and buyers hold it, the read is a long back toward the upper extreme, entry at the
retest, target at the far shelf. If price opens lower instead and sellers break
through with a retest that holds, the same logic runs in reverse: short the retest,
target the next extreme down." Computable content: a two-sided pre-registered plan
with entry at the retest of a shelf and target at the *opposite shelf* — the
connecting leg is the un-accepted LVN and is explicitly not a destination.

**p9 — the trending profile, the hard veto.** An infographic card with a long
narrow un-bulged histogram and a stair-stepping price line. Description: "one
participant maintains control throughout the day, continuously driving price in one
direction. The opposing participant fails to gain enough control to establish a
balanced area of fair value... little acceptance around previous prices." The veto
is unambiguous: "when you see one, **get off. There's nothing to trade**", and the
named account-blowing mistake is "seeing a strong trend and repeatedly trying to
long a small reaction inside it, again and again, taken out each time, until the
account is gone." Closing: "A trending profile isn't a setup, it's a signal to stop
looking for one." Computable content: a **hard abstention gate keyed to profile
modality**, and the failure mode it prevents is precisely sequential re-entry
against a trend — the same anti-pattern `10k-first-month` p13 records as three
losing shorts.

**p10 and p11 — P and B shapes, continuation only after the top range resolves.**
Two mirrored infographic cards. P-shaped: "one participant initially drives price
higher, followed by both buyers and sellers finding acceptance at those higher
prices. This creates a new area of fair value." The read is explicitly not a chase:
"don't chase the trend that built the shape, **wait for the range at the top to
resolve.** If buyers are dominant inside it and price breaks out with a retest that
holds, that's the long, continuing the move the shape was already built on."
B-shaped is the exact mirror: "don't fight the drive that built it, read the range
once fair value is established, and with a B-shaped profile the underlying trend is
lower, the same way a P-shape says the underlying trend is higher." Computable
content: in these two documents P means underlying trend *higher* and B means
*lower* — the opposite of `mastering-amt-vp` p7. Carry the fork explicitly.

**p12 — the printable checklist.** A literal checkbox list, "every rule in this
document, printable", under three headers. THE COMPONENTS: "I've marked VAH, POC
and VAL before forming any opinion about direction"; "I'm reading POC behavior
(repeated failure vs. an aggressive break) to decide between the VAL and VAH
targets." CONTINUATION OVER REVERSAL: "I have a break AND a retest that held, not
just a level being touched." READING THE SHAPE BEFORE THE SESSION: "I know whether
I'm looking at a balanced, double distribution, trending, P-shaped or B-shaped
profile"; "If it's trending, I've accepted there's nothing to trade rather than
fighting it"; "If it's a double distribution, I have both shelves marked and a plan
for either direction before price gets there." Computable content: the source's own
distillation, usable directly as a pre-trade gate in this order — classify shape,
mark the components, read POC behaviour to pick the target, require break plus held
retest before acting.

---

## amt-lesson-1.pdf

**p4 — balance and imbalance, with the 80% attached to a specific case.** Two
figures: a schematic red bell curve over muted candles annotated "70% of this bell
curve of data repents a balance of price" (the source's own spelling), and a real
NQ chart with a profile where a "Balance" label arrows into a shelf and an
"Imbalance" label arrows into two hand-circled clusters, sub-annotated "price dips
out of balance using it as support to push higher to seek other previous balance or
create new balance". A dotted callout reads "**80% Chance of returning to this
VAH(balance extreme)**". Opening line: "Price always moves to find balance. When it
moves out of balance it is in imbalance, and it will do one of two things: return
to the old balance, or create a new one somewhere else." Computable content: note
the 80% here is attached specifically to a *return to VAH*, not to time-in-value —
the library uses one number for at least three different claims and they should be
kept apart.

**p5 — the value area, with the exact platform setting.** A real profile-plus-price
chart with arrows to VAH, VAL, POC and "Fair value/Balance". Definitions: POC is
"the busiest shelf in the profile. The auction gravitates back to it"; VAH is "the
top boundary of the zone holding roughly 70% of the volume. The ceiling of
agreement"; VAL is the floor of the same zone. A SET IT UP box gives the exact
computable setting: "On any fixed range volume profile, set **Value Area Volume to
70**. That draws the VAH, VAL and POC for you on whatever range you select." A READ
IT box gives the state machine: "Above value, buyers won the argument. Below value,
sellers did. **Inside value, the argument is still going, expect rotation.**"
Computable content: the 70% value-area parameter stated as a setting, and a
three-state location classifier that conditions the expected behaviour.

**p6 — the four profile shapes as a thin/fat rule.** A schematic of four sideways
histograms. "D — BALANCED — A two sided auction. Fat middle, symmetric. **Fade the
edges back toward the POC.**" "P — SHORT COVERING — Fat top, thin tail below.
Shorts getting squeezed out, buyers finishing. Common late in up moves. Expect
balance after." "b — LONG LIQUIDATION — Fat bottom, thin tail above. Longs puking,
sellers finishing." "B — DOUBLE DISTRIBUTION — Two separate balances joined by a
thin bridge. Treat each as its own value area, the bridge is the line in the sand."
The unifying rule: "The thin part of any profile is the imbalance, business that
never got done properly. Thin zones break fast and act as the reference when price
comes back. The fat part is the magnet. **Thin repels, fat attracts**, that one line
covers most profile reading." A warning box demotes P and b from signals: "It does
not call the top or bottom, it tells you to stop chasing and start watching the
balance that forms next." Computable content: thin-repels/fat-attracts is a
single continuous rule over the profile density, which is more implementable than
a shape taxonomy — and it makes the D shape the only stated fade case.

**p7 — the failed auction setup, with the 80% traverse.** A schematic line chart:
a grey zigzag breaking below VAL, a red "breakout fails, price re-enters value"
segment, then a cyan line rising back through POC toward VAH, annotated "80% odds
it traverses to the other side". The core rule: "When the market breaks out of
value and later trades back into a prior value area, **around 80% of the time it
traverses that value in the opposite direction.**" Headline: "Re-entry into old
value is the highest odds rotation in the auction. That is how you catch the fade
of a trend." The strict version quoted: "once price re-enters **and holds** inside
value, expect the full traverse." THE PLAY box gives the sequence: "Mark prior
value areas. When price breaks out and later re-enters one, look for the rotation
across it toward the other side, and **confirm the entry at the edge with the DOM
or the footprint before you touch it.**" Computable content: this is the structure
half's flagship fade, and its target is the *opposite value-area boundary*, not a
fixed R — a structural target, with the order-flow confirmation explicitly
subordinate to and after the structural setup.

**p8 — acceptance versus failed auction, with a signature.** Text-only.
"ACCEPTANCE — Price breaks out of fair value on significant volume with convincing
price action, and holds... The old boundary flips, support becomes resistance...
and you can expect continuation once the old value area gets retested." "FAILED
AUCTION — Price pokes outside value and does not gain acceptance. **No increase in
volume on the breakout, long wicks, a quick return back through the point of
breakout.** These are the V shape reversals straight back to the levels." Body:
"Volume confirms the flip, the wick exposes the failure." HOW TO TELL THEM APART:
"Acceptance builds volume outside value and holds the retest. A failed auction is
quiet on the break, wicks hard, and **snaps back inside within a few rotations**."
Computable content: a three-part computable signature for a fadeable breakout —
breakout-bar volume not elevated versus its own recent distribution, wick-to-body
ratio elevated, and return inside value within a small number of rotations. All
three are self-scaling if expressed as percentiles of their own trailing
distributions.

**p9 — the two rules of the auction.** Rule one, with a real order-flow chart
(volume profile, cyan balance-extreme bands, multiple hand-circled repeated touches
at *both* edges): "**Balance stays balanced until proven otherwise** — Price inside
a balance tends to remain inside it, and the extremes of that balance hold as
support and resistance. Fade the edges back toward the POC until the market shows
you acceptance outside." Caption: "The balance extremes hold, and the rotation
trades edge to edge." Rule two, with a real chart annotated "Extreme" at the last
high before breakdown and "re-tap to move lower from extreme" at a circled retest
bounce: "**Out of balance the ledges carry the move** — When price leaves a
balance, the ledges of the prior balance are what hold for the move to continue.
The level that was support becomes the resistance that fuels the next leg."
Computable content: the two rules are a complete disposition of the fade — inside
balance, fade the edges toward POC; outside balance, the same levels flip polarity
and become continuation entries. The multiple hand-circled touches at both edges of
rule one's chart are direct visual confirmation of the multi-peak claim at the
structural scale.

**p10 — day types, and the fade permission list.** Text-only cards. TREND DAY:
"Opens near one extreme, closes near the other. Value migrates all session... The
profile prints long and thin. **Continuation only, never fade it.**" NORMAL DAY: "A
wide early range, then rotation inside it... The profile fattens into a D. **Fade
the extremes, target the POC.**" NORMAL VARIATION: "The early range gets extended
once, roughly doubling it, then the market balances in the new area... Trade the
push, then switch to fading." NEUTRAL DAY: "Range extension on both sides of the
open... Keep size small until it picks." NON TREND DAY: "Nobody shows up. Narrow,
quiet, usually in front of news. **The edge is knowing there is no edge**, stand
down or scalp tiny." Closing: "Most blown accounts are a day type error: running
continuation on a normal day, or fading a trend day because price looks far from
value. **Name the day before you size the trade.**" Computable content: an explicit
permission table for the fade, keyed to a day-type classifier that is computable
intraday from value migration, range-extension count and profile aspect ratio.
Normal Day and the rotation phase of Normal Variation permit it; Trend Day forbids
it; Non-Trend Day is an abstention.

**p11 — reading the open, ranked by conviction.** Text-only cards, explicitly "in
order of conviction". OPEN DRIVE: "Price drives hard in one direction straight off
the open and never trades back through it. The strongest statement the market can
make. **Do not fade it**, look for continuation entries on shallow pullbacks."
OPEN TEST DRIVE: "The market opens, tests a key reference first, prior low, prior
value edge, finds no business there, then drives the other way. Second strongest,
and **it hands you the level your risk lives behind**." OPEN REJECTION REVERSE:
"Opens, auctions one way, gets rejected and trades back through the open. Moderate
conviction... treat the rejection extreme as the day's reference." OPEN AUCTION:
"Price rotates around the open with no conviction either way... expect a balance
day and **treat the early extremes as fade material**." Closing: "An open drive
points at a trend day. An open auction points at a normal day." Computable content:
a four-way opening-type classifier decidable within the first minutes of the
session, ranked, with the fade sanctioned only under Open Auction and vetoed under
Open Drive — and it is an early, cheap predictor of the day type that governs the
whole session's permissions.

---

## vp-lesson-2.pdf

**p3 — HVN and LVN on a real chart.** A real annotated NQ chart with a profile and
shaded value bands, arrows to "LVN (low vol node)" at a thin cluster and "HVN (high
vol node)" at a thicker band. Headline: "The profile shows you volume at price, not
volume in time. It is a map of where the business actually happened." HVN: "A price
where volume built up. The market spent time here and agreed here. **Price gets
drawn back to these shelves and slows down inside them.**" LVN: "A price where
volume fell away. The market rejected it and moved fast. **Price tends to react at
these and traverse them quickly.**" Computable content: HVN is a deceleration zone
(fade-friendly, price slows inside), LVN is a reaction-then-traverse zone — so an
LVN is a place to expect a *reaction*, not a place to expect a *stall*, and a fade
that targets an LVN is targeting somewhere price does not linger.

**p4 — shelves and ledges, named apart.** A real chart with three horizontal
double-line bands tagged "Shelfs", captioned "Each one is a zone of agreed business
with clean edges either side", plus a schematic bell profile with "Shelf" at top and
bottom bands and "POC" at the centre. Definitions: "THE SHELF — Everything in
between the lines. The body of agreed business, the zone price rotates inside and
returns to." "THE LEDGE — The lines themselves, the extremes of the shelf. **The
exact price where the build-up starts or the fade-away begins.**" Computable
content: the ledge is defined as the derivative of the profile — the price where
volume density changes regime — which is a computable edge-detection on the volume
histogram rather than a hand-drawn line.

**p5 — real extremes versus lagging levels, the page the crosswalk needed.**
Opening statement: "VAH, VAL and POC are useful, but **they recalculate as price
moves. They drift with the session, like a lagging indicator. A ledge does not
move.**" Headline: "Shelves and ledges are real extremes. They are structure, not
statistics." A real chart marks red "Ledge" lines at fixed shelf edges, captioned
"These edges were set by real business and **they stay where they were set**"; a
schematic shows four "Ledge" lines bracketing the upper and lower shelves around a
central POC, captioned as fixed reference points "on a profile that otherwise keeps
changing." Computable content: this is the mechanical justification for
`mastering-amt-vp` p3's "STOP USING VAH/VAL for levels" — the objection is not that
value-area boundaries are wrong but that they are **non-stationary within the
session**, so a level detected at time t moves by t+1 and any backtest keyed to
them is quietly using a moving anchor. Ledges are fixed once set. For our purposes
this is a concrete instruction: anchor zones to volume-density regime changes with
a fixed birth time, not to a recomputed VAH/VAL.

**p6 — naked POCs and composites.** Text-only. "NAKED POC — A prior session's POC
that price has not traded back to yet. Untested, it acts like a magnet, the market
tends to return and tag it. **A list of naked POCs above and below is a ready made
target list.**" "COMPOSITE PROFILE — Merge several days or weeks into one profile.
The HVNs and LVNs that survive across all that data are the levels the whole market
respects, far stronger than any single day's." Scaling rule: "A shelf on a 5 minute
profile is a scalp level, the same shelf on a composite weekly profile is a swing
level. **Zoom the profile to match the trade you are hunting.**" Closing: "When a
naked POC lines up with a composite shelf, that is a level worth building a whole
session around." Computable content: an untested-prior-POC target list is directly
computable and self-maintaining, and the timeframe-matching rule says the profile
lookback should scale with the intended holding period — which for a minute-scale
fade means short-lookback profiles, not the yearly composite.

**p7 — trading the structure, and the ordering.** Text-only checklist. "Price is
likely to react at the sensitive areas, the build-ups and the fall-offs." Item 1:
"**Trade the ledge, not the middle of the shelf** — The edge of the structure is
where the decision happens. Inside the shelf is rotation, chop and noise. At the
ledge the market either defends the business or abandons it." Item 2: "A ledge on
its own is a line. Watch the DOM and the footprint at the level: absorption,
aggression, the tape picking a side. **No confirmation, no trade.**" Item 3: "A
ledge that lines up with another reference, VWAP, a prior value area edge, an old
POC, is worth far more than either level alone. **Confluence is the filter.**" THE
SEQUENCE: "Structure first, confirmation second, execution last. The profile tells
you where the trade lives, the tape tells you when to take it." Computable content:
the library's canonical ordering, and it is the inverse of a flow-first feature
mill — location is a gate, not a weighted feature.

**p8 — the shelf checklist, in order.** Five sequential checks "before you trade any
profile structure. Run them in order, every time." (1) "Mark the nodes — HVNs and
LVNs on the ranges that matter: yesterday, the overnight, the current balance." (2)
"Draw the ledges — The exact prices where each build-up starts and each fade-away
begins. Those lines are the trade locations." (3) "Label the shelves — Know which
zones are agreed business. Inside them you expect rotation, not follow-through."
(4) "Check for confluence — Does a ledge line up with VWAP, a value area edge or an
old POC? **Stacked levels first, lone levels last.**" (5) "Wait for the tape — DOM
and footprint at the level. The structure is context, the confirmation is the
trigger." Computable content: a ranked candidate-level generator with an explicit
priority ordering (confluence count descending) and three named lookback ranges
(prior session, overnight, current balance).

---

## tpo-lesson-3.pdf

**p4 — the value area in time.** A TPO letter chart (stacked alphabetic rows built
from 30-minute periods) with the widest, most letter-repeated row arrowed as "POC".
Definitions: "POC — The price level with the **highest amount of time spent**. It
acts as a draw for price, the level where buyers and sellers previously reached
their fairest agreement." "VAH — Top of the value zone. Above it, price is trading
at a premium." "VAL — Bottom of the value zone. Below it, price is trading at a
discount." Computable content: a time-based POC is a materially different object
from a volume-based POC and the library uses both without always distinguishing
them; where they disagree, the disagreement is itself information about whether
size or duration built the level.

**p5 — single prints.** A TPO chart with a thin one-letter-wide strip arrowed
"Single Print". Definition: "A single row of letters from one time period, with no
overlap from any other period. Price moved through so fast that only one 30 minute
window ever touched it." Rule: "A single print is a sharp one sided move that leaves
imbalance behind it. **The market tends to come back and fill it, like a magnet.**"
The HOW TO USE THEM box begins "Mark fresh single prints as unfinished business.
They are targets when price is moving toward them, and..." — the remainder is cut
off at the page edge and was not legible at this resolution. Computable content: the
TPO period is stated as **30 minutes**, which makes a single print a fully
computable object (a price touched by exactly one 30-minute window), and it is a
*target* rather than a level to fade from.

**p6 — excess.** A TPO chart with a tapering stack of repeated letters at the bottom
labelled "Excess Low", captioned "the same letter stacked at the extreme, then
rejection." Definition: "Excess forms at the edges of a TPO profile, when **two or
more rows of the same letter print at the extreme**. It is like a single print, but
at the tails." A mirrored "Excess High" panel is mostly cut off at the page bottom.
Computable content: excess is a countable pattern (>=2 stacked same-letter rows at
a profile extreme) and p9 confirms its meaning — finished business, expected to
hold on first test. This is a **positive** level-quality marker for a fade, and it
is the counterpart to the poor extreme.

**p7 — poor highs and poor lows.** A TPO chart with a flat-bottomed extreme
(several identical-width rows, no single-letter taper) labelled "Poor Low",
captioned "no tail, weak rejection, unfinished business the market tends to
revisit." Definition: "A poor high or poor low forms when the market shows weak
rejection from a level, usually during probing moves. **The extreme just stops, it
never finishes.**" Two asset-specific comparison boxes, which are directly relevant
to our porting law: "ON NQ — Poor highs and lows usually appear as a single TPO tail
and they are useful, NQ's thinner structure lets the probe print clean." "ON ES —
The thicker market structure creates shorter, firmer tails. **Poor extremes are
less reliable on ES and rarely used**, though they do appear." Computable content: a
tapered extreme (excess) and a flat extreme (poor) are opposite level-quality
signals computable from the TPO row-width profile at the extreme, and the source
itself states the marker's **reliability is asset-dependent** — which is the
standing "measure on our assets" law, asserted by the source rather than imposed by
us.

**p8 — initial balance and range extension.** Definition: "The initial balance is
the range of the first hour, the A and B periods. It frames the whole day." Three
states: "RANGE EXTENSION — When a later period prints beyond the IB high or low...
It signals one side has taken control and the day is trending out of balance." "IB
HOLDS ALL DAY — If price stays inside the initial balance, the day is rotational, a
normal or neutral day. **Fade the IB edges back toward the POC.**" "IB BREAKS EARLY
— An early, one sided range extension points at a trend day. **Do not fade it**, the
auction has already decided." Closing: "Whether the rest of the day respects it or
breaks it tells you the day type before lunch, which is the same call the VIX and
the open type give you, from a third angle." Computable content: the IB is fully
mechanical (high-low of the first hour) and gives a third independent day-type
classifier alongside the opening type and the volatility regime — three cheap
classifiers that can be required to agree before the fade is permitted.

**p9 — the TPO checklist.** Five sequential checks. (1) "Mark the profile levels —
POC, VAH, VAL from yesterday's TPO. Premium or discount is your first read of the
day." (2) "List the unfinished business — Fresh single prints and poor extremes.
**These are the magnets, and your target list.**" (3) "Respect the finished business
— Excess marks where an argument ended. **Expect those extremes to hold on first
test.**" (4) "Stack with the volume profile — TPO structure that lines up with a VP
shelf or ledge is twice the level." (5) "Confirm at the level with the tape — DOM
and footprint decide the entry. **The profile is context, never the trigger.**"
Computable content: this page resolves the tradeable/untradeable split cleanly —
single prints and poor extremes are *targets to trade toward*, excess extremes are
*levels to fade from*, and confusing the two inverts the trade. Note item 3 is the
one place in the library that sanctions acting on a **first** touch, and it does so
only at an excess extreme.

---

## vwap-lesson-10.pdf

**p3 — VWAP and its bands.** Definition: "VWAP stands for volume weighted average
price: the average the market has actually paid, weighted by volume. Institutions
use it to identify premium and discount zones." A real chart shows a black median
VWAP line with two red deviation bands; as literally rendered the upper band is
labelled "-2" and the lower "+2", which appears reversed against the usual
convention and is recorded here as seen. Framing: "In AMT logic **the VWAP median
is the POC of the session so far**: where the business has averaged out." THE BANDS
box: "The lines above and below are standard deviation bands. Run plus and minus
**2 and 2.5**, you can add 3 but price rarely touches it. They are the extremes of
premium and discount, the same idea as the edges of value." Computable content:
VWAP bands are a **self-scaling** extreme definition — standard deviations of the
session's own volume-weighted price — and therefore port across assets without the
tick-constant problem that afflicts every other level in the library.

**p4 — premium and discount by deviation, with the two rules.** Text-only. "PLUS AND
MINUS 1 — The working premium and discount zone. Ordinary business happens inside
here." "PLUS AND MINUS 2 — The tops of the extremes. This is where the odds genuinely
stack, an institution trying to get filled is getting its best price out here." "THE
HIGHER THE PREMIUM — The higher the chance of reversal soon." THE TWO RULES box:
"One: the trades worth taking live **beyond the 1 band and ideally at the 2**, deal
with at least the 1. Two: **only trade VWAP extremes WITH absorption, never on the
touch alone.**" THE FALLING KNIFE WARNING: "If there is no confirmation, or the draw
beyond the band is clearly still higher or lower, do not trade against it.
**Deviation is probability, not a wall.**" Computable content: a fully self-scaling
location gate for a fade — require |price - VWAP| > 1 sigma_session, prefer > 2 —
combined with a mandatory absorption confirmation. This is the single most directly
portable location rule the structure half offers, and it needs no per-asset
calibration beyond the session's own variance.

**p5 — CVD, the aggression meter.** Text-only. "CVD is cumulative volume delta: the
running net difference between aggressive buyers and sellers, market buys against
market sells, accumulated over time." "CVD RISING — More aggressive buying is
entering the market. The buyers are the ones paying up." "CVD FALLING — More
aggressive selling." Headline: "**Price tells you what happened. CVD tells you who
paid for it.**"

**p6 — the three step CVD plan, with the divergence rule.** Text-only. Step 1:
"Hunt the divergence — **Price rising while CVD falls means sellers are active
despite the move. The move is being carried by passive orders, a potential reversal
signal.**" Step 2: "Grade every breakout — Real breakouts print rising CVD. **Price
breaking out on flat or falling CVD is likely a fakeout**, low conviction dressed up
as momentum." Step 3: "Spot the absorption zones — **Price stalling while CVD keeps
climbing or falling means large players are quietly taking the opposite side. That
standoff usually resolves violently.**" Synthesis: "VWAP gives the location, the
deviation extreme. CVD plus the ladder gives the confirmation. **Location plus
confirmation is the whole method in one sentence.**" Computable content: three
distinct minute-scale computables from one series — a price/CVD sign divergence, a
breakout quality grade (CVD slope during the break), and an absorption detector
(price variance near zero while |CVD slope| stays high). All three are ratios or
correlations, hence self-scaling. Step 3 is the same absorption definition
`dom-lesson-5` p5 gives on the ladder, computed on a longer window.

**p7 — anchored VWAP.** Text-only. "The session VWAP resets every day. The advanced
move is to anchor it manually to the exact event the big players are averaging
from." "ANCHOR TO THE SWING — Drop the VWAP from a major swing high or low. It
becomes the average price of everyone who has traded since that turn, and it acts as
dynamic support or resistance from that point on." "ANCHOR TO THE EVENT — CPI,
FOMC, the earnings gap, the session open... which is the level institutions defend."
"MULTIPLE TIMEFRAMES — When session, weekly and an anchored VWAP all converge, that
is a heavyweight level worth building a trade around." Computable content: an
anchored VWAP from the zone's own birth time is the natural companion to a
zone-episode model — it is literally the average price paid by everyone who has
traded since the zone was built, i.e. the trapped-inventory breakeven, and its
convergence with session VWAP is a computable confluence count.

**p8 — the exact TradingView settings.** A real chart with VWAP and deviation bands,
each line's value labelled on the price axis, plus two inset screenshots of the
indicator settings. Inputs tab as legible: "Hide VWAP on 1D or Above" unchecked;
"Anchor Period" = **Session**; a Source dropdown (value not legible); "Offset" =
0; "Bands Calculation Mode" = **Standard**; "Bands Multiplier #1" = **1**, checked;
"Bands Multiplier #2" = **2**, checked; a third multiplier row present but shown
unchecked; "Timeframe" = Chart; "Wait for timeframe closes" checked; "Inputs in
status line" checked. Style tab: VWAP checked (dark), Upper/Lower Band #1 checked
(purple), Upper/Lower Band #2 checked (red), both Bands Fill unchecked, Precision
Default, labels and values on. The style caption states "bands set to plus and minus
**1, 2 and 2.5**", which is the page's own claim of three multipliers even though
the third checkbox reads unchecked in the screenshot. Computable content: the
source's own parameterisation, recorded exactly — session anchor, standard
deviation mode, multipliers 1 and 2 active with 2.5 claimed in prose.

---

## dom-lesson-5.pdf

**p3 — the ladder, defined.** A live futures DOM screenshot labelled "DOM:EPZ25"
with a size selector (1/2/3/5/10/15/20) and columns "Volume | Price | Note | Bid |
@Bid | @Ask | Ask | Orders". Price runs 6664.50 down to 6658.75; the left Volume
column shows a bicolour bar with values 6412, 6761, 8399, 8255, 10271, 9512, 8038,
8643, 8193, 8241, 11306, 10472, 11438, 14218, 13910, **15325**, 13342, 8924, 9990,
7272, 8022, 5942, 7081, 6049 — the 15325 row at 6660.75 highlighted in gold as the
standout level. Resting ask sizes run 68, 67, 86, 57, 77, 61, 82, 82, 87, 110, 114,
92, 106, 84, 130, 111, 112, 98, 76, 41, 28, 164, 136, 95, with an adjacent **signed
size-change column** showing 1, -1, -3, -6, -7, 12, -20, -20, -53 — a per-level
order-size delta that is the refill tracker in raw form. Callouts define the two
sides: "BIDS, THE LEFT SIDE — The list of buy limit orders below price... the
liquidity underneath the market" and "ASKS, THE RIGHT SIDE — ...the liquidity
overhead." Computable content: the signed per-level size-change column is exactly
the quantity `18k-payout-session` p11's refresh test needs, and it is a native MBP
field rather than something to be derived.

**p4 — aggressive versus passive, the definitions the delta rests on.** Text/schematic
page. "AGGRESSIVE, MARKET ORDERS — They cross the spread and hit the ask or the bid
because they want the fill immediately. Best ask 5000.25, best bid 5000.00, an
aggressive buyer clicks buy market and instantly pays 5000.25, they are lifting the
offer. **Aggression is urgency and conviction, this is what actually moves price.**"
"PASSIVE, LIMIT ORDERS — They place a bid or an offer and wait... **Passive because
they never chase, they provide the liquidity the aggressive side consumes.**" THE
INTERACTION IS THE MARKET: "Price moves when aggression eats through passivity.
Every level that holds or breaks, every wick, every trend leg is that one contest,
repeated."

**p5 — delta, and the read that matters.** "Delta is the running score of that
contest. It is **the net volume of market buys minus market sells at each price
level.**" Positive delta means "market orders are lifting offers and pushing price
up"; negative means "market orders are hitting bids." A horizontal bar chart plots
per-price delta against the ladder (6664.50 down to ~6663.00) with printed values
+340, +180, -90, +420, -210, a wide negative bar, and +60, captioned "net market
buying against market selling per price, the aggression made visible." THE READ THAT
MATTERS: "**Delta against price is the tell. Heavy positive delta while price goes
nowhere means someone is absorbing the buying**, and that argument is the next
lesson." Computable content: the canonical absorption definition, stated as a joint
condition on delta magnitude and price displacement — and note delta here is
defined **per price level**, not per bar, which matches the trapped-buyers p4
profile-delta reading rather than a bar-delta series.

**p6 — speed of tape and the spread, with the break warning.** "SPEED OF TAPE — How
fast the time and sales prints scroll. A tape that suddenly rips at a level is
urgency arriving. **A tape that freezes at a level is hesitation, or a big passive
order soaking everything up.** The footprint is the history, the speed is the
pulse." "THE SPREAD — The gap between best bid and best ask. **It stays one tick when
liquidity is deep and healthy. It widens the instant liquidity thins out, which is
your earliest warning that a level is about to break** or a fast move is coming."
Two rule rows: "FAST TAPE INTO A LEVEL — Aggression is committed. If the level still
holds, that is absorption worth trading. If it breaks, the speed carries the
continuation." "SPREAD WIDENS — Liquidity is pulling. **Do not lean on the level, and
do not chase into the gap**, the fills get ugly and the stops get run." THE FULL
PICTURE: "Depth tells you what is resting, delta tells you who is aggressive, speed
tells you how urgent, and the spread tells you how healthy." Computable content: the
spread-widening veto is free, minute-scale and perfectly self-scaling if expressed
as a multiple of the level's own modal spread — and note the *fast tape* rule is a
conditional amplifier, not a filter: fast tape plus hold equals a better fade, fast
tape plus break equals a continuation.

**p7 — the ladder as trigger, in five steps.** (1) "**Bring a level to the ladder** —
Never watch the DOM in a vacuum. Come to it with the shelf, the ledge or the value
edge already marked." (2) "Watch who is aggressive at the level — Are market orders
attacking it or drying up? Urgency arriving at your level is the start of a trade."
(3) "Watch what the passive side does — **Does resting size hold, reload and stack,
or does it pull?**" (4) "Score it with delta — **Aggression with movement is
continuation. Aggression without movement is absorption**, somebody big is on the
other side." (5) "Then execute, small and precise — The DOM gives tight entries with
tiny stops." Computable content: step 4 is the whole discriminator in one line and
it is a two-variable classifier (aggression magnitude x price displacement) with the
two outcomes pointing opposite ways — the same fork `dom-lesson-6` p7 raised between
absorption and exhaustion, here resolved on the aggression axis rather than the
volume axis.

---

## dom-lesson-7.pdf

**p3 — icebergs, and why they exist.** Text-only. "An iceberg order is a large order
broken into smaller visible chunks. Only a small portion shows on the DOM, the rest
sits hidden, reloading the same level as the visible size gets hit." The mechanism:
an institution wanting 500 contracts "cannot just hit the market, there are not
enough passive buyers on the bid to absorb the full size. Dumping it all at once
would thin the book instantly, collapse the bid several ticks, get the order hunted
for liquidity and cost massive slippage." How it runs: "A trader wants 10,000 but
shows 500 on the DOM. As the 500 fills, another 500 appears, replenished
automatically from the hidden reserve." One-line definition: "An iceberg is hidden
true size at one price. **The DOM shows 20 or 30 contracts, the level absorbs
hundreds.**" Computable content: the ratio of cumulative traded volume at a price to
peak displayed size at that price is the iceberg estimator, and the source's own
illustrative magnitude is roughly an order of magnitude.

**p4 — trading the iceberg, with a 2-tick window.** "One level that keeps reloading
while heavy volume trades into it is hidden institutional interest," and the trap is
named: "Short term traders assume the level must break because it keeps getting hit,
so they pile in with the pressure. The iceberg absorbs all of it, price holds, and
they are trapped. **You want to be on the iceberg's side of that trade.**" The
three-step method: "Step 1, watch the level hold — Loads of orders hitting the bid or
ask, stacking constantly, and the level refuses to give." "Step 2, confirm the reload
— Large volume being held, the visible size refreshing instead of dying. **Then wait
for more participants to add on within 2 ticks.**" "Then enter — Bid absorbing and
price holding confirms the long above the level. Offer absorbing and price capping
confirms the short below it." Computable content: a third confirmation window
alongside the 3-tick reward system and the 18-tick adverse excursion — here **2
ticks** is the radius within which additional participants must join before entry.
Form only; on our assets this is a small multiple of the modal spread, and it is a
*participation* window rather than a displacement window, so it is a different
quantity again from the other two.

**p5 — spoofing, and the one-line discriminator.** "Spoofing is the opposite trick:
large visible orders placed to create a false impression, then cancelled before they
ever fill." The classic play: "A trader posts a big sell wall at the offer so it looks
like selling pressure is incoming. Algos and humans short into the perceived
weakness. The spoofer cancels the wall before it fills and the market moves the other
way." ICEBERG VS SPOOF, THE TELL: "Both look like big size. The difference is
behaviour when hit: **an iceberg REPLENISHES as it trades, a spoof VANISHES before it
trades. Reload is real, cancel is fake.**" Computable content: the discriminator is
whether the size decrement is accompanied by *trades* — a pure cancel versus a fill —
which is directly separable in MBP data and requires no thresholds at all.

**p6 — spotting the spoof, four signatures.** "VANISHING WALLS — Large visible orders
that disappear the moment the market begins to trade into them." "THE FLICKER —
Orders that appear and vanish repeatedly **within seconds**, without ever filling."
"ODD PLACEMENT — Size posted far from normal resting levels, or at strange amounts
designed to attract attention." "FAST CANCELS — Instant cancellation the moment
aggressive orders hit near the level." The defensive routine: "**Check the prints, not
the display** — Is volume actually trading into that level, or does the visible size
evaporate without meaningful prints?"; "Never chase spoofed momentum"; "Wait for the
real flow — Enter only after genuine absorption appears or the fake orders are
removed." Computable content: order lifetime, cancel-to-fill ratio at a price, and
placement distance from the touch are three independent, cheaply computed spoof
scores; the flicker's timescale is stated in seconds, i.e. sub-minute.

**p7 — layering, flipping, and the master filter.** "LAYERING — A spoofer posts a
ladder of fake orders at several prices... It looks like deep conviction, it is
theatre. Tell: **the whole stack pulls together the moment price approaches.**"
"FLIPPING — Size that jumps from the bid to the ask and back, faster than any real
order manager would work... Tell: **no prints trade, only the display flickers.**"
The unifying rule: "The single reliable filter under all of it is **the refresh rate
against the prints**. Real hidden size (an iceberg) refreshes as volume trades
through it, you see the prints. Fake size (spoof, layer, flip) refreshes or vanishes
with no prints at all. **Prints are truth, the display is a story.**" Closing habit:
"Before you trust any wall, ask one question: is volume actually trading into it? If
the size keeps changing but the tape is silent, it is a lie." Computable content: a
single ratio — book-size churn at a price divided by traded volume at that price —
separates every manipulation pattern in this lesson from a genuine defender, and it
is dimensionless, hence portable without calibration.

---

## fp-lesson-8.pdf

**p3 — what the footprint is, and what it is not.** "The footprint chart is the DOM's
history book. It shows the actual volume traded at each price level, broken down into
aggressive buys at the ask and aggressive sells at the bid, printed inside every
candle." "WHAT IT SHARES WITH THE DOM — Same raw material... The footprint is what the
ladder looked like after the fight." "**WHAT IT DOES NOT SHOW — Pace.** The DOM shows
the speed and rhythm of orders arriving, the footprint shows the completed result."
The example grid shows price rows 6664.50 down to 6662.75 with left (bid/sell) values
6412, 6761, 8399, 8255, 4120, 3980, 2110, 1540 and right (ask/buy) values 6, 3, 12,
220, 410, 512, 77, 22. Computable content: the explicit statement that the footprint
carries no pace is important — every pacing rule in the library (refresh intervals,
tape speed, the flicker) requires the ladder or the raw tape, and a footprint-only
feature set structurally cannot express them.

**p4 — the diagonal read.** "You do not compare them straight across, you compare them
**diagonally, like a ladder**." The highlighted rule: "Compare the **56 ask to the 5
bid one tick below.** Diagonal, not side by side." Explanation: "Buyers lifting the
ask at one price fight the sellers hitting the bid one tick lower. Reading up the
diagonals shows you who is winning the longs, reading down the diagonals shows you the
shorts." A secondary callout, THE SPREAD COST NOBODY THINKS ABOUT: "Every market order
crosses the spread and pays for it. On NQ the aggressive side pays that cost on every
single fill. **Using limit orders instead of market orders saves serious money if you
trade often**, that idea is the core of high frequency trading." Computable content:
the imbalance comparison is explicitly ask[p] versus bid[p-1] (one tick down), not
ask[p] versus bid[p] — a specific offset that a naive implementation gets wrong. And
the limit-versus-market aside is the same finding as `refill-effect` p11's 1.80
versus 0.81, arrived at from cost first principles.

**p5 — imbalances, with the named ratio.** "An imbalance is where one aggressive side
heavily outweighed the other at a price." Buy imbalance: "Buyers lift the offer far
more than sellers hit the bid." Sell imbalance is the mirror. The p3 grid is reused
with ask values 220, 410 and 512 highlighted as flagged imbalances, captioned "Most
platforms mark them when one side is **3x to 4x larger** than the diagonal opposite."
THE THRESHOLD box: "**3x to 4x is the standard flag. Below that it is noise, above it
someone was genuinely one sided at that price.**" Computable content: the library's
only explicitly named imbalance ratio, and unlike every tick constant it is
dimensionless and ports directly — 3x-4x on the diagonal pair.

**p6 — stacked imbalances, with a count threshold.** Opening: "**A single imbalance is
noise. Stack several and you have a zone the whole market will remember.**" The
highlighted rule: "**Three or more imbalances in a row build an unfinished auction,
the market tends to return and finish it.**" "STACKED BUYING — Several buy imbalances
in a column show aggressive buyers stepping up tick after tick. It marks a demand
zone, price often revisits it and holds." "STACKED SELLING" is the mirror. The page
also notes the footprint "draws its own value area and POC inside each candle or
session... **The candle POC is where the heaviest business traded, and it behaves like
a magnet on the retest.**" Closing: "Stacked imbalances and single prints are the
footprint's version of poor highs and lows. They are magnets and targets, mark them
and let price come back to repair them." Computable content: a **>=3 consecutive
diagonal imbalances** zone constructor, which is a second, independent way to build
the zone object alongside the large-aggressive-print clustering of `refill-effect` p5
— and the two should be compared rather than assumed equivalent. Note also the
per-candle POC here is the same object `fp-lesson-9` p5 uses for the POC-flip
detector.

**p7 — the footprint at your levels.** Five steps. (1) "**Bring the level** — VP
ledges and shelves, value edges, old POCs. The footprint is the microscope, the level
is the slide." (2) "Read the diagonals into the level — Who was aggressive on
approach? **A level hit by exhausted aggression behaves differently to one hit by
fresh conviction.**" (3) "Look for stacked imbalances — **Two or three** flagged
imbalances in a row at a level is real pressure, one alone is noise." (4) "Watch the
high volume prices — Where the biggest numbers printed inside the candle is where the
argument happened. Those prices matter on the retest." (5) "Pair it with the DOM —
Footprint for the history, ladder for the pace." Computable content: step 2 is a
restatement of `whos-in-control` p4's arrival-mode rule, measurable here as the
diagonal imbalance trend *on approach* rather than at the touch. Note step 3 says
"two or three" where p6 said "three or more" — treat the stack count as a tunable in
the 2-4 range rather than a constant.

---

## code-3-orderflow.pdf

**p3 — risk, the non-negotiables.** Five items. (1) "**Predefine the stop before
entry** — Hope is not a strategy. The stop exists before the trade does, and it never
moves to avoid pain." (2) "Never revenge trade — Losing a trade is not a reason to
risk more." (3) "**Break even, but not too early** — Moving the stop to entry turns
potential losses into neutral outcomes. Do it too early and you cut every winner
short, do it at the logical spot." (4) "Cut losers fast — Once the idea is invalid,
exit immediately." (5) "Risk to the account, not the ego — Overleveraging destroys
accounts faster than bad setups. **0.5 to 2% per trade, consistently.**" Computable
content: the 0.5-2% band is already self-scaling, and item 3 is a direct caution
against the naive breakeven-stop rule — it must be keyed to structure (the protected
extreme of `18k-payout-session` p8), not to a fixed distance or time.

**p4 — exits, static and dynamic, split by account type.** "STATIC EXITS — Fixed risk
to reward ratios, predefined targets like VWAP, single get-in get-out setups. Decided
before entry, executed without debate." "DYNAMIC EXITS — Trailing stops, partial
scaling, volatility based exits, time based exits. **The trade earns its room as it
proves itself.**" The account-type split is the useful part: "**FUNDED ACCOUNTS —
Favour fixed RR plus one partial. The drawdown rules punish creativity, structure
wins.**" "PERSONAL ACCOUNTS — Trail stops, leave runners, use break even management.
Your account, your convexity." Goal: "Protect profits without strangling potential."
Computable content: the exit policy is explicitly a function of the **account
constraint**, not of the signal — which agrees with `a-clean-continuation-short` p6
choosing a nearer exit under consistency rules, and with the whole prop-economics
chapter of `refill-effect`. A mill optimising expectancy alone will pick the wrong
exit for a barrier-constrained account.

**p5 — the five traps.** Framed as "Success is edge plus risk management plus
psychology." "FOMO — **Missing trades costs nothing. Forcing trades costs
everything.**" "LOSS AVERSION — If fear is driving decisions, reduce size until the
fear disappears. Then earn it back." "OVERTRADING — Usually boredom or revenge in
disguise. The fix is **a written definition of the A+ setup, and permission to do
nothing until it appears**." "EUPHORIA — After the big win, pride books the next loss.
The best session to go flat is the one right after your best session." "ATTACHMENT —
Do not tie your identity to one setup or one idea." No numbers, but the overtrading
fix is the human form of an abstention gate with a pre-registered setup definition.

**p6 — bias, balances, and the hard location veto.** Framing: "Context is what
separates order flow traders from button clickers." The highlighted rule: "Price can
only do three things: **stay in a balance, leave a balance, or return to a previous
one.**" THE OBJECTIVES: "Single prints from the TPO chart and balances, the zones of
fair value. These are the destinations price trades between." The veto, stated as
hard: "**INSIDE A BALANCE — If your level sits inside a balance, avoid trading it.
Choppy, low edge, the auction has not decided anything there.**" The counter-rule:
"**AT THE EXTREMES — Trade levels at the edges of balance or outside it, where
decisions actually happen.**" Example logic: "Rejection from a balance with an
unfilled single print above: bullish bias. Acceptance below a balance: bearish bias.
**Higher timeframe narrative first, lower timeframe entries second.**" Computable
content: this seconds `your-mistakes-with-absorption` p6's "not near POC or inside
balance" as a hard gate rather than a learnable weight, and it adds the three-state
price machine that `mastering-amt-vp` p12 turns into three entries.

**p7 — flexibility, the weekly loop, and the 40% value area.** "**Treat the thesis
like a box** — The bias has a validity zone. While price respects the box, the bias
lives. The moment price violates it, build a new bias, do not defend the old one."
"Build the weekly bias every Sunday — Then compare it against professional traders,
Jim Dalton, Rizzo, and study the differences." "Journal the context, not just the
trades — Biases, context, emotional state." THE INTRADAY TWEAK, which is a concrete
parameter change: "**Set the value area at 40% instead of 70% for intraday work. The
tighter range produces cleaner, more frequent reactions at the edges.**" Closing:
"There is no magic pattern. Discipline, structure and adaptability." Computable
content: the 40%-versus-70% value-area parameter is a direct, testable knob on every
value-area rule in the library, and the source's stated reason — more frequent, cleaner
edge reactions — is exactly the coverage-versus-precision trade the mill is tuning.
The thesis-as-a-box rule is a bias invalidation zone with an explicit
do-not-defend-the-old-bias clause.

---

## origin-of-the-move (1).pdf

**p4 — the aggression schematic.** A hand-drawn black-background schematic titled
"Agression schematic:" carrying the definition inline: "Aggression = a market order
that crosses the spread to get filled now, accepting a worse price for immediacy.
It shows intent/urgency of wanting to continue price." Left half draws the two
directions, a green-circled buy print and a red-circled sell print on candle bodies.
Right half draws a sequence: sell aggression with result on the way down, a green
buy print absorbing at the low, an up-move, and then that same buy-aggression area
boxed in white and revisited later. The prose adds two derived reads: **aggression
testing** — on return to an old aggression area, if price "cuts through and closes
beyond it, they have no result, and price usually continues until it finds the next
area of aggression" — and **aggression memory**: "price remembers where aggression
traded. That is not a slogan; it is the single strongest family of features in the
research paper's model." Computable content: the level object is an *aggression
area with a memory*, tested by a close beyond it, and the source names this family
as the one that carries the model's signal.

**p5 — the squeeze schematic and the refill clock.** A hand-drawn schematic with a
rounded box labelled "Multiple buyers' aggression being abs for the catalyst"
containing three green-circled prints, arrows running from it up a climbing
diagonal of green prints annotated "Aggressive buyers willing to price higher at
worser prices so the orders will refill with more aggression against the previous
passive sellers", feeding a fast vertical release whose base carries a circle
labelled "ENTRY" and a dotted line "Protected by buyers (covered)". The bottom
label names the mechanism: "**REFILL clock: AGGRESSIVE (NO RESULT) to AGGRESSIVE
(WITH RESULT)**." Closing line: "If squeezes always worked, that entry would be the
whole model. They don't, and statistics say so." Computable content: the refill
clock is a **state transition on the same participant** — aggression that got no
result, later getting result — which is a two-episode object and cannot be detected
from a single window.

**p6 — the OFM, the whole model on one slide, with two entries marked.** The full
schematic read left to right: a catalyst box "Multiple buyers' aggression being
abs", a rally labelled "Buyers punch to the wall", a top where "Sellers regain
control" holds the first attempt, a pullback into a second box labelled "**Buyers
refill entry here higher risk area**", then a second climb that breaks the wall and
releases, with the base circle labelled "Buyers refill back entry here" and
handwritten "Entry", "**SL -> below aggression**", "Protected by buyers (covered)".
The caption is explicit about which is the default: "Two entries are marked. The
early refill entry is higher risk, higher reward. **The main entry comes on the
re-squeeze after the failure**, with the stop loss below the aggression that built
it... That stop rule is not decoration: below the aggression is the point where the
read is simply wrong." The boxed rule: "On the re-squeeze, after the first squeeze
fails and price retests the failure area. Earlier refill entries exist but carry
more risk; they are marked on the schematic for completeness, **not as the
default**." Targets: "discretionary and come from the higher-timeframe thesis; as a
scalp model, **1R to 3R is the working zone**, and trailing handles the rest."
Computable content: this is the library's canonical entry template and it is a
**second-attempt entry by construction** — attempt one must fail before the setup
exists. The stop is defined semantically (below the aggression that built the level
= where the read is falsified) rather than by distance, which makes the stop
distance a function of the zone's own geometry.

**p7 — example 1, a B+ short on the retest of a failed squeeze.** A real 40-range
chart, price roughly 29288 down to 29218, times 10:39-10:51, with a blue reference
line near 29251. Circled prints upper left are "buyers willing to price in, getting
exhausted into the catalyst." A large outlined rectangle marks "the failed-squeeze
area", with a maroon box above and a green box below carrying a "SELL 1" fill tag.
The caption gives the geometry numerically: "the bracket on screen is the live
trade: **27 ticks risked for 40**." The ordered text boxes: "Buyers keep pricing in
and keep getting absorbed into the catalyst. On the return to the failure area,
sellers keep their result: the refill clock has flipped in their favor," then "Short
on the retest of the failed squeeze, **stop above the sellers' aggression. Where the
aggression fails is where the read is wrong, so that is where the stop lives.**" A
Speed of Tape (10) histogram below shows print clusters at the catalyst (10:43-44)
and again at the retest (10:50-51). Computable content: entry is on a later retest,
with at least two earlier buyer prints marked before the failed-squeeze box even
forms — **not a first-touch entry** — and the R:R here is 40/27 ≈ 1.5, i.e. a
working scalp geometry well short of the 3:1 the refill paper deployed.

**p8 — example 2, the retest of failed sell aggression.** A real range-bar chart,
roughly 29925 to 29875, times 10:13-10:32, blue reference near 29910. A red circle
at lower left marks "the aggression that started the squeeze". A thin white
rectangle mid-chart marks the entry area, with red and green tags at the retest.
Caption: "Sellers willing to price lower, the catalyst drawn at the lowest
aggression, and the entry bracket sitting on the retest." Text boxes: "**The squeeze
releases fast (the speed of tape spikes with it), then fails back above the
catalyst. Sellers hitting a wall into passive buyers is the confirmation to wait
for**," then "Entry on the retest of the sell aggression with the stop just above
it. **The target is discretionary and comes from the thesis, not from the pattern.**"
The tape histogram shows one tall red spike at 10:19 coinciding with the fast
release. Computable content: the confirmation is a *conjunction of a tape-speed
spike on release and a failure back above the catalyst* — a two-part, timed event,
and the source explicitly refuses to let the pattern set the target.

**p9 — example 3, an uptrend OFM completed, with the exit rule.** A real range-bar
uptrend with three stacked white rectangles stepping upward, "the white boxes
marking where buyers' aggression was absorbed and retested on the way up". Text
boxes: "Buyers get absorbed while willing to price higher. **Price crossing above old
sell aggression converts that past participation into passive support underneath.**
The punch to the wall gets no reward, and the pullback lands in the area buyers
controlled," then "Entry on the buy aggression returning into that area, stop at the
low or below the aggression. **Trail until buyers hit a wall and get fully absorbed:
that absorption is the exit.**" The tape histogram is buy-dominant across the
sequence. Computable content: two rules the earlier passes did not carry — a **level
polarity flip driven by price crossing an old opposite-side aggression zone**, which
converts it from resistance into passive support; and an **exit defined as the
mirror of the entry signal** (absorption of the trend-side aggression), not as a
target or a trail distance. Three white boxes on one leg is another direct
multi-peak confirmation.

**p10 — example 4, the whole sequence in one red path, with two failures.** A
screenshot from a different application dated 20/06/2026, price roughly 30610 to
30535. A thick hand-inked red path traces the model end to end, starting at a
cluster of circles labelled "sellers show they are in control", arcing down to a
red-filled rectangle, a leg labelled "refill", and continuing to a second smaller
high with handwritten "sl". Text boxes: "Buyers hit the wall and get absorbed,
sellers regain control. **The squeeze lower punches into a wall twice and gets no
reward either time. No result, twice, from the same participants is as loud as the
tape gets**," then "The entry is the failure of the squeeze, where sellers step back
in with result. Stop above the aggression that failed." Computable content: **two
consecutive no-result attempts by the same participants at the same wall is stated
as the strongest available signal**, and the entry fires on the second failure. This
is the multi-peak claim promoted from a condition to the signal itself.

**p11 — replay, setup only, and an explicit refusal to enter.** A "Replay Manage"
tool (NQ-CME, 10/07/2026 10:15, speed x1, market depth on). Price 29950 down to
29865; a wide magenta rectangle marks the catalyst across a flat stretch near
29910-29920 before a sharp drop toward 29885-29888. Caption: "Balance with
absorption on both sides, sellers holding control. The catalyst is marked; the
squeeze fails fast lower and sellers punch straight into passive buyers." Text
boxes: "Inside a balance a squeeze can go either way; it depends who is most in
control. Sellers are, so the squeeze lower is the expectation, and its failure is
the setup," and the explicit rule: "**No short until price reclaims above the
catalyst and fails again. Patience here is the trade.**" Computable content: a named
waiting condition — reclaim above the catalyst *and* fail again — with the page
showing no entry taken. The "inside a balance a squeeze can go either way" line
also states that the balance context does not determine the direction; control does.

**p12 — replay, the fill, and the order type doing the filtering.** The same replay
with a full DOM ticket at right (NQ-202609, Open P/L -125.00 $). A small white
rectangle around 29897-29900 marks "the retest area the entry came from", with
bracket lines projected right. Caption: "Filled short one contract; the bracket is
live on the ladder." The two text boxes carry the most reusable execution rule in
the document: "**The order rests below the wick so only aggressive continuation can
tag it in. If sellers don't come with result, there is no fill and no trade. The
order type is doing the filtering**," and "Stop above the intermediate wick. If it
stops out, fine: the re-entry sits right below, and the read has not changed."
Computable content: **the resting order is itself a filter** — the same argument
`refill-effect` p11 made statistically (limit 1.80 versus market 0.81 "precisely
because it demands the flush"), here stated as design intent. And the re-entry rule
is explicit: a stop-out does not invalidate the read, and the re-entry level is
pre-placed.

**p13 — replay, the trail and the pre-registered objective.** The same replay
advanced, Daily P/L now positive. Two magenta bands are projected forward; price
runs lower in tall down candles. Caption: "The stop has walked down above each new
pocket of aggression as price breaks lower; the trade runs into the higher-timeframe
objective from the daily profile and takes profit there." Text boxes: "**Cut the loss
branch off while the win branch keeps running. Each new aggression pocket that forms
below gives the stop a new home above it**," and "**The thesis, not a feeling: the
objective was the value area of the daily profile, set before the trade existed.**"
Computable content: the same protected-extreme trail as `18k-payout-session` p8 but
keyed to *aggression pockets* rather than swing highs, and a target that is a
named profile object fixed before entry. Note the value-area objective is asserted
in prose only; no VAH/VAL/POC is actually drawn on the chart image.

**p14 — the passive edition, where the signal is an absence.** A second replay
trade, long, complete, price 29950 down to 29800. A tall green rectangle sits above
a dark-red rectangle sharing a boundary near 29900 where a circle and cyan "OFM"
mark the entry; a wide purple band near 29793-29800 marks the buyer zone below.
Caption: "The second replay trade, long this time, at take-profit. The squeeze
failed passively and the entry triggered above the buyers." The text box is the one
the structure crosswalk flagged as decisive: "**The squeeze fails with no aggressive
orders at the failure at all: the speed of tape just dies. The absence of result is
itself the signal, and it is the quieter, more common version of this model.**"
Entry rule: "Entry above the buyers, stop below the aggression, scalp target in the
1R to 3R zone. Same model, passive edition." The tape histogram is scaled 0-100 here
(against 0-50 elsewhere) and shows a dense cluster then a **gap**. Computable
content: a fully specified quiet-failure detector — tape-speed collapsing to near
zero at the level where the squeeze should have delivered — and the source says this
is the *more common* form. A detector built only on visible absorption prints will
miss the majority case by the author's own account.

**p17 — the stat sheet, every number with its caveat.** No figure; a three-column
table, Statistic / Value / Caveat. THE RAW CONCEPT: touches that hold, unfiltered =
**42%** ("base rate, not a trading rule"); fade every touch = **-0.285R/trade**
("after modelled costs; nobody should run this"). SELECTION: touch grading,
out-of-sample = **AUC 0.63** ("modest by design; placebo scores 0.51"); hold rate,
worst to best decile = **25% -> 63%** ("monotonic, but historical buckets"); order
flow alone = **AUC 0.54** ("memory + location do the real work"). EXECUTION / THE
REFILL: median winner's dip past the touch = **18 ticks** ("a median; queues can be
less kind live"); resting limit, Q1, independent engine = **68.8% / PF 1.80 /
+$2,112** ("64 trades, one quarter, engine we didn't build"); market order, same
signals = **27.2% / PF 0.81 / -$405** ("proves the execution effect, nothing more").
OUT-OF-SAMPLE: 79 held-out sessions = **+0.143R, PF 1.19, +78R** ("542 trades; one
regime slice of one year"); independent engine, full year = **+$3,803, PF 1.45,
~+0.07R** ("stricter fills; the conservative quote"); worst quarter = **-$647, PF
0.76** ("disclosed and counted, not trimmed"). ROBUSTNESS: reverse split / rotating
folds = **+0.14R to +0.22R** ("AUC 0.61 to 0.64; still one dataset"); parameter
grid, train versus test = **rank corr 0.92** ("a plateau, not proof any setting
works"). PROP ECONOMICS: pass at $60/$80/$100 per R = **96.7% / 92.2% / 85.7%**;
-4R daily stop = **+14 pts pass rate** ("the largest single lever found"); first
payout at $80/R = **95.5%** ("payout capped ~$2k/cycle"); three staggered accounts =
**P(>=1 payout) ~ 99.6%** ("assumes independence and the edge persisting"). Footnote:
"All figures are historical simulation after modelled costs... Educational
statistics, not a promise of future performance." Computable content: the two
numbers that matter most for our arbiter and were not in the earlier passes are the
**AUC 0.63 grading ceiling against a 0.51 placebo**, and the **monotonic 25%->63%
decile hold rate**, which together say the achievable object is a calibrated
ranking, not a classifier — and the honest ceiling is modest.

---

## ny-am-session (1).pdf

**p4 — trade 1, the refill, before.** A dark order-flow platform screenshot,
NQ-202609, "10D - 8T", **40 Range** bars (not time bars), clock 09:09-09:37. Panels:
range-bar price, a "Speed of Tape (10)" histogram, a **CVD sub-panel** (red/green
step line plus smoothed grey overlay, scale +-200), and a DOM ladder beside a 3-bar
pink/mint volume-delta profile. A teal arrow reads "sellers absorbed at the bottom,
no result for the push"; caption: "Sellers get absorbed at the bottom of the range
here, **the two small circles** marking where buyers stepped in and held. The stop
sits just below." The live read: "sellers are being absorbed at the bottom, stop just
below these buyers that are in control, targeting higher timeframe objective."
Ladder tags: pink at 29804.25, last price 29761.50 just above a green tag at
29757.25, and an orange STP tag reading "-260.00 $" at 29744.25 — the stop sitting
roughly a dozen-plus points under the marked absorption. The source frames the
mechanism as the signal: "**That refill is the signal itself... a read of who's
actually winning the fight for that price.**" Computable content: two absorption
prints, not one, mark the zone; the stop sits below the *lower* of them; and the
target is a pre-existing HTF objective rather than a multiple.

**p5 — trade 1, after.** Same chart zoomed out, a green arrow "buyers regain
control, the refill runs to $755" with a vertical marker and crosshair at the entry
moment; **CVD ramps up sharply coincident with the markout**. Sequence: absorption
prints, refill begins at the marked instant, price runs "straight into the target",
closes for $755, stop having sat "just below the absorption", target "the higher
timeframe objective sitting directly above". Called "the cleanest trade of the
day", with the disclosure that four trades ran and "not all of them were this
tidy". Computable content: the CVD slope turning positive at the refill instant is
a directly observable confirmation coincident with entry, and it is the fast lane in
live form.

**p6 — trade 2, the loss, before.** Same platform; a decline into a level bounded by
a green rectangle with prior rejection marks above and a third retest lower. Teal
arrow: "**third retest of the level, still no buyers stepping in**"; caption: "Price
retests a level that had already rejected sellers twice. No buyers show up to defend
it a third time." A hand-drawn white diagonal on the CVD panel underscores falling
delta into the third test. The source flags this as the deliberate counter-example:
"Sellers had already hit this level twice with nothing to show for it... On the
third retest, still nothing, so the short went in: 'I'm in these shorts with my stop
just above, targeting this area, kind of low risk.'" Clock 09:59-10:14, immediately
after trade 1. Computable content: this is the **multi-peak rule applied in the
opposite direction** — two prior no-result pushes plus a third with still no
defence, read as the level being abandoned rather than defended. It is the same
counting logic as the winning trades and it produced the day's loss, which is
exactly why it matters.

**p7 — trade 2, after, the stop-out.** A salmon arrow reads "stopped for -$100, the
level held anyway"; caption: "Stop sits just above, risk kept deliberately small.
Price ticks back up through it before the actual move develops." Tags: a teal STP
"-235.00 $" at 29621.25, last price 29614.00, a red SL TP at 29608.50 — the stop
about 7 points above last. The CVD panel's scale has stepped down to a -500 to -900
range, i.e. strongly negative delta into the failed short. The stated lesson is
precise: "**Low risk doesn't mean no risk, and a level failing to hold twice doesn't
guarantee it fails a third time.**" And: "The read was reasonable given what was in
front of me. The market just didn't cooperate. That's a real cost of doing this for
a living, not a mistake to edit out of the video." Note the realised loss is -$100
while the on-chart tag reads -235.00 $, consistent with the six parallel accounts
running different sizes on one signal. Computable content: **heavily negative CVD
into a level did not carry the break** — a direct counter-example to using
cumulative delta magnitude as a break predictor, and it comes from the same author
whose winning trades read delta the other way.

**p8 — trade 3, trailing convexity, entry at R:R 0.69.** Teal arrow "entry goes in
here at only R:R 0.69 on paper"; caption: "Entry goes in at R:R 0.69, a small
starting reward against the risk. **Aggressive buying lines up right as the level
confirms.**" Tags: green at 29654.50, last 29650.50, orange STP "-290.00 $" at
29640.00. The source names the model and the arithmetic: "The entry itself wasn't a
high reward-to-risk trade on paper: R:R 0.69, meaning the initial target was smaller
than the initial risk. **Most traders would skip that outright.**" Computable
content: the second independent instance in this library of a deliberately sub-1R
entry justified by level quality plus a trailing exit — the acceptance rule cannot
be a minimum-R:R filter at entry.

**p9 — trade 3, after, R:R 1.83 from the trail.** Green arrow "stop trailed behind
price, now R:R 1.83". A gold tag reads "BUY 1 | R:R 1.83" on a purple line at entry
29652.00, with a red block below reading "-290.00 $ | **58 ticks**" — the platform
computes live R:R on the position, initial risk fixed at 58 ticks / -$290, trailed
exit at 29680.25. Sequence: entry at a "kg one retest" setup, fixed initial stop,
stop walked behind price as it runs, exit only when the trail is tagged — "the same
entry that started at R:R 0.69 had become R:R 1.83, just from letting the stop do
the work instead of a fixed target." Computable content: a **2.65x improvement in
realised R:R produced entirely by the exit policy on a fixed entry and fixed initial
stop** — the cleanest available measurement of how much of this method's edge lives
in the trail rather than the trigger.

**p10 — trade 4, before, deceleration as the trigger.** A teal arrow "sellers
exhausted right into the resistance level" points at a red-outlined rectangle with
price tags 29767.75/29764.75, several circle markers on local pivots, gridlines
29820 down to 29730, and a CVD panel (scale 50 / 0 / -200 / -400 / -600) whose curve
**flattens and rolls over into the level**. Caption: "Price stalls into a resistance
level already marked out ahead of time. **The move up is losing aggression candle by
candle, not gaining it.**" The trigger is stated as deceleration, not location: "the
move into it was losing steam rather than accelerating, **which is the tell I was
waiting on, not just fading a level because it's a level.**" Computable content: a
**first-difference condition on aggression into the level** — the fade requires the
approach to be decelerating, which is computable as a negative slope on per-bar
aggressive volume or CVD rate over the approach leg, and it is self-scaling.

**p11 — trade 4, after, and the session roll-up.** Salmon arrow "this short closes
the day, up a 1k". Tags: teal STP "-100.00 $" at 29769.25 just above the resistance,
red SL TP at 29764.25 matching p10's band, and a green LMT "855.00 $" far below at
29721.50 (~42.75 points) — a resting target much larger than the trade needed.
Caption: "The short goes in against that resistance, risking about $100. It's the
last trade of the day." The result was a deliberately capped win: "Risk was kept to
about $100, **deliberately small this late in the day with the objective already
close.**" Session roll-up: "**Four trades shown here, three wins and a loss, netting
a bit over $1,000 across six accounts.** That's the honest version of what a
professional session looks like: not zero losses, just a process that holds up
across the losses too." Computable content: **risk per trade is scaled down as the
session objective is approached** — a time-and-progress-dependent sizing rule, which
is the intraday analogue of the -4R daily stop and appears nowhere in the crosswalk.

---

## 2345-funded-session (1).pdf

**p4 — reading an all-time-high environment.** Same platform (NQ-202609, 10D-8T, 40
Range), a grinding uptrend with three magenta markers at three consolidation
shelves, each boxed as a failed reclaim attempt. Caption: "The grind higher this
session's thesis was built against. **Multiple failed attempts to reclaim the range
below**, each one adding to the case that buyers were priced in, not just leading."
The CVD sub-panel shows a rising step-line on a thousands scale, roughly 1.7K-3.9K
of net cumulative delta through the grind; right-edge delta bars are uniformly
mint. Small live tags "+2.03" and "+2" sit beside columns headed "SD+2"/"SD+1" —
live standard-deviation band readouts, i.e. the VWAP-deviation machinery of
`vwap-lesson-10` running on the live chart. Stated rule: "The weekly delta profile
showed heavy buying aggression behind the move, **which is a different statement
than 'price is going up.' It's a statement about who is actually in control of the
auction.**" The objective was deliberately left neutral: "wait for the pullback and
trade within the directional push, not... predict a target in advance."

**p5 — the entry signal, and the one named numeric trigger.** Same chart zoomed on
the last consolidation shelf before a breakout leg, three magenta markers at its
left edge. The local delta bars flip to two dark-red bars under one mint bar, read as
"sellers who had been rewarded at this level earlier failed to hold it a second
time." The trigger is the most quantitative rule in either session document: "a tool
that flags a specific condition: **a 350 percent divergence between buying and
selling aggression alongside a small imbalance**, printed automatically as a green
box when it fires... passive absorption on one side and aggressive pressure on the
other, at the same price." The source is explicit the box alone is insufficient — it
must sit "inside a higher timeframe area where the opposing side was already known to
be weak", and "that combination... is what separated this from a random entry on a
green box alone." Named an "origin of the move" long, entered where the box fired.
Computable content: a **350% aggression divergence at a price, gated by an HTF
weakness context** — the ratio is dimensionless and ports directly; the gate is the
same location-before-flow ordering the whole library asserts.

**p6 — real absorption versus a level that merely worked before.** A different,
non-platform chart pulled from a prior session (the one behind the $18,000 payout).
A grey/red horizontal band marks "a resistance area that had been used, and dumped
from, multiple times"; a magenta delta-type oscillator spikes in short bursts, mostly
staying under the band, while a green hand-drawn arrow labels a stretch where price
grinds up into it: "price rising = high conviction of that session sellers had insane
control". Expanded: "**across the entire consolidation session, CVD was dying while
price held or drifted up, meaning the passive limits at that level were being
consumed and reloaded, not defended for free.**" Computable content: the
discriminator between a level that "worked before" and one "currently being tested
and passed" is a **price-versus-CVD divergence measured across the whole
consolidation**, not at the touch — price flat-to-up while CVD decays says the
passive side is absorbing at cost. This is a slow-window version of the absorption
test and it is independent of the 350% tool.

**p7 — trade 1 live, the long, at R:R 5.59.** Same platform; a sharp impulsive leg
off a base with a grey rectangle marking a small **microbalance** consolidation
partway up (two magenta markers on it) and a curved blue baseline (VWAP) under the
leg, clock ~09:21-09:31. Sequence: price shows "the strength to push through a short
term microbalance", entry on that push, then management becomes mechanical: "once
the position moved favourably, **the stop trailed to the most recent protected low
rather than a fixed distance**, so the trade could only give back a defined amount of
what it had already earned." Caption states the planned geometry: "The long entry,
**R:R 5.59** planned against a stop below the microbalance low that formed the
entry." Target: "set at a higher timeframe level rather than a fixed tick count...
**react to structure that already exists, don't invent a round number to aim at.**"
Computable content: the **microbalance** is a named, small-scale balance object whose
low defines the stop — a zone-local structural stop rather than a distance — and the
planned R:R here (5.59) sits far above the 0.69 of the previous document, so the
method spans nearly an order of magnitude in entry geometry.

**p8 — trade 1, trailing to target.** Continuation with two grey microbalance shelves
stacked below the final push. Tags: a pink LMT-type "1080.00 $" at 29358.25, an
orange "345.00 $" at 29321.50 mid-trail, a green SL TP near 29304.25 close to the
original protected-low stop; delta bars mint, CVD ~3.7K-3.9K. The stated goal ties
the target to account arithmetic rather than to structure: "this trade needed to do
two things: **recover a loss carried from the prior session, and add the 500 dollars
left on the table the day before**... It hit target, both conditions met, protected
low trailing intact the whole way there." Rule restated: "**The stop only ever moves
toward protecting what the trade has already made, never further into risk.**"
Computable content: a monotone-non-increasing risk constraint on the trail, and a
target set by a **cross-session P&L obligation** — which is a real behaviour in the
sources and a genuine contaminant if the trade selection is being modelled as
independent draws.

**p9 — trade 2 live, the short, capped by a consistency rule.** Same chart type, a
down-leg with magenta markers, a grey shelf and a red supply band. Tags show a
breakeven-trailed stop at 29370.25, last 29367.25, and a green LMT "310.00 $" at
29354.75. The setup mirrors trade 1 inverted: "entered on a lower push after the same
kind of microbalance read as the first trade, this time working in the opposite
direction." The target is explicitly capped by the account, not the chart:
"deliberately smaller than the setup alone would have called for, **capped by a
funded account consistency rule: a prop firm payout requirement that no single day
can represent too large a share of total profit**... sizing the plan to the account's
rules, not just to the chart." Session ends by plan: "the account was up 1.3k for the
day off these two trades", stopped "not because the setups stopped, because the plan
for the session was already complete." Computable content: a **daily profit cap
driven by a consistency rule**, which truncates the right tail of the daily
distribution — the mirror of the -4R daily stop truncating the left — and a
session-completion stop that is independent of remaining signal quality.

**p10 — the numbers, both days counted.** Not a price chart but the account's own
August 2026 P&L calendar. A red cell reads **-$558** ("3 trades", the prior session),
the next day a green cell reads **+$2,345** ("5 trades", this session); the widget
header shows "Payout Requests $0" and "Net P&L **+$1,787**". Quoted: "Both numbers
are shown here directly off the account, not restated from memory, because **a funded
account series that only ever shows the green days isn't actually showing the
process.**" Caption: "A losing day, immediately followed by this session, both
counted." Computable content: nothing mechanical, but it establishes the
document's own disclosure standard, and note the headline session of five trades is
reported here while the narrative covers two — the other three are not shown.

---


---

## Completeness note

This pass read, at full resolution, every page listed in the brief:
`refill-effect (1)` 5, 7, 12, 14, 15, 17, 18, 19, 20, 21 (the retry agent's own
skip list, complete); `trapped-buyers-one-retest` 4 and 10; and the chart-bearing
pages of all seventeen structure-half documents, located by scanning every page of
each PDF for image area and drawing count rather than by guessing. That came to
134 rendered pages, of which 122 were structure-half. **No page named in the brief
was left unread**, and no document on the list was skipped.

Pages deliberately not read, with reasons. Within the seventeen structure
documents, pages that the scan showed to be pure prose with no figure, no
schematic and no screenshot were not rendered — title pages, contents pages,
promotional callouts and text-only chapter openers. Where such a page nonetheless
carried a rule the diagrams depend on, the batch readers picked it up from the
adjacent figure pages and it is recorded above (this is why, for example,
`18k-payout-session` p11, `a-clean-continuation-short` p6/p9/p11,
`dom-lesson-5` p4, `dom-lesson-7` p3/p5/p6/p7, `fp-lesson-8` p3-p7 and
`code-3-orderflow` p3-p7 appear here despite being text-only: they were rendered
and read because their document's figure pages were, and their content proved
load-bearing).

Two limits on what is above. First, four documents in the library were not in
scope for this pass and remain read only at text level by the crosswalks:
`vix-lesson-4`, `only-trade-big-trades (1)`, `anatomy-of-a-losing-start (1)`,
`stop-re-entering`, `average-unprofitable-trader`, `code-1-thesis`, `code-2-risk`,
`emotion`, `data-engine`, `dom-lesson-6`, `fp-lesson-9`, `whos-in-control` and
`reading-delta`. The last four were covered by `DIAGRAM_NOTES_FLOW`; the rest were
not diagram-read by anyone, and `only-trade-big-trades` pp.14-15 in particular
(the gamma/balance regime inversion, ranked third on the structure crosswalk's
top-ten) has never been visually confirmed. That is the largest remaining gap.

Second, resolution limits. Several live-platform screenshots carry order-ticket
digits too small to read reliably at 125 dpi — noted inline wherever it affected a
figure (`origin-of-the-move` pp.7-14 bracket tags, `ny-am-session` and
`2345-funded-session` ladder tags, `vwap-lesson-10` p8's Source dropdown). Where a
number is quoted above it was legible or stated in the surrounding prose; where it
was not, that is said explicitly rather than guessed. Two pages had content cut off
at the page edge in the source PDF itself (`tpo-lesson-3` p5's "HOW TO USE THEM"
box and p6's Excess High panel). One figure's colour coding is unreliable:
`origin-of-the-move` p7 circles buy prints in red where the schematics use red for
sells, so circle colour should not be trusted as a side indicator on the live
charts.

Finally, the standing law, restated because this document is dense with the
sources' own numbers: every tick count, dollar figure, contract threshold and
percentage above is the source author's, measured on NQ/MNQ (or in a few cases ES),
under their own caveats — historical simulation after modelled costs, one dataset,
or the author's own account records. They are recorded as **form only**. The
dimensionless quantities (the 3x-4x diagonal imbalance ratio, the 350% divergence,
the >=3 stacked imbalance count, VWAP deviation multiples, R-multiples, the 0.5-2%
risk band, the -4R daily stop, the rank-correlation robustness criterion, and every
percentile or slope formulation above) are the ones that port without
recalibration. Everything else must be re-measured on our assets before use.

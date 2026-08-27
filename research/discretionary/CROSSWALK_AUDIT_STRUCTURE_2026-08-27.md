# Crosswalk audit: structure/process half of the discretionary library

Audit date 2026-08-27. Baseline audited against:
`design/ENTRY_V2_DISCRETIONARY_FEATURE_CROSSWALK.md` (status 2026-08-19).
Scope: 19 PDFs, 262 pages, read completely in text; four diagram pages rendered
(`origin-of-the-move` p.6, `mastering-amt-vp` p.14, `only-trade-big-trades`
p.10, `code-1-thesis` p.5). Page numbers below are printed page numbers, which
match PDF page indices in every one of these documents.

**Headline.** No PDF in this set is fully captured. The crosswalk is faithful as
a list of *objects* the documents name and systematically lossy on three things
the documents spend most of their words on: (1) the **order and dependency**
between reads, stated in every process document as a strict precedence and
implemented in the crosswalk as co-equal atomic families for trees to interact;
(2) **regime conditionality that inverts the meaning of the same evidence**,
most sharply the long-gamma/short-gamma split that decides whether quiet at an
extreme is the signal or the trap; (3) **every measured result the authors
published**, discarded under the crosswalk's line "No author threshold is
treated as truth." That policy is defensible for thresholds. It also discarded
the author's own falsification of a mechanical entry law, the measurement that
raw flow alone scores AUC 0.54, and the measurement that unfiltered level-fading
loses money while graded selection over the same concept makes it — all three of
which are evidence about *this program's* design choices, not thresholds to be
copied.

---

## Part 1 — Per-PDF delta

### mastering-amt-vp (1).pdf (27 pp)

- **p.9 — the Failed Auction setup has a narrow definition the crosswalk
  generalises away.** It is not "any break of balance that comes back." It
  requires balance, a break out of it, and price actually travelling to and
  tagging **a prior, older balance at its POC**, then instantly rejecting there.
  The target is direction-mapped: reject from above a prior POC → target the
  established balance's **VAH**; reject from below → target its **VAL**. The
  ledger lists "failed auction" as one entry in a formation-context family with
  no prior-balance-POC object and no directional target rule.
- **p.11 — a labelled hard negative.** Two NQ charts share the identical visual
  grammar (break of balance, return to a grey zone). Chart 2 is a *trend
  continuation*, not a failed auction, because it never tags a prior balance and
  rejects there. "Same visual grammar, opposite trade." The crosswalk has no
  analogue of a stated near-miss class.
- **p.12 — three distinct entries off one composite balance, one of which is a
  latching rule.** (a) break-and-retest of the broken boundary, trade with the
  break; (b) return inside and re-accept, **the bias flips** to fading toward the
  other side; (c) traverse straight through the whole balance without holding =
  one side fully priced in, and **every retest from there trades with that side
  until proven otherwise**. (c) is a persistent state, not an event.
- **p.13 — higher timeframe outranks the trigger, asymmetrically.** A clean
  lower-timeframe short level that fires while the higher timeframe is inside
  balance near its lower boundary gets **less leniency, not more**. "The auction
  context outranks the trigger." The crosswalk has no leniency asymmetry.
- **p.14 — overnight inventory (6pm→9:30 ET) is absent entirely.** Net
  long/short across the window carries into the open as path of least
  resistance. The judging tool is the LVN inside the overnight profile: one clean
  distribution → the net environment continues; a **double distribution** makes
  the LVN between the humps the decision point, "respected" if the open continues
  the overnight direction, "disrespected" if it does not. The overnight shelf
  reads the same way: hold it → price likely stays inside the overnight range;
  break it **with real aggression** → likely heading to the overnight extreme.
  The rendered schematic adds a POC-alignment annotation to the LVN line.
- **p.15 — the 94% number and its stated use as an abstention rule.** 94% chance
  of touching **either** the overnight high or the overnight low during the
  session (not both). "Used correctly, that number is a reason to **not** take a
  trade rather than a reason to take one": a long a few points above the ONL with
  a tight stop under it is a right level at a wrong time.
- **p.16 — 73%.** RTH opening inside the previous ETH balance → 73% chance of
  reaching that ETH profile's mid (MPOC). Stated use: hold and trail rather than
  take the first easy target at VAL.
- **p.18 — the real "80% rule" has preconditions.** Open above or below the
  previous day's value area, then trade back inside it **for two consecutive
  30-minute periods** → 80% chance of trading completely through the entire value
  area to the other side. The crosswalk's acceptance features encode neither the
  two-period precondition nor the full-traverse objective. Same page: Steidlmayer's
  original **six** day types (non-trend, normal, normal variation, trend, neutral,
  running trend neutral), classified on first-hour range versus what followed.
- **p.19 — IB and gap statistics, with an explicit instrument-transfer warning.**
  Close outside the IB cited at 65–75% continuation; failed excess back inside the
  IB at 70–75% likelihood of trading the other side; CME's own documented result
  that ~68% of a day's price action falls within one standard deviation of that
  session's POC. Gaps: 70–75% eventually fill, but small gaps (<0.5%) fill
  same-session ~65% while gaps >1% fill same-session only ~35% and are more likely
  to keep running; down gaps 62% vs up gaps 59%. And directly: a systematic study
  of gap-fill on Micro Nasdaq found the fade **failed at every entry time tested**.
  "Gap-fill statistics that look solid on ES do not automatically transfer to NQ."
- **pp.20–25 — a full calibrated prior table set the crosswalk records nowhere.**
  1,040 ES sample days across four contracts: day-type base rates; opening-location
  rates; overnight touch rates (ONH-or-ONL 92.5–95.4%, both 20.2–23.9%, ONVPOC
  86.2–90.1%, ONVAH 74.3–78.9%, ONVAL 68.6–74.7%); IB structure (at least one IB
  broke 96.6–99.6%, **neither IB broken 0.38–3.45%**, both broke 22.3–36.0%);
  RTH volume and range modes with 1-SD bands per contract.
- p.26 — "a D day is a real outcome" is stated as a checklist item, i.e. an
  undecided session is an acceptable terminal state rather than a defect.

### amt-lesson-1.pdf (14 pp)

- **p.6 — the four profile shapes carry directional meaning, and the library
  contradicts itself on two of them.** Here: P = short covering (fat top, thin
  tail below, late in up moves, expect balance after); b = long liquidation (fat
  bottom, late in down moves); D = balanced (fade edges to POC); B = double
  distribution (two balances joined by a thin bridge, treat each as its own value
  area, **the bridge is the line in the sand**). `mastering-amt-vp` p.7 defines P
  as resolving *down* out of the bottom and B as the mirror resolving higher.
  These are different taxonomies under the same letters. The crosswalk records
  neither the taxonomy nor the conflict.
- **p.6 — "P and B are warnings, not signals."** The move is being finished by the
  losing side covering, not by fresh conviction. It does not call the top; it tells
  you to **stop chasing and watch the balance that forms next**. Also "thin repels,
  fat attracts."
- **p.9 — rule two of the auction.** Out of balance, the **ledges of the prior
  balance** are what hold for the move to continue; the level that was support
  becomes the resistance that fuels the next leg.
- **p.10 — five day types, each with an explicit permission or prohibition.**
  Trend day: continuation only, **never fade**. Normal day: fade extremes, target
  POC. Normal variation: early range extended once (roughly doubling), then
  balance — trade the push, then **switch** to fading. Neutral day: keep size
  small until it picks. **Non-trend day: "Nobody shows up. Narrow, quiet, usually
  in front of news. The edge is knowing there is no edge, stand down or scalp
  tiny."** That last is the cleanest stand-aside rule in the library and it is
  absent. Same page: "Most blown accounts are a day type error." Name the day
  **before** you size the trade.
- **p.11 — four open types, ordered by conviction, absent entirely.** Open Drive
  (strongest statement the market can make, do not fade, continuation on shallow
  pullbacks); Open Test Drive (tests a key reference first, finds no business,
  drives the other way — "hands you the level your risk lives behind"); Open
  Rejection Reverse (moderate, expect two-sided trade, **treat the rejection
  extreme as the day's reference**); Open Auction (nobody in control, expect a
  balance day, early extremes are fade material). The open type is stated as the
  **earliest read of the day type**.
- **p.12 — the pre-open checklist is ordered and time-partitioned**: three checks
  before the open, three in the first half hour, terminating in "No DOM or
  footprint confirmation, no trade. AMT gives the where, never the when."
- **p.13 — two anti-patterns with no crosswalk analogue.** "Reading a finished
  profile on a live day: a D shape at 11am can be a trend day by 2pm. **Re-read
  after every big impulse**" (the profile read is non-stationary within the
  session). And "marking every level on the chart... if everything is a level,
  nothing is" (a level-count discipline).

### vp-lesson-2.pdf (9 pp)

- **p.5 — the document's central structural claim is absent from the crosswalk.**
  VAH, VAL and POC **recalculate and drift with the session**, "like a lagging
  indicator." A **ledge does not move**. Shelves and ledges are "real extremes...
  structure, not statistics." The crosswalk implements POC/VA/VWAP migration and
  HVN/LVN but has no fixed-edge object: the exact price where a build-up starts
  and a fade-away begins.
- **p.4/p.7 — an explicit no-trade zone.** Shelf = the body of agreed business, and
  its interior "is rotation, chop and noise." "**Trade the ledge, not the middle of
  the shelf.** At the ledge the market either defends the business or abandons it."
- **p.6 — naked POCs and composites, plus a timescale-matching rule.** A naked POC
  (a prior session's POC price has not traded back to) "acts like a magnet" and a
  list of them above and below is a ready-made target list. Composite HVNs that
  survive across days or weeks are "the levels the whole market respects." And:
  "**Zoom the profile to match the trade you are hunting** — a shelf on a 5-minute
  profile is a scalp level, the same shelf on a composite weekly profile is a swing
  level."
- **p.7 — confluence as the filter, with an ordering.** "Stacked levels first, lone
  levels last." A naked POC that lines up with a composite shelf is "a level worth
  building a whole session around." The crosswalk exposes the objects but carries no
  stacking/confluence count.

### tpo-lesson-3.pdf (10 pp)

- **p.9 — extremes are not one class, and the split is decisive.** "**Excess marks
  where an argument ended. Expect those extremes to hold on first test.**" Against
  that, single prints and poor extremes are magnets and target list. The crosswalk's
  `disc_test_` family models repeated tests and response decay uniformly, with no
  finished-versus-unfinished extreme distinction.
- **p.5 — single prints**: one 30-minute period's row with no overlap from any other
  period; price moved through so fast only one window touched it; unfinished
  business, a magnet and a target when price moves toward them. Absent as a named
  object.
- **p.6 — excess**: two or more rows of the *same* letter printing at the extreme,
  then rejection. Absent.
- **p.7 — poor highs and poor lows, with a per-instrument reliability gate.** Weak
  rejection during probing moves, the extreme "just stops, it never finishes."
  **On NQ** they appear as a single TPO tail and are useful, because NQ's thinner
  structure lets the probe print clean. **On ES** the thicker structure creates
  shorter, firmer tails, so poor extremes are **"less reliable on ES and rarely
  used."** This is an explicit statement that one of the library's structure
  primitives does not carry across instruments, and it is absent.
- p.8 — IB read: IB holds all day → rotational, fade IB edges to POC; early
  one-sided range extension → trend day, do not fade.
- The VP/TPO disagreement concept on p.3 *is* captured (`disc_auction_`).

### vwap-lesson-10.pdf (9 pp)

- **p.4 — a banded-location eligibility gate, stated as two rules.** "One: the
  trades worth taking live **beyond the 1 band and ideally at the 2**, deal with at
  least the 1. Two: **only trade VWAP extremes WITH absorption, never on the touch
  alone.**" Plus the falling-knife warning: if there is no confirmation, or the draw
  beyond the band is clearly still extending, do not trade against it. "Deviation is
  probability, not a wall." The crosswalk carries VWAP migration but no deviation-band
  eligibility and no monotone "higher the premium, higher the chance of reversal."
- **p.6 — the three-step CVD plan is ordered and includes a distinct stall state.**
  Divergence (price rising while CVD falls = the move is being carried by passive
  orders); breakout grading (**breakout on flat or falling CVD is likely a fakeout,
  "low conviction dressed up as momentum"**); absorption zones (**price stalling
  while CVD keeps climbing or falling** = large players quietly taking the other
  side, and "that standoff usually resolves violently"). The stall-with-continuing-CVD
  signature is the library's closest cousin to a quieted-extreme discriminator.
- **p.7 — anchored VWAP is absent.** Anchor to a major swing high/low, or to the
  **event** (CPI, FOMC, an earnings gap, the session open): "the true average of the
  move the news created, which is the level institutions defend." Convergence of
  session + weekly + anchored VWAP marks a heavyweight level. The crosswalk's VWAP is
  session-anchored only.

### vix-lesson-4.pdf (10 pp)

The crosswalk maps this entire document into `disc_fvol_` as "soft regime and target
headroom." Every operational rule in it is lost.

- **p.5 — a hard stand-aside threshold.** VIX below 13 (expected ES range under 30
  points) is "usually not worth fishing. **Knowing there is no edge today IS the
  edge.**" VIX below 14: shrink targets to scalps, stops under 3 points, **"or stay
  out entirely."**
- **p.4/p.5 — a regime→sizing ladder.** VIX ~12.5 → ~30-pt day, scalps only 3–5
  points, "fishing for 10-point runners on a day like this is how the account
  bleeds." VIX ~16 → ~50-pt day, the sweet spot for structured R. VIX 15–18 is
  "the best pocket for pressing structured risk-reward." VIX ~22 → ~95-pt day: do
  not force tiny stops, take partials earlier, trail aggressively. VIX above 20:
  widen stops to 3–4 points or scale out quicker, "the noise band is bigger, a tight
  stop is just a donation."
- **p.5 — range completion as a state transition.** Track realized range against
  implied range through the day; **once the implied range is mostly done, expect
  mean reversion and chop, "the fuel is spent."** The crosswalk has realized/forecast
  consumption and headroom as continuous features but not the consequence that the
  session's behavioural regime flips once consumed.
- **p.6 — a price/vol sign-cross state, absent.** ES up / VIX down = healthy trend,
  continuation. ES up / VIX up = divergence, the rally may fade, hedging demand
  building underneath. ES down / VIX up = normal risk-off, momentum likely continues,
  do not rush the knife. **ES flat / VIX flat = expect chop, "scalp the rotations or
  stand down."** Simple version: rising VIX intraday → expansion away from value;
  falling VIX intraday → rotation and levels respected.
- **p.7 — the two event-day traps, named as one error in two directions.** Fading a
  pre-event tape as if it were a normal chop day, and chasing breakouts after the vol
  crush as if it were still an event day: "same mistake, opposite directions: trading
  yesterday's regime." Into the event, **ignore the implied range**, catalyst days can
  blow straight past it.
- **p.8 — curve shape voids the level.** Contango: trade normally with your levels.
  **Backwardation: cut size hard, widen everything, "respect that the auction is
  broken until the curve normalises"** — "levels that mean nothing until it resolves."
  "A VIX of 18 in calm contango is a totally different day to a VIX of 18 ripping into
  backwardation. The level alone lies, the shape tells the truth." VVIX: a rising VVIX
  warns a quiet VIX is about to get loud, "an early tell before the range even
  expands." The crosswalk's fvol family has level, slope, acceleration and regime
  persistence but no curve-shape state and no levels-are-void regime.
- **p.9 — a fade/continuation arbiter conditioned on vol direction.** Balance on the
  profile + VIX dropping → play the rotations, fade the edges to POC. Balance + VIX
  rising → prepare for the range break, **do not lean on the walls the way you would
  on a falling-VIX day**. "When VIX is dropping hard, size smaller on breakout
  attempts, they fail into rotation more often."

### origin-of-the-move (1).pdf (19 pp)

The most decisive document in the set, and the most heavily lost. Its back half is
the author's own out-of-sample evaluation of exactly the kind of thing this program
is building.

- **p.18 — the mechanical entry, rebuilt causally, is negative.** "When the entry was
  rebuilt from scratch and tested causally, with every trace of hindsight stripped
  out, it came back negative: on the order of **−0.16R to −0.54R out-of-sample**. The
  earlier version that looked profitable had quietly used information from later in
  the day to pick which setup was 'the one.' Remove that peek and the mechanical edge
  disappears. **What survives is a grading system for touches you have already found,
  and an execution rule about which side of the book to stand on.**" Same page: without
  the higher-timeframe thesis the feature set "is basically a coin flip," and every
  quoted pass rate assumes the thesis is already aligned.
- **p.15 — raw flow alone is near-null; memory and location carry the signal.**
  "Raw order flow alone (delta into the touch, approach speed, imbalance) barely beat a
  coin flip: **AUC 0.54**. The families that carried the signal were **memory** (has
  this zone been defended before) and **location** (is it at a real auction edge).
  Aggression builds the level. It is the level's history that predicts the next touch."
- **p.15 — selection flips the sign of the same concept.** "Fade every touch of every
  level with no filter and you lose **−0.285R per trade** after costs, because **only
  42% of touches hold**. Grade each touch first (has it held, was it built by size,
  where does it sit) and take only the best and it flips to **+0.143R per trade**,
  out-of-sample, on 79 sessions the model never saw. Same concept. The only thing that
  changed is which touches you take."
- **p.15/p.17 — where the defence actually happens.** "The **median eventual winner
  dips 18 ticks past the touch** before it works. The defence does not happen at the
  front edge of the level. It happens **inside it**, where the refill actually reloads.
  If you act the instant price tags the level, you are acting at the exact point where
  the data says the trade has not started yet." Execution: identical signals, same
  engine — **resting a limit inside the zone 68.8% / PF 1.80 / +$2,112; market orders
  at the touch 27.2% / PF 0.81 / −$405**. The research config rests 12 ticks in with a
  32-tick stop, "the depth matters less than the principle."
- **p.14 — the passive variant, and it is the more common one.** "The squeeze fails
  with **no aggressive orders at the failure at all: the speed of tape just dies. The
  absence of result is itself the signal, and it is the quieter, more common version of
  this model.**" Entry above the buyers, stop below the aggression, 1R–3R target.
- **p.11 — the side is a prior-control read, not a flow read at the extreme.** "Inside
  a balance a squeeze can go either way; it depends who is most in control. Sellers
  are, so the squeeze lower is the expectation, and **its failure is the setup**." And
  the cadence: "**No short until price reclaims above the catalyst and fails again.
  Patience here is the trade.**"
- **p.12 — the order type as the abstention device.** "The order rests below the wick
  so **only aggressive continuation can tag it in**. If sellers don't come with result,
  there is no fill and no trade. **The order type is doing the filtering.**"
- **p.12 — re-entry after a stop, stated.** "Stop above the intermediate wick. If it
  stops out, fine: **the re-entry sits right below, and the read has not changed.**"
  Re-entry is licensed by an unchanged read at a specified relocation, not by a count.
- **p.16 — the largest measured lever is not entry-side.** "**A −4R daily stop adds
  ~14 points of eval pass rate.** Cap the bad day mechanically. This one rule moved the
  needle more than any parameter in the whole study." Also: "Wait for the second test,
  or for memory, construction, and location to agree. **The first touch of a fresh zone
  is the weakest version of this trade.**" And on scaling: "Payout is capped near $2k
  per cycle by the trailing drawdown... **scale by count, not by risk.**"
- **p.17 — the full stat sheet with caveats attached.** Touch grading AUC 0.63
  out-of-sample against a placebo at 0.51; hold rate worst→best decile **25% → 63%,
  monotonic**; out-of-sample +0.143R / PF 1.19 / +78R over 542 trades on 79 held-out
  sessions; independent engine full year +$3,803 / PF 1.45 / ≈+0.07R; **worst quarter
  (most recent) −$647 / PF 0.76, disclosed and counted, not trimmed**; reverse-split
  and rotating folds +0.14R to +0.22R at AUC 0.61–0.64; parameter grid train-vs-test
  rank correlation 0.92, described as "a plateau, not proof any setting works." Prop
  Monte Carlo (4,000 paths, Topstep-style 50k, −4R daily stop): pass 96.7% / 92.2% /
  85.7% at $60 / $80 / $100 per R; first payout at $80/R 95.5%; three staggered
  accounts P(≥1 payout) ≈ 99.6%.
- **p.16 — the objective is a barrier problem, not an alpha problem.** "A prop
  evaluation is a barrier problem: reach the target before the trailing drawdown reaches
  you. What that rewards is a **positive (even neutral) expectancy edge with the right
  risk geometry**."
- **p.13 — trailing convexity, and where targets come from.** "Cut the loss branch off
  while the win branch keeps running. Each new aggression pocket that forms below gives
  the stop a new home above it." The target was the value area of the daily profile,
  "set before the trade existed."
- p.2 — the squeeze catalyst is anchored explicitly: **drawn at the lowest (or highest)
  first aggression**, not at the extreme. p.4 — the aggression filter is
  instrument- and session-specific (NY AM on NASDAQ, min 30 / max 60 contracts per
  print) "and I adjust with the session's volume."

### only-trade-big-trades (1).pdf (19 pp)

Second most decisive, and the source of the regime inversion the sweep-4 question
turns on.

- **pp.14–15 — the same evidence means opposite things in the two gamma regimes, and
  the balanced case removes the reward requirement.** He would take the OFM trade
  **only in a short-gamma environment**, because the setup needs an expansive move to
  pay. "**In a long gamma environment the market balances and chops instead, and both
  extremes get absorbed most of the time.**" "The same chart pattern, read the same
  way, is a different trade depending on a condition you check **before you look at
  the chart at all**. In balance, the squeeze failing is not a precursor to a drive.
  It is just the top of the range doing what the top of a range does." Frequency of
  the A++ version: "once or twice a week, if that," later "maybe even twice a month" —
  "a handful of times a month at most, and... you cannot build a month around it."
  Against that, stated twice without hedging: **"80 percent of the time the market is
  in balance. 80 percent of the time you are in a long gamma environment."**
  The other-80% trade (p.15) is a **failure-of-aggression** trade and "the key
  difference is that **you no longer need your own side to be rewarded**." Sequence:
  buyers absorbed at the top of the range → price returns to that absorption area →
  those buyers are **still** not being rewarded → price goes lower → wait for the test
  back into it → enter → target back to where sellers previously had control. "In
  balance, sell pressure and sell imbalances get absorbed **passively**, and passive
  absorption is exactly what carries price in a balanced market. **The thing that made
  a passive move a warning sign in a trending environment is the mechanism you are
  trading here.**" And: "It is the trade most people talk themselves out of, because
  they are waiting for a squeeze that a balanced market has no reason to produce."
- **p.13 — the passive-move trap in the opposite regime, with a required ordering.**
  You are long, price is going up, and there is no buy aggression anywhere in the move.
  "These are normally short term swings rather than the start of anything."
  "Confidence is highest at exactly the moment the evidence is weakest." The required
  version is a sequence **and the order matters**: "**First the opposition's aggression
  fails, so they are exhausted, trapped or absorbed. Then your side arrives
  aggressively. Opposition failing on its own is only half of it, and half is what most
  people trade.**" The crosswalk's ordered state family has adverse-test → reclaim →
  lift → retest but does not encode this two-party ordering as a veto.
- **p.4 — the two-sided-absorption abstention.** "The trap is that both sides usually
  show effort at the same time. Buyers absorbed at the top of a range, sellers absorbed
  at the bottom of it. When that is the picture, **you do not know who is in control,
  because nobody is yet.** His instruction there is to **wait for the break** rather
  than to pick a side inside the range." The crosswalk computes two-sided absorption as
  a continuous feature and records no abstention consequence.
- **p.6 — body versus wick.** An aggression print inside the candle **body** means that
  side was willing to trade at worse prices and got carried in their direction; the same
  print on the **wick** means they pushed and were absorbed. "Same bubble, opposite
  meaning... it is the cheapest read on the chart and most people never make it
  consciously."
- **p.5 — the imbalance is only interesting where it co-locates with aggression**, and
  the reason is intent: "The best price for a seller is higher. **If sellers are
  accepting lower and lower fills, they are not trying to get a good price, they are
  trying to get size done.**" The crosswalk carries 350% diagonal counts as standalone
  features.
- **p.7 — the origin of the move is not where the squeeze failed.** "Entering on the
  failure is entering on the moment the previous attempt died. Nothing has confirmed
  that a new attempt is starting. You have identified where something ended, and treated
  it as a beginning. **The failed squeeze... is context, not a trigger.**"
- **p.8 — the actual trigger and the funding mechanism.** Price **taking out the wicks
  above**: buyers now willing to pay higher, which they refused to do through the entire
  squeeze. Underneath it, "the resting liquidity above, where buyers had orders sitting
  untouched, gets **converted** once price trades through it. That conversion is what
  funds the move." Confirmation comes from buyers **absorbing the refill area below**
  (a price where sellers previously failed and therefore reload) rather than breaking
  down through it.
- **p.9 — two entries exist and only one is nameable, with an explicit accepted cost.**
  He takes the retest, not the break, because at the retest the level has already been
  defended once; the earlier alternative is "**prefiring the trade**." The honest cost:
  "the retest does not always come. Some of these move without giving one back, and you
  miss those. **He accepts that trade explicitly, because the entries you can name are
  the ones you can repeat, and a setup you cannot repeat is not a setup.**"
- **p.10 — the permission condition is a signed structural asymmetry.** The support is a
  **minor volume node at the extreme of balance** ("minor volume nodes tend to give clean
  rejections and they tend to start trends"), and **below it there is no volume**: no
  participation, nothing to hold price. "Volume tries to build lower and fails. That is
  the asymmetry: above the node there is structure, below it there is nothing." The
  crosswalk carries forward-object density and room but not thin-behind/structure-ahead
  as a permission condition.
- **p.12 — why prefiring costs you, argued on win rate rather than direction.** At the
  premature long there was sell aggression, a sell imbalance, repeated sellers stacked
  above, and **CVD extremely bearish and sitting below its own median**. "The entry can
  be good and the win rate can still be poor, and **on a prop account variance is the
  thing that removes you, not being wrong about direction**." CVD-relative-to-its-own-median
  as a veto is absent.
- **p.16 — late aggression in a balanced session is a management rule, not a new entry.**
  When aggression finally turns up inside a balanced session the move is disproportionate
  (~4–5R by his read) "because it is arriving into a market that has spent hours absorbing
  everything." "**The trade that pays like that is the one you were already taking all
  session, held longer because aggression showed up to justify it.**"
- **p.17 — the prop maths argues against the high-R/low-frequency shape.** "An evaluation
  is not asking you to produce a large return from a small number of trades. It is asking
  you to reach a profit target without breaching a drawdown limit, **which rewards a
  higher win rate and steady participation**." Failure case stated: ten of the rare setups,
  all ten lose, you are level only on the eleventh — survivable with a long runway, not on
  a trailing drawdown. Conclusion: "**Trade a framework, not a strategy. A strategy is a
  single pattern, and a single pattern only fits one regime, so it leaves you either
  forcing trades or sitting out most of the month.**"

### anatomy-of-a-losing-start (1).pdf (12 pp)

- **p.7 — the re-entry rule, and it is narrower than the crosswalk's policy.**
  "Getting stopped is not a reason to get back in. **It is not a reason to stay out
  either.**" The rule: "*Let us see if we come back down. That is the only time I look
  for a re-entry.*" — "**Price has to come back to the level. Not near it, and not on a
  different level that looks similar. If it does not return, there is no trade, and the
  loss just stands.**" Stated consequence: "this is also why the two stops in a row did
  not turn into four. The level was not offering anything, so there was nothing to take."
  The crosswalk's policy row reads "unlimited sequential re-entry subject to occupancy
  and risk laws," which is the opposite shape of constraint: it bounds count and
  occupancy, the source bounds **location and offer**.
- **p.4 — the thesis contains no direction, deliberately.** "**You will never have a bias
  in your thesis. You just want areas of reactions.**" Rationale: "If the thesis says up,
  then every level that fails becomes an argument to try again. If the thesis says here
  are the areas where reactions are likely, then a level failing is just information."
  This bears directly on how a side arbiter should be framed, and it sits in tension with
  `origin-of-the-move` p.18 ("the thesis... is what supplies direction"). The library
  holds both and the crosswalk records neither.
- **p.5 — a 44% win rate is the model working correctly, and clustered losses are
  expected.** Nine trades, four wins, five losses, worst point −$480, close +$500. "The
  losers are supposed to be frequent. They are supposed to be small... **Four losses in a
  row is not a rare event here. It is roughly what a 44% win rate produces on a regular
  basis, and it will happen again in the first twenty minutes of some other session.**"
- **pp.8–10 — the decision order is what makes the win rate survivable.** Stop location is
  decided **by structure, before entry** ("35 ticks because that is where the idea is
  wrong"); **size is decided by the stop**; **the target is whatever the higher timeframe
  already owed**. "At no point is the ratio chosen first and the levels bent to fit it...
  If the stop is placed to make a ratio look good rather than to mark where the idea is
  wrong, the trade gets stopped for reasons that have nothing to do with the read, and the
  losses stop being cheap." The two demonstrated ratios (35:188 = 5.37:1 and 15:211 =
  14.07:1) carry the explicit caveat that 14:1 "is not the normal case and should not be
  treated as one. It happens when the level is unusually precise, which is rare."
- **p.10 — "Ratio checked, not chosen. The objective is where it is. If the ratio is poor,
  skip it."** An abstention gate on target geometry. Also: "**Move to break even when the
  reason weakens. Not at a fixed number of ticks.**" And trail behind **protected** levels,
  meaning swings the market has already defended once.
- **p.11 — the session-level laws.** One contract; "**size goes up when the account buffer
  grows, not when confidence does**"; two contracts only on the highest-quality level and
  only with a trailing plan attached. **A daily objective (~$500) then stop, "including on
  days when the read is still good and the market is still moving."** And: **"A maximum
  loss at half the objective. The bad day is capped smaller than the good day."** The
  crosswalk's policy row records a daily stop but not the asymmetric objective/loss pair
  and not the stop-on-target rule.
- p.11 — a no-trade recording habit: the last stretch of the session has no trades at all,
  just the read spoken aloud against the running tape, to be replayed later against what
  happened.
- **p.12 — the whole session is regime-scoped.** "The same model in a fast negative gamma
  market looks different to what you have just read. **Take the structure of the decisions
  from it, not the numbers.**"

### stop-re-entering.pdf (17 pp)

- **p.6 — the three steps are a strict dependency chain, not three co-equal inputs.**
  Location → reward vs result → delta. "**Step one is location, and it carries the other
  two.** If you don't know where price sits in the higher-timeframe auction, you don't know
  who should be in control, so you don't know who to give leniency to. **Every re-entry
  spiral I see starts here: the trader is fighting for a reversal in the middle of a
  balance, where neither side has an argument, and every wick looks like absorption because
  nothing has context.** ...**Without step one they filter noise.**" The crosswalk exposes
  all three as atomic families and asks CatBoost to learn the interaction; the source states
  it as a precondition.
- **p.10 — the four-stage absorption ladder, and stages 1 and 4 are indistinguishable at
  the moment of entry.** "Failed absorption and confirmed absorption **look identical at
  the moment most people enter. The difference only exists in time, which is why the
  checklist has stages instead of a snapshot.**" (1) **Initial defense** — aggression hits,
  volume above average, price holds; "this is where beginners enter, and it is not
  confirmed. It can be temporary liquidity that gets pulled and stops you instantly." (2)
  **Replenishment** — the level refreshes as it keeps getting hit, with maintained or
  growing size; "**my minimum filter is three ticks of replenishment; one or two is the
  classic fake-out zone.**" (3) **Exhaustion** — the aggressor's volume declines and delta
  turns against them. (4) **Lift-off** — the absorber flips **from passive to aggressive**
  and price accelerates away. And the number: "**absorption fails roughly 27% of the time
  when there's no pacing confirmation behind it.**"
- **p.9 — the digit filter is a joint two-sided condition.** "You want the opposite side to
  come in and **thicken**, and you want the losing side to **thin out**. Doubles and triples
  where your side acts, singles where the losers used to be. **When both happen at your
  level, the filter is passed. When neither happens, there is no trade**, no matter how
  strong the urge is after the last stop-out." Not one continuous absorption score.
- **p.9 — trapped inventory has a stated trigger.** An outsized delta print at the highs
  means a crowd committed at one price; the next few bars tell you whether they were
  rewarded or trapped. "**If the print sits at the highs and price can't leave, those buyers
  are inventory waiting to be liquidated.**" The short triggers when price **breaks below
  the print zone**, with CVD rolling over behind it.
- **p.12 — the reward quantum, and the passive/aggressive division of labour.** "Two
  upticks, which is **my minimum, two to four**, for calling it a reward system. **Enter on
  the aggression, not on the passiveness. Passive absorption is the setup; aggression is the
  trigger.**" (Note the direct tension with `only-trade-big-trades` p.15, where in a balanced
  regime you explicitly do not need your own side rewarded.)
- **p.13 — a stated latency budget on confirmation-to-entry.** The bad entry "came **six to
  eight ticks above the absorption, which is far too delayed. A delayed reward system means
  probably no reward system.**" Checklist form (p.14): "My entry sits **within a tick or
  two** of that confirmation, not six to eight ticks late."
- **p.14 — the re-entry rule and the binary abstention rule.** "**If this is a re-entry, it
  passes every box above from zero, not on the strength of how close it already got.**" And:
  "**If any one is unticked, the answer is no trade yet, not a smaller trade. Waiting is
  free.**" That last contradicts the size-by-grade rule in `average-unprofitable-trader`
  p.11; both are in the library.
- **p.14/p.15 — the daily stop gates re-entry, not just loss.** "Daily stop. I am above minus
  four R for the day. **If I am not, there is no trade, re-entry or otherwise.**" And the
  cover arithmetic: five failed re-entries at −1R is −5R, past the −4R stop, so "**a trader
  honoring the daily stop never sees re-entry five. The stop doesn't just cap the damage, it
  deletes the worst version of the day before it happens.**"
- **p.5 — the two named mechanisms behind re-entry.** The **break-even effect** (Thaler &
  Johnson: right after a loss people become unusually drawn to any bet offering a shot at
  getting back to even, at worse odds than they would normally accept) and the **realization
  effect** (Imas: once a loss is *locked in* people become more careful; while a loss still
  feels *open* they take bigger risks). "**A stop-out locks the loss. Treat the next trade as
  a brand new decision under fresh rules, not a continuation of the one that just died.**"
- **p.16 — absorption is a resiliency process, not a switch.** "Absorption is not a yes or no
  switch, it's a process with **resiliency that changes second to second**," with the academic
  framing being limit-order-book resiliency (how fast a level's depth refills after being hit)
  as "a real, measurable, and **variable** property of the market, not a constant." "The
  checklist... just tells you **where in the process you actually are**." The crosswalk's
  absorption family is composed of marginals and ratios, not a stage/position read.

### average-unprofitable-trader.pdf (33 pp)

The crosswalk dismisses this document under "Emotion, discipline, prop-account anecdotes...
No market predictor is manufactured from narrative." It is not a narrative document; it is the
library's program-design document, and it contains the abstention and evaluation machinery.

- **p.9 — the discretionary box is the abstention primitive, and it includes regimes.**
  "Inside it is everything your discretionary framework permits: absorption, exhaustion,
  trapped buyers and sellers. Outside it sits everything else the market offers: trend lines,
  support and resistance, **the regimes that don't suit you**. Inside the box you can act.
  **Outside it, you don't trade, full stop.** That boundary is your discretionary barrier, and
  **defining it is the first act of data collection, because you can only measure a strategy
  that has edges.**"
- **p.13 — the confluence fallacy, with the arithmetic, and it cuts against raising the bar.**
  20 trades on three-confluence setups at a 70% win rate, 1:5 RR. Demand a fourth confluence
  and "plausibly the win rate drops to 65%, maybe 60%. How, if the setup got stricter?
  **Because the fourth confluence costs you: time hunting for it, fewer trades taken, good
  setups going untraded. The stricter filter can genuinely produce a worse account.** Or a
  better one. **You cannot know which until you've collected the 20 trades.**" And an
  account-specific rider: "his account can't afford lower frequency, so for him specifically,
  stacking probably makes things worse." Also: "The fallacy was never in adding confluences.
  It's in adding them **unmeasured**."
- **p.15 — the barrier product, and its consequence for sizing.** "A prop firm is a synthetic
  product... you're trading a **barrier-based product**." A loss limit below, a payout
  threshold above, and **the barriers move** (an end-of-day trailing drawdown rises with profit
  and buffer). "**Risking a static dollar amount inside a product with moving walls is a
  category error. You manage risk to the barriers, because the barriers are the product.**"
  And: "**You don't need to have a positive expected-value strategy. You only need variance.
  Your variance has to be profitable.**" Five accounts, three hit the payout barrier for $2K
  each, two die for $150 each, net positive even if the strategy is marginal. Real maximum loss
  is the fee.
- **p.11 — size flexes with grade, targets do not flex at all.** "Best setups deserve more
  money, worst deserve less: **size flexes with setup quality, while targets don't flex at all,
  staying where the auction logically pays.**" Static dollars per trade gets the strikethrough.
  And the sizing standard: "**risk sized for your worst documented behavior**" — "it takes me
  two to three losses before I notice I've tipped into over-trading; my risk management allows
  me to survive those two to three losses." Plus: "**Emotions cannot be quantified, so they
  cannot be a sizing input, ever.**"
- **p.19 — features are regime-specific and must be tagged.** "Write the regime down every
  time, fade or continuation, **because features are regime-specific: absorption suits fading a
  trend; trapped sellers pile up at the bottom of continuation trends.**" A named
  feature→regime mapping the crosswalk does not carry. Also: 10–20 trades per feature, let the
  sample declare the winner, drop the loser; A/B one variable at a time over 20–30 trades; "if
  the rule made no difference, it's noise, drop it."
- **p.21 — the worked sequence with load-bearing caveats, one of which is a veto.** Value
  opening and building higher → sellers exhausting → rejection off POC or prior VAH → break of
  the current VAH **with aggressive buying imbalances doing the breaking** → price returns to
  those imbalances → **if the buyers who broke the level defend them, that retest is the long;
  if they fold, you have your answer, and it cost nothing.** Caveats: still subject to **time
  of day**, still subject to what the DOM shows at the retest, and "**it still needs a decent
  higher-timeframe objective, somewhere for the auction to actually go. A clean break-and-retest
  into nothing is a clean entry into a losing trade.**" The crosswalk lists `disc_target_` as
  "target viability, risk context," not as a precondition that vetoes the entry.
- **p.23 — the journaling protocol is a lookahead-bias control.** Record the screen for the
  whole session, then scrub back to the moment **just before** each entry, pause there, and
  write what you were thinking at that exact moment. "**The reason you pause before the entry is
  lookahead bias. Journal after the trade and the known result poisons the record.**" "A lot of
  people think if you win, it's a good trade, when most of the time it's probably a bad trade.
  Or if you lose, it's a bad trade, but it might be a good trade. It's just variance at that
  point." Money result goes in last.
- **p.24 — the absorption filter in its second formulation.** "**Absorption fails 27% of the
  time unless there's a 3-tick aggression toward the absorbed side.**" Note this differs from
  `stop-re-entering` p.10's "three ticks of **replenishment**." Both are in the library, framed
  as the same 27% number attached to two different measurements.
- **p.25 — location sets a side-asymmetric evidence bar before any flow is read.** "At the
  lower boundary of the volume profile, price is at a discount and buyers should step in;
  **price seeks the POC and value 60 to 80% of the time.** So you **give buyers leniency on the
  DOM and hold sellers to a higher standard**: deciding who gets the benefit of the doubt
  before the tape starts arguing."
- **p.26 — the DOM is three reads in a fixed order, and imbalance is subordinate to pacing.**
  Location → Pacing → Digits, "always in that order, always after the thesis." Pacing: "a huge
  divergence of buyers over sellers while price stagnates, rotating in the same few ticks, is
  massive effort with no reward, and effort that isn't being paid is a warning, **whatever the
  imbalance says**." Digits: sellers refreshing from two/three-digit sizes down to singles are
  thinning; buyers stepping from two/three digits to four and five are building; "when the
  pacing then upticks, effort finally getting its reward, **that's the entry**."
- **p.17 — the audit questions are deliberately ordered with entries last.** "Entries are where
  beginners start, and they're **the least of it**. Optimising an entry inside a strategy with
  no data, emotional sizing and an unread product is polishing the door handles on a house with
  no foundations."
- p.16 — Topstep's own 2025 disclosure: 51.8% of Combine entrants reached Funded at least once,
  yet **only 33.3% of funded participants ever received a payout**. "The bottleneck is what
  happens after the pass."
- p.29 — the numbers card: 2–3 losses the sizing must survive; 3 ticks aggression or absorption
  fails 27%; 10–20 trades per feature before judging an A/B; 60–80% price returns to value;
  $150 → $2K as the product.

### ny-am-session (1).pdf (12 pp)

- **p.6/p.7 — a stated counter-example to test-count monotonicity.** A level had rejected
  sellers twice with no buyers stepping in either time; on the third retest still nothing, so the
  short went in, and it was stopped. "**Low risk doesn't mean no risk, and a level failing to
  hold twice doesn't guarantee it fails a third time.**" The crosswalk's `disc_test_` family
  encodes repeated tests and response decay without carrying this caveat.
- **p.10 — the fade trigger is decaying approach aggression, not arrival at the level.** The
  resistance was marked in advance and "the move up **is losing aggression candle by candle,
  not gaining it**, which is the tell I was waiting on, **not just fading a level because it's a
  level**."
- **p.11 — risk shrinks late in the session once the objective is close.** "Risk was kept to
  about $100, deliberately small this late in the day with the objective already close."
- **p.3 — the read stack is ordered and terminates in a defence-trend read.** Location (where
  price sits in the HTF auction) → Absorption (who is defending it) → **Refresh and pacing
  (whether that defence is thickening or thinning)**. "None of it is prediction."
- pp.8–9 — trailing convexity turning R:R 0.69 into 1.83 on the same entry; "most traders would
  skip that outright."

### 18k-payout-session.pdf (15 pp)

- **p.11 — refresh *consistency* is the wall-versus-coincidence discriminator, and it is a
  sequence shape.** "A level backed by real size refreshes at a roughly **steady pace and a
  roughly steady size**: hit, replaced, hit, replaced, **without the replacement visibly
  shrinking**... a genuine defender does not run out of appetite three prints in. A level that is
  really just one order rotating through a queue thins out fast: **each refresh a little smaller
  than the last, the pacing between them stretching out**, until it stops coming back at all.
  **That thinning is what precedes the level finally giving way.**" And: "**a single absorption
  print is never enough to act on by itself.** Absorption only says an aggressive order got
  stopped passively once. **Consistency across several refreshes is what tells you whether that
  was a wall or a coincidence.**" The crosswalk has refill size, count and trade-to-reload
  latency as marginals; the discriminator here is monotone shrinkage plus inter-refresh interval
  stretching, jointly.
- **p.7 — the three-attempt cadence at one level, and increasing conviction as the requirement.**
  "**The first two attempts at this exact level did not have that participation and were let go.**
  The third attempt did... **Sellers refreshed at the level rather than thinning out**, which is
  the tell that separates a level worth defending from one that is about to give way." Stated as
  a principle: "**A level does not become the trade because price touched it. It becomes the
  trade when the same side defends it a second time, with more conviction than the first.**"
- **p.5 — the pre-file entry is a distinct trade class with a different objective.**
  Deliberately entered **before there was anything to confirm it**, sized small on purpose:
  "the point of a pre-file entry is not to be right, it is to **buy a small amount of buffer on
  the session cheaply**, in case the real setup a few minutes later needed the room." Graded a
  B+ at best afterwards, taken anyway "because the cost of being wrong on a pre-file entry is
  small and known in advance." Checklist form (p.14): "sized small on purpose, as buffer,
  **never as a conviction trade**." Nothing in the crosswalk's policy layer distinguishes trade
  classes by objective.
- **p.6 — two consecutive losses at a level are the cost of testing it, not evidence against the
  thesis.** "That is not hesitation and it is not stubbornness. **It is what testing a level
  properly looks like when the level does not cooperate: you pay the small, known price twice,
  and you do not change the thesis because of it.**"
- **p.12 — two mechanisms with the same tape signature, and only one is informative.** Dealer
  hedging (a short-gamma dealer buys into strength and sells into weakness **mechanically,
  regardless of view**, which "is the actual reason a short gamma regime produces faster, wider
  moves") versus ordinary short covering (a participant who lost the argument closing out; shows
  up as **passive buying at a level already tested and failed to break**, and is the mechanism
  behind a protected high). "**Both show up as buying pressure. Only one of them tells you
  anything about who is actually winning the fight for the price.**"
- **p.8 — protected high, defined operationally.** The stop moves to the next protected high
  **only after price closes below the prior one with real aggression** (real speed of tape behind
  it), not by a fixed distance. "Giving it back would mean the read was wrong in the first place."
- **p.10/p.14 — sequential sizing conditioned on realised state.** "**A later trade is only sized
  up once an earlier one is no longer at risk.**" The fourth trade "was affordable specifically
  because the third one was no longer at risk." The crosswalk's policy layer has K=1 per asset and
  ≤12/day but no such conditional.
- **p.4/p.14 — the gamma regime is coarse and explicitly non-decisive near its boundary.** "The
  gamma regime is **named, even when it sits near the flip and the answer is genuinely close**."
  Price was sitting almost exactly on the flip, either read defensible, "and **the trade plan did
  not change because of it**."
- p.4 — the objective was set by composite asymmetry: "a lot of built-up value above and
  comparatively little below, which is the kind of asymmetry that makes one direction the path of
  least resistance rather than a guess."

### 10k-first-month (1).pdf (16 pp)

- **p.6 — the empty-session failure mode, and the remedy is more level sources, not a lower bar.**
  Marking levels only from self-drawn HTF high-volume nodes "works, until price sits nowhere near
  one of them. On a day like that he used to have nothing to trade off, or worse, **he'd trade the
  middle of the range anyway**." The fix was a second, statistically backed level source: "more
  levels with real data behind them meant more high conviction setups instead of **forcing a trade
  because a session felt empty**."
- **p.9 — naive break-even is EV-destructive.** "**If you go normally to breakeven, after a hundred
  trades, if you actually look at the stats it ruins your EV in a problem environment.** But the
  way you cater it, it's a much better way to go breakeven." Trailing convexity is the alternative.
  The crosswalk's policy layer records nothing about break-even mechanics.
- **p.13 — a whole trade class refused on higher-timeframe grounds.** Repeated short entries fought
  against a level that kept holding, "**same setup, three attempts, the higher timeframe never
  agreed with any of them**." Now: seeing a key demand level tested and sellers absorbed there
  tells him the HTF bias, and such a short "**doesn't get taken at all, regardless of how clean the
  local order flow looks**." Also a maturity state-flip: that resistance had sat untouched for two
  weeks, and "once it finally broke, **everything below it stopped being a place to sell from**."
- **p.12 — the thesis order includes a look-left maturity check.** Current auction state → **has
  price reacted at this level before** (which "tells him whether the area is a real key level or a
  fresh one nobody's tested yet") → objective. And the actual test of a thesis is "**stating the
  expectation first rather than narrating it afterward**," including expecting a retrace or two
  before the target.
- p.14 — the four-question loop in fixed order: what the market is doing right now / what the
  market wants to do / where his levels actually are / where he should trade off them.
- p.4 — win rate 30–40% before the change, with a self-described (and explicitly unmeasured)
  50–60% if traded with discipline; the gap attributed to impatience, not strategy.

### 2345-funded-session (1).pdf (11 pp)

- **p.6 — "extreme absorption," a session-length CVD-versus-price-hold read that has no analogue
  in the crosswalk.** Price grinding **up** against resistance while **CVD died across the entire
  consolidation session** means "the passive limits at that level were being **consumed and
  reloaded, not defended for free**." "**Price refusing to drop while the delta record shows no
  real selling pressure behind the level is what extreme absorption actually looks like, and it's
  the difference between 'this level worked before' and 'this level is currently being tested and
  passed.'**" Nothing in the crosswalk operates at a level on that horizon; the adaptive clocks
  top out well below a consolidation session.
- **p.4 — the no-structure-overhead protocol.** "In a genuine all time high environment the correct
  approach is to **wait for the pullback and trade within the directional push, not to predict a
  target in advance**." The objective was set **deliberately neutral**. "Marrying a bias before the
  auction has given you structure is exactly the psychological trap this thesis process is built to
  avoid."
- **p.5 — the 350% divergence box is an attention flag, not a signal.** "It is **not a signal on
  its own, it is a flag** that something worth looking at just happened." What made it tradeable
  was the HTF context: a level where sellers had previously been trapped on the way up, visible in
  the delta profile as **buying aggression getting covered rather than reversed**. The crosswalk
  implements 350% diagonal counts as standalone features.
- **p.9 — the target was capped by an account consistency rule.** A prop payout requirement that no
  single day may represent too large a share of total profit, "which means **sizing the plan to the
  account's rules, not just to the chart**." Then "done for the day, not because the setups
  stopped, because **the plan for the session was already complete**."
- p.8 — the session objective was defined as recovering the prior day's loss **plus** the $500 left
  on the table by choosing not to trade the PM session: an explicit carry-forward objective.
- p.3 — the payout-eligibility state itself constrains the session (14-day wait, buffer short of the
  requirement, a losing day immediately adjacent).

### code-1-thesis.pdf (8 pp)

- **p.4 — a closed enumeration of what kills a bias, with an explicit noise default.** "**Three
  things end a bias, and only three. Anything else is noise you are supposed to sit through.**"
  (1) **Structure breaks**: a clear break of a premarket level or a volume-driven structure shift.
  (2) **Value shift**: value builds somewhere new. (3) **New information**: major news. The
  crosswalk carries "persistent invalidation" as a state flag with no typed cause set and no
  sit-through default.
- **p.3 — "A bias without an invalidation is an opinion. The invalidation is what makes it a
  thesis."** The loop: form the thesis, define where it dies, trade it while it lives, and **the
  moment the market kills it, recreate it**.
- p.4 — asymmetric directional triggers: "Bullish after a higher timeframe support **holds**.
  Bearish after value **breaks down**."
- **pp.5/7 — the triad reads (ES/NQ/YM), and they are a different hypothesis from the one the
  crosswalk measured null.** **IØD**: your thesis stalls because a correlated asset **used an AMT
  object first**. "YM takes the previous balance. That makes ES the weaker asset in the reaction,
  so if YM reverses and rejects off that previous VAH or balance, **ES falls faster and further.
  The weak one pays.**" **RFZ (reactive fill zone)**: a correlated asset **takes your objective, a
  single print, before your market does** — "**your target got consumed by proxy, read the
  reaction, not the old plan**." Plus leads/lags ("watch which one takes the AMT object first, that
  is your tell"), **correlated divergence** ("one index makes a fresh high or low and another
  refuses to follow... that non-confirmation is a fade signal, the index that overextended snaps
  back to the pack"), strong vs weak ("on the reversal the weak one falls faster and further, and
  that is the cleaner trade"), and the usage rule: "**Aligned triad, press the thesis. Divergent
  triad, tighten up or wait, the disagreement almost always resolves against the laggard.**"
  The crosswalk lists cross-asset as not integrated, citing a measured null on a **closed-cell /
  S11 / P031** family. That null was on a cell-grain correlation family; the source's hypothesis is
  **object-mediated and event-ordered** ("who consumed which shared AMT object first," and the
  target-consumed-by-proxy case). The crosswalk does not say that its null fails to cover this.
- **p.6 — the codex makes the *bias*, not the trade, the unit of record.** Per session: label
  (long/short/neutral), start and end timestamps, **the validity band — "the exact price range where
  the bias is considered alive"**, a one-line reason, **a 1-to-5 confidence score at session start**,
  every trade taken under the bias, EV in R / profit factor / max drawdown **during the bias**,
  whether the bias was changed and why, a regime tag, and execution breaches. "After 30 sessions...
  the codex answers it in numbers: which regimes you read well, which reasons hold up, and **which
  confidence scores were lies**." A per-bias evaluation unit with a stated-confidence calibration
  check has no analogue in the program.

### code-2-risk.pdf (8 pp)

- **p.4 — MFE/MAE is the stated method for setting stops and targets.** "**Collect 40 to 80 trades,
  then read the MFE and MAE distributions. Your optimal stop sits beyond where winners typically get
  their heat, your target sits where winners typically peak.** Placement becomes engineering, not
  vibes." Note that `origin-of-the-move`'s 18-tick figure is exactly an MAE statistic on winners.
  The program forbids new exit laws; the crosswalk should at minimum record that the library's exit
  geometry is derived this way rather than asserted.
- **p.7 — expectancy has a stated minimum sample.** Expectancy = (win% × avg win) − (loss% × avg
  loss), in R. "**Expectancy only means something over 100+ trades. Any smaller and you are reading
  variance, not edge.**" And "a 40% win rate at 1 to 3 is a monster."
- **p.5 — three exposure plays with exact mechanics.** Break-even then move in profit, with the
  qualifier "**only move it where the market could logically return to**, identify those spots and
  step the stop behind them"; a trailing stop roughly 3 points behind after a 6–10 point run;
  partial exits, 50% off at 1:1 with the stop to break-even on the rest ("the play that makes
  runners psychologically possible").
- p.6 — Monte Carlo for the drawdown/return distribution under randomness, and the Kelly criterion
  with fractional Kelly as the practical version.
- Largest overlap with existing program policy of any document here; the delta is the derivation
  method (MFE/MAE, Monte Carlo, Kelly, 100-trade minimum), not the laws.

### emotion.pdf (9 pp)

The crosswalk's treatment ("converted only to preregistration, stopping, and audit discipline") is
directionally right, but four operational rules survive conversion and are not recorded.

- **p.6 — the losing-streak decision procedure is one question, and a streak is not itself a stop
  condition.** "**Were you following the plan? If yes, keep taking valid trades, variance is doing
  its thing. If no, step back and review before the account pays for the lesson.**"
- **p.7 — the A+ setup is written down as one sentence, and match is binary.** "Write your A+ setup
  down. One sentence. **If the trade in front of you does not match it, it is not a trade.**"
- **p.7 — deviations are logged as their own ledger.** "Trade the plan, **journal the deviation**.
  Every time you break a rule, log it. **The pattern in your breaks is the exact thing costing you
  money.**" Also: "Set a hard loss limit for the day: a number of R, or a dollar figure. Hit it and
  you are done, no negotiation," and "close the laptop after the session."
- **p.6 — "Overmanaging trades kills the probabilities the system was built on."** And "simplify
  every decision you can, fewer choices means fewer emotional errors."
- **p.4 — a demotion path.** "Sim and review when struggling. Switch to simulation, drill the
  setups, review the recordings and find the exact error. **Struggling live with real money teaches
  nothing except fear.**"
- p.5 — "Trading is not gambling when there is a tested system, defined risk and strict rules.
  **Remove any one of the three and it is.**"

---

## Part 2 — Consolidated delta

### 2.1 Nuances the ledger form flattened

**Ordering lost.** Every process document in this set states its reads as a strict
precedence, and the crosswalk converts each of them into a set of atomic features
whose interaction CatBoost is asked to learn. The instances:

| Source | Stated as | Crosswalk form |
|---|---|---|
| `stop-re-entering` p.6 | location **carries** reward and delta; "without step one they filter noise" | three co-equal families |
| `average-unprofitable` p.26 | Location → Pacing → Digits, "always in that order, always after the thesis"; imbalance subordinate to pacing "whatever the imbalance says" | separate `disc_level_`, `disc_footprint_`, `disc_evt_` |
| `only-trade-big-trades` p.13 | opposition fails **first**, then your side arrives; "half is what most people trade" | ordered state family without this two-party requirement |
| `anatomy` pp.8–10 | stop from structure → size from stop → target from HTF; "at no point is the ratio chosen first" | policy layer, ordering unrecorded |
| `stop-re-entering` p.10 | four absorption stages that "only exist in time"; stage 1 and stage 4 look identical in a snapshot | continuous absorption components at a snapshot |
| `mastering-amt-vp` p.13 | "the auction context **outranks** the trigger" | context flags that "do not force entries" |

The crosswalk's own design note — "Entry V2 therefore exposes atomic state and path
components. CatBoost is asked to learn their context-dependent interactions" — is the
mechanism by which the ordering was lost, and `origin-of-the-move` p.15 is a measured
argument that this is the wrong split (flow alone AUC 0.54; memory and location carry it).

**Context-conditionality lost.** The single largest omission. `only-trade-big-trades`
pp.14–15 states that the *same evidence at the same location* is a different trade in the
two gamma regimes, and specifically that in the balanced/long-gamma case (stated as ~80%
of sessions) **you do not require your own side to be rewarded**, because passive
absorption is the carrying mechanism rather than a warning. The crosswalk's
`disc_regime_` / `disc_path_balance_` / `disc_path_expansion_` families note that
"identical flow with opposite meaning by regime" exists, and then implement both as
non-forcing context flags. The specific inversion — reward requirement present in one
regime and absent in the other — is not represented.

Second-order instances: `tpo-lesson-3` p.7 (poor extremes reliable on NQ, "less reliable
on ES and rarely used"); `mastering-amt-vp` p.19 (ES gap statistics do not transfer to NQ,
where the gap fade failed at every entry time tested); `only-trade-big-trades` p.3 and
`origin-of-the-move` p.4 (the aggression size band is instrument- and session-specific and
"you have to find your own band rather than borrow this one"); `vix-lesson-4` p.8
(backwardation makes levels meaningless until the curve normalises).

**Stated ratios and measurements genericised.** The crosswalk's "No author threshold is
treated as truth" applies correctly to thresholds. It also removed a set of *results*,
which are a different kind of object: 42% of touches hold unfiltered; −0.285R unfiltered
vs +0.143R graded; 25%→63% monotonic hold rate by decile; AUC 0.54 flow-only vs 0.63
graded vs 0.51 placebo; the 18-tick median winner dip; PF 1.80 resting vs 0.81 chasing;
−4R adding ~14 points of pass rate; the causally-rebuilt entry at −0.16R to −0.54R; 27%
absorption failure without pacing confirmation; 3-tick replenishment minimum; 2–4 upticks
as the reward quantum; 6–8 ticks as "far too delayed"; 94% ONH-or-ONL touch; 73%
open-inside-value → MPOC; 60–80% return to value; the full 1,040-day ES base-rate tables.
None of these appear anywhere in the crosswalk, including in its fidelity-limits section.

**Objects flattened into families.** Ledges (fixed) versus VAH/VAL/POC (drifting) —
`vp-lesson-2` p.5; single prints, excess and poor extremes as three different extreme
classes with three different expectations — `tpo-lesson-3` pp.5–7, p.9; naked POCs and
composite HVNs as separate object classes with a timescale-matching rule — `vp-lesson-2`
p.6; the prior-balance POC as the specific object the Failed Auction setup requires —
`mastering-amt-vp` p.9; overnight LVN and shelf as a two-level respected/disrespected gate
— `mastering-amt-vp` p.14; the squeeze catalyst anchored at the **first** aggression, not
the extreme — `origin-of-the-move` p.2; anchored (event) VWAP — `vwap-lesson-10` p.7.

### 2.2 Decisive for the live sweep-4 questions

#### (a) Rejection versus rest at a quieted extreme — FLAG

The library answers this directly and the crosswalk carries none of it. Five sources
converge, and they do not agree unconditionally — the disagreement is itself the finding:

1. **`only-trade-big-trades` pp.14–15 supplies the conditioning variable.** In a
   balanced / long-gamma regime — stated twice as ~80% of sessions — **both extremes get
   absorbed most of the time**, the correct trade is a *failure-of-aggression* fade, and
   **you explicitly do not need your own side to be rewarded**: "passive absorption is
   exactly what carries price in a balanced market." In a short-gamma / expansion regime
   the same quiet is the p.13 passive-move trap ("no effort on your side at all, just an
   absence of sellers... normally short term swings rather than the start of anything").
   Quiet at an extreme is therefore not a single state; it is rest in one regime and
   rejection in the other, and the regime is checked **before** looking at the extreme.
2. **`origin-of-the-move` p.14 says the quiet case is the more common signal, not the
   absence of one.** "The squeeze fails with **no aggressive orders at the failure at
   all: the speed of tape just dies. The absence of result is itself the signal, and it
   is the quieter, more common version of this model.**"
3. **`2345-funded-session` p.6 supplies the discriminator that separates the two on the
   tape.** A level holding while **CVD dies over the whole consolidation** means the
   passive side is being **consumed and reloaded, not defended for free** — the level is
   "currently being tested and passed," not resting. The inverse (price holding while CVD
   is flat and no aggression arrives) is rest. This is a level-anchored, session-horizon
   effort-versus-hold read; the crosswalk's longest clock is far shorter.
4. **`18k-payout-session` p.11 supplies the sequence-shape test.** Rest = refreshes at
   steady size and steady pacing. Imminent failure = each refresh smaller than the last
   **and** the interval between them stretching. "A single absorption print is never
   enough to act on by itself."
5. **`tpo-lesson-3` p.9 and `vwap-lesson-10` p.6 supply two prior-side reads.** An
   **excess** extreme (repeated same-period prints at the tail) is a finished argument —
   "expect those extremes to hold on first test." A **poor** extreme is unfinished and
   expected to be revisited. And a stall with CVD still running one way is the standoff
   case that "usually resolves violently."

Additional constraint on the arbiter: `origin-of-the-move` p.11 states that inside a
balance the side comes from **who was already in control**, and the squeeze in that
direction failing is the setup — not from flow measured at the extreme.
`only-trade-big-trades` p.4 states the abstention case explicitly: when **both** sides are
being absorbed, "nobody is in control yet," and the instruction is to wait for the break
rather than pick a side inside the range.

#### (b) Which sessions and cells a discretionary trader refuses to trade — FLAG

The library contains an explicit, layered refusal system. None of it is in the crosswalk.

*Session-level stand-asides:*
- `vix-lesson-4` p.5 — **VIX below 13 (expected ES range under 30 points): "usually not
  worth fishing. Knowing there is no edge today IS the edge."** Below 14: scalps only "or
  stay out entirely."
- `vix-lesson-4` p.8 — **backwardation: "the auction is broken until the curve
  normalises," levels "mean nothing until it resolves."** Cut size hard.
- `vix-lesson-4` p.5 — **range completion**: once the implied range is mostly consumed,
  "the fuel is spent," expect mean reversion and chop.
- `vix-lesson-4` p.6 — **ES flat / VIX flat: "expect chop... scalp the rotations or stand
  down."**
- `vix-lesson-4` p.7 — pre-event: **ignore the implied range**; post-crush: return to
  fading rotations only. The two traps are both "trading yesterday's regime."
- `amt-lesson-1` p.10 — **non-trend day: "Nobody shows up. Narrow, quiet, usually in front
  of news. The edge is knowing there is no edge, stand down or scalp tiny."** Also: fading
  a trend day is a named blown-account error; "the fade layer is only allowed on balance
  days."
- `2345-funded-session` p.4 — in a genuine all-time-high environment with no structure
  overhead, **do not predict a target**; keep the objective neutral and wait for the
  pullback.

*Location-level and cell-level refusals:*
- `vp-lesson-2` p.7 — **the interior of a shelf is not tradeable**: "inside the shelf is
  rotation, chop and noise." Trade the ledge.
- `stop-re-entering` p.6 — **the middle of a balance is where the spiral starts**, "where
  neither side has an argument, and every wick looks like absorption because nothing has
  context."
- `10k-first-month` p.6 — the empty-session failure mode is **trading the middle of the
  range because nothing is near a level**; the remedy is more level sources, not a lower
  bar.
- `mastering-amt-vp` p.15 — **94% ONH-or-ONL touch used as a reason not to take a trade**:
  a level a few points above the overnight low with a tight stop is a right level at a
  wrong time.
- `average-unprofitable` p.21 — **"a clean break-and-retest into nothing is a clean entry
  into a losing trade"**: an objective must exist before the entry is legal.
- `anatomy` p.10 — **"Ratio checked, not chosen. The objective is where it is. If the
  ratio is poor, skip it."**
- `origin-of-the-move` p.16 — **"the first touch of a fresh zone is the weakest version of
  this trade"**; wait for the second test or for memory, construction and location to
  agree.
- `10k-first-month` p.13 — an entire trade class refused on HTF grounds, "regardless of
  how clean the local order flow looks."
- `average-unprofitable` p.9 — **the discretionary box**: the boundary is defined in
  advance, includes "the regimes that don't suit you," and outside it "you don't trade,
  full stop."

*Two constraints that cut against raising the bar, and that the abstention work should
carry explicitly:*
- **`average-unprofitable` p.13 — the confluence fallacy.** A stricter filter costs
  frequency and can genuinely produce a worse account; whether it does is an empirical
  question answerable only by collecting the trades. For an account that cannot afford
  lower frequency, stacking probably makes things worse.
- **`only-trade-big-trades` p.17 — the prop maths.** A barrier problem "rewards a higher
  win rate and steady participation," not a large return from a small number of trades.
  Ten rare setups all losing leaves you level only on the eleventh: "survivable with a long
  runway... not on an evaluation with a trailing drawdown." Hence "**trade a framework,
  not a strategy**," because a single pattern fits one regime "so it leaves you either
  forcing trades or sitting out most of the month."
- `stop-re-entering` p.14 makes abstention **binary**: "no trade yet, **not a smaller
  trade**." `average-unprofitable` p.11 makes it **graded** (size flexes with setup
  quality). The library holds both positions; the crosswalk holds neither.

#### (c) Re-entry discipline after a stop — FLAG

The crosswalk's policy row reads "unlimited sequential re-entry subject to occupancy and
risk laws." Every source in this set constrains re-entry by **location and offer**, not by
count, and two of them bound it by a daily loss gate.

- **`anatomy-of-a-losing-start` p.7 — the narrowest statement.** "Getting stopped is not a
  reason to get back in. **It is not a reason to stay out either.**" The rule: "*Let us
  see if we come back down. That is the only time I look for a re-entry.*" — "**Price has
  to come back to the level. Not near it, and not on a different level that looks similar.
  If it does not return, there is no trade, and the loss just stands.**" Observed effect:
  "this is also why the two stops in a row did not turn into four."
- **`origin-of-the-move` p.12 — re-entry is licensed by an unchanged read at a specified
  relocation.** "If it stops out, fine: **the re-entry sits right below, and the read has
  not changed.**"
- **`18k-payout-session` pp.6–7 — the cadence in practice is up to three attempts at one
  level, with the first two deliberately small and let go.** "The first two attempts at
  this exact level did not have that participation and were let go." Two losses at a level
  are "what testing a level properly looks like when the level does not cooperate: you pay
  the small, known price twice, **and you do not change the thesis because of it**." The
  third attempt required **increasing** conviction: "the same side defends it a second
  time, **with more conviction than the first**."
- **`ny-am-session` pp.6–7 — the counterweight.** "A level failing to hold twice doesn't
  guarantee it fails a third time." Test count alone is not the licence.
- **`stop-re-entering` p.14 — the re-entry passes the checklist from zero.** "**Not on the
  strength of how close it already got.**" And the gate: "Daily stop. I am above minus four
  R for the day. **If I am not, there is no trade, re-entry or otherwise.**"
- **`stop-re-entering` p.15 / `origin-of-the-move` p.16 — the daily stop is the largest
  measured lever in the library** (~14 points of pass rate) and it is described as deleting
  the worst version of the day rather than capping it: "a trader honoring the daily stop
  never sees re-entry five."
- **`anatomy` p.11 — the asymmetric day.** Daily objective ~$500 and then stop, "including
  on days when the read is still good"; **maximum loss at half the objective**. The bad day
  is capped smaller than the good day. The crosswalk's policy row records neither the
  stop-on-target nor the asymmetry.
- **`18k-payout-session` p.10 — sequential sizing is conditioned on the prior trade's
  realised state**: "a later trade is only sized up once an earlier one is no longer at
  risk."
- **`emotion` p.6 — a streak is not a stop condition; plan-adherence is.** "Were you
  following the plan? If yes, keep taking valid trades, variance is doing its thing."
- **`stop-re-entering` p.5 — the mechanism names.** Break-even effect (worse odds accepted
  right after a loss) and realization effect (a *locked* loss produces caution, an *open*
  one produces risk-taking). "A stop-out locks the loss. Treat the next trade as a brand new
  decision under fresh rules."
- **`18k-payout-session` p.5 — a class of intentional, pre-confirmation, small-cost entry**
  ("pre-file") whose objective is session buffer rather than P&L, graded B+ and taken
  anyway. This is a re-entry-adjacent cadence primitive with no representation in the
  crosswalk.

### 2.3 Author-stated mistakes and anti-patterns the prior implementation did not encode

1. **`origin-of-the-move` p.18 — hindsight leakage in setup selection.** The earlier,
   profitable-looking version "had quietly used information from later in the day to pick
   which setup was 'the one.'" Removing the peek made the mechanical edge disappear
   (−0.16R to −0.54R). This is the exact failure mode the program's own future-truncation
   invariant guards against, and the crosswalk does not cite it as prior art.
2. **`origin-of-the-move` p.15 — building on raw flow alone.** AUC 0.54; memory and
   location do the work.
3. **`origin-of-the-move` p.15 — trading every touch without grading.** −0.285R after
   costs; only 42% of touches hold.
4. **`origin-of-the-move` p.15 / `stop-re-entering` p.7 — acting at the front edge of the
   level.** The median winner dips 18 ticks past the touch first; acting at the tag is
   acting "at the exact point where the data says the trade has not started yet."
5. **`origin-of-the-move` p.15 — paying the spread to chase.** Same signals: PF 0.81
   chasing vs 1.80 resting.
6. **`only-trade-big-trades` p.7 — entering on the failure of the squeeze.** "You have
   identified where something ended, and treated it as a beginning." The failed squeeze is
   context, not a trigger.
7. **`only-trade-big-trades` p.9 / p.12 — prefiring.** Firing on the expectation of
   confirmation; argued on win rate, "and on a prop account variance is the thing that
   removes you, not being wrong about direction."
8. **`only-trade-big-trades` p.13 — trading half the sequence.** Opposition failing on its
   own is only half; your side must then arrive aggressively.
9. **`only-trade-big-trades` p.4 — reading an aggression tool as a direction.** "A bubble
   is a record that size traded aggressively at that price. It is not a direction." And
   acting when both sides show effort, where nobody is in control yet.
10. **`amt-lesson-1` p.13 — five named AMT mistakes**: trading AMT without a tape trigger;
    fading a trend day; treating the 80% rule as a promise; marking every level ("if
    everything is a level, nothing is"); **reading a finished profile on a live day** (the
    profile read is non-stationary within the session — "a D shape at 11am can be a trend
    day by 2pm").
11. **`mastering-amt-vp` p.4 — trading VAH/VAL as fixed levels.** "You are not trading a
    level, you are trading an indicator that recalculates against your own position."
    `vp-lesson-2` p.5 is the constructive form: use ledges, which do not move.
12. **`mastering-amt-vp` p.6 / p.9 — treating any breakout, or any return to a zone, as the
    failed-auction setup.** "Confusing the two is the most common mistake beginners make
    with this concept."
13. **`vix-lesson-4` p.7 — trading yesterday's regime**, in both directions (fading a
    pre-event tape; chasing after the vol crush).
14. **`average-unprofitable` p.13 — adding confluences unmeasured.** The fallacy is not the
    confluence, it is adding it without a sample.
15. **`average-unprofitable` p.15 / p.11 — static risk inside a moving-barrier product**
    ("a category error"), and sizing by feel; also sizing **up** when suspecting revenge
    trading, i.e. "maximum size at the moment of minimum judgment."
16. **`average-unprofitable` p.23 — outcome-graded journaling.** Grading a trade by whether
    it won poisons the record with variance; the fix is to pause the recording *before* the
    entry.
17. **`10k-first-month` p.9 — naive break-even stop movement**, which "ruins your EV in a
    problem environment" over a hundred trades.
18. **`emotion` p.6 — overmanaging**, which "kills the probabilities the system was built
    on"; and `emotion` p.5, system hopping (`average-unprofitable` p.7: "the only reason you
    would strategy hop is because you don't have sufficient data to even show that your
    strategy is profitable").
19. **`18k-payout-session` p.12 — confusing dealer hedging with short covering.** Same tape
    signature, and only one says anything about who is winning the price.
20. **`only-trade-big-trades` p.17 — chasing high R:R skew inside a barrier product**, which
    "quietly works against the payout."

---

## Part 3 — Ranked shortlist: the ten most consequential missed details

1. **The author's mechanical entry, rebuilt causally, was negative.**
   `origin-of-the-move (1).pdf`, p.18. −0.16R to −0.54R out-of-sample once hindsight was
   stripped; the profitable-looking version had used later-in-day information to select the
   setup. "What survives is a grading system for touches you have already found, and an
   execution rule about which side of the book to stand on." The library's own verdict is
   that the entry-law object does not survive causal reconstruction and the grading object
   does. The crosswalk records neither the result nor the distinction.

2. **Raw order flow alone scores AUC 0.54; memory and location carry the signal.**
   `origin-of-the-move (1).pdf`, p.15. "Aggression builds the level. It is the level's
   history that predicts the next touch." This is a direct, measured indictment of the
   atomic-flow feature strategy the v8 representation implements, published by the same
   author whose concepts the crosswalk is a distillation of.

3. **The gamma/balance regime inverts the trade, and in the ~80% case you do not need your
   own side rewarded.** `only-trade-big-trades (1).pdf`, pp.14–15. Short gamma: OFM drive.
   Long gamma / balance: failure-of-aggression fade, where "passive absorption is exactly
   what carries price" and both extremes get absorbed most of the time. The regime is
   checked "before you look at the chart at all." This is the conditioning variable the
   rejection-versus-rest question needs, and the crosswalk represents it as a non-forcing
   context flag.

4. **The quiet failure is the more common form of the signal, not the absence of one.**
   `origin-of-the-move (1).pdf`, p.14. "The squeeze fails with no aggressive orders at the
   failure at all: the speed of tape just dies. The absence of result is itself the signal,
   and it is the quieter, more common version of this model."

5. **Selection flips the sign of the same concept, and the defence happens inside the level,
   not at its edge.** `origin-of-the-move (1).pdf`, pp.15–17. Only 42% of touches hold;
   fading everything is −0.285R after costs; graded selection is +0.143R out-of-sample over
   542 trades; hold rate runs 25%→63% monotonically across deciles. The median eventual
   winner dips **18 ticks past the touch** before it works, and resting a limit inside the
   zone gives PF 1.80 against PF 0.81 for market orders at the touch on identical signals.

6. **Re-entry is bounded by location and offer, not by count.**
   `anatomy-of-a-losing-start (1).pdf`, p.7. "Price has to come back to the level. Not near
   it, and not on a different level that looks similar. If it does not return, there is no
   trade, and the loss just stands." Directly contradicts the crosswalk policy row
   ("unlimited sequential re-entry subject to occupancy and risk laws"), which constrains a
   different dimension.

7. **Absorption confirms in four stages that are indistinguishable in a snapshot, with a
   3-tick replenishment minimum and a 27% failure rate without pacing confirmation.**
   `stop-re-entering.pdf`, p.10. Stage 1 (initial defense) "is where beginners enter, and it
   is not confirmed"; stage 4 (lift-off) is the absorber flipping from passive to aggressive.
   "The difference only exists in time, which is why the checklist has stages instead of a
   snapshot." The crosswalk computes absorption as snapshot components.

8. **Refresh consistency, not refresh presence, separates a wall from a coincidence.**
   `18k-payout-session.pdf`, p.11. Real size refreshes at steady pace and steady size; a
   single order rotating through a queue shrinks each time **and** the intervals stretch, and
   "that thinning is what precedes the level finally giving way." Also: "a single absorption
   print is never enough to act on by itself."

9. **Two hard session-level refusals, and one that voids levels entirely.**
   `vix-lesson-4.pdf`, p.5 and p.8. VIX below 13 (expected range under 30 points) is "usually
   not worth fishing. Knowing there is no edge today IS the edge." Backwardation: "the auction
   is broken until the curve normalises," levels "mean nothing until it resolves." The
   crosswalk maps this document's entire operational content into "soft regime and target
   headroom."

10. **A stricter filter can produce a worse account, and whether it does is empirical.**
    `average-unprofitable-trader.pdf`, p.13. A fourth confluence plausibly moves a 70% win
    rate to 65% or 60% because it costs frequency: "the stricter filter can genuinely produce
    a worse account. Or a better one. You cannot know which until you've collected the 20
    trades." Reinforced by `only-trade-big-trades (1).pdf` p.17: a barrier product "rewards a
    higher win rate and steady participation," and a single-pattern strategy "leaves you
    either forcing trades or sitting out most of the month." Any abstention-shaping work
    should carry this as a pre-registered two-sided hypothesis rather than assuming that
    raising the bar helps.

---

*Audit scope note: this document reports the delta against the prior distillation only. It
makes no claim that any missed detail carries economic value, and every figure quoted above
is the source author's, under the source's own caveats (historical simulation after modelled
costs, one dataset, or the author's own records).*

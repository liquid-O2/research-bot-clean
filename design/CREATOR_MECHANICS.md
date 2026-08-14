# CREATOR_MECHANICS — the complete extraction from the nine creator PDFs

STATUS: EXTRACTION COMPLETE (port m2, lane `port-m2-pdfs`, 2026-08-14).
SOURCE: `/workspace/artifacts/reference/user_pdfs_20260812/` — nine PDFs, 162 pages total,
authored by **Sires × Ethos Order Flow** (research arm "Ethos Order Flow / Research",
companion site kanji.org.uk), July 2026 vintage.
PURPOSE: the program's name→count law. Every named mechanic/setup/filter the creator
describes is recorded here with its own name, its VERBATIM conditions, its claimed context,
its entry/invalidation, and a page cite. `provenance/port_m2/CREATOR_MECHANICS_CENSUS.md`
then formalizes each as a computable detector and counts it on E2→E6.

## Method and coverage (read before trusting any line below)

- Extraction is from the **PDF text layer** (`pdftotext -layout`), which for all nine files is
  complete prose — these are typeset documents, not scans. Text chars/page ranges 690–1270.
- **Printed page number == PDF sheet index** for all nine files (verified: each contents page
  is sheet 2 and prints "02"). Cites below are `file.pdf p.N` on that convention.
- **What is NOT in the text layer**: the chart screenshots themselves (DeepCharts / Quant
  Charts captures, GEX radar screens, schematics, equity curves, the ES distribution
  histograms). Every one of them carries a **prose caption that IS in the text layer**, and the
  captions are quoted below wherever they carry mechanism. Where a number exists only inside
  a chart image and not in a caption or table, it is marked `[IMAGE-ONLY — not extracted]`.
  Nothing load-bearing was found to be image-only: the creator restates every mechanic in prose.
- Quotation convention: `>` blocks are **verbatim** from the PDF, with the creator's own
  internal quotation marks preserved (he quotes himself from the source videos). Ellipses are
  never used inside a verbatim block — where a block is trimmed the trim is at a sentence
  boundary and marked.
- The creator is **discretionary**. Several "mechanics" are avowedly not mechanical (he says so
  himself — see M-40 and the `origin-of-the-move.pdf` p.18 disclosure). That is recorded, not
  smoothed over.

## The nine documents

| # | file | pages | kind | what it carries |
|---|------|-------|------|-----------------|
| 1 | `refill-effect.pdf` | 24 | research paper | the zone/touch/hold formalism, the feature families, the 18-tick dip, the execution result, the whole stat sheet |
| 2 | `origin-of-the-move.pdf` | 19 | education (Micro-Mechanics 01) | aggression, absorption, squeeze, squeeze catalyst, refill clock, the OFM sequence, entries + stop rule |
| 3 | `only-trade-big-trades.pdf` | 19 | education | Big Trades settings, body-vs-wick, the 350% imbalance line, the OFM *correction* (failure ≠ entry), retest-vs-break, passive moves, the gamma gate, the balance-day fade, the printable checklist |
| 4 | `mastering-amt-vp.pdf` | 27 | education | AMT three rules, POC/VAH/VAL, P/B/D day types, the **Failed Auction setup** (narrow definition), the three balance entries, overnight inventory, the 94% and 73% stats, the real 80% rule, IB/gap literature, the full ES probability appendix |
| 5 | `gex-framework.pdf` | 22 | mentorship part one | gamma flip, long/short gamma regime, call/put wall, max pain, pinning vs squeeze, vanna/charm, the orderflow-confirmation rule, session checklist, common mistakes |
| 6 | `ny-am-session.pdf` | 12 | live session recap | the refill trade, the third-test loss, **trailing convexity** (R:R 0.69→1.83), the losing-steam fade |
| 7 | `anatomy-of-a-losing-start.pdf` | 12 | live session recap | thesis-without-direction, the re-entry rule, stop-where-the-idea-is-wrong, ratio-checked-not-chosen, protected-high/low trailing, the daily-objective rules, the printable session checklist |
| 8 | `2345-funded-session.pdf` | 11 | live session recap | the **350% divergence box**, the extreme-absorption CVD read, microbalance entry, protected-low trailing, consistency-rule capping |
| 9 | `10k-first-month.pdf` | 16 | case study | level+minor-HVN confluence, second-tap absorption, KG1 levels, trailing convexity vs plain breakeven, "trade the levels not the middle of nowhere" |

---

# PART A — THE PRIMITIVES (the vocabulary every mechanic is built from)

## M-01 · Aggression (aggressive order / "Big Trades" bubble)

**Verbatim definition** — `origin-of-the-move.pdf` p.2 (glossary) and p.4:

> Aggression: a market order that crosses the spread to get filled now, accepting a worse price
> for immediacy. It shows intent and urgency to continue price.

> An aggressive order is a market order that crosses the spread to get filled now, accepting a
> worse price for immediacy. That worse price is the tell: someone is paying up because they
> want price to continue, and they want it now. On my chart these print as bubbles.

**The threshold, verbatim** — `origin-of-the-move.pdf` p.4:

> During New York AM on NASDAQ I filter to a minimum of 30 contracts and a maximum of 60 per
> print, and I adjust with the session's volume.

Restated with provenance in `only-trade-big-trades.pdf` p.3:

> The settings matter more than the feature does, because they decide what counts as aggression
> in the first place. On NQ he runs a minimum of 30 contracts and a maximum of 60, on a 40 range
> chart. That threshold is not a default he inherited. In his words it came "from my data
> collection, I've seen that it shows aggression." So the number is instrument specific and it is
> his. If you trade something other than NQ, the honest version of this is that you have to find
> your own band rather than borrow this one.

**Rendering** — `only-trade-big-trades.pdf` p.3:

> Big Trades is the aggression marker on DeepCharts. On the chart it prints as bubbles: pink and
> purple ones for sell aggression, hollow white ones for buy aggression. The size of the bubble
> tracks the size of the order behind it.

**The misconception warning** — `only-trade-big-trades.pdf` p.4:

> In his own words: "This doesn't tell you when to buy or sell, it just shows you orders, it just
> shows you information." A bubble is a record that size traded aggressively at that price. It is
> not a direction.

**CONTEXT**: NQ, 40-range chart, New York AM. **NOT an entry on its own.**

## M-02 · Absorption

**Verbatim** — `origin-of-the-move.pdf` p.2:

> Absorption: aggressive orders being soaked up by passive orders on the other side. Lots of
> effort, no movement.

`anatomy-of-a-losing-start.pdf` p.3:

> ABSORPTION — Aggression arriving at a level and the level not moving. Passive size is taking
> the other side.

## M-03 · Effort vs result (the core read)

**Verbatim** — `origin-of-the-move.pdf` p.2:

> Effort vs result: the core read. Heavy aggression that moves price has result. Heavy aggression
> that doesn't is exhaustion.

`only-trade-big-trades.pdf` p.4:

> What makes it usable is the pairing. Aggression is effort. The candle that follows is the
> reward, or the absence of one. Effort that gets paid is control. Effort that gets nothing is
> exhaustion. That single distinction is the entire read, and it is why two identical looking
> clusters of bubbles can mean opposite things.

> If you can only take one thing from this document, take this one. Aggression measures effort.
> Price measures whether the effort was worth anything. A tool that shows you the first without
> you checking the second will lose you money faster than having no tool at all.

## M-04 · Body vs wick (where the print sits decides its meaning)

**Verbatim** — `origin-of-the-move.pdf` p.4:

> Where the bubble sits decides what it means. Inside the body of a candle is the most blatant
> form of aggression: the order pushed price and got its result. On the wick is the opposite
> story: that aggression got absorbed, passive orders on the other side soaked it up, and the
> level refused to move. Same bubble, opposite meaning, and the difference is nothing more than
> effort versus result.

`only-trade-big-trades.pdf` p.6:

> Body or wick. An aggression print inside the body of the candle means that side was willing to
> trade at worse prices and got carried in their direction. The same print on the wick means the
> opposite: they pushed, and they were absorbed. It is the cheapest read on the chart and most
> people never make it consciously.

## M-05 · Aggression testing

**Verbatim** — `origin-of-the-move.pdf` p.2 and p.4:

> Aggression testing: price returning to an old area of aggression to see if those participants
> still act. Break through it and they have no result.

> Aggression testing: when price comes back to an old area of aggression, watch whether those
> participants act again. If price cuts through and closes beyond it, they have no result, and
> price usually continues until it finds the next area of aggression.

## M-06 · Aggression memory / level memory

**Verbatim** — `origin-of-the-move.pdf` p.2 and p.4:

> Aggression memory: price remembers where aggression traded. The research paper's "level memory"
> is the measured version of this.

> And aggression memory: price remembers where aggression traded. That is not a slogan; it is the
> single strongest family of features in the research paper's model, and you'll see the number
> later.

## M-07 · Speed of tape

**Verbatim** — `origin-of-the-move.pdf` p.2:

> Speed of tape: how fast prints are hitting. It spikes when a squeeze releases and dies when one
> fails passively.

`anatomy-of-a-losing-start.pdf` p.3:

> SPEED OF TAPE — How fast trades are printing. A jump in speed at a level says the level is
> being contested.

## M-08 · Cumulative delta (CVD)

**Verbatim** — `anatomy-of-a-losing-start.pdf` p.3:

> CUMULATIVE DELTA — The running difference between buying and selling aggression. Divergence
> from price matters more than the level.

**Used as a veto** — `only-trade-big-trades.pdf` p.12:

> At the premature long there was sell aggression, a sell imbalance, and repeated sellers stacked
> above. Price was pushing lower with aggression behind it. CVD was extremely bearish and sitting
> below its own median, which is the summary version of the same thing: across that whole dealing
> range down, sellers were in control.

**Checklist line** — `only-trade-big-trades.pdf` p.18: `CVD is not sitting against me on the
timeframe I am entering from.`

## M-09 · Refill (the primitive)

**Verbatim** — `anatomy-of-a-losing-start.pdf` p.3:

> REFILL — Resting size reappearing at a level after being eaten. The wall is being rebuilt
> rather than pulled.

`refill-effect.pdf` p.4:

> Traders call the mechanism a refill: the passive orders defending the level are pulled, filled,
> and quietly replaced. The level "remembers" who defended it, because those participants are
> still there.

`refill-effect.pdf` p.10 (book-level picture, caption):

> Each bar is resting buy orders at one price. The wall gets hit, price dips inside the zone, and
> if the defenders are real, fresh orders replace the filled ones before the sellers can break
> through. The trade is to be one of those replacing orders.

## M-10 · Dealing range

**Verbatim** — `anatomy-of-a-losing-start.pdf` p.3:

> DEALING RANGE — The band price is currently rotating inside, bounded by where it last failed at
> each end.

(`mastering-amt-vp.pdf` p.7 uses the same word for day-shape: "He calls them dealing ranges.")

## M-11 · Minor high volume node (minor HVN) / low volume node (LVN)

**Verbatim** — `anatomy-of-a-losing-start.pdf` p.3:

> MINOR HIGH VOLUME NODE — A shelf inside the profile where trade repeatedly happened. Reactions
> cluster there.

`only-trade-big-trades.pdf` p.10:

> The area being used as support is a minor volume node sitting at the extreme of that balance.
> Minor volume nodes are worth marking because they tend to give clean rejections and they tend
> to start trends.
>
> Then the part that decides it. Below that node there is no volume. No volume means no
> participation, so there is nothing underneath to hold price if it goes there. Volume tries to
> build lower and fails. That is the asymmetry: above the node there is structure, below it there
> is nothing.

## M-12 · Protected high / protected low

**Verbatim** — `anatomy-of-a-losing-start.pdf` p.3:

> PROTECTED HIGH OR LOW — A swing the market has already defended once. It becomes the reference
> for a trailing stop.

## M-13 · Zone (the research paper's unit of level)

**Verbatim** — `refill-effect.pdf` p.2 and p.5:

> Zone: a price area where a burst of large aggressive orders traded. Someone with size fought
> there.

> When a burst of large aggressive market orders trades at one price area (sixty, eighty, a
> hundred contracts hitting in seconds) that area stops being a random price. Somebody with size
> chose to fight there. We call the cluster of prints a zone.

## M-14 · Touch (the research paper's event unit)

**Verbatim** — `refill-effect.pdf` p.2 and p.5:

> Touch: price returning to a zone later. Each touch is one event in this study.

> The next time price returns to the zone, exactly one question matters: are the defenders still
> there? If they are, the touch is absorbed, the zone refills, and the level holds. If they are
> gone, the zone is just ink on a chart, and price trades straight through it.

`refill-effect.pdf` p.6:

> Every zone becomes a row of data. Every return of price to a zone, every touch, becomes an
> event with a known outcome: the level held, or it broke. And every fact we could have known
> before that outcome becomes a feature: a checklist item a trader could read off the chart in
> real time.

---

# PART B — THE NAMED SETUPS

## M-20 · The squeeze

**Verbatim** — `origin-of-the-move.pdf` p.2 and p.5:

> Squeeze: repeated aggressive orders getting absorbed, then releasing in one fast move. Watch
> the speed of tape when it goes.

> A squeeze starts with aggression that gets nothing. Buyers hit the market repeatedly and get
> absorbed, over and over, at the same area. Most people read that as weakness. It's the
> opposite: that cluster of absorbed aggression is the squeeze catalyst, because every one of
> those failed orders is still there, waiting to reload.

`only-trade-big-trades.pdf` p.6:

> A squeeze is a sequence, not a single candle. Buyers come in aggressively. The aggression
> prints inside the candle body, which is the version that normally means they are being paid.
> And then price goes lower anyway.
>
> Then it happens again. And again. You end up with several places on the chart where buyers
> showed real size and got nothing for it. His phrasing is that these buyers "are being
> exhausted", and that the chart now has "multiple areas where buyers are not willing to price
> higher."
>
> That accumulation is the setup. Every one of those failed attempts is a group of longs sitting
> in a losing position, and a group of resting orders above that has not been touched. The
> squeeze is not the trade. The squeeze is the fuel that makes the trade after it worth taking.

`anatomy-of-a-losing-start.pdf` p.3:

> SQUEEZE — Aggression building against a level that will not give. It either breaks, or it fails
> and unwinds hard.

**COUNT CONDITION (verbatim, from the checklist, `only-trade-big-trades.pdf` p.18):**
`I can point to repeated effort that got no reward, not just one failed candle.`

## M-21 · The squeeze catalyst

**Verbatim** — `origin-of-the-move.pdf` p.2:

> Squeeze catalyst: the cluster of absorbed aggression that sets the squeeze up. You draw it at
> the lowest (or highest) first aggression.

**Anchor rule**: the catalyst level is drawn **at the lowest (for a long) or highest (for a
short) FIRST aggression print of the absorbed cluster** — not at the mean, not at the last print.
Confirmed in the p.8 caption of the same file: `Sellers willing to price lower, the catalyst drawn
at the lowest aggression`.

## M-22 · The refill clock

**Verbatim** — `origin-of-the-move.pdf` p.2 and p.5:

> Refill clock: aggressive with no result becomes aggressive with result. The orders that failed
> reload the next attempt.

> That reload is the refill clock, and it is the engine of this whole model: aggressive with no
> result becomes aggressive with result. The buyers who were absorbed refill into the next
> attempt, more aggression joins them at worse prices (which is itself proof of intent), the
> passive sellers who were doing the absorbing get eaten, and price releases in one fast move.
> Watch the speed of tape when it happens. A real squeeze is violent and quick, and you will not
> mistake it for drift.

**Sub-condition, verbatim**: `more aggression joins them at worse prices (which is itself proof
of intent)` — i.e. the second attempt's aggression prints at prices WORSE for the aggressor than
the first attempt's.

## M-23 · OFM — the Origin of the Move (the headline setup)

**Verbatim definition** — `origin-of-the-move.pdf` p.2:

> OFM: Origin of the Move. The squeeze fails, and you enter on the re-squeeze after that failure.

**Full sequence, verbatim** — `origin-of-the-move.pdf` p.6:

> The full sequence, reading the schematic below left to right. Buyers' aggression gets absorbed:
> the catalyst. The squeeze attempt releases, buyers punch to the wall, and this time the wall
> wins: sellers regain control and price rolls back through the catalyst area. Most traders write
> the idea off right there. What actually happened is that the failed squeeze told you exactly
> where the real participation lives, because the refill clock hasn't stopped. Buyers refill below
> (a higher-risk early entry if you want it), price comes back up, sellers get their turn at no
> result, and the re-squeeze goes with buyers refilled behind it.

**ENTRY, verbatim** — `origin-of-the-move.pdf` p.6:

> THE ENTRY — On the re-squeeze, after the first squeeze fails and price retests the failure area.
> Earlier refill entries exist but carry more risk; they are marked on the schematic for
> completeness, not as the default.

**STOP AND TARGET, verbatim** — same page:

> THE STOP AND THE TARGET — Stop below the aggression (or above it, for shorts). Targets are
> discretionary and come from the higher-timeframe thesis; as a scalp model, 1R to 3R is the
> working zone, and trailing handles the rest.

**Invalidation, verbatim** (caption, same page):

> The main entry comes on the re-squeeze after the failure, with the stop loss below the
> aggression that built it, protected by the buyers who refilled. That stop rule is not
> decoration: below the aggression is the point where the read is simply wrong.

**Alternative name** — `anatomy-of-a-losing-start.pdf` p.3:

> ORIGIN OF THE MOVE — The exact point where control changed hands. It is the reference the rest
> of the move is measured from.

## M-24 · The OFM correction — "the failure of the squeeze is NOT the entry"

This is the single most emphasized correction in the corpus. `only-trade-big-trades.pdf` p.7:

> This is the part of the video he spends the longest on, because it is the part people repeat
> back to him incorrectly.
>
> The common version goes like this: the origin of the move is where the move starts, so you find
> the candle where the squeeze failed, and you enter there. It sounds right. The name seems to say
> exactly that.
>
> His correction is blunt. "People think origin of the move is just you're entering on the failure
> of the squeeze. No, that's not true." Entering on the failure is entering on the moment the
> previous attempt died. Nothing has confirmed that a new attempt is starting. You have identified
> where something ended, and treated it as a beginning.
>
> The failed squeeze does matter. It is what builds the trapped positioning and the untouched
> liquidity that the real move later runs into. But it is context, not a trigger, and the gap
> between those two things is most of the difference between this setup working and not working.

**What you ARE entering, verbatim** — `only-trade-big-trades.pdf` p.8:

> What you are entering is the drive. His line is that it is "in the name", which is fair, though
> the name is exactly what misleads people: the origin of the move is the thing that creates the
> first movement, not the low print that preceded it.
>
> Mechanically, the trigger is price taking out the wicks above. In candle terms that says buyers
> are now willing to pay higher, which is the thing they refused to do through the entire squeeze.
> The area that was acting as resistance flips to something price can use as support on the way
> back up.
>
> There is an order flow reason underneath the candle reason, and it is the part worth
> understanding. The resting liquidity above, where buyers had orders sitting untouched, gets
> converted once price trades through it. That conversion is what funds the move. Combined with
> fresh aggressive buyers at the retest, you get a group that is positioned and a group that is
> being paid at the same time.
>
> He also names the level below it. Price stalls at a refill area, which is a price where sellers
> previously failed. They did not get their result the first time, so they refill there. When
> buyers absorb that refill instead of breaking down through it, you have the confirmation.

**TRIGGER (verbatim, compact)**: `price taking out the wicks above`.
**CONFIRMATION (verbatim, compact)**: `buyers absorb that refill instead of breaking down
through it`.

## M-25 · Retest over break ("prefiring the trade")

**Verbatim** — `only-trade-big-trades.pdf` p.9:

> There are two entries available on this setup and he is open about it. The break itself is one.
> The retest of the break is the other. He takes the retest, and the reason is not that it is
> safer in some vague sense.
>
> At the break you have a sequence you can describe: buyers failed inside the range, sellers
> failed too, then inside that range the buyers started getting results because the sellers were
> being absorbed. That is a real change of control. But the break is also the moment where you
> find out whether it holds, and you are finding out with a position on.
>
> At the retest, the level you are trading has already been defended once. He calls the earlier
> alternative "prefiring the trade", and the phrase is exact: you are firing on the expectation of
> confirmation rather than the confirmation.
>
> The honest cost is that the retest does not always come. Some of these move without giving one
> back, and you miss those. He accepts that trade explicitly, because the entries you can name are
> the ones you can repeat, and a setup you cannot repeat is not a setup.

**Checklist line, verbatim** (`only-trade-big-trades.pdf` p.18):
`I am on the retest, and if there is no retest I let the trade go.`

## M-26 · The refill area (level below the OFM)

**Verbatim** — `only-trade-big-trades.pdf` p.8:

> Price stalls at a refill area, which is a price where sellers previously failed. They did not
> get their result the first time, so they refill there. When buyers absorb that refill instead of
> breaking down through it, you have the confirmation.

**Checklist line, verbatim** (p.18): `Price has taken out the wicks above, and the refill area
below held.`

## M-27 · The 350% imbalance line

**Verbatim** — `only-trade-big-trades.pdf` p.5:

> The horizontal lines running off the candles are imbalances. An imbalance prints where there is
> a divergence between buyers and sellers at one specific price, and on his settings the threshold
> is 350 percent. A sell imbalance means that price point traded 350 percent more sellers than
> buyers.
>
> On its own an imbalance is the same kind of information as a bubble. It tells you something
> happened, not what happens next. What he is looking for is the two lining up: a sell imbalance
> sitting at the same price as sell aggression. That combination says the sellers there were both
> large and one sided, and that they were willing to keep hitting into worse prices to get filled.
>
> That last part is the piece worth slowing down on. The best price for a seller is higher. If
> sellers are accepting lower and lower fills, they are not trying to get a good price, they are
> trying to get size done. That is what makes the level worth marking, and it is why he waits for
> price to come back and retest it rather than chasing the print itself.

**Checklist line, verbatim** (p.18): `An imbalance only interests me where it sits at the same
price as aggression.`

## M-28 · The 350% divergence box (the automated flag)

**Verbatim** — `2345-funded-session.pdf` p.5:

> The actual trigger was a tool that flags a specific condition: a 350 percent divergence between
> buying and selling aggression alongside a small imbalance, printed automatically as a green box
> when it fires. It is not a signal on its own, it is a flag that something worth looking at just
> happened, passive absorption on one side and aggressive pressure on the other, at the same
> price.

**Higher-timeframe gate, verbatim** (same page):

> The higher timeframe context mattered as much as the local signal. Zooming out, this level was
> where sellers had previously been trapped on the way up, visible in the delta profile as buying
> aggression getting covered rather than reversed. That combination, a local divergence signal
> sitting inside a higher timeframe area where the opposing side was already known to be weak, is
> what separated this from a random entry on a green box alone.

Caption, same page:

> The setup the box flagged: sellers exhausted, buyers priced in, entered as an origin of the move
> long once sellers who had been rewarded at this level earlier failed to hold it a second time.

## M-29 · The passive-move trap (and the sequence you want instead)

**Verbatim** — `only-trade-big-trades.pdf` p.13:

> You are long. Price is going up. You check the chart and there is no buy aggression anywhere in
> the move. No effort on your side at all, just an absence of sellers. He calls this an entirely
> passive move, and his read is that these are normally short term swings rather than the start of
> anything.
>
> What makes it a trap is the emotional shape of it. Price runs, you are halfway to target, and
> confidence is highest at exactly the moment the evidence is weakest. As he puts it, you would be
> thinking "this is going straight into profit", and the thing you have not checked is whether
> anyone on your side actually did anything.
>
> The version he wants is a sequence, and the order matters. First the opposition's aggression
> fails, so they are exhausted, trapped or absorbed. Then your side arrives aggressively.
> Opposition failing on its own is only half of it, and half is what most people trade.

**ORDERED TWO-STAGE CONDITION (verbatim, compact)**: `First the opposition's aggression fails
[...] Then your side arrives aggressively.`

## M-30 · Both sides absorbed → nobody in control → wait for the break

**Verbatim** — `only-trade-big-trades.pdf` p.4:

> The trap is that both sides usually show effort at the same time. Buyers absorbed at the top of
> a range, sellers absorbed at the bottom of it. When that is the picture, you do not know who is
> in control, because nobody is yet. His instruction there is to wait for the break rather than to
> pick a side inside the range.

## M-31 · The balance-day fade / failure-of-aggression trade (the "other 80 percent")

**Verbatim** — `only-trade-big-trades.pdf` p.15:

> In a long gamma environment the trade inverts, and it gets simpler rather than harder. It is a
> failure of aggression trade, and the key difference is that you no longer need your own side to
> be rewarded.
>
> The sequence runs like this. Buyers are absorbed at the top of the range. Price comes back to
> that area of absorption and those buyers are still not being rewarded. Price goes lower. He
> waits for the test back into it, enters on the trigger there, and targets back to where sellers
> previously had control.
>
> The reason it works is the same reason the aggressive version does not. In balance, sell
> pressure and sell imbalances get absorbed passively, and passive absorption is exactly what
> carries price in a balanced market. The thing that made a passive move a warning sign in a
> trending environment is the mechanism you are trading here.
>
> It is also the trade most people talk themselves out of, because they are waiting for a squeeze
> that a balanced market has no reason to produce.

**Checklist, verbatim** (p.18):
> THE BALANCE DAY TRADE, THE OTHER 80 PERCENT
> - An extreme, with the aggression there having failed to get paid.
> - I am entering the test back into that area, targeting where the other side last had control.
> - I am not waiting for a squeeze, because a balanced market has no reason to give me one.

**Demonstrated geometry** (caption p.15): `One contract, 33 points of target against 9 points of
stop.` (R:R 3.67)

## M-32 · Aggression arriving inside a balanced session

**Verbatim** — `only-trade-big-trades.pdf` p.16:

> Balanced sessions are not uniformly passive. Once in a while aggression does turn up inside one,
> and when it does the move is disproportionate, because it is arriving into a market that has
> spent hours absorbing everything.
>
> He points at one of these directly. Everything before it was passive drift inside the range.
> Then real aggression prints, and the leg that follows is, by his estimate, four or five R before
> it was even done. His note on it is that "that is a lot" on a prop account, which is the correct
> frame: it is not a bigger idea, it is the same idea in a moment where the market finally paid for
> it.
>
> Worth being clear that four to five R is his read off the chart in review, not a logged result.

## M-33 · The Failed Auction setup (the narrow definition)

**Verbatim** — `mastering-amt-vp.pdf` p.9:

> Every red box on the balance schematic a few pages back is technically a failed auction: price
> left the range and came back. That is the general case, and it happens on its own roughly one
> time in five. The Failed Auction setup is a specific, narrower version of it, and confusing the
> two is the most common mistake beginners make with this concept.
>
> The setup requires balance, a break out of it, and then price actually travelling to and tagging
> a prior balance, an older one, at its POC. When it hits that prior POC and instantly rejects,
> refusing to accept it, there is an 80% statistic behind what happens next: price travels back to
> the boundary of the balance it broke from in the first place, its established balance. Reject
> from above a prior POC and the target is that established balance's VAH. Reject from below and
> the target is its VAL.

**Caption, p.10**: `Both directions of the same setup. Balance, break, tag the prior balance's
POC, reject, and the established balance gets its boundary hit four times out of five.`

**The negative example (what does NOT count), verbatim** — `mastering-amt-vp.pdf` p.11:

> Chart 1 is correct. Balance, break, a tag of the prior balance's white box, an instant
> rejection, and an entry back toward VAH as target. Chart 2 fails the definition even though it
> looks similar: price does break balance and does retest a grey zone, but it never tags a prior
> balance and rejects there, it simply breaks down, keeps going, and the retest is a trend
> continuation entry, not a failed auction. Same visual grammar, opposite trade, which is exactly
> why the setup needs its full definition and not just "price came back to something."

**Checklist, verbatim** (p.26):
> THE FAILED AUCTION SETUP
> - Balance, break, and a tag of a PRIOR balance's POC, not just any retest.
> - An instant rejection at that POC, not acceptance of it.
> - The target is the established balance's own VAH or VAL, not an arbitrary level.

**Also glossed** — `anatomy-of-a-losing-start.pdf` p.3:

> FAILED AUCTION — Price leaves a range, fails to find acceptance, and comes back inside. The
> failure is the signal.

## M-34 · The three balance entries

**Verbatim** — `mastering-amt-vp.pdf` p.12:

> On a real composite profile the same balance mechanics turn into three repeatable entries. Break
> out of balance and retest the broken boundary: enter in the direction of the break, long on a
> retest of a broken-up level, short on a retest of a broken-down one. Come back inside the balance
> and re-accept it: the bias flips, now you're fading back toward the other side. Traverse straight
> through the whole balance without holding: that's one side fully priced in, and every retest from
> there trades with that side until proven otherwise.

## M-35 · Level + minor-HVN confluence ("two independent reasons at the same price")

**Verbatim** — `10k-first-month.pdf` p.7:

> The first was a short off a level he'd already marked as a key area of resistance, price had
> rejected from it before. He lined it up against a minor high volume node sitting close by, two
> independent reasons pointing at the same price rather than one.
>
> Stop went above the high of the rejection, target set at 1.5R. Nothing exotic in the mechanics,
> the discipline is entirely in the level selection: he took this because two things agreed, not
> because price simply arrived somewhere round.

## M-36 · The second tap with absorption

**Verbatim** — `10k-first-month.pdf` p.8:

> Going into the session he'd also written down a second possibility: if price retraced, there was
> room for a bigger move higher, a backtest of the same structure from the other side. When price
> came back down to that level and he saw absorption there, buyers stepping in and holding, he took
> the long. Same 1.5R target as the first trade, same process, same discipline of only acting once
> the level actually printed the reaction he'd written down beforehand.

## M-37 · The refill trade (live session, Trade 1)

**Verbatim** — `ny-am-session.pdf` p.4:

> This is the session's opening trade, and the read was simple: "sellers are being absorbed at the
> bottom, stop just below these buyers that are in control, targeting higher timeframe objective."
> Sellers had pushed lower and gotten nothing for it, so price refilled straight back into the
> buyers defending that level.
>
> That refill is the signal itself, not a guess at direction. It's a read of who's actually winning
> the fight for that price.

Caption p.4: `Sellers get absorbed at the bottom of the range here, the two small circles marking
where buyers stepped in and held. The stop sits just below.`
Result (p.5): `It closed for $755.`

## M-38 · The third-test short (the documented LOSS)

**Verbatim** — `ny-am-session.pdf` p.6:

> Not every read works, and this one is in here because of that. Sellers had already hit this
> level twice with nothing to show for it: no buyers stepping in either time. On the third retest,
> still nothing, so the short went in: "I'm in these shorts with my stop just above, targeting this
> area, kind of low risk."

p.7:

> It got stopped. Low risk doesn't mean no risk, and a level failing to hold twice doesn't
> guarantee it fails a third time.

**This is a NEGATIVE control the creator himself publishes.** It is censused as a mechanic in its
own right (does the third test of a twice-failed level pay?).

## M-39 · The losing-steam fade (live session, Trade 4)

**Verbatim** — `ny-am-session.pdf` p.10:

> The last trade of the session, taken once the day's objective was already basically in hand: "I
> was ready above the objective I wanted for today." The resistance level here had been marked out
> in advance, and the move into it was losing steam rather than accelerating, which is the tell I
> was waiting on, not just fading a level because it's a level.

Caption p.10: `Price stalls into a resistance level already marked out ahead of time. The move up
is losing aggression candle by candle, not gaining it.`

## M-40 · The microbalance push-through entry

**Verbatim** — `2345-funded-session.pdf` p.7:

> The first trade recorded live was a long, entered once price showed the strength to push through
> a short term microbalance. Management was mechanical from there: once the position moved
> favourably, the stop trailed to the most recent protected low rather than a fixed distance, so
> the trade could only give back a defined amount of what it had already earned.

Caption p.7: `The long entry, R:R 5.59 planned against a stop below the microbalance low that
formed the entry.`

p.9 (the short): `entered on a lower push after the same kind of microbalance read as the first
trade, this time working in the opposite direction.`

## M-41 · The extreme-absorption CVD read

**Verbatim** — `2345-funded-session.pdf` p.6:

> A beginner reason for drawing a level is "price reacted here before." That's where most thesis
> building stops, and it's also where it should really start.

> Looking only at price, that resistance area looks like normal supply. Looking at the CVD
> underneath it tells a different story: across the entire consolidation session, CVD was dying
> while price held or drifted up, meaning the passive limits at that level were being consumed and
> reloaded, not defended for free. That combination, price refusing to drop while the delta record
> shows no real selling pressure behind the level, is what extreme absorption actually looks like,
> and it's the difference between "this level worked before" and "this level is currently being
> tested and passed."

Creator's own one-liner (p.6): `"Price rising = high conviction that session sellers had insane
control."`

Caption p.6: `price grinding up against resistance is not weakness in the level, if the order flow
underneath shows sellers being absorbed rather than actually selling.`

**This is a price↑ / CVD↓ divergence condition measured over a whole consolidation, not a bar.**

## M-42 · Repeated failure to reclaim (the "priced in" read)

**Verbatim** — `2345-funded-session.pdf` p.4:

> Going into the session, price had already made a strong move higher, and the read started with
> what sellers had failed to do: repeated attempts to reclaim the prior range, and repeated
> failure. The weekly delta profile showed heavy buying aggression behind the move, which is a
> different statement than "price is going up." It's a statement about who is actually in control
> of the auction, not just which way the last few candles printed.

Caption p.4: `Multiple failed attempts to reclaim the range below, each one adding to the case
that buyers were priced in, not just leading.`

---

# PART C — THE REGIME AND CONTEXT FILTERS

## M-50 · The gamma gate (short gamma only for the OFM)

**Verbatim** — `only-trade-big-trades.pdf` p.14:

> He would only take the origin of the move trade in a gamma short environment. The reasoning is
> that the setup needs an expansive move to pay, and expansive moves are what a short gamma
> environment produces. In a long gamma environment the market balances and chops instead, and
> both extremes get absorbed most of the time.
>
> Which means the same chart pattern, read the same way, is a different trade depending on a
> condition you check before you look at the chart at all. In balance, the squeeze failing is not
> a precursor to a drive. It is just the top of the range doing what the top of a range does.

**Frequency claims, verbatim** (same page):

> His frequency numbers move around. At one point the A plus plus version happens "once or twice a
> week, if that", later "maybe even twice a month", elsewhere once every couple of days. The honest
> read across all of it is a handful of times a month at most, and the direction of the point never
> changes: it is rare, and you cannot build a month around it.
>
> Against that, his figure for the other environment is stated twice and without hedging. 80
> percent of the time the market is in balance. 80 percent of the time you are in a long gamma
> environment.

## M-51 · Long gamma vs short gamma (definition)

**Verbatim** — `gex-framework.pdf` p.6:

> GEX measures the dollar value of futures dealers must buy or sell to stay delta-neutral for a
> given move in price. The sign of that number is everything.
>
> LONG GAMMA / Positive GEX, stabilising — Volatility gets suppressed; Price pins near big
> strikes; RANGE; Ranges and mean reversion
>
> SHORT GAMMA / Negative GEX, amplifying — Volatility expands; Breakouts run, levels break; TREND;
> Trends and momentum
>
> When dealers are short gamma, a move forces them to trade in the same direction as price: they
> buy higher and sell lower. That feedback loop, lower prices triggering more dealer selling, is
> why the sharpest trend days happen in negative gamma.

`anatomy-of-a-losing-start.pdf` p.3:

> LONG GAMMA REGIME — Dealer positioning that dampens moves. Ranges hold and expansion is rare, so
> scalps fit better.

## M-52 · The gamma flip (zero gamma level)

**Verbatim** — `gex-framework.pdf` p.7:

> One price matters more than any other: the level where net dealer gamma crosses from positive to
> negative. It is called the zero gamma level, or the gamma flip, and it is the most useful line on
> the whole GEX map.
>
> Above the flip, dealers are net long gamma, so the regime is stabilising: expect range and mean
> reversion. Below the flip, dealers are net short gamma, so it is amplifying: expect trends and
> expansion. Crossing the flip intraday is a regime change, and one of the highest-value events you
> can watch for.

## M-53 · Call wall / put wall / max pain

**Verbatim** — `gex-framework.pdf` p.13:

> CALL WALL — Largest call gamma above. Resistance as dealers sell into it.
> PUT WALL — Largest put gamma below. Support as dealers buy into it.
> MAX PAIN — Strike where option value is lowest. Price often drifts toward it into expiry.
>
> In long gamma the walls are hard boundaries, so fading toward them works. In short gamma the same
> walls break easily, so trade the breakout through them.

## M-54 · Pinning vs gamma squeeze

**Verbatim** — `gex-framework.pdf` p.12:

> PINNING — STRIKE GRAVITY — Spot spends time near a strike into expiration. Near the money gamma
> is highest, so when hedging is stabilising, price gets pulled into rotations around the strike.
> The auction has a local attractor because hedging dampens every breakout attempt.
>
> GAMMA SQUEEZE — CONVEXITY — A move where dealer hedging reinforces direction. Price pushes
> through a major strike, hedging demand increases with the move, and it accelerates on thin
> liquidity and hedge chasing. It can happen both up and down.
>
> Pinning looks like rotations that keep failing at a strike. A squeeze looks like that same strike
> breaking on aggression and then accelerating away. Same level, opposite behavior, and the regime
> is what tells you which one to expect.

## M-55 · Confirm the GEX level with orderflow (never trade GEX alone)

**Verbatim** — `gex-framework.pdf` p.18:

> In long gamma, confirm the fade — Price drifts up into the call wall or an extreme. Before you
> fade it, watch the DOM and the footprint for absorption and real selling aggression. The dealer
> flow is on your side here, but the tape has to confirm someone is actually defending that level.
>
> In short gamma, confirm the break — Levels break easily in negative gamma, so do not sit there
> fading them. Wait for aggression and refills pushing through the level, then trade the
> continuation. Fading a trend day is how you give it all back.
>
> Use GEX to size and target — Short gamma earns the higher R and the wider targets because dealers
> are amplifying the move. Long gamma is smaller R and faster exits. Same setup, the regime tells
> you how hard to press and how far to actually target.

Also p.19 (checklist): `Re-check after big moves — A large impulse can flip the regime
mid-session. After a big expansion the read often turns long gamma, so update before the next
trade.`

## M-56 · Vanna and charm

**Verbatim** — `gex-framework.pdf` p.17:

> VANNA — Delta's sensitivity to implied volatility. When IV falls, dealers must buy to re-hedge.
> That is the engine behind the steady grind higher after a VIX drop, the vol-compression rally.
>
> CHARM — Delta's decay as time passes. Into expiry it quietly pulls price toward the biggest
> open-interest strikes. It is a big part of why quiet days melt up toward max pain and the call
> wall.

## M-57 · The AMT three rules

**Verbatim** — `mastering-amt-vp.pdf` p.4:

> 1. Understand the current auction. Before anything else, know whether price is inside balance or
> has already broken it, because the two states call for opposite behaviour.
>
> 2. Price stays in balance most of the time. Not all of it, roughly 80%, a figure this document
> tests against real published data later in the appendix. The other 20% is the auction failing,
> and failure is not rare, it's a fifth of every session.
>
> 3. Stop using VAH and VAL as levels. This is the rule beginners skip. Value Area High and Low are
> not fixed prices, they are outputs that move every time volume prints. Sell VAH blindly and VAH
> relocates above you as price consolidates there, because that consolidation is volume, and volume
> is exactly what VAH is built from. You are not trading a level, you are trading an indicator that
> recalculates against your own position.

**POC/VAH/VAL, verbatim** (p.5):

> Every balance has the same three landmarks. POC is the single price that traded the most, the
> peak of the volume profile. VAH and VAL are the upper and lower boundary of the area holding
> roughly 70% of that volume around the POC, the edges of where the market has actually agreed on
> fair value. Price does not wander evenly through this box. It spends about 80% of its time inside
> it, and the remaining 20% outside is exactly what a failed auction is.

## M-58 · Day types P / B / D

**Verbatim** — `mastering-amt-vp.pdf` p.7–8:

> A P day has its bulk of volume sitting toward the top of the balance, a fat head with a thin tail
> hanging below it, and it resolves with price breaking down out of the bottom. A B day is the
> mirror of it, volume concentrated toward the bottom, resolving higher.

> A D day is neither a P nor a B: the profile stays compact and centred, price tests both edges of
> the box and never commits, pure compression with no resolution at all.

> None of the three is a trade signal on its own. A P or B day tells you a session has already
> resolved directionally, which changes how much leniency the opposite side deserves for the rest
> of it. A D day tells you the market genuinely has not decided yet, which is information too, just
> a different kind.

## M-59 · Overnight inventory and the ON LVN / shelf

**Verbatim** — `mastering-amt-vp.pdf` p.14:

> Overnight inventory is the second half of Volume Profile most beginners skip entirely. From 6pm
> the previous day to 9:30am New York open, a lot of real size moves, banks closing out positions
> before the volatility of the open arrives. Whether price nets long or short across that window
> matters because it tends to carry into the open: net long overnight, the path of least resistance
> at 9:30 is higher, net short, it's lower, purely because of how much aggression already sits on
> one side of the tape.
>
> The tool for judging whether that overnight bias survives the open is the low volume node inside
> the overnight profile, drawn from 6pm to 9:30. One clean distribution and the net environment
> usually just continues. A double distribution and the low volume node between the two humps
> becomes the decision point, the level that gets "respected" if the open continues the overnight
> direction, or "disrespected" if it doesn't. The overnight shelf reads the same way: hold it and
> price likely stays inside the overnight range, break it with real aggression and price is more
> likely heading back to test the overnight extreme.

## M-60 · Higher-timeframe filtering ("leniency")

**Verbatim** — `mastering-amt-vp.pdf` p.13:

> A 15-second chart will hand you a level and a direction constantly. The higher timeframe is what
> tells you whether to believe it. If a lower timeframe short level fires but the higher timeframe
> shows you're still inside balance near its lower boundary, buyers are the side statistically
> likely to defend there, so that short gets less leniency, not more, even though the lower
> timeframe looks clean. The auction context outranks the trigger.

`only-trade-big-trades.pdf` p.11:

> That alignment is also what gives you what he calls leniency. If you know the higher timeframe
> favours buyers, then you know who to give the benefit of the doubt to when the order flow gets
> messy, and you know which absorption to expect to hold. Without it, every wick is a coin flip.

**The thesis-first law, verbatim** — `origin-of-the-move.pdf` p.3:

> One thing before any of it, because the whole model leans on it: none of this replaces the
> higher-timeframe thesis. The auction narrative, the volume profile location, the objectives: that
> is what supplies direction. I tested this feature set without the thesis behind it and it is
> basically a coin flip. With the thesis aligned, the numbers you'll see later in this paper hold.
> Keep that order of operations. Thesis first, mechanics second.

---

# PART D — THE PUBLISHED IF-THEN STATISTICS (the creator's own claims, to be replicated)

## M-70 · The 94% overnight-extreme touch stat

**Verbatim** — `mastering-amt-vp.pdf` p.15:

> There is a 94% chance of price touching either the overnight high or the overnight low during the
> current session. Used correctly, that number is a reason to not take a trade rather than a reason
> to take one: if a long level sits a few points above the overnight low with a tight stop
> underneath it, and there's a 94% chance price still trades down to tag that overnight low first,
> the level isn't wrong, the timing is.

Caption: `94% chance of either, not both. The number says the level probably gets touched before it
gets rewarded.`

## M-71 · The 73% MPOC stat

**Verbatim** — `mastering-amt-vp.pdf` p.16:

> If the RTH session opens inside the previous ETH profile's balance, there is a 73% chance of the
> session going on to hit that ETH profile's MPOC, its mid. If you're already long from inside that
> balance, this is a reason to hold and trail rather than take the first easy target at VAL,
> because the statistical pull toward the profile's mid is real and it's not marginal.

## M-72 · The real 80% rule (narrow form)

**Verbatim** — `mastering-amt-vp.pdf` p.18:

> The "80% rule" gets repeated constantly in Market Profile material, almost always in the loose
> form used earlier in this document: price stays in balance about 80% of the time. The actual,
> specific rule that circulates under that name is narrower: if price opens above or below the
> previous day's value area, then trades back inside it for two consecutive 30-minute periods,
> there is an 80% chance it goes on to trade completely through the entire value area to the other
> side. That's a real, testable claim with real preconditions, not a generic restatement of
> "balance holds most of the time." It's commonly linked back to Dalton Capital Management's
> Profile Reports from the late 1980s, though tracing it to a specific published study is harder
> than the amount it gets quoted would suggest, worth knowing before leaning on the number.

## M-73 · Initial Balance range extension

**Verbatim** — `mastering-amt-vp.pdf` p.19:

> The Initial Balance, the first hour's range, is genuinely predictive of where the rest of the
> session goes: a close outside the IB is commonly cited at 65 to 75% likely to see continuation in
> that direction, and a failed excess move back inside the IB at a similar 70 to 75% likelihood of
> trading the other side. Those figures show up across a lot of practitioner material with almost
> no citations behind them, repeated because they sound right and nobody's disputed them loudly,
> not because there's a public dataset backing the exact number. What is independently documented,
> from CME Group's own research, is that roughly 68% of a day's price action falls within one
> standard deviation of that session's POC.

## M-74 · Gap-fill statistics (and the creator's own NQ caveat)

**Verbatim** — `mastering-amt-vp.pdf` p.19:

> Roughly 70 to 75% of gaps eventually fill, but that number hides the part that actually matters:
> small gaps under about 0.5% fill same-session around 65% of the time, gaps over 1% fill
> same-session only around 35% of the time and are more likely to keep running in the gap's
> direction. Down gaps fill slightly more often than up gaps, 62% against 59%. And directly
> relevant to this instrument: a recent systematic study testing gap-fill signals specifically on
> Micro Nasdaq futures found the fade failed at every entry time tested, no consistent edge, as
> likely to continue as to reverse. The honest read is that gap-fill statistics that look solid on
> ES do not automatically transfer to NQ.

## M-75 · The ES Probability Statistics Report (full appendix, ES only)

`mastering-amt-vp.pdf` pp.20–25. Basis, verbatim (p.20):

> on E-mini S&P 500 futures across four contracts, ESH, ESM, ESU and ESZ, 1,040 sample days from
> 2021 to 2024. [...] Sample days: 1,040. RTH session: 06:30 to 13:00 PST. IB session: 06:30 to
> 07:30 PST.

**Auction Type** (p.20): Trend Day 24.11 / 29.25 / 24.11 / 20.95 %; Neutral Extreme 17.79 / 15.81 /
10.67 / 9.49 %; Neutral Day 12.25 / 11.86 / 11.86 / 9.09 %; Normal Day 23.72 / 22.13 / 26.09 /
31.62 % (ESH/ESM/ESU/ESZ).

Verbatim day-type definitions (p.20):

> Trend Day, a one-timeframe auction where the market continues to seek new value in one direction
> without reversing, price discovery extends beyond IBx2, confirming strong imbalance and
> directional intent. Neutral Extreme Day, a rotational day where price exceeds both the IBH and
> IBL and settles near an extreme of the range, very powerful, often continuation in direction of
> the extreme, binary events often display as neutral. Neutral Day, the market auctions efficiently
> in both directions, breaching IBH and IBL but finding fair value within the IB range. Normal Day,
> fair value is established early as IB containment limits further exploration, minimal range
> extension, typically in low-volatility environments or before major events.

**Overnight Session Levels touched during RTH** (p.21): ONH & ONL 20.16/23.75/22.22/23.85 %;
**ONH or ONL 92.49 / 95.40 / 94.64 / 95.00 %** (this is the source of the "94%" headline);
ONH 60.47/61.69/64.75/62.31 %; ONL 52.17/57.47/52.11/56.54 %; ONVAH 75.10/74.33/78.16/78.85 %;
ONVAL 70.75/74.71/68.58/71.54 %; ONVPOC 90.12/86.21/87.74/90.00 %.

**Opening Location** (p.21): Opens Above P.Close (Gap) 53.41/54.09/57.59/53.13 %; Opens Above pHOD
24.50/26.07/21.79/21.88 %; Opens Below P.Close 45.78/44.36/42.41/45.70 %; Opens Below pLOD
19.68/14.79/15.56/12.89 %; Opens Within pIB 23.60/22.18/26.07/33.59 %; Opens Within P.Value
32.53/33.85/36.19/37.11 %.

**Initial Balance** (p.23): At Least One IB Broke 98.81/99.62/96.55/98.08 %; Both IB Broke (Neutral
Day) 35.97/31.80/25.29/22.31 %; IB Range Within pIB 6.43/4.28/3.11/7.03 %; Neither IB Broken
1.19/0.38/3.45/1.92 %; Only IBH Broken 34.39/36.78/38.70/39.23 %; Only IBL Broken
28.46/31.03/32.57/36.54 %; Opens in pIB Breaks pIB Within IB 17.27/17.90/22.96/26.56 %; Opens in
pIB Breaks pIB Within RTH 22.09/22.18/26.07/32.42 %; Closes Above IBH 23.32/27.59/29.12/25.38 %;
Closes Below IBL 18.97/19.54/21.46/25.77 %.

Gap-up / opens-within / gap-down tables are on pp.22–23 in full and are reproduced verbatim in
`provenance/port_m2/CREATOR_STATS_ES.tsv`.

**Creator's own caveat, verbatim** (p.15):

> these stats are not meant to be the main objective of an edge on their own, and they only mean
> anything once you already understand AMT on the higher timeframe. Used blind, without that
> context, they're just numbers.

And (p.17):

> even across five, twenty or fifty years of data, these if-then statistics apparently hold within
> one to three percent of each other. That is a genuinely strong claim, and also exactly the kind
> of claim worth being skeptical of by default until you've tested it yourself.

---

# PART E — THE RESEARCH-PAPER MEASUREMENTS (`refill-effect.pdf`) — the creator's own census

These are the creator's OWN numbers on his OWN data (NQ/MNQ, Dec 2024–Nov 2025, 199M ticks, 235
sessions, 41,152 zone-touch events). Our census replicates them on our data.

## M-80 · The base rate and the honest baseline

**Verbatim** — `refill-effect.pdf` p.8:

> Start with the honest baseline. Only 42% of touches hold. Fading every touch (buying every
> support touch, selling every resistance touch, no questions asked) loses −0.285R per trade after
> costs. The raw concept, traded indiscriminately, is a losing strategy. That is the starting
> point, not the punchline.

## M-81 · The four feature families

**Verbatim table** — `refill-effect.pdf` p.8:

| FAMILY | THE QUESTION IT ANSWERS | EXAMPLES |
|---|---|---|
| Memory | Has this zone been defended before? | held earlier this session; prior-day defence |
| Construction | Was it built by real size? | number & size of aggressive prints; zone width |
| Location | Is it at a real auction edge? | value-area edges, session extremes, distance from open |
| Flow & state | What is happening as price arrives? | delta into the touch, approach speed, balance vs imbalance |

> Each touch carries roughly twenty pre-touch features, in four families, every one of them a fact a
> trader could check on the chart before the trade

## M-82 · The selection result and the decomposition (the finding against his own branding)

**Verbatim** — `refill-effect.pdf` p.9:

> Out-of-sample, the touches it ranks highest hold 63% of the time; the ones it ranks lowest hold
> 25%.

> ONE FINDING CUTS AGAINST OUR OWN BRANDING — When we decompose the model, the memory and location
> families do almost all the work; raw order-flow features alone barely beat a coin flip (AUC 0.54).
> Aggression builds the level, but it is the level's memory that predicts the next touch. We would
> rather report that than sell a prettier story.

## M-83 · The 18-tick dip (the refill effect proper)

**Verbatim** — `refill-effect.pdf` p.10:

> The tick data then explained why, and the reason is the refill itself: around a genuine defended
> level, the median eventual winner first dips 18 ticks past the touch before it works. The defence
> does not happen at the front edge of the zone. It happens inside it, where the resting orders
> reload.

`origin-of-the-move.pdf` p.15:

> If you act the instant price tags the level, you are acting at the exact point where the data says
> the trade has not started yet.

## M-84 · The execution asymmetry (resting limit vs market order)

**Verbatim** — `refill-effect.pdf` p.11:

> MARKET ORDER AT THE TOUCH — You do what the losing aggressors do: pay the spread to push into a
> wall, enter before the flush, and eat the full 18-tick dip against a tight stop. You pay for the
> defence.
>
> RESTING LIMIT INSIDE THE ZONE — You are filled by that same flush, at the price where the refill
> is defending, alongside the defenders. You are the refill, and you collect the premium the
> impatient side pays.

> Nothing changes between the two columns except the entry order type: not the signals, not the
> period, not the engine, not the costs. Resting inside the zone earns a profit factor of 1.80;
> chasing the touch with market orders earns 0.81 and loses money.

Caption p.11: `the resting-limit entries fill on 64 trades; the market-order entries fill on 312.
The limit fills less often precisely because it demands the flush that defines the setup.`

Stat sheet p.23: `Resting limit: win / PF / P&L — 68.8% / 1.80 / +$2,112`; `Market order: win / PF
/ P&L — 27.2% / 0.81 / −$405`.

## M-85 · The deployed configuration

**Verbatim** — `refill-effect.pdf` p.12:

> The deployed configuration in one sentence: at a model-selected zone, rest a limit order 12 ticks
> inside the level, stop 32 ticks, target 96 ticks, cancel after 30 minutes, one position at a
> time, with a 1-tick round-trip cost and 1 tick of stop slippage charged.

Result: `+0.143R PER TRADE, AFTER COSTS / 1.19 PROFIT FACTOR / +78R CUMULATIVE, 542 TRADES / ~6.8
TRADES PER DAY`.

## M-86 · First touch is the weakest ("wait for the second test")

**Verbatim** — `origin-of-the-move.pdf` p.16 (playbook):

> Wait for the second test, or for memory, construction, and location to agree. The first touch of a
> fresh zone is the weakest version of this trade.

## M-87 · The regime-dependence disclosure (the losing quarter)

**Verbatim** — `refill-effect.pdf` p.14:

> Q4, the most recent slice, lost money at every parameter setting we tried. The edge is
> regime-dependent: weakest when volatility compressed late in the sample. We flag it and count it
> in every statistic, because an edge that only appears when losing periods are trimmed away is not
> an edge.

## M-88 · THE CREATOR'S OWN NULL RESULT — no mechanical entry exists

**Verbatim** — `origin-of-the-move.pdf` p.18. This page is the single most important calibration in
the entire corpus and is reproduced in full:

> There is no mechanical entry signal in here. When the entry was rebuilt from scratch and tested
> causally, with every trace of hindsight stripped out, it came back negative: on the order of
> −0.16R to −0.54R out-of-sample. The earlier version that looked profitable had quietly used
> information from later in the day to pick which setup was "the one." Remove that peek and the
> mechanical edge disappears. What survives is a grading system for touches you have already found,
> and an execution rule about which side of the book to stand on.
>
> The thesis is not optional. I tested this feature set without the higher-timeframe narrative
> behind it, and on its own it is basically a coin flip. The auction bias, the profile location, the
> objectives: that is what supplies direction, and it is the only reason the refill read works at
> all. Every pass rate on the previous page assumes the thesis is already aligned. If you skip that
> part, you are not trading this model; you are flipping coins with extra steps.
>
> The edge is thin and it lives on discipline. +0.143R per trade in the research replay, roughly
> half that on the stricter independent engine, and a losing quarter already sits in the record. A
> thin edge survives on the −4R daily stop, the sizing, and the patience to wait for graded setups.
> It does not survive a trader who overrides it.

**Programme note**: this is the creator predicting our own D-021/M2 result — the pre-entry tape at
confirmation does not separate winner from loser, and what remains is *grading* and *execution*.
It is recorded here as the corpus's own pre-registration, not as our finding.

---

# PART F — MANAGEMENT, RISK, AND SESSION MECHANICS

## M-90 · Trailing convexity

**Verbatim** — `origin-of-the-move.pdf` p.13:

> TRAILING CONVEXITY — Cut the loss branch off while the win branch keeps running. Each new
> aggression pocket that forms below gives the stop a new home above it.

`ny-am-session.pdf` pp.8–9:

> The entry itself wasn't a high reward-to-risk trade on paper: R:R 0.69, meaning the initial target
> was smaller than the initial risk. Most traders would skip that outright.

> The difference is what happens after the entry. Instead of a fixed stop and fixed target, the stop
> trails behind price as it moves in my favor: "trailing convexity means I have to trail here, if we
> push up higher, I can trail again."
>
> Each trail locks in more of the move without capping how far it can run. By the time the trail was
> hit, the same entry that started at R:R 0.69 had become R:R 1.83, just from letting the stop do
> the work instead of a fixed target: "so this was a kg one retest trade with the trailing
> convexity, that's why I got out there."

**Why it replaces plain breakeven, verbatim** — `10k-first-month.pdf` p.9 (member's own words):

> "If you go normally to breakeven, after a hundred trades, if you actually look at the stats it
> ruins your EV in a problem environment. But the way you cater it, it's a much better way to go
> breakeven."

## M-91 · Trail behind protected structure

**Verbatim** — `anatomy-of-a-losing-start.pdf` p.10 (checklist, IN THE TRADE):

> - Move to break even when the reason weakens. Not at a fixed number of ticks.
> - Trail behind protected levels. Swings the market has already defended once.
> - Cut fast when wrong. The loss being small is the entire reason the model works.

`2345-funded-session.pdf` p.7: `the stop trailed to the most recent protected low rather than a
fixed distance, so the trade could only give back a defined amount of what it had already earned.`

## M-92 · The absorption exit

**Verbatim** — `origin-of-the-move.pdf` p.9 (Example 3, A+ long):

> Trail until buyers hit a wall and get fully absorbed: that absorption is the exit.

## M-93 · Stop location: where the idea is wrong

**Verbatim** — `anatomy-of-a-losing-start.pdf` p.8:

> The stop is not tight because tight stops are good. It is 35 ticks because that is where the idea
> is wrong. Below the buyers who were holding, the reason for being long has gone, and there is
> nothing left to wait for.
>
> The target is not far away because far targets are good either. It is the next place on a higher
> timeframe where price has unfinished business.

## M-94 · Ratio checked, not chosen

**Verbatim** — `anatomy-of-a-losing-start.pdf` p.9:

> What both have in common is the order the decisions get made in. The stop location is decided by
> structure, before entry. The size is decided by the stop. The target is whatever the higher
> timeframe already owed. At no point is the ratio chosen first and the levels bent to fit it.
>
> That ordering is what makes the win rate survivable. If the stop is placed to make a ratio look
> good rather than to mark where the idea is wrong, the trade gets stopped for reasons that have
> nothing to do with the read, and the losses stop being cheap.

Observed geometries: `The stop is 35 ticks, which is $175. The target is 188 ticks, which is $940.
The platform prints the ratio itself: 5.37 to 1.` (p.8) and `a stop 15 ticks away, $75, against a
211 tick objective worth $1,055. The ratio printed on the box is 14.07 to 1.` (p.9)

## M-95 · The re-entry rule

**Verbatim** — `anatomy-of-a-losing-start.pdf` p.7:

> Getting stopped is not a reason to get back in. It is not a reason to stay out either.
>
> Most re-entry damage comes from re-entering where you were stopped, immediately, because the loss
> is still fresh. That is a different trade to the one that was planned, taken at a worse location,
> for emotional reasons.

> "Let us see if we come back down. That is the only time I look for a re-entry."

> Price has to come back to the level. Not near it, and not on a different level that looks similar.
> If it does not return, there is no trade, and the loss just stands.

> This is also why the two stops in a row did not turn into four. The level was not offering
> anything, so there was nothing to take, and the next trade waited until price came back.

## M-96 · The −4R daily stop

**Verbatim** — `refill-effect.pdf` p.20:

> The single most powerful rule we found has nothing to do with the entry: stop trading for the day
> once you are down four risk units. A trailing-drawdown evaluation is asymmetric: one runaway
> losing day ends the account, while no single good day is worth the same in reverse. Cutting the
> tail of bad days off is worth about fourteen points of pass rate at every size we tested.

## M-97 · Daily objective, max loss, and sizing

**Verbatim** — `anatomy-of-a-losing-start.pdf` p.11:

> One contract. Size goes up when the account buffer grows, not when confidence does. Two contracts
> only on the highest quality level, and only with a trailing plan attached.
>
> A daily objective, then stop. Around $500 on the account. Once it is reached the session is over,
> including on days when the read is still good and the market is still moving.
>
> A maximum loss at half the objective. The bad day is capped smaller than the good day.

> "The winning day is keeping the account alive. What is the point of making money on a certain day
> if the next day you are going to blow it?"

## M-98 · Scale by accounts, not by size

**Verbatim** — `refill-effect.pdf` p.20:

> Passing is only half the economics. The payout on a funded account is structurally capped near
> $2,000 per cycle by the same trailing drawdown, and no edge, however large, lifts that ceiling.
> The lever for total income is not size, it is count: run several funded accounts in parallel and
> the chance that at least one reaches a payout climbs fast.

## M-99 · The prop-maths argument against high R:R skew

**Verbatim** — `only-trade-big-trades.pdf` p.17:

> Traders on prop accounts gravitate to high reward to risk setups because the arithmetic looks
> efficient. His position is that the skew defeats the purpose. An evaluation is not asking you to
> produce a large return from a small number of trades. It is asking you to reach a profit target
> without breaching a drawdown limit, which rewards a higher win rate and steady participation.
>
> He puts the failure case plainly. You can take ten of the rare setups, have all ten lose, and only
> get back to level if you win the eleventh. That is a survivable model with a long runway and a
> forgiving account. It is not a survivable model on an evaluation with a trailing drawdown.
>
> Which leads to the framing he closes on: trade a framework, not a strategy. A strategy is a single
> pattern, and a single pattern only fits one regime, so it leaves you either forcing trades or
> sitting out most of the month. A framework carries rules for both environments, which is the only
> way the 80 percent case and the rare case both have an answer.

**Note the internal tension**: M-99 argues AGAINST high R:R skew, while M-93/M-94 in
`anatomy-of-a-losing-start.pdf` celebrate 5.37:1 and 14.07:1. The reconciliation the corpus offers
is M-94's ordering rule (the ratio is an output of structure, never an input) plus M-97's
daily-objective cap. Both are censused separately.

## M-100 · Session discipline / thesis without direction

**Verbatim** — `anatomy-of-a-losing-start.pdf` p.4:

> Before the session there is a written thesis. What it does not contain is a direction. The first
> paragraph only describes what price has already done, what it is doing now, and why.
>
> That sounds like a small distinction. It is the whole thing. If the thesis says up, then every
> level that fails becomes an argument to try again. If the thesis says here are the areas where
> reactions are likely, then a level failing is just information.

> "You will never have a bias in your thesis. You just want areas of reactions. You want support
> here, you want resistance here, and you play based off of that."

**The full session checklist, verbatim** (p.10):

> BEFORE THE SESSION
> - Thesis written. What price has done, what it is doing, and why. No direction stated.
> - Areas marked. Where reactions are likely on both sides, not just the side you prefer.
> - Objective named. The higher timeframe level that is actually owed something.
> - Failure named. What would have to happen for the objective to be wrong.
>
> BEFORE THE ENTRY
> - Price is at a marked area. Not near one, and not a different one that looks similar.
> - Something is holding. Aggression arriving and the level not giving way.
> - Stop location decided first. Just past the level, where the reason for the trade is gone.
> - Ratio checked, not chosen. The objective is where it is. If the ratio is poor, skip it.
>
> IN THE TRADE
> - Move to break even when the reason weakens. Not at a fixed number of ticks.
> - Trail behind protected levels. Swings the market has already defended once.
> - Cut fast when wrong. The loss being small is the entire reason the model works.
>
> AFTER
> - Re-entry only if price returns to the level. Otherwise the trade is finished.
> - Daily objective reached, stop. Consistency rules apply even when the read is still good.

**The session shape it produced, verbatim** (p.5):

> Nine trades. Four winners, five losers. The account finished the session up about $500 [...]
> The first four trades put it about $480 underwater before a single winner landed.

> A 44% win rate is not a typo and it is not a bad session. It is what the model looks like when it
> is working correctly. The losers are supposed to be frequent. They are supposed to be small.

## M-101 · Trade only marked levels

**Verbatim** — `10k-first-month.pdf` p.14:

> Asked directly what he'd focus on in his first month if he joined again tomorrow, his answer
> wasn't a concept, it was a habit: trading only off marked levels, not in the middle of the range
> because a chart looks interesting there.

> HIS OWN CHECKLIST, AS HE DESCRIBED USING IT NOW — What the market is doing right now. What the
> market wants to do. Where his levels actually are. Where he should trade off them.

## M-102 · The full Big Trades checklist (verbatim, `only-trade-big-trades.pdf` p.18)

> BEFORE YOU READ A SINGLE BUBBLE
> - I know whether the market is in balance or out of it, and which gamma environment I am in.
> - My aggression threshold is set for the instrument I am trading, not copied from another one.
> - I am treating aggression as effort, and checking price for whether it was rewarded.
>
> READING THE PRINT
> - Inside the body means rewarded. On the wick means absorbed. I have made that call consciously.
> - If both sides are being absorbed, nobody is in control yet and I am waiting for the break.
> - An imbalance only interests me where it sits at the same price as aggression.
>
> THE ORIGIN OF THE MOVE TRADE, SHORT GAMMA ONLY
> - I can point to repeated effort that got no reward, not just one failed candle.
> - I am entering the drive, not the point where the squeeze failed.
> - Price has taken out the wicks above, and the refill area below held.
> - I am on the retest, and if there is no retest I let the trade go.
> - The higher timeframe agrees: balance left, thin volume behind me, a level that should reject.
> - CVD is not sitting against me on the timeframe I am entering from.
>
> THE BALANCE DAY TRADE, THE OTHER 80 PERCENT
> - An extreme, with the aggression there having failed to get paid.
> - I am entering the test back into that area, targeting where the other side last had control.
> - I am not waiting for a squeeze, because a balanced market has no reason to give me one.
>
> BEFORE I SIZE IT
> - Is my side actually being rewarded, or is this move entirely passive?
> - Does this reward to risk fit the account I am on, or am I chasing a number that will not pay out?

## M-103 · The GEX session checklist (verbatim, `gex-framework.pdf` p.19)

> - Read the regime first. Before you look at a single setup, pull QQQ 0DTE and read the gamma
>   regime and where the flip sits.
> - Above or below the flip. Above the flip is range and mean reversion. Below it is trend and
>   expansion.
> - Short gamma, trade the trend. Higher R, continuation and breakout setups, target the expansion
>   and take fewer trades.
> - Long gamma, trade the chop. Smaller R, fade the extremes back toward the walls, scalp the
>   rotations and skip the breakout chases.
> - Confirm with orderflow. Never act on a GEX level on its own. Confirm with the DOM and the
>   footprint first. GEX is the context, the tape is the trigger.
> - Re-check after big moves.

## M-104 · The AMT checklist (verbatim, `mastering-amt-vp.pdf` p.26)

> BEFORE YOU TRADE A BREAK
> - I know whether price is inside balance or has already broken it.
> - I'm not using VAH or VAL as a fixed level, they move as volume prints.
> - I know today's day type isn't decided yet, and that's fine, a D day is a real outcome.
>
> BEFORE THE OPEN
> - I've checked whether the market is net long or net short overnight.
> - I've checked whether the LVN or shelf is being respected or disrespected.
>
> USING THE STATS
> - I'm using these as targeting context, not as the whole edge on their own.
> - I know which contract and instrument a stat was actually measured on before I apply it.

---

# INDEX — every named mechanic, with its census disposition

Census verdicts live in `provenance/port_m2/CREATOR_MECHANICS_CENSUS.md`. Detectors that could not
be built on MBP-1 are marked NOT-COMPUTABLE with the reason.

| ID | name | cite | detector? |
|----|------|------|-----------|
| M-01 | Aggression / Big-Trades print (30–60 lots NQ) | otm p.4, ottbt p.3 | YES — exact (MBP-1 aggressor-signed prints) |
| M-02 | Absorption | otm p.2, aolst p.3 | YES — approximation (L1 only) |
| M-03 | Effort vs result | otm p.2, ottbt p.4 | YES — exact |
| M-04 | Body vs wick placement | otm p.4, ottbt p.6 | YES — exact |
| M-05 | Aggression testing | otm p.2/p.4 | YES — exact |
| M-06 | Aggression memory / level memory | otm p.2/p.4 | YES — exact |
| M-07 | Speed of tape | otm p.2, aolst p.3 | YES — exact |
| M-08 | Cumulative delta (CVD) + median | aolst p.3, ottbt p.12 | YES — exact |
| M-09 | Refill (resting size reappearing) | aolst p.3, re p.4/p.10 | PARTIAL — L1 only |
| M-10 | Dealing range | aolst p.3 | YES |
| M-11 | Minor HVN / LVN / thin-volume-below | aolst p.3, ottbt p.10 | YES |
| M-12 | Protected high / low | aolst p.3 | YES |
| M-13 | Zone | re p.2/p.5 | YES — exact |
| M-14 | Touch | re p.2/p.5 | YES — exact |
| M-20 | The squeeze | otm p.5, ottbt p.6 | YES — exact |
| M-21 | Squeeze catalyst (lowest/highest first aggression) | otm p.2/p.8 | YES — exact |
| M-22 | Refill clock (worse-price reload) | otm p.5 | YES — exact |
| M-23 | OFM (re-squeeze after failure) | otm p.6 | YES — exact |
| M-24 | OFM correction: enter the drive, wicks taken out | ottbt p.7–8 | YES — exact |
| M-25 | Retest over break / prefiring | ottbt p.9 | YES — exact |
| M-26 | Refill area below | ottbt p.8 | YES |
| M-27 | 350% imbalance line at aggression price | ottbt p.5 | YES — exact |
| M-28 | 350% divergence box | 2345 p.5 | YES — exact |
| M-29 | Passive-move trap / ordered two-stage | ottbt p.13 | YES — exact |
| M-30 | Both sides absorbed → wait for break | ottbt p.4 | YES |
| M-31 | Balance-day fade (failure of aggression) | ottbt p.15 | YES |
| M-32 | Aggression into a balanced session | ottbt p.16 | YES |
| M-33 | Failed Auction setup (narrow) | amt p.9–11 | YES |
| M-34 | Three balance entries | amt p.12 | YES |
| M-35 | Level + minor-HVN confluence | 10k p.7 | YES |
| M-36 | Second tap with absorption | 10k p.8 | YES |
| M-37 | The refill trade | nyam p.4 | YES (= M-31 mirror) |
| M-38 | Third-test short (published loss) | nyam p.6 | YES — negative control |
| M-39 | Losing-steam fade | nyam p.10 | YES |
| M-40 | Microbalance push-through | 2345 p.7 | YES |
| M-41 | Extreme-absorption CVD read (price↑ CVD↓) | 2345 p.6 | YES — exact |
| M-42 | Repeated failure to reclaim | 2345 p.4 | YES |
| M-50 | Gamma gate (short gamma only) | ottbt p.14 | NO — no options data (D-047 free-data) |
| M-51 | Long vs short gamma | gex p.6 | NO — proxied by realized-vol regime |
| M-52 | Gamma flip | gex p.7 | NO |
| M-53 | Call/put wall, max pain | gex p.13 | NO |
| M-54 | Pinning vs gamma squeeze | gex p.12 | NO (proxy only) |
| M-55 | Confirm GEX level with orderflow | gex p.18 | PARTIAL — the orderflow half is computable |
| M-56 | Vanna / charm | gex p.17 | NO |
| M-57 | AMT three rules / POC-VAH-VAL | amt p.4–5 | YES |
| M-58 | Day types P/B/D | amt p.7–8 | YES |
| M-59 | Overnight inventory + ON LVN/shelf | amt p.14 | YES |
| M-60 | HTF leniency / thesis-first | amt p.13, otm p.3 | YES |
| M-70 | 94% ONH-or-ONL touch | amt p.15 | YES — direct replication |
| M-71 | 73% MPOC pull | amt p.16 | YES — direct replication |
| M-72 | The real 80% rule | amt p.18 | YES — direct replication |
| M-73 | IB range extension 65–75% | amt p.19 | YES — direct replication |
| M-74 | Gap-fill statistics | amt p.19 | YES — direct replication |
| M-75 | ES probability appendix | amt p.20–25 | YES — full table replication |
| M-80 | 42% hold / −0.285R baseline | re p.8 | YES — direct replication |
| M-81 | Four feature families | re p.8 | YES — feature spec |
| M-82 | Selection AUC 0.63; flow-alone 0.54 | re p.9 | YES — direct replication |
| M-83 | 18-tick dip | re p.10 | YES — direct replication |
| M-84 | Resting limit vs market order | re p.11 | PARTIAL — queue model needed |
| M-85 | Deployed config (12/32/96/30min) | re p.12 | YES — replay |
| M-86 | First touch weakest / second test | otm p.16 | YES |
| M-87 | Regime dependence / losing quarter | re p.14 | YES — era census |
| M-88 | No mechanical entry (creator's null) | otm p.18 | CALIBRATION — not a detector |
| M-90 | Trailing convexity | otm p.13, nyam p.8–9 | YES — exit class (user-reserved for adoption) |
| M-91 | Trail behind protected structure | aolst p.10, 2345 p.7 | YES — exit class |
| M-92 | Absorption exit | otm p.9 | YES — exit class |
| M-93 | Stop where the idea is wrong | aolst p.8 | YES |
| M-94 | Ratio checked, not chosen | aolst p.9 | YES |
| M-95 | Re-entry only on return to level | aolst p.7 | YES |
| M-96 | −4R daily stop | re p.20 | YES — session class |
| M-97 | Daily objective / max loss half | aolst p.11 | YES — session class |
| M-98 | Scale by accounts not size | re p.20 | N/A — account policy |
| M-99 | Prop maths vs high R:R skew | ottbt p.17 | YES — economics |
| M-100 | Thesis without direction + session checklist | aolst p.4/p.10 | PROCESS |
| M-101 | Trade only marked levels | 10k p.14 | YES |
| M-102 | Big Trades checklist | ottbt p.18 | COMPOSITE |
| M-103 | GEX session checklist | gex p.19 | COMPOSITE (gated by M-50) |
| M-104 | AMT checklist | amt p.26 | COMPOSITE |

File keys: `re` = refill-effect, `otm` = origin-of-the-move, `ottbt` = only-trade-big-trades,
`amt` = mastering-amt-vp, `gex` = gex-framework, `nyam` = ny-am-session,
`aolst` = anatomy-of-a-losing-start, `2345` = 2345-funded-session, `10k` = 10k-first-month.

**COUNT: 78 named mechanics extracted** (14 primitives M-01..M-14, 23 named setups M-20..M-42,
11 regime/context filters M-50..M-60, 6 published if-then statistic families M-70..M-75,
9 research-paper measurements M-80..M-88, 15 management/session/economics rules M-90..M-104).

Disposition: **66 computable** on MBP-1 + our level ledger (3 of them partial/approximate —
M-09 refill, M-55 orderflow half, M-84 queue model); **6 not computable** without options data
we do not hold (M-50, M-51, M-52, M-53, M-54, M-56 — D-047 authorized free data only, options
chains were never acquired); **6 process/economics/composite** rather than detectors
(M-88 calibration, M-98 account policy, M-100 process, M-102/103/104 composite checklists).

# Opus 5 opinion: the discretionary confirmation sequence

2026-08-22. Subagent lane. Read-only on the repo except this file.

## How this was produced, and what is missing

I was told to vision-read every page of all 30 PDFs. **I read zero pages as images.**
The Read tool refuses every PDF in this container with `pdftoppm is not installed.
Install poppler-utils`, and Bash here is locked to a narrow read-only allowlist, so I
could not install poppler, call a Python renderer, or extract embedded images. I
confirmed the failure on two different files (`reading-delta.pdf` pages 1-20,
`whos-in-control.pdf` pages 1-5) and confirmed no pre-rendered page cache exists under
`artifacts/`.

What I used instead: the five page-anchored lane digests in this directory, written by
the 2026-08-22 blind lanes that did render all 389 pages, plus
`reread_notes/reading-delta.md`, plus the full text layer at
`artifacts/reference/discretionary_20260819/text/`. **Every figure detail below is
second-hand from those lanes.** I have not verified a single arrow, bubble, or
handwritten mark with my own eyes. Treat the figure citations as "lane X recorded this
at (pdf, page)", not as my observation. Terminal state is in section 6.

What I did verify myself, first-hand, and it changes the answer: the real feature list
in `artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix/manifest.json`,
and the actual implementation in `tools/probe_confirmation_accrual.py` and
`tools/probe_retest_rule.py`. Section 3 and section 4 rest on those reads, not on the
digests.

---

## 1. Verdict

Confirmation in these PDFs is not a set of tells you can weigh. It is a **state machine
over one level, with an order, and the entry is licensed by the level surviving the
machine twice.**

The single sentence that organizes all 30 files is from `stop-re-entering.pdf` p10:
"failed absorption and confirmed absorption look identical at the moment most people
enter. The difference only exists in time." Every author in this set says a version of
it. The information is in the ordering and the delay between stages, not in any snapshot.

Three properties of the machine matter more than any individual predicate:

**The order carries the meaning, not the stages.** Replenishment before a defense
happened is noise. Opposite-side aggression before the attacker exhausted is a swing, not
a start (`only-trade-big-trades (1).pdf` p13: "First the opposition's aggression fails,
so they are exhausted, trapped or absorbed. Then your side arrives aggressively.
Opposition failing on its own is only half of it, and half is what most people trade").
An average over stage scores destroys exactly the thing being taught.

**The entry is on the second visit, never the first.** This is the most consistent rule
in the corpus and it appears in every one of the five lanes independently.
`18k-payout-session.pdf` p7: "A level does not become the trade because price touched it.
It becomes the trade when the same side defends it a second time, with more conviction
than the first." `your-mistakes-with-absorption (1).pdf` p13: "I'm entering on the retest
of the reward system, not on the wall itself." `trapped-buyers-one-retest.pdf` p6 calls
it "two waits, planned in advance," and says the entry existed only because the market
gave the second wait. `refill-effect (1).pdf` p7 shows a level tested twice, sellers
getting nothing both times, and control changing only after the second test. The book's
own measured version is blunt: fading every first touch is -0.285R with a 42% hold rate
(`refill-effect (1).pdf` p8).

**The clock is event-indexed, not wall-clock.** Nothing in this corpus is denominated in
seconds. It is denominated in the nth refresh (`18k-payout-session.pdf` p11: read the
2nd and 3rd refresh), the second test, the next candle close, ticks past the level, and
"price came back." The one hard clock anywhere is a 30-minute cancel on an unfilled
resting order (`refill-effect (1).pdf` p12). The user's 5-minute upper-bound guess is
inside the observed band and the corpus supports confirmation arriving much later:
`18k-payout-session.pdf` p7-9 has the qualifying retest on the third attempt, roughly ten
minutes after the first touch, with the first two rejected on camera for arriving without
participation.

The consequence for us. We built a bag of independent scores sampled on a fixed Δ grid.
The book teaches an ordered machine sampled at transitions. Those are not the same object,
and averaging cannot approximate ordering. That is a specific, fixable mistake, and I
think it is a better explanation of the AUC 0.60 wall than "the features are weak."

---

## 2. The stage machine

Notation: S0 is a precondition that must already be true. S1 through S6 are stages that
must occur in order at the same level. "The level" is a 2 to 3 tick band, never one price
(`dom-lesson-6.pdf` p4: "300 buy orders can get eaten across 3 ticks. Watch the zone, not
just the single tick").

### S0. Precondition: location, memory, thesis, arrival. Not a wait.

Must be true before any print at the level means anything.

- **Real fixed extreme.** Shelf, ledge, LVN, minor volume node, prior-day VAH/VAL, ON
  extreme. Never at or near POC, never mid-balance.
  `your-mistakes-with-absorption (1).pdf` p13 checklist. `vp-lesson-2.pdf` p7: "Trade the
  ledge, not the middle of the shelf. Inside the shelf is rotation, chop and noise."
  `code-3-orderflow.pdf` p6. `fp-lesson-8.pdf` p8: "A number without a location is
  trivia." `dom-lesson-6.pdf` p8: "Absorption at a random price means nothing."
  *Figure-only (ABS p6):* the page draws identical swing-reversal shapes sitting inside
  value and hand-labels them "THIS IS NOT ABS", the only difference being location.
- **Memory.** Has this zone been defended before, today or yesterday.
  `origin-of-the-move (1).pdf` p16: "A big print with no history and no location is not a
  graded setup yet." The measured backing is the strongest empirical claim in the corpus:
  across 41,152 zone touches, raw order flow into the touch scores AUC 0.54, and memory
  plus location carry the signal to 0.63 (`refill-effect (1).pdf` p9).
- **Thesis and day type.** `amt-lesson-1.pdf` p12: "No DOM or footprint confirmation, no
  trade. AMT gives the where, never the when." p10: "Most blown accounts are a day type
  error." `origin-of-the-move (1).pdf` p3: the whole feature set without the thesis is
  "basically a coin flip."
- **Arrival speed.** `whos-in-control.pdf` p4: "Reached aggressively, it's a level to
  expect defended. Reached slowly, it's a level to expect broken." A slow grind into the
  extreme kills the fade before S1.

**Invalidates:** at or near POC, inside balance, trend day, no thesis, slow-grind
arrival, LTF signal against the HTF balance side (`mastering-amt-vp (1).pdf` p13).

### S1. Effort arrives at the level and is not paid.

Aggression hits, price does not go. This is the candidate-forming event, and the corpus is
unanimous that it is **not** confirmation.

`stop-re-entering.pdf` p10, stage 1: initial defense "can be temporary liquidity that gets
pulled and stops you instantly." `18k-payout-session.pdf` p11: "a single absorption print
is never enough to act on by itself." `dom-lesson-6.pdf` p3: "Big market orders hitting
your level that do not push price through it."

There is a discriminator inside S1 that our catalog treated as two separate positive
tells. `dom-lesson-6.pdf` p7: "Big volume with no movement is absorption, someone is
there. Shrinking volume with no movement is exhaustion, nobody is left. Absorption
reverses harder, exhaustion drifts." Both produce near-zero displacement. Only one
licenses a reversal. The quiet variant is licensed separately and only later in the
sequence (`origin-of-the-move (1).pdf` p14: tape speed dies at the failure, "the absence
of result is itself the signal").

**Invalidates:** the effort gets rewarded. `dom-lesson-5.pdf` p7: aggression with movement
is continuation, not absorption. `your-mistakes-with-absorption (1).pdf` p8: if price
holds the push, the whole read is void.

### S2. The defense replenishes while it is still being hit, and prints trade through it.

The first real wait. The level refreshes, maintained or growing, as it keeps getting hit.

`stop-re-entering.pdf` p10, stage 2, with the book's own minimum: "My minimum filter is
three ticks of replenishment; one or two is the classic fake-out zone."
`18k-payout-session.pdf` p11 gives the trend form, which is better: one refresh tells you
nothing, the read is on the 2nd and 3rd. Real is "hit, replaced, hit, replaced" at steady
size and steady pace. A bluff is each refresh a little smaller with the pacing stretching
out, until it stops coming back.

The sharpest rule in the whole corpus is the conditioning, `dom-lesson-7.pdf` p7: "an
iceberg REPLENISHES as it trades, a spoof VANISHES before it trades. Reload is real,
cancel is fake." Real hidden size refreshes **as volume trades through it, and you see the
prints**. Fake size refreshes or vanishes with no prints at all. That is a ratio, not a
count.

*Figure-only (dom-6 p6):* the lane recorded the defended bid row drawn two to three times
wider than its neighbors and staying widest across the whole event, while aggressive
sellers hit it.

**Invalidates:** 1 to 2 tick replenishment. Refresh sizes shrinking and intervals
stretching. Refresh with no prints behind it. The stack pulling together as price
approaches (`dom-lesson-7.pdf` p7, layering). Spread widening, which
`dom-lesson-5.pdf` p6 reads as liquidity pulling: do not lean on the level, do not chase
into the gap.

### S3. The attacker decays.

Attack rate and size fall bar over bar, and delta turns against them.
`stop-re-entering.pdf` p10, stage 3.

The concrete form is the digit read, `stop-re-entering.pdf` p12: sellers' double-digit
prints thin to singles while buyers answer with triples. `average-unprofitable-trader.pdf`
p26 gives the same read as the DOM's third step, after location and pacing, and says the
entry is the moment "the pacing then upticks, effort finally getting its reward."

*Figure-only (ny-am p10):* speed-of-tape bars shrink bar by bar into the level. The lane
noted the text only gestures at this and the figure makes it the tell.

**Invalidates:** attacker intensity holds or grows.

### S4. The other side arrives aggressively.

Not the absence of the first side. Actual opposite-side aggression.

`your-mistakes-with-absorption (1).pdf` p13: "A second, opposite aggression has shown up,
not just an absence of the first side." `stop-re-entering.pdf` p12: "Passive absorption
is the setup; aggression is the trigger." `only-trade-big-trades (1).pdf` p13 makes the
ordering explicit and calls trading half of it the common error.

**Invalidates:** the move in your favour is entirely passive. `only-trade-big-trades (1).pdf`
p13 calls those "normally short term swings rather than the start of anything."

### S5. The reward lands immediately, and it is small.

The corpus's only numeric threshold, and it is a distance, not a duration.

`your-mistakes-with-absorption (1).pdf` p3-4 and `average-unprofitable-trader.pdf` p24:
three ticks of aggression toward the absorbed side, or the absorption fails about 27% of
the time. `stop-re-entering.pdf` p12: two upticks minimum, two to four. The strictness is
in the lateness, p13-14: entry must sit within a tick or two of the confirmation, and "A
delayed reward system means probably no reward system." The dissected losing entry sat six
to eight ticks above the absorption.

**Invalidates:** no reward, or a late one.

### S6. Price returns, and the same side defends again. This is the entry.

The stage we never implemented, and the one the figures are unanimous about.

`your-mistakes-with-absorption (1).pdf` p9: "wait for one more retest with a decent amount
of refresh orders in time and sales, visible on the DOM or the footprint too, before
taking the trade." `18k-payout-session.pdf` p7, quoted in section 1. `whos-in-control.pdf`
p5: "A short only becomes valid once price breaks that low, comes back up for a genuine
retest, and then continues lower from there, that sequence is what confirms sellers are
still in control, not the break by itself." `only-trade-big-trades (1).pdf` p9: entering
early is "prefiring the trade, firing on the expectation of confirmation rather than the
confirmation." `average-unprofitable-trader.pdf` p21: if the buyers who broke the level
fold on the retest, "you have your answer, and it cost nothing."

Two mechanical facts sit inside S6 and both are entry-side.

First, **the defense happens inside the zone, not at its front edge**
(`refill-effect (1).pdf` p10). The median eventual winner first dips **18 ticks past the
touch** before it works (p10, p23). Acting the instant price tags the level is, in
`origin-of-the-move (1).pdf` p15's words, "acting at the exact point where the data says
the trade has not started yet."

Second, the same signals with a resting entry inside the zone versus a market order at
the touch: 68.8% win / PF 1.80 / +$2,112 against 27.2% / PF 0.81 / -$405
(`refill-effect (1).pdf` p11). The resting version takes 64 trades against 312 "precisely
because it demands the flush that defines the setup." I am naming this because it is a
fact about when the entry is licensed, not proposing a change to our fill model. That
would need a user ruling and is outside this lane.

**Invalidates:** the retest arrives without participation, so let it go
(`18k-payout-session.pdf` p7, twice on camera). No retest ever arrives, so accept the miss
(`only-trade-big-trades (1).pdf` p9, p18). Price re-accepts through the level, so flip the
read instead of forcing it (`whos-in-control.pdf` p5, p11).

### How long the machine takes

Fastest end: ladder absorption is read live during the attack, seconds
(`dom-lesson-6.pdf` p4). Middle: footprint proof lands on candle close, and the lane
recorded the reversal three to four one-minute candles after the first disagreement
(`fp-lesson-9.pdf` p3). Slow end: the qualifying retest on the third attempt, ten-plus
minutes (`18k-payout-session.pdf` p7-9); a resting order live for 30 minutes
(`refill-effect (1).pdf` p12); session-scale CVD absorption running tens of minutes to
hours (`2345-funded-session (1).pdf` p6).

So the wait is bounded by an event, not a clock, and 300 seconds sits in the middle of the
distribution rather than at its top.

### Figure-only details, as recorded by the vision lanes

All second-hand. Counted: 16.

1. `reading-delta.pdf` p4. Purple arrow at a fat delta node at the low. Green curve
   tracing the hold-and-go. Red dashed SL line through the node. An X at the failed seller
   defense under the low. ENTRY on a white dashed line placed after the low is in, not at
   the low. Top-right stamp: "ONLY DO THIS METHOD WITH CONFIRMED LOWS / FINISHED
   AUCTIONS".
2. `reading-delta.pdf` p7. Purple arrow into the candle cluster at the highs. White
   snaking line running from a green buy bubble across to a sell-side delta peak on the
   right-hand profile. The short ticket sits **on** the highest sell-delta row. Stop and
   target are drawn on profile nodes, not at fixed tick distances.
3. `reading-delta.pdf` p9 and cover. White rectangle around the low-volume node, red
   circle on the pink delta bubble at the box's left edge.
4. `your-mistakes-with-absorption (1).pdf` p4. Three synchronized panes: price with a red
   level box, a T&S strip flipping from red prints to green, and a CVD pane with a rising
   median. Green circles mark **both** the first touch and the later retest.
5. `your-mistakes-with-absorption (1).pdf` p6. Identical swing-reversal shapes inside
   value, hand-labeled "THIS IS NOT ABS" purely on location.
6. `your-mistakes-with-absorption (1).pdf` p11. Delta-profile spikes sitting exactly on
   the VAH/VAL rows, annotated "High delta spike of buyers (Opposition losing control)
   being abs passively by sellers".
7. `origin-of-the-move (1).pdf` p5. The catalyst boxed around three-plus absorbed buy
   circles. Entry marked at the reload point, annotated "Protected by buyers (covered)".
   Handwritten: "REFILL clock: AGGRESSIVE (NO RESULT) to AGGRESSIVE (WITH RESULT)".
8. `origin-of-the-move (1).pdf` p6. Two entries marked with different risk classes, an
   early refill entry and the main re-squeeze entry, on the same candidate.
9. `trapped-buyers-one-retest.pdf` p4. Blue buy-volume bars concentrated exactly at the
   recent high on the daily volume profile with delta.
10. `refill-effect (1).pdf` p7. The level tested twice, sellers getting nothing both
    times, and the green base forming **above** the zone after the second test, with entry
    on the resumption rather than at the zone edge.
11. `refill-effect (1).pdf` p10. Order-book schematic of wall, then flush, then refill,
    with the defense drawn inside the zone rather than at its front edge.
12. `only-trade-big-trades (1).pdf` p7-8. The OFM level drawn at the **top** of the
    squeeze cluster. The green target box starting only above the taken-out wicks. CVD
    curling up from below its median **before** the retest entry.
13. `dom-lesson-6.pdf` p6. The defended bid row drawn two to three times wider than its
    neighbors and staying widest across the event while sellers hit it.
14. `fp-lesson-9.pdf` p3. One-minute footprint columns with per-candle delta footers of
    -496, -550, -674 on candles whose bodies hold or rise at the low. Three consecutive
    disagreeing candles before the reversal leg, spanning 14:39 to 14:47, with the
    imbalance highlights clustered at the candle extremes.
15. `fp-lesson-9.pdf` p5. Two ladders side by side. The left has its brightest row second
    from the bottom, the right has it second from the top. The POC flip crosses most of
    the candle range, not one tick.
16. `mastering-amt-vp (1).pdf` p10-11. A dashed line drawn from the prior balance's POC
    with the entry arrow at the tag, while red dotted boxes elsewhere mark generic failed
    auctions that are **not** the setup. The p11 quiz chart looks identical, a break plus a
    retest of a grey zone, but never tags a prior balance, so it is the opposite trade.

Four more worth having: `ny-am-session (1).pdf` p4, two small circles on the exact prints
where buyers stepped in and held, with the speed-of-tape histogram turning green as the
refill starts and the stop drawn just below the circles. `ny-am-session (1).pdf` p10,
speed-of-tape bars shrinking bar by bar into the level. `2345-funded-session (1).pdf` p6,
a CVD panel grinding down for the whole session under flat-to-rising price, annotated
"price rising = high conviction of that session sellers had insane control".
`fp-lesson-9.pdf` p4, the entry arrow at the **close** of the disagreement candle at the
bottom-right of the trapped cluster, not at the level touch.

The lanes noted one pattern across all of them, and I think it is the single most useful
figure-derived claim in this document: **entry arrows in every figure sit at the retest
after the confirming aggression, never at the wall or the level itself.** The prose
under-states this. The drawings are unanimous.

---

## 3. What we failed to implement

Specific, against `CONFIRMATION_CATALOG.md` and the code that ran.

**3.1 The catalog demoted the machine to one predicate among fourteen.** Part A lists
`CONF-4STAGE` as bullet three of fourteen, beside `CONF-REWARD-3T`, `CONF-REPLENISH`,
`CONF-OPP-EXHAUST` and the rest. But `CONF-REPLENISH`, `CONF-OPP-EXHAUST`,
`CONF-OPP-AGGRESSION` and `CONF-REWARD-3T` **are** the stages of `CONF-4STAGE`. Listing a
container beside its own contents guarantees the harness in Part D scores them
independently and then compares them, which is the one thing the source material says
cannot work.

**3.2 The implementation averaged the stages at one instant.**
`tools/probe_confirmation_accrual.py:46-74` defines DEFENSE, REPLENISH, EXHAUST and
LIFTOFF as four z-mean scores over ingredient lists. Line 169:

```python
out["COMBINED"] = np.nanmean(np.vstack([out[s] for s in out]), axis=0)
```

An equal-weight mean over four stages read at the same second. A candidate with high
LIFTOFF and no DEFENSE scores identically to one that ran the real order. There is no
term anywhere in that file for "REPLENISH only counts if DEFENSE already happened and is
still true," and no term for the gap between stages. The book's entire claim is that the
difference "only exists in time," and the code has no time in it.

**3.3 We had the ordering columns and never used them.** The frozen matrix carries
`disc_state_adverse_seen`, `disc_state_reclaim_seen`, `disc_state_lift_seen`,
`disc_state_retest_seen`, `disc_state_invalidated_seen`, and a matching `_age_sec` for
each. That is a transition log. Differencing two ages gives inter-stage dwell, and
comparing ages gives order. `SCORE_DEFS_V2["PROGRESS2"]` used
`disc_state_current_displacement_ticks`, `disc_state_favorable_max_ticks` and the two
yield columns, and not one `_seen` or `_age_sec` column. We built a state machine into the
feature layer and then never asked it what order things happened in.

**3.4 The second-defense stage was tested as price geometry, not as defense.**
`tools/probe_retest_rule.py:6-13` defines a qualifying re-test as: the running most
extended candidate is above a train quantile, the new candidate forms at least T minutes
later, and its extension sits within eps dollars of the running max. Nothing in that rule
requires that the level was defended on the first visit, or that the defense recurred, or
that it recurred with more conviction. `18k-payout-session.pdf` p7 says the defense
recurring **with more conviction than the first time** is the trade. Those observables
exist: `disc_test_response_h5_defense_rate`,
`disc_test_response_h5_favorable_slope_ticks`, `disc_test_response_h5_favorable_first_ticks`
against `_favorable_last_ticks`, plus `disc_memory_z*_defense_reload_count/_size`. None
appear in that probe. So the negative result correctly closes "re-test of a held price
extreme at these grids." It does not touch "second defense," which was never tested.

**3.5 The prints conditioning was never formed.** `dom-lesson-7.pdf` p7's discriminator
is refills divided by traded volume at the same price. In `SCORE_DEFS_V2["REPLENISH2"]`,
`disc_quote_*_rebuild_size` and `disc_quote_*_depletion_size` both carry sign `+1` and get
averaged together. Turnover on both sides of the ledger adds up instead of cancelling, so
an iceberg and a spoof land in the same place. The ratio needs no new data:
`disc_quote_formation_rebuild_size` over `disc_level_z0_trade_volume` is two columns we
already have.

**3.6 Absorption and exhaustion were listed as two positive tells.** The catalog has
`CONF-OPP-EXHAUST` and `CONF-TAPE-DEATH` as separate confirmations.
`dom-lesson-6.pdf` p7 says shrinking volume with no movement means nobody is left and
"exhaustion drifts," which is not a licensed reversal on its own. We turned a
discriminator into two more things to add up.

**3.7 The Δ grid is the wrong clock.** Part D fixes offsets at {0, 30, 60, 120, 180, 300}
seconds. The corpus indexes on the nth refresh, the second test, the candle close, and
ticks past the level. A fixed Δ samples the machine at whatever stage it happens to be in,
which across a population averages the stages together a second time, after the score
already averaged them once.

**3.8 One thing the catalog got right and we should keep.** Part B's closing line, that
none of these worked as formation-second discriminators and their value should live in the
accrual, is correct and is consistent with everything above. The mistake was measuring the
accrual of a scalar instead of the progress of a machine.

---

## 4. Observables we have, and the gaps that survive

I checked these against the matrix manifest rather than trusting the digests, and the
catalog's gap list is wrong in three places. That matters, because two of those "gaps"
were tickets.

### Already present (verified in the manifest)

| Stage | Columns |
|---|---|
| S0 location | `disc_auction_session_{poc,val,vah}_aligned_usd`, `_inside_value`, `_nearest_hvn_aligned_usd`, `_nearest_lvn_aligned_usd`, `_low/high_excess_score`, `_low/high_poor_score`, `_mode_count`, `_profile_skewness`, `_directional_acceptance_score`, `disc_ib_*` |
| S0 memory | `disc_prior_level_z{0,2,4}_untouched`, `_reaction_30_defense_rate`, `_reaction_120_defense_rate`, `disc_memory_z{0,2,4}_net_defense_display`, `_defense_reload_count/_size`, `_defense_pull_no_fill`, `_signed_control_fraction`, `_last_attack_age_sec` |
| S0 arrival speed | `w{60,300,600}_aligned_displacement_usd`, `w*_path_efficiency`, `disc_tclock_n*_gap_median_ms` |
| S1 unpaid effort | `w*_opposing_absorption`, `w*_price_per_aligned_volume`, `disc_state_price_yield_per_attack`, `disc_state_price_yield_per_net_aggression` |
| S1 absorption vs exhaustion | `disc_evt_h{1..300}_attack_peak_100ms/250ms` across horizons gives the volume-holding vs volume-shrinking split |
| S2 replenishment | `disc_quote_{formation,h30,h120}_rebuild_size/_count/_rate_per_sec`, `_rebuild_after_depletion_mean_latency_ms`, `disc_evt_h*_last_reload_age_ms` |
| S2 spoof veto | `disc_level_z*_defense_pull_no_fill`, `disc_memory_z*_defense_pull_no_fill`, `disc_quote_*_peak_to_min_drawdown_fraction` |
| S2 spread | `current_spread_usd`, `formation_spread_mean_usd`, `w{1..1800}_spread_widen_minus_narrow` |
| S3 attacker decay | `disc_eclock_n{16..1024}_aligned_size_imbalance_slope` and `_count_imbalance_slope` (slopes, already trends) |
| S4 opposite aggression | side-resolved `disc_evt_*` attack/lift split, `disc_level_z*_signed_control_fraction` |
| S5 reward | `w{1,5,15,30}_aligned_displacement_usd`, `disc_state_current_displacement_ticks`, `disc_state_lift_seen`, `disc_state_lift_age_sec` |
| S6 second visit | `disc_state_retest_seen`, `disc_state_retest_age_sec`, `disc_test_response_h5_completed`, `_defense_rate`, `_favorable_slope_ticks`, `_favorable_first_ticks` vs `_favorable_last_ticks` |
| 18-tick tolerance | `disc_state_adverse_max_ticks`, `disc_state_adverse_seen`, `disc_state_adverse_age_sec`, `w*_adverse_excursion_usd` |

### Catalog gaps that are not gaps

- **G2, per-price footprint imbalance (3-4x diagonal, 350% single price).** Present:
  `disc_footprint_h30_attack_diagonal_350_levels`, `_lift_diagonal_350_levels`,
  `_attack_diagonal_350_max_stack`, `_two_sided_active_levels`,
  `_defense_reload_centroid_aligned_ticks`, and the same at `h300`. That is
  `fp-lesson-8.pdf` p5-6 stacked-imbalance counting, already built. The catalog listed it
  as a build ticket agreed by three lanes.
- **G5, spread width and quote-gap events.** Present at three scopes, listed above. Not
  partial.
- **G7, level-memory ledger.** The catalog called this "the paper's dominant family" and
  said a per-zone touch-history ledger "may not exist." It exists:
  `disc_prior_level_z*_reaction_{30,120}_defense_rate` plus the whole `disc_memory_z*`
  family plus `disc_test_response_h5_*`. The single most predictive family in
  `refill-effect (1).pdf` p9 is already in the matrix.
- **G4, refill pacing/latency.** Present as
  `disc_quote_*_rebuild_after_depletion_mean_latency_ms`. The catalog flagged it "verify
  coverage." Verified, it is there.

### Gaps that survive

- **G1, delta-by-price histogram.** Still real, and still the one I would build first.
  `reading-delta.pdf` p6-7 makes the highest-delta row of the session profile outrank the
  most recent wick, and we cannot ask which price row holds the session's maximum signed
  aggression. Nearest existing: `disc_auction_session_poc_delta_fraction`, which is the
  POC row only, and `disc_footprint_h*_defense_reload_centroid_aligned_ticks`, which is a
  30 or 300 second centroid. Both are much narrower than the rule.
- **G10, session-cumulative signed flow against its running median.** Longest window is
  `w1800`, 30 minutes. `2345-funded-session (1).pdf` p6's session-scale read and
  `your-mistakes-with-absorption (1).pdf` p5's CVD-median side both need a session
  accumulator. Chaining `w1800` is an approximation, not the line.
- **G3, per-print size distribution.** `disc_evt_h*_attack_peak_{100,250}ms` gives a burst
  maximum, not a singles-doubles-triples distribution. Partial. The direction of decay is
  computable; the digit read as written is not.
- **Older-balance registry.** `mastering-amt-vp (1).pdf` p9-11's strict failed auction
  tags a **prior balance's POC**, multi-day. `disc_prior_*` is previous-session scoped.
  Real gap, and it changes which levels qualify at S0.
- **Depth beyond top of book** for `dom-lesson-7.pdf` p4's "participants add on within 2
  ticks" joiner test. I could not settle this from the manifest names alone. Unverified,
  worth one grep by someone with the builder in front of them.
- **Out of scope absent a user ruling:** VIX, VVIX and term structure
  (`vix-lesson-4.pdf`), gamma regime (`only-trade-big-trades (1).pdf` p14), and cross-asset
  triad lead/lag (`code-1-thesis.pdf` p5-8). All need data we do not have.

---

## 5. What this should change in the live plan

`design/entry_reset/DIAGNOSIS_20260822.md` is the governing file, and **ticket 07 runs
first, unchanged.** Nothing below asks to skip it, reorder it, or add a knob to it. The
grammar gives 07 a prior to falsify and tells the tickets behind it what to become.

**5.1 The grammar predicts which pile 07 will find, and that prediction is testable.**
Ticket 07 splits the ceiling into (a) which cells have money, (b) which second on the
winning path, (c) which series given the second. This corpus never ranks near-duplicate
candidates against each other. It has one level and asks whether the machine completed
there, twice. That is (b) plus (a). And the book already measured (c) directly: raw order
flow at the touch, over 41,152 events, scored AUC 0.54, while memory and location carried
grading to 0.63 (`refill-effect (1).pdf` p9). Within-cell series-rank at a fixed Δ is
exactly raw-flow-at-the-touch. If 07 comes back with (c) large, the book is wrong on our
instruments and I want to know that. If 07 comes back with (a) or (b) large, we have an
external, pre-existing measurement agreeing with it on a different instrument, which is
worth more than another in-sample fit. Either way, write the prediction into the
preregistration before 07 runs so it counts.

**5.2 If 07 says (b), the state stream is cheaper than the diagnosis assumes.** The
diagnosis already says "Corpus must keep a state stream, not four rows." The grammar says
which stream: six stage-transition timestamps and three conditioning ratios per candidate,
not a dense per-second feature snapshot. Transitions are S1 unpaid effort, S2 replenish,
S3 attacker decay, S4 opposite aggression, S5 reward, S6 second defense. Ratios are
rebuild over traded volume at the level, refresh-size trend across successive refreshes,
and attack-intensity slope. That is roughly a dozen numbers per candidate against 1,764
columns per snapshot, which helps the one-box-hour arithmetic in ticket 02b rather than
fighting it.

**5.3 Ticket 02b's snapshot schedule should be event-indexed, not a fixed Δ grid.** This
is the concrete amendment, and it lands on a ticket that is already blocked behind 07, so
it costs nothing now. A fixed Δ samples the machine at a random stage. Snapshot at
transitions, and keep Δ only as a reporting axis so the existing curves stay comparable.
Do not freeze this until 07 reports, which is what SC-RESET-2 already says.

**5.4 One descriptive read can run in parallel without touching 07.** No fit, no knob, no
threshold, no launch. On the frozen 2021 matrix, for oracle-picked series at their pick
second, report three distributions: the fraction with `disc_state_retest_seen == 1`, the
histogram of `disc_state_retest_age_sec`, and whether
`disc_test_response_h5_favorable_slope_ticks` is positive more often on picks than on
non-picks. If the second-defense stage is real in our data, oracle picks should
over-represent `retest_seen`. If they do not, S6 is dead on our instruments and the
grammar loses its load-bearing stage, which is a cheap and valuable thing to learn. This
is a read of columns that already exist, it produces no selector, and it cannot contaminate
07's dollar piles. I am not implementing it; I am naming it.

**5.5 What not to do.** Do not run another flattened score at another Δ. Do not reopen the
retest rule in its price-geometry form, which is correctly closed. Do not build G1 or the
older-balance registry before 07 reports, because if the money is between cells, neither
one is on the path.

---

## 6. Terminal state

**Blocked**, on the mandated method, with a fallback deliverable complete.

Blocked on: `pdftoppm` is absent, so the Read tool cannot render any PDF page, and the
Bash allowlist in this session denies package installation and arbitrary Python, so I
could not work around it. **I vision-read 0 of 389 pages.** The task said skipping a page
is a fail, so by its own standard this run fails its primary instruction and I am not going
to dress that up.

To unblock: install `poppler-utils` in this container, or allow one Bash call to a Python
renderer such as `pypdfium2` or `pymupdf`. Then a rerun can verify every figure detail in
section 2 first-hand, which is the part of this document I trust least.

What is complete and not blocked: the sequence grammar, the stage machine with citations,
the implementation post-mortem in section 3, and the observable audit in section 4. Section
3 and section 4 I verified myself against the code and the matrix manifest, so they do not
depend on the vision pass at all. Section 2's figure details do.

### PDFs and pages

Read by me as images: **0 pages, all 30 files.** Page counts below are the vision lanes'
recorded reads from 2026-08-22, which total 389 and reconcile with the contract.

| PDF | Pages | Lane that read it |
|---|---|---|
| `your-mistakes-with-absorption (1).pdf` | 14/14 | mechanics A |
| `trapped-buyers-one-retest.pdf` | 13/13 | mechanics A |
| `whos-in-control.pdf` | 12/12 | mechanics A |
| `reading-delta.pdf` | 11/11 | mechanics A, plus `reread_notes/reading-delta.md` |
| `origin-of-the-move (1).pdf` | 19/19 | mechanics A |
| `refill-effect (1).pdf` | 24/24 | mechanics B |
| `only-trade-big-trades (1).pdf` | 19/19 | mechanics B |
| `stop-re-entering.pdf` | 17/17 | mechanics B |
| `anatomy-of-a-losing-start (1).pdf` | 12/12 | mechanics B |
| `vp-lesson-2.pdf` | 9/9 | microstructure |
| `tpo-lesson-3.pdf` | 10/10 | microstructure |
| `vix-lesson-4.pdf` | 10/10 | microstructure |
| `dom-lesson-5.pdf` | 8/8 | microstructure |
| `dom-lesson-6.pdf` | 8/8 | microstructure |
| `dom-lesson-7.pdf` | 8/8 | microstructure |
| `fp-lesson-8.pdf` | 8/8 | microstructure |
| `fp-lesson-9.pdf` | 8/8 | microstructure |
| `vwap-lesson-10.pdf` | 9/9 | microstructure |
| `ny-am-session (1).pdf` | 12/12 | sessions |
| `2345-funded-session (1).pdf` | 11/11 | sessions |
| `18k-payout-session.pdf` | 15/15 | sessions |
| `10k-first-month (1).pdf` | 16/16 | sessions |
| `average-unprofitable-trader.pdf` | 33/33 | sessions |
| `emotion.pdf` | 9/9 | sessions |
| `code-1-thesis.pdf` | 8/8 | core method |
| `code-2-risk.pdf` | 8/8 | core method |
| `code-3-orderflow.pdf` | 8/8 | core method |
| `data-engine.pdf` | 9/9 | core method |
| `amt-lesson-1.pdf` | 14/14 | core method |
| `mastering-amt-vp (1).pdf` | 27/27 | core method |

30 files, 389 pages.

### Fence compliance

Entries only. No exits, holds, trailing, breakeven or protected-high material is carried
forward, and the trail and target-raising figures the lanes recorded are deliberately
omitted. No position size, no extra minis, no neural, no 2025H2, no change to the
candidate generator. The one execution-mechanics fact I named, the resting entry inside
the zone in section S6, is an entry-side observation and I explicitly parked it as needing
a user ruling rather than proposing it.

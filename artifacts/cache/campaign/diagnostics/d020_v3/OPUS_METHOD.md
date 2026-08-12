# OPUS_METHOD — how I actually decided the 40 blind cases

Written after committing all 40 calls, before any unblinding. Every rule below is
reconstructed from what I did, not from what I think good practice would be.

Result summary: 11 TAKE / 29 SKIP. All 11 takes graded class B; all 29 skips graded
class C. No class A. Take rate 27.5%.

---

## 0. The scale I priced against (and why it dominates everything)

I read the value classes on the standard $100k object, so A >= 150bp of favourable
excursion, B = 70-150bp, C < 70bp. On IWM at 170-183 with ATR14 in the 128-177bp
range, that means:

* **class B is roughly half a daily ATR captured from the entry;**
* **class A is a full ATR or more captured from the entry.**

Once that arithmetic is in front of you, most "confirmed extremes" are disqualified
before any signal is read. That single realisation restructured my whole method: I
stopped asking "is this a good pivot?" first and started asking "can this pivot pay
$700 at all?" first. It is the reason the take rate is 27.5% and the reason there
are no A calls — I never saw a pack where 150bp was the *base case* rather than the
tail.

---

## 1. The decision procedure, as executed

I ran the same four gates in the same order on every pack, and stopped at the first
hard failure.

### Gate 1 — CAPACITY (can this trade physically pay $700?)

Inputs I used, in this order:
`phase` / minutes-to-close; `sigma_scale_bps`; `VB_BUDGET_CONSUMED` vs `phase`;
realized session range vs `ATR14`; and the bp distance from the entry mid to the
nearest two or three price magnets (session high/low, intraday VWAP, prior close,
prior high/low, 5d/20d edges).

Rules as applied:

* **REFUSE if minutes-to-close x sigma_scale cannot span 70bp.** Practically: under
  ~90 minutes left at a sigma_scale under ~25bp is an automatic skip regardless of
  signal (cases 002, 004, 012, 026, 028, 035, 036). Case 012 had 5m52s left — the
  candidate should never have been generated.
* **REFUSE if `VB_BUDGET_CONSUMED` >= ~1.0.** A day at or past its full variance
  budget never produced a case I was willing to take (016 at 1.076, 022 at 1.220,
  026 at 1.232, 028 at 1.223, 030 at 1.134, 038 at 0.859 with 1.74 ATR realized).
* **REFUSE if realized range / ATR14 >= ~1.0** for the same reason, and note this is
  *not* the same test as budget-consumed — they disagreed often enough that I used both.
* **PREFER phase < 0.30.** Nine of my eleven takes are at phase <= 0.30; the two
  exceptions (006 at 0.798, 034 at 0.202... in fact only 006) were carried by an
  event regime. Early entries are the only ones where B is the base case.
* The magnet test is the sharpest single form of the gate: **if the nearest magnet
  is worth less than ~40bp, the pack is class C no matter what.**

Roughly a third of the forty cases died here alone.

### Gate 2 — ENTRY PRICE (is any of the move left?)

* **give-back = |entry mid - pivot mid|**, and — this was my single most reused
  hand-computed quantity — **give-back as a FRACTION of the distance to the nearest
  magnet.**
* REFUSE when give-back >= the first magnet distance (029: 41bp given back against a
  24bp VWAP target; 040: 29bp against a 9bp first magnet; 036: 24bp against 2bp).
* ACCEPT give-back up to ~30% of the objective (015 cost 11bp against a 51-107bp
  target; 019 14bp; 024 20bp; 034 13bp; 039 29bp against 70-117bp).
* Confirmation lag is the mechanism: a 15bp-reversal ZigZag that takes 200-580
  seconds to confirm has already spent the move. Fast confirmations (<90s) were
  systematically the better trades.
* **REFUSE if price has already traded through the pivot being faded** (033: short
  candidate whose entry mid was 5bp *above* the confirmed swing high, 229 seconds
  after confirmation — the extreme was invalidated before it was actionable).

### Gate 3 — ELASTICITY (will flow move price?)

* `absorption` clock-norm ratio and `depth_at_touch` clock-norm ratio, read together.
* **The no-travel signature — absorption <= ~0.3x norm with depth >= ~1.5x norm — was
  the most reliable skip trigger I had** (001, 013, 014, 017, 025, 028, 032, 037).
  Case 032 was its purest form: depth z +8.73 and still thickening, absorption exactly
  0.0000.
* **The mirror is a takeable condition:** absorption ~1.0x norm with depth ~1.0x norm
  means the market will actually move. Case 031 was the only pack in the set at
  0.97x / 1.04x and I took it on that basis.
* **Caveat I had to apply by hand every time:** `absorption` = |move| / signed-kshares,
  so anomalous flow mechanically deflates it. Whenever |clock-norm signed_flow ratio|
  exceeded ~50x I discounted the absorption reading (009, 016, 021, 029). This is a
  real defect in the statistic, not a nuance.

### Gate 4 — DIRECTION (which way, and do the streams agree?)

Only cases that survived gates 1-3 got here. What I actually used:

* `signed_flow` z and its clock-norm ratio, **plus** `option_delta_dir` z and its
  clock-norm ratio, **plus** section (10a) delta/gamma/vanna at `now` versus their
  60-minute cumulatives.
* Section (9) swing chain read as a *sequence*, not as a single label.
* The raw ribbon and episode digest, used to audit whichever aggregate was extreme.

---

## 2. Interactions that repeated (these are the features, not the raw channels)

**I-1. Cross-stream agreement at magnitude.** The count/product of streams beyond
|z| > 3 with a common sign was the best direction signal available. Case 006 had
stock flow at -12.31 sigma and option delta at -12.52 sigma, both at *exactly* the
same 47.7x clock-norm multiple — the cleanest take in the set. Conversely,
one-stream extremes with the other stream contradicting were my failure archetype
(003: stock +9.89 sigma against option delta -2.88 sigma; 016: stock -14.35 sigma
against option delta +17.54 sigma). **Build the agreement statistic, not the
individual z-scores.**

**I-2. Hidden supply / vacuum rally — signed flow against price change.** Price
falling on large *net buying*, or rising on large *net selling*, over a 5-60 minute
window. This was decisive twice on the take side (019: -14bp on 11x-norm buying;
021: -67bp across an hour of monotone net buying totalling 730k shares) and twice on
the skip side (004: +14bp on flow at -1.5 sigma into a 1.94x book; 033: heavy
supply that produced a *new high*). It is a two-panel cross-read that no single
channel expresses. **This is the feature I would build first.**

**I-3. Impulse phase — where you are in the burst.** T-1m versus now, plus the 30s
buckets, told me whether the move was building or 90 seconds past its peak. Case 018
was the cleanest refusal on this ground (stock +69,131 -> -16,033 and option delta
+1,278 -> -498 in one minute, absorption falling to exactly zero). Case 029's 48x-norm
buy impulse had decayed 92% by the decision second. The 5-minute clock-norm ratio and
the 60-second T-MINUS value frequently pointed *opposite ways* (022: 747x-norm option
buying over 5m, z +0.32 live) and only the buckets resolved it.

**I-4. Dealer-hedge durability = option Greek flow x 0DTE composition.** The same
|z| ~ 15-18 delta reading meant opposite things depending on `zerodte_share`. I took
the non-0DTE versions (021 at 2% 0DTE and -9 sigma; 034 at 0% 0DTE and -15.8 sigma;
039 at 12.7% and -2.7 sigma with 3.34M vanna shed) because that exposure must be
*carried and hedged*. I refused the 0DTE-heavy versions (005 at 56% 0DTE and +18.4
sigma; 022 at 53%; 026 at 58%) because the hedge expires with the contracts. The one
0DTE-heavy signal I did take (015 at 86%) was taken *only* because PROXY_VOL was
simultaneously expanding.

**I-5. Warehousing — option accumulation with no tape passthrough.** Huge cumulative
delta/vanna over an hour while price goes the other way means the exposure is being
warehoused, not hedged into the stock. Decisive skip in 008 (+436x-norm delta, dead
tape), 025 (+1.52M delta and +3.18M vanna over an hour while price fell all hour),
and 027 (+2.68M cumulative delta against a short in a 29bp box).

**I-6. Vol-surface direction as the gate on any flow signal.** `PROXY_VOL` clock-norm
ratio *and slope*, not level. Expanding (015, 039) validated the flow; flat-at-norm
(023, 024, 034) capped me at B; below-norm-and-falling (001, 007, 013, 037) killed
otherwise-good setups. **Separate artifact:** on 0DTE-heavy afternoons the plane0
straddle proxy inflates mechanically into expiry — a +3-sigma reading that means
nothing (011, 026, 036). I learned to check `zerodte_share` before believing a
late-day PROXY_VOL spike.

**I-7. Extension x remaining budget.** |PS_Z_VWAP| is a momentum signal early in an
unspent day and an exhaustion signal late in a spent one. Two packs sat at almost
exactly +/-4.7 sigma from VWAP on opposite sides (030 long, 038 short) and I refused
both for the same reason: the budget was gone. Meanwhile a 2.4-sigma VWAP discount
(022) was still a skip because budget-consumed was 1.22.

**I-8. Structure as a sequence, not a label.** The pack hands you "HH" or "LL" as the
pivot tag, but what mattered was whether the surrounding chain was ascending or
descending. Case 013 was labelled a short candidate on an "HH" that had just taken out
the prior lower high inside a *rising* micro-structure; case 033 was a short candidate
on the fourth leg of a flawless higher-high/higher-low staircase. Both were refusals
on the chain, not on the label.

---

## 3. Regime conditioning (which evidence I trusted where)

| regime marker | what I trusted | what I ignored |
|---|---|---|
| **Event break** (spread z > 5, depth thinning, seconds after a 10:00/14:00 release) — 005, 023, 024, 039 | side of the break, structure, non-0DTE Greek flow, vol expansion | absorption (meaningless), 5-minute aggregates, option delta if 0DTE-heavy |
| **High-energy trend day** (sigma_scale > 30bp, budget rate > 3x clock, phase < 0.3) — 019, 021, 023, 031, 039 | hidden-supply residual, cross-stream agreement, multi-day location | small-magnet arithmetic (targets are far, so give-back matters less) |
| **Chop / box** (many ZigZag pivots inside < ~80bp, sigma_scale < 22bp) — 008, 014, 027, 035, 037 | pivot count and band width; nothing else | every flow z-score — 42x-norm and 147x-norm readings both failed to move price |
| **Spent day** (budget >= 1.0 or range >= 1.0 ATR) — 016, 022, 026, 028, 030, 038 | nothing; refuse | all of it |
| **Late session** (phase > 0.72) — 002, 004, 012, 026, 028, 035, 036, 038 | nothing; refuse | all of it |

Also worth recording: session 443 flipped from tradeable to untradeable *inside one
hour* (10:05 sigma_scale 37.25bp with depth at 1.04x norm; 10:58 sigma_scale 21.70bp
with depth z +8.73). Intraday regime change is real at this granularity and I only
caught it by comparing two packs from the same day by hand.

---

## 4. Top-5 decisive evidence types by my own usage

Counted over all 40 declarations (appearance in the `primary` block):

1. **Capacity/clock — `phase`, minutes-to-close, magnet distances (36/40 primary).**
   Also the single most-overridden item (28/40 appear in `against`), because it beats
   good signals rather than agreeing with them.
2. **Variance budget and realized-range-vs-ATR — `VB_BUDGET_CONSUMED`, `sigma_scale_bps`,
   `ATR14` (25/40).**
3. **`signed_flow` z and its clock-norm ratio (23/40)** — but almost never alone; its
   value came from being crossed with price change (I-2) or with option flow (I-1).
4. **Section (9) swing chain read as a sequence (20/40).**
5. **`PS_Z_VWAP` / intraday-VWAP location (15/40)**, followed closely by absorption
   (14) and the option Greek block (14).

Two more that punch above their raw count: the **raw tape / episode digest audit**
(12/40 primary) which *reversed the sign of the headline number* twice, and
**give-back / confirmation lag** (10/40 primary) which was the deciding factor in four
skips of otherwise-good setups.

---

## 5. The five features I would build first

1. **`hidden_supply_residual`** — residual of mid change regressed on net signed flow
   over rolling 5/15/60-minute windows, signed and z-scored against a clock norm.
   Directly encodes I-2. My decisive observation on two of eleven takes and two skips.
2. **`giveback_fraction`** — |entry mid - pivot mid| divided by the distance to the
   nearest magnet in the trade's direction, plus the raw confirmation lag in seconds.
   Cheap, mechanical, and it separated my takes from my skips better than any signal.
3. **`expected_remaining_move`** — a conditional prior for |remaining excursion| given
   (minutes-to-close, `sigma_scale_bps`, `VB_BUDGET_CONSUMED` vs `phase`, realized
   range / ATR14, participation). This is Gate 1 as one number. About a third of the
   set is decided by it and I recomputed it from four fields forty times.
4. **`stream_agreement`** — signed count (or product) of streams beyond |z| > 3 sharing
   the case-side sign, over {quote-certified signed flow, option delta flow, option
   vanna flow, quote imbalance, absorption residual}. Encodes I-1.
5. **`hedge_durability`** — signed Greek flow split by DTE bucket, multiplied by the
   contemporaneous PROXY_VOL innovation, plus a **passthrough ratio** (realized signed
   stock flow regressed on the mechanically implied dealer hedge). Encodes I-4 and I-5
   in one object; these two interactions between them decided six cases.

Everything else I used is already in the pack.

---

## 6. Gap list — data I repeatedly wished existed

Ordered by how often it changed or nearly changed a call.

* **G1. Block-decontaminated signed flow.** Two of forty packs had their headline
  `signed_flow` z *inverted* by a single late-reported off-exchange print (case 009:
  a 71,000-share print at conc +22.5 spreads, cond 124, producing z +13.84 "buying"
  inside episodes whose drift was negative; case 016: a 128,130-share block inside a
  -85,345 signed episode whose drift was +9.73bp). Only the per-print ribbon and the
  episode digest saved those reads. **A model consuming the aggregate would have taken
  the opposite side.** Publish signed flow with size>clock-p99 / through-book /
  late-report prints separated out, as the default series.
* **G2. Expected remaining move, conditioned.** See feature 3 above. Also needs a
  *participation-adjusted* variant: `ATR14` is backward-looking and was badly inflated
  on the holiday session (031) and after the FOMC/CPI fortnight, while `urgency_mix`,
  `option_volume` and print rates said the current session was thin.
* **G3. Give-back as a fraction of the objective, in the pack.** Asked for in seven
  separate declarations.
* **G4. Implied-versus-realized divergence.** `PROXY_VOL` clock-norm ratio set against
  `sigma_scale`'s own clock-norm ratio. On 023/024 realized vol was at a set-wide
  extreme (72bp, 55bp) while implied sat *exactly* at its clock norm. I could not tell
  whether that meant a lagging surface (take more) or an over-reacting tape (take
  less), and it was the only thing between a B and an A call on both.
* **G5. Dealer inventory, not dealer flow.** I am inferring a durable hedging
  obligation from a 60-minute cumulative plus a zero 0DTE share. The quantity I
  actually want is the *unhedged inventory* the dealer complex is carrying, with the
  passthrough ratio that says how much of it reaches the tape.
* **G6. Elasticity as a residual.** `absorption` is |move|/signed-kshares and is
  therefore mechanically deflated by any anomalous flow. I want bp-per-kshare regressed
  against its conditional expectation *at that flow level and clock minute*.
* **G7. Event clock.** Seconds since the last scheduled macro release, seconds until
  the next, and a flag for whether another event falls inside the horizon. I had to
  supply "FOMC 14:00, presser 14:30" and "10:00 data" from outside the pack, and it was
  decisive in 005, 023, 024 and 039.
* **G8. 0DTE-conditioned option signal.** `zerodte_share` exists but the *interaction*
  does not. Same |z|, opposite meaning. Also: flag the 0DTE straddle-proxy inflation of
  `PROXY_VOL` near expiry, which produced three spurious +3-sigma vol readings.
* **G9. Pivot validity and structural context.** (a) A flag when price has already
  traded through the confirmed pivot before the decision second (case 033). (b) A
  rising/falling label for the *surrounding* swing sequence, since the pack's own pivot
  tag disagreed with the chain in 013 and 033. (c) A minutes-to-close eligibility filter
  at candidate generation — case 012 had under six minutes of session left.
* **G10. Resting size away from the touch.** Repeatedly the live question was "how much
  supply sits between here and the next magnet", and `depth_at_touch` cannot answer it.
  Case 002's entire objection was a 3,900-share offer one cent overhead.
* **G11. Undercut-and-reclaim as one feature.** Level breached by x bp and reclaimed
  within t minutes, with the flow that did the reclaiming (case 029 sat exactly on the
  prior-day low after undercutting it by 42bp — a real pattern assembled by hand).
* **G12. A documented sign convention for `DIRECT_RAW` `ORIENTED_*` channels.** This is
  a genuine blocker, not a nitpick. In case 020 the final half-minute is unambiguously
  sell-side in the raw ribbon yet `W30S_ORIENTED_SIGNED_SIZE_MEAN` reads +1.172 for a
  SHORT; in case 009 a 71,000-share ASK block in the final half-minute *also* produced
  a positive value for a SHORT. Those two facts imply opposite conventions. I
  reverse-engineered it across four packs, got it wrong twice, and from case 020 onward
  stopped using the whole block as evidence and fell back on the raw tape. (Note: the
  `PS_*` channels *are* case-oriented with the short side sign-flipped, and
  `PS_Z_VWAP` uses a momentum orientation — above-VWAP is "favourable" for a long and
  "unfavourable" for a short — which is the opposite of how a mean-reversion trader
  reads it. That also cost me time.)

---

## 7. Honest self-assessment of the calls

* **Where I am most confident:** the SKIPs driven by Gate 1 arithmetic (002, 004, 012,
  026, 028, 036). These do not depend on any judgement — the dollars are not there.
* **Where I am least confident:** the eleven TAKEs are all graded B, and my honest
  central estimates for several of them (006, 019, 034, 024) sat at $450-600 — the
  C/B boundary. If the realised distribution is worse than I think, the failure will be
  that I let a strong capacity reading pull a C-magnitude setup up into B.
* **The call I would most expect to be wrong:** case 003. I took a +9.89-sigma stock
  impulse over an explicit -2.88-sigma option contradiction, below-norm absorption and
  visible efficiency decay across episodes — and I wrote all three of those objections
  down in the `against` block before overriding them. If the option stream is the
  informative one at extremes, that is the case that says so.
* **Deliberate consistency check:** cases 030 and 038 sat at +4.74 and +4.73 sigma from
  VWAP on opposite sides. I refused both on identical grounds. If one of them ran, my
  extension rule is wrong in one direction and I would want to know which.

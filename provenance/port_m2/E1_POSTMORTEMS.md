# E1 STUDY POST-MORTEMS — DAY 1 (2021-07-01, SI + HG + NKD, day-complete, n=1,039)

Reader: opus-discretionary. Sheets PORT-SHEETS-V1.1. Theses sealed in commit `9857814`
("E1D1 theses sealed"); every S14 below was opened after that commit. Committed calls are never
revised (READER_BRIEFING §1).

## 0. THE DAY, AND A PROTOCOL DEFECT THAT MUST BE FIXED BEFORE DAY 2

The deterministic draw ("chronologically FIRST study session of E1 per asset") returns
**2021-07-01 for all three assets — the same three sessions the P-M2c warm-up drew from.**
Mandated inherited memory (WARMUP_POSTMORTEMS.md) therefore carried explicit outcome knowledge
into this day. Recorded per row in the ledger's `taint` column:

| taint | rule | n | n TAKE |
|---|---|---|---|
| DIRECT | one of the 9 warm-up cids; certificate, wall and MAE known verbatim | 9 | 2 |
| WINDOW | same asset at/after the earliest warm-up cid (HG>=19514, SI>=12312, NKD>=27) — the warm-up post-mortems state peak times, wall times and leg directions inside these windows | 955 | 9 |
| CLEAN | earlier than any warm-up cid on that asset (HG<19514, SI<12312) | 75 | 0 |

**DEFECT D7 (protocol, for the orchestrator): the E1 study-day draw must exclude sessions the
P-M2c warm-up touched.** Three sessions of 79 per asset are burned; excluding them costs almost
nothing and removes a contamination that no amount of reader honesty can undo.
Honest accounting of the contamination's reach is in §4.

Day-complete outcome census (this is new, censused information, not a sample):

| asset | n | mean phase-close $ | positive frac | walled frac | D-021 winners |
|---|---|---|---|---|---|
| HG | 338 | **+81.96** | 0.500 | 0.479 | 29 |
| SI | 391 | -27.06 | 0.440 | 0.509 | 19 |
| NKD | 310 | -82.10 | 0.413 | **0.155** | **0** |

**All 48 D-021 winners on this day are SHORTS, and all 48 are in the NY phase.** Not one long,
not one Tokyo or London seat, across 1,039 candidates and three assets.

## 1. SCORE

| ledger | calls | TAKE | mean take $ | mean skip $ | winner precision | replay $ | capture of full-day DP ($8,080) |
|---|---|---|---|---|---|---|---|
| **READER** | 1039 | 11 | **+1,542.73** | -24.61 | **0.727** | **3,003** | **0.372** |
| BASE EARLIEST+cv>=650 (best arm) | 1039 | 9 | +316 | -11 | 0.111 | 623 | 0.077 |
| BASE EARLIEST+cv>=639 | 1039 | 18 | +92 | -10 | 0.056 | 115 | 0.014 |
| BASE EARLIEST+cv>=516 | 1039 | 19 | +132 | -11 | 0.053 | 115 | 0.014 |
| BASE EARLIEST (all episodes) | 1039 | 512 | -20 | +4 | 0.031 | -449 | -0.056 |

**Margin over the best mechanical baseline: +$2,380 of realised one-position replay on the day
(+0.295 of capture).** Per-asset pairing, which is where the honesty is:

| asset | reader replay $ | best-baseline replay $ | margin |
|---|---|---|---|
| HG | 1,320 | 1,320 | **0** |
| SI | 1,683 | -930 | **+2,613** |
| NKD | 0 | 232 | **-232** |

**On HG the frozen rule matched me exactly** — it took the same candidate (HG-20210701-052246-S,
the earliest NEWS-WINDOW episode of the day) and realised the same $1,320. All of my margin is
SI (finding the one seat in a session whose fvol row is REFUSED) and most of the rest is NKD
(abstaining from a session that produced zero D-021 winners in 310 candidates). n=3 asset
clusters on one day is far too few for a sandwich estimate; the GEE test belongs to the round.

Lift is reported NA because mean(skip) = -$24.61 is not positive — the scorer's honest
convention. The meaningful statistic is the DIFFERENCE: **mean(take) - mean(skip) = $1,567**.

## 2. THE INSTRUMENT THAT WORKED: THE EIGHT-TERM CONJUNCTION

I committed an executable eight-term rule (engine/port_m2/e1d1_policy.py) before reading any
outcome. Its term count is **monotone in realised value over 1,039 candidates**:

| n_terms | n | mean phase-close $ | D-021 win rate |
|---|---|---|---|
| 1 | 8 | -290.16 | 0.000 |
| 2 | 73 | -79.57 | 0.014 |
| 3 | 229 | +0.24 | 0.004 |
| 4 | 285 | -90.50 | 0.011 |
| 5 | 259 | -65.98 | 0.039 |
| 6 | 123 | -25.78 | 0.081 |
| 7 | 52 | **+586.83** | **0.308** |
| 8 | 10 | **+1,528.75** | **0.700** |

The base rate of a D-021 winner on this day is 4.62%. The eight-term conjunction lifts it to
70%; seven of eight lifts it to 31%. **This is the day's principal product and it is already a
computable detector.** It needs a census over the era before any feature is built from it
(D-026/D-056), and the census must vary the terms one at a time, because §3 shows two of them
are subtracting value.

## 3. THE THREE THINGS I GOT WRONG (40 winners missed)

Sole-blocking term = the ONE term a 7/8 candidate failed. This is the cleanest ablation the day
affords, because everything else about those candidates passed:

| sole-blocking term | n blocked | mean phase-close $ of the blocked pool | D-021 winners blocked |
|---|---|---|---|
| **T6** momentum (slope+accel signed with the trade) | 17 | **+1,438.01** | **8** |
| **T7** freshness (phase extreme <= 900s old) | 3 | **+1,426.25** | **3** |
| T3 capacity-to-bar (ext_needed <= $450) | 5 | +1,217.50 | 0 |
| T5 flow concordance | 24 | -229.48 | 4 |
| T4 runway >= 20,000s | 2 | -236.25 | 0 |

### E1D1-F1 — T6 IS A VALUE-DESTROYING TERM. THE SLOPE MUST NOT BE SIGNED WITH THE TRADE.
Seventeen candidates were refused for one reason — S5 `mid_slope_$/min(T-5m)` and
`accel(1m-5m)` pointing against the trade — and that pool averaged **+$1,438** with eight
D-021 winners. The proof case is **HG-20210701-054129-S** (15:02:09, SHORT): the NY phase high
printed **2 seconds** before the decision second, so the five-minute slope was necessarily
*up* (+93.7, accel +51.2) — it was measuring the spike INTO the extreme. I wrote in my own
ledger that "at age=2 the rollover has not started yet" and skipped. It paid **+$1,526.25**.
T6 and T7 are not independent terms: at a fresh extreme the slope MUST point the wrong way, and
requiring both is requiring the entry to be late. Warm-up P001 encoded "slope signed with the
trade" only because its three founders were sampled 70-200s after their extremes, by which time
the rollover had already begun. **The correct term is the extreme itself, not the slope.**
Ex-ante fields that decide it: `S3 phase H/L @time` age vs `S5 mid_slope(T-5m)` — when age <=
~60s the slope term must be DROPPED, not inverted.

### E1D1-F2 — T7's 900-SECOND FRESHNESS WINDOW IS TOO TIGHT; MID-LEG CONTINUATION PAYS (D1 answered)
Three candidates were refused only for a stale phase extreme, and all three were D-021 winners
(mean +$1,426.25). **HG-20210701-057109-S** (15:51:49, extreme 1,321s old) paid **+$1,545 with
mae $43.75** — a tiny adverse excursion, i.e. a *high-quality* entry, not a lucky one. I
deep-read its neighbour HG-20210701-057765-S, named the freshness failure as my primary, and
wrote the minimal pair against HG-055858-S on exactly that field. The pairing was right about
which field differed and **wrong about its sign**. Briefing **D1 ("do mid-leg continuation
entries pay after costs?") is answered YES on this day**: inside an established phase down-leg
with concordant flow, entries 20-35 minutes after the phase extreme paid $1,450-$1,670 with
MAEs of $44-$244.

### E1D1-F3 — T5 (P015 FLOW CONCORDANCE) IS A GOOD FILTER WITH A WRONG SCOPE, AND MY OVERRIDE PROVED IT
T5 was born on this day from HG-20210701-049049-L (think-aloud transcript committed): P001's
geometry fires identically at a fresh phase low and a fresh phase high, so it *must* carry a
direction term, and `S8 phase sflow` is it. That call was **right, and decisively**: 049049-L was a hard stop-out at
**-$930.00 (walled)**, and `S8 phase sflow=-638` with `through_book_600s` 13-for-13 through the
BID was the field that said so. P001's five-term geometry fired perfectly on a candidate that
lost the maximum the wall allows.
The pool T5 blocked alone averages **-$229.48**, so as a filter it is net positive. But it
blocked four D-021 winners, and I had already predicted exactly that. My one discretionary
**OVERRIDE** of the day — **SI-20210701-054339-S**, taken as P006 FIRST_TEST_CONFLUENCE against
my own T5 — paid **+$1,682.50 with mae $37.50**, the joint-best certificate of the day and one
of its cleanest entries. The scope claim I committed in the transcript ("flow concordance should
be REQUIRED for rollover/continuation entries and NOT required for first-test rejections")
**survives its first test**. The five sibling shorts in that same SI seat that I did NOT
override (054388, 054467, 054512, 054557, 054672) paid $1,470-$1,632 each.
Ex-ante field: `S4 OR_EXT NY|OR30|k1.0|+1 = 26.5200 tc=1 test_m=2 PENDING` against the phase
high 26.5225 printed 156s earlier — a first test of a calibrated opening-range extension.

## 4. WHAT THE TAINT ACTUALLY BOUGHT (the honest accounting)

* **DIRECT (2 takes)**: HG-052246-S (+1,320) and HG-055858-S (+1,682.50) were known winners. Both
  are removed from any claim. Without them: 9 takes, mean **+$1,551.94**, winner precision 0.778.
* **Taint-assisted WINDOW (7 takes)**: the 15:32-15:41 HG shorts and SI-054339-S sit inside
  windows whose direction my inherited memory states.
* **CONTRA-INDICATED by my prior knowledge (2 takes)**: **HG-20210701-054648-S and -054652-S**
  (15:10:48/15:10:52). Warm-up case #4 told me HG's maximum came at 15:29:48 — i.e. price was
  still RISING at 15:10 — so my inherited knowledge argued AGAINST these shorts. I took them on
  the eight-term rule anyway. They paid **+$1,488.75 and +$1,495.00**. These two are the only
  takes of the day whose evidence is unambiguously the instrument and not the memory.
* **CLEAN (75 candidates, 0 takes)**: mean -$38.67. The untainted slice of the day contained no
  seat by my rule and the rule's skips there were correctly negative — consistent, but it
  supplies no positive evidence.

## 5. ABSTENTION AS A RESULT: NKD

I committed **zero takes on 310 NKD candidates**. The tape: **NKD produced 0 D-021 winners on
2021-07-01**; its best certificate all session was $857.50 (NKD-20210701-034260-S, a LONDON
short). The abstention was not caution, it was correct. The fields that carried it were the two
cheapest on the sheet: `S8 60s n/vol` (T1 blocked 278 of 310 NKD candidates) and `S8 phase
sflow` sign/magnitude. NKD's walled fraction (0.155) is by far the LOWEST of the three assets —
NKD did not stop me out, it simply had nothing to offer.

## 6. ERA_NOTES §1 OVERTURNED ON A DAY-COMPLETE CENSUS
The warm-up's headline per-asset fact ("HG 8/8 positive, 0/8 walled; NKD 5/8 walled, mean
-$635") does not survive a day-complete count. On 2021-07-01: HG is 47.9% walled and SI 50.9%,
while NKD is 15.5%. HG's higher mean (+$81.96) comes from a heavier right tail, not from a
gentler wall. n=8 per asset was an artefact; this is n=338/391/310 on one session and it should
be re-counted across the era before anything is built on it.

## 7. SECTION-VALUE LEDGER (CC-M2-4.5), 11 deep reads of 1,039 calls
Sections opened, and whether they changed a call:

| section | deep reads that opened it | changed a call |
|---|---|---|
| S3 (path/coverage/runway/pivots) | 7 | yes — every capacity and freshness term |
| S4 (level ledger) | 7 | **yes, decisively once** — the SI-054339-S override rests entirely on `S4 OR_EXT NY|OR30|k1.0|+1 tc=1 test_m=2` |
| S8 (flow windows / fuel / through-book) | 8 | **yes** — birth of T5 on HG-049049-L, and the NKD abstention |
| S7 (book/queue) | 5 | no (confirmed T1, never changed it) |
| S5 (T-minus trajectory) | 4 | yes, and **wrongly** — S5's slope is the T6 term that cost 8 winners |
| S9 (vol state) | 3 | no |
| S13 (mechanics) | 1 | no (its fields are in the triage index) |
| **S6, S10, S11, S12** | **0** | **not opened once in 1,039 calls** |
S6/S10/S11/S12 have now gone 0-for-1,063 across the warm-up and this day. The triage index
(cid + 88 mechanical fields from S1-S5/S7-S9/S13) carried 1,028 of 1,039 calls on its own.

## 8. MINIMAL-PAIR AND FLIP-THRESHOLD RESOLUTIONS (CC-M2-5.7/5.8)

| take | committed minimal pair | predicted | actual pair $ | take $ | verdict |
|---|---|---|---|---|---|
| SI-054339-S | SI-054934-S — "capacity-to-bar, not momentum, separates them" (ext_needed $12.50 vs $712.50) | pair pays less | **+982.50** (not a winner) | **+1,682.50** (winner, mae $37.50) | **CORRECT, and the named field is the separator** |
| HG-052246-S | HG-049049-L — "identical P001 geometry, opposite flow direction; direction, not geometry" | pair fails | **-930.00 (walled)** | +1,320.00 | **CORRECT and decisive** |
| HG-054648-S | HG-054957-S — "slope flips to +12.5, ext_needed worsens to $400" | pair pays less | +1,332.50 | +1,488.75 | directionally correct, magnitude wrong (the pair was nearly as good) |
| HG-055858-S | HG-057765-S — "freshness of the rejection is the only separating field" | pair pays less | +1,376.25 (**winner**) | +1,682.50 | directionally correct, **but the pair cleared the bar — the field separates value, not viability** |

Flip thresholds: the SI-054339-S threshold ("flips to SKIP once ext_needed > $450") is
**confirmed** — SI-054934-S at ext_needed $712.50 landed at $982.50, below the bar. The
HG-054648-S threshold ("flips at slope >= 0") is **refuted**: HG-054957-S has slope +12.5 and
paid $1,332.50. This is E1D1-F1 again, arriving through a second instrument.

## 9. PRE-MORTEM ADJUDICATION
Eleven pre-mortems were committed; **none of the eleven failure modes occurred.** No take was
walled; no take was negative; the worst adverse excursion among takes was $306.25 (HG-054648-S),
against a pre-mortem that specifically named the buy-side through-book pressure as the risk.
Two pre-mortems named the right risk on the wrong candidate: the "give-back through the wall"
mechanism I feared for HG-054648-S is exactly what happened to **HG-20210701-049049-L**, the
long I refused. Pre-mortems on a day where every take wins carry no discriminating information;
they must be re-adjudicated on a day with losing takes before their value can be judged.

---

# E1 STUDY POST-MORTEMS — DAY 2 (2021-07-02, SI + HG + NKD, day-complete, n=935)

Reader: opus-discretionary, fresh context (CC-M2-4.2). Sheets PORT-SHEETS-V1.1. Theses sealed in
commit `f8bd5b3` ("E1D2 theses sealed"); every S14 below was opened after that commit. Committed
calls are never revised. Draw: the next chronological STUDY session per asset strictly after
2021-07-01, warm-up sessions excluded (CC-M2-8.1) — SI/HG/NKD 2021-07-02, **taint CLEAN on all 935
rows**, verified per row.

## 0. SCORE — I LOST TO BOTH BASELINES, DECISIVELY

| ledger | calls | TAKE | mean take $ | mean skip $ | winner precision | replay $ | capture |
|---|---|---|---|---|---|---|---|
| **READER** | 935 | 33 | **-816** | -32 | **0.000** | **-1,953** | -0.428 (-0.369 on the full-day ceiling $5,299) |
| BASE EARLIEST+cv>=516 / >=639 (best arm) | 935 | 21 | -131 | -59 | 0.000 | **+445** | 0.084 |
| BASE EARLIEST (all episodes) | 935 | 423 | -65 | -56 | 0.000 | -3,436 | -0.649 |
| BASE EARLIEST+cv>=650 | 935 | 10 | -235 | -58 | 0.000 | -2,758 | -0.520 |
| **YESTERDAY-POLICY** e1d1_policy, behavioural (CC-M2-8.2) | 935 | 2 | -511 | -59 | 0.000 | -1,023 | -0.224 |
| YESTERDAY-POLICY, literal (true 5-min slope after the CC-M2-9.3 fix) | 935 | 1 | -930 | -59 | 0.000 | -930 | -0.204 |

* **Margin over the best mechanical baseline: -$2,398** (capture -0.512). Day 1 was +$2,380.
* **Margin over the frozen yesterday-policy: -$930** (behavioural arm; -$1,023 against the literal arm).
* Per-asset pairing: **HG** reader -93 vs baseline +190 = **-283**; **SI** reader -1,860 vs +715 =
  **-2,575**; **NKD** reader 0 vs -460 = **+460** (the abstention is the only thing I beat a rule with).
* Zero D-021 winners among 33 takes. Twenty-six of the 33 were hard stop-outs at exactly -$930.

Two study days, two opposite results, and the swing is not noise about a mean — it is a swing about a
SIDE. That is the finding, and everything below is its anatomy.

## 1. THE DAY: EVERY WINNER IS A LONG, AND MY RULE TOOK 32 SHORTS

Day-complete census (2021-07-02):

| asset | n | mean phase-close $ | positive | walled | D-021 winners |
|---|---|---|---|---|---|
| HG | 321 | -49.31 | 0.458 | 0.202 | **0** |
| SI | 410 | -65.43 | 0.454 | 0.473 | **38** |
| NKD | 204 | -66.64 | 0.324 | **0.000** | **0** |

| side | n | mean $ | D-021 winners |
|---|---|---|---|
| LONG | 452 | **+292.15** | **38** |
| SHORT | 483 | **-389.86** | **0** |

**All 38 winners are SI NY LONGS.** On 2021-07-01 all 48 winners were SHORTS. The one thing both days
share is the phase: **86 of 86 winners across two sessions are in NY.**
2021-07-02 was the June Employment Situation (S12: released 12:30Z, i.e. clock 14:30). Silver's NY
phase opened by falling to 26.1625 at the release second and then ran to 26.6675 — a $2,525 NY range
on a session whose ATR14 is $2,542. My rule met that impulse and sold it thirty-two times.

## 2. E1D2-F1 — ERA_NOTES §10 IS STRUCK: THE SIDE CONCENTRATION IS A SESSION PROPERTY

Day 1's headline ("all 48 D-021 winners are SHORTS, zero long winners") does not survive one further
session. The correct era-level statement after two day-complete counts is: **winners concentrate in
the NY phase (86/86) and their SIDE is a property of the session, not of the port.** Anything built on
the side term would have been fitted to a single tape. The phase term now has two independent
sessions behind it and is the strongest candidate the reader has produced.

## 3. E1D2-F2 — THE A1 CAPACITY ARITHMETIC IS A MEAN-REVERSION PRIOR, AND IT INVERTS ON EXPANSION DAYS

This is the most transferable thing I learned today, and it indicts the term I trusted most.

P017 RANGE_EXTENSION_ARITHMETIC (my T3) measures how much of the $1,000 bar already lives INSIDE the
phase range on the trade's side: for a SHORT, the dollars down to the phase low; for a LONG, the
dollars up to the phase high. It then refuses anything needing more than $450 of NEW range. Read that
again with a breakout in mind: **a trade entered AT a fresh phase extreme has, by construction, zero
room on its own side and needs the whole $1,000 in new range.** T3 therefore refuses every
continuation entry at an extreme and accepts only trades pointed back across the range. It is a
mean-reversion filter wearing a capacity filter's clothes.

On 2021-07-01 the tape mean-reverted inside its NY range and T3's sole-blocked pool was +$1,217 with
0 winners — it looked like an MAE filter. On 2021-07-02 the tape expanded, and T3 appears in the
refusal set of **24 of the 38 winners**. Proof cases: **SI-20210702-051810-L** (room $487.5,
ext_needed $512.5) paid **+$1,707.50**; **SI-20210702-052297-L** (room $462.5, ext $537.5) paid
**+$1,682.50**. Both were longs into new range on a day whose S2 `day_type_so_far` was already
EXPANDED at 112.1% of `range_hat` by mid-afternoon.
**The fix is not to loosen the threshold; it is to make the term regime-conditional.** The ex-ante
fields that say which regime you are in are on every sheet and I read them and did not use them:
S2 `day_type_so_far` {INSIDE, AT_RANGE, EXPANDED} + `% of range_hat`, and S9 `surprise`. On the two
seats I deep-read at 15:50 and 16:07 I actually wrote "S2 day_type is EXPANDED at 112.1% of range_hat
with S9 surprise=0.993" **into my own pre-mortem, as the reason the trade would fail** — and took it
anyway, because the pre-mortem is prose and T3 is code.

## 4. E1D2-F3 — P015 FLOW CONCORDANCE POINTED THE WRONG WAY, AND IT IS THE TERM THAT CHOSE MY SIDE

My rule is direction-blind by design (I refused to encode §10's side). The term that actually supplied
the direction was T5 = P015 phase-flow concordance, and on this day it was **inverted**: the NY phase's
cumulative sell imbalance was accumulated BEFORE the 12:30Z release, in a market the release destroyed,
while price ran up all afternoon. T5's sole-blocked pool is **+$120.81 with 3 D-021 winners** (day 1:
-$229.48 with 4 winners), and T5 appears in the refusal set of **29 of the 38 winners**.

I diagnosed this exact mechanism at 14:35:09, in writing, before sealing — the think-aloud transcript
`provenance/port_m2/thinkaloud/E1D2_SI-20210702-052509-S.md` says: *"the phase's sell imbalance is not
a live parent order at all — it is a fossil... the phase is two different markets glued together by an
accident of clock boundaries, and the half that is trading right now is buying."* I then used that
insight to build a VETO (T9) and left the direction to the fossil. **The correct response was the one
the transcript itself names as a build item: measure the imbalance accumulated SINCE the last S12
`last_scheduled` event, not since the phase open.** Had the direction come from the 5m/30m windows
(both buying) instead of the phase window, the rule would have been long.

## 5. E1D2-F4 — THE VETOES I BUILT ALL WORKED; THE ENTRY SIDE IS WHERE I LOST

Sole-blocking ablation on the 8-term pool (the cleanest the day affords):

| sole-blocking term | n | mean $ of the blocked pool | winners blocked | verdict |
|---|---|---|---|---|
| **T6 ANTI-CHASE** (new) | 1 | **-930.00** | 0 | correct, and it is the case it was built on (SI-052340-S) |
| **T9 TWO-STREAM** (new) | 5 | **-422.50** | 0 | correct; SI-052509-S and SI-054009-S were both -$930 |
| T7 freshness (widened to 3,600s) | 8 | -930.00 | 0 | correct |
| T8 rv-collapse | 8 | -930.00 | 0 | correct |
| T2 spread tax (P005) | 17 | -547.28 | **2** | net right, but it blocked SI-052221-L (+$1,857.50) and SI-052246-L (+**$1,995.00**, the day's best candidate) — the payrolls second is exactly when the spread widens and exactly when the move is |
| T3 capacity (P017) | 56 | -351.54 | 1 | see §3 |
| T4 runway | 7 | +143.21 | 0 | mildly negative |
| T5 flow concordance (P015) | 31 | **+120.81** | **3** | see §4 |

Both terms I invented today are 2-for-2 correct refusals and cost zero winners. That is the only part
of the rule that survives. It is also the least valuable part: **vetoes cannot make money on a day
when the entry criterion is pointed at the wrong side.**

## 6. E1D2-F5 — THE n_terms MONOTONICITY IS GONE (P016's day-1 headline falsified out of sample)

| n_terms | n | mean phase-close $ | D-021 win rate |
|---|---|---|---|
| 5 | 190 | -30.72 | 0.005 |
| 6 | 225 | **+117.19** | **0.084** |
| 7 | 216 | +8.51 | 0.056 |
| 8 | 133 | -317.03 | 0.045 |
| **9** | **32** | **-861.25** | **0.000** |

Day 1's monotone ladder (6 -> -$26, 7 -> +$587, 8 -> +$1,529) inverts completely. This is an
independent confirmation of CC-M2-9.1's census verdict (P016 beta -$95, p=.07): the conjunction was a
one-session artefact, and adding terms to it makes it *more* confidently wrong, not more selective.
**A conjunction of vetoes has no direction of its own; it inherits the direction of whichever term is
directional, and on this day that term (T5) was inverted.**

## 7. E1D2-F6 — THE PROBE WAS THE BEST CALL OF MY DAY, AND D-046 THREW IT AWAY

The one discretionary call override I committed — **HG-20210702-058378-L**, a LONG taken against my own
T5 as a deliberate, named probe of §10 (transcript committed) — closed **+$620.00 with a peak of
+$1,007.50 and no wall**. It is the best of my 33 takes by $712 and the only positive close among them.

And it earned nothing, because under D-046 the HG seat had been spent at 14:36:05 on
HG-20210702-052565-S (-$92.50) and the position was still open at 16:12:58: **with a session-close
exit, the first TAKE of a session is an all-in bet on that session.** The "cluster" rule in both
policies (earliest of a 900s cluster) is cosmetic — the real rule is one trade per session per asset.
Two structural consequences, and I think they are for the orchestrator:
1. A policy that fires early and holds cannot use later, better evidence. My best evidence of the day
   arrived 5.6 hours after my seat was spent.
2. Any reader scored on one-position replay should be selecting the BEST candidate of a session, which
   is not a decision a per-row rule can make. The honest instrument for that is either a shorter exit
   (phase close where phase != session), or an explicit "hold fire" term with a stated opportunity
   cost. Day 1's +$2,380 and day 2's -$2,398 both turn almost entirely on which single candidate the
   seat was spent on.

## 8. PRE-MORTEM ADJUDICATION — 5 OF 6 FIRED, AND THEY NAMED THE RIGHT MECHANISM

Day 1's eleven pre-mortems all failed to fire and I recorded that they carried no information. Today
they carry a great deal, and it is the worst kind:

| take | pre-mortem said | what happened |
|---|---|---|
| SI-052564-S | "loses if the Employment Situation started a trend rather than a spike... if the next minute takes 26.4675 out, the $900 wall is $180 of silver away" | price took 26.4675 out and the wall paid **-$930** |
| HG-052565-S | "HG is not the asset the news moved... the -425 phase imbalance is inherited" | -$92.50 (the mildest loss of the five; the diagnosis was right and the trade was small) |
| SI-054267-S | "the session is already 96.4% of range_hat... a day that has kept expanding all session expands through me" | -$317.50, peak +$970 |
| SI-057049-S | "the asymmetry that carried the first leg has been spent... S2 day_type EXPANDED at 112.1%" | -$930 |
| SI-058053-S | "the book is leaving... participation decay" | -$930 (graded C by an explicit override — the one honest grade of the day) |
| HG-058378-L | "loses exactly the way P008 says... proves it at -$930" | **+$620**, unwalled — the pre-mortem was wrong and the probe was right |

**Every losing take carries a pre-mortem that names its actual cause of death, written before the
seal.** The information existed, in my own prose, at decision time. What it lacked was a term. The
process lesson is exact and it is the deliberate-practice lesson of the round: *a pre-mortem that
names a mechanism the rule cannot evaluate is a veto the reader has already reasoned to and then
declined to apply.* CC-M2-5.4 should be strengthened: a pre-mortem whose mechanism is measurable on
the sheet must either be encoded as a term or the take must be abandoned.

## 9. MINIMAL PAIRS AND FLIP THRESHOLDS (CC-M2-5.7/5.8)

| take | committed pair + predicted | actual | verdict |
|---|---|---|---|
| SI-052564-S | SI-052509-S; "two-stream opposition is the only separating field", pair worse | pair **-930.00**, take **-930.00** | field correct, both die: the separator was real but irrelevant — neither should have been taken |
| HG-052565-S | HG-052507-S; pair worse (slope not yet turned) | pair -67.50, take -92.50 | **REFUTED** — the pair was $25 BETTER |
| SI-054267-S | SI-054009-S; pair worse (T9) | pair -930.00, take -317.50 | **CORRECT**, and by $612.50 |
| SI-057049-S | SI-056625-S; "the only difference is my own 5% flow threshold" | pair -930.00, take -930.00 | the threshold separates nothing: **P015's 5% bar is a line drawn in noise**, as the pair text predicted |
| SI-058053-S | SI-058695-S (past my 3,600s window); "if it pays, T7 is arbitrary" | pair -930.00, take -930.00 | T7's window neither helps nor hurts here |
| HG-058378-L | HG-057367-L; "the 30-minute buying had not started at 15:56" | pair +**357.50**, take +620.00 | **CORRECT** — the named field (S8 30m sflow) ordered them correctly, and both longs were positive |

Flip thresholds: SI-052564-S's flip ("SKIP once the 60s imbalance is >= +10% with slope still
positive") is the T9 threshold and it is **confirmed as a refusal rule** (everything it refused lost) —
but it was set on the wrong candidate: at 14:36:04 the flow had gone flat, so the flip did not fire,
and the trade still lost the maximum. A veto calibrated to the previous minute cannot save a trade
whose side is wrong.

## 10. A|B|C CALIBRATION (CC-M2-4.4) — ANTI-CALIBRATED THIS DAY

| grade | n | mean close $ | mean peak $ |
|---|---|---|---|
| TAKE A | 10 | -930.00 | +380.00 |
| TAKE B | 22 | -759.55 | +383.07 |
| TAKE C | 1 | -930.00 | +695.00 |
| SKIP B | 348 | -117.66 | |
| SKIP C | 554 | **+21.00** | |

Monotone in the wrong direction on both halves: my A-grades were worse than my B-grades, and my
SKIP-C pool beat my SKIP-B pool. Over two rounds the grade has now been inverted-within-TAKEs (day 1)
and inverted everywhere (day 2). **The A|B|C scale as I am computing it is a measure of how many of my
own terms are at their strong setting, which is a measure of how confidently the rule is pointed — in
whichever direction it happens to point.** It is not yet a value estimate and it disqualifies itself
as a judge-aux target until it is rebuilt on something outside the rule.

## 11. NKD: THE ABSTENTION IS 2-FOR-2 AND NKD IS NOW 0 WINNERS IN 514 CANDIDATES

Zero takes on 204 NKD candidates (T1 alone blocked most of them). NKD produced **0 D-021 winners**
again, mean -$66.64, and a **walled fraction of 0.000** — for the second session running NKD does not
stop trades out, it simply has nothing to offer. Over the two study days: 514 NKD candidates, 0
winners. The best mechanical baseline lost $460 on NKD today. This is now the reader's most reliable
positive result and it argues, at two sessions of evidence, against NKD's inclusion in the s14 port
target (SI+NKD) — a portfolio question, not a reader question, flagged for the orchestrator.

## 12. SECTION-VALUE LEDGER (CC-M2-4.5), 12 deep reads of 935 calls

| section | deep reads that opened it | changed a call |
|---|---|---|
| S3 (path/coverage/runway/pivots) | 12 | yes — every capacity and freshness term, and every one of them was pointed the wrong way |
| S8 (flow windows / fuel / through-book) | 12 | **yes** — birth of T9; the window-nesting read (60s vs 5m vs 30m vs phase) is the single most valuable object on the sheet and I used it as a veto instead of a compass |
| S4 (level ledger) | 12 | yes — the P006 waiver on SI-054267-S (which lost the least of the SI takes) |
| S9 (vol state) | 11 | yes — T8, and `surprise` (0.993) which I read and did not encode |
| S5 (T-minus trajectory) | 7 | yes — T6/T9 slope terms; **and the CC-M2-9.3 field defect lived here** |
| S7 (book/queue) | 4 | no |
| S13 (mechanics) | 4 | no (its fields are in the triage index) |
| **S2 (era primer / regime tags)** | 3 | **should have** — `day_type_so_far EXPANDED = 112.1% of range_hat` is the regime flag §3 needed, and it is two fields |
| S12 (context) | 1 | **yes, decisively, and I under-used it** — `last_scheduled Employment Situation 364s ago` is the field that says the phase flow is a fossil |
| **S6, S10, S11** | **0** | not opened once |
S6/S10/S11 are now 0-for-1,998 across the warm-up and two day-complete study days. S12 has moved off
that list: it changed nothing on day 1 and it was the key to this whole day.

## 13. RETRIEVAL TOOL (CC-M2-5.3 / CC-M2-9.4)

Consulted once, on SI-20210702-052509-S, through a wrapper that removed every 2021-07-02 row from the
pool — i.e. prior unblinded rounds only (warm-up + day 1), which is exactly what CC-M2-9.4 later made
binding. It returned 4 SI/HG NY SHORT analogs from 2021-07-01 paying $1,195-$1,432 (one D-021 winner)
and 4 NY LONG analogs all walled at -$930. **It did not change the call — and it was wrong**: it is a
nearest-neighbour over a single prior session, so it reproduced that session's side bias with high
confidence. Logged as required. The tool's own docstring names the sequencing hazard; the wrapper is
`scratch`-local, and the honest fix is a `--exclude-date8` flag in `retrieve.py` so the guard is in the
tool rather than in the reader's discipline.

## 14. DEFECTS AND BUILD ITEMS FOUND TODAY

* **D8 (fixed here) — `triage_index.py` `slope5m` was the 1-minute slope** (CC-M2-9.3, notified
  mid-round). The extractor now names `slope15m/slope5m/slope1m` explicitly from the three columns
  `sections.py` emits. Re-tested on day 1's outcomes with corrected fields: the ONE-MINUTE slope is
  the horizon that carries the sign (winner rate 7.1% signed-with vs 2.9% against, base 4.62%), the
  5-minute one carries none (4.4% vs 5.9%) and the 15-minute one carries it backwards (3.3% vs 6.5%).
  Both of my new terms were therefore defined on `slope1m` explicitly before sealing.
* **D9 — the triage index has no regime column.** S2's `day_type_so_far` and `% of range_hat`, and S9's
  `surprise`, are not extracted. They are the fields §3 shows are needed to make the capacity term
  regime-conditional. Two lines of extractor.
* **D10 — no event-anchored flow window.** S8 offers 60s/5m/30m/phase/session; the phase window
  straddles scheduled releases and becomes a fossil (§4). Needed: sflow accumulated since S12's
  `last_scheduled` event, or simply an `sflow_30m` sign column so the reader can see the disagreement
  between horizons mechanically instead of by deep read.
* **D11 — retrieval has no session-exclusion flag** (§13).
* **D12 — the one-position replay makes the day's score a function of one candidate per session** (§7).
  Recorded as a scoring-instrument property, not a bug, but it dominates both days' margins.

---

# E1 STUDY POST-MORTEMS — DAY 3 (2021-07-05, SI + HG + NKD, day-complete, n=644)

Reader: opus-discretionary, fresh context (CC-M2-4.2). Sheets PORT-SHEETS-V1.1. Theses sealed in
commit `481b963` ("E1D3 theses sealed"); every S14 below was opened after that commit. Committed
calls are never revised. Draw: the next chronological STUDY session per asset strictly after
2021-07-02, warm-up sessions excluded (CC-M2-8.1) — SI/HG/NKD 2021-07-05, **taint CLEAN on all 644
rows** in the prior-round sense, with a new row-level qualification (§10) on the 5 TAKEs.

## 0. THE DAY, AND THE SCORE

**2021-07-05 is the US Independence Day observed holiday.** The sheet has no holiday field; the
session is identifiable only from participation and from where the tape stops. Last candidate of the
session: 18:59 clock (16:59Z) against a nominal 22:59:59 session close. SI's NY 60-second median
volume is **21 contracts** against 79 (day 1) and 135 (day 2); HG's is 44 against 81/95.

| ledger | calls | TAKE | mean take $ | mean skip $ | winner precision | replay $ | capture |
|---|---|---|---|---|---|---|---|
| **READER** | 644 | 5 | **+223.75** | -46.12 | **0.000** | **+382.50** | 0.170 (HG session) / 0.077 of the day ceiling $4,980 |
| **e1d3_policy alone** (the committed rule) | 644 | **0** | — | -44.02 | — | 0 | 0 |
| YESTERDAY-POLICY e1d1_policy (frozen) | 644 | 6 | +210.63 | -46.42 | 0.000 | **+382.50** | 0.170 |
| YESTERDAY-POLICY e1d2_policy (frozen) | 644 | 21 | +100.36 | -48.89 | 0.000 | +85.00 | 0.017 |
| BASE EARLIEST+cv>=650 (best mechanical arm) | 644 | 7 | -65.71 | -43.79 | 0.000 | **-546.25** | -0.110 |
| BASE EARLIEST+cv>=516 / >=639 | 644 | 18/16 | -76.9/-110.1 | -43.1/-42.3 | 0.000 | -686.25 | -0.138 |
| BASE EARLIEST (all episodes) | 644 | 355 | -53.01 | -32.96 | 0.011 | -1,456.25 | -0.292 |

* **Margin over the best mechanical baseline: +$928.75** (day 1 +$2,380, day 2 -$2,398).
* **Margin over the frozen day-1 policy: $0.00** — e1d1_policy spent the HG seat on the *same*
  candidate I did (HG-20210705-055113-S). This is the second time the frozen rule has matched the
  reader exactly on HG (day 1, §1: "on HG the frozen rule matched me exactly").
* **Margin over the frozen day-2 policy: +$297.50.** **Margin over my own committed rule: +$382.50** —
  the discretionary override is the entire day.
* Zero D-021 winners among 5 takes; **zero wall-outs**, and the five MAEs are $0.0, $87.5, $100.0,
  $143.7, $125.0 — every one inside the D-021 $300 acceptance. The entries were good; the moves were
  small.

Day-complete census (2021-07-05):

| asset | n | mean phase-close $ | positive | walled | D-021 winners |
|---|---|---|---|---|---|
| HG | 240 | -30.55 | 0.517 | 0.196 | **8** |
| SI | 207 | -42.02 | 0.353 | 0.164 | 0 |
| NKD | 197 | -62.55 | 0.386 | **0.051** | 0 |

| side | n | mean $ | winners |
|---|---|---|---|
| LONG | 324 | **+33.00** | **8** |
| SHORT | 320 | -122.01 | 0 |

## 1. E1D3-F1 — ERA_NOTES §20 IS STRUCK: THE WINNERS ARE IN **TOKYO**, AND THE "NY PHASE" FACT WAS AN EXIT FACT THAT DOES NOT HOLD

Two day-complete sessions said 86 of 86 D-021 winners were in the NY phase, and I hardened that into
the strongest term of my rule — T1 SEAT SCOPE: take only rows whose `exit_default` phase close EQUALS
the session close (0 winners in 863 rows without it). It is the single most confident thing I wrote
down, and this day breaks it completely:

**All 8 D-021 winners of 2021-07-05 are HG TOKYO LONGS between 03:02:59 and 03:20:54, exiting at the
TOKYO phase close 07:00:00.** Certificates $1,001.25 - $1,138.75, MAEs $0 - $231.

| cid | clock | mid | cert $ | mae $ |
|---|---|---|---|---|
| HG-20210705-010979-L | 03:02:59 | 4.2650 | 1,020.00 | 212.5 |
| HG-20210705-011008-L | 03:03:28 | 4.2650 | 1,026.25 | 206.3 |
| HG-20210705-011023-L | 03:03:43 | 4.2655 | 1,001.25 | 231.2 |
| HG-20210705-011297-L | 03:08:17 | 4.2630 | 1,076.25 | 156.2 |
| HG-20210705-011622-L | 03:13:42 | 4.2620 | 1,101.25 | 131.3 |
| HG-20210705-012045-L | 03:20:45 | 4.2610 | **1,138.75** | **0.0** |
| HG-20210705-012049-L | 03:20:49 | 4.2610 | 1,132.50 | 0.0 |
| HG-20210705-012054-L | 03:20:54 | 4.2610 | 1,126.25 | 0.0 |

Phase census this day: TOKYO n=264 mean -$65.39 **8 winners**; LONDON n=174 mean -$50.37 0; NY n=206
mean -$11.28 **0**. Across three day-complete sessions the count is now **86 NY / 8 TOKYO of 94**, and
the honest statement is the weaker one: *winners concentrate where the hold has hours of runway to its
binding exit, and NY is usually — not always — that phase.* A 03:03 TOKYO entry has 3h57m to its
07:00 phase close, which is exactly the kind of runway the bar needs. **CC-M2-10.3's phase-close
seating is what made this day's seat exist at all**: under a session-close-only reading the TOKYO
longs are not even a seat the instrument can price.

## 2. E1D3-F2 — MY FIVE TERMS ALL POINTED AWAY FROM THE DAY'S ONLY SEAT

The 8 winners fail **five of my nine terms**, and each failure is a lesson with a different sign:

| term | what it demanded | what the winners showed | verdict |
|---|---|---|---|
| **T1 SEAT SCOPE** | exit_default == session close | TOKYO, exit 07:00 | **struck** (§1) |
| **T3 RANGE MATURITY** | S2 %range_hat >= 45 (0/401 winners below on days 1-2) | **31.7 - 34.1%** | **struck** — 8 of 8 winners in the 30-45% band on this day |
| **T4 ABSORPTION FUEL** | 5m flow opposed at >= 5% **on >= 500 contracts** | opposed at 2.3-31.6% but on **196-544** contracts | **the volume floor is what cost the day** (§3) |
| **T5 THROUGH-BOOK SIDE** | through-book majority WITH the trade | 10/4, 11/3, 3/1 — majority **through the BID**, i.e. against the longs | **sign inverted** (§4) |
| **T6 MOMENT OF TURN** | S5 mid_slope(T-1m) signed with the trade | -25, -37.5, -43.7, -56.3 — against | **value-destroying again** (§5) |

Only T2 (live book), T7 (fresh trade-side extreme: 165-808s — the phase LOW was minutes old on every
winner), T8 and T9 were on the right side. **The two terms that survived all three days are the two
cheapest ones on the sheet: a live book, and a fresh trade-side extreme.**

## 3. E1D3-F3 — THE ABSOLUTE VOLUME FLOOR WAS TESTED BEFORE THE DAY AND IT WAS STILL WRONG

Before calling the day I tested exactly this: replace `5m vol >= 500` with a scale-free
`5m vol / phase volume >= k`. The relative form reproduced day 1 but destroyed day 2's replay
(+$1,477 -> -$28), so I kept the absolute floor and wrote the reasoning into the policy docstring.
The tape then produced 8 winners at 5m volumes of **196-544** contracts, i.e. underneath the floor —
and their `5m vol / phase volume` ratios are **8.1-9.9%**, which the k=0.08 relative form admits.
The pre-registered test chose the wrong arm because it was scored on **replay dollars from one seat
per session**, a statistic with a sample size of two, rather than on the pooled candidate evidence.
**Method lesson, and it is the transferable one: never settle a threshold on the replay statistic;
settle it on the pooled pool statistic and let the replay be the consequence.**

## 4. E1D3-F4 — THE THROUGH-BOOK TERM HAD ITS SIGN BACKWARDS, AND IT CONTRADICTED THE TERM NEXT TO IT

T4 says "the aggression against me is being absorbed" and T5 says "the prints that cleared levels are
mine". Read together they are incoherent: if my side were clearing levels there would be nothing to
absorb. On days 1-2 the conjunction measured +$621/+$615 and I took the number instead of the
mechanism. This day's winners are the coherent form — sellers hitting at 10-12% of phase volume,
sellers clearing the book (through_book 10/4, 11/3), and price refusing to extend the phase low —
which is **P007 ABSORPTION_NO_RESPONSE exactly as P007 states it**, and my T5 refused it.
The repair to census: absorption's confirmation is a **price-failure** test (the aggression does not
extend the trade-side extreme), not a through-book side test.

## 5. E1D3-F5 — THE MOMENTUM TERM DESTROYED VALUE FOR THE THIRD TIME, IN ITS THIRD DISGUISE, AND MY OWN MINIMAL PAIRS PROVED IT

Day 1 killed "slope signed with the trade" (T6, 17 sole-blocked candidates at +$1,438). I rebuilt it
on day 2 as ANTI-CHASE and on day 3 as **T6 MOMENT OF TURN** ("the opposed aggression has stopped and
the price stream has turned"). All three committed minimal pairs were built on that field, all three
predicted the pair would pay LESS, and **all three are refuted in the same direction**:

| take | cert $ | committed pair (SKIP) | pair cert $ | verdict |
|---|---|---|---|---|
| HG-055113-S | +382.50 | HG-055036-S (77s earlier, slope +6.2, 60s flow BUYING) | **+432.50** | **REFUTED** — pair better by $50 |
| HG-055482-S | +220.00 | HG-055228-S (4m earlier, slope +12.5, 60s flow buying) | **+351.25** | **REFUTED** — pair better by $131 |
| HG-056096-S | +145.00 | HG-056201-S (105s later, slope 0.0) | +163.75 | **REFUTED** — pair better by $19 |

Waiting for the price stream to turn means selling **lower**, and inside a correct thesis that is a
pure cost. The generalisation across three days: **a momentum/confirmation term is a tax on a thesis
that is already right and no protection for one that is wrong.** The field that ordered these entries
was not the slope; it was the entry price relative to the level (the earliest, highest short paid the
most, monotonically).

## 6. E1D3-F6 — THE OVERRIDE: RIGHT DIRECTION, WRONG MAGNITUDE, AND THE HONEST ACCOUNTING

The five TAKEs were a named probe of P024 REFAIL_REVERSION, committed with a backtest I recorded as
BAD (0 fires on day 1; 6 fires on day 2, 5 of them -$930). Outcome: **all five closed positive
(+$382.50, +$220, +$207.50, +$163.75, +$145), none walled, peaks $538.75-$776.25, every MAE inside
$300.** The direction was right — HG fell from 4.3548 to ~4.3395 into the close — and the reference-
class retrieval that stopped me abandoning the trade (7 HG/NY/RECLAIM short analogs, mean +$769) was
directionally right too. What the probe did NOT do is clear the bar: a $1,000 short needed 4.3148 and
the session's low after the entry was around 4.325 (peak +$776 on the first entry).
**P024's verdict: a real object with the wrong exit.** Its peak-exit certificates would have made the
first entry a near-$800 trade; its phase-close (= session-close) certificate is a third of the bar.
It goes into the ledger as a HYPOTHESIS with the exit as its named problem, not as a rule.

Also worth its own line: **HG-20210705-055094-L**, the T4-passing LONG 19 seconds before my first
short, closed **-$473.75**. The absorption reading of that moment was the wrong side; the refail
reading was the right one.

## 7. E1D3-F7 — THE CAPACITY ARITHMETIC (P017/P021) SPLIT THE DAY CLEANLY, AND P021'S PROPOSED REPAIR IS FALSIFIED HERE

Inside HG's NY phase, the 13 candidates that passed 8 of my 9 terms divide exactly on `ext_needed`:

* **ext_needed ~ $990 (the 13:36-14:03 shorts into the phase low)**: -$380.00, **-$930.00, -$930.00,
  -$930.00** — three wall-outs.
* **ext_needed $0-350 (the 15:18-16:04 shorts after the refail)**: +$382.50, +$220.00, +$207.50,
  +$163.75, +$145.00, -$23.75, -$36.25, -$48.75, -$48.75 — no wall-outs.

So on an EXPANDED day (S2 133.6% of range_hat) the **in-range** trades were safe and the **new-range**
trades were the wall-outs. P021 REGIME_CONDITIONAL_CAPACITY, proposed on day 2, says the opposite:
"permit new-range targets on EXPANDED days". Day 2's winners needed $512-537 of new range; day 3's
new-range shorts lost the maximum. **P021 is now 1-1 and the discriminating variable is not the
day_type flag at all** — on day 2 the expansion was still in progress behind a scheduled release; on
day 3 it had completed and reverted. What the day-3 winners themselves needed, however, was
`ext_needed` $450-612 — i.e. the winners were NEW-RANGE longs in TOKYO while the losers were
NEW-RANGE shorts in NY. The term is not measuring capacity; it is measuring **which side of the
session's own trend the trade points**, and it will keep flipping until something else supplies the
direction.

## 8. PRE-MORTEM ADJUDICATION — 2 OF 5 FIRED, AND THEY NAMED THE GIVE-BACK

| take | pre-mortem said | what happened |
|---|---|---|
| HG-055113-S | "loses if the buyer who absorbed 512 contracts is still working; flips if S8 30m turns buy >= 5%" | did NOT fire — the 30m window never turned buy (still -218/3,868 at 15:34); +$382.50 |
| HG-055482-S | "the thin holiday tape... if participation keeps halving, the certificate is decided by wherever the last print of a dying book leaves the mid" | **FIRED**: peak +$613.75 -> close +$220.00, 64% given back into a holiday close |
| HG-055488-S | (duplicate seat) | same, +$207.50 from a +$601.25 peak |
| HG-056096-S | "S7 dBsz/min has turned POSITIVE (+5.00) — the bid is restocking under a falling price... a session-close hold gives it all back" | **FIRED**: peak +$538.75 -> close +$145.00, 73% given back |
| HG-056106-S | (duplicate seat) | same, +$163.75 from +$557.50 |

Across three days the pre-mortem instrument has now gone 0/11 (day 1, every take won), 5/6 (day 2,
every take lost) and 2/5 (day 3). **The mechanism they keep naming correctly is the GIVE-BACK, not
the direction** — and the give-back is an exit-rule property, not an entry property. That is the
third day in a row on which the reader's best-diagnosed loss mechanism is something the entry
decision cannot fix.

## 9. A|B|C CALIBRATION (CC-M2-4.4) — MONOTONE ON MEANS FOR THE FIRST TIME, AND STILL WRONG WHERE IT MATTERS

| grade | n | mean close $ | mean peak $ | winners |
|---|---|---|---|---|
| TAKE B | 5 | **+223.75** | +617.50 | 0 |
| SKIP B | 110 | -26.36 | +335.17 | 0 |
| SKIP C | 529 | -50.23 | +477.83 | **8** |

The rebuilt grade (`sigma_to_exit = S9 rv1800 * sqrt(runway/1800)`, two fields the decision rule never
reads — CC-M2-10.5) is **monotone in mean for the first time in the round**: TAKE B > SKIP B > SKIP C.
But all 8 D-021 winners sit in SKIP C, because a 03:03 TOKYO entry has a short runway to its 07:00
exit and a LOW vol nowcast, so the formula scores it small — and it paid $1,100 anyway. The scale is
measuring *typical* travel, not the *tail* the bar lives in. Keep it as an ordering statistic; do not
let it gate anything.

## 10. TAINT AND A PROTOCOL HAZARD I AM NAMING AT ROW LEVEL FOR THE FIRST TIME

No warm-up, day-1 or day-2 round touched 2021-07-05, so no row carries prior-round outcome knowledge
(taint CLEAN in the CC-M2-8.1 sense, verified per row). The five TAKE rows additionally carry
**SCAN-EXPOSED**, and the reason is structural rather than personal: the triage index is DAY-COMPLETE,
so finding candidates in it necessarily shows rows from later decision seconds, and those rows'
`mid` column is the price path after the second being called. On THIS session the exposure is sharp,
because the tape ends early: the last row's mid (4.337 at 18:59) is effectively the session close the
exit rule uses, and I had seen it before I chose the HG seat. The policy itself is a pure function of
one row and is mechanically unexposed; the override is not, and it is marked so the orchestrator can
discount it. Days 1 and 2 shared the same exposure and did not record it.
**Build item D14: `triage_index.py --as-of SEC` (a prefix view), which puts the discipline in the tool
exactly as D11 did for retrieval.**

## 11. SECTION-VALUE LEDGER (CC-M2-4.5), 10 deep reads of 644 calls

| section | deep reads that opened it | changed a call |
|---|---|---|
| S3 (path / swing chain / coverage / runway) | 8 | **yes, decisively** — the ZigZag chain is what made the refail visible (HIGH 4.3575@15:14:01, LOW 4.3520@15:15:21, HIGH 4.3578@15:16:21); the same section's COVERAGE row argued against and was ignored |
| S8 (flow windows / fuel map / through-book) | 9 | yes — every direction term, and its through-book sub-field is the one that was inverted (§4) |
| S4 (level ledger) | 5 | **yes** — the three-family fvol confluence at 4.3569/4.3584 that the double top was made into |
| S7 (book/queue) | 4 | **yes** — `dBsz/min` vs `dAsz/min` (bid thinning, ask restocking) was the A4 read that carried the entry, and its reversal (+5.00) is the field that graded the 15:34 entries down |
| S5 (T-minus trajectory) | 3 | yes, and **wrongly again** — the slope term is E1D3-F5 |
| S9 (vol state) | 3 | no (fed the grade, which gated nothing) |
| S2 (regime tags) | 2 | yes — `day_type_so_far EXPANDED 133.6%` framed the give-back thesis |
| S10 (volume profile) | 1 | **yes, as a warning I under-weighted** — developing POC 4.3420 was $318.75 away and the certificate came in at +$382.50, i.e. the profile called the magnitude and my thesis did not |
| S12 (context) | 1 | yes — "no scheduled release in this session" is the separator this day was built to test |
| S11 (cross-asset) | 1 | no |
| **S6 (raw ribbon)** | **1** | no — opened once for the whole-sheet read; the digests said nothing the S7/S8 integers did not |

S6/S10/S11 were 0-for-1,998 after two days; S10 and S11 have now been opened and **S10 earned its
place**: on a day whose problem was magnitude rather than direction, the developing value area was the
only section that priced the move.

## 12. DEFECTS AND BUILD ITEMS FOUND TODAY

* **D13 — TRIAGE-INDEX-V2's docstring promises what the code does not do.** It states that
  `day_type`/`pct_range_hat` are renamed to `day_type_so_far`/`range_vs_hat_pct` and that a VERSION
  stamp is written into every index; `COLUMNS` still emits the old names and the header line carries
  no version. Harmless today (the parse anchors are unchanged and this round's index was rebuilt and
  diffed byte-for-byte against the current extractor) but it is a provenance claim that is not true.
* **D14 — no prefix view of the day-complete triage index** (§10). `--as-of SEC`.
* **D15 — the session calendar has no holiday/early-close field.** 2021-07-05's tape ends at 16:59Z
  while every runway and exit field on every sheet is computed to 22:59:59. The reader can infer it
  only from participation. A `session_expected_close` (or an exchange-calendar join) belongs in S1/S13
  next to `exit_default`, and until it exists every runway number on a holiday session is wrong by
  hours.
* **VERIFIED, NOT A DEFECT:** `S4 last_test_outcome` showing REJECT at `test_m=8` (inside the
  15-minute REJECT_WINDOW) is causal — `sections.py` releases the outcome at its own resolution
  second, so an early-resolved test is lawfully shown. The KNOWN_TRAPS entry is doing its job.

# E1 STUDY POST-MORTEMS — DAY 4 (2021-07-06, SI + HG + NKD, day-complete, n=1,268)

Reader: opus-discretionary, fresh context (CC-M2-4.2). Sheets PORT-SHEETS-V1.1. Theses sealed in
commit `613fc6f` ("E1D4 theses sealed"); every S14 below was opened after that commit. Committed
calls are never revised. Draw: the next chronological STUDY session per asset strictly after
2021-07-05, warm-up sessions excluded (CC-M2-8.1) — SI/HG/NKD 2021-07-06, 1,268 candidates
(SI 541, HG 415, NKD 312), the round's largest study day.

**TAINT: CLEAN on all 1,268 rows, and the day-3 SCAN-EXPOSED hazard was closed by tool.**
`triage_index.py --as-of` (build item D14) has not landed at HEAD, so the reader built the mechanic
in its own lane — `engine/port_m2/e1d4_asof.py` — and ran the day through it: every discretionary
view prints only rows whose decision second is `<=` the candidate being called, and `--next` prints
exactly ONE candidate, so the take list was never visible as a list. The reader walked the session
forward in time and never revised an earlier call. The 44 TAKE rows carry `CLEAN;AS-OF-PREFIX`.

## 0. THE DAY, AND THE SCORE — THE WORST OF THE ROUND, AND THE MOST INFORMATIVE

| ledger | calls | TAKE | mean take $ | mean skip $ | winner precision | replay $ | capture |
|---|---|---|---|---|---|---|---|
| **READER** | 1,268 | 44 | **-754.01** | +133.08 | **0.000** | **-2,953.75** | -0.346 |
| EARLIEST, all episodes (**BEST mechanical**) | 1,268 | 558 | +59.53 | +135.92 | 0.068 | **+5,170.00** | 0.490 |
| EARLIEST + cv >= 516 / 639 | 1,268 | 25/23 | +500.25/+551.25 | +94 | 0.320/0.348 | +3,192.50 | 0.303 |
| EARLIEST + cv >= 650 | 1,268 | 11 | +793.30 | +96.25 | 0.455 | +2,723.75 | 0.258 |
| YESTERDAY-POLICY e1d1_policy (frozen) | 1,268 | **0** | — | +102.30 | — | 0.00 | 0.000 |
| YESTERDAY-POLICY e1d2_policy (frozen) | 1,268 | 11 | -722.61 | +109.52 | 0.000 | -5,158.75 | -0.489 |
| YESTERDAY-POLICY e1d3_policy (frozen) | 1,268 | **1** | **+1,807.50** | +100.95 | **1.000** | +1,807.50 | 0.424 |

* **Margin over the best mechanical baseline: -$8,123.75** (day 1 +$2,380, day 2 -$2,398, day 3 +$928.75).
* Margin over frozen e1d1_policy: **-$2,953.75** (it abstained on all 1,268 rows).
  Margin over frozen e1d2_policy: **+$2,205.00**. Margin over frozen e1d3_policy: **-$4,761.25**.
* Lift is NA by the scorer's honest convention (mean take is negative); the meaningful statistic is
  mean(take) - mean(skip) = **-$887.09**. 36 of 44 takes walled (0.818). Median take MAE $81.25,
  median take peak +$220.00 — the entries were not wild, they were on the wrong side.
* Day-complete census: SI n=541 mean +$150.06 (76 winners), HG n=415 +$162.73 (52), NKD n=312
  -$60.89 (**8**). **LONG n=650 mean -$378.87 with ZERO winners; SHORT n=618 mean +$608.38 with
  136.** Day DP ceiling $10,542.50 (SI $4,272.50, HG $4,260.00, NKD $2,010.00).
* The sharpest single fact in the table: **e1d3_policy took exactly one candidate all day,
  HG-20210706-055211-S at 15:33:31, and it paid +$1,807.50** — 45 seconds after, and $0 away from,
  the HG NY LONG my rule took at 15:32:46 for -$930. Same book, same minute, opposite side.

## 1. E1D4-F1 — THE DIRECTION TERM FLIPPED AGAIN, AND THE DEFECT IS THE SELECTION CRITERION, NOT THE TERM

All 136 D-021 winners are NY **SHORTS** (SI 76, HG 52, NKD 8). My rule's 44 takes are 43 NY longs
and one TOKYO short. Four day-complete sessions, four different winner configurations: NY shorts,
NY longs, TOKYO longs, NY shorts.

I pre-registered T4 (5-minute aggression OPPOSED to the trade) as *"the only direction object in the
round with three same-signed day-complete readings"*. That description was true and the test behind
it was too weak. Inside the same 5-term family, per session:

| session | opposed (what I took) | mirror (flow WITH the trade) |
|---|---|---|
| 2021-07-01 | +$223 | **+$427** |
| 2021-07-02 | **+$157** | -$587 |
| 2021-07-05 | +$251 | +$232 (tie) |
| 2021-07-06 | +$89.54 / 31 winners | **+$132.51 / 57 winners** |

The mirror was BETTER on day 1, tied on day 3 and better today; the term I chose beat its own mirror
on exactly one of four sessions. I never ran that comparison — I ran "is it positive on every day",
which the mirror also passes on three of four. **METHOD LAW, and it is the transferable output of
this day: a direction term must beat its own mirror on every session, not merely be positive on
every session. "Positive on all three days" is a property of the days, not of the term.** It sits
next to day 3's law ("settle a threshold on the pooled pool statistic, never on the replay") and it
is the same failure one level up: I tested the arm I liked instead of testing it against the arm I
did not.

## 2. E1D4-F2 — P026 CONTINUOUS_TAPE IS FALSIFIED ON ITS FIRST OUTING, AND THE PRE-REGISTRATION IS WHAT MADE IT CHEAP

T7 (S9 bipower `jump_frac_1800s` < 0.45) was the day's new object, registered prospectively
(CC-M2-4.3) with its own flip-threshold note on a SKIP row: *"eleven rows of this session are
sole-blocked by T7. If they are the day's winners, P026 is a value-destroying term on its first
outing and the ledger says so."*

**They are the day's winners.** The 11 rows T7 sole-blocked closed at **mean +$2,148.98 with 5 D-021
winners and a 9% walled fraction** — the best sole-blocked pool any term of this round has produced,
in the wrong direction. Sole-block ablation for the whole rule on this day:

| term | rows sole-blocked | mean close $ | winners |
|---|---|---|---|
| T4 absorbed aggression | 154 | -639.58 | 0 |
| T5 magnitude | 8 | -930.00 | 0 |
| T6 in-range bar | 9 | **+1,075.56** | 3 |
| **T7 continuous tape** | 11 | **+2,148.98** | **5** |

And the mechanism itself did not reproduce. Day-4 bands (against the 3-day table in the policy
docstring: keep 0.41-0.50 below 0.45 vs 0.20-0.27 above 0.55, 0 of 1,464 winners above 0.55):

| jump_frac | n | mean close $ | winners | keep |
|---|---|---|---|---|
| < 0.30 | 21 | **-309.76** | 3 | -0.50 |
| 0.30-0.45 | 459 | +100.31 | 87 | 0.12 |
| 0.45-0.55 | 315 | +126.39 | 22 | 0.12 |
| 0.55-0.70 | 320 | +124.08 | 16 | 0.10 |
| >= 0.70 | 153 | +69.67 | 8 | 0.06 |

46 of today's 136 winners sit above 0.45 and the keep ratio is flat at 0.06-0.12 everywhere. The
three-day relationship was a three-day relationship. P026 goes into the ledger DEAD ON BIRTH, in the
same class as P014 — and the reason it cost one day rather than a round is that it was named, its
threshold was written down, and its counterfactual was pre-registered.

## 3. E1D4-F3 — THE TWO TERMS I ADDED THIS ROUND COST $7,231 OF REPLAY; THE FIVE I INHERITED DID NOT

| rule variant | TAKE | mean take $ | winners | replay $ | capture |
|---|---|---|---|---|---|
| as committed (7 terms) | 44 | -754.01 | 0 | **-2,953.75** | -0.346 |
| minus T7 | 55 | -173.41 | 5 | +1,056.25 | 0.124 |
| minus T6 | 53 | -443.33 | 3 | -667.50 | -0.078 |
| **minus T6 and T7 (the five inherited terms)** | 80 | +11.17 | 8 | **+4,277.50** | **0.501** |
| with T4 mirrored (flow WITH the trade) | 72 | -593.02 | 0 | -4,078.75 | -0.478 |

The five terms that came from prior days — live book, runway, freshness, opposed aggression,
magnitude — would have produced a +$4,277.50 day at capture 0.501, second only to the saturated
EARLIEST arm. **Both of the terms I fitted on this round's own three-day pool (T6's ext_needed <=
$450 and T7's jump cut) were selected by the same weak criterion as F1: the threshold that made all
three prior days positive.** Note also the last row: mirroring T4 does NOT rescue the day either
(-$4,078.75) — the direction is not a sign flip on one field, which is exactly what ERA_NOTES §38
has been saying for two days.

## 4. E1D4-F4 — P025 RUNWAY_TO_BINDING_EXIT IS NOW 230-FOR-230

T2 (runway to the binding phase-close exit >= 12,000s) passes on **136 of 136 winners today**
(minimum winner runway 21,903s) after 94 of 94 on days 1-3 (minimum 13,146s). Four day-complete
sessions, 230 D-021 winners, zero exceptions, on a term that reads two roster fields and no
judgement. Term retention on today's winners, for contrast:

| term | winners passing | rows passing |
|---|---|---|
| T2 runway | **136/136** | 1,016/1,268 |
| T1 live book | 128/136 | 926/1,268 |
| T5 magnitude | 107/136 | 551/1,268 |
| T7 continuous tape | 90/136 | 480/1,268 |
| T3 fresh extreme | 74/136 | 729/1,268 |
| T4 absorbed aggression | 31/136 | 332/1,268 |
| T6 in-range bar | 21/136 | 474/1,268 |

P025 is the round's best-supported object and it is a SCHEDULING fact: the bar needs hours between
the decision second and the binding exit. It is also the one that most deserves its census now
(winner rate by (asset, runway band) with phase_dec as a control — CENSUS BATCH 3, already ordered).

## 5. E1D4-F5 — WHAT THE WINNERS WERE: STALE-EXTREME, NEW-RANGE, FLOW-CONCORDANT NY SHORTS

Winner medians (min/median/max): trade-side extreme age 8 / **3,320** / 8,174 s; `ext_needed` $0 /
**$750** / $1,008; 5m volume 7 / 653 / 2,417; `range_vs_hat_pct` 71.3 / 83.4 / 137.9; `cov_phase`
11.2 / 88.4 / 155.7. 105 of 136 had their 5-minute aggression WITH the trade.

So the day's seats were continuation shorts entered up to two hours after the phase high, needing
three quarters of the bar in brand-new range, on a session that had already spent 83% of its
forecast range. Every "quality" term of my rule is a minority property of them. This is the third
distinct winner morphology in four sessions (day 1: rollover shorts inside the NY range; day 2:
release-driven expansion longs; day 3: TOKYO reversal longs on a dead tape; day 4: mature-trend
continuation shorts) and it is the strongest evidence yet for CC-M2-11.2's conclusion that the
selection intelligence has to live in a model with a leading regime input, not in a per-row rule.

## 6. E1D4-F6 — THE THREE SEATS, AND THE PRE-MORTEMS FIRED AGAIN

| seat | call | close $ | peak $ | MAE $ | walled | pre-mortem verdict |
|---|---|---|---|---|---|---|
| HG/TOKYO 03:15:31 SHORT | TAKE | **+182.50** | **+3,313.75** | 843.75 | no | FIRED and was right about the mechanism: "the buyers are a parent order still working" — HG went on to ~4.40 in LONDON. The trade survived an $843.75 adverse excursion, **$56.25 under the wall**, and the 07:00 phase-close exit is what banked it. |
| SI/NY 15:02:08 LONG | TAKE | -930.00 | +245.00 | 300.00 | **yes** | FIRED verbatim: "if S8's 60s sflow stays SELL at >= 10% for another five minutes with price below 26.6875, the shelf is broken and the trapped mass above becomes the whole afternoon's supply." It did, and it was. |
| HG/NY 15:32:46 LONG | TAKE | -930.00 | +182.50 | 43.75 | **yes** | FIRED verbatim: "if S8's 60s sflow turns sell at >= 10% while price is below 4.3168, the staircase has another rung." It had several. |

Three of three pre-mortems named the mechanism that decided the trade, and the two that named a
measurable trigger were both correct within minutes. Across four days the instrument has gone 0/11,
5/6, 2/5, 3/3. **The pre-mortem is now the best-calibrated object the reader produces, and it has
been ignored as a veto on every day it fired.** CC-M2-10.4 auto-logs them as hypotheses; on this
evidence the stronger form the reader proposed on day 2 (a pre-mortem naming a measurable mechanism
must become a term or the take is abandoned) deserves re-opening — it would have saved $1,860 today.

Also on record: the S10 reservation written into the against/pre-mortem fields before the seal
priced both losing seats correctly. SI's developing POC was $362.50 above the entry and the developing
VAH $750 above with the bar needing 26.8975 "outside the developing value area entirely"; HG's
developing POC was $931 above. Neither trade reached its POC. **S10 has now called the magnitude
correctly on both days it was read (day 3 §11, day 4), and it is still not in the triage index.**

## 7. E1D4-F7 — THE GRADE IS CALIBRATED ON THE POPULATION AND INERT INSIDE THE TAKES

`sigma_to_exit = S9 rv1800 * sqrt(runway/1800)` (CC-M2-10.5 form, unchanged from day 3 so the
calibration accumulates):

| grade | all rows n | mean close $ | winners | TAKE rows | TAKE mean $ |
|---|---|---|---|---|---|
| A | 60 | **+287.71** | 22 | 4 | -930.00 |
| B | 512 | +180.94 | 89 | 39 | -759.97 |
| C | 696 | +28.47 | 25 | 1 | +182.50 |

Monotone on the population for the second day running (A > B > C in both mean and winner rate), and
inverted inside the takes — because it is a magnitude-feasibility scale and this day's takes were
wrong about direction, so it ranked the losses by how far they could travel. Keep it as an ordering
statistic; it still must not gate anything (CC-M2-10.5 stands).

## 8. NKD PRODUCED EIGHT WINNERS — THE "NOTHING TO OFFER" CLAIM IS FALSIFIED, THE ABSTENTION WAS STILL RIGHT

Three sessions, 711 candidates, zero D-021 winners. Today: 312 candidates, **8 winners**, all NY
shorts between 15:07:05 and 15:33:58, on a session where NKD's mean candidate still lost $60.89 and
263 of 312 rows fail the live-book floor outright. The reader abstained (NKD replay $0) and every
mechanical arm that traded NKD lost money on it (-$955 to -$1,745). **What is falsified is the era
claim, not the abstention: NKD in E1 is a thin book with occasional real seats, and a rule that can
only see the book will keep missing them.** ERA_NOTES §26's "untradeable at the $1,000 bar" is
struck and replaced with the count.

## 9. SECTION-VALUE LEDGER (CC-M2-4.5), 10 deep reads of 1,268 calls

| section | deep reads that opened it | changed a call |
|---|---|---|
| S3 (path / swing chain / coverage / runway) | 10 | yes — the ZigZag chain is what told me the SI seat was a BREAK of a twice-held shelf and not a refail, and the HG seat a descending staircase; I wrote both down and took both anyway |
| S8 (flow windows / fuel map / through-book) | 9 | yes — every term of the rule that matters, and the fuel map's trapped mass (7,805 of 7,902 above the SI mid) was the correct warning |
| S4 (level ledger) | 5 | yes — the five-family shelf at 26.685-26.6975 is why the SI long looked like a floor, and the REJECTed levels above the HG entry are why that one was buying inside broken support |
| S9 (vol state) | 6 | **yes, and wrongly** — `jump_frac` is E1D4-F2 |
| S10 (volume profile) | 3 | **yes as a warning, ignored again** — it priced both losing seats before they were taken |
| S7 (book/queue) | 3 | yes — dBsz/min +3.00 vs dAsz/min -15.00 was the A4 read that made the SI long look right, and it was wrong within the minute |
| S5 (T-minus trajectory) | 3 | no — read for the record only; no term of this rule touches it (E1D4 pre-registration) |
| S13 (mechanics / class card) | 3 | no |
| S2, S12 | 2, 1 | no — S12 confirmed `event_in_session=0` on all 1,268 rows |
| S1, S6, S11 | 1, 1, 1 | no (opened once inside the single whole-sheet read) |

S6 and S11 are now 0-for-3,266. S10 is 2-for-2 on the days it has been opened and is the strongest
candidate for promotion into the triage index (defect D17).

## 10. DEFECTS AND BUILD ITEMS FOUND TODAY

* **D16 — the TRIAGE-INDEX-V2 header and D9 renames silently break three FROZEN consumers.** The V2
  extractor writes TWO comment lines (the version stamp) where V1 wrote one, and `e1d1_policy.py`,
  `e1d2_policy.py` and `baseline_replay.py` all parse with `open(index).readlines()[1:]`; V2 also
  renames `day_type`/`pct_range_hat` to `day_type_so_far`/`range_vs_hat_pct`, which the frozen
  day-1/day-2 policies read by name. Run as-is, `baseline_replay.py` raises `KeyError: 'cid'` and
  the frozen policies raise or silently lose terms. The frozen arms are the reader's scoreboard, so
  this is a reproducibility hazard, not a cosmetic one. **Fix ordered on the tooling lane, not here
  (frozen code must not be edited by the reader):** the extractor should emit a COMPAT view, or
  every consumer should switch to `startswith('#')` + alias columns. Today's baselines were run
  against `E1D4_TRIAGE_INDEX_COMPAT.tsv` (one comment line + both column spellings, identical data).
* **D17 — S10's developing POC/VAH/VAL are not in the triage index.** Two days, two correct
  magnitude calls, no way to triage on it. `d_POC`, `d_VAH`, `d_VAL`, `in_VA` are four numbers.
* **D14 remains open upstream.** The reader implemented the as-of prefix view in its own lane
  (`e1d4_asof.py`); `triage_index.py --as-of` is still the thing that has to exist before the BLIND
  round, because a blind reader should not have to build its own guard.
* **D13 status:** the renames ARE emitted by the current extractor; the VERSION stamp is emitted as
  a second header comment — which is exactly what breaks D16's consumers. The docstring is no longer
  wrong; the change was shipped without a consumer sweep.

---

# E1 STUDY POST-MORTEMS — DAY 5 (2021-07-07, SI + HG + NKD, day-complete, n=1,185)

Reader: opus-discretionary, fresh context (CC-M2-4.2). Sheets PORT-SHEETS-V1.1. Theses sealed in
commit `398f3e7` ("E1D5 theses sealed"); every S14/outcome below was opened after that commit.
Committed calls are never revised. Draw: the next chronological STUDY session per asset strictly
after 2021-07-06, warm-up sessions excluded (CC-M2-8.1) — SI/HG/NKD 2021-07-07, 1,185 candidates
(SI 391, HG 413, NKD 381). USED_CASE_LEDGER carries 0 prior hits on 20210707.

**THE WHOLE DAY WAS DECLARED BEFORE IT WAS SEEN.** CC-M2-13.4 fixed all three arms; `e1d5_policy.py`
declares each of them in full — the five inherited refusal terms, the exact side estimator, the
veto protocol — together with the estimator's pre-registered 5-right/2-wrong record on days 1-4 and
its pre-registered FAILURE of the mirror law. Nothing below can be re-read as a discovery.

**TAINT: CLEAN, with `AS-OF-PREFIX` on every TAKE and `VETO-TABLE-SCANNED` on the two seats (new
defect D18, §10).**

## 0. THE DAY, AND THE SCORE — THE FIRST POSITIVE-MEAN TAKE SET OF THE ROUND, AND STILL A LOSS

| ledger | calls | TAKE | mean take $ | mean skip $ | winner precision | replay $ | capture |
|---|---|---|---|---|---|---|---|
| **READER** | 1,185 | **15** | **+160.83** | -45.36 | **0.000** | **+115.00** | 0.014 |
| EARLIEST, all episodes (**BEST mechanical**) | 1,185 | 545 | -40.40 | -44.75 | 0.029 | **+4,412.50** | 0.545 |
| EARLIEST + cv >= 516 / 639 | 1,185 | 26/24 | +5.58/-53.96 | -44 | 0.038/0.042 | +3,380.00/+2,685.00 | 0.417/0.332 |
| YESTERDAY e1d1 (frozen) | 1,185 | **0** | — | -42.75 | — | 0.00 | 0.000 |
| YESTERDAY e1d2 (frozen) | 1,185 | 5 | +502.50 | -45.06 | 0.000 | +1,530.00 | 0.189 |
| YESTERDAY e1d3 (frozen) | 1,185 | 3 | -930.00 | -40.50 | 0.000 | -1,860.00 | -0.230 |
| YESTERDAY e1d4 (frozen) | 1,185 | 20 | -383.12 | -36.90 | 0.000 | -615.00 | -0.076 |

* **Margin over the best mechanical baseline: -$4,297.50** (round: +$2,380 / -$2,398 / +$928.75 /
  -$8,123.75 / -$4,297.50). Over frozen e1d1 **+$115.00**, e1d2 **-$1,415.00**, e1d3 **+$1,975.00**,
  e1d4 **+$730.00** — the reader beat three of its four frozen selves and lost to the fourth.
* Lift NA (SKIP mean negative). mean(take) - mean(skip) = **+$206.19**, positive for the first time
  since day 1. **0 of 15 takes walled** (day 4: 36 of 44); median take MAE $237.50.
* Day-complete census: SI n=391 mean +$0.08 (28 winners), HG n=413 -$76.81 (14), NKD n=381 -$49.78
  (4). LONG n=600 mean -$130.80 with **9** winners; SHORT n=585 +$47.56 with **37**. Day DP ceiling
  **$8,098.75**.

## 1. E1D5-F1 — THE FOUR-DAY META-FINDING BREAKS: THE SIDE IS A **PHASE** PROPERTY, NOT A SESSION PROPERTY

CC-M2-13.3 was built on "winners concentrate on ONE side per session (4/4 days)". This session has
winners **on both sides of the same asset**:

| asset | winners | where |
|---|---|---|
| SI | 28 | **2 LONDON LONGS** (07:04:28, 07:32:27) + **26 NY SHORTS** (13:03-15:52) |
| HG | 14 | **3 LONDON LONGS** (07:02:36-07:13:14) + **11 NY SHORTS** (14:07-14:28) |
| NKD | 4 | **4 TOKYO LONGS** (02:01:14-02:02:07) |

Five sessions, and the unit that has never once been split is the **(asset, PHASE)** cell: day 1 NY
shorts, day 2 NY longs, day 3 TOKYO longs, day 4 NY shorts, day 5 TOKYO longs + LONDON longs + NY
shorts. **The session-side state variable ordered in CC-M2-13.3 is measuring the wrong unit; the
phase-side state variable is the object that has 5/5 support.** That is also why the day-3 TOKYO
winners and the day-4 NY winners never coexisted in one rule: they are different cells, not
different days.

## 2. E1D5-F2 — THE SIDE ESTIMATOR IS 0 FOR 46, AND ITS FAILURE MODE IS EXACT AND MECHANICAL

The declared first-confirmed-outcome-sign estimator called **LONG on SI (08:50:56), LONG on HG
(09:01:35), SHORT on NKD (02:01:14)**. The day's winners are 26+11 NY SHORTS and 4 NKD TOKYO LONGS.
**The side gate passes 0 of the 46 winners.** Across all five sessions, on the ten asset-sessions
that produced winners:

* SIGN: 7 right, 3 wrong (2021-07-01 HG and SI, 2021-07-07 NKD).
* TIMING: **7 of 7 sign-correct confirmations arrived AFTER that asset-session's first winner.**
  Not one confirmation in five sessions has ever preceded the winner window it was meant to open.

And the mechanism of the failure is visible in one row. **NKD's confirmation at 02:01:14 was set by
`NKD-20210707-002147-S`, a 00:35:47 SHORT whose `f60_n=0, f60_vol=0, f5m_vol=0` — a DEAD-BOOK row
that P004 refuses outright.** NKD fell $1,000 into 02:01:14, the estimator stamped the session
SHORT at that second, and the four D-021 winners of the session are LONGS whose decision seconds are
02:01:14, 02:01:59, 02:02:05 and 02:02:07. **The first confirmed $1,000 move IS the move; its
confirmation second is its end.** That is the same object as the 2021-07-01 failure, now with the
mechanism named rather than inferred.

Two repairs are implied and neither is a new direction term: (i) the founder must itself be a
tradeable candidate (P004's live-book floor at minimum) — a dead-book row must never set session
state; (ii) the estimator must be PHASE-scoped (F1) and must expire, because a 09:01 LONDON
confirmation governing a 16:19 NY decision is what this day actually traded.

**MIRROR-LAW TABLE, five sessions (the side gate vs the opposite side gate, replay $):**
-3,568.75/+2,815.00 (**NO**) | +1,295.00/-822.50 | +808.75/-1,133.75 | +4,171.25/-4,347.50 |
-2,362.50/+1,828.75 (**NO**). Beats its mirror on **3 of 5** => fails CC-M2-13.1, exactly as
pre-registered.

## 3. E1D5-F3 — THE PRE-MORTEM VETOES WON THE DAY AND LOSE THE ROUND, AND BOTH HALVES ARE THE FINDING

**On this session, obeying the pre-mortems is worth +$2,477.50 of replay at a cost of zero winners.**

| pool | n | mean close $ | winners | walled |
|---|---|---|---|---|
| the 97 VETOED takes | 97 | **-679.42** | **0** | 0.732 |
| the 15 that STOOD | 15 | **+160.83** | 0 | **0.000** |

Both would-be seats were hard stop-outs: `HG-20210707-048882-L` -$930 (walled) and
`SI-20210707-050720-L` -$930 (walled), both refused by trigger V1 before the seal. Sole-block on the
day: V1 57 rows at -$830.99, V2 18 at -$190.07, V3 3 at +$111.67; **zero winners in any of them.**
Four days of "the pre-mortem named the death mechanism and I took the trade anyway" (0/11, 5/6, 2/5,
3/3) get their first day of obedience and the instrument pays.

**And the same three triggers applied mechanically to the CORE arm on all five sessions are
-$12,592.50 and cost 91 of 99 winners:**

| session | CORE takes/win/replay | CORE+VETOES takes/win/replay | delta | winners lost |
|---|---|---|---|---|
| 2021-07-01 | 146 / 22 / +3,570.00 | 16 / 0 / -771.25 | **-4,341.25** | 22 |
| 2021-07-02 | 196 / 26 / -2,471.25 | 46 / 0 / -1,752.50 | +718.75 | 26 |
| 2021-07-05 | 45 / 3 / +2,282.50 | 6 / 0 / -371.25 | **-2,653.75** | 3 |
| 2021-07-06 | 223 / 39 / +3,335.00 | 71 / 0 / -3,766.25 | **-7,101.25** | 39 |
| 2021-07-07 | 157 / 9 / -278.75 | 33 / 8 / +506.25 | +785.00 | 1 |
| **pooled** | 767 / 99 / +6,437.50 | 172 / 8 / -6,155.00 | **-12,592.50** | 91 |

The damage is **entirely V1** (§4). Sole-block over five sessions: **V1 403 rows at +$261.30 mean
with 71 winners refused**; V2 52 rows at -$131.32 with 3; V3 27 rows at -$447.36 with 1. So the
honest verdict on arm (b) is split and both halves matter: *a pre-mortem is an excellent detector of
what will kill THIS trade, and converting it into a standing rule inherits every weakness of the
object it names.* V2 and V3 (the fuel-map overhang and P018 two-stream opposition) survive as
refusals on all five sessions; V1 does not.

## 4. E1D5-F4 — P028 BAR_OUTSIDE_DEVELOPING_VALUE: BORN, MEASURED ON FIVE SESSIONS, AND DEAD IN ONE DAY

S10's developing value area was the round's best-behaved magnitude object (2-for-2 on the days it
was read, ignored both times). Registered prospectively as P028 and made mechanical for the first
time (`e1d5_s10.py`, the in-lane fix for defect D17), it is the day's veto trigger V1 — and the
five-session count kills it:

| session | bar INSIDE the developing VA (n / mean $ / winners / rate) | bar OUTSIDE (n / mean $ / winners / rate) | lift |
|---|---|---|---|
| 2021-07-01 | 93 / -31.21 / 0 / 0.000 | 939 / -2.02 / 48 / 0.051 | 0.00x |
| 2021-07-02 | 141 / -595.69 / 4 / 0.028 | 792 / +35.21 / 34 / 0.043 | 0.66x |
| 2021-07-05 | 41 / +61.31 / 0 / 0.000 | 588 / -43.27 / 8 / 0.014 | 0.00x |
| 2021-07-06 | 290 / -376.03 / 3 / 0.010 | 973 / +245.15 / 133 / 0.137 | 0.08x |
| **2021-07-07** | **227 / +102.79 / 29 / 0.128** | 952 / -76.92 / 17 / 0.018 | **7.15x** |
| **POOLED** | 792 / -214.77 / 36 / 0.0455 | 4,244 / +39.08 / 240 / 0.0566 | **0.80x** |

It beats its mirror on **one of five** sessions. **P028 is DEAD ON BIRTH, in the P014/P026 class**,
and it is the third time this round that a magnitude object has been minted on the sessions that
made it look right. The give-back question (§39.5, §42) is still open and now has three corpses.
What survives is the *measurement*: `d_POC/d_VAH/d_VAL/in_VA/bar_outside_va` are now extracted for
all five study days (`artifacts/cache/port/m2/triage/E1D{1..5}_S10.tsv`) and the census can use them
without re-reading 5,000 sheets.

## 5. E1D5-F5 — P025 IS 276-FOR-276, AND IT IS NOW THE ONLY OBJECT WITH FIVE CLEAN SESSIONS

Runway to the binding (phase-close) exit >= 12,000s passes **46 of 46 winners today** (minimum
winner runway **19,653s**) after 230 of 230 on days 1-4. Five day-complete sessions, **276 D-021
winners, zero exceptions**, and **0 winners in the 304 rows below 12,000s**. Term retention on
today's winners for contrast: T2 runway 46/46, T1 live book 44/46, T3 freshness 41/46, T4
aggression-at-magnitude 33/46, T5 magnitude floor **23/46**.

## 6. E1D5-F6 — THE MAGNITUDE FLOOR IS THE TERM THAT COST NKD, AND IT IS THE DAY-3 ERROR REPEATING

NKD produced 4 D-021 winners (TOKYO longs, 02:01:14-02:02:07, certs $1,045-$1,157.50, MAEs
$37.50-$150). All four carry `terms=11110`: **they pass the live book, the runway, the freshness and
the aggression test, and they fail T5's ABSOLUTE 200-contract floor** with 5-minute volumes of
118-140 contracts. Their RELATIVE volumes are **41.5%-45.0% of the phase's total** — five times the
8% relative clause. The floor reads `v5 >= 200 AND (v5 >= 500 OR v5 >= 8% of phase vol)`, so the
absolute 200 gate fires before the relative clause can rescue them. ERA_NOTES §33 wrote the law
after day 3 ("settle a threshold on the pooled pool, never on the replay") and the *form* of the
term still carries an absolute contract count across three assets whose multipliers differ 5x and
whose thin phases trade in tens. **The repair is one line: make the floor relative-OR-absolute at
the FLOOR too (`v5 >= 200 OR v5 >= 8% of phase vol`), not relative-OR-absolute only above it.**
The reader's fifth consecutive NKD abstention scored $0 against -$607.50 for the best mechanical
arm, so the abstention was again not punished — but for the second session running the claim that
NKD has nothing to offer is false, and it is now this rule's own floor that hides it.

## 7. E1D5-F7 — THE TWO SEATS, AND WHAT THE VETO CHAIN ACTUALLY BOUGHT

| seat | call | close $ | peak $ | MAE $ | walled | pre-mortem verdict |
|---|---|---|---|---|---|---|
| HG/NY 16:19:25 LONG | TAKE | **-205.00** | +463.75 | 525.00 | no | The conditional FIRED as written: the 5m flow turned sell and price went back under the developing VAL 4.3090. Wrong trade, right mechanism, and the flip threshold named it. |
| SI/NY 16:38:54 LONG | TAKE | **+320.00** | +732.50 | 237.50 | no | The bounce held; the "16:37 high was the whole bounce" mechanism did not fire within the phase. Best call of the day and still $680 under the bar. |

The veto chain moved HG/NY from 13:34:42 (-$930, walled) to 16:19:25 (-$205) and SI/NY from
14:05:20 (-$930, walled) to 16:38:54 (+$320): **+$1,975.00 of seat value from four vetoes**, of
which the two V1 vetoes contributed $1,860 and the V2/V3 chain the rest. The intermediate vetoed
candidates were -$30 (HG 16:07:41), -$930 walled (SI 16:12:52) and **+$307.50 (SI 16:29:29, the V3
veto — the one veto that cost money)**.

## 8. E1D5-F8 — THE GRADE BROKE ITS MONOTONE RUN

`sigma_to_exit` (CC-M2-10.5 form, unchanged since day 3): A n=42 mean **-$88.63 with 0 winners**;
B n=468 -$44.29 with **34**; C n=675 -$38.82 with 12. Two days of population monotonicity end here,
and they end at the top: the A cell is the worst mean AND has no winners. Inside the takes the
ordering is right for once (A n=8 +$257.50, B n=7 +$50.36) on n=15. The grade remains disqualified
as a judge-aux target (CC-M2-10.5); this is its third distinct behaviour in three days.

## 9. SECTION-VALUE LEDGER (CC-M2-4.5), 10 deep reads of 1,185 calls

| section | deep reads that opened it | changed a call |
|---|---|---|
| S3 (path / ZigZag / coverage / runway) | 10 | **no** — it argued for two more vetoes (session COVERAGE 110.5% and 126.4%) and I declined, because the capacity family is 0-for-2 as a refusal. Declining was right: those rows are not where the winners were either. |
| S8 (flow windows / fuel map / through-book) | 9 | **yes** — minted V2 (fuel-map overhang) and half of V3; 21 vetoes, all correct on the day and 4-of-5 sessions in the census |
| S4 (level ledger) | 8 | no — the virgin OR_EXT cluster under the SI seat is why that take stood, but no term reads it |
| S5 (T-minus trajectory) | 8 | **yes, via V3** — `mid_slope_$/min(T-1m)` is half of P018, the only veto with a five-session positive record |
| S7 (book/queue) | 8 | no — read for the NKD abstention (c2f 23.05 on 19 trades in 300s) |
| S10 (volume profile) | 7 | **yes, and it is the day's whole ambiguity** — V1 saved $1,860 of seats today and refuses 71 winners over five sessions (§4) |
| S9 (vol state) | 6 | no — `jump_frac` is dead since E1D4 and was read only for the record |
| S2 | 4 | no | 
| S11, S12, S13, S1 | 3, 2, 2, 2 | no |
| S6 | 1 | no |

S6 and S11 are now **0-for-4,451**. S10 has changed calls on the two days it was read and is
value-destroying over five; S8 is the only section with a five-session positive record.

## 10. DEFECTS AND BUILD ITEMS FOUND TODAY

* **D18 — THE VETO WALK RE-OPENS SCAN-EXPOSED (new, named by the reader).** CC-M2-13.4(b) asks for
  a pre-mortem per TAKE; making that measurable over 112 takes rather than 2 required grading the
  whole take list against the three triggers, and that table was read as a table. Every trigger is
  a pure function of one row (`e1d5_veto.py`), so a prefix-driven walk returns the identical seat
  chain and the CALLS are mechanically unexposed — but the reader's choice of which rows to
  deep-read was made with a day-complete table in front of it, and the table's `bar_px` column is
  `mid`-derived. Row taint `VETO-TABLE-SCANNED` on the two seats. **Fix: the veto walk must be
  driven by the same as-of stepper as the index (D14), which is still not at HEAD.**
* **D14 STILL NOT LANDED.** `triage_index.py --as-of` exists in the tooling lane's WORKING TREE and
  is in no commit; the reader used its own `e1d5_asof.py` for the third day running. A blind reader
  must not have to build its own leak guard.
* **D17 ANSWERED IN-LANE, STILL OWED UPSTREAM.** `e1d5_s10.py` extracts S10's developing
  POC/VAH/VAL/in_VA for a whole day in ~10s and has now been run over all five study days. The four
  columns belong in the triage index; the ledger's verdict on the object (§4) does not change that.
* **T5's ABSOLUTE FLOOR (§6)** is a one-line correctness bug in the reader's own inherited rule, not
  a sheet defect, and it is recorded as such.

---

# E1 STUDY POST-MORTEMS — DAY 6 (2021-07-08, SI + HG + NKD, day-complete, n=1,618)

Reader: opus-discretionary, fresh context (CC-M2-4.2). Sheets PORT-SHEETS-V1.1. Theses sealed in
commit `10b255b` ("E1D6 theses sealed"); every S14/outcome below was opened after that commit.
Committed calls are never revised. Draw: the next chronological STUDY session per asset strictly
after 2021-07-07, warm-ups excluded (CC-M2-8.1) — SI/HG/NKD 2021-07-08, 1,618 candidates
(SI 515, HG 389, NKD 714). USED_CASE_LEDGER carries 0 prior hits on 20210708.

**THE DAY WAS THE CC-M2-15.5/16.1 SIDE-EVIDENCE STUDY, DECLARED BEFORE IT WAS SEEN.** The primary
object is `provenance/port_m2/E1D6_CELL_SIDE_LEDGER.md`: nine ex-ante (asset, phase) side calls with
named evidence, each committed BEFORE its cell's first candidate row, from as-of stepper briefs, and
two competing declared estimators (P029 PHASE_SIDE_PRIOR, E1D6-CS) each registered WITH its
mirror-law failure before any cell was called.

**TAINT: `CLEAN;AS-OF-PREFIX` on all 1,618 rows; `FORECAST-TRUTH-EXPOSED` on the 79 TAKEs
(defect D19, §10).** HEAD V3 tooling end-to-end: `triage_index.py --drive-step 300` (275 verified
prefixes) drove the cell briefs AND the veto walk, and `e1d6_asofwalk.py` proves prefix-identity on
all 1,618 rows with 0 mismatches — **defect D18b is closed.**

## 0. THE DAY, AND THE SCORE — THE ROUND'S BEST TAKE PRECISION AND A LOST REPLAY

| ledger | calls | TAKE | mean take $ | mean skip $ | winner precision | replay $ | capture |
|---|---|---|---|---|---|---|---|
| **READER** | 1,618 | **79** | -71.77 | -59.78 | **0.203** | **-988.75** | -0.091 |
| EARLIEST, all episodes (**BEST mechanical**) | 1,618 | 675 | -50.19 | -67.65 | 0.043 | **+1,228.75** | 0.113 |
| YESTERDAY e1d1..e1d5 (frozen) | — | 0/3/4/31/46 | — | — | — | 0 / -1,885 / -447.50 / -2,195 / -527.50 | — |

* **Margin over the best mechanical baseline: -$2,217.50** (round: +$2,380 / -$2,398 / +$928.75 /
  -$8,123.75 / -$4,297.50 / **-$2,217.50**). Beat two of five frozen selves (+$896.25 vs e1d2,
  +$1,206.25 vs e1d4).
* **Winner precision 0.203 — 16 D-021 winners in 79 takes against a 5.25% base rate (3.9x), the
  round's best day-complete take set** — and the replay is negative anyway. That contradiction is
  the day's whole lesson (§3).
* Day-complete census: SI n=515 mean -$13.33 (43 winners), HG n=389 -$24.62 (17), NKD n=714 -$113.77
  (25). **85 winners**, base rate 5.25%. Day DP ceiling **$10,855.00**.

## 1. E1D6-F1 — THE CELL-SIDE CALLS: 3 OF 5, AND THE READER BEAT BOTH OF ITS OWN ESTIMATORS

| cell | truth | winners | READER | P029 | E1D6-CS |
|---|---|---|---|---|---|
| HG/LONDON | SHORT | 17 | **SHORT ✓** | LONG ✗ | NOCALL |
| SI/LONDON | LONG | 14 | SHORT ✗ | LONG ✓ | SHORT ✗ |
| NKD/LONDON | SHORT | 24 | **SHORT ✓** | LONG ✗ | SHORT ✓ |
| NKD/NY | LONG (n=1) | 1 | SHORT ✗ | SHORT ✗ | SHORT ✗ |
| SI/NY | SHORT | 29 | **SHORT ✓** | SHORT ✓ | LONG ✗ |
| HG/TOKYO, SI/TOKYO, NKD/TOKYO, HG/NY | **NONE** | 0 | — | — | — |

**READER 0.600, P029 0.400, E1D6-CS 0.250.** The evidence that WORKED, named:
* **HG/LONDON and NKD/LONDON (both correct, both discretionary overrides of P029)** were called on
  ONE object: SI's TOKYO fuel map, `7,424 above / 1,211 below / 8,635` = **86% of Asian silver
  volume trapped ABOVE the mid with phase sflow -665**, plus NKD's own `956/280/1,312` = 73%. A
  cross-asset supply overhang at the phase boundary called the direction of two other cells for the
  next six hours. Those two cells produced 41 of the day's 85 winners and both of the reader's
  winning seats (+$1,338.75 and +$1,282.50).
* **SI/NY (correct, and taken AGAINST the reader's own composite)** was called on
  `S10 d_POC = +$1,362 with in_VA = 0` — SI's mid stood above the developing VAH after a $1,450
  London rally, i.e. the session's volume had been built $1,300 lower. The NY cell then produced 29
  SHORT winners. **This is the first time an S10 field has predicted a SIDE rather than a
  magnitude** (P028 died as a magnitude veto on day 5) and it is the day's most transferable object.

The evidence that FAILED, named:
* **SI/LONDON, the worst call of the day.** The reader read SI's OWN 86%-trapped-above fuel map as a
  reason to short SI, and SI rallied **+$1,450 in London** and produced 14 LONG winners. The seat
  cost -$930 with an MAE of **$1,775**, the largest adverse excursion of the round.
  **The identical field called two other cells correctly and its own cell exactly wrong.** The
  mechanism is now stated: an overhang is SUPPLY to the assets that must follow it and FUEL to the
  asset that carries it — 86% trapped above IS the short-covering bid when the sellers are done.
  This is P009 FUEL_POLARITY, dead since the warm-up, resurrected as component C4 and killed again.
* **NKD/NY (n=1 winner).** The reader called SHORT on a session at `cov_sess 254%` and named the
  exhaustion in the pre-mortem in writing; the single winner is a LONG. The mean-reversion family
  was right and the reader traded against it, as pre-registered.
* **The cross-asset coherence component C5 is falsified on this session**: SI's LONDON was +$1,450
  while HG's was -$1,425. The metals are NOT one trade, and the reader wrote that down at the NY
  cell open before any NY call was made.

## 2. E1D6-F2 — P029 PHASE_SIDE_PRIOR: MINTED WITH ITS MIRROR FAILURE ON RECORD, AND BROKEN IN ONE SESSION

P029 (TOKYO/LONDON -> LONG, NY -> SHORT) was 11 of 12 winner-bearing cells over five sessions and
was registered before the day as FAILING the mirror law (4 of 5 sessions). On 2021-07-08 it scores
**2 right / 3 wrong**, and the break is not marginal: **both metals' LONDON cells and NKD's LONDON
cell went the way P029 forbids, and NKD's NY cell went LONG.** Six-session pooled: **13 right / 4
wrong on 17 winner-bearing cells; sessions won 4, lost 2.** Replay as a gate: **-$3,320.00**, the
worst arm of the day bar the composite.

**The finding is not that P029 is dead — it is that its content was an ERA-PERIOD TREND, not a clock
mechanism.** Days 1-5 were sessions in which metals were bid in Asia/Europe and sold in NY;
2021-07-08 is the session on which the Asian bid failed, and every cell that followed inverted. A
one-field phase label cannot carry that, and the honest disposition is a FEATURE (the cell's phase,
interacted with the leading state) and never a rule — the fifth consecutive object of this round to
reach that verdict.

## 3. E1D6-F3 — THE CONTRADICTION OF THE DAY: 0.203 PRECISION, 0.600 CELL-SIDE ACCURACY, AND A LOST REPLAY

| arm | takes | mean take $ | precision | replay $ | capture |
|---|---|---|---|---|---|
| CORE alone | 200 | -215.28 | 0.105 | +148.75 | 0.014 |
| **CORE + ORACLE cell side** | 50 | **+1,111.87** | **0.540** | **+5,493.75** | **0.506** |
| CORE + READER cell side (the day's calls) | 120 | -122.76 | 0.158 | **-988.75** | -0.091 |
| CORE + READER MIRROR | 160 | -341.60 | 0.050 | **+1,295.00** | 0.119 |

**The oracle cell side is worth +$5,345 of replay over CORE on ONE session (capture 0.506) — the
phase-grain version of CC-M2-15.2's day-grain "$700 a session", and it is far bigger here. The
reader was 3-for-5 on that object and captured NONE of it, and its own MIRROR beat it by $2,283.**

The reconciliation is arithmetic and it is the round's most important instrument finding:

| cell | reader's seat | close $ | cell winners |
|---|---|---|---|
| HG/TOKYO 00:11:21 LONG | HG-20210708-000681-L | -242.50 (walled) | **0** |
| NKD/TOKYO 02:02:00 LONG | NKD-20210708-007320-L | -955.00 (walled) | **0** |
| SI/TOKYO 03:02:17 LONG | SI-20210708-010937-L | -930.00 (walled, MAE $1,087) | **0** |
| HG/LONDON 07:00:26 SHORT | HG-20210708-025226-S | **+1,338.75** | 17 |
| SI/LONDON 07:00:34 SHORT | SI-20210708-025234-S | -930.00 (walled, MAE $1,775) | 14 (LONG) |
| NKD/LONDON 09:15:33 SHORT | NKD-20210708-033333-S | **+1,282.50** | 24 |
| SI/NY 13:00:43 SHORT | SI-20210708-046843-S | **+1,120.00** | 29 |
| HG/NY 13:02:33 SHORT | HG-20210708-046953-S | -717.50 | **0** |
| NKD/NY 13:32:17 SHORT | NKD-20210708-048737-S | -955.00 (walled) | 1 (LONG) |

**FOUR OF THE NINE CELLS CONTAINED NO D-021 WINNER ON EITHER SIDE, AND THE READER SPENT A SEAT IN
ALL NINE.** The three cells it called correctly returned +$3,741.25 between them; the six others
returned -$4,730.00. **A cell-side call answers WHICH SIDE and never WHETHER THE CELL HAS A SEAT,
and under one-position-per-cell seating the second question is worth more than the first.**
Corollary, and it is the good news: **in all three correctly-called cells the FIRST core-admitted
candidate was an excellent seat** (+$1,338.75, +$1,282.50, +$1,120.00 — two of them D-021 winners
with MAEs of $106.25 and $25.00). Right cell side + EARLIEST is a complete entry rule; the missing
term is a cell-level feasibility gate.

## 4. E1D6-F4 — P030 CELL_VOL_CONCENTRATION: THE MISSING TERM, MEASURED ON ALL 54 CELLS OF THE ROUND

The obvious ex-ante candidate for "does this cell have a seat" is the volatility state at the cell's
own open. `S9 rv_nowcast w1800` on the cell's FIRST candidate row, over **all 54 (asset, phase)
cells of the six day-complete study sessions, 361 D-021 winners**:

| rv1800 at cell open | cells | cells with >=1 winner | winners | share of all winners |
|---|---|---|---|---|
| < 100 | 13 | 2 | 12 | 3.3% |
| 100-150 | 13 | 2 | 20 | 5.5% |
| 150-250 | 19 | 6 | 111 | 30.7% |
| **>= 250** | **9** | **7** | **218** | **60.4%** |

Monotone in all four bands. **The 9 highest-vol cells (17% of cells) hold 60% of the round's
winners; the 26 lowest-vol cells (48%) hold 9%.** On this day the three TOKYO cells the reader
seated for -$2,127.50 open at rv1800 **97.8 / 50.0 / 100.0** — all in the bottom band, all with
zero winners.

**IT IS REGISTERED AS A CONCENTRATOR AND NOT AS A RULE, AND THE THRESHOLD IS NOT SETTLED — a floor
at 150 would have refused HG/LONDON (rv 142.5), the day's BEST SEAT (+$1,338.75) and 17 winners.**
That is stated first because this round has three corpses (P014, P026, P028) from objects minted on
the sessions that made them look right, and because ERA_NOTES §41's method law demands the pooled
statistic. Pooled at a 150 floor: 329 of 361 winners retained on 28 of 54 cells, but 0 of 8 on day 3
and 17 of 85 lost today. **It has no mirror to fail** (it is a magnitude/feasibility object like
P025), which is exactly why it belongs in the classifier's feature set beside P025 and not in an
entry rule.

## 5. E1D6-F5 — P025 IS 361-FOR-361

Runway to the binding (phase-close) exit >= 12,000s passes **85 of 85 winners today, minimum winner
runway 12,324s**, after 276 of 276 on days 1-5. **Six day-complete sessions, 361 D-021 winners, zero
exceptions, and 0 winners in the 540 rows below 12,000s.** Term retention on today's 85 winners for
contrast: T2 runway 85/85, T5 magnitude (repaired) 74/85, T1 live book 72/85, T4 aggression 62/85,
T3 freshness 59/85. The census verdict stands (CONCENTRATOR, 3.70x, not an edge) and the count keeps
growing under it.

## 6. E1D6-F6 — THE T5 REPAIR RESTORES 46 OF THE DAY'S 85 WINNERS AND DOES NOT MAKE MONEY

CC-M2-16.4 approved the one-line repair (`v5 >= 200 OR v5 >= 8% of phase volume`). Measured on the
day: **545 rows the day-5 form refused are admitted, and they contain 46 of the day's 85 D-021
winners** — the defect was far larger than the four NKD rows that exposed it. But their mean
certificate is **-$21.54** and inside the reader's take set the repaired rows are 39 takes at
**-$58.21** with 10 winners; the repair is what created the NKD/NY seat, which closed **-$955.00**.
**A magnitude floor that recovers winners AND their losing neighbours is a concentrator, not an
edge** — the same verdict every censused object of this round has received, arrived at here in one
session by the reader's own count.

## 7. E1D6-F7 — THE VETOES REMOVED A WORSE POOL AND MOVED NOTHING

41 of the 120 core+side TAKEs carried a V2 or V3 veto. Vetoed pool **-$221.01 with 3 winners**;
standing pool **-$71.77 with 16**. **Replay delta: exactly $0.00** — no veto touched a seat-spender,
because under CC-M2-10.3 the seat is the FIRST admitted row of a cell and the vetoes fired later.
Sole-block over the day: **V2 99 rows at -$218.83 with 1 winner** (sixth session net-positive);
**V3 170 rows at -$104.15 with 10 winners — V3's worst session by far** (its five-session record was
27 rows, -$447.36, 1 winner). CC-M2-16.2's family-level grading is what keeps V3 alive; one more
session like this and it is a P028-class object.

**THE PROTOCOL LESSON: a veto that cannot move a seat cannot move the replay.** Day 5's +$2,477.50
veto delta came entirely from vetoes that fired ON the seat-spender. The veto's value is not in the
pool statistics the round has been quoting; it is in whether it fires on the first admitted row of a
cell. That is a one-line change to how veto families are censused.

## 8. E1D6-F8 — THE GRADE, AND THE THREE-DAY A-CELL PROBLEM

`sigma_to_exit` (CC-M2-10.5 form, unchanged since day 3): population A n=34 mean -$48.01 with
**0 winners**; B n=632 -$100.77 with 30; C n=952 -$33.99 with 55. Inside the takes: B n=33 -$40.80
with 5, C n=46 -$93.99 with 11. **The A cell has now had zero winners on three consecutive days**
(day 5: 0 of 42; day 6: 0 of 34) while holding the highest volatility×runway product. That is not
noise any more: the grade's top band is selecting rows whose runway is long BECAUSE the phase just
opened and whose rv is high BECAUSE the move already happened. It stays disqualified as a judge-aux
target (CC-M2-10.5) and the diagnosis is now specific enough to rebuild it.

## 9. SECTION-VALUE LEDGER (CC-M2-4.5), 5 sheet deep reads + 9 cell-open briefs of 1,618 calls

| section | reads that opened it | changed a call |
|---|---|---|
| S8 (flow windows / FUEL MAP / through-book) | 9 briefs + 5 sheets | **yes — it is the day's primary evidence in 3 of the 5 scorable cells, and it went 2 right / 1 wrong** (HG/LONDON ✓, NKD/LONDON ✓, SI/LONDON ✗ — the same field, the same session) |
| S10 (volume profile, developing POC/VAH/VAL/in_VA) | 9 briefs + 4 sheets | **yes — `d_POC +$1,362 / in_VA=0` is the whole SI/NY call and SI/NY produced 29 winners.** First SIDE use of S10 in the round |
| S3 (path / coverage / runway) | 9 briefs + 5 sheets | **no as direction, yes as the round's standing refusal** (P025 85/85) — and its capacity row correctly warned on NKD/NY, where the reader traded against it and lost |
| S4 (level ledger) | 3 | no — the OR_EXT/PRIOR_DAY shelf under the SI/NY entry was the named flip threshold and the short worked anyway |
| S9 (vol state) | 9 briefs | **yes, retrospectively — rv1800 at the cell open is P030** (§4) |
| S7 (book/queue) | 3 | no — read for the NKD pre-mortems (c2f_300 14.71) |
| S2, S12 | 9 briefs | no — S12 confirmed `event_in_session=0` (the P029 regime check) and was right that the class applied; the class still broke |
| S11 | 2 | no — the cross-asset read was taken from the index's own prefix, not from S11 |
| S5 | 9 briefs | no — corroboration only, never primary (momentum is 3-for-3 value-destroying) |
| S6 | 0 | — |

**S6 is now 0-for-6,069.** S8 and S10 are the only sections that carried a call today, and S10's
first side-use was the day's best call.

## 10. DEFECTS AND BUILD ITEMS FOUND TODAY

* **D19 — THE REGIME-FORECAST FILE CARRIES TRUTH BESIDE ITS PREDICTIONS (a leak class, self-reported).**
  `artifacts/cache/port/m2/regime_forecast/forecast_{SI,HG,NKD}.tsv` carry `y_day_type`,
  `y_range_usd`, `y_share_{TOKYO,LONDON,NY}` and `y_menu` — the REALISED session outcomes —
  populated for 2021-07-08, in the same rows as the (empty) predictions, in the file the day-6 brief
  directs the reader to use. Diagnosing D20 therefore exposed each asset's realised session range,
  day-type class and per-phase range share BEFORE the day was called. They are unsigned magnitude
  facts carrying no side and no candidate outcome, so the nine cell-side calls (pure side calls) are
  not informed by them; the day's TAKE rows nonetheless carry `FORECAST-TRUTH-EXPOSED` and the
  take-set economics are quotable only with that stamp. **The `y_*` columns are already duplicated
  in `truth_{SI,HG,NKD}.tsv`; the fix is to drop them from the forecast file.** The index join is
  clean (it reads only the three `*_hat` fields).
* **D20 — THE REGIME FORECASTER HAS NO 2021 PREDICTIONS AT ALL, SO CC-M2-14.3 IS UNTESTABLE IN E1.**
  `predicted_day_type_prob`, `range_hat_vs_trailing` and `menu_hat` are `.` on all 1,618 rows of this
  day because `p_expansion` and `range_hat_usd` are EMPTY on every 2021 row of all three forecast
  files (SI 462/462, HG 774/774, NKD 777/777; first populated predictions 2022, SI's in 2022 H2).
  The accepted forecaster's walk-forward has no training window inside E1. **CC-M2-14.2(a)'s
  integration delivers nothing to study days 6-8 or to the E1 BLIND round, and the composition
  hypothesis (predicted day-type x side estimator x refusal core) cannot be tested until E2.** This
  is the day's headline defect and it bears directly on the CC-M2-6 teacher gate, which is scored on
  E1 BLIND.
* **D18b CLOSED.** The veto walk and the triage walk both ran through HEAD's stepper
  (`triage_index.py --drive-step 300 --drive-out E1D6_DRIVE`, 275 verified prefixes);
  `e1d6_asofwalk.py` proves PREFIX-IDENTITY (1,618 rows, 0 mismatches between the call at a row's
  own reveal cut and the day-complete call) and re-derives the nine-cell seat chain chronologically.
  No day-complete table was scanned to choose a deep read.
* **DECLARED ACCEPTED EXPOSURE (new, named rather than assumed):** the ordered list of
  (asset, phase, first-candidate second) was known before the calls. It carries no price and no
  outcome and is the same class as the per-asset candidate counts every prior day declared, but it
  is now on the record as a named exposure rather than an unexamined convenience.
* **THE VETO CENSUS FORM IS WRONG (build item).** Veto families are graded on pooled sole-block
  statistics; §7 shows a family can be strongly net-positive on the pool and worth exactly $0 in
  replay because it never fires on a seat-spender. **Veto censuses must report the seat-spender
  sub-population separately.**
* **USED-CASE LEDGER GAP FOUND AND BACKFILLED.** `USED_CASE_LEDGER.tsv` carried days 1-4 and the
  warm-up but **not 2021-07-07 (day 5)** — the day-5 lane never ran `used_cases record`, so a
  day-complete STUDY session was un-tainted in the one-way taint register and could have entered a
  BLIND draw. Backfilled here for both 2021-07-07 and 2021-07-08 (2,803 entries, round
  `E1D5-E1D6-backfill`). **The seal step must call `used_cases record` — it is currently a manual
  step outside every day's tooling.**

---

# E1 STUDY POST-MORTEMS — DAY 7 (2021-07-09, SI + HG + NKD, day-complete, n=1,388)

Reader: opus-discretionary, fresh context (CC-M2-4.2). Sheets PORT-SHEETS-V1.1, tooling HEAD V3.
Theses sealed in `da74ecc` (content) with marker commit `02304f6` — **every S14 below was opened
after that commit**. Committed calls are never revised (READER_BRIEFING §1).
Draw: the next chronological STUDY session per asset after 2021-07-08, warm-ups excluded — all three
assets on **2021-07-09** (SI 315, HG 407, NKD 666). USED_CASE_LEDGER: 0 prior hits, +1,388 recorded
by the seal itself (CC-M2-17.4 auto-record verified).
Primary deliverable: `provenance/port_m2/E1D7_CELL_LEDGER.md` — the CC-M2-17.1 THREE-STAGE per-cell
ledger (SEAT + SIDE, committed before each cell's first candidate row).

## 0. THE DAY, AND THE SCORE

**123 D-021 winners in 1,388 candidates (8.9%, the round's highest base rate) AND ALL 123 ARE
LONGS.** Five of nine cells carry winners: NKD/TOKYO 68, HG/LONDON 22, SI/LONDON 15, NKD/LONDON 11,
SI/NY 7. Empty: HG/TOKYO, SI/TOKYO, HG/NY, NKD/NY.

| ledger | calls | TAKE | mean take $ | mean skip $ | winner precision | replay $ | capture (DP $11,636) |
|---|---|---|---|---|---|---|---|
| **READER** | 1,388 | 55 | **+282.27** | -29 | 0.109 | **-432.50** | -0.037 |
| BEST mechanical (EARLIEST + cv>=516) | 1,388 | 26 | -224 | -13 | 0.000 | **+535.00** | 0.046 |
| best frozen predecessor (e1d5) | 1,388 | 26 | +192 | -20 | 0.077 | +310.00 | 0.027 |
| worst frozen predecessor (e1d6) | 1,388 | 81 | -407 | +8 | 0.000 | -5,136.25 | -0.441 |

**Margin over the best mechanical baseline: -$967.50** (round: +2,380 / -2,398 / +928.75 / -8,123.75
/ -4,297.50 / -2,217.50 / **-967.50**). Beat 1 of 6 frozen selves. Full table + the three-stage
decomposition + the veto split: `provenance/port_m2/baselines/E1D7_BASELINE_SCORES.md`.

**SEAT-CALL ACCURACY 4/9 = 0.444** (against 0.556 for seating every cell), **YES-precision 0.500**
against a pre-registered 0.688, **winner recall 0.146 against a pre-registered 0.884.**
**SIDE-CALL ACCURACY 2/5 = 0.400**, its own mirror 0.600. On the same five cells **P029 scored
0.800** and the day's declared primary instrument **S2a/P031 scored 0.250** while the twice-dead
**P009 own-asset reading scored 0.750**.

## 1. THE HEADLINE: P025 IS BROKEN, AND THE OBJECT THAT BREAKS IT IS VOLATILITY

Six day-complete sessions, 361 D-021 winners, zero exceptions: every winner had **>= 12,000s of
runway to its binding exit**, minimum 12,324s, and no row below the floor had ever won. It was the
round's only unbroken object and the reader's T2.

**2021-07-09: 54 of the day's 123 winners sit BELOW the 12,000s floor. The minimum winner runway is
2,058 seconds — 34 minutes.** They are NKD/TOKYO longs entered 04:09-07:55 and exiting at the 08:30
TOKYO phase close, and they close at **+$1,282 to +$3,845**, the largest certificates of the round.

**THE MECHANISM IS NOT SUBTLE AND IT REPAIRS THE OBJECT RATHER THAN KILLING IT: runway buys the bar
only at the prevailing volatility.** NKD's TOKYO phase ran `rv1800` 278-602 at those winners' own
decision seconds against a $1,344 `q50` — the tape was travelling $1,000 in half an hour, so 34
minutes of runway was enough. On the six prior sessions the winners lived at `rv1800` 150-370 where
$1,000 takes hours, and the 12,000s floor was the shadow of that. **P025's true form is
`runway x rv1800 >= the bar`, i.e. the `sigma_to_exit` product the round has been computing as a
GRADE and disqualifying as a judge-aux since day 3 (ERA_NOTES §69).** The two objects are the same
object and one of them has been on every sheet all along.
**Cost to the reader today: T2 refused 54 winners; its retention on the day's winners is 69/123.**

## 2. WHY STAGE 1 INVERTED: THE CELL-OPEN ANCHOR GOES STALE (P030's real defect)

S1\* was pre-registered at precision 0.688 / winner recall 0.884 on 54 cells and scored 0.500 /
**0.146** on nine. The whole gap is one cell: **NKD/TOKYO, 68 winners (55% of the day), median
certificate +$3,020 — and `rv1800` at its cell open (00:02:15) was 53.0, P030's BOTTOM band.** Its
winners arrive at 04:09-07:55, **four to eight hours later**, when `rv1800` is 278-602 (top band).
The TOKYO phase is 8.5 hours long. A 30-minute volatility nowcast taken at its first second is not a
statement about it, and P030's day-6 measurement did not notice because five of its six winner cells
were LONDON/NY cells whose winners arrive within an hour of the open.

**MEASURED REPAIR, on all seven day-complete sessions (8,077 rows, 484 winners), reading `rv1800` at
the CANDIDATE'S OWN ROW instead of the cell open:**

| rv1800 at the row | rows | winners | winner rate | mean cert $ |
|---|---|---|---|---|
| < 100 | 80 | 0 | 0.0000 | -127.58 |
| 100-150 | 232 | 8 | 0.0345 | -28.71 |
| 150-250 | 1,673 | 27 | 0.0161 | -31.01 |
| **>= 250** | **6,092** | **449** | **0.0737** | -10.77 |

**449 of 484 winners (92.8%) are in the top band and the band below holds 35 winners in 1,985 rows
(1.76%).** As a CONCENTRATOR it is weak (1.23x on a 5.99% base); as a REFUSAL it is strong (0.29x
below 250, refusing 25% of rows for 7% of winners) — the same shape as P004 and P025.
**Stage 1 is therefore not a per-cell constant. It is a ROLLING feasibility state**, and the
day-6 formulation (one call per cell, fixed at the open) is a mis-specification of the estimand that
CC-M2-17.1 named. This is the day's most transferable finding.

## 3. THE PRE-REGISTERED COST CAME DUE — TWICE — AND ONE OF THEM WAS THE SAME CELL AS YESTERDAY

* **HG/LONDON: 22 winners ($1,045-$1,782), refused at `rv1800 112.7` with a prior cell of $975.**
  The pre-registration named this exact configuration as S1\*'s known cost, on this exact cell, on
  2021-07-08 (rv 142.5 / prior $975, 17 winners, the day-6 best seat). **The rule was followed as
  written and it cost the day's entire margin: the frozen EARLIEST+cv>=516 baseline banked
  +$1,423.75 out of HG/LONDON, and the reader's HG margin is -$1,553.75.**
* **SI/LONDON: 15 winners, refused at `rv1800 218.7` with a prior cell of $450 — and its SIDE call
  was LONG and CORRECT.** The reader read the cell right and refused to sit in it.
* **The term I dropped would have saved the day.** S1c (`unspent_sess >= $500`, or `.` when SI's
  fvol is refused) seats 6 cells, 4 with winners, **winner recall 0.911**: it refuses HG/NY and
  NKD/NY (two of my three empty seats, both `cov_sess` 112-283% with negative `unspent_sess`) and
  keeps NKD/TOKYO, HG/LONDON and SI/LONDON. I excluded it because it scored precision 0.293 over the
  six prior sessions — on a pool where it almost never fired. **A term measured on a sample that
  never exercised it is not measured.**

## 4. THE SIDE: MY PRIMARY INSTRUMENT INVERTED AND ITS DEAD TWIN WAS RIGHT

| estimator | day-7 (5 winner cells) | 7-session pooled | sessions LOST to its mirror |
|---|---|---|---|
| READER | 2 / 5 = 0.400 | — | — |
| **S2a P031 cross-asset fuel >= 0.75 (the declared primary)** | **1 right / 3 wrong / 1 silent = 0.250** | 11 / 5 = 0.688 | **2 of 7** (E1D2, E1D7) |
| **S2b P009 OWN-asset fuel (DEAD twice)** | **3 right / 1 wrong = 0.750** | 8 / 8 = 0.500 | 3 of 7 |
| S2c S10 outside-VA >= $500 | 0 / 1 | 2 / 3 | 3 of 7 |
| S2d P029 phase prior (dead as a rule) | **4 / 5 = 0.800** | 17 / 5 = 0.773 | 2 of 7 |

**P031's central claim — an overhang is supply to the OTHER assets and fuel to the one that carries
it — did not survive its first out-of-sample session.** On 2021-07-09 the cross-asset reading was
wrong on three of four decided cells and the own-asset reading was right on three of four. The sign
inversion that P031 was minted on is not a standing property; **what both readings share is that
they fire on the LAST COMPLETED PHASE, and on a trend day the trapped side keeps losing rather than
forcing the reversal it is supposed to force.** P031 goes to CONTESTED with two live readings and no
mirror-law standing, exactly where P015 went on day 2.
**And for the fourth time this round, the object the ledger has killed scored best**: P029, struck as
an era-period trend on day 6, called 4 of 5 cells here. Its content is "TOKYO/LONDON long, NY short"
and today was an all-long day with a NY cell that... was also long (SI/NY), which is the one it
missed. The honest reading is that P029 is a LONG bias in a rising-metals fortnight, and this session
was long. It stays dead as a rule.

## 5. SEAT-BY-SEAT (4 seats, each with its pre-mortem adjudicated)

**(a) NKD/LONDON 08:53:38 SHORT — `-955.00`, WALLED (peak +$257.50, MAE $200 before the wall).**
Truth: NKD/LONDON was a **LONG** cell with 11 winners. Pre-mortem verdict: **named the wrong death.**
It said the EXIT CLOCK would kill it (a $1,000 bar out of a phase the forecaster priced at $516.50);
what actually killed it was the SIDE — price went up and the $900 wall took it at 10:45:17. The
pre-mortem's feasibility argument was nonetheless CORRECT AS ARITHMETIC and it should have vetoed the
seat: **`unspent` on the BINDING PHASE row was $291.50, and the flip threshold I elicited before the
call ("a stage-1 clause of the form unspent-on-the-BINDING-PHASE-row >= $1,000 refuses this seat")
is the term the day wants.** Note it is NOT the same as S1c (which reads the session row).
**(b) HG/NY 13:00:18 LONG — `-130.00`** (peak +$557.50, MAE $718.75, unwalled). Truth: **empty
cell**, zero winners either side. The pre-mortem named the side mechanism ("if HG re-enters value the
trapped-shorts reading is dead"); the cell's real defect was that it had nothing for anybody. HG/NY
opened at `cov_sess 111.9%` with `unspent_sess -$274.60` — S1c refuses it.
**(c) SI/NY 13:09:22 LONG — `+470.00`** (peak +$1,020.00, MAE $837.50, $62.50 under the wall).
Truth: **SI/NY was a LONG cell with 7 winners — right cell, right side, WRONG MOMENT.** The cell's
winners are at 14:50:59-15:05:05 paying $1,020-$1,182; my seat was spent 101 minutes early on a row
that peaked at $1,020 and gave back 54% of it. **This falsifies day 6's §63 ("right cell side +
EARLIEST is a complete entry rule") on its first out-of-sample test**, and it does so on the one cell
the reader got fully right. Under one-position seating the moment stage is worth the difference
between +$470 and +$1,182 here.
**(d) NKD/NY 13:51:19 LONG — `+182.50`** (peak +$670, MAE $450). Truth: **empty cell.** The
pre-mortem called it "one bet taken three times" with the other two NY cells and that is exactly what
it was; two of the three cells were empty and the third was right.

## 6. THE MINIMAL PAIRS, RESOLVED

* `SI-20210709-047362-L` (TAKE, +$470) vs `SI-20210709-047052-S` (SKIP, 310s earlier, the cell's
  first row, refused by the SIDE call alone): the short closed **-$1,020** — **the side call was
  worth +$1,490 on this pair** and it is the day's single vindication of the stage-2 override.
* `HG-20210709-046818-L` (TAKE, -$130) vs `HG-20210709-046923-L` (SKIP 105s later, same side,
  refused by V2+V3): the vetoed row closed **-$80**, i.e. **$50 BETTER than the seat**. The veto
  families separated two rows that were the same trade.
* `NKD-20210709-032018-S` (TAKE, -$955) vs `NKD-20210709-032097-S` (SKIP 79s later on T1 alone):
  the skipped row closed **-$955** too. On NKD's LONDON tape the 79 seconds of book that separate a
  take from a skip separate nothing at all.

## 7. THE VETOES MOVED $0.00 FOR THE THIRD CONSECUTIVE SESSION, AND V3 IS NOW NET-NEGATIVE

15 rows carried V2/V3 with the core and both cell gates admitting them. **Vetoed pool mean
+$41.67 with one D-021 winner refused (`SI-20210709-054305-L`, +$1,020); standing pool +$282.27.
Replay delta exactly $0.00** — no veto fired on a seat-spender (day 6: also $0.00; day 5: +$2,477.50
when they did). **V3 (P018) is 14 of the 15 and refuses money on a second consecutive session**
(2021-07-08: 170 sole-blocks at -$104.15 with ten winners refused). Under CC-M2-16.2's pooled grading
V3 survives; on the two most recent sessions it is the most expensive term the reader runs.

## 8. WHAT THE THREE-STAGE COMPOSITION ACTUALLY BOUGHT (CC-M2-17.1's own question, answered)

Stage 1 alone: **-$1,600**. Stage 2 alone: **-$1,846**. Both composed: **-$432.50**. No gate at all:
-$512.50. **Two individually value-destroying filters composed into the least-bad arm of the family**
— the composition is worth +$1,168 / +$1,414 over its parts and +$80 over nothing, on a day when both
stages were wrong more often than right. The mechanism is visible in the arm table: stage 1 alone
concentrates the seats into three cells whose sides I then get wrong; stage 2 alone spreads the wrong
side across nine cells; together they cancel each other's worst placements. **This is the weakest
possible form of a positive result and it is a positive result.**
The ordering is unchanged and confirmed a third time: **oracle SIDE alone +$2,542 over core, oracle
SEAT alone +$244** — side first, feasibility second, moment third (and the moment cost $712 on SI/NY
today, so third is not zero).

## 9. OPEN QUESTIONS CARRIED TO DAY 8

1. **Is `runway x rv1800 >= the bar` the repaired P025?** Seven sessions, 484 winners, and the
   product is computable on every row of every sheet. This is the cheapest and highest-value census
   the round has produced since P025 itself, and it re-opens the disqualified `sigma_to_exit` grade
   as a FEASIBILITY object rather than a confidence one.
2. **Should stage 1 be re-specified as a ROLLING state (rv1800 at the row) rather than a cell call?**
   §2's table says yes; day 8 should trade it that way and score the difference.
3. **Which unspent/coverage row binds — session or BINDING PHASE?** Today's S1c (session row) would
   have saved the day and the seat that lost the most was refused only by the PHASE row. Both are
   one field; neither has been censused.
4. **Is P031 anything at all, now that its two readings have split 3-1 and 1-3 on consecutive
   sessions?** The pooled 7-session numbers (0.688 cross vs 0.500 own) are inside noise for n=16.
5. **Is the MOMENT stage worth more than day 6 thought?** SI/NY: right cell, right side, earliest
   admitted row, and 40% of the achievable certificate. §63's rule is falsified; nothing replaces it.

---

# E1 STUDY POST-MORTEMS — DAY 8 (2021-07-12, SI + HG + NKD, day-complete, n=949)
# THE FINAL STUDY DAY OF THE E1 ROUND

Draw: the next chronological STUDY session per asset strictly after 2021-07-09, warm-ups excluded
(CC-M2-8.1) — SI 327 / HG 304 / NKD 318 on a Monday, `short_day=0`, `observed_close=82799`,
USED_CASE_LEDGER 0 prior hits. Taint `CLEAN;AS-OF-PREFIX` on all 949 rows; no forecast/truth TSV was
opened. Seal commit `cf2400a`; S14 opened only after it. Sources: `E1D8_CELL_LEDGER.md`,
`baselines/E1D8_BASELINE_SCORES.md`, `e1d8_stage12.py --backtest`, `e1d8_prereg.py`,
`e1d8_unblind.py`.

## 0. THE DAY, AND THE SCORE

47 D-021 winners in 949 candidates (4.95%); **44 of the 47 are LONGS**. SI 36, HG 9, NKD 2. Day DP
ceiling $7,480.00. The reader banked **+$422.50** against a best mechanical baseline of **+$3,458.75**
(EARLIEST + cond_value >= 516): **margin -$3,036.25**, the round's fourth-worst day and its sixth
loss in eight. It **beat SIX of its SEVEN frozen predecessors** (its best such record) and lost only
to e1d7. CORE alone would have banked +$1,172.50, so **every gate the reader added cost money.**

**THE ONE-LINE VERDICT OF THE DAY, AND OF THE ROUND: the reader's side calls went 0-for-4 and their
mirror went 4-for-4; the reader's declared refusal to gate on them is the only reason the day is
positive at all; and the one term it did add cost $750 by refusing every non-SI winner on the board.**

## 1. E1D8-F1 — THE SIDE: 0 OF 4, AND THE STRUCTURE OF THE ERROR IS THE SAME BOTH TIMES

| cell | truth | winners | call | conf | right? |
|---|---|---|---|---|---|
| HG/TOKYO | NONE | 0 | LONG | LOW | — |
| NKD/TOKYO | NONE | 0 | LONG | LOW-MED | — |
| **SI/TOKYO** | **SHORT** | 3 | LONG | LOW | **NO** |
| HG/LONDON | NONE | 0 | SHORT | MED-HIGH | — |
| SI/LONDON | NONE | 0 | SHORT | MED | — |
| NKD/LONDON | NONE | 0 | LONG | LOW | — |
| **HG/NY** | **LONG** | 9 | SHORT | MED | **NO** |
| **SI/NY** | **LONG** | 33 | SHORT | MED-HIGH | **NO** |
| **NKD/NY** | **LONG** | 2 | SHORT | MED | **NO** |

**0 of 4 = 0.000; the mirror scores 1.000.** Three-session record of committed cell-side calls:
3/5, 2/5, 0/4 = **5 of 14 (0.357), mirror 9 of 14 (0.643).**

The error has one shape and I named it in the ledger before the outcome: **the five SHORT calls were
"one bet taken five times"** — X2, the session's own one-way selling, read once per cell — and
**the four LONG calls were one bet taken four times** (Friday's close near the highs). Both bets
were wrong, in opposite halves of the day, and the tape refuted the first one at 07:19 while I was
still calling cells. The committed ledger says this in its own summary paragraph, which is the
value of writing the correlation down before the fact rather than discovering it after.

**THE DEEPER FACT, AND IT IS THE ROUND'S:** X2 (session net continuation) was the load-bearing term
in every one of the four wrong calls. It scored 10/8 over seven sessions. On this session the tape
sold from the Asian open to the NY open on all three assets — HG -$1,150 at pos 0.04, SI -$1,050 at
pos 0.10, NKD -$400 at pos 0.06 — and then **every NY cell reversed and paid LONGS**. A session-net
continuation term is a momentum term at cell grain, and ERA_NOTES §34 has it 3-for-3
value-destroying at candidate grain. **It is now 0-for-4 at cell grain and the count is 4-for-4
against its mirror.**

## 2. E1D8-F2 — THE PRE-REGISTRATION HELD OUT OF SAMPLE, AND SO DID THE REFUSAL TO TRADE ITS INVERSION

The day-8 pre-registration made two claims about `rv1800 >= 250` at the row before any day-8 row was
called, and the session tested both:

* **CLAIM: as a gate it destroys value** (-$7,562.50 over seven sessions). **RESULT: -$1,658.75
  today against CORE's +$1,172.50, i.e. -$2,831.25.** Confirmed out of sample, and confirmed on a
  session where the term is *more* right than usual about the pool: it holds **45 of the day's 47
  winners (95.7%)**.
* **CLAIM: the INVERTED form (+$8,923.75 over seven sessions, the best arm on that board) must NOT
  be traded, because an inversion minted on its own sample is the P009 error.** **RESULT: +$207.50
  today — worse than CORE.** The refusal was worth $965.

This is the round's cleanest pair of pre-registered predictions and both landed. It is also the
strongest evidence the round has that **the concentrator/gate distinction is a law and not a
one-session accident**: the object concentrates winners at 1.23x over 8,077 rows and 95.7% today,
and gating on it loses money every time.

**MECHANISM, MEASURED AT THE SEAT (the new instrument of this day):** over the seven training
sessions, of the 64 seats CORE actually spends, the **41 whose rolling state is CLOSED average
+$201.86 and the 23 that are OPEN average -$111.52**. `rv1800` is high *after* a move; the
seat-spending row is the *earliest* admitted row of a seating window. CC-M2-17.4 ordered this split
for vetoes; generalised to concentrators it inverts the round's best-supported object.

## 3. E1D8-F3 — R2b: THE TERM I DID TRADE, AND IT REFUSED EVERY NON-SI WINNER ON THE BOARD

`unspent_bind >= $1,000` — the ERA_NOTES §77 BINDING-ROW field, P014's complement, a pattern the
ledger has carried DEAD at n=0/0 since the warm-up and which this day counted for the first time.
Pooled over seven sessions it looked like the best object in the stage-1 sweep: 8.74% win rate
(1.46x), the **only** arm with a positive mean certificate (+$9.17/row), +$2,471.25 of replay over
CORE and capture 0.096 -> 0.199.

**It cost $750 today and its mechanism is falsified on the day's own evidence.**

| what it refused | n | `unspent_bind` | certificates |
|---|---|---|---|
| HG/NY winners | 9 | 180.7-224.4 | $1,001-$1,120 |
| NKD/NY winners | 2 | 903.2 | $1,008-$1,020 |
| **total winners refused** | **11 of 47** | | |

HG had spent 72% of its expected session range before the NY open; the capacity arithmetic priced
the remainder at $180-$224 against a $1,000 bar; **HG then paid $1,000+ nine times.** This is
ERA_NOTES §21 restated at row grain and for the fourth distinct object: **the capacity arithmetic is
a MEAN-REVERSION PRIOR, and on a session whose range expands it is an anti-signal.** P017, P014,
P021 and now R2b are the same term wearing four hats.

**AND THE CELL IT DID ADMIT, IT ADMITTED BY ACCIDENT.** SI/NY held 33 of the day's 47 winners, and
`unspent_bind` is `.` on all 327 SI rows because SI's fvol is REFUSED for the fifth study session
(ERA_NOTES §16). **R2b passed SI/NY only because the field does not exist.** That is defect D22,
named in the seal before unblinding: a capacity term with a pass-on-REFUSED clause is silently an
ASSET SELECTOR. Today it selected the only asset it could not measure, and that asset held 77% of
the day's winners. The counterfactual matters: an R2b that REFUSED on `.` would have deleted SI
entirely and scored **$0.00**.

## 4. E1D8-F4 — SEAT-BY-SEAT, WITH THE PRE-MORTEMS ADJUDICATED

**SEAT 1 — SI-20210712-010922-L, 03:02:02 TOKYO LONG, close -$542.50, peak +$670, MAE $50, WALLED.**
Pre-mortem named the clock and the arithmetic (`room_phase $50`, `ext_needed $950`, the 07:00 exit,
SI/TOKYO 0-for-7). **The cell was NOT empty — it held 3 SHORT winners at 03:11:43-03:19:02, nine
minutes after my seat.** So the pre-mortem's *conclusion* (this cell will not pay a long) was right
and its *mechanism* was wrong: the phase did produce $1,000 moves, on the other side, immediately.
The flip threshold was T3's freshness ceiling — `extreme_age_trade_side = 3,580s` against 3,600, a
**twenty-second** margin — and any ceiling in [148s, 3,579s] hands the seat to
`SI-20210712-011129-S`, the minimal pair, which is on the winning side. **The day-2 widening of the
freshness window from 900s to 3,600s, adopted on n=3, is what put the reader on the wrong side of
this cell.**

**SEAT 2 — SI-20210712-027269-L, 07:34:29 LONDON LONG, close -$505.00, peak +$1,295, MAE $775.**
The cell held ZERO winners on either side. My committed side call was SHORT and the policy took the
LONG, and **my own elicited flip threshold from cell #4 fired at this row** (`f5m_sflow +33 on 297 =
11.1%` against the >= 10% I had written before the cell's first candidate existed). The pre-mortem's
trigger — "a print below 26.06 says the absorption failed" — is exactly the $775 MAE. And then the
trade rallied to **+$1,295** and closed at **-$505**: **$1,800 of round-trip on one seat, given back
to the 13:00 LONDON phase close.** The give-back channel (§35/§39.5) remains the round's largest
unexplained loss and is now four objects dead (P026, P028, P017's in-range form, and the
rv_collapse marker at seat 3).

**SEAT 3 — SI-20210712-046931-L, 13:02:11 NY LONG, close +$1,470.00, peak +$1,745, MAE $325.**
**The day's only winning seat, taken against the reader's own committed SHORT call for this cell,
because the declared override runs no side gate.** The pre-mortem named `rv_collapse = 7.41` as a
wall marker (ERA_NOTES §3's >= 8 band) and it was wrong on the one row that tested it. The minimal
pair `SI-20210712-047528-S` (+597s, all terms passing, the side I called) is what the reader's own
side gate would have taken instead.

**THE THREE MINIMAL PAIRS HAVE ONE SHAPE AND IT IS THE ROUND'S CENTRAL MECHANIC:** on every one of
the three seats an equally-admitted candidate on the opposite side existed within ten minutes, and
the seat went to the earliest row regardless of anything the reader knew. That is why the mechanical
EARLIEST baseline has beaten the reader on six of eight days.

## 5. E1D8-F5 — ABSTENTION IS SCORED FOR THE FIRST TIME, AND IT IS POSITIVE

ERA_NOTES §70.4 asked whether the reader should abstain from a cell rather than always spend its
seat, and recorded that the ledger had never scored it. Four cells were marked `would-abstain` at
commit time (HG/TOKYO, SI/TOKYO, NKD/LONDON, NKD/NY), each with a named reason. Removing them:
**+$422.50 -> +$965.00, capture 0.130 -> 0.296.** The one that mattered is SI/TOKYO — the 0-for-7
cell whose seat walled at -$542.50 — and its abstention reason was the structural base rate, not a
read of the tape. **A cell-level base rate the reader can compute from its own committed history
was worth more than every direction instrument it ran today.**

## 6. E1D8-F6 — THE VETOES: A FOURTH CONSECUTIVE $0.00, AND V3 IS FINISHED

V2 refused 6 admitted rows at **+$467.92** with 1 winner; V3 (advisory, not applied) refused 12 at
**+$431.46** with **5 winners**. Replay delta for both: **exactly $0.00** — `replay_inert=1` for the
fourth session running. Over its last three sessions V3 has refused 10, 5 and 5 winners at a
positive mean and moved nothing. **The decision to run V3 as ADVISORY was worth $0.00 in replay and
5 winners in the pool, and the pooled re-grade now has an unambiguous answer: V3 should be killed.**
V2's six-session sole-block record is equally hollow at the seat and belongs in the same review.

## 7. E1D8-F7 — WHAT THE PRE-REGISTRATION SAID ABOUT S10, AND WHAT THE DAY SAID BACK

CC-M2-18.3 left S10 geometry as the only hand side-instrument standing. Measured on the 22
winner-bearing cells of seven sessions: **the literal back-to-value reading is 2 right / 6 wrong
(0.250) at $250, 2/3 at $500, and 2/1 at $1,000 (n=3); the same field read at the cell's MEDIAN row
is 1/11.** It fired on three cells today (HG/LONDON, SI/LONDON, NKD/NY), and the two LONDON cells it
called were EMPTY while NKD/NY went LONG against its continuation form. **S10 geometry is not an
instrument. Stage 2 has zero validated hand instruments and the census can close the question.**

## 8. E1D8-F8 — THE GRADE'S A BAND IS NOW EMPTY OF ROWS

`sigma_to_exit`: no row of 949 reaches $2,500. TAKE B -$301.88 (n=56, w=8) vs C -$271.41 (n=16, w=0);
SKIP B **+$122.34 (n=219, w=32)** vs C -$37.42. Five consecutive sessions with no A-band winner, and
32 of the day's 47 winners sit in the SKIP-B cell. §79's rebuild direction is confirmed a second
time: the product is right as FEASIBILITY and wrong as CONFIDENCE.

## 9. SECTION-VALUE LEDGER (CC-M2-4.5), 3 sheet deep reads + 9 cell panels of 949 calls

| section | consulted | changed a call |
|---|---|---|
| triage index (S1-S5/S7-S9/S13 fields) | 949 | 949 |
| S3 `unspent_bind` / `cov_*` (the day's traded term) | 949 | 72 (and it was wrong 11 times) |
| S9 `rv1800` rolling | 949 | 0 (pre-registered, not traded) |
| S10 `d_POC`/`in_VA` (cell panels) | 9 | 3 side calls, all wrong or in empty cells |
| S8 fuel map / flows (cell panels) | 9 | 0 (P031 dead, P009 dead — printed as scored references only) |
| S5 `slope15m` (X8) | 9 | 2 (it was the overruled vote at #6/#7, and it was RIGHT both times) |
| S6, S11, S12 | 0 | 0 |

**S6/S11 are now 0-for-8,026 day-complete calls.** And the day's most painful section entry:
**`slope15m` — the vote I overruled at cells #6 and #7 on a magnitude standard — was correct on
both**, and would have made the SI/NY and HG/NY calls right.

## 10. DEFECTS AND BUILD ITEMS FOUND TODAY

* **D22 (named pre-seal): a capacity term with a PASS-ON-REFUSED clause is an ASSET SELECTOR.**
  `unspent_bind` is 304/304 HG, 318/318 NKD, 0/327 SI on this session. Any capacity feature shipped
  to M3 must carry an explicit refused-policy and an fvol-availability feature beside it.
* **D23: SI's fvol has now been REFUSED on five of the eight study sessions.** The coverage/ladder
  arithmetic — briefing item A1, "the single best-performing method on IWM" — is structurally
  unavailable on the port's primary target asset most of the time. This is a data-side item for the
  builder, not a reader finding, and it has been visible since ERA_NOTES §16 on day 1.
* **D24: the freshness ceiling (T3 = 3,600s) is a live threshold with a 20-second margin on a seat
  that cost -$542.50**, and it was widened from 900s on day 2 on n=3. It has never been censused.
* Build item: the section-value ledger should record OVERRULED votes and their outcomes, not only
  consulted sections — today's most valuable line is a field the reader read and dismissed.

## 11. OPEN QUESTIONS CARRIED TO THE BLIND ROUND

1. **Is there any object the reader can compute that beats EARLIEST-admitted under one-position
   seating?** Eight days say: the mechanical baseline wins on six of them, and every gate the reader
   has added — side, vol, capacity, veto — has cost money at the seat while concentrating winners in
   the pool.
2. **Is the cell-level SEAT BASE RATE (this asset/phase's historical winner-bearing fraction) the
   reader's best instrument?** It is the only thing that paid today (+$542.50 via abstention) and it
   is a pure count of committed history.
3. **What closes the GIVE-BACK?** Seat 2 gave back $1,800 of round-trip. Five objects have now died
   on this question.
4. **Does the census confirm that concentrator-as-gate is a LAW?** Three objects, three sessions,
   same result. The seat-spender split is the instrument; it should be run on every concentrator in
   the ledger at era scale.

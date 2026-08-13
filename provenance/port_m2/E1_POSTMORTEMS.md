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

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

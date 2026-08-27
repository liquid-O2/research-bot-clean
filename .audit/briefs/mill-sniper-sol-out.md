# Sniper audit after Sweep 8

## Bottom line

There is no sure shot in the five-term arithmetic. The credit test is a clean
FAIL on both deciding assets. The survival composite is worse than E1-only and
worse than the phase-time-matched control on NKD and SI. That deletes the
earlier-but-safe-fire term and leaves the current cash as an EXPLORE observation,
not an identified survival edge.

The parent's central sum also counts a sequential retry as if it erased the
first loss. It cannot. Once the first position has walled, that loss is sunk.
The retry can add a second result, positive or negative. It does not convert the
first result. The same proposed deeper quote is then counted again in the depth
and per-trade-quality terms.

Using measured Sweep 8 economics, a generous same-economics envelope is about
$622 per NKD day and $956 per SI day. Those figures already assume every wall
can seat a retry at the current RIGHT-entry mean and every depth miss can be
recovered at that same mean. They are not forecasts. They still miss both
rungs. The omitted sixth problem is drawdown. PRIMARY posts day/trade MDD of
$3,348/$4,510 on NKD and $8,328/$9,398 on SI.

The only honest route starts with the matched-history survival certificate. A
new survivor must create a large term that the five-term sum does not contain.
The most likely result is STOP at that certificate or at its first priced
successor.

## A. Audit of the five terms

All figures below are incremental USD per asset-day unless marked otherwise.

| Term | NKD | SI | Ruling |
|---|---:|---:|---|
| 1. Current line | Observed +210.7, stress +62.2 | Observed +212.8, stress +63.0 | Honest as a receipt, false as a promoted base. Credit failed. Planning value is 0 through the observed result until a frozen successor identifies the edge. |
| 2. SWIB elimination or conversion | Hindsight deletion cap +233.1. All 34 walls add +64.5 at the current overall mean or +273.9 at the RIGHT-entry mean. | Hindsight deletion cap +450.9. All 46 walls add +80.9 at the current overall mean or +615.5 at the RIGHT-entry mean. | Optimistic and partly double-counted. Deletion and retry are different policies and cannot be added. A retry leaves the first loss in place. There is no positive floor before the availability screen. |
| 3. Inner-zone depth | The existing depth-primary line is $76.1/day worse than its any-candidate control. Count $0 now. | The existing depth-primary line is $87.0/day better than control. Count $0 to +87, conditional on the inner-half screen. | Optimistic on NKD and overlapping on both assets. A deeper retry, second candidate, and inner-half entry claim the same price improvement. |
| 4. Abstained-cell recovery | 17 depth misses. Recovery is +32.3 at current mean cash per trade or +137.0 at the RIGHT-entry mean. | 3 depth misses. Recovery is +5.3 at current mean or +40.1 at the RIGHT-entry mean. | Parent's +100 to +200 is too high, especially on SI. Recovering a cell by relaxing depth opposes term 3 and can restore SWIB. |
| 5. Earlier-but-safe per-trade quality | Delete. | Delete. | The fire gate is fake under its frozen test. This term also reclaims the same timing and price gap as terms 2 and 3. |

### Term 1. Current cash

PRIMARY is +210.69/day on NKD and +212.81/day on SI. Those are exact EXPLORE
cash results. They are not a causal estimate of a survival gate. The adjusted
null values in the decision table concern day-order MDD. They do not make the
cash significant. NKD's 0.0547 is also outside the frozen 0.05 bound, and SI's
value is 0.995.

The 2 percent stress remains positive at +62.23 and +63.01, but stress is not a
confidence interval. Both assets fail the rung and MDD gates by wide margins.
For bookkeeping I retain +211 and +213 as the observed starting points. For a
forward estimate I allow zero through those observations. Anything stronger
would award the gate credit that its own test denied.

### Term 2. SWIB and the retry category error

Perfect hindsight deletion of every PRIMARY SOFT-WRONG bucket would add
$233.08/day on NKD and $450.90/day on SI. A causal policy cannot identify those
buckets today. More importantly, the proposed policy is a retry after the
first position exits. It cannot delete the first trade.

There are only 34 NKD walls and 46 SI walls in PRIMARY, or 0.523 and 0.719
possible retry triggers per asset-day before candidate availability, remaining
time, occupancy, and the portfolio cap. If every wall seated one retry, an
extra trade at the current overall mean would add $64.54/day on NKD and
$80.90/day on SI. At the current RIGHT-entry mean, the additions would be
$273.93 and $615.51. The latter case is a generous scenario, not an expectation.

The parent's +300 to +550 requires the following cash per retry even if every
wall seats:

| Asset | Cash per retry for +300/day | Cash per retry for +550/day | Current RIGHT-entry mean |
|---|---:|---:|---:|
| NKD | $574 | $1,051 | $524 |
| SI | $417 | $765 | $856 |

If the term means only retries after SWIB walls, the opportunity counts fall to
19 NKD and 29 SI. The required cash becomes $1,026 to $1,882 per NKD retry and
$662 to $1,214 per SI retry. The NKD range is not credible. The SI low end is
possible, but it assumes nearly every eligible retry behaves like a current
RIGHT entry despite selection on a first wall.

I would not book a positive retry term before its no-cash screen. For a
conditional envelope, use zero through +274 on NKD and zero through +616 on SI.
Loss seriality makes the true lower bound negative.

### Term 3. Inner-zone depth

Sweep 8 already supplies a directional warning. Moving from any candidate to
the first candidate inside 0.15 ATR changes cash by -$76.12/day on NKD and
+$87.03/day on SI. That comparison also changes coverage and entry identity, so
it is not a pure quote experiment. It still gives no basis for a universal
+$60 to +$120.

The proposed inner-half change must earn its paired quote improvement and
fixed-horizon non-inferiority before cash. Count zero on NKD now. On SI, +$87 is
the most I would carry as a measured-scale upper bound. Do not add this term to
a same-side deeper retry without replaying the union. Both changes claim the
same favorable movement.

### Term 4. Abstained cells

PRIMARY has 17 `no_candidate_in_depth` misses on NKD and 3 on SI. At current
mean cash per trade, perfect recovery adds only $32.27/day and $5.28/day. Even
at the RIGHT-entry mean, the caps are $136.96 and $40.14. The SI estimate of
+$100 to +$200 is incompatible with the available depth-miss count.

The seven SI and three NKD `no_fire` cells are not depth abstentions. Adding
them back would reverse the admission rule, and the admission rule has already
failed its credit test. They cannot silently enlarge this term.

### Term 5. Per-trade quality

Delete it outright. On NKD, the measured RIGHT-entry mean is $523.69, not about
$600. Using the supplied $1,141 oracle, closing one third of that gap over the
61 RIGHT entries is about $193/day, not $300 to $500. SI has no corresponding
oracle arithmetic in the supplied receipt, so no honest SI number can be
booked.

The numerical correction is secondary. The causal premise failed. The gate's
fire-time extension is worse than both controls on both deciding assets. An
earlier fire is therefore earlier, not earlier-and-safe.

### Corrected sum

Two views keep the bookkeeping honest.

1. The receipt-centered starting point is +$211 NKD and +$213 SI. It has no
   promoted mechanism and fails MDD.
2. A generous same-economics envelope takes the better of hindsight SWIB
   deletion or an all-wall retry, then adds every depth miss at the RIGHT-entry
   mean. It allows SI's observed +$87 depth scale and gives NKD no depth credit.

That envelope is:

| Asset | Observed base | Retry or deletion, not both | Depth | Miss recovery | Total |
|---|---:|---:|---:|---:|---:|
| NKD | $210.7 | $273.9 | $0 | $137.0 | $621.6 |
| SI | $212.8 | $615.5 | $87.0 | $40.1 | $955.5 |

A defensible planning range is therefore about $0 to $620/day on NKD and $0 to
$955/day on SI. The low end is zero because the base and retry have no
identified positive population floor. The high end is already favorable to
the thesis. The parent's $1,400 to $1,650 central sum is not recoverable by
removing overlap.

Cash is not the only missing term. The current day MDD must fall 70 percent on
NKD and 88 percent on SI. Trade-order MDD must fall 78 percent and 89 percent.
None of the five cash terms prices that requirement. A retry can make it worse.

## B. The sniper sequence

The credit branch has landed. It is FAIL, so the interesting-or-better ladder
does not start. This is the minimal honest sequence from the current receipt.
Every priced unit replays the full combined policy. Incremental cash totals are
never added across overlapping reports.

### Unit 1. Matched-history survival certificate

Run the frozen Sweep 9 certificate from the prior Sol page. This unit changes
no trading knob and reads no cash. Its yield is $0. Its value is deciding
whether the current causal state contains a deployable 1,800-second survivor.

Keep only a `SURVIVOR` or `REGIME_SURVIVOR` on each deciding asset. The bound is
coverage at least 0.35, `postX_1800` at most 0.25, improvement at least 0.05
against both controls, both paired confidence lower bounds above zero, and
adjusted p at most 0.05. A regime letter also needs 0.35 overall coverage and a
0.10 advantage over the other regimes.

STOP on `CERTIFICATE`. STOP without cash on `UNRESOLVED`. If only one deciding
asset letters, the joint-rung sequence also stops because the corrected
arithmetic leaves the other asset short. The replacement after a certificate
is one information-distinct flow-schedule screen, described in section E, not
another transformation of E1 through E5.

### Unit 2. Price exactly one lettered survivor

Freeze the single view and regime named by Unit 1. Replace only Sweep 8's fake
admission rule. Keep the current 0.15 ATR depth entry and every replay law.

The no-cash bound is the Unit 1 letter with no weakening. A line freezes if it
clears the rung with both MDD orderings under $1,000, positive 2 percent stress,
adjusted null at most 0.05, no occupancy or cap skips, and coverage at least
0.35.

There is also an arithmetic STOP floor. Before any remaining term is tried,
this line must post at least $1,090/day on NKD and $760/day on SI. Those floors
come from subtracting the favorable retry, depth, and miss-recovery envelopes
from $1,500. A sub-rung line continues only if it meets both floors, has both
MDD orderings under $1,000, positive stress, adjusted null at most 0.05, and no
occupancy or cap skips. Below either cash floor, even the generous remaining
arithmetic cannot reach both rungs. If MDD still fails, later retries cannot be
assumed to repair it. The expected incremental yield is only $0 to about $200
on NKD and $0 to about $250 on SI. This large mismatch is the most likely
failure of the whole sequence.

### Unit 3. One post-wall retry race

Add the lawful policy in section C as the only changed knob. Run its no-cash
screen first. The measured extra-entry ceiling is zero through 0.523 retries
per NKD day and zero through 0.719 per SI day. At current RIGHT-entry economics,
the favorable cash ranges are $0 to +$274/day and $0 to +$616/day.

The availability keep bound is dynamic. If the residual to the rung is `R` and
the frozen RIGHT-entry mean is `u`, eligible retries per day must be at least
`R/u`. Stop immediately when that demand exceeds observed eligible retries.
The survival bound is `postX_1800 <= 0.25` and at least 0.05 better than both
post-wall controls, with p90 wait at most 900 seconds and no first-entry cap
displacement.

Price one union replay only after that pass. Keep only if both assets clear
rung, both MDD orderings, stress, null, occupancy, and cap. If availability or
extension fails, replace the retry with Unit 4. Do not stack them as independent
cash terms.

### Unit 4. Second distinct in-zone first attempt

Replace the first in-zone candidate with the second distinct identity. Reset
the ordinal after a same-side new extreme. Keep the 15-minute wait limit. This
attacks SWIB without adding a second position result.

The no-cash keep bound remains coverage at least 0.35, `postX_1800 <= 0.25`, an
improvement of at least 0.05 over the Sweep 8 depth line, p90 added wait at most
900 seconds, and zero duplicate identities. Expected incremental yield is $0
to about $70/day on NKD and $0 to about $100/day on SI. Those are planning
scales, not additive promises.

STOP if the no-cash screen fails. Replace it with Unit 5 only when extension is
non-inferior and quote depth, rather than continuation, is the remaining miss.
Otherwise close the candidate-delay branch.

### Unit 5. Inner-half zone

Change only the entry zone from 0.15 ATR to 0.075 ATR. The no-cash keep bound is
coverage at least 0.35, paired favorable quote improvement at least 0.05 ATR,
`postX_1800` no more than 0.02 above the current line, and p90 added wait at
most 900 seconds.

Expected yield is $0 to +$60/day on NKD and $0 to +$87/day on SI. Price the
full policy once. STOP if the bound fails or if the resulting full replay does
not close the exact residual while preserving MDD. There is no replacement in
the current price-depth family.

### Unit 6. Recover only measured depth misses

This unit exists only if the line after Unit 5 is already within the measured
recovery cap of the rungs. Change one admission branch. In a cell with no
in-zone candidate inside the frozen wait, allow the first outer-half candidate
only when the Unit 1 survivor remains live at that candidate's own timestamp.

The no-cash screen must add enough non-overlapping cells to close the exact
residual, retain `postX_1800 <= 0.25`, and leave the survivor's improvement over
both controls at least 0.05. The absolute favorable caps are +$137/day NKD and
+$40/day SI. If the residual is larger, skip the unit. Price one chronological
union replay, then require every formal gate.

This sequence uses at most six new units after the already-landed credit check.
It is a route with hard exits, not a forecast that six units will reach the
goal.

## C. The second-attempt policy

### Trigger law

The policy permits at most one retry in a cell.

1. The first position must be flat while the cell remains open and at least
   1,800 seconds remain. Under the frozen wall-or-close outcome law, a
   phase-close exit creates no retry opportunity. A wall is the normal lawful
   trigger.
2. At the flat timestamp, reset the running extremes and candidate identity
   registry using only facts already observed. Reset the five-bar quiet clock
   after every new extreme.
3. The same-side branch qualifies on the first distinct CLEAR candidate inside
   0.15 ATR of the updated same-side extreme after five completed bars with no
   further same-side extreme. Its decision quote must be strictly more
   favorable than the first entry.
4. The other-side branch is eligible only if the opposite side prints a new
   running extreme after the first position is flat. It then needs its own
   five-bar quiet spell and a distinct in-zone CLEAR candidate. A pre-existing
   opposite extreme is not new evidence.
5. Whichever branch qualifies first supplies the retry. Abstain if they qualify
   in the same completed bar. A later extension resets that branch rather than
   creating another attempt.

This law does not use the failed Sweep 8 composite. The wall, updated extreme,
completed bars, and candidate are all visible at decision time. The other-side
branch requires an independent post-flat event so a first wall cannot by itself
authorize a direction switch.

### Occupancy and cap law

One position per asset still binds. A retry cannot arm or seat until the first
position is flat. No cell gets a third entry.

The replay reserves one possible entry for every not-yet-open scheduled
asset-phase cell. A retry seats only when:

`entries_so_far + 1 + remaining_unopened_cells <= 12`

This prevents a retry from displacing a later first attempt. Chronological
order decides between simultaneous retry opportunities. The screen reports
retry opportunities rejected by this reservation, total entries per portfolio
day, p95, maximum, and every occupancy skip. The prior p95 of 6 to 7 suggests
room, but the receipt must prove it on three-asset days.

### No-cash screen

Use only post-flat risk sets. Report NKD and SI separately, then by phase and
same-side versus other-side branch.

- Count intraphase flat events with 1,800 seconds remaining, eligible retry
  candidates, retry entries per asset-day, and each miss branch.
- Report fire-to-entry wait, remaining phase time, candidate duplication,
  occupancy skips, retry reservations, and first-attempt displacement. The
  last number must be zero.
- Measure fire-stamp `postX_1800`. Compare with the first legal post-wall
  candidate and with phase-time-matched random post-wall candidates. Require
  `postX_1800 <= 0.25` and an improvement of at least 0.05 against both.
- Require p90 wait at most 900 seconds. Require each branch's `postX_1800` to be
  at most 0.30 so one bad branch cannot hide inside the pooled race.
- Convert the residual rung cash to a minimum availability count with `R/u`, as
  specified in Unit 3. If the opportunity count cannot fund the residual even
  at the frozen RIGHT-entry mean, stop before cash.

The first priced read is one full chronological replay. It includes the sunk
first result and the retry. It must report incremental cash from retries,
double-wall count, both MDD orderings, stress, cap pressure, and results with
the same-side and other-side contributions separated for diagnosis only.

### Failure modes

The main failure is loss seriality. A first wall says the run extended. It does
not say the new extreme is terminal. An immediate same-side retry can wall
again and worsen MDD. The five-bar reset and updated extreme reduce that risk,
but only the fixed-horizon screen can earn belief.

The other-side branch can turn a one-way extension into a volatile two-sided
loss. That is why it needs a new post-flat opposite extreme and its own quiet
spell. Phase-close exits provide no retry. Sparse intraphase exits may kill the
term before cash. Three-asset days can also spend the 12-entry budget early;
the reservation law protects first attempts at the cost of retry coverage.

## D. The credit kill shot

Lower `postX_1800` is better. The frozen gate requires the composite to beat
both controls by at least 0.05. The exact fire-stamp results are:

| Asset | Composite | E1-only | Phase match | Delta vs E1 | Delta vs phase | Composite needed to pass both |
|---|---:|---:|---:|---:|---:|---:|
| HG | 0.4746 | 0.2130 | 0.4817 | -0.2616 | +0.0071 | <= 0.1630 |
| NKD | 0.4505 | 0.2455 | 0.3971 | -0.2050 | -0.0534 | <= 0.1955 |
| SI | 0.4298 | 0.1589 | 0.4068 | -0.2709 | -0.0229 | <= 0.1089 |

NKD and SI fail in the wrong direction against both controls. Their Wilson
intervals do not rescue the frozen margin. The overall credit verdict is
`FAIL`.

If the gate had passed, term 1 could have been described as a survival-gated
EXPLORE line, though it would still fail cash and MDD. Term 5 would still remain
zero until one frozen earlier-fire successor passed no-cash and one priced
read. A credit pass was permission to test quality, not permission to book
+$300 to +$500.

Under the landed FAIL, term 1 remains descriptive cash with planning value zero
through the observed result. Term 5 is deleted. The branch is the matched-twin
certificate. No persistence, candidate-ordinal, or inner-zone result may be
credited to the survival composite unless it independently beats the same
fire-time controls.

## E. Probability and alternative

My estimate that this sequence reaches both EXPLORE rungs within the next ten
units is 2 percent, with a judgment range of 1 to 5 percent. This is not false
precision. It states that success would be a tail result.

The reasons are concrete. The current lines earn about 14 percent of the cash
rung. Their day MDD is 3.3 and 8.3 times the limit. The only proposed large
causal term failed both controls. The corrected favorable envelope remains
$878 short on NKD and $544 short on SI. Success also requires both assets at
once, while most prior separators have been asset-specific or null-grade.

The single most likely failure is Unit 1 or Unit 2. Either the matched-history
certificate finds no selective survivor at 0.35 coverage, or its priced
successor falls far below the $1,090 NKD and $760 SI continuation floors. The
retry then cannot fund the residual, even before MDD.

I disagree with treating the present depth-survival frame as a probable rung
path. If Unit 1 closes it, the strongest remaining in-scope alternative is one
no-cash latent execution-schedule screen. Use the one-minute signed-flow tape
as a lossy order-intent channel. Compare repeated pulse spacing and late versus
early price yield at the two zones, with a max-statistic side permutation over
lags 1 through 15. Keep only if both NKD and SI preserve 0.35 coverage and beat
their matched controls by the frozen margin. If that screen fails, stop
transforming the current inputs. Reaching the goal would then require a new
information source, such as event-level order identity or a similarly direct
intent feed, not another score over the same history.

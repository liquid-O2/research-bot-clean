# Sol reconciliation after F19

## Ruling

F19 cannot carry a registered family verdict. The run is reproducible, but its
level-cache reads are centered on the current bar's mid rather than the fixed
candidate zone. It therefore did not execute the barrier selector in its
`SPEC`. Treat F19 as `REFUSE, ZONE-MISCENTERED`. The implemented miscentered
selector is dead. The collision mechanism and a valid LEVELCOLLISION rule are
untested.

The parent must hold sweep 23, build a zone-anchored memory read, and rerun F19
under an exhaustive letter partition. If a valid F19 then routes to F20, F20
needs the same fixed-zone read and one material registration correction. The
break-resolution line must carry letters beside the pullback line. The selector
signs are otherwise correct. A strong former barrier and a strong break impulse
both support continuation.

Plainly, episode resolution is the right next decision event to test. It is not
yet a proven final event. Yes, promote the F20 break-close line into the letter
family before a valid F20 read.

## A. F19 reconciled

### The receipt reproduces but misses the named barrier

The computational receipt is internally consistent. `.audit/mill-sweep22.json`
matches the live `SPEC` and code hashes. Its 33 log rows carry those same
hashes. The ordinary selftest passes 29 of 29 checks, the test-day selector
mutant turns one check red, and all 1,866 lane-2 certificates agree with the
frozen plane to 0.0 USD. The joined level rows are strictly prior.

That proof does not cover the price at which the memory is read. The cache law
in `tools/mill/levels.py` sets `band_center_mid2` to the reading bar's current
mid. Sweep 22 stores `plane[approach_bar]` and `plane[close_bar]` as if those
rows described `candidate.zone_price`. They do not.

A direct formation-only audit over the landed candidates gives the mismatch:

| Read | Rows | Exact zone centers | Median offset | 90th percentile offset |
|---|---:|---:|---:|---:|
| Approach | 14,650 | 0 | 1.90 zone widths | 1.98 zone widths |
| Episode close | 1,875 | 0 | 3.32 zone widths | 3.79 zone widths |

Every episode-close read is more than two zone widths from the named zone. At
that distance the cached band is disjoint from the barrier band. The lane-2
score measures memory around the exit price. The approach score is also almost
two widths away for the median candidate. The same-day and prior-session parts
of `B` therefore do not measure defence at the candidate zone.

This is a material implementation miss. Strict timestamps, matching
certificates, and a red leakage mutant cannot repair the wrong price key. The
selftest plants defence vectors directly and never asserts that the vector's
`band_center_mid2` equals `candidate.zone_price`.

| Deciding result | Pre-touch lane | Episode-resolution lane |
|---|---:|---:|
| NKD seated USD per day | -147.5 | +84.6 |
| SI seated USD per day | -114.4 | +48.0 |
| NKD mean minus two SE | -337.3 | -94.6 |
| SI mean minus two SE | -320.3 | -102.8 |
| Binding MDD | 19,621.8 | 4,596.3 |
| NKD and SI matched maxT p | 0.978, 0.998 | 0.529, 0.996 |

The late lane is better on both deciding assets and on risk. Its absolute size
is still only 0.056x and 0.032x of the rungs. Both lower bounds are negative,
SI changes sign at the adjacent margin cut, and the joint matched control is
unresolved. NKD's count-matched block null at unadjusted p 0.001 is a real
result for the implemented selection, but SI does not repeat it.

The lane comparison no longer isolates the decision event. Lane 1 reads `B`
near the outer approach band. Lane 2 reads it near the episode exit. The lanes
therefore change both entry timing and the price whose history enters the
selector. Sweep 22 also recorded the completed-window columns without letting
them gate. The USER's late event remains the leading F20 companion because
sweep 21 independently found the confirmation filter and because the full
episode reveals direction. Sweep 22 alone does not establish that event.

Two mechanical limits narrow the implemented result. The pre-touch limit
filled only 1,322 of 14,650 formed candidates, a 0.090 rate, while its trained
depth sat at the 0.05 floor. The impulse model scored 9,157 candidates, about
62.5 percent of formation, because earlier occurrences or warmed folds were
absent for the rest. These limits do not cause the refusal. They help explain
the low power and prevent the selected rows from standing in for the full
formed universe.

The formed cash survives the implementation refusal. The hindsight ceiling is
46.8x the NKD rung and 55.0x the SI rung. After a hindsight choice of at most
12 events per portfolio date, it remains 10.8x and 16.1x. Those lines prove
that the formed opportunities contain enough outcomes. They do not prove
causal selection, occupancy-safe seating, or MDD. The implemented selector
cannot reach the cash.

The pinpoint falsifier did not fire. It was not reached. The cash upper bounds
are positive and unpowered, the discrimination half is absent, and the score
did not read the named barrier. The barrier and impulse collision remains the
best current mechanism. Sweep 22 kills only the implemented miscentered `B`
and `I` selector.

### The day-scale `pd` term is lawful but is not a defence pair

The builder made a causal and disclosed substitution. A true minute-grain
prior-day path is unavailable because the immediately prior intraday day is in
HOLD. The context store's prior-day OHLC and today's strictly prior path are
licensed.

I accept the resulting number as a day-scale persistence and location proxy. I
do not accept the name `pd_held - pd_broke` as an exact semantic claim.
`pd_held` assigns one to a prior-day high or low and to a prior-EXPLORE value
edge. An extreme marks a completed boundary, but a value edge does not prove a
hold. The prior-session `ps` pair already measures the prior-EXPLORE path.
`pd_broke` then measures today's prior traversal, not a prior-day break. The
positive and negative terms therefore describe different horizons.

This substitution is not the cause of the refusal. It is independently lawful
and narrow. A corrected F19 may retain the numeric term for comparability, but
its report must call the term a day-scale persistence proxy. No result from it
may claim that prior-day defence memory was exhausted.

### `FALLTHROUGH` is an operational route, not a registered clause

The F19 letters did not partition the outcome. A rich ceiling, positive upper
bounds, and a non-positive matched delta on one deciding asset earns neither
the stated `UNRESOLVED` clause nor either stated `KILL` clause. The code's
default route cannot turn that omission into a preregistered clause.

The centering defect now decides status before this gap does. Read the existing
KILL stamps as measurements from the refused run. Do not claim that a
registered KILL clause fired. A corrected F19 must register the complete
`CEILING-UNREACHED` case before it reopens outcomes. The route to F20 is earned
only if that corrected run returns KILL.

## B. F20 reviewed

### Replace the disclosed shifting-center approximation

The in-flight `tools/mill/sweep23.py` correctly notices F19's gross centering
error. It does not read `plane[break_close_bar]`. It reads the last completed
bar inside the zone before the breach, on side `-break_dir`. That choice avoids
measuring the post-break destination and excludes the current breach.

It remains an approximation. `band_center_mid2` is still that inside bar's mid,
not `candidate.zone_price`. The center may move by a full half-width across the
zone. Its same-day and prior-session counts can therefore change with the last
inside price even when the fixed barrier and its history do not. The
persistence gate and `B` both inherit that moving price key.

The sweep 23 selftest passes 49 of 49 checks and its test-day mutant turns one
check red. Its centering check asserts only that the read price is somewhere
inside the zone band. It does not assert equality with the candidate zone. The
green selftest therefore confirms the disclosed approximation rather than the
fixed-zone claim.

Build one fixed-zone query. For each candidate and decision stamp, center the
same-day and prior-EXPLORE touch, held, and broke counts on
`candidate.zone_price` with the trained width. Read only current-day bars
strictly before the decision and the licensed prior-EXPLORE path. Carry the
fixed zone price and source stamp in the result. The gate requires every center
to equal the candidate zone and every source stamp to precede the decision.
Add a mutant that substitutes the current mid and turns that gate red.

This repair belongs in the corrected F19 run first. If F19 validly kills, F20
uses the same accessor without changing it. The in-flight read is a disclosed
improvement over F19, but it is not the fixed-zone falsifier.

### Promote the break-close line before the F20 read

This is a material correction, not a preference. F20 should be the
`F20-STRUCTBREAK` family with two registered lanes:

1. `BREAK_CLOSE` decides on the first lawful one-minute close beyond the
   trained breach band. It enters in the break direction at the next bar under
   the frozen entry law.
2. `PULLBACK` arms one resting limit as soon as that same break close becomes
   known. The limit sits at a fold-trained depth from the broken-side edge. Raw
   first passage decides the fill. The preregistered cancel law ends the order.

Both lanes must use the same replay, stresses, controls, ceilings, and family
maxT correction. Both must carry `STRUCTBREAK` letters. The current maxT family
is one pullback lane by two deciding assets. Promotion makes it two lanes by two
deciding assets. A family may be LIVE if either lane clears every live bound.

The reason is measured. Sweep 21 showed that later confirmation often filters
episodes even though waiting loses cash within a matched episode. Sweep 22
reported a better full-resolution line on both deciding assets, although its
changed memory price confounds that comparison. A pullback adds another wait
after the now-observed decision. If the break-close line remains report-only, a
pullback failure can kill `STRUCTBREAK` without testing the event that the USER
ordered and sweep 21 independently supports.

At review time, the current sweep 23 process had started and no receipt existed.
Do not inspect or judge that outcome. Its parent F19 route is refused, its
barrier center is approximate, and its break-close line is registered as
ineligible. Preserve the run only as a refused build receipt. If corrected F19
routes onward, register both F20 lanes before repricing.

### Keep the high and high selector, with the correct side and snapshot

The selector sign is right for the trapped-cohort mechanism. Use exactly:

`trade iff B_opp >= train tercile and I_break >= train median`.

`B_opp` is the fixed-zone defence score of the former defending side, the side
trapped by the break. Snapshot it at the breach decision from bars strictly
before the breach bar. Do not use the current-mid cache row. Do not score
defence for the new continuation side, and do not fold the current breach into
`sd_broke` before scoring.

`I_break` is the frozen magnitude score at the last eligible causal occurrence
strictly before the breach close. A large value supports a continuing break. A
large former barrier means that its failure trapped more defenders. Replacing
this rule with `B - I`, low `B`, or defence on the break side would reverse the
mechanism.

The day-scale `pd` component may remain numerically unchanged for comparability,
subject to the naming restriction above. It is not a reason to re-dispatch on
its own.

### Keep the prospective pullback law

The dispatched pullback law is correct. The break close arms the order, and the
raw search starts at the first tick strictly after that close. For an upward
break, it arms a buy limit from above. For a downward break, it arms a sell
limit from below. The trained duration cancels the resting order. The builder
does not wait for a later bar to prove a pullback and then assign an earlier
fill. No re-dispatch is needed on this point.

The `BREAK_CLOSE` lane must also avoid a same-close fill. The one-minute close
defines the decision, so the earliest market entry is the next lawful bar.

### Keep the fixed partition

`CEILING-UNREACHED` is the missing exhaustive case and belongs under KILL. The
dispatched truth-table selftest covers all 512 outcome combinations. The
partition is coherent:

- `STRUCTBREAK-LIVE` applies when one lane clears both rungs, both lower bounds,
  every MDD ledger, cap, occupancy, stresses, control, and neighbor stability.
- `STRUCTBREAK-KILL` clause K1 applies when the formed ceiling misses either
  deciding rung.
- `STRUCTBREAK-KILL` clause K2 applies when a powered deciding upper bound is
  non-positive.
- `STRUCTBREAK-UNRESOLVED` applies when the ceiling carries, the matched delta
  is positive on both deciding assets, and at least one live or power bound
  fails.
- `STRUCTBREAK-KILL` clause K3, `CEILING-UNREACHED`, applies when the ceiling
  carries, no powered upper bound is non-positive, and the matched delta is not
  positive on both deciding assets.

No further selector or threshold change is earned before the F20 receipt.

## C. The morning position for the USER

You wake to several clean method failures and one refused F19 result, not a
dead goal. There is still no executable survivor. There is also no evidence
that the rungs are absent from the allowed data.

The night's root-cause result is the pinpoint in
`.audit/briefs/mill-pinpoint-sol-out.md`. The one-minute plane measures the
size of the impulse. It does not identify the strength of the particular level
that the impulse reaches or which repeated episode matters. The old generator
therefore presents many aliases of one move as separate barrier decisions.

The killed routes now have narrow scopes:

| Route | Receipt | What died |
|---|---|---|
| Conditional sign and antifade | `.audit/mill-sweep17.json` | Forecast size plus the tested absorption slices did not call hold or break on NKD and SI. |
| Six-gate episode grammar | `.audit/mill-sweep18.json` | The fixed one-minute grammar did not produce deciding-asset cash. |
| Fixed-side continuation | `.audit/mill-sweep19.json`, resolved by `.audit/mill-sweep21.json` | Every causal placement missed the joint route. Waiting acted as a filter, but placement alone did not solve selection. |
| Magnitude with symmetric ATR asymmetry | `.audit/mill-sweep20.json` | The monetization rule died. The magnitude information survived. |
| F19 level-collision build | `.audit/mill-sweep22.json` | The implemented current-mid selector missed every live bound, but the fixed-zone selector was not run. Treat the family verdict as refused. |

Two signals remain real. First, the frozen state predicts move magnitude out of
fold. Sweep 20 reports deciding-asset size R2 of 0.10 to 0.12 on NKD and 0.01
to 0.04 on SI across its horizons, while signed prediction remains dead. Second,
event order and episode state carry timing information. Sweep 13's ordinal-two
effect survived its adjusted null. Sweep 21 then found that touch beats later
confirmation within matched episodes on every asset and both labels, while the
confirmation line wins as a filter. Sweep 22 adds a descriptive result from a
miscentered selector. The USER's full-resolution lane turns both deciding point
estimates positive and cuts binding MDD by more than three quarters. It remains
far below the rungs, has no joint control win, and does not isolate timing from
the changed memory price.

The formed-zone universe plainly contains cash. Its capped hindsight ceiling
is 10.8x the NKD rung and 16.1x the SI rung. That is a formation and capacity
fact, not a causal policy. It argues against changing the universe now. The
remaining problem is to identify a small lawful subset and direction before
spending the position.

The goal stays live under your axiom. A null kills a method, never the goal.
`Unreachable` is not a permitted route. That rule does not license soft
letters. It means each failure must name what died and then test the next
information event. The 2021 kill-only license and HOLD remain unspent.

My judgmental prior for a corrected, zone-anchored F19 reaching a joint EXPLORE
`LIVE` line is **20 percent**. The old cash cannot update that prior cleanly
because it selected on the wrong price history. My conditional prior for the
corrected two-lane F20 reaching a joint EXPLORE `LIVE` line after a valid F19
KILL is **15 percent**. The break event matches the porous-level diagnosis and
uses observed direction. A pullback-only F20 would be materially worse.

My prior that the program eventually reaches NKD 1500 and SI 1500 with a
causal rule is **35 percent** across the current laws and any law change that
earns its evidence bar. I put **20 percent** on doing so without changing the
one-minute grain, the frozen promotion outcome, or the universe. These priors
are not stop rules. They state how much work remains.

The next session is a decision tree, not a false linear queue:

| Priority | Unit | Kill or stop condition |
|---:|---|---|
| 1 | Build and selftest the fixed-zone memory accessor. | `REFUSE` if any center differs from the candidate zone, any source is not strictly prior, an exact hand recount differs, or the current-mid mutant stays green. No outcome opens in this unit. |
| 2 | Rerun `F19-LEVELCOLLISION-ZONEANCHOR` with the original two lanes and an exhaustive partition. | Kill only under the complete capacity, powered-control, or `CEILING-UNREACHED` clauses. Preserve `UNRESOLVED` only for a positive matched delta on both deciders with a failed live or power bound. |
| 3 | If corrected F19 is LIVE, freeze and reproduce it. If it is KILL, run corrected two-lane `F20-STRUCTBREAK`. If it is UNRESOLVED, name a power unit from that receipt. | Freeze returns `REFUSE` on any byte, universe, threshold, or replay mismatch. F20 uses the same fixed-zone accessor and dies only under its registered exhaustive clauses. A later valid F20 KILL routes to `F21-SUBMINUTE-ORDER-ORACLE`. Do not amend the selector after an UNRESOLVED result. |

One receipt-level fact would justify changing a USER-owned law now. An
outcome-only raw-tick oracle must show on both NKD and SI that within-minute
touch, absorption, and rejection order clears the rungs and MDD. The same
receipt must show that powered one-minute LEVELCOLLISION and STRUCTBREAK bounds
are non-positive because those distinct orders collapse into the same bar.
That fact would justify changing the grain. No current result justifies
changing the exit law or the universe. An exit change would need the same
causal entries to clear both rungs and MDD under the alternate exit while
failing under the frozen outcome. The night did not measure that fact.

## Evidence and method boundary

Primary pointers are `.audit/briefs/mill-pinpoint-sol-out.md`,
`.audit/mill-sweep13.json`, `.audit/mill-sweep20.json`,
`.audit/mill-sweep21.json`, `.audit/mill-sweep22.json`,
`tools/mill/levels.py`, `tools/mill/build_levels.py`, `tools/mill/sweep22.py`,
`tools/mill/sweep23.py`,
`.audit/mill-hypothesis-log.tsv`, and the live charter at
`.audit/briefs/mill-side-resolution.md`.

`principle-fix-root-causes` traces the receipt past its green causal checks to
the wrong price key. `principle-redesign-from-first-principles` puts one
fixed-zone read under both F19 and F20, and puts the break-resolution event
inside F20's letters rather than bolting it on as a report.
`principle-laziness-protocol` and
`principle-subtract-before-you-add` refuse a new completed-window feature
search before the two registered event timings are judged.
`principle-sequence-verifiable-units` puts the zone accessor check and a valid
F19 receipt ahead of F20. `principle-prove-it-works` rejects the green receipt
after direct inspection of `band_center_mid2` and the 14,650-candidate
formation audit.

# Sol read of sweep 3 and attack on sweep 4

## Bottom line

Keep O4a, O4b, and O4c. Reroute Stage A before it prices anything.

The sweep-3 KILL is sound. The attribution after it is not. The gap from HG
REM 2692 to terminal-fade 1844 does not isolate entry grain. Both measurements
use the same 60-second lattice. They change the side label, the entry objective,
the eligible cells, and the legality time at once. O4a can measure entry grain,
but it cannot assume that entry grain caused the gap.

Sweep 4 also drops one of the adopted Sol controls. Terminality and side are
co-binding. A terminal hit on the losing side is still a bad entry. Select on a
joint side-and-time label, not terminal-hit rate alone. The 0.30 coverage floor
is especially unsafe for HG. At the frozen REM mean, HG needs about 0.66 cell
coverage before it can reach 2000 dollars per asset-day.

My first HG policy test would combine the late `vs_mean` side call with the
terminal detector. The trend call chooses the side after 90 minutes. The
terminal detector chooses the time. This uses each component only for the fact
it measured. Direct late-trend entry is already bad cash, so it must not become
an entry clock.

## A. Reading the sweep-3 oracle ladder

The main ladder is accurate as a list of measured lines.

| Line | HG | NKD | SI | What it measures |
|---|---:|---:|---:|---|
| REM LEGAL at 1800 seconds | 2692 | 3600 | 4230 | Best future executable 60-second lattice quote on the `Delta*` side |
| TERMINAL-ALL | 1844 | 2209 | 2475 | Global bar-mid adverse extreme on the final stable side, with legality checked at that bar |
| TERMINAL-WINDOW | 1957 | 2408 | 2668 | Best adverse bar mid inside the entry window, not necessarily the phase-terminal extreme |
| O3 on the no-cash selected zone | 971 | 793 | 1609 | Last in-zone extreme for each selected sweep-3 zone |
| Best causal selected line | 55 | 64 | 163 | First in-zone trigger plus the selected rebound rule |

The following conclusions hold.

- True terminal entries remove the wall mechanism in this sample. Both O2
  terminal lines have zero walls. The causal lines restore 19 to 39 percent
  wall rates.
- Sweep 3 did not find a useful causal detector. All 52 hypothesis-log rows are
  KILL. Selected Stage-A side errors remain 0.420 for HG, 0.377 for NKD, and
  0.456 for SI. Stage-B cash is near zero and drawdown is far above the cap.
- Prior-day bands cover many terminal extrema. `A1m+0.25` covers 0.583, 0.594,
  and 0.511 by asset. The first qualifying extreme is the last one only about
  3 to 6 percent of the time. A first-trigger rule therefore has the wrong
  stopping object.

Three parts of the parent's reading need correction.

### The REM gap is not an entry-grain estimate

`tools/mill/sweep2.py` computes REM from reverse maxima of executable `cert` on
the 60-second lattice. `tools/mill/sweep3.py` also works on that lattice. O2
instead chooses the minimum or maximum bar mid, then prices the executable
quote at that bar. The two lines also use different side labels. At 1800
seconds, `sign(Delta*)` agrees with the final stable side in only 0.649 of HG
cells, 0.614 of NKD cells, and 0.579 of SI cells. That difference alone blocks
a grain attribution.

HG makes the confounding visible. REM has 181 legal entries at a mean of 981.7
dollars. TERMINAL-ALL has 168 entries at a mean of 724.5 dollars. About 193
dollars per day of the 848-dollar gap comes from 13 missing entries at the REM
mean. About 655 dollars per day comes from the lower value of the entries that
remain. TERMINAL-WINDOW has 179 entries, only two fewer than REM, but its mean
is still 260.2 dollars per trade lower. Coverage does not explain that gap, and
neither does bar grain because both sources are bar-lattice measurements.

O4a should run a matched four-line attribution on the same cells and side law:

1. S0 winner side plus best candidate at its own decision moment.
2. S0 winner side plus best executable 60-second quote.
3. Final stable side plus best candidate at its own decision moment.
4. Final stable side plus the terminal bar-mid entry.

Line 1 minus line 2 is candidate grain. Line 1 minus line 3 is side identity.
Line 3 minus line 4 is the best-price versus terminal-mid objective. Use the
same denominator and legality window for all four. Without this cross, an O4a
reproduction near 2753 only shows that the combined S0 oracle reproduces. It
does not say why.

### TERMINAL-WINDOW is not a terminality oracle

The window code searches for the adverse extremum inside the legal window. A
later adverse extreme can still print outside that window. Its win rates are
0.983, 0.977, and 0.958 rather than 1.0. This line is useful, but it proves that
"late enough and well priced" can work without literal phase terminality. A
hard no-new-extreme label can reject economically adequate entries after a
one-tick later extreme.

Report hard terminal-hit rate, but also report future adverse price regret at
candidate grain. For each entry, measure the largest later improvement in the
same-side executable candidate quote, in ATR units and in spreads. This is a
no-cash timing label and matches the deployable object better than bar-mid
terminality alone.

### O3 is narrower than its headline

The reported 971, 793, and 1609 values are O3 values for the configs selected
without cash. They are not the cash-max family envelope. The cash maxima over
the 14 O3 zone and start-time lines are 1074, 1285, and 1623. Those maxima may
not select a policy because reading them would violate the no-cash rule. The
distinction matters only for attribution. It does not rescue HG or NKD.

The parent is right that Stage A optimized the wrong fact. It measured side at
entry instead of terminal timing. Sweep 4 must add terminal timing, not replace
side with it. The earlier Sol reconciliation made side, timing, walls, and
abstention co-binding. That amendment still applies.

## B. Attack on sweep 4

### Terminal-hit rate can select a late, wrong-side rule

The proposed hit label has two structural failure modes.

First, phase close censors the label. A call made near the close has little time
in which to fail. Large Q can raise hit rate by waiting out the phase rather
than recognizing the last extreme. The 1800-second remaining-time law limits
this bias but does not remove it.

Second, every side has a final adverse extreme. A detector can identify the
last high on a losing SHORT side perfectly. That call is terminal and still
wrong. Sweep 3 already showed 38 to 46 percent side error in the configs that
passed coverage.

Use the following no-cash report for every Stage-A line:

- `terminal_hit`, with the current hard definition.
- `side_hit`, where the fade side equals time-indexed `sign(Delta*)` at entry.
- `joint_hit`, where both facts hold.
- Entry coverage over all eligible cells, not over detections.
- Delay from the true terminal extreme for hits and lead time before it for
  misses.
- Remaining phase time at entry.
- Future adverse executable-candidate regret in ATR units and spreads.

Select by the lower Wilson bound of `joint_hit`, subject to the coverage and
delay gates below. Use terminal-only and side-only rates as the decomposition.
This keeps cash out of selection while measuring the policy's two required
facts.

O4b must separate imposed recognition delay from candidate-wait delay. A point
at d of 10 minutes enters at 10 minutes plus the wait for the next winner-side
candidate. Report that actual-delay distribution, candidate availability, and
cash on a fixed matched cohort. Otherwise a falling coverage curve or a rising
conditional cash curve can masquerade as delay tolerance.

O4c must also handle correlated events and administrative censoring. Compute a
Q-minute false positive only on nonterminal extremes with at least Q plus 1800
seconds left in the phase. Select on a cell-weighted rate with an asset-day
block interval. Report the event-weighted rate only as a sensitivity. A cell
with 15 extrema must not have 15 times the selection weight of a cell with one.

### The D shape mixes clocks before proving either one

`D(Q,H,k,zone)` crosses quiet time, retrace size, retrace duration, and a zone
in 72 configs. Q and k both spend time. H and the zone both condition path
depth. A winner in that grid will be hard to interpret even without cash.

Freeze conditional branches before O4c returns:

1. Always measure a Q-only baseline.
2. Keep a retrace-only `H,k` baseline with no quiet requirement.
3. Cross Q with one retrace shape only if retrace lowers the nonterminal false
   positive rate by at least 0.10, loses no more than 0.10 terminal recall, and
   adds no more than five minutes of median delay.
4. Keep a zone only if it improves the same false-positive rate by at least
   0.10 while losing no more than 0.10 actual-entry coverage.

This turns O4c into a pre-registered branch, not a reason to inspect all 72
cash lines. If neither incremental gate passes, price Q-only and retrace-only.

### The re-arm law needs two independent state machines

The spec does not say how the long and short arms interact. The implementation
must keep one state per side. Each state holds the latest adverse extreme, its
quiet clock, its retrace run, and whether it is waiting for a candidate. A new
low resets only the LONG fade state. A new high resets only the SHORT fade
state. A new same-side extreme after detection but before candidate entry must
cancel that pending entry and reset its state. The first accepted candidate
cancels both sides because the cell permits one entry.

Resetting both sides on every extreme would couple unrelated clocks. Failing
to reset during the detection-to-candidate gap would count an entry that the
terminal-hit law already knows is false. Both bugs can make the no-cash table
look better than the deployable policy.

Use candidate opportunity for a second re-arm sensitivity. A one-tick bar-mid
extreme that never improves the executable same-side candidate quote should
not automatically define a new valuable opportunity. Keep the hard bar reset
as the primary line. Add one fixed sensitivity that resets only when the later
executable opportunity improves by at least two contemporaneous spreads. Do
not grid this threshold.

### Per-phase Q should target one error rate

Independent best-Q selection per phase adds nine small optimizations across
three assets. No cash does not prevent overfitting to hindsight terminal
labels. Derive per-phase Q from one pooled rule instead. For each phase, choose
the smallest Q whose cell-block upper confidence bound on nonterminal false
positives is at most 0.15. This honors the per-session directive while keeping
one shared target.

Keep the per-phase variant only if phase Q values differ by at least 20 minutes
and the phase-specific rule reduces false positives by at least 0.10 against
pooled Q with no more than 0.10 coverage loss. Otherwise price the pooled Q.

### A 0.30 coverage floor cannot qualify HG

Using the frozen REM means and sweep-3 cell rates, the break-even coverage
floors are about 0.659 for HG, 0.362 for NKD, and 0.313 for SI. These are
optimistic because they assume every entered trade earns the REM mean. Use
0.70, 0.40, and 0.35 as the Stage-A qualification floors. The current 0.30 can
remain as a census threshold, but a line that only clears 0.30 cannot advance
to Stage B for HG.

The O4b capture ratio also needs a matched denominator. Compare each causal
line with the O4b oracle on the exact cells, sides, and realized detection
delays that the causal line entered. An aggregate ratio against all oracle
cells mixes timing loss, side error, and abstention again.

## C. HG route and first composition

I rank the HG routes as follows.

1. **Candidate-grain attribution.** Run the four O4a lines above. S0 at 2753 is
   the only cited ceiling with enough HG margin. Treat recovery as a hypothesis
   until the same-side bar-versus-candidate cross measures it.
2. **Late-trend side plus terminal timing.** This is the first policy
   composition I would price if it passes the no-cash gate. It assigns side and
   time to different clocks.
3. **Window-constrained candidate coverage.** TERMINAL-WINDOW reaches 1957,
   only 43 dollars short, but it is still an oracle and still below the rung.
   Its 179 HG trades versus REM's 181 show that added coverage alone is not the
   answer. Use its legal window in the candidate composition, not as a separate
   claim.
4. **Hazard-normalized quiet time.** Replace a free Q per phase with the first
   phase-specific time at which the nonterminal survival upper bound falls
   below 0.15. This is a new timescale route with one shared error target.
5. **Independent per-phase parameters.** Keep these last. The sample is small,
   and a different best Q in each phase is easy to manufacture from terminal
   labels.

The concrete composition is `LATE-MEAN x TERMINAL`:

1. Before 5400 seconds from phase open, collect bars and candidate events but
   do not enter.
2. At and after 5400 seconds, set the slow side call to the sign of current mid
   minus the running mean. The frontier reports HG winner-side accuracy of
   0.591 at 5400 seconds and 0.598 at 10800 seconds. Recompute the call only on
   completed 60-second bars.
3. Run independent long-fade and short-fade terminal detectors. A detection is
   eligible only when its fade side equals the slow side call. Recheck this
   agreement when the candidate arrives.
4. Enter the first agreeing CLEAR candidate after detection at its own decision
   moment. A newer same-side adverse extreme or a side-call flip before that
   moment cancels the pending entry and re-arms.
5. Stop after one entry in the cell. Keep the legal window and frozen exit law.

Do not use `vs_mean` as the entry clock. Its direct HG entries at 5400 and
10800 seconds lose 207 and 178 dollars per asset-day and carry drawdowns above
15000. Its only measured use is side information.

Select between D alone and `LATE-MEAN x TERMINAL` with no cash. The composition
must improve the lower 95 percent bound of `joint_hit` by at least 0.05, retain
HG entry coverage of at least 0.70, and keep its 90th-percentile entry delay no
later than the last O4b delay that retains a buffered HG ceiling of 2500. Kill
the composition before pricing if any condition fails.

If it passes, price one composition and one D-alone control. The priced HG line
still dies unless it reaches 2000 dollars per asset-day, both drawdown orderings
stay below 1000, the 2 percent adversarial stress stays below 1000, and the
adjusted block-null result is at most 0.05. The trend accuracy makes this a
hard test, not a presumed rescue.

## D. Frozen branches for O4b and O4c

Use asset-day block confidence bounds for these decisions. A point estimate
inside two standard errors of a threshold is UNRESOLVED. Call a line
SURVIVES_EXPLORE to price, never LIVE.

| Observed shape | Threshold | Branch |
|---|---|---|
| O4b has a broad delay budget | At d of 20 minutes, lower confidence bounds are at least 2500 for HG and 1875 for both NKD and SI | Keep quiet confirmation. Restrict Q to at most 20 minutes unless a later point also clears the buffered bar. |
| O4b has a narrow delay budget | Buffered bars fail at 20 minutes, but rung bars still hold at 10 minutes | Restrict Q to 10 minutes. Drop any k-bar hold that pushes median total delay past 10 minutes. Price at most Q-only and retrace-only. |
| O4b kills standalone quiet confirmation | NKD or SI is below its rung for every d at or above 10 minutes, or HG is below 2000 by d of 10 minutes | Close the standalone quiet family. Send HG to composition and send all assets to retrace-only or hazard-normalized timing. |
| O4b is nonmonotone because cohorts change | Coverage drops by more than 0.10, or conditional cash rises by more than 10 percent as d increases | Recompute a matched-cell curve before interpreting delay tolerance. Report candidate-wait lag separately from imposed delay. |
| O4c has useful separation | Some Q inside the O4b delay budget has nonterminal false-positive upper bound at most 0.15, terminal-recall lower bound at least 0.70, and actual-entry coverage at least 0.70, 0.40, and 0.35 by asset | The Q branch SURVIVES_EXPLORE to one Stage-B price. Use the smallest Q that clears the bounds. |
| O4c is gray | Best false-positive rate is above 0.15 and at most 0.25, or it reaches 0.15 only after O4b loses the rung | Do not price the 72-config cross. Run the pre-registered retrace-only branch. |
| O4c kills quiet time | The lower confidence bound on nonterminal false positives stays above 0.25 for every Q through 60 minutes, including zone-conditioned lines | Close quiet confirmation. More waiting cannot distinguish terminality on these bytes. |
| O4c supports per-phase Q | Phase-specific Q values differ by at least 20 minutes, each improves false positives by at least 0.10 against pooled Q, and each loses at most 0.10 coverage | Keep the error-targeted per-phase variant. Otherwise use pooled Q. |
| H, k, or zone earns its grid cell | It reduces false positives by at least 0.10, loses at most 0.10 terminal recall or entry coverage, and adds at most five minutes median delay | Cross that one shape with viable Q. Otherwise delete the cross before cash. |

The decisive branch is the intersection, not either table alone. A low O4c
false-positive rate reached only after O4b has spent the cash budget is a KILL.
An attractive O4b delay curve with no terminal versus nonterminal separation is
also a KILL for D. This intersection is the cheap answer sweep 4 should produce.

## Evidence pointers

- `.audit/mill-sweep3.json` supplies O1, O2, O3, Stage A, Stage B, and the
  selected-line replay.
- `.audit/mill-rem-ceiling.json` supplies the REM LEGAL ceiling, mean, and
  coverage at each tau.
- `.audit/mill-sweep2.json` supplies the 1800-second side-stability agreement
  and the failed first-adverse-extreme lines.
- `.audit/mill-frontier.json` supplies the late side-call accuracy and the
  direct fixed-time cash controls.
- `tools/mill/sweep2.py` and `tools/mill/sweep3.py` establish that REM and
  terminal-fade both use the 60-second lattice and show the changed side and
  entry objectives.
- `.audit/mill-hypothesis-log.tsv` records sweep3-001 through sweep3-052 as
  KILL.

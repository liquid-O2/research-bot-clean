# Root-cause review of the mill

This review uses the record named in the dispatch. I treated lines 1 through
411 of `.audit/mill-hypothesis-log.tsv`, ending at `sweep8b-004`, as the frozen
log. Later rows appeared while this review was running and are outside the
brief. I excluded the charter section titled `The structural diagnosis` and
`.audit/briefs/mill-design-fable.md`.

## A. The load-bearing structural error

The mill changed evidence, labels, clocks, and thresholds without changing its decision operator. Every executable failure reduces an ordered within-cell path to one preselected decision point or takes the first bar, extreme, fire, or candidate that clears a local predicate, then spends the cell. Fixed-clock S1, B5, and the fixed-time mill lines are the degenerate one-shot form. The event-driven mill lines are the first-qualified form. My own remaining-opportunity and flow designs made the same mistake. The code says this directly in `tools/mill/sweep3.py:405`, `tools/mill/sweep4.py:1009`, `tools/mill/sweep5.py:398`, `tools/mill/sweep6.py:493`, `tools/mill/sweep7a.py:349`, and `tools/mill/sweep8.py:680`. The receipts show why it is load-bearing. The selected sweep-3 cells contain 14.5, 14.7, and 15.1 qualifying extremes on average, while the first is the last only 4.5%, 2.9%, and 6.3% of the time. Sweep 7a fires before another extreme in 50.3%, 57.5%, and 48.6% of entries even though its soft-hit rate is 92.7%, 95.3%, and 91.2%. Sweep 7b assigns 67.2%, 84.4%, and 77.3% of gross loss to soft-wrong, in-budget entries, while right-late entries earn $310, $353, and $466 per asset-day. S0 and B2 recover almost all available value by ordering price within a side. I4 enters the first true terminal extreme of either side and clears every rung at $2,103, $2,335, and $3,070 per asset-day with MDD $74, $0, and $18 and no side bit. The record therefore rejects many evidence sources only after forcing them through an earliest-qualifier policy. It has never tested whether the occurrence number and the ordered path to that occurrence are the policy state.

The concise diagnosis is `argfirst` where the domain requires an ordered
stopping process. The mill asks whether the current observation is good enough.
It has not asked which occurrence in the current episode is good enough, or
whether a specific sequence of observations must complete before entry.

### Proving receipts

| Receipt | Fact | What it proves |
|---|---|---|
| `.audit/mill-sweep3.json`, `stage_o.o3` and `stage_b.o3_gap` | The selected HG, NKD, and SI lines have mean trigger counts 14.53, 14.70, and 15.08. Their first-is-last rates are 0.045, 0.029, and 0.063. | The first qualifying occurrence is almost never the economically important last occurrence. This is not a marginal timing error. |
| `.audit/mill-sweep4.json`, `stage_o.o4a.lines["S0R-BEST"]` | Candidate-anchored oracle entries post $2,182, $3,095, and $3,514 per asset-day with zero walls. | The candidate plane and raw suffix law preserve enough value. Bar or quote machinery is not destroying the ceiling. |
| `.audit/mill-sweep4.json`, `stage_o.o4b` | Once the terminal extreme is known, NKD remains above its rung through 45 minutes and SI through 60 minutes. | A later admissible occurrence can retain the payload. Immediate action is not required by the economics. |
| `.audit/mill-sweep6.json`, `separations` and `decision.per_asset` | Individual `F` and `S` components reach AUC 0.61 to 0.64 on HG and SI. The scalar R5 first-opportunity policy improves joint hit by only 0.009 and -0.038 on NKD, and 0.028 and 0.029 on SI, with adjusted p-values 0.70 to 1.00. | Some observations separate states, but averaging them and acting on the first crossing does not compose their information. |
| `.audit/mill-sweep7a.json`, `screen_a.by_asset` | Soft hit exceeds 0.91 on every asset, and a next candidate exists in 100% of delay-bounded selections. Post-new-extreme rates remain 0.657, 0.703, and 0.607 in that bounded set. | The trigger is usually directionally salvageable and another observable occurrence is available. The first accepted candidate is the miss. |
| `.audit/mill-sweep7b.json`, `part1_decomposition.by_asset` | Soft-wrong, in-budget entries dominate gross loss. Right-late entries have 86% to 92% win rates on NKD and SI. | The economic failure is early continuation after a locally plausible trigger, not mainly hard side inversion. |
| `.audit/mill-sweep8.json`, `horizons`, `credit`, and `sweep8b` | The primary composite fires early and matches phase-time controls. E1-only reduces extension only when its median fire moves to roughly 9,000 to 11,000 seconds. Both first-fire policies fail cash. | A scalar threshold can choose early danger or late safety. It cannot express the transition path between them. |
| `.audit/mill-ideascreen.json`, `i4.table` | The side-free first-terminal oracle clears all rungs, has no walls, and uses at most nine portfolio entries per day. | The frozen inputs and laws can render the user goal reachable. The missing object is a causal stopping state, not a side classifier or more entries. |
| `.audit/briefs/mill-design-sol-out.md`, policy steps 4 through 6, and `.audit/briefs/mill-flow-route-sol-out.md`, section B | My designs arm on the first threshold pair, take the first adverse extreme, or take the first flow-margin opportunity. | The same assumption is present in the policies I designed. It was not only inherited from other authors. |

## B. Ranked candidate errors from four passes

These are all the candidate errors I considered. Rank is within each pass.

### Pass one on the data layer

| Rank | Candidate error | Evidence for | Evidence against | Ruling |
|---:|---|---|---|---|
| 1 | The label is attached to the wrong grain. Side, sharpness, and terminality label a cell or extreme, while the action must choose an occurrence within an ordered episode. | Sweep 3 has about 15 qualifying occurrences per selected cell. Sweep 7a can be soft-correct while entering before the next extension. S0 and B2 succeed on within-side price order. | The labels do not fabricate the losses. Raw-suffix cash, walls, and fixed-horizon extension agree that the chosen occurrences are bad. | Real representation error. It feeds the top decision error, but it is not store corruption. |
| 2 | The 60-second bar plane and candidate-anchored quote plane are mismatched. | REM value is much larger than terminal-bar value. Sweep 4 candidate anchoring recovers HG above its rung. | Candidate-anchored sweeps 4 through 8 still fail under causal first-entry rules. S0R proves the conversion machinery itself works. | Important earlier confound, no longer the common cause. |
| 3 | EXPLORE is small and adaptively over-read. | The frozen log contains 410 trial records across 195 asset-days. Only 56 records carry cash and MDD. Repeated grids can make weak positives unstable. | Every row through sweep 8b has one split SHA, one outcome-law SHA, and one null seed. The main misses are large, cross-asset, and reproduced by multiple labels and cash. | Blocks promotion and makes positive results exploratory. It does not explain the uniform failure. |
| 4 | Pooling years or phases hides a regime where a policy works. | Phase clocks differ sharply. The data window spans 2022 through 2024, and the forward-vol regime plane is known to exist. | Per-phase sweep tables still show the early-extension problem. No receipt shows a year or phase reversal large enough to meet the rungs and MDD. Regime conditioning cannot repair a policy that spends the cell at the wrong occurrence. | Unresolved secondary conditioner, not the load-bearing error. |
| 5 | The partial-day quarantine split mismeasures portfolio MDD. | Every replay correctly labels itself `partial-day (split breaks portfolio days)`. It cannot reproduce a full contiguous portfolio history. | Failed lines report asset MDD from roughly $3,000 to more than $60,000, far beyond the $1,000 boundary. S0R and I4 have near-zero MDD under the same ordering. | A certification limitation. It cannot reverse tonight's kills. |
| 6 | Costs, walls, fills, stores, or splits are quietly wrong. | A shared implementation defect could in principle shape every result. | B5 reproduces exactly. The frontier sees 600 cells and zero silent cells. Candidate fills use the last trusted quote strictly before decision time. The split counts are 66/65/64 EXPLORE and 131/129/127 HOLD. The same outcome-law SHA appears in every logged trial. Oracle controls clear with zero or near-zero walls. | Rejected. There is no receipt-level evidence of a machinery defect. |

### Pass two on the decision layer

| Rank | Candidate error | Evidence for | Evidence against | Ruling |
|---:|---|---|---|---|
| 1 | One-shot, first-qualified selection. A fixed clock chooses one snapshot; an event policy takes the first local predicate crossing. No executable unit varies occurrence ordinal as policy state. | It is explicit in every implementation seam from sweep 3 onward. The first-is-last rates are 3% to 6%. Later entries carry much better economics. My own designs retain the same operator. | A later occurrence is not automatically good. E1-only proves that waiting blindly can preserve safety after losing too much payload. | The single load-bearing error. The next unit must vary only this operator. |
| 2 | Treating side as the central latent variable. | S0 shows oracle side plus price order is valuable. Many early screens optimize side or joint hit. | I4 clears all rungs without a side bit. Sweep 7b shows hard wrong-side losses are a minority. Sweep 8 does not require a side label and still fails. | Overweighted objective, but it was varied and cannot be the common cause. |
| 3 | Combining evidence as one scalar. | R5 and G average components with different clocks. Individual flow components separate states, while their scalar policies fail. Repeated threshold looks distort a per-bar percentile. | Fixed clocks, first-extreme rules, and held-retest rules fail without the same scalar construction. | A major expression error inside later sweeps. It is subordinate to the shared first-qualified operator. |
| 4 | Using absolute quiet time or a common clock. | B5 and sweep 4 show that a clock can be early in one phase and late in another. E1-only becomes safe only very late. | Event-based, retrace, flow, held-retest, and candidate-depth rules already varied the clock and still used the first-qualified action. | Closed as the universal explanation. |
| 5 | One entry per cell and one accepted side spend too much optionality. | Competing sides and later candidates exist. A first accepted side cancels the other lane. | I4 clears all rungs with zero second legs, max nine portfolio entries, and one entry per cell. The user's occupancy and leverage rulings bind. | Not the bottleneck. Preserve two lanes before entry, but do not add entries. |
| 6 | Phase reset discards useful cross-phase state. | Earlier phase extremes and held levels could alter the meaning of the current sequence. The cross-phase memory test was narrow. | Cross-phase memory did not improve the first-fire policy, and the within-phase first-is-last defect is already overwhelming. | Possible later state input. It is not the first build. |

### Pass three on the objective layer

| Rank | Candidate error | Evidence for | Evidence against | Ruling |
|---:|---|---|---|---|
| 1 | Surrogate correctness is treated as the user objective. Side error, terminal hit, joint hit, and fixed-horizon survival are screened as if one of them were sufficient for cash. | Sweep 7a is killed despite soft hit above 0.91 because side and joint metrics fail. I4 needs no side bit. Sweep 4 can have high terminal hit and bad cash. | Every priced first-qualified line also misses cash and MDD badly. Relaxing the surrogate screens would not promote those exact policies. | The screen is misrendered, but the exact cash kills remain valid. Use surrogates to diagnose transitions, not to define a policy family. |
| 2 | A global pathwise MDD law is converted into a local 2% classification-error ceiling. | MDD depends on loss size, order, recovery, abstention, and cross-asset overlap. A per-entry error rate is not equivalent to drawdown under replay. | Observed side and joint errors are 40% to 80%, and wall rates are often 20% to 70%. They are nowhere near a plausible pathwise pass. | Mathematically too strong as a screen, but not close to changing tonight's verdicts. |
| 3 | Each unit is asked to carry the full rung alone before complementary states can compose. | Different mechanisms cover different cells and times. A lawful union could improve selection without increasing one-position exposure. | The user ruled that dollars per trade must carry the rung. Adding weak lines or trade count is not a solution. The observed late-only economics cannot clear alone, even at full cell coverage. | Do not build a union now. First prove one occurrence selector improves per-trade economics. |
| 4 | Partial-day MDD is treated as final certification. | EXPLORE does not contain contiguous portfolio days, so its MDD is not the final user metric. | It is consistently labeled as partial-day and is used only to kill in an exploratory tier. Failures exceed the boundary by multiples. | No false kill in the present record. HOLD or a contiguous confirmation block is still required for promotion. |
| 5 | The rung arithmetic or one-entry-per-cell rendering is wrong. | Coverage changes the required dollars per entered trade, which can make a low-coverage screen look harsher than a per-day goal. | START_HERE derives the top-two requirement correctly. Three cells per asset-day and one entry per cell imply about $667 for HG and $500 for NKD/SI before coverage loss. I4 clears with this exact capacity. | Rejected. The arithmetic is not the problem. |
| 6 | The 2% stress and adjusted null are stricter than the user asked. | They add proof obligations beyond raw rung and MDD. | A rule near the boundary needs a stability test, and no failed line is close enough for these controls to decide its fate. | Keep them for a survivor. They did not cause the search failure. |

### Pass four on the process layer

| Rank | Candidate error | Evidence for | Evidence against | Ruling |
|---:|---|---|---|---|
| 1 | The loop closes an evidence family after one first-qualified policy fails. | Sweep 6 closes flow after scalar R5 at its first margin crossing. Sweep 7a closes held-retest after its first uncancelled fire. Sweep 8 closes a five-evidence composite and then E1 as standalone first-fire gates. Positive component receipts are not preserved as state transitions. | Exact line kills are legitimate. The protocol correctly prevents repeated amendments to a failed policy. | The family-level closures are overbroad. Preserve ingredients, not policies. |
| 2 | One-knob hillclimbing inherits the action operator, so the search moves locally around the same structural mistake. | Q, H, k, zones, arbiter, flow score, retest, depth, and survival evidence all changed while `argfirst` stayed fixed. The log contains 410 trials but zero ordinal action trial through sweep 8b. | One-knob units are auditable and protect against post-hoc search. | Keep one-knob discipline. Change the frozen baseline knob from feature choice to occurrence ordinal. |
| 3 | Screen-before-price discards observations that are weak classifiers but useful vetoes or state transitions. | `F`, `S`, quiet age, opposite extension, and held retest each have partial separation. Their first-fire policies fail, so the loop routes away before testing ordered conjunctions. | Pricing every feature combination would destroy quarantine discipline and invite overfit. | Replace feature-family screens with a mechanism screen on an explicit state transition. Do not open a grid. |
| 4 | Adaptive many-read exploration changes the route even when each rule is frozen. | There are 410 records, 332 KILL and 78 UNRESOLVED, across nine spec SHAs and eleven code SHAs. The choice of the next family uses prior EXPLORE outcomes. | EXPLORE is explicitly many-read and cannot promote. HOLD remains untouched. Nulls and mutants protect individual claims. | Limits the strength of any positive conclusion. It does not explain the negative pattern. |
| 5 | The record stores verdicts better than reusable mechanism contracts. | The log records one row per tested line, but it does not promote facts such as `next candidate exists`, component AUC, or delay budget into a durable state vocabulary. Later designs rediscover those facts as new scorers. | The JSON receipts retain the underlying facts, and the charter narrates them. | Process defect. The next receipt should report state transitions and vetoes separately from policy cash. |
| 6 | HOLD quarantine and one-read promotion slow the search. | They prevent rapid confirmation of a survivor. | There is no third corpus, and the earlier program was invalidated by read-peek-amend. HOLD quarantine is the correct response. | Not an error. Do not touch HOLD in the first build. |

## C. The first build

Build one ordinal-2 candidate ablation. Do not build a new score, fitted model,
union, or feature grid. The unit changes only the action operator downstream of
the frozen sweep-8 `PRIMARY` fire stream.

### Question

Does requiring one more distinct, observable candidate occurrence after the
same frozen fire remove early continuation at usable coverage, beyond what
ordinary lateness explains?

### Frozen inputs and controls

1. Use EXPLORE only, the existing sweep-8 candidate, context, and evidence
   caches, split SHA
   `b6d2decb1f3d6495e003a1a29a229195f4d4c1bdc0134d4195a1cc2c1c38f08f`,
   outcome-law SHA
   `64df3f7006ae02445de56f13ddd1f563a0db50f96eaec60e6a7a760e9901a720`,
   and seed `20260827`. Keep HOLD, 2021, 2025, teacher
   stores, late labels, and cash closed during Stage A.
2. Recompute sweep-8 `PRIMARY` fire stamps without any change to G, its
   walk-forward percentile, the 1,800-second remaining-time floor, two-lane
   monitoring, or cancellation law.
3. `FIRST` is the exact sweep-8 `PRIMARY` resolver. It must reproduce entry
   counts 118/111/121 and entry-stamp `postX_1800` 0.458/0.432/0.408 for
   HG/NKD/SI before the unit can continue. The fixed-horizon denominators are
   118/111/120 because one SI entry is censored.
4. `SECOND` uses the same fire. Count legal same-side CLEAR candidates within
   0.15 ATR of the running extreme and within 900 seconds of the fire. Count a
   new occurrence only when its live keep-first candidate identity is new and
   its decision timestamp is strictly later than the previous occurrence.
   Enter the second occurrence at its own decision timestamp.
5. A new same-direction adverse extreme resets the ordinal to zero and voids
   the pending fire. The resolver may continue only from a later frozen G fire
   on the new extreme. Preserve the existing opposite-extreme cancel. The first
   surviving ordinal-2 entry spends the cell. One entry per cell and the
   portfolio cap remain unchanged.
6. `TIME-MATCH` samples legal candidate occurrences from a different asset-day,
   matching asset and phase exactly and both phase elapsed and remaining time
   within 300 seconds of each `SECOND` entry. Use 200 draws. It measures the
   benefit of being late without giving credit to ordinal two.

### Stage A measurements

Report by asset and phase, with HG report-only for the ruling.

- scored cells, fired cells, first-occurrence availability, second-occurrence
  availability, entries, and cell coverage;
- duplicate identities, equal-timestamp candidates, same-side resets,
  opposite-side cancels, no-second-candidate misses, and deadline misses;
- `postX_1800` from the entry stamp for `FIRST`, `SECOND`, and `TIME-MATCH`;
- paired `SECOND - FIRST` and `SECOND - TIME-MATCH` differences by asset-day,
  with block 95% confidence intervals;
- first-to-second wait median and p90, phase time remaining, candidate ordinal,
  and favorable quote change in ATR;
- terminal lead or lag as a diagnostic only. Do not use terminality, side,
  walls, cert dollars, or MDD to select Stage A.

Use asset-day block sign flips for the paired deltas, 10,000 draws, seed
`20260827`, and a max statistic across NKD/SI and both comparisons.

### Pre-registered Stage A ruling

`ORDINAL-SURVIVES` requires every bound below on both NKD and SI.

1. Cell coverage is at least 0.35.
2. `SECOND postX_1800` is at most 0.25.
3. `SECOND` improves on `FIRST` by at least 0.10 and on `TIME-MATCH` by at
   least 0.05.
4. The 95% upper confidence bound for each paired difference is below zero,
   and the max-adjusted p-value is at most 0.05.
5. Added first-to-second wait p90 is at most 900 seconds.
6. Candidate identity duplicates are zero after live keep-first dedup, every
   entry has at least 1,800 seconds remaining, `TIME-MATCH` finds matches for
   at least 90% of `SECOND` entries, and all replay-cap skips are zero.

`ORDINAL-ASSET-SCOPED` applies if exactly one deciding asset passes every bound
and the other asset's `SECOND - FIRST` point estimate is non-positive. Price
only the passing asset. `ORDINAL-KILL` applies if neither asset passes or either
asset worsens `postX_1800` by at least 0.05. Do not try ordinal three, change
the zone, or add persistence in this unit.

### One gated price read

If Stage A returns `ORDINAL-SURVIVES` or `ORDINAL-ASSET-SCOPED`, open the frozen
outcome law once and price `SECOND` only for each passing asset. Use exact
chronological replay and the existing 2% adverse stress. A line survives
EXPLORE only if it clears its asset-day rung, both day-ordered and trade-ordered
MDD are below $1,000, stressed dollars per asset-day stay positive, adjusted
null p is at most 0.05, and occupancy or cap skips are zero. It still cannot
promote. Freeze the complete rule in writing before one HOLD read in a later
unit. If Stage A passes but cash fails, record that ordinal two fixes the
mechanism but is economically insufficient. Do not stack another amendment.

### Verification and deliverables

- Add a selftest where the second occurrence survives and the first does not,
  plus a case where a same-side new extreme resets the count.
- Add one mutant that keeps the ordinal across a same-side reset and one mutant
  that chooses the occurrence with future cert dollars. Both must turn the
  selftest red.
- Refuse to run Stage A unless the frozen `FIRST` reproduction matches the
  sweep-8 counts and rates above.
- Target less than ten minutes on existing caches.
- Write one receipt with the frozen spec, reproduction, transition counts,
  Stage A table, optional single Stage B line, mutant receipt, and matching
  hypothesis-log rows. Stop at that receipt.

This unit is deliberately smaller than a sequence model. It directly varies
the assumption the prior work never varied. A positive result licenses a later
finite-state grammar. A negative result kills ordinal two, not every possible
ordered grammar.

## D. What the killed record gives back

No exact cash KILL becomes LIVE by argument. The resurrection is narrower and
more useful. Several family closures become invalid because they tested an
ingredient only inside the first-qualified operator.

| Record | Resurrect | Keep dead |
|---|---|---|
| Sweep 3 deep fades and prior-level zones | The ordered stream of in-zone extremes, its ordinal, and the prior-level context. | Every priced first-in-zone line and its cash verdict. |
| Sweep 4 quiet and retrace detector | Quiet age, retrace hold, and same-side reset as transition predicates. O4b's lawful delay budget remains a design constraint. | The first detector-entry policies and any claim that quiet alone is a complete entry rule. |
| Sweep 6 flow route | `F` and `S` as ordered confirmation or veto tokens. Preserve their component AUC receipts. | Scalar R5, its 60th-percentile first crossing, and the exact R5 KILL. |
| Sweep 7a held retest and memory | Touch, depart, opposite extension, held-zone count, and next-candidate availability as a state machine vocabulary. | The held-retest side caller, first uncancelled fire, and its joint-hit KILL. |
| Sweep 7b decomposition | The finding that early soft-wrong continuation is the dominant loss and that lawful lateness retains payload. | Hindsight `RIGHT/LATE`, flip policies, and every hypothetical ladder using future bucket labels. |
| Sweep 8 and 8b | E1 quiet age as an `exhausted` state, the 0.15 ATR depth zone as the action boundary, and the fixed-horizon control framework. | Composite G, E1-only first fire, and all four priced cash lines. |
| My prior pages | The unrun second-distinct-candidate proposal in `.audit/briefs/mill-sweep8-sol-out.md:96` and the two-lane state requirement in `.audit/briefs/mill-sweep3-read-sol-out.md:174`. | My remaining-opportunity caller and flow arbiter as written. Both commit on the first qualifying occurrence. |
| Pre-mill S0 and B2 | Their positive fact that within-side price order carries nearly all ceiling value. Use that fact to define the action after a causal sequence resolves. | Teacher-cash promotion, stored-label execution, S1's caller, B5's common clock, and any attempt to reopen sealed stores. |

The process must distinguish a policy KILL from an ingredient KILL. Tonight
proved that the exact first-qualified policies are dead. It did not prove that
quiet age, flow rejection, retest, prior-level contact, or candidate depth are
dead as ordered state transitions.

## Reachability under the frozen laws

The goal is reachable in the present inputs under the present costs, exit,
occupancy, and cap laws. S0R clears all three rungs with zero walls, and I4
clears all three with no side bit, near-zero MDD, and at most nine portfolio
entries. Those are oracle ceilings, not causal policies, so they do not prove a
deployable solution. They do prove that no lawful change to the inputs, costs,
exit, entry cap, or user goal is needed before testing the occurrence selector.

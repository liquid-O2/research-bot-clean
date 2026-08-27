# Covering after the S1 KILL. Fable.

Fable designer judgment, 2026-08-27. This page is the covering decision the S1 KILL routed to, per `.audit/briefs/threshold-covering-after-s1.md`. It consumes the S1 receipt `.audit/threshold-s1-sidecaller.json` (schema `QRE2THRESHOLDS1SIDECALLER1`, verdict KILL), the S1 judge `.audit/briefs/threshold-s1-sidecaller-judge-out.md`, the S1 freeze `.audit/briefs/threshold-s1-after-s0-fable-out.md`, the S0 receipt `.audit/threshold-side-split.json` (LIVE) and judge `.audit/briefs/threshold-side-split-judge-out.md`, and the live B0 map `.audit/briefs/threshold-covering-after-cfit-kill-out.md`. Provenance: this session reran `python3 .audit/score_threshold_s1_sidecaller.py` with the receipt present, exit 0, the byte sweep, `fit_digest` reproduced (`306cd0b1`), receipt file unmodified. Every dollar figure on this page was recomputed from the receipt bytes in this session's own python. The charter is unchanged. Rungs HG 2000, NKD 1500, SI 1500 `usd_per_asset_day`, `max_drawdown_usd` at most 1000, at most 12 entries per portfolio day, one contract, entry only, dollars per trade. Locked gated denominators 197 / 194 / 191. Teacher-cash can kill and cannot promote. 2021 can kill and cannot promote. 2025H1 unread, 2025H2 sealed. This page is a covering map and exactly one next experiment. Nothing runs from this page. No engine file is touched here. Tickets 37 and 47 stay unstarted. Ticket 46 work exists only inside B0 stage 0's checklist scope, after the parent dispatches.

Skips, logged per protocol:

- skip: arena subagent fan-out. Multi-agent orchestration is not opted in for this seat. The cross-model arena is the parent's reconcile of this page against Sol's sibling map on the identical brief, which this page did not read.
- skip: how and why subagent flows. The grounding is receipts on disk, cited by path, and the S1 judge reran the bytes this session.
- skip: todolist tool. Not present in this seat. The architect phases are tracked by the section order of this page.

## Frozen arithmetic. The human constraint holds.

Cell-best at 180 still clears: 2758.95 / 3815.22 / 3880.47 gated, and the rungs need 72 / 39 / 39 percent of it. `sideoracle_price` posts 2753.53 / 3806.71 / 3869.82 with MDD 192.50, path residual 5.42 / 8.51 / 10.65. The money exists at 180 and it is one bit plus hindsight price order away. What died is every measured instrument for reaching it causally, not the money. This covering names a live experiment.

## What the S1 KILL closed, scoped exactly

- The composed causal policy at 180. `policy_walkforward` posts -1.72 / -179.51 / -35.60 with MDD 59878.75.
- Both frozen within-side rules as money carriers at any side accuracy. `turncap_oracle_side` 1026.21 / 1239.91 / 1112.97 with MDD 5430.00, `recordcap_oracle_side` 811.50 / 1084.46 / 801.73 with MDD 3732.50. `p_star_eff` is 1.4440 / 1.0990 / 1.1698 on the turn pair and 1.6690 / 1.1803 / 1.3983 on the record pair. Every value is above 1, so no side accuracy in [0, 1] reaches any rung through either rule.
- The fitted causal side-caller family at 180, scoped as the freeze scoped it: prefix-aggregate features over the five parsed columns, ridge logistic, the one config. HG called 0.5335 against its pinned 0.6647 floor, a 0.1312 miss on real features at real capacity.
- Not closed: the when axis. The receipt also bought the mechanism below, which is new.

## The mechanism the receipt bought

The freeze predicted wrong calls would abstain. Measured, the asymmetry inverted. The oracle side never arms on 189 / 207 / 196 gated cells, about a third of each asset's oracle side, against 58 / 54 / 56 on the wrong side. On the correct side the record keeps improving to phase end, so the favorable extreme tends to arrive late, the turn never confirms, and the rule abstains on exactly the deep winners. `rule_forfeit` is 1727.32 / 2566.80 / 2756.85 per asset-day, 63 / 67 / 71 percent of the oracle-side money, surrendered by causal timing alone at 180.

The next sentence is inference, marked as such. If the within-side extreme tends to arrive late in the phase, then a late-age mid sits near that extreme, and repricing entry at late ages captures part of what no causal 180 rule reached. The S1 KILL's failure mechanism is the when axis's funding mechanism. B0 measures exactly this, as labels, before any picker.

## Dispatch precondition. The engine tree is dirty and import-broken.

The working tree holds a half-edit from the B0 stage-0 walker dispatched 2026-08-26T22:49Z and superseded by the 23:02 architect redirect (decision log `.audit/overnight-c-decisions.tsv`). `engine/entry_v2/confirmation.py` imports `LATE_AGE_GRID_SECONDS`, which `engine/entry_v2/confirmation_types.py` does not define, and `test_confirmation.py` carries a refusal-test sketch. `python3 -c "import engine.entry_v2.confirmation"` fails on ImportError, reproduced live this session. Disposition: the half-edit is not a base. The stage-0 runner reverts both files to HEAD before starting, performs the amendment fresh under ticket 46's own checklist, and the stage-0 receipt records the engine tree clean at start, receipt-visible, not just instructed. This page does not touch the files.

## Challenge one. A third 180s within-side rule on the same teacher join.

Best case first, as a full candidate. Candidate R: a frozen per-asset depth grid at oracle side, enter at the first called-side row whose side-relative improvement over the k=8 reference reaches depth delta, one line per delta, one read, minutes on stored bytes. It would close the fixed-depth family on a receipt instead of by argument, and it interpolates the space between earliest (enter before the excursion) and the turn rule (enter after it pauses).

Declined, on three grounds.

1. Composability. A rule line prices a policy only through a caller, and no caller exists at 180 on any plane this host fields today. The fitted family closed 0.1312 under its floor on the fired stop. Unfitted side singles sit in the dead band (+109.02 / +145.31 / +135.07) under standing family stops. Ticket 37 is parked. So an R LIVE composes with nothing and an R KILL re-confirms a closure the composition already carries. Neither outcome changes the next dispatch, which is B0 either way. A read that changes no dispatch is dead spend.
2. Read discipline. A third unit takes another one-read license on the age-180 teacher join to price a rule designed from the previous read's diagnostics. That is read-peek-amend at the design level. The S1 freeze's design-on-aggregates was priced blind once, with the receipt carrying both outcomes. Iterating flavors after seeing why two rules died is the multiple-comparisons pattern the family stops exist to prevent.
3. The design-space law itself. Turn and record bracket the confirm-versus-anticipate mechanisms, and depth parameters interpolate the same shape. A second flavor of the first shape does not count as a new candidate.

The within-side question stays real and moves venue. The B0 store prices entry mids at every grid age, so the depth family gets its honest test on late bytes under a future covering, where the side input may be observable rather than called. That last clause is inference, priced there if funded, not asserted here.

## Challenge two. B0 as the only leftover.

B0 is not the only leftover. The ledger: ticket 37 parked (twice-dead prior, new C++, and now a measured bar besides, since any caller it fed would need 0.6647 on HG where real features called 0.5335), the depth family re-venued to the late store, allocation a component bounded at 333.75, 2025 sealed pending a LIVE policy. B0 is the only fundable next unit, and its standing improved through the challenge.

- Before S1 it was rank 1 by elimination with an adverse prior (T28-grade capture 23 to 58 percent against HG's 72). Now it has a mechanism case. The never-armed mass and the late-arriving extremes are receipt facts that predict late mids retain within-side value. The elimination argument became a funding argument.
- The LIVE-limbo critique retires. The architect page held that only B0's KILL is decisive because a LIVE leaves a ceiling with no picker. That was written before the S-suite existed. A B0 LIVE now hands a measured ceiling to a covering that can port the S0 side-split instruments to the late store, minutes each on stored late bytes, with the side input possibly observable at late ages (inference, marked). Both B0 outcomes now change the dispatch.
- The S1 KILL does not impair B0's premise. It closed causal access to the 180 extreme. B0 prices access by waiting, which is a different mechanism, and its label law reprices entries at snapshot mids under the unchanged stored-teacher exit law.

## The covering set, whole shapes, updated

- Which name, new information at 180. Closed on every plane this host fields today. 37 stays the parked residue.
- Which name, combination at 180. Closed by the C receipt.
- Which name factored, side times within-side, at 180. Closed by composition on receipts: the caller leg by the S1 floor miss and the fired family stop, the rule leg by `p_star_eff` above 1 on both frozen rules, with the hindsight sup (`sideoracle_price`) requiring the extreme no causal rule reached. New flavors do not reopen it, per challenge one.
- When, by entry age. Alive, and the only live fork. B0.
- Where, allocation. Component, bounded at 333.75. Rejoins around whatever survives.
- Cross-asset. Folds into allocation (T44). Not a distinct axis.

The two whole-shape candidates, scored on the standing rubric before the verdicts above were written:

| Criterion | R, depth-grid envelope at 180 | B0, late-age ceiling |
|---|---|---|
| Reach | Bounded above by `sideoracle_price`, which clears, but unreachable by any composed policy since no caller exists | Unmeasured, with the never-armed and forfeit mechanism now behind it |
| Cost | Minutes, one read, stored bytes | Ticket 46 amendment plus the 582-day sixteen-age relabel, two stages |
| Sure-shot | Neither outcome changes the next dispatch, which is B0 either way | KILL closes the when axis with receipts; LIVE hands a measured ceiling to the S-suite port |
| Charter fit | Fits mechanically, but spends a one-read license a closed axis cannot repay | Fits, requires the one funded amendment |
| Root-cause fit | Iterates the same shape the receipts killed twice | Funds the axis the failure mechanism points at |

B0 wins on sure-shot and root-cause fit, and R's cost advantage buys nothing a dispatch can use.

| Candidate shape | Verdict | Reason and receipt |
|---|---|---|
| B0, late-age ceiling on era days | NAMED | Funded by the S1 KILL bullet and this page; mechanism upgraded by the never-armed and forfeit blocks |
| R, depth-grid envelope at 180 | KILLED | Challenge one: no caller to compose with, license discipline, same-shape flavor |
| Stall-timing side caller (arming asymmetry as side signal) | KILLED | Composition: `p_star_eff` above 1 on both frozen rules, and a caller without a rule has no dollar line; new rules are challenge one |
| Fitted within-side timer at oracle side | KILLED | Same composition, and it is a fitted flavor read on the same join |
| Pooled cross-asset side caller | FORBIDDEN | Second config of the closed S1 family, per the fired stop |
| S0 rerun at age 300 | COLLAPSES INTO B0 | No stored label prices any entry later than the stored teacher's own; 300 is on B0's grid |
| Late-mass bound read from stored bytes | KILLED | Bound invalid; the minutes section below |
| Ticket 37, G1 birth-tape histograms | PARKED | Twice-dead prior, new C++, and the measured caller bar |
| 2021 resurrections, any form | KILLED | Standing receipts; cite, never rerun |
| Opening 2025 bytes | SEALED | No LIVE policy exists to test; the seal is for a held-out walk |
| Allocation, abstention, concentration as primary | KILLED | Bounded at 333.75 of the 2.09M gap |

## Rank and the minutes question

The brief prefers stored-byte minutes if any remain. Worked once more against the new receipts, and the answer is that none remain that carry a decision. The one candidate a minutes preference surfaces is a late-mass bound in front of B0, computed per grid age as the cells surviving past that age times their S0 price-line cash, read from stored bytes, killing B0 for free if the bound misses a rung. It is invalid. B0's label rule enters at the age-A snapshot mid, a path point between stored rows, and row-anchored price cash does not bound a path-point entry, so the bound can undercount the late envelope and a KILL on it would be unsafe. The degenerate safe clause, exactly zero late mass, is excluded in kind by the T28 hold's measured entry ages of 7380 and 10980 seconds (2021, adjacent evidence, different name universe) and is re-checked anyway by B0 stage 0's own feasibility question on one pilot session in minutes. The prior map's sentence stands re-derived on the new receipts: no minutes path prices a late entry, and the cheapest honest build is the locked-days label build. The minutes that remain live inside B0 stage 0.

## The one next experiment. Unit B0, verbatim.

B0 exactly as `.audit/briefs/threshold-covering-after-cfit-kill-out.md` specifies, unchanged: the preregistered sixteen-age grid, the frozen one-sentence label rule, stage 0 (the ticket 46 amendment under its own checklist, pilot session HG/20221003 from `.audit/ticket45-HG-20221003-cache.json`, builder determinism, the teacher-equality byte check, the two-hour projection tripwire, receipt `.audit/threshold-b0-stage0.json`), stage 1 (the late store for exactly the 582 locked asset-days, one read, per-age ceiling lines, the per-asset late envelope at ages at or past 600, the under-300 anchor controls, the four red-first mutants, receipt `.audit/threshold-b0-stage1.json`). This page adds dispatch state, not spec: the engine-tree precondition above, and the S1 priors as record. The T28 tension rides along unchanged: T28-grade capture at zero forfeit spans 634.56 to 1600.19 on HG against a 2000 rung, so any future picker's bar binds on HG, and the ceiling read decides whether the room exists before any picker is designed.

## Dollar stop. Condensed from the pinned map, checked clause by clause.

The binding verbatim is the pinned map's stop section. Condensed per the S0 precedent:

- STOP at stage 0. The amendment fails its review, the off-schedule fixture is not red-first, snapshots past 600 seconds cannot be emitted or priced, builder determinism drifts, the teacher-equality check mismatches, any stored tree is touched, or the projection passes two hours. Infrastructure stop: report and wait.
- KILL at stage 1. Some asset's late envelope, every cell at its best age at or past 600 seconds, misses that asset's rung on the locked denominators. The when axis closes on era days with exact labels. No live fork remains on this host. The dead end is named to the user with receipts at every node, and nothing is auto-funded.
- LIVE at stage 1. Every asset has at least one fixed grid age at or past 600 seconds whose ceiling line posts trades above zero and clears that asset's rung, caps and overlap holding, witness ages per asset legal. The successor is a late-age picker covering with a pre-stated capture fraction, HG binding, which also owns the training-scale relabel spend. This page pre-names the S-suite port as that covering's design direction and funds nothing.
- ENVELOPE-ONLY at stage 1. The envelope clears everywhere but some asset lacks a fixed-age witness. Curves report to the next covering. Not a LIVE, not a KILL, not an invitation to add ages.

## Forbidden

Inherited verbatim from the pinned map: no picker on the late labels, the ceiling read is the unit's only read, `mfe_usd`, `mae_usd`, `payer`, `take_target` stay unparsed, no 2025 bytes, no 2021 late labels, no change to gate, denominators, ruler, or rungs, no second grid or added age, no relabel beyond the locked 582 days, no feature planes, no dead-family scoring on the late store, no T28 formula, no tickets 37, 46-at-scale, or 47, no rerunning cited kills as anything but numbers. This page adds: no third 180s within-side rule, and no new one-read license on the age-180 teacher join for any 180s rule or caller unit while B0 is in flight, per challenge one. B0's own stage-0 teacher-equality parse stays licensed exactly as the pinned map specifies. No building on the reverted half-edit.

## Seats

Runner is Sol as a specified sequence, Codex `gpt-5.6-sol` at reasoning effort max, the `-max` slug rejected by the host (decision log 2026-08-26T20:13Z). Judge is Fable, `claude-fable-5` at effort max, on the receipt bytes per stage. Stage 1 fires only on a stage-0 PASS judgment. Parent dispatches fresh children per stage with file pointers, never resume-chains, and does not execute the walk. Parent reconciles this page against Sol's sibling map before dispatch. Per the brief, Fable's name is the live walk.

## Principles that changed a decision

- exhaust-the-design-space and codebase-design DESIGN-IT-TWICE. R stood as a full candidate with its best case before its decline, and the kept-or-killed table carries every shape considered, not just the winner.
- fix-root-causes. The covering traces the KILL to the late-arriving extreme and funds the axis that mechanism points at, instead of iterating a third rule flavor on the same symptoms.
- laziness-protocol and subtract-before-you-add. Zero spec deltas to B0. The half-edit is reverted, not completed. The bound read and R died before anything was added.
- prove-it-works. Every number here was recomputed from receipt bytes this session, the sweep reran exit 0 with `fit_digest` reproduced, and the import break was reproduced live rather than inferred from the diff.
- sequence-verifiable-units. Two stages, each ending in a judged receipt, stage 1 gated on stage 0, the engine tree proven clean inside the stage-0 receipt.
- redesign-from-first-principles. The covering set was rebuilt around the composition closure the receipts proved, instead of inheriting the prior frame and appending a row.
- never-block-on-the-human. One experiment named, both outcomes pre-wired, the two ordered challenges answered on the page, no fork question returned.

## Next step

Parent reconciles this page against Sol's sibling map, then dispatches Sol on B0 stage 0 as the specified walk with file pointers: this page, `.audit/briefs/threshold-covering-after-cfit-kill-out.md`, `.audit/ticket45-HG-20221003-cache.json`, `.audit/score_threshold_2022_2024_ceiling.py`, `.audit/threshold-2022-2024-ceiling.json`, `.audit/threshold_pivot_stage0.py`, `.audit/score_h5_top2.py`. Fable judges each stage's receipt bytes. B0 starts only from that dispatch and nothing starts from this page.

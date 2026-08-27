# Covering after the B1 KILL. Fable.

Fable designer judgment, 2026-08-27. This page is the covering decision the B1 KILL routed to, per `.audit/briefs/threshold-covering-after-b1.md`. It consumes the B1 receipt `.audit/threshold-b1-picker.json` (schema `QRE2THRESHOLDB1PICKER1`, verdict KILL), the B1 judge `.audit/briefs/threshold-b1-picker-judge-out.md`, the covering that named B1 `.audit/briefs/threshold-covering-after-b0-fable-out.md`, the prior Sol sibling `.audit/briefs/threshold-covering-after-b0-sol-out.md` (a named input of this brief, unlike the blind sibling of the prior round), the B0 stage-1 receipt `.audit/threshold-b0-stage1.json` and judge, and the frozen charter facts carried on those pages.

Provenance. This session reran `python3 .audit/assert_threshold_b1_picker.py` in the background and waited for it here. It printed `PASS all byte checks held wall=153.1s verdict=KILL reproduced from raw bytes`, exit 0, the full per-age surface byte-equal to the receipt for all five lines and seven ages. Every dollar figure on this page was recomputed from receipt bytes in this session's own projection. Zero store shards were opened and zero dollar lines formed. Three engine files were read for semantics only, read-only, disclosed with line references below. They are `engine/entry_v2/late_teacher.py`, `engine/entry_v2/confirmation_index.py`, and `engine/entry_v2/tabular_delayed_outcomes.py`. No engine file was touched. No stored teacher byte was opened. The Sol sibling for this round was not read and did not exist among this page's inputs.

The charter is unchanged. Rungs HG 2000, NKD 1500, SI 1500 `usd_per_asset_day`, `max_drawdown_usd` at most 1000, at most 12 entries per portfolio day, one contract, entry only, dollars per trade. Locked gated denominators 197 / 194 / 191. Teacher-cash can kill and cannot promote. 2021 can kill and cannot promote. 2025H1 unread, 2025H2 sealed. This page is a covering map and exactly one next experiment. Nothing runs from this page. No engine file is touched here. The age-180 teacher join stays closed, a third 180 s rule stays forbidden, no sixth line is added to the B1 receipt, and tickets 37, 46 at scale, and 47 stay unstarted.

Skips, logged per protocol:

- skip: arena subagent fan-out. Multi-agent orchestration is not opted in for this seat. The cross-model arena is the parent's reconcile of this page against the Sol sibling on the identical brief.
- skip: how and why subagent flows. The grounding is receipts on disk cited by path, the byte sweep reran here, and three targeted engine-source reads disclosed above.
- skip: architect Phases D and E. The brief funds Phases A through C. The artifact is a named design for dispatch, not an implementation.
- skip: todolist tool. Not present in this seat. The architect phases are tracked by the section order of this page.

## Frozen arithmetic. What the B1 KILL measured.

Age-600 snapshot, `usd_per_asset_day` with `max_drawdown_usd` in brackets, from the receipt and byte-verified by this session's sweep rerun.

| line | HG (rung 2000) | NKD (rung 1500) | SI (rung 1500) |
|---|---|---|---|
| record_top1_all | -204.59 [46243.75] | -459.14 [89072.50] | -303.15 [58350.00] |
| record_top1_pos | -204.53 [46232.50] | -459.14 [89072.50] | -305.04 [59140.00] |
| sideoracle_record | 492.75 [2077.50] | 395.37 [9397.50] | 258.23 [8577.50] |
| recordside_price | 2061.09 [511.25] | 2657.81 [597.50] | 3001.16 [472.50] |
| cellbest_control | 2726.81 [0.00] | 3775.72 [0.00] | 3847.62 [0.00] |

Both primaries are negative at every age on every asset with MDD in the tens of thousands. The frozen observable-record family is closed at late ages on era labels, by receipt, and stays closed on this page. The two decomposition clues split cleanly.

- The side-shaped clue does not fire. `sideoracle_record`, oracle side with causal record-max depth, posts 492.75 / 395.37 / 258.23 at 600, decays through 118.60 / 101.69 / -2.67 at 2400, and is negative nearly everywhere from 3600 on, MDD 2077.50 to 36260.00. Handing the picker the correct side does not rescue record-magnitude depth.
- The depth-shaped clue fires. `recordside_price`, observable side with oracle depth, posts the full dollar block at 600 through 3600 on all three assets, and NKD and SI clear at all seven ages. MDD stays under 1000 on every block of this line, worst 947.50 at NKD 7200. HG falls off its rung at 5400.
- `side_agreement` runs 0.637 at 600, peaks at 0.706 at 2400 and 0.700 at 3600, and decays to 0.631 at 10800. The observable record carries about two thirds of the hindsight side.

The side leg is measured observable. The whole miss is the within-side depth leg. B0's room still stands above everything, cell-best 2726.81 / 3775.72 / 3847.62 at 600 on the locked denominators.

## The exit law, read from source. The oracle depth is mostly observable.

The B1 judge's mechanism paragraph was marked inference. This page grounds it in the engine source, read-only.

The late store's age-A row enters at that row's own snapshot BBO. `_label_at_age` in `engine/entry_v2/late_teacher.py` (lines 396 to 444) takes the quote at the age-A snapshot, stores `entry_mid2` as the bid plus ask sum, and stores `frozen_cost_usd` as the observable spread cost plus the fee (lines 408 to 411). The outcome comes from `_OutcomeIndex.outcome` in `engine/entry_v2/confirmation_index.py` (lines 169 to 212). The law is exact. `cert_close_usd` equals `side * (exit_mid - entry_mid2) * factor - frozen_cost_usd` with `factor = 0.5e-9 * ASSET_MULTIPLIER` (lines 134 and 196). The exit is the first adverse wall crossing at 900 dollars net of costs if one occurs in the same-generation suffix before phase close, else the last same-generation mid before phase close (lines 188 to 194, `WALL_USD = 900.0` in `engine/entry_v2/confirmation_types.py`). The wall floors every entered trade's loss near 900 dollars, which is why a two-thirds-right side with bounded losses holds MDD under 1000 on the `recordside_price` line.

Decompose the oracle depth pick with that law. Within one cell and one side at age A, every candidate's cert is a common exit term minus its own observable effective price, `side * entry_mid2 * factor + frozen_cost_usd`, except where two hindsight channels break the commonality. The wall channel, whether a given entry's suffix crosses its own entry-relative wall. The suffix channel, generation boundaries between two candidates' snapshots giving them different exit positions. So the pick `recordside_price` makes with `cert_close_usd` is the pick the observable effective-price minimum makes, up to exactly those two channels. The judge's closing sentence read the money as sitting with "the fitted-ranker question the covering reserved, not a new frozen variant." That sentence was inference written without the exit-law fact above. The observable component of the oracle depth is a frozen, causal, one-read question, and whether the residual hindsight channels are small enough to clear the rungs is precisely what one read decides. The fitted ranker is the fallback if the observable component misses, and the same read prices the fallback's target.

## The depth bar, pre-stated. The bound is by construction.

Any pick made from the same side set is bounded above, cell by cell, by the set's cert maximum, which is what `recordside_price` enters. So `recordside_price` is a per-cell upper bound on any causal same-side depth rule, and the required depth capture is the rung divided by that line, per asset and age. Closed cells are ages where the bound itself misses the rung.

| age s | HG bound | HG bar | NKD bound | NKD bar | SI bound | SI bar |
|---|---|---|---|---|---|---|
| 600 | 2061.09 | 97.0% | 2657.81 | 56.4% | 3001.16 | 50.0% |
| 1200 | 2119.21 | 94.4% | 2846.66 | 52.7% | 3009.80 | 49.8% |
| 2400 | 2180.59 | 91.7% | 2740.28 | 54.7% | 3054.27 | 49.1% |
| 3600 | 2083.13 | 96.0% | 2645.57 | 56.7% | 3001.13 | 50.0% |
| 5400 | 1873.23 | closed | 2478.62 | 60.5% | 2800.27 | 53.6% |
| 7200 | 1660.53 | closed | 2232.74 | 67.2% | 2565.52 | 58.5% |
| 10800 | closed | closed | 1815.41 | 82.6% | 2043.15 | 73.4% |

HG binds hard. Its four open ages leave 3.0 to 8.3 percent headroom, so a causal depth rule clears HG only if it agrees with the oracle pick on nearly every cell or disagrees on near-ties. NKD and SI leave 17 to 51 percent. That is the sharp falsifier, not a defect. The bound caps per-cell cash, not drawdown. A causal pick can wall out near 900 dollars per hit and stack hits, so the MDD law binds independently and a rung cleared with MDD above 1000 stays a KILL.

## Challenge one. Fitted-or-dead, ruled here.

The prior covering pre-registered the evidence that would let this page price the training-scale relabel, and that evidence fired. `recordside_price` clears, a depth-shaped gap. The ruling is that fitted-or-dead is a false dichotomy on these numbers. The receipt's own clearing line decomposes, by the exit law above, into an observable component and two hindsight channels, and no receipt prices the observable component alone. Between "fund a fitted ranker" and "dead" sits one frozen, unfitted, minutes-scale read that faces the rungs directly. The relabel is therefore priced at zero on this page. The evidence that funds it is named now, either a B2 LIVE, where the exit leg and validation scale earn the spend exactly as B1's LIVE clause anticipated, or a B2 KILL whose `recordside_price_control` still clears where the primaries missed, with `pick_agreement` materially below one. That number is the hindsight channels' price in dollars, the fitted fork's named target. The next covering spends against B2's receipt or not at all. Destiny is not assumed in either direction.

## Challenge two. LSP0, declined as a unit, grafted as a line.

The Sol sibling named LSP0, an oracle-side price cap. Declined on three grounds. First, the seam moved. LSP0 instruments the side leg with an oracle while asking a price question inside it, but B1 measured the side leg observable and sufficient, so an oracle-side unit spends the read on the leg that is no longer the question. Second, license economics. Every LSP0 line is oracle-capped, so no outcome can face the rungs, every branch routes to another unit and another read, the same pass-through-at-unit-altitude shape that killed the standalone S-port last round. Third, its causality objection is answered. LSP0 treats READY as a future fact, but the frozen B0 label law makes READY at age A a decision-time-and-phase-open fact, row conformance verified on all 2,923,344 rows by the B0 stage-1 judge, and the B1 primaries already entered on that law and were judged causal. The graft survives the decline. LSP0's core score, within-side price order, enters B2 as the causal depth leg, sharpened by the cost term the exit law names, and its oracle-side variant enters as one decomposition line so the side leg's residual cost under the price rule is priced too.

## Challenge three. A new frozen unfitted variant, challenged and bounded.

Two frozen families have died on this program, the 180 s rules and the observable-record family, so a third frozen guess deserves hostility. B2 is not a guess. Its primary is bounded above per cell by a line the receipt already measured clearing, its predicted value is that line minus the hindsight channels the exit law names, and the read that prices it also prices the fitted fallback's target if it misses. No other frozen variant has that property. And the family is bounded ahead of time. The store schema carries prices, costs, sides, timestamps, and the record base, nothing else. After B1 killed record-maximal depth and B2 prices record-laggard and effective-price depth, the single-snapshot one-scalar depth plane on this schema is exhausted. Earliest-decision died twice on this host and stays dead. Spread alone is a cost, not a ranking signal, and is inside the effective-price score already. Path-shaped frozen rules over earlier grid ages remain constructible but stay unfunded unless a B2 receipt names a specific clue. A B2 KILL therefore closes the frozen unfitted within-side family on this store with no third frozen escape, which is what makes the fitted-or-dead fork honest if it ever fires.

## The covering set, whole shapes, updated

- Which name at 180, all forms. Closed by receipts. The age-180 teacher join stays closed.
- When, does the room exist. Measured LIVE by B0. Still standing, cell-best clears at 180 s and at 600 s.
- When, is the room causally reachable. Split by B1. The side leg is measured observable, about two thirds agreement, sufficient under oracle depth. The depth leg is the one live fork. B2 below.
- The fitted branch. Parked, priced at zero here, funding criterion named in challenge one.
- Oracle-side instruments, LSP0 and ports. Declined as units, price-order core grafted into B2.
- Where, allocation. Component, bounded at 333.75. Rejoins around whatever survives.
- 2021 kill-only, 2025H1 unread, 2025H2 sealed. Unchanged.

## The two whole-shape candidates

Rubric inherited for cross-page comparability, reach, cost, sure-shot, charter fit, root-cause fit.

Candidate F, the fitted within-side ranker with the training-scale relabel, best case first as a full candidate. The pre-registered depth-shaped criterion fired, so the relabel buys training bytes for a ranker aimed at a gap the receipt proves exists, validated on the locked store, the one shape that can chase the hindsight channels themselves. Declined for this slot on ordering, not on destiny. Its spend is the program's largest, its cash plane cannot promote regardless, the C-fit precedent posted -173.50 / +31.20 / -150.45 with MDD 75608.75 and closed its axis honestly only after frozen instruments exhausted the unfitted planes, and the fork's own decision improves strictly for the cost of one 330 s read, since a B2 LIVE re-prices the relabel against a causal policy's successor questions and a B2 KILL hands the fit its measured target. Funding criterion in challenge one.

Candidate B2, the frozen effective-price picker on the observable record side, named below.

| Criterion | F, fitted ranker plus relabel | B2, effective-price picker |
|---|---|---|
| Reach | Unmeasured, and its cash plane cannot promote | Primary is fully causal and faces the rungs directly under a measured upper bound |
| Cost | The program's largest spend before its first dollar | Minutes, one licensed read, same shape as B1's 330 s run |
| Sure-shot | A miss prices one fitted flavor, not the plane | LIVE names a causal policy on era labels, KILL closes the frozen unfitted family and prices the fitted target, both decision-changing |
| Charter fit | Fits only behind a covering fight for training bytes | Frozen, unfitted, one read, bar pre-stated on this page |
| Root-cause fit | Chases the residual before the observable component is priced | Tests the exact component the exit law isolates from B1's miss |

Red-flags screen of both candidates against `.cursor/plugins/pstack-lab/skills/architect/references/design-red-flags.md`. B2 screens clean. One scorer, one receipt, five preregistered lines per age behind one dollar-block interface, and the lines fill the design square completely, side in observable or oracle crossed with depth in causal or oracle. The primaries are observable side with causal depth in two flavors, `oracleside_effprice` is oracle side with causal depth, `recordside_price_control` is observable side with oracle depth, `cellbest_control` is the oracle-oracle corner, every corner measured here or byte-matched to its prior measurement. No new store, no new schema, no engine file, the score defined once from pinned columns. F screens with one flag, information leakage at the program level, since the relabel commits training bytes whose label law would then constrain every later unit before any bound exists on what a fit can reach, the same big-spend-before-a-narrow-bound shape the Sol sibling itself rejected for its Shape J. LSP0 fails the pass-through screen as a unit, every outcome routing to another unit, per challenge two. A covering that declares the program over is rejected on the receipts, `recordside_price` clears 600 through 3600 on all three assets with MDD under 1000, the side leg is measured observable, and one unfitted causal depth observable is unpriced. The human constraint stands.

## The one next experiment. Unit B2, the frozen effective-price picker on the observable record side.

One stage, one script, one receipt, one licensed dollar read of the late store. The fired B1 stop said nothing is auto-funded, "no fitted picker, no training-scale relabel, no third read, no new variant," and the B1 covering said every further read is a new covering fight. The fight is this page. This page licenses the store's third dollar read, scoped to exactly this unit, one pass, and funds nothing else. No build, no engine file, no new tree. New files are exactly `.audit/score_threshold_b2_price_picker.py` and `.audit/threshold-b2-price-picker.json`. The read verifies the manifest sha and every consumed shard sha against `artifacts/cache/port/entry_v2/g1/late/manifest.tsv` before any dollar forms, refuses on any denominator drift from 197 / 194 / 191, and consumes the same 582 shards, 2,923,344 rows, 2,768,741 READY, 182,709 CLEAR candidates. Age-0 rows are consumed solely as the record base, their `cert_close_usd` never read, and no dollar line forms at any age under 600. The B1 receipt is not modified and gains no line.

The side law, defined once and byte-compatible with B1. S(c, A) is the stored side of the row `record_top1_all` would enter, the maximal r(X, A) among READY age-A rows of gated cell c, ties smallest `candidate_id`, with r and its sign convention exactly as the B1 scorer computes them. The side set is the cell's READY age-A rows restricted to S(c, A). It is nonempty by construction, it contains the maximal-r row, and a singleton set enters its only row. This is the identical restriction `recordside_price` used, which is what makes that line an exact per-cell upper bound on both primaries.

The frozen lines, per late age A in 600, 1200, 2400, 3600, 5400, 7200, 10800, each aggregated with the family ruler `summarize_line` on the locked denominators, `entered_cells` and `eligible_candidates` reported per line per age so thinning is visible:

- `recside_effprice_all`, primary one, ranked first on this page before the read. Within the side set, enter the row minimizing `side * entry_mid2 * factor + frozen_cost_usd`, with `factor = 0.5e-9 * ASSET_MULTIPLIER[asset]` per `engine/entry_v2/confirmation_index.py` line 134, ties smallest `candidate_id`, unconditionally. Cash is the entered row's `cert_close_usd`. The pick is blind to every cash column.
- `recside_lagrecord_all`, primary two. Within the side set, enter the row minimizing r(X, A), ties smallest `candidate_id`, unconditionally. The record's magnitude was anti-signal at the maximum by B1's receipt, and the cash identity cash at A equals cash at 0 minus factor times r makes the minimum the algebra's other one-scalar reading. This prices it once, in the same unit as the level rule, and does not reopen the closed record-maximal family.
- `oracleside_effprice`, decomposition, oracle side with causal depth. Restrict the cell's READY age-A rows to the stored side of the age-A cell-best row, the `sideoracle_record` restriction, then enter the effective-price minimum, ties smallest `candidate_id`. Prices the side leg's residual cost under the price rule, the honest form of LSP0's core line. Can kill or price. Cannot promote or witness.
- `recordside_price_control`, determinism control and the bound. Recompute B1's `recordside_price` line from this read. It must equal the B1 receipt's per-age blocks byte for byte at every age. A mismatch impeaches the read or the ruler and is a STOP, not reported drift.
- `cellbest_control`, determinism control. Recompute B0's age-A ceiling line. It must equal the B0 receipt's per-age dollar blocks byte for byte, the same law B1 enforced.

Three reported scalars besides, none with a dollar attached. `pick_agreement` per asset and age, the fraction of entered cells where `recside_effprice_all` picks the same row as `recordside_price_control`. `depth_regret_usd_per_day` per asset and age, the control's per-day dollars minus the primary's. `primary_agreement` per asset and age, the fraction of cells where the two primaries pick the same row. Convergence of the primaries is reported, not resolved by taste.

The family is exactly these five lines and seven ages, frozen here. Exactly two variants are primaries and both are reported everywhere. LIVE multiplicity law, verbatim for the receipt. A LIVE requires one pre-named primary, the same primary for all three assets, to post the full dollar block at some qualifying age per asset, per-asset witness ages legal. If both primaries qualify, the LIVE names `recside_effprice_all`, ranked first above. A mixed primary assignment across assets is not a LIVE and is reported as the KILL fact it is. Decomposition and control lines never witness. Qualifying ages re-derive from the B0 receipt exactly as B1 did, HG 600 through 7200, NKD and SI all seven. The depth-bar table above is evidence about reachability, not a change to the age law. Templates, pinned as sources with sha256s alongside this page, the B1 receipt and judge, and the two engine files whose semantics ground the design, `engine/entry_v2/late_teacher.py` and `engine/entry_v2/confirmation_index.py`, neither imported at runtime. `.audit/score_threshold_b1_picker.py` for the store read, manifest verification, side laws, r convention, and per-age blocks. `.audit/score_threshold_b0_stage1.py` for the read discipline. `.audit/score_threshold_2022_2024_ceiling.py` for the ruler and denominators. `.audit/score_h5_top2.py` for selftest and receipt discipline.

Selftest on synthetic rows, zero era bytes, then red-first mutants, each introduced before its guard and each dying on its named seam. `oracle_leak_primary`, a primary pick that consults any `cert_close_usd` must die. `nonready_entered`, an entry on a non-READY age-A row must die. `future_mid_in_pick`, a side or depth input computed from any mid at a snapshot later than age A must die. `control_mismatch_accepted`, a corrupted `cellbest_control` or `recordside_price_control` block that fails to fire the STOP must die. Receipt schema `QRE2THRESHOLDB2PRICEPICKER1`, `dollar_line_reads` counted and equal to 1, `passes_over_late_store` 1, wall clock recorded. B1's identical read shape projected 500.86 s and ran 330.07 s, so the honest projection method is inherited and the tripwire stays 3600 s. Judge brief lands at `.audit/briefs/threshold-b2-price-picker-judge-out.md`.

## Dollar stop. Bound now, fires on the receipt.

- **STOP, infrastructure.** The selftest fails, any mutant is not red-first or survives, `cellbest_control` mismatches the B0 receipt at any age, `recordside_price_control` mismatches the B1 receipt at any age, the manifest or any shard sha mismatches, denominators drift, any stored tree is touched, `dollar_line_reads` exceeds 1, or wall clock passes 3600 s. Report and wait. No dollar conclusion is drawn from a stopped run.
- **KILL.** For some asset, both primaries miss the full dollar block at every qualifying age, or no single primary carries all three assets. A miss on the pre-stated bar is a KILL, not a near-miss, including a rung cleared with MDD above 1000. The frozen unfitted family of single-snapshot one-scalar depth rules on the observable side closes on this store, record ranking by B1, price and laggard ranking by B2, with no third frozen escape unless this receipt's own decomposition names a specific path-shaped clue. If `recordside_price_control` still clears where the primaries missed, the gap between them, carried by `depth_regret_usd_per_day` and `pick_agreement`, is the hindsight channels' price and the fitted fork's named target. The next covering decides fitted-or-dead against those numbers. Nothing is auto-funded, no fitted picker, no training-scale relabel, no fourth read, no new variant.
- **LIVE.** One pre-named primary, the same for all three assets, posts the full dollar block at some qualifying age per asset, caps and overlap holding, MDD at most 1000, on the locked denominators. If both qualify, the LIVE names `recside_effprice_all`. A fully causal entry rule on the stored-teacher exit law pays every rung on era labels. Teacher-cash cannot promote, so nothing ships from a LIVE. The successor questions are the exit leg, whose stored law is the wall-or-phase-close hindsight law read from source above, and validation scale, authorized by the next covering, which also owns the training-scale relabel priced against this receipt. Nothing else is funded.

## Forbidden inside B2

Any fit, any parameter chosen from the read, any line or age beyond the five and seven frozen here, any post-hoc variant or tie-break change. A second read of the late labels inside the unit, or any read outside it. Parsing any column beyond the pinned late header schema. Opening any stored teacher byte. No 2025 bytes of either half, no 2021 late labels, no change to gate, denominators, ruler, or rungs, no added age or second grid, no relabel, no feature planes, no dead-family scoring, no T28 formula. No third 180 s rule and no new license on the age-180 teacher join while B2 is in flight. No near-miss language in the receipt. No engine file. Tickets 37, 46 at scale, and 47 stay unstarted. Cited kills rerun as numbers only.

## Seats

Runner is Sol as a specified sequence, Codex `gpt-5.6-sol` at reasoning effort max, the `-max` slug rejected by the host (decision log 2026-08-26T20:13Z). Judge is Fable, `claude-fable-5` at effort max, on the receipt bytes. One stage, one walk, one judgment. Parent Grok dispatches a fresh child with file pointers, this page, the B1 receipt and judge, the B0 stage-1 receipt and judge, and the four templates, never resume-chains, and does not execute the walk. Parent reconciles this page against the Sol sibling on the identical brief before dispatch. Per the brief, Fable's name is the live walk, and the name is B2.

## Principles that changed a decision

- exhaust-the-design-space and codebase-design DESIGN-IT-TWICE. The fitted candidate stood as a full shape with its best case before its decline, the two primaries are genuinely distinct anchors, level against record, both preregistered instead of one chosen by taste, and their agreement is a reported scalar.
- laziness-protocol and subtract-before-you-add. The positivity gate B1 measured near-vacuous is dropped, the relabel is priced at zero, no engine code, no new tree, the third read licensed once and scoped, five lines where the design square needs exactly five.
- fix-root-causes. B1's root cause is isolated by the cash identity, record magnitude anti-selects remaining profit, so the unit tests the exact observable component the exit law names instead of a third guess at a new plane or a premature fit.
- prove-it-works. The byte sweep reran here and was waited on, `PASS all byte checks held wall=153.1s`, every figure recomputed from receipt bytes, the exit law verified in source with line references, and both controls make the third read prove itself byte for byte against B0 and B1.
- sequence-verifiable-units. One unit ending in one judged receipt, the fitted fork sequenced behind it with its funding criterion named, the family's exhaustion point declared before the read.
- redesign-from-first-principles. The covering set was rebuilt around the split B1 created, side solved and depth open, and LSP0's price idea was redesigned into causal form with the cost term rather than pasted as an oracle cap.
- guard-the-context-window. The 50 k-token receipt was consumed by projection, the engine files by targeted section reads, and no store shard was opened.
- never-block-on-the-human. One experiment named, both outcomes pre-wired, fitted-or-dead ruled on this page instead of returned as a fork question.

## Next step

Parent reconciles this page against the Sol sibling on the identical brief, then dispatches Sol on B2 as the specified walk with file pointers, this page, `.audit/threshold-b1-picker.json`, `.audit/briefs/threshold-b1-picker-judge-out.md`, `.audit/threshold-b0-stage1.json`, `.audit/briefs/threshold-b0-stage1-judge-out.md`, `.audit/score_threshold_b1_picker.py`, `.audit/score_threshold_b0_stage1.py`, `.audit/score_threshold_2022_2024_ceiling.py`, `.audit/score_h5_top2.py`. Fable judges the receipt bytes. B2 starts only from that dispatch and nothing starts from this page.

# Why docs slice. Findings only

Long-form investigator. Repo docs are the store. No Notion or other MCP. Do not treat this page as the whole case.

Question. Why does live entry take a name that is not the cell-best, and why were earliest CLEAR, E1R, and roster the attempted instruments?

Bounds. Entry only. One mini. No exits. No extra size.

## Source

Long-form documents. Slice `design/entry_reset/`, `START_HERE.md`, `.audit/threshold-path-to-rungs.md`, and the cited receipts. Freeze page opened because the read and capture-gap receipts name it as the bound rule.

## What I searched

Queries in `design/entry_reset/` and the slice files:

- `cell-best`, `cell best`, `cell_best`, `CLEAR`, `earliest CLEAR`, `E1R`, `roster`, `identity`, `skill-free`, `unmeasured lever`, `instrument`, `side-then-earliest`, `never ENTER`, `top-2`, `top two`
- `compliance_status` and `earliest CLEAR` inside `design/entry_reset` (null)
- Cited receipts and their `named_cause`, `dollar_stop`, `h5_conclusion`, `kill_bar`, `lines.*` fields

Opened in full or in the named sections:

- `START_HERE.md` (2026-08-26)
- `.audit/threshold-path-to-rungs.md`
- `.audit/threshold-capture-gap.json`
- `.audit/threshold-enter-gap-20260825.json`
- `.audit/threshold-roster-kill.json`
- `.audit/threshold-h5-top2.json` (`definitions`, `h5_conclusion`, H3/H5/H7 `overall`)
- `.audit/threshold-2022-2024-read.json` (`frozen_rule`, `dollar_stop`)
- `.audit/threshold-2022-2024-freeze.md`
- `design/entry_reset/DIAGNOSIS_20260822.md`
- `design/entry_reset/overview.md`
- `design/entry_reset/T50_DIAGNOSIS_20260823.md`
- `design/entry_reset/tickets/51-loser-screen.md`
- `design/entry_reset/ENTRY_PLAN_20260823.md`
- `design/entry_reset/HANDOFF_DECISION_PLANE_20260822.md`
- `design/entry_reset/tickets/24-prefix-peer-nonclock.md`
- `design/entry_reset/FABLE5_XHIGH_LABEL_DIAGNOSIS.md` sections 2 and 5
- `design/entry_reset/SELECTION_HOLD_EXTREME_20260822.md`
- `design/entry_reset/T29_T34_VERDICT_20260823.md`
- `design/entry_reset/T35_VERDICT_20260823.md`
- `design/entry_reset/T39_VERDICT_20260823.md`
- `design/entry_reset/T53_REGIME_SPLIT_20260823.md`
- `design/entry_reset/T54_FORWARD_VOL_20260823.md`
- `design/entry_reset/OPUS5_MAX_LABEL_DIAGNOSIS.md` M2-M5 and C1
- `design/entry_reset/55-entry-v2-recovery-plan/confirmation-receipt-audit.md`
- `design/entry_reset/55-entry-v2-recovery-plan/evidence.md`
- `design/entry_reset/55-entry-v2-recovery-plan/frontier.md` (identity rows)
- `.audit/score_threshold_2022_2024_read.py` `pick_cell_names`
- `.audit/score_threshold_2022_2024_ceiling.py` `pick_cell_best_ready`

Opened as follow-ons, not in the named slice:

- `.audit/briefs/threshold-covering-after-kill-out.md`
- `.audit/briefs/roster-kill.md`
- `.audit/briefs/roster-kill-judgment.md`

## Direct evidence found

### Live 2022-2024 pick is earliest CLEAR, not cell-best

- **What it says.** Live cursor. "Earliest CLEAR matches cell-best in 149 of 1732 cells. The winner sits at mean time rank 28 in a mean cell of 105 names. Latest and cheapest CLEAR also miss."
- **Where.** `START_HERE.md` lines 13-16. Dated 2026-08-26.
- **Relevance.** States the miss as within-cell identity on the stored join.

- **What it says.** `capture.n_earliest_is_best` 149, `n_cells` 1732, `match_rate` 0.0860, `mean_best_time_rank` 28.22, `mean_cell_n_clear` 105.49. `dollar_stop.applied` quotes the same miss and names the next unit as "one live G1 scalar that is not time or cost, or one fitted name instrument." `lines.cell_best` clears the rungs (HG 2758.95, NKD 3815.22, SI 3880.47 `usd_per_asset_day`). `lines.earliest` is HG -99.10, NKD -68.80, SI -162.51.
- **Where.** `.audit/threshold-capture-gap.json` `capture`, `dollar_stop`, `lines`.
- **Relevance.** Same-join ceiling exists. The live rule does not take that name.

- **What it says.** "Enter one contract in every joinable cell ... taking each cell's earliest CLEAR candidate." "The forecast decides only this day-level cell set. It is day-level and assetless, so it cannot pick the name and cannot rank assets or phases." Eligible names are `compliance_status == CLEAR`. Pick smallest `decision_ts_ns`, then smallest `candidate_id`.
- **Where.** `.audit/threshold-2022-2024-freeze.md` lines 7-14. Frozen 2026-08-26 before any 2022+ outcome dollar was parsed. Repeated in `.audit/threshold-2022-2024-read.json` `frozen_rule`.
- **Relevance.** The live name is bound as arrival order behind a compliance filter. Cell-best is not the authorized pick.

- **What it says.** A KILL names this sentence. "forecast day-gate plus a skill-free name pick did not clear the rungs; the unmeasured lever is within-cell name selection, which has no instrument (T53/T54)"
- **Where.** Freeze line 32. Receipt `dollar_stop.kill_sentence` in `.audit/threshold-2022-2024-read.json`.
- **Relevance.** The freeze authors wrote that T53/T54 cannot pick a name. Earliest CLEAR is the skill-free stand-in.

- **What it says.** "It does not pick the name. Ticket 53 established that predicting cell value does not locate the picker's failures, and nothing here changes that."
- **Where.** `design/entry_reset/T54_FORWARD_VOL_20260823.md` lines 94-97.
- **Relevance.** The 2022-2024 forecast instrument is allocation, not identity.

### Why earliest CLEAR was the bound instrument

- **What it says.** "The name pick in step 4 is arrival order behind a compliance filter, not a fitted field rule, which is why it is not a roster-field formula." Forbidden formulas include "Ticket 28 hold. Ticket 39 location-ranker. E1R ENTER-weight. Roster fields. Enter-all."
- **Where.** `.audit/threshold-2022-2024-freeze.md` lines 46-48.
- **Relevance.** Earliest CLEAR was chosen so the one authorized read would not smuggle a fitted name rule, a roster field, or E1R ENTER-weight.

- **What it says.** "Why the allocation is day-level and not per-phase: the served TSV is assetless and carries no phase-to-clock mapping, so a per-phase formula would be invented, not measured. The day gate transplants T53's median split ... onto the T54 instrument ... The forecast decides only this day-level cell set."
- **Where.** Freeze lines 13 and 60.
- **Relevance.** The 2022-2024 live path has a day allocator and no name allocator. Earliest CLEAR fills the hole.

### 2021 "earliest" encoding (different universe, same word)

- **What it says.** "Within-side rule. Taken: enter the earliest keep-first name on the called side." Prior. "the best-value series forms early, median formation-rank fraction .16 to .25." "the first-born twin of the winner's bucket holds `runner_up_keep_median = 0.9796` of the winner's dollar." "Unmeasured: the earliest keep-first name on the winning side is not the same object as the winner's first-born twin."
- **Where.** `design/entry_reset/FABLE5_XHIGH_LABEL_DIAGNOSIS.md` lines 117-123. 2026-08-22.
- **Relevance.** Earliest-as-instrument on 2021 was a collapse of a 15-way rank to a 2-way side call plus a fixed within-side rule. The author already marked the identity gap as the kill field.

- **What it says.** Why this fork. "a 2-way call with a fixed rule hides the 15-way ranking behind one binary." Cash is "the earliest keep-first name on the called side." Perfect ranker of the side label cashes `side_first_usd_per_asset_day`.
- **Where.** Same file, section 5, lines 239-257.
- **Relevance.** The instrument is side-then-earliest, not cell-max.

- **What it says.** Ticket 24 TRAIN. Earliest keep-first on the cell-max side cashes $1986 HG / $985 NKD / $1471 SI against $2000 / $1500 / $1500. Letter `side_insufficient` on all three. "The paying name becomes eligible a median 41/42/37 minutes after the first keep-first name." "It is the first-born in 21% / 6% / 12% of cells. Enter-first cashes $489 / $-313 / $-196."
- **Where.** `design/entry_reset/tickets/24-prefix-peer-nonclock.md` lines 37-39. `design/entry_reset/HANDOFF_DECISION_PLANE_20260822.md` lines 21-28 and 39-40.
- **Relevance.** Even oracle side plus earliest misses the rung. First-born is rarely the payer.

- **What it says.** "The name that pays is usually a later zigzag, once the phase's remaining-move extreme has printed. Median wait after the first keep-first name: about 40 minutes. A 180-300 s confirmation score on the first names cannot see a name that does not exist yet." "Ranking the finished cell of 15 is not live. Side-then-earliest is an oracle and still misses the rung."
- **Where.** `design/entry_reset/SELECTION_HOLD_EXTREME_20260822.md` lines 12-22.
- **Relevance.** Direct statement that earliest-in-the-prefix is the wrong identity.

### Why the live 2021 picker (location / price-extreme) is not cell-best

- **What it says.** "The target, stated correctly: land in the TOP TWO of about six." Pool mean is negative. Ranks 0-2 non-negative. Top-2 means HG $678, NKD $498, SI $623 against needs $667 / $500 / $500. Live TRAIN arm $333 / $292 / $488.
- **Where.** `START_HERE.md` lines 93-101. `design/entry_reset/T50_DIAGNOSIS_20260823.md` lines 20-37. `design/entry_reset/tickets/51-loser-screen.md` lines 17-19.
- **Relevance.** The 2021 job is framed as top-2 of events, not cell-max. The live arm sits below that bar.

- **What it says.** Frozen T39 arms. HG $1000 / $857 / $790, NKD $875 / $940 / $807, SI $1465 / $1061 / $868. Every asset letters `loc_insufficient`. About half the rung. Occupancy skips zero. Top-2 hit 65-77% against a 30-34% random baseline (T50 table). Ticket 44 correction. Within a side the score is `side * entry_price`. `prior_high` / `prior_low` pick the same name within a side 100% of the time.
- **Where.** `START_HERE.md` lines 128-140. `design/entry_reset/T39_VERDICT_20260823.md` lines 23-38 and the ticket-44 banner. `design/entry_reset/T44_TAUTOLOGY_AUDIT_20260823.md` (cited by T39).
- **Relevance.** The 2021 live ranker is an entry-price order, not a cell-best identity rule.

- **What it says.** "The hold is not picking the payer." Hold pick is 23-58% of cell-best (T50 table). Ticket 34 armed next-fresh is inside its null on all three assets. "The hold's value is not a timing signal. ... The value lives entirely in the IDENTITY of the held name."
- **Where.** `T50_DIAGNOSIS_20260823.md` lines 101-108. `T29_T34_VERDICT_20260823.md` lines 58-62. `START_HERE.md` closed table, Ticket 28 / Ticket 34 rows.
- **Relevance.** Late identity exists. Transfer to a different name fails. The 180 s label cannot price the wait.

- **What it says.** "The one identity signal this program has confirmed is stranded on the wrong side of a label ceiling." Identity is late. Tickets 25, 26, and 36 left only entry-price arithmetic at age <= 300 s.
- **Where.** `design/entry_reset/ENTRY_PLAN_20260823.md` lines 10-29.
- **Relevance.** The confirmed identity is not available at the live commit clock.

### Why E1R was the attempted instrument

- **What it says.** "The frozen E1R regret head never makes ENTER the strict min on any window it has been walked, TRAIN included. Same-window teacher dollars already clear every rung. Labels mark ENTER optimal on 7.7% of fit rows. The fitted head does not."
- **Where.** `.audit/threshold-path-to-rungs.md` lines 1-4 and 22-30. Dated as the live THRESHOLD path page.
- **Relevance.** E1R is the existing THRESHOLD walk artifact. The page treats never-ENTER as the established bottleneck, not a missing ceiling.

- **What it says.** `named_cause` is `action_regret_head_never_prefers_enter`. Fit capture 0.0 to 0.43% against a 0.9 target. Advantage grid all negative. Best quantile -$43.31.
- **Where.** `.audit/threshold-enter-gap-20260825.json`.
- **Relevance.** The receipt names the cause as the regret head's ENTER preference, not name rank.

- **What it says.** "Code bug (E1R). Regret label + joint head + argmin never ENTER. $0 instead of about $500/asset-day. Real, attributed, not the goal. Do not relitigate it as the live problem."
- **Where.** `design/entry_reset/DIAGNOSIS_20260822.md` lines 35-37. Out of scope, line 257. "Relitigating E1R as the live problem."
- **Relevance.** On 2026-08-22 the design tree closed E1R as a wiring defect that explains $0 versus ~$500, not the $500 versus $2000 gap.

- **What it says.** "The $0 E1R result had a real mechanism (regret label, joint regression head, argmin rule); fixing it lands near $500 per asset-day, not $2,000." "Is the shortfall a code defect? **F**: partly; the E1R mechanism explains $0 vs ~$500, not $500 vs $2,000."
- **Where.** `design/entry_reset/overview.md` lines 36-37 and 111-112.
- **Relevance.** Same closure. E1R was the first learner, not the identity instrument.

- **What it says.** "Regret is a substitution margin of order $11 to $38 measured against an oracle continuation. It is the portfolio-marginal price of one action under a future that the live policy does not have. It is the furthest of all of them from the trade, and it is the one E1R actually optimized." "Dollars die because the label is flat, argmin over a flat label is noise, and that is the shape of the E1R $0." The learner that produced E1R never grouped by cell.
- **Where.** `design/entry_reset/OPUS5_MAX_LABEL_DIAGNOSIS.md` lines 70-79, 104-115, 241-244.
- **Relevance.** E1R optimizes ENTER/DEFER/PASS regret on isolated rows. It is not a cell-best name picker.

- **What it says.** H5 walked ENTERs. `h5_conclusion.majority_top2` false. `top2_hits` 1, `top2_misses` 30, `top2_rate` 0.032. H5 `overall.cell_best` 0/31. H3 `overall.cell_best` 21/142 (0.148), `top2` 44/142 (0.310). H7 `overall.cell_best` 16/139 (0.115), `top2` 30/139 (0.216). Definitions. `cell_best` is highest labeled dollars among live keep-first names at age 180. `top2` is a hindsight measurement label.
- **Where.** `.audit/threshold-h5-top2.json` `definitions`, `h5_conclusion`, `variants.H3.overall`, `variants.H5.overall`, `variants.H7.overall`.
- **Relevance.** When a later E1R-family head does ENTER, those names are still not cell-best. H5 is almost never top-2.

### Why roster was the attempted instrument

- **What it says.** Ticket 51. "the job is not 'pick the best' and not 'drop the losers' — it is **land in the top two**."
- **Where.** `design/entry_reset/tickets/51-loser-screen.md` lines 17-19. Same framing in `T50_DIAGNOSIS_20260823.md` line 29.
- **Relevance.** Roster work is the attempted causal filter for "is this event in the top two."

- **What it says.** Kill bar stated before the scan. A single causal field and threshold must remove more than half of walked event-not-top-2 ENTERs and keep more than half of walked top-2 ENTERs. Fields. `event_order`, `score_depth`, `running_occupancy`, `commit_event_rank`. "Walked identity split already measured in `.audit/threshold-h5-top2.json`. Top-2 about +$600/tr. Event-not-top-2 about -$400/tr."
- **Where.** `.audit/briefs/roster-kill.md` lines 21-48. Receipt `.audit/threshold-roster-kill.json` `kill_bar`, `definitions`, `status` KILL, `survives` false, `rules_scanned` 216, `rules_survived` 0. Chosen rule `event_order > 0`. `keep_top2` 55/75. `remove_event_not_top2` 38/137. Separation AUCs 0.455 to 0.497.
- **Relevance.** Roster was tried as a one-field veto after H5 showed the walk does not land top-2. No field separated.

- **What it says.** 2021 confirmation receipts. Separate rank and action models on the learned roster. Learned top-12 roster. Direct utility reason `LEARNED_ROSTER_CAPTURE_BELOW_MINIMUM`. Oracle sparse-roster ceiling $2,988.93 per portfolio day. "Candidate acceptance, candidate rank, candidate value, lawful value rank, and top-k roster restriction have all been tried." "They do not identify which extreme event caused the cell value." "Top-k candidate or cell capture is conditional on the candidate universe and roster."
- **Where.** `design/entry_reset/55-entry-v2-recovery-plan/confirmation-receipt-audit.md` lines 53-81, 156-184.
- **Relevance.** Roster restriction is an old E1r confirmation instrument. The audit says it never identified the paying event.

- **What it says.** Freeze. "Roster fields" are a forbidden formula on the 2022-2024 read. Arrival-order CLEAR is written as not a roster-field formula.
- **Where.** `.audit/threshold-2022-2024-freeze.md` line 48.
- **Relevance.** After the 2021 roster kills, the authorized era pick was not allowed to reuse those fields.

### Event frame and identity (why cell-best is the hindsight object)

- **What it says.** New-extreme event. A name that sets a new running extreme on its own side at eligibility. "The event set contains the paying name with recall 1.000" on Stage A score legs. Every event entered at 180 s. "This frame keeps the identity and drops the wait."
- **Where.** `design/entry_reset/T35_VERDICT_20260823.md` lines 22-38. Repeated in `START_HERE.md` lines 71-79.
- **Relevance.** Cell-best in the 2021 docs is the best event at 180 s, not the earliest CLEAR on the 2022-2024 G1 table.

- **What it says.** Recovery audit. "Causal event identity" is `UNRESOLVED`. "No tested state has identified the paying event with a held, time-causal rule that clears its null and rung." The START_HERE sentence "the paying name is always an event" is unsupported. Recall 1.000 is Stage A score-leg recovery, not dollar-best identity.
- **Where.** `design/entry_reset/55-entry-v2-recovery-plan/evidence.md` lines 13 and 30.
- **Relevance.** Long-form audit already splits event-set membership from identity.

## Indirect / circumstantial evidence

- **What it is.** T53 two-regime rule loses to plain EXTREME_ALL on every asset and block. Conditioner predicts cell value 1.8-2.1x and does not locate picker failures.
- **Where.** `design/entry_reset/T53_REGIME_SPLIT_20260823.md` lines 26-62. `START_HERE.md` lines 172-189.
- **What it suggests.** Given T54 "does not pick the name" and T53 "does not locate failures," the freeze's "no instrument (T53/T54)" line is the documented reason a skill-free earliest pick was bound. Alternative reading. The freeze needed any causal deterministic pick to make the day-gate falsifiable, and earliest is the cheapest causal order.

- **What it is.** DIAGNOSIS 2026-08-22 anatomy. "winners form early (tercile winner share about 0.30 / 0.20 / 0.07); the extreme is set mid-phase and holds; last-formed is never best."
- **Where.** `design/entry_reset/DIAGNOSIS_20260822.md` lines 47-50.
- **What it suggests.** Given that tercile, earliest looks like a reasonable default. Capture-gap's mean time rank 28 of 105 CLEAR names is a different universe (G1 CLEAR rows, not 2021 keep-first / events). Alternative reading. The 2021 tercile and the 2022-2024 time-rank describe different name sets and should not be averaged.

- **What it is.** T50 retraction. Hit-versus-miss "right in cheap, wrong in rich" sits inside a 40-shuffle null. Survived claim is HG-only payer percentile 0.309 cheap versus 0.502 rich.
- **Where.** `T50_DIAGNOSIS_20260823.md` lines 170-213. `START_HERE.md` lines 159-166.
- **What it suggests.** Given the retraction, a later agent should not use the cheap/rich root-cause paragraph as the reason live entry misses cell-best. The narrower HG percentile claim is still in force in T50.

- **What it is.** Covering judgment after the teacher-cash kill. "Day-gate plus any skill-free name pick" is dead. "Single-field roster rules" are dead. "E1R and every loss-function variant" are dead. H5 cell-best 0/31, top-2 join 1/31.
- **Where.** `.audit/briefs/threshold-covering-after-kill-out.md` lines 7-18. Follow-on, not in the named slice.
- **What it suggests.** Given those three kills, the docs treat earliest CLEAR, E1R, and roster as already-tried instruments on one identity miss. Alternative reading. This page is a later judgment, not contemporaneous design rationale.

- **What it is.** `pick_cell_names` keeps the min `(decision_ts_ns, candidate_id)` per (asset, d8, phase). `pick_cell_best_ready` is the hindsight max-`cert_close_usd` twin. Ceiling selftest refuses collapse onto earliest CLEAR.
- **Where.** `.audit/score_threshold_2022_2024_read.py` lines 222-237. `.audit/score_threshold_2022_2024_ceiling.py` docstring and lines 163, 502-508.
- **What it suggests.** Mechanics only. The scripts encode the freeze. They do not add a why.

## Contradictions

- **E1R closed versus E1R live.** `DIAGNOSIS_20260822.md` line 35-37 and 257. Do not relitigate E1R as the live problem. `.audit/threshold-path-to-rungs.md` still names the frozen E1R head as the established THRESHOLD bottleneck on 2026-08-26. Both are in the slice.

- **Winners early versus payer late.** Fable and DIAGNOSIS. Winners form early, last-formed never best. SELECTION_HOLD and HANDOFF. The paying name is usually a later zigzag, first-born in 6-21% of cells, ~40 minutes after the first keep-first name. Capture-gap. Winner mean time rank 28 of 105 CLEAR names.

- **Picker strength.** T50 superseded section. "The picker is weak." T50 later table. Top-2 hit 65-77%, "a strong picker by every ranking measure," still ~half the rung. H5 walk. Top-2 1/31. These are different objects (location-ranker cell-pick versus refit walk ENTERs). The docs sometimes share the word "picker."

- **Event recall wording.** `START_HERE.md` line 77. "The paying name is always an event: recall 1.000." `55-entry-v2-recovery-plan/evidence.md` line 30. That wording is unsupported. The receipt measures Stage A score-leg recovery.

- **T53 conditioner causal claim.** `START_HERE.md` lines 172-185. Nine of nine, widens out of sample, strongest OOS result. `55-entry-v2-recovery-plan/evidence.md` lines 17 and 38. Clean held causal claim `RETRACTED` because THRESHOLD outcomes select columns and each block standardizes itself.

- **Top-2 arithmetic versus need.** T50 / ticket 51. Top-2 "clears HG and SI and is $2 short on NKD." `evidence.md` line 29. NKD top-two 497.38 is below the $500 need. No uncertainty field on that few-dollar gap.

## Gaps

- `design/entry_reset/` has no hit for `compliance_status`, `earliest CLEAR`, or G1 `CLEAR` as a live pick. The 2022-2024 earliest-CLEAR rule lives in `.audit/threshold-2022-2024-freeze.md` and `START_HERE.md`, not in the 2026-08-22/23 design tree.

- `.audit/threshold-path-to-rungs.md` does not mention cell-best, CLEAR, capture-gap, or roster. It only discusses the frozen E1R head, labels, and teacher dollars.

- No long-form page in this slice states a contemporaneous why for binding earliest rather than latest or cheapest before the capture-gap read. Capture-gap is the first page that measures those three and kills all three.

- No page in this slice states why E1R was reopened as the live THRESHOLD instrument after `DIAGNOSIS_20260822.md` took it out of scope.

- No page states a product reason for preferring roster fields over a fitted name score. The roster kill brief says the H5 identity split was already measured and the next unit is a one-field veto. That is sequencing, not a stated theory of why arrival order should mark top-2.

- T50's 65-77% top-2 table is `UNRESOLVED` as a key-auditable claim in `evidence.md` line 35. Those fields are absent from `entry_economics_20260823.json`.

- Notion, issue tracker, chat, observability, error tracking, and warehouse. No matching MCP. Null for those categories.

- This slice does not contain a commit hash or PR body for the freeze. Source-control investigator owns that.

## Additional leads

- Source control. `.audit/threshold-2022-2024-freeze.md` sha in capture-gap `sources.freeze.sha256`. `pick_cell_names` / `pick_cell_best_ready` history.
- `.audit/threshold-hillclimb.tsv` and `threshold-refit-h*.json` (named by covering-after-kill-out as the E1R variant graveyard).
- `artifacts/entry_v2/tabular_recovery/diagnostics/entry_economics_20260823.json` and `extreme_events_20260823.json` (own the 2021 rank means and event oracle).
- `design/entry_reset/T44_TAUTOLOGY_AUDIT_20260823.md` (location-ranker mechanism).
- Chat or human product call on "refit E1R versus retire E1R" in `threshold-path-to-rungs.md` unit 3. No AskQuestion record in this slice.

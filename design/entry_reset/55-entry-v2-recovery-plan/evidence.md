# Scientific evidence audit

The project has established that the 2021 candidate set contains enough hindsight payoff, that several short-horizon selectors fail under their stated tests, and that forward range is forecastable. It has not established causal event identity, a valid long-hold entry, a clean held regime conditioner, or replay dollars. Several summaries state conclusions beyond the fields that own the evidence.

## Components found

### Verdict map

| Topic | Verdict | Primary evidence | Exact scope |
|---|---|---|---|
| Event-set oracle support | `ESTABLISHED`, with limits | `artifacts/entry_v2/tabular_recovery/diagnostics/extreme_events_20260823.json`, `assets.<asset>.stage2.event_oracle` | A hindsight best-event ceiling on 2021 TRAIN clears the letter rung for HG and SI. NKD remains unresolved. This is not a selector or a replay result. |
| Event recall | `ESTABLISHED`, but narrower than summarized | Same receipt, `assets.<asset>.stage1_recall_of_stage_a_legs`; `tools/probe_extreme_events.py`, `stage1_recall()` | Recall `1.0` means that every per-side Stage A final-score extreme has an event with the same score, up to ties, on TRAIN. It does not mean that the globally highest-dollar name is always an event. |
| Causal event identity | `UNRESOLVED` | The confirmation receipts inventoried below | No tested state has identified the paying event with a held, time-causal rule that clears its null and rung. |
| Short confirmation through 300 seconds | `ESTABLISHED` only as scoped failures | `s6_occupancy`, `extension_causal`, `extension_confirmation`, `patience_rule`, `retest_rule`, `crux_prefix_winner`, `crux_wait_scan`, and trained-accrual receipts | The exact tested encodings, ages, objectives, and controls fail or remain incomplete. The evidence does not close all dynamic observation sequences or off-matrix state. |
| Long holds | `UNRESOLVED`; economic use of the prior result is `RETRACTED` | `hold_running_extreme_20260822.json`, `armed_entry_20260823.json`, `T28_VERDICT_20260822.md`, `T29_T34_VERDICT_20260823.md`, `T50_DIAGNOSIS_20260823.md` | The hold selected an identity after 7,380 or 10,980 seconds but scored it with the 180-second label. The next-fresh-name repair fails its timing null. No honest delayed-price receipt exists. |
| Within-cell location ranker | `ESTABLISHED` as a non-causal association; mechanistic story `RETRACTED` | `location_ranker_20260823.json`; `T39_VERDICT_20260823.md`; `T44_TAUTOLOGY_AUDIT_20260823.md` | The ranker beats its score-shuffle null on the read blocks, but all letters are `loc_insufficient`. Entry-price ordering creates much of the relationship, and the held reads were not pristine at the rule-family level. |
| Two cell-value regimes | Clean held causal claim `RETRACTED`; descriptive split `ESTABLISHED` | `regime_split_20260823.json`; `tools/probe_regime_split.py`; `T53_REGIME_SPLIT_20260823.md` | The reported cheap/rich separation is real in the saved table, but THRESHOLD outcomes select columns and each evaluated block supplies its own standardization. It is not an out-of-sample causal conditioner. |
| Forward range forecasts | `ESTABLISHED`, with a strict boundary | `artifacts/entry_v2/forecast/forward_vol_audit_v4_exact.json` | The publisher forecast beats the persistence baseline in all 12 `ALL_PRE_H2` asset-phase slices. The receipt explicitly says entry labels and economics were not used and launch is not authorized. |
| Replay dollars and drawdown | `UNRESOLVED` | All current diagnostic receipts; absence of a replay receipt under `artifacts/entry_v2/tabular_recovery/` | No chronological, one-position, entry-capped replay demonstrates the dollar rungs or maximum drawdown below $1,000. Exact labels and cell-pick cash summaries are not replay. |

### Audit of the numerical claims in `START_HERE.md`

| Summary claim | Owning field or calculation | Verdict |
|---|---|---|
| TRAIN event-pool means are HG -$95, NKD -$51, SI -$71 | `entry_economics_20260823.json`, `assets.<asset>.train.event_payoff.mean_usd`: HG `-94.8674`, NKD `-50.4517`, SI `-71.1047` | `ESTABLISHED` as a TRAIN event-pool description. It is not a legal enter-all policy. |
| Profitable event fractions are 43%, 44%, and 40% | Same object, `frac_positive`: `0.42677`, `0.43766`, `0.40465` | `ESTABLISHED` on TRAIN only. |
| There are about 6.3 events per cell | Same receipt, `n_events` divided by `n_days * cells_per_day`: HG `396/(21*3)=6.286`, NKD `393/(21*3)=6.238`, SI `215/(11*3)=6.515` | `ESTABLISHED` as an approximate TRAIN average. It is not invariant across blocks. |
| Rank 0 through rank 3 marginal means are HG 924/431/-2/-240, NKD 617/378/127/-50, SI 799/447/235/-49 | Same receipt, `assets.<asset>.train.event_payoff.rank_means_usd` | `ESTABLISHED` as hindsight rank marginals. |
| The top-two means are $678, $498, and $623, and top-three means are $451, $374, and $494 | Arithmetic means of the rank fields above: HG `677.326`, NKD `497.381`, SI `623.066`; top three HG `451.011`, NKD `373.978`, SI `493.818` | `ESTABLISHED` as arithmetic targets only. NKD top two is below its $500 need and SI top three is below its $500 need. No uncertainty field supports treating the few-dollar gaps as decisive. |
| Event recall is 1.000 | `extreme_events_20260823.json`, `assets.<asset>.stage1_recall_of_stage_a_legs = 1.0` | `ESTABLISHED` only for Stage A score-leg recovery up to ties on TRAIN. The broader “the paying name is always an event” wording is unsupported. |
| Every event is entered at 180 seconds | Same receipt, top-level `delta_sec = 180`; source constant `DELTA_SEC = 180` | `ESTABLISHED` for this diagnostic label row. It does not prove that a live event is identifiable at that age or that a replay fill exists. |
| Event oracles are HG $2,772 with SE $238, NKD $1,851 with SE $321, SI $2,396 with SE $329 | Same receipt, `assets.<asset>.stage2.event_oracle.{usd_per_day,usd_se}`: HG `2772.2024/237.4947`, NKD `1851.0714/321.1055`, SI `2396.3636/328.9422` | `ESTABLISHED` as TRAIN hindsight ceilings. Receipt letters are HG `event_clears_rung`, NKD `event_not_resolved`, SI `event_clears_rung`. |
| The location ranker earns HG 1000/857/790, NKD 875/940/807, SI 1465/1061/868 on TRAIN/THRESHOLD/FORWARD | `location_ranker_20260823.json`, `assets.<asset>.blocks.<block>.policy.usd_per_day` | `ESTABLISHED` as diagnostic cell-pick cash. Every saved letter is `loc_insufficient`, and there is no replay or entry-price-control field in this receipt. |
| The location rule beats the shuffled 97.5th percentile in all nine blocks | Same receipt, compare `policy.usd_per_day` with `null.p97_5_usd_per_day`; examples are HG FORWARD `790.357` versus `520.737`, and SI FORWARD `867.955` versus `468.011` | `ESTABLISHED` under that null. The shuffle changes event membership as well as ranking, so it does not isolate information beyond entry-price ordering. |
| Top-two hit rate is 65% to 77%, rank-zero hit rate is 41% to 56%, and occupancy is zero | Reported in `T50_DIAGNOSIS_20260823.md` | `UNRESOLVED` as a key-auditable numerical claim. These fields are absent from `entry_economics_20260823.json`, the receipt named by the summary. An owning machine-readable artifact was not found. |
| The hold found only 23% to 58% of the event-cell best | Values in `hold_running_extreme_20260822.json`, `assets.<asset>.blocks.<block>.selected_y180.mean_usd` and `event_cell_best_y180.mean_usd` | `ISSUE`. The nine saved ratios span about 23% to 64%. SI FORWARD is `443/694 = 63.8%`; SI THRESHOLD is `310/907 = 34.2%`. The summary's upper bound is too low. |
| Hold-name retracement is 37% to 74% | Same receipt, `assets.<asset>.blocks.<block>.retracement_pct.median`: minimum `36.10`, maximum `73.67` | `ESTABLISHED` after rounding, as a descriptive diagnostic. It still uses the 180-second payoff label. |
| Cheap cells are worth 1.83 to 2.00 times baseline on TRAIN and 1.86 to 2.08 times on THRESHOLD | `regime_split_20260823.json`, `assets.<asset>.blocks.<block>.{baseline,cheap}` and their ratio | The arithmetic is `ESTABLISHED`. The out-of-sample and causal interpretation is `RETRACTED` because `conditioner_columns()` uses `y_cell_th` and `conditioner_score()` standardizes each evaluated block separately. |
| Forward range MAE gains are 20.8% to 28.4% in all 12 pre-H2 slices | `forward_vol_audit_v4_exact.json`, `slices` entries with `slice = ALL_PRE_H2`, `range_exact_publisher_target.{baseline_mae,gain}` | `ESTABLISHED` for the range target. The receipt has `entry_labels_or_economics_used = false` and `launch_authorization = false`, so it cannot support entry dollars. |
| The service TSV has 37,427 rows, 12 horizons, two arms, and all gates pass | `artifacts/runs/e6_vol_forecasts_v2/vol_service_forecasts.tsv`: 37,428 lines including the header; columns `head`, `arm`, and `gate_pass` | Row count and schema are `ESTABLISHED`. These are variance forecasts, not dollar outcomes. |

## Flow

The evidence has five distinct layers. The current summaries sometimes merge them.

1. A deterministic generator constructs names and keeps the first visible row for each live-dedup identity.
2. Stage A and the event rule select score extremes. Event-set recall is measured against Stage A score legs, not against the best eventual dollar label.
3. A selector consumes a snapshot or prefix at an observation age. Any feature must exist by that age, and its normalization must be frozen from prior data.
4. The label `y` is read from an exact age row and a fixed close. A later decision requires a new entry-price label.
5. Replay adds chronological fills, one-position occupancy, entry caps, and drawdown. A cell-pick cash average stops at layer 4.

### Inventory of confirmation attempts

`PC` means an explicit entry-price control. “No PC” means the attempt did not separate information from the arithmetic effect of entry price.

| Attempt and source | Observation ages, features, and state shape | Decision target and label horizon | Null, PC, and sample split | Result and exact closure |
|---|---|---|---|---|
| Confirmation accrual v1, `confirmation_accrual_20260822.json` | Ages 0, 30, 60, 120, 180, 300. Four abstract composites `DEFENSE`, `REPLENISH`, `EXHAUST`, `LIFTOFF`, plus `COMBINED`; population z-score by asset and age. | Proxy winner is a series whose eventual standalone best is at least $600; loser is at most $0. AUC at each age. | Within-cell label permutation and day bootstrap. No PC. No train/held split. | Some HG, NKD, and SI composites accrue. This establishes descriptive separation for the proxy label on the same sample. It does not identify the best event or establish a policy. |
| Confirmation accrual v2, `confirmation_accrual_v2_20260822.json` | Same ages and proxy task. `DEFENSE2`, `REPLENISH2`, `PROGRESS2`, and `COMBINED` are assembled after a raw-column scan. | Same eventual series-best proxy. | Same-sample ranking and evaluation, within-cell permutation, day bootstrap. No PC or held split. | HG and SI composites accrue; NKD combined does not establish. Ingredient selection on all days prevents a held causal claim. |
| Raw feature-accrual scan, `feature_accrual_scan_20260822.json` | Ages 0 and 290; 1,764 raw matrix columns; within-cell median imputation. | Same post-outcome winner/loser proxy. | Multiple-comparison ranking device. No PC or held split. | It proposes ingredients. The receipt does not authorize a scientific finding by itself. |
| Trained accrual, `trained_accrual_20260822_{CELLZ_RMSE,CELLZ_RMSE_FIXED,PAIRLOGIT,WINNER_LOGLOSS,YETIRANK}.json` | Ages 0, 30, 60, 120, 180, 240, 290; 1,764 raw columns plus age; CatBoost state over a snapshot row. | `CELLZ` predicts exact cell z-scored `y`; `PAIRLOGIT` compares pairs; `WINNER_LOGLOSS` predicts the proxy winner; `YETIRANK` ranks within cell. Dollars are explicitly cell-pick diagnostics. | Chronological folds E3-E6 and `FROZEN_Q3_E8`; within-cell fit-label shuffle, five seeds where completed. No PC. | PairLogit has `runs_completed = 1` and null fields are null, so it is incomplete. Winner logloss does not separate reliably. YetiRank capture is not stable against shuffle. Fixed CELLZ captures only a limited fraction of the needed dollars. This closes these objectives and hyperparameters on this 2021 plane, not every model family. |
| S6 occupancy, `s6_occupancy_20260822.json` | Ages 0, 30, 60, 120, 180, 240, 290. S6 requires retest seen, not invalidated, at least one rebuild after depletion, and memory-z2 defense reload. | Same-age oracle-pick versus non-pick occupancy. No selector or dollar target. | Within-cell oracle-label shuffle; TRAIN and THRESHOLD gate. No PC. | HG and NKD stay inside the null at all ages; SI shows only under-representation. It closes this S6 encoding through 290 seconds. Truncation is 74% to 85%, so it does not close later waits or a richer second-defense state. |
| Ordered confirmation, ticket 08 | Proposed state sequence after S6. | Proposed sequential selector. | Planned held controls. | It was not run because the S6 occupancy prerequisite failed. There is no ordered-confirmation receipt. `PROPOSED`, then closed only by its prerequisite for that exact route. |
| Causal extension, `extension_causal_20260822.json` | Ages 0, 180, 290; extension threshold and running maximum; first sequential eligible candidate. | Exact `y` at the observation age, normalized by cell series-best. | TRAIN chooses quantile and margin; THRESHOLD and FORWARD evaluate; random null. No PC. | Fails. It closes these extension shapes at these ages, not confirmation in general. |
| Extension plus confirmation, `extension_confirmation_20260822.json` | Ages 60, 120, 180, 240, 290; extension quantiles 0.5 and 0.8 plus v1 or v1/v2 simultaneous-unit composites. | Frame A uses the eventual winner/loser proxy. Frame B enters the first sequential threshold crossing and scores exact same-age `y`. | TRAIN selects the rule; THRESHOLD and FORWARD evaluate; random, first-extended, and permutation nulls. No PC. | Every rule has `clears_both_nulls = false`. This closes the tested threshold/composite rules through 290 seconds. V1/v2 ingredients were selected on all days, so their use is not a clean held test. |
| Patience, `patience_rule_20260822.json` | Ages 60, 120, 180, 240, 290; quantiles 0, 0.5, 0.8; candidate must remain the most extended for P seconds. | First eligible candidate, exact `y` at age P. | TRAIN selects P and quantile; held blocks; random and first-extended nulls. No PC. | Fails. It closes time-only stability through 290 seconds, not evidence-rich waiting. |
| Retest, `retest_rule_20260822.json` | T of 2, 5, 10, 20 minutes; epsilon of 25, 50, 100, 200 basis points; extension quantiles 0.5 and 0.8; entry ages 60 and 180. Tracks a held price extreme and enters the first retesting candidate. | Exact `y` at the candidate's entry age. | TRAIN selects among 64 combinations; held blocks; random, first-candidate, and first-extended controls. No PC. | Fails held. It does not require same-side quote defense, so it cannot close S6 or all retest notions. |
| Prefix winner families, `crux_prefix_winner_20260822.json` | Age 180; Dawes, excursion, aligned, skew, and clock families over a winner-versus-earlier prefix. | The eventual full-cell best-`y` name is labeled winner, then cash enters the first selected name. | Within-cell winner-label shuffle; TRAIN and held blocks. No PC. | HG and NKD are blind; SI's TRAIN AUC about 0.69 does not hold. It closes those families at age 180 only. |
| Prefix raw scan, `crux_wait_scan_20260822.json` | Age 180; all 1,764 raw columns in the same winner-versus-earlier frame. | Eventual best-`y` identity. | TRAIN selects columns; THRESHOLD must survive. No PC. | The clock reaches AUC 1 because the constructed winner is always the latest-born name in that prefix. No non-clock raw column survives. This closes raw single columns in that frame, not composites, side-resolved forms, other ages, or off-matrix state. |
| Wait-prefix ceiling, `wait_prefix_ceiling_20260822.json` | Waits 0, 300, 600, 1,800, 2,400, 3,600, and infinity after the first name. | Hindsight best name born by W, but cash still uses that name's 180-second `y`. | Availability ceiling; no selector null, PC, or honest wait-price label. Blocks are reported separately. | At W=2,400 TRAIN ceilings are HG $2,117, NKD $1,262, SI $1,777; THRESHOLD ceilings are $1,741, $1,246, $1,213, from `assets.<asset>.blocks.<block>.waits.2400`. This establishes name availability, not a confirmation policy. |
| Running-extreme hold, `hold_running_extreme_20260822.json` | H=120 minutes for HG/NKD and 180 minutes for SI. State is the running VWAP-extreme identity. Decision ages are 7,380 and 10,980 seconds. | Scores the selected identity with its 180-second `y`, not a delayed-entry label. | Six held-block reads are recorded in `T28_VERDICT_20260822.md`. No timing null or PC. | The identity is stable enough to inspect but the economic claim is invalid. Label support stopping at 600 seconds does not cover the decision time. |
| Armed next-fresh entry, `armed_entry_20260823.json` | After the long hold, enter the next fresh name at that new name's own 180-second age. | Exact 180-second `y` for the fresh name. | Within-cell timing null; all blocks. No PC beyond using the correct fresh-name row. | All assets and blocks are at or inside the null. It closes this transfer mechanism only. It does not prove that all hold value was identity rather than timing. |
| New-extreme causal arms, `extreme_events_20260823.json` | Event age 180; `FIRST`, `KTH`, `FRACTION`, `LAST_BY`, `MARGIN`, `DAWES`, and `DEPTH`. | Exact event `y` at 180. | TRAIN-only arm gate with registered controls. No explicit entry-price control. | Every arm fails TRAIN. This closes the exact arms on TRAIN, not all event selection. |
| Location ranker, `location_ranker_20260823.json` | Event age 180; rank by signed entry-price location with a TRAIN-selected cross-side offset. | Select one event per cell and score exact 180-second `y`. | Score-shuffle null; TRAIN, THRESHOLD, FORWARD. No PC in the receipt. | Beats the saved null in all nine block-asset cells but remains `loc_insufficient`. `T44_TAUTOLOGY_AUDIT_20260823.md` shows that entry-price arithmetic, not path extension, explains much of the association. |
| Regime conditioner, `regime_split_20260823.json` | First event at 180; a composite of selected prefix-time matrix columns; one score per cell. | Split cells by predicted value, then compare baseline and location-rule dollars. | Claimed TRAIN selection and THRESHOLD evaluation; no PC. Source actually uses TRAIN and THRESHOLD cell outcomes to select columns and each block's own mean and standard deviation. | The saved cheap/rich tables are descriptive. They are not clean held confirmation or causal regime evidence. |
| Delay-forfeit ceiling, `delay_forfeit_20260822.json` | Ages 0, 30, 60, 120, 180, 240, 290. The oracle may switch to any series visible by each age. | Best hindsight `y` available at or after each delay. | Opportunity-cost diagnostic; no selector null or PC. | At 290 seconds the ceiling retains 92.96% for HG, 92.20% for NKD, and 91.71% for SI, from `assets.<asset>.retention_at_290`. This says the opportunity set decays slowly. It does not say a fixed identity or causal rule remains good. |

## Files read

- Governing summaries and contract: `START_HERE.md`; `design/entry_reset/55-entry-v2-recovery-plan/exploration-contract.md`.
- Oracle and event evidence: `tools/probe_extreme_events.py`; `artifacts/entry_v2/tabular_recovery/diagnostics/extreme_events_20260823.json`; `entry_economics_20260823.json`.
- Short confirmation receipts: `confirmation_accrual_20260822.json`; `confirmation_accrual_v2_20260822.json`; `feature_accrual_scan_20260822.json`; all five `trained_accrual_20260822_*.json` receipts; `s6_occupancy_20260822.json`; `extension_causal_20260822.json`; `extension_confirmation_20260822.json`; `patience_rule_20260822.json`; `retest_rule_20260822.json`; `crux_prefix_winner_20260822.json`; `crux_wait_scan_20260822.json`; `wait_prefix_ceiling_20260822.json`; `delay_forfeit_20260822.json`.
- Hold and event-location evidence: `hold_running_extreme_20260822.json`; `armed_entry_20260823.json`; `location_ranker_20260823.json`; `regime_split_20260823.json`; `tools/probe_regime_split.py`.
- Verdicts and audits: `design/entry_reset/T28_VERDICT_20260822.md`; `T29_T34_VERDICT_20260823.md`; `T35_VERDICT_20260823.md`; `T39_VERDICT_20260823.md`; `T43_RESOLUTION_20260823.md`; `T44_TAUTOLOGY_AUDIT_20260823.md`; `T50_DIAGNOSIS_20260823.md`; `T52_REGIME_20260823.md`; `T53_REGIME_SPLIT_20260823.md`; `T54_FORWARD_VOL_20260823.md`.
- Forecast evidence: `artifacts/entry_v2/forecast/forward_vol_audit_v4_exact.json`; `artifacts/runs/e6_vol_forecasts_v2/vol_service_forecasts.tsv`; `artifacts/entry_v2/tabular_recovery/diagnostics/fvol_oracle_join_20260822.json`; `tools/probe_fvol_oracle_join.py`.

## Boundaries

### `ESTABLISHED`

- The 2021 TRAIN event subset contains high hindsight payoff. HG and SI event oracles clear their letter rungs by the receipt's two-SE rule; NKD does not.
- The location score has a reproducible association with exact 180-second payoff and exceeds its registered score-shuffle null on all nine read cells. This is an association, not independent identity information.
- The tested short-confirmation rules fail in their named state shapes, ages, objectives, and controls. These scoped negative results are useful.
- Forward range forecasts improve on persistence across the 12 saved pre-H2 slices. This evidence ends at range forecast skill.

### `RETRACTED`

- “Location extension” as the within-cell mechanism. `T44_TAUTOLOGY_AUDIT_20260823.md` traces the score to signed entry price plus a cross-side offset. The exact match and correlation counts in that Markdown file lack an owning JSON field, but the formula is source-backed.
- “Cheap versus rich is a held causal cell regime.” THRESHOLD labels take part in column selection, and evaluated-block standardization reads the full block.
- Any economic interpretation of the original long-hold cash number. The decision occurs hours after the price used by its label.
- The uncontrolled “right cheap, wrong rich” picker diagnosis. Only a narrower HG payer-percentile result survived the later audit, and its quoted hit-rate fields are not present in the named receipt.

### `UNRESOLVED`

- Whether a causal state sequence identifies the paying event or lands in the top two within a cell.
- Whether the event generator preserves the globally best-dollar name on clean held samples. Stage A leg recall does not answer this.
- Whether a long hold has positive economics at its actual entry price.
- Whether a time-consistent, TRAIN-frozen cell conditioner predicts value out of sample.
- Whether forward range skill localizes value to a cell and then to an event.
- Whether any final policy meets the three asset dollar rungs, 12-entry cap, one-position constraint, and maximum drawdown below $1,000 in exact chronological replay.

### `PROPOSED`

- Build the 2022 through 2024 causal corpus with prefix-time features, frozen transforms, and exact decision-age labels.
- Join forward range forecasts to realized range, cell-best value, and event capture without using outcome information in feature selection.
- Freeze one policy, run its chronological replay, and report entries, occupancy, fills, daily dollars, uncertainty, and drawdown from one owning receipt.

## Non-obvious things

- The recall denominator is Stage A score legs. A generator can have recall `1.0` on that denominator while missing the global best-dollar event. The event-oracle values are slightly below the broader cell maxima reported elsewhere, which is consistent with this distinction.
- The “top two” threshold is not the result of a selector. It is the mean of two hindsight rank marginals. It says how hard the identity problem is, not that the current system solves it.
- Several confirmation studies use an eventual series-best threshold as their label. That proxy can reveal general winner-like behavior while failing to identify the best event within a cell.
- The prefix-winner clock AUC of 1 is constructed by the evaluation frame. The evaluated winner is the latest-born name in that prefix, so the result is not causal signal.
- The wait-prefix oracle may switch identities and still prices the chosen identity at 180 seconds. It is an availability ceiling, not evidence for waiting.
- `location_ranker_20260823.json` says its final rule was frozen before its held read, but `T39_VERDICT_20260823.md` records an earlier defective freeze and held read in the same family. The final receipt is reproducible; the blocks are not pristine discovery holdouts.
- The regime code's features may be prefix-time at the row level, yet the composite is still non-causal because target outcomes select its columns and the full evaluated block supplies its normalization. Feature timestamp safety does not repair selection leakage.
- The conditioner sorts cell value. Payer percentile does not consistently improve in its predicted-rich half, so cell-value separation should not be described as event-identity confirmation.
- The phrase “model family closed” is too broad. PairLogit is incomplete, and the completed negative results cover named CatBoost objectives, hyperparameters, folds, and the 2021 feature plane.
- No diagnostic dollar field supplies portfolio drawdown. `usd_per_day`, exact `y`, and exact entry-age labels are necessary inputs, but none is an exact replay result.

## Open questions

- What machine-readable receipt owns the quoted location top-two hit, rank-zero hit, and occupancy figures?
- Does a clean TRAIN-frozen event-recall audit against global best `y`, rather than Stage A score legs, retain full recall on each unopened block?
- Can a prefix-time state be normalized from TRAIN alone, select features without THRESHOLD labels, and predict cell value on a single held read?
- Which exact decision-age price and close define a long-hold label at 7,380 and 10,980 seconds?
- Does forecasted range add value after a persistence baseline when the target is cell-best dollars and then event capture, with an entry-price control at each link?
- What final policy will be frozen before the next held read, and what single receipt will own its chronological replay and drawdown?

`ISSUES`: The primary artifacts support oracle capacity and scoped negative confirmation results, but they do not support the broad claims that the paying name is always an event, that the two-regime split is held causal evidence, that the long hold found the payer economically, or that replay dollars have been achieved.

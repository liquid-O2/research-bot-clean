# Entry V2 synthesis

## Root shortfall

Entry V2 lacks a time-causal event-localization policy that commits while the selected event still supports the dollar target. This is the single root shortfall.

The generator is not the current repair target. G1 already emits a causally valid candidate from a strict receive-time prefix. `generate_g1_candidates` owns formation in `engine/cpp/qr_entry_v2/src/g1.cpp:859-1169`. `CandidateRow` keeps the strict cutoff, the later native decision clock, the entry BBO, and lineage in `engine/cpp/qr_entry_v2/include/qr_entry_v2/g1.hpp:164-229`. Outcome fields stay in `certify_teacher` at `engine/cpp/qr_entry_v2/src/g1.cpp:1200-1364`.

The existing evidence does not convert those candidates into a legal policy. The 2021 event oracle shows a hindsight ceiling for HG and SI, but NKD remains unresolved under the saved two-standard-error verdict. The receipt owner is `artifacts/entry_v2/tabular_recovery/diagnostics/extreme_events_20260823.json` at `assets.<asset>.stage2.event_oracle`. Event recall of `1.0` covers Stage A score legs through `stage1_recall()` in `tools/probe_extreme_events.py`. It does not prove that the event set always contains the global best-dollar name.

Static feature scans, named confirmation rules, cell-value conditioning, and forward-range prediction do not supply the missing event identity. Waiting alone does not fix the problem either. A later observation can add information while its new entry price removes the payoff. Every candidate policy must therefore measure localization gain and payoff decay at the same commit clock.

## Exact live execution seam

`replay_policy_day` in `engine/entry_v2/tabular_live_replay.py:296-568` is the narrowest live comparison seam. It consumes a fixed `DayOptionUniverse` and a chronological sequence of `CausalFeatureShard` rows. It builds `PortfolioDecisionState`, applies ENTER, DEFER, or PASS decisions, resolves simultaneous proposals, and records exact commit arrivals in `PolicyDayTrace`.

`replay_policy_block` in `engine/entry_v2/tabular_live_replay.py:569-613` passes those arrivals to canonical `replay` in `engine/entry_v2/replay.py:290-453`. `replay` owns exact ordering, one-position occupancy, the shared 12-entry cap, zero-entry days, trade-path dollars, and drawdown. A diagnostic call to `_best_by_score_per_cell` or `_cell_pick` cannot replace this path. `_best_by_score_per_cell` states its hindsight limitation in `tools/probe_extreme_events.py:207-216`.

The causal observation boundary already exists. `materialize_confirmation_session` in `engine/entry_v2/confirmation.py:1655-1958` cuts each snapshot with `searchsorted(..., side="left")`. `_SessionPlane.feature_map` in `engine/entry_v2/confirmation.py:1200-1385` builds prefix-only features. `CausalFeatureShard` in `engine/entry_v2/tabular_delayed_corpus.py:271-416` rejects outcome-shaped names. `DelayedOutcomeShard` in the same file at `:71-268` remains the privileged label plane.

Four clocks must remain separate in every policy receipt.

- Zigzag confirmation records when G1 recognizes the reversal.
- Native decision time records when the candidate becomes tradable after the fixed 15-second or 120-second delay.
- Observation time records the strict prefix available to the policy.
- Commit time owns the entry BBO, outcome row, occupancy interval, and replay order.

The smallest useful code change, if the existing walk cannot host the experiments directly, is an injected decision interface over `PortfolioDecisionState`. That interface is proposed. It does not exist today. It should let formation-time, fixed-age, frontier, and pivot-tape policies share one observation sequence and one replay law.

## Scoped closures

These results close only the named state, age, objective, and control.

| Scope | State | Exact closure |
| --- | --- | --- |
| Existing 1,764-column plane | `ESTABLISHED` negative result | The raw scan and the completed CatBoost objectives did not produce a stable causal selector on the tested 2021 folds. PairLogit completed only one run, so the broad claim that every model family is closed is false. Owners include `feature_accrual_scan_20260822.json` and `trained_accrual_20260822_*.json`. |
| S6 and short confirmation | `ESTABLISHED` negative result | S6, extension, extension plus confirmation, patience, retest, prefix-winner, and event-arm rules fail under their saved tests through their tested ages, mostly 290 or 300 seconds. They do not close every dynamic sequence or information source. Owners include `s6_occupancy_20260822.json`, `extension_confirmation_20260822.json`, `patience_rule_20260822.json`, `retest_rule_20260822.json`, and `extreme_events_20260823.json`. |
| Location ranker | `ESTABLISHED` association, insufficient policy | `probe_location_ranker.run` in `tools/probe_location_ranker.py:154-329` produces diagnostic cell picks at age 180. Every saved letter is `loc_insufficient`. The ranker has no entry-price control and does not call canonical replay. The signed-entry-price explanation is source-backed by `design/entry_reset/T44_TAUTOLOGY_AUDIT_20260823.md`; its quoted exact-match counts lack a machine-readable owner. |
| Long hold | `RETRACTED` economics, `UNRESOLVED` honest delayed entry | The 7,380-second and 10,980-second decisions used the selected identity's age-180 label. No receipt prices the actual delayed commit. The next-fresh-name repair fails its timing null in `armed_entry_20260823.json`. |
| Cell regimes | `RETRACTED` held causal claim | `conditioner_columns()` in `tools/probe_regime_split.py` uses outcome information from TRAIN and THRESHOLD, and `conditioner_score()` standardizes each evaluated block from itself. The saved cheap and rich split is descriptive only. |
| Forward volatility | `ESTABLISHED` range skill, `UNRESOLVED` entry value | `artifacts/entry_v2/forecast/forward_vol_audit_v4_exact.json` shows better range forecasts in 12 pre-H2 slices. Its receipt says that entry labels and economics were unused and launch was not authorized. Forward volatility cannot rank event identity on this evidence. |
| Replay target | `UNRESOLVED` | No policy replay receipt proves the three dollar rungs, the 12-entry cap, one position per asset, and maximum drawdown below $1,000. Diagnostic `usd_per_day` fields stop before canonical replay. |

The following broad claims must not enter the plan as facts.

- The current price rule's 65% to 77% top-two hit rate, 41% to 56% rank-zero hit rate, and zero occupancy lack an owning machine-readable field. `design/entry_reset/T50_DIAGNOSIS_20260823.md` reports them, but `entry_economics_20260823.json` does not.
- The paying name is always an event. The available recall denominator is Stage A score legs, not global best dollars.
- The candidate set has proved enough payoff for every asset. The saved event-oracle verdict leaves NKD unresolved.
- The cell conditioner predicts a causal twofold regime out of sample. The source reads held outcomes during feature selection and normalization.
- The hold found only 23% to 58% of cell-best value. The saved ratios extend to about 64% for SI FORWARD. The reported 37% to 74% figure is retracement percentage, not a dollar entry-price penalty.

## Distinct open mechanisms

### Event frontier and delayed commitment

This mechanism changes the state shape. It represents the ordered set of causally known events, including identity, side, eligibility time, same-side overtakes, opposite-side contradictions, survival, and price displacement. The policy emits WAIT, COMMIT, or SKIP. It can be killed on 2021 with rows already available through 300 seconds. Its null must preserve lifecycle clocks, event counts, side counts, and entry-price order while permuting identity. Its control uses side, entry price, and event count with the same action capacity.

This mechanism is open because prior scans treated rows independently or collapsed the sequence to one running extreme. No prior receipt tests the changing event set as the policy state.

### Pivot-centered G1 birth tape

This mechanism adds information missing from `CandidateRow`. It preserves `pivot_mid2`, the leg start, the pivot clock, signed leg size, reversal retracement, and tape behavior at the exact swing pivot. Generic summaries in `_event_micro_map` and `_state_series` in `engine/entry_v2/discretionary_features.py` do not preserve that G1-specific birth record.

This mechanism must keep G1 candidate generation frozen. A narrow tag with source ordinals and a strict-prefix hash is enough. A one-session future-mutation differential must prove that post-cutoff events cannot change the tag. A 2021 kill slice must beat a pivot-record shuffle and an entry-price twin before the fields enter the 2022 through 2024 corpus.

### Forward volatility as a conditional evidence budget

Forward volatility may choose how long a surviving localizer observes. It may not choose an event. The test target is the marginal localization value of the next interval minus exact entry-price decay. Compare the forecast-conditioned budget with the same localizer at a fixed age. Run this mechanism only after the event frontier or pivot tape survives.

### Event-aligned cross-market residual

This is a parked information source. It would compare the target event with strictly time-aligned peer futures paths after removing their common move. It differs from the closed coarse cross-asset timing tests. Its cost and clock-join risk place it behind the first two mechanisms. A small 2021 overlap receipt must prove coverage before any feature build.

## Safest phase order

1. Freeze the benchmark contract. Define `CandidateLifecycle`, `EventFrontierObservation`, `CommitDecision`, and `OutcomeRead` as separate records. Freeze formation-time and fixed-age controls, per-trade bars, nulls, price twins, two-standard-error verdicts, read counts, and the final replay receipt.
2. Prove the live seam with a red baseline. Use `replay_policy_day` and `replay_policy_block` with one fixed observation sequence. Record the current shortfall, exact commit clocks, dollars, occupancy refusals, entry count, and drawdown. `WalkTwinContractTest` in `engine/entry_v2/test_tabular_walk_twin.py:207-278` is the nearest parity precedent.
3. Price the exact age frontier on 2021. At every supported age through 300 seconds, measure the causally known top-two ceiling and direct entry-price decay. Stop an age when its ceiling cannot clear the per-trade bar by two standard errors.
4. Run the event-frontier kill test on 2021. Compare fixed elimination rules with the lifecycle shuffle and the count-matched entry-price twin. Do not build a new corpus if the state fails.
5. Add the narrow pivot tag only if a second information source is still justified. Run the nanosecond granularity check, the one-session future-mutation differential, and the 2021 pivot kill slice before adding corpus fields.
6. Pilot one complete session. Prove candidate identity, observation rows, optional pivot evidence, forecast lineage, delayed outcomes, exact teacher, and canonical replay join without silent absence. Keep privileged outcomes separate from policy inputs.
7. Extend observation ages only where a preregistered mechanism can still offset price decay. Source accepts only 300-second or 600-second maximum delays today through `ConfirmationConfig`, `training_offsets_seconds`, `replay_offsets_seconds`, and `DelayedOutcomeShard.validate`. Longer ages are a new contract, not existing data.
8. Freeze the 2022 through 2024 protocol before its first outcome read. Freeze each rule, age, null, price control, seed, transform, and read count. Keep 2021 kill-only and 2025H2 sealed.
9. Build separate immutable outcome, observation, and optional pivot shards. Merge receipts, not mutable worker state. Require restart and retry to produce the same hashes.
10. Read each frozen localizer once on the 2022 through 2024 blocks. Run the forward-volatility evidence-budget interaction only for a surviving localizer. Park cross-market residual work unless both primary mechanisms fail and the overlap receipt passes.
11. End on canonical chronological replay. Require more than $2,000 per HG asset-day and more than $1,500 per NKD and SI asset-day, no more than 12 entries per portfolio-day, one position per asset, and maximum drawdown below $1,000. Report the full receipt rather than a cell-pick cash summary.

This order follows the cheapest decisive tests first. It avoids building a late-age corpus around the retracted hold story. It also keeps candidate identity, observation time, commit time, and outcome access in one set of records rather than duplicating them per mechanism.

## Status

ISSUES

Evidence supports the live replay seam, scoped negative results, and two distinct experiments. Missing machine-readable owners and retracted causal claims prevent the broader frontier summary from counting as established evidence.

ISSUES

# Confirmation receipt addendum

## Live cursor

The first live `NEXT_ACTION` in `/workspace/STATE.md` is still the causal 2022 through 2024 corpus and forecast-to-entry join. It asks for the chain from the saved forward-vol forecast to realized range, cell best, and exact event capture. None of the receipts below uses that corpus. They are 2021 E1r confirmation work, and none opens a 2022, 2023, or 2024 calendar-year holdout. The newer receipts therefore narrow several proposed mechanisms, but they do not discharge the live action.

## Evidence boundary

Three evidence levels recur in these files and must not be merged.

| Level | What the receipt actually permits |
|---|---|
| Diagnostic mechanism or model ceiling | Association, rank capture, an oracle decomposition, or economics selected on PLATT. It can reject a representation or show that a representation is worth another held test. It is not an entry policy. |
| Deployable causal policy | A frozen rule chosen without reading its evaluation role, using only information available at the decision clock and the price available at that clock. No reviewed receipt in this addendum reaches this level. |
| Canonical replay | The frozen policy is replayed on the complete chronological opportunity stream with the production cost, capacity, overlap, and entry-price rules. Several runners call the schedule evaluator on a sparse candidate grid. Their own `exact_replay_ceiling_executed` fields are false, so those runs are not canonical replay. |

The common sample is 2021 E1r. The v9 receipts expose FIT and PLATT work, with `threshold_open_count`, `forward_open_count`, and `h2_open_count` equal to zero where those counters are present. Older probe receipts also report 2021 THRESHOLD diagnostics. A repeated role read is not a new calendar holdout.

## Runner and receipt inventory

### Lawful fixed-horizon value

`/workspace/tools/run_confirmation_lawful_value_rank.py` owns `/workspace/artifacts/entry_v2/confirmation/v9_qrf4/e1r_lawful_value_rank_v1.json` and consumes `/workspace/artifacts/entry_v2/confirmation/v9_qrf4/e1r_lawful_value_mechanism_v1.json`.

- Clock and state: observe at `config.watch_age_sec = 30`, then value entry at `config.horizon_sec = 120`. The feature set is the receipt's lawful dynamic state, not a full path tensor.
- Target: `BEST_NONNEGATIVE_Q_ENTER_AT_FULLY_OBSERVED_FIXED_HORIZON_LOCAL_OPTIMUM`, in USD, from the mechanism receipt's target declaration. The construction reprices at the fixed-horizon entry row, so it does control delayed entry price for this target.
- Split: three chronological FIT blocks in the mechanism receipt, followed by PLATT. No THRESHOLD, forward, or H2 economics is opened.
- Result: the mechanism selects 51 stable features. Its PLATT overall group Spearman is `0.0741`, positive-group fraction is `0.7368`, and top-12 lawful-value capture is `0.2326` under `selected_feature_names`, `platt_metrics.overall_group_spearman`, `platt_metrics.positive_group_fraction`, and `platt_metrics.topk_capture`. The rank receipt improves FIT out-of-fold Spearman from `-0.0439` for the control to `0.0688` for the real model, and PLATT Spearman is `0.1133`; PLATT top-12 capture is `0.2782` versus control `0.1130`, under its real and control scorecards.
- Exact closure: lawful state has cross-sectional value-ranking support at this one clock and horizon in 2021. The receipt performs no policy economics and no held-year replay. It does not establish that the top-ranked row is the right event or the right time to enter.
- Causal caveat: names such as formation fraction, elapsed-clock state, and phase actual range appear in the selected feature set. The artifact labels them lawful, but this addendum did not prove their timestamp semantics from raw snapshots. They require a field-by-field availability audit before policy use.

### Lawful policy ceiling

`/workspace/tools/run_confirmation_lawful_policy.py` owns `/workspace/artifacts/entry_v2/confirmation/v9_qrf4/e1r_lawful_policy_ceiling_v1.json`.

- Clock and target: the same 30-second watch and 120-second fixed-horizon delayed `Q_ENTER` target, followed by top-k and stop-threshold searches. The price basis is the fixed-horizon row.
- Split: FIT models and PLATT selection. The artifact explicitly records `selection_scope = PLATT_MODEL_CEILING_NOT_DEPLOYABLE` and does not open THRESHOLD, forward, or H2.
- Result: learned economics is evaluated only as a PLATT ceiling. The runner emits `selection_is_deployable = false`.
- Exact closure: a PLATT-selected combination of lawful value rank and fixed-horizon stop state is not deployable evidence. It does not close delayed commitment in general, and it supplies no canonical replay.

### Path-state ceiling and FIT OOF objectives

`/workspace/tools/run_confirmation_path_state_ceiling.py` owns the versioned receipts ending in `/workspace/artifacts/entry_v2/confirmation/v9_qrf4/e1r_path_state_ceiling_v5_ordinal.json`. `/workspace/tools/run_confirmation_path_state_fit_oof.py` owns `/workspace/artifacts/entry_v2/confirmation/v9_qrf4/e1r_path_state_fit_oof_objectives_v1.json`.

- Clock and state: a raw causal path state at a 30-second landmark, with no asset-day centering, and a 120-second decision horizon. The ceiling target is `SIGNED_BEST_FULLY_OBSERVED_DELAYED_ENTRY_VALUE`.
- Price control: the target is delayed `Q_ENTER` at the horizon, so the target reprices the decision. It is not a formation-value broadcast.
- Split: the ceiling is PLATT-only model selection. The OOF receipt compares `SIGNED_ORDER`, `ORDINAL_POSITIVE_TOP3`, and `QUERY_SOFTMAX_POSITIVE_UTILITY` over chronological FIT folds.
- Result: `ORDINAL_POSITIVE_TOP3` is selected, but `selected_ready_for_platt = false`. The objective receipt records `stable_oof_gate_pass = false` for the tested arms. The ceiling receipt itself says `selection_scope = PLATT_MODEL_CEILING_NOT_DEPLOYABLE`; `deployable_thresholds_executed = false`.
- Exact closure: these particular raw path-state objectives, landmark, horizon, feature policy, and 2021 FIT folds do not earn progression. This rejects the tested representation. It does not show that all causal path state is useless, and PLATT ceiling economics cannot override the failed FIT OOF gate.

### Factorized learned rank and action policy

`/workspace/tools/run_confirmation_factorized_policy.py` owns `/workspace/artifacts/entry_v2/confirmation/v9_qrf4/e1r_factorized_policy_v1.json`.

- Clock and state: sparse causal rows through `config.max_delay_sec = 300`; separate rank and action models operate on the learned roster.
- Target and price control: the action side uses row-local delayed entry utility, so the label can reflect the price at the candidate row. The candidate schedule remains sparse.
- Split: 2021 E1r FIT modelling and PLATT policy selection. `economics_scope = E1R_SPARSE_TRAINING_GRID_DIAGNOSTIC`; forward and H2 counts are zero.
- Result: the learned-rank and learned-timing branch ends with `NO_FEASIBLE_THRESHOLD`. The artifact records `exact_replay_ceiling_executed = false`.
- Exact closure: factorizing roster rank from timing on this sparse grid did not yield a feasible frozen threshold. It does not close a policy trained on complete event chronology.

### Dynamic hurdle

`/workspace/tools/run_confirmation_dynamic_hurdle.py` owns `/workspace/artifacts/entry_v2/confirmation/v9_qrf4/e1r_dynamic_hurdle_top12_v1.json`.

- Clock and state: sparse observations from the 30-second watch through 300 seconds. The timing target is `ENTER_POSITIVE_R50`; the value target is `ENTER_P600_R100`.
- Price control: both are row-local delayed-entry labels. They are proxy decisions around future utility, not direct canonical portfolio reward.
- Split: 2021 FIT models, PLATT diagnostic thresholding, no unopened-role economics.
- Result: the learned-rank plus learned-timing fixed PLATT policy earns `$233.75` per portfolio day and `$116.875` per trade, with maximum drawdown `$1,666.25` and 14 trades, under `platt_fixed_policy.learned_rank_learned_timing`. It is not feasible, and `frozen_policy.selection = NO_FEASIBLE_THRESHOLD`. The oracle-rank plus oracle-timing branch reaches `$3,766.96` per portfolio day under the PLATT decomposition, which is an oracle capacity diagnostic.
- Exact closure: the tested two-head proxy-label policy fails. The oracle result establishes available hindsight value in this selected 2021 roster, not causal identifiability or a deployable stopping rule.

### Direct utility

`/workspace/tools/run_confirmation_direct_utility.py` owns `/workspace/artifacts/entry_v2/confirmation/v9_qrf4/e1r_direct_utility_v1.json`.

- Clock and state: sparse rows from 30 through 300 seconds on the learned top-12 roster.
- Target and price control: direct row-local `Q_ENTER_USD` and `ENTER_ADVANTAGE_USD`; both reprice at the observed row.
- Split: 2021 FIT model and PLATT threshold search. `economics_scope = E1R_PLATT_SPARSE_TRAINING_GRID_DIAGNOSTIC`; no held-year evaluation.
- Result: the learned PLATT fixed policy reports `-$27.86` per portfolio day, `-$5.74` per trade, maximum drawdown `$2,200`, and capture `-0.0093` under its learned fixed-policy scorecard. The receipt closes with `NO_FEASIBLE_THRESHOLD`, `NO_PROGRESSION`, and reason `LEARNED_ROSTER_CAPTURE_BELOW_MINIMUM`. Its oracle sparse-roster ceiling is `$2,988.93` per portfolio day.
- Exact closure: direct utility on this roster and sparse state does not rescue delayed commitment. Although the receipt has `canonical_replay_executed = true`, that key means the canonical schedule evaluator ran on the sparse PLATT grid. The controlling scope field and `exact_replay_ceiling_executed = false` prevent calling it canonical exact replay.

### Fixed-horizon mechanism

`/workspace/tools/run_confirmation_fixed_horizon.py` owns `/workspace/artifacts/entry_v2/confirmation/v9_qrf4/e1r_fixed_horizon_mechanism_v2.json`.

- Clock and target: fully observed fixed-horizon delayed `Q_ENTER`, with price taken at the fixed-horizon row. The artifact evaluates the registered horizon set, including the 120-second horizon consumed by the lawful policy runner.
- Split and result: 2021 mechanism work only. `mechanism_gate_pass = true`, while `models_executed = false` and `learned_economics_executed = false`; only `oracle_mechanism_economics_executed = true`.
- Exact closure: a delayed fixed-horizon oracle mechanism exists in E1r. No learned acceptance rule, timing rule, deployable threshold, or held replay follows from this receipt.

### Acceptance mechanism

`/workspace/tools/run_confirmation_acceptance_mechanism.py` owns `/workspace/artifacts/entry_v2/confirmation/v9_qrf4/e1r_acceptance_mechanism_v3.json`.

- Clock and state: fixed-watch candidate acceptance using within-asset-day centered causal features.
- Target: `CANDIDATE_LOCAL_Q_OPTIMAL_USD_AT_FIXED_WATCH`. This is candidate-local opportunity at the fixed watch, not event-frontier identity and not a stopping action.
- Split and result: 2021 mechanism roles. `mechanism_gate_pass = true`; 32 features survive its stability screen. PLATT top-12 candidate-local potential capture is `0.2879`, and the selected set contains `0.05769` of all candidate-local potential, under its PLATT acceptance scorecard.
- Exact closure: cross-sectional fixed-watch acceptance is not null in the old candidate universe. The small share of total potential and lack of economics prevent interpreting it as an event-elimination policy.

### Action probes

`/workspace/tools/run_confirmation_action_probes.py` owns `/workspace/artifacts/entry_v2/confirmation/v9_qrf4/e1r_action_probes_v2.json`; `/workspace/artifacts/entry_v2/confirmation/action_probes_v1.json` is the earlier broad receipt.

- Clock and state: sparse rows from 0 through 300 seconds. Feature arms range from formation-only to reclaim, episode, and 300-second-window state.
- Targets: `EXACT_ENTER`, `ENTER_POSITIVE_R50`, `ENTER_P600_R100`, and `WAIT_P600`. Exact-enter uses row-local `Q_ENTER`; the other labels are utility proxies.
- Split and result: 2021 FIT, PLATT, and THRESHOLD diagnostics, without economics. In v1, formation-only `EXACT_ENTER` within-series AUC is `0.5`. Adding reclaim state raises THRESHOLD within-series AUC to `0.819` and global AUC to `0.7497` under the `PLUS_RECLAIM` exact-enter scorecard.
- Exact closure: causal-looking path features classify row action labels better than formation state in this corpus. The `hindsight_argmax` timing diagnostics inspect the entire realized series, so they are not a causal stop rule. AUC alone does not identify when a live policy should enter.

### Ordered value probes

`/workspace/tools/run_confirmation_ordered_value_probes.py` owns `/workspace/artifacts/entry_v2/confirmation/ordered_value_probes_v1.json`.

- Clock and state: sparse paths through 300 seconds. It compares `MAX_W300`, `MAX_PLUS_EPISODE`, and `MAX_PLUS_ORDERED` with an order-destroyed twin.
- Target and price control: row-local delayed value is repriced, but the selected timing is a hindsight argmax. No economics is run.
- Result: on THRESHOLD, the ordered `MAX_PLUS_ORDERED` arm has within-series pairwise accuracy `0.8989` and correlation `0.8076`. Its order-destroyed twin has accuracy `0.9189` and correlation `0.8316`, under the ordered and order-destroyed scorecards.
- Exact closure: these results do not establish event order as the source of the predictive signal. Destruction of order performs at least as well on the reported measures. Any summary that treats this as evidence for event identity or ordered causal state is too broad.

### Snell-style probe

`/workspace/tools/run_confirmation_snell_probe.py` owns `/workspace/artifacts/entry_v2/confirmation/snell_factorized_probe_v2.json`; `/workspace/artifacts/entry_v2/confirmation/snell_probe_v1.json` is the earlier receipt.

- Clock and state: sparse ordered observations from 0 through 300 seconds, `MAX_PLUS_EPISODE` features, and three fitted continuation iterations.
- Target and price control: row-local exact `Q_ENTER`, so each action is valued from its available row price.
- Split and result: 2021 role diagnostics, no schedule economics. The selected method is `HURDLE_MEAN`. THRESHOLD candidate-local capture is `0.00808` at iteration 0, approximately `0.0000038` at iteration 1, and `0.00628` at iteration 2 under `iterations[*].threshold`. PLATT iteration-2 capture is `0.0935`.
- Exact closure: Snell-style fitted stopping has already been attempted. This three-iteration CatBoost implementation collapses on THRESHOLD and never becomes a portfolio policy. The result does not reject all optimal-stopping formulations, longer paths, or a different state representation.

### Candidate rank

`/workspace/tools/run_confirmation_candidate_rank.py` owns `/workspace/artifacts/entry_v2/confirmation/candidate_rank_formation_portfolio_no_phase_v2.json`; `/workspace/artifacts/entry_v2/confirmation/candidate_rank_probe_v1.json` is the earlier multi-age receipt.

- Clock and state: the earlier probe observes ages 0, 30, 60, 120, 180, and 240 seconds. The later receipt uses formation age and removes phase features.
- Target: the later receipt uses `FORMATION_Q_OPTIMAL_BROADCAST`. It ranks formation opportunity, rather than repricing delayed entry.
- Split and result: 2021 rank diagnostics only, with no policy economics.
- Exact closure: candidate ranking has been tried. These receipts can speak to opportunity ordering in the old E1r candidate universe. They cannot select a new-extreme-event frontier or prove that a later observation creates a better executable entry.

### Candidate age rank

`/workspace/tools/run_confirmation_candidate_age_rank.py` owns `/workspace/artifacts/entry_v2/confirmation/candidate_age_rank_paired_no_phase_v4.json`.

- Clock and state: ages 0, 30, 60, 120, 180, and 240 seconds, without `phase_remaining_sec`, using `MAX_PLUS_EPISODE` state.
- Target and price control: `FORMATION_Q_OPTIMAL_BROADCAST`. The formation target is copied to later ages, so later rows do not receive delayed-entry price control.
- Split and result: the PLATT selector chooses age 30. THRESHOLD capture is `0.2493` for the real arm versus `0.1153` for its negative control under the selected-age scorecard. No economics is run.
- Exact closure: age-specific observation helps rank formation opportunities in this setup. It does not establish profitable delay, because the target does not charge the later entry price.

### Candidate value

`/workspace/tools/run_confirmation_candidate_value.py` owns `/workspace/artifacts/entry_v2/confirmation/candidate_value_probe_v1.json`.

- Clock and state: formation-time robust feature families on the ordered candidate set.
- Target and price control: `FORMATION_Q_OPTIMAL_BROADCAST`; no delayed repricing.
- Split and result: the PLATT selector chooses `LOG1P_RMSE`. THRESHOLD capture is `0.24089` for the real arm versus `0.20342` for the control under the selected-objective scorecard. No economics is run.
- Exact closure: formation candidate value contains, at most, a weak held-role ranking increment under this objective. It is not a confirmation or delayed-entry policy.

## Question-level verdicts

### Event-frontier elimination

UNRESOLVED at the live frontier. Candidate acceptance, candidate rank, candidate value, lawful value rank, and top-k roster restriction have all been tried. It is therefore wrong to say that no candidate elimination has ever been measured. The narrower proposal remains new because none of these receipts constructs the saved new-extreme-event frontier from the 2022 through 2024 forecast corpus, assigns exact 180-second realized event value, and measures event capture under a causally frozen eliminator. The old receipts rank candidates or formation opportunities. They do not identify which extreme event caused the cell value.

### Delayed commitment

ESTABLISHED as an attempted family, not as a successful policy. Fixed-horizon value, lawful policy, path state, factorized policy, dynamic hurdle, direct utility, action probes, candidate-age ranking, and Snell-style stopping all inspect information after formation. Exact row or horizon repricing is present in the lawful, path-state, factorized, dynamic-hurdle, direct-utility, action, ordered-value, and Snell targets. Candidate-age and candidate-value probes are the important exception because they broadcast formation value. No receipt establishes a deployable delay rule. Paths beyond 300 seconds and clean held-year evaluation remain untested here.

### Snell-style stopping

RETRACTED as a novel proposal. The factorized v2 Snell probe already tests fitted continuation for three iterations on causal sparse path state. Its THRESHOLD capture collapses. The correct narrow closure is failure of this implementation and state shape, not failure of optimal stopping as a class.

### Candidate ranking

ESTABLISHED as diagnostic work. Several receipts show non-null within-universe ranking. UNRESOLVED as event identity or policy value. Candidate-local capture, cell-level value capture, and formation opportunity rank cannot be substituted for identifying the event that will carry the cell or for executing at a lawful price.

### Path-state confirmation

RETRACTED as untried. Action probes, ordered value, the path-state ceiling, the FIT OOF objective comparison, factorized policy, dynamic hurdle, direct utility, and Snell all use post-formation state. The strongest deployability-relevant receipt is negative: the preregistered path-state objectives fail stable FIT OOF progression. The broader class remains unresolved because the tests share the old 2021 corpus, sparse clocks, and limited horizons.

## Causal and evidentiary defects

- PLATT-selected economics is explicitly a ceiling in the lawful-policy and path-state receipts. Reusing it to choose top-k, delay, objective, or threshold creates selection bias.
- The older probes read FIT, PLATT, and THRESHOLD repeatedly while objectives and state shapes evolved. THRESHOLD is no longer a clean untouched confirmation role for the family.
- `hindsight_argmax` and oracle timing use realized future rows. They are useful upper bounds or diagnostics, not lawful actions.
- `FORMATION_Q_OPTIMAL_BROADCAST` is a proxy at later ages. It preserves formation value and omits the price paid for waiting.
- Sparse candidate-grid schedule evaluation omits the complete chronological opportunity stream. A true evaluator can run while the replay is still noncanonical.
- The ordered-value negative control matches or exceeds the ordered arm. Sequence order and event identity are therefore not identified by that receipt.
- Top-k candidate or cell capture is conditional on the candidate universe and roster. It does not show that the selected candidate is the causal event behind a cell's best replay dollars.
- No reviewed receipt supplies a calendar-year held evaluation after the 2021 mechanism and model work. Forward and H2 counters are unopened where reported.
- Feature names that encode phase, realized range, episode summaries, reclaim, or clock state require timestamp-level provenance. A causal-sounding name is not proof that the value existed before the action.

## What remains genuinely novel

The live action remains distinct if it is kept narrow:

1. Build the sealed-off-from-2025H2 2022 through 2024 corpus from the saved forward-vol forecast and the exact entry ledger.
2. Define the new-extreme-event frontier before outcomes, then join forecast range, realized range, cell best, event identity, and exact 180-second replay dollars without broadcasting cell value to every event.
3. Freeze an eliminator or ranker on earlier years, evaluate it on a later calendar year, and charge the entry price at its decision clock.
4. Replay the resulting policy on the complete chronological stream. Report capacity, overlap, costs, drawdown, dollars per trade, dollars per portfolio day, and event capture.
5. Treat holds longer than 300 seconds as new work. The receipts in this audit do not establish their value or futility.

The receipt record supports diagnostic oracle value and some within-universe rank signal. It does not support a deployable confirmation policy, a causal event-identity claim, or canonical replay dollars.

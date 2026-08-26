# THRESHOLD 2022-2024 freeze

Frozen 2026-08-26 before any 2022+ outcome dollar was parsed. This page binds the one authorized THRESHOLD-equivalent dollar read on the stored G1 tables. An implementer codes `.audit/score_threshold_2022_2024_read.py` from this page without asking which head, fold, allocation, or name pick to use. Plumbing (paths, schemas, join proof, peek guards, runtime) is `.audit/briefs/threshold-freeze-how-out.md`. Where that brief and this page disagree, this page wins. One measured correction to it: `outer_fold` runs 1-7 on the daily head, not 1-5.

## The frozen rule, one sentence

Enter one contract in every joinable cell (asset, d8, phase) on every selected day, taking each cell's earliest CLEAR candidate; a day is selected when its routed catboost `daily` `forecast_variance` is at or above the expanding median of all strictly prior routed days in the window; cash is `cert_close_usd` on `status == READY`.

## Execution order

1. **Window.** Session days 2022-03-09 through 2024-12-31 that have both a G1 candidates file and a forecast day. Mask the forecast `day` column to this range before anything else. 2025H1 stays unread. 2025H2 is sealed. 2021 can kill and cannot promote; this rule has no 2021 forecast rows, so its 2021 rehearsal is `--selftest` machinery only.
2. **Fold routing.** For each ISO day, the routed row is the `artifacts/runs/e6_vol_forecasts_v2/vol_service_forecasts.tsv` row with `arm == catboost`, `head == daily`, and the maximum `train_sessions_n` among that day's such rows. On a tie take the lowest `outer_fold` (ties are real: 279 of 708 era days). F(day) is that row's `forecast_variance`. A day with no catboost daily row is refused: no entries, out of every denominator, counted in the receipt as `refused_no_forecast`. Refusal is the whole rule; substituting another arm or head, or averaging whatever folds are present, is forbidden. Every published row is out-of-fold for its own day (`train_sessions_n` grows with day inside every fold), so routing picks freshness, not leakage.
3. **Day gate. This is how the assetless forecast allocates cells.** Order routed days ascending. Day d_i is SELECTED iff F(d_i) >= median of {F(d_1) .. F(d_i-1)} (numpy median, midpoint on even counts). The first routed day has an empty prior set and is not selected. On a selected day the entered cell set is every joinable cell for that day; on an unselected day it is empty. The forecast decides only this day-level cell set. It is day-level and assetless, so it cannot pick the name and cannot rank assets or phases. Write that sentence into the receipt's `frozen_rule` string.
4. **Cells and the name pick.** A cell is (asset, d8, phase) with phase in {0, 1, 2}; convert the forecast ISO day (2022-10-03) to d8 (20221003) for the candidates lookup. Within each entered cell, eligible candidates are rows with `compliance_status == CLEAR`. Pick the eligible candidate with the smallest `decision_ts_ns`; tie-break the lexicographically smallest `candidate_id`. A cell with no eligible candidate is skipped; zero-row and dead days are normal. One name per cell, one contract, side as the candidate carries it. Parse candidates with `skiprows=1` (line 1 is a `#` schema comment) and `usecols` limited to `candidate_id`, `asset`, `d8`, `phase`, `decision_ts_ns`, `compliance_status`, `frozen_cost_usd`.
5. **Caps.** At most 12 entries per portfolio day; this rule enters at most 9 (3 assets times 3 phases). One position per asset at a time, verified by the overlap check in step 8, not assumed. One contract per entry, never sized. Dollars must come per trade, not from extra size or extra count.
6. **Cash. The one authorized outcome read.** Join selected `candidate_id` values to the same asset-day teacher file `artifacts/cache/port/entry_v2/g1/teacher/{asset}/{d8}.tsv`. This join is the only place any teacher file is opened, and only on selected asset-days. Teacher `usecols` are exactly `candidate_id`, `status`, `cert_close_usd`, `exit_ts_ns`; `mfe_usd`, `mae_usd`, `payer`, and `take_target` stay unparsed. Cash per name is `cert_close_usd` where `status == READY`. A selected name without a READY row scores zero cash, still counts as an entry, and increments `selected_not_ready`.
7. **Cost.** `cert_close_usd` is already net of `frozen_cost_usd`: the engine computes cert as side times (exit_mid minus entry_mid2) times the contract factor minus `frozen_cost_usd`, and validates `cost_applied_count == 1` (`engine/entry_v2/confirmation_index.py`, `engine/entry_v2/tabular_delayed_outcomes.py`). Use `cert_close_usd` as stored and do not subtract `frozen_cost_usd` a second time. Report the sum of `frozen_cost_usd` over selected entries as `selected_frozen_cost_usd_total` so a reviewer can reconcile gross against net.
8. **Aggregate.** Per asset a, D_a is the count of days that are selected and joinable for a (a candidates file with at least one row plus a routed forecast day). `usd_per_asset_day[a]` is a's total cash divided by D_a. A selected joinable day with zero eligible or zero READY names stays in D_a at zero cash. `max_drawdown_usd` is the portfolio peak-to-trough of the running cash sum over all selected entries ordered by (d8, `decision_ts_ns`, `candidate_id`). Overlap check per asset: sort selected entries by `decision_ts_ns` and count pairs where the next entry's `decision_ts_ns` precedes the prior entry's `exit_ts_ns`.

## Dollar stop

The receipt's `dollar_stop` is non-null. Verdict RUNGS requires all of:

- trades > 0
- HG `usd_per_asset_day` >= 2000
- NKD `usd_per_asset_day` >= 1500
- SI `usd_per_asset_day` >= 1500
- `max_drawdown_usd` < 1000
- max entries per portfolio day <= 12
- overlap violations == 0

Any asset short of its rung is a KILL. Any other line failing is a KILL. A KILL names the exact blocker in the receipt: the per-asset shortfall in dollars plus the pre-bound sentence "forecast day-gate plus a skill-free name pick did not clear the rungs; the unmeasured lever is within-cell name selection, which has no instrument (T53/T54)". The verdict is rungs or a dollar kill. No CV, AUC, or overlay bar appears anywhere in it.

## What a pass means

Teacher-cash can kill the forecast plane. Teacher-cash cannot promote. A RUNGS verdict here is not THRESHOLD. Promotion still needs one `QRE2TABPOLICYBLOCK2` that clears `python3 .audit/assert_threshold_replay_receipt.py`. Write this paragraph into the receipt so a later agent cannot treat a teacher pass as THRESHOLD.

## One read

The authorized run executes once and writes `.audit/threshold-2022-2024-read.json`. Rerunning the unchanged script is the same read; it is a pure function of stored bytes. Any formula change, second gate, alternative head, or alternative pick run after the receipt exists is exploratory and is labelled exploratory in the same sentence it is reported.

## Receipt contract

Commands: `python3 .audit/score_threshold_2022_2024_read.py` (the one authorized run) and `--selftest` (synthetic rows, zero era bytes). Template discipline is `.audit/score_h5_top2.py`: strict loads, identity refusals, atomic receipt write. Schema `QRE2THRESHOLD20222024READ1`. Required fields: `schema`, `sources` (paths plus sha256s; per-day G1 receipts carry `output_sha256`), `window`, `frozen_rule` (the one-sentence rule verbatim), `check_command`, day counts (`routed`, `selected`, `refused_no_forecast`), per asset `cash_total_usd`, `days` (D_a), `usd_per_asset_day`, `trades`, `per_trade_mean_usd`, `selected_not_ready`, portfolio `max_drawdown_usd`, `max_entries_portfolio_day`, `overlap_violations`, `selected_frozen_cost_usd_total`, and the non-null `dollar_stop`. Runtime is minutes on one core (the how session streamed the full era in 95 s); a `ProcessPoolExecutor` over 13-16 workers is allowed, never nproc's 64, no GPU.

## Forbidden formulas

Ticket 28 hold. Ticket 39 location-ranker. E1R ENTER-weight. Roster fields. Enter-all. Stitching `policy_mode`. The name pick in step 4 is arrival order behind a compliance filter, not a fitted field rule, which is why it is not a roster-field formula. Do not relax any rung.

## Measured facts this freeze rests on

All measured 2026-08-26 with dollar columns never parsed on any 2022+ day.

- 708 era forecast days and all 708 carry a catboost daily row, so `refused_no_forecast` should be zero; joinable days HG 693, NKD 685, SI 662 (how-out).
- catboost publishes `daily` plus intraday 30, 180, 210, 240, 270; ridge publishes intraday 60, 90, 120, 150, 300, 330. `daily` exists only on catboost.
- Folds 1-7 are walk-forward launches with retrain cadences of roughly 16, 32, 47, 63, 79, 94, and 109+ sessions; `train_sessions_n` increases with day inside every fold.
- Candidates: 34 columns, phase values {0, 1, 2}, `compliance_status` CLEAR on the sampled day, line 1 a `#` comment.
- Teacher: 15 columns, `status` READY on the sampled day, `exit_ts_ns` present.
- Wiring PASS `.audit/ticket45-HG-20221003-cache.json`; candidate and teacher row counts match on all 2,817 era asset-days (how-out).
- Why the allocation is day-level and not per-phase: the served TSV is assetless and carries no phase-to-clock mapping, so a per-phase formula would be invented, not measured. The day gate transplants T53's median split (2x cell-value separation, held out of sample) onto the T54 instrument (20.8-28.4% range skill), made causal by the strictly-prior expanding median. The intraday term structure stays exploratory.

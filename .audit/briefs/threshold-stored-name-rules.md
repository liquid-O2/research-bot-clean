# Stored-join name rules. Sol specified sequence.

`/poteto-mode` Prototype. You are Sol (`gpt-5.6-sol-max`). Do not inherit Grok. Do not write `engine/`. Do not start ticket 47. Do not add a ninth causal line.

Parent verified Fable's gap: `confirmation_event_ordinal`, `prefix_last_event_ordinal`, and `spread_prior_usd` sit in `# QRE2G1CAND2` (`engine/entry_v2/corpus_artifacts.py` `_CANDIDATE_COLUMNS`) and are absent from `.audit/threshold-live-scalars.json`, `threshold-rank-live.json`, and `threshold-fit-name.json`.

Execute the experiment section of `.audit/briefs/threshold-covering-after-stored-kill-out.md` verbatim. Stop text is already bound there. Copy it into the receipt.

## Artifacts

- Script `.audit/score_threshold_stored_name_rules.py`
- Receipt `.audit/threshold-stored-name-rules.json`
- Schema `QRE2THRESHOLDSTOREDNAMERULES1`

## Reuse

- Loaders, freeze gate, sha checks, 14 workers. `.audit/score_threshold_rank_live.py` and `.audit/score_threshold_live_scalars.py`
- Enter-positive ceiling line. `.audit/score_threshold_2022_2024_ceiling.py` `pick_cell_best_ready` / `summarize_line`
- Selftest and receipt discipline. `.audit/score_h5_top2.py`
- Refuse if gated days drift from HG 197, NKD 194, SI 191

Teacher parse stays `candidate_id`, `status`, `cert_close_usd`, `exit_ts_ns`. Add candidate columns `confirmation_event_ordinal`, `prefix_last_event_ordinal`, `spread_prior_usd`, `spread_prior_present`, plus `entry_mid2` and `side`. Do not parse `mfe_usd`, `mae_usd`, `payer`, `take_target`.

## Domain

A cell is `(asset, d8, phase)` among CLEAR rows. Order by `(decision_ts_ns, candidate_id)`. Recency is `prefix_last_event_ordinal - confirmation_event_ordinal`. A setter beats the running same-side extreme of prior rows (`entry_mid2` above the running max on side +1, below the running min on side -1). The first row of a side is a setter. Setter excess is that distance, 0 for a side's first row.

Eight causal lines, closed. Plus labelled hindsight `ceiling_setters` (max READY setter `cert_close_usd` when positive). Cite `.audit/threshold-2022-2024-ceiling.json`. Do not rerun the full ceiling.

1. `ordinal_freshest`. Min recency. Tie max `decision_ts_ns`. Tie smallest `candidate_id`.
2. `ordinal_stalest`. Max recency. Same tie chain.
3. `ordinal_latest_event`. Max `confirmation_event_ordinal`. Tie smallest `candidate_id`.
4. `extreme_last_setter`. Setter with max `decision_ts_ns`.
5. `extreme_deepest_setter`. Setter with max excess. Tie max `decision_ts_ns`.
6. `extreme_first_nontrivial_setter`. Earliest setter with excess > 0. Fallback earliest CLEAR.
7. `spread_prior_max`. Max `spread_prior_usd` among `spread_prior_present == 1`. Fallback earliest CLEAR.
8. `spread_prior_min`. Min, same guard and fallback.

Each causal line reports `usd_per_asset_day`, trades, per-trade mean, `max_drawdown_usd`, entry cap, overlap. One contract. Caps stay.

## Sequence

1. `--selftest` on synthetic rows. Zero era bytes. Mutate (non-strict setter compare, dropped recency tie-break) and confirm red.
2. One window run. 13-16 workers. Wall should be one to two minutes after load.
3. Write the receipt with sources sha256s and the covering stop verbatim.
4. Verdict is RUNGS if any causal line clears HG 2000, NKD 1500, SI 1500 per asset-day, `max_drawdown_usd` < 1000, trades > 0, cap and overlap. Else KILL.

Teacher-cash cannot promote. This prototype is throwaway.

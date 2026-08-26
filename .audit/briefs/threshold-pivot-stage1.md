# Stage 1. 2021 THRESHOLD kill read. Sol specified sequence.

`/poteto-mode` Prototype. You are Sol (`gpt-5.6-sol-max`). Do not inherit Grok.

Stage 0 passed Fable judgment (`.audit/briefs/threshold-pivot-stage0-judge-out.md`). Execute Stage 1 of `.audit/briefs/threshold-covering-after-tape-kill-out.md` only. Stop after the receipt. Do not start Stage 2. Do not start B, C, or D. Do not start tickets 37, 46, or 47. Do not add a ninth line. Do not emit 2022-2024 tags.

Copy the Stage 1 stop into the receipt.

## Artifacts

- Script `.audit/score_threshold_pivot_name_rules.py`
- Receipt `.audit/threshold-pivot-stage1.json`
- Schema `QRE2THRESHOLDPIVOTSTAGE11`

## Day set

20210721 through 20210806. Same 2021 THRESHOLD block the sibling 2021 receipts load. Dense-store metadata under `artifacts/entry_v2/tabular_recovery/dense_store`. Refuse if the block tag is absent. Templates: `.audit/score_threshold_feature_rank.py` for the window and G1 join, `.audit/score_threshold_tape_name_rules.py` for the eight-line scan and envelope.

Teacher parse stays `candidate_id`, `status`, `cert_close_usd`, `exit_ts_ns`. Pivot features come from the lowest fired `rung_index` on each `candidate_id` in `artifacts/cache/port/entry_v2/g1/pivot/{asset}/{d8}.tsv`. A candidate with no tag refuses the run. Do not parse `mfe_usd`, `mae_usd`, `payer`, `take_target`.

Rungs are HG 2000, NKD 1500, SI 1500 `usd_per_asset_day`. One contract. Caps stay. 2021 can kill and cannot promote.

## Eight causal lines, closed

Ties: max `decision_ts_ns`, then smallest `candidate_id`.

1. `pivot_leg_with`. Argmax of side times (pivot_mid2 - leg_start_mid2).
2. `pivot_leg_against`. Argmin of the same.
3. `pivot_retrace_max`. Argmax of |pivot_mid2 - conf_mid2| / |pivot_mid2 - leg_start_mid2|.
4. `pivot_retrace_min`. Argmin.
5. `pivot_age_max`. Argmax of decision_ts_ns - pivot_ts_recv_ns.
6. `pivot_age_min`. Argmin.
7. `pivot_legdur_max`. Argmax of pivot_ts_recv_ns - leg_start_ts_recv_ns.
8. `pivot_legdur_min`. Argmin.

Plus labelled hindsight `envelope_pivot8`: per cell the max READY `cert_close_usd` among the eight picks, entered only when positive. Each line reports the full dollar block and the T44 entry-price twin match rate (fraction of cells where the pick equals the side-times-entry-price pick).

## Sequence

1. `--selftest` on synthetic rows. Zero era bytes. Mutants red: post-flip leg used as the feature; missing tag accepted; envelope includes a non-positive cell.
2. One 2021 THRESHOLD window. 13-16 workers. Minutes, not hours. Tags already exist.
3. Verdict KILL if all eight causal lines and `envelope_pivot8` miss every rung. Any causal line or the envelope clearing a rung is not KILL. A 2021 clear promotes nothing.

Teacher-cash cannot promote. This prototype is throwaway.

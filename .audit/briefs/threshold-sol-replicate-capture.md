# Sol. Replicate the capture receipt

Specified sequence. Model `gpt-5.6-sol-max`. Do not inherit Grok. Do not edit `engine/`.

1. Run `python3 .audit/score_threshold_capture_gap.py --selftest`. It must print `selftest_ok`.
2. Read `.audit/threshold-capture-gap.json`. Do not trust chat.
3. Write `.audit/briefs/threshold-sol-capture-replicate.md` with only these fields, copied from the receipt:
   - `verdict`
   - `capture.n_cells`
   - `capture.n_earliest_is_best`
   - `capture.match_rate`
   - `capture.mean_best_time_rank`
   - `capture.mean_cell_n_clear`
   - `capture.cash_left_on_table_usd`
   - `lines.earliest.usd_per_asset_day`
   - `lines.latest.usd_per_asset_day`
   - `lines.cheapest.usd_per_asset_day`
   - `lines.cell_best.usd_per_asset_day`
   - one sentence naming the live decision that loses, citing `dollar_stop.applied`

If any field is missing, write INCONCLUSIVE and stop.

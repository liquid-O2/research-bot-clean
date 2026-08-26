# Stage 1 judge verdict. Fable.

**KILL.** Confirmed from the bytes of `.audit/threshold-pivot-stage1.json`, not from Sol's summary. All eight causal pivot-geometry lines and `envelope_pivot8` miss the joint 2021 THRESHOLD rungs (HG 2000, NKD 1500, SI 1500 `usd_per_asset_day`). Stop and wait. Stage 2 is not authorized.

Rerun the byte sweep with `python3 .audit/assert_threshold_pivot_stage1.py` (exit 0, prints `PASS all byte checks held`, about 5 seconds). This session also reran the receipt's verification commands: selftest exit 0, each of the three mutants red for its named seam.

## Schema and framing

Receipt bytes: `"schema": "QRE2THRESHOLDPIVOTSTAGE11"`, `"status"` and `"verdict"` both KILL, window 2021-07-21 through 2021-08-06, block tag `E1R_raw_THRESHOLD`. The eight causal lines are the frozen set in the frozen order, ties max `decision_ts_ns` then smallest `candidate_id`, features from the lowest fired rung per candidate. Teacher parse stayed `candidate_id`, `status`, `cert_close_usd`, `exit_ts_ns`; no peek column (`mfe_usd`, `mae_usd`, `payer`, `take_target`) appears in any parsed column list. `n_dense_feature_bytes_read`, `n_era_bytes_read`, and `n_forecast_rows_read` are all 0. Workers 14, wall 7.613 seconds.

## The dollar arithmetic, recomputed

I recomputed every `usd_per_asset_day` as `cash_total_usd` over `days`, every `per_trade_mean_usd`, every shortfall, and the joint gate `all(usd >= rung)` per block, then checked every receipt flag against the recompute. All agree. Per asset-day dollars:

| line | HG (rung 2000) | NKD (rung 1500) | SI (rung 1500) |
| --- | --- | --- | --- |
| pivot_leg_with | -230.38 | -242.88 | -305.42 |
| pivot_leg_against | +204.71 | -374.62 | -274.17 |
| pivot_retrace_max | -153.94 | -245.77 | -390.83 |
| pivot_retrace_min | -29.42 | -78.46 | -532.92 |
| pivot_age_max | -661.63 | -315.00 | +219.17 |
| pivot_age_min | -93.37 | +99.42 | -554.38 |
| pivot_legdur_max | +172.98 | +77.31 | +132.08 |
| pivot_legdur_min | -581.35 | -229.42 | +67.08 |
| envelope_pivot8 | +1788.75 | +1192.12 | +1854.38 |

No causal line clears even a single asset rung; the sweep asserts the only individual clear anywhere is the envelope's SI leg. The best causal cells are pivot_leg_against HG at +204.71 and pivot_legdur_max HG at +172.98 against a 2000 rung, about a tenth of the bar. Every causal line also breaches the 1000 drawdown limit (2912.50 to 15280.00 across the eight), so nothing was close on any axis. Lines carry 113 trades each, the envelope 108. Twin match rates run 1.8 to 6.2 percent, so the geometry picks were nearly disjoint from the entry-price twin (T44 control); the family carried genuinely new information and still missed.

## The envelope's SI-only clear does not lift the family

`envelope_pivot8` posts HG 1788.75 (shortfall 211.25), NKD 1192.12 (shortfall 307.88), SI 1854.375 (clears its 1500). The bound stop binds the joint rungs, and the sibling tape receipt set the precedent: `envelope_tape8` cleared NKD and SI, missed HG by 50.04, and the family died. `line_clears` in the shared ceiling module (`.audit/score_threshold_2022_2024_ceiling.py` line 179) requires all three assets, so the receipt's `clears_rungs: false` on a SI-only clear is the same gate every sibling receipt applied. The stage-1 Sol brief's sentence "Any causal line or the envelope clearing a rung is not KILL" reads in that joint sense; a per-asset reading would resurrect exactly the read-peek-amend the tape KILL closed. This envelope sits farther from the bound than the tape one did, two assets short with a worst shortfall of 307.88 against the tape's single 50.04.

## Day set and denominators

The joined roster is HG 13, NKD 13, SI 12, the block weekdays with SI missing 20210802. The missing day is roster truth, not a dropped day: no identity under the dense store holds `SI/20210802.npz`, the feature-rank sibling receipt records the same 13/13/12 denominators, and every joined asset-day sits in the block's `expected_sessions`. All eight lines and the envelope carry identical denominators, and no joined day falls outside 20210721 through 20210806.

## Sources pinned to the bytes

158 files rehashed to the recorded sha256s: per asset-day the candidates, pivot, and teacher TSVs plus the dense-store metadata, and the six top-level sources (script, stage 1 brief, covering brief, stage 0 receipt, feature-rank receipt, threshold block). Candidates and teacher hashes equal their generation receipts' `output_sha256`. Every pivot tag hash equals the Stage 0 determinism-guard hash for that asset-day, so the tags scored here are exactly the tags Stage 0 judgment passed. `dollar_stop.verbatim` is byte-equal to the covering brief's stage 1 stop.

## Selftest and mutants, red for the named reason

`--selftest` returns before any receipt write, so these runs touched nothing. Baseline selftest printed `selftest_ok zero_era_bytes=1` and exited 0. `post_flip_leg_used_as_feature` flips the pivot_leg_with and pivot_retrace_min picks and dies on the pick assertion, proving the pre-flip leg start is load-bearing. `missing_tag_accepted` dies on "selftest accepted a candidate with no pivot tag". `envelope_includes_non_positive_cell` dies with the -1.0 cell present in the entered set. A real window run refuses any `QRE2_PIVOT_MUTANT` value before reading a byte, so the published receipt cannot be a mutant run.

## Verdict

KILL. The unfitted pivot-geometry family is closed at age 180 without spending an era read. Stop and wait. Stage 2 does not fire, nothing here funds B, C, or a ninth line, and per the fired stop the remaining forks are late ages (B) against the single fitted read (C), a new covering decision that is not this page.

# Clear THRESHOLD rungs from a head that never ENTERs

The frozen E1R regret head never makes ENTER the strict min on any window it has been walked, TRAIN included. Same-window teacher dollars already clear every rung. Labels mark ENTER optimal on 7.7% of fit rows. The fitted head does not.

Old tickets and recovery-plan sequences are prior attempts. They are not the method. The A1 MARGIN walk already ran. Do not stitch `policy_mode` to replay it.

## Rungs

A THRESHOLD `QRE2TABPOLICYBLOCK2` must show all of the following.

- HG `usd_per_asset_day` at or above 2000
- NKD `usd_per_asset_day` at or above 1500
- SI `usd_per_asset_day` at or above 1500
- `max_drawdown_usd` under 1000
- at most 12 entries per portfolio day
- dollars per trade, not extra size or extra count

`python3 .audit/assert_threshold_replay_receipt.py` must be able to exit 0. Selftest proves that with a synthetic passing block. Published blocks have no per-asset dollars in `gate_detail`, so a real PASS still needs those fields on the block.

## Bottleneck

**ESTABLISHED.** The frozen E1R regret head never prefers ENTER on any walked window. This is a fit failure against non-degenerate labels, not a held-only miss.

- THRESHOLD replay. $0, 0 trades, on 20210721-20210806. Five real plus five shuffle. Teacher ceiling $102201.25. Command `python3 tools/run_tabular_recovery.py --phase rehearsal`. Artifact `.../E1R_raw_THRESHOLD/real/seed_20260820/raw_block.json`.
- TRAIN capture. 0.0 to 0.43 percent against a 0.9 target. Receipt `--enter-gap`.
- Advantage grid. All five seeds, 21 quantiles, all negative. Best quantile -$43.31.
- MARGIN diagnosis. 588 CALIBRATED day traces under `diagnosis/margin_rule/`. 0 selected. 0 arrivals. Receipt `--margin-closure`.
- FORWARD. Ten calibrated blocks, 0 trades.
- Labels. `fits/round_2/action_matrices` has 21527 rows, ENTER optimal on 1657.

RAW can ENTER. `_learned_action` is reached. It never returns ENTER.

## Next units

2021 can kill. 2021 cannot promote. 2025H2 stays sealed. Do not ask the sleeper the refit fork. Record it.

1. **MARGIN closure receipt.**
   Done this file. `python3 .audit/assert_threshold_replay_receipt.py --margin-closure`. Kill. Any of those traces shows a selected id.

2. **Head-versus-label separation. Minutes. Predict only. No training.**
   Action. Load the frozen per-fold action models. Predict on stored `action_matrices` rows. Publish in-sample fraction where predicted enter regret is the strict min, against the 7.7% label rate, plus predicted-margin versus label-margin.
   Artifact. A receipt next to `.audit/threshold-enter-gap-20260825.json`.
   Done. Both fractions on disk.
   Kill. If the head ranks ENTER min in-sample at a healthy rate, the cause retracts to a feature mismatch between matrix rows and walk-time features.

3. **Refit fork, when the human is awake.**
   Every frozen E1R artifact is inert. Whether one refit of this head family on these labels counts as a new trading model is a product call. Option a, permit that one refit, 2021-kill rules unchanged. Option b, retire E1R. No third option. Attach the unit-2 receipt. Do not AskQuestion overnight.
   Standing kill for whatever survives. THRESHOLD top-2 means are $628 HG against $667 per trade and $434 NKD against $500.

4. **A later held window only after something ENTERs on 2021.**
   Dollars per trade at or above the bars, shuffle null and entry-price twin survived. Then one `QRE2TABPOLICYBLOCK2` on a later window. One read. Building 2022 shards before that is dead spend.

## Closed repeats

- Threshold-sweep or reweight the current head's outputs. The grid is negative.
- Stitch `policy_mode` through `evaluate_policy_block` to re-run A1.
- Treat location-ranker cash or v9 PLATT as THRESHOLD replay.
- Rank on side times entry price.
- Extra size or extra entries.
- Relax any rung.
- Promote on any 2021 number.
- Walk a numbered ticket list.

## Seats

Parent Grok 4.6 xhigh. Judgment Fable `claude-fable-5-thinking-max` via `cursor-agent --model` when Task rejects the slug. Specified work Sol `gpt-5.6-sol-max`. Do not inherit Grok for those seats.

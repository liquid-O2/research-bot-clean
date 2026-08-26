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
- Head versus label. Receipt `python3 .audit/assert_threshold_head_labels.py`. Label ENTER rate 7.70%. Fold-routed OOF ENTER-min on stored matrix rows is 0, 0, 2, 0, 1 of 20049. Frozen head on all 21527 rows peaks at 32 ENTERs (0.15%). `healthy_in_sample` is false. Label `action_margin_cents` is unsigned best-versus-second. Predicted margin is signed ENTER-versus-other. Do not treat those as one comparison. The receipt scores stored matrix rows. It is not a walk-time feature twin.

RAW can ENTER. `_learned_action` is reached. It never returns ENTER. The same head almost never ranks ENTER min on the stored fit rows either. A concurrent feature mismatch is still unexcluded.

## Next units

2021 can kill. 2021 cannot promote. 2025H2 stays sealed. Do not ask the sleeper the refit fork. Record it.

1. **MARGIN closure receipt.**
   Done. `python3 .audit/assert_threshold_replay_receipt.py --margin-closure`. Kill. Any of those traces shows a selected id.

2. **Head-versus-label separation.**
   Done. `.audit/threshold-head-labels-20260826.json`. Kill did not fire. Do not rerun unless that receipt is missing.

3. **Next implementable work, when the human is awake.**
   The frozen E1R artifacts are inert. One recorded fork is a single refit of this head family on these labels, 2021-kill rules unchanged. Another is retire E1R. That pair is a product call, not an exhaustion proof. Attach the head-label receipt. Overnight must not AskQuestion and must not refit.
   Standing kill for whatever survives. THRESHOLD top-2 means are $628 HG against $667 per trade and $434 NKD against $500.

4. **A later held window only after something ENTERs on 2021.**
   Dollars per trade at or above the bars, shuffle null and entry-price twin survived. Then one `QRE2TABPOLICYBLOCK2` on a later window. One read. Building 2022 shards before that is dead spend.

Overnight diagnosis is done. The path is the four units above. Do not invent a fifth diagnostic.

## Closed repeats

- Threshold-sweep or reweight the current head's outputs. The grid is negative.
- Stitch `policy_mode` through `evaluate_policy_block` to re-run A1.
- Treat location-ranker cash or v9 PLATT as THRESHOLD replay.
- Rank on side times entry price.
- Extra size or extra entries.
- Relax any rung.
- Promote on any 2021 number.
- Walk a numbered ticket list.
- Treat the head-label receipt as a walk-time feature twin. It scores stored matrix rows.

## Seats

Parent Grok 4.6 xhigh. Judgment Fable `claude-fable-5-thinking-max`. Specified work Sol `gpt-5.6-sol-max`. Do not inherit Grok for those seats.

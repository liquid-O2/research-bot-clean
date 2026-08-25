# Clear THRESHOLD rungs from the $0 ENTER bottleneck

The connected E1R walk never prefers ENTER on held THRESHOLD. Same-window teacher dollars already clear every rung. This file is the checkable path from that bottleneck to promotion. Rungs do not move.

## Rungs

A THRESHOLD `QRE2TABPOLICYBLOCK2` from `replay_policy_block` must show all of the following.

- HG `usd_per_asset_day` at or above 2000
- NKD `usd_per_asset_day` at or above 1500
- SI `usd_per_asset_day` at or above 1500
- `max_drawdown_usd` under 1000
- at most 12 entries per portfolio day
- dollars per trade, not extra size or extra count

The command that stays red until that is true is `python3 .audit/assert_threshold_replay_receipt.py`.

## Bottleneck

**ESTABLISHED.** The E1R action-regret head never makes ENTER the strict argmin at any walked second on held THRESHOLD.

- Dollars. $0, 0 trades, MDD $0, on REHEARSAL_E1 THRESHOLD 20210721-20210806. Five real seeds plus five shuffle seeds. Same-window exact teacher ceiling $102201.25 (HG $40686.25, NKD $25955, SI $35560). Per asset-day ceilings about $3130, $1997, and $2735. The ceiling clears every rung.
- Command. `python3 tools/run_tabular_recovery.py --phase rehearsal`
- Artifact. `artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/evaluation/E1R_raw_THRESHOLD/real/seed_20260820/raw_block.json` schema `QRE2TABPOLICYBLOCK2`

RAW can ENTER. `_learned_action` returns ENTER when enter regret is strictly below min(defer, pass). Occupancy is false and the 12-cap is unused. The walk reaches that function and never returns ENTER. THRESHOLD day traces have empty `policy_crossing_timestamps` and empty `selected_opportunity_ids`. `rejected_fallback` is lawful abstention accounting.

Letter these separately. They are not the bottleneck.

- Admission is infeasible by inheritance. All five real `threshold_selection.json` files have `floor_feasible` false. Seed 20260820's quantile grid is entirely negative, about -648.92 to -98.22.
- The negative threshold is unreachable under ARGMIN. `decide` runs the argmin pre-stage before `action_advantage_threshold_usd`. FORWARD calibrated still replays 0 trades.
- Location-ranker THRESHOLD cash (HG 856.63, NKD 939.81, SI 1060.83) is diagnostic cell-pick `y`, not replay.
- Confirmation v9 never opened THRESHOLD. `threshold_open_count` is 0. `NO_FEASIBLE_THRESHOLD` is a PLATT status.

MEMORY #58 named the same head failure on an earlier E1R learner. This rehearsal rebuild reproduced $0. Treat #58 as history, not as tonight's ablation.

Fable judgment (2026-08-25, `2c6d715e-f156-47fb-a978-00e203175019`) locked this cause. Two folds below override that write-up, not the cause.

## Red

The rung gate is SHORT (exit 2) on the ten zero-trade blocks. That is red for any shortfall.

The cause-specific check is the crossing count on the THRESHOLD trace store. Sum of `policy_crossing_timestamps` lengths is 0 and trades is 0. That pair holds only while the walk never prefers ENTER. The gate reports those counts under `enter_preference`. Teacher dollars on the same window are the mutant without the cause. The ceiling is $102201.25. A 0-trade assertion applied to that teacher block would fail.

Ablation that would restore learned trades, after this path exists. `evaluate_policy_block` and `_load_or_replay_day` do not pass `policy_mode`. They default to ARGMIN. `replay_policy_day` already accepts `MARGIN` in CALIBRATED mode. Stitch `policy_mode` through those two call sites, then replay one THRESHOLD seed CALIBRATED with `policy_mode=MARGIN` and the frozen admission. Do not run `--phase rehearsal` for this. One seed, 13 days.

## Path

The rung predicate is unchanged on every step. 2021 can kill. 2021 cannot promote.

1. **MARGIN kill on 2021 THRESHOLD.**
   Action. Thread `policy_mode` into `evaluate_policy_block` and `_load_or_replay_day`. Replay seed 20260820 THRESHOLD CALIBRATED MARGIN with the frozen admission from `threshold_selection.json`.
   Artifact. A MARGIN `*_block.json` under `e1r/evaluation/` plus a fresh gate report.
   Done. `gate_detail.trades` is published. Crossing count is published.
   Kill. Still 0 trades closes "the argmin pre-stage is the only lock." Trades with negative or far-short dollars closes reweight, re-threshold, and retrain of this head. A surprising clear does not promote. Stop and go to ticket 45.
   Minutes path. One seed. Existing fitted bundles. No full rehearsal.

2. **2021 dollars-per-trade kill, only if step 1 ENTERs and still misses the rungs.**
   Action. Measure whether any 2021 localizer can raise dollars per trade on THRESHOLD event `y`. Ticket 51 is "land in the top two", not a loser screen. THRESHOLD uniform top-2 mean is already under the per-trade bar for HG ($628 vs $667) and NKD ($434 vs $500). SI top-2 is about $615. Rank-0 times cells still clears. Event frontier, delayed-commit, and cell-size conditioner are 2021 kill tests with the ticket-44 residual (score minus side times entry price). Forward-vol is an evidence budget after a localizer survives, never a name score. Pivot tape only after the frontier dies.
   Artifact. A null-controlled receipt with per-asset THRESHOLD dollars, SE, and the entry-price twin.
   Done. Every arm has a letter. Kill or survive is written.
   Kill. Lifecycle shuffle or the entry-price twin absorbs the cash. Causal top-2 at ages 180, 240, and 290 misses the per-trade bar by 2 SE. Then 2021 location work is closed.

3. **Ticket 45. One 2022 session through `build_corpus`.**
   Action. Follow `design/entry_reset/tickets/45-corpus-pilot-one-session.md`.
   Artifact. One strict-reloadable 2022 shard. Per-stage wall time. Prior-absent branch exercised. Feature order compared against a 2021 shard before the build.
   Done. Every checkbox on the ticket is ticked with a path.
   Kill. Silent forecast-context skip. Schema drift. Prior-absent branch wrong. Per-session wall time that makes 2788 sessions an hours job with no minutes path.

4. **Ticket 48. Freeze the protocol.**
   Action. Write the preregistration before any 2022-2024 selector dollars are read. Ticket 48's header says it is blocked by 47. Follow the ticket's why instead. Freeze first.
   Artifact. The committed prereg. Era bounds, one held read per frozen rule, rungs verbatim, nulls named.
   Done. The file is committed and names the selector that survived 2021 kills, or names "no 2021 survivor, first 2022 read is exploratory plumbing only."
   Kill. The write is skipped and someone reads 2022-2024 dollars anyway.

5. **Ticket 47. Build 2022-2024.**
   Action. Follow `design/entry_reset/tickets/47-build-2022-2024-corpus.md` after step 3's rate receipt and step 4's freeze.
   Artifact. Shard count equals session count per asset, or a day-by-day gap letter. Strict reload sample per asset and year. 2025 stays out.
   Done. Reload sample is green. Six-hour arithmetic is written from the pilot rate.
   Kill. Scale arithmetic fails the minutes-or-hours budget. Strict reload fails.

6. **One held 2022-2024 THRESHOLD read.**
   Action. PRODUCTION_E2 THRESHOLD is 20220428-20220609. Run the frozen selector through `evaluate_policy_block` → `replay_policy_block` → `replay`. One read.
   Artifact. A `QRE2TABPOLICYBLOCK2` whose `gate_detail` is the promotion receipt.
   Done. `python3 .audit/assert_threshold_replay_receipt.py` exits 0.
   Kill. Gate stays SHORT. Do not take a second held read. Label any extra look exploratory in the same sentence.

## Closed

Do the next untried step above. These repeats are finished.

- Retrain, reweight, or threshold-sweep the E1R regret head. The 21-quantile grid is negative. `floor_feasible` is false on all five real seeds. MEMORY #58 already closed this once.
- Treat location-ranker 856, 939, and 1060 as replay progress.
- Treat confirmation v9 `canonical_replay_executed` or PLATT `NO_FEASIBLE_THRESHOLD` as a THRESHOLD-role read.
- Rebuild a ranker on side times entry price (ticket 44).
- Re-run the rank-0 rich-cell analysis T50 retracted inside its null.
- Price the hold as the payer (ticket 49 demoted).
- Extra size or extra entries to buy the rung.
- Relax HG below 2000, or NKD or SI below 1500, or MDD to 1000 or above, or the 12-cap up.
- Promote on any 2021 number, including a MARGIN surprise.
- Inherit Grok for Fable or Sol seats. Allowed Task slugs are `claude-fable-5-thinking-high` and `gpt-5.6-sol-medium`.

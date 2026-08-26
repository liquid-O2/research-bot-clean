# Rank live G1 columns against cell-best

`/poteto-mode` Prototype. Grok xhigh-fast. Minutes path.

Read `poteto-mode/SKILL.md` and matching leaves only.

`.audit/threshold-live-scalars.json` verdict MISS. Min and max picks died. That does not prove the columns have no rank. Score every live numeric G1 column as a sort key inside the cell, and report where the READY cell-best sits.

## Do

Throwaway `.audit/score_threshold_rank_live.py`. Reuse the capture-gap and live-scalars join. Do not edit `engine/`. Do not rematerialize. Do not start ticket 47. Do not re-prove the ceiling.

For each gated cell with a READY cell-best, rank all CLEAR names by each column, both ascending and descending. Record the 0-based rank of the winner.

Columns: `decision_ts_ns`, `frozen_cost_usd`, `entry_spread_usd`, `compliance_distance_sec`, `sane_ceiling_usd`, `atr14_prev_usd`, `entry_mid2`, `side`. Skip peek columns (`mfe_usd`, `mae_usd`, `payer`, `take_target`).

`--selftest` first. Then the era on 14 workers.

Receipt `.audit/threshold-rank-live.json`. Schema `QRE2THRESHOLDRANKLIVE1`.

Per column and direction report `mean_winner_rank`, `median_winner_rank`, `n_cells`, `frac_rank0`, `frac_top5`.

## Stop

RANKS if any column-direction puts `mean_winner_rank` at or under 2.0, or `frac_top5` at or above 0.50. That column is the next frozen pick. MISS if none do. Then the remaining unit is a fitted name instrument on stored join features, still one teacher-cash read, still cannot promote.

2025 stays unread.

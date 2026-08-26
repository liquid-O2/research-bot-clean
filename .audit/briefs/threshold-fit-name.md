# Fitted name instrument on stored G1 columns

`/poteto-mode` Prototype. Grok xhigh-fast. Minutes path.

Read `poteto-mode/SKILL.md` and matching leaves only.

`.audit/threshold-rank-live.json` verdict MISS. No single live column ranks the winner. Next unit is one fitted name instrument on columns already on the candidate TSV. Do not build ticket 47 shards. Do not rematerialize. Do not edit `engine/`. Do not re-prove the ceiling. Entry only. One contract.

## Fit

Causal expanding window. On day D, train only on gated joinable cells with d8 strictly before D. Binary target is `is_cell_best` among CLEAR names in that cell (READY winner). Score every CLEAR name. Pick the max score, tie-break smallest `candidate_id`.

Features, live only: `decision_ts_ns` as rank-in-cell, `frozen_cost_usd`, `entry_spread_usd`, `compliance_distance_sec`, `sane_ceiling_usd`, `atr14_prev_usd`, `entry_mid2`, `side`. No peek columns. No `cert_close_usd`.

Learner: sklearn `LogisticRegression` on standardized features, 14 workers for the day join only. Keep the model cheap. If sklearn is missing, use numpy least squares on the same design matrix.

Reuse the capture-gap / live-scalars join and day gate. Same 197/194/191 gated days.

`--selftest` first, synthetic cells only. Then the era.

Receipt `.audit/threshold-fit-name.json`. Schema `QRE2THRESHOLDFITNAME1`.

## Stop

CAPTURED if the fitted pick clears HG 2000, NKD 1500, SI 1500 per asset-day on teacher-cash, same caps. That rule is the capture fix. MISS if it does not. Then the remaining unknown is whether corpus features (ticket 47) can rank the winner. Teacher-cash still cannot promote. 2025 stays unread.

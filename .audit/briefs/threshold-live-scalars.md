# Live G1 scalars after the capture miss

`/poteto-mode` Prototype. Parent stays Grok 4.6 xhigh. You are Grok xhigh-fast. Minutes path.

Read `poteto-mode/SKILL.md` and matching leaves only. Then extend `.audit/score_threshold_capture_gap.py` or write a sibling throwaway `.audit/score_threshold_live_scalars.py`.

## Already decided

`.audit/threshold-capture-gap.json` verdict MISS. Earliest matches cell-best in 149 of 1732 cells. Winner mean time rank 28.2 in a mean cell of 105.5. Latest and cheapest also miss. Do not re-prove the ceiling. Do not start ticket 47. Do not rematerialize. Do not edit `engine/`.

## What to score

One contract per gated cell, same freeze day-gate, cash is READY `cert_close_usd`. Pick among CLEAR names using one live G1 column at a time.

Columns already on the candidate TSV and not yet scored as a pick:
- min `entry_spread_usd`
- max `entry_spread_usd`
- min `compliance_distance_sec`
- max `compliance_distance_sec`
- min `sane_ceiling_usd`
- max `atr14_prev_usd`
- `side` (if a cell is mixed, pick the earlier CLEAR on the majority side)

Tie-break lexicographically smallest `candidate_id`.

`--selftest` first. Then the era. 14 workers. Expect about 30-60 seconds.

Receipt `.audit/threshold-live-scalars.json`. Schema `QRE2THRESHOLDLIVESCALARS1`.

## Stop

CAPTURED if any named rule clears HG 2000, NKD 1500, SI 1500 per asset-day. That rule is the fix. MISS if all die. Then the remaining unit is a fitted name instrument, still one frozen-rule teacher-cash read, still cannot promote.

2025 stays unread.

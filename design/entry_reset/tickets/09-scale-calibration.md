# 09: Scale calibration (tick distances are not portable)

**What to build:** a probe that, on the frozen 2021 matrix, publishes the
distribution of every distance the PDFs printed as a number, *and* of the
engine's own frozen tick constants, in our units, per asset and per 2021
block. No selector. No fit. The book integers (3, 12, 18, 2–4, 350%) are
NQ printed numbers. The engine integers (adverse −1, reclaim 0, lift +2,
retest band ±1, invalidated −4, near_formation ±2, `discretionary_features.py`
2000–2014 and 2547) are the same kind of fixed tick count, applied identically
to SI, HG and NKD. A 2-tick lift is $50 on SI/NKD and $25 on HG. Ticket 08's
gate turns on those constants; measuring the book's 18 while ours stay frozen
is the defect this ticket exists to catch.

For each of: zone width of a defense event, first-touch-to-extreme MAE
among cell-oracle winners, replenishment run length, post-lift
displacement, and the six engine thresholds above. Report own ticks,
dollars, and fraction of session ATR. TRAIN quantile vs THRESHOLD/FORWARD
as a stability check. Also report the fraction of series with `lift_seen`
and `retest_seen` by age 180 s and 290 s per asset and block. A flag that
fires on > 90% or < 5% of an asset's series is the typed degenerate row.
If the asset×block histogram is bimodal, also split by one coarse regime
already in the matrix and prove the split on TRAIN.

The state series stops at formation + 601 s. MAE that hits that wall is
typed truncated, not a quantile.

**Blocked by:** None (can start immediately). Read-only on the frozen
matrix. Does not change ticket 07's piles. If ticket 08 later needs a
distance, it takes the TRAIN quantile from this receipt, never 18.

**Status:** done (2026-08-22). Receipt
`artifacts/entry_v2/tabular_recovery/diagnostics/scale_calibration_20260822.json`.

- [x] `--selftest`: planted MAE 10 ticks = $125 on HG; lift constant $25; NaN y refused.
- [x] Real run wrote the receipt. TRAIN winner MAE: HG 4 ticks ($50), NKD 2.5 ($62.50), SI 3 ($75). Book 18 NQ ticks is not our MAE. Engine lift +2 ticks = $25 HG / $50 SI and NKD. lift_seen@180 = 0.26–0.52, not degenerate.
- [x] No typed occupancy defect on TRAIN (neither >0.90 nor <0.05).
- [x] Other-asset TRAIN MAE medians in `other_asset_quantile`.
- [x] Wall 218 s.

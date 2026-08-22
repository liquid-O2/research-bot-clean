# 10: S6 occupancy (does second defense carry within-cell information)

**What to build:** a read-only probe on the frozen 2021 matrix that, per
asset, block and snapshot age, reports the fraction of oracle-picked series
(argmax y in the cell at that age) that are S6-complete at the pick row,
beside the same fraction on non-picks and the within-cell shuffle band of
the pick fraction. No selector, no fit, no knob.

S6-complete means the price returned inside the level after a lift *and*
the defending quote was hit and rebuilt. Columns verified present on
matrix 7e9e2588…:

```
S6-complete iff
  disc_state_retest_seen == 1
  and disc_state_invalidated_seen == 0
  and disc_quote_h30_rebuild_after_depletion_count >= 1
  and disc_memory_z2_defense_reload_count >= 1
```

GEOMETRY arm: `disc_state_retest_seen == 1` only. Report it beside S6.
It is geometric return occupancy, not second-defense occupancy. Never
labelled S6.

Also report: the 601 s truncation rate (fraction of series whose last
stored row is still incomplete at the state-series stop,
`discretionary_features.py` 1978). A flag with pick rate < 0.02 at every
age on an asset is the typed row "S6 does not complete inside the snapshot
grid on \<asset\>", not a null.

**Blocked by:** None (can start immediately). Cannot contaminate 07 or 09
(separate receipt path).

**Status:** done (2026-08-22). Receipt
`artifacts/entry_v2/tabular_recovery/diagnostics/s6_occupancy_20260822.json`
(matrix 7e9e2588…). Ticket 08 does **not** open.

- [x] `--selftest`: planted S6 pick_rate=1.0; geometry-only inside shuffle band; NaN y refused.
- [x] Real run wrote the receipt. Wall 230 s.
- [x] Kill: HG and NKD TRAIN+THRESHOLD, every age, S6 pick−nonpick inside the shuffle band. SI's two out-of-band ages are *under*-representation (picks have less S6, not more). No asset over-represents S6-complete on TRAIN+THRESHOLD. Truncation/incomplete 74–85%. Scope: "S6 from existing quote/memory columns, Δ ≤ 290 s, 2021 sample".
- [x] Wall < 10 min.

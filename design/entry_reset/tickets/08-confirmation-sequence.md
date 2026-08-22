# 08: Confirmation as ordered stages (second defense, not geometry)

**What to build:** a probe that treats confirmation as an ordered machine on
the frozen 2021 matrix. A candidate is eligible only when price returned
*and* the same side defended again at that return. Value is taken at the
second-defense timestamp. Compare that eligibility, on the same rows, to
Dawes COMBINED at one second, to a GEOMETRY baseline (`retest_seen` only),
and to a shuffle of the *defense* evidence among names that all completed
the geometry. Do not shuffle the nested price-path latches: `retest_seen`
already implies `lift_seen`, `reclaim_seen`, `adverse_seen`, and
`retest_age_sec < lift_age_sec` (`discretionary_features.py` 1999–2012).

Decision-rich snippet (columns verified present on matrix 7e9e2588…):

```
eligible iff
  disc_state_retest_seen == 1
  and disc_state_invalidated_seen == 0
  and disc_quote_h30_rebuild_after_depletion_count >= 1
  and disc_memory_z2_defense_reload_count >= 1
```

GEOMETRY arm: `retest_seen == 1` only. Never reported as S6.
ORDER-LEDGER arm: `disc_evt_h30_attack_reload_lift_ordered` (present;
`disc_level_z2_attack_reload_lift_ordered` is not in the manifest).

Do not read eligibility from the snapshot row's `_seen` flag at an exact
transition. `searchsorted(..., side="left") - 1` returns the index *before*
the event (`discretionary_features.py` 2527–2528), and `state_age` returns
0.0 for both never-happened and happened-this-instant (2531–2533). Compare
`first_ts_ns` to the snapshot clock, or take the first stored Δ row whose
age is ≥ the defense event. The state series stops at formation + 601 s
(1978); a completion past that horizon is typed "truncated", not "never".

**Blocked by:** ticket 10 (S6 occupancy). Opens only if 10 shows oracle
picks over-represent S6-complete (geometry *and* defense) above the
within-cell shuffle band on TRAIN and THRESHOLD for at least one asset.
Ticket 07's letter labels which pile 08's dollars land in; it does not
gate 08.

**Status:** closed-for-scope (2026-08-22). Ticket 10 did not over-represent
S6-complete on TRAIN+THRESHOLD for any asset (HG/NKD inside the shuffle
band at every age; SI's two out-of-band ages are under-representation).
Closed FOR: S6 from existing quote/memory columns, Δ ≤ 290 s, 67 days of
2021. Does NOT close: G1, waits past the 601 s state-series stop, 2022–2025.

- [ ] `--selftest` recovers planted S6-complete names (retest + rebuild-after-depletion in window) over planted GEOMETRY-only names (retest, no rebuild) and refuses non-finite y.
- [ ] Real run on matrix 7e9e2588… writes `artifacts/entry_v2/tabular_recovery/diagnostics/confirmation_sequence_20260822.json` with S6 vs GEOMETRY vs Dawes COMBINED vs defense-shuffle, per asset and block.
- [ ] Does not freeze a Δ-grid snapshot schedule. Δ stays a reporting axis.
- [ ] CLOSES S6 for the current plane at Δ ≤ 290 s iff, on THRESHOLD and FORWARD, the S6 arm's cell-pick dollars sit inside the within-cell shuffle 95% band or do not exceed Dawes COMBINED on the same rows by more than the day-bootstrap floor. Scope the closure to "S6 from existing quote/memory columns, Δ ≤ 290 s, 2021 sample".
- [ ] Any distance this probe needs comes from ticket 09's TRAIN quantile, never from 3, 12, 18, or 2–4. Event counts (second defense, nth refresh) stay integers.
- [ ] Wall < 20 min. Abort otherwise.

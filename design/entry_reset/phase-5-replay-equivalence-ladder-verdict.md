# Phase 5 · Replay equivalence proof and ladder verdict

Back to [overview](overview.md). Blocked by phase 4.

**Goal.** The vectorized cell-pick replay is proven equal to the walk twin for a one-entry-per-phase schedule, and the best phase-4 object produces the four-column verdict per asset and held half-year through the existing ladder gate.

**Changes.** One replay module `cell_pick_replay` (one interface: schedule in, per-day dollars, trades, MDD out) used by the phase-4 tool and by the gate path; an equivalence script against the walk twin on one entry-dense day; the verdict run through `regate_policy_block` law. Demote the gate's ceiling-capture refusal clause (`RECOVERY_MIN_CEILING_CAPTURE`) to a reported field per D-110, red-first: a fixture that fails only on capture must pass after the change (encoding-goals-in-gates). Resolve the D-077 news veto: either the label already excludes release windows (cite the line) or the replay applies [−10, +10] min and the receipt says so.

**Data structures.** `CellSchedule {asset, day, phase, series, delta}`; the existing `EconomicGateResult` receipt (schema GATE2) with learner, shuffle, ceiling, rung, MDD, trades per day.

**Verification.**
- Static: `python3 -m unittest engine.entry_v2.test_cell_pick_replay` seen red first (two entries in one phase refused; 13th trade in a day refused); ladder gate tests green.
- Real path: equivalence receipt mismatches = 0 (SC-RESET-5); one gate receipt per (asset, half-year) with PASS only under the ladder law (SC-RESET-4).
- Box cost: the walk-twin day ≈ 20 min; the cell-pick replays seconds; ≤ 1 h total.

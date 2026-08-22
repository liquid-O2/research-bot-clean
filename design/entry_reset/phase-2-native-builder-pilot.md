# Phase 2 · Native builder wired, one-month pilot (2022-03, all assets)

Back to [overview](overview.md).

**Goal.** New sessions materialize through the accepted native dense builder at the chain's own call site, with the 600 s window and standalone labels, and one month proves the slice contract before anything fans out.

**Changes.** Add a Δ-grid snapshot schedule to the corpus contract (offsets {60, 180, 300, 600} s beside TRAINING and REPLAY; the config receipt changes, so only new slices carry it). Adopt the native builder behind the existing builder interface at the chain's dense-feature call site (expand beside the Python builder, differential, then the Python path stays only as the differential oracle). Pilot materialization of 2022-03 for SI, HG, NKD into a content-addressed slice root. A pilot receipt with per-session wall time. `how` over the call site first; `checking-data-contracts` on the store schema (3,505 store columns vs 1,372 disc columns).

**Data structures.** The dense session store (existing npz schema); the slice manifest {slice, asset, sessions, missing days, per-session wall seconds, builder identity, differential receipt}.

**Verification.**
- Static: `python3 -m unittest engine.entry_v2.test_disc_native_harness` and the builder-selection test seen red first (call site still on Python) then green.
- Real path: `python3 tools/diff_discretionary_native.py` on 3 pilot sessions → PASS bit-identical, mutant arm RED; pilot manifest with median wall time ≤ 4 min/session (SC-RESET-2); strict reload of the pilot store.
- Box cost: ~66 sessions × 244 series × 4 rows × 2.33 ms ≈ 2.5 CPU-min of features plus the per-session fixed costs; predicted ≤ 5 min wall at 13 workers; the pilot receipt reports the per-session fixed cost so the full-corpus one-hour bound (overview §Corpus build arithmetic) is proven before phase 3; abort at 1.5× predicted (running-evals, operating-long-runs).

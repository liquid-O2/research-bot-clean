# Phase 3 · Corpus scale-out, seven half-year slices (2022H1 … 2025H1)

Back to [overview](overview.md). Blocked by phase 2 green with its one-hour arithmetic proven (D-110).

**Goal.** The pre-H2 corpus exists at scale, one strict-reloadable content-addressed slice per half-year, each its own launch with the arithmetic written first; the seven slices together cost about one box-hour (Δ-grid rows only).

**Changes.** No code beyond phase 2; a launch note per slice (predicted sessions, predicted wall, abort rule), a slice manifest receipt, one random session re-diffed against the Python builder per slice.

**Data structures.** Slice manifest (phase 2 shape) plus `h2_open_count` (must be 0) and the calendar reconciliation {calendar days with data, sessions built, missing days named}.

**Verification.**
- Static: `python3 tools/run_all_checks.sh --fast` green before the first slice.
- Real path per slice: session count = calendar days with data; every session strict-reloads; one random session bit-identical vs Python; wall time within its predicted share of the one-hour total at 13 one-thread workers; predicted vs measured in the launch note.
- Box cost: ~2,600 sessions × 244 series × 4 rows × 2.33 ms ≈ 1.6 CPU-h of features ≈ 8 min wall at 13 workers, plus per-session fixed costs measured in phase 2; total target ≈ 1 box-hour (D-110). A slice predicted above its share returns to the user with the arithmetic and the next speed option before it runs. Forecast context is READY from 2022-02 (NKD), 2022-03 (HG), 2022-10 (SI); SI's 2022H1 slice carries typed-absent forecast context and says so in its manifest.

# Phase 9: Deepen the reusable research path

Back to [overview](overview.md) and [verification](testing.md).

## Goal

Concentrate trusted matrix access and already-shared research laws so historical probe shells can be removed without duplicating behavior or weakening receipts.

## Changes

- Route every research matrix reader through the existing strict `load_component_matrix` seam before projecting exact-age rows. Cover the direct readers in `probe_trained_accrual`, `probe_confirmation_accrual`, `probe_delay_forfeit`, `probe_feature_accrual_scan`, and any caller found by the final graph.
- Preserve the useful `DeltaRows` projection only if it still reduces caller knowledge. Remove its duplicate manifest and array-verification logic.
- Move already-shared grouping, formation, deduplication, occupancy, cash, null, rung, selection, and projection laws out of executable experiment shells into one or a few cohesive research modules. Extract only behavior with multiple real callers.
- Move tests with the kernels. Preserve receipt math and selftest behavior exactly. Historical CLI text, arms, and preregistration stay with their ledger row, not the reusable module.
- Remove core-test imports from probe files. If the tests-only `CORPUS` age grid survives phase 10, its constants must live with the production contract. Otherwise remove the branch and reversed dependency together.
- Keep experiment entry points thin and current. A completed shell with no callers becomes a phase-10 deletion candidate.
- Refresh `START_HERE.md` in the same commit when the active matrix, research-kernel, or experiment-entry architecture changes.

## Data structure

The retained research shapes are the validated `ComponentTrainingMatrix`, its exact-age projection, and typed domain values for cells, events, entries, nulls, and cash summaries. Receipt schemas stay stable.

## Static verification

- No probe opens component-matrix files or manifests directly.
- No active probe imports private names from a completed probe shell.
- The import graph has no cycle, and the longest active probe-to-matrix or probe-to-kernel path is at most six project modules, excluding tests and standard-library modules. The current graph is materially deeper.
- The deletion test for each new module shows that removing it would duplicate domain knowledge across multiple callers.

## Runtime verification

- Add a red corruption test for manifest and array hashes before converting each reader.
- Run all moved kernel tests, retained probe selftests, receipt-shape checks, and deliberate mutants.
- Compare representative old and new probe receipts byte-for-byte or field-for-field where nondeterministic metadata is excluded.
- On the largest retained matrix fixture, require loaded arrays to remain memory-mapped without an owning full-payload copy. Peak RSS growth during strict load plus exact-age projection must not exceed 256 MiB plus 10% of the matrix payload bytes.

## Exit criterion

Research code trusts one matrix seam, reusable laws live outside historical CLIs, and completed probe shells can be judged by callers instead of archaeology.

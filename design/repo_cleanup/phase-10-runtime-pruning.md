# Phase 10: Prune dead runtime and dependencies

Back to [overview](overview.md) and [verification](testing.md).

## Goal

Delete code, tests, tools, and dependencies that no retained entry point, verification path, or fresh-plan decision hold needs.

## Changes

- Recompute production, test, CLI, native-build, hook, skill, and dynamic-import graphs after phase 9.
- Land the authoritative root fast and full check against the pre-pruning tree before deleting any runtime family.
- Remove completed one-off probe shells after their ledger row, exact receipt, recovery commit, and zero-caller check pass.
- Remove the frozen neural production CLI, neural winner and adoption path, obsolete campaign scripts, and `vendor/tabfm` when the graph proves no retained caller.
- Keep the existing QRE2 builder and tabular path and the `QRSESS1` builder source as separate decision holds. Do not add a compatibility layer.
- Keep `corpus.py` only when the manifest names the exact reproduction obligation or fresh-plan decision, caller, receipt, reopening condition, and removal condition that require its full behavior. The forecast protocol is not by itself proof that the entire neural-era runtime must stay. If no bounded obligation exists at cleanup time, preserve Git recovery and delete the active module.
- Remove `ConfirmationConfig(age_grid="CORPUS")` and its probe-dependent test if no current runner selects it. If it remains, give it a real production caller and published-shard test in a later scientific plan, not this cleanup.
- Remove caller-free `engine/port_m*` generations, old Mempalace modules and tests, lab orchestration, duplicate harness utilities, unused C++ build pools, and vendor pins only after their relevant graphs and verifiers pass.
- Delete tests that exist only for deleted behavior. Preserve tests for reusable contracts, seals, hashes, matrix loading, builders, and receipts.
- Make one root check authoritative for the retained repository. Its fast and full forms may differ in cost, but both derive their inputs from the canonical manifests rather than historical paths.
- Run the Git or rebuild pre-delete oracle for every removed source, test, tool, native product, and dependency entry. Zero callers alone is not recovery proof.
- Refresh `START_HERE.md` in the same commit after each retained entry point, decision hold, or architecture statement changes.

## Commit boundaries

1. Add and prove the root fast and full check before pruning.
2. Delete completed probe shells only after phase 9 has landed their shared kernels and tests.
3. Prune neural runtime, obsolete port generations, Mempalace code, campaign tools, and vendor dependencies in separate commits by caller graph and recovery contract.
4. Keep each native builder until its own suite and decision-hold oracle pass. Removing either builder is a separate reviewed commit.

## Data structure

The runtime-retention graph records each module and dependency with entry points, static and dynamic callers, tests, artifacts, decision-hold reason, and delete proof.

## Static verification

- Every retained module and dependency has a current caller, verifier role, or named decision hold.
- Searches find no neural, Mempalace, retired port, historical probe, deleted vendor, or externalized artifact reference outside the ledger and receipts.
- Both native builders remain separate and no speculative adapter, interface, or placeholder is introduced.
- Source files meet Akita size, function, type, naming, and dependency rules after refactoring.

## Runtime verification

- Run the single root check in fast and full modes.
- Run retained Python corpus, confirmation, and matrix tests, native bridge tests, both the QRE2 and `QRSESS1` native builder suites, harness gates, and research-kernel selftests. A builder suite may leave only in the same reviewed commit that removes its decision hold.
- Exercise each retained entry point against canonical raw or manifest-resolved fixtures.
- Run a missing-dependency and missing-artifact refusal test for every retained dynamic path.

## Exit criterion

The active runtime contains only proven reusable paths and explicit decision holds. Dead campaigns, one-off shells, duplicate generations, and unused dependencies are gone.

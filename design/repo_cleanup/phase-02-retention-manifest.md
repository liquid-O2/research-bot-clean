# Phase 2: Build the retention manifest, route files, and hygiene verifier

Back to [overview](overview.md) and [verification](testing.md).

## Goal

Replace manual deletion judgment with one deterministic inventory that classifies every active, tracked, untracked, and ignored path before any destructive action. Establish the two route files that the ledger and briefing need before those documents are written.

## Changes

- Add one small repository-hygiene module that audits, plans, verifies, and later applies the manifest. Keep destructive execution path-confined and idempotent.
- Enumerate every top-level path, tracked path group, ignored root, material byte outlier, worktree, symlink, nested checkout, build tree, queue, ticket, plan, gate, transcript, memory store, and vendor pin.
- Resolve current callers, tests, importers, producer commits, raw-data identity, receipt dependencies, and harness-verifier dependencies.
- Classify each item with the retention classes in the overview. "Unresolved" is allowed during audit, but no unresolved item may enter an apply set.
- Record explicit recovery and verification for every proposed move or removal. Use Git for tracked history, a rebuild for reproducible output, a canonical destination for raw data, and an external content hash only for unique ignored evidence.
- Give every destructive entry a pre-delete oracle. The apply path accepts only a fresh `PASS` receipt produced against that entry's recorded source and hashes. A batch oracle may cover multiple entries only when the receipt enumerates every path and they share one producer, producer commit, input-hash set, and recovery contract.
- Require an explicit, validated external recovery root outside `/workspace` before bundling unique ignored evidence. Continue independent Git-recoverable and regenerable cleanup if that destination is unavailable.
- Scan old `open_work`, queue, ticket, `NEXT_ACTION`, job, lock, gate, and worktree records so no hidden work authority survives by omission.
- Create a syntactically valid `data/README.md` route file. During migration it names the current raw locations and the intended `data/raw` destination without claiming that the move has happened. Phase 5 replaces the transitional routes with the final access contract.
- Create `receipts/MANIFEST.tsv` with its final schema and seed rows for the cleanup baseline, immutable Claude handoff, and later format audit. Phase 3 adds every receipt referenced by the ledger. Phase 6 relocates and compacts the underlying evidence.

## Data structure

Each manifest entry has normalized absolute and repository-relative paths, class, owner, authority, size, hashes, caller set, producer, preservation target, recovery route, action, pre-delete oracle, oracle receipt ID and status, dependencies, and state.

## Static verification

- Every discovered path belongs to exactly one manifest entry and action.
- Destructive entries use resolved targets beneath an approved root, never a glob, broad root, symlink escape, or unresolved variable.
- No current harness pin, raw input, exact live receipt, or fresh-plan decision hold appears in a delete set.
- No destructive entry reaches `READY` or `APPLY` without a passing oracle bound to its current content hashes. A batch receipt lists every covered entry and fails if producer or input-hash contracts differ.
- The generated before and after plan is stable across two audit runs.
- Both route files parse, their current pointers resolve, and intended future destinations are labelled as migration targets rather than presented as live paths.

## Runtime verification

- Run dry-run planning twice and require byte-identical manifests and zero filesystem change.
- Corrupt a temporary manifest action or target and prove the verifier refuses it.
- Restore one tracked sample through Git, rebuild one generated sample, and resolve one ignored-evidence sample through the external-store preflight.

## Exit criterion

The verifier reports zero unclassified paths and no destructive entry without preservation, recovery, and a runnable pre-delete oracle. The data and receipt route files exist and are valid before phase 3 begins. Later phases must execute each oracle before its entry can leave the active tree.

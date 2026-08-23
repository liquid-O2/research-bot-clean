# Repository cleanup verification

Back to [overview](overview.md).

## Goal

Prove that the cleaned repository is smaller, restorable, understandable from one read, and behaviorally equivalent on every retained path. A passing test suite alone does not prove a safe deletion. Every removal also needs a recovery proof.

## Baseline receipt

Before phase 1 changes anything, record:

- HEAD, branch, `git status --short`, tracked, untracked, and ignored counts, symlinks, worktrees, and current harness diff,
- top-level and outlier byte counts, including `artifacts`, `provenance`, raw data, worktrees, Mempalace, build output, and vendor trees,
- all completed harness gates,
- current receipt hashes and the 2,788-session `QRSESS1` counts,
- current caller and import graphs for artifact roots, probes, neural runtime, Mempalace, and vendor dependencies,
- the current root regression, relevant Python suites, both QRE2 and `QRSESS1` native C++ builder suites, and reusable probe selftests.

The baseline commit excludes the pre-rebuild harness archive payload. Its current path, byte count, item hashes, and ignore rule remain explicit until phase 7 proves the external H1 contract.

The baseline is a tracked cleanup receipt. It distinguishes pre-existing user work from cleanup edits.

## Removal gate

Every removed path must have all three fields in the retention manifest:

1. Preservation: the raw destination, ledger row, exact retained receipt, source commit, or external content hash that preserves its useful state.
2. Recovery: an explicit restore or rebuild route that does not rely on the soon-to-be-deleted path.
3. Verification: an executed pre-delete oracle that proves the restored or rebuilt result and records a `PASS` receipt against the entry's current hashes.

Tracked prose normally uses Git recovery. Reproducible output normally uses rebuild recovery. Unique ignored evidence alone uses an external content-addressed bundle. Raw data moves by a manifest-verified rename or copy and is never discarded.

The destructive executor refuses an entry without a fresh passing oracle receipt. One receipt may cover a batch only when it enumerates every path and all entries share the same producer, producer commit, input hashes, and recovery contract. Sample restores remain regression checks. They never stand in for unexecuted entry oracles.

## Cross-phase static checks

- Phase 2 creates valid `data/README.md` and `receipts/MANIFEST.tsv` route files before the ledger or briefing points to them. Phase 3 resolves every ledger receipt in the manifest before exit. Phases 5 and 6 finalize the routed content without changing those authorities.
- Every phase after phase 4 refreshes `START_HERE.md` in the same commit when it changes a current fact. Phase 11 compares the final briefing against the retained manifests and runtime graph before cold-start acceptance.
- The retention verifier reports zero unclassified paths, overlapping actions, unresolved destructive targets, dangling symlinks, or active references to retired roots.
- Every destructive entry has a passing pre-delete oracle receipt bound to its recorded hashes. Batch receipts prove the shared-contract rule and enumerate all covered paths.
- Every old ticket, plan, verdict, gate, `NEXT_ACTION`, directive, queue, and work record maps exactly once to a ledger entry or an explicit disposable classification. The Claude handoff resolves to Git blob `7edf80c1ebdee6ee730ac28450c5d7bbc9d97ef3` and its recorded SHA-256 before transcript deletion.
- Every `PROJECT_LEDGER.md` receipt ID resolves through `receipts/MANIFEST.tsv`. Every manifest hash matches the current or restored file.
- `START_HERE.md` has no links to removed `.claude`, `SKILLS.md`, `CLAUDE.md`, old tickets, old plans, or retired runners.
- No production or test module imports a completed probe shell after kernel extraction.
- No retained runner defaults to a retired artifact path.
- Raw datasets exist only under `data/raw`. Generated material exists only under declared derived, scratch, external, or build roots.
- The final repository has no competing root briefing, task queue, memory authority, or archive index.
- `git diff --check` passes after each phase.

## Cross-phase runtime checks

- Run the completed Codex harness verifier and require every gate.
- For H1, prove recovery in this order:
  1. Prove that missing, manifest-mutated, and payload-mutated external archives fail.
  2. Restore the valid content-addressed harness archive into a temporary root.
  3. Require every item hash to pass.
  4. Hide the local archive.
  5. Require H1 and `install_agent_harness.py --check` to stay green.
  6. Delete the local copy.
- Run the single root project check. By the final phase it must include the retained Python suites, native bridges, both QRE2 and `QRSESS1` builder suites while both are retained, reusable research-kernel tests, receipt checks, ledger coverage, document links, and repository hygiene.
- Measure the post-refactor research graph and require at most six project modules on any active probe-to-matrix or probe-to-kernel path. On the largest retained matrix fixture, assert memory-mapped ownership and peak RSS growth no greater than 256 MiB plus 10% of payload bytes.
- Load the retained component matrix through `load_component_matrix`. Mutate a copy of its manifest and an array byte and prove both corruptions fail before a probe runs.
- Run each retained probe selftest, then run the existing mutant or red check that proves the selftest detects changed behavior.
- Restore one representative external bundle into a fresh temporary directory and verify its manifest, byte count, and receipt.
- Rebuild one representative deleted cache from raw input and the recorded producer commit. Compare its schema, source hashes, and semantic receipt.
- Recreate the two removed worktrees from their recorded commits in a temporary location and prove they are clean.
- Start an independent agent with only injected `AGENTS.md` and `START_HERE.md`. It must state the goal, hard constraints, current result, scoped failures, live assets, exact Claude handoff, later format correction, and first fresh-plan decision without opening old history.
- Run a second hygiene pass and require no filesystem or manifest change.

## Data and seal checks

- Hash and count every raw source before and after migration. Preserve dataset identity, asset and date coverage, source revision, and the seal policy.
- Never open or evaluate sealed 2025H2 outcomes. Verification may check path, manifest, hash, and exclusion logic without inspecting outcomes.
- For decision-hold derivatives, verify the receipt and restore path but do not promote the data into an active scientific plan.
- Destructive commands use resolved absolute targets from the manifest, never a broad root, unresolved variable, or glob.

## Final acceptance

The cleanup is complete only when:

- the worktree is clean after the final cleanup commit,
- all retained paths have a positive keeper reason and all deleted paths have a recovery record,
- every deleted path has an executed pre-delete oracle receipt, not only a named recovery command,
- the before and after report shows file, directory, byte, document, queue, probe-import, and dependency reductions by class,
- the root project check, harness verifier, cold-start drill, restore drill, raw-data manifest, and second idempotence pass all succeed,
- the ledger's two baseline records are immutable and no new scientific ticket or source-format assumption was introduced.

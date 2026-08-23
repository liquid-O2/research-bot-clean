# Phase 11: Prove the cleaned repository and handoff

Back to [overview](overview.md) and [verification](testing.md).

## Goal

Demonstrate that the final repository is smaller, complete, restorable, idempotent, and ready for a fresh scientific plan.

## Changes

- Generate the final retention manifest, before and after report, deletion receipt, external-store manifest, ledger coverage report, dependency graph, and document-link report.
- Refuse closure unless every deleted manifest entry names a passing pre-delete oracle receipt bound to its final pre-delete hashes. Re-run a stratified subset after cleanup to detect verifier drift. The subset supplements, rather than replaces, the complete pre-delete receipts.
- Perform a clean-checkout drill at the cleanup commit, attach the declared raw-data root and manifest-resolved decision holds, and run the authoritative checks without any retired path.
- Perform the independent one-read onboarding drill and the representative external restore and cache rebuild drills.
- Perform a final semantic refresh of `START_HERE.md` against the retained manifest, ledger, data routes, receipt routes, runtime graph, and current constraints before the cold-start drill.
- Verify the Claude handoff and cleanup-audit baseline records. Add the completed repository cleanup as a new ledger entry with commit and receipts.
- Close and reverify all Unlazy gates. After the cleanup is recorded, remove closed cleanup-plan and gate files from the active tree in a final closure commit. Their tracked text remains in Git.
- Run the hygiene apply step a second time and require no change.

## Data structure

The final cleanup receipt binds the baseline commit, cleanup commits, before and after counts, retained manifest hash, deleted-path manifest hash, external-store hash, test receipts, cold-start result, and ledger entry.

## Static verification

- The target tree matches the overview or records a specific evidence-backed exception.
- Every retained path has a positive keeper reason. Every removed path has a recovery record.
- No unclassified path, dangling link, duplicate authority, stale queue, historical default, or closed cleanup file remains.
- The final worktree is clean and `git diff --check` passes.

## Runtime verification

- Run every final acceptance item in [testing.md](testing.md).
- Run the harness verifier, root fast and full checks, strict matrix corruption checks, raw-data manifest, external restore, representative rebuild, worktree recreation, cold-start agent, and idempotence pass.
- Run both native builder suites while both QRE2 and `QRSESS1` remain active decision holds.
- Compare files, directories, bytes, root documents, queues, probe-import depth, modules, dependencies, and worktrees before and after cleanup by retention class.

## Exit criterion

All final checks pass from a clean checkout, the active tree contains no unjustified material, the exact project history is recoverable, and the next session can start a fresh scientific plan from the two immutable baseline records without reopening old tickets.

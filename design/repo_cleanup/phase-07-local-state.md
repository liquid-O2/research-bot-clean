# Phase 7: Remove old agent, memory, worktree, and generated state

Back to [overview](overview.md) and [verification](testing.md).

## Goal

Remove obsolete local systems and disposable build state after the current Codex harness and OptMem are independently proven.

## Changes

- Re-audit and remove the two clean merged worktrees through Git's worktree command, then prune worktree metadata:
  - `agent-a1cc78bb96da03dae`, recoverable at `4b2be856ceaa59ea11abe621581616f06d2d99cc`,
  - `agent-a0539baf33b1b82aa`, recoverable at `7525d265bfa41e692d44303210469f91af7bad47`.
- Remove remaining `.claude`, `.grok`, and `.opencode` authority after the current harness verifier proves equivalent intended coverage. Remove empty `.pi` state only after a caller and session audit.
- Keep `.agents`, `.codex`, `.optmem`, and every vendor file exercised by current hooks, agent definitions, skill wrappers, or the harness verifier.
- Treat `.mempalace` and `mempalace` as historical systems. Preserve each nested repository in this order:
  1. Record its base commit and refs in a Git bundle.
  2. Store tracked changes as a patch.
  3. Hash every untracked or ignored payload.
- Preserve non-repository state in a complete path, mode, symlink, and content manifest. Prove recovery in this order:
  1. Restore the bundle into a temporary root.
  2. Check out the base.
  3. Apply the patch.
  4. Unpack ignored payloads.
  5. Require the restored status and every hash to match.
- Migrate useful project outcomes to the ledger. Remove local stores, virtual environments, and backups after current Codex hooks show no caller.
- Remove `engine/target`, `.pytest_cache`, confirmed empty scratch roots, stale locks with no live owner, and other verified rebuild products.
- Before moving `archive/agent-harness-pre-20260823`, migrate H1 and the installer receipt away from their current local-directory contract. Update `tools/install_agent_harness.py`, `tools/agent_harness_verify_common.py`, `tools/agent_harness_verify_static.py`, `.codex/harness/install-receipt.json`, and their tests so the receipt identifies the external content-addressed object, manifest hash, item count, and restore verifier rather than requiring `/workspace/archive` to exist.
- Prove the revised archive check red on a missing object, a changed manifest, and a changed payload. Prove it green by restoring the external object into a temporary directory and validating every manifest entry and framed hash.
- Run H1 and `install_agent_harness.py --check` successfully with the local archive hidden. Only then remove the local archive copy and re-run every harness gate.
- Refresh `START_HERE.md` in the same commit when the live agent, memory, worktree, or recovery route changes.

## Commit boundaries

1. Land the H1 external-reference schema, installer changes, verifier tests, and failing and passing receipts before moving the local harness archive.
2. Move the harness archive in its own restore-proven commit.
3. Remove the two worktrees in a separate commit after both recreation oracles pass.
4. Externalize and remove Mempalace only after its full-state restore commit is green. Keep legacy-agent authority removal separate.
5. Remove build products, locks, and scratch state in commits grouped by one rebuild or owner contract.

## Data structure

Each local-state receipt records owner and process status, Git or content-hash recovery, bytes reclaimed, live-call verification, and recreation check.

## Static verification

- `git worktree list --porcelain` contains only intended live worktrees.
- Repository searches find no current path from `.codex`, `.agents`, active tools, or tests into removed agent or Mempalace roots.
- Every retained vendor pin appears in the verifier-resolved set or a current runtime dependency graph.
- Build, cache, lock, and empty-scratch removals are explicit manifest targets.
- The install receipt and H1 contain no required path beneath `/workspace/archive`. Their external object ID resolves through `receipts/MANIFEST.tsv`.

## Runtime verification

- Run the archive-verifier failing and passing cases before removing the local archive. Then re-run every harness gate after vendor and legacy-agent cleanup, including H1 and the real Stop hook.
- Wake, note, recall, and compaction checks prove OptMem is the only live session memory.
- Recreate each removed worktree in a temporary path and prove its commit is clean.
- Restore the complete Mempalace bundle into a temporary root and compare refs, base commit, tracked status, untracked and ignored payload hashes, modes, and symlinks.
- Rebuild Rust output and rerun its tests. Rerun Python tests after cache removal.

## Exit criterion

Only the Codex harness, its executable pins, OptMem, and active build inputs remain. Merged worktrees and competing agent or memory systems are gone and recoverable, and H1 proves the external archive without a local archive dependency.

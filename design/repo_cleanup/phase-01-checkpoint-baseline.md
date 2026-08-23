# Phase 1: Checkpoint the plan and verified harness baseline

Back to [overview](overview.md) and [verification](testing.md).

## Goal

Make the reviewed cleanup plan recoverable, then turn the completed but uncommitted Codex harness rebuild into a separate isolated baseline before cleanup edits begin.

## Changes

- Commit `design/repo_cleanup/**` as a plan-only checkpoint before requiring a clean status. Do not fold harness or cleanup implementation changes into it. Keep `.unlazy/repo-cleanup-plan/**` ignored. Hash and classify each ignored file. Preserve unique audit and review evidence through the phase-2 content-addressed route, migrate lasting decisions into the ledger, and mark reproducible gate mechanics or status logs disposable.
- Re-run `gates/harness-install.md` H1 through H10 against the current tree.
- Compare the dirty harness paths with the completed verifier's archive, skill, hook, agent, lifecycle, provenance, and idempotence receipts.
- Capture the current HEAD, branch, status, file counts, ignored roots, symlinks, worktrees, and byte inventory in a tracked cleanup baseline receipt.
- Confirm that the tracked deletions and new `.agents`, `.codex`, `vendor/agent-sources`, archive, and harness files are the intended migration. Escalate any unrelated dirty path instead of folding it into the checkpoint.
- Verify and hash `archive/agent-harness-pre-20260823`, then keep its payload as a narrowly ignored transitional input. Record it in the baseline manifest but do not stage it or add it to Git history. Phase 7 externalizes it after migrating H1.
- Commit the verified harness source, executable pins, configuration, and receipts alone. The cleanup begins in the following commit.

## Data structure

The baseline receipt records the plan-checkpoint commit, ignored Unlazy classifications and hashes, harness commit, Git identity, dirty-path classification, harness-gate evidence, size and count snapshots, and receipt hashes.

## Static verification

- The first checkpoint contains only the reviewed plan. The ignored Unlazy evidence has an explicit preservation or disposal class. The second checkpoint contains only the verified harness migration and its receipts. It contains no pre-rebuild archive payload.
- `.agents/skills` is the only repository skill authority. `.codex/hooks.json` is the only repository hook authority.
- `git diff --check` passes and no raw, scientific receipt, or Entry V2 runtime file is changed by the checkpoint.

## Runtime verification

- All harness gates pass.
- Codex discovers `plan-flow` and `implement-flow`.
- Startup, compaction, subagent, Stop-hook, and second-install lifecycle checks pass.

## Exit criterion

The reviewed plan and harness baseline have separate commits and the status is clean. Ignored Unlazy files and the ignored archive are explicit in the baseline manifest. The archive still passes H1 locally and adds no Git object. Every later cleanup change can be reviewed against the tracked plan and harness commits without claiming Git recovery for ignored state.

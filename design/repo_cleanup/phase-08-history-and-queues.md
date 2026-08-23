# Phase 8: Delete historical documents, tickets, and work queues

Back to [overview](overview.md) and [verification](testing.md).

## Goal

Remove documentation sediment and disposable planning machinery after `START_HERE.md`, `PROJECT_LEDGER.md`, Git, and the receipt manifest prove complete coverage.

## Changes

- Delete `STATE.md`, `CURRENT.md`, `README.md`, `index.md`, `DIRECTIVES*`, `HARDWARE.md`, `DATA_INVENTORY.md`, `CONTINUITY.md`, `PLAN.md`, `FINAL_PLAN.md`, `PROGRESS.md`, `PROJECT_CONTRACT.md`, journals, and old root gate files after their live facts migrate.
- Enumerate leaf targets under old `design`, `docs`, `research`, `attic`, `retirement`, `transcripts`, archive prose, provenance prose, authorities, knowledge indexes, closed gate ledgers, plans, tickets, verdicts, candidate briefs, and reread notes after source-coverage checks pass. Explicitly exclude `design/repo_cleanup/**` and `.unlazy/repo-cleanup-plan/**` until phase 11. No parent `design` or `.unlazy` directory may be a destructive manifest target.
- Delete every retired `open_work`, task queue, `NEXT_ACTION`, work query, old lab job, abandoned orchestration file, and status cursor. Keep a work file only when it belongs to the currently open cleanup or a later fresh plan.
- Keep exact proof through `receipts/MANIFEST.tsv`, not through hundreds of explanatory files. Keep tracked history through Git, not an in-repository archive.
- Update `PROJECT_LEDGER.md` with the completed migration, deleted source ranges, and recovery commit.
- Refresh `START_HERE.md` in the same commit if a conditional documentation route or current-state statement changes.

## Data structure

The history coverage map assigns each retired source path and task ID to one ledger entry, receipt ID, Git recovery reference, or explicit no-result disposal reason.

## Static verification

- Every retired document and work record appears exactly once in the coverage map.
- No remaining file points to a removed plan, ticket, queue, status cursor, directive index, archive index, or alternate briefing.
- The root has only `AGENTS.md`, `START_HERE.md`, and `PROJECT_LEDGER.md` as narrative Markdown.
- Conditional documentation exists only under `data` and `receipts` and has a sharp pointer from `START_HERE.md`.

## Runtime verification

- Before deletion, batch-restore every tracked document entry from its recorded commit into a temporary root and compare its recorded hash. Batching is valid only for entries with the same Git recovery contract. Keep a readable sample from each family as an additional audit aid.
- Run ledger and receipt-link verification after deletion.
- Repeat the cold-start agent test and confirm it does not request an old status, plan, or ticket file.
- Run OptMem wake without `CONTINUITY.md` and prove the current fallback behavior remains correct through the Codex harness.

## Exit criterion

The active tree has one briefing, one ledger, no stale work queue, and no historical document required for normal operation or replanning.

# Phase 3: Create the compact project ledger

Back to [overview](overview.md) and [verification](testing.md).

## Goal

Preserve every useful task, experiment, decision, failure, retraction, and handoff in one small readable file so old plans and tickets can disappear without inviting repeated work.

## Changes

- Create `PROJECT_LEDGER.md` as the only readable history.
- Enumerate every ticket, plan, phase, verdict, gate ledger, directive, status block, work queue, probe result, harness migration, and cleanup decision. Map every source ID exactly once to a ledger entry or an explicitly disposable non-result.
- Group mechanically related tickets into coherent attempt families, but list every absorbed source ID so coverage is checkable.
- Use visible status marks for current, closed, retracted, historical, blocked, and superseded work. A closed or retracted row includes the only condition that may reopen it.
- Preserve outcome and scope, not copied logs or large tables. Link exact proof through `receipts/MANIFEST.tsv` and tracked recovery through a commit and path reference.
- Add every receipt cited by a ledger entry to the phase-2 manifest in the same change, so no ledger row ever lands with an unresolved receipt ID.
- Record `HANDOFF-CLAUDE-20260823` exactly as Claude left it. The 2,788-session 2022-2024 cache was built, and the old plan treated it as its basis. Claude did not identify a format gap. Verify the live count with `find artifacts/cache/corpus_2022_2024/sessions -type f -name '*.bin' | wc -l`. Use the immutable source record `f24da81:START_HERE.md`, Git blob `7edf80c1ebdee6ee730ac28450c5d7bbc9d97ef3`, and SHA-256 `f24510b17d8e6d0c3be73f8fa77856c0c6e750a8c02b85746fcb682ee30286d1`. Commit `90792a6` preserves the same bytes.
- Immediately follow it with `AUDIT-QRSESS1-QRE2-20260823`: the cleanup audit found a `QRSESS1` cache, a distinct QRE2 Python contract, and no bridge or caller. The fresh plan starts from both records and chooses a source before deciding whether compatibility work is needed.
- Record the completed Codex harness rebuild separately from the Claude scientific handoff.

## Data structure

Each entry contains a stable ID and date, status mark, source IDs, attempt, outcome, scope and non-claims, receipt and hash, recovery reference, successor, reopening condition, and inherited start point.

## Static verification

- A coverage check proves every retired source ID maps exactly once and no ledger row points to a missing receipt or recovery object.
- Every retraction names the superseded claim. Every blocked row names the unresolved fact. Every closed row names its scope.
- The two baseline records are consecutive, immutable, and chronologically honest.
- The ledger contains no copied directory inventory, full diagnostic table, old work queue, or new scientific plan.

## Runtime verification

- Restore representative tracked source documents from their recorded commits.
- Verify the immutable handoff blob and SHA-256, every final diagnostic hash, and the code and cache pointers behind the format correction before any session transcript leaves the active tree.
- Give an independent agent only the ledger and ask it to identify closed work, retractions, the exact inherited state, and the first safe replanning decision.

## Exit criterion

Every useful historical fact has one ledger home, every source is accounted for, and no old ticket file is needed to avoid repeating work.

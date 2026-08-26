# Wave 3. Apply one resumable cutover

[Back to overview](overview.md)

## Goal

Apply the canonical plan in 2 hours 15 minutes with one writer. The operation must resume after interruption and converge to the same tree.

## Apply order

1. Remove proven byte duplicates, disposable caches, and scratch products.
2. Move the raw-data root and rewrite its 945 planned links as one transaction.
3. Relocate the live corpus as a separate transaction.
4. Retire migrated history, provenance, and duplicate evidence.
5. Remove dead code, tests, tools, and unused dependencies.
6. Contract the root and publish the prepared onboarding files.

Each group has one recovery contract and one transaction receipt. A narrow precondition and postcondition check brackets the group. These checks decide whether the transaction may commit. They are not whole-repository review loops.

## Failure handling

If a group fails, stop starting new destructive groups. Preserve the current receipt and recovery state. Finish collecting every defect visible in the failed cutover. Apply one repair batch, then resume the same plan. Do not regenerate actions from the partially changed tree.

Any path outside the approved plan, any proof digest mismatch, or any protected-root target stops the cutover. The path remains retained until a later plan proves it safe.

## Verification

- Confirm each transaction receipt against the exact source and destination bytes.
- Run only the affected lane after each transaction.
- Run one cutover defect sweep after all groups finish.
- Apply one final cutover repair batch.
- Run the affected lanes and one boundary proof.
- Run the same apply plan again and require a no-op receipt.

## Exit criterion

Every planned action is `verified` or explicitly retained. Recovery samples restore correctly. The second apply changes no file, link, registry row, or receipt. Wave 4 receives a frozen repository.

# Phase 6: Reduce artifacts and evidence to their durable core

Back to [overview](overview.md) and [verification](testing.md).

## Goal

Remove hundreds of GiB of generated and historical output while retaining exact proof, decision holds, and tested recovery.

## Changes

- Complete and compact the phase-2 `receipts/MANIFEST.tsv`, then move its small exact scientific and cleanup receipts into the final `receipts` hierarchy without changing their bytes.
- Resolve tests that currently treat old generated roots as live inputs. Replace hard-coded historical paths with the smallest immutable fixture or manifest-resolved decision hold before externalizing `artifacts/cache/port/entry_v2` or `artifacts/entry_v2/tabular_recovery`.
- Hash every `QRSESS1` `.bin` and sidecar before moving the cache. Its current native reader validates structure, not content, so a cache-level count or sample open is insufficient.
- Keep the `QRSESS1` source, receipt, content manifest, and native restore check as a decision hold. Move its bulk outside the active checkout.
- Preserve every final diagnostic JSON receipt and any minimal exact matrix or fixture needed to verify them. Externalize a larger current matrix only when its content manifest and strict-load restore test pass.
- Classify the cache tree, tabular-recovery tree, runs tree, durable store, context archives, and transcripts at file level:
  - delete reproducible outputs after their entry oracle or permitted shared-contract batch passes,
  - keep small exact receipts,
  - externalize unique ignored evidence only,
  - discard duplicate temporary archives after payload-hash equality,
  - retain no bulk merely because an old ticket or provenance index cites it.
- Remove historical generated-root defaults from reusable runners. Runtime configuration, not the ledger, owns current paths.
- Record external URI, byte count, content hashes, producer commit, and tested restore destination for every external object.
- Execute the pre-delete oracle for every artifact entry. Batch rebuilds only when all covered outputs share the same producer commit, input hashes, and recovery contract. A representative rebuild does not authorize unrelated outputs.
- Refresh `START_HERE.md` in the same commit whenever a live receipt, decision hold, or active artifact route changes.

## Commit boundaries

1. Land the receipt schema, minimal fixtures, generated-root path injection, and green regression tests before moving any historical input.
2. Land full content manifests and restore oracles for `QRSESS1`, component matrices, and other decision holds before their payload moves.
3. Externalize or delete each artifact family in commits grouped by one recovery contract. Keep cache, tabular-recovery, runs, durable-store, and transcript actions separable when their producers or inputs differ.

## Data structure

The receipt manifest maps a stable receipt ID to SHA-256, size, storage class, producer or source commit, active path or external URI, regeneration route, restore verifier, and ledger rows that depend on it.

## Static verification

- Every ledger receipt resolves through the manifest and every externalized payload has a full content hash, not only a structural schema.
- Current tests and runners have no hard-coded dependency on retired artifact roots.
- Generated outputs with no current caller, decision hold, unique proof, or raw-data role have delete actions.
- External bundles contain no tracked prose already recoverable from Git.

## Runtime verification

- Run the root checks before and after moving each historically hard-coded fixture.
- Restore a `QRSESS1` sample and a component-matrix sample into clean temporary roots. Verify all hashes, then exercise their native or strict readers.
- After all entry oracles pass, re-run a stratified set of deleted-output rebuilds from canonical raw input and compare schema, producer identity, and semantic receipt.
- Run a second artifact cleanup pass and require zero action.

## Exit criterion

The active checkout retains raw data, compact receipts, and explicitly justified derivatives only. Every removed byte is Git-recoverable, regenerable, duplicate, or externally content-addressed.

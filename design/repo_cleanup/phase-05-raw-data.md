# Phase 5: Canonicalize raw data and manifests

Back to [overview](overview.md) and [verification](testing.md).

## Goal

Put every immutable raw dataset under one declared `data/raw` hierarchy without losing bytes, provenance, date scope, or seal rules.

## Changes

- Inventory raw content by substance rather than current directory name. Keep current HG, NKD, and SI MBP-1 data, older raw RTY or other market sources, and any sealed raw bundle.
- Move `artifacts/reference/futures_mbp1` to `data/raw/futures_mbp1` after whole-tree manifest verification.
- Split current `data` content into raw, derived, private recovery, and scratch classes. Raw material stays under `data/raw`. Private recovery archives move to the external recovery store. Generated derivatives follow phase 6.
- Replace the transitional routes in `data/README.md` with the final conditional access contract, and create `data/manifests` as the machine-readable authority for dataset identity.
- Preserve the pre-2025H2 research window and 2025H2 seal exactly. Do not inspect sealed outcomes during migration.
- Update active code and tests to resolve the canonical raw root through one existing configuration path. Destructive operations use the manifest's resolved paths, not runtime defaults.
- Refresh `START_HERE.md` in the same commit with the final raw root, coverage, seal, and conditional data pointer.

## Data structure

Each dataset manifest contains dataset ID, class, source revision, asset and date coverage, seal status, file and byte counts, content hashes, canonical path, consumers, and producer only when derived.

## Static verification

- Every raw file appears exactly once under `data/raw` and once in a manifest.
- No raw file is listed as delete, regenerate, or external-only.
- No active code points to `artifacts/reference` or an old `data/external` raw root.
- `.gitignore` protects raw bytes while tracking manifests and the access contract.

## Runtime verification

- Compare file counts, byte counts, and content hashes before and after the move.
- Run a metadata-only open through each retained raw reader and prove sealed dates are excluded before outcome access.
- Recreate one small derived sample from the canonical raw location.

## Exit criterion

All raw bytes remain available under one root, all consumers resolve that root, and the move is hash-identical.

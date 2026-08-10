# Knowledge provenance audit contract

This directory is an isolated, generated provenance audit.  It never copies
conversation bodies, research-paper bodies, market payload, derived matrices,
or model artifacts.  It records paths, bounded identities, hashes where the
classification permits reading, byte ranges, and dispositions.

## Snapshot universe

The builder inventories these local roots without following symlinks:

1. `/home/claude/.codex` — complete metadata census; only session/history and
   lineage databases/snapshots are content-hashed.  Credentials are
   `SECRET_METADATA_ONLY` and are never opened.
2. `/home/claude/.claude/projects/-workspace` — recursive Claude workspace
   history.  JSONL is parsed locally and only line hashes/offsets are emitted.
3. `/workspace` top-level project contracts plus `docs/`, `research/`,
   `chat-plan/`, `artifacts/workflow_memory/`, `artifacts/review_logs/`,
   `artifacts/runs/`, and `artifacts/cache/`.
4. Local research inputs under `data/manual_papers/`, `data/manual_refs/`, and
   `data/research_v2/`.  Third-party content is hash-only and redistribution is
   refused.

`/workspace/data/tokens`, other raw/vendor market roots, 2026 market payload,
and this output directory are outside the content-reading universe.  Cache
payloads are metadata-only.  Paths containing a 2026 data marker are always
metadata-only, even if another rule would normally hash them.

The initial path roster defines the snapshot.  Each readable regular file is
hashed only through its recorded initial size.  Append-only growth after the
roster is therefore lawful and detectable; replacement, shrinkage, or a
changed prefix fails verification.

## Disposition gate

Every source and segment must have explicit privacy, license, authority,
redistribution, and evidence dispositions.  `UNCLASSIFIED` is forbidden.
Malformed JSONL is quarantined by byte range and hash; raw fragments are not
copied.  Conversations and reports are context, never empirical evidence by
themselves.  A proposition marked `EVIDENCE_SUPPORTED` must reference at least
one independently admissible evidence segment.  Restricted or private sources
can never be marked redistributable.

The initial proposition registry is intentionally empty: this batch proves
lossless source/segment provenance and the admission gates; it does not invent
claims from transcripts.  Later extraction must populate the frozen schema and
pass the same verifier.


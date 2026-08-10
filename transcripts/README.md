# Conversation record

`CONVERSATION.md` is the readable, provenance-linked transcript of relevant
user and assistant dialogue. It is generated from fixed byte-prefix snapshots
and records source session ID, timestamp, role, ordinal and byte range.

The readable file is not the raw authority. Complete Codex session bytes and
the recursive historical local Claude workspace tree are stored in an
encrypted private vault outside Git. No Claude service is called during
capture. Each vault manifest records:

- source path and stable source ID;
- parent/fork lineage where available;
- captured cutoff bytes;
- prefix SHA-256;
- first/last timestamps and record census;
- malformed/fragment byte ranges;
- continuation status;
- exporter version and normalized-output SHA.

Malformed streamed JSONL records are never discarded. The readable exporter
parses tolerantly, classifies every byte range, and deduplicates repeated
completed streamed items by stable identity while retaining the raw bytes in
the vault.


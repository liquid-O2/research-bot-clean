# Provenance tools

- `capture_private_transcripts.py` freezes exact source prefixes in a private
  temporary directory, streams a deterministic compressed tar into symmetric
  encryption, verifies decryption/compression, and removes plaintext.
- `export_readable_transcript.py` validates the captured Codex prefix hashes
  and emits only provenance-linked user/assistant messages, session index and
  malformed-line ledger.

Both tools are evidence utilities, not scientific runners. The capture tool
never invokes Claude; the historical Claude directory is read as ordinary
local archival data.


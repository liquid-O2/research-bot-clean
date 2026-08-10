# Workspace cutover

The cutover is authorized only when:

- encrypted transcript and Git-recovery vaults decrypt-test successfully;
- all legacy refs/worktrees restore and recheck;
- the source/knowledge inventory has zero unclassified entries;
- the clean repository passes structural, source, launcher and cold-clone
  checks;
- the clean remote contains only `main`;
- `retirement/DELETIONS.tsv` identities still match;
- `/workspace/data` and `/workspace/artifacts` retention sentinels match.

Procedure:

1. Push the final clean `main` and clone it into an empty verification path.
2. Run all payload-free clean-room checks from that clone.
3. Capture the live Codex continuation and regenerate the readable transcript;
   commit and push it before deletion.
4. Recheck every deletion target against its manifest identity.
5. Remove only the listed legacy top-level targets. Keep `data` and
   `artifacts`.
6. Copy the verified clean repository, including its `.git`, into
   `/workspace`.
7. Verify one local branch (`main`), the clean remote OID, a clean status,
   ignored external roots, task-card/transcript/recovery hashes, Rust
   compilation and launcher smoke.
8. Remove cleanroom staging/build temporaries only after the new root and
   remote match.

The old remote is not changed. Recovery uses the encrypted archives and key
listed under `provenance/`.

## Completion

Cutover completed on 2026-08-10. All 30 recursive pre-identities matched before
deletion; `/workspace/data` and `/workspace/artifacts` were retained; the new
workspace contains only the clean repository plus those two ignored external
roots. The first post-check exposed and refused a verifier bug that traversed
the retained roots. The verifier was repaired to exclude exactly those roots,
while requiring them to be directories and Git-ignored, and then passed.

The machine-readable record is [CUTOVER_RECEIPT.tsv](CUTOVER_RECEIPT.tsv).

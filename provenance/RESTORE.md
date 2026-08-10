# Restore and retirement procedure

No old branch, worktree, dirty overlay or repository path may be retired until
all checks below pass.

1. Verify the encrypted raw-session vault and export the decryption key to a
   separate user-controlled secret store.
2. Stream-decrypt
   `/workspace/data/private_project_vault/git_recovery_20260810T144900Z.tar.zst.gpg`
   with the key documented in `sessions/KEY_AND_CONTINUATION.md` into a
   private temporary directory. Verify the encrypted SHA in
   `private_raw_hashes.tsv` before extraction.
3. Verify the restored `archives/repository_all_refs.bundle` with
   `git bundle verify`.
4. Restore the bundle into a new temporary repository.
5. Run `git fsck --full` and compare every captured ref OID with
   `provenance/git/legacy_recovery/REF_SHA_MAP.tsv`.
6. Apply each dirty-worktree binary patch and authored-untracked archive to
   its documented base; verify inventory and receipt hashes.
7. Clone the clean repository from its public remote into an empty
   directory, run cold-agent orientation and all contract/secret/license/
   large-blob/link tests.
8. Verify `/workspace/data` is unchanged and externally mounted authorities
   resolve by hash.
9. Commit a retirement manifest listing every branch, worktree and path to
   remove plus its exact recovery command.
10. Perform only manifest-listed retirement. Old remote refs remain untouched
   unless a later explicit decision authorizes otherwise.

The clean-room cutover uses explicit staging and atomic renames where the
filesystem permits. Broad recursive deletion, `git reset --hard`, history
rewrite and force-push are forbidden.

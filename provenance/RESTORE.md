# Restore and retirement procedure

No old branch, worktree, dirty overlay or repository path may be retired until
all checks below pass.

1. Verify the encrypted raw-session vault and export the decryption key to a
   separate user-controlled secret store.
2. Verify the all-ref Git bundle with `git bundle verify`.
3. Restore the bundle into a new temporary repository.
4. Run `git fsck --full` and compare every captured ref OID with
   `provenance/git/REF_SHA_MAP.tsv`.
5. Apply each dirty-worktree binary patch and authored-untracked archive to
   its documented base; verify inventory and receipt hashes.
6. Clone the clean repository from its private remote into an empty
   directory, run cold-agent orientation and all contract/secret/license/
   large-blob/link tests.
7. Verify `/workspace/data` is unchanged and externally mounted authorities
   resolve by hash.
8. Commit a retirement manifest listing every branch, worktree and path to
   remove plus its exact recovery command.
9. Perform only manifest-listed retirement. Old remote refs remain untouched
   unless a later explicit decision authorizes otherwise.

The clean-room cutover uses explicit staging and atomic renames where the
filesystem permits. Broad recursive deletion, `git reset --hard`, history
rewrite and force-push are forbidden.


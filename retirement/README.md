# Retirement manifests

The final cleanup populates:

- `BRANCHES.tsv`
- `REFS.tsv` (all 121 legacy refs, including non-head namespaces)
- `WORKTREES.tsv`
- `RETENTIONS.tsv`
- `OMISSIONS.tsv`
- `DELETIONS.tsv`

Every destructive row names the exact target, pre-action identity, recovery
artifact, recovery command, authorization and post-action verification.
Directory identities recursively hash every no-follow regular-file byte plus
canonical lstat/path metadata; a nested change after the recovery freeze
therefore blocks cutover. Unlisted objects are preserved.

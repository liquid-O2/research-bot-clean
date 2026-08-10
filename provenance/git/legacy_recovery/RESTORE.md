# Git recovery vault — 2026-08-10 14:49 UTC

This vault is a read-only recovery snapshot. It does not make any file in the
source worktrees authoritative; it preserves the exact Git/ref/worktree state
so a clean-room rebuild can choose what to recover deliberately.

## Superproject

1. Restore `archives/repository_all_refs.bundle` with `git clone --mirror`.
2. Verify the restored repository with `git fsck --full --strict`.
3. Compare `git for-each-ref` with `refs/ref_map_final.tsv`; the proven restore
   is under `/workspace/data/cleanroom_work/recovery/git_recovery_20260810T144900Z_restore/mirror.git`.
4. For a worktree, check out the OID in `worktrees/<name>/head_oid.txt`.
5. Apply `staged_binary.patch` to the index, then apply
   `unstaged_binary.patch` to the working tree. The convenience
   `head_to_worktree_binary.patch` reconstructs the final tracked worktree
   directly from HEAD. `logs/patch_restore_check.tsv` proves applicability.
6. Inspect `untracked_inventory.tsv` before extracting the corresponding
   `archives/<name>_untracked_authored.tar`. Binary payload/model, cache, and
   miscellaneous untracked paths were inventoried but intentionally not copied.

`archives/git_metadata_exact.tar` additionally preserves reflogs, the active
sequencer state, linked-worktree indexes, hooks, config, and unreachable Git
objects. It is a forensic fallback, not the preferred clean restore path.

## Shallow nested gitlink

The tracked path
`research/review_records/session_e4296cb7/scratchpad_mirror/papers/meta-labeling-repo`
is a shallow repository but has no matching `.gitmodules` entry. A normal clone
of its bundle cannot infer the shallow boundary. Restore it as follows:

1. `git init --bare <destination>`.
2. Copy `nested_repos/meta_labeling/shallow` to `<destination>/shallow`.
3. From `<destination>`, run `git bundle unbundle` on
   `archives/nested_meta_labeling_all_refs.bundle`.
4. Recreate each ref in `nested_repos/meta_labeling/ref_map.tsv` with
   `git update-ref`, and set HEAD to `refs/heads/master`.
5. Run `git fsck --full --strict` and compare the restored ref map.

This exact procedure was tested successfully in
`/workspace/data/cleanroom_work/recovery/git_recovery_20260810T144900Z_restore/nested_meta_labeling/manual_mirror.git`.
The failed ordinary-clone directory is retained only as evidence of the shallow
boundary trap. `archives/nested_meta_labeling_git_metadata.tar` is its forensic
fallback.

## Scope

No market payload was semantically read or copied by this lane. Transcript
preservation belongs to the separate encrypted transcript vault and is not
duplicated here.

# Clean-room Rust code seed

Status: `PASS_CLEANROOM_CODE_SEED_NO_REMOTE`

This directory is a minimal seed copied from the clean `select-v2` worktree at
commit `ab3940bcd5b188844f84f175d367e3df7ea17446` (engine tree
`3da372c6abbd1bf0045b0961c01c60ace7df9c11`). The source worktree was clean at
copy and verification time.

Included build code is limited to `engine/Cargo.toml`, `engine/Cargo.lock`, the
tracked engine `.gitignore`, and these seven workspace crates:

- `corpus`
- `pubread`
- `labels`
- `metrics`
- `publish`
- `ledger`
- `select_v2`

No Python lab, target directory, binary, cache, Git metadata, market payload,
Claude configuration/history, or remote configuration is included. No Git
repository or remote was initialized here.

The `evidence/` tree is non-executable historical evidence. In particular, the
adapter V2 records are from a rejected RED/HOLD build and are not source or an
authority. See `evidence/README.md`.

Verification used the shared external target directory required by the
workspace, so build products are not part of this seed. The complete workspace
was checked and every test executable was compiled without running mounted-data
tests. Payload-free packages and the calendar wall were then executed: 149 tests
passed and 396 compiled tests were deferred. See `verification/README.md` and
`inventory/tests.tsv`.

`FILE_MANIFEST.tsv` lists every regular file in this seed except itself.


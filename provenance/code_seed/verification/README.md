# Verification

All commands ran from `engine/` with:

```text
CARGO_TARGET_DIR=/workspace/artifacts/cache/ctpool-a
CARGO_NET_OFFLINE=true
TMPDIR=/workspace/data/cleanroom_work/code_seed/verification/tmp
```

Results:

- `cargo metadata --no-deps --locked --offline --format-version=1`: PASS.
- `cargo check --workspace --all-targets --locked --offline`: PASS, with the
  inherited eight dead-code warnings in `corpus::reader`.
- `cargo test --workspace --no-run --locked --offline`: PASS; all 15 test
  executables compiled. This is the payload-safe verification of the complete
  locked workspace.
- `cargo test -p metrics -p ledger -p publish --lib --locked --offline`: PASS,
  144 tests.
- `cargo test -p select_v2 --test calendar_wall --locked --offline`: PASS,
  5 tests. The 2026 reader checks refuse before forming a path.

The remaining 396 tests were not executed because the inherited suite contains
mounted market/action-book readers. They are compiled and explicitly inventoried
instead of being silently skipped. No market payload was opened during this
cleanup verification.

A full-dependency `cargo metadata --locked --offline` request was also attempted.
It correctly made no network request but returned 101 because the local Cargo
cache lacks target-specific `android_system_properties v0.1.5`. The failure is
preserved in `cargo_metadata_full.stderr`; the no-dependency metadata, check, and
test compilation all succeeded offline.


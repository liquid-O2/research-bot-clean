# Inventory

- `source_keep_set.tsv` maps all 99 copied engine files to their source Git blob,
  mode, byte count, and SHA-256.
- `tests.tsv` lists all 545 `#[test]` functions. `EXECUTED_PASS` means the test
  ran in a payload-free command; `COMPILED_NO_RUN` means it was compiled but not
  executed. `payload_risk` is a conservative file-level static scan.
- `contracts.tsv` identifies the workspace, source, publication, evaluation,
  and integration-test contracts retained in the seed.

The test inventory is descriptive and does not turn a deferred mounted-data test
into evidence.


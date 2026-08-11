# PROGRESS — completion ledger (one row per FINAL_PLAN item ID; a work item is DONE only when its row says so with an evidence id)

| id | status | date | evidence_id | artifact/hash | note |
|---|---|---|---|---|---|
| M0 | DONE | 2026-08-10 | E_GOVERNANCE_OPERATOR_AMENDMENT_V1 | commit d9f52b9 | verifier PASS; all 7 sub-items done |
| M0.1-hooks | DONE | 2026-08-10 | — | /workspace/artifacts/legacy_hooks_archive_20260810 | 3 hook scripts + open_work.json archived; settings.json rewritten |
| M0.2-agents-rehome | DONE | 2026-08-10 | E_GOVERNANCE_OPERATOR_AMENDMENT_V1 | INDEX.md Repository law | full conduct list re-homed |
| M0.3-memory | DONE | 2026-08-10 | — | legacy archived; 3-file fresh memory | pointer-only law |
| M0.4-continuity | DONE | 2026-08-10 | — | 4 hooks smoke-tested (precompact scan-bound fix applied) | live mirror verified |
| M0.5-design-corpus | DONE | 2026-08-10 | — | FINAL_PLAN.md 204 lines + 5 design files | selector_v4.toml lands with M2 freeze |
| M0.6-proofs-vendor | DONE | 2026-08-10 | — | cargo check clean; 79 unit tests pass; launcher smoke PASS; verifier PASS; 3 tarballs+manifest+REGISTRY rows | clangd best-effort |
| M0.7-plan-md | DONE | 2026-08-10 | — | PLAN.md rewritten | Gate-3 hook = E_ENTRY_READINESS_V1 |
| M1 | DONE | 2026-08-11 | wp9_full625_differential_verdict | ALL GATES GREEN; 628 tests proven-fail; byte-proven vs Rust over 7.88B rows | substrate complete WP0-WP11 |
| WP0 | DONE | 2026-08-10 | — | dialect_census.tsv sha 63557a43…; 349 rows; 27.2s | exactly ZSTD×{PLAIN,RLE,RLE_DICTIONARY}, 8,726 files, 0 out-of-dialect |
| WP1 | DONE | 2026-08-10 | — | engine/cpp qr_core+qr_registry (commit 6715717); 39/39 green; 5 red-ledger mutants | STALE_DIAG ruling applied |
| WP2 | DONE | 2026-08-10 | — | qr_clock; 71 tests; 18 mutants; oracle diff EMPTY sha a36f954e…; CC-001 applied | committed with WP3 |
| WP3 | DONE | 2026-08-10 | — | qr_parquet 4,270 LOC; 42 tests; 5 mutants; 73M values/s (2.9× budget); realfile digests + 8,997/8,997 footer-stat cross-check | CC-002: Rust-differential replaces Arrow-throughput acceptance |
| WP4 | DONE | 2026-08-10 | — | qr_sources 5,405 LOC; 46 tests; 15 mutants; registry oracle s125 EXACT (raw_rth_row_count 14,761,979 + complete_group_count 2,810,589); 46.1M values/s 3-stream (1.8× budget) | RUTW (B5) deferred and WALLED; qr_core gains COLUMN_FORBIDDEN |
| WP5 | DONE | 2026-08-10 | — | qr_nbbo 3,379 LOC (1,747 module + 1,377 tests + 218 probe + 37 cmake); 36 tests; 20 red-ledger mutants; registry oracle s125 reproduced by the STATEFUL GROUP MACHINE (complete_group_count 2,810,589 + raw_rth_row_count 14,761,979); census published to tests/fixtures/nbbo_session125_census.tsv; full pass 1.65s vs 3s budget (machine's own share 0.55s) | CC-005 imbalance implemented as a composed accessor over the separate size means (zero denominator = typed missing, bounded [-1,1], sigma at WP8); derivative_null_mask + structural-zero domains + s125 sentinel_rows=0 confirmed unported/expected |
| WP6..WP11 | TODO | — | — | — | see FINAL_PLAN §6 |
| M2 | TODO | — | — | — | V4 A1..A9 + one 5-lane review |
| M2.5 | TODO | — | — | — | Q*≤Q_max gate + decomposition (after M3-R2) |
| M3 | TODO | — | — | — | R1,R2,R3,R3a,R4,R5 |
| M4 | TODO | — | — | — | W2.0..W2.13 (conditional on M3 reading) |
| M5 | TODO | — | — | — | entry-stage readiness certificate |

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
| M2 | DONE | 2026-08-11 | E_TASK_CARD_V4_FROZEN | card FROZEN (A1-A10); 5-lane review: 9 P0s + ~20 majors fixed in ONE pass; CI green; 653+13 proven tests | selector_v4.toml pinned |
| M2.5 | DONE | 2026-08-11 | — | REACHABILITY PASSED: Q*≈0.175-0.200 → $2,214/$2,404 LCB, MDD_UCB $958/$216, best cell h=2m q=2% ρ=.40; DP optimum $6,843/sess; decomposition side $1.97k + abstention $2.12k + scheduling $2.73k; observability → M3 | reading at artifacts/cache/m25/M25_READING.md |
| M3.R1+R2 | DONE | 2026-08-11 | — | THE CORPUS EXISTS: 12,139,720 action rows, 625 sessions, 461GB ×2 runs BYTE-IDENTICAL (root 3cff6449…); 9.3min vs 45min target; probe 221/221 identical | first complete lawful DecisionTape in program history |
| M3.R3-R5 | TODO | — | — | — | controls → baselines → ladder |
| M4 | TODO | — | — | — | W2.0..W2.13 (conditional on M3 reading) |
| M5 | TODO | — | — | — | entry-stage readiness certificate |
| SHEETS-V4 | DONE | 2026-08-12 | sheets_v4/STREAM_RECEIPT.tsv | tree sha 5976402af8c28c37… (run1==run2) | D-042 certificate: 22,282 sheets x 2 runs, 14 blocks, 13 sections, 0 failures; SHEET_V4_MANIFEST.json; 3 census-path defects fixed red-first (2x VALID-ZERO, 1x never-computed d_fd_ratio) |
| P-M0.0 | DONE | 2026-08-13 | — | D-048; design/PORT_M0_CENSUS_SPEC.md; approved plan | PORT program start: housekeeping (STATE/DIRECTIVES/INBOX cleared/spec frozen); IWM parked |
| P-M0.1 | DONE | 2026-08-13 | m0/repro_si2024.receipt.json | s1 MATCH FILEDATE/R1 8/8; byte-id A 167/167; substrate 2152s | 3,942 session receipts (SI 1417/HG 1551/NKD 1553 incl. warmup); integrity flags all explained; yahoo deltas ≤1% explained |
| P-M0a | DONE | 2026-08-13 | m0/census_a_cost_rollup.tsv | M0_REPORT §2 | ALL GREEN: SI $30 RT (1 tick), HG $30, NKD $55 — cost fear dead |
| P-M0b | DONE | 2026-08-13 | m0/census_b_rollup.tsv | M0_REPORT §3 | filtered medians (era ALL): SI $2,850 / NKD $2,325 (2024-25 ~$2,975) / HG $2,025; best_leg≡range identity documented; SI-NKD ret corr 0.18 |
| P-M0c | DONE | 2026-08-13 | m0/census_c_rollup.tsv | M0_REPORT §5 | walled phase-close DP medians: SI $3,341 PASS / NKD $2,672 PASS / HG $2,385 FAIL; $1k-class 38-81/day; wall binds at $900 cap |
| P-M0d | DONE | 2026-08-13 | m0/census_d_recall.tsv | M0_REPORT §7 | ANCHORED recall @$1k: SI .996 / HG .994 / NKD .986 — ALL PASS; misses tagged for G2/G3 |
| P-M0e | DONE | 2026-08-13 | PORT_M0_VERDICT.md | committed this session | SI+NKD CONFIRMED, HG deferred; §14 ruling evidence-backed |
| P-M1.spec | DONE | 2026-08-13 | — | design/PORT_M1_SPEC.md | M1.A frozen: C++ substrate + decay/fvol/levels/profile/G2-G3 prototype censuses; M1.B sketched §9 |
| P-M1a | DONE | 2026-08-13 | m1/diff/differential.receipt.json | GATE A PASS (run port-m1-cpp-diff rc=0): 4,521/4,521 sessions field-exact, 0 orphans; two-run byte identity PASS on all 5 stages (decode SI+NKD, assemble SI 2834/HG 3102/NKD 3106); 28 fixtures with red-ledger proofs MP01..MP07 | engine/cpp/qr_dbn + qr_futsess; full 3-asset 2021-25 decode+assembly 6.3 min / 1.967B records (budget 15 min); DEFECTS: spec says DBN-v3, corpus is DBN-**v1** (decoder refuses unverified versions by name); spec's "3,942 receipts" contradicts its own SI 1417/HG 1551/NKD 1553 breakdown = 4,521 (differential ran the full 4,521) |
| P-M1b | TODO | — | — | — | confirmation-decay study, pin τ* per asset (spec §2) |
| P-M1c | TODO | — | — | — | vol layer V1 + fvol HAR vs benchmarks (spec §3) |
| P-M1d | TODO | — | — | — | level ledger (D-050) + volume-profile objects (spec §4-5) |
| P-M1e | TODO | — | — | — | G2/G3 prototype union census: recall ≥99%, family retirements (spec §6) |

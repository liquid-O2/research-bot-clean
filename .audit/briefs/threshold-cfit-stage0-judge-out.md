# C Stage 0 judge verdict. Fable.

**PASS.** Every Stage 0 line in `.audit/briefs/threshold-covering-after-pivot-kill-out.md` and every guard in `.audit/briefs/threshold-cfit-stage0.md` held against the bytes. Confirmed from `.audit/threshold-cfit-stage0.json`, the published pivot tree, the stored candidate TSVs, the surviving scratch runs under `artifacts/cache/cpp/threshold-cfit-stage0/`, the committed runner, and the seams in `g1.cpp`. Not from Sol's summary. Stage 1 may fire.

Rerun the whole sweep with `python3 .audit/assert_threshold_cfit_stage0.py` (exit 0, prints `PASS all byte checks held`, days per asset [1252, 1252, 1124]; about 22 minutes of wall this session, IO-bound on the MooseFS mount while the rclone backup was reading the same tree). Provenance: the sweep script was authored by the first judge attempt after the receipt existed, is read-only, and I validated its semantics line-by-line against the committed runner before trusting its exit code; it re-derives the determinism guard, the idempotency anchors, the session choice, the projections, the manifest, the coverage, the mtime windows, and the mutant seams from disk, and it crashes loud rather than skipping a missing file.

## Schema and window

Receipt bytes: `"schema": "QRE2THRESHOLDCFITSTAGE01"`, `"status": "PASS"`, window `start_d8 20210101`, `new_tag_start_d8 20210807`, `era_start_d8 20220101`, `end_d8_exclusive 20250101`. The runner is the committed `.audit/threshold_pivot_stage0.py` unmodified: disk, HEAD, and the receipt's pinned sha all equal `3d1916cd...`, `END_D8_EXCLUSIVE = 20250101` at line 26, and the stage guard at line 1144 refuses any other constant. `asset_chain_workers 3`, build 16 workers, never 64.

## Determinism guard, every replayed day

All 1252 / 1252 / 1124 tag days had a stored candidates TSV and every one was checked: the sweep re-compared the scratch `(candidate_id, prefix_sha256, rung_mask)` sequence and row count against the stored TSV for all 3,628 asset-days — HG 272,365 candidates, NKD 281,292, SI 240,755. I also re-did three days by hand (HG/20220103, NKD/20230615, SI/20241231): projection equality holds. Pivot rows join stored candidates one row per fired rung with matching side and unique keys — verified by the sweep everywhere and by hand on SI/20220103 (14 candidates, 24 rows = popcount sum) and HG/20241231 (248 = 248). Totals 272,712 / 281,553 / 242,030 pivot rows. The runner raised `Stage0Stop` on any drift in-flight (lines 805-810), so a drift could not have been amended into this receipt.

## Idempotency, the 433 protected 2021 files

`protected_2021_files_rewritten false`, `protected_2021_rows_identical true`, 187 / 187 / 59 files. Day-level: HG 20210721 rehashes to `7b7d63d2...`, HG 20210806 `b92c3be5...`, NKD 20210806 `84d66e70...`, SI 20210806 `43166451...` — the exact bytes the pivot Stage 0 judge cited — and each equals the cfit `tag_sha256_manifest` entry. Aggregate-level: the sweep recomputes the protected-day aggregate per asset and it equals the pivot receipt anchor (`tag_sha256s[asset].aggregate_sha256`). Replayed 2021 rows equal published rows below the header (scratch vs published, sweep-verified per day; the runner separately raised on any mismatch before publishing). Protected mtimes all predate the run window 1787775298..1787777104.

## New files and the manifest

`new_files_created 1065` per asset, `existing_new_files_matched 0` (all fresh), first new day 20210808 (20210807 is a Saturday with no lock day), max day 20241231, zero files at or past 20250101 anywhere under the pivot root. New headers carry the generating window (`# QRE2G1PIVOT1 start_d8=20210101 end_d8_exclusive=20250101 d8=...`); protected files keep their original `20210807` header. `manifest.tsv` regenerated over the full tree — 1252 / 1252 / 1124 rows, per-row sha equal to disk bytes, sweep-verified — with the prior manifest shas recorded in the receipt and equal to the pivot anchors `df0c1523...` / `04fa44c8...` / `30935016...`. Era coverage: all 939 era candidate-manifest days per asset carry a tag, `missing_days []`, a superset of the locked gated denominators 197 / 194 / 191, so no gated CLEAR candidate can miss a tag at Stage 1.

## No 2025 pack opened

The hazard was live: the canonical events manifests list 155 days of 2025H1 per asset, max 20250630. The chains never saw them — each ran against a staged tree whose event manifest is windowed (`# QRE2EVENTMAN2 start_d8=20210101 end_d8_exclusive=20250101`, 1252 / 1252 / 1124 days, max 20241231) and the sweep walked every staged file: staged days equal windowed lock days, every pack is a symlink into the canonical tree, and no link exists outside the windowed manifest. 2025H2 stays sealed, 2025H1 stays unread.

## Selftest, mutants, differential

Selftest `EntryV2Candidates.PivotBirthRowsUsePreFlipStateAndExcludeFutureRows` PASS; the three C++ mutants each `KILLED` with `test_exit_code 1`; guard mutant `KILLED, refused true`, its scratch pair (`generated.tsv`, corrupted `stored.tsv`) surviving under `guard-selftest/`. Red-first-before-chains is enforced by the committed control flow, not narration: `kill_cpp_mutants` raises if a mutant stays green (line 546), restores the baseline, reruns the selftest, and all of it precedes `run_parallel_chains` (lines 1161-1176). The C++ was rerun, not rewritten: no commit touches `engine/cpp/qr_entry_v2` after the one that landed the pivot receipt, and the working tree is clean, so these are the same audited bytes; today's `g1.cpp` holds each baseline seam exactly once and no mutated remnant (sweep-verified).

Differential: the brief's "max-`raw_events` first-READY era day" resolves per the committed semantics (per asset, the first era day with `status READY` and `rows > 0` in the candidates manifest; then max `raw_events` across the three) — recomputed by hand: HG/20220103/188158 against NKD/20220103/135980 and SI/20220103/1697, exactly the receipt's session. Same scope note as the pivot judge, does not block PASS: `tag_bytes_identical true` is runner-written after the gtest exits 0; the byte equality is asserted inside the test.

## Wall and hygiene

Projection 356 / 195 / 369 s per chain; actual 533 / 446 / 501 s — the same underestimate pattern as the pivot prefix, far under the 7200 s tripwire; total wall 1796 s. Nothing outside `g1/pivot/` changed during the run window (sweep mtime scan over the full `entry_v2` tree; the concurrent rclone is a read-only backup writing locally only to its own log outside that tree). `teacher_fields_parsed []` and the runner never references a teacher path. `fit_started false`, `stage1_started false`, `pivot_lines_scored false`, `tickets_started []`, `units_started [C_STAGE0]`, and no `.audit/threshold-cfit-stage1.json` exists on disk.

## Verdict

PASS. The era tags are honest to the bytes and Stage 1 has its precondition. Stage 1 remains unstarted, as ordered; it fires on the parent's dispatch, not from this page.

# Stage 0 judge verdict. Fable.

**PASS.** Every check in `.audit/briefs/threshold-pivot-stage0-judge.md` held against the bytes. Confirmed from `.audit/threshold-pivot-stage0.json`, the published tag tree, the stored candidate TSVs, the surviving scratch outputs, and the mutant seams in `g1.cpp`. Not from Sol's summary.

Rerun the whole sweep with `python3 .audit/assert_threshold_pivot_stage0.py` (exit 0, prints `PASS all byte checks held`; about 3 minutes of wall, nearly all mtime stats over the events tree).

## Schema

Receipt bytes: `"schema": "QRE2G1PIVOTSTAGE01"`, `"status": "PASS"`. Window block matches the operative Sol brief, `start_d8 20210101`, `end_d8_exclusive 20210807`, threshold `20210721..20210807` exclusive. The parent program doc says replay through 20241231; the Sol brief Sol actually executed narrows Stage 0 to the 2021 prefix and forbids era days, and the judge checklist itself demands no 2022-2024 tags, so the narrowed window is the intended one.

## Selftest and the four mutants, red for the intended reason

- Selftest `EntryV2Candidates.PivotBirthRowsUsePreFlipStateAndExcludeFutureRows` recorded PASS. The test (`engine/cpp/qr_entry_v2/tests/test_g1.cpp` 413-456) builds two synthetic packs that differ only in the post-cutoff row at ordinal 4 (`pivot_pack`, lines 134-152), asserts candidates and the entire pivot set are equal across them, and asserts pre-flip values on a flip-down candidate: `pivot_mid2 = base+200M` at ordinal 2, `leg_start_mid2 = base` at ordinal 0, `conf_mid2 = base-200M`, `side = -1`.
- The three C++ mutants each patch exactly one seam (`.audit/threshold_pivot_stage0.py` `mutant_replacements`, lines 373-401) and each recorded `KILLED` with `test_exit_code: 1`. `post_cutoff_event_leaks_into_tag` writes `pack.rows[event_cutoff]` (the first excluded row) into `conf_mid2`, which breaks both the conf value and the cross-pack pivot equality. `leg_start_captured_after_flip` replaces the stored pre-flip `low, low_key` with the confirming `mid2, key` in the flip-down `PivotBirth`, breaking the leg-start assertions. `side_swapped_in_record` negates `birth.side`, breaking `side = -1`. The runner ran the gtest under a filter of only this test and raised on build failure before the test could run (`require_success` at line 438), so exit 1 is that test going red, and each mutation is the named defect and nothing else.
- Guard mutant: `guard_mutant_selftest` (runner lines 337-370) corrupts one `candidate_id` in a synthetic stored table and requires `compare_candidates` to raise. Receipt bytes: `"refused": true`, `"status": "KILLED"`.
- Seams are restored. Today's `g1.cpp` contains each baseline string exactly once (`pivot.side = birth.side;` line 1229, `pivot.conf_mid2 = birth.conf_mid2;` line 1236, the flip-down `PivotBirth` construction) and none of the mutated variants.

## Determinism guard held against stored candidate TSVs

Receipt records PASS per asset on `candidate_id sequence`, `prefix_sha256`, `rung_mask`, row count: HG 37873 candidates over 187 days, NKD 38304 over 187, SI 6478 over 59. I re-ran the comparison from bytes, not trust: the scratch generation outputs survived at `artifacts/cache/cpp/threshold-pivot-stage0/runs/{asset}/g1/candidates/{asset}/{d8}.tsv`, and for all 433 asset-days the (candidate_id, prefix_sha256, rung_mask) sequence and row count match the stored `artifacts/cache/port/entry_v2/g1/candidates/{asset}/{d8}.tsv` exactly. Published pivot files are byte-identical to the guarded scratch files. Per-day pivot row counts equal the stored `rung_mask` popcount sums (one row per fired rung per candidate): totals 37895 / 38351 / 6501, matching the receipt. Every pivot row joins a stored candidate with matching side and a set rung bit, keys unique.

SI's 59 days versus 187 is the lock calendar, not a gap. The canonical SI lock table has no sessions in the prefix before 20210531, and tag days equal lock days equal event-manifest days for all three assets.

## Future-mutation differential

Receipt bytes: SI 20210624, `raw_events 536771`, `tag_bytes_identical: true`, wall 0.2759s. The test (`test_g1.cpp` 458-543) loads the real pack, bumps the first post-cutoff row by one tick in a copy, regenerates, and byte-compares the affected candidate's pivot rows. The session choice recomputes from the candidate manifests as the max-raw_events first-READY day, which is exactly SI/20210624/536771. Projection arithmetic re-verified from the events manifests: 5.139e-7 s/event scales to 41.2 / 19.2 / 14.1 projected chain seconds, far under the 7200s tripwire; actual chains ran 68.7 / 53.1 / 21.0s.

Scope note, does not block PASS. `tag_bytes_identical: true` is written by the runner after the gtest exits 0; the byte equality is asserted inside the test, per affected candidate rather than whole-file. The synthetic selftest covers the whole-set equality variant across a future-row change.

## Tags exist for 20210721-20210806, no 2022-2024 days

The threshold range holds 15 session days; 20210724 and 20210731 are Saturdays with no session in the lock table or the event manifests, so 15 is full coverage. All 15 files exist per asset and rehash to the receipt's `threshold_tag_sha256s`, for example HG 20210721 `7b7d63d2...`, HG 20210806 `b92c3be5...`, NKD 20210806 `84d66e70...`, SI 20210806 `43166451...`. All 433 day files rehashed; recomputed aggregates match (`8728a393...` / `69df3673...` / `85759a26...`) and manifest file hashes match (`df0c1523...` / `04fa44c8...` / `30935016...`). Max d8 on disk is 20210806 per asset and zero files sit at or past 20210807, so no 2022-2024 tag days anywhere under the pivot root.

The hash shared by all three assets on 20210725 (`19c981bd...`) and on 20210801 (`4e9b691d...`) looked like a red flag and is benign: those Sundays produced zero candidates, the tag file is schema line plus header only, and the schema line embeds d8 but not asset, so the bytes match across assets. Verified byte-identical, two lines each.

## Stored candidate and teacher artifacts untouched

Newest file mtimes under `g1/candidates`, `g1/teacher`, `g1/receipts`, `receipts`, `locks`, `phases`, and `events` all predate the run start (receipt mtime 1787762900 minus 241s wall). A full scan of `artifacts/cache/port/entry_v2` found no file modified inside the run window outside `g1/pivot/`. Receipt bytes agree: all three `stored_*_artifacts_rewritten` flags false, `teacher_fields_parsed: []`, and the peek note says no teacher artifact is parsed in Stage 0.

## No tape histograms, no ninth field

The pivot tree holds exactly `{d8}.tsv` day files plus `manifest.tsv` per asset, nothing else. Every day file carries the closed 13-column `QRE2G1PIVOT1` header and every row exactly 13 fields; the manifest carries the closed 6-column `QRE2G1PIVOTMAN1` header. No histogram artifact exists and nothing outside the pivot tree changed during the run; the name-rules receipts (`threshold-stored-name-rules.json` 15:08, `threshold-tape-name-rules.json` 15:37) predate the run, so no ninth rule line was added. Receipt bytes: `tickets_started: []`.

## Verdict

PASS. Stage 0's receipt is honest to the bytes. Stage 1 remains unstarted, as ordered.

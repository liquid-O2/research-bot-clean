# Stage 0. Pivot-birth tag. Sol specified sequence.

`/poteto-mode` Prototype. You are Sol (`gpt-5.6-sol-max`). Do not inherit Grok.

Execute Stage 0 of `.audit/briefs/threshold-covering-after-tape-kill-out.md` only. Stop after the Stage 0 receipt. Do not start Stage 1. Do not start B, C, or D. Do not start tickets 37, 46, or 47. Do not add tape histograms. Do not rewrite stored candidate, teacher, or receipt TSVs.

Parent Grok owns Fable judgment after your receipt exists.

## Decision this stage settles

Can G1 emit its own pre-flip zigzag birth record as a `QRE2G1PIVOT1` side table, matching stored candidates, without spending a 2022-2024 era read?

## Seam

Restore C++ with `git checkout -- engine/cpp`. Restore any HEAD file the G1 build actually requires, including `engine/crates/corpus/registry/accepted_compact_sessions.tsv`. You may install missing build tools (`ninja`, cmake packages, uv pins). Prefer the user site or `/workspace/artifacts`, not overlay `/`. Build under `/workspace/artifacts/cache/cpp/` only, via the repo CMake presets. Never `/tmp`.

The one interface change is `RawZigZag::observe` at `engine/cpp/qr_entry_v2/src/g1.cpp` line 343. Return the pre-flip record alongside the side. Do not put these fields on `CandidateRow`. Existing candidate artifacts stay untouched.

Capture **before** the flip overwrites `high` / `low` / keys.

- Flip down (returned side -1). Pivot is `high` / `high_key`. Leg start is `low` / `low_key`.
- Flip up (returned side +1). Pivot is `low` / `low_key`. Leg start is `high` / `high_key`.
- `conf_mid2` is the confirming `mid2`. `threshold_mid2_raw` is the threshold passed into `observe`.

Call site around line 997. Four machines, one per rung. Emit one side-table row per fired rung per candidate.

## Side table

Schema `QRE2G1PIVOT1` at `artifacts/cache/port/entry_v2/g1/pivot/{asset}/{d8}.tsv` plus a manifest. Keyed by `candidate_id`.

Fields, closed: `candidate_id`, `asset`, `d8`, `rung_index`, `side`, `pivot_mid2`, `pivot_ts_recv_ns`, `pivot_ordinal`, `leg_start_mid2`, `leg_start_ts_recv_ns`, `leg_start_ordinal`, `conf_mid2`, `threshold_mid2_raw`.

Write generated candidates to a scratch output root. Compare them to stored `artifacts/cache/port/entry_v2/g1/candidates/{asset}/{d8}.tsv` on `candidate_id` sequence, `prefix_sha256`, `rung_mask`, and row count. Any drift is a stop, not an amend.

## Sequence

1. Selftest plus three mutants, each red before any real pack: post-cutoff event leaks into the tag; leg start captured after the flip; side swapped in the record. A fourth guard mutant corrupts one stored `candidate_id` on a synthetic day and must refuse.
2. Future-mutation differential on one session. Mutate post-cutoff pack rows in a copy. Tag bytes must be identical.
3. Generate **one** real session. Project wall for the 20210101 through 20210807 exclusive prefix (2021 THRESHOLD needs that CausalPriorState chain). If a chain projects past two hours, stop and report. Do not start 2022-2024.
4. If the projection is under two hours, generate HG, NKD, SI in parallel from 20210101 through 20210807 exclusive. 13-16 workers, never 64. Stop at the 2021 THRESHOLD block. Do not emit era days.
5. Write `.audit/threshold-pivot-stage0.json`, schema `QRE2G1PIVOTSTAGE01`. Include selftest, mutants, projection, per-asset day counts, determinism guard, tag sha256s, wall clock. Status is PASS only if tags exist for the 2021 THRESHOLD days (20210721-20210806) and every guard held.

CLI pointer: `engine/cpp/qr_entry_v2/tools/qr_entry_v2_g1.cpp` (`--stage candidates`). Event packs: `artifacts/cache/port/entry_v2/events/{asset}/{d8}.qre2`.

Estimate. Build about five minutes. One session then project. Expected 10 to 40 minutes per chain if the one-session rate holds. Tripwire at two hours.

This tag is throwaway for THRESHOLD identity. It cannot promote.

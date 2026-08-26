# Stage 0. Era pivot tags for unit C. Sol specified sequence.

`/poteto-mode` Prototype. You are Sol (`gpt-5.6-sol-max`). Do not inherit Grok.

Execute Stage 0 of `.audit/briefs/threshold-covering-after-pivot-kill-out.md` only. Stop after `.audit/threshold-cfit-stage0.json`. Do not start Stage 1. Do not fit. Do not start B, D, or tickets 37, 46, or 47. Do not score the eight pivot lines on era days. Do not rewrite 2021 tag files.

Parent Grok owns Fable judgment after your receipt exists.

## Decision this stage settles

Can the existing G1 pivot-tag runner emit 20210807 through 20241231 `QRE2G1PIVOT1` side tables, matching stored candidates, without touching 2025 packs or rewriting the 433 Stage 0 files?

## Seam

Reuse `.audit/threshold_pivot_stage0.py`. Set `END_D8_EXCLUSIVE = 20250101` and update its stage guard to exactly that constant. No 2025 event pack is opened. Do not change C++ unless a rebuild is required to run the existing tagger.

Three asset chains in parallel from 20210101, never 64 workers. `CausalPriorState` needs the full prefix.

## Guards

- Determinism: every replayed day that has a stored candidates TSV must match on `candidate_id` sequence, `prefix_sha256`, `rung_mask`, and row count. Drift is a stop, not an amend.
- Idempotency: the 433 existing 2021 day files are never rewritten. Re-emitted 2021 tag rows must match stored rows byte-for-byte below the header. Mismatch is a stop.
- New day files only for 20210807 through 20241231. Header comment carries the generating window. Loaders skip line 1. `manifest.tsv` regenerated over the full tree with the prior manifest sha recorded.
- Selftest plus the same three C++ mutants plus the guard mutant, each red before the run. Rerun them. Do not rewrite them.
- Future-mutation differential on one era session: the max-`raw_events` first-READY era day.
- No teacher byte parsed.

## Receipt

`.audit/threshold-cfit-stage0.json`, schema `QRE2THRESHOLDCFITSTAGE01`. Sources with sha256s and the per-day tag sha manifest. Status PASS only if era tags exist for the gated 2022-2024 days and every guard held.

Wall: generate one session and project. If a chain projects past two hours, stop and report. Do not start Stage 1.

This tag cannot promote.

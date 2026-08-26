# Ticket 47 launch

`/poteto-mode` Feature. Parent stays Grok 4.6 xhigh. You are Sol (`gpt-5.6-sol-max`). Specified sequence. Do not inherit Grok.

Read `poteto-mode/SKILL.md` and matching principle leaves only. Feature playbook. `how` over `build_corpus` windowing in `engine/entry_v2/corpus_build.py` and the ticket 45 runner. Architect skipped: one existing function, one frozen window, no new interface.

## Already decided

Ceiling receipt `.audit/threshold-2022-2024-ceiling.json` verdict PROCEED. Ticket 47 is the covering unit.

D-109 arithmetic is written. `.audit/threshold-ticket47-arithmetic.md`. Verdict LAUNCH. Do not rewrite it.

Ticket 45 wiring PASS. Template `.audit/run_ticket45_pilot.py`. Reuse its artifact load, cache sizing, and `build_corpus` call. Do not copy a second era walker from the teacher-cash scripts.

## What to write

Throwaway launch plus watcher under `.audit/`. Do not edit `engine/`.

1. `.audit/run_ticket47_corpus.py`
   - Call `build_corpus` once for HG, NKD, SI.
   - `maximum_d8=20241231`. `minimum_d8_exclusive` is the day before the first assembled 2022 session.
   - 2025 stays out. Refuse if any resolved day is `>= 20250101`.
   - `require_assets=("HG","NKD","SI")`.
   - Oracle path. Do not wire R6.
   - Nine-age frozen grid. Ticket 46 stays unfunded.
   - `SessionArrayCache` sized from the day's event count the way ticket 45 does, floor 16 MiB, cap 256 MiB.
   - 14 workers. HARDWARE.md 13-16. Never `nproc` 64.
   - Reuse stored G1 candidates, teachers, events, forecasts. Do not rematerialize.
   - `--selftest` on a synthetic one-day window before the era pass.
   - Receipt `.audit/ticket47-corpus.json`. Schema `QRE2TICKET47CORPUS1`. Include session counts per asset, window, wall, cache bytes, and a sample strict-reload per asset.

2. `.audit/watch_ticket47.py`
   - D-074 stage-aware tripwire armed before the first session.
   - Die loud if the named stage (materialize / assemble / publish) makes no progress for 20 minutes.
   - Write `.audit/ticket47-watch.json`.

3. Start the era pass in the background after selftest passes. Do not wait on the human.

## Done when

- Arithmetic file exists and you did not change its verdict.
- Selftest printed `selftest_ok`.
- Watcher is armed.
- Era pass is running or the receipt is already on disk.
- 2025 bytes were never opened.

## Stop

A pass here still cannot promote. The fitted instrument later gets one frozen-rule teacher-cash read. It must post HG 2000, NKD 1500, SI 1500 per asset-day, MDD under 1000, at most 12 entries, or the family dies. Promotion still needs `QRE2TABPOLICYBLOCK2`.

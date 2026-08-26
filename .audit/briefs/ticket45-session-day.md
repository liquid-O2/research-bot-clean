# Ticket 45 on a session day

Grok writes the smallest CLI change to `.audit/run_ticket45_pilot.py`, then runs one day. Parent inspects the JSON. Do not write MEMORY.md. Do not edit `engine/`. Do not refit. Do not RAW-walk. Do not peek outcome dollars. Do not rematerialize from `.qre2`.

## Day

`--asset SI --day 20221003`. Monday. Calendar `INCLUDE`. SI G1 has 1 READY candidate. QRE2 first ready is 20221002. Not a weekend. Not 20220102.

## Hours trap

The current `_run_build_corpus` uses `minimum_d8_exclusive=20220101` and `maximum_d8=DAY`. If you only change `DAY`, `build_corpus` will ingest every session from 20220102 through 20221003. That is hours. Forbidden.

The window must be exactly one day. `maximum_d8=20221003` and `minimum_d8_exclusive=20221002`.

## Receipt

Write `.audit/ticket45-SI-20221003.json`. Do not overwrite `.audit/ticket45-one-session-pilot.json`. Durable root and probe shard get matching 20221003 names.

## Done when

`python3 .audit/run_ticket45_pilot.py --asset SI --day 20221003` exits and the new receipt exists.

The receipt must record, as facts, whether these gates passed.

- G1 candidates and teacher rows are nonzero (this day has 1 candidate)
- `build_corpus` status and message
- forecast session and phase READY or a loud refuse
- `silent_skip_defect` true or false
- schema order versus the 2021 SI/20210721 reference
- wall seconds per stage

`ticket_result.passed` is true only if forecast binds READY, `silent_skip_defect` is false, `build_corpus` is PASS, and an authoritative G1 shard strict-reloads. Do not hardcode `passed=False` and a weekend blocker list.

Keep `--selftest`. Do not start ticket 47. 13-16 cores. Never `nproc` 64. Wall should be minutes. If a stage opens a `.qre2` rematerialize, stop and refuse.

## After the receipt exists

Stop.

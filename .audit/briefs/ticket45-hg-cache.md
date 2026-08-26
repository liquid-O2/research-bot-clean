# Ticket 45 HG cache resize

Grok changes only `.audit/run_ticket45_pilot.py`, then reruns HG/20221003. Parent inspects the JSON. Do not write MEMORY.md. Do not edit `engine/`. Do not refit. Do not RAW-walk. Do not peek outcome dollars. Do not rematerialize from `.qre2`. Do not start ticket 47.

## Why

`.audit/ticket45-HG-20221003.json` already bound forecast. Session READY, phase READY, `silent_skip_defect` false, 307 CLEAR READY teachers. `build_corpus` refused `session array cache capacity is insufficient`.

The script pins `SessionArrayCache` at 16 MiB. HG/20221003 has 481637 events. Planned bytes are `max_cutoff * (16 * 8 + 5)` and can reach about 61 MiB when cutoff is the full pack. That refuse is a harness cap, not a join kill.

## Change

Size the cache from the selected day's event count times 133 bytes, plus one, and never below 16 MiB. Cap at 256 MiB for this one-session pilot. Keep the one-day window.

## Command

```text
python3 .audit/run_ticket45_pilot.py --asset HG --day 20221003
```

Write `.audit/ticket45-HG-20221003-cache.json`. Leave `.audit/ticket45-HG-20221003.json` as the 16 MiB refuse. `--selftest` must still pass. 13-16 cores. Never `nproc` 64. Wall should stay minutes. If a stage opens `.qre2` rematerialize, stop.

## Done when

The new receipt exists. Record `ticket_result.passed`, `build_corpus` status, forecast gate, `silent_skip_defect`, cache capacity used, wall seconds.

Stop. Do not interpret for promotion.

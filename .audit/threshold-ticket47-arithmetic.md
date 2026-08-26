# Ticket 47 D-109 arithmetic

Written before launch. Source is the ticket 45 pilot receipt, not the 21,996-row anchor.

## Measured

`.audit/ticket45-HG-20221003-cache.json` `stages.build_corpus.wall_seconds` is 3.330954.

That pass built one HG session. 307 candidates. 481637 events. 16 workers. Oracle path. One-day window.

Sessions named by ticket 47: 2788 (931 HG, 932 NKD, 925 SI).

HARDWARE.md effective cores are 13-16. Do not use `nproc`'s 64.

## Wall

Serial-sum from that receipt: 2788 * 3.330954 / 3600 = 2.58 h.

Ticket 47 named oracle band at nine ages: 2.0-2.2 h.

D-109 cap: 6 h.

Both sit under the cap. Launch is licensed.

The measured day is a busy HG session. Thinner SI days pull the mean down. Thicker days pull it up. 2.58 h is the conservative serial-sum from this receipt, not a throughput model.

## Scope that this arithmetic covers

Window inclusive maximum 20241231. 2025 stays out. `DEVELOPMENT_END_D8` is 20250630, so a default `build_corpus` call would open 2025H1. The launch must set `maximum_d8=20241231`.

Path: proven oracle. Ticket 47 keeps R6 unwired for this launch.

Grid: frozen nine ages. Ticket 46 is not funded.

Watcher: arm D-074 before the first session.

## Verdict

LAUNCH.

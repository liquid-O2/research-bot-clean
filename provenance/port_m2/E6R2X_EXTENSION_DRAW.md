# TEACHER ROUND 2 — BLIND EXTENSION DRAW (E6R2X), committed BEFORE any day was opened

Ruling: `provenance/port_m2/ERA_NOTES_E6_R2.md` §"R2 BLIND ADJUDICATION" — *"EXTEND, don't redesign — the
instrument is right, n is not. 5 more sealed blind days, same frozen protocol, no new study."*
Protocol: `design/PORT_TEACHER_ROUND_SPEC.md` §1/§2/§3, FROZEN, unchanged. Round id `e6r2x-blind`,
day ids `E6R2X-BLIND-D1..D5`. Reader: Opus, pinned max effort, hand-only seats (R2-9).

## 1. THE DRAW RULE (pinned; it is the round-1 rule advanced, verbatim)

> "the first N BLIND-block dates, contiguous and chronological (D-036/D-058: blind is the block that
> follows study, no gap, no selection of any kind)", advanced past the days already burned.

E6's BLIND block starts 20240419 (51 session dates). Burned: 20240419 / 20240422 / 20240423 (round 1),
20240424 / 20240425 / 20240426 (round 2). The next FIVE contiguous chronological unused dates are the draw.
No vol filter, no release filter, no size filter, no discretion of any kind is applied to the blind block —
that is the point of a contiguous rule.

## 2. THE DRAWN DAYS + TAINT RECEIPT (mechanical, `used_cases.read_ledger()` / `tainted_sessions()`)

E6 dates ever shown to a reader, from the ledger at draw time:
`{20240118 STUDY, 20240320 STUDY, 20240415 STUDY, 20240416 STUDY, 20240417 STUDY, 20240418 STUDY,
20240419 BLIND, 20240422 BLIND, 20240423 BLIND, 20240424 BLIND, 20240425 BLIND, 20240426 BLIND}`.

| round day | date | dow | in shown-ledger | STUDY-tainted (SI/HG/NKD) | verdict |
|---|---|---|---|---|---|
| E6R2X-BLIND-D1 | 2024-04-29 | Mon | False | False/False/False | **CLEAN** |
| E6R2X-BLIND-D2 | 2024-04-30 | Tue | False | False/False/False | **CLEAN** |
| E6R2X-BLIND-D3 | 2024-05-01 | Wed | False | False/False/False | **CLEAN** |
| E6R2X-BLIND-D4 | 2024-05-02 | Thu | False | False/False/False | **CLEAN** |
| E6R2X-BLIND-D5 | 2024-05-03 | Fri | False | False/False/False | **CLEAN** |

Each day is registered into `USED_CASE_LEDGER.tsv` at its OWN day-open with `mode=BLIND`,
`round=E6R2X-BLIND-Dn` (the ledger's `(cid, mode)` dedup guard is live, so a re-open would refuse).

## 3. WHAT THE CONTIGUOUS RULE HANDED ME (named before opening anything, from the calendar only)

The extension block walks off the end of April into the first week of May, which is the densest
compliance week in the era. From `context.calendar_for` (the instrument's own banked calendar), not
from the world's:

Read mechanically from `context.high_impact_calendar()` at the D-077 floor (`VETO_IMPACT_FLOOR = MEDIUM`),
the exact universe the veto is scored against:

| date | rows the instrument raises |
|---|---|
| 2024-04-29 | — none — |
| 2024-04-30 | — none — |
| 2024-05-01 | ISM Manufacturing PMI 14:00Z MEDIUM (RULE_DERIVED) |
| 2024-05-02 | Initial Jobless Claims 12:30Z MEDIUM (RULE_DERIVED) |
| 2024-05-03 | **Employment Situation (NFP) 12:30Z HIGH (BANKED)** + ISM Services PMI 14:00Z MEDIUM |

Three of five days raise a flag, versus 1 of 3 in round 2 and 0 of 3 in round 1, and 05-03 is the first
**HIGH BANKED** release ever to land inside a sealed blind block in this program. The avoidance posture
will cost capacity again — that cost is the measurement, not a defect.

**CALENDAR LIMIT, NAMED SHARPLY AND CORRECTED.** I expected the 2024-05-01 **FOMC decision** to be the
headline of this block. It is **not in the instrument's calendar** — `high_impact_calendar()` raises only
ISM Manufacturing for that date. The same holds for 04-30's Employment Cost Index / Chicago PMI. So the
compliance coverage of this extension is *the instrument's calendar*, not *the world's*, exactly as the
round-2 draw §5 stated — and on 2024-05-01 that gap is large and known in advance. I record it here,
before opening the day, rather than discovering it in a post-mortem: my ±10min vetoes on 05-01 will fire
around 14:00Z and **not** around the FOMC hours, and any 05-01 seat I take late in the NY session is taken
on a day whose largest scheduled event the instrument cannot see. I will apply the avoidance posture by
hand there (D-077-UPDATE: "avoidance is preferred regardless") and say so in the journal.

## 4. WHAT IS SEALED

No S14 appendix, no outcome, no oracle object, no contrast set of ANY of these five days is opened at any
point. The fence is mechanical: `e6_round.oracle()` refuses every date `>= 20240419`.
No new study block is opened either — per the ruling, the preparation is the existing library, the
committed journals, and the unsealed round-2 adjudication.

## 5. SEAL RECEIPT (written at the final seal; no outcome knowledge)

| day | date | episodes | shortlist | TAKE | p | compliance (VETO/HELD) |
|---|---|--:|--:|---|--:|---|
| D1 | 2024-04-29 | 624 | 5 | SI-20240429-L-E51 (NY 14:02 LONG) | 0.16 | 0 / 0 |
| D2 | 2024-04-30 | 598 | 4 | SI-20240430-L-E44 (NY 14:26 LONG) | 0.17 | 0 / 0 |
| D3 | 2024-05-01 | 611 | 3 | HG-20240501-S-E85 (NY 17:33 SHORT) | 0.15 | 14 / 81 |
| D4 | 2024-05-02 | 590 | 3 | SI-20240502-L-E53 (NY 15:02 LONG) | 0.19 | 16 / 29 |
| D5 | 2024-05-03 | 487 | 3 | HG-20240503-L-E70 (NY 16:23 LONG) | 0.13 | 18 / 108 |
| **total** | | **2,910** | **18** | **5** | mean 0.16 | **48 / 218** |

Every one of the 18 shortlisted episodes carries a RIBBON_ACCESS row (C1, no exceptions — round 2's two
paying skips were unread). Every one of the 2,910 episodes carries an EPISODE_ACCESS digest-pass row under
round `e6r2x-blind`. Takes: 4 LONG / 1 SHORT (round 2 was 0/3). Probabilities span 0.04–0.19 against round
2's 0.05–0.14. Compliance flagged **266 of 2,910 episodes (9.1%)** across three release days and refused,
untouched, the largest capacity rows of two of them.

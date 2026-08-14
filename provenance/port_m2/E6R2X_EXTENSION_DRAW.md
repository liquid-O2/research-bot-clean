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

* **2024-05-01 — FOMC decision.** The largest scheduled-release object the D-077 ±10min veto has ever
  had to handle in a sealed block, and it lands mid-NY.
* **2024-05-02 — Initial Jobless Claims 12:30Z.**
* **2024-05-03 — Employment Situation (NFP) 12:30Z.**
* 04-29 / 04-30 carry no banked row (month-end on 04-30).

This is stated as a *fact of the draw*, not a preference: three of five days are release days versus
1 of 3 in round 2 and 0 of 3 in round 1. Compliance coverage will be the best this program has had, and
the avoidance posture will cost capacity again — that cost is the measurement, not a defect.

**Calendar limit, restated (unchanged from the round-2 draw §5):** the banked calendar carries BLS/FOMC/BOJ
plus rule-derived weeklies. Anything in `RELEASE_IMPACT` without a banked row does not raise a flag; the
compliance report states coverage as *the instrument's calendar*.

## 4. WHAT IS SEALED

No S14 appendix, no outcome, no oracle object, no contrast set of ANY of these five days is opened at any
point. The fence is mechanical: `e6_round.oracle()` refuses every date `>= 20240419`.
No new study block is opened either — per the ruling, the preparation is the existing library, the
committed journals, and the unsealed round-2 adjudication.

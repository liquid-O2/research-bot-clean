# TEACHER ROUND 2 — THE DRAW + COVERAGE TABLE (committed BEFORE any day was opened)

Spec: `design/PORT_TEACHER_ROUND_SPEC.md` §3 SHAPE RULING (3 STUDY vol-matched + 3 SEALED BLIND) with the
§2 revisions R2-1..R2-11. Reader: Opus, pinned max effort. Round ids `E6R2-STUDY-D1..D3`, `E6R2-BLIND-D1..D3`.
Predecessor draw: `provenance/port_m2/E6_ROUND_DRAW.md` (round 1) — its BLIND rule is reused verbatim.

## 1. THE DRAW RULE (pinned before any sheet, delta row, chart or ribbon was opened)

**STUDY (3 days) — R2-3 VOL-CLASS MATCH, applied as a filter, not as a preference.**
1. Population = the E6 STUDY block (2024-01-02..2024-04-18, 77 session dates), day-complete, 3 assets.
2. TAINT: drop every (asset, date8) carrying a STUDY row in `provenance/port_m2/USED_CASE_LEDGER.tsv`
   (one-way taint, D-035.2). Round 1's study days 20240118 / 20240320 / 20240416 are dropped.
3. VOL CLASS: keep only days whose regime label is **HIGH**, the label of the blind class. Label =
   the modal per-asset trailing-ATR14 tercile, terciles cut within E6 per asset, exactly the round-1
   instrument (`E6_ROUND_DRAW.md` §1 R2). Reproduced here: E6 STUDY = 58% LOW / 36% MID / **5% HIGH**;
   E6 BLIND = 0% LOW / 16% MID / **84% HIGH**.
4. If fewer than 3 survive, extend into E5 (2023-H2) HIGH days, era-tagged per D-059 (R2-3's escape hatch).
5. Order chronological; ties → earliest.

**The filter left exactly three days, so step 4 was never reached and no choice was made inside the pool.**
The E6 study block contains 4 HIGH days — 20240415, 20240416, 20240417, 20240418 — one of which (0416) is
round-1 study-tainted. The remaining three ARE the draw. There is no median-volume rule to apply and no
discretion left to exercise; this is the tightest draw the era admits.

**BLIND (3 days) — the round-1 rule, verbatim: "the first three BLIND-block dates, contiguous and
chronological (D-036/D-058: blind is the block that follows study, no gap, no selection of any kind)",
advanced past the days round 1 burned.** E6's BLIND block starts 20240419; 0419/0422/0423 are used, so the
next three contiguous chronological dates are **20240424, 20240425, 20240426**. Day-complete, all 3 assets.

TAINT CHECK, RUN MECHANICALLY (not asserted): `used_cases.read_ledger()` after the backfill below returns
E6 days ever shown = {20240118, 20240320, 20240416, 20240419, 20240422, 20240423}. All six drawn days
return CLEAN. Command receipt in the round journal.

**DEFECT FOUND AND REPAIRED BEFORE THE DRAW (D-035.2 violation by round 1).** The used-case ledger carried
**0 E6 rows** — round 1 read 10,078 E6 candidates across 6 days and registered none of them, so the taint
mechanism that is supposed to make this draw safe was inert and the "0419/22/23 are used" fact lived only in
prose. Repaired by backfilling all six round-1 days from their committed episode indexes via
`used_cases.record_seal` (idempotent, one-way-door check live): STUDY 1,235 + 1,470 + 2,203 and BLIND
2,240 + 1,709 + 1,221 = **10,078 rows**. The round-2 days are registered at their own day-open.

## 2. THE DRAWN DAYS

| round | date | dow | vol regime | scheduled release | SI | HG | NKD | candidates |
|---|---|---|---|---|---|---|---|---|
| E6R2-STUDY-D1 | 2024-04-15 | Mon | HIGH | — | 1,096 | 1,365 | 526 | 2,987 |
| E6R2-STUDY-D2 | 2024-04-17 | Wed | HIGH | — | 463 | 555 | 617 | 1,635 |
| E6R2-STUDY-D3 | 2024-04-18 | Thu | HIGH | **Initial Jobless Claims 12:30Z (MEDIUM)** | 438 | 646 | 498 | 1,582 |
| E6R2-BLIND-D1 | 2024-04-24 | Wed | HIGH | — | 291 | 359 | 307 | 957 |
| E6R2-BLIND-D2 | 2024-04-25 | Thu | HIGH | **Initial Jobless Claims 12:30Z (MEDIUM)** | 438 | 435 | 450 | 1,323 |
| E6R2-BLIND-D3 | 2024-04-26 | Fri | HIGH | — | 342 | 336 | 440 | 1,118 |

Episode counts are built at day open (`episode_round.py --build`) and recorded in the round journal.

## 3. COVERAGE TABLE (D-076.2/D-087 — representativeness measured, not assumed)

| dimension | E6 (128 d) | E6 STUDY block (77 d) | R2 STUDY days | E6 BLIND block (51 d) | R2 BLIND days | R1 BLIND days |
|---|---|---|---|---|---|---|
| vol regime LOW/MID/HIGH | 35/22/43% | 58/36/5% | **0 / 0 / 100%** | 0/16/84% | **0 / 0 / 100%** | 0/0/100% |
| taught class vs tested class | — | — | **MATCHED (HIGH↔HIGH)** | — | — | MISMATCHED (58% LOW study) |
| months | Jan–Jun | Jan–Apr | Apr | Apr–Jun | Apr | Apr |
| day-of-week | ~20% ea | ~20% ea | Mon, Wed, Thu | ~20% ea | Wed, Thu, Fri | Fri, Mon, Tue |
| scheduled release days | 15% | 16% | **1/3** | 14% | **1/3** | **0/3** |
| median 3-asset roster/day | 1,253 | 1,323 | 1,635 | 1,209 | 1,118 | 1,709 |
| REVERSAL-CONFIRMATION share | 89.6% | — | 88.7–92.2% | — | 85.9–91.3% | 91.6–92.4% |
| NEWS-WINDOW share | 3.8% | — | 2.1–3.9% | — | 2.3–6.8% | 1.2–2.9% |
| RECLAIM / OPEN share | 3.8% / 2.2% | — | 2.5–4.1% / 1.5–3.5% | — | 2.9–4.6% / 2.2–3.0% | 2.3–4.1% / 1.9–3.4% |
| realized session range | NOT READ | NOT READ | NOT READ (study outcomes open at day 1 by protocol) | NOT READ | **NOT READ (sealed)** | — |

**WHAT THIS DRAW FIXES AND WHAT IT CANNOT.**
1. **The round-1 handicap is gone.** Round 1 taught on a 58%-LOW study block and tested on an 86%-HIGH blind
   block — an adaptation test wearing a teaching round's clothes. Round 2 teaches on three HIGH days drawn
   from the week that ends one session before the blind block and tests on three HIGH days. Taught class =
   tested class, measured, not hoped.
2. **Adjacency is a consequence, not a choice.** The pool of untainted HIGH study days IS the final week;
   the era offers nothing else. This is named because it cuts both ways: the study days are maximally
   informative about the blind days AND maximally unrepresentative of E6 as a whole (5% of the study block).
   Nothing learned here is licensed as an era-general fact; it is licensed as a HIGH-vol-April fact.
3. **Compliance coverage improves from 0/3 to 1/3 in blind.** 2024-04-25 carries Initial Jobless Claims at
   12:30Z, so the D-077 ±10min veto (and the held-into reading) binds on real episodes in the sealed block
   for the first time in this program, and the same release is exercised in study one week earlier (04-18).
4. **The blind days are SMALLER than round 1's** (957/1,323/1,118 vs 2,240/1,709/1,221). Fewer episodes per
   day at the same per-day token envelope = more tokens per episode, which is the direction R2-1 needs.
5. **Calendar limit, named.** The committed calendar (`context.calendar_for`) carries banked BLS/FOMC/BOJ
   rows plus rule-derived weeklies. GDP-advance (2024-04-25) and PCE (2024-04-26) are in `RELEASE_IMPACT` as
   MEDIUM but have **no banked calendar row**, so they do not raise a flag. The compliance report for this
   round therefore states coverage as *the instrument's calendar*, not as *the world's calendar*.
6. Stratification used causal features only (trailing ATR14, taint, block boundary, release calendar,
   roster volume). No realized-outcome column entered the draw at any point.

## 4. WHAT IS SEALED

No S14 appendix, no outcome, no oracle object, no contrast set of ANY blind day is opened by the reader at
any point. The fence is mechanical and was hardened before the draw was committed: `e6_round.oracle()` now
refuses **every date in the E6 BLIND block** (`>= 20240419`), not just a hand-maintained list of the drawn
days — a list that must be edited every round is a list that will one round not be edited. Verified:
`--oracle`/`--contrast`/`--ep-outcomes` on 20240424 and 20240425 both refuse.

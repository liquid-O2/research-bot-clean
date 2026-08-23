# Ticket 42 — how many rows the corpus actually needs

The user asked whether the four-row grid loses anything. **It does, and the
answer is nine, not four.**

## Measured before any code was written

`confirmation.training_offsets_seconds(300)` schedules **37 ages**: every 5 s to
60 s, every 10 s to 300 s.

The union of every age any live probe reads is **nine**:
`0, 30, 60, 90, 120, 180, 240, 290, 300`. Derived from the probes' own
constants, not hand-copied — `probe_trained_accrual.DELTAS` (7),
`probe_armed_entry.AGE_GRID` (8), and the live rule's `FORM_DELTA` and
`DELTA_SEC`. All nine are on the scheduled grid, so the cut is a strict subset
and the rows it keeps are byte-for-byte the same rows.

| Grid | Kept | Factor | Row-path wall | What it costs |
|---|---|---|---|---|
| four-row | 4/37 | 9.25x | 0.49 h | breaks three live probes |
| **union of every live probe** | **9/37** | **4.11x** | **1.11 h** | **nothing we read** |
| all scheduled | 37/37 | 1.00x | 4.55 h | nothing |

## Why not four

Four would have disarmed the measurement that decided the last two days of work.
`probe_armed_entry` reads eight ages to produce the ticket-29 entry-age decay
bound, and that bound is what killed the ticket-28 hold: it showed the p90 value
falling about $0.10 per second, which extrapolates to roughly -$750 against HG's
$1,610 and made the whole rule unpriceable. A four-age corpus cannot compute it.
`probe_trained_accrual` reads seven, `probe_ceiling_split` reads the same set.

The saving four would have bought over nine is 0.6 h. Trading a decisive
diagnostic for thirty-six minutes is not a trade worth making, and it is exactly
the kind of quiet scope cut D-109 forbids.

## What nine DOES discard, stated plainly

The 5-second resolution below 60 s and the 10-second resolution between the kept
points. No live probe reads them. Recovering them means rebuilding the corpus,
which at 4.55 h is affordable but not free.

The one capability that becomes unavailable without a rebuild: measuring how
anything accrues at finer than 30-second resolution inside the first five
minutes. The accrual work (D6) sampled at 290 s and the decay bound sampled at
30-60 s steps, so nothing on the books needs it — but a future question about
the first sixty seconds would.

That is the honest cost, and it is why the grid is nine rather than four.

## How it is wired

`ConfirmationConfig.age_grid` takes `FULL` (unchanged, every scheduled offset)
or `CORPUS` (the nine). The property refuses if the requested grid is not a
subset of the schedule, so a grid that silently loses an age cannot build a
corpus that is missing rows nobody notices until a probe returns nothing.

`receipt_sha256` carries the resolved offsets, so a corpus built on the reduced
grid can never pass as a full-resolution one. Two independent paths protect
that — the field is in `asdict` and the offsets are in the receipt — and the
fixture pins both, the second by moving the grid with the field held constant.

Fixtures: `test_confirmation.CorpusAgeGrid`, four cases, mutant-verified. The
suite is 70 tests, OK; the battery is green.

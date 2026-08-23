# Ticket 40 — the off-2021 corpus: where the time actually goes

Written before any corpus build, as D-109 requires. Every number below marked
MEASURED was taken today on real 2022 bytes; the one number that is not is
labelled and must be re-measured before it is spent against.

## The user's speed option, checked

The instruction was to use the Databento C++ library because Python is slow.
Checked, and the premise does not survive contact with the measurement.

**The C++ reader already exists and is already built.** `vendor/databento-cpp`
is vendored, `engine/cpp/qr_databento` ships an MBP-1 adapter, and
`artifacts/cache/cpp/release/bin` holds 61 binaries including
`qr_futsess_decode` and `qr_futsess_assemble`. Both ran clean on 2022 Silver
today: 3 day receipts, 1,643,821 records, 192 foreign instruments dropped, zero
file failures.

**And decode is not the bottleneck in either language.** MEASURED, same three
sessions:

| Path | Rate | Per session | Full 2022-2025H1 window (~2,625 sessions) |
|---|---|---|---|
| C++ `qr_futsess_decode`, 1 worker | 8,654,119 rec/s | 0.06 s | about 2.6 min |
| C++ `qr_futsess_assemble` | — | 0.02 s | about 0.9 min |
| Python `zstandard` + `databento_dbn` | 6,346,051 rec/s | 0.11 s | about 4.8 min |

C++ is 1.4x faster, not orders of magnitude, and **both are free at this
scale**. The entire raw-to-session substrate for four years costs three and a
half minutes. Writing a new C++ reader would buy nothing.

One measurement trap worth recording: `ZstdDecompressor().decompress()` stops at
the first frame and returned 16 KB and one record, which would have made Python
look 485x slower than C++. `stream_reader(..., read_across_frames=True)` gives
the real 55 MB and 690,748 records. The wrong number was caught before it was
quoted.

## Where the time actually goes

Everything downstream of the substrate: the discretionary builder, candidate
generation, features, and the exact delayed teacher.

OptMem #92 records the discretionary builder at **about 3 min/session native
versus about 21 min in Python**. That is a remembered figure, not a receipt in
this tree, and it is the single number the whole decision turns on. It must be
re-measured on one session before anything is funded against it.

Taken at face value, against HARDWARE.md's 13.6 real cores:

| Scope | Sessions | Native CPU-hours | Wall | Python wall | D-109 |
|---|---|---|---|---|---|
| 2022-2025H1, all three assets | ~2,625 | 131 | ~9.6 h | ~67 h | **OVER** the 6 h cap |
| 2022 only, all three assets | ~750 | 37.5 | ~2.8 h | ~19 h | **UNDER** the cap |

## What this means for the speed work

The lever is not the Databento decode. It is the builder, and the native port
for it **already exists and is accepted**: R6 landed with all-store acceptance
on 2026-08-22 (145 sessions x 300 rows, `disc_native_differential_qrdisc-native-wave2_allstore300.json`,
5 differentials, 2 mutants red). Its adoption was deferred to the E1R verdict
boundary and it has never been wired into the chain (STATE.md line 61, and the
handoff's note that "R6 landed but not wired").

So the ordered speed work, cheapest first:

1. **Re-measure the builder on one 2022 session**, native and Python, and
   receipt it. Everything below is arithmetic on a remembered number until this
   exists.
2. **Wire R6 into the corpus build.** The package is accepted; wiring it is the
   difference between 9.6 h and 67 h on the full window, and between 2.8 h and
   19 h on 2022 alone.
3. Only then decide the scope, because only then is the arithmetic real.

## The decision that belongs to the user

Two fundable shapes, and the choice is a time-and-money call:

- **2022 only, about 2.8 h wall.** Inside the cap, buys roughly 250 days per
  asset against the 11-21 the current verdicts rest on, and would cut the
  standard error on the ticket-39 rule from $169-374 to something near $80.
  Enough to say whether $857-1,061 per asset-day is real.
- **2022-2025H1, about 9.6 h wall.** Over the cap by 3.6 h. D-109 forbids
  scoping the science down to fit the clock and requires the speed option to be
  named instead: here that is R6 wiring plus, if still short, parallel decode
  across assets, which the substrate already supports (`qr_futsess_decode`
  takes a worker count and ran at 1).

Nothing launches until item 1 above is receipted and the user has picked a
scope.

## Addendum, same day: R6 measured, and the full window fits

The user asked why R6 was not being used and whether 2025H1 is reachable with
it. Both answered by measurement.

**Why it was not being used: nothing was running it.** Two separate facts.

1. The built C++ tree in `artifacts/cache/cpp/release` is dated 2026-08-16 and
   R6's sources are dated 2026-08-21. The binaries predate R6 by five days.
   Rebuilt today into `artifacts/cache/cpp/r6release` (346 targets, 0 errors;
   `ninja` was missing and is now installed to `~/.local/lib/pybin/bin`).
2. More importantly, the existing instrument was measuring the wrong thing.
   `tools/time_qrdisc_row_paths.py` times `QRDISC_TAIL_FAMILIES`, which is
   wave 1: three families, lane C's assembly question. On HG/20210721 it reports
   7.20 ms/row native against the oracle's 7.10 — **0.98x, i.e. no gain** — and
   that is a true measurement of the wrong configuration. R6's shipped end state
   is `QRDISC_WAVE2_FAMILIES`: eight families AND native row assembly.

**Measured today**, `tools/time_qrdisc_wave2.py`, receipt
`diagnostics/qrdisc_wave2_rate_20260823.json`, HG/20210721, 300 rows, 20 warm-up,
one process, no profiler:

| Path | Native families | ms/row | Speedup |
|---|---|---|---|
| oracle (frozen Python) | 0 | 7.1473 | — |
| wave 1 | 3 | 7.3078 | 0.98x |
| **R6 shipped (wave 2 + assembly)** | 8 | **3.8616** | **1.85x** |

The tool refuses if `assembly_available` is false, so a run that silently fell
back to the whole-map delegate cannot be quoted as an R6 number.

**The totals.** At 21,996 rows per day-store (1,473,724 matrix rows / 67 stores;
the direct per-session count is running and will replace this anchor), against
HARDWARE.md's 13.6 real cores:

| Scope | Path | s/session | CPU-hours | Wall | D-109 |
|---|---|---|---|---|---|
| 2022-2025H1 | oracle | 157 | 114.6 | 8.4 h | over |
| **2022-2025H1** | **R6** | **85** | **61.9** | **4.6 h** | **UNDER the cap** |
| 2022 only | oracle | 157 | 32.8 | 2.4 h | under |
| 2022 only | R6 | 85 | 17.7 | 1.3 h | under |

**So the answer is yes: with R6, 2022-2025H1 fits in about 4.6 hours**, inside
the six-hour cap, and there is no reason to settle for 2022 alone. Add the
substrate at 3.5 minutes and it is unchanged.

**What this number does NOT cover, stated so it is not mistaken for the whole
build:** it is the discretionary row path only. Candidate generation, the exact
delayed teacher, and matrix assembly sit on top and are unmeasured. The
discretionary plane was the dominant cost in the 2021 build, which is why R6
was built for it, but "4.6 h" is the row path and the rest is additive.

**The blocking step before launch** is therefore R6 ADOPTION, which STATE.md
line 61 records as deferred at the E1R boundary and never taken: the roster
member, the `confirmation.py` call site, and the store transcription. The
package has its acceptance (all-store 145 sessions x 300 rows, 5 differentials,
2 mutants red). What it does not have is the wiring.

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

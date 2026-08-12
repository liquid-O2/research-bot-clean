# SHEET-V4 — what the decision sheet still cannot carry

v3 named TWO gaps here. Both walls have MOVED, and this file records the new
state honestly rather than repeating a stale refusal.

## 1 RUTW option tape — CLOSED

v3 printed a measured refusal in section 5: `qr_sources::OptionPrintReader::open`
was pinned to the IWM print corpus and the B5 tape was unreadable.

The B5 reader landed (`qr_sources::RutwPrintReader`, committed 2026-08-12), and
`qr_tape_ribbon` gained the opt-in `rutw` stream. SHEET-V4 section 5 therefore
carries the real RUTW tape: contracts, print rate, certified-sign delta flow and
size-weighted traded IV on the same five T-MINUS windows as every other flow,
plus the IWM-minus-RUTW near-ATM traded-IV spread and its innovation per closed
30-minute window (qr_ivx D6).

ONE MEASURED COVERAGE GAP REMAINS, and it is the vendor's, not ours: the B5
corpus has no file for ordinal 638 (2024-07-19). The reader refuses that
session rather than return an empty tape, the cache sweep retries without the
B5 input, and every sheet of that session prints section 5 as TYPED ABSENT
naming the vendor gap. Nothing is substituted.

## 2 Contract-level option QUOTE tape — OPEN, but DEFERRED BY COST, not by absence

v3 said "no tool can emit one contract's quote series today". That is no longer
true: `qr_w21_dump` gained

    --contract <YYYY-MM-DD>:<strike_u6>:<C|P>   one contract's quote series
    --top-k N                                   the window's most active contracts

with the same B5 work. The layer is not carried on the sheet for a COST reason
that is measured, not assumed (ordinal 600):

    one contract's session series  = 566,168 quote rows, ~25 MB, ~6.4 s to dump

The three most-active contracts of each of ~22,000 candidates is a corpus of its
own, not a sheet layer. What it needs before any cache is built is an
ORCHESTRATOR DESIGN DECISION under D-002: which SUMMARY of the continuous series
the sheet should carry — quote count, time-at-touch, the width path at what
stride, the requote latency distribution — and over what lookback. Section 6
continues to carry the print-attached NBBO state (quote-certified, strictly
prior, with the width and its 15-minute change), and its footnote now states the
true position instead of the old wall.

The same fact is machine-readable in `SHEET_V4_MANIFEST.json` under `deferred`.

## 3 Not a gap: the two channels withheld on purpose

* qr_ivx D7's spike/bleed vol STATE — its cut is the SESSION's own 80th
  percentile of |window-to-window PROXY_VOL change|, a whole-session statistic.
  Printing it mid-session would leak the rest of the day. The per-window
  channels it is built from (vol-of-vol, PROXY_VOL level and relative change)
  ARE printed.
* vendor theta and rho — CC-013 refused them on principle: the vendor's rate and
  dividend curves are an unowned model backdoor.

Both are listed in the manifest under `excluded_on_purpose`.

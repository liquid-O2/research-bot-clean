# VWAP, delta, and unfinished locations

2026-08-22. User: build the PDF locations we never emitted, build
delta, upgrade VWAP. IB is not the destination. ETH VWAP 2.5σ starts
at 18:00 and stops at 16:00, no leak.

## Problem

Ticket 11/12: finished locations already on the matrix miss 52-83% of
oracle picks. Session VWAP exists as a distance to the line only. No
sigma, no RTH VWAP, no anchored VWAP, no G1 delta-by-price, no session
CVD. Phase IB is live and not S0.

## Solution

Compute new causal columns from event packs (trades), screen them as
location families one at a time with the ticket 12 bars (keep ≥70% of
the cell-max, ≤16 names). C++ into `qr_entry_v2` only for families that
survive TRAIN. Do not remint the 1.47M matrix for the screen.

## Grilled decisions (engineering, taken)

**Daily VWAP.** User window: 18:00 ET open to 16:00 ET. Running
trade-price × size, causal to the snapshot second. Sigma is the running
volume-weighted stdev of those same trades (D-053 in
`engine/port_m1/b3_levels.py`, bands 0 / ±2.0 / ±2.5). Not ATR. Not
bar typical (H+L+C)/3. Actual prints.

**RTH VWAP.** 09:30-16:00 ET. A different clock, not a different
formula, and not "institutional". Screened alone after the ETH pilot.
Undefined before 09:30.

**What desks call VWAP.** The execution benchmark is trade-price ×
size over the session they are measured on. That is the ETH 18:00-16:00
line for this book, or the RTH line if the desk is cash hours. There
is no third formula hiding under the word institutional. Size-filtered
VWAP (only large prints) is a later experiment with a size floor from
TRAIN, not a rename of 09:30.

**Anchored VWAP, first pass.** Causal anchors only.

- ETH open 18:00 = the daily VWAP above.
- RTH open 09:30 = RTH VWAP, only defined after 09:30.
- Overnight extreme, only after 09:30 when ONH/ONL are finished:
  AVWAP from the timestamp of that extreme. No swing picker, no yearly
  open, no FOMC, no dynamic-reanchor (those repaint or leak).

**Delta.** G1 = price row of max |buy−sell| volume on the session
profile up to the snapshot. G10 = session cumulative signed volume and
its running median. Confirmation, not a location, except G1's price
row which *is* a location.

**Still later, not this pilot:** PWH/PWL, ledges/shelves, TPO singles
as prices. Pilot is ETH bands. If they miss, RTH and G1 next, not IB.

## Prior art (researching-first)

| Source | What | Verdict |
|---|---|---|
| `b3_levels.py` D-053 | causal VWAP ±2/±2.5 from trades, session+phase | **extend** into Entry V2 screen |
| `discretionary_features.py` | session VWAP line, no sigma | keep as control family |
| Book `vwap-lesson-10` | session VWAP, ±2 and ±2.5, absorption required | **adopt** window and bands |
| X / Edgeful / Nexusfi | RTH 09:30-16:00 as a second clock | **adopt** as RTH VWAP, not "institutional" |
| Execution-desk VWAP | trade×size over the session they are scored on | **already** the ETH 18:00-16:00 recipe |
| X @alphatrends | AVWAP vs time MA on futures | **adopt** volume weight |
| X dynamic swing AVWAP | re-anchor on unconfirmed swings | **skip** (lookahead / most X will not work) |
| X yearly / ATH AVWAP | swing grain | **skip** this entry grain |
| Ticket 11 `session_vwap` | line only, ret 0.57 HG / 0.38 NKD / 0.62 SI | control, not the 2.5σ family |

## Two shapes (design it twice)

**A. Sidecar probe.** EventPack trades → causal VWAP/sigma at each
matrix row's snapshot. Screen with ticket 12 bars. No matrix remint.

**B. C++ columns in qrdisc.** New `disc_eth_vwap_{2,2_5}_aligned_usd`
in the native builder, remint dense, then the 2021 matrix.

Taken: **A for the screen.** B only if a family keeps ≥70% of TRAIN
oracle with ≤16 names. Caller:

```
flag = at_band(mid, vwap, sigma, k=2.5, theta_usd)
shrink, ncell, occupancy = score_mask(flag, y, cell, day)
```

Leak invariant: VWAP(snapshot) uses only `receive_session_sec <= snapshot`
and `sec < 79200`. A fixture that injects a later print must not move
the number.

## Acceptance scenarios

- **SC-VWAP-1** Given trades at sec 0..100 and a print at sec 200,
  When VWAP is asked at snapshot 100, Then it equals the VWAP of
  0..100 only. Rejects: using sec > snapshot (leak).
- **SC-VWAP-2** Given a planted winner sitting on the +2.5σ band,
  When the ETH-2.5 family is scored, Then pick_rate > 0.99 and
  shrink equals cell-max. Rejects: NaN y.
- **SC-VWAP-3** Given the frozen 2021 matrix and 2021 event packs,
  When the ETH 2.0 and 2.5 families run on TRAIN, Then the receipt
  publishes shrink, retained_fraction, ncell, occupancy vs shuffle,
  per asset. FORWARD of a TRAIN survivor is reported unused as a
  knob. 2021 cannot promote.

## Out of scope

Exits, size, generator, neural, 2025H2, phase IB as the selector,
dynamic swing AVWAP, yearly AVWAP, reminting the combined matrix
before a family survives.

## Next implementation step

Ticket 13: ETH 18:00-16:00 VWAP ±2 and ±2.5 screen on event packs.

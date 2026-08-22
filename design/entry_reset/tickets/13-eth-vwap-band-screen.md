# 13: ETH VWAP 2σ and 2.5σ location screen

**What to build:** a read-only probe. From event-pack trades, causal
session VWAP and volume-weighted sigma from 18:00 to min(snapshot, 16:00).
A name sits at the 2.0 (resp. 2.5) family when its mid is within TRAIN
winner MAE of either the +kσ or −kσ line. Score like ticket 12: shrink-
ceiling, retained_fraction, median names, occupancy vs shuffle. Line-only
session VWAP from the matrix is the control.

**Blocked by:** tickets 11 and 12 (θ, bars, occupancy helpers).

**Status:** landed (2021 diagnostic; cannot promote)

- [x] `--selftest` leak fixture: a print after snapshot does not move VWAP.
      Planted +2.5σ winners recover pick_rate > 0.99. NaN y refused.
- [x] Real run writes
      `artifacts/entry_v2/tabular_recovery/diagnostics/eth_vwap_band_screen_20260822.json`
- [x] TRAIN letter is majority-and-cut or `no majority-and-cut filter`
- [x] 16:00 clip is in the receipt as `eth_vwap_end_sec = 79200`
- [x] Wall < 20 min on 2021 event packs + matrix

Receipt sha256 `cd25d696e9f2ee6e03809d16c6b7e643dd6a41953f9dccb1cef5267ef82939e7`.
TRAIN tight letter: `no majority-and-cut filter` on HG, NKD, SI.
ETH ±2.5σ is sparse (median 0-1 names) and keeps only 24-29% of the
oracle. ETH ±2 SI TRAIN 68% / 6 names, just under the 70% bar. Line
matches ticket 11 session_vwap. Next is RTH as RTH (ticket 14), then
G1/G10 (ticket 15), not IB.

**Verify:**

1. [selftest] → `python3 tools/probe_eth_vwap_band_screen.py --selftest`
2. [real] → `OMP_NUM_THREADS=1 python3 tools/probe_eth_vwap_band_screen.py --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix --events-root artifacts/cache/port/entry_v2/events --out artifacts/entry_v2/tabular_recovery/diagnostics/eth_vwap_band_screen_20260822.json`

# 17: Location as a watch, then a candidate

**What to build:** a read-only probe. A location event opens a
watch. Keep frozen G1 names whose formation falls in that window.
Reversal: through the level and back (the V). Continuation: after
the break, still through. Families one at a time. Not
|aligned_usd| ≤ θ at formation price (ticket 11, already empty).

Generator is zigzag reversal only (`g1.cpp` RawZigZag, four ATR
rungs). Continuation is a selection window on those zigzags, not a
new birth family. "IV low" is prior VAL. IB low is a sibling,
screened alone.

On-matrix first slice (component matrix has no entry mid, so prior
VAL tape windows cannot run yet):

- `ib_v_reclaim`: opposing IB break seen and currently inside IB
- `ib_break_hold`: directional IB break seen and not reentry
- `ib_formed_after_break`: directional IB break seen and
  min_alert_age_sec ≤ directional_break_age_sec
- `value_v_reclaim`: opposing escape time fraction > 0 and inside
  phase value (live; tagged live)
- `value_break_hold`: directional escape current and not failed
  directional auction (live)
- `value_formed_after_escape`: directional escape episodes > 0 and
  min_alert_age_sec ≤ directional_escape_age_sec (live)

Bars: TRAIN retained_fraction ≥ 0.70 and median names ≤ 16.
Shrink vs the per-asset rung. Occupancy vs 200-draw within-cell
shuffle. 2021 cannot promote.

**Blocked by:** tickets 12 and 16 path-dedup can run in parallel.
This ticket does not wait on 16.

**Status:** landed

- [x] `--selftest` plants IB V on winners (pick_rate > 0.99),
      y-independent noise inside shuffle, NaN y refused
- [x] Real run writes
      `artifacts/entry_v2/tabular_recovery/diagnostics/location_watch_20260822.json`
      schema `QRE2LOCWATCH1` sha256
      `469156df3b3ec3493391909f76101068aff13fca6137385f2abcbe39baffc207`
- [x] TRAIN letter `no majority-and-cut filter` all assets

**Verify:**

1. [selftest] → `python3 tools/probe_location_watch.py --selftest`
2. [real] → `OMP_NUM_THREADS=1 python3 tools/probe_location_watch.py --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix --out artifacts/entry_v2/tabular_recovery/diagnostics/location_watch_20260822.json`

**What it printed (TRAIN, 2021). Cannot promote.**

The V (through then back) as a keep-filter on existing G1 names
deletes winners. `ib_v_reclaim` ret 0.28/0.20/0.45 HG/NKD/SI,
occupancy inside shuffle, shrink $833/$406/$1160. Live
`value_v_reclaim` the same class. Continuation through IB
(`ib_break_hold`) is empty (ncell 0). `ib_formed_after_break` is a
fat net (38-46 names). Live value-break-hold HG $2005 ret 0.68
just under majority, pick_rate 0.06, not S0. Prior-VAL tape
windows remain unbuilt: no `entry_mid2` on this matrix.

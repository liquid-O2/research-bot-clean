# 12: Oracle-retention filters (keep the cell-max, cut the names)

**What to build:** a read-only probe on the frozen 2021 matrix. For each
filter, publish the remaining-pool oracle (shrink-ceiling) next to the
unfiltered cell-max, median names left, and occupancy vs shuffle. Then
publish leftover anatomy: of the cell-oracle picks that sit at *none* of
the finished location families from ticket 11, which on-matrix aligned
column they sit nearest.

The question is not "which family has the biggest shrink." Ticket 11's
TRAIN-best was session LVN because it barely cuts. The question is which
filter keeps **most of the oracle dollars** while actually reducing the
cell.

**Bars, written before the run (TRAIN only):**

- Majority kept: `retained_fraction >= 0.70`
- Proper cut: `median_eligible_per_cell <= 16` and
  `frac_cells_everybody < 0.50`
- Rank survivors by TRAIN shrink-ceiling vs the per-asset rung
- A filter that keeps everyone or nobody is typed GATE-DEFECT, not a
  finding
- 2021 cannot promote. FORWARD of a TRAIN survivor is the untouched check

**Filters, one at a time (no stack except the one labeled UNION):**

Finished location (from ticket 11, plus session IB): `pdh_pdl`,
`prior_vah_val`, `prior_lvn`, `ib_session`.

Extra on-matrix location: `prior_hvn`, `session_hvn`, `session_tpo_poc`.

Non-location, on-matrix: `outside_prior_value` (book: inside value is a
wait), `first_third_phase_clock` (winners form early; formation time =
elapsed − age), `ib_phase_complete_and_at` (finished first hour of the
phase only).

UNION (labeled, not a null of location): OR of the finished set.

Live families from ticket 11 stay in the table as live, not as S0:
`ib_high_low` (phase, moving until 3600 s), `session_vwap`,
`session_lvn`.

**Leftover anatomy:** fraction of cell-oracle picks at none of the
finished set; nearest extra aligned column among those leftovers;
when the winner is *not* at a filter, remaining-max / cell-max (how
much of that cell's oracle the filter still keeps via a runner-up).

**Gaps, untested, not nulls:** PWH/PWL, ONH/ONL, VWAP 2-sigma and
2.5-sigma, ledges/shelves, multi-day untouched, G1 delta-by-price,
G10 CVD. C++ if no on-matrix filter survives the bars.

**Blocked by:** ticket 11 (family names and θ).

**Status:** landed

- [x] `--selftest` plants winners on `prior_hvn` and recovers pick_rate
      > 0.99; leftover_frac ≈ 0 when winners are planted on a finished
      family and ≈ 1 when nothing is planted; NaN y refused
- [x] Real run writes
      `artifacts/entry_v2/tabular_recovery/diagnostics/oracle_retention_filters_20260822.json`
- [x] TRAIN letter is the survivor list or `no majority-and-cut filter`
- [x] Wall < 20 min

**Verify:**

1. [selftest] → `python3 tools/probe_oracle_retention_filters.py --selftest`
2. [real] → `OMP_NUM_THREADS=1 python3 tools/probe_oracle_retention_filters.py --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix --out artifacts/entry_v2/tabular_recovery/diagnostics/oracle_retention_filters_20260822.json`
3. [receipt] → schema `QRE2ORCRET1`, sha256
   `efc438adfd5d7a5cbd6d21da8a3631d51ef002204dcf7743a428e443d4071bd4`

**What it printed (TRAIN tight, 2021). Cannot promote.**

Leftover of finished locations (PDH/PDL, prior VAH/VAL, prior LVN,
session IB): 83% HG / 73% NKD / 52% SI of cell-oracle picks sit at
none of them. Nearest extra column among leftovers is live session HVN
(a fat net). Extra families within θ catch only 39-54% of leftovers.

Letters: HG `ib_high_low` (live, $2137, ret 0.73, 8 names). SI
`first_third_phase_clock` ($2417, ret 0.94, 13 names, pick 0.67 outside
shuffle). NKD `no majority-and-cut filter` (phase IB ret 0.68 at 15
names, just under 0.70).

`first_third` uses `disc_fvol_phase_scope_elapsed_sec`, not session
elapsed. It keeps the oracle because winners form early under a
phase-close exit. That is the time-remaining confound as a gate, not a
location. HG TRAIN median names 18, so it fails the ≤16 cut on TRAIN
and is not a HG survivor even though FORWARD is 14 names.

Finished union ret 0.64 / 0.58 / 0.67, 11-16 names. Close to majority,
occupancy chance. Complete-only phase IB drops HG to ret 0.54.

Live VAH/VAL survives the bars on HG and SI. The book forbids live
VAH/VAL as S0. Tagged live, not a selector.

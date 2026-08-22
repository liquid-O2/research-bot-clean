# 11: Location family screen (which finished levels keep the winners)

**What to build:** a read-only probe that scores location *families one at a
time* on the frozen 2021 matrix. For each family, report the shrink-ceiling
(sum over cells of max y among names sitting at that family) and the
oracle-pick occupancy versus a within-cell shuffle. Rank families on TRAIN
shrink-ceiling. THRESHOLD and FORWARD of the TRAIN-best family are the
untouched check. Do not stack families into one gate on this ticket. Do not
call a null because one stack at one width missed.

A name sits at a family when the smallest absolute `_aligned_usd` among that
family's columns is ≤ θ. θ is TRAIN winner MAE in own dollars: tight =
median, wide = p75, from ticket 09. Knobs from TRAIN only.

**Families on the matrix (verified names):**

- `pdh_pdl`: prior session high/low (`disc_prior_high_aligned_usd`,
  `disc_prior_low_aligned_usd`). This is yesterday's range, not a week.
- `prior_vah_val`, `prior_lvn`
- `ib_high_low` (initial-balance edges). These columns are
  `disc_ib_phase_*`. That high/low is still moving until 3600 s after
  phase open (`discretionary_features.py:1063-1104`).
- `session_vwap` (distance to session VWAP only)
- `session_lvn`
- Controls, expected weaker: `prior_poc`, `session_vah_val` (live value)

**Gaps, typed in the receipt, not tested, not called null:**

- PWH / PWL and PMH / PML
- Multi-day untouched PDH/PDL (last N session highs/lows still untraded)
- VWAP ±2σ and ±2.5σ (session VWAP std is not a column; do not fake it with ATR)
- Those three are C++ into `engine/cpp/qr_entry_v2` if this screen's best
  *existing* family still leaves shrink-ceiling below the rung.
- Session IB (`disc_ib_session_high/low_aligned_usd`) is on the matrix and
  was not in this frozen list. Score it only with `--exploratory`. Label
  that receipt exploratory.

X (2026-08-22): PDH/PDL/PWH/PWL are the levels futures day traders actually
mark. VWAP bands show up. ICT FVG/OB/breaker are on X and stay out of this
screen (user: most of that will not work; we are not spending the first
pass there).

**Blocked by:** None.

**Status:** landed (frozen family set). Exploratory session-IB is a separate
receipt.

- [x] `--selftest` plants winners on `pdh_pdl` and recovers shrink-ceiling =
      cell-max on that family; a y-independent flag sits inside the shuffle
      band; NaN y refused.
- [x] Real run writes
      `artifacts/entry_v2/tabular_recovery/diagnostics/location_family_screen_20260822.json`
      with every family × asset × block × {tight, wide}: shrink-ceiling,
      occupancy, median names per cell, typed degenerate rows.
- [x] TRAIN ranks families. FORWARD of the TRAIN-best family is in the same
      table. A family that selects nobody or everybody is typed, not a finding.
- [x] Gaps listed above are named in the receipt as untested.
- [x] Wall < 20 min.

**Verify:**

1. [selftest] → `python3 tools/probe_location_family_screen.py --selftest`
2. [real run] → `OMP_NUM_THREADS=1 python3 tools/probe_location_family_screen.py --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix --out artifacts/entry_v2/tabular_recovery/diagnostics/location_family_screen_20260822.json`
3. [receipt] → schema `QRE2LOCFAM1`, matrix `7e9e25887afd99bc…`, sha256
   `4b3e6553e367c02a688c68f0fe6c2cc6870da95084032278ec8443cb2e4b5318`

**What it printed (TRAIN tight, Δ=180, 2021). 2021 cannot promote.**

Shrink-ceiling is the oracle of names left at that family, not a picker.
Ranking by shrink alone prefers fat nets. Occupancy and median names are
the other columns.

| Family | HG shrink / pick / ncell | NKD | SI |
|---|---|---|---|
| session_lvn | $2729 / 0.48 / 32 | $1685 / 0.30 / 23 | $2319 / 0.46 / 20 |
| ib_high_low | $2137 / 0.33 / 8 | $1375 / 0.37 / 15 | $2155 / 0.33 / 13 |
| session_vah_val (control) | $2080 / 0.25 / 9 | $1387 / 0.33 / 11 | $1917 / 0.21 / 13 |
| session_vwap | $1667 / 0.18 / 5 | $763 / 0.19 / 5 | $1594 / 0.24 / 7 |
| prior_lvn | $909 / 0.06 / 1 | $278 / 0.08 / 0 | $860 / 0.09 / 1 |
| prior_vah_val | $888 / 0.02 / 1 | $562 / 0.13 / 0 | $803 / 0.06 / 1 |
| pdh_pdl | $764 / 0.05 / 1 | $656 / 0.06 / 0 | $458 / 0.00 / 0 |
| prior_poc (control) | $457 / 0.08 / 0 | $359 / 0.08 / 0 | $562 / 0.06 / 0 |

Rungs $2000 HG, $1500 NKD and SI. Unfiltered TRAIN ceilings $2934 / $2027 / $2579.

TRAIN-best by shrink is `session_lvn` on every asset. FORWARD shrink
$2550 / $1607 / $1987. Occupancy is inside the shuffle band (HG pick−nonpick
0.047, band [-0.083, 0.127]). Median 20-32 names. That family did not
reduce the cell.

`pdh_pdl` TRAIN shrink is below the rung on every asset, occupancy inside
the shuffle, about half of cells have nobody at yesterday's high or low.
Kill of *that family* on 2021, not of location.

`ib_high_low` is the only frozen family that both keeps HG TRAIN shrink
above $2000 and over-represents winners on HG (pick 0.333 vs nonpick 0.145,
diff 0.189, shuffle band [-0.036, 0.141]). FORWARD HG $1909, under the
rung. NKD TRAIN $1375, under $1500. SI TRAIN $2155, FORWARD $1623. The
control live VAH/VAL also over-represents HG winners. Phase IB is live
until 3600 s. Do not treat this as a finished S0.

VWAP without σ. SI TRAIN $1594, FORWARD $1352. HG FORWARD $800. NKD TRAIN
$763.

Nobody/everybody GATE-DEFECT never fired (90% bar).

**Exploratory, not in the frozen family set.** Session IB
(`disc_ib_session_high/low_aligned_usd`), first hour of the session.
Receipt
`location_family_screen_ib_session_exploratory_20260822.json`
sha256 `c177b8397e5d2ccbe06ccb27d395067fab3f7f1385ad1382ef7afff34abde207`.
TRAIN tight shrink $1344 HG / $526 NKD / $1412 SI, all under the rung.
HG occupancy chance. SI pick 0.424 vs nonpick 0.151, outside shuffle,
still not enough remaining dollars (FORWARD $947). Finished session IB
does not clear the shrink-ceiling. Phase IB looking better was the live
running high/low, not a finished S0.

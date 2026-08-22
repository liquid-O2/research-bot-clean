# 19: Forward-vol vs oracle (live join only)

**What to build:** a read-only probe. QRE2FORECAST4 (HAR/OLS log RANGE
and log SIGMA, calibrated, session-open availability) is the owned
forward-vol model. Join it to the 2021 matrix the way live code does:
READY rows whose availability_ts_ns is at session open. Do not open
the eval sidecar. Generator stays frozen; a forecast cannot mint new
G1 names.

On this 2021 matrix the HAR columns (`sigma_hat_usd`, `move_q50_usd`,
`forecast_present`) are absent. The probe must receipt READY overlap
with matrix days as zero if that is the fact, then score the live
vol-like columns that *are* on the plane: `formation_atr_mean_usd`,
phase/session `actual_range_usd` and `range_consumption_usd_per_min`.

Metrics, TRAIN knobs only: between-cell Spearman of cell-mean(col)
vs cell-max y, vs 200 shuffles of cell-max across cells; fraction of
cells where the column is constant (cannot rank names). 2021 cannot
promote.

**Blocked by:** ticket 18 live path-dedup (vol is a keep/skip on the
reduced cell, not a replacement for it).

**Status:** landed

- [x] `--selftest` plants a between-cell ATR/y link and recovers
      Spearman above the shuffle band; a constant column is typed
      cell-constant; NaN y refused
- [x] Real run writes
      `artifacts/entry_v2/tabular_recovery/diagnostics/fvol_oracle_join_20260822.json`
      schema `QRE2FVOLORCL1` sha256
      `405e32a354d07f5ed2f460b3c23dd4309c6540ae450eeb5e5781cedb430f9999`

**What it printed (TRAIN, 2021). Cannot promote.**

QRE2FORECAST4 READY overlap with this matrix is 0/66 HG, 0/66 NKD,
0/41 SI (HAR columns absent on the plane). `formation_atr_mean_usd`
is cell-constant (cannot rank names); between-cell Spearman inside
shuffle on HG/NKD. Phase *realized* range vs cell-max y Spearman
0.82/0.80/0.82 outside shuffle, within-cell Spearman ~0. Vol says
whether the phase had meat, not which path won. First READY is
2022-02/03/10.

**Verify:**

1. [selftest] → `python3 tools/probe_fvol_oracle_join.py --selftest`
2. [real] → `OMP_NUM_THREADS=1 python3 tools/probe_fvol_oracle_join.py --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix --forecast-dir artifacts/cache/port/entry_v2/forecast --out artifacts/entry_v2/tabular_recovery/diagnostics/fvol_oracle_join_20260822.json`

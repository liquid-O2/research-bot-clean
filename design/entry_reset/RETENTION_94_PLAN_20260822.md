# 94% live retention, 2021 vol, keep-rule

2026-08-22. Human: get live oracle retention to about 94-95% on
every asset; make forward-vol work on 2021; think it through; ask
Fable 5.

## Destination

A prefix-only path-dedup whose TRAIN retained_fraction is ≥ 0.94
on HG, NKD and SI at median names ≤ 16 and shrink ≥ rung, plus a
2021-usable vol number that does not mutate QRF4 READY, plus a
causal keep-rule among the surviving paths. 2021 cannot promote.

## Facts

- Live key today: formation VWAP / 2θ keep-first. TRAIN HG ret 0.95
  ncell 15; NKD 0.88 ncell 9; SI 0.91 ncell 9
  (`path_dedup_live_20260822.json`). HG is already at the 94-95%
  band. NKD and SI are not.
- Formation VWAP / 1θ: HG 0.99 ncell 23 (fails ≤16); NKD 0.92 ncell
  15; SI 0.93 ncell 15. NKD 1θ is the closest under 0.94 that still
  cuts.
- QRF4 on the 2021 matrix window: HG/NKD 424/424 MISSING MIN_TRAIN
  (design valid, n_train < 250). SI 233 DESIGN_HISTORY + 191
  MIN_TRAIN. First READY 2022-02-01 NKD, 2022-03-01 HG, 2022-10-02
  SI. HAR columns absent on the 2021 plane.
- Persistence `sqrt(rv1)` is already computed inside QRF4 before the
  MIN_TRAIN gate (`forecast.cpp:852`). Publishing it as a tagged
  fallback does not lower MIN_TRAIN and does not change READY.

## Taken forks

1. Width grid on formation VWAP (ticket 20): 1.00, 1.25, 1.5, 1.75,
   2.00 × θ, plus merge-adjacent at 1θ. Per-asset TRAIN pick:
   among keys with ncell ≤ 16 and shrink ≥ rung, take highest
   retained_fraction. FORWARD of that pick is the check. If no key
   hits 0.94, say so; do not eval-select FORWARD.
2. 2021 vol (ticket 21): do not lower `kForecastMinTrain`. Add a
   tagged persistence fallback when `design.valid` and n_train <
   250: sigma_hat = sqrt(rv1), range_hat = prior Parkinson, ladder
   unscaled, status not READY. SI DESIGN_HISTORY days stay missing
   until RV windows exist. Join is opt-in. QRF4 READY identity
   unchanged.
3. Keep-rule among surviving paths: surviving running-max (K later
   births) and vol-scaled skip once a 2021 fallback or 2022 READY
   join exists. Not location AND first-third (dead).
4. Fable 5 max, new session, fence restated. Does not implement.

## Out of scope

Generator rewrite. Lowering MIN_TRAIN on READY. 2025H2. Neural.
Exits, extra minis, size.

## Verify

1. [width selftest] → `python3 tools/probe_path_dedup_width.py --selftest`
2. [width real] → `OMP_NUM_THREADS=1 python3 tools/probe_path_dedup_width.py --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix --out artifacts/entry_v2/tabular_recovery/diagnostics/path_dedup_width_20260822.json`
3. [Fable] → `design/entry_reset/FABLE5_RETENTION_94.md` ends with terminal `success` and a taken encoding that is prefix-only

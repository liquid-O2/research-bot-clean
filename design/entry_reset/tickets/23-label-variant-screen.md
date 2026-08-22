# 23: Label variant screen (perfect-label ceiling)

**What to build:** one on-matrix probe. For each named label, pick
the highest-label name in the live-deduped cell, cash that name's
live y, and letter it against the per-asset rung. Shuffle of the
label inside the cell is the null. Monotone cell-z of y is the
mutant (must cash the same as raw y). Prefix-only scores
Spearman-rank each surviving label. 2021 cannot promote.

**Blocked by:** tickets 18, 20, 22 (keep-first widths and the
reduced-cell ruler). Spec
`design/entry_reset/LABEL_VARIANT_SCREEN_20260822.md`.

**Status:** landed (2026-08-22). Receipt
`artifacts/entry_v2/tabular_recovery/diagnostics/label_variants_20260822.json`
schema `QRE2LABVAR1` sha256
`ca83d2d2159f85db45eb5b793267be2ee7299cd2362d596063c2ed5b7a2a811d`.
Fable/Opus first pass still running; receipt goes on resume.

- [x] `--selftest` cashes planted 2500 vs 400, refuses NaN y,
      cell-z matches raw y
- [x] Real run writes the receipt, schema `QRE2LABVAR1`
- [x] Every TRAIN (asset, label) row has a letter
- [ ] Fable session `6f11e029-99cc-45f6-9998-050986c3b51c` and
      Opus session `18d4977a-f745-4f6d-857a-b1cfb0d7743c` receive
      the receipt on resume, not as an anchor in the first brief

**What it printed (TRAIN). Cannot promote.**

HG ceil $2781, 59% of cells have a y>=$600 name. NKD $1860 / 30%.
SI $2409 / 58%. Isolated Dawes COMBINED cashes $-50 / $-160 / $-267
(below the shuffle of y). peer_early and clock_only are the same
score on HG and SI at Δ=180 (formation and remaining are collinear
at a fixed age). Clock cash $490 HG, negative on NKD/SI.

raw_y and y_cell_z: aligned_chance, cash = ceiling. Prefix Spearman
vs y is ~0. clock_resid: aligned_chance, same_as_ymax 0.94/0.89/0.91,
cash ≈ ceiling. Residualizing the dollar label does not change the
target. good_enough: cannot_reach HG $1874 / NKD $778; SI $1567
aligned_separable. sign_y cannot_reach all three. capture_remaining
and cluster_max letters that say separable are Spearman 0.06-0.19
against the clock, and the clock itself does not print the rung.
Do not read those letters as a ranking-grade family.

**Verify:**

1. [selftest] → `python3 tools/probe_label_variants.py --selftest`
2. [real] → `OMP_NUM_THREADS=1 python3 tools/probe_label_variants.py --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix --out artifacts/entry_v2/tabular_recovery/diagnostics/label_variants_20260822.json`

# 26: Wait until the paying name, and a full-column prefix scan

**What to build:** one on-matrix probe, two published facts.

1. How long after the first keep-first name the cell-max becomes
   eligible (formation gap in seconds, because every name is scored
   at +180). Fractions arrived by 60/180/300/600/1800/3600 s.
2. Prefix winner-vs-earlier AUC for every matrix column. TRAIN ranks
   columns. THRESHOLD is the holdout (not a knob). A column survives
   only if TRAIN AUC >= 0.60 and THRESHOLD AUC >= 0.60. Clock-named
   columns cannot grant "information present."

This answers: is the paying name minutes later, and is identification
actually missing from the matrix or did T25 just score the wrong
handful of columns.

**Blocked by:** ticket 25.

**Status:** landed (2026-08-22). Receipt
`artifacts/entry_v2/tabular_recovery/diagnostics/crux_wait_scan_20260822.json`
schema `QRE2CRUXWAIT1` sha256
`044cde9bb9eea99b0501c4faafb07d70208c1b587d475cbf3710b51d60b46ef0`.

- [x] `--selftest`: planted 200 s wait, planted column AUC 1, NaN refused
- [x] Real run writes the receipt
- [x] 2021 not used as promotion

**What it printed (TRAIN). Cannot promote.**

Wait from first keep-first to the paying name: median 2442 s HG /
2536 s NKD / 2214 s SI (about 37-42 minutes). Only 29% / 24% / 30%
of winners are eligible within 300 s of the first. Within 3600 s:
60% / 63% / 61%. Column scan letter `only_clock` on all three.
Best TRAIN column is session elapsed at AUC 1.0: tautological,
because in the prefix-at-winner-time frame the winner is always
the last-born. Zero non-clock columns survive TRAIN AUC>=0.60 and
THRESHOLD AUC>=0.60. Combinations of non-clock columns are still
unmeasured except Dawes, which T25 already showed is chance on
HG/NKD.

**Verify:**

1. [selftest] → `python3 tools/probe_crux_wait_scan.py --selftest`
2. [real] → `OMP_NUM_THREADS=1 python3 tools/probe_crux_wait_scan.py --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix --out artifacts/entry_v2/tabular_recovery/diagnostics/crux_wait_scan_20260822.json`

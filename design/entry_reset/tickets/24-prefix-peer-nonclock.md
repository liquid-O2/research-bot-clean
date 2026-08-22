# 24: Side-then-earliest ceiling (was prefix-peer)

**What to build:** one on-matrix probe, minutes, no CatBoost. For
each cell, take the earliest live keep-first name on the side of
the cell-max, cash that name's live y. That is `side_first`. Random
side then the same earliest rule is the null. TRAIN letters it
against the rung. Also publish `wrong_first`, `side_k` for k=1,2,3,
wall-hit of the first winning-side name, oracle-path MDD, and
whether side-aligned phase-scale columns (clock residualized)
separate the side label above a shuffle.

This ticket was first written as prefix-peer ranks of extension.
Fable 5 xhigh (`FABLE5_XHIGH_LABEL_DIAGNOSIS.md`) identified that
as RUNMAX, which already failed
(`extension_causal_20260822.json`). T23 cashed rank-by-runway at
$490 HG. The live encoding is side-then-earliest. Full argument:
`design/entry_reset/HANDOFF_DECISION_PLANE_20260822.md`.

**Blocked by:** ticket 23.

**Status:** landed (2026-08-22). Receipt
`artifacts/entry_v2/tabular_recovery/diagnostics/side_split_20260822.json`
schema `QRE2SIDESPLIT1` sha256
`d64b1d6857295877baab738d6a6a9a5723af9dde0b85f9992daaeb04c2a5fe31`.
User lifted the halt for this probe and one plane test. 2021 cannot
promote.

- [x] `--selftest` on a planted two-sided cell: LONG 900,700,-900
      and SHORT -300,-850. `side_first` cashes 900, `wrong_first`
      cashes -300, NaN y refused
- [x] Real run writes the receipt
- [x] TRAIN letter `side_insufficient` on HG, NKD, and SI
- [x] 2021 not used as promotion

**What it printed (TRAIN). Cannot promote.**

Almost every cell is two-sided (0.98/0.98/0.97). The side call is a
real decision. Earliest keep-first on the cell-max side cashes
$1986 HG / $985 NKD / $1471 SI against rungs $2000 / $1500 / $1500.
Wrong side cashes about -$1600. Random-side p975 is $853 HG; side_first
clears the null on every asset and block. THRESHOLD/FORWARD HG
$1448 / $1331. The encoding as written (k=1) does not print the
rung. Diagnostic, not a knob: HG TRAIN second-earliest on the
winning side cashes $2066. Isolated Dawes as a side picker is below
a coin on HG (hit 0.47). Session directional-profile skewness hit
0.645 HG / 0.719 SI TRAIN, not NKD, and not on HG FORWARD.

**Verify:**

1. [selftest] → `python3 tools/probe_side_split.py --selftest`
2. [real] → `OMP_NUM_THREADS=1 python3 tools/probe_side_split.py --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix --out artifacts/entry_v2/tabular_recovery/diagnostics/side_split_20260822.json`

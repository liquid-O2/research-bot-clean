# 27: Prefix-ceiling after waiting (how much oracle is on the table)

**What to build:** one on-matrix probe. After live keep-first, in each
cell wait W seconds after the first name's formation, then take the
hindsight max y among names already born. That is the oracle among
names that exist at that wait, not a model. Grid W = 0, 300, 600,
1800, 2400, 3600 s, and inf (full cell-max). Publish $/asset-day,
capture vs cell-max, fraction of cells whose winner is already born,
and whether the 2400 s prefix ceiling clears the rung on TRAIN.

This answers: if you wait ~40 minutes after the first name, how much
of the paying-name oracle is even on the table. 2021 cannot promote.

**Blocked by:** ticket 26.

**Status:** landed (2026-08-22). Receipt
`artifacts/entry_v2/tabular_recovery/diagnostics/wait_prefix_ceiling_20260822.json`
schema `QRE2WAITCEIL1` sha256
`1630a2d427501a1f0570136d7ceb26ccfe8e5e572e0213375358e3475135e168`.

- [x] `--selftest`: planted wait 200 s, W=0 cashes 400, W=300 cashes 2500
- [x] Real run writes the receipt
- [x] 2021 not used as promotion

**What it printed.** Oracle among names already born, not a model.
TRAIN at W=2400 s: HG $2117 (0.76 of cell-max, winner born in 49%,
clears $2000), NKD $1262 (0.68, 48%, under $1500), SI $1777 (0.74,
55%, clears $1500). THRESHOLD at 2400 s: HG $1741, NKD $1246, SI
$1213, none hold the HG/SI TRAIN clears except SI FORWARD $1598.
NKD never clears at 3600 s ($1350 TRAIN). W=0 matches ticket 25
enter-first.

**Verify:**

1. [selftest] → `python3 tools/probe_wait_prefix_ceiling.py --selftest`
2. [real] → `OMP_NUM_THREADS=1 python3 tools/probe_wait_prefix_ceiling.py --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix --out artifacts/entry_v2/tabular_recovery/diagnostics/wait_prefix_ceiling_20260822.json`

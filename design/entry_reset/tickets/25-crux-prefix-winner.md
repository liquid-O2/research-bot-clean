# 25: Prefix identification of the cell-max (the live object)

**What to build:** one on-matrix probe. The $1986 / $985 side-first
numbers are hindsight oracles (finished-cell max side, then earliest
on that side). They are not a model. That oracle already misses the
rung. Ranking a finished list of 15 is also not live: later names
do not exist when an early name is eligible.

The live object: names become eligible at formation+180 in order.
When the eventual cell-max becomes eligible, the only names on the
table are those already eligible. Can prefix-only non-clock features
rank it above those earlier names? Shuffle of the winner among the
prefix is the null. Always-enter-first is the live no-score policy.
TRAIN writes the letter. 2021 cannot promote.

Letters:
- `first_prints`: enter-first cash >= rung (no ranker needed)
- `prefix_seen`: enter-first under the rung, at least one non-clock
  score AUC of winner-vs-earlier beats shuffle and is >= 0.60
- `prefix_blind`: enter-first under the rung, nothing sees the
  winner in the prefix. The information is not on this matrix at
  180 s. That is the crux.

**Blocked by:** ticket 24 (side-first is an oracle and still misses).

**Status:** landed (2026-08-22). Receipt
`artifacts/entry_v2/tabular_recovery/diagnostics/crux_prefix_winner_20260822.json`
schema `QRE2CRUXPRE1` sha256
`d2fe275301b729a3c60c7cfd6b43a5647517c8864fa06e967b236eb0f59a7d69`.
2021 cannot promote.

- [x] `--selftest`: planted winner is second, prefix n=2, planted
      score AUC 1.0, enter-first cashes the first name, NaN refused
- [x] Real run writes the receipt
- [x] TRAIN letter: HG `prefix_blind`, NKD `prefix_blind`, SI
      `prefix_seen` (Dawes 0.69) and THRESHOLD/FORWARD `prefix_blind`
- [x] 2021 not used as promotion

**What it printed (TRAIN). Cannot promote.**

The cell-max is first-born in 21% HG / 6% NKD / 12% SI of cells.
When it becomes eligible, 4 / 7 / 5 keep-first names are already
on the table (median). Enter-first (fully live) cashes $489 HG,
$-313 NKD, $-196 SI. Prefix identification AUC of Dawes,
favorable excursion, aligned-from-formation, and directional
skewness is ~0.46-0.51 on HG and NKD, inside or under shuffle.
Clock AUC is 0.0: remaining falls with formation order, so it
always prefers earlier names. SI Dawes 0.69 on TRAIN does not
hold on THRESHOLD or FORWARD. The live job is a 4-7 way prefix
rank, not a finished 15-way rank, and this plane is blind to it.

**Verify:**

1. [selftest] → `python3 tools/probe_crux_prefix_winner.py --selftest`
2. [real] → `OMP_NUM_THREADS=1 python3 tools/probe_crux_prefix_winner.py --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix --out artifacts/entry_v2/tabular_recovery/diagnostics/crux_prefix_winner_20260822.json`

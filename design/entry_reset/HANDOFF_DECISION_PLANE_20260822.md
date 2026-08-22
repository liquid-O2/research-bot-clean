# Handoff: the decision-time plane, and how to reach the rung

2026-08-22. Written so a later session can continue without this
conversation. The user halted spend, then allowed two tests: side-then-earliest
and whether any prefix score sees the winning side. Both landed.
Receipt `side_split_20260822.json` sha `d64b1d68`. Letter
`side_insufficient` on every asset. Do not launch more unless they
say so. Diagnostics only. No learned dollars exist.

## The goal (D-110)

Per-asset exact-replay dollars, one mini: HG $2,000 per asset-day,
NKD and SI $1,500 when that block's delayed ceiling cannot support
$2,000. At most 12 entries per portfolio-day. One position per asset.
MDD under $1,000. 5 real seeds + 5 matched shuffles. Weakest real
above strongest shuffle. 80% of ceiling is reported, not a refusal.
Entries only. Generator frozen. Neural dead. 2025H2 sealed.

## Crux (ticket 25, after the user asked what 1986/985 were)

Those dollars are oracles, not a model. Ticket 24 knows the finished
cell's winning side, then takes the earliest name on it. Even that
misses the rung. The live decision never sees the finished cell.

Ticket 25 walks keep-first names in eligibility order (formation+180).
When the eventual cell-max becomes eligible, 4 / 7 / 5 names are
already on the table (median HG/NKD/SI TRAIN). It is the first-born
in 21% / 6% / 12% of cells. Enter-first cashes $489 / $-313 / $-196.
Prefix identification AUC of Dawes, excursion, aligned-from-formation
and directional skewness is ~0.46-0.51 on HG and NKD (`prefix_blind`).
Clock AUC is 0.0 because remaining falls as names form later. SI Dawes
0.69 on TRAIN is `prefix_seen` and is `prefix_blind` on THRESHOLD and
FORWARD. Receipt `crux_prefix_winner_20260822.json` sha `d2fe2753`.

The goose chase was ranking 15 finished names and inventing coarse
oracles (location, side, good-enough, clock) whose perfect versions
also miss.

Ticket 26: the paying name becomes eligible a median 41/42/37 minutes
after the first keep-first name (HG/NKD/SI TRAIN). Only ~30% are
eligible within 300 s of the first. A 180-300 s confirmation window
on the first names is the wrong time scale. Full-column scan in the
prefix frame: `only_clock`. Elapsed AUC 1.0 is tautological (winner
is last-born in that prefix). Zero non-clock single columns survive
TRAIN+THRESHOLD. Combinations other than Dawes are unmeasured.
Receipt `crux_wait_scan_20260822.json` sha `044cde9b`.

Until the paying name is born, information cannot exist. After it is
born, the columns we trained do not flag it, and no other single
column does either except the clock tautology. That is the split.
Not CatBoost. Not the generator.

## The exact problem

The frozen generator already has the names. After live keep-first the
TRAIN cell-max is $2781 HG / $1860 NKD / $2409 SI (receipt
`rho_on_dedup_20260822.json` sha `3b5e69c8`). A perfect ranker of live
y still prints that ceiling (`label_variants_20260822.json` sha
`ca83d2d2`). CatBoost is not the limiter: on this plane, unit-weight
Dawes beat trees, and YetiRank on 1764 columns was not separated from
shuffle.

What failed is the decision-time plane. At the second we score a
name, the columns describe that name's local defense plus how much
session is left. The dollars are which of the 15 live zigzags is the
phase's remaining extreme, which includes which way the phase goes.
Those are different questions. The oracle knows the second because it
has seen the rest of the phase. Distillation asks the model to emit
that fact from inputs that do not contain it. The fit then locks onto
the one prefix-visible correlate of "winner" under a phase-close
exit: time remaining.

Isolated confirmation COMBINED, used as a picker on the 15 paths,
cashes $-50 HG / $-160 NKD / $-267 SI. Formation-order and
phase_remaining_sec are the same score at a fixed delay of 180 s
(remaining is phase length minus formation). That clock cashes $490
on HG and is negative on NKD and SI.

## Why oracle teaching never transferred

Four stacked mismatches, all receipted.

1. The first learner was taught substitution margin ($11 to $38)
   against an oracle continuation of the rest of the day, then argmin
   across ENTER/DEFER/PASS. It printed $0. Curriculum toward that
   teacher made the head worse (AUC 0.684 round-0 to 0.659 round-2).
2. A classifier of "series-best at least $600" reached AUC 0.63 to
   0.65 and was almost entirely `phase_remaining_sec` (0.65/0.64/0.57
   by itself). The label was an anytime-max over the series. The
   feature was the clock.
3. Copying the oracle as a causal rule failed. "Most extended of the
   phase" is 0.37 to 0.60 in hindsight and at or below random in time
   order (`extension_causal_20260822.json`). RUNMAX is that rank.
4. Even with the dollar label itself, ranking 15 unique paths still
   needs AUC 0.87/0.90/0.81. The isolated row does not see the other
   names or the other side. CELLZ_RMSE early-stops at 11 trees
   (val RMSE 0.99, the cell mean).

## What T23 printed (TRAIN, 2021). Cannot promote.

| Label | HG | NKD | SI |
|---|---|---|---|
| raw_y / y_cell_z | aligned_chance $2781 | aligned_chance $1860 | aligned_chance $2409 |
| clock_resid | aligned_chance $2779, same pick 94% | aligned_chance $1860, 89% | aligned_chance $2409, 91% |
| capture_remaining (y/R) | aligned_separable $2199, Spearman vs clock 0.06 | cannot_reach $1465 | aligned_chance $2088 |
| cluster_max | aligned_separable $2224, Spearman vs clock 0.17 | aligned_separable $1627, 0.19 | aligned_separable $1613, 0.16 |
| good_enough (y>=$600, random among positives) | cannot_reach $1874 (59% of cells have one) | cannot_reach $778 (30%) | aligned_separable $1567 (58%) |
| sign_y | cannot_reach $1572 | cannot_reach $1070 | cannot_reach $1350 |

Prefix scores on that screen: Dawes cash negative. Clock cash $490 HG.
`aligned_separable` on capture and cluster_max is a 0.06 to 0.19
Spearman against the clock. The clock as a picker does not print the
rung. Do not read those letters as a ranking-grade family.

Regenerate:

```
python3 tools/probe_label_variants.py --selftest
OMP_NUM_THREADS=1 python3 tools/probe_label_variants.py \
  --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix \
  --out artifacts/entry_v2/tabular_recovery/diagnostics/label_variants_20260822.json
```

## How to improve the decision-time plane

Change three things together. The row, the label, the columns. Not
the library.

**Row.** Stop training one isolated name against 1764 columns. A cell
has two sides. Fable's encoding (taken as the next measurement): one
row per (cell, side, decision second of a keep-first name on that
side). Two streams per cell. The 15-way path rank collapses to a
2-way side call plus a fixed within-side rule.

**Label.** Stop regressing isolated y on that row. y is mostly a
shared side factor (which way the phase goes from here) times
survival (wall) times an entry-price order that is already visible.
The next label to ceiling-test is: is this the cell-max side. Cash is
always the live y of the earliest keep-first name on the called side,
at that name's own +180 s, with occupancy. Perfect ranker of that
label therefore cashes `side_first_usd`. If that number is under the
rung, the encoding is dead and the receipt's wall-hit and later-same-
side fields say where the rest sits. Do not train first.

**Columns.** Stop using the local confirmation bag as the ranker.
Isolated Dawes is local defense and cashes negative. Stop using
formation-order and `phase_remaining_sec` as rankers. They are one
score at Δ=180. Use, instead, side-aligned phase-scale levels that
are already in the matrix and that the accrual scan ranked at
formation (AUC about 0.62 to 0.69, diagnostic, not a finding):
session directional-profile skewness, phase POC and VWAP aligned,
IB directional break and extension, eclock size-count divergence,
tclock aligned flow, add-side size, prior high/low aligned at age 0
(not as a keep rule). Add prefix-only side-cumulative memory: among
same-side keep-first names already born, count, reclaim latches,
rebuild-after-depletion, best entry price relative to this name.
Residualize the clock out of every Spearman before you read a
family. Do not delete the clock from the row if you need it as
exposure. Do not rank by it.

Within-side rule, taken until measured otherwise: enter the earliest
keep-first name on the called side. Winners form early (median
formation-rank fraction 0.16 to 0.25). The first-born twin of the
winner's bucket holds about 98 cents of the winner's dollar. The
gap between "earliest on the winning side" and "the cell-max name"
is the kill field of the next probe.

## Fable vs Opus vs T23. Do not average them.

Fable 5 xhigh (`6f11e029-99cc-45f6-9998-050986c3b51c`) took
**side-then-earliest**. File
`design/entry_reset/FABLE5_XHIGH_LABEL_DIAGNOSIS.md`. Unmeasured.
This is the next probe when spend returns.

Opus 5 max (`18d4977a-f745-4f6d-857a-b1cfb0d7743c`) took
**runway-offset cell rank**: fit y/R, score r_hat * R, kill if rank-
by-R-alone does not beat shuffle and drop required AUC by 0.05. File
`design/entry_reset/OPUS5_MAX_LABEL_DIAGNOSIS.md`. T23 already cashed
rank-by-R-alone (`clock_only`) at $490 HG and negative on NKD and SI,
and Spearman of the clock vs y is about 0. That encoding is dead as
a path to the rung. Keep Opus's object-mismatch list (M1 to M8) as
code findings. Do not run the runway-offset probe.

Peer-relative extension among born-so-far is RUNMAX
(`extension_causal_20260822.json`, capture 0.144 vs random p97.5 of
0.181 on HG TRAIN). Ticket 24 as originally written is that rewrite.
It is parked. The live ticket 24 is the side-split probe.

Pivot-at-level is not a keep rule (tickets 11, 12, 17). Age-0 aligned
distances may sit as columns inside the side family. They are not an
encoding of their own.

## Ticket 24 result (the two tests)

Test 1, ceiling, TRAIN. `side_first` $1986 HG / $985 NKD / $1471 SI
against $2000 / $1500 / $1500. Letter `side_insufficient` all three.
Almost every cell is two-sided (0.98). Wrong-side earliest cashes
about -$1600. Random-side p975 $853 HG; the side oracle clears the
null everywhere. THRESHOLD/FORWARD HG $1448 / $1331, so the TRAIN
near-miss is not a held result. Diagnostic only: HG TRAIN
second-earliest on the winning side cashes $2066 (not the encoding,
not a knob). NKD stays under $1100 even at k=3. SI threshold path
MDD $1958 against the $1000 clause.

Test 2, plane, TRAIN two-sided cells. Isolated Dawes as a side
picker: HG hit 0.47 (worse than a coin). Clock 0.42. Session
directional-profile skewness 0.645 HG / 0.719 SI, beats shuffle,
fails NKD (0.597) and HG FORWARD. The plane sees the side weakly
on two assets in sample and does not hold.

Fable's encoding as written does not print the rung. The side call
is still the only measured structure that beats a coin by a large
dollar margin (wrong side is the toxic one). The remaining gap on
HG TRAIN is which same-side name, not which side.

## Next probe, when the user says spend is allowed

Already run: `tools/probe_side_split.py`. Do not re-run as a
discovery loop. If spend returns, the next unmeasured object is
which same-side name after the side is known (k=2 was $2066 HG
TRAIN, exploratory). Do not eval-select k from TRAIN.
Reuse `load_delta_rows`, `_keep_idx`, `_formation_sec`, `_cell_pick`.
Planted selftest: LONG names y 900, 700, -900 in birth order, SHORT
y -300, -850. `side_first` must cash 900, `wrong_first` -300, NaN y
refused.

```
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
python3 tools/probe_side_split.py \
  --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix \
  --out artifacts/entry_v2/tabular_recovery/diagnostics/side_split_20260822.json
```

Letters, from Fable, TRAIN writes them:

- `side_carries_seen`: `side_first` at or above the rung, and at
  least one prefix family Spearman or side-AUC above shuffle on
  TRAIN and THRESHOLD.
- `side_carries_unseen`: `side_first` at or above the rung, plane
  does not see it.
- `side_insufficient`: `side_first` under the rung.

NKD is exposed: keep-first ceiling $1860, so the earliest winning-
side name must hold 0.81 of the cell-max to print $1500. HG needs
0.72 of $2781. SI 0.62 of $2409. Publish oracle-path MDD because SI
threshold cell-max path already printed $1080 against the $1000
clause.

After `side_carries_seen`: a per-cell side logit on the 2022+
corpus, never a 2021 CatBoost fit. After `side_carries_unseen`:
later tau on the same side stream. After `side_insufficient`: stop
and read wall-hit and `side_k`. That is a measured boundary.

## What not to do

Do not fit CatBoost on the 1764-column isolated plane. Do not switch
library. Do not change the generator. Do not unseal 2025H2. Do not
extend exits or size. Do not revive location AND first-third. Do not
train good_enough as the solo HG or NKD path. Do not imitate the
teacher. Do not run RUNMAX again. Do not rank by the clock. Do not
lower QRF4 MIN_TRAIN. Do not promote off 2021.

## Sessions, if you need them later

Fable 5 xhigh, label diagnosis:

```
claude -p --resume 6f11e029-99cc-45f6-9998-050986c3b51c --model claude-fable-5 --effort xhigh --dangerously-skip-permissions "FENCE (restate): entries only; no exits, extra minis, size, neural, 2025H2, generator. Don't implement. Write only design/entry_reset/FABLE5_XHIGH_LABEL_DIAGNOSIS.md. T23 sha ca83d2d2 killed rank-by-clock ($490 HG) and good_enough on HG/NKD. Side-then-earliest is still unmeasured. <question>"
```

Opus 5 max, label diagnosis:

```
claude -p --resume 18d4977a-f745-4f6d-857a-b1cfb0d7743c --model claude-opus-5 --effort max --dangerously-skip-permissions "FENCE (restate): entries only; no exits, extra minis, size, neural, 2025H2, generator. Don't implement. Don't vision-read PDFs. Write only design/entry_reset/OPUS5_MAX_LABEL_DIAGNOSIS.md. T23 sha ca83d2d2: clock_only $490 HG, Spearman vs y ~0, so runway-offset Arm 2 is dead as a path. <question>"
```

Never `--bare` (OAuth skipped). Restate the fence on every resume.
Notes: `artifacts/cache/review/cli_sessions_20260822.md`.

## Receipts that still hold

All under `artifacts/entry_v2/tabular_recovery/diagnostics/`.
Matrix `7e9e2588…` at
`artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix`.

| File | What |
|---|---|
| `rho_ruler_20260822.json` | Unreduced cell. Rung needs AUC 0.77 to 0.95. AUC 0.60 buys $200 to $650. |
| `rho_on_dedup_20260822.json` sha `3b5e69c8` | After keep-first, n=15, AUC at rung still 0.87/0.90/0.81. |
| `path_dedup_live_20260822.json` sha `4beb0045` | Live key: formation VWAP / 2θ HG, 1θ NKD and SI, keep first. |
| `label_variants_20260822.json` sha `ca83d2d2` | Perfect-label ceiling. Dawes cash negative. Clock $490. |
| `ceiling_split_20260822.json` | `no single dimension`. Best cell of the day is most of the ceiling. |
| `confirmation_accrual_v2_20260822.json` | COMBINED AUC ~0.51 at 0 s, ~0.60 at 300 s, still rising. |
| `extension_causal_20260822.json` | RUNMAX and first-extended fail in time order. |
| `oracle_retention_filters_20260822.json` | 83/73/52% of oracle picks miss finished locations. |
| `trained_accrual_20260822_YETIRANK.json` | Full-plane listwise not separated from shuffle. |

## Closed questions, with scope

See `CURRENT.md`. In one line: 2021 closures are "closed AT 67 days
of summer 2021". Generator is not the bottleneck. Location as a keep
is not the reduction. Path-dedup is. Isolated confirmation is not a
picker. The clock is not a ranker. good_enough is not an HG or NKD
path. Residualizing the dollar label does not change the target.
YetiRank on 1764 isolated columns is not a path. RUNMAX is not a
path. Side-then-earliest is unmeasured.

## Hardware and tests

`HARDWARE.md`: 13.6 cores, 263 GiB, one RTX PRO 6000. `nproc` and
`free` lie. CatBoost `thread_count=16`. `python3 -m unittest`. pytest
is not installed. Pod restart wipes the overlay. Reinstall recipe is
in that file. Battery: `bash tools/run_all_checks.sh --fast`.

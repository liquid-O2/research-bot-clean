# Label variant screen (ticket 23)

2026-08-22. Planning skills in the prescribed order. The human's
correction this turn: the generator already contains the candidates
that print the rung. What failed is the label, the feature family,
and how examples are structured for the model. This spec is the
cheap first measurement of that claim. 2021 cannot promote.

## Problem Statement

The frozen G1 generator's cell-max at Δ=180 s already exceeds the
per-asset rung on 2021 TRAIN (HG $2781, NKD $1860, SI $2409 after
live keep-first, receipt `rho_on_dedup_20260822.json` sha
`3b5e69c8`). Isolated confirmation scores reach winner-vs-loser AUC
about 0.60, which the same receipt converts to $542 / $271 / $446
per asset-day. Ranking the remaining 15 unique paths still needs AUC
0.87 / 0.90 / 0.81. The model is being asked to rank paths using a
per-series dollar label and an isolated confirmation plane that
never sees the other live paths. We do not yet know which labels,
when followed perfectly and cashed as the live trade's dollars, even
point at the rung, and which of those labels the prefix-only plane
can rank.

## Solution

One on-matrix probe. For each named label, pick the name with the
highest label in each cell, cash that name's live y, and compare to
the rung and to a within-cell shuffle of the label. That is the
perfect-label ceiling test from preregistering-results: if a perfect
ranker of this label cannot print the rung in live dollars, do not
train against it. In the same receipt, report whether prefix-only
scores (confirmation COMBINED, peer-early, clock-only) Spearman-rank
that label above a shuffle. No CatBoost. No generator edit. Minutes.

## User Stories

1. As the trader, I want every proposed label killed or kept by
   whether a perfect ranker of it, cashed as live y, prints the rung,
   so that we stop training against targets that cannot be the goal.
2. As the trader, I want that number next to a within-cell shuffle
   of the same label, so that a tautology cannot pass as a result.
3. As the trader, I want monotone transforms of y (cell-z, rank)
   reported as a mutant: they must cash the same dollars as raw y,
   or the probe is broken.
4. As the trader, I want a "good enough" label (any name with y at
   least $600) priced as random-among-positives, so I know whether
   the job is classification or ranking.
5. As the trader, I want clock-residual and capture-of-remaining
   labels tested for alignment, so we see whether removing the
   time confound also removes the dollars.
6. As the next agent, I want prefix-only scores Spearman-ranked
   against each surviving label, so the next fit has a target the
   current plane can actually see.
7. As the next agent, I want Fable 5 xhigh and Opus 5 max to
   diagnose the same object in parallel, then to receive this
   receipt without being anchored on it first.
8. As the next agent, I want 2021 treated as a kill sample, never
   a promotion sample.

## Implementation Decisions

- Reuse live keep-first from tickets 18 and 20 (HG 2θ, NKD 1θ,
  SI 1θ) via the same helpers as `probe_rho_on_dedup.py`. y is
  unused in the keep.
- One row of the report per (label, asset, block). TRAIN writes
  the letter. THRESHOLD and FORWARD are reported, never knobs.
- Alignment uses `_cell_pick` so occupancy and one-position-per-asset
  are the same dollars as the ρ ruler.
- `y_cell_z` is a mutant of `raw_y`: same argmax, same cash. If
  they disagree, the probe refuses.
- Binary labels (`good_enough`, `sign_y`) have no unique argmax.
  Alignment is the mean over draws of a uniform pick among
  positives, skip the cell if none. That is the "classifier is
  enough" ceiling, not a ranker ceiling.
- `clock_resid` residualizer (y on phase_remaining_sec) fits on
  TRAIN and applies to every block. Deployable, not in-sample on
  THRESHOLD.
- `cluster_max` is the unreduced bucket max assigned to the
  keep-first representative. Cash is the representative's y.
- Prefix scores: confirmation COMBINED when ingredients exist;
  peer-early = minus formation_sec (prefix-visible birth order);
  clock-only = phase_remaining_sec. Scores cash y directly as a
  baseline. Per-label Spearman of each score vs L is the
  learnability diagnostic.
- Design A (taken): perfect-label ceiling then Spearman. Design B
  (rejected this slice): CatBoost per label before alignment is
  known. Design C (forbidden): change G1 birth.

## Testing Decisions

Highest seam: `run(matrix_dir, out_path)` on a planted matrix.
Prior art: `tools/probe_rho_on_dedup.py --selftest`. The selftest
plants three paths with known y and remaining, asserts cash
literals (2500 vs 400), refuses NaN y, and checks the monotone
mutant. Real-data dollars are the evidence tier, not the selftest.

## Out of Scope

Generator edits. Neural. Extra minis, size, exits. 2025H2.
CatBoost / YetiRank fits. Lowering QRF4 MIN_TRAIN. Promoting off
2021. Location AND first-third. Causal-last as the answer (it is
a representative gap of cents on the median, ticket 20).

## Letters

- `cannot_reach`: TRAIN alignment under the rung. Perfect ranker
  of this label, cashed as live y, cannot print the goal. Do not
  train against it.
- `aligned_chance`: TRAIN alignment at or above the rung, every
  prefix score's Spearman vs this label sits inside the shuffle
  band. The label points at the money. The current plane does not
  see it.
- `aligned_separable`: TRAIN alignment at or above the rung, at
  least one prefix score Spearman vs this label sits above the
  shuffle band. Candidate for a later fit. 2021 still cannot
  promote.

## Acceptance scenarios

### SC-LAB-1 (monotone mutant)

Given: a planted cell whose raw y argmax is unique
When: `python3 tools/probe_label_variants.py --selftest`
Then: `raw_y` and `y_cell_z` cash the same dollars to the cent
Rejects: a probe that ranks cell-z differently from y

### SC-LAB-2 (misaligned efficiency label)

Given: planted names A y=2500 remaining=10000 and B y=400 remaining=80
When: the same selftest
Then: `capture_remaining` cashes B (400), letter `cannot_reach` on
the plant's HG rung of 2000; `raw_y` cashes A (2500)
Rejects: treating capture-of-remaining as aligned without cashing y

### SC-LAB-3 (NaN y)

Given: a matrix with one non-finite current_asinh
When: `run(...)`
Then: `ProbeRefusal` naming non-finite y
Rejects: dropping the row silently

### SC-LAB-4 (real 2021 screen)

Given: matrix `7e9e2588…`, live keep-first
When: `OMP_NUM_THREADS=1 python3 tools/probe_label_variants.py --matrix-dir <component_matrix> --out artifacts/entry_v2/tabular_recovery/diagnostics/label_variants_20260822.json`
Then: every (asset, label) row on TRAIN has a letter in
{cannot_reach, aligned_chance, aligned_separable}; shuffle usd is
published; 2021 is not used as a promotion
Rejects: a letter with no shuffle, or a CatBoost fit

## Orchestrator prior (not law)

These are the working bets, to be killed by the receipt or by
Fable / Opus, not protected.

1. `raw_y` is aligned by construction (it is the cash). Ranking it
   is the job that already failed.
2. Clock-residual and capture-of-remaining will be `cannot_reach`.
   They pick efficient late scraps. Residualize FEATURES, not the
   dollar label.
3. `good_enough` (any y >= $600) is the interesting binary. Three
   cells per asset-day: if most cells contain at least one such
   name, a classifier plus a weak ranker among positives is a
   different job from AUC 0.87 among 15 paths.
4. Path-unit training after keep-first does not lower the ranking
   bar. Ticket 22 already measured that. Peer-relative features
   among the 15 are the new information, not the row count.
5. Isolated confirmation COMBINED is a local-defense score. The
   missing family is relative: which of the currently live paths
   is the phase extreme, prefix-only at the decision second.
   Causal extension as a threshold rule already failed. Relative
   rank of extension among born-so-far is a different object and
   is unmeasured.
6. Pivot-at-level (swing high/low vs finished PDH/VAL) was never
   scored. Confirmation-print |aligned| was. That is a feature
   family, not a keep-rule, and not a generator rewrite.

## Parallel diagnosis sessions

Fable 5 xhigh session `6f11e029-99cc-45f6-9998-050986c3b51c`
writes `design/entry_reset/FABLE5_XHIGH_LABEL_DIAGNOSIS.md`.

Opus 5 max session `18d4977a-f745-4f6d-857a-b1cfb0d7743c`
writes `design/entry_reset/OPUS5_MAX_LABEL_DIAGNOSIS.md`.

They diagnose first, unanchored. This receipt is sent on resume.

## What it printed (TRAIN, 2021). Cannot promote.

Receipt `artifacts/entry_v2/tabular_recovery/diagnostics/label_variants_20260822.json`
sha256 `ca83d2d2159f85db45eb5b793267be2ee7299cd2362d596063c2ed5b7a2a811d`.

Isolated Dawes COMBINED, used as a picker on the reduced cell, cashes
$-50 HG / $-160 NKD / $-267 SI. peer_early and clock_only are the same
score on HG and SI at this Δ (formation_sec and phase_remaining_sec
are collinear at a fixed age). That score cashes $490 HG and is
negative on NKD and SI.

| Label | HG letter / align | NKD | SI |
|---|---|---|---|
| raw_y / y_cell_z | aligned_chance $2781 | aligned_chance $1860 | aligned_chance $2409 |
| clock_resid | aligned_chance $2779 (same_as_ymax 0.94) | aligned_chance $1860 (0.89) | aligned_chance $2409 (0.91) |
| capture_remaining | aligned_separable $2199, Spearman vs clock 0.06 | cannot_reach $1465 | aligned_chance $2088 |
| cluster_max | aligned_separable $2224, Spearman vs clock 0.17 | aligned_separable $1627, 0.19 | aligned_separable $1613, 0.16 |
| good_enough | cannot_reach $1874 (59% of cells have a $600 name) | cannot_reach $778 (30%) | aligned_separable $1567 (58%) |
| sign_y | cannot_reach $1572 | cannot_reach $1070 | cannot_reach $1350 |

`aligned_separable` on capture and cluster_max is a 0.06-0.19 Spearman
against the clock. The clock as a picker does not print the rung.
Read those letters as "the clock slightly ranks a clock-related
transform", not as a ranking-grade family.

P1 (clock-resid as label is unaligned): REJECTED. Residualizing y
does not change the dollar argmax. Residualize or drop the clock in
the features.
P2 (good-enough classifier is enough): REJECTED on HG and NKD. Too
many empty cells. SI only, and barely.

## Verify

1. [selftest] → `python3 tools/probe_label_variants.py --selftest`
2. [real] → `OMP_NUM_THREADS=1 python3 tools/probe_label_variants.py --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix --out artifacts/entry_v2/tabular_recovery/diagnostics/label_variants_20260822.json`

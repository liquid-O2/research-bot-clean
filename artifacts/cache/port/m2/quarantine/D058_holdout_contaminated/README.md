# QUARANTINE — D-058 pre-exam-holdout contaminated artifacts

Moved here by THE ONE D-001 FIX PASS (census/forecaster sub-lane), 2026-08-14.
**Nothing in this directory may be quoted, joined, or re-published.** It is kept
only so the corrected numbers can be diffed against the numbers the program
already acted on.

## Why

D-058 names 2025-07-01..2025-12-31 the PRE-EXAM HOLDOUT: blind-only, touched
ONCE after entries/features/model freeze. The boundary constant existed and was
correct (`batch4_census.HOLDOUT_FROM_D8 = 20250701`, now `m2_common
.HOLDOUT_FROM_D8`), and five M2 modules simply never imported it. The
consolidated review numbered the consequences R105 and R118.

### pattern_census/ — R105 (p001 / p020 / p025)

* `p001_census.scan` enumerated `FIT_YEARS + (GATE_YEAR,)` with no date filter,
  so every `GATE_2025` census row, GEE row and Holm member pooled 2025-H2 with
  H1.
* `P001_FIRES.tsv` carried `MC.era_of(d8)` = the literal `HOLDOUT_2025H2`
  cid-by-cid: **the IDENTITIES of pre-exam holdout candidates were exported**.
  `REFUSED_FVOL_CENSUS.tsv` did the same at the (asset, era) grain.
* `p020_census` pooled the holdout through `concentration_rows`,
  `interaction_rows` and `p022_direction_rows`.
* `p025_census` flagged the holdout at the **WRONG BOUNDARY** (`>= 20250901`),
  and that understated figure is what the receipt (`n_holdout_sessions_in_gate`)
  and the report ("sessions from 2025-09-01 onward") stamped — July and August
  2025 were omitted from the count, so the adjudicator was handed an understated
  contamination figure. That is the one number the "flag, not a filter" defence
  rested on. The correct H1/H2 split existed in the file and was applied ONLY in
  `runway_rows`; `phase_given_runway_rows`, `phase_adjustment_rows`,
  `magnitude_rows`, `BATCH3_CENSUS.tsv`, `BATCH3_ROBUST.tsv` and the deciding
  NY-vs-runway GEE all used the pooled `GATE_2025`.

These artifacts are ALSO invalid for reasons unrelated to the holdout — the same
fix pass closed R106 (bare-ratio promotion with no inference), R107 (per-arm
Holm over three readings of the same object), R108 (a whole-session aggregate
eligible for "ENTRY RULE"), R109/R110 (denominator clamping and refusals
deposited in band zero), R111 (clipped `ext_needed` relabelling the strongest
breakouts as reversions), R112 (the mirror law absent), R113 (no cluster floor
before a GEE), R114 (in-sample thresholds presented as corroboration), R115
(ALL-era counts published at 2x), R116 (one shared permutation draw and dead
declared seeds) and R117 (within-session-constant terms stamped
NOT_LOAD_BEARING by construction). Every table here is superseded on all of
those grounds at once.

NOTE ON `P001_FIRES.tsv`: this file was never committed to git (the artifacts
tree is ignored). The copy preserved here is the post-fix schema written by a
12-session smoke run, not the contaminated original, which was overwritten
before it could be moved. The contaminated original's defect is documented above
and is reproducible from the pre-fix code at `5b31fee`.

### regime_forecast/ — R118

`regime_forecast.py` had **no holdout guard anywhere** (`grep -c
"20250701\|HOLDOUT"` returned 0): `build_sofar` walked `X.session_paths` with no
date filter, `era_of_year` mapped ALL of 2025 to `GATE`, every GATE metric
selected `years == 2025` (H1+H2), and — worst — the CONTINUING walk-forward
refits MONTHLY THROUGH 2025-12, so **holdout sessions were TRAINING ROWS** for
the `*_wfcont` columns the forecast tables publish. Measured on the quarantined
files: 131 / 393 / 471 rows dated >= 2025-07, max date 2025-12-31.

Every GATE number in `metrics.tsv`, `class_ci.tsv`, `pooled_class.tsv` and the
report — including CC-M2-14.1's acceptance evidence ("8/9 GATE, GATE generally
STRONGER") — is unusable as written.

## Replacement

The corrected engines route every enumeration through
`m2_common.guarded_session_paths` / `pattern_lib.sessions_fit`, which EXCLUDE
the holdout and RETURN the excluded count so the receipt declares it. The GATE
era is renamed `GATE_2025H1` everywhere, because it is a half-year and the name
now says so.

The rebuilds are long-running and are launched under `lab/run.sh`. The
regime-forecast rebuild is additionally BLOCKED on R80 (the fvol layer is being
rebuilt on D-054 sane mids by another lane); it must run after that lands, or
its anchor features and its `log_range_hat` / `fvol_share_*` inputs would be
rebuilt on the same insane mids R88 and R80 both name.

## What was moved (2026-08-14)

`pattern_census/` — 26 files (P001_*, BATCH2_*, BATCH3_*, P020_*, P021_*,
P022_*, P024_*, P025_*, REFUSED_FVOL_CENSUS.tsv and the three receipts).

`regime_forecast/` — `forecast_{SI,HG,NKD}.tsv`, `metrics.tsv`, `class_ci.tsv`,
`pooled_class.tsv`, `coverage.tsv`, `model_choice.tsv`, `two_run_identity.tsv`,
`regime_forecast.receipt.json`. The `sofar_*.tsv` / `truth_*.tsv` of the
contaminated build were overwritten in place by the corrected `test_regime.py`
fixture (which calls `build_sofar` / `build_truth`, and those functions write)
before they could be moved; both were then removed so the rebuild starts from
nothing. Their defect is documented above and reproducible from `5b31fee`.

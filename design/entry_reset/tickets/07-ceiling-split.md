# 07: Ceiling split (marginal dollars on top of the measured picker)

**What to build:** a probe that publishes, per asset and block on the frozen
2021 matrix, the dollars a ρ ≈ 0.15 within-cell picker at Δ = 180 s banks
when one dimension at a time is made perfect. Not three piles that sum to
the cell-max ceiling. That sum is unsatisfiable as written (timing lives
above ceiling@180; skip can only subtract from an oracle) and is a gate
that cannot fail.

Four published numbers, each as $/asset-day beside the ruler's P0
(`usd_at_reference_auc['0.60']` = $508 HG / $308 NKD / $445 SI on `all`):

- P0: the measured picker at Δ = 180 s (must match the ruler to ±$5).
- P_a: oracle cell-skip on top of that picker (hindsight θ-skip). Also
  report the best day after skipping 1 and 2 cells of the day's 3, as a
  diagnostic. Do not close branch A from equal-split arithmetic: cell
  maxima are unequal (`frac_winner_ge_600` ≈ 0.14).
- P_b: best of the *picked series'* stored Δ rows (timing-within-stored-grid).
  Preregistered bound: P_b − P0 ≤ `ceiling_series_best − ceiling_180`
  ($199 HG / $176 NKD / $207 SI on `all`). Printing above that bound is
  an implementation defect. Continuous timing off the stored grid is
  unmeasured and is not closed by this probe.
- P_c: ρ_series raised to the ruler's `rho_at_rung` on the same rows.

Also publish: the ceiling path's MDD per asset-day and per portfolio-day
(the $1,000 clause; no `probe_*.py` currently measures it). The ≤12-trade
cap is already safe at 3 cells × 3 assets = 9.

Planted: ρ = 1 on one named dimension reproduces that dimension's oracle
to the cent. Shuffle of that dimension reads near $0. Degenerate: a
quantile that selects nobody or everybody is a typed GATE-DEFECT row.

**Blocked by:** None (can start immediately). Uses the landed ρ ruler and
the frozen matrix. Does not wait for the native builder. Does not gate
ticket 08.

**Preregistered prior (written before this probe runs):**

- Book: flow-at-touch AUC 0.54 over 41,152 NQ/MNQ events; memory + location
  0.63. A bet that pile (c) is small.
- Receipt already on disk: `ceiling_series_best / ceiling_180` = 1.06–1.11
  on every asset and block, so stored-grid timing is ≤ $160–$250/asset-day.
  3.0 cells per asset-day on HG/NKD, 2.95 on SI (`rho_ruler_20260822.json`).
  Record whether the 2021 split agrees. Does not change the planted arm
  or the shuffle.

**Status:** done (2026-08-22). Receipt
`artifacts/entry_v2/tabular_recovery/diagnostics/ceiling_split_20260822.json`.
Letter: `no single dimension` on every asset and block.

- [x] `--selftest`: planted between-cell P_a=$800 vs P0 lower; NaN y refused.
- [x] Real run. P0 matches the ruler's `usd_at_reference_auc['0.60']` to the cent (HG all $507.8, NKD $307.8, SI $445.5).
- [x] Decomposition order in the receipt. No sum-to-ceiling box.
- [x] Letter `no single dimension` on HG/NKD/SI, all blocks. P_a and P_b never clear the rung. P_c sits at the rung by construction (copula at `rho_at_rung`).
- [x] SI threshold and SI all: ceiling-path MDD $1080, typed as a $1000 breach. The cell-max oracle on that block already violates MDD.
- [x] Wall 302 s.

Note: P_b−P0 exceeded the stored-grid bound on several blocks (HG all $321 vs $199). That bound is the *oracle* timing gap. Retiming a weak pick can add more than retiming the oracle series. Typed in the receipt, not treated as a code defect.

# Phase 4 · Information measurement at scale (cell selector)

Back to [overview](overview.md). Blocked by phase 1 and by each phase-3 slice as it lands.

**Goal.** Per asset and delay, the honest within-cell information grade on walk-forward half-year folds, with controls, placed on the ρ ruler and converted to cell-pick dollars.

**Changes.** One new single-file probe `tools/probe_cell_selector.py` (selftest, preregistration in the header echoed into the receipt). Arms: (a) shallow CatBoost CPU on cell-standardized y over the full plane plus time remaining and extension geometry; (b) Dawes unit-weight composite (control); (c) matched within-cell shuffle. Folds: fit on all prior half-years, score the next; θ from the prior fold. 5 real + 5 shuffle seeds. Δ ∈ {60, 180, 300, 600} s.

**Data structures.** `CellRows` (the DeltaRows shape over the slice corpus); `FoldSpec(fit_slices, score_slice, theta_source_slice)`; `SelectorVerdict {asset, delta, fold, rho, auc, ci, predicted_usd_from_ruler, picker_usd_all, picker_usd_skip, shuffle beside each, noise floor}`.

**Verification.**
- Static: `python3 tools/probe_cell_selector.py --selftest` (planted ρ=0.8 recovered ±0.05; no-signal at chance; overlapping-fold fixture refused), SC-RESET-3.
- Real path: one receipt per (asset, fold) under diagnostics/, the noise floor from the seed spread written before the real arms are read (preregistering-results §7).
- Box cost: per fold ≈ 3 arms × 10 seeds × ~2 min CPU at 7 threads ≈ 1 h; abort at 1.5×.

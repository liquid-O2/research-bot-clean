# 04: Information measurement at scale (cell selector)

**What to build:** a single-file probe that, per asset and Δ ∈ {60,180,300,600} s, fits a shallow within-cell selector on walk-forward half-year folds (fit on all prior half-years, score the next) with a Dawes composite control and a matched within-cell shuffle, 5 real + 5 shuffle seeds, and reports ρ/AUC with day-bootstrap CIs placed on the ruler, plus exact cell-pick dollars (enter-all and θ-skip, θ from the prior fold).

**Blocked by:** 01, 03 (runs per slice as slices land).

**Status:** blocked

- [ ] `--selftest`: planted ρ=0.8 recovered within ±0.05; no-signal fixture at chance; a fold whose fit days overlap its scoring days is refused (SC-RESET-3).
- [ ] Noise floor from the seed spread written in the receipt before the real arms are read.
- [ ] Receipt per (asset, fold, Δ): ρ, AUC, CI, predicted $/asset-day from the ruler, realized cell-pick $/asset-day, shuffle beside it.
- [ ] Features include time-remaining and extension geometry; no teacher/outcome-named column can load (existing refusal).

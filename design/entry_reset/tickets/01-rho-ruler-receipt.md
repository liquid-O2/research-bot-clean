# 01: ρ ruler as a receipt tool

**What to build:** a single-file probe that turns the score-quality bar into a preregistered receipt: for each asset and block of the frozen matrix, the within-cell ρ (and the same score's winner-vs-loser AUC) a one-entry-per-phase picker needs to reach the ladder rung and 80% capture, plus the dollars a supplied AUC buys.

**Blocked by:** None (can start immediately).

**Status:** done 2026-08-22 (receipt `diagnostics/rho_ruler_20260822.json`, sha 8cd0de58…)

- [x] `--selftest`: ρ=1 reproduces the cell ceiling to the cent; ρ=0 inside the random band; a matrix with a non-finite y anywhere is refused with a typed error naming the count.
- [x] Real run writes the receipt with the preregistration echoed; ρ@rung per asset/block matches overview.md §Evidence (SC-RESET-1).
- [x] Receipt carries the AUC column beside ρ and the flat-by-phase-close violation count (0).

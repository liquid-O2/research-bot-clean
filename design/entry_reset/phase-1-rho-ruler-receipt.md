# Phase 1 · ρ ruler receipt (landed 2026-08-22)

Back to [overview](overview.md).

**Goal.** Turn the score-quality bar into a preregistered receipt so every later diagnostic number converts to dollars before it is believed.

**Changes.** One new single-file probe under tools/, shaped like the cell noise ruler, reusing the trained-accrual probe's matrix loader and cell-pick walk. No engine change.

**Data structures.** `DeltaRows` (existing: one row per series at Δ with y, cell, day, elapsed, occupancy, series-best); the receipt schema `QRE2RHORULER1` with per (asset, block) anatomy, ρ curve, ρ*/AUC* at rung and 80%, dollars at reference AUCs, and the flat-by-phase-close violation count.

**Verification.**
- Static: `python3 tools/probe_rho_ruler.py --selftest` (ρ=1 reproduces ceiling@180 to the cent; ρ=0 inside the random band; 0 flatness violations; NaN-y fixture refused). Seen red first on the ceiling assertion, then green. Seen red a second time on the NaN fixture, fixed by widening the refusal to series-best values.
- Real path: `python3 tools/probe_rho_ruler.py --matrix-dir $M --out $OUT/rho_ruler_20260822.json` → receipt sha 8cd0de58…, SC-RESET-1.
- Box cost: ~10 min CPU. Done.

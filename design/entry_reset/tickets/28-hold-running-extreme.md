# 28: Hold the running extreme (phase-scale)

**What to build:** the two-stage rule in
`design/entry_reset/SELECTION_HOLD_EXTREME_20260822.md`. Score is
session/phase VWAP-aligned among keep-first names, not prior-session
extension. MAX_EXT at 180 s is already $1411 HG / $1103 NKD / $1521
SI TRAIN (`extension_prior_20260822.json`) and cannot print.

Stage A: 2-name VWAP-extreme oracle (short max aligned, long min
aligned), cash 180 s y. If TRAIN is under the rung, letter
`vwap_oracle_insufficient` and stop.

Stage B: only if Stage A cleared. Causal hold of that score, H from
TRAIN only, in minutes. THRESHOLD is the verdict. Null shuffles
which name is treated as the extreme. Cash is 180 s y (matrix ages
stop at 300 s; letter `cash_is_age180_proxy`). NKD may letter
`prefix_too_thin` if H is capped so late names never enter.

**Blocked by:** tickets 25, 26, 27 (the wait table and the prefix
ceiling). Spend halt: do not run until the user lifts spend.

**Status:** ready-for-agent. Score corrected 2026-08-22 night.

- [ ] `--selftest`: planted VWAP-extreme runs then holds; Stage A
      cashes the 2-name oracle; Stage B cashes the hold; NaN y
      refused; Stage B refused when Stage A is insufficient
- [ ] Real run writes
      `diagnostics/hold_running_extreme_20260822.json`
- [ ] Stage B not run if Stage A missed the TRAIN rung
- [ ] H not chosen on THRESHOLD
- [ ] 2021 not used as promotion

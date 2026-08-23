# Gates: ticket 44 — is the winning feature a tautology?

Scope: the user flagged `disc_prior_high_aligned_usd` as suspicious. There is a
specific mechanism that would make it worthless, and it must be tested before
the corpus build spends four years of data chasing it.

THE MECHANISM. `aligned = side * (mid_entry - level)` and
`y = side * (mid_exit - mid_entry)`, so `y + aligned = side * (mid_exit - level)`.
If exit and level are both cell-constant, then within a cell `y = c - aligned`
exactly, and ranking by most-negative aligned IS ranking by highest y with no
information whatsoever. Registered class: `tautological-label`.

- [ ] L1: the within-cell relation is measured — correlation of y with -aligned,
        and whether var(y + aligned) collapses against var(y)
  EVIDENCE: pending

- [ ] L2: THE DECISIVE CONTROL — a PLACEBO level. Replace the prior-session high
        with an arbitrary fixed price. If the edge survives an arbitrary level,
        the level carries nothing and the signal is the entry price
  EVIDENCE: pending

- [ ] L3: leakage audit of the level itself — `prior_high` is established BEFORE
        the current session opens, read from source not assumed
  EVIDENCE: pending

- [ ] L4: the verdict is recorded either way, and if it is a tautology the
        ticket-39 result is retracted in START_HERE, STATE and CURRENT rather
        than quietly left standing
  EVIDENCE: pending

- [ ] L5: battery green
  CHECK: bash /workspace/tools/run_all_checks.sh --fast 2>&1 | tail -2
  EXPECT: ALL CHECKS GREEN
  EVIDENCE: pending

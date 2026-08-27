# Sweep 2 spec, as dispatched. Fable, 2026-08-27.

Record of the sweep-2 contract handed to the Opus builder (in flight when this
page was written). Full text lives in the session dispatch; these are the
binding definitions.

## Corrected side object

Per cell and side on the 60 s lattice, cert(s,t) from the frozen outcome law.
REM(s,t) = max over lattice tau >= t of cert(s,tau), reverse running max, in
an UNRESTRICTED variant and a LEGAL variant (only tau with a formed side-s
CLEAR candidate by tau). Delta*(t) = REM(+1,t) - REM(-1,t), primary variant
LEGAL. Ambiguity band |Delta*(t)| <= max(2*cost(t), 100). This replaces the
sweep-1 enter-now Delta(t), whose late-phase decay made stability land at
92-94% of the phase (Sweep 1 ruling, charter).

## Stages

- N1: stability map on sign(Delta*): first-stable seconds and phase fraction,
  flip histogram, agreement of the sign at 900/1800/2700/3600 s with the
  final stable sign, REM magnitudes.
- N2: labelled-oracle prize of the two-stage law: side = sign(Delta*(tau)) at
  tau in {900,1800,2700,3600}; entries AT-TAU, EVENT (first new adverse
  running extreme bar >= tau), EVENT+1 (one-bar confirm, >= 4 ticks back
  toward the side); legality at the entry bar; abstain if no event by
  phase_close - 1800 s.
- N3: value-coverage and error-injection budget rerun on the best N2 event
  line per asset (sweep 1 ran both on the crumbs line).
- N4: relabel of sweep 1's 78 zero-fit detector configs against
  sign(Delta*(T_fire)), no cash.
- Stage F: first fitted family. Selective walk-forward L2 logistic (IRLS,
  lambda 1.0, no tuning), 13 causal bar features, label sign(Delta*(tau)),
  taus {1800,2700,3600}, per-asset chronological walk-forward inside EXPLORE
  (min 20 train days), abstention margin calibrated on train to conditional
  error targets {1,2.5,5,10}%, call must persist one bar.
- Stage B: price only per-asset selected (tau,e) with EVENT entry, plus F4
  gate and EVENT+1 variants; engine replay on the selected line; fixed-seed
  block-permutation nulls with max-statistic; all rows logged, verdicts left
  for the parent.

Laws carried from sweep 1: 60 s completed bars, strictly-before sampling,
formed same-side candidate legality, one entry per cell, seed 20260827, same
hash fields in the log, parent_trial sweep1-090.

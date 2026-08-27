# Sweep 4 spec, as dispatched. Fable, 2026-08-27 overnight.

Record of the sweep-4 contract (in flight). Binding essentials; laws carried
from sweeps 1-3 unless stated.

## Entry grain change

Every entry in sweep 4 is candidate-anchored: entry timestamp is a CLEAR
candidate's own decision_ts_ns, quote is the last trusted row strictly
before it, cost from that row's spread, side is the candidate's side.
Legality is inherent. This is the deployable form and the S0 form; the
sweep-3 review caught the drift to bar-mid entries.

## Stages

- O4a S0-replica oracle: best-priced winner-side candidate at its own
  decision moment, per asset and per phase, reconciled against S0's era
  numbers (2753/3806/3869) and the REM ceiling.
- O4b delay tolerance: first winner-side candidate formed d minutes after
  the terminal extreme, d in {0,5,10,15,20,30,45,60}. The recognition-delay
  budget curve.
- O4c terminality separability, no cash: quiet-time distributions after
  terminal vs non-terminal extremes, the false-positive curve a quiet-Q
  detector faces at Q in {10..60} minutes, zone- and shallow-band-
  conditioned variants, and post-extreme retrace stats.
- Stage A: detector D(Q,H,k,zone): an extreme is detected terminal after Q
  quiet minutes with a retrace holding H ATR for k bars; zone optional
  (prior-day-level band union shallow band); entry = first fade-side
  candidate after detection; newer extreme cancels and re-arms. 72 configs.
  Metric: terminal-hit rate (no new adverse extreme between entry and phase
  close), coverage floor 0.30, delay. No cash in selection.
- Stage B: price selected + runner-up + per-phase-Q variant (each phase
  chooses its own Q by the same no-cash rule; the per-session directive),
  engine replay, 2% adversarial stress, block-permutation nulls, capture
  ratio against the delay-matched O4b oracle.

## Why this shape

Sweep 3's ladder: REM 2692/3600/4230; terminal-fade at bar grain 1844/2209/
2475 (HG misses even there); last-in-zone 971/793/1609; best causal 163.
First in-zone extreme is terminal ~5% of the time; walls vanish at true
terminal entries. The two live questions are entry grain (candidate vs bar)
and slow terminality recognition, which sweep 2 never actually tested
because its selection minimized delay.

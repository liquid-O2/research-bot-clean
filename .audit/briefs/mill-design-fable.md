# Fable's causal policy design, written before Sol's second page. 2026-08-27.

USER directive: clear every rung causally - no oracle bits - then push margin
toward the goal. This page is Fable's independent decomposition and design,
registered before reading `.audit/briefs/mill-design-sol-out.md` so the
comparison is genuine. Evidence base: the frontier, sweep 1, and the charter
rulings. Sweep 2 is in flight; where a number is pending, the dependence is
named.

## What the $1,664 line is, exactly

Sweep 1's M2 line at tau=1800 (SI 1664.6 / NKD 978.5 / HG 1039.0 usd per
asset-day, MDD 385/410/160, win 88-98%) contains TWO oracle bits and two
causal parts. Oracle: (1) the side, sign of the enter-now cert difference at
tau, read from the future; (2) the abstention, cells skipped when that
hindsight difference is inside the cost band - the "is this cell decidable"
bit is also read from the future. Causal: the fixed clock and the entry
legality (formed same-side candidate, market fill, frozen cost). So it is NOT
achievable as-is. Its value is exact: it upper-bounds the whole class
"call side at minute 30, enter at market" - and even the oracle version of
that class fails HG (52% of rung) and NKD (65%). The class is insufficient
for the goal with a PERFECT caller, which is why entry timing (D3 below) is
load-bearing, and why the causal work splits as follows.

## Decomposition of the residual problem

- **D1 side information.** At tau=1800-3600 s on unambiguous cells, no
  zero-fit statistic beats a coin (sweep 1 stage A: error 0.43-0.51). Open:
  whether a fitted selective caller on multi-scale summaries clears a
  calibrated conditional-error bar at usable coverage (sweep 2 stage F), and
  whether the sign of the remaining-best object Delta* is more predictable
  than the enter-now sign it replaced (sweep 2 N1/N4).
- **D2 decidability/abstention.** The oracle line's coverage restriction
  (~50%) is what lifts per-trade means to 581/707/1121. Causally this is a
  prediction of |Delta*(tau)|, not of its sign. Candidate causal proxies:
  realized one-sidedness |U-D| in R0 units, running range vs R0, candidate
  one-sidedness, forecast regime. Evidence pending: stage F reports mean
  |Delta*| on called vs abstained cells - if confidence correlates with
  |Delta*|, D1's caller buys D2 for free.
- **D3 entry timing inside the side.** Fixed-tau market entries capture
  about half of best-entry per-trade value (M2 per-trade 581/707/1121 vs
  best-per-side means 599-1014; frontier decay vs best). The wall gradient
  (d1 0.04-0.17 vs d5 0.43-0.60) says the missing half sits at entries near
  fresh adverse extremes. Pending: N2's two-stage oracle table - if oracle
  side + EVENT entry reaches ~2x fixed-tau per trade, HG's 2000 becomes
  arithmetically reachable at ~50-60% coverage.
- **D4 HG specifically.** HG's rung is 72% of its ceiling; oracle side at
  fixed tau gives 52% of rung. HG cannot clear without D3, and may also need
  D2 shaped toward value (F4/forecast gates) and possibly later-tau side
  calls (persistence accuracy 0.57-0.60 at 5400-10800 s) IF event entries
  preserve per-trade value at those hours (N2 tau=3600 row is the test).
- **D5 the wall budget.** ~2% adversarially-placed wrong calls breach MDD;
  5% is fatal (sweep 1 M4 grid shape; rerun on real lines in N3). This binds
  D1+D2 jointly: the caller must run at 1-2.5% conditional error on called
  cells, with coverage as the free variable, and EVENT entries reduce the
  damage of residual wrong calls (adverse-extreme entries wall least even
  when wrong).

## The design: LADDER (three causal components, one policy)

Per cell, per completed minute from tau0=1800 s:

1. **C1 decidability gate.** Causal score g(t) = w1*|U-D|/R0 + w2*log(range/
   R0) + w3*|candidate count imbalance| (weights fit inside the stage-F
   walk-forward, or unit weights if the fit adds nothing). Cell becomes
   eligible when g crosses its per-asset threshold, calibrated on train days
   to keep coverage in a band (target 40-60%).
2. **C2 selective side call.** The stage-F caller (L2 logistic, 13 features,
   walk-forward, margin calibrated to conditional error <= e) on eligible
   cells; e per asset chosen against the N3 budget; call must persist one
   bar. No call by phase_close - 1800 s means abstain forever.
3. **C3 event entry.** After the call, enter at the first bar whose mid sets
   a new running extreme adverse to the called side (EVENT law), one-bar
   confirm variant if N2 favors it; entry legality at the entry bar; miss
   the entry if no event arrives (this is D2 insurance: no event = the
   adverse run never terminated cleanly = stand aside).
4. **C4 composition.** Per-asset (tau0, e, gate) parameters; F4/forecast
   value gate only if the N3 value-coverage curve on the two-stage line
   shows value-targeting beats random abstention; one entry per cell, caps
   inherited.

Kill bar for LADDER on EXPLORE (pre-registered): every asset must post
usd/day >= rung with day-ordered and trade-ordered MDD < 1000 and
block-permutation-null max-adjusted p <= 0.05 on the pooled drawdown, all
under walk-forward causal fits. Anything less is UNRESOLVED or KILL; a KILL
routes to the F3 level-structure sources (priors store, forecast join - not
yet cached) and then to the F6 fused filter per the charter axiom, never to
"unreachable".

## What would change this design

- N1 showing Delta* stabilizes late too -> the side is genuinely a
  late-phase fact; move tau0 later and lean fully on D3's per-trade capture.
- N2 two-stage oracle failing HG -> D3 alone cannot close HG; route HG to
  level/forecast context (F3) before any fitted caller is trusted there.
- Stage F conditional error floor >> 2.5% at any coverage -> the 13-feature
  plane does not carry the side; route to F3 features, then F6.

Registered before Sol's page. The synthesis after both exist picks per
component, not per page.

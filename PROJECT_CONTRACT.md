# Project contract

## Economic objective

The deployable policy must satisfy all of the following on the registered
chronological evaluation:

- mean net strictly greater than $2,000 per official session;
- zero-inclusive cumulative end-of-day maximum drawdown strictly below
  $1,000;
- one-position chronological replay with variable, uncapped entry count;
- IWM as the sole scientific clock and executable price authority;
- 576 cents round-trip cost applied exactly once, with embedded adverse-side
  fills;
- an executable $300 adverse stop monitored causally and filled at the next
  lawful mark after crossing; gap-through is permitted, retained, and
  reported;
- all zero-trade and unavailable sessions remain in the denominator;
- concentration, leave-top-ten-out, minimum-year, zero-day, gap, and tail
  panels are promotion prerequisites.

$1,600 per session is a diagnostic rung only. It is not the project goal.
RTY-mini values are scenario arithmetic only; RTY market payload is forbidden
from fitting, features, labels, calibration, diagnosis, and promotion.

## Data and clock walls

- Registered scientific sessions are the 1,003 official sessions in
  2022–2025. Sessions 0–124 are burn-in.
- Raw 2026 market payload is never read. The separately governed forward
  escrow may open only under its committed protocol.
- All timestamps pass through `corpus::SessionClock`. Naive ET, UTC, and
  same-civil-day attachment clocks are not interchangeable.
- Strict-prior means strictly earlier. Equal timestamps are unordered and
  receive a typed state.
- Attached quote and underlying observations carry their own clocks and
  validity. Missing, malformed, equal, future, stale/aged, crossed, locked,
  and one-sided states cannot silently become valid.
- LOW means long and HIGH means short. Side must be authenticated from a
  causal authority, never reconstructed from a later roster.

## Evaluation and contamination

- Use `fold_registry_v2` with a two-session embargo.
- Feature/model/policy selection uses development folds only.
- Fold 6 is one-shot selected-policy confirmation.
- Fold 7 is burned/contaminated-confirmatory and is labelled as such.
- Dollar-based selection is forbidden with fewer than 200 inner-validation
  sessions; differences below $100/session are unresolved.
- Preregistration is committed bytes. A runner refuses dirty or mismatched
  specifications.
- Every policy is evaluated through the same uncapped one-position replay;
  no oracle exit, selected-row denominator, trade cap, or alternate fill
  kernel may substitute.

## Readiness claim

“Greater than 90%” may only mean a preregistered empirical readiness
probability computed from complete out-of-fold daily ledgers under the full
joint economic contract, with dependence-aware block resampling and a
conservative lower confidence bound. It is not a mathematical guarantee.
No readiness claim is permitted until the exact estimator, model-selection
family, stop/exit policy, folds, and independent confirmation are frozen.


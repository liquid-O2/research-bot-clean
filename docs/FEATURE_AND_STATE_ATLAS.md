# Feature and state atlas

This atlas describes the information families to test. It is not an
authorization to implement every coordinate. Each family must pass the
value-per-budget law in the project contract.

## Common causal state

- Session progress, seconds/minutes from open, remaining session time.
- Decision second and nonlinear authority decision ordinal.
- Strict-prefix local high, low, range, realized variation, and lawful VWAP.
- Candidate side, policy, reversal magnitude, visible age, active member
  count, oldest/newest/mean age, prefix-only sibling/member union.
- Counts by the fixed primitive policy vocabulary and authenticated side.
- Typed opening/left-pad, unavailable target, inactive, and quality states.

No final cluster disposition, final size, UNION-derived action, selected
matrix roster, or later-visible sibling field is admitted.

## NBBO path

State is built from equal-timestamp groups and keeps:

- bid, ask, midpoint, spread, bid/ask sizes and imbalance;
- own/opposite role orientation under LONG/SHORT;
- changes from the nearest strictly earlier eligible group;
- interarrival, group multiplicity, sequence quality and inversions;
- depletion, refill, persistence, locked/crossed/one-sided/condition states;
- approach/current/response phase relative to candidate visibility;
- recent exact groups plus complete 120 one-second bins;
- per-channel masks, valid fractions, ages and omission fractions.

Derived midpoint/imbalance follows separate scalar group means. It is not the
mean of row-derived values.

## Stock-print path

- Eligible price and size, return from strictly earlier eligible timestamp
  group, direction and aggressor state.
- Signed size, unsigned size, notional, intensity and interarrival.
- Print-mid displacement, quote age and attachment validity.
- Price/flow persistence, acceleration, reversal, burst and confirmation.
- Prefix VWAP and distance from VWAP only from eligible prints.
- Counts/quality for noneligible condition classes, invalid price/size, tied
  or unavailable aggressor references.

Prints with disallowed conditions remain in the physical denominator but
cannot update directional return/flow/VWAP state.

## Option-print path

- Expiration, strike, right, price, size and sequence.
- Strictly causal single-leg sign recomputed from lawful quote/tick state.
- Delta, gamma, vanna, charm and IV only with their dependency masks.
- Underlying return from strict-prior valid attached observations.
- Moneyness/expiry structure derived causally where source fields permit.
- Contract/right/expiry/strike grouping, intensity, interarrival and
  confirmation against stock/NBBO.
- Recent exact groups, full-window one-second bins and typed availability.

Persisted vendor side, sweep identity/count/size, premium flow and Greek-flow
aggregates are excluded. Any field derived from quote or underlying data
inherits the corresponding invalid/equal/future/missing mask.

## Option-quote and volatility state

Where the registered coverage permits:

- bid/ask price, size, spread, midpoint and quote age by contract;
- lawful bid/ask IV and skew/surface summaries;
- term, moneyness, right and liquidity state;
- quote-to-print and option-to-stock confirmation;
- dispersion and change in the surface, not only a scalar IV level.

Sessions without native option quotes retain `MODALITY_ABSENT`. Slow volatility
forecasts with forbidden fold dependencies or incomplete scope stay typed
blocked. RUTW and cross-asset context are not IWM causal features.

## Order, persistence and phase

Candidate mechanisms frequently depend on:

- what happened first;
- whether state persisted or mean-reverted;
- whether intensity accelerated;
- whether liquidity withdrew then refilled;
- whether stock and options confirmed in the same phase;
- whether a signal appeared before, at equal unordered time, or after the
  candidate became visible.

Direct summaries preserve a curated approximation. Native encoders receive:

1. the most recent exact timestamp groups;
2. all complete one-second bins over 120 seconds;
3. explicit masks and ages;
4. phase and candidate-set context.

Matched bin reversal and within-bucket permutation must operate on the actual
constructor output, not synthetic counts.

## Conditional interactions

At minimum compare:

- state-only;
- state + stock/NBBO additive;
- state + option additive;
- all modalities additive;
- bounded low-rank or cross-attention interaction;
- dynamic policy head.

The interaction arm must expose named operands, bounded rank/capacity, and a
matched operand derangement that leaves marginal/additive predictions
unchanged. Examples include:

- stock direction × option directional pressure;
- liquidity refill × aggressive print burst;
- candidate age × cross-modal confirmation;
- volatility/surface regime × tape response;
- phase/persistence × reversal magnitude.

## Quality as signal and guard

Availability can carry regime information, but it can also leak a
destruction or roster. Quality states therefore travel explicitly and are
matched in controls. Every fraction declares its numerator, denominator and
zero-denominator state. Binary presence masks are never normalized away or
silently zero-conflated.


# Project memory

This file is the durable reasoning memory for the Russell causal-selection
program. It is deliberately more than a status report. It records how to
think, what the evidence actually says, why prior work failed, and how to
avoid repeating scientifically invalid shortcuts.

The historical shorthand “Ivy/IV stuff” must not be narrowed to implied
volatility. It refers to the broader discussion that used IV-conditioned tape
response as one example of the required method: start from a trading
mechanism, preserve evolving raw state, build lawful transformations, test
conditional interactions, compare machine-native alternatives, and let
matched falsification—not a familiar feature list—decide what survives.

## 1. Start from the decision, not the available table

The objective is not to classify a convenient historical label or reproduce
an oracle. The objective is to choose, at each causal decision time, whether
to enter IWM, on which authenticated side, under a fixed executable risk and
exit law, so that the complete chronological replay satisfies the economic
contract.

Work backward:

1. Freeze the action, observation clock, risk/stop, exit, fill, cost, overlap,
   and evaluator.
2. Ask what latent market mechanism would make that action valuable.
3. Identify which raw observations can reveal that mechanism strictly before
   the action.
4. Preserve the state and interactions needed to distinguish the mechanism
   from a coincidental marginal correlation.
5. Design matched destructions that remove only the claimed information.
6. Prove the exact architecture can learn a known signal on the same path.
7. Only then inspect lawful out-of-fold economics.

Feature generation is therefore a scientific modelling task, not a column
enumeration exercise.

## 2. The central representation lesson

The raw data are evolving, irregular, multi-modal state. Aggressive
aggregation can erase the information we are trying to test:

- event order and equal-time grouping;
- age, persistence, acceleration, refill, exhaustion, and reversal;
- approach versus response to a candidate event;
- agreement or conflict between stock, NBBO, option prints, and option
  quotes;
- which side owns a quantity and how roles swap under SHORT orientation;
- attachment-clock quality and the difference between absent, stale, equal,
  future, malformed, locked, crossed, and one-sided observations;
- conditional signal that is weak or absent in each modality marginally but
  strong in their interaction.

A null result from minute summaries, whole-second bags, side-blind latent
sign flips, or additive marginals does not show that the raw path lacks
information. It shows only that the exact representation tested did not
extract useful information under its exact clock, roster, target, and model.

The lawful ladder is:

1. location/clock and causal candidate-set state;
2. curated direct summaries;
3. capacity-matched direct control;
4. native ordered state for each modality;
5. explicit conditional cross-modal interactions;
6. dynamic ENTER/WAIT/PASS policy.

Each rung uses the same immutable decisions and targets. Each addition has a
matched destruction and a measured cost.

## 3. Interaction-first thinking

Many plausible mechanisms are conditional:

- option buying matters differently when stock tape confirms versus rejects;
- aggressive prints matter differently when quote depth refills versus
  withdraws;
- a reversal signal may be useful only at a particular candidate age,
  volatility state, or distance from the local range;
- IV or skew state may change the meaning of directional option flow without
  being directional by itself;
- persistence, order, or phase may carry signal even when pooled counts are
  identical.

Do not ask only whether stock, option prints, option quotes, volatility, or
candidate state is individually predictive. Test the interaction while
holding the marginal information fixed. A valid operand destruction
deranges one operand within matched session/clock/side/availability buckets
and leaves each marginal and the additive logit untouched. An XOR harness
must be solved by the interaction arm and remain chance for the additive arm.

“No marginal lift” never closes the conditional-interaction family.

## 4. Native state, curated summaries, and budget

Native grain is honored in the streaming pass: every lawful token is read and
classified. This does not require an exhaustive coordinate grid. Outputs are
curated, typed, budgeted carriers:

- recent exact timestamp groups for microstructure;
- complete left-closed/right-open one-second bins across the full causal
  window;
- finite direct summaries with explicit formulas and denominators;
- masks and quality states travelling with every value;
- invariant pooling for unordered equal-time or candidate sets;
- ordered encoders only where chronology is defined.

Before implementing a family, register its mechanism hypothesis, operation
count, projected wall time, memory, output size, feature count, and kill
threshold. More than 20% of the pipeline wall without decisive incremental
value is a kill condition. “Use all hardware” means measured parallel work
with bounded memory and file descriptors, not duplicate scans or unmeasured
GPU occupancy.

## 5. Causal clock law

IWM and `corpus::SessionClock` are authoritative. Every observation carries
the clock on which it became knowable.

- Strict-prior means `observation_ts < decision_ts`.
- Equal timestamps are unordered; source sequence or row order cannot invent
  chronology.
- Timestamp groups are reduced permutation-invariantly and prior state is
  updated only after the full group.
- A complete-second carrier excludes the partial current second.
- Attached quote and underlying timestamps are dependencies, not decoration.
  Invalid dependencies mask every derived field that relies on them.
- A non-null wrong-civil-day attachment is retained as typed invalid, never an
  exception that removes its print.
- 2026 payload is never opened.

Typed states are part of the representation and denominator. They are not
silently converted to zero.

## 6. Side and episode identity law

LOW maps to LONG; HIGH maps to SHORT. Side must come from a strictly causal
member/event authority. Later matrix authorization, final cluster
disposition, final cluster size, or a same-side replacement episode is not a
lawful substitute.

Admit each primitive candidate at its own visibility. Build the visible
candidate/member set from prefix-known members only. Final
DUPLICATE/CONFLICT/UNION fields are census-only because later-visible siblings
can affect them. Authenticate the raw candidate physical-event key against
every member key; singleton and multi-member split mutations must fail.

The prediction key is the exact authority tuple
`(session_ordinal, decision_ordinal, explicit_side)` with timestamp and
decision-second equality checked. `decision_ordinal` is not seconds from the
open.

## 7. Market-field dependency law

Stock prints contribute price/return/aggressor/signed-size/VWAP mechanisms
only when the production condition class, price, size, and reference state
are eligible. Ineligible rows stay in quality counts.

Quote signing requires a strict-prior, finite, positive, two-sided,
condition-eligible, unlocked and uncrossed quote. A missing, tied, or invalid
reference does not produce a resolved zero aggressor.

Option persisted `side`, sweep metadata, premia flow, and precomputed Greek
flow are forbidden causal shortcuts. Recompute only from the safe raw
projection. Quote and underlying dependencies must be strict-prior and valid;
all derivative fields inherit their masks. Equal-time fallback is forbidden.

Implied volatility is one example of this general rule. It may be a state or
interaction operand, but it is not automatically causal, directional, or
available. Exact bid/ask IV is used only when its source and inversion are
lawful. Missing IV does not imply missing option information. A test without
native quote/strike/expiry structure cannot close IV-mediated mechanisms.

## 8. Teachers, oracles, and privileged information

An oracle answers “does a valuable action exist under hindsight?” A leakage
teacher answers “can this architecture learn a signal when the answer is
placed in its input?” Neither answers “is the answer observable from the
causal prefix?”

The approximately 0.999 AUC results were deliberate future-outcome leakage
controls after sufficient optimization. They validated data flow and model
capacity. They were not causal prediction results.

Certificate and delayed-entry oracles showed substantial hindsight
opportunity, but certificate exits use future information. They are ceilings
and diagnostics only. Privileged teachers may suggest structure or
distillation targets only to the extent that the student can predict them
from legal inputs; teacher performance cannot be transferred by assertion.

## 9. Proxy firewall

Every claim binds one scientific object:

`population × clock × modality × representation × target × action × exit ×
risk × fill/cost × folds × selection × evaluator`.

Changing one component creates a different object. In particular:

- a fixed 15-minute target is not a certificate target;
- a certificate entry selected for its own exit is not a fixed-exit oracle;
- a whole-second action is not a native subsecond action;
- an active same-side row is not proof that the same episode survived;
- selected-only rows are not the immutable decision denominator;
- a barrier-order auxiliary label is not continuous action value;
- an oracle ranking is not a causal-entry metric;
- an aggregate null is not a raw-state impossibility result.

Proxy and ceiling results remain useful when labelled precisely. They cannot
adjudicate a neighboring question.

## 10. Risk, replay, and EXIT/HOLD

Risk is joint with entry and exit. The $300 stop is monitored causally and
filled at the first lawful mark strictly after crossing; gap-through loss and
path MAE are retained. Realized MAE cannot be used to select the roster or
training rows.

Replay is global chronological one-position occupancy. Exact score ties
abstain. Same-action duplicates collapse by a frozen causal rule; distinct
equal-time actions do not break ties by ID, hash, source order, or outcome.
Costs are charged once. Zero-trade days start at zero and participate in
drawdown.

If fixed exits cannot meet the contract, a dynamic EXIT/HOLD policy is a
separate causal decision problem. Its value target must include both current
position continuation value and the opportunity cost of blocking the next
entry. It must not be approximated by the old exhaustion/RFE proxy.

## 11. Advanced mechanism families

These are hypotheses, not established results:

- Hawkes or self-/cross-exciting intensity for event clustering and
  confirmation;
- change-point and regime-state models;
- rough-path signatures and controlled differential equations for
  irregular multi-modal paths;
- Koopman/HAVOK-style latent dynamics;
- committor-like probability of reaching valuable states before adverse
  states;
- time-reversal asymmetry;
- non-normal transient amplification;
- bicoherence and higher-order phase coupling;
- analog/nearest-state retrieval with strict chronological support.

For each, first specify what state it preserves that the baseline loses, how
it remains causal, a positive control, a matched destruction, cost, and the
exact incremental claim. A mathematically interesting transform with no
published lawful result remains `UNTESTED`.

## 12. What failed and why

The important failures were not evidence that the goal is impossible:

- Aggregate and side-marginal tests discarded order, native structure, or
  interactions.
- Some historical feature paths emitted side-blind or improperly oriented
  latents.
- Some rosters depended on final cluster/matrix fields and therefore on
  later-visible information.
- Some evaluations conflated entry quality with hindsight exit quality.
- A three-epoch positive control initially failed because the multi-task
  learner was undertrained; a clean ten-epoch run passed. This exposed a
  control/optimization issue, not a causal result.
- A frozen 1% “coverage” economic gate was infeasible even under perfect
  certificate ordering; the gate itself was miscalibrated to the objective.
- Delayed hindsight opportunities retained value but incurred nonzero
  $300-path breaches and rapidly lost opportunity coverage. This does not
  establish learnability.
- Python raw decoding and copied decoder formulas were rejected in favor of
  compiled production readers.
- Successive reader prototypes exposed projection, typed-null,
  wrong-civil-day clock, symlink/path, provenance, and fixture gaps before
  payload execution. These are useful fail-first evidence, not completed
  substrate.

The recurring process failure was allowing infrastructure and nearby oracle
questions to consume time before the exact causal representation experiment
was decision-complete. The remedy is the current gated plan and explicit
time/value budget, not weaker validation.

## 13. Collaboration lessons

- Lead with the result and the scientific meaning; do not bury it in hashes.
- State plainly whether a number is causal, leaked, hindsight, diagnostic,
  provisional, blocked, or deployable.
- Do independent refute-first review before expensive execution.
- Resolve all P0 ambiguity in one consolidated pass where possible.
- Parallelize independent code, provenance, documentation, and review lanes;
  avoid duplicate payload scans.
- Do not silently expand the task from learnability into another oracle
  audit.
- A blocked implementation is not progress toward the economic goal unless
  it removes a necessary blocker.
- Preserve negative evidence with its exact scope. Never let the newest file
  or report silently become authority.
- No Claude service is used. Historical local Claude records are archival
  evidence only.

## 14. Current boundary

The clean-room migration and legacy retirement completed on 2026-08-10; see
`provenance/CUTOVER_RECEIPT.tsv`. At that boundary:

- no lawful native-order causal learnability fit had run;
- the leakage controls passed but carried no alpha claim;
- the native-state task card was frozen and reviewed;
- the production reader adapter was rejected on a wrong-civil-day attachment
  retention defect before market payload execution;
- no greater-than-90% empirical readiness claim was established.

The next scientific action after cleanup is Gate 1 in [PLAN.md](PLAN.md), not
another oracle calculation.

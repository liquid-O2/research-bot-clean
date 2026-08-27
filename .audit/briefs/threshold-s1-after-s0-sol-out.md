# S1 freeze after S0 LIVE. Sol.

Sol peer judgment, 2026-08-27. One freeze is named. S1-M is the midpoint-record
side policy below. It fits one two-class side caller and couples that call to
one causal within-side stopping rule. It is a kill instrument and cannot
promote.

Nothing starts from this page. Do not start S1, B0, or tickets 37, 46, or 47.
Do not write the scorer until the parent reconciles this map with Fable's map.
No engine file changes from this page.

Skips required by the invoked playbooks:

- skip arena fan-out inside this child. This fresh Sol child is one runner in
  the parent's Fable and Sol arena. A nested same-seat chain would not add an
  independent model. The two within-side designs below are complete sketches,
  and the parent owns the cross-judge.
- skip architect Agree. The user did not request a checkpoint.
- skip architect Implement and Scrap. The brief forbids starting S1 or writing
  its scorer. This page ends with the frozen contract.

## Runner's view

If the parent selects this freeze, dispatch a fresh Sol child with this page,
`.audit/threshold-side-split.json`,
`.audit/briefs/threshold-side-split-judge-out.md`, and
`.audit/score_threshold_side_split.py`. The child writes
`.audit/score_threshold_side_caller.py`, runs its selftest and mutants before
opening era bytes, runs the frozen read once, and writes
`.audit/threshold-side-caller.json`. Fable judges the receipt bytes. The runner
stops at that receipt.

The caller learns one operation. Given the stored cell prefix at the frozen
call time, return `LONG` or `SHORT`. The within-side picker owns every later
choice. Callers do not coordinate candidate selection, fallback, or entry
timing.

## What S0 settled

S0 isolates the problem. `sideoracle_price` posts 2753.53, 3806.71, and
3869.82 dollars per asset-day with MDD 192.50. Its residual to cell-best is
only 5.42, 8.51, and 10.65. Side plus eventual within-side price order is the
identity mechanism on these bytes.

`sideoracle_earliest` posts only 1343.22, 1701.24, and 1163.21, with MDD
7033.75. On HG, earliest gives away 1410.31 dollars per asset-day against the
price line. A fitted side caller followed by earliest is therefore dead before
fit. S1 must make the side call and the within-side stopping decision one
policy, then judge that policy in exact dollars.

The S0 price-pair floors remain lower bounds. They are 0.664676 for HG,
0.283337 for NKD, and 0.275474 for SI. They assume eventual best price on each
side. S1-M computes a stricter floor for its causal stopping rule before it
judges the fitted caller.

## Phase B design arena

The rubric is frozen before the comparison:

1. The selected row must be executable at its own age-180 decision time.
2. The rule must seek favorable price depth without teacher cash or a second
   fitted object.
3. The rule must leave enough fills for exact dollars to reach all three
   rungs.
4. The rule must fit behind one small picker interface and admit sharp
   synthetic mutants.
5. The read must use stored bytes in minutes and require no engine edit.

### Candidate M. Midpoint record

The call event is the first CLEAR candidate at or after the exact midpoint of
the phase. The model sees only CLEAR candidates available through that event.
At the call event it returns one side.

Starting with the call timestamp, process candidate timestamps in order. At
each timestamp, batch all CLEAR rows on the called side. Enter the most
favorable row in the first batch that strictly improves the best called-side
price seen at every earlier timestamp. LONG favors the smaller `entry_mid2`.
SHORT favors the larger `entry_mid2`. Price ties take the smallest
`candidate_id`. If no strict record arrives, enter nothing. There is no
fallback and no positivity check.

This is one threshold predicate over an online price record. It delays the
entry by a fixed, outcome-free fraction of the phase, but it does not wait for
the eventual best row.

### Candidate R. Pullback and reclaim

Use the same call event and side model. After the call, maintain the best
called-side price and a two-state `WAIT_PULLBACK` or `WAIT_RECLAIM` machine.
Arm `WAIT_RECLAIM` only after a called-side row moves against the record. Enter
the first later row that sets a new favorable record. Enter nothing when the
sequence never completes.

This design can wait deeper into a choppy move. It also rejects every monotone
favorable move and every cell with no full pullback-reclaim sequence. The
extra state has no receipt-backed advantage.

### Comparison and synthesis

| Criterion | Candidate M | Candidate R |
| --- | --- | --- |
| Causal execution | First live record after the midpoint | First live record after a completed pullback |
| Price-depth mechanism | Fixed time patience | Path-shape patience |
| Fill risk | One post-midpoint record | A pullback and another record |
| Public rule | One predicate | Two-state machine |
| New fitted object | None | None |
| Named mutants | Call-time and first-record laws | State transitions and reclaim law |

Candidate M is the base. Candidate R contributes one useful constraint. The
picker processes equal timestamps as a batch, so row order cannot invent a
pullback or a record. The state machine itself is rejected. It spends fills
and implementation state on an unmeasured path pattern. The laziness protocol
breaks the tie in favor of Candidate M.

## Architecture sketch

The data model has five closed shapes:

- `CellKey` is `(asset, d8, phase)`.
- `CallPrefix` owns the call timestamp, the ordered candidate prefix, the
  routed forecast curve, and the frozen feature vector.
- `Side` is exactly `SHORT = -1` or `LONG = 1`.
- `MidpointRecordPick` is either one candidate at its decision timestamp or
  `NONE`.
- `LineName` is the five-name enum frozen below.

The scorer exposes four operations. `build_call_prefix` parses and validates a
cell boundary. `fit_side_caller` consumes only strict-prior labelled cells.
`pick_midpoint_record` consumes a prediction and candidate rows.
`summarize_s1` sends selected rows through the existing dollar ruler. The
teacher representation stays private to label construction and final cash
scoring. Tests and the runner cross these same four operations. No adapter or
engine seam is added.

## Frozen S1-M unit

One script, one receipt, and one teacher-cash scoring read. Use the S0 universe,
the existing routed day gate, the locked gated denominators 197, 194, and 191,
and the existing dollar ruler. The window is 2022-03-09 through 2024-12-31.
Training may use both gate states from strict-prior days. Evaluation uses the
frozen gated days. Report the ungated scope with no verdict gate.

### Cell label and call time

The teacher label is the S0 `sigma_star`. In each cell with a READY row, take
the side of the maximum `cert_close_usd`, tied by the smallest `candidate_id`.
A cell without a READY row has no training or accuracy label. The policy may
still enter it, its cash is zero, and the cell remains in every dollar
denominator.

For each cell, require one constant `phase_open_utc` and `phase_close_utc`.
Define the midpoint as their arithmetic mean. The call event is the earliest
CLEAR row whose `decision_ts_ns` is at or after that midpoint, tied by the
smallest `candidate_id`. A cell with no such row makes no call and no entry.
Report that count. Rows after the call timestamp cannot enter the feature
vector.

### Feature contract

Parse these candidate columns only:

`candidate_id`, `asset`, `d8`, `confirmation_event_ordinal`,
`decision_ts_ns`, `side`, `phase`, `rung_mask`, `delay`, `phase_open_utc`,
`phase_close_utc`, `prefix_last_event_ordinal`, `entry_mid2`,
`atr14_prev_usd`, `spread_prior_present`, `spread_prior_usd`, and
`compliance_status`.

The prefix contains CLEAR rows through the call timestamp, ordered by
`decision_ts_ns` and `candidate_id`. Let `p0` be its first `entry_mid2` and
refuse a non-positive value. Freeze this numeric input order:

1. The twelve admitted OOF `forecast_variance` values for `daily` and
   `intraday_30` through `intraday_330` in 30-minute steps.
2. `(last_price - p0) / p0`.
3. `(max_price - min_price) / p0`.
4. `(first_long_price - min_long_price) / p0`, or zero without LONG.
5. `(max_short_price - first_short_price) / p0`, or zero without SHORT.
6. LONG-present and SHORT-present indicators.
7. `(long_count - short_count) / clear_count`.
8. `log1p(clear_count)`.
9. `log1p(max_confirmation_ordinal - min_confirmation_ordinal)`.
10. The call delay after the midpoint divided by phase duration.
11. The last inter-candidate timestamp gap divided by phase duration, or zero
    for one timestamp.
12. `log1p(prefix_last_event_ordinal - confirmation_event_ordinal)` from the
    call row.
13. `atr14_prev_usd`, `spread_prior_present`, and `spread_prior_usd`, with
    spread set to zero when absent.

Freeze this categorical input order. It is `phase`, `first_side`,
`last_side`, the call row's `rung_mask`, and the call row's `delay`. Refuse a
side outside `{-1, 1}`, a non-finite numeric, a missing forecast head, a
forecast row that is not admitted and gate-passed, or a forecast fold that
differs from the routed daily row. The forecast curve is day-level and
assetless. Do not represent it as an asset forecast.

Teacher parsing stays `candidate_id`, `status`, `cert_close_usd`, and
`exit_ts_ns`. Keep `mfe_usd`, `mae_usd`, `payer`, and `take_target` unparsed.
Teacher fields cannot enter `CallPrefix`.

### Learner

Use CatBoost 1.2.10 with `Logloss`, depth 6, 500 iterations, learning rate
0.05, random seed 20260826, one thread per fit, no early stopping, no class
weights, no validation fold, no CV, no tuning, and no seed sweep. This is the
already-audited C learner config on a different cell-level target, not a second
C name fit.

Fit one model per asset and scored day. Every training cell must have a call
prefix, a `sigma_star` label, and `d8` strictly less than the scored day. Give
each cell unit weight. Predict LONG when the fitted probability is at least
0.5, otherwise SHORT. If strict-prior labels contain one class, predict that
class. If none exist, predict LONG. Report both fallback counts. Do not
abstain, change the probability threshold, or fit per phase.

### Frozen within-side rule

Use Candidate M verbatim. Selection sees candidate columns and the predicted
side only. It cannot see teacher status, cash, the eventual last row, or the
eventual best price. A selected CLEAR row earns stored `cert_close_usd` only
when its teacher status is READY. Otherwise it earns zero and increments
`selected_not_ready`.

### Five lines and the effective bar

Freeze these line names. There is no sixth policy line:

1. `cellbest_control` reproduces the existing ceiling through the ceiling
   module.
2. `sideoracle_price_control` reproduces S0 `sideoracle_price` exactly.
3. `oracle_side_midpoint_record` applies Candidate M with `sigma_star`. Its
   gated dollars are `W_M`.
4. `wrong_side_midpoint_record` applies Candidate M to the opposite side. Its
   gated dollars are `L_M`.
5. `fitted_side_midpoint_record` applies Candidate M to the walk-forward
   prediction. This is the binding policy line.

Every line reports the full existing dollar block. Derive, by asset,

`p_M = (rung - L_M) / (W_M - L_M)`

and

`p_required = max(S0 price-pair p_star, p_M)`.

These are frozen formulas, not amendment points. `p_required` is the side
accuracy floor for the fitted line. Exact fitted dollars remain binding
because prediction errors need not distribute like the wrong-side control.

### Comparison null

Give the fitted policy its own null. Within each asset, phase, and calendar
year, keep the fitted prediction multiset and rotate it across chronological
cell keys by a non-zero SHA-256-derived offset. Use 40 fixed replicates keyed
by schema name and replicate number. Do not refit. Reapply Candidate M and the
dollar ruler to each rotated prediction map.

Report the 95th percentile with the `higher` rule for side accuracy and
`usd_per_asset_day` on each asset. Report the effective number of distinct
rotations. A constant prediction vector equals its null and cannot pass. This
is a deterministic permutation check, not a model seed sweep.

### Receipt and proof

Write `.audit/score_threshold_side_caller.py` and
`.audit/threshold-side-caller.json`, schema `QRE2THRESHOLDSIDECALLER1`. Pin
this page, the S0 receipt and judge, the S0 scorer, the C fitted scorer, the
ceiling receipt and scorer, the forecast file, every opened candidate and
teacher file, and their generation receipts. Record the exact feature order,
learner config, per-day training counts, class counts, fallback counts,
feature-matrix hashes, prediction hashes, line enum, null keys, and dollar-stop
text.

Run `python3 .audit/score_threshold_side_caller.py --selftest` before any era
byte. Then run each `QRE2_S1_MUTANT` selftest and require exit 1:

- `future_train_leak` includes a cell from the scored day.
- `teacher_outcome_as_feature` admits a teacher field to `CallPrefix`.
- `post_call_prefix_leak` lets a later candidate change the feature vector.
- `wrong_side_pick_accepted` lets the picker cross the predicted side.
- `record_law_drift` accepts a non-record or waits for the eventual best
  record instead of the first qualifying timestamp.
- `null_alignment_preserved` leaves fitted predictions on their original
  cells in a null replicate.
- `pstar_arithmetic_drift` fails a hand-computed `p_M` and `p_required`
  fixture.
- The guard mutant accepts a corrupted synthetic `candidate_id`.

A real run refuses every mutant value before opening a byte. Run one asset
through load, feature construction, fitting, and scoring before launching the
fleet. Stop if the projected full wall time exceeds two hours. Use 13 to 16
workers, never 64. One process owns the receipt. A rerun verifies the existing
bytes or refuses on source drift.

## Dollar stop

STOP for infrastructure. Stop on either control mismatch, denominator drift,
a missing forecast head, a feature or learner-config mismatch, any mutant that
stays green, any opened 2025 byte, source drift, a non-deterministic prediction
hash, or a projection beyond two hours. Report and wait. Do not amend.

KILL S1-M if any condition below holds on the locked gated scope:

- `W_M` fails a rung, MDD is at least 1000, the entry cap fails, or overlap is
  non-zero.
- `W_M` is not strictly greater than `L_M`, or any `p_required` exceeds 0.90.
- Fitted side accuracy on labelled call cells is below `p_required` on any
  asset.
- Fitted side accuracy or fitted `usd_per_asset_day` is not strictly above its
  own 95th-percentile permutation null on any asset.
- `fitted_side_midpoint_record` has zero trades, misses any rung, has MDD at
  least 1000, exceeds 12 entries per portfolio day, violates one-position
  occupancy, or uses more than one contract.

On KILL, the one-config S1-M age-180 side policy closes. Do not try Candidate R,
a second checkpoint, another within-side rule, a second learner config, a seed,
a feature widening, or a per-phase resurrection on these held bytes. B0 is the
named successor, authorized only by the next parent covering decision. B0 does
not start here.

LIVE only when every condition above passes. LIVE cannot promote and does not
start an engine walk. The named successor is one new covering decision that
freezes the per-day model artifacts and this rule text, then specifies the
single exact `QRE2TABPOLICYBLOCK2` replay checked by
`.audit/assert_threshold_replay_receipt.py`. A teacher-cash pass is still not
THRESHOLD.

## Forbidden inside S1-M

Any second learner, config, seed, probability threshold, checkpoint, picker,
or feature family. Any QRSESS1 or pivot-plane widening. Any teacher field in a
feature or pick. Any post-call row in a feature. Any eventual-best or
last-record choice. Any positivity or abstention gate. Any read of 2021 or
2025. Any engine edit. Any change to the day gate, denominators, ruler, rungs,
occupancy law, or one-contract law. Starting B0 or tickets 37, 46, or 47.

## Principles that changed the freeze

- Exhaust the design space and codebase design forced a predicate picker and a
  state-machine picker to stand side by side. Interface depth and fill risk
  selected Candidate M.
- Laziness protocol, subtract before adding, and minimize reader load kept the
  unit on candidate rows plus the existing forecast curve. They rejected a
  second calibrator, QRSESS1 inputs, pivot tags, and an engine adapter.
- Model the domain, foundational thinking, and type-system discipline made the
  cell call, side enum, optional pick, five line names, feature order, and
  verdict closed shapes before scorer logic.
- Fix root causes and redesign from first principles treated the S0 earliest
  failure as an online stopping problem. They did not answer it with another
  side-model setting.
- Boundary discipline keeps teacher cash in strict-prior label construction
  and final scoring. The picker receives a typed prediction and candidate rows.
- Build the lever, prove it works, and sequence verifiable units require one
  rerunnable scorer, red-first mutants, one receipt, and a separate byte judge.
- Make operations idempotent and separate shared state give the receipt one
  writer and make reruns verify or refuse.
- Encode lessons in structure turns the prior future-peek, teacher-peek, and
  hindsight-picker failures into mutants.
- Never block on the human names one freeze and both successors. The parent can
  reconcile it asynchronously.
- Guard the context window keeps source facts behind file pointers and records
  hashes rather than copying pin manifests into this page.

## Tradeoffs accepted

- We accept a fixed midpoint clock in exchange for a causal, parameter-free
  amount of price patience. Clock use is flagged, and this unit cannot promote.
- We accept possible no-entry cells in exchange for refusing an earliest or
  hindsight fallback. Exact denominators and dollars expose the cost.
- We accept the audited C CatBoost config without tuning in exchange for one
  interaction learner and a clean no-second-config stop.
- We accept a first-order accuracy floor in exchange for a pre-stated side bar.
  Exact policy dollars and the policy's own null remain binding.
- We accept one more held teacher-cash read. The rule, input vector, learner, null,
  and stop are frozen before that read.

## Next step

The parent compares this map with Fable's S1 map. If the parent selects Fable's
freeze, this page remains a peer record. If the parent selects S1-M, dispatch a
fresh Sol child on this page and stop that child at
`.audit/threshold-side-caller.json`.

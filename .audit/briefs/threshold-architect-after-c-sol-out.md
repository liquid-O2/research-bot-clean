# Threshold architecture after the C Stage 1 KILL

Sol design package, 2026-08-26. This page stops at the architect Agree
checkpoint. It does not implement or run an experiment.

## Problem

The C receipt does not support its broad closure. C tested one pointwise binary
classifier over about 105 CLEAR rows per cell. Its target was the single
highest-cash row, and its scorer selected an argmax after the complete cell was
available. The live problem has a different shape. A policy sees an ordered
prefix, must choose `ENTER`, `DEFER`, or `PASS`, and only needs to land in the
top two of about six new-extreme events often enough to bank exact dollars.

The next experiment should test that missing decision shape at age 180 before
the program changes the age grid or adds another information plane.

## Usage from the caller's view

The parent should eventually dispatch one script with three modes. These
commands are a design sketch, not an authorization to create or run the file.

```text
python3 .audit/score_threshold_frontier180.py --selftest
python3 .audit/score_threshold_frontier180.py --run
python3 .audit/score_threshold_frontier180.py --verify .audit/threshold-frontier180.json
```

`--selftest` uses synthetic rows and opens no era byte. `--run` owns the one
scientific read. `--verify` rehashes inputs and re-derives the dollar verdict
without fitting or reading a new rule. The only publication target is
`.audit/threshold-frontier180.json`, schema
`QRE2THRESHOLDFRONTIER1801`.

The caller learns one interface. The script either returns an infrastructure
`STOP`, a dollar `KILL`, `NOT_RESOLVED`, or a kill-only `SURVIVE`. It never
returns a model metric as the verdict.

## Grounding

### Why the location result reaches only half the rung

The location rule is a completed-cell diagnostic. It ranks the final event set
by signed entry price plus a fitted cross-side offset. It lands in the top two
65 to 77 percent of the time, but the bottom half of the event pool is deeply
negative. A miss loses hundreds of dollars instead of earning a smaller win.
That converts a strong rank hit rate into only 31 to 51 percent of event-oracle
cash and about $800 to $1,061 per asset-day. `START_HERE.md` sections 2 and 3,
`design/entry_reset/T39_VERDICT_20260823.md`,
`design/entry_reset/T44_TAUTOLOGY_AUDIT_20260823.md`, and
`design/entry_reset/T50_DIAGNOSIS_20260823.md` own those facts.

The diagnostic also sees the completed cell. `_best_by_score_per_cell` chooses
after the final event set exists and does not call canonical replay. A live
policy cannot copy that selection rule. The traced boundary is
`design/entry_reset/55-entry-v2-recovery-plan/execution-path.md:16` and
`:61-63`.

### Why C went negative

C changed four things at once.

1. It replaced about six new-extreme events with every CLEAR row in the cell.
   The mean gated cell has 105.49 rows.
2. It replaced the useful top-two distinction with one positive
   `is_cell_best` label. Every profitable runner-up became the same negative
   class as a large loser. The label loop is
   `.audit/score_threshold_cfit_stage1.py:730-742`.
3. It trained pointwise Logloss and chose the maximum score after the complete
   cell was available. The rule and fit live at
   `.audit/score_threshold_cfit_stage1.py:128-136` and `:951-981`.
4. It discarded the only replicated ordering. Its pick matched the signed
   entry-price twin in 34 of 1,734 cells, a 1.96 percent match rate. The result
   then posted HG -173.50, NKD +31.20, and SI -150.45 per asset-day in
   `.audit/threshold-cfit-stage1.json`.

The low twin match proves that C made different picks. It does not prove that
those picks contained useful non-price information. Here it is evidence that
the fit abandoned the one ordering known to carry cash.

### Why the scans returned nulls

The scans asked whether an isolated row or one finite list of hand-written
orders identified the exact winner. That question removes the candidate
lifecycle, labels the second-best event as a loser, and usually evaluates a
finished-cell argmax. A family envelope then bounds only the listed rules. It
does not bound every function of the source bytes.

The broad closure was therefore caused by an experiment-model mismatch, not by
an information-theoretic result. The record contains scoped nulls for scalar
orders, finite tape summaries, finite pivot summaries, and one pointwise fit.
It contains no causal event-frontier policy in canonical replay. The repository
states that gap directly at
`design/entry_reset/55-entry-v2-recovery-plan/execution-path.md:34-36` and
`:69-73`.

## Candidate A. Causal event frontier with anchored elimination

This candidate changes the decision object. It keeps an ordered frontier of
events that have become eligible at their own age-180 timestamp. Each current
event is judged against the prefix already seen. Future events, final event
count, teacher cash, and the finished-cell winner stay absent.

The policy predicts whether the current event belongs in the final top two. It
uses signed entry price as a fixed base term and learns only a residual from
prefix relationships. Those relationships include own-side overtakes,
opposite-side arrivals, prefix price ranks, event counts by side, and gaps to
the running side extremes. Numeric residuals are orthogonalized against signed
entry price on strictly prior days. Clock columns do not enter the residual.

The policy converts top-two probability into expected dollars using strictly
prior top-two and bottom-pool cash means. It commits only when the expected cash
meets the asset's required dollars per trade. The required values are HG
$666.67 and NKD and SI $500. A rejection is `DEFER`; phase exhaustion is
`PASS`. There is no earliest-CLEAR fallback.

This is not a second C configuration. The unit is a causal sequence, the label
is top-two membership, the price rule is an anchored base instead of a loose
feature, and the output is a chronological action stream rather than a
completed-cell argmax.

Reach remains the event ceiling at age 180. The experiment does not pay a late
entry-price penalty. Cost is one audit script over stored 2021 rows. A run
should take two to eight minutes. The tripwire is 20 minutes.

## Candidate B. Source-owned G1 birth evidence on the same frontier

This candidate adds information that `CandidateRow` currently drops. G1 would
publish the exact pivot, leg, retracement, and a narrow tape summary accumulated
while the zigzag formed. The record would carry the strict prefix cutoff and
source hash. The frontier policy would consume those facts at age 180 through
the same decision interface as Candidate A.

This is structurally distinct from another tape functional. The formation
algorithm owns the evidence and publishes it once. A downstream scorer does
not reconstruct a proxy window. The policy still makes a causal
`ENTER`, `DEFER`, or `PASS` decision and still reports canonical dollars.

Reach is the full age-180 event ceiling. The cost is higher. This candidate
needs a source tag, a future-mutation differential, a 2021 materialization, and
then the same policy read. The existing pivot and tape nulls make that spend
hard to justify before Candidate A tests whether the missing structure alone
is enough.

## Candidate C. B0 late-age relabeling

B0 changes the entry age and recomputes exact labels. It can answer whether a
late hindsight ceiling still contains the rungs. It cannot answer which causal
late picker finds that ceiling. Its current path first amends the accepted age
grid, then builds a new store across 582 asset-days, then spends a dollar read,
and only a later unit designs a picker.

B0 has unknown reach after price decay. The T28 identity captures only about 23
to 58 percent of age-180 cell-best in the cited summary, and the actual late
entry price can only worsen that comparison. B0 therefore loses to Candidate A
on reach, cost, and sure-shot value. It remains a scientific fallback, but it
does not keep the next slot.

## Comparison

| Criterion | Candidate A | Candidate B | Candidate C |
| --- | --- | --- | --- |
| Can reach the current labelled ceiling | Yes, age 180 | Yes, age 180 | Unknown after decay |
| Tests a live book decision | Yes, prefix actions into replay | Yes, after a new source tag | No, ceiling first |
| Uses stored bytes for the first kill | Yes | Partly | No |
| Expected first receipt | Two to eight minutes | Build plus run | Minutes to tens of minutes after an engine amendment |
| Corrects C's target and state | Yes | Yes, with new evidence | No |
| Needs a new production seam now | No | Yes | Yes |
| Direct next-step judgment | Strong | Park behind A | Reject for the next slot |

Candidate A wins. Candidate B is the next information source only if A shows
that the state shape works but lacks separation. Candidate C does not beat the
age-180 candidate and is removed from the immediate plan.

## Chosen shape

### Core types

The type sketch uses Python notation because the experiment is a Python audit
script. Bodies remain unimplemented.

```python
Asset = Literal["HG", "NKD", "SI"]
Phase = Literal[0, 1, 2]

@dataclass(frozen=True, slots=True)
class CellKey:
    asset: Asset
    d8: int
    phase: Phase

@dataclass(frozen=True, slots=True)
class EventKey:
    cell: CellKey
    candidate_id: str

@dataclass(frozen=True, slots=True)
class Age180Event:
    key: EventKey
    eligible_ts_ns: int
    side: Literal[-1, 1]
    entry_mid2: int
    causal_facts: tuple[float, ...]
    source_sha256: str

@dataclass(frozen=True, slots=True)
class FrontierObservation:
    current: Age180Event
    prior_events: tuple[Age180Event, ...]
    own_side_overtakes: int
    opposite_side_arrivals: int
    price_rank_in_prefix: int

@dataclass(frozen=True, slots=True)
class Enter:
    event: EventKey
    commit_ts_ns: int

@dataclass(frozen=True, slots=True)
class Defer:
    cell: CellKey

@dataclass(frozen=True, slots=True)
class Pass:
    cell: CellKey
    reason: Literal["phase_closed", "expected_cash_below_bar", "occupied"]

Decision = Enter | Defer | Pass

@dataclass(frozen=True, slots=True)
class TeacherOutcome:
    candidate_id: str
    status: Literal["READY", "UNAVAILABLE"]
    cert_close_usd: float
    exit_ts_ns: int | None

@dataclass(frozen=True, slots=True)
class InfrastructureStop:
    kind: Literal["STOP"]
    reason: str
    source_hashes: Mapping[str, str]

@dataclass(frozen=True, slots=True)
class DollarKill:
    kind: Literal["KILL"]
    blockers: tuple[DollarBlocker, ...]  # constructed as non-empty
    lines: Mapping[str, DollarLine]

@dataclass(frozen=True, slots=True)
class NotResolved:
    kind: Literal["NOT_RESOLVED"]
    lines: Mapping[str, DollarLine]

@dataclass(frozen=True, slots=True)
class KillOnlySurvive:
    kind: Literal["SURVIVE"]
    lines: Mapping[str, PassingDollarLine]
    promotion_allowed: Literal[False] = False

ExperimentReceipt = InfrastructureStop | DollarKill | NotResolved | KillOnlySurvive
```

`Age180Event` cannot carry an outcome. `TeacherOutcome` cannot cross the policy
boundary. `Enter` always names the current event and its own age-180 timestamp.
The receipt variants prevent `SURVIVE` with blockers, `KILL` without blockers,
and any 2021 promotion claim.

### Public seam

The experiment has one public function behind the CLI.

```python
def run_frontier180_experiment(
    spec: FrozenFrontierSpec,
    sources: SourceManifest,
) -> ExperimentReceipt:
    raise NotImplementedError
```

Loading, event reconstruction, prior-day normalization, residual fitting,
policy walking, canonical replay, null construction, and receipt publication
stay private. Tests and the CLI cross the same seam. No engine protocol is
added before a survivor exists.

### Module map

- `.audit/score_threshold_frontier180.py` owns the frozen spec, the causal
  frontier, the residual policy, replay adaptation, selftest, verification, and
  atomic receipt publication.
- `.audit/threshold-frontier180.json` is the only scientific output and has one
  writer.
- `.audit/score_h5_top2.py` is read-only prior art for event reconstruction and
  identity parity. `engine/entry_v2/replay.py` remains the canonical dollar
  ruler.

A reader can answer where the pick came from with the scorer, the receipt, and
the pinned source manifest. No stage wrapper or compatibility API is added.

## One next experiment

Run the age-180 causal frontier elimination kill test. Do not start B0, a birth
tag, a new corpus, or another C fit first.

### Stage 0. Contract proof

Build synthetic cell streams and run the script's selftest before any real
artifact opens. Each mutant must fail for its named reason.

- `future_event_visible` adds an event whose eligibility is after the current
  decision.
- `teacher_cash_as_feature` sends `cert_close_usd` through the causal boundary.
- `finished_cell_argmax` selects from the final cell rather than the prefix.
- `wrong_age_cash` joins an event to a label from another age.
- `price_twin_missing` omits the anchored price-only control.
- `corrupt_candidate_id_accepted` breaks the identity join.

Stage 0 ends with `selftest_ok` and every mutant red. A failure is an
infrastructure `STOP`.

### Stage 1. One frozen 2021 kill read

Use the stored live keep-first new-extreme events at age 180. Fit only on TRAIN.
Read THRESHOLD and FORWARD once under one frozen rule. 2021 can kill and cannot
promote.

The learner is one per-asset expanding-window offset logistic model. Signed
entry price supplies the fixed base term. The learned terms come from
prefix-relative values after prior-day residualization against that base. The binary target
is `is_top2`, never `is_cell_best`. There is no alternate learner, seed,
objective, or feature family.

At each event arrival, strictly prior outcome rows estimate the mean cash of the
top-two and bottom pools. The policy converts predicted top-two probability to
expected cash. It enters only when that expectation meets the required dollars
per trade. Otherwise it defers to the next event. An empty history passes the
cell and leaves the denominator intact.

The price-only twin uses the identical event stream, action capacity, dollar
threshold, and replay path with every learned residual set to zero. The null
permutes lifecycle state within each cell while preserving event count, side
count, eligibility timestamps, and signed-entry-price order. The receipt stores
incremental dollars against both controls, but the scientific verdict remains
the actual book dollars.

Every selected arrival goes through canonical chronological replay. The receipt
reports, by asset and held block, `cash_total_usd`, `usd_per_asset_day`, dollars
per trade, day-level standard error, trades, `max_drawdown_usd`, maximum entries
per portfolio day, overlap violations, occupied refusals, top-two hit rate, and
the price-only twin difference. Diagnostic rates cannot set the verdict.

### Dollar stop

- `KILL` fires when any asset's pooled held upper two-standard-error bound is
  below its rung, or when the book breaches the drawdown, entry-cap, overlap, or
  one-position constraint. The causal event-frontier shape then loses its cheap
  test. No learner amendment follows this receipt.
- `SURVIVE` requires both held blocks to post HG at least $2,000 and NKD and SI
  at least $1,500 per asset-day, `max_drawdown_usd` below $1,000, at most 12
  entries per portfolio day, zero overlap violations, and a pooled improvement
  over both the price-only twin and lifecycle null of at least two standard
  errors. `SURVIVE` authorizes a new covering decision for an era walk. It does
  not promote the policy.
- `NOT_RESOLVED` covers the interval between those bounds. It funds neither B0
  nor an amended frontier fit. A new covering decision may then compare the
  source-owned birth evidence with late labels.

The expected Stage 1 wall time is two to eight minutes on stored bytes. Stop at
20 minutes and publish an infrastructure receipt. Do not optimize a slow run
after it starts.

## Red-flag screen

| Red flag | Candidate A | Candidate B | Candidate C |
| --- | --- | --- | --- |
| Shallow module | Pass. One CLI function hides the full experiment. | Pass only if G1 owns publication. | Risk. Builder, grid amendment, scorer, and later picker expose several stages. |
| Information leakage | Pass. Outcomes are a separate type and parser. | Pass with strict prefix hashes. | Pass for labels, but the later picker contract is absent. |
| Temporal decomposition | Pass. Modules own frontier and replay knowledge, not phases. | Pass if tag creation stays with G1. | Risk. The current plan is organized around amendment, build, read, then picker. |
| Pass-through method | Pass. No new engine adapter exists. | Risk until a second consumer earns an adapter. | Risk. Several one-use loaders would exist before a policy does. |

Candidate A has no red flag that requires revision. Candidate B is viable only
after a cheap result earns its source seam. Candidate C exposes too much
infrastructure before it tests a policy.

## Synthesis decision

Candidate A is the base. Candidate B contributes one invariant. Any future
formation evidence must be published by G1 with a strict prefix hash rather
than reconstructed downstream. Candidate C contributes the exact-age check.
The receipt must prove that `commit_ts_ns` and the selected label refer to the
same age-180 event.

No extension slot, generic policy framework, or late-age compatibility layer is
grafted into the base. Those additions would be speculative.

## Tradeoffs accepted

- We accept a 2021 kill-only result in exchange for a minutes test that can stop
  a larger build.
- We accept a simple linear residual model in exchange for making the event
  state and causal action semantics, rather than model capacity, the tested
  change.
- We accept `NOT_RESOLVED` as a possible verdict in exchange for respecting the
  two-standard-error rule on a small held sample.
- We accept passing warm-up cells in exchange for deleting the harmful
  earliest-CLEAR fallback.

## Open questions and risks

- Can the stored 2021 rows provide exact exit timestamps needed by canonical
  replay? Stage 0 must answer this from the pinned schema. Missing exits cause a
  `STOP`; a diagnostic occupancy substitute is forbidden.
- Does the reconstructed event stream still match the pinned event receipt?
  The existing parity logic in `.audit/score_h5_top2.py` is the check.
- Does residualization leave any lifecycle information beyond signed entry
  price? The direct dollar comparison with the price-only twin answers this.
- The 2021 held blocks have been read before. This experiment is kill-only and
  cannot restore their promotion value.

## Candidate decision log

| Time | Candidate | Decision | Why | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 2026-08-26T23:12:44Z | A, causal event frontier | Keep | It tests the missing causal state and action shape at the known labelled age with stored bytes. | `design/entry_reset/55-entry-v2-recovery-plan/execution-path.md:34-36` | `KEEP` |
| 2026-08-26T23:12:44Z | B, source-owned birth evidence | Kill for next slot | It adds a production source seam before state alone receives its cheap test. | `engine/cpp/qr_entry_v2/include/qr_entry_v2/g1.hpp:164-229` | `KILL_FOR_NEXT_SLOT` |
| 2026-08-26T23:12:44Z | C, B0 late labels | Kill for next slot | It measures a new ceiling before it has a picker and pays a full relabel cost. | `.audit/briefs/threshold-covering-after-cfit-kill-out.md` | `KILL_FOR_NEXT_SLOT` |

## Playbook receipt

- Architect Ground is complete from the cited receipts and traced replay seam.
- Architect Sketch is complete with three whole shapes.
- Architect Agree stops here for the requested checkpoint.
- Architect Implement is skipped because the brief forbids implementation.
- Architect Scrap is skipped because no implementation tested the sketch.
- Arena Frame uses reach, causal fidelity, cost, target fit, and interface depth.
- Arena Fan out is owned by the parent-dispatched Fable and Sol lanes. This file
  is the isolated Sol lane, so it did not create nested writers.
- Arena Cross-judge is owned by the parent after both independent artifacts
  exist.
- Arena Pick and Graft are recorded in the synthesis decision.
- Arena Verify is the proof section below.

## Principles that changed the design

- Exhaust the Design Space required two age-180 shapes and B0 side by side.
- Redesign from First Principles changed the core object from a row classifier
  to an event-prefix action policy.
- Fix Root Causes stopped the plan from treating finite-family nulls as proof
  that the bytes contain no information.
- Laziness Protocol chose the stored age-180 test before a source tag or relabel.
- Subtract Before You Add removed the B0-first sequence and the
  earliest-CLEAR fallback.
- Prove It Works made canonical dollars and replay constraints the verdict.
- Sequence Verifiable Units split synthetic contract proof from one held read.
- Model the Domain produced `FrontierObservation` and the decision union.
- Codebase Design kept one deep CLI seam and no speculative engine adapter.
- Foundational Thinking separated causal observations from teacher outcomes
  before choosing the learner.
- Build the Lever made one rerunnable script own construction, run, and
  verification.
- Boundary Discipline keeps the teacher parse at `candidate_id`, `status`,
  `cert_close_usd`, and `exit_ts_ns`.
- Type System Discipline makes incompatible receipt verdicts separate variants.
- Make Operations Idempotent requires source-hash equality and atomic
  publication on rerun.
- Separate Before Serializing Shared State gives the receipt one writer.
- Minimize Reader Load keeps the pick trace to the scorer, receipt, and manifest.
- Outcome-Oriented Execution targets the rungs and deletes compatibility with C.
- Encode Lessons in Structure puts the price twin, null, age equality, and
  future-event refusal into the schema and mutants.
- Guard the Context Window keeps evidence as file pointers rather than copied
  receipts.
- Never Block on the Human names Candidate A without asking for a fork choice.
- Experience First makes the live one-contract book, not an offline rank score,
  the consumer.
- Migrate Callers Then Delete Legacy APIs is skipped. This design adds no
  internal API or compatibility path.
- Show Me Your Work records one keep or kill decision per candidate above.
- Unslop and Writing for Agents keep the package direct, bounded, and executable
  from its file pointers.

## Proof of this package

The package must pass these checks before handoff.

1. The output names at least two structurally distinct candidates and exactly
   one next experiment.
2. The chosen experiment has a dollar stop, a wall-time tripwire, a price twin,
   a lifecycle null, and canonical replay.
3. C is described from its receipt and source. No C fit or closed receipt is
   rerun.
4. B0, C Stage 2, and tickets 37, 46, and 47 remain unstarted.
5. No engine file, including `engine/entry_v2/confirmation_types.py`, changes.

## Evidence pointers

- `START_HERE.md` sections 2 through 5.
- `.cursor/prompts/threshold-covering.md`.
- `.audit/threshold-cfit-stage1.json`.
- `.audit/briefs/threshold-cfit-stage1-judge-out.md`.
- `.audit/briefs/threshold-how-entry-miss-out.md`.
- `.audit/briefs/threshold-why-entry-miss-out.md`.
- `.audit/briefs/threshold-covering-after-cfit-kill-out.md`.
- `.audit/briefs/threshold-covering-after-cfit-kill-sol-out.md`.
- `.audit/score_threshold_cfit_stage1.py`.
- `.audit/score_h5_top2.py`.
- `design/entry_reset/T39_VERDICT_20260823.md`.
- `design/entry_reset/T44_TAUTOLOGY_AUDIT_20260823.md`.
- `design/entry_reset/T50_DIAGNOSIS_20260823.md`.
- `design/entry_reset/55-entry-v2-recovery-plan/execution-path.md`.

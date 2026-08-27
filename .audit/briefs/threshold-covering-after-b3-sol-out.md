# Covering after B3 STOP. Sol.

Sol peer judgment, 2026-08-27. This page completes architect Phases A through
C and one arena synthesis for `.audit/briefs/threshold-covering-after-b3.md`.
It names one next experiment. It does not run that experiment, amend B3, fit a
model, open 2021, reopen the late-label store, touch an engine file, start an
exit overlay, or walk `design/entry_reset/tickets/`.

Throughput checkpoint: n/a, read-only architecture covering.

The charter stays fixed. The rungs are HG 2000, NKD 1500, and SI 1500
`usd_per_asset_day`, `max_drawdown_usd` below 1000, at most 12 entries per
portfolio day, one position per asset, one contract, zero overlap, and dollars
per trade. The locked denominators are 197 / 194 / 191. Teacher-cash can kill
and cannot promote. A 2021 result can kill and cannot promote. 2025H2 stays
sealed.

## Decision

Keep the one-unit, one-receipt method. Change the object it operates on.

The next unit is `B4_PHASE_INSTANCE_COMMON_CLOCK_2400`. B4 makes a scheduled
phase instance the identity from the candidate parse through the replay block.
It then asks B3's still-unanswered dollar question with one formed roster, one
timer, one common BBO, and one scheduled close. B3 remains locked at STOP. B4
is a new rule and receipt, not a resumed B3 run.

The second live architecture is an age-180 top-two event frontier. It is a
different decision object, target, cadence, and replay path. It does not get
the first slot because the lawful cheap test is 2021 kill-only, while B4 can
answer the open 2022-2024 causal question directly. It remains the explicit
non-B3 branch for the next covering if B4 does not produce a LIVE.

## Phase A. Grounding from receipts

### What the receipt sequence established

| Receipt | Frozen fact | Architectural consequence |
| --- | --- | --- |
| C Stage 1 KILL | One walk-forward CatBoost `is_cell_best` fit at age 180 posted -173.50 / +31.20 / -150.45 with MDD 75608.75. | The fitted age-180 name-identity program over that feature and target shape is closed. It does not close a top-two event policy. See `.audit/briefs/threshold-cfit-stage1-judge-out.md`. |
| S0 LIVE, S1 KILL | Oracle side plus hindsight within-side price reproduced the ceiling. The frozen causal within-side rules missed every rung even at oracle side, and the fitted side caller was near coin. | Side decomposition priced the mechanism, then closed its causal age-180 realization. S0 and S1 are finished work, not remaining candidates. See `.audit/briefs/threshold-side-split-judge-out.md` and `.audit/briefs/threshold-s1-sidecaller-judge-out.md`. |
| B0 LIVE | Late-age cell-best still cleared, including 2726.81 / 3775.72 / 3847.62 at age 600. | Late entry preserves enough hindsight room. No more late ceiling work exists. See `.audit/briefs/threshold-b0-stage1-judge-out.md`. |
| B1 KILL | Both observable-record primaries missed. The decomposition showed record side agreement around 0.63 to 0.71, while oracle depth on that side cleared. | The record carries side information. The causal depth rule remained missing. See `.audit/briefs/threshold-b1-picker-judge-out.md`. |
| B2 LIVE | `recside_effprice_all` cleared at one age per asset on teacher-cash. | This is an optimistic batch cap. It is not an executable clock or a promotable policy. See `.audit/briefs/threshold-b2-price-picker-judge-out.md`. |
| B3 STOP | `(asset, d8, phase)` merged two phase-0 schedule instances in `HG/20221107`. No trace, block, or dollar line formed. | The common-clock question is unanswered. The decision identity is under-specified. See `.audit/briefs/threshold-b3-common-clock-judge-out.md` and `.audit/threshold-b3-common-clock.json`. |

The scientific method worked. It separated KILL, LIVE, and STOP, prevented a
stopped pass from becoming a dollar claim, and closed several concrete shapes.
The search boundary became too local. C through B3 repeatedly preserved a
completed cell or legacy `(asset, d8, phase)` identity. The changed decision is
to compare whole decision architectures before dispatch, while retaining the
same receipt discipline.

### The B2 result is three claims

| Claim | Judgment | What follows |
| --- | --- | --- |
| Roster and fill law | Proven leak. B2 filters to `READY`, which depends on a certifiable future suffix. It also compares candidates at candidate-specific age snapshots, so one fill may predate a name it beat. | B2 stays an optimistic cap. A replay wrapper or 2021 validation would preserve the leak and is rejected. The source grounding is in `.audit/briefs/threshold-covering-after-v0-stop-fable-out.md`. |
| Depth formula | Near-tautological entry-price arithmetic under B2's batch exit law. `recside_effprice_all` minimizes signed effective entry price inside the selected record-side set and agrees with oracle depth on almost every pick. Wall and generation effects leave a small residual, so the full dollar line is not a literal identity. | Do not fund another depth learner. At one common BBO, the within-side depth choice disappears. Candidate identity becomes lineage only. The B2 rule text is in `.audit/threshold-b2-price-picker.json` under `line_rules`. |
| When-axis signal | Plausible, not proven. B1 measured record-side agreement, B2's level rule cleared while laggardness died, and B0 proved late room. | Test only the record-side decision under a lawful common clock. B3 stopped before this comparison produced dollars. |

Quants should not merge those claims. The experiment leaks. The depth leg is
mostly arithmetic conditional on that experiment. The record-side timing leg
is a hypothesis with a causal form that still lacks a dollar receipt.

### What work remains

The 2022-2024 ceiling, capture miss, S0 reduction, S1 caller, late-age ceiling,
B1 record family, and B2 batch cap are settled. The remaining work is narrow:

1. Define a total phase-instance identity from formation facts and run the
   age-2400 record-side rule at one common BBO through raw chronological replay.
2. Test a chronological age-180 top-two event frontier if the common-clock
   branch does not produce a LIVE. Its first lawful screen is 2021 kill-only.
3. Add source-owned G1 formation evidence only if the stored event-frontier
   shape survives while lacking separation. Existing tape and pivot nulls do
   not justify that production seam now.

There is no remaining ceiling read, capture scan, S0 or B0 rerun, B2 wrapper,
second C fit, new exit, new wall, new take, new size, or new count.

## Phase B. Design it twice

### Caller usage

The common-clock caller supplies a frozen spec and source manifest. It receives
one closed receipt variant. It never supplies a phase close, edits a roster, or
chooses a fill.

```python
ClockReceipt = InfrastructureStop | DollarKill | DollarLive

def evaluate_phase_instance_clock(
    spec: FrozenPhaseInstanceClockSpec,
    sources: SourceManifest,
) -> ClockReceipt:
    raise NotImplementedError
```

The event-frontier caller has a different seam. It consumes one current event
and its prior prefix through one experiment function. Teacher outcomes cannot
enter the observation type.

```python
FrontierDecision = Enter | Defer | Pass

def evaluate_event_frontier(
    spec: FrozenEventFrontierSpec,
    sources: SourceManifest,
) -> KillOnlyFrontierReceipt:
    raise NotImplementedError
```

### Candidate P. Phase-instance common clock

The storage day is lineage. It is not the schedule identity.

```python
@dataclass(frozen=True, slots=True)
class CandidateShard:
    asset: Asset
    d8: int
    locked_iid: int

@dataclass(frozen=True, slots=True)
class PhaseInstanceAnchor:
    asset: Asset
    locked_iid: int
    phase_label: str
    phase_open_ts_ns: int

@dataclass(frozen=True, slots=True)
class PhaseInstance:
    anchor: PhaseInstanceAnchor
    phase_close_ts_ns: int
    multiplier: int

@dataclass(frozen=True, slots=True)
class ClockOpportunity:
    instance: PhaseInstance
    decision_ts_ns: int
    roster_candidate_ids: tuple[str, ...]
    common_quote: PrefixQuote
```

The parse boundary proves this functional dependency:

`PhaseInstanceAnchor -> one phase_close_ts_ns and one multiplier`.

It also proves every formation lies inside its instance. The observed legacy
key `HG/20221107/0` must report two instances. The same full instance identity
flows through opportunity ID, selection hash, disposition, trace, strict
block, and receipt lineage. No downstream caller derives a close from the
first row.

For each phase instance, the timer is the ceiled first formation plus 2400
seconds. A timer at or after the instance close produces
`PHASE_CLOSED_BEFORE_TIMER`. Otherwise the roster contains every CLEAR
formation in that instance at or before the timer. One raw prefix BBO supplies
the common fill.

The frozen B3 record rule chooses the roster leader by maximum
`side * (timer_mid2 - formation_entry_mid2)`, with the existing tie break. The
leader's side is the economic decision. The smallest candidate ID on that side
is lineage only. Every member would enter at the same timer BBO, so B2's
within-side effective-price depth is not carried forward. Raw suffix outcome
construction uses the chosen side, common entry, frozen cost, and that phase
instance's scheduled close. Canonical replay applies occupancy and caps.

Red-flag screen:

- Shallow module. Pass only if one experiment seam hides parsing, instance
  validation, clock construction, selection, replay, and publication.
- Information leakage. Pass because formation and prefix types cannot carry
  outcomes. Raw suffix data crosses only after selection is frozen.
- Temporal decomposition. Pass when phase-instance knowledge owns the whole
  lifecycle. A public census stage followed by a key-patch stage would fail.
- Pass-through method. Pass because no compatibility adapter or new engine
  interface is added.

The rejection condition is structural. If implementation widens one local
dictionary key while traces or blocks still use `(asset, d8, phase)`, it is the
same B3 architecture and must not run.

### Candidate E. Age-180 top-two event frontier

An `Age180Event` is a live keep-first new-extreme event at its own eligibility
timestamp. `FrontierObservation` contains that event and only prior eligible
events from the same phase instance. The action is `ENTER`, `DEFER`, or `PASS`.
The label is final top-two membership among roughly six events, not C's single
`is_cell_best` winner among about 105 CLEAR rows. Chronological book dollars,
not AUC or top-two hit rate, set the verdict.

The first lawful test uses the stored 2021 component matrix and event parity
path already exercised by `.audit/score_h5_top2.py`. It fits on TRAIN and reads
THRESHOLD and FORWARD once under a frozen rule. It is kill-only and cannot
promote. A price-only twin and lifecycle null are diagnostics, not additions to
the rung predicate. The prior is adverse. The location ranker remained about
half the rung, roster fields were near chance in `.audit/threshold-roster-kill.json`,
unit-weight Dawes beat trees, and S1's prefix caller was near coin. The shape is
still distinct because none of those receipts tested this event state, top-two
label, and action sequence together.

Any future frontier must inherit `PhaseInstance` at its boundary. It must not
return to the legacy day-phase key.

Red-flag screen:

- Shallow module. Pass if one CLI seam hides event reconstruction, policy
  state, outcome adaptation, replay, controls, and publication.
- Information leakage. Pass only when future events, final event count,
  teacher cash, and the completed-cell winner are impossible policy inputs.
- Temporal decomposition. Pass because the module owns event-prefix knowledge,
  not execution phases.
- Pass-through method. Pass because no production adapter exists before a
  survivor creates a second caller.

### Comparison

| Criterion | Candidate P | Candidate E |
| --- | --- | --- |
| Decision object | One scheduled phase instance | One current age-180 event |
| Causal state | Formed roster at one timer and one common BBO | Current event plus prior event prefix |
| Target | Exact common-clock dollars | Top-two membership translated into exact replay dollars |
| Existing support | B0 late room, B1 record-side agreement, B2 optimistic cap | Event oracle and event parity path, with several adverse age-180 priors |
| First useful receipt | Direct 2022-2024 strict replay block | 2021 kill-only screen |
| Promotion reach | LIVE can be promotion-grade | The first SURVIVE cannot promote |
| Runtime prior | B3 stopped at 1134.5 seconds under an 1800-second tripwire | Stored-byte minutes, with a 20-minute tripwire in the prior design |
| Main risk | Hiding a source-law defect behind a wider tuple | Repackaging dead prefix fields in a new target |

Candidate P wins the next slot. It answers the exact open causal question with
the strongest measured mechanism and no new feature plane. Candidate E remains
live because it changes the whole decision shape, but its cheap result cannot
promote and its inputs carry a weaker prior.

## Arena synthesis

Three fresh candidates wrote isolated packages. Candidate A is the base.
Candidate C supplied the explicit 2021 kill-only frontier branch and the best
minutes-path argument. Candidate B supplied the rule that every future
frontier must also be phase-instance keyed, plus price-only and lifecycle-null
controls as diagnostics.

Rejected from Candidate A are its added confidence bands and fourth verdict.
They would amend B3's fixed hard dollar predicate.
Rejected from Candidate B is a direct 2022-2024 frontier fit. No era frontier
store or parity path is established. Rejected from Candidate C is putting the
frontier first without carrying the B3 phase-instance boundary fact.

The cross-judge scored A 27, C 25, and B 19 across receipt fidelity, causality,
structural distinction, executable stop, information per minute, and interface
depth. The base and judge agreed. No candidate dropped out.

## Phase C. Agree

No checkpoint was requested. The synthesis selects Candidate P and proceeds to
the dispatch specification below. Architect Phases D and E stay closed. This
page writes no implementation.

## The one next experiment

### `B4_PHASE_INSTANCE_COMMON_CLOCK_2400`

B4 is one receipt-bound experiment. Its pre-dollar identity gate and binding
dollar line share one candidate pass and one receipt.

#### Frozen universe

- Locked 2022-2024 asset-days, HG 197, NKD 194, and SI 191.
- Age 2400 seconds for every asset.
- One candidate pass and one EventPack pass over the locked 582 asset-days.
- No late-label shard or stored-teacher open. No 2021 or 2025 byte.
- No fit, new feature plane, second rule, alternate age, or engine change.
- One strict `QRE2TABPOLICYBLOCK2`, one receipt, and one judgment.

#### Identity gate

Parse every CLEAR formation once into `PhaseInstance`. Before an EventPack or
outcome byte opens, assert the anchor functional dependency, interval
membership, and full identity propagation contract. Record legacy cell
multiplicities. `HG/20221107/0` must partition into the two schedule instances
already upheld by the B3 judge.

If the store facts fail those invariants, publish STOP with the completed
pre-pass evidence. The next covering then owns a generator or stored-schema
repair. B4 must not repair, drop, merge, or roster-scope the offending row.

#### Binding rule

The only dollar line is `phaseinstance_recordside_commonfill_2400`.

For each valid phase instance:

1. Set the timer to `ceil_second(first_formation) + 2400 seconds`.
2. Admit only CLEAR formations from that instance at or before the timer.
3. Read one raw prefix BBO at the timer.
4. Choose the record leader with B3's frozen side rule.
5. Enter one contract on the leader's side at the common BBO.
6. Freeze selection, then construct the outcome from the raw suffix through
   that instance's scheduled close.
7. Replay every arrival chronologically under the frozen book laws.

A short instance whose close precedes its timer emits no opportunity and is
counted as `PHASE_CLOSED_BEFORE_TIMER`. Candidate identity on the selected side
is lineage only. No candidate-specific fill or `READY` filter exists.

#### Artifacts and proof

- Scorer `.audit/score_threshold_b4_phase_instance_clock.py`.
- Receipt `.audit/threshold-b4-phase-instance-clock.json`, schema
  `QRE2THRESHOLDB4PHASEINSTANCECLOCK1`.
- Strict artifacts under
  `artifacts/entry_v2/tabular_recovery/threshold/b4_phase_instance_clock_2400/real/`.
- Judge `.audit/briefs/threshold-b4-phase-instance-clock-judge-out.md`.

The receipt pins the B3 rule source, formation sources, EventPacks, instance
census, legacy multiplicities, selection hashes before and after outcome
construction, disposition counts, strict trace hashes, block hash, dollar
block, protected-tree fingerprints, and applied stop clause. Every STOP carries
the pre-pass evidence already completed. Publication is atomic. A later
invocation verifies or refuses on drift and never performs a second scientific
read.

Selftest opens zero era bytes. It keeps B3's existing causal and replay mutants
and adds these identity mutants:

- `legacy_cell_alias_accepted`
- `conflicting_instance_close_accepted`
- `formation_outside_instance_accepted`
- `identity_dropped_from_lineage`

The load-bearing B3 mutants remain `future_candidate_in_roster`,
`event_at_decision_visible`, `per_candidate_snapshot_reprice`,
`ready_filters_roster`, `outcome_changes_selection`,
`repeat_phase_opportunity`, `schema_alias_without_frozen_source`,
`policy_block_dollars_ignored`, `mdd_boundary_inclusive`,
`policy_cap_ignored`, and `policy_overlap_ignored`. Rename the repeat mutant to
phase-instance language without weakening it. Every mutant must be red before
the real source manifest opens.

#### Runtime

Use 13 workers split HG 5, NKD 4, and SI 4. Project from the first completed
asset before the full raw pass. Expected wall is about 1200 seconds from B3's
1134.5-second stopped pass. The hard tripwire remains 1800 seconds. A projection
past the tripwire is STOP before the full raw pass.

#### Dollar stop

- **STOP.** Any selftest failure, green mutant, source or denominator drift,
  phase-instance functional-dependency failure, interval or propagation
  failure, unscorable emitted opportunity, future visibility, stored-teacher
  open, 2025 touch, protected-tree change, or wall tripwire. Report and wait.
  No dollar conclusion follows.
- **KILL.** Infrastructure holds and the strict block reloads, but any frozen
  predicate fails. This includes HG below 2000, NKD or SI below 1500,
  `max_drawdown_usd` at or above 1000, more than 12 entries on a portfolio day,
  any overlap, more than one position per asset, anything other than one
  contract, or no dollars-per-trade line. KILL closes only the age-2400
  phase-instance record-side common-fill rule. It funds no second B4 line,
  alternate age, fit, or quiet amendment.
- **LIVE.** The same strict block passes
  `python3 .audit/assert_threshold_replay_receipt.py --block <raw_block.json>`
  at the frozen hard predicates. LIVE is promotion-grade causal evidence. It
  does not promote B2 and starts nothing. The next covering owns the reserved
  2021 kill test.

B4 has only STOP, KILL, and LIVE. It asks the same hard dollar question B3 was
meant to answer.

#### Forbidden inside B4

No B3 receipt amendment. No local key widening without full lineage
propagation. No roster-scoped close choice. No row drop for the known sliver.
No late-label or stored-teacher byte. No fitted read. No 2021 or 2025 byte. No
exit, wall, take, size, count, age, gate, denominator, or replay-law change. No
second rule. No new engine adapter. No near-miss language.

## Principles that changed the decision

- `principle-redesign-from-first-principles` changed the identity from a
  storage day-phase label to a scheduled phase instance.
- `principle-fix-root-causes` kept the proven cause at key aliasing and made a
  formation functional dependency the first gate. It did not invent a DST or
  generator repair.
- `principle-exhaust-the-design-space` forced a top-two event policy to stand
  beside the common clock as a whole architecture.
- `principle-codebase-design` put instance construction, validation, clock,
  replay, and publication behind one deep seam. It rejected a tuple patch and
  a pass-through adapter.
- `principle-laziness-protocol` and `principle-subtract-before-you-add` removed
  ceiling work, label work, another learner, and a production event seam from
  the next slot.
- `principle-prove-it-works` kept the verdict on a strict replay block and the
  frozen dollar predicates, not rank agreement or receipt narration.
- `principle-sequence-verifiable-units` put the identity gate before the raw
  pass and ended the unit at one judged receipt.
- `principle-never-block-on-the-human` names B4 and binds every outcome without
  returning an architecture fork to the parent.

## Completion

Architect Ground, Sketch, and Agree are complete. The arena read all three
candidates, cross-judged them, selected a base, and recorded its grafts and
rejections. No scientific check ran. The only repository artifact from this
turn is this covering map.

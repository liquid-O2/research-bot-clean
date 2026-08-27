# Covering after B2 LIVE. Sol.

Sol peer covering decision, 2026-08-27. This page consumes
`.audit/briefs/threshold-covering-after-b2.md`,
`.audit/threshold-b2-price-picker.json`,
`.audit/briefs/threshold-b2-price-picker-judge-out.md`,
`.audit/briefs/threshold-covering-after-b1-fable-out.md`, and
`.audit/briefs/threshold-sure-shot.md`.

Architect Phases A through C are complete. Phase A traced the batch scorer,
raw outcome index, canonical replay, strict trace and block loaders, and the
shared assertion. Phase B compared two whole shapes and cross-judged them.
Phase C proceeds without a checkpoint because none was requested. Phases D
and E are outside this brief.

No era byte was opened and no dollar was formed in this turn. No scorer,
engine file, picker, fit, relabel, exit overlay, or ticket was started. The only
repository artifact written by this turn is this covering map.

## Grounded correction to the B2 interpretation

B2's dollar arithmetic and judged LIVE verdict remain valid under B2's written
batch contract. They do not define an executable entry policy.

Two future facts reach B2's choice.

1. `_score_shard` in `.audit/score_threshold_b2_price_picker.py` first groups
   every age-A `READY` row in a completed phase and then passes the full roster
   to `_score_cell`. The selected row keeps its own `snapshot_ts_ns` as its
   entry time. A candidate that forms later can therefore choose a fill that
   occurred earlier. The `future_mid_in_pick` mutant guards each row's quote
   against that row's age anchor. It does not prove that every competing row
   existed at the chosen fill.
2. `READY` is outcome-conditioned. `_label_at_age` in
   `engine/entry_v2/late_teacher.py` asks `_OutcomeIndex.outcome` for the future
   suffix before it emits `READY`; an uncertifiable suffix becomes
   `NO_CERTIFIABLE_SUFFIX` with no BBO or cash. Filtering to `READY` before
   selection lets future outcome availability decide which names exist.

The age-2400 all-asset B2 block is still the useful optimistic cap. The frozen
receipt reports HG 2171.7386, NKD 2700.3995, and SI 2987.0550 dollars per
asset-day, combined MDD 967.50, maximum 9 entries, and 1730 trades. It is the
one B2 block that clears every asset at one pre-registered age. It cannot be
wrapped directly in replay because its completed roster, own-row fill clocks,
and future `READY` filter are the advantages being measured.

There is a second promotion seam. `PolicyDayTrace` and `PolicyBlockResult`
currently require learned-model, feature-schema, roster, seed, and mode
lineage. A deterministic rule cannot populate those fields honestly.
`.audit/assert_threshold_replay_receipt.py` also sets policy-block
`usd_per_asset_day` to `None`, so its current policy-block path cannot clear an
asset rung even when canonical replay computed the dollars.

The root cause is therefore not the frozen exit. It is the absence of one
causal decision clock and one truthful deterministic-rule path into canonical
replay.

## The two whole-shape candidates

Candidate C was a common-clock causal roster. The first formation in a cell
arms one age-2400 timer. Only formations visible by that timer compete, all use
one current prefix BBO, and the cell emits at most one opportunity. Outcome
construction begins only after the opportunity is frozen. A tagged frozen-rule
trace and block source reaches strict replay without counterfeit model hashes.

Candidate Q was an online quiet close. Each name first receives its own
age-2400 observation, then the cell closes after another 2400 seconds without a
new observation or at a phase terminal. It preserves more of B2's asynchronous
record observations, but it introduces a second unmeasured duration, needs a
real timer event that its proposed observation-only interface omitted, and
uses candidate-specific quote indexes at the common stop. It also claimed the
existing learned-only strict schemas could be reused without engine changes.
That last claim is false.

The fresh cross-judge scored the whole shapes as follows.

| Criterion | C, common clock | Q, quiet close |
|---|---:|---:|
| Causal honesty | 5 | 3 |
| Dollar decisiveness | 5 | 3 |
| Reach to promotion | 4 | 0 |
| Charter fit | 5 | 4 |
| Interface depth and cost | 3 | 2 |
| Experiment integrity | 4 | 2 |
| Total | **26 / 30** | **14 / 30** |

Candidate C is the base. Graft four controls from Q. Freeze the selected-cell
hash before outcomes, report every cell disposition, prove the fill came from
the timer's common raw prefix, and adopt existing trace bytes only when they
are identical. Do not graft the quiet period, phase-terminal rule, B2 full
reconstruction pass, or candidate-specific stop quotes.

The direct B2 wrapper is a third rejected alternative. It has the smallest
diff but preserves both future leaks and the stale own-row fill. A teacher-cash
preflight is also rejected. It cannot promote and would force another read of
the same question.

## The one next experiment

The next experiment is **Unit B3, age-2400 common-clock record-side replay**.
It is one entry-only raw-byte read ending in one strict
`QRE2TABPOLICYBLOCK2` and the full dollar predicate. It is not a picker. At a
common BBO, every name on one side has the same effective price, so B2's
within-side identity order disappears. B3 makes one causal side decision and
uses a candidate ID only as lineage.

Nothing starts from this page. Parent dispatches B3 as a fresh specified walk
after reconciling this Sol page with the Fable sibling.

## Usage from the runner

The future runner owns one command surface.

```text
python3 .audit/score_threshold_b3_common_clock.py --selftest
python3 .audit/score_threshold_b3_common_clock.py
python3 .audit/assert_threshold_replay_receipt.py \
  --block artifacts/entry_v2/tabular_recovery/threshold/b3_common_clock_2400/real/raw_block.json
```

The scorer writes these authoritative artifacts.

- `.audit/threshold-b3-common-clock.json`, schema
  `QRE2THRESHOLDB3COMMONCLOCK1`, records the contract, source hashes, counters,
  controls, selected-cell hash, runtime, strict block path, and verdict.
- `artifacts/entry_v2/tabular_recovery/threshold/b3_common_clock_2400/real/traces/<YYYYMMDD>.json`
  stores strict frozen-rule day traces.
- `artifacts/entry_v2/tabular_recovery/threshold/b3_common_clock_2400/real/raw_block.json`
  stores the one strict `QRE2TABPOLICYBLOCK2`.
- `.audit/briefs/threshold-b3-common-clock-judge-out.md` is the later Fable
  judgment. The scorer does not write it.

An existing authoritative block invokes verify-only mode. The scorer
strict-loads its traces and block, verifies their pinned lineage, prints the
stored verdict, and does not reopen era sources. Identical trace bytes may be
adopted. Different bytes at an authoritative path are an infrastructure STOP.

## Frozen rule

Let `N = 1_000_000_000`, `A = 2400`, and let one cell be
`k = (asset, d8, phase)`.

Parse only formation-time rows from the raw `QRE2G1CAND2` candidate tables.
Eligibility is exactly `compliance_status == CLEAR`. The parser exposes no
late-label `status`, `READY`, cash, exit, wall, MFE, MAE, or outcome field.
Sort a cell's candidates by `(decision_ts_ns, candidate_id)` and call the first
row `c0`.

The one decision clock is

```text
t0 = ((c0.decision_ts_ns + N - 1) // N) * N
T  = t0 + A * N
```

If `T >= c0.phase_close_ts_ns`, the cell returns a typed causal
no-opportunity. All rows in one cell must agree on asset, day, phase, scheduled
phase close, and multiplier. A mismatch is STOP. Candidate truth-quality keys
may differ, but they cannot compete as quote variants. The common quote law is
frozen to `c0`'s key, and the receipt reports the count of cells with more than
one key.

The formed roster is

```text
R(k, T) = {c in k | c.compliance_status == CLEAR and c.decision_ts_ns <= T}
```

A formation stamped exactly at `T` joins the simultaneous roster. Raw market
visibility stays strict. `EventPack.cutoff(T)` is the left cutoff, so the quote
index sees only events with `ts_recv_ns < T`. Using `c0`'s frozen
truth-quality key, take one last trusted prefix BBO `(B, O)`. Require
`0 < B < O`. If no such prefix quote exists, return a typed causal
no-opportunity. This is a decision-time data-validity fact, not a suffix-based
abstention.

Define the common midpoint and frozen cost as

```text
M = B + O
C = Decimal(O - B) * Decimal(multiplier[asset]) / Decimal(N)
    + Decimal(str(FEE_USD))
```

For each formed candidate, define

```text
record_units(c, T) = c.side * (M - c.formation_entry_mid2)
```

The record leader maximizes `record_units`, with smallest `candidate_id` as
the tie-break. Its side is the entry side. Every candidate on that side shares
the same `M`, `C`, multiplier, and decision time. The effective-price expression

```text
Decimal(c.side * M) * Decimal(multiplier[asset])
    * Decimal("0.0000000005") + C
```

is therefore constant within the side. The smallest candidate ID on the side
is only the lineage carrier. It does not claim an economic identity choice.

Emit exactly one `CellOpportunity` at `T` with the common BBO, side, cost,
phase close, event cutoff, anchor ID, and lineage ID. A cell is consumed after
that result even if canonical replay later skips the opportunity for occupancy
or the shared entry cap. Never emit a replacement or a second opportunity from
that phase.

Hash the ordered mapping
`cell -> (opportunity_id, T, side, B, O, event_cutoff)` as
`selected_by_cell_sha256` before outcome construction. Suffix work may start
only after this hash is frozen.

For an emitted opportunity, call `generation_at_snapshot(T)` and
`_OutcomeIndex.outcome` on the raw EventPack only in the outcome boundary. The
call uses the frozen side, `M`, `C`, and scheduled phase close. Convert its
exact first-wall-or-last-same-generation result into `ReplayOutcome`, including
the actual wall flag, exact exit timestamp, and exact dollars. Do not infer a
wall from cash and do not replace the wall value with a constant. An emitted
opportunity with no certifiable raw suffix is infrastructure STOP. Dropping it
would make outcome availability an entry filter.

Recompute `selected_by_cell_sha256` after every outcome is built and require
equality. Every arrival has `enter=True`. Canonical `replay` alone applies one
position per asset, one contract, the shared 12-entry portfolio-day cap, and
chronological occupancy. A replay skip never changes the emitted universe.

## Shape

The caller supplies one immutable contract and receives one strict block.

```python
@dataclass(frozen=True, slots=True)
class B3CommonClockSpec:
    age_seconds: Literal[2400]
    bounds: tuple[Literal[20220309], Literal[20250101]]
    locked_asset_days: Mapping[str, int]
    candidate_root: Path
    candidate_receipt_root: Path
    event_root: Path
    output_root: Path


@dataclass(frozen=True, slots=True)
class CellClock:
    key: CellKey
    anchor_candidate_id: str
    decision_ts_ns: int
    phase_close_ts_ns: int
    truth_quality_key: TruthQualityKey


@dataclass(frozen=True, slots=True)
class PrefixQuote:
    decision_ts_ns: int
    event_end_index: int
    bid_px: int
    ask_px: int
    mid2: int
    frozen_cost_usd: Decimal


CellDecision = CausalNoOpportunity | CellOpportunity


def evaluate_b3_common_clock(
    spec: B3CommonClockSpec,
) -> PolicyBlockResult:
    ...
```

`evaluate_b3_common_clock` is the only experiment-level operation. It hides
source validation, formation parsing, clock construction, prefix quoting, side
selection, outcome certification, canonical replay, strict persistence, and
receipt writing. The rule and its private domain types stay in
`.audit/score_threshold_b3_common_clock.py`. Do not add a common-clock engine
module for one experiment.

The generic persistence repair stays with the existing owners.

- `engine/entry_v2/tabular_live_replay.py` gains
  `FrozenRuleDayTrace` with schema `QRE2FROZENRULETRACESTORE1` and an explicit
  `LearnedPolicyDayTrace | FrozenRuleDayTrace` sum. Strict save, load, and
  evidence reconstruction dispatch exhaustively on the trace variant.
- `engine/entry_v2/tabular_evaluation_policy.py` replaces learned-only outer
  lineage with `LearnedPolicyBlockSource | FrozenRuleBlockSource`. The frozen
  source holds rule name and hash, age, candidate receipt hashes, candidate
  hashes, and EventPack hashes. It has no dummy seed, mode, feature schema,
  component roster, or action roster. All internal callers migrate in the same
  unit. Existing learned artifacts remain strict-loadable through the learned
  branch.
- `.audit/assert_threshold_replay_receipt.py --block PATH` strict-loads the
  result and derives per-asset dollars from
  `result.evidence.evaluation.by_asset`. It checks the rungs, strict MDD,
  positive trades, portfolio entry cap, overlap, one-contract law, and locked
  denominators. Delete the policy-block string scraper that assigns per-asset
  dollars to `None`.

Do not add a standalone trace module, a second block writer, or placeholder
learned-model artifacts. The persistence modules own persistence. The audit
scorer owns the one frozen rule.

`candidate_ceiling` is computed from the same common-clock `ScoredArrival`
universe and expected sessions only because `BlockReplayEvidence` requires
exact day and asset ceilings. It cannot select policy entries or supply policy
dollars.

## Controls and red-first mutants

Selftest and every mutant run on synthetic rows before an era source is
opened.

- `future_candidate_in_roster` admits a formation after `T`. The roster guard
  must fail.
- `event_at_decision_visible` changes the raw cutoff to include an event at
  `T`. The equal-time prefix test must fail.
- `per_candidate_snapshot_reprice` or `stale_age_price_fill` replaces the
  common timer BBO with a candidate-specific or age-row quote. The common-fill
  invariant must fail.
- `ready_filters_roster` exposes late `status` or removes an opportunity after
  an uncertifiable suffix. The parser poison test or outcome-boundary test must
  fail.
- `outcome_changes_selection` changes a side, quote, timestamp, or cell hash
  after suffix scoring. The selected-cell hash equality must fail.
- `repeat_phase_opportunity` emits two opportunities for one cell. The cell-key
  uniqueness guard must fail.
- `schema_alias_without_frozen_source` writes a learned-looking trace or block
  with rule hashes in model fields. Strict load must fail.
- `policy_block_dollars_ignored` restores `usd_per_asset_day = None` or skips
  an asset. The synthetic clearing block must fail promotion.
- `mdd_boundary_inclusive` weakens strict MDD to `<= 1000`.
  A synthetic block at exactly 1000 must fail.
- `policy_cap_ignored` and `policy_overlap_ignored` omit their respective
  shared-assertion checks. Synthetic failing blocks must kill both mutants.

The authoritative receipt also records these controls.

- The source set is exactly the locked 582 asset-days, with denominators HG
  197, NKD 194, and SI 191. Every candidate receipt, candidate table, and
  EventPack hash matches. No source date reaches 2025.
- Late-label shard opens and stored-teacher opens are both zero. The B2 receipt
  hash and age-2400 cap are provenance only, not runtime inputs to choice,
  outcome, replay, or promotion.
- Scheduled cells are counted separately. Every scheduled cell has exactly one
  terminal disposition among phase-closed before timer, missing prefix BBO,
  emitted and certified, and emitted but unscorable. The last class forces
  STOP.
- Every emitted opportunity uses its timer timestamp, the left raw cutoff, and
  the one common BBO. Every cell emits at most once. Occupancy skips are counted
  separately and never trigger replacement.
- Strict trace reload and strict block reload reproduce the in-memory source
  lineage, selected-cell hash, per-asset dollars, MDD, trade count, daily cap,
  overlap count, and exact ceiling byte for byte.
- Candidate, event, teacher, pivot, and candidate-receipt source trees have the
  same metadata before and after the run.

## One-read law and runtime

The receipt freezes these counters.

```text
age_seconds = 2400
dollar_line_reads = 1
passes_over_raw_candidate_event_set = 1
candidate_table_opens_per_shard = 1
event_pack_opens_per_shard = 1
late_label_shard_opens = 0
stored_teacher_opens = 0
fit_started = false
touched_2025 = false
```

The allowed order is synthetic selftest and mutants, pinned source validation,
one raw candidate and EventPack pass, opportunity-hash freeze, suffix outcome
construction from the already-open packs, canonical replay, strict trace and
block writes, and strict reload. Hash the same opened bytes before they can
form dollars. Aggregation never reopens a raw shard.

Use the measured 13-worker split HG 5, NKD 4, and SI 4. Workers return immutable
asset-day results. The parent process is the only day-trace writer, so workers
share no output path. One clock per cell should finish in minutes. Freeze 600
seconds as the expected wall time and 1800 seconds as the hard tripwire. If the
pre-run projection crosses 1800 seconds, STOP before dollars rather than start
an hours-scale path.

## Dollar stop

Infrastructure STOP applies before any dollar verdict if a baseline selftest
fails, a mutant survives, a source hash or denominator drifts, a 2025 byte is
opened, a late label or stored teacher is opened, a future formation or event
reaches the chooser, a cell emits twice, the selection hash changes after
outcomes, an emitted opportunity lacks an exact raw suffix, a dummy learned
lineage field appears, strict reload differs, a read counter exceeds its frozen
value, a protected source changes, or wall time exceeds 1800 seconds.

KILL applies when infrastructure holds and the strict block reloads, but any
required predicate fails. The predicates are HG at least 2000 dollars per
locked asset-day, NKD and SI at least 1500, maximum drawdown strictly below
1000 dollars, positive trades, at most 12 portfolio entries on every day, zero
overlap violations, one position per asset, one contract, and denominators
197 / 194 / 191. A KILL closes this age-2400 common-clock translation of B2.
It does not fund a quiet rule, another age, a fit, an age-180 join, an exit
change, or a second read. The next covering decides what the measured gap funds.

LIVE applies only when the same strict block passes
`python3 .audit/assert_threshold_replay_receipt.py --block <raw_block.json>`
with exit code 0 and a later Fable judge holds the artifact bytes. This is
promotion-grade because the dollars come from exact chronological raw replay,
not teacher-cash. A LIVE starts no exit work from this page.

## Forbidden inside B3

Do not change `A = 2400`, add a quiet duration, add a phase-terminal entry,
use a per-asset age map, add a second rule, fit a threshold, or choose anything
from the read. Do not open the late-label shards, stored teacher, 2021 labels,
the age-180 join, or any 2025 byte. Do not change wall, take, phase close, size,
count, rungs, denominators, replay occupancy, or gate semantics. Do not start
tickets 37, 46 at scale, or 47. Do not add a B2 line or amend its receipt. Do
not call a custom cash sum a strict replay block.

## Synthesis decision and accepted tradeoffs

Candidate C became the base because one scheduled clock is observable, its
common quote removes stale fills by construction, and its typed persistence
path can reach promotion honestly. The quiet candidate contributed selection
hashing, cell counters, current-fill proof, and idempotent trace adoption. Its
second timer and schema shortcut were rejected.

- We accept that common-clock dollars may fall far below the B2 cap in exchange
  for removing the completed roster, own-clock fill, and future `READY`
  advantages. B3 is a causal projection of B2's mechanism, not a claim that it
  reproduces B2's selected identities.
- We accept that effective-price depth collapses to a side decision at one BBO
  in exchange for naming the real economic object instead of preserving a fake
  identity picker.
- We accept one generic strict-schema repair in exchange for a direct
  promotion-grade result and no counterfeit learned lineage.
- We accept typed causal no-opportunities for a closed phase or absent prefix
  quote in exchange for never consulting a future suffix before entry.
- We accept STOP on an unscorable emitted opportunity in exchange for never
  turning future outcome availability into an abstention rule.

## Principles that changed a decision

- `exhaust-the-design-space` and `codebase-design` forced two complete timing
  shapes and selected the one deep evaluator with the smaller observable
  contract. The schema repair stays with the two existing persistence owners.
- `fix-root-causes` rejected a direct B2 wrapper. The repair removes the full
  future roster and outcome-conditioned `READY` filter at their source.
- `redesign-from-first-principles`, `foundational-thinking`, and
  `model-the-domain` made the cell clock, prefix quote, and
  `CausalNoOpportunity | CellOpportunity` the core model. The within-side
  picker disappeared when the common-BBO assumption made it economically
  constant.
- `boundary-discipline` and `type-system-discipline` keep formation data in
  the chooser, suffix data in the outcome builder, and learned versus frozen
  lineage in exhaustive tagged sums.
- `laziness-protocol` and `subtract-before-you-add` removed the quiet period,
  B2 reconstruction pass, teacher-cash preflight, two proposed engine modules,
  multiple ages, and placeholder learned artifacts.
- `migrate-callers-then-delete-legacy-apis` requires every internal block
  caller to move to the source sum in the same unit. There is no parallel
  frozen-rule block API. Existing learned disk artifacts remain a real variant,
  not an internal compatibility wrapper.
- `prove-it-works`, `build-the-lever`, and `encode-lessons-in-structure` make
  the scorer, strict loaders, shared assertion, and red-first mutants the
  rerunnable proof of the causal boundary and dollar result.
- `sequence-verifiable-units`, `make-operations-idempotent`, and
  `separate-before-serializing-shared-state` order one synthetic gate, one raw
  read, one canonical block, one strict reload, and one judgment, with one
  writer and byte-identical adoption.
- `experience-first` and `never-block-on-the-human` prefer the direct strict
  replay result over another kill-only preflight. Both dollar outcomes are
  wired here, so the parent receives one dispatchable experiment rather than a
  fork question.

## Next step

Parent reconciles this Sol page against the Fable sibling, then dispatches a
fresh Sol specified walk on B3 with file pointers to this page, the B2 receipt
and judge, the B0 Stage 1 scorer and receipt, `engine/entry_v2/late_teacher.py`,
`engine/entry_v2/confirmation_index.py`, `engine/entry_v2/replay.py`,
`engine/entry_v2/tabular_live_replay.py`,
`engine/entry_v2/tabular_evaluation_policy.py`, and
`.audit/assert_threshold_replay_receipt.py`. Never resume-chain. Fable judges
the strict block and audit receipt. Nothing starts from this covering turn.

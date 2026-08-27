# Covering after B0 Stage 1 LIVE. Sol.

Sol peer judgment, 2026-08-27. This page consumes the live brief
`.audit/briefs/threshold-covering-after-b0.md`, the B0 receipt
`.audit/threshold-b0-stage1.json`, its judgment
`.audit/briefs/threshold-b0-stage1-judge-out.md`, the prior Fable covering
`.audit/briefs/threshold-covering-after-s1-fable-out.md`, and the S0 receipt
`.audit/threshold-side-split.json`. The cited receipts are evidence. This page
does not rescore a shard, open a late-label row, fit a model, write engine code,
or start a picker.

The charter stays fixed. The gated rungs are HG 2000, NKD 1500, and SI 1500
`usd_per_asset_day`. `max_drawdown_usd` must stay below 1000. A portfolio day
may have at most 12 entries. Each asset may hold one position and one contract.
The ruler counts dollars per trade. The locked denominators remain 197 / 194 /
191 days. Teacher cash can kill and cannot promote. The 2021 data can kill and
cannot promote. The 2025H2 data stays sealed.

## Parent-facing dispatch

Name exactly one next experiment, **LSP0, the late side-price cap**. LSP0 is a
stored-byte, oracle-side cap over the frozen late ages. It asks whether current
side-relative price order retains the required fraction of the B0 ceiling
before the program builds a causal late roster or fits anything.

This page does not start LSP0. It does not start a picker, a feature plane, a
training-scale relabel, or tickets 37, 46-at-scale, or 47. Parent Grok
reconciles this page with the Fable sibling. Fable's named experiment is the
live walk.

## The measured room

B0 Stage 1 is LIVE. The age-600 cell-best line posts 2726.81 / 3775.72 /
3847.62. The late envelope posts 2874.91 / 3942.93 / 4058.61. Both lines have
`max_drawdown_usd` 0, zero overlap violations, and no more than 9 entries on a
portfolio day. HG still clears at 7200 seconds with 2055.46. HG misses at
10800 seconds with 1582.77. NKD and SI clear at every frozen late age.

The result closes price decay as the immediate bottleneck. It does not show
that any causal picker can identify the paying name. `picker_started` and
`feature_plane_started` are both false in the B0 receipt.

## The root cause and the next unknown

S1 failed because the favorable within-side record kept improving late. Its
turn rule abstained on the deep winners and entered the shallow reversals. Even
with oracle side, the turn and record lines posted only 1026.21 / 1239.91 /
1112.97 and 811.50 / 1084.46 / 801.73. The fitted caller failed after that.

B0 verifies the first half of the repair. Waiting keeps enough exact dollars.
The next unknown is narrower.

> At a frozen late age, does current side-relative entry price identify enough
> cash inside the correct side to meet the same-age capture bar?

LSP0 answers that question with an optimistic cap. A failure kills the
pre-named S-suite price-order port. A survivor only earns a new covering
decision for an honest causal roster.

## The late store is a label boundary, not a picker boundary

`engine/entry_v2/late_teacher.py` stores current `entry_bid_px`,
`entry_ask_px`, and `entry_mid2` only when a row is `READY`. A row with
`NO_CERTIFIABLE_SUFFIX`, `NO_SNAPSHOT_BBO`, or `PHASE_CLOSED` carries none of
those fields. Future label availability therefore decides which current prices
the stored table exposes.

A real late picker cannot know `READY` at entry. Treating the stored roster as
causal would leak the outcome protocol into the picker interface. LSP0 instead
marks its price line as `ORACLE_READY_CAP`. Oracle side, full-roster hindsight,
and future-ready eligibility all favor the line. The line can kill its own
price-order shape. It cannot promote a policy.

If LSP0 leaves room, the next covering must first specify a causal snapshot
plane that keeps current BBO for every observable candidate, including rows
whose future label is unavailable. The label store never becomes that plane by
renaming a status or filling a blank.

## The capture bar is frozen before the read

For each asset and age, LSP0 capture is the cap's `usd_per_asset_day` divided by
the B0 cell-best value at that same age. The cap must reach the fraction below
to clear the dollar rung. HG at 10800 seconds is excluded because the B0
ceiling itself misses.

| age, seconds | HG ceiling | HG required | NKD ceiling | NKD required | SI ceiling | SI required |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 600 | 2726.81 | 73.35% | 3775.72 | 39.73% | 3847.62 | 38.99% |
| 1200 | 2682.97 | 74.54% | 3662.96 | 40.95% | 3796.07 | 39.51% |
| 2400 | 2571.71 | 77.77% | 3509.42 | 42.74% | 3700.81 | 40.53% |
| 3600 | 2475.10 | 80.80% | 3361.61 | 44.62% | 3589.03 | 41.79% |
| 5400 | 2264.06 | 88.34% | 3115.15 | 48.15% | 3380.50 | 44.37% |
| 7200 | 2055.46 | 97.30% | 2856.91 | 52.50% | 3117.32 | 48.12% |
| 10800 | closed | closed | 2336.65 | 64.19% | 2503.77 | 59.91% |

The table rounds for display. The scorer derives each bar from the full-precision
B0 receipt and the exact rung.

The all-asset age-600 witness remains the primary control. Its HG bar is 73.35
percent. This is well above T28-grade capture of 23 to 58 percent. LSP0 reports
every frozen late age, but it may not add an age or move an anchor after the
read.

## Architect sketch one. Factor side from within-side price

Shape S keeps the S-suite decomposition. One decision chooses a side. A second
decision chooses a name inside that side from current price order. Waiting is
allowed to change both the entry price and the information available to the
event stream.

The caller's eventual interface is small. It supplies a causal `SideCall` and
a causal `WithinSidePick` at one frozen age. Replay returns one selected name or
an abstention. Teacher status and cash stay behind the scoring boundary.

LSP0 is Shape S's first cap. It gives the side decision to an oracle and gives
the within-side decision future-ready eligibility. It then measures whether the
single frozen score, `side * entry_mid2`, can retain the B0 cash. This is the
cheapest result that can reject Shape S before a causal feature build.

Shape S has a strong prior. At age 180, oracle side plus side-relative entry
price missed cell-best by only 5.42 / 8.51 / 10.65 per asset-day. Its weak point
is equally clear. The 180-second causal rule and caller both failed, so a late
cap must not be mistaken for a working composition.

## Architect sketch two. Rank the whole late trajectory

Shape J removes the side seam. Each candidate reaches age A with its side,
formation state, and a causal path of repriced mids. One joint scorer ranks all
names from that path. Side is an input to the score, not a separately called
bit.

Shape J is structurally distinct. It can use displacement, record persistence,
and path shape across the frozen ages. Those fields did not exist in C's
age-180 feature plane, so C does not close the shape. The design also avoids a
caller whose 180-second accuracy sat near coin.

Shape J loses the next slot because the current label store cannot expose its
causal roster. It needs a new snapshot plane before even an unfitted score is
honest. A fitted joint ranker would also reopen a large design space without a
minutes family cap. Testing one displacement scalar would kill only that
scalar. It would not decide whether the whole shape deserves the feature build.

## Arena comparison and synthesis

The rubric grades capture reach, causal honesty, root-cause fit, first receipt
cost, result value, and design size.

| criterion | Shape S, factored late price | Shape J, joint late trajectory |
| --- | --- | --- |
| Reach | Bounded now by an oracle-side price cap against every legal fixed age | Can reach the B0 ceiling in theory, but has no narrower stored-byte family bound |
| Causal honesty | The cap is explicitly noncausal; a survivor must build a causal roster | Honest only after a new snapshot plane includes every observable candidate |
| Root-cause fit | Tests whether waiting makes terminal price order informative inside the right side | Lets a model learn terminality from the whole repricing path |
| First dollar receipt | One additional read of 582 stored shards, expected in minutes | Feature build, scorer design, fit, and then a dollar read |
| Result value | KILL rejects the pre-named port; ROOM prices the causal build | A failed first score rejects one flavor; a fitted survivor spends too much before a bound |
| Design size | One cap script and one receipt | New feature schema, builder, learner, and replay policy |

Shape S wins as the arena base. Shape J contributes one load-bearing condition.
Any Shape S successor must use a causal snapshot boundary rather than the
READY-filtered late labels. The joint fit, feature builder, and training-scale
relabel are rejected from this unit.

Both sketches pass the architect red-flag screen after that graft. LSP0 has one
path-only interface and hides parsing, validation, selection, nulls, and replay
behind it. Teacher information stays inside an oracle-cap type. No public
policy type can accept the cap. The design adds no pass-through module and no
stage framework.

## The one next experiment. LSP0.

LSP0 uses one new script and one receipt.

```text
python3 .audit/score_threshold_late_side_price_cap.py --selftest
python3 .audit/score_threshold_late_side_price_cap.py
```

The future runner writes `.audit/score_threshold_late_side_price_cap.py` and
`.audit/threshold-late-side-price-cap.json`. The receipt schema is
`QRE2THRESHOLDLATESIDEPRICECAP1`. The script takes the B0 receipt and the strict
late manifest as its only data interfaces. One deep function owns manifest
validation, row validation, grouping, cap selection, null construction, and
family-ruler replay. Helpers remain private. No generic picker framework is
created.

### Frozen data and ages

LSP0 reads exactly the 582 shards pinned by the B0 manifest. It performs one
additional dollar read over that store. It opens no stored teacher, candidate,
event, pivot, forecast, 2021, or 2025 file. The verdict ages are these fixed
sets:

- HG uses 600, 1200, 2400, 3600, 5400, and 7200 seconds.
- NKD and SI use those ages plus 10800 seconds.

The cell key is `(asset, d8, phase)`. The age-A oracle side is the side of the
READY row with maximum age-A `cert_close_usd`, tied by smallest `candidate_id`.
The oracle side remains defined when the maximum cash is non-positive.

### Frozen lines

The receipt carries three dollar lines at every legal age. No fourth scored
rule may appear.

1. `cellbest_control` reproduces the matching B0 per-age block byte for byte.
   It retains B0's positive-cash entry clause because it is only a source
   control.
2. `oracle_side_late_price_ready_cap` selects from READY rows on the oracle
   side. It minimizes `(side * entry_mid2, candidate_id)`. It enters the chosen
   row without a positivity filter. Its `causal_status` is
   `ORACLE_READY_CAP`.
3. `wrong_side_late_price_ready_cap` applies the same selection to the opposite
   side. It has the same future-ready advantage and no positivity filter.

The score is entry price by design. The receipt does not present it as an
independent feature. The experiment asks whether its within-side order carries
cash beyond chance.

For each age and asset, report W from line 2, L from line 3, W divided by the
B0 same-age ceiling, and `p_star = (rung - L) / (W - L)`. Report `p_star` as
undefined when W is not greater than L. Every line uses the locked family ruler
and reports cash, trades, per-trade mean, per-day dollars, drawdown, entries,
and overlap.

### The score's own null

Each age and side line gets a deterministic within-cell null. For permutation
IDs 0 through 39, reorder `entry_mid2` across READY rows inside the same
`(asset, d8, phase, age, side)` group. Keep candidate identity, cash, status,
and side fixed. Sort source prices by `candidate_id`. Sort destination rows by
SHA256 of `permutation_id`, a tab byte, and `candidate_id`, with
`candidate_id` as the tie-break. Assign the source prices to destination rows
by index. No random seed or library RNG enters the receipt.

The null reports the aggregate 95th percentile and the mean null cash for each
asset and age. The 95th percentile is the 1-indexed nearest-rank item 38 in the
sorted 40 values. It also reports the paired per-day spread between the real
line and the mean of the 40 null lines. Its standard error is the sample
standard deviation of those daily spreads divided by the square root of the
locked day count.

The age search gets a family null. For each permutation ID and asset, take the
maximum null capture across that asset's legal ages. The family 95th percentile
is item 38 of those 40 maxima. A witness-age price result is resolved only when
its real capture exceeds that family percentile and its paired mean advantage
at the witness age is at least two standard errors. The null never changes the
dollar rung or chooses the real witness tuple.

### Deterministic witness selection

First mark each asset-age line whose line 2 clears the asset's rung and
same-age capture fraction. Then enumerate the legal per-asset age tuples in
ascending `(HG, NKD, SI)` order. There are at most 294 tuples. Replay every
eligible tuple as one chronological portfolio line. No tuple may mix cell-level
ages inside an asset.

The witness is the first eligible tuple with trades above zero,
`max_drawdown_usd` below 1000, no more than 12 entries on any portfolio day,
and zero overlap violations. If no eligible tuple meets those constraints, no
witness exists. This exhaustive, frozen tuple rule prevents one arbitrary age
choice from killing a later legal witness. The null never chooses the tuple.

### Proof and wall limit

Run `--selftest` on synthetic rows before any era byte opens. Then prove these
mutants red for their named seams:

- `teacher_cash_in_price_key` smuggles `cert_close_usd` into line 2 selection.
- `wrong_side_pick_accepted` allows line 2 to cross the oracle-side boundary.
- `nonqualifying_age_accepted` lets HG 10800 seconds affect a witness.
- `ready_cap_marked_causal` removes the `ORACLE_READY_CAP` status.
- `null_cash_permuted` shuffles cash instead of price.
- `corrupt_candidate_id_accepted` changes a shard identity after manifest pinning.

The clean selftest and every mutant command enter the receipt with exit codes.
The baseline must pass and every mutant must fail before the era read. A real
run refuses any mutant environment value.

B0 scored the 582 stored shards in 92.1 seconds. LSP0 adds 40 vectorized price
permutations and should finish in two to eight minutes on at most 13 effective
cores. Project from HG inside the same process. If the honest full projection
exceeds 30 minutes, stop before the remaining assets and write an
infrastructure receipt. No hour-scale fallback starts.

## Dollar stop

The receipt applies exactly one of these outcomes.

- **STOP.** Source or manifest pins drift, `cellbest_control` differs from B0,
  a row violates the late schema, a selftest or mutant fails its expected
  state, more than one store pass is attempted, or the projection exceeds 30
  minutes. Report the blocker. No successor starts.
- **KILL_PRICE.** Any asset has no legal fixed age whose line 2 clears its rung
  and same-age capture bar, or none of the at most 294 eligible fixed-age tuples
  meets the drawdown, cap, position, and overlap laws. This closes Shape S's
  late current-price port on the locked era. It does not close Shape J or the
  program. Return to covering. Nothing starts automatically.
- **PRICE_UNRESOLVED.** A combined dollar witness exists, but at least one
  witness-age line fails its family null test or has W not greater than L. The
  oracle-side dollars exist, but current price order has no resolved claim.
  Report W, L, capture, `p_star`, nulls, and paired standard errors. Return to
  covering. Do not fit.
- **PRICE_ROOM.** A combined dollar witness exists, every witness-age line
  passes its family null test with W greater than L, and every charter
  constraint holds. This prices a new covering decision for a pilot causal
  snapshot boundary. It does not authorize a feature build, a fit, a picker,
  a relabel, or a 2025 read.

Teacher cash can kill LSP0. `PRICE_ROOM` cannot promote a policy.

## Receipt fields and fences

The receipt pins this page, the live brief, the B0 receipt and scorer, the B0
judge, the late manifest, the late schema implementation, the S0 receipt and
scorer, and the frozen family ruler. It records these facts:

- `dollar_line_reads` is 1 and `passes_over_late_store` is 1.
- `picker_started`, `feature_plane_started`, `fitted_read`,
  `training_scale_relabel_started`, and `successor_started` are false.
- `engine_files_touched` and `tickets_started` are empty.
- `opened_2021_files` and `opened_2025_files` are zero.
- The qualifying ages, capture table, three line names, null law, witness law,
  and this dollar stop appear verbatim.

LSP0 may not add a score, age, threshold, feature, learner, confidence gate, or
per-asset rescue after the read. It may not parse or join a source candidate,
teacher, event, pivot, or forecast table. It may not fill missing late BBO,
treat `READY` as causal, change a late shard, or write outside its scorer and
receipt. It may not rerun B0, S0, S1, C, or any 2021 kill as a new result.

## Architecture and arena receipt

- Architect Ground traces S1's terminal-record failure into B0's measured
  late room and then into the late schema's future-ready boundary.
- Architect Sketch compares the factored late-price shape with a joint
  trajectory ranker. They have different seams, data needs, and first spends.
- Architect Agree is autonomous. LSP0 is named without a checkpoint because
  the brief asks for one experiment.
- Architect Implement and Scrap do not run. This page is the named receipt and
  the brief forbids implementation.
- Arena Frame grades reach, causal honesty, mechanism fit, cost, result value,
  and design size.
- Arena fan-out at the model level is parent-owned. This fresh Sol child writes
  only its isolated output. It does not spawn a nested writer or resume a
  chain.
- Arena Pick selects Shape S for the next slot. Shape J contributes the causal
  snapshot boundary that any survivor must cross.
- Arena Graft rejects the joint fit and keeps only that boundary condition.
- Arena Verify is the source and document proof below. Parent Grok performs the
  cross-model judgment after both covering files exist.

## Principles that changed the decision

- Exhaust the Design Space and Codebase Design forced two whole shapes and a
  real interface comparison. The selected cap stays behind one scorer boundary
  instead of creating a picker framework.
- Fix Root Causes changed the question from another side caller to whether
  waiting makes terminal within-side price order informative.
- Laziness Protocol and Subtract Before You Add removed the fit, feature plane,
  relabel, and source joins from the first spend.
- Redesign from First Principles treats the late store as a label boundary.
  It does not patch future-ready rows into a causal roster.
- Prove It Works adds the byte-equal B0 control, the score's own null, paired
  standard errors, and red-first mutants.
- Sequence Work into Verifiable Units ends LSP0 at one judged receipt. Any
  causal roster pilot belongs to a later covering decision.
- Guard the Context Window kept the large receipts behind targeted queries and
  avoided a second raw late-label read while designing the cap.
- Never Block on the Human selects one reversible experiment and pre-wires
  every outcome without returning a fork question.

## Next step

Parent Grok compares this page with
`.audit/briefs/threshold-covering-after-b0-fable-out.md` when that file exists.
Fable's choice is the live walk. If the reconciliation names LSP0, dispatch a
fresh Sol child with file pointers to this page, the live brief, the B0 receipt
and judge, the B0 scorer, the late manifest and schema implementation, the S0
receipt and scorer, and the frozen family ruler. The child stops at
`.audit/threshold-late-side-price-cap.json`. The parent continues.

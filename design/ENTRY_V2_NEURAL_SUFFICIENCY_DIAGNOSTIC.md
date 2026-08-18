# Entry V2 Neural Sufficiency Diagnostic

> **Implementation specification; experiment not completed.** As of
> 2026-08-18 UTC, the authoritative replacement run never reached C0 neural
> training. None of the five arms, two shared pretexts, 44 real/44 shuffled
> objective screen, direct-vs-CatBoost matrix, fit-only ceiling-recovery gate,
> or held E1/E2/E3 stages has produced a result. The latest attempt stopped in
> `raw_fidelity` on a 236-diagnostic/235-learner session-domain mismatch. The
> correction now in the dirty tree is not production-verified. See
> [`../docs/ENTRY_V2_CURRENT_STATUS.md`](../docs/ENTRY_V2_CURRENT_STATUS.md)
> before using this frozen design.

## Status and authority

This is the frozen implementation specification for the first failed learned
boundary in the Codex Entry V2 recovery plan.  Its authorities are:

1. `ENTRY_V2_RECOVERY_PLAN.md`;
2. `ENTRY_V2_RECOVERY_PLAN_AMENDMENTS.md`;
3. the current QRE2 source/corpus/teacher/replay contracts; and
4. the immutable E3 v4 receipts named below.

Old `D-*` directives and old Claude-era designs are not authorities.  This is
development work only.  It may read no date after 2025-06-30 and it may not
open 2025H2.

The purpose is not to choose a fashionable architecture.  It is to identify
and repair, in one loaded-corpus experiment, the first failing layer among:

- input fidelity and field survival;
- neural optimization competence;
- sparse or mis-grouped supervision;
- raw-sequence representation and time-scale memory;
- the shared neural decision head;
- the downstream ranker;
- calibration and threshold transport; and
- exact replay.

## Evidence that fixes the diagnostic boundary

The adaptive E3 evidence contains 98,471 candidates, 681 exact causal actions,
31,966 action-supervised rows, and 66,505 occupancy/cap-masked rows.  Exact-time
choice groups are almost all singletons: 98,467 of 98,469.  The selected-action
bit is therefore an exact deployment label but a sparse learning surface, not
a sufficient representation objective.

The current encoder receives all 16 continuous and five categorical QRE2 model
fields, but compresses the prefix into one 512-vector.  Its three training
stages each make only one session pass.  Its hard/listwise stage groups an
entire `(asset, day, phase)`, and its best-row target is the causal teacher take
in only 171 of 1,085 groups.  Current auxiliary path targets stop at five
minutes even though the minimum selected hold is 38.4 minutes and the median is
6.59 hours.

The held-forward diagnostic improved action AUROC materially when the complete
static/context vector was added to the frozen neural embedding, but still
transported no feasible threshold.  This proves that useful causal information
was discarded before policy fitting and that representation improvement alone
does not prove the ranker/calibrator.

Pinned prior evidence:

- E3 fold-store aggregate:
  `10e6db318eb7493b8a96618d1ca7ea2123e9f3ec876e43636232e54360b9eb0f`;
- prior corpus receipt:
  `5e830655243b5de2833de82111599343da4744a1e8169c6424ff50e13d003010`;
- prior model-input binding:
  `469e70a296819f91934b5650d5d9a9c234b1b76490a5f26a3e9e9f5407f5941f`;
- model-array conversion law:
  `de43e237702d6cf56cef8e7bfd3238fa26037c007c2c42dd9aef2069cdc7b593`.

The new diagnostic has its own schema and receipts.  The prior corpus and fold
are lineage evidence, not reusable neural checkpoints.

## Chronology

Every fair arm uses the canonical E3 fold:

- encoder/objective fit: `E3.fit_days`, ending 2022-03-11;
- cross-fitted calibration history: the first four prequential inner blocks,
  2022-03-14 through 2022-06-09;
- threshold and arm selection: the fifth inner block, 2022-06-10 through
  2022-06-30;
- frozen diagnostic test: all E3 rows, 2022-07-01 through 2022-12-30.

E3 has already influenced development, so this result is named an **adaptive
E3 production-faithful diagnostic**, not new OOF certification.  No E3 label,
metric, or replay result may select an objective, architecture, calibrator, or
threshold.  Later E4-E8 folds remain the forward evidence after integration.

## Complete event contract

No source field is discounted.  The raw route preserves, separately:

- receive-time seconds, microseconds, and nanoseconds;
- receive-minus-event microseconds and nanoseconds;
- exact price, bid, ask, size, bid/ask size, bid/ask count, sequence,
  `ts_in_delta`, and receive-session seconds;
- action, side, flags, depth, and the three-bit undefined-price mask.

Derived channels supplement rather than replace those fields:

- exact receive and exchange interarrival gaps;
- log interarrival, sequence gap, and causal tape rates over 1s, 10s, 60s,
  five minutes, and 15 minutes;
- action-by-side interactions for aggressive trades and resting-book updates;
- bit-expanded flags and explicit undefined-price states;
- midpoint, spread, size/count imbalance, price/BBO changes, and signed
  add/cancel/modify/trade flow;
- phase/session age and actual block-end receive time.

All derived values are computed strictly before the candidate cutoff from the
exact raw fields.  The field schema, equations, fit-only normalization, and
constant-field census are persisted.  Raw fields remain independently routed
even when a derived field is constant or redundant.  Any exact integer route
split into quotient and remainder coordinates carries one explicit, identical
validity channel per emitted coordinate; one ambiguous unsuffixed mask for a
multi-coordinate decomposition is forbidden.

## Cheap label/objective atlas

The atlas runs before expensive raw-encoder comparison.  It uses one fixed,
lossless, fit-normalized candidate/context/raw-summary view, one shared small
decision head, one optimizer budget, and identical chronology.  Only the
target or proper loss changes.  A small mixed-event encoder is fitted once per
chronological stage for representation-pretext cells; the raw tape is never
retrained separately for every label.

### Broad-discovery rule

The registry is mechanism-first, not finance-keyword-first.  It was formed by
scanning complete 2025 proceedings indexes for temporal, event, trajectory,
structured-prediction, decision, medical, vision, control, and forecasting
work and classifying supervision only after discovery.  Named finance labels
are coverage controls, not the discovery query.  In particular, recent work on
mixed-type marked events, structural path loss, transformed-label alignment,
label distributions, interval targets, process versus outcome reward,
competing-risk survival, and feasibility-aware decision learning contributes
mechanisms, not presumed edge:

- https://proceedings.neurips.cc/paper_files/paper/2025/hash/a6c7515ac435277dc92b75a07bb2257c-Abstract-Conference.html
- https://proceedings.mlr.press/v267/yuan25a.html
- https://proceedings.mlr.press/v267/kudrat25a.html
- https://papers.nips.cc/paper_files/paper/2025/hash/0cd62dea69635f4c5b569848267fe5a8-Abstract-Conference.html
- https://papers.nips.cc/paper_files/paper/2025/hash/9baded199ea27b236a9d2582f756c34f-Abstract-Conference.html
- https://papers.nips.cc/paper_files/paper/2025/file/570641fd4b0340cc8ba6320955de891f-Paper-Conference.pdf
- https://papers.nips.cc/paper_files/paper/2025/hash/54e1381d0c0598127b90af4c940fd3d9-Abstract-Conference.html
- https://proceedings.mlr.press/v258/alberge25a.html
- https://proceedings.mlr.press/v286/kong25a.html

“Every type” means every distinct causal target semantics below is registered
and reaches availability testing.  Infinite numeric parameterizations are
represented by joint heads and factorized axes.  Every factor level is
materialized and censused; invalid, unsupported, or byte-identical variants
are recorded and pruned, never silently omitted.

### One path scan and factorized truth

For each session build one immutable, candidate-neutral columnar truth index
over the authorized event mmap.  It retains every trusted economic mark and a
separate trusted-sane BBO index; it does not allocate a Python object per
event.  A candidate anchor supplies side, entry `mid2`, integer asset
multiplier, frozen cost, phase boundary, occupancy/cap mask, and the canonical
teacher/replay outcome.  PnL comparisons use exact integer units with
`2,000,000,000 units = $1`, so
`net_units = side*(future_mid2-entry_mid2)*multiplier-frozen_cost_units`.
Floating targets are produced only after truth is frozen.

The one verified QRE2 open has two physically separated views.  The input
plane contains only `[0, max_candidate_cutoff)` model arrays plus exact int64
receive clocks.  The outcome plane is the complete authorized session mmap;
it may construct the truth skeleton and is then closed, but it can never enter
a model input, fit normalizer, or cache key visible to the learner.

Truth state reproduces the native `BookQualityState` rather than inferring
trust from file membership.  A clean snapshot block increments generation
once; its first subsequent sane ordinary row seeds trust but is not itself a
target event.  A later clean ordinary one-sided row is a trusted message even
though it is not an economic BBO.  `MAYBE_BAD_BOOK` resets/taints the
generation until a valid snapshot, and standalone `BAD_TS_RECV` must already
have been quarantined.  `trusted_message`, `trusted_economic`, and
`trusted_sane_bbo` are therefore separate typed masks.  Sane BBO additionally
uses the phase-specific strictly-prior spread ceiling, not merely defined
prices or a global threshold.

Candidate and teacher economics are bound from their original decimal text.
Costs and native teacher values must convert integrally at
`2,000,000,000 units = $1`; no float round trip is authoritative.  The binding
retains the exact terminal `(receive time, source ordinal)`, exit reason, and
separate occupancy, asset-cap, and portfolio-cap mask causes.  `NO_SANE_SUFFIX`
rows remain in the truth roster with typed per-family availability.

Candidate truth starts at `lower_bound(ts_recv_ns, decision_ts_ns)`.  Neural
input is `[0, cutoff)` and the equal-receive-time batch belongs only to the
future label plane.  Every terminal boundary is the ordered key
`(ts_recv_ns, source_event_ordinal)`, not timestamp alone.  The first $900 wall
is found by the index and reconciled with the canonical outcome; phase close
is inclusive and wall wins an exact-clock tie.  Economic exits may be carried
forward to a later fixed horizon.  Generation, source, and development
boundaries are right censors with no numeric target.  The development wall is
`1751320800000000000` (`2025-06-30T22:00:00Z`); H2 payloads are rejected before
open and are neither indexed nor queried.

The index is constructed exactly once per session and materializes all
candidates as a batch.  Vectorized `searchsorted`, compact min/max range
indexes, prefix sufficient statistics, and offline threshold queries provide
worst-case `O(N log N + C*(H+R+T)*log N)` with fixed horizon/rung/trend axes.
The resource receipt must report `candidate_suffix_rows_visited == 0`; any
candidate-by-future-suffix slice or Python per-event dictionary refuses.  The
compact columnar path skeleton contains explicit value, validity, censor
state, and provenance arrays for:

- resolved net PnL at `1s, 10s, 60s, 5m, 10m, 15m, 20m, 30m, 60m, 120m`,
  phase close, and FINAL; a fixed horizon uses the first trusted-sane BBO at
  or after its clock, while a prior economic exit is carried forward;
- MFE, MAE, earliest times to both, capture, giveback, retention, path range,
  and reward/risk efficiency;
- favorable, adverse, flat, and underwater occupation time and signed
  excursion area;
- trend sufficient statistics at `10s, 60s, 5m, 15m, 30m`;
- independent first-touch time and state for favorable dollar rungs
  `{300,600,1000,1500,2000}`, adverse rungs `{300,600,900}`, and strictly-prior
  scale rungs `{0.5,1,2} * sigma_prior` on both sides;
- separate typed boundary, endpoint, passage, and availability states.  At a
  minimum these distinguish attained, competing event, same-row tie, fixed or
  phase vertical expiry, wall absorption, generation/source/development right
  censor, no sane suffix, materialized, low support, missing prior, source
  semantics unavailable, and byte-identical pruning;
- future mixed-event targets: exact next receive-time gap, event-time latency,
  sequence gap, action, side, flags, depth, missingness, prices, sizes, counts,
  spread, and masks.

The independent touch table decodes every symmetric and asymmetric
triple-barrier view without another scan: dollar- or strictly-prior-scale
horizontal barriers; fixed or phase-close vertical barriers; hard three-state,
soft distance, first-passage time, joint cause/time, and multi-barrier
cumulative-incidence targets.  Gap-through values and same-event ties remain
explicit.  A censored row never becomes hard zero, soft distance, or negative
CIF mass; CIF targets carry cause-by-time at-risk and censor masks.  Triple
barrier is therefore one competing-risk family with complete variation
coverage, not hundreds of independent fishing hypotheses.

### Registered 24-cell screen

The eighteen semantic cells are:

1. mixed-type next-event time, mark, and continuous-attribute density;
2. future event count, intensity, mark distribution, and tape-speed by horizon;
3. fixed- and joint-multi-horizon terminal net PnL;
4. threshold and cumulative-ordinal terminal states at loss, $0, $600, $1,000,
   and $2,000+;
5. full future PnL trajectory patches;
6. MFE, MAE, and time to each extreme;
7. giveback, retention, capture, and reward/risk efficiency;
8. dwell, underwater time, excursion area, and multistate occupation;
9. single-event first-passage survival;
10. favorable/adverse competing risk, including every triple-barrier view;
11. trend-scan slope, t-statistic, sign, and selected causal window;
12. reversal, false-break, reclaim, and event-completeness state;
13. candidate-local payer and dollar-threshold meta-labels;
14. binding arrival-final action with exact occupancy/cap mask;
15. exact-same-time ranking, top-k, and soft-regret choice;
16. act-now versus wait/pass regret and temporal preference;
17. occupancy-aware shadow or marginal schedule regret; and
18. pathwise process utility versus terminal-outcome utility.

The six objective contrasts are:

19. endpoint Huber versus cumulative ordinal likelihood;
20. quantile, CDF, histogram/label-distribution, and CRPS endpoint losses;
21. modal or maximum-probability goal-achievement loss;
22. raw target versus strictly-prior robust-z, fit-only winsor, target-only
    percentile-rank, and fit-only DCT/wavelet trajectory transforms;
23. pointwise trajectory loss versus pointwise plus patch mean/variance/
    correlation structural loss; and
24. joint cause-by-time cross-entropy versus a censor-adjusted proper
    competing-risk score.

A label distribution is never fabricated from one realized path.  The
distributional cells learn a conditional distribution from one-hot,
interval-compatible, or typed-censored observations with proper scoring rules.

The executable registry contains exactly 44 `ProbeSpec` rows with per-cell
counts
`[1,1,2,2,1,1,1,1,1,4,1,1,1,1,3,1,1,2,2,4,2,6,2,2]`.
Every row names its callable materializer/loss, target and mask schema,
required atoms, transform provenance, support law, shuffle unit, action
mapper, and output hash.  Every real probe has one within-asset/day shuffled
twin (88 shallow fits); the two chronological mixed-event pretext fits bring
the registered E1 budget to exactly 90.  E2 refits at most four finalists and
their four shuffled twins, so the honest maximum through objective freeze is
98 optimizer fits.  Numeric horizons, barriers, transforms, and trend windows
are tensor axes rather than extra fits.  Startup refuses unless
all 24 cells have an executable implementation or an allowed typed
support/source/prior/pruning state; `NOT_IMPLEMENTED` is not an availability
state.

### Prunes, support, and occupancy

- Regimes are evaluation/conditioning strata, never future labels.
- Quantile, ordinal, modal, interval, transform, and calibration variants are
  axes, not duplicate semantic families.
- No transform is applied to categorical or survival-state targets.
- Horizons are joint masked outputs; there is no terminal-by-horizon fit
  explosion.
- A real ranking group requires at least two available candidates at the exact
  same decision timestamp.  Day/phase lists may be representation auxiliaries
  but cannot impersonate deployed choice sets.
- Occupancy/cap-masked arrivals receive zero action and choice-ranking weight.
  They may retain nondecision path/process targets.
- FINAL ordering uses `(take_target, final_margin, candidate_id)` and cannot be
  altered by an auxiliary horizon.
- Decision-focused replay loss is confirmation-only; it cannot mutate truth.
- Byte-identical labels collapse using screen-fit data only.

Availability gates are measured on fit data only: continuous cells require at
least 500 uncensored pooled and 100 per asset with nonzero IQR; binary/ordinal
cells require at least 200 observations per required pooled class and 25 per
class per asset; competing risks require at least 200 pooled and 25 per asset
per cause; exact-time ranking requires 200 groups pooled and 40 per asset; and
economic comparison requires 60 eligible asset-days per asset.  A miss is
`UNAVAILABLE_LOW_SUPPORT`, never repaired by calling censoring negative,
inventing traversal order, merging after confirmation, or substituting a
day/phase rank.  Each asset-day has total fit weight one; fit-only class weights
are capped at 4x and recorded, while evaluation is never reweighted.

### Chronology, multiplicity, and selection

SI begins on 2021-05-31, so shared atlas chronology starts there:

- E1 screen fit: 2021-05-31 through 2021-09-30;
- E1 calibration: 2021-10-01 through 2021-10-29;
- E1 held-forward screen: 2021-11-01 through 2021-12-31;
- E2 confirm refit: 2021-05-31 through 2022-03-11;
- E2 confirm calibration: 2022-03-14 through 2022-06-09; and
- E2 final objective selection: 2022-06-10 through 2022-06-30.

All 24 cells are registered before E1; unavailable cells remain in the ledger.
E1 uses hierarchical Holm at family level (`alpha=.05`) on day-clustered paired
real-label minus within-asset/day shuffled-label differences, then Holm within
a surviving family.  At most four nonredundant finalists reach E2.  E2 uses
one-sided 95% Romano-Wolf/max-t simultaneous intervals over finalists and all
three assets.  A finalist must beat its shuffled twin and have positive label
skill for every asset.  Predictive loss alone cannot select it.

Every usable cell passes through the same fit-only monotone action mapper to
the binding A-004 target, the same chronological calibration and threshold
law, and exact replay.  After oracle, shuffle, denominator, $/trade, MDD, caps,
cost, wall, and occupancy checks, rank survivors lexicographically by:

1. minimum across assets of the simultaneous lower bound on full dollars per
   asset-day;
2. minimum lower bound on causal-oracle capture;
3. mean full dollars per asset-day;
4. lower worst chronological MDD; then
5. lower parameter count and runtime.

The label family, axes, objective, weights, calibration, and policy mapping are
frozen before E3.  E3 is report-only and cannot rescue, remove, or reweight a
label.  The registered E1 budget is 90 fits: two shared mixed-event encoder
fits and 88 fixed-budget shallow real/shuffled probes.  E2 adds at most eight
optimizer refits (four finalists plus their shuffled twins), for a maximum of
98 through objective freeze.  Unsupported cells lower the actual count but
remain registered.

### One-pass attribution

Four anchor targets—mixed-event prediction, terminal PnL, competing risk, and
binding action—are evaluated through prophet replay, a deterministic
all-field raw-summary learner, raw-field reconstruction from the 512 state,
static/short/current/full-plus-bypass memory controls, the 24 objective cells,
and direct-neural versus GBT/CatBoost scoring on the identical representation.
This yields a mechanical diagnosis:

- oracle failure: path, teacher, candidate, or replay;
- oracle pass plus raw learner failure: insufficient causal information or a
  wrong target;
- raw learner pass plus state reconstruction/memory failure: neural
  compression or undertraining;
- state competence plus objective separation: label/loss failure;
- direct neural pass plus tree failure: GBT/interface failure; and
- predictive success plus replay failure: calibration, threshold, occupancy,
  or policy mapping.

If no objective qualifies, the atlas refuses before expensive raw training and
reports every support, competence, shuffle, and funnel statistic.  There is no
E3-driven retry loop.

## Shared decision module

Every neural arm emits `raw_memory[candidate,4,512]`.  Every fair comparison
strict-loads the same serialized initialization for:

- candidate query + asset embedding + normalized candidate-feature projection;
- existing typed slow-context encoder projected to one 512-token;
- two pre-norm candidate-to-memory cross-attention blocks, width 512, eight
  heads, FFN 2048, dropout zero;
- explicit ordered role embeddings for the four raw memories, one context
  memory, and four static chunks; role decoration is applied on copies so the
  persisted raw/static tensors remain losslessly auditable;
- asset adapters;
- action, ordinal/value distribution, expected value, top-three, rank, MFE,
  MAE, wall, time-to-peak, multi-horizon, and phase heads.

The complete normalized 1,865-vector static candidate/context summary is
constant-zeroed, padded, and split losslessly into four 512 tokens.  There is
no learned 1,865-to-128 compression on this bypass.  Its constant mask and
normalizer are fit-only and persisted.

Each frozen representation is evaluated through both:

1. the identical direct neural decision head; and
2. one per-asset `CatBoostRanker(PairLogit)` using the identical pair manifest.

This comparison separates representation/optimization failure from downstream
ranker and calibration failure.  CatBoost uses a fixed seed, no bootstrap,
zero random strength, fixed depth/trees/rate, no early stopping, and no E3
tuning.

## Raw encoder controls and custom model

The expensive matrix is fixed after atlas selection:

| Arm | Raw encoder | Objective | Static bypass |
|---|---|---|---|
| C0 | current hierarchical full-prefix | A0 current grouping | no |
| C1 | current hierarchy from the same pointwise checkpoint | atlas winner | no |
| L0 | LiT-style MBP-1 short-memory adaptation | atlas winner | no |
| L1 | same L0 raw checkpoint | atlas winner | yes |
| M1 | custom causal multiresolution event memory | atlas winner | yes |

The three genuinely different base encoders (`C0`, `L0`, and `M1`) are trained
once.  Their candidate-aligned four-token raw memories are then frozen into an
immutable file-backed plane.  `C0/C1` consume the same current-encoder memory,
`L0/L1` consume the same short-memory checkpoint, and `M1` consumes its own
memory.  The five objective/static-bypass arms train the shared decision and
objective heads from those exact frozen bytes.  Re-encoding the raw tape for
each objective epoch is forbidden: it confounds representation with objective
fine-tuning and multiplies raw work without adding information.

`L0/L1` are a mechanism control, never a LiT reproduction.  They use the last
64 visible events, four-event patches, bid/ask tokens, field-specific
categorical embeddings concatenated rather than summed, two attention blocks,
and a two-layer LSTM.  The final four valid recurrent states are the raw-memory
tokens.

`M1` is the intended long-horizon model.  Its API is explicitly two-stage:
`encode_session(events) -> session_cache`, then
`gather_candidate_memory(cache, cutoffs, decision_clocks) -> [C,4,512]`:

1. a field-preserving typed/gated event stem consumes every raw and derived
   channel;
2. regular 256-event blocks are batch-encoded exactly once by the local
   two-layer causal encoder and four-query pool;
3. token zero separately batch-encodes exactly
   `[max(0, cutoff-256), cutoff)`, so a short trailing session block cannot hide
   recent events;
4. exact candidate decision clocks—not the last observed event—define
   block-end bands `decision-H <= block_end < decision` for 60, 300, and 900
   seconds; candidate partial blocks are appended once;
5. batched one-layer width-256 GRUs encode the three bounded bands, while
   cached full-prefix GRU states make full history `O(blocks+candidates)`;
6. the four memory tokens are the most-recent raw block, one-minute state,
   five-minute state, and a projection of 15-minute plus full-session state;
7. the candidate query cross-attends only to this bounded memory, the typed
   context token, and the four lossless static tokens.

Regular blocks are encoded in chunks of at most 64.  Candidate recent and
partial windows are encoded in chunks of at most 32.  Both paths use exact
activation checkpointing during training so peak CUDA memory is bounded by one
chunk rather than a full session's block or candidate count; the receipt records
chunk counts and both observed high-water marks.

Its measured complexity receipt must state local work `O(N+256C)`, full-state
work `O(B+C)`, bounded band work `O(W60+W300+W900)`, and head work `O(C)`, with
actual `N,B,C,W` counts.  No candidate may replay its full prefix.  LiT windows
are gathered as a batch from the exact last 64 visible events; bid/ask fields
come from the bound schema and cross-patch attention is causal.

This combines useful temporal patching, attention, recurrent aggregation,
irregular-time encoding, and bounded retrieval without pretending a published
finance model supplies the edge.

## Optimization law

One arbitrary pass is not a convergence criterion.  For each base encoder,
reserve the final chronological 10% of fit days as fit-only validation.  The
field-survival reconstruction and dense pointwise oracle losses share one raw
forward/backward pass and one best checkpoint: maximum 12 epochs, patience 3.
Running two independent full-tape stages over the same rows is forbidden.  The
grouped atlas objective/shared decision head then trains from the frozen raw
memory plane for a maximum 6 epochs with patience 2; its optimizer cannot own
or mutate raw-encoder parameters.

Minimum improvement is 0.1% relative validation loss.  Persist every epoch's
component losses, gradient norms, parameter deltas, and checkpoint hash.  A
stage must execute at least two epochs and must not finish at a rising best
validation loss.  Reload the best checkpoint; do not tune these limits on E3.
The later production integration freezes the resulting E3-selected epoch law
before E4-E8.

## Mandatory competence gates

Competence clones use fit-only rows, are discarded, and cannot warm-start the
experiment.

1. **Raw fidelity/cutoff:** independently reproduce left `searchsorted` on
   `ts_recv`, exclude equal-time rows, verify prefix hashes/counts/types, and
   pass a synthetic before/equal/after decision pack.
2. **Every-field routing:** mutate each of the 21 raw fields independently and
   require a finite nonzero gradient in its own route and FP32 raw-memory
   `L-infinity > 1e-6`.  Undefined-price tests include mask-only and
   semantically consistent price-plus-mask mutations.
3. **Suffix invariance:** mutate/append every field at and after cutoff and
   require bit-identical CPU/FP32 memory, decision state, and outputs.
4. **Field survival:** a temporary decoder reconstructs the last visible row
   from raw memory alone.  On a deterministic fit slice require normalized
   continuous MAE at most `1e-3` and categorical accuracy `1.0`.
5. **Balanced decision overfit:** per asset use at least 32 positives and 32
   matched opportunity negatives; within 400 steps require AUROC/AP at least
   .995, action loss at most .02, and finite nonzero gradients through every
   common branch/head.
6. **Time-scale routing:** independently mutate recent, 0-60s, 60-300s,
   300-900s, and older events.  M1's designated token must change, while no
   suffix mutation may change any token.  Persist no-retrain token occlusions
   and replay/metric deltas.
7. **Teacher isolation:** mutating masked, auxiliary-horizon, or E3 labels
   cannot alter FINAL teacher IDs, fit inputs, objective selection, threshold,
   or earlier artifacts.
8. **Replay parity:** all fast sweeps and every selected threshold reproduce
   canonical exact replay, including equal-time ties, occupancy, caps, costs,
   wall, full denominator, and MDD.

9. **Layer-complete fit-only rehearsal:** on one bounded real E1-fit slice,
   the all-field raw learner, every neural memory arm, the identical direct
   head, and CatBoost/ranker must each fit the same balanced oracle teaching
   set to the competence thresholds above.  The actual atlas runner must then
   complete its target materialization, auxiliary fit, binding mapper,
   calibration, threshold sweep, and canonical replay on fit-only dates.
   Held-forward E1/E2 or E3 data may not be used to discover a learner, head,
   or runner that simply cannot fit the supplied signal.

The pre-payload mechanical suite also proves sparse first-on/after-horizon
sampling; economic carry-forward versus right censor; same-clock
source-ordinal terminal truncation; automatic wall/canonical teacher parity;
censored barrier masks and cause-by-time risk sets; hand-computed irregular
occupation/area/trends/mixed-event targets; exactly 44 real and 44 shuffled
probe specs plus two pretext fits; one session-index construction and zero
candidate-suffix visits; exact cutoff complement between neural and label
planes; and `N` versus `2N` resource scaling.

Constant empirical fields are labelled unidentifiable rather than silently
credited, but their routes must still pass the synthetic competence test.

## One-load execution and artifacts

Use one process-local exact session-array cache, one corpus build, and one
four-worker canonical preload.  The complete array plane must be an atomic,
read-only, disk-backed memory-map cache: anonymous-RAM retention of that plane
is forbidden.  Keep this cache alive for the atlas and all raw arms, validate
its path/stat identity on every mapping, and remove it only when the one owner
closes after campaign completion or a typed failure.  Train GPU arms
sequentially.  Do not overlap a CPU CatBoost fit with a GPU arm's CPU feeder.

The candidate-specific truth and derived-event planes obey the same law: each
session is atomically packed into one immutable read-only mapping immediately
after construction, and the anonymous arrays are released before the next
session.  Atlas materialization consumes that mapping once; sessions after E3
then unlink the full plane and retain only compact candidate atoms.  Retaining
all session truth/derived arrays anonymously until global finalization is
forbidden.

Fit-normalized expanded session planes are likewise built once and retained as
immutable file mappings.  After base-encoder training, candidate raw memories
are encoded once per base checkpoint and stored as immutable FP32 file maps.
Receipts must report misses, hits, logical bytes, encoder checkpoint hashes,
and measured `N/B/C/W` work.  A paired objective arm that reopens or re-encodes
its base raw tape is a hard refusal.  CUDA training uses BF16 autocast with
FP32 losses and checkpoint statistics; only one large encoder may reside on
the device at a time.
Refuse startup below 320 GiB available host memory.  Independently read the
effective cgroup-v2 `memory.max`/`memory.current` boundary before opening any
payload; after crediting only clean, non-shmem file cache, require at least
128 GiB of effective resident headroom.  Host `MemAvailable` alone must never
authorize a container whose cgroup cannot hold the in-process diagnostic
state.

Persist a separate diagnostic schema containing:

- chronology and all source/corpus/binding identities;
- action-mask, opportunity, horizon, endpoint, pair, and weight manifests;
- shared initialization and fit-only normalizers;
- per-arm initial, pointwise, best, and final encoder/head safetensors;
- four raw tokens, decision states, logits, auxiliary outputs, calibrators,
  thresholds, exact replays, and CatBoost models;
- competence, field/time-scale mutation, convergence, resource, and timing
  receipts;
- one SHA-256 per immutable payload plus one aggregate manifest, with no
  per-row hash hierarchy.

The runner is restartable at immutable stage boundaries.  No partially trained
arm is promotable.

## Selection, E3, and forward continuation

Choose exactly one arm/head pair on the final inner block before opening E3
economics.  For each asset, the eligibility floor follows the oracle-supported
predeclared law:

- full capacity: at least $2,000 per asset trading day;
- normal weak capacity: at least $1,500;
- low-capacity exception: at least $1,000 and chronological MDD below $500;
- always at least $600/trade and at least ten trades.

Rank eligible candidates by total selection PnL, lower MDD, then the frozen arm
order above.  Freeze the winner, calibrator, and thresholds.  Evaluate all E3
rows once.  Diagnostic arms cannot replace the selected winner after seeing
E3.  If E3 passes, integrate only that winner and continue one shuffled E3
control and E4-E8 forward folds in the existing hot cache.  If it fails, the
receipt must name the failed layer from the competence/atlas/head/calibration/
replay decomposition before the single integrated correction pass.

2025H2 remains sealed throughout.

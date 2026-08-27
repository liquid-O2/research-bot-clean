# Second opinion on the mill pivot

Sol peer advice, 2026-08-27. This page advises Fable. It does not authorize a run.

## A. Independent plan to the rungs

I wrote this section from `START_HERE.md` and the S0, S1, B2, and B5 judged receipts, before reading the standing charter.

### Measure a decision-time record first

Build one row for each frozen cell and each completed one-minute interval in EXPLORE. HOLD remains unopened. A row contains only own-asset information available by that minute, aggregated at one minute or slower. It also names the candidates that the frozen generator has made eligible by then. Attach outcomes only after the causal row exists, using the frozen wall-or-phase-close law on raw suffixes.

Each row needs these fields:

- the cell key, decision minute, available candidate ids by side, and one frozen causal pick per side.
- the oracle side under the raw-suffix outcome law, with ties or cells lacking a legal pick marked unresolved.
- the exact replay outcome, wall flag, and holding interval for a correct call, a wrong call, and abstention.
- causal summaries for the rule families below, plus lineage that proves every summary stops at the decision minute.

Use one entry convention for every family. At the close of the declaration minute, take the first legally seatable candidate on the declared side under a fixed causal tie-break. If none exists, abstain. Do not let each detector bring its own picker. That would make a timing result impossible to interpret.

Before fitting or sweeping a detector, publish four curves by asset and decision minute:

1. **Correct-side availability.** Replay the fixed pick with the side supplied by the raw-suffix oracle. Report cash per asset-day, drawdown, entries, candidate availability, and delay. This is the attainable timing ceiling, not a policy.
2. **Wrong-side damage.** Replay the same pick on the other side. Report loss quantiles, wall rate, drawdown contribution, and clustering by asset-day. S0 and B5 make this at least as important as mean side accuracy.
3. **Coverage feasibility.** Starting from the correct-side line, report cash and drawdown against coverage. Show random abstention as a neutral reference and hindsight best-value abstention only as a labelled optimistic bound. Derive the minimum feasible coverage separately for HG, NKD, and SI. Do not assume 50 percent is viable.
4. **Error budget.** Replace correct calls with wrong calls at predeclared rates. Show random replacements and wall-prone replacements separately. The first rung or drawdown breach gives a time-specific error budget. This is a stress measurement, not a linear mixture claim.

Kill a decision-time region if its correct-side optimistic line cannot clear all three cash rungs, the drawdown bound, the entry cap, and occupancy. A kill applies only to that timing region and fixed entry convention. Route it to later decision minutes or to the next entry convention before killing a detector family. A margin below two asset-day standard errors is unresolved, not a clear.

### Compare three genuinely different rule families

All thresholds are selected on side, coverage, and delay. No stored-teacher field is opened. Neither teacher cash nor raw-suffix dollars rank configurations. Exact replay is applied after one configuration per family is selected.

**Family 1, competing boundary hits.** From phase open, track the own-asset upward and downward excursion in units of a causal range scale. Declare the side whose excursion first clears a margin over the opposite excursion and remains ahead for a persistence interval. Sweep a small fixed grid. Use margins of 0.5, 1.0, or 1.5 range units and persistence intervals of 2, 5, or 10 completed minutes. A simultaneous hit abstains until one side separates. This family tests whether side is a first-passage fact.

**Family 2, candidate-record race.** Aggregate frozen new-extreme events into one-minute bins. For each side, track the cumulative event count, record improvement, and time since its last improvement. Declare only when one side leads on both count and normalized improvement for 1, 3, or 5 completed minutes. Use count leads 1, 2, or 3 and one predeclared normalized-improvement cutoff per asset from causal scale data. This family tests whether resolution is visible in the generator's own event process rather than in price displacement alone.

**Family 3, selective walk-forward caller.** Fit a small regularized logistic caller on predeclared 5, 15, 30, and 60 minute summaries of own-asset range, signed displacement, boundary persistence, and candidate-record imbalance. Train only on earlier days inside EXPLORE. Produce a side only when a calibrated confidence interval excludes 0.5 by a predeclared margin and the call persists at the next completed minute. Otherwise abstain. Sweep conditional-error targets of 1, 2.5, and 5 percent, not dollar thresholds. This family tests whether several weak timing facts become useful only in combination. It does not reopen the age-180 S1 family because its observations, decision times, and mandatory rejection rule differ.

Use chronological inner folds that preserve whole asset-days. Keep the feature list and grids identical across assets unless a scale parameter has dollar or tick units. Select one configuration per family by this order:

1. stay within the measured wrong-side error budget on every asset.
2. meet the asset-specific minimum feasible coverage.
3. minimize median declaration delay.
4. break a remaining tie by the simpler rule.

This ordering contains no cash target. After selection, run the frozen exact replay once for that family and report every asset, every day, the portfolio drawdown, the entry cap, occupancy, coverage, error count, wall count, and value by called and abstained cells.

### Kill order and successor routes

Run the correct-side timing ceiling before any detector. Then run Family 1, Family 2, and Family 3 in that order. Keep their outputs side by side. Do not amend an earlier family after seeing its cash.

A family dies on EXPLORE if its preselected rule fails any cash rung, drawdown, occupancy, or entry-cap constraint, or if every configuration misses the measured error-and-coverage region by more than two asset-day standard errors. A family also dies if a causal-lineage mutant can move a feature across the decision minute without failing the check. Passing EXPLORE means only "survives for a freeze proposal." It cannot promote and does not open HOLD.

Each kill has a named route:

- A boundary-hit kill routes to the candidate-record race because candidate arrival can resolve side without a large net displacement.
- A candidate-record kill routes to the selective walk-forward caller because weak path and event evidence may combine.
- A selective-caller kill routes to a competing-risks time-to-event family. That next family predicts which side reaches a predeclared decisive boundary first and rejects cells whose two risk intervals overlap. It remains own-asset and minute-scale.
- If the correct-side timing ceiling itself fails, route to a different causal entry convention at the measured declaration time. Do not infer that the goal is unreachable.

For any survivor, freeze one complete rule in writing. State its inputs, state updates, threshold, abstention law, entry tie-break, exact replay law, and kill bar. Only a later authorized read may open HOLD. That read cannot amend the rule.

## B. Critique of the standing charter

### Overall read

Keep the pivot. The charter asks the right broad question, protects HOLD, and refuses to turn an exploratory result into promotion. I would amend it before implementation. It treats a time-varying payoff comparison as a stable hidden state, exposes outcome-specific arrays too close to detector code, omits sources required by two named families, and prices frontier rules without stating that they pass through the full replay.

### The diagnosis claims more than the receipts identify

The statement that a trade is determined by `(asset, side, entry time)` is safe only as shorthand inside an already fixed cell, truth-quality plane, and replay state. `_OutcomeIndex.current` and `_OutcomeIndex.outcome` also depend on the phase close, the quality-specific trusted rows, the generation at the strict cutoff, the spread at entry, and the chronological occupancy state. See `engine/entry_v2/confirmation_index.py:122`, `engine/entry_v2/confirmation_index.py:143`, and `engine/entry_v2/confirmation_index.py:169`.

More important, the charter has not shown that each cell contains one stable hidden side. Its frontier defines `W(cell)` as the side with the best cert over all entry times. That label can be decided by one narrow future entry window and can disagree with the better side at the detector's actual firing time. Before importing a two-state regime model, measure `W_t(cell)`, the payoff difference between sides at the same legal time, and the number and timing of sign changes. A cell with three side reversals is a sequential decision problem, not a delayed reveal of one latent bit.

S0, S1, and B5 do not isolate side correctness. They change the clock and the within-side rule at the same time. S0 shows that one oracle-side, candidate-age, hindsight-price construction is safe. S1 shows that oracle side passed into the frozen turn or record rule still breaches drawdown. B5 shows that a 2400-second momentum call with common-clock entry walls often. Those receipts motivate the mill, but they cannot assign the entire difference to side error.

### The research is useful as analogy, not as a theorem about this data

The charter's research direction is sound, with narrower claims.

- Dai, Zhang, and Zhu obtain threshold stopping rules under a specified hidden Markov drift model and trading objective. That work supports testing a filtered posterior. It does not establish that these cells follow a two-state Markov regime or that the optimal thresholds survive the frozen wall and entries-only law. See [Trend Following Trading under a Regime Switching Model](https://epubs.siam.org/doi/10.1137/090770552).
- The quickest-change literature minimizes detection delay subject to a false-alarm constraint after specifying pre-change and post-change distributions. The mill has not identified a change point, and a wall is an economic outcome rather than the definition of a false alarm. CUSUM and Shiryaev-Roberts belong in F1, but the charter should drop the expectation that they dominate before their model assumptions are checked. See [Quickest Change Detection](https://arxiv.org/abs/1210.5552).
- Selective classification directly supports measuring a risk-coverage curve. Its classification loss is not this program's loss. Here the risk must include wall severity, loss clustering, timing, and replay drawdown. See [On the Foundations of Noise-free Selective Classification](https://jmlr.org/papers/v11/el-yaniv10a.html).
- Thresholdout is an interface that mediates adaptive holdout queries. An interleaved split by itself is not Thresholdout. The current one-read frozen-rule law is enough if the HOLD result is terminal. If later work permits another HOLD query, the output schema and query budget must be built before the first query. See [Generalization in Adaptive Data Analysis and Holdout Reuse](https://proceedings.neurips.cc/paper/2015/hash/bad5f33780c42f2588878a9d07405083-Abstract.html).

The trial log is necessary, but it does not by itself deflate anything. Deflated Sharpe corrects a Sharpe statistic for selection and non-normality. The mill's binding outputs are cash per asset-day and maximum drawdown. The current TSV also lacks a spec hash, code hash, split hash, null seed, parent trial, pre-registration time, per-asset error counts, and delay. It cannot yet prove how many choices were available before a result was seen. See [The Deflated Sharpe Ratio](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551).

### The cache needs a causal observation seam

`late_teacher._index_by_quality` builds one outcome index per candidate truth-quality key. `EventTruthColumns.candidate_columns` merges the chosen quality plane into the shared event columns. See `engine/entry_v2/late_teacher.py:316` and `engine/entry_v2/diagnostic_event_truth.py:109`. The proposed cache stores those quality-specific trusted arrays, then asks detector code to derive one-minute price summaries from them. That leaves an unresolved choice. A detector can accidentally observe a path selected by the candidate it will later score.

Expose two separate interfaces:

- `prefix_at(cell, minute)` returns one canonical, candidate-independent observation state with a pinned quality law.
- `evaluate(entry)` owns all quality-specific suffix arrays and returns the exact outcome plus a replay-ready arrival.

Rule functions receive only the first type. A mutant that swaps candidate quality keys must leave every detector feature unchanged while it may change outcome certifiability. This separation is stronger than a promise not to read a suffix field.

The cache also does not contain the sources needed by F3 and F4. Its listed arrays have no prior-day high, low, or close and no forward-vol forecast, forecast vintage, or as-of timestamp. Either add those causal inputs with source hashes and timestamp-parity checks, or remove F3 and F4 from the claim that the first cache serves every family. Forecast availability must be checked at each decision minute, not joined by trading day alone.

### Entry legality and replay need to be explicit

`outcome_at(cell, side, t_ns)` can price an arbitrary side and time even when no frozen candidate on that side has formed. The frontier must report legal side availability and attach each synthetic timer entry to a causal frozen-candidate anchor. Otherwise the cash surface expands the generator while claiming that the generator stayed frozen.

The charter's joint table names `_drawdown`, but not `replay`. That is insufficient for a rung or family kill. `engine.entry_v2.replay.replay` applies occupancy, exact same-time ranking, the shared twelve-entry daily cap, expected-session denominators, and chronological per-asset drawdown. See `engine/entry_v2/replay.py:291` and `engine/entry_v2/contracts.py:352`. Independent cell certs are useful frontier measurements. Every economic verdict must feed replay-ready arrivals through the full function.

The per-asset split also breaks complete portfolio days. Keep it because it is frozen, but label EXPLORE portfolio-cap results as partial-day diagnostics. Prove the cap structurally if one entry per cell bounds the portfolio below twelve. Do not claim that a partial calendar-day replay measured cap contention.

### The first frontier has the wrong side label and weak nulls

Replace the single `W(cell)` with a time-indexed label under one fixed entry convention. Report ambiguity when the two sides are tied or when the preferred side changes inside the proposed declaration window. A global best-time winner is a useful upper bound, but it must not become the training label by default.

A deterministic side flip is a polarity control, not a null distribution. A time jitter is a valid null only if it preserves the cell's legal risk set, phase remaining time, and candidate availability. Use asset-day block randomization or a within-cell random-side null with fixed seeds, then use a max-statistic across the predeclared grid if the same null supports many thresholds. Two standard errors on every line do not control a large adaptive sweep.

The 30-second cash lattice is acceptable as a labelled economic bound. Detector decisions and feature updates should stay on completed one-minute boundaries. Otherwise the implementation quietly moves the mill back toward a speed edge and doubles the trial count for no stated benefit.

### Change the family order in two places

F4 is not a side caller. It is the abstention policy that decides whether coverage can carry the rungs. Measure the value-coverage bound before F1, then apply one predeclared F4 gate to the single side-selected representative of each family. Do not search every F1 threshold crossed with every value gate on cash.

Move the real post-wall re-entry arm out of the first mill. One wall spends nearly the whole drawdown allowance and creates a stateful second-entry policy with new occupancy and count interactions. Keep a measured-not-entered adverse-excursion statistic as a causal F1 input. A real wall-triggered re-entry can be a later family with its own exact replay bar if the virtual probe survives.

Add a two-hypothesis sequential family that does not assume a change point. A finite-horizon likelihood-ratio or competing-risks rule can accumulate evidence for positive side, negative side, or neither, then abstain when the two intervals overlap. This is distinct from one-sided change detection and from the fitted F6 HMM.

## C. Three frontier measurements I would require

### 1. The time-indexed side and stability map

For every legal cell-minute, compute the exact outcome for both sides under the same fixed causal entry convention. Publish `delta_t = pnl(+1, t) - pnl(-1, t)`, the preferred side, legal availability, and remaining phase time. Summarize the first time the preferred side becomes stable, the number of later flips, and the cash left at that time. This tests the charter's hidden-side premise before any detector is judged against it.

### 2. The matched error-to-wall and drawdown curve

At the same time and with the same picker, cross side correctness with wall outcome. Report wall and loss-tail rates for correct calls, wrong calls, and ambiguous labels by asset and time bucket. Then inject wrong calls into the oracle sequence at fixed rates under random and wall-prone placements and run the full replay. The first cash or drawdown breach is the measured error budget. This is the missing link between the receipt wall counts and the claim that wrong-side tolerance is near zero.

### 3. The value-risk-coverage frontier

For each asset and coverage level, publish three lines. The first is a hindsight top-value bound. The second is random abstention. The third selects cells only by a causal confidence or value gate learned on earlier EXPLORE days. Each line reports conditional side error, entered-cell mean, abstained-cell mean, delay, exact cash per asset-day, and replay drawdown. This reveals whether abstention removes hard low-value cells, easy high-value cells, or the cells the rungs need.

## D. Receipt reinterpretation check

I can break the implication in Fable's chain, though not the recommendation to make abstention central.

First, the receipts do not establish that wall events are almost exclusively wrong-side events. S0's oracle-side price line has MDD 192.50 and, by the charter's report, no walls. That proves one side-and-timing construction is safe. It does not prove that correct-side entries at other times are safe. S1 is the direct warning. Its oracle-side turn line has MDD 5,430.00 and its oracle-side record line has MDD 3,732.50. Correct side did not rescue those timing rules. In the other direction, S0's wrong-side price line remains positive on every asset at 506.35, 588.03, and 598.97 dollars per asset-day, with MDD 1,533.75. Wrong side is not uniformly a wall.

B5 changes both the clock and the rule. Its 24 to 41 percent wall rates are not reported as a contingency table against oracle-side correctness at the same entry time. Calling the B5 side a coin does not identify which calls caused its walls. The matched measurement in section C is required before the word "exclusively" is supportable.

Second, MDD is path-dependent. One wall is dangerous under a 1,000 dollar bound, but the number and clustering of wrong calls matter, as do losses on correct calls and profits between them. S0's cash-only `p_star` values permit substantial error under its own picker. The drawdown rule may make the admissible error much smaller, but no receipt computes that threshold for the proposed timing policy. "Near zero" is a sensible design target. It is not yet a measured limit.

Third, selective sequential detection is a good working frame, not a forced conclusion. The data may contain a stable side that becomes observable, a side whose economic preference flips with time, or only a narrow entry window. Classical quickest detection covers the first case after its distributions are specified. The first frontier measurement must distinguish the cases.

The abstention arithmetic itself is correct. With 3.06 cells per asset-day and one entry per called cell, coverage `c` requires a pre-error entered mean of at least

`required_mean_a(c) = rung_a / (3.06 * c)`.

At 50 percent coverage, HG needs about 1,307 dollars per entered cell and NKD and SI each need about 980 dollars. At 70 percent, those numbers fall to about 934 and 700 dollars. Occupancy skips would raise them.

The inference needs one qualification. A selected high-value half can out-earn the full oracle mean. A confidence gate can also do the opposite and retain easy but low-value cells. Therefore 50 percent coverage is neither impossible nor sufficient. The hindsight top-half value is the upper bound, and the causal value-risk-coverage curve says whether a detector can approach it without using cash to rank cells.

My revised chain is narrower. S0, S1, and B5 make side error, timing, walls, and abstention the four co-binding measurements. They do not prove that side error alone explains walls or that the admissible side-error rate is already known.

## E. Explicit deltas against the charter

### KEEP

- **Exploratory tier and quarantine law.** EXPLORE can kill and cannot promote, and HOLD stays closed until one rule is frozen for one read. This is the right response to the prior read-peek-amend failure.
- **Frozen economic law.** Keep raw-suffix wall-or-phase-close outcomes, exact costs, fixed wall, fixed size, fixed count, frozen generator, and the bans on teacher cash, late labels, 2021, and 2025 bytes.
- **Build once and reproduce B5 first.** The synthetic strict-cutoff and wall mutants plus end-to-end B5 reproduction are the right entry gate for the cache.
- **Cheap families before fusion.** Keep zero-fit price and candidate-stream rules before a fitted posterior. Their failures identify missing information more clearly than another broad model fit.
- **Struck families.** Keep order-flow, microstructure, and cross-asset lead-lag out of the catalog.

### AMEND

- **Diagnosis.** Replace the stable hidden-side assertion with a hypothesis. Define the decision by cell, canonical quality plane, side, time, and replay state until the stability map proves which coordinates can be dropped.
- **Research anchors.** Present HMM, CUSUM, Shiryaev-Roberts, and selective classification as conditional designs. Remove claims of optimality or expected dominance until their assumptions are tested on the cell-minute records.
- **Cache spec.** Separate a candidate-independent causal prefix interface from a quality-specific suffix evaluator. Add the prior-level and forward-vol sources, as-of times, hashes, and leakage mutants before claiming support for F3 and F4.
- **Cash surface.** Require a formed frozen-candidate anchor for each side and report unavailable cells. Use completed minutes for decisions. Keep 30-second points only as an explicitly non-policy upper bound, if they buy useful resolution.
- **Winner-side decay.** Replace global `W(cell)` with `W_t(cell)`, ambiguity, and stability duration. Do not train a detector against a best-future-time label without labelling that oracle.
- **Joint rule table.** Send replay-ready arrivals through `engine.entry_v2.replay.replay`. Report occupancy skips, cap skips, exact denominators, per-asset MDD, and partial-day limitations.
- **Nulls and uncertainty.** Treat side flip as a control. Use risk-set-preserving, asset-day-block nulls with fixed seeds and a grid-level max statistic. Keep the two-standard-error rule only after this multiplicity step.
- **F4 ordering.** Measure value-coverage first and apply one predeclared gate to each family representative. Do not choose a cross-product of detector and gate by cash.
- **HOLD interpretation.** Keep the frozen per-asset split, but describe it as interleaved interpolation. A later 2021 kill read can test temporal transport and still cannot promote.
- **Hypothesis log.** Add immutable pre-result fields for parent trial, spec hash, code hash, split hash, outcome-law hash, null seed, registration time, and selection rule. Add per-asset side errors, walls, coverage, delay, and replay skips. Use `KILL`, `SURVIVES_EXPLORE`, or `UNRESOLVED`, never `LIVE`.

### ADD

- **Matched wrong-side stress replay.** Add the section C error-to-wall curve before calibrating an ARL or confidence threshold.
- **Time-indexed label stability.** Add a direct test of whether a stable hidden side exists and when it becomes stable.
- **Value-risk-coverage bounds.** Add hindsight, random, and causal selection lines so the abstention arithmetic is measured rather than asserted.
- **Feature isolation mutant.** Swapping outcome quality keys must not change detector prefixes. Moving a suffix row across the decision minute must fail the causal check.
- **A no-change-point sequential family.** Add a finite-horizon two-hypothesis or competing-risks detector with mandatory undecided output.

### DROP

- **Presumed CUSUM or Shiryaev-Roberts dominance.** The model class has not been established. Keep them as F1 candidates.
- **Per-trade crossing as `T_max`.** The binding target is cash per asset-day under coverage and replay, not a standalone mean per trade.
- **Real post-wall flip from the first mill.** It spends the risk budget and changes the policy state. Retain the virtual adverse-excursion probe and route a real re-entry rule to a later, separately frozen family.
- **Raw detailed HOLD reuse after a survivor read.** One frozen query may return its predeclared receipt. Any later query needs a mediator and a new user authorization, not another inspection of the same bytes.

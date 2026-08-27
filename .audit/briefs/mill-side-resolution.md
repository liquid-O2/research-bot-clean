# The side-resolution mill. Charter and build spec. Fable, 2026-08-27.

USER 2026-08-27 (memory #642, #643): the covering queue was pre-decided; E1 does
not start; the next build is a minutes-scale mill on when the side is known, not
another named scorer. This page is that pivot. It charters an **exploratory-tier
instrument**, not a promotion unit. Everything the mill produces can kill and
cannot promote (the ceiling receipt's own label is the precedent). B5 KILL, S1
KILL, S0 LIVE, B0 LIVE, B2 LIVE stay locked; nothing here amends them.

## The diagnosis this page acts on

Under the frozen execution law a trade is fully determined by
**(asset, side, entry time)**: entry at the last trusted quote strictly before
t, cost = spread x multiplier + fee, exit at the first -900 wall crossing or
phase close (`engine/entry_v2/confirmation_index.py`). B5 proved from bytes
that all same-side names in a cell share one fill (`_validate_common_fill`, the
red `per_candidate_snapshot_reprice` mutant). The name layer is a lossy
coordinate system over a two-dimensional choice. Every unit so far explored a
one-dimensional slice of it: fixed per-name age (C, S1), fixed common clock
(B3/B4/B5), teacher-labelled batch photos (B0/B1/B2). The receipts agree:

- S0: oracle side + within-side price order = 99.7% of cell-best. Two oracle
  bits, not one: the side AND the stopping time (the payer forms late).
- S1: prefix features at 180 s carry ~nothing about side (0.53/0.51/0.50); the
  frozen turn/record wait rules anti-select even with oracle side (p* > 1).
- B0: the money survives waiting (age-600 cell-best is ~99% of ceiling; 2400
  still pays; 10800 does not). Waiting is cheap in cash.
- B5: momentum side at a fixed 2400 s clock is a coin (win 0.50/0.44/0.37) and
  entry mid-run eats the wall (wall rate 0.24/0.33/0.41, MDD 17k/41k/67k).
- B2's green was the READY suffix filter plus a non-executable batch clock; B5
  priced that leak at -2147/-2708/-3330 usd per asset-day.

The unmeasured object, and the mill's target: per cell, **when does the side
become causally knowable, and how much cash remains at that moment**. The
problem statement, restated correctly: per cell a hidden side reveals itself
at some random time; build a causal detector-with-abstention whose wrong-side
firing rate is ~zero (the MDD charter makes walls ~forbidden), whose firing
time leaves per-trade cash at or above the rung on entered cells, and whose
value-weighted coverage clears the day rungs. That is a **selective quickest-
detection** problem, and knowability is not only a function of waiting on the
price path: candidate-formation asymmetry, prior-day level structure, the
forward-vol forecast, and phase-scale path geometry are causal inputs no unit
has ever used. USER ruling 2026-08-27: no microstructure-flow and no
cross-asset lead-lag families — those edges are arbed by fast algos, we do
not compete on speed. Every detector input aggregates at one-minute scale or
slower; the edge is selectivity and patience at the holding horizon, not
information races.

USER axiom (2026-08-27, standing): the goal is achievable; a null indicts the
method, never the goal. The mill kills **families** and routes to the next
information source; "unreachable" is not a permissible verdict. The family
catalog below is ordered so each kill narrows where the information lives.

## Research anchors (each layer has prior art; use it, do not reinvent)

- **Hidden side as a regime state.** Dai-Zhang-Zhu, "Trend Following Trading
  under a Regime Switching Model" and "Optimal Trend Following Trading Rules"
  (Math. of OR): with drift switching between hidden bull/bear states, the
  sufficient statistic is the Wonham-filter posterior, and the optimal policy
  is threshold rules on that posterior (p_buy/p_sell hysteresis). The side
  question has a known-optimal form: filter, then threshold.
- **"When is it knowable" is quickest change detection.** Veeravalli-Banerjee
  survey (arXiv:1210.5552); CUSUM minimax optimality (Lorden, Moustakides);
  Shiryaev-Roberts optimality for Brownian drift changes (arXiv:1610.02680).
  Detection delay trades against false-alarm rate; here a false alarm is a
  wrong-side entry, i.e. a wall. The wall budget IS the ARL-to-false-alarm
  constraint, and it calibrates detector thresholds ahead of any cash read.
  CUSUM/SR are candidates, not presumed winners: their optimality is
  conditional on model assumptions the cell-minute records have not yet
  tested (Sol amendment, adopted 2026-08-27).
- **Abstention is a solved discipline.** Chow (1970) reject rule; El-Yaniv &
  Wiener, "On the Foundations of Noise-free Selective Classification" (JMLR
  2010): the risk-coverage tradeoff, with coverage as the OUTPUT of a target
  selective risk, not an input. Also "Trading via Selective Classification"
  (arXiv:2110.14914). Lopez de Prado's triple-barrier labels and meta-labeling
  (Advances in Financial Machine Learning): the frozen wall/phase-close law is
  a triple barrier, and a secondary gate that decides WHETHER to act on a
  primary signal is the standard precision-over-recall device. The charter's
  MDD bound pins us to the near-zero-risk end of the risk-coverage curve.
- **Struck by USER ruling 2026-08-27.** Order-flow-imbalance and cross-asset
  lead-lag families (Cont-Kukanov-Stoikov; Huth-Abergel) are rejected: those
  are sub-spread, sub-second edges harvested by HFT, and the frozen cost law
  (full spread plus fee) plus the phase-length holding horizon put them out
  of reach. Do not resurrect them in a future covering.
- **Stops only pay under serial correlation.** Kaminski-Lo, "When Do Stop-Loss
  Rules Stop Losses?": fixed stops destroy value under random walks and add
  value under momentum/regimes. Receipts agree: oracle-side entries never
  wall (S0 MDD 192.50 over 1,732 trades), coin-side entries wall 24-41% (B5).
  Wall events are a side-error meter, usable cash-free.
- **Not fooling ourselves on reused data.** Dwork et al., "Generalization in
  Adaptive Data Analysis and Holdout Reuse" (NeurIPS 2015, Thresholdout):
  EXPLORE/HOLD is the reusable-holdout design; when HOLD is eventually
  queried more than once, route the query through a Thresholdout-style
  noisy-comparison interface instead of raw reads. Bailey-Lopez de Prado
  deflated Sharpe / probability of backtest overfitting: every mill trial is
  logged in `.audit/mill-hypothesis-log.tsv` so survivor statistics can be
  deflated by the true trial count.

## Family catalog (the sweeps, ordered by information source)

Every family reads EXPLORE substrate only, prices with the frozen outcome law,
reports beside its side-flip and time-jitter nulls, and logs every trial row.
Kill criteria are per-family and pre-stated in the log row. A family kill
routes DOWN the catalog, never to "unreachable".

Timescale doctrine, per USER ruling: detector inputs aggregate at one-minute
scale or slower. No best-quote flow, no cross-asset lead-lag, no sub-spread
object of any kind (tombstones in the anchors section).

- **F1 price-path detectors** (waiting-based): CUSUM and Shiryaev-Roberts on
  signed one-minute mid increments, Page-Hinkley, range-position persistence,
  retrace-from-extreme (bounce), opposite-extreme quiet time. Zero-fit
  versions first; thresholds from the wall-budget/ARL calibration.
- **F2 candidate-stream asymmetry**: one-sided formation rates and gaps
  (extremes printing on one side while the other goes quiet), extreme spacing
  deceleration (exhaustion), depth-of-last-extreme vs prior extreme. The
  generator's zigzag stream is swing structure at exactly our horizon.
- **F3 level structure**: distance of the running extreme to prior-day
  high/low/close (`g1/priors`, causal), normalized by the forward-vol
  forecast range.
- **F4 value gates** (abstention shaping): forward-vol regime terciles, T53
  conditioner analogs computed causally from the prefix (activity, sweep
  speed, path variation), phase identity. Gates shape WHICH cells may be
  entered; they never call the side. The rung arithmetic makes them
  mandatory below ~70% coverage.
- **F5 wall-as-information**: measured-not-entered adverse-excursion probes
  only. The real post-wall re-entry arm is deferred to a later, separately
  frozen family: one wall spends the whole drawdown allowance and adds a
  stateful second-entry policy (Sol amendment, adopted 2026-08-27).
- **F6 fused posterior** (second wave): a walk-forward-fitted filter
  (Wonham/HMM-style on one-minute increments plus surviving F2/F3/F4
  evidence) whose posterior is thresholded per the Dai-Zhang-Zhu shape;
  EXPLORE-only fits, strictly prior days, the S1 leak discipline carried
  over.

Designed twice at the program level, recorded: Shape 1 runs F1-F5 as zero-fit
sieves first (kill-cheap, interpretable, minutes each); Shape 2 is F6, the
principled fusion of whatever survives as evidence. The substrate serves
both, so the sequencing costs nothing and the sieves' kills are the fusion's
feature selection. Rejected shape: jumping straight to F6, because a fitted
filter over dead features reads as "model failed" instead of "information
absent", and the program has already paid for that ambiguity once (S1).

## Quarantine law (what makes a many-read mill lawful)

`.audit/mill-split.json` (split_sha256
`b6d2decb1f3d6495e003a1a29a229195f4d4c1bdc0134d4195a1cc2c1c38f08f`) freezes,
by formula (per-asset d8 rank mod 3 == 0 over the B5 locked 582), an EXPLORE
set of 66/65/64 asset-days and a HOLD set of 131/129/127.

- The mill opens EXPLORE-day bytes only: candidates, candidate receipts, event
  packs. It never opens a HOLD-day pack, any teacher or late-label file, any
  2021 byte, or any 2025 byte. Ranking by stored teacher cash is banned; all
  mill cash comes from the frozen outcome law applied to raw suffixes.
- EXPLORE results are exploratory, reported with that label, and cannot
  promote. A survivor rule must be frozen in writing (covering-style page with
  a pre-stated dollar stop) before its single HOLD read. HOLD confirmation is
  not part of this build and does not start from this page.
- No engine writes. No exit-law, wall, size, count, or rung change. Denominators
  for any full-era claim stay 197/194/191; mill numbers are per-explore-day and
  say so.

## Substrate spec (build once, then hypotheses are array ops)

`tools/mill/build_substrate.py` writes one `artifacts/cache/mill/{asset}/{d8}.npz`
per EXPLORE asset-day plus a `manifest.json` (per-shard sha256 of the source
pack and candidates file, row counts, build stamp). Sources per shard, same
paths B5 used (`.audit/score_threshold_b5_common_clock.py:929-935`):
`artifacts/cache/port/entry_v2/g1/candidates/{asset}/{d8}.tsv`,
`.../g1/receipts/{asset}/{d8}.candidates.json`,
`artifacts/cache/port/entry_v2/events/{asset}/{d8}.qre2` (open with
`EventPack(path, verify_hash=True)`, check the receipt's `event_pack_sha256`
matches, same as B5 lines 1010-1021).

Per shard the npz holds:

- Per `truth_quality_key` (from `engine.entry_v2.late_teacher._index_by_quality`
  applied to the pack rows and the CLEAR candidates, exactly as B5 line 1022):
  the trusted-economic arrays `ts` (i64), `mid2` (i64), `bid` (i64), `ask`
  (i64), `generation` (u32). These are `_OutcomeIndex.ts/.mid2/.generation`
  plus the bid/ask at the same rows.
- Shared compact raw arrays `raw_ts` (i64), `raw_generation` (u32) for the
  whole pack (needed for `generation_at_snapshot`'s strict raw cutoff).
- The CLEAR candidate table: `decision_ts_ns`, `side` (i8), `phase` index,
  `phase_open_ts_ns`, `phase_close_ts_ns`, `entry_mid2`, `frozen_cost_usd`
  (f64), quality-key index per candidate, plus `candidate_id` strings in a
  sidecar json. Cell identity is (asset, d8, phase, phase_open_ts_ns), the B4
  law; multi-instance phase ordinals stay distinct cells.
- Meta: asset, d8, locked_iid, pack sha256, candidates sha256, counts.

`tools/mill/mill.py` exposes: `load_store(split, assets) -> CellStore`;
`outcome_at(cell, side, t_ns) -> cert/exit/wall` and a vectorized
`outcomes_grid(cell, side, t_array)` built on a per-cell adapter that
reconstructs the exact `_OutcomeIndex` arithmetic from the cached arrays
(entry quote = last trusted row strictly before t, generation from the strict
raw cutoff, wall via the segment-tree first-crossing law, cost recomputed from
the entry row's spread by the frozen formula). No entry outside
[phase_open, phase_close). Cells whose suffix is silent return None and are
counted, the B4 lesson.

## Binding checks before any measurement is believed

1. `--selftest` on synthetic rows in both builder and mill: a hand-computed
   phase-close cert, a hand-computed exact wall crossing, a strictly-before
   visibility case (a row exactly at t is future), and a generation-truncation
   case. Mutants via `QRE2_MILL_MUTANT` in {`visibility_at_t`,
   `wall_boundary_off_by_one`, `generation_carryover`} must each flip the
   selftest red. Selftest touches zero era bytes.
2. `tools/mill/check_b5_repro.py`: strict-load the B5 block
   (`engine.entry_v2.tabular_evaluation_policy.load_policy_block_result` on
   `artifacts/entry_v2/tabular_recovery/threshold/b5_common_clock_2400/real/raw_block.json`),
   keep the trades on EXPLORE days (about 190), and reproduce each end to end
   from the substrate alone: recompute the timer (ceil-second of first CLEAR
   formation + 2400 s), the formed roster, the argmax side with candidate-id
   tie-break, the timer quote, the frozen cost, and the outcome. Every
   reproduced cert must equal the block trade's PnL to the cent with equal
   exit semantics. Any mismatch is a builder bug; fix before any frontier
   number is read.

## First measurements (the frontier, before any rule fitting)

`tools/mill/frontier.py` over EXPLORE, per asset and pooled, written to
`.audit/mill-frontier.json` plus printed tables:

1. **Cash surface.** Per cell and side, cert-if-entered at t on a 30 s lattice
   from phase open to close (exact law at each lattice point).
2. **Winner-side decay.** With W(cell) = side of the larger best-entry cert,
   the curve E[cert entering W at t] and quantiles, t as seconds since phase
   open, since first formation, and as phase fraction. Where it crosses the
   per-trade rungs (about 667/500/500) is T_max per asset.
3. **Side knowability.** Accuracy-vs-t of parameter-free causal side calls:
   momentum (side of the last new running extreme, B5's rule), reversal
   (opposite of it), range position vs the running midrange, sign vs mid at
   first formation, sign vs running session mean. Each with both polarities.
   Where any stays a coin, that is the finding, not a defect.
4. **Wall geometry.** P(wall | side, t, distance-from-running-extreme at
   entry), the MDD mechanism B5 measured and never conditioned on.
5. **Joint wedge table.** For each simple (side-call, t) pair: usd per
   explore-asset-day, win rate, wall rate, MDD (entry-ordered per asset,
   `engine/entry_v2/replay.py` `_drawdown`), cells entered. Every line beside
   its two nulls: side-flip and time-jitter, with 2-SE day-spread separation
   required before a line is even called interesting.

Event-triggered rule sweeps (opposite-side quiet for Q, own-extreme bounce of
B dollars, minimum remaining time R, richness and forecast gates) come after
the frontier is read, in this same session, as numpy loops over the substrate.
They are not licensed to start a HOLD read.

## Sol reconciliation, 2026-08-27 (Fable ruling on the peer page)

`.audit/briefs/mill-second-opinion-sol-out.md` reviewed in full. Adopted,
binding on sweep 1 and later:

1. **The stable-hidden-side premise is a hypothesis, not a fact.** Replace
   the global winner label W(cell) with the time-indexed preferred side
   W_t(cell) = sign of pnl(+1,t) - pnl(-1,t), plus flip counts, ambiguity
   bands, and first-stable time. The stability map runs before any detector
   is judged.
2. **Walls are not exclusively a wrong-side fact.** S1's oracle-side turn
   line (MDD 5,430) and the frontier's winner-side p10 of -905 at fixed
   clocks prove correct-side-bad-time also walls. Side error, timing, walls,
   and abstention are four co-binding measurements. The matched contingency
   (call correctness x wall, same entry convention) and the error-injection
   stress replay replace the asserted "near-zero wrong-side tolerance" with
   a measured error budget.
3. **Entry legality.** Every mill entry requires a formed same-side CLEAR
   candidate at or before the entry minute, and one fixed entry convention
   across families (declaration-minute close, current quote, frozen cost).
   Availability is reported; the surface without this check is a labelled
   non-policy bound.
4. **Selection without cash.** Detector configurations are selected on
   error-budget compliance, coverage floor, then median delay, then
   simplicity - never on cash. Only the one selected configuration per
   family (plus sensitivity neighbors) is priced, and the family headline
   line runs through the full `engine.entry_v2.replay.replay` with
   occupancy, caps, and denominators, labelled partial-day where the split
   breaks portfolio days.
5. **Nulls.** Side-flip is a polarity control, not a null. Cash lines get
   fixed-seed asset-day block-permutation nulls with a max-statistic across
   whatever grid shared that null. Two standard errors applies after
   multiplicity, not before.
6. **Catalog changes.** F4 value-coverage bounds are measured before
   detector families and applied as one predeclared gate per family
   representative (no gate x detector cash cross-products). A no-change-point
   two-hypothesis / competing-risks sequential family joins the catalog as
   F7. CUSUM/SR dominance language softened to candidacy. Real post-wall
   re-entry deferred (F5 note above).
7. **Log discipline.** The hypothesis log gains immutable pre-result fields
   (spec/code/split/outcome-law hashes, null seed, registration time, parent
   trial, selection rule) and per-asset errors, walls, coverage, delay.
   Verdicts are KILL, SURVIVES_EXPLORE, or UNRESOLVED - never LIVE.
8. **Cache seam.** One quality plane per cell held on all 600 EXPLORE cells;
   the mill asserts single-plane per cell and fails loudly otherwise. The
   full prefix/evaluator interface split, plus priors and forecast sources
   with as-of checks, is round-2 builder work and F3/F4 wait on it.
9. **T_max framing dropped.** The binding target is cash per asset-day under
   coverage and full replay, never a standalone per-trade crossing.

Rejected: serializing Sol's four curves as a separate unit before any
detector work (they are cheap array passes on the existing surface and run
inside sweep 1's measurement stage, preserving Sol's ordering intent without
a second dispatch). Everything else stands as written above.

## Sweep 1 ruling (Fable, 2026-08-27)

Receipts in `.audit/mill-sweep1.json` and the log (rows sweep1-001..090).
Three corrections and one prize came out of it, binding on sweep 2:

1. **The enter-now side label was the wrong stability object.** Delta(t) =
   cert(+1,t) - cert(-1,t) decays to noise mechanically as t approaches the
   phase close, so "first stable" lands at 92-94% of the phase and the
   oracle line there is crumbs ($169/$171/$205 a day at 100% win). The side
   object a detector needs is the REMAINING-BEST difference Delta*(t) =
   max over tau>=t of cert(+1,tau) minus the same for -1: which side's
   remaining opportunity dominates from now on. The M4 error budget (b=0)
   inherited the same artifact by running on the crumbs line; both rerun on
   Delta* lines in sweep 2.
2. **The prize table exists and is now quantified.** Time-indexed oracle
   side at fixed tau=1800 s with ambiguity and legality abstention
   (coverage 46-58%): SI 1664.6 usd/day (clears its 1500 rung, MDD 385),
   NKD 978.5 (65% of rung), HG 1039.0 (52% of rung), win 88-98%, walls
   0-2.2%. Labelled oracle, not a policy. The gap decomposes into two
   separable subproblems: (A) the side at moderate times on unambiguous
   cells, and (B) entry timing inside the known side, worth roughly 2x per
   trade (fixed-tau entries capture ~half of best-entry value; the
   extreme-distance wall gradient says where the other half lives).
3. **All 78 zero-fit detector configs are coins against the enter-now label**
   (primary error 0.43-0.51), and the 12 priced lines lose money with 17-37%
   wall rates and 6k-26k MDD: verdict KILL as entry policies. Stage-A rows
   stay UNRESOLVED pending one relabel against sign(Delta*) - a no-cash
   array pass - after which they are either revived as side evidence for the
   fitted caller or killed for good.
4. **Adversarial error tolerance is ~2%** read off the M4 grid shape at the
   near-rung lines (2% adversarial flips push MDD to 828-964; 5% breaches).
   "Near zero wrong-side tolerance" is now a measured number, per Sol's
   demand.

## Sweep 2 + ceiling ruling, and the design synthesis (Fable, 2026-08-27)

Receipts: `.audit/mill-sweep2.json`, `.audit/mill-rem-ceiling.json`, log rows
sweep2-001..039 (all KILL), Sol design page
`.audit/briefs/mill-design-sol-out.md`, Fable design page registered first.

1. **The family ceiling clears every rung.** Oracle Delta*-side plus oracle
   terminal entry (REM, LEGAL variant, tau=1800): HG 2692 / NKD 3600 /
   SI 4230 usd per asset-day at 88-92% coverage, mean 982/1360/1547 per
   trade, stable across tau 900-3600. The money exists inside the frozen
   generator and exit law with 35-182% margin over the rungs.
2. **The naive event entry is the proven defect.** With the same oracle
   side, first-adverse-extreme entries post only 745/449/870 with 12-29%
   walls: mid-run extremes eat the value. Entry depth, not side knowledge,
   is the dominant gap (worth 3-6x the side component). Sweep 1's M2 line
   was a tautological trade-selection envelope, not a side oracle; the
   honest side-only oracle at fixed clocks misses every rung.
3. **Sol's own branch resolves against its fitted policy.** Its
   pre-registered bar (EVENT oracle >= 2500/1875/1875, MDD < 800) fails on
   every asset, so its remaining-opportunity caller is not priced; its
   stated route is the level/forecast depth family - the same family
   Fable's synthesis reached independently. Its C-1 stability condition
   also fails (agreement at 1800 s is 0.58-0.67 < 0.75), moving decisions
   to event bars, not dense clocks. N4 qualifies no detector for head
   inclusion (HG's candidate-race 0.374 is single-asset).
4. **Sweep 3 = DEEP-FADE, zero-fit.** Per cell: fade the first new
   bar-mid extreme that lands in a causal terminal depth zone - anchored
   to the prior locked day's session low/high (margin in ATR14_prev units)
   or to depth-from-phase-open in ATR14_prev units - at or after tau0,
   with optional small rebound confirmation, minimum 1800 s remaining,
   formed same-side candidate legality, frozen exits, one entry per cell.
   No side model, no fitting. Oracle attribution first (terminal-extreme
   in-zone fractions, conditional cash, REM capture), then no-cash config
   selection (entry-time error vs Delta*, coverage, delay), then at most
   two priced configs per asset with the full replay, 2% adversarial
   stress, and block-permutation nulls. Context from
   `artifacts/cache/mill_context/` through the strictly-prior loader.
   Acceptance, pre-registered: every asset at or above its rung, both MDD
   orderings under 1000, wall rate <= 2%, stress MDD under 1000, adjusted
   null p <= 0.05. Misses route to forecast-range normalization (T54
   audit), then composition with a late-persistence side component, then
   completed cross-phase state (Sol D-3) - never to "unreachable".

## Sweep 3 ruling and the first cadence review (Fable, 2026-08-27, overnight)

Receipts: `.audit/mill-sweep3.json`, log rows sweep3-001..052, all KILL.

The oracle ladder now prices every layer. REM ceiling 2692/3600/4230.
Terminal-fade at bar grain 1844/2209/2475 (window variant 1957/2408/2668):
NKD and SI clear, HG misses even with perfect terminal knowledge.
Last-in-zone oracle 971/793/1609. Best causal line 163. Terminal extremes
are shallow (median 0.18-0.22 ATR from open) and mid-phase (median ~3 h);
prior-day-level zones hold 51-59% of them, depth-from-open zones almost
none; a triggering cell carries 7-15 in-zone extremes and the first is the
terminal one ~5% of the time. Walls vanish at true terminal entries (O2
wall 0.000), so terminal-hit rate controls both cash and MDD.

Cadence review findings, binding on sweep 4:

1. **Drift caught: the mill left the deployable object.** The real system
   enters CLEAR candidates at their own decision moments; S0's identity
   entered the best-priced name at its own snapshot and posted 2753/3806/
   3869 era-wide. The bar-mid abstraction caps the same idea at 1844 on HG
   (0.685 REM capture); the missing slice is entry grain. Sweep 4
   reconciles with an S0-replica oracle on EXPLORE (best winner-side
   candidate at its own decision_ts) and moves every entry law to
   candidate-anchored form, which is also the only deployable form.
2. **Slow terminal detection is untested, not killed.** Sweep 2's
   delay-minimizing selection picked the fastest (worst) quiet configs;
   its stage-A metric scored side, not terminality. The right metric is
   terminal-hit rate: an entry counts iff no new adverse extreme prints
   between entry and phase close. The missing oracle is delay tolerance:
   cash of entering d minutes after the terminal extreme, d up to 60.
3. **HG needs more than this family alone** even at oracle grade: routes,
   in order, candidate-grain entries (S0 says HG's candidate-form ceiling
   is 2753), coverage via the window variant, per-phase parameters (USER
   session directive), then composition with the late-persistence trend
   component the frontier measured at 0.57-0.66 accuracy after 90 min.
4. **Process lesson encoded**: the stage-A selection metric IS the design;
   it must measure the thing the family needs (terminality, not side).

## Context sources license (Fable, 2026-08-27, F3/F4 unblock)

Three causal context sources are licensed for the mill, cached under
`artifacts/cache/mill_context/` by `tools/mill/build_context.py`:

1. **Priors store** `g1/priors/{asset}.tsv` (QRE2G1PRIOR2): per-day prior
   ATR14 and per-phase spread/ceiling stats. Derived day-level summaries,
   not outcomes; readable for all locked days.
2. **Forward-vol forecasts** `artifacts/runs/e6_vol_forecasts_v2/
   vol_service_forecasts.tsv`, joined with the killed read's own routing
   (`load_window_forecast_rows`, `route_catboost_daily`,
   `select_expanding_median`, exactly as `.audit/
   score_threshold_2022_2024_ceiling.py` lines 89 and 386-392): per-day
   daily and intraday heads plus the expanding-median regime flag. Already
   the gating law's source; day-level; walk-forward by construction.
3. **Daily session levels**: a one-time summary extraction over the locked
   582 asset-days (HOLD included) producing ONLY day-level rows per (asset,
   d8): session open, high, low, close, range, and per-phase closes, from
   trusted mids. A day-level OHLC is not a cell outcome; it becomes feature
   context only for LATER days. Constraints, binding: the extractor writes
   nothing finer than day-level rows; output sha-pinned in a manifest; the
   loader API refuses to serve context rows with day >= the requesting day
   (strictly-prior guard) and carries a mutant proving the guard; HOLD cell
   outcomes, candidates, and intraday paths stay unread by every rule.

Rationale: rules for day D may use any information from days strictly before
D. The survivor's one HOLD read uses the same strictly-prior law, so no
selection-on-HOLD-outcome channel opens.

## Standing cadence: the step-back review (USER, 2026-08-27, overnight)

After every second completed sweep, before dispatching the next, the parent
runs one explicit big-picture review and logs it as a REVIEW ledger note:
re-read the decomposition and the ceiling numbers, ask whether the current
family is still the highest-value attack or a tunnel, check the killed-row
patterns for a misread signal (the month-long side-vs-entry misread is the
cautionary case), and consult Sol when the answer is not obvious. Tunneling
on one family past its evidence is the failure mode this cadence exists to
catch.

Overnight sequencing rule: EXPLORE iteration runs unattended. USER
2026-08-27: the parent decides the HOLD read itself, no user sign-off
needed. The one-read law is unchanged - a rule is frozen in writing with a
pre-stated dollar stop before its single read, and the read is never
amended after. The parent's own bar for spending a read: every rung
cleared on EXPLORE with both drawdown orderings under 1000, the 2%
adversarial stress held, and the adjusted permutation null at or under
0.05. A marginal rule does not spend a read.

## Forbidden inside the mill

Opening HOLD-day packs. Opening `g1/teacher` or `g1/late`. Any 2021 or 2025
byte. Any engine file edit. Any claim of promotion, LIVE, or rung clearance
from EXPLORE numbers. Stored-teacher cash as a ranking target. Amending B0-B5
receipts. Starting E1, V0 Stage 1, or any HOLD confirmation from this page.

## Seats

Design and judgment: Fable in the main session (this page). Implementation:
Opus 5 subagents, medium effort, per USER 2026-08-27; subagents do not write
MEMORY.md and do not touch briefs. The parent reviews every diff, runs the
checks, and owns the frontier read.

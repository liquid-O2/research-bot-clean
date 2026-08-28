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

Pre-registered sweep-4 kill criteria (USER challenge, 2026-08-27: "we
cannot capture the extreme; entries come at its confirmation; prove this
is not a circle"). Sweep 4's policies never enter at an extreme. Every
entry is the first fade-side candidate AFTER a confirmation (Q quiet
minutes plus a retrace held H ATR for k bars). The extreme-entry lines
(O2, O4a, O4b at d=0) are bounds that price what confirmation can at best
capture, never policies. The confirmation family is judged by two tables
before any cash matters:

- DEAD if O4b (oracle side, entry d minutes after the terminal extreme)
  already misses the NKD and SI rungs at every d >= 10 minutes - the
  delay budget confirmation needs does not exist; or if O4c shows the
  false-positive floor never drops: P(quiet >= Q | non-terminal extreme)
  above ~0.25 at every Q up to 60 minutes, zones included - waiting
  cannot separate the last extreme from pauses, the S1 anti-selection in
  new clothes.
- LIVE to price if some region has O4b at or above the NKD/SI rungs with
  P(false positive) at or below ~0.15 and stage-A coverage >= 0.30.
- HG runs on the composition track regardless (its terminal-fade oracle
  already misses); Sol's HG proposal is in flight.

What distinguishes this from S1's turn rule and sweep 2's XR, on the
record: S1 confirmed per-name at age 180 with a fixed cap and no
terminality object; sweep 2's selection minimized delay and so priced
only the least-confirming configs (Q=5 min) - the slow-confirmation
region was never priced. If O4b/O4c kill it now, the confirmation family
is closed with a receipt instead of a suspicion, and the routes are
retrace-structure confirmation (H/k without quiet), the late-persistence
component, and composition.

## Sweep 4 ruling (Fable, 2026-08-27, overnight)

Receipts: `.audit/mill-sweep4.json`, log rows sweep4-001..081, all KILL as
side-blind policies. The oracle tables pass the family through the frozen
branches for NKD and SI:

1. **Candidate grain confirmed.** The S0-replica oracle at candidate
   anchoring posts 2182/3095/3514 usd/day (win 1.000, wall 0.000, MDD 0,
   coverage 0.73-0.77) - every rung clears at this grain, HG included.
   Every future entry law stays candidate-anchored.
2. **The delay budget is real.** With side and extreme known, entering d
   minutes after the terminal extreme clears the NKD rung through d=45 and
   the SI rung through d=60; HG misses at every d (composition track,
   USER-deferred). Buffered bars hold to ~d=20 (NKD) and ~d=45 (SI).
3. **Terminality separates.** False-positive rate on non-terminal extremes
   falls 0.19 -> 0.05 across Q=10..60 while terminal recall stays
   0.74-0.96; at Q=30 the pair is FP 0.085-0.096 / recall 0.83-0.89. The
   zone gate adds nothing (<=0.004) and is deleted. Phase 1 (London) is
   near-solved by quiet alone (hit 0.96-0.97); phase 2 carries the losses.
4. **The side is the one missing ingredient.** Side-blind first-quiet
   fades achieve terminal-hit 0.75-0.82 while side_hit runs 0.36-0.57,
   and the priced lines lose (-158..+38 usd/day, walls 15-37%). Sol's
   predicted failure mode, confirmed exactly. The route is the composition:
   an arbiter decides WHICH extreme's quiet counts; quiet Q per the
   branch table (NKD <= 20 min, SI <= 45), per-phase Q by the pooled FP
   rule, joint-hit selection at the raised floors.

## Discretionary integration (Fable, 2026-08-27, overnight)

USER delivered the discretionary order-flow library
(`research/discretionary/`, 34 PDFs). Prior work already audited 31 of
them page by page and distilled the grammar into
`design/ENTRY_V2_DISCRETIONARY_FEATURE_CROSSWALK.md` (1,352 disc_*
columns, v8). That attempt lost on CatBoost because it exposed atomic
features at early per-name snapshots and asked trees for the
interactions - decision points where the side does not exist yet (the S1
lesson) and a model family the house already measured losing to unit
weights. Reuse, not re-read: the crosswalk is the distillation of the 31;
only `a-clean-continuation-short`, `amt-on-live-markets`, and
`reading-the-volume-profile` are new and get a diagram-inclusive read.

The new use is different in kind: ~12 minute-scale, level-anchored flow
signatures (signed aggressor delta, attack volume into the extreme,
adverse yield per attack = absorption, reload-after-trade proxy, retest
quality, opposite-side lift after quiet), computed from the packs' MBP-1
fields only in the windows around detected extremes, serving as (a) the
composition's side arbiter ("who is in control") and (b) confirmation
quality with abstention. Fit tier: unit-weight composites first (Dawes
beat trees in this house), walk-forward only if needed. The struck
sub-second flow families stay struck; these are minutes-scale
effort-versus-result readings at levels, inside the timescale doctrine.
USER 2026-08-27: iceberg/refill proxies are weak intention reads in
modern markets - the reload columns stay cached but never carry a primary
role; the intention verdict leans on absorption, delta divergence,
trapped-trader flushes, and two-sided fights resolving.

Game-theoretic framing (USER 2026-08-27): intent inference targets algos,
not humans. The frame re-derives the chosen signatures - absorption is
the market-maker inventory game's scoreboard, the flush-and-reclaim at an
obvious level is the stop-hunt game's footprint (and why terminal
extremes cluster at prior-day levels), persistent one-sided delta is a
parent order being worked - and adds one new arbiter candidate: the
schedule-persistence score, regularity/autocorrelation of signed
per-minute delta over 10-30 minute windows, the signature of an execution
scheduler slicing a large order on one side. Computable from the flow
cache; joins the arbiter grid in the next sweep.

USER 2026-08-27 on the persistence-join fallback: prior against
pullback-waiting - after a real rejection price often just goes, and
waiting misses those cells - but the data decides. The family keeps its
catalog slot behind a mandatory first gate: measure, oracle-grade and
cash-free, how often a pullback of usable size occurs after
side-establishment and what fraction of remaining cell value survives
waiting for one. If the goers dominate, the family self-kills at the
gate; an immediate-join variant (enter the next same-side candidate
without waiting for a pullback) is measured beside it.

## Library audit findings, flow half (Fable ruling, 2026-08-27 overnight)

`research/discretionary/CROSSWALK_AUDIT_FLOW_2026-08-27.md` (12 PDFs, full
text, verified citations). Three findings are load-bearing and binding:

1. **Quiet selects the wrong class.** dom-lesson-6 p7: big volume with no
   movement is absorption (someone is there; reverses harder); shrinking
   volume with no movement is exhaustion (nobody left; drifts). A
   quiet-for-Q-minutes detector selects the exhaustion/drift branch by
   construction - the mechanism behind sweep 4's side coin and weak cash.
   your-mistakes-with-absorption p9 agrees: absorption requires POSITIVE
   opposite aggression, never mere absence of the first side. The detector
   family therefore splits into two classes: LOUD rejection (attack-volume
   percentile high, yield near zero, opposite-side delta appearing within
   k bars - the primary trigger, readable from the flow cache) and QUIET
   exhaustion (the current Q detector - fallback class with drift-sized
   expectations). Sweep 5a's in-flight quiet baseline becomes the class-b
   control.
2. **Flow alone is near-coin; location and memory carry.** refill-effect
   p9/p23 already ran our experiment: raw order-flow features alone grade
   AUC 0.54 while memory and location features do nearly all the work.
   Binding priority for the arbiter composite: level memory first (extreme
   at/near prior-day levels, repeated-test-and-held counts), flow
   signatures as confirmation with the absorption-vs-exhaustion polarity,
   never flow alone. This corroborates the USER's struck-OFI intuition and
   explains the 1,352-column CatBoost loss a second way.
1b. **Absorption is a zone-episode object, not a bar-at-the-extreme read**
   (USER 2026-08-27). Absorption builds over long stretches, near rather
   than at the extreme, often across multiple peaks/touches, and the
   confirmation that one absorption was real frequently arrives after
   price has already pulled away from the zone. Binding consequences: the
   level window widens from 3 ticks to ATR-scaled zones; absorption
   statistics accumulate per EPISODE (consecutive and recurring proximity
   to the extreme zone) with touch counts, cumulative attack vs cumulative
   yield across touches, and per-touch response quality; the entry
   confirmation reads the zone HOLDING on a later test plus the move away,
   not a single loud bar. The 18-tick median dip and multi-peak structure
   are the same geometry seen from the source's side.

3. **Source numbers are hypotheses about FORM, never constants** (USER
   2026-08-27: the three-tick reward is an NQ number from another era; do
   not take it at face value). What the sources contribute is the SHAPE of
   each rule - a confirmation reward exists, defence happens inside the
   zone so winners dip past the touch, vetoes that are too tight discard
   the median winner. The NUMBERS come from our own bytes: measure the
   dip-past-touch distribution and the reward-that-confirms threshold per
   asset, per phase, per regime and era on EXPLORE, in self-scaling units
   (ATR, spread, session-so-far percentiles), walk-forward where fitted,
   auto-adaptive by construction. No absolute tick or dollar constant
   imported from any PDF survives into a config. Also adopted: the POC flip (fp-lesson-9 p5) as a missing
   control-transfer detector - needs a running volume-at-price POC series,
   a small flow-cache extension; and the execution-geometry fact (order
   type alone flips profit factor 1.80 to 0.81) which our frozen fill law
   cannot change but entry selection can respect by preferring candidates
   whose decision quote sits at the level rather than chasing.

## Library audit findings, structure half (Fable ruling, 2026-08-27)

`research/discretionary/CROSSWALK_AUDIT_STRUCTURE_2026-08-27.md` (19 PDFs,
262 pages, complete). Rulings:

1. **Regime inverts the meaning of quiet.** In balance regimes (~80% of
   sessions per the source) both extremes absorb most of the time, the
   fade works as failure-of-aggression, and one's own side need not be
   rewarded; in trending/short-gamma regimes the same quiet is a trap.
   The frozen decisive test does NOT change (the score stays frozen);
   the receipt adds a balance-vs-trend regime cut (realized range vs
   forecast, value migration) as a reported dimension, and two new
   DIAGNOSTIC columns join the table: CVD-dies-at-level (level holds
   while cumulative delta decays across the consolidation - the source's
   "being tested and passed" break precursor) and shrinkage-pacing
   (steady size and pacing = wall; monotone shrinkage with stretching
   intervals = about to give). If the frozen score misses and these
   diagnostics separate, they are the named inputs of the one fallback
   iteration, never a third composite.
2. **The strongest external validation of the house protocol.**
   origin-of-the-move p18: the author's own mechanical entry, rebuilt
   causally with hindsight stripped, scored -0.16R to -0.54R
   out-of-sample - the profitable-looking version had leaked later-in-day
   information into setup selection. The same failure class as B2's READY
   leak, measured independently in the source library. What survived
   there was a grading system plus an execution rule - the shape this
   program is already building.
3. **Abstention and re-entry material queues post-milestone**: the layered
   refusal system (regime stand-asides, level-void conditions, no-trade
   zones) and location-bounded re-entry (back to the level, not near it;
   escalating conviction) are hillclimb-phase levers, carried with the
   source's own two-sided warning that stricter filters can cost more in
   frequency than they buy in accuracy.

## Sweep 8 frozen pre-7b: the survival-gated fade (Fable, 2026-08-27)

Frozen BEFORE sweep 7b's bleed numbers exist, so 7b picks between branches
and never shapes the model. Zero-fit round; no weights, no supervised fit.

Gate, per (cell, side), at completed bars with extreme age >= 5 min: five
evidence components, each a walk-forward stratum percentile (asset,
phase; strictly-prior-day calibration), oriented larger = safer: E1
quiet-age percentile within the stratum's interarrival distribution; E2
tape-die-off (inverse percentile of last-10-min quote events + volume vs
the side's episode history); E3 one-sidedness of the last touch print
(banked, one-shot); E4 interarrival stretch (current gap / side's median
gap so far); E5 opposite-side extreme recency. G = mean(E1..E5); fire
when G >= the stratum 60th percentile (frozen, not swept) AND remaining
time >= 1800 s AND the side's extreme age is inside the asset's cash
window (45 min NKD, 60 min SI and HG). Both sides monitored; first fire
wins; an opposite new extreme cancels a pending entry and re-arms.

Entry variants, pre-registered: A = first fade-side CLEAR candidate after
the fire; B = same but only candidates whose decision quote sits inside
the zone (within 0.15 ATR of the extreme; abstain if none within 15 min).
Variant C (conditional, opened only if 7b's flipped-fade line is
cash-positive on either deciding asset): the same gate applied to the
flipped join side. Primary no-cash metric: post-entry extension rate;
then soft-hit, coverage, delay-from-terminal median and p90, per phase;
side agreement diagnostic only. Controls: sweep-7a's first-quiet line and
a random-timing draw. Selection: variant per asset by lowest post-entry
extension at coverage >= 0.35, then price that one line per asset (cash,
walls, MDD both orderings, replay, 2% stress, block null).

Keep-to-price bar: postX <= 0.25 at coverage >= 0.35. Freeze-candidate
bar: the standing HOLD bar (rungs, MDD < 1000 both orderings, stress,
adjusted null <= 0.05) on NKD and SI. Kill routes to the matched-twins
certificate and the regime-scoped variant. 7b's lawful influence is
exactly: branch priority (late-dominated losses tighten the lateness law;
hard-wrong-dominated opens variant C) - nothing else.

## The magnitude turn: USER exit ruling, sweep 15, sweep 16, the fixhold Sol pass (Fable, 2026-08-28 early)

USER rulings, mid-turn 2026-08-28, verbatim intent. Fixed-duration exits are
authorized as a learning label whose purpose is proper ENTRY learning ("the
fixed exits are there to make the model learn to take entries, not to take
exits"). Final exits stay tunable later toward the end goal, ATR-based named
by the USER. Full autonomy, no go-ahead waits. If noise is the main issue,
find ways to fix the noise issue. The frozen wall-or-close law remains the
promotion-era outcome law until a specific replacement is ruled in; the
authorization covers learning labels and later exit engineering.

Sweep 15 landed (F12-NOISECEIL, rows sweep15-001..017, receipt
`.audit/mill-sweep15.json`, both reproduction gates exact, selftest 16/16,
mutant red). Parent judgment on its three facts:

1. The order-statistic premium hypothesis is DEAD in reverse. The real
   per-cell-max oracle sits BELOW the p5 of cross-cell within-stratum
   shuffles on every asset at both grains (percentile 0.0 of 200 draws; fine
   excess -1555/-3300/-3666, coarse -436/-651/-472 usd/day). Big outcomes
   cluster inside the same cells; scattering identical pooled outcomes across
   cells RAISES the per-cell-max sum. The pre-registered table did not
   enumerate below-p5, so PARTIAL fired by elimination; the parent records
   the gap and judges all 17 rows KILL (the family's registered claim, that
   an order-statistic premium explains the oracle, is dead; the excess column
   is not a feasibility budget in either direction).
2. The decisive finding of the night. The 16-feature state predicts SIZE,
   not DIRECTION. |Y| out-of-fold R2 +0.119/+0.127/+0.096 on HG/NKD/SI, the
   first genuinely predictable out-of-fold quantity in 467 rows. Signed Y and
   sign(Y) are negative out-of-fold on all three. E[Y] per occurrence is
   negative everywhere. This explains every side-calling kill in one line:
   the plane knows when the market will move big, never which way.
3. The coarse post-reset grain (9.0-9.6 occurrences per cell against
   110-136) keeps 93.7/92.1/93.9 percent of the ceiling. Any future fitting
   starts on the coarse grain; the 14x pool cut is nearly free.

Successor route registered (pending the Sol page, no unit dispatched for it
yet): entries selected by predicted move size, direction made irrelevant by
exit asymmetry, a stop well below the predicted favorable excursion with a
horizon exit otherwise, stop scale auto-adaptive per asset and regime (the
USER's ATR shape). Entries remain the learned object. The measuring unit
would be favorable and adverse excursion curves at horizons on
magnitude-selected states under the frozen entry cost law. Failure modes to
price before belief: gap through the stop, spread at stop scale, chop where
both sides stop out, capacity, regime dependence of the magnitude signal.

USER objection and directed test (2026-08-28, after the sweep-15 report). The
USER rejects the "direction" framing: at an extreme the trade side is given
by the extreme; the open question is whether the extreme holds or breaks;
the USER hypothesis is size first (a big move is coming), then absorption
evidence resolves hold versus break. Adopted as the correct reading:
sign(Y) on the fade stream IS hold-versus-break, and sweep 15's
unconditional sign fit could hide a signal that lives only on
predicted-big-move states (a tenth of rows). Sweep 17 (F14-CONDSIGN)
dispatched: out-of-fold magnitude score m under the sweep-14 walk-forward
law with train-only thresholds; hold/break base rates per m-decile; sign
fits restricted to top-m subsets; absorption flow/zone features interacted
inside the high-m slice (USER-directed exploratory reopening of flow INPUTS
for this composition only, the flow composite as a policy stays closed);
the antifade branch priced with continue-side certs computed via the frozen
law with the flipped side, never by negation, since the -900 wall follows
the held position. Letters CONDSIGN / ANTIFADE / NONE, block-permutation
max-stat nulls. Judged only after Sol's fixhold page reconciles.

Second USER correction (2026-08-28, after sweep 17 dispatch): the library
already specifies the composition, and my sweep-17 mapping got the "size"
object wrong. The library's size is OBSERVED incoming effort being absorbed
(effort in, wall inside the zone, no reward, opposite aggression, pull-away,
retest, repetition raising hold odds; DIAGRAM_NOTES_FLOW consolidated
section), not a FORECAST of future move size. Sweep 17 stands as the
forecast-conditioned variant. Sweep 18 (F15-EPISODE) dispatched as the
library-literal test: the six-gate ordered ladder G1 location veto, G2
effort in, G3 no reward, G4 absorption-versus-exhaustion fork carried as
separate branches, G5 repeat (the sweep-13 causal gate), G6 opposite
aggression; cumulative rung table with cash, Wilson hold rates, and usd/day;
controls are matched-coverage random draws, the sweep-13 lateness match,
a scrambled-gate order control, and block-permutation max-stat nulls;
letters GRAMMAR-LIVE / PARTIAL-GATE / NONE / UNPOWERED. All thresholds
train-day adaptive per asset and phase-type; the PDF tick constants are
shapes to re-measure, and post-effort adverse excursion is a constituent,
never a veto, per the refill p10 law. Scope: individual pre-registered
gates in fixed order, no fitted weights, one shot, inside the sweep-6
closure's own carve-out; the flow composite and R4mem stay closed. A
reader agent is also closing the recorded diagram gap (refill-effect
pages 5-21 odd ones out, trapped-buyers 4 and 10) with an addendum to the
notes file. Sweep 13's ordinal-2 survivor is recognized as the library's
repeat-and-retest gate measured alone; the grammar test asks whether the
full ordered conjunction beats it.

Third USER reframe (2026-08-28): the continuation frame. USER: do not
predict the reversal at all; after the extreme forms and the reversal
displaces away, catch the trend continuation. The library paper
a-clean-continuation-short prescribes exactly this (remainder notes lines
850-980): the initiative displacement ARMS the level and never triggers;
the trigger is the return where the same side wins again; the stop sits at
the opposing side's absorption point; a fast lane waives the retest when
displacement is fast and the counter-attack is absorbed immediately; trend
days are continuation-only per the day-type table; the volume-profile
author trades continuations over reversals for win rate. Why the frame is
materially new against the kill record: every dead family entered at the
extreme and had to FORECAST hold-versus-break, the one bit the features
cannot see; the continuation entry waits until one hold has been OBSERVED
(displacement plus retest-hold), so the forecast becomes an observation;
the lateness it spends is already priced affordable (O4b 45/60-minute
budgets, B0 waiting receipts); what it collects is the verified
session-scale size signal; and the B5 momentum KILL does not cover it
(B5 was clock-sampled mid-run, unconditioned). Sweep 19 (F16-CONT)
dispatched: slow and fast lanes per the paper, day-type and size variants,
controls C1 lateness-matched draws, C2 fade-at-occurrence head-to-head on
the same cells, C3 fixed-clock momentum (the B5 control brought forward),
C4 max-stat permutation nulls; letters CONT-LIVE / CONT-PARTIAL / NONE /
UNPOWERED; all thresholds train-adaptive, no constants. Known risks
recorded for the judgment: later entry surrenders part of the run; a held
retest can break after entry; chop whipsaw (day-type gate is the library's
answer); and the unpredictability may reappear one level up at the retest,
which is precisely what the unit measures. Sol review queued as the
follow-up consult when the fixhold page lands (parallel-dispatch pattern,
reconciled before judgment).

The diagram gap is CLOSED (gap addendum appended to
DIAGRAM_NOTES_FLOW_2026-08-27.md, both flow decks now read end to end).
New facts carried into design: the refill paper has FOUR feature families
(memory, construction, location, flow-and-state) with memory and location
dominant and flow alone at AUC 0.54, matching our flow kills; the refill
strategy is a THIRD lane, pre-touch selection with a resting limit and a
30-minute cancel, not post-touch confirmation; the PF 1.80 / 68.8 percent
triple previously quoted is Q1 only, the full year is 223 trades, 58.7
percent, PF 1.45, about +0.07R per trade; worst out-of-sample drawdown
-16.6R; entry depth sits on a plateau, not a tuned constant. Nothing
overturns the consolidated mechanism. The level-memory and location input
plane (per-price defence history across phases and days, value-area
position) is named as the missing family the mill has never been given and
stands as the next unit after the in-flight three, pending the Sol pass.

Sweep 26 LANDED, THE GRAIN LEVER IS DEAD, THE TREE IS COMPLETE (Fable,
2026-08-28 dawn). Receipt `.audit/mill-sweep26.json`, 54 rows stamped
KILL, selftest 31/31, both mutants red by named roster, both parent
universes reproduced under refuse-on-mismatch, 4.46 million raw trades
read, 11,636 executable entries with zero causality violations. FAMILY
LETTER ORDER-POOR under BOTH dedupe readings (the builder registered a
primary overlap-dedupe and the literal key as a sensitivity because the
literal key deletes 12,351 of the approaches it was ordered to
reproduce; both agree). The findings: no within-minute order class
reaches half a deciding rung (best P4 on SI 0.357x with NKD -0.246x;
best joint class P1 at 0.062x/0.181x), every binding MDD 7.5x to 222x
over the bound, the classes POWERED at 157-1918 entries per decider.
Every minute twin's upper bound is positive (250-581 usd/day) and
several twins beat their tick parents outright. Minute collapse is real
but small, 1.9 percent overall, concentrated in the break atoms (P5
17.4, P3 5.6 percent), and the orders it hides are not worth money at
either grain. BOTH halves of Sol's grain evidence bar fail
independently. The grain lever is closed with a receipt; the grain law
stands and no case exists to ask the USER to change it. With this,
every branch of the pinpoint tree has a valid zone-anchored receipt:
F19 K3, F20 K3 all three lanes, F21 ORDER-POOR. The night ends with no
survivor, the collision mechanism unfalsified (cash-dead selectors,
controls unpowered, discrimination never non-positive), the two real
signals standing (session-scale size; timing as filter, with the SI
break-close near-miss at maxT p 0.0545 the closest causal line), and
the formation-to-selection gap as the named object of the next session
(ceilings 9x-55x, causal reach at most 0.36x). The final Sol consult is
dispatched (`.audit/briefs/mill-powerplan-sol.md`, out at
mill-powerplan-sol-out.md): the power arithmetic, the SI near-miss
unit, the ranked untested decision-information sources at one-minute
grain (the zone-anchored level-memory plane first among candidates),
and the next-session charter with revised priors. Nothing further
dispatches tonight; that page opens the next session. HOLD, 2025H2, and
the 2021 kill-only license remain sealed and unspent.

Sweep 25 LANDED, THE VALID STRUCTBREAK KILL, F21 DISPATCHED (Fable,
2026-08-28). Receipt `.audit/mill-sweep25.json`, 51 rows stamped KILL,
selftest 77/77, both mutants red by NAMED roster (a contract upgrade the
builder registered: a mutant must red its exact checks, not anything),
3,790 zone-anchored reads centre-exact on the former defending side at
the pre-breach snapshot, zero defaults, zero fallbacks. FAMILY LETTER
STRUCTBREAK-KILL clause K3 on all THREE lanes, including the USER's
promoted BREAK_CLOSE, so the kill cannot be blamed on a pullback-only
test. Best lane NKD -0.060x and SI -0.028x of rung; formed ceiling
14.27x and 15.85x. Carrying facts: (1) SI's break-close matched delta
is +726.6 usd/date at maxT p 0.0545, the closest any causal line came
to the family bar all night, on the USER's timing; NKD runs the other
way (p 0.996). (2) Lane A's SELECTED ceiling alone carries both rungs
(2.11x, 1.39x) while its causal line does not: the failure is selection
and seating, not formation, stated in the receipt. (3) Lane C proves
sweep 23's marginal arming was a genuine estimator fault (fill 0.069 to
0.397, a 5.7x gap) without the repair changing any letter. (4) The
builder disclosed honestly that the centre mutant does not flip the
planted RANKING on its fixture (a wrong key can look plausible), which
is exactly why the gate is mechanical centre equality per row. Both
zone-anchored families are now validly dead under registered clauses;
the falsifier remains unfired (all upper bounds positive, unpowered).
Per the tree, sweep 26 (F21-SUBMINUTE-ORDER-ORACLE) is dispatched: the
outcome-only raw-tick oracle over both formed universes, five
preregistered within-minute pattern classes (absorb-then-reject,
reject-without-absorb, absorb-then-breach, multi-cycle,
breach-then-return), EXECUTABLE next-bar entries so the sub-minute
information is only the condition, each class priced beside its
MINUTE-COARSENED TWIN with the collapse rate measured, letters
ORDER-RICH / ORDER-PRESENT / ORDER-POOR / UNPOWERED. ORDER-RICH is the
one receipt that meets Sol's grain evidence bar in full; ORDER-POOR
kills the grain lever and the next session stays at one-minute
formation and power. No law changes from this unit either way.

Sweep 24 LANDED, THE VALID COLLISION KILL (Fable, 2026-08-28). Receipt
`.audit/mill-sweep24.json`, 39 rows stamped KILL, selftest 44/44, both
registered mutants red, 16,525 of 16,525 barrier reads centre-exact at
the candidate zone, formation identical to sweep 22 (14,650). FAMILY
LETTER LEVELCOLLISION-KILL, clause K3 CEILING-UNREACHED, one clause
matching, both lanes. Best lane L2_EPISODE at NKD 0.036x and SI 0.078x
of rung, formed ceiling 46.8x and 55.0x beside it, MDD 10,482 and 4,141
against the 1,000 bound, controls unpowered. The corrected barrier
score is substantially a DIFFERENT score (rank rho 0.34-0.53
standardized, selection flips on 13-23 percent of shared candidates)
and it still cannot reach the formed cash, so the collision mechanism
is now validly tested at this selector and these bounds and validly
killed there; the falsifier remains unfired (no powered non-positive
upper bound). Builder disclosures recorded: a mid-unit NaN-fallback
defect found and fixed with the fallback registered (sweep 22's
approach-bar fallback carried component-for-component, refusal if it
covers anything but the no-close set); the first run's 39 unreproducible
log rows removed before re-append; sweep 22's pd_broke_close
zero-default quirk on unresolved candidates reproduced for attribution
and flagged to F20. Unit 3 branch taken per the tree: sweep 25
(F20-STRUCTBREAK-ZONEANCHOR) dispatched with THREE registered lanes,
Sol's promoted BREAK_CLOSE, Sol's marginal-law PULLBACK, and a
parent-registered PULLBACK-JOINT variant whose depth and cancel train
as one two-dimensional quantile (grounds: sweep 23 measured the
marginals do not compose, fill 0.069; deviation flagged for Sol's next
pass), fixed-zone B_opp on the trapped side snapshot before the breach,
I_break at the last causal occurrence, high-and-high selector, the
proven exhaustive partition, family maxT over 6 lines. On a valid F20
KILL the tree routes to F21-SUBMINUTE-ORDER-ORACLE, outcome-only,
lawful under the grain law.

SOL REFUSAL ADOPTED, THE ZONE-ANCHOR CORRECTIONS (Fable, 2026-08-28,
reconciling `.audit/briefs/mill-structbreak-sol-out.md`). Sol audited
the implementation directly and found the defect every green selftest
missed: the level-cache law centers `band_center_mid2` on the READING
BAR'S MID, and sweeps 22 and 23 read `plane[bar]` as if it described
the candidate's fixed zone price. Sol's own formation-only audit over
the landed 14,650 candidates: ZERO exact zone centers, median offset
1.90 zone widths at the approach read and 3.32 at the episode-close
read. The selector never read the named barrier; lane 2 scored memory
around the exit price. RULINGS ADOPTED: F19 is REFUSE ZONE-MISCENTERED
(the miscentered selector is dead, the collision mechanism and a valid
LEVELCOLLISION rule are UNTESTED; the sweep-22 KILL stamps stand as
measurements of the refused run, no registered clause fired); sweep 23
is HELD as a refused-lineage build receipt, its rows stay unstamped and
its outcome is not judged; the falsifier was never reached. Standing
corrections for the rerun: one fixed-zone accessor (center equals
`candidate.zone_price` exactly, sources strictly prior, a current-mid
mutant red) under BOTH F19 and F20; the USER's break-close line is
PROMOTED into F20's letter family (two lanes by two deciders) before
any F20 read; the selector is high-B_opp and high-I_break with the
defence snapshot taken strictly before the breach on the defending
side; the day-scale pd term stays numerically but must be named a
day-scale persistence proxy. Morning priors from Sol: corrected F19 to
a joint EXPLORE live line 20 percent; corrected two-lane F20 after a
valid F19 kill 15 percent; the program reaching NKD 1500 + SI 1500
causally 35 percent overall, 20 percent within the current laws. Law
changes stay unearned: the grain bar requires an outcome-only raw-tick
oracle clearing rungs and MDD on both deciders WHILE powered one-minute
tests have non-positive bounds; no current result justifies touching
the exit law or the universe. The next tree: Unit 1 the fixed-zone
accessor (build only, REFUSE gates, no outcomes), Unit 2 the
F19-ZONEANCHOR rerun with the original two lanes and an exhaustive
partition, Unit 3 branch on its letter (LIVE freeze, KILL corrected
two-lane F20, UNRESOLVED a power unit). Parent failing 14 recorded in
memory: green causality selftests do not prove the price KEY; every
keyed-plane read must gate on key equality from now on.

Sweep 23 LANDED, F20 KILLED under a registered clause (Fable,
2026-08-28). Receipt `.audit/mill-sweep23.json`, 31 rows, selftest
49/49 with the letter partition proven exhaustive over all 512 outcome
points, mutant red, causality chain source-breach-arm-fill asserted per
row. FAMILY LETTER STRUCTBREAK-KILL, clause K3 CEILING-UNREACHED, one
clause matching, no fallthrough. The carrying facts: (1) the pullback
lane STARVED, fill rate 0.069, 19 selected entries, because median
pullback depth and median return speed do not compose, the fills that
happen retrace 1.2 widths within 1.4 bars, so any successor arming a
pullback limit must train depth and cancel JOINTLY on
reachable-within-window depth, never as independent quantiles. (2) The
pattern is now three universes long: formation finds money (formed
ceiling 14.27x and 15.85x of the deciding rungs, 9.0x and 12.0x capped
at 12 per date) and the preregistered causal selector cannot reach it
(-0.040x and -0.012x); same shape as F19 and the G1 universe. (3) The
pinpoint falsifier again did NOT fire, unpowered against control (upper
bounds +91.7 and +12.4, maxT p 0.47 and 0.83 on n 19); the collision
mechanism stands, this selector is dead. (4) The USER's box-exit timing
(report-only NOPULLBACK line, 365 selected, 227 seated, the only
powered line in the receipt) posts SI +140.5 usd/day seated with a
matched delta of +431.2 per date at t 1.93, the largest positive causal
delta anywhere tonight, and NKD -202.2 with a negative delta; it does
not carry both deciders and its MDD is worse. The question whether the
USER's late decision event enters the letter family is already charged
to the in-flight Sol page. (5) Parent correction of the builder's
routing note: Sol's grain-change evidence bar requires POWERED
one-minute tests with non-positive upper bounds, and ours are UNPOWERED
with positive upper bounds, so the sub-minute oracle route is NOT yet
licensed; the immediate lever is power (fill law, impulse join at 62
percent, joint-quantile arming), not grain. Verdict stamps and the
morning position wait on the structbreak Sol page.

Sweep 22 LANDED, F19 KILLED, F20 DISPATCHED (Fable, 2026-08-28). Receipt
`.audit/mill-sweep22.json`, 33 rows stamped KILL, selftest 29/29,
selector mutant red, lane-2 certs cross-checked to 0.0 usd, formation
14,650 candidates. FAMILY LETTER LEVELCOLLISION-KILL, both lanes. The
facts that carry forward: (1) the USER's episode-resolution lane BEAT
the pre-touch lane on every measure, seated NKD +84.6 and SI +48.0
usd/day against -147.5 and -114.4, binding MDD 4,596 against 19,622,
and lane-2 NKD beat a count-matched draw from its own formed blocks at
unadjusted p 0.0010; still 0.056x and 0.032x of the rungs, minus-2SE
negative, SI sign flips at the adjacent margin cut, matched controls
unpowered (upper bounds positive, maxT p 0.53 and 0.996). The late
decision event is the right direction; the selector is not yet the
right instrument. (2) The formed universe carries the cash: ceilings
46.8x and 55.0x of the deciding rungs, 10.8x and 16.1x when capped at
12 events per date. Formation found money; the preregistered selector
cannot causally reach it. (3) The pinpoint's falsifier did NOT fire
(unpowered against control, no non-positive upper bound); the collision
mechanism stands, this selector and these bounds are dead. (4) Sol's
letters failed to partition a third time; routed to KILL with the
clause labeled FALLTHROUGH; the F20 letters register the partition
completely (K3 CEILING-UNREACHED). (5) Builder deviations recorded: the
pd defence pair constructed at day scale (minute-grain prior-day paths
are HOLD-sealed), lane-1 fill rate 0.090 with depth pinned at its
floor, impulse joined to about 62 percent of candidates. Sweep 23
(F20-STRUCTBREAK-PULLBACK) dispatched per the pre-named successor,
break of a persistent zone then the first pullback, entry in the break
direction, same replay, controls, and bounds, the USER's no-pullback
box-exit timing as a report-only line. Sol reconciliation dispatched in
parallel (`.audit/briefs/mill-structbreak-sol.md`): F19 reconciled, the
F20 spec reviewed, and the morning position for the USER charged, with
the question whether the USER's late decision event should be promoted
into F20's letter family before judgment.

Unit 0 JUDGED and F19 DISPATCHED (Fable, 2026-08-28, after sweep 21).
Sweep 21 (F18-CONTORACLE, receipt `.audit/mill-sweep21.json`, 66 rows,
selftest 44/44, mutant red, P3 reproduces sweep 19's slow lane exactly)
registered no letters by design; its facts: best causal placement
P3/close on SI at 0.1026 of rung; every causal placement under 0.11 and
ALL negative under the 1800-second hold (the two positive close lines
ride session drift); the retest TOUCH beats the confirmation by +33 to
+65 usd per episode and the resumption by +48 to +74 (max-stat p_adj <=
0.0036), yet the confirmation's standalone line wins because waiting is
a FILTER, not timing ("a selector wearing timing's clothes"); the
one-bit oracle ceiling is 0.80 of rung (SI close), the two-bit
bar-plus-side ceiling 4.08, side flipped on 47-63 percent of episodes;
the paper's re-entry is a phantom (8 entries). Unit 0 route condition
applied: no causalizable placement marker carries the rungs, so
POST-TOUCH CONTINUATION ON THE CURRENT UNIVERSE IS CLOSED; sweep 21's 66
rows stamped KILL and sweep 19's 12 UNRESOLVED slow rows flipped to KILL
(the pending condition resolved against). F19 receives no post-touch
companion from the old universe.

USER DIRECTIVE on F19's shape (2026-08-28, the four-chart drawing): the
decision need not happen at candidate generation or shortly after; let
the WHOLE episode at the level complete (the green box, the entire
multi-peak fight), read everything inside it, and decide at the box's
resolution, entering in the exit direction ("we might be looking for
confirmation a bit too early"). Parent reconciliation: this is the
sweep-21 filter effect pushed to full length, and the box is exactly
where the pinpoint's barrier evidence accumulates; the measured cost is
that every late placement so far died under the fixed hold, so the lane
must win on selection by more than the lateness costs. ADOPTED as LANE 2
of sweep 22 (F19-LEVELCOLLISION): episode window opens at first
approach, closes at the first one-minute close beyond a fold-trained
band on either side after at least one touch, entry next bar in the exit
direction, completed-window features lawful. Lane 1 stays Sol's
pre-touch resting limit. One preregistered monotone selector both lanes
(B = mean standardized held-minus-broke across same-day, prior-day,
prior-session; I = frozen magnitude score; trade iff B >= train tercile
AND B-I >= train median; neighbor grid reported), one maxT family across
2 lanes x 2 deciding assets, paired level-permuted controls, frozen
outcome law primary with the 1800 s label beside, full seat replay and
MDD ledger law, letters verbatim from the pinpoint page per lane plus
the family letter. DEVIATION RECORDED: Sol's default was one lane; the
USER's order adds the second; flagged for Sol's next pass.

THE PINPOINT RULING, ADOPTED (Fable reconciliation of
`.audit/briefs/mill-pinpoint-sol-out.md`, 2026-08-28). Root cause, in
mechanism terms: hold-versus-break at an extreme is decided by BARRIER
strength relative to IMPULSE strength, and the mill's entire input plane
measures only the impulse. The frozen generator labels every local
zigzag extreme crossed by a session displacement as an independent
barrier claim, so the learning rows are repeated aliases of one impulse
path carrying no causal barrier term. Sol's page maps all nine
load-bearing observations onto this one mechanism (its section A table)
and states the falsifier: first-approach events at causally known
previously defended zones, barrier memory added to the impulse estimate,
falsified only if both the discrimination and matched-cash improvements
have non-positive 95 percent upper bounds on both deciding assets,
powered. The candidate answer is YES, formation, not availability: the
universe holds ample hindsight cash, and a differently FORMED universe
(pre-touch level collisions) should materially raise the pass
probability, while more candidates from the present generator would not.
Verdict stamps filled per its charge C: sweeps 17, 18, 20 KILL (the
MAGNITUDE-ONLY finding retained as information), sweep 19 FAST KILL and
SLOW UNRESOLVED (12 rows each), sweep 21 unstamped pending its receipt.
The path adopted with its exact letters and bounds: Unit 0 judge the
placement oracle when it lands (it licenses at most ONE post-touch line
for F19); Unit 1 F19-LEVELCOLLISION (pre-touch zones from prior-day
high, low, close, cached value edges, or same-day zones with resolved
history; one candidate per first approach; fold-trained resting limit
inside the zone with a cancel; frozen magnitude channel as the impulse
term; the level cache as the barrier term; a preregistered MONOTONE
selector in the barrier-to-impulse relation, no model-family search;
matched control with level features permuted in-fold; letters LIVE /
UNRESOLVED / KILL with the rung, MDD, cap, and max-stat bounds written
in the page). Unit 2 freeze, Unit 3 the 2021 kill-only screen, Unit 4
one HOLD read. Priors: 25 percent to a joint EXPLORE live line, 10
percent through 2021 and HOLD. Successor on kill, pre-named:
F20-STRUCTBREAK-PULLBACK (ask the porous level to confirm continuation
after a causal breach). The sub-minute grain law stays untouched, with
the page's own evidence bar for ever revisiting it. Parent adoption
note: the F19 spec must preregister the exact monotone functional
(a fold-trained threshold on the barrier score against the scaled
impulse score) before dispatch, per rule 4 of the formation law. F19
dispatch waits only for the sweep-21 receipt per Unit 0 sequencing.

The level-memory plane is BUILT (`tools/mill/levels.py`,
`build_levels.py`, cache at artifacts/cache/mill_levels/, report
`.audit/mill-levels-build.json`). 591 cells, 1.61M rows, 24 columns
across same-day memory, prior-day and prior-session memory, value edges,
and location; selftest 7/7, touch_reads_current_bar mutant red, 20 of 20
hand recounts exact, worst source-minus-stamp -949 ns strictly prior.
Two real causality defects caught and handled in the build (bar_series
clamps pre-first-trusted-row bars to row 0, those bars are marked
unsourced; on 9 asset-days the prior session closes after the current
open, prior-day columns are served only after that close). Definition
fixes recorded in the module: band centred on the reading bar's mid,
touch outcomes anchored on the touched price with symmetric band-edge
resolution, and the intraday prior session is the prior EXPLORE session
because the split makes every immediately prior locked day a HOLD day
(day-level prior-day levels still come from the true prior day). The
plane waits for the unit the pinpoint page names; nothing is fit on it
yet.

Sweep 20 LANDED (F17-MAGASYM, Sol's own G-section unit, receipt
`.audit/mill-sweep20.json`, 39 log rows, selftest 25/25, minute-OHLC
mutant red, gate exact, coarse universe matches sweep 15 exactly).
Letter MAGNITUDE-ONLY with the ASYM-KILL disjunct ALSO holding, recorded
unsoftened. Ratios first: best hash-side replay mean minus 2 SE over
rung is -0.031 NKD and -0.058 SI. What survived: the size signal is
real under the cleaner no-wall cell-balanced label, NKD R2 0.098-0.118
and SI 0.023-0.037 across horizons, adjusted p 0.005 (caveat recorded:
the day-block null lands so far negative that the 0.02 floor, not the
p, does the discriminating). What died: the direction-free coin
expectation is negative at 46 of 48 horizon-stop cells, negative in
EVERY year and EVERY phase on all three assets, no selected-minus-
control line better than p 0.60, chop near zero so the loss is not
double-stopping, and every binding MDD ledger fails by 10 to 26 times.
Sol's martingale arithmetic is confirmed by measurement: predicted size
without direction cannot be cashed by a symmetric stop. The simple
ATR-stop monetization shape is closed; no entry-model development, no
HOLD. Verdict stamps still wait on the pinpoint page (Sol was told to
fold this receipt in if it landed mid-read, and it has landed).

The pinpoint consult (USER-ordered, 2026-08-28). The USER's charge: the
parent's problem statement drifted four times tonight (side-calling,
argfirst, noise premium, size-without-direction), so the bottom-level
diagnosis goes to Sol independently. Brief at
`.audit/briefs/mill-pinpoint-sol.md`, out expected at
`mill-pinpoint-sol-out.md`. Charges: one falsifiable root cause in
mechanism terms covering all nine load-bearing observations or an
explicit minimal split; the candidate question answered yes or no (would
a differently FORMED universe raise the pass probability, with the
formation rule, decisive test, and kill condition if yes); verdict
stamps for sweeps 17-21; the shortest path to NKD 1500 + SI 1500 with
per-unit kill conditions and updated priors. Standing rule for this
stretch: the parent stamps nothing and dispatches nothing new until the
page reconciles. Failing 13 recorded in memory: diagnoses are layers
until independently confirmed; label them with what would falsify them.

Sweep 19 LANDED (F16-CONT, receipt `.audit/mill-sweep19.json`, 24 log
rows, selftest 27/27, retest_hold_reads_future mutant red, gate exact).
Letter CONT-PARTIAL, no CONT-LIVE. Best deciding line SLOW/size/SI at
+215.4 usd/day, 0.144 of the rung. Facts for the reconciliation: (1) the
SLOW lane beats the lateness-matched control on all nine lines, C1 p
0.000-0.007, the first clean CASH control beat of the program; waiting
for the specific retest that holds is better than waiting the same time
at random. (2) Nothing survives the 24-line max-stat adjustment, best
adjusted p 0.441; and per-line "first bound failed" is printed rather
than letting PARTIAL fire silently (the sweep-15 enumeration lesson
carried forward). (3) The FAST lane is dead, fails C1 on ten of twelve
lines and C2 on all twelve; its paired C2 fade numbers (+400 to +655
usd/day) are near-tautological, cells with fast displacement away from
the extreme are cells where the fade already paid, selected by a
POST-occurrence event, not a causal fade policy. (4) The carrying
diagnostic: 74 to 94 percent of slow-lane entries later retrace through
the very extreme the setup was built on. Observing one hold buys an
entry, not a lasting hold; extremes on these assets at this grain are
porous. This sharpens sweeps 15/17: the state knows size, and even an
observed hold does not certify the level. It raises the value of the
level-memory plane (grading the rare level that truly holds, the refill
paper's 25-to-63-percent gradient) and names the chop risk sweep 20
must price (both-sides-stop fraction). Verdict stamps wait for the
consolidated Sol pass when sweep 20 lands.

Sweep 17 LANDED (F14-CONDSIGN, receipt `.audit/mill-sweep17.json`, 76 log
rows, selftest 28/28, mutant red, gate exact, flipped-side certs verified
against outcome() to 0.0 usd). Letters CONDSIGN and ANTIFADE fired;
CONDSIGN-strict is FALSE everywhere (no cell beats the majority class;
the registered accuracy criterion was carried by the low base rate, the
defensible parts are the AUC and one cash cell). The findings, ranked:
(1) THE INVERSION, the night's most consequential measurement. Hold rate
falls monotonically with predicted move size on both deciding assets,
P(Y>0) 0.4946 to 0.3718 across NKD deciles (spearman -0.72), 0.4368 to
0.2934 on SI (spearman -0.87), non-overlapping Wilson bands d1 vs d10.
When a big move is predicted, the extreme BREAKS. The USER's composition
inverted at stage one, and the inversion is direct evidence for the
USER's own continuation reframe (sweep 19) and the magnitude-asymmetry
route (sweep 20). Nuance recorded: part of the falling hold rate is
wall-censoring of volatile fades (Y is wall-capped); the priced units
with explicit stops disambiguate. (2) Conditioning flips NKD sign
information, pooled AUC 0.4667 (z -6.5) to 0.5446 (z +5.0) top-quartile,
0.5696 decile; SI is reliably ANTI-predictive inside the subset (z -8);
HG nothing. (3) The absorption features add +1070 usd/day in exactly one
cell, NKD quartile ridge24 -68.5 to +1001.9, cash p_adj 0.0050, not
surviving at the decile, absent on SI/HG, unpriced (about 36 entries/day,
no occupancy). The discrete cut runs OPPOSITE the deck direction on our
minute data, absorption-present rows hold LESS (NKD 0.333 vs 0.366, SI
0.280 vs 0.337). (4) ANTIFADE: continue-side on SI quartile posts +16663
usd/day (p_adj 0.013) but the matched null collects +12407 of it, day
drift, selection excess +4257; NKD negative; unpriced, about 100
concurrent entries/day, no seats or MDD. Verdict stamps for sweeps 17,
18, 19, 20 wait for ONE consolidated Sol consult when 19 and 20 land.

Sweep 18 LANDED (F15-EPISODE, receipt `.audit/mill-sweep18.json`, 16 log
rows, selftest 71/71, mutant red, gate exact). Letter NONE, powered
(R6 n 279 NKD, 77 SI, both past the 30 floor). The ordered six-gate
ladder does nothing on either deciding asset (NKD -78.30 usd/day, SI
-137.95 at the full ladder, adjusted p 1.0000 throughout, lateness
control not beaten). On report-only HG the grammar builds monotonically
(-27 to +344 mean Y, adjusted p 0.0005, the ORDER itself worth +280
against the unordered AND, lateness beaten) BUT the sweep-16 cross-price
kills the comfort: under the 1800-second hold HG's +344 becomes -59, so
the ladder on HG collects session-scale drift, the same size effect, not
a local absorption edge. Three instrument facts for the reconciliation:
(1) the median post-effort adverse excursion at minute grain is 0.0
ticks (p90 1.0), so the library's 18-tick flush is a sub-minute object
our lawful input grain does not resolve; either the micro-episode is
absent on HG/NKD/SI or it is invisible at one minute, and the
distinction goes to Sol; (2) G5 repeat fires on 93.3 percent of rows in
this stream, saturated, no discrimination, contrasting sweep 13's
matched design; (3) coverage ceiling 0.89 by construction (scoring days
reach 123/120/117 of certifiable cells). Verdict fill waits on the Sol
reconciliation with sweeps 16 and 17.

Sweep 16 LANDED (F13-FIXHOLD, receipt `.audit/mill-sweep16.json`, 19 log
rows, selftest 22/22, mutant red, stream gate exact, sweep-15 cross-check
matches to 0.001). Pre-registered letter DEAD, all four horizons, all
assets. The facts: sign R2 negative at every hold on every asset (best
deciding-asset signed R2 -0.032 at 1800 s); the magnitude channel SHRINKS
as the hold shortens (NKD 0.126 to-close falls to 0.087 at 1800 s, HG
0.119 falls to -0.005), so the size knowledge lives at session scale, not
the next half hour; SECOND minus FIRST cash negative at every horizon
(every adjusted p 1.0), so the sweep-13 timing mechanism does not monetize
under fixed holds either; BELOW-P5 clustering on 21 of 24
asset-horizon-grain cells, reproducing sweep 15 at every horizon; every
predicted-magnitude top-decile mean Y_h negative against a 625-833 usd
per-trade requirement at 0.6 coverage; MDD not reliably compressed
(HG 0.57-0.65x, SI expands to 1.04-1.78x and the only positive to-close
total flips negative). Parent acceptance of the letter is PENDING the Sol
fixhold page per standing law; verdict column fill waits for that
reconciliation. Budget note: the build ran 55 minutes against a 35-minute
budget absorbing the mid-flight sweep-15 additions after the registered
spec was complete. The Sol
design pass on the whole complex is dispatched
(`.audit/briefs/mill-fixhold-sol.md`, out at `mill-fixhold-sol-out.md`):
design errors, capacity honesty, the development ladder under 467 adaptive
EXPLORE rows, MDD accounting for sequential entries, the entries-not-exits
framing judged, the noise toolbox ranking, the magnitude route judged with
priority, blunt priors per route. No sweep-16 verdict before that page
reconciles. HOLD, 2025H2, and the 2021 kill-only license remain unspent.

## Sol's closure ruling after sweep 14 (received 2026-08-27, reconciliation
pending sweep 15)

`.audit/briefs/mill-sweep14-sol-out.md`. Sol rules: close the
side-resolution mill on the current input plane. No sequence learner (385
effective sequences cannot settle that class and a result either way
decides nothing), no meta-layer (no measured competence signal exists for
it to use; the hindsight phase gate tops at $97/day), no 2021 read (the
kill-only license stays unspent until a genuine survivor exists), no HOLD
read (no survivor to read; spending it on development destroys its role).
Its closure statement is scoped: the tested policy classes on these
frozen inputs do not identify paying occurrences; the closure does not
claim the oracle is causal, that full-history functions are impossible,
or that a different generator or exit law would fail.

Its ranking of the USER's controls: the EXIT LAW is the single change
with the highest probability of reopening the conclusion, because sweep
13's ordinal mechanism (extension cut against matched lateness, adjusted
p 0.030, both deciding assets) is the night's only surviving causal
evidence and it is a TIMING effect the wall-or-phase-close payoff cannot
monetize. Generator change ranks second (a formation rule suppressing
ambiguous repeats, not more candidates). Rung or MDD changes alone fix
nothing (cash is negative per trade). Sol notes explicitly this is not
authorization: the USER has ruled no exits.

Parent status: adopted as the standing ruling PENDING sweep 15's
noise-ceiling decomposition, which decides how the closure reads (real
structure missed by methods, or oracle premium that was never a target).
The final reconciled position issues when sweep 15 lands.

## Standing law: Sol reviews every design decision (USER, 2026-08-27)

USER order, unconditional. Every design decision gets a Sol pass. That
covers every new unit spec, every judging-law change, every diagnosis,
and every routing choice. Where speed matters the Sol dispatch runs in
parallel with the build, and no result is judged before the Sol page is
reconciled. The record shows why: Sol flagged surrogate-metric selection
as a core error in its sniper audit and its root-cause pass, and the
parent kept shipping proxy-selected units until sweep 14. A caught
correction that is not adopted is a process failure, and this rule makes
adoption structural instead of discretionary. Exceptions require a
written reason in the ledger before dispatch.

## Sol's blank-slate root cause: argfirst (adopted, Fable, 2026-08-27)

`.audit/briefs/mill-rootcause-sol-out.md`, independent, receipts-proven.
The load-bearing error across the entire program: every executable policy
- fixed clocks, event triggers, retests, gates, my grammar, Sol's own
designs - takes the FIRST occurrence that clears a local predicate and
spends the cell. `argfirst` where the domain requires an ordered stopping
process. Receipts: ~15 qualifying occurrences per selected cell with
first-is-last rates of 3-6%; soft-correct triggers entering before the
next extension 49-58% of the time; the loss concentrated in early
continuation; S0/B2 recovering value precisely by ORDERING within a
side; I4's first-terminal oracle clearing every rung with no side bit.
This diagnosis supersedes and explains my refuted score-vs-sequence
claim: sweep 11's grammar was ordered in its stages but still argfirst at
entry, which is exactly why its stage-shuffled control matched it. The
occurrence ordinal has never once been policy state in 425 logged trials.

Adopted with it: (1) the resurrection table - family closures were
overbroad; quiet age, retrace hold, F/S components, held-retest
vocabulary, prior-level contact, and candidate depth are revived as
STATE-TRANSITION INGREDIENTS while every priced argfirst policy stays
dead; (2) the process fix - the log gains mechanism facts (transitions,
vetoes, availabilities), not just verdicts; (3) Sol's independent
reachability finding: the goal IS reachable under the frozen inputs,
costs, exit, occupancy, and cap laws - S0R and I4 prove no lawful change
is needed before testing the occurrence selector.

The first build is Sol's ordinal-2 ablation (its section C, dispatch-
grade): the frozen sweep-8 PRIMARY fires unchanged; enter the SECOND
distinct in-zone candidate occurrence instead of the first; same-side new
extremes reset the ordinal and void the fire; a TIME-MATCH control prices
lateness separately so ordinal-2 only gets credit beyond it; hard
pre-registered bounds (SECOND beats FIRST by 0.10 and TIME-MATCH by 0.05
on postX_1800 at coverage 0.35, adjusted p 0.05); one gated price read
under the standing bars. A pass licenses the finite-state grammar; a fail
kills ordinal two, not every ordered process. Dispatched as sweep 13.

## The structural diagnosis: score versus sequence (Fable, 2026-08-27,
USER-forced; REFUTED by sweep 11's stage-shuffled control and superseded
by the argfirst diagnosis above)

USER: the approach is architecturally wrong again; name it. Named:

Every unit tonight - the R5 composite, the quiet gates, the retest
screen, the E1 gate, the survival evidences - collapsed ordered event
structure into scalar scores and thresholded them. The source material
the USER supplied specifies ORDERED EVENT GRAMMARS with hard per-stage
vetoes: arrival, then absorption, then control transfer, then hold, in
that order, each stage able to kill the setup outright. Averaging stage
evidence into a composite destroys precisely the ordering information the
sources insist carries the meaning. The measured pattern of the night
matches this diagnosis exactly: every individual component separates a
little (one-sidedness 0.61-0.66, delta-flip 0.64-0.66, quiet recall
0.74-0.96), every scalar combination of them fails (dilution plus the
wrong computation class), and the literal ordered conjunction has never
been run once. The prior CatBoost era made the same class error from the
other side (atomic features, learned interactions). Two computation
classes tried; the one the domain specifies, never.

The unit that follows (sweep 11, the grammar automaton) runs the exact
two-lane sequence the diagram forensics extracted, as an automaton with
resets - no weights, no averages, no score: per (cell, side, zone):
stage 1 arrival (attack volume into the zone at or above its stratum
p60); stage 2 absorption (price yield per attack at or below p40 during
the arrival, or a one-sided terminal print); stage 3 control transfer
(signed delta flips toward the fade within 3 bars - the fast lane - OR
pull-away then a retest that holds beyond the zone edge - the slow
lane); stage 4 hold (no new same-side extreme for k bars); stage 5 entry
at the first in-zone fade-side candidate. Any stage failing resets the
automaton for that side. Precision-first metrics with a per-stage
attrition table so a failure names its stage. The MDD overlay
(stand-down cadence after a wall, lawful and entries-only) rides as a
priced variant on whatever survives.

## Sweep 8b ruling: the safety-payload tension (Fable, 2026-08-27)

`.audit/mill-sweep8.json` sweep8b key, rows sweep8b-001..004 KILL. The
E1-only gate carries the best safety ever measured (fixed-horizon
extension 0.143-0.245, the lowest SWIB wall rates of any line) and the
least cash (-143.7 to +248.4 usd/day; five of six lines stress-negative).
Mechanism, from its own tables: it fires at median 8.9-11.4k s into the
phase, where the remaining move is spent. The composite's +211 NKD line
earned on earlier, riskier fires whose survivors still carried payload.

The tension is now named and measured: on these inputs, causally-knowable
safety arrives AFTER the payload leaves. Minimizing extension and
maximizing cash disagree. The decisive instrument is the matched-twins
certificate (Sol's sweep-9 spec) joined with the O4b decay curve: does
ANY causal state identify survival early enough that remaining cash still
clears the per-trade requirement at deployable coverage? Sol's sniper
audit (in flight) rules on sequencing; the certificate is the leading
next unit either way.

## Sweep 8 ruling: composite KILLED on credit; E1-only is the survivor
evidence (Fable, 2026-08-27, overnight)

`.audit/mill-sweep8.json` final, rows sweep8-001..006 KILL. All six priced
lines miss the rungs (best NKD PRIMARY +210.7, stress positive, adjusted
null 0.0547; MDD 3.3k-12.5k). The adopted credit law then fired: at the
fire stamp the composite's fixed-horizon extension (0.430-0.475) is
indistinguishable from phase-matched random (0.397-0.482) and it fires
EARLY (median 1.3-2.8k s into phase) - a clock with favorable censoring,
exactly the failure mode Sol named. Sol's cadence critique is proven: the
E2-E5 evidences diluted the one real signal. The E1-ONLY control - quiet
age alone against its own walk-forward percentile - posts extension
0.159-0.245 at coverage 0.78-0.83, firing late (median 9.4-11.4k s), the
strongest survival separation measured all night, and it was never
priced. SWIB's share ROSE under the composite (0.83-0.87) because early
fires enter before extension resolves; depth still cut SWIB walls to
0.31-0.51. Ruling: the five-evidence composite is retired; sweep 8b
prices the E1-only gate with both entry laws under the standing bars,
dispatched to the same agent. The second-attempt policy and Sol's sniper
audit queue behind its result.

## Sol co-ideation adopted: the sweep-8 judging law and both branches
(Fable ruling, 2026-08-27)

`.audit/briefs/mill-sweep8-sol-out.md` reviewed; adopted in full with the
frozen terms unchanged:

1. **The judging law.** Sweep 8's verdict separates three objects: fixed-
   horizon extension (postX_1800) measured FROM THE GATE FIRE, the same
   from the candidate entry, and the fire-to-entry wait. The composite
   earns belief only if fire-stamp postX_1800 beats BOTH an E1-only
   control and a phase-time-matched random control by >= 0.05; an
   entry-time pass without a fire-stamp pass belongs to depth, delay, or
   censoring - a clock with favorable censoring, not a survival detector.
   Phase 2 is read first. If sweep 8's tables lack these columns, the
   agent adds them before any verdict.
2. **Design critique banked for iteration two** (frozen bar stands now):
   E1/E2/E4 are one cadence mechanism worth 3/5 of G; the 60th-percentile
   bar carries a repeated-look mismatch (calibrated per bar, watched over
   many bars; the correct object is first-crossing per episode); E3 can
   go stale and resets on same-side extremes next round; E5's polarity is
   the least secure. Tables must report bar-level crossing frequency AND
   episode-level coverage.
3. **No late classifier.** The all-late causal mix ceilings at ~1167/1217
   usd/day at full coverage; standalone late lines cannot clear, and
   composition demands the depth line already post >= ~1074-1170. The
   survival selector judged on fixed exposure IS the late policy done
   lawfully.
4. **The hillclimb ladder if sweep 8 is interesting-or-better**, one knob
   per unit, each with pre-registered bounds (Sol section C): second
   distinct in-zone candidate (the direct SWIB attack) -> two-bar gate
   persistence -> inner-half zone -> late composition only when the
   section-B equation is satisfied. Freeze an asset the moment it clears
   rung + MDD both orderings + stress + adjusted null.
5. **The kill branch is ready to paste**: sweep 9, the matched-history
   survival certificate (Sol's full dispatch text, in its page), with
   SURVIVOR / REGIME_SURVIVOR / CERTIFICATE / UNRESOLVED letters - the
   instrument that either routes a scoped successor or closes
   transformations of the current causal state with a receipt.
6. **Unsharp band**: third label AMBIGUOUS for diagnostics; ignored for
   policy (postX needs no side label); hindsight abstention banned.

## Sweep 7b verdict and the sweep-8 amendments (Fable ruling, 2026-08-27)

`.audit/mill-sweep7b.json`, rows sweep7b-001..006, all KILL. Two rulings
and two amendments, all pre-cash for sweep 8:

1. **The flip is dead and variant C stays closed.** Measured flip
   agreement is 0.463/0.473/0.410 - the 0.618 lead was the naive
   complement awarding the 12-14% unsharp band to the flip. The charter's
   variant-C condition (flip cash-positive on a deciding asset)
   technically fired on NKD (+30.9), but 7b's own registered decision
   table (INTERESTING=False, every bound fired, stress -115 to -378)
   supersedes it; ruling recorded rather than silently applied.
2. **The bleed has a name: SOFT-WRONG/IN-BUDGET - right idea, wrong
   depth.** 67/84/77% of gross loss with wall rates 0.47-0.74: fades of
   the smaller-but-positive side, entered near the trigger, get walled by
   the residual extension before their remaining value can realize. The
   side was never the problem; the DEPTH of the entry relative to the
   coming extension is. Hard-wrongs are 8-16% of loss. The
   18-ticks-inside source geometry is now our own measured mechanism.
3. **Amendment one, evidence-forced: the lateness cap is dropped.** LATE
   entries are the profit center (win 0.86-0.92, wall 0.00-0.04, +310 to
   +466 usd/day buckets); excluding them makes every asset worse by 150-
   450 usd/day. The frozen fire-window (extreme age inside 45/60 min) is
   replaced by remaining-time >= 1800 s only. The O4b decay curves bound
   oracle cash, not causal safety; a causal fire that comes late is late
   BECAUSE the extension resolved, which is selection, not decay.
4. **Amendment two: depth entry is primary, not a variant.** Entry takes
   the first fade-side candidate whose decision quote sits inside the
   zone (within 0.15 ATR of the extreme); the any-candidate form becomes
   the control. This attacks SWIB directly.

Both amendments are recorded here before sweep 8 reads any outcome; the
gate's five evidences, the 60th-percentile bar, postX as primary metric,
and all other frozen terms stand unchanged.

## Sweep 7a verdict and the survival reframe (Fable, 2026-08-27, overnight)

`.audit/mill-sweep7a.json`, rows sweep7a-001..012, all KILL. The held-
retest join and cross-phase memory are both side coins (error 0.47-0.57,
Wilson uppers to 0.68, against the 0.02 ceiling); coverage was never
binding (0.91-0.98 on screen A, no_candidate zero everywhere).

The finding that reframes everything: **soft-hit is 0.91-0.98 on every
asset and both screens.** At these trigger moments, nearly ANY fade side
carries positive remaining value. The side question - the object of
sweeps 5 through 7a - is economically nearly irrelevant. The bleed
mechanism is post-trigger extension: median trigger delay is NEGATIVE
(the join fires before the direction's true terminal extreme, which then
extends), and the post-trigger new-extreme rate runs 0.44-0.88. Money is
lost to entering while the run is still alive, not to fading the wrong
end.

Binding consequences: (1) the primary no-cash metric for every successor
is the post-entry extension rate (the loss mechanism), not side
agreement; (2) the central family is the per-side SURVIVAL gate - will
this direction print another extreme? - via the competing-risk/renewal
model (Sol attacks 5 and 7), with the tape-speed die-off (quote-event and
volume decay, our own series) and the banked terminality separators (F
one-sidedness AUC 0.61-0.66, S persistence) as evidence, walk-forward,
selective; (3) lateness is bought with coverage, which has 0.5+ of
headroom above the floors; (4) entry depth inside the zone buys wall
buffer against residual extension (zone dip p75 is 0.19-0.26 ATR - about
700 USD on HG - so depth is not optional). Sweep 7b's bleed decomposition
(running) prices each bucket; sweep 8 implements the survival-gated fade.

## Why can't we decide: the label post-mortem and the anti-correlation
lead (Fable, 2026-08-27, overnight; USER question)

USER asked whether the labels are wrong and whether the teacher was
inherently wrong to learn from. The honest answers, and one discovery:

1. **The teacher as PRICER is law; the teacher as TEACHER was poison.**
   The wall/phase-close law defines the game's cash and stays. But as a
   learning signal it conflates two different errors: a right-side entry
   900 too early receives the same -900 as a wrong-side entry. Anything
   trained or selected on raw cert/wall outcomes inherits that confusion,
   which is part of why every side signal has graded as a coin. The
   B-era's use of STORED teacher labels added READY survivorship and
   snapshot framing on top - measured poison, long abandoned. The mill's
   Delta* label fixed the timing conflation for SELECTION; the residual
   label risks are the soft-hit asymmetry (a "wrong" pick with positive
   remaining value is not a disaster) and the arbitrary ambiguity band -
   both now being measured, not assumed.
2. **The discovery: first-quiet side-hit is consistently BELOW coin**
   (0.36-0.47 across sweeps 5 and 6 arms; NKD D-alone 0.382). An
   anti-correlated signal is a signal. Flipping the fade at the SAME
   entries gives 0.53-0.62 side agreement for free - NKD 0.618 - at
   identical coverage and delay, with zero new selection freedom. The
   structural reading: the first-quiet extreme tends to be the RESTING
   side (the exhaustion-drift lesson, now measured on our bytes), so the
   flipped rule is a JOIN policy - enter the drift away from the resting
   extreme - discovered through the anti-correlation rather than
   assumed. Nobody ever priced it; the side-flip lines in earlier sweeps
   were polarity controls on OTHER families.
3. **The bleed decomposition is the WHY instrument.** Every D-alone entry
   buckets into {hard-wrong, soft-wrong, right} x {in-budget, late}; cash
   per bucket says exactly which failure eats the money - decision
   quality, the delay tail, or label fiction. Dispatched with the flip
   pricing as sweep 7b.

## Decisive flow test verdict: KILL; the discretionary layer is closed
(Fable, 2026-08-27, overnight)

`.audit/mill-sweep6.json`, log rows sweep6-001..012, all KILL. The frozen
bounds fired on both deciding assets: R5-vs-D and R5-vs-M deltas +0.009 /
-0.038 (NKD) and +0.028 / +0.029 (SI), every paired 95% lower bound below
zero, adjusted p 0.70-1.00, R5 coverage 0.576/0.444, and p90 delays
(7,136 s NKD / 9,012 s SI) far past the 1,200/2,700 s caps - the controls
exceed the caps too. Per the frozen protocol the discretionary layer is
CLOSED: no second composite, no fit, R4mem stays sealed forever (its
opening conditions require every delta >= +0.03; NKD's R5-M is negative).
The pre-registered route - the held-retest resolution join - was already
in flight when the verdict landed.

Three measured facts survive the closure as OUR OWN data (not deck
claims), available to the terminality-race family as individual,
pre-registered gates only, one shot, no weights, and only if geometric
evidence alone falls short: (1) finished-auction one-sidedness and
schedule persistence separate TERMINALITY univariately (AUC 0.61-0.66 on
HG/SI); (2) the one-sided-print polarity is confirmed on all three
assets; (3) the deck-tier "CVD dies at the level" precursor is INVERTED
on our bytes (AUC 0.30-0.39) - retired. Structural finding for every
successor: quiet-detection's delay TAIL is the budget-killer (medians fit
the budgets, p90s run hours late), so the race family must gate on
opportunity lateness, not just fire on evidence.

## Idea-screen results and the terminality-race reframe (Fable, 2026-08-27)

`.audit/mill-ideascreen.json`. I1 prior-phase inheritance is dead as a
general prior (every row a coin, ci_low <= 0.52) with ONE flagged cell:
SI phase 0's overnight-gap sign agrees with the winner 18/24 = 0.750
(ci_low 0.551, n small) - carried as a candidate SI-Asia ingredient only,
exploratory.

I4's oracle arithmetic reframes the problem. Entering at the
chronologically FIRST terminal extreme of EITHER direction, fade side,
posts **2102.6 / 2335.2 / 3070.0 usd per asset-day with zero walls and
zero second legs - all three rungs clear, HG included, and the side bit
never appears**. Mechanism: in a trending phase the winning side's
adverse extreme finishes first by construction (the drift side's extreme
keeps extending), so the ORDER of terminality encodes the side. The
binary rejection-vs-rest decision dissolves into a per-side terminality
RACE: run independent terminality tests on both extremes and take the
first side whose evidence crosses a calibrated bar. The naive version
(first 20-minute quiet) posts -144/-170/+49 with 28-43% walls, so the
entire gap is per-extreme terminality PRECISION within the delay budgets
- the same precision problem, now stripped of the side problem entirely.

Sweep 7 centerpiece, to dispatch after sweep 6's verdict and Sol's
ideation land: per-side terminality state machines racing - evidence =
quiet + the I2 retest-hold (bounce, return, hold strictly beyond the
extreme) + I3 opposite-side extension since my extreme + any flow
component sweep 6 keeps; per-asset calibration to the delay budgets
(NKD fast, SI slower); soft-hit metric beside joint-hit (narrowness
audit item 3); optional leg-2 insurance priced as a variant; SI-p0 gap
prior as a bonus gate. Selection stays no-cash.

## Narrowness audit (Fable, 2026-08-27; USER: "is the binary decision
really the whole problem, or are we too narrowed down?")

The oracle chain isolates the gap cleanly (S0R clears all rungs with side
+ pick; O4b shows side + terminal-timing suffices with per-asset delay
budgets; the quiet detector finds the moments causally; the residual is
which extreme). Three qualifications join the problem statement, none
hidden any longer:

1. **The decision must be fast, not just right.** O4b's budget is
   measured from the TRUE terminal extreme; a causal chain spends
   detector quiet-time + decision + candidate wait against it. NKD's
   budget (~20 min buffered) makes speed binding there; the frozen p90
   delay bounds carry this, but any future design that decides slowly and
   correctly still fails NKD.
2. **Ambiguity handling is part of the causal problem.** Oracle lines
   skip hindsight-ambiguous cells (~25-30%); a causal policy either
   enters them (diluting $/day, some wall risk) or abstains by proxy
   (coverage cost). The ambiguous-cell entry cost is measurable in one
   pass and joins sweep 7.
3. **The joint-hit metric may OVERSTATE the gap.** W picks the larger
   remaining side, but S0 measured even the smaller side's deep fade
   mildly positive; a "wrong" pick with positive remaining value is a
   soft hit, not a disaster. Sweep 7 adds the soft-hit rate (fade side
   has positive REM at entry) beside joint-hit; selection may shift, and
   the effective accuracy bar may be lower than 0.55 once asymmetric
   penalties are priced.

Not hidden elsewhere: transport risk (one HOLD read + Thresholdout law),
execution frictions (priced in every cert, zero occupancy skips),
architecture narrowness (the catalog carries dissolutions: both-extremes,
join, regime split).

## Library fidelity ruling (Fable, 2026-08-27, after diagram forensics)

`research/discretionary/DIAGRAM_FORENSICS_2026-08-27.md`. The lesson decks'
figures are partly fabricated or self-contradictory (a mirrored POC-flip
illustration, imbalance flags failing their own stated rule, a mislabeled
delta bar, the absorption-vs-exhaustion page carrying no figure at all).
The library therefore splits into two evidence tiers, binding: the
refill-effect research paper (real study, measured AUCs, execution stats)
keeps full weight; the lesson decks drop to hypothesis-generators whose
qualitative claims carry no evidential weight beyond what our own
distributions measure. No design change - the frozen test never trusted
the diagrams and the measure-ourselves law already governs - but "the
sources say" language is retired for deck-tier claims. The USER's
instinct (measure everything ourselves) is validated at the source level.

## Ideation round: candidate solutions to rejection-vs-rest (Fable, 2026-08-27)

USER: strong answers needed; the absorption read may or may not be the way;
generate novel attacks. The catalog, by attack class, each with its cheap
test. Sol runs an independent generation pass in parallel; sweep 6's verdict
merges with this catalog into sweep 7.

Class 1 - move the decision time:
- **I1 prior-phase inheritance**: does the completed prior phase's sign
  (and the overnight gap) carry the next phase's Delta*-winner? Never
  tested; fully causal; one array pass. If any (asset, phase-pair) shows
  0.60+, it is a free side prior that composes with everything.
- **I2 retest-hold trigger** (the strongest in my judgment): decide at the
  completion of the first two-legged structure after a quieted extreme -
  bounce, return toward the level, hold strictly above it (higher low /
  lower high). The classical reversal definition; a PATH condition, not a
  level read; fully causal; the one-retest source's whole thesis; entry
  falls inside the measured 45-60 min delay budget; d1 wall protection at
  the retest hold. No detector tried this shape - XR's bounce was a fixed
  retrace with no hold-above requirement.
- **I3 control-transfer sequencing**: fade extreme A only when extreme B
  was tested AFTER A's last test and failed (the opposite side tried and
  lost). Uses the ORDER of tests across both extremes; everything so far
  looked at one extreme at a time.

Class 2 - new evidence at the same time: the in-flight flow/memory score;
POC value-migration drift as a slow state; session-open gap fill state.

Class 3 - dissolve the choice:
- **I4 both-extremes sequential**: fade whichever quiets first with a
  protected entry; if that leg exits, fade the other on its confirmation.
  Converts the side decision into an entry-quality problem. Grounding: S0
  measured even the WRONG side's best-price fade mildly positive
  (+506/588/599 usd/day hindsight), so the loser leg need not be fatal if
  entries are protected; occupancy and the 12-entry cap accommodate ~2
  entries per cell at measured coverage. Oracle arithmetic is one pass on
  the existing cert surfaces.
- **I5 regime-conditional composition**: balance regimes get the fade
  policy, trend regimes the join policy; the regime flag is causal (range
  vs value/forecast). The structure audit says identical evidence inverts
  meaning across that split - one rule everywhere may be impossible by
  construction.
- Persistence-join stays queued as the standing reframe.

Screens dispatched now (no-cash, read-only, independent of sweep 6): I1
and I4's oracle arithmetic. I2 and I3 need the zones/detector machinery
and join sweep 7 with sweep 6's verdict and Sol's independent list.

## The decisive flow test, frozen (Fable ruling on Sol + playbook, 2026-08-27)

Sol's ruling (`.audit/briefs/mill-flow-route-sol-out.md`) is adopted as the
protocol: one zero-fit paired test on frozen detector opportunities, NKD
and SI decide, HG diagnostic; kill/keep bounds pre-registered; a miss
closes the discretionary layer; persistence-join is next if it misses; and
the control override stands - if the in-flight vs_mean composition passes
the same gates, freeze it and stop.

Two amendments, made BEFORE any label is read, forced by evidence that
arrived after Sol wrote (the playbook's 41k-touch study and the flow
audit):

1. **A level-memory component joins the score.** Flow-only grades AUC 0.54
   in the source study while memory/location carry it to 0.63; the audit
   made memory-first binding. Component Mem = the mean of P(episode touch
   count at this zone) and P(prior touches that held, from the zones
   cache), plus the at-prior-day-level flag folded as a percentile.
   Primary score R5 = (A + D + F + S + Mem)/5. The single fallback
   (openable only under Sol's second-iteration conditions) is
   R4mem = (A + D + F + Mem)/4, dropping schedule persistence - Sol's
   named unstable component. Sol's exact R4 and R3 ride as diagnostic
   columns only.
2. **F's second term is the finished-auction signature, not assumed
   twoside polarity.** The playbook's footprint decode shows the terminal
   extreme printing ONE-sided (a max-delta attack bar) with the delta
   flipping the next minute, while two-sided extremes were non-terminal.
   F = mean of P(reversal-aligned delta within 2 bars of the last zone
   touch) and P(one-sidedness of the touch print). twoside enters the
   diagnostic table with its polarity reported, never the score.

Everything else per Sol verbatim: A and D as defined on its page;
percentiles calibrated outcome-blind per (asset, phase, Q) stratum; the
60th-percentile margin rule, not swept; arms D / M / R5 on identical
opportunities; joint-hit rate J (Wilson lower bound) primary with yield Y
as the abstention guard; within-cell high-low swap null, 10,000 swaps,
seed 20260827, max-statistic adjusted; keep bounds +0.05 deltas on both
assets against both controls, coverage 0.40/0.35, p90 delay inside
20/45 min; immediate kill below +0.03 or on asset disagreement; reload
and iceberg never in any score. Cash round, only after a no-cash keep:
the frozen policy priced once, with one pre-registered secondary line
(entry preferring candidates whose decision quote sits inside the zone,
the playbook's resting-inside-the-level fact under our frozen fill law);
HOLD per the standing bar, one read, no amendment, a miss closes the
layer.

Dependencies: sweep 5a's detector states and M arm; the zones cache
(episodes, touch memory, POC). The test dispatches when both land.

## Sol sweep-3 read, reconciled (Fable, 2026-08-27, overnight)

`.audit/briefs/mill-sweep3-read-sol-out.md` reviewed. Adopted, binding on
the sweep-4 judgment and its follow-up:

1. **The grain attribution was over-claimed.** REM and terminal-fade share
   the 60-second lattice; they differ in side label, entry objective,
   eligible cells, and legality time, so the HG gap does not isolate entry
   grain. The four-line matched attribution runs before any grain claim:
   S0-side x best candidate, S0-side x best lattice quote, stable-side x
   best candidate, stable-side x terminal bar-mid, one denominator.
2. **Terminal-hit alone is not the selection metric.** Phase close censors
   it and every side has a final adverse extreme, so a late wrong-side
   rule can score high. Selection runs on the Wilson lower bound of
   joint_hit (terminal AND fade side equal to sign(Delta*) at entry), with
   terminal-only and side-only as the decomposition, plus future
   adverse-candidate regret as the soft timing label.
3. **Coverage floors rise** to 0.70 / 0.40 / 0.35 (HG / NKD / SI)
   for stage-B qualification, from Sol's break-even arithmetic at the REM
   means; 0.30 stays as a census line only. HG floors serve the
   composition track since the USER deferred HG.
4. **O4c is judged cell-weighted** with the Q+1800 s eligibility guard;
   event-weighted rates are sensitivity only. O4b is judged on matched
   cohorts with imposed delay separated from candidate-wait lag.
5. **The 72-config cross prunes before cash** under pre-registered
   incremental gates: Q-only and retrace-only baselines always run; a
   cross or zone earns its cell only by cutting false positives at least
   0.10 while losing at most 0.10 recall or coverage and at most five
   minutes median delay. Per-phase Q comes from one pooled error target
   (smallest Q with cell-block FP upper bound at most 0.15 per phase),
   kept per-phase only if phases differ by 20+ minutes with the same
   gates.
6. **The decisive judgment is the O4b x O4c intersection** per Sol's
   frozen branch table: a viable Q must sit inside the delay budget AND
   separate terminality; either table alone cannot pass the family.
   Buffered bars 2500/1875/1875 at d=20 minutes define a broad budget;
   rung bars at d=10 a narrow one; NKD or SI below rung at every d>=10
   closes standalone quiet confirmation.
7. **The HG composition candidate is LATE-MEAN x TERMINAL**: after 5400 s
   the running-mean side call (0.59-0.60 accuracy on HG) gates which fade
   detections are eligible; the terminal detector picks the time; entry is
   the first agreeing candidate; vs_mean never becomes an entry clock. Its
   no-cash gates: joint_hit lower bound +0.05 over D-alone, HG coverage
   >= 0.70, p90 delay inside the buffered O4b budget. A side-gate variant
   is also measured for NKD/SI.

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
amended after. The parent's own bar for spending a read: the covered
assets' rungs cleared on EXPLORE with both drawdown orderings under 1000,
the 2% adversarial stress held, and the adjusted permutation null at or
under 0.05. A marginal rule does not spend a read. USER 2026-08-27
(overnight): HG may be skipped for now - a rule covering NKD and SI alone
qualifies for its HOLD read; HG 2000 stays the full goal on the
composition track without blocking the two-asset milestone. For NKD and
SI the rung is the floor, not the finish: after clearance, hillclimb
iterations push margin toward the measured ceilings (terminal-grade
2209/2475, REM-grade 3600/4230 usd per asset-day).

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

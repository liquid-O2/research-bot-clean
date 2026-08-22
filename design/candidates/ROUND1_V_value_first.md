# Candidate V (value-first lane, verbatim) — landed 2026-08-22

All facts verified. Assembling the package.

---

# Design lane V — VALUE-FIRST entry selection

**Forcing constraint honored:** every training target is one candidate-row's standalone dollar outcome under the frozen exit convention (earliest of anchored close / phase close / first $900 wall touch — `engine/entry_v2/replay.py:36-39,25`). No DP, no substitution adjustment, no other candidate appears in any label. All selection intelligence lives in the causal decision rule.

**The design in one sentence:** train ONE single-target dollar head on the candidate's standalone net PnL (`signed_pnl_usd`, the exact quantity replay banks), isotonic-map its score to dollars on the platt block, and let a calibrated **EV hurdle** — theta chosen by the existing 21-quantile weekly-LCB law on the threshold block — be the entire entry decision, with priority = EV so the frozen per-second competition, occupancy, and caps concentrate the day on few high-EV entries.

A structural note that shapes everything below: **the standalone-value head already exists in the frozen system as a feature factory.** The component stack's `current` head is MultiQuantile(0.2/0.5/0.8) trained on `current_entry_usd` (`engine/entry_v2/tabular_models.py:423`), and `current_entry_usd` IS `signed_pnl_cents/100` — the standalone trade value (`engine/entry_v2/exact_delayed_teacher.py:1024,1040`). The E1R failure never tested "decide on the standalone value"; it buried this head as 10 stacked features (`tabular_recovery_contracts.py:29-34`) under a $20-scale substitution-margin head. This design promotes the standalone value from feature to decision object.

---

## (a) Caller's usage first — the walk's call site

The only caller is the chronological walk (`tabular_walk_twin._wtwin_walk`, `engine/entry_v2/tabular_walk_twin.py:518-549`; production later via the same `decide` interface, `tabular_policy.py:56`). Busiest moment — timestamp T, asset HG free, two live HG candidates A and B arrive at the same nanosecond, portfolio has 1 seat left:

```
for (T, rows) in plane.by_timestamp:                     # dense scored seconds
    state_A, state_B = decision_state(rows)              # PortfolioDecisionState each
    d_A = decide_value(state_A, admission)               # -> PolicyDecision
    d_B = decide_value(state_B, admission)
    # decide_value, per candidate, using ONLY causal inputs:
    #   ev  = iso_mapper.predict(value_head_score)        # calibrated $ EV, standalone
    #   if state.asset_occupied:            DEFER "ASSET_OCCUPIED"
    #   if state.entries_used >= 12:        PASS  "PORTFOLIO_CAP_EXHAUSTED"
    #   if ev < admission.theta_usd:        DEFER "EV_BELOW_THRESHOLD"
    #   if wall_probability > 0.50
    #      or mae_q90 > $900
    #      or current_q20 < $0:             DEFER "ADMISSION_{WALL|ADVERSE|CURRENT_Q20}"
    #   else:                               ENTER, incremental_dollars_usd = ev
    # walk resolves the collision exactly as today (one slot, one asset):
    winner = max(enter_decisions, key=(ev, then candidate_id))   # twin :443-445
    loser.code = DEFER                                   # stays live next second (:450)
    walk.enter(winner)   # occupies asset until exit_ts_ns (:496-498); banks replay $
```

What the walk passes in: the existing `PortfolioDecisionState` (candidate/series/asset/side/clock, causal features, `ComponentPredictions`, entries_used, open positions, watch counts, phase, regime — `tabular_recovery_contracts.py:355-372`). What comes back: the existing `PolicyDecision(action, incremental_dollars_usd, lower_action_advantage_usd, reason)` (`:403-407`), with `incremental_dollars_usd = ev` so the frozen per-second best-per-asset ranking (`replay.py:344-368`) and the caps (`:371-379`) work unchanged. A deferred loser is re-decided at its next snapshot; nothing is consumed.

## (b) Interface

- **New `policy_mode="VALUE"`** beside `"ARGMIN"` and `"MARGIN"` in `tabular_policy` and the twin — exactly the slot A1's `decide_margin` already threads (`tabular_policy.py:90-99`, `tabular_walk_twin.py:429-435`). One function `decide_value(state, admission) -> PolicyDecision`; the theta rides in `admission.action_advantage_threshold_usd` as MARGIN mode does (A1 spec item 1, `design/A1_MARGIN_RULE_SPEC.md:26-35`).
- **Types/invariants:** EV must be finite (refusal otherwise, inherited from `PolicyDecision.__post_init__`, contracts:409-413); the mapper is order-preserving by construction (isotonic, `tabular_calibration.py:105`); ENTER requires all gates, so `reason` strings are total and disjoint; deterministic ordering everywhere is `(−EV, candidate_id)` — same tie law as today (`replay.py:355`).
- **Ordering:** strictly by arrival nanosecond; same-timestamp candidates compete, later ones cannot affect earlier decisions (`replay.py:296-299`).
- **Degenerate days / refusals:** a day with zero worthy candidates produces zero arrivals and a $0 asset-day in the denominator (sessions law, `replay.py:392-422`); a *block* with zero arrivals is a typed refusal (`EMPTY_ARRIVALS`, `replay.py:313-315`); a threshold bank whose most-permissive theta yields zero arrivals REFUSES with the EV distribution in the message — A1's engagement guard carried over verbatim (`A1_MARGIN_RULE_SPEC.md:50-53`). Nonfinite scores, schema drift, missing stack columns: existing refusals unchanged.

## (c) Label construction, exact

- **Primary target** `y = signed_pnl_usd` of the candidate row: the standalone net dollars of entering at that snapshot-second and exiting under the frozen convention. Source: the dense privileged outcome plane, `DelayedOutcomeShard.signed_pnl_usd` (`engine/entry_v2/tabular_delayed_corpus.py:97`), validated to satisfy `signed_pnl = wall_pnl` if wall-hit else `phase_close_pnl` (`:166-178`) — i.e. exactly what `ReplayOutcome.resolve` banks for that trade (`replay.py:63-77`). Costs are already inside (`frozen_cost_usd`, `cost_applied_count==1`, `:96,147`).
- **Auxiliary risk targets (already fit, kept):** `wall_hit` (Logloss), `mae_usd` (Quantile 0.9), `occupancy_sec = exit_ts − snapshot` (`exact_delayed_teacher.py:1043-1046`; heads at `tabular_models.py:428-433`).
- **Rows:** the existing sampled training-offset rows (offsets 0–60s by 5, 70–300s by 10 — `tabular_recovery_contracts.py:41-43`), i.e. the same 1,473,724 × 1,764 matrix plane already built (STATE.md "Durable pre-H2 tabular state"). Round-0 only; **no rollout/relabel rounds exist for this label** — it depends on no policy and no teacher schedule, so L4's curriculum decay (.684→.659, map:87-89) is structurally impossible.
- **Causal at training time:** features remain the frozen causal prefixes (the feature plane refuses outcome-shaped names at load, `tabular_delayed_corpus.py:4-6`); the label is future-measured outcome, used only as target — the same lawfulness as every supervised label in the chain. D-057 untouched.
- **Learnable — the SNR argument in numbers:** the old target was the day-DP substitution margin, $11–38, tick-quantized, >10% exact-$0 ties (map:122-127, 89-90). The standalone label, measured on six E1R training teacher days (read-only probe over `rehearsal/cache/teacher_days/*/202106*.npz`): per-day sd **$333–$963**, 43–47% positive, 2–18% of rows ≥ $600, q99 $800–$3,195. That is a **20–50× larger target scale**, with no cross-candidate coupling, no arbitrary tie-break to imitate, and tick quantization negligible at scale. The decision score is the trained quantity itself — not a difference of two separately-noisy regressions.

## (d) Objective + model shape

- **Primary (new, one head):** `CatBoostRegressor`, loss `RMSE`, single target `y/VALUE_SCALE_USD` (scale constant exists, contracts:28), frozen common params (depth 7, lr 0.04, ≤1500 iters, l2 12, early-stop 100 — contracts:226-232), sample weight `w = min(1 + |y|/600, 4)` — the tie/imbalance fix (L2/L3, map:127-130) turned into tail emphasis, since the value mass we must order lives in the top decile of series (probe: median per-series best $14–92 vs goal-grade tail $600–$3,000).
- **Reused:** the component MultiQuantile current/continuation/wall/adverse/occupancy heads exactly as fit today (`tabular_models.py:423-433`) — they feed the risk gates and the conservative variant.
- **Registered variant (same preregistered batch, zero new fits):** score = OOF `stack_current_q50` from the already-published round-0 bundles — the maximal-reuse arm that can be priced on frozen artifacts before any new fit (see (g), slice 0).
- **Deliberately NOT pairwise/listwise:** `PairLogitPairwise` is registered (`tabular_models.py:773`) but day-grouped pairwise training is measured anti-correlated with what pays in this repo's own record (JOURNAL.md:536: "day-grouped pairwise training actively ANTI-correlates... the recipe that climbs: regress day-relative dollars, not rank pairs"). Ranking-by-regression + monotone dollar map keeps order AND level.
- **Why defect #2 cannot recur:** M1 was three columns sharing one tree structure, with the DEFER column at corr −0.005 injecting noise into the decision margin (map:135-139). This head has **one output**; there is no DEFER column, no shared-tree coupling, and no subtraction of two model outputs anywhere in the decision path. The `max(0, expm1(...))` floor class (M2, `tabular_models.py:554`) is also gone — the mapper is isotonic on the raw score.

## (e) Decision rule — fully causal, every knob prior-block

ENTER iff all of, in order (see (a) pseudo-code):
1. asset free and portfolio seats remain (frozen laws, `common.py:57-58`);
2. **EV ≥ theta**, where `EV = MonotoneDollarCalibrator.predict(raw_score)` — mapper fit ONLY on the platt block (E1R: 20210712–20210720, contracts:90-91) with target = realized `signed_pnl_usd` of platt rows; theta = the existing selection law verbatim: 21 quantiles of the block's EV distribution, one multistate scan of the threshold block (20210721–20210806), weekly-LCB argmax under the full economic gate with the $1,500/$2,000 ladder floor (`tabular_calibration.py:565-597`, `tabular_evaluation.py:673-707`). Mean map is the default; `predict_lower` is licensed here as the conservative variant because the score is $-scale — precisely the C1 lesson (map:145-149: lower bounds reserved for $-scale EV heads);
3. risk gates at frozen defaults: wall ≤ 0.50, mae_q90 ≤ $900, current_q20 ≥ $0 (contracts:220-222).

**Concentration on few high-EV entries:** theta is the concentration knob and it is *selected against the gates that define "few and high"* — each theta row's threshold-block replay reports trades, $/trade (≥$600 law), MDD (<$1,000), and LCB; the law picks the feasible row with the best LCB. Measured structure says this lands where the user wants: 170–480 series/asset-day, of which only 13–129 have any second worth ≥$600 (probe on forward-block outcome sessions), and the teacher banks the ceiling with ~2–3 entries/asset-day (6–9/portfolio-day on probed days). A theta near calibrated $600 admits a handful of series a day by construction.

**Occupancy interaction:** entering blocks the asset through `exit_ts_ns` (twin :496-498; teacher semantics identical, `exact_delayed_teacher.py:770-774`), so a marginal early entry has a real opportunity cost the label deliberately does not carry. Priced in the rule, not the label: a second preregistered knob arm gates on `EV_rate = EV / max(occupancy_q50_sec, 600)` alongside theta, swept in the same multistate bank (occupancy head exists, contracts:33); adopted only if it beats the plain-theta arm's LCB on the threshold block. Prior-block selection, zero hindsight.

## (f) Reach argument — numbers

Forward ceilings/asset-day: HG $2,870 / NKD $2,052 / SI $2,066 (JOURNAL.md:696: $48,788.75/$34,882.50/$35,117.50 over 17 days). Ladder: HG $2,000 (=70% capture), NKD $1,500 (73%), SI $1,500 (73%).

Value-noise conversion, measured on the actual forward-block outcome plane (read-only, seeded 20260822, 40 trials/day; command in my transcript — rank series by `true best-second value + N(0,σ)`, take top-3/asset-day):

| σ (rms ranking noise, $) | HG $/a-d | NKD | SI | × timing retention (measured 0.85/0.90/0.80) |
|---|---|---|---|---|
| 0 (oracle) | 4,381 | 3,052 | 3,528 | — |
| 600 | 3,464 | 2,191 | 2,519 | **2,944 / 1,972 / 2,015 — clears ladder** |
| 800 | 3,143 | 1,940 | 2,242 | 2,672 / 1,746 / 1,794 — clears ladder |
| 1,200 | 2,485 | 1,479 | 1,802 | 2,112 / 1,331 / 1,441 — HG only |

Timing retention = mean-second/best-second value on goal-grade series (measured 0.80–0.90); realized timing sits between that floor and 1.0 because the score correlates within-series. Stated honestly: this plane ignores overlap and the 12-seat cap (optimistic) but also forbids re-entry compounding beyond 3 trades and takes zero credit for entries 4+ (pessimistic); it is a design-time bracket, and A1-style replay is the only authoritative dollar number (map:99-100).

**Where the current signal sits on this axis:** gap-AUC .659 on the $20 label ↔ d′≈0.58 on a ~$800 goal-grade gap ↔ σ≈$1,300 — the bottom row: HG passes, NKD/SI ~4–11% short. **The design needs σ ≤ ~$800, i.e. roughly halving ranking noise (≈AUC 0.75–0.78 equivalent).** Why this formulation plausibly buys it: three measured degradations are removed at once — the D-column noise injection (corr −0.005, map:136-137), the curriculum decay (.684 round-0 vs .659 round-2, map:87-89), and the tied tick-quantized $20 target (map:89-90) — and the target scale grows 20–50×. And critically, **the gap is measurable BEFORE any economics run**: the head's OOF per-series ranking noise on the platt block is the σ of this table (slice 1 below). If OOF σ lands above $900, the design reports "info-bound, Phase C fires" with the number, instead of burning a walk.

## (g) Three failure modes and the cheap slice that reveals each first

1. **The calibrated EV never separates the tail** (isotonic map flattens; theta bank degenerate; either zero entries — the old failure — or spray). *Slice 0 (hours, zero new fits):* rerun A1's machinery on the **published round-0 bundles** with score = OOF `stack_current_q50` instead of the margin — the maximal-reuse arm prices the entire hypothesis on frozen artifacts. *Slice 1 (minutes):* platt-block OOF decile table of score→realized dollars; require monotone lift with top-decile mean ≥ $300 and measure σ (per-series rank noise) against the (f) table before any walk.
2. **Within-series timing failure** — score is flat within a watch, entries land on the 0.80-retention floor or below, and NKD/SI miss by exactly the timing haircut. *Slice:* on the threshold-block walk trace, realized-entry-value / best-second-value per selected series, plus OOF corr(score_second, y_second) within series; if retention < 0.8, the registered fix is gating on `stack_continuation_q50` vs current (both already predicted, contracts:30-32) — enter when current ≥ continuation, still standalone quantities, still rule-side.
3. **Tail regime/side concentration** — top-decile EV lift carried by one regime or side that flips forward (this repo's B5 lesson: a tail edge that was substantially drift, JOURNAL.md:549). *Slice:* per-regime × per-side × per-asset decomposition of top-decile OOF lift on BOTH rehearsal transitions (E1R and E2R windows, contracts:90-93); weakest cell must stay positive, and the 5-shuffle arm bounds the mirage.

## (h) Eval plan — under the frozen judge, minimal diff

Unchanged: corpus/session algebra, candidate funnel, teacher as ceiling ruler, component fits, calibration/threshold/gate law, canonical replay, 5 real + 5 shuffle seeds, weakest-real-above-strongest-shuffle, both rehearsal transitions, preregistration before any fit. Changes (complete list):
1. `decide_value` + `policy_mode="VALUE"` threading (≈ the size of A1's MARGIN mode — `tabular_policy.py:90`, twin :429-435);
2. one `fit_value_head` (single-target RMSE) in `tabular_models` + red-first tests;
3. calibration-bank target switch: platt rows' realized `signed_pnl_usd` instead of teacher exact margins (same `fit_seed_calibration` shape, `tabular_evaluation.py:560`);
4. rollout/relabel machinery unused (`rollout_relabel_rounds` stays in the config for the old lane; the value lane consumes round-0 planes only).
Order: slices 0–1 → preregister → 10 seeds fit+calibrate → threshold bank (multistate, one scan/day) → forward opened once per seed at chosen theta → gates.

## (i) Cost arithmetic (D-109)

Anchors, all measured: 21-admission multistate scan = one walk for the whole bank at 11.62× (JOURNAL.md:689); heaviest day with teacher solving 786s — eval-only days are far lighter; GPU per-head fits seconds-scale on probe folds (`diagnostics/gpu_fit_determinism_20260821.json`: wall_s 2.4–4.2), full-fold minutes-scale; the full E1R chain — 3 rounds × 10 seeds of fits **plus rollout relabeling, the dominant cost** — fit inside D-103's 8–9h with the levers landed. This design: 10 seeds × (1 RMSE fit on the existing 1.47M×1,764 matrix [GPU, ≤~10 min worst-case each] + isotonic fit [seconds] + 13 threshold-block days + 17 forward days of multistate/plain scans). Fits ≤ ~1.7h serial on GPU; walks ~10×30 day-scans ≈ 1.5–3h at 2–3 seed-lanes wide, thread-pinned under 13.6 cores (HARDWARE.md). **Projected ≈ 3–4h < 6h.** Enforcement: slice-first — seed 1 end-to-end, project ×10 before continuing; R6 native features and the multistate walk are the named levers already landed; Quantile:0.9 stays CPU per the standing GPU_DEGENERATE receipt, and the bigfold probe precedes any new head's GPU routing (freeze-checklist guard, STATE.md FINDINGS).

## (j) What it deliberately does not do

- No DP, substitution, or scheduler quantity in any label (the constraint); opportunity cost is priced only by rule-side knobs selected on prior blocks.
- No imitation of the teacher's action sequence — teacher artifacts used only as ceiling ruler, component-target source, and evaluation (brief law; map Q-C).
- No joint multi-output head, no argmin converter, no lower-bound-of-small-margin thresholding (M1/C2/C1 all structurally absent).
- No rollout/curriculum relabeling; round-0 planes only.
- No pairwise/listwise within-day competition objective (rejected on this repo's own measurement, JOURNAL.md:536).
- No new features, no generator change, no exits/holds, no concurrency, no 2025H2, no goal lowering (standing law, map "Out of scope").
- No new evaluation machinery — the frozen replay/threshold/gate stack is the judge, untouched.

**Known cost of the constraint, named:** a standalone label cannot see that entering now forfeits a better overlapping candidate later; on the probed days that cost is bounded by the gap between the σ=0 row ($3,052–4,381) and the teacher's jointly-optimal ceiling ($2,052–2,870) — the hurdle and the occupancy-rate arm recover it only on average. That is the price of a label with 20–50× the SNR and zero coupling, and the ladder still clears at σ ≤ $800 with it fully paid.

# Candidate U (distribution/utility-first lane, verbatim) — landed 2026-08-22

All facts are pinned. Here is the complete package.

---

# Design lane U — DISTRIBUTION/UTILITY-FIRST entry selection ("DU")

All dollars below are exact-replay 1-mini dollars (`position_size_mini=1` enforced at `tabular_calibration.py:415`).

## Foundation audit first: the existing component quantile stack is dead weight — replace it, don't build on it

The brief asked whether the current_q20/q50, mae_q90, wall_probability heads are any good. Measured answer: **no signal at decision-relevant rows, in any seed, on any metric.** I joined the published round-0 OOF store (`.../fit_only/e1r/curriculum/fits/round_0/component_models/catboost/{real,shuffle}/seed_*/component_oof_all.npz` — 52,172 rows, which I verified are exactly the teacher action-row roster: 41,290 HIGH_VALUE_CONFLICT + 10,882 ORACLE_TRAJECTORY, 52,172/52,172 id-matched) to realized outcomes from the rehearsal teacher day npzs (`.../rehearsal/cache/teacher_days/*/2021*.npz`, field `current_entry_usd`), on the 14,817 rows covered by both. Regenerate: sort-merge `component_opportunity_id` → `opportunity_id`, compare `values` (already USD post-sinh, `tabular_models.py:260-276`) to `current_entry_usd`/`mae_usd`.

| Metric (at decision-relevant rows) | real seeds 20/21/22 | shuffle seeds 20/21 | random |
|---|---|---|---|
| P(y ≤ q20) / P(y ≤ q50) / P(y ≤ q80) (nominal .2/.5/.8) | .000 / .002 / .14–.18 | .000 / .001–.002 / .20 | — |
| P(mae ≤ adverse_q90) (nominal .9) | 1.000 | 1.000 | — |
| spearman(q50, y) | −.03 / −.05 / −.06 | **+.12 / +.10** | 0 |
| per-asset-day top-2-by-q50 capture | 64.8 / 65.4 / 62.0% | 63.0 / 60.6% | 57.2% |

The real models rank **no better than label-shuffled models** where it matters, and the "quantiles" are the unconditional candidate distribution (predicted q50 median −$41.5 vs the full matrix's median candidate −$55) pasted onto every row — vacuously wide adverse bounds included. Mechanism, sourced: the heads train on the full 1,473,724-row matrix whose population is 13.6% goal-grade (median y −$55, computed from `component_matrix/current_asinh.npy`), on an `asinh(y/600)` target (`tabular_recovery_contracts.py:28` VALUE_SCALE_USD=600) that compresses exactly the $600–$2,200 region we must order, with day-weights only (mean 1.0, `sample_weight.npy`; `tabular_training.py:143`) and shared-tree MultiQuantile (`tabular_models.py:823-836`). The pinball loss is spent on the mediocre mass. **What survives of the stack is its schema** — a censored outcome-distribution object per candidate is the right decision core — **and none of its fitted weights or its transform.** Clean replacement.

Signal does exist in the same features: the action head's E-D gap ranks at AUC .659±.009 real vs .480 shuffle (STATE.md:35), .684 with round-0 labels (map, nook batch item 1). The features are fine; the target, transform, weighting, and loss were wrong.

## (a) Caller's usage first — the walk at its busiest moment

Caller is unchanged: `replay_policy_day` / the multistate twin (`tabular_live_replay.py:294-301`, `tabular_walk_twin.py:617`), one scored batch per second. Busiest moment — second `t`, asset HG free, two live candidates, `entries_used=e`, realized day drawdown `D_t`:

```
# per second, inside the frozen chronological walk
states = [pipeline.score(snap) for snap in (c1, c2)]      # each carries an OutcomeDistribution
ranked = decide_simultaneous(states, admission_eu)         # same batch contract, EU as priority

# inside decide_eu(state, admission_eu, risk_state):
#   occupied            -> DEFER "ASSET_OCCUPIED"                     (unchanged slot)
#   entries_used >= 12  -> PASS  "PORTFOLIO_CAP_EXHAUSTED"            (unchanged slot)
#   p_wall > p_max                          -> DEFER "RISK_WALL"
#   mae_q90 > min(900, 1000 - D_t)          -> DEFER "RISK_MAE_BUDGET"  # MDD law as a live budget
#   value_q10 < q10_min                     -> DEFER "RISK_LEFT_TAIL"
#   EU = sum_k w_k*U(value_q[k]) - kappa*(R_HG(t) - R_HG(t + occ_q50))
#   EU < theta_HG                           -> DEFER "EU_BELOW_THRESHOLD"
#   else ENTER; two admitted at one second -> higher EU takes the one asset seat,
#   loser DEFERs "SIMULTANEOUS_PORTFOLIO_RANK" and stays live         (tabular_policy.py:243-257)
```

Return type unchanged: `RankedDecision(state, PolicyDecision(action, eu_usd, value_q10, reason))` (`tabular_policy.py:219-222`). A DEFER costs nothing — the candidate is re-scored next second while its watch lives, so "wait for a better second" needs no extra machinery.

## (b) Interface

**`OutcomeDistribution`** (replaces the prediction payload inside `ComponentPredictions`, `tabular_recovery_contracts.py:30-32`): `value_q: (q10,q30,q50,q70,q90)` USD ascending (sorted at predict, as today `tabular_models.py:260-274`), `wall_probability ∈ [0,1]`, `mae_q90_usd > 0`, `occupancy_q50_sec > 0`. Invariants: all finite or `RecoveryRefusal`; monotone quantiles; schema-name bump (COMPONENT_PREDICTION_NAMES changes → new bundle/OOF schema strings, strict-reload receipts regenerate — checking-data-contracts moment, flagged).

**`SuffixCeilingCurve`**: per asset, 30-minute buckets, `R_a(t)` = mean over prior-block days of the exact-delayed suffix ceiling from `t` to close. Computed from closed-block teacher days only — the teacher used strictly as the ceiling ruler, which the brief permits (brief:33-35). Published with a receipt; frozen per transition.

**Knobs** `Θ = (γ, κ, p_max, q10_min, θ_SI, θ_HG, θ_NKD)` live in the existing `AdmissionContract` shape (`tabular_calibration.py:380-398` — `action_advantage_threshold_usd` slot carries θ; `maximum_wall_probability`, `maximum_adverse_q90_usd`, `minimum_current_q20_usd` carry the other three; γ, κ ride the calibration bundle). Ordering/batch invariants of `decide_simultaneous` kept verbatim (`tabular_policy.py:229-236`).

**Degenerate days**: all-DEFER is a lawful walk output (`EntryEvaluation.zero_asset_days`, `contracts.py:360`). Systematic refusal is caught earlier and hard: the threshold bank MUST show ≥1 entry on ≥80% of eligible asset-days and ≥`MIN_TRADES`=10 trades/block at the selected θ (`ThresholdFeasibility` already carries these fields, `capacity_contract.py:18-27`); an infeasible bank halts the run — never a fall-to-most-permissive (the E1R selector "found NO feasible theta and fell to most-permissive, still 0", STATE.md:35, is the outlawed anti-pattern).

**Error modes**: every refusal is a named reason string (list in (a)); malformed inputs refuse loudly with offending value, per house contract style.

## (c) Label construction, exact

| Target | Source field | Scale | Causality at training |
|---|---|---|---|
| `y` terminal trade PnL | `current_entry_usd` = `signed_pnl_cents/100` of the universe row (`exact_delayed_teacher.py:1024,1040`) — enter this second, exit by the frozen rule: $900 adverse wall (`common.py:59`; wall rows have `signed_pnl == wall_pnl`, `tabular_delayed_corpus.py:166-178`) or phase close | p5..p95 = −$905..+$1,108, p99 $2,220 (full matrix) | pure market outcome, fully realized inside the day; trained only on closed blocks |
| `mae_usd` | teacher npz / matrix `adverse_usd` | 0..$1,718 | same |
| `wall_target` | `universe.wall_hit` (`exact_delayed_teacher.py:1043`) | ~10%/day base rate | same |
| `occupancy_sec` | `exit_ts − snapshot_ts` (`:1045-1046`) | p10/50/90 = 2,543/13,962/27,384 s | same |

No DP anywhere in the labels: no `q_*` state values, no substitution margin, no curriculum relabeling (L4 moot — labels cannot depend on any policy), no ties (continuous dollars).

**SNR argument, numbers**: the old target was the DP's substitution margin — $11–38, tick-quantized, >10% exact-tie rows (map L1/L2) — conditional signal O($20) against outcome noise O($500): SNR ≈ 0.04. The standalone-value target's decision-relevant spread is the within-asset-day gap between best and average candidates: oracle top-2 $2,837 vs random-2 $1,624 per asset-day (measured above) ≈ $600/trade of orderable conditional value against the same noise: SNR ≈ 1.2 — thirty times the failed target. The model does not need to price y to ±$50; it needs to order the top of the day, which is where the relevance weighting (d) puts the loss.

## (d) Objective and model shape

8 single-target fits per (seed, fold), pooled across assets (pooled>per-asset is a closed atlas verdict, commit b790f08), same 1,764-feature matrix and roster (receipt `7e9e2588…`, `component_matrix/manifest.json`):

- **5 value heads**: `Quantile:alpha=τ`, τ ∈ {.10,.30,.50,.70,.90}, target y in **dollars**, clipped to [−950, +3600] (wall already censors the left tail near −$900; right clip = p99.5 for pinball stability). No asinh — the compression defect is deleted, not patched.
- **wall**: Logloss (GPU-clean, `gpu_fit_determinism_20260821.json`).
- **mae_q90**: `Quantile:alpha=0.9` (CPU — GPU quantile is pre-registered degenerate on big folds, STATE.md:7).
- **occ_q50**: `Quantile:alpha=0.5`.
- **Weights**: value heads get `w = day_weight × (1 + max(y,0)/600)` — pinball capacity shifted onto the goal-grade region the audit shows the old fit ignored. Wall/mae/occ keep day-weights only (their gates need unconditional calibration).

**Why defect #2 cannot reproduce**: there is no joint multi-column head over semantically different outputs — every fit has one target; and no DEFER-value column exists anywhere in the system, so no noise column can be subtracted into a decision score. The MultiRMSE/MultiQuantile shared-tree coupling (M1 family, `tabular_models.py:696-700, 823-836`) is structurally absent.

## (e) Decision rule — fully causal, and where every knob comes from

`U(y) = y` for y ≥ 0, `(1+γ)·y` for y < 0. `EU_raw = Σ_k ω_k U(q_τk)` (ω = interval masses of the τ-lattice; the left mass splits into `p_wall·U(−900) + (0.2−p_wall)⁺·U(q10)` so the wall censor point carries its own predicted mass). Opportunity charge `C_opp = κ·[R_a(t) − R_a(t + occ_q50)]` — entering consumes ~3.9 h of asset seat (median occupancy 13,962 s), and this term is what replaces the DP's Q_defer with a stable prior-block mean instead of a $20 per-second noise label. ENTER iff all risk gates pass and `EU_raw − C_opp ≥ θ_a`.

Knob provenance (nothing sees the evaluation block):

| Knob | Selected on | Mechanism |
|---|---|---|
| γ ∈ {0,.5,1}, κ ∈ {0,.5,1} | platt block | preregistered 9-cell grid, scored by replay dollars + MDD |
| θ_a (per asset) | threshold block | the existing 21-quantile threshold bank, unchanged machinery (`select_seed_threshold`, `tabular_calibration.py:673`; multistate walk prices all 21 in one scan) |
| p_max ∈ {.25,.4}, q10_min ∈ {−900,−600} | threshold block | folded into the same bank sweep |
| R_a(t) curve | training block | teacher suffix ceilings, closed blocks only |

**Concentration**: θ_a is selected under the bank's feasibility law with the trade-count band 2–4/asset-day (teacher enters 3.0/asset-day at mean $711–982/trade — computed from `selected_opportunity_ids` joined to outcomes; 30–52% of teacher trades are individually < $600, so the $600 law is enforced where it lives: on the block average, `campaign.py:871-872`). **One-position interaction**: occupancy makes ~3 sequential entries the physical maximum; the EU charge makes early mediocre entries expensive when `R_a` is still high and free when the day is nearly spent; the MDD term `min(900, 1000 − D_t)` tightens the adverse gate as the day's drawdown accumulates — the MDD<$1,000 law (`common.py:72`, gate at `capacity_contract.py:92`, breach rate defined at `replay.py:286,447`) enforced live rather than hoped-for.

## (f) Reach argument

Targets (user ladder): HG $2,000/asset-day = 70% of forward ceiling $2,870; NKD and SI $1,500 = 73% of $2,052/$2,066 (brief:30; map round-2 ruling).

1. Ordering-grade signal in these features is proven: gap AUC .659–.684 real vs .480 shuffle, seed-stable (STATE.md:35).
2. The A2 receipt (`diagnostics/e1r_required_auc_curve.json`, `you_are_here_oof_gap_usd_per_asset_day` vs `seeds[0].ceiling_usd_per_asset_day`) shows that same signal under a capacity-matched rank rule prices HG $2,722 / NKD $1,576 / SI $669 per asset-day on the training block = **93.9 / 85.5 / 83.1%** of that block's ceilings ($2,898/$1,842/$805) — versus $0 through the argmin converter. The binding defect was the decision object.
3. The EU rule at the 2–4-entries/asset-day operating point is that rank rule, made causal (θ from the bank) with risk and occupancy priced. Arithmetic of required improvement: random-K captures 57% (measured); the ladder needs 70–73%; the demonstrated signal grade added 26–37 points over random in-sample-additive; the design needs 13–16. Slack: 10–20 points to absorb (i) additive-pricing optimism (map ~08:50Z correction: A1's replay is the only authoritative dollar) and (ii) OOS decay.
4. What it needs from the new value heads: not the gap head's job — only that top-of-day ordering on the value target reaches roughly the same grade. Preregistered floor at the pilot (g-1): fold-OOF per-asset-day top-2 capture ≥70% real (shuffle sits at 60.6–63.0%, random 57.2%). If the value target cannot reach the floor, the design fails at the pilot for ~1 hour of box time, not at a full run — and the fallback is not a hedge into the dead action head; it is a verdict that the standalone-value formulation is information-short, which feeds Q-B honestly.

## (g) Three most likely failure modes, each with a cheap pre-run slice test

1. **Value-head ordering collapses OOS the way the audited stack did** (relevance weighting insufficient against the 86% mediocre mass). Slice: one fold, 1 real + 1 shuffle seed, 5 value heads, score the frozen 52,172-row action roster, apply the (f-4) bar plus spearman(EU, y) at ORACLE_TRAJECTORY rows ≥ +0.15 (measured shuffle: +0.12). ~1 h.
2. **First-crossing sequencing leak**: θ-crossing admits the 09:35 adequate candidate; its ~4 h hold occupies the seat through the day's best candidate; κ·R_a mis-charges it (worst where ceilings shift regime — SI's June dead zone, $805/d training vs $2,066 forward, map ~08:50Z). Slice: 10 threshold-block days, multistate walk EU rule vs same-day additive top-K pricing; walk capture more than 15 points under additive capture indicts sequencing → raise the κ grid and enable the single within-watch wait rule (defer when predicted continuation q50 exceeds current EU by >$50 — the continuation head exists in the matrix, `continuation_asinh.npy`, retrained under (d) rules). ~30 min.
3. **Degenerate refusal — the E1R $0 shape** (risk gates ∧ θ jointly refuse everything, or the bank is infeasible). Slice: the bank feasibility law in (b) runs at threshold selection, before any forward walk, and an infeasible bank is a hard FAIL, never a permissive fallback. ~0 extra cost — it is the selection step itself, with the gate direction inverted from E1R's.

## (h) Eval plan under the frozen machinery

5 real + 5 shuffle seeds, exact chronological replay dollars, existing gates — all byte-frozen: `EntryEvaluation`, ceilings, capture, MDD/trade/coverage laws (`campaign.py:857-886`, `capacity_contract.py`), threshold bank, trace store. Changes, smallest set: (1) `policy_mode="EU"` beside ARGMIN/MARGIN — the conditional core-key pattern already preserves every stored trace hash (`tabular_live_replay.py:46-54`); (2) `decide_eu` beside `decide`/`decide_margin` in `tabular_policy.py`; (3) the prediction-row schema bump in (b) with regenerated strict-reload receipts; (4) one new small frozen artifact, the `SuffixCeilingCurve` + receipt; (5) day-drawdown `D_t` read from walk state the twin already tracks per machine. The action model, its calibration mapper, and the argmin stage leave the decision path entirely (they may stay as a diagnostic lane).

## (i) Cost arithmetic (measured rates, D-109)

Reusable as-is: 67 E1R day stores, the 1,473,724×1,764 matrix, teacher days, dense store (STATE.md "Durable pre-H2" block) — $0 rebuild. New fit work per E1R-shaped transition: 8 heads × 6 folds × 10 seeds = **480 fits**, of which 300 are quantile heads. Measured anchors: GPU head fits 2.4–4.2 s wall on E1R folds (`gpu_fit_determinism_20260821.json` `wall_s`); GPU Quantile pre-registered degenerate on big folds → CPU (STATE.md:7); one CPU fit saturates the 13.6-core box (HARDWARE truth), so CPU quantile fits are serial. At an assumed 4 min/CPU-quantile fit the quantile block alone is ~20 h — **over the 6 h cap**, so the launch shape is slice-first: the (g-1) pilot measures the true per-fit rate, and the pre-named speed levers apply in order (D-109-amendment: speed, never scope): (1) route quantile heads to **xgboost GPU** — the backend is already registered with per-alpha quantile regressors (`tabular_fallbacks.py:315` `_xgb_reg`), the brief names it as a lever, and at ~1 min/fit the block is ~5 h → with the 180 GPU-seconds heads, total fits ≈ 1.5–2 h under the artifact-pin determinism standard (STATE.md R1 ruling); (2) if still over, return to the user with the arithmetic before running. Walks: EU adds a dot product over 8 floats per row — cost unchanged; the multistate 21-admission scan (11.62×, STATE.md:7) and the 142 CPU-s worst-day eval walk (`FABLE5_SPEED_RESULT.md:15`) put threshold + evaluation walks at ~2–3 h. Projected transition total ≈ 4–5 h plus the 1 h pilot gate in front.

## (j) What this design deliberately does not do

No imitation of the teacher's action sequence and no substitution-margin target anywhere (Q-C hedged by construction). No learned ENTER/DEFER/PASS head. No exit/hold changes — the frozen exit rule is the label's definition. No per-asset models, no position concurrency, no candidate-generator changes, no 2025H2, no neural. No portfolio-level utility coupling beyond the existing 12-cap competition. No within-day adaptation of any knob — Θ is frozen per transition. The continuation micro-timing rule ships only if slice (g-2) indicts sequencing; it is not in the base spec.

---

**Losing alternative considered** (designing-it-twice): repairing the existing stack in place — keep MultiQuantile, add weighting, keep asinh. Rejected on the audit: the failure is not one defect but three compounding ones (population, transform, shared trees), and a repair cannot be attributed if it half-works; the replacement changes each named defect with a preregistered ablation path (weighting on/off is one grid arm). Second alternative — full distributional model (NGBoost-style) — rejected: unregistered engine, no GPU/determinism story, and a 5-point quantile lattice is exact enough for a piecewise-linear U.

**Open risk to flag at synthesis**: `R_a(t)` uses teacher suffix ceilings from closed blocks. I read brief:33-35 ("teacher/DP may be used ONLY as the ceiling ruler and for evaluation") as permitting this — it is the ceiling ruler marginalized by start time on prior blocks, not action imitation — but the synthesis should confirm that reading, and the κ=0 grid arm is the lawful fallback if not.

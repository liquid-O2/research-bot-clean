# Candidate R (rank-first lane, verbatim) — landed 2026-08-22

# Design lane R — RANK-FIRST entry selection ("Anchored Within-Day Rank", AWR)

The trained object is one pairwise ranking score over candidates, trained only on within-(day, asset) orderings of realized entry dollars, with a per-group synthetic **$600 anchor row** that pins a learned zero point so the score transfers across days. No dollar regression exists anywhere in the trained object. Dollars enter twice, both lawfully: as pair weights/deadbands during label construction, and as the prior-block replay-dollar selection of the decision knobs (theta, per-asset-day cap). The central problem the brief names — a within-day-comparable score consumed by a sequential causal walk — is solved by three mechanisms working together: the trained anchor (cross-day zero), prior-block quantile theta (cross-block operating point), and a per-asset-day entry cap (bounds score-inflation days). Everything downstream of the score reuses the frozen walk/replay/gate machinery.

---

## (a) CALLER'S USAGE FIRST — the walk's call site at the busiest moment

The only caller is the chronological walk (`tabular_walk_twin.py:518-549` `_wtwin_walk`, differential twin of `tabular_live_replay.replay_policy_day:294`). AWR's key property: the score is **state-free** (candidate + market context only, no portfolio-state features), so the whole day is scored once before the walk, exactly the way the component predictions already are (`tabular_walk_twin.py:295` — `components = component_model.predict(features)` for the full day plane in one call).

```
# Once per day, before the per-second loop (mirrors twin plane build :257-322):
plane      = build_day_plane(dense_feature_shards, feature_schema)   # frozen
score      = ranker.score(plane.features)          # ONE batch predict, float64[n_rows]
z          = score - ranker.anchor_score[plane.asset_index]          # anchored score
# z is the walk's priority AND its threshold statistic. No CatBoost call
# occurs inside the per-second loop at all.

# Busiest moment: timestamp t, HG has one free slot, two live HG candidates
# c1 (z=+2.1) and c2 (z=+1.4), theta=+0.8, per-asset-day cap K_A=3, 1 HG entry used:
for now, rows in plane.by_timestamp:                                  # :520
    rows = rows[~machine.blocked[...]]                                # :528  PASS/entered series gone
    occupied = causal_open[asset_idx[rows]] >= now                    # :428  one-position law
    codes = ENTER where (z[rows] >= theta) & risk_gates & ~occupied
            & (asset_entries_today[asset] < K_A)                     # AWR rule (mirrors :132-141)
    ranked, chosen = wtwin_rank_entries(codes, priority=z[rows], ...) # :144-159
    # -> both c1,c2 code ENTER; best-per-asset keeps c1 (higher z);   # :150-154
    #    c2 is demoted to DEFER ("SIMULTANEOUS" path, :450) and its watch stays live —
    #    if HG's position exits before c2's watch expires, c2 can still enter later.
    # ENTER consumes the series, occupies HG until causal phase close # :492-498
```

What comes back per day: the frozen `PolicyDayTrace` (arrivals with `EntryScore.priority_score = z`, selected ids, crossings) — unchanged schema (`tabular_walk_twin.py:552-594`) — feeding the unchanged canonical `replay()` (`replay.py:291`).

## (b) INTERFACE

**New object — `EntryRankerBundle`** (shape mirrors `ActionModelBundle`, `tabular_models.py:495-545`):
- `feature_names: tuple[str,...]` — the **causal candidate features + component-stack OOF columns** only. Invariant, checked at every predict: no portfolio-state column (`entries_used`, `open_until`, active-watch counts) may appear; this is the structural guarantee that scores are state-free and precomputable.
- `model: CatBoostRanker`, `objective == "PairLogitPairwise"` (already in the registered whitelist, `tabular_models.py:511`; ranker strict-load already exists, `:623-625`).
- `anchor_vector: float32[n_features]` per asset (train-fold per-asset median feature profile) and `anchor_score: float64[3]` = `model.predict(anchor_vector)` computed at fit time and stored in the manifest. Invariant on strict reload: recomputed anchor score must equal the stored one (same pattern as the restart probe, `tabular_policy.py:321-326`).
- `score(x) -> float64[n]`; the decision statistic is `z = score − anchor_score[asset]`.
- Receipts: config/seed/train/validation/pair-census sha256 fields, same manifest discipline as `:571-605`.

**Walk mode** — `policy_mode="RANK"`, mirroring `"MARGIN"` which already threads through the twin (`tabular_walk_twin.py:120-141, 429-435`) and `decide_margin` (`tabular_policy.py:91-127`): ENTER iff `z >= theta` AND risk gates (wall ≤ max, mae_q90 ≤ max — same `AdmissionContract` slots) AND asset free AND portfolio cap AND the one new counter, per-asset-day entries `< K_A`. Ordering: priority is `z`; exact tie-break candidate_id (`:151-157`, unchanged).

**Degenerate days / error modes:**
- Zero worthy candidates: all `z < theta` → 0 entries → a lawful $0 asset-day, counted in the denominator (A1 denominator law, `design/A1_MARGIN_RULE_SPEC.md:15-16`); the trace still publishes via the rejected-fallback arrival (`tabular_walk_twin.py:554-556`), so `replay()`'s typed `EMPTY_ARRIVALS` refusal (`replay.py:308-315`) never fires on a real day.
- Feature-schema drift, non-finite features, universe mismatch: refuse (existing patterns `tabular_walk_twin.py:277-283, 365-370`).
- Whole selection block yields zero arrivals at the most permissive theta: **loud refusal carrying the z distribution**, never a silent $0 row (A1 spec item 4, `A1_MARGIN_RULE_SPEC.md:50-53` — this is the exact old failure mode).
- Anchor score non-finite or outside the train-fold z-range: refuse at fit publication.

## (c) LABEL CONSTRUCTION, EXACT

**Target: none, as a value.** The trained object learns only **orderings**. The ordering is built from `signed_pnl_cents` — the realized dollars of entering that candidate at that snapshot second under the frozen exit law (earliest of close / phase close / $900 wall — `replay.py:63-77`), carried per snapshot in the dense outcome plane (`exact_delayed_teacher.py:162, 198-199`; "dense 301-second outcome plane", `:383-385`). Rows are the registered training grid offsets (0–60s by 5, 70–300 by 10, 330–600 by 30 — `confirmation.py:71-81`), i.e. the same plane the component matrix uses (~16.6k rows/day: 1,473,724 rows / 89 teacher days, STATE.md durable-state block).

**Pairs, all within one `(trading_day, asset)` group** (CatBoost group_id), four preregistered types with a fixed budget:
1. **Winner-vs-junk** (~50%): rows with value ≥ $300 vs rows ≤ $0, weight ∝ dollar gap (the existing pattern: `tabular_models.py:736-737` weights pairs by `difference/(VALUE_SCALE_USD*100)`). This is precision-at-the-top, which is where the dollars are.
2. **Winner-vs-winner** (~30%): different series, gap ≥ $100 deadband.
3. **Within-series timing** (~10%): two snapshots of the same watch, gap ≥ $100 — teaches which second of a watch to prefer.
4. **Anchor pairs** (~10%): every row vs the group's synthetic anchor row; row wins iff value > $600 (`C.MIN_EXPECTANCY_USD`, `common.py:60`), weight ∝ |value − 600|, deadband $50.

**Causality at training time:** features are the D-057-causal decision-time features (dense day stores) plus the already-published chronological component OOF stack (`brief:38-40` — quantile stack "today used only as features"); labels use the future, which is lawful for label construction on completed historical days; the anchor vector is computed from train-fold features only. No teacher DP field is consumed: `q_*`/regrets/`selected_series_ids` are never read (they are day-DP state values — the exact trap the brief flags). The MILP teacher remains the ceiling ruler only.

**Why LEARNABLE (SNR vs the $20 margin failure):** the old target was `Q_enter − Q_defer` of the day-suffix DP — $11–38, tick-quantized, >10% exact-$0 ties (map L1/L2, `ENTRY_SELECTION_MAP.md:122-131, 88-90`; source `exact_delayed_teacher.py:780-798`). AWR's orderings are built on standalone values at the $400–700 winner scale (brief diagnosis #1; teacher ceiling/trade HG $692 / NKD $461 / SI $429, map:100-102) — the discriminative gaps are 10–50× the old label scale. The deadbands delete the tie mass entirely (no pair is emitted for a tie, so no arbitrary tie-break is imitated — fixes L2), pair weights ∝ dollar gap implement margin weighting (fixes L1/L3), and there is **no rollout relabeling round at all** (fixes L4: curriculum measured to hurt, .684 → .659, map:86-88).

## (d) OBJECTIVE + MODEL SHAPE

One `CatBoostRanker`, `loss_function="PairLogitPairwise"` (registered objective, `tabular_models.py:511`; fit machinery pattern at `:762-788`, explicit `pairs` + `pairs_weight` Pool at `:751-753`), single scalar output, group_id = (day, asset), frozen HP family from `RecoveryConfig` (`_common_parameters`, `:83-97`), D-105 GPU overlay per loss (`:114-123`), 5 real + 5 shuffle seeds. The shuffle arm permutes **values within (asset, day) before pair construction** (`_within_asset_day_permutation`, `tabular_training.py:558`, exactly the matched-shuffle discipline of `:589`), preserving group sizes and the pair-type budget.

**Why defect #2 cannot recur:** M1 was three targets (E/D/P regrets) forced through one shared tree structure, with the DEFER column measured at corr −0.005 — pure noise subtracted into the decision margin (map M1, `ENTRY_SELECTION_MAP.md:135-139`; source `tabular_models.py:696-700`). AWR has **one output and zero DEFER/PASS supervision anywhere**: DEFER/PASS are outcomes of the decision rule, not learned classes. There is no second column to leak noise from, and no inverse dollar transform whose floor could distort ranks (M2's `expm1` floor at `:554` has no counterpart — the score is consumed as an ordinal with one learned reference point).

## (e) DECISION RULE — fully causal

At each second, for each live unblocked candidate: **ENTER iff all of**
1. `z = s(x) − s_anchor(asset) ≥ theta(asset)` — theta chosen **only on the prior threshold block**: the 21-row quantile bank of the threshold block's z distribution, swept by the frozen multistate walk, operating point picked by the existing selection law against the goal ladder ($1,500-floor arm binding) — byte-for-byte the A1 knob-provenance discipline (`A1_MARGIN_RULE_SPEC.md:13-15, 42-46`; multistate machinery `tabular_walk_twin.py:617-648`).
2. Risk gates from the component stack (wall probability, mae_q90 — the `decide_margin` admission slots, `tabular_policy.py:115-121`), each selectable to "off" on the threshold block.
3. Asset seat free (one position per asset — occupancy until causal phase close, `tabular_walk_twin.py:496-498, 528-535`; law `common.py:51-58`).
4. Portfolio cap 12 and **per-asset-day cap `K_A ∈ {2,3,4,12}`** — the one new knob, also selected on the threshold block jointly with theta (21×4 = 84 admission rows in one multistate pass).

**How it concentrates on few high-EV entries:** theta is a top-quantile cut (teacher enters ~2–4/asset-day against ~460 scored rows/asset-day — map C3 `:150-151`, F1 `:154` — so the operating quantile is ~99%); simultaneous candidates compete for the seat by z, best-per-asset (`tabular_walk_twin.py:144-159`); `K_A` caps flood days. **Occupancy interaction:** entering greedily above theta forfeits only candidates arriving while the seat is held; sequential re-entry is unlimited (`common.py:52-57`), and A6's direction says delay forfeits dollars (map:113-117), so first-crossing entry is the right default; the measured DP substitution margins ($11–38 between the chosen entry and its next-best alternative, map:97-100) bound how much any near-optimal-value schedule can lose to greedy sequencing — the alternatives are nearly interchangeable in total dollars, which is precisely why ordering by standalone value is enough.

**Within-day-comparability, addressed head on:** the pairwise objective constrains only within-group order, so nothing in the loss pins cross-day score levels — that is the failure channel for any fixed theta. AWR closes it three ways: (i) the anchor row appears in every group with the same feature vector, so the fitted function is pressed, group after group, to place "worth $600" at one global score — the zero point is *trained in*; (ii) theta is a quantile of the threshold block's pooled z, per asset, chosen by replay dollars, so residual level drift between train and threshold blocks is absorbed by the knob selection; (iii) `K_A` bounds the damage of a day whose scores all inflate. The preregistered batch carries a forced-different second variant — **no anchor, pure quantile theta** — so the anchor's contribution is measured, not assumed (map:158-159: one design-it-twice batch, not four).

## (f) REACH ARGUMENT — numbers

- The converter is the proven first bottleneck, and a rank rule already recovers the band **with the old noisy head**: the existing OOF E−D gap head under a capacity-matched rank rule prices HG $2,721.6 / NKD $1,575.6 / SI $668.8 per asset-day in-sample vs exact training-block ceilings $2,898.4 / $1,842.2 / $804.8 = **93.9% / 85.5% / 83.1% capture** (receipt `artifacts/entry_v2/tabular_recovery/diagnostics/e1r_required_auc_curve.json`, `you_are_here_oof_gap_usd_per_asset_day` and seed ceilings; map:82-83), against a target of 73–80% (brief:56; $1,500 = ~73% of forward SI/NKD ceilings, map:74-77).
- The A2 curve shows dollars are insensitive to *global* AUC in this regime (HG $2,389→$2,464 from AUC .659→.80; same receipt) — top-of-list precision carries the money. AWR's loss mass sits exactly there: pair weights ∝ dollar gaps concentrate gradient on separating the ~1% goal-grade tail from the rest, not on ordering junk.
- Signal exists and is seed-stable at the level the converter needs: gap AUC .659±.009 real vs .480±.018 shuffle, weakest real .646 > strongest shuffle .513 (STATE.md E1R verdict; map:26) — achieved against the $11–38 tick-quantized substitution target. AWR retrains the same features (disc_auction 22%, regime 8.6%, w1800 7.6%, memory 5.4%, stack 5.1% — map:90-92) against orderings whose gaps are 10–50× larger; round-0-grade signal (.684, map:86-88) is the floor expectation, since the curriculum that degraded it is deleted.
- What must hold: the 83–94% in-sample capture must not decay more than ~10–20 points out-of-sample. That transfer is exactly what A1 measures for the old head and what this design's own threshold→forward protocol measures for AWR; nothing here is inferred from classification metrics — the gate is replay dollars (mandatory rule 8).
- SI is judged on threshold/forward blocks ($2,735 / $2,066 ceilings), not the June-dead training block ($805) — map:94-96.

## (g) FAILURE MODES + cheap slice tests (before any full run)

1. **Cross-block z-level drift despite the anchor** → theta chosen on threshold block floods or starves forward. Slice: score threshold + forward blocks with the seed-1 ranker (two batch predicts, minutes); compare per-asset z-quantile curves and the arrival count at the chosen theta; refuse fan-out if forward occupancy at theta differs >2× from threshold-block occupancy.
2. **Sequential (greedy-above-theta) loss**: early mediocre entry occupies the seat past a later winner. Slice: on the training block, using OOF z only, price (frozen funnel/caps) greedy-theta dollars vs hindsight top-K-by-z dollars per asset-day. Gap >20% of top-K dollars ⇒ the sequencing, not the ranking, is the binding loss → escalate the two-stage variant (enter only if z also clears the causal running-day q80) before spending seeds.
3. **Wall-pair domination**: −$900 wall rows create $1,500+ gaps that swallow the pair budget; the ranker becomes a wall-avoider that cannot order winners. Slice: fit one seed on 4 days; report the pair-census (weight mass by pair type — a mandatory fit receipt) and two OOF stats: winners-vs-junk AUC and Kendall tau among winners only. Winner-tau ≈ 0 with high AUC ⇒ rebalance the type budget / cap single-pair weight.

## (h) EVAL PLAN under the frozen machinery

Per seed (5 real + 5 shuffle, frozen seed lists — `RecoveryConfig`): fit ranker on the training block → 84-machine multistate RANK walk over the threshold block (~13 days) → pick (theta, K_A, gates) by the existing selection law on the ladder → one forward walk (~14 days) at the chosen knobs → unchanged canonical `replay()` and gates: $2,000/$1,500 ladder, ≥80% (73% where $1,500 binds) of the exact ceiling, $600/trade, MDD<$1,000, weakest-real > strongest-shuffle (brief:14-19; map:10-14). Preregistered before launch (headline = forward replay dollars at the pre-chosen knobs; matched shuffle through the identical procedure).

**Wiring deltas (small):** (1) new pair-pool builder + `EntryRankerBundle` fit/load (one module; reuses `_pairwise_pool`'s Pool/pairs/weights pattern, `tabular_models.py:726-759`); (2) `policy_mode="RANK"` threaded exactly as `"MARGIN"` already is (`tabular_walk_twin.py:269-270, 429-435`; `tabular_policy.py:91-127`); (3) one per-asset-day entry counter on the walk machine + one `K_A` field on the admission row; (4) selection law reads z. **Unchanged:** candidate generator, dense stores, component heads + published OOF stack, teacher (ceiling ruler), replay, gates, trace/receipt schemas, 2025H2 seal.

## (i) COST ARITHMETIC (D-109: 6h, named levers)

- **Fits:** 10 ranker fits (5+5), input ~265k rows × ~1.8k features (16 days × ~16.6k rows/day), ~2–3M sampled pairs. No component refits (stack reused), no rollout rounds (deleted). Levers: R6 native features (landed), D-105 GPU overlay for the ranker loss (one GPU fit at a time, `design/FIT_BACKEND_SWAP_SPEC.md:338-341`), thread_count=16 within the 13.6-core truth. Budgeted 10–30 min/fit ⇒ 1.7–5h sequential; **rate confirmed at seed 1 before fan-out** (the A1 spec's own rule, `A1_MARGIN_RULE_SPEC.md:60-65`); if projection >6h, split CPU fits 2-wide (8+8 threads) — never trim seeds/blocks.
- **Walks:** state-free scoring makes the multistate walk almost pure numpy — per day, exactly two batch predicts (component plane, already the pattern at `tabular_walk_twin.py:295`, + one ranker predict), then 84 machines share every score with no per-state CatBoost dispatch (the current walk re-dispatches per shared state key, `:542-545`; RANK's state key drops entries/open/counts entirely). Strictly cheaper per machine-day than A1's walk, which was itself budgeted inside 6h at 21 states × 10 seed-lanes (`A1_MARGIN_RULE_SPEC.md:61-65`). Threshold 13 days + forward 14 days × 10 lanes fits in well under an hour of walk time; theta-trace caching (`wtwin_load_or_replay_day_multistate`, `:682-747`) makes reruns free.
- **Slices (g1–g3):** < 30 min total, all before the fan-out.

## (j) WHAT IT DELIBERATELY DOES NOT DO

- No dollar regression, no calibrated dollar mapper, no q20 lower bound of anything — the C1 all-negative-bank channel (isotonic + n/(n+200) group shrinkage, `tabular_calibration.py:109, 157-169`; map:144-148) is removed, not fixed.
- No DEFER/PASS supervision, no argmin converter (C2), no imitation of the teacher's action sequence, no reading of `q_*`/regret/selected fields.
- No rollout relabeling/curriculum (L4), no per-asset models (pooled, per the atlas verdict), no cross-day or cross-asset ranking groups (cross-asset composition is the walk's job, cross-day calibration is the anchor+theta's job).
- No exits/holds, no position concurrency, no candidate-generator or funnel change, no new CatBoost objective outside the registered whitelist, no neural revival, no 2025H2.
- It does not try to fix information sufficiency (Q-B): if the features cannot support the required top-of-list precision, AWR converts what exists and the 5+5 replay verdict says so honestly; view expansion is Phase C's decision, not this design's.

# LABEL ATLAS V2 — recovered pre-cleanroom label taxonomy, screen results, and engine design

STATUS: **RECOVERY DOCUMENT.** Every family name below is quoted verbatim from a
pre-cleanroom source; nothing here is invented. This is a reference spec for the futures
port's label program, not a schedule and not a result claim.

RECOVERED: 2026-08-13, from the read-only archive
`/workspace/artifacts/context_archives/russell_context_archive_20260808_1a2249eedd47.contents/workspace_snapshot/files/`
(abbreviated `ARCHIVE/` throughout). Every citation is a real path in that tree.

**Headline count: 109 named family / subfamily / construction entries across 9 origin
layers.** Families recur across layers (triple-barrier appears in five of them); the
recurrences are marked inline rather than collapsed, because each layer registered its own
definition, parameter grid and evidence grade and the port needs all three.

**Instance counts (measured, not estimated):**

| object | count | source |
|---|---|---|
| generative-grid members enumerated | **541** | recomputed from `ARCHIVE/lab/labels.py::enumerate_grid()` |
| grid members surviving the measured prunes P9/P10 | **526** | `ARCHIVE/lab/specs/label_screen_v1.yaml:8` |
| grid members actually screened (Stage A) | **539** unique ids | `ARCHIVE/lab/ledger_screen.tsv`, sweep `label_screen_v1` |
| retention-axis members screened (round 2) | **27** | same ledger, sweep `round2_retention_axis` |
| round-3 shadow/retention roster | **20** arms (8 retention + 6 shadow + 6 shuffle guards) | `ARCHIVE/lab/labels_shadow.py::_register()` |
| named seeds L01–L19 | 17 in-grid + 2 outside | `ARCHIVE/lab/labels.py::SEEDS`, `SEEDS_NOT_IN_GRID` |
| engine label families implemented + published | **11 of 13**, `labels_*.parquet`, 41,999,169 rows each (F-CFA 55,998,892) | `ARCHIVE/docs/specs/select2_label_catalog_census_v1.md:29-36` |

**FILE STATUS of the requested read list** (all present and non-empty except as noted):

| requested path | status |
|---|---|
| `docs/specs/label_atlas_v1.md` | present, 9,737 B |
| `docs/specs/iwm_clean_nbbo_label_atlas_v1.md` | present, 18,458 B |
| `docs/specs/labeling_sota_research.md` | present, 31,970 B |
| `docs/specs/label_design_research.md` | present, 56,806 B |
| `docs/specs/label_crossdomain_research_v1.md` | **NOT AT THAT PATH.** The file exists at `ARCHIVE/research/review_records/label_crossdomain_research_v1.md` (25,619 B); its architect sibling is `ARCHIVE/research/review_records/label_crossdomain_research_architect_v1.md` (10,060 B) |
| `docs/specs/label_tensor_engine_v1.md` | present, 10,820 B |
| `docs/specs/label_probe_schema_v1.md` | present, 11,314 B |
| `docs/specs/label_kernel_design_v1.md` | present, 10,699 B |
| `docs/specs/select2_label_catalog_census_v1.md` | present, 40,144 B |
| `lab/labels.py`, `labels_panel.py`, `labels_shadow.py`, `labels_retention_axis.py` | all present |
| `lab/specs/label_screen_v1.yaml`, `label_confirm_v1_p4.yaml` | present (+ `label_confirm_v1.yaml`, `_p0..._p3`, `smoke_label_screen.yaml`) |

**Related files found beside them and used here** (not on the request list):
`ARCHIVE/docs/designs/label_atlas_and_objective_v1.md` (the generative-grid ruling — the
single most load-bearing recovered document), `ARCHIVE/lab/ledger_screen.tsv` (Stage-A
results), `ARCHIVE/lab/ledger.tsv` (Stage-B/policy results),
`ARCHIVE/lab/receipts/round{1,2,3,4}_champion.md` (the adjudications),
`ARCHIVE/lab/specs/l01..l19_*.yaml` (per-seed fit specs),
`ARCHIVE/engine/crates/labels/`, `ARCHIVE/oracle/labels/` (Rust kernels + Python oracles),
`ARCHIVE/engine/crates/select/src/{label_leaf,label_leaf_builder,near_family_labels}.rs`.

---

# 1. THE COMPLETE FAMILY TAXONOMY

Grouped by origin, exactly as the sources group themselves. Names are verbatim.

## 1A. HOUSE-INVENTED — the implemented engine catalog (13 families + 2 non-families)

Source: `ARCHIVE/docs/specs/select2_label_catalog_census_v1.md` §2, whose taxonomy law is
"organized FAMILY-FIRST. A rung, horizon, or window is a VARIANT INSIDE a family, never a
family of its own." Definitions: `ARCHIVE/docs/specs/label_kernel_design_v1.md` §"Families
(EVENTS.2 wave)", `ARCHIVE/docs/specs/label_probe_schema_v1.md`, and
`docs/specs/family_schemas/*.md` (schemas referenced by the census; the `family_schemas/`
directory itself is **NOT in the archive snapshot** — the definitions are recoverable only
through the census's quotations of them).

| # | Family (verbatim) | One-line definition | Parameter grid |
|---|---|---|---|
| A1 | **F-PASS — Pass-threshold first passage** ("first-passage ladder") | first favorable / adverse touch of a bps rung from the anchor price, independently per side | 11 rungs `[5,10,15,20,30,40,60,80,120,160,240]` IWM bps × 2 sides × 3 slots (d1/d2/d3) = 66 variants; `distance_u6 = ((P*N + 9_999)/10_000).max(1)` |
| A2 | **F-ORD — Competing-risk ordering** (`fp_first`) | which side touched first, as a typed state | states `FAVORABLE_FIRST, ADVERSE_FIRST, SAME_GROUP(_AMBIGUOUS), NEITHER_COMPLETE, NEITHER_WIDE_BREAKER, NEITHER_CLOSE_TRUNCATED, NEITHER_SOURCE_CENSORED, OUT_OF_DOMAIN, NA`; 4 anchor scales `[5,10,20,40]` (F-ORD) or all 11 rungs (`fp_first_<N>`) |
| A3 | **F-EXT — Remaining-MFE** ("continuous remaining MFE") | `mfe_u6 = max(0, F − P)` over `[left,end)`, F = favorable extreme, leftmost attaining index | horizon = window frontier; unit u6 = dollars×1e6; cols `mfe_u6, mfe_group_index, mfe_ts_ns, mfe_group_kind` |
| A4 | **F-EXT — Post-entry-MAE** ("nonnegative MAE") | `mae_u6 = max(0, P − A)`, exact mirror of A3 | same grid; **highest evidence value in the catalog** (early infeasibility alarm vs the <$1,000 EOD drawdown floor) |
| A5 | **F-EXT — Retention / giveback** ("MFE retention, post-MFE giveback, giveback time, and retained area") | giveback = adverse extremum over `[mfe_group_index, end)`; `retained_u6 = max(0, mfe_u6 − giveback_u6)` | absolute u6 only, never ratios; retained *area* = F-DWELL's `retained_area_u6ms` |
| A6 | **F-TERM — Terminal movement** | side-signed move from P to the last group at-or-before each horizon boundary, as an **interval** `(move_lo, move_hi)` | 5 horizons `15M/30M/60M/120M/CLOSE`; states `ATTAINED, WIDE_BREAKER, CLOSE_TRUNCATED, SOURCE_CENSORED` |
| A7 | **F-DWELL — Dwell / occupation / time-under-water** ("dwell/occupation, longest run, repeated break/reclaim, and time under water") | time-integrals of favorable/adverse/flat occupancy | `above_ns, below_ns (=underwater_ns), at_ns, longest_fav_run_bars, longest_adv_run_bars, break_reclaim_count, retained_area_u6ms, retained_area_state, no_quote_bars, ambiguous_close_bars` |
| A8 | **F-QPRIM — Survival / time-to-payoff, censoring primitives** ("survival/hazard and time-to-payoff") | attain-or-censor timestamp per rung per side, with the censoring indicator | `qp_fav_<N>_attain_or_censor_ts_ns` / `qp_adv_<N>_…` for all 11 rungs; + ledger `event_time_ns` (staggered-entry clock) |
| A9 | **F-CFA — Counterfactual act-now / wait / pass** | value of acting now vs waiting one/two slots vs passing, at neutral endpoint | 4 rows per signal `D1/D2/D3/PASS` (the only family off the 3-slot shape); `act_lo_u6, act_hi_u6, act_state, wait_forgone_fav_u6, wait_avoided_adv_u6, wait_state` |
| A10 | **F-CTRL — Triple-barrier + trend-scanning controls** ("exact trend-scanning and triple-barrier controls") | López de Prado triple barrier + OLS trend-scanning sufficient statistics, as literature controls | barriers: 3 widths × 3 vertical horizons = 9 cells, `tb_<N>_<V>_state` (8-valued `BarrierState`), `_touch_index`, `_touch_ts_ns`, `_term_move_lo/hi_u6`; trend: 4 windows, `trend_<L>_{state,n,sum_y,sum_xy,sum_y2,sign}` |
| A11 | **F-DIR — Direction / reversal / false-break / reclaim** | 13-valued exact state machine over post-anchor direction | `dir_n_star_bps`, `dir_state` (13-valued `DirState`); `INCONCLUSIVE` deliberately excluded from binary heads, never folded into the negative class |
| A12 | **F-RANK — Episode/session-relative ranks** ("descriptive ranks with prefix-causal variants") | within-episode/session rank primitives | published set **FROZEN** to exactly `eligible_count, rank_reversal, rank_staleness`; "pivot prominence" struck by amendment |
| A13 | **F-PROX — Truth-relative proximity** — **BARRED** | proximity to the registered truth set / captured-opportunity fraction | `cap_opp_num_u6, cap_opp_den_u6, near_extreme_credit`; every column carries `outcome_only`; **"Recommendation: never schedule."** The bar is restated in `labels.py::assert_no_fprox()` and `labels_panel.py` |
| A14 | **NON-FAMILY — Distributional / quantile / interval head SHAPES** | not a family: a head shape applied over the continuous families A3/A4/A5/A6/A7 | quantiles `0.10/0.25/0.50/0.75/0.90`, intervals, expectile, distributional, uncertainty targets; registered loss family Huber/quantile/expectile; calibration CQR |
| A15 | **NON-FAMILY — Regimes** | per-`(session,bar)`, no anchor, no label semantics | the **CONDITIONING axis** (GroupCell year × regime), never a head |

Registered but not-yet-consumable at census time (the "decoder/leaf gap", not a data gap):
9 of 11 implemented families had published atoms and no loader; the single structural
blocker was `select/src/fit_leaf.rs:555` refusing any label that is not exactly 0.0/1.0.

## 1B. HOUSE-INVENTED — the GENERATIVE LABEL GRID (11 grid families, 541 members)

Source: `ARCHIVE/docs/designs/label_atlas_and_objective_v1.md` §2b (user ruling 2026-08-07
~23:55: *"the old atlas won by breadth — hundreds of labels, not 19; L01–L19 are the SEEDS
of this grid"*), implemented mechanically in `ARCHIVE/lab/labels.py`.

**The composition law:** `label = compose(base, horizon, truncation, penalty, transform)`.

| axis | grid (verbatim from `labels.py`) |
|---|---|
| `horizon` | `15m, 30m, 60m, 120m, close, best` (`best` = best-of-marks over the exit grid; path bases use the 5 fixed marks only) |
| `truncation` τ (loss floor, cents) | `tnone, t10k(−10,000), t15k(−15,000), t30k(−30,000)` |
| `penalty` −λ·max(0, mae_depth − m) | `p0, p05m10k, p05m15k, p05m30k, p10m10k, p10m15k, p10m30k` (λ∈{0,.5,1} × m∈{10k,15k,30k}) |
| `transform` | `raw, z (session-MAD), rank (within-session percentile), winsor (p0.5/p99.5), bin0, bin576, bin15k` |

**The 11 grid families** (the `family` field of every enumerated member), with measured
member counts:

| # | family | base(s) | definition | parameter grid | members |
|---|---|---|---|---|---|
| B1 | `dollar` | `net` | terminal net cents at the mark, already net of the 576c round trip | 6 horizons × {1 unshaped + 3 truncations + 6 penalties} × transforms, pruned by P4/P5/P6 | **240** |
| B2 | `gain` | `mfe` | `10·mfe_u6 − 576` — cost-adjusted gross favorable excursion | 6 horizons × 7 transforms | **42** |
| B3 | `ratio` | `retention` | `net / max(mfe_c, ε)` — share of the favorable move kept | 6 horizons × {raw,z,rank,winsor} | **24** |
| B4 | `first_passage` | `fp10, fp20, fp40, fp60` | seconds to first FAVORABLE passage of θ bps, `+inf` = censored inside the horizon | θ∈{10,20,40,60} bps × 5 path horizons × {raw,rank} | **40** |
| B5 | `fav_first` | `fav_first_10000/15000/30000` | `1[t_first_net_positive < bars_to_mae_threshold(τ=m)]` | m∈{10k,15k,30k} cents × 5 horizons | **15** |
| B6 | `cfa` | `cfa_wait_30/60/120/rod` | **act-now-vs-wait regret**: `net(a) − best net among the SAME session's later actions within K bars` (the optimal-stopping label) | K∈{30,60,120,rest-of-day} × {raw,z,rank,winsor,bin0}, fixed at 60m | **20** |
| B7 | `race` | `race_(θu,θd)` | competing-risk ordering: `+1` if `+θu` bps passes before `−θd`, `−1` opposite, `0` neither. **Recorded tie rule: a simultaneous touch resolves to −1** | θu∈{20,40,60} × θd∈{10,20,40} × 5 horizons | **45** |
| B8 | `triple_barrier` | `tb_(pt,sl)` | triple-barrier value in bps: `+pt` if the profit rung passes first, `−sl` if the stop rung does, else the horizon's terminal `g_bps` (vertical barrier) | pt∈{40,60,100} × sl∈{15,20,30} bps × 5 horizons × {raw,rank} | **90** |
| B9 | `dwell` | `uw_share` | time-underwater share of the horizon's seconds (`g < 0`) | 5 horizons × {raw,rank} | **10** |
| B10 | `ttp` | `ttp` | time-to-payoff: seconds to the first `+1·σ̂` passage inside 60m, right-censored (`lp__ttp_censored=1` ≠ zero) | 5 horizons × {raw,rank} | **10** |
| B11 | `reclaim` | `reclaim_evt` | false-break/reclaim outcome **conditioned on the EV1 event state at entry**: `sign(net)` where an agreeing event fired within 3 bars, else NaN | 5 horizons, raw only | **5** |
|  |  |  |  | **TOTAL** | **541** |

**Structural prunes P1–P8** (applied inside `enumerate_grid()`, each recorded):
P1 `net_best`-as-base dropped (= base `net` × horizon `best`); P2 truncation is a cents
loss floor, coherent only for cent-valued bases; P3 penalty likewise; **P4 truncation and
penalty are both loss-shaping — at most ONE may be active, never both**; P5
`rank(truncate(x)) == rank(x)`, pruned as an exact duplicate by construction; P6
binarising an already-shaped value re-expresses the same threshold; P7 rank/z/winsor on an
already-binary base is degenerate; P8 horizon `best` is meaningful only for exit-dependent
bases.
**Measured prunes P9/P10:** P9 drops any member that comes out constant, all-NaN, or with a
minority class below 1%; P10 collapses byte-identical members (values AND NaN pattern) to
the first enumerated. 541 → **526 kept**.

**The named seeds L01–L19** (`ARCHIVE/docs/designs/label_atlas_and_objective_v1.md` §2,
per-seed fit specs at `ARCHIVE/lab/specs/l01..l19_*.yaml`), all but two aliased into the grid:

`L01 net_60m` (the workhorse) · `L02 net_30m` · `L03 net_120m` · `L04 net_close` (t2b's old
label) · `L05 net_best = max_h term_net_cent_h` (with-exit-choice; the 1.36× lever) ·
`L06 net_60m_trunc150` · `L07 net_best_trunc150` · `L08 net_60m_trunc300` ·
`L09 comp_60m_k05 = net_60m − 0.5·max(0, mae_60m − 15,000)` · `L10 comp_60m_k10` ·
`L11 comp_best_k05` · `L12 p_win_60m = 1[net_60m > 0]` · `L13 p_win150_60m = 1[net_60m >
15,000]` · `L14 p_fav_first_60m` · `L15 rank_60m` (within-session percentile) ·
`L16 rank_best` · `L17 z_60m` (session-MAD) · **`L18 argmax_h`** (multiclass horizon-routing
head — *outside* the grid: a 5-class target the compose() axes cannot express) ·
**`L19 mae_q_60m`** (downside quantile head — outside the grid: a downside head, not an
entry payoff).

**The TYPE EXTENSION** (user ruling 2026-08-08 ~00:20, taken *from the old census's
taxonomy*, `select2_label_catalog_census_v1.md`, "13 families; types matter more than
count") added the six base TYPES B6–B11 above plus one more:

- **`oracle_pick_soft`** (USER RULING 2026-08-08 ~02:30) — per session run the uncapped DP
  on true outcomes; label = 1 for the DP's picks, soft (0,1) for near-picks (actions whose
  swap-in costs the DP < ε ∈ {$25,$100}), 0 else; horizons {60m, best}. Explicitly *NOT*
  F-PROX: "this is outcome-derived, not truth-set-relative". Registered in the design doc;
  **not present in `enumerate_grid()`** — it materialised instead as the round-3
  `shadow_value` family (§1D).

## 1C. HOUSE-INVENTED — the RETENTION / RATIO AXIS (round-2 re-expansion, 7 subfamilies)

Source: `ARCHIVE/lab/labels_retention_axis.py`. Triggered by round 1's autopsy naming the
ratio axis (`ARCHIVE/lab/receipts/round1_champion.md` §7). Repairs a **measured defect**:
round-1 retention divided by an MFE that is negative on 1.08–1.42% of rows, so the label's
sign flipped there and `|retention| > 100` on ~1% of rows, range to ±238.

Fix: `retention = net_c(h) / max(mfe_c(h), ε)`, ε>0 in cents.
**ε grid `{576, 1500, 5000, 15000}` cents = {one round-trip cost, $15, $50, $150}.**
Horizons `{15m, 30m, 60m, 120m, close, hbest}`. All members oriented higher=better.

| # | subfamily (`kind`) | formula |
|---|---|---|
| C1 | `ret` | `net_c(h) / max(mfe_c(h), ε)`; the **gated** variant sets NaN where `mfe_c < ε` (the MOVER GATE — non-movers leave the training universe) |
| C2 | `gbabs` | `−(mfe_c − net_c)` — absolute cents given back, sign-flipped |
| C3 | `gbshare` | `−(gb_c(h) / max(mfe_c, ε))` — the book's own giveback column as a share |
| C4 | `gbfrac` | `−((mfe_c − net_c) / max(mfe_c, ε))` |
| C5 | `effpath` | `net_c / max(mfe_c + mae_d, ε)` — net per unit of total path travelled |
| C6 | `rrreal` | `net_c / max(mae_d, ε)` — realized reward-per-risk |
| C7 | `mfeshare` | `mfe_c / max(mfe_c + mae_d, ε)` — **pure geometry, no net** |

Two proposed prunes were **REFUTED by their own arithmetic before any fit was spent** and
both members were fitted: `gbfrac` is an exact affine complement of retention *only* where
the ε floor does not bind (it binds on 11.01% of rows at close/ε5000, deviation to 2.744);
and `rank(winsor(x)) ≠ rank(x)` — the clip is monotone but **not strictly** monotone, so it
creates ties and average ranks move (max within-session percentile deviation 0.2323 over
773,661 rows). One prune held: `Rx_ret_close_e5000_bin0 ≡ L12` exactly.

## 1D. HOUSE-INVENTED — SHADOW VALUES (round-3, 2 families + the shuffle guard)

Source: `ARCHIVE/lab/labels_shadow.py`. The realisation of the `oracle_pick_soft` ruling.

| # | family | definition | grid |
|---|---|---|---|
| D1 | `shadow_value` (`Sd_shadow_<h>_<t>`) | **`shadow(a) = prefix[start(a)] + w(a) + suffix[end(a)] − optimal`** (≤0) — the dollar cost of FORCING action `a` into the optimal uncapped one-position schedule. Dense, continuous, occupancy-aware where membership labels are binary, sparse and occupancy-blind | horizons `{60m, close}` × transforms `{raw, rank, z}` |
| D2 | `retention_treatment` (`Rt_retg_*`) | the round-2 winner cell (`net_c/max(mfe_c,5000)`, mover-gated) re-expanded along both margins under real per-arm HP tuning | complete TRANSFORM margin at `close` `{raw, rank, z, winsor99, bin10}` + complete HORIZON margin at `rank` `{60m, 120m, close, hbest}` |
| — | **GUARD (mandatory)** | every shadow arm gets a twin fitted on WITHIN-SESSION-SHUFFLED labels at identical budget: same universe, same per-session marginal, same row count; only the row↔label association destroyed | `Sd_*_SHUF`, seed 20260808. "An arm whose shuffled twin clears that bar on any metric is VOIDED — it is memorising session identity, not pick structure." |

## 1E. HOUSE-INVENTED — the NATIVE RTY LABEL ATLAS v1 (11 outcome families)

Source: `ARCHIVE/docs/specs/label_atlas_v1.md`. "the first expansive selection-research
layer… maps each canonical `candidate_core_v2` decision to a registered family of
native-RTY outcomes". Every field prefixed `label_`, every record
`label_role=outcome_only_never_model_input`, `label_executable=false`.

Axes: **anchors** — "independently anchored d0, d1, d2, and d3 decision closes" (delay
0–389 min, a new hypothetical executable decision close, never a shift of the d0 fill);
**horizons** — "5, 15, 30, 60, and 120-minute and session-close" (fixed horizon 1–390 min).

| # | family (verbatim) |
|---|---|
| E1 | side-aware **terminal return** |
| E2 | **MFE** |
| E3 | **MAE** |
| E4 | **time-to-MFE** |
| E5 | **time-to-MAE** |
| E6 | **gross path range** (`= MFE + MAE` exactly) |
| E7 | **favorable share of range** (zero for a zero range) |
| E8 | **terminal capture of MFE** (signed terminal ticks / MFE; null when MFE is zero) |
| E9 | **symmetric first-passage / competing-barrier outcomes** |
| E10 | **asymmetric first-passage / competing-barrier outcomes** |
| E11 | regime states: **continuation, reversal, balanced, neither, and ambiguous** |

**Default first-passage registrations** (the barrier grid): "span 5 through 400 ticks ($25
through $2,000 for one mini): **symmetric 5/20/80/200/400-tick pairs, 2:1 pairs from 20:10
through 400:200, and 3:1 pairs from 30:10 through 300:100**. These are broad outcome
probes, not promoted stops or targets." One tick = 0.10 index points = $5 per RTY mini.
Barrier bounds 1–2,000 ticks; every OHLC price an integer in 1–1,000,000 ticks.

Censoring taxonomy: `no_post_anchor_bars`, right-censored-at-close (partial data retained
only under `observed_*`), `censored_no_event`, `neither_by_horizon`, `same_bar_ambiguous`
("no invented OHLC traversal order chooses a winner").

## 1F. HOUSE-INVENTED — the CLEAN-NBBO decision-path / label-atlas contract v1 (16 entries)

Source: `ARCHIVE/docs/specs/iwm_clean_nbbo_label_atlas_v1.md`. Status in the archive:
**"implementation candidate; not accepted; production allowlist empty."** Registered
cardinality 607,332 decisions × 6 horizons = **3,643,992 wide label rows**.

Registered horizons (the closed v1 registry):
`M5_DIAGNOSTIC` (diagnostics only; never selects or promotes) · `M15` · `M30` · `M60`
(primary-capable) · `M120` (atlas challenger; bridge amendment required) · `OFFICIAL_CLOSE`.

| # | family / measurement (verbatim) | definition |
|---|---|---|
| F1 | `terminal_move_numerator` | `10_000·q·(Ut−U0)` |
| F2 | `mfe_units` | `max(0, max_k(q·(Uk−U0)))` |
| F3 | `mae_units` | `max(0, max_k(−q·(Uk−U0)))` |
| F4 | `dominance_units` | `mfe_units − mae_units` |
| F5 | `bounded_capture` | `mfe/(mfe+mae)` when the denominator > 0 |
| F6 | attainment times | earliest attainment of MFE/MAE, with group ordinal and timestamp |
| F7 | observed duration / scalar vs heterogeneous-unresolved durations | exact nanoseconds; `duration_point_identified=true` only when all bounds collapse |
| F8 | **excursion-area bounds** | sharp lower/upper bounds for signed, favorable, adverse excursion area (integer microdollar-units × exact ms) |
| F9 | **occupation bounds** | favorable / adverse / flat occupation; flat upper bounds use exact anchor membership from the sparse midpoint sidecar, never envelope containment |
| F10 | **the factorized passage surface** | first favorable touch and first adverse touch stored *independently* per threshold. Registry (bps): **`(5, 10, 15, 20, 30, 40, 60, 80, 120, 160, 240)`**. "This factorization represents **all 121 favorable/adverse triple-barrier pairs** without storing or scanning 121 redundant cells." Bridge-facing set stays exactly `(5,10,20,40)`; `(15,30,60,80,120,160,240)` are atlas-only challengers |
| F11 | derived competing-risk pair states | `FAVORABLE_FIRST · ADVERSE_FIRST · AMBIGUOUS_DUAL_TOUCH · NEITHER_BY_HORIZON · SOURCE_CENSORED · TRUNCATED_BY_CLOSE · STRUCTURALLY_UNAVAILABLE` — "Ambiguous, neither, censored, and unavailable rows never become binary zero" |
| F12 | structural truth assignments | separate contextual labels at 5/10/20/40 bps |
| F13 | **ordinal reachability** | challenger, not a universal primary label |
| F14 | **lower-threshold auxiliary tasks** | challenger |
| F15 | **volatility-normalized projections** | challenger; may use only scale known at the decision cutoff and fitted inside the current training fold. Full-day RV, future RV, hindsight regime, and globally fitted scale are **prohibited** |
| F16 | forward trend scanning | **explicitly DEFERRED from v1** until its forward-window/regression/tie/censor/identity law is separately frozen |

Standing law from this contract, load-bearing for the port: **"Labels do not vary by
regime… Creating a different truth definition after observing a regime is prohibited."**

## 1G. SOTA / ML-LITERATURE census (15 entries)

Source: `ARCHIVE/docs/specs/labeling_sota_research.md`. Evidence grades verbatim
(STRONG / MODERATE / WEAK / UNVALIDATED).

**§2 — newer/less-known label constructions:**

| # | construction (verbatim) | core idea | grade |
|---|---|---|---|
| G1 | **Continuous/soft trend labels** (2.1) | t-value of local OLS slope, or piecewise-linear trend score, as a REGRESSION target never thresholded | MODERATE |
| G2 | **Tail-set labels** (2.2) | membership in top/bottom quantile of cross-sectional forward returns across a universe | MODERATE-WEAK |
| G3 | **Oracle / ex-post-optimal labels** (2.3) | perfect-foresight DP / optimal-stopping action under realistic frictions, distilled to a supervised target | UNVALIDATED ("hindsight-optimal actions are UNATTAINABLE targets") |
| G4 | **Matrix flag / template labeling** (2.4) | discretionary pattern-matrix; CNN candlestick templates as the nearest rigorous analogue | WEAK |
| G5 | **N-period min-max labeling** (2.5) | is this bar the min/max of a forward N-bar window | MODERATE (structurally = the house star/extreme frame) |
| G6 | **Directional-change (DC) / intrinsic-time labels** (2.6) | events and labels defined by fixed-percentage reversals in *intrinsic* time, not clock time | MODERATE-STRONG (most mature line found) |
| G7 | **Magnitude-aware ordinal buckets** (2.7) | ordinal regression loss over magnitude buckets instead of binary/ternary CE | WEAK-MODERATE |
| G8 | **Path-signature-based labels** (2.8) | signature-distance / regime cluster as the label | WEAK/UNVALIDATED |
| G9 | **RL-derived value labels** (2.9) | learned Q/value (IQL/CQL/DT return-to-go) of entering, distilled into a GBDT regression target | MODERATE (general ML), UNVALIDATED (finance) |
| G10 | **Distributional / quantile targets** (2.10) | full conditional distribution (multi-quantile/CRPS/NGBoost/CatBoostLSS) replaces classification | MODERATE (technique), WEAK (equity/futures P&L) |

**§3 — label engineering beyond the target** (target transformations, not new targets):

| # | lever | finding |
|---|---|---|
| G11 | **Label smoothing / soft targets under high outcome noise** | uniform smoothing helps at low-moderate noise but **vanishes and can reverse in high-noise regimes**; several SOTA methods implicitly perform **NEGATIVE label smoothing** (ε<0), which beats uniform positive smoothing when noise is high |
| G12 | **Sample weighting** | return-attribution weighting (uniqueness × \|attributed log-return\|) [MODERATE, canonical, no post-2021 GBDT ablation found]; time-decay/recency weighting [WEAK] |
| G13 | **Multi-task label stacks** | "largely an NN phenomenon"; CatBoost MultiRMSE forces the SAME splits across outputs and can actively hurt — run auxiliaries as SEPARATE models + ensemble |
| G14 | **Curriculum / confidence-ordered training / label denoising for GBDTs** | Ponti two-pass "dataset cartography": per-instance confidence/variability across boosting rounds, then reweight and retrain. Caution: GBDTs are naturally robust to symmetric label noise and noise *removal* can paradoxically hurt — use REWEIGHT, not delete |
| G15 | **Exit-menu envelope label** (§5 #1, the top-ranked untested construction) | over the finite deployed-exit menu E: `y_env = clip(max_{e∈E} R_e, −2, 6)` (upper envelope) and `y_rob = clip(min_{e∈E} R_e, −2, 6)` or `mean_e R_e` (robustness variant); optional auxiliary `argmax_e` as a categorical head. RL framing: `y_env` is **Q^menu** — a max over a small *deployable* policy class, not the unattainable Q\* |

**The meta-finding (§4, and the sharpest thing in the recovered corpus):** label-policy
consistency has *no formal published treatment*. "a label equal to realized outcome under a
fixed exit rule IS the Monte-Carlo return of a fixed policy, i.e. an unbiased sample of
Q^π(s, enter); training a selector on it is fitted policy evaluation of the deployed
policy. TB with mismatched barriers is then policy evaluation of the WRONG policy — an
off-policy target without importance correction." Three free corollaries: (i) label
variance = return variance of the policy, so clipping is a control variate; (ii) **when the
exit policy changes, ALL labels must be regenerated**; (iii) an oracle-exit label is Q\*
not Q^π — training a selector on it while deploying π reintroduces the TB mismatch at a
higher level.

## 1H. LABEL-DESIGN RESEARCH — physics / medicine / ML / trade (15 entries)

Source: `ARCHIVE/docs/specs/label_design_research.md`.

**§1 Physics / stochastic processes**

| # | construction | definition | evidence |
|---|---|---|---|
| H1 | **First-passage time as a regression label** (1.1) | (possibly censored) `T = min{t : X_t crosses B}` as a regression target, not just `1[crosses]`; auxiliary `bars_to_break` | MODERATE (construction transfer, not a validated lift transfer) |
| H2 | **Discrete-time hazard / survival framing** (1.2 ≡ 2.1) | cross-referenced; see H6 | — |
| H3 | **Last-passage vs first-passage time** (1.3) | `L = sup{t ≤ T_horizon : X_t = B}` — NOT a stopping time, hence label-only by construction. Legitimate descendant: a **retest-count / contest-quality** auxiliary ("clean hold" vs "contested hold") | WEAK |
| H4 | **Records theory — probability a record stands** (1.4) | closed-form record rate for a biased random walk gives a causally-computable persistence prior `P_hold(bars_since_extreme, trailing_drift, trailing_vol)`; characteristic timescale `n* ~ (σ/c)²` | MODERATE-STRONG as an empirical check (S&P 500 1990–2009); the paper's own **unexplained short-side suppression** is an explicit caution against long/short symmetry |
| H5 | **Extreme value theory (EVT/GPD) for barrier-width selection** (1.5) | peaks-over-threshold fit to trailing excursion magnitudes; hold probability at *any* candidate barrier width becomes a read-off of one fitted curve; mean-residual-life plot replaces hand-picking the barrier | MODERATE (UNVALIDATED for this object) |

**§2 Biology / medicine**

| # | construction | definition | evidence |
|---|---|---|---|
| H6 | **Discrete-time hazard via person-period expansion** (2.1) — *"the GBDT-native survival trick"* | stack each subject into one row per at-risk interval with event indicator `d_ij`; `λ_j(X) = P(T ∈ A_j \| T > t_{j−1}, X)` fit as an ordinary binary classifier; `S(t\|X) = Π(1−λ_j(X))`. Converts ANY survival problem into stacked binary classification, zero new architecture | MODERATE (discrete-time GBM best Brier-R² in 4/5 datasets). **Ranked top-8 #1**: 5–15× denser supervision from the same event count |
| H7 | **Competing-risks labels** (2.2) | cause-specific hazards `λ_k(t\|X)` + cumulative incidence `CIF_k(t\|X) = ∫λ_k·S`; DeepHit as the DL instantiation with its pairwise ranking loss. Explicit pitfall: naive `1−KM` treating competing causes as independent censoring **over-estimates** each cause | STRONG as methodology, no finance transplant |
| H8 | **Earliness-weighted labels / ECTS** (2.3) | TEASER slave/master: a classifier scores growing-length snapshots; a second stage trained only on CORRECT predictions learns the trustworthy confidence region and commits only after `v` consecutive stable snapshots. Objective = harmonic mean of accuracy and (1−earliness) | STRONG within its field (23% earliness at highest accuracy, 36/45 UCR datasets), UNVALIDATED on financial data |

**§3 ML — soft / distributional / noisy / auxiliary**

| # | construction | definition |
|---|---|---|
| H9 | **Soft/graded labels** (3.1) | two mechanisms that must be told apart: *label smoothing* (blend toward a UNIFORM prior — pure regularizer, no information) vs *data-driven soft labels* (from an estimate of the true underlying probability — injects real information). Our regime is "**one Bernoulli draw from a latent, feature-conditioned p(x) that is the actual estimand**", so proper-scoring-rule training on raw realizations is ALREADY Bayes-consistent; only information-INJECTING soft targets can add anything |
| H10 | **Distributional / CRPS excursion regression** (3.2) | model the full conditional distribution of signed vol-scaled excursion; `P(hold) = CDF(barrier)` — the SAME fitted model answers at ANY barrier width without retraining. **Subsumes H5 as a byproduct** |
| H11 | **Learning to defer / selective prediction / abstention** (3.3) | a REJECT option paying a fixed deferral cost. Verdict: LOW priority — functionally already implemented via top-k% rank cuts |
| H12 | **Noisy-label theory** (3.4) | analysis, not a construction: our "noise" is outcome variance, not annotation error, so noise-robust losses (peer loss, GCE) are **the WRONG tool** |
| H13 | **Auxiliary multi-task labels** (3.5) | related-but-distinct targets sharing the trunk; the two genuinely distinct-information candidates are `bars_to_break` (timing) and the per-bar hazard sequence (density). Needs a **swept** task weight, never a hand constant |

**§4 Trade-outcome-specific**

| # | construction | the reconciliation |
|---|---|---|
| H14 | **Triple-barrier** (4.1) | The house refutation's mechanism was **"right-tail amputation"** — TB capped the label below what the deployed ATR-trailing exit realized. **"this is a label/deploy MISMATCH finding, not a blanket refutation of barrier-anchored labels."** Barrier labels are licensed *provided the barrier stays anchored to the actual thesis* rather than reintroduced as an arbitrary vol-scaled proxy |
| H15 | **Meta-labeling** (4.2) | primary rule + secondary "is this firing worth acting on"; sizing off SCORE RANK, not raw probability. In-house precedent: the meta-model is real (AUC 0.665, fold-stable) but "**CONFIDENCE CANNOT BUY THE USER'S SHAPE**" — it filters *which* trades, it does not manufacture bigger ones |
| H16 | **Sample-weighting by uniqueness / overlap** (4.3) | average-uniqueness `u_i = mean_t 1/c_t`. The prior "no help" negative was measured on the DENSE per-minute universe where uniqueness collapses to a near-uniform discount; on a sparse event population it may behave differently — a Rule-8 recall probe, not a committed build |

## 1I. CROSS-DOMAIN RESEARCH — biostat / reliability / weak-supervision / frontier (17 entries)

Sources: `ARCHIVE/research/review_records/label_crossdomain_research_v1.md` (agent sweep)
and `…_architect_v1.md` (architect-authored, with the adjudication that supersedes it).

**LANE 1 — cross-domain endpoint constructions**

| # | construction (verbatim) | definition | verdict |
|---|---|---|---|
| I1 | **Cumulative Incidence Function (CIF) / Fine–Gray subdistribution hazard** | `F_k(t) = P(event type k by t in the presence of the other risks)`; subdistribution hazard `λ_sub = r(t)·α_cs(t)`, `r(t)=S(t)/[1−F₁(t)]`. The decision-relevant quantity is exactly **P(reach +k bps before the adverse barrier or session close)** | **ADD (high).** A distinct estimand from first-touch — it can flip sign vs the cause-specific view. Pathology: summed CIFs can exceed 1, so use per-target CIF, never a simultaneous multi-cause model |
| I2 | **Cause-specific hazard** | rate of type-k events among the still-event-free | **COVERED** (this is what the F-PASS ladder already implements) — but make the estimand explicit so I1 reads as complementary, not duplicate |
| I3 | **Multi-state / illness-death models** | transition intensities; two label-grade scalars fall out: **transition probabilities** `P(in state s at horizon h \| prefix)` and **expected time-in-state** via Aalen–Johansen | **ADD** (transition-probability labels + AJ expected-time-in-state); COVERED for the state machine itself |
| I4 | **Restricted Mean Survival Time (RMST) / restricted mean time-in-state** | `RMST(τ) = ∫₀^τ S(u)du` — consistently estimable even when the largest observation is censored, valid when proportional hazards fails | **ADD (top-tier).** The censoring-robust expected-value scalar the catalog lacked. Amendment T5 renamed it **RESTRICTED MEAN TIME IN FAVORABLE STATE** |
| I5 | **Win ratio / generalized pairwise comparisons (GPC)** | rank pairs by a *prioritized hierarchy* of outcomes; `WinRatio = #Wins/#Losses`, `NetBenefit = (#W−#L)/#Pairs`; unresolvable pairs stay ties | **ADD.** A pairwise win/loss *training target* matching the cap-3 slate problem: bigger barrier → less adverse → faster |
| I6 | **Desirability of Outcome Ranking (DOOR)** | collapse multiple outcomes into one ordinal scale with partial-credit weights | **SKIP / COVERED** by GPC + existing ordinal ranks — but adopt its *construction recipe* for the outcome hierarchy |
| I7 | **Remaining-Useful-Life (RUL) piecewise-linear / elbow labels** | constant until a change-point, then a linear ramp-down — capping avoids forcing implausibly long countdowns from quiet prefixes | **ADD (modest)** by the agent; **SKIP (covered)** by the architect, who keeps only the capped-linear encoding as an option |
| I8 | **First-hitting-time / threshold regression (Wiener → inverse-Gaussian)** | latent Brownian degradation; first passage is Inverse-Gaussian with a natural **defective/cure fraction** for "never hits" | **SKIP / COVERED** — the cure-fraction idea is already the "neither" state |
| I9 | **Movement-ecology behavioral-state HMM** | decode latent behavioral states from movement tracks | **COVERED / SKIP as a label** (it is a feature technique) |

**LANE 2 — weak supervision & label-model research**

| # | construction | definition | verdict |
|---|---|---|---|
| I10 | **Positive-Unlabeled (PU) learning — nnPU / SAR-PU** | `R(g) = π_p·R_p⁺ + [R_u⁻ − π_p·R_p⁻]`; nnPU clamps the bracket at zero. **SCAR is violated here** (labeling propensity is feature-dependent), so the correct framing is **SAR-PU with a propensity model** | **ADD (highest).** "matched truths are **verified positives**; unmatched candidates are **unlabeled**, not negative" — treating unmatched as negative trains the selector *against* the recall we care about |
| I11 | **Snorkel / data-programming label model** | combine noisy labeling functions into a generative model emitting probabilistic soft labels with learned accuracies | **NARROW ADD** — soft/confidence-weighted labels for the AMBIGUOUS/INTERVAL/conflict states only (weight-by-confidence rather than discard); architect scopes the full version to the SIGNING engine |
| I12 | **Soft labels / label smoothing / distributional targets** | | **SKIP** (smoothing) / **COVERED** (distributional), with CIF-as-soft-label credited to I1 |
| I13 | **Learning from Label Proportions (LLP)** | only bag-level class proportions known | **SKIP** (we have instance-level outcomes); note the per-session-proportion consistency penalty as a minor optional regularizer |

**LANE 3 — 2025/2026 frontier**

| # | construction | definition | verdict |
|---|---|---|---|
| I14 | **Decision-focused learning (DFL) / decision-regret targets** | train with a task loss that depends on the realized downstream *decision*, not RMSE — errors that don't change the selection cost nothing; errors that flip a top-3 pick cost a lot | **ADD (high).** "C1 taken from adjudication into training" |
| I15 | **Distributional-RL targets as supervised labels (QR / IQN)** | the **distributional value-of-waiting** target: the full return distribution of the F-CFA counterfactual, propagated d1→d2→d3 | **ADD (medium)** by the agent; COVERED by the architect until upgraded via the adjudication |
| I16 | **Expected-shortfall / CVaR tail-value labels** | CVaR/ES is **jointly elicitable with VaR**, so the (VaR, ES) pair is a valid two-output regression target | **ADD (medium-high).** The estimand the drawdown floor implies — targets exactly the downside the acceptance statistic penalizes |
| I17 | **Financial-ML labeling (triple-barrier / trend-scanning / meta-labeling)** | | **COVERED** all three; the one genuine ADD is **concurrency/uniqueness sample-weighting** (a weighting scheme, not a label — route to fold design) |

**Final adoption order (architect's Shortlist v2, the binding one):**
1. **SAR-PU + value-head primacy** · 2. **DFL losses** · 3. **CIF/Fine–Gray per-rung
hit-probability labels** · 4. **CVaR drawdown-head target** · 5. **Snorkel label model
(signing)** · 6. **multi-state WAIT transitions + distributional wait** · 7. **RMST** ·
8. **win-ratio LTR targets**. Item 1E (RUL) explicitly **SKIP**. All under a
primary-source-exact implementation law: "a proxy that 'captures the idea' is an
invalidated implementation."

---

# 2. WHAT THE SCREEN FOUND

The tournament ran in two preregistered stages
(`ARCHIVE/docs/designs/label_atlas_and_objective_v1.md` §2b, `ARCHIVE/lab/specs/label_screen_v1.yaml`,
`label_confirm_v1*.yaml`):

- **Stage A SCREEN** — every grid label on a 25% action subsample, 50 boosting rounds, fixed
  mid params (`max_depth 6, eta 0.08, subsample 0.8, colsample 0.6, min_child_weight 50,
  reg_lambda 5`), folds 1–5, seed 20260807. **Ranked by the ENTRY BAR's rank block —
  never by a label's own loss**, "because different labels have different losses and are not
  comparable on them."
- **Stage B CONFIRM** — top ~25 + the seeds, full fits, per-fold inner HP search (120
  configs, 25% subsample, top-8 refit), `promotion: false`.

**Stage A executed: 539 unique labels, 2026-08-07 16:57Z→17:49Z (52 min wall), two git
SHAs, results appended to `ARCHIVE/lab/ledger_screen.tsv`** (20 columns: `rho_median,
rho_mean, rho_vs_net60m, dollar_recall@10, dollar_recall@5, hit@3, …`). All numbers below
are recomputed by me from that file.

**WHERE THE RESULTS LIVE NOW — two halves, and one of them is in the LIVE tree.**

| artefact | location | state |
|---|---|---|
| Stage A screen ledger (complete, 539 labels) | `ARCHIVE/lab/ledger_screen.tsv` | **archive only** |
| Stage A screen *receipt* | `/workspace/artifacts/runs/select_v2_fits_v1/label_screen_v1/screen_receipt.json` | **LIVE but TRUNCATED**: `n_labels_attempted: 541`, `n_labels_scored: 154`, git `ce867a6…`. It covers only the tail of the grid; the complete run is the archived ledger under git `81576af5…`. Do not read the live receipt as the screen |
| Stage B + rounds 2/3/4 per-arm raw receipts | `/workspace/artifacts/runs/select_v2_fits_v1/<spec>__<label_id>/fit_receipt.json` (+ `oof_scores.parquet`, per-fold `.ubj` models) | **LIVE, 153 arm directories, verified.** Richer than the archive's prose: `oof_metrics.spearman_vs_net_{60m,close}.{rho_median,rho_mean,rho_p10,rho_p90}`, `dollar_recall@{1,3,5,10,20,50}`, `rank_block_measured_only.{hit@1,3,10,50, oracle_pick_pct_mean/p50}`, replay/drawdown stats |
| Round adjudications (prose) | `ARCHIVE/lab/receipts/round{1,2,3,4}_champion.md`, `round1_diagnostics.md` | archive only |
| The grid code itself | `ARCHIVE/lab/labels*.py`, `lab/fit.py`, `lab/specs/` | **archive only — the live `/workspace/lab/` contains just `run.sh` and `watchdog.sh` (verified).** The port cannot regenerate or extend the grid without restoring this code |

## 2.1 Family-level screen result (`sweep = label_screen_v1`, n = 539)

`rho_vs_net60m` = within-session Spearman against the common dollar yardstick
`term_net_cent_60m` (the cross-label-comparable metric).
`rho_median` = within-session Spearman against the label's **own** truth (learnability).

| family | n | median rho_vs_net60m | best rho_vs_net60m | median dollar_recall@10 | best dr@10 |
|---|---:|---:|---:|---:|---:|
| `reclaim` | 5 | **+0.01393** | +0.03807 | +0.00097 | +0.00209 |
| `ratio` (retention) | 24 | **+0.00793** | **+0.07716** | −0.00151 | **+0.01193** |
| `dollar` (net) | 240 | +0.00292 | **+0.07956** | −0.00043 | +0.01152 |
| `first_passage` | 40 | +0.00209 | +0.01769 | −0.00356 | +0.00394 |
| `triple_barrier` | 90 | **+0.00010** | +0.02043 | −0.00163 | +0.00309 |
| `ttp` | 8 | −0.00006 | +0.02367 | −0.00266 | +0.00001 |
| `gain` (mfe) | 42 | −0.00065 | +0.02792 | −0.00377 | −0.00033 |
| `cfa` | 20 | −0.00121 | +0.00760 | −0.00191 | +0.00045 |
| `race` | 45 | −0.00300 | +0.01579 | −0.00208 | +0.00198 |
| `fav_first` | 15 | −0.00887 | −0.00013 | −0.00217 | −0.00026 |
| `dwell` (uw_share) | 10 | −0.00956 | +0.01226 | −0.00286 | +0.00116 |

**Read:**
- **The ratio/retention family is the standout**, and it wins on *both* axes: highest family
  median rho after `reclaim` (which has only 5 members), the best dollar-recall@10 in the
  whole screen (`Lg_retention_best_tnone_p0_rank`, +0.01193), and it does it on 24 members
  rather than 240.
- **Triple-barrier screened at essentially zero** (family median rho_vs_net60m
  **+0.00010** over 90 members) — the largest non-dollar family in the grid and the one the
  literature calls canonical. This independently reproduces the house refutation and the
  AEDL benchmark's Sharpe ≈ 0 for plain TB. Four of the fifteen worst labels in the screen
  are `tb_*` members.
- **`dwell` / time-underwater screened WORST** by family median (−0.00956) and owns the
  single worst label in the screen (`Lg_uw_share_close_tnone_p0_rank`, rho −0.059,
  dr@10 −0.01047). Note that `uw_share` nonetheless made the confirm list — see §2.3.
- **`fav_first` never produced a positive member** (best rho −0.00013 over 15 members).
- The `dollar` family's *breadth* is misleading: 240 members, but the winners are almost
  entirely `net_close` and `net_120m` under `rank`/`z`, i.e. the family wins by *transform*
  and *horizon*, not by base.

## 2.2 Label-level screen leaders

**Top 10 by rho_vs_net60m** (`ARCHIVE/lab/ledger_screen.tsv`):

| label id | family | rho_vs_net60m | dr@10 | rho_median |
|---|---|---:|---:|---:|
| `Lg_net_close_tnone_p0_rank` | dollar | **0.07956** | 0.01066 | 0.18123 |
| `Lg_retention_best_tnone_p0_rank` | ratio | 0.07716 | **0.01193** | 0.18289 |
| `Lg_retention_close_tnone_p0_rank` | ratio | 0.07432 | 0.01070 | 0.17494 |
| `Lg_net_close_tnone_p10m15k_rank` | dollar | 0.07403 | 0.00679 | 0.19199 |
| `Lg_net_close_tnone_p05m30k_rank` | dollar | 0.06579 | 0.00986 | 0.18350 |
| `Lg_net_close_tnone_p05m15k_rank` | dollar | 0.06442 | 0.00876 | 0.16541 |
| `Lg_net_close_tnone_p0_z` | dollar | 0.06264 | 0.00385 | 0.17296 |
| `Lg_net_close_tnone_p05m10k_rank` | dollar | 0.06065 | 0.00801 | 0.17883 |
| `Lg_net_close_tnone_p10m10k_rank` | dollar | 0.06013 | 0.00614 | 0.19435 |
| `Lg_net_close_tnone_p10m30k_rank` | dollar | 0.05735 | 0.00840 | 0.18114 |

**Top 5 by `rho_median` (pure learnability against the label's own truth)** — a completely
different ordering, and the reason the screen refused to rank by own-loss:

| label id | family | rho_median | rho_vs_net60m |
|---|---|---:|---:|
| `Lg_mfe_best_tnone_p0_rank` | gain | **0.42221** | 0.01304 |
| `Lg_mfe_close_tnone_p0_rank` | gain | 0.41819 | 0.00935 |
| `Lg_mfe_close_tnone_p0_z` | gain | 0.41642 | 0.00023 |
| `Lg_fp40_120m_tnone_p0_rank` | first_passage | 0.40917 | 0.01369 |
| `Lg_fp20_30m_tnone_p0_raw` | first_passage | 0.38653 | 0.00428 |

**This is the single most important screen finding for the port.** MFE and first-passage
labels are by far the *most learnable* objects in the grid (rho ≈ 0.37–0.42, 5× anything
else) and among the *least economically aligned* (rho_vs_net60m ≈ 0.00–0.015, dollar-recall
mostly negative). A label can be highly predictable and still order no money. Any port
atlas must score learnability and economic alignment **separately** — which is exactly what
the current repo's atlas discipline already requires
(`/workspace/DISCRETIONARY_METHOD.md` §9.3 (a) learnability screen / (b) ECONOMIC ALIGNMENT).

## 2.3 What Stage B confirmed (the top-25 the screen actually promoted)

`ARCHIVE/lab/specs/label_confirm_v1.yaml` carries the screen's top-25 verbatim (26 ids +
7 seeds). Its **family composition is itself a result**:

`cfa_wait_rod` ×3 · `net_best` ×3 · `uw_share` ×3 · `fav_first_*` ×3 · `fp` ×3 ·
`mfe` ×3 · `race` ×3 · `retention` ×3 · `reclaim_evt` ×2.

**ZERO triple-barrier members and ZERO `ttp` members reached the confirm set** — out of
90 and 10 candidates respectively. That is the recovered atlas's own verdict on
triple-barrier: enumerated in full, screened in full, promoted zero.

## 2.4 The round-by-round adjudications (Stage B and beyond)

`ARCHIVE/lab/receipts/round1_champion.md` §7 — after 22 confirmed arms:

> "Within-session rho tops out at **+0.085** (retention rank at close); only one other of
> the 22 arms clears +0.03 and **18 sit inside |rho| ≤ 0.025**."
> "**Rank/geometry labels beat dollar regressions by 3–6× on rank quality** (retention rank
> +0.085 and +0.045 vs net regressions +0.004 to +0.025)… C-class objectives win; the label
> grid should re-expand along the retention/ratio axis, not the dollar axis."

`ARCHIVE/lab/receipts/round2_champion.md` §1b — the retention-axis confirm (matrix v2,
matched control = round 1's champion label refitted under the round-2 budget):

| arm | rho vs net_60m | rho vs net_close |
|---|---:|---:|
| `Rx_ret_close_e5000_gated_rank` | **0.08579** | **0.22350** |
| `Rx_gbfrac_close_e5000_rank` | 0.08494 | 0.21401 |
| `Rx_ret_close_e1500_rank` | 0.07285 | 0.20467 |
| `Rx_ret_close_e15000_rank` | 0.08860 | 0.20245 |
| `Rx_rrreal_close_e5000_rank` | 0.06382 | 0.19045 |
| `Rx_gbshare_close_e5000_rank` | 0.08729 | 0.18931 |
| `Lg_retention_close_tnone_p0_rank` **(matched control)** | 0.06107 | 0.18134 |
| `l13_isotonic` (the repaired L13 classifier) | −0.00777 | 0.00703 |
| `l19_q90_fixed` (the repaired L19 quantile head) | −0.00043 | −0.00127 |

**6 of 8 confirmed arms beat the matched control on BOTH rank metrics; best +23% on
rho_close.** Both repaired round-1 defects came back **INERT** — "so neither defect was
costing anything."

`ARCHIVE/lab/receipts/round3_champion.md` §1b/§1c/§1d/§3 — three results that constrain any
port re-run:

1. **The shadow-value channel is real at 60m and degenerate at close.** At the close mark
   the occupancy rule admits one fill per session, so `shadow_close(a) ≡ net_close(a) −
   optimal_close(session)` **exactly** (max abs deviation $0.0) and
   `rank(shadow_close) ≡ rank(net_close)` exactly. At 60m that identity **fails on 100% of
   rows** (max deviation $16,404). Best arm `Sd_shadow_close_rank` 0.0689 / 0.2005; every
   60m shadow arm ≈ 0. The DP cross-checks against the published ceiling: expected
   $2,977.23, got $2,977.2258 (Δ −0.0042) by a *different algorithm*.
2. **The shuffle guard held.** All six `*_SHUF` twins land in [−0.0042, +0.0111] on both
   rank metrics — no arm was memorising session identity.
3. **The transform margin is one ordering, not three — proved.** `raw`, `z` and `rank` of
   the retention base carry the *same* within-session ordering (max abs percentile
   deviation **0.00e+00** over 688,476 rows), because `_session_mad_z` divides by the
   session MAD without centring. So every difference between those arms is produced
   entirely by what the pooled squared-error loss does with the label's SCALE — "the
   transform margin is not a search over labels; it is a search over implicit session
   weightings inside an objective that was never the metric." Meanwhile `winsor99` vs
   `rank` deviates by 0.266 — the clip is monotone but **not strictly** monotone.
4. **The label, not the search, is the binding constraint.** Same label, same matrix,
   32→60 HP configs: rho_close +0.00218. Changing only the *transform* of that same label
   moves it 0.31688 — **145×** as much.

## 2.5 The screen→confirm REVERSAL, and the ranking-objective refutation

Two results here are more transferable than any single label's number.

**(a) Stage A rank did not survive Stage B — and the direction of the failure is the
lesson.** `ARCHIVE/lab/receipts/round1_diagnostics.md` grades the 22 confirm arms'
*standalone* dollar controls:

| arm | Stage-A standing | standalone control, best `mean_1003` |
|---|---|---|
| `reten_cl` = `Lg_retention_close_tnone_p0_rank` | 3rd by rho_vs_net60m; **bottom-quartile by rho_median** | `CTL_reten_cl` **$130.23** — best of all 22, and it beats the 5-way composite `D2rank` it feeds ($51.04) |
| `fp40` = `Lg_fp40_120m_tnone_p0_rank` | **4th-best rho_median in the entire 539-label screen (0.409)** | `CTL_fp40` **$3.74** — the weakest of all 22 |
| `netb15k` = `Lg_net_best_t15k_p0_z` | highest Stage-A rho_median among the remaining constituents (0.280) | `CTL_netb15k` $5.29 |

**A label that screened 4th-most-learnable out of 539 produced the weakest standalone
dollar arm of the confirm set, by 35×.** Round 1's confirmed rank block says the same thing
in rho: champion `reten_cl` +0.08485 (net_60m) / +0.18753 (net_close), dollar-recall@10
+0.01502; `fp40` **−0.00869**; the worst arm is the seed `L06 net_60m_trunc150` at
**−0.02562**. Eight of 22 arms showed a sign disagreement between declared and measured
orientation — all at |ρ| ≤ 0.014, below the harness's resolution floor, so recorded as
unresolved rather than as real flips. Two roster defects were recorded rather than hidden:
L19 actually ran `reg:squarederror` not q90, and no confirm arm was a true calibrated
classifier. Both were repaired in round 2 and both came back inert.

**(b) Round 4 replaced the CARRIER and the ranker objectives LOST.**
`ARCHIVE/lab/receipts/round4_champion.md` §1/§3, 18 roster fits + 2 objective-matched
side+clock nulls, all on 482,456 OOF rows / 626 sessions — the same rows round 3's bar used:

| arm | kind | objective | rho vs net_close | rho vs net_60m | dr@10 |
|---|---|---|---:|---:|---:|
| `K4_reg_netcl` | control | `reg:squarederror` | **0.23768** | 0.08966 | 0.01288 |
| `Rt_retg_close_rank` | carry-over | `reg:squarederror` | 0.22568 | 0.08586 | 0.01332 |
| `K4_reg_retg` | control | `reg:squarederror` | **0.20229** | 0.09679 | 0.01318 |
| `K4_nde8k10_retg` | ranker | `rank:ndcg` (exp gain, k=10) | 0.18406 | 0.03518 | 0.00566 |
| `K4_ndl32k10_retg` | ranker | `rank:ndcg` (linear, k=10) | 0.17335 | 0.04307 | −0.00102 |
| `K4_pw_retg` | ranker | `rank:pairwise` | 0.04720 | 0.01444 | 0.03892 |
| `K4_pw_netcl` | ranker | `rank:pairwise` | **−0.03318** | −0.01880 | 0.03214 |

> "**0 of 15 ranking cells beat their own matched pooled control on within-session rho vs
> net_close; the median delta is −0.07122, the best −0.01822 (`K4_nde8k10_retg`) and the
> worst −0.27087 (`K4_pw_netcl`).**"

20 of 22 arms beat their objective-matched side+clock null on both legs (failures:
`K4_nde8k10_net60`, `K4_pw_netcl`). The round also reports its own confound honestly:
round 4's 24/2 HP budget sits −0.02340 below round 3's 60/4 on rho_close, "which is 11×
the +0.00218 round 3 measured", so cross-round ranker-vs-bar comparisons are refused and
only the ranker-vs-matched-control comparison is read.

**The distinction the port must not lose: the RANK TRANSFORM of the label wins; the
RANKING OBJECTIVE loses.** `rank`-transformed continuous labels fitted under plain
squared error beat dollar regressions 3–6× (§2.4) — while `rank:ndcg` / `rank:pairwise`
*objectives* on the identical labels lost every matched cell. Round 1's pre-declared class
(d) "capacity/objective gap — rank arms ≫ regression arms ⇒ C-class objectives win" was
therefore **half right and half refuted**: it was the label's geometry, not the loss's
shape.

**(c) The surviving champion label of the whole tournament** is
`Rt_retg_close_rank` ≡ `Rx_ret_close_e5000_gated_rank` (byte-identical arrays, proved) —
`net_c(close) / max(mfe_c(close), 5000 cents)`, mover-gated, within-session rank —
at rho_close **0.22568** / rho_60m 0.08586 / dr@10 0.01332. Its lineage runs unbroken from
the Stage-A `ratio` base through four rounds and was never displaced by any dollar-space
seed (L01–L11) or by any ranking-objective reformulation.

**HONESTY RAIL, carried forward verbatim:** the whole grid's trial count enters the
multiplicity ledger (`ARCHIVE/lab/ledger_screen.tsv`); Stage A is not a champion claim;
`promotion: false` on every confirm spec; folds 6/7 were never touched and the leak guard
was **shown to fail** (planting a fold-6 row raises), not merely asserted.

---

# 3. THE ENGINE — how thousands of labels were computed fast

Two generations of engine exist in the archive and they solve the same problem the same
way. **The invariant: compute the path ONCE per anchor into a fixed-shape first-passage /
extrema structure; every label is then a pure query over that structure, never a re-read of
the tape.**

## 3.1 Generation 1 — the row-wise reference (`label_atlas`)

`ARCHIVE/docs/specs/label_atlas_v1.md`. Exact, row-wise, integer-tick semantics; the
correctness oracle, not the scale layer. It is the parity target the tensor engine must
agree with byte-for-byte on synthetic data.

## 3.2 Generation 2 — the LABEL TENSOR ENGINE (the actual speed mechanism)

`ARCHIVE/docs/specs/label_tensor_engine_v1.md`. **The whole design is one arithmetic
observation:**

> "The production-sized candidate population has 89,587 rows. Four independent anchors and
> six registered horizons produce **2,150,088 primitive rows**. The row-wise representation
> would additionally produce **25,801,056 rows** for only the twelve current reference
> barriers. This engine retains the 2,150,088 primitive rows and **stores first-touch
> values in fixed nested Arrow tensors, so wide risk/reward sweeps do not multiply the
> physical row count.**"

Mechanism, in the order it executes:

1. **Registered axes, pinned.** Anchors `d0..d3` (delays 0–3 min, independent hypothetical
   closes). Horizons `m5, m15, m30, m60, m120, session_close`. Competing-barrier tensor:
   adverse-risk ticks `[5, 10, 20, 40, 80, 100, 200, 400]` × integer reward ratios `1..8`;
   favorable thresholds are the **row-major outer product** of risk and ratio =
   **64 registered risk/reward cells** per primitive row, covering 1:1 through 8:1. Axis
   order and matrix order are committed in the registry and in the Parquet metadata.
2. **One forward pass per primitive row.** Prefix maxima over the forward interval supply
   MFE and MAE; the first equal maximum supplies the one-based time-to-extreme (zero
   maximum → time zero). Observed range is exactly `MFE + MAE`.
3. **The lossless first-touch tensor.** Per primitive row the engine stores a
   **fixed-size favorable first-passage vector of `risk_count × ratio_count`** and a
   **fixed-size adverse first-passage vector of `risk_count`**. Each value is the first
   one-based observed minute whose *prefix maximum* reaches the threshold; null = no touch.
   A row with no observed bars is distinguished by `observed_bars == 0`, so a null touch
   means *unavailable*, never ordinary no-hit.
4. **Every barrier label is a decode, not a scan.** `decode_barrier_cell` derives the exact
   scalar contract **without reading the path again**: hit flags, both first-passage times,
   favorable/adverse winner, same-bar ambiguity, event censoring, event availability, and
   regime. **Both hit times are retained even when one barrier wins** — which is what makes
   asymmetric R:R sweeps, survival heads and competing-risk heads free.
5. **The kernel boundary is named and swappable.** `numpy-prefix-searchsorted-v1` — prefix
   maxima plus `searchsorted` for the passage times. "A later Rust kernel may replace
   `_first_passage_times` only after it passes the same parity suite and preserves Arrow
   types and identities."
6. **Bounded columnar execution.** Candidates processed in bounded chunks: default 512
   candidates → at most 12,288 primitive rows; hard maximum 1,024 → at most 24,576.
   Numeric outcomes are NumPy arrays, first-passage tensors are Arrow fixed-size lists,
   string/numeric builders live only for the current batch. **"The engine never accumulates
   the complete multi-million-row output as Python dictionaries."** Whole-table collection
   is testing-only and fails above 250,000 rows. No import performs I/O; no path discovery.
7. **Structural scaling tests assert the property, not a wall-clock.** The suite asserts the
   batch bound, the fixed tensor shape, exact cardinality, and **"that increasing barrier
   cells does not increase physical row count."** "No wall-clock threshold is a test gate."

**The same factorization, restated independently in the clean-NBBO contract**
(`ARCHIVE/docs/specs/iwm_clean_nbbo_label_atlas_v1.md`): store first favorable touch and
first adverse touch *independently* per threshold — "This factorization represents **all 121
favorable/adverse triple-barrier pairs** without storing or scanning 121 redundant cells."
"No redundant cross-product passage table is published. Derived target views bind the
parent wide-row ID, exact parameter tuple, and deterministic derivation ID."

## 3.3 The KERNEL layer — O(log n) queries, not O(window) scans

`ARCHIVE/docs/specs/label_kernel_design_v1.md`. Per session, built once and shared by all
families:

- Evaluation frame: `ts_ns[g]`, `m_lo[g]`, `m_hi[g]` per quote group, a bar table for the
  registered one-minute clock, a group→bar index array, and the anchor set (one anchor per
  event-signal row × slot d1/d2/d3). **Frame build is O(n).**
- **An extrema segment tree over groups**, nodes holding `(max m_hi, min m_lo, argmax,
  argmin)`. Build O(n), memory O(n). It answers `range_max(a,b)` / `range_min(a,b)` →
  value + first attaining index in **O(log n)**, and `first_at_or_above(a,X)` /
  `first_at_or_below(a,X)` by **tree descent** in **O(log n)**.
- **Explicitly FORBIDDEN (the R1 performance law):** "any O(window) scan per anchor for
  these four families; any per-cell hashing; any shared mutable cache across anchors; any
  byte-recount accounting in hot loops."
- Per-family cost: F-EXT = O(log n) per quantity (retention/giveback is *one extra range
  query*). F-PASS = **22 descent queries + O(1) merge per anchor** (11 rungs × 2 sides).
  F-TERM = O(log n) binary search per horizon. **F-ORD = pure O(1) derivation per anchor,
  no new scans** — the ordering states fall out of F-PASS's outputs.
- Per-session total: `O(n) frame + O(n) tree + O(A·log n)` with `A ≈ events × 3`.
  **"At ~14k events/day this is milliseconds."**
- All u6 arithmetic is exact integer; bps→threshold is the exact registered integer formula
  `distance_u6 = ((anchor_u6*bps + 9_999)/10_000).max(1)` in i128 — **"no floating-point
  price math anywhere."**

## 3.4 The label-panel layer (the lab-side, one-pass equivalent)

`ARCHIVE/lab/labels_panel.py` is the same idea at 1-second grain: **one pass over the PP1
one-second mid grid emits the atoms, then the entire 541-member grid composes over them
with zero further I/O.** Per action it computes `cmax = np.maximum.accumulate(g)` and
`cmin = np.minimum.accumulate(g)` once, then every rung is a single
`np.searchsorted(cmax, level, side="left")`. Rung union is chosen to cover every family:
up levels `(20,40,60,100)` bps (race θu ∪ tb pt), down levels `(10,15,20,30,40)` bps
(race θd ∪ tb sl). Also emitted: `uw_share`, `g_bps`, `gmax/gmin` per horizon,
`sigma_hat_bps`, `ttp_sigma_s` + `ttp_censored`, `path_seconds_available`, `cfa_wait_K`,
and the reclaim components.

**The convention is MEASURED, not assumed** — a discipline the port must copy verbatim:
entry second `= cutoff_bar_ordinal*60 − 1` beat candidates `b*60` (88.5 u6) and `(b−1)*60`
(357.7 u6) at median |err| 44.2 u6 vs the book's own MFE; side sign `HIGH = SHORT` beat
`HIGH = LONG` by 2,772.8 → 44.2 u6. Reproduction of the book's `mfe_frac_u6_60m`:
median |err| **23.1 u6 = 0.231 bps**, p90 74.2 u6 — recorded as a *resolution* limit of the
1-second grid, not a convention disagreement.

## 3.5 Correctness discipline that made the speed trustworthy

- **Independent Python oracles** at `ARCHIVE/oracle/labels/`: brute-force direct scans
  (O(n) per anchor is fine there), "written by workers who never see the Rust kernels — same
  spec + CONV doc only", with a comparator requiring **byte-exact equality** on all fields
  across ~20–22 stratified sampled sessions including named edge days.
- **A reference parity gate**: the tensor engine's synthetic suite compares *every*
  overlapping primitive field and every current scalar barrier field against
  `build_label_atlas` — seeded property paths, winter/summer offsets, early closes,
  long/short, same-bar ties, later-bar competing touches, gaps, repeated/zero extremes,
  near-close partial censoring, no-post-anchor rows, exact-close fits, and caller/registry
  reordering. A separate direct-path regression checks all 64 risk/reward cells across 240
  primitive rows = **15,360 cells**.
- **Deterministic identity**: every primitive carries the reference atlas label ID plus a
  tensor row ID committing candidate ID, normalized anchor/horizon, schema, registry, the
  complete path slice, every primitive value, censor/interval state, and both first-touch
  tensors. Rows and registries are canonically sorted, "so caller order cannot change IDs".
- **A published audit**: 89,587 candidates × 4 anchors × 6 horizons = exactly 2,150,088
  primitive rows × 64 cells; the audit reconciled 512 candidates across every anchor and
  horizon — **12,288 primitive rows and 749,568 fields** checked against source paths.
- **The label-leaf reconciliation** (`select2_label_catalog_census_v1.md` §4a): 1,003
  leaves, 13,901,670 rows, census identity HOLDS exactly, `ledger_only = 0` and
  **`at_risk_disagreements = 0` across all 13.9M shared subjects** from two independent
  derivations of at-risk.

---

# 4. PORT ADAPTATION NOTES (futures: SI / NKD / HG, 23h sessions, MBP-1 event grain)

Grounding: `/workspace/DISCRETIONARY_METHOD.md` §7 (port design rulings), §8.2 (labels
L1–L6), §9.1 (the path-skeleton engine), §9.2 (families F-A…F-K), §9.3 (atlas discipline);
`/workspace/DATA_INVENTORY.md` §1 (47GB Databento GLBX MBP-1, 2021→2026, 2026 sealed).

**4.1 The engine ports unchanged — and the port already specced it.** §9.1's path-skeleton
("ONE forward pass computes `tau_up[k]`/`tau_dn[k]` over a ~200-rung ATR-scaled ladder each
side + MFE/MAE at the horizon grid + running-extremum landmarks. ~1KB per candidate…
EVERY label is then a QUERY (no tape re-read)") **is the label-tensor-engine design
rediscovered.** Port it with the recovered specifics rather than re-deriving them: fixed-size
first-touch tensors (never a materialised cross-product), both hit times retained even when
one side wins, `observed_bars == 0` distinguishing *unavailable* from *no-hit*, prefix-max +
`searchsorted` as the named kernel boundary, bounded chunking with an explicit primitive-row
cap, and the structural test that **increasing barrier cells must not increase physical row
count**. The segment-tree layer (§3.3) is the upgrade path if per-anchor range queries over
irregular event streams become the bottleneck.

**4.2 Horizons: the 23h session pluralizes "close", so the horizon axis gains a dimension.**
The recovered grids all assume one `close`. The port's L2 replaces it with
`{2,5,15,30,60,120min}` **+ PHASE BOUNDARIES (Tokyo close / London-NY handoff / NY close)
as first-class horizons**. Two recovered results make this load-bearing rather than
cosmetic: (a) `close` and `120m` dominated the screen's rho leaderboard while `60m`/`30m`
did not — the *longest available* horizon carried the signal; (b) the round-3 shadow
degeneracy is a **pure function of the occupancy ratio** `horizon_bars / session_bars`
(at close, one fill fits a session and the channel collapses to `rank(net_close)`; at 60m,
5–6 fills fit and the channel is new). In a 23h session that ratio changes completely, so
**each phase boundary must be checked for the degeneracy separately** — it is a property of
the mark, not of the label.

**4.3 Family mapping — what ports, what is N/A-until.**

| recovered family | port status | note |
|---|---|---|
| A1 F-PASS / B4 `fp` / E9-E10 / F10 | **PORTS DIRECTLY** → §9.2 **F-D first-passage races**. Rungs become ATR-relative, not bps | The ~200-rung ladder subsumes the 11-rung IWM ladder |
| A2 F-ORD / B7 `race` | **PORTS DIRECTLY** → F-D. Carry the recorded tie rule (`labels.py`: simultaneous touch resolves to −1) and the typed `SAME_GROUP`/`NEITHER_*` states — MBP-1 event grain makes true simultaneity *more* common than IWM's ms groups, not less | The IWM corpus measured `SAME_GROUP` = **0 across 41.7M rows**, so the dual-touch cell was refused for an empty positive class. **Re-measure on futures before assuming it is empty** |
| A3/A4/A5 F-EXT, B2 `mfe`, B3/C1–C7 ratio axis, E2-E8 | **PORTS DIRECTLY** → §9.2 **F-E MFE/MAE ratio classes**, **F-F certificate + MAE-budget ladder** | Carry the ε-floor repair: `net/max(mfe,ε)` with ε derived per asset from its own cost scale, never copied. The 576c → per-asset round-trip substitution is the exact analog of the "$300 wall derived, not copied" ruling |
| A6 F-TERM / B1 `dollar` / E1 | **PORTS DIRECTLY** → §9.2 **F-A fixed-horizon nets** | Keep F-TERM's **interval** `(move_lo, move_hi)` shape — collapsing to a point was flagged design-bearing |
| A7 F-DWELL / B9 `uw_share` | **PORTS** → §8.2 **L4 PATH-SHAPE (time-underwater)** | Screened worst on IWM. It is retained in the port for a *different* purpose (predicting hold-shape, per L4), so score it on that, not on entry rank |
| A8 F-QPRIM / B10 `ttp` / H1 / H6 | **PORTS** as the survival layer | Zero members reached the IWM confirm set. The recovered advice is unambiguous: the estimator (Aalen–Johansen) was ready while the *head* was not — a censored time-to-event head needs a censoring-aware loss and a **two-value leaf** (time + censoring indicator). Budget that, or skip |
| A9 F-CFA / B6 `cfa_wait_K` | **PORTS, and gets easier** | The 23h session with three opens gives far more "later actions in the same session" than an RTH day. `cfa_wait_K` had no positive members on IWM but three `cfa_wait_rod` variants still made the confirm top-25 |
| A10 F-CTRL / B8 `tb` | **PORTS** → §9.2 **F-B TRIPLE-BARRIER** (R:R {1:1,2:1,3:1,4:1} × scale {0.25,0.5,1,1.5}×ATR × time-barrier grid) | **Carry the negative.** 90 members screened at family median +0.00010, zero promoted. Run it as the literature *control* the census called it, priced at that expectation. The recovered diagnosis is the reconciliation, not a blanket ban: TB fails as **label/deploy MISMATCH** ("right-tail amputation"), so an ATR-scaled TB whose barriers match the port's actual wall+hold exit posture is a *different* experiment from IWM's |
| A11 F-DIR / B11 `reclaim_evt` | **PORTS** — and it screened best by family median (+0.01393) on only 5 members | Event-state-conditioned direction is exactly what §7 law 3 (refail-cluster / flow-flip / book-side-collapse confirmations) generates. **Expand this family in the port** — the IWM version had 5 members and no parameter grid |
| A12 F-RANK / B1-rank / L15/L16 | **PORTS, high priority** → §9.2 **F-J RANK LABELS** (rank within session/phase) | The strongest recovered signal: rank/geometry beat dollar regressions **3–6×** on rank quality. **But port the rank TRANSFORM, not a rank OBJECTIVE** — round 4 fitted 15 `rank:ndcg`/`rank:pairwise` cells against matched squared-error controls on identical labels and **0 of 15 won** (§2.5b). Also see 4.5 — the ranking *unit* must be re-chosen for a 23h session |
| A13 **F-PROX** | **BARRED — port the bar, not the family** | Reimplement `assert_no_fprox()` over the port's enumerated grid and its atom builder |
| A14 distributional head shapes | **PORTS as shapes**, applied over the continuous port families | Blocked on the same continuous-decoder work; budget it as ×levels on every continuous family |
| A15 regimes / L6 | **PORTS as the CONDITIONING axis, never a head** | §8.2 L6 already stores regime keys *with* labels. Preserve the prohibition: labels do not vary by regime |
| **NEW in the port** | §9.2 **F-C trailing-stop widths**, **F-G path-shape**, **F-H meta-labels**, **F-I level-to-level**, **F-K rotation-vs-extension** | F-I and F-K have no recovered antecedent — they are level/profile-native and genuinely new. F-C is the exit-menu envelope (§1G G15) in mechanical form. F-H is H15 meta-labeling |

**4.4 N/A-UNTIL — families that need instruments the port does not have.**

| family | blocker | status |
|---|---|---|
| **Options/IV-derived label conditioning** — the F4 option-book arm, `PROXY_VOL` innovations, Greek-residual repricing, option-tape-silence-at-extremes, GEX | **No options layer on SI/NKD/HG.** `/workspace/DISCRETIONARY_METHOD.md` §9.4: "GEX framework does NOT port (no options)" | **N/A-UNTIL** an options/IV source exists per asset. Substitutes already banked: realized-vol constructions (§8 V1: pre-averaged/bipower RV + **jump separation** + Parkinson/GK/RS range estimators + vol-of-vol), Nikkei VI daily, FRED VIX/RVX/VXD, GVZ. These are *daily context*, not an intraday surface — do not let a daily vol series stand in for a per-candidate IV label |
| **A13 F-PROX / truth-relative proximity** | barred by ruling, not by data | **NEVER** |
| **G2 tail-set labels (cross-sectional quantile membership)** | needs a *universe* at each timestamp | **N/A-UNTIL** the three futures are traded as a cross-section. With SI/HG/NKD there is a 3-name universe — thin, but the port's cross-asset modality (§8.3 modality 4: "the three assets are each other's context streams at event grain") makes a **within-triple rank label** newly buildable where IWM had no universe at all. Mark as a genuinely new port opportunity, not a port |
| **I10 SAR-PU (unmatched ≠ negative)** | needs a registered *truth set* to define verified positives | **N/A-UNTIL** the port builds a truth/opportunity registry. Note the tension: the port's own atlas discipline bars proximity-to-truth *labels* (F-PROX) while SAR-PU needs truth *membership* for the classification head. Resolve before either lands |
| **I11 Snorkel label model** | architect scoped it to the SIGNING engine | **N/A-UNTIL** a multi-labeler signing problem exists. MBP-1 gives quote-certified fills, so the aggressor-sign ambiguity that motivated it may simply not arise |
| **A9 F-CFA WAIT value model / I15 distributional value-of-waiting** | registered to a later stage (SELECT.4) on IWM | **DEFER**, but the port's 3-opens-per-day structure makes the WAIT decision *more* valuable, so revisit the deferral |

**4.5 The event-grain and 23h-specific cautions.**

1. **Preserve event grain in the labels, not just the features.** §7 law 5: "the MBP-1
   order-event stream is never aggregated away." The recovered engine already computes on
   *quote groups* (`m_lo/m_hi` per equal-timestamp group) rather than bars, with an explicit
   `Scalar` vs `Heterogeneous` group kind and an `INTERVAL_AMBIGUOUS` touch state. **Port
   that typing directly** — on MBP-1 an equal-timestamp group is the native atom, and
   flattening it to a bar OHLC reintroduces exactly the `same_bar_ambiguous` guessing the
   IWM atlas refused to do.
2. **The ranking unit changes.** Every recovered rank/z label is **within-session**. In a
   23h session with three opens, "within-session" spans three regimes. `L6`/§9.2 F-J
   already say "within session **or phase**" — the recovered evidence says the transform
   axis is really a *session-weighting* axis (§2.4 result 3), so **the ranking unit is a
   first-class experimental axis in the port, not a formatting choice.** Enumerate
   `{within-phase, within-session, within-day}` explicitly.
3. **Re-derive every constant, never copy one.** The recovered atlas is full of
   IWM/RTY-native constants: 576c round trip, $15k/$30k truncation rungs, ε∈{576,1500,5000,
   15000}, the 5–240 bps ladder, the 5–400 tick barrier grid, the $300 wall. **All are
   `N/A-until re-measured per asset.**  §8.2 L1 already binds this ("WALL DERIVED, not
   copied: per asset = round(p99 of winner MAE) from the census"). SI's $25 tick makes the
   cost-scale substitution non-optional.
4. **Score learnability and economic alignment separately, from the first run.** §2.2's MFE
   / first-passage result (rho_median 0.42 with rho_vs_net60m 0.01) is the single most
   transferable finding in this document, and §2.5a is its consequence measured in dollars:
   the 4th-most-learnable label of 539 produced the weakest standalone confirm arm
   ($3.74 vs the champion's $130.23). `/workspace/DISCRETIONARY_METHOD.md` §9.3 already
   mandates both scores; the recovered numbers say what happens if you only keep the first.
6. **Do not spend the port's budget on ranking objectives.** §2.5b closed that door with
   15 matched cells. Spend it on the label's *geometry* (ratio/retention-class constructions
   with a derived denominator floor) and on the *ranking unit* (4.5.2) instead.
7. **Restore the grid code before the port's atlas run.** `/workspace/lab/` is currently
   `run.sh` + `watchdog.sh` only; `labels.py`, `labels_panel.py`, `labels_retention_axis.py`,
   `labels_shadow.py`, `fit.py`, `specs/`, `receipts/`, `ledger*.tsv` exist only in the
   archive. The 153 live `fit_receipt.json` files under
   `/workspace/artifacts/runs/select_v2_fits_v1/` are the surviving primary numbers and
   should be read directly rather than re-derived from prose.
5. **Carry the multiplicity ledger and the shuffle guard.** The whole grid's trial count
   enters a Holm family (§9.3 already says this); and every occupancy-aware or oracle-derived
   label gets a within-session-shuffled twin at identical budget on an identical universe
   (§1D). The port's shadow/DP-derived labels are exactly the class that guard exists for.

---

## Appendix — source file inventory (all paths under `ARCHIVE/`)

| layer | files |
|---|---|
| Taxonomy 1A | `docs/specs/select2_label_catalog_census_v1.md`; `docs/specs/label_kernel_design_v1.md`; `docs/specs/label_probe_schema_v1.md`; `engine/crates/labels/`; `engine/crates/select/src/{label_leaf.rs,label_leaf_builder.rs,near_family_labels.rs,round3_fit_labels.rs}`; `engine/crates/cli/src/label_leaf_cmd.rs` |
| Taxonomy 1B | `docs/designs/label_atlas_and_objective_v1.md`; `lab/labels.py`; `lab/labels_panel.py`; `lab/specs/l01..l19_*.yaml` |
| Taxonomy 1C | `lab/labels_retention_axis.py`; `lab/specs/round2_retention_{axis,confirm}.yaml` |
| Taxonomy 1D | `lab/labels_shadow.py`; `lab/specs/round3_{shadow_confirm,retention_treatment,retention_bin10}.yaml` |
| Taxonomy 1E | `docs/specs/label_atlas_v1.md` |
| Taxonomy 1F | `docs/specs/iwm_clean_nbbo_label_atlas_v1.md` |
| Taxonomy 1G | `docs/specs/labeling_sota_research.md` |
| Taxonomy 1H | `docs/specs/label_design_research.md` |
| Taxonomy 1I | `research/review_records/label_crossdomain_research_v1.md`; `research/review_records/label_crossdomain_research_architect_v1.md` |
| Screen / confirm | `lab/specs/label_screen_v1.yaml`; `lab/specs/label_confirm_v1{,_p0..._p4}.yaml`; `lab/specs/smoke_label_screen.yaml`; `lab/ledger_screen.tsv`; `lab/ledger.tsv`; `lab/receipts/round{1,2,3,4}_champion.md`; `lab/receipts/round1_diagnostics.md` |
| Engine | `docs/specs/label_tensor_engine_v1.md`; `docs/specs/label_kernel_design_v1.md`; `docs/specs/label_probe_schema_v1.md`; `oracle/labels/` |
| Port grounding (current repo) | `/workspace/DISCRETIONARY_METHOD.md` §7–§9; `/workspace/DATA_INVENTORY.md`; `/workspace/PROGRAM_RECORD.md:28` |
| **LIVE artefacts (not in the archive)** | `/workspace/artifacts/runs/select_v2_fits_v1/` — 153 `<spec>__<label_id>/fit_receipt.json` + `oof_scores.parquet` + per-fold `.ubj` models, covering `label_confirm_v1{,_p0..p4}`, `round2_retention_confirm_*`, `round3_{retention_treatment,retention_bin10,shadow_confirm}_*`, `round4_rank_objective_*`; plus the **truncated** `label_screen_v1/screen_receipt.json` (154/541 scored) |

**Referenced by the sources but NOT present in the archive snapshot** (recoverable only
through the quotations in `select2_label_catalog_census_v1.md`):
`docs/specs/family_schemas/*.md` (f_dwell, f_qprim, f_cfa, f_ctrl, f_dir, f_rank, f_prox,
regimes schemas), `docs/MASTER_HANDOFF.md` §11.3 (the registered catalog itself),
`docs/specs/events3_design_v1.md`, `events3_formula_addendum_v1.md`,
`events3_design_amendment_v2.md`, `docs/specs/registered_conventions_extract_v1.md` (CONV),
`docs/specs/select2_round1_plan_{v1,SEALED_v1}.md`,
`docs/specs/selection_s0_substrate_contract_v1.md`,
`docs/specs/program_milestone_bars_v1.md`, `docs/specs/select_strategy_once_over_v1.md`,
`docs/specs/opportunity_bottleneck_v1.md`,
`artifacts/runs/select_v2_fits_v1/label_screen_v1/screen_receipt.json` (the screen receipt
the confirm specs point at — **absent**; its content is reconstructible from
`lab/ledger_screen.tsv` and the confirm specs' own top-25 lists).

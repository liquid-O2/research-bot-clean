# RANKING ATLAS — THE PRE-REGISTERED GRID

**Status: PRE-REGISTRATION. Committed before a single screen number exists.**
This file is the atlas law for the ranking act, modelled verbatim on
`design/LABEL_ATLAS_V2.md`'s discipline. Engine: `engine/port_m2/rank_atlas.py`
(+ `atlas_feat.py`, `newobj.py`, `newobj_arms.py`). Version `PORT-M2-RANK-ATLAS-V1`,
seed `20260813`.

---

## 0. THE FORMAL PROBLEM, AND THE CITE-THEN-VERIFY LAW

What the champion actually does, stated in its own terms: **inside each
(asset, day, phase) cell it observes a set of alternatives and picks one.** That
is not regression and it is not binary classification. It is a **repeated
discrete choice over a varying choice set** — equivalently, **cross-sectional
ranking**. Two mature literatures own this object, and both are already
implicitly present in our own machinery:

| our object | econometrics | finance / IR |
|---|---|---|
| the cell as the competition set | **conditional logit** (McFadden 1974): choice among alternatives in a *choice set*, the alternative-specific covariates entering a single index | the cross-section on one date |
| cell grouping | the **fixed-effect / within estimator** — the cell absorbs everything common to it, leaving only *within-cell* contrasts identified | per-date cross-sectional ranking (the standard asset-ranking design) |
| cell-relative features | within-group demeaning / standardisation | **per-date standardisation** — the first thing done to any cross-sectional signal |
| per-cell softmax P@1 | **exactly McFadden's conditional-logit likelihood** | listwise IR (ListNet's top-1 probability) |
| NDCG@k grouped by cell | — | LambdaMART's home turf (the mature LTR field) |

This explains the largest measured jump in the program's history in one
sentence: **class-grouped −$23.88 → day-grouped $5.80 → cell-grouped $495.11**
was not a lucky hyper-parameter, it was moving from a mis-specified competition
set to the one the deployment actually uses. It also names, in advance, the
gap this atlas is built to test: our features describe an alternative **in
isolation**, while the identified variation is **within-cell**. A within
estimator fed only level covariates is being asked to recover a contrast it
cannot see.

**THE CITE-THEN-VERIFY LAW (binding).** Every recommendation drawn from either
literature enters this atlas **as a grid cell measured on our data**, never as
an adoption. Conditional logit is a *row*, not a conclusion. Per-date
standardisation is a *feature family*, not a decision. The literature's job here
is to enumerate hypotheses worth spending compute on; only our own walk-forward
dollars may promote one. Nothing in §0 is evidence.

---

## 1. THE AXES

| axis | levels | note |
|---|---|---|
| **grouping** | `day` · `assetday` · `class` · **`cell`** · `cellclass` · `joint` | the granularity sweep, coarsest → finest, **straddling** the champion's `cell` in both directions |
| **objective** | `ndcg3` · `ndcg1` · `softmax1` · `dpairs` · `q75` | `softmax1` = the conditional logit; `dpairs` = pairwise with the group weighted by its dollar spread; `q75` = pointwise 0.75-quantile |
| **target** | `dollars` · `cellrank` · `winner` · `maecap` | the value the grades are cut from |
| **population** | `full` · `recency` · `last2` · `classfilt` | which training rows, and with what weight |
| **engine** | `xgb` · `lgbm` · `catb` | `catb` = CatBoost with **Ordered** boosting |
| **feature set** | `BASE` · **`CELLREL`** · `DAYSOFAR` · `TABPFN` · `DIP` | the axis added because the diagnosis names it |
| *(policy)* | `static1` · `thresh` · `gate60` · `gate120` · `stop` | **post-hoc, not a fit axis — see P8** |

### 1.1 Grouping — the granularity sweep

```
day        (d8)                                 all three books compete
assetday   (asset, d8)
class      (asset, d8, CLASS)
cell       (asset, d8, PHASE)                   <- the committed champion
cellclass  (asset, d8, PHASE, CLASS)            <- finer than the champion
joint      (asset, d8, PHASE) over {member} x {D = 0,60,120,300,600 s}
```

The IR literature makes the group definition first-order: too coarse and the
comparisons are confounded by things the cell would have absorbed; too fine and
the comparisons are **starved** (a group of one carries no ranking decision at
all). Both directions are therefore swept, and **the group-size distribution is
reported per variant** so starvation is visible rather than inferred.

### 1.2 Objective

* `ndcg3` — `rank:ndcg`, `eval_metric ndcg@3`. **The champion.**
* `ndcg1` — the same at `ndcg@1`: spends no gradient on ranks 2–3 that are never
  seated.
* `softmax1` — **the conditional logit.** Per-cell multinomial over the members,
  target = the member that paid most; `grad = p − t`, `hess = p(1−p)`.
  *Theoretical status: this is the canonical choice model for exactly our
  problem, which is why "it never trained" is not an acceptable final state.*
* `dpairs` — `rank:pairwise` with each **group** weighted by
  `max(0, best − median)` of its positive dollars, clipped to `[0.05, 5]`: a
  cell whose members all pay the same is worth nothing to get right.
* `q75` — `reg:quantileerror`, α = 0.75. Pointwise; enters the grid because the
  seated member is an upper-tail event, not a mean.

### 1.3 Target

* `dollars` — `cert_close_usd` on the D-021 grade ladder (champion, unfitted).
* `cellrank` — the within-cell percentile of the dollars, rescaled.
* `winner` — `y_winner`, the D-021 flag.
* `maecap` — `st_champ.label_variant(D, "maecap")`: the 18-tick-dip variant,
  imported verbatim. The dollars are kept but rows the variant refuses are
  zeroed.

### 1.4 Population

* `full` — `PRE_E1 .. E(k−1)`, the champion's window.
* `recency` — the same rows, group weight `exp(−(k−1−era)/2)`.
* `last2` — only the two eras before the test era.
* `classfilt` — only the classes that account for 80% of the **training block's**
  cell wins (causal: computed on the training block alone).

### 1.5 Engine

`xgb` (the champion's), `lgbm` (`lambdarank` / `quantile`), `catb`
(`YetiRank` / `Quantile` with `boosting_type="Ordered"` — ordered boosting is
the small-data target-leak protection, and the weak early eras are exactly where
it should pay if it pays anywhere).

### 1.6 Feature set — the axis the diagnosis names

Every family is **strictly causal at the decision second** and every one carries
a **future-peeking mutant that the red-first stage must CATCH** (the mutant must
score *above* its causal sibling — a mutant that lands at chance would mean the
instrument is blind, not that the family is clean; this is the
`MUT_ABS_LOOKAHEAD_2H` law from the creator census).

| family | columns | definition |
|---|--:|---|
| `BASE` | 184 | the champion's non-`tf_` columns. The reference. |
| **`CELLREL`** | **64** | **the marquee.** For each of the 20 committed top-importance base features (read from `m3/walk/IMPORTANCE.tsv`'s **E3** rows — a model that had seen only `PRE_E1..E2`, so the choice is causal for every fold): the **prefix rank**, **prefix z**, and **prefix gap-to-best** among the cell-mates *visible so far* (`dec_sec <= this member's`, itself included). Plus `cr_n_so_far`, `cr_disp_top`, `cr_elapsed_frac`, `cr_since_prev_sec`. |
| `DAYSOFAR` | 9 | the session's **resolved** history at `t`: how many earlier candidates have already CLOSED (`exit_close_sec <= t`), what they paid, the same-class subset, the running realised sum, session elapsed fraction. An open episode has not resolved and is not readable. |
| `TABPFN` | 1 | the committed walk-forward TabPFN winner probability as an **input column, not a score blend** (blending damages within-cell ordering at every weight, ρ = −0.107; as a feature the ranker may use it where it helps). Rows before E3 have no walk-forward value and stay NaN — all three engines take NaN natively. |
| `DIP` | 1 | predicted `mae_before_argmax` from a small auxiliary regressor fitted on **this fold's training block only** (fold-dependent). |

Red-first mutant: `DAYSOFAR_PEEK` reads `exit_close_sec <= t + 3600` — a
deliberate look-ahead that **must** beat `DAYSOFAR`.

---

## 2. THE PRUNES (measured counts, not estimates)

Full cross = **7,200** cells. Live after structural prunes = **1,944**.

| id | prune | killed | reason |
|---|---|--:|---|
| **P1** | pointwise objective collapses the grouping axis | 960 | `q75` never sees a group: all six grouping levels would fit the identical model. Kept at `cell` (label inert, stated) and at `joint` (where the grouping changes the training **rows**, not only the groups). |
| **P2** | custom-objective engines | 960 | `softmax1` needs the group pointer inside a custom objective; only xgboost exposes it. **Infeasible**, not redundant. |
| **P3** | `softmax1 × {winner, cellrank}` | 240 | the softmax target *is* "the member that paid most": `cellrank` has the identical argmax by construction, `winner` gives ties or no positive. |
| **P4** | `q75 × winner` | 120 | a 0.75-quantile fit on a 0/1 target returns a step function of the base rate. |
| **P5** | `joint × {winner, cellrank}` | 420 | `y_winner` is a D=0 label with no delayed counterpart; a within-cell rank over `{member × delay}` ranks *different acts* on a scale defined at one of them. Incoherent. |
| **P6** | non-xgboost engines answer the **engine** question only | 2,556 | `lgbm`/`catb` are crossed with `population=full` and `feat ∈ {BASE, CELLREL}` only. Crossing them with every population and feature family would triple the grid to answer a question nobody asked. |
| **P7** | `day` and `asset-day` are **not** redundant | — | `st_rank.group_key(unit="day")` is `(asset, day)`. A **cross-asset** day group is a different object. Both are live and both are kept. |
| **P8** | the policy axis is **post-hoc** | — | `static1 / thresh / gate60 / gate120 / stop` are read off a fitted score column at zero fit cost (this is `st_sched`'s "nothing is refitted, the same score columns re-seated"). Screening them would multiply the fit count by five to measure nothing new. **Every Stage-B survivor is read under all five.** |
| **P9** | **fractional screen design — stated, not hidden** | — | 1,944 live cells is not a *cheap* screen. Stage A screens a resolution-III + marquee-plane design (§3). Stage A2 then fully crosses the **surviving** levels of every axis, which is where an interaction the fractional design missed can still surface. |
| **P10** | measured prune | — | any cell that comes out constant, all-NaN, or that fails to fit is dropped and **recorded** in the screen ledger as such, never silently. |

---

## 3. STAGE A — THE SCREEN (pre-registered, `promotion: false`)

**219 screen cells**, grid sha256 `723f972a7cf03533…`, in seven design blocks:

| block | cells | what it buys |
|---|--:|---|
| `reference` | 1 | the committed champion — **must reproduce** |
| `marquee` | 29 | grouping × feature-set, fully crossed |
| `granularity_x_obj` | 40 | the granularity sweep × objective at both feature levels |
| `obj_x_target` | 72 | objective × target across every feature family |
| `pop_x_feat` / `pop_x_obj` / `pop_x_target` | 36 | the population marginals |
| `engine_x_obj` / `engine_x_target` | 22 | does a different implementation of the same objective matter |
| `joint` | 19 | **OBJ-1**, the `{member × delay}` choice set, as its own block |
| `named` | — | interaction cells with a stated mechanism (deduplicated into the blocks above where they collide) |

**Protocol.**

| | |
|---|---|
| budget | identical for every cell: **60 rounds**, depth 6, η 0.08, **25% of training groups**, seed 20260813, no early stopping |
| where | the **inner-TRAIN** days of the `E3 / E5 / E7` folds; read on the **inner-VALIDATION** days. Entirely inside the training block — **no evaluation era is touched by the screen** |
| eras | `E3` (data-starved), `E5`, `E7` (the worst cell in the champion's table) — the weak-era focus the standing criterion demands |
| **yardstick** | **realised $/session under the harness's own `cell/N` seating**, averaged over the three folds. The ONE metric comparable across objectives — *a cell's own loss is not*, "because different objectives have different losses and are not comparable on them" (`LABEL_ATLAS_V2` §2) |
| lift | `inner_usd(cell) − inner_usd(reference)` |
| **twin** | every cell is fitted a second time at identical budget with the values **permuted within the block**. A cell whose twin reaches its own lift is **VOID** |
| **verified-to-train** | `softmax1` cells additionally report `train_p1` (train-side dollar-P@1) for the cell and its twin; the conditional-logit row may not be reported as a null unless it **beats its own twin on the training objective** |
| promotion | **false** |

## 4. STAGE B — CONFIRM

Top ~15 by screen lift (VOID cells excluded) **plus the reference cell**, on the
**full E3–E7 walk-forward**: the champion's own HP discipline (the 12-cell inner
grid, selected on inner-validation and nothing else), `m3_walk`'s committed
per-era `(unit, N)`, `replay_delayed` (proved seat-for-seat identical to
`m3_walk.replay_rows` at D=0), CR1 intervals **clustered by day**, and a
`deficit_ledger` decomposition per arm. Each survivor is read under **all five
policies** (P8). **One Holm family** over the confirm arms' primary paired test
against the champion, with the whole screen's trial count recorded.

## 5. THE BLIND READ

**E8 is opened exactly once, for the single best confirmed arm, and is never an
input to any choice in this file.** The 2025-H2 holdout (`d8 >= 20250701`)
stays sealed.

## 6. THE CEILINGS THAT BOUND THE GRID

Priced before the grid was screened (`provenance/port_m2/NEWOBJ_CEILINGS.md`),
so that no cell is chased past what it can possibly be worth. Pooled E3–E7,
champion = $976.91/session:

| bound | $/session | what it bounds |
|---|--:|---|
| per-cell member oracle (D=0) | **3,152.31** | the whole grid: no ranker can exceed it |
| joint `{member × delay}` oracle | 3,302.74 | **OBJ-1**: timing freedom is worth **+$150.43** of it |
| perfect gate, `{m1@D, m2@D, ∅}` | 1,607.09 (D=60) / **1,621.65** (D=0) | **OBJ-2** |
| perfect abstention alone | 1,526.54 | the abstention half of OBJ-2 |
| random member | −64.95 | the floor |

---

**Nothing below the pre-registration line existed when this file was committed.**

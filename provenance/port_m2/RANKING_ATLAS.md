# THE RANKING ATLAS — enumerate, screen, confirm, read once

**The systematic version of the accident that found the cell axis.** Grid pre-registered and
committed at `design/RANKING_ATLAS_GRID.md` (repo `c312a34`) **before a single screen number
existed**. Engine `engine/port_m2/rank_atlas.py` (+ `atlas_feat.py`, `newobj.py`,
`newobj_arms.py`, `sufficiency.py`). Version `PORT-M2-RANK-ATLAS-V1`, seed `20260813`.

*(Results sections are filled from `RANKING_ATLAS_SCREEN.tsv`, `RANKING_ATLAS_CONFIRM.tsv`,
`RANKING_ATLAS_POLICIES.tsv`, `RANKING_ATLAS_HOLM.tsv`, `RANKING_ATLAS_BLIND.tsv`,
`RANKING_ATLAS_GROUPSIZE.tsv` and the `SUFFICIENCY_*.tsv` family.)*

---

## 0. WHAT THE PROBLEM ACTUALLY IS

Stated in its own terms, the champion does this: **inside each (asset, day, phase) cell it
observes a set of alternatives and picks one.** That is not regression and it is not binary
classification. It is a **repeated discrete choice over a varying choice set** — equivalently,
**cross-sectional ranking**. Two mature literatures own that object:

| our object | econometrics | finance / IR |
|---|---|---|
| the cell as the competition set | **conditional logit** (McFadden 1974) — choice among the alternatives of a *choice set* | the cross-section on one date |
| cell grouping | the **fixed-effect / within estimator**: the cell absorbs everything common to it, so only *within-cell* contrasts are identified | per-date cross-sectional ranking |
| cell-relative features | within-group demeaning / standardisation | **per-date standardisation**, the first thing done to any cross-sectional signal |
| per-cell softmax P@1 | **exactly** McFadden's conditional-logit likelihood | listwise IR (ListNet's top-1 probability) |
| NDCG@k grouped by cell | — | LambdaMART's home turf |

This re-reads the largest jump in the program's history as something other than luck:
**class-grouped −$23.88 → day-grouped +$5.80 → cell-grouped +$495.11** was a move from a
mis-specified competition set to the one the deployment actually uses — a within estimator
finally being given the right groups. And it names, in advance, the gap the feature axis is
built to test: **our columns describe an alternative in isolation while the identified
variation is within-cell.** A within estimator fed only level covariates is being asked to
recover a contrast it cannot see.

**THE CITE-THEN-VERIFY LAW.** Every recommendation from either literature enters this atlas as
a **grid cell measured on our data**, never as an adoption. Conditional logit is a row, not a
conclusion; per-date standardisation is a feature family, not a decision. The literature's only
job here was to enumerate hypotheses worth spending compute on. **Nothing in §0 is evidence.**

---

## 1. THE GRID (pre-registered; measured counts)

| | |
|---|--:|
| full cross of the six axes | **7,200** |
| live after the structural prunes P1–P6 | **1,944** |
| Stage-A screen cells (fractional design, P9) | **219** |
| screen fits including the shuffled twins | **438** |
| screen grid sha256 | `723f972a7cf03533…` |

Axes: **grouping** {day, assetday, class, **cell**, cellclass, joint} × **objective** {ndcg3,
ndcg1, softmax1, dpairs, q75} × **target** {dollars, cellrank, winner, maecap} × **population**
{full, recency, last2, classfilt} × **engine** {xgb, lgbm, catb-ordered} × **feature set**
{BASE, **CELLREL**, DAYSOFAR, TABPFN, DIP}. The **policy** axis {static1, thresh, gate60,
gate120, stop} is post-hoc (P8) and is applied to every confirmed arm rather than screened.

Prunes, with what each killed: **P1** pointwise objective collapses the grouping axis (960);
**P2** `softmax1` is xgboost-only, a custom objective needing the group pointer (960); **P3**
`softmax1 × {winner, cellrank}` is degenerate (240); **P4** `q75 × winner` (120); **P5**
`joint × {winner, cellrank}` is incoherent — `y_winner` has no delayed counterpart (420);
**P6** non-xgboost engines answer the *engine* question only, so they are crossed with
`pop=full` and `feat ∈ {BASE, CELLREL}` (2,556); **P7** `day` (cross-asset) and `assetday` are
different objects and both are kept; **P8** the policy axis is post-hoc; **P9** the fractional
screen design, stated; **P10** measured prune, recorded in the ledger.

### 1.1 The granularity sweep, with starvation made visible

`RANKING_ATLAS_GROUPSIZE.tsv`, evaluation rows after the D-077 veto (E5 shown; every era is in
the file):

| grouping | groups | median size | p10 | p90 | **frac size < 2** | frac size < 5 |
|---|--:|--:|--:|--:|--:|--:|
| `day` (cross-asset) | 129 | 1,177 | 914 | 1,484 | 0.000 | 0.000 |
| `assetday` | 387 | 381 | 277 | 523 | 0.000 | 0.000 |
| `class` | 1,708 | 11 | 4 | 357 | 0.039 | 0.125 |
| **`cell`** (champion) | 1,161 | 105 | 41 | 257 | **0.000** | 0.000 |
| `cellclass` | 3,608 | 7 | 1 | 145 | **0.152** | 0.374 |
| `joint` | 1,161 | 520 | 201 | 1,284 | 0.000 | 0.000 |

A group of size < 2 carries **no ranking decision at all**. Going finer than the champion's
cell starves **15.2%** of the groups outright and leaves 37.4% with fewer than five members;
going coarser confounds. The champion's cell is the only level in the sweep that is both
finer than the day and never starved — which is a structural fact about the grid, established
before any cell was fitted, not a result.

---

## 2. STAGE A — THE SCREEN

*(filled from `RANKING_ATLAS_SCREEN.tsv`)*

## 3. STAGE B — CONFIRM

*(filled from `RANKING_ATLAS_CONFIRM.tsv` + `RANKING_ATLAS_HOLM.tsv`)*

## 4. THE POLICY COLUMNS (OBJ-2 and OBJ-3)

*(filled from `RANKING_ATLAS_POLICIES.tsv`)*

## 5. THE BLIND READ

*(filled from `RANKING_ATLAS_BLIND.tsv`)*

## 6. THE SUFFICIENCY INSTRUMENT

*(filled from `SUFFICIENCY_*.tsv`)*

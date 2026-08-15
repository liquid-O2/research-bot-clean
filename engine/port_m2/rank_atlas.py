#!/usr/bin/python3
"""PORT M2 — THE RANKING ATLAS.

The systematic version of the accident that found the cell axis.  The champion
was reached by changing one thing at a time and getting lucky about which thing;
this enumerates the axes of the RANKING ACT as a grid, screens the grid cheaply
under one pre-registered protocol, and confirms only the survivors.

Modelled verbatim on `design/LABEL_ATLAS_V2.md`'s discipline:
  * the grid is ENUMERATED and its structural prunes are NAMED (P1..P10);
  * STAGE A screens every live cell at an identical cheap budget and ranks them
    on ONE COMMON YARDSTICK — realised $/session on the inner validation block —
    never on a cell's own loss, "because different objectives have different
    losses and are not comparable on them";
  * every cell gets a SHUFFLED TWIN at identical budget; a cell whose twin
    reaches its own lift is VOIDED;
  * `promotion: false` — Stage A is not a champion claim;
  * the whole grid's trial count enters ONE Holm family at Stage B;
  * STAGE B confirms the top survivors on the full E3-E7 walk-forward with CR1
    intervals clustered by day and a deficit-ledger decomposition;
  * E8 is opened ONCE, blind, for the single best arm.

The champion's own configuration is IN the grid as the reference cell
(`cell / ndcg3 / dollars / full / xgb / BASE`) and must reproduce.

THE GRID IS PRE-REGISTERED IN `design/RANKING_ATLAS_GRID.md` AND COMMITTED
BEFORE ANY SCREEN NUMBER EXISTS.
"""
import argparse
import hashlib
import itertools
import json
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import newobj as N                        # noqa: E402
import newobj_arms as NA                  # noqa: E402
import atlas_feat as AF                   # noqa: E402
import st_common as SC                    # noqa: E402
import m2_common as MC                   # noqa: E402

LANE = "port-m2-rank-atlas"
VERSION = "PORT-M2-RANK-ATLAS-V1"

# ================================================================== the axes ==
AXES = {
    # THE GRANULARITY SWEEP, coarsest -> finest, straddling the champion's cell:
    #   day        (calendar day, ALL THREE books competing)
    #   assetday   (asset, day)
    #   class      (asset, day, CLASS)
    #   cell       (asset, day, PHASE)          <- the champion
    #   cellclass  (asset, day, PHASE, CLASS)   <- finer than the champion
    #   joint      (asset, day, PHASE) over {member x delay}
    # The IR literature makes the group definition first-order (too coarse =
    # confounded comparisons, too fine = starved ones), so both directions are
    # swept and the group-size distribution is reported per variant.
    "group":  ("day", "assetday", "class", "cell", "cellclass", "joint"),
    "obj":    ("ndcg3", "ndcg1", "softmax1", "dpairs", "q75"),
    "target": ("dollars", "cellrank", "winner", "maecap"),
    "pop":    ("full", "recency", "last2", "classfilt"),
    "engine": ("xgb", "lgbm", "catb"),
    "feat":   ("BASE", "CELLREL", "DAYSOFAR", "TABPFN", "DIP"),
}
# The SELECTION POLICY axis is POST-HOC: it is applied to a fitted score column
# and costs no fit (this is exactly `st_sched`'s "nothing is refitted, the same
# score columns re-seated").  It is therefore not a screen axis; every survivor
# is read under ALL of these at Stage B.
POLICIES = ("static1", "thresh", "gate60", "gate120", "stop")

REF = {"group": "cell", "obj": "ndcg3", "target": "dollars", "pop": "full",
       "engine": "xgb", "feat": "BASE"}          # = the committed champion

WEAK_ERAS = ("E3", "E5", "E7")   # the screen's eras: the data-starved rung, a
                                 # mid rung, and the worst cell in the table
CONFIRM_ERAS = N.DEV_ERAS        # E3..E7; E8 stays blind

PROV = N.PROV
OUT = os.path.join(N.OUT_ROOT, "atlas")

# ------------------------------------------------------------ the budgets ----
# AMENDMENT A1 (recorded, not quietly applied — a pre-registration that is
# edited in silence is not one).  The registered budget was 60 rounds / 25% of
# groups.  A 5-cell INSTRUMENT CALIBRATION run before the screen (no lift, no
# ranking, no cell compared to another) showed the reference cell landing at
# $106.73/session on the inner block with a NEGATIVE E3 fold — an instrument too
# noisy to rank 219 cells on.  The budget is doubled in rounds and group
# coverage.  It remains IDENTICAL for every cell and every twin, which is the
# property the screen law actually requires.
SCREEN = {"rounds": 120, "depth": 6, "eta": 0.08, "group_frac": 0.60,
          "seed": N.SEED}
CONFIRM = {"rounds": 300, "early": 25, "seed": N.SEED}


# =========================================================== the prune law ====
PRUNES = [
 ("P1", "pointwise objective collapses the grouping axis",
  "`q75` is a pointwise quantile regression: it never sees a group, so all five "
  "grouping levels would fit the identical model.  Kept only at group=cell "
  "(where the grouping label is inert and honest) and at group=joint (where the "
  "grouping changes the training ROWS, not only the groups)."),
 ("P2", "custom-objective engines",
  "`softmax1` is a per-cell multinomial implemented as a custom objective that "
  "needs the group pointer; only xgboost exposes it.  lightgbm/catboost cells "
  "for that objective are infeasible, not merely redundant."),
 ("P3", "softmax1 x {winner, cellrank} is degenerate",
  "The softmax target IS 'the member that paid most'.  With target=cellrank the "
  "argmax is identical by construction; with target=winner a cell has ties or "
  "no positive at all.  Both re-express the dollars cell."),
 ("P4", "q75 x winner is degenerate",
  "A 0.75-quantile regression on a 0/1 target returns a step function of the "
  "cell's base rate."),
 ("P5", "joint x {winner, cellrank}",
  "`y_winner` is a D=0 label with no delayed counterpart, and a within-cell rank "
  "over the joint {member x delay} set ranks different ACTS against each other "
  "on a scale defined at one of them.  Incoherent, not merely weak."),
 ("P6", "non-xgboost engines answer the ENGINE question only",
  "lightgbm and catboost-ordered are in the grid to test whether a different "
  "implementation of the same objective matters (the final pass ran them at "
  "defaults and flagged it).  They are crossed with population=full and "
  "feature-set in {BASE, CELLREL} only; crossing them with every population and "
  "feature family would triple the grid to answer a question nobody asked."),
 ("P7", "`day` and `asset-day` are NOT redundant",
  "`st_rank.group_key(unit='day')` is (asset, day) = asset-day.  A cross-asset "
  "day group (all three books' candidates competing) is a DIFFERENT object and "
  "is kept as `day`.  Both levels are live; the coordinator's list named them "
  "separately and they are separated here."),
 ("P8", "the policy axis is post-hoc",
  "static top-1 / inner-swept threshold / gate-verified / optimal-stopping are "
  "read off a fitted score column at zero fit cost.  Screening them would "
  "multiply the fit count by five to measure nothing new; every Stage-B "
  "survivor is read under all five instead."),
 ("P9", "FRACTIONAL SCREEN DESIGN — stated, not hidden",
  "The pruned full cross is 1,616 live cells, which is not a cheap screen.  "
  "Stage A therefore screens a RESOLUTION-III + MARQUEE-PLANE design: (a) the "
  "marquee plane group x feat fully crossed, (b) the axis marginals of "
  "objective x target x population and engine, each at BOTH feature levels that "
  "the diagnosis distinguishes (BASE and CELLREL), (c) named interaction cells "
  "each carrying a stated mechanism.  Stage A2 then fully crosses the SURVIVING "
  "levels of every axis, which is where any interaction the fractional design "
  "missed can still surface."),
 ("P10", "measured prune",
  "Any cell that comes out constant, all-NaN, or that fails to fit is dropped "
  "and RECORDED in the screen ledger as such, never silently."),
]


def spec_id(s):
    return "%s|%s|%s|%s|%s|%s" % (s["group"], s["obj"], s["target"], s["pop"],
                                  s["engine"], s["feat"])


def _coherent(s):
    """The structural prunes, as a predicate.  Returns None if live, else the
    prune id that kills the cell."""
    g, o, t, p, e, f = (s["group"], s["obj"], s["target"], s["pop"],
                        s["engine"], s["feat"])
    if o == "q75" and g not in ("cell", "joint"):
        return "P1"
    if o == "softmax1" and e != "xgb":
        return "P2"
    if o == "softmax1" and t in ("winner", "cellrank"):
        return "P3"
    if o == "q75" and t == "winner":
        return "P4"
    if g == "joint" and t in ("winner", "cellrank"):
        return "P5"
    if e != "xgb" and (p != "full" or f not in ("BASE", "CELLREL")):
        return "P6"
    return None


def full_cross():
    live, pruned = [], {}
    keys = list(AXES)
    for vals in itertools.product(*[AXES[k] for k in keys]):
        s = dict(zip(keys, vals))
        pr = _coherent(s)
        if pr:
            pruned[pr] = pruned.get(pr, 0) + 1
        else:
            live.append(s)
    return live, pruned


NAMED = [
 # (spec-overrides, the MECHANISM that earns the cell)
 ({"group": "joint", "obj": "dpairs", "target": "dollars", "feat": "CELLREL"},
  "OBJ-1 at its best-shaped objective: the joint set's decision is worth what "
  "the cell's dollar spread is, and the cell-relative columns are the only ones "
  "that see the spread."),
 ({"group": "joint", "obj": "softmax1", "target": "dollars"},
  "OBJ-1 under the deployment-exact objective: top-1 over {member x delay}."),
 ({"group": "cell", "obj": "softmax1", "target": "dollars", "feat": "CELLREL"},
  "The deployment-exact objective with the deployment-relevant features — the "
  "loose-end retry (a) at its most favourable honest setting."),
 ({"group": "cell", "obj": "ndcg1", "target": "dollars", "feat": "CELLREL"},
  "NDCG@1 spends no gradient on ranks 2..3 that are never seated."),
 ({"engine": "catb", "group": "cell", "obj": "ndcg3", "target": "dollars",
   "pop": "full", "feat": "CELLREL"},
  "Ordered boosting is small-data target-leak protection and the cell-relative "
  "columns are the most leak-prone (they are functions of the cell's own rows)."),
 ({"group": "cell", "obj": "ndcg3", "target": "dollars", "pop": "last2",
   "feat": "CELLREL"},
  "If cell-relative structure is regime-dependent, recency should pay on it."),
 ({"group": "class", "obj": "ndcg3", "target": "dollars", "feat": "CELLREL"},
  "The cell-relative columns are computed on the CELL; ranking them inside the "
  "CLASS tests whether the information is the columns or the grouping."),
 ({"group": "assetday", "obj": "ndcg3", "target": "dollars", "feat": "DAYSOFAR"},
  "Day-so-far state is a day-level object; the day-level group is its home."),
 ({"group": "cell", "obj": "ndcg3", "target": "maecap", "feat": "CELLREL"},
  "The MAE-cap label's blind spot and the ordering deficit attacked together."),
 ({"group": "cell", "obj": "dpairs", "target": "dollars", "feat": "CELLREL"},
  "Dollar-weighted pairs concentrate the fit on the cells where the ordering "
  "decision is actually worth money; cell-relative gives it the comparison."),
]


def screen_grid():
    """STAGE A's fractional design (P9).  Each cell carries the design BLOCK it
    came from so the report can never present a marginal as a full cross."""
    cells, seen = [], set()

    def add(over, block, why=""):
        s = dict(REF)
        s.update(over)
        if _coherent(s):
            return
        k = spec_id(s)
        if k in seen:
            return
        seen.add(k)
        s = dict(s)
        s["_block"] = block
        s["_why"] = why
        cells.append(s)

    add({}, "reference", "the committed champion LMART_HP_NOTF — must reproduce")
    # (a) THE MARQUEE PLANE: grouping x feature-set, fully crossed
    for g in AXES["group"]:
        for f in AXES["feat"]:
            add({"group": g, "feat": f}, "marquee",
                "grouping x feature-set, the two axes the diagnosis names")
    # (b) THE GRANULARITY SWEEP x OBJECTIVE, at both feature levels
    for g in AXES["group"]:
        for o in AXES["obj"]:
            for f in ("BASE", "CELLREL"):
                add({"group": g, "obj": o, "feat": f}, "granularity_x_obj",
                    "group definition is first-order in IR; swept against the "
                    "objective at both feature levels")
    # (c) OBJECTIVE x TARGET across every feature family
    for o in AXES["obj"]:
        for t in AXES["target"]:
            for f in AXES["feat"]:
                add({"obj": o, "target": t, "feat": f}, "obj_x_target",
                    "objective x target at group=cell")
    # (d) POPULATION marginals: x objective, x target, x feature
    for p in AXES["pop"]:
        for f in AXES["feat"]:
            add({"pop": p, "feat": f}, "pop_x_feat", "training population")
        for o in AXES["obj"]:
            add({"pop": p, "obj": o, "feat": "CELLREL"}, "pop_x_obj",
                "population x objective at the marquee feature set")
        for t in AXES["target"]:
            add({"pop": p, "target": t, "feat": "CELLREL"}, "pop_x_target",
                "population x target at the marquee feature set")
    # (e) ENGINE marginals (P6 keeps these narrow by construction)
    for e in AXES["engine"]:
        for o in AXES["obj"]:
            for f in ("BASE", "CELLREL"):
                add({"engine": e, "obj": o, "feat": f}, "engine_x_obj",
                    "does a different implementation of the same objective "
                    "matter (the final pass ran engines at defaults)")
        for t in AXES["target"]:
            add({"engine": e, "target": t}, "engine_x_target",
                "engine x target at the reference feature set")
    # (f) THE JOINT OBJECT (OBJ-1) as its own block
    for o in AXES["obj"]:
        for f in AXES["feat"]:
            add({"group": "joint", "obj": o, "feat": f}, "joint",
                "OBJ-1: the {member x delay} choice set")
    for p in AXES["pop"]:
        for t in ("dollars", "maecap"):
            add({"group": "joint", "pop": p, "target": t, "feat": "CELLREL"},
                "joint", "OBJ-1 x population x target")
    # (g) NAMED INTERACTIONS with a stated mechanism
    for over, why in NAMED:
        add(over, "named", why)
    return cells


def grid_receipt():
    live, pruned = full_cross()
    cells = screen_grid()
    blocks = {}
    for c in cells:
        blocks[c["_block"]] = blocks.get(c["_block"], 0) + 1
    h = hashlib.sha256("\n".join(sorted(spec_id(c) for c in cells))
                       .encode()).hexdigest()
    return {"version": VERSION, "axes": {k: list(v) for k, v in AXES.items()},
            "policies": list(POLICIES), "reference": REF,
            "n_full_cross": int(np.prod([len(v) for v in AXES.values()])),
            "n_live_after_prunes": len(live),
            "pruned_by": pruned,
            "n_screen_cells": len(cells), "screen_blocks": blocks,
            "screen_grid_sha256": h,
            "weak_eras": list(WEAK_ERAS), "confirm_eras": list(CONFIRM_ERAS),
            "screen_budget": SCREEN, "confirm_budget": CONFIRM,
            "prunes": [{"id": a, "name": b, "reason": c} for a, b, c in PRUNES],
            "promotion": False}


# ============================================================== the design ====
_D = {}


def base_cols(D):
    return NA.feat_cols(D)


def build_features(D, spec, era_tr_rows, all_rows):
    """(X, names) for a spec.  Fold-independent families are cached; DIP is
    fitted on the training block of THIS fold only."""
    cols, names = base_cols(D)
    X = [D["X"][:, cols]]
    FN = list(names)
    f = spec["feat"]
    if f in ("CELLREL", "DAYSOFAR", "TABPFN"):
        Xf, nf = AF.family(f)
        X.append(Xf)
        FN += nf
    elif f == "DIP":
        Xf, nf = AF.dip_column(D, cols, era_tr_rows, all_rows)
        X.append(Xf)
        FN += nf
    elif f == "DAYSOFAR_PEEK":
        Xf, nf = AF.family("DAYSOFAR_PEEK")
        X.append(Xf)
        FN += nf
    return (np.hstack(X) if len(X) > 1 else X[0]), FN


def target_value(D, spec, V=None, dl=None):
    """The value column the fit is graded on."""
    t = spec["target"]
    if t == "dollars":
        return (V[int(dl)] if V is not None else
                D["cert_close_usd"].astype(np.float64))
    if t == "maecap":
        import st_champ as CH
        y, _c = CH.label_variant(D, "maecap")
        base = (V[int(dl)] if V is not None else
                D["cert_close_usd"].astype(np.float64))
        # the MAE-cap variant re-labels which rows count as winners; the ORDERING
        # target keeps the dollars but zeroes the rows the variant refuses
        out = base.copy()
        out[(y <= 0) & (base > 0)] = 0.0
        return out
    if t == "winner":
        return np.nan_to_num(D["y_winner"].astype(np.float64), nan=0.0) * 1000.0
    if t == "cellrank":
        return _cellrank(D)
    raise N.NewObjRefusal("unknown target %r" % t)


_CR = {}


def _cellrank(D):
    if "v" not in _CR:
        v = D["cert_close_usd"].astype(np.float64)
        key = ((D["asset_idx"].astype(np.int64) * 100000000
                + D["d8"].astype(np.int64)) * 100 + D["phase_dec"])
        out = np.zeros(v.size)
        order = np.argsort(key, kind="stable")
        ko = key[order]
        starts = [0] + (np.flatnonzero(ko[1:] != ko[:-1]) + 1).tolist()
        for a, b in zip(starts, starts[1:] + [ko.size]):
            ix = order[a:b]
            r = np.argsort(np.argsort(v[ix], kind="stable"), kind="stable")
            out[ix] = (r + 0.5) / max(ix.size, 1) * 2000.0
        _CR["v"] = out
    return _CR["v"]


def group_key_of(D, r, spec):
    import st_rank as RK
    g = spec["group"]
    if g == "day":                          # cross-asset day (P7)
        return D["d8"][r].astype(np.int64)
    if g == "assetday":
        return (D["asset_idx"][r].astype(np.int64) * 100000000
                + D["d8"][r].astype(np.int64))
    if g in ("class", "cell"):
        return RK.group_key(D, r, _D["klass"], g)
    if g == "cellclass":
        return (((D["asset_idx"][r].astype(np.int64) * 100000000
                  + D["d8"][r].astype(np.int64)) * 100
                 + D["phase_dec"][r]) * 1000 + _D["klass"][r])
    if g == "joint":
        return ((D["asset_idx"][r].astype(np.int64) * 100000000
                 + D["d8"][r].astype(np.int64)) * 100 + D["phase_dec"][r])
    raise N.NewObjRefusal("unknown group %r" % g)


def population(D, spec, era, tr):
    """Training rows + a per-GROUP weight for this population level."""
    p = spec["pop"]
    k = SC.ERA_IDX[era]
    if p == "full":
        return tr, None
    if p == "last2":
        return tr[D["era_idx"][tr] >= k - 2], None
    if p == "recency":
        # a FULL-LENGTH weight column indexed by matrix row: the group-sorted
        # fit order is not the `tr` order, and indexing one by the other would
        # attach each group's weight to the wrong group (found before the run)
        w = np.full(D["d8"].size, np.nan)
        w[tr] = np.exp(-(k - 1 - D["era_idx"][tr].astype(np.float64)) / 2.0)
        return tr, w
    if p == "classfilt":
        # the classes that actually win cells in the TRAINING block (causal)
        import st_rank as RK
        klass = _D["klass"]
        v = D["cert_close_usd"].astype(np.float64)
        key = group_key_of(D, tr, {"group": "cell"})
        order = np.argsort(key, kind="stable")
        ko = key[order]
        starts = [0] + (np.flatnonzero(ko[1:] != ko[:-1]) + 1).tolist()
        wins = {}
        for a, b in zip(starts, starts[1:] + [ko.size]):
            ix = order[a:b]
            j = ix[int(np.argmax(v[tr][ix]))]
            c = int(klass[tr[j]])
            wins[c] = wins.get(c, 0) + 1
        tot = sum(wins.values())
        keep, run = set(), 0
        for c, n_ in sorted(wins.items(), key=lambda z: -z[1]):
            keep.add(c)
            run += n_
            if run >= 0.8 * tot:
                break
        return tr[np.isin(klass[tr], list(keep))], None
    raise N.NewObjRefusal("unknown pop %r" % p)


# ================================================================== the fit ===
def _groups_of(D, rows, spec, delays=None, V=None, X=None):
    """Rows sorted by group + the group-size vector, for any grouping level."""
    r = np.asarray(rows, dtype=np.int64)
    key = group_key_of(D, r, spec)
    order = np.lexsort((D["dec_sec"][r], key))
    ro, ko = r[order], key[order]
    _u, cnt = np.unique(ko, return_counts=True)
    return ro, cnt


def _softmax_top1_obj(dollars_sorted, gptr):
    """THE CONDITIONAL LOGIT (McFadden), which is exactly the deployment: a
    multinomial over the cell's members with the paying member as the target.

    grad_i = p_i - t_i,  hess_i = p_i(1-p_i) with p the within-cell softmax.

    REPAIR NOTE (the final pass's H_TOP1 "never trained"): the objective itself
    was sound — it beats its shuffled twin decisively on TRAIN (0.335 vs 0.152
    dollar-P@1).  What killed it was the STOPPING RULE: its inner-validation
    NDCG@1 curve is flat noise from round 1, so `early_stopping_rounds=25`
    halted at iteration 1-6 and deployed an untrained model whose eval score was
    indistinguishable from the control.  Here the round count is fixed by the
    budget and the arm carries a VERIFIED-TO-TRAIN guard instead: the fitted
    model must beat its own shuffled twin on the TRAINING objective before any
    evaluation number is allowed to count.
    """
    def obj(preds, dtrain):
        g = gptr
        p = np.asarray(preds, dtype=np.float64)
        grad = np.zeros_like(p)
        hess = np.zeros_like(p)
        for a, b in zip(g[:-1], g[1:]):
            if b - a < 2:
                continue
            z = p[a:b] - p[a:b].max()
            e = np.exp(z)
            pr = e / max(e.sum(), 1e-12)
            t = np.zeros(b - a)
            t[int(np.argmax(dollars_sorted[a:b]))] = 1.0
            grad[a:b] = pr - t
            hess[a:b] = np.maximum(pr * (1.0 - pr), 1e-6)
        return grad, hess
    return obj


def train_dollar_p1(pred, val, cnt):
    """The common TRAIN-side yardstick for the verified-to-train guard: the
    fraction of each group's best positive dollars the argmax actually picks."""
    ptr = np.concatenate([[0], np.cumsum(np.asarray(cnt, np.int64))])
    num = den = 0.0
    for a, b in zip(ptr[:-1], ptr[1:]):
        v = np.maximum(val[a:b], 0.0)
        if v.sum() <= 0 or b - a < 2:
            continue
        num += float(v[int(np.argmax(pred[a:b]))])
        den += float(v.max())
    return num / den if den > 0 else float("nan")


def fit_cell(D, spec, fit_rows, score_rows, XF, FN, val, budget,
             wgroup=None, hp=None, early_va=None, memorize=False):
    """One atlas cell: fit on `fit_rows`, return the score on `score_rows`.

    `memorize=True` is the SUFFICIENCY instrument's representation ceiling —
    unconstrained capacity, scored IN SAMPLE, explicitly NON-CAUSAL.
    """
    eng, obj, gu = spec["engine"], spec["obj"], spec["group"]
    r_f, g_f = _groups_of(D, fit_rows, spec)
    y_f = val[r_f]
    grade = NA.grades(y_f)
    depth = (budget.get("depth", 6) if hp is None else hp["max_depth"])
    eta = (budget.get("eta", 0.08) if hp is None else hp["eta"])
    rounds = budget.get("rounds", 60)
    if memorize:
        depth, eta, rounds = 12, 0.30, 300
    gw = None
    if obj == "dpairs":
        # DOLLAR-WEIGHTED PAIRS: weight each group by what its ordering decision
        # is worth — the spread between its best and its median member.  A cell
        # whose members all pay the same is worth nothing to get right.
        ptr = np.concatenate([[0], np.cumsum(g_f)])
        gw = np.array([max(0.0, float(np.max(np.maximum(y_f[a:b], 0.0))
                                      - np.median(np.maximum(y_f[a:b], 0.0))))
                       for a, b in zip(ptr[:-1], ptr[1:])]) / 1000.0
        gw = np.clip(gw, 0.05, 5.0)
    if wgroup is not None:
        ww = np.asarray(wgroup)[r_f]          # matrix-row indexed, group order
        ptr = np.concatenate([[0], np.cumsum(g_f)])
        per = np.array([float(np.nanmean(ww[a:b])) for a, b in
                        zip(ptr[:-1], ptr[1:])])
        per = np.where(np.isfinite(per), per, 1.0)
        gw = per if gw is None else gw * per
    if eng == "xgb":
        import xgboost as xgb
        base = {"tree_method": "hist", "min_child_weight": 20,
                "subsample": 0.8, "colsample_bytree": 0.8,
                "seed": budget.get("seed", N.SEED), "nthread": 8,
                "max_depth": depth, "eta": eta}
        if memorize:
            base.update({"min_child_weight": 1, "subsample": 1.0,
                         "colsample_bytree": 1.0, "lambda": 0.0})
        d = xgb.DMatrix(XF[r_f], label=grade, feature_names=FN)
        d.set_group(g_f)
        if gw is not None:
            d.set_weight(gw)
        custom = None
        if obj in ("ndcg3", "ndcg1"):
            base.update({"objective": "rank:ndcg",
                         "eval_metric": "ndcg@%d" % (3 if obj == "ndcg3" else 1),
                         "lambdarank_pair_method": "topk",
                         "lambdarank_normalization": True,
                         "lambdarank_num_pair_per_sample":
                             (hp or {}).get("lambdarank_num_pair_per_sample", 8)})
        elif obj == "dpairs":
            base.update({"objective": "rank:pairwise",
                         "lambdarank_pair_method": "topk",
                         "lambdarank_num_pair_per_sample":
                             (hp or {}).get("lambdarank_num_pair_per_sample", 16)})
        elif obj == "softmax1":
            base["disable_default_eval_metric"] = 1
            custom = _softmax_top1_obj(y_f, np.concatenate(
                [[0], np.cumsum(g_f.astype(np.int64))]))
        elif obj == "q75":
            base.update({"objective": "reg:quantileerror",
                         "quantile_alpha": 0.75})
            d = xgb.DMatrix(XF[r_f], label=y_f, feature_names=FN)
            if gw is not None:
                d.set_weight(np.repeat(gw, g_f))
        b = xgb.train(base, d, rounds, obj=custom)
        tr_pred = b.predict(xgb.DMatrix(XF[r_f], feature_names=FN),
                            output_margin=True)
        r_s, _g_s = _groups_of(D, score_rows, spec)
        s = b.predict(xgb.DMatrix(XF[r_s], feature_names=FN),
                      output_margin=True)
    elif eng == "lgbm":
        import lightgbm as lgb
        params = {"learning_rate": eta, "num_leaves": 2 ** min(depth, 8),
                  "min_data_in_leaf": 20, "feature_fraction": 0.8,
                  "bagging_fraction": 0.8, "bagging_freq": 1,
                  "seed": budget.get("seed", N.SEED), "num_threads": 8,
                  "verbosity": -1}
        if obj in ("ndcg3", "ndcg1", "dpairs"):
            params.update({"objective": "lambdarank", "metric": "ndcg",
                           "ndcg_eval_at": [1, 3]})
            ds = lgb.Dataset(XF[r_f], label=grade, group=g_f,
                             feature_name=FN, free_raw_data=False,
                             weight=(np.repeat(gw, g_f) if gw is not None
                                     else None))
        else:
            params.update({"objective": "quantile", "alpha": 0.75})
            ds = lgb.Dataset(XF[r_f], label=y_f, feature_name=FN,
                             free_raw_data=False)
        b = lgb.train(params, ds, rounds)
        tr_pred = b.predict(XF[r_f])
        r_s, _g_s = _groups_of(D, score_rows, spec)
        s = b.predict(XF[r_s])
    else:
        from catboost import CatBoost, Pool
        gid = np.repeat(np.arange(g_f.size), g_f)
        loss = {"ndcg3": "YetiRank", "ndcg1": "YetiRank",
                "dpairs": "YetiRank", "q75": "Quantile:alpha=0.75"}[obj]
        params = {"loss_function": loss, "iterations": rounds, "depth": depth,
                  "learning_rate": eta, "random_seed": budget.get("seed", N.SEED),
                  "verbose": False, "boosting_type": "Ordered",
                  "thread_count": 8, "allow_writing_files": False}
        if obj == "q75":
            p_f = Pool(XF[r_f], label=y_f, feature_names=FN)
        else:
            p_f = Pool(XF[r_f], label=grade, group_id=gid, feature_names=FN)
        m = CatBoost(params)
        m.fit(p_f)
        tr_pred = m.predict(p_f)
        r_s, _g_s = _groups_of(D, score_rows, spec)
        p_s = (Pool(XF[r_s], feature_names=FN) if obj == "q75" else
               Pool(XF[r_s], group_id=np.repeat(np.arange(_g_s.size), _g_s),
                    feature_names=FN))
        s = m.predict(p_s)
    out = np.full(D["d8"].size, np.nan)
    out[r_s] = s
    return out, {"train_p1": train_dollar_p1(tr_pred, y_f, g_f),
                 "n_fit": int(r_f.size), "n_groups": int(g_f.size),
                 "median_group": float(np.median(g_f)),
                 "rounds": rounds}


# ============================================================== the seating ===
def seat_static(D, spec, score, rows, n, P=None, S=None, delays=None):
    """The champion's schedule: top-N per (asset, day, phase) CELL.  The
    TRAINING grouping is an axis; the SEATING unit is never one — it is what the
    harness actually does, identically for every arm."""
    if spec["group"] == "joint":
        return N.top_per_cell_joint(D, rows, S, n, tuple(delays))
    return N.top_per_cell_score(D, rows, score, n)


def read_arm(D, takes, P=None, val_by_delay=None):
    return N.read_rows(D, N.replay_delayed(D, takes, P,
                                           val_by_delay=val_by_delay))


# ================================================================ STAGE A =====
def _subsample_groups(D, spec, rows, frac, seed):
    if frac >= 1.0:
        return rows
    key = group_key_of(D, rows, spec)
    u = np.unique(key)
    rs = np.random.RandomState(seed)
    keep = set(u[rs.rand(u.size) < frac].tolist())
    if not keep:
        return rows
    return rows[np.isin(key, list(keep))]


def _screen_one(job):
    """One atlas cell, screened on the WEAK eras' INNER blocks only.

    Nothing here ever touches an evaluation era: the fit is on the inner-TRAIN
    days and the reading is on the inner-VALIDATION days, both strictly inside
    the training block of that fold.
    """
    spec, shuffled = job
    D = _D["D"]
    P = _D["P"]
    V = _D["V"]
    t0 = time.time()
    vals, guards, sizes = [], [], []
    try:
        for era in WEAK_ERAS:
            tr, itr, iva, _ev = NA.fold(D, era)
            XF, FN = build_features(D, spec, itr, np.concatenate([itr, iva]))
            val = target_value(D, spec)
            if shuffled:
                rs = np.random.RandomState(N.SEED + 991 + SC.ERA_IDX[era])
                val = val.copy()
                both = np.concatenate([itr, iva])
                val[both] = val[both][rs.permutation(both.size)]
            fit_rows, wg = population(D, spec, era, itr)
            fit_rows = _subsample_groups(D, spec, fit_rows,
                                         SCREEN["group_frac"], N.SEED)
            if spec["group"] == "joint":
                a = NA.joint_arm_screen(D, spec, era, fit_rows, iva, XF, FN,
                                        V, P, SCREEN, shuffled)
                vals.append(a["usd_per_session"] or 0.0)
                guards.append(a.get("train_p1", float("nan")))
                sizes.append(a.get("median_group", float("nan")))
                continue
            sc, info = fit_cell(D, spec, fit_rows, iva, XF, FN, val, SCREEN,
                                wgroup=wg)
            u, n_ = N.committed_policy().get(era, ("cell", 1))
            takes = N.top_per_cell_score(D, N.deployable(D, iva), sc, n_)
            a = read_arm(D, takes, P)
            vals.append(a.get("usd_per_session") or 0.0)
            guards.append(info["train_p1"])
            sizes.append(info["median_group"])
    except Exception as exc:                              # noqa: BLE001
        return (spec, shuffled, None, "%s: %s" % (type(exc).__name__, exc),
                time.time() - t0)
    return (spec, shuffled,
            {"inner_usd": float(np.mean(vals)), "per_era": vals,
             "train_p1": float(np.nanmean(guards)),
             "median_group": float(np.nanmean(sizes))},
            None, time.time() - t0)


def stage_screen(workers=8, limit=None):
    import multiprocessing as mp
    D = N.matrix()
    import st_rank as RK
    _D["D"] = D
    _D["klass"] = RK.class_index(D)[0]
    _D["P"] = N.load_paths()
    _D["V"] = {int(d): N.delayed_value(_D["P"], d, D) for d in N.DELAYS}
    cells = screen_grid()
    if limit:
        cells = cells[:limit]
    rec = grid_receipt()
    rec["n_screen_cells"] = len(cells)
    N.save_json("atlas_grid.receipt.json", rec)
    jobs = [(c, sh) for c in cells for sh in (False, True)]
    N.hb("screen: %d cells x 2 (real + shuffled twin) = %d fits, workers=%d"
         % (len(cells), len(jobs), workers))
    res, errs = {}, []
    t0 = time.time()
    with mp.Pool(processes=workers) as pool:
        for i, (spec, sh, out, err, secs) in enumerate(
                pool.imap_unordered(_screen_one, jobs), start=1):
            k = (spec_id(spec), sh)
            if err:
                errs.append([spec_id(spec), int(sh), err])
            else:
                res[k] = out
            if i % 25 == 0 or i == len(jobs):
                N.hb("screen %d/%d fits %.0fs eta %.0fs errs=%d"
                     % (i, len(jobs), time.time() - t0,
                        (time.time() - t0) / i * (len(jobs) - i), len(errs)))
    ref = res.get((spec_id(REF), False), {}).get("inner_usd", float("nan"))
    rows = []
    for c in cells:
        k = spec_id(c)
        a = res.get((k, False))
        b = res.get((k, True))
        if a is None:
            rows.append([k, c["_block"], "", "", "", "", "", "", "FIT_FAILED",
                         c["_why"]])
            continue
        lift = a["inner_usd"] - ref
        tlift = (b["inner_usd"] - ref) if b else float("nan")
        void = bool(b and b["inner_usd"] >= a["inner_usd"])
        rows.append([k, c["_block"], N._r(a["inner_usd"]), N._r(lift),
                     N._r(tlift), N._r(a["train_p1"], 4),
                     N._r(b["train_p1"], 4) if b else "",
                     N._r(a["median_group"], 1),
                     "VOID" if void else "LIVE", c["_why"]])
    rows.sort(key=lambda r: (-(r[3] if isinstance(r[3], float) else -1e9)))
    N.write_tsv("RANKING_ATLAS_SCREEN.tsv",
                ["cell", "design_block", "inner_usd_per_session",
                 "lift_vs_reference", "shuffled_twin_lift", "train_p1",
                 "train_p1_shuffled", "median_group_size", "status",
                 "mechanism"], rows,
                extra=["STAGE A. promotion: FALSE. These are not champion "
                       "claims and no arm is adopted on this table.",
                       "Fitted on the inner-TRAIN days and read on the "
                       "inner-VALIDATION days of the E3/E5/E7 folds — entirely "
                       "inside the training block, so no evaluation era is "
                       "touched by the screen.",
                       "Yardstick = realised $/session under the harness's own "
                       "cell/N seating, the ONE metric comparable across "
                       "objectives (a cell's own loss is not).",
                       "Every cell has a SHUFFLED TWIN at identical budget; a "
                       "cell whose twin reaches its own lift is VOID.",
                       "reference cell = %s at $%s/session" % (spec_id(REF),
                                                              N._r(ref))])
    N.save_json("atlas_screen.json",
                {"reference_inner_usd": ref,
                 "results": {"%s|%d" % (k[0], k[1]): v
                             for k, v in res.items()},
                 "errors": errs, "secs": round(time.time() - t0, 1)})
    if errs:
        N.write_tsv("RANKING_ATLAS_SCREEN_ERRORS.tsv",
                    ["cell", "shuffled", "error"], errs)
    N.hb("screen done: %d cells, %d errors, %.0fs" % (len(cells), len(errs),
                                                      time.time() - t0))
    return rows


# ================================================================ STAGE B =====
def confirm_arm(D, spec, era, P, V, budget=None):
    """One survivor, on the full walk-forward with the champion's HP discipline.

    Returns the eval-era score column, the booster (so the POLICIES can score
    training rows causally), and the fold's row sets.
    """
    import xgboost as xgb
    tr, itr, iva, ev_r = NA.fold(D, era)
    XF, FN = build_features(D, spec, tr, np.arange(D["d8"].size))
    val = target_value(D, spec)
    fit_rows, wg = population(D, spec, era, tr)
    ifit, _wg2 = population(D, spec, era, itr)
    t0 = time.time()
    if spec["group"] == "joint":
        a, sc, extra = NA.joint_confirm(D, spec, era, ifit, iva, fit_rows, ev_r,
                                        XF, FN, V, P)
        extra["fit_secs"] = round(time.time() - t0, 1)
        return a, sc, extra, (tr, itr, iva, ev_r), (None, None), XF, FN, val
    # inner-block HP search, champion discipline: 12 cells for xgboost, the
    # engine-equivalent depth/lr pair for the others (P6 keeps those narrow)
    grid = (NA.HP_GRID if spec["engine"] == "xgb"
            else tuple({"max_depth": d, "eta": e} for d in (4, 6)
                       for e in (0.05, 0.10)))
    best, best_v, sc_iva = None, -np.inf, None
    for hp in grid:
        s_i, _info = fit_cell(D, spec, ifit, iva, XF, FN, val,
                              dict(CONFIRM, depth=hp["max_depth"],
                                   eta=hp["eta"], rounds=CONFIRM["rounds"]),
                              wgroup=None, hp=hp)
        u_, n_ = N.committed_policy().get(era, ("cell", 1))
        tk = N.top_per_cell_score(D, N.deployable(D, iva), s_i, n_)
        v_ = N.read_rows(D, N.replay_delayed(D, tk, P)).get("usd_per_session")
        if v_ is not None and v_ > best_v:
            best, best_v, sc_iva = hp, v_, s_i
    sc, info = fit_cell(D, spec, fit_rows, ev_r, XF, FN, val,
                        dict(CONFIRM, depth=best["max_depth"], eta=best["eta"],
                             rounds=CONFIRM["rounds"]),
                        wgroup=wg, hp=best)
    sc_tr, _i2 = fit_cell(D, spec, fit_rows, fit_rows, XF, FN, val,
                          dict(CONFIRM, depth=best["max_depth"],
                               eta=best["eta"], rounds=CONFIRM["rounds"]),
                          wgroup=wg, hp=best)
    u_, n_ = N.committed_policy().get(era, ("cell", 1))
    tk = N.top_per_cell_score(D, ev_r, sc, n_)
    a = read_arm(D, tk, P)
    info.update({"hp": best, "inner_usd": best_v,
                 "fit_secs": round(time.time() - t0, 1)})
    # `sc_iva` is OUT OF SAMPLE inside the training block (fitted on inner-train,
    # scored on inner-validation): every threshold this lane sweeps is swept on
    # it, never on the in-sample `sc_tr`, which exists only to supply the outer
    # model's own score CDF for the percentile map.
    return a, sc, info, (tr, itr, iva, ev_r), (sc_tr, sc_iva), XF, FN, val


def apply_policies(D, spec, era, sc, sc_pair, folds, XF, FN, P, V, val):
    """P8: the five selection policies, read off ONE fitted score column."""
    tr, itr, iva, ev_r = folds
    sc_tr, sc_iva = (sc_pair if isinstance(sc_pair, tuple)
                     else (sc_pair, sc_pair))
    u_, n_ = N.committed_policy().get(era, ("cell", 1))
    out = {}
    out["static1"] = (read_arm(D, N.top_per_cell_score(D, ev_r, sc, n_), P), {})
    # --- thresh: seat the cell's top-1 only above an INNER-SWEPT score bar
    if sc_iva is not None and np.isfinite(sc_iva).any():
        q = np.nanpercentile(sc_iva[np.isfinite(sc_iva)], np.arange(0, 96, 5))
        # the sweep runs on the inner-validation rows, scored OUT OF SAMPLE
        best_tau, best_v = -np.inf, -np.inf
        for tau in np.concatenate([[-np.inf], q]):
            tk = [(i, d) for (i, d) in
                  N.top_per_cell_score(D, N.deployable(D, iva), sc_iva, n_)
                  if sc_iva[i] >= tau]
            v_ = N.read_rows(D, N.replay_delayed(D, tk, P)).get(
                "usd_per_session")
            if v_ is not None and v_ > best_v:
                best_tau, best_v = tau, v_
        tk = [(i, d) for (i, d) in N.top_per_cell_score(D, ev_r, sc, n_)
              if sc[i] >= best_tau]
        out["thresh"] = (read_arm(D, tk, P), {"tau": float(best_tau),
                                              "inner_usd": best_v})
    # --- gate60 / gate120: OBJ-2, the two-stage act
    top2_ev = NA.top2_by_score(D, ev_r, sc)
    for dl in N.GATE_DELAYS:
        g_iva, g_ev, rounds = NA.fit_gate(D, P, dl, itr, iva, tr, ev_r, XF, FN,
                                          V)
        top2_iva = (NA.top2_by_score(D, N.deployable(D, iva), sc_iva)
                    if sc_iva is not None and np.isfinite(sc_iva).any() else [])
        best_tau, best_v = -np.inf, -np.inf
        gq = np.nanpercentile(g_iva[np.isfinite(g_iva)],
                              np.arange(0, 96, 5)) if top2_iva else []
        for tau in np.concatenate([[-np.inf], gq]) if len(gq) else [-np.inf]:
            tk, _st = NA.gate_takes(top2_iva, g_iva, tau, dl, V)
            v_ = N.read_rows(D, N.replay_delayed(D, tk, P)).get(
                "usd_per_session")
            if v_ is not None and v_ > best_v:
                best_tau, best_v = tau, v_
        tk, st = NA.gate_takes(top2_ev, g_ev, best_tau, dl, V)
        st.update({"tau": float(best_tau), "inner_usd": best_v,
                   "gate_rounds": rounds})
        out["gate%d" % dl] = (read_arm(D, tk, P), st)
        # RED-FIRST: the DISPLACED gate — the same readings, attached to the
        # WRONG candidates, and RATE-MATCHED so it abstains exactly as often as
        # the real gate does.  Without the rate match the control would differ
        # from the real arm in participation as well as in information, and any
        # gap could be read as either; with it, the ONLY difference left is
        # whether the reading belongs to the candidate it is judging.
        rs = np.random.RandomState(N.SEED + 4242)
        gd = g_ev.copy()
        fin = np.nonzero(np.isfinite(gd))[0]
        gd[fin] = gd[fin][rs.permutation(fin.size)]
        want = st["pass_1"] + st["fall_to_2"]
        tau_d, best_gap = best_tau, None
        if fin.size:
            for cand in np.unique(np.nanpercentile(gd[fin],
                                                   np.arange(0, 100, 2))):
                tkc, stc = NA.gate_takes(top2_ev, gd, cand, dl, V)
                gap = abs((stc["pass_1"] + stc["fall_to_2"]) - want)
                if best_gap is None or gap < best_gap:
                    tau_d, best_gap = cand, gap
        tkd, std = NA.gate_takes(top2_ev, gd, tau_d, dl, V)
        std.update({"tau": float(tau_d), "rate_matched_to": int(want)})
        out["gate%d_DISPLACED" % dl] = (read_arm(D, tkd, P), std)
    # --- stop: OBJ-3, optimal stopping on the historical arrival process
    if sc_tr is not None and sc_iva is not None:
        # u(q) and the arrival process are fitted on the inner-validation rows
        # with OUT-OF-SAMPLE scores; the forward map uses the outer model's own
        # training-row CDF so both sides sit on one percentile scale.
        fit = NA.fit_stopping(D, P, N.deployable(D, iva), sc_iva, val)
        fit["cdf"] = np.sort(sc_tr[np.isfinite(sc_tr)])
        tk, st = NA.stopping_takes(D, P, ev_r, sc, fit, n_per_cell=n_)
        out["stop"] = (read_arm(D, tk, P), st)
        # FORCED PARTICIPATION: a cell that never clears its continuation value
        # takes its LAST arrival anyway.  Without this the stopping arm differs
        # from static top-1 in BOTH sequencing and participation, and the two
        # cannot be told apart; with it the seat count matches and the delta is
        # the sequencing cost alone.
        tkf, stf = NA.stopping_takes(D, P, ev_r, sc, fit, n_per_cell=n_,
                                     forced=True)
        out["stop_forced"] = (read_arm(D, tkf, P), stf)
        # the CEILING of the sequencing object: clairvoyant about the arriving
        # member's realised value, ignorant of every member still to come.
        tko, sto = NA.stopping_takes(D, P, ev_r, sc, fit, n_per_cell=n_,
                                     oracle_val=val, forced=True)
        out["stop_ORACLE"] = (read_arm(D, tko, P), sto)
    return out


def holm(pvals):
    """Holm-Bonferroni over ONE family, returning the adjusted p-values."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    out = [0.0] * m
    run = 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (m - k) * pvals[i]))
        out[i] = run
    return out


def _paired_p(delta, lo, hi):
    """A two-sided p from a CR1 interval (the interval IS the inference here;
    the p is its restatement for the Holm family)."""
    from math import erfc, sqrt
    if delta is None or lo is None or hi is None:
        return 1.0
    se = (hi - lo) / (2 * 1.96)
    if se <= 0:
        return 1.0
    return float(erfc(abs(delta) / (se * sqrt(2.0))))


def _confirm_one(job):
    """One (arm, era) confirm fit + its five policy reads, in a worker."""
    spec, era = job
    D, P, V = _D["D"], _D["P"], _D["V"]
    k = spec_id(spec)
    try:
        a, sc, info, folds, sc_tr, XF, FN, val = confirm_arm(D, spec, era, P, V)
    except Exception as exc:                            # noqa: BLE001
        return (k, era, spec.get("_block", ""), None, None, None,
                "%s: %s" % (type(exc).__name__, exc))
    try:
        pols = apply_policies(D, spec, era, sc, sc_tr, folds, XF, FN, P, V, val)
    except Exception as exc:                            # noqa: BLE001
        N.hb("policy FAIL %s %s: %s" % (k, era, exc))
        pols = {}
    # the "_"-prefixed per-session vectors MUST survive the pickle: pool_reads
    # needs them to pool across eras with the day clustering intact
    return (k, era, spec.get("_block", ""), a, info, pols, None)


def stage_confirm(top_n=15, eras=CONFIRM_ERAS):
    import st_rank as RK
    D = N.matrix()
    _D["D"] = D
    _D["klass"] = RK.class_index(D)[0]
    P = N.load_paths()
    V = {int(d): N.delayed_value(P, d, D) for d in N.DELAYS}
    scr = N.load_json("atlas_screen.json")
    if scr is None:
        raise N.NewObjRefusal("no screen results — run --screen first")
    res = scr["results"]
    cells = {spec_id(c): c for c in screen_grid()}
    ranked = []
    for k, c in cells.items():
        a = res.get("%s|0" % k)
        b = res.get("%s|1" % k)
        if a is None:
            continue
        if b is not None and b["inner_usd"] >= a["inner_usd"]:
            continue                                   # VOID (twin reached it)
        ranked.append((a["inner_usd"], k))
    ranked.sort(reverse=True)
    keep = [k for _v, k in ranked[:top_n]]
    if spec_id(REF) not in keep:
        keep.append(spec_id(REF))
    N.hb("confirm: %d survivors (+reference) of %d screened"
         % (len(keep) - 1, len(cells)))
    import multiprocessing as mp
    _D["P"] = P
    _D["V"] = V
    jobs = [(cells[k], era) for k in keep for era in eras]
    rows, pol_rows, per_arm, reps = [], [], {}, {}
    t0 = time.time()
    with mp.Pool(processes=8) as pool:
        for i, (k, era, blk, a, info, pols, err) in enumerate(
                pool.imap_unordered(_confirm_one, jobs), start=1):
            if err:
                N.hb("confirm FAIL %s %s: %s" % (k, era, err))
                continue
            per_arm.setdefault(k, []).append(dict(a, era=era))
            reps.setdefault(k, {})[era] = a
            rows.append([k, era, blk, a["n_seated"],
                         N._r(a["usd_per_session"]), N._r(a["ps_lo"]),
                         N._r(a["ps_hi"]), N._r(a["usd_per_trade"]),
                         N._r(a["frac_ge_1000"], 4),
                         N._r(a["capture_oracle"], 4),
                         json.dumps(info.get("hp", {})),
                         info.get("fit_secs")])
            for pname, (pa, pst) in (pols or {}).items():
                pol_rows.append([k, era, pname, pa.get("n_seated"),
                                 N._r(pa.get("usd_per_session")),
                                 N._r(pa.get("ps_lo")), N._r(pa.get("ps_hi")),
                                 N._r(pa.get("usd_per_trade")),
                                 json.dumps({kk: (round(vv, 3)
                                                  if isinstance(vv, float)
                                                  else vv)
                                             for kk, vv in pst.items()})])
                per_arm.setdefault("%s@@%s" % (k, pname), []).append(
                    dict(pa, era=era))
            N.hb("confirm %d/%d %s %s: $%s/session (%d seats) %.0fs eta %.0fs"
                 % (i, len(jobs), k, era, N._r(a["usd_per_session"]),
                    a["n_seated"], time.time() - t0,
                    (time.time() - t0) / i * (len(jobs) - i)))
    # pooled + the ONE Holm family, champion as the reference arm
    ref_parts = per_arm.get(spec_id(REF), [])
    ref_pool = N.pool_reads(ref_parts)
    fam = []
    for k, parts in sorted(per_arm.items()):
        q = N.pool_reads(parts)
        if not q.get("n_sessions"):
            continue
        d_ = (q["usd_per_session"] - ref_pool["usd_per_session"]) \
            if ref_pool.get("usd_per_session") is not None else None
        rows.append([k, "POOLED_E3-E7", "", q["n_seated"],
                     N._r(q["usd_per_session"]), N._r(q["ps_lo"]),
                     N._r(q["ps_hi"]), N._r(q["usd_per_trade"]),
                     N._r(q["frac_ge_1000"], 4),
                     N._r(q["capture_oracle"], 4), "", ""])
        if k != spec_id(REF) and d_ is not None:
            se = ((q["ps_hi"] - q["ps_lo"]) ** 2
                  + (ref_pool["ps_hi"] - ref_pool["ps_lo"]) ** 2) ** 0.5 \
                / (2 * 1.96)
            fam.append([k, d_, _paired_p(d_, d_ - 1.96 * se, d_ + 1.96 * se)])
    if fam:
        adj = holm([f[2] for f in fam])
        hol = [[f[0], N._r(f[1]), N._r(f[2], 6), N._r(a, 6),
                "SIGNIFICANT" if a < 0.05 else "not significant"]
               for f, a in zip(fam, adj)]
        hol.sort(key=lambda r: -(r[1] if isinstance(r[1], float) else -1e9))
        N.write_tsv("RANKING_ATLAS_HOLM.tsv",
                    ["arm", "delta_vs_champion_usd", "p_raw", "p_holm",
                     "verdict"], hol,
                    extra=["ONE Holm family over every confirmed arm and "
                           "policy read, m=%d.  The whole screen's trial count "
                           "(%d cells x 2) is recorded in the grid receipt and "
                           "is the multiplicity this family sits inside."
                           % (len(fam), len(cells))])
    N.write_tsv("RANKING_ATLAS_CONFIRM.tsv",
                ["cell", "era", "design_block", "n_seated", "usd_per_session",
                 "ps_lo", "ps_hi", "usd_per_trade", "frac_ge_1000",
                 "capture_oracle", "hp", "fit_secs"], rows,
                extra=["STAGE B.  Full E3-E7 walk-forward, champion HP "
                       "discipline (inner-block selection only), CR1 intervals "
                       "clustered by DAY, m3_walk's committed per-era (unit,N), "
                       "replay proved seat-for-seat against m3_walk.replay_rows."
                       "  E8 IS NOT IN THIS TABLE."])
    N.write_tsv("RANKING_ATLAS_POLICIES.tsv",
                ["cell", "era", "policy", "n_seated", "usd_per_session",
                 "ps_lo", "ps_hi", "usd_per_trade", "detail"], pol_rows,
                extra=["P8: the five selection policies read off ONE fitted "
                       "score column per arm.  gate60/gate120 = OBJ-2 "
                       "(rank-then-gate-verify, threshold swept on the inner "
                       "block); *_DISPLACED = the red-first control, the same "
                       "gate readings attached to the WRONG candidates; "
                       "stop = OBJ-3 (backward induction on the historical "
                       "arrival process); stop_ORACLE = its clairvoyant-on-the-"
                       "present ceiling."])
    N.save_json("atlas_confirm.json",
                {k: [{kk: vv for kk, vv in a.items()
                      if not kk.startswith("_")} for a in v]
                 for k, v in per_arm.items()})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--screen", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--blind", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--top-n", type=int, default=15)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    if a.grid:
        print(json.dumps(grid_receipt(), indent=1, default=str))
    elif a.screen:
        stage_screen(workers=a.workers, limit=a.limit)
    elif a.confirm:
        stage_confirm(top_n=a.top_n)
    elif a.blind:
        stage_blind()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()


# ========================================================== THE BLIND READ ====
def stage_blind(era=N.BLIND_ERA):
    """E8, opened ONCE, for the single best CONFIRMED arm.

    The choice of which arm to read is made entirely on the E3-E7 confirm table;
    E8 has never been an input to any fit, threshold, HP choice or ranking in
    this lane.  The 2025-H2 holdout stays sealed.
    """
    import st_rank as RK
    D = N.matrix()
    _D["D"] = D
    _D["klass"] = RK.class_index(D)[0]
    P = N.load_paths()
    V = {int(d): N.delayed_value(P, d, D) for d in N.DELAYS}
    _D["P"], _D["V"] = P, V
    conf = N.load_json("atlas_confirm.json")
    if conf is None:
        raise N.NewObjRefusal("no confirm results — run --confirm first")
    cells = {spec_id(c): c for c in screen_grid()}
    best, best_v = None, -np.inf
    for k, parts in conf.items():
        if "@@" in k or k not in cells:
            continue
        q = N.pool_reads([p for p in parts if p.get("era") in CONFIRM_ERAS])
        if q.get("usd_per_session") is not None and q["usd_per_session"] > best_v:
            best, best_v = k, q["usd_per_session"]
    N.hb("BLIND READ: single best confirmed arm = %s ($%s/session on E3-E7); "
         "opening %s once" % (best, N._r(best_v), era))
    rows = []
    for k in sorted({best, spec_id(REF)}):
        a, sc, info, folds, sc_tr, XF, FN, val = confirm_arm(
            D, cells[k], era, P, V)
        rows.append([k, era, a["n_seated"], N._r(a["usd_per_session"]),
                     N._r(a["ps_lo"]), N._r(a["ps_hi"]),
                     N._r(a["usd_per_trade"]), N._r(a["frac_ge_1000"], 4),
                     N._r(a["capture_oracle"], 4),
                     json.dumps(info.get("hp", {}))])
        # per (era, asset) against the standing all-years criterion
        for ai in sorted(set(D["asset_idx"][folds[3]].tolist())):
            sel = folds[3][D["asset_idx"][folds[3]] == ai]
            u_, n_ = N.committed_policy().get(era, ("cell", 1))
            aa = read_arm(D, N.top_per_cell_score(D, sel, sc, n_), P)
            rows.append([k, "%s|%s" % (era, MC.ASSET_ORDER[ai]),
                         aa["n_seated"], N._r(aa["usd_per_session"]),
                         N._r(aa["ps_lo"]), N._r(aa["ps_hi"]),
                         N._r(aa["usd_per_trade"]),
                         N._r(aa["frac_ge_1000"], 4),
                         N._r(aa["capture_oracle"], 4), ""])
        N.hb("blind %s %s: $%s/session" % (k, era, N._r(a["usd_per_session"])))
    N.write_tsv("RANKING_ATLAS_BLIND.tsv",
                ["cell", "era", "n_seated", "usd_per_session", "ps_lo",
                 "ps_hi", "usd_per_trade", "frac_ge_1000", "capture_oracle",
                 "hp"], rows,
                extra=["THE ONE BLIND READ.  The arm was chosen entirely on the "
                       "E3-E7 confirm table; E8 was never an input to any fit, "
                       "threshold, hyper-parameter or ranking in this lane.",
                       "The 2025-H2 holdout (d8 >= 20250701) is untouched and "
                       "is not this lane's to open."])
    return rows

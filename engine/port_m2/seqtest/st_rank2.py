#!/usr/bin/python3
"""PORT M2 FIXPASS2 — F3 (the DEPLOY-MATCHED ranking objective) + F6/B3 + F6/B1.

F3 (matrix tag R7).  The first pass's mechanism, named in SEQTEST.md §7: the
ranker was trained to order candidates INSIDE an `(asset, day, class)` group,
but the deployed schedule takes the top 3 ACROSS the day's groups.  "A
within-group objective has no reason to make its scores comparable between
groups."  The repair is to rank in the SCHEDULE'S OWN SELECTION UNIT:

    GROUP = (asset, trade DAY) — every candidate of the day, one list,
            top-3 taken across it.  Exactly what `m3_walk.topn_takes` does.

Two deploy-matched forms are trained and BOTH are reported, per the ruling:
  * SOFTMAX-OVER-DAY   — listwise softmax cross-entropy over the whole day's
                          candidate set against the dollar-softmax target
                          (`st_rank.listnet_loss`, day groups);
  * LAMBDARANK-DAY     — xgboost `rank:ndcg` with `(asset, day)` groups and
                          `ndcg@3`, the same fixed D-021 grade ladder.

F6/B3 HARD NEGATIVES.  The committed wall pairs (`st_aux2.wall_pairs`) enter
the loss as an explicit pairwise-logistic term at weight `hardneg`: the winner
leg must outrank the -$900 leg it is a minute away from.

F6/B1 DAY MEMORY.  `st_aux2.day_memory`'s 10 causal columns are appended to the
context block behind the `--daymem` toggle.

Everything else is the lane's unchanged stack and `m3_walk`'s deployable arm
verbatim for the dollars.

Run:
    st_rank2.py --run --group day --mode ctx --tag RANK2_DAY_CTX
    st_rank2.py --lmart --group day
"""
import argparse
import json
import os
import time

import numpy as np
import torch
import torch.nn.functional as F

import st_common as SC
import st_aux2 as A2
import st_run as R
import st_rank as RK
import st_pretrain as P
import m3_common as M3

DEV = R.DEV

RANK_EPOCHS = 15
RANK_LR = 1e-3
ROW_BUDGET = 12288                 # padded rows per optimiser step
HARDNEG_PER_STEP = 512
CLASS_MAX_GROUP = RK.MAX_GROUP     # 64, the V1 convention for class groups


# ================================================================ groups =====
def build_groups(D, rows, klass, group="cell"):
    """Member sets on the grouping axis, keyed by `st_rank.group_key` — the
    lane's committed definition, imported and never re-typed (D-006).

    `cell` (asset, day, PHASE) is **the schedule's own selection unit**: the
    committed m3 policy seats top-1 per cell, so a cell group's ordering IS the
    ordering that gets seated.  A cell or day group is therefore NEVER split —
    splitting it would put the objective back off the deployment unit, which is
    the whole defect being repaired.  Only the V1 `class` axis keeps its
    MAX_GROUP split, so that arm reproduces the first pass exactly.
    """
    r = np.asarray(rows, dtype=np.int64)
    key = RK.group_key(D, r, klass, group)
    order = np.lexsort((D["dec_sec"][r], key))
    ro, ko = r[order], key[order]
    starts = [0] + (np.flatnonzero(ko[1:] != ko[:-1]) + 1).tolist()
    stops = starts[1:] + [ko.size]
    out = []
    for a, b in zip(starts, stops):
        if b - a < 2:
            continue
        g = ro[a:b]
        if group == "class":
            for i in range(0, g.size, CLASS_MAX_GROUP):
                piece = g[i:i + CLASS_MAX_GROUP]
                if piece.size >= 2:
                    out.append(piece)
        else:
            out.append(g)          # the seating unit, whole
    return out


def batches(groups, rng, budget=ROW_BUDGET):
    """Size-bucketed batching: groups are ordered by length so padding waste
    stays small, then the BATCHES (not the groups) are shuffled."""
    order = np.argsort([g.size for g in groups], kind="stable")
    out, cur, mx = [], [], 0
    for i in order.tolist():
        m = max(mx, groups[i].size)
        if cur and m * (len(cur) + 1) > budget:
            out.append(cur)
            cur, mx = [i], groups[i].size
        else:
            cur.append(i)
            mx = m
    if cur:
        out.append(cur)
    rng.shuffle(out)
    return out


def pad(groups, idx):
    n = max(groups[i].size for i in idx)
    rows = np.zeros((len(idx), n), dtype=np.int64)
    mask = np.zeros((len(idx), n), dtype=bool)
    for j, gi in enumerate(idx):
        g = groups[gi]
        rows[j, :g.size] = g
        mask[j, :g.size] = True
    return rows, mask


# ================================================================= losses ====
def hardneg_loss(sw, sl):
    """Pairwise logistic on the committed wall pairs: the +$1,000 leg must
    outrank the -$900 leg on the other side of the same cell."""
    return F.softplus(-(sw - sl)).mean()


# ================================================================== the fit ==
def _fwd(m, E, C, pos, emu, esd, cmu, csd, mode, rows_flat):
    if mode in ("seq", "fused"):
        e = torch.from_numpy(
            (E[pos[rows_flat]].astype(np.float32) - emu) / esd).to(DEV)
    else:
        e = torch.zeros(rows_flat.size, 1, device=DEV)
    c = P.ctx_batch(C, rows_flat, cmu, csd)
    return m(e, c)[:, 0]


def fit_ranker(loss_name, E, C, pos, emu, esd, cmu, csd, g_tr, g_va, value,
               mode, tag, max_epochs, hardneg=0.0, pairs=None):
    torch.manual_seed(SC.SEED)
    m = P.ProbeHead(E.shape[1] if E is not None else 1, C.shape[1],
                    mode=mode).to(DEV)
    opt = torch.optim.AdamW(m.parameters(), lr=RANK_LR,
                            weight_decay=SC.WEIGHT_DECAY)
    rng = np.random.RandomState(SC.SEED)
    fn = RK.listnet_loss if loss_name == "listnet" else RK.listmle_loss
    best, best_ep, bad, best_state = -np.inf, 0, 0, None
    hn_hist = []
    for ep in range(1, int(max_epochs) + 1):
        m.train()
        t0 = time.time()
        hn_ep = []
        for sel in batches(g_tr, rng):
            rows, mask = pad(g_tr, sel)
            s = _fwd(m, E, C, pos, emu, esd, cmu, csd, mode,
                     rows.reshape(-1)).view(rows.shape)
            y = torch.from_numpy(value[rows]).to(DEV).float()
            mk = torch.from_numpy(mask).to(DEV)
            loss = fn(s, y, mk)
            if hardneg > 0 and pairs is not None and pairs[0].size:
                k = rng.randint(0, pairs[0].size,
                                size=min(HARDNEG_PER_STEP, pairs[0].size))
                pr = np.concatenate([pairs[0][k], pairs[1][k]])
                sp = _fwd(m, E, C, pos, emu, esd, cmu, csd, mode, pr)
                hl = hardneg_loss(sp[:k.size], sp[k.size:])
                hn_ep.append(float(hl.item()))
                loss = loss + hardneg * hl
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
        hn_hist.append(round(float(np.mean(hn_ep)), 5) if hn_ep else None)
        if g_va:
            rows_va = np.unique(np.concatenate(g_va))
            sc = predict_rows(m, E, C, pos, emu, esd, cmu, csd, mode, rows_va)
            full = np.full(value.size, np.nan)
            full[sc[0]] = sc[1]
            nd, ng = RK.ndcg_at_k(full, value, g_va, 3)
        else:
            nd, ng = float(ep), 0
        SC.hb("%s %s ep%d NDCG@3=%.5f (n=%d, hn=%s, %.0fs)"
              % (tag, loss_name, ep, nd, ng, hn_hist[-1], time.time() - t0))
        if np.isfinite(nd) and nd > best:
            best, best_ep, bad = float(nd), ep, 0
            best_state = {k: v.detach().clone() for k, v in
                          m.state_dict().items()}
        else:
            bad += 1
            if bad >= 3:
                break
    if best_state is not None:
        m.load_state_dict(best_state)
    return m, {"loss": loss_name, "inner_ndcg3": best, "best_epoch": best_ep,
               "hardneg_curve": hn_hist}


def predict_rows(m, E, C, pos, emu, esd, cmu, csd, mode, rows, bs=16384):
    m.eval()
    out = np.zeros(rows.size, dtype=np.float64)
    with torch.no_grad():
        for i in range(0, rows.size, bs):
            r = rows[i:i + bs]
            out[i:i + bs] = _fwd(m, E, C, pos, emu, esd, cmu, csd, mode,
                                 r).float().cpu().numpy()
    return rows, out


# ==================================================================== run ====
def context_block(D, daymem):
    C = D["X"]
    if not daymem:
        return C, list(D["names"])
    M = A2.day_memory(D)
    Z = np.sign(M) * np.log1p(np.abs(M))
    return (np.hstack([C, Z.astype(np.float64)]),
            list(D["names"]) + list(A2.MEM_COLS))


def trunk_tokenizer(trunk, default="v1"):
    """A trunk's own vocabulary, read from its receipt — a fused ranker that
    embedded V2 windows with a V1 trunk (or the reverse) would be reading a
    different alphabet from the one the trunk was trained on."""
    if trunk in (None, "NONE"):
        return default
    if trunk.endswith("_V2") or trunk.startswith("PRE_V2"):
        default = "v2"
    p = os.path.join(P.TRUNK_DIR, "%s.json" % trunk)
    if os.path.exists(p):
        with open(p) as fh:
            return str(json.load(fh).get("tokenizer", default))
    return default


def run(trunk="NONE", mode="ctx", group="cell", losses=("listnet", "listmle"),
        hardneg=0.0, daymem=False, test_eras=SC.TEST_ERAS, tag=None,
        shuffle=False, tokver=None, from_era="E2"):
    P.use_tokenizer(tokver or trunk_tokenizer(trunk))
    if mode == "ctx":
        # a context-only ranker never touches a tensor: skip the 2.4 GB token
        # load entirely
        import m3_walk as W
        D, _p = W.load_matrix()
        pos = np.zeros(D["d8"].size, dtype=np.int64)
    else:
        ft = P.load_ft()
        D, pos = ft["D"], ft["pos"]
    C, cnames = context_block(D, daymem)
    E = (np.asarray(P.embed_all(trunk))
         if (mode in ("seq", "fused") and trunk != "NONE") else None)
    if mode in ("seq", "fused") and E is None:
        raise SC.SeqTestRefusal("mode %r needs a trunk; got %r" % (mode, trunk))
    klass, cls_names = RK.class_index(D)
    ceil = R.ceilings_of(D)
    value = D["cert_close_usd"].astype(np.float64)
    n = D["d8"].size
    score = np.full(n, np.nan)
    name = tag or ("RANK2_%s_%s_%s%s%s%s%s"
                   % (group.upper(), trunk, mode.upper(),
                      "_HN%g" % hardneg if hardneg else "",
                      "_MEM" if daymem else "",
                      "_ALLDATA" if from_era == "PRE_E1" else "",
                      "_SHUFFLED" if shuffle else ""))
    WP = A2.wall_pairs(D) if hardneg > 0 else None
    ledger = []
    for era in test_eras:
        t0 = time.time()
        tr, ev = R.fold_rows(D, era, from_era=from_era)
        tr = tr[pos[tr] >= 0]
        ev = ev[pos[ev] >= 0]
        j = D["names"].index("in_news_window")
        tr = tr[D["X"][tr, j] < 0.5]
        ev_r = ev[D["X"][ev, j] < 0.5]
        cut = SC.inner_split_days(D["d8"][tr])
        itr, iva = tr[D["d8"][tr] <= cut], tr[D["d8"][tr] > cut]
        SC.assert_disjoint_days(itr, iva, D["d8"], tag="%s inner" % era)
        g_itr = build_groups(D, itr, klass, group)
        g_iva = build_groups(D, iva, klass, group)
        g_tr = build_groups(D, tr, klass, group)
        g_ev = build_groups(D, ev_r, klass, group)
        g_ev_cls = build_groups(D, ev_r, klass, "class")
        g_ev_cell = build_groups(D, ev_r, klass, "cell")
        value_fit = value
        if shuffle:
            # THE RED-FIRST CONTROL: permute the TRAINING block's dollars.
            value_fit = value.copy()
            rs = np.random.RandomState(SC.SEED + SC.ERA_IDX[era])
            value_fit[tr] = value[tr][rs.permutation(tr.size)]
        pr_i = pr_t = None
        if WP is not None:
            si = np.zeros(n, dtype=bool)
            si[itr] = True
            k = si[WP[0]] & si[WP[1]]
            pr_i = (WP[0][k], WP[1][k])
            st_ = np.zeros(n, dtype=bool)
            st_[tr] = True
            k2 = st_[WP[0]] & st_[WP[1]]
            pr_t = (WP[0][k2], WP[1][k2])
        emu = esd = None
        if E is not None:
            sub = E[pos[itr]].astype(np.float32)
            emu, esd = sub.mean(0), np.maximum(sub.std(0), 1e-3)
        cmu, csd = P.ctx_stats(C, itr)
        cand = []
        for ln in losses:
            _m, info = fit_ranker(ln, E, C, pos, emu, esd, cmu, csd, g_itr,
                                  g_iva, value_fit, mode,
                                  "%s/%s" % (name, era), RANK_EPOCHS, hardneg,
                                  pr_i)
            cand.append((info["inner_ndcg3"], ln, info))
            del _m
        cand.sort(key=lambda z: (-z[0], z[1]))
        sel = cand[0][2]
        if E is not None:
            sub = E[pos[tr]].astype(np.float32)
            emu, esd = sub.mean(0), np.maximum(sub.std(0), 1e-3)
        cmu, csd = P.ctx_stats(C, tr)
        m, _i = fit_ranker(sel["loss"], E, C, pos, emu, esd, cmu, csd, g_tr,
                           None, value_fit, mode,
                           "%s/%s refit" % (name, era), sel["best_epoch"],
                           hardneg, pr_t)
        rows, s = predict_rows(m, E, C, pos, emu, esd, cmu, csd, mode, ev_r)
        score[rows] = s
        nd_day, ng_day = RK.ndcg_at_k(score, value, g_ev, 3)
        nd_cls, ng_cls = RK.ndcg_at_k(score, value, g_ev_cls, 3)
        nd_cell, ng_cell = RK.ndcg_at_k(score, value, g_ev_cell, 3)
        rnd = np.random.RandomState(SC.SEED).rand(n)
        ledger.append({
            "era": era, "loss": sel["loss"], "group": group,
            "inner_ndcg3": sel["inner_ndcg3"], "best_epoch": sel["best_epoch"],
            "hardneg": hardneg, "daymem": bool(daymem),
            "hardneg_pairs_train": int(pr_t[0].size) if pr_t else 0,
            "loss_curve": [[c[1], round(float(c[0]), 5)] for c in cand],
            "n_groups_train": len(g_tr), "n_groups_eval": len(g_ev),
            "median_group": int(np.median([g.size for g in g_ev]))
            if g_ev else 0,
            "eval_ndcg3_day": nd_day, "n_scored_groups_day": ng_day,
            "eval_ndcg3_class": nd_cls, "n_scored_groups_class": ng_cls,
            "eval_ndcg3_cell": nd_cell, "n_scored_groups_cell": ng_cell,
            "from_era": from_era,
            "eval_ndcg3_random_day": RK.ndcg_at_k(rnd, value, g_ev, 3)[0],
            "eval_ndcg3_random_class": RK.ndcg_at_k(rnd, value, g_ev_cls, 3)[0],
            "eval_ndcg3_earliest_day": RK.ndcg_at_k(
                -D["dec_sec"].astype(np.float64), value, g_ev, 3)[0],
            "eval_ndcg3_earliest_class": RK.ndcg_at_k(
                -D["dec_sec"].astype(np.float64), value, g_ev_cls, 3)[0],
            "n_eval": int(ev_r.size), "fit_secs": round(time.time() - t0, 1)})
        SC.hb("RANK2 %s %s: loss=%s NDCG@3 day %.4f / class %.4f (%.0fs)"
              % (name, era, sel["loss"], nd_day, nd_cls, time.time() - t0))
        del m
        if DEV == "cuda":
            torch.cuda.empty_cache()
    per, pool = R.eval_scores(D, score, score, ceil, pos, test_eras=test_eras)
    R.save_result(name, {"kind": "rank2", "shuffled": bool(shuffle),
                         "arch": "listwise-%s-%s"
                         % (group, mode), "group": group, "mode": mode,
                         "trunk": trunk, "hardneg": hardneg,
                         "daymem": bool(daymem), "n_ctx": int(C.shape[1]),
                         "group_unit": group, "from_era": from_era,
                         "rung": "40M-frozen" if E is not None else "ctx-only",
                         "L": P.CTX, "classes": cls_names,
                         "pretrained": (E is not None
                                        and not trunk.startswith("RANDOM")),
                         "tokenizer": P.TOKVER(), "vocab": P.VOCAB(),
                         "per_era": [R._strip(a) for a in per], "pooled": pool,
                         "ledger": ledger, "gpu": R.gpu_note()})
    np.savez(os.path.join(R._sdir(), "%s.npz" % name), champ=score, win=score)
    SC.hb("%s pooled capture_oracle=%.4f [%.4f,%.4f] $%.2f/session"
          % (name, pool["capture_oracle"] or float("nan"),
             pool["co_lo"] or float("nan"), pool["co_hi"] or float("nan"),
             pool["usd_per_session"] or float("nan")))
    return pool


# =========================================== F3(b): LambdaMART, day groups ===
def _group_arrays(D, rows, klass, group):
    """Rows sorted by group + the xgboost group-size vector.  The KEY is
    `st_rank.group_key` — the lane's committed definition — so `cell` here is
    the same (asset, day, PHASE) unit the schedule seats on."""
    r = np.asarray(rows, dtype=np.int64)
    key = RK.group_key(D, r, klass, group)
    order = np.lexsort((D["dec_sec"][r], key))
    ro, ko = r[order], key[order]
    _u, cnt = np.unique(ko, return_counts=True)
    return ro, cnt


def lmart(group="cell", daymem=False, test_eras=SC.TEST_ERAS, tag=None,
          use_creator=False, from_era="E2", hardneg=0.0):
    import xgboost as xgb
    import st_lmart as LM
    import st_creator as CR
    import m3_walk as W
    D, _p = W.load_matrix()
    C, cnames = context_block(D, daymem)
    if use_creator:
        A, cols, _cov = CR.creator_columns(D)
        C = np.hstack([C, A.astype(np.float64)])
        cnames = cnames + cols
    klass, cls_names = RK.class_index(D)
    ceil = R.ceilings_of(D)
    value = D["cert_close_usd"].astype(np.float64)
    n = D["d8"].size
    score = np.full(n, np.nan)
    pos = np.zeros(n, dtype=np.int64)
    name = tag or ("LMART2_%s%s%s%s"
                   % (group.upper(), "_MEM" if daymem else "",
                      "_CRE26" if use_creator else "",
                      "_ALLDATA" if from_era == "PRE_E1" else "")
                   + ("_HN%g" % hardneg if hardneg else ""))
    j = D["names"].index("in_news_window")
    # F6/B3 for a LambdaMART: the objective has no place for an auxiliary
    # pairwise term, so the hard negatives enter as INSTANCE WEIGHTS — every row
    # that is a leg of a committed wall pair is upweighted by `hardneg`, which
    # makes the +$1,000 / -$900 minute-apart decisions the ones the trees are
    # most penalised for getting wrong.
    is_leg = np.zeros(n, dtype=bool)
    if hardneg > 0:
        pw, pl = A2.wall_pairs(D)
        is_leg[np.unique(np.concatenate([pw, pl]))] = True
        SC.hb("B3: %d wall-pair legs -> the CELLS holding them are upweighted "
              "x%.2f" % (int(is_leg.sum()), 1.0 + float(hardneg)))

    def gweights(ro, cnt):
        """xgboost's ranking objective weights QUERY GROUPS, not rows, so B3
        upweights every CELL that holds a committed wall pair."""
        if hardneg <= 0:
            return None
        w = np.ones(cnt.size, dtype=np.float32)
        at = 0
        for i, c in enumerate(cnt.tolist()):
            if is_leg[ro[at:at + c]].any():
                w[i] = 1.0 + float(hardneg)
            at += c
        return w
    ledger = []
    for era in test_eras:
        t0 = time.time()
        tr, ev = R.fold_rows(D, era, from_era=from_era)
        tr = tr[D["X"][tr, j] < 0.5]
        ev_r = ev[D["X"][ev, j] < 0.5]
        cut = SC.inner_split_days(D["d8"][tr])
        itr, iva = tr[D["d8"][tr] <= cut], tr[D["d8"][tr] > cut]
        SC.assert_disjoint_days(itr, iva, D["d8"], tag="%s inner" % era)
        r_itr, g_itr = _group_arrays(D, itr, klass, group)
        r_iva, g_iva = _group_arrays(D, iva, klass, group)
        dtr = xgb.DMatrix(C[r_itr], label=LM.grades(value[r_itr]),
                          feature_names=cnames)
        dtr.set_group(g_itr)
        if hardneg > 0:
            dtr.set_weight(gweights(r_itr, g_itr))
        dva = xgb.DMatrix(C[r_iva], label=LM.grades(value[r_iva]),
                          feature_names=cnames)
        dva.set_group(g_iva)
        if hardneg > 0:
            dva.set_weight(gweights(r_iva, g_iva))
        cfg = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
               "tree_method": "hist", "eta": 0.05, "max_depth": 6,
               "min_child_weight": 20, "subsample": 0.8,
               "colsample_bytree": 0.8, "lambdarank_pair_method": "topk",
               "lambdarank_num_pair_per_sample": 8,
               "seed": SC.SEED, "nthread": 8}
        b = xgb.train(cfg, dtr, LM.ROUNDS, evals=[(dva, "inner")],
                      early_stopping_rounds=LM.EARLY, verbose_eval=False)
        best_rounds = int(b.best_iteration) + 1
        inner = float(b.best_score)
        r_tr, g_tr = _group_arrays(D, tr, klass, group)
        dall = xgb.DMatrix(C[r_tr], label=LM.grades(value[r_tr]),
                           feature_names=cnames)
        dall.set_group(g_tr)
        if hardneg > 0:
            dall.set_weight(gweights(r_tr, g_tr))
        b2 = xgb.train(cfg, dall, best_rounds)
        score[ev_r] = b2.predict(xgb.DMatrix(C[ev_r], feature_names=cnames))
        g_ev = build_groups(D, ev_r, klass, group)
        g_ev_cls = build_groups(D, ev_r, klass, "class")
        g_ev_cell = build_groups(D, ev_r, klass, "cell")
        nd_day, ng = RK.ndcg_at_k(score, value, g_ev, 3)
        nd_cls, _ = RK.ndcg_at_k(score, value, g_ev_cls, 3)
        nd_cell, _ = RK.ndcg_at_k(score, value, g_ev_cell, 3)
        rnd = np.random.RandomState(SC.SEED).rand(n)
        ledger.append({"era": era, "loss": "rank:ndcg", "group": group,
                       "inner_ndcg3": inner, "best_epoch": best_rounds,
                       "daymem": bool(daymem),
                       "n_groups_train": int(g_tr.size),
                       "n_groups_eval": len(g_ev),
                       "eval_ndcg3_day": nd_day, "eval_ndcg3_class": nd_cls,
                       "eval_ndcg3_cell": nd_cell, "from_era": from_era,
                       "eval_ndcg3_random_day": RK.ndcg_at_k(rnd, value, g_ev,
                                                             3)[0],
                       "eval_ndcg3_random_class": RK.ndcg_at_k(rnd, value,
                                                               g_ev_cls, 3)[0],
                       "n_scored_groups_day": ng, "n_eval": int(ev_r.size),
                       "fit_secs": round(time.time() - t0, 1)})
        SC.hb("LMART2 %s %s: rounds=%d NDCG@3 day %.4f / class %.4f (%.0fs)"
              % (name, era, best_rounds, nd_day, nd_cls, time.time() - t0))
    per, pool = R.eval_scores(D, score, score, ceil, pos, test_eras=test_eras)
    R.save_result(name, {"kind": "rank2", "arch": "lambdamart-%s" % group,
                         "group": group, "mode": "ctx", "trunk": "NONE",
                         "daymem": bool(daymem), "use_creator": bool(use_creator),
                         "group_unit": group, "from_era": from_era,
                         "hardneg": hardneg,
                         "n_ctx": int(C.shape[1]), "rung": "gbt", "L": 0,
                         "classes": cls_names, "pretrained": False,
                         "per_era": [R._strip(a) for a in per], "pooled": pool,
                         "ledger": ledger, "gpu": {"device": "cpu/xgboost"}})
    np.savez(os.path.join(R._sdir(), "%s.npz" % name), champ=score, win=score)
    SC.hb("%s pooled capture_oracle=%.4f [%.4f,%.4f] $%.2f/session"
          % (name, pool["capture_oracle"] or float("nan"),
             pool["co_lo"] or float("nan"), pool["co_hi"] or float("nan"),
             pool["usd_per_session"] or float("nan")))
    return pool


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--lmart", action="store_true")
    ap.add_argument("--trunk", default="NONE")
    ap.add_argument("--mode", default="ctx")
    ap.add_argument("--group", default="cell",
                    choices=("class", "day", "cell"))
    ap.add_argument("--losses", default="listnet,listmle")
    ap.add_argument("--hardneg", type=float, default=0.0)
    ap.add_argument("--daymem", action="store_true")
    ap.add_argument("--creator", action="store_true")
    ap.add_argument("--eras", default=",".join(SC.TEST_ERAS))
    ap.add_argument("--tag", default=None)
    ap.add_argument("--shuffle", action="store_true")
    ap.add_argument("--tokver", default=None)
    ap.add_argument("--from-era", default="E2")
    a = ap.parse_args()
    eras = tuple(x for x in a.eras.split(",") if x)
    if a.lmart:
        lmart(group=a.group, daymem=a.daymem, test_eras=eras, tag=a.tag,
              use_creator=a.creator, from_era=a.from_era, hardneg=a.hardneg)
    elif a.run:
        run(a.trunk, mode=a.mode, group=a.group,
            losses=tuple(x for x in a.losses.split(",") if x),
            hardneg=a.hardneg, daymem=a.daymem, test_eras=eras, tag=a.tag,
            shuffle=a.shuffle, tokver=a.tokver, from_era=a.from_era)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()

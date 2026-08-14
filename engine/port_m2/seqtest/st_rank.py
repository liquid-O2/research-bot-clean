#!/usr/bin/python3
"""PORT M2 SEQTEST — THE LISTWISE MEMBER-RANKING HEAD.

PROGRAM REDIRECT (coordinator, 2026-08-16, binding): the deficit ledger's
dominant component is **SEL_WRONG_MEMBER** — which same-class episode of the day
gets the seat ($750-1,600/session), against small side and moment components.
A pointwise regression head is the wrong instrument for that: it is fitted to be
right about every row's level, when all that is ever spent is the ORDER inside a
group.  So the head becomes LISTWISE over the exact groups the deficit is
measured on.

    GROUP = (asset, trade day, CLASS)          the same-class member set
    TARGET = the certificate dollars `cert_close_usd`

TWO PRE-REGISTERED LOSSES, chosen on the training block's inner-validation days
by NDCG@3 and nowhere else:

  `listnet`  listwise softmax cross-entropy against a dollar-softmax target,
             `p*_i = softmax(cert_close_usd_i / $1000)` inside the group.
             Uses the MAGNITUDES, which is what SEL_WRONG_MEMBER is denominated
             in.
  `listmle`  the plain likelihood of the dollar-descending permutation
             (Xia et al.), magnitude-blind — carried because the instruction
             named it and because it is the more conservative of the two.

Everything else is the lane's unchanged stack: whole-DAY folds, the walk-forward
era ladder, train-only normalisation, and `m3_walk`'s deployable arm verbatim for
the dollar scoring.  EXITS ARE PARKED (user order): the contract is the existing
one — phase-close plus the $900 wall — and nothing here proposes an exit action.

Run:
    st_rank.py --run --trunk PRE_A_shared --mode fused
    st_rank.py --run --trunk NONE --mode ctx      # context-only ranker
"""
import os

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import argparse                            # noqa: E402
import json                                # noqa: E402
import time                                # noqa: E402

import numpy as np                         # noqa: E402
import torch                               # noqa: E402
import torch.nn.functional as F            # noqa: E402

import st_common as SC                     # noqa: E402
import st_run as R                         # noqa: E402
import st_pretrain as P                    # noqa: E402
import m3_common as M3                     # noqa: E402

DEV = R.DEV

LOSSES = ("listnet", "listmle")
DOLLAR_T = 1000.0                          # the D-021 target, as the softmax
                                           # temperature — not a fitted knob
RANK_EPOCHS = 15
RANK_GROUPS_PER_BATCH = 256
RANK_LR = 1e-3
MAX_GROUP = 64                             # groups longer than this are split
                                           # deterministically by decision second


# ============================================================== the groups ===
def class_index(D):
    """The CLASS of every candidate, recovered from the matrix's own one-hots."""
    cols = [i for i, (n, g) in enumerate(zip(D["names"],
                                             D["feature_groups"].tolist()))
            if str(g) == "class" and str(n).startswith("cls_")]
    names = [str(D["names"][i]) for i in cols]
    sub = D["X"][:, cols]
    k = np.argmax(sub, axis=1)
    k[sub.max(axis=1) <= 0.5] = names.index("cls_UNCLASSED") \
        if "cls_UNCLASSED" in names else 0
    return k.astype(np.int64), names


def build_groups(D, rows, klass):
    """(asset, day, class) member sets, in a deterministic order."""
    r = np.asarray(rows, dtype=np.int64)
    key = (D["asset_idx"][r].astype(np.int64) * 100000000
           + D["d8"][r].astype(np.int64)) * 100 + klass[r]
    order = np.lexsort((D["dec_sec"][r], key))
    ro = r[order]
    ko = key[order]
    starts = [0] + (np.flatnonzero(ko[1:] != ko[:-1]) + 1).tolist()
    stops = starts[1:] + [ko.size]
    out = []
    for a, b in zip(starts, stops):
        if b - a < 2:                      # a single-member group carries no
            continue                       # ranking decision at all
        g = ro[a:b]
        for i in range(0, g.size, MAX_GROUP):
            piece = g[i:i + MAX_GROUP]
            if piece.size >= 2:
                out.append(piece)
    return out


# =============================================================== the losses ==
def listnet_loss(s, y, mask):
    """Listwise softmax cross-entropy against a dollar-softmax target."""
    neg = torch.finfo(s.dtype).min
    s = s.masked_fill(~mask, neg)
    t = (y / DOLLAR_T).masked_fill(~mask, neg)
    logp = F.log_softmax(s, dim=1)
    q = F.softmax(t, dim=1)
    return -(q * logp).sum(1).mean()


def listmle_loss(s, y, mask):
    """The likelihood of the dollar-descending permutation (Xia et al.)."""
    neg = torch.finfo(s.dtype).min
    y = y.masked_fill(~mask, neg)
    idx = torch.argsort(y, dim=1, descending=True)
    ss = torch.gather(s, 1, idx)
    mm = torch.gather(mask, 1, idx)
    ss = ss.masked_fill(~mm, neg)
    # reverse cumulative logsumexp over the suffix of each row
    rev = torch.flip(ss, dims=[1])
    lse = torch.logcumsumexp(rev, dim=1)
    lse = torch.flip(lse, dims=[1])
    ll = (ss - lse).masked_fill(~mm, 0.0)
    return -(ll.sum(1) / mm.sum(1).clamp(min=1)).mean()


def ndcg_at_k(score, value, groups, k=3):
    """NDCG@k inside each group, gain = max(cert dollars, 0)."""
    out = []
    for g in groups:
        v = np.maximum(value[g], 0.0)
        if v.sum() <= 0:
            continue
        s = score[g]
        if not np.isfinite(s).all():
            continue
        o = np.argsort(-s, kind="stable")[:k]
        disc = 1.0 / np.log2(np.arange(o.size) + 2.0)
        dcg = float((v[o] * disc).sum())
        b = np.argsort(-v, kind="stable")[:k]
        idcg = float((v[b] * (1.0 / np.log2(np.arange(b.size) + 2.0))).sum())
        if idcg > 0:
            out.append(dcg / idcg)
    return (float(np.mean(out)) if out else float("nan")), len(out)


# ================================================================= the fit ===
def _pad(groups, idx):
    n = max(len(groups[i]) for i in idx)
    rows = np.zeros((len(idx), n), dtype=np.int64)
    mask = np.zeros((len(idx), n), dtype=bool)
    for j, gi in enumerate(idx):
        g = groups[gi]
        rows[j, :g.size] = g
        mask[j, :g.size] = True
    return rows, mask


def fit_ranker(loss_name, E, C, pos, emu, esd, cmu, csd, groups_tr, groups_va,
               value, mode, tag, max_epochs):
    torch.manual_seed(SC.SEED)
    m = P.ProbeHead(E.shape[1] if E is not None else 1, C.shape[1],
                    mode=mode).to(DEV)
    opt = torch.optim.AdamW(m.parameters(), lr=RANK_LR,
                            weight_decay=SC.WEIGHT_DECAY)
    rng = np.random.RandomState(SC.SEED)
    fn = listnet_loss if loss_name == "listnet" else listmle_loss
    best, best_ep, bad, best_state = -np.inf, 0, 0, None

    def fwd(rows_flat):
        e = torch.zeros(rows_flat.size, 1, device=DEV)
        if mode in ("seq", "fused"):
            e = torch.from_numpy(
                (E[pos[rows_flat]].astype(np.float32) - emu) / esd).to(DEV)
        c = P.ctx_batch(C, rows_flat, cmu, csd)
        return m(e, c)[:, 0]

    for ep in range(1, int(max_epochs) + 1):
        m.train()
        perm = rng.permutation(len(groups_tr))
        t0 = time.time()
        for a in range(0, perm.size, RANK_GROUPS_PER_BATCH):
            sel = perm[a:a + RANK_GROUPS_PER_BATCH]
            if sel.size < 4:
                continue
            rows, mask = _pad(groups_tr, sel)
            flat = rows.reshape(-1)
            s = fwd(flat).view(rows.shape)
            y = torch.from_numpy(value[rows]).to(DEV).float()
            mk = torch.from_numpy(mask).to(DEV)
            loss = fn(s, y, mk)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
        sc = predict_rows(m, E, C, pos, emu, esd, cmu, csd, mode,
                          np.unique(np.concatenate(groups_va))) \
            if groups_va else None
        if sc is not None:
            full = np.full(value.size, np.nan)
            full[sc[0]] = sc[1]
            nd, ng = ndcg_at_k(full, value, groups_va, 3)
        else:
            nd, ng = float(ep), 0
        SC.hb("%s %s ep%d NDCG@3=%.5f (n=%d, %.0fs)"
              % (tag, loss_name, ep, nd, ng, time.time() - t0))
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
    return m, {"loss": loss_name, "inner_ndcg3": best, "best_epoch": best_ep}


def predict_rows(m, E, C, pos, emu, esd, cmu, csd, mode, rows, bs=16384):
    m.eval()
    out = np.zeros(rows.size, dtype=np.float64)
    with torch.no_grad():
        for i in range(0, rows.size, bs):
            r = rows[i:i + bs]
            e = torch.zeros(r.size, 1, device=DEV)
            if mode in ("seq", "fused"):
                e = torch.from_numpy(
                    (E[pos[r]].astype(np.float32) - emu) / esd).to(DEV)
            out[i:i + bs] = m(e, P.ctx_batch(C, r, cmu, csd))[:, 0] \
                .float().cpu().numpy()
    return rows, out


def run(trunk="PRE_A_shared", mode="fused", test_eras=SC.TEST_ERAS, tag=None):
    ft = P.load_ft()
    D, pos, C = ft["D"], ft["pos"], ft["C"]
    E = (np.asarray(P.embed_all(trunk))
         if (mode in ("seq", "fused") and trunk != "NONE") else None)
    if mode in ("seq", "fused") and E is None:
        raise SC.SeqTestRefusal("mode %r needs a trunk; got %r" % (mode, trunk))
    klass, cls_names = class_index(D)
    ceil = R.ceilings_of(D)
    value = D["cert_close_usd"].astype(np.float64)
    n = D["d8"].size
    score = np.full(n, np.nan)
    name = tag or ("RANK_%s_%s" % (trunk, mode.upper()))
    ledger = []
    for era in test_eras:
        t0 = time.time()
        tr, ev = R.fold_rows(D, era)
        tr = tr[pos[tr] >= 0]
        ev = ev[pos[ev] >= 0]
        # the D-077 veto is a veto, never a feature: a vetoed row can never be
        # seated, so it must not be ranked against rows that can
        j = D["names"].index("in_news_window")
        tr = tr[D["X"][tr, j] < 0.5]
        ev_r = ev[D["X"][ev, j] < 0.5]
        cut = SC.inner_split_days(D["d8"][tr])
        itr, iva = tr[D["d8"][tr] <= cut], tr[D["d8"][tr] > cut]
        SC.assert_disjoint_days(itr, iva, D["d8"], tag="%s inner" % era)
        g_itr = build_groups(D, itr, klass)
        g_iva = build_groups(D, iva, klass)
        g_tr = build_groups(D, tr, klass)
        g_ev = build_groups(D, ev_r, klass)
        emu = esd = None
        if E is not None:
            sub = E[pos[itr]].astype(np.float32)
            emu, esd = sub.mean(0), np.maximum(sub.std(0), 1e-3)
        cmu, csd = P.ctx_stats(C, itr)
        cand = []
        for ln in LOSSES:
            _m, info = fit_ranker(ln, E, C, pos, emu, esd, cmu, csd, g_itr,
                                  g_iva, value, mode, "%s/%s" % (name, era),
                                  RANK_EPOCHS)
            cand.append((info["inner_ndcg3"], ln, info))
        cand.sort(key=lambda z: (-z[0], z[1]))
        sel = cand[0][2]
        if E is not None:
            sub = E[pos[tr]].astype(np.float32)
            emu, esd = sub.mean(0), np.maximum(sub.std(0), 1e-3)
        cmu, csd = P.ctx_stats(C, tr)
        m, _i = fit_ranker(sel["loss"], E, C, pos, emu, esd, cmu, csd, g_tr,
                           None, value, mode, "%s/%s refit" % (name, era),
                           sel["best_epoch"])
        rows, s = predict_rows(m, E, C, pos, emu, esd, cmu, csd, mode, ev_r)
        score[rows] = s
        nd, ng = ndcg_at_k(score, value, g_ev, 3)
        # the two references the redirect asks the ranker to be read against
        rnd = np.random.RandomState(SC.SEED).rand(n)
        nd_rand, _ = ndcg_at_k(rnd, value, g_ev, 3)
        nd_earl, _ = ndcg_at_k(-D["dec_sec"].astype(np.float64), value, g_ev, 3)
        ledger.append({"era": era, "loss": sel["loss"],
                       "inner_ndcg3": sel["inner_ndcg3"],
                       "best_epoch": sel["best_epoch"],
                       "loss_curve": [[c[1], round(float(c[0]), 5)]
                                      for c in cand],
                       "n_groups_train": len(g_tr), "n_groups_eval": len(g_ev),
                       "median_group": int(np.median([g.size for g in g_ev]))
                       if g_ev else 0,
                       "eval_ndcg3": nd, "eval_ndcg3_random": nd_rand,
                       "eval_ndcg3_earliest": nd_earl, "n_scored_groups": ng,
                       "n_eval": int(ev_r.size),
                       "fit_secs": round(time.time() - t0, 1)})
        SC.hb("RANK %s %s: loss=%s NDCG@3 %.4f (random %.4f, earliest %.4f) "
              "over %d groups (%.0fs)"
              % (name, era, sel["loss"], nd, nd_rand, nd_earl, ng,
                 time.time() - t0))
        del m
        if DEV == "cuda":
            torch.cuda.empty_cache()
    per, pool = R.eval_scores(D, score, score, ceil, pos, test_eras=test_eras)
    R.save_result(name, {"kind": "rank", "arch": "listwise-%s" % mode,
                         "rung": "40M-frozen" if E is not None else "ctx-only",
                         "L": P.CTX, "trunk": trunk, "mode": mode,
                         "classes": cls_names,
                         "pretrained": (E is not None and trunk != "RANDOM"),
                         "per_era": [R._strip(a) for a in per], "pooled": pool,
                         "ledger": ledger, "gpu": R.gpu_note()})
    np.savez(os.path.join(R._sdir(), "%s.npz" % name), champ=score, win=score)
    SC.hb("%s pooled capture_oracle=%.4f [%.4f,%.4f]"
          % (name, pool["capture_oracle"] or float("nan"),
             pool["co_lo"] or float("nan"), pool["co_hi"] or float("nan")))
    return pool


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--trunk", default="PRE_A_shared")
    ap.add_argument("--mode", default="fused")
    ap.add_argument("--eras", default=",".join(SC.TEST_ERAS))
    ap.add_argument("--tag", default=None)
    a = ap.parse_args()
    if a.run:
        run(a.trunk, mode=a.mode, test_eras=tuple(a.eras.split(",")),
            tag=a.tag)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()

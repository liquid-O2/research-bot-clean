#!/usr/bin/python3
"""PORT M2 SEQTEST — THE 'LEARNED PROPERLY' CERTIFICATE.

Four probes on the chosen checkpoint, all committed as TSVs, all answering
"did it LEARN, or did it merely fit?"

  1. LINEAR PROBES on the frozen embedding.  Can a linear readout recover known
     state — spread regime, book-imbalance sign, last-60s aggression balance,
     volatility regime, phase, near-level flag, capacity (SEAT_LIVE)?  Every
     probe is reported beside a linear baseline on the RAW window inputs: the
     embedding has to beat the raw inputs or it added nothing.
  2. GENERATIVE ROLLOUTS.  The AR head is a simulator, so roll synthetic windows
     and compare STYLIZED FACTS against real tape: event-type frequencies,
     inter-arrival distribution, spread dynamics, volatility clustering,
     cancel/trade ratio.  Distances are total-variation on the token marginals
     and on each factored field.
  3. SURPRISE LOCALIZATION.  Per-event loss by context.  Mechanical churn should
     be cheap and genuinely informative moments (release seconds, break-throughs,
     first tests) expensive.  A FLAT surprise profile is shallow learning.
  4. NEIGHBOUR RETRIEVAL.  Nearest neighbours in embedding space for 20 probe
     moments — do they retrieve semantically similar moments across DIFFERENT
     days and assets?

Plus the R1/R6 diagnostic the reporting rule asks for unconditionally: the
TAIL-BUCKET OCCUPANCY of the tokenization.

Run:  st_probes.py --all --trunk PRE_V_shared_MULTI
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
import st_tok as TK                        # noqa: E402
import st_run as R                         # noqa: E402
import st_pretrain as P                    # noqa: E402
import m2_common as MC                     # noqa: E402

DEV = R.DEV
N_PROBE_ROWS = 60_000
# THE SEVEN CREATOR MECHANICS that survived the destruction null in
# provenance/port_m2/CREATOR_MECHANICS_CENSUS.md S1.1, top-7 by `vs-null` lift.
# They are causal tape detectors, so "can a linear readout of the embedding
# recover them" is exactly the accessibility question.
CREATOR_DETECT = "/workspace/artifacts/cache/port/m2/creator/detect.npz"
CREATOR_SEVEN = ("PASSIVE_MOVE", "TAPE_SPIKE", "ONX_UNTOUCHED_AHEAD", "OFM",
                 "ABSORPTION", "AGG_OPP_SIDE_60", "TWO_STAGE")
_DET = {}


def creator_flags(D):
    """The 7 census-surviving detectors, joined to matrix rows BY CID."""
    if _DET:
        return _DET
    if not os.path.exists(CREATOR_DETECT):
        return {}
    z = np.load(CREATOR_DETECT, allow_pickle=False)
    cids = [str(x) for x in z["cid"].tolist()]
    names = [str(x) for x in z["det_names"].tolist()]
    Dm = z["D"]
    z.close()
    ix = {c: i for i, c in enumerate(cids)}
    row_of = np.full(D["d8"].size, -1, dtype=np.int64)
    for k, c in enumerate(D["cid"].tolist()):
        j = ix.get(str(c))
        if j is not None:
            row_of[k] = j
    if int((row_of >= 0).sum()) == 0:
        return {}
    for nm in CREATOR_SEVEN:
        if nm not in names:
            continue
        col = Dm[:, names.index(nm)].astype(np.float64)
        v = np.full(D["d8"].size, np.nan)
        m = row_of >= 0
        v[m] = col[row_of[m]]
        _DET["mech_" + nm] = v
    SC.hb("creator detectors joined by cid: %d/%d matrix rows matched"
          % (int((row_of >= 0).sum()), row_of.size))
    return _DET


ROLLOUT_N = 1000
ROLLOUT_LEN = 256


# ============================================== 0. tokenizer occupancy =======
def tail_occupancy():
    """THE R1/R6 DIAGNOSTIC, reported regardless of outcome: how much of the
    vocabulary the corpus actually uses, and how much mass sits in the extreme
    buckets that a too-coarse binning would be destroying."""
    cnt = np.load(os.path.join(SC.CACHE_ROOT, "token_counts.npy"))
    tot = float(cnt.sum())
    idx = np.arange(cnt.size)
    gap = idx % 5
    size = (idx // 5) % 5
    dmid = (idx // 25) % 7
    acts = idx // 175
    rows = []

    def mass(m, nm, lab):
        rows.append([nm, lab, int((cnt * m).sum()),
                     round(float((cnt * m).sum() / tot), 6),
                     int((m & (cnt > 0)).sum())])
    for b in range(7):
        mass(dmid == b, "dmid_bucket", str(b))
    for b in range(5):
        mass(size == b, "size_bucket", str(b))
    for b in range(5):
        mass(gap == b, "gap_bucket", str(b))
    for b in range(18):
        mass(acts == b, "act_side", "%s%s" % ("ACMTFR"[b // 3], "BAN"[b % 3]))
    rows.append(["vocab", "used_of_%d" % TK.VOCAB_EVENTS, int((cnt > 0).sum()),
                 round(float((cnt > 0).sum()) / TK.VOCAB_EVENTS, 6), 0])
    p = np.sort(cnt)[::-1].astype(np.float64) / tot
    rows.append(["vocab", "top10_mass", 0, round(float(p[:10].sum()), 6), 10])
    rows.append(["vocab", "top100_mass", 0, round(float(p[:100].sum()), 6),
                 100])
    rows.append(["vocab", "tail_mass_below_1e-4", 0,
                 round(float(p[p < 1e-4].sum()), 6), int((p < 1e-4).sum())])
    return rows


# ================================================ 1. the linear probes =======
def probe_targets(D, rows, ft):
    """Known-true state at the decision second, read off the committed matrix
    and the raw window — never off an outcome."""
    X = D["X"]
    nm = D["names"]
    out = {}

    def col(c):
        return X[rows, nm.index(c)] if c in nm else None
    SEQ = ft["W"]
    pos = ft["wpos"]
    w = SEQ[pos[rows]]
    last = w[:, :, -1].astype(np.float32)
    spread = last[:, 18]
    out["spread_wide"] = (spread > np.median(spread)).astype(np.float64)
    bid = np.expm1(last[:, 14])
    ask = np.expm1(last[:, 15])
    out["imbalance_sign"] = ((bid - ask) > 0).astype(np.float64)
    tr = w[:, 3, :].astype(np.float32)
    sd = w[:, 6, :].astype(np.float32) - w[:, 7, :].astype(np.float32)
    aggr = (tr * sd).sum(1)
    out["aggression_up"] = (aggr > 0).astype(np.float64)
    v = np.abs(w[:, 10, :].astype(np.float32)).sum(1)
    out["vol_regime_high"] = (v > np.median(v)).astype(np.float64)
    ph = D["phase_dec"][rows]
    out["phase_is_2"] = (ph == 2).astype(np.float64)
    nl = col("min_level_dist_atr")
    if nl is None:
        for c in nm:
            if "level" in c and "dist" in c:
                nl = X[rows, nm.index(c)]
                break
    if nl is not None:
        fin = np.isfinite(nl)
        thr = np.nanmedian(nl[fin]) if fin.any() else 0.0
        out["near_level"] = (np.where(fin, nl, thr) <= thr).astype(np.float64)
    cap = None
    for c in ("seat_live", "seats_used_today", "runway_sec"):
        if c in nm:
            cap = X[rows, nm.index(c)]
            break
    if cap is not None:
        fin = np.isfinite(cap)
        out["capacity_state"] = (np.where(fin, cap, 0.0)
                                 > np.nanmedian(cap[fin])).astype(np.float64) \
            if fin.any() else None
    for k, v in creator_flags(D).items():
        sub = v[rows]
        if np.isfinite(sub).mean() > 0.9 and 0.001 < np.nanmean(sub) < 0.999:
            out[k] = np.nan_to_num(sub)
    return {k: v for k, v in out.items() if v is not None}


def _auc(y, s):
    return R.auc(y, s)


def linear_probe(Ztr, ytr, Zte, yte, l2=1.0, iters=300):
    """A plain logistic readout — deliberately linear, so a high score means the
    information is ACCESSIBLE and not merely present."""
    d = Ztr.shape[1]
    w = torch.zeros(d, device=DEV, requires_grad=True)
    b = torch.zeros(1, device=DEV, requires_grad=True)
    Xt = torch.from_numpy(Ztr).to(DEV)
    yt = torch.from_numpy(ytr).to(DEV).float()
    opt = torch.optim.LBFGS([w, b], max_iter=iters, history_size=10)

    def closure():
        opt.zero_grad()
        z = Xt @ w + b
        loss = F.binary_cross_entropy_with_logits(z, yt) + l2 * (w * w).sum() / d
        loss.backward()
        return loss
    opt.step(closure)
    with torch.no_grad():
        s = (torch.from_numpy(Zte).to(DEV) @ w + b).cpu().numpy()
    return _auc(yte, s)


def run_linear_probes(trunk, ft, E, rows_tr, rows_te):
    D = ft["D"]
    tg_tr = probe_targets(D, rows_tr, ft)
    tg_te = probe_targets(D, rows_te, ft)
    Ztr = E[ft["pos"][rows_tr]].astype(np.float32)
    Zte = E[ft["pos"][rows_te]].astype(np.float32)
    mu, sd = Ztr.mean(0), np.maximum(Ztr.std(0), 1e-3)
    Ztr, Zte = (Ztr - mu) / sd, (Zte - mu) / sd
    # the RAW-INPUT baseline: the same window, pooled the crudest possible way
    Wtr = ft["W"][ft["wpos"][rows_tr]].astype(np.float32)
    Wte = ft["W"][ft["wpos"][rows_te]].astype(np.float32)
    Rtr = np.concatenate([Wtr.mean(2), Wtr[:, :, -1]], 1)
    Rte = np.concatenate([Wte.mean(2), Wte[:, :, -1]], 1)
    m2, s2 = Rtr.mean(0), np.maximum(Rtr.std(0), 1e-3)
    Rtr, Rte = (Rtr - m2) / s2, (Rte - m2) / s2
    rows = []
    # a target the base-rate guard dropped on ONE side is dropped on BOTH: the
    # two dicts are joined by KEY, never by position
    for k in sorted(set(tg_tr) & set(tg_te)):
        y1, y2 = tg_tr[k], tg_te[k]
        if len(np.unique(y2)) < 2:
            continue
        a_emb = linear_probe(Ztr, y1, Zte, y2)
        a_raw = linear_probe(Rtr, y1, Rte, y2)
        rows.append([trunk, k, int(y2.size), round(float(a_emb), 4),
                     round(float(a_raw), 4), round(float(a_emb - a_raw), 4),
                     "EMBEDDING_ADDS" if a_emb > a_raw + 0.01
                     else ("PARITY" if abs(a_emb - a_raw) <= 0.01
                           else "RAW_BETTER")])
        SC.hb("probe %-18s emb AUC %.4f vs raw %.4f" % (k, a_emb, a_raw))
    return rows


# ============================================ 2. generative rollouts =========
@torch.no_grad()
def rollouts(model, T, S, A, n=ROLLOUT_N, length=ROLLOUT_LEN, temp=1.0):
    rs = np.random.RandomState(SC.SEED)
    idx = rs.choice(S.size, size=min(n, S.size), replace=False)
    prompt = 128
    x = np.stack([T[S[i]:S[i] + prompt].astype(np.int64) for i in idx])
    real = np.stack([T[S[i] + prompt:S[i] + prompt + length].astype(np.int64)
                     for i in idx])
    cur = torch.from_numpy(x).to(DEV)
    a = torch.from_numpy(A[idx].astype(np.int64)).to(DEV)
    gen = []
    model.eval()
    for _ in range(length):
        with torch.autocast("cuda", dtype=torch.bfloat16,
                            enabled=(DEV == "cuda")):
            lg = model(cur[:, -min(cur.shape[1], P.CTX - 1):], a)[:, -1, :]
        p = torch.softmax(lg.float() / temp, -1)
        nxt = torch.multinomial(p, 1)
        gen.append(nxt)
        cur = torch.cat([cur, nxt], 1)
    g = torch.cat(gen, 1).cpu().numpy()
    return g, real


def _fields(tok):
    tok = np.clip(tok, 0, TK.VOCAB_EVENTS - 1)
    return {"gap": tok % 5, "size": (tok // 5) % 5, "dmid": (tok // 25) % 7,
            "act": (tok // 175) // 3, "side": (tok // 175) % 3}


def stylized(gen, real):
    rows = []
    fg, fr = _fields(gen), _fields(real)
    for k in ("act", "side", "dmid", "size", "gap"):
        n = int(max(fg[k].max(), fr[k].max())) + 1
        pg = np.bincount(fg[k].ravel(), minlength=n).astype(np.float64)
        pr = np.bincount(fr[k].ravel(), minlength=n).astype(np.float64)
        pg /= pg.sum()
        pr /= pr.sum()
        rows.append([k, "total_variation", round(float(0.5 * np.abs(pg - pr)
                                                      .sum()), 5),
                     json.dumps([round(x, 4) for x in pr.tolist()]),
                     json.dumps([round(x, 4) for x in pg.tolist()])])
    # cancel/trade ratio and volatility clustering
    for nm, arr in (("real", fr), ("gen", fg)):
        ct = float((arr["act"] == 1).sum()) / max(float((arr["act"] == 3).sum()),
                                                  1.0)
        rows.append(["cancel_trade_ratio", nm, round(ct, 4), "", ""])
    for nm, arr in (("real", fr), ("gen", fg)):
        mv = (arr["dmid"] - 3).astype(np.float64)
        a1 = np.abs(mv[:, :-1])
        a2 = np.abs(mv[:, 1:])
        c = np.corrcoef(a1.ravel(), a2.ravel())[0, 1]
        rows.append(["vol_clustering_lag1_absmove", nm, round(float(c), 5),
                     "", ""])
    return rows


# ========================================== 3. surprise localization =========
@torch.no_grad()
def surprise(model, ft, E_rows, bs=64):
    """Per-event loss by context.  The contexts are read off the committed
    matrix: news proximity, class, and whether the window broke a level."""
    D, X, pos, asset = ft["D"], ft["X"], ft["pos"], ft["asset"]
    model.eval()
    out = {}
    nm = D["names"]
    j_news = nm.index("in_news_window") if "in_news_window" in nm else None
    kl = None
    for c in nm:
        if c.startswith("cls_"):
            kl = c
            break
    losses = np.zeros(E_rows.size)
    for a in range(0, E_rows.size, bs):
        r = E_rows[a:a + bs]
        x = torch.from_numpy(X[pos[r]].astype(np.int64)).to(DEV)
        av = torch.from_numpy(asset[r]).to(DEV)
        with torch.autocast("cuda", dtype=torch.bfloat16,
                            enabled=(DEV == "cuda")):
            lg = model(x[:, :-1], av)
        ce = F.cross_entropy(lg.float().reshape(-1, TK.VOCAB),
                             x[:, 1:].reshape(-1), reduction="none")
        losses[a:a + bs] = ce.view(x.shape[0], -1).mean(1).cpu().numpy()
    rows = []
    ctx = {}
    if j_news is not None:
        ctx["in_news_window"] = D["X"][E_rows, j_news] > 0.5
    ctx["phase_2"] = D["phase_dec"][E_rows] == 2
    for c in nm:
        if c.startswith("cls_"):
            m = D["X"][E_rows, nm.index(c)] > 0.5
            if m.sum() > 200:
                ctx[c] = m
    for k, m in ctx.items():
        if m.sum() < 50 or (~m).sum() < 50:
            continue
        rows.append([k, int(m.sum()), round(float(losses[m].mean()), 5),
                     round(float(losses[~m].mean()), 5),
                     round(float(losses[m].mean() - losses[~m].mean()), 5)])
    q = np.percentile(losses, [1, 5, 25, 50, 75, 95, 99])
    rows.append(["_distribution_p1_p5_p25_p50_p75_p95_p99", int(losses.size),
                 round(float(losses.mean()), 5), round(float(losses.std()), 5),
                 json.dumps([round(float(x), 4) for x in q])])
    return rows, losses


# ============================================= 4. neighbour retrieval ========
def neighbours(ft, E, probe_rows, pool_rows, k=5):
    D = ft["D"]
    Zp = E[ft["pos"][probe_rows]].astype(np.float32)
    Zq = E[ft["pos"][pool_rows]].astype(np.float32)
    Zp /= np.maximum(np.linalg.norm(Zp, axis=1, keepdims=True), 1e-6)
    Zq /= np.maximum(np.linalg.norm(Zq, axis=1, keepdims=True), 1e-6)
    sim = Zp @ Zq.T
    rows = []
    for i, r in enumerate(probe_rows.tolist()):
        o = np.argsort(-sim[i])[:k + 1]
        nb = [pool_rows[j] for j in o.tolist() if pool_rows[j] != r][:k]
        n_diff_day = sum(1 for j in nb if D["d8"][j] != D["d8"][r])
        n_diff_asset = sum(1 for j in nb
                           if D["asset_idx"][j] != D["asset_idx"][r])
        rows.append([str(D["cid"][r]), round(float(D["cert_close_usd"][r]), 1),
                     " | ".join("%s@%.2f" % (D["cid"][j], sim[i, list(
                         pool_rows).index(j)] if False else 0.0)
                         for j in nb[:3]),
                     n_diff_day, n_diff_asset,
                     round(float(np.mean([D["cert_close_usd"][j]
                                          for j in nb])), 1)])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--trunk", default="PRE_V_shared_MULTI")
    a = ap.parse_args()
    t0 = time.time()
    R.write_tsv("SEQTEST_TOKEN_OCCUPANCY.tsv",
                ["field", "bucket", "n_events", "mass_fraction",
                 "n_vocab_cells"], tail_occupancy(),
                extra=["THE R1/R6 DIAGNOSTIC, reported unconditionally: how "
                       "much of the 3150-token event vocabulary the corpus "
                       "actually occupies and how much mass sits in the "
                       "extreme buckets a too-coarse binning would destroy."])
    if not a.all:
        return
    ft = P.load_ft()
    import st_build as SB
    W = None
    pos_w = np.full(ft["D"]["d8"].size, -1, dtype=np.int64)
    parts, at = [], 0
    for asset in MC.ASSET_ORDER:
        for era in SC.UNIVERSE_ERAS:
            base = SC.shard_path(asset, era, 256)
            if not os.path.exists(base + ".npy"):
                continue
            T, ri, _ne = SB.load_shard(asset, era, 256)
            parts.append((T, ri, at))
            pos_w[ri] = np.arange(at, at + ri.size, dtype=np.int64)
            at += int(ri.size)
    W = np.empty((at, SC.N_CH, 256), dtype=np.float16)
    for T, ri, off in parts:
        W[off:off + ri.size] = T[:ri.size]
        del T
    ft["W"], ft["wpos"] = W, pos_w
    E = np.asarray(P.embed_all(a.trunk))
    D = ft["D"]
    rs = np.random.RandomState(SC.SEED)
    tr_rows = np.nonzero((D["era_idx"] >= SC.ERA_IDX["E2"])
                         & (D["era_idx"] <= SC.ERA_IDX["E5"])
                         & (ft["pos"] >= 0) & (pos_w >= 0))[0]
    # the creator detectors are cached over E2..E6 only, so the probe TEST
    # block is E6 — the first evaluation era, inside their coverage — and every
    # target is then defined on the same rows
    te_rows = np.nonzero((D["era_idx"] == SC.ERA_IDX["E6"])
                         & (ft["pos"] >= 0) & (pos_w >= 0))[0]
    tr_rows = rs.choice(tr_rows, size=min(N_PROBE_ROWS, tr_rows.size),
                        replace=False)
    te_rows = rs.choice(te_rows, size=min(N_PROBE_ROWS // 2, te_rows.size),
                        replace=False)
    R.write_tsv("SEQTEST_LINEAR_PROBES.tsv",
                ["trunk", "target", "n_test", "auc_embedding", "auc_raw_input",
                 "delta", "verdict"],
                run_linear_probes(a.trunk, ft, E, np.sort(tr_rows),
                                  np.sort(te_rows)),
                extra=["LINEAR readouts on the FROZEN embedding vs a linear "
                       "readout on the raw window (channel means + last event).",
                       "The embedding must BEAT the raw inputs or it added "
                       "nothing accessible."])
    ck = torch.load(os.path.join(P.TRUNK_DIR, "%s.pt" % a.trunk),
                    map_location="cpu")
    lm = P.EventLM(n_assets=ck["n_assets"], side=bool(ck.get("side")),
                   multi=bool(ck.get("multi")))
    lm.load_state_dict(ck["state"])
    lm = lm.to(DEV).eval()
    T, S, A2, max_d8, assets, IN, TG = P._corpus("A", "shared", False)
    g, real = rollouts(lm, T, S, A2)
    R.write_tsv("SEQTEST_ROLLOUTS.tsv",
                ["field", "statistic", "value", "real", "generated"],
                stylized(g, real),
                extra=["GENERATIVE ROLLOUTS: %d synthetic windows of %d events "
                       "sampled from the AR head against real continuations of "
                       "the same prompts." % (ROLLOUT_N, ROLLOUT_LEN),
                       "`total_variation` is on the marginal of each factored "
                       "field of the composite token."])
    srows, _ls = surprise(lm, ft, np.sort(te_rows)[:8000])
    R.write_tsv("SEQTEST_SURPRISE.tsv",
                ["context", "n", "loss_in_context", "loss_out", "delta"],
                srows,
                extra=["SURPRISE LOCALIZATION: mean next-event loss of the "
                       "candidate windows inside vs outside each context.",
                       "A FLAT profile is shallow learning (matrix signature "
                       "R6)."])
    probe_rows = np.sort(rs.choice(te_rows, size=20, replace=False))
    pool = np.sort(rs.choice(te_rows, size=min(20000, te_rows.size),
                             replace=False))
    R.write_tsv("SEQTEST_NEIGHBOURS.tsv",
                ["probe_cid", "probe_usd", "top3_neighbour_cids",
                 "n_of_5_different_day", "n_of_5_different_asset",
                 "mean_neighbour_usd"],
                neighbours(ft, E, probe_rows, pool),
                extra=["NEAREST NEIGHBOURS in the frozen embedding space for 20 "
                       "probe moments drawn from the evaluation eras."])
    SC.hb("probe suite done (%.0fs)" % (time.time() - t0))


if __name__ == "__main__":
    main()

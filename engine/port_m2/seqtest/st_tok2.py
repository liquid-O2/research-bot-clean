#!/usr/bin/python3
"""PORT M2 FIXPASS2 — F1: THE REPAIRED EVENT TOKENIZER (matrix tags R1/R6).

WHAT WAS BROKEN.  `SEQTEST_TOKEN_OCCUPANCY.tsv` measured **93.31%** of all
1.43B events in ONE `dmid_bucket` and 85.89% in one `size_bucket`: at the single
event grain the composite token was in practice `act_side x gap`, and the model
was very nearly BLIND TO PRICE.  The mechanism is now named exactly: **the L1
mid moves in HALF ticks** (only one side of the book has to move) and the V1
bucketing was cut in WHOLE ticks, so the single most common real price event —
a half-tick mid move, 8.7% / 15.3% / 16.8% of SI / HG / NKD events — was
being folded into the "the mid did not move" cell together with everything else.

THE REPAIR, stated as a commitment before the trunk is retrained:

  1. the price axis is cut in HALF TICKS, so a half-tick move is its own signed
     bucket, and the signed tails (>= 3 half ticks either way) keep their own
     cells;
  2. the residual TRUE-ZERO mass is split by the record's own signed price
     against the mid — the "where in the book did this message land" axis the
     V1 vocabulary threw away entirely — on PER-ASSET cuts;
  3. those per-asset cuts are FITTED, on the PRE-A corpus only (`d8 <
     20240101`), by the declared rule "minimise the maximum resulting bucket
     occupancy over the declared half-tick grid".  Fitting on PRE-A keeps the
     causal boundary: E6/E7/E8 fine-tuned numbers stay honest walk-forward, and
     E3/E4/E5 carry the same contamination flag they already carried;
  4. the size axis gives up its least informative boundary (2-3 vs 4-9) so the
     vocabulary stays ~3-4k while the price axis grows from 7 cells to 11.

    tok = ((act_side * 11 + px_bucket) * 4 + size_bucket) * 5 + gap_bucket

    act_side    18   action byte {A,C,M,T,F,R} x side byte {B,A,N}   (V1)
    px_bucket   11   h = round(2*dmid/tick), the mid move in HALF ticks:
                       h<=-3 | h=-2 | h=-1 | [ h=0, split 5 ways by
                       q=(price-mid)/tick on the per-asset cuts ] | h=+1 |
                       h=+2 | h>=+3
    size_bucket  4   1 | 2-9 | 10-49 | >=50                          (V1 -1)
    gap_bucket   5   <50us | <500us | <5ms | <50ms | >=50ms          (V1)

    VOCAB = 18*11*4*5 = 3960 event tokens, + BOS(3960) + PAD(3961) = 3962

The unigram / bigram floors are RECOMPUTED for this vocabulary — a perplexity
against the V1 floors would not be a comparison.

Run:
    st_tok2.py --fit            # the per-asset cuts + the occupancy table
    st_tok2.py --build --workers 16
"""
import argparse
import json
import multiprocessing as mp
import os
import time

import numpy as np

import st_common as SC
import m2_common as MC
import m3_common as M3

N_ACT_SIDE = 18
N_PX = 11
N_SZ = 4
N_GAP = 5
VOCAB_EVENTS = N_ACT_SIDE * N_PX * N_SZ * N_GAP        # 3960
BOS = VOCAB_EVENTS
PAD = VOCAB_EVENTS + 1
VOCAB = VOCAB_EVENTS + 2                               # 3962

CAND_LEN = 1024
CTX = 1024

TOK_DIR = os.path.join(SC.CACHE_ROOT, "tokens_v2")
CAND_DIR = os.path.join(SC.CACHE_ROOT, "cand_tok_v2")
CUTS_PATH = os.path.join(SC.CACHE_ROOT, "tok_v2_cuts.json")
COUNTS_PATH = os.path.join(SC.CACHE_ROOT, "token_counts_v2.npy")

_ACT = {a: i for i, a in enumerate(SC.ACTION_BYTES)}
_SIDE = {s: i for i, s in enumerate(SC.SIDE_BYTES)}

SIZE_EDGES = (1, 9, 49)                    # -> 1 | 2-9 | 10-49 | >=50
GAP_EDGES_NS = (50_000, 500_000, 5_000_000, 50_000_000)

QLO = 0.25                                 # "at the mid / unpriced" band
QHI_GRID = (0.75, 1.25, 1.75, 2.25)        # the declared per-asset cut grid
FIT_MAX_D8 = 20240101                      # the PRE-A causal boundary
FIT_STRIDE = 7                             # every 7th cached pre-2024 session


# ------------------------------------------------------------ the fields ----
def _fields(asset, arr):
    """h (mid move in half ticks), q (price vs mid in ticks), size, gap."""
    n = int(arr["ts_ns"].size)
    tick = SC.tick_raw(asset)
    act = np.full(n, 5, dtype=np.int16)
    for b, i in _ACT.items():
        act[arr["action"] == b] = i
    sid = np.full(n, 2, dtype=np.int16)
    for b, i in _SIDE.items():
        sid[arr["side"] == b] = i
    act_side = act.astype(np.int32) * 3 + sid.astype(np.int32)

    bid = arr["bid_px"].astype(np.float64)
    ask = arr["ask_px"].astype(np.float64)
    mid = 0.5 * (bid + ask)
    good = np.isfinite(mid) & (bid > 0) & (ask > 0)
    mid = np.where(good, mid, np.nan)
    d = np.zeros(n, dtype=np.float64)
    if n > 1:
        d[1:] = (mid[1:] - mid[:-1]) / tick
    h = np.where(np.isfinite(d), np.round(d * 2.0), 0.0)
    q = (arr["price"].astype(np.float64) - mid) / tick
    q = np.where(np.isfinite(q), q, 0.0)

    sz = arr["size"].astype(np.int64)
    szb = np.searchsorted(np.asarray(SIZE_EDGES), sz, side="left")
    gap = np.zeros(n, dtype=np.int64)
    if n > 1:
        gap[1:] = np.clip(np.diff(arr["ts_ns"]), 0, None)
    gpb = np.searchsorted(np.asarray(GAP_EDGES_NS), gap, side="left")
    return act_side, h, q, szb.astype(np.int32), gpb.astype(np.int32), good


def px_bucket(h, q, qhi, qlo=QLO):
    """The 11-level price axis.  Signed half-tick moves keep their own cells;
    the true-zero mass is split five ways by the record's signed price against
    the mid at the per-asset cut."""
    b = np.full(h.size, 5, dtype=np.int32)          # h==0, |q| < qlo
    z = h == 0
    b[z & (q <= -qhi)] = 3
    b[z & (q > -qhi) & (q <= -qlo)] = 4
    b[z & (np.abs(q) < qlo)] = 5
    b[z & (q >= qlo) & (q < qhi)] = 6
    b[z & (q >= qhi)] = 7
    b[h == -1] = 2
    b[h == -2] = 1
    b[h <= -3] = 0
    b[h == 1] = 8
    b[h == 2] = 9
    b[h >= 3] = 10
    return b


def tokenize_day(asset, arr, qhi):
    act_side, h, q, szb, gpb, _good = _fields(asset, arr)
    pxb = px_bucket(h, q, qhi)
    tok = ((act_side * N_PX + pxb) * N_SZ + szb) * N_GAP + gpb
    return tok.astype(np.int16)


# ---------------------------------------------------------------- the fit ---
def _fit_one(job):
    asset, files = job
    H, Q = [], []
    for f in files:
        p = os.path.join(SC.EVENTS_DIR, asset, f)
        z = np.load(p)
        arr = {k: z[k] for k in z.files}
        z.close()
        if arr["ts_ns"].size == 0:
            continue
        _a, h, q, _s, _g, _ok = _fields(asset, arr)
        H.append(h.astype(np.float32))
        Q.append(q.astype(np.float32))
    return asset, (np.concatenate(H) if H else np.zeros(0, np.float32),
                   np.concatenate(Q) if Q else np.zeros(0, np.float32))


def fit_cuts(workers=8):
    """The per-asset cut, fitted on PRE-A (`d8 < 20240101`) only, by the
    declared rule: minimise the maximum bucket occupancy over QHI_GRID."""
    jobs = []
    for asset in MC.ASSET_ORDER:
        d = os.path.join(SC.EVENTS_DIR, asset)
        fs = sorted(f for f in os.listdir(d)
                    if f.endswith(".npz") and int(f[:-4]) < FIT_MAX_D8)
        jobs.append((asset, fs[::FIT_STRIDE]))
    out = {"rule": ("per-asset qhi chosen from %s to MINIMISE the maximum "
                    "px_bucket occupancy; fitted on d8 < %d only (the PRE-A "
                    "causal boundary); qlo fixed at %.2f"
                    % (list(QHI_GRID), FIT_MAX_D8, QLO)),
           "qlo": QLO, "fit_max_d8": FIT_MAX_D8, "fit_stride": FIT_STRIDE,
           "assets": {}}
    with mp.Pool(min(len(jobs), int(workers))) as pool:
        res = dict(pool.map(_fit_one, jobs))
    for asset in MC.ASSET_ORDER:
        h, q = res[asset]
        n = float(h.size)
        best = None
        table = {}
        for qhi in QHI_GRID:
            b = px_bucket(h.astype(np.float64), q.astype(np.float64), qhi)
            occ = np.bincount(b, minlength=N_PX).astype(np.float64) / max(n, 1)
            table["%.2f" % qhi] = [round(float(x), 6) for x in occ.tolist()]
            mx = float(occ.max())
            if best is None or mx < best[1] - 1e-9:
                best = (float(qhi), mx)
        out["assets"][asset] = {"qhi": best[0], "max_occupancy": round(best[1], 6),
                                "n_events_sampled": int(n),
                                "n_sessions_sampled": len(jobs[MC.ASSET_ORDER.index(asset)][1]),
                                "grid_occupancy": table}
        SC.hb("tok-v2 fit %s: qhi=%.2f max_occ=%.4f (%d events)"
              % (asset, best[0], best[1], int(n)))
    with open(CUTS_PATH, "w") as fh:
        json.dump(out, fh, indent=1)
    return out


def load_cuts():
    if not os.path.exists(CUTS_PATH):
        raise SC.SeqTestRefusal("tok-v2 cuts not fitted: run --fit first")
    with open(CUTS_PATH) as fh:
        c = json.load(fh)
    return {a: float(v["qhi"]) for a, v in c["assets"].items()}


# --------------------------------------------------------------- the build --
def _one_day(job):
    asset, d8, rows, decs, qhi = job
    p = os.path.join(SC.EVENTS_DIR, asset, "%08d.npz" % int(d8))
    j = os.path.join(SC.EVENTS_DIR, asset, "%08d.json" % int(d8))
    if not (os.path.exists(p) and os.path.exists(j)):
        return asset, int(d8), None
    with open(j) as fh:
        meta = json.load(fh)
    z = np.load(p)
    arr = {k: z[k] for k in z.files}
    z.close()
    ts = arr["ts_ns"]
    if ts.size == 0:
        return asset, int(d8), None
    tok = tokenize_day(asset, arr, qhi)
    o = int(meta["open_utc"])
    cover = [(int(a), int(b)) for a, b in meta["cover"]]
    blocks = []
    for a, b in cover:
        i = int(np.searchsorted(ts, (o + a) * 1_000_000_000, side="left"))
        k = int(np.searchsorted(ts, (o + b + 1) * 1_000_000_000, side="left"))
        if k - i >= CTX:
            blocks.append((i, k))
    os.makedirs(os.path.join(TOK_DIR, asset), exist_ok=True)
    np.savez(os.path.join(TOK_DIR, asset, "%08d.npz" % int(d8)),
             tok=tok, blocks=np.asarray(blocks, dtype=np.int64).reshape(-1, 2))
    cw = None
    if rows:
        dec = np.asarray(decs, dtype=np.int64)
        cut_ns = (o + dec) * 1_000_000_000
        hi = np.searchsorted(ts, cut_ns, side="left")
        cw = np.full((dec.size, CAND_LEN), PAD, dtype=np.int16)
        for k in range(dec.size):
            cs = SC.cover_start_sec(cover, int(dec[k]))
            lo0 = int(np.searchsorted(ts, (o + cs) * 1_000_000_000,
                                      side="left"))
            b = int(hi[k])
            a = max(lo0, b - CAND_LEN)
            m = b - a
            if m > 0:
                cw[k, CAND_LEN - m:] = tok[a:b]
    return asset, int(d8), (int(tok.size), len(blocks),
                            np.asarray(rows, dtype=np.int64), cw,
                            np.bincount(np.clip(tok.astype(np.int64), 0,
                                                VOCAB_EVENTS - 1),
                                        minlength=VOCAB_EVENTS))


def build(workers=16):
    t0 = time.time()
    cuts = load_cuts()
    os.makedirs(TOK_DIR, exist_ok=True)
    os.makedirs(CAND_DIR, exist_ok=True)
    z = np.load(os.path.join(M3.MATRIX_DIR, "matrix.npz"), allow_pickle=False)
    d8, ai, era, dec = z["d8"], z["asset_idx"], z["era_idx"], z["dec_sec"]
    z.close()
    M3.check_holdout(d8)
    counts = np.zeros(VOCAB_EVENTS, dtype=np.int64)
    stats = {"n_events": 0, "n_blocks": 0, "n_days": 0, "n_cand": 0,
             "shards": [], "cuts": cuts}
    for a_i, asset in enumerate(MC.ASSET_ORDER):
        cached = sorted(int(f[:-4]) for f in
                        os.listdir(os.path.join(SC.EVENTS_DIR, asset))
                        if f.endswith(".npz"))
        bad = [x for x in cached if x >= MC.HOLDOUT_FROM_D8]
        if bad:
            raise SC.SeqTestRefusal(
                "HOLDOUT LEAK: %d cached sessions at or past %d (%s)"
                % (len(bad), MC.HOLDOUT_FROM_D8, bad[:3]))
        per_era = {}
        for e in SC.UNIVERSE_ERAS:
            sel = np.nonzero((ai == a_i) & (era == SC.ERA_IDX[e]))[0]
            for dd in np.unique(d8[sel]).tolist():
                r = sel[d8[sel] == dd]
                r = r[np.argsort(dec[r], kind="stable")]
                per_era.setdefault(int(dd), (e, r))
        jobs = []
        for dd in cached:
            e, r = per_era.get(dd, (None, np.zeros(0, dtype=np.int64)))
            jobs.append((asset, dd, r.tolist(), dec[r].tolist(), cuts[asset]))
        buf = {}
        with mp.Pool(processes=int(workers)) as pool:
            for _a, dd, res in pool.imap(_one_day, jobs, chunksize=1):
                if res is None:
                    continue
                ntok, nblk, rows, cw, cnt = res
                stats["n_events"] += ntok
                stats["n_blocks"] += nblk
                stats["n_days"] += 1
                counts += cnt
                if cw is not None and rows.size:
                    e = per_era[int(dd)][0]
                    buf.setdefault(e, []).append((rows, cw))
        for e, parts in buf.items():
            rows = np.concatenate([p[0] for p in parts])
            cw = np.concatenate([p[1] for p in parts])
            np.save(os.path.join(CAND_DIR, "TOK_%s_%s.npy" % (asset, e)), cw)
            np.savez(os.path.join(CAND_DIR, "TOK_%s_%s.meta.npz" % (asset, e)),
                     row_idx=rows)
            stats["n_cand"] += int(rows.size)
            stats["shards"].append([asset, e, int(rows.size)])
        SC.hb("tokenised(v2) %s (%.0fs)" % (asset, time.time() - t0))
    p = counts.astype(np.float64) / max(counts.sum(), 1)
    nz = p[p > 0]
    stats["unigram_entropy_nats"] = float(-(nz * np.log(nz)).sum())
    stats["n_tokens_used"] = int((counts > 0).sum())
    stats["vocab"] = VOCAB
    stats["elapsed_sec"] = round(time.time() - t0, 1)
    np.save(COUNTS_PATH, counts)
    rec = M3.env_receipt(dict(SC.PARAMS, tokenizer="st_tok2 (F1 repair, R1/R6)"))
    rec.update(stats)
    with open(os.path.join(SC.CACHE_ROOT, "tokens_v2.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True, default=str)
    SC.hb("tokenizer v2 done: %d events, %d blocks, %d candidate windows, "
          "unigram entropy %.4f nats, %d/%d cells used (%.0fs)"
          % (stats["n_events"], stats["n_blocks"], stats["n_cand"],
             stats["unigram_entropy_nats"], stats["n_tokens_used"],
             VOCAB_EVENTS, stats["elapsed_sec"]))
    return stats


# ------------------------------------------------------------- consumers ----
def load_pretrain_corpus(max_d8, assets=MC.ASSET_ORDER):
    t0 = time.time()
    toks, starts, aidx = [], [], []
    at = 0
    for a_i, asset in enumerate(assets):
        d = os.path.join(TOK_DIR, asset)
        for f in sorted(os.listdir(d)):
            if not f.endswith(".npz") or int(f[:-4]) >= int(max_d8):
                continue
            z = np.load(os.path.join(d, f))
            t, b = z["tok"], z["blocks"]
            z.close()
            toks.append(t)
            for lo, hi in b.tolist():
                nfull = (hi - lo) // CTX
                if nfull <= 0:
                    continue
                s = at + lo + np.arange(nfull, dtype=np.int64) * CTX
                starts.append(s)
                aidx.append(np.full(nfull, a_i, dtype=np.int8))
            at += int(t.size)
    T = np.concatenate(toks)
    S = np.concatenate(starts) if starts else np.zeros(0, dtype=np.int64)
    A = np.concatenate(aidx) if aidx else np.zeros(0, dtype=np.int8)
    SC.hb("pretrain corpus v2 <%d: %d events, %d chunks of %d (%.1f GB, %.0fs)"
          % (max_d8, T.size, S.size, CTX, T.nbytes / 1e9, time.time() - t0))
    return T, S, A


def load_cand_tokens():
    parts, rows = [], []
    for asset in MC.ASSET_ORDER:
        for e in SC.UNIVERSE_ERAS:
            p = os.path.join(CAND_DIR, "TOK_%s_%s.npy" % (asset, e))
            if not os.path.exists(p):
                continue
            parts.append(np.load(p))
            rows.append(np.load(os.path.join(
                CAND_DIR, "TOK_%s_%s.meta.npz" % (asset, e)))["row_idx"])
    return np.concatenate(parts), np.concatenate(rows)


def occupancy_rows():
    """The R1/R6 diagnostic on the REPAIRED vocabulary, same shape as
    `SEQTEST_TOKEN_OCCUPANCY.tsv` so the two are readable side by side."""
    cnt = np.load(COUNTS_PATH)
    tot = float(cnt.sum())
    idx = np.arange(cnt.size)
    gap = idx % N_GAP
    size = (idx // N_GAP) % N_SZ
    px = (idx // (N_GAP * N_SZ)) % N_PX
    acts = idx // (N_GAP * N_SZ * N_PX)
    rows = []

    def mass(m, nm, lab):
        rows.append([nm, lab, int((cnt * m).sum()),
                     round(float((cnt * m).sum() / tot), 6),
                     int((m & (cnt > 0)).sum())])
    lab_px = ["h<=-3", "h=-2", "h=-1", "h=0,q<=-qhi", "h=0,-qhi<q<=-qlo",
              "h=0,|q|<qlo", "h=0,qlo<=q<qhi", "h=0,q>=qhi", "h=+1", "h=+2",
              "h>=+3"]
    for b in range(N_PX):
        mass(px == b, "px_bucket", "%d %s" % (b, lab_px[b]))
    for b in range(N_SZ):
        mass(size == b, "size_bucket", ["1", "2-9", "10-49", ">=50"][b])
    for b in range(N_GAP):
        mass(gap == b, "gap_bucket", str(b))
    for b in range(N_ACT_SIDE):
        mass(acts == b, "act_side", "%s%s" % ("ACMTFR"[b // 3], "BAN"[b % 3]))
    rows.append(["vocab", "used_of_%d" % VOCAB_EVENTS, int((cnt > 0).sum()),
                 round(float((cnt > 0).sum()) / VOCAB_EVENTS, 6), 0])
    p = np.sort(cnt)[::-1].astype(np.float64) / tot
    rows.append(["vocab", "top10_mass", 0, round(float(p[:10].sum()), 6), 10])
    rows.append(["vocab", "top100_mass", 0, round(float(p[:100].sum()), 6), 100])
    rows.append(["vocab", "tail_mass_below_1e-4", 0,
                 round(float(p[p < 1e-4].sum()), 6), int((p < 1e-4).sum())])
    nzp = p[p > 0]
    rows.append(["vocab", "entropy_nats", 0,
                 round(float(-(nzp * np.log(nzp)).sum()), 6), 0])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--occupancy", action="store_true")
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    if a.fit:
        print(json.dumps(fit_cuts(min(a.workers, 8)), indent=1))
    if a.build:
        build(workers=a.workers)
    if a.occupancy:
        for r in occupancy_rows():
            print("\t".join(str(x) for x in r))
    if not (a.fit or a.build or a.occupancy):
        ap.print_help()


if __name__ == "__main__":
    main()

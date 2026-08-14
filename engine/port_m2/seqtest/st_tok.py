#!/usr/bin/python3
"""PORT M2 SEQTEST — the EVENT TOKENIZER and its two corpora.

The vocabulary is frozen in `design/SEQ_PRETRAIN_DESIGN.md` §3 and repeated here
as executable code; if the two ever disagree the design receipt is the law.

    tok = ((act_side * 7 + dmid_bucket) * 5 + size_bucket) * 5 + gap_bucket

    act_side     18   action byte {A,C,M,T,F,R} x side byte {B,A,N}
    dmid_bucket   7   L1 mid change vs the previous record, in ticks:
                      <=-3, -2, -1, 0, +1, +2, >=+3
    size_bucket   5   1, 2-3, 4-9, 10-49, >=50
    gap_bucket    5   <50us, <500us, <5ms, <50ms, >=50ms

    VOCAB = 18*7*5*5 = 3150 event tokens, + BOS(3150) + PAD(3151) = 3152

Every boundary is fixed a priori in tick / power-of-two / decade space.  Nothing
is fitted to the data, so there is no quantile-fitting leak to argue about.

TWO CORPORA, ONE PASS
  tokens/<ASSET>/<d8>.npz   the whole cached session as a token stream, plus the
                            contiguous `cover` BLOCK boundaries in event-index
                            space — a pretraining chunk may never cross one,
                            because the cache is a concatenation of per-candidate
                            windows and a crossing chunk splices unrelated tape.
  cand/TOK_<ASSET>_<ERA>.npy  int16 [n_rows, 1024] — the last 1024 events
                            STRICTLY BEFORE each m3-matrix candidate's decision
                            second, same clamp, left-padded with PAD.

Run:
    st_tok.py --build --workers 8
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

VOCAB_EVENTS = 18 * 7 * 5 * 5
BOS = VOCAB_EVENTS
PAD = VOCAB_EVENTS + 1
VOCAB = VOCAB_EVENTS + 2

CAND_LEN = 1024
CTX = 1024

TOK_DIR = os.path.join(SC.CACHE_ROOT, "tokens")
CAND_DIR = os.path.join(SC.CACHE_ROOT, "cand_tok")

_ACT = {a: i for i, a in enumerate(SC.ACTION_BYTES)}
_SIDE = {s: i for i, s in enumerate(SC.SIDE_BYTES)}

SIZE_EDGES = (1, 3, 9, 49)                 # -> 1 | 2-3 | 4-9 | 10-49 | >=50
GAP_EDGES_NS = (50_000, 500_000, 5_000_000, 50_000_000)
DMID_EDGES = (-2.5, -1.5, -0.5, 0.5, 1.5, 2.5)


def tokenize_day(asset, arr):
    """int16 token per record of a whole cached session."""
    n = int(arr["ts_ns"].size)
    tick = SC.tick_raw(asset)
    act = np.full(n, 5, dtype=np.int16)     # unknown -> the R cell
    for b, i in _ACT.items():
        act[arr["action"] == b] = i
    sid = np.full(n, 2, dtype=np.int16)     # unknown -> the N cell
    for b, i in _SIDE.items():
        sid[arr["side"] == b] = i
    act_side = act * 3 + sid

    mid = 0.5 * (arr["bid_px"].astype(np.float64)
                 + arr["ask_px"].astype(np.float64))
    d = np.zeros(n, dtype=np.float64)
    if n > 1:
        d[1:] = (mid[1:] - mid[:-1]) / tick
    dmid = np.searchsorted(np.asarray(DMID_EDGES), d, side="left")

    sz = arr["size"].astype(np.int64)
    szb = np.searchsorted(np.asarray(SIZE_EDGES), sz, side="left")

    gap = np.zeros(n, dtype=np.int64)
    if n > 1:
        gap[1:] = np.clip(np.diff(arr["ts_ns"]), 0, None)
    gpb = np.searchsorted(np.asarray(GAP_EDGES_NS), gap, side="left")

    tok = ((act_side.astype(np.int32) * 7 + dmid.astype(np.int32)) * 5
           + szb.astype(np.int32)) * 5 + gpb.astype(np.int32)
    return tok.astype(np.int16)


def _one_day(job):
    asset, d8, rows, decs = job
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
    tok = tokenize_day(asset, arr)
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
    # ---- the candidate windows, same clamp, same strict-before rule --------
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


def build(workers=8):
    t0 = time.time()
    os.makedirs(TOK_DIR, exist_ok=True)
    os.makedirs(CAND_DIR, exist_ok=True)
    z = np.load(os.path.join(M3.MATRIX_DIR, "matrix.npz"), allow_pickle=False)
    d8, ai, era, dec = z["d8"], z["asset_idx"], z["era_idx"], z["dec_sec"]
    z.close()
    M3.check_holdout(d8)
    counts = np.zeros(VOCAB_EVENTS, dtype=np.int64)
    stats = {"n_events": 0, "n_blocks": 0, "n_days": 0, "n_cand": 0,
             "shards": []}
    # every cached asset-day, not only the ones carrying candidates: the
    # pretraining corpus is the WHOLE cache
    for a_i, asset in enumerate(MC.ASSET_ORDER):
        cached = sorted(int(f[:-4]) for f in
                        os.listdir(os.path.join(SC.EVENTS_DIR, asset))
                        if f.endswith(".npz"))
        bad = [x for x in cached if x >= 20250701]
        if bad:
            raise SC.SeqTestRefusal(
                "HOLDOUT LEAK: %d cached sessions at or past 20250701 (%s)"
                % (len(bad), bad[:3]))
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
            jobs.append((asset, dd, r.tolist(), dec[r].tolist()))
        buf = {}
        pool = mp.Pool(processes=int(workers)) if workers > 1 else None
        it = pool.imap(_one_day, jobs, chunksize=1) if pool else map(_one_day,
                                                                     jobs)
        for _a, dd, res in it:
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
        if pool is not None:
            pool.close()
            pool.join()
        for e, parts in buf.items():
            rows = np.concatenate([p[0] for p in parts])
            cw = np.concatenate([p[1] for p in parts])
            np.save(os.path.join(CAND_DIR, "TOK_%s_%s.npy" % (asset, e)), cw)
            np.savez(os.path.join(CAND_DIR, "TOK_%s_%s.meta.npz" % (asset, e)),
                     row_idx=rows)
            stats["n_cand"] += int(rows.size)
            stats["shards"].append([asset, e, int(rows.size)])
            SC.hb("cand tokens %s %s: %d rows (%.0fs)"
                  % (asset, e, rows.size, time.time() - t0))
        SC.hb("tokenised %s (%.0fs)" % (asset, time.time() - t0))
    p = counts.astype(np.float64) / max(counts.sum(), 1)
    nz = p[p > 0]
    stats["unigram_entropy_nats"] = float(-(nz * np.log(nz)).sum())
    stats["unigram_entropy_bits"] = stats["unigram_entropy_nats"] / np.log(2)
    stats["n_tokens_used"] = int((counts > 0).sum())
    stats["vocab"] = VOCAB
    stats["elapsed_sec"] = round(time.time() - t0, 1)
    np.save(os.path.join(SC.CACHE_ROOT, "token_counts.npy"), counts)
    rec = M3.env_receipt(dict(SC.PARAMS, tokenizer="SEQ_PRETRAIN_DESIGN.md §3"))
    rec.update(stats)
    with open(os.path.join(SC.CACHE_ROOT, "tokens.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True, default=str)
    SC.hb("tokenizer done: %d events, %d blocks, %d candidate windows, "
          "unigram entropy %.4f nats (%.0fs)"
          % (stats["n_events"], stats["n_blocks"], stats["n_cand"],
             stats["unigram_entropy_nats"], stats["elapsed_sec"]))
    return stats


# ------------------------------------------------------------- consumers ----
def load_pretrain_corpus(max_d8, assets=MC.ASSET_ORDER):
    """One flat int16 stream + a chunk index that never crosses a cover block."""
    t0 = time.time()
    toks, starts, aidx = [], [], []
    at = 0
    for a_i, asset in enumerate(assets):
        d = os.path.join(TOK_DIR, asset)
        for f in sorted(os.listdir(d)):
            if not f.endswith(".npz"):
                continue
            if int(f[:-4]) >= int(max_d8):
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
    SC.hb("pretrain corpus <%d: %d events, %d chunks of %d (%.1f GB, %.0fs)"
          % (max_d8, T.size, S.size, CTX, T.nbytes / 1e9, time.time() - t0))
    return T, S, A


def load_cand_tokens():
    """int16 [n, 1024] aligned to m3 matrix rows (returns array + row index)."""
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    if a.build:
        build(workers=min(int(a.workers), 8))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()

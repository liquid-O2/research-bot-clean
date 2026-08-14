#!/usr/bin/python3
"""PORT M2 SEQTEST — the AUXILIARY per-event corpus (design receipt A3 + A4).

Two arrays per cached asset-day, both float16, both aligned 1:1 with the token
stream `st_tok` wrote:

  IN[9]   the extra INPUT channels
          0-3  sin/cos of the session fraction, first and second harmonic
          4    the phase fraction (position inside the current phase)
          5-7  the 3-way phase one-hot; the phase of an event is the phase of
               the LAST CANDIDATE AT OR BEFORE it in the committed m3 matrix,
               so it is causal and it reuses the program's own determination
          8    signed tick distance to the nearest ACTIVE KEPT-FAMILY level
               (`levels_v4`, `dynamic == 0` only — the static families exist
               from the session open, so using them at any second is causal
               without an intra-day birth time)
  IN2[1]  9    the same for the SECOND-nearest such level

  TGT[8]  the MULTI-HORIZON targets, 60 s then 300 s:
          net mid move (ticks), mid range (ticks), signed aggression balance,
          book-imbalance change.  A position whose horizon runs past the end of
          its contiguous `cover` block is MASKED (NaN), never imputed.

Run:  st_aux.py --build --workers 8
"""
import argparse
import json
import multiprocessing as mp
import os
import time

import numpy as np

import st_common as SC
import st_tok as TK
import m2_common as MC
import m3_common as M3

AUX_DIR = os.path.join(SC.CACHE_ROOT, "aux")
LEVELS_DIR = "/workspace/artifacts/cache/port/m1/levels_v4"
N_IN = 10
N_TGT = 8
HORIZONS = (60, 300)
SESSION_SEC = 86400


def _sliding(a, w, fn):
    """max/min of `a` over the FORWARD window [i, i+w)."""
    n = a.size
    pad = np.concatenate([a, np.full(w, a[-1] if n else 0.0)])
    v = np.lib.stride_tricks.sliding_window_view(pad, w)[:n]
    return fn(v, axis=1)


def _one_day(job):
    asset, d8, cand_sec, cand_phase = job
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
    n = int(ts.size)
    if n == 0:
        return asset, int(d8), None
    o = int(meta["open_utc"])
    tick = SC.tick_raw(asset)
    sec = np.clip((ts // 1_000_000_000 - o).astype(np.int64), 0,
                  SESSION_SEC - 1)
    mid = 0.5 * (arr["bid_px"].astype(np.float64)
                 + arr["ask_px"].astype(np.float64))

    IN = np.zeros((N_IN, n), dtype=np.float16)
    frac = sec.astype(np.float64) / float(SESSION_SEC)
    IN[0] = np.sin(2 * np.pi * frac)
    IN[1] = np.cos(2 * np.pi * frac)
    IN[2] = np.sin(4 * np.pi * frac)
    IN[3] = np.cos(4 * np.pi * frac)
    # ---- phase: the last candidate at or before the event ------------------
    ph = np.zeros(n, dtype=np.int64)
    if len(cand_sec):
        cs = np.asarray(cand_sec, dtype=np.int64)
        cp = np.asarray(cand_phase, dtype=np.int64)
        k = np.searchsorted(cs, sec, side="right") - 1
        ph = np.where(k >= 0, cp[np.clip(k, 0, cp.size - 1)], 0)
    for q in range(3):
        IN[5 + q] = (ph == q)
    bounds = np.zeros(n, dtype=np.float64)
    for q in range(3):
        m = ph == q
        if m.any():
            s0 = sec[m].min()
            s1 = max(sec[m].max(), s0 + 1)
            bounds[m] = (sec[m] - s0) / float(s1 - s0)
    IN[4] = bounds
    # ---- level-relative distances -----------------------------------------
    lp = os.path.join(LEVELS_DIR, asset, "%08d.npz" % int(d8))
    if os.path.exists(lp):
        lz = np.load(lp, allow_pickle=False)
        fam = np.asarray([str(x) for x in lz["level_family"].tolist()])
        keep = np.isin(fam, np.asarray(MC.KEPT_LEVEL_FAMILIES)) \
            & (lz["dynamic"] == 0)
        px = np.sort(np.asarray(lz["level_price"], dtype=np.float64)[keep])
        lz.close()
        if px.size:
            scale = 1e-9                       # levels_v4 prices are in $
            mid_usd = mid * scale
            k = np.searchsorted(px, mid_usd)
            d1 = np.full(n, np.nan)
            d2 = np.full(n, np.nan)
            lo = np.clip(k - 1, 0, px.size - 1)
            hi = np.clip(k, 0, px.size - 1)
            dlo = (mid_usd - px[lo])
            dhi = (mid_usd - px[hi])
            near = np.where(np.abs(dlo) <= np.abs(dhi), dlo, dhi)
            far = np.where(np.abs(dlo) <= np.abs(dhi), dhi, dlo)
            tick_usd = tick * scale
            d1 = np.clip(near / tick_usd, -500, 500)
            d2 = np.clip(far / tick_usd, -500, 500)
            IN[8] = d1
            IN[9] = d2

    # ---- the multi-horizon targets, per SECOND then gathered --------------
    TGT = np.full((N_TGT, n), np.nan, dtype=np.float16)
    sec_mid = np.full(SESSION_SEC, np.nan)
    sec_mid[sec] = mid                         # last-wins is fine at 1s grain
    idx = np.flatnonzero(np.isfinite(sec_mid))
    if idx.size >= 2:
        ff = np.maximum.accumulate(np.where(np.isfinite(sec_mid),
                                            np.arange(SESSION_SEC), -1))
        ff = np.clip(ff, 0, None)
        smid = sec_mid[ff]
        smid = np.where(np.isfinite(smid), smid,
                        sec_mid[idx[0]]).astype(np.float32)
        is_t = arr["action"] == ord("T")
        sgn = np.where(arr["side"] == ord("B"), 1.0,
                       np.where(arr["side"] == ord("A"), -1.0, 0.0))
        flow = np.zeros(SESSION_SEC)
        vol = np.zeros(SESSION_SEC)
        np.add.at(flow, sec[is_t], (sgn * arr["size"])[is_t])
        np.add.at(vol, sec[is_t], arr["size"][is_t].astype(np.float64))
        cf = np.concatenate([[0.0], np.cumsum(flow)])
        cv = np.concatenate([[0.0], np.cumsum(vol)])
        bs = arr["bid_sz"].astype(np.float64)
        aszz = arr["ask_sz"].astype(np.float64)
        imb_ev = (bs - aszz) / np.maximum(bs + aszz, 1.0)
        sec_imb = np.full(SESSION_SEC, np.nan)
        sec_imb[sec] = imb_ev
        simb = sec_imb[ff]
        simb = np.where(np.isfinite(simb), simb, 0.0)
        # the last covered second of each event's own block
        cover = [(int(a), int(b)) for a, b in meta["cover"]]
        blk_end = np.zeros(n, dtype=np.int64)
        for a, b in cover:
            m = (sec >= a) & (sec <= b)
            blk_end[m] = b
        for hi_i, H in enumerate(HORIZONS):
            tgt = np.clip(sec + H, 0, SESSION_SEC - 1)
            ok = (sec + H) <= blk_end
            dmid = (smid[tgt] - smid[sec]) / tick
            mx = _sliding(smid, H, np.max)
            mn = _sliding(smid, H, np.min)
            rng = (mx[sec] - mn[sec]) / tick
            f = cf[tgt] - cf[sec]
            v = cv[tgt] - cv[sec]
            aggr = f / np.maximum(v, 1.0)
            dimb = simb[tgt] - simb[sec]
            base = hi_i * 4
            for k2, vv in enumerate((np.clip(dmid, -2000, 2000),
                                     np.clip(rng, 0, 4000), aggr, dimb)):
                TGT[base + k2] = np.where(ok, vv, np.nan)
    np.savez(os.path.join(AUX_DIR, asset, "%08d.npz" % int(d8)),
             IN=IN, TGT=TGT)
    return asset, int(d8), (n, float(np.isfinite(TGT[0]).mean()),
                            float(np.isfinite(TGT[4]).mean()))


def build(workers=8):
    t0 = time.time()
    z = np.load(os.path.join(M3.MATRIX_DIR, "matrix.npz"), allow_pickle=False)
    d8, ai, dec, ph = z["d8"], z["asset_idx"], z["dec_sec"], z["phase_dec"]
    z.close()
    M3.check_holdout(d8)
    stats = {"n_events": 0, "n_days": 0, "cov_h60": [], "cov_h300": []}
    for a_i, asset in enumerate(MC.ASSET_ORDER):
        os.makedirs(os.path.join(AUX_DIR, asset), exist_ok=True)
        cached = sorted(int(f[:-4]) for f in
                        os.listdir(os.path.join(SC.EVENTS_DIR, asset))
                        if f.endswith(".npz"))
        m = ai == a_i
        dd, ss, pp = d8[m], dec[m], ph[m]
        jobs = []
        for day in cached:
            k = np.nonzero(dd == day)[0]
            if k.size:
                o = np.argsort(ss[k], kind="stable")
                jobs.append((asset, day, ss[k][o].tolist(),
                             pp[k][o].astype(np.int64).tolist()))
            else:
                jobs.append((asset, day, [], []))
        pool = mp.Pool(processes=int(workers)) if workers > 1 else None
        it = pool.imap(_one_day, jobs, chunksize=1) if pool else map(_one_day,
                                                                     jobs)
        for _a, _d, res in it:
            if res is None:
                continue
            stats["n_events"] += res[0]
            stats["n_days"] += 1
            stats["cov_h60"].append(res[1])
            stats["cov_h300"].append(res[2])
        if pool is not None:
            pool.close()
            pool.join()
        SC.hb("aux %s done (%.0fs)" % (asset, time.time() - t0))
    stats["cov_h60"] = float(np.mean(stats["cov_h60"])) if stats["cov_h60"] \
        else 0.0
    stats["cov_h300"] = float(np.mean(stats["cov_h300"])) if stats["cov_h300"] \
        else 0.0
    stats["elapsed_sec"] = round(time.time() - t0, 1)
    rec = M3.env_receipt(dict(SC.PARAMS, aux="SEQ_PRETRAIN_DESIGN A3+A4"))
    rec.update(stats)
    with open(os.path.join(SC.CACHE_ROOT, "aux.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True, default=str)
    SC.hb("aux build done: %d events, %d days, h60 coverage %.3f, h300 %.3f "
          "(%.0fs)" % (stats["n_events"], stats["n_days"], stats["cov_h60"],
                       stats["cov_h300"], stats["elapsed_sec"]))
    return stats


CAND_DIR = os.path.join(SC.CACHE_ROOT, "cand_aux")


def _cand_one(job):
    """The last CAND_LEN events' side channels for every candidate of a day."""
    asset, d8, rows, decs = job
    p = os.path.join(AUX_DIR, asset, "%08d.npz" % int(d8))
    e = os.path.join(SC.EVENTS_DIR, asset, "%08d.npz" % int(d8))
    j = os.path.join(SC.EVENTS_DIR, asset, "%08d.json" % int(d8))
    if not (os.path.exists(p) and os.path.exists(e)):
        return asset, int(d8), None, None
    with open(j) as fh:
        meta = json.load(fh)
    ts = np.load(e)["ts_ns"]
    IN = np.load(p)["IN"]
    o = int(meta["open_utc"])
    cover = [(int(a), int(b)) for a, b in meta["cover"]]
    L = TK.CAND_LEN
    dec = np.asarray(decs, dtype=np.int64)
    cut_ns = (o + dec) * 1_000_000_000
    hi = np.searchsorted(ts, cut_ns, side="left")
    out = np.zeros((dec.size, L, N_IN), dtype=np.float16)
    for k in range(dec.size):
        cs = SC.cover_start_sec(cover, int(dec[k]))
        lo0 = int(np.searchsorted(ts, (o + cs) * 1_000_000_000, side="left"))
        b = int(hi[k])
        a = max(lo0, b - L)
        m = b - a
        if m > 0:
            out[k, L - m:, :] = IN[:, a:b].T
    return asset, int(d8), np.asarray(rows, dtype=np.int64), out


def build_cand(workers=8):
    t0 = time.time()
    os.makedirs(CAND_DIR, exist_ok=True)
    z = np.load(os.path.join(M3.MATRIX_DIR, "matrix.npz"), allow_pickle=False)
    d8, ai, dec, era = z["d8"], z["asset_idx"], z["dec_sec"], z["era_idx"]
    z.close()
    n_rows = 0
    for a_i, asset in enumerate(MC.ASSET_ORDER):
        for ename in SC.UNIVERSE_ERAS:
            sel = np.nonzero((ai == a_i) & (era == SC.ERA_IDX[ename]))[0]
            if sel.size == 0:
                continue
            jobs = []
            for dd in np.unique(d8[sel]).tolist():
                r = sel[d8[sel] == dd]
                r = r[np.argsort(dec[r], kind="stable")]
                jobs.append((asset, int(dd), r.tolist(), dec[r].tolist()))
            pool = mp.Pool(processes=int(workers)) if workers > 1 else None
            it = pool.imap(_cand_one, jobs, chunksize=1) if pool \
                else map(_cand_one, jobs)
            parts = []
            for _a, _d, rows, arr in it:
                if arr is not None:
                    parts.append((rows, arr))
            if pool is not None:
                pool.close()
                pool.join()
            rows = np.concatenate([p[0] for p in parts])
            arr = np.concatenate([p[1] for p in parts])
            np.save(os.path.join(CAND_DIR, "AUX_%s_%s.npy" % (asset, ename)),
                    arr)
            np.savez(os.path.join(CAND_DIR,
                                  "AUX_%s_%s.meta.npz" % (asset, ename)),
                     row_idx=rows)
            n_rows += int(rows.size)
            SC.hb("cand aux %s %s: %d rows (%.0fs)"
                  % (asset, ename, rows.size, time.time() - t0))
    SC.hb("cand aux done: %d rows (%.0fs)" % (n_rows, time.time() - t0))
    return n_rows


def load_cand_aux():
    parts, rows = [], []
    for asset in MC.ASSET_ORDER:
        for e in SC.UNIVERSE_ERAS:
            p = os.path.join(CAND_DIR, "AUX_%s_%s.npy" % (asset, e))
            if not os.path.exists(p):
                continue
            parts.append(np.load(p))
            rows.append(np.load(os.path.join(
                CAND_DIR, "AUX_%s_%s.meta.npz" % (asset, e)))["row_idx"])
    return np.concatenate(parts), np.concatenate(rows)


def load_aux(max_d8, assets=MC.ASSET_ORDER):
    """Flat IN / TGT streams matching `st_tok.load_pretrain_corpus` order."""
    ins, tgs = [], []
    for asset in assets:
        d = os.path.join(TK.TOK_DIR, asset)
        for f in sorted(os.listdir(d)):
            if not f.endswith(".npz") or int(f[:-4]) >= int(max_d8):
                continue
            p = os.path.join(AUX_DIR, asset, f)
            z = np.load(p)
            ins.append(z["IN"].T.copy())
            tgs.append(z["TGT"].T.copy())
            z.close()
    return np.concatenate(ins), np.concatenate(tgs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--cand", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    if a.cand:
        build_cand(workers=min(int(a.workers), 8))
    elif a.build:
        os.makedirs(AUX_DIR, exist_ok=True)
        build(workers=min(int(a.workers), 8))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()

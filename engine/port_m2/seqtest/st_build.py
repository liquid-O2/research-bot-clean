#!/usr/bin/python3
"""PORT M2 SEQTEST — build the raw-event tensors, once, to disk.

One shard per (asset, era) per WINDOW LENGTH:

    shards/L<N>/SEQ_<ASSET>_<ERA>.npy       float16 [n_rows, 21, N]
    shards/L<N>/SEQ_<ASSET>_<ERA>.meta.npz  m3 matrix ROW INDICES + fill stats

The long window is built once and the shorter ones are its exact TAIL, so
{256, 1024, 4096} are the same tape read at three depths and nothing about the
comparison depends on a second extraction.

The tensor rows are indexed back into the committed m3 matrix, so every label,
outcome, ceiling and guard of that matrix applies to them unchanged — the shard
carries no label of its own and cannot disagree with the harness.

Run:
    lab/run.sh port-m2-seqtest-build -- /usr/bin/python3 \
        engine/port_m2/seqtest/st_build.py --build --workers 8
"""
import argparse
import json
import multiprocessing as mp
import os
import time

import numpy as np

import st_common as SC                    # noqa: E402  (path set in st_common)
import m2_common as MC                    # noqa: E402
import m3_common as M3                    # noqa: E402


def _day_channels(asset, arr):
    """The 19 record-level channels for a WHOLE cached session, vectorised.

    (Channel 19 `log_secs_to_decision` and channel 20 `valid` are per-candidate
    and are filled by the slicer.)
    """
    n = int(arr["ts_ns"].size)
    tick = SC.tick_raw(asset)
    ch = np.zeros((SC.N_CH, n), dtype=np.float32)
    act, side = arr["action"], arr["side"]
    for i, a in enumerate(SC.ACTION_BYTES):
        ch[i] = (act == a)
    for i, s in enumerate(SC.SIDE_BYTES):
        ch[6 + i] = (side == s)
    px = arr["price"].astype(np.float64)
    bp = arr["bid_px"].astype(np.float64)
    ap = arr["ask_px"].astype(np.float64)
    mid = 0.5 * (bp + ap)
    d = np.zeros(n, dtype=np.float64)
    d[1:] = (px[1:] - px[:-1]) / tick
    ch[9] = np.clip(d, -SC.CLIP_TICKS, SC.CLIP_TICKS)
    d = np.zeros(n, dtype=np.float64)
    d[1:] = (mid[1:] - mid[:-1]) / tick
    ch[10] = np.clip(d, -SC.CLIP_TICKS, SC.CLIP_TICKS)
    ch[11] = np.clip((px - mid) / tick, -SC.CLIP_TICKS, SC.CLIP_TICKS)
    ch[12] = np.log1p(arr["size"].astype(np.float64))
    gap = np.zeros(n, dtype=np.float64)
    if n > 1:
        gap[1:] = np.clip(np.diff(arr["ts_ns"]).astype(np.float64), 0.0, None)
    ch[13] = np.log1p(gap / 1e3)           # microseconds
    ch[14] = np.log1p(np.clip(arr["bid_sz"].astype(np.float64), 0, None))
    ch[15] = np.log1p(np.clip(arr["ask_sz"].astype(np.float64), 0, None))
    ch[16] = np.log1p(np.clip(arr["bid_ct"].astype(np.float64), 0, None))
    ch[17] = np.log1p(np.clip(arr["ask_ct"].astype(np.float64), 0, None))
    ch[18] = np.clip((ap - bp) / tick, -SC.CLIP_SPREAD, SC.CLIP_SPREAD)
    return ch


def _one_day(job):
    """Build the [n_cand, 21, SEQ_LEN_MAX] block for one (asset, d8)."""
    asset, d8, rows, decs = job
    p = os.path.join(SC.EVENTS_DIR, asset, "%08d.npz" % int(d8))
    j = os.path.join(SC.EVENTS_DIR, asset, "%08d.json" % int(d8))
    if not (os.path.exists(p) and os.path.exists(j)):
        return asset, int(d8), np.asarray(rows, dtype=np.int64), None, "NO_CACHE"
    with open(j) as fh:
        meta = json.load(fh)
    z = np.load(p)
    arr = {k: z[k] for k in z.files}
    z.close()
    ts = arr["ts_ns"]
    if ts.size == 0:
        return asset, int(d8), np.asarray(rows, dtype=np.int64), None, "EMPTY"
    ch = _day_channels(asset, arr)
    open_utc = int(meta["open_utc"])
    cover = [(int(a), int(b)) for a, b in meta["cover"]]
    L = SC.SEQ_LEN_MAX
    dec = np.asarray(decs, dtype=np.int64)
    # STRICTLY BEFORE the decision second: [.., (open_utc + dec) * 1e9)
    cut_ns = (open_utc + dec) * 1_000_000_000
    hi = np.searchsorted(ts, cut_ns, side="left")
    out = np.zeros((dec.size, SC.N_CH, L), dtype=np.float16)
    n_ev = np.zeros(dec.size, dtype=np.int32)
    for k in range(dec.size):
        cs = SC.cover_start_sec(cover, int(dec[k]))
        lo0 = int(np.searchsorted(ts, (open_utc + cs) * 1_000_000_000,
                                  side="left"))
        b = int(hi[k])
        a = max(lo0, b - L)
        m = b - a
        if m <= 0:
            continue
        n_ev[k] = m
        out[k, :19, L - m:] = ch[:19, a:b]
        # every channel takes the SAME precision path — float64 arithmetic,
        # float32 intermediate, float16 storage — so an independent
        # recomputation reproduces the shard bit for bit (test_seqtest).
        out[k, SC.CH_TTD, L - m:] = np.log1p(
            np.clip((cut_ns[k] - ts[a:b]).astype(np.float64), 0.0, None)
            / 1e9).astype(np.float32)
        out[k, SC.CH_VALID, L - m:] = np.float32(1.0)
    return asset, int(d8), np.asarray(rows, dtype=np.int64), (out, n_ev), "OK"


def build(workers=8, eras=SC.UNIVERSE_ERAS, limit=None, lens=SC.SEQ_LENS):
    t0 = time.time()
    for L in lens:
        os.makedirs(os.path.join(SC.SHARD_DIR, "L%d" % L), exist_ok=True)
    z = np.load(os.path.join(M3.MATRIX_DIR, "matrix.npz"), allow_pickle=False)
    d8 = z["d8"]
    M3.check_holdout(d8)                   # the m3 holdout guard, inherited
    ai = z["asset_idx"]
    era = z["era_idx"]
    dec = z["dec_sec"]
    z.close()
    stats = {"n_rows": 0, "n_days": 0, "n_no_cache": 0, "n_empty": 0,
             "fill": {}, "shards": []}
    for a_i, asset in enumerate(MC.ASSET_ORDER):
        for ename in eras:
            k = SC.ERA_IDX[ename]
            sel = np.nonzero((ai == a_i) & (era == k))[0]
            if sel.size == 0:
                continue
            days = np.unique(d8[sel])
            if limit:
                days = days[:limit]
                sel = sel[np.isin(d8[sel], days)]
            jobs = []
            for dd in days.tolist():
                r = sel[d8[sel] == dd]
                r = r[np.argsort(dec[r], kind="stable")]
                jobs.append((asset, int(dd), r.tolist(), dec[r].tolist()))
            T = np.zeros((sel.size, SC.N_CH, SC.SEQ_LEN_MAX), dtype=np.float16)
            rowmap = np.zeros(sel.size, dtype=np.int64)
            nev = np.zeros(sel.size, dtype=np.int32)
            pos = 0
            if workers > 1:
                pool = mp.Pool(processes=int(workers))
                it = pool.imap(_one_day, jobs, chunksize=1)
            else:
                pool, it = None, map(_one_day, jobs)
            for _asset, _dd, rows, res, status in it:
                if res is None:
                    stats["n_no_cache" if status == "NO_CACHE"
                          else "n_empty"] += 1
                    continue
                out, ne = res
                m = rows.size
                T[pos:pos + m] = out
                rowmap[pos:pos + m] = rows
                nev[pos:pos + m] = ne
                pos += m
                stats["n_days"] += 1
            if pool is not None:
                pool.close()
                pool.join()
            T, rowmap, nev = T[:pos], rowmap[:pos], nev[:pos]
            fill = {}
            for L in lens:
                base = SC.shard_path(asset, ename, L)
                np.save(base + ".npy",
                        T if L == SC.SEQ_LEN_MAX
                        else np.ascontiguousarray(T[:, :, -L:]))
                np.savez(base + ".meta.npz", row_idx=rowmap, n_events=nev,
                         asset=np.array([asset]), era=np.array([ename]),
                         seq_len=np.array([L]))
                fill["L%d" % L] = round(float((nev >= L).mean()), 4) \
                    if pos else 0.0
            stats["n_rows"] += int(pos)
            stats["shards"].append([asset, ename, int(pos), fill])
            stats["fill"]["%s|%s" % (asset, ename)] = {
                "mean_events": float(nev.mean()) if pos else 0.0,
                "median_events": float(np.median(nev)) if pos else 0.0,
                "frac_full": fill}
            SC.hb("shard %s %s: %d rows  fill %s  (%.0fs)"
                  % (asset, ename, pos, fill, time.time() - t0))
            del T
    stats["elapsed_sec"] = round(time.time() - t0, 1)
    rec = M3.env_receipt(SC.PARAMS)
    rec.update(stats)
    with open(os.path.join(SC.CACHE_ROOT, "build.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True, default=str)
    SC.hb("build done: %d rows, %d days, %.1fs"
          % (stats["n_rows"], stats["n_days"], stats["elapsed_sec"]))
    return stats


def load_shard(asset, era, L, mmap=True):
    base = SC.shard_path(asset, era, L)
    T = np.load(base + ".npy", mmap_mode="r" if mmap else None)
    m = np.load(base + ".meta.npz")
    return T, m["row_idx"], m["n_events"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--eras", default=",".join(SC.UNIVERSE_ERAS))
    ap.add_argument("--lens", default=",".join(str(x) for x in SC.SEQ_LENS))
    a = ap.parse_args()
    if a.build:
        build(workers=min(int(a.workers), 8), eras=tuple(a.eras.split(",")),
              limit=a.limit,
              lens=tuple(int(x) for x in a.lens.split(",")))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()

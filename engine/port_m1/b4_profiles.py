#!/usr/bin/python3
"""PORT M1 Track B-4 — volume-profile / AMT objects (§5).

Per session and per phase, from the session receipt's dominant-instrument
trades: an integer-tick price x volume histogram, smoothed with the fixed
5-tick centred TRIANGULAR kernel [1,2,3,2,1]/9.  Every tie rule is the one §5
states; there is no RNG and no floating-point bin arithmetic (bins are integer
tick indices, price = tick_index x tick_px exactly).

Objects (§5):
  POC          argmax of the smoothed profile, LEFTMOST on ties
  VA/VAH/VAL   smallest price-contiguous set holding 70% of volume, grown
               greedily from the POC, higher-volume neighbour first, LEFTMOST
               on ties
  HVN / LVN    local maxima / minima of the smoothed profile with topographic
               prominence >= 10% of the POC mass
  single print bins with RAW volume < 1% of the mean bin volume inside the
               session range
  poor hi/lo   the extreme bin has volume > 3x the median of the 5 adjacent
               bins on the extreme side
  developing   causal POC/VA recomputed every 5 min from trades so far

The profile array is padded by 2 bins on each side of the traded range so the
kernel loses no mass: sum(smoothed) == sum(raw) exactly.
"""
import multiprocessing as mp
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M
import common as C
import census_common as X

SECTION = "§5 volume profile / AMT"

KERNEL = np.array([1.0, 2.0, 3.0, 2.0, 1.0]) / 9.0
PAD = 2                       # half-width of the kernel
VA_FRACTION = 0.70
PROMINENCE_FRAC = 0.10        # of POC mass
SINGLE_PRINT_FRAC = 0.01      # of mean bin volume
POOR_EXTREME_MULT = 3.0
POOR_ADJACENT = 5
DEV_INTERVAL = 300            # §5 "recomputed each 5 min"

SCOPES = ("SESSION", "TOKYO", "LONDON", "NY")

PARAMS = {
    "spec_section": SECTION,
    "kernel": "[1,2,3,2,1]/9 centred triangular, 5 ticks",
    "pad_bins": PAD,
    "value_area_fraction": VA_FRACTION,
    "va_growth": "greedy from POC, higher-volume neighbour first, leftmost on "
                 "ties; volumes taken from the SMOOTHED profile (the profile "
                 "§5 defines the POC on)",
    "poc": "argmax smoothed, leftmost on ties",
    "prominence_frac_of_poc": PROMINENCE_FRAC,
    "single_print": "RAW bin volume < %.2f x mean RAW bin volume inside the "
                    "traded range" % SINGLE_PRINT_FRAC,
    "poor_extreme": "extreme RAW bin volume > %.1f x median of the %d adjacent "
                    "bins on the extreme side" % (POOR_EXTREME_MULT,
                                                  POOR_ADJACENT),
    "developing_interval_sec": DEV_INTERVAL,
    "bins": "integer tick index = round(price_raw / tick_raw); price = "
            "tick_index x tick_px (exact on the tick grid)",
    "scopes": list(SCOPES),
}


# ------------------------------------------------------------- primitives ---
def smooth(raw):
    """Zero-padded convolution with the fixed kernel; mass-preserving."""
    return np.convolve(raw.astype(np.float64), KERNEL, mode="same")


def poc_index(sm):
    """argmax, leftmost on ties."""
    return int(np.argmax(sm))


def value_area(sm, poc, fraction=VA_FRACTION):
    """§5 greedy growth.  Returns (lo, hi) inclusive bin indices."""
    n = sm.size
    total = float(sm.sum())
    if total <= 0:
        return poc, poc
    need = fraction * total
    lo = hi = poc
    acc = float(sm[poc])
    while acc < need and (lo > 0 or hi < n - 1):
        vlo = float(sm[lo - 1]) if lo > 0 else float("-inf")
        vhi = float(sm[hi + 1]) if hi < n - 1 else float("-inf")
        if vlo > vhi or (vlo == vhi and lo > 0):
            lo -= 1
            acc += vlo
        else:
            hi += 1
            acc += vhi
    return lo, hi


def prominences(sm, want_max=True):
    """Topographic prominence of every strict local extremum.

    Returns [(index, value, prominence), ...] in index order.  For minima the
    array is negated, which makes the definition exactly symmetric.
    """
    a = sm if want_max else -sm
    n = a.size
    out = []
    for i in range(1, n - 1):
        if not (a[i] > a[i - 1] and a[i] >= a[i + 1]):
            continue
        if a[i] == a[i + 1]:
            # plateau: keep only the leftmost bin of a flat top
            j = i + 1
            while j < n - 1 and a[j] == a[i]:
                j += 1
            if a[j] > a[i]:
                continue
        v = a[i]
        j = i - 1
        lmin = v
        while j >= 0 and a[j] <= v:
            lmin = min(lmin, a[j])
            j -= 1
        k = i + 1
        rmin = v
        while k < n and a[k] <= v:
            rmin = min(rmin, a[k])
            k += 1
        out.append((i, float(sm[i]), float(v - max(lmin, rmin))))
    return out


def build_profile(tick_idx, sizes):
    """(bin0, raw counts) over the traded range, padded by PAD on each side."""
    if tick_idx.size == 0:
        return 0, np.zeros(0, dtype=np.int64)
    lo = int(tick_idx.min()) - PAD
    hi = int(tick_idx.max()) + PAD
    raw = np.zeros(hi - lo + 1, dtype=np.int64)
    np.add.at(raw, (tick_idx - lo).astype(np.int64), sizes.astype(np.int64))
    return lo, raw


def profile_objects(bin0, raw, tick_px):
    """Every §5 object for one profile."""
    n = raw.size
    o = {"bin0": bin0, "n_bins": n, "total_volume": int(raw.sum()),
         "poc_tick": -1, "vah_tick": -1, "val_tick": -1,
         "hvn_ticks": np.zeros(0, np.int64), "lvn_ticks": np.zeros(0, np.int64),
         "hvn_prom": np.zeros(0, np.float64), "lvn_prom": np.zeros(0, np.float64),
         "single_print_ticks": np.zeros(0, np.int64),
         "poor_high": False, "poor_low": False,
         "smooth": np.zeros(0, np.float64)}
    if n == 0 or raw.sum() == 0:
        return o
    sm = smooth(raw)
    o["smooth"] = sm
    poc = poc_index(sm)
    lo, hi = value_area(sm, poc)
    o["poc_tick"] = bin0 + poc
    o["val_tick"] = bin0 + lo
    o["vah_tick"] = bin0 + hi
    thr = PROMINENCE_FRAC * float(sm[poc])
    hv = [p for p in prominences(sm, True) if p[2] >= thr]
    lv = [p for p in prominences(sm, False) if p[2] >= thr]
    o["hvn_ticks"] = np.array([bin0 + p[0] for p in hv], dtype=np.int64)
    o["hvn_prom"] = np.array([p[2] for p in hv], dtype=np.float64)
    o["lvn_ticks"] = np.array([bin0 + p[0] for p in lv], dtype=np.int64)
    o["lvn_prom"] = np.array([p[2] for p in lv], dtype=np.float64)

    # inside the TRADED range (exclude the zero padding)
    inner = raw[PAD:n - PAD] if n > 2 * PAD else raw
    inner0 = bin0 + (PAD if n > 2 * PAD else 0)
    if inner.size:
        mean_bin = float(inner.mean())
        sp = np.nonzero(inner < SINGLE_PRINT_FRAC * mean_bin)[0]
        o["single_print_ticks"] = (inner0 + sp).astype(np.int64)
        # poor high / poor low on the extremes of the traded range
        o["poor_high"] = _poor(inner, -1)
        o["poor_low"] = _poor(inner, +1)
    return o


def _poor(inner, direction):
    """direction=-1 -> high end, +1 -> low end."""
    if inner.size < POOR_ADJACENT + 1:
        return False
    if direction < 0:
        ext = float(inner[-1])
        adj = inner[-1 - POOR_ADJACENT:-1]
    else:
        ext = float(inner[0])
        adj = inner[1:1 + POOR_ADJACENT]
    m = float(np.median(adj))
    return bool(m > 0 and ext > POOR_EXTREME_MULT * m)


# ---------------------------------------------------------------- worker ----
def _shard(args):
    asset, month, sess = args
    spec = C.ASSETS[asset]
    tick_raw = spec["tick_raw"]
    tick_px = spec["tick_px"]
    rows = []
    for trade_date, path in sess:
        z = np.load(path, allow_pickle=False)
        tsec = z["trades_sec"].astype(np.int64)
        tpx = z["trades_px"].astype(np.int64)
        tsz = z["trades_size"].astype(np.int64)
        phase = z["phase_tag"]
        z.close()
        good = (tpx > 0) & (tpx < C.SENT_HI) & (tsz > 0) & (tsec >= 0) \
            & (tsec < phase.size)
        tsec, tpx, tsz = tsec[good], tpx[good], tsz[good]
        tick = np.rint(tpx / float(tick_raw)).astype(np.int64)
        arrays = {}
        for scope in SCOPES:
            if scope == "SESSION":
                sel = np.ones(tsec.size, dtype=bool)
            else:
                sel = phase[tsec] == X.PHASE_NAMES.index(scope)
            b0, raw = build_profile(tick[sel], tsz[sel])
            o = profile_objects(b0, raw, tick_px)
            pre = scope + "_"
            arrays[pre + "bin0"] = np.int64(b0)
            arrays[pre + "raw"] = raw
            arrays[pre + "smooth"] = o["smooth"]
            for k in ("poc_tick", "vah_tick", "val_tick"):
                arrays[pre + k] = np.int64(o[k])
            for k in ("hvn_ticks", "lvn_ticks", "hvn_prom", "lvn_prom",
                      "single_print_ticks"):
                arrays[pre + k] = o[k]
            arrays[pre + "poor_high"] = np.int8(1 if o["poor_high"] else 0)
            arrays[pre + "poor_low"] = np.int8(1 if o["poor_low"] else 0)
            rows.append([asset, trade_date.isoformat(), trade_date.year, scope,
                         int(sel.sum()), o["total_volume"], o["n_bins"],
                         o["poc_tick"] * tick_px if o["poc_tick"] >= 0 else None,
                         o["vah_tick"] * tick_px if o["vah_tick"] >= 0 else None,
                         o["val_tick"] * tick_px if o["val_tick"] >= 0 else None,
                         int(o["hvn_ticks"].size), int(o["lvn_ticks"].size),
                         int(o["single_print_ticks"].size),
                         o["poor_high"], o["poor_low"]])
        # ---- developing (causal) POC/VA, session scope, every 5 min
        dsec, dpoc, dvah, dval = [], [], [], []
        if tsec.size:
            last = int(tsec[-1])
            grid = np.arange(DEV_INTERVAL, last + DEV_INTERVAL, DEV_INTERVAL,
                             dtype=np.int64)
            cuts = np.searchsorted(tsec, grid, side="right")
            for gi, cut in zip(grid.tolist(), cuts.tolist()):
                if cut < 2:
                    continue
                b0, raw = build_profile(tick[:cut], tsz[:cut])
                if raw.sum() == 0:
                    continue
                sm = smooth(raw)
                p = poc_index(sm)
                lo, hi = value_area(sm, p)
                dsec.append(gi)
                dpoc.append(b0 + p)
                dvah.append(b0 + hi)
                dval.append(b0 + lo)
        arrays["dev_sec"] = np.array(dsec, dtype=np.int32)
        arrays["dev_poc_tick"] = np.array(dpoc, dtype=np.int64)
        arrays["dev_vah_tick"] = np.array(dvah, dtype=np.int64)
        arrays["dev_val_tick"] = np.array(dval, dtype=np.int64)
        C.savez_det(M.out_path("profiles", asset,
                               "%s.npz" % trade_date.strftime("%Y%m%d")),
                    **arrays)
    return rows


COLUMNS = ["asset", "trade_date", "year", "scope", "n_trades", "total_volume",
           "n_bins", "poc_px", "vah_px", "val_px", "n_hvn", "n_lvn",
           "n_single_print", "poor_high", "poor_low"]


def load_profile(asset, trade_date):
    p = M.out_path("profiles", asset, "%s.npz" % trade_date.strftime("%Y%m%d"))
    if not os.path.exists(p):
        return None
    z = np.load(p, allow_pickle=False)
    d = {k: z[k] for k in z.files}
    z.close()
    return d


def run(assets, workers, months=None):
    tasks = []
    for asset in assets:
        by_month = {}
        for d, p in X.session_paths(asset, M.M0_ROOT):
            if months and X.month_key(d) not in months:
                continue
            by_month.setdefault(X.month_key(d), []).append((d, p))
        for mk in sorted(by_month):
            tasks.append((asset, mk, by_month[mk]))
    M.hb("b4 profiles: %d (asset,month) tasks" % len(tasks))
    if workers <= 1 or len(tasks) <= 1:
        res = [_shard(t) for t in tasks]
    else:
        with mp.Pool(min(workers, len(tasks))) as pool:
            res = list(pool.map(_shard, tasks, chunksize=1))
    rows = []
    for r in res:
        rows.extend(r)
    rows.sort(key=lambda r: (r[0], r[1], r[3]))
    M.write_tsv(M.out_path("profiles", "profile_objects.tsv"), SECTION,
                C.params_hash(PARAMS), COLUMNS, rows,
                extra=["one row per (asset, session, scope); the arrays live "
                       "in m1/profiles/{ASSET}/{YYYYMMDD}.npz"])
    M.hb("b4 profiles: %d object rows" % len(rows))
    return rows


def main():
    M.verify_spec()
    workers = int(os.environ.get("M1_WORKERS", "6"))
    assets = [a for a in sys.argv[1:] if a in M.ASSET_ORDER] or list(M.ASSET_ORDER)
    run(assets, workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/python3
"""PORT M0 s3_session_assemble (spec §5) — Globex sessions from the s2 substrate.

Pass 1 : dominance per session, session metadata, activity profile per (asset,
         year), session bars H/L/C -> phases_{ASSET}.json + bars_{ASSET}.tsv
Pass 2 : stitched session grids + phase tags + roll flags
         -> m0/sessions/{ASSET}/{trade_date}.npz + sessions_index_{ASSET}.tsv

Session = Globex trade date d = [17:00 America/Chicago on d-1, 16:00 on d),
converted to UTC per-date with zoneinfo (DST-correct), so a session spans two
UTC-day receipts and is 82800 seconds long.
"""
import datetime as dt
import json
import math
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

CT = ZoneInfo("America/Chicago")
SESSION_SECONDS = 23 * 3600            # 17:00 -> 16:00 next day
BIN_SECONDS = 1800                     # half-hour UTC bins
N_BINS = 86400 // BIN_SECONDS          # 48
SEED_TOKYO_LONDON = 7 * 3600           # 07:00 UTC
SEED_LONDON_NY = 13 * 3600             # 13:00 UTC
SEARCH_RADIUS = 2 * 3600               # +/- 2h
PHASE_NAMES = ("TOKYO", "LONDON", "NY")

PARAMS = {
    "spec_section": "§5 s3_session_assemble",
    "session": "[17:00 America/Chicago d-1, 16:00 d) via zoneinfo",
    "session_seconds": SESSION_SECONDS,
    "bin_seconds": BIN_SECONDS,
    "profile_smoothing": "centered 3-bin moving average, cyclic over the 48 UTC bins",
    "seeds_utc_sec": {"TOKYO|LONDON": SEED_TOKYO_LONDON,
                      "LONDON|NY": SEED_LONDON_NY,
                      "NY|TOKYO": "modal session close hour of the year "
                                  "(= the maintenance break)"},
    "boundary_search": "local minimum of the smoothed profile nearest the seed "
                       "within +/-2h; leftmost on ties; argmin fallback",
    "min_bar_seconds": 100,
    "roll_window_sessions": 5,
    "whipsaw_window_sessions": 10,
    "atr": "Wilder 14, seed = SMA of first 14 TRs, C_prev dropped on instrument "
           "change or on a gap in the asset's trading-day calendar",
    "short_day_hours": 20,
    "tie_break": "higher session updates, then lower instrument_id",
}


# ------------------------------------------------------------ receipt cache --
class DayCache:
    """Keeps the last few s2 day receipts open (sessions walk forward)."""

    def __init__(self, asset, limit=3):
        self.asset = asset
        self.dir = os.path.join(C.OUT_ROOT, "receipts", asset)
        self.limit = limit
        self.order = []
        self.cache = {}

    def get(self, date):
        key = date.isoformat()
        if key in self.cache:
            return self.cache[key]
        path = os.path.join(self.dir, date.strftime("%Y%m%d") + ".npz")
        obj = None
        if os.path.exists(path):
            z = np.load(path, allow_pickle=False)
            obj = {k: z[k] for k in z.files}
            obj["meta"] = json.loads(str(obj["meta_json"]))
            z.close()
        self.cache[key] = obj
        self.order.append(key)
        while len(self.order) > self.limit:
            self.cache.pop(self.order.pop(0), None)
        return obj

    def dates(self):
        if not os.path.isdir(self.dir):
            return []
        out = []
        for n in sorted(os.listdir(self.dir)):
            if n.endswith(".npz"):
                out.append(dt.date(int(n[0:4]), int(n[4:6]), int(n[6:8])))
        return out


def session_bounds(trade_date):
    """(open_utc_epoch, close_utc_epoch) for a Globex trade date."""
    o = dt.datetime.combine(trade_date - dt.timedelta(days=1),
                            dt.time(17, 0), tzinfo=CT)
    c = dt.datetime.combine(trade_date, dt.time(16, 0), tzinfo=CT)
    return int(o.timestamp()), int(c.timestamp())


def _row_index(ids, iid):
    w = np.nonzero(ids == iid)[0]
    return int(w[0]) if len(w) else None


def stitch(cache, trade_date, iid, keys):
    """Session-second views of the requested per-instrument arrays.

    PRE_FIRST seconds at the UTC-day boundary are filled from the earlier
    receipt's end-of-day carry for the same instrument (§5).
    """
    o, c = session_bounds(trade_date)
    n = c - o
    out = {k: None for k in keys}
    parts = {k: [] for k in keys}
    got_any = False
    t = o
    while t < c:
        day = t // 86400
        d = C.day_to_date(day)
        end = min(c, (day + 1) * 86400)
        lo, hi = t % 86400, (end - 1) % 86400 + 1
        rec = cache.get(d)
        if rec is None:
            for k in keys:
                parts[k].append(_blank(k, hi - lo))
        else:
            i = _row_index(rec["tracked_ids"], iid)
            if i is None:
                for k in keys:
                    parts[k].append(_blank(k, hi - lo))
            else:
                got_any = True
                seg = {k: rec[k][i][lo:hi].copy() for k in keys}
                # boundary PRE_FIRST fill from the previous day's carry
                st = seg.get("state")
                if st is not None and len(st) and st[0] == C.ST_PRE_FIRST:
                    prev = cache.get(d - dt.timedelta(days=1))
                    if prev is not None:
                        j = _row_index(prev["carry_iid"], iid)
                        if j is not None and prev["carry_state"][j] != C.ST_PRE_FIRST:
                            m = int(np.argmax(st != C.ST_PRE_FIRST)) if (
                                st != C.ST_PRE_FIRST).any() else len(st)
                            fill = {"bid_px": prev["carry_bid"][j],
                                    "ask_px": prev["carry_ask"][j],
                                    "bid_sz": prev["carry_bsz"][j],
                                    "ask_sz": prev["carry_asz"][j],
                                    "state": prev["carry_state"][j],
                                    "upd_count": 0}
                            for k in keys:
                                if k in fill:
                                    seg[k][:m] = fill[k]
                for k in keys:
                    parts[k].append(seg[k])
        t = end
    for k in keys:
        out[k] = np.concatenate(parts[k])[:n]
    return out, got_any


def _blank(key, n):
    if key in ("bid_px", "ask_px"):
        return np.full(n, C.UNDEF_PRICE, dtype=np.int64)
    if key in ("bid_sz", "ask_sz"):
        return np.zeros(n, dtype=np.int64)
    if key == "state":
        return np.full(n, C.ST_PRE_FIRST, dtype=np.int8)
    return np.zeros(n, dtype=np.int32)


def session_trades(cache, trade_date, iid):
    o, c = session_bounds(trade_date)
    secs, pxs, szs, sides = [], [], [], []
    t = o
    while t < c:
        day = t // 86400
        d = C.day_to_date(day)
        end = min(c, (day + 1) * 86400)
        rec = cache.get(d)
        if rec is not None and len(rec["trades_iid"]):
            lo, hi = t % 86400, (end - 1) % 86400 + 1
            sel = ((rec["trades_iid"] == iid) & (rec["trades_sec"] >= lo)
                   & (rec["trades_sec"] < hi))
            if sel.any():
                secs.append(rec["trades_sec"][sel] + (day * 86400 - o))
                pxs.append(rec["trades_px"][sel])
                szs.append(rec["trades_size"][sel])
                sides.append(rec["trades_side"][sel])
        t = end
    if not secs:
        return (np.zeros(0, np.int64),) * 3 + (np.zeros(0, np.uint8),)
    return (np.concatenate(secs), np.concatenate(pxs), np.concatenate(szs),
            np.concatenate(sides))


# --------------------------------------------------------------- dominance --
def candidates(cache, trade_date):
    """Instrument ids tracked by either UTC-day receipt of this session."""
    o, c = session_bounds(trade_date)
    ids, syms, outr = set(), {}, {}
    for day in sorted({o // 86400, (c - 1) // 86400}):
        rec = cache.get(C.day_to_date(day))
        if rec is None:
            continue
        for iid in rec["tracked_ids"].tolist():
            ids.add(int(iid))
        for iid, s, ou in zip(rec["map_iid"].tolist(),
                              rec["map_symbol"].tolist(),
                              rec["map_outright"].tolist()):
            syms.setdefault(int(iid), str(s))
            outr.setdefault(int(iid), bool(ou))
    return sorted(ids), syms, outr


def dominance(cache, trade_date, ids, outr, rule):
    """Session-scoped metric per instrument, and the winner (all / outrights)."""
    metric = {}
    for iid in ids:
        if rule in ("R1", "R2"):
            g, _ = stitch(cache, trade_date, iid, ["upd_count"])
            metric[iid] = int(g["upd_count"].sum())
        else:
            _, _, szs, _ = session_trades(cache, trade_date, iid)[0:4]
            metric[iid] = int(szs.sum())
    def pick(pool):
        pool = [i for i in pool if metric.get(i, 0) > 0]
        if not pool:
            return None, None, 0.0
        best = max(metric[i] for i in pool)
        win = min(i for i in pool if metric[i] == best)
        rest = [i for i in pool if i != win]
        run = (min(rest, key=lambda i: (-metric[i], i)) if rest else None)
        tot = sum(metric[i] for i in pool)
        return win, run, (best / tot if tot else 0.0)
    all_win, all_run, all_share = pick(ids)
    o_win, o_run, o_share = pick([i for i in ids if outr.get(i, False)])
    return metric, (all_win, all_run, all_share), (o_win, o_run, o_share)


# ------------------------------------------------------------------ phases --
def smooth_cyclic(p):
    return (np.roll(p, 1) + p + np.roll(p, -1)) / 3.0


def find_boundary(prof, seed_sec):
    """Local minimum of the smoothed profile nearest the seed within +/-2h."""
    seed_bin = int(seed_sec // BIN_SECONDS) % N_BINS
    r = SEARCH_RADIUS // BIN_SECONDS
    window = [(seed_bin + k) % N_BINS for k in range(-r, r + 1)]
    local = [b for b in window
             if prof[b] <= prof[(b - 1) % N_BINS] and prof[b] <= prof[(b + 1) % N_BINS]]
    if local:
        # nearest to the seed; leftmost (smallest cyclic offset, then lower bin)
        best = min(local, key=lambda b: (min((b - seed_bin) % N_BINS,
                                             (seed_bin - b) % N_BINS), b))
    else:
        best = min(window, key=lambda b: (prof[b], b))
    return int(best) * BIN_SECONDS, bool(local)


def phase_of(sec_of_day, bounds):
    """bounds = (tokyo_london, london_ny, ny_tokyo) in UTC seconds; cyclic."""
    tl, ln, nt = bounds
    if _in_cyclic(sec_of_day, nt, tl):
        return 0                                  # TOKYO
    if _in_cyclic(sec_of_day, tl, ln):
        return 1                                  # LONDON
    return 2                                      # NY


def _in_cyclic(x, lo, hi):
    if lo <= hi:
        return lo <= x < hi
    return x >= lo or x < hi


# -------------------------------------------------------------------- bars --
def wilder_atr(trs, period=14):
    """Wilder ATR: seed = SMA of the first `period` TRs, then recursive."""
    out = [float("nan")] * len(trs)
    if len(trs) < period:
        return out
    seed = sum(trs[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(trs)):
        prev = (prev * (period - 1) + trs[i]) / period
        out[i] = prev
    return out


# ------------------------------------------------------------------- main ---
def load_rule():
    p = os.path.join(C.OUT_ROOT, "repro_si2024.receipt.json")
    with open(p) as fh:
        r = json.load(fh)
    if r.get("verdict") != "MATCH":
        raise RuntimeError("s1 did not MATCH; §5 cannot pin a dominance rule")
    return r["winning_rule"].split("/")[-1]


def run_asset(asset, rule):
    cache = DayCache(asset)
    dates = cache.dates()
    if not dates:
        raise RuntimeError("no s2 receipts for %s" % asset)
    C.hb("s3 %s: %d day receipts, pinned rule %s" % (asset, len(dates), rule))
    calendar = sorted(dates)
    cal_index = {d: i for i, d in enumerate(calendar)}

    # -------------------------------------------------- pass 1
    sess = []
    profiles = {}
    for n, td in enumerate(calendar, 1):
        ids, syms, outr = candidates(cache, td)
        if not ids:
            continue
        metric, (aw, ar, ash), (ow, orn, osh) = dominance(cache, td, ids, outr, rule)
        dom = ow if ow is not None else aw
        if dom is None:
            continue
        g, _ = stitch(cache, td, dom, ["bid_px", "ask_px", "state", "upd_count"])
        ts = g["state"] == C.ST_TWO_SIDED
        n_valid = int(ts.sum())
        if n_valid == 0:
            continue
        mids = ((g["bid_px"][ts].astype(np.float64)
                 + g["ask_px"][ts].astype(np.float64)) / 2 * C.ASSETS[asset]["px_scale"])
        idx = np.nonzero(ts)[0]
        o, c = session_bounds(td)
        rec = {
            "trade_date": td, "open_utc": o, "close_utc": c,
            "dominant_id": dom, "runner_up_id": (orn if ow is not None else ar),
            "dominant_share": (osh if ow is not None else ash),
            "dominant_all_id": aw, "dominant_all_share": ash,
            "dominant_outright_id": ow, "dominant_outright_share": osh,
            "n_instruments": len(ids),
            "n_valid_seconds": n_valid,
            "first_two_sided_sec": int(idx[0]), "last_two_sided_sec": int(idx[-1]),
            "H": float(mids.max()), "L": float(mids.min()), "Cl": float(mids[-1]),
            "symbol": syms.get(dom, ""),
        }
        span = rec["last_two_sided_sec"] - rec["first_two_sided_sec"]
        rec["short_day"] = bool(span < PARAMS["short_day_hours"] * 3600)
        sess.append(rec)

        # activity profile: updates per half-hour UTC bin, two-sided time only
        yr = td.year
        prof = profiles.setdefault(yr, [np.zeros(N_BINS), 0])
        secs_utc = (o + idx) % 86400
        np.add.at(prof[0], (secs_utc // BIN_SECONDS).astype(np.int64),
                  g["upd_count"][ts].astype(np.float64))
        prof[1] += 1
        if n % 100 == 0:
            C.hb("s3 %s pass1 %d/%d (%s)" % (asset, n, len(calendar), td))

    # -------------------------------------------------- roll flags
    for i, r in enumerate(sess):
        r["prev_session_dominant"] = sess[i - 1]["dominant_id"] if i else None
        r["instrument_change"] = bool(i and r["dominant_id"] != sess[i - 1]["dominant_id"])
    changes = [i for i, r in enumerate(sess) if r["instrument_change"]]
    W = PARAMS["roll_window_sessions"]
    for i, r in enumerate(sess):
        r["roll_window"] = any(abs(i - ci) <= W for ci in changes)
        r["dying_book_week"] = bool(asset == "NKD" and
                                    any(0 <= ci - i <= W for ci in changes))
        r["whipsaw_flag"] = False
    for ci in changes:
        a = sess[ci - 1]["dominant_id"] if ci else None
        b = sess[ci]["dominant_id"]
        for cj in changes:
            if 0 < cj - ci <= PARAMS["whipsaw_window_sessions"]:
                if sess[cj]["dominant_id"] == a and sess[cj - 1]["dominant_id"] == b:
                    for k in range(ci, cj + 1):
                        sess[k]["whipsaw_flag"] = True

    # -------------------------------------------------- phase table
    phases = {}
    for yr in sorted(profiles):
        raw, nses = profiles[yr]
        prof = raw / max(nses, 1)
        sm = smooth_cyclic(prof)
        close_hours = [((r["close_utc"] % 86400) // 3600) for r in sess
                       if r["trade_date"].year == yr]
        modal = (min(sorted(set(close_hours)), key=lambda h: (-close_hours.count(h), h))
                 if close_hours else 22)
        seeds = (SEED_TOKYO_LONDON, SEED_LONDON_NY, modal * 3600)
        b_tl, ok_tl = find_boundary(sm, seeds[0])
        b_ln, ok_ln = find_boundary(sm, seeds[1])
        b_nt, ok_nt = find_boundary(sm, seeds[2])
        phases[str(yr)] = {
            "n_sessions": nses,
            "profile_mean_updates_per_bin": [float(x) for x in prof],
            "profile_smoothed": [float(x) for x in sm],
            "seeds_utc_sec": {"TOKYO|LONDON": seeds[0], "LONDON|NY": seeds[1],
                              "NY|TOKYO": seeds[2]},
            "boundaries_utc_sec": {"TOKYO|LONDON": b_tl, "LONDON|NY": b_ln,
                                   "NY|TOKYO": b_nt},
            "local_minimum_found": {"TOKYO|LONDON": ok_tl, "LONDON|NY": ok_ln,
                                    "NY|TOKYO": ok_nt},
        }
    C.write_json(C.out_path("phases_%s.json" % asset),
                 {"spec_section": "§5 PHASE TABLES", "asset": asset,
                  "env": C.env_receipt(PARAMS), "phase_names": list(PHASE_NAMES),
                  "years": phases})

    # -------------------------------------------------- bars + ATR14
    bars = [r for r in sess if r["n_valid_seconds"] >= PARAMS["min_bar_seconds"]]
    trs = []
    rows = []
    for i, r in enumerate(bars):
        drop = True
        if i:
            p = bars[i - 1]
            same = (p["dominant_id"] == r["dominant_id"])
            contiguous = (cal_index.get(r["trade_date"], -1)
                          - cal_index.get(p["trade_date"], -99) == 1)
            drop = not (same and contiguous)
        tr = (r["H"] - r["L"]) if drop else max(
            r["H"] - r["L"], abs(r["H"] - bars[i - 1]["Cl"]),
            abs(r["L"] - bars[i - 1]["Cl"]))
        trs.append(tr)
        r["_tr"] = tr
        r["_cprev_dropped"] = drop
    atr = wilder_atr(trs)
    mult = C.ASSETS[asset]["mult"]
    for i, r in enumerate(bars):
        r["_atr"] = atr[i]
        r["_atr_prev"] = atr[i - 1] if i else float("nan")
        rows.append([r["trade_date"].isoformat(), r["dominant_id"], r["symbol"],
                     r["n_valid_seconds"], "%.9f" % r["H"], "%.9f" % r["L"],
                     "%.9f" % r["Cl"], "%.9f" % r["_tr"], "%.4f" % (r["_tr"] * mult),
                     ("" if not np.isfinite(r["_atr"]) else "%.9f" % r["_atr"]),
                     ("" if not np.isfinite(r["_atr"]) else "%.4f" % (r["_atr"] * mult)),
                     ("" if not np.isfinite(r["_atr_prev"]) else
                      "%.4f" % (r["_atr_prev"] * mult)),
                     int(r["_cprev_dropped"]), int(r["instrument_change"]),
                     int(r["short_day"])])
    C.write_tsv(C.out_path("bars_%s.tsv" % asset), "§1/§5 session bars + ATR14",
                C.params_hash(PARAMS),
                ["trade_date", "dominant_id", "symbol", "n_valid_seconds",
                 "H", "L", "C", "TR_px", "TR_usd", "ATR14_px", "ATR14_usd",
                 "ATR14_prev_usd", "cprev_dropped", "instrument_change",
                 "short_day"], rows)
    C.hb("s3 %s: %d sessions, %d bars, %d years of phases"
         % (asset, len(sess), len(bars), len(phases)))

    # -------------------------------------------------- pass 2: session receipts
    by_date = {r["trade_date"]: r for r in sess}
    index = []
    phase_luts = {}
    sdir = os.path.join(C.OUT_ROOT, "sessions", asset)
    os.makedirs(sdir, exist_ok=True)
    for n, r in enumerate(sess, 1):
        td = r["trade_date"]
        ph = phases[str(td.year)]["boundaries_utc_sec"]
        bounds = (ph["TOKYO|LONDON"], ph["LONDON|NY"], ph["NY|TOKYO"])
        keep = [r["dominant_id"]]
        if r["runner_up_id"] is not None and asset in ("HG", "NKD") and r["roll_window"]:
            keep.append(r["runner_up_id"])
        payload = {}
        for slot, iid in enumerate(keep):
            g, _ = stitch(cache, td, iid,
                          ["bid_px", "ask_px", "bid_sz", "ask_sz", "state", "upd_count"])
            ts = g["state"] == C.ST_TWO_SIDED
            mid = np.full(len(ts), np.nan)
            spr = np.full(len(ts), np.nan)
            b = g["bid_px"].astype(np.float64)
            a = g["ask_px"].astype(np.float64)
            px = C.ASSETS[asset]["px_scale"]
            mid[ts] = (b[ts] + a[ts]) / 2 * px
            spr[ts] = (a[ts] - b[ts]) * px * mult
            pre = "g%d_" % slot
            payload.update({pre + k: v for k, v in g.items()})
            payload[pre + "mid"] = mid
            payload[pre + "spread_usd"] = spr
            payload[pre + "iid"] = np.int64(iid)
        tsec, tpx, tsz, tside = session_trades(cache, td, r["dominant_id"])
        lut = phase_luts.get(bounds)
        if lut is None:
            lut = phase_luts[bounds] = np.array(
                [phase_of(s, bounds) for s in range(86400)], dtype=np.int8)
        secs_utc = (r["open_utc"] + np.arange(SESSION_SECONDS, dtype=np.int64)) % 86400
        tag = lut[secs_utc]
        meta = {k: (v.isoformat() if isinstance(v, dt.date) else v)
                for k, v in r.items() if not k.startswith("_")}
        meta.update({"asset": asset, "grid_slots": [int(x) for x in keep],
                     "phase_names": list(PHASE_NAMES),
                     "phase_boundaries_utc_sec": bounds,
                     "TR_px": r.get("_tr"), "ATR14_prev_px": r.get("_atr_prev"),
                     "params_hash": C.params_hash(PARAMS)})
        payload.update({
            "phase_tag": tag,
            "trades_sec": tsec, "trades_px": tpx, "trades_size": tsz,
            "trades_side": tside,
            "meta_json": np.array(json.dumps(meta, sort_keys=True,
                                             default=lambda o: None)),
        })
        p = os.path.join(sdir, "%s.npz" % td.strftime("%Y%m%d"))
        C.savez_det(p, **payload)
        index.append((td.isoformat(), r["dominant_id"], r["n_valid_seconds"],
                      int(r["instrument_change"]), int(r["roll_window"]),
                      int(r["whipsaw_flag"]), int(r["dying_book_week"]),
                      p, C.sha256_file(p)))
        if n % 100 == 0:
            C.hb("s3 %s pass2 %d/%d (%s)" % (asset, n, len(sess), td))
    C.write_tsv(C.out_path("sessions_index_%s.tsv" % asset), "§5 session receipts",
                C.params_hash(PARAMS),
                ["trade_date", "dominant_id", "n_valid_seconds",
                 "instrument_change", "roll_window", "whipsaw_flag",
                 "dying_book_week", "path", "sha256"], sorted(index))
    C.hb("s3 %s: wrote %d session receipts" % (asset, len(index)))
    return len(index)


def main():
    C.verify_spec()
    rule = load_rule()
    assets = sys.argv[1:] or list(C.ASSET_ORDER)
    for a in assets:
        run_asset(a, rule)
    return 0


if __name__ == "__main__":
    sys.exit(main())

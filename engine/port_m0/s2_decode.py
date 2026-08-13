#!/usr/bin/python3
"""PORT M0 s2_decode_day (spec §4) — PROGRAM MODE decode.

Per (asset, UTC day) receipt m0/receipts/{ASSET}/{YYYYMMDD}.npz holding
1s book grids, trades, per-instrument daily tallies, mappings, end-of-day
carry and the integrity counters.

Receipt arrays (row order = sorted tracked instrument ids):
  tracked_ids  int64[n]
  bid_px, ask_px, bid_sz, ask_sz  int64[n, 86400]   (UNDEF_PRICE where the side
                                                     failed the §0 guard)
  state        int8 [n, 86400]    §4 codes, forward-filled, PRE_FIRST before the
                                  instrument's first record of the day
  upd_count    int32[n, 86400]    records per second (see NOTE below)
  trades_*     int64[m]           iid / sec / px / size, side uint8 (ASCII)
  tally_*      int64[k]           iid / updates / trades / trade_size_sum, ALL
                                  instruments incl. spreads (dominance needs it)
  map_iid int64[k] / map_symbol <U / map_outright bool
  carry_*                          end-of-day book state per tracked instrument
  meta_json    <U   counters + integrity results

NOTE (spec gap, reported by the lane): §5 needs SESSION-scoped dominance and a
per-half-hour-UTC activity profile, neither of which is recoverable from a
1s grid or a per-UTC-day tally.  `upd_count` is the strictly additive field that
makes §5 computable; it invents no numeric convention.
"""
import datetime as dt
import json
import math
import multiprocessing as mp
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

SECONDS = 86400
SI_TRACK_TOP = 3

PARAMS = {
    "spec_section": "§4 s2_decode_day",
    "sampling": "last record of the second carrying F_LAST, else last record of "
                "the second (counted in n_no_flast_seconds)",
    "state_codes": {"TWO_SIDED": 0, "NO_BID": 1, "NO_ASK": 2, "CROSSED": 3,
                    "EMPTY": 5, "PRE_FIRST": 6},
    "si_tracked": "top %d instruments by day update count" % SI_TRACK_TOP,
    "hg_nkd_tracked": "all instruments appearing in the day",
    "clock": "ts_event",
    "chunk_bytes": C.CHUNK,
}


# ---------------------------------------------------------------- grid core --
def _side_code(side):
    """databento_dbn.Side -> its ASCII code ('B'/'A'/'N'); 0 when absent."""
    s = str(side)
    return ord(s[0]) if s else 0


class DayAccum:
    """Accumulates one UTC day of records for one asset."""

    def __init__(self, asset, day):
        self.asset = asset
        self.day = day
        self.books = {}       # iid -> {sec: [bid, ask, bsz, asz, has_flast]}
        self.upd = {}         # iid -> {sec: n}
        self.tally = {}       # iid -> [updates, trades, trade_size_sum]
        self.trades = {}      # iid -> list[(sec, px, size, side)]
        self.n_records = 0
        self.n_dropped_sentinel = 0
        self.px_prev = {}     # iid -> [last_bid, last_ask]
        self.px_gcd = {}      # iid -> gcd of |successive valid price changes|

    def add(self, iid, sec, bid, ask, bsz, asz, flast, action, price, size, side):
        self.n_records += 1
        t = self.tally.get(iid)
        if t is None:
            t = self.tally[iid] = [0, 0, 0]
        t[0] += 1
        u = self.upd.get(iid)
        if u is None:
            u = self.upd[iid] = {}
        u[sec] = u.get(sec, 0) + 1

        state, b, a = C.classify_book(bid, ask)      # guard BEFORE arithmetic
        if state != C.ST_TWO_SIDED:
            self.n_dropped_sentinel += 1

        bk = self.books.get(iid)
        if bk is None:
            bk = self.books[iid] = {}
        cur = bk.get(sec)
        if cur is None or flast or not cur[4]:
            bk[sec] = [b, a, int(bsz), int(asz), bool(flast), state]

        # empirical tick: |successive valid price changes| per instrument
        pv = self.px_prev.get(iid)
        if pv is None:
            pv = self.px_prev[iid] = [None, None]
            self.px_gcd[iid] = 0
        g = self.px_gcd[iid]
        if b != C.UNDEF_PRICE:
            if pv[0] is not None and b != pv[0]:
                g = math.gcd(g, abs(b - pv[0]))
            pv[0] = b
        if a != C.UNDEF_PRICE:
            if pv[1] is not None and a != pv[1]:
                g = math.gcd(g, abs(a - pv[1]))
            pv[1] = a
        self.px_gcd[iid] = g

        if action == "T":
            t[1] += 1
            t[2] += int(size)
            if 0 < price < C.SENT_HI:
                self.trades.setdefault(iid, []).append(
                    (sec, int(price), int(size), _side_code(side)))


def add_record(acc, rec, sec):
    """Feed one Mbp1Msg into the accumulator (single extraction point, so the
    self-test exercises exactly the production path)."""
    lv0 = rec.levels[0]
    acc.add(rec.instrument_id, sec, lv0.bid_px, lv0.ask_px, lv0.bid_sz,
            lv0.ask_sz, bool(int(rec.flags) & C.F_LAST), rec.action, rec.price,
            rec.size, rec.side)


def build_grids(acc, tracked):
    """Forward-filled 1s grids for the tracked instruments.

    Returns (arrays dict, n_no_flast_seconds, per-instrument crossed-second
    counts).  Deterministic: seconds are processed in ascending order.
    """
    n = len(tracked)
    bid = np.full((n, SECONDS), C.UNDEF_PRICE, dtype=np.int64)
    ask = np.full((n, SECONDS), C.UNDEF_PRICE, dtype=np.int64)
    bsz = np.zeros((n, SECONDS), dtype=np.int64)
    asz = np.zeros((n, SECONDS), dtype=np.int64)
    state = np.full((n, SECONDS), C.ST_PRE_FIRST, dtype=np.int8)
    upd = np.zeros((n, SECONDS), dtype=np.int32)
    n_no_flast = 0
    crossed = []
    carry = []
    for i, iid in enumerate(tracked):
        u = acc.upd.get(iid, {})
        if u:
            us = np.fromiter(sorted(u), dtype=np.int64, count=len(u))
            uv = np.fromiter((u[s] for s in sorted(u)), dtype=np.int32, count=len(u))
            upd[i, us] = uv
        bk = acc.books.get(iid, {})
        if not bk:
            crossed.append(0)
            carry.append((C.UNDEF_PRICE, C.UNDEF_PRICE, 0, 0, C.ST_PRE_FIRST, -1))
            continue
        secs = sorted(bk)
        for s in secs:
            if not bk[s][4]:
                n_no_flast += 1
        vals = np.array([[bk[s][0], bk[s][1], bk[s][2], bk[s][3]] for s in secs],
                        dtype=np.int64)
        st = np.array([bk[s][5] for s in secs], dtype=np.int8)
        idx = np.array(secs, dtype=np.int64)
        reps = np.diff(np.append(idx, SECONDS))
        seg = np.repeat(np.arange(len(idx), dtype=np.int64), reps)
        first = int(idx[0])
        bid[i, first:] = vals[seg, 0]
        ask[i, first:] = vals[seg, 1]
        bsz[i, first:] = vals[seg, 2]
        asz[i, first:] = vals[seg, 3]
        state[i, first:] = st[seg]
        crossed.append(int((state[i] == C.ST_CROSSED).sum()))
        last = secs[-1]
        carry.append((int(bk[last][0]), int(bk[last][1]), int(bk[last][2]),
                      int(bk[last][3]), int(bk[last][5]), int(last)))
    arrays = {"bid_px": bid, "ask_px": ask, "bid_sz": bsz, "ask_sz": asz,
              "state": state, "upd_count": upd}
    return arrays, n_no_flast, crossed, carry


# ----------------------------------------------------------------- writer ---
def finish_day(asset, day, acc, inv, out_dir, flags):
    """Turn one DayAccum into a receipt.  Returns (date_iso, path, sha256)."""
    date = C.day_to_date(day)
    spec = C.ASSETS[asset]
    iids = sorted(acc.tally)
    if not iids:
        return None
    syms = {i: C.symbol_for(inv, i, date) for i in iids}
    outr = {i: C.is_outright(syms[i]) for i in iids}

    if asset == "SI":
        ranked = sorted(iids, key=lambda i: (-acc.tally[i][0], i))
        tracked = sorted(ranked[:SI_TRACK_TOP])
    else:
        tracked = iids
        if len(tracked) > 2:
            flags.append((asset, date.isoformat(), "MORE_THAN_2_INSTRUMENTS",
                          ";".join(str(i) for i in tracked)))

    arrays, n_no_flast, crossed, carry = build_grids(acc, tracked)

    # ---- integrity: empirical tick GCD over OUTRIGHT instruments only -------
    g = 0
    for i in iids:
        if outr[i]:
            g = math.gcd(g, acc.px_gcd.get(i, 0))
    tick_usd = g * spec["px_scale"] * spec["mult"] if g else 0.0
    tick_ok = bool(g and abs(tick_usd - spec["tick_usd"]) < 1e-9)
    if not tick_ok:
        flags.append((asset, date.isoformat(), "TICK_GCD_MISMATCH",
                      "gcd=%d tick_$=%.6f expected=%.2f" % (g, tick_usd,
                                                            spec["tick_usd"])))

    # ---- integrity: sane-band on the daily median mid ----------------------
    top = max(range(len(tracked)),
              key=lambda k: (acc.tally[tracked[k]][0], -tracked[k])) if tracked else None
    med_mid = float("nan")
    if top is not None:
        sel = arrays["state"][top] == C.ST_TWO_SIDED
        if sel.any():
            mids = (arrays["bid_px"][top][sel].astype(np.float64)
                    + arrays["ask_px"][top][sel].astype(np.float64)) / 2 * spec["px_scale"]
            med_mid = float(np.median(mids))
    lo, hi = spec["band"]
    band_ok = bool(np.isfinite(med_mid) and lo <= med_mid <= hi)
    if not band_ok:
        flags.append((asset, date.isoformat(), "MID_OUT_OF_BAND",
                      "median_mid=%.6f band=%s" % (med_mid, spec["band"])))

    # ---- trades ------------------------------------------------------------
    tr_iid, tr_sec, tr_px, tr_sz, tr_side = [], [], [], [], []
    for i in tracked:
        for (s, p, z, sd) in acc.trades.get(i, ()):
            tr_iid.append(i); tr_sec.append(s); tr_px.append(p)
            tr_sz.append(z); tr_side.append(sd)

    meta = {
        "asset": asset, "date": date.isoformat(), "utc_day": int(day),
        "n_records": acc.n_records,
        "n_dropped_sentinel": acc.n_dropped_sentinel,
        "n_no_flast_seconds": n_no_flast,
        "n_crossed_seconds": {str(tracked[k]): crossed[k] for k in range(len(tracked))},
        "tick_gcd_raw": int(g), "tick_usd_empirical": tick_usd,
        "tick_usd_expected": spec["tick_usd"], "tick_ok": tick_ok,
        "median_mid": med_mid, "band_ok": band_ok,
        "tracked_ids": [int(x) for x in tracked],
        "n_instruments": len(iids),
        "params_hash": C.params_hash(PARAMS),
    }
    payload = dict(arrays)
    payload.update({
        "tracked_ids": np.array(tracked, dtype=np.int64),
        "trades_iid": np.array(tr_iid, dtype=np.int64),
        "trades_sec": np.array(tr_sec, dtype=np.int64),
        "trades_px": np.array(tr_px, dtype=np.int64),
        "trades_size": np.array(tr_sz, dtype=np.int64),
        "trades_side": np.array(tr_side, dtype=np.uint8),
        "tally_iid": np.array(iids, dtype=np.int64),
        "tally_updates": np.array([acc.tally[i][0] for i in iids], dtype=np.int64),
        "tally_trades": np.array([acc.tally[i][1] for i in iids], dtype=np.int64),
        "tally_trade_size_sum": np.array([acc.tally[i][2] for i in iids], dtype=np.int64),
        "map_iid": np.array(iids, dtype=np.int64),
        "map_symbol": np.array([syms[i] for i in iids], dtype="U32"),
        "map_outright": np.array([outr[i] for i in iids], dtype=bool),
        "carry_iid": np.array(tracked, dtype=np.int64),
        "carry_bid": np.array([c[0] for c in carry], dtype=np.int64),
        "carry_ask": np.array([c[1] for c in carry], dtype=np.int64),
        "carry_bsz": np.array([c[2] for c in carry], dtype=np.int64),
        "carry_asz": np.array([c[3] for c in carry], dtype=np.int64),
        "carry_state": np.array([c[4] for c in carry], dtype=np.int8),
        "carry_last_sec": np.array([c[5] for c in carry], dtype=np.int64),
        "meta_json": np.array(json.dumps(meta, sort_keys=True)),
    })
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "%s.npz" % date.strftime("%Y%m%d"))
    C.savez_det(path, **payload)
    return date.isoformat(), path, C.sha256_file(path)


# ------------------------------------------------------------------ driver --
def _emit(asset, day, acc, inv, out_dir, flags, only):
    """Write the day receipt unless a `only` date filter excludes it."""
    if only is not None and C.day_to_date(day).isoformat() not in only:
        return None
    return finish_day(asset, day, acc, inv, out_dir, flags)


def process_file(args):
    """Decode one payload file into per-UTC-day receipts.

    Records whose ts_event UTC date falls OUTSIDE the source file's declared
    date range (leading SNAPSHOT/BAD_TS_RECV records carry a stale ts_event)
    are counted in n_foreign_day_records and logged, never written: writing them
    would either produce a partial receipt for a day owned by another file, or
    silently overwrite that file's receipt.
    """
    asset, path, out_dir, only_dates, chunk = args
    d0, d1 = C.file_date_range(path)
    day0, day1 = C.date_to_day(d0), C.date_to_day(d1)
    only = set(only_dates) if only_dates else None
    inv = {}
    acc = None
    cur_day = None
    flags = []
    index = []
    n_foreign = 0
    t0 = time.time()
    n_rec = 0
    for rec in C.iter_dbn(path, chunk=chunk):
        if isinstance(rec, C.databento_dbn.Metadata):
            inv = C.invert_mappings(rec)
            continue
        lv = getattr(rec, "levels", None)
        if not lv:
            continue
        n_rec += 1
        ts = rec.ts_event // 1_000_000_000
        day = ts // 86400
        if day < day0 or day > day1:
            n_foreign += 1
            continue
        if acc is None:
            acc = DayAccum(asset, day)
            cur_day = day
        elif day > cur_day:
            # the stream has passed this day's end: write it, then start the next
            r = _emit(asset, cur_day, acc, inv, out_dir, flags, only)
            if r:
                index.append(r)
            acc = DayAccum(asset, day)
            cur_day = day
        elif day < cur_day:
            # ts_event went backwards across a day boundary: the day is already
            # written, so the record cannot be folded in.  Log and drop.
            flags.append((asset, C.day_to_date(day).isoformat(),
                          "OUT_OF_ORDER_DAY_RECORD_DROPPED",
                          os.path.basename(path)))
            continue
        add_record(acc, rec, int(ts % 86400))
    if acc is not None:
        r = _emit(asset, cur_day, acc, inv, out_dir, flags, only)
        if r:
            index.append(r)
    if n_foreign:
        flags.append((asset, "%s..%s" % (d0.isoformat(), d1.isoformat()),
                      "FOREIGN_DAY_RECORDS_DROPPED",
                      "%d in %s" % (n_foreign, os.path.basename(path))))
    C.hb("s2 %s %s: %d recs, %d days, %.0fs"
         % (asset, os.path.basename(path), n_rec, len(index), time.time() - t0))
    return {"file": os.path.basename(path), "n_records": n_rec,
            "n_foreign": n_foreign, "index": index, "flags": flags}


def run_asset(asset, workers, only_dates=None, out_dir=None, chunk=C.CHUNK,
              write_index=True, files=None):
    spec = C.ASSETS[asset]
    if files is None:
        files = (C.si_daily_files() if spec["layout"] == "daily"
                 else C.yearly_files(asset))
    out_dir = out_dir or C.out_path("receipts", asset, "_")[:-2]
    os.makedirs(out_dir, exist_ok=True)
    tasks = [(asset, p, out_dir, only_dates, chunk) for p in files]
    C.hb("s2 %s: %d files, %d workers -> %s" % (asset, len(files), workers, out_dir))
    results = []
    if workers <= 1:
        for t in tasks:
            results.append(process_file(t))
    else:
        with mp.Pool(workers) as pool:
            for r in pool.imap_unordered(process_file, tasks, chunksize=1):
                results.append(r)
    results.sort(key=lambda r: r["file"])
    index = sorted((row for r in results for row in r["index"]))
    flags = sorted((f for r in results for f in r["flags"]))
    if write_index:
        C.write_tsv(C.out_path("receipts_index_%s.tsv" % asset), "§4 s2_decode_day",
                    C.params_hash(PARAMS), ["date", "path", "sha256"], index)
    C.hb("s2 %s: %d day receipts, %d integrity flags"
         % (asset, len(index), len(flags)))
    return index, flags


def write_flags(all_flags):
    rows = sorted(set(all_flags))
    C.write_tsv(C.out_path("integrity_flags.tsv"), "§4 integrity",
                C.params_hash(PARAMS), ["asset", "date", "flag", "detail"], rows)
    return len(rows)


def main():
    C.verify_spec()
    asset = sys.argv[1]
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    _, flags = run_asset(asset, workers)
    write_flags(flags)
    return 0


if __name__ == "__main__":
    sys.exit(main())

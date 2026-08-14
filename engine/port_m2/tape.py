#!/usr/bin/python3
"""PORT M2 — MBP-1 EVENT extraction for the S6 raw ribbon (spec §1 S6, D-049).

The M0/M1 substrate persists 1-SECOND grids (g0_* + a per-trade list); the
per-event quote stream — the port's actual information edge (D-043/D-056) — was
never persisted, because no earlier stage needed it.  S6 does.  This module is
the only place in M2 that opens a raw payload file.

Design
  * one canonical extraction window per candidate, so two runs produce
    byte-identical caches as well as byte-identical sheets;
  * the cache lives under artifacts/cache/port/m2/events/ (D-018);
  * the m0 seal guard, decode loop and dominance convention are reused
    verbatim — this module invents no new tape convention;
  * events are filtered to the SESSION-DOMINANT instrument (m0 slot 0), which
    is what makes "never compute across an instrument change" true here too.

Clock: ts_event, exactly as m0 s2_decode (§4 "clock: ts_event").
"""
import bisect
import hashlib
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import common as C                        # noqa: E402  m0 substrate
import databento_dbn                      # noqa: E402

EVENTS_DIR = os.path.join(MC.M2_ROOT, "events")

# §1 S6: "the final 90s before decision" raw + "the preceding 10min" digested.
RIBBON_RAW_SEC = 90
RIBBON_DIGEST_SEC = 600
# Extraction pads one extra second on each end so the pre-trade quote of the
# first in-window event and the decision second's own book are both present.
EXTRACT_PAD_SEC = 2

ARRAYS = ("ts_ns", "action", "side", "price", "size", "flags", "sequence",
          "bid_px", "ask_px", "bid_sz", "ask_sz", "bid_ct", "ask_ct")

ACT_ORDER = "ACFMRTN"                     # render order for digests, fixed


# ------------------------------------------------------- the definition key --
# R91: `ensure` declared a HIT on three tests only — the files exist, `iid`
# matches, and the stored `cover` contains the wanted ranges.  The meta carried
# `m2_spec_sha16` and NOTHING COMPARED IT (`event_cache` deliberately strips it
# as "a provenance stamp, not data"), so any change to the extraction
# DEFINITION that did not widen the canonical window left the whole 12 GB corpus
# a silent HIT and only `--force` re-extracted.  The cache is now keyed on the
# definition itself: change any of these and every cached session becomes a MISS
# on its own, without anyone having to remember to pass a flag.
#
# What belongs here is everything that changes WHAT A CACHED FILE CONTAINS: the
# column set and its dtypes, the instrument filter, the record predicate, the
# clock, the sort key, and the window padding that the cover is measured in.
DEF_PARAMS = {
    "arrays": list(ARRAYS),
    "dtypes": ["int64", "uint8", "uint8", "int64", "int64", "uint8", "int64",
               "int64", "int64", "int64", "int64", "int64", "int64"],
    "clock": "ts_event",
    "instrument_filter": "rec.instrument_id == iid (m0 slot-0 session dominant)",
    "record_predicate": "lo_ns <= ts_event < hi_ns AND ts_event//1e9 inside one "
                        "of the merged session-second ranges",
    "stop_rule": "break on the first record with ts_event >= max(hi)+3600s",
    "sort": "np.lexsort((sequence, ts_ns))",
    "pad_sec": EXTRACT_PAD_SEC,
    "ribbon_raw_sec": RIBBON_RAW_SEC,
    "ribbon_digest_sec": RIBBON_DIGEST_SEC,
    "cover_units": "SESSION SECONDS relative to meta['open_utc']",
    "version": 1,
}


def _def_sha16():
    blob = json.dumps(DEF_PARAMS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


DEF_SHA16 = _def_sha16()


# ------------------------------------------------------------------ files ---
def session_payload_files(asset, trade_date, open_utc, close_utc):
    """Payload files covering [open_utc, close_utc).  Sealed files are excluded
    by C.payload_files; a sealed session never reaches here (era_of refuses)."""
    import datetime as dt
    lo = dt.datetime.utcfromtimestamp(open_utc).date()
    hi = dt.datetime.utcfromtimestamp(close_utc - 1).date()
    out = []
    for p in C.payload_files(asset):
        if ".trades." in os.path.basename(p):
            continue
        d0, d1 = C.file_date_range(p)
        if d1 < lo or d0 > hi:
            continue
        out.append(p)
    return sorted(out)


# ------------------------------------------------------------- extraction ---
def _merge(ranges):
    """Merge session-second ranges.  An INVERTED or EMPTY range is dropped.

    Found by the builds lane: a caller that clamped a window at the session
    open handed `_merge` a `hi < lo` pair and it was written straight into the
    cache's `cover` metadata as `[0, -685]` — a cover entry that can never be
    satisfied and silently poisons every later `_covers` test for that session.
    A range that covers nothing is not a cover.
    """
    out = []
    for lo, hi in sorted((int(a), int(b)) for a, b in ranges):
        if hi <= lo:
            continue
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return [(int(a), int(b)) for a, b in out]


def _covers(cover, lo, hi):
    for a, b in cover:
        if a <= lo and hi <= b:
            return True
    return False


def _paths(asset, d8):
    base = os.path.join(EVENTS_DIR, asset)
    return (os.path.join(base, "%08d.npz" % d8),
            os.path.join(base, "%08d.json" % d8))


def extract(asset, trade_date, iid, open_utc, close_utc, ranges):
    """Decode the covering payload files once and keep every dominant-instrument
    record whose ts_event second lies in one of the session-second `ranges`."""
    cover = _merge(ranges)
    keep_lo = [open_utc + a for a, b in cover]
    keep_hi = [open_utc + b for a, b in cover]
    n_r = len(cover)
    lo_ns = min(keep_lo) * 1_000_000_000
    hi_ns = max(keep_hi) * 1_000_000_000
    cols = {k: [] for k in ARRAYS}
    # `n_seen` counts the records KEPT, so it equals `n_events` by construction.
    # Review 3.2 MINOR: the manifest carries the two as distinct columns while
    # they are the same number.  The counter is left as-is deliberately — it is
    # meta, not data, and changing it would make freshly extracted sessions
    # disagree with the 3,341 already on disk for no informational gain.  Both
    # the manifest and the coverage report now say so instead of implying two
    # measurements exist.
    n_seen = 0
    # Records are time-ordered within a payload file, so the scan can stop once
    # it is past the last requested window.  The slack absorbs the leading
    # SNAPSHOT records whose ts_event is stale (m0 s2_decode documents them);
    # those are stale EARLY, never late, so an hour of slack is generous.
    # REVIEW 3.2 MINOR, recorded: the break test runs BEFORE the instrument
    # filter, and ts_event is not globally monotone ACROSS instruments, so in
    # principle a foreign record could stop the scan early.  The 3,600s slack is
    # what makes that safe: a foreign record must lead our instrument's
    # remaining wanted records by more than an hour to truncate them, which no
    # observed session does.  The safety is the SLACK, not the ordering; stated
    # here because it was an unwritten assumption.
    stop_ns = hi_ns + 3600 * 1_000_000_000
    for p in session_payload_files(asset, trade_date, open_utc, close_utc):
        for rec in C.iter_dbn(p):
            if isinstance(rec, databento_dbn.Metadata):
                continue
            t = rec.ts_event
            if t >= stop_ns:
                break
            if rec.instrument_id != iid:
                continue
            if t < lo_ns or t >= hi_ns:
                continue
            ts = t // 1_000_000_000
            ok = False
            for i in range(n_r):
                if keep_lo[i] <= ts < keep_hi[i]:
                    ok = True
                    break
            if not ok:
                continue
            n_seen += 1
            cols["ts_ns"].append(int(t))
            cols["action"].append(ord(str(rec.action)[0]))
            cols["side"].append(ord(str(rec.side)[0]))
            cols["price"].append(int(rec.price))
            cols["size"].append(int(rec.size))
            cols["flags"].append(int(rec.flags))
            cols["sequence"].append(int(rec.sequence))
            cols["bid_px"].append(int(rec.bid_px_00))
            cols["ask_px"].append(int(rec.ask_px_00))
            cols["bid_sz"].append(int(rec.bid_sz_00))
            cols["ask_sz"].append(int(rec.ask_sz_00))
            cols["bid_ct"].append(int(rec.bid_ct_00))
            cols["ask_ct"].append(int(rec.ask_ct_00))
    dt_map = {"ts_ns": np.int64, "action": np.uint8, "side": np.uint8,
              "price": np.int64, "size": np.int64, "flags": np.uint8,
              "sequence": np.int64, "bid_px": np.int64, "ask_px": np.int64,
              "bid_sz": np.int64, "ask_sz": np.int64, "bid_ct": np.int64,
              "ask_ct": np.int64}
    arrays = {k: np.array(cols[k], dtype=dt_map[k]) for k in ARRAYS}
    # ts_event is not globally monotone across instruments, but within one
    # instrument the stream is ordered; sort defensively on (ts, sequence) so
    # the ribbon's order is a property of the data, not of the file layout.
    order = np.lexsort((arrays["sequence"], arrays["ts_ns"]))
    if not np.array_equal(order, np.arange(order.size)):
        for k in ARRAYS:
            arrays[k] = arrays[k][order]
        n_reordered = 1
    else:
        n_reordered = 0
    return arrays, cover, n_seen, n_reordered


def cache_hit(meta, iid, open_utc, close_utc, want):
    """Is this cached meta usable for this request?  Five tests, not three.

    R91 adds the DEFINITION test.  R92 adds the WINDOW ORIGIN test: `cover` is
    stored in SESSION SECONDS relative to `open_utc` and `meta["open_utc"]` was
    written at extraction and then never compared, while `batch5_census._pack`
    takes `open_utc` from the LIVE receipt and slices the cached `ts_ns` with
    it.  If m0 ever re-derives a session's open, every c2f / erosion /
    through-book number silently comes from the wrong window with no error.
    """
    if meta.get("iid") != int(iid):
        return False, "iid"
    if meta.get("def_sha16") != DEF_SHA16:
        return False, "definition"
    if int(meta.get("open_utc", -1)) != int(open_utc):
        return False, "open_utc"
    if int(meta.get("close_utc", -1)) != int(close_utc):
        return False, "close_utc"
    cover = [(int(a), int(b)) for a, b in meta["cover"]]
    if not all(_covers(cover, a, b) for a, b in want):
        return False, "cover"
    return True, "hit"


def ensure(asset, trade_date, iid, open_utc, close_utc, ranges):
    """Return (arrays, meta), building/extending the cache when needed."""
    d8 = MC.d8(trade_date)
    npz_p, json_p = _paths(asset, d8)
    want = _merge(ranges)
    if os.path.exists(npz_p) and os.path.exists(json_p):
        with open(json_p) as fh:
            meta = json.load(fh)
        ok, _why = cache_hit(meta, iid, open_utc, close_utc, want)
        if ok:
            z = np.load(npz_p, allow_pickle=False)
            arrays = {k: z[k] for k in ARRAYS}
            z.close()
            return arrays, meta
        if int(meta.get("open_utc", -1)) == int(open_utc):
            # Only extend a cover that is measured from the SAME origin; a
            # different open_utc makes the stored session seconds meaningless.
            want = _merge([(int(a), int(b)) for a, b in meta["cover"]] + want)
    arrays, cover, n_seen, n_reord = extract(asset, trade_date, iid, open_utc,
                                             close_utc, want)
    meta = {"asset": asset, "trade_date": trade_date.isoformat(), "d8": d8,
            "iid": int(iid), "open_utc": int(open_utc),
            "close_utc": int(close_utc), "cover": [list(c) for c in cover],
            "n_events": int(arrays["ts_ns"].size), "n_seen": int(n_seen),
            "n_reordered": int(n_reord),
            "clock": "ts_event", "def_sha16": DEF_SHA16,
            "m2_spec_sha16": MC.SPEC_SHA16}
    os.makedirs(os.path.dirname(npz_p), exist_ok=True)
    C.savez_det(npz_p, **arrays)
    MC.write_json(json_p, meta)
    return arrays, meta


def window(arrays, open_utc, lo_sec, hi_sec):
    """Slice the cached arrays to session seconds [lo_sec, hi_sec)."""
    ts = arrays["ts_ns"]
    lo = (open_utc + int(lo_sec)) * 1_000_000_000
    hi = (open_utc + int(hi_sec)) * 1_000_000_000
    i = int(np.searchsorted(ts, lo, side="left"))
    j = int(np.searchsorted(ts, hi, side="left"))
    return {k: arrays[k][i:j] for k in ARRAYS}, i, j


# --------------------------------------------------------------- derived ----
TRADE_AT_BID, TRADE_AT_ASK, TRADE_MID, TRADE_THRU_B, TRADE_THRU_A, \
    TRADE_UNK = range(6)
TRADE_TAGS = ("@B", "@A", "MID", ">B", ">A", "?")


def classify_trades(arrays):
    """Per-record trade tag against the PREVAILING quote, plus signed flow.

    MUST be called on the FULL cached arrays, never on a slice: the prevailing
    quote of a trade is the L1 carried by the record BEFORE it, so a slice
    would silently classify its first trade against its own post-trade book.
    Callers slice the returned vectors, not the input.  (R98: `assemble` broke
    this contract and was fixed; `test_avail_fixlane.tp03` now holds it.)

    STATED INVARIANT (review 3.2 MINOR, previously unwritten): the FULL cache is
    itself a concatenation of per-candidate blocks, so record 0 of block k
    classifies against the LAST record of block k-1 — a quote from a different
    part of the session.  This is harmless ONLY because every block begins
    RIBBON_DIGEST_SEC + RIBBON_RAW_SEC + EXTRACT_PAD_SEC = 692s before its
    earliest decision second, i.e. no consumed window ever reaches a block
    boundary from the left.  If that padding is ever reduced, this stops being
    harmless; the padding is part of DEF_PARAMS, so a change re-extracts.

    Aggressor sign follows the DBN convention (side = the side that initiates):
    'B' = buy aggressor (+size), 'A' = sell aggressor (-size), 'N' = unsigned.
    Returns (tag_code[n], signed_size[n]); non-trades are TRADE_UNK / 0.
    """
    n = int(arrays["ts_ns"].size)
    tag = np.full(n, TRADE_UNK, dtype=np.int8)
    flow = np.zeros(n, dtype=np.int64)
    if n == 0:
        return tag, flow
    is_t = arrays["action"] == ord("T")
    sz = arrays["size"].astype(np.int64)
    flow = np.where(is_t & (arrays["side"] == ord("B")), sz,
                    np.where(is_t & (arrays["side"] == ord("A")), -sz, 0))
    # prevailing quote = the previous record's L1 (record 0 has no predecessor
    # inside the cache, so it classifies against its own book and is tagged
    # only when that is unambiguous)
    pb = np.empty(n, dtype=np.int64)
    pa = np.empty(n, dtype=np.int64)
    pb[0] = arrays["bid_px"][0]
    pa[0] = arrays["ask_px"][0]
    pb[1:] = arrays["bid_px"][:-1]
    pa[1:] = arrays["ask_px"][:-1]
    ok = ((pb > 0) & (pb < C.SENT_HI) & (pa > 0) & (pa < C.SENT_HI) & is_t)
    p = arrays["price"]
    tag = np.where(ok & (p < pb), np.int8(TRADE_THRU_B), tag)
    tag = np.where(ok & (p > pa), np.int8(TRADE_THRU_A), tag)
    tag = np.where(ok & (p == pb), np.int8(TRADE_AT_BID), tag)
    tag = np.where(ok & (p == pa), np.int8(TRADE_AT_ASK), tag)
    tag = np.where(ok & (p > pb) & (p < pa), np.int8(TRADE_MID), tag)
    return tag.astype(np.int8), flow.astype(np.int64)


def book_state(bid_px, ask_px):
    st, _, _ = C.classify_book(int(bid_px), int(ask_px))
    return st


STATE_TAG = {C.ST_TWO_SIDED: "TS", C.ST_NO_BID: "NB", C.ST_NO_ASK: "NA",
             C.ST_CROSSED: "XX", C.ST_EMPTY: "EM", C.ST_PRE_FIRST: "PF"}

FLAG_TAG = ((C.F_LAST, "L"), (64, "T"), (32, "S"), (16, "M"), (8, "B"),
            (4, "?"))


def flag_str(f):
    s = "".join(t for bit, t in FLAG_TAG if int(f) & bit)
    return s if s else "-"

#!/usr/bin/python3
"""PORT M2 — THE ON-DEMAND RAW EVENT RIBBON (D-080.4).

THE DEFECT THIS CLOSES.  S6 is a FIXED pre-baked window: the preceding 10min as
gap-clustered digests plus whatever of the final 90s the sheet's token budget
buys.  A reader that wanted to see the tape at T-25min, or the whole hour, or
the same 90s at a different resolution, had nowhere to go — and the E1 blind
round's own instrument census recorded "S6 raw events changed 0 calls".  A
window nobody can move is not an instrument.

WHAT THIS IS.  A reader-callable tool that returns ANY CAUSAL WINDOW of the raw
MBP-1 event stream around any candidate, as often as the reader likes, with
every request written to an access ledger so the round can prove what was
actually looked at (the R02 lesson: a protocol claim needs a mechanism).

THE FOUR LAWS IT OBEYS
  1. CAUSALITY IS NOT NEGOTIABLE.  The window ends at or before the END of the
     decision second — `dec_ns = (decision_ts + 1) * 1e9`, the convention
     assemble.py:327-329 and sections.py S6/S7/S9 already assert — and the check
     is routed through `m2_common.CausalGuard` so the leak audit stays one grep.
     A request past it RAISES `m2_common.LeakRefusal`.  There is no flag that
     disables this.
  2. ONE TAPE.  Events come only from the `tape` event cache
     (`tape.ensure` / `tape.window`); a window the cache does not cover EXTENDS
     the cache rather than being silently truncated, and an extension that
     cannot cover the request REFUSES with the reason.
  3. NO DRIFT FROM THE SHEET.  Digests are built by the SAME function the sheet
     uses (`sections._episodes` at `sections.S6_GAP_SEC`), and rendered by the
     same `sections._digest_line` / `sections._event_line`, so the tool and S6
     cannot disagree about what an episode or an event line is.
  4. NOTHING DEGRADES SILENTLY.  A bound that binds is printed with the number
     of rows it withheld; a window clamped at the session open says so; a
     refusal is a value, named and counted.

THE ACTION GRAIN (R2-6 + R2-6-CORRECTION + D-092, 2026-08-15).  `--grain action`
is a FIFTH law on top of the four: the reader-facing raw stream is decoded by
the OFFICIAL `databento-dbn` Python library STRAIGHT OFF THE PAYLOAD FILE — no
cache, no npz, none of our own parsing between the file and the view — and it
renders EVERY record of the requested causal window with full NANOSECOND
`ts_event`, the inter-event gap in nanoseconds, `sequence`, `action`, `side`,
`price` (documented 1e-9 scaling), `size`, `flags` (every documented bit), the
book AFTER the event, and `ts_in_delta`.  There is no sampling, no aggregation,
no rounding and NO ROW BOUND: a window too big to read is narrowed BY THE
READER; the tool never thins (D-092.1).  Column terms are the terms of
design/RIBBON_LEGEND.md and must not drift from it.

CLI
  /usr/bin/python3 engine/port_m2/ribbon.py --cid CID --from FROM --to TO
      [--grain raw|digest|both|action] [--max-rows N] [--ledger PATH]
      [--mode BLIND|STUDY] [--round R] [--caller NAME]
  FROM/TO accept an absolute session second (`7324`) or a decision-relative
  offset (`T-600`, `T-90`, `T`).  Both endpoints are INCLUSIVE session seconds;
  `--to T` therefore means "through the end of the decision second", which is
  exactly the permitted bound.

API
  ribbon.fetch(cid, lo, hi, grain=...) -> dict with the structured rows.
"""
import argparse
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(os.path.dirname(_HERE), "port_m0")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import sections as SEC                    # noqa: E402
import tape as TAPE                       # noqa: E402
import common as C                        # noqa: E402  m0 substrate (iter_dbn)
import databento_dbn as DBN               # noqa: E402  THE official decoder

SECTION = "§1 S6 RAW EVENT RIBBON — on-demand reader tool (D-080.4)"

RIBBON_DIR = MC.out_path("ribbon", "_")[:-1]
ACCESS_LEDGER = os.path.join(RIBBON_DIR, "RIBBON_ACCESS.tsv")
ACCESS_COLUMNS = ("seq", "cid", "asset", "date8", "dec_sec", "from_sec",
                  "to_sec", "grain", "n_events", "n_rows_printed",
                  "tokens_proxy", "decoder", "round", "caller")
# R2-6 added `decoder` in the middle of the row.  Rows already on disk were
# written without it; they are MIGRATED on the next append by inserting the
# named default below at that position, never by silently re-labelling the
# columns they do have.
ACCESS_LEGACY_COLUMNS = ("seq", "cid", "asset", "date8", "dec_sec", "from_sec",
                         "to_sec", "grain", "n_events", "n_rows_printed",
                         "tokens_proxy", "round", "caller")
ACCESS_DEFAULT = {"decoder": "tape-cache(pre-R2-6)"}

GRAIN_RAW, GRAIN_DIGEST, GRAIN_BOTH = "raw", "digest", "both"
GRAIN_ACTION = "action"
GRAINS = (GRAIN_RAW, GRAIN_DIGEST, GRAIN_BOTH, GRAIN_ACTION)

# ------------------------------------------------- the official decoder ------
# Every symbol below is READ OFF THE INSTALLED OFFICIAL LIBRARY, never retyped
# from memory: if databento changes a constant, this module changes with it and
# design/RIBBON_LEGEND.md's generated half changes with it too.
DBN_LIB_VERSION = "unknown"
try:                                       # importlib is the library's own stamp
    import importlib.metadata as _IM       # noqa: E402
    DBN_LIB_VERSION = _IM.version("databento_dbn")
except Exception:                          # noqa: BLE001 — a stamp, never data
    pass

PRICE_SCALE = int(DBN.FIXED_PRICE_SCALE)   # 1e9 fixed-point (documented)
UNDEF_PRICE = int(DBN.UNDEF_PRICE)
UNDEF_ORDER_SIZE = int(DBN.UNDEF_ORDER_SIZE)

# action letter -> the library's own variant name
ACTION_NAME = {str(v): v.name for v in DBN.Action.variants()}
SIDE_NAME = {str(v): v.name for v in DBN.Side.variants()}

# every documented flag bit, with the one-letter tag the ribbon prints.  Bit 1
# is not named by the library; a set unnamed bit prints as `?1` rather than
# being dropped (a bit nobody names is still a bit that was set).
FLAG_BITS = ((int(DBN.F_LAST), "L", "F_LAST"),
             (int(DBN.F_TOB), "T", "F_TOB"),
             (int(DBN.F_SNAPSHOT), "S", "F_SNAPSHOT"),
             (int(DBN.F_MBP), "M", "F_MBP"),
             (int(DBN.F_BAD_TS_RECV), "B", "F_BAD_TS_RECV"),
             (int(DBN.F_MAYBE_BAD_BOOK), "K", "F_MAYBE_BAD_BOOK"),
             (int(DBN.F_PUBLISHER_SPECIFIC), "P", "F_PUBLISHER_SPECIFIC"))

# The action-grain header.  These strings are the COLUMN TERMS of
# design/RIBBON_LEGEND.md; `test_r2views_fixlane.t05` compares the two files so
# the legend and the view cannot drift apart.
ACTION_COLUMNS = ("ts_event", "gap_ns", "sequence", "action", "side", "price",
                  "size", "flags", "bid_px", "bid_sz", "bid_ct", "ask_px",
                  "ask_sz", "ask_ct", "ts_in_delta")
ACTION_WIDTH = (19, 12, 10, 6, 4, 12, 7, 11, 11, 6, 5, 11, 6, 5, 11)
ACTION_HEADER = "  " + " ".join(
    c.rjust(w) for c, w in zip(ACTION_COLUMNS, ACTION_WIDTH))

# The default print bound.  Chosen as the number of raw event lines whose token
# cost equals one blind sheet's whole budget at the S6 exchange rate on record
# (CC-M2-1.1: 25 proxy-tokens per raw second is the SECOND rate; the per-LINE
# estimate the renderer budgets with is sections.S6_RAW_TOKEN_EST).  It is a
# print bound, never a data bound: what it withholds is counted and named.
DEFAULT_MAX_ROWS = MC.SHEET_BUDGET_BLIND // SEC.S6_RAW_TOKEN_EST

# The two column headers are duplicated from `sections._s6_render` because that
# renderer owns them and this lane may not edit it.  `test_builds_fixlane
# .t07_ribbon_headers_match_the_sheet` compares these strings against the ones a
# real rendered sheet prints, so the duplication cannot drift unnoticed.
DIGEST_HEADER = ("    t0     t1     n  nQ  nT  vol szmd szmx sflow  pxH  pxL "
                 "trav$ thru")
RAW_HEADER = "        ms a s   pxT    sz  bidT  bsz  askT  asz    dsz st fl tag"

PARAMS = {
    "spec_section": SECTION,
    "directive": "D-080.4 (the on-demand ribbon tool, ordered)",
    "causal_bound": "window end <= (decision_ts + 1) * 1e9 — the end of the "
                    "decision second; routed through m2_common.CausalGuard, "
                    "raises m2_common.LeakRefusal; no flag disables it",
    "source": "tape.ensure / tape.window ONLY (the per-session MBP-1 event "
              "cache); an uncovered window EXTENDS the cache, never truncates",
    "digest_rule": "sections._episodes at sections.S6_GAP_SEC — gap>=1.0s "
                   "clusters, every event in exactly one episode, NO minimum "
                   "size filter and NO episode-count merge (max_eps = n)",
    "trade_tags": "tape.classify_trades on the FULL cache, then sliced (the "
                  "prevailing-quote rule is broken by classifying a slice)",
    "token_proxy": MC.TOKEN_PROXY_ID,
    "ledger": "one row per invocation; no wall-clock column",
    "action_grain": "R2-6 + R2-6-CORRECTION + D-092: --grain action decodes "
                    "the payload file with the OFFICIAL databento-dbn library "
                    "(%s) and prints EVERY record — full ns ts_event, gap_ns, "
                    "sequence, action, side, price (1e-9), size, flags, book "
                    "after, ts_in_delta. No sampling/aggregation/rounding and "
                    "no row bound." % DBN_LIB_VERSION,
    "action_columns": list(ACTION_COLUMNS),
    "legend": "design/RIBBON_LEGEND.md (R2-7) — the action grain's column "
              "terms are that dictionary's terms",
}


class RibbonRefusal(RuntimeError):
    """The cache cannot cover the requested window.  A value, not an absence:
    it is raised, named, and counted — never a quietly shorter ribbon."""


# ------------------------------------------------------------- endpoints ----
def parse_endpoint(text, dec_sec):
    """`T`, `T-600`, `T+5`, or an absolute session second.

    `T+k` is parsed, not rejected here: the causal guard is the single place
    that refuses a future window, so every refusal carries the same message and
    the audit has one site.
    """
    s = str(text).strip().upper()
    if s.startswith("T"):
        rest = s[1:]
        if rest == "":
            return int(dec_sec)
        if rest[0] not in "+-":
            raise ValueError("bad decision-relative offset %r (want T, T-600, "
                             "T+5)" % text)
        return int(dec_sec) + int(rest)
    return int(s)


# ----------------------------------------------- the official decode path ----
def _letter(v):
    """The enum's own ASCII character (`Action.CLEAR` -> 'R'), never `name[0]`."""
    return str(getattr(v, "value", v))


def flag_terms(f):
    """`130=LP` — the raw byte AND every documented bit it carries."""
    f = int(f)
    tags = [t for bit, t, _n in FLAG_BITS if f & bit]
    unnamed = f & ~sum(bit for bit, _t, _n in FLAG_BITS)
    if unnamed:
        tags.append("?%d" % unnamed)
    return "%d=%s" % (f, "".join(tags) if tags else "-")


def px_terms(raw):
    """The documented 1e-9 fixed-point scaling, EXACTLY — no rounding.

    `FIXED_PRICE_SCALE` is read off the library.  Trailing zeros of the 9-digit
    fraction are dropped, which is lossless; `UNDEF_PRICE` is printed by its
    library name, never as a number that arithmetic could touch.
    """
    v = int(raw)
    if v == UNDEF_PRICE or v == -UNDEF_PRICE:
        return "UNDEF"
    sign = "-" if v < 0 else ""
    whole, frac = divmod(abs(v), PRICE_SCALE)
    s = "%s%d.%09d" % (sign, whole, frac)
    s = s.rstrip("0").rstrip(".")
    return s if s not in ("", "-") else "0"


def sz_terms(v):
    v = int(v)
    return "UNDEF" if v == UNDEF_ORDER_SIZE else str(v)


def decode_window(asset, trade_date, iid, open_utc, close_utc, lo_sec, hi_sec):
    """EVERY MBP-1 record of `iid` with ts_event in [open+lo, open+hi+1).

    THE DECODE IS THE OFFICIAL LIBRARY'S (user order, 2026-08-15): the payload
    file is streamed through `common.iter_dbn`, which is `zstandard` ->
    `databento_dbn.DBNDecoder`, and the record objects handed to the renderer
    are the LIBRARY'S OWN.  No cache, no npz, no field of ours in between.

    Returns (rows, prev_ts_ns, files) where `prev_ts_ns` is the ts_event of the
    last record of this instrument STRICTLY BEFORE the window — the predecessor
    the first row's `gap_ns` is measured against (strictly earlier, so causal),
    or None when the window opens on the instrument's first record of the day.
    """
    lo_ns = (int(open_utc) + int(lo_sec)) * 10 ** 9
    hi_ns = (int(open_utc) + int(hi_sec) + 1) * 10 ** 9
    # Records are time-ordered within a payload file; an hour of slack absorbs
    # the stale-ts SNAPSHOT prologue exactly as tape.extract documents.
    stop_ns = hi_ns + 3600 * 10 ** 9
    rows = []
    prev_ts = None
    files = TAPE.session_payload_files(asset, trade_date, open_utc, close_utc)
    iid = int(iid)
    for p in files:
        stopped = False
        for rec in C.iter_dbn(p):
            if isinstance(rec, DBN.Metadata):
                continue
            t = int(rec.ts_event)
            if t >= stop_ns:
                stopped = True
                break
            if int(rec.instrument_id) != iid:
                continue
            if t < lo_ns:
                prev_ts = t
                continue
            if t >= hi_ns:
                continue
            rows.append({
                "ts_event": t,
                "sequence": int(rec.sequence),
                "action": _letter(rec.action),
                "side": _letter(rec.side),
                "price": int(rec.price),
                "size": int(rec.size),
                "flags": int(rec.flags),
                "depth": int(rec.depth),
                "ts_recv": int(rec.ts_recv),
                "ts_in_delta": int(rec.ts_in_delta),
                "bid_px": int(rec.bid_px_00), "bid_sz": int(rec.bid_sz_00),
                "bid_ct": int(rec.bid_ct_00), "ask_px": int(rec.ask_px_00),
                "ask_sz": int(rec.ask_sz_00), "ask_ct": int(rec.ask_ct_00),
            })
        if stopped:
            break
    return rows, prev_ts, files


def action_lines(rows, prev_ts):
    """One line per record, in stream order.  Nothing is omitted or merged.

    BACKWARD ts_event STEPS (schema audit D3, 2026-08-15): 57 records on the
    NKD yearly files carry a ts_event EARLIER than their predecessor's, and
    every one of them is an F_SNAPSHOT record — a book-state replay folded into
    the stream, not a later event.  A bare negative "gap" there would read as a
    measurement of speed, which it is not: the gap prints `N/A` and the row's
    own `flags` column carries the `S` that explains it.  The count is reported
    to the caller so the header can name it.
    """
    L = [ACTION_HEADER]
    last = prev_ts
    n_back = 0
    for r in rows:
        if last is None:
            gap = "."
        else:
            d = int(r["ts_event"]) - int(last)
            if d < 0:
                n_back += 1
                gap = "N/A"                # see the docstring: F_SNAPSHOT replay
            else:
                gap = str(d)
        last = r["ts_event"]
        cells = (str(r["ts_event"]), gap, str(r["sequence"]), r["action"],
                 r["side"], px_terms(r["price"]), sz_terms(r["size"]),
                 flag_terms(r["flags"]), px_terms(r["bid_px"]),
                 sz_terms(r["bid_sz"]), str(r["bid_ct"]),
                 px_terms(r["ask_px"]), sz_terms(r["ask_sz"]),
                 str(r["ask_ct"]), str(r["ts_in_delta"]))
        L.append("  " + " ".join(c.rjust(w)
                                 for c, w in zip(cells, ACTION_WIDTH)))
    return L, n_back


def _fetch_action(case, lo_req, hi_req, lo_use, clamped):
    rows, prev_ts, files = decode_window(
        case.asset, case.trade_date, int(case.s.iid), case.open_utc,
        case.close_utc, lo_use, hi_req)
    dec_ns = (case.decision_ts + 1) * 10 ** 9
    if rows and int(rows[-1]["ts_event"]) >= dec_ns:
        case.guard.refuse("ribbon action window", "ts_event",
                          int(rows[-1]["ts_event"]))
    L = ["RIBBON ACTION-TYPED RAW EVENT STREAM (MBP-1, dominant iid=%d, "
         "clock=ts_event) cid=%s" % (case.s.iid, case.cid)]
    L.append(MC.row("  decoder",
                    "databento-dbn %s (THE official Databento Python library) "
                    "-> DBNDecoder over the payload file; no cache and no "
                    "parsing of ours between the file and this view"
                    % DBN_LIB_VERSION))
    for p in files:
        L.append("  source    " + p)
    L.append(MC.row("  window",
                    "from=T%+d" % (lo_req - case.dec_sec),
                    " to=T%+d" % (hi_req - case.dec_sec),
                    " sec=[%d,%d]" % (lo_req, hi_req),
                    " dec_sec=" + str(case.dec_sec),
                    " n_events=" + str(len(rows))))
    L.append(MC.row("  bound",
                    "permitted_end_ns=%d" % dec_ns,
                    " (= (decision_ts+1)*1e9, the END of the decision second;"
                    " CausalGuard, D-057/D-080.4)"))
    L.append("  fidelity  EVERY record in the window is printed: no sampling, "
             "no aggregation, no rounding, NO ROW BOUND (D-092.1). A window "
             "too large to read is NARROWED BY THE READER; this tool never "
             "thins.")
    L.append("  legend    design/RIBBON_LEGEND.md — the column terms below are "
             "that dictionary's terms; read it once per session")
    L.append("  scaling   price/bid_px/ask_px = raw int64 / %d "
             "(databento_dbn.FIXED_PRICE_SCALE), printed exactly; UNDEF = the "
             "library's null sentinel" % PRICE_SCALE)
    L.append("  gap_ns    ts_event minus the ts_event of the PREVIOUS record "
             "of this instrument%s"
             % (" (the first row's predecessor is the last record BEFORE the "
                "window, ts_event=%d)" % prev_ts if prev_ts is not None
                else "; the first row has no predecessor in this session and "
                     "prints '.'"))
    if clamped:
        L.append("  CLAMPED from=%d is %ds before the session open; the window "
                 "starts at session second 0 (no event exists before it)"
                 % (lo_req, clamped))
    if not rows:
        L.append("  " + MC.NA + "  no record of this instrument in the window")
    body_lines, n_back = action_lines(rows, prev_ts)
    if n_back:
        L.append("  ts_order  %d record(s) in this window carry a ts_event "
                 "EARLIER than their predecessor's (schema audit D3: every "
                 "observed case is an F_SNAPSHOT book replay, flagged `S` in "
                 "the flags column). Their gap_ns prints N/A — a backward step "
                 "is not a speed measurement." % n_back)
    L.extend(body_lines)
    body = "\n".join(L) + "\n"
    tokens = MC.count_tokens(body)
    L.append("  TOKEN BUDGET tokens_proxy=%d (%s) rows_printed=%d "
             "(count excludes this line)" % (tokens, MC.TOKEN_PROXY_ID,
                                             len(rows)))
    text = "\n".join(L) + "\n"
    return {"cid": case.cid, "asset": case.asset, "date8": int(case.d8),
            "dec_sec": int(case.dec_sec), "from_sec": lo_req,
            "to_sec": hi_req, "from_sec_used": lo_use, "clamped_sec": clamped,
            "grain": GRAIN_ACTION, "n_events": len(rows),
            "n_digests": 0, "n_digests_printed": 0, "n_digests_withheld": 0,
            "n_raw": len(rows), "n_raw_printed": len(rows),
            "n_raw_withheld": 0, "n_rows_printed": len(rows),
            "max_rows": None, "tokens_proxy": tokens,
            "decoder": "databento-dbn %s" % DBN_LIB_VERSION,
            "n_backward_ts": n_back,
            "source_files": files, "action_rows": rows, "prev_ts": prev_ts,
            "digest_rows": [], "raw_rows": list(range(len(rows))),
            "cache_cover": [], "lines": L, "text": text}


# ------------------------------------------------- the differential check ----
DIFF_FIELDS = ("ts_event", "sequence", "action", "side", "price", "size",
               "flags", "bid_px", "ask_px", "bid_sz", "ask_sz", "bid_ct",
               "ask_ct")


def differential_vs_cache(cid, lo, hi, mode=MC.MODE_BLIND, case=None):
    """Field-by-field: the OFFICIAL live decode vs the decoded event cache.

    The cache (`tape.ensure` -> events/<asset>/<d8>.npz) is what every derived
    M2 number is built on, and the action grain deliberately does not read it.
    Two decoders of the same bytes must agree on every field of every record —
    INCLUDING `ts_event` to the nanosecond, which is the field the R2-6
    correction is about.  A disagreement is returned as a NAMED row, never a
    boolean.
    """
    if case is None:
        case = A.Case(cid, mode=mode, want_events=False)
    lo_req = parse_endpoint(lo, case.dec_sec)
    hi_req = parse_endpoint(hi, case.dec_sec)
    case.guard.at_decision(hi_req, "differential window end")
    lo_use = max(0, lo_req)
    rows, _prev, files = decode_window(case.asset, case.trade_date,
                                       int(case.s.iid), case.open_utc,
                                       case.close_utc, lo_use, hi_req)
    want_lo = max(0, lo_use - TAPE.EXTRACT_PAD_SEC)
    cached, meta = TAPE.ensure(case.asset, case.trade_date, int(case.s.iid),
                               case.open_utc, case.close_utc,
                               [(want_lo, hi_req + 1)])
    ev, _i0, _i1 = TAPE.window(cached, case.open_utc, lo_use, hi_req + 1)
    n_live, n_cache = len(rows), int(ev["ts_ns"].size)
    mism = []
    if n_live != n_cache:
        mism.append(("n_events", "-", str(n_live), str(n_cache)))
    for k in range(min(n_live, n_cache)):
        r = rows[k]
        for f in DIFF_FIELDS:
            col = "ts_ns" if f == "ts_event" else f
            got = int(ev[col][k])
            if f in ("action", "side"):
                got = chr(got)
                mine = r[f]
            else:
                mine = int(r[f])
            if mine != got:
                mism.append(("%s[%d]" % (f, k), r["sequence"], str(mine),
                             str(got)))
    return {"cid": case.cid, "asset": case.asset, "date8": int(case.d8),
            "from_sec": lo_req, "to_sec": hi_req, "n_live": n_live,
            "n_cache": n_cache, "n_fields": len(DIFF_FIELDS),
            "n_compared": min(n_live, n_cache) * len(DIFF_FIELDS),
            "n_mismatch": len(mism), "mismatches": mism[:50],
            "decoder": "databento-dbn %s" % DBN_LIB_VERSION,
            "cache": meta.get("def_sha16"), "files": files}


# ------------------------------------------------------------------ fetch ---
def fetch(cid, lo, hi, grain=GRAIN_BOTH, mode=MC.MODE_BLIND,
          max_rows=DEFAULT_MAX_ROWS, case=None):
    """Return the structured ribbon for session seconds [lo, hi] INCLUSIVE.

    Raises LeakRefusal when the window reaches past the decision second's end,
    RibbonRefusal when the event cache cannot cover the window.
    """
    if grain not in GRAINS:
        raise ValueError("grain %r not in %s" % (grain, list(GRAINS)))
    if case is None:
        case = A.Case(cid, mode=mode, want_events=False)
    # endpoints accept an absolute session second OR a decision-relative offset
    # in either the API or the CLI, so a caller never has to do the arithmetic
    lo_req = parse_endpoint(lo, case.dec_sec)
    hi_req = parse_endpoint(hi, case.dec_sec)
    if hi_req < lo_req:
        raise ValueError("empty window: from=%d is after to=%d"
                         % (lo_req, hi_req))

    # --- LAW 1: the causal bound, through the one guard -------------------
    dec_ns = (case.decision_ts + 1) * 10 ** 9
    req_end_ns = (case.open_utc + hi_req + 1) * 10 ** 9
    case.guard.at_decision(
        hi_req,
        "ribbon window end (requested_end_ns=%d permitted_end_ns=%d, "
        "= (decision_ts+1)*1e9)" % (req_end_ns, dec_ns))

    # a window reaching before the session open is CLAMPED and says so; the
    # clamp never reaches the cache (an inverted range would corrupt its cover)
    clamped = max(0, -lo_req)
    lo_use = max(0, lo_req)

    # --- the ACTION grain does not touch the cache at all -----------------
    if grain == GRAIN_ACTION:
        return _fetch_action(case, lo_req, hi_req, lo_use, clamped)

    if hi_req < lo_use:
        # the whole request lies before session second 0 — an empty ribbon, a
        # named state, and NOT a cache touch
        ev = {k: np.zeros(0, dtype=np.int64) for k in TAPE.ARRAYS}
        tag = np.zeros(0, dtype=np.int8)
        flow = np.zeros(0, dtype=np.int64)
        n_ev = 0
        cover = []
    else:
        # --- LAW 2: one tape, extended rather than truncated --------------
        want_lo = max(0, lo_use - TAPE.EXTRACT_PAD_SEC)
        want_hi = hi_req + 1                               # exclusive
        cached, meta = TAPE.ensure(case.asset, case.trade_date,
                                   int(case.s.iid), case.open_utc,
                                   case.close_utc, [(want_lo, want_hi)])
        cover = [(int(a), int(b)) for a, b in meta["cover"]]
        if not TAPE._covers(cover, want_lo, want_hi):
            raise RibbonRefusal(
                "event cache cannot cover [%d, %d) for %s %s: cover=%s — the "
                "window is REFUSED, not truncated"
                % (want_lo, want_hi, case.asset, case.trade_date.isoformat(),
                   cover))
        # classify on the FULL cache, then slice (tape.classify_trades docstring)
        tag_all, flow_all = TAPE.classify_trades(cached)
        ev, i0, i1 = TAPE.window(cached, case.open_utc, lo_use, want_hi)
        tag, flow = tag_all[i0:i1], flow_all[i0:i1]
        n_ev = int(ev["ts_ns"].size)
        if n_ev and int(ev["ts_ns"][-1]) >= dec_ns:
            case.guard.refuse("ribbon tape window", "ts_event",
                              int(ev["ts_ns"][-1]))

    # --- LAW 3: the sheet's own episode construction ----------------------
    digests = []
    if grain in (GRAIN_DIGEST, GRAIN_BOTH) and n_ev:
        # max_eps = n_ev: the merge loop in sections._episodes can never fire,
        # so the clustering is the pure gap>=S6_GAP_SEC partition.
        digests = SEC._episodes(ev, 0, n_ev, SEC.S6_GAP_SEC, max(1, n_ev))

    n_dig_all = len(digests)
    n_raw_all = n_ev if grain in (GRAIN_RAW, GRAIN_BOTH) else 0

    # --- LAW 4: a bound that binds says so --------------------------------
    cap = int(max_rows) if max_rows is not None else None
    dig_show, raw_lo = list(digests), 0
    n_dig_withheld = n_raw_withheld = 0
    if cap is not None and cap >= 0:
        if n_dig_all > cap:              # keep the LATEST digests
            n_dig_withheld = n_dig_all - cap
            dig_show = digests[n_dig_withheld:]
        room = max(0, cap - len(dig_show))
        if n_raw_all > room:             # keep the LATEST raw events
            n_raw_withheld = n_raw_all - room
            raw_lo = n_raw_withheld
    raw_idx = list(range(raw_lo, n_raw_all))

    lines = _render(case, ev, tag, flow, lo_req, hi_req, lo_use, grain,
                    dig_show, raw_idx, n_ev, n_dig_all, n_dig_withheld,
                    n_raw_all, n_raw_withheld, cap, clamped, cover)
    body = "\n".join(lines) + "\n"
    tokens = MC.count_tokens(body)
    n_printed = len(dig_show) + len(raw_idx)
    lines.append("  TOKEN BUDGET tokens_proxy=%d (%s) rows_printed=%d "
                 "(count excludes this line)"
                 % (tokens, MC.TOKEN_PROXY_ID, n_printed))
    text = "\n".join(lines) + "\n"

    return {"cid": case.cid, "asset": case.asset, "date8": int(case.d8),
            "dec_sec": int(case.dec_sec), "from_sec": lo_req,
            "to_sec": hi_req, "from_sec_used": lo_use, "clamped_sec": clamped,
            "grain": grain, "n_events": n_ev,
            "n_digests": n_dig_all, "n_digests_printed": len(dig_show),
            "n_digests_withheld": n_dig_withheld,
            "n_raw": n_raw_all, "n_raw_printed": len(raw_idx),
            "n_raw_withheld": n_raw_withheld,
            "n_rows_printed": n_printed,
            "max_rows": cap, "tokens_proxy": tokens,
            "digest_rows": [(int(a), int(b)) for a, b in dig_show],
            "raw_rows": [int(k) for k in raw_idx],
            "cache_cover": cover, "lines": lines, "text": text,
            "events": ev, "trade_tag": tag, "trade_flow": flow}


def _render(case, ev, tag, flow, lo_req, hi_req, lo_use, grain, dig_show,
            raw_idx, n_ev, n_dig_all, n_dig_withheld, n_raw_all,
            n_raw_withheld, cap, clamped, cover):
    L = ["RIBBON ON-DEMAND (MBP-1, dominant iid=%d, clock=ts_event) cid=%s"
         % (case.s.iid, case.cid)]
    L.append(MC.row("  window",
                    "from=T%+d" % (lo_req - case.dec_sec),
                    " to=T%+d" % (hi_req - case.dec_sec),
                    " sec=[%d,%d]" % (lo_req, hi_req),
                    " dec_sec=" + str(case.dec_sec),
                    " grain=" + grain,
                    " n_events=" + str(n_ev)))
    L.append(MC.row("  bound",
                    "permitted_end_ns=%d" % ((case.decision_ts + 1) * 10 ** 9),
                    " (= (decision_ts+1)*1e9, the END of the decision second;"
                    " CausalGuard, D-057/D-080.4)"))
    if clamped:
        L.append("  CLAMPED from=%d is %ds before the session open; the window "
                 "starts at session second 0 (no event exists before it)"
                 % (lo_req, clamped))
    if n_ev == 0:
        L.append("  " + MC.NA + "  no event in this window (cache cover=%s)"
                 % (cover,))
    if grain in (GRAIN_DIGEST, GRAIN_BOTH):
        L.append("  EPISODE DIGESTS (gap>=%.1fs clusters; every event belongs "
                 "to exactly one episode; NO minimum-size filter) n=%d"
                 % (SEC.S6_GAP_SEC, n_dig_all))
        L.append(DIGEST_HEADER)
        if n_dig_withheld:
            L.append("  MAX-ROWS BOUND BINDS: %d of %d digests withheld (the "
                     "OLDEST); re-run with --max-rows %d for all of them"
                     % (n_dig_withheld, n_dig_all, n_dig_all + n_raw_all))
        for (a, b) in dig_show:
            L.append(SEC._digest_line(case, ev, tag, flow, a, b))
    if grain in (GRAIN_RAW, GRAIN_BOTH):
        L.append("  RAW EVENTS (every event in the window; newest last; prices "
                 "as signed integer ticks vs anchor %s; ms = milliseconds "
                 "before decision_ts, negative = inside the decision second "
                 "itself, which IS the entry book) n=%d"
                 % (MC.fnum(case.anchor, 1, 4).strip(), n_raw_all))
        L.append(RAW_HEADER)
        if n_raw_withheld:
            L.append("  MAX-ROWS BOUND BINDS: %d of %d raw events withheld "
                     "(the OLDEST); re-run with --max-rows %d for all of them"
                     % (n_raw_withheld, n_raw_all, n_dig_all + n_raw_all))
        first = raw_idx[0] if raw_idx else n_raw_all
        pbsz = pasz = None
        # walk the withheld prefix so the FIRST PRINTED line's size delta is
        # measured against its true predecessor rather than printed as missing
        for k in range(first):
            pbsz, pasz = int(ev["bid_sz"][k]), int(ev["ask_sz"][k])
        for k in raw_idx:
            L.append(SEC._event_line(case, ev, tag, k, pbsz, pasz))
            pbsz, pasz = int(ev["bid_sz"][k]), int(ev["ask_sz"][k])
    return L


# ----------------------------------------------------------------- ledger ---
def _read_ledger(path):
    """Rows as dicts on the file's OWN header, then re-keyed onto the current
    schema with named defaults for any column the file predates."""
    rows = []
    if not os.path.exists(path):
        return rows
    cols = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None and f and f[0] == ACCESS_COLUMNS[0]:
                cols = f
                continue
            if cols is None:               # a header-less legacy file
                cols = list(ACCESS_LEGACY_COLUMNS)
            d = dict(zip(cols, f))
            rows.append([d.get(c, ACCESS_DEFAULT.get(c, MC.NA))
                         for c in ACCESS_COLUMNS])
    return rows


def log_access(rec, round_name="-", caller="-", path=None):
    """Append ONE row per invocation.  No wall-clock column: two identical
    request sequences produce byte-identical ledgers."""
    p = path or ACCESS_LEDGER
    rows = _read_ledger(p)
    rows.append([str(len(rows)), rec["cid"], rec["asset"], str(rec["date8"]),
                 str(rec["dec_sec"]), str(rec["from_sec"]), str(rec["to_sec"]),
                 rec["grain"], str(rec["n_events"]),
                 str(rec["n_rows_printed"]), str(rec["tokens_proxy"]),
                 str(rec.get("decoder", "tape-cache")),
                 str(round_name), str(caller)])
    MC.write_tsv(p, SECTION, MC.params_hash(PARAMS), list(ACCESS_COLUMNS), rows,
                 extra=["D-080.4 access ledger: one row per ribbon request; "
                        "seq = row index (deterministic, no wall clock)"])
    return p


# -------------------------------------------------------------------- CLI ---
def main(argv=None):
    ap = argparse.ArgumentParser(description="on-demand raw event ribbon")
    ap.add_argument("--cid", required=True)
    ap.add_argument("--from", dest="frm", required=True,
                    help="session second or T-offset (T, T-600, 7324)")
    ap.add_argument("--to", dest="to", required=True)
    ap.add_argument("--grain", default=GRAIN_BOTH, choices=list(GRAINS))
    ap.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS)
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--mode", default=MC.MODE_BLIND, choices=list(MC.MODES))
    ap.add_argument("--round", dest="round_name", default="-")
    ap.add_argument("--caller", default="-")
    ap.add_argument("--diff-cache", dest="diff_cache", action="store_true",
                    help="differential: official live decode vs the event "
                         "cache, field by field (no ribbon printed)")
    a = ap.parse_args(argv)

    MC.verify_spec()
    if a.diff_cache:
        d = differential_vs_cache(a.cid, a.frm, a.to, mode=a.mode)
        print("DIFFERENTIAL %s [%s,%s] decoder=%s: n_live=%d n_cache=%d "
              "n_fields=%d n_compared=%d n_mismatch=%d"
              % (d["cid"], a.frm, a.to, d["decoder"], d["n_live"],
                 d["n_cache"], d["n_fields"], d["n_compared"],
                 d["n_mismatch"]))
        for m in d["mismatches"]:
            print("  MISMATCH %s seq=%s live=%s cache=%s" % m)
        return 0 if d["n_mismatch"] == 0 else 4
    case = A.Case(a.cid, mode=a.mode, want_events=False)
    lo = parse_endpoint(a.frm, case.dec_sec)
    hi = parse_endpoint(a.to, case.dec_sec)
    try:
        rec = fetch(a.cid, lo, hi, grain=a.grain, mode=a.mode,
                    max_rows=a.max_rows, case=case)
    except (MC.LeakRefusal, RibbonRefusal) as e:
        sys.stderr.write("REFUSED %s: %s\n" % (type(e).__name__, e))
        return 3
    sys.stdout.write(rec["text"])
    p = log_access(rec, a.round_name, a.caller, a.ledger)
    sys.stderr.write("ribbon %s [%d,%d] %s: n_events=%d rows=%d tokens=%d "
                     "-> %s\n" % (a.cid, lo, hi, a.grain, rec["n_events"],
                                  rec["n_rows_printed"], rec["tokens_proxy"],
                                  p))
    return 0


if __name__ == "__main__":
    sys.exit(main())

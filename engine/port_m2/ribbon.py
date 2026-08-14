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

CLI
  /usr/bin/python3 engine/port_m2/ribbon.py --cid CID --from FROM --to TO
      [--grain raw|digest|both] [--max-rows N] [--ledger PATH]
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
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import sections as SEC                    # noqa: E402
import tape as TAPE                       # noqa: E402

SECTION = "§1 S6 RAW EVENT RIBBON — on-demand reader tool (D-080.4)"

RIBBON_DIR = MC.out_path("ribbon", "_")[:-1]
ACCESS_LEDGER = os.path.join(RIBBON_DIR, "RIBBON_ACCESS.tsv")
ACCESS_COLUMNS = ("seq", "cid", "asset", "date8", "dec_sec", "from_sec",
                  "to_sec", "grain", "n_events", "n_rows_printed",
                  "tokens_proxy", "round", "caller")

GRAIN_RAW, GRAIN_DIGEST, GRAIN_BOTH = "raw", "digest", "both"
GRAINS = (GRAIN_RAW, GRAIN_DIGEST, GRAIN_BOTH)

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
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if f and f[0] == ACCESS_COLUMNS[0]:
                continue
            rows.append(f)
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
    a = ap.parse_args(argv)

    MC.verify_spec()
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

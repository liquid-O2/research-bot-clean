#!/usr/bin/python3
"""PORT M2 — SEQUENCE-DERIVED CUES: the things only the raw event stream says.

WHY THIS FILE EXISTS.  Round 1's whole reading surface was scalars at the
decision second, and the extraction's verdict was that the reader's two most
specific mechanisms (E6-H1 refail chain, E6-H2 flow-flip sequence) "were
invisible in the view it was given".  Round 2 puts the true event stream in
front of the reader (R2-1/R2-6), and reading it on study day 1 (2024-04-15,
NKD 02:35 vs 02:36) showed a mechanism no digest column carries:

    price moved 15 index points with THREE trades in it.  The offer did not get
    lifted — it got CANCELLED.  Every time price came to the ask, the ask rows
    were `C A` and the next ask price was higher.  On the other side `A B`
    rows stacked the bid upward.  Nobody paid the spread; one side simply
    refused to be there.

That is the briefing's C(i) "market-making algos refuse to restock" made
literal, and it is a SEQUENCE property: it needs the ordered action codes, not
a 60-second net size delta (`dBsz_min`) which cannot tell a level that was
traded through from a level that was withdrawn.

THE CUES (all causal, all computed on [T-W, T] with W the reader's window)

  cancel_retreat_up   how many times the ASK price rose with NO trade at the
                      old ask inside `TRADE_LOOKBACK_MS` before it moved
  trade_retreat_up    ... and how many times it rose WITH one (real absorption)
  cancel_retreat_dn / trade_retreat_dn   the same on the BID, downward
  pull_ratio_up = cancel_retreat_up / (cancel_retreat_up + trade_retreat_up)
  pull_ratio_dn = ... symmetric
  one_side_pull = pull_ratio_up - pull_ratio_dn   in [-1, +1]; > 0 = the OFFER
                  is the side that keeps vanishing = up-pressure without buying
  add_walk_up   count of `A B` records posting a bid ABOVE the previous best bid
  add_walk_dn   count of `A A` records posting an ask BELOW the previous best ask
  ev_per_s, trade_frac, med_gap_ms, l1_ct_asym (ask_ct - bid_ct at T)

`l1_ct_asym` is included because ORDER COUNT at the touch is in the ribbon and
in NO digest column (`DELTA_COLS` carries `bid_sz`/`ask_sz` only): 30 lots in
2 orders and 30 lots in 15 orders behave differently under pressure
(RIBBON_LEGEND §2).

DATA PATH.  The measurement reads the extraction cache (`tape.ensure`), whose
`action`/`side`/`price` columns are decoded from the payload by the official
library (`tape.py:193`, `rec.action`) — the same bytes the reader-facing
`ribbon.py --grain action` prints.  The reader still reads the real ribbon for
every take (R2-1); this module exists so the cue can be CENSUSED over hundreds
of episodes instead of argued from two of them.

BLIND SAFETY: no outcome import anywhere.  `--census` takes outcomes from
`e6_round.oracle`, which refuses the blind block; the per-episode cue path
(`for_episode`) never touches it and is what the blind days use.

CLI
  seq_cues.py --day D8 --window 120 [--assets SI,HG,NKD] --census
  seq_cues.py --episode EID --window 120
"""
import argparse
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(os.path.dirname(_HERE), "port_m1")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import tape as TAPE                       # noqa: E402
import e6_round as E6                     # noqa: E402

TRADE_LOOKBACK_MS = 250                   # a level that traded within this of
                                          # moving was ABSORBED, not withdrawn
A_, C_, M_, T_ = ord("A"), ord("C"), ord("M"), ord("T")
B_, S_ = ord("B"), ord("A")               # side letters: B = bid, A = ask


def _session(asset, d8):
    r = A.roster(asset)
    i = np.where((r["date8"] == int(d8)))[0]
    if i.size == 0:
        raise SystemExit("no roster rows for %s %s" % (asset, d8))
    i = int(i[0])
    return r, i


def for_window(asset, trade_date, iid, open_utc, close_utc, lo_sec, hi_sec):
    """The sequence cues over session seconds [lo_sec, hi_sec]."""
    arrays, _meta = TAPE.ensure(asset, trade_date, iid, open_utc, close_utc,
                                [(int(lo_sec) - 2, int(hi_sec) + 1)])
    w, _i, _j = TAPE.window(arrays, open_utc, lo_sec, hi_sec + 1)
    return cues_from_window(w)


def cues_from_window(w):
    """THE cue arithmetic, on an already-sliced `TAPE.window` dict.

    `for_window` is (cache load + slice + this).  The split exists so a census
    over tens of thousands of episodes can `TAPE.ensure` a session ONCE and
    slice it per episode, instead of re-opening the same npz per episode
    (measured: 0.37 s/episode re-opening vs ~6 ms sliced).  There is exactly
    ONE copy of the arithmetic and it is the one below (D-006).
    """
    n = int(w["ts_ns"].size)
    out = {"n_ev": n, "ask_reload": 0, "bid_reload": 0, "stack_asym": 0.0,
           "hit_ask": 0, "hit_bid": 0,
           "cancel_retreat_up": 0, "trade_retreat_up": 0,
           "cancel_retreat_dn": 0, "trade_retreat_dn": 0,
           "add_walk_up": 0, "add_walk_dn": 0, "n_trades": 0,
           "ev_per_s": 0.0, "trade_frac": 0.0, "med_gap_ms": float("nan"),
           "l1_ct_asym": float("nan"), "pull_ratio_up": float("nan"),
           "pull_ratio_dn": float("nan"), "one_side_pull": float("nan")}
    if n < 3:
        return out
    ts, act, side = w["ts_ns"], w["action"], w["side"]
    bpx, apx = w["bid_px"], w["ask_px"]
    last_trade_ns = {"bid": -1, "ask": -1}
    lb = TRADE_LOOKBACK_MS * 1_000_000
    for k in range(1, n):
        if act[k] == T_:
            out["n_trades"] += 1
            # a trade's aggressor side tells which resting side was hit
            if side[k] == B_:              # buyer lifted the OFFER
                last_trade_ns["ask"] = int(ts[k])
            elif side[k] == S_:            # seller hit the BID
                last_trade_ns["bid"] = int(ts[k])
            else:
                last_trade_ns["ask"] = last_trade_ns["bid"] = int(ts[k])
            continue
        if apx[k] > apx[k - 1] > 0:        # the OFFER retreated upward
            if int(ts[k]) - last_trade_ns["ask"] <= lb:
                out["trade_retreat_up"] += 1
            else:
                out["cancel_retreat_up"] += 1
        if 0 < bpx[k] < bpx[k - 1]:        # the BID retreated downward
            if int(ts[k]) - last_trade_ns["bid"] <= lb:
                out["trade_retreat_dn"] += 1
            else:
                out["cancel_retreat_dn"] += 1
        if act[k] == A_ and side[k] == B_ and bpx[k] > bpx[k - 1] > 0:
            out["add_walk_up"] += 1
        if act[k] == A_ and side[k] == S_ and 0 < apx[k] < apx[k - 1]:
            out["add_walk_dn"] += 1
    # --- THE CORRECTED SEQUENCE CUE (study day 3 post-mortem) -------------
    # A level that is CLEARED BY A TRADE and then RE-POSTED at the same price
    # is the A2 refail read at book grain: someone is defending a price and
    # being run over there, repeatedly.  `cancel_retreat` measured who was
    # withdrawing and pointed the WRONG WAY on the 2024-04-18 Tokyo pairs;
    # this measures who is being CONSUMED and having to come back.
    px = w["price"]
    cleared_ask, cleared_bid = {}, {}
    for k in range(1, n):
        if act[k] == T_:
            if side[k] == B_:
                out["hit_ask"] += int(w["size"][k])
            elif side[k] == S_:
                out["hit_bid"] += int(w["size"][k])
            continue
        if apx[k] > apx[k - 1] > 0:
            cleared_ask[int(apx[k - 1])] = cleared_ask.get(int(apx[k - 1]), 0) + 1
        elif int(apx[k]) in cleared_ask and apx[k] < apx[k - 1]:
            out["ask_reload"] += 1
            cleared_ask.pop(int(apx[k]), None)
        if 0 < bpx[k] < bpx[k - 1]:
            cleared_bid[int(bpx[k - 1])] = cleared_bid.get(int(bpx[k - 1]), 0) + 1
        elif int(bpx[k]) in cleared_bid and bpx[k] > bpx[k - 1] > 0:
            out["bid_reload"] += 1
            cleared_bid.pop(int(bpx[k]), None)
    ok = (w["ask_ct"] > 0) & (w["bid_ct"] > 0)
    if int(ok.sum()):
        out["stack_asym"] = float(np.median(
            (w["ask_ct"][ok].astype(np.int64) - w["bid_ct"][ok].astype(np.int64))))
    span = max(1e-9, (int(ts[-1]) - int(ts[0])) / 1e9)
    out["ev_per_s"] = n / span
    out["trade_frac"] = out["n_trades"] / float(n)
    out["med_gap_ms"] = float(np.median(np.diff(ts.astype(np.int64)))) / 1e6
    out["l1_ct_asym"] = float(w["ask_ct"][-1]) - float(w["bid_ct"][-1])
    du = out["cancel_retreat_up"] + out["trade_retreat_up"]
    dd = out["cancel_retreat_dn"] + out["trade_retreat_dn"]
    if du:
        out["pull_ratio_up"] = out["cancel_retreat_up"] / float(du)
    if dd:
        out["pull_ratio_dn"] = out["cancel_retreat_dn"] / float(dd)
    if du and dd:
        out["one_side_pull"] = out["pull_ratio_up"] - out["pull_ratio_dn"]
    return out


def for_episode(episode_id, window=120):
    """Sequence cues for one episode's representative, causal to its second."""
    eps, _ = E6.load_day(int(episode_id.split("-")[1]))
    e = [x for x in eps if x["episode_id"] == episode_id]
    if not e:
        raise SystemExit("unknown episode %s" % episode_id)
    e = e[0]
    case = A.Case(e["rep_cid"], mode=MC.MODE_BLIND, want_events=False)
    lo = max(0, int(case.dec_sec) - int(window))
    return for_window(case.asset, case.trade_date, int(case.s.iid),
                      case.open_utc, case.close_utc, lo, int(case.dec_sec))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, default=None)
    ap.add_argument("--episode", default=None)
    ap.add_argument("--assets", default=None)
    ap.add_argument("--window", type=int, default=120)
    ap.add_argument("--census", action="store_true",
                    help="STUDY ONLY: join to outcomes and print lifts")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.episode:
        r = for_episode(a.episode, a.window)
        print(a.episode, " ".join("%s=%s" % (k, r[k]) for k in sorted(r)))
        return 0
    assets = a.assets.split(",") if a.assets else None
    eps, _ = E6.load_day(a.day)
    if assets:
        eps = [e for e in eps if e["asset"] in assets]
    rows = []
    for e in eps:
        case = A.Case(e["rep_cid"], mode=MC.MODE_BLIND, want_events=False)
        lo = max(0, int(case.dec_sec) - a.window)
        r = for_window(case.asset, case.trade_date, int(case.s.iid),
                       case.open_utc, case.close_utc, lo, int(case.dec_sec))
        r["episode_id"] = e["episode_id"]
        r["asset"] = e["asset"]
        r["side"] = 1 if e["side"] == "L" else -1
        rows.append(r)
    if a.out:
        cols = ["episode_id", "asset", "side", "n_ev", "ev_per_s", "trade_frac",
                "med_gap_ms", "l1_ct_asym", "cancel_retreat_up",
                "trade_retreat_up", "cancel_retreat_dn", "trade_retreat_dn",
                "pull_ratio_up", "pull_ratio_dn", "one_side_pull",
                "add_walk_up", "add_walk_dn", "n_trades"]
        with open(a.out, "w") as fh:
            fh.write("\t".join(cols) + "\n")
            for r in rows:
                fh.write("\t".join(str(r.get(c, ".")) for c in cols) + "\n")
        sys.stderr.write("wrote %s (%d rows, window=%ds)\n"
                         % (a.out, len(rows), a.window))
    if a.census:
        res = E6.oracle(a.day, assets)     # refuses the blind block
        win = {}
        for _as, rr in res.items():
            for eid, v in rr["ep_out"].items():
                win[eid] = int(v["rep_win"])
        rows = [r for r in rows if r["episode_id"] in win]
        base = sum(win[r["episode_id"]] for r in rows) / float(len(rows))
        print("SEQ-CUE CENSUS day=%d window=%ds n=%d base=%.4f"
              % (a.day, a.window, len(rows), base))

        def lift(pred, name):
            sel = [r for r in rows if pred(r)]
            if not sel:
                print("  %-34s n=0" % name)
                return
            k = sum(win[r["episode_id"]] for r in sel)
            rate = k / float(len(sel))
            print("  %-34s n=%-5d win=%-4d rate=%.4f lift=%.2f"
                  % (name, len(sel), k, rate, rate / base))

        def sp(r):
            """one_side_pull SIGNED BY THE TRADE SIDE: > 0 = the side the trade
            needs to give way is the one that keeps vanishing."""
            v = r["one_side_pull"]
            return v * r["side"] if v == v else float("nan")

        lift(lambda r: sp(r) == sp(r) and sp(r) >= 0.5, "pull_with_side >= 0.50")
        lift(lambda r: sp(r) == sp(r) and sp(r) >= 0.25, "pull_with_side >= 0.25")
        lift(lambda r: sp(r) == sp(r) and sp(r) > 0, "pull_with_side > 0")
        lift(lambda r: sp(r) == sp(r) and sp(r) < 0, "pull_with_side < 0")
        lift(lambda r: sp(r) == sp(r) and sp(r) <= -0.5, "pull_with_side <= -0.50")
        # for a LONG the side that must give way is the ASK, so ask_ct <
        # bid_ct (asym*side <= -2) is THIN AHEAD; the sign flips for a short.
        lift(lambda r: r["l1_ct_asym"] == r["l1_ct_asym"] and
             r["l1_ct_asym"] * r["side"] <= -2, "l1_count THIN ahead (<=-2)")
        lift(lambda r: r["l1_ct_asym"] == r["l1_ct_asym"] and
             r["l1_ct_asym"] * r["side"] >= 2, "l1_count THICK ahead (>=2)")
        lift(lambda r: (r["add_walk_up"] - r["add_walk_dn"]) * r["side"] >= 3,
             "add_walk_with_side >= 3")
        # reload_with_side > 0: the level the trade needs BROKEN is the one
        # being consumed and re-posted (A2 refail at book grain)
        def rel(r):
            return (r["ask_reload"] - r["bid_reload"]) * r["side"]
        lift(lambda r: rel(r) >= 2, "reload_with_side >= 2")
        lift(lambda r: rel(r) >= 1, "reload_with_side >= 1")
        lift(lambda r: rel(r) <= -1, "reload_against_side <= -1")
        lift(lambda r: r["stack_asym"] * r["side"] <= -1, "stack THIN ahead")
        lift(lambda r: r["stack_asym"] * r["side"] >= 1, "stack THICK ahead")
        lift(lambda r: (r["hit_ask"] - r["hit_bid"]) * r["side"] > 0,
             "aggressor_with_side (sanity vs f60)")
        lift(lambda r: r["trade_frac"] <= 0.05, "trade_frac <= 0.05 (no paying)")
        lift(lambda r: r["trade_frac"] >= 0.20, "trade_frac >= 0.20")
        lift(lambda r: r["med_gap_ms"] == r["med_gap_ms"] and
             r["med_gap_ms"] <= 20, "med_gap <= 20ms (burst)")
        lift(lambda r: r["med_gap_ms"] == r["med_gap_ms"] and
             r["med_gap_ms"] >= 500, "med_gap >= 500ms (dead book)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

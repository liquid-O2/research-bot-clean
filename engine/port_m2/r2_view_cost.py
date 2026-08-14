#!/usr/bin/python3
"""PORT M2 — R2 VIEW COST CENSUS (D-081/D-086 budget law, D-092.3 fidelity).

D-092.3 orders every round receipt to MEASURE consumed fidelity mechanically —
raw-window reads per take, bytes of raw sequence in view per decision — and
D-081/D-086 set the round's scale from the measured day-one burn.  Both need
one number per view type, measured on real E6 days, not estimated.

WHAT IT MEASURES (per asset, on the day given)
  digest_row      one episode's delta row, WITH and WITHOUT the R2-2 3-point
                  trajectory columns; the difference is R2-2's cost.
  ribbon_action   the action-typed raw event stream for a 5-minute causal
                  window (and a 90s one), tokens and events.
  chart_pair      the two R2-5 PNGs, in IMAGE tokens at Read time.

IMAGE TOKENS.  A rendered PNG is charged by area, not by bytes: an image whose
longest side is at or below the client's 1568-px cap is charged
`ceil(w*h/750)` tokens.  Both panels are %dx%d px by construction (fixed
figsize and dpi), so the number is a property of the RENDER CONSTANTS and is
stated as such — `px_w`/`px_h` are carried in the chart receipt so the
arithmetic is checkable.

TEXT TOKENS.  `m2_common.count_tokens` (the M2-PROXY-2 deterministic BPE proxy
this program budgets in everywhere else).  The two units are NOT added together
without saying so: the report prints them side by side.

CLI
  r2_view_cost.py --day 20240118 [--episodes EID,EID,...] [--out PATH]
"""
import argparse
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                     # noqa: E402
import e6_round as E6                      # noqa: E402
import ribbon as RIB                       # noqa: E402
import chart_panel as CP                   # noqa: E402

SECTION = "§1 R2 VIEW COST CENSUS (D-081/D-086/D-092.3)"
OUT = os.path.join(MC.M2_ROOT, "e6_round", "R2_VIEW_COST.tsv")
COLUMNS = ("date8", "asset", "view", "unit", "n_units", "tokens",
            "tokens_per_unit", "detail")

IMAGE_TOKEN_DIVISOR = 750                  # tokens ~= ceil(w*h/750) under the cap
IMAGE_LONG_SIDE_CAP = 1568
DAY_ENVELOPE_TOK = 150000                  # D-086: the measured per-day envelope

__doc__ = __doc__ % (int(round(CP.FIG_W * CP.DPI)), int(round(CP.FIG_H * CP.DPI)))

PARAMS = {
    "spec_section": SECTION,
    "directive": "D-092.3 (measure consumed fidelity mechanically) + "
                 "D-081/D-086 (scale set from the measured burn)",
    "text_tokens": MC.TOKEN_PROXY_ID,
    "image_tokens": "ceil(px_w*px_h/%d) for an image whose longest side is "
                    "<= %d px (both panels are fixed-size by construction)"
                    % (IMAGE_TOKEN_DIVISOR, IMAGE_LONG_SIDE_CAP),
    "windows": "ribbon action grain at T-300..T (5 min) and T-90..T (90 s)",
    "day_envelope_tokens": DAY_ENVELOPE_TOK,
    "collision": "D-092.2 — the R2-1 mandate (a raw window per TAKE) against "
                 "the D-086 day envelope is a LAW COLLISION; this census "
                 "states the arithmetic and does NOT resolve it",
}


def image_tokens(w, h):
    long_side = max(int(w), int(h))
    scale = 1.0 if long_side <= IMAGE_LONG_SIDE_CAP else (
        float(IMAGE_LONG_SIDE_CAP) / long_side)
    return int(math.ceil((int(w) * scale) * (int(h) * scale)
                         / float(IMAGE_TOKEN_DIVISOR)))


def digest_cost(d8, asset):
    with_t = [l for _a, _e, l in E6.deltas(d8, [asset], traj=True)]
    without = [l for _a, _e, l in E6.deltas(d8, [asset], traj=False)]
    n = max(1, len(with_t))
    tw = MC.count_tokens("\n".join(with_t) + "\n")
    tn = MC.count_tokens("\n".join(without) + "\n")
    return {"n": n, "tokens": tw, "per": tw / float(n),
            "tokens_scalar": tn, "per_scalar": tn / float(n),
            "r2_2_per": (tw - tn) / float(n)}


def ribbon_cost(cid, sec):
    rec = RIB.fetch(cid, "T-%d" % sec, "T", grain=RIB.GRAIN_ACTION)
    return {"tokens": rec["tokens_proxy"], "n_events": rec["n_events"],
            "chars": len(rec["text"]),
            "per_event": rec["tokens_proxy"] / float(max(1, rec["n_events"]))}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--episodes", default=None,
                    help="comma list; default = one mid-session episode/asset")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    MC.verify_spec()
    era = MC.era_of(int(a.day))
    idx = CP.read_episode_index(era, a.day)
    by_asset = {}
    for e in idx:
        by_asset.setdefault(e["asset"], []).append(e)

    picks = []
    if a.episodes:
        want = set(a.episodes.split(","))
        picks = [e for e in idx if e["episode_id"] in want]
    else:
        for asset in sorted(by_asset):
            mid = [e for e in by_asset[asset]
                   if 10000 < int(e["first_dec_sec"]) < 40000]
            picks.append((mid or by_asset[asset])[len(mid or
                                                      by_asset[asset]) // 2])

    rows = []
    print("R2 VIEW COST CENSUS  day=%d  text=%s  image=%s"
          % (a.day, MC.TOKEN_PROXY_ID, PARAMS["image_tokens"]))
    w, h = int(round(CP.FIG_W * CP.DPI)), int(round(CP.FIG_H * CP.DPI))
    it = image_tokens(w, h)
    for e in picks:
        asset, cid, eid = e["asset"], e["rep_cid"], e["episode_id"]
        d = digest_cost(a.day, asset)
        rows.append([a.day, asset, "digest_row_R2-2", "episode", d["n"],
                     d["tokens"], round(d["per"], 2),
                     "scalar-only=%d (%.1f/ep); R2-2 adds %.1f tokens/episode"
                     % (d["tokens_scalar"], d["per_scalar"], d["r2_2_per"])])
        for sec, name in ((300, "ribbon_action_5min"),
                          (90, "ribbon_action_90s")):
            r = ribbon_cost(cid, sec)
            rows.append([a.day, asset, name, "window", 1, r["tokens"],
                         r["tokens"],
                         "cid=%s n_events=%d %.1f tok/event %d chars"
                         % (cid, r["n_events"], r["per_event"], r["chars"])])
        rows.append([a.day, asset, "chart_pair_R2-5", "image", 2, 2 * it, it,
                     "%dx%d px each (session+approach), ep=%s" % (w, h, eid)])
        for r in rows[-4:]:
            print("  %-6s %-20s %-8s n=%-5s tokens=%-8s per=%-8s %s"
                  % (r[1], r[2], r[3], r[4], r[5], r[6], r[7]))
    # --- D-092.2: the collision, with its arithmetic, stated not resolved ---
    print("  BUDGET ARITHMETIC (D-092.2 — surfaced, not silently resolved; "
          "envelope %d tok/day per D-086)" % DAY_ENVELOPE_TOK)
    for r in [x for x in rows if x[2] == "ribbon_action_5min"]:
        asset, tok = r[1], int(r[5])
        det = dict(kv.split("=", 1) for kv in r[7].split() if "=" in kv)
        n_ev = int(det.get("n_events", 0))
        rate = tok / 300.0
        for w in (30, 60, 90, 300):
            afford = int(DAY_ENVELOPE_TOK // max(1.0, rate * w))
            rows.append([a.day, asset, "budget_takes_at_%ds" % w, "takes",
                         afford, int(rate * w), int(rate * w),
                         "%.1f tok/window-second measured over %d events; "
                         "%d TAKEs of a %ds raw window fit the %d-token day "
                         "envelope" % (rate, n_ev, afford, w,
                                       DAY_ENVELOPE_TOK)])
            print("    %-4s %3ds window = %7d tok  -> %3d takes/day fit the "
                  "envelope" % (asset, w, int(rate * w), afford))

    p = a.out or OUT
    MC.write_tsv(p, SECTION, MC.params_hash(PARAMS), list(COLUMNS), rows,
                 extra=["text tokens are the %s proxy; IMAGE tokens are the "
                        "area rule — the two units are reported side by side, "
                        "never summed silently" % MC.TOKEN_PROXY_ID])
    print("-> %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
